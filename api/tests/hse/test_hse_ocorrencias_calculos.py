"""Cálculos puros das ocorrências do HSE (ISSUE-073, D6): faixa do potencial, pirâmide, HiPo e prazos.

A faixa do potencial é a matriz própria do HSE (P x I de 1 a 5): Baixo até 4, Moderado de 5,
Alto de 10 e Crítico de 15. O nível da pirâmide sai do tipo (1 a 4); o Ambiental fica fora dela.
O HiPo é a consequência potencial além da gravidade real. Os prazos contam do evento: a
comunicação em horas, a investigação preliminar em dias (as horas arredondadas para cima, como o
protótipo) e o relatório final em dias, julgados pela data de referência quando ainda abertos.
Nada aqui lê o relógio nem o banco.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.modulos.hse import calculations

REFERENCIA = date(2026, 9, 25)


# ── Faixa do potencial (P x I) ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("p", "i", "band_id", "score"),
    [
        (1, 1, "baixo", 1),
        (1, 4, "baixo", 4),
        (1, 5, "moderado", 5),
        (3, 3, "moderado", 9),
        (2, 5, "alto", 10),
        (3, 4, "alto", 12),
        (3, 5, "critico", 15),
        (5, 5, "critico", 25),
    ],
)
def test_faixa_do_potencial_nas_fronteiras(p: int, i: int, band_id: str, score: int) -> None:
    band = calculations.potential_band(p, i)

    assert (band.id, band.score) == (band_id, score)


def test_faixa_do_potencial_tem_os_nomes_do_prototipo() -> None:
    assert calculations.potential_band(1, 1).name == "Baixo"
    assert calculations.potential_band(2, 3).name == "Moderado"
    assert calculations.potential_band(2, 5).name == "Alto"
    assert calculations.potential_band(3, 5).name == "Crítico"


# ── Pirâmide ─────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kind", "level"),
    [
        ("Fatalidade", 1),
        ("Acidente com afastamento", 1),
        ("Trabalho restrito", 2),
        ("Tratamento médico", 2),
        ("Primeiros socorros", 2),
        ("Dano material", 3),
        ("Quase acidente", 4),
        ("Ambiental", None),
        ("Desvio", None),
        ("Tipo desconhecido", None),
    ],
)
def test_nivel_da_piramide_pelo_tipo(kind: str, level: int | None) -> None:
    assert calculations.pyramid_level(kind) == level


def test_nome_do_nivel_da_piramide() -> None:
    assert calculations.pyramid_level_name(1) == "Lesão grave"
    assert calculations.pyramid_level_name(2) == "Lesão leve"
    assert calculations.pyramid_level_name(4) == "Quase acidente"
    assert calculations.pyramid_level_name(None) == ""


# ── HiPo ─────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("gravity", "impact", "high"),
    [
        (2, 3, True),
        (3, 3, False),
        (4, 5, True),
        (5, 5, False),
        (None, 5, False),
        (2, None, False),
    ],
)
def test_hipo_e_a_consequencia_potencial_alem_da_gravidade_real(
    gravity: int | None, impact: int | None, *, high: bool
) -> None:
    assert calculations.is_high_potential(gravity, impact) is high


# ── Prazos ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("hours", "overdue"),
    [(23, False), (24, False), (25, True), (None, False)],
)
def test_comunicacao_fora_do_prazo_nas_fronteiras(hours: int | None, *, overdue: bool) -> None:
    assert calculations.communication_overdue(hours, 24) is overdue


@pytest.mark.parametrize(
    ("deadline_hours", "days"),
    [(48, 2), (47, 2), (25, 2), (24, 1), (1, 1), (0, 0)],
)
def test_prazo_preliminar_em_dias_arredonda_para_cima(deadline_hours: int, days: int) -> None:
    assert calculations.investigation_deadline_days(deadline_hours) == days


def test_investigacao_fora_do_prazo_na_fronteira_do_dia() -> None:
    event = date(2026, 9, 12)

    assert calculations.investigation_overdue(event, date(2026, 9, 13), 48) is False
    assert calculations.investigation_overdue(event, date(2026, 9, 14), 48) is False
    assert calculations.investigation_overdue(event, date(2026, 9, 15), 48) is True


def test_investigacao_vencida_enquanto_registrada() -> None:
    event = date(2026, 9, 22)

    assert calculations.investigation_pending_overdue(event, date(2026, 9, 24), 48) is False
    assert calculations.investigation_pending_overdue(event, date(2026, 9, 25), 48) is True


def test_prazo_do_relatorio_final_e_o_evento_mais_os_dias() -> None:
    assert calculations.report_deadline(date(2026, 9, 25), 30) == date(2026, 10, 25)


@pytest.mark.parametrize(
    ("level", "hipo", "required"),
    [(1, False, True), (2, False, False), (4, False, False), (4, True, True), (None, True, True)],
)
def test_relatorio_exigido_de_lti_e_de_hipo(
    level: int | None, *, hipo: bool, required: bool
) -> None:
    assert calculations.report_required(level, hipo=hipo) is required


def test_relatorio_fora_do_prazo_nas_fronteiras() -> None:
    event = date(2026, 9, 25)

    assert (
        calculations.report_overdue(
            date(2026, 10, 25), event_date=event, deadline_days=30, reference_date=REFERENCIA
        )
        is False
    )
    assert (
        calculations.report_overdue(
            date(2026, 10, 26), event_date=event, deadline_days=30, reference_date=REFERENCIA
        )
        is True
    )


def test_relatorio_vencido_so_quando_ainda_aberto() -> None:
    event = date(2026, 8, 1)

    assert (
        calculations.report_overdue(
            None, event_date=event, deadline_days=30, reference_date=REFERENCIA
        )
        is True
    )
    assert (
        calculations.report_overdue(
            date(2026, 8, 20), event_date=event, deadline_days=30, reference_date=REFERENCIA
        )
        is False
    )
