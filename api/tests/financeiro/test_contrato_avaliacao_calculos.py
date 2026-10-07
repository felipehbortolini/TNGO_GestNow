"""Cálculos puros da avaliação de desempenho da contratada (ISSUE-034).

As fronteiras das classes são as dos parâmetros: A a partir de 85, B a partir de 70, C a partir
de 50 e D a partir de 0. Com os pesos gravados {20, 25, 55} as notas escolhidas caem exatamente
em 84/85, 69/70 e 49/50; o arredondamento do JavaScript é o meio para cima e os pesos gravados
são os da avaliação, não os do parâmetro.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.modulos.financeiro import calculations

WEIGHTS = {"a": 20, "b": 25, "c": 55}

CLASSES = (
    calculations.EvaluationClass(name="A", minimum=85, description="Preferencial"),
    calculations.EvaluationClass(name="B", minimum=70, description="Aprovada"),
    calculations.EvaluationClass(
        name="C", minimum=50, description="Aprovada com plano de melhoria"
    ),
    calculations.EvaluationClass(name="D", minimum=0, description="Não recomendada"),
)


# ── Nota ponderada ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("notes", "expected"),
    [
        ({"a": 5, "b": 4, "c": 4}, 84),
        ({"a": 4, "b": 5, "c": 4}, 85),
        ({"a": 4, "b": 2, "c": 4}, 70),
        ({"a": 5, "b": 1, "c": 4}, 69),
        ({"a": 2, "b": 4, "c": 2}, 50),
        ({"a": 3, "b": 3, "c": 2}, 49),
    ],
)
def test_nota_ponderada_bate_na_fronteira(notes: dict[str, int], expected: int) -> None:
    assert calculations.evaluation_weighted_score(notes, WEIGHTS) == expected


@pytest.mark.parametrize(
    ("notes", "weights", "expected"),
    [
        ({"a": 2, "b": 1}, {"a": 1, "b": 7}, 23),
        ({"a": 4, "b": 1}, {"a": 1, "b": 7}, 28),
        ({"a": 2, "b": 2}, {"a": 1, "b": 7}, 40),
    ],
)
def test_nota_arredonda_meio_para_cima_como_o_javascript(
    notes: dict[str, int], weights: dict[str, int], expected: int
) -> None:
    assert calculations.evaluation_weighted_score(notes, weights) == expected


def test_criterio_sem_nota_nao_conta_nem_o_peso() -> None:
    assert calculations.evaluation_weighted_score({"a": 5}, WEIGHTS) == 100


def test_sem_nota_ou_sem_peso_nao_ha_nota() -> None:
    assert calculations.evaluation_weighted_score({}, WEIGHTS) is None
    assert calculations.evaluation_weighted_score({"a": 5}, {}) is None


def test_pesos_gravados_mudam_a_nota_das_mesmas_notas() -> None:
    notes = {"a": 3, "b": 5}

    first = calculations.evaluation_weighted_score(notes, {"a": 50, "b": 50})
    second = calculations.evaluation_weighted_score(notes, {"a": 80, "b": 20})

    assert first == 80
    assert second == 68
    assert first != second


# ── Classe ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("score", "expected"),
    [(100, "A"), (85, "A"), (84, "B"), (70, "B"), (69, "C"), (50, "C"), (49, "D"), (0, "D")],
)
def test_classe_pela_fronteira(score: int, expected: str) -> None:
    chosen = calculations.evaluation_class(score, CLASSES)

    assert chosen is not None
    assert chosen.name == expected


def test_nota_e_classe_na_fronteira_de_84_e_85() -> None:
    at_84 = calculations.evaluation_weighted_score({"a": 5, "b": 4, "c": 4}, WEIGHTS)
    at_85 = calculations.evaluation_weighted_score({"a": 4, "b": 5, "c": 4}, WEIGHTS)

    assert calculations.evaluation_class(at_84, CLASSES).name == "B"
    assert calculations.evaluation_class(at_85, CLASSES).name == "A"


def test_sem_nota_nao_ha_classe() -> None:
    assert calculations.evaluation_class(None, CLASSES) is None


def test_classe_no_empate_fica_a_primeira_da_lista() -> None:
    classes = (
        calculations.EvaluationClass(name="B1", minimum=70),
        calculations.EvaluationClass(name="B2", minimum=70),
    )

    chosen = calculations.evaluation_class(80, classes)

    assert chosen is not None
    assert chosen.name == "B1"


# ── Exige plano ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("note", [1, 2])
def test_nota_ate_o_limite_exige_plano(note: int) -> None:
    assert calculations.evaluation_requires_plan({"a": 4, "b": note, "c": 5}, 2)


def test_nota_acima_do_limite_nao_exige_plano() -> None:
    assert not calculations.evaluation_requires_plan({"a": 4, "b": 3, "c": 5}, 2)


def test_sem_nota_nao_exige_plano() -> None:
    assert not calculations.evaluation_requires_plan({}, 2)


# ── Série do gráfico de áreas ────────────────────────────────────────────


def test_serie_da_avaliacao_em_ordem_de_periodo() -> None:
    evaluations = (
        calculations.EvaluationFact(
            period=date(2026, 8, 1), notes={"a": 5, "b": 4, "c": 4}, weights=WEIGHTS
        ),
        calculations.EvaluationFact(
            period=date(2026, 7, 1), notes={"a": 4, "b": 5, "c": 4}, weights=WEIGHTS
        ),
    )

    assert calculations.evaluation_trend_points(evaluations) == (
        {"ano": 2026, "mes": 7, "valor": 85},
        {"ano": 2026, "mes": 8, "valor": 84},
    )
