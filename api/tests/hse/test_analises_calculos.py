"""Cálculos puros das análises de risco (ISSUE-074): recomendações atrasadas e taxa de fechadas.

Cada fórmula tem o caso de fronteira: prazo igual à referência não está atrasado, recomendação
fechada nunca está atrasada, sem recomendação emitida a taxa é vazia e o meio arredonda para cima.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.hse import calculations as calc

REFERENCIA = date(2026, 9, 25)


def test_prazo_igual_a_referencia_nao_esta_atrasado() -> None:
    assert not calc.is_recommendation_overdue("Aberta", date(2026, 9, 25), REFERENCIA)
    assert calc.is_recommendation_overdue("Aberta", date(2026, 9, 24), REFERENCIA)


def test_recomendacao_fechada_nunca_esta_atrasada() -> None:
    assert not calc.is_recommendation_overdue("Fechada", date(2026, 1, 1), REFERENCIA)


def test_count_recommendations_separa_abertas_atrasadas_e_fechadas() -> None:
    lines = [
        ("Aberta", date(2026, 9, 30)),
        ("Aberta", date(2026, 9, 25)),
        ("Aberta", date(2026, 9, 24)),
        ("Fechada", date(2026, 8, 1)),
    ]

    counts = calc.count_recommendations(lines, REFERENCIA)

    assert counts == calc.RecommendationCounts(issued=4, open=3, overdue=1, closed=1)


def test_count_recommendations_sem_linhas_zera_tudo() -> None:
    assert calc.count_recommendations([], REFERENCIA) == calc.RecommendationCounts()


def test_counts_somam_os_estudos() -> None:
    first = calc.RecommendationCounts(issued=3, open=2, overdue=1, closed=1)
    second = calc.RecommendationCounts(issued=2, open=0, overdue=0, closed=2)

    assert first.plus(second) == calc.RecommendationCounts(issued=5, open=2, overdue=1, closed=3)


def test_taxa_de_fechadas_sobre_emitidas() -> None:
    assert calc.recommendations_closed_rate(12, 25) == Decimal("48.0")
    assert calc.recommendations_closed_rate(9, 17) == Decimal("52.9")
    assert calc.recommendations_closed_rate(0, 2) == Decimal("0.0")
    assert calc.recommendations_closed_rate(2, 2) == Decimal("100.0")


def test_taxa_de_fechadas_com_o_meio_arredonda_para_cima() -> None:
    assert calc.recommendations_closed_rate(1, 8) == Decimal("12.5")
    assert calc.recommendations_closed_rate(1, 16) == Decimal("6.3")


def test_taxa_de_fechadas_sem_emitidas_e_vazia() -> None:
    assert calc.recommendations_closed_rate(0, 0) is None
