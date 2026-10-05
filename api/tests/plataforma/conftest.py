"""Fixtures of the platform route tests: routes inside the test transaction, and two projects.

``fragment_route`` opens its own unit of work, which would commit to
``gestnow_teste`` and see none of what a test wrote in ``db_session``. Here the
unit of work is replaced by the test's session, so the route reads the
projects the test created and nothing outlives the test.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from src.core import database
from src.core.models import Client
from src.modulos.configuracoes.models import Person, Project


@pytest.fixture
def rotas_na_transacao_do_teste(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """Make every ``fragment_route`` use the session of the test instead of its own."""

    @contextmanager
    def unidade_do_teste() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(database, "unidade_de_trabalho", unidade_do_teste)
    return db_session


def criar_projeto(session: Session, *, codigo: str, nome: str) -> Project:
    """A project of the register, with the client and manager it requires."""
    cliente = Client(name=f"Cliente {codigo}", active=True)
    gerente = Person(name=f"Gerente {codigo}", email=f"gerente-{codigo.lower()}@example.invalid")
    session.add_all([cliente, gerente])
    session.flush()
    projeto = Project(client_id=cliente.id, manager_id=gerente.id, code=codigo, name=nome)
    session.add(projeto)
    session.flush()
    return projeto


@pytest.fixture
def dois_projetos(rotas_na_transacao_do_teste: Session) -> tuple[Project, Project]:
    """Two projects, created inside the test transaction."""
    fabrica = criar_projeto(
        rotas_na_transacao_do_teste, codigo="TN-TESTE-001", nome="Construção de uma nova fábrica"
    )
    caldeira = criar_projeto(
        rotas_na_transacao_do_teste, codigo="TN-TESTE-002", nome="Construção de uma nova caldeira"
    )
    return fabrica, caldeira
