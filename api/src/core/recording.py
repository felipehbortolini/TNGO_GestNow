"""The single way a facade writes an editable record (D5, D5b).

``create``, ``update`` and ``delete`` do four things together, inside the
caller's transaction: snapshot the record, enforce the version the screen
opened, apply the change and append the audit line. The entity in the
trail is the record's table name, so the trail speaks the same Portuguese
as the database (D5). A facade that needs more than this (an aggregate
with children, an integration between modules) composes ``audit`` and
``versioning`` directly — inside the same unit of work the route opened.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from src.core import audit, versioning
from src.core.versioning import Versioned


def create(session: Session, *, user_id: int, record: Versioned) -> Versioned:
    """Insert the record, flush it and leave the trail line of creation."""
    session.add(record)
    session.flush()
    audit.created(session, user_id=user_id, entity=record.__tablename__, record=record)
    return record


def update(
    session: Session,
    *,
    user_id: int,
    record: Versioned,
    changes: Mapping[str, Any],
    version: int | str | None,
) -> Versioned:
    """Apply the fields, after the version check, and leave the trail with before and after."""
    before = audit.snapshot(record)
    versioning.require(session, record, version)
    for attribute, value in changes.items():
        setattr(record, attribute, value)
    versioning.advance(record)
    session.flush()
    audit.changed(
        session, user_id=user_id, entity=record.__tablename__, record=record, before=before
    )
    return record


def delete(
    session: Session,
    *,
    user_id: int,
    record: Versioned,
    version: int | str | None,
) -> Versioned:
    """Remove the record, after the version check, and leave the trail of removal."""
    before = audit.snapshot(record)
    versioning.require(session, record, version)
    session.delete(record)
    session.flush()
    audit.deleted(
        session, user_id=user_id, entity=record.__tablename__, record=record, before=before
    )
    return record
