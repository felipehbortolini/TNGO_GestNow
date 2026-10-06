"""Pure rules of the Punch list (ISSUE-049, HU-068, HU-069): no database, no clock.

Every function receives the reference date as an argument. The business names, as the
prototype (``punchComCalculos``, ``resumoPunch`` and the panel of ``punch-list.js``) knew them:

* ``is_open``: an item is open while it is neither Fechado nor Cancelado;
* ``item_age_days``: days since the opening, up to the closing (or the reference date);
* ``is_overdue``: open and past the deadline;
* ``blocking_count``: how many open items hold a system back from a milestone;
* ``blocked_system_ids``: the systems with an open item A, for the alert of blocked systems;
* ``closed_percentage``: the closed items over the valid ones, for the indicator of closed;
* ``next_situations``: the moves the flow allows from a situation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

OPEN = "Aberto"
IN_TREATMENT = "Em tratamento"
AWAITING_VERIFICATION = "Aguardando verificação"
CLOSED = "Fechado"
CANCELLED = "Cancelado"
SITUATIONS = (OPEN, IN_TREATMENT, AWAITING_VERIFICATION, CLOSED, CANCELLED)

CATEGORIES = ("A", "B", "C")
DISCIPLINES = (
    "Civil",
    "Mecânica",
    "Tubulação",
    "Elétrica",
    "Instrumentação",
    "Automação",
    "Arquitetura",
)
MILESTONES = (
    "Completação mecânica",
    "Pré-comissionamento",
    "Comissionamento",
    "Partida",
    "Aceite provisório",
    "Aceite definitivo",
)
ORIGINS = ("Walkdown", "Inspeção", "Comissionamento", "Cliente", "Auditoria")
FINAL_MILESTONE = "Aceite definitivo"
# The milestones the panel reads the release of each system against.
PANEL_MILESTONES = ("Completação mecânica", "Comissionamento", "Aceite definitivo")
# The milestones the alert of blocked systems reads (the prototype reads these two).
ALERT_MILESTONES = ("Comissionamento", "Completação mecânica")

_FINAL_SITUATIONS = frozenset({CLOSED, CANCELLED})
_FLOW: dict[str, tuple[str, ...]] = {
    OPEN: (IN_TREATMENT, CANCELLED),
    IN_TREATMENT: (AWAITING_VERIFICATION, CANCELLED),
    AWAITING_VERIFICATION: (CLOSED, IN_TREATMENT, CANCELLED),
    CLOSED: (),
    CANCELLED: (),
}


@dataclass(frozen=True)
class PunchFacts:
    """What the rules read of an item: system, category, milestone, situation and dates."""

    system_id: int
    category: str
    milestone: str
    situation: str
    opened_on: date
    due_date: date
    closed_on: date | None = None


def is_open(situation: str) -> bool:
    """Whether the item still needs work: neither Fechado nor Cancelado."""
    return situation not in _FINAL_SITUATIONS


def next_situations(situation: str) -> tuple[str, ...]:
    """The situations the flow allows after this one (empty when the item is final)."""
    return _FLOW.get(situation, ())


def can_move(situation: str, target: str) -> bool:
    """Whether the flow allows going from ``situation`` to ``target``."""
    return target in next_situations(situation)


def item_age_days(facts: PunchFacts, reference_date: date) -> int:
    """Days since the opening: up to the reference date while open, up to the closing after."""
    end = reference_date if is_open(facts.situation) else facts.closed_on or reference_date
    return (end - facts.opened_on).days


def is_overdue(facts: PunchFacts, reference_date: date) -> bool:
    """Whether the deadline passed and the item is still open (the deadline day is on time)."""
    return is_open(facts.situation) and facts.due_date < reference_date


def blocking_count(items: Iterable[PunchFacts], system_id: int, milestone: str) -> int:
    """How many open items of the system hold it back from the milestone.

    For the Aceite definitivo every open item blocks; for the other milestones only an
    open item A whose own milestone is that one or an earlier one.
    """
    reached = MILESTONES.index(milestone)
    total = 0
    for item in items:
        if not is_open(item.situation) or item.system_id != system_id:
            continue
        if milestone == FINAL_MILESTONE or (
            item.category == "A" and MILESTONES.index(item.milestone) <= reached
        ):
            total += 1
    return total


def is_system_blocked(items: Iterable[PunchFacts], system_id: int, milestone: str) -> bool:
    """Whether the system is blocked for the milestone: at least one item holds it back."""
    return blocking_count(list(items), system_id, milestone) > 0


def blocked_system_ids(items: Sequence[PunchFacts], system_ids: Iterable[int]) -> list[int]:
    """The systems of the alert: blocked for the Comissionamento or the Completação mecânica."""
    return [
        system_id
        for system_id in system_ids
        if any(blocking_count(items, system_id, milestone) for milestone in ALERT_MILESTONES)
    ]


def closed_percentage(closed: int, valid: int) -> int | None:
    """The closed items over the valid ones (not cancelled), rounded half up; ``None`` with none."""
    if valid <= 0:
        return None
    return (closed * 200 + valid) // (2 * valid)
