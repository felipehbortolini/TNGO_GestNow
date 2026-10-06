"""Pure calculations for the Planning module.

The 6WLA rules (ISSUE-045) live here, one function per business rule. None of
them reads the clock: the reference date comes in as an argument (D6).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.core import calendario

# The horizon of the 6WLA: six weeks, the first two of them being the ones the
# Programação Semanal can still take (an open constraint there is a warning).
LOOKAHEAD_WEEKS = 6
SHORT_TERM_WEEKS = 2
DAYS_IN_WEEK = 7
# Monday to Saturday: the days the weekly schedule programs.
SCHEDULED_DAYS_IN_WEEK = 6

DEFAULT_CODE_PREFIX = "LA-"
CODE_DIGITS = 2
PERCENT = Decimal(100)
TWO_PLACES = Decimal("0.01")

_TRAILING_NUMBER = re.compile(r"(\d+)$")


@dataclass(frozen=True)
class LookaheadWeekInfo:
    """One week of the horizon: its position, its Monday and its ISO label (``S40``)."""

    index: int
    start: date
    label: str


@dataclass(frozen=True)
class ActivityCounts:
    """What the indicators read of an activity: the weeks it is planned in and its restrictions."""

    planned: tuple[bool, ...]
    total_constraints: int
    open_constraints: int
    overdue_constraints: int


@dataclass(frozen=True)
class LookaheadFigures:
    """The five indicators of the 6WLA, as the screen and the exports show them."""

    activities: int
    short_term_activities: int
    short_term_ready: int
    total_constraints: int
    open_constraints: int
    overdue_constraints: int
    removal_index: Decimal | None


def lookahead_window_start(reference_date: date) -> date:
    """Monday of the first week of the horizon: the week after the one holding the date.

    On 25/09/2026 (a Friday of S39) the horizon starts on 28/09/2026 (S40), as the prototype did.
    """
    current_monday = calendario.add_days(reference_date, -reference_date.weekday())
    return calendario.add_days(current_monday, DAYS_IN_WEEK)


def lookahead_weeks(reference_date: date) -> tuple[LookaheadWeekInfo, ...]:
    """The six weeks of the horizon for the reference date, in order."""
    first = lookahead_window_start(reference_date)
    weeks = []
    for index in range(LOOKAHEAD_WEEKS):
        start = calendario.add_days(first, DAYS_IN_WEEK * index)
        label = calendario.iso_week(start).rsplit("-", maxsplit=1)[-1]
        weeks.append(LookaheadWeekInfo(index=index, start=start, label=label))
    return tuple(weeks)


def constraint_is_open(removal_date: date | None) -> bool:
    """A restriction is open while it has no removal date."""
    return removal_date is None


def constraint_is_overdue(due_date: date, removal_date: date | None, reference_date: date) -> bool:
    """Open and with the needed date already past: the day of the date itself is not overdue."""
    return constraint_is_open(removal_date) and due_date < reference_date


def activity_is_ready(open_constraints: int) -> bool:
    """An activity is ready to be scheduled when it has no open restriction."""
    return open_constraints == 0


def has_open_constraint_in_short_term(planned: Sequence[bool], open_constraints: int) -> bool:
    """Planned in one of the first two weeks with an open restriction: it must not be scheduled."""
    return open_constraints > 0 and any(planned[:SHORT_TERM_WEEKS])


def week_at_risk(index: int, planned: Sequence[bool], open_constraints: int) -> bool:
    """The orange mark: a planned week of the short term while the activity has an open restriction."""
    return index < SHORT_TERM_WEEKS and planned[index] and open_constraints > 0


def activity_situation(open_constraints: int, overdue_constraints: int) -> str:
    """The situation of an activity: ``vencida``, ``com_restricao`` or ``pronta``."""
    if overdue_constraints:
        return "vencida"
    if open_constraints:
        return "com_restricao"
    return "pronta"


def removal_index(total_constraints: int, open_constraints: int) -> Decimal | None:
    """Removed restrictions over identified ones, in percentage points; ``None`` without any."""
    if total_constraints == 0:
        return None
    removed = Decimal(total_constraints - open_constraints)
    return (removed * PERCENT / Decimal(total_constraints)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )


def lookahead_figures(activities: Sequence[ActivityCounts]) -> LookaheadFigures:
    """The indicators of a set of activities: horizon, short-term readiness and restrictions."""
    short_term = [item for item in activities if any(item.planned[:SHORT_TERM_WEEKS])]
    total = sum(item.total_constraints for item in activities)
    opened = sum(item.open_constraints for item in activities)
    return LookaheadFigures(
        activities=len(activities),
        short_term_activities=len(short_term),
        short_term_ready=sum(1 for item in short_term if activity_is_ready(item.open_constraints)),
        total_constraints=total,
        open_constraints=opened,
        overdue_constraints=sum(item.overdue_constraints for item in activities),
        removal_index=removal_index(total, opened),
    )


def next_activity_code(existing_codes: Sequence[str]) -> str:
    """The next code of the project: the prefix of the first one and the highest number plus one."""
    prefix = DEFAULT_CODE_PREFIX
    if existing_codes:
        prefix = _TRAILING_NUMBER.sub("", existing_codes[0])
    highest = 0
    for code in existing_codes:
        found = _TRAILING_NUMBER.search(code)
        if found:
            highest = max(highest, int(found.group(1)))
    return f"{prefix}{highest + 1:0{CODE_DIGITS}d}"


def activity_span(planned: Sequence[bool], window_start: date) -> tuple[date, date] | None:
    """First and last day (Saturday included) of the planned weeks, or ``None`` when there is none."""
    indexes = [index for index, marked in enumerate(planned) if marked]
    if not indexes:
        return None
    start = calendario.add_days(window_start, DAYS_IN_WEEK * indexes[0])
    last_monday = calendario.add_days(window_start, DAYS_IN_WEEK * indexes[-1])
    return start, calendario.add_days(last_monday, SCHEDULED_DAYS_IN_WEEK - 1)
