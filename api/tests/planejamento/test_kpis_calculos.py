"""Cálculos dos KPIs de performance (ISSUE-048): SPI(t), tendência semanal, faixas e referência.

Fórmulas puras, com o corte injetado (D6): cada teste afirma o número que a pessoa lê, com a
fronteira que a regra promete.
"""

from __future__ import annotations

from decimal import Decimal

from src.modulos.planejamento import calculations as c

D = Decimal


def _plano(*horas: str) -> tuple[c.PlannedHours, ...]:
    weeks = ("2026-S36", "2026-S37", "2026-S38", "2026-S39")
    return tuple(
        c.PlannedHours(week=week, hours=D(horas[index])) for index, week in enumerate(weeks)
    )


def test_o_spi_t_agregado_interpola_a_semana_equivalente() -> None:
    trend = c.schedule_trend(_plano("10", "10", "10", "10"), D("25"), cut_week="2026-S39")

    assert trend.equivalent_weeks == D("2.5")
    assert trend.elapsed_weeks == 4
    assert trend.spi_t == D("0.63")
    assert trend.trend_week == "2026-S42"
    assert trend.slip_weeks == 3


def test_o_spi_t_sem_realizado_nao_existe() -> None:
    trend = c.schedule_trend(_plano("10", "10", "10", "10"), D(0), cut_week="2026-S39")

    assert trend.spi_t is None
    assert trend.slip_weeks is None


def test_o_realizado_no_fim_do_plano_devolve_o_plano_inteiro() -> None:
    trend = c.schedule_trend(_plano("10", "10", "10", "10"), D("50"), cut_week="2026-S39")

    assert trend.equivalent_weeks == D("4")
    assert trend.spi_t == D("1")
    assert trend.trend_week == "2026-S39"
    assert trend.slip_weeks == 0


def test_o_realizado_acima_do_plano_nao_passa_da_duracao() -> None:
    trend = c.schedule_trend(_plano("10", "10", "10", "10"), D("80"), cut_week="2026-S39")

    assert trend.equivalent_weeks == D("4")
    assert trend.spi_t == D("1")


def test_o_corte_antes_do_inicio_do_plano_nao_tem_indice() -> None:
    trend = c.schedule_trend(_plano("10", "10", "10", "10"), D("5"), cut_week="2026-S30")

    assert trend.spi_t is None


def test_a_tendencia_semanal_calcula_os_quatro_indicadores() -> None:
    entradas = {
        "2026-S38": c.TrendInput(
            appropriated=D("120"),
            earned=D("100"),
            planned=D("100"),
            capped=D("100"),
            working=10,
            transit=2,
            stopped=8,
            capacities=(D("7"), D("7.33")),
        )
    }

    linhas = c.weekly_trend(("2026-S38", "2026-S39"), entradas)

    assert [(linha.week, linha.pf) for linha in linhas] == [
        ("2026-S38", D("1.20")),
        ("2026-S39", None),
    ]
    primeira = linhas[0]
    assert primeira.adherence == D("100.0")
    assert primeira.working_pct == D("50.00")
    assert primeira.capacity == D("7.17")
    assert primeira.adherence_ratio == (D("100"), D("100"))
    assert primeira.working_ratio == (D("10"), D("20"))


def test_a_aderencia_do_item_limita_o_realizado_ao_previsto() -> None:
    figuras = c.item_figures(
        start_week="2026-S36",
        finish_week="2026-S39",
        total=D("100"),
        index_hh=D("10"),
        places=0,
        situation=c.ITEM_APPROVED,
        planned=(c.PlannedWeek(week="2026-S39", planned=D("10")),),
        reported=(c.ReportedWeek(week="2026-S39", realized=D("15"), hh=D("150")),),
        cut_week="2026-S39",
        current_week="2026-S39",
        window_weeks=4,
    )

    assert figuras.window_capped_hours == D("100")
    assert figuras.window_adherence == D("100.0")


def test_a_aderencia_da_janela_pondera_pelas_horas_orcadas() -> None:
    def figuras(realizado: str, previsto: str, indice: str) -> c.ItemFigures:
        return c.item_figures(
            start_week="2026-S39",
            finish_week="2026-S39",
            total=D("10"),
            index_hh=D(indice),
            places=0,
            situation=c.ITEM_APPROVED,
            planned=(c.PlannedWeek(week="2026-S39", planned=D(previsto)),),
            reported=(c.ReportedWeek(week="2026-S39", realized=D(realizado), hh=D("1")),),
            cut_week="2026-S39",
            current_week="2026-S39",
            window_weeks=4,
        )

    indicadores = c.quantities_indicators([figuras("5", "10", "10"), figuras("9", "10", "100")])

    assert indicadores.window_adherence == D("86.4")
    assert indicadores.window_adherence != D("70.0")


def test_o_percentual_das_hh_paradas_divide_pelas_disponiveis() -> None:
    assert c.stoppage_share(D("50"), D("1000")) == D("5.00")
    assert c.stoppage_share(D("50"), D(0)) is None


def test_as_faixas_dos_cinco_indicadores_geram_alerta_e_atencao() -> None:
    bands = c.PerformanceBands(
        adherence="danger", pf="warning", spi="success", working=None, utilization="danger"
    )

    assert c.performance_alerts(bands) == (("adherence", "utilization"), ("pf",))
    assert c.performance_alerts(c.PerformanceBands()) == ((), ())


def test_a_referencia_da_acao_leva_a_semana_e_a_empresa() -> None:
    assert c.performance_action_reference(1, "2026-S39") == "PRD-2026-S39-01"
    assert c.performance_action_reference(12, "2026-S38") == "PRD-2026-S38-12"

    assert c.performance_action_parts("PRD-2026-S39-01") == ("2026-S39", 1)
    assert c.performance_action_parts(" PRD-2026-S38-12 ") == ("2026-S38", 12)
    assert c.performance_action_parts("PRD-2026-S39") is None
    assert c.performance_action_parts("outra") is None


def test_o_grafico_da_taxa_manda_o_par_de_cada_semana_com_a_meta() -> None:
    chart = c.ratio_chart(
        "Aderência semanal por empresa",
        weeks=("2026-S38", "2026-S39"),
        series=(
            c.TrendSeries(label="Alfa", ratios=((D("80"), D("100")), None)),
            c.TrendSeries(label="Zeta", ratios=((D("90"), D("100")), (D("95"), D("100")))),
        ),
        target=D("90"),
        target_label="Meta",
    )

    assert [serie["id"] for serie in chart["series"]] == ["serie-1", "serie-2", "meta"]
    assert chart["series"][2]["papel"] == "linha-base"
    assert chart["modo"] == "periodo"
    assert chart["formato"] == "pct"
    assert chart["eixo_max"] == 100
    primeiro, segundo = chart["periodos"]
    assert (primeiro["ano"], primeiro["semana"]) == (2026, 38)
    assert primeiro["valores"]["serie-1"] == {"num": 80.0, "den": 100.0}
    assert primeiro["valores"]["meta"] == {"num": 90.0, "den": 100.0}
    assert segundo["valores"]["serie-1"] is None
    assert segundo["valores"]["serie-2"] == {"num": 95.0, "den": 100.0}
