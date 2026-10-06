"""Fixtures of the Weekly Scheduling tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from src.core import config, database
from tests.cenario_programacao import Scenario, build_scenario


@pytest.fixture
def scenario(db_session: Session) -> Scenario:
    """The project, the companies and the people of each role, inside the test transaction."""
    return build_scenario(db_session)


@pytest.fixture
def sessao_das_rotas(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """Routes use the session of the test, in demonstration mode."""

    @contextmanager
    def unidade_do_teste() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(database, "unidade_de_trabalho", unidade_do_teste)
    monkeypatch.delenv(config.APP_MODE_VARIABLE, raising=False)
    return db_session
