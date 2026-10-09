"""Pure calculations of the supplier register, of the purchase plan and of the process (ISSUE-057/058/059, D6).

Every rule is one function with its business name (``LEIA-ME.md``) and the reference date is
always an argument: nothing here reads the clock. "Documents in day", "qualification due" and
the situation a final contract evaluation leads to are never stored; the facade calculates them
on every query from the documents and the evaluations of the Financeiro.

The purchase plan: the plan dates of the seven acquisition milestones, the stage that the real
dates lead to, the planned slack against the ROS and the derivation of the three intermediate
milestone dates are pure functions too, so the screen and the import share the same rules.

The purchase process: the ten stages of the flow, the situation of each of the nine steps of the
bar, the required approval band, the process number, the commercial and final scores and the
ranking of the proposals are pure functions, so the screen, the seed and the exports share them.

The emission (ISSUE-060): the standard manufacturing schedule of an order, its delivery slack,
the justification the recommendation demands and the LLI gate are pure functions too; the
numbers of the order and of the contract follow the prototype's global series
(``core.numbering.next_series_number``).
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


# ── The purchase process (ISSUE-059) ─────────────────────────────────────────────────────────

# The ten stages of the prototype (``ETAPAS_SUP``); the bar of the process shows the nine from
# "Requisição" on, as the stepper of the prototype did.
PROCESS_STAGES: tuple[str, ...] = (
    STAGE_PLANNED,
    "Requisição",
    "RFx emitida",
    "Propostas recebidas",
    "Equalização técnica",
    "Equalização comercial",
    "Negociação",
    "Recomendação de adjudicação",
    "Aprovada",
    "Pedido/contrato emitido",
)

# The nine steps of the process bar, in order: the key of the acquisition milestone and the
# stage it reaches (the label the bar prints).
PROCESS_STEPS: tuple[tuple[str, str], ...] = (
    ("requisicao", "Requisição"),
    ("rfx", "RFx emitida"),
    ("propostas", "Propostas recebidas"),
    ("eqTecnica", "Equalização técnica"),
    ("eqComercial", "Equalização comercial"),
    ("negociacao", "Negociação"),
    ("recomendacao", "Recomendação de adjudicação"),
    ("adjudicacao", "Aprovada"),
    ("pedido", "Pedido/contrato emitido"),
)

STEP_DONE = "concluido"
STEP_CURRENT = "andamento"
STEP_FUTURE = "futuro"

RFQ_PREFIX = "RFQ"
RFP_PREFIX = "RFP"
SERVICE_KINDS: tuple[str, ...] = ("Serviço", "EPC")

ONE_TENTH = Decimal("0.1")
HUNDRED = Decimal(100)


def stage_index(stage: str) -> int:
    """The position of the stage in the flow; an unknown stage reads as ``Planejado``."""
    try:
        return PROCESS_STAGES.index(stage)
    except ValueError:
        return 0


def process_stage(history_stages: Sequence[str], fallback: str) -> str:
    """The stage the process is in: the one the last recorded action led to.

    The prototype kept the stage in the package; here it is the ``etapa`` of the last history
    line (the action that moved the process), and the stage calculated from the real dates of
    the package is the fallback of a process the load brought without history.
    """
    recorded = [stage for stage in history_stages if stage]
    return recorded[-1] if recorded else fallback


def step_situation(position: int, *, current: int, done: bool) -> str:
    """How one of the nine steps of the bar reads: done, current or future.

    The step of the current stage is ``andamento`` (the stage only moves when its action runs),
    the ones before it are done and the ones after are future; a fact ahead of the recorded stage
    counts as done, and a process at the last stage has all nine done.
    """
    if current >= len(PROCESS_STEPS):
        return STEP_DONE
    if position < current or (position > current and done):
        return STEP_DONE
    return STEP_CURRENT if position == current else STEP_FUTURE


def single_supplier(invitee_count: int, minimum: int) -> bool:
    """Whether the process ran with a single supplier: fewer invitees than the minimum.

    The rule of the emission guarantees it: below the minimum of the parameter the RFx is only
    accepted as a single supplier with justification, so at reading it means exactly that.
    """
    return invitee_count < minimum


def is_service(kind: str) -> bool:
    """Whether the package of the kind generates a contract (``RFP``): service and EPC."""
    return kind in SERVICE_KINDS


def next_process_number(numbers: Sequence[str], *, service: bool, year: int) -> str:
    """The next RFx number of the type: the highest number of the year plus one, three digits.

    The prototype numbered globally by type and year (``RFQ-2026-014``), not per project; from
    the 1000th process the three-digit field simply grows, as the prototype's did.
    """
    prefix = f"{RFP_PREFIX if service else RFQ_PREFIX}-{year}-"
    counters = [
        int(number[len(prefix) :])
        for number in numbers
        if number.startswith(prefix) and number[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(counters, default=0) + 1:03d}"


def approval_band_for(value_cents: int, bands: Sequence[tuple[int | None, str]]) -> str | None:
    """The band of approval of a value: the first ceiling that covers it, the last as fallback.

    The prototype's ``regras.alcada``: a band with no ceiling covers everything and the value
    exactly on the ceiling belongs to the band it closes. Without bands there is no required
    approval.
    """
    if not bands:
        return None
    for ceiling, name in bands:
        if ceiling is None or value_cents <= ceiling:
            return name
    return bands[-1][1]


def commercial_score(price_cents: int | None, lowest_cents: int | None) -> Decimal | None:
    """The commercial score: the lowest approved price divided by the price, in percent.

    One decimal, half up, exactly as the prototype (``menor preço ÷ preço x 100``); without a
    price or a lowest price there is no score.
    """
    if lowest_cents is None or price_cents is None or price_cents <= 0:
        return None
    value = Decimal(lowest_cents) / Decimal(price_cents) * HUNDRED
    return value.quantize(ONE_TENTH, rounding=ROUND_HALF_UP)


def final_score(
    technical: Decimal | int | None,
    commercial: Decimal | int | None,
    weight_technical: int,
    weight_commercial: int,
) -> Decimal | None:
    """The weighted final score: ``(técnica x peso + comercial x peso) ÷ soma dos pesos``.

    One decimal, half up; without a score or without weight there is no final score (the
    prototype divides by the sum of the weights, not by 100).
    """
    if technical is None or commercial is None:
        return None
    total = weight_technical + weight_commercial
    if total <= 0:
        return None
    value = (
        Decimal(technical) * weight_technical + Decimal(commercial) * weight_commercial
    ) / total
    return value.quantize(ONE_TENTH, rounding=ROUND_HALF_UP)


def proposal_ranking(
    entries: Sequence[tuple[int, Decimal | None, int]],
) -> list[tuple[int, int]]:
    """The ranking of the proposals: final score descending, price ascending (prototype).

    ``entries`` are ``(id, final score, value in cents)``; only the proposals with a final score
    enter, ties on both keep the order they were read in (a stable sort, as the prototype's).
    """
    ranked = [(item_id, score, value) for item_id, score, value in entries if score is not None]
    ordered = sorted(ranked, key=lambda entry: (-entry[1], entry[2]))
    return [(entry[0], position) for position, entry in enumerate(ordered, start=1)]


def cycle_days(requisition: date | None, order: date | None, reference_date: date) -> int | None:
    """The purchase cycle: the days from the requisition to the order, or to the reference.

    The prototype's ``cicloDias``: without a real requisition there is no cycle; without the
    order the cycle runs up to the reference date.
    """
    if requisition is None:
        return None
    return ((order or reference_date) - requisition).days


# ── The emission (ISSUE-060) ─────────────────────────────────────────────────────────────────

# The six manufacturing milestones of the prototype (``NOMES_MARCOS_PEDIDO``) and the share of
# the order-to-delivery window each one falls on (``PROP_FAB``).
MANUFACTURING_MILESTONES: tuple[tuple[str, Decimal], ...] = (
    ("Aprovação de documentos", Decimal("0.15")),
    ("Matéria-prima", Decimal("0.3")),
    ("Fabricação", Decimal("0.75")),
    ("Inspeção / FAT", Decimal("0.85")),
    ("Embarque", Decimal("0.93")),
    ("Entrega", Decimal("1")),
)

PURCHASE_ORDER_PREFIX = "PED"
PURCHASE_CONTRACT_PREFIX = "CT"


def manufacturing_schedule(emission: date, contractual: date) -> tuple[tuple[str, date], ...]:
    """The standard manufacturing schedule: the six milestones between emission and delivery.

    Each milestone falls on the share of the window the prototype used (``entre`` with
    ``PROP_FAB``), rounded half up; the last one lands on the contractual date itself.
    """
    return tuple(
        (name, _between(emission, contractual, share)) for name, share in MANUFACTURING_MILESTONES
    )


def delivery_slack_days(ros: date | None, forecast: date | None) -> int | None:
    """The slack of an order: the ROS minus the forecast delivery (negative is late)."""
    if ros is None or forecast is None:
        return None
    return (ros - forecast).days


def recommendation_requires_justification(rank: int | None, qualification: str | None) -> bool:
    """Whether recommending demands a justification: not the best score or not qualified.

    The prototype's rule: only the first of the ranking with the supplier qualified follows
    without justification; a blocked supplier never follows (the facade refuses it).
    """
    return rank != 1 or qualification != QUALIFIED


def lli_before_gate(
    *,
    lli: bool,
    requisition: date | None,
    project_start: date | None,
    gate_date: date | None,
) -> bool:
    """Whether an LLI package was contracted before the investment gate without its approval.

    The prototype's rule: an LLI whose requisition happened before the project start demands the
    specific approval of the LLI gate (the date saved in the plan) before the adjudication.
    """
    if not lli or requisition is None or project_start is None or gate_date is not None:
        return False
    return requisition < project_start


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
