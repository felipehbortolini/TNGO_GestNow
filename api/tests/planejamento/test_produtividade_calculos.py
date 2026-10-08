"""Cálculos da Produtividade (ISSUE-046): perfis, maior resto, revisão e limites.

Tabela de casos e fronteiras, como manda o Padrão: a soma das semanas fecha com o total em
cada perfil, o saldo da revisão sai das semanas congeladas e o apontamento recusa o acumulado
acima da linha de base e as HH em falta.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.modulos.planejamento import calculations

D = Decimal


def _soma(values: tuple[Decimal, ...]) -> Decimal:
    return sum(values, D(0))


@pytest.mark.parametrize(
    "profile",
    [
        calculations.PROFILE_S_CURVE,
        calculations.PROFILE_LINEAR,
        calculations.PROFILE_START,
        calculations.PROFILE_END,
    ],
)
def test_a_distribuicao_fecha_o_total_em_cada_perfil(profile: str) -> None:
    values = calculations.distribute_total(D(100), 5, profile, places=0)

    assert len(values) == 5
    assert _soma(values) == D(100)
    assert all(value >= 0 for value in values)


def test_a_curva_s_concentra_no_pico_pelo_maior_resto() -> None:
    values = calculations.distribute_total(D(100), 5, calculations.PROFILE_S_CURVE, places=0)

    assert values == (D(14), D(24), D(24), D(24), D(14))
    assert _soma(values) == D(100)


def test_o_linear_reparte_por_igual() -> None:
    assert calculations.distribute_total(D(100), 5, calculations.PROFILE_LINEAR, 0) == (
        D(20),
        D(20),
        D(20),
        D(20),
        D(20),
    )


def test_o_inicio_concentra_nas_primeiras_semanas() -> None:
    values = calculations.distribute_total(D(100), 4, calculations.PROFILE_START, places=0)

    assert values[0] > values[-1]
    assert _soma(values) == D(100)


def test_a_casa_da_unidade_manda_no_maior_resto() -> None:
    values = calculations.distribute_total(D("10"), 4, calculations.PROFILE_LINEAR, places=1)

    assert values == (D("2.5"), D("2.5"), D("2.5"), D("2.5"))
    assert _soma(values) == D("10")


def test_a_revisao_congela_as_semanas_passadas_e_redistribui_o_saldo() -> None:
    frozen = (
        calculations.PlannedWeek(week="2026-S38", planned=D(30)),
        calculations.PlannedWeek(week="2026-S39", planned=D(20)),
    )

    free = calculations.revision_distribution(
        total=D(120),
        frozen=frozen,
        start_week="2026-S40",
        finish_week="2026-S41",
        profile=calculations.PROFILE_LINEAR,
        places=0,
    )

    assert free == (
        calculations.PlannedWeek(week="2026-S40", planned=D(35)),
        calculations.PlannedWeek(week="2026-S41", planned=D(35)),
    )
    assert _soma(tuple(line.planned for line in free)) + D(50) == D(120)


def test_o_saldo_nunca_e_negativo_quando_o_total_encolhe() -> None:
    frozen = (calculations.PlannedWeek(week="2026-S38", planned=D(90)),)

    free = calculations.revision_distribution(
        total=D(80),
        frozen=frozen,
        start_week="2026-S39",
        finish_week="2026-S39",
        profile=calculations.PROFILE_LINEAR,
        places=0,
    )

    assert free == (calculations.PlannedWeek(week="2026-S39", planned=D(0)),)


def test_o_fim_da_revisao_e_depois_da_semana_corrente() -> None:
    assert calculations.first_free_week("2026-S30", "2026-S39") == "2026-S40"
    assert calculations.first_free_week("2026-S45", "2026-S39") == "2026-S45"


def test_o_apontamento_recusa_o_acumulado_acima_da_lb() -> None:
    assert calculations.entry_over_limit(D(90), D(20), D(100), places=0)
    assert not calculations.entry_over_limit(D(90), D(10), D(100), places=0)


def test_a_tolerancia_respeita_a_casa_da_unidade() -> None:
    assert calculations.item_tolerance(0) == D("0.5")
    assert calculations.item_tolerance(1) == D("0.05")


def test_o_codigo_do_item_e_sequencial_e_herda_o_prefixo() -> None:
    assert calculations.next_item_code([]) == "QTD-01"
    assert calculations.next_item_code(["QTD-01", "QTD-02"]) == "QTD-03"
    assert calculations.next_item_code(["CB-QTD-09"]) == "CB-QTD-10"


def test_o_indicador_de_faixa_respeita_o_sentido_bom() -> None:
    bands = (D(75), D(90))

    assert calculations.indicator_band(D(95), bands, higher_is_better=True) == "success"
    assert calculations.indicator_band(D(80), bands, higher_is_better=True) == "warning"
    assert calculations.indicator_band(D(70), bands, higher_is_better=True) == "danger"
    assert calculations.indicator_band(D("0.9"), (D(1), D("1.1")), higher_is_better=False) == (
        "success"
    )
    assert calculations.indicator_band(None, bands, higher_is_better=True) is None


def _figures(*, cut_week: str = "2026-S34", situation: str = calculations.ITEM_APPROVED):
    planned = tuple(
        calculations.PlannedWeek(week=week, planned=D(10))
        for week in calculations.list_weeks("2026-S30", "2026-S40")
    )
    reported = tuple(
        calculations.ReportedWeek(week=week, realized=D(10), hh=D(125))
        for week in calculations.list_weeks("2026-S30", "2026-S33")
    )
    return calculations.item_figures(
        start_week="2026-S30",
        finish_week="2026-S40",
        total=D(110),
        index_hh=D(10),
        places=0,
        situation=situation,
        planned=planned,
        reported=reported,
        cut_week=cut_week,
        current_week=cut_week,
        window_weeks=4,
    )


def test_o_item_calcula_aderencia_fp_e_tendencia() -> None:
    figures = _figures()

    assert (figures.prev_acum, figures.real_acum) == (D(50), D(40))
    assert (figures.pct_prev, figures.pct_real) == (D("45.5"), D("36.4"))
    assert figures.deviation_pp == D("-9.1")
    assert figures.pf == D("1.25")
    assert figures.balance == D(70)
    assert figures.trend_week == "2026-S43"
    assert figures.deviation_weeks == 3
    assert figures.pending


def test_o_item_em_elaboracao_fica_fora_dos_indicadores() -> None:
    figures = _figures(situation=calculations.ITEM_DRAFT)

    assert not figures.approved
    assert not figures.active
    assert not figures.pending
    assert figures.trend_week is None


def test_a_serie_semanal_marca_o_futuro_como_nulo() -> None:
    item = calculations.SeriesItem(
        total=D(100),
        index_hh=D(1),
        planned=(
            calculations.PlannedWeek(week="2026-S38", planned=D(40)),
            calculations.PlannedWeek(week="2026-S39", planned=D(40)),
            calculations.PlannedWeek(week="2026-S40", planned=D(20)),
        ),
        reported=(calculations.ReportedWeek(week="2026-S38", realized=D(30), hh=D(30)),),
    )

    series = calculations.quantities_series(
        (item,), current_week="2026-S39", in_hours=False, unit="m"
    )

    assert series.weeks == ("2026-S38", "2026-S39", "2026-S40")
    assert series.realized == (D(30), None, None)
    assert series.realized_pct == (D(30), D(30), None)
    assert series.planned_pct == (D(40), D(80), D(100))


def test_a_serie_passa_para_horas_ganhas_quando_mistura_unidades() -> None:
    item = calculations.SeriesItem(
        total=D(10),
        index_hh=D(2),
        planned=(calculations.PlannedWeek(week="2026-S38", planned=D(10)),),
        reported=(),
    )

    series = calculations.quantities_series(
        (item,), current_week="2026-S38", in_hours=True, unit="HH"
    )

    assert series.planned == (D(20),)
    assert series.unit == "HH"


def test_a_figura_do_item_sem_contrato_nao_quebra() -> None:
    figures = calculations.item_figures(
        start_week="2026-S30",
        finish_week="2026-S40",
        total=D(0),
        index_hh=D(10),
        places=0,
        situation=calculations.ITEM_APPROVED,
        planned=(),
        reported=(),
        cut_week="2026-S34",
        current_week="2026-S34",
        window_weeks=4,
    )

    assert figures.pct_prev is None
    assert figures.pf is None
    assert figures.real_acum == D(0)
    assert calculations.frozen_planned((), "2026-S34") == ()
    assert calculations.week_start("nao-e-semana") is None
    assert calculations.places_for_unit("t") == 1
    assert calculations.places_for_unit("m") == 0
