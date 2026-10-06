"""Input validation of the lessons learned (ISSUE-027): the lesson, the validation and the reuse.

The rules are those of the prototype (``salvarLicao``, ``validarLicao`` and ``aplicarLicao``): a field
missing, a text too short or too long, a value outside its list or a date after the reference date is
422 with one message per field, so the form comes back filled with the message under the field.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from src.core.errors import InvalidDataError
from src.modulos.governanca import lessons_calculations as calc
from src.modulos.governanca import lessons_models as lm
from src.modulos.governanca import validation

type Form = Mapping[str, str | None]
type Messages = dict[str, str]

TITLE_LIMITS = (10, 150)
WHAT_HAPPENED_LIMITS = (20, 1000)
CAUSE_LIMITS = (10, 600)
RECOMMENDATION_LIMITS = (calc.RECOMMENDATION_MINIMUM, 1000)
RETURN_COMMENT_LIMITS = (10, 500)
VALIDATION_COMMENT_MAXIMUM = 500
HOW_LIMITS = (20, 600)

CHECKED_VALUE = validation.CHECKED_VALUE

FIELD_TITLE = "titulo"
FIELD_KIND = "tipo"
FIELD_PHASE = "fase"
FIELD_AREA = "area"
FIELD_DISCIPLINE = "disciplina"
FIELD_ORIGIN = "origem"
FIELD_ORIGIN_REF = "origem_ref"
FIELD_WHAT_HAPPENED = "aconteceu"
FIELD_CAUSE = "causa"
FIELD_TERM_DAYS = "impacto_prazo_dias"
FIELD_COST = "impacto_custo"
FIELD_RECOMMENDATION = "recomendacao"
FIELD_KEYWORDS = "palavras_chave"
FIELD_APPLICABILITY = "aplicabilidade"
FIELD_VERSION = "versao"
FIELD_CODE = "codigo"
FIELD_SEND = "enviar"
FIELD_RESULT = "resultado"
FIELD_COMMENT = "comentario"
FIELD_PROJECT = "projeto_id"
FIELD_DATE = "data"
FIELD_HOW = "como"
FIELD_GENERATE = "gerar"
FIELD_RESPONSIBLE = "responsavel_id"
FIELD_PLANNED = "prevista"

RESULT_VALIDATED = "Validada"
RESULT_PUBLISHED = "Publicada"
RESULT_RETURNED = "Devolvida"
VALIDATION_RESULTS = (RESULT_VALIDATED, RESULT_PUBLISHED, RESULT_RETURNED)

GENERATE_NOTHING = "nada"
GENERATE_ACTION = "acao"
GENERATE_RISK = "risco"
GENERATE_OPTIONS = (GENERATE_NOTHING, GENERATE_ACTION)
RISK_LATER_MESSAGE = "A criação de risco a partir da lição chega com o módulo de Riscos."

ORIGIN_REF_REQUIRED = "Informe o número do registro de origem (rastreabilidade)."
DATE_AFTER_REFERENCE = "A data não pode ser posterior a hoje."
PLANNED_BEFORE_REFERENCE = "A data prevista não pode ser anterior a hoje."


@dataclass(frozen=True)
class LessonInput:
    """A lesson that passed the rules of the form: what the facade writes."""

    title: str
    kind: str
    phase: str
    area: str
    discipline: str
    origin: str
    origin_ref: str | None
    what_happened: str
    cause: str
    term_days: int
    cost_cents: int
    recommendation: str
    keywords: tuple[str, ...]
    applicability: str


def validate_lesson(
    form: Form, *, discipline_names: frozenset[str], origins: tuple[str, ...]
) -> LessonInput:
    """The lesson of the form, or 422 with a message per field that breaks a rule."""
    messages: Messages = {}
    title = _text(form, FIELD_TITLE, "Título", TITLE_LIMITS, messages)
    kind = _choice(form, FIELD_KIND, lm.LESSON_TYPES, "Escolha o tipo.", messages)
    phase = _choice(form, FIELD_PHASE, lm.LESSON_PHASES, "Escolha a fase.", messages)
    area = _choice(form, FIELD_AREA, lm.LESSON_AREAS, "Escolha a área de conhecimento.", messages)
    discipline = (form.get(FIELD_DISCIPLINE) or "").strip()
    if discipline not in discipline_names:
        messages[FIELD_DISCIPLINE] = "Escolha a disciplina."
    origin = _choice(form, FIELD_ORIGIN, origins, "Escolha a origem.", messages)
    origin_ref = _origin_ref(form, origin, messages)
    what_happened = _text(
        form, FIELD_WHAT_HAPPENED, "O que aconteceu", WHAT_HAPPENED_LIMITS, messages
    )
    cause = _text(form, FIELD_CAUSE, "Causa", CAUSE_LIMITS, messages)
    recommendation = _text(
        form, FIELD_RECOMMENDATION, "Recomendação", RECOMMENDATION_LIMITS, messages
    )
    term_days = _term_days(form, messages)
    cost_cents = _cost(form, messages)
    keywords = _keywords(form, messages)
    applicability = _choice(
        form, FIELD_APPLICABILITY, lm.LESSON_APPLICABILITIES, "Escolha a aplicabilidade.", messages
    )
    if messages or term_days is None or cost_cents is None:
        raise InvalidDataError(messages)
    return LessonInput(
        title=title,
        kind=kind,
        phase=phase,
        area=area,
        discipline=discipline,
        origin=origin,
        origin_ref=origin_ref,
        what_happened=what_happened,
        cause=cause,
        term_days=term_days,
        cost_cents=cost_cents,
        recommendation=recommendation,
        keywords=tuple(keywords),
        applicability=applicability,
    )


@dataclass(frozen=True)
class ValidationInput:
    """The decision of the validator: the result, the applicability confirmed and the comment."""

    result: str
    applicability: str
    comment: str


def validate_decision(form: Form, *, current_applicability: str) -> ValidationInput:
    """The validation of the form: validate, validate and publish, or return with a comment (422)."""
    messages: Messages = {}
    result = _choice(
        form, FIELD_RESULT, VALIDATION_RESULTS, "Escolha o resultado da validação.", messages
    )
    comment = (form.get(FIELD_COMMENT) or "").strip()
    if result == RESULT_RETURNED:
        comment = _text(
            form, FIELD_COMMENT, "Comentário para o autor", RETURN_COMMENT_LIMITS, messages
        )
        applicability = current_applicability
    else:
        applicability = _choice(
            form,
            FIELD_APPLICABILITY,
            lm.LESSON_APPLICABILITIES,
            "Confirme a aplicabilidade.",
            messages,
        )
        if len(comment) > VALIDATION_COMMENT_MAXIMUM:
            messages[FIELD_COMMENT] = (
                f"Comentário: máximo de {VALIDATION_COMMENT_MAXIMUM} caracteres."
            )
    if messages:
        raise InvalidDataError(messages)
    return ValidationInput(result=result, applicability=applicability, comment=comment)


@dataclass(frozen=True)
class ApplicationInput:
    """A reuse that passed the rules: where, when, how, and what to generate in the Central."""

    project_id: int
    applied_on: date
    how: str
    generate_action: bool
    responsible_person_id: int | None
    planned_date: date | None


def validate_application(
    form: Form, *, reference_date: date, person_ids: frozenset[int]
) -> ApplicationInput:
    """The reuse of the form, or 422 with a message per field (the project's reach is checked later)."""
    messages: Messages = {}
    project_id = _integer(form, FIELD_PROJECT, "Escolha o projeto.", messages)
    applied_on = _date(form, FIELD_DATE, "Informe a data.", messages)
    if applied_on is not None and applied_on > reference_date:
        messages[FIELD_DATE] = DATE_AFTER_REFERENCE
    how = _text(form, FIELD_HOW, "Como a lição será aplicada", HOW_LIMITS, messages)
    generate = (form.get(FIELD_GENERATE) or GENERATE_NOTHING).strip()
    responsible, planned = None, None
    if generate == GENERATE_RISK:
        messages[FIELD_GENERATE] = RISK_LATER_MESSAGE
    elif generate not in GENERATE_OPTIONS:
        messages[FIELD_GENERATE] = "Escolha o que gerar."
    elif generate == GENERATE_ACTION:
        responsible = _integer(
            form, FIELD_RESPONSIBLE, "Escolha o responsável pela ação.", messages
        )
        if responsible is not None and responsible not in person_ids:
            messages[FIELD_RESPONSIBLE] = "Escolha o responsável pela ação."
        planned = _date(form, FIELD_PLANNED, "Informe a data prevista.", messages)
        if planned is not None and planned < reference_date:
            messages[FIELD_PLANNED] = PLANNED_BEFORE_REFERENCE
    if messages or project_id is None or applied_on is None:
        raise InvalidDataError(messages)
    return ApplicationInput(
        project_id=project_id,
        applied_on=applied_on,
        how=how,
        generate_action=generate == GENERATE_ACTION,
        responsible_person_id=responsible,
        planned_date=planned,
    )


@dataclass(frozen=True)
class DraftInput:
    """What another module hands over to open a draft lesson: the text it knows and the origin."""

    title: str
    kind: str
    phase: str
    area: str
    origin: str
    origin_ref: str | None
    what_happened: str
    cause: str
    recommendation: str
    discipline: str = ""
    term_days: int = 0
    cost_cents: int = 0
    keywords: tuple[str, ...] = ()
    applicability: str = lm.APPLICABILITY_PROJECT


def validate_draft(draft: DraftInput) -> None:
    """422 with a message per field when the draft of another module breaks a rule of the lesson."""
    messages: Messages = {}
    _limit(draft.title, "Título da lição", TITLE_LIMITS, FIELD_TITLE, messages)
    _limit(
        draft.recommendation, "Recomendação", RECOMMENDATION_LIMITS, FIELD_RECOMMENDATION, messages
    )
    _member(draft.kind, lm.LESSON_TYPES, "Escolha o tipo da lição.", FIELD_KIND, messages)
    _member(draft.phase, lm.LESSON_PHASES, "Escolha a fase.", FIELD_PHASE, messages)
    _member(draft.area, lm.LESSON_AREAS, "Escolha a área de conhecimento.", FIELD_AREA, messages)
    _member(draft.origin, lm.LESSON_ORIGINS, "Escolha a origem.", FIELD_ORIGIN, messages)
    if calc.is_module_origin(draft.origin) and not (draft.origin_ref or "").strip():
        messages[FIELD_ORIGIN_REF] = ORIGIN_REF_REQUIRED
    if messages:
        raise InvalidDataError(messages)


def money_input(cents: int) -> str:
    """Cents as the form writes reais: ``12345`` is ``123,45``."""
    return f"{cents // 100},{cents % 100:02d}"


def _origin_ref(form: Form, origin: str, messages: Messages) -> str | None:
    if not calc.is_module_origin(origin):
        return None
    reference = (form.get(FIELD_ORIGIN_REF) or "").strip().upper()
    if not reference:
        messages[FIELD_ORIGIN_REF] = ORIGIN_REF_REQUIRED
    return reference or None


def _term_days(form: Form, messages: Messages) -> int | None:
    raw = (form.get(FIELD_TERM_DAYS) or "").strip()
    if not raw.isdigit():
        messages[FIELD_TERM_DAYS] = "Informe o impacto em prazo em dias (zero ou mais)."
        return None
    return int(raw)


def _cost(form: Form, messages: Messages) -> int | None:
    cents = validation.parse_money((form.get(FIELD_COST) or "").strip())
    if cents is None or cents < 0:
        messages[FIELD_COST] = "Informe o impacto em custo (zero ou mais)."
        return None
    return cents


def _keywords(form: Form, messages: Messages) -> list[str]:
    words = calc.parse_keywords(form.get(FIELD_KEYWORDS))
    if not words:
        messages[FIELD_KEYWORDS] = "Informe ao menos uma palavra-chave (separe por vírgula)."
    elif len(words) > calc.KEYWORDS_MAXIMUM:
        messages[FIELD_KEYWORDS] = f"Use no máximo {calc.KEYWORDS_MAXIMUM} palavras-chave."
    return words


def _text(form: Form, field: str, label: str, limits: tuple[int, int], messages: Messages) -> str:
    text = (form.get(field) or "").strip()
    _limit(text, label, limits, field, messages)
    return text


def _limit(text: str, label: str, limits: tuple[int, int], field: str, messages: Messages) -> None:
    minimum, maximum = limits
    stripped = text.strip()
    if not stripped:
        messages[field] = f"{label} é obrigatório."
    elif len(stripped) < minimum:
        messages[field] = f"{label}: mínimo de {minimum} caracteres."
    elif len(stripped) > maximum:
        messages[field] = f"{label}: máximo de {maximum} caracteres."


def _choice(
    form: Form, field: str, options: tuple[str, ...], message: str, messages: Messages
) -> str:
    value = (form.get(field) or "").strip()
    _member(value, options, message, field, messages)
    return value


def _member(
    value: str, options: tuple[str, ...], message: str, field: str, messages: Messages
) -> None:
    if value not in options:
        messages[field] = message


def _integer(form: Form, field: str, message: str, messages: Messages) -> int | None:
    raw = (form.get(field) or "").strip()
    if not raw.isdigit():
        messages[field] = message
        return None
    return int(raw)


def _date(form: Form, field: str, missing: str, messages: Messages) -> date | None:
    raw = (form.get(field) or "").strip()
    if not raw:
        messages[field] = missing
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        messages[field] = validation.INVALID_DATE_MESSAGE
        return None
