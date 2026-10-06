"""Regras puras da Punch list (ISSUE-049): fluxo, idade, vencimento e bloqueio, com fronteiras.

A data de referência entra como argumento; nenhuma regra lê o relógio. Os números de referência
são os do protótipo (``punchComCalculos`` e ``bloqueio`` de ``punch-list.js``).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from src.modulos.planejamento import punch_calculations as calc
from src.modulos.planejamento.punch_calculations import PunchFacts

HOJE = date(2026, 9, 25)


def _item(**changes: Any) -> PunchFacts:
    values: dict[str, Any] = {
        "system_id": 1,
        "category": "A",
        "milestone": "Comissionamento",
        "situation": calc.OPEN,
        "opened_on": date(2026, 9, 15),
        "due_date": date(2026, 10, 15),
        "closed_on": None,
    }
    values.update(changes)
    return PunchFacts(**values)


@pytest.mark.parametrize(
    ("situation", "expected"),
    [
        (calc.OPEN, True),
        (calc.IN_TREATMENT, True),
        (calc.AWAITING_VERIFICATION, True),
        (calc.CLOSED, False),
        (calc.CANCELLED, False),
    ],
)
def test_item_aberto_e_o_que_nao_e_fechado_nem_cancelado(situation: str, expected: object) -> None:
    assert calc.is_open(situation) is expected


@pytest.mark.parametrize(
    ("origin", "target", "allowed"),
    [
        (calc.OPEN, calc.IN_TREATMENT, True),
        (calc.OPEN, calc.CLOSED, False),
        (calc.IN_TREATMENT, calc.AWAITING_VERIFICATION, True),
        (calc.IN_TREATMENT, calc.CLOSED, False),
        (calc.AWAITING_VERIFICATION, calc.CLOSED, True),
        (calc.AWAITING_VERIFICATION, calc.IN_TREATMENT, True),
        (calc.CLOSED, calc.IN_TREATMENT, False),
        (calc.CANCELLED, calc.OPEN, False),
        (calc.OPEN, calc.CANCELLED, True),
    ],
)
def test_o_fluxo_so_permite_os_passos_do_protocolo(
    origin: str, target: str, allowed: object
) -> None:
    assert calc.can_move(origin, target) is allowed


def test_idade_de_item_aberto_conta_ate_a_data_de_referencia() -> None:
    assert calc.item_age_days(_item(opened_on=date(2026, 9, 18)), HOJE) == 7
    assert calc.item_age_days(_item(opened_on=HOJE), HOJE) == 0


def test_idade_de_item_fechado_conta_ate_o_fechamento() -> None:
    fechado = _item(situation=calc.CLOSED, opened_on=date(2026, 8, 5), closed_on=date(2026, 8, 20))
    assert calc.item_age_days(fechado, HOJE) == 15


def test_vencido_so_depois_do_prazo_e_so_se_aberto() -> None:
    assert calc.is_overdue(_item(due_date=date(2026, 9, 24)), HOJE) is True
    assert calc.is_overdue(_item(due_date=HOJE), HOJE) is False
    assert calc.is_overdue(_item(due_date=date(2026, 9, 24), situation=calc.CLOSED), HOJE) is False


def test_item_a_aberto_bloqueia_o_marco_do_item_e_os_seguintes() -> None:
    itens = [_item(milestone="Comissionamento")]
    assert calc.blocking_count(itens, 1, "Completação mecânica") == 0
    assert calc.blocking_count(itens, 1, "Pré-comissionamento") == 0
    assert calc.blocking_count(itens, 1, "Comissionamento") == 1
    assert calc.blocking_count(itens, 1, "Partida") == 1


def test_item_b_ou_c_nao_bloqueia_marco_algum_antes_do_aceite_definitivo() -> None:
    itens = [_item(category="B"), _item(category="C")]
    assert calc.blocking_count(itens, 1, "Comissionamento") == 0
    assert calc.blocking_count(itens, 1, "Aceite provisório") == 0


def test_no_aceite_definitivo_qualquer_item_aberto_bloqueia() -> None:
    itens = [_item(category="C"), _item(category="B", situation=calc.IN_TREATMENT)]
    assert calc.blocking_count(itens, 1, calc.FINAL_MILESTONE) == 2


def test_item_fechado_ou_cancelado_nao_bloqueia() -> None:
    itens = [_item(situation=calc.CLOSED, closed_on=HOJE), _item(situation=calc.CANCELLED)]
    assert calc.blocking_count(itens, 1, calc.FINAL_MILESTONE) == 0
    assert calc.is_system_blocked(itens, 1, "Comissionamento") is False


def test_o_bloqueio_e_por_sistema() -> None:
    itens = [_item(system_id=1), _item(system_id=2, category="C")]
    assert calc.is_system_blocked(itens, 1, "Comissionamento") is True
    assert calc.is_system_blocked(itens, 2, "Comissionamento") is False


def test_alerta_lista_os_sistemas_bloqueados_para_completacao_ou_comissionamento() -> None:
    itens = [
        _item(system_id=1, milestone="Completação mecânica"),
        _item(system_id=2, milestone="Partida"),
        _item(system_id=3, category="B"),
    ]
    assert calc.blocked_system_ids(itens, [1, 2, 3]) == [1]


@pytest.mark.parametrize(
    ("closed", "valid", "expected"),
    [(3, 15, 20), (1, 3, 33), (2, 3, 67), (0, 4, 0), (4, 4, 100), (0, 0, None)],
)
def test_percentual_de_fechados_arredonda_para_cima_na_metade(
    closed: int, valid: int, expected: int | None
) -> None:
    assert calc.closed_percentage(closed, valid) == expected
