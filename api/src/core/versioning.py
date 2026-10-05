"""Optimistic concurrency: the version the screen opened must still be current (D5).

Every editable record carries ``versao``. The screen sends the version it
opened; before writing, the facade locks the row and compares. A
mismatch means someone else saved first: the write is refused, and the
author and time of the last change come from the audit trail so the
message can name who changed it and when (409).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from src.core import audit, calendario
from src.core.errors import InvalidDataError, VersionConflictError

SEM_VESTIGIO = "Este registro foi alterado por outra pessoa. Recarregue para ver a versão atual"


class Versioned(Protocol):
    """A record the platform protects with the ``versao`` column (D5)."""

    __tablename__: str
    id: int
    version: int


def require(session: Session, record: Versioned, expected: int | str | None) -> None:
    """Lock the row, compare with the version the screen opened and refuse on mismatch."""
    session.refresh(record, with_for_update=True)
    if record.version != _expected(expected):
        raise VersionConflictError(_message(session, record))


def advance(record: Versioned) -> None:
    """Move the record to the next version, after the write is applied."""
    record.version += 1


def _expected(value: int | str | None) -> int:
    if value is None:
        raise InvalidDataError({"versao": "A versão do registro não foi informada."})
    try:
        return int(value)
    except ValueError:
        raise InvalidDataError({"versao": "A versão do registro não foi informada."}) from None


def _message(session: Session, record: Versioned) -> str:
    last = audit.last_change(session, entity=record.__tablename__, record_id=record.id)
    if last is None:
        return SEM_VESTIGIO
    author = audit.author_name(session, last.user_id) or "outra pessoa"
    return (
        f"Este registro foi alterado por {author} às {_display_time(last.occurred_at)}. "
        "Recarregue para ver a versão atual"
    )


def _display_time(moment: datetime) -> str:
    return calendario.in_product_timezone(moment).strftime("%d/%m/%Y %H:%M")
