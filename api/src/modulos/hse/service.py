"""Business facade of the HSE module: HHT, monthly closing, inspections, observations and DDS.

Every write goes through ``core.recording`` (trail, version and transaction together); a module
never reads these tables, it uses the functions below (D9, ISSUE-072).

* ``save_hours``: one HHT record per project, month and company: saving again updates the
  same record, never duplicates it (an import line and the form do the same);
* ``save_closing``: one monthly closing per project and month, with the same upsert;
* ``save_inspection``, ``save_observation``, ``save_talk``: the individual proactive records;
* ``list_*`` and the summaries read them; ``labour_histogram`` is the planned labour derived
  from the HHT and the physical S curve, calculated here and read by the HHT screen and by the
  disbursement schedule;
* ``register_curve_reader``: the module that owns the physical S curve (the EAP) says where to
  read it; without a reader every month keeps the factor 1.

The name of the person observed in an observation is personal data: only a manager or an admin
reads it (``Permission.VIEW_RESTRICTED``, Q35); the others see the record without the name.
Nothing here reads the clock: the routes obtain the date from ``core.calendario``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from src.core import rbac, recording
from src.core.errors import InvalidDataError
from src.core.export_document import project_label
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, validation
from src.modulos.hse.calculations import (
    ClosingLine,
    CurvePoint,
    ExpectedWindow,
    HistogramPoint,
    HoursLine,
    HoursSummary,
    ProactiveSummary,
)
from src.modulos.hse.models import (
    BehaviorObservation,
    MonthlyClosing,
    SafetyInspection,
    SafetyInspectionItem,
    SafetyTalk,
    WorkedHours,
)
from src.modulos.hse.validation import (
    ClosingInput,
    HoursInput,
    InspectionInput,
    ObservationInput,
    RegisterChoices,
    TalkInput,
)

MODULE = "hse"
PARAMETER_GROUP = "hse"
DEFAULT_OBSERVATION_TARGET = 40
DEFAULT_DEVIATION_TARGET = 12

UNKNOWN_PROJECT_MESSAGE = "O projeto informado não existe."
NOT_FOUND_MESSAGE = "Registro não encontrado."
UNKNOWN_NAME = "Cadastro removido"

CurveReader = Callable[[Session, int, date], Sequence[CurvePoint]]
_curve_readers: list[CurveReader] = []


def register_curve_reader(reader: CurveReader) -> None:
    """Say where the physical S curve of a project is read: ``reader(session, project_id, today)``."""
    if reader not in _curve_readers:
        _curve_readers.append(reader)


ContractCompanyReader = Callable[[Session, Scope], Collection[int]]
_contract_company_readers: list[ContractCompanyReader] = []


def register_contract_company_reader(reader: ContractCompanyReader) -> None:
    """Say where the companies with a contract in a scope are read (Financeiro, ISSUE-0xx)."""
    if reader not in _contract_company_readers:
        _contract_company_readers.append(reader)


@dataclass(frozen=True)
class SaveResult:
    """What a save did: the id of the record and whether it was created (or updated)."""

    id: int
    created: bool


@dataclass(frozen=True)
class Page:
    """A slice of a list: the rows of the page and where the page sits."""

    rows: tuple[Any, ...]
    page: int
    page_count: int
    total: int


def paginate(rows: Sequence[Any], page: int) -> Page:
    """The rows of a page (``PAGE_SIZE`` each); a page past the end is the last one."""
    size = validation.PAGE_SIZE
    page_count = max(1, -(-len(rows) // size))
    current = min(max(page, 1), page_count)
    start = (current - 1) * size
    return Page(
        rows=tuple(rows[start : start + size]),
        page=current,
        page_count=page_count,
        total=len(rows),
    )


# ── Register lookups ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Names:
    """The names of the register a list prints: projects, companies and people by id."""

    projects: Mapping[int, str]
    companies: Mapping[int, str]
    people: Mapping[int, str]

    def project(self, project_id: int) -> str:
        """``TN-001 · Nome do projeto`` or the placeholder of a removed one."""
        return self.projects.get(project_id, UNKNOWN_NAME)

    def company(self, company_id: int | None) -> str:
        """The company name; the dash when the record has none."""
        if company_id is None:
            return "—"
        return self.companies.get(company_id, UNKNOWN_NAME)

    def person(self, person_id: int | None) -> str:
        """The person name; the dash when the record has none."""
        if person_id is None:
            return "—"
        return self.people.get(person_id, UNKNOWN_NAME)


def names_of(session: Session) -> Names:
    """The names a list prints, read once per request from the register of Configurações."""
    return Names(
        projects={
            project.id: project_label(project) for project in configuracoes.list_projects(session)
        },
        companies={item.id: item.name for item in configuracoes.list_company_options(session)},
        people={item.id: item.name for item in configuracoes.list_person_options(session)},
    )


def register_choices(session: Session) -> RegisterChoices:
    """The companies and the people a form may choose from."""
    return RegisterChoices(
        company_ids={item.id for item in configuracoes.list_company_options(session)},
        person_ids={item.id for item in configuracoes.list_person_options(session)},
    )


def company_options(session: Session) -> list[configuracoes.RegisterOption]:
    """The companies of the register, by name, for the selector of a form."""
    return configuracoes.list_company_options(session)


def person_options(session: Session) -> list[configuracoes.RegisterOption]:
    """The people of the register, by name, for the selector of a form."""
    return configuracoes.list_person_options(session)


def company_id_by_name(session: Session, name: str) -> int | None:
    """The company whose name matches ignoring case and accents, or ``None``."""
    wanted = _plain(name)
    for item in configuracoes.list_company_options(session):
        if _plain(item.name) == wanted:
            return item.id
    return None


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _require_project(session: Session, project_id: int) -> None:
    if configuracoes.find_project(session, project_id) is None:
        raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)


def _scoped(statement: Select[Any], model: Any, scope: Scope) -> Select[Any]:
    if scope.project_id is None:
        return statement
    return statement.where(model.project_id == scope.project_id)


# ── HHT ──────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HoursRow:
    """One line of the HHT table: the record with the names and the hours per person."""

    id: int
    project_id: int
    project_label: str
    month: date
    company_id: int
    company_name: str
    headcount: int
    hours: Decimal
    hours_per_person: int
    version: int

    @property
    def month_text(self) -> str:
        """``Set/2026``."""
        return calculations.month_display(self.month)


def save_hours(
    session: Session, *, user: User, data: HoursInput, reference_date: date
) -> SaveResult:
    """Record the HHT of a month and a company; saving again updates the same record (HU-121).

    422 with a message by field (month, company, headcount, hours); 409 when ``data.version``
    is sent and someone saved the record since the screen opened it.
    """
    rbac.require(user, Permission.WRITE)
    _require_project(session, data.project_id)
    problems = validation.hours_problems(
        data, register_choices(session), reference_date=reference_date
    )
    if problems or data.month is None or data.company_id is None:
        raise InvalidDataError(problems)
    month = calculations.month_of(data.month)
    existing = session.scalar(
        select(WorkedHours)
        .where(
            WorkedHours.project_id == data.project_id,
            WorkedHours.month == month,
            WorkedHours.company_id == data.company_id,
        )
        .with_for_update()
    )
    changes = {"average_headcount": data.headcount, "hours": data.hours}
    if existing is None:
        record = recording.create(
            session,
            user_id=user.id,
            record=WorkedHours(
                project_id=data.project_id,
                company_id=data.company_id,
                month=month,
                average_headcount=data.headcount,
                hours=data.hours,
            ),
        )
        return SaveResult(id=record.id, created=True)
    recording.update(
        session,
        user_id=user.id,
        record=existing,
        changes=changes,
        version=existing.version if data.version is None else data.version,
    )
    return SaveResult(id=existing.id, created=False)


def hours_lines(session: Session, *, scope: Scope) -> list[HoursLine]:
    """The HHT records of the scope as the calculations read them, oldest month first."""
    statement = _scoped(select(WorkedHours), WorkedHours, scope).order_by(
        WorkedHours.month, WorkedHours.company_id
    )
    return [
        HoursLine(
            project_id=row.project_id,
            company_id=row.company_id,
            month=row.month,
            headcount=row.average_headcount,
            hours=row.hours,
        )
        for row in session.scalars(statement)
    ]


def list_hours(session: Session, *, scope: Scope) -> list[HoursRow]:
    """The HHT table: the most recent month first, then the company."""
    names = names_of(session)
    statement = _scoped(select(WorkedHours), WorkedHours, scope).order_by(
        WorkedHours.month.desc(), WorkedHours.company_id, WorkedHours.project_id
    )
    return [
        HoursRow(
            id=row.id,
            project_id=row.project_id,
            project_label=names.project(row.project_id),
            month=row.month,
            company_id=row.company_id,
            company_name=names.company(row.company_id),
            headcount=row.average_headcount,
            hours=row.hours,
            hours_per_person=calculations.hours_per_person(row.hours, row.average_headcount),
            version=row.version,
        )
        for row in session.scalars(statement)
    ]


def find_hours(session: Session, *, hours_id: int) -> HoursRow | None:
    """One HHT record, to open it for editing (the month and the company are locked)."""
    row = session.get(WorkedHours, hours_id)
    if row is None:
        return None
    names = names_of(session)
    return HoursRow(
        id=row.id,
        project_id=row.project_id,
        project_label=names.project(row.project_id),
        month=row.month,
        company_id=row.company_id,
        company_name=names.company(row.company_id),
        headcount=row.average_headcount,
        hours=row.hours,
        hours_per_person=calculations.hours_per_person(row.hours, row.average_headcount),
        version=row.version,
    )


@dataclass(frozen=True)
class HoursScreen:
    """What the HHT screen shows: the table, the four indicators, what is planned and the histogram."""

    rows: tuple[HoursRow, ...]
    summary: HoursSummary
    expected_months: int
    planned_to_date: calculations.PlannedLabour | None
    planned_last_month: calculations.PlannedLabour | None
    companies_expected: int
    histogram: tuple[HistogramPoint, ...]


def hours_screen(session: Session, *, scope: Scope, reference_date: date) -> HoursScreen:
    """The HHT screen of the scope: table, indicators and the labour histogram (HU-121)."""
    lines = hours_lines(session, scope=scope)
    summary = calculations.summarize_hours(lines)
    histogram = labour_histogram(session, scope=scope, reference_date=reference_date)
    last = summary.last_month
    return HoursScreen(
        rows=tuple(list_hours(session, scope=scope)),
        summary=summary,
        expected_months=_expected_months(session, scope=scope, reference_date=reference_date),
        planned_to_date=(
            calculations.planned_labour(histogram, up_to=last) if last is not None else None
        ),
        planned_last_month=(
            calculations.planned_labour(histogram, up_to=last, only_month=True)
            if last is not None
            else None
        ),
        companies_expected=_companies_expected(session, scope=scope),
        histogram=tuple(histogram),
    )


def _expected_months(session: Session, *, scope: Scope, reference_date: date) -> int:
    windows = [
        ExpectedWindow(start=project.start_date, planned_end=project.expected_end_date)
        for project in configuracoes.list_projects(session)
        if scope.project_id is None or project.id == scope.project_id
    ]
    return calculations.expected_months(windows, reference_date)


def _companies_expected(session: Session, *, scope: Scope) -> int:
    """Empresas previstas: the companies with a contract in the scope plus the ones that reported."""
    expected = {line.company_id for line in hours_lines(session, scope=scope)}
    for reader in _contract_company_readers:
        expected.update(reader(session, scope))
    return len(expected)


# ── Labour histogram ─────────────────────────────────────────────────────────────────────────


def labour_histogram(
    session: Session, *, scope: Scope, reference_date: date
) -> list[HistogramPoint]:
    """Histograma de mão de obra previsto, per project and month, calculated from HHT and the curve."""
    lines = hours_lines(session, scope=scope)
    curves: dict[int, Sequence[CurvePoint]] = {}
    for project_id in {line.project_id for line in lines}:
        curves[project_id] = _curve_of(session, project_id, reference_date)
    return calculations.labour_histogram(lines, curves)


def _curve_of(session: Session, project_id: int, reference_date: date) -> Sequence[CurvePoint]:
    for reader in _curve_readers:
        points = reader(session, project_id, reference_date)
        if points:
            return points
    return ()


# ── Monthly closing ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClosingRow:
    """One line of the monthly table: the closing with its project and its two rates."""

    id: int
    project_id: int
    project_label: str
    month: date
    deviations: int
    observations: int
    planned_dds: int
    held_dds: int
    inspected_items: int
    conforming_items: int
    version: int

    @property
    def month_text(self) -> str:
        """``Set/2026``."""
        return calculations.month_display(self.month)

    @property
    def dds_rate(self) -> Decimal | None:
        """Percent of the planned DDS that were held."""
        return calculations.rate_percent(self.held_dds, self.planned_dds)

    @property
    def conformity_rate(self) -> Decimal | None:
        """Percent of the inspected items that were conforming."""
        return calculations.rate_percent(self.conforming_items, self.inspected_items)


def save_closing(
    session: Session, *, user: User, data: ClosingInput, reference_date: date
) -> SaveResult:
    """Record the closing of a month (one per month); saving again updates it (HU-121)."""
    rbac.require(user, Permission.WRITE)
    _require_project(session, data.project_id)
    problems = validation.closing_problems(data, reference_date=reference_date)
    if problems or data.month is None:
        raise InvalidDataError(problems)
    month = calculations.month_of(data.month)
    existing = session.scalar(
        select(MonthlyClosing)
        .where(MonthlyClosing.project_id == data.project_id, MonthlyClosing.month == month)
        .with_for_update()
    )
    values = {
        "deviations": data.deviations,
        "observations": data.observations,
        "planned_dds": data.planned_dds,
        "held_dds": data.held_dds,
        "inspected_items": data.inspected_items,
        "conforming_items": data.conforming_items,
    }
    if existing is None:
        record = recording.create(
            session,
            user_id=user.id,
            record=MonthlyClosing(project_id=data.project_id, month=month, **values),
        )
        return SaveResult(id=record.id, created=True)
    recording.update(
        session,
        user_id=user.id,
        record=existing,
        changes=values,
        version=existing.version if data.version is None else data.version,
    )
    return SaveResult(id=existing.id, created=False)


def _closing_row(row: MonthlyClosing, names: Names) -> ClosingRow:
    return ClosingRow(
        id=row.id,
        project_id=row.project_id,
        project_label=names.project(row.project_id),
        month=row.month,
        deviations=row.deviations,
        observations=row.observations,
        planned_dds=row.planned_dds,
        held_dds=row.held_dds,
        inspected_items=row.inspected_items,
        conforming_items=row.conforming_items,
        version=row.version,
    )


def list_closings(session: Session, *, scope: Scope) -> list[ClosingRow]:
    """The monthly closings of the scope, the most recent month first."""
    names = names_of(session)
    statement = _scoped(select(MonthlyClosing), MonthlyClosing, scope).order_by(
        MonthlyClosing.month.desc(), MonthlyClosing.project_id
    )
    return [_closing_row(row, names) for row in session.scalars(statement)]


def find_closing(session: Session, *, closing_id: int) -> ClosingRow | None:
    """One closing, to open it for editing (the month is locked)."""
    row = session.get(MonthlyClosing, closing_id)
    return _closing_row(row, names_of(session)) if row is not None else None


def proactive_summary(session: Session, *, scope: Scope, reference_date: date) -> ProactiveSummary:
    """The four indicators of the proactive screen, with the targets per 10 mil HHT in force."""
    closings = [
        ClosingLine(
            project_id=row.project_id,
            month=row.month,
            deviations=row.deviations,
            observations=row.observations,
            planned_dds=row.planned_dds,
            held_dds=row.held_dds,
            inspected_items=row.inspected_items,
            conforming_items=row.conforming_items,
        )
        for row in session.scalars(_scoped(select(MonthlyClosing), MonthlyClosing, scope))
    ]
    targets = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    ).get("metas", {})
    return calculations.summarize_proactive(
        closings,
        hours_lines(session, scope=scope),
        observations_per_ten_thousand=int(
            targets.get("observacoesPor10MilHht", DEFAULT_OBSERVATION_TARGET)
        ),
        deviations_per_ten_thousand=int(
            targets.get("desviosPor10MilHht", DEFAULT_DEVIATION_TARGET)
        ),
    )


def proactive_targets(session: Session, *, reference_date: date) -> tuple[int, int]:
    """The targets per 10 mil HHT in force: observations and deviations."""
    targets = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    ).get("metas", {})
    return (
        int(targets.get("observacoesPor10MilHht", DEFAULT_OBSERVATION_TARGET)),
        int(targets.get("desviosPor10MilHht", DEFAULT_DEVIATION_TARGET)),
    )


# ── Inspections ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InspectionRow:
    """One inspection of the list: names, the items and how many of them are conforming."""

    id: int
    project_id: int
    project_label: str
    inspected_on: date
    area: str
    company_name: str
    responsible_name: str
    note: str
    items: tuple[SafetyInspectionItem, ...]
    version: int
    company_id: int | None
    responsible_id: int

    @property
    def conforming(self) -> int:
        """How many items are conforming."""
        return sum(1 for item in self.items if item.conforming)

    @property
    def conformity_rate(self) -> Decimal | None:
        """Percent of conforming items."""
        return calculations.rate_percent(self.conforming, len(self.items))


def save_inspection(
    session: Session,
    *,
    user: User,
    data: InspectionInput,
    reference_date: date,
    inspection_id: int | None = None,
) -> SaveResult:
    """Record an inspection with its checklist (conforming and non-conforming items), or edit one."""
    rbac.require(user, Permission.WRITE)
    _require_project(session, data.project_id)
    problems = validation.inspection_problems(
        data, register_choices(session), reference_date=reference_date
    )
    if problems or data.inspected_on is None or data.responsible_id is None:
        raise InvalidDataError(problems)
    values = {
        "inspected_on": data.inspected_on,
        "area": data.area.strip(),
        "company_id": data.company_id,
        "responsible_id": data.responsible_id,
        "note": data.note.strip() or None,
    }
    if inspection_id is None:
        record = recording.create(
            session,
            user_id=user.id,
            record=SafetyInspection(project_id=data.project_id, **values),
        )
        created = True
    else:
        record = _existing(session, SafetyInspection, inspection_id)
        recording.update(
            session, user_id=user.id, record=record, changes=values, version=data.version
        )
        for item in _items_of(session, record.id):
            session.delete(item)
        session.flush()
        created = False
    for position, item in enumerate(data.items, start=1):
        session.add(
            SafetyInspectionItem(
                inspection_id=record.id,
                position=position,
                description=item.description.strip(),
                conforming=item.conforming,
                note=item.note.strip() or None,
            )
        )
    session.flush()
    return SaveResult(id=record.id, created=created)


def _items_of(session: Session, inspection_id: int) -> list[SafetyInspectionItem]:
    statement = (
        select(SafetyInspectionItem)
        .where(SafetyInspectionItem.inspection_id == inspection_id)
        .order_by(SafetyInspectionItem.position)
    )
    return list(session.scalars(statement))


def _existing(session: Session, model: Any, record_id: int) -> Any:
    record = session.get(model, record_id)
    if record is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return record


def _inspection_row(session: Session, row: SafetyInspection, names: Names) -> InspectionRow:
    return InspectionRow(
        id=row.id,
        project_id=row.project_id,
        project_label=names.project(row.project_id),
        inspected_on=row.inspected_on,
        area=row.area,
        company_name=names.company(row.company_id),
        responsible_name=names.person(row.responsible_id),
        note=row.note or "",
        items=tuple(_items_of(session, row.id)),
        version=row.version,
        company_id=row.company_id,
        responsible_id=row.responsible_id,
    )


def list_inspections(session: Session, *, scope: Scope) -> list[InspectionRow]:
    """The inspections of the scope, the most recent first."""
    names = names_of(session)
    statement = _scoped(select(SafetyInspection), SafetyInspection, scope).order_by(
        SafetyInspection.inspected_on.desc(), SafetyInspection.id.desc()
    )
    return [_inspection_row(session, row, names) for row in session.scalars(statement)]


def find_inspection(session: Session, *, inspection_id: int) -> InspectionRow | None:
    """One inspection with its checklist, to open it for editing."""
    row = session.get(SafetyInspection, inspection_id)
    return _inspection_row(session, row, names_of(session)) if row is not None else None


# ── Observations ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ObservationRow:
    """One observation of the list; ``observed_name`` is ``None`` for who may not read it (Q35)."""

    id: int
    project_id: int
    project_label: str
    observed_on: date
    area: str
    kind: str
    description: str
    status: str
    company_name: str
    responsible_name: str
    observed_name: str | None
    observed_id: int | None
    company_id: int | None
    responsible_id: int
    version: int


def save_observation(
    session: Session,
    *,
    user: User,
    data: ObservationInput,
    reference_date: date,
    observation_id: int | None = None,
) -> SaveResult:
    """Record a behavior observation, or edit one (a Membro writes; the observed name is restricted)."""
    rbac.require(user, Permission.WRITE)
    _require_project(session, data.project_id)
    problems = validation.observation_problems(
        data, register_choices(session), reference_date=reference_date
    )
    if problems or data.observed_on is None or data.responsible_id is None:
        raise InvalidDataError(problems)
    values = {
        "observed_on": data.observed_on,
        "area": data.area.strip(),
        "company_id": data.company_id,
        "observed_id": data.observed_id,
        "responsible_id": data.responsible_id,
        "kind": data.kind,
        "description": data.description.strip(),
        "status": data.status,
    }
    if observation_id is None:
        record = recording.create(
            session,
            user_id=user.id,
            record=BehaviorObservation(project_id=data.project_id, **values),
        )
        return SaveResult(id=record.id, created=True)
    record = _existing(session, BehaviorObservation, observation_id)
    if not rbac.can(user, Permission.VIEW_RESTRICTED):
        values["observed_id"] = record.observed_id
    recording.update(session, user_id=user.id, record=record, changes=values, version=data.version)
    return SaveResult(id=record.id, created=False)


def _observation_row(row: BehaviorObservation, names: Names, *, restricted: bool) -> ObservationRow:
    return ObservationRow(
        id=row.id,
        project_id=row.project_id,
        project_label=names.project(row.project_id),
        observed_on=row.observed_on,
        area=row.area,
        kind=row.kind,
        description=row.description,
        status=row.status,
        company_name=names.company(row.company_id),
        responsible_name=names.person(row.responsible_id),
        observed_name=names.person(row.observed_id) if restricted else None,
        observed_id=row.observed_id if restricted else None,
        company_id=row.company_id,
        responsible_id=row.responsible_id,
        version=row.version,
    )


def list_observations(session: Session, *, user: User, scope: Scope) -> list[ObservationRow]:
    """The observations of the scope, the most recent first; the observed name only for who may."""
    names = names_of(session)
    restricted = rbac.can(user, Permission.VIEW_RESTRICTED)
    statement = _scoped(select(BehaviorObservation), BehaviorObservation, scope).order_by(
        BehaviorObservation.observed_on.desc(), BehaviorObservation.id.desc()
    )
    return [
        _observation_row(row, names, restricted=restricted) for row in session.scalars(statement)
    ]


def find_observation(session: Session, *, user: User, observation_id: int) -> ObservationRow | None:
    """One observation, to open it for editing."""
    row = session.get(BehaviorObservation, observation_id)
    if row is None:
        return None
    return _observation_row(
        row, names_of(session), restricted=rbac.can(user, Permission.VIEW_RESTRICTED)
    )


# ── DDS ──────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TalkRow:
    """One DDS of the list."""

    id: int
    project_id: int
    project_label: str
    held_on: date
    topic: str
    company_name: str
    responsible_name: str
    participants: int
    company_id: int | None
    responsible_id: int
    version: int


def save_talk(
    session: Session,
    *,
    user: User,
    data: TalkInput,
    reference_date: date,
    talk_id: int | None = None,
) -> SaveResult:
    """Record a DDS (topic, date, who led it, participants), or edit one."""
    rbac.require(user, Permission.WRITE)
    _require_project(session, data.project_id)
    problems = validation.talk_problems(
        data, register_choices(session), reference_date=reference_date
    )
    if problems or data.held_on is None or data.responsible_id is None:
        raise InvalidDataError(problems)
    values = {
        "held_on": data.held_on,
        "topic": data.topic.strip(),
        "company_id": data.company_id,
        "responsible_id": data.responsible_id,
        "participants": data.participants,
    }
    if talk_id is None:
        record = recording.create(
            session, user_id=user.id, record=SafetyTalk(project_id=data.project_id, **values)
        )
        return SaveResult(id=record.id, created=True)
    record = _existing(session, SafetyTalk, talk_id)
    recording.update(session, user_id=user.id, record=record, changes=values, version=data.version)
    return SaveResult(id=record.id, created=False)


def _talk_row(row: SafetyTalk, names: Names) -> TalkRow:
    return TalkRow(
        id=row.id,
        project_id=row.project_id,
        project_label=names.project(row.project_id),
        held_on=row.held_on,
        topic=row.topic,
        company_name=names.company(row.company_id),
        responsible_name=names.person(row.responsible_id),
        participants=row.participants,
        company_id=row.company_id,
        responsible_id=row.responsible_id,
        version=row.version,
    )


def list_talks(session: Session, *, scope: Scope) -> list[TalkRow]:
    """The DDS of the scope, the most recent first."""
    names = names_of(session)
    statement = _scoped(select(SafetyTalk), SafetyTalk, scope).order_by(
        SafetyTalk.held_on.desc(), SafetyTalk.id.desc()
    )
    return [_talk_row(row, names) for row in session.scalars(statement)]


def find_talk(session: Session, *, talk_id: int) -> TalkRow | None:
    """One DDS, to open it for editing."""
    row = session.get(SafetyTalk, talk_id)
    return _talk_row(row, names_of(session)) if row is not None else None


def count_records(session: Session, *, scope: Scope) -> dict[str, int]:
    """How many inspections, observations and DDS the scope holds: the badges of the tabs."""

    def count(model: Any) -> int:
        statement = _scoped(select(func.count()).select_from(model), model, scope)
        return int(session.scalar(statement) or 0)

    return {
        "inspecoes": count(SafetyInspection),
        "observacoes": count(BehaviorObservation),
        "dds": count(SafetyTalk),
        "mensal": count(MonthlyClosing),
    }
