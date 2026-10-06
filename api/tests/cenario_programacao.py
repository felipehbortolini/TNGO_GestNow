"""Scenario of the Weekly Scheduling tests: one project, two companies and the people of each role."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, ScheduleRole, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as registers
from src.modulos.configuracoes.models import Collaborator, Company, Person
from src.modulos.programacao_semanal import service
from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.service import Caller
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto

WEEK = "S.31/2026"
# Friday 24/07/2026, 10:00 in São Paulo (13:00 UTC): inside a 08:00-15:00 Friday window.
FRIDAY_MORNING = datetime(2026, 7, 24, 13, 0, tzinfo=UTC)
# Saturday 25/07/2026, 10:00 in São Paulo: not the supplier's weekday.
SATURDAY_MORNING = datetime(2026, 7, 25, 13, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Scenario:
    """The project, two companies, the registers and one user per way of arriving."""

    session: Session
    project_id: int
    other_project_id: int
    company_a: int
    company_b: int
    location_id: int
    unit_id: int
    foreman_a: int
    foreman_b: int
    author_id: int
    planner: User
    supplier_a: User
    supplier_b: User
    viewer: User

    def caller(self, user: User, *, project: bool = True, now: datetime = FRIDAY_MORNING) -> Caller:
        """The facade's ``Caller``: in the project, or in the Portfólio."""
        scope = Scope(project_id=self.project_id if project else None, source="url")
        return Caller(user=user, scope=scope, now=now)


def _user(collaborator: Collaborator, person: Person, roles: set[tuple[int, ScheduleRole]]) -> User:
    return User(
        id=collaborator.id,
        person_id=person.id,
        name=person.name,
        email=person.email,
        general_profile=GeneralProfile(collaborator.general_profile),
        bond=Bond(collaborator.bond),
        company_id=collaborator.company_id,
        schedule_roles=frozenset(roles),
    )


def _supplier(session: Session, email: str, project_id: int, company_obj: Company) -> User:
    collaborator = criar_colaborador(
        session,
        email=email,
        perfil="Membro",
        vinculo="Fornecedor",
        empresa=company_obj,
        papeis=[(project_id, "Fornecedor")],
    )
    person = session.get(Person, collaborator.person_id)
    return _user(collaborator, person, {(project_id, ScheduleRole.SUPPLIER)})


def build_scenario(db_session: Session) -> Scenario:
    """A project with a window open on Fridays for company A and none for company B."""
    project = criar_projeto(db_session, codigo="PS-1", nome="Projeto da programação")
    other = criar_projeto(db_session, codigo="PS-2", nome="Outro projeto")
    company_a = criar_empresa(db_session, "Empresa A")
    company_b = criar_empresa(db_session, "Empresa B")
    admin = criar_colaborador(db_session, email="ps-admin@example.invalid", perfil="Admin")
    planner_c = criar_colaborador(
        db_session, email="ps-plan@example.invalid", papeis=[(project.id, "Planejador")]
    )
    viewer_c = criar_colaborador(db_session, email="ps-view@example.invalid", perfil="Visualizador")
    author = admin.id
    location = registers.ensure_location(
        db_session, author_id=author, project_id=project.id, name="Frente 1"
    )
    unit = registers.ensure_measure_unit(db_session, author_id=author, code="m", name="m")
    foreman_a = _foreman(db_session, project.id, company_a, "ps-enc-a@example.invalid")
    foreman_b = _foreman(db_session, project.id, company_b, "ps-enc-b@example.invalid")
    friday = window_rules.WindowDay(weekday=5, opens=time(8, 0), closes=time(15, 0))
    service.store_window(
        db_session,
        author_id=author,
        project_id=project.id,
        rules=window_rules.Window(company_id=company_a.id, days=(friday,), weeks=frozenset({WEEK})),
    )
    return Scenario(
        session=db_session,
        project_id=project.id,
        other_project_id=other.id,
        company_a=company_a.id,
        company_b=company_b.id,
        location_id=location,
        unit_id=unit,
        foreman_a=foreman_a,
        foreman_b=foreman_b,
        author_id=author,
        planner=_user(
            planner_c,
            db_session.get(Person, planner_c.person_id),
            {(project.id, ScheduleRole.PLANNER)},
        ),
        supplier_a=_supplier(db_session, "ps-forn-a@example.invalid", project.id, company_a),
        supplier_b=_supplier(db_session, "ps-forn-b@example.invalid", project.id, company_b),
        viewer=_user(viewer_c, db_session.get(Person, viewer_c.person_id), set()),
    )


def _foreman(session: Session, project_id: int, company: Company, email: str) -> int:
    collaborator = criar_colaborador(
        session,
        email=email,
        vinculo="Fornecedor",
        empresa=company,
        papeis=[(project_id, "Encarregado")],
    )
    return collaborator.person_id
