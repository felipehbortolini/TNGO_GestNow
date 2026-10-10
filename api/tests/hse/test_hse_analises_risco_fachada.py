"""Fachada das Análises de risco do HSE (ISSUE-074, D5, D9): o registro, a ação e a sincronização.

O estudo nasce com código da série do tipo no projeto e as recomendações nascem Abertas. Cada
recomendação cria no máximo uma ação na Central (origem HSE, com o código do estudo e o item da
ordem) e as duas ficam em passo nas duas direções: concluir a ação fecha a recomendação na data
da conclusão, replanejar move o prazo, fechar a recomendação conclui a ação — e uma ação de
ocorrência (``OCR-``), que divide a origem HSE, não reage.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.core import origin_links
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.validation import CompletionRequest, ReplanRequest
from src.modulos.hse import models, service
from src.modulos.hse.models import (
    RiskAnalysis,
    RiskAnalysisParticipant,
    RiskAnalysisRecommendation,
)
from src.modulos.hse.validation import AnalysisFilters, AnalysisRecommendationInput
from tests.apoio_hse import (
    REFERENCIA,
    Cenario,
    acao_de,
    analise_de,
    fechamento_de_recomendacao,
    investigacao_de,
    ocorrencia_de,
    usuario_de,
)
from tests.identidades import criar_colaborador

ONTEM = REFERENCIA - timedelta(days=1)


def _escopo(cenario: Cenario, *, projeto: bool = True) -> Scope:
    return Scope(project_id=cenario.projeto.id if projeto else None, source="url")


def _registrar(cenario: Cenario, sessao, **campos: object) -> service.AnalysisSave:
    return service.save_analysis(
        sessao, user=cenario.maria, data=analise_de(cenario, **campos), reference_date=REFERENCIA
    )


def _ficha(sessao, cenario: Cenario, codigo: str) -> service.AnalysisSheet:
    ficha = service.analysis_sheet(sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA)
    assert ficha is not None
    return ficha


def _recomendacao(sessao, codigo: str, posicao: int = 1) -> RiskAnalysisRecommendation:
    analise = service.analysis_by_code(sessao, codigo)
    assert analise is not None
    return sessao.scalars(
        select(RiskAnalysisRecommendation).where(
            RiskAnalysisRecommendation.analysis_id == analise.id,
            RiskAnalysisRecommendation.position == posicao,
        )
    ).one()


def _criar_acao(cenario: Cenario, sessao, codigo: str, posicao: int = 1) -> actions.ActionRecord:
    return service.create_recommendation_action(
        sessao, user=cenario.maria, code=codigo, position=posicao, reference_date=REFERENCIA
    )


def _concluir(sessao, cenario: Cenario, record: actions.ActionRecord) -> None:
    actions.complete_action(
        sessao,
        user=cenario.gil,
        request=CompletionRequest(
            action_id=record.id, completed_on=REFERENCIA, version=record.version
        ),
        reference_date=REFERENCIA,
    )


# ── O registro ───────────────────────────────────────────────────────────────────────────────


def test_o_codigo_nasce_da_serie_do_projeto_por_tipo(sessao, cenario: Cenario) -> None:
    apr = _registrar(cenario, sessao)
    hazop = _registrar(cenario, sessao, kind="HAZOP")
    outro = service.save_analysis(
        sessao,
        user=cenario.maria,
        data=analise_de(cenario, project_id=cenario.outro.id),
        reference_date=REFERENCIA,
    )

    assert apr.code == "APR-TN-2026-0001"
    assert hazop.code == "HAZOP-TN-2026-0001", "cada tipo tem a sua série"
    assert outro.code == "APR-TN-2026-0001", "a série é de cada projeto"


def test_o_estudo_grava_participantes_e_recomendacoes_abertas(sessao, cenario: Cenario) -> None:
    salva = _registrar(
        cenario,
        sessao,
        participant_ids=(cenario.gil.person_id, cenario.maria.person_id),
        recommendations=(
            AnalysisRecommendationInput(
                description="Plano de rigging assinado.",
                responsible_id=cenario.gil.person_id,
                due_date=REFERENCIA + timedelta(days=5),
            ),
            AnalysisRecommendationInput(
                description="Isolamento da área de içamento.",
                responsible_id=cenario.maria.person_id,
                due_date=REFERENCIA + timedelta(days=15),
            ),
        ),
    )

    ficha = _ficha(sessao, cenario, salva.code)

    assert ficha.line.title == "Içamento da carcaça do moinho"
    assert ficha.line.participants == 2
    assert ficha.line.participant_names == ("Gil Gestor", "Maria Membro")
    assert [(line.position, line.situation) for line in ficha.line.recommendations] == [
        (1, "Aberta"),
        (2, "Aberta"),
    ]
    assert ficha.line.open_count == 2 and ficha.line.closed_count == 0
    assert ficha.line.recommendations[0].responsible_name == "Gil Gestor"


def test_o_cadastro_das_pessoas_e_conferido(sessao, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError, match="cadastro"):
        _registrar(cenario, sessao, participant_ids=(99999,))

    with pytest.raises(InvalidDataError, match="responsável"):
        _registrar(
            cenario,
            sessao,
            recommendations=(
                AnalysisRecommendationInput(
                    description="Recomendação sem dono.",
                    responsible_id=None,
                    due_date=REFERENCIA,
                ),
            ),
        )


def test_a_validacao_usa_as_mensagens_do_prototipo(sessao, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError, match="título"):
        _registrar(cenario, sessao, title="abc")

    with pytest.raises(InvalidDataError, match="participante"):
        _registrar(cenario, sessao, participant_ids=())

    with pytest.raises(InvalidDataError, match="recomendação"):
        _registrar(cenario, sessao, recommendations=())

    with pytest.raises(InvalidDataError, match="prazo"):
        _registrar(
            cenario,
            sessao,
            recommendations=(
                AnalysisRecommendationInput(
                    description="Recomendação sem prazo.",
                    responsible_id=cenario.gil.person_id,
                    due_date=None,
                ),
            ),
        )

    with pytest.raises(InvalidDataError, match="tipo"):
        _registrar(cenario, sessao, kind="JSA")

    with pytest.raises(InvalidDataError, match="posterior"):
        _registrar(cenario, sessao, held_on=REFERENCIA + timedelta(days=1))


def test_o_visualizador_nao_grava(sessao, cenario: Cenario) -> None:
    vendo = usuario_de(
        sessao,
        criar_colaborador(
            sessao,
            email="vera.analises@example.invalid",
            nome="Vera Visualizadora",
            perfil="Visualizador",
        ),
    )

    with pytest.raises(AccessDeniedError):
        service.save_analysis(
            sessao, user=vendo, data=analise_de(cenario), reference_date=REFERENCIA
        )


# ── A ação na Central (D9) ───────────────────────────────────────────────────────────────────


def test_a_recomendacao_cria_a_acao_na_central_com_link_de_volta(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)

    record = _criar_acao(cenario, sessao, salva.code)

    assert (record.origin, record.origin_ref, record.item) == ("HSE", salva.code, "1")
    assert record.group == "APR · Recomendação"
    assert record.subject == "Plano de rigging assinado por engenheiro habilitado."
    assert record.description == "Içamento da carcaça do moinho (Moagem 210)"
    assert record.responsible_id == cenario.gil.person_id
    assert record.planned_date == REFERENCIA + timedelta(days=10)

    link = origin_links.resolve("HSE", salva.code)
    assert link.has_link and "analises-risco" in (link.url or ""), (
        "o link de volta roteia o código APR para a tela dos estudos"
    )
    link_ocr = origin_links.resolve("HSE", "OCR-TN-2026-0001")
    assert link_ocr.has_link and "ocorrencias" in (link_ocr.url or "")

    ficha = _ficha(sessao, cenario, salva.code)
    assert ficha.line.recommendations[0].action is not None
    assert ficha.line.recommendations[0].action.status_label == "Em andamento"


def test_a_segunda_acao_da_mesma_recomendacao_e_recusada(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)
    _criar_acao(cenario, sessao, salva.code)

    with pytest.raises(InvalidDataError, match="Já existe uma ação na Central"):
        _criar_acao(cenario, sessao, salva.code)


def test_uma_recomendacao_nao_encontrada_e_recusada(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)

    with pytest.raises(InvalidDataError, match="Recomendação não encontrada"):
        _criar_acao(cenario, sessao, salva.code, posicao=9)

    with pytest.raises(InvalidDataError, match="Estudo não encontrado"):
        _criar_acao(cenario, sessao, "APR-TN-2026-9999")


# ── A sincronização (D9, padrão da ISSUE-049) ────────────────────────────────────────────────


def test_concluir_a_acao_fecha_a_recomendacao_na_data_da_conclusao(
    sessao, cenario: Cenario
) -> None:
    salva = _registrar(cenario, sessao)
    record = _criar_acao(cenario, sessao, salva.code)

    _concluir(sessao, cenario, record)

    recomendacao = _recomendacao(sessao, salva.code)
    assert recomendacao.situation == models.RECOMMENDATION_CLOSED
    assert recomendacao.closed_on == REFERENCIA
    ficha = _ficha(sessao, cenario, salva.code)
    assert ficha.line.closed_count == 1 and ficha.line.open_count == 0
    assert ficha.line.recommendations[0].action is not None
    assert ficha.line.recommendations[0].action.status_label == "Concluída"


def test_replanejar_a_acao_move_o_prazo_da_recomendacao(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)
    record = _criar_acao(cenario, sessao, salva.code)
    novo_prazo = REFERENCIA + timedelta(days=30)

    actions.replan_action(
        sessao,
        user=cenario.gil,
        request=ReplanRequest(
            action_id=record.id,
            new_date=novo_prazo,
            justification="O fornecedor do guindaste pediu mais prazo para a mobilização.",
            version=record.version,
        ),
        reference_date=REFERENCIA,
    )

    recomendacao = _recomendacao(sessao, salva.code)
    assert recomendacao.due_date == novo_prazo
    assert recomendacao.situation == models.RECOMMENDATION_OPEN


def test_fechar_a_recomendacao_manualmente_conclui_a_acao(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)
    record = _criar_acao(cenario, sessao, salva.code)

    service.close_recommendation(
        sessao,
        user=cenario.maria,
        code=salva.code,
        position=1,
        data=fechamento_de_recomendacao(),
        reference_date=REFERENCIA,
    )

    recomendacao = _recomendacao(sessao, salva.code)
    assert recomendacao.situation == models.RECOMMENDATION_CLOSED
    assert recomendacao.closed_on == REFERENCIA
    assert recomendacao.evidence == "Lista de verificação assinada em campo."
    concluida = actions.find_action(
        sessao, user=cenario.gil, action_id=record.id, reference_date=REFERENCIA
    )
    assert concluida is not None and concluida.completed_on == REFERENCIA


def test_fechar_a_recomendacao_sem_acao_e_sem_data_e_recusado(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)

    service.close_recommendation(
        sessao,
        user=cenario.maria,
        code=salva.code,
        position=1,
        data=fechamento_de_recomendacao(),
        reference_date=REFERENCIA,
    )
    assert _recomendacao(sessao, salva.code).situation == models.RECOMMENDATION_CLOSED

    with pytest.raises(InvalidDataError, match="já fechada"):
        service.close_recommendation(
            sessao,
            user=cenario.maria,
            code=salva.code,
            position=1,
            data=fechamento_de_recomendacao(),
            reference_date=REFERENCIA,
        )

    outra = _registrar(cenario, sessao, kind="HAZOP")
    with pytest.raises(InvalidDataError, match="data de conclusão"):
        service.close_recommendation(
            sessao,
            user=cenario.maria,
            code=outra.code,
            position=1,
            data=fechamento_de_recomendacao(closed_on=None),
            reference_date=REFERENCIA,
        )

    with pytest.raises(InvalidDataError, match="posterior"):
        service.close_recommendation(
            sessao,
            user=cenario.maria,
            code=outra.code,
            position=1,
            data=fechamento_de_recomendacao(closed_on=REFERENCIA + timedelta(days=1)),
            reference_date=REFERENCIA,
        )


def test_a_acao_da_ocorrencia_nao_reage_na_recomendacao(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)
    ocorrencia = service.save_occurrence(
        sessao, user=cenario.maria, data=ocorrencia_de(cenario), reference_date=REFERENCIA
    )
    service.record_investigation(
        sessao,
        user=cenario.maria,
        code=ocorrencia.code,
        data=investigacao_de(),
        reference_date=REFERENCIA,
    )
    service.define_corrective_actions(
        sessao,
        user=cenario.maria,
        code=ocorrencia.code,
        actions_input=(acao_de(cenario),),
        reference_date=REFERENCIA,
    )
    record = actions.actions_of_origin(
        sessao,
        user=cenario.gil,
        origin_kind="HSE",
        reference=ocorrencia.code,
        reference_date=REFERENCIA,
    )[0]

    _concluir(sessao, cenario, record)

    recomendacao = _recomendacao(sessao, salva.code)
    assert recomendacao.situation == models.RECOMMENDATION_OPEN, (
        "a ação OCR- da ocorrência divide a origem HSE, mas não mexe no estudo"
    )


# ── A lista e o indicador (a ISSUE-075 consome) ─────────────────────────────────────────────


def test_a_tela_filtra_por_tipo_busca_e_abertas(sessao, cenario: Cenario) -> None:
    apr = _registrar(cenario, sessao)
    hazop = _registrar(cenario, sessao, kind="HAZOP", title="Circuito de reagentes")
    service.close_recommendation(
        sessao,
        user=cenario.maria,
        code=apr.code,
        position=1,
        data=fechamento_de_recomendacao(),
        reference_date=REFERENCIA,
    )

    todas = service.analyses_screen(
        sessao,
        scope=_escopo(cenario),
        filters=AnalysisFilters(),
        reference_date=REFERENCIA,
    )
    so_hazop = service.analyses_screen(
        sessao,
        scope=_escopo(cenario),
        filters=AnalysisFilters(kind="HAZOP"),
        reference_date=REFERENCIA,
    )
    abertas = service.analyses_screen(
        sessao,
        scope=_escopo(cenario),
        filters=AnalysisFilters(open_only=True),
        reference_date=REFERENCIA,
    )
    busca = service.analyses_screen(
        sessao,
        scope=_escopo(cenario),
        filters=AnalysisFilters(search="reagentes"),
        reference_date=REFERENCIA,
    )

    assert todas.universe == 2 and len(todas.rows) == 2
    assert todas.rows[0].held_on == REFERENCIA, "a lista vem da data mais recente"
    assert [row.code for row in so_hazop.rows] == [hazop.code]
    assert [row.code for row in abertas.rows] == [hazop.code]
    assert [row.code for row in busca.rows] == [hazop.code]
    assert todas.summary.open == 1 and todas.summary.closed == 1
    assert todas.summary.closed_pct == Decimal("50.0")


def test_o_indicador_do_painel_conta_fechadas_sobre_emitidas(sessao, cenario: Cenario) -> None:
    salva = _registrar(
        cenario,
        sessao,
        recommendations=(
            AnalysisRecommendationInput(
                description="Plano de rigging assinado.",
                responsible_id=cenario.gil.person_id,
                due_date=REFERENCIA + timedelta(days=5),
            ),
            AnalysisRecommendationInput(
                description="Isolamento da área.",
                responsible_id=cenario.gil.person_id,
                due_date=REFERENCIA + timedelta(days=15),
            ),
        ),
    )

    antes = service.recommendation_share(sessao, scope=_escopo(cenario))
    assert (antes.closed, antes.emitted) == (0, 2)
    assert antes.pct == Decimal("0.0")

    service.close_recommendation(
        sessao,
        user=cenario.maria,
        code=salva.code,
        position=1,
        data=fechamento_de_recomendacao(),
        reference_date=REFERENCIA,
    )

    depois = service.recommendation_share(sessao, scope=_escopo(cenario))
    assert (depois.closed, depois.emitted) == (1, 2)
    assert depois.pct == Decimal("50.0")

    carteira = service.recommendation_share(sessao, scope=_escopo(cenario, projeto=False))
    assert carteira.emitted == 2, "a carteira soma os estudos dos projetos"


def test_a_contagem_no_banco_do_cenario_e_do_fluxo(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)

    assert sessao.scalar(select(func.count()).select_from(RiskAnalysis)) == 1
    assert sessao.scalar(select(func.count()).select_from(RiskAnalysisParticipant)) == 1
    assert sessao.scalar(select(func.count()).select_from(RiskAnalysisRecommendation)) == 1
    assert _recomendacao(sessao, salva.code).situation == models.RECOMMENDATION_OPEN
