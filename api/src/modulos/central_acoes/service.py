"""Business facade of the Central de Ações: the single seam of action (D9, D6, ISSUE-019).

Every module that generates an action calls ``create_action`` with the origin and the
reference of its own record; nothing else writes the table ``acao``. The status is never
stored: every query calculates it with the reference date the caller hands in
(``calculations.action_status``). Replanning needs a justification, which is kept in the
history of the action; completing needs the completion date. Both tell the module of the
origin by its registered reaction (``origins.register_reaction``), inside the same
transaction, so either both records change or none does.

Public API (stable; a change needs an issue of its own, a new field comes with a default):

* ``create_action(session, *, user, new, reference_date) -> ActionRecord``: the seam of creation;
* ``replan_action(session, *, user, request, reference_date) -> ActionRecord``;
* ``complete_action(session, *, user, request, reference_date) -> ActionRecord``;
* ``close_from_origin(session, *, user, origin, completed_on, reference_date)`` and
  ``reopen_from_origin(session, *, user, origin, reference_date)``, where ``origin`` is an
  ``origin_links.OriginRef(kind, reference)``: the origin closed or reopened a record on its own
  screen, the Central follows;
* ``find_action``, ``list_actions``, ``replan_history``, ``count_by_status`` and
  ``count_actions_of_origin``: reading.

Nothing here reads the clock: the routes obtain the date from ``core.calendario``. A module
never reads the table ``acao``; it uses the functions above.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import attachment_origins, audit, origin_links, rbac, recording
from src.core.attachment_origins import OriginRecord, OriginType
from src.core.errors import InvalidDataError
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import calculations, origins, validation
from src.modulos.central_acoes.calculations import (
    ACTION,
    ActionDates,
    ActionStatus,
    StatusCounts,
    StatusFilter,
)
from src.modulos.central_acoes.models import Action, ActionReplan
from src.modulos.central_acoes.origins import ActionEvent
from src.modulos.central_acoes.validation import (
    ActionFilters,
    CompletionRequest,
    NewAction,
    ReplanEntry,
    ReplanRequest,
)
from src.modulos.configuracoes import service as configuracoes

MODULE = "central_acoes"
ATTACHMENT_TABLE = "acao"

NOT_FOUND_MESSAGE = "Ação não encontrada."
NOT_AN_ACTION_MESSAGE = "Uma informação da ata não é replanejada nem concluída."
TREATED_AT_SOURCE_MESSAGE = (
    "Esta ação é tratada no registro de origem: replaneje ou conclua por lá."
)
ALREADY_COMPLETED_MESSAGE = "Esta ação já está concluída."
UNKNOWN_PROJECT_MESSAGE = "O projeto informado não existe."
UNKNOWN_PERSON_MESSAGE = "A pessoa informada não está no cadastro."
UNKNOWN_PERSON_NAME = "Pessoa removida do cadastro"


@dataclass(frozen=True)
class ActionRecord:
    """One action as the screens and the other modules read it: the columns and the status."""

    id: int
    project_id: int
    origin: str
    origin_ref: str | None
    item: str | None
    group: str | None
    kind: str
    subject: str
    description: str | None
    requester_id: int
    responsible_id: int
    planned_date: date | None
    replanned_date: date | None
    completed_on: date | None
    ata_id: int | None
    contributes_probability: bool
    contributes_impact: bool
    version: int
    status: ActionStatus
    days_overdue: int

    @property
    def due_date(self) -> date | None:
        """The deadline in force: the replanned date, or the planned one when never replanned."""
        return calculations.effective_due_date(self.planned_date, self.replanned_date)

    @property
    def status_label(self) -> str:
        """The status as the screen writes it (``Em andamento``)."""
        return calculations.STATUS_LABELS[self.status]


@dataclass(frozen=True)
class ActionRow:
    """One line of the list or one card of the kanban: the action with what is printed around it."""

    record: ActionRecord
    requester_name: str
    responsible_name: str
    project_label: str
    link: origin_links.OriginLink
    replan_count: int

    @property
    def treated_at_source(self) -> bool:
        """Whether replanning and completing happen in the module of the origin (Punch list)."""
        return self.record.origin in origins.TREATED_AT_SOURCE

    @property
    def can_change(self) -> bool:
        """Whether the action is open and treated here, so it may be replanned or completed."""
        is_open = self.record.status in (ActionStatus.IN_PROGRESS, ActionStatus.OVERDUE)
        return is_open and not self.treated_at_source


@dataclass(frozen=True)
class ResponsibleOption:
    """A person who is responsible for at least one action of the scope: a choice of the filter."""

    id: int
    name: str


@dataclass(frozen=True)
class ActionListing:
    """What the screen Ações shows for a filter: the KPIs, the list and what the kanban shows."""

    counts: StatusCounts
    due_by_reference: int
    universe: int
    rows: tuple[ActionRow, ...]
    board: tuple[ActionRow, ...]
    responsibles: tuple[ResponsibleOption, ...]
    page: int

    @property
    def total(self) -> int:
        """How many actions the list holds, whatever the page."""
        return len(self.rows)

    @property
    def page_count(self) -> int:
        """How many pages the list has; an empty list still has one."""
        return page_count_of(len(self.rows))

    @property
    def page_rows(self) -> tuple[ActionRow, ...]:
        """The lines of the current page."""
        start = (self.page - 1) * validation.PAGE_SIZE
        return self.rows[start : start + validation.PAGE_SIZE]

    @property
    def overdue_share(self) -> int | None:
        """Atrasadas as a whole percentage of the open ones, or ``None`` when nothing is open."""
        return calculations.overdue_share_of_open(self.counts)

    def board_column(self, status: ActionStatus) -> tuple[ActionRow, ...]:
        """The cards of one kanban column, by deadline."""
        return tuple(row for row in self.board if row.record.status is status)


@dataclass(frozen=True)
class ReplanLine:
    """One line of the history of replans: when, from, to, by whom and why."""

    registered_on: date
    from_date: date
    to_date: date
    author_name: str
    justification: str


def page_count_of(total: int) -> int:
    """How many pages a list of ``total`` lines takes; an empty list still has one page."""
    return max(1, -(-total // validation.PAGE_SIZE))


# ── Writing: the seam and the movements of an action ─────────────────────────────────────────


def create_action(
    session: Session, *, user: User, new: NewAction, reference_date: date
) -> ActionRecord:
    """The single way to record an action: it keeps the origin and the reference of the record.

    Refuses with 422 (one message per field) when the origin, the reference, the subject, the
    planned date, the project or a person do not hold up, and with 403 when the user may not
    write. Everything goes in the transaction of the caller.
    """
    rbac.require(user, Permission.WRITE)
    problems = validation.new_action_problems(new)
    problems.update(_register_problems(session, new))
    if problems:
        raise InvalidDataError(problems)
    action = Action(
        project_id=new.project_id,
        ata_id=new.ata_id,
        requester_id=new.requester_id,
        responsible_id=new.responsible_id,
        origin=new.origin,
        origin_ref=new.origin_ref.strip(),
        item=new.item,
        group=new.group,
        kind=new.kind,
        contributes_probability=new.contributes_probability,
        contributes_impact=new.contributes_impact,
        subject=new.subject.strip(),
        description=(new.description or "").strip() or None,
        planned_date=new.planned_date,
        replanned_date=new.replans[-1].to_date if new.replans else None,
        completed_on=new.completed_on,
    )
    recording.create(session, user_id=user.id, record=action)
    for entry in new.replans:
        _record_replan(session, user=user, action_id=action.id, entry=entry)
    return _record_of(action, reference_date)


def replan_action(
    session: Session, *, user: User, request: ReplanRequest, reference_date: date
) -> ActionRecord:
    """Move the deadline of an open action; the justification stays in its history (HU-053).

    422 without a justification (or with one that is too short), without the new date, with a
    date before the reference date or equal to the deadline in force; 409 when someone saved the
    action since the screen opened it. The module of the origin is told in the same transaction.
    """
    rbac.require(user, Permission.WRITE)
    action = _open_action_treated_here(session, request.action_id)
    current_due = calculations.effective_due_date(action.planned_date, action.replanned_date)
    problems = validation.replan_problems(
        request, current_due=current_due, reference_date=reference_date
    )
    if problems or request.new_date is None or current_due is None:
        raise InvalidDataError(problems or {"data": validation.NEW_DATE_REQUIRED})
    recording.update(
        session,
        user_id=user.id,
        record=action,
        changes={"replanned_date": request.new_date},
        version=request.version,
    )
    entry = ReplanEntry(
        author_id=user.person_id,
        registered_on=reference_date,
        from_date=current_due,
        to_date=request.new_date,
        justification=request.justification,
    )
    _record_replan(session, user=user, action_id=action.id, entry=entry)
    origins.react(session, user, action, ActionEvent.REPLANNED)
    return _record_of(action, reference_date)


def complete_action(
    session: Session, *, user: User, request: CompletionRequest, reference_date: date
) -> ActionRecord:
    """Complete an open action with the completion date; the module of the origin is told."""
    rbac.require(user, Permission.WRITE)
    action = _open_action_treated_here(session, request.action_id)
    message = validation.completion_problem(request.completed_on, reference_date)
    if message is not None:
        raise InvalidDataError({"data_conclusao": message})
    recording.update(
        session,
        user_id=user.id,
        record=action,
        changes={"completed_on": request.completed_on},
        version=request.version,
    )
    origins.react(session, user, action, ActionEvent.COMPLETED)
    return _record_of(action, reference_date)


def close_from_origin(
    session: Session,
    *,
    user: User,
    origin: origin_links.OriginRef,
    completed_on: date,
    reference_date: date,
) -> list[ActionRecord]:
    """The origin closed its record on its own screen: complete the open actions that point to it.

    Does not tell the origin back (it is the one that moved); an action already completed stays
    as it is. The ``item`` of the origin narrows it to the actions of that item of the record (a
    recommendation of a risk analysis). Returns the actions that were completed now.
    """
    rbac.require(user, Permission.WRITE)
    changed: list[ActionRecord] = []
    for action in _actions_of_origin(session, origin):
        if action.completed_on is not None or calculations.is_information(action.kind):
            continue
        _update(session, user=user, action=action, changes={"completed_on": completed_on})
        changed.append(_record_of(action, reference_date))
    return changed


def reopen_from_origin(
    session: Session, *, user: User, origin: origin_links.OriginRef, reference_date: date
) -> list[ActionRecord]:
    """The origin reopened its record: the completed actions that point to it are open again."""
    rbac.require(user, Permission.WRITE)
    changed: list[ActionRecord] = []
    for action in _actions_of_origin(session, origin):
        if action.completed_on is None:
            continue
        _update(session, user=user, action=action, changes={"completed_on": None})
        changed.append(_record_of(action, reference_date))
    return changed


# ── Reading ──────────────────────────────────────────────────────────────────────────────────


def find_action(
    session: Session, *, user: User, action_id: int, reference_date: date
) -> ActionRecord | None:
    """The action with the id, or ``None`` when there is none."""
    rbac.require_module(user, MODULE)
    action = session.get(Action, action_id)
    return None if action is None else _record_of(action, reference_date)


def count_by_status(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> StatusCounts:
    """The number of actions on time, overdue and completed in the scope (informations excluded)."""
    rbac.require_module(user, MODULE)
    statuses = (
        calculations.action_status(_action_dates(action), reference_date)
        for action in _actions_in_scope(session, scope=scope)
    )
    return calculations.counts_by_status(statuses)


def list_actions(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: ActionFilters,
    reference_date: date,
) -> ActionListing:
    """The list, the KPIs and the kanban of the screen Ações for the filters and the scope.

    The KPIs count the actions that pass origin, responsible and search (the status filter does
    not change them: it is chosen by them). The list also takes the status filter, and only
    items of the kind Ação enter (an Informação stays in its ata). The kanban distributes the
    same actions by status: all of them when the filter is Em andamento or Todos, otherwise the
    ones of the list.
    """
    rbac.require_module(user, MODULE)
    universe = _actions_in_scope(session, scope=scope)
    records = [
        _record_of(action, reference_date)
        for action in _filter_by_context(session, universe, filters)
    ]
    listed = [
        record
        for record in records
        if calculations.matches_status_filter(filters.status, record.status)
    ]
    on_board = records if filters.status in (StatusFilter.OPEN, StatusFilter.ALL) else listed
    desk = _Desk.load(session, records=records)
    return ActionListing(
        counts=calculations.counts_by_status(record.status for record in records),
        due_by_reference=calculations.due_by_reference_count(
            (_dates_of(record) for record in records), reference_date
        ),
        universe=len(universe),
        rows=tuple(desk.row(record) for record in _by_deadline(listed)),
        board=tuple(desk.row(record) for record in _by_deadline(on_board)),
        responsibles=_responsible_options(session, universe),
        page=min(max(filters.page, 1), page_count_of(len(listed))),
    )


def replan_history(session: Session, *, user: User, action_id: int) -> list[ReplanLine]:
    """The replans of an action, the most recent first: the justifications of the deadline."""
    rbac.require_module(user, MODULE)
    statement = (
        select(ActionReplan)
        .where(ActionReplan.action_id == action_id)
        .order_by(ActionReplan.registered_on.desc(), ActionReplan.id.desc())
    )
    replans = session.scalars(statement).all()
    names = _person_names(session, {replan.author_id for replan in replans})
    return [
        ReplanLine(
            registered_on=replan.registered_on,
            from_date=replan.from_date,
            to_date=replan.to_date,
            author_name=names.get(replan.author_id, UNKNOWN_PERSON_NAME),
            justification=replan.justification,
        )
        for replan in replans
    ]


def read_action_origin(session: Session, *, user: User, record_id: int) -> OriginRecord | None:
    """The reading function of the attachments of an action: who reads the action reads them."""
    action = session.get(Action, record_id)
    if action is None:
        return None
    rbac.require_module(user, MODULE)
    return OriginRecord(project_id=action.project_id)


def list_actions_of_origin(
    session: Session,
    *,
    user: User,
    origin_kind: str,
    reference: str,
    reference_date: date,
) -> list[ActionRecord]:
    """The actions of one record of origin, by id: what its module reads to show and sync them."""
    rbac.require_module(user, MODULE)
    origin = origin_links.OriginRef(kind=origin_kind, reference=reference)
    return [
        _record_of(action, reference_date)
        for action in _actions_of_origin(session, origin)
        if not calculations.is_information(action.kind)
    ]


@dataclass(frozen=True)
class OriginActionCount:
    """How many actions of one record of origin exist, how many are open and how many overdue."""

    total: int = 0
    open: int = 0
    overdue: int = 0


def count_actions_of_origin(
    session: Session,
    *,
    user: User,
    origin_kind: str,
    references: Collection[str],
    reference_date: date,
) -> dict[str, OriginActionCount]:
    """The actions (never the informations) of each record of one origin, by its reference.

    The module that owns the record of origin asks here instead of reading ``acao``: the Riscos
    register prints ``abertas/total`` per risk and refuses to delete a risk with an open action.
    A reference with no action is left out of the answer.
    """
    rbac.require_module(user, MODULE)
    if not references:
        return {}
    statement = select(Action).where(
        Action.origin == origin_kind,
        Action.origin_ref.in_(list(references)),
        Action.kind == ACTION,
    )
    counts: dict[str, OriginActionCount] = {}
    for action in session.scalars(statement):
        status = calculations.action_status(_action_dates(action), reference_date)
        known = counts.get(action.origin_ref or "", OriginActionCount())
        counts[action.origin_ref or ""] = OriginActionCount(
            total=known.total + 1,
            open=known.open + (status is not ActionStatus.COMPLETED),
            overdue=known.overdue + (status is ActionStatus.OVERDUE),
        )
    return counts


# ── Internals ────────────────────────────────────────────────────────────────────────────────


def _action_dates(action: Action) -> ActionDates:
    return ActionDates(
        kind=action.kind,
        planned_date=action.planned_date,
        replanned_date=action.replanned_date,
        completed_on=action.completed_on,
    )


def _dates_of(record: ActionRecord) -> ActionDates:
    return ActionDates(
        kind=record.kind,
        planned_date=record.planned_date,
        replanned_date=record.replanned_date,
        completed_on=record.completed_on,
    )


def _record_of(action: Action, reference_date: date) -> ActionRecord:
    dates = _action_dates(action)
    return ActionRecord(
        id=action.id,
        project_id=action.project_id,
        origin=action.origin,
        origin_ref=action.origin_ref,
        item=action.item,
        group=action.group,
        kind=action.kind,
        subject=action.subject,
        description=action.description,
        requester_id=action.requester_id,
        responsible_id=action.responsible_id,
        planned_date=action.planned_date,
        replanned_date=action.replanned_date,
        completed_on=action.completed_on,
        ata_id=action.ata_id,
        contributes_probability=action.contributes_probability,
        contributes_impact=action.contributes_impact,
        version=action.version,
        status=calculations.action_status(dates, reference_date),
        days_overdue=calculations.days_overdue(dates, reference_date),
    )


def _update(
    session: Session, *, user: User, action: Action, changes: dict[str, date | None]
) -> None:
    """A change that comes from the origin: the version in the row is the one it is written over."""
    recording.update(
        session, user_id=user.id, record=action, changes=changes, version=action.version
    )


def _register_problems(session: Session, new: NewAction) -> dict[str, str]:
    """The messages for a project or a person that is not in the register."""
    problems: dict[str, str] = {}
    projects = {project.id for project in configuracoes.list_projects(session)}
    if new.project_id not in projects:
        problems["projeto"] = UNKNOWN_PROJECT_MESSAGE
    ids = {new.requester_id, new.responsible_id, *(entry.author_id for entry in new.replans)}
    known = configuracoes.find_people(session, ids)
    if new.requester_id not in known:
        problems["solicitante"] = UNKNOWN_PERSON_MESSAGE
    if new.responsible_id not in known:
        problems["responsavel"] = UNKNOWN_PERSON_MESSAGE
    if any(entry.author_id not in known for entry in new.replans):
        problems["replanejamentos"] = UNKNOWN_PERSON_MESSAGE
    return problems


def _open_action_treated_here(session: Session, action_id: int) -> Action:
    """The action a person may replan or complete here, or the 422 that says why not."""
    action = session.get(Action, action_id)
    if action is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    if calculations.is_information(action.kind):
        raise InvalidDataError(NOT_AN_ACTION_MESSAGE)
    if action.origin in origins.TREATED_AT_SOURCE:
        raise InvalidDataError(TREATED_AT_SOURCE_MESSAGE)
    if action.completed_on is not None:
        raise InvalidDataError(ALREADY_COMPLETED_MESSAGE)
    return action


def _record_replan(session: Session, *, user: User, action_id: int, entry: ReplanEntry) -> None:
    """Add the replan to the history and leave its trail line (a fact: it is never edited)."""
    replan = ActionReplan(
        action_id=action_id,
        author_id=entry.author_id,
        registered_on=entry.registered_on,
        from_date=entry.from_date,
        to_date=entry.to_date,
        justification=entry.justification.strip(),
    )
    session.add(replan)
    session.flush()
    audit.created(session, user_id=user.id, entity=replan.__tablename__, record=replan)


def _actions_of_origin(session: Session, origin: origin_links.OriginRef) -> list[Action]:
    statement = (
        select(Action)
        .where(Action.origin == origin.kind, Action.origin_ref == origin.reference.strip())
        .order_by(Action.id)
    )
    if origin.item is not None:
        statement = statement.where(Action.item == origin.item)
    return list(session.scalars(statement).all())


def _actions_in_scope(session: Session, *, scope: Scope) -> list[Action]:
    """The items of the kind Ação of the scope, by id: an Informação never enters the list."""
    statement = select(Action).where(Action.kind == ACTION).order_by(Action.id)
    if scope.project_id is not None:
        statement = statement.where(Action.project_id == scope.project_id)
    return list(session.scalars(statement).all())


def _filter_by_context(
    session: Session, universe: Sequence[Action], filters: ActionFilters
) -> list[Action]:
    """Origin, responsible and free search: what the KPIs count (the status is not here)."""
    kept = [
        action
        for action in universe
        if (not filters.origin or action.origin == filters.origin)
        and (filters.responsible_id is None or action.responsible_id == filters.responsible_id)
    ]
    if not filters.search:
        return kept
    names = _person_names(session, {action.responsible_id for action in kept})
    codes = {project.id: project.code for project in configuracoes.list_projects(session)}
    wanted = normalize_text(filters.search)
    return [
        action
        for action in kept
        if wanted in normalize_text(_searchable_text(action, names, codes))
    ]


def _searchable_text(action: Action, names: dict[int, str], codes: dict[int, str]) -> str:
    """What the free search reads: subject, description, reference, origin, who, group, project."""
    parts = (
        action.subject,
        action.description,
        action.origin_ref,
        action.origin,
        names.get(action.responsible_id),
        action.group,
        codes.get(action.project_id),
    )
    return " ".join(part for part in parts if part)


def normalize_text(text: str) -> str:
    """Lower case without accents, so ``Mudança`` is found by ``mudanca``."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _by_deadline(records: Iterable[ActionRecord]) -> list[ActionRecord]:
    """The deadline in force, the closest first; an action with no date goes last."""
    return sorted(
        records,
        key=lambda record: (record.due_date is None, record.due_date or date.min, record.id),
    )


def _person_names(session: Session, ids: Collection[int]) -> dict[int, str]:
    found = configuracoes.find_people(session, ids)
    return {person_id: person.name for person_id, person in found.items()}


def _responsible_options(
    session: Session, universe: Sequence[Action]
) -> tuple[ResponsibleOption, ...]:
    names = _person_names(session, {action.responsible_id for action in universe})
    options = [ResponsibleOption(id=key, name=name) for key, name in names.items()]
    return tuple(sorted(options, key=lambda option: (normalize_text(option.name), option.id)))


@dataclass(frozen=True)
class _Desk:
    """What a line needs besides the action: names, project labels and the count of replans."""

    names: dict[int, str]
    projects: dict[int, str]
    replans: dict[int, int]

    @classmethod
    def load(cls, session: Session, *, records: Sequence[ActionRecord]) -> _Desk:
        """Read once what the lines of a listing print, instead of once per line."""
        people = {record.responsible_id for record in records}
        people |= {record.requester_id for record in records}
        labels = {
            project.id: f"{project.code} · {project.name}"
            for project in configuracoes.list_projects(session)
        }
        return cls(
            names=_person_names(session, people),
            projects=labels,
            replans=_replan_counts(session, [record.id for record in records]),
        )

    def row(self, record: ActionRecord) -> ActionRow:
        """The line of one action."""
        return ActionRow(
            record=record,
            requester_name=self.names.get(record.requester_id, UNKNOWN_PERSON_NAME),
            responsible_name=self.names.get(record.responsible_id, UNKNOWN_PERSON_NAME),
            project_label=self.projects.get(record.project_id, ""),
            link=origin_links.resolve(record.origin, record.origin_ref, record_id=record.ata_id),
            replan_count=self.replans.get(record.id, 0),
        )


def _replan_counts(session: Session, action_ids: Sequence[int]) -> dict[int, int]:
    """How many replans each action has; an action never replanned is absent."""
    if not action_ids:
        return {}
    statement = (
        select(ActionReplan.action_id, func.count())
        .where(ActionReplan.action_id.in_(action_ids))
        .group_by(ActionReplan.action_id)
    )
    return dict(session.execute(statement).tuples().all())


attachment_origins.register(
    OriginType(table=ATTACHMENT_TABLE, module=MODULE, read=read_action_origin)
)
