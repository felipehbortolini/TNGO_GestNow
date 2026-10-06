"""Facade of the Punch list (ISSUE-049, HU-068, HU-069, D7, D9, D5a).

The items of completion: numbered by the pattern of the project (``PL-TN-2026-0001``), with the
hierarchy Área, Sistema, Subsistema and TAG, the category A, B or C, the milestone and the flow
Aberto, Em tratamento, Aguardando verificação, Fechado (back to Em tratamento when the
verification rejects) or Cancelado (with a justification).

* Closing needs evidence (at least one attachment of the item, D5a) and a verifier who is not the
  executant: the server refuses with 403, whatever the screen shows (D7).
* A system with an open item A is blocked for the milestone of the item (``blocking_count``).
* Every item is also an action of the Central (origin Punch list), created through the single seam
  of action (D9). The item repeats its changes in the action, and the Central, which treats a
  Punch list action at the source, shows the item's situation and links back to it.

Writing goes through ``core.recording`` (trail, version and transaction together). Nothing here
reads the clock: the date comes from the caller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import attachment_origins, attachments, numbering, origin_links, rbac, recording
from src.core.attachment_origins import OriginRecord, OriginType
from src.core.errors import InvalidDataError
from src.core.rbac import Conflict, Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.central_acoes.validation import NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import punch_calculations as calc
from src.modulos.planejamento import punch_validation as validation
from src.modulos.planejamento.models import PunchItem
from src.modulos.planejamento.punch_validation import ItemInput

MODULE = "planejamento"
ATTACHMENT_TABLE = "punch_item"
ACTION_ORIGIN = "Punch list"
NUMBERING_KIND = "punch"
ALL_OPEN = "abertos"

NOT_FOUND_MESSAGE = "Item da punch list não encontrado."
NOT_OPEN_MESSAGE = "Só um item aberto pode ser editado ou cancelado."
WRONG_STEP_MESSAGE = "O item está em «{situation}»: este passo não é possível agora."
EVIDENCE_MESSAGE = "A evidência é obrigatória: anexe ao menos uma foto ou um documento ao item."
SEGREGATION_MESSAGE = "O verificador não pode ser o executante do item (segregação de funções)."
UNKNOWN_PROJECT_MESSAGE = "O projeto informado não existe."


@dataclass(frozen=True)
class PunchFilter:
    """The filters of the list: the situation (``abertos`` by default), the rest as chosen."""

    situation: str = ALL_OPEN
    category: str = ""
    system_id: int | None = None
    discipline: str = ""
    company_id: int | None = None
    search: str = ""


@dataclass(frozen=True)
class PunchRow:
    """An item as the list, the Excel and the forms read it: stored fields and the calculated."""

    id: int
    project_id: int
    project_label: str
    code: str
    system_id: int
    system_label: str
    subsystem: str
    tag: str
    discipline: str
    category: str
    milestone: str
    origin: str
    description: str
    company_id: int | None
    company_name: str
    responsible_id: int
    responsible_name: str
    identified_by_id: int
    identified_by_name: str
    verified_by_name: str
    opened_on: date
    due_date: date
    closed_on: date | None
    situation: str
    treatment_comment: str
    verification_comment: str
    cancellation_reason: str
    rejections: int
    age_days: int
    is_open: bool
    is_overdue: bool
    version: int

    @property
    def facts(self) -> calc.PunchFacts:
        """What the rules read of the item."""
        return calc.PunchFacts(
            system_id=self.system_id,
            category=self.category,
            milestone=self.milestone,
            situation=self.situation,
            opened_on=self.opened_on,
            due_date=self.due_date,
            closed_on=self.closed_on,
        )

    @property
    def can_start(self) -> bool:
        """Aberto goes to Em tratamento."""
        return self.situation == calc.OPEN

    @property
    def can_submit(self) -> bool:
        """Em tratamento goes to Aguardando verificação."""
        return self.situation == calc.IN_TREATMENT

    @property
    def can_verify(self) -> bool:
        """Aguardando verificação closes or goes back to Em tratamento."""
        return self.situation == calc.AWAITING_VERIFICATION


@dataclass(frozen=True)
class Figures:
    """The indicators of the list (the prototype's five), counted over every item of the scope."""

    open: int
    open_a: int
    awaiting: int
    overdue: int
    closed: int
    valid: int

    @property
    def closed_percentage(self) -> int | None:
        """The closed items over the valid ones (not cancelled)."""
        return calc.closed_percentage(self.closed, self.valid)


@dataclass(frozen=True)
class SystemRow:
    """A system of the table of release: open items by category and the block by milestone."""

    system_id: int
    project_label: str
    label: str
    area: str
    open_a: int
    open_b: int
    open_c: int
    blocks: tuple[int, ...]


@dataclass(frozen=True)
class PunchBoard:
    """What the screen prints: the filtered rows, the indicators, the alert and the systems."""

    rows: tuple[PunchRow, ...]
    total: int
    figures: Figures
    blocked_systems: tuple[str, ...]
    systems: tuple[SystemRow, ...]
    portfolio: bool
    can_write: bool
    filters: PunchFilter


@dataclass(frozen=True)
class SystemChoice:
    """A system of the project the form offers."""

    id: int
    label: str


@dataclass(frozen=True)
class FormOptions:
    """The register lists of the form of an item."""

    systems: tuple[SystemChoice, ...]
    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]


# ── Reading ──────────────────────────────────────────────────────────────────────────────────


def can_write(user: User) -> bool:
    """Whether the profile may open, edit and move items."""
    return rbac.can(user, Permission.WRITE)


def punch_board(
    session: Session,
    *,
    user: User,
    scope: Scope,
    reference_date: date,
    filters: PunchFilter,
) -> PunchBoard:
    """The list of the scope with the filters, the indicators and the release of the systems."""
    rbac.require_module(user, MODULE)
    every = _rows_in_scope(session, scope=scope, reference_date=reference_date)
    systems = [
        item for item in configuracoes.list_systems(session) if _in_scope(scope, item.project_id)
    ]
    names = _Names.read(session)
    facts = [row.facts for row in every]
    blocked = set(calc.blocked_system_ids(facts, [item.id for item in systems]))
    return PunchBoard(
        rows=tuple(row for row in every if _passes(row, filters)),
        total=len(every),
        figures=_figures(every),
        blocked_systems=tuple(_system_label(item) for item in systems if item.id in blocked),
        systems=tuple(_system_row(item, every, names) for item in systems),
        portfolio=scope.is_portfolio,
        can_write=can_write(user),
        filters=filters,
    )


def find_item(
    session: Session, *, user: User, scope: Scope, item_id: int, reference_date: date
) -> PunchRow:
    """The item of the scope with the id, or 422 when there is none."""
    rbac.require_module(user, MODULE)
    record = _scoped_item(session, scope, item_id)
    return _rows(session, [record], reference_date=reference_date)[0]


def find_item_by_code(
    session: Session, *, user: User, scope: Scope, code: str, reference_date: date
) -> PunchRow | None:
    """The item of the scope with the code, or ``None``: what the link back from the Central opens."""
    rbac.require_module(user, MODULE)
    statement = select(PunchItem).where(PunchItem.code == code.strip())
    if not scope.is_portfolio:
        statement = statement.where(PunchItem.project_id == scope.project_id)
    record = session.scalars(statement).first()
    return None if record is None else _rows(session, [record], reference_date=reference_date)[0]


def form_options(session: Session, *, project_id: int) -> FormOptions:
    """The systems of the project, the companies and the people the form offers."""
    return FormOptions(
        systems=tuple(
            SystemChoice(id=item.id, label=_system_label(item))
            for item in configuracoes.list_systems(session)
            if item.project_id == project_id
        ),
        companies=tuple(configuracoes.list_company_options(session)),
        people=tuple(configuracoes.list_person_options(session)),
    )


def register_choices(session: Session, *, project_id: int) -> validation.RegisterChoices:
    """The ids the register accepts in a form of the project, for the validation."""
    options = form_options(session, project_id=project_id)
    return validation.RegisterChoices(
        system_ids=frozenset(item.id for item in options.systems),
        company_ids=frozenset(item.id for item in options.companies),
        person_ids=frozenset(item.id for item in options.people),
    )


def item_fields(row: PunchRow) -> dict[str, str]:
    """The item as the fields of the form (the names of the form, the text the inputs hold)."""
    return {
        "sistema": str(row.system_id),
        "subsistema": row.subsystem,
        "tag": row.tag,
        "disciplina": row.discipline,
        "categoria": row.category,
        "marco": row.milestone,
        "origem": row.origin,
        "prazo": row.due_date.isoformat(),
        "descricao": row.description,
        "empresa": "" if row.company_id is None else str(row.company_id),
        "responsavel": str(row.responsible_id),
        "identificado_por": str(row.identified_by_id),
        "versao": str(row.version),
    }


# ── Writing: the item and the flow ───────────────────────────────────────────────────────────


def create_item(
    session: Session,
    *,
    user: User,
    scope: Scope,
    data: ItemInput,
    reference_date: date,
) -> PunchItem:
    """Open an item in the project of the scope: numbered, with its action in the Central.

    422 per field when the data does not hold up; 403 below Membro. Everything goes in the
    transaction of the caller (the item and the action, or neither).
    """
    rbac.require(user, Permission.WRITE)
    project_id = scope.require_project()
    project = configuracoes.find_project(session, project_id)
    if project is None:
        raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)
    validation.require_valid_item(data, register_choices(session, project_id=project_id))
    code = numbering.next_number(
        session, project=project, kind=NUMBERING_KIND, reference_date=reference_date
    )
    record = recording.create(
        session,
        user_id=user.id,
        record=_new_record(project_id, code, data, opened_on=reference_date),
    )
    central_acoes.create_action(
        session, user=user, new=_action_of(session, record), reference_date=reference_date
    )
    return record


def update_item(session: Session, *, user: User, scope: Scope, edit: ItemEdit) -> PunchItem:
    """Edit an open item; the version the screen opened must still be current (409 otherwise)."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_item(session, scope, edit.item_id)
    if not calc.is_open(record.situation):
        raise InvalidDataError(NOT_OPEN_MESSAGE)
    validation.require_valid_item(
        edit.data, register_choices(session, project_id=record.project_id)
    )
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes=_changes_of(edit.data),
        version=edit.version,
    )
    _repeat_in_action(session, user, record)
    return record


def start_treatment(
    session: Session, *, user: User, scope: Scope, item_id: int, version: str | None
) -> PunchItem:
    """Aberto goes to Em tratamento."""
    record = _movable_item(session, user, scope, item_id, expected=calc.OPEN)
    return _move(session, user, record, {"situation": calc.IN_TREATMENT}, version=version)


def submit_for_verification(
    session: Session, *, user: User, scope: Scope, request: TreatmentRequest
) -> PunchItem:
    """Em tratamento goes to Aguardando verificação: what was done and the evidence are required."""
    record = _movable_item(session, user, scope, request.item_id, expected=calc.IN_TREATMENT)
    problems = validation.treatment_problems(request.comment)
    if problems:
        raise InvalidDataError(problems)
    _require_evidence(session, record)
    changes = {
        "situation": calc.AWAITING_VERIFICATION,
        "treatment_comment": request.comment.strip(),
    }
    return _move(session, user, record, changes, version=request.version)


def verify_item(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: VerificationRequest,
    reference_date: date,
) -> PunchItem:
    """Verify a closing: approve (Fechado) or reject (back to Em tratamento).

    403 when the verifier is the executant; 422 without evidence to approve, or without the
    reason to reject. Closing completes the action of the Central in the same transaction.
    """
    record = _movable_item(
        session, user, scope, request.item_id, expected=calc.AWAITING_VERIFICATION
    )
    rbac.require_segregation(user, Conflict(record.responsible_id, SEGREGATION_MESSAGE))
    problems = validation.verification_problems(request.result, request.comment)
    if problems:
        raise InvalidDataError(problems)
    comment = request.comment.strip() or None
    if request.result == validation.REJECTED:
        changes = {
            "situation": calc.IN_TREATMENT,
            "verification_comment": comment,
            "rejections": record.rejections + 1,
        }
        return _move(session, user, record, changes, version=request.version)
    _require_evidence(session, record)
    changes = {
        "situation": calc.CLOSED,
        "closed_on": reference_date,
        "verified_by_id": user.person_id,
        "verification_comment": comment,
    }
    closed = _move(session, user, record, changes, version=request.version)
    _complete_action(
        session, user, closed, completed_on=reference_date, reference_date=reference_date
    )
    return closed


def cancel_item(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: CancellationRequest,
    reference_date: date,
) -> PunchItem:
    """Cancel an open item with a justification; its action in the Central is closed with it."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_item(session, scope, request.item_id)
    if not calc.is_open(record.situation):
        raise InvalidDataError(NOT_OPEN_MESSAGE)
    problems = validation.cancellation_problems(request.justification)
    if problems:
        raise InvalidDataError(problems)
    changes = {
        "situation": calc.CANCELLED,
        "cancellation_reason": request.justification.strip(),
    }
    cancelled = _move(session, user, record, changes, version=request.version)
    _complete_action(
        session, user, cancelled, completed_on=reference_date, reference_date=reference_date
    )
    return cancelled


@dataclass(frozen=True)
class ItemEdit:
    """What the edit form sends: the item, its typed fields and the version the screen opened."""

    item_id: int
    data: ItemInput
    version: str | None = None


@dataclass(frozen=True)
class TreatmentRequest:
    """What the sending modal sends: the item, what was done and the version."""

    item_id: int
    comment: str
    version: str | None = None


@dataclass(frozen=True)
class VerificationRequest:
    """What the closing modal sends: the item, the result, the comment and the version."""

    item_id: int
    result: str
    comment: str = ""
    version: str | None = None


@dataclass(frozen=True)
class CancellationRequest:
    """What the cancelling modal sends: the item, the justification and the version."""

    item_id: int
    justification: str
    version: str | None = None


# ── Writing: the demonstration load ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LoadedItem:
    """An item of the prototype as the load writes it: its code and its history come with it."""

    project_id: int
    code: str
    data: ItemInput
    opened_on: date
    situation: str
    closed_on: date | None = None
    verified_by_id: int | None = None
    cancellation_reason: str | None = None


def load_item(session: Session, *, user_id: int, item: LoadedItem) -> PunchItem:
    """Write an item of the prototype as it is; its action comes from the load of the Central."""
    return recording.create(
        session,
        user_id=user_id,
        record=replace_record(
            _new_record(item.project_id, item.code, item.data, opened_on=item.opened_on),
            situation=item.situation,
            closed_on=item.closed_on,
            verified_by_id=item.verified_by_id,
            cancellation_reason=item.cancellation_reason,
        ),
    )


def continue_numbering(session: Session, *, project_id: int, last_number: int) -> None:
    """Make the next code of the project come after the last one the load wrote."""
    project = configuracoes.find_project(session, project_id)
    if project is not None:
        numbering.start_after(
            session, project=project, kind=NUMBERING_KIND, last_number=last_number
        )


def replace_record(record: PunchItem, **values: object) -> PunchItem:
    """The record with the fields set (a new record not yet in the session)."""
    for name, value in values.items():
        setattr(record, name, value)
    return record


# ── Attachments and links back ───────────────────────────────────────────────────────────────


def read_punch_item(session: Session, *, user: User, record_id: int) -> OriginRecord | None:
    """The reading function of the attachments of an item: who reads the module reads them."""
    record = session.get(PunchItem, record_id)
    if record is None:
        return None
    rbac.require_module(user, MODULE)
    return OriginRecord(project_id=record.project_id)


def _link_to_item(ref: origin_links.OriginRef) -> str | None:
    return origin_links.link_to_screen("planejamento/punch_list", item=ref.reference)


attachment_origins.register(OriginType(table=ATTACHMENT_TABLE, module=MODULE, read=read_punch_item))
origin_links.register(origin_links.OriginLinkType(kind=ACTION_ORIGIN, build=_link_to_item))


# ── Internals ────────────────────────────────────────────────────────────────────────────────


def _new_record(project_id: int, code: str, data: ItemInput, *, opened_on: date) -> PunchItem:
    return PunchItem(
        project_id=project_id,
        system_id=data.system_id,
        company_id=data.company_id,
        responsible_id=data.responsible_id,
        identified_by_id=data.identified_by_id,
        code=code,
        subsystem=data.subsystem,
        tag=data.tag,
        discipline=data.discipline,
        category=data.category,
        milestone=data.milestone,
        origin=data.origin,
        description=data.description,
        opened_on=opened_on,
        due_date=data.due_date,
        situation=calc.OPEN,
        rejections=0,
    )


def _changes_of(data: ItemInput) -> dict[str, object]:
    return {
        "system_id": data.system_id,
        "subsystem": data.subsystem,
        "tag": data.tag,
        "discipline": data.discipline,
        "category": data.category,
        "milestone": data.milestone,
        "origin": data.origin,
        "description": data.description,
        "company_id": data.company_id,
        "responsible_id": data.responsible_id,
        "identified_by_id": data.identified_by_id,
        "due_date": data.due_date,
    }


def _scoped_item(session: Session, scope: Scope, item_id: int) -> PunchItem:
    record = session.get(PunchItem, item_id)
    if record is None or not _in_scope(scope, record.project_id):
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return record


def _movable_item(
    session: Session, user: User, scope: Scope, item_id: int, *, expected: str
) -> PunchItem:
    rbac.require(user, Permission.WRITE)
    record = _scoped_item(session, scope, item_id)
    if record.situation != expected:
        raise InvalidDataError(WRONG_STEP_MESSAGE.format(situation=record.situation))
    return record


def _move(
    session: Session,
    user: User,
    record: PunchItem,
    changes: Mapping[str, object],
    *,
    version: str | None,
) -> PunchItem:
    recording.update(session, user_id=user.id, record=record, changes=changes, version=version)
    _repeat_in_action(session, user, record)
    return record


def _require_evidence(session: Session, record: PunchItem) -> None:
    if not attachments.has_evidence(
        session, origin_table=ATTACHMENT_TABLE, origin_record_id=record.id
    ):
        raise InvalidDataError({"anexo": EVIDENCE_MESSAGE})


def _system_labels(session: Session) -> dict[int, str]:
    return {item.id: _system_label(item) for item in configuracoes.list_systems(session)}


def _system_label(item: configuracoes.SystemOption) -> str:
    return f"{item.code} {item.name}"


def _action_description(record: PunchItem, system_label: str) -> str:
    tag = f" · {record.tag}" if record.tag else ""
    return f"Sistema {system_label}{tag} · categoria {record.category} · {record.situation}"


def _action_of(session: Session, record: PunchItem) -> NewAction:
    label = _system_labels(session).get(record.system_id, "")
    return NewAction(
        project_id=record.project_id,
        origin=ACTION_ORIGIN,
        origin_ref=record.code,
        subject=record.description,
        requester_id=record.identified_by_id,
        responsible_id=record.responsible_id,
        planned_date=record.due_date,
        description=_action_description(record, label),
        group=label,
    )


def _origin_of(record: PunchItem) -> origin_links.OriginRef:
    return origin_links.OriginRef(kind=ACTION_ORIGIN, reference=record.code, record_id=record.id)


def _repeat_in_action(session: Session, user: User, record: PunchItem) -> None:
    """The item changed: the action of the Central repeats what it takes from the item."""
    label = _system_labels(session).get(record.system_id, "")
    central_acoes.update_from_origin(
        session,
        user=user,
        origin=_origin_of(record),
        changes=central_acoes.OriginChanges(
            subject=record.description,
            description=_action_description(record, label),
            group=label,
            requester_id=record.identified_by_id,
            responsible_id=record.responsible_id,
            planned_date=record.due_date,
        ),
    )


def _complete_action(
    session: Session,
    user: User,
    record: PunchItem,
    *,
    completed_on: date,
    reference_date: date,
) -> None:
    central_acoes.close_from_origin(
        session,
        user=user,
        origin=_origin_of(record),
        completed_on=completed_on,
        reference_date=reference_date,
    )


def _in_scope(scope: Scope, project_id: int) -> bool:
    return scope.is_portfolio or scope.project_id == project_id


def _rows_in_scope(session: Session, *, scope: Scope, reference_date: date) -> list[PunchRow]:
    statement = select(PunchItem).order_by(PunchItem.project_id, PunchItem.code)
    if not scope.is_portfolio:
        statement = statement.where(PunchItem.project_id == scope.project_id)
    return _rows(session, list(session.scalars(statement)), reference_date=reference_date)


@dataclass(frozen=True)
class _Names:
    projects: Mapping[int, str]
    companies: Mapping[int, str]
    people: Mapping[int, str]
    systems: Mapping[int, str]

    @classmethod
    def read(cls, session: Session) -> _Names:
        return cls(
            projects={
                project.id: f"{project.code} · {project.name}"
                for project in configuracoes.list_projects(session)
            },
            companies={item.id: item.name for item in configuracoes.list_company_options(session)},
            people={item.id: item.name for item in configuracoes.list_person_options(session)},
            systems=_system_labels(session),
        )


def _rows(
    session: Session, records: Sequence[PunchItem], *, reference_date: date
) -> list[PunchRow]:
    names = _Names.read(session)
    return [_row_of(record, names, reference_date) for record in records]


def _row_of(record: PunchItem, names: _Names, reference_date: date) -> PunchRow:
    facts = calc.PunchFacts(
        system_id=record.system_id,
        category=record.category,
        milestone=record.milestone,
        situation=record.situation,
        opened_on=record.opened_on,
        due_date=record.due_date,
        closed_on=record.closed_on,
    )
    return PunchRow(
        id=record.id,
        project_id=record.project_id,
        project_label=names.projects.get(record.project_id, ""),
        code=record.code,
        system_id=record.system_id,
        system_label=names.systems.get(record.system_id, ""),
        subsystem=record.subsystem,
        tag=record.tag,
        discipline=record.discipline,
        category=record.category,
        milestone=record.milestone,
        origin=record.origin,
        description=record.description,
        company_id=record.company_id,
        company_name=names.companies.get(record.company_id or 0, ""),
        responsible_id=record.responsible_id,
        responsible_name=names.people.get(record.responsible_id, ""),
        identified_by_id=record.identified_by_id,
        identified_by_name=names.people.get(record.identified_by_id, ""),
        verified_by_name=names.people.get(record.verified_by_id or 0, ""),
        opened_on=record.opened_on,
        due_date=record.due_date,
        closed_on=record.closed_on,
        situation=record.situation,
        treatment_comment=record.treatment_comment or "",
        verification_comment=record.verification_comment or "",
        cancellation_reason=record.cancellation_reason or "",
        rejections=record.rejections,
        age_days=calc.item_age_days(facts, reference_date),
        is_open=calc.is_open(record.situation),
        is_overdue=calc.is_overdue(facts, reference_date),
        version=record.version,
    )


def _passes(row: PunchRow, filters: PunchFilter) -> bool:
    return all(
        (
            filters.situation != ALL_OPEN or row.is_open,
            filters.situation in ("", ALL_OPEN) or row.situation == filters.situation,
            not filters.category or row.category == filters.category,
            filters.system_id is None or row.system_id == filters.system_id,
            not filters.discipline or row.discipline == filters.discipline,
            filters.company_id is None or row.company_id == filters.company_id,
            _matches(row, filters.search),
        )
    )


def _matches(row: PunchRow, search: str) -> bool:
    needle = search.strip().lower()
    if not needle:
        return True
    haystack = " ".join((row.code, row.description, row.tag, row.subsystem, row.system_label))
    return needle in haystack.lower()


def _figures(rows: Sequence[PunchRow]) -> Figures:
    open_rows = [row for row in rows if row.is_open]
    return Figures(
        open=len(open_rows),
        open_a=sum(1 for row in open_rows if row.category == "A"),
        awaiting=sum(1 for row in rows if row.situation == calc.AWAITING_VERIFICATION),
        overdue=sum(1 for row in rows if row.is_overdue),
        closed=sum(1 for row in rows if row.situation == calc.CLOSED),
        valid=sum(1 for row in rows if row.situation != calc.CANCELLED),
    )


def _system_row(
    item: configuracoes.SystemOption, rows: Sequence[PunchRow], names: _Names
) -> SystemRow:
    facts = [row.facts for row in rows]
    mine = [row for row in rows if row.system_id == item.id and row.is_open]

    def open_of(category: str) -> int:
        return sum(1 for row in mine if row.category == category)

    return SystemRow(
        system_id=item.id,
        project_label=names.projects.get(item.project_id, ""),
        label=_system_label(item),
        area=item.area or "",
        open_a=open_of("A"),
        open_b=open_of("B"),
        open_c=open_of("C"),
        blocks=tuple(
            calc.blocking_count(facts, item.id, milestone) for milestone in calc.PANEL_MILESTONES
        ),
    )
