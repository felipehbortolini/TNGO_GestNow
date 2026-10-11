"""Fixtures dos testes do Relatório Gerencial.

Análise do período (ISSUE-081): as rotas na transação do teste (``sessao_das_rotas``), um
projeto de teste com uma pessoa de cada perfil (``cenario``) e a demonstração carregada com a
data do protótipo (``demonstracao``), para os casos que precisam de desvios de verdade.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from src.core import calendario, config, database
from src.core.auth import _user_of
from src.core.rbac import GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from tests.identidades import criar_colaborador, criar_projeto
from tests.oraculo import OracleContext, harness

PROJECT_1 = "TN-2026-014"


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


@dataclass(frozen=True)
class Demonstracao:
    """A demonstração carregada na transação do teste, com o Admin e o projeto 1 à mão."""

    session: Session
    reference_date: date
    admin: User
    project_id: int


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
    projeto = criar_projeto(session, codigo="TN-ANALISE-001", nome="Projeto da análise")
    projeto.start_date = calendario.today() - timedelta(days=60)
    session.flush()
    ids = {
        perfil: criar_colaborador(
            session, email=f"{perfil.lower()}@analise.example.invalid", perfil=perfil
        ).id
        for perfil in ("Visualizador", "Membro", "Gestor")
    }
    return Cenario(
        session=session,
        project=projeto,
        scope=Scope(project_id=projeto.id, source="url"),
        visualizador=_usuario(session, "visualizador@analise.example.invalid"),
        membro=_usuario(session, "membro@analise.example.invalid"),
        gestor=_usuario(session, "gestor@analise.example.invalid"),
        colaboradores=ids,
    )


@pytest.fixture
def demonstracao(db_session: Session) -> Demonstracao:
    """A demonstração em 25/09/2026 e o Admin que enxerga tudo, para os casos com desvios."""
    context: OracleContext = harness.load_demonstration(db_session)
    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == GeneralProfile.ADMIN
    )
    project = next(
        item for item in configuracoes.list_projects(db_session) if item.code == PROJECT_1
    )
    return Demonstracao(
        session=db_session,
        reference_date=context.reference_date,
        admin=_user_of(admin),
        project_id=project.id,
    )
