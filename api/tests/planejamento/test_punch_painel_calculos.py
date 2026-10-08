"""Cálculos do painel da Punch list (ISSUE-050): aging, burndown, contagens e liberação.

As contas são puras: a data de referência entra como argumento (D6) e as fronteiras do aging
são testadas com a data injetada (7, 8, 30 e 31 dias).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.planejamento import calculations

HOJE = date(2026, 9, 25)


def _estado(
    opened_on: date,
    *,
    situation: str = "Aberto",
    category: str = "B",
    system_id: int = 1,
    discipline: str = "Civil",
    company: str = "Alfa Montagens",
    closed_on: date | None = None,
) -> calculations.PunchPanelState:
    return calculations.PunchPanelState(
        situation=situation,
        category=category,
        system_id=system_id,
        discipline=discipline,
        company=company,
        opened_on=opened_on,
        closed_on=closed_on,
    )


def test_a_faixa_do_aging_usa_os_limites_dos_parametros() -> None:
    bands = (7, 30)

    assert calculations.punch_aging_labels(bands) == (
        "Até 7 dias",
        "8 a 30 dias",
        "Mais de 30 dias",
    )
    assert calculations.punch_aging_band(0, bands) == 0
    assert calculations.punch_aging_band(7, bands) == 0
    assert calculations.punch_aging_band(8, bands) == 1
    assert calculations.punch_aging_band(30, bands) == 1
    assert calculations.punch_aging_band(31, bands) == 2


def test_o_aging_conta_a_fronteira_com_a_data_injetada() -> None:
    states = (
        _estado(date(2026, 9, 18), category="A"),
        _estado(date(2026, 9, 17), category="B"),
        _estado(date(2026, 8, 26), category="C"),
        _estado(date(2026, 8, 25), category="A"),
        _estado(date(2026, 9, 1), situation="Fechado", closed_on=date(2026, 9, 10)),
        _estado(date(2026, 9, 20), situation="Cancelado"),
    )

    rows = calculations.punch_aging_counts(states, reference_date=HOJE, bands=(7, 30))

    assert [(row.label, row.counts.a, row.counts.b, row.counts.c) for row in rows] == [
        ("Até 7 dias", 1, 0, 0),
        ("8 a 30 dias", 0, 1, 1),
        ("Mais de 30 dias", 1, 0, 0),
    ]
    assert [row.counts.total for row in rows] == [1, 2, 1]


def test_o_percentual_de_sistemas_liberados_por_marco() -> None:
    assert calculations.punch_released_pct(4, 1) == Decimal("75.0")
    assert calculations.punch_released_pct(4, 4) == Decimal("0.0")
    assert calculations.punch_released_pct(4, 0) == Decimal("100.0")
    assert calculations.punch_released_pct(3, 1) == Decimal("66.7")
    assert calculations.punch_released_pct(0, 0) is None


def test_o_burndown_bate_com_as_datas_de_abertura_e_fechamento() -> None:
    states = (
        _estado(date(2026, 8, 5), situation="Fechado", closed_on=date(2026, 8, 20)),
        _estado(date(2026, 8, 28)),
        _estado(date(2026, 9, 2)),
        _estado(date(2026, 9, 15), situation="Cancelado"),
    )

    points = calculations.punch_burndown(states, reference_date=HOJE)

    assert [point.week for point in points] == [
        date(2026, 8, 3),
        date(2026, 8, 10),
        date(2026, 8, 17),
        date(2026, 8, 24),
        date(2026, 8, 31),
        date(2026, 9, 7),
        date(2026, 9, 14),
        date(2026, 9, 21),
        date(2026, 9, 28),
    ]
    assert [(point.opened, point.closed, point.balance) for point in points] == [
        (0, 0, 0),
        (1, 0, 1),
        (1, 0, 1),
        (1, 1, 0),
        (2, 1, 1),
        (3, 1, 2),
        (3, 1, 2),
        (3, 1, 2),
        (3, 1, 2),
    ]


def test_o_burndown_sem_item_tem_as_duas_semanas_da_referencia() -> None:
    assert calculations.punch_burndown_weeks((), reference_date=HOJE) == (
        date(2026, 9, 21),
        date(2026, 9, 28),
    )


def test_as_contagens_por_disciplina_seguem_a_ordem_do_cadastro() -> None:
    states = (
        _estado(date(2026, 9, 1), discipline="Mecânica", category="A"),
        _estado(date(2026, 9, 2), discipline="Civil", category="C"),
        _estado(date(2026, 9, 3), discipline="Mecânica", category="B"),
        _estado(date(2026, 9, 4), discipline="Elétrica", situation="Fechado"),
    )

    rows = calculations.punch_discipline_counts(
        states, order=("Civil", "Elétrica", "Mecânica", "Tubulação")
    )

    assert [(row.label, row.counts.a, row.counts.b, row.counts.c) for row in rows] == [
        ("Civil", 0, 0, 1),
        ("Mecânica", 1, 1, 0),
    ]


def test_as_contagens_por_empresa_seguem_a_primeira_aparicao() -> None:
    states = (
        _estado(date(2026, 9, 1), company="Zeta Civil", category="C"),
        _estado(date(2026, 9, 2), company="Alfa Montagens", category="A"),
        _estado(date(2026, 9, 3), company="Zeta Civil", category="C"),
    )

    rows = calculations.punch_company_counts(states)

    assert [(row.label, row.counts.total) for row in rows] == [
        ("Zeta Civil", 2),
        ("Alfa Montagens", 1),
    ]
