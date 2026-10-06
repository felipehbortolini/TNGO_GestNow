"""Pure calculations for the Planning module.

Relato do período (ISSUE-044): the periods a report may cover, the ones still owed, the labels
a person reads and the rules that order and summarize the reports. Every function that needs
a date receives it as an argument (D6); nothing here reads the clock. The business names are
listed in ``LEIA-ME.md``.


The 6WLA rules (ISSUE-045) live here, one function per business rule. None of
them reads the clock: the reference date comes in as an argument (D6).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.core import calendario
from src.modulos.planejamento.validation import MONTHLY, OPPORTUNITY, THREAT, WEEKLY

MONTH_NAMES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


BEFORE_PROJECT_MESSAGE = "O período é anterior ao início do projeto."


NOT_STARTED_MESSAGE = "O período ainda não começou; registre a partir do período corrente."


PERIOD_REQUIRED_MESSAGE = "Escolha o período do relato."


DAYS_IN_WEEK = 7


MONTHS_IN_YEAR = 12


MONTH_ABBREVIATION_LENGTH = 3


@dataclass(frozen=True)
class PeriodOption:
    """One period the form offers: its label, whether it is under way and whether it has a report."""

    period: str
    label: str
    in_progress: bool
    taken: bool


def report_period_range(
    kind: str, project_start: date | None, reference_date: date
) -> tuple[str, str]:
    """First and last period a report may cover: from the project's start to the current one.

    A project with no start date registered is read as starting on the reference date.
    """
    first = calendario.period_of(kind, project_start or reference_date)
    return first, calendario.period_of(kind, reference_date)


def report_period_error(
    kind: str, period: str, *, project_start: date | None, reference_date: date
) -> str | None:
    """The message for the period field, or ``None`` when the period may hold a report.

    A period before the project started is refused, and so is a future one: the first period
    that may be reported is the current one.
    """
    if not calendario.valid_period(kind, period):
        return PERIOD_REQUIRED_MESSAGE
    first, last = report_period_range(kind, project_start, reference_date)
    if period < first:
        return BEFORE_PROJECT_MESSAGE
    if period > last:
        return NOT_STARTED_MESSAGE
    return None


def expected_report_count(kind: str, project_start: date | None, reference_date: date) -> int:
    """Reports owed by a project: the periods already closed since it started.

    The current period is under way and is not owed yet, so it is left out.
    """
    first, last = report_period_range(kind, project_start, reference_date)
    return max(0, len(calendario.list_periods(kind, first, last)) - 1)


def previous_period(kind: str, reference_date: date) -> str:
    """The last closed period before the one that holds the reference date."""
    current = calendario.period_of(kind, reference_date)
    return calendario.add_periods(kind, current, -1) or current


def next_period(kind: str, period: str) -> str | None:
    """The period right after the given one, or ``None`` when the label is not valid."""
    return calendario.add_periods(kind, period, 1)


def period_name(kind: str, period: str) -> str:
    """The period as a person reads it: ``Semana 38 · 14/09 a 20/09/2026`` or ``Agosto de 2026``."""
    bounds = calendario.period_bounds(kind, period)
    if bounds is None:
        return period
    if kind == WEEKLY:
        number = int(period.split("-S")[1])
        return f"Semana {number} · {bounds[0]:%d/%m} a {bounds[1]:%d/%m/%Y}"
    return f"{MONTH_NAMES[bounds[0].month - 1]} de {bounds[0].year}"


def short_period_name(kind: str, period: str) -> str:
    """The short label of a period: ``S38`` for a week, ``ago/26`` for a month."""
    bounds = calendario.period_bounds(kind, period)
    if bounds is None:
        return period
    if kind == WEEKLY:
        return f"S{int(period.split('-S')[1]):02d}"
    month = MONTH_NAMES[bounds[0].month - 1][:MONTH_ABBREVIATION_LENGTH].lower()
    return f"{month}/{bounds[0].year % 100:02d}"


def period_options(
    kind: str,
    *,
    project_start: date | None,
    reference_date: date,
    taken: Iterable[str],
) -> list[PeriodOption]:
    """The periods of the kind for the form, the most recent first, with the ones already reported."""
    first, last = report_period_range(kind, project_start, reference_date)
    already = set(taken)
    return [
        PeriodOption(
            period=period,
            label=period_name(kind, period),
            in_progress=calendario.is_partial(kind, period, reference_date),
            taken=period in already,
        )
        for period in reversed(calendario.list_periods(kind, first, last))
    ]


def first_free_period(options: Sequence[PeriodOption]) -> str:
    """The most recent period with no report yet (the current one, if it is free), or empty."""
    return next((option.period for option in options if not option.taken), "")


def choose_period(options: Sequence[PeriodOption], requested: str) -> str:
    """The period the form selects: the one asked for, if it is free, or else the first free one."""
    free = {option.period for option in options if not option.taken}
    return requested if requested in free else first_free_period(options)


def report_order_key(kind: str, period: str) -> tuple[int, int]:
    """Sort key of the list: the most recent period first, the monthly before the weekly on a tie."""
    bounds = calendario.period_bounds(kind, period)
    start = bounds[0].toordinal() if bounds is not None else 0
    return -start, 0 if kind == MONTHLY else 1


def latest_period_before(periods: Iterable[str], period: str) -> str | None:
    """The most recent of the periods that comes before the given one, or ``None`` when none does.

    It is the report that "Copiar do período anterior" brings: not necessarily the period right
    before, but the latest one already reported.
    """
    earlier = [candidate for candidate in periods if candidate < period]
    return max(earlier, default=None)


def nature_counts(natures: Iterable[str]) -> tuple[int, int]:
    """How many attention points are threats and how many are opportunities."""
    kept = list(natures)
    return kept.count(THREAT), kept.count(OPPORTUNITY)


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """The count with its noun: ``1 ameaça``, ``2 ameaças``; the plural defaults to an ``s``."""
    noun = singular if count == 1 else (plural_form or f"{singular}s")
    return f"{count} {noun}"


def points_summary(threats: int, opportunities: int) -> str:
    """The attention points of a report in words: ``2 ameaças · 1 oportunidade``."""
    return f"{plural(threats, 'ameaça')} · {plural(opportunities, 'oportunidade')}"


def period_offset(kind: str, *, anchor: date, reference_date: date) -> int:
    """How many periods the period of the reference date is after the period of the anchor date."""
    anchor_label = calendario.period_of(kind, anchor)
    reference_label = calendario.period_of(kind, reference_date)
    if kind == WEEKLY:
        anchor_start = calendario.week_start(anchor_label)
        reference_start = calendario.week_start(reference_label)
        if anchor_start is None or reference_start is None:
            return 0
        return (reference_start - anchor_start).days // DAYS_IN_WEEK
    return (reference_date.year * MONTHS_IN_YEAR + reference_date.month) - (
        anchor.year * MONTHS_IN_YEAR + anchor.month
    )


def shift_period(kind: str, period: str, *, anchor: date, reference_date: date) -> str:
    """Move a period of the prototype to the run of the load, whole periods at a time.

    The demonstration keeps the scenario's coherence: the last closed week and month of the
    prototype stay the last closed week and month of the day the load runs. With the reference
    date equal to the anchor nothing moves.
    """
    count = period_offset(kind, anchor=anchor, reference_date=reference_date)
    return calendario.add_periods(kind, period, count) or period


# The horizon of the 6WLA: six weeks, the first two of them being the ones the
# Programação Semanal can still take (an open constraint there is a warning).
LOOKAHEAD_WEEKS = 6


SHORT_TERM_WEEKS = 2


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
