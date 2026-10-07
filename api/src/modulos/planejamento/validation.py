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

The dictionary of the WBS package and the weight rules (ISSUE-036): the
descriptive fields of the package (description, deliverable, acceptance,
company, owner and the EAC item) and the rules that keep the weights within the
parameters (100% of the project and the maximum per package).

The measurement of the package by its criterion (ISSUE-037): the entries of the
advance per criterion, the reversal gate (Gestor and justification) and the
import of the accumulated progress line by line, each refusal with its motive.

The revision of the EAP and the breakdown (ISSUE-038): the new package and the
adjustment of a package from a change request, with the limits of the
parameters and the gate that keeps weight for the other packages.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

from src.core.errors import AccessDeniedError, InvalidDataError

if TYPE_CHECKING:
    from src.modulos.planejamento.calculations import EapPercentEntries, EapStep

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


PACKAGE_DESCRIPTION_MIN = 3


PACKAGE_DESCRIPTION_MAX = 120


PACKAGE_TEXT_MAX = 300


PACKAGE_DESCRIPTION_MESSAGE = "Descreva o pacote (mínimo de 3 caracteres)."


PACKAGE_WEIGHT_ZERO_MESSAGE = "Informe um peso maior que zero."


PACKAGE_WEIGHT_MAX_MESSAGE = (
    "O peso passa o máximo de {maximum}% por pacote: decomponha em pacotes menores."
)


WEIGHTS_TOTAL_MESSAGE = "Os pesos dos pacotes devem somar 100% (atual: {total}%)."


HUNDRED = Decimal(100)


TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class DictionaryChoices:
    """O que o cadastro oferece ao dicionário: as empresas, as pessoas e os itens da EAC."""

    company_ids: frozenset[int]
    person_ids: frozenset[int]
    eac_codes: frozenset[str]


@dataclass(frozen=True)
class PackageDictionary:
    """O dicionário do pacote, pronto para a fachada."""

    description: str
    deliverable: str
    acceptance: str
    company_id: int | None
    owner_id: int
    eac_code: str | None


def _package_description(raw: Mapping[str, str], errors: dict[str, str]) -> str:
    value = _text(raw, "descricao")
    if len(value) < PACKAGE_DESCRIPTION_MIN:
        errors["descricao"] = PACKAGE_DESCRIPTION_MESSAGE
    elif len(value) > PACKAGE_DESCRIPTION_MAX:
        errors["descricao"] = TOO_LONG_MESSAGE.format(
            label="A descrição", limit=PACKAGE_DESCRIPTION_MAX
        )
    return value


def _optional_text(
    raw: Mapping[str, str], field: str, *, label: str, limit: int, errors: dict[str, str]
) -> str:
    value = _text(raw, field)
    if len(value) > limit:
        errors[field] = TOO_LONG_MESSAGE.format(label=label.capitalize(), limit=limit)
    return value


def _optional_choice_id(
    raw: Mapping[str, str],
    field: str,
    *,
    label: str,
    allowed: frozenset[int],
    errors: dict[str, str],
) -> int | None:
    text = _text(raw, field)
    if not text:
        return None
    found = parse_id(text)
    if found is None or found not in allowed:
        errors[field] = UNKNOWN_CHOICE_MESSAGE.format(label=label)
        return None
    return found


def _optional_choice_text(
    raw: Mapping[str, str],
    field: str,
    *,
    label: str,
    allowed: frozenset[str],
    errors: dict[str, str],
) -> str | None:
    value = _text(raw, field)
    if not value:
        return None
    if value not in allowed:
        errors[field] = UNKNOWN_CHOICE_MESSAGE.format(label=label)
        return None
    return value


def parse_dictionary_form(raw: Mapping[str, str], choices: DictionaryChoices) -> PackageDictionary:
    """O dicionário do formulário, ou ``InvalidDataError`` com a mensagem de cada campo errado."""
    errors: dict[str, str] = {}
    description = _package_description(raw, errors)
    deliverable = _optional_text(
        raw, "entregavel", label="o entregável", limit=PACKAGE_TEXT_MAX, errors=errors
    )
    acceptance = _optional_text(
        raw, "aceitacao", label="o critério de aceitação", limit=PACKAGE_TEXT_MAX, errors=errors
    )
    company_id = _optional_choice_id(
        raw, "empresa", label="a empresa", allowed=choices.company_ids, errors=errors
    )
    owner_id = _choice_id(
        raw, "responsavel", label="o responsável", allowed=choices.person_ids, errors=errors
    )
    eac_code = _optional_choice_text(
        raw, "eac", label="o item da EAC", allowed=choices.eac_codes, errors=errors
    )
    if errors:
        raise InvalidDataError(errors)
    return PackageDictionary(
        description=description,
        deliverable=deliverable,
        acceptance=acceptance,
        company_id=company_id,
        owner_id=owner_id,
        eac_code=eac_code,
    )


def weights_total(weights: Sequence[Decimal]) -> Decimal:
    """A soma dos pesos dos pacotes, em % com 2 casas."""
    return sum(weights, Decimal(0)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def hundred_rule_error(weights: Sequence[Decimal]) -> str | None:
    """A regra dos 100%: os pesos dos pacotes de um projeto fecham em exatamente 100."""
    total = weights_total(weights)
    if total != HUNDRED:
        return WEIGHTS_TOTAL_MESSAGE.format(total=total)
    return None


def package_weight_error(weight: Decimal, *, maximum: Decimal) -> str | None:
    """O peso de um pacote: maior que zero e até o máximo do parâmetro."""
    if weight <= 0:
        return PACKAGE_WEIGHT_ZERO_MESSAGE
    if weight > maximum:
        return PACKAGE_WEIGHT_MAX_MESSAGE.format(maximum=maximum)
    return None


ZERO = Decimal(0)


FIELD_MEASURED_ON = "data"


FIELD_EXECUTED = "executado"


FIELD_MILESTONE_STATE = "estado"


FIELD_ESTIMATED_PCT = "estimadoPct"


FIELD_NOTE = "obs"


FIELD_JUSTIFICATION = "justificativa"


JUSTIFICATION_MIN_CHARACTERS = 10


MEASUREMENT_DATE_REQUIRED_MESSAGE = "Informe a data da medição."


MEASUREMENT_DATE_FUTURE_MESSAGE = "A data não pode ser posterior à referência."


STEP_PCT_RANGE_MESSAGE = "Use um valor entre 0 e 100%."


EXECUTED_REQUIRED_MESSAGE = "Informe a quantidade executada acumulada."


EXECUTED_OVER_QUANTITY_MESSAGE = (
    "O executado passa a quantidade da linha de base ({quantity} {unit}). "
    "Registre uma SM (08) para revisar a EAP."
)


MILESTONE_STATE_MESSAGE = "Escolha a situação do marco."


ESTIMATED_PCT_RANGE_MESSAGE = "Informe um avanço entre 0 e 100%."


ESTIMATED_WEIGHT_MESSAGE = (
    "Percentual estimado só vale para pacotes de até {maximum}% de peso; use etapas ou unidades."
)


REVERSAL_MANAGER_MESSAGE = "Estorno de avanço exige papel Gestor."


REVERSAL_JUSTIFICATION_MESSAGE = (
    "Estorno de avanço (de {from_pct}% para {to_pct}%) exige justificativa."
)


IMPORT_PACKAGE_NOT_FOUND_MESSAGE = "{code}: pacote não encontrado."


IMPORT_PLANNING_MESSAGE = "{code}: pacote de planejamento não recebe medição."


IMPORT_REGRESSION_MESSAGE = (
    "{code}: o avanço não pode regredir (de {from_pct}% para {to_pct}%); "
    "estorno só pela tela, com justificativa."
)


@dataclass(frozen=True)
class ProgressEntries:
    """As entradas do critério da medição; só as do critério do pacote vêm preenchidas."""

    steps: tuple[EapStep, ...] = ()
    executed: Decimal | None = None
    state: str | None = None
    estimated_pct: Decimal | None = None


@dataclass(frozen=True)
class ProgressPackage:
    """O pacote de nível 3 como a validação pura da medição o lê.

    ``current`` é o real corrente do critério; ``steps`` são as etapas correntes do critério
    Etapas; ``kind`` separa o pacote de trabalho do de planejamento, que não recebe medição.
    """

    kind: str
    criterion: str | None
    weight: Decimal
    current: Decimal
    quantity: Decimal | None = None
    unit: str = ""
    steps: tuple[EapStep, ...] = ()


@dataclass(frozen=True)
class ProgressData:
    """A medição validada do formulário: a data, o de/para, as entradas e a observação."""

    measured_on: date
    from_pct: Decimal
    to_pct: Decimal
    entries: ProgressEntries
    note: str = ""


@dataclass(frozen=True)
class ImportRowInput:
    """Uma linha da planilha de avanço: o código do pacote e o % acumulado ou a quantidade."""

    code: str = ""
    percent: Decimal | None = None
    executed: Decimal | None = None


@dataclass(frozen=True)
class ImportRowResult:
    """O resultado de uma linha da importação: a medição aceita ou o motivo da recusa.

    ``entries`` nulo sem ``error`` é linha sem mudança: não há o que gravar.
    """

    code: str
    entries: ProgressEntries | None = None
    from_pct: Decimal | None = None
    to_pct: Decimal | None = None
    error: str = ""


def parse_progress_form(
    raw: Mapping[str, str],
    package: ProgressPackage,
    *,
    reference_date: date,
    is_manager: bool,
    max_estimated_weight: Decimal,
) -> ProgressData:
    """A medição do formulário, ou ``InvalidDataError`` com a mensagem de cada campo errado.

    O acumulado não regride: uma medição abaixo do real corrente exige papel Gestor
    (``AccessDeniedError``) e justificativa de 10 caracteres ou mais.
    """
    from src.modulos.planejamento import calculations

    if package.criterion not in calculations.EAP_CRITERIA:
        raise InvalidDataError(calculations.EAP_NO_CRITERION_MESSAGE)
    errors: dict[str, str] = {}
    measured_on = _measurement_date(raw, reference_date, errors)
    entries = _progress_entries(raw, package, max_estimated_weight, errors)
    if errors:
        raise InvalidDataError(errors)
    to_pct = _progress_after(package, entries)
    _require_reversal_terms(raw, package, to_pct, is_manager=is_manager)
    note = _text(raw, FIELD_NOTE) or _text(raw, FIELD_JUSTIFICATION)
    return ProgressData(
        measured_on=measured_on,
        from_pct=package.current,
        to_pct=to_pct,
        entries=entries,
        note=note,
    )


def parse_import_rows(
    rows: Sequence[ImportRowInput], packages: Mapping[str, ProgressPackage]
) -> tuple[ImportRowResult, ...]:
    """A importação do avanço, linha a linha: a medição aceita ou o motivo da recusa.

    O pacote de planejamento, o percentual fora dos degraus do marco e a linha que regride
    são recusados com o motivo; a linha sem mudança não tem o que gravar.
    """
    return tuple(_import_row(row, packages) for row in rows)


def _measurement_date(raw: Mapping[str, str], reference_date: date, errors: dict[str, str]) -> date:
    text = _text(raw, FIELD_MEASURED_ON)
    try:
        found = date.fromisoformat(text)
    except ValueError:
        errors[FIELD_MEASURED_ON] = MEASUREMENT_DATE_REQUIRED_MESSAGE
        return reference_date
    if found > reference_date:
        errors[FIELD_MEASURED_ON] = MEASUREMENT_DATE_FUTURE_MESSAGE
    return found


def _progress_entries(
    raw: Mapping[str, str],
    package: ProgressPackage,
    max_estimated_weight: Decimal,
    errors: dict[str, str],
) -> ProgressEntries:
    from src.modulos.planejamento import calculations

    if package.criterion == calculations.CRITERION_STEPS:
        return ProgressEntries(steps=_steps_input(raw, package, errors))
    if package.criterion == calculations.CRITERION_UNITS:
        return ProgressEntries(executed=_executed_input(raw, package, errors))
    if package.criterion == calculations.CRITERION_MILESTONE_0_100:
        return ProgressEntries(state=_state_input(raw, calculations.MILESTONE_0_100_STATES, errors))
    if package.criterion == calculations.CRITERION_MILESTONE_50_50:
        return ProgressEntries(state=_state_input(raw, calculations.MILESTONE_50_50_STATES, errors))
    return ProgressEntries(
        estimated_pct=_estimated_input(raw, package, max_estimated_weight, errors)
    )


def _steps_input(
    raw: Mapping[str, str], package: ProgressPackage, errors: dict[str, str]
) -> tuple[EapStep, ...]:
    from src.modulos.planejamento.calculations import EapStep

    steps: list[EapStep] = []
    for index, step in enumerate(package.steps):
        field = f"etapa{index}"
        text = _text(raw, field)
        if not text:
            steps.append(step)
            continue
        value = _decimal(text)
        if value is None or value < ZERO or value > HUNDRED:
            errors[field] = STEP_PCT_RANGE_MESSAGE
            value = step.pct
        steps.append(EapStep(name=step.name, weight=step.weight, pct=value))
    return tuple(steps)


def _executed_input(
    raw: Mapping[str, str], package: ProgressPackage, errors: dict[str, str]
) -> Decimal | None:
    value = _decimal(_text(raw, FIELD_EXECUTED))
    message = _executed_error(value, package)
    if message:
        errors[FIELD_EXECUTED] = message
    return value


def _executed_error(executed: Decimal | None, package: ProgressPackage) -> str | None:
    if executed is None or executed < ZERO:
        return EXECUTED_REQUIRED_MESSAGE
    if package.quantity is not None and executed > package.quantity:
        return EXECUTED_OVER_QUANTITY_MESSAGE.format(
            quantity=_plain_number(package.quantity), unit=package.unit
        )
    return None


def _state_input(raw: Mapping[str, str], states: Sequence[str], errors: dict[str, str]) -> str:
    value = _text(raw, FIELD_MILESTONE_STATE)
    if value not in states:
        errors[FIELD_MILESTONE_STATE] = MILESTONE_STATE_MESSAGE
    return value


def _estimated_input(
    raw: Mapping[str, str],
    package: ProgressPackage,
    max_estimated_weight: Decimal,
    errors: dict[str, str],
) -> Decimal | None:
    value = _decimal(_text(raw, FIELD_ESTIMATED_PCT))
    if package.weight > max_estimated_weight:
        errors[FIELD_ESTIMATED_PCT] = ESTIMATED_WEIGHT_MESSAGE.format(
            maximum=_plain_number(max_estimated_weight)
        )
    elif value is None or value < ZERO or value > HUNDRED:
        errors[FIELD_ESTIMATED_PCT] = ESTIMATED_PCT_RANGE_MESSAGE
    return value


def _progress_after(package: ProgressPackage, entries: ProgressEntries) -> Decimal:
    from src.modulos.planejamento import calculations

    return calculations.eap_package_progress(
        package.criterion,
        etapas=entries.steps,
        quantity=package.quantity,
        executed=entries.executed,
        state=entries.state,
        estimated_pct=entries.estimated_pct,
    )


def _require_reversal_terms(
    raw: Mapping[str, str], package: ProgressPackage, to_pct: Decimal, *, is_manager: bool
) -> None:
    from src.modulos.planejamento import calculations

    if not calculations.eap_progress_regression(package.current, to_pct):
        return
    if not is_manager:
        raise AccessDeniedError(REVERSAL_MANAGER_MESSAGE)
    if len(_text(raw, FIELD_JUSTIFICATION)) < JUSTIFICATION_MIN_CHARACTERS:
        raise InvalidDataError(
            {
                FIELD_JUSTIFICATION: REVERSAL_JUSTIFICATION_MESSAGE.format(
                    from_pct=_plain_number(package.current), to_pct=_plain_number(to_pct)
                )
            }
        )


def _import_row(row: ImportRowInput, packages: Mapping[str, ProgressPackage]) -> ImportRowResult:
    from src.modulos.planejamento import calculations

    package = packages.get(row.code)
    if package is None:
        return ImportRowResult(
            code=row.code, error=IMPORT_PACKAGE_NOT_FOUND_MESSAGE.format(code=row.code)
        )
    if package.kind == calculations.PLANNING_PACKAGE:
        return ImportRowResult(code=row.code, error=IMPORT_PLANNING_MESSAGE.format(code=row.code))
    entries, message = _import_entries(row, package)
    if message:
        return ImportRowResult(code=row.code, error=f"{row.code}: {message}")
    to_pct = _progress_after(package, entries)
    if calculations.eap_progress_regression(package.current, to_pct):
        return ImportRowResult(
            code=row.code,
            error=IMPORT_REGRESSION_MESSAGE.format(
                code=row.code,
                from_pct=_plain_number(package.current),
                to_pct=_plain_number(to_pct),
            ),
        )
    if to_pct == package.current:
        return ImportRowResult(code=row.code)
    return ImportRowResult(code=row.code, entries=entries, from_pct=package.current, to_pct=to_pct)


def _import_entries(row: ImportRowInput, package: ProgressPackage) -> tuple[ProgressEntries, str]:
    from src.modulos.planejamento import calculations

    if package.criterion == calculations.CRITERION_UNITS and row.executed is not None:
        entries = ProgressEntries(executed=row.executed)
    else:
        conversion = calculations.eap_entries_from_percent(
            package.criterion,
            row.percent,
            etapas=package.steps,
            quantity=package.quantity,
        )
        if conversion.error:
            return ProgressEntries(), conversion.error
        entries = _converted_entries(conversion)
    if package.criterion == calculations.CRITERION_UNITS:
        message = _executed_error(entries.executed, package)
        if message:
            return ProgressEntries(), message
    return entries, ""


def _converted_entries(conversion: EapPercentEntries) -> ProgressEntries:
    return ProgressEntries(
        steps=conversion.etapas,
        executed=conversion.executed,
        state=conversion.state,
        estimated_pct=conversion.estimated_pct,
    )


def _decimal(text: str) -> Decimal | None:
    try:
        value = Decimal(text)
    except ArithmeticError:
        return None
    return value if value.is_finite() else None


def _plain_number(value: Decimal) -> str:
    """O número sem zeros à direita: ``1400.0000`` vira ``1400`` e ``5.00`` vira ``5``."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


BREAKDOWN = "desdobramento"


REVISION = "revisao"


PACKAGE_RESOURCES = (BREAKDOWN, REVISION)


PARENT_LEVEL = 2


PACKAGE_LEVEL = 3


FIELD_RESOURCE = "recurso"


FIELD_ORIGIN = "origem"


FIELD_CHANGE = "sm"


FIELD_PACKAGE_KIND = "tipo"


FIELD_PARENT = "pai"


FIELD_CRITERION = "criterio"


FIELD_STAGE_MODEL = "modelo"


FIELD_UNIT = "unidade"


FIELD_QUANTITY = "quantidade"


FIELD_WEIGHT = "peso"


FIELD_START = "inicio"


FIELD_FINISH = "termino"


FIELD_COMPANY = "empresa"


FIELD_OWNER = "responsavel"


FIELD_EAC = "eac"


FIELD_DELIVERABLE = "entregavel"


FIELD_ACCEPTANCE = "aceitacao"


FIELD_PACKAGE = "pacote"


RESOURCE_MESSAGE = "Escolha a origem do peso."


PARENT_MESSAGE = "Escolha a subárea do pacote."


PACKAGE_KIND_MESSAGE = "Escolha o tipo do pacote."


CRITERION_MESSAGE = "Escolha o critério de medição."


STAGE_MODEL_MESSAGE = "Escolha o modelo de etapas."


UNIT_MESSAGE = "Escolha a unidade."


QUANTITY_MESSAGE = "Informe a quantidade da linha de base."


ORIGIN_MESSAGE = "Escolha o pacote de planejamento de origem."


BREAKDOWN_WEIGHT_MESSAGE = "O pacote de planejamento {code} só tem {weight}% de peso a desdobrar."


BREAKDOWN_JUSTIFICATION_MESSAGE = "Justifique o desdobramento (mínimo de 10 caracteres)."


CHANGE_MESSAGE = "Escolha uma SM aprovada com impacto em escopo ainda não incorporada à EAP."


REVISION_JUSTIFICATION_MESSAGE = "Justifique a revisão (mínimo de 10 caracteres)."


REVISION_PACKAGE_MESSAGE = "Escolha o pacote afetado."


REVISION_PACKAGE_NOT_FOUND_MESSAGE = "Pacote {code} não encontrado."


REVISION_QUANTITY_MESSAGE = "A nova quantidade não pode ser menor que o executado ({executed})."


REVISION_WEIGHT_MAX_MESSAGE = "O peso passa o máximo de {maximum}% por pacote."


REVISION_FINISH_MESSAGE = "O término não pode ser anterior ao início ({start})."


FINISH_MESSAGE = "O término não pode ser anterior ao início."


REVISION_FIXED_WEIGHT_MESSAGE = (
    "Os pesos alterados somam 100% ou mais; os demais pacotes ficariam sem peso."
)


@dataclass(frozen=True)
class PackageState:
    """O pacote existente como as regras da revisão o leem: o peso, o executado e as pontas."""

    code: str
    level: int
    kind: str
    criterion: str | None
    weight: Decimal
    quantity: Decimal | None = None
    executed: Decimal | None = None
    start: date | None = None
    finish: date | None = None


@dataclass(frozen=True)
class RevisionLimits:
    """Os parâmetros vigentes da EAP que a revisão respeita: os tetos de peso."""

    max_package_weight: Decimal
    max_estimated_weight: Decimal


@dataclass(frozen=True)
class RevisionAdjustment:
    """O ajuste de um pacote da revisão: o peso novo e, se mudarem, a quantidade e o término."""

    code: str
    weight: Decimal
    quantity: Decimal | None = None
    finish: date | None = None


@dataclass(frozen=True)
class RevisionData:
    """A revisão validada do formulário: a SM, a justificativa e o ajuste do pacote afetado."""

    change_code: str
    justification: str
    adjustment: RevisionAdjustment


@dataclass(frozen=True)
class NewPackageData:
    """O pacote novo validado: a origem do peso, o dicionário, as datas e as etapas do modelo."""

    resource: str
    parent_code: str
    description: str
    kind: str
    criterion: str | None
    model: str | None
    unit: str
    quantity: Decimal | None
    weight: Decimal
    start: date
    finish: date
    company_id: int | None
    owner_id: int
    eac_code: str | None
    deliverable: str
    acceptance: str
    justification: str
    source_code: str | None
    change_code: str | None
    steps: tuple[EapStep, ...] = ()


def parse_package_form(
    raw: Mapping[str, str],
    *,
    packages: Mapping[str, PackageState],
    limits: RevisionLimits,
    stage_models: Sequence[Mapping[str, Any]],
) -> NewPackageData:
    """O pacote novo do formulário, ou ``InvalidDataError`` com a mensagem de cada campo errado.

    O desdobramento sai de um pacote de planejamento existente: o pacote novo é de trabalho e
    não passa o peso da origem. A revisão entra por uma SM aprovada com impacto em escopo e
    aceita pacote de trabalho (com critério, modelo, unidade e quantidade) ou de planejamento.
    O peso acima do máximo do parâmetro tem precedência sobre o limite da origem.
    """
    from src.modulos.planejamento import calculations

    errors: dict[str, str] = {}
    resource = _resource(raw, errors)
    parent_code = _text(raw, FIELD_PARENT)
    parent = packages.get(parent_code)
    if parent is None or parent.level != PARENT_LEVEL:
        errors[FIELD_PARENT] = PARENT_MESSAGE
        parent_code = ""
    description = _package_description(raw, errors)
    kind = _package_kind(raw, resource, errors)
    weight = _decimal(_text(raw, FIELD_WEIGHT)) or ZERO
    weight_message = package_weight_error(weight, maximum=limits.max_package_weight)
    if weight_message:
        errors[FIELD_WEIGHT] = weight_message
    criterion = _package_criterion(raw, kind, errors)
    model, steps = _package_stages(raw, criterion, stage_models, errors)
    unit, quantity = _package_units(raw, criterion, errors)
    if criterion == calculations.CRITERION_ESTIMATED and weight > limits.max_estimated_weight:
        errors[FIELD_CRITERION] = ESTIMATED_WEIGHT_MESSAGE.format(
            maximum=_plain_number(limits.max_estimated_weight)
        )
    start = _required_date(raw, FIELD_START, label="o início da linha de base", errors=errors)
    finish = _required_date(raw, FIELD_FINISH, label="o término da linha de base", errors=errors)
    if date.min not in (start, finish) and finish < start:
        errors[FIELD_FINISH] = FINISH_MESSAGE
    owner_id = _required_id(raw, FIELD_OWNER, label="o responsável", errors=errors)
    company_id = _optional_id(raw, FIELD_COMPANY, label="a empresa", errors=errors)
    eac_code = _text(raw, FIELD_EAC) or None
    deliverable = _optional_text(
        raw, FIELD_DELIVERABLE, label="o entregável", limit=PACKAGE_TEXT_MAX, errors=errors
    )
    acceptance = _optional_text(
        raw,
        FIELD_ACCEPTANCE,
        label="o critério de aceitação",
        limit=PACKAGE_TEXT_MAX,
        errors=errors,
    )
    justification = _justification(
        raw,
        short_message=(
            BREAKDOWN_JUSTIFICATION_MESSAGE
            if resource == BREAKDOWN
            else REVISION_JUSTIFICATION_MESSAGE
        ),
        errors=errors,
    )
    source_code, change_code = _package_link(raw, resource, packages, weight, errors)
    if errors:
        raise InvalidDataError(errors)
    return NewPackageData(
        resource=resource,
        parent_code=parent_code,
        description=description,
        kind=kind,
        criterion=criterion,
        model=model,
        unit=unit,
        quantity=quantity,
        weight=weight,
        start=start,
        finish=finish,
        company_id=company_id,
        owner_id=owner_id,
        eac_code=eac_code,
        deliverable=deliverable,
        acceptance=acceptance,
        justification=justification,
        source_code=source_code,
        change_code=change_code,
        steps=steps,
    )


def parse_revision_form(
    raw: Mapping[str, str],
    *,
    packages: Mapping[str, PackageState],
    limits: RevisionLimits,
) -> RevisionData:
    """A revisão do formulário (um ajuste), ou ``InvalidDataError`` com a mensagem de cada campo.

    A SM aprovada com impacto em escopo e a justificativa abrem a revisão; o pacote é de nível
    3, o peso novo fica até o máximo do parâmetro, a quantidade (só em Unidades) não fica
    abaixo do executado e o término vazio mantém o da linha de base.
    """
    errors: dict[str, str] = {}
    change_code = _text(raw, FIELD_CHANGE)
    if not change_code:
        errors[FIELD_CHANGE] = CHANGE_MESSAGE
    justification = _justification(raw, short_message=REVISION_JUSTIFICATION_MESSAGE, errors=errors)
    package_code = _text(raw, FIELD_PACKAGE)
    package = _revision_package(package_code, packages, errors)
    weight = _decimal(_text(raw, FIELD_WEIGHT))
    weight_message = _revision_weight_error(weight, maximum=limits.max_package_weight)
    if weight_message:
        errors[FIELD_WEIGHT] = weight_message
    quantity = _revision_quantity(raw, package, errors)
    finish = _revision_finish(raw, package, errors)
    if errors:
        raise InvalidDataError(errors)
    return RevisionData(
        change_code=change_code,
        justification=justification,
        adjustment=RevisionAdjustment(
            code=package_code,
            weight=weight if weight is not None else ZERO,
            quantity=quantity,
            finish=finish,
        ),
    )


def revision_fixed_weight_error(total: Decimal) -> str | None:
    """A soma dos pesos alterados: 100 ou mais deixa os demais pacotes sem peso."""
    if total >= HUNDRED:
        return REVISION_FIXED_WEIGHT_MESSAGE
    return None


def _resource(raw: Mapping[str, str], errors: dict[str, str]) -> str:
    resource = _text(raw, FIELD_RESOURCE)
    if resource not in PACKAGE_RESOURCES:
        errors[FIELD_RESOURCE] = RESOURCE_MESSAGE
    return resource


def _package_kind(raw: Mapping[str, str], resource: str, errors: dict[str, str]) -> str:
    from src.modulos.planejamento import calculations

    if resource == BREAKDOWN:
        return calculations.WORK_PACKAGE
    kind = _text(raw, FIELD_PACKAGE_KIND)
    if kind not in (calculations.WORK_PACKAGE, calculations.PLANNING_PACKAGE):
        errors[FIELD_PACKAGE_KIND] = PACKAGE_KIND_MESSAGE
        return calculations.WORK_PACKAGE
    return kind


def _package_criterion(raw: Mapping[str, str], kind: str, errors: dict[str, str]) -> str | None:
    from src.modulos.planejamento import calculations

    if kind == calculations.PLANNING_PACKAGE:
        return None
    criterion = _text(raw, FIELD_CRITERION)
    if criterion not in calculations.EAP_CRITERIA:
        errors[FIELD_CRITERION] = CRITERION_MESSAGE
        return None
    return criterion


def _package_stages(
    raw: Mapping[str, str],
    criterion: str | None,
    stage_models: Sequence[Mapping[str, Any]],
    errors: dict[str, str],
) -> tuple[str | None, tuple[EapStep, ...]]:
    from src.modulos.planejamento import calculations

    if criterion != calculations.CRITERION_STEPS:
        return None, ()
    model = _text(raw, FIELD_STAGE_MODEL)
    chosen = next((item for item in stage_models if str(item.get("id", "")) == model), None)
    if chosen is None:
        errors[FIELD_STAGE_MODEL] = STAGE_MODEL_MESSAGE
        return None, ()
    return model, _stage_steps(chosen)


def _stage_steps(model: Mapping[str, Any]) -> tuple[EapStep, ...]:
    from src.modulos.planejamento.calculations import EapStep

    stages = model.get("etapas") or ()
    return tuple(
        EapStep(name=str(stage.get("nome", "")), weight=_stage_weight(stage.get("peso")))
        for stage in stages
    )


def _stage_weight(value: Any) -> Decimal:
    weight = _decimal(str(value))
    return weight if weight is not None else ZERO


def _package_units(
    raw: Mapping[str, str], criterion: str | None, errors: dict[str, str]
) -> tuple[str, Decimal | None]:
    from src.modulos.planejamento import calculations

    if criterion != calculations.CRITERION_UNITS:
        return "", None
    unit = _text(raw, FIELD_UNIT)
    if not unit:
        errors[FIELD_UNIT] = UNIT_MESSAGE
    quantity = _decimal(_text(raw, FIELD_QUANTITY))
    if quantity is None or quantity <= ZERO:
        errors[FIELD_QUANTITY] = QUANTITY_MESSAGE
    return unit, quantity


def _package_link(
    raw: Mapping[str, str],
    resource: str,
    packages: Mapping[str, PackageState],
    weight: Decimal,
    errors: dict[str, str],
) -> tuple[str | None, str | None]:
    from src.modulos.planejamento import calculations

    if resource == REVISION:
        change_code = _text(raw, FIELD_CHANGE)
        if not change_code:
            errors[FIELD_CHANGE] = CHANGE_MESSAGE
        return None, change_code or None
    if resource != BREAKDOWN:
        return None, None
    source_code = _text(raw, FIELD_ORIGIN)
    origin = packages.get(source_code)
    if origin is None or origin.kind != calculations.PLANNING_PACKAGE:
        errors[FIELD_ORIGIN] = ORIGIN_MESSAGE
        return None, None
    if weight > origin.weight and FIELD_WEIGHT not in errors:
        errors[FIELD_WEIGHT] = BREAKDOWN_WEIGHT_MESSAGE.format(
            code=origin.code, weight=_plain_number(origin.weight)
        )
    return source_code or None, None


def _justification(raw: Mapping[str, str], *, short_message: str, errors: dict[str, str]) -> str:
    value = _text(raw, FIELD_JUSTIFICATION)
    if len(value) < JUSTIFICATION_MIN_CHARACTERS:
        errors[FIELD_JUSTIFICATION] = short_message
    return value


def _required_id(raw: Mapping[str, str], field: str, *, label: str, errors: dict[str, str]) -> int:
    text = _text(raw, field)
    if not text:
        errors[field] = REQUIRED_MESSAGE.format(label=label)
        return 0
    found = parse_id(text)
    if found is None:
        errors[field] = UNKNOWN_CHOICE_MESSAGE.format(label=label)
        return 0
    return found


def _optional_id(
    raw: Mapping[str, str], field: str, *, label: str, errors: dict[str, str]
) -> int | None:
    text = _text(raw, field)
    if not text:
        return None
    found = parse_id(text)
    if found is None:
        errors[field] = UNKNOWN_CHOICE_MESSAGE.format(label=label)
        return None
    return found


def _revision_package(
    code: str, packages: Mapping[str, PackageState], errors: dict[str, str]
) -> PackageState | None:
    if not code:
        errors[FIELD_PACKAGE] = REVISION_PACKAGE_MESSAGE
        return None
    package = packages.get(code)
    if package is None or package.level != PACKAGE_LEVEL:
        errors[FIELD_PACKAGE] = REVISION_PACKAGE_NOT_FOUND_MESSAGE.format(code=code)
        return None
    return package


def _revision_weight_error(weight: Decimal | None, *, maximum: Decimal) -> str | None:
    if weight is None or weight <= ZERO:
        return PACKAGE_WEIGHT_ZERO_MESSAGE
    if weight > maximum:
        return REVISION_WEIGHT_MAX_MESSAGE.format(maximum=_plain_number(maximum))
    return None


def _revision_quantity(
    raw: Mapping[str, str], package: PackageState | None, errors: dict[str, str]
) -> Decimal | None:
    from src.modulos.planejamento import calculations

    text = _text(raw, FIELD_QUANTITY)
    if not text or package is None or package.criterion != calculations.CRITERION_UNITS:
        return None
    quantity = _decimal(text)
    executed = package.executed if package.executed is not None else ZERO
    if quantity is None or quantity < executed:
        errors[FIELD_QUANTITY] = REVISION_QUANTITY_MESSAGE.format(executed=_plain_number(executed))
        return None
    return quantity


def _revision_finish(
    raw: Mapping[str, str], package: PackageState | None, errors: dict[str, str]
) -> date | None:
    text = _text(raw, FIELD_FINISH)
    if not text:
        return None
    try:
        finish = date.fromisoformat(text)
    except ValueError:
        errors[FIELD_FINISH] = INVALID_DATE_MESSAGE.format(label="o término")
        return None
    if package is not None and package.start is not None and finish < package.start:
        errors[FIELD_FINISH] = REVISION_FINISH_MESSAGE.format(start=f"{package.start:%d/%m/%Y}")
    return finish
