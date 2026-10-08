"""Derived numbers of the weekly schedule, never typed by hand (D10).

Total Semanal, PPC and Aderência are computed by the system. An activity carries
three parallel arrays of seven days, Monday through Sunday: the planned, the done
in the day shift and the done in the night shift. Everything here is a projection
of those three, as the app computes it: the same rounding, the same bands.

| Termo de negócio | Nome no código |
|---|---|
| Total previsto da semana | ``planned_total`` |
| Total realizado (dia mais noite) | ``done_total`` |
| PPC da atividade | ``activity_ppc`` |
| Aderência da programação | ``schedule_adherence`` |
| PPC médio | ``mean_ppc`` |
| Faixa de desempenho | ``performance_band`` |
| Desvio do realizado | ``deviation_percent`` |
| Curva S do avanço | ``curve_points`` |
| Ranking por contratada/frente/encarregado | ``ranking`` |
| Distribuição por situação/aprovação/faixa | ``situation_distribution`` |
| Mapa de calor dia x frente | ``heatmap_day_front``, ``heat_band``, ``heat_faixas`` |
| Turnos por dia | ``shifts_by_day`` |
| Gargalos da semana | ``bottlenecks`` |
| Evolução da aderência por contratada | ``evolution_by_company`` |

No function reads the clock or the database.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from src.modulos.programacao_semanal import weeks

DAYS = 7
DAY_LABELS = ("2ª", "3ª", "4ª", "5ª", "6ª", "Sáb", "Dom")
DAY_NAMES = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")

# One scale for the whole screen: the table, the gauges and the charts tell one story.
HIGH_BAND = 80.0
MEDIUM_BAND = 60.0

BAND_HIGH = "alta"
BAND_MEDIUM = "media"
BAND_LOW = "baixa"

SITUATION_DRAFT = "em_elaboracao"
SITUATION_VALIDATED = "validada"
SITUATION_PUBLISHED = "publicada"
SITUATIONS = (SITUATION_DRAFT, SITUATION_VALIDATED, SITUATION_PUBLISHED)

APPROVAL_PENDING = "pendente"
APPROVAL_APPROVED = "aprovado"
APPROVALS = (APPROVAL_PENDING, APPROVAL_APPROVED)

SITUATION_LABELS = {
    SITUATION_DRAFT: "Em elaboração",
    SITUATION_VALIDATED: "Validada",
    SITUATION_PUBLISHED: "Publicada",
}
APPROVAL_LABELS = {APPROVAL_PENDING: "Pendente", APPROVAL_APPROVED: "Aprovado"}


def to_number(value: object, default: float = 0.0) -> float:
    """Read a number that may arrive as Brazilian text (``"1.234,5"``); the default when it is not."""
    if value is None or value == "" or isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return default


def seven_days(values: Iterable[object] | None = None) -> list[float]:
    """Normalise any day array to exactly seven numbers: cut the excess, fill with zeros."""
    numbers = [to_number(value) for value in (values or [])][:DAYS]
    return numbers + [0.0] * (DAYS - len(numbers))


def planned_total(planned_days: Sequence[object], headline: object = 0.0) -> float:
    """The planned total of the week: the days win over the headline figure."""
    if planned_days:
        return _total(planned_days)
    return round(to_number(headline), 2)


def done_total(day_shift: Sequence[object], night_shift: Sequence[object]) -> float:
    """The done total of the week: the day shift plus the night shift."""
    return round(_total(day_shift) + _total(night_shift), 2)


def activity_ppc(planned: float, done: float) -> float:
    """PPC of one activity: done over planned, in percent; zero when nothing was planned."""
    if not planned:
        return 0.0
    return round(done / planned * 100, 2)


def performance_band(value: float, *, high: float = HIGH_BAND, medium: float = MEDIUM_BAND) -> str:
    """The band of a percentage: ``alta`` from ``high``, ``media`` from ``medium``, else ``baixa``."""
    if value >= high:
        return BAND_HIGH
    if value >= medium:
        return BAND_MEDIUM
    return BAND_LOW


def deviation_percent(done: float, planned: float) -> float:
    """How far the done is from the plan, in percent: the rule of the app, without rounding.

    It is the percentage the reporting panel shows and the one the deviation rule
    compares with the parameter's limit: ``abs(done - planned) / planned * 100``.
    Nothing planned means no deviation to accuse.
    """
    if not planned:
        return 0.0
    return abs(done - planned) / planned * 100


@dataclass(frozen=True)
class ActivityFigures:
    """The seven-day arrays of an activity and every number derived from them."""

    planned_days: tuple[float, ...]
    day_shift: tuple[float, ...]
    night_shift: tuple[float, ...]
    day_totals: tuple[float, ...]
    planned_total: float
    done_total: float
    ppc: float
    band: str
    has_done: bool


def figures_of(
    planned_days: Iterable[object] | None,
    day_shift: Iterable[object] | None = None,
    night_shift: Iterable[object] | None = None,
    *,
    headline: object = 0.0,
) -> ActivityFigures:
    """Fill every derived field of an activity from its three day arrays (and its headline)."""
    planned = seven_days(planned_days)
    day = seven_days(day_shift)
    night = seven_days(night_shift)

    planned_sum = planned_total(planned, headline)
    if planned_sum == 0 and to_number(headline) > 0:
        planned_sum = round(to_number(headline), 2)
    done_sum = done_total(day, night)
    ppc = activity_ppc(planned_sum, done_sum)
    return ActivityFigures(
        planned_days=tuple(planned),
        day_shift=tuple(day),
        night_shift=tuple(night),
        day_totals=tuple(round(day[index] + night[index], 2) for index in range(DAYS)),
        planned_total=planned_sum,
        done_total=done_sum,
        ppc=ppc,
        band=performance_band(ppc),
        has_done=done_sum > 0,
    )


def schedule_adherence(activities: Iterable[ActivityFigures]) -> float:
    """Adherence of a set: the sum of the done over the sum of the planned, in percent.

    It is not the average of the PPCs: a large activity weighs more than a small one.
    """
    items = list(activities)
    planned = sum(item.planned_total for item in items)
    if not planned:
        return 0.0
    done = sum(item.done_total for item in items)
    return round(done / planned * 100, 2)


def mean_ppc(activities: Iterable[ActivityFigures]) -> float:
    """The unweighted mean of the PPCs of the activities that have a plan."""
    values = [item.ppc for item in activities if item.planned_total > 0]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _total(values: Sequence[object]) -> float:
    return round(sum(to_number(value) for value in values), 2)


# ── The physical S-curve of the week (ISSUE-055) ─────────────────────────
#
# Ported from the app's ``indicadores.curva_s``: the units of the activities are
# not comparable (kg of rebar with m³ of soil), so the curve is built on the
# completion share of each activity, with equal weight per activity, and the
# denominator of an activity is its scope over the whole horizon. The app's
# legend says it: the curve is not volume.


@dataclass(frozen=True)
class CurveActivity:
    """One activity inside the curve horizon: its week, its identity and its totals.

    ``identity`` is the exclusive ID, the same activity followed across weeks; the
    ``planned_total`` accumulates the scope of that ID over the horizon.
    """

    week: str
    identity: str
    planned_total: float
    done_total: float


@dataclass(frozen=True)
class CurvePoint:
    """One week of the curve: the share of the period and the running totals."""

    week: str
    period: str
    base: float
    planned: float
    done: float
    base_accumulated: float
    planned_accumulated: float
    done_accumulated: float


def curve_points(activities: Iterable[CurveActivity]) -> list[CurvePoint]:
    """The S-curve, one point per week, over the horizon the caller collected.

    Three series, as the app draws them: the **base** spreads the scope evenly over
    the weeks (the reference pace), the **planned** is what the programming delivers
    and the **done** is what the week actually delivered. Nothing here reads the
    clock: the weeks come in the activities, in the order the caller read them.
    """
    items = list(activities)
    by_week: dict[str, list[CurveActivity]] = {}
    for item in items:
        if item.week:
            by_week.setdefault(item.week, []).append(item)
    if not by_week:
        return []

    scope: dict[str, float] = {}
    for item in items:
        scope[item.identity] = scope.get(item.identity, 0.0) + item.planned_total
    weighted = {identity for identity, total in scope.items() if total > 0}
    weight = 100.0 / len(weighted) if weighted else 0.0

    ordered = sorted(by_week, key=weeks.sort_key)
    step = 100.0 / len(ordered)
    points: list[CurvePoint] = []
    base_accumulated = 0.0
    planned_accumulated = 0.0
    done_accumulated = 0.0
    for index, week in enumerate(ordered):
        planned = 0.0
        done = 0.0
        for item in by_week[week]:
            total = scope.get(item.identity, 0.0)
            if total <= 0:
                continue
            planned += weight * (item.planned_total / total)
            done += weight * (item.done_total / total)
        base_accumulated = round(step * (index + 1), 2)
        planned_accumulated = round(planned_accumulated + planned, 2)
        done_accumulated = round(done_accumulated + done, 2)
        points.append(
            CurvePoint(
                week=week,
                period=weeks.period_label(week),
                base=round(step, 2),
                planned=round(planned, 2),
                done=round(done, 2),
                base_accumulated=base_accumulated,
                planned_accumulated=planned_accumulated,
                done_accumulated=min(done_accumulated, 999.0),
            )
        )
    return points


# ── The dashboard: the week read as an operation (ISSUE-056) ─────────────
#
# Ported from the app's ``indicadores``: the indicators the dashboard draws, over
# the same figures of the matrix. Every function here is pure and returns
# quantities — an adherence of a group is the sum of the done over the sum of the
# planned, and the evolution sends the pair of each week so the chart can aggregate
# by period (the rate of a month is not the mean of its weekly rates). The heatmap
# paints by the module's single performance scale (60/80), which is also the band
# of the table, the matrix and the spreadsheet.

BOTTLENECK_LIMIT = 8
NO_KEY = "—"

# The tone and the icon of each band in the day-by-front heatmap (D11); the icon is
# the direction of the value, so the color is never the only signal.
HEAT_TONES = {BAND_HIGH: "ok", BAND_MEDIUM: "atencao", BAND_LOW: "erro"}
HEAT_ICONS = {BAND_HIGH: "sobe", BAND_MEDIUM: "igual", BAND_LOW: "desce"}


@dataclass(frozen=True)
class IndicatorActivity:
    """One activity as the dashboard reads it: the cut keys and the figures of the week."""

    week: str
    identity: str
    description: str
    project_label: str
    location: str
    company: str
    foreman: str
    unit: str
    situation: str
    approval: str
    figures: ActivityFigures


@dataclass(frozen=True)
class RankingLine:
    """One group of a breakdown with its whole indicator set."""

    label: str
    activities: int
    adherence: float
    mean_ppc: float
    planned: float
    done: float
    pending: int


def ranking(activities: Iterable[IndicatorActivity], attribute: str) -> list[RankingLine]:
    """Break the activities by one key and sort the worst adherence first, as the app.

    A breakdown exists to show where to act, so the worst group leads the list; the
    label breaks ties, which keeps the order stable between calls.
    """
    groups: dict[str, list[IndicatorActivity]] = {}
    for item in activities:
        key = str(getattr(item, attribute) or NO_KEY)
        groups.setdefault(key, []).append(item)
    lines = [
        RankingLine(
            label=key,
            activities=len(items),
            adherence=schedule_adherence([item.figures for item in items]),
            mean_ppc=mean_ppc([item.figures for item in items]),
            planned=round(sum(item.figures.planned_total for item in items), 2),
            done=round(sum(item.figures.done_total for item in items), 2),
            pending=sum(1 for item in items if item.approval == APPROVAL_PENDING),
        )
        for key, items in groups.items()
    ]
    lines.sort(key=lambda line: (line.adherence, line.label))
    return lines


@dataclass(frozen=True)
class StatusSegment:
    """One slice of a status block: how many activities are in one state."""

    key: str
    label: str
    value: int
    tone: str


@dataclass(frozen=True)
class StatusBlock:
    """One reading of the week: the flow, the approval of the done work or the PPC band."""

    title: str
    segments: tuple[StatusSegment, ...]


def situation_distribution(activities: Iterable[IndicatorActivity]) -> tuple[StatusBlock, ...]:
    """Where the week sits: the flow, the approval and the PPC band, each in counts.

    The approval has three readings, as the app: approved, waiting for the inspector
    (there is done work) and without done work.
    """
    items = list(activities)
    situations = dict.fromkeys(SITUATIONS, 0)
    approval = {APPROVAL_APPROVED: 0, APPROVAL_PENDING: 0, "sem_realizado": 0}
    bands = {BAND_HIGH: 0, BAND_MEDIUM: 0, BAND_LOW: 0}
    for item in items:
        if item.situation in situations:
            situations[item.situation] += 1
        if not item.figures.has_done:
            approval["sem_realizado"] += 1
        elif item.approval == APPROVAL_APPROVED:
            approval[APPROVAL_APPROVED] += 1
        else:
            approval[APPROVAL_PENDING] += 1
        bands[item.figures.band] += 1
    return (
        StatusBlock(
            title="Situação da programação",
            segments=(
                StatusSegment(
                    SITUATION_PUBLISHED, "Publicada", situations[SITUATION_PUBLISHED], "ok"
                ),
                StatusSegment(
                    SITUATION_VALIDATED, "Validada", situations[SITUATION_VALIDATED], "info"
                ),
                StatusSegment(
                    SITUATION_DRAFT, "Em elaboração", situations[SITUATION_DRAFT], "atencao"
                ),
            ),
        ),
        StatusBlock(
            title="Aprovação do realizado",
            segments=(
                StatusSegment(APPROVAL_APPROVED, "Aprovado", approval[APPROVAL_APPROVED], "ok"),
                StatusSegment(
                    APPROVAL_PENDING, "Aguardando fiscal", approval[APPROVAL_PENDING], "atencao"
                ),
                StatusSegment(
                    "sem_realizado", "Sem realizado", approval["sem_realizado"], "neutro"
                ),
            ),
        ),
        StatusBlock(
            title="Faixa de PPC",
            segments=(
                StatusSegment(BAND_HIGH, f"{HIGH_BAND:g}% ou mais", bands[BAND_HIGH], "ok"),
                StatusSegment(
                    BAND_MEDIUM,
                    f"{MEDIUM_BAND:g} a {HIGH_BAND - 1:g}%",
                    bands[BAND_MEDIUM],
                    "atencao",
                ),
                StatusSegment(BAND_LOW, f"Abaixo de {MEDIUM_BAND:g}%", bands[BAND_LOW], "erro"),
            ),
        ),
    )


@dataclass(frozen=True)
class HeatmapCell:
    """One day of a front: the plan, the done of both shifts and the delivered share."""

    planned: float
    done: float
    percent: float | None


@dataclass(frozen=True)
class HeatmapRow:
    """One front of the heatmap, Monday through Sunday."""

    label: str
    cells: tuple[HeatmapCell, ...]


@dataclass(frozen=True)
class Heatmap:
    """The day-by-front grid: the fronts and the seven days, with their cells."""

    columns: tuple[str, ...]
    rows: tuple[HeatmapRow, ...]


def heatmap_day_front(activities: Iterable[IndicatorActivity]) -> Heatmap:
    """How much of each day's plan each front delivered.

    The percentage is of the plan of that day in that front, not of the week; a day
    without a plan has no percentage — it is absence of plan, not 0% of adherence.
    """
    items = list(activities)
    fronts = sorted({item.location or NO_KEY for item in items})
    rows = []
    for front in fronts:
        of_front = [item for item in items if (item.location or NO_KEY) == front]
        cells = []
        for index in range(DAYS):
            planned = round(sum(item.figures.planned_days[index] for item in of_front), 2)
            done = round(sum(item.figures.day_totals[index] for item in of_front), 2)
            percent = round(done / planned * 100, 1) if planned else None
            cells.append(HeatmapCell(planned=planned, done=done, percent=percent))
        rows.append(HeatmapRow(label=front, cells=tuple(cells)))
    return Heatmap(columns=DAY_LABELS, rows=tuple(rows))


def heat_band(percent: float | None) -> str:
    """The tone of a delivered share on the module's scale; empty without a plan."""
    if percent is None:
        return ""
    return HEAT_TONES[performance_band(percent)]


def heat_faixas() -> tuple[dict[str, object], ...]:
    """The bands of the heatmap in the contract of the Design System (D11).

    The list goes from the most specific to the most general, because the visual
    takes the first band that matches the value.
    """
    return (
        {
            "de": HIGH_BAND,
            "tom": HEAT_TONES[BAND_HIGH],
            "nivel": 1,
            "icone": HEAT_ICONS[BAND_HIGH],
            "rotulo": f"{HIGH_BAND:g}% ou mais do previsto do dia",
        },
        {
            "de": MEDIUM_BAND,
            "menor_que": HIGH_BAND,
            "tom": HEAT_TONES[BAND_MEDIUM],
            "nivel": 2,
            "icone": HEAT_ICONS[BAND_MEDIUM],
            "rotulo": f"de {MEDIUM_BAND:g}% a {HIGH_BAND - 1:g}% do previsto do dia",
        },
        {
            "menor_que": MEDIUM_BAND,
            "tom": HEAT_TONES[BAND_LOW],
            "nivel": 3,
            "icone": HEAT_ICONS[BAND_LOW],
            "rotulo": f"abaixo de {MEDIUM_BAND:g}% do previsto do dia",
        },
        {"vazia": True, "tom": "cinza", "rotulo": "sem previsão para o dia"},
    )


@dataclass(frozen=True)
class ShiftDay:
    """One weekday of the week with the plan and the two shifts."""

    label: str
    name: str
    planned: float
    day_shift: float
    night_shift: float
    done: float


def shifts_by_day(activities: Iterable[IndicatorActivity]) -> list[ShiftDay]:
    """Planned against done for each weekday, with the day and the night shifts apart."""
    items = list(activities)
    return [
        ShiftDay(
            label=DAY_LABELS[index],
            name=DAY_NAMES[index],
            planned=round(sum(item.figures.planned_days[index] for item in items), 2),
            day_shift=round(sum(item.figures.day_shift[index] for item in items), 2),
            night_shift=round(sum(item.figures.night_shift[index] for item in items), 2),
            done=round(sum(item.figures.day_totals[index] for item in items), 2),
        )
        for index in range(DAYS)
    ]


@dataclass(frozen=True)
class Bottleneck:
    """One activity dragging the week down, for the action list."""

    identity: str
    description: str
    project_label: str
    company: str
    location: str
    foreman: str
    unit: str
    ppc: float
    planned: float
    done: float
    idle_days: int


def bottlenecks(
    activities: Iterable[IndicatorActivity], limit: int = BOTTLENECK_LIMIT
) -> list[Bottleneck]:
    """The activities below the medium band, worst PPC first — the action list.

    An activity without a plan is not a bottleneck: there is nothing it failed to
    deliver. The number of idle days is the planned days that produced nothing.
    """
    candidates = [
        item
        for item in activities
        if item.figures.planned_total > 0 and item.figures.ppc < MEDIUM_BAND
    ]
    candidates.sort(key=lambda item: (item.figures.ppc, -item.figures.planned_total))
    return [
        Bottleneck(
            identity=item.identity,
            description=item.description,
            project_label=item.project_label,
            company=item.company,
            location=item.location,
            foreman=item.foreman,
            unit=item.unit,
            ppc=item.figures.ppc,
            planned=item.figures.planned_total,
            done=item.figures.done_total,
            idle_days=sum(
                1
                for index in range(DAYS)
                if item.figures.planned_days[index] > 0 and item.figures.day_totals[index] == 0
            ),
        )
        for item in candidates[:limit]
    ]


@dataclass(frozen=True)
class CompanyWeek:
    """What one company planned and delivered in a week."""

    planned: float
    done: float


@dataclass(frozen=True)
class EvolutionPoint:
    """One week of the evolution: the companies with activity in it, and their quantities."""

    week: str
    totals: Mapping[str, CompanyWeek]


@dataclass(frozen=True)
class Evolution:
    """Adherence by company week by week — quantities, so the chart can aggregate."""

    series: tuple[str, ...]
    points: tuple[EvolutionPoint, ...]


def evolution_by_company(activities: Iterable[IndicatorActivity]) -> Evolution:
    """One line per company, week by week, with the planned and the done of each week.

    The server sends quantities and never a ready percentage: the chart divides the
    sum of the done by the sum of the planned at whatever grouping level it is
    showing, and the rate of a month is not the mean of its weekly rates. A company
    without activity in a week does not appear in that week, as in the app.
    """
    items = list(activities)
    weeks_list = sorted({item.week for item in items if item.week}, key=weeks.sort_key)
    companies = sorted({item.company or NO_KEY for item in items})
    points = []
    for week in weeks_list:
        totals: dict[str, CompanyWeek] = {}
        for company in companies:
            of_group = [
                item for item in items if item.week == week and (item.company or NO_KEY) == company
            ]
            if not of_group:
                continue
            totals[company] = CompanyWeek(
                planned=round(sum(item.figures.planned_total for item in of_group), 2),
                done=round(sum(item.figures.done_total for item in of_group), 2),
            )
        points.append(EvolutionPoint(week=week, totals=totals))
    return Evolution(series=tuple(companies), points=tuple(points))
