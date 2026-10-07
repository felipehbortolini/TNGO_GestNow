"""Validações puras das reservas (ISSUE-041): consumo, liberação e reserva inexistente.

As fronteiras do protótipo: o pedido igual ao saldo passa e um centavo acima recusa; a liberação
é limitada ao saldo menos o pedido em outras SMs abertas; sem reserva constituída a recusa é a
mensagem própria. As funções devolvem a mensagem e a fachada da Governança as usa na etapa 2.
"""

from __future__ import annotations

from src.modulos.financeiro.validation import (
    RESERVE_MISSING,
    reserve_consumption_error,
    reserve_missing_error,
    reserve_release_error,
)

BALANCE = 200_000_00
SOURCE = "Reserva de contingência"


def test_consumo_igual_ao_saldo_passa() -> None:
    assert reserve_consumption_error(BALANCE, BALANCE, reserve_source=SOURCE) is None


def test_consumo_um_centavo_acima_do_saldo_recusa() -> None:
    message = reserve_consumption_error(BALANCE + 1, BALANCE, reserve_source=SOURCE)

    assert message is not None
    assert "R$ 200.000,01" in message
    assert "R$ 200.000,00" in message
    assert "aditivo de orçamento" in message


def test_consumo_nomeia_a_reserva_da_fonte() -> None:
    message = reserve_consumption_error(1, 0, reserve_source=SOURCE)

    assert message is not None
    assert "Saldo da reserva de contingência insuficiente" in message


def test_consumo_de_zero_recusa_com_saldo_negativo() -> None:
    assert reserve_consumption_error(0, -1, reserve_source=SOURCE) is not None


def test_liberacao_igual_ao_saldo_livre_passa() -> None:
    assert reserve_release_error(150_000_00, BALANCE, 50_000_00) is None


def test_liberacao_desconta_o_pedido_em_outras_sms_abertas() -> None:
    message = reserve_release_error(150_000_00 + 1, BALANCE, 50_000_00)

    assert message == (
        "A reserva tem R$ 150.000,00 livres para liberar "
        "(saldo menos o pedido em outras SMs abertas)."
    )


def test_liberacao_sem_pedido_em_aberto_usa_o_saldo_inteiro() -> None:
    assert reserve_release_error(BALANCE, BALANCE, 0) is None
    assert reserve_release_error(BALANCE + 1, BALANCE, 0) is not None


def test_liberacao_com_pedido_maior_que_o_saldo_mostra_o_saldo_livre_negativo() -> None:
    message = reserve_release_error(1, 10_000_00, 12_000_00)

    assert message is not None
    assert "-R$ 2.000,00" in message


def test_projeto_sem_reserva_tem_mensagem_propria() -> None:
    assert reserve_missing_error() == RESERVE_MISSING
    assert RESERVE_MISSING == "O projeto não tem reservas constituídas."
