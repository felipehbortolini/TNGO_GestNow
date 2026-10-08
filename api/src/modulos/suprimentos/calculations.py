"""Pure calculations of the supplier register (ISSUE-057, D6).

Every rule is one function with its business name (``LEIA-ME.md``) and the reference date is
always an argument: nothing here reads the clock. "Documents in day", "qualification due" and
the situation a final contract evaluation leads to are never stored; the facade calculates them
on every query from the documents and the evaluations of the Financeiro.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

QUALIFIED = "Qualificado"
IN_QUALIFICATION = "Em qualificação"
RESTRICTED = "Restrito"
BLOCKED = "Bloqueado"
SITUATIONS: tuple[str, ...] = (QUALIFIED, IN_QUALIFICATION, RESTRICTED, BLOCKED)

# The document alert of the prototype: a document up to 30 days from expiring is "a vencer";
# the qualification itself warns 90 days ahead.
DOCUMENT_ALERT_DAYS = 30
QUALIFICATION_ALERT_DAYS = 90

# The class of the final contract evaluation (ISSUE-034) leads the qualification (D9): the
# approved classes qualify, C restricts (the plan of improvement) and D blocks ("not recommended").
SITUATION_BY_CLASS: dict[str, str] = {
    "A": QUALIFIED,
    "B": QUALIFIED,
    "C": RESTRICTED,
    "D": BLOCKED,
}


def _is_expired(validity: date | None, reference_date: date) -> bool:
    """A date before the reference date: it expires on the day after its validity."""
    return validity is not None and validity < reference_date


def _is_expiring(validity: date | None, reference_date: date, alert_days: int) -> bool:
    """Not expired and within the alert window (today included)."""
    if validity is None or _is_expired(validity, reference_date):
        return False
    return (validity - reference_date).days <= alert_days


def document_is_expired(validity: date | None, reference_date: date) -> bool:
    """A document with validity before the reference date is expired (a valid today is not)."""
    return _is_expired(validity, reference_date)


def document_is_expiring(
    validity: date | None, reference_date: date, *, days: int = DOCUMENT_ALERT_DAYS
) -> bool:
    """A document that expires within ``days`` of the reference date, without being expired."""
    return _is_expiring(validity, reference_date, days)


def qualification_is_expired(validity: date | None, reference_date: date) -> bool:
    """The qualification validity before the reference date is expired."""
    return _is_expired(validity, reference_date)


def qualification_is_expiring(
    validity: date | None, reference_date: date, *, days: int = QUALIFICATION_ALERT_DAYS
) -> bool:
    """The qualification that expires within ``days``, without being expired (the mock's 90)."""
    return _is_expiring(validity, reference_date, days)


def documents_up_to_date(validities: Iterable[date | None], reference_date: date) -> bool:
    """Every document is in day; a supplier with no document at all counts as in day."""
    return all(not document_is_expired(validity, reference_date) for validity in validities)


def situation_for_evaluation_class(class_name: str | None) -> str | None:
    """The qualification the final evaluation class leads to, or ``None`` when it is unknown."""
    return SITUATION_BY_CLASS.get((class_name or "").strip().upper())


def justification_is_required(previous_situation: str | None, new_situation: str) -> bool:
    """A change of situation from the previous one needs a justification (10 chars and up)."""
    return previous_situation is not None and previous_situation != new_situation


def average_score(scores: Iterable[int]) -> Decimal | None:
    """The mean of the evaluation scores, one decimal, half up; ``None`` when there is none."""
    values = list(scores)
    if not values:
        return None
    total = Decimal(sum(values))
    mean = total / Decimal(len(values))
    return mean.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
