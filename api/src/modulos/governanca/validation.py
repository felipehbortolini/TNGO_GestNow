"""Input validation of the Governança module: what a new change and a cancellation must carry.

The rules are those of the prototype (``validarCamposSm`` and ``cancelarMudanca``): a required field
missing, a text too short or too long, a value outside its list or a date after the reference date
is 422 with one message per field, so the form comes back filled with the message under the field.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from src.core.errors import InvalidDataError
from src.modulos.governanca import calculations, models

TITLE_LIMITS = (10, 150)
DESCRIPTION_LIMITS = (20, 1000)
EMERGENCY_JUSTIFICATION_LIMITS = (20, 500)
CANCELLATION_LIMITS = (10, 500)

IMPACT_TEXT_LIMITS = (3, 300)
ACTIVITIES_MAXIMUM = 300
TRANSFER_ROWS = 5

CHECKED_VALUE = "sim"
UNCHECKED_VALUE = "nao"

FIELD_TITLE = "titulo"
FIELD_KIND = "tipo"
FIELD_ORIGIN = "origem"
FIELD_PRIORITY = "prioridade"
FIELD_DESCRIPTION = "descricao"
FIELD_REQUEST_DATE = "data_solicitacao"
FIELD_EARLY_EXECUTION = "execucao_antecipada"
FIELD_EMERGENCY_START = "inicio_emergencia"
FIELD_EMERGENCY_JUSTIFICATION = "justificativa_emergencia"
FIELD_JUSTIFICATION = "justificativa"
FIELD_VERSION = "versao"
FIELD_IMPACT_VERSION = "versao_impacto"
FIELD_RESPONSIBLE = "responsavel_id"
FIELD_DEADLINE = "prazo"
FIELD_COST = "custo"
FIELD_TERM_DAYS = "prazo_dias"
FIELD_CONTRACT_MILESTONE = "marco_contratual"
FIELD_SCOPE = "escopo"
FIELD_QUALITY = "qualidade"
FIELD_RISKS = "riscos"
FIELD_SAFETY = "sms"
FIELD_CONTRACT = "contrato"
FIELD_ACTIVITIES = "atividades"
FIELD_EAC_ITEMS = "itens_eac"
FIELD_SOURCE = "fonte_recurso"
FIELD_AUTHORITY = "alcada"
FIELD_RELEASE_RESERVE = "liberacao_reserva"
FIELD_RELEASE_VALUE = "liberacao_valor"
FIELD_TRANSFERS = "remanejamentos"
TRANSFER_SOURCE = "remanejamento_origem"
TRANSFER_TARGET = "remanejamento_destino"
TRANSFER_VALUE = "remanejamento_valor"

IMPACT_TEXT_FIELDS = (
    (FIELD_SCOPE, "Escopo"),
    (FIELD_QUALITY, "Qualidade"),
    (FIELD_RISKS, "Riscos novos ou alterados"),
    (FIELD_SAFETY, "SMS"),
    (FIELD_CONTRACT, "Contrato"),
)
ZERO_COST_MESSAGES = {
    models.TYPE_REALLOCATION: (
        "Remanejamento não muda o total do orçamento: impacto em custo zero. "
        "Acréscimo exige SM de custo com fonte de recurso."
    ),
    models.TYPE_RESERVE_RELEASE: (
        "Liberação de reserva não muda o orçado da EAC: impacto em custo zero."
    ),
}
MONEY_PATTERN = re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d{1,2})?$")
ITEM_SEPARATORS = re.compile(r"[,;\s]+")

DATE_AFTER_TODAY_MESSAGE = "A data não pode ser posterior a hoje."
INVALID_DATE_MESSAGE = "Informe uma data válida."

type Form = Mapping[str, str | None]
type Messages = dict[str, str]


@dataclass(frozen=True)
class NewChange:
    """A request that passed the rules: what the facade writes."""

    title: str
    kind: str
    origin: str
    priority: str
    description: str
    request_date: date
    emergency_start: date | None = None
    emergency_justification: str | None = None

    @property
    def is_emergency_execution(self) -> bool:
        """Whether the execution started before the decision (the emergency was marked)."""
        return self.emergency_start is not None


def validate_new_change(form: Form, *, reference_date: date) -> NewChange:
    """The request of the form, or 422 with a message per field that breaks a rule."""
    messages: Messages = {}
    title = _text(form, FIELD_TITLE, "Título", TITLE_LIMITS, messages)
    description = _text(
        form, FIELD_DESCRIPTION, "Descrição e justificativa", DESCRIPTION_LIMITS, messages
    )
    kind = _choice(form, FIELD_KIND, models.CHANGE_TYPES, "Escolha o tipo da mudança.", messages)
    origin = _choice(form, FIELD_ORIGIN, models.CHANGE_ORIGINS, "Escolha a origem.", messages)
    priority = _choice(
        form, FIELD_PRIORITY, models.CHANGE_PRIORITIES, "Escolha a prioridade.", messages
    )
    request_date = _request_date(form, reference_date, messages)
    start, justification = _emergency(form, priority, request_date, reference_date, messages)
    if messages or request_date is None:
        raise InvalidDataError(messages)
    return NewChange(
        title=title,
        kind=kind,
        origin=origin,
        priority=priority,
        description=description,
        request_date=request_date,
        emergency_start=start,
        emergency_justification=justification,
    )


def validate_cancellation_justification(form: Form) -> str:
    """The justification of a cancellation, or 422: it is mandatory, 10 to 500 characters."""
    messages: Messages = {}
    justification = _text(
        form, FIELD_JUSTIFICATION, "Justificativa do cancelamento", CANCELLATION_LIMITS, messages
    )
    if messages:
        raise InvalidDataError(messages)
    return justification


def _text(form: Form, field: str, label: str, limits: tuple[int, int], messages: Messages) -> str:
    minimum, maximum = limits
    text = (form.get(field) or "").strip()
    if not text:
        messages[field] = f"{label} é obrigatório."
    elif len(text) < minimum:
        messages[field] = f"{label}: mínimo de {minimum} caracteres."
    elif len(text) > maximum:
        messages[field] = f"{label}: máximo de {maximum} caracteres."
    return text


def _choice(
    form: Form, field: str, options: tuple[str, ...], message: str, messages: Messages
) -> str:
    value = (form.get(field) or "").strip()
    if value not in options:
        messages[field] = message
    return value


def _date_field(form: Form, field: str, missing: str, messages: Messages) -> date | None:
    raw = (form.get(field) or "").strip()
    if not raw:
        messages[field] = missing
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        messages[field] = INVALID_DATE_MESSAGE
        return None


def _request_date(form: Form, reference_date: date, messages: Messages) -> date | None:
    found = _date_field(form, FIELD_REQUEST_DATE, "Informe a data da solicitação.", messages)
    if found is not None and found > reference_date:
        messages[FIELD_REQUEST_DATE] = DATE_AFTER_TODAY_MESSAGE
    return found


def _emergency(
    form: Form,
    priority: str,
    request_date: date | None,
    reference_date: date,
    messages: Messages,
) -> tuple[date | None, str | None]:
    """The start and the justification of the execution ahead of the decision, when it was marked."""
    marked = (
        priority == models.PRIORITY_EMERGENCY and form.get(FIELD_EARLY_EXECUTION) == CHECKED_VALUE
    )
    if not marked:
        return None, None
    start = _date_field(form, FIELD_EMERGENCY_START, "Informe quando a execução começou.", messages)
    _check_emergency_start(start, request_date, reference_date, messages)
    justification = _text(
        form,
        FIELD_EMERGENCY_JUSTIFICATION,
        "Justificativa da emergência",
        EMERGENCY_JUSTIFICATION_LIMITS,
        messages,
    )
    return start, justification


def _check_emergency_start(
    start: date | None, request_date: date | None, reference_date: date, messages: Messages
) -> None:
    if start is None:
        return
    if start > reference_date:
        messages[FIELD_EMERGENCY_START] = DATE_AFTER_TODAY_MESSAGE
    elif request_date is not None and start < request_date:
        messages[FIELD_EMERGENCY_START] = (
            "A execução não pode começar antes do registro (registro imediato é obrigatório)."
        )


# ── The analysis: start and impact (ISSUE-024) ───────────────────────────


@dataclass(frozen=True)
class AnalysisStart:
    """The start of the analysis that passed the rules: who answers for it and until when."""

    responsible_id: int
    deadline: date


def validate_analysis_start(
    form: Form, *, people_ids: frozenset[int], reference_date: date
) -> AnalysisStart:
    """The responsible and the deadline of the analysis, or 422 with a message per field."""
    messages: Messages = {}
    responsible = _responsible(form, people_ids, messages)
    deadline = _date_field(form, FIELD_DEADLINE, "Informe o prazo da análise.", messages)
    if deadline is not None and deadline < reference_date:
        messages[FIELD_DEADLINE] = "O prazo não pode ser anterior à data de referência."
    if messages or responsible is None or deadline is None:
        raise InvalidDataError(messages)
    return AnalysisStart(responsible_id=responsible, deadline=deadline)


def _responsible(form: Form, people_ids: frozenset[int], messages: Messages) -> int | None:
    raw = (form.get(FIELD_RESPONSIBLE) or "").strip()
    if raw.isdigit() and int(raw) in people_ids:
        return int(raw)
    messages[FIELD_RESPONSIBLE] = "Escolha o responsável pela análise."
    return None


@dataclass(frozen=True)
class TransferInput:
    """A transfer between two EAC items, by code, with the amount in cents."""

    source_code: str
    target_code: str
    value_cents: int


@dataclass(frozen=True)
class ImpactInput:
    """The impact analysis that passed the rules, with the authority the server requires of it."""

    cost_cents: int
    term_days: int
    affects_contract_milestone: bool
    scope: str
    quality: str
    risks: str
    safety: str
    contract: str
    activities: str
    item_codes: tuple[str, ...]
    resource_source: str | None
    authority: str
    required_authority: str
    release_reserve: str | None = None
    release_cents: int | None = None
    transfers: tuple[TransferInput, ...] = ()


@dataclass(frozen=True)
class ImpactRules:
    """What the rules of the impact read of the change: its type and the references of the authority."""

    kind: str
    budget_cents: int | None
    manager_limit_percent: Decimal | int | float


def validate_impact(form: Form, *, rules: ImpactRules) -> ImpactInput:
    """The impact analysis of the form, or 422 with a message per field that breaks a rule.

    Cost and term are mandatory (zero when there is none); the five texts are 3 to 300 characters
    ("Sem impacto" is an answer); a positive cost needs the source of the resource; a reallocation or a
    release of reserve has zero cost and its own fields; the authority cannot be below the required one.
    """
    messages: Messages = {}
    cost = _cost(form, rules.kind, messages)
    term = _term_days(form, messages)
    milestone = _milestone(form, messages)
    texts = {
        field: _text(form, field, label, IMPACT_TEXT_LIMITS, messages)
        for field, label in IMPACT_TEXT_FIELDS
    }
    activities = _optional_text(form, FIELD_ACTIVITIES, "Atividades do cronograma", messages)
    codes = _item_codes(form.get(FIELD_EAC_ITEMS))
    source = _source(form, cost, messages)
    release = _release(form, rules.kind, messages)
    transfers = _transfers(form, rules.kind, messages)
    chosen = _choice(
        form, FIELD_AUTHORITY, models.CHANGE_AUTHORITIES, "Escolha a alçada de decisão.", messages
    )
    required = calculations.required_change_authority(
        calculations.AuthorityFacts(
            kind=rules.kind,
            resource_source=source,
            cost_cents=cost or 0,
            transferred_cents=sum(item.value_cents for item in transfers),
            budget_cents=rules.budget_cents,
            affects_contract_milestone=bool(milestone),
        ),
        manager_limit_percent=rules.manager_limit_percent,
    )
    _check_authority(chosen, required.authority, rules.kind, source, messages)
    if messages or cost is None or term is None or milestone is None:
        raise InvalidDataError(messages)
    return ImpactInput(
        cost_cents=cost,
        term_days=term,
        affects_contract_milestone=milestone,
        scope=texts[FIELD_SCOPE],
        quality=texts[FIELD_QUALITY],
        risks=texts[FIELD_RISKS],
        safety=texts[FIELD_SAFETY],
        contract=texts[FIELD_CONTRACT],
        activities=activities,
        item_codes=codes,
        resource_source=source,
        authority=chosen,
        required_authority=required.authority,
        release_reserve=release[0],
        release_cents=release[1],
        transfers=transfers,
    )


def parse_money(text: str) -> int | None:
    """Cents of a value written in reais (``1.234,56``, ``-500``), or ``None`` when it is not one."""
    cleaned = text.replace("R$", "").replace(" ", "").strip()
    if not MONEY_PATTERN.match(cleaned):
        return None
    try:
        reais = Decimal(cleaned.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None
    return int(reais * 100)


def _cost(form: Form, kind: str, messages: Messages) -> int | None:
    raw = (form.get(FIELD_COST) or "").strip()
    cents = parse_money(raw) if raw else None
    if cents is None:
        messages[FIELD_COST] = (
            "Informe o impacto em custo (zero se não houver; negativo para redução)."
        )
    elif cents != 0 and kind in ZERO_COST_MESSAGES:
        messages[FIELD_COST] = ZERO_COST_MESSAGES[kind]
    return cents


def _term_days(form: Form, messages: Messages) -> int | None:
    raw = (form.get(FIELD_TERM_DAYS) or "").strip()
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    messages[FIELD_TERM_DAYS] = (
        "Informe o impacto em prazo em dias inteiros (zero se não houver; negativo para antecipação)."
    )
    return None


def _milestone(form: Form, messages: Messages) -> bool | None:
    value = (form.get(FIELD_CONTRACT_MILESTONE) or "").strip()
    if value in (CHECKED_VALUE, UNCHECKED_VALUE):
        return value == CHECKED_VALUE
    messages[FIELD_CONTRACT_MILESTONE] = "Informe se a mudança afeta marco contratual."
    return None


def _optional_text(form: Form, field: str, label: str, messages: Messages) -> str:
    text = (form.get(field) or "").strip()
    if len(text) > ACTIVITIES_MAXIMUM:
        messages[field] = f"{label}: máximo de {ACTIVITIES_MAXIMUM} caracteres."
    return text


def _item_codes(raw: str | None) -> tuple[str, ...]:
    """The codes of the EAC items written in the field, without repetition and in order."""
    found = [code for code in ITEM_SEPARATORS.split(raw or "") if code]
    return tuple(dict.fromkeys(found))


def _source(form: Form, cost: int | None, messages: Messages) -> str | None:
    """The source of the resource: mandatory when the cost is positive, and only then kept."""
    if cost is None or cost <= 0:
        return None
    source = (form.get(FIELD_SOURCE) or "").strip()
    if source not in models.RESOURCE_SOURCES:
        messages[FIELD_SOURCE] = (
            "Informe a fonte do recurso (aditivo de orçamento, reserva de contingência "
            "ou reserva gerencial)."
        )
        return None
    return source


def _release(form: Form, kind: str, messages: Messages) -> tuple[str | None, int | None]:
    if kind != models.TYPE_RESERVE_RELEASE:
        return None, None
    reserve = (form.get(FIELD_RELEASE_RESERVE) or "").strip()
    if reserve not in models.RELEASE_RESERVES:
        messages[FIELD_RELEASE_RESERVE] = "Escolha a reserva a liberar (contingência ou gerencial)."
    cents = parse_money((form.get(FIELD_RELEASE_VALUE) or "").strip())
    if cents is None or cents <= 0:
        messages[FIELD_RELEASE_VALUE] = "Informe o valor a liberar, maior que zero."
        cents = None
    return (reserve if reserve in models.RELEASE_RESERVES else None), cents


def _transfers(form: Form, kind: str, messages: Messages) -> tuple[TransferInput, ...]:
    if kind != models.TYPE_REALLOCATION:
        return ()
    found = []
    for number in range(1, TRANSFER_ROWS + 1):
        row = _transfer_row(form, number, messages)
        if row is not None:
            found.append(row)
    if not found and FIELD_TRANSFERS not in messages:
        messages[FIELD_TRANSFERS] = "Informe ao menos uma transferência entre itens da EAC."
    return tuple(found)


def _transfer_row(form: Form, number: int, messages: Messages) -> TransferInput | None:
    source = (form.get(f"{TRANSFER_SOURCE}_{number}") or "").strip()
    target = (form.get(f"{TRANSFER_TARGET}_{number}") or "").strip()
    raw = (form.get(f"{TRANSFER_VALUE}_{number}") or "").strip()
    if not (source or target or raw):
        return None
    cents = parse_money(raw) if raw else None
    problem = _transfer_problem(source, target, cents)
    if problem:
        messages[FIELD_TRANSFERS] = f"Transferência {number}: {problem}"
        return None
    return TransferInput(source_code=source, target_code=target, value_cents=cents or 0)


def _transfer_problem(source: str, target: str, cents: int | None) -> str | None:
    if not source or not target:
        return "informe o item de origem e o de destino."
    if source == target:
        return "origem e destino devem ser itens diferentes."
    if cents is None or cents <= 0:
        return "informe um valor maior que zero."
    return None


def _check_authority(
    chosen: str, required: str, kind: str, source: str | None, messages: Messages
) -> None:
    if FIELD_AUTHORITY in messages or not calculations.is_authority_lowered(chosen, required):
        return
    if kind == models.TYPE_RESERVE_RELEASE:
        messages[FIELD_AUTHORITY] = "Liberação de reserva é decidida pelo Comitê (patrocinador)."
    elif source == models.SOURCE_MANAGEMENT_RESERVE:
        messages[FIELD_AUTHORITY] = (
            "A reserva gerencial só é liberada pelo Comitê (patrocinador): eleve a alçada."
        )
    else:
        messages[FIELD_AUTHORITY] = (
            "O impacto exige decisão do Comitê: a alçada pode ser elevada, nunca rebaixada."
        )
