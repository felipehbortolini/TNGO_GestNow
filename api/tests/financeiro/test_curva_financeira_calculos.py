"""Cálculos da Curva S financeira (ISSUE-042): planejado, série do ERP e tendência.

O planejado é o total da revisão da EAC distribuído pelo perfil do previsto (a linha de base
física do projeto); o comprometido e o realizado acumulam os fatos mensais do ERP até o corte;
a tendência parte do realizado do mês consultado e chega à EAC por desempenho, distribuindo o
custo restante pelo perfil do planejado, sem usar dado posterior ao mês. Os números do cenário
(planejado de 2026-01 e realizado de 2026-08) vêm do mock do protótipo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.financeiro.calculations import (
    ErpCostFact,
    ErpCurvePoint,
    curva_financeira_erp,
    curva_financeira_planejado,
    curva_financeira_trend,
)

D = Decimal

BAC = 4_460_000_000
PROFILE = (
    D("2.1"),
    D("5.4"),
    D("10.2"),
    D("16.8"),
    D("24.5"),
    D("33.0"),
    D("42.1"),
    D("54.0"),
    D("65.7"),
    D("75.8"),
    D("84.2"),
    D("90.6"),
    D("95.1"),
    D("98.4"),
    D("100"),
    D("100"),
)
MONTHS = (
    date(2026, 1, 1),
    date(2026, 2, 1),
    date(2026, 3, 1),
    date(2026, 4, 1),
    date(2026, 5, 1),
    date(2026, 6, 1),
    date(2026, 7, 1),
    date(2026, 8, 1),
    date(2026, 9, 1),
    date(2026, 10, 1),
    date(2026, 11, 1),
    date(2026, 12, 1),
    date(2027, 1, 1),
    date(2027, 2, 1),
    date(2027, 3, 1),
    date(2027, 4, 1),
)
COMMITTED_DELTAS = (
    448_000_000,
    920_000_000,
    0,
    652_000_000,
    480_000_000,
    800_000_000,
    400_000_000,
    260_000_000,
    153_000_000,
)
ACTUAL_DELTAS = (
    90_000_000,
    155_000_000,
    195_000_000,
    260_000_000,
    310_000_000,
    350_000_000,
    400_000_000,
    520_000_000,
    590_000_000,
)


def _facts() -> tuple[ErpCostFact, ...]:
    return tuple(
        ErpCostFact(
            item_id=1,
            month=date(2026, index + 1, 1),
            committed_cents=committed,
            actual_cents=actual,
        )
        for index, (committed, actual) in enumerate(
            zip(COMMITTED_DELTAS, ACTUAL_DELTAS, strict=True)
        )
    )


# ── Planejado ────────────────────────────────────────────────────────────


def test_planejado_do_cenario_reproduz_o_mock() -> None:
    planned = curva_financeira_planejado(PROFILE, BAC)

    assert len(planned) == len(PROFILE)
    assert planned[0] == 93_660_000
    assert planned[7] == 2_408_400_000
    assert planned[8] == 2_930_220_000
    assert planned[-1] == BAC


def test_planejado_arredonda_o_meio_centavo_para_cima() -> None:
    assert curva_financeira_planejado((D("0.5"),), 100) == (1,)


def test_planejado_sem_perfil_fica_vazio() -> None:
    assert curva_financeira_planejado((), BAC) == ()


# ── Série do ERP ─────────────────────────────────────────────────────────


def test_erp_acumula_os_movimentos_e_para_no_mes_do_corte() -> None:
    points = curva_financeira_erp(_facts(), MONTHS, cutoff=date(2026, 9, 25))
    by_month = {point.month: point for point in points}

    assert by_month[date(2026, 1, 1)].actual_cents == 90_000_000
    assert by_month[date(2026, 8, 1)].actual_cents == 2_280_000_000
    assert by_month[date(2026, 9, 1)].committed_cents == 4_113_000_000
    assert by_month[date(2026, 9, 1)].actual_cents == 2_870_000_000
    assert by_month[date(2026, 10, 1)] == ErpCurvePoint(
        month=date(2026, 10, 1), committed_cents=None, actual_cents=None
    )
    assert by_month[date(2027, 4, 1)].actual_cents is None


def test_erp_ignora_o_fato_posterior_ao_mes_do_corte() -> None:
    facts = (
        *_facts(),
        ErpCostFact(item_id=1, month=date(2026, 10, 1), committed_cents=9, actual_cents=9),
    )

    points = curva_financeira_erp(facts, MONTHS, cutoff=date(2026, 9, 25))
    by_month = {point.month: point for point in points}

    assert by_month[date(2026, 9, 1)].actual_cents == 2_870_000_000
    assert by_month[date(2026, 10, 1)].actual_cents is None


def test_erp_trata_valor_nulo_do_fato_como_zero() -> None:
    facts = (ErpCostFact(item_id=1, month=date(2026, 1, 1), committed_cents=None, actual_cents=50),)

    point = curva_financeira_erp(facts, (date(2026, 1, 1),), cutoff=date(2026, 1, 10))[0]

    assert point.committed_cents == 0
    assert point.actual_cents == 50


# ── Tendência ────────────────────────────────────────────────────────────


def test_tendencia_parte_do_realizado_e_chega_a_eac_pelo_perfil() -> None:
    trend = curva_financeira_trend(
        (100, 300, 600, 1000), (50, 150, None, None), 1, bac_cents=1000, ev_cents=120
    )

    assert trend == (None, 150, 621, 1250)


def test_tendencia_nao_usa_dado_posterior_ao_mes_consultado() -> None:
    planned = (100, 300, 600, 1000)

    depois_grande = curva_financeira_trend(
        planned, (50, 150, 999_999, 999_999), 1, bac_cents=1000, ev_cents=120
    )
    depois_pequeno = curva_financeira_trend(
        planned, (50, 150, 1, 2), 1, bac_cents=1000, ev_cents=120
    )

    assert depois_grande == depois_pequeno == (None, 150, 621, 1250)


def test_tendencia_sem_custo_restante_chega_a_eac_no_mes_seguinte() -> None:
    trend = curva_financeira_trend((100, 1000), (500, None), 0, bac_cents=1000, ev_cents=500)

    assert trend == (500, 1000)


def test_tendencia_limita_a_fracao_do_restante_a_um() -> None:
    trend = curva_financeira_trend(
        (100, 500, 1200), (500, None, None), 0, bac_cents=1000, ev_cents=500
    )

    assert trend == (500, 722, 1000)


def test_tendencia_sem_realizado_no_mes_ou_sem_cpi_nao_existe() -> None:
    planned = (100, 300)

    assert curva_financeira_trend(planned, (None, None), 0, bac_cents=1000, ev_cents=120) == (
        None,
        None,
    )
    assert curva_financeira_trend(planned, (0, None), 0, bac_cents=1000, ev_cents=120) == (
        None,
        None,
    )
    assert curva_financeira_trend(planned, (50, None), -1, bac_cents=1000, ev_cents=120) == (
        None,
        None,
    )
    assert curva_financeira_trend(planned, (50, None), 5, bac_cents=1000, ev_cents=120) == (
        None,
        None,
    )
