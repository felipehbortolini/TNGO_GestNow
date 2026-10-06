"""Input validation of the Risk management module (ISSUE-064).

The shapes the facade receives (identification, assessment, deletion, filters) and the checks of
what a person types. The checks are pure and return one message per field, in a dict that is
empty when everything holds up; the facade turns it into one ``InvalidDataError`` (422), so the
rule holds for the route and for any module that calls the facade.
"""

from __future__ import annotations

from collections.abc import Mapping
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
        probability=parse_level(params.get("p")),
        impact=parse_level(params.get("i")),
        assessment=INHERENT if params.get("aval") == INHERENT else RESIDUAL,
        page=parse_id(params.get("pagina")) or 1,
    )
