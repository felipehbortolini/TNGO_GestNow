"""Fixtures dos testes do Planejamento: a rota usa a sessão do teste e o relógio fica parado."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from src.core import calendario, config, database
from tests.apoio_6wla import HOJE, Cadastro, montar_cadastro


@pytest.fixture
def sessao(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """A sessão do teste, que as rotas usam no lugar da própria; demonstração; hoje 25/09/2026."""

    @contextmanager
    def unidade_do_teste() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(database, "unidade_de_trabalho", unidade_do_teste)
    monkeypatch.delenv(config.APP_MODE_VARIABLE, raising=False)
    monkeypatch.setattr(calendario, "today", lambda: HOJE)
    return db_session


@pytest.fixture
def cadastro(sessao: Session) -> Cadastro:
    """Dois projetos, uma empresa e uma pessoa de cada perfil, na transação do teste."""
    return montar_cadastro(sessao)
