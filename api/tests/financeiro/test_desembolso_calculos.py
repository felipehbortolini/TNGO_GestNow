"""Cálculos puros do cronograma de desembolso (ISSUE-043, HU-091): distribuição e histograma.

A distribuição do saldo a pagar de um item usa os marcos de pagamento futuros do contrato e, no
que sobrar, o perfil da projeção; a soma dos meses é sempre o saldo, em centavos inteiros, pelo
maior resto. O histograma converte as séries acumuladas (o previsto da linha de base e o
realizado dos fatos do ERP) na variação mensal que a tela desenha.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.financeiro import calculations

MESES = (date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1))


# ── Distribuição ─────────────────────────────────────────────────────────


def test_o_perfil_distribui_o_saldo_e_a_soma_fecha() -> None:
    assert calculations.distribute_balance(1000, MESES, (1, 2, 7)) == (100, 200, 700)


def test_o_maior_resto_fecha_os_centavos() -> None:
    assert calculations.distribute_balance(100, MESES, (1, 1, 1)) == (34, 33, 33)
    assert calculations.distribute_balance(10, MESES, (1, 1, 1)) == (4, 3, 3)


def test_o_marco_futuro_entra_e_o_resto_segue_o_perfil() -> None:
    marco = calculations.PaymentMilestone(month=MESES[0], value_cents=300)

    assert calculations.distribute_balance(1000, MESES, (1, 1), (marco,)) == (650, 350, 0)


def test_marco_maior_que_o_saldo_e_reduzido_proporcionalmente() -> None:
    marcos = (
        calculations.PaymentMilestone(month=MESES[0], value_cents=200),
        calculations.PaymentMilestone(month=MESES[1], value_cents=100),
    )

    assert calculations.distribute_balance(100, MESES, (0, 0, 0), marcos) == (67, 33, 0)


def test_marco_fora_dos_meses_ou_sem_valor_nao_entra() -> None:
    marcos = (
        calculations.PaymentMilestone(month=date(2026, 9, 1), value_cents=500),
        calculations.PaymentMilestone(month=MESES[0], value_cents=0),
    )

    assert calculations.distribute_balance(100, MESES, (0, 0, 1), marcos) == (0, 0, 100)


def test_sem_perfil_o_saldo_fecha_no_ultimo_mes() -> None:
    assert calculations.distribute_balance(100, MESES, (0, 0, 0)) == (0, 0, 100)


def test_item_sem_saldo_ou_sem_mes_futuro_nao_distribui() -> None:
    assert calculations.distribute_balance(0, MESES, (1, 1, 1)) == (0, 0, 0)
    assert calculations.distribute_balance(100, (), ()) == ()


# ── Histograma ───────────────────────────────────────────────────────────


def test_o_histograma_converte_o_acumulado_em_mensal() -> None:
    meses = (date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1))

    histograma = calculations.disbursement_histogram(
        meses, planned_cumulative=(100, 300, 600), actual_cumulative=(50, 150, None)
    )

    assert [(linha.planned_cents, linha.actual_cents) for linha in histograma] == [
        (100, 50),
        (200, 100),
        (300, None),
    ]


def test_o_histograma_fica_nulo_onde_o_acumulado_e_nulo() -> None:
    meses = (date(2026, 8, 1), date(2026, 9, 1))

    histograma = calculations.disbursement_histogram(
        meses, planned_cumulative=(100, 300), actual_cumulative=(None, None)
    )

    assert [linha.month for linha in histograma] == list(meses)
    assert [linha.planned_cents for linha in histograma] == [100, 200]
    assert [linha.actual_cents for linha in histograma] == [None, None]


def test_a_parte_sobre_o_total_tem_uma_casa() -> None:
    assert calculations.share_percent(287, 452) == Decimal("63.5")
    assert calculations.share_percent(1, 0) is None
