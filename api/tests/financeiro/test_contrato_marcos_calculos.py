"""Cálculos puros dos marcos, claims e EOT (ISSUE-033).

Os números são os do contrato 1 da carga de demonstração, conferidos à mão: o valor atual é
R$ 3.450.000,00 e o marco M1 de 10% vale R$ 345.000,00; o claim notificado 14 dias depois do
evento está dentro do prazo de 30 dias; o término vigente de 30/11/2026 prorrogado em 21 dias
vira 21/12/2026.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.modulos.financeiro import calculations

CONTRACT_CURRENT_VALUE_CENTS = 345_000_000
MILESTONE_PCTS = (10, 20, 25, 29, 12, 4)


# ── Valor e retenção do marco ────────────────────────────────────────────


def test_valor_do_marco_e_o_percentual_sobre_o_valor_atual() -> None:
    assert calculations.milestone_value_cents(CONTRACT_CURRENT_VALUE_CENTS, 10) == 34_500_000


@pytest.mark.parametrize(
    ("current_cents", "pct", "expected"),
    [
        (345_000_000, 4, 13_800_000),
        (130_000_000, 35, 45_500_000),
        (255_000_000, 10, 25_500_000),
        (0, 10, 0),
    ],
)
def test_valor_do_marco_bate_com_os_marcos_da_carga(
    current_cents: int, pct: int, expected: int
) -> None:
    assert calculations.milestone_value_cents(current_cents, pct) == expected


@pytest.mark.parametrize(
    ("current_cents", "pct", "expected"),
    [(349, 1, 3), (350, 1, 4), (333, 5, 17), (350, 5, 18)],
)
def test_valor_do_marco_arredonda_meio_centavo_para_cima(
    current_cents: int, pct: int, expected: int
) -> None:
    assert calculations.milestone_value_cents(current_cents, pct) == expected


def test_retencao_do_marco_e_o_valor_pela_retencao_do_contrato() -> None:
    assert calculations.milestone_retention_cents(34_500_000, 5) == 1_725_000


@pytest.mark.parametrize(
    ("value_cents", "retention_pct", "expected"),
    [(349, 1, 3), (350, 1, 4), (0, 5, 0), (100, 100, 100)],
)
def test_retencao_do_marco_arredonda_meio_centavo_para_cima(
    value_cents: int, retention_pct: int, expected: int
) -> None:
    assert calculations.milestone_retention_cents(value_cents, retention_pct) == expected


def test_retencao_do_marco_da_carga_bate_com_a_do_contrato_1() -> None:
    value = calculations.milestone_value_cents(CONTRACT_CURRENT_VALUE_CENTS, 10)
    retention = calculations.milestone_retention_cents(value, 5)

    assert value - retention == 32_775_000


# ── Soma dos percentuais ─────────────────────────────────────────────────


def test_soma_dos_percentuais_dos_marcos_do_contrato_1_fecha_100() -> None:
    assert calculations.milestone_pct_total(MILESTONE_PCTS) == 100
    assert calculations.milestone_pct_complete(MILESTONE_PCTS)


@pytest.mark.parametrize("pcts", [(10, 20), (99,), (101,), (50, 51), ()])
def test_soma_dos_percentuais_diferente_de_100_nao_fecha(pcts: tuple[int, ...]) -> None:
    assert not calculations.milestone_pct_complete(pcts)


# ── Prazo de notificação do claim ────────────────────────────────────────


def test_prazo_de_notificacao_e_o_evento_mais_os_dias_do_contrato() -> None:
    assert calculations.claim_notification_deadline(date(2026, 7, 8), 30) == date(2026, 8, 7)


def test_notificar_no_ultimo_dia_do_prazo_nao_e_atraso() -> None:
    deadline = calculations.claim_notification_deadline(date(2026, 7, 8), 30)

    assert not calculations.claim_notification_late(deadline, deadline)


def test_notificar_um_dia_antes_do_ultimo_dia_nao_e_atraso() -> None:
    deadline = calculations.claim_notification_deadline(date(2026, 7, 8), 30)

    assert not calculations.claim_notification_late(date(2026, 8, 6), deadline)


def test_notificar_no_primeiro_dia_de_atraso_e_fora_do_prazo() -> None:
    deadline = calculations.claim_notification_deadline(date(2026, 7, 8), 30)

    assert calculations.claim_notification_late(date(2026, 8, 8), deadline)


def test_claim_da_carga_notificado_no_prazo() -> None:
    deadline = calculations.claim_notification_deadline(date(2026, 7, 8), 30)

    assert not calculations.claim_notification_late(date(2026, 7, 22), deadline)


def test_claim_da_carga_notificado_fora_do_prazo() -> None:
    deadline = calculations.claim_notification_deadline(date(2026, 6, 10), 30)

    assert calculations.claim_notification_late(date(2026, 8, 5), deadline)


# ── Nova data de término da EOT ──────────────────────────────────────────


def test_concessao_prorroga_o_termino_vigente() -> None:
    assert calculations.extension_new_end_date(date(2026, 11, 30), 21) == date(2026, 12, 21)


def test_concessao_atravessa_o_fim_do_mes() -> None:
    assert calculations.extension_new_end_date(date(2026, 1, 31), 1) == date(2026, 2, 1)


def test_concessao_de_zero_dias_mantem_a_data() -> None:
    assert calculations.extension_new_end_date(date(2026, 11, 30), 0) == date(2026, 11, 30)
