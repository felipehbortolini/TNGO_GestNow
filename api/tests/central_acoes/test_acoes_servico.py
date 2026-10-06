"""A fachada das ações (ISSUE-019, D9): criação pela costura, replanejamento, conclusão e origem.

Tudo na transação do teste, com a data de referência injetada em 25/09/2026.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from src.core import origin_links
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.scope import Scope
from src.modulos.central_acoes import origins, service
from src.modulos.central_acoes.calculations import ActionStatus, StatusFilter
from src.modulos.central_acoes.origins import ActionEvent
from src.modulos.central_acoes.validation import (
    ActionFilters,
    CompletionRequest,
    ReplanRequest,
)
from tests.apoio_acoes import REFERENCIA, Cenario, nova_acao

PORTFOLIO = Scope(project_id=None, source="padrao")


def _criar(session: Session, cenario: Cenario, **campos: object) -> service.ActionRecord:
    return service.create_action(
        session, user=cenario.gil, new=nova_acao(cenario, **campos), reference_date=REFERENCIA
    )


def _replanejar(
    session: Session, cenario: Cenario, acao: service.ActionRecord, **campos: object
) -> service.ActionRecord:
    base = ReplanRequest(
        action_id=acao.id,
        new_date=REFERENCIA + timedelta(days=20),
        justification="Aguardando a liberação do fornecedor.",
        version=acao.version,
    )
    return service.replan_action(
        session,
        user=cenario.gil,
        request=replace(base, **campos),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


# ── A costura única de criação ───────────────────────────────────────────────


def test_criar_grava_origem_referencia_e_calcula_o_status(
    sessao: Session, cenario: Cenario
) -> None:
    acao = _criar(sessao, cenario)

    assert acao.origin == "Risco"
    assert acao.origin_ref == "RSK-TESTE-0001"
    assert acao.status is ActionStatus.IN_PROGRESS
    achada = service.find_action(
        sessao, user=cenario.gil, action_id=acao.id, reference_date=REFERENCIA
    )
    assert achada is not None
    assert achada.origin_ref == "RSK-TESTE-0001"


def test_criar_com_prevista_no_passado_nasce_atrasada(sessao: Session, cenario: Cenario) -> None:
    acao = _criar(sessao, cenario, planned_date=REFERENCIA - timedelta(days=1))

    assert acao.status is ActionStatus.OVERDUE
    assert acao.days_overdue == 1


def test_criar_com_origem_invalida_ou_sem_referencia_e_recusado(
    sessao: Session, cenario: Cenario
) -> None:
    with pytest.raises(InvalidDataError) as erro:
        _criar(sessao, cenario, origin="Origem inventada", origin_ref="  ")

    assert set(erro.value.detail) >= {"origem", "origem_ref"}  # type: ignore[arg-type]


def test_visualizador_nao_cria_acao(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.create_action(
            sessao, user=cenario.vera, new=nova_acao(cenario), reference_date=REFERENCIA
        )


# ── Replanejar ───────────────────────────────────────────────────────────────


def test_replanejar_muda_a_data_e_guarda_a_justificativa(sessao: Session, cenario: Cenario) -> None:
    acao = _criar(sessao, cenario)

    nova = _replanejar(sessao, cenario, acao)

    assert nova.replanned_date == REFERENCIA + timedelta(days=20)
    historico = service.replan_history(sessao, user=cenario.gil, action_id=acao.id)
    assert len(historico) == 1
    assert historico[0].justification == "Aguardando a liberação do fornecedor."
    assert historico[0].from_date == REFERENCIA + timedelta(days=10)
    assert historico[0].to_date == REFERENCIA + timedelta(days=20)


@pytest.mark.parametrize("justificativa", ["", "   ", "x"])
def test_replanejar_sem_justificativa_e_recusado_e_nada_muda(
    sessao: Session, cenario: Cenario, justificativa: str
) -> None:
    acao = _criar(sessao, cenario)

    with pytest.raises(InvalidDataError) as erro:
        _replanejar(sessao, cenario, acao, justification=justificativa)

    assert "justificativa" in erro.value.detail  # type: ignore[operator]
    assert service.replan_history(sessao, user=cenario.gil, action_id=acao.id) == []


def test_replanejar_com_versao_antiga_da_conflito(sessao: Session, cenario: Cenario) -> None:
    acao = _criar(sessao, cenario)
    _replanejar(sessao, cenario, acao)

    with pytest.raises(VersionConflictError):
        _replanejar(
            sessao,
            cenario,
            acao,
            new_date=REFERENCIA + timedelta(days=30),
        )


def test_acao_da_punch_list_e_tratada_na_origem(sessao: Session, cenario: Cenario) -> None:
    acao = _criar(sessao, cenario, origin="Punch list", origin_ref="PL-TN-1")

    with pytest.raises(InvalidDataError):
        _replanejar(sessao, cenario, acao)


# ── Concluir ─────────────────────────────────────────────────────────────────


def test_concluir_marca_a_acao_como_concluida(sessao: Session, cenario: Cenario) -> None:
    acao = _criar(sessao, cenario)

    feita = service.complete_action(
        sessao,
        user=cenario.gil,
        request=CompletionRequest(action_id=acao.id, completed_on=REFERENCIA, version=acao.version),
        reference_date=REFERENCIA,
    )

    assert feita.status is ActionStatus.COMPLETED


def test_concluir_sem_data_ou_no_futuro_e_recusado(sessao: Session, cenario: Cenario) -> None:
    acao = _criar(sessao, cenario)

    for data in (None, REFERENCIA + timedelta(days=1)):
        with pytest.raises(InvalidDataError):
            service.complete_action(
                sessao,
                user=cenario.gil,
                request=CompletionRequest(
                    action_id=acao.id, completed_on=data, version=acao.version
                ),
                reference_date=REFERENCIA,
            )


# ── A sincronização com a origem ─────────────────────────────────────────────


def test_a_origem_e_avisada_ao_replanejar_e_concluir(
    sessao: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(origins, "_REACTIONS", {})
    avisos: list[tuple[str, ActionEvent]] = []
    origins.register_reaction(
        "Risco", lambda _session, _user, action, event: avisos.append((action.origin_ref, event))
    )
    acao = _criar(sessao, cenario)

    nova = _replanejar(sessao, cenario, acao)
    service.complete_action(
        sessao,
        user=cenario.gil,
        request=CompletionRequest(action_id=acao.id, completed_on=REFERENCIA, version=nova.version),
        reference_date=REFERENCIA,
    )

    assert avisos == [
        ("RSK-TESTE-0001", ActionEvent.REPLANNED),
        ("RSK-TESTE-0001", ActionEvent.COMPLETED),
    ]


def test_a_origem_que_fechou_conclui_as_acoes_e_reabre(sessao: Session, cenario: Cenario) -> None:
    acao = _criar(sessao, cenario)
    origem = origin_links.OriginRef(kind="Risco", reference="RSK-TESTE-0001", record_id=None)

    fechadas = service.close_from_origin(
        sessao, user=cenario.gil, origin=origem, completed_on=REFERENCIA, reference_date=REFERENCIA
    )
    reabertas = service.reopen_from_origin(
        sessao, user=cenario.gil, origin=origem, reference_date=REFERENCIA
    )

    assert [item.id for item in fechadas] == [acao.id]
    assert fechadas[0].status is ActionStatus.COMPLETED
    assert [item.status for item in reabertas] == [ActionStatus.IN_PROGRESS]


# ── A lista ──────────────────────────────────────────────────────────────────


def test_a_lista_filtra_por_status_e_os_kpis_ignoram_o_filtro_de_status(
    sessao: Session, cenario: Cenario
) -> None:
    _criar(sessao, cenario, origin_ref="RSK-A")
    _criar(sessao, cenario, origin_ref="RSK-B", planned_date=REFERENCIA - timedelta(days=3))
    _criar(sessao, cenario, origin_ref="RSK-C", planned_date=REFERENCIA)

    def listar(status: StatusFilter) -> service.ActionListing:
        return service.list_actions(
            sessao,
            user=cenario.gil,
            scope=PORTFOLIO,
            filters=ActionFilters(status=status),
            reference_date=REFERENCIA,
        )

    assert len(listar(StatusFilter.OPEN).rows) == 3
    atrasadas = listar(StatusFilter.OVERDUE)
    assert [linha.record.origin_ref for linha in atrasadas.rows] == ["RSK-B"]
    assert atrasadas.counts.overdue == 1
    assert atrasadas.counts.total == 3
    assert {linha.record.origin_ref for linha in atrasadas.board} == {"RSK-A", "RSK-B", "RSK-C"}


def test_so_acao_entra_na_lista_e_o_escopo_filtra_o_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    _criar(sessao, cenario, origin_ref="RSK-A")
    _criar(sessao, cenario, origin_ref="RSK-B", project_id=cenario.projeto_b.id)
    _criar(
        sessao,
        cenario,
        origin="Ata",
        origin_ref="TN-2026-0001",
        kind="Informação",
        planned_date=None,
    )

    do_projeto_a = service.list_actions(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=cenario.projeto_a.id, source="padrao"),
        filters=ActionFilters(status=StatusFilter.ALL),
        reference_date=REFERENCIA,
    )
    do_portfolio = service.list_actions(
        sessao,
        user=cenario.gil,
        scope=PORTFOLIO,
        filters=ActionFilters(status=StatusFilter.ALL),
        reference_date=REFERENCIA,
    )

    assert [linha.record.origin_ref for linha in do_projeto_a.rows] == ["RSK-A"]
    assert len(do_portfolio.rows) == 2


def test_a_linha_traz_link_so_quando_o_tipo_de_origem_existe(
    sessao: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(origin_links, "_TYPES", {})
    origin_links.register(
        origin_links.OriginLinkType(
            kind="Ata",
            build=lambda ref: origin_links.link_to_screen(
                "central_acoes/ata", codigo=ref.reference
            ),
        )
    )
    _criar(sessao, cenario, origin="Ata", origin_ref="TN-2026-0009")
    _criar(sessao, cenario, origin="Risco", origin_ref="RSK-X")

    listagem = service.list_actions(
        sessao,
        user=cenario.gil,
        scope=PORTFOLIO,
        filters=ActionFilters(status=StatusFilter.ALL),
        reference_date=REFERENCIA,
    )

    links = {linha.record.origin: linha.link for linha in listagem.rows}
    assert links["Ata"].url == "/central-acoes/ata?codigo=TN-2026-0009"
    assert links["Risco"].url is None
    assert links["Risco"].reference == "RSK-X"
