"""Oráculo do relatório gerencial (ISSUE-083 a ISSUE-085): as folhas do projeto 1 em 2026-S38.

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
A ISSUE-085 fecha as folhas 5 a 7 na posição da data de referência (25/09/2026): Riscos com 7
ativos e a exposição de R$ 3,4 mi, Qualidade com 4 RNC abertas no corte e as 3 inspeções do
período, HSE com as taxas do mês parcial e a pirâmide, e — no segundo teste — a Carteira de
projetos do Portfólio com os pesos 55,36/29,34/15,30 e os consolidados da carteira.
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
        sections=("planejamento", "financeiro", "suprimentos", "riscos", "qualidade", "hse"),
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
    _afirmar_financeiro(visao)
    _afirmar_suprimentos(visao)
    assert visao.carteira is None, "a carteira e so do Portfolio"
    _afirmar_riscos(visao)
    _afirmar_qualidade(visao)
    _afirmar_hse(visao)


def _afirmar_financeiro(visao: service.ReportSheets) -> None:
    """A folha Financeiro no mes de competencia, com a tendencia partindo de agosto."""
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


def _afirmar_suprimentos(visao: service.ReportSheets) -> None:
    """A folha Suprimentos no corte, com o horizonte de S39 a S42."""
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


def _afirmar_riscos(visao: service.ReportSheets) -> None:
    """A folha Riscos na data de referencia: 7 ativos, a matriz residual e os principais."""
    riscos = visao.riscos
    assert riscos is not None, "folha de riscos montada"
    assert (riscos.active, riscos.registered) == (7, 9), "riscos ativos e cadastrados"
    assert (riscos.threats, riscos.opportunities) == (6, 1), "ameacas e oportunidades ativas"
    assert (riscos.top.name, riscos.top.total, riscos.top.goal) == ("Crítico", 2, 0), (
        "faixa do topo com a meta"
    )
    assert riscos.second is not None
    assert (riscos.second.name, riscos.second.total, riscos.second.goal) == ("Alto", 1, 1), (
        "segunda faixa com a meta"
    )
    assert (riscos.exposure_cents, riscos.exposure_limit_cents) == (340000000, 160000000), (
        "exposicao (VME) e o saldo da reserva de contingencia"
    )
    assert (riscos.overdue_reviews, riscos.agenda) == (1, 2), "revisao vencida e pauta"
    assert (riscos.identified, riscos.closed) == (0, 0), "identificados e encerrados no periodo"
    celulas = {(celula.probability, celula.impact): celula for celula in riscos.matrix}
    assert len(celulas) == 25, "matriz 5 x 5"
    assert (celulas[(4, 4)].text, celulas[(4, 4)].tone) == ("1O", "erro"), "celula P4 x I4"
    assert celulas[(3, 4)].tone == "atencao", "tom da faixa alta"
    assert sum(celula.threats + celula.opportunities for celula in riscos.matrix) == 7, (
        "os sete ativos na matriz"
    )
    assert [ponto.score for ponto in riscos.evolution] == [45, 45, 57, 80, 72, 56], (
        "exposicao mensal das ameacas"
    )
    assert [risco.number for risco in riscos.principais] == [
        "RSK-0004",
        "RSK-0003",
        "RSK-0001",
        "RSK-0006",
        "RSK-0002",
    ], "principais riscos pelo score residual, sem o prefixo do projeto"
    assert riscos.principais[1].review_overdue is True, "revisao vencida marcada"


def _afirmar_qualidade(visao: service.ReportSheets) -> None:
    """A folha Qualidade no corte: a posicao, o periodo, a serie e a pauta na referencia."""
    qualidade = visao.qualidade
    assert qualidade is not None, "folha da qualidade montada"
    assert (qualidade.open_at_cut, qualidade.critical_at_cut) == (4, 0), "RNC em aberto no corte"
    assert qualidade.overdue_at_reference == 1, "RNC vencida na data de referencia"
    assert (qualidade.opened_period, qualidade.closed_period) == (1, 0), "RNC do periodo"
    assert (qualidade.approval_pct, qualidade.approval_meta) == (D("66.7"), D("95")), (
        "aprovacao em inspecoes do periodo contra a meta"
    )
    assert qualidade.inspections == 3 and len(qualidade.rejected) == 1, "inspecoes do periodo"
    assert qualidade.rejected[0].rnc_code == "RNC-TN-2026-0005", "reprovacao ligada a RNC"
    assert (qualidade.conformity_pct, qualidade.conformity_meta) == (D("82.9"), D("90")), (
        "conformidade em auditorias do periodo"
    )
    assert (qualidade.audits_period, qualidade.late_audits) == (1, 1), "auditorias do periodo"
    assert (qualidade.cost_accumulated_cents, qualidade.cost_period_cents) == (5670000, 0), (
        "custo da nao qualidade acumulado e do periodo"
    )
    assert [(linha.name, linha.total) for linha in qualidade.discipline] == [
        ("Mecânica", 3),
        ("Civil", 2),
        ("Tubulação", 1),
    ], "disciplinas do Pareto de RNC"
    assert [entrada.code for entrada in qualidade.agenda] == ["RNC-TN-2026-0004"], (
        "pauta de tratamento na data de referencia"
    )
    assert qualidade.agenda[0].reasons == ("prazo de tratamento vencido há 8 dias",), (
        "motivo da pauta"
    )


def _afirmar_hse(visao: service.ReportSheets) -> None:
    """A folha HSE no mes do corte: as taxas, a piramide, os dias e os proativos."""
    hse = visao.hse
    assert hse is not None and hse.empty is False, "folha HSE montada"
    mes = hse.month_indicators
    assert (mes.hours, mes.tf, mes.trif, mes.tg) == (
        D("147150.00"),
        D("0.00"),
        D("6.80"),
        D("0.0"),
    ), "HHT e taxas do mes (setembro parcial)"
    assert (mes.registrable, mes.lti, mes.hipo) == (1, 0, 1), "lesoes registraveis, LTI e HiPo"
    assert mes.pyramid == (0, 2, 5, 32, 189), "piramide do mes"
    acumulado = hse.accumulated
    assert (acumulado.hours, acumulado.trif) == (D("788070.00"), D("8.88")), "HHT e TRIF acumuladas"
    assert acumulado.pyramid == (0, 16, 31, 190, 1240), "piramide acumulada"
    assert (acumulado.days_without_leave, hse.days_expected) == (258, 258), (
        "dias sem afastamento no corte"
    )
    assert (hse.occurrences, hse.occurrence_levels) == (10, (0, 0, 2, 8)), "ocorrencias da semana"
    assert (hse.month_occurrences, hse.hours_expected) == (39, 147200), (
        "ocorrencias do mes e HHT previsto do histograma"
    )
    assert (
        acumulado.dds_pct,
        acumulado.conformity_pct,
        acumulado.observations_per_10k,
        acumulado.almost_miss_report,
        acumulado.recommendations_pct,
    ) == (D("94.1"), D("87.0"), D("41.0"), D("27.1"), D("52.9")), "indicadores proativos"
    assert hse.analysis.record is not None, "analise do HSE registrada"


def _afirmar_a_carteira(context: OracleContext) -> None:
    """A folha Carteira do Portfólio na data de referência: a mesma leitura da tela Início."""
    admin = next(
        acesso
        for acesso in configuracoes.list_active_access(context.session)
        if acesso.general_profile == GeneralProfile.ADMIN
    )
    visao = service.report_view(
        context.session,
        user=_user_of(admin),
        scope=Scope(project_id=None, source="url"),
        kind=calendario.WEEKLY,
        period="2026-S38",
        sections=("riscos", "qualidade", "hse"),
        reference_date=context.reference_date,
    )

    carteira = visao.carteira
    assert carteira is not None, "a carteira entra sozinha no Portfolio"
    assert carteira.project_count == 3, "projetos da carteira"
    assert carteira.budget_cents == 7020000000, "BAC da carteira"
    assert carteira.budget_baseline_cents == 7020000000, "linha de base da carteira"
    assert (carteira.predicted, carteira.actual, carteira.deviation_pp) == (
        D("52.0"),
        D("48.9"),
        D("-3.1"),
    ), "avanco ponderado"
    assert (carteira.spi, carteira.cpi) == (D("0.94"), D("0.97")), "indices da carteira"
    assert (carteira.projection_cents, carteira.vac_cents) == (7116500000, -96500000), (
        "projecao no termino e VAC"
    )
    assert (carteira.baseline_finish, carteira.trend_finish) == (
        date(2027, 6, 1),
        date(2027, 7, 1),
    ), "termino da linha de base e pela tendencia"
    assert (carteira.critical_risks, carteira.critical_orders, carteira.overdue_actions) == (
        4,
        4,
        14,
    ), "riscos, pedidos e acoes"
    assert [(linha.code, linha.weight, linha.health) for linha in carteira.projects] == [
        ("TN-2026-014", D("55.36"), "warn"),
        ("TN-2026-021", D("29.34"), "erro"),
        ("TN-2026-027", D("15.3"), "warn"),
    ], "pesos e situacao por projeto"
    assert carteira.projects[0].trend_finish == date(2027, 4, 1), "tendencia pelo projeto"
    assert [(item.name, item.weight, item.source) for item in carteira.criteria] == [
        ("Valor financeiro (orçamento vigente)", D("60"), "orcamento"),
        ("Criticidade estratégica", D("25"), "nota"),
        ("Complexidade e exposição a risco", D("15"), "nota"),
    ], "criterios da ponderacao"
    assert carteira.curve_chart["periodos"], "Curva S fisica ponderada"
    riscos = visao.riscos
    assert riscos is not None
    assert (riscos.active, riscos.registered) == (16, 19), "riscos consolidados da carteira"
    assert (riscos.top.total, riscos.second.total) == (4, 2), "faixas consolidadas"  # type: ignore[union-attr]
    assert (riscos.exposure_cents, riscos.agenda) == (487000000, 5), "exposicao e pauta"
    assert [risco.number for risco in riscos.principais] == [
        "RSK-CB-2026-0001",
        "RSK-TN-2026-0004",
        "RSK-CB-2026-0004",
        "RSK-TN-2026-0003",
        "RSK-TN-2026-0001",
    ], "no Portfolio o codigo completo"
    qualidade = visao.qualidade
    assert qualidade is not None
    assert (qualidade.open_at_cut, qualidade.critical_at_cut) == (7, 1), "RNC consolidadas"
    assert (qualidade.cost_accumulated_cents, qualidade.discipline_total) == (6920000, 10), (
        "custo e disciplinas"
    )
    assert [entrada.code for entrada in qualidade.agenda] == [
        "RNC-TN-2026-0004",
        "RNC-CB-2026-0002",
    ], "pauta consolidada"
    hse = visao.hse
    assert hse is not None
    assert (hse.month_indicators.hours, hse.month_indicators.trif) == (
        D("204266.00"),
        D("9.79"),
    ), "HHT e TRIF do mes consolidados"
    assert hse.accumulated.pyramid == (0, 22, 39, 236, 1450), "piramide acumulada da carteira"
    assert (hse.occurrences, hse.month_occurrences, hse.hours_expected) == (15, 55, 204300), (
        "ocorrencias e HHT previsto da carteira"
    )


def test_oraculo_do_relatorio_gerencial(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    _afirmar_as_folhas(context)


def test_oraculo_da_carteira_do_portfolio(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    _afirmar_a_carteira(context)
