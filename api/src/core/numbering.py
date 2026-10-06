"""Project numbering: one sequence per project and kind, locked by row (D5).

``next_number`` reserves the next value inside the caller's transaction:
the row lock serialises concurrent reservations, and because the value is
written in the same transaction, a rollback returns the number to the
pool — no gap left by concurrency. The format follows the project's
standard pattern (``SM-TN-2026-0001``), the same the prototype printed.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.core.models import NumberingSequence


class NumberedProject(Protocol):
    """The project fields the numbering reads: identity and standard patterns."""

    id: int
    ata_pattern: str | None
    risk_pattern: str | None
    punch_pattern: str | None


# kind -> (prefix template, digits). ``ata``, ``risco`` and ``punch`` read
# the project's patterns; the others follow the prototype's prefixes, with
# the year for pedido and contrato and three digits as the prototype used.
KINDS: dict[str, tuple[str, int]] = {
    "ata": ("{ata}", 4),
    "mudanca": ("SM-{ata}", 4),
    "risco": ("{risco}", 4),
    "punch": ("{punch}", 4),
    "rnc": ("RNC-{ata}", 4),
    "claim": ("CLM-{ata}", 4),
    "eot": ("EOT-{ata}", 4),
    "licao": ("LA-{ata}", 4),
    "pedido": ("PED-{ano}", 3),
    "contrato": ("CT-{ano}", 3),
}


def next_number(
    session: Session,
    *,
    project: NumberedProject,
    kind: str,
    reference_date: date,
) -> str:
    """Reserve and format the next number of ``kind`` for the project."""
    prefix, digits = _prefix(project, kind, reference_date)
    row = _locked_row(session, project.id, kind)
    number = row.next_value
    row.next_value = number + 1
    session.flush()
    return f"{prefix}-{number:0{digits}d}"


def start_after(session: Session, *, project: NumberedProject, kind: str, last_number: int) -> None:
    """Make the next number of ``kind`` come after ``last_number``; the sequence never goes back.

    For the load of the demonstration, whose records arrive already numbered: the first number a
    person generates continues the series instead of colliding with it.
    """
    row = _locked_row(session, project.id, kind)
    row.next_value = max(row.next_value, last_number + 1)
    session.flush()


def _prefix(project: NumberedProject, kind: str, reference_date: date) -> tuple[str, int]:
    template, digits = KINDS[kind]
    ata = project.ata_pattern or f"TN-{reference_date.year}"
    risco = project.risk_pattern or "RSK"
    punch = project.punch_pattern or "PL"
    return template.format(ata=ata, risco=risco, punch=punch, ano=reference_date.year), digits


def _locked_row(session: Session, project_id: int, kind: str) -> NumberingSequence:
    """The project's sequence row, created if missing and locked for update.

    The insert is ``ON CONFLICT DO NOTHING`` so two first-time reservations
    do not race: the second waits for the first to commit and then locks
    the row it created.
    """
    statement = (
        select(NumberingSequence)
        .where(NumberingSequence.project_id == project_id, NumberingSequence.kind == kind)
        .with_for_update()
    )
    row = session.scalars(statement).one_or_none()
    if row is None:
        session.execute(
            pg_insert(NumberingSequence)
            .values(project_id=project_id, kind=kind, next_value=1)
            .on_conflict_do_nothing(
                index_elements=[NumberingSequence.project_id, NumberingSequence.kind]
            )
        )
        row = session.scalars(statement).one()
    return row
