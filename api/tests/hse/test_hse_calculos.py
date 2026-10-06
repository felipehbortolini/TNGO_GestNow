"""Cálculos puros do HSE (ISSUE-072, D6): resumo do HHT, fator do histograma e taxas proativas.

O fator do histograma é a razão entre o avanço planejado e o realizado da Curva S física, limitada
à faixa de 0,85 a 1,20; o HHT previsto sai do registrado ajustado por ele, arredondado às centenas.
As metas proativas vêm do HHT dos meses fechados. Nada aqui lê o relógio nem o banco.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.modulos.hse.calculations import (
    ClosingLine,
    CurvePoint,
    HoursLine,
    add_months,
    expected_months,
    histogram_factor,
    hours_per_person,
    is_future_month,
    labour_histogram,
    month_display,
    month_label,
    month_of,
    months_between,
    parse_month,
    planned_labour,
    proactive_target,
    rate_percent,
    summarize_hours,
    summarize_proactive,
)

HOURS = Decimal("13080")
AGOSTO = date(2026, 8, 1)
REFERENCIA = date(2026, 9, 25)

CURVE = (
    CurvePoint(month=date(2026, 7, 1), planned=40.0, actual=36.0),
    CurvePoint(month=AGOSTO, planned=50.0, actual=None),
    CurvePoint(month=date(2026, 9, 1), planned=60.0, actual=54.0),
)


# ── Meses ────────────────────────────────────────────────────────────────────────────────────


def test_mes_guarda_o_primeiro_dia_e_tem_rotulo_e_escrita() -> None:
    assert month_of(date(2026, 9, 25)) == date(2026, 9, 1)
    assert month_label(date(2026, 9, 1)) == "2026-09"
    assert month_display(date(2026, 9, 1)) == "Set/2026"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("2026-09", date(2026, 9, 1)),
        ("2026-01", date(2026, 1, 1)),
        ("2026-13", None),
        ("2026-00", None),
        ("2026-9", None),
        ("2026-09-01", None),
        ("", None),
        (None, None),
    ],
)
def test_leitura_do_mes(label: str | None, expected: date | None) -> None:
    assert parse_month(label) == expected


def test_somar_meses_atravessa_o_ano() -> None:
    assert add_months(date(2026, 12, 1), 1) == date(2027, 1, 1)
    assert add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)


def test_meses_entre_as_datas_inclusive() -> None:
    assert months_between(date(2026, 1, 20), date(2026, 3, 5)) == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
    ]
    assert months_between(date(2026, 3, 1), date(2026, 1, 1)) == []


def test_mes_futuro_nao_pode_ser_registrado() -> None:
    assert is_future_month(date(2026, 10, 1), REFERENCIA)
    assert not is_future_month(date(2026, 9, 30), REFERENCIA)


def test_meses_esperados_somam_as_janelas_sem_repetir() -> None:
    from src.modulos.hse.calculations import ExpectedWindow

    windows = (
        ExpectedWindow(start=date(2026, 1, 5), planned_end=date(2026, 8, 31)),
        ExpectedWindow(start=date(2026, 1, 5), planned_end=date(2027, 3, 31)),
        ExpectedWindow(start=None, planned_end=None),
    )

    # O projeto 1 termina em agosto, o 2 segue até a referência: janeiro a setembro, uma vez cada.
    assert expected_months(windows, REFERENCIA) == 9


# ── HHT ──────────────────────────────────────────────────────────────────────────────────────


def test_horas_por_pessoa_arredonda_o_meio_para_cima() -> None:
    assert hours_per_person(HOURS, 60) == 218
    assert hours_per_person(Decimal("10"), 4) == 3  # 2,5
    assert hours_per_person(Decimal("10"), 8) == 1  # 1,25
    assert hours_per_person(Decimal("10"), 0) == 0


def test_resumo_do_hht_soma_meses_empresas_e_pega_o_ultimo_efetivo() -> None:
    lines = [
        HoursLine(1, 1, date(2026, 7, 1), 40, Decimal("8000")),
        HoursLine(1, 2, date(2026, 7, 1), 20, Decimal("4000")),
        HoursLine(1, 1, AGOSTO, 60, HOURS),
    ]

    summary = summarize_hours(lines)

    assert summary.total_hours == Decimal("25080")
    assert summary.months_with_record == 2
    assert summary.last_month == AGOSTO
    assert summary.last_month_headcount == 60
    assert summary.companies_with_record == 2


def test_resumo_sem_registro_e_vazio() -> None:
    summary = summarize_hours([])

    assert summary.total_hours == 0
    assert summary.last_month is None
    assert summary.last_month_headcount == 0


# ── Histograma ───────────────────────────────────────────────────────────────────────────────


def test_fator_do_histograma_e_a_razao_entre_o_planejado_e_o_realizado() -> None:
    # Setembro: avanço planejado de 10 (50→60) sobre o realizado de 18 (36→54): 0,56 vira 0,85.
    assert histogram_factor(CURVE, date(2026, 9, 1)) == pytest.approx(0.85)


def mes_de(month: int) -> date:
    """Um mês qualquer de 2026, para as curvas dos testes."""
    return date(2026, month, 1)


def test_fator_do_histograma_tem_teto_de_um_virgula_dois() -> None:
    curve = (
        CurvePoint(month=mes_de(1), planned=40.0, actual=36.0),
        CurvePoint(month=mes_de(2), planned=50.0, actual=38.0),
    )

    assert histogram_factor(curve, mes_de(2)) == pytest.approx(1.2)


def test_fator_do_histograma_e_um_sem_curva_fora_do_mes_sem_realizado_ou_sem_avanco() -> None:
    assert histogram_factor((), AGOSTO) == 1.0
    assert histogram_factor(CURVE, date(2026, 6, 1)) == 1.0
    assert histogram_factor(CURVE, AGOSTO) == 1.0  # agosto ainda sem realizado
    sem_avanco = (
        CurvePoint(month=mes_de(1), planned=40.0, actual=36.0),
        CurvePoint(month=mes_de(2), planned=40.0, actual=36.0),
    )
    assert histogram_factor(sem_avanco, mes_de(2)) == 1.0


def test_histograma_soma_as_empresas_do_mes_e_arredonda_as_centenas() -> None:
    lines = [
        HoursLine(1, 1, AGOSTO, 60, Decimal("13080")),
        HoursLine(1, 2, AGOSTO, 40, Decimal("8000")),
    ]

    points = labour_histogram(lines, {})

    (point,) = points
    assert point.project_id == 1
    assert point.month == AGOSTO
    # 21.080 horas viram 21.100 (centenas); 100 pessoas ajustadas pelo fator 1.
    assert (point.planned_hours, point.planned_headcount) == (21_100, 100)
    assert (point.recorded_hours, point.recorded_headcount) == (Decimal("21080"), 100)


def test_histograma_aplica_o_fator_da_curva_e_ordena_por_projeto_e_mes() -> None:
    lines = [
        HoursLine(2, 1, AGOSTO, 10, Decimal("1000")),
        HoursLine(1, 1, date(2026, 7, 1), 20, Decimal("2000")),
    ]
    curves = {1: (CurvePoint(month=date(2026, 7, 1), planned=20.0, actual=10.0),)}

    points = labour_histogram(lines, curves)

    assert [(point.project_id, point.month) for point in points] == [
        (1, date(2026, 7, 1)),
        (2, AGOSTO),
    ]
    # Julho do projeto 1: avanço planejado 20 sobre o realizado 10 (fator 2) vira o teto 1,20.
    assert points[0].planned_hours == 2400
    assert points[0].planned_headcount == 24
    assert points[1].planned_hours == 1000


def test_hht_previsto_acumulado_e_do_mes() -> None:
    points = labour_histogram(
        [
            HoursLine(1, 1, date(2026, 7, 1), 40, Decimal("8000")),
            HoursLine(1, 1, AGOSTO, 60, Decimal("12000")),
        ],
        {},
    )

    acumulado = planned_labour(points, up_to=AGOSTO)
    do_mes = planned_labour(points, up_to=AGOSTO, only_month=True)

    assert (acumulado.hours, acumulado.headcount) == (20_000, 100)
    assert (do_mes.hours, do_mes.headcount) == (12_000, 60)
    assert planned_labour(points, up_to=date(2026, 6, 1)) is None


# ── Segurança proativa ───────────────────────────────────────────────────────────────────────


def test_percentual_arredonda_a_uma_casa_e_sem_todo_e_nulo() -> None:
    assert rate_percent(40, 44) == Decimal("90.9")
    assert rate_percent(57, 60) == Decimal("95.0")
    assert rate_percent(0, 0) is None


def test_meta_proativa_aplica_a_base_de_dez_mil_horas() -> None:
    assert proactive_target(12, HOURS) == 16  # 12 x 13.080 / 10.000 = 15,696
    assert proactive_target(12, Decimal(0)) == 0


def test_resumo_proativo_usa_o_hht_dos_meses_fechados() -> None:
    closings = [
        ClosingLine(1, AGOSTO, 12, 30, 22, 20, 60, 57),
        ClosingLine(1, date(2026, 7, 1), 8, 20, 20, 20, 50, 50),
    ]
    hours = [
        HoursLine(1, 1, AGOSTO, 60, HOURS),
        HoursLine(1, 1, date(2026, 7, 1), 40, Decimal("10000")),
    ]

    summary = summarize_proactive(
        closings, hours, observations_per_ten_thousand=12, deviations_per_ten_thousand=8
    )

    assert summary.dds_rate == Decimal("95.2")  # 40 de 42
    assert summary.conformity_rate == Decimal("97.3")  # 107 de 110
    assert (summary.held_dds, summary.planned_dds) == (40, 42)
    assert (summary.conforming_items, summary.inspected_items) == (107, 110)
    assert (summary.observations, summary.deviations) == (50, 20)
    # (12 x 23.080) / 10.000 = 27,696 -> 28; (8 x 23.080) / 10.000 = 18,464 -> 18.
    assert (summary.observations_target, summary.deviations_target) == (28, 18)


def test_resumo_proativo_sem_hht_nao_tem_meta() -> None:
    summary = summarize_proactive(
        [ClosingLine(1, AGOSTO, 0, 0, 0, 0, 0, 0)],
        [],
        observations_per_ten_thousand=12,
        deviations_per_ten_thousand=8,
    )

    assert summary.observations_target is None
    assert summary.deviations_target is None
