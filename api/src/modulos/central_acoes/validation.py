"""Input validation for the Central actions module (ISSUE-019).

The shapes the facade receives (a new action, a replan, a completion) and the checks of what
a person types: the filters of the list, the dates and the justification. The checks are pure
and return the message of the field, or ``None`` when the value holds up; the facade turns the
messages into one ``InvalidDataError``, so the rule holds for the route and for any module that
calls the facade.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from src.modulos.central_acoes.calculations import ACTION, INFORMATION, StatusFilter
from src.modulos.central_acoes.origins import ORIGINS

MIN_JUSTIFICATION_LENGTH = 10
MAX_JUSTIFICATION_LENGTH = 300
MAX_SEARCH_LENGTH = 120
MAX_ID_DIGITS = 18

LIST_VIEW = "lista"
KANBAN_VIEW = "kanban"
VIEWS = (LIST_VIEW, KANBAN_VIEW)

KINDS = (ACTION, INFORMATION)

JUSTIFICATION_REQUIRED = "Informe a justificativa do replanejamento."
JUSTIFICATION_TOO_SHORT = (
    f"Detalhe a justificativa (mínimo de {MIN_JUSTIFICATION_LENGTH} caracteres)."
)
JUSTIFICATION_TOO_LONG = f"A justificativa aceita até {MAX_JUSTIFICATION_LENGTH} caracteres."
NEW_DATE_REQUIRED = "Informe a nova data."
NEW_DATE_IN_THE_PAST = "A nova data não pode ser anterior à data de referência."
INVALID_DATE = "Informe uma data válida."
COMPLETION_DATE_REQUIRED = "Informe a data de conclusão."
COMPLETION_IN_THE_FUTURE = "A data de conclusão não pode ser posterior à data de referência."
NEW_DATE_UNCHANGED = "Informe uma data diferente do prazo vigente."
PAGE_SIZE = 15


@dataclass(frozen=True)
class ReplanEntry:
    """One replan already made: when it was registered, the two dates, who and why.

    Only the load of the demonstration and a migration of old data hand these to the seam of
    creation (``NewAction.replans``); a replan of a living action goes by ``ReplanRequest``.
    """

    author_id: int
    registered_on: date
    from_date: date
    to_date: date
    justification: str


@dataclass(frozen=True)
class NewAction:
    """What a module hands to the single seam of creation: the origin, its reference and the item.

    ``kind`` is ``Ação`` or ``Informação`` (the annotation of the minutes); only an action needs
    ``planned_date``. ``origin_ref`` is the code of the record of origin (the number of the ata,
    the code of the risk); ``ata_id`` is the minutes' own id when the origin is an Ata.
    ``completed_on`` and ``replans`` are for a record that already has a history (the load of
    the demonstration, an import of old data); a module that opens a new action leaves them out.
    """

    project_id: int
    origin: str
    origin_ref: str
    subject: str
    requester_id: int
    responsible_id: int
    planned_date: date | None
    kind: str = ACTION
    description: str | None = None
    group: str | None = None
    item: str | None = None
    ata_id: int | None = None
    contributes_probability: bool = False
    contributes_impact: bool = False
    completed_on: date | None = None
    replans: tuple[ReplanEntry, ...] = ()


@dataclass(frozen=True)
class ReplanRequest:
    """A replan: the action, the new date, the justification and the version the screen opened."""

    action_id: int
    new_date: date | None
    justification: str
    version: int | str | None


@dataclass(frozen=True)
class CompletionRequest:
    """A completion: the action, the completion date and the version the screen opened."""

    action_id: int
    completed_on: date | None
    version: int | str | None


@dataclass(frozen=True)
class ActionFilters:
    """The filters of the list: free search, origin, status, responsible and the page."""

    search: str = ""
    origin: str = ""
    status: StatusFilter = StatusFilter.OPEN
    responsible_id: int | None = None
    page: int = 1


def parse_id(raw: str | None) -> int | None:
    """An id typed or sent by a screen: digits only, never absurdly long, or ``None``."""
    text = (raw or "").strip()
    if not text.isascii() or not text.isdigit() or len(text) > MAX_ID_DIGITS:
        return None
    return int(text)


def parse_date(raw: str | None) -> date | None:
    """A date as the date field sends it (``2026-09-25``), or ``None`` when empty or invalid."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_filters(params: Mapping[str, str]) -> ActionFilters:
    """The filters of the list from the query string; a value that means nothing is ignored."""
    origin = (params.get("origem") or "").strip()
    try:
        status = StatusFilter((params.get("status") or "").strip() or StatusFilter.OPEN)
    except ValueError:
        status = StatusFilter.OPEN
    return ActionFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH_LENGTH],
        origin=origin if origin in ORIGINS else "",
        status=status,
        responsible_id=parse_id(params.get("responsavel")),
        page=parse_page(params),
    )


def parse_view(params: Mapping[str, str]) -> str:
    """The way the list is shown, ``lista`` or ``kanban``; anything else is the list."""
    chosen = (params.get("visao") or "").strip()
    return chosen if chosen in VIEWS else LIST_VIEW


def justification_problem(justification: str) -> str | None:
    """The message for the justification field, or ``None`` when it holds up (HU-053)."""
    size = len(justification.strip())
    if size == 0:
        return JUSTIFICATION_REQUIRED
    if size < MIN_JUSTIFICATION_LENGTH:
        return JUSTIFICATION_TOO_SHORT
    if size > MAX_JUSTIFICATION_LENGTH:
        return JUSTIFICATION_TOO_LONG
    return None


def new_date_problem(new_date: date | None, reference_date: date) -> str | None:
    """The message for the new date of a replan: required and not before the reference date."""
    if new_date is None:
        return NEW_DATE_REQUIRED
    if new_date < reference_date:
        return NEW_DATE_IN_THE_PAST
    return None


def parse_page(params: Mapping[str, str]) -> int:
    """The page of the list, starting at 1; anything that is not a positive number is page 1."""
    parsed = parse_id(params.get("pagina"))
    return parsed if parsed else 1


def completion_problem(completed_on: date | None, reference_date: date) -> str | None:
    """The message for the completion date: required and not after the reference date."""
    if completed_on is None:
        return COMPLETION_DATE_REQUIRED
    if completed_on > reference_date:
        return COMPLETION_IN_THE_FUTURE
    return None


def replan_problems(
    request: ReplanRequest, *, current_due: date | None, reference_date: date
) -> dict[str, str]:
    """The messages of a replan by field: the new date and the justification (HU-053)."""
    problems: dict[str, str] = {}
    date_message = new_date_problem(request.new_date, reference_date)
    if date_message is None and request.new_date == current_due:
        date_message = NEW_DATE_UNCHANGED
    if date_message is not None:
        problems["data"] = date_message
    justification_message = justification_problem(request.justification)
    if justification_message is not None:
        problems["justificativa"] = justification_message
    return problems


def new_action_problems(new: NewAction) -> dict[str, str]:
    """The messages of a new action, by field; empty when the action may be created."""
    problems: dict[str, str] = {}
    if new.origin not in ORIGINS:
        problems["origem"] = "Informe uma origem válida."
    if not new.origin_ref.strip():
        problems["origem_ref"] = "Informe a referência do registro de origem."
    if new.kind not in KINDS:
        problems["tipo"] = "Informe se é uma ação ou uma informação."
    if not new.subject.strip():
        problems["assunto"] = "Informe o assunto."
    if new.kind == ACTION and new.planned_date is None:
        problems["data_prevista"] = "Informe a data prevista."
    problems.update(_history_problems(new))
    return problems


def _history_problems(new: NewAction) -> dict[str, str]:
    """The messages about the history a record arrives with: completion and replans."""
    problems: dict[str, str] = {}
    if new.completed_on is not None and new.kind != ACTION:
        problems["data_conclusao"] = "Só uma ação tem data de conclusão."
    if any(justification_problem(entry.justification) for entry in new.replans):
        problems["replanejamentos"] = "Todo replanejamento precisa da justificativa."
    return problems
