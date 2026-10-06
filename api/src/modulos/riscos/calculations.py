"""Pure calculations of the Risk management module (D6, ISSUE-064).

Every rule is one function with its business name (``LEIA-ME.md``), and the reference date is
always an argument: nothing here reads the clock. Score, severity, VME and exposure are never
stored; the facade calculates them on every query from the active scale and the probabilities
of the parameters (group Riscos).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

THREAT = "Ameaça"
OPPORTUNITY = "Oportunidade"
CLOSED_SITUATIONS = ("Materializado", "Encerrado")
MIN_LEVEL = 1
MAX_LEVEL = 5
PERCENT = Decimal(100)

# The six dimensions of impact, in the order the form shows them: key and label.
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("prazo", "Prazo"),
    ("custo", "Custo"),
    ("escopo", "Escopo e qualidade"),
    ("sms", "SMS"),
    ("imagem", "Imagem"),
    ("legal", "Legal e contratual"),
)


@dataclass(frozen=True)
class Band:
    """A band of the severity scale: its key, its name and the lowest score that falls in it."""

    id: str
    name: str
    minimum: int


@dataclass(frozen=True)
class Scale:
    """The active severity scale: bands from the lightest to the heaviest."""

    name: str
    bands: tuple[Band, ...]
    life_risk_is_high: bool


@dataclass(frozen=True)
class ProbabilityBand:
    """A level of probability: its name, its percentage range and the mean used by the VME."""

    level: int
    name: str
    range_text: str
    mean_pct: Decimal


@dataclass(frozen=True)
class RiskParameters:
    """What the group Riscos of the parameters gives the calculations."""

    scale: Scale
    cadence_days: Mapping[str, int]
    probabilities: tuple[ProbabilityBand, ...]
    impacts: tuple[str, ...]
    review_alert_days: int


def parameters_from_values(values: Mapping[str, Any]) -> RiskParameters:
    """The parameters of the group Riscos as the calculations read them."""
    scales = values["escalas"]
    chosen = scales[values["escalaAtiva"]]
    bands = sorted(
        (Band(item["id"], item["nome"], int(item["minimo"])) for item in chosen["faixas"]),
        key=lambda band: band.minimum,
    )
    return RiskParameters(
        scale=Scale(chosen["nome"], tuple(bands), bool(chosen["riscoVidaEhAlto"])),
        cadence_days=dict(values["cadenciaDias"]),
        probabilities=tuple(
            ProbabilityBand(
                int(item["nivel"]), item["nome"], item["faixa"], Decimal(str(item["mediaPct"]))
            )
            for item in values["probabilidades"]
        ),
        impacts=tuple(values["impactos"]),
        review_alert_days=int(values["revisaoAlertaDias"]),
    )


def risk_score(probability: int, impact: int) -> int:
    """Score of the risk: probability times impact, from 1 to 25."""
    return probability * impact


def risk_severity(score: int, scale: Scale, *, life_risk: bool = False) -> Band:
    """Severity of the score on the active scale; a risk to life is always the highest on CIPM."""
    if life_risk and scale.life_risk_is_high:
        return scale.bands[-1]
    chosen = scale.bands[0]
    for band in scale.bands:
        if score >= band.minimum:
            chosen = band
    return chosen


def severity_rank(severity_id: str, scale: Scale) -> int:
    """Position of the band on the scale, 0 for the lightest; an unknown ``critico`` is the top."""
    for position, band in enumerate(scale.bands):
        if band.id == severity_id:
            return position
    return len(scale.bands) - 1 if severity_id == "critico" else -1


def resulting_impact(dimensions: Mapping[str, int | None]) -> int:
    """Impact of the risk: the highest of the dimensions (worst case); zero when none was rated."""
    rated = [level for level in dimensions.values() if level and MIN_LEVEL <= level <= MAX_LEVEL]
    return max(rated, default=0)


def is_impact_reduced(impact: int, dimensions: Mapping[str, int | None]) -> bool:
    """Whether the chosen impact is below the worst case: it may be raised, never reduced."""
    return impact < resulting_impact(dimensions)


def probability_mean_pct(
    probability: int, probabilities: Sequence[ProbabilityBand]
) -> Decimal | None:
    """Mean percentage of the probability level, or ``None`` when the level has no band."""
    for band in probabilities:
        if band.level == probability:
            return band.mean_pct
    return None


def expected_monetary_value(
    probability: int, cost_impact_cents: int, probabilities: Sequence[ProbabilityBand]
) -> int:
    """VME in cents: mean probability of the band times the cost impact, half up."""
    mean = probability_mean_pct(probability, probabilities)
    if mean is None:
        return 0
    value = Decimal(cost_impact_cents) * mean / PERCENT
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def threat_exposure(items: Iterable[tuple[str, int]]) -> int:
    """Exposure of the project in cents: the sum of the VME of the threats only."""
    return sum(vme for nature, vme in items if nature == THREAT)


def review_cadence(severity_id: str, cadence_days: Mapping[str, int]) -> int:
    """Days between reviews for the severity; the longest when the band has no value."""
    return cadence_days.get(severity_id) or max(cadence_days.values())


def is_active(situation: str) -> bool:
    """A risk is active until it materializes or is closed."""
    return situation not in CLOSED_SITUATIONS


def days_until(due: date | None, reference_date: date) -> int | None:
    """Days from the reference date to the date (negative when past); ``None`` without date."""
    return None if due is None else (due - reference_date).days


def is_review_overdue(next_review: date | None, reference_date: date, *, active: bool) -> bool:
    """Review overdue: an active risk whose next review is before the reference date."""
    return active and next_review is not None and next_review < reference_date


def is_review_due_soon(
    next_review: date | None, reference_date: date, *, active: bool, alert_days: int
) -> bool:
    """Review due within the alert days (today included); overdue ones are not 'soon'."""
    remaining = days_until(next_review, reference_date)
    return active and remaining is not None and 0 <= remaining <= alert_days


def justification_required(previous_score: int | None, new_score: int) -> bool:
    """A new score that differs from the previous assessment needs a justification."""
    return previous_score is not None and previous_score != new_score


def residual_exceeds_inherent(nature: str, residual_score: int, inherent_score: int | None) -> bool:
    """For a threat the residual score may not be above the inherent one."""
    return nature == THREAT and inherent_score is not None and residual_score > inherent_score


def next_code_number(existing_codes: Iterable[str], prefix: str) -> int:
    """Next sequence number for the prefix: the highest numeric suffix plus one.

    Only ``<prefix>-<digits>`` counts: ``RSK-TN-2026-SE-0001`` does not move ``RSK-TN-2026``.
    """
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    highest = 0
    for code in existing_codes:
        found = pattern.match(code)
        if found:
            highest = max(highest, int(found.group(1)))
    return highest + 1


def format_code(prefix: str, number: int) -> str:
    """The code as the register prints it: ``RSK-TN-2026-0010``."""
    return f"{prefix}-{number:04d}"
