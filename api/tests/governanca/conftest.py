"""Fixtures dos testes de Governança: as rotas rodam dentro da transação do teste, em demonstração.

``fragment_route`` abre a própria unidade de trabalho, que gravaria em ``gestnow_teste`` sem enxergar
o que o teste escreveu em ``db_session``. Aqui a unidade de trabalho é a sessão do teste, de modo que a
rota lê os projetos e as pessoas que o teste criou e nada sobrevive a ele. O dia de hoje é fixo.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from src.core import calendario, config, database
from tests.governanca.apoio import HOJE


@pytest.fixture
def sessao(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """A sessão do teste, usada também pelas rotas; modo demonstração e o dia de hoje fixo."""

    @contextmanager
    def unidade_do_teste() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(database, "unidade_de_trabalho", unidade_do_teste)
    monkeypatch.delenv(config.APP_MODE_VARIABLE, raising=False)
    monkeypatch.setattr(calendario, "today", lambda: HOJE)
    return db_session
