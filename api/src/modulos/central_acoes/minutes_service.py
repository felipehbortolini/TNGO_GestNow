"""Facade of the minutes (atas) of the Central de Ações (HU-051, HU-054, D5, D9, ISSUE-021).

The list shows only the most recent revision of each minutes; a new minutes takes the number of
the project from the platform sequence and opens with its author in the attendance list; the
executing companies and the attendance list are kept here, and nothing leaves them while an open
action of the minutes is under the responsibility of the person (or of someone of the company).
Every write goes by ``core.recording`` (trail, version, transaction); the companies and the
attendees have no version of their own: the version of the minutes protects them, so a change of
the lists advances it.

Public API (stable; a change needs an issue of its own):

* ``create_minutes(session, *, user, new, reference_date) -> MinutesRecord``;
* ``list_minutes(session, *, user, scope, filters, reference_date) -> MinutesListing``;
* ``find_minutes(session, *, user, minutes_id, reference_date) -> MinutesSheet | None``;
* ``set_companies``, ``add_guests`` and ``remove_attendee``: the lists of the ficha;
* ``guest_candidates``: the people the search of guests offers.

The Central registers here the link of the origin ``Ata`` (``origin_links``): an action of a
minutes opens the ficha of its minutes. Nothing here reads the clock; the routes hand in the date.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit, numbering, origin_links, rbac, recording
from src.core.errors import InvalidDataError
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import calculations, service, validation
from src.modulos.central_acoes.calculations import (
    ACTION,
    INFORMATION,
    ActionDates,
    ActionStatus,
    RevisionEntry,
    StatusCounts,
)
from src.modulos.central_acoes.models import (
    Action,
    ActionReplan,
    Minutes,
    MinutesCompany,
    MinutesParticipant,
)
from src.modulos.central_acoes.service import ReplanLine, normalize_text, replan_history
from src.modulos.central_acoes.validation import (
    AttendanceRequest,
    CompaniesRequest,
    ItemInput,
    MinutesFilters,
    NewAction,
    NewMinutes,
    ReplanEntry,
    ReplanRequest,
    RevisionInput,
)
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.service import PersonDetail

MODULE = "central_acoes"
NUMBER_KIND = "ata"
MINUTES_ORIGIN = "Ata"
MINUTES_SCREEN = "central_acoes/ata"
WITHOUT_COMPANY_LABEL = "Timenow / cliente"
GENERAL_GROUP = "Geral"

NOT_FOUND_MESSAGE = "A ata pedida não existe ou foi removida."
READ_ONLY_MESSAGE = "Esta é uma revisão anterior, somente leitura: abra a revisão vigente."
UNKNOWN_PROJECT_MESSAGE = "O projeto informado não existe."
UNKNOWN_UNIT_MESSAGE = "A unidade informada não está no cadastro."
UNKNOWN_PERSON_MESSAGE = "A pessoa informada não está no cadastro."
UNKNOWN_COMPANY_MESSAGE = "A empresa informada não está no cadastro."
GUEST_REQUIRED_MESSAGE = "Escolha ao menos uma pessoa."
ALREADY_ATTENDING_MESSAGE = "A pessoa já está na lista de presença."
NOT_ATTENDING_MESSAGE = "A pessoa não está na lista de presença desta ata."
UNKNOWN_PERSON_NAME = "Pessoa removida do cadastro"
NO_COUNTS = StatusCounts(on_time=0, overdue=0, completed=0)


@dataclass(frozen=True)
class MinutesRecord:
    """One revision of a minutes as the screens read it: the columns of ``ata``."""

    id: int
    project_id: int
    number: str
    revision: int
    meeting_date: date
    meeting_type: str
    board: str
    unit_id: int | None
    prepared_by_id: int
    main_company_id: int | None
    subject: str
    version: int


@dataclass(frozen=True)
class MinutesRow:
    """A line of the list: the minutes with what is printed around it."""

    record: MinutesRecord
    project_label: str
    main_company_name: str
    open_count: int
    overdue_count: int


@dataclass(frozen=True)
class MinutesListing:
    """What the screen Atas shows: the latest revision of each minutes, filtered and paged."""

    rows: tuple[MinutesRow, ...]
    universe: int
    page: int

    @property
    def total(self) -> int:
        """How many minutes the list holds, whatever the page."""
        return len(self.rows)

    @property
    def page_count(self) -> int:
        """How many pages the list has; an empty list still has one."""
        return max(1, -(-len(self.rows) // validation.MINUTES_PAGE_SIZE))

    @property
    def page_rows(self) -> tuple[MinutesRow, ...]:
        """The lines of the current page."""
        start = (self.page - 1) * validation.MINUTES_PAGE_SIZE
        return self.rows[start : start + validation.MINUTES_PAGE_SIZE]


@dataclass(frozen=True)
class Attendee:
    """A person of the attendance list with the open actions she holds in this minutes."""

    person: PersonDetail
    company_name: str
    open_count: int


@dataclass(frozen=True)
class CompanyEntry:
    """An executing company of the minutes and whether it is the main one."""

    id: int
    name: str
    is_main: bool


@dataclass(frozen=True)
class MinutesSheet:
    """The ficha of a minutes: header, companies, attendance and the count of its items."""

    record: MinutesRecord
    project_label: str
    prepared_by_name: str
    unit_name: str
    main_company_name: str
    companies: tuple[CompanyEntry, ...]
    attendees: tuple[Attendee, ...]
    counts: StatusCounts
    information_count: int
    latest_id: int
    revision_ids: tuple[int, ...]

    @property
    def is_latest(self) -> bool:
        """Whether this revision is the one in force: only it may be changed."""
        return self.record.id == self.latest_id

    @property
    def item_count(self) -> int:
        """Annotations and actions of the minutes."""
        return self.counts.total + self.information_count


# ── Writing ──────────────────────────────────────────────────────────────────────────────────


def create_minutes(
    session: Session, *, user: User, new: NewMinutes, reference_date: date
) -> MinutesRecord:
    """Generate a minutes: number of the project, revision 0 (or the one handed in), author and companies (HU-051).

    422 with one message per field when something required is missing or unknown, 403 when the
    user may not write. Everything goes in the transaction of the caller.
    """
    rbac.require(user, Permission.WRITE)
    problems = validation.minutes_problems(new)
    problems.update(_register_problems(session, new))
    project = configuracoes.find_project(session, new.project_id)
    if problems or project is None or new.meeting_date is None or new.prepared_by_id is None:
        raise InvalidDataError(problems or {"projeto": UNKNOWN_PROJECT_MESSAGE})
    number = new.number or numbering.next_number(
        session, project=project, kind=NUMBER_KIND, reference_date=reference_date
    )
    minutes = Minutes(
        project_id=new.project_id,
        unit_id=new.unit_id,
        prepared_by_id=new.prepared_by_id,
        main_company_id=new.main_company_id,
        number=number,
        revision=new.revision,
        meeting_date=new.meeting_date,
        meeting_type=new.meeting_type,
        board=new.board.strip(),
        subject=new.subject.strip(),
    )
    recording.create(session, user_id=user.id, record=minutes)
    companies = [new.main_company_id] if new.main_company_id is not None else []
    for company_id in dict.fromkeys([*companies, *new.company_ids]):
        _add_company(session, user=user, minutes_id=minutes.id, company_id=company_id)
    for person_id in dict.fromkeys([new.prepared_by_id, *new.participant_ids]):
        _add_participant(session, user=user, minutes_id=minutes.id, person_id=person_id)
    return _record_of(minutes)


def set_companies(session: Session, *, user: User, request: CompaniesRequest) -> MinutesRecord:
    """Set the main company and the executing companies; refused while an open action blocks it.

    The main company always belongs to the executing ones. A company leaves only when nobody of
    it holds an open action of this minutes (HU-054); the message names the companies.
    """
    rbac.require(user, Permission.WRITE)
    minutes = _latest_minutes(session, request.minutes_id)
    known = configuracoes.list_company_names(session)
    wanted = tuple(
        dict.fromkeys(
            [
                *([request.main_company_id] if request.main_company_id is not None else []),
                *request.company_ids,
            ]
        )
    )
    unknown = [company_id for company_id in wanted if company_id not in known]
    if unknown:
        raise InvalidDataError({"empresas": UNKNOWN_COMPANY_MESSAGE})
    current = {row.company_id: row for row in _company_rows(session, minutes.id)}
    removed = [company_id for company_id in current if company_id not in wanted]
    _refuse_blocked_companies(session, minutes=minutes, removed=removed, names=known)
    recording.update(
        session,
        user_id=user.id,
        record=minutes,
        changes={"main_company_id": request.main_company_id},
        version=request.version,
    )
    for company_id in removed:
        _delete_child(session, user=user, row=current[company_id])
    for company_id in wanted:
        if company_id not in current:
            _add_company(session, user=user, minutes_id=minutes.id, company_id=company_id)
    return _record_of(minutes)


def add_guests(session: Session, *, user: User, request: AttendanceRequest) -> MinutesRecord:
    """Add people of the register to the attendance list (``Buscar convidado``)."""
    rbac.require(user, Permission.WRITE)
    minutes = _latest_minutes(session, request.minutes_id)
    if not request.person_ids:
        raise InvalidDataError({"pessoas": GUEST_REQUIRED_MESSAGE})
    known = configuracoes.find_people(session, request.person_ids)
    if any(person_id not in known for person_id in request.person_ids):
        raise InvalidDataError({"pessoas": UNKNOWN_PERSON_MESSAGE})
    attending = {row.person_id for row in _participant_rows(session, minutes.id)}
    if any(person_id in attending for person_id in request.person_ids):
        raise InvalidDataError({"pessoas": ALREADY_ATTENDING_MESSAGE})
    _touch(session, user=user, minutes=minutes, version=request.version)
    for person_id in request.person_ids:
        _add_participant(session, user=user, minutes_id=minutes.id, person_id=person_id)
    return _record_of(minutes)


def remove_attendee(
    session: Session, *, user: User, minutes_id: int, person_id: int, version: int | str | None
) -> MinutesRecord:
    """Take a person off the attendance list, unless an open action of the minutes is hers (HU-054).

    Refused with 422 and the message when she holds an open action here; otherwise the row goes
    and the trail records it.
    """
    rbac.require(user, Permission.WRITE)
    minutes = _latest_minutes(session, minutes_id)
    rows = {row.person_id: row for row in _participant_rows(session, minutes.id)}
    if person_id not in rows:
        raise InvalidDataError(NOT_ATTENDING_MESSAGE)
    open_count = _open_actions_by_person(session, minutes.id).get(person_id, 0)
    if open_count:
        names = configuracoes.find_people(session, [person_id])
        raise InvalidDataError(
            blocked_attendee_message(
                names[person_id].name if person_id in names else UNKNOWN_PERSON_NAME, open_count
            )
        )
    _touch(session, user=user, minutes=minutes, version=version)
    _delete_child(session, user=user, row=rows[person_id])
    return _record_of(minutes)


def blocked_attendee_message(name: str, open_count: int) -> str:
    """The refusal of taking a person off the list: how many open actions are under her."""
    noun = "ação aberta" if open_count == 1 else "ações abertas"
    return f"Não é possível retirar {name}: {open_count} {noun} sob sua responsabilidade nesta ata."


def blocked_companies_message(names: Sequence[str]) -> str:
    """The refusal of taking companies off the minutes: someone of them holds an open action."""
    return (
        f"Não é possível retirar {', '.join(names)}: há ação em aberto com responsável da empresa."
    )


# ── Reading ──────────────────────────────────────────────────────────────────────────────────


def list_minutes(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: MinutesFilters,
    reference_date: date,
) -> MinutesListing:
    """The latest revision of each minutes of the scope, newest meeting first (HU-051)."""
    rbac.require_module(user, MODULE)
    statement = select(Minutes)
    if scope.project_id is not None:
        statement = statement.where(Minutes.project_id == scope.project_id)
    stored = list(session.scalars(statement).all())
    latest = calculations.latest_revision_ids(
        RevisionEntry(m.id, m.project_id, m.number, m.revision) for m in stored
    )
    current = [minutes for minutes in stored if minutes.id in latest]
    projects = {project.id: project for project in configuracoes.list_projects(session)}
    wanted = normalize_text(filters.search)
    kept = [
        minutes
        for minutes in current
        if not wanted
        or wanted in normalize_text(_searchable_text(minutes, projects.get(minutes.project_id)))
    ]
    kept.sort(key=lambda minutes: (minutes.meeting_date, minutes.id), reverse=True)
    companies = configuracoes.list_company_names(session)
    counts = _status_counts_by_minutes(session, [minutes.id for minutes in kept], reference_date)
    rows = tuple(
        MinutesRow(
            record=_record_of(minutes),
            project_label=_project_label(projects.get(minutes.project_id)),
            main_company_name=companies.get(minutes.main_company_id or 0, ""),
            open_count=counts.get(minutes.id, NO_COUNTS).open,
            overdue_count=counts.get(minutes.id, NO_COUNTS).overdue,
        )
        for minutes in kept
    )
    pages = max(1, -(-len(rows) // validation.MINUTES_PAGE_SIZE))
    return MinutesListing(rows=rows, universe=len(current), page=min(max(filters.page, 1), pages))


def find_minutes(
    session: Session, *, user: User, minutes_id: int, reference_date: date
) -> MinutesSheet | None:
    """The ficha of the minutes with the id, or ``None`` when there is none."""
    rbac.require_module(user, MODULE)
    minutes = session.get(Minutes, minutes_id)
    if minutes is None:
        return None
    lineage = list(
        session.scalars(
            select(Minutes)
            .where(Minutes.project_id == minutes.project_id, Minutes.number == minutes.number)
            .order_by(Minutes.revision)
        ).all()
    )
    names = configuracoes.list_company_names(session)
    company_rows = _company_rows(session, minutes.id)
    open_by_person = _open_actions_by_person(session, minutes.id)
    people = configuracoes.find_person_details(
        session,
        {row.person_id for row in _participant_rows(session, minutes.id)}
        | {minutes.prepared_by_id},
    )
    attendees = tuple(
        sorted(
            (
                Attendee(
                    person=people[row.person_id],
                    company_name=names.get(people[row.person_id].company_id or 0, "")
                    or WITHOUT_COMPANY_LABEL,
                    open_count=open_by_person.get(row.person_id, 0),
                )
                for row in _participant_rows(session, minutes.id)
                if row.person_id in people
            ),
            key=lambda attendee: (normalize_text(attendee.person.name), attendee.person.id),
        )
    )
    project = configuracoes.find_project(session, minutes.project_id)
    units = {unit.id: unit.name for unit in configuracoes.list_organizational_units(session)}
    prepared_by = people.get(minutes.prepared_by_id)
    return MinutesSheet(
        record=_record_of(minutes),
        project_label=f"{project.code} · {project.name}" if project else "",
        prepared_by_name=prepared_by.name if prepared_by else UNKNOWN_PERSON_NAME,
        unit_name=units.get(minutes.unit_id or 0, ""),
        main_company_name=names.get(minutes.main_company_id or 0, ""),
        companies=tuple(
            CompanyEntry(
                id=row.company_id,
                name=names.get(row.company_id, ""),
                is_main=row.company_id == minutes.main_company_id,
            )
            for row in company_rows
        ),
        attendees=attendees,
        counts=_status_counts_by_minutes(session, [minutes.id], reference_date).get(
            minutes.id, NO_COUNTS
        ),
        information_count=_information_count(session, minutes.id),
        latest_id=lineage[-1].id,
        revision_ids=tuple(item.id for item in lineage),
    )


def guest_candidates(
    session: Session, *, user: User, minutes_id: int, search: str
) -> list[PersonDetail]:
    """The people of the register who are not yet in the attendance list, by name."""
    rbac.require_module(user, MODULE)
    attending = {row.person_id for row in _participant_rows(session, minutes_id)}
    wanted = normalize_text(search)
    return [
        person
        for person in configuracoes.list_person_details(session)
        if person.id not in attending
        and (
            not wanted
            or wanted in normalize_text(f"{person.name} {person.role or ''} {person.email}")
        )
    ]


# ── Items and revisions of the minutes (ISSUE-022) ───────────────────────────────────────────

ITEM_NOT_FOUND_MESSAGE = "O item informado não pertence a esta ata."


@dataclass(frozen=True)
class ItemRow:
    """One annotation or action of the minutes, as the tab, the modals and the exports read it."""

    id: int
    kind: str
    group: str
    item: str
    subject: str
    description: str
    requester_id: int
    requester_name: str
    responsible_id: int
    responsible_name: str
    planned_date: date | None
    replanned_date: date | None
    completed_on: date | None
    status: ActionStatus
    status_label: str
    days_overdue: int
    has_replans: bool

    @property
    def is_action(self) -> bool:
        """Whether the item is an action (an annotation is never replanned nor completed)."""
        return self.kind == ACTION


@dataclass(frozen=True)
class ItemGroup:
    """One group / area of the minutes with its items, in the order of the numbering."""

    number: str
    name: str
    items: tuple[ItemRow, ...]


@dataclass(frozen=True)
class ItemSummary:
    """The KPIs of the tab: total, em dia, atrasadas, concluídas, informações e previstas."""

    total: int
    on_time: int
    overdue: int
    completed: int
    information: int
    due_by_reference: int


@dataclass(frozen=True)
class ItemListing:
    """The items of the minutes grouped by group / area, with the KPIs of the tab."""

    groups: tuple[ItemGroup, ...]
    summary: ItemSummary


@dataclass(frozen=True)
class RevisionLine:
    """One revision of the lineage of the minutes, as the Histórico da ata modal lists it."""

    id: int
    revision: int
    meeting_date: date
    subject: str
    is_latest: bool


@dataclass(frozen=True)
class ItemRef:
    """Which item of which minutes: the pair every write of an item receives."""

    minutes_id: int
    item_id: int | None = None


def list_items(
    session: Session, *, user: User, minutes_id: int, reference_date: date
) -> ItemListing:
    """The items of the minutes: groups in the order of the numbering and the KPIs of the tab."""
    rbac.require_module(user, MODULE)
    rows = _item_rows(session, minutes_id, reference_date)
    return ItemListing(groups=_item_groups(rows), summary=_item_summary(rows, reference_date))


def find_item(
    session: Session, *, user: User, minutes_id: int, item_id: int, reference_date: date
) -> ItemRow | None:
    """One item of the minutes, or ``None`` when it does not belong to it."""
    rbac.require_module(user, MODULE)
    action = _item_of(session, minutes_id, item_id)
    if action is None:
        return None
    return _item_row(
        action, _names_of(session, [action]), _replan_ids(session, [action.id]), reference_date
    )


def next_item_number(session: Session, minutes_id: int, group: str) -> str:
    """The next number of the group: ``1.1`` when the group is new, else one more in the group."""
    wanted = group.strip()
    pairs = session.execute(
        select(Action.group, Action.item).where(Action.ata_id == minutes_id)
    ).all()
    known: dict[str, list[tuple[int, int]]] = {}
    for name, item in pairs:
        key = (name or "").strip() or GENERAL_GROUP
        known.setdefault(key, []).append(_item_key(item))
    if wanted not in known:
        highest = max((first for items in known.values() for first, _ in items), default=0)
        return f"{highest + 1}.1"
    leading = min(first for first, _ in known[wanted])
    second = max(second for _, second in known[wanted])
    return f"{leading}.{second + 1}"


def save_item(
    session: Session,
    *,
    user: User,
    ref: ItemRef,
    data: ItemInput,
    reference_date: date,
) -> ItemRow:
    """Create or edit an item of the minutes; an action is born by the seam of the Central (D9)."""
    rbac.require(user, Permission.WRITE)
    minutes = _latest_minutes(session, ref.minutes_id)
    participants = {row.person_id for row in _participant_rows(session, minutes.id)}
    problems = validation.item_problems(
        data, participant_ids=participants, reference_date=reference_date
    )
    if problems:
        raise InvalidDataError(problems)
    if ref.item_id is None:
        created = service.create_action(
            session,
            user=user,
            new=_new_action(minutes, data, item=next_item_number(session, minutes.id, data.group)),
            reference_date=reference_date,
        )
        action = _item_of(session, minutes.id, created.id)
        if action is None:  # pragma: no cover - o registro acabou de ser criado
            raise InvalidDataError(ITEM_NOT_FOUND_MESSAGE)
        return _item_row(
            action, _names_of(session, [action]), _replan_ids(session, [action.id]), reference_date
        )
    action = _item_of(session, minutes.id, ref.item_id)
    if action is None:
        raise InvalidDataError(ITEM_NOT_FOUND_MESSAGE)
    changes: dict[str, object] = {
        "kind": data.kind,
        "group": data.group.strip(),
        "subject": data.subject,
        "description": data.description,
        "requester_id": data.requester_id,
        "responsible_id": data.responsible_id,
        "completed_on": data.completed_on,
    }
    if action.replanned_date is None:
        changes["planned_date"] = data.planned_date
    if (action.group or "").strip() != data.group.strip():
        changes["item"] = next_item_number(session, minutes.id, data.group)
    recording.update(session, user_id=user.id, record=action, changes=changes, version=data.version)
    return _item_row(
        action, _names_of(session, [action]), _replan_ids(session, [action.id]), reference_date
    )


def replan_item(
    session: Session,
    *,
    user: User,
    ref: ItemRef,
    request: ReplanRequest,
    reference_date: date,
) -> ItemRow:
    """Register the replan of an item of the minutes through the rules of the Central (HU-053)."""
    rbac.require(user, Permission.WRITE)
    minutes = _latest_minutes(session, ref.minutes_id)
    if ref.item_id is None:
        raise InvalidDataError(ITEM_NOT_FOUND_MESSAGE)
    action = _item_of(session, minutes.id, ref.item_id)
    if action is None:
        raise InvalidDataError(ITEM_NOT_FOUND_MESSAGE)
    if action.kind != ACTION:
        raise InvalidDataError(service.NOT_AN_ACTION_MESSAGE)
    service.replan_action(
        session,
        user=user,
        request=ReplanRequest(
            action_id=action.id,
            new_date=request.new_date,
            justification=request.justification,
            version=request.version,
        ),
        reference_date=reference_date,
    )
    return _item_row(
        action, _names_of(session, [action]), _replan_ids(session, [action.id]), reference_date
    )


def item_justifications(
    session: Session, *, user: User, minutes_id: int, item_id: int
) -> tuple[ReplanLine, ...]:
    """The replans of one item of the minutes, newest first (the Justificativas modal)."""
    rbac.require_module(user, MODULE)
    action = _item_of(session, minutes_id, item_id)
    if action is None:
        raise InvalidDataError(ITEM_NOT_FOUND_MESSAGE)
    return tuple(replan_history(session, user=user, action_id=action.id))


def generate_revision(
    session: Session,
    *,
    user: User,
    minutes_id: int,
    data: RevisionInput,
    reference_date: date,
) -> MinutesRecord:
    """Open the next revision of the lineage, carrying the lists and the items (HU-052).

    The current revision stays as history (read only); the new one receives the companies, the
    attendance and a copy of every item, with its replans, and starts feeding the Central.
    """
    rbac.require(user, Permission.WRITE)
    minutes = _latest_minutes(session, minutes_id)
    problems = validation.revision_problems(data, current_date=minutes.meeting_date)
    if problems:
        raise InvalidDataError(problems)
    if data.meeting_date is None:  # pragma: no cover - a validação acima exige a data
        raise InvalidDataError({"data": validation.MINUTES_DATE_REQUIRED})
    recording.update(session, user_id=user.id, record=minutes, changes={}, version=data.version)
    new = Minutes(
        project_id=minutes.project_id,
        unit_id=minutes.unit_id,
        prepared_by_id=minutes.prepared_by_id,
        main_company_id=minutes.main_company_id,
        number=minutes.number,
        revision=minutes.revision + 1,
        meeting_date=data.meeting_date,
        meeting_type=minutes.meeting_type,
        board=minutes.board,
        subject=minutes.subject,
    )
    recording.create(session, user_id=user.id, record=new)
    for row in _company_rows(session, minutes.id):
        _add_company(session, user=user, minutes_id=new.id, company_id=row.company_id)
    for row in _participant_rows(session, minutes.id):
        _add_participant(session, user=user, minutes_id=new.id, person_id=row.person_id)
    for action in _item_actions(session, minutes.id):
        service.create_action(
            session,
            user=user,
            new=_copied_action(session, new, action),
            reference_date=reference_date,
        )
    return _record_of(new)


def revision_history(session: Session, *, user: User, minutes_id: int) -> tuple[RevisionLine, ...]:
    """Every revision of the lineage, newest first, marking the one in force."""
    rbac.require_module(user, MODULE)
    minutes = session.get(Minutes, minutes_id)
    if minutes is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    lineage = list(
        session.scalars(
            select(Minutes)
            .where(Minutes.project_id == minutes.project_id, Minutes.number == minutes.number)
            .order_by(Minutes.revision.desc())
        ).all()
    )
    latest_id = max((item.id for item in lineage), default=minutes.id)
    return tuple(
        RevisionLine(
            id=item.id,
            revision=item.revision,
            meeting_date=item.meeting_date,
            subject=item.subject,
            is_latest=item.id == latest_id,
        )
        for item in lineage
    )


# ── Internals ────────────────────────────────────────────────────────────────────────────────


def _record_of(minutes: Minutes) -> MinutesRecord:
    return MinutesRecord(
        id=minutes.id,
        project_id=minutes.project_id,
        number=minutes.number,
        revision=minutes.revision,
        meeting_date=minutes.meeting_date,
        meeting_type=minutes.meeting_type,
        board=minutes.board,
        unit_id=minutes.unit_id,
        prepared_by_id=minutes.prepared_by_id,
        main_company_id=minutes.main_company_id,
        subject=minutes.subject,
        version=minutes.version,
    )


def _project_label(project: configuracoes.ProjectSummary | None) -> str:
    return f"{project.code} · {project.name}" if project else ""


def _searchable_text(minutes: Minutes, project: configuracoes.ProjectSummary | None) -> str:
    """What the search reads: number, subject, meeting type and the code of the project."""
    parts = (minutes.number, minutes.subject, minutes.meeting_type, project.code if project else "")
    return " ".join(parts)


def _register_problems(session: Session, new: NewMinutes) -> dict[str, str]:
    """The messages for a project, unit, person or company that is not in the register."""
    problems: dict[str, str] = {}
    if configuracoes.find_project(session, new.project_id) is None:
        problems["projeto"] = UNKNOWN_PROJECT_MESSAGE
    units = {unit.id for unit in configuracoes.list_organizational_units(session)}
    if new.unit_id is not None and new.unit_id not in units:
        problems["unidade"] = UNKNOWN_UNIT_MESSAGE
    people = {person for person in (new.prepared_by_id, *new.participant_ids) if person is not None}
    if len(configuracoes.find_people(session, people)) != len(people):
        problems["elaborado_por"] = UNKNOWN_PERSON_MESSAGE
    wanted = {*new.company_ids, *([new.main_company_id] if new.main_company_id else [])}
    if not wanted <= configuracoes.list_company_names(session).keys():
        problems["empresas"] = UNKNOWN_COMPANY_MESSAGE
    return problems


def _latest_minutes(session: Session, minutes_id: int) -> Minutes:
    """The minutes a person may change: it exists and it is the revision in force."""
    minutes = session.get(Minutes, minutes_id)
    if minutes is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    highest = session.scalar(
        select(Minutes.revision)
        .where(Minutes.project_id == minutes.project_id, Minutes.number == minutes.number)
        .order_by(Minutes.revision.desc())
        .limit(1)
    )
    if highest is not None and minutes.revision < highest:
        raise InvalidDataError(READ_ONLY_MESSAGE)
    return minutes


def _touch(session: Session, *, user: User, minutes: Minutes, version: int | str | None) -> None:
    """Advance the version of the minutes for a change of its lists, after the version check."""
    recording.update(session, user_id=user.id, record=minutes, changes={}, version=version)


def _company_rows(session: Session, minutes_id: int) -> list[MinutesCompany]:
    statement = (
        select(MinutesCompany)
        .where(MinutesCompany.minutes_id == minutes_id)
        .order_by(MinutesCompany.id)
    )
    return list(session.scalars(statement).all())


def _participant_rows(session: Session, minutes_id: int) -> list[MinutesParticipant]:
    statement = (
        select(MinutesParticipant)
        .where(MinutesParticipant.minutes_id == minutes_id)
        .order_by(MinutesParticipant.id)
    )
    return list(session.scalars(statement).all())


def _add_company(session: Session, *, user: User, minutes_id: int, company_id: int) -> None:
    row = MinutesCompany(minutes_id=minutes_id, company_id=company_id)
    session.add(row)
    session.flush()
    audit.created(session, user_id=user.id, entity=row.__tablename__, record=row)


def _add_participant(session: Session, *, user: User, minutes_id: int, person_id: int) -> None:
    row = MinutesParticipant(minutes_id=minutes_id, person_id=person_id)
    session.add(row)
    session.flush()
    audit.created(session, user_id=user.id, entity=row.__tablename__, record=row)


def _delete_child(
    session: Session, *, user: User, row: MinutesCompany | MinutesParticipant
) -> None:
    """Remove a row of a list of the minutes and leave the trail of the removal."""
    before = audit.snapshot(row)
    session.delete(row)
    session.flush()
    audit.deleted(session, user_id=user.id, entity=row.__tablename__, record=row, before=before)


def _open_actions(session: Session, minutes_id: int) -> list[Action]:
    """The actions (never the annotations) of the minutes without a completion date."""
    statement = select(Action).where(
        Action.ata_id == minutes_id, Action.kind == ACTION, Action.completed_on.is_(None)
    )
    return list(session.scalars(statement).all())


def _open_actions_by_person(session: Session, minutes_id: int) -> dict[int, int]:
    counts: dict[int, int] = {}
    for action in _open_actions(session, minutes_id):
        counts[action.responsible_id] = counts.get(action.responsible_id, 0) + 1
    return counts


def _refuse_blocked_companies(
    session: Session, *, minutes: Minutes, removed: Collection[int], names: dict[int, str]
) -> None:
    """422 naming the companies that cannot leave: someone of them holds an open action here."""
    if not removed:
        return
    responsibles = {action.responsible_id for action in _open_actions(session, minutes.id)}
    people = configuracoes.find_person_details(session, responsibles)
    holding = {person.company_id for person in people.values()}
    blocked = [names.get(company_id, "") for company_id in removed if company_id in holding]
    if blocked:
        raise InvalidDataError({"empresas": blocked_companies_message(blocked)})


def _status_counts_by_minutes(
    session: Session, minutes_ids: Sequence[int], reference_date: date
) -> dict[int, StatusCounts]:
    """The actions of each minutes by status on the reference date (annotations do not count)."""
    if not minutes_ids:
        return {}
    statement = select(Action).where(Action.ata_id.in_(minutes_ids), Action.kind == ACTION)
    statuses: dict[int, list[ActionStatus]] = {}
    for action in session.scalars(statement):
        dates = ActionDates(
            kind=action.kind,
            planned_date=action.planned_date,
            replanned_date=action.replanned_date,
            completed_on=action.completed_on,
        )
        statuses.setdefault(action.ata_id or 0, []).append(
            calculations.action_status(dates, reference_date)
        )
    return {key: calculations.counts_by_status(value) for key, value in statuses.items()}


def _information_count(session: Session, minutes_id: int) -> int:
    statement = select(Action.id).where(Action.ata_id == minutes_id, Action.kind == INFORMATION)
    return len(session.scalars(statement).all())


def _item_of(session: Session, minutes_id: int, item_id: int) -> Action | None:
    return session.scalars(
        select(Action).where(Action.id == item_id, Action.ata_id == minutes_id)
    ).one_or_none()


def _item_actions(session: Session, minutes_id: int) -> list[Action]:
    """Every item of the minutes, in the order of the numbering."""
    statement = select(Action).where(Action.ata_id == minutes_id)
    return sorted(session.scalars(statement).all(), key=lambda action: _item_key(action.item))


def _item_rows(session: Session, minutes_id: int, reference_date: date) -> list[ItemRow]:
    actions = _item_actions(session, minutes_id)
    names = _names_of(session, actions)
    with_replans = _replan_ids(session, [action.id for action in actions])
    return [_item_row(action, names, with_replans, reference_date) for action in actions]


def _names_of(session: Session, actions: Sequence[Action]) -> dict[int, str]:
    ids = {action.requester_id for action in actions}
    ids.update(action.responsible_id for action in actions)
    return configuracoes.person_names(session, ids)


def _replan_ids(session: Session, action_ids: Sequence[int]) -> set[int]:
    if not action_ids:
        return set()
    statement = select(ActionReplan.action_id).where(ActionReplan.action_id.in_(action_ids))
    return set(session.scalars(statement).all())


def _replan_rows(session: Session, action_id: int) -> list[ActionReplan]:
    statement = (
        select(ActionReplan).where(ActionReplan.action_id == action_id).order_by(ActionReplan.id)
    )
    return list(session.scalars(statement).all())


def _item_row(
    action: Action,
    names: Mapping[int, str],
    with_replans: Collection[int],
    reference_date: date,
) -> ItemRow:
    dates = ActionDates(
        kind=action.kind,
        planned_date=action.planned_date,
        replanned_date=action.replanned_date,
        completed_on=action.completed_on,
    )
    status = calculations.action_status(dates, reference_date)
    return ItemRow(
        id=action.id,
        kind=action.kind,
        group=(action.group or "").strip() or GENERAL_GROUP,
        item=action.item or "",
        subject=action.subject,
        description=action.description or "",
        requester_id=action.requester_id,
        requester_name=names.get(action.requester_id, UNKNOWN_PERSON_NAME),
        responsible_id=action.responsible_id,
        responsible_name=names.get(action.responsible_id, UNKNOWN_PERSON_NAME),
        planned_date=action.planned_date,
        replanned_date=action.replanned_date,
        completed_on=action.completed_on,
        status=status,
        status_label=calculations.STATUS_LABELS[status],
        days_overdue=calculations.days_overdue(dates, reference_date),
        has_replans=action.id in with_replans,
    )


def _item_groups(rows: Sequence[ItemRow]) -> tuple[ItemGroup, ...]:
    grouped: dict[str, list[ItemRow]] = {}
    for row in rows:
        grouped.setdefault(row.group, []).append(row)
    return tuple(
        ItemGroup(
            number=group_rows[0].item.split(".")[0] or str(position + 1),
            name=name,
            items=tuple(group_rows),
        )
        for position, (name, group_rows) in enumerate(grouped.items())
    )


def _item_summary(rows: Sequence[ItemRow], reference_date: date) -> ItemSummary:
    return ItemSummary(
        total=len(rows),
        on_time=sum(1 for row in rows if row.status is ActionStatus.IN_PROGRESS),
        overdue=sum(1 for row in rows if row.status is ActionStatus.OVERDUE),
        completed=sum(1 for row in rows if row.status is ActionStatus.COMPLETED),
        information=sum(1 for row in rows if row.status is ActionStatus.INFORMATION),
        due_by_reference=sum(
            1
            for row in rows
            if row.is_action and row.planned_date is not None and row.planned_date <= reference_date
        ),
    )


def _item_key(item: str | None) -> tuple[int, int]:
    """``1.10`` as ``(1, 10)``; what is not a number counts as zero, so the order never breaks."""
    parts = (item or "").split(".")
    first = int(parts[0]) if parts[0].isdigit() else 0
    second = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return first, second


def _new_action(minutes: Minutes, data: ItemInput, *, item: str) -> NewAction:
    return NewAction(
        project_id=minutes.project_id,
        origin=MINUTES_ORIGIN,
        origin_ref=minutes.number,
        subject=data.subject,
        requester_id=cast(int, data.requester_id),
        responsible_id=cast(int, data.responsible_id),
        planned_date=data.planned_date,
        kind=data.kind,
        description=data.description,
        group=data.group.strip(),
        item=item,
        ata_id=minutes.id,
        completed_on=data.completed_on,
    )


def _copied_action(session: Session, new: Minutes, action: Action) -> NewAction:
    """One item of the current revision as the seam of the next revision receives it."""
    return NewAction(
        project_id=new.project_id,
        origin=MINUTES_ORIGIN,
        origin_ref=new.number,
        subject=action.subject,
        requester_id=action.requester_id,
        responsible_id=action.responsible_id,
        planned_date=action.planned_date,
        kind=action.kind,
        description=action.description,
        group=action.group,
        item=action.item,
        ata_id=new.id,
        contributes_probability=action.contributes_probability,
        contributes_impact=action.contributes_impact,
        completed_on=action.completed_on,
        replans=tuple(
            ReplanEntry(
                author_id=row.author_id,
                registered_on=row.registered_on,
                from_date=row.from_date,
                to_date=row.to_date,
                justification=row.justification,
            )
            for row in _replan_rows(session, action.id)
        ),
    )


def _build_minutes_link(reference: origin_links.OriginRef) -> str | None:
    """The address of the ficha of the minutes an action came from; none when the id is unknown."""
    if reference.record_id is None:
        return None
    return origin_links.link_to_screen(MINUTES_SCREEN, id=reference.record_id)


origin_links.register(origin_links.OriginLinkType(kind=MINUTES_ORIGIN, build=_build_minutes_link))
