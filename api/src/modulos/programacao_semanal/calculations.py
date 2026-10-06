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
| Desvio do realizado em relação ao previsto | ``deviation_percent`` |
| Desvio que exige justificativa | ``needs_deviation_note`` |

No function reads the clock or the database.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

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


def deviation_percent(planned: float, done: float) -> float:
    """Distance of the done from the planned, in percent of the planned; zero when nothing was planned."""
    if planned <= 0:
        return 0.0
    return abs(done - planned) / planned * 100


def needs_deviation_note(planned: float, done: float, *, limit: float, required: bool) -> bool:
    """Whether the done needs a justification: the rule is on and the deviation passes the limit.

    A deviation exactly at the limit does not need one; neither does an activity with no plan.
    """
    return required and deviation_percent(planned, done) > limit


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
