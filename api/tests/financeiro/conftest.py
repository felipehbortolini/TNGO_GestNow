"""Fixtures dos testes do Financeiro: rotas na transação do teste e um cenário de EAC.

``fragment_route`` abre a própria unidade de trabalho, que gravaria no ``gestnow_teste`` e não
veria nada do que o teste escreveu em ``db_session``. Aqui a unidade de trabalho é a sessão do
teste: a rota lê o que o teste criou e nada sobrevive a ele. O cenário tem dois projetos, o
projeto 1 com dois pacotes e três itens e o projeto 2 com um pacote e um item.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import config, database
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes.models import Collaborator, Person, Project, Unit
from src.modulos.financeiro import service
from src.modulos.financeiro.service import NewItem
from tests.identidades import criar_colaborador, criar_projeto

REFERENCE_DATE = date(2026, 9, 25)
MEMBER_EMAIL = "membro-eac@example.invalid"
VIEWER_EMAIL = "visualizador-eac@example.invalid"
MANAGER_EMAIL = "gestor-eac@example.invalid"


@dataclass(frozen=True)
class EacScenario:
    """Two projects with an EAC, the people who work on it and the ids of the items."""

    session: Session
    first: Project
    second: Project
    member: Collaborator
    viewer: Collaborator
    manager: Collaborator
    responsible: Person
    items: dict[str, int]


def user_of(collaborator: Collaborator, session: Session, profile: GeneralProfile) -> User:
    """The ``User`` the platform would build for the collaborator."""
    person = session.scalars(select(Person).where(Person.id == collaborator.person_id)).one()
    return User(
        id=collaborator.id,
        person_id=person.id,
        name=person.name,
        email=person.email,
        general_profile=profile,
        bond=Bond.TIMENOW,
    )


@pytest.fixture
def rotas_na_transacao(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """Every ``fragment_route`` and ``file_route`` uses the session of the test (demonstration)."""

    @contextmanager
    def unidade_do_teste() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(database, "unidade_de_trabalho", unidade_do_teste)
    monkeypatch.delenv(config.APP_MODE_VARIABLE, raising=False)
    return db_session


@pytest.fixture
def cenario(rotas_na_transacao: Session) -> EacScenario:
    """Project 1 (two packages, three items) and project 2 (one package, one item)."""
    session = rotas_na_transacao
    first = criar_projeto(session, codigo="TN-EAC-001", nome="Fábrica de teste")
    second = criar_projeto(session, codigo="TN-EAC-002", nome="Caldeira de teste")
    member = criar_colaborador(session, email=MEMBER_EMAIL, nome="Maria Membro", perfil="Membro")
    viewer = criar_colaborador(
        session, email=VIEWER_EMAIL, nome="Vera Visualizadora", perfil="Visualizador"
    )
    manager = criar_colaborador(session, email=MANAGER_EMAIL, nome="Gil Gestor", perfil="Gestor")
    responsible = session.scalars(select(Person).where(Person.id == member.person_id)).one()
    unit = Unit(kind="medida", code="un", name="Unidade")
    session.add(unit)
    session.flush()
    items: dict[str, int] = {}

    def add(project: Project, code: str, description: str, **fields: Any) -> None:
        parent_code = ".".join(code.split(".")[:-1])
        items[f"{project.code}:{code}"] = service.create_item(
            session,
            user_id=member.id,
            new=NewItem(
                project_id=project.id,
                code=code,
                description=description,
                level=len(code.split(".")),
                parent_id=items.get(f"{project.code}:{parent_code}"),
                **fields,
            ),
        )

    leaf = {
        "unit_id": unit.id,
        "responsible_id": responsible.id,
        "cost_type": "Serviço",
        "capex": True,
        "cost_center": "CC-1",
    }
    add(first, "1", "Engenharia")
    add(first, "1.1", "Projeto básico")
    add(first, "1.1.1", "Engenharia civil", quantity=Decimal(100), unit_price_cents=10_000, **leaf)
    add(
        first, "1.1.2", "Engenharia elétrica", quantity=Decimal("2.5"), unit_price_cents=400, **leaf
    )
    add(first, "2", "Suprimentos")
    add(first, "2.1", "Equipamentos")
    add(first, "2.1.1", "Bombas", quantity=Decimal(3), unit_price_cents=2_000_000, **leaf)
    add(second, "1", "Obra civil")
    add(second, "1.1", "Fundações")
    add(second, "1.1.1", "Estacas", quantity=Decimal(10), unit_price_cents=500_000, **leaf)
    return EacScenario(
        session=session,
        first=first,
        second=second,
        member=member,
        viewer=viewer,
        manager=manager,
        responsible=responsible,
        items=items,
    )
