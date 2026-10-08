"""As fórmulas puras do cadastro de fornecedores (ISSUE-057): a tabela de casos e as fronteiras.

A data de referência é sempre argumento; a fronteira de cada regra é o dia exato: um documento
vence no dia seguinte à validade e o alerta conta o próprio dia do limite (30 dias do documento,
90 da qualificação).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.modulos.suprimentos import calculations

REFERENCIA = date(2026, 9, 25)


# ── Documento vencido e a vencer ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("days", "expired", "expiring"),
    [
        (-1, True, False),
        (0, False, True),
        (1, False, True),
        (30, False, True),
        (31, False, False),
    ],
)
def test_documento_contra_a_data_de_referencia(days: int, *, expired: bool, expiring: bool) -> None:
    validity = REFERENCIA + timedelta(days=days)

    assert calculations.document_is_expired(validity, REFERENCIA) is expired
    assert calculations.document_is_expiring(validity, REFERENCIA) is expiring


def test_documento_sem_validade_nao_vence() -> None:
    assert calculations.document_is_expired(None, REFERENCIA) is False
    assert calculations.document_is_expiring(None, REFERENCIA) is False


def test_o_alerta_do_documento_muda_com_o_parametro() -> None:
    validity = REFERENCIA + timedelta(days=10)

    assert calculations.document_is_expiring(validity, REFERENCIA, days=10) is True
    assert calculations.document_is_expiring(validity, REFERENCIA, days=9) is False


# ── Qualificação vencida e a vencer ──────────────────────────────────────


@pytest.mark.parametrize(
    ("days", "expired", "expiring"),
    [
        (-1, True, False),
        (0, False, True),
        (90, False, True),
        (91, False, False),
    ],
)
def test_qualificacao_contra_a_data_de_referencia(
    days: int, *, expired: bool, expiring: bool
) -> None:
    validity = REFERENCIA + timedelta(days=days)

    assert calculations.qualification_is_expired(validity, REFERENCIA) is expired
    assert calculations.qualification_is_expiring(validity, REFERENCIA) is expiring


def test_qualificacao_sem_validade_nao_vence() -> None:
    assert calculations.qualification_is_expired(None, REFERENCIA) is False
    assert calculations.qualification_is_expiring(None, REFERENCIA) is False


# ── Documentos em dia ────────────────────────────────────────────────────


def test_documentos_em_dia_ignora_o_vencido() -> None:
    assert calculations.documents_up_to_date([], REFERENCIA) is True
    assert calculations.documents_up_to_date([None, REFERENCIA], REFERENCIA) is True
    assert (
        calculations.documents_up_to_date([REFERENCIA, REFERENCIA - timedelta(days=1)], REFERENCIA)
        is False
    )


# ── A classe da avaliação final leva a situação ──────────────────────────


@pytest.mark.parametrize(
    ("score_class", "situation"),
    [
        ("A", calculations.QUALIFIED),
        ("B", calculations.QUALIFIED),
        ("C", calculations.RESTRICTED),
        ("D", calculations.BLOCKED),
        ("a", calculations.QUALIFIED),
        ("E", None),
        ("", None),
        (None, None),
    ],
)
def test_situacao_da_classe_da_avaliacao(score_class: str | None, situation: str | None) -> None:
    assert calculations.situation_for_evaluation_class(score_class) == situation


# ── Justificativa da mudança ─────────────────────────────────────────────


def test_justificativa_so_e_exigida_na_mudanca() -> None:
    assert calculations.justification_is_required(None, "Qualificado") is False
    assert calculations.justification_is_required("Qualificado", "Qualificado") is False
    assert calculations.justification_is_required("Qualificado", "Restrito") is True


# ── Nota média ───────────────────────────────────────────────────────────


def test_nota_media_arredonda_meio_para_cima() -> None:
    assert calculations.average_score([]) is None
    assert calculations.average_score([5]) == Decimal("5.0")
    assert calculations.average_score([4, 4, 3]) == Decimal("3.7")
    assert calculations.average_score([1, 2]) == Decimal("1.5")
