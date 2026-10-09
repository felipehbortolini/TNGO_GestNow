"""Input validation of the Risk management module (ISSUE-064).

The shapes the facade receives (identification, assessment, deletion, filters) and the checks of
what a person types. The checks are pure and return one message per field, in a dict that is
empty when everything holds up; the facade turns it into one ``InvalidDataError`` (422), so the
rule holds for the route and for any module that calls the facade.

The response plan, the periodic review, the closing and the reopening (ISSUE-065) follow the
same shape: an input dataclass, a pure check that returns one message per field, and the
constants of the vocabulary the screen and the facade share.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from src.modulos.riscos import calculations
from src.modulos.riscos.calculations import MAX_LEVEL, MIN_LEVEL, OPPORTUNITY, THREAT

NATURES = (THREAT, OPPORTUNITY)
MANUAL_ORIGINS = (
    "Manual",
    "Ata de reunião",
    "Workshop de riscos",
    "Lições aprendidas",
    "Auditoria",
)
ATA_ORIGIN = "Ata de reunião"
SITUATIONS = (
    "Identificado",
    "Em análise",
    "Em tratamento",
    "Monitorado",
    "Materializado",
    "Encerrado",
)
DELETION_REASONS = (
    "Registro em duplicidade",
    "Criado por engano",
    "Não é risco (é problema já ocorrido)",
    "Outro",
)
OTHER_REASON = "Outro"
ASSESSMENT_KINDS = ("inerente", "residual")
INHERENT = "inerente"
RESIDUAL = "residual"
REVIEW_FILTERS = ("vencidas", "proximas", "sem")
SITUATION_ALL = "todas"
SITUATION_ACTIVE = "ativos"

MIN_TEXT = 10
MAX_TEXT = 255
MAX_DESCRIPTION = 1000
MAX_JUSTIFICATION = 500
MAX_SEARCH = 120
MAX_DAYS = 999
PAGE_SIZE = 15
MAX_ID_DIGITS = 18
CENTS = Decimal(100)

# The cell of the matrix as the chart sends it: ``p3|i4`` is probability 3 and impact 4.
CELL_LABEL = re.compile(r"^p([1-5])\|i([1-5])$")

TEXT_REQUIRED = "{label} é obrigatório."
TEXT_TOO_SHORT = "{label}: mínimo de {minimum} caracteres."
TEXT_TOO_LONG = "{label}: máximo de {maximum} caracteres."
CHOOSE_NATURE = "Escolha a natureza."
CHOOSE_CATEGORY = "Escolha a categoria da RBS."
CHOOSE_OWNER = "Escolha o dono do risco."
CHOOSE_ORIGIN = "Escolha a origem."
CHOOSE_ATA = "Escolha a ata de origem."
IDENTIFICATION_DATE_REQUIRED = "Informe a data de identificação."
IDENTIFICATION_IN_THE_FUTURE = "A data de identificação não pode ser futura."
NATURE_LOCKED = (
    "Risco com plano de resposta: a natureza define as estratégias e não pode ser trocada. "
    "Encerre como duplicado e registre um novo."
)
CHOOSE_KIND = "Escolha o tipo da avaliação."
CHOOSE_PROBABILITY = "Escolha a probabilidade."
RATE_A_DIMENSION = "Avalie ao menos uma dimensão de impacto."
CHOOSE_IMPACT = "Escolha o impacto."
INVALID_MONEY = "Informe um valor em reais, como 1.850.000,00."
INVALID_DAYS = "Informe dias (zero ou mais)."
JUSTIFICATION_REQUIRED = (
    "Justifique a avaliação (obrigatória quando o score ou a severidade mudam; "
    f"mínimo de {MIN_TEXT} caracteres)."
)
RESIDUAL_ABOVE_INHERENT = (
    "Para ameaças, o residual não pode superar o inerente. Se a resposta criou nova exposição, "
    "registre um risco secundário."
)
RESIDUAL_NEEDS_PLAN = "A avaliação residual só é habilitada depois que o plano de resposta existir."
CHOOSE_REASON = "Escolha o motivo da exclusão."
REASON_NOTE_REQUIRED = "Detalhe o motivo (obrigatório quando o motivo for Outro)."
CATEGORY_GROUP_REQUIRED = "Informe o grupo (nível 1 da RBS)."
CATEGORY_NAME_REQUIRED = "Informe a subcategoria."
CATEGORY_DUPLICATED = "Categoria já cadastrada."


@dataclass(frozen=True)
class RiskInput:
    """What the form of Novo risco and edição sends: the identification of the risk."""

    nature: str
    category_id: int | None
    cause: str
    title: str
    consequence: str
    owner_id: int | None
    identified_on: date | None
    origin_type: str
    ata_id: int | None = None
    description: str = ""
    trigger: str = ""
    version: int | str | None = None
    project_id: int | None = None
    code: str | None = None


@dataclass(frozen=True)
class AssessmentInput:
    """What the form of the assessment sends: P, the six dimensions, I and the money."""

    kind: str
    probability: int | None
    impact: int | None
    dimensions: Mapping[str, int | None]
    schedule_impact_days: int | None = None
    cost_impact_cents: int | None = None
    life_risk: bool = False
    justification: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class DeletionInput:
    """What the exclusion form sends: the reason, the note and the version the screen opened."""

    reason: str
    note: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class RiskFilters:
    """The filters of the register: what the query string of the screen says."""

    search: str = ""
    nature: str = ""
    category: str = ""
    severities: tuple[str, ...] = ()
    situation: str = SITUATION_ACTIVE
    strategy: str = ""
    owner_id: int | None = None
    review: str = ""
    identified_from: date | None = None
    identified_until: date | None = None
    include_closed: bool = False
    include_deleted: bool = False
    probability: int | None = None
    impact: int | None = None
    assessment: str = RESIDUAL
    page: int = 1


def text_problem(
    value: str, label: str, *, minimum: int = 0, maximum: int = MAX_TEXT
) -> str | None:
    """The message for a required text out of its limits, or ``None``."""
    text = (value or "").strip()
    if not text:
        return TEXT_REQUIRED.format(label=label)
    if len(text) < minimum:
        return TEXT_TOO_SHORT.format(label=label, minimum=minimum)
    if len(text) > maximum:
        return TEXT_TOO_LONG.format(label=label, maximum=maximum)
    return None


def identification_problems(
    data: RiskInput, *, reference_date: date, system_origin: bool = False
) -> dict[str, str]:
    """One message per field of the identification that does not hold up."""
    problems: dict[str, str] = {}
    checks = {
        "causa": text_problem(data.cause, "Causa", minimum=MIN_TEXT),
        "titulo": text_problem(data.title, "Evento", minimum=MIN_TEXT),
        "consequencia": text_problem(data.consequence, "Consequência", minimum=MIN_TEXT),
        "natureza": None if data.nature in NATURES else CHOOSE_NATURE,
        "categoria": None if data.category_id else CHOOSE_CATEGORY,
        "donoId": None if data.owner_id else CHOOSE_OWNER,
        "identificadoEm": _identification_date_problem(data.identified_on, reference_date),
        "gatilho": _optional_length_problem(data.trigger, "Gatilho", MAX_TEXT),
        "descricao": _optional_length_problem(data.description, "Descrição", MAX_DESCRIPTION),
    }
    problems.update({name: message for name, message in checks.items() if message})
    if not system_origin:
        problems.update(_origin_problems(data))
    return problems


def _identification_date_problem(value: date | None, reference_date: date) -> str | None:
    if value is None:
        return IDENTIFICATION_DATE_REQUIRED
    return IDENTIFICATION_IN_THE_FUTURE if value > reference_date else None


def _optional_length_problem(value: str, label: str, maximum: int) -> str | None:
    if len((value or "").strip()) > maximum:
        return TEXT_TOO_LONG.format(label=label, maximum=maximum)
    return None


def _origin_problems(data: RiskInput) -> dict[str, str]:
    if data.origin_type not in MANUAL_ORIGINS:
        return {"origemTipo": CHOOSE_ORIGIN}
    if data.origin_type == ATA_ORIGIN and not data.ata_id:
        return {"ataId": CHOOSE_ATA}
    return {}


def assessment_problems(data: AssessmentInput) -> dict[str, str]:
    """One message per field of the assessment that does not hold up (the worst-case rule included)."""
    problems: dict[str, str] = {}
    if data.probability is None or not MIN_LEVEL <= data.probability <= MAX_LEVEL:
        problems["p"] = CHOOSE_PROBABILITY
    worst = calculations.resulting_impact(data.dimensions)
    if not worst:
        problems["dimensoes"] = RATE_A_DIMENSION
    if data.impact is None or not MIN_LEVEL <= data.impact <= MAX_LEVEL:
        problems["i"] = CHOOSE_IMPACT
    elif worst and calculations.is_impact_reduced(data.impact, data.dimensions):
        problems["i"] = f"O impacto resultante não pode ser menor que a maior dimensão ({worst})."
    if data.schedule_impact_days is not None and not 0 <= data.schedule_impact_days <= MAX_DAYS:
        problems["impactoPrazoDias"] = INVALID_DAYS
    if data.cost_impact_cents is not None and data.cost_impact_cents < 0:
        problems["impactoCustoCentavos"] = INVALID_MONEY
    if len((data.justification or "").strip()) > MAX_JUSTIFICATION:
        problems["justificativa"] = TEXT_TOO_LONG.format(
            label="Justificativa", maximum=MAX_JUSTIFICATION
        )
    return problems


def deletion_problems(data: DeletionInput) -> dict[str, str]:
    """One message per field of the exclusion that does not hold up."""
    if data.reason not in DELETION_REASONS:
        return {"motivo": CHOOSE_REASON}
    if data.reason == OTHER_REASON and len(data.note.strip()) < MIN_TEXT:
        return {"observacao": REASON_NOTE_REQUIRED}
    return {}


def deletion_reason_text(data: DeletionInput) -> str:
    """The reason as it is kept: the chosen one, followed by the note when there is one."""
    note = data.note.strip()
    return f"{data.reason}: {note}" if note else data.reason


def category_problems(group: str, name: str) -> dict[str, str]:
    """One message per field of the quick category that does not hold up."""
    problems: dict[str, str] = {}
    if len((group or "").strip()) < 2:
        problems["grupo"] = CATEGORY_GROUP_REQUIRED
    if len((name or "").strip()) < 2:
        problems["nome"] = CATEGORY_NAME_REQUIRED
    return problems


# ── What a person types, as the route reads it ────────────────────────────────────────────────


def parse_id(raw: str | None) -> int | None:
    """A positive whole number from the request, or ``None`` when it is not one."""
    text = (raw or "").strip()
    if not text.isdigit() or len(text) > MAX_ID_DIGITS or int(text) < 1:
        return None
    return int(text)


def parse_level(raw: str | None) -> int | None:
    """A level from 1 to 5, or ``None``."""
    number = parse_id(raw)
    return number if number is not None and number <= MAX_LEVEL else None


def parse_date(raw: str | None) -> date | None:
    """A date written ``2026-09-25``, or ``None`` when it is empty or not a real date."""
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def parse_days(raw: str | None) -> int | None:
    """Whole days from the request: ``None`` when empty, ``-1`` when it is not a whole number."""
    text = (raw or "").strip()
    if not text:
        return None
    return int(text) if text.isdigit() and len(text) <= MAX_ID_DIGITS else -1


def parse_cents(raw: str | None) -> int | None:
    """Reais written as ``1.850.000,00`` as cents: ``None`` when empty, ``-1`` when invalid."""
    text = (raw or "").strip().replace("R$", "").replace(" ", "")
    if not text:
        return None
    normalized = text.replace(".", "").replace(",", ".")
    try:
        reais = Decimal(normalized)
    except InvalidOperation:
        return -1
    if not reais.is_finite() or reais < 0:
        return -1
    return int((reais * CENTS).to_integral_value())


def parse_filters(params: Mapping[str, str]) -> RiskFilters:
    """Read the filters of the register from the query string; an invalid value is ignored."""
    severities = tuple(item for item in (params.get("severidade") or "").split(",") if item)
    review = params.get("revisao", "")
    situation = params.get("situacao", SITUATION_ACTIVE)
    probability, impact = parse_level(params.get("p")), parse_level(params.get("i"))
    cell = CELL_LABEL.fullmatch((params.get("celula") or "").strip())
    if cell is not None:
        probability, impact = int(cell[1]), int(cell[2])
    return RiskFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH],
        nature=params.get("natureza", "") if params.get("natureza") in NATURES else "",
        category=(params.get("categoria") or "").strip(),
        severities=severities,
        situation=situation
        if situation in (*SITUATIONS, SITUATION_ACTIVE, SITUATION_ALL)
        else SITUATION_ACTIVE,
        strategy=(params.get("estrategia") or "").strip(),
        owner_id=parse_id(params.get("dono")),
        review=review if review in REVIEW_FILTERS else "",
        identified_from=parse_date(params.get("de")),
        identified_until=parse_date(params.get("ate")),
        include_closed=params.get("encerrados") == "1",
        include_deleted=params.get("excluidos") == "1",
        probability=probability,
        impact=impact,
        assessment=INHERENT if params.get("aval") == INHERENT else RESIDUAL,
        page=parse_id(params.get("pagina")) or 1,
    )


# ── Plano de resposta, revisão, encerramento e reabertura (ISSUE-065) ─────────────────────────

PLAN_STRATEGIES: Mapping[str, tuple[str, ...]] = {
    THREAT: ("Mitigar", "Transferir", "Evitar", "Aceitar"),
    OPPORTUNITY: ("Explorar", "Melhorar", "Compartilhar", "Aceitar"),
}
INSTRUMENTS = ("Seguro", "Cláusula contratual", "Subcontratação", "Hedge financeiro")
NEW_CHANGE = "nova"
PLAN_MIN_TEXT = 20
PLAN_AVOID_MIN = 80
PLAN_ACCEPT_MIN = 30
MAX_PLAN = 1000
MIN_APPROVAL_COMMENT = 10
MAX_APPROVAL_COMMENT = 500
APPROVAL_DECISIONS = ("Aprovado", "Devolvido")
APPROVAL_PENDING = "Pendente"
APPROVAL_APPROVED = "Aprovado"
APPROVAL_RETURNED = "Devolvido"
APPROVAL_NOT_REQUIRED = "Não exigida"
CLOSING_REASONS = ("Não se materializou", "Materializado", "Superado", "Transferido", "Duplicado")
MATERIALIZED = "Materializado"
DUPLICATED = "Duplicado"
MIN_REAL_DAYS = 0
MIN_LESSON = 20
MAX_LESSON = 1000
MIN_REOPEN = 10
MAX_REOPEN = 500
MIN_REVIEW_COMMENT = 10
MAX_REVIEW_COMMENT = 1000
MIN_ACTION_SUBJECT = 5
MAX_ACTION_SUBJECT = 255
MAX_ACTION_DESCRIPTION = 500
APURACOES = (
    "Sem mudança",
    "Risco reduzido",
    "Risco agravado",
    "Risco materializado",
    "Risco superado",
)
COMPARABLE_APURACOES = ("Sem mudança", "Risco reduzido", "Risco agravado")

CHOOSE_STRATEGY = "Escolha a estratégia."
PLAN_REQUIRED = "Descreva o plano de resposta."
PLAN_AVOID_SHORT = (
    "Estratégia Evitar: descreva a mudança de escopo ou de solução (mínimo de 80 caracteres)."
)
PLAN_ACCEPT_SHORT = "Estratégia Aceitar: justifique a aceitação no plano (mínimo de 30 caracteres)."
PLAN_DETAIL = "Detalhe o plano (mínimo de 20 caracteres)."
INSTRUMENT_REQUIRED = "Indique o instrumento da transferência."
SM_REQUIRED = "Evitar exige registro da mudança de escopo ou de solução (SM)."
SM_NOT_FOUND = "SM não encontrada no projeto."
CHOOSE_TARGET = "Escolha a severidade-alvo."
TARGET_ABOVE = "A severidade-alvo não pode ser maior que a inerente ({band})."
TARGET_DATE_REQUIRED = "Informe o prazo para atingir o alvo."
TARGET_DATE_FUTURE = "O prazo para o alvo deve ser uma data futura."
CHOOSE_PLAN_RESPONSIBLE = "Escolha o responsável pelo plano."
PLAN_NEEDS_ASSESSMENT = "Avalie o risco (inerente) antes de definir o plano de resposta."
ACTION_REQUIRED = (
    "Risco {band} exige pelo menos uma ação vinculada. Registre a primeira em Nova ação."
)
NO_PENDING_APPROVAL = "Não há plano aguardando aprovação."
CHOOSE_DECISION = "Escolha a decisão."
RETURN_COMMENT_REQUIRED = "Explique o que precisa ser revisto (mínimo de 10 caracteres)."
REVIEW_NEEDS_ASSESSMENT = "Avalie o risco antes de registrar a primeira revisão."
REVIEW_DATE_REQUIRED = "Informe a data da revisão."
REVIEW_DATE_FUTURE = "A data da revisão não pode ser futura."
REVIEW_DATE_BEFORE_LAST = "A data não pode ser anterior à última revisão ({date})."
CHOOSE_ASSESSED_SITUATION = "Escolha a situação apurada."
TRIGGER_REQUIRED = "Informe se o gatilho ocorreu."
NEXT_REVIEW_REQUIRED = "Informe a próxima revisão."
NEXT_REVIEW_AFTER = "A próxima revisão deve ser posterior à data desta revisão."
NEXT_REVIEW_LIMIT = (
    "Pela cadência da faixa {band} ({days} dias), a próxima revisão deve ser até {date}. "
    "Pode antecipar, nunca postergar."
)
ASSESSED_MISMATCH = "Score de {previous} para {score}: a situação apurada deve ser “{expected}”."
CHOOSE_CLOSING_REASON = "Escolha o motivo do encerramento."
CLOSING_DATE_REQUIRED = "Informe a data do encerramento."
CLOSING_DATE_FUTURE = "A data do encerramento não pode ser futura."
CLOSING_DATE_BEFORE = "A data não pode ser anterior à identificação ({date})."
CHOOSE_DUPLICATE = "Escolha o risco original (mesmo projeto)."
REAL_TERM_INVALID = "Informe o impacto real em prazo (zero ou mais)."
REAL_COST_INVALID = "Informe o impacto real em custo (zero ou mais)."
LESSON_REQUIRED = "Lição aprendida é obrigatória."
LESSON_SHORT = "Lição aprendida: mínimo de 20 caracteres."
LESSON_LONG = "Lição aprendida: máximo de 1000 caracteres."
REOPEN_JUSTIFICATION_REQUIRED = "Justifique a reabertura (mínimo de 10 caracteres)."
REOPEN_JUSTIFICATION_LONG = "Justificativa: máximo de 500 caracteres."
ACTION_SUBJECT_SHORT = "Assunto: mínimo de 5 caracteres."
ACTION_SUBJECT_LONG = "Assunto: máximo de 255 caracteres."
CHOOSE_REQUESTER = "Escolha o solicitante."
CHOOSE_RESPONSIBLE = "Escolha o responsável."
ACTION_DESCRIPTION_LONG = "Descrição: máximo de 500 caracteres."
PLANNED_DATE_REQUIRED = "Informe a data prevista."
PLANNED_DATE_PAST = "A data prevista não pode ser anterior à data de referência."


@dataclass(frozen=True)
class PlanInput:
    """What the response plan form sends: the strategy, the text and the target."""

    strategy: str
    plan: str
    instrument: str = ""
    change_code: str = ""
    target_severity: str = ""
    target_date: date | None = None
    response_cost_cents: int | None = None
    plan_responsible_id: int | None = None
    require_approval: bool = False
    version: int | str | None = None


@dataclass(frozen=True)
class PlanRules:
    """What the plan check reads from the risk and the parameters."""

    nature: str
    inherent_band: calculations.Band
    scale: calculations.Scale
    reference_date: date
    current_target: date | None


@dataclass(frozen=True)
class ApprovalInput:
    """What the plan approval form sends: the decision and the comment."""

    decision: str
    comment: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class ReviewInput:
    """What the periodic review form sends: the date, the apurada, P and I, and the next review."""

    reviewed_on: date | None
    assessed_situation: str
    probability: int | None
    impact: int | None
    comment: str
    trigger: bool
    next_review: date | None
    notify: bool = False
    version: int | str | None = None


@dataclass(frozen=True)
class ReviewRules:
    """What the review check reads from the current assessment and the parameters."""

    reference_date: date
    last_review: date | None
    current_score: int
    current_band: calculations.Band
    cadence_days: int


@dataclass(frozen=True)
class ClosingInput:
    """What the closing form sends: the reason, the real impact, the generated records."""

    reason: str
    closed_on: date | None
    duplicated_code: str = ""
    real_schedule_days: int | None = None
    real_cost_cents: int | None = None
    generate_action: bool = False
    action_subject: str = ""
    action_responsible_id: int | None = None
    action_planned_date: date | None = None
    open_change: bool = False
    lesson: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class ClosingRules:
    """What the closing check reads from the risk and its actions."""

    reference_date: date
    identified_on: date
    open_items: tuple[str, ...]
    is_opportunity: bool


@dataclass(frozen=True)
class ReopenInput:
    """What the reopening form sends: the justification."""

    justification: str
    version: int | str | None = None


@dataclass(frozen=True)
class ActionInput:
    """What the action form of the risk sends: the fields of the Central de Ações."""

    subject: str
    description: str = ""
    requester_id: int | None = None
    responsible_id: int | None = None
    planned_date: date | None = None
    contributes_probability: bool = False
    contributes_impact: bool = False


def plan_problems(data: PlanInput, rules: PlanRules) -> dict[str, str]:
    """One message per field of the response plan that does not hold up."""
    problems: dict[str, str] = {}
    if data.strategy not in PLAN_STRATEGIES.get(rules.nature, ()):
        problems["estrategia"] = CHOOSE_STRATEGY
    plan_problem = _plan_text_problem(data)
    if plan_problem:
        problems["plano"] = plan_problem
    if data.strategy == "Transferir" and data.instrument not in INSTRUMENTS:
        problems["instrumento"] = INSTRUMENT_REQUIRED
    if data.strategy == "Evitar" and not (data.change_code or "").strip():
        problems["smRef"] = SM_REQUIRED
    problems.update(_target_problems(data, rules))
    if data.response_cost_cents is not None and data.response_cost_cents < 0:
        problems["custoRespostaCentavos"] = INVALID_MONEY
    if not data.plan_responsible_id:
        problems["responsavelPlanoId"] = CHOOSE_PLAN_RESPONSIBLE
    return problems


def _plan_text_problem(data: PlanInput) -> str | None:
    text = (data.plan or "").strip()
    if not text:
        return PLAN_REQUIRED
    if len(text) > MAX_PLAN:
        return TEXT_TOO_LONG.format(label="Plano de resposta", maximum=MAX_PLAN)
    if data.strategy == "Evitar" and len(text) < PLAN_AVOID_MIN:
        return PLAN_AVOID_SHORT
    if data.strategy == "Aceitar" and len(text) < PLAN_ACCEPT_MIN:
        return PLAN_ACCEPT_SHORT
    if len(text) < PLAN_MIN_TEXT:
        return PLAN_DETAIL
    return None


def _target_problems(data: PlanInput, rules: PlanRules) -> dict[str, str]:
    problems: dict[str, str] = {}
    if calculations.find_band(rules.scale, data.target_severity) is None:
        problems["severidadeAlvo"] = CHOOSE_TARGET
    elif calculations.is_target_above(
        rules.nature, rules.inherent_band.id, data.target_severity, rules.scale
    ):
        problems["severidadeAlvo"] = TARGET_ABOVE.format(band=rules.inherent_band.name)
    if data.target_date is None:
        problems["prazoAlvo"] = TARGET_DATE_REQUIRED
    elif data.target_date <= rules.reference_date and data.target_date != rules.current_target:
        problems["prazoAlvo"] = TARGET_DATE_FUTURE
    return problems


def approval_problems(data: ApprovalInput) -> dict[str, str]:
    """One message per field of the approval decision that does not hold up."""
    if data.decision not in APPROVAL_DECISIONS:
        return {"decisao": CHOOSE_DECISION}
    if (
        data.decision == APPROVAL_RETURNED
        and len((data.comment or "").strip()) < MIN_APPROVAL_COMMENT
    ):
        return {"comentario": RETURN_COMMENT_REQUIRED}
    if len((data.comment or "").strip()) > MAX_APPROVAL_COMMENT:
        return {
            "comentario": TEXT_TOO_LONG.format(label="Comentário", maximum=MAX_APPROVAL_COMMENT)
        }
    return {}


def review_problems(data: ReviewInput, rules: ReviewRules) -> dict[str, str]:
    """One message per field of the periodic review that does not hold up."""
    problems: dict[str, str] = {}
    problems.update(_review_date_problems(data.reviewed_on, rules))
    if data.assessed_situation not in APURACOES:
        problems["situacaoApurada"] = CHOOSE_ASSESSED_SITUATION
    if data.probability is None or not MIN_LEVEL <= data.probability <= MAX_LEVEL:
        problems["p"] = CHOOSE_PROBABILITY
    if data.impact is None or not MIN_LEVEL <= data.impact <= MAX_LEVEL:
        problems["i"] = CHOOSE_IMPACT
    comment = text_problem(
        data.comment, "Comentário", minimum=MIN_REVIEW_COMMENT, maximum=MAX_REVIEW_COMMENT
    )
    if comment:
        problems["comentario"] = comment
    problems.update(_next_review_problems(data, rules))
    mismatch = _assessed_mismatch(data, rules)
    if mismatch:
        problems["situacaoApurada"] = mismatch
    return problems


def _review_date_problems(reviewed_on: date | None, rules: ReviewRules) -> dict[str, str]:
    if reviewed_on is None:
        return {"data": REVIEW_DATE_REQUIRED}
    if reviewed_on > rules.reference_date:
        return {"data": REVIEW_DATE_FUTURE}
    if rules.last_review is not None and reviewed_on < rules.last_review:
        return {"data": REVIEW_DATE_BEFORE_LAST.format(date=_br(rules.last_review))}
    return {}


def _next_review_problems(data: ReviewInput, rules: ReviewRules) -> dict[str, str]:
    if data.next_review is None:
        return {"proximaRevisao": NEXT_REVIEW_REQUIRED}
    if data.reviewed_on is None:
        return {}
    if data.next_review <= data.reviewed_on:
        return {"proximaRevisao": NEXT_REVIEW_AFTER}
    limit = calculations.next_review_limit(data.reviewed_on, rules.cadence_days)
    if data.next_review > limit:
        return {
            "proximaRevisao": NEXT_REVIEW_LIMIT.format(
                band=rules.current_band.name, days=rules.cadence_days, date=_br(limit)
            )
        }
    return {}


def _assessed_mismatch(data: ReviewInput, rules: ReviewRules) -> str | None:
    if data.assessed_situation not in COMPARABLE_APURACOES:
        return None
    if data.probability is None or data.impact is None:
        return None
    score = data.probability * data.impact
    expected = calculations.assessed_situation(rules.current_score, score)
    if expected == data.assessed_situation:
        return None
    return ASSESSED_MISMATCH.format(previous=rules.current_score, score=score, expected=expected)


def closing_problems(data: ClosingInput, rules: ClosingRules) -> dict[str, str]:
    """One message per field of the closing that does not hold up."""
    problems: dict[str, str] = {}
    if data.reason not in CLOSING_REASONS:
        problems["motivo"] = CHOOSE_CLOSING_REASON
    problems.update(_closing_date_problems(data.closed_on, rules))
    if data.reason != MATERIALIZED and rules.open_items:
        problems["acoes"] = open_actions_message(rules.open_items)
    if data.reason == MATERIALIZED:
        problems.update(_real_impact_problems(data))
    lesson_problem = _lesson_problem(data.lesson)
    if lesson_problem:
        problems["licao"] = lesson_problem
    return problems


def _lesson_problem(lesson: str) -> str | None:
    text = (lesson or "").strip()
    if not text:
        return LESSON_REQUIRED
    if len(text) < MIN_LESSON:
        return LESSON_SHORT
    if len(text) > MAX_LESSON:
        return LESSON_LONG
    return None


def _closing_date_problems(closed_on: date | None, rules: ClosingRules) -> dict[str, str]:
    if closed_on is None:
        return {"data": CLOSING_DATE_REQUIRED}
    if closed_on > rules.reference_date:
        return {"data": CLOSING_DATE_FUTURE}
    if closed_on < rules.identified_on:
        return {"data": CLOSING_DATE_BEFORE.format(date=_br(rules.identified_on))}
    return {}


def _real_impact_problems(data: ClosingInput) -> dict[str, str]:
    problems: dict[str, str] = {}
    if data.real_schedule_days is None or data.real_schedule_days < MIN_REAL_DAYS:
        problems["impactoRealPrazoDias"] = REAL_TERM_INVALID
    if data.real_cost_cents is None or data.real_cost_cents < MIN_REAL_DAYS:
        problems["impactoRealCustoCentavos"] = REAL_COST_INVALID
    return problems


def open_actions_message(items: Sequence[str]) -> str:
    """The refusal of a closing with open actions, naming the items as the prototype did."""
    count = len(items)
    noun = "ação" if count == 1 else "ações"
    linked = "vinculada" if count == 1 else "vinculadas"
    listed = ", ".join(f"item {item}" for item in items)
    return (
        f"Existe{'m' if count > 1 else ''} {count} {noun} em aberto {linked} a este risco "
        f"({listed}). Conclua ou cancele antes de encerrar, salvo se o motivo for Materializado."
    )


def reopen_problems(data: ReopenInput) -> dict[str, str]:
    """One message for the reopening justification that does not hold up."""
    text = (data.justification or "").strip()
    if len(text) < MIN_REOPEN:
        return {"justificativa": REOPEN_JUSTIFICATION_REQUIRED}
    if len(text) > MAX_REOPEN:
        return {"justificativa": REOPEN_JUSTIFICATION_LONG}
    return {}


def action_problems(data: ActionInput, *, reference_date: date) -> dict[str, str]:
    """One message per field of the action of the risk that does not hold up."""
    problems: dict[str, str] = {}
    subject = (data.subject or "").strip()
    if len(subject) < MIN_ACTION_SUBJECT:
        problems["assunto"] = ACTION_SUBJECT_SHORT
    elif len(subject) > MAX_ACTION_SUBJECT:
        problems["assunto"] = ACTION_SUBJECT_LONG
    if len((data.description or "").strip()) > MAX_ACTION_DESCRIPTION:
        problems["descricao"] = ACTION_DESCRIPTION_LONG
    if not data.requester_id:
        problems["solicitanteId"] = CHOOSE_REQUESTER
    if not data.responsible_id:
        problems["responsavelId"] = CHOOSE_RESPONSIBLE
    if data.planned_date is None:
        problems["prevista"] = PLANNED_DATE_REQUIRED
    elif data.planned_date < reference_date:
        problems["prevista"] = PLANNED_DATE_PAST
    return problems


def _br(value: date) -> str:
    return value.strftime("%d/%m/%Y")
