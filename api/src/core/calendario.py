"""The platform calendar: the only place that reads the clock (D6).

``today`` returns the date in the product's timezone and ``now`` the current
instant; every other function receives the date of reference as an argument,
so calculations are tested with an injected date and nothing else needs to
look at the clock. Weeks are ISO 8601 (Monday to Sunday, ``2026-S38``) and
months are civil (``2026-08``); a period carries its bounds, the cut date —
its end, limited to the date of reference — and the mark that it is still in
progress (partial).
"""

from __future__ import annotations

import calendar
import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

PRODUCT_TIMEZONE = ZoneInfo("America/Sao_Paulo")

WEEKLY = "Semanal"
MONTHLY = "Mensal"

# The prototype walked period by period with the same ceiling, so a bad label
# cannot make a list run away.
MAX_PERIODS = 600

_WEEK_LABEL = re.compile(r"^(\d{4})-S(\d{2})$")
_MONTH_LABEL = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def now() -> datetime:
    """The current instant in UTC, the timestamp the trail records."""
    return datetime.now(UTC)


def today() -> date:
    """Today in the product's timezone: the only source of "hoje" (D6)."""
    return datetime.now(PRODUCT_TIMEZONE).date()


def in_product_timezone(moment: datetime) -> datetime:
    """Convert an instant to the product's timezone, for display only."""
    return moment.astimezone(PRODUCT_TIMEZONE)


def iso_week(reference_date: date) -> str:
    """ISO week label of a date (``2026-S38``); week 1 holds the first Thursday."""
    year, week, _ = reference_date.isocalendar()
    return f"{year}-S{week:02d}"


def period_of(kind: str, reference_date: date) -> str:
    """Label of the period containing the date: ISO week or civil month."""
    if kind == WEEKLY:
        return iso_week(reference_date)
    return f"{reference_date.year}-{reference_date.month:02d}"


def valid_period(kind: str, label: str) -> bool:
    """Whether the label names a real period of the kind."""
    return period_bounds(kind, label) is not None


def period_bounds(kind: str, label: str) -> tuple[date, date] | None:
    """First and last day of the period, or ``None`` when the label is not valid."""
    if kind == WEEKLY:
        start = week_start(label)
        return (start, add_days(start, 6)) if start is not None else None
    if kind == MONTHLY:
        first = _month_start(label)
        return (first, _month_end(first)) if first is not None else None
    return None


def week_start(label: str) -> date | None:
    """The Monday of an ISO week label, or ``None`` when the label is not valid."""
    match = _WEEK_LABEL.fullmatch(label)
    if match is None:
        return None
    try:
        return date.fromisocalendar(int(match[1]), int(match[2]), 1)
    except ValueError:
        return None


def add_days(reference_date: date, days: int) -> date:
    """The date a number of days after (or before, when negative) the reference."""
    return reference_date + timedelta(days=days)


def add_periods(kind: str, label: str, count: int) -> str | None:
    """Walk ``count`` periods from the label; ``None`` when the label is not valid."""
    if kind == WEEKLY:
        start = week_start(label)
        if start is None:
            return None
        return iso_week(add_days(start, 7 * count))
    if kind == MONTHLY:
        first = _month_start(label)
        if first is None:
            return None
        month_index = first.year * 12 + first.month - 1 + count
        year, month = divmod(month_index, 12)
        return f"{year}-{month + 1:02d}"
    return None


def list_periods(kind: str, first: str, last: str) -> list[str]:
    """Every period of the kind from ``first`` to ``last``, in ascending order."""
    labels: list[str] = []
    label: str | None = first
    while label is not None and first <= label <= last and len(labels) < MAX_PERIODS:
        labels.append(label)
        label = add_periods(kind, label, 1)
    return labels


def project_periods(kind: str, start: date, reference_date: date) -> list[str]:
    """Periods from the project's start date up to the period of the reference date."""
    return list_periods(kind, period_of(kind, start), period_of(kind, reference_date))


def is_partial(kind: str, label: str, reference_date: date) -> bool:
    """Whether the period still contains the reference date: it comes out partial."""
    bounds = period_bounds(kind, label)
    return bounds is not None and bounds[0] <= reference_date <= bounds[1]


def cut_date(kind: str, label: str, reference_date: date) -> date | None:
    """The period's end, limited to the reference date: data is read up to here."""
    bounds = period_bounds(kind, label)
    return min(bounds[1], reference_date) if bounds is not None else None


def month_end(label: str) -> date | None:
    """The last day of a civil month label, or ``None`` when the label is not valid."""
    first = _month_start(label)
    return _month_end(first) if first is not None else None


def _month_start(label: str) -> date | None:
    match = _MONTH_LABEL.fullmatch(label)
    if match is None:
        return None
    return date(int(match[1]), int(match[2]), 1)


def _month_end(first: date) -> date:
    return first.replace(day=calendar.monthrange(first.year, first.month)[1])
