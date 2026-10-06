"""Input validation of the Governança module: what a new change and a cancellation must carry.

The rules are those of the prototype (``validarCamposSm`` and ``cancelarMudanca``): a required field
missing, a text too short or too long, a value outside its list or a date after the reference date
is 422 with one message per field, so the form comes back filled with the message under the field.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from src.core.errors import InvalidDataError
from src.modulos.governanca import models

TITLE_LIMITS = (10, 150)
DESCRIPTION_LIMITS = (20, 1000)
EMERGENCY_JUSTIFICATION_LIMITS = (20, 500)
CANCELLATION_LIMITS = (10, 500)

CHECKED_VALUE = "sim"

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
