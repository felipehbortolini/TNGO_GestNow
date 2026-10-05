"""Carrega a demonstração para o oráculo, com a data do protótipo injetada."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.carga import run_demonstration
from tests.oraculo import ORACLE_DATE, OracleContext


def load_demonstration(session: Session) -> OracleContext:
    """Carrega a demonstração sem deslocamento e devolve o contexto das afirmações."""
    run_demonstration(session, reference_date=ORACLE_DATE)
    return OracleContext(session=session, reference_date=ORACLE_DATE)
