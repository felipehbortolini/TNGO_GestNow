"""Fixtures dos testes das análises de risco: a transação do teste serve a toda rota e o cenário.

Mesmo desenho de ``tests/central_acoes/conftest.py``: a unidade de trabalho da rota é a sessão do
teste, no modo demonstração e com o relógio em 25/09/2026; nada sobrevive ao teste.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from src.core import calendario, config, database
from tests.apoio_acoes import REFERENCIA, Cenario, montar_cenario


@pytest.fixture
def sessao(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """A sessão do teste serve a toda rota, no modo demonstração, com o relógio em 25/09/2026."""

    @contextmanager
    def unidade_do_teste() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(database, "unidade_de_trabalho", unidade_do_teste)
    monkeypatch.delenv(config.APP_MODE_VARIABLE, raising=False)
    monkeypatch.setattr(calendario, "today", lambda: REFERENCIA)
    return db_session


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    """Dois projetos e cinco pessoas, um colaborador de cada perfil."""
    return montar_cenario(sessao)
