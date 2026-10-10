"""Cálculos das Análises de risco do HSE (ISSUE-074, D6): o atraso e o indicador de fechamento.

A recomendação atrasada é a aberta com o prazo anterior à data de referência (o critério do
protótipo, ``analiseCalculada``); o indicador é fechadas ÷ emitidas, em percentual de uma casa,
sem valor quando nada foi emitido.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.hse import calculations

REFERENCIA = date(2026, 9, 25)


def _linha(situacao: str, prazo: date) -> calculations.RecommendationLine:
    return calculations.RecommendationLine(situation=situacao, due_date=prazo)


def test_recomendacao_atrasada_e_a_aberta_com_o_prazo_anterior_a_referencia() -> None:
    assert calculations.recommendation_overdue(_linha("Aberta", date(2026, 9, 24)), REFERENCIA)
    assert not calculations.recommendation_overdue(_linha("Aberta", REFERENCIA), REFERENCIA), (
        "o prazo no próprio dia ainda está no prazo"
    )
    assert not calculations.recommendation_overdue(
        _linha("Fechada", date(2026, 9, 1)), REFERENCIA
    ), "recomendação fechada não conta como atrasada"


def test_count_recommendations_conta_abertas_fechadas_e_atrasadas() -> None:
    linhas = (
        _linha("Aberta", date(2026, 9, 30)),
        _linha("Aberta", date(2026, 9, 10)),
        _linha("Fechada", date(2026, 8, 20)),
        _linha("Fechada", date(2026, 9, 26)),
    )

    counts = calculations.count_recommendations(linhas, REFERENCIA)

    assert (counts.open, counts.closed, counts.overdue, counts.total) == (2, 2, 1, 4)


def test_o_indicador_de_recomendacoes_fechadas_e_a_divisao_com_uma_casa() -> None:
    assert calculations.closed_recommendations_pct(9, 17) == Decimal("52.9"), (
        "as 9 de 17 do cenário do protótipo"
    )
    assert calculations.closed_recommendations_pct(1, 3) == Decimal("33.3"), (
        "uma casa, meio para cima"
    )
    assert calculations.closed_recommendations_pct(2, 2) == Decimal("100.0")
    assert calculations.closed_recommendations_pct(0, 0) is None, (
        "sem recomendações emitidas não há indicador"
    )
