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

The expediting and the receipt (ISSUE-061): the situation of a manufacturing milestone against
the reference date, the slack against the ROS, the contractual delay and the on-time delivery
(OTD) of a set of orders are pure functions, so the screen, the import and the exports share them.

The map of purchases (ISSUE-062): the twelve milestones in the two halves of the map, the
estimated baseline of the manufacturing milestones of a package still without an order, the line
situation and the procurement progress (the weights of the parameters over the applicable
milestones, weighted by the value of the package) are pure functions too.

The panel (ISSUE-063): the nine indicators of the prototype (adherence, the mean cycle, the two
savings, the emergency share, the committed-against-budget share, the mean of valid proposals and
the single-supplier share) and the three accumulated curves of the panel (contracting, saving and
the advancement of the map, with the baseline, the real and the trend) are pure functions as well,
so the screen, the seed, the exports and the oracle share the same arithmetic.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
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
ONE_HUNDREDTH = Decimal("0.01")
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

# The FAT milestone (the fourth, one-based) is the one that records the inspection in the 06
# and, rejected, does not complete: it demands the new forecast of the retest (ISSUE-069).
INSPECTION_POSITION = 4

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


# ── The expediting and receiving (ISSUE-061) ─────────────────────────────────────────────────

# The situations of a manufacturing milestone (``regras.situacaoMarco`` of the prototype): done
# up to the baseline, done late, overdue without a real date, forecast late, due soon and without
# a baseline or a forecast at all.
MILESTONE_ON_TIME = "prazo"
MILESTONE_LATE = "atraso"
MILESTONE_OVERDUE = "vencido"
MILESTONE_FORECAST_LATE = "previsto-atraso"
MILESTONE_DUE_SOON = "a-vencer"
MILESTONE_WITHOUT_DATE = "sem-data"
MILESTONE_NOT_APPLICABLE = "na"

# How an order reads in the list (``sit`` of the prototype).
ORDER_DELIVERED = "Entregue"
ORDER_CRITICAL = "Crítico"
ORDER_WARNING = "Atenção"
ORDER_ON_TIME = "No prazo"


@dataclass(frozen=True)
class MilestoneSituation:
    """How one manufacturing milestone reads: its situation, the deviation and the days overdue."""

    situation: str
    deviation_days: int | None
    days_overdue: int


def milestone_situation(
    *,
    baseline: date | None,
    forecast: date | None,
    real: date | None,
    reference_date: date,
    applicable: bool = True,
) -> MilestoneSituation:
    """The situation of a milestone against the reference date, as the prototype reads it.

    With a real date the deviation is the real date minus the baseline (positive is late) and the
    situation is ``prazo`` or ``atraso``. Without it the target is the forecast, else the
    baseline: a target before the reference date is ``vencido`` (with the days overdue), a target
    after it is ``previsto-atraso`` when it passes the baseline or ``a-vencer`` otherwise; with no
    target at all, ``sem-data``. A milestone that does not apply to the package (the manufacturing
    half of a service/EPC package, ISSUE-062) reads ``na``.
    """
    if not applicable:
        return MilestoneSituation(MILESTONE_NOT_APPLICABLE, None, 0)
    if real is not None:
        deviation = (real - baseline).days if baseline is not None else 0
        return MilestoneSituation(
            situation=MILESTONE_LATE if deviation > 0 else MILESTONE_ON_TIME,
            deviation_days=deviation,
            days_overdue=0,
        )
    target = forecast or baseline
    if target is None:
        return MilestoneSituation(MILESTONE_WITHOUT_DATE, None, 0)
    deviation = (target - baseline).days if baseline is not None else 0
    if target < reference_date:
        return MilestoneSituation(MILESTONE_OVERDUE, deviation, (reference_date - target).days)
    return MilestoneSituation(
        MILESTONE_FORECAST_LATE if deviation > 0 else MILESTONE_DUE_SOON, deviation, 0
    )


def required_on_site_slack(ros: date | None, forecast: date | None) -> int | None:
    """Folga ROS: the days between the required on site date and the delivery forecast.

    The same formula the prototype used for the order (``regras.folga``): positive is slack,
    negative is critical. ``delivery_slack_days`` is the name the emission (ISSUE-060) gave it;
    this is the business name the expediting reads (ISSUE-061).
    """
    return delivery_slack_days(ros, forecast)


def contractual_delay_days(contractual: date | None, delivered_on: date | None) -> int | None:
    """The delay against the contractual date: the delivery (or forecast) minus the contract.

    Positive is late, as ``R.diasEntre(dataContratual, entrega || previsao)`` of the prototype;
    without one of the dates there is no delay.
    """
    if contractual is None or delivered_on is None:
        return None
    return (delivered_on - contractual).days


def order_situation(*, delivered: bool, band: str, has_overdue: bool) -> str:
    """How the order reads in the list: delivered, critical, warning or on time.

    The prototype's ``sit``: an order with negative slack is critical, an order within the alert
    window or with an overdue milestone is a warning and the rest is on time.
    """
    if delivered:
        return ORDER_DELIVERED
    if band == SLACK_CRITICAL:
        return ORDER_CRITICAL
    if band == SLACK_WARNING or has_overdue:
        return ORDER_WARNING
    return ORDER_ON_TIME


def on_time_delivery(deliveries: Iterable[tuple[date | None, date | None]]) -> Decimal | None:
    """The OTD of a set of orders: the deliveries up to the contractual date over the deliveries.

    ``deliveries`` are ``(entrega, data contratual)`` pairs; the orders not yet delivered stay
    out of both the numerator and the denominator, and without any delivery the OTD is ``None``.
    One decimal, half up, as the prototype printed it (``noPrazo / ent.length * 100``).
    """
    realized = [(delivered, contractual) for delivered, contractual in deliveries if delivered]
    if not realized:
        return None
    on_time = sum(
        1 for delivered, contractual in realized if contractual is None or delivered <= contractual
    )
    return (Decimal(on_time) / Decimal(len(realized)) * HUNDRED).quantize(
        ONE_TENTH, rounding=ROUND_HALF_UP
    )


# ── The map of purchases (ISSUE-062) ─────────────────────────────────────────────────────────

# The two halves of the twelve milestones of the map (``MARCOS_AQ`` and ``MARCOS_FAB`` of the
# prototype). Each manufacturing milestone keeps its position in the standard schedule
# (``MANUFACTURING_MILESTONES``): "Matéria-prima" does not enter the map, as in the prototype.
MAS_ACQUISITION = "aquisicao"
MAS_FABRICATION = "fabricacao"

MAS_FABRICATION_MILESTONES: tuple[tuple[str, str, int], ...] = (
    ("documentos", "Documentos aprovados", 0),
    ("fabricacao", "Fabricação", 2),
    ("inspecao", "Inspeção / FAT", 3),
    ("embarque", "Embarque", 4),
    ("entrega", "Entrega", 5),
)

MAS_MILESTONES: tuple[tuple[str, str, str], ...] = (
    *((key, label, MAS_ACQUISITION) for key, label in ACQUISITION_MILESTONES),
    *((key, label, MAS_FABRICATION) for key, label, _ in MAS_FABRICATION_MILESTONES),
)
MAS_PHASE_LABELS: Mapping[str, str] = {
    MAS_ACQUISITION: "Aquisição",
    MAS_FABRICATION: "Fabricação e entrega",
}

# The situations of the line of the map, in the words of the prototype (``sit`` de ``linhaMas``).
MAS_DELIVERED = "Entregue"
MAS_CONTRACTED = "Contratado"
MAS_CRITICAL = "Crítico"
MAS_WARNING = "Atenção"
MAS_ON_TIME = "No prazo"
MAS_LINE_SITUATIONS: tuple[str, ...] = (
    MAS_CRITICAL,
    MAS_WARNING,
    MAS_ON_TIME,
    MAS_DELIVERED,
    MAS_CONTRACTED,
)


def estimated_fabrication_date(
    start: date | None, delivery: date | None, position: int
) -> date | None:
    """The estimated date of a manufacturing milestone between the order and the delivery target.

    A package still without an order has no contractual schedule; the map estimates its
    manufacturing baseline between the planned order and the ROS, on the same shares the emission
    uses (``MANUFACTURING_MILESTONES``). The prototype interpolated to the planned delivery of the
    mock (``plano.entrega``), a column the model does not have (DECISION, ISSUE-058); the ROS is
    the delivery target of the plan (DIVERGENCIAS-DO-PROTOTIPO).
    """
    if start is None or delivery is None:
        return None
    return _between(start, delivery, MANUFACTURING_MILESTONES[position][1])


def mas_line_situation(*, concluded: bool, service: bool, band: str, has_overdue: bool) -> str:
    """How the line of the map reads: delivered or contracted, critical, warning or on time.

    The prototype's ``sit`` of the line: a package already delivered (equipment) or contracted
    (service and EPC) closes the cycle; the rest is critical with negative slack, a warning within
    the alert window or with an overdue milestone, and on time otherwise.
    """
    if concluded:
        return MAS_CONTRACTED if service else MAS_DELIVERED
    if band == SLACK_CRITICAL:
        return MAS_CRITICAL
    if band == SLACK_WARNING or has_overdue:
        return MAS_WARNING
    return MAS_ON_TIME


@dataclass(frozen=True)
class MasProgressMilestone:
    """One milestone of the map for the progress: its parameter weight and its layers."""

    weight: int
    applicable: bool
    baseline: date | None
    real: date | None


@dataclass(frozen=True)
class MasProgress:
    """The progress of the map: the realized and the planned percentages and their index."""

    realized_pct: Decimal
    planned_pct: Decimal

    @property
    def index(self) -> Decimal | None:
        """Real over planned, two decimals; ``None`` when nothing is planned yet."""
        if not self.planned_pct:
            return None
        return (self.realized_pct / self.planned_pct).quantize(
            ONE_HUNDREDTH, rounding=ROUND_HALF_UP
        )


# How the index of the advance reads: on the pace of the baseline, near it or below it.
PROGRESS_ON_PACE = "no-ritmo"
PROGRESS_NEAR = "proximo"
PROGRESS_BELOW = "abaixo"


def progress_band(index: Decimal | None) -> str | None:
    """The band of the index: on pace at 1.00 or more, near at 0.95, below under it."""
    if index is None:
        return None
    if index >= 1:
        return PROGRESS_ON_PACE
    return PROGRESS_NEAR if index >= Decimal("0.95") else PROGRESS_BELOW


def _progress_pct(part: int, whole: int) -> Decimal:
    """The percentage of the weights, one decimal, half up, as the prototype rounds it."""
    if whole <= 0:
        return Decimal(0)
    return (Decimal(part) / Decimal(whole) * HUNDRED).quantize(ONE_TENTH, rounding=ROUND_HALF_UP)


def package_progress(
    milestones: Iterable[MasProgressMilestone], *, reference_date: date
) -> MasProgress:
    """The progress of one package: the weights of the applicable milestones.

    The realized part is the weight of the milestones already done and the planned part is the
    weight of the ones whose baseline is up to the reference date; the weight of a milestone that
    does not apply (the manufacturing half of a service/EPC package) stays out of the total, so
    the acquisition half is renormalized by itself. One decimal, half up.
    """
    applicable = [milestone for milestone in milestones if milestone.applicable]
    total = sum(milestone.weight for milestone in applicable)
    done = sum(milestone.weight for milestone in applicable if milestone.real is not None)
    planned = sum(
        milestone.weight
        for milestone in applicable
        if milestone.baseline is not None and milestone.baseline <= reference_date
    )
    return MasProgress(
        realized_pct=_progress_pct(done, total),
        planned_pct=_progress_pct(planned, total),
    )


def procurement_progress(packages: Iterable[tuple[MasProgress, int]]) -> MasProgress:
    """The procurement progress: the progress of each package weighted by its value.

    ``packages`` are ``(progress, value in cents)`` pairs; the value of a package is the
    adjudicated one (the order or the recommendation), else the estimate (the prototype's
    ``adjudicado || estimativa``). Both percentages and the index read one and two decimals, half
    up, as the prototype printed them.
    """
    entries = list(packages)
    total_value = sum(value for _, value in entries)
    if total_value <= 0:
        return MasProgress(Decimal(0), Decimal(0))
    realized = (
        sum(progress.realized_pct * value for progress, value in entries) / Decimal(total_value)
    ).quantize(ONE_TENTH, rounding=ROUND_HALF_UP)
    planned = (
        sum(progress.planned_pct * value for progress, value in entries) / Decimal(total_value)
    ).quantize(ONE_TENTH, rounding=ROUND_HALF_UP)
    return MasProgress(realized_pct=realized, planned_pct=planned)


# ── The panel (ISSUE-063) ────────────────────────────────────────────────────────────────────
#
# The nine indicators of the prototype and the three cumulative curves of the panel are pure
# functions too, so the screen, the seed, the exports and the oracle share the same arithmetic:
# adherence, the mean cycle, the two savings, the emergency share, the committed-against-budget
# share and the curves of contracting, saving and the MAP advancement (baseline, real and trend).


def purchase_plan_adherence(adjudicated: int, planned: int) -> Decimal | None:
    """The adherence to the purchase plan: adjudicated over planned until the date, in percent.

    The prototype's ``aderenciaPct``: one decimal, half up; without anything planned there is no
    adherence.
    """
    if planned <= 0:
        return None
    return (Decimal(adjudicated) / Decimal(planned) * HUNDRED).quantize(
        ONE_TENTH, rounding=ROUND_HALF_UP
    )


def average_cycle_days(days: Iterable[int]) -> int | None:
    """The mean purchase cycle, in whole days, half up (the prototype's ``Math.round``).

    Without any cycle there is no mean.
    """
    values = list(days)
    if not values:
        return None
    mean = Decimal(sum(values)) / Decimal(len(values))
    return int(mean.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def saving_pct(base_cents: int, paid_cents: int) -> Decimal | None:
    """The saving over a base value, in percent: ``(base - paid) / base``.

    The same arithmetic serves the saving over the estimate and the saving in the negotiation
    (the base is the estimate or the winner's first proposal); one decimal, half up, and no
    saving without a base.
    """
    if base_cents <= 0:
        return None
    return (Decimal(base_cents - paid_cents) / Decimal(base_cents) * HUNDRED).quantize(
        ONE_TENTH, rounding=ROUND_HALF_UP
    )


def emergency_share(emergency_cents: int, adjudicated_cents: int) -> Decimal | None:
    """The share of emergency purchases: the emergency value over the adjudicated value."""
    if adjudicated_cents <= 0:
        return None
    return (Decimal(emergency_cents) / Decimal(adjudicated_cents) * HUNDRED).quantize(
        ONE_TENTH, rounding=ROUND_HALF_UP
    )


def committed_over_budget(adjudicated_cents: int, budget_cents: int) -> Decimal | None:
    """Comprometido x orçado: the adjudicated value over the current budget of the EAC items."""
    if budget_cents <= 0:
        return None
    return (Decimal(adjudicated_cents) / Decimal(budget_cents) * HUNDRED).quantize(
        ONE_TENTH, rounding=ROUND_HALF_UP
    )


def average_offers(counts: Iterable[int]) -> Decimal | None:
    """The mean of valid proposals per package, one decimal, half up; without any, ``None``."""
    values = list(counts)
    if not values:
        return None
    return (Decimal(sum(values)) / Decimal(len(values))).quantize(ONE_TENTH, rounding=ROUND_HALF_UP)


def single_supplier_share(flags: Iterable[bool]) -> Decimal | None:
    """The share of the packages with a single supplier, in percent, one decimal, half up."""
    values = list(flags)
    if not values:
        return None
    return (Decimal(sum(1 for flag in values if flag)) / Decimal(len(values)) * HUNDRED).quantize(
        ONE_TENTH, rounding=ROUND_HALF_UP
    )


def month_start(value: date) -> date:
    """The first day of the month of a date: the key of the monthly curves."""
    return value.replace(day=1)


def month_end(value: date) -> date:
    """The last day of the month of a date."""
    if value.month == 12:
        following = date(value.year + 1, 1, 1)
    else:
        following = date(value.year, value.month + 1, 1)
    return following - timedelta(days=1)


def _months_between(first: date, last: date) -> tuple[date, ...]:
    """The first day of every month from ``first`` to ``last``, both included."""
    months: list[date] = []
    current = month_start(first)
    limit = month_start(last)
    while current <= limit:
        months.append(current)
        current = month_end(current) + timedelta(days=1)
    return tuple(months)


@dataclass(frozen=True)
class ContractingCurve:
    """The contracting curve: adjudicated packages accumulated, plan against real, by month."""

    months: tuple[date, ...]
    planned: tuple[int, ...]
    realized: tuple[int | None, ...]
    cut_month: date


def contracting_curve(
    planned_dates: Iterable[date],
    realized_dates: Iterable[date],
    *,
    reference_date: date,
) -> ContractingCurve:
    """The accumulated adjudications per month: the plan and the real until the cut month.

    The months run from the first date to the last one or the reference month, whichever is
    later; the realized count is ``None`` after the month of the reference date, as the
    prototype's curve (the plan keeps going to the right).
    """
    planned = [value for value in planned_dates if value is not None]
    realized = [value for value in realized_dates if value is not None]
    if not planned and not realized:
        return ContractingCurve((), (), (), month_start(reference_date))
    months = _months_between(min([*planned, *realized]), max([*planned, *realized, reference_date]))
    cut = month_start(reference_date)
    return ContractingCurve(
        months=months,
        planned=tuple(
            sum(1 for value in planned if month_start(value) <= month) for month in months
        ),
        realized=tuple(
            None if month > cut else sum(1 for value in realized if month_start(value) <= month)
            for month in months
        ),
        cut_month=cut,
    )


@dataclass(frozen=True)
class SavingCurve:
    """The saving curve: the accumulated saving over the estimate and in the negotiation."""

    months: tuple[date, ...]
    estimated: tuple[int | None, ...]
    negotiation: tuple[int | None, ...]
    cut_month: date


def saving_curve(
    entries: Iterable[tuple[date, int, int | None]],
    *,
    reference_date: date,
) -> SavingCurve:
    """The accumulated saving per adjudication month.

    ``entries`` are ``(adjudication date, saving over the estimate, saving in the negotiation or
    ``None``)``; a package without a first proposal does not sum in the negotiation line. Both
    lines are ``None`` after the cut month, as the prototype's chart.
    """
    rows = list(entries)
    if not rows:
        return SavingCurve((), (), (), month_start(reference_date))
    months = _months_between(
        min(row[0] for row in rows), max([*(row[0] for row in rows), reference_date])
    )
    cut = month_start(reference_date)
    return SavingCurve(
        months=months,
        estimated=tuple(
            None if month > cut else sum(row[1] for row in rows if month_start(row[0]) <= month)
            for month in months
        ),
        negotiation=tuple(
            None
            if month > cut
            else sum(row[2] or 0 for row in rows if month_start(row[0]) <= month)
            for month in months
        ),
        cut_month=cut,
    )


@dataclass(frozen=True)
class ProgressCurveMilestone:
    """One milestone for the advancement curve: its weight, applicability and its three layers."""

    weight: int
    applicable: bool
    baseline: date | None
    forecast: date | None
    real: date | None


@dataclass(frozen=True)
class ProcurementCurve:
    """The advancement curve of the map: the baseline, the real and the trend, per month."""

    months: tuple[date, ...]
    baseline: tuple[Decimal, ...]
    real: tuple[Decimal | None, ...]
    trend: tuple[Decimal | None, ...]
    cut_month: date


def procurement_curve(
    packages: Iterable[tuple[Iterable[ProgressCurveMilestone], int]],
    *,
    reference_date: date,
) -> ProcurementCurve | None:
    """The advancement of the map per month, weighted by the value of the package.

    ``packages`` are ``(milestones, value in cents)`` pairs. The baseline of a month counts the
    applicable milestones whose baseline is up to its end; the real counts the realized ones up
    to the cut (the reference date in the cut month, ``None`` after it) and the trend follows the
    real, the forecast or the baseline of each milestone after the cut. The weights of the
    milestones that do not apply stay out, so a service package renormalizes its acquisition half
    (the same rule of ``package_progress``; the prototype's curve did not renormalize — DIVERGENCIAS).
    A package with no date and no value leaves no curve.
    """
    entries = [(list(milestones), value) for milestones, value in packages]
    dates = [
        value
        for milestones, _ in entries
        for milestone in milestones
        if milestone.applicable
        for value in (milestone.baseline, milestone.forecast, milestone.real)
        if value is not None
    ]
    total_value = sum(value for _, value in entries)
    if not dates or total_value <= 0:
        return None
    months = _months_between(min(dates), max([*dates, reference_date]))
    cut = month_start(reference_date)

    def percentage(until: date, layer: str) -> Decimal:
        weighted = Decimal(0)
        for milestones, value in entries:
            applicable = [milestone for milestone in milestones if milestone.applicable]
            total = sum(milestone.weight for milestone in applicable)
            if total <= 0:
                continue
            done = sum(
                milestone.weight
                for milestone in applicable
                if (moment := _curve_layer(milestone, layer)) is not None and moment <= until
            )
            weighted += Decimal(value) * Decimal(done) / Decimal(total)
        return (weighted / Decimal(total_value) * HUNDRED).quantize(
            ONE_TENTH, rounding=ROUND_HALF_UP
        )

    return ProcurementCurve(
        months=months,
        baseline=tuple(percentage(month_end(month), "baseline") for month in months),
        real=tuple(
            None
            if month > cut
            else percentage(reference_date if month == cut else month_end(month), "real")
            for month in months
        ),
        trend=tuple(
            None
            if month < cut
            else percentage(
                reference_date if month == cut else month_end(month),
                "real" if month == cut else "fallback",
            )
            for month in months
        ),
        cut_month=cut,
    )


def _curve_layer(milestone: ProgressCurveMilestone, layer: str) -> date | None:
    """The date the curve reads of a milestone: one layer, or the first one that exists."""
    if layer == "fallback":
        return milestone.real or milestone.forecast or milestone.baseline
    return getattr(milestone, layer)
