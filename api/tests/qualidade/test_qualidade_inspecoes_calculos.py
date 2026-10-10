"""As fronteiras das inspeções (ISSUE-069): aprovação, notificação e pontos cobertos.

Funções puras, sem banco: a ressalva conta como aprovada, a taxa sai com uma casa (meio para
cima), a antecedência da notificação é em horas e o aviso segue a fronteira do parâmetro —
ausente avisa, menor avisa, exatamente o parâmetro passa.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from src.modulos.qualidade import calculations

REFERENCIA = date(2026, 9, 25)


def test_a_ressalva_conta_como_aprovada() -> None:
    assert calculations.approved_inspection("Aprovado") is True
    assert calculations.approved_inspection("Aprovado com ressalva") is True
    assert calculations.approved_inspection("Reprovado") is False


def test_a_taxa_de_aprovacao_sai_com_uma_casa() -> None:
    assert calculations.inspection_approval_rate([]) is None
    taxa = calculations.inspection_approval_rate(["Aprovado", "Aprovado com ressalva", "Reprovado"])
    assert taxa == Decimal("66.7")


def test_as_horas_da_notificacao() -> None:
    assert calculations.notification_hours(None, REFERENCIA) is None
    assert calculations.notification_hours(REFERENCIA - timedelta(days=2), REFERENCIA) == 48
    assert calculations.notification_hours(REFERENCIA, REFERENCIA) == 0


def test_o_aviso_da_notificacao_segue_a_fronteira_do_parametro() -> None:
    assert calculations.notification_warning("W", None, REFERENCIA, 48) == (
        "Ponto W sem registro da notificação ao cliente."
    )
    assert calculations.notification_warning(
        "W", REFERENCIA - timedelta(days=1), REFERENCIA, 48
    ) == ("Notificação ao cliente com antecedência menor que 48 horas.")
    assert (
        calculations.notification_warning("H", REFERENCIA - timedelta(days=2), REFERENCIA, 48)
        is None
    )
    assert calculations.notification_warning("R", None, REFERENCIA, 48) is None


def test_os_pontos_cobertos_contam_uma_vez() -> None:
    assert calculations.covered_points([]) == 0
    assert calculations.covered_points([1, 2, 2, None, 3]) == 3
