"""Cálculos puros das reservas de contingência e gerencial (ISSUE-041, D5b).

O saldo como soma dos movimentos assinados, o consumo e o seu limite pelo avanço físico real
mais a tolerância do parâmetro, o saldo após a análise das SMs abertas, a composição da linha
de base de custo e do orçamento do projeto e o saldo real x previsto do gráfico, mês a mês até
o corte.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.financeiro.calculations import (
    MOVEMENT_CONSTITUTION,
    MOVEMENT_CONSUMPTION,
    MOVEMENT_RELEASE,
    ReserveMovementLine,
    reserve_after_analysis,
    reserve_balance,
    reserve_burn,
    reserve_composition,
    reserve_consumption_limit,
    reserve_consumption_pct,
)

D = Decimal


def _movement(kind: str, value_cents: int, on: date) -> ReserveMovementLine:
    return ReserveMovementLine(kind=kind, value_cents=value_cents, on=on)


# ── Saldo, consumo e limite ──────────────────────────────────────────────


def test_saldo_e_a_soma_dos_movimentos_assinados() -> None:
    movements = [
        _movement(MOVEMENT_CONSTITUTION, 20_000_000, date(2026, 1, 10)),
        _movement(MOVEMENT_CONSUMPTION, -3_000_000, date(2026, 2, 15)),
        _movement(MOVEMENT_RELEASE, -1_000_000, date(2026, 3, 31)),
    ]

    assert reserve_balance(movements) == 16_000_000


def test_sem_movimento_o_saldo_e_zero() -> None:
    assert reserve_balance([]) == 0


def test_consumo_percentual_tem_uma_casa() -> None:
    assert reserve_consumption_pct(3_000_000, 20_000_000) == D("15.0")
    assert reserve_consumption_pct(1, 3) == D("33.3")
    assert reserve_consumption_pct(2, 3) == D("66.7")


def test_consumo_percentual_sem_reserva_constituida_nao_existe() -> None:
    assert reserve_consumption_pct(1_000, 0) is None


def test_limite_de_consumo_e_o_avanco_real_mais_a_tolerancia() -> None:
    assert reserve_consumption_limit(D("61.8"), 10) == D("71.8")


def test_limite_de_consumo_nao_passa_de_100() -> None:
    assert reserve_consumption_limit(D("95.5"), 10) == D("100.0")
    assert reserve_consumption_limit(D("100.0"), 10) == D("100.0")


def test_limite_de_consumo_sem_avanco_real_nao_existe() -> None:
    assert reserve_consumption_limit(None, 10) is None


def test_saldo_apos_a_analise_desconta_o_pedido_em_sms_abertas() -> None:
    assert reserve_after_analysis(16_000_000, 4_000_000) == 12_000_000
    assert reserve_after_analysis(3_000_000, 5_000_000) == -2_000_000


# ── Composição do orçamento ──────────────────────────────────────────────


def test_composicao_soma_a_contingencia_a_linha_de_base_e_a_gerencial_ao_orcamento() -> None:
    composition = reserve_composition(44_600_000, 12_000_000, 5_000_000)

    assert composition.cost_baseline_cents == 56_600_000
    assert composition.project_budget_cents == 61_600_000


def test_composicao_sem_reservas_e_o_orcado_atual() -> None:
    composition = reserve_composition(44_600_000, 0, 0)

    assert composition.cost_baseline_cents == 44_600_000
    assert composition.project_budget_cents == 44_600_000


# ── Saldo real x previsto (burn) ─────────────────────────────────────────


def test_burn_previsto_desconta_o_avanco_planejado_e_o_real_desconta_os_movimentos() -> None:
    months = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]
    baseline = [D(0), D(25), D(50), D(75)]
    movements = [
        _movement(MOVEMENT_CONSTITUTION, 20_000_000, date(2026, 1, 10)),
        _movement(MOVEMENT_CONSUMPTION, -3_000_000, date(2026, 2, 15)),
        _movement(MOVEMENT_RELEASE, -1_000_000, date(2026, 3, 31)),
        _movement(MOVEMENT_CONSUMPTION, -5_000_000, date(2026, 4, 1)),
    ]

    burn = reserve_burn(months, baseline, 2, 20_000_000, movements)

    assert [(point.expected_cents, point.actual_cents) for point in burn] == [
        (20_000_000, 20_000_000),
        (15_000_000, 17_000_000),
        (10_000_000, 16_000_000),
        (5_000_000, None),
    ]
    assert [point.month for point in burn] == months


def test_burn_conta_o_movimento_no_ultimo_dia_do_mes_e_ignora_o_do_dia_seguinte() -> None:
    months = [date(2026, 3, 1), date(2026, 4, 1)]
    movements = [
        _movement(MOVEMENT_CONSTITUTION, 10_000_000, date(2026, 3, 1)),
        _movement(MOVEMENT_RELEASE, -1_000_000, date(2026, 3, 31)),
        _movement(MOVEMENT_CONSUMPTION, -5_000_000, date(2026, 4, 1)),
    ]

    burn = reserve_burn(months, [D(0), D(50)], 1, 10_000_000, movements)

    assert burn[0].actual_cents == 9_000_000
    assert burn[1].actual_cents == 4_000_000


def test_burn_previsto_arredonda_o_meio_centavo_para_cima() -> None:
    burn = reserve_burn([date(2026, 1, 1)], [D("33.35")], 0, 100, [])

    assert burn[0].expected_cents == 67


def test_burn_sem_baseline_no_mes_usa_zero() -> None:
    burn = reserve_burn([date(2026, 1, 1), date(2026, 2, 1)], [D(50)], 1, 10_000_000, [])

    assert burn[1].expected_cents == 10_000_000
