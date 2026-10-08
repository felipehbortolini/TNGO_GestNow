"""Pure calculations for the Planning module.

Relato do período (ISSUE-044): the periods a report may cover, the ones still owed, the labels
a person reads and the rules that order and summarize the reports. Every function that needs
a date receives it as an argument (D6); nothing here reads the clock. The business names are
listed in ``LEIA-ME.md``.


The 6WLA rules (ISSUE-045) live here, one function per business rule. None of
them reads the clock: the reference date comes in as an argument (D6).

The WBS rules (ISSUE-036): the real of a package comes from the entries of its
measuring criterion, the nodes of the tree add up the children by weight (the
100% rule) and the deviation uses the bands of the parameters. The reference
date also comes in as an argument (D6).

The measurement rules (ISSUE-037): the conversion of an accumulated percent
into the entries of the criterion (used by the import of the advance), the
degrees a milestone accepts and the detection of a reversal.

The revision of the EAP and the breakdown (ISSUE-038): the rescale of the
weights to a target by the largest remainder (the others close at 100%) and the
linear predicted of a package between the dates of its baseline. The reference
date comes in as an argument (D6).

The physical S-curve (ISSUE-039): the monthly calendar of the packages with
weight, the baseline of each month by the linear predicted of the package, the
real from the dated measurements and the trend that follows the baseline from
the cut, plus the weighted curve of the portfolio. The reference date comes in
as an argument (D6).

The planning KPIs (ISSUE-040): the SPI (real over predicted), the monthly SPI
series up to the cut and the contribution of an area to the real of the project
(weight times real). The cut already lives in the series, so no function here
reads the clock (D6).

The productivity (ISSUE-046): the distribution of the baseline total across the
weeks by the chosen profile (S-curve 20/60/20, linear, concentrated at the start
or at the end), always closing with the total by the largest remainder; the
figures of an item (planned, realized, earned hours, factor of productivity and
the finish trend by earned schedule); and the freeze/redistribute rule of a
baseline revision, whose balance is the new total minus the frozen weeks. The
cut, the current week and the reference date all come in as arguments (D6).

The field hours (ISSUE-047): the capacity of a field day (the execution of the
two shifts), the utilization against the reference journey, the delay, the
lunch break, the effective and the idle man-hours; the summary of the journeys
of a period; the share of the work sampling (working, transit and stopped), the
Pareto of the reasons (descending order with the accumulated) and the stoppage
figures (crew hours and machine hours). The window of the period and the bands
of the indicators come in as arguments; the catalogs of the reasons are the ones
of the prototype, read here by the server, never by the screen (D6).

The performance KPIs (ISSUE-048): the aggregate trend of the schedule (the
earned schedule index of a set of items, SPI(t), and the slip in weeks), the
weekly trend of a company (factor of productivity, adherence, percentage
working and capacity), the share of the stoppages over the available man-hours,
the bands of the five indicators per company and the reference of the action of
the Central (``PRD-2026-S39-01``). The cut and the reference date come in as
arguments (D6); the chart payload hands the raw pair of each week, never the
ready percentage (D11).
"""

from __future__ import annotations

import re
from calendar import monthrange
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from math import ceil
from typing import Any

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


WORK_PACKAGE = "Trabalho"


PLANNING_PACKAGE = "Planejamento"


CRITERION_STEPS = "Etapas"


CRITERION_UNITS = "Unidades"


CRITERION_MILESTONE_0_100 = "Marco 0/100"


CRITERION_MILESTONE_50_50 = "Marco 50/50"


CRITERION_ESTIMATED = "Percentual estimado"


EAP_CRITERIA = (
    CRITERION_STEPS,
    CRITERION_UNITS,
    CRITERION_MILESTONE_0_100,
    CRITERION_MILESTONE_50_50,
    CRITERION_ESTIMATED,
)


MILESTONE_NOT_STARTED = "Não iniciado"


MILESTONE_STARTED = "Iniciado"


MILESTONE_DONE = "Concluído"


SUCCESS_BAND = "success"


WARNING_BAND = "warning"


DANGER_BAND = "danger"


ZERO = Decimal(0)


HALF = Decimal(50)


ONE_PLACE = Decimal("0.1")


@dataclass(frozen=True)
class EapStep:
    """Uma etapa do critério Etapas: o nome, o peso no pacote e o % concluído corrente."""

    name: str
    weight: Decimal
    pct: Decimal | None = None


@dataclass(frozen=True)
class EapWeightedValue:
    """Um valor da média ponderada: o peso e o percentual que ele pondera."""

    weight: Decimal
    value: Decimal


@dataclass(frozen=True)
class EapPackage:
    """O pacote de nível 3 como o cálculo do nó precisa dele.

    ``kind`` diz se é pacote de trabalho ou de planejamento; as entradas do critério são o
    estado corrente de onde o real é calculado.
    """

    kind: str
    weight: Decimal
    predicted: Decimal
    start: date | None
    finish: date | None
    criterion: str | None = None
    etapas: Sequence[EapStep] = ()
    quantity: Decimal | None = None
    executed: Decimal | None = None
    state: str | None = None
    estimated_pct: Decimal | None = None


@dataclass(frozen=True)
class EapTotals:
    """Os totais de um nó da árvore: um pacote, uma área, uma subárea ou a linha 0."""

    weight: Decimal
    predicted: Decimal
    actual: Decimal
    start: date | None
    finish: date | None
    packages: int = 0
    planning: int = 0
    overdue: bool = False
    not_started: bool = False


def eap_package_progress(
    criterion: str | None,
    *,
    etapas: Sequence[EapStep] = (),
    quantity: Decimal | None = None,
    executed: Decimal | None = None,
    state: str | None = None,
    estimated_pct: Decimal | None = None,
) -> Decimal:
    """O real do pacote pelo critério de medição, entre 0 e 100 e com 2 casas.

    O pacote de planejamento, sem critério, não mede avanço: fica em zero.
    """
    if criterion == CRITERION_STEPS:
        value = _steps_progress(etapas)
    elif criterion == CRITERION_UNITS:
        value = _units_progress(quantity, executed)
    elif criterion == CRITERION_MILESTONE_0_100:
        value = PERCENT if state == MILESTONE_DONE else ZERO
    elif criterion == CRITERION_MILESTONE_50_50:
        value = _milestone_half_progress(state)
    elif criterion == CRITERION_ESTIMATED:
        value = estimated_pct if estimated_pct is not None else ZERO
    else:
        value = ZERO
    return _clamp_progress(value)


def _steps_progress(etapas: Sequence[EapStep]) -> Decimal:
    weighted = sum(((step.weight or ZERO) * (step.pct or ZERO) for step in etapas), ZERO)
    return weighted / PERCENT


def _units_progress(quantity: Decimal | None, executed: Decimal | None) -> Decimal:
    if quantity is None or quantity <= ZERO:
        return ZERO
    done = executed if executed is not None else ZERO
    return min(PERCENT, done * PERCENT / quantity)


def _milestone_half_progress(state: str | None) -> Decimal:
    if state == MILESTONE_DONE:
        return PERCENT
    if state == MILESTONE_STARTED:
        return HALF
    return ZERO


def _round_two(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _clamp_progress(value: Decimal) -> Decimal:
    return _round_two(min(PERCENT, max(ZERO, value)))


def eap_weighted_progress(values: Sequence[EapWeightedValue]) -> Decimal:
    """A média ponderada dos valores pelo peso, com 2 casas; sem peso, zero."""
    total_weight = sum((item.weight for item in values), ZERO)
    if total_weight == ZERO:
        return ZERO
    weighted = sum((item.weight * item.value for item in values), ZERO)
    return _round_two(weighted / total_weight)


def eap_deviation_pp(actual: Decimal, predicted: Decimal) -> Decimal:
    """O desvio físico em pontos percentuais: real menos previsto, com 1 casa."""
    return (actual - predicted).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)


def eap_deviation_band(deviation: Decimal | None, bands: Sequence[Decimal]) -> str | None:
    """A faixa do desvio: ``success`` até -faixa[0], ``warning`` até -faixa[1], senão ``danger``."""
    if deviation is None:
        return None
    if deviation >= -bands[0]:
        return SUCCESS_BAND
    if deviation >= -bands[1]:
        return WARNING_BAND
    return DANGER_BAND


def eap_package_overdue(
    kind: str, finish: date | None, actual: Decimal, reference_date: date
) -> bool:
    """Pacote vencido: de trabalho, com término anterior à referência e real abaixo de 100."""
    if kind == PLANNING_PACKAGE or finish is None:
        return False
    return finish < reference_date and actual < PERCENT


def eap_package_not_started(
    kind: str, start: date | None, actual: Decimal, reference_date: date
) -> bool:
    """Pacote não iniciado: de trabalho, já deveria ter começado e o real está em zero."""
    if kind == PLANNING_PACKAGE or start is None:
        return False
    return start <= reference_date and actual == ZERO


def eap_package_totals(package: EapPackage, *, reference_date: date) -> EapTotals:
    """O nó do pacote: real do critério, contagem e as marcas de vencido e não iniciado.

    O pacote de planejamento não mede avanço, mesmo que traga um critério gravado.
    """
    work = package.kind != PLANNING_PACKAGE
    actual = (
        eap_package_progress(
            package.criterion,
            etapas=package.etapas,
            quantity=package.quantity,
            executed=package.executed,
            state=package.state,
            estimated_pct=package.estimated_pct,
        )
        if work
        else ZERO
    )
    return EapTotals(
        weight=package.weight,
        predicted=package.predicted,
        actual=actual,
        start=package.start,
        finish=package.finish,
        packages=1 if work else 0,
        planning=0 if work else 1,
        overdue=eap_package_overdue(package.kind, package.finish, actual, reference_date),
        not_started=eap_package_not_started(package.kind, package.start, actual, reference_date),
    )


def eap_node_totals(children: Sequence[EapTotals]) -> EapTotals:
    """Os totais de um nó a partir dos filhos: peso somado, previsto e real ponderados, extremos."""
    if not children:
        return EapTotals(weight=ZERO, predicted=ZERO, actual=ZERO, start=None, finish=None)
    weight = sum((child.weight for child in children), ZERO).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    predicted = eap_weighted_progress(
        [EapWeightedValue(child.weight, child.predicted) for child in children]
    )
    actual = eap_weighted_progress(
        [EapWeightedValue(child.weight, child.actual) for child in children]
    )
    starts = [child.start for child in children if child.start is not None]
    finishes = [child.finish for child in children if child.finish is not None]
    return EapTotals(
        weight=weight,
        predicted=predicted,
        actual=actual,
        start=min(starts) if starts else None,
        finish=max(finishes) if finishes else None,
        packages=sum(child.packages for child in children),
        planning=sum(child.planning for child in children),
        overdue=any(child.overdue for child in children),
        not_started=any(child.not_started for child in children),
    )


def eap_root_totals(children: Sequence[EapTotals]) -> EapTotals:
    """A linha 0 da árvore: o total do projeto (ou do portfólio) a partir dos nós de nível 1."""
    return eap_node_totals(children)


EAP_PERCENT_RANGE_MESSAGE = "O avanço precisa ficar entre 0 e 100%."


MILESTONE_0_100_OPTIONS_MESSAGE = "Marco 0/100 só aceita 0 ou 100%."


MILESTONE_50_50_OPTIONS_MESSAGE = "Marco 50/50 só aceita 0, 50 ou 100%."


EAP_NO_CRITERION_MESSAGE = "Pacote sem critério de medição."


MILESTONE_0_100_PERCENT_STATES = (
    (ZERO, MILESTONE_NOT_STARTED),
    (PERCENT, MILESTONE_DONE),
)


MILESTONE_0_100_STATES = tuple(state for _, state in MILESTONE_0_100_PERCENT_STATES)


MILESTONE_50_50_PERCENT_STATES = (
    (ZERO, MILESTONE_NOT_STARTED),
    (HALF, MILESTONE_STARTED),
    (PERCENT, MILESTONE_DONE),
)


MILESTONE_50_50_STATES = tuple(state for _, state in MILESTONE_50_50_PERCENT_STATES)


@dataclass(frozen=True)
class EapPercentEntries:
    """As entradas do critério convertidas de um % acumulado; ``error`` diz por que não converteu."""

    etapas: tuple[EapStep, ...] = ()
    executed: Decimal | None = None
    state: str | None = None
    estimated_pct: Decimal | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Se o percentual virou as entradas do critério."""
        return self.error is None


def eap_entries_from_percent(
    criterion: str | None,
    percent: Decimal | None,
    *,
    etapas: Sequence[EapStep] = (),
    quantity: Decimal | None = None,
) -> EapPercentEntries:
    """Converte um % acumulado nas entradas do critério (a importação do avanço).

    As Etapas são preenchidas em sequência pelo peso de cada uma; os marcos só aceitam os
    degraus do critério; o Percentual estimado guarda o próprio valor. O ``error`` traz o
    motivo quando o percentual não vira entradas.
    """
    if percent is None or not percent.is_finite() or percent < ZERO or percent > PERCENT:
        return EapPercentEntries(error=EAP_PERCENT_RANGE_MESSAGE)
    return _entries_of_criterion(criterion, percent, etapas=etapas, quantity=quantity)


def _entries_of_criterion(
    criterion: str | None,
    percent: Decimal,
    *,
    etapas: Sequence[EapStep],
    quantity: Decimal | None,
) -> EapPercentEntries:
    if criterion == CRITERION_STEPS:
        entries = EapPercentEntries(etapas=_steps_from_percent(etapas, percent))
    elif criterion == CRITERION_UNITS:
        base = quantity if quantity is not None else ZERO
        entries = EapPercentEntries(executed=_round_two(base * percent / PERCENT))
    elif criterion == CRITERION_MILESTONE_0_100:
        entries = _milestone_entries(
            MILESTONE_0_100_PERCENT_STATES, percent, MILESTONE_0_100_OPTIONS_MESSAGE
        )
    elif criterion == CRITERION_MILESTONE_50_50:
        entries = _milestone_entries(
            MILESTONE_50_50_PERCENT_STATES, percent, MILESTONE_50_50_OPTIONS_MESSAGE
        )
    elif criterion == CRITERION_ESTIMATED:
        entries = EapPercentEntries(estimated_pct=_round_two(percent))
    else:
        entries = EapPercentEntries(error=EAP_NO_CRITERION_MESSAGE)
    return entries


def eap_progress_regression(before: Decimal, after: Decimal) -> bool:
    """O acumulado regrediu: o real depois ficou abaixo do real antes."""
    return after < before


def _steps_from_percent(etapas: Sequence[EapStep], percent: Decimal) -> tuple[EapStep, ...]:
    remaining = percent
    converted: list[EapStep] = []
    for step in etapas:
        weight = step.weight or ZERO
        used = min(weight, max(ZERO, remaining))
        remaining -= used
        pct = _round_two(used * PERCENT / weight) if weight else ZERO
        converted.append(EapStep(name=step.name, weight=step.weight, pct=pct))
    return tuple(converted)


def _milestone_entries(
    degrees: Sequence[tuple[Decimal, str]], percent: Decimal, message: str
) -> EapPercentEntries:
    state = next((state for degree, state in degrees if degree == percent), None)
    if state is None:
        return EapPercentEntries(error=message)
    return EapPercentEntries(state=state)


def eap_rescale_weights(
    weights: Sequence[tuple[str, Decimal]], target: Decimal
) -> dict[str, Decimal]:
    """Reescala os pesos para somarem o alvo, pelo maior resto, com 2 casas.

    O alvo vira centésimos; cada chave fica com o piso da sua proporção e a sobra de um
    centésimo vai para os maiores restos, com o empate resolvido pela ordem de entrada.
    Sem peso na entrada não há proporção: todas as chaves saem zeradas (o protótipo
    distribuía a sobra do alvo a esmo, o que não fechava o alvo).
    """
    total = sum((weight for _, weight in weights), ZERO)
    if total == ZERO:
        return {code: ZERO for code, _ in weights}
    target_cents = int((target * PERCENT).to_integral_value(rounding=ROUND_HALF_UP))
    rows = [(code, weight * target_cents / total) for code, weight in weights]
    bases = [int(share.to_integral_value(rounding=ROUND_FLOOR)) for _, share in rows]
    remainders = [share - base for (_, share), base in zip(rows, bases, strict=True)]
    leftover = target_cents - sum(bases)
    if leftover > 0:
        order = sorted(range(len(rows)), key=lambda index: -remainders[index])
        for index in order[:leftover]:
            bases[index] += 1
    return {code: _round_two(base / PERCENT) for (code, _), base in zip(rows, bases, strict=True)}


def eap_linear_predicted(start: date | None, finish: date | None, reference_date: date) -> Decimal:
    """O previsto do pacote novo na referência, pela distribuição linear da linha de base.

    Zero sem datas ou com a referência até o início; 100 da referência a partir do término;
    no meio, os dias corridos entre o início e a referência sobre o prazo, com 1 casa.
    """
    if start is None or finish is None or reference_date <= start:
        return ZERO
    if reference_date >= finish:
        return PERCENT
    elapsed = Decimal((reference_date - start).days)
    span = Decimal((finish - start).days)
    return (elapsed * PERCENT / span).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CurvaFisicaMeasurement:
    """Uma medição datada do pacote: o dia e o percentual acumulado que ela atingiu."""

    measured_on: date
    to_pct: Decimal


@dataclass(frozen=True)
class CurvaFisicaPackage:
    """O pacote como a Curva S física o lê: peso congelado, datas da LB e medições."""

    weight: Decimal
    start: date | None = None
    finish: date | None = None
    measurements: Sequence[CurvaFisicaMeasurement] = ()


@dataclass(frozen=True)
class CurvaFisicaCalendar:
    """O calendário mensal da curva e o índice do mês de corte."""

    months: tuple[date, ...]
    cut_index: int


@dataclass(frozen=True)
class CurvaFisicaSeries:
    """Uma curva: os meses, o corte e as séries baseline, real e tendência."""

    months: tuple[date, ...]
    cut_index: int
    baseline: tuple[Decimal, ...]
    real: tuple[Decimal | None, ...]
    trend: tuple[Decimal | None, ...]


def _round_one(value: Decimal) -> Decimal:
    return value.quantize(ONE_PLACE, rounding=ROUND_HALF_UP)


def _month_first(day: date) -> date:
    return day.replace(day=1)


def _month_last(month: date) -> date:
    return month.replace(day=monthrange(month.year, month.month)[1])


def _next_month(month: date) -> date:
    if month.month == MONTHS_IN_YEAR:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)


def _month_sequence(first: date, last: date) -> tuple[date, ...]:
    months: list[date] = []
    current = first
    while current <= last:
        months.append(current)
        current = _next_month(current)
    return tuple(months)


def _cut_index(months: Sequence[date], reference_date: date) -> int:
    reference_month = _month_first(reference_date)
    realized = [index for index, month in enumerate(months) if month <= reference_month]
    return realized[-1] if realized else -1


def _as_of(month: date, reference_date: date) -> date:
    if month == _month_first(reference_date):
        return reference_date
    return _month_last(month)


def _measurement_at(package: CurvaFisicaPackage, as_of: date) -> Decimal:
    measured = [
        measurement for measurement in package.measurements if measurement.measured_on <= as_of
    ]
    if not measured:
        return ZERO
    return max(measured, key=lambda measurement: measurement.measured_on).to_pct


def curva_fisica_months(
    packages: Sequence[CurvaFisicaPackage], reference_date: date
) -> CurvaFisicaCalendar:
    """O calendário da curva e o índice do mês de corte.

    Os meses vão do primeiro dia do mês do início mais antigo ao primeiro dia do mês do
    término mais novo, entre os pacotes com peso > 0 e as duas datas. O corte é o mês da
    referência; com a referência depois do término, é o último mês (todos já têm real);
    antes do início, nenhum mês tem real e o corte é -1.
    """
    starts: list[date] = []
    finishes: list[date] = []
    for package in packages:
        if package.weight <= ZERO or package.start is None or package.finish is None:
            continue
        starts.append(package.start)
        finishes.append(package.finish)
    if not starts:
        return CurvaFisicaCalendar(months=(), cut_index=-1)
    months = _month_sequence(_month_first(min(starts)), _month_first(max(finishes)))
    return CurvaFisicaCalendar(months=months, cut_index=_cut_index(months, reference_date))


def curva_fisica_baseline(
    packages: Sequence[CurvaFisicaPackage], months: Sequence[date], reference_date: date
) -> tuple[Decimal, ...]:
    """O previsto acumulado de cada mês: a soma ponderada do previsto linear dos pacotes.

    O mês da referência usa a própria referência; os demais, o último dia do mês. Pacote
    sem peso não entra; cada valor sai com 1 casa.
    """
    baseline: list[Decimal] = []
    for month in months:
        as_of = _as_of(month, reference_date)
        total = sum(
            (
                package.weight * eap_linear_predicted(package.start, package.finish, as_of)
                for package in packages
                if package.weight > ZERO
            ),
            ZERO,
        )
        baseline.append(_round_one(total / PERCENT))
    return tuple(baseline)


def curva_fisica_real(
    packages: Sequence[CurvaFisicaPackage], months: Sequence[date], reference_date: date
) -> tuple[Decimal | None, ...]:
    """O real acumulado de cada mês: a soma ponderada da última medição até a data do mês.

    O mês da referência usa a própria referência; os demais, o último dia do mês. O pacote
    sem medição entra com zero e o mês depois do mês da referência sai vazio (``None``).
    """
    reference_month = _month_first(reference_date)
    real: list[Decimal | None] = []
    for month in months:
        if month > reference_month:
            real.append(None)
            continue
        as_of = _as_of(month, reference_date)
        total = sum(
            (
                package.weight * _measurement_at(package, as_of)
                for package in packages
                if package.weight > ZERO
            ),
            ZERO,
        )
        real.append(_round_one(total / PERCENT))
    return tuple(real)


def curva_fisica_trend(
    baseline: Sequence[Decimal], real: Sequence[Decimal | None], cut_index: int
) -> tuple[Decimal | None, ...]:
    """A tendência: arranca no real do corte e segue o ritmo da linha de base.

    Vazio antes do corte; no corte, o real do corte; depois, o real do corte mais o avanço
    da linha de base desde o corte, com teto de 100 e 1 casa. Sem corte ou sem real no
    corte, não há tendência.
    """
    if cut_index < 0 or cut_index >= len(real):
        return (None,) * len(baseline)
    actual = real[cut_index]
    if actual is None:
        return (None,) * len(baseline)
    trend: list[Decimal | None] = []
    for index, planned in enumerate(baseline):
        if index < cut_index:
            trend.append(None)
        elif index == cut_index:
            trend.append(_round_one(actual))
        else:
            trend.append(min(PERCENT, _round_one(actual + planned - baseline[cut_index])))
    return tuple(trend)


def _portfolio_cut_index(series: Mapping[int, CurvaFisicaSeries], months: Sequence[date]) -> int:
    cuts = [
        item.months[item.cut_index]
        for item in series.values()
        if item.months and item.cut_index >= 0
    ]
    if not cuts:
        return -1
    past = [index for index, month in enumerate(months) if month <= max(cuts)]
    return past[-1] if past else -1


def _portfolio_average(
    series: Mapping[int, CurvaFisicaSeries],
    weights: Mapping[int, Decimal],
    month: date,
    value_of: Callable[[CurvaFisicaSeries, date], Decimal | None],
    divisor: Decimal,
) -> Decimal:
    total = sum(
        (
            weights.get(project_id, ZERO) * (value_of(item, month) or ZERO)
            for project_id, item in series.items()
        ),
        ZERO,
    )
    return _round_one(total / divisor)


def _series_baseline(item: CurvaFisicaSeries, month: date) -> Decimal:
    if not item.months or month < item.months[0]:
        return ZERO
    if month > item.months[-1]:
        return PERCENT
    return item.baseline[item.months.index(month)]


def _series_real(item: CurvaFisicaSeries, month: date) -> Decimal:
    measured = [
        value
        for day, value in zip(item.months, item.real, strict=True)
        if day <= month and value is not None
    ]
    return measured[-1] if measured else ZERO


def _series_trend(item: CurvaFisicaSeries, month: date) -> Decimal | None:
    if not item.months or month < item.months[0]:
        return ZERO
    if month > item.months[-1]:
        return PERCENT
    index = item.months.index(month)
    if item.trend[index] is not None:
        return item.trend[index]
    if item.cut_index >= 0 and month <= item.months[item.cut_index]:
        return item.real[index]
    return item.baseline[index]


def curva_fisica_portfolio(
    series: Mapping[int, CurvaFisicaSeries],
    weights: Mapping[int, Decimal],
    months: Sequence[date],
) -> CurvaFisicaSeries:
    """A curva da carteira: a média ponderada das curvas, no calendário da união dos meses.

    Antes do primeiro mês do projeto ele vale zero; depois do último, 100 na linha de base e
    o último real no real; dentro do calendário do projeto, o real de um mês posterior ao
    corte dele repete o último real. O corte é o maior corte e o peso é renormalizado pelos
    projetos presentes, com 1 casa.
    """
    divisor = sum((weights.get(project_id, ZERO) for project_id in series), ZERO) or Decimal(1)
    cut_index = _portfolio_cut_index(series, months)
    baseline = tuple(
        _portfolio_average(series, weights, month, _series_baseline, divisor) for month in months
    )
    real: list[Decimal | None] = []
    trend: list[Decimal | None] = []
    for month in months:
        after_cut = cut_index < 0 or month > months[cut_index]
        real.append(
            None if after_cut else _portfolio_average(series, weights, month, _series_real, divisor)
        )
        before_cut = cut_index < 0 or month < months[cut_index]
        trend.append(
            None
            if before_cut
            else _portfolio_average(series, weights, month, _series_trend, divisor)
        )
    return CurvaFisicaSeries(
        months=tuple(months),
        cut_index=cut_index,
        baseline=baseline,
        real=tuple(real),
        trend=tuple(trend),
    )


# ── KPIs de planejamento (ISSUE-040) ─────────────────────────────────────


def spi_index(real: Decimal | None, previsto: Decimal | None) -> Decimal | None:
    """O SPI físico: real ÷ previsto, com 2 casas; sem previsto (zero ou ausente) não há índice."""
    if real is None or previsto is None or previsto == ZERO:
        return None
    return (real / previsto).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def spi_series(
    baseline: Sequence[Decimal], real: Sequence[Decimal | None]
) -> tuple[Decimal | None, ...]:
    """O SPI de cada mês até o corte: real ÷ previsto do mês; sem real ou sem previsto, ``None``.

    O corte é o último mês com real; os meses seguintes não entram na série.
    """
    cut = next((index for index in range(len(real) - 1, -1, -1) if real[index] is not None), -1)
    if cut < 0:
        return ()
    return tuple(
        spi_index(actual, planned)
        for planned, actual in zip(baseline[: cut + 1], real[: cut + 1], strict=True)
    )


def area_contribution(weight: Decimal, real: Decimal) -> Decimal:
    """A contribuição da área para o real do projeto: peso vezes real dividido por 100, 1 casa."""
    return (weight * real / PERCENT).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)


# ── Produtividade: quantidades e apontamento (ISSUE-046) ──────────────────


ITEM_DRAFT = "Em elaboração"


ITEM_APPROVED = "Aprovada"


ITEM_SITUATIONS = (ITEM_DRAFT, ITEM_APPROVED)


PROFILE_S_CURVE = "curvaS"


PROFILE_LINEAR = "linear"


PROFILE_START = "inicio"


PROFILE_END = "fim"


PROFILES = (PROFILE_S_CURVE, PROFILE_LINEAR, PROFILE_START, PROFILE_END)


# O prefixo do código do item quando o projeto ainda não tem nenhum.
ITEM_CODE_PREFIX = "QTD-"


SCURVE_RAMP = Decimal("0.2")


SCURVE_BODY = Decimal("0.8")


START_WEIGHT = Decimal("1.6")


START_SLOPE = Decimal("1.2")


END_WEIGHT = Decimal("0.4")


END_SLOPE = Decimal("1.2")


def item_tolerance(places: int) -> Decimal:
    """Metade da menor casa da unidade: a folga que a soma das semanas aceita."""
    return (Decimal(1) / (Decimal(10) ** places)) / 2


def round_quantity(value: Decimal, places: int) -> Decimal:
    """Arredonda uma quantidade na casa da unidade do item (a tolerância da validação)."""
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def round_percent(value: Decimal, places: int = 1) -> Decimal:
    """Arredonda um percentual (ou índice) com o número de casas que a tela mostra."""
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def places_for_unit(unit_code: str) -> int:
    """As casas da unidade do item: tonelada guarda uma casa; as demais, nenhuma."""
    return 1 if unit_code == "t" else 0


def s_curve_20_60_20(fraction: Decimal) -> Decimal:
    """O peso da Curva S 20/60/20: rampa de 20%, pico de 60% e desmobilização de 20%.

    ``fraction`` é o centro da semana no intervalo (``(k + 0,5) / n``); a rampa sobe até
    20% do prazo, o corpo fica cheio e a desmobilização cai nos últimos 20%.
    """
    if fraction < SCURVE_RAMP:
        return SCURVE_RAMP + SCURVE_BODY * fraction / SCURVE_RAMP
    if fraction > Decimal(1) - SCURVE_RAMP:
        return SCURVE_RAMP + SCURVE_BODY * (Decimal(1) - fraction) / SCURVE_RAMP
    return Decimal(1)


def profile_weight(fraction: Decimal, profile: str) -> Decimal:
    """O peso de uma semana conforme o perfil: curva S, linear, início ou fim."""
    if profile == PROFILE_S_CURVE:
        return s_curve_20_60_20(fraction)
    if profile == PROFILE_START:
        return START_WEIGHT - START_SLOPE * fraction
    if profile == PROFILE_END:
        return END_WEIGHT + END_SLOPE * fraction
    return Decimal(1)


def profile_weights(count: int, profile: str) -> tuple[Decimal, ...]:
    """O peso de cada uma das ``count`` semanas no perfil; sem semanas, nenhum peso."""
    if count <= 0:
        return ()
    return tuple(
        profile_weight((Decimal(index) + Decimal("0.5")) / Decimal(count), profile)
        for index in range(count)
    )


def distribute_total(total: Decimal, count: int, profile: str, places: int) -> tuple[Decimal, ...]:
    """Distribui o total pelas semanas no perfil, pelo maior resto: a soma fecha com o total.

    O total é contado na sua menor unidade inteira (a casa da unidade); a sobra da divisão
    vai para as semanas de maior resto, e o empate fica com a semana de menor índice.
    """
    if count <= 0:
        return ()
    factor = Decimal(10) ** places
    units = int((total * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    weights = profile_weights(count, profile)
    weight_total = sum(weights, ZERO)
    exact = tuple(units * weight / weight_total for weight in weights)
    shares = [int(value) for value in exact]
    missing = units - sum(shares)
    order = sorted(range(count), key=lambda index: (-(exact[index] - shares[index]), index))
    for index in order[: max(0, missing)]:
        shares[index] += 1
    return tuple(Decimal(share) / factor for share in shares)


def distribution_closes(
    values: Sequence[Decimal],
    total: Decimal,
    places: int,
    *,
    frozen: Decimal = ZERO,
) -> bool:
    """A soma das semanas (com as congeladas) fecha com o total dentro da tolerância."""
    return abs(sum(values, ZERO) + frozen - total) <= item_tolerance(places)


def entry_over_limit(others: Decimal, realized: Decimal, total: Decimal, places: int) -> bool:
    """O acumulado do item passa o total da linha de base, além da tolerância da unidade."""
    return others + realized > total + item_tolerance(places)


def item_code_prefix(codes: Sequence[str]) -> str:
    """O prefixo do código do item: o do primeiro item do projeto, ou ``QTD-`` quando não há."""
    if not codes:
        return ITEM_CODE_PREFIX
    return re.sub(r"\d+$", "", codes[0])


def next_item_code(codes: Sequence[str]) -> str:
    """O próximo código do projeto: o maior número existente mais um, com dois dígitos."""
    biggest = 0
    for code in codes:
        found = re.search(r"(\d+)$", code)
        if found is not None:
            biggest = max(biggest, int(found.group(1)))
    return f"{item_code_prefix(codes)}{biggest + 1:02d}"


def week_label(day: date) -> str:
    """A semana ISO de uma data (``2026-S39``), a mesma escrita da plataforma."""
    return calendario.iso_week(day)


def week_start(label: str) -> date | None:
    """A segunda-feira de uma semana ISO, ou ``None`` quando o rótulo não é válido."""
    return calendario.week_start(label)


def list_weeks(first: str, last: str) -> tuple[str, ...]:
    """As semanas ISO de ``first`` a ``last``, em ordem crescente."""
    return tuple(calendario.list_periods(WEEKLY, first, last))


def weeks_between(first: str, last: str) -> int | None:
    """Quantas semanas separam duas semanas ISO; ``None`` quando alguma não é válida."""
    found = list_weeks(first, last)
    return len(found) - 1 if found else None


def shift_week(label: str, count: int) -> str | None:
    """A semana ``count`` semanas depois (antes, quando negativo) do rótulo."""
    return calendario.add_periods(WEEKLY, label, count)


@dataclass(frozen=True)
class PlannedWeek:
    """O previsto da linha de base numa semana."""

    week: str
    planned: Decimal


@dataclass(frozen=True)
class ReportedWeek:
    """O apontamento da contratada numa semana: realizado e HH apropriadas."""

    week: str
    realized: Decimal
    hh: Decimal


@dataclass(frozen=True)
class ItemFigures:
    """Os indicadores de um item no corte, como a tela e a exportação os leem.

    Tudo é calculado dos fatos (D5b): o previsto da distribuição da revisão vigente, o
    realizado e as HH dos apontamentos, e o total e o índice orçado do item. O saldo é o que
    falta para o total; a tendência de término sai do earned schedule.
    """

    approved: bool
    active: bool
    pending: bool
    prev_acum: Decimal
    real_acum: Decimal
    hh_acum: Decimal
    prev_week: Decimal
    real_week: Decimal | None
    balance: Decimal
    pct_prev: Decimal | None
    pct_real: Decimal | None
    deviation_pp: Decimal | None
    week_adherence: Decimal | None
    pf: Decimal | None
    window_adherence: Decimal | None
    pf_window: Decimal | None
    trend_week: str | None
    deviation_weeks: int | None
    earned_hours: Decimal
    planned_hours: Decimal
    total_hours: Decimal
    week_earned_hours: Decimal
    week_planned_hours: Decimal
    window_appropriated: Decimal
    window_earned: Decimal
    window_planned_hours: Decimal
    window_capped_hours: Decimal


def item_figures(
    *,
    start_week: str,
    finish_week: str,
    total: Decimal,
    index_hh: Decimal,
    places: int,
    situation: str,
    planned: Sequence[PlannedWeek],
    reported: Sequence[ReportedWeek],
    cut_week: str,
    current_week: str,
    window_weeks: int,
) -> ItemFigures:
    """Os indicadores do item no corte: acumulados, aderência, fator de produtividade e tendência."""
    planned_by_week = {line.week: line.planned for line in planned}
    window_start = shift_week(cut_week, -(window_weeks - 1)) or cut_week
    prev_acum, prev_week, prev_window = _planned_until(
        planned, cut_week=cut_week, window_start=window_start
    )
    real_acum, hh_acum, real_week, hh_window, real_window, capped = _reported_until(
        reported, planned_by_week=planned_by_week, cut_week=cut_week, window_start=window_start
    )
    approved = situation == ITEM_APPROVED
    balance = round_quantity(max(ZERO, total - real_acum), places)
    earned = real_acum * index_hh
    planned_hours = prev_acum * index_hh
    total_hours = total * index_hh
    trend_week, deviation_weeks = _finish_trend(
        approved=approved,
        balance=balance,
        real_acum=real_acum,
        planned=planned,
        reported=reported,
        start_week=start_week,
        finish_week=finish_week,
        cut_week=cut_week,
    )
    return ItemFigures(
        approved=approved,
        active=(
            approved and start_week <= cut_week and (cut_week <= finish_week or real_acum < total)
        ),
        pending=(
            approved
            and real_week is None
            and cut_week <= current_week
            and (prev_week > ZERO or real_acum < total)
        ),
        prev_acum=prev_acum,
        real_acum=real_acum,
        hh_acum=hh_acum,
        prev_week=prev_week,
        real_week=real_week,
        balance=balance,
        pct_prev=_share(prev_acum, total),
        pct_real=_share(real_acum, total),
        deviation_pp=(
            None if total <= ZERO else round_percent((real_acum - prev_acum) / total * PERCENT)
        ),
        week_adherence=_ratio(min(real_week, prev_week), prev_week)
        if real_week is not None and prev_week > ZERO
        else None,
        pf=round_percent(hh_acum / earned, 2) if earned > ZERO else None,
        window_adherence=_ratio(capped, prev_window),
        pf_window=round_percent(hh_window / (real_window * index_hh), 2)
        if real_window > ZERO
        else None,
        trend_week=trend_week,
        deviation_weeks=deviation_weeks,
        earned_hours=earned,
        planned_hours=planned_hours,
        total_hours=total_hours,
        week_earned_hours=ZERO if real_week is None else min(real_week, prev_week) * index_hh,
        week_planned_hours=prev_week * index_hh,
        window_appropriated=hh_window,
        window_earned=real_window * index_hh,
        window_planned_hours=prev_window * index_hh,
        window_capped_hours=capped * index_hh,
    )


def _planned_until(
    planned: Sequence[PlannedWeek], *, cut_week: str, window_start: str
) -> tuple[Decimal, Decimal, Decimal]:
    """O previsto acumulado até o corte, o da semana do corte e o da janela da média."""
    acum = ZERO
    week = ZERO
    window = ZERO
    for line in planned:
        if line.week > cut_week:
            continue
        acum += line.planned
        if line.week >= window_start:
            window += line.planned
        if line.week == cut_week:
            week = line.planned
    return acum, week, window


def _reported_until(
    reported: Sequence[ReportedWeek],
    *,
    planned_by_week: Mapping[str, Decimal],
    cut_week: str,
    window_start: str,
) -> tuple[Decimal, Decimal, Decimal | None, Decimal, Decimal, Decimal]:
    """O realizado e as HH até o corte, o da semana, os da janela e o realizado limitado ao previsto."""
    acum = ZERO
    hours = ZERO
    week: Decimal | None = None
    hh_window = ZERO
    real_window = ZERO
    capped = ZERO
    for line in reported:
        if line.week > cut_week:
            continue
        acum += line.realized
        hours += line.hh
        if line.week == cut_week:
            week = line.realized
        if line.week >= window_start:
            hh_window += line.hh
            real_window += line.realized
            capped += min(line.realized, planned_by_week.get(line.week, ZERO))
    return acum, hours, week, hh_window, real_window, capped


def _finish_trend(
    *,
    approved: bool,
    balance: Decimal,
    real_acum: Decimal,
    planned: Sequence[PlannedWeek],
    reported: Sequence[ReportedWeek],
    start_week: str,
    finish_week: str,
    cut_week: str,
) -> tuple[str | None, int | None]:
    """A semana de término pela tendência (earned schedule) e o desvio em semanas da LB.

    Sem saldo, a tendência é a última semana apontada; com saldo, o ritmo do realizado
    (semanas da LB equivalentes ao realizado sobre as semanas decorridas) projeta a duração.
    """
    if not approved or real_acum <= ZERO:
        return None, None
    if balance <= ZERO:
        weeks = sorted(line.week for line in reported if line.week <= cut_week)
        trend = weeks[-1] if weeks else None
    else:
        elapsed = weeks_between(start_week, cut_week)
        if elapsed is None:
            return None, None
        elapsed += 1
        equivalent = _equivalent_weeks(planned, real_acum)
        spi_t = equivalent / Decimal(elapsed)
        if spi_t <= ZERO:
            return None, None
        projected = max(elapsed, ceil(Decimal(len(planned)) / spi_t))
        trend = shift_week(start_week, projected - 1)
    if trend is None:
        return None, None
    return trend, weeks_between(finish_week, trend)


def _equivalent_weeks(planned: Sequence[PlannedWeek], real_acum: Decimal) -> Decimal:
    """As semanas da LB necessárias para chegar ao realizado acumulado (earned schedule)."""
    acum = ZERO
    equivalent = ZERO
    for index, line in enumerate(planned):
        if acum + line.planned >= real_acum:
            fraction = (real_acum - acum) / line.planned if line.planned > ZERO else ZERO
            return Decimal(index) + fraction
        acum += line.planned
        equivalent = Decimal(index + 1)
    return equivalent


def _share(value: Decimal, total: Decimal) -> Decimal | None:
    """O percentual de ``value`` sobre o total, com 1 casa; sem total, não há percentual."""
    if total <= ZERO:
        return None
    return round_percent(value / total * PERCENT)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """A razão em percentual, com 1 casa; sem denominador, não há razão."""
    if denominator <= ZERO:
        return None
    return round_percent(numerator / denominator * PERCENT)


def indicator_band(
    value: Decimal | None, bands: Sequence[Decimal], *, higher_is_better: bool
) -> str | None:
    """A faixa de um indicador: ``success``, ``warning`` ou ``danger`` (como no protótipo).

    ``higher_is_better`` diz o sentido bom: aderência e SPI sobem, fator de produtividade desce.
    """
    if value is None:
        return None
    if higher_is_better:
        return (
            SUCCESS_BAND
            if value >= bands[1]
            else (WARNING_BAND if value >= bands[0] else DANGER_BAND)
        )
    return (
        SUCCESS_BAND if value <= bands[0] else (WARNING_BAND if value <= bands[1] else DANGER_BAND)
    )


@dataclass(frozen=True)
class ItemWeek:
    """Uma semana da ficha do item: o previsto da LB, o apontamento e a aderência da semana."""

    week: str
    planned: Decimal
    realized: Decimal | None
    hh: Decimal | None
    adherence: Decimal | None
    pf: Decimal | None
    planned_pct: Decimal
    realized_pct: Decimal | None
    pending: bool


def item_weeks(
    *,
    start_week: str,
    total: Decimal,
    index_hh: Decimal,
    places: int,
    situation: str,
    planned: Sequence[PlannedWeek],
    reported: Sequence[ReportedWeek],
    current_week: str,
) -> tuple[ItemWeek, ...]:
    """A ficha do item, semana a semana, na união da distribuição com os apontamentos."""
    entries = {line.week: line for line in reported}
    planned_by_week = {line.week: line.planned for line in planned}
    weeks = sorted(set(planned_by_week) | set(entries))
    approved = situation == ITEM_APPROVED
    planned_acum = ZERO
    real_acum = ZERO
    rows: list[ItemWeek] = []
    for week in weeks:
        value = planned_by_week.get(week, ZERO)
        entry = entries.get(week)
        planned_acum += value
        if entry is not None:
            real_acum += entry.realized
        realized = entry.realized if entry is not None else None
        hours = entry.hh if entry is not None else None
        rows.append(
            ItemWeek(
                week=week,
                planned=round_quantity(value, places),
                realized=None if realized is None else round_quantity(realized, places),
                hh=hours,
                adherence=(
                    _ratio(min(realized, value), value)
                    if realized is not None and value > ZERO
                    else None
                ),
                pf=(
                    round_percent(hours / (realized * index_hh), 2)
                    if hours is not None and realized is not None and realized > ZERO
                    else None
                ),
                planned_pct=_share(planned_acum, total) or ZERO,
                realized_pct=None if realized is None else _share(real_acum, total),
                pending=(
                    entry is None and approved and week <= current_week and week >= start_week
                ),
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class QuantityIndicators:
    """Os indicadores da aba Quantidades: avanço, SPI de quantidades, aderência e FP."""

    items: int
    pct_prev: Decimal | None
    pct_real: Decimal | None
    spi: Decimal | None
    pf: Decimal | None
    pf_window: Decimal | None
    week_adherence: Decimal | None
    window_adherence: Decimal | None
    pending: int
    late_trend: int
    hh_appropriated: Decimal
    earned_hours: Decimal
    budgeted_hours: Decimal


def quantities_indicators(figures: Sequence[ItemFigures]) -> QuantityIndicators:
    """Os indicadores das quantidades: as horas ganhas somam unidades diferentes (o protótipo)."""
    total_hours = sum((item.total_hours for item in figures), ZERO)
    earned = sum((item.earned_hours for item in figures), ZERO)
    planned = sum((item.planned_hours for item in figures), ZERO)
    hours = sum((item.hh_acum for item in figures), ZERO)
    with_entry = [
        item for item in figures if item.week_planned_hours > ZERO and item.real_week is not None
    ]
    week_planned = sum((item.week_planned_hours for item in with_entry), ZERO)
    window_appropriated = sum((item.window_appropriated for item in figures), ZERO)
    window_earned = sum((item.window_earned for item in figures), ZERO)
    window_planned = sum((item.window_planned_hours for item in figures), ZERO)
    window_capped = sum((item.window_capped_hours for item in figures), ZERO)
    return QuantityIndicators(
        items=len(figures),
        pct_prev=_share(planned, total_hours),
        pct_real=_share(earned, total_hours),
        spi=round_percent(earned / planned, 2) if planned > ZERO else None,
        pf=round_percent(hours / earned, 2) if earned > ZERO else None,
        pf_window=round_percent(window_appropriated / window_earned, 2)
        if window_earned > ZERO
        else None,
        week_adherence=_ratio(
            sum((item.week_earned_hours for item in with_entry), ZERO), week_planned
        ),
        window_adherence=_ratio(window_capped, window_planned),
        pending=sum(1 for item in figures if item.pending),
        late_trend=sum(1 for item in figures if (item.deviation_weeks or 0) > 0),
        hh_appropriated=hours,
        earned_hours=round_quantity(earned, 0),
        budgeted_hours=round_quantity(total_hours, 0),
    )


@dataclass(frozen=True)
class GroupedItem:
    """Um item aprovado como o resumo por grupo o lê: grupo, unidade, total e indicadores."""

    group: str
    unit: str
    places: int
    total: Decimal
    figures: ItemFigures


@dataclass(frozen=True)
class GroupSummary:
    """O resumo de um grupo de itens aprovados na unidade deles."""

    group: str
    unit: str
    places: int
    items: int
    total: Decimal
    prev_acum: Decimal
    real_acum: Decimal
    prev_week: Decimal
    real_week: Decimal
    pct_prev: Decimal | None
    pct_real: Decimal | None


def group_summaries(items: Sequence[GroupedItem]) -> tuple[GroupSummary, ...]:
    """Os grupos dos itens aprovados, somando cada grupo na sua unidade."""
    buckets: dict[tuple[str, str], list[GroupedItem]] = {}
    for item in items:
        if item.figures.approved:
            buckets.setdefault((item.group, item.unit), []).append(item)
    summaries = [_group_summary(key[0], key[1], bucket) for key, bucket in sorted(buckets.items())]
    return tuple(summaries)


def _group_summary(group: str, unit: str, items: Sequence[GroupedItem]) -> GroupSummary:
    places = items[0].places
    total = sum((item.total for item in items), ZERO)
    prev_acum = sum((item.figures.prev_acum for item in items), ZERO)
    real_acum = sum((item.figures.real_acum for item in items), ZERO)
    return GroupSummary(
        group=group,
        unit=unit,
        places=places,
        items=len(items),
        total=total,
        prev_acum=prev_acum,
        real_acum=real_acum,
        prev_week=sum((item.figures.prev_week for item in items), ZERO),
        real_week=sum((item.figures.real_week or ZERO for item in items), ZERO),
        pct_prev=_share(prev_acum, total),
        pct_real=_share(real_acum, total),
    )


@dataclass(frozen=True)
class SeriesItem:
    """Um item aprovado como a série semanal o lê: total, índice orçado e os fatos."""

    total: Decimal
    index_hh: Decimal
    planned: tuple[PlannedWeek, ...]
    reported: tuple[ReportedWeek, ...]


@dataclass(frozen=True)
class QuantitySeries:
    """A série semanal do filtro: previsto e realizado (em quantidade ou horas ganhas)."""

    weeks: tuple[str, ...]
    planned: tuple[Decimal, ...]
    realized: tuple[Decimal | None, ...]
    planned_pct: tuple[Decimal | None, ...]
    realized_pct: tuple[Decimal | None, ...]
    in_hours: bool
    unit: str


def quantities_series(
    items: Sequence[SeriesItem], *, current_week: str, in_hours: bool, unit: str
) -> QuantitySeries:
    """A série semanal do filtro: a semana passada sem apontamento vale zero, a futura não existe.

    Quando o filtro mistura unidades, a série sai em horas ganhas (quantidade vezes índice
    orçado), que é o que soma unidades diferentes; a acumulada é percentual do total da série.
    """
    weeks = _series_weeks(items)
    total_value = sum(
        (item.total * (item.index_hh if in_hours else Decimal(1)) for item in items), ZERO
    )
    planned_acum = ZERO
    realized_acum = ZERO
    planned: list[Decimal] = []
    realized: list[Decimal | None] = []
    planned_pct: list[Decimal | None] = []
    realized_pct: list[Decimal | None] = []
    for week in weeks:
        week_planned = _week_planned(items, week, in_hours=in_hours)
        week_realized = _week_realized(items, week, in_hours=in_hours)
        planned_acum += week_planned
        planned.append(round_quantity(week_planned, 1))
        planned_pct.append(_share(planned_acum, total_value))
        if week > current_week:
            realized.append(None)
            realized_pct.append(None)
            continue
        realized_acum += week_realized or ZERO
        if week_realized is not None:
            realized.append(round_quantity(week_realized, 1))
        else:
            realized.append(None if week == current_week else ZERO)
        realized_pct.append(_share(realized_acum, total_value))
    return QuantitySeries(
        weeks=weeks,
        planned=tuple(planned),
        realized=tuple(realized),
        planned_pct=tuple(planned_pct),
        realized_pct=tuple(realized_pct),
        in_hours=in_hours,
        unit=unit,
    )


def _series_weeks(items: Sequence[SeriesItem]) -> tuple[str, ...]:
    weeks: set[str] = set()
    for item in items:
        weeks.update(line.week for line in item.planned)
        weeks.update(line.week for line in item.reported)
    return tuple(sorted(weeks))


def _week_planned(items: Sequence[SeriesItem], week: str, *, in_hours: bool) -> Decimal:
    total = ZERO
    for item in items:
        for line in item.planned:
            if line.week == week:
                total += line.planned * (item.index_hh if in_hours else Decimal(1))
    return total


def _week_realized(items: Sequence[SeriesItem], week: str, *, in_hours: bool) -> Decimal | None:
    total = ZERO
    found = False
    for item in items:
        for line in item.reported:
            if line.week == week:
                found = True
                total += line.realized * (item.index_hh if in_hours else Decimal(1))
    return total if found else None


def weekly_chart(series: QuantitySeries) -> dict[str, Any]:
    """O payload do gráfico de produção semanal: o servidor manda a quantidade de cada semana."""
    return {
        "titulo": "Produção semanal",
        "modo": "periodo",
        "formato": "numero",
        "unidade": series.unit,
        "casas": 1,
        "series": [
            {"id": "previsto", "rotulo": "Previsto (LB)", "papel": "linha-base", "tipo": "valor"},
            {"id": "realizado", "rotulo": "Realizado", "papel": "realizado", "tipo": "valor"},
        ],
        "periodos": _chart_periods(
            series, {"previsto": series.planned, "realizado": series.realized}
        ),
    }


def accumulated_chart(series: QuantitySeries) -> dict[str, Any]:
    """O payload do avanço acumulado: percentual do previsto e do realizado por semana."""
    return {
        "titulo": "Avanço acumulado",
        "modo": "acumulado",
        "formato": "pct",
        "unidade": "%",
        "casas": 1,
        "eixo_max": 100,
        "series": [
            {"id": "previsto", "rotulo": "Previsto (LB)", "papel": "linha-base", "tipo": "valor"},
            {"id": "realizado", "rotulo": "Realizado", "papel": "realizado", "tipo": "valor"},
        ],
        "periodos": _chart_periods(
            series, {"previsto": series.planned_pct, "realizado": series.realized_pct}
        ),
    }


def _chart_periods(
    series: QuantitySeries, values: Mapping[str, Sequence[Decimal | None]]
) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = []
    for index, week in enumerate(series.weeks):
        day = calendario.week_start(week)
        if day is None:
            continue
        periods.append(
            {
                "ano": day.year,
                "mes": day.month,
                "semana": day.isocalendar()[1],
                "valores": {
                    name: _chart_number(values[name][index]) for name in ("previsto", "realizado")
                },
            }
        )
    return periods


def _chart_number(value: Decimal | None) -> float | None:
    """O número do gráfico: o ``data-dados`` viaja em JSON, que não conhece ``Decimal``."""
    return None if value is None else float(value)


def revision_distribution(
    *,
    total: Decimal,
    frozen: Sequence[PlannedWeek],
    start_week: str,
    finish_week: str,
    profile: str,
    places: int,
) -> tuple[PlannedWeek, ...]:
    """Redistribui o saldo (novo total menos as semanas congeladas) da primeira semana livre em diante.

    As semanas até a atual ficam congeladas (o fato da LB); o saldo é distribuído pelo perfil
    entre as semanas livres, pelo maior resto. Novo total menor que as congeladas deixa saldo
    zero — a validação é quem recusa fechar a soma com o total.
    """
    frozen_total = sum((line.planned for line in frozen), ZERO)
    balance = max(ZERO, total - frozen_total)
    weeks = calendario.list_periods(WEEKLY, start_week, finish_week)
    values = distribute_total(balance, len(weeks), profile, places)
    return tuple(
        PlannedWeek(week=week, planned=value) for week, value in zip(weeks, values, strict=True)
    )


def frozen_planned(distribution: Sequence[PlannedWeek], cut_week: str) -> tuple[PlannedWeek, ...]:
    """As semanas congeladas da distribuição: as que ficam até a semana de corte."""
    return tuple(line for line in distribution if line.week <= cut_week)


def first_free_week(item_start_week: str, cut_week: str) -> str:
    """A primeira semana livre da revisão: a seguinte ao corte, ou o início do item, se posterior."""
    following = shift_week(cut_week, 1) or cut_week
    return item_start_week if item_start_week > following else following


# ── Horas efetivas e campo (ISSUE-047) ─────────────────────────────────────


PERIOD_WEEK = "semana"


PERIOD_WINDOW = "janela"


PERIOD_ALL = "tudo"


PERIODS = (PERIOD_WEEK, PERIOD_WINDOW, PERIOD_ALL)


# Os 12 motivos de parada e os 5 de trânsito da amostragem, como no protótipo.
STOP_REASONS = (
    "Direcionamento da liderança para execução",
    "Descanso entre atividades",
    "Término da atividade antecessora",
    "Raio de ação de içamento (munck, guindaste)",
    "Pit stop",
    "Raio de ação de máquina",
    "Dúvida de execução / interferência",
    "Mais pessoas que a frente de serviço comporta",
    "Material / insumo / acessório",
    "Sobreposição de atividades na própria frente",
    "Direito de recusa (trabalho seguro)",
    "Máquina ou equipamento indisponível",
)


TRANSIT_REASONS = (
    "Material / insumo / acessório",
    "Água / banheiro",
    "Entre frentes de serviço",
    "Ferramenta",
    "Máquina / equipamento",
)


# Os 10 motivos e as 5 responsabilidades da paralisação, como no protótipo.
STOPPAGE_REASONS = (
    "Chuva / condição climática",
    "Falta de material",
    "Falta de liberação de área / permissão de trabalho",
    "Interferência com a operação da planta",
    "Aguardando equipamento de içamento",
    "Quebra de máquina / equipamento",
    "Aguardando frente (atividade predecessora)",
    "Falta de projeto / dúvida técnica",
    "Parada de segurança",
    "Terceiros (concreteira, concessionária)",
)


RESPONSIBILITIES = ("Contratada", "Cliente", "Gerenciadora", "Clima", "Terceiros")


# Tempo perdido que não é da contratada: potencialmente excusável (base de pleito em Contratos).
EXTERNAL_RESPONSIBILITIES = ("Cliente", "Gerenciadora", "Terceiros")


SAMPLE_STOPPED = "Parado"


SAMPLE_TRANSIT = "Trânsito"


STOPPAGE_CREW = "Efetivo"


STOPPAGE_MACHINE = "Máquina/Equipamento"


STOPPAGE_KINDS = (STOPPAGE_CREW, STOPPAGE_MACHINE)


DEFAULT_DELAY_BANDS = (Decimal("15"), Decimal("30"))


# A margem em pontos percentuais que ainda vale atenção nas bandas de utilização e de trabalho.
BAND_MARGIN = Decimal("10")


MINUTES_PER_HOUR = Decimal(60)


def minutes_of(value: time) -> int:
    """Os minutos desde a meia-noite de um horário."""
    return value.hour * 60 + value.minute


def shift_hours(start: time, end: time) -> Decimal | None:
    """As horas de execução de um turno; nulo quando o término vem antes do início."""
    if end < start:
        return None
    return Decimal(minutes_of(end) - minutes_of(start)) / MINUTES_PER_HOUR


@dataclass(frozen=True)
class ShiftTimes:
    """Os três horários de um turno: chegada na frente, início e término das atividades."""

    arrival: time
    start: time
    end: time


@dataclass(frozen=True)
class FieldDayFigures:
    """Uma jornada lida: atrasos, execuções, capacidade produtiva e horas-homem (ISSUE-047)."""

    morning: ShiftTimes
    afternoon: ShiftTimes
    crew: int
    morning_delay_min: int
    afternoon_delay_min: int
    lunch_min: int
    morning_execution: Decimal | None
    afternoon_execution: Decimal | None
    capacity: Decimal
    utilization: Decimal
    effective_hh: Decimal
    idle_hh: Decimal
    week: str


def field_day_figures(
    *,
    day: date,
    crew: int,
    morning: ShiftTimes,
    afternoon: ShiftTimes,
    daily_hours: Decimal,
) -> FieldDayFigures:
    """As figuras da jornada: CP = execução da manhã + da tarde; utilização, atrasos e HH.

    HH efetivas = CP x efetivo; HH improdutivas = (jornada de referência - CP) x efetivo, sem
    contar a diferença negativa. Tudo arredondado como a tela mostra (D6: nada lê o relógio).
    """
    morning_execution = shift_hours(morning.start, morning.end)
    afternoon_execution = shift_hours(afternoon.start, afternoon.end)
    capacity = (morning_execution or ZERO) + (afternoon_execution or ZERO)
    utilization = round_percent(capacity / daily_hours * PERCENT, 1) if daily_hours > ZERO else ZERO
    return FieldDayFigures(
        morning=morning,
        afternoon=afternoon,
        crew=crew,
        morning_delay_min=minutes_of(morning.start) - minutes_of(morning.arrival),
        afternoon_delay_min=minutes_of(afternoon.start) - minutes_of(afternoon.arrival),
        lunch_min=minutes_of(afternoon.arrival) - minutes_of(morning.end),
        morning_execution=morning_execution,
        afternoon_execution=afternoon_execution,
        capacity=round_quantity(capacity, 2),
        utilization=utilization,
        effective_hh=round_quantity(capacity * crew, 1),
        idle_hh=round_quantity(max(ZERO, daily_hours - capacity) * crew, 1),
        week=calendario.iso_week(day),
    )


@dataclass(frozen=True)
class CapacitySummary:
    """O resumo das jornadas do filtro: médias de horário e de CP, somas de HH (Hhora das horas)."""

    records: int
    average_crew: Decimal | None
    morning: ShiftTimes | None
    afternoon: ShiftTimes | None
    morning_delay_min: Decimal | None
    afternoon_delay_min: Decimal | None
    lunch_min: Decimal | None
    morning_capacity: Decimal | None
    afternoon_capacity: Decimal | None
    capacity: Decimal | None
    utilization: Decimal | None
    effective_hh: Decimal
    idle_hh: Decimal


def capacity_summary(
    figures: Sequence[FieldDayFigures], *, daily_hours: Decimal
) -> CapacitySummary:
    """O resumo das jornadas: médias como o protótipo as mostra e somas de HH inteiras."""
    capacity = _average([figure.capacity for figure in figures])
    utilization = (
        round_percent(capacity / daily_hours * PERCENT, 1)
        if capacity is not None and daily_hours > ZERO
        else None
    )
    return CapacitySummary(
        records=len(figures),
        average_crew=_rounded_average([figure.crew for figure in figures], 1),
        morning=_average_times([figure.morning for figure in figures]),
        afternoon=_average_times([figure.afternoon for figure in figures]),
        morning_delay_min=_rounded_average([figure.morning_delay_min for figure in figures], 0),
        afternoon_delay_min=_rounded_average([figure.afternoon_delay_min for figure in figures], 0),
        lunch_min=_rounded_average([figure.lunch_min for figure in figures], 0),
        morning_capacity=_rounded_average([figure.morning_execution for figure in figures], 2),
        afternoon_capacity=_rounded_average([figure.afternoon_execution for figure in figures], 2),
        capacity=None if capacity is None else round_quantity(capacity, 2),
        utilization=utilization,
        effective_hh=round_quantity(sum((figure.effective_hh for figure in figures), ZERO), 0),
        idle_hh=round_quantity(sum((figure.idle_hh for figure in figures), ZERO), 0),
    )


def _average(values: Sequence[Decimal | None]) -> Decimal | None:
    """A média dos valores presentes; lista vazia (ou toda nula) devolve nulo."""
    kept = [value for value in values if value is not None]
    if not kept:
        return None
    return sum(kept, ZERO) / Decimal(len(kept))


def _rounded_average(values: Sequence[Decimal | int | None], places: int) -> Decimal | None:
    found = _average([None if value is None else Decimal(value) for value in values])
    return None if found is None else round_quantity(found, places)


def _average_times(shifts: Sequence[ShiftTimes]) -> ShiftTimes | None:
    """O turno médio das jornadas: a média dos minutos de cada marco, em hora cheia."""
    if not shifts:
        return None
    return ShiftTimes(
        arrival=_mean_time([minutes_of(shift.arrival) for shift in shifts]),
        start=_mean_time([minutes_of(shift.start) for shift in shifts]),
        end=_mean_time([minutes_of(shift.end) for shift in shifts]),
    )


def _mean_time(values: Sequence[int]) -> time:
    total = sum(values, 0)
    minutes = round(Decimal(total) / Decimal(len(values)))
    return time(hour=(minutes // 60) % 24, minute=minutes % 60)


@dataclass(frozen=True)
class SampleCounts:
    """As pessoas observadas numa rodada: trabalhando, em trânsito e paradas."""

    working: int
    transit: int
    stopped: int


@dataclass(frozen=True)
class SampleShare:
    """O resumo da amostragem: totais de pessoas e os três percentuais."""

    records: int
    people: int
    working: int
    transit: int
    stopped: int
    working_pct: Decimal | None
    transit_pct: Decimal | None
    stopped_pct: Decimal | None


def sample_share(rows: Sequence[SampleCounts]) -> SampleShare:
    """O resumo da amostragem: soma as pessoas e divide cada estado pelo total observado."""
    working = sum(row.working for row in rows)
    transit = sum(row.transit for row in rows)
    stopped = sum(row.stopped for row in rows)
    people = working + transit + stopped
    return SampleShare(
        records=len(rows),
        people=people,
        working=working,
        transit=transit,
        stopped=stopped,
        working_pct=_people_share(working, people),
        transit_pct=_people_share(transit, people),
        stopped_pct=_people_share(stopped, people),
    )


def _people_share(people: int, total: int) -> Decimal | None:
    if total <= 0:
        return None
    return round_percent(Decimal(people) / Decimal(total) * PERCENT, 2)


@dataclass(frozen=True)
class ReasonTotal:
    """Um motivo do Pareto: o total e, no Pareto, o percentual e o acumulado."""

    reason: str
    total: int
    percent: Decimal | None
    accumulated: Decimal | None


def reason_pareto(counts: Mapping[str, int], *, catalog: Sequence[str]) -> tuple[ReasonTotal, ...]:
    """O Pareto dos motivos: ordem decrescente do total, com o percentual e o acumulado.

    O empate fica com a ordem do catálogo do protótipo; motivo fora do catálogo entra depois,
    em ordem alfabética, para nada sumir da tela.
    """
    total = sum(counts.values())
    ordered = sorted(
        counts.items(),
        key=lambda item: (-item[1], _catalog_index(item[0], catalog), item[0]),
    )
    accumulated = 0
    rows: list[ReasonTotal] = []
    for reason, amount in ordered:
        accumulated += amount
        rows.append(
            ReasonTotal(
                reason=reason,
                total=amount,
                percent=_reason_share(amount, total),
                accumulated=_reason_share(accumulated, total),
            )
        )
    return tuple(rows)


def _reason_share(value: int, total: int) -> Decimal | None:
    if total <= 0:
        return None
    return round_percent(Decimal(value) / Decimal(total) * PERCENT, 1)


def _catalog_index(reason: str, catalog: Sequence[str]) -> int:
    return catalog.index(reason) if reason in catalog else len(catalog)


@dataclass(frozen=True)
class StoppageFigures:
    """Uma paralisação lida: as horas, o total (Hhora ou Mhora) e se é externa."""

    kind: str
    reason: str
    responsibility: str
    hours: Decimal
    total: Decimal
    external: bool
    week: str


def stoppage_figures(
    *,
    day: date,
    kind: str,
    reason: str,
    responsibility: str,
    quantity: Decimal,
    start: time,
    end: time,
) -> StoppageFigures:
    """As figuras da paralisação: horas = término menos início; total = quantidade x horas.

    O total é Hhora no efetivo (pessoas x horas) e Mhora na máquina ou equipamento
    (unidades x horas); o tipo escolhe o nome, a conta é a mesma.
    """
    hours = shift_hours(start, end) or ZERO
    return StoppageFigures(
        kind=kind,
        reason=reason,
        responsibility=responsibility,
        hours=round_quantity(hours, 2),
        total=round_quantity(hours * quantity, 1),
        external=responsibility in EXTERNAL_RESPONSIBILITIES,
        week=calendario.iso_week(day),
    )


@dataclass(frozen=True)
class StoppageTotal:
    """Um agrupamento da paralisação: a chave, o total e o número de eventos."""

    key: str
    total: Decimal
    events: int


@dataclass(frozen=True)
class StoppageSummary:
    """O resumo das paralisações: Hhora, Mhora, as externas e os agrupamentos."""

    events: int
    crew_hours: Decimal
    machine_hours: Decimal
    external_hours: Decimal
    client_hours: Decimal
    weather_hours: Decimal
    by_reason: tuple[StoppageTotal, ...]
    by_responsibility: tuple[StoppageTotal, ...]
    machine_by_reason: tuple[StoppageTotal, ...]


def stoppage_summary(rows: Sequence[StoppageFigures]) -> StoppageSummary:
    """O resumo das paralisações: Hhora do efetivo, Mhora das máquinas e os agrupamentos."""
    return StoppageSummary(
        events=len(rows),
        crew_hours=_sum_totals(row for row in rows if row.kind == STOPPAGE_CREW),
        machine_hours=_sum_totals(row for row in rows if row.kind != STOPPAGE_CREW),
        external_hours=_sum_totals(
            row for row in rows if row.kind == STOPPAGE_CREW and row.external
        ),
        client_hours=_sum_totals(
            row for row in rows if row.kind == STOPPAGE_CREW and row.responsibility == "Cliente"
        ),
        weather_hours=_sum_totals(
            row for row in rows if row.kind == STOPPAGE_CREW and row.responsibility == "Clima"
        ),
        by_reason=_group_stoppages([row for row in rows if row.kind == STOPPAGE_CREW], "reason"),
        by_responsibility=_group_stoppages(
            [row for row in rows if row.kind == STOPPAGE_CREW], "responsibility"
        ),
        machine_by_reason=_group_stoppages(
            [row for row in rows if row.kind != STOPPAGE_CREW], "reason"
        ),
    )


def _sum_totals(rows: Iterable[StoppageFigures]) -> Decimal:
    return round_quantity(sum((row.total for row in rows), ZERO), 1)


def _group_stoppages(rows: Sequence[StoppageFigures], attribute: str) -> tuple[StoppageTotal, ...]:
    grouped: dict[str, list[StoppageFigures]] = {}
    for row in rows:
        grouped.setdefault(getattr(row, attribute), []).append(row)
    totals = [
        StoppageTotal(key=key, total=_sum_totals(group), events=len(group))
        for key, group in grouped.items()
    ]
    return tuple(sorted(totals, key=lambda item: (-item.total, item.key)))


def utilization_band(utilization: Decimal | None, *, target: Decimal) -> str | None:
    """A faixa da utilização: na meta ou acima é bom, até 10 p.p. abaixo é atenção."""
    if utilization is None:
        return None
    if utilization >= target:
        return "success"
    return "warning" if utilization >= target - BAND_MARGIN else "danger"


def working_band(working_pct: Decimal | None, *, target: Decimal) -> str | None:
    """A faixa do % trabalhando: na meta ou acima é bom, até 10 p.p. abaixo é atenção."""
    if working_pct is None:
        return None
    if working_pct >= target:
        return "success"
    return "warning" if working_pct >= target - BAND_MARGIN else "danger"


def start_delay_band(minutes: Decimal | None, bands: Sequence[Decimal]) -> str | None:
    """A faixa do atraso de início: até o primeiro limite é bom, até o segundo é atenção."""
    if minutes is None:
        return None
    if minutes <= bands[0]:
        return "success"
    return "warning" if minutes <= bands[1] else "danger"


def hours_window(
    period: str,
    *,
    cut_week: str,
    window_weeks: int,
    reference_date: date,
) -> tuple[date | None, date]:
    """A janela do período do filtro: de onde até onde os registros entram.

    ``semana`` é a semana de corte; ``janela`` são as últimas N semanas; ``tudo`` começa vazio.
    O fim nunca passa da data de referência (D6); semana inválida cai na semana da referência.
    """
    monday = calendario.week_start(cut_week) or calendario.week_start(
        calendario.iso_week(reference_date)
    )
    if monday is None:
        monday = reference_date
    end = calendario.add_days(monday, DAYS_IN_WEEK - 1)
    if end > reference_date:
        end = reference_date
    if period == PERIOD_ALL:
        return None, end
    if period == PERIOD_WINDOW:
        first = shift_week(calendario.iso_week(monday), -(window_weeks - 1))
        monday = calendario.week_start(first) if first is not None else monday
    return monday, end


# ── KPIs de performance da Produtividade (ISSUE-048) ───────────────────────


# A janela da tendência semanal por empresa, como no protótipo: 12 semanas até o corte.
TREND_WEEKS = 12


PERFORMANCE_ORIGIN = "Produtividade"


PERFORMANCE_ACTION_PREFIX = "PRD"


_ACTION_REFERENCE = re.compile(r"^PRD-(\d{4}-S\d{2})-(\d+)$")


# Os indicadores que podem pôr a empresa em alerta ou em atenção, na ordem do protótipo.
PERFORMANCE_BAND_KEYS = ("adherence", "pf", "spi", "working", "utilization")


@dataclass(frozen=True)
class PlannedHours:
    """O previsto da linha de base numa semana, em horas ganhas (quantidade x índice orçado)."""

    week: str
    hours: Decimal


@dataclass(frozen=True)
class ScheduleTrend:
    """A tendência de término pelo prazo agregado (earned schedule) de um conjunto de itens."""

    equivalent_weeks: Decimal
    elapsed_weeks: int
    spi_t: Decimal | None
    trend_week: str | None
    slip_weeks: int | None


def schedule_trend(
    planned: Sequence[PlannedHours], earned_hours: Decimal, *, cut_week: str
) -> ScheduleTrend:
    """As semanas da LB equivalentes ao realizado sobre as decorridas: o SPI(t) agregado.

    ``planned`` é o previsto da linha de base somado por semana, em horas ganhas; o ES é
    interpolado na semana em que o acumulado alcança o realizado. Sem realizado não há
    índice; o atraso em semanas compara o término projetado com o fim da linha de base.
    """
    if not planned or earned_hours <= ZERO:
        return ScheduleTrend(
            equivalent_weeks=ZERO, elapsed_weeks=0, spi_t=None, trend_week=None, slip_weeks=None
        )
    elapsed = weeks_between(planned[0].week, cut_week)
    if elapsed is None:
        return ScheduleTrend(
            equivalent_weeks=ZERO, elapsed_weeks=0, spi_t=None, trend_week=None, slip_weeks=None
        )
    elapsed += 1
    equivalent = _equivalent_hours(planned, earned_hours)
    spi_t = round_percent(equivalent / Decimal(elapsed), 2)
    if spi_t <= ZERO:
        return ScheduleTrend(
            equivalent_weeks=equivalent,
            elapsed_weeks=elapsed,
            spi_t=None,
            trend_week=None,
            slip_weeks=None,
        )
    duration = Decimal(len(planned))
    projected = max(elapsed, ceil(duration / spi_t))
    trend = shift_week(planned[0].week, projected - 1)
    slip = None if trend is None else weeks_between(planned[-1].week, trend)
    return ScheduleTrend(
        equivalent_weeks=equivalent,
        elapsed_weeks=elapsed,
        spi_t=spi_t,
        trend_week=trend,
        slip_weeks=slip,
    )


def _equivalent_hours(planned: Sequence[PlannedHours], earned_hours: Decimal) -> Decimal:
    """As semanas da LB necessárias para chegar ao realizado acumulado (earned schedule)."""
    acum = ZERO
    equivalent = ZERO
    for index, line in enumerate(planned):
        if acum + line.hours >= earned_hours:
            fraction = (earned_hours - acum) / line.hours if line.hours > ZERO else ZERO
            return Decimal(index) + fraction
        acum += line.hours
        equivalent = Decimal(index + 1)
    return equivalent


def stoppage_share(crew_hours: Decimal, available_hh: Decimal) -> Decimal | None:
    """As HH paradas como percentual das HH disponíveis, com 2 casas; sem disponível, nada."""
    if available_hh <= ZERO:
        return None
    return round_percent(crew_hours / available_hh * PERCENT, 2)


def performance_action_reference(company_id: int, cut_week: str) -> str:
    """A referência da ação da empresa na semana: ``PRD-2026-S39-01`` (semana e empresa)."""
    return f"{PERFORMANCE_ACTION_PREFIX}-{cut_week}-{company_id:02d}"


def performance_action_parts(reference: str) -> tuple[str, int] | None:
    """A semana e a empresa de uma referência ``PRD-2026-S39-01``; ``None`` fora do formato."""
    found = _ACTION_REFERENCE.fullmatch(reference.strip())
    if found is None:
        return None
    return found[1], int(found[2])


@dataclass(frozen=True)
class PerformanceBands:
    """As faixas (success, warning ou danger) dos cinco indicadores de um bloco."""

    adherence: str | None = None
    pf: str | None = None
    spi: str | None = None
    working: str | None = None
    utilization: str | None = None


def performance_alerts(bands: PerformanceBands) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Os indicadores em alerta (danger) e em atenção (warning), na ordem do protótipo."""
    alerts = tuple(key for key in PERFORMANCE_BAND_KEYS if getattr(bands, key) == DANGER_BAND)
    attentions = tuple(key for key in PERFORMANCE_BAND_KEYS if getattr(bands, key) == WARNING_BAND)
    return alerts, attentions


@dataclass(frozen=True)
class TrendInput:
    """Os fatos de uma semana de uma empresa: o apontamento das quantidades e o campo."""

    appropriated: Decimal
    earned: Decimal
    planned: Decimal
    capped: Decimal
    working: int
    transit: int
    stopped: int
    capacities: tuple[Decimal, ...]


@dataclass(frozen=True)
class TrendWeek:
    """Uma semana da tendência por empresa: FP, aderência, % trabalhando e CP.

    ``adherence_ratio`` e ``working_ratio`` levam o numerador e o denominador crus da
    semana: o gráfico da biblioteca resume o período pelo par, nunca pelo percentual pronto.
    """

    week: str
    pf: Decimal | None
    adherence: Decimal | None
    working_pct: Decimal | None
    capacity: Decimal | None
    adherence_ratio: tuple[Decimal, Decimal] | None
    working_ratio: tuple[Decimal, Decimal] | None


def weekly_trend(weeks: Sequence[str], inputs: Mapping[str, TrendInput]) -> tuple[TrendWeek, ...]:
    """A tendência semanal por empresa: uma linha por semana, sem dado a semana sai vazia."""
    rows: list[TrendWeek] = []
    for week in weeks:
        data = inputs.get(week)
        if data is None:
            rows.append(
                TrendWeek(
                    week=week,
                    pf=None,
                    adherence=None,
                    working_pct=None,
                    capacity=None,
                    adherence_ratio=None,
                    working_ratio=None,
                )
            )
            continue
        rows.append(_trend_week(week, data))
    return tuple(rows)


def _trend_week(week: str, data: TrendInput) -> TrendWeek:
    people = data.working + data.transit + data.stopped
    return TrendWeek(
        week=week,
        pf=round_percent(data.appropriated / data.earned, 2) if data.earned > ZERO else None,
        adherence=_ratio(data.capped, data.planned),
        working_pct=(
            round_percent(Decimal(data.working) / Decimal(people) * PERCENT, 2)
            if people > 0
            else None
        ),
        capacity=_rounded_average(data.capacities, 2),
        adherence_ratio=(data.capped, data.planned) if data.planned > ZERO else None,
        working_ratio=(Decimal(data.working), Decimal(people)) if people > 0 else None,
    )


@dataclass(frozen=True)
class TrendSeries:
    """Uma empresa no gráfico da tendência: o rótulo e o par (num, den) de cada semana."""

    label: str
    ratios: tuple[tuple[Decimal, Decimal] | None, ...]


def ratio_chart(
    title: str,
    *,
    weeks: Sequence[str],
    series: Sequence[TrendSeries],
    target: Decimal,
    target_label: str,
) -> dict[str, Any]:
    """O ``data-dados`` do gráfico semanal de uma taxa (D11), com a meta em tracejado."""
    identifiers = [f"serie-{index + 1}" for index in range(len(series))]
    chart_series: list[dict[str, Any]] = [
        {"id": identifier, "rotulo": item.label}
        for identifier, item in zip(identifiers, series, strict=True)
    ]
    chart_series.append({"id": "meta", "rotulo": target_label, "papel": "linha-base"})
    periods: list[dict[str, Any]] = []
    for index, week in enumerate(weeks):
        day = week_start(week)
        if day is None:
            continue
        values: dict[str, Any] = {}
        for identifier, item in zip(identifiers, series, strict=True):
            ratio = item.ratios[index]
            values[identifier] = (
                None
                if ratio is None
                else {"num": _chart_number(ratio[0]), "den": _chart_number(ratio[1])}
            )
        values["meta"] = {"num": _chart_number(target), "den": 100.0}
        periods.append(
            {
                "ano": day.year,
                "mes": day.month,
                "semana": day.isocalendar()[1],
                "valores": values,
            }
        )
    return {
        "titulo": title,
        "modo": "periodo",
        "formato": "pct",
        "unidade": "%",
        "casas": 1,
        "casas_dica": 1,
        "eixo_max": 100,
        "series": chart_series,
        "periodos": periods,
    }
