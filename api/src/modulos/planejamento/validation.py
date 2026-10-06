"""Input validation for the Planning module.

The 6WLA forms (ISSUE-045) follow the fields of the prototype and are checked
here, on the server: the screen only helps. Every function reads the raw text
of the form and returns typed data, or raises ``InvalidDataError`` with one
message per field (the form comes back filled, with the message under the
field).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from src.core.errors import InvalidDataError
from src.modulos.planejamento.calculations import LOOKAHEAD_WEEKS

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
