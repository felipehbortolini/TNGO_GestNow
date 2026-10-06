"""Fixtures dos testes do Planejamento.

Relato do período (ISSUE-044): rotas na transação do teste e projeto de teste (``sessao_das_rotas``,
``cenario``).

6WLA (ISSUE-045): a rota usa a sessão do teste e o relógio fica parado (``sessao``, ``cadastro``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from src.core import calendario, config, database
from src.core.auth import _user_of
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from tests.apoio_6wla import HOJE, Cadastro, montar_cadastro
from tests.identidades import criar_colaborador, criar_projeto


@dataclass(frozen=True)
class Cenario:
    """Um projeto iniciado há 60 dias e uma pessoa de cada perfil, na transação do teste."""

    session: Session
    project: Project
    scope: Scope
    visualizador: User
    membro: User
    gestor: User
    colaboradores: dict[str, int]


def _usuario(session: Session, email: str) -> User:
    acesso = configuracoes.find_access_by_email(session, email)
    if acesso is None:
        raise LookupError(email)
    return _user_of(acesso)


@pytest.fixture
def sessao_das_rotas(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """As rotas usam a sessão do teste, em modo demonstração."""

    @contextmanager
    def unidade_do_teste() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(database, "unidade_de_trabalho", unidade_do_teste)
    monkeypatch.delenv(config.APP_MODE_VARIABLE, raising=False)
    return db_session


@pytest.fixture
def cenario(sessao_das_rotas: Session) -> Cenario:
    """Projeto de teste (início há 60 dias) e colaboradores Visualizador, Membro e Gestor."""
    session = sessao_das_rotas
    projeto = criar_projeto(session, codigo="TN-RELATO-001", nome="Projeto do relato")
    projeto.start_date = calendario.today() - timedelta(days=60)
    session.flush()
    ids = {
        perfil: criar_colaborador(
            session, email=f"{perfil.lower()}@relato.example.invalid", perfil=perfil
        ).id
        for perfil in ("Visualizador", "Membro", "Gestor")
    }
    return Cenario(
        session=session,
        project=projeto,
        scope=Scope(project_id=projeto.id, source="url"),
        visualizador=_usuario(session, "visualizador@relato.example.invalid"),
        membro=_usuario(session, "membro@relato.example.invalid"),
        gestor=_usuario(session, "gestor@relato.example.invalid"),
        colaboradores=ids,
    )


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
