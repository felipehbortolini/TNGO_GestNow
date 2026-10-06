"""Input validation for the Central actions module (ISSUE-019).

The shapes the facade receives (a new action, a replan, a completion) and the checks of what
a person types: the filters of the list, the dates and the justification. The checks are pure
and return the message of the field, or ``None`` when the value holds up; the facade turns the
messages into one ``InvalidDataError``, so the rule holds for the route and for any module that
calls the facade.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
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


# ── The minutes (ISSUE-021) ──────────────────────────────────────────────────────────────────

MEETING_TYPES: tuple[str, ...] = (
    "Coordenação de obra",
    "Licenciamento",
    "Status com o cliente",
    "Segurança",
    "Planejamento",
    "Kickoff",
    "Reunião de acompanhamento",
)
MAX_SUBJECT_LENGTH = 150
MAX_BOARD_LENGTH = 100
MINUTES_PAGE_SIZE = 15

MINUTES_DATE_REQUIRED = "Informe a data da reunião."
MEETING_TYPE_REQUIRED = "Escolha o tipo de reunião."
BOARD_REQUIRED = "Informe a diretoria."
BOARD_TOO_LONG = f"A diretoria aceita até {MAX_BOARD_LENGTH} caracteres."
UNIT_REQUIRED = "Escolha a unidade."
PREPARED_BY_REQUIRED = "Escolha quem elaborou a ata."
MINUTES_SUBJECT_REQUIRED = "Informe o assunto da ata."
MINUTES_SUBJECT_TOO_LONG = f"O assunto aceita até {MAX_SUBJECT_LENGTH} caracteres."


@dataclass(frozen=True)
class NewMinutes:
    """What a person fills to generate a minutes; ``number``, ``revision`` and ``participant_ids`` are for the load.

    A new minutes takes its number from the sequence of the project and starts with its author
    in the attendance list; the load of the demonstration hands the number and the attendance
    the prototype had.
    """

    project_id: int
    meeting_date: date | None
    meeting_type: str
    board: str
    unit_id: int | None
    prepared_by_id: int | None
    subject: str
    company_ids: tuple[int, ...] = ()
    main_company_id: int | None = None
    number: str | None = None
    revision: int = 0
    participant_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class MinutesFilters:
    """The filters of the list of minutes: free search and the page."""

    search: str = ""
    page: int = 1


@dataclass(frozen=True)
class CompaniesRequest:
    """The executing companies of a minutes: the main one, the others and the version opened."""

    minutes_id: int
    main_company_id: int | None
    company_ids: tuple[int, ...]
    version: int | str | None


@dataclass(frozen=True)
class AttendanceRequest:
    """A change of the attendance list: the people and the version the screen opened."""

    minutes_id: int
    person_ids: tuple[int, ...]
    version: int | str | None


def parse_ids(raw_values: Sequence[str]) -> tuple[int, ...]:
    """The ids a multiple field sent, without repeats and without what is not a number."""
    parsed = (parse_id(raw) for raw in raw_values)
    return tuple(dict.fromkeys(item for item in parsed if item is not None))


def minutes_problems(new: NewMinutes) -> dict[str, str]:
    """The messages of a new minutes by field; empty when it may be generated (HU-051)."""
    problems: dict[str, str] = {}
    if new.meeting_date is None:
        problems["data"] = MINUTES_DATE_REQUIRED
    if new.meeting_type not in MEETING_TYPES:
        problems["tipo_reuniao"] = MEETING_TYPE_REQUIRED
    board = new.board.strip()
    if not board:
        problems["diretoria"] = BOARD_REQUIRED
    elif len(board) > MAX_BOARD_LENGTH:
        problems["diretoria"] = BOARD_TOO_LONG
    if new.unit_id is None:
        problems["unidade"] = UNIT_REQUIRED
    if new.prepared_by_id is None:
        problems["elaborado_por"] = PREPARED_BY_REQUIRED
    subject = new.subject.strip()
    if not subject:
        problems["assunto"] = MINUTES_SUBJECT_REQUIRED
    elif len(subject) > MAX_SUBJECT_LENGTH:
        problems["assunto"] = MINUTES_SUBJECT_TOO_LONG
    return problems


def parse_minutes_filters(params: Mapping[str, str]) -> MinutesFilters:
    """The search and the page of the list of minutes from the query string."""
    return MinutesFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH_LENGTH], page=parse_page(params)
    )


# ── The items of the minutes (ISSUE-022) ─────────────────────────────────────────────────────


MAX_GROUP_LENGTH = 100
MAX_ITEM_DESCRIPTION_LENGTH = 500

ITEM_KIND_REQUIRED = "Informe se é uma anotação ou uma ação."
ITEM_GROUP_REQUIRED = "Informe o grupo / área."
ITEM_GROUP_TOO_LONG = f"O grupo aceita até {MAX_GROUP_LENGTH} caracteres."
ITEM_SUBJECT_REQUIRED = "Informe o assunto."
ITEM_SUBJECT_TOO_LONG = f"O assunto aceita até {MAX_SUBJECT_LENGTH} caracteres."
ITEM_DESCRIPTION_REQUIRED = "Informe a descrição."
ITEM_DESCRIPTION_TOO_LONG = f"A descrição aceita até {MAX_ITEM_DESCRIPTION_LENGTH} caracteres."
ITEM_REQUESTER_REQUIRED = "Escolha o solicitante."
ITEM_RESPONSIBLE_REQUIRED = "Escolha o responsável."
ITEM_PERSON_NOT_ATTENDING = "A pessoa precisa estar na lista de presença desta ata."
ITEM_PLANNED_REQUIRED = "Informe a data prevista da ação."
ITEM_COMPLETION_ONLY_FOR_ACTION = "Só uma ação tem data de conclusão."
ITEM_COMPLETION_IN_THE_FUTURE = "A data de conclusão não pode ser posterior à data de referência."
REVISION_BEFORE_CURRENT = "A data não pode ser anterior à revisão atual."


@dataclass(frozen=True)
class ItemInput:
    """An annotation or action of the minutes, as the form sends it."""

    kind: str
    group: str
    subject: str
    description: str
    requester_id: int | None
    responsible_id: int | None
    planned_date: date | None
    completed_on: date | None
    version: int | str | None = None


@dataclass(frozen=True)
class RevisionInput:
    """A new revision of the minutes: the date of the meeting and the version the screen opened."""

    meeting_date: date | None
    version: int | str | None


def parse_item(form: Mapping[str, str]) -> ItemInput:
    """The item the form sends: kind, group, texts, the two people and the two dates."""
    return ItemInput(
        kind=(form.get("tipo") or "").strip(),
        group=(form.get("grupo") or "").strip(),
        subject=(form.get("assunto") or "").strip(),
        description=(form.get("descricao") or "").strip(),
        requester_id=parse_id(form.get("solicitante")),
        responsible_id=parse_id(form.get("responsavel")),
        planned_date=parse_date(form.get("prevista")),
        completed_on=parse_date(form.get("conclusao")),
        version=form.get("versao"),
    )


def parse_revision(form: Mapping[str, str]) -> RevisionInput:
    """The new revision the form sends: the date of the meeting."""
    return RevisionInput(meeting_date=parse_date(form.get("data")), version=form.get("versao"))


def item_problems(
    data: ItemInput, *, participant_ids: Collection[int], reference_date: date
) -> dict[str, str]:
    """The messages of an item by field; empty when it may be saved (HU-052)."""
    problems: dict[str, str] = {}
    if data.kind not in KINDS:
        problems["tipo"] = ITEM_KIND_REQUIRED
    problems.update(_item_text_problems(data))
    problems.update(_item_people_problems(data, participant_ids))
    if data.kind == ACTION and data.planned_date is None:
        problems["prevista"] = ITEM_PLANNED_REQUIRED
    if data.completed_on is not None:
        if data.kind != ACTION:
            problems["conclusao"] = ITEM_COMPLETION_ONLY_FOR_ACTION
        elif data.completed_on > reference_date:
            problems["conclusao"] = ITEM_COMPLETION_IN_THE_FUTURE
    return problems


def _item_text_problems(data: ItemInput) -> dict[str, str]:
    problems: dict[str, str] = {}
    checks = (
        ("grupo", data.group.strip(), MAX_GROUP_LENGTH, ITEM_GROUP_REQUIRED, ITEM_GROUP_TOO_LONG),
        (
            "assunto",
            data.subject,
            MAX_SUBJECT_LENGTH,
            ITEM_SUBJECT_REQUIRED,
            ITEM_SUBJECT_TOO_LONG,
        ),
        (
            "descricao",
            data.description,
            MAX_ITEM_DESCRIPTION_LENGTH,
            ITEM_DESCRIPTION_REQUIRED,
            ITEM_DESCRIPTION_TOO_LONG,
        ),
    )
    for field, text, maximum, required_message, too_long_message in checks:
        if not text:
            problems[field] = required_message
        elif len(text) > maximum:
            problems[field] = too_long_message
    return problems


def _item_people_problems(data: ItemInput, participant_ids: Collection[int]) -> dict[str, str]:
    problems: dict[str, str] = {}
    checks = (
        ("solicitante", data.requester_id, ITEM_REQUESTER_REQUIRED),
        ("responsavel", data.responsible_id, ITEM_RESPONSIBLE_REQUIRED),
    )
    for field, person_id, required_message in checks:
        if person_id is None:
            problems[field] = required_message
        elif person_id not in participant_ids:
            problems[field] = ITEM_PERSON_NOT_ATTENDING
    return problems


def revision_problems(data: RevisionInput, *, current_date: date) -> dict[str, str]:
    """The messages of a new revision: the date is required, never before the current one."""
    problems: dict[str, str] = {}
    if data.meeting_date is None:
        problems["data"] = MINUTES_DATE_REQUIRED
    elif data.meeting_date < current_date:
        problems["data"] = REVISION_BEFORE_CURRENT
    return problems
