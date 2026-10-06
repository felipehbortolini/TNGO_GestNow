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
from src.modulos.governanca import calculations, lessons_models, models

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


# ── A decisão e o encerramento (ISSUE-025) ───────────────────────────────────────────────────

FIELD_RESULT = "resultado"
FIELD_DECISION_DATE = "data"
FIELD_PARTICIPANTS = "participantes"
FIELD_CONDITIONS = "condicoes"
FIELD_REAPPEAR = "reapresentar_em"
FIELD_ACTIONS = "acoes"
FIELD_PLANNED = "prevista"
FIELD_ATA = "ata_id"
FIELD_SCHEDULE = "cronograma"
FIELD_CLOSING_CONTRACT = "contrato"
FIELD_CLOSING_RISKS = "riscos"
FIELD_CLOSING_NOTE = "observacao"
FIELD_LESSON = "registrar_licao"
FIELD_LESSON_TITLE = "licao_titulo"
FIELD_LESSON_KIND = "licao_tipo"
FIELD_LESSON_PHASE = "licao_fase"
FIELD_LESSON_DISCIPLINE = "licao_disciplina"
FIELD_LESSON_RECOMMENDATION = "licao_recomendacao"

DECISION_TEXT_LIMITS = (10, 600)
CONDITIONS_LIMITS = (10, 600)
CLOSING_NOTE_MAXIMUM = 500
LESSON_TITLE_LIMITS = (10, 150)
LESSON_RECOMMENDATION_LIMITS = (20, 1000)

DECISION_RESULT_REQUIRED = "Escolha a decisão."
DECISION_DATE_REQUIRED = "Informe a data da decisão."
DECISION_DATE_BEFORE_ANALYSIS = "A decisão não pode ser anterior à análise de impacto."
DECISION_QUORUM_REQUIRED = "O Comitê exige quórum de {quorum} participantes."
DECISION_MANAGER_REQUIRED = "Na alçada do gerente do projeto, {name} precisa constar como decisor."
DECISION_REAPPEAR_REQUIRED = "Informe quando a solicitação volta à pauta."
DECISION_REAPPEAR_ORDER = "A reapresentação precisa ser depois da decisão."
DECISION_PLANNED_REQUIRED = "Informe a data prevista das ações de implementação."
DECISION_PLANNED_ORDER = "A data prevista não pode ser anterior à decisão."
DECISION_ATA_UNKNOWN = "A ata informada não pertence ao projeto da mudança."
DECISION_ONLY_AWAITING = (
    "Só há decisão para solicitação Aguardando comitê. Conclua a análise de impacto antes."
)
DECISION_IMPACT_REQUIRED = "A análise de impacto é obrigatória antes da decisão."
CLOSING_ONLY_IMPLEMENTING = "Só uma mudança Em implementação é encerrada."
CLOSING_OPEN_ACTIONS = (
    "Há {count} ação(ões) de implementação em aberto: conclua-as na Central antes de encerrar."
)
CLOSING_SCHEDULE_REQUIRED = (
    "Confirme que a linha de base do cronograma e a Curva S física foram atualizadas."
)
CLOSING_CONTRACT_REQUIRED = "Confirme que o aditivo contratual foi formalizado."
CLOSING_RISKS_REQUIRED = "Confirme que os riscos afetados foram revisados no registro."
CLOSING_DATE_REQUIRED = "Informe a data do encerramento."
REOPEN_NOT_POSTPONED = "Só uma solicitação Adiada volta à pauta."


@dataclass(frozen=True)
class DecisionInput:
    """A decisão que passou pelas regras: o resultado, quem decidiu e o que ele gera."""

    result: str
    decision_date: date | None
    participants: tuple[int, ...]
    justification: str
    conditions: str
    reappear_on: date | None
    ata_id: int | None
    actions: tuple[str, ...]
    planned_date: date | None
    version: int | str | None = None


@dataclass(frozen=True)
class ClosingLesson:
    """A lição opcional do encerramento, como o formulário a pede."""

    title: str
    kind: str
    phase: str
    discipline: str
    recommendation: str


@dataclass(frozen=True)
class ClosingInput:
    """O encerramento que passou pelas regras: a data, as confirmações, a observação e a lição."""

    closing_date: date | None
    schedule: bool
    contract: bool
    risks: bool
    note: str
    lesson: ClosingLesson | None
    version: int | str | None = None


def parse_decision(form: Mapping[str, object]) -> DecisionInput:
    """A decisão do formulário; os campos de lista chegam já como sequências."""
    return DecisionInput(
        result=(_string(form.get(FIELD_RESULT))).strip(),
        decision_date=_date_value(form.get(FIELD_DECISION_DATE)),
        participants=_id_list(form.get(FIELD_PARTICIPANTS)),
        justification=_string(form.get(FIELD_JUSTIFICATION)).strip(),
        conditions=_string(form.get(FIELD_CONDITIONS)).strip(),
        reappear_on=_date_value(form.get(FIELD_REAPPEAR)),
        ata_id=_int_value(form.get(FIELD_ATA)),
        actions=_text_list(form.get(FIELD_ACTIONS)),
        planned_date=_date_value(form.get(FIELD_PLANNED)),
        version=_version_value(form.get(FIELD_VERSION)),
    )


@dataclass(frozen=True)
class DecisionFacts:
    """O que a ficha diz para a decisão: a alçada, o gerente, o quórum e a data da análise."""

    authority: str | None
    manager_id: int | None
    manager_name: str
    quorum: int
    impact_date: date | None
    reference_date: date


def decision_problems(data: DecisionInput, facts: DecisionFacts) -> dict[str, str]:
    """As mensagens da decisão por campo; vazio quando ela pode ser registrada (HU-127)."""
    problems: Messages = {}
    if data.result not in models.DECISION_RESULTS:
        problems[FIELD_RESULT] = DECISION_RESULT_REQUIRED
    problems.update(_decision_date_problems(data, facts))
    problems.update(_decision_people_problems(data, facts))
    _limits_problem(
        data.justification,
        "Justificativa da decisão",
        DECISION_TEXT_LIMITS,
        FIELD_JUSTIFICATION,
        problems,
    )
    problems.update(_decision_outcome_problems(data))
    return problems


def _decision_date_problems(data: DecisionInput, facts: DecisionFacts) -> dict[str, str]:
    if data.decision_date is None:
        return {FIELD_DECISION_DATE: DECISION_DATE_REQUIRED}
    if data.decision_date > facts.reference_date:
        return {FIELD_DECISION_DATE: DATE_AFTER_TODAY_MESSAGE}
    if facts.impact_date is not None and data.decision_date < facts.impact_date:
        return {FIELD_DECISION_DATE: DECISION_DATE_BEFORE_ANALYSIS}
    return {}


def _decision_people_problems(data: DecisionInput, facts: DecisionFacts) -> dict[str, str]:
    if facts.authority == models.AUTHORITY_COMMITTEE and len(data.participants) < facts.quorum:
        return {FIELD_PARTICIPANTS: DECISION_QUORUM_REQUIRED.format(quorum=facts.quorum)}
    if facts.authority == models.AUTHORITY_MANAGER and (
        facts.manager_id is None or facts.manager_id not in data.participants
    ):
        return {FIELD_PARTICIPANTS: DECISION_MANAGER_REQUIRED.format(name=facts.manager_name)}
    return {}


def _decision_outcome_problems(data: DecisionInput) -> dict[str, str]:
    problems: Messages = {}
    if data.result == models.SITUATION_APPROVED_WITH_CONDITIONS:
        _limits_problem(data.conditions, "Condições", CONDITIONS_LIMITS, FIELD_CONDITIONS, problems)
    if data.result == models.SITUATION_POSTPONED:
        if data.reappear_on is None:
            problems[FIELD_REAPPEAR] = DECISION_REAPPEAR_REQUIRED
        elif data.decision_date is not None and data.reappear_on <= data.decision_date:
            problems[FIELD_REAPPEAR] = DECISION_REAPPEAR_ORDER
    if data.result in models.APPROVED_SITUATIONS and data.actions:
        if data.planned_date is None:
            problems[FIELD_PLANNED] = DECISION_PLANNED_REQUIRED
        elif data.decision_date is not None and data.planned_date < data.decision_date:
            problems[FIELD_PLANNED] = DECISION_PLANNED_ORDER
    return problems


def parse_closing(form: Form) -> ClosingInput:
    """O encerramento do formulário, com a lição opcional quando pedida."""
    lesson = None
    if (form.get(FIELD_LESSON) or "").strip() == CHECKED_VALUE:
        lesson = ClosingLesson(
            title=(form.get(FIELD_LESSON_TITLE) or "").strip(),
            kind=(form.get(FIELD_LESSON_KIND) or "").strip(),
            phase=(form.get(FIELD_LESSON_PHASE) or "").strip(),
            discipline=(form.get(FIELD_LESSON_DISCIPLINE) or "").strip(),
            recommendation=(form.get(FIELD_LESSON_RECOMMENDATION) or "").strip(),
        )
    return ClosingInput(
        closing_date=_date_value(form.get(FIELD_DECISION_DATE)),
        schedule=(form.get(FIELD_SCHEDULE) or "").strip() == CHECKED_VALUE,
        contract=(form.get(FIELD_CLOSING_CONTRACT) or "").strip() == CHECKED_VALUE,
        risks=(form.get(FIELD_CLOSING_RISKS) or "").strip() == CHECKED_VALUE,
        note=(form.get(FIELD_CLOSING_NOTE) or "").strip(),
        lesson=lesson,
        version=form.get(FIELD_VERSION),
    )


def closing_problems(
    data: ClosingInput, *, impact: models.ChangeImpact | None, open_actions: int
) -> dict[str, str]:
    """As mensagens do encerramento: ações abertas, confirmações do impacto e a lição (HU-128)."""
    problems: Messages = {}
    if open_actions:
        problems["geral"] = CLOSING_OPEN_ACTIONS.format(count=open_actions)
    if data.closing_date is None:
        problems[FIELD_DECISION_DATE] = CLOSING_DATE_REQUIRED
    if impact is not None:
        if bool(impact.term_days) and not data.schedule:
            problems[FIELD_SCHEDULE] = CLOSING_SCHEDULE_REQUIRED
        if calculations.has_impact(impact.contract) and not data.contract:
            problems[FIELD_CLOSING_CONTRACT] = CLOSING_CONTRACT_REQUIRED
        if calculations.has_impact(impact.risks) and not data.risks:
            problems[FIELD_CLOSING_RISKS] = CLOSING_RISKS_REQUIRED
    if len(data.note) > CLOSING_NOTE_MAXIMUM:
        problems[FIELD_CLOSING_NOTE] = f"Observações: máximo de {CLOSING_NOTE_MAXIMUM} caracteres."
    if data.lesson is not None:
        problems.update(_lesson_problems(data.lesson))
    return problems


def _lesson_problems(lesson: ClosingLesson) -> dict[str, str]:
    problems: Messages = {}
    _limits_problem(
        lesson.title, "Título da lição", LESSON_TITLE_LIMITS, FIELD_LESSON_TITLE, problems
    )
    _limits_problem(
        lesson.recommendation,
        "Recomendação",
        LESSON_RECOMMENDATION_LIMITS,
        FIELD_LESSON_RECOMMENDATION,
        problems,
    )
    if lesson.kind not in lessons_models.LESSON_TYPES:
        problems[FIELD_LESSON_KIND] = "Escolha o tipo da lição."
    if lesson.phase not in lessons_models.LESSON_PHASES:
        problems[FIELD_LESSON_PHASE] = "Escolha a fase."
    return problems


def _limits_problem(
    text: str, label: str, limits: tuple[int, int], field: str, problems: Messages
) -> None:
    minimum, maximum = limits
    if not text:
        problems[field] = f"{label} é obrigatório."
    elif len(text) < minimum:
        problems[field] = f"{label}: mínimo de {minimum} caracteres."
    elif len(text) > maximum:
        problems[field] = f"{label}: máximo de {maximum} caracteres."


def _string(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _version_value(raw: object) -> int | str | None:
    """A versão que a tela abriu, como o campo a envia; ``None`` quando não veio."""
    return raw if isinstance(raw, (int, str)) else None


def _int_value(raw: object) -> int | None:
    text = _string(raw).strip()
    return int(text) if text.isdigit() else None


def _date_value(raw: object) -> date | None:
    text = _string(raw).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _id_list(raw: object) -> tuple[int, ...]:
    values = raw if isinstance(raw, (list, tuple)) else ([raw] if raw else [])
    parsed = (_int_value(item) for item in values)
    return tuple(dict.fromkeys(item for item in parsed if item is not None))


def _text_list(raw: object) -> tuple[str, ...]:
    values = raw if isinstance(raw, (list, tuple)) else ([raw] if raw else [])
    return tuple(dict.fromkeys(text for text in (_string(item).strip() for item in values) if text))
