"""Input validation of the Quality module: the shapes and the checks of the RNC (ISSUE-068).

The checks are pure and return one message per field, in a dict that is empty when everything
holds up; the facade turns it into one ``InvalidDataError`` (422), so the rule holds for the
route and for any module that calls the facade. The messages and the minimum lengths are the
ones of the prototype (``js/services/api.js``, the RNC block). The vocabulary lives in
``calculations`` and is reexported here for the screens.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from src.modulos.qualidade.calculations import (
    DISPOSITIONS,
    DISPOSITIONS_WITH_CONCESSION,
    METHODS,
    ORIGINS,
    SEVERITIES,
    SITUATIONS,
)

SITUATION_ACTIVE = "ativas"
SITUATION_OVERDUE = "vencidas"
SITUATION_ALL = "todas"

MIN_IDENTIFICATION = 15
MIN_CONTAINMENT = 10
MIN_CAUSE = 15
MIN_CONCESSION = 5
MIN_EFFECT_TEXT = 15
MIN_LESSON_TITLE = 10
MIN_LESSON_RECOMMENDATION = 15
MIN_REASON = 10
MIN_JUSTIFICATION = 10
MAX_TEXT = 600
MAX_CAUSE = 800
MAX_CONTAINMENT = 400
MAX_REFERENCE = 120
MAX_REASON = 300
MAX_JUSTIFICATION = 300
MAX_LESSON_TITLE = 120
MAX_LESSON_RECOMMENDATION = 500
MAX_SEARCH = 120
MAX_ACTIONS = 8
PAGE_SIZE = 20
MAX_ID_DIGITS = 18
CENTS = Decimal(100)

CHOOSE_PROJECT = "Escolha o projeto da RNC."
DATE_REQUIRED = "Informe a data da constatação."
DATE_FUTURE = "A data não pode ser posterior à referência."
CHOOSE_ORIGIN = "Escolha a origem."
CHOOSE_DISCIPLINE = "Escolha a disciplina."
CHOOSE_COMPANY = "Escolha a empresa responsável."
DESCRIPTION_SHORT = (
    "Descreva a não conformidade (mínimo de 15 caracteres): o que, onde e o requisito não atendido."
)
CHOOSE_SEVERITY = "Escolha a severidade."
CONTAINMENT_SHORT = (
    "Registre a contenção imediata (mínimo de 10 caracteres): bloqueio, segregação ou suspensão."
)
CHOOSE_RESPONSIBLE = "Escolha o responsável pela análise de causa."
CHOOSE_METHOD = "Escolha o método de análise."
CAUSE_SHORT = "Descreva a causa raiz (mínimo de 15 caracteres)."
CHOOSE_DISPOSITION = "Escolha a disposição do produto não conforme."
CONCESSION_REFERENCE_REQUIRED = (
    "Reparo e Usar como está exigem a concessão do cliente: informe o documento."
)
CONCESSION_DATE_REQUIRED = "Informe a data da concessão."
COST_NEGATIVE = "O custo da não qualidade não pode ser negativo."
ACTIONS_REQUIRED = "Inclua ao menos uma ação corretiva (elimina a causa raiz)."
ACTION_SUBJECT_REQUIRED = "Ação {position}: informe o assunto."
ACTION_RESPONSIBLE_REQUIRED = "Ação {position}: escolha o responsável."
ACTION_DATE_REQUIRED = "Ação {position}: informe a data prevista."
ACTION_DATE_PAST = "Ação {position}: a data prevista não pode ser anterior à referência."
EFFECTIVE_REQUIRED = "Informe se a ação foi eficaz."
EFFECT_TEXT_SHORT = "Descreva a evidência da verificação (mínimo de 15 caracteres)."
CHECK_DATE_REQUIRED = "Informe a data da verificação."
CHECK_DATE_FUTURE = "A data não pode ser posterior à referência."
CHECK_DATE_BEFORE = "A data não pode ser anterior à abertura."
LESSON_TITLE_SHORT = "Informe o título da lição (mínimo de 10 caracteres)."
LESSON_RECOMMENDATION_SHORT = "Informe a recomendação da lição (mínimo de 15 caracteres)."
REASON_SHORT = "Informe o motivo do cancelamento (mínimo de 10 caracteres)."
COST_REQUIRED = "Informe o custo (zero ou mais)."
JUSTIFICATION_SHORT = "Informe a composição do custo (mínimo de 10 caracteres)."


@dataclass(frozen=True)
class RncFilters:
    """The filters of the list: what the query string of the screen says."""

    search: str = ""
    situation: str = SITUATION_ACTIVE
    severity: str = ""
    discipline: str = ""
    origin: str = ""
    company_id: int | None = None
    page: int = 1


@dataclass(frozen=True)
class OpeningInput:
    """What the form of a new RNC sends: the identification, the containment and the evidence."""

    project_id: int | None
    rnc_date: date | None
    origin: str
    origin_ref: str
    discipline: str
    company_id: int | None
    severity: str
    description: str
    containment: str
    version: int | str | None = None


@dataclass(frozen=True)
class ResponsibleInput:
    """What the analysis assignment sends: who answers for the root cause analysis."""

    responsible_id: int | None
    version: int | str | None = None


@dataclass(frozen=True)
class ActionInput:
    """One corrective action of the RNC: it goes to the Central with origin RNC."""

    subject: str
    responsible_id: int | None
    planned_date: date | None
    description: str = ""


@dataclass(frozen=True)
class AnalysisInput:
    """What the analysis form sends: method, root cause, disposition, concession, cost and actions."""

    method: str
    root_cause: str
    disposition: str
    actions: tuple[ActionInput, ...]
    concession_reference: str = ""
    concession_date: date | None = None
    cost_cents: int = 0
    version: int | str | None = None


@dataclass(frozen=True)
class VerificationInput:
    """What the effectiveness verification sends: the result, the evidence and the optional lesson."""

    effective: bool | None
    text: str
    checked_on: date | None
    register_lesson: bool = False
    lesson_title: str = ""
    lesson_recommendation: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class CancellationInput:
    """What the cancellation sends: the reason and the version the screen opened."""

    reason: str
    version: int | str | None = None


@dataclass(frozen=True)
class CostInput:
    """What the cost update sends: the apured cost and its composition."""

    cost_cents: int | None
    justification: str
    version: int | str | None = None


def opening_problems(
    data: OpeningInput,
    *,
    reference_date: date,
    discipline_names: Sequence[str],
    project_known: bool,
    company_known: bool,
) -> dict[str, str]:
    """One message per field of the opening that does not hold up (the prototype's rules)."""
    problems: dict[str, str] = {}
    if data.project_id is None or not project_known:
        problems["projeto"] = CHOOSE_PROJECT
    if data.rnc_date is None:
        problems["data"] = DATE_REQUIRED
    elif data.rnc_date > reference_date:
        problems["data"] = DATE_FUTURE
    if data.origin not in ORIGINS:
        problems["origem"] = CHOOSE_ORIGIN
    if data.discipline not in discipline_names:
        problems["disciplina"] = CHOOSE_DISCIPLINE
    if data.company_id is None or not company_known:
        problems["empresaId"] = CHOOSE_COMPANY
    if len((data.description or "").strip()) < MIN_IDENTIFICATION:
        problems["descricao"] = DESCRIPTION_SHORT
    if data.severity not in SEVERITIES:
        problems["severidade"] = CHOOSE_SEVERITY
    if len((data.containment or "").strip()) < MIN_CONTAINMENT:
        problems["contencao"] = CONTAINMENT_SHORT
    return problems


def responsible_problems(data: ResponsibleInput, *, person_known: bool) -> dict[str, str]:
    """The analysis assignment needs a person of the register."""
    if data.responsible_id is None or not person_known:
        return {"responsavelId": CHOOSE_RESPONSIBLE}
    return {}


def analysis_problems(
    data: AnalysisInput,
    *,
    reference_date: date,
    people_known: Mapping[int, object],
) -> dict[str, str]:
    """One message per field of the analysis that does not hold up, actions included."""
    problems: dict[str, str] = {}
    if data.method not in METHODS:
        problems["metodo"] = CHOOSE_METHOD
    if len((data.root_cause or "").strip()) < MIN_CAUSE:
        problems["causaRaiz"] = CAUSE_SHORT
    if data.disposition not in DISPOSITIONS:
        problems["disposicao"] = CHOOSE_DISPOSITION
    requires_concession = data.disposition in DISPOSITIONS_WITH_CONCESSION
    if requires_concession and len((data.concession_reference or "").strip()) < MIN_CONCESSION:
        problems["concessaoReferencia"] = CONCESSION_REFERENCE_REQUIRED
    if requires_concession and data.concession_date is None:
        problems["concessaoData"] = CONCESSION_DATE_REQUIRED
    if data.cost_cents < 0:
        problems["custoCentavos"] = COST_NEGATIVE
    if not data.actions:
        problems["acoes"] = ACTIONS_REQUIRED
    problems.update(
        actions_problems(data.actions, reference_date=reference_date, people_known=people_known)
    )
    return problems


def actions_problems(
    actions: Sequence[ActionInput],
    *,
    reference_date: date,
    people_known: Mapping[int, object],
) -> dict[str, str]:
    """One message per action that does not hold up, numbered as the prototype did."""
    problems: dict[str, str] = {}
    for position, action in enumerate(actions, start=1):
        if not (action.subject or "").strip():
            problems.setdefault("acoes", ACTION_SUBJECT_REQUIRED.format(position=position))
        if action.responsible_id is None or action.responsible_id not in people_known:
            problems.setdefault("acoes", ACTION_RESPONSIBLE_REQUIRED.format(position=position))
        if action.planned_date is None:
            problems.setdefault("acoes", ACTION_DATE_REQUIRED.format(position=position))
        elif action.planned_date < reference_date:
            problems.setdefault("acoes", ACTION_DATE_PAST.format(position=position))
    return problems


def verification_problems(
    data: VerificationInput, *, reference_date: date, opened_on: date
) -> dict[str, str]:
    """One message per field of the effectiveness verification that does not hold up."""
    problems: dict[str, str] = {}
    if data.effective is None:
        problems["eficaz"] = EFFECTIVE_REQUIRED
    if len((data.text or "").strip()) < MIN_EFFECT_TEXT:
        problems["texto"] = EFFECT_TEXT_SHORT
    if data.checked_on is None:
        problems["data"] = CHECK_DATE_REQUIRED
    elif data.checked_on > reference_date:
        problems["data"] = CHECK_DATE_FUTURE
    elif data.checked_on < opened_on:
        problems["data"] = CHECK_DATE_BEFORE
    if data.effective and data.register_lesson:
        if len((data.lesson_title or "").strip()) < MIN_LESSON_TITLE:
            problems["licaoTitulo"] = LESSON_TITLE_SHORT
        if len((data.lesson_recommendation or "").strip()) < MIN_LESSON_RECOMMENDATION:
            problems["licaoRecomendacao"] = LESSON_RECOMMENDATION_SHORT
    return problems


def cancellation_problems(data: CancellationInput) -> dict[str, str]:
    """The cancellation needs a reason (minimum of 10 characters)."""
    if len((data.reason or "").strip()) < MIN_REASON:
        return {"motivo": REASON_SHORT}
    return {}


def cost_problems(data: CostInput) -> dict[str, str]:
    """The cost update needs a value of zero or more and its composition."""
    if data.cost_cents is None or data.cost_cents < 0:
        return {"custoCentavos": COST_REQUIRED}
    if len((data.justification or "").strip()) < MIN_JUSTIFICATION:
        return {"justificativa": JUSTIFICATION_SHORT}
    return {}


def parse_id(raw: str | None) -> int | None:
    """A positive whole number from the request, or ``None`` when it is not one."""
    text = (raw or "").strip()
    if not text.isdigit() or len(text) > MAX_ID_DIGITS or int(text) < 1:
        return None
    return int(text)


def parse_date(raw: str | None) -> date | None:
    """A date written ``2026-09-25``, or ``None`` when it is empty or not a real date."""
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


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


def reais_text(cents: int) -> str:
    """Cents as the form shows them (``34.000,00``), without the currency symbol."""
    reais, centavos = divmod(cents, 100)
    whole = f"{reais:,}".replace(",", ".")
    return f"{whole},{centavos:02d}"


def parse_filters(params: Mapping[str, str]) -> RncFilters:
    """Read the filters of the list from the query string; an invalid value is ignored."""
    situation = (params.get("situacao") or SITUATION_ACTIVE).strip()
    severity = (params.get("severidade") or "").strip()
    origin = (params.get("origem") or "").strip()
    return RncFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH],
        situation=situation
        if situation in (*SITUATIONS, SITUATION_ACTIVE, SITUATION_OVERDUE, SITUATION_ALL)
        else SITUATION_ACTIVE,
        severity=severity if severity in SEVERITIES else "",
        discipline=(params.get("disciplina") or "").strip(),
        origin=origin if origin in ORIGINS else "",
        company_id=parse_id(params.get("empresa")),
        page=parse_id(params.get("pagina")) or 1,
    )
