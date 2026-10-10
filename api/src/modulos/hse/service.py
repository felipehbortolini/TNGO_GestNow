"""Business facade of the HSE module: HHT, monthly closing, inspections, observations, DDS,
the occurrence with its investigation, its restricted data and its closing (ISSUE-073) and the
risk analyses with their recommendations (ISSUE-074).

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
  read it; without a reader every month keeps the factor 1;
* ``save_occurrence``: the occurrence registers with the deadlines in force **recorded on the
  row** (D5b) and the restricted data (nome e dados médicos) in the same transaction (Q35);
  ``record_investigation``, ``define_corrective_actions``, ``start_treatment`` and
  ``close_occurrence`` walk the flow Registrada → Em investigação → Ações definidas → Em
  tratamento → Encerrada. The corrective actions are written in the Central in the same
  transaction (origin ``HSE``, D9) and a closed HiPo opens its lesson in Rascunho through the
  facade of Governança (D9). The restricted data and the attachments never leave to whom does
  not hold ``Permission.VIEW_RESTRICTED`` (Q35).
* ``save_analysis``: the risk analysis (APR/JSA or HAZOP) with its participants and its
  recommendations, numbered by type (``APR-``/``HAZOP-``); ``close_recommendation`` closes a
  recommendation manually and concludes its action in the Central, and
  ``create_recommendation_action`` opens that action (origin ``HSE``, reference the study code
  and item the position of the recommendation). The reaction registered for the origin ``HSE``
  keeps both in step (D9): completing the action closes the recommendation on the completion
  date and replanning moves its deadline; an occurrence action (``OCR-``) does not react.
  ``recommendation_share`` is the closed ÷ issued indicator of the panel (ISSUE-075).

The name of the person observed in an observation is personal data: only a manager or an admin
reads it (``Permission.VIEW_RESTRICTED``, Q35); the others see the record without the name.
Nothing here reads the clock: the routes obtain the date from ``core.calendario``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from src.core import attachment_origins, audit, calendario, numbering, origin_links, rbac, recording
from src.core.attachment_origins import OriginRecord, OriginType
from src.core.errors import InvalidDataError
from src.core.export_document import project_label
from src.core.models import AuditEntry
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import origins as action_origins
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.calculations import ActionStatus
from src.modulos.central_acoes.models import Action
from src.modulos.central_acoes.origins import ActionEvent
from src.modulos.central_acoes.validation import CompletionRequest, NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import lessons_models as lessons
from src.modulos.governanca import lessons_service
from src.modulos.governanca.lessons_validation import DraftInput
from src.modulos.hse import calculations, models, validation
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
    Occurrence,
    OccurrenceInvestigation,
    OccurrenceRestricted,
    RiskAnalysis,
    RiskAnalysisParticipant,
    RiskAnalysisRecommendation,
    SafetyInspection,
    SafetyInspectionItem,
    SafetyTalk,
    WorkedHours,
)
from src.modulos.hse.validation import (
    AnalysisFilters,
    AnalysisInput,
    ClosingInput,
    HoursInput,
    InspectionInput,
    ObservationInput,
    RecommendationClosureInput,
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


# ── Ocorrências (ISSUE-073) ──────────────────────────────────────────────────────────────────

OCCURRENCE_ENTITY = "ocorrencia"
OCCURRENCE_HISTORY_ENTITY = "ocorrencia.historico"
# A origem HSE é compartilhada pela ocorrência (OCR-) e pelas análises de risco (APR-/HAZOP-).
HSE_ORIGIN = "HSE"
ACTION_GROUP = "Ação corretiva"

OCCURRENCE_NOT_FOUND_MESSAGE = "Ocorrência não encontrada."
ALREADY_INVESTIGATED_MESSAGE = "Esta ocorrência já foi investigada."
INVESTIGATE_FIRST_MESSAGE = "Investigue a ocorrência antes de definir as ações."
ALREADY_CLOSED_MESSAGE = "Ocorrência já encerrada."
TREATMENT_FIRST_MESSAGE = "Só é possível encerrar depois de iniciado o tratamento."
ACTIONS_FIRST_MESSAGE = "Defina as ações corretivas antes de iniciar o tratamento."
OPEN_ACTIONS_MESSAGE = "Existem {count} ações corretivas em aberto. Conclua-as antes de encerrar."
COMMUNICATION_LATE_MESSAGE = "Comunicação registrada fora do prazo de {hours} horas."

OPEN_STATUSES = (ActionStatus.IN_PROGRESS, ActionStatus.OVERDUE)


def deadlines_in_force(session: Session, *, reference_date: date) -> calculations.DeadlinePolicy:
    """Os prazos de comunicação, investigação e relatório vigentes na data (grupo ``hse``).

    Eles são gravados na ocorrência no registro (D5b): mudar o parâmetro depois muda o próximo
    registro, nunca o prazo de uma ocorrência que já existe.
    """
    values = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    )
    deadlines = values.get("prazos", {})
    return calculations.DeadlinePolicy(
        communication_hours=_positive_int(
            deadlines.get("comunicacaoHoras"), calculations.DEFAULT_COMMUNICATION_HOURS
        ),
        investigation_hours=_positive_int(
            deadlines.get("investigacaoPreliminarHoras"),
            calculations.DEFAULT_INVESTIGATION_HOURS,
        ),
        report_days=_positive_int(
            deadlines.get("relatorioFinalDias"), calculations.DEFAULT_REPORT_DAYS
        ),
    )


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(cast(Any, value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _event_date(occurrence: Occurrence) -> date:
    """A data do evento no fuso do produto: a base dos prazos."""
    return calendario.in_product_timezone(occurrence.happened_at).date()


def _moment(day: date, time_text: str) -> datetime | None:
    """A data e a hora digitadas como o instante local do produto, ou ``None`` quando inválida."""
    parsed = validation.parse_time(time_text)
    if parsed is None:
        return None
    return datetime.combine(day, time(parsed[0], parsed[1]), tzinfo=calendario.PRODUCT_TIMEZONE)


def occurrence_by_code(session: Session, code: str) -> Occurrence | None:
    """A ocorrência pelo código, ou ``None``: o que o registro de anexos e os links perguntam."""
    return session.scalars(select(Occurrence).where(Occurrence.code == code)).one_or_none()


def _occurrence_or_refuse(session: Session, code: str) -> Occurrence:
    occurrence = occurrence_by_code(session, code)
    if occurrence is None:
        raise InvalidDataError(OCCURRENCE_NOT_FOUND_MESSAGE)
    return occurrence


def _role_of(data: validation.OccurrenceInput, *, environmental: bool) -> str | None:
    """A função da pessoa envolvida: só dos tipos que a pedem e nunca do ambiental (sem nome, Q35)."""
    if environmental or data.kind not in validation.TYPES_WITH_ROLE:
        return None
    return data.role.strip() or None


@dataclass(frozen=True)
class OccurrenceSave:
    """O que o registro devolveu: o código e os avisos que a tela mostra como toast."""

    code: str
    avisos: tuple[str, ...]


def save_occurrence(
    session: Session,
    *,
    user: User,
    data: validation.OccurrenceInput,
    reference_date: date,
) -> OccurrenceSave:
    """Registra a ocorrência com o prazo vigente gravado e o restrito na mesma transação.

    O nível 5 (desvios) não tem registro individual: vem do consolidado mensal. O tipo Ambiental
    não tem gravidade real, potencial nem HiPo; a severidade é própria. O nome e os dados médicos
    entram em ``ocorrencia_restrito`` (Q35): o Membro preenche e só Gestor e Admin leem de volta.
    """
    rbac.require(user, Permission.WRITE)
    _require_project(session, data.project_id)
    problems = validation.occurrence_problems(
        data, register_choices(session), reference_date=reference_date
    )
    if problems or data.happened_on is None:
        raise InvalidDataError(problems)
    happened_at = _moment(data.happened_on, data.happened_time)
    if happened_at is None:
        raise InvalidDataError({"hora": validation.TIME_FORMAT})
    project = configuracoes.find_project(session, data.project_id)
    if project is None:
        raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)
    deadlines = deadlines_in_force(session, reference_date=reference_date)
    environmental = data.kind == "Ambiental"
    code = numbering.next_number(
        session, project=project, kind="ocorrencia", reference_date=reference_date
    )
    record = Occurrence(
        project_id=data.project_id,
        company_id=data.company_id,
        code=code,
        happened_at=happened_at,
        kind=data.kind,
        subtype=data.subtype.strip() if environmental else None,
        area=data.area.strip(),
        place=None,
        description="" if environmental else data.description.strip(),
        role=_role_of(data, environmental=environmental),
        people_involved=0 if environmental else (data.people_involved or 0),
        potential_p=None if environmental else data.potential_p,
        potential_i=None if environmental else data.potential_i,
        hipo=bool(data.hipo and not environmental),
        environmental=environmental,
        environmental_severity=data.environmental_severity.strip() if environmental else None,
        immediate_cause=None if environmental else data.immediate_cause.strip(),
        communication_hours=cast(int, data.communication_hours),
        communication_deadline_hours=deadlines.communication_hours,
        investigation_deadline_hours=deadlines.investigation_hours,
        report_deadline_days=deadlines.report_days,
        situation=models.SITUATION_REGISTERED,
    )
    recording.create(session, user_id=user.id, record=record)
    recording.create(
        session,
        user_id=user.id,
        record=OccurrenceRestricted(
            occurrence_id=record.id,
            name=data.name.strip() or None,
            real_gravity=None if environmental else data.real_gravity,
            days_lost=((data.days_lost or 0) if data.kind in validation.TYPES_WITH_DAYS else 0),
            days_charged=(
                (data.days_charged or 0) if data.kind in validation.TYPES_WITH_DAYS else 0
            ),
            cat=bool(data.cat and data.kind in validation.TYPES_WITH_ROLE),
            medical_notes=data.medical_notes.strip() or None,
        ),
    )
    _append_history(session, user=user, occurrence=record, text="Ocorrência registrada.")
    avisos: list[str] = []
    if calculations.communication_overdue(
        record.communication_hours, record.communication_deadline_hours
    ):
        avisos.append(COMMUNICATION_LATE_MESSAGE.format(hours=record.communication_deadline_hours))
    return OccurrenceSave(code=code, avisos=tuple(avisos))


@dataclass(frozen=True)
class InvestigationSave:
    """O que a investigação devolveu: o código e se ela passou do prazo preliminar."""

    code: str
    late: bool


def record_investigation(
    session: Session,
    *,
    user: User,
    code: str,
    data: validation.InvestigationInput,
    reference_date: date,
) -> InvestigationSave:
    """Registra a investigação preliminar (fato) e move a ocorrência para Em investigação."""
    rbac.require(user, Permission.WRITE)
    occurrence = _occurrence_or_refuse(session, code)
    if occurrence.situation != models.SITUATION_REGISTERED:
        raise InvalidDataError(ALREADY_INVESTIGATED_MESSAGE)
    event_date = _event_date(occurrence)
    problems = validation.investigation_problems(
        data, event_date=event_date, reference_date=reference_date
    )
    if problems or data.investigated_on is None:
        raise InvalidDataError(problems)
    recording.create(
        session,
        user_id=user.id,
        record=OccurrenceInvestigation(
            occurrence_id=occurrence.id,
            responsible_id=user.person_id,
            method=data.method,
            root_cause=data.root_cause.strip(),
            investigated_on=data.investigated_on,
        ),
    )
    late = calculations.investigation_overdue(
        event_date, data.investigated_on, occurrence.investigation_deadline_hours
    )
    recording.update(
        session,
        user_id=user.id,
        record=occurrence,
        changes={"situation": models.SITUATION_INVESTIGATING},
        version=occurrence.version,
    )
    text = (
        f"Investigação registrada ({data.method}). "
        f"Causa raiz: {data.root_cause.strip().rstrip('.')}"
    )
    if late:
        text += " · fora do prazo preliminar"
    _append_history(session, user=user, occurrence=occurrence, text=f"{text}.")
    return InvestigationSave(code=code, late=late)


def define_corrective_actions(
    session: Session,
    *,
    user: User,
    code: str,
    actions_input: Sequence[validation.CorrectiveActionInput],
    reference_date: date,
) -> int:
    """Cria as ações corretivas na Central (origem ``HSE``) e move para Ações definidas."""
    rbac.require(user, Permission.WRITE)
    occurrence = _occurrence_or_refuse(session, code)
    if occurrence.situation == models.SITUATION_REGISTERED:
        raise InvalidDataError(INVESTIGATE_FIRST_MESSAGE)
    if occurrence.situation == models.SITUATION_CLOSED:
        raise InvalidDataError(ALREADY_CLOSED_MESSAGE)
    if not actions_input:
        raise InvalidDataError({"acoes": validation.ACTIONS_REQUIRED})
    choices = register_choices(session)
    problems: dict[str, str] = {}
    for index, item in enumerate(actions_input, start=1):
        found = validation.corrective_action_problems(item, choices)
        if len(actions_input) > 1:
            found = {
                key: f"Ação {index}: {message[0].lower()}{message[1:]}"
                for key, message in found.items()
            }
        problems.update(found)
    if problems:
        raise InvalidDataError(problems)
    for item in actions_input:
        sequence = actions.next_origin_item(
            session, origin_kind=HSE_ORIGIN, reference=occurrence.code
        )
        actions.create_action(
            session,
            user=user,
            new=NewAction(
                project_id=occurrence.project_id,
                origin=HSE_ORIGIN,
                origin_ref=occurrence.code,
                subject=item.subject.strip(),
                description=(item.description or "").strip() or None,
                requester_id=user.person_id,
                responsible_id=cast(int, item.responsible_id),
                planned_date=item.planned_date,
                group=ACTION_GROUP,
                item=sequence,
            ),
            reference_date=reference_date,
        )
    if occurrence.situation == models.SITUATION_INVESTIGATING:
        recording.update(
            session,
            user_id=user.id,
            record=occurrence,
            changes={"situation": models.SITUATION_ACTIONS},
            version=occurrence.version,
        )
    count = len(actions_input)
    _append_history(
        session,
        user=user,
        occurrence=occurrence,
        text=f"{count} ação(ões) corretiva(s) criada(s) na Central.",
    )
    return count


def start_treatment(session: Session, *, user: User, code: str) -> None:
    """Move a ocorrência para Em tratamento, depois das ações definidas."""
    rbac.require(user, Permission.WRITE)
    occurrence = _occurrence_or_refuse(session, code)
    if occurrence.situation != models.SITUATION_ACTIONS:
        raise InvalidDataError(ACTIONS_FIRST_MESSAGE)
    recording.update(
        session,
        user_id=user.id,
        record=occurrence,
        changes={"situation": models.SITUATION_TREATING},
        version=occurrence.version,
    )
    _append_history(session, user=user, occurrence=occurrence, text="Tratamento iniciado.")


@dataclass(frozen=True)
class ClosingSave:
    """O que o encerramento devolveu: o código, o relatório fora do prazo e a lição do HiPo."""

    code: str
    report_late: bool
    lesson_code: str | None


def close_occurrence(
    session: Session,
    *,
    user: User,
    code: str,
    data: validation.ClosureInput,
    reference_date: date,
) -> ClosingSave:
    """Encerra a ocorrência com a eficácia verificada; exige as ações corretivas concluídas.

    Um HiPo encerrado exige a lição e a abre em Rascunho pela fachada de Governança, na mesma
    transação (D9), com origem ``HSE`` e o código da ocorrência.
    """
    rbac.require(user, Permission.MANAGE)
    occurrence = _occurrence_or_refuse(session, code)
    if occurrence.situation == models.SITUATION_CLOSED:
        raise InvalidDataError(ALREADY_CLOSED_MESSAGE)
    if occurrence.situation != models.SITUATION_TREATING:
        raise InvalidDataError(TREATMENT_FIRST_MESSAGE)
    open_actions = _open_actions(
        session, user=user, occurrence=occurrence, reference_date=reference_date
    )
    if open_actions:
        raise InvalidDataError(OPEN_ACTIONS_MESSAGE.format(count=open_actions))
    event_date = _event_date(occurrence)
    problems = validation.closure_problems(
        data, event_date=event_date, reference_date=reference_date
    )
    if problems or data.closed_on is None:
        raise InvalidDataError(problems)
    lesson_code = None
    if occurrence.hipo:
        lesson_code = _write_lesson(
            session, user=user, occurrence=occurrence, data=data, reference_date=reference_date
        )
    recording.update(
        session,
        user_id=user.id,
        record=occurrence,
        changes={
            "situation": models.SITUATION_CLOSED,
            "closed_on": data.closed_on,
            "effectiveness": data.effectiveness.strip(),
        },
        version=occurrence.version,
    )
    report_late = calculations.report_overdue(
        data.closed_on,
        event_date=event_date,
        deadline_days=occurrence.report_deadline_days,
        reference_date=reference_date,
    )
    text = f"Ocorrência encerrada. Eficácia: {data.effectiveness.strip()}"
    if lesson_code:
        text += f" Lição {lesson_code} criada em Rascunho."
    _append_history(session, user=user, occurrence=occurrence, text=f"{text.rstrip('.')}.")
    return ClosingSave(code=code, report_late=report_late, lesson_code=lesson_code)


def _open_actions(
    session: Session, *, user: User, occurrence: Occurrence, reference_date: date
) -> int:
    records = actions.actions_of_origin(
        session,
        user=user,
        origin_kind=HSE_ORIGIN,
        reference=occurrence.code,
        reference_date=reference_date,
    )
    return sum(1 for record in records if record.status in OPEN_STATUSES)


def _write_lesson(
    session: Session,
    *,
    user: User,
    occurrence: Occurrence,
    data: validation.ClosureInput,
    reference_date: date,
) -> str:
    """A lição obrigatória do HiPo encerrado, em Rascunho, pela fachada de Governança (D9)."""
    created = lessons_service.create_draft_lesson(
        session,
        user=user,
        project_id=occurrence.project_id,
        draft=DraftInput(
            title=data.lesson_title.strip(),
            kind="A evitar",
            phase="Construção",
            area="SMS",
            origin=lessons.ORIGIN_HSE,
            origin_ref=occurrence.code,
            what_happened=occurrence.description or occurrence.area,
            cause=_root_cause_of(session, occurrence.id),
            recommendation=data.lesson_recommendation.strip(),
            keywords=("HSE", "ocorrência", "HiPo"),
        ),
        reference_date=reference_date,
    )
    return created.code


def _root_cause_of(session: Session, occurrence_id: int) -> str:
    statement = (
        select(OccurrenceInvestigation.root_cause)
        .where(OccurrenceInvestigation.occurrence_id == occurrence_id)
        .order_by(OccurrenceInvestigation.id.desc())
        .limit(1)
    )
    return session.scalar(statement) or ""


# ── A leitura das ocorrências ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OccurrenceRow:
    """Uma ocorrência como a lista e a ficha a mostram, com os prazos já julgados."""

    id: int
    project_id: int
    project_label: str
    code: str
    happened_at: datetime
    area: str
    company_id: int | None
    company_name: str
    kind: str
    level: int | None
    level_name: str
    band: calculations.PotentialBand | None
    potential_p: int | None
    potential_i: int | None
    environmental: bool
    environmental_severity: str | None
    subtype: str | None
    hipo: bool
    role: str | None
    people_involved: int
    description: str
    immediate_cause: str | None
    situation: str
    communication_hours: int
    communication_overdue: bool
    investigation_deadline_hours: int
    investigation_late: str | None
    report_required: bool
    report_deadline_days: int
    report_late: str | None
    closed_on: date | None
    effectiveness: str | None
    version: int

    @property
    def moment_text(self) -> str:
        """``25/09/2026 09:25``: a data e a hora do evento no fuso do produto."""
        moment = calendario.in_product_timezone(self.happened_at)
        return moment.strftime("%d/%m/%Y %H:%M")

    @property
    def overdue(self) -> bool:
        """Fora do prazo: comunicação, investigação ou relatório final."""
        return (
            self.communication_overdue
            or self.investigation_late is not None
            or self.report_late is not None
        )


@dataclass(frozen=True)
class OccurrenceSummary:
    """Os indicadores da tela: total, em aberto, HiPo em aberto e fora do prazo."""

    total: int
    open_count: int
    hipo_open: int
    overdue: int


@dataclass(frozen=True)
class OccurrenceScreen:
    """O que a lista mostra: as linhas do filtro, os indicadores, o universo e os prazos vigentes."""

    rows: tuple[OccurrenceRow, ...]
    summary: OccurrenceSummary
    universe: int
    deadlines: calculations.DeadlinePolicy


def summarize_occurrences(rows: Sequence[OccurrenceRow]) -> OccurrenceSummary:
    """Total, em aberto, HiPo em aberto e fora do prazo do conjunto recebido."""
    open_rows = [row for row in rows if row.situation != models.SITUATION_CLOSED]
    return OccurrenceSummary(
        total=len(rows),
        open_count=len(open_rows),
        hipo_open=sum(1 for row in open_rows if row.hipo),
        overdue=sum(1 for row in rows if row.overdue),
    )


def _matches(record: Occurrence, filters: validation.OccurrenceFilters) -> bool:
    if filters.situation and record.situation != filters.situation:
        return False
    if filters.kind and record.kind != filters.kind:
        return False
    if filters.hipo and not record.hipo:
        return False
    if filters.search:
        wanted = _plain(filters.search)
        haystack = _plain(" ".join((record.code, record.area, record.description or "")))
        return wanted in haystack
    return True


def _investigations_of(
    session: Session, occurrence_ids: Sequence[int]
) -> dict[int, OccurrenceInvestigation]:
    if not occurrence_ids:
        return {}
    statement = (
        select(OccurrenceInvestigation)
        .where(OccurrenceInvestigation.occurrence_id.in_(occurrence_ids))
        .order_by(OccurrenceInvestigation.id)
    )
    return {row.occurrence_id: row for row in session.scalars(statement)}


def _occurrence_row(
    record: Occurrence,
    investigation: OccurrenceInvestigation | None,
    names: Names,
    reference_date: date,
) -> OccurrenceRow:
    level = calculations.pyramid_level(record.kind)
    band = None
    if record.potential_p is not None and record.potential_i is not None:
        band = calculations.potential_band(record.potential_p, record.potential_i)
    event_date = _event_date(record)
    investigation_late: str | None = None
    if investigation is not None:
        if calculations.investigation_overdue(
            event_date, investigation.investigated_on, record.investigation_deadline_hours
        ):
            investigation_late = "fora"
    elif (
        record.situation == models.SITUATION_REGISTERED
        and calculations.investigation_pending_overdue(
            event_date, reference_date, record.investigation_deadline_hours
        )
    ):
        investigation_late = "vencido"
    report_required = calculations.report_required(level, hipo=record.hipo)
    report_late: str | None = None
    if report_required and calculations.report_overdue(
        record.closed_on,
        event_date=event_date,
        deadline_days=record.report_deadline_days,
        reference_date=reference_date,
    ):
        report_late = "fora" if record.closed_on is not None else "vencido"
    return OccurrenceRow(
        id=record.id,
        project_id=record.project_id,
        project_label=names.project(record.project_id),
        code=record.code,
        happened_at=record.happened_at,
        area=record.area,
        company_id=record.company_id,
        company_name=names.company(record.company_id),
        kind=record.kind,
        level=level,
        level_name=calculations.pyramid_level_name(level) if level else "Ambiental",
        band=band,
        potential_p=record.potential_p,
        potential_i=record.potential_i,
        environmental=record.environmental,
        environmental_severity=record.environmental_severity,
        subtype=record.subtype,
        hipo=record.hipo,
        role=record.role,
        people_involved=record.people_involved,
        description=record.description,
        immediate_cause=record.immediate_cause,
        situation=record.situation,
        communication_hours=record.communication_hours,
        communication_overdue=calculations.communication_overdue(
            record.communication_hours, record.communication_deadline_hours
        ),
        investigation_deadline_hours=record.investigation_deadline_hours,
        investigation_late=investigation_late,
        report_required=report_required,
        report_deadline_days=record.report_deadline_days,
        report_late=report_late,
        closed_on=record.closed_on,
        effectiveness=record.effectiveness,
        version=record.version,
    )


def occurrences_screen(
    session: Session,
    *,
    scope: Scope,
    filters: validation.OccurrenceFilters,
    reference_date: date,
) -> OccurrenceScreen:
    """A tela de ocorrências: as linhas do filtro, os indicadores e os prazos vigentes."""
    names = names_of(session)
    statement = _scoped(select(Occurrence), Occurrence, scope).order_by(
        Occurrence.happened_at.desc(), Occurrence.id.desc()
    )
    records = list(session.scalars(statement))
    investigations = _investigations_of(session, [record.id for record in records])
    rows = tuple(
        _occurrence_row(record, investigations.get(record.id), names, reference_date)
        for record in records
        if _matches(record, filters)
    )
    return OccurrenceScreen(
        rows=rows,
        summary=summarize_occurrences(rows),
        universe=len(records),
        deadlines=deadlines_in_force(session, reference_date=reference_date),
    )


@dataclass(frozen=True)
class InvestigationRow:
    """A investigação como a ficha a mostra."""

    method: str
    root_cause: str
    investigated_on: date
    responsible_name: str


@dataclass(frozen=True)
class HistoryLine:
    """Uma linha rica do histórico da ocorrência (a trilha da entidade ``ocorrencia.historico``)."""

    moment: datetime
    author_name: str
    text: str


@dataclass(frozen=True)
class OccurrenceSheet:
    """A ficha da ocorrência: a linha, a investigação, as ações da Central, o histórico e a lição."""

    line: OccurrenceRow
    investigation: InvestigationRow | None
    actions: tuple[actions.ActionRecord, ...]
    history: tuple[HistoryLine, ...]
    lesson_code: str | None

    @property
    def open_actions(self) -> int:
        """Quantas ações corretivas da Central continuam abertas."""
        return sum(1 for record in self.actions if record.status in OPEN_STATUSES)


def occurrence_sheet(
    session: Session, *, user: User, code: str, reference_date: date
) -> OccurrenceSheet | None:
    """A ficha da ocorrência (sem o dado restrito, que tem a rota própria da Q35)."""
    record = occurrence_by_code(session, code)
    if record is None:
        return None
    names = names_of(session)
    investigation = session.scalars(
        select(OccurrenceInvestigation)
        .where(OccurrenceInvestigation.occurrence_id == record.id)
        .order_by(OccurrenceInvestigation.id.desc())
        .limit(1)
    ).first()
    rows = actions.actions_of_origin(
        session,
        user=user,
        origin_kind=HSE_ORIGIN,
        reference=record.code,
        reference_date=reference_date,
    )
    return OccurrenceSheet(
        line=_occurrence_row(record, investigation, names, reference_date),
        investigation=(
            InvestigationRow(
                method=investigation.method,
                root_cause=investigation.root_cause,
                investigated_on=investigation.investigated_on,
                responsible_name=names.person(investigation.responsible_id),
            )
            if investigation is not None
            else None
        ),
        actions=rows,
        history=_history_of(session, record.id),
        lesson_code=lessons_service.code_of_origin(
            session, origin=lessons.ORIGIN_HSE, reference=record.code
        ),
    )


def _history_of(session: Session, occurrence_id: int) -> tuple[HistoryLine, ...]:
    """As linhas ricas do histórico: a trilha da entidade ``ocorrencia.historico`` (D5b)."""
    statement = (
        select(AuditEntry)
        .where(
            AuditEntry.entity == OCCURRENCE_HISTORY_ENTITY,
            AuditEntry.record_id == occurrence_id,
        )
        .order_by(AuditEntry.occurred_at.desc(), AuditEntry.id.desc())
    )
    lines: list[HistoryLine] = []
    for entry in session.scalars(statement):
        text = str((entry.after or {}).get("texto") or "")
        if not text:
            continue
        lines.append(
            HistoryLine(
                moment=calendario.in_product_timezone(entry.occurred_at),
                author_name=audit.author_name(session, entry.user_id),
                text=text,
            )
        )
    return tuple(lines)


def _append_history(
    session: Session,
    *,
    user: User,
    occurrence: Occurrence,
    text: str,
    moment: datetime | None = None,
) -> None:
    """A linha rica do histórico: ela não tem coluna, então anda na trilha de auditoria (D5b)."""
    audit.append(
        session,
        audit.TrailLine(
            user_id=user.id,
            entity=OCCURRENCE_HISTORY_ENTITY,
            record_id=occurrence.id,
            action=audit.CREATED,
            after={"data": _event_date(occurrence).isoformat(), "texto": text},
            project_id=occurrence.project_id,
            occurred_at=moment,
        ),
    )


@dataclass(frozen=True)
class RestrictedRow:
    """O dado restrito da ocorrência (Q35): nome e dados médicos, só para Gestor e Admin."""

    name: str | None
    real_gravity: int | None
    days_lost: int
    days_charged: int
    cat: bool
    medical_notes: str | None
    suggests_hipo: bool


def restricted_view(session: Session, *, user: User, code: str) -> RestrictedRow | None:
    """O bloco restrito da ficha; exige ``VIEW_RESTRICTED`` (403 para os demais, Q35)."""
    rbac.require(user, Permission.VIEW_RESTRICTED)
    record = occurrence_by_code(session, code)
    if record is None:
        return None
    row = session.scalars(
        select(OccurrenceRestricted).where(OccurrenceRestricted.occurrence_id == record.id)
    ).one_or_none()
    if row is None:
        return None
    return RestrictedRow(
        name=row.name,
        real_gravity=row.real_gravity,
        days_lost=row.days_lost,
        days_charged=row.days_charged,
        cat=row.cat,
        medical_notes=row.medical_notes,
        suggests_hipo=not record.hipo
        and calculations.is_high_potential(row.real_gravity, record.potential_i),
    )


# ── Análises de risco (ISSUE-074) ────────────────────────────────────────────────────────────

RECOMMENDATION_GROUP_SUFFIX = " · Recomendação"
ANALYSIS_NOT_FOUND_MESSAGE = "Estudo não encontrado."
RECOMMENDATION_NOT_FOUND_MESSAGE = "Recomendação não encontrada."
ALREADY_CLOSED_RECOMMENDATION_MESSAGE = "Recomendação já fechada."
RECOMMENDATION_ACTION_EXISTS_MESSAGE = "Já existe uma ação na Central para esta recomendação."
# The type of the study decides the numbering kind and the group of the action it creates.
ANALYSIS_NUMBERING_KINDS = {"APR": "apr", "HAZOP": "hazop"}


@dataclass(frozen=True)
class AnalysisSave:
    """O que o registro do estudo devolveu: o código da série do tipo."""

    code: str


@dataclass(frozen=True)
class RecommendationRow:
    """Uma recomendação como a ficha a mostra: os nomes, o atraso e a ação da Central."""

    id: int
    position: int
    description: str
    responsible_id: int
    responsible_name: str
    due_date: date
    situation: str
    closed_on: date | None
    evidence: str | None
    overdue: bool
    version: int
    action: actions.ActionRecord | None

    @property
    def is_closed(self) -> bool:
        """Whether the recommendation is already closed."""
        return self.situation == models.RECOMMENDATION_CLOSED


@dataclass(frozen=True)
class AnalysisRow:
    """Um estudo como a lista e a ficha o mostram, com os participantes e as recomendações."""

    id: int
    project_id: int
    project_label: str
    code: str
    kind: str
    area: str
    title: str
    held_on: date
    participant_ids: tuple[int, ...]
    participant_names: tuple[str, ...]
    recommendations: tuple[RecommendationRow, ...]
    version: int

    @property
    def participants(self) -> int:
        """How many people took part in the study."""
        return len(self.participant_ids)

    @property
    def open_count(self) -> int:
        """Recomendações abertas do estudo."""
        return sum(1 for line in self.recommendations if not line.is_closed)

    @property
    def closed_count(self) -> int:
        """Recomendações fechadas do estudo."""
        return sum(1 for line in self.recommendations if line.is_closed)

    @property
    def overdue_count(self) -> int:
        """Recomendações abertas com o prazo vencido na data de referência."""
        return sum(1 for line in self.recommendations if line.overdue)


@dataclass(frozen=True)
class RecommendationSummary:
    """Abertas, fechadas, atrasadas e o indicador de fechamento de um conjunto de estudos."""

    open: int
    closed: int
    overdue: int
    closed_pct: Decimal | None


@dataclass(frozen=True)
class AnalysisScreen:
    """O que a tela mostra: as linhas do filtro, o universo de estudos e o resumo das recomendações."""

    rows: tuple[AnalysisRow, ...]
    universe: int
    summary: RecommendationSummary


@dataclass(frozen=True)
class AnalysisSheet:
    """A ficha do estudo: a linha com os participantes e as recomendações com a ação da Central."""

    line: AnalysisRow


@dataclass(frozen=True)
class RecommendationShare:
    """Recomendações fechadas ÷ emitidas de um escopo: o indicador do painel (ISSUE-075)."""

    closed: int
    emitted: int
    pct: Decimal | None


def analysis_by_code(
    session: Session, code: str, *, project_id: int | None = None
) -> RiskAnalysis | None:
    """O estudo pelo código, ou ``None``; o projeto desempata a série quando ela se repete."""
    statement = select(RiskAnalysis).where(RiskAnalysis.code == code)
    if project_id is not None:
        statement = statement.where(RiskAnalysis.project_id == project_id)
    return session.scalars(statement.order_by(RiskAnalysis.id)).first()


def _analysis_or_refuse(
    session: Session, code: str, *, project_id: int | None = None
) -> RiskAnalysis:
    analysis = analysis_by_code(session, code, project_id=project_id)
    if analysis is None:
        raise InvalidDataError(ANALYSIS_NOT_FOUND_MESSAGE)
    return analysis


def _recommendation_or_refuse(
    session: Session, analysis: RiskAnalysis, position: int
) -> RiskAnalysisRecommendation:
    record = session.scalars(
        select(RiskAnalysisRecommendation)
        .where(
            RiskAnalysisRecommendation.analysis_id == analysis.id,
            RiskAnalysisRecommendation.position == position,
        )
        .order_by(RiskAnalysisRecommendation.id)
    ).first()
    if record is None:
        raise InvalidDataError(RECOMMENDATION_NOT_FOUND_MESSAGE)
    return record


def save_analysis(
    session: Session,
    *,
    user: User,
    data: AnalysisInput,
    reference_date: date,
) -> AnalysisSave:
    """Registra o estudo com os participantes e as recomendações na mesma transação.

    O código nasce da série do tipo no projeto (``APR-<padrão da ata>-NNNN`` ou
    ``HAZOP-<padrão da ata>-NNNN``) e cada recomendação nasce Aberta.
    """
    rbac.require(user, Permission.WRITE)
    _require_project(session, data.project_id)
    problems = validation.analysis_problems(
        data, register_choices(session), reference_date=reference_date
    )
    if problems or data.held_on is None:
        raise InvalidDataError(problems)
    project = configuracoes.find_project(session, data.project_id)
    if project is None:
        raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)
    code = numbering.next_number(
        session,
        project=project,
        kind=ANALYSIS_NUMBERING_KINDS[data.kind],
        reference_date=reference_date,
    )
    record = RiskAnalysis(
        project_id=data.project_id,
        code=code,
        kind=data.kind,
        area=data.area.strip(),
        title=data.title.strip(),
        held_on=data.held_on,
    )
    recording.create(session, user_id=user.id, record=record)
    for person_id in data.participant_ids:
        recording.create(
            session,
            user_id=user.id,
            record=RiskAnalysisParticipant(analysis_id=record.id, person_id=person_id),
        )
    for position, item in enumerate(data.recommendations, start=1):
        recording.create(
            session,
            user_id=user.id,
            record=RiskAnalysisRecommendation(
                analysis_id=record.id,
                responsible_id=cast(int, item.responsible_id),
                position=position,
                description=item.description.strip(),
                due_date=cast(date, item.due_date),
                situation=models.RECOMMENDATION_OPEN,
            ),
        )
    return AnalysisSave(code=code)


def _participants_of(
    session: Session, analysis_ids: Sequence[int]
) -> dict[int, list[RiskAnalysisParticipant]]:
    if not analysis_ids:
        return {}
    statement = (
        select(RiskAnalysisParticipant)
        .where(RiskAnalysisParticipant.analysis_id.in_(analysis_ids))
        .order_by(RiskAnalysisParticipant.id)
    )
    grouped: dict[int, list[RiskAnalysisParticipant]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.analysis_id, []).append(row)
    return grouped


def _recommendations_of(
    session: Session, analysis_ids: Sequence[int]
) -> dict[int, list[RiskAnalysisRecommendation]]:
    if not analysis_ids:
        return {}
    statement = (
        select(RiskAnalysisRecommendation)
        .where(RiskAnalysisRecommendation.analysis_id.in_(analysis_ids))
        .order_by(RiskAnalysisRecommendation.analysis_id, RiskAnalysisRecommendation.position)
    )
    grouped: dict[int, list[RiskAnalysisRecommendation]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.analysis_id, []).append(row)
    return grouped


def _recommendation_row(
    record: RiskAnalysisRecommendation,
    action: actions.ActionRecord | None,
    names: Names,
    reference_date: date,
) -> RecommendationRow:
    return RecommendationRow(
        id=record.id,
        position=record.position,
        description=record.description,
        responsible_id=record.responsible_id,
        responsible_name=names.person(record.responsible_id),
        due_date=record.due_date,
        situation=record.situation,
        closed_on=record.closed_on,
        evidence=record.evidence,
        overdue=calculations.recommendation_overdue(
            calculations.RecommendationLine(situation=record.situation, due_date=record.due_date),
            reference_date,
        ),
        version=record.version,
        action=action,
    )


def _analysis_row(
    record: RiskAnalysis,
    names: Names,
    *,
    participants: Sequence[RiskAnalysisParticipant],
    recommendations: Sequence[RiskAnalysisRecommendation],
    actions_by_position: Mapping[str, actions.ActionRecord],
    reference_date: date,
) -> AnalysisRow:
    return AnalysisRow(
        id=record.id,
        project_id=record.project_id,
        project_label=names.project(record.project_id),
        code=record.code,
        kind=record.kind,
        area=record.area,
        title=record.title,
        held_on=record.held_on,
        participant_ids=tuple(item.person_id for item in participants),
        participant_names=tuple(names.person(item.person_id) for item in participants),
        recommendations=tuple(
            _recommendation_row(
                item, actions_by_position.get(str(item.position)), names, reference_date
            )
            for item in recommendations
        ),
        version=record.version,
    )


def _matches_analysis(record: RiskAnalysis, filters: AnalysisFilters, *, open_count: int) -> bool:
    if filters.kind and record.kind != filters.kind:
        return False
    if filters.open_only and open_count == 0:
        return False
    if filters.search:
        wanted = _plain(filters.search)
        haystack = _plain(" ".join((record.code, record.title, record.area)))
        return wanted in haystack
    return True


def _summarize_recommendations(
    rows: Sequence[AnalysisRow], reference_date: date
) -> RecommendationSummary:
    counts = calculations.count_recommendations(
        (
            calculations.RecommendationLine(situation=line.situation, due_date=line.due_date)
            for row in rows
            for line in row.recommendations
        ),
        reference_date,
    )
    return RecommendationSummary(
        open=counts.open,
        closed=counts.closed,
        overdue=counts.overdue,
        closed_pct=calculations.closed_recommendations_pct(counts.closed, counts.total),
    )


def analyses_screen(
    session: Session,
    *,
    scope: Scope,
    filters: AnalysisFilters,
    reference_date: date,
) -> AnalysisScreen:
    """A tela de análises: as linhas do filtro, o universo de estudos e o resumo das recomendações."""
    names = names_of(session)
    records = list(
        session.scalars(
            _scoped(select(RiskAnalysis), RiskAnalysis, scope).order_by(
                RiskAnalysis.held_on.desc(), RiskAnalysis.id.desc()
            )
        )
    )
    ids = [record.id for record in records]
    participants = _participants_of(session, ids)
    recommendations = _recommendations_of(session, ids)
    rows: list[AnalysisRow] = []
    for record in records:
        found = recommendations.get(record.id, [])
        open_count = sum(1 for item in found if item.situation != models.RECOMMENDATION_CLOSED)
        if not _matches_analysis(record, filters, open_count=open_count):
            continue
        rows.append(
            _analysis_row(
                record,
                names,
                participants=participants.get(record.id, []),
                recommendations=found,
                actions_by_position={},
                reference_date=reference_date,
            )
        )
    return AnalysisScreen(
        rows=tuple(rows),
        universe=len(records),
        summary=_summarize_recommendations(rows, reference_date),
    )


def analysis_sheet(
    session: Session,
    *,
    user: User,
    code: str,
    reference_date: date,
    project_id: int | None = None,
) -> AnalysisSheet | None:
    """A ficha do estudo, com as recomendações e o status das ações da Central de cada uma."""
    record = analysis_by_code(session, code, project_id=project_id)
    if record is None:
        return None
    names = names_of(session)
    actions_by_position = {
        (action.item or "").strip(): action
        for action in actions.actions_of_origin(
            session,
            user=user,
            origin_kind=HSE_ORIGIN,
            reference=record.code,
            reference_date=reference_date,
        )
    }
    return AnalysisSheet(
        line=_analysis_row(
            record,
            names,
            participants=_participants_of(session, [record.id]).get(record.id, []),
            recommendations=_recommendations_of(session, [record.id]).get(record.id, []),
            actions_by_position=actions_by_position,
            reference_date=reference_date,
        )
    )


def close_recommendation(
    session: Session,
    *,
    user: User,
    code: str,
    position: int,
    data: RecommendationClosureInput,
    reference_date: date,
    project_id: int | None = None,
) -> None:
    """Fecha a recomendação com a data de conclusão e a evidência, e conclui a ação vinculada.

    O fechamento manual move a recomendação para Fechada e conclui a ação da Central na mesma
    transação (D9): a sincronização vale nas duas direções. Uma recomendação já fechada é
    recusada (422).
    """
    rbac.require(user, Permission.WRITE)
    analysis = _analysis_or_refuse(session, code, project_id=project_id)
    recommendation = _recommendation_or_refuse(session, analysis, position)
    if recommendation.situation == models.RECOMMENDATION_CLOSED:
        raise InvalidDataError(ALREADY_CLOSED_RECOMMENDATION_MESSAGE)
    problems = validation.recommendation_closure_problems(data, reference_date=reference_date)
    if problems or data.closed_on is None:
        raise InvalidDataError(problems)
    recording.update(
        session,
        user_id=user.id,
        record=recommendation,
        changes={
            "situation": models.RECOMMENDATION_CLOSED,
            "closed_on": data.closed_on,
            "evidence": data.evidence.strip() or None,
        },
        version=recommendation.version,
    )
    _complete_linked_action(
        session,
        user=user,
        analysis=analysis,
        position=position,
        completed_on=data.closed_on,
        reference_date=reference_date,
    )


def _complete_linked_action(
    session: Session,
    *,
    user: User,
    analysis: RiskAnalysis,
    position: int,
    completed_on: date,
    reference_date: date,
) -> None:
    """A recomendação fechou na tela do estudo: conclui a ação que a representa, se ainda aberta."""
    record = _actions_by_position(
        session, user=user, analysis=analysis, reference_date=reference_date
    ).get(str(position))
    if record is None or record.completed_on is not None:
        return
    actions.complete_action(
        session,
        user=user,
        request=CompletionRequest(
            action_id=record.id, completed_on=completed_on, version=record.version
        ),
        reference_date=reference_date,
    )


def _actions_by_position(
    session: Session, *, user: User, analysis: RiskAnalysis, reference_date: date
) -> dict[str, actions.ActionRecord]:
    return {
        (record.item or "").strip(): record
        for record in actions.actions_of_origin(
            session,
            user=user,
            origin_kind=HSE_ORIGIN,
            reference=analysis.code,
            reference_date=reference_date,
        )
    }


def create_recommendation_action(
    session: Session,
    *,
    user: User,
    code: str,
    position: int,
    reference_date: date,
    project_id: int | None = None,
) -> actions.ActionRecord:
    """Cria a ação da recomendação na Central (origem ``HSE``), na mesma transação (D9).

    O ``item`` da ação é a ordem da recomendação e o grupo, ``<TIPO> · Recomendação``; a
    descrição do estudo vai como descrição da ação. Uma recomendação tem no máximo uma ação:
    a segunda tentativa é recusada com a mensagem do protótipo.
    """
    rbac.require(user, Permission.WRITE)
    analysis = _analysis_or_refuse(session, code, project_id=project_id)
    recommendation = _recommendation_or_refuse(session, analysis, position)
    existing = _actions_by_position(
        session, user=user, analysis=analysis, reference_date=reference_date
    )
    if str(recommendation.position) in existing:
        raise InvalidDataError(RECOMMENDATION_ACTION_EXISTS_MESSAGE)
    return actions.create_action(
        session,
        user=user,
        new=NewAction(
            project_id=analysis.project_id,
            origin=HSE_ORIGIN,
            origin_ref=analysis.code,
            item=str(recommendation.position),
            group=f"{analysis.kind}{RECOMMENDATION_GROUP_SUFFIX}",
            subject=recommendation.description,
            description=f"{analysis.title} ({analysis.area})",
            requester_id=user.person_id,
            responsible_id=recommendation.responsible_id,
            planned_date=recommendation.due_date,
        ),
        reference_date=reference_date,
    )


def recommendation_share(session: Session, *, scope: Scope) -> RecommendationShare:
    """Recomendações fechadas ÷ emitidas do escopo: o indicador do painel HSE (ISSUE-075)."""
    statement = select(RiskAnalysisRecommendation.situation).join(
        RiskAnalysis, RiskAnalysis.id == RiskAnalysisRecommendation.analysis_id
    )
    if scope.project_id is not None:
        statement = statement.where(RiskAnalysis.project_id == scope.project_id)
    situations = list(session.scalars(statement))
    closed = sum(1 for situation in situations if situation == models.RECOMMENDATION_CLOSED)
    return RecommendationShare(
        closed=closed,
        emitted=len(situations),
        pct=calculations.closed_recommendations_pct(closed, len(situations)),
    )


def react_to_hse_action(session: Session, user: User, action: Action, event: ActionEvent) -> None:
    """A ação mudou na Central: a recomendação do estudo espelha a conclusão ou o replanejamento.

    A origem ``HSE`` é compartilhada com as ocorrências (ISSUE-073): uma ação ``OCR-`` não
    reage aqui. A conclusão fecha a recomendação na data da conclusão; o replanejamento move o
    prazo; uma recomendação já fechada não muda.
    """
    reference = (action.origin_ref or "").strip()
    if not reference.startswith(("APR-", "HAZOP-")):
        return
    item = (action.item or "").strip()
    if not item.isdigit():
        return
    recommendation = _recommendation_of_action(session, action, position=int(item))
    if recommendation is None or recommendation.situation == models.RECOMMENDATION_CLOSED:
        return
    if event is ActionEvent.COMPLETED and action.completed_on is not None:
        recording.update(
            session,
            user_id=user.id,
            record=recommendation,
            changes={
                "situation": models.RECOMMENDATION_CLOSED,
                "closed_on": action.completed_on,
            },
            version=recommendation.version,
        )
    elif event is ActionEvent.REPLANNED and action.replanned_date is not None:
        recording.update(
            session,
            user_id=user.id,
            record=recommendation,
            changes={"due_date": action.replanned_date},
            version=recommendation.version,
        )


def _recommendation_of_action(
    session: Session, action: Action, *, position: int
) -> RiskAnalysisRecommendation | None:
    statement = (
        select(RiskAnalysisRecommendation)
        .join(RiskAnalysis, RiskAnalysis.id == RiskAnalysisRecommendation.analysis_id)
        .where(
            RiskAnalysis.project_id == action.project_id,
            RiskAnalysis.code == (action.origin_ref or "").strip(),
            RiskAnalysisRecommendation.position == position,
        )
    )
    return session.scalars(statement).one_or_none()


# ── Integrações (D9, D5a) ────────────────────────────────────────────────────────────────────


def read_occurrence_origin(session: Session, *, user: User, record_id: int) -> OriginRecord | None:
    """A leitura dos anexos de uma ocorrência: restrita, porque carregam dado pessoal (Q35).

    Quem grava ainda envia (a rota de envio só pede ``WRITE``); listar e baixar exige
    ``VIEW_RESTRICTED``, que a plataforma confere com o ``restricted`` devolvido aqui.
    """
    occurrence = session.get(Occurrence, record_id)
    if occurrence is None:
        return None
    rbac.require_module(user, MODULE)
    return OriginRecord(project_id=occurrence.project_id, restricted=True)


def _occurrence_exists(session: Session, reference: str) -> bool:
    """A ocorrência que uma lição de Governança aponta, pelo código (D9)."""
    return session.scalar(select(Occurrence.id).where(Occurrence.code == reference)) is not None


def _hse_origin_link(reference: origin_links.OriginRef) -> str | None:
    """A tela da origem pelo prefixo do código: o estudo (APR-/HAZOP-) ou a ocorrência (OCR-)."""
    screen = (
        "hse/analises_risco"
        if reference.reference.startswith(("APR-", "HAZOP-"))
        else "hse/ocorrencias"
    )
    return origin_links.link_to_screen(screen, busca=reference.reference)


origin_links.register(origin_links.OriginLinkType(kind=HSE_ORIGIN, build=_hse_origin_link))

attachment_origins.register(
    OriginType(table=OCCURRENCE_ENTITY, module=MODULE, read=read_occurrence_origin)
)

lessons_service.register_origin(lessons.ORIGIN_HSE, _occurrence_exists)

# A reação da origem HSE (compartilhada com as ocorrências): a ação concluída fecha a
# recomendação do estudo e o replanejamento move o prazo (D9, padrão da ISSUE-049).
action_origins.register_reaction(HSE_ORIGIN, react_to_hse_action)
