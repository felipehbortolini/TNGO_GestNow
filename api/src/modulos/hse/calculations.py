"""Pure calculations for the HSE module: HHT summary, proactive rates and the labour histogram.

Every rule is one function with its business name, and the reference date is always an argument:
nothing here reads the clock (D6). A month is the first day of the civil month; its label is
``2026-09``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

PERCENT = Decimal(100)
TEN_THOUSAND = Decimal(10000)
# The histogram factor is limited to this band (prototype ``histogramaMaoDeObra``).
FACTOR_FLOOR = 0.85
FACTOR_CEILING = 1.2
# The planned hours are rounded to hundreds, the planned headcount to units.
HOURS_ROUNDING = 100


def month_of(value: date) -> date:
    """The first day of the civil month of the date: how a month is stored."""
    return value.replace(day=1)


def month_label(month: date) -> str:
    """``2026-09``: the label of a month, the key the curves and the exports use."""
    return f"{month.year:04d}-{month.month:02d}"


def parse_month(label: str | None) -> date | None:
    """The first day of the month named by ``AAAA-MM``, or ``None`` when it is not a real month."""
    text = (label or "").strip()
    if len(text) != len("2026-09") or text[4] != "-":
        return None
    if not (text[:4].isdigit() and text[5:].isdigit()):
        return None
    year, month = int(text[:4]), int(text[5:])
    if not 1 <= month <= 12 or year < 1:
        return None
    return date(year, month, 1)


MONTH_NAMES = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")


def month_display(month: date) -> str:
    """``Set/2026``: how a month is written on the screens and in the exports."""
    return f"{MONTH_NAMES[month.month - 1]}/{month.year:04d}"


def add_months(month: date, count: int) -> date:
    """The first day of the month ``count`` months after (or before, when negative) the given one."""
    index = month.year * 12 + (month.month - 1) + count
    return date(index // 12, index % 12 + 1, 1)


def months_between(first: date, last: date) -> list[date]:
    """Every month from ``first`` to ``last`` inclusive; empty when ``last`` comes first."""
    result: list[date] = []
    current = month_of(first)
    while current <= month_of(last):
        result.append(current)
        current = add_months(current, 1)
    return result


def is_future_month(month: date, reference_date: date) -> bool:
    """Whether the month is after the month of the reference date: it cannot be recorded yet."""
    return month_of(month) > month_of(reference_date)


def round_half_up(value: Decimal | float) -> int:
    """Round to an integer with halves going up, as the prototype's ``Math.round`` does."""
    if isinstance(value, float):
        return math.floor(value + 0.5)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def hours_per_person(hours: Decimal, headcount: int) -> int:
    """Média de horas por pessoa: HHT divided by the average headcount, 0 without headcount."""
    if headcount <= 0:
        return 0
    return round_half_up(hours / Decimal(headcount))


@dataclass(frozen=True)
class ExpectedWindow:
    """The span of one project that should have HHT: from its start, until its end or the reference."""

    start: date | None
    planned_end: date | None


def expected_months(windows: Iterable[ExpectedWindow], reference_date: date) -> int:
    """Meses esperados com registro: the distinct months of the windows, up to the reference month.

    A project with no start date adds nothing; a project that ended before the reference month
    stops at its planned end. In the Portfólio a month shared by two projects counts once.
    """
    months: set[date] = set()
    reference = month_of(reference_date)
    for window in windows:
        if window.start is None:
            continue
        last = reference
        if window.planned_end is not None and month_of(window.planned_end) < reference:
            last = month_of(window.planned_end)
        months.update(months_between(window.start, last))
    return len(months)


@dataclass(frozen=True)
class HoursLine:
    """One HHT record as the calculations read it: project, company, month, headcount and hours."""

    project_id: int
    company_id: int
    month: date
    headcount: int
    hours: Decimal


@dataclass(frozen=True)
class HoursSummary:
    """The four indicators of the HHT screen."""

    total_hours: Decimal
    months_with_record: int
    last_month: date | None
    last_month_headcount: int
    companies_with_record: int


def summarize_hours(lines: Sequence[HoursLine]) -> HoursSummary:
    """HHT total, months with a record, headcount of the last month and companies with a record."""
    months = {line.month for line in lines}
    last = max(months) if months else None
    return HoursSummary(
        total_hours=sum((line.hours for line in lines), Decimal(0)),
        months_with_record=len(months),
        last_month=last,
        last_month_headcount=sum(line.headcount for line in lines if line.month == last),
        companies_with_record=len({line.company_id for line in lines}),
    )


@dataclass(frozen=True)
class CurvePoint:
    """A month of the physical S curve of a project: the planned and the actual accumulated."""

    month: date
    planned: float
    actual: float | None


def histogram_factor(curve: Sequence[CurvePoint], month: date) -> float:
    """Fator do histograma: planned advance of the month over the actual one, within 0,85 to 1,20.

    Without a curve, a month outside it, a month with no actual yet, or no advance in the planned
    or in the actual, the factor is 1.
    """
    ordered = sorted(curve, key=lambda point: point.month)
    index = next((i for i, point in enumerate(ordered) if point.month == month), None)
    if index is None or ordered[index].actual is None:
        return 1.0
    point = ordered[index]
    previous = ordered[index - 1] if index > 0 else None
    planned_step = point.planned - (previous.planned if previous else 0.0)
    previous_actual = previous.actual if previous and previous.actual is not None else 0.0
    actual_step = (point.actual or 0.0) - previous_actual
    if actual_step <= 0 or planned_step <= 0:
        return 1.0
    return max(FACTOR_FLOOR, min(FACTOR_CEILING, planned_step / actual_step))


@dataclass(frozen=True)
class HistogramPoint:
    """A month of the labour histogram: the planned hours and headcount and the recorded ones."""

    project_id: int
    month: date
    planned_hours: int
    planned_headcount: int
    recorded_hours: Decimal
    recorded_headcount: int


def labour_histogram(
    lines: Sequence[HoursLine], curves: Mapping[int, Sequence[CurvePoint]]
) -> list[HistogramPoint]:
    """Histograma de mão de obra previsto: the recorded HHT of each project and month, adjusted.

    The recorded hours and headcount of the month (every company added) are scaled by
    ``histogram_factor`` of the project's physical S curve; the planned hours are rounded to
    hundreds and the planned headcount to units. The curve of a project that has none leaves the
    factor at 1. The result is ordered by project and month.
    """
    totals: dict[tuple[int, date], tuple[Decimal, int]] = {}
    for line in lines:
        key = (line.project_id, line.month)
        hours, headcount = totals.get(key, (Decimal(0), 0))
        totals[key] = (hours + line.hours, headcount + line.headcount)
    points: list[HistogramPoint] = []
    for (project_id, month), (hours, headcount) in sorted(totals.items()):
        factor = histogram_factor(curves.get(project_id, ()), month)
        points.append(
            HistogramPoint(
                project_id=project_id,
                month=month,
                planned_hours=round_half_up(float(hours) * factor / HOURS_ROUNDING)
                * HOURS_ROUNDING,
                planned_headcount=round_half_up(headcount * factor),
                recorded_hours=hours,
                recorded_headcount=headcount,
            )
        )
    return points


@dataclass(frozen=True)
class PlannedLabour:
    """The planned hours and headcount of the histogram, up to a month or in one month."""

    hours: int
    headcount: int


def planned_labour(
    points: Sequence[HistogramPoint], *, up_to: date, only_month: bool = False
) -> PlannedLabour | None:
    """HHT previsto até o mês (acumulado) or só no mês; ``None`` when no point qualifies."""
    chosen = [
        point for point in points if (point.month == up_to if only_month else point.month <= up_to)
    ]
    if not chosen:
        return None
    return PlannedLabour(
        hours=sum(point.planned_hours for point in chosen),
        headcount=sum(point.planned_headcount for point in chosen),
    )


def rate_percent(part: int, whole: int) -> Decimal | None:
    """``part`` over ``whole`` in percent, one decimal, half up; ``None`` when the whole is zero."""
    if whole <= 0:
        return None
    return (Decimal(part) * PERCENT / Decimal(whole)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def proactive_target(per_ten_thousand_hours: int, hours: Decimal) -> int:
    """Meta proativa: the target per 10 mil HHT applied to the hours, rounded half up."""
    return round_half_up(Decimal(per_ten_thousand_hours) * hours / TEN_THOUSAND)


@dataclass(frozen=True)
class ClosingLine:
    """One monthly closing as the proactive indicators read it."""

    project_id: int
    month: date
    deviations: int
    observations: int
    planned_dds: int
    held_dds: int
    inspected_items: int
    conforming_items: int


@dataclass(frozen=True)
class ProactiveSummary:
    """The four indicators of the Inspeções e observações screen."""

    dds_rate: Decimal | None
    held_dds: int
    planned_dds: int
    conformity_rate: Decimal | None
    conforming_items: int
    inspected_items: int
    observations: int
    deviations: int
    observations_target: int | None
    deviations_target: int | None


def summarize_proactive(
    closings: Sequence[ClosingLine],
    hours: Sequence[HoursLine],
    *,
    observations_per_ten_thousand: int,
    deviations_per_ten_thousand: int,
) -> ProactiveSummary:
    """DDS realized, inspection conformity, observations and deviations against the HHT targets.

    The targets apply to the HHT of the months that have a closing (same project and month);
    with no HHT in those months there is no target.
    """
    closed = {(line.project_id, line.month) for line in closings}
    closed_hours = sum(
        (line.hours for line in hours if (line.project_id, line.month) in closed), Decimal(0)
    )
    has_hours = closed_hours > 0
    planned = sum(line.planned_dds for line in closings)
    held = sum(line.held_dds for line in closings)
    inspected = sum(line.inspected_items for line in closings)
    conforming = sum(line.conforming_items for line in closings)
    return ProactiveSummary(
        dds_rate=rate_percent(held, planned),
        held_dds=held,
        planned_dds=planned,
        conformity_rate=rate_percent(conforming, inspected),
        conforming_items=conforming,
        inspected_items=inspected,
        observations=sum(line.observations for line in closings),
        deviations=sum(line.deviations for line in closings),
        observations_target=(
            proactive_target(observations_per_ten_thousand, closed_hours) if has_hours else None
        ),
        deviations_target=(
            proactive_target(deviations_per_ten_thousand, closed_hours) if has_hours else None
        ),
    )


# ── Risk analyses (APR/JSA and HAZOP, ISSUE-074) ─────────────────────────────────────────────

RECOMMENDATION_OPEN = "Aberta"
RECOMMENDATION_CLOSED = "Fechada"


@dataclass(frozen=True)
class RecommendationCounts:
    """What a set of recommendations says: issued, open, overdue and closed."""

    issued: int = 0
    open: int = 0
    overdue: int = 0
    closed: int = 0

    def plus(self, other: RecommendationCounts) -> RecommendationCounts:
        """The sum of two counts, to total the recommendations of several studies."""
        return RecommendationCounts(
            issued=self.issued + other.issued,
            open=self.open + other.open,
            overdue=self.overdue + other.overdue,
            closed=self.closed + other.closed,
        )


def is_recommendation_overdue(status: str, due_date: date, reference_date: date) -> bool:
    """A recommendation is overdue when it is still open and its deadline is before the reference."""
    return status == RECOMMENDATION_OPEN and due_date < reference_date


def count_recommendations(
    recommendations: Iterable[tuple[str, date]], reference_date: date
) -> RecommendationCounts:
    """Issued, open, overdue and closed from the ``(status, deadline)`` of each recommendation."""
    issued = open_ = overdue = closed = 0
    for status, due_date in recommendations:
        issued += 1
        if status == RECOMMENDATION_CLOSED:
            closed += 1
        else:
            open_ += 1
        if is_recommendation_overdue(status, due_date, reference_date):
            overdue += 1
    return RecommendationCounts(issued=issued, open=open_, overdue=overdue, closed=closed)


def recommendations_closed_rate(closed: int, issued: int) -> Decimal | None:
    """Closed recommendations over issued ones, in percentage points; ``None`` with none issued."""
    return rate_percent(closed, issued)
