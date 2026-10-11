"""Cálculos puros da Análise do período (ISSUE-081/ISSUE-082): detecção, textos, resumo e competência.

Um caso por chave dos módulos 02, 03, 04 e 06, os limites que não são desvio, os textos
numéricos no formato do protótipo e o mês de competência do custo. Riscos e HSE não têm
detecção — neles só o texto é exigido —, mas o resumo dos cinco módulos é afirmado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.relatorio import calculations

D = Decimal

AVANCO = calculations.Deviation(
    key="avanco",
    indicator="Avanço físico acumulado",
    data={"real": D("61.8"), "previsto": D("65.7"), "desvio": D("-3.9"), "spi": D("0.94")},
)


def _planning(**mudancas: object) -> calculations.PlanningFigures:
    base: dict[str, object] = {
        "predicted": D("65.7"),
        "actual": D("61.8"),
        "deviation_pp": D("-3.9"),
        "spi": D("0.94"),
        "previous_predicted": D("54.0"),
        "previous_actual": D("50.3"),
        "previous_spi": D("0.93"),
        "trend_finish": date(2027, 4, 1),
        "baseline_finish": date(2027, 3, 1),
        "areas": (
            calculations.AreaFigure(name="Suprimentos", deviation_pp=D("-6.0")),
            calculations.AreaFigure(name="Obras civis", deviation_pp=D("0.5")),
        ),
        "productivity": calculations.ProductivityFigure(
            spi=D("0.88"),
            pf_window=D("1.12"),
            adherence=D("83.9"),
            working_pct=D("55.0"),
            utilization=D("70.0"),
            meta_pf=D("1"),
            meta_adherence=D("90"),
            meta_working=D("60"),
            meta_utilization=D("75"),
            weeks=4,
        ),
    }
    base.update(mudancas)
    return calculations.PlanningFigures(**base)  # type: ignore[arg-type]


def _cost(**mudancas: object) -> calculations.CostFigures:
    base: dict[str, object] = {
        "closed": True,
        "cpi": D("0.92"),
        "spi": D("0.94"),
        "cv_cents": -123456789,
        "sv_cents": -36600000,
        "ev_cents": 2243000000,
        "ac_cents": 2280000000,
        "previous_cpi": D("0.98"),
        "budget_cents": 4460000000,
        "projection_cents": 4526000000,
        "vac_cents": -66000000,
        "deviation_percent": D("-1.5"),
        "contingency_pct": D("20.0"),
        "packages": (
            calculations.CostPackageFigure(
                code="1.1",
                description="Engenharia",
                deviation_cents=25500000,
                deviation_percent=D("12.3"),
            ),
        ),
    }
    base.update(mudancas)
    return calculations.CostFigures(**base)  # type: ignore[arg-type]


def _procurement(**mudancas: object) -> calculations.ProcurementFigures:
    base: dict[str, object] = {
        "adherence_pct": D("80.0"),
        "adjudicated": 8,
        "planned": 10,
        "saving_pct": D("3.4"),
        "otd_pct": D("90.0"),
        "on_time": 9,
        "deliveries": 10,
        "warning": 2,
        "critical_orders": (
            calculations.CriticalOrderFigure(number="PD-0001", description="Moinho", slack_days=-5),
        ),
        "late_milestones": (
            calculations.LateMilestoneFigure(code="PD-0001", milestone="Entrega", days=3),
        ),
    }
    base.update(mudancas)
    return calculations.ProcurementFigures(**base)  # type: ignore[arg-type]


def _risk(**mudancas: object) -> calculations.RiskFigures:
    base: dict[str, object] = {
        "active": 7,
        "top_band": "Crítico",
        "top_total": 2,
        "exposure_cents": 340000000,
        "overdue_reviews": 1,
        "identified": 1,
        "closed": 0,
        "reduction_avg_pct": 33,
    }
    base.update(mudancas)
    return calculations.RiskFigures(**base)  # type: ignore[arg-type]


def _quality(**mudancas: object) -> calculations.QualityFigures:
    base: dict[str, object] = {
        "open_in_period": 1,
        "closed_in_period": 0,
        "open_at_cut": 4,
        "approval_pct": D("66.7"),
        "approval_meta": D("95"),
        "approval_rejected": 1,
        "approval_total": 3,
        "conformity_pct": D("82.9"),
        "conformity_meta": D("90"),
        "non_quality_cost_cents": 5670000,
        "overdue": (calculations.OverdueItem(code="RNC-TN-2026-0004", days=3),),
        "late_audits": (calculations.OverdueItem(code="AUD-TN-2026-05", days=5),),
    }
    base.update(mudancas)
    return calculations.QualityFigures(**base)  # type: ignore[arg-type]


def _hse(**mudancas: object) -> calculations.HseFigures:
    base: dict[str, object] = {
        "tf": D("0.00"),
        "trif": D("6.80"),
        "accumulated_trif": D("8.88"),
        "days_without_leave": 258,
        "hipo": 1,
        "hours": D("147150"),
        "occurrences": 10,
    }
    base.update(mudancas)
    return calculations.HseFigures(**base)  # type: ignore[arg-type]


# ── Detecção: planejamento ─────────────────────────────────────────────────


def test_planejamento_detecta_as_cinco_chaves() -> None:
    keys = [deviation.key for deviation in calculations.planning_deviations(_planning())]

    assert keys == ["avanco", "avanco_periodo", "termino", "areas", "produtividade"]


def test_planejamento_no_limite_nao_e_desvio() -> None:
    figures = _planning(
        deviation_pp=D("0"),
        previous_predicted=D("65.7"),
        previous_actual=D("61.8"),
        trend_finish=date(2027, 3, 1),
        areas=(calculations.AreaFigure(name="Obras civis", deviation_pp=D("0")),),
        productivity=calculations.ProductivityFigure(
            spi=D("1"),
            pf_window=D("1"),
            adherence=D("90"),
            working_pct=D("60"),
            utilization=D("75"),
            meta_pf=D("1"),
            meta_adherence=D("90"),
            meta_working=D("60"),
            meta_utilization=D("75"),
            weeks=4,
        ),
    )

    assert calculations.planning_deviations(figures) == ()


def test_planejamento_sem_produtividade_nao_tem_a_chave() -> None:
    figures = _planning(productivity=None)

    keys = [deviation.key for deviation in calculations.planning_deviations(figures)]

    assert "produtividade" not in keys


# ── Detecção: financeiro ───────────────────────────────────────────────────


def test_financeiro_detecta_as_quatro_chaves() -> None:
    keys = [deviation.key for deviation in calculations.cost_deviations(_cost())]

    assert keys == ["cpi", "spi_custo", "vac", "pacotes"]


def test_financeiro_no_limite_nao_e_desvio() -> None:
    figures = _cost(
        cpi=D("1"),
        spi=D("1"),
        vac_cents=0,
        packages=(
            calculations.CostPackageFigure(
                code="1.1",
                description="Engenharia",
                deviation_cents=0,
                deviation_percent=D("0"),
            ),
        ),
    )

    assert calculations.cost_deviations(figures) == ()


def test_financeiro_sem_fechamento_nao_tem_desvio() -> None:
    figures = calculations.CostFigures(closed=False)

    assert calculations.cost_deviations(figures) == ()
    assert calculations.analysis_summary("financeiro", figures) == ()


# ── Detecção: suprimentos ──────────────────────────────────────────────────


def test_suprimentos_detecta_as_quatro_chaves() -> None:
    keys = [deviation.key for deviation in calculations.procurement_deviations(_procurement())]

    assert keys == ["aderencia", "otd", "criticos", "marcos_atrasados"]


def test_suprimentos_no_limite_nao_e_desvio() -> None:
    figures = _procurement(
        adherence_pct=D("100"),
        otd_pct=D("100"),
        critical_orders=(),
        late_milestones=(),
    )

    assert calculations.procurement_deviations(figures) == ()


# ── Detecção: qualidade (riscos e HSE não têm detecção) ────────────────────


def test_qualidade_detecta_as_quatro_chaves() -> None:
    keys = [deviation.key for deviation in calculations.quality_deviations(_quality())]

    assert keys == [
        "rnc_vencidas",
        "aprovacao_inspecao",
        "conformidade_auditoria",
        "auditorias_atrasadas",
    ]


def test_qualidade_no_limite_nao_e_desvio() -> None:
    figures = _quality(
        approval_pct=D("95"),
        conformity_pct=D("90"),
        overdue=(),
        late_audits=(),
    )

    assert calculations.quality_deviations(figures) == ()


def test_qualidade_sem_percentual_nao_e_desvio() -> None:
    figures = _quality(approval_pct=None, conformity_pct=None)

    keys = [deviation.key for deviation in calculations.quality_deviations(figures)]

    assert keys == ["rnc_vencidas", "auditorias_atrasadas"]


def test_qualidade_sem_vencidos_nao_tem_as_chaves_de_item() -> None:
    figures = _quality(
        overdue=(),
        late_audits=(),
        approval_pct=D("66.7"),
        conformity_pct=D("82.9"),
    )

    keys = [deviation.key for deviation in calculations.quality_deviations(figures)]

    assert keys == ["aprovacao_inspecao", "conformidade_auditoria"]


# ── Textos dos desvios ─────────────────────────────────────────────────────


def test_texto_do_avanco() -> None:
    assert (
        calculations.deviation_description(AVANCO)
        == "Real 61,8% x previsto 65,7% (-3,9 p.p.; SPI 0,94)"
    )


def test_texto_do_avanco_do_periodo() -> None:
    deviation = calculations.Deviation(
        key="avanco_periodo",
        indicator="Avanço no período",
        data={"real": D("1.2"), "previsto": D("2.0")},
    )

    assert (
        calculations.deviation_description(deviation)
        == "No período: real +1,2 p.p. x previsto +2,0 p.p. (-0,8 p.p.)"
    )


def test_texto_do_termino() -> None:
    deviation = calculations.Deviation(
        key="termino",
        indicator="Término pela tendência",
        data={"tendencia": date(2027, 9, 1), "baseline": date(2027, 8, 1)},
    )

    assert (
        calculations.deviation_description(deviation) == "Tendência set/27 x linha de base ago/27"
    )


def test_texto_das_areas() -> None:
    deviation = calculations.Deviation(
        key="areas",
        indicator="Avanço por área",
        data={
            "itens": (
                calculations.AreaFigure(name="Área A", deviation_pp=D("-1.2")),
                calculations.AreaFigure(name="Área B", deviation_pp=D("-0.5")),
            )
        },
    )

    assert calculations.deviation_description(deviation) == "Área A -1,2 p.p.; Área B -0,5 p.p."


def test_texto_da_produtividade() -> None:
    deviation = calculations.Deviation(
        key="produtividade",
        indicator="Produtividade",
        data={
            "itens": (
                calculations.ProductivityItem(key="spi", value=D("0.88"), target=D("1")),
                calculations.ProductivityItem(key="pf", value=D("1.12"), target=D("1")),
            ),
            "semanas": 4,
        },
    )

    assert calculations.deviation_description(deviation) == (
        "SPI de quantidades 0,88 (meta 1,00); Fator de produtividade 1,12 (meta ≤ 1,00) "
        "· últimas 4 semanas"
    )


def test_texto_do_cpi() -> None:
    deviation = calculations.Deviation(
        key="cpi",
        indicator="CPI (desempenho de custo)",
        data={"cpi": D("0.92"), "cv": -123456789, "ev": 2243000000, "ac": 2280000000},
    )

    assert calculations.deviation_description(deviation) == (
        "CPI 0,92 · CV -R$ 1.234.567,89 (EV R$ 22.430.000,00 x AC R$ 22.800.000,00)"
    )


def test_texto_do_spi_de_custo() -> None:
    deviation = calculations.Deviation(
        key="spi_custo",
        indicator="SPI de custo (valor agregado)",
        data={"spi": D("0.94"), "sv": -36600000},
    )

    assert calculations.deviation_description(deviation) == "SPI de custo 0,94 · SV -R$ 366.000,00"


def test_texto_do_vac() -> None:
    deviation = calculations.Deviation(
        key="vac",
        indicator="Projeção no término",
        data={
            "projecao": 4526000000,
            "bac": 4460000000,
            "vac": -66000000,
            "pct": D("-1.5"),
        },
    )

    assert calculations.deviation_description(deviation) == (
        "Projeção R$ 45.260.000,00 x orçamento R$ 44.600.000,00 (VAC -R$ 660.000,00; -1,5%)"
    )


def test_texto_dos_pacotes() -> None:
    deviation = calculations.Deviation(
        key="pacotes",
        indicator="Pacotes com sobrecusto projetado",
        data={
            "itens": (
                calculations.CostPackageFigure(
                    code="1.1",
                    description="Engenharia",
                    deviation_cents=25500000,
                    deviation_percent=D("12.3"),
                ),
                calculations.CostPackageFigure(
                    code="1.2",
                    description="Montagem",
                    deviation_cents=37000000,
                    deviation_percent=None,
                ),
            )
        },
    )

    assert calculations.deviation_description(deviation) == (
        "1.1 Engenharia +R$ 255.000,00 (12,3%); 1.2 Montagem +R$ 370.000,00"
    )


def test_texto_da_aderencia_e_do_otd() -> None:
    aderencia = calculations.Deviation(
        key="aderencia",
        indicator="Aderência ao plano de compras",
        data={"adjudicados": 8, "planejados": 10, "pct": D("80.0")},
    )
    otd = calculations.Deviation(
        key="otd",
        indicator="Entregas no prazo (OTD)",
        data={"noPrazo": 9, "total": 10, "pct": D("90.0")},
    )

    assert (
        calculations.deviation_description(aderencia)
        == "8 de 10 pacotes adjudicados até o corte (80,0%)"
    )
    assert calculations.deviation_description(otd) == "9 de 10 entregas no prazo (90,0%)"


def test_texto_dos_criticos_e_dos_marcos() -> None:
    criticos = calculations.Deviation(
        key="criticos",
        indicator="Pedidos críticos",
        data={
            "itens": (
                calculations.CriticalOrderFigure(
                    number="PD-0001", description="Moinho", slack_days=-5
                ),
            )
        },
    )
    marcos = calculations.Deviation(
        key="marcos_atrasados",
        indicator="Marcos realizados com atraso no período",
        data={
            "itens": (
                calculations.LateMilestoneFigure(code="PD-0001", milestone="Entrega", days=3),
            )
        },
    )

    assert calculations.deviation_description(criticos) == "PD-0001 Moinho (folga -5 d)"
    assert calculations.deviation_description(marcos) == "PD-0001 Entrega (+3 d)"


def test_texto_das_rnc_vencidas_e_das_auditorias_atrasadas() -> None:
    rncs = calculations.Deviation(
        key="rnc_vencidas",
        indicator="RNC com prazo de tratamento vencido",
        data={
            "itens": (
                calculations.OverdueItem(code="RNC-TN-2026-0004", days=3),
                calculations.OverdueItem(code="RNC-TN-2026-0007", days=12),
            )
        },
    )
    auditorias = calculations.Deviation(
        key="auditorias_atrasadas",
        indicator="Auditorias atrasadas",
        data={"itens": (calculations.OverdueItem(code="AUD-TN-2026-05", days=5),)},
    )

    assert calculations.deviation_description(rncs) == (
        "RNC-TN-2026-0004 (+3 d); RNC-TN-2026-0007 (+12 d)"
    )
    assert calculations.deviation_description(auditorias) == "AUD-TN-2026-05 (+5 d)"


def test_texto_da_aprovacao_em_inspecoes() -> None:
    uma = calculations.Deviation(
        key="aprovacao_inspecao",
        indicator="Aprovação em inspeções",
        data={"pct": D("66.7"), "meta": D("95"), "reprovadas": 1, "total": 3},
    )
    duas = calculations.Deviation(
        key="aprovacao_inspecao",
        indicator="Aprovação em inspeções",
        data={"pct": D("50.0"), "meta": D("95"), "reprovadas": 2, "total": 4},
    )

    assert calculations.deviation_description(uma) == "66,7% (meta 95%) · 1 reprovada em 3"
    assert calculations.deviation_description(duas) == "50,0% (meta 95%) · 2 reprovadas em 4"


def test_texto_da_conformidade_em_auditorias() -> None:
    deviation = calculations.Deviation(
        key="conformidade_auditoria",
        indicator="Conformidade em auditorias",
        data={"pct": D("82.9"), "meta": D("90")},
    )

    assert calculations.deviation_description(deviation) == "82,9% (meta 90%)"


def test_chave_desconhecida_nao_tem_texto() -> None:
    deviation = calculations.Deviation(key="outra", indicator="Outra", data={})

    assert calculations.deviation_description(deviation) == ""


# ── Resumo do período ──────────────────────────────────────────────────────


def test_resumo_do_planejamento_tem_os_onze_rotulos() -> None:
    items = calculations.analysis_summary("planejamento", _planning())

    assert [item.label for item in items] == [
        "Avanço previsto",
        "Avanço real",
        "SPI físico",
        "SPI físico do período anterior",
        "Avanço no período (real)",
        "Avanço no período (previsto)",
        "Término pela tendência",
        "Término da linha de base",
        "SPI de quantidades",
        "Fator de produtividade",
        "Aderência semanal",
    ]
    assert [item.kind for item in items][-3:] == ["indice", "indice", "pct"]


def test_resumo_do_financeiro_e_do_suprimentos() -> None:
    custo = calculations.analysis_summary("financeiro", _cost())
    suprimentos = calculations.analysis_summary("suprimentos", _procurement())

    assert [item.label for item in custo] == [
        "Orçamento vigente (BAC)",
        "Realizado acumulado",
        "Valor agregado (EV)",
        "CPI",
        "CPI do mês anterior",
        "SPI de custo",
        "Projeção no término",
        "Contingência consumida",
    ]
    assert [item.label for item in suprimentos] == [
        "Aderência ao plano de compras",
        "Saving",
        "Entregas no prazo (OTD)",
        "Pedidos críticos",
        "Pedidos em atenção",
        "Pacotes adjudicados",
    ]


def test_resumo_dos_riscos_da_qualidade_e_do_hse() -> None:
    riscos = calculations.analysis_summary("riscos", _risk())
    qualidade = calculations.analysis_summary("qualidade", _quality())
    hse = calculations.analysis_summary("hse", _hse())

    assert [item.label for item in riscos] == [
        "Riscos ativos",
        "Críticos",
        "Exposição (VME)",
        "Revisão vencida",
        "Identificados no período",
        "Redução média",
    ]
    assert [item.kind for item in riscos] == ["num", "num", "moeda", "num", "num", "pct"]
    assert [item.label for item in qualidade] == [
        "RNC abertas no período",
        "RNC encerradas no período",
        "RNC em aberto no corte",
        "Aprovação em inspeções",
        "Conformidade em auditorias",
        "Custo da não qualidade acumulado",
    ]
    assert [item.label for item in hse] == [
        "TF no mês",
        "TRIF no mês",
        "TRIF acumulada",
        "Dias sem afastamento",
        "HiPo no mês",
        "HHT no mês",
        "Ocorrências no período",
    ]
    assert [item.kind for item in hse] == [
        "num2",
        "num2",
        "num2",
        "num",
        "num",
        "num",
        "num",
    ]


def test_resumo_de_riscos_com_faixa_alta_plural() -> None:
    items = calculations.analysis_summary("riscos", _risk(top_band="Alto", top_total=3))

    assert items[1].label == "Altos"
    assert items[1].value == 3


# ── Mês de competência e términos ──────────────────────────────────────────


def test_competencia_do_mensal_e_o_proprio_mes() -> None:
    assert calculations.competence_month("Mensal", "2026-08") == date(2026, 8, 1)


def test_competencia_do_semanal_e_o_ultimo_mes_fechado() -> None:
    assert calculations.competence_month("Semanal", "2026-S38") == date(2026, 8, 1)


def test_competencia_de_semana_no_inicio_do_mes_e_o_mes_anterior() -> None:
    assert calculations.competence_month("Semanal", "2026-S36") == date(2026, 8, 1)


def test_competencia_na_borda_do_mes_cheio() -> None:
    assert calculations.competence_month("Semanal", "2027-S04") == date(2027, 1, 1)


def test_competencia_de_semana_que_termina_no_mes_seguinte() -> None:
    assert calculations.competence_month("Semanal", "2026-S40") == date(2026, 9, 1)


def test_termino_da_serie_que_chega_a_100() -> None:
    months = [date(2026, 9, 1), date(2026, 10, 1)]
    values = [D("90"), D("100")]

    assert calculations.finish_month(months, values) == date(2026, 10, 1)
    assert calculations.trend_finish(months, values) == date(2026, 10, 1)


def test_termino_da_tendencia_que_nao_chega_a_100_e_o_ultimo_mes() -> None:
    months = [date(2026, 9, 1), date(2026, 10, 1)]
    values = [D("61.8"), D("96.1")]

    assert calculations.finish_month(months, values) is None
    assert calculations.trend_finish(months, values) == date(2026, 10, 1)


def test_termino_sem_valor_nenhum() -> None:
    assert calculations.finish_month([], []) is None
    assert calculations.trend_finish([date(2026, 9, 1)], [None]) is None


# ── Formatadores ───────────────────────────────────────────────────────────


def test_formatadores() -> None:
    assert calculations.format_percent(D("61.85")) == "61,9%"
    assert calculations.format_percent(None) == "·"
    assert calculations.format_index(D("0.937")) == "0,94"
    assert calculations.format_pp(D("-3.9")) == "-3,9 p.p."
    assert calculations.format_month(date(2026, 9, 1)) == "set/26"
    assert calculations.format_money(123456) == "R$ 1.234,56"
    assert calculations.format_number(3) == "3"
    assert calculations.format_number(None) == "·"


def test_formatador_de_duas_casas() -> None:
    assert calculations.format_number2(D("6.8")) == "6,80"
    assert calculations.format_number2(D("8.884")) == "8,88"
    assert calculations.format_number2(None) == "·"


def test_periodo_anterior_e_nome() -> None:
    assert calculations.previous_period("Semanal", "2026-S38") == "2026-S37"
    assert calculations.previous_period("Mensal", "2026-01") == "2025-12"
    assert calculations.period_name("Mensal", "2026-08") == "Agosto de 2026"
    assert calculations.short_month("Semanal", "2026-S38") == "S38"


def test_erro_do_periodo() -> None:
    inicio = date(2026, 8, 1)
    referencia = date(2026, 9, 25)

    assert (
        calculations.period_error(
            "Semanal", "2026-S38", project_start=inicio, reference_date=referencia
        )
        is None
    )
    assert (
        calculations.period_error(
            "Semanal", "2026-S20", project_start=inicio, reference_date=referencia
        )
        == "O período é anterior ao início do projeto."
    )
    assert (
        calculations.period_error(
            "Semanal", "2026-S40", project_start=inicio, reference_date=referencia
        )
        == "O período ainda não começou; registre a partir do período corrente."
    )
    assert (
        calculations.period_error(
            "Semanal", "qualquer", project_start=inicio, reference_date=referencia
        )
        == "Escolha o tipo e o período."
    )
