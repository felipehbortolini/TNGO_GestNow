"""Input validation for the HSE module: HHT, monthly closing, inspections, observations, DDS.

The shapes the facade receives and the checks of what a person types. The checks are pure and
return the message by field of the form; the facade turns them into one ``InvalidDataError``, so
the rule holds for the form, for the import and for any module that calls the facade.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from src.modulos.hse import calculations

MAX_ID_DIGITS = 18
MAX_HEADCOUNT = 5000
MAX_HOURS = Decimal(999999)
MAX_DDS = 2000
MAX_ITEMS = 20000
MAX_OBSERVATIONS = 5000
MAX_DEVIATIONS = 5000
MAX_PARTICIPANTS = 5000
MAX_TEXT = 300
MAX_CHECKLIST_ITEMS = 60
PAGE_SIZE = 15

OBSERVATION_KINDS = ("Ato inseguro", "Condição insegura", "Comportamento seguro")
OBSERVATION_OPEN = "Aberta"
OBSERVATION_TREATED = "Tratada"
OBSERVATION_STATUSES = (OBSERVATION_OPEN, OBSERVATION_TREATED)

MONTH_REQUIRED = "Informe o mês (AAAA-MM)."
MONTH_IN_THE_FUTURE = "Não é possível registrar um mês futuro em relação à referência."
COMPANY_REQUIRED = "Escolha a empresa."
UNKNOWN_COMPANY = "A empresa informada não está no cadastro."
UNKNOWN_PERSON = "A pessoa informada não está no cadastro."
RESPONSIBLE_REQUIRED = "Escolha o responsável."
DATE_REQUIRED = "Informe a data."
DATE_IN_THE_FUTURE = "A data não pode ser posterior à data de referência."
AREA_REQUIRED = "Informe a área."
TOPIC_REQUIRED = "Informe o tema."
DESCRIPTION_REQUIRED = "Informe a descrição."
TOO_LONG = f"Aceita até {MAX_TEXT} caracteres."
CHECKLIST_REQUIRED = "Informe ao menos um item do checklist."
CHECKLIST_TOO_LONG = f"O checklist aceita até {MAX_CHECKLIST_ITEMS} itens."
ITEM_DESCRIPTION_REQUIRED = "Todo item do checklist precisa de descrição."
HELD_ABOVE_PLANNED = "Não pode ser maior que o programado."
CONFORMING_ABOVE_INSPECTED = "Não pode ser maior que o inspecionado."
KIND_INVALID = "Escolha o tipo da observação."
STATUS_INVALID = "Escolha a situação da observação."


def _range_message(limit: int | Decimal, *, what: str) -> str:
    return f"Informe {what} de 0 a {limit:,}.".replace(",", ".")


@dataclass(frozen=True)
class HoursInput:
    """One HHT record: the project, the month, the company, the headcount and the hours."""

    project_id: int
    month: date | None
    company_id: int | None
    headcount: int | None
    hours: Decimal | None
    version: int | str | None = None


@dataclass(frozen=True)
class ClosingInput:
    """One monthly closing: the six counts of the month."""

    project_id: int
    month: date | None
    deviations: int | None
    observations: int | None
    planned_dds: int | None
    held_dds: int | None
    inspected_items: int | None
    conforming_items: int | None
    version: int | str | None = None


@dataclass(frozen=True)
class ChecklistItemInput:
    """One checklist item as typed: the description, whether it is conforming and a note."""

    description: str
    conforming: bool
    note: str = ""


@dataclass(frozen=True)
class InspectionInput:
    """One safety inspection with its checklist."""

    project_id: int
    inspected_on: date | None
    area: str
    responsible_id: int | None
    company_id: int | None = None
    note: str = ""
    items: tuple[ChecklistItemInput, ...] = field(default_factory=tuple)
    version: int | str | None = None


@dataclass(frozen=True)
class ObservationInput:
    """One behavior observation."""

    project_id: int
    observed_on: date | None
    area: str
    kind: str
    description: str
    responsible_id: int | None
    company_id: int | None = None
    observed_id: int | None = None
    status: str = OBSERVATION_OPEN
    version: int | str | None = None


@dataclass(frozen=True)
class TalkInput:
    """One DDS: when, the topic, who led it and how many people took part."""

    project_id: int
    held_on: date | None
    topic: str
    responsible_id: int | None
    participants: int | None
    company_id: int | None = None
    version: int | str | None = None


@dataclass(frozen=True)
class RegisterChoices:
    """The ids the register knows: what a company or a person of a form must be one of."""

    company_ids: Collection[int]
    person_ids: Collection[int]


def parse_id(raw: str | None) -> int | None:
    """An id sent by a screen: digits only, never absurdly long, or ``None``."""
    text = (raw or "").strip()
    if not text.isascii() or not text.isdigit() or len(text) > MAX_ID_DIGITS:
        return None
    return int(text)


def parse_count(raw: str | None) -> int | None:
    """A whole number as typed, or ``None`` when empty, fractional, negative or not a number."""
    text = (raw or "").strip()
    if not text.isascii() or not text.isdigit() or len(text) > MAX_ID_DIGITS:
        return None
    return int(text)


def parse_decimal(raw: str | None) -> Decimal | None:
    """A non-negative number as typed (comma or point as the decimal mark), or ``None``."""
    text = (raw or "").strip().replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def parse_date(raw: str | None) -> date | None:
    """A date as the date field sends it (``2026-09-25``), or ``None`` when empty or invalid."""
    text = (raw or "").strip()
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def parse_page(params: Mapping[str, str]) -> int:
    """The page of a list, starting at 1; anything that is not a positive number is page 1."""
    return parse_id(params.get("pagina")) or 1


def month_problem(month: date | None, reference_date: date) -> str | None:
    """The message for the month field: required, and not after the reference month."""
    if month is None:
        return MONTH_REQUIRED
    if calculations.is_future_month(month, reference_date):
        return MONTH_IN_THE_FUTURE
    return None


def count_problem(value: int | None, limit: int, *, what: str) -> str | None:
    """The message for a count field: required, 0 or more and within the limit."""
    if value is None or value < 0 or value > limit:
        return _range_message(limit, what=what)
    return None


def company_problem(
    company_id: int | None, choices: RegisterChoices, *, required: bool
) -> str | None:
    """The message for the company field; an optional company, when sent, must exist."""
    if company_id is None:
        return COMPANY_REQUIRED if required else None
    return None if company_id in choices.company_ids else UNKNOWN_COMPANY


def person_problem(
    person_id: int | None, choices: RegisterChoices, *, required: bool
) -> str | None:
    """The message for a person field; an optional person, when sent, must exist."""
    if person_id is None:
        return RESPONSIBLE_REQUIRED if required else None
    return None if person_id in choices.person_ids else UNKNOWN_PERSON


def day_problem(day: date | None, reference_date: date) -> str | None:
    """The message for a date field: required and not after the reference date."""
    if day is None:
        return DATE_REQUIRED
    return DATE_IN_THE_FUTURE if day > reference_date else None


def text_problem(text: str, *, required_message: str | None) -> str | None:
    """The message for a free text: required when a message is given, and at most 300 characters."""
    size = len(text.strip())
    if size == 0:
        return required_message
    return TOO_LONG if size > MAX_TEXT else None


def hours_problems(
    data: HoursInput, choices: RegisterChoices, *, reference_date: date
) -> dict[str, str]:
    """The messages of an HHT record by field of the form."""
    found = {
        "mes": month_problem(data.month, reference_date),
        "empresa": company_problem(data.company_id, choices, required=True),
        "efetivo_medio": count_problem(data.headcount, MAX_HEADCOUNT, what="o efetivo médio"),
        "hht": (
            None
            if data.hours is not None and data.hours <= MAX_HOURS
            else _range_message(MAX_HOURS, what="as horas-homem trabalhadas")
        ),
    }
    return {name: message for name, message in found.items() if message}


def closing_problems(data: ClosingInput, *, reference_date: date) -> dict[str, str]:
    """The messages of a monthly closing by field: the month, the six counts and their order."""
    found = {
        "mes": month_problem(data.month, reference_date),
        "dds_programados": count_problem(data.planned_dds, MAX_DDS, what="os DDS programados"),
        "dds_realizados": count_problem(data.held_dds, MAX_DDS, what="os DDS realizados"),
        "itens_inspecionados": count_problem(
            data.inspected_items, MAX_ITEMS, what="os itens inspecionados"
        ),
        "itens_conformes": count_problem(
            data.conforming_items, MAX_ITEMS, what="os itens conformes"
        ),
        "observacoes": count_problem(data.observations, MAX_OBSERVATIONS, what="as observações"),
        "desvios": count_problem(data.deviations, MAX_DEVIATIONS, what="os desvios"),
    }
    if found["dds_realizados"] is None and (data.held_dds or 0) > (data.planned_dds or 0):
        found["dds_realizados"] = HELD_ABOVE_PLANNED
    if found["itens_conformes"] is None and (data.conforming_items or 0) > (
        data.inspected_items or 0
    ):
        found["itens_conformes"] = CONFORMING_ABOVE_INSPECTED
    return {name: message for name, message in found.items() if message}


def inspection_problems(
    data: InspectionInput, choices: RegisterChoices, *, reference_date: date
) -> dict[str, str]:
    """The messages of an inspection by field: date, area, people, company and the checklist."""
    found = {
        "data": day_problem(data.inspected_on, reference_date),
        "area": text_problem(data.area, required_message=AREA_REQUIRED),
        "responsavel": person_problem(data.responsible_id, choices, required=True),
        "empresa": company_problem(data.company_id, choices, required=False),
        "observacao": text_problem(data.note, required_message=None),
        "itens": _checklist_problem(data.items),
    }
    return {name: message for name, message in found.items() if message}


def _checklist_problem(items: tuple[ChecklistItemInput, ...]) -> str | None:
    if not items:
        return CHECKLIST_REQUIRED
    if len(items) > MAX_CHECKLIST_ITEMS:
        return CHECKLIST_TOO_LONG
    for item in items:
        if not item.description.strip():
            return ITEM_DESCRIPTION_REQUIRED
        if text_problem(item.description, required_message=None) or text_problem(
            item.note, required_message=None
        ):
            return TOO_LONG
    return None


def observation_problems(
    data: ObservationInput, choices: RegisterChoices, *, reference_date: date
) -> dict[str, str]:
    """The messages of a behavior observation by field of the form."""
    found = {
        "data": day_problem(data.observed_on, reference_date),
        "area": text_problem(data.area, required_message=AREA_REQUIRED),
        "tipo": None if data.kind in OBSERVATION_KINDS else KIND_INVALID,
        "descricao": text_problem(data.description, required_message=DESCRIPTION_REQUIRED),
        "responsavel": person_problem(data.responsible_id, choices, required=True),
        "observado": person_problem(data.observed_id, choices, required=False),
        "empresa": company_problem(data.company_id, choices, required=False),
        "situacao": None if data.status in OBSERVATION_STATUSES else STATUS_INVALID,
    }
    return {name: message for name, message in found.items() if message}


def talk_problems(
    data: TalkInput, choices: RegisterChoices, *, reference_date: date
) -> dict[str, str]:
    """The messages of a DDS by field of the form."""
    found = {
        "data": day_problem(data.held_on, reference_date),
        "tema": text_problem(data.topic, required_message=TOPIC_REQUIRED),
        "responsavel": person_problem(data.responsible_id, choices, required=True),
        "empresa": company_problem(data.company_id, choices, required=False),
        "participantes": count_problem(
            data.participants, MAX_PARTICIPANTS, what="o número de participantes"
        ),
    }
    return {name: message for name, message in found.items() if message}
