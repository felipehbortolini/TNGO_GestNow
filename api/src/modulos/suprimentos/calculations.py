"""Pure calculations of the supplier register and of the purchase plan (ISSUE-057/058, D6).

Every rule is one function with its business name (``LEIA-ME.md``) and the reference date is
always an argument: nothing here reads the clock. "Documents in day", "qualification due" and
the situation a final contract evaluation leads to are never stored; the facade calculates them
on every query from the documents and the evaluations of the Financeiro.

The purchase plan: the plan dates of the seven acquisition milestones, the stage that the real
dates lead to, the planned slack against the ROS and the derivation of the three intermediate
milestone dates are pure functions too, so the screen and the import share the same rules.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise

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


# ── The purchase plan (ISSUE-058) ────────────────────────────────────────────────────────────

# The seven acquisition milestones of the prototype (``MARCOS_AQ``), in plan order.
ACQUISITION_MILESTONES: tuple[tuple[str, str], ...] = (
    ("requisicao", "Requisição"),
    ("rfx", "RFx emitida"),
    ("propostas", "Propostas"),
    ("eqTecnica", "Equalização técnica"),
    ("eqComercial", "Equalização comercial"),
    ("adjudicacao", "Aprovação"),
    ("pedido", "Pedido/contrato"),
)
MILESTONE_KEYS: tuple[str, ...] = tuple(key for key, _ in ACQUISITION_MILESTONES)
MILESTONE_LABELS: Mapping[str, str] = dict(ACQUISITION_MILESTONES)

REQUISITION_MILESTONE = "requisicao"
ADJUDICATION_MILESTONE = "adjudicacao"
ORDER_MILESTONE = "pedido"
PLAN_MILESTONES: tuple[str, ...] = (
    REQUISITION_MILESTONE,
    "rfx",
    ADJUDICATION_MILESTONE,
    ORDER_MILESTONE,
)

# The stage the last milestone with a real date leads to (``ETAPAS_SUP`` of the prototype).
STAGE_PLANNED = "Planejado"
STAGE_BY_MILESTONE: Mapping[str, str] = {
    "requisicao": "Requisição",
    "rfx": "RFx emitida",
    "propostas": "Propostas recebidas",
    "eqTecnica": "Equalização técnica",
    "eqComercial": "Equalização comercial",
    "adjudicacao": "Aprovada",
    "pedido": "Pedido/contrato emitido",
}

# The derivation of the three intermediate plan dates, as the prototype's ``montarPacote`` does.
PROPOSAL_DAYS = 21
COMMERCIAL_WINDOW_DAYS = 7
PROPOSAL_SHARE = Decimal("0.4")
TECHNICAL_SHARE = Decimal("0.5")
COMMERCIAL_SHARE = Decimal("0.6")

# The prototype's default alert window for the planned slack; the parameter arrives with the
# purchases parameters (ISSUE-076).
SLACK_ALERT_DAYS = 7
SLACK_CRITICAL = "critico"
SLACK_WARNING = "atencao"
SLACK_OK = "ok"


def package_stage(real_dates: Mapping[str, date | None]) -> str:
    """The stage of the package: the one of the last milestone with a real date.

    Without any real date the package is ``Planejado``; with the last milestone done it is
    ``Pedido/contrato emitido``. The stage is calculated, never stored.
    """
    last = None
    for key in MILESTONE_KEYS:
        if real_dates.get(key) is not None:
            last = key
    return STAGE_BY_MILESTONE.get(last or "", STAGE_PLANNED)


def lb_frozen(requisition_real: date | None) -> bool:
    """Whether the baseline is frozen: from the requisition with a real date on."""
    return requisition_real is not None


def plan_dates_in_order(plan_dates: Mapping[str, date | None]) -> bool:
    """The plan dates grow: requisition <= RFx <= adjudication <= order (equal dates hold up)."""
    ordered = [plan_dates.get(key) for key in PLAN_MILESTONES]
    if any(value is None for value in ordered):
        return False
    known = [value for value in ordered if value is not None]
    return all(before <= after for before, after in pairwise(known))


def planned_slack_days(ros: date | None, order_plan: date | None) -> int | None:
    """The planned slack: the ROS minus the planned order date.

    The prototype added the delivery time after the order for equipment and material; the model
    has no such column and the mock carries no data, so the conservative reading is the order
    milestone itself (DECISION, ISSUE-058).
    """
    if ros is None or order_plan is None:
        return None
    return (ros - order_plan).days


def slack_band(slack_days: int | None, *, alert_days: int = SLACK_ALERT_DAYS) -> str:
    """How the slack reads: critical below zero, warning within the alert window, otherwise ok."""
    if slack_days is None:
        return SLACK_OK
    if slack_days < 0:
        return SLACK_CRITICAL
    return SLACK_WARNING if slack_days <= alert_days else SLACK_OK


def derived_plan_dates(
    *, requisition: date, rfx: date, adjudication: date, order: date
) -> dict[str, date]:
    """The seven plan dates, deriving the three intermediate ones as the prototype does (Q31).

    Proposals are 21 days after the RFx, shortened to 40% of the window to the adjudication when
    they would pass it; the commercial equalization is seven days before the adjudication, pushed
    to 60% of the window when it would land before the proposals; the technical equalization
    falls halfway between the proposals and the commercial one.
    """
    proposals = rfx + timedelta(days=PROPOSAL_DAYS)
    if proposals > adjudication:
        proposals = _between(rfx, adjudication, PROPOSAL_SHARE)
    commercial = adjudication - timedelta(days=COMMERCIAL_WINDOW_DAYS)
    if commercial < proposals:
        commercial = _between(proposals, adjudication, COMMERCIAL_SHARE)
    technical = _between(proposals, commercial, TECHNICAL_SHARE)
    return {
        REQUISITION_MILESTONE: requisition,
        "rfx": rfx,
        "propostas": proposals,
        "eqTecnica": technical,
        "eqComercial": commercial,
        ADJUDICATION_MILESTONE: adjudication,
        ORDER_MILESTONE: order,
    }


def _between(start: date, end: date, share: Decimal) -> date:
    """A date between two others, at the share the prototype rounds half up."""
    distance = Decimal((end - start).days) * share
    return start + timedelta(days=int(distance.to_integral_value(rounding=ROUND_HALF_UP)))


def adjudication_deviation_days(
    plan: date | None,
    real: date | None,
    forecast: date | None,
    reference_date: date,
) -> int | None:
    """The deviation of the adjudication against the LB: positive is late.

    The effective date is the real one, else the forecast, else the reference date when the LB
    is already past it; without a plan or an effective date there is no deviation.
    """
    if plan is None:
        return None
    if real is not None:
        return (real - plan).days
    if forecast is not None:
        return (forecast - plan).days
    if plan < reference_date:
        return (reference_date - plan).days
    return None


def adjudication_overdue(
    plan: date | None,
    real: date | None,
    forecast: date | None,
    reference_date: date,
) -> bool:
    """Whether the adjudication is late: not done and with the LB or the forecast past it."""
    if real is not None:
        return False
    deviation = adjudication_deviation_days(plan, real, forecast, reference_date)
    return deviation is not None and deviation > 0


def next_package_code(codes: Sequence[str]) -> str:
    """The next code of the project: the prefix of the last one and the next two-digit number.

    The prototype took the prefix of the last code and the highest number under it; from the
    100th package it truncates to two digits and collides, so the code keeps the full number
    (DIVERGENCIAS-DO-PROTOTIPO, pending acceptance).
    """
    prefixes = [code.rstrip("0123456789") for code in codes]
    prefix = prefixes[-1] if prefixes else "PC-"
    numbers = [
        int(code[len(prefix) :])
        for code in codes
        if code.startswith(prefix) and code[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1:02d}"
