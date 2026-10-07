"""Validações da ficha do contrato (ISSUE-032): o fluxo da medição e os formulários.

As transições são as do protótipo: Em análise vai para Aprovada ou Devolvida (com motivo);
Aprovada vai para Faturada; Faturada vai para Paga; Devolvida é terminal. A medição pede período
e valor maior que zero; o aditivo pede data, motivo e valor e/ou dias.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.core.errors import InvalidDataError
from src.modulos.financeiro import calculations, validation

# ── Transições da medição ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (calculations.SITUATION_UNDER_REVIEW, calculations.SITUATION_APPROVED),
        (calculations.SITUATION_UNDER_REVIEW, calculations.SITUATION_RETURNED),
        (calculations.SITUATION_APPROVED, calculations.SITUATION_INVOICED),
        (calculations.SITUATION_INVOICED, calculations.SITUATION_PAID),
    ],
)
def test_transicao_permitida_passa(current: str, target: str) -> None:
    assert validation.measurement_transition_allowed(current, target)
    validation.check_measurement_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (calculations.SITUATION_UNDER_REVIEW, calculations.SITUATION_INVOICED),
        (calculations.SITUATION_UNDER_REVIEW, calculations.SITUATION_PAID),
        (calculations.SITUATION_APPROVED, calculations.SITUATION_PAID),
        (calculations.SITUATION_INVOICED, calculations.SITUATION_APPROVED),
        (calculations.SITUATION_RETURNED, calculations.SITUATION_UNDER_REVIEW),
        (calculations.SITUATION_PAID, calculations.SITUATION_INVOICED),
    ],
)
def test_transicao_recusada_traz_a_situacao_no_campo(current: str, target: str) -> None:
    assert not validation.measurement_transition_allowed(current, target)

    with pytest.raises(InvalidDataError) as erro:
        validation.check_measurement_transition(current, target)

    message = erro.value.detail["situacao"]
    assert current in message
    assert target in message


# ── Formulário da medição e devolução ────────────────────────────────────


def test_medicao_valida_volta_com_periodo_centavos_e_marco() -> None:
    form = validation.parse_measurement_form(
        {"periodo": "2026-09", "bruto": "1.000,00", "marco": "4"}
    )

    assert form.period == date(2026, 9, 1)
    assert form.value_cents == 100_000
    assert form.milestone_id == 4


def test_medicao_sem_marco_e_por_quantidade() -> None:
    form = validation.parse_measurement_form({"periodo": "2026-09", "bruto": "1.000,00"})

    assert form.milestone_id is None


def test_medicao_sem_periodo_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_measurement_form({"periodo": "", "bruto": "1.000,00"})

    assert "período" in erro.value.detail["periodo"]


def test_medicao_com_periodo_invalido_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_measurement_form({"periodo": "2026-13", "bruto": "1.000,00"})

    assert "período" in erro.value.detail["periodo"]


@pytest.mark.parametrize("value", ["", "0,00", "-1.000,00"])
def test_medicao_com_valor_nao_positivo_e_recusada(value: str) -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_measurement_form({"periodo": "2026-09", "bruto": value})

    assert "maior que zero" in erro.value.detail["bruto"]


def test_medicao_acima_do_saldo_disponivel_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_measurement_balance(value_cents=55_200_001, available_cents=55_200_000)

    message = erro.value.detail["bruto"]
    assert "supera o saldo disponível" in message
    assert "Registre um aditivo antes" in message


def test_medicao_dentro_do_saldo_passa() -> None:
    validation.check_measurement_balance(value_cents=55_200_000, available_cents=55_200_000)


def test_devolucao_sem_motivo_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_return_form({"motivo": "   "})

    assert "motivo da devolução" in erro.value.detail["motivo"]


def test_devolucao_com_motivo_volta_o_texto() -> None:
    assert validation.parse_return_form({"motivo": "Falta a evidência do marco M2."}) == (
        "Falta a evidência do marco M2."
    )


def test_devolucao_com_motivo_longo_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_return_form({"motivo": "x" * 301})

    assert "300" in erro.value.detail["motivo"]


# ── Formulário do aditivo ────────────────────────────────────────────────


def test_aditivo_valido_volta_com_todas_as_origens() -> None:
    form = validation.parse_addendum_form(
        {
            "data": "2026-05-18",
            "valor": "150.000,00",
            "dias": "21",
            "motivo": "Engenharia do sistema de tratamento de efluentes.",
            "sm": "7",
            "claim": "3",
        }
    )

    assert form.signed_on == date(2026, 5, 18)
    assert form.value_cents == 15_000_000
    assert form.days == 21
    assert form.reason == "Engenharia do sistema de tratamento de efluentes."
    assert form.change_id == 7
    assert form.claim_id == 3


def test_aditivo_aceita_valor_negativo_de_supressao() -> None:
    form = validation.parse_addendum_form(
        {"data": "2026-05-18", "valor": "-15.000,00", "motivo": "Supressão do escopo."}
    )

    assert form.value_cents == -1_500_000
    assert form.days == 0


def test_aditivo_so_com_dias_passa() -> None:
    form = validation.parse_addendum_form(
        {"data": "2026-05-18", "valor": "0,00", "dias": "21", "motivo": "Prorrogação."}
    )

    assert form.value_cents == 0
    assert form.days == 21


def test_aditivo_sem_valor_nem_dias_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_addendum_form(
            {"data": "2026-05-18", "valor": "0,00", "dias": "0", "motivo": "Sem efeito."}
        )

    assert "valor, prorrogação ou ambos" in erro.value.detail["valor"]


def test_aditivo_sem_data_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_addendum_form({"data": "", "dias": "1", "motivo": "Prorrogação."})

    assert "data de assinatura" in erro.value.detail["data"]


def test_aditivo_sem_motivo_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_addendum_form({"data": "2026-05-18", "dias": "1", "motivo": ""})

    assert "motivo do aditivo" in erro.value.detail["motivo"]


def test_aditivo_com_motivo_longo_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_addendum_form({"data": "2026-05-18", "dias": "1", "motivo": "x" * 301})

    assert "300" in erro.value.detail["motivo"]
