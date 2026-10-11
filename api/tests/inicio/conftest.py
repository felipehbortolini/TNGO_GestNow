"""Fixtures dos testes do Início (ISSUE-079).

As rotas rodam na transação do teste (``sessao_das_rotas``) em modo demonstração; o ``cenario``
cria um projeto de teste com uma pessoa de cada perfil (incluindo o Fornecedor, que não alcança
o módulo); a ``demonstracao`` carrega a base do protótipo com a data injetada em 25/09/2026, com
o Admin e o projeto 1 à mão para os casos de número conhecido.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import TypedDict

import pytest
from sqlalchemy.orm import Session

from src.core import config, database
from src.core.auth import _user_of
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from src.modulos.configuracoes.service import ProjectSummary
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto
from tests.oraculo import OracleContext, harness

PROJECT_1 = "TN-2026-014"


class _Perfis(TypedDict):
    """Os colaboradores do cenário por perfil, para o cookie do seletor da demonstração."""

    Visualizador: int
    Membro: int
    Gestor: int
    Fornecedor: int


@dataclass(frozen=True)
class Cenario:
    """Um projeto de teste e uma pessoa de cada perfil na transação do teste."""

    session: Session
    project: Project
    scope: Scope
    visualizador: User
    membro: User
    gestor: User
    fornecedor: User
    colaboradores: dict[str, int]


@dataclass(frozen=True)
class Demonstracao:
    """A demonstração carregada na transação do teste, com o Admin e o projeto 1 à mão."""

    session: Session
    reference_date: date
    admin: User
    project_id: int
    project: ProjectSummary


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
    """Projeto de teste e colaboradores Visualizador, Membro, Gestor e Fornecedor."""
    session = sessao_das_rotas
    projeto = criar_projeto(session, codigo="TN-INICIO-001", nome="Projeto do Início")
    empresa = criar_empresa(session, "Fornecedor do Início")
    perfis: _Perfis = {
        "Visualizador": criar_colaborador(
            session, email="visualizador@inicio.example.invalid", perfil="Visualizador"
        ).id,
        "Membro": criar_colaborador(
            session, email="membro@inicio.example.invalid", perfil="Membro"
        ).id,
        "Gestor": criar_colaborador(
            session, email="gestor@inicio.example.invalid", perfil="Gestor"
        ).id,
        "Fornecedor": criar_colaborador(
            session,
            email="fornecedor@inicio.example.invalid",
            perfil="Membro",
            vinculo="Fornecedor",
            empresa=empresa,
        ).id,
    }
    return Cenario(
        session=session,
        project=projeto,
        scope=Scope(project_id=projeto.id, source="url"),
        visualizador=_usuario(session, "visualizador@inicio.example.invalid"),
        membro=_usuario(session, "membro@inicio.example.invalid"),
        gestor=_usuario(session, "gestor@inicio.example.invalid"),
        fornecedor=_usuario(session, "fornecedor@inicio.example.invalid"),
        colaboradores=dict(perfis),
    )


@pytest.fixture
def demonstracao(db_session: Session) -> Demonstracao:
    """A demonstração em 25/09/2026 e o Admin que enxerga tudo, para os números conhecidos."""
    context: OracleContext = harness.load_demonstration(db_session)
    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    project = next(
        item for item in configuracoes.list_projects(db_session) if item.code == PROJECT_1
    )
    return Demonstracao(
        session=db_session,
        reference_date=context.reference_date,
        admin=_user_of(admin),
        project_id=project.id,
        project=project,
    )
