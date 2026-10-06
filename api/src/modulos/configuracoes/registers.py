"""Read facade of the support registers other modules consume (D5, D10).

Configurações owns the registers of companies, people, locations and units. A module
that needs to list them or to name them (the Weekly Scheduling draws the selects of
its form and the names of its matrix from here) asks this facade and never reads the
tables. Everything here only reads: the writes of the registers are the facade of
Configurações itself (``service``). Nothing here reads the clock.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.modulos.configuracoes.models import (
    Collaborator,
    CollaboratorScheduleRole,
    Company,
    Location,
    Person,
    Project,
    Unit,
)

MEASURE_UNIT_KIND = "medida"


@dataclass(frozen=True)
class Option:
    """A register row as a select prints it: the id the form sends and the label a person reads."""

    id: int
    label: str


def list_companies(session: Session, *, only: int | None = None) -> list[Option]:
    """The companies by name; ``only`` cuts the list to one company (the supplier's own)."""
    statement = select(Company.id, Company.name).order_by(Company.name, Company.id)
    if only is not None:
        statement = statement.where(Company.id == only)
    return [Option(id=row.id, label=row.name) for row in session.execute(statement)]


def list_locations(session: Session, *, project_id: int) -> list[Option]:
    """The locations of the project by name."""
    statement = (
        select(Location.id, Location.name)
        .where(Location.project_id == project_id)
        .order_by(Location.name, Location.id)
    )
    return [Option(id=row.id, label=row.name) for row in session.execute(statement)]


def list_measure_units(session: Session) -> list[Option]:
    """The units of measure, labelled by their code (``kg``, ``m²``), by code."""
    statement = (
        select(Unit.id, Unit.code)
        .where(Unit.kind == MEASURE_UNIT_KIND)
        .order_by(Unit.code, Unit.id)
    )
    return [Option(id=row.id, label=row.code) for row in session.execute(statement)]


def list_people_with_role(
    session: Session, *, project_id: int, role: str, company_id: int | None = None
) -> list[Option]:
    """The active people who hold a Weekly Scheduling role in the project, by name.

    The id is the person's (``pessoa.id``), the one the records of the Weekly
    Scheduling point to. ``company_id`` keeps only the people of one company.
    """
    statement = (
        select(Person.id, Person.name)
        .join(Collaborator, Collaborator.person_id == Person.id)
        .join(CollaboratorScheduleRole, CollaboratorScheduleRole.collaborator_id == Collaborator.id)
        .where(
            CollaboratorScheduleRole.project_id == project_id,
            CollaboratorScheduleRole.role == role,
            Collaborator.active.is_(True),
        )
        .order_by(Person.name, Person.id)
    )
    if company_id is not None:
        statement = statement.where(Person.company_id == company_id)
    return [Option(id=row.id, label=row.name) for row in session.execute(statement)]


def company_names(session: Session, ids: Collection[int]) -> dict[int, str]:
    """The name of each company id."""
    return _pairs(session, ids, select(Company.id, Company.name).where(Company.id.in_(ids)))


def location_names(session: Session, ids: Collection[int]) -> dict[int, str]:
    """The name of each location id."""
    return _pairs(session, ids, select(Location.id, Location.name).where(Location.id.in_(ids)))


def unit_codes(session: Session, ids: Collection[int]) -> dict[int, str]:
    """The code of each unit id (``kg``, ``m²``)."""
    return _pairs(session, ids, select(Unit.id, Unit.code).where(Unit.id.in_(ids)))


def person_names(session: Session, ids: Collection[int]) -> dict[int, str]:
    """The name of each person id."""
    return _pairs(session, ids, select(Person.id, Person.name).where(Person.id.in_(ids)))


def project_labels(session: Session, ids: Collection[int]) -> dict[int, str]:
    """``TN-001 · Nome do projeto`` for each project id: how a project is named in the Portfólio."""
    if not ids:
        return {}
    statement = select(Project.id, Project.code, Project.name).where(Project.id.in_(ids))
    return {row.id: f"{row.code} · {row.name}" for row in session.execute(statement)}


def _pairs(session: Session, ids: Collection[int], statement: Select) -> dict[int, str]:
    """The ``(id, label)`` rows of the statement as a dict; nothing is asked when there are no ids."""
    if not ids:
        return {}
    return {int(row[0]): str(row[1]) for row in session.execute(statement)}
