"""Append-only audit trail: who changed what, when, before and after (D5b).

One row per change, written inside the same transaction as the change it
describes: a rolled-back save leaves no trail, and a committed save
always leaves one. The database refuses UPDATE and DELETE on the table
(migration 0002), so the trail is append-only for real and not by
convention.

The before/after snapshots are keyed by column name, not attribute name:
the trail is read by people and by BI, and both know the table's
Portuguese names (D5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from src.core.models import AuditEntry

CREATED = "criado"
UPDATED = "alterado"
DELETED = "excluido"


@dataclass(frozen=True)
class TrailLine:
    """One trail row before it becomes an ``AuditEntry``."""

    user_id: int
    entity: str
    record_id: int
    action: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    project_id: int | None = None
    occurred_at: datetime | None = None


def append(session: Session, line: TrailLine) -> AuditEntry:
    """Add the trail row to the session's transaction and return it."""
    entry = AuditEntry(
        project_id=line.project_id,
        user_id=line.user_id,
        occurred_at=line.occurred_at or datetime.now(UTC),
        entity=line.entity,
        record_id=line.record_id,
        action=line.action,
        before=line.before,
        after=line.after,
    )
    session.add(entry)
    return entry


def snapshot(record: object) -> dict[str, Any]:
    """The record's columns as a JSON-safe dict keyed by column name."""
    mapper = inspect(type(record))
    if mapper is None:
        message = "O registro não é um modelo mapeado."
        raise TypeError(message)
    return {
        attribute.columns[0].name: _json_value(getattr(record, attribute.key))
        for attribute in mapper.column_attrs
    }


def created(session: Session, *, user_id: int, entity: str, record: object) -> AuditEntry:
    """Trail line of an insertion: nothing before, the record after."""
    return append(
        session,
        TrailLine(
            user_id=user_id,
            entity=entity,
            record_id=_record_id(record),
            action=CREATED,
            after=snapshot(record),
            project_id=_project_id(record),
        ),
    )


def changed(
    session: Session,
    *,
    user_id: int,
    entity: str,
    record: object,
    before: dict[str, Any],
) -> AuditEntry:
    """Trail line of an update: the snapshot taken before, the record after."""
    return append(
        session,
        TrailLine(
            user_id=user_id,
            entity=entity,
            record_id=_record_id(record),
            action=UPDATED,
            before=before,
            after=snapshot(record),
            project_id=_project_id(record),
        ),
    )


def deleted(
    session: Session,
    *,
    user_id: int,
    entity: str,
    record: object,
    before: dict[str, Any],
) -> AuditEntry:
    """Trail line of a removal: the snapshot taken before, nothing after."""
    return append(
        session,
        TrailLine(
            user_id=user_id,
            entity=entity,
            record_id=_record_id(record),
            action=DELETED,
            before=before,
            project_id=_project_id(record),
        ),
    )


def last_change(session: Session, *, entity: str, record_id: int) -> AuditEntry | None:
    """The most recent trail line of one record, or ``None`` if it has none."""
    statement = (
        select(AuditEntry)
        .where(AuditEntry.entity == entity, AuditEntry.record_id == record_id)
        .order_by(AuditEntry.occurred_at.desc(), AuditEntry.id.desc())
        .limit(1)
    )
    return session.scalars(statement).first()


def author_name(session: Session, user_id: int) -> str:
    """Name of the collaborator who wrote a trail line, read from the register (D7)."""
    from src.modulos.configuracoes.models import Collaborator, Person

    statement = (
        select(Person.name)
        .join(Collaborator, Collaborator.person_id == Person.id)
        .where(Collaborator.id == user_id)
    )
    return session.scalar(statement) or ""


def _record_id(record: object) -> int:
    record_id = getattr(record, "id", None)
    if record_id is None:
        message = "O registro precisa estar gravado (flush) antes da trilha."
        raise ValueError(message)
    return int(record_id)


def _project_id(record: object) -> int | None:
    project_id = getattr(record, "project_id", None)
    return int(project_id) if project_id is not None else None


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)
