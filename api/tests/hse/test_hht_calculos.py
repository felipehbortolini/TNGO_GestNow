"""Cálculos puros do HSE (ISSUE-072, D6): HHT, histograma de mão de obra e taxas do consolidado.

Cada fórmula tem o caso de fronteira: meio arredondado para cima, mês inválido, sem efetivo,
curva ausente, passo real zero e fator nos tetos de 0,85 e 1,20.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.hse import calculations as calc
from src.modulos.hse import validation


def test_parse_month_aceita_so_mes_real() -> None:
    assert calc.parse_month("2026-09") == date(2026, 9, 1)
    assert calc.parse_month("2026-13") is None
    assert calc.parse_month("2026-9") is None
    assert calc.parse_month(None) is None


def test_round_half_up_leva_meio_para_cima() -> None:
    assert calc.round_half_up(2.5) == 3
    assert calc.round_half_up(Decimal("2.5")) == 3
    assert calc.round_half_up(Decimal("2.49")) == 2


def test_hours_per_person_sem_efetivo_e_zero() -> None:
    assert calc.hours_per_person(Decimal(13080), 60) == 218
    assert calc.hours_per_person(Decimal(100), 0) == 0
    assert calc.hours_per_person(Decimal(5), 2) == 3


def test_months_between_inclui_extremos_e_vazio_se_invertido() -> None:
    assert len(calc.months_between(date(2026, 11, 15), date(2027, 2, 1))) == 4
    assert calc.months_between(date(2026, 5, 1), date(2026, 4, 30)) == []


def test_expected_months_conta_mes_compartilhado_uma_vez() -> None:
    windows = [
        calc.ExpectedWindow(date(2026, 1, 10), None),
        calc.ExpectedWindow(date(2026, 3, 1), date(2026, 6, 30)),
        calc.ExpectedWindow(None, None),
    ]
    assert calc.expected_months(windows, date(2026, 9, 25)) == 9
    assert calc.expected_months(windows[1:], date(2026, 9, 25)) == 4


def test_summarize_hours_resume_o_ultimo_mes() -> None:
    lines = [
        calc.HoursLine(1, 1, date(2026, 8, 1), 10, Decimal(100)),
        calc.HoursLine(1, 2, date(2026, 9, 1), 20, Decimal(200)),
        calc.HoursLine(1, 3, date(2026, 9, 1), 5, Decimal(50)),
    ]
    summary = calc.summarize_hours(lines)
    assert summary.total_hours == Decimal(350)
    assert summary.months_with_record == 2
    assert summary.last_month == date(2026, 9, 1)
    assert summary.last_month_headcount == 25
    assert summary.companies_with_record == 3
    assert calc.summarize_hours([]).last_month is None


def _curve(planned: list[float], actual: list[float | None]) -> list[calc.CurvePoint]:
    return [
        calc.CurvePoint(date(2026, 1 + index, 1), plan, real)
        for index, (plan, real) in enumerate(zip(planned, actual, strict=True))
    ]


def test_fator_do_histograma_dentro_da_faixa() -> None:
    curve = _curve([2.1, 5.4], [1.8, 4.9])
    assert round(calc.histogram_factor(curve, date(2026, 1, 1)), 3) == 1.167
    assert round(calc.histogram_factor(curve, date(2026, 2, 1)), 3) == 1.065


def test_fator_do_histograma_limites_e_sem_dado() -> None:
    assert calc.histogram_factor([], date(2026, 1, 1)) == 1.0
    curve = _curve([10.0, 20.0, 30.0], [1.0, 2.0, None])
    assert calc.histogram_factor(curve, date(2026, 1, 1)) == calc.FACTOR_CEILING
    assert calc.histogram_factor(curve, date(2026, 3, 1)) == 1.0
    assert calc.histogram_factor(curve, date(2030, 1, 1)) == 1.0
    low = _curve([1.0, 2.0], [10.0, 20.0])
    assert calc.histogram_factor(low, date(2026, 1, 1)) == calc.FACTOR_FLOOR
    stalled = _curve([1.0, 2.0], [5.0, 5.0])
    assert calc.histogram_factor(stalled, date(2026, 2, 1)) == 1.0


def test_histograma_soma_empresas_e_arredonda_horas_a_centenas() -> None:
    lines = [
        calc.HoursLine(1, 1, date(2026, 1, 1), 60, Decimal(12000)),
        calc.HoursLine(1, 2, date(2026, 1, 1), 35, Decimal(8710)),
    ]
    curve = {1: _curve([2.1, 5.4], [1.8, 4.9])}
    (point,) = calc.labour_histogram(lines, curve)
    assert point.planned_hours == 24200
    assert point.planned_headcount == 111
    assert point.recorded_hours == Decimal(20710)
    assert calc.labour_histogram(lines, {})[0].planned_hours == 20700


def test_taxa_percentual_uma_casa_e_none_sem_total() -> None:
    assert calc.rate_percent(1, 3) == Decimal("33.3")
    assert calc.rate_percent(1, 8) == Decimal("12.5")
    assert calc.rate_percent(0, 0) is None


def test_meta_proativa_por_10_mil_hht() -> None:
    assert calc.proactive_target(40, Decimal(788070)) == 3152
    assert calc.proactive_target(12, Decimal(0)) == 0
    assert calc.proactive_target(1, Decimal(5000)) == 1


def test_validacao_do_hht_por_campo() -> None:
    choices = validation.RegisterChoices(company_ids={1}, person_ids=set())
    ref = date(2026, 9, 25)
    ok = validation.HoursInput(1, date(2026, 9, 1), 1, 60, Decimal(13080))
    assert validation.hours_problems(ok, choices, reference_date=ref) == {}
    bad = validation.HoursInput(1, date(2026, 10, 1), 2, -1, Decimal(1000000))
    assert set(validation.hours_problems(bad, choices, reference_date=ref)) == {
        "mes",
        "empresa",
        "efetivo_medio",
        "hht",
    }


def test_validacao_do_consolidado_fronteiras() -> None:
    ref = date(2026, 9, 25)
    ok = validation.ClosingInput(1, date(2026, 9, 1), 0, 10, 4, 4, 20, 20)
    assert validation.closing_problems(ok, reference_date=ref) == {}
    bad = validation.ClosingInput(1, date(2026, 9, 1), 0, 10, 4, 5, 20, 21)
    assert set(validation.closing_problems(bad, reference_date=ref)) == {
        "dds_realizados",
        "itens_conformes",
    }
