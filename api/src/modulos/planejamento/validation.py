"""Input validation for the Planning module.

Relato do período (ISSUE-044): the limits of the content of a report, one function per rule,
with the same messages and the same boundaries as the prototype (``salvarRelato``). Each
function answers the messages by the name of the field of the form, so the screen shows the
message next to the input (422 per field); an empty answer means the boundary holds.


The 6WLA forms (ISSUE-045) follow the fields of the prototype and are checked
here, on the server: the screen only helps. Every function reads the raw text
of the form and returns typed data, or raises ``InvalidDataError`` with one
message per field (the form comes back filled, with the message under the
field).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from src.core.errors import InvalidDataError

# The two kinds of report, as the register keeps them.
WEEKLY = "Semanal"


MONTHLY = "Mensal"


KINDS = (WEEKLY, MONTHLY)


# The nature of the risk tied to an attention point: the planning reading, not the 05 register.
THREAT = "Ameaça"


OPPORTUNITY = "Oportunidade"


NATURES = (THREAT, OPPORTUNITY)


# The limits of the content (HU-046).
MAX_LINES = 20


MAX_LINE_CHARACTERS = 300


MAX_POINTS = 12


MAX_POINT_CHARACTERS = 400


MIN_POINT_CHARACTERS = 10


# The names of the fields of the form; the error messages are keyed by them.
FIELD_KIND = "tipo"


FIELD_PERIOD = "periodo"


FIELD_ACTIVITIES = "atividades_periodo"


FIELD_NEXT_ACTIVITIES = "atividades_proximo"


FIELD_POINTS = "pontos"


KIND_MESSAGE = "Escolha o tipo do relato (semanal ou mensal)."


PERIOD_MESSAGE = "Escolha o período do relato."


ACTIVITY_REQUIRED_MESSAGE = "Informe ao menos uma atividade (uma por linha)."


LINE_TOO_LONG_MESSAGE = f"Cada linha pode ter até {MAX_LINE_CHARACTERS} caracteres."


TOO_MANY_POINTS_MESSAGE = f"No máximo {MAX_POINTS} pontos de atenção por relato."


POINT_DESCRIPTION_SHORT_MESSAGE = (
    f"Descreva o ponto de atenção (mínimo de {MIN_POINT_CHARACTERS} caracteres)."
)


POINT_RISK_SHORT_MESSAGE = (
    f"Descreva o risco atrelado (mínimo de {MIN_POINT_CHARACTERS} caracteres)."
)


POINT_TOO_LONG_MESSAGE = f"Até {MAX_POINT_CHARACTERS} caracteres."


POINT_NATURE_MESSAGE = "Escolha ameaça ou oportunidade."


_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class PointInput:
    """What a person typed for one attention point: the point, its nature and the risk."""

    description: str = ""
    nature: str = ""
    risk: str = ""

    @property
    def is_blank(self) -> bool:
        """Whether nothing was typed: a row left empty is not a point."""
        return not (self.description or self.nature or self.risk)


def point_field(index: int, name: str) -> str:
    """The name of a field of one point in the form: ``ponto_0_descricao``."""
    return f"ponto_{index}_{name}"


def clean_lines(raw: str | Sequence[str] | None) -> list[str]:
    """The lines of a text, each with its spaces collapsed, the empty ones left out (one per line)."""
    if raw is None:
        return []
    lines = raw.splitlines() if isinstance(raw, str) else list(raw)
    cleaned = (_WHITESPACE.sub(" ", str(line)).strip() for line in lines)
    return [line for line in cleaned if line]


def clean_point(point: PointInput) -> PointInput:
    """The point with the outer spaces cut, as the prototype saved it."""
    return PointInput(
        description=point.description.strip(),
        nature=point.nature.strip(),
        risk=point.risk.strip(),
    )


def non_blank_points(points: Sequence[PointInput]) -> list[PointInput]:
    """The points a person really filled in, trimmed; the rows left empty are dropped."""
    cleaned = (clean_point(point) for point in points)
    return [point for point in cleaned if not point.is_blank]


def validate_kind(kind: str) -> dict[str, str]:
    """The message for the type field when it is neither weekly nor monthly."""
    return {} if kind in KINDS else {FIELD_KIND: KIND_MESSAGE}


def activity_lines_error(label: str, lines: Sequence[str]) -> str | None:
    """The message for a list of activities: at least one, up to 20 lines of 300 characters."""
    if not lines:
        return ACTIVITY_REQUIRED_MESSAGE
    if len(lines) > MAX_LINES:
        return f"{label}: no máximo {MAX_LINES} linhas."
    if any(len(line) > MAX_LINE_CHARACTERS for line in lines):
        return LINE_TOO_LONG_MESSAGE
    return None


def validate_activities(
    activities: Sequence[str], next_activities: Sequence[str]
) -> dict[str, str]:
    """Both lists of activities (already cleaned) against the limits of the lines."""
    errors: dict[str, str] = {}
    checks = (
        (FIELD_ACTIVITIES, "Atividades do período", activities),
        (FIELD_NEXT_ACTIVITIES, "Atividades do próximo período", next_activities),
    )
    for field, label, lines in checks:
        message = activity_lines_error(label, lines)
        if message:
            errors[field] = message
    return errors


def text_error(text: str, *, short_message: str) -> str | None:
    """The message for a point text: at least 10 and at most 400 characters."""
    if len(text) < MIN_POINT_CHARACTERS:
        return short_message
    if len(text) > MAX_POINT_CHARACTERS:
        return POINT_TOO_LONG_MESSAGE
    return None


def validate_point(index: int, point: PointInput) -> dict[str, str]:
    """The errors of one trimmed attention point, keyed by its fields in the form."""
    checks = (
        (
            point_field(index, "descricao"),
            text_error(point.description, short_message=POINT_DESCRIPTION_SHORT_MESSAGE),
        ),
        (
            point_field(index, "natureza"),
            None if point.nature in NATURES else POINT_NATURE_MESSAGE,
        ),
        (
            point_field(index, "risco"),
            text_error(point.risk, short_message=POINT_RISK_SHORT_MESSAGE),
        ),
    )
    return {field: message for field, message in checks if message}


def validate_points(points: Sequence[PointInput]) -> dict[str, str]:
    """The attention points (trimmed, blank rows already dropped) against their limits."""
    errors: dict[str, str] = {}
    if len(points) > MAX_POINTS:
        errors[FIELD_POINTS] = TOO_MANY_POINTS_MESSAGE
    for index, point in enumerate(points):
        errors.update(validate_point(index, point))
    return errors


# The restriction types of the prototype, in the order its form lists them.
CONSTRAINT_KINDS = (
    "Projeto",
    "Material",
    "Mão de obra",
    "Equipamento",
    "Liberação de área",
    "Segurança",
    "Documentação",
    "Predecessora",
)


ACTIVITY_MAX_LENGTH = 120


AREA_MAX_LENGTH = 120


DESCRIPTION_MAX_LENGTH = 200


COMMENT_MAX_LENGTH = 200


# An id never has more digits than this: the cap keeps absurd input away from ``int`` and the database.
MAX_ID_DIGITS = 18


REQUIRED_MESSAGE = "Informe {label}."


TOO_LONG_MESSAGE = "{label} aceita no máximo {limit} caracteres."


UNKNOWN_CHOICE_MESSAGE = "Escolha {label} da lista."


INVALID_DATE_MESSAGE = "Informe {label} como uma data válida."


WEEKS_MESSAGE = "Marque ao menos uma das seis semanas."


@dataclass(frozen=True)
class RegisterChoices:
    """What the register offers the form: the ids and names a field may carry."""

    company_ids: frozenset[int]
    person_ids: frozenset[int]
    disciplines: frozenset[str]


@dataclass(frozen=True)
class ActivityForm:
    """What the activity form sent: the text fields and the indexes of the marked weeks."""

    fields: Mapping[str, str]
    weeks: Sequence[str]


@dataclass(frozen=True)
class ActivityData:
    """A valid activity of the 6WLA, ready for the facade."""

    activity: str
    area: str
    discipline: str
    company_id: int
    owner_id: int
    planned: tuple[bool, ...]


@dataclass(frozen=True)
class ConstraintData:
    """A valid restriction: type, owner of the removal, description and the date it is needed."""

    kind: str
    owner_id: int
    description: str
    due_date: date


@dataclass(frozen=True)
class RemovalData:
    """A valid removal: the date and, optionally, how it was removed."""

    removal_date: date
    comment: str | None


def parse_id(text: str | None) -> int | None:
    """The id a form or an address carried, or ``None`` when it is not a plain number."""
    value = (text or "").strip()
    if value.isascii() and value.isdigit() and len(value) <= MAX_ID_DIGITS:
        return int(value)
    return None


def _text(raw: Mapping[str, str], field: str) -> str:
    return (raw.get(field) or "").strip()


def _required_text(
    raw: Mapping[str, str], field: str, *, label: str, limit: int, errors: dict[str, str]
) -> str:
    value = _text(raw, field)
    if not value:
        errors[field] = REQUIRED_MESSAGE.format(label=label)
    elif len(value) > limit:
        errors[field] = TOO_LONG_MESSAGE.format(label=label.capitalize(), limit=limit)
    return value


def _choice_id(
    raw: Mapping[str, str],
    field: str,
    *,
    label: str,
    allowed: frozenset[int],
    errors: dict[str, str],
) -> int:
    text = _text(raw, field)
    if not text:
        errors[field] = REQUIRED_MESSAGE.format(label=label)
        return 0
    found = parse_id(text)
    if found is None or found not in allowed:
        errors[field] = UNKNOWN_CHOICE_MESSAGE.format(label=label)
        return 0
    return found


def _choice_text(
    raw: Mapping[str, str],
    field: str,
    *,
    label: str,
    allowed: frozenset[str],
    errors: dict[str, str],
) -> str:
    value = _text(raw, field)
    if not value:
        errors[field] = REQUIRED_MESSAGE.format(label=label)
    elif value not in allowed:
        errors[field] = UNKNOWN_CHOICE_MESSAGE.format(label=label)
    return value


def _required_date(
    raw: Mapping[str, str], field: str, *, label: str, errors: dict[str, str]
) -> date:
    text = _text(raw, field)
    if not text:
        errors[field] = REQUIRED_MESSAGE.format(label=label)
        return date.min
    try:
        return date.fromisoformat(text)
    except ValueError:
        errors[field] = INVALID_DATE_MESSAGE.format(label=label)
        return date.min


def planned_weeks(raw_weeks: Sequence[str]) -> tuple[bool, ...]:
    """The six marks from the indexes the form sent; anything but ``0`` to ``5`` is ignored."""
    # Imported here: ``calculations`` reads the kinds and natures of this module at import time.
    from src.modulos.planejamento.calculations import LOOKAHEAD_WEEKS

    marked = {found for item in raw_weeks if (found := parse_id(item)) is not None}
    return tuple(index in marked for index in range(LOOKAHEAD_WEEKS))


def parse_activity(form: ActivityForm, choices: RegisterChoices) -> ActivityData:
    """The activity of the form, or ``InvalidDataError`` with the message of each wrong field."""
    raw = form.fields
    errors: dict[str, str] = {}
    activity = _required_text(
        raw, "atividade", label="a atividade", limit=ACTIVITY_MAX_LENGTH, errors=errors
    )
    area = _required_text(
        raw, "area", label="a área ou o local", limit=AREA_MAX_LENGTH, errors=errors
    )
    discipline = _choice_text(
        raw, "disciplina", label="a disciplina", allowed=choices.disciplines, errors=errors
    )
    company_id = _choice_id(
        raw, "empresa", label="a empresa", allowed=choices.company_ids, errors=errors
    )
    owner_id = _choice_id(
        raw, "responsavel", label="o responsável", allowed=choices.person_ids, errors=errors
    )
    planned = planned_weeks(form.weeks)
    if not any(planned):
        errors["semanas"] = WEEKS_MESSAGE
    if errors:
        raise InvalidDataError(errors)
    return ActivityData(
        activity=activity,
        area=area,
        discipline=discipline,
        company_id=company_id,
        owner_id=owner_id,
        planned=planned,
    )


def parse_constraint(raw: Mapping[str, str], choices: RegisterChoices) -> ConstraintData:
    """The restriction of the form, or ``InvalidDataError`` with the message of each wrong field."""
    errors: dict[str, str] = {}
    kind = _choice_text(
        raw, "tipo", label="o tipo", allowed=frozenset(CONSTRAINT_KINDS), errors=errors
    )
    owner_id = _choice_id(
        raw,
        "responsavel",
        label="o responsável pela remoção",
        allowed=choices.person_ids,
        errors=errors,
    )
    description = _required_text(
        raw, "descricao", label="a descrição", limit=DESCRIPTION_MAX_LENGTH, errors=errors
    )
    due_date = _required_date(raw, "necessaria", label="a data necessária", errors=errors)
    if errors:
        raise InvalidDataError(errors)
    return ConstraintData(kind=kind, owner_id=owner_id, description=description, due_date=due_date)


def parse_removal(raw: Mapping[str, str]) -> RemovalData:
    """The removal of the form, or ``InvalidDataError`` with the message of each wrong field."""
    errors: dict[str, str] = {}
    removal_date = _required_date(raw, "remocao", label="a data de remoção", errors=errors)
    comment = _text(raw, "comentario")
    if len(comment) > COMMENT_MAX_LENGTH:
        errors["comentario"] = TOO_LONG_MESSAGE.format(
            label="O comentário", limit=COMMENT_MAX_LENGTH
        )
    if errors:
        raise InvalidDataError(errors)
    return RemovalData(removal_date=removal_date, comment=comment or None)
