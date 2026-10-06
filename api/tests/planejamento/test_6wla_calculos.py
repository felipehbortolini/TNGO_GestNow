"""Fórmulas do 6WLA (ISSUE-045): a janela de seis semanas, as restrições e os indicadores.

Costura pura, sem banco: cada regra recebe a data de referência como argumento (D6) e
o teste injeta a data. Cada uma tem o caso de fronteira: o dia da data necessária, a
virada de ano, o domingo, o horizonte sem restrição.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.modulos.planejamento import calculations as calc


def _contagem(
    planned: tuple[bool, ...], total: int = 0, opened: int = 0, overdue: int = 0
) -> calc.ActivityCounts:
    return calc.ActivityCounts(
        planned=planned,
        total_constraints=total,
        open_constraints=opened,
        overdue_constraints=overdue,
    )


NENHUMA = (False,) * 6
SO_A_PRIMEIRA = (True, False, False, False, False, False)
SO_A_TERCEIRA = (False, False, True, False, False, False)


# ── A janela de seis semanas anda com a data de hoje ─────────────────────


@pytest.mark.parametrize(
    ("hoje", "inicio"),
    [
        (date(2026, 9, 25), date(2026, 9, 28)),  # sexta da S39: o horizonte do protótipo
        (date(2026, 9, 21), date(2026, 9, 28)),  # segunda: ainda é a mesma semana
        (date(2026, 9, 27), date(2026, 9, 28)),  # domingo: fronteira da semana ISO
        (date(2026, 9, 28), date(2026, 10, 5)),  # segunda seguinte: a janela andou uma semana
        (date(2026, 10, 6), date(2026, 10, 12)),
        (date(2026, 12, 30), date(2027, 1, 4)),  # virada de ano
    ],
)
def test_a_janela_comeca_na_segunda_da_semana_seguinte_a_de_hoje(hoje: date, inicio: date) -> None:
    assert calc.lookahead_window_start(hoje) == inicio
    assert inicio.weekday() == 0


def test_as_seis_semanas_do_prototipo_em_25_09_2026() -> None:
    semanas = calc.lookahead_weeks(date(2026, 9, 25))

    assert [semana.label for semana in semanas] == ["S40", "S41", "S42", "S43", "S44", "S45"]
    assert semanas[0].start == date(2026, 9, 28)
    assert semanas[5].start == date(2026, 11, 2)
    assert [semana.index for semana in semanas] == [0, 1, 2, 3, 4, 5]


def test_a_janela_anda_sete_dias_quando_a_data_anda_uma_semana() -> None:
    antes = calc.lookahead_weeks(date(2026, 9, 25))
    depois = calc.lookahead_weeks(date(2026, 10, 2))

    assert [semana.label for semana in depois] == ["S41", "S42", "S43", "S44", "S45", "S46"]
    assert depois[0].start == antes[1].start


def test_a_janela_atravessa_a_semana_53_e_o_ano_novo() -> None:
    semanas = calc.lookahead_weeks(date(2026, 12, 21))

    assert [semana.label for semana in semanas] == ["S53", "S1", "S2", "S3", "S4", "S5"]
    assert semanas[1].start == date(2027, 1, 4)


# ── Restrição aberta e vencida ───────────────────────────────────────────


def test_sem_data_de_remocao_a_restricao_esta_aberta() -> None:
    assert calc.constraint_is_open(None) is True
    assert calc.constraint_is_open(date(2026, 9, 20)) is False


@pytest.mark.parametrize(
    ("necessaria", "remocao", "vencida"),
    [
        (date(2026, 9, 24), None, True),  # um dia atrás
        (date(2026, 9, 25), None, False),  # o próprio dia da data de referência não vence
        (date(2026, 9, 26), None, False),
        (date(2026, 9, 24), date(2026, 9, 20), False),  # removida não vence
        (date(2026, 9, 24), date(2026, 9, 25), False),
    ],
)
def test_vencida_e_aberta_com_a_data_necessaria_ja_passada(
    necessaria: date, remocao: date | None, *, vencida: bool
) -> None:
    assert calc.constraint_is_overdue(necessaria, remocao, date(2026, 9, 25)) is vencida


def test_a_mesma_restricao_vence_quando_a_data_de_referencia_avanca() -> None:
    necessaria = date(2026, 10, 6)

    assert calc.constraint_is_overdue(necessaria, None, date(2026, 10, 6)) is False
    assert calc.constraint_is_overdue(necessaria, None, date(2026, 10, 7)) is True


def test_atividade_pronta_e_a_sem_restricao_aberta() -> None:
    assert calc.activity_is_ready(0) is True
    assert calc.activity_is_ready(1) is False


@pytest.mark.parametrize(
    ("abertas", "vencidas", "situacao"),
    [(0, 0, "pronta"), (2, 0, "com_restricao"), (2, 1, "vencida"), (1, 1, "vencida")],
)
def test_situacao_da_atividade(abertas: int, vencidas: int, situacao: str) -> None:
    assert calc.activity_situation(abertas, vencidas) == situacao


# ── A atividade com restrição aberta aparece sinalizada ──────────────────


def test_restricao_aberta_nas_duas_primeiras_semanas_sinaliza_a_atividade() -> None:
    assert calc.has_open_constraint_in_short_term(SO_A_PRIMEIRA, 1) is True
    assert calc.has_open_constraint_in_short_term((False, True, False, False, False, False), 1)


def test_a_terceira_semana_ja_e_fora_do_curto_prazo() -> None:
    assert calc.has_open_constraint_in_short_term(SO_A_TERCEIRA, 3) is False


def test_sem_restricao_aberta_nada_e_sinalizado() -> None:
    assert calc.has_open_constraint_in_short_term(SO_A_PRIMEIRA, 0) is False


def test_a_marca_laranja_so_vale_para_semana_programada_do_curto_prazo() -> None:
    planejada = (True, True, True, False, False, False)

    assert [calc.week_at_risk(i, planejada, 1) for i in range(6)] == [
        True,
        True,
        False,
        False,
        False,
        False,
    ]
    assert not any(calc.week_at_risk(i, planejada, 0) for i in range(6))


# ── Índice de remoção e indicadores ──────────────────────────────────────


def test_indice_de_remocao_sem_restricao_e_nulo() -> None:
    assert calc.removal_index(0, 0) is None


@pytest.mark.parametrize(
    ("total", "abertas", "esperado"),
    [
        (28, 23, Decimal("17.86")),  # o número do protótipo: 18%
        (15, 13, Decimal("13.33")),
        (4, 0, Decimal("100.00")),
        (2, 2, Decimal("0.00")),
        (8, 7, Decimal("12.50")),
        (3, 2, Decimal("33.33")),
    ],
)
def test_indice_de_remocao(total: int, abertas: int, esperado: Decimal) -> None:
    assert calc.removal_index(total, abertas) == esperado


def test_indicadores_do_horizonte() -> None:
    atividades = [
        _contagem(SO_A_PRIMEIRA, total=2, opened=1),
        _contagem((False, True, False, False, False, False), total=0),
        _contagem(SO_A_TERCEIRA, total=1, opened=1, overdue=1),
        _contagem((True, True, False, False, False, False), total=3, opened=0),
    ]

    figuras = calc.lookahead_figures(atividades)

    assert figuras.activities == 4
    assert figuras.short_term_activities == 3
    assert figuras.short_term_ready == 2
    assert figuras.total_constraints == 6
    assert figuras.open_constraints == 2
    assert figuras.overdue_constraints == 1
    assert figuras.removal_index == Decimal("66.67")


def test_indicadores_sem_atividade() -> None:
    figuras = calc.lookahead_figures([])

    assert figuras == calc.LookaheadFigures(
        activities=0,
        short_term_activities=0,
        short_term_ready=0,
        total_constraints=0,
        open_constraints=0,
        overdue_constraints=0,
        removal_index=None,
    )


# ── Código da atividade e a barra do Gantt ───────────────────────────────


@pytest.mark.parametrize(
    ("existentes", "proximo"),
    [
        ([], "LA-01"),
        (["LA-01", "LA-02"], "LA-03"),
        (["LA-09", "LA-10"], "LA-11"),  # numérico, não alfabético
        (["LA-01", "LA-14"], "LA-15"),
        (["CB-LA-01", "CB-LA-05"], "CB-LA-06"),
        (["LA-99"], "LA-100"),
        (["SEM-NUMERO"], "SEM-NUMERO01"),
    ],
)
def test_proximo_codigo_da_atividade(existentes: list[str], proximo: str) -> None:
    assert calc.next_activity_code(existentes) == proximo


def test_a_barra_vai_da_primeira_a_ultima_semana_programada_ate_o_sabado() -> None:
    planejada = (False, True, True, False, False, False)

    assert calc.activity_span(planejada, date(2026, 9, 28)) == (
        date(2026, 10, 5),
        date(2026, 10, 17),
    )


def test_a_barra_de_uma_semana_so_vai_de_segunda_a_sabado() -> None:
    assert calc.activity_span(SO_A_PRIMEIRA, date(2026, 9, 28)) == (
        date(2026, 9, 28),
        date(2026, 10, 3),
    )


def test_sem_semana_programada_nao_ha_barra() -> None:
    assert calc.activity_span(NENHUMA, date(2026, 9, 28)) is None
