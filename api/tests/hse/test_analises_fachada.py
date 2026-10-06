"""Fachada das análises de risco (ISSUE-074, D9): estudo, recomendação, ação na Central e sincronia.

A recomendação vira ação na Central pela costura única (origem HSE, referência o código do estudo,
item o número da recomendação), com o link de volta ao estudo. A situação fica sincronizada nos dois
sentidos, na mesma transação: fechar a recomendação conclui a ação; concluir a ação na Central fecha
a recomendação; replanejar a ação move o prazo da recomendação.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from src.core import origin_links
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.scope import Scope
from src.modulos.central_acoes import service as central
from src.modulos.central_acoes.validation import CompletionRequest, NewAction, ReplanRequest
from src.modulos.hse import analysis_service as analyses
from src.modulos.hse.analysis_service import AnalysisFilter, RecommendationRef
from src.modulos.hse.validation import (
    AnalysisInput,
    ClosingRecommendationInput,
    RecommendationInput,
)
from tests.apoio_acoes import REFERENCIA, Cenario


def _entrada(cenario: Cenario, **campos: object) -> AnalysisInput:
    base = AnalysisInput(
        project_id=cenario.projeto_a.id,
        kind="APR",
        area="Moagem 210",
        title="Içamento da carcaça do moinho",
        studied_on=REFERENCIA - timedelta(days=10),
        participant_ids=(cenario.gil.person_id, cenario.mario.person_id),
        recommendations=(
            RecommendationInput(
                description="Plano de rigging assinado por engenheiro habilitado.",
                responsible_id=cenario.gil.person_id,
                due_date=REFERENCIA + timedelta(days=5),
            ),
            RecommendationInput(
                description="Teste de carga do guindaste antes da operação.",
                responsible_id=cenario.mario.person_id,
                due_date=REFERENCIA - timedelta(days=2),
            ),
        ),
    )
    return AnalysisInput(**{**base.__dict__, **campos})  # type: ignore[arg-type]


def _registrar(session: Session, cenario: Cenario, **campos: object) -> str:
    saved = analyses.save_analysis(
        session, user=cenario.mario, data=_entrada(cenario, **campos), reference_date=REFERENCIA
    )
    return saved.code


def _estudo(session: Session, cenario: Cenario, code: str) -> analyses.AnalysisRow:
    found = analyses.find_analysis(
        session, user=cenario.mario, code=code, reference_date=REFERENCIA
    )
    assert found is not None
    return found


def _acoes(session: Session, cenario: Cenario, code: str) -> list[central.ActionRecord]:
    return central.list_actions_of_origin(
        session, user=cenario.mario, origin_kind="HSE", reference=code, reference_date=REFERENCIA
    )


def _fechar(session: Session, cenario: Cenario, code: str, position: int) -> None:
    row = _estudo(session, cenario, code).recommendations[position - 1]
    analyses.close_recommendation(
        session,
        user=cenario.mario,
        target=RecommendationRef(code=code, position=position),
        data=ClosingRecommendationInput(closed_on=REFERENCIA, version=row.version),
        reference_date=REFERENCIA,
    )


# ── O estudo ─────────────────────────────────────────────────────────────────


def test_estudo_nasce_numerado_por_tipo_com_recomendacoes_abertas(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)
    hazop = _registrar(sessao, cenario, kind="HAZOP")
    second = _registrar(sessao, cenario)

    assert (code, hazop, second) == (
        "APR-TN-2026-0001",
        "HAZOP-TN-2026-0001",
        "APR-TN-2026-0002",
    )
    study = _estudo(sessao, cenario, code)
    assert [item.status for item in study.recommendations] == ["Aberta", "Aberta"]
    assert [item.position for item in study.recommendations] == [1, 2]
    assert study.counts.open == 2
    assert study.counts.overdue == 1


def test_codigo_do_prototipo_e_aceito_e_a_numeracao_continua_depois_dele(
    sessao: Session, cenario: Cenario
) -> None:
    _registrar(sessao, cenario, code="APR-TN-2026-018")

    assert _registrar(sessao, cenario) == "APR-TN-2026-0019"
    with pytest.raises(InvalidDataError):
        _registrar(sessao, cenario, code="APR-TN-2026-018")


def test_estudo_incompleto_e_recusado_com_a_mensagem_por_campo(
    sessao: Session, cenario: Cenario
) -> None:
    with pytest.raises(InvalidDataError) as caught:
        _registrar(sessao, cenario, title="", participant_ids=(), recommendations=())

    assert {"titulo", "participantes", "recomendacoes"} <= set(caught.value.detail)


def test_visualizador_nao_registra_estudo(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(AccessDeniedError):
        analyses.save_analysis(
            sessao, user=cenario.vera, data=_entrada(cenario), reference_date=REFERENCIA
        )


def test_lista_filtra_por_tipo_busca_e_so_abertas(sessao: Session, cenario: Cenario) -> None:
    apr = _registrar(sessao, cenario)
    hazop = _registrar(sessao, cenario, kind="HAZOP", title="Revisão de segurança do reator")
    scope = Scope(project_id=cenario.projeto_a.id, source="padrao")

    def codes(**filters: object) -> list[str]:
        listing = analyses.list_analyses(
            sessao, scope=scope, filters=AnalysisFilter(**filters), reference_date=REFERENCIA
        )
        return sorted(item.code for item in listing.rows)

    assert codes() == sorted([apr, hazop])
    assert codes(kind="HAZOP") == [hazop]
    assert codes(search="reator") == [hazop]
    assert codes(search="MOAGEM") == sorted([apr, hazop])
    assert codes(search="inexistente") == []
    _fechar(sessao, cenario, hazop, 1)
    _fechar(sessao, cenario, hazop, 2)
    assert codes(only_open=True) == [apr]


# ── A ação na Central ────────────────────────────────────────────────────────


def test_recomendacao_cria_a_acao_com_origem_hse_e_link_de_volta(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)

    action_id = analyses.create_recommendation_action(
        sessao, user=cenario.mario, code=code, position=1, reference_date=REFERENCIA
    )

    (action,) = _acoes(sessao, cenario, code)
    assert action.id == action_id
    assert (action.origin, action.origin_ref, action.item) == ("HSE", code, "1")
    assert action.group == "APR · Recomendação"
    assert action.subject.startswith("Plano de rigging")
    assert action.description == "Içamento da carcaça do moinho (Moagem 210)"
    assert action.responsible_id == cenario.gil.person_id
    assert action.requester_id == cenario.mario.person_id
    assert action.planned_date == REFERENCIA + timedelta(days=5)
    link = origin_links.resolve("HSE", code)
    assert link.url == f"/hse/analises-risco?busca={code}"
    shown = _estudo(sessao, cenario, code).recommendations
    assert shown[0].action_id == action_id
    assert shown[1].action_id is None


def test_a_mesma_recomendacao_nao_gera_duas_acoes(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)
    analyses.create_recommendation_action(
        sessao, user=cenario.mario, code=code, position=1, reference_date=REFERENCIA
    )

    with pytest.raises(InvalidDataError):
        analyses.create_recommendation_action(
            sessao, user=cenario.mario, code=code, position=1, reference_date=REFERENCIA
        )
    assert len(_acoes(sessao, cenario, code)) == 1


def test_recomendacao_inexistente_e_recusada(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)

    with pytest.raises(InvalidDataError):
        analyses.create_recommendation_action(
            sessao, user=cenario.mario, code=code, position=9, reference_date=REFERENCIA
        )
    with pytest.raises(InvalidDataError):
        analyses.create_recommendation_action(
            sessao, user=cenario.mario, code="APR-NAO-EXISTE", position=1, reference_date=REFERENCIA
        )


def test_recomendacao_ja_fechada_gera_a_acao_ja_concluida(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)
    _fechar(sessao, cenario, code, 1)

    analyses.create_recommendation_action(
        sessao, user=cenario.mario, code=code, position=1, reference_date=REFERENCIA
    )

    (action,) = _acoes(sessao, cenario, code)
    assert action.completed_on == REFERENCIA


# ── A sincronia ──────────────────────────────────────────────────────────────


def test_fechar_a_recomendacao_conclui_a_acao_so_dela(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)
    for position in (1, 2):
        analyses.create_recommendation_action(
            sessao, user=cenario.mario, code=code, position=position, reference_date=REFERENCIA
        )

    _fechar(sessao, cenario, code, 1)

    first, second = _acoes(sessao, cenario, code)
    assert first.completed_on == REFERENCIA
    assert second.completed_on is None
    study = _estudo(sessao, cenario, code)
    assert study.recommendations[0].status == "Fechada"
    assert study.recommendations[0].closed_on == REFERENCIA
    assert study.counts.closed == 1


def test_concluir_a_acao_na_central_fecha_a_recomendacao(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)
    analyses.create_recommendation_action(
        sessao, user=cenario.mario, code=code, position=1, reference_date=REFERENCIA
    )
    (action,) = _acoes(sessao, cenario, code)

    central.complete_action(
        sessao,
        user=cenario.gil,
        request=CompletionRequest(
            action_id=action.id, completed_on=REFERENCIA - timedelta(days=1), version=action.version
        ),
        reference_date=REFERENCIA,
    )

    first = _estudo(sessao, cenario, code).recommendations[0]
    assert first.status == "Fechada"
    assert first.closed_on == REFERENCIA - timedelta(days=1)
    assert _estudo(sessao, cenario, code).recommendations[1].status == "Aberta"


def test_replanejar_a_acao_move_o_prazo_da_recomendacao(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)
    analyses.create_recommendation_action(
        sessao, user=cenario.mario, code=code, position=1, reference_date=REFERENCIA
    )
    (action,) = _acoes(sessao, cenario, code)
    new_date = REFERENCIA + timedelta(days=20)

    central.replan_action(
        sessao,
        user=cenario.gil,
        request=ReplanRequest(
            action_id=action.id,
            new_date=new_date,
            justification="Aguardando a liberação do engenheiro.",
            version=action.version,
        ),
        reference_date=REFERENCIA,
    )

    assert _estudo(sessao, cenario, code).recommendations[0].due_date == new_date


def test_acao_de_outra_origem_hse_nao_mexe_em_estudo(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)
    created = central.create_action(
        sessao,
        user=cenario.gil,
        new=central_new(cenario, "OCR-TN-2026-0001"),
        reference_date=REFERENCIA,
    )

    central.complete_action(
        sessao,
        user=cenario.gil,
        request=CompletionRequest(
            action_id=created.id, completed_on=REFERENCIA, version=created.version
        ),
        reference_date=REFERENCIA,
    )

    assert _estudo(sessao, cenario, code).counts.closed == 0


def central_new(cenario: Cenario, reference: str) -> NewAction:
    """Uma ação de HSE que não é de análise de risco: o código é de uma ocorrência."""
    return NewAction(
        project_id=cenario.projeto_a.id,
        origin="HSE",
        origin_ref=reference,
        subject="Investigação da ocorrência",
        requester_id=cenario.mario.person_id,
        responsible_id=cenario.gil.person_id,
        planned_date=REFERENCIA + timedelta(days=3),
    )


def test_fechar_duas_vezes_e_recusado(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)
    _fechar(sessao, cenario, code, 1)

    with pytest.raises(InvalidDataError):
        analyses.close_recommendation(
            sessao,
            user=cenario.mario,
            target=RecommendationRef(code=code, position=1),
            data=ClosingRecommendationInput(closed_on=REFERENCIA, version=2),
            reference_date=REFERENCIA,
        )


def test_fechar_com_data_futura_e_recusado_e_nao_conclui_a_acao(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)
    analyses.create_recommendation_action(
        sessao, user=cenario.mario, code=code, position=1, reference_date=REFERENCIA
    )

    with pytest.raises(InvalidDataError):
        analyses.close_recommendation(
            sessao,
            user=cenario.mario,
            target=RecommendationRef(code=code, position=1),
            data=ClosingRecommendationInput(closed_on=date(2026, 9, 26), version=1),
            reference_date=REFERENCIA,
        )

    (action,) = _acoes(sessao, cenario, code)
    assert action.completed_on is None


def test_fechar_com_versao_velha_da_conflito(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)

    with pytest.raises(VersionConflictError):
        analyses.close_recommendation(
            sessao,
            user=cenario.mario,
            target=RecommendationRef(code=code, position=1),
            data=ClosingRecommendationInput(closed_on=REFERENCIA, version=99),
            reference_date=REFERENCIA,
        )


def test_visualizador_nao_fecha_nem_cria_acao(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)

    with pytest.raises(AccessDeniedError):
        analyses.create_recommendation_action(
            sessao, user=cenario.vera, code=code, position=1, reference_date=REFERENCIA
        )
    with pytest.raises(AccessDeniedError):
        analyses.close_recommendation(
            sessao,
            user=cenario.vera,
            target=RecommendationRef(code=code, position=1),
            data=ClosingRecommendationInput(closed_on=REFERENCIA, version=1),
            reference_date=REFERENCIA,
        )
