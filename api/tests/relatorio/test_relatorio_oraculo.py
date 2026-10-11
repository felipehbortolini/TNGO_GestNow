"""Oráculo do relatório gerencial (ISSUE-083/ISSUE-084): as folhas do projeto 1 em 2026-S38.

Na demonstração, o corte da semana 38 é 20/09/2026 e as folhas do projeto 1 saem com a
posição da leitura semanal do dono — o previsto interpolado dentro do mês (61,7%, contra 65,7%
do ponto do mês) e o real medido (61,8%, parado desde a semana anterior) —, a produtividade da
janela de quatro semanas (SPI de quantidades 0,89, FP 1,10, aderência 83,9%, pessoas trabalhando
55,2%, utilização 77,2% e 480,7 HH paralisadas, com a Alfa Montagens em alerta), as barras das
últimas 8 semanas e a análise e o relato do período registrados. O custo usa o mês de
competência (2026-08 no semanal): a folha Financeiro sai com os KPIs da tela (BAC 44.600, EV
22.434, AC 22.800, CPI 0,98, projeção 45.255 e VAC -655 mil) e a tendência partindo do realizado
de agosto — sem dado posterior —, e a folha Suprimentos com o painel no corte (aderência 92,9%,
13 de 14 adjudicados, saving 5,2%, OTD 66,7% e 3 pedidos críticos) e o horizonte de S39 a S42.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core import calendario
from src.core.auth import _user_of
from src.core.rbac import GeneralProfile
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.relatorio import calculations, service
from tests.oraculo import OracleContext, harness

PROJECT_1 = "TN-2026-014"

D = Decimal


def _afirmar_as_folhas(context: OracleContext) -> None:
    admin = next(
        acesso
        for acesso in configuracoes.list_active_access(context.session)
        if acesso.general_profile == GeneralProfile.ADMIN
    )
    project = next(
        item for item in configuracoes.list_projects(context.session) if item.code == PROJECT_1
    )
    visao = service.report_view(
        context.session,
        user=_user_of(admin),
        scope=Scope(project_id=project.id, source="url"),
        kind=calendario.WEEKLY,
        period="2026-S38",
        sections=("planejamento", "financeiro", "suprimentos"),
        reference_date=context.reference_date,
    )

    assert visao.cut == date(2026, 9, 20), "corte da semana 38"
    planejamento = visao.planning
    assert planejamento is not None
    assert (planejamento.figures.predicted, planejamento.figures.actual) == (
        D("61.7"),
        D("61.8"),
    ), "posicao interpolada no corte semanal"
    assert planejamento.figures.deviation_pp == D("0.1"), "desvio acumulado no corte"
    assert planejamento.figures.spi == D("1.00"), "SPI fisico no corte"
    assert (
        planejamento.figures.previous_predicted,
        planejamento.figures.previous_actual,
        planejamento.figures.previous_spi,
    ) == (D("58.8"), D("61.8"), D("1.05")), "posicao anterior"
    assert (
        planejamento.figures.predicted_period,
        planejamento.figures.actual_period,
    ) == (D("2.9"), D("0.0")), "avanco do periodo na semana"
    assert planejamento.figures.trend_finish == date(2027, 4, 1), "termino pela tendencia"
    assert planejamento.figures.baseline_finish == date(2027, 3, 1), "termino da linha de base"
    produtividade = planejamento.figures.productivity
    assert produtividade is not None
    assert (
        produtividade.spi,
        produtividade.pf_window,
        produtividade.adherence,
        produtividade.working_pct,
        produtividade.utilization,
    ) == (D("0.89"), D("1.10"), D("83.9"), D("55.20"), D("77.2")), "produtividade da janela"
    assert produtividade.stoppage_hours == D("480.7"), "HH paralisadas na janela"
    assert produtividade.alert_companies == ("Alfa Montagens",), "empresas em alerta"
    assert len(planejamento.bars) == 8, "barras das ultimas 8 semanas"
    assert planejamento.bars[-1].period == "2026-S38"
    assert visao.analysis is not None and visao.analysis.record is not None, "analise registrada"
    assert visao.relato is not None and visao.relato.activities, "relato registrado"
    assert calculations.competence_month(calendario.WEEKLY, "2026-S38") == date(2026, 8, 1), (
        "custo apurado no ultimo mes fechado"
    )
    financeiro = visao.financeiro
    assert financeiro is not None and financeiro.empty is False, "folha financeira montada"
    assert financeiro.month == date(2026, 8, 1), "competencia de agosto"
    assert (
        financeiro.budget_cents,
        financeiro.actual_cents,
        financeiro.actual_month_cents,
    ) == (4460000000, 2280000000, 520000000), "BAC, realizado acumulado e do mes"
    assert (financeiro.ev_cents, financeiro.pv_cents) == (2243380000, 2408400000), (
        "valor agregado (EV e PV)"
    )
    assert (financeiro.cpi, financeiro.spi, financeiro.previous_cpi) == (
        D("0.98"),
        D("0.93"),
        D("0.99"),
    ), "indices de custo"
    assert (financeiro.projection_cents, financeiro.vac_cents) == (4525500000, -65500000), (
        "projecao no termino e VAC"
    )
    assert financeiro.eac_trend_cents == 4532803181, "EAC por desempenho no mes do relatorio"
    periodos = financeiro.curve_chart["periodos"]
    agosto = [(item["ano"], item["mes"]) for item in periodos].index((2026, 8))
    valores = [item["valores"] for item in periodos]
    assert valores[agosto]["tendencia"] == valores[agosto]["realizado"], (
        "tendencia partindo do realizado de agosto"
    )
    assert all(item["realizado"] is None for item in valores[agosto + 1 :]), (
        "sem dado posterior ao mes do relatorio"
    )
    assert all(item["tendencia"] is not None for item in valores[agosto + 1 :]), (
        "tendencia ate a EAC depois do corte"
    )
    assert [linha.band_tone for linha in financeiro.packages] == ["erro", "neutro", "erro"], (
        "faixas de calor da EAC por pacote"
    )
    assert financeiro.analysis.record is not None, "analise do financeiro registrada"
    suprimentos = visao.suprimentos
    assert suprimentos is not None, "folha de suprimentos montada"
    assert (suprimentos.adherence_pct, suprimentos.otd_pct) == (D("92.9"), D("66.7")), (
        "aderencia e OTD no corte"
    )
    assert (suprimentos.adjudicated, suprimentos.planned) == (13, 14), "pacotes adjudicados"
    assert (suprimentos.saving_cents, suprimentos.critical) == (215000000, 3), "saving e criticos"
    assert (suprimentos.horizon_start, suprimentos.horizon_end) == (
        date(2026, 9, 21),
        date(2026, 10, 18),
    ), "horizonte de S39 a S42"
    assert [linha.code for linha in suprimentos.events] == ["PED-2026-0002"], (
        "marco realizado no periodo"
    )
    assert suprimentos.analysis.record is not None, "analise de suprimentos registrada"


def test_oraculo_do_relatorio_gerencial(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    _afirmar_as_folhas(context)
