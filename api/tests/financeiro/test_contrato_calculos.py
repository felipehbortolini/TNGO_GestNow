"""Cálculos puros da ficha do contrato (ISSUE-032): cascata, medido, saldo e término vigente.

Os números são os do contrato 1 da carga de demonstração, conferidos à mão: valor original de
R$ 3.300.000,00, aditivo AD-01 de R$ 150.000,00 e 21 dias, término original em 30/10/2026 e
vigente em 20/11/2026; as medições BM-01 a BM-04 somam R$ 2.898.000,00 de medido aprovado.
"""

from __future__ import annotations

from datetime import date

from src.modulos.financeiro import calculations
from src.modulos.financeiro.calculations import ContractAddendumLine, ContractMeasurementLine

ORIGINAL_CENTS = 330_000_000
ADDENDUM = ContractAddendumLine(value_cents=15_000_000, days=21)
MEASUREMENTS = (
    ContractMeasurementLine(value_cents=34_500_000, situation=calculations.SITUATION_PAID),
    ContractMeasurementLine(value_cents=69_000_000, situation=calculations.SITUATION_PAID),
    ContractMeasurementLine(value_cents=86_250_000, situation=calculations.SITUATION_PAID),
    ContractMeasurementLine(value_cents=100_050_000, situation=calculations.SITUATION_INVOICED),
)


# ── Valor atual ──────────────────────────────────────────────────────────


def test_valor_atual_e_o_original_mais_os_aditivos() -> None:
    assert calculations.contract_current_value_cents(ORIGINAL_CENTS, (ADDENDUM,)) == 345_000_000


def test_sem_aditivo_o_valor_atual_e_o_original() -> None:
    assert calculations.contract_current_value_cents(ORIGINAL_CENTS, ()) == ORIGINAL_CENTS


def test_aditivo_de_supressao_reduz_o_valor_atual() -> None:
    suppression = ContractAddendumLine(value_cents=-15_000_000)

    assert calculations.contract_current_value_cents(100_000_000, (suppression,)) == 85_000_000


# ── Medido aprovado e saldo a faturar ────────────────────────────────────


def test_medido_aprova_somente_aprovada_faturada_e_paga() -> None:
    measurements = (
        ContractMeasurementLine(value_cents=10_000, situation=calculations.SITUATION_PAID),
        ContractMeasurementLine(value_cents=20_000, situation=calculations.SITUATION_INVOICED),
        ContractMeasurementLine(value_cents=30_000, situation=calculations.SITUATION_APPROVED),
        ContractMeasurementLine(value_cents=40_000, situation=calculations.SITUATION_UNDER_REVIEW),
        ContractMeasurementLine(value_cents=50_000, situation=calculations.SITUATION_RETURNED),
    )

    assert calculations.contract_measured_cents(measurements) == 60_000


def test_medido_do_contrato_da_carga_bate() -> None:
    assert calculations.contract_measured_cents(MEASUREMENTS) == 289_800_000


def test_saldo_a_faturar_e_o_valor_atual_menos_o_medido() -> None:
    current = calculations.contract_current_value_cents(ORIGINAL_CENTS, (ADDENDUM,))
    measured = calculations.contract_measured_cents(MEASUREMENTS)

    assert calculations.contract_balance_to_invoice_cents(current, measured) == 55_200_000


# ── Término vigente ──────────────────────────────────────────────────────


def test_aditivo_com_dias_prorroga_o_termino_vigente() -> None:
    assert calculations.contract_current_end_date(date(2026, 10, 30), (ADDENDUM,)) == date(
        2026, 11, 20
    )


def test_aditivo_de_supressao_de_dias_antecipa_o_termino() -> None:
    reduction = ContractAddendumLine(days=-6)

    assert calculations.contract_current_end_date(date(2026, 11, 20), (reduction,)) == date(
        2026, 11, 14
    )


def test_sem_aditivo_o_termino_vigente_e_o_original() -> None:
    assert calculations.contract_current_end_date(date(2026, 10, 30), ()) == date(2026, 10, 30)


# ── Degraus da cascata ───────────────────────────────────────────────────


def test_cascata_do_contrato_da_carga_tem_os_degraus_do_visual() -> None:
    addenda = (ADDENDUM,)

    steps = calculations.contract_cascade_steps(
        original_cents=ORIGINAL_CENTS, addenda=addenda, measurements=MEASUREMENTS
    )

    assert [step["id"] for step in steps] == ["original", "aditivos", "atual", "medido", "saldo"]
    assert [step["rotulo"] for step in steps] == [
        "Valor original",
        "Aditivos aprovados",
        "Valor atual",
        "Medido",
        "Saldo a faturar",
    ]
    assert [step.get("tipo") for step in steps] == ["total", None, "total", None, "total"]
    assert [step["valor"] for step in steps] == [
        330_000_000,
        15_000_000,
        345_000_000,
        -289_800_000,
        55_200_000,
    ]


def test_cascata_com_supressao_marca_o_aditivo_com_sinal_negativo() -> None:
    steps = calculations.contract_cascade_steps(
        original_cents=100_000_000,
        addenda=(ContractAddendumLine(value_cents=-15_000_000),),
        measurements=(),
    )

    by_id = {step["id"]: step for step in steps}

    assert by_id["aditivos"]["valor"] == -15_000_000
    assert by_id["atual"]["valor"] == 85_000_000
    assert by_id["medido"]["valor"] == 0
    assert by_id["saldo"]["valor"] == 85_000_000
