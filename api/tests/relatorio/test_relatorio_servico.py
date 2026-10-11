"""Fachada do relatório gerencial (ISSUE-083): situação do modal, folhas e escopo.

O modal mostra a situação real do relato e da análise de cada módulo sem exigir WRITE — um
Visualizador o vê. As folhas saem no corte do período, com a posição do dono, a produtividade
da janela, as barras do avanço por período e a análise e o relato do período. No Portfólio a
situação do relato sai por projeto e a folha 2 consolida os pontos de atenção.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.core import calendario
from src.core.errors import InvalidDataError
from src.core.scope import Scope
from src.modulos.planejamento import service as planejamento
from src.modulos.planejamento.models import EapItem, EapMeasurement
from src.modulos.planejamento.validation import MONTHLY, WEEKLY
from src.modulos.relatorio import service, validation
from tests.relatorio.conftest import Cenario, Demonstracao

PORTFOLIO = Scope(project_id=None, source="url")

D = Decimal


def _periodo(kind: str, deslocamento: int = 0) -> str:
    return (
        calendario.add_periods(kind, calendario.period_of(kind, calendario.today()), deslocamento)
        or ""
    )


def _escopo(demonstracao: Demonstracao) -> Scope:
    return Scope(project_id=demonstracao.project_id, source="url")


def _status(
    cenario: Cenario,
    *,
    user: object | None = None,
    scope: Scope | None = None,
    kind: str = WEEKLY,
    period: str = "",
    sections: tuple[str, ...] = (),
) -> service.ReportStatusView:
    return service.report_status(
        cenario.session,
        user=user or cenario.visualizador,  # type: ignore[arg-type]
        scope=scope or cenario.scope,
        kind=kind,
        period=period,
        reference_date=calendario.today(),
        sections=sections,
    )


def _gravar_relato(cenario: Cenario, *, kind: str = WEEKLY, period: str) -> None:
    planejamento.save_report(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        request=planejamento.SaveRequest(
            draft=planejamento.ReportDraft(
                kind=kind,
                period=period,
                activities=("Concluída a fundação do prédio da moagem.",),
                next_activities=("Iniciar a montagem das estruturas.",),
            )
        ),
        reference_date=calendario.today(),
    )


def _folhas(
    demonstracao: Demonstracao,
    *,
    scope: Scope | None = None,
    kind: str = WEEKLY,
    period: str = "2026-S38",
    sections: tuple[str, ...] = (),
) -> service.ReportSheets:
    return service.report_view(
        demonstracao.session,
        user=demonstracao.admin,
        scope=scope or _escopo(demonstracao),
        kind=kind,
        period=period,
        sections=sections,
        reference_date=demonstracao.reference_date,
    )


# ── O escopo do relatório ──────────────────────────────────────────────────


def test_escopo_do_relatorio_e_o_pedido_ou_o_do_request(cenario: Cenario) -> None:
    assert service.report_scope(
        cenario.session, fallback=cenario.scope, requested="portfolio"
    ).is_portfolio
    assert (
        service.report_scope(
            cenario.session, fallback=cenario.scope, requested=str(cenario.project.id)
        ).project_id
        == cenario.project.id
    )
    assert (
        service.report_scope(cenario.session, fallback=cenario.scope, requested="").project_id
        == cenario.project.id
    )


def test_escopo_de_projeto_desconhecido_e_recusado(cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as erro:
        service.report_scope(cenario.session, fallback=cenario.scope, requested="99999")

    assert service.UNKNOWN_PROJECT_MESSAGE in str(erro.value)


# ── O modal de emissão ─────────────────────────────────────────────────────


def test_modal_abre_para_visualizador_com_os_padroes(cenario: Cenario) -> None:
    status = _status(cenario)

    assert status.kind == WEEKLY
    assert status.period == _periodo(WEEKLY, -1)
    assert status.in_progress is False
    assert status.relato is not None and status.relato.registered is False
    assert status.project_options[0].value == "portfolio"
    assert status.project_options[0].selected is False
    assert status.project_options[1].value == str(cenario.project.id)
    assert status.project_options[1].selected is True
    assert status.period_options[0].period == _periodo(WEEKLY)
    assert len(status.analyses) == 6
    assert {analise.situation for analise in status.analyses} == {"missing"}
    assert all(analise.url.startswith("/") for analise in status.analyses)
    assert [secao.key for secao in status.sections] == [
        "planejamento",
        "financeiro",
        "suprimentos",
        "riscos",
        "qualidade",
        "hse",
    ]


def test_modal_mostra_o_relato_registrado_com_o_link(cenario: Cenario) -> None:
    _gravar_relato(cenario, period=_periodo(WEEKLY, -1))

    status = _status(cenario)

    assert status.relato is not None
    assert status.relato.registered is True
    assert status.relato.url == (
        f"/planejamento/relato?abrir=1&tipo={WEEKLY}&periodo={_periodo(WEEKLY, -1)}"
    )


def test_modal_do_portfolio_lista_o_relato_por_projeto(cenario: Cenario) -> None:
    status = _status(cenario, scope=PORTFOLIO)

    assert status.relato is None
    assert len(status.project_relatos) == 1
    projeto = status.project_relatos[0]
    assert projeto.registered is False
    assert f"projeto={cenario.project.id}" in projeto.url
    assert all(analise.url.endswith("projeto=portfolio") for analise in status.analyses)


def test_modal_mostra_a_analise_registrada_e_o_desvio_novo_pendente(
    demonstracao: Demonstracao,
) -> None:
    session = demonstracao.session
    item = session.scalars(
        select(EapItem)
        .where(EapItem.project_id == demonstracao.project_id, EapItem.level == 3)
        .order_by(EapItem.weight.desc())
    ).first()
    assert item is not None
    ultima = session.scalars(
        select(EapMeasurement)
        .where(EapMeasurement.item_id == item.id)
        .order_by(EapMeasurement.measured_on.desc())
    ).first()
    assert ultima is not None and ultima.to_pct > D("5")
    session.add(
        EapMeasurement(
            item_id=item.id,
            author_id=demonstracao.admin.person_id,
            measured_on=date(2026, 9, 18),
            from_pct=ultima.to_pct,
            to_pct=ultima.to_pct - D("5"),
        )
    )
    session.flush()

    status = service.report_status(
        session,
        user=demonstracao.admin,
        scope=_escopo(demonstracao),
        kind=WEEKLY,
        period="2026-S38",
        reference_date=demonstracao.reference_date,
    )

    planejamento_status = next(a for a in status.analyses if a.module == "planejamento")
    assert planejamento_status.registered is True
    assert planejamento_status.deviations >= 1
    assert planejamento_status.pending == 1
    assert planejamento_status.situation == "deviations"
    assert planejamento_status.url == (
        "/planejamento/relato?analise=1&tipo=Semanal&periodo=2026-S38"
    )


# ── As folhas ──────────────────────────────────────────────────────────────


def test_folhas_de_projeto_sem_curva_mostram_os_avisos(cenario: Cenario) -> None:
    visao = service.report_view(
        cenario.session,
        user=cenario.visualizador,
        scope=cenario.scope,
        kind=WEEKLY,
        period=_periodo(WEEKLY, -1),
        sections=(),
        reference_date=calendario.today(),
    )

    assert visao.planning is not None
    assert visao.planning.empty is True
    assert visao.planning.bars == ()
    assert visao.planning.predicted_period is None
    assert visao.analysis is not None and visao.analysis.record is None
    assert visao.relato is None
    assert visao.relato_url.startswith("/planejamento/relato?abrir=1")


def test_folhas_do_projeto_1_no_corte_da_semana_38(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao)

    assert visao.cut == date(2026, 9, 20)
    assert visao.in_progress is False
    assert visao.scope_label == "TN-2026-014 · Construção de uma nova fábrica"
    assert visao.sections == (
        "planejamento",
        "financeiro",
        "suprimentos",
        "riscos",
        "qualidade",
        "hse",
    )
    assert visao.carteira is None
    planejamento_folha = visao.planning
    assert planejamento_folha is not None
    assert planejamento_folha.empty is False
    assert planejamento_folha.figures.predicted == D("61.7")
    assert planejamento_folha.figures.actual == D("61.8")
    assert planejamento_folha.figures.spi == D("1.00")
    assert planejamento_folha.figures.deviation_pp == D("0.1")
    assert planejamento_folha.figures.previous_spi == D("1.05")
    assert planejamento_folha.figures.trend_finish == date(2027, 4, 1)
    assert planejamento_folha.figures.baseline_finish == date(2027, 3, 1)
    assert planejamento_folha.week_label == "S38"
    assert [linha.code for linha in planejamento_folha.rows] == ["1", "2", "3", "4", "5"]
    produtividade = planejamento_folha.figures.productivity
    assert produtividade is not None
    assert produtividade.spi == D("0.89")
    assert produtividade.pf_window == D("1.10")
    assert produtividade.adherence == D("83.9")
    assert produtividade.working_pct == D("55.20")
    assert produtividade.utilization == D("77.2")
    assert produtividade.stoppage_hours == D("480.7")
    assert produtividade.stoppage_share == D("2.17")
    assert produtividade.alert_companies == ("Alfa Montagens",)
    assert len(planejamento_folha.bars) == 8
    assert planejamento_folha.bars[0].period == "2026-S31"
    assert planejamento_folha.bars[-1].period == "2026-S38"
    assert planejamento_folha.predicted_period == D("2.9")
    assert planejamento_folha.actual_period == D("0.0")
    assert visao.analysis is not None and visao.analysis.record is not None
    assert visao.analysis_url == "/planejamento/relato?analise=1&tipo=Semanal&periodo=2026-S38"
    assert visao.relato is not None
    assert visao.relato.activities


def test_folhas_do_mensal_do_projeto_1(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, kind=MONTHLY, period="2026-08")

    assert visao.cut == date(2026, 8, 31)
    planejamento_folha = visao.planning
    assert planejamento_folha is not None
    assert planejamento_folha.figures.predicted == D("54.00")
    assert planejamento_folha.figures.actual == D("50.3")
    assert planejamento_folha.figures.spi == D("0.93")
    assert [bar.period for bar in planejamento_folha.bars] == [
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
    ]
    assert planejamento_folha.predicted_period == D("11.9")
    assert planejamento_folha.actual_period == D("11.3")


# ── As folhas Financeiro e Suprimentos (ISSUE-084) ─────────────────────────


def test_folha_financeira_do_projeto_1_no_mes_de_competencia(
    demonstracao: Demonstracao,
) -> None:
    visao = _folhas(demonstracao, sections=("financeiro",))

    folha = visao.financeiro
    assert folha is not None
    assert folha.empty is False
    assert folha.month == date(2026, 8, 1)
    assert folha.month_current is True
    assert folha.is_portfolio is False
    assert folha.budget_cents == 4460000000
    assert folha.actual_cents == 2280000000
    assert folha.actual_month_cents == 520000000
    assert folha.planned_month_cents == 530740000
    assert (folha.ev_cents, folha.pv_cents) == (2243380000, 2408400000)
    assert (folha.cpi, folha.spi, folha.previous_cpi) == (D("0.98"), D("0.93"), D("0.99"))
    assert (folha.projection_cents, folha.vac_cents) == (4525500000, -65500000)
    assert (folha.band_tone, folha.band_label) == ("erro", "Sobrecusto de 1% a 5%")
    assert folha.contingency_pct == D("20.0")
    assert (folha.contingency_consumed_cents, folha.contingency_total_cents) == (
        40000000,
        200000000,
    )
    assert folha.eac_trend_cents == 4532803181
    assert len(folha.history) == 6
    assert folha.history[-1].month == date(2026, 8, 1)
    assert [linha.code for linha in folha.packages] == ["1", "2", "3"]
    assert [linha.band_tone for linha in folha.packages] == ["erro", "neutro", "erro"]
    assert folha.total is not None
    assert (folha.total.band_tone, folha.total.deviation_percent) == ("erro", D("1.5"))
    assert folha.analysis.record is not None
    assert folha.analysis_url == "/financeiro/kpis?analise=1&tipo=Semanal&periodo=2026-S38"


def test_tendencia_da_folha_financeira_parte_do_realizado_de_agosto(
    demonstracao: Demonstracao,
) -> None:
    """A curva da folha é a do dono no mês de competência: sem dado posterior a ele."""
    visao = _folhas(demonstracao, sections=("financeiro",))

    folha = visao.financeiro
    assert folha is not None
    periodos = folha.curve_chart["periodos"]
    agosto = [(item["ano"], item["mes"]) for item in periodos].index((2026, 8))
    valores = [item["valores"] for item in periodos]

    assert valores[agosto]["realizado"] is not None
    assert valores[agosto]["tendencia"] == valores[agosto]["realizado"]
    assert all(item["realizado"] is None for item in valores[agosto + 1 :])
    assert all(item["tendencia"] is not None for item in valores[agosto + 1 :])


def test_folha_financeira_sem_fechamento_mostra_o_aviso(cenario: Cenario) -> None:
    visao = service.report_view(
        cenario.session,
        user=cenario.visualizador,
        scope=cenario.scope,
        kind=WEEKLY,
        period=_periodo(WEEKLY, -1),
        sections=("financeiro",),
        reference_date=calendario.today(),
    )

    folha = visao.financeiro
    assert folha is not None
    assert folha.empty is True
    assert folha.packages == ()
    assert folha.analysis.record is None
    assert folha.analysis_url.startswith("/financeiro/kpis?analise=1")


def test_folha_de_suprimentos_do_projeto_1_no_corte(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, sections=("suprimentos",))

    folha = visao.suprimentos
    assert folha is not None
    assert folha.is_portfolio is False
    assert (folha.adherence_pct, folha.adherence_target) == (D("92.9"), 90)
    assert (folha.adjudicated, folha.planned, folha.packages_total) == (13, 14, 14)
    assert folha.adjudicated_cents == 3900000000
    assert (folha.saving_cents, folha.saving_pct) == (215000000, D("5.2"))
    assert (folha.otd_pct, folha.otd_target) == (D("66.7"), 90)
    assert (folha.delivered, folha.delivered_on_time) == (3, 2)
    assert (folha.critical, folha.warning) == (3, 1)
    assert (folha.emitted, folha.emitted_planned) == (10, 14)
    assert [linha.number for linha in folha.criticals] == [
        "PED-2026-0001",
        "PED-2026-0002",
        "PED-2026-0004",
    ]
    assert [(linha.code, linha.deviation_days) for linha in folha.events] == [("PED-2026-0002", 26)]
    assert (folha.horizon_start, folha.horizon_end) == (date(2026, 9, 21), date(2026, 10, 18))
    assert folha.weekly is True
    assert [linha.code for linha in folha.forecasts] == [
        "PED-2026-0007",
        "PC-14",
        "PED-2026-0009",
        "PED-2026-0001",
        "PED-2026-0002",
        "PED-2026-0005",
    ]
    assert folha.forecasts[1].kind == "Adjudicação"
    assert folha.forecasts[1].deviation_days == 17
    assert folha.curve_chart["periodos"]
    assert folha.analysis.record is not None
    assert folha.analysis_url == "/suprimentos/painel?analise=1&tipo=Semanal&periodo=2026-S38"


def test_folha_de_suprimentos_no_mensal_muda_o_horizonte(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, kind=MONTHLY, period="2026-08", sections=("suprimentos",))

    folha = visao.suprimentos
    assert folha is not None
    assert (folha.horizon_start, folha.horizon_end) == (date(2026, 9, 1), date(2026, 9, 30))
    assert folha.weekly is False
    assert folha.forecasts == ()


def test_folhas_do_portfolio_trazem_financeiro_e_suprimentos(
    demonstracao: Demonstracao,
) -> None:
    visao = _folhas(demonstracao, scope=PORTFOLIO, sections=("financeiro", "suprimentos"))

    financeiro_folha = visao.financeiro
    assert financeiro_folha is not None
    assert financeiro_folha.is_portfolio is True
    assert [linha.project_code for linha in financeiro_folha.packages] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ]
    assert financeiro_folha.total is not None
    suprimentos_folha = visao.suprimentos
    assert suprimentos_folha is not None
    assert suprimentos_folha.is_portfolio is True
    assert all(linha.project_code for linha in suprimentos_folha.forecasts)
    assert suprimentos_folha.critical >= 3


def test_folhas_do_portfolio_consolidam_os_relatos(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, scope=PORTFOLIO)

    assert visao.is_portfolio is True
    assert visao.scope_label == "Portfólio · 3 projetos"
    assert visao.planning is not None and visao.planning.is_portfolio is True
    assert visao.relato is None
    assert len(visao.project_relatos) == 3
    assert visao.relato_points
    assert all(linha.project_label for linha in visao.project_relatos if linha.registered)


def test_folhas_do_periodo_em_andamento_saem_parciais(cenario: Cenario) -> None:
    visao = service.report_view(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        kind=WEEKLY,
        period=_periodo(WEEKLY),
        sections=(),
        reference_date=calendario.today(),
    )

    assert visao.in_progress is True
    assert visao.cut == calendario.today()


def test_folhas_recusam_tipo_periodo_e_secao(cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as tipo:
        service.report_view(
            cenario.session,
            user=cenario.membro,
            scope=cenario.scope,
            kind="Trimestral",
            period=_periodo(WEEKLY),
            sections=(),
            reference_date=calendario.today(),
        )
    with pytest.raises(InvalidDataError) as periodo:
        service.report_view(
            cenario.session,
            user=cenario.membro,
            scope=cenario.scope,
            kind=WEEKLY,
            period="",
            sections=(),
            reference_date=calendario.today(),
        )
    with pytest.raises(InvalidDataError) as secao:
        service.report_view(
            cenario.session,
            user=cenario.membro,
            scope=cenario.scope,
            kind=WEEKLY,
            period=_periodo(WEEKLY),
            sections=("carteira",),
            reference_date=calendario.today(),
        )

    assert validation.FIELD_KIND in dict(tipo.value.detail)  # type: ignore[arg-type]
    assert validation.FIELD_PERIOD in dict(periodo.value.detail)  # type: ignore[arg-type]
    assert dict(secao.value.detail)[validation.FIELD_SECTIONS] == validation.SECTION_MESSAGE  # type: ignore[arg-type]


# ── As folhas Riscos, Qualidade e HSE (ISSUE-085) ──────────────────────────


def test_folha_de_riscos_do_projeto_1_na_referencia(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, sections=("riscos",))

    folha = visao.riscos
    assert folha is not None
    assert visao.carteira is None
    assert (folha.active, folha.registered, folha.threats, folha.opportunities) == (7, 9, 6, 1)
    assert (folha.top.name, folha.top.total, folha.top.threats, folha.top.opportunities) == (
        "Crítico",
        2,
        1,
        1,
    )
    assert folha.top.goal == 0
    assert folha.second is not None
    assert (folha.second.name, folha.second.total, folha.second.goal) == ("Alto", 1, 1)
    assert (folha.exposure_cents, folha.exposure_limit_cents) == (340000000, 160000000)
    assert (folha.overdue_reviews, folha.agenda, folha.identified, folha.closed) == (1, 2, 0, 0)
    celulas = {(celula.probability, celula.impact): celula for celula in folha.matrix}
    assert len(celulas) == 25
    assert (celulas[(4, 4)].text, celulas[(4, 4)].tone) == ("1O", "erro")
    assert (celulas[(3, 5)].text, celulas[(3, 5)].tone) == ("1A", "erro")
    assert celulas[(3, 4)].tone == "atencao"
    assert celulas[(2, 3)].tone == "alerta"
    assert sum(celula.threats + celula.opportunities for celula in folha.matrix) == 7
    assert [ponto.month for ponto in folha.evolution] == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]
    assert [ponto.score for ponto in folha.evolution] == [45, 45, 57, 80, 72, 56]
    assert folha.evolution[-1].current is True
    assert folha.evolution_chart["periodos"][-1]["valores"]["score"] == 56.0
    assert [risco.number for risco in folha.principais] == [
        "RSK-0004",
        "RSK-0003",
        "RSK-0001",
        "RSK-0006",
        "RSK-0002",
    ]
    assert folha.principais[0].nature == "Oportunidade"
    assert folha.principais[0].score == 16
    assert folha.principais[1].review_overdue is True
    assert folha.analysis.record is not None
    assert folha.analysis_url == "/riscos/painel?analise=1&tipo=Semanal&periodo=2026-S38"


def test_folha_da_qualidade_do_projeto_1_no_corte(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, sections=("qualidade",))

    folha = visao.qualidade
    assert folha is not None
    assert (folha.open_at_cut, folha.critical_at_cut, folha.overdue_at_reference) == (4, 0, 1)
    assert (folha.opened_period, folha.closed_period) == (1, 0)
    assert folha.approval_pct == D("66.7")
    assert folha.approval_meta == D("95")
    assert folha.inspections == 3
    assert [
        (linha.point, linha.itp_code, linha.company_name, linha.rnc_code)
        for linha in folha.rejected
    ] == [
        (
            "Torque de ligações estruturais",
            "ITP-TN-MEC-01",
            "Alfa Montagens",
            "RNC-TN-2026-0005",
        )
    ]
    assert (folha.conformity_pct, folha.conformity_meta) == (D("82.9"), D("90"))
    assert (folha.audits_period, folha.late_audits) == (1, 1)
    assert (folha.cost_accumulated_cents, folha.cost_period_cents) == (5670000, 0)
    assert [(linha.name, linha.total) for linha in folha.discipline] == [
        ("Mecânica", 3),
        ("Civil", 2),
        ("Tubulação", 1),
    ]
    assert folha.discipline_total == 6
    assert [ponto.month for ponto in folha.series] == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]
    assert (
        folha.series[-1].opened,
        folha.series[-1].closed,
        folha.series[-1].open,
        folha.series[-1].inspections,
    ) == (3, 1, 4, 11)
    assert folha.series[-1].approval_pct == D("90.9")
    assert folha.series_chart["periodos"][-1]["valores"] == {"abertas": 3, "encerradas": 1}
    assert [entrada.code for entrada in folha.agenda] == ["RNC-TN-2026-0004"]
    assert folha.agenda[0].reasons == ("prazo de tratamento vencido há 8 dias",)
    assert folha.analysis_url == "/qualidade/painel?analise=1&tipo=Semanal&periodo=2026-S38"


def test_folha_hse_do_projeto_1_no_mes_do_corte(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, sections=("hse",))

    folha = visao.hse
    assert folha is not None
    assert folha.empty is False
    assert folha.weekly is True
    assert folha.month == date(2026, 9, 1)
    assert folha.partial_month is True
    assert (folha.base, folha.base_name, folha.reference_name) == (1000000, "NBR 14280", "Bird")
    assert folha.reference_ratio == D("54.5")
    assert folha.observations_target == 40
    mes = folha.month_indicators
    assert (mes.tf, mes.trif, mes.tg) == (D("0.00"), D("6.80"), D("0.0"))
    assert (mes.registrable, mes.lti, mes.hipo, mes.environmental) == (1, 0, 1, 1)
    assert mes.pyramid == (0, 2, 5, 32, 189)
    acumulado = folha.accumulated
    assert (acumulado.hours, acumulado.tf, acumulado.trif, acumulado.tg) == (
        D("788070.00"),
        D("0.00"),
        D("8.88"),
        D("0.0"),
    )
    assert (acumulado.hipo, acumulado.environmental) == (2, 3)
    assert acumulado.pyramid == (0, 16, 31, 190, 1240)
    assert (acumulado.days_without_leave, folha.days_expected) == (258, 258)
    assert folha.days_since == date(2026, 1, 5)
    assert (folha.occurrences, folha.occurrence_levels) == (10, (0, 0, 2, 8))
    assert (folha.hipo_period, folha.month_occurrences) == (0, 39)
    assert (
        acumulado.dds_pct,
        acumulado.conformity_pct,
        acumulado.observations_per_10k,
        acumulado.almost_miss_report,
        acumulado.recommendations_pct,
    ) == (D("94.1"), D("87.0"), D("41.0"), D("27.1"), D("52.9"))
    assert len(folha.evolution_chart["periodos"]) == 6
    assert folha.evolution_chart["periodos"][-1]["valores"] == {"tf": 0.0, "trif": 6.8}
    assert folha.analysis_url == "/hse/painel?analise=1&tipo=Semanal&periodo=2026-S38"


def test_folha_hse_no_mensal_troca_as_ocorrencias_pelo_hht(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, kind=MONTHLY, period="2026-08", sections=("hse",))

    folha = visao.hse
    assert folha is not None
    assert folha.weekly is False
    assert folha.month == date(2026, 8, 1)
    assert folha.partial_month is False
    assert folha.month_indicators.hours == D("140610.00")
    assert folha.month_indicators.trif == D("7.11")
    assert folha.month_indicators.pyramid == (0, 2, 10, 44, 196)
    assert folha.hours_expected is not None and folha.hours_expected > 0
    assert folha.accumulated.days_without_leave == 238


def test_folhas_do_portfolio_consolidam_riscos_qualidade_e_hse(
    demonstracao: Demonstracao,
) -> None:
    visao = _folhas(demonstracao, scope=PORTFOLIO, sections=("riscos", "qualidade", "hse"))

    riscos = visao.riscos
    assert riscos is not None
    assert (riscos.active, riscos.registered) == (16, 19)
    assert (riscos.threats, riscos.opportunities) == (13, 3)
    assert (riscos.top.total, riscos.top.threats, riscos.top.opportunities) == (4, 2, 2)
    assert (riscos.second.total, riscos.second.goal) == (2, 3)  # type: ignore[union-attr]
    assert (riscos.exposure_cents, riscos.exposure_limit_cents) == (487000000, 269000000)
    assert (riscos.overdue_reviews, riscos.agenda) == (3, 5)
    assert [risco.number for risco in riscos.principais] == [
        "RSK-CB-2026-0001",
        "RSK-TN-2026-0004",
        "RSK-CB-2026-0004",
        "RSK-TN-2026-0003",
        "RSK-TN-2026-0001",
    ]
    assert [ponto.score for ponto in riscos.evolution] == [51, 67, 101, 124, 109, 120]
    qualidade = visao.qualidade
    assert qualidade is not None
    assert (qualidade.open_at_cut, qualidade.critical_at_cut) == (7, 1)
    assert qualidade.overdue_at_reference == 1
    assert (qualidade.cost_accumulated_cents, qualidade.discipline_total) == (6920000, 10)
    assert [(linha.name, linha.total) for linha in qualidade.discipline] == [
        ("Civil", 5),
        ("Mecânica", 4),
        ("Tubulação", 1),
    ]
    assert [entrada.code for entrada in qualidade.agenda] == [
        "RNC-TN-2026-0004",
        "RNC-CB-2026-0002",
    ]
    hse = visao.hse
    assert hse is not None
    assert hse.month_indicators.hours == D("204266.00")
    assert (hse.month_indicators.trif, hse.month_indicators.registrable) == (D("9.79"), 2)
    assert hse.month_indicators.pyramid == (0, 3, 7, 45, 245)
    assert hse.accumulated.hours == D("982962.00")
    assert hse.accumulated.pyramid == (0, 22, 39, 236, 1450)
    assert (hse.occurrences, hse.occurrence_levels) == (15, (0, 1, 2, 12))
    assert (hse.month_occurrences, hse.hours_expected) == (55, 204300)
    assert hse.days_expected == 258


def test_folha_da_carteira_do_portfolio_na_referencia(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, scope=PORTFOLIO, sections=())

    carteira = visao.carteira
    assert carteira is not None
    assert visao.is_portfolio is True
    assert (carteira.project_count, carteira.budget_cents) == (3, 7020000000)
    assert carteira.budget_baseline_cents == 7020000000
    assert (carteira.predicted, carteira.actual, carteira.deviation_pp) == (
        D("52.0"),
        D("48.9"),
        D("-3.1"),
    )
    assert (carteira.spi, carteira.spi_tone) == (D("0.94"), "warning")
    assert (carteira.cpi, carteira.cpi_tone) == (D("0.97"), "warning")
    assert (carteira.projection_cents, carteira.vac_cents) == (7116500000, -96500000)
    assert (carteira.baseline_finish, carteira.trend_finish) == (
        date(2027, 6, 1),
        date(2027, 7, 1),
    )
    assert (carteira.critical_risks, carteira.critical_orders, carteira.overdue_actions) == (
        4,
        4,
        14,
    )
    assert [
        (linha.code, linha.weight, linha.health, linha.health_label) for linha in carteira.projects
    ] == [
        ("TN-2026-014", D("55.36"), "warn", "Atenção"),
        ("TN-2026-021", D("29.34"), "erro", "Crítico"),
        ("TN-2026-027", D("15.3"), "warn", "Atenção"),
    ]
    assert carteira.projects[0].trend_finish == date(2027, 4, 1)
    assert carteira.projects[1].vac_cents == 2000000
    assert [(item.name, item.weight, item.source) for item in carteira.criteria] == [
        ("Valor financeiro (orçamento vigente)", D("60"), "orcamento"),
        ("Criticidade estratégica", D("25"), "nota"),
        ("Complexidade e exposição a risco", D("15"), "nota"),
    ]
    assert carteira.curve_chart["periodos"]
