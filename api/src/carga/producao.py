"""Production start: an empty base with the first Admin (ISSUE-008, D6/D7).

The demonstration never runs here: the only fictional-free base is written —
the person and collaborator of the first Admin, whose e-mail comes from the
``GESTNOW_ADMIN_EMAIL`` environment variable, and version 1 of the initial
parameters. Running it again finds everything and writes nothing.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit
from src.core.errors import InvalidDataError
from src.modulos.configuracoes import service as config_service
from src.modulos.configuracoes.models import Collaborator, Person

ADMIN_PROFILE = "Admin"
TIMENOW_BOND = "Timenow"


def start(session: Session, *, reference_date: date, admin_email: str) -> None:
    """Write the minimum base of production, inside the caller's transaction."""
    collaborator = ensure_first_admin(session, email=admin_email)
    config_service.seed_initial_parameters(
        session, author_id=collaborator.id, effective_from=reference_date
    )


def ensure_first_admin(session: Session, *, email: str) -> Collaborator:
    """The Admin of the informed e-mail, creating person and collaborator when missing."""
    normalized = _normalize(email)
    person = session.scalars(select(Person).where(Person.email == normalized)).first()
    if person is None:
        return _create_admin(session, email=normalized)
    collaborator = session.scalars(
        select(Collaborator).where(Collaborator.person_id == person.id)
    ).first()
    if collaborator is None:
        collaborator = _link_admin(session, person_id=person.id)
    return collaborator


def _create_admin(session: Session, *, email: str) -> Collaborator:
    """Create person and collaborator before any author exists, then leave the trail."""
    person = Person(name=_display_name(email), email=email)
    session.add(person)
    session.flush()
    collaborator = _link_admin(session, person_id=person.id)
    audit.created(session, user_id=collaborator.id, entity=person.__tablename__, record=person)
    return collaborator


def _link_admin(session: Session, *, person_id: int) -> Collaborator:
    collaborator = Collaborator(
        person_id=person_id,
        general_profile=ADMIN_PROFILE,
        bond=TIMENOW_BOND,
    )
    session.add(collaborator)
    session.flush()
    audit.created(
        session,
        user_id=collaborator.id,
        entity=collaborator.__tablename__,
        record=collaborator,
    )
    return collaborator


def _normalize(email: str) -> str:
    text = (email or "").strip().lower()
    if "@" not in text or " " in text:
        raise InvalidDataError({"email": "Informe um e-mail válido em GESTNOW_ADMIN_EMAIL."})
    return text


def _display_name(email: str) -> str:
    return email.split("@", 1)[0]
