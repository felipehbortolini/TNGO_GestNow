"""Input validation for the HSE module: HHT, monthly closing, inspections, observations, DDS,
the occurrence with its investigation and its closing (ISSUE-073) and the risk analyses
(ISSUE-074).

The shapes the facade receives and the checks of what a person types. The checks are pure and
return the message by field of the form; the facade turns them into one ``InvalidDataError``, so
the rule holds for the form, for the import and for any module that calls the facade.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from src.modulos.hse import calculations, models

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


# ── Ocorrências (ISSUE-073) ──────────────────────────────────────────────────────────────────

MAX_OCCURRENCE_AREA = 80
MAX_OCCURRENCE_ROLE = 60
MAX_OCCURRENCE_DESCRIPTION = 500
MAX_MEDICAL_NOTES = 500
MAX_PEOPLE_INVOLVED = 20
MAX_COMMUNICATION_HOURS = 200
MAX_DAYS_LOST = 365
MIN_OCCURRENCE_DESCRIPTION = 10
MAX_SEARCH_LENGTH = 120
MIN_EFFECTIVENESS = 10
MAX_EFFECTIVENESS = 600

# The types whose occurrence asks for the role of the involved person (without the name, Q35).
TYPES_WITH_ROLE = (
    "Fatalidade",
    "Acidente com afastamento",
    "Trabalho restrito",
    "Tratamento médico",
    "Primeiros socorros",
)
# The types whose occurrence asks for the days lost and charged (the lost-time injuries).
TYPES_WITH_DAYS = ("Fatalidade", "Acidente com afastamento")

# The immediate causes the form offers (the prototype's list); the rule only requires one.
IMMEDIATE_CAUSES = (
    "Procedimento não seguido",
    "Condição insegura do local",
    "Falha de planejamento da tarefa",
    "EPI inadequado",
    "Falta de sinalização",
    "Equipamento sem inspeção",
    "Outra",
)

OCCURRENCE_DATE_REQUIRED = "Informe a data e a hora."
TIME_FORMAT = "Use o formato HH:MM (ex.: 14:30)."
OCCURRENCE_AREA_REQUIRED = "Informe a área ou o local."
KIND_REQUIRED = "Escolha o tipo de ocorrência."
SUBTYPE_REQUIRED = "Escolha o subtipo ambiental."
SEVERITY_REQUIRED = "Escolha a severidade."
OCCURRENCE_DESCRIPTION_REQUIRED = "Descreva o ocorrido (mínimo de 10 caracteres)."
CAUSE_REQUIRED = "Escolha a causa imediata."
POTENTIAL_REQUIRED = "Informe a probabilidade e o impacto potenciais."
GRAVITY_REQUIRED = "Informe a gravidade real observada."
ROLE_REQUIRED = "Informe a função da pessoa envolvida (sem nome, por LGPD)."
METHOD_REQUIRED = "Escolha o método de investigação."
ROOT_CAUSE_REQUIRED = "Descreva a causa raiz (mínimo de 10 caracteres)."
INVESTIGATION_DATE_REQUIRED = "Informe a data da investigação."
DATE_BEFORE_EVENT = "A data não pode ser anterior à do evento."
ACTIONS_REQUIRED = "Inclua ao menos uma ação corretiva."
EFFECTIVENESS_REQUIRED = "Registre a verificação de eficácia (mínimo de 10 caracteres)."


@dataclass(frozen=True)
class OccurrenceInput:
    """Uma ocorrência como a pessoa registra: o evento, a classificação e o dado restrito (Q35)."""

    project_id: int
    happened_on: date | None
    happened_time: str
    area: str
    company_id: int | None
    kind: str
    subtype: str = ""
    environmental_severity: str = ""
    description: str = ""
    role: str = ""
    people_involved: int | None = 0
    potential_p: int | None = None
    potential_i: int | None = None
    hipo: bool = False
    immediate_cause: str = ""
    communication_hours: int | None = None
    name: str = ""
    real_gravity: int | None = None
    days_lost: int | None = 0
    days_charged: int | None = 0
    cat: bool = False
    medical_notes: str = ""


@dataclass(frozen=True)
class InvestigationInput:
    """Uma investigação: método, causa raiz e data."""

    method: str
    root_cause: str
    investigated_on: date | None


@dataclass(frozen=True)
class CorrectiveActionInput:
    """Uma ação corretiva do modal: assunto, descrição, responsável e data prevista."""

    subject: str
    responsible_id: int | None
    planned_date: date | None
    description: str = ""


@dataclass(frozen=True)
class ClosureInput:
    """O encerramento: a verificação de eficácia, a data e o rascunho da lição (HiPo)."""

    effectiveness: str
    closed_on: date | None
    lesson_title: str = ""
    lesson_recommendation: str = ""


@dataclass(frozen=True)
class OccurrenceFilters:
    """Os filtros da lista de ocorrências: busca, situação, tipo e só HiPo."""

    search: str = ""
    situation: str = ""
    kind: str = ""
    hipo: bool = False


def parse_time(raw: str | None) -> tuple[int, int] | None:
    """A time as ``HH:MM`` typed in the form, or ``None`` when it is not a real time."""
    text = (raw or "").strip()
    if len(text) != 5 or text[2] != ":":
        return None
    hours, minutes = text[:2], text[3:]
    if not (hours.isascii() and hours.isdigit() and minutes.isascii() and minutes.isdigit()):
        return None
    value = (int(hours), int(minutes))
    return value if value[0] <= 23 and value[1] <= 59 else None


def parse_filters(params: Mapping[str, str]) -> OccurrenceFilters:
    """Os filtros da lista a partir da query string; valor desconhecido é ignorado."""
    situation = (params.get("situacao") or "").strip()
    kind = (params.get("tipo") or "").strip()
    return OccurrenceFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH_LENGTH],
        situation=situation if situation in models.OCCURRENCE_SITUATIONS else "",
        kind=kind if kind in models.OCCURRENCE_TYPES else "",
        hipo=(params.get("hipo") or "").strip() in ("1", "true", "sim"),
    )


def _limit_problem(
    text: str, limit: int, *, required_message: str | None, minimum: int = 0
) -> str | None:
    size = len(text.strip())
    if size == 0 or (minimum and size < minimum):
        return required_message
    return f"Aceita até {limit} caracteres." if size > limit else None


def _level_problem(value: int | None, message: str) -> str | None:
    return None if value is not None and 1 <= value <= 5 else message


def occurrence_problems(
    data: OccurrenceInput, choices: RegisterChoices, *, reference_date: date
) -> dict[str, str]:
    """As mensagens de uma nova ocorrência por campo, como o protótipo as escreve."""
    environmental = data.kind == "Ambiental"
    found: dict[str, str | None] = {
        "data": day_problem(data.happened_on, reference_date),
        "hora": (
            None
            if not data.happened_time.strip()
            else TIME_FORMAT
            if parse_time(data.happened_time) is None
            else None
        ),
        "area": _limit_problem(
            data.area, MAX_OCCURRENCE_AREA, required_message=OCCURRENCE_AREA_REQUIRED
        ),
        "empresa": company_problem(data.company_id, choices, required=True),
        "tipo": None if data.kind in models.OCCURRENCE_TYPES else KIND_REQUIRED,
        "comunicacao": count_problem(
            data.communication_hours, MAX_COMMUNICATION_HOURS, what="as horas até a comunicação"
        ),
    }
    if not data.happened_time.strip() and found["data"] is None:
        found["hora"] = OCCURRENCE_DATE_REQUIRED
    if environmental:
        found["subtipo"] = (
            None if data.subtype in models.ENVIRONMENTAL_SUBTYPES else SUBTYPE_REQUIRED
        )
        found["severidade"] = (
            None
            if data.environmental_severity in models.ENVIRONMENTAL_SEVERITIES
            else SEVERITY_REQUIRED
        )
    else:
        found["descricao"] = _limit_problem(
            data.description,
            MAX_OCCURRENCE_DESCRIPTION,
            required_message=OCCURRENCE_DESCRIPTION_REQUIRED,
            minimum=MIN_OCCURRENCE_DESCRIPTION,
        )
        found["causa_imediata"] = None if data.immediate_cause.strip() else CAUSE_REQUIRED
        found["potencial"] = (
            None
            if _level_problem(data.potential_p, POTENTIAL_REQUIRED) is None
            and _level_problem(data.potential_i, POTENTIAL_REQUIRED) is None
            else POTENTIAL_REQUIRED
        )
        found["gravidade"] = _level_problem(data.real_gravity, GRAVITY_REQUIRED)
        if data.kind in TYPES_WITH_ROLE:
            found["funcao"] = _limit_problem(
                data.role, MAX_OCCURRENCE_ROLE, required_message=ROLE_REQUIRED
            )
        found["pessoas"] = count_problem(
            data.people_involved, MAX_PEOPLE_INVOLVED, what="o número de pessoas envolvidas"
        )
        if data.kind in TYPES_WITH_DAYS:
            found["dias_perdidos"] = count_problem(
                data.days_lost, MAX_DAYS_LOST, what="os dias perdidos"
            )
            found["dias_debitados"] = count_problem(
                data.days_charged, MAX_DAYS_LOST, what="os dias debitados"
            )
    found["medica"] = _limit_problem(data.medical_notes, MAX_MEDICAL_NOTES, required_message=None)
    return {name: message for name, message in found.items() if message}


def investigation_problems(
    data: InvestigationInput, *, event_date: date, reference_date: date
) -> dict[str, str]:
    """As mensagens de uma investigação por campo, como o protótipo as escreve."""
    found: dict[str, str | None] = {
        "metodo": None if data.method in models.INVESTIGATION_METHODS else METHOD_REQUIRED,
        "causa_raiz": _limit_problem(
            data.root_cause,
            MAX_OCCURRENCE_DESCRIPTION,
            required_message=ROOT_CAUSE_REQUIRED,
            minimum=MIN_OCCURRENCE_DESCRIPTION,
        ),
        "data": day_problem(data.investigated_on, reference_date),
    }
    if (
        found["data"] is None
        and data.investigated_on is not None
        and data.investigated_on < event_date
    ):
        found["data"] = DATE_BEFORE_EVENT
    return {name: message for name, message in found.items() if message}


def corrective_action_problems(
    data: CorrectiveActionInput, choices: RegisterChoices
) -> dict[str, str]:
    """As mensagens de uma ação corretiva por campo."""
    found = {
        "assunto": None if data.subject.strip() else "Informe o assunto.",
        "responsavel": person_problem(data.responsible_id, choices, required=True),
        "prevista": None if data.planned_date is not None else "Informe a data prevista.",
        "descricao": _limit_problem(data.description, MAX_TEXT, required_message=None),
    }
    return {name: message for name, message in found.items() if message}


def closure_problems(
    data: ClosureInput, *, event_date: date, reference_date: date
) -> dict[str, str]:
    """As mensagens do encerramento: a eficácia verificada e a data (≤ hoje e ≥ evento)."""
    found: dict[str, str | None] = {
        "eficacia": _limit_problem(
            data.effectiveness,
            MAX_EFFECTIVENESS,
            required_message=EFFECTIVENESS_REQUIRED,
            minimum=MIN_EFFECTIVENESS,
        ),
        "data": day_problem(data.closed_on, reference_date),
    }
    if found["data"] is None and data.closed_on is not None and data.closed_on < event_date:
        found["data"] = DATE_BEFORE_EVENT
    return {name: message for name, message in found.items() if message}


# ── Análises de risco (ISSUE-074) ────────────────────────────────────────────────────────────

MAX_ANALYSIS_AREA = 80
MAX_ANALYSIS_TITLE = 150
MIN_ANALYSIS_TITLE = 5

ANALYSIS_TYPE_REQUIRED = "Escolha o tipo de estudo."
ANALYSIS_AREA_REQUIRED = "Informe a área."
ANALYSIS_TITLE_REQUIRED = f"Informe o título do estudo (mínimo de {MIN_ANALYSIS_TITLE} caracteres)."
PARTICIPANTS_REQUIRED = "Escolha ao menos um participante."
RECOMMENDATIONS_REQUIRED = "Inclua ao menos uma recomendação."
RECOMMENDATION_RESPONSIBLE_REQUIRED = "Recomendação {index}: escolha o responsável."
RECOMMENDATION_DEADLINE_REQUIRED = "Recomendação {index}: informe o prazo."
CLOSING_DATE_REQUIRED = "Informe a data de conclusão."


@dataclass(frozen=True)
class AnalysisRecommendationInput:
    """Uma recomendação digitada: descrição, responsável e prazo."""

    description: str
    responsible_id: int | None
    due_date: date | None


@dataclass(frozen=True)
class AnalysisInput:
    """Um estudo como a pessoa registra: tipo, área, título, data, participantes e recomendações."""

    project_id: int
    kind: str
    area: str
    title: str
    held_on: date | None
    participant_ids: tuple[int, ...] = ()
    recommendations: tuple[AnalysisRecommendationInput, ...] = ()


@dataclass(frozen=True)
class RecommendationClosureInput:
    """O fechamento de uma recomendação: a data de conclusão e a evidência opcional."""

    closed_on: date | None
    evidence: str = ""


@dataclass(frozen=True)
class AnalysisFilters:
    """Os filtros da lista de análises: busca, tipo e só com recomendação aberta."""

    search: str = ""
    kind: str = ""
    open_only: bool = False


def parse_ids(raws: Iterable[str | None]) -> tuple[int, ...]:
    """Os ids válidos de um campo de múltipla escolha, na ordem e sem repetição."""
    found: list[int] = []
    for raw in raws:
        parsed = parse_id(raw)
        if parsed is not None and parsed not in found:
            found.append(parsed)
    return tuple(found)


def parse_analysis_filters(params: Mapping[str, str]) -> AnalysisFilters:
    """Os filtros da lista a partir da query string; valor desconhecido é ignorado."""
    kind = (params.get("tipo") or "").strip()
    return AnalysisFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH_LENGTH],
        kind=kind if kind in models.ANALYSIS_TYPES else "",
        open_only=(params.get("abertas") or "").strip() in ("1", "true", "sim"),
    )


def _analysis_title_problem(title: str) -> str | None:
    size = len(title.strip())
    if size < MIN_ANALYSIS_TITLE:
        return ANALYSIS_TITLE_REQUIRED
    return f"Aceita até {MAX_ANALYSIS_TITLE} caracteres." if size > MAX_ANALYSIS_TITLE else None


def _recommendations_problem(
    recommendations: Sequence[AnalysisRecommendationInput], choices: RegisterChoices
) -> str | None:
    if not recommendations:
        return RECOMMENDATIONS_REQUIRED
    problems: list[str] = []
    for index, item in enumerate(recommendations, start=1):
        if item.responsible_id is None or item.responsible_id not in choices.person_ids:
            problems.append(RECOMMENDATION_RESPONSIBLE_REQUIRED.format(index=index))
        if item.due_date is None:
            problems.append(RECOMMENDATION_DEADLINE_REQUIRED.format(index=index))
        if _limit_problem(item.description, MAX_TEXT, required_message=None):
            problems.append(f"Recomendação {index}: aceita até {MAX_TEXT} caracteres.")
    return " ".join(problems) if problems else None


def analysis_problems(
    data: AnalysisInput, choices: RegisterChoices, *, reference_date: date
) -> dict[str, str]:
    """As mensagens de um novo estudo por campo, como o protótipo as escreve."""
    found = {
        "tipo": None if data.kind in models.ANALYSIS_TYPES else ANALYSIS_TYPE_REQUIRED,
        "area": _limit_problem(
            data.area, MAX_ANALYSIS_AREA, required_message=ANALYSIS_AREA_REQUIRED
        ),
        "titulo": _analysis_title_problem(data.title),
        "data": day_problem(data.held_on, reference_date),
        "participantes": (
            PARTICIPANTS_REQUIRED
            if not data.participant_ids
            else UNKNOWN_PERSON
            if any(person_id not in choices.person_ids for person_id in data.participant_ids)
            else None
        ),
        "recomendacoes": _recommendations_problem(data.recommendations, choices),
    }
    return {name: message for name, message in found.items() if message}


def recommendation_closure_problems(
    data: RecommendationClosureInput, *, reference_date: date
) -> dict[str, str]:
    """As mensagens do fechamento: a data de conclusão (≤ hoje) e a evidência."""
    found: dict[str, str | None] = {
        "data": (
            CLOSING_DATE_REQUIRED
            if data.closed_on is None
            else DATE_IN_THE_FUTURE
            if data.closed_on > reference_date
            else None
        ),
        "evidencia": _limit_problem(data.evidence, MAX_TEXT, required_message=None),
    }
    return {name: message for name, message in found.items() if message}
