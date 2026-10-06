"""Cálculos puros das revisões, do saldo livre e do item novo (ISSUE-030, D5b, D6).

A base do item sai da revisão congelada quando ela existe; o remanejamento aplicado vale na
origem e no destino enquanto a revisão que o consolida não chega; o saldo livre desconta o
comprometido e o reservado em outras SMs abertas; o código do item novo é o próximo número
livre entre os irmãos.
"""

from __future__ import annotations

from decimal import Decimal

from src.modulos.financeiro.calculations import (
    ItemLine,
    ReallocationLine,
    ReservationLine,
    current_base_cents,
    free_balance_cents,
    item_totals,
    next_item_code,
)

D = Decimal


def _item(
    identifier: int, quantity: str, price: int, *, parent_id: int | None = None, **fields: object
) -> ItemLine:
    return ItemLine(
        id=identifier,
        parent_id=parent_id,
        code=str(identifier),
        description="Item",
        level=3,
        quantity=D(quantity),
        unit_price_cents=price,
        **fields,
    )


# ── Base congelada na árvore ─────────────────────────────────────────────


def test_totais_usam_a_base_congelada_quando_ela_existe() -> None:
    items = [
        ItemLine(id=1, parent_id=None, code="1", description="Pacote", level=1),
        ItemLine(id=2, parent_id=1, code="1.1", description="Subpacote", level=2),
        _item(3, "10", 1_000, parent_id=2, base_cents=7_000),
        _item(4, "2", 500, parent_id=2),
    ]

    totals = item_totals(items)

    assert totals[3] == 7_000
    assert totals[4] == 1_000
    assert totals[2] == 8_000
    assert totals[1] == 8_000


# ── Orçado atual ─────────────────────────────────────────────────────────


def test_orcado_atual_sem_revisao_e_quantidade_vezes_preco() -> None:
    items = [_item(1, "10", 1_000), _item(2, "2", 500)]

    bases = current_base_cents(items, revision_bases={}, latest_revision=None)

    assert bases == {1: 10_000, 2: 1_000}


def test_orcado_atual_com_revisao_usa_a_base_congelada_e_zero_fora_dela() -> None:
    items = [_item(1, "10", 1_000), _item(2, "2", 500)]

    bases = current_base_cents(items, revision_bases={1: 9_000}, latest_revision=2)

    assert bases == {1: 9_000, 2: 0}


def test_remanejamento_aplicado_move_o_valor_entre_origem_e_destino() -> None:
    items = [_item(1, "10", 1_000), _item(2, "2", 500)]
    lines = [ReallocationLine(source_item_id=1, target_item_id=2, value_cents=3_000, revision=3)]

    bases = current_base_cents(
        items, revision_bases={1: 9_000, 2: 1_000}, latest_revision=2, reallocations=lines
    )

    assert bases == {1: 6_000, 2: 4_000}


def test_remanejamento_de_outra_revisao_ou_de_item_desconhecido_nao_entra() -> None:
    items = [_item(1, "10", 1_000)]
    lines = [
        ReallocationLine(source_item_id=1, target_item_id=99, value_cents=400, revision=3),
        ReallocationLine(source_item_id=1, target_item_id=99, value_cents=500, revision=2),
    ]

    bases = current_base_cents(
        items, revision_bases={1: 9_000}, latest_revision=1, reallocations=lines
    )

    assert bases == {1: 8_500}


def test_remanejamento_sem_revisao_consolida_na_revisao_zero() -> None:
    items = [_item(1, "10", 1_000), _item(2, "2", 500)]
    lines = [ReallocationLine(source_item_id=1, target_item_id=2, value_cents=1_000, revision=0)]

    bases = current_base_cents(items, revision_bases={}, latest_revision=None, reallocations=lines)

    assert bases == {1: 9_000, 2: 2_000}


# ── Saldo livre ──────────────────────────────────────────────────────────


def test_saldo_livre_desconta_comprometido_e_reservado_do_proprio_item() -> None:
    reservations = [
        ReservationLine(source_item_id=1, value_cents=1_000),
        ReservationLine(source_item_id=1, value_cents=500),
        ReservationLine(source_item_id=2, value_cents=9_000),
    ]

    free = free_balance_cents(
        1, base_cents=10_000, committed_cents=3_000, reservations=reservations
    )

    assert free == 5_500


def test_saldo_livre_sem_comprometido_nem_reserva_e_a_base() -> None:
    assert free_balance_cents(1, base_cents=10_000, committed_cents=0, reservations=()) == 10_000


def test_saldo_livre_fica_negativo_quando_o_comprometido_supera_a_base() -> None:
    assert free_balance_cents(1, base_cents=1_000, committed_cents=2_500, reservations=()) == -1_500


# ── Código do item novo ──────────────────────────────────────────────────


def test_codigo_do_item_novo_e_o_proximo_irmao() -> None:
    assert next_item_code("1.1", ["1.1.1", "1.1.2", "1.2.1"]) == "1.1.3"
    assert next_item_code("1", ["1.1", "1.2", "10"]) == "1.3"


def test_codigo_do_item_novo_na_raiz_e_o_proximo_pacote() -> None:
    assert next_item_code(None, ["1", "2", "10"]) == "11"


def test_codigo_do_item_novo_sem_irmaos_comeca_no_um() -> None:
    assert next_item_code("2.1", []) == "2.1.1"
    assert next_item_code(None, []) == "1"
