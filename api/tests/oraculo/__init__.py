"""Harness do teste-oráculo (D6, Q31, ISSUE-008).

A demonstração é carregada com a data do protótipo injetada em 25/09/2026,
sem deslocamento, num banco de teste; cada módulo registra aqui as suas
afirmações de número conhecido, e o teste em ``test_oraculo.py`` roda todas
de uma vez e cita a descrição da que falhar.

Enquanto a divergência está pendente de aceite (Q31), o módulo afirma o
número do protótipo; quando a diferença decorre de decisão já tomada na
spec, afirma o número da spec e cita a divergência registrada em
``docs/DIVERGENCIAS-DO-PROTOTIPO.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

# Data de referência fixa do protótipo (MOCK.referencia).
ORACLE_DATE = date(2026, 9, 25)


@dataclass(frozen=True)
class OracleContext:
    """O que cada afirmação recebe: a sessão do banco de teste e a data injetada."""

    session: Session
    reference_date: date


Check = Callable[[OracleContext], None]

_CHECKS: list[tuple[str, Check]] = []


def register_check(description: str, check: Check) -> None:
    """Registra uma afirmação de número conhecido, com a descrição que a identifica."""
    _CHECKS.append((description, check))


def registered_checks() -> list[tuple[str, Check]]:
    """As afirmações registradas, na ordem em que entraram."""
    return list(_CHECKS)
