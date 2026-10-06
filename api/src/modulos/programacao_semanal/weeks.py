"""Week references of the Weekly Scheduling: ``S.30/2026``, Monday to Sunday (D10).

A week is written ``S.30/2026`` everywhere: interface, storage, spreadsheet. This
module is the only place of the Weekly Scheduling that builds one, reads one and
turns one into real dates. The ISO calendar is the source of truth: week 1 of a
year is the one that holds its first Thursday, and Monday opens the week. Nothing
here reads the clock: the caller passes the date (``core.calendario.today``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

WEEK_FORMAT = "S.{number:02d}/{year}"
DAYS_IN_WEEK = 7

# The ISO calendar of ``datetime`` only exists for these years.
_FIRST_YEAR = 1
_LAST_YEAR = 9998
_NO_PARTS = (0, 0)


def reference(year: int, number: int) -> str:
    """The canonical reference of a week: ``reference(2026, 30)`` is ``S.30/2026``."""
    return WEEK_FORMAT.format(number=number, year=year)


def parts(week: str) -> tuple[int, int]:
    """Split a reference into ``(year, number)``; ``(0, 0)`` when it cannot be read."""
    text = str(week)
    if "/" not in text:
        return _NO_PARTS
    head, tail = text.split("/", 1)
    number = "".join(char for char in head if char.isdigit())
    year = "".join(char for char in tail if char.isdigit())
    if not number or not year:
        return _NO_PARTS
    return (int(year), int(number))


def sort_key(week: str) -> tuple[int, int]:
    """The chronological sort key, right across the turn of a year."""
    return parts(week)


def weeks_in_year(year: int) -> int:
    """52 or 53, whichever the ISO calendar says for the year (2026 has 53)."""
    return date(year, 12, 28).isocalendar().week


def start(week: str) -> date | None:
    """The Monday of the week, or ``None`` when the reference is not a real week."""
    year, number = parts(week)
    if not _FIRST_YEAR <= year <= _LAST_YEAR or not number or number > weeks_in_year(year):
        return None
    return date.fromisocalendar(year, number, 1)


def end(week: str) -> date | None:
    """The Sunday of the week."""
    monday = start(week)
    return monday + timedelta(days=DAYS_IN_WEEK - 1) if monday else None


def is_valid(week: str) -> bool:
    """Whether the text names a real ISO week."""
    return start(week) is not None


def week_dates(week: str) -> list[date]:
    """The seven dates of the week, Monday first; empty when the reference is not real."""
    monday = start(week)
    if not monday:
        return []
    return [monday + timedelta(days=offset) for offset in range(DAYS_IN_WEEK)]


def period_label(week: str) -> str:
    """The range a person reads: ``20/07 a 26/07/2026``; empty when the reference is not real."""
    first, last = start(week), end(week)
    if not first or not last:
        return ""
    return f"{first.day:02d}/{first.month:02d} a {last.day:02d}/{last.month:02d}/{last.year}"


@dataclass(frozen=True)
class WeekInfo:
    """Everything a screen needs to draw one week reference."""

    id: str
    year: int
    number: int
    first_day: date | None
    last_day: date | None
    period: str
    valid: bool


def describe(week: str) -> WeekInfo:
    """The week as the filters and the headers print it."""
    first, last = start(week), end(week)
    year, number = parts(week)
    return WeekInfo(
        id=week,
        year=year,
        number=number,
        first_day=first,
        last_day=last,
        period=period_label(week),
        valid=first is not None,
    )


def of_date(day: date) -> str:
    """The reference of the week that holds a date."""
    iso = day.isocalendar()
    return reference(iso.year, iso.week)


def shift(week: str, steps: int) -> str:
    """Move ``steps`` weeks forward (positive) or back (negative); an unreadable one stays."""
    monday = start(week)
    if not monday:
        return week
    return of_date(monday + timedelta(weeks=steps))


def horizon(week: str, *, back: int = 5, ahead: int = 2) -> list[str]:
    """A contiguous run of weeks around one week, oldest first."""
    return [shift(week, step) for step in range(-back, ahead + 1)]
