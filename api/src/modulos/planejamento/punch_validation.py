"""Validation of the Punch list (ISSUE-049): one function per rule, messages by form field.

The screen only helps: every rule is checked here, on the server. A function answers the
messages by the name of the field of the form (422 per field); an empty answer means it holds.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from src.core.errors import InvalidDataError
from src.modulos.planejamento import punch_calculations as calc

REQUIRED = "Campo obrigatório."
INVALID_CHOICE = "Escolha uma das opções da lista."
INVALID_DATE = "Informe uma data válida."
MAX_DESCRIPTION = 300
MAX_COMMENT = 300
MIN_JUSTIFICATION = 10
TOO_LONG = "Use no máximo {limit} caracteres."
JUSTIFICATION_REQUIRED = "Detalhe a justificativa (mínimo de 10 caracteres)."
REJECTION_REASON_REQUIRED = "Explique o motivo da reprovação."
TREATMENT_REQUIRED = "Descreva o que foi feito."
UNKNOWN_RESULT = "Escolha Aprovado ou Reprovado."

APPROVED = "aprovado"
REJECTED = "reprovado"
RESULTS = (APPROVED, REJECTED)


@dataclass(frozen=True)
class ItemInput:
    """The typed fields of an item as the form (or one line of the import) carries them."""

    system_id: int | None = None
    subsystem: str = ""
    tag: str = ""
    discipline: str = ""
    category: str = ""
    milestone: str = ""
    origin: str = ""
    description: str = ""
    company_id: int | None = None
    responsible_id: int | None = None
    identified_by_id: int | None = None
    due_date: date | None = None


@dataclass(frozen=True)
class RegisterChoices:
    """What the register offers the form: the systems of the project, companies and people."""

    system_ids: frozenset[int]
    company_ids: frozenset[int]
    person_ids: frozenset[int]


def whole_number(raw: str | None) -> int | None:
    """The text as an integer, or ``None`` when it is empty or not a whole number."""
    try:
        return int((raw or "").strip())
    except ValueError:
        return None


def date_of(raw: str | None) -> date | None:
    """The text ``aaaa-mm-dd`` as a date, or ``None`` when it is empty or not a real date."""
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def item_from_form(fields: Mapping[str, str]) -> ItemInput:
    """The typed item behind the raw text of the form; what does not parse stays empty."""

    def text(name: str) -> str:
        return (fields.get(name) or "").strip()

    return ItemInput(
        system_id=whole_number(fields.get("sistema")),
        subsystem=text("subsistema"),
        tag=text("tag"),
        discipline=text("disciplina"),
        category=text("categoria"),
        milestone=text("marco"),
        origin=text("origem"),
        description=text("descricao"),
        company_id=whole_number(fields.get("empresa")),
        responsible_id=whole_number(fields.get("responsavel")),
        identified_by_id=whole_number(fields.get("identificado_por")),
        due_date=date_of(fields.get("prazo")),
    )


def item_problems(data: ItemInput, choices: RegisterChoices) -> dict[str, str]:
    """The messages for the fields of an item that do not hold up, by the name of the field."""
    problems: dict[str, str] = {}
    _choice(problems, "sistema", data.system_id, choices.system_ids)
    _choice(problems, "empresa", data.company_id, choices.company_ids)
    _choice(problems, "responsavel", data.responsible_id, choices.person_ids)
    _choice(problems, "identificado_por", data.identified_by_id, choices.person_ids)
    _option(problems, "disciplina", data.discipline, calc.DISCIPLINES)
    _option(problems, "categoria", data.category, calc.CATEGORIES)
    _option(problems, "marco", data.milestone, calc.MILESTONES)
    _option(problems, "origem", data.origin, calc.ORIGINS)
    for name, value in (("subsistema", data.subsystem), ("tag", data.tag)):
        if not value:
            problems[name] = REQUIRED
    if not data.description:
        problems["descricao"] = REQUIRED
    elif len(data.description) > MAX_DESCRIPTION:
        problems["descricao"] = TOO_LONG.format(limit=MAX_DESCRIPTION)
    if data.due_date is None:
        problems["prazo"] = REQUIRED
    return problems


def require_valid_item(data: ItemInput, choices: RegisterChoices) -> None:
    """Refuse with 422, one message per field, when the item does not hold up."""
    problems = item_problems(data, choices)
    if problems:
        raise InvalidDataError(problems)


def treatment_problems(comment: str) -> dict[str, str]:
    """The messages for sending to verification: what was done is required."""
    text = comment.strip()
    if not text:
        return {"comentario": TREATMENT_REQUIRED}
    if len(text) > MAX_COMMENT:
        return {"comentario": TOO_LONG.format(limit=MAX_COMMENT)}
    return {}


def verification_problems(result: str, comment: str) -> dict[str, str]:
    """The messages for the verification: a known result and, to reject, the reason."""
    problems: dict[str, str] = {}
    if result not in RESULTS:
        problems["resultado"] = UNKNOWN_RESULT
    if result == REJECTED and not comment.strip():
        problems["comentario"] = REJECTION_REASON_REQUIRED
    if len(comment.strip()) > MAX_COMMENT:
        problems["comentario"] = TOO_LONG.format(limit=MAX_COMMENT)
    return problems


def cancellation_problems(justification: str) -> dict[str, str]:
    """Cancelling needs a justification of at least ten characters."""
    if len(justification.strip()) < MIN_JUSTIFICATION:
        return {"justificativa": JUSTIFICATION_REQUIRED}
    return {}


def _choice(
    problems: dict[str, str], name: str, value: int | None, allowed: frozenset[int]
) -> None:
    if value is None:
        problems[name] = REQUIRED
    elif value not in allowed:
        problems[name] = INVALID_CHOICE


def _option(problems: dict[str, str], name: str, value: str, allowed: tuple[str, ...]) -> None:
    if not value:
        problems[name] = REQUIRED
    elif value not in allowed:
        problems[name] = INVALID_CHOICE
