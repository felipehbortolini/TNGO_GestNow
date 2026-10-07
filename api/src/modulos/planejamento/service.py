"""Business facade for the Planning module.

Relato do período (ISSUE-044, HU-046): the weekly (ISO week) and the monthly (civil month)
report of a project, two distinct records. A person registers what was done in the period,
what comes in the next one and the attention points, each with the risk tied to it (a threat
or an opportunity, the planning reading with no link to the 05 register). The period goes
from the start of the project to the current one: a future period is refused, a duplicate is
refused (the existing one is edited) and the type and the period never change after creation.

Writes go through here, in the transaction of the request. The report is an aggregate: the
activities and the attention points are its children, edited together and protected by the
``versao`` of the root, so the facade composes ``versioning`` and ``audit`` itself (the trail
carries the whole content, before and after). Nothing reads the clock: the caller passes the
date of reference, obtained from ``core.calendario``.


The 6WLA (ISSUE-045): the board of the six weeks, the activities and their
restrictions. Every function receives the session, the user, the scope and the
reference date as arguments; nothing here reads the clock (D6). Writing goes
through ``core.recording`` (trail, version and transaction together), and the
registers of other modules (projects, companies, people, disciplines) are read
through the facade of Configurações.

The WBS (ISSUE-036): the tree of the project (area, subarea and package) and the
read-only tree of the Portfólio (portfolio, project with its weight in the
portfolio and the areas), the dictionary of the package and the indicator of the
SMs still to incorporate. The real of each package comes from the current
entries of its measuring criterion (D5b), the nodes add up the children by
weight (the 100% rule) and the deviation uses the bands of the parameters in
force. The weight of the project in the portfolio and the EAC item of the
dictionary come from the Financeiro facade, imported locally (D9); the approved
SMs come from the Governança facade. Nothing here reads the clock (D6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, selectinload

from src.core import audit, calendario, rbac, recording, versioning
from src.core.audit import TrailLine
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.import_values import normalize_text
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, validation
from src.modulos.planejamento.models import (
    EapBreakdown,
    EapItem,
    EapItemStep,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
    Lookahead,
    LookaheadConstraint,
    LookaheadWeek,
    Report,
    ReportActivity,
    ReportPoint,
)
from src.modulos.planejamento.validation import MONTHLY, WEEKLY, PointInput

if TYPE_CHECKING:
    from src.modulos.governanca.service import ChangeEapSource

MODULE = "planejamento"


# The group of an activity: what was done in the period or what comes in the next one.
GROUP_PERIOD = "periodo"


GROUP_NEXT = "proximo"


NOT_FOUND_MESSAGE = "Relato não encontrado."


UNKNOWN_PROJECT_MESSAGE = "O projeto do relato não existe."


@dataclass(frozen=True)
class ReportDraft:
    """What a person typed: the type and period, the two lists of activities and the points."""

    kind: str = ""
    period: str = ""
    activities: tuple[str, ...] = ()
    next_activities: tuple[str, ...] = ()
    points: tuple[PointInput, ...] = ()


@dataclass(frozen=True)
class SaveRequest:
    """A save: the draft and, when it edits a report, its id and the version the screen opened."""

    draft: ReportDraft
    report_id: int | None = None
    version: str | None = None


@dataclass(frozen=True)
class ReportFilter:
    """The filter of the list: the type (empty is all) and the text to search for."""

    kind: str = ""
    search: str = ""


@dataclass(frozen=True)
class ReportView:
    """A report as the screens read it: identity, labels, content, counts and who wrote it last."""

    id: int
    project_id: int
    project_code: str
    project_name: str
    kind: str
    period: str
    name: str
    short_name: str
    next_name: str
    activities: tuple[str, ...]
    next_activities: tuple[str, ...]
    points: tuple[PointInput, ...]
    threats: int
    opportunities: int
    version: int
    updated_at: datetime
    updated_by: str

    @property
    def project_label(self) -> str:
        """``TN-2026-014 · Nome do projeto``: how the Portfólio names the project of a row."""
        return f"{self.project_code} · {self.project_name}"


@dataclass(frozen=True)
class NewReportChoices:
    """What the form of a new report offers: the project it will belong to and its periods."""

    project_label: str
    options: list[calculations.PeriodOption]


@dataclass(frozen=True)
class PeriodCoverage:
    """Whether a closed period was reported: how many projects of the scope did, of how many."""

    period: str
    name: str
    short_name: str
    registered: int
    expected: int

    @property
    def is_complete(self) -> bool:
        """Whether every project of the scope reported the period."""
        return self.registered >= self.expected


@dataclass(frozen=True)
class ReportSummary:
    """The indicators of the screen (HU-046): the last closed week and month, the points and the count."""

    previous_week: PeriodCoverage
    previous_month: PeriodCoverage
    last_weekly: ReportView | None
    reference_points: int | None
    total: int
    weekly_total: int
    monthly_total: int
    expected_total: int
    is_portfolio: bool


# ── Reading ────────────────────────────────────────────────────────────────


def list_reports(
    session: Session,
    *,
    user: User,
    scope: Scope,
    report_filter: ReportFilter | None = None,
) -> list[ReportView]:
    """The reports of the scope, the most recent period first, after the type and the search."""
    rbac.require_module(user, MODULE)
    chosen = report_filter or ReportFilter()
    views = _views(session, _reports_in(session, scope))
    kept = [view for view in views if _passes(view, chosen)]
    return sorted(
        kept,
        key=lambda view: (
            *calculations.report_order_key(view.kind, view.period),
            view.project_code,
        ),
    )


def report_summary(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> ReportSummary:
    """The indicators of the screen, read on the reference date for the projects of the scope."""
    rbac.require_module(user, MODULE)
    projects = _projects_in(session, scope)
    views = _views(session, _reports_in(session, scope))
    weekly = [view for view in views if view.kind == WEEKLY]
    last_weekly = max(weekly, key=lambda view: (view.period, view.id), default=None)
    return ReportSummary(
        previous_week=_coverage(WEEKLY, projects, views, reference_date),
        previous_month=_coverage(MONTHLY, projects, views, reference_date),
        last_weekly=last_weekly,
        reference_points=_reference_points(weekly, last_weekly),
        total=len(views),
        weekly_total=len(weekly),
        monthly_total=len(views) - len(weekly),
        expected_total=sum(
            calculations.expected_report_count(kind, project.start_date, reference_date)
            for project in projects.values()
            for kind in validation.KINDS
        ),
        is_portfolio=scope.is_portfolio,
    )


def get_report(session: Session, *, user: User, scope: Scope, report_id: int) -> ReportView:
    """One report of the scope, or 422 when there is none with that id in it."""
    rbac.require_module(user, MODULE)
    return _views(session, [_find(session, scope, report_id)])[0]


def find_report(
    session: Session, *, user: User, scope: Scope, kind: str, period: str
) -> ReportView | None:
    """The report of the project of the scope for the type and period, or ``None`` when absent.

    It is the address of the report manager's modal: type, period and open. In the Portfólio
    there is no project to look in, so there is no answer.
    """
    rbac.require_module(user, MODULE)
    if scope.project_id is None:
        return None
    report = _report_of(session, project_id=scope.project_id, kind=kind, period=period)
    return _views(session, [report])[0] if report is not None else None


def period_choices(
    session: Session, *, user: User, scope: Scope, kind: str, reference_date: date
) -> NewReportChoices:
    """The project of the scope and the periods the form offers for a new report of the type."""
    rbac.require_module(user, MODULE)
    project = _project(session, scope.require_project())
    taken = session.scalars(
        select(Report.period).where(Report.project_id == project.id, Report.kind == kind)
    ).all()
    return NewReportChoices(
        project_label=f"{project.code} · {project.name}",
        options=calculations.period_options(
            kind, project_start=project.start_date, reference_date=reference_date, taken=taken
        ),
    )


def previous_report(
    session: Session, *, user: User, scope: Scope, request: SaveRequest
) -> ReportView | None:
    """The report "Copiar do período anterior" brings: the latest of the same type before the period.

    The project and the period are those of the report being edited, or of the project of the
    scope and the period chosen in the form of a new one.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    project_id, kind, period = _target(session, scope, request)
    candidates = list(
        session.scalars(
            select(Report)
            .options(selectinload(Report.activities), selectinload(Report.points))
            .where(Report.project_id == project_id, Report.kind == kind)
        )
    )
    earlier = calculations.latest_period_before((report.period for report in candidates), period)
    chosen = next((report for report in candidates if report.period == earlier), None)
    return _views(session, [chosen])[0] if chosen is not None else None


# ── Writing ────────────────────────────────────────────────────────────────


def save_report(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: SaveRequest,
    reference_date: date,
) -> ReportView:
    """Create the report or save the edit of one, or refuse with 422 per field.

    Writing asks for Membro. A new report belongs to the project of the scope (in the Portfólio
    the screen asks for the project first). The type and the period of an existing report are
    kept: only the content changes. A stale version is refused with 409.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    existing = _find(session, scope, request.report_id) if request.report_id is not None else None
    project_id = existing.project_id if existing is not None else scope.require_project()
    kind = existing.kind if existing is not None else request.draft.kind
    period = existing.period if existing is not None else request.draft.period
    content = _content_of(request.draft)
    errors = _save_errors(
        session,
        project=_project(session, project_id),
        draft=ReportDraft(kind=kind, period=period, **content),
        is_new=existing is None,
        reference_date=reference_date,
    )
    if errors:
        raise InvalidDataError(errors)
    if existing is not None:
        report = _edit(
            session, user=user, report=existing, version=request.version, content=content
        )
    else:
        report = _assemble(
            project_id=project_id, kind=kind, period=period, person_id=user.person_id
        )
        fill_report(report, **content)
        insert_report(session, user_id=user.id, report=report)
    return _views(session, [report])[0]


def insert_report(session: Session, *, user_id: int, report: Report) -> Report:
    """Write an assembled report with the trail of its creation (the whole content, after).

    The screen creates through ``save_report``; the demonstration load calls this one, with the
    authors and the times of the prototype already on the report.
    """
    session.add(report)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user_id,
            entity=Report.__tablename__,
            record_id=report.id,
            action=audit.CREATED,
            after=_aggregate(report),
            project_id=report.project_id,
        ),
    )
    return report


def delete_report(
    session: Session, *, user: User, scope: Scope, report_id: int, version: str | None
) -> ReportView:
    """Delete the report, which leaves the period pending again; asks for Gestor.

    Returns the report as it was, for the message. A stale version is refused with 409.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    report = _find(session, scope, report_id)
    view = _views(session, [report])[0]
    before = _aggregate(report)
    versioning.require(session, report, version)
    session.delete(report)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=Report.__tablename__,
            record_id=view.id,
            action=audit.DELETED,
            before=before,
            project_id=view.project_id,
        ),
    )
    return view


# ── Rules of the save ──────────────────────────────────────────────────────


def _target(session: Session, scope: Scope, request: SaveRequest) -> tuple[int, str, str]:
    """The project, the type and the period a save is about: the report's own when it exists."""
    if request.report_id is None:
        return scope.require_project(), request.draft.kind, request.draft.period
    report = _find(session, scope, request.report_id)
    return report.project_id, report.kind, report.period


def _content_of(draft: ReportDraft) -> dict[str, Any]:
    """The content of the draft cleaned the way it is saved: lines trimmed, blank points dropped."""
    return {
        "activities": tuple(validation.clean_lines(draft.activities)),
        "next_activities": tuple(validation.clean_lines(draft.next_activities)),
        "points": tuple(validation.non_blank_points(draft.points)),
    }


def _save_errors(
    session: Session,
    *,
    project: configuracoes.ProjectSummary,
    draft: ReportDraft,
    is_new: bool,
    reference_date: date,
) -> dict[str, str]:
    """Every message of a save, by the field of the form: type, period, activities and points."""
    errors = validation.validate_kind(draft.kind)
    if not errors:
        problem = _period_problem(
            session, project=project, draft=draft, is_new=is_new, reference_date=reference_date
        )
        if problem:
            errors[validation.FIELD_PERIOD] = problem
    errors.update(validation.validate_activities(draft.activities, draft.next_activities))
    errors.update(validation.validate_points(draft.points))
    return errors


def _period_problem(
    session: Session,
    *,
    project: configuracoes.ProjectSummary,
    draft: ReportDraft,
    is_new: bool,
    reference_date: date,
) -> str | None:
    """The message for the period: not valid, before the project, in the future or already reported."""
    problem = calculations.report_period_error(
        draft.kind, draft.period, project_start=project.start_date, reference_date=reference_date
    )
    if problem is not None or not is_new:
        return problem
    already = _report_of(session, project_id=project.id, kind=draft.kind, period=draft.period)
    return _duplicate_message(draft.kind) if already is not None else None


def _duplicate_message(kind: str) -> str:
    return f"Já existe relato {kind.lower()} para este período; edite o registro existente."


def _assemble(*, project_id: int, kind: str, period: str, person_id: int) -> Report:
    """A report not yet written, authored and stamped now."""
    moment = calendario.now()
    return Report(
        project_id=project_id,
        created_by_id=person_id,
        updated_by_id=person_id,
        kind=kind,
        period=period,
        created_at=moment,
        updated_at=moment,
    )


def fill_report(
    report: Report,
    *,
    activities: Sequence[str],
    next_activities: Sequence[str],
    points: Sequence[PointInput],
) -> None:
    """Replace the children of the report with the content, in the order given.

    The screen goes through ``save_report``; the demonstration load assembles its reports with
    this and writes them with ``insert_report``.
    """
    report.activities = [
        *_activity_rows(GROUP_PERIOD, activities),
        *_activity_rows(GROUP_NEXT, next_activities),
    ]
    report.points = [
        ReportPoint(
            order=order, description=point.description, nature=point.nature, risk=point.risk
        )
        for order, point in enumerate(points, start=1)
    ]


def _activity_rows(group: str, lines: Sequence[str]) -> list[ReportActivity]:
    return [
        ReportActivity(group=group, order=order, text=line)
        for order, line in enumerate(lines, start=1)
    ]


def _edit(
    session: Session,
    *,
    user: User,
    report: Report,
    version: str | None,
    content: dict[str, Any],
) -> Report:
    """Save the content of an existing report after the version check, leaving the trail."""
    before = _aggregate(report)
    versioning.require(session, report, version)
    fill_report(report, **content)
    report.updated_by_id = user.person_id
    report.updated_at = calendario.now()
    versioning.advance(report)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=Report.__tablename__,
            record_id=report.id,
            action=audit.UPDATED,
            before=before,
            after=_aggregate(report),
            project_id=report.project_id,
        ),
    )
    return report


def _aggregate(report: Report) -> dict[str, Any]:
    """The report and its children as the trail keeps them, keyed by the Portuguese names."""
    return {
        **audit.snapshot(report),
        "atividades": [
            {"grupo": row.group, "ordem": row.order, "texto": row.text} for row in report.activities
        ],
        "pontos": [
            {
                "ordem": row.order,
                "descricao": row.description,
                "natureza": row.nature,
                "risco": row.risk,
            }
            for row in report.points
        ],
    }


# ── Reading helpers ────────────────────────────────────────────────────────


def _projects_in(session: Session, scope: Scope) -> dict[int, configuracoes.ProjectSummary]:
    """The projects of the scope by id: every project in the Portfólio, the chosen one otherwise."""
    return {
        project.id: project
        for project in configuracoes.list_projects(session)
        if scope.project_id is None or project.id == scope.project_id
    }


def _project(session: Session, project_id: int) -> configuracoes.ProjectSummary:
    for project in configuracoes.list_projects(session):
        if project.id == project_id:
            return project
    raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)


def _reports_in(session: Session, scope: Scope) -> list[Report]:
    statement = select(Report).options(selectinload(Report.activities), selectinload(Report.points))
    if scope.project_id is not None:
        statement = statement.where(Report.project_id == scope.project_id)
    return list(session.scalars(statement))


def _find(session: Session, scope: Scope, report_id: int) -> Report:
    """The report with the id inside the scope, or 422: an id of another project is not found."""
    report = session.get(Report, report_id)
    if report is None or (scope.project_id is not None and report.project_id != scope.project_id):
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return report


def _report_of(session: Session, *, project_id: int, kind: str, period: str) -> Report | None:
    statement = select(Report).where(
        Report.project_id == project_id, Report.kind == kind, Report.period == period
    )
    return session.scalars(statement).first()


def _views(session: Session, reports: Sequence[Report]) -> list[ReportView]:
    """The reports as the screens read them, with the project and the author named once."""
    if not reports:
        return []
    projects = {project.id: project for project in configuracoes.list_projects(session)}
    names = configuracoes.person_names(session, {report.updated_by_id for report in reports})
    return [_view(report, projects[report.project_id], names) for report in reports]


def _view(
    report: Report, project: configuracoes.ProjectSummary, names: dict[int, str]
) -> ReportView:
    points = tuple(
        PointInput(description=row.description, nature=row.nature, risk=row.risk)
        for row in report.points
    )
    threats, opportunities = calculations.nature_counts(point.nature for point in points)
    return ReportView(
        id=report.id,
        project_id=project.id,
        project_code=project.code,
        project_name=project.name,
        kind=report.kind,
        period=report.period,
        name=calculations.period_name(report.kind, report.period),
        short_name=calculations.short_period_name(report.kind, report.period),
        next_name=_next_name(report.kind, report.period),
        activities=_lines(report, GROUP_PERIOD),
        next_activities=_lines(report, GROUP_NEXT),
        points=points,
        threats=threats,
        opportunities=opportunities,
        version=report.version,
        updated_at=report.updated_at,
        updated_by=names.get(report.updated_by_id, ""),
    )


def _lines(report: Report, group: str) -> tuple[str, ...]:
    return tuple(row.text for row in report.activities if row.group == group)


def _next_name(kind: str, period: str) -> str:
    following = calculations.next_period(kind, period)
    return calculations.period_name(kind, following) if following is not None else ""


def _passes(view: ReportView, report_filter: ReportFilter) -> bool:
    """Whether the report stays in the list: the type, and the search in any of its texts."""
    if report_filter.kind and view.kind != report_filter.kind:
        return False
    needle = normalize_text(report_filter.search)
    if not needle:
        return True
    texts = [
        view.name,
        view.project_code,
        *view.activities,
        *view.next_activities,
        *(f"{point.description} {point.nature} {point.risk}" for point in view.points),
    ]
    return needle in normalize_text(" ".join(texts))


def _coverage(
    kind: str,
    projects: dict[int, configuracoes.ProjectSummary],
    views: Sequence[ReportView],
    reference_date: date,
) -> PeriodCoverage:
    """How many projects reported the last closed period of the type."""
    period = calculations.previous_period(kind, reference_date)
    reported = {view.project_id for view in views if view.kind == kind and view.period == period}
    return PeriodCoverage(
        period=period,
        name=calculations.period_name(kind, period),
        short_name=calculations.short_period_name(kind, period),
        registered=len(reported & projects.keys()),
        expected=len(projects),
    )


def _reference_points(weekly: Sequence[ReportView], last: ReportView | None) -> int | None:
    """The attention points of the weekly report before the last one, of the same project."""
    if last is None:
        return None
    of_project = {view.period: view for view in weekly if view.project_id == last.project_id}
    earlier = calculations.latest_period_before(of_project, last.period)
    return len(of_project[earlier].points) if earlier is not None else None


# First key of the advisory lock that serializes the code of a new activity of a project.
ACTIVITY_CODE_LOCK = 4501


ACTIVITY_NOT_FOUND_MESSAGE = "A atividade não existe mais. Recarregue a tela."


CONSTRAINT_NOT_FOUND_MESSAGE = "A restrição não existe mais. Recarregue a tela."


OTHER_PROJECT_MESSAGE = "O registro pertence a outro projeto: abra a tela no projeto dele."


ALREADY_REMOVED_MESSAGE = "A restrição já foi removida."


CHOOSE_ACTIVITY_MESSAGE = "Escolha a atividade da lista."


OPEN_CONSTRAINTS = "abertas"


ALL_CONSTRAINTS = "todas"


STATUS_OVERDUE = "Vencida"


STATUS_OPEN = "Aberta"


STATUS_REMOVED = "Removida"


@dataclass(frozen=True)
class LookaheadFilter:
    """What the person filtered: search text, discipline, only open restrictions and the list."""

    search: str = ""
    discipline: str = ""
    only_with_open_constraint: bool = False
    constraints: str = OPEN_CONSTRAINTS


@dataclass(frozen=True)
class ConstraintView:
    """A restriction as the screen and the exports read it."""

    id: int
    activity_id: int
    activity_code: str
    activity_name: str
    project_id: int
    project_label: str
    kind: str
    description: str
    owner_id: int | None
    owner_name: str
    due_date: date
    removal_date: date | None
    removal_comment: str | None
    is_open: bool
    is_overdue: bool
    version: int

    @property
    def status(self) -> str:
        """``Vencida``, ``Aberta`` or ``Removida``."""
        if self.is_overdue:
            return STATUS_OVERDUE
        return STATUS_OPEN if self.is_open else STATUS_REMOVED


@dataclass(frozen=True)
class ActivityView:
    """An activity of the horizon with its weeks, restrictions and counts."""

    id: int
    project_id: int
    project_label: str
    code: str
    name: str
    area: str
    discipline: str
    company_id: int | None
    company_name: str
    owner_id: int | None
    owner_name: str
    planned: tuple[bool, ...]
    constraints: tuple[ConstraintView, ...]
    version: int

    @property
    def open_constraints(self) -> int:
        """How many restrictions are still open."""
        return sum(1 for item in self.constraints if item.is_open)

    @property
    def overdue_constraints(self) -> int:
        """How many open restrictions are past the date they were needed."""
        return sum(1 for item in self.constraints if item.is_overdue)

    @property
    def is_ready(self) -> bool:
        """Free of open restrictions: it can go to the weekly schedule."""
        return calculations.activity_is_ready(self.open_constraints)

    @property
    def situation(self) -> str:
        """``vencida``, ``com_restricao`` or ``pronta``."""
        return calculations.activity_situation(self.open_constraints, self.overdue_constraints)

    @property
    def has_short_term_risk(self) -> bool:
        """Planned in the first two weeks with an open restriction: it must not be scheduled."""
        return calculations.has_open_constraint_in_short_term(self.planned, self.open_constraints)

    def week_at_risk(self, index: int) -> bool:
        """Whether the planned week ``index`` carries the orange mark."""
        return calculations.week_at_risk(index, self.planned, self.open_constraints)

    def counts(self) -> calculations.ActivityCounts:
        """What the indicators read of the activity."""
        return calculations.ActivityCounts(
            planned=self.planned,
            total_constraints=len(self.constraints),
            open_constraints=self.open_constraints,
            overdue_constraints=self.overdue_constraints,
        )


@dataclass(frozen=True)
class LookaheadBoard:
    """The 6WLA of a scope on a date: the weeks, the visible activities and the indicators.

    ``figures`` count every activity of the scope (the filters do not move the
    indicators, as in the prototype); ``activities`` and ``constraints`` are what
    the filters leave.
    """

    reference_date: date
    weeks: tuple[calculations.LookaheadWeekInfo, ...]
    activities: tuple[ActivityView, ...]
    constraints: tuple[ConstraintView, ...]
    figures: calculations.LookaheadFigures
    total_activities: int
    can_write: bool
    portfolio: bool


@dataclass(frozen=True)
class FormOptions:
    """What the forms offer: the register lists and the weeks of the horizon."""

    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]
    disciplines: tuple[str, ...]
    kinds: tuple[str, ...]
    weeks: tuple[calculations.LookaheadWeekInfo, ...]

    def company_choices(self) -> tuple[tuple[str, str], ...]:
        """The companies as ``(value, text)`` pairs for a selector."""
        return tuple((str(item.id), item.name) for item in self.companies)

    def person_choices(self) -> tuple[tuple[str, str], ...]:
        """The people as ``(value, text)`` pairs for a selector."""
        return tuple((str(item.id), item.name) for item in self.people)

    def discipline_choices(self) -> tuple[tuple[str, str], ...]:
        """The disciplines as ``(value, text)`` pairs for a selector."""
        return tuple((name, name) for name in self.disciplines)

    def kind_choices(self) -> tuple[tuple[str, str], ...]:
        """The restriction types as ``(value, text)`` pairs for a selector."""
        return tuple((name, name) for name in self.kinds)

    def choices(self) -> validation.RegisterChoices:
        """The same lists as the sets the validation checks the form against."""
        return validation.RegisterChoices(
            company_ids=frozenset(item.id for item in self.companies),
            person_ids=frozenset(item.id for item in self.people),
            disciplines=frozenset(self.disciplines),
        )


def can_write(user: User) -> bool:
    """Whether the profile may include and edit activities and restrictions."""
    return rbac.can(user, Permission.WRITE)


def form_options(session: Session, *, reference_date: date) -> FormOptions:
    """The register lists of the forms and the six weeks of the horizon of the date."""
    return FormOptions(
        companies=tuple(configuracoes.list_company_options(session)),
        people=tuple(configuracoes.list_person_options(session)),
        disciplines=tuple(configuracoes.list_discipline_names(session)),
        kinds=validation.CONSTRAINT_KINDS,
        weeks=calculations.lookahead_weeks(reference_date),
    )


def _register_choices(session: Session) -> validation.RegisterChoices:
    """The ids and names the register accepts in a form, for the validation."""
    return validation.RegisterChoices(
        company_ids=frozenset(item.id for item in configuracoes.list_company_options(session)),
        person_ids=frozenset(item.id for item in configuracoes.list_person_options(session)),
        disciplines=frozenset(configuracoes.list_discipline_names(session)),
    )


# ── Reading ──────────────────────────────────────────────────────────────


def lookahead_board(
    session: Session,
    *,
    user: User,
    scope: Scope,
    reference_date: date,
    filters: LookaheadFilter,
) -> LookaheadBoard:
    """The board of the scope: indicators over every activity, grid and list over the filtered."""
    activities = _activities_in_scope(session, scope=scope, reference_date=reference_date)
    visible = tuple(item for item in activities if _matches(item, filters))
    constraints = [constraint for item in visible for constraint in item.constraints]
    if filters.constraints == OPEN_CONSTRAINTS:
        constraints = [item for item in constraints if item.is_open]
    constraints.sort(key=lambda item: (item.due_date, item.id))
    return LookaheadBoard(
        reference_date=reference_date,
        weeks=calculations.lookahead_weeks(reference_date),
        activities=visible,
        constraints=tuple(constraints),
        figures=calculations.lookahead_figures([item.counts() for item in activities]),
        total_activities=len(activities),
        can_write=can_write(user),
        portfolio=scope.is_portfolio,
    )


def find_activity(
    session: Session, *, scope: Scope, activity_id: int, reference_date: date
) -> ActivityView:
    """One activity of the scope, with its restrictions."""
    record = _scoped_activity(session, scope, activity_id)
    return _activity_views(session, [record], reference_date=reference_date)[0]


def find_constraint(
    session: Session, *, scope: Scope, constraint_id: int, reference_date: date
) -> ConstraintView:
    """One restriction of the scope, with the activity it belongs to."""
    record = _scoped_constraint(session, scope, constraint_id)
    activity = find_activity(
        session, scope=scope, activity_id=record.lookahead_id, reference_date=reference_date
    )
    return next(item for item in activity.constraints if item.id == record.id)


def _matches(activity: ActivityView, filters: LookaheadFilter) -> bool:
    if filters.discipline and activity.discipline != filters.discipline:
        return False
    if filters.only_with_open_constraint and not activity.open_constraints:
        return False
    needle = normalize_text(filters.search)
    if not needle:
        return True
    haystack = normalize_text(
        " ".join(
            (
                activity.code,
                activity.name,
                activity.area,
                activity.discipline,
                activity.company_name,
                activity.project_label,
            )
        )
    )
    return needle in haystack


def _activities_in_scope(
    session: Session, *, scope: Scope, reference_date: date
) -> list[ActivityView]:
    statement = select(Lookahead).order_by(Lookahead.project_id, Lookahead.id)
    if not scope.is_portfolio:
        statement = statement.where(Lookahead.project_id == scope.project_id)
    return _activity_views(session, list(session.scalars(statement)), reference_date=reference_date)


def _activity_views(
    session: Session, records: Sequence[Lookahead], *, reference_date: date
) -> list[ActivityView]:
    """The views of the activities, with the weeks and the restrictions read in one query each."""
    if not records:
        return []
    ids = [record.id for record in records]
    weeks = _weeks_by_activity(session, ids)
    constraints = _constraints_by_activity(session, ids)
    names = _Names.read(session)
    views = []
    for record in records:
        activity_constraints = tuple(
            _constraint_view(item, record, names, reference_date=reference_date)
            for item in constraints.get(record.id, [])
        )
        views.append(
            ActivityView(
                id=record.id,
                project_id=record.project_id,
                project_label=names.project(record.project_id),
                code=record.code,
                name=record.activity,
                area=record.area,
                discipline=record.discipline,
                company_id=record.company_id,
                company_name=names.company(record.company_id),
                owner_id=record.owner_id,
                owner_name=names.person(record.owner_id),
                planned=weeks.get(record.id, (False,) * calculations.LOOKAHEAD_WEEKS),
                constraints=activity_constraints,
                version=record.version,
            )
        )
    return views


def _weeks_by_activity(session: Session, ids: Sequence[int]) -> dict[int, tuple[bool, ...]]:
    marks: dict[int, list[bool]] = {
        activity_id: [False] * calculations.LOOKAHEAD_WEEKS for activity_id in ids
    }
    statement = select(LookaheadWeek).where(LookaheadWeek.lookahead_id.in_(ids))
    for week in session.scalars(statement):
        marks[week.lookahead_id][week.index] = week.planned
    return {activity_id: tuple(values) for activity_id, values in marks.items()}


def _constraints_by_activity(
    session: Session, ids: Sequence[int]
) -> dict[int, list[LookaheadConstraint]]:
    statement = (
        select(LookaheadConstraint)
        .where(LookaheadConstraint.lookahead_id.in_(ids))
        .order_by(LookaheadConstraint.order, LookaheadConstraint.id)
    )
    grouped: dict[int, list[LookaheadConstraint]] = {}
    for item in session.scalars(statement):
        grouped.setdefault(item.lookahead_id, []).append(item)
    return grouped


@dataclass(frozen=True)
class _Names:
    """The names of the register entries a row mentions, read once per request."""

    projects: Mapping[int, str]
    companies: Mapping[int, str]
    people: Mapping[int, str]

    @classmethod
    def read(cls, session: Session) -> _Names:
        return cls(
            projects={
                project.id: f"{project.code} · {project.name}"
                for project in configuracoes.list_projects(session)
            },
            companies={item.id: item.name for item in configuracoes.list_company_options(session)},
            people={item.id: item.name for item in configuracoes.list_person_options(session)},
        )

    def project(self, project_id: int) -> str:
        return self.projects.get(project_id, "")

    def company(self, company_id: int | None) -> str:
        return self.companies.get(company_id, "") if company_id is not None else ""

    def person(self, person_id: int | None) -> str:
        return self.people.get(person_id, "") if person_id is not None else ""


def _constraint_view(
    item: LookaheadConstraint, activity: Lookahead, names: _Names, *, reference_date: date
) -> ConstraintView:
    return ConstraintView(
        id=item.id,
        activity_id=activity.id,
        activity_code=activity.code,
        activity_name=activity.activity,
        project_id=activity.project_id,
        project_label=names.project(activity.project_id),
        kind=item.kind,
        description=item.description,
        owner_id=item.owner_id,
        owner_name=names.person(item.owner_id),
        due_date=item.due_date,
        removal_date=item.removal_date,
        removal_comment=item.removal_comment,
        is_open=calculations.constraint_is_open(item.removal_date),
        is_overdue=calculations.constraint_is_overdue(
            item.due_date, item.removal_date, reference_date
        ),
        version=item.version,
    )


# ── Writing ──────────────────────────────────────────────────────────────


def create_activity(
    session: Session,
    *,
    user: User,
    scope: Scope,
    form: validation.ActivityForm,
) -> Lookahead:
    """Include an activity in the project of the scope, with the next code of the project."""
    rbac.require(user, Permission.WRITE)
    project_id = scope.require_project()
    data = validation.parse_activity(form, _register_choices(session))
    session.execute(
        select(func.pg_advisory_xact_lock(ACTIVITY_CODE_LOCK, cast(project_id, Integer)))
    )
    existing = list(
        session.scalars(
            select(Lookahead.code).where(Lookahead.project_id == project_id).order_by(Lookahead.id)
        )
    )
    record = recording.create(
        session,
        user_id=user.id,
        record=Lookahead(
            project_id=project_id,
            company_id=data.company_id,
            owner_id=data.owner_id,
            code=calculations.next_activity_code(existing),
            activity=data.activity,
            area=data.area,
            discipline=data.discipline,
        ),
    )
    for index, planned in enumerate(data.planned):
        week = LookaheadWeek(lookahead_id=record.id, index=index, planned=planned)
        session.add(week)
        session.flush()
        audit.created(session, user_id=user.id, entity=week.__tablename__, record=week)
    return record


def update_activity(
    session: Session,
    *,
    user: User,
    scope: Scope,
    activity_id: int,
    form: validation.ActivityForm,
) -> Lookahead:
    """Edit an activity; the version the screen opened (``versao``) must still be current."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_activity(session, scope, activity_id)
    data = validation.parse_activity(form, _register_choices(session))
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes={
            "company_id": data.company_id,
            "owner_id": data.owner_id,
            "activity": data.activity,
            "area": data.area,
            "discipline": data.discipline,
        },
        version=form.fields.get("versao"),
    )
    _replace_weeks(session, user=user, activity=record, planned=data.planned)
    return record


@dataclass(frozen=True)
class LoadedConstraint:
    """A restriction of the demonstration load: already typed, with the removal it carries."""

    kind: str
    owner_id: int | None
    description: str
    due_date: date
    removal_date: date | None


@dataclass(frozen=True)
class LoadedActivity:
    """An activity of the demonstration load: the register ids are the ones of this database."""

    project_id: int
    company_id: int | None
    owner_id: int | None
    code: str
    activity: str
    area: str
    discipline: str
    planned: tuple[bool, ...]
    constraints: tuple[LoadedConstraint, ...]


def load_activity(session: Session, *, author_id: int, data: LoadedActivity) -> Lookahead:
    """Write one activity of the demonstration load, with its weeks and restrictions, and the trail."""
    record = recording.create(
        session,
        user_id=author_id,
        record=Lookahead(
            project_id=data.project_id,
            company_id=data.company_id,
            owner_id=data.owner_id,
            code=data.code,
            activity=data.activity,
            area=data.area,
            discipline=data.discipline,
        ),
    )
    for index, planned in enumerate(data.planned):
        week = LookaheadWeek(lookahead_id=record.id, index=index, planned=planned)
        session.add(week)
        session.flush()
        audit.created(session, user_id=author_id, entity=week.__tablename__, record=week)
    for order, item in enumerate(data.constraints, start=1):
        recording.create(
            session,
            user_id=author_id,
            record=LookaheadConstraint(
                lookahead_id=record.id,
                owner_id=item.owner_id,
                order=order,
                kind=item.kind,
                description=item.description,
                due_date=item.due_date,
                removal_date=item.removal_date,
            ),
        )
    return record


def _replace_weeks(
    session: Session, *, user: User, activity: Lookahead, planned: tuple[bool, ...]
) -> None:
    """Move the six marks to the new values, leaving a trail line for each one that changed."""
    weeks = session.scalars(
        select(LookaheadWeek).where(LookaheadWeek.lookahead_id == activity.id)
    ).all()
    for week in weeks:
        if week.planned == planned[week.index]:
            continue
        before = audit.snapshot(week)
        week.planned = planned[week.index]
        session.flush()
        audit.changed(
            session, user_id=user.id, entity=week.__tablename__, record=week, before=before
        )


def create_constraint(
    session: Session,
    *,
    user: User,
    scope: Scope,
    raw: Mapping[str, str],
) -> LookaheadConstraint:
    """Register a restriction on the activity the form names (``atividade``); it starts open."""
    rbac.require(user, Permission.WRITE)
    activity = _scoped_activity(session, scope, _activity_id_of(raw), lock=True)
    data = validation.parse_constraint(raw, _register_choices(session))
    last_order = session.scalar(
        select(func.max(LookaheadConstraint.order)).where(
            LookaheadConstraint.lookahead_id == activity.id
        )
    )
    return recording.create(
        session,
        user_id=user.id,
        record=LookaheadConstraint(
            lookahead_id=activity.id,
            owner_id=data.owner_id,
            order=(last_order or 0) + 1,
            kind=data.kind,
            description=data.description,
            due_date=data.due_date,
        ),
    )


def _activity_id_of(raw: Mapping[str, str]) -> int:
    found = validation.parse_id(raw.get("atividade"))
    if found is None:
        raise InvalidDataError({"atividade": CHOOSE_ACTIVITY_MESSAGE})
    return found


def update_constraint(
    session: Session,
    *,
    user: User,
    scope: Scope,
    constraint_id: int,
    raw: Mapping[str, str],
) -> LookaheadConstraint:
    """Edit the type, owner, description and needed date of a restriction."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_constraint(session, scope, constraint_id)
    data = validation.parse_constraint(raw, _register_choices(session))
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes={
            "kind": data.kind,
            "owner_id": data.owner_id,
            "description": data.description,
            "due_date": data.due_date,
        },
        version=raw.get("versao"),
    )
    return record


def remove_constraint(
    session: Session,
    *,
    user: User,
    scope: Scope,
    constraint_id: int,
    raw: Mapping[str, str],
) -> LookaheadConstraint:
    """Register the removal of an open restriction: the date and, optionally, how it was removed."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_constraint(session, scope, constraint_id)
    data = validation.parse_removal(raw)
    if not calculations.constraint_is_open(record.removal_date):
        raise InvalidDataError(ALREADY_REMOVED_MESSAGE)
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes={"removal_date": data.removal_date, "removal_comment": data.comment},
        version=raw.get("versao"),
    )
    return record


# ── The records of the scope ─────────────────────────────────────────────


def _require_in_scope(scope: Scope, project_id: int) -> None:
    if not scope.is_portfolio and scope.project_id != project_id:
        raise InvalidDataError(OTHER_PROJECT_MESSAGE)


def _scoped_activity(
    session: Session, scope: Scope, activity_id: int, *, lock: bool = False
) -> Lookahead:
    statement = select(Lookahead).where(Lookahead.id == activity_id)
    if lock:
        statement = statement.with_for_update()
    record = session.scalars(statement).one_or_none()
    if record is None:
        raise InvalidDataError(ACTIVITY_NOT_FOUND_MESSAGE)
    _require_in_scope(scope, record.project_id)
    return record


def _scoped_constraint(session: Session, scope: Scope, constraint_id: int) -> LookaheadConstraint:
    record = session.get(LookaheadConstraint, constraint_id)
    if record is None:
        raise InvalidDataError(CONSTRAINT_NOT_FOUND_MESSAGE)
    _scoped_activity(session, scope, record.lookahead_id)
    return record


def activity_fields(activity: ActivityView) -> dict[str, Any]:
    """The values of the activity form for an edit: the same names the form sends."""
    return {
        "atividade": activity.name,
        "area": activity.area,
        "disciplina": activity.discipline,
        "empresa": str(activity.company_id or ""),
        "responsavel": str(activity.owner_id or ""),
        "versao": str(activity.version),
    }


def constraint_fields(constraint: ConstraintView) -> dict[str, Any]:
    """The values of the restriction form for an edit: the same names the form sends."""
    return {
        "tipo": constraint.kind,
        "responsavel": str(constraint.owner_id or ""),
        "descricao": constraint.description,
        "necessaria": constraint.due_date.isoformat(),
        "versao": str(constraint.version),
    }


# ── EAP: árvore, dicionário e carteira (ISSUE-036) ───────────────────────


EAP_GROUP = "eap"

LEVEL_ROOT = 0


LEVEL_AREA = 1


LEVEL_SUB_AREA = 2


LEVEL_PACKAGE = 3


ROOT_CODE = "0"


PORTFOLIO_LABEL = "Portfólio"


PORTFOLIO_DESCRIPTION = "Portfólio de projetos"


EAP_PROJECT_NOT_FOUND_MESSAGE = "O projeto da EAP não existe."


PACKAGE_NOT_FOUND_MESSAGE = "Pacote da EAP não encontrado."


ONLY_PACKAGES_MESSAGE = "Só os pacotes (nível 3) têm dicionário editável."


EAP_PORTFOLIO_READ_ONLY_MESSAGE = (
    "A EAP do Portfólio é somente leitura. Abra o projeto para editar o dicionário."
)


DEFAULT_DEVIATION_BANDS = (Decimal(2), Decimal(5))


DEFAULT_MAX_PACKAGE_WEIGHT = Decimal(10)


DEFAULT_MAX_ESTIMATED_WEIGHT = Decimal(5)


@dataclass(frozen=True)
class EapMeasurementView:
    """A medição do pacote como o dicionário a mostra: quando, de quanto para quanto, quem e a nota."""

    id: int
    measured_on: date
    from_pct: Decimal
    to_pct: Decimal
    author: str
    note: str

    @property
    def is_reversal(self) -> bool:
        """Whether the progress went back: the dictionary marks the measurement of the reversal."""
        return self.to_pct < self.from_pct


@dataclass(frozen=True)
class EapNode:
    """Um nó da árvore da EAP: a linha 0, a área, a subárea ou o pacote.

    Os nós de nível 1 e 2 não têm peso próprio: o peso é a soma dos filhos (regra dos 100%),
    calculada pelo servidor. Os campos descritivos do pacote (critério, modelo, etapas, unidade,
    quantidade, estado, entregável, aceitação, empresa, responsável, item da EAC e medições) só
    valem para o nível 3.
    """

    id: int | None
    code: str
    level: int
    description: str
    project_id: int | None
    project_code: str
    project_label: str
    weight: Decimal
    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    band: str | None
    start: date | None
    finish: date | None
    packages: int
    planning: int
    overdue: bool
    not_started: bool
    weight_in_parent: Decimal | None = None
    weight_in_project: Decimal | None = None
    kind: str | None = None
    criterion: str | None = None
    model: str = ""
    unit: str = ""
    quantity: Decimal | None = None
    executed: Decimal | None = None
    state: str | None = None
    estimated_pct: Decimal | None = None
    deliverable: str = ""
    acceptance: str = ""
    company_id: int | None = None
    company_name: str = ""
    owner_id: int | None = None
    owner_name: str = ""
    eac_item_id: int | None = None
    eac_code: str = ""
    steps: tuple[calculations.EapStep, ...] = ()
    measurements: tuple[EapMeasurementView, ...] = ()
    version: int = 0

    @property
    def is_work_package(self) -> bool:
        """Pacote de trabalho: nível 3 fora do tipo Planejamento; é ele que mede avanço."""
        return self.level == LEVEL_PACKAGE and self.kind != calculations.PLANNING_PACKAGE

    @property
    def is_planning_package(self) -> bool:
        """Pacote de planejamento: peso reservado, sem medição até ser desdobrado."""
        return self.level == LEVEL_PACKAGE and self.kind == calculations.PLANNING_PACKAGE


@dataclass(frozen=True)
class EapIndicators:
    """Os indicadores da tela: o avanço, os pacotes, as áreas e as marcas de atenção."""

    actual: Decimal
    predicted: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    work_packages: int
    planning_packages: int
    planning_weight: Decimal | None
    areas: int
    subareas: int
    overdue: int
    not_started: int
    late: int
    projects: int


@dataclass(frozen=True)
class EapRevisionView:
    """Uma revisão da EAP: a linha de base ou a que incorporou uma SM aprovada.

    ``package_count`` sai dos pesos congelados da revisão (D5b) e ``change_code`` é o link da SM.
    No Portfólio a linha traz o projeto e quantas revisões ele tem.
    """

    revision: int
    revision_date: date
    alteration: str
    justification: str
    approved_by: str
    package_count: int
    id: int | None = None
    change_id: int | None = None
    change_code: str = ""
    project_id: int | None = None
    project_label: str = ""
    revision_count: int = 0


@dataclass(frozen=True)
class EapBreakdownView:
    """Um desdobramento da revisão vigente: de qual pacote de planejamento para qual de trabalho.

    ``source_closed`` diz que a origem ficou encerrada: peso zerado pelo desdobramento (ou origem
    ausente), ela sai da árvore mas o desdobramento continua legível.
    """

    id: int
    revision: int
    applied_on: date
    weight: Decimal
    source_code: str
    source_description: str
    target_code: str
    target_description: str
    author: str
    justification: str
    source_closed: bool = False


@dataclass(frozen=True)
class EapPendingChange:
    """Uma SM aprovada com impacto em escopo que nenhuma revisão da EAP incorporou ainda."""

    id: int
    code: str
    title: str
    project_id: int
    project_label: str


@dataclass(frozen=True)
class EapOverview:
    """A EAP do escopo: a árvore, os indicadores, as revisões e os desdobramentos da vigente."""

    reference_date: date
    is_portfolio: bool
    can_edit: bool
    scope_label: str
    nodes: tuple[EapNode, ...]
    indicators: EapIndicators
    current_revision: EapRevisionView | None
    revisions: tuple[EapRevisionView, ...]
    breakdowns: tuple[EapBreakdownView, ...]
    pending_changes: tuple[EapPendingChange, ...]

    @property
    def root(self) -> EapNode:
        """A linha 0: o total do projeto ou do portfólio."""
        return self.nodes[0]

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no EAP: only the line 0 in the tree."""
        return len(self.nodes) <= 1


@dataclass(frozen=True)
class EapParameters:
    """Os parâmetros do grupo ``eap`` vigentes: as faixas, os limites e os modelos de etapas."""

    deviation_bands: tuple[Decimal, Decimal]
    max_package_weight: Decimal
    max_estimated_weight: Decimal
    stage_models: tuple[Mapping[str, Any], ...]

    def model_name(self, model: str | None) -> str:
        """O nome do modelo de etapas pelo id gravado no pacote; vazio sem modelo."""
        for candidate in self.stage_models:
            if str(candidate.get("id", "")) == (model or ""):
                return str(candidate.get("nome", ""))
        return ""


@dataclass(frozen=True)
class EapDictionaryOptions:
    """O que o formulário do dicionário oferece: as empresas, as pessoas e os itens da EAC."""

    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]
    eac_codes: tuple[str, ...]

    def company_choices(self) -> tuple[tuple[str, str], ...]:
        """As empresas como pares ``(valor, texto)`` para um seletor."""
        return tuple((str(item.id), item.name) for item in self.companies)

    def person_choices(self) -> tuple[tuple[str, str], ...]:
        """As pessoas como pares ``(valor, texto)`` para um seletor."""
        return tuple((str(item.id), item.name) for item in self.people)


@dataclass(frozen=True)
class _Lookups:
    """Os nomes que os nós mencionam, lidos uma vez por requisição."""

    companies: Mapping[int, str]
    people: Mapping[int, str]
    units: Mapping[int, str]
    eac_codes: Mapping[int, str]

    def company(self, company_id: int | None) -> str:
        return self.companies.get(company_id, "") if company_id is not None else ""

    def person(self, person_id: int | None) -> str:
        return self.people.get(person_id, "") if person_id is not None else ""

    def unit(self, unit_id: int | None) -> str:
        return self.units.get(unit_id, "") if unit_id is not None else ""

    def eac_code(self, item_id: int | None) -> str:
        return self.eac_codes.get(item_id, "") if item_id is not None else ""


@dataclass(frozen=True)
class _Reading:
    """O que toda leitura da EAP carrega: a sessão, os parâmetros vigentes, a data e os nomes."""

    session: Session
    parameters: EapParameters
    reference_date: date
    lookups: _Lookups


@dataclass(frozen=True)
class _TreeData:
    """Os itens do projeto já indexados: filhos, totais, etapas e medições."""

    by_parent: Mapping[int | None, tuple[EapItem, ...]]
    totals: Mapping[int, calculations.EapTotals]
    steps: Mapping[int, tuple[EapItemStep, ...]]
    measurements: Mapping[int, tuple[EapMeasurementView, ...]]


@dataclass(frozen=True)
class _ProjectSnapshot:
    """A EAP de um projeto lida uma vez: a árvore, os indicadores e as revisões."""

    nodes: tuple[EapNode, ...]
    indicators: EapIndicators
    revisions: tuple[EapRevisionView, ...]

    @property
    def root(self) -> EapNode:
        return self.nodes[0]

    @property
    def current_revision(self) -> EapRevisionView | None:
        current: EapRevisionView | None = None
        for view in self.revisions:
            if current is None or view.revision > current.revision:
                current = view
        return current


@dataclass(frozen=True)
class _PortfolioEntry:
    """Um projeto da carteira com EAP: a linha, o projeto, a EAP lida e o peso na carteira."""

    number: int
    project: configuracoes.ProjectSummary
    snapshot: _ProjectSnapshot
    weight: Decimal


# ── Leitura da árvore ─────────────────────────────────────────────────────


def eap_overview(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> EapOverview:
    """A EAP do escopo: a árvore do projeto (editável) ou a do Portfólio (somente leitura).

    The tree of the project carries the dictionary and the measurements of each package; the tree
    of the Portfólio has one line per project with EAP, with its weight in the portfolio, and one
    line per area, read-only, as the EAC does (D8). The real of each package comes from the
    current entries of its criterion and the nodes add up the children by weight (D5b). The
    reference date enters as an argument (D6).
    """
    rbac.require_module(user, MODULE)
    projects = _scope_projects(scope, configuracoes.list_projects(session))
    items_by_project = _items_by_project(session, [project.id for project in projects])
    reading = _Reading(
        session=session,
        parameters=_parameters(session, reference_date=reference_date),
        reference_date=reference_date,
        lookups=_lookups(
            session,
            items=[item for group in items_by_project.values() for item in group],
        ),
    )
    if scope.is_portfolio:
        return _portfolio_overview(
            reading, user=user, projects=projects, items_by_project=items_by_project
        )
    project = projects[0]
    return _project_overview(
        reading, user=user, project=project, items=items_by_project.get(project.id, ())
    )


def _project_overview(
    reading: _Reading,
    *,
    user: User,
    project: configuracoes.ProjectSummary,
    items: Sequence[EapItem],
) -> EapOverview:
    snapshot = _project_snapshot(reading, project, items)
    current = snapshot.current_revision
    breakdowns = _breakdowns(
        reading,
        project_id=project.id,
        revision=current.revision if current is not None else None,
        items=items,
    )
    pending = _pending_changes(
        reading.session,
        user=user,
        projects=(project,),
        used_by_project={project.id: _used_changes(snapshot.revisions)},
        reference_date=reading.reference_date,
    )
    return EapOverview(
        reference_date=reading.reference_date,
        is_portfolio=False,
        can_edit=rbac.can(user, Permission.WRITE),
        scope_label=_project_label(project),
        nodes=snapshot.nodes,
        indicators=snapshot.indicators,
        current_revision=current,
        revisions=snapshot.revisions,
        breakdowns=breakdowns,
        pending_changes=pending,
    )


def _portfolio_overview(
    reading: _Reading,
    *,
    user: User,
    projects: Sequence[configuracoes.ProjectSummary],
    items_by_project: Mapping[int, tuple[EapItem, ...]],
) -> EapOverview:
    entries = _portfolio_entries(reading, projects, items_by_project)
    nodes: list[EapNode] = [_portfolio_root(reading, entries)]
    for entry in entries:
        nodes.append(_portfolio_project_node(reading, entry))
        nodes.extend(_portfolio_area_node(entry, area) for area in _area_nodes(entry.snapshot))
    pending = _pending_changes(
        reading.session,
        user=user,
        projects=[entry.project for entry in entries],
        used_by_project={
            entry.project.id: _used_changes(entry.snapshot.revisions) for entry in entries
        },
        reference_date=reading.reference_date,
    )
    return EapOverview(
        reference_date=reading.reference_date,
        is_portfolio=True,
        can_edit=False,
        scope_label=PORTFOLIO_LABEL,
        nodes=tuple(nodes),
        indicators=_portfolio_indicators(nodes[0], entries),
        current_revision=None,
        revisions=_portfolio_revisions(entries),
        breakdowns=(),
        pending_changes=pending,
    )


def _portfolio_entries(
    reading: _Reading,
    projects: Sequence[configuracoes.ProjectSummary],
    items_by_project: Mapping[int, tuple[EapItem, ...]],
) -> tuple[_PortfolioEntry, ...]:
    """The projects with EAP, numbered in the order of the portfolio, with their weight in it."""
    from src.modulos.financeiro import service as financeiro

    weights = financeiro.portfolio_weights(reading.session, reference_date=reading.reference_date)
    entries: list[_PortfolioEntry] = []
    number = 0
    for project in projects:
        items = items_by_project.get(project.id, ())
        if not items:
            continue
        number += 1
        entries.append(
            _PortfolioEntry(
                number=number,
                project=project,
                snapshot=_project_snapshot(reading, project, items),
                weight=weights[project.id].weight if project.id in weights else Decimal(0),
            )
        )
    return tuple(entries)


def _portfolio_root(reading: _Reading, entries: Sequence[_PortfolioEntry]) -> EapNode:
    totals = calculations.eap_root_totals(
        [replace(_totals_of(entry.snapshot.root), weight=entry.weight) for entry in entries]
    )
    deviation = calculations.eap_deviation_pp(totals.actual, totals.predicted)
    return EapNode(
        id=None,
        code=ROOT_CODE,
        level=LEVEL_ROOT,
        description=PORTFOLIO_DESCRIPTION,
        project_id=None,
        project_code="",
        project_label=PORTFOLIO_LABEL,
        weight=totals.weight,
        predicted=totals.predicted,
        actual=totals.actual,
        deviation_pp=deviation,
        band=calculations.eap_deviation_band(deviation, reading.parameters.deviation_bands),
        start=totals.start,
        finish=totals.finish,
        packages=totals.packages,
        planning=totals.planning,
        overdue=totals.overdue,
        not_started=totals.not_started,
    )


def _portfolio_project_node(reading: _Reading, entry: _PortfolioEntry) -> EapNode:
    root = entry.snapshot.root
    return EapNode(
        id=None,
        code=str(entry.number),
        level=LEVEL_AREA,
        description=_project_label(entry.project),
        project_id=entry.project.id,
        project_code=entry.project.code,
        project_label=_project_label(entry.project),
        weight=entry.weight,
        predicted=root.predicted,
        actual=root.actual,
        deviation_pp=root.deviation_pp,
        band=root.band,
        start=root.start,
        finish=root.finish,
        packages=root.packages,
        planning=root.planning,
        overdue=root.overdue,
        not_started=root.not_started,
        weight_in_parent=entry.weight,
        owner_id=entry.project.manager_id,
        owner_name=reading.lookups.person(entry.project.manager_id),
    )


def _portfolio_area_node(entry: _PortfolioEntry, area: EapNode) -> EapNode:
    weight = (area.weight * entry.weight / calculations.PERCENT).quantize(
        calculations.TWO_PLACES, rounding=ROUND_HALF_UP
    )
    return replace(
        area,
        code=f"{entry.number}.{area.code}",
        level=LEVEL_SUB_AREA,
        project_id=entry.project.id,
        project_code=entry.project.code,
        project_label=_project_label(entry.project),
        weight=weight,
        weight_in_parent=area.weight,
        weight_in_project=area.weight,
    )


def _portfolio_indicators(root: EapNode, entries: Sequence[_PortfolioEntry]) -> EapIndicators:
    return EapIndicators(
        actual=root.actual,
        predicted=root.predicted,
        deviation_pp=root.deviation_pp,
        spi=_spi(root.actual, root.predicted),
        work_packages=sum(entry.snapshot.indicators.work_packages for entry in entries),
        planning_packages=sum(entry.snapshot.indicators.planning_packages for entry in entries),
        planning_weight=None,
        areas=sum(entry.snapshot.indicators.areas for entry in entries),
        subareas=sum(entry.snapshot.indicators.subareas for entry in entries),
        overdue=sum(entry.snapshot.indicators.overdue for entry in entries),
        not_started=sum(entry.snapshot.indicators.not_started for entry in entries),
        late=sum(entry.snapshot.indicators.late for entry in entries),
        projects=len(entries),
    )


def _portfolio_revisions(entries: Sequence[_PortfolioEntry]) -> tuple[EapRevisionView, ...]:
    views: list[EapRevisionView] = []
    for entry in entries:
        current = entry.snapshot.current_revision
        if current is None:
            continue
        views.append(
            replace(
                current,
                project_id=entry.project.id,
                project_label=_project_label(entry.project),
                revision_count=len(entry.snapshot.revisions),
            )
        )
    return tuple(views)


def _project_snapshot(
    reading: _Reading, project: configuracoes.ProjectSummary, items: Sequence[EapItem]
) -> _ProjectSnapshot:
    nodes = _tree(reading, project, items)
    return _ProjectSnapshot(
        nodes=nodes,
        indicators=_indicators(nodes, projects=1),
        revisions=_revisions(reading.session, project_id=project.id),
    )


def _tree(
    reading: _Reading, project: configuracoes.ProjectSummary, items: Sequence[EapItem]
) -> tuple[EapNode, ...]:
    """The line 0 and every node of the project, depth first, in the order of the codes."""
    data = _tree_data(reading, items)
    roots = data.by_parent.get(None, ())
    nodes: list[EapNode] = [
        _root_node(
            reading, project, calculations.eap_root_totals([data.totals[root.id] for root in roots])
        )
    ]

    def append(item: EapItem, parent_weight: Decimal | None) -> None:
        node = _node(reading, project=project, item=item, data=data, parent_weight=parent_weight)
        nodes.append(node)
        for child in data.by_parent.get(item.id, ()):
            append(child, node.weight)

    for root in roots:
        append(root, None)
    return tuple(nodes)


def _tree_data(reading: _Reading, items: Sequence[EapItem]) -> _TreeData:
    live = [item for item in items if not _is_closed_package(item)]
    by_parent = _children_by_parent(live)
    steps = _steps_by_item(reading.session, [item.id for item in live])
    measurements = _measurements_by_item(
        reading.session, [item.id for item in live], reading.lookups
    )
    totals = _totals_by_item(
        live, by_parent=by_parent, steps=steps, reference_date=reading.reference_date
    )
    return _TreeData(by_parent=by_parent, totals=totals, steps=steps, measurements=measurements)


def _is_closed_package(item: EapItem) -> bool:
    """O pacote encerrado pelo desdobramento: nível 3 com peso zerado, fora da árvore."""
    return item.level == LEVEL_PACKAGE and (item.weight or Decimal(0)) <= 0


def _root_node(
    reading: _Reading, project: configuracoes.ProjectSummary, totals: calculations.EapTotals
) -> EapNode:
    deviation = calculations.eap_deviation_pp(totals.actual, totals.predicted)
    return EapNode(
        id=None,
        code=ROOT_CODE,
        level=LEVEL_ROOT,
        description=project.name,
        project_id=project.id,
        project_code=project.code,
        project_label=_project_label(project),
        weight=totals.weight,
        predicted=totals.predicted,
        actual=totals.actual,
        deviation_pp=deviation,
        band=calculations.eap_deviation_band(deviation, reading.parameters.deviation_bands),
        start=totals.start,
        finish=totals.finish,
        packages=totals.packages,
        planning=totals.planning,
        overdue=totals.overdue,
        not_started=totals.not_started,
    )


def _node(
    reading: _Reading,
    *,
    project: configuracoes.ProjectSummary,
    item: EapItem,
    data: _TreeData,
    parent_weight: Decimal | None,
) -> EapNode:
    totals = data.totals[item.id]
    deviation = calculations.eap_deviation_pp(totals.actual, totals.predicted)
    return EapNode(
        id=item.id,
        code=item.code,
        level=item.level,
        description=item.description,
        project_id=project.id,
        project_code=project.code,
        project_label=_project_label(project),
        weight=totals.weight,
        predicted=totals.predicted,
        actual=totals.actual,
        deviation_pp=deviation,
        band=calculations.eap_deviation_band(deviation, reading.parameters.deviation_bands),
        start=totals.start,
        finish=totals.finish,
        packages=totals.packages,
        planning=totals.planning,
        overdue=totals.overdue,
        not_started=totals.not_started,
        weight_in_parent=_share_of(totals.weight, parent_weight),
        kind=item.kind,
        criterion=item.criterion,
        model=reading.parameters.model_name(item.model),
        unit=reading.lookups.unit(item.unit_id),
        quantity=item.quantity,
        executed=item.executed,
        state=item.state,
        estimated_pct=item.estimated_pct,
        deliverable=item.deliverable or "",
        acceptance=item.acceptance or "",
        company_id=item.company_id,
        company_name=reading.lookups.company(item.company_id),
        owner_id=item.owner_id,
        owner_name=reading.lookups.person(item.owner_id),
        eac_item_id=item.eac_item_id,
        eac_code=reading.lookups.eac_code(item.eac_item_id),
        steps=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct)
            for step in data.steps.get(item.id, ())
        ),
        measurements=data.measurements.get(item.id, ()),
        version=item.version,
    )


def _totals_by_item(
    items: Sequence[EapItem],
    *,
    by_parent: Mapping[int | None, tuple[EapItem, ...]],
    steps: Mapping[int, tuple[EapItemStep, ...]],
    reference_date: date,
) -> dict[int, calculations.EapTotals]:
    """The totals of every item: the real of the criterion for a package, the children for the rest."""
    totals: dict[int, calculations.EapTotals] = {}

    def compute(item: EapItem) -> calculations.EapTotals:
        if item.id in totals:
            return totals[item.id]
        if item.level == LEVEL_PACKAGE:
            found = calculations.eap_package_totals(
                _package(item, steps.get(item.id, ())), reference_date=reference_date
            )
        else:
            found = calculations.eap_node_totals(
                [compute(child) for child in by_parent.get(item.id, ())]
            )
        totals[item.id] = found
        return found

    for item in items:
        compute(item)
    return totals


def _package(item: EapItem, steps: Sequence[EapItemStep]) -> calculations.EapPackage:
    return calculations.EapPackage(
        kind=item.kind or "",
        weight=item.weight or Decimal(0),
        predicted=item.predicted or Decimal(0),
        start=item.start,
        finish=item.finish,
        criterion=item.criterion,
        etapas=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct) for step in steps
        ),
        quantity=item.quantity,
        executed=item.executed,
        state=item.state,
        estimated_pct=item.estimated_pct,
    )


def _indicators(nodes: Sequence[EapNode], *, projects: int) -> EapIndicators:
    root = nodes[0]
    work = [node for node in nodes if node.is_work_package]
    planning = [node for node in nodes if node.is_planning_package]
    return EapIndicators(
        actual=root.actual,
        predicted=root.predicted,
        deviation_pp=root.deviation_pp,
        spi=_spi(root.actual, root.predicted),
        work_packages=len(work),
        planning_packages=len(planning),
        planning_weight=_weight_of(planning),
        areas=sum(1 for node in nodes if node.level == LEVEL_AREA),
        subareas=sum(1 for node in nodes if node.level == LEVEL_SUB_AREA),
        overdue=sum(1 for node in work if node.overdue),
        not_started=sum(1 for node in work if node.not_started),
        late=sum(1 for node in work if node.band == calculations.DANGER_BAND),
        projects=projects,
    )


def _revisions(session: Session, *, project_id: int) -> tuple[EapRevisionView, ...]:
    """The revisions of the project, oldest first, with the frozen package count and the SM link."""
    from src.modulos.governanca import service as governanca

    records = list(
        session.scalars(
            select(EapRevision)
            .where(EapRevision.project_id == project_id)
            .order_by(EapRevision.revision, EapRevision.id)
        )
    )
    if not records:
        return ()
    counts = _revision_package_counts(session, [record.id for record in records])
    codes = governanca.change_codes(
        session,
        change_ids=[record.change_id for record in records if record.change_id is not None],
    )
    names = configuracoes.person_names(session, {record.approved_by_id for record in records})
    return tuple(
        EapRevisionView(
            id=record.id,
            revision=record.revision,
            revision_date=record.revision_date,
            alteration=record.alteration,
            justification=record.justification,
            approved_by=names.get(record.approved_by_id, ""),
            package_count=counts.get(record.id, 0),
            change_id=record.change_id,
            change_code=codes.get(record.change_id, "") if record.change_id is not None else "",
        )
        for record in records
    )


def _revision_package_counts(session: Session, revision_ids: Sequence[int]) -> dict[int, int]:
    """How many packages each revision froze: the level-3 items of ``eap_revisao_item``."""
    if not revision_ids:
        return {}
    statement = (
        select(EapRevisionItem.revision_id, func.count())
        .join(EapItem, EapItem.id == EapRevisionItem.item_id)
        .where(EapRevisionItem.revision_id.in_(revision_ids), EapItem.level == LEVEL_PACKAGE)
        .group_by(EapRevisionItem.revision_id)
    )
    counts: dict[int, int] = {}
    for row in session.execute(statement):
        counts[int(row[0])] = int(row[1])
    return counts


def _breakdowns(
    reading: _Reading,
    *,
    project_id: int,
    revision: int | None,
    items: Sequence[EapItem],
) -> tuple[EapBreakdownView, ...]:
    """The breakdowns of the current revision: from which planning package to which work package."""
    if revision is None:
        return ()
    records = list(
        reading.session.scalars(
            select(EapBreakdown)
            .where(EapBreakdown.project_id == project_id, EapBreakdown.revision == revision)
            .order_by(EapBreakdown.id)
        )
    )
    if not records:
        return ()
    by_id = {item.id: item for item in items}
    names = configuracoes.person_names(reading.session, {record.by_id for record in records})
    views: list[EapBreakdownView] = []
    for record in records:
        source = by_id.get(record.source_item_id)
        target = by_id.get(record.target_item_id)
        views.append(
            EapBreakdownView(
                id=record.id,
                revision=record.revision,
                applied_on=record.applied_on,
                weight=record.weight,
                source_code=source.code if source is not None else "",
                source_description=source.description if source is not None else "",
                target_code=target.code if target is not None else "",
                target_description=target.description if target is not None else "",
                author=names.get(record.by_id, ""),
                justification=record.justification,
                source_closed=source is None or _is_closed_package(source),
            )
        )
    return tuple(views)


def _pending_changes(
    session: Session,
    *,
    user: User,
    projects: Sequence[configuracoes.ProjectSummary],
    used_by_project: Mapping[int, frozenset[int]],
    reference_date: date,
) -> tuple[EapPendingChange, ...]:
    """As SMs aprovadas com impacto em escopo que nenhuma revisão da EAP incorporou ainda.

    The list comes from the Governança facade (the approved changes and their impact, through
    ``find_change_sheet``); the incorporation itself is the revision flow of ISSUE-038, so this is
    what the facades already give today. The scope-impact cut mirrors the prototype: an impact
    whose scope text is empty or says "sem impacto" does not count.
    """
    from src.modulos.governanca import service as governanca

    pending: list[EapPendingChange] = []
    for project in projects:
        used = used_by_project.get(project.id, frozenset())
        for change in governanca.approved_changes(session, project_id=project.id):
            if change.id in used:
                continue
            sheet = governanca.find_change_sheet(
                session, user=user, code=change.code, reference_date=reference_date
            )
            if sheet is None or not _has_scope_impact(sheet.impact):
                continue
            pending.append(
                EapPendingChange(
                    id=change.id,
                    code=change.code,
                    title=change.title,
                    project_id=project.id,
                    project_label=sheet.project_label,
                )
            )
    return tuple(pending)


def _has_scope_impact(impact: Any) -> bool:
    from src.modulos.governanca import calculations as governanca_calculations

    return governanca_calculations.has_scope_impact(impact.scope if impact is not None else "")


def _parameters(session: Session, *, reference_date: date) -> EapParameters:
    """The ``eap`` group in force on the date, with the initial values when there is no version."""
    values = (
        configuracoes.current_group(session, group=EAP_GROUP, reference_date=reference_date)
        or configuracoes.INITIAL_PARAMETERS[EAP_GROUP]
    )
    return EapParameters(
        deviation_bands=_deviation_bands(values),
        max_package_weight=_decimal_value(
            values.get("pesoMaximoPacotePct"), DEFAULT_MAX_PACKAGE_WEIGHT
        ),
        max_estimated_weight=_decimal_value(
            values.get("estimadoMaximoPct"), DEFAULT_MAX_ESTIMATED_WEIGHT
        ),
        stage_models=_stage_models(values),
    )


def _deviation_bands(values: Mapping[str, Any]) -> tuple[Decimal, Decimal]:
    raw = values.get("faixasDesvioPP")
    if not isinstance(raw, Sequence) or isinstance(raw, str) or len(raw) != 2:
        return DEFAULT_DEVIATION_BANDS
    return (
        _decimal_value(raw[0], DEFAULT_DEVIATION_BANDS[0]),
        _decimal_value(raw[1], DEFAULT_DEVIATION_BANDS[1]),
    )


def _decimal_value(value: Any, default: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return default


def _stage_models(values: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = values.get("modelosEtapas")
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return ()
    return tuple(item for item in raw if isinstance(item, Mapping))


# ── Escrita do dicionário ─────────────────────────────────────────────────


def update_dictionary(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    form: Mapping[str, str],
) -> EapItem:
    """Save the dictionary of a package: the descriptive fields, never the baseline.

    The description, the deliverable, the acceptance, the company, the owner and the EAC item are
    the dictionary (the prototype's ``eapEditarPacote``); the weight, the dates and the criterion
    belong to the baseline and only change through a revision (ISSUE-038). Writing asks for Membro
    and the Portfólio is refused: it is read-only (D8). A stale version is refused with 409.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    item = _editable_package(session, scope=scope, item_id=item_id)
    data = validation.parse_dictionary_form(
        form, _dictionary_choices(session, project_id=item.project_id)
    )
    recording.update(
        session,
        user_id=user.id,
        record=item,
        changes={
            "description": data.description,
            "deliverable": data.deliverable,
            "acceptance": data.acceptance,
            "company_id": data.company_id,
            "owner_id": data.owner_id,
            "eac_item_id": _eac_item_id(session, project_id=item.project_id, code=data.eac_code),
        },
        version=form.get("versao"),
    )
    return item


def _editable_package(session: Session, *, scope: Scope, item_id: int) -> EapItem:
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    item = session.get(EapItem, item_id)
    if item is None:
        raise InvalidDataError(PACKAGE_NOT_FOUND_MESSAGE)
    if item.project_id != scope.project_id:
        raise AccessDeniedError(OTHER_PROJECT_MESSAGE)
    if item.level != LEVEL_PACKAGE:
        raise InvalidDataError(ONLY_PACKAGES_MESSAGE)
    return item


def _dictionary_choices(session: Session, *, project_id: int) -> validation.DictionaryChoices:
    from src.modulos.financeiro import service as financeiro

    levels = financeiro.eac_item_levels(session, project_id=project_id)
    return validation.DictionaryChoices(
        company_ids=frozenset(item.id for item in configuracoes.list_company_options(session)),
        person_ids=frozenset(item.id for item in configuracoes.list_person_options(session)),
        eac_codes=frozenset(code for code, level in levels.items() if level >= LEVEL_PACKAGE),
    )


def _eac_item_id(session: Session, *, project_id: int, code: str | None) -> int | None:
    if not code:
        return None
    from src.modulos.financeiro import service as financeiro

    found = financeiro.eac_item_ids_by_code(session, project_id=project_id, codes=[code])
    return found.get(code)


def dictionary_node(
    session: Session, *, user: User, scope: Scope, item_id: int, reference_date: date
) -> EapNode:
    """O nó do pacote dentro do escopo, como a árvore o mostra; o Portfólio é recusado (D8).

    It is what the form of the dictionary opens on: the read-only Portfólio has no package to
    edit, an id that is not a package is refused and a project of the scope that does not exist
    comes back as the message of the tree.
    """
    rbac.require_module(user, MODULE)
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    overview = eap_overview(session, user=user, scope=scope, reference_date=reference_date)
    node = next((candidate for candidate in overview.nodes if candidate.id == item_id), None)
    if node is None:
        raise InvalidDataError(PACKAGE_NOT_FOUND_MESSAGE)
    if node.level != LEVEL_PACKAGE:
        raise InvalidDataError(ONLY_PACKAGES_MESSAGE)
    return node


def dictionary_options(session: Session, *, project_id: int) -> EapDictionaryOptions:
    """As listas do formulário do dicionário: empresas, pessoas e os itens de custo da EAC."""
    from src.modulos.financeiro import service as financeiro

    levels = financeiro.eac_item_levels(session, project_id=project_id)
    return EapDictionaryOptions(
        companies=tuple(configuracoes.list_company_options(session)),
        people=tuple(configuracoes.list_person_options(session)),
        eac_codes=tuple(sorted(code for code, level in levels.items() if level >= LEVEL_PACKAGE)),
    )


def dictionary_fields(node: EapNode) -> dict[str, str]:
    """Os valores do formulário do dicionário, com os mesmos nomes que o formulário envia."""
    return {
        "descricao": node.description,
        "entregavel": node.deliverable,
        "aceitacao": node.acceptance,
        "empresa": "" if node.company_id is None else str(node.company_id),
        "responsavel": "" if node.owner_id is None else str(node.owner_id),
        "eac": node.eac_code,
        "versao": str(node.version),
    }


# ── Medição do avanço (ISSUE-037) ─────────────────────────────────────────


PLANNING_PACKAGE_PROGRESS_MESSAGE = (
    "Pacote de planejamento não recebe medição: desdobre-o em pacotes de trabalho antes."
)


IMPORT_NOTE = "Importação do avanço"


@dataclass(frozen=True)
class ProgressView:
    """A medição registrada: o código do pacote, de quanto para quanto, o estorno e o item."""

    code: str
    from_pct: Decimal
    to_pct: Decimal
    is_reversal: bool
    item: EapItem


@dataclass(frozen=True)
class ProgressImport:
    """O resultado da importação: quantas linhas gravaram e o motivo de cada linha recusada."""

    applied: int
    errors: tuple[str, ...]


def register_progress(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    form: Mapping[str, str],
    reference_date: date,
) -> ProgressView:
    """Registra o avanço de um pacote de trabalho pelas entradas do seu critério.

    The entries of the criterion (the % of each step, the executed quantity, the milestone state
    or the estimated %) are written to the item and its steps, and the measurement is born as an
    immutable fact with the date, de/para, author and note. The accumulated progress does not go
    back: a reversal needs Gestor (403) and a justification of 10 characters or more (422), and
    the justification travels in the note. Writing asks for Membro, the date cannot pass the
    reference date and the Portfólio is read-only (D8). The version the screen opened protects
    the item (409).
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    item = _measurable_package(session, scope=scope, item_id=item_id)
    data = validation.parse_progress_form(
        form,
        _progress_package(
            item,
            _steps_of(session, item.id),
            unit=_unit_code(session, item.unit_id),
        ),
        reference_date=reference_date,
        is_manager=rbac.can(user, Permission.MANAGE),
        max_estimated_weight=_parameters(
            session, reference_date=reference_date
        ).max_estimated_weight,
    )
    _write_entries(
        session,
        user=user,
        item=item,
        entries=data.entries,
        version=form.get("versao"),
    )
    _record_measurement(
        session,
        user=user,
        item=item,
        measured_on=data.measured_on,
        from_pct=data.from_pct,
        to_pct=data.to_pct,
        note=data.note or None,
    )
    return ProgressView(
        code=item.code,
        from_pct=data.from_pct,
        to_pct=data.to_pct,
        is_reversal=calculations.eap_progress_regression(data.from_pct, data.to_pct),
        item=item,
    )


def progress_import_packages(
    session: Session, *, project_id: int
) -> dict[str, validation.ProgressPackage]:
    """Os pacotes de nível 3 do projeto como a importação do avanço os lê, sem gravar nada.

    É o que o importador de planilha usa para conferir cada linha: o real corrente do critério,
    a unidade e as etapas correntes, na transação da requisição.
    """
    return _progress_packages(
        session, tuple(_progress_items(session, project_id=project_id).values())
    )


def import_progress(
    session: Session,
    *,
    user: User,
    scope: Scope,
    rows: Sequence[validation.ImportRowInput],
    measurement_date: date,
    reference_date: date,
) -> ProgressImport:
    """Importa o avanço acumulado por pacote, linha a linha, sem estorno.

    Every line is checked on its own (``parse_import_rows``): a package that does not exist, a
    planning package, a milestone off its degrees, an executed quantity above the baseline and a
    line that regresses are refused with the motive; a line without change has nothing to write.
    An accepted line writes the entries and one measurement, dated with ``measurement_date`` and
    noted as an import. The import never reverses: a reversal only goes through the screen, with
    justification. Writing asks for Membro and the date cannot pass the reference date. Everything
    runs in the transaction the route opened.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    project_id = scope.require_project()
    if measurement_date > reference_date:
        raise InvalidDataError(
            {validation.FIELD_MEASURED_ON: validation.MEASUREMENT_DATE_FUTURE_MESSAGE}
        )
    items = _progress_items(session, project_id=project_id)
    packages = _progress_packages(session, tuple(items.values()))
    applied, errors = 0, []
    for row in rows:
        result = validation.parse_import_rows((row,), packages)[0]
        if result.error:
            errors.append(result.error)
            continue
        if result.entries is None or result.from_pct is None or result.to_pct is None:
            continue
        item = items[result.code]
        _write_entries(
            session,
            user=user,
            item=item,
            entries=result.entries,
            version=str(item.version),
        )
        _record_measurement(
            session,
            user=user,
            item=item,
            measured_on=measurement_date,
            from_pct=result.from_pct,
            to_pct=result.to_pct,
            note=IMPORT_NOTE,
        )
        packages[result.code] = replace(packages[result.code], current=result.to_pct)
        applied += 1
    return ProgressImport(applied=applied, errors=tuple(errors))


def _measurable_package(session: Session, *, scope: Scope, item_id: int) -> EapItem:
    """O pacote de trabalho do escopo que pode receber medição."""
    item = _editable_package(session, scope=scope, item_id=item_id)
    if item.kind == calculations.PLANNING_PACKAGE:
        raise InvalidDataError(PLANNING_PACKAGE_PROGRESS_MESSAGE)
    return item


def _write_entries(
    session: Session,
    *,
    user: User,
    item: EapItem,
    entries: validation.ProgressEntries,
    version: int | str | None,
) -> None:
    """Grava as entradas do critério no item e nas etapas, com a trilha de cada mudança."""
    recording.update(
        session,
        user_id=user.id,
        record=item,
        changes=_entry_changes(entries),
        version=version,
    )
    _save_steps(session, user=user, item=item, steps=entries.steps)


def _entry_changes(entries: validation.ProgressEntries) -> dict[str, Any]:
    """Os campos do item que o critério atualiza; as etapas mudam nas linhas filhas."""
    values = {
        "executed": entries.executed,
        "state": entries.state,
        "estimated_pct": entries.estimated_pct,
    }
    return {field: value for field, value in values.items() if value is not None}


def _save_steps(
    session: Session, *, user: User, item: EapItem, steps: Sequence[calculations.EapStep]
) -> None:
    """Grava o % concluído das etapas que mudaram, com a trilha de cada uma."""
    if not steps:
        return
    records = session.scalars(
        select(EapItemStep)
        .where(EapItemStep.item_id == item.id)
        .order_by(EapItemStep.order, EapItemStep.id)
    ).all()
    for record, step in zip(records, steps, strict=False):
        if step.pct is None or record.pct == step.pct:
            continue
        before = audit.snapshot(record)
        record.pct = step.pct
        session.flush()
        audit.changed(
            session, user_id=user.id, entity=record.__tablename__, record=record, before=before
        )


def _record_measurement(
    session: Session,
    *,
    user: User,
    item: EapItem,
    measured_on: date,
    from_pct: Decimal,
    to_pct: Decimal,
    note: str | None,
) -> EapMeasurement:
    """Grava a medição como fato imutável, com o autor sendo a pessoa do usuário."""
    return recording.create(
        session,
        user_id=user.id,
        record=EapMeasurement(
            item_id=item.id,
            author_id=user.person_id,
            measured_on=measured_on,
            from_pct=from_pct,
            to_pct=to_pct,
            note=note,
        ),
    )


def _progress_items(session: Session, *, project_id: int) -> dict[str, EapItem]:
    """Os pacotes (nível 3) do projeto pelo código, inclusive os de planejamento."""
    statement = (
        select(EapItem)
        .where(EapItem.project_id == project_id, EapItem.level == LEVEL_PACKAGE)
        .order_by(EapItem.id)
    )
    return {item.code: item for item in session.scalars(statement)}


def _progress_packages(
    session: Session, items: Sequence[EapItem]
) -> dict[str, validation.ProgressPackage]:
    """Os pacotes como a validação da importação os lê, com a unidade e as etapas correntes."""
    steps = _steps_by_item(session, [item.id for item in items])
    units = {unit.id: unit.code for unit in configuracoes.list_measure_units(session)}
    return {
        item.code: _progress_package(
            item, steps.get(item.id, ()), unit=units.get(item.unit_id or 0, "")
        )
        for item in items
    }


def _progress_package(
    item: EapItem, steps: Sequence[EapItemStep], *, unit: str
) -> validation.ProgressPackage:
    """O pacote de nível 3 com o real corrente e as entradas correntes do seu critério."""
    return validation.ProgressPackage(
        kind=item.kind or "",
        criterion=item.criterion,
        weight=item.weight or Decimal(0),
        current=_item_progress(item, steps),
        quantity=item.quantity,
        unit=unit,
        steps=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct) for step in steps
        ),
    )


def _item_progress(item: EapItem, steps: Sequence[EapItemStep]) -> Decimal:
    """O real corrente do pacote, calculado das entradas do critério (D5b)."""
    return calculations.eap_package_progress(
        item.criterion,
        etapas=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct) for step in steps
        ),
        quantity=item.quantity,
        executed=item.executed,
        state=item.state,
        estimated_pct=item.estimated_pct,
    )


def _steps_of(session: Session, item_id: int) -> tuple[EapItemStep, ...]:
    """As etapas correntes de um pacote, na ordem."""
    return _steps_by_item(session, [item_id]).get(item_id, ())


def _unit_code(session: Session, unit_id: int | None) -> str:
    """O código da unidade de medida do pacote; vazio sem unidade."""
    if unit_id is None:
        return ""
    return next(
        (unit.code for unit in configuracoes.list_measure_units(session) if unit.id == unit_id),
        "",
    )


# ── Revisões da EAP e desdobramento (ISSUE-038) ───────────────────────────


REVISION_MANAGER_MESSAGE = "Nova revisão da EAP exige papel Gestor."


REVISION_EMPTY_MESSAGE = "A revisão precisa alterar ao menos um pacote."


@dataclass(frozen=True)
class RevisionRequest:
    """O que a tela da EAP pede na revisão: a SM, a justificativa, os ajustes e os pacotes novos."""

    change_code: str
    justification: str
    adjustments: tuple[validation.RevisionAdjustment, ...] = ()
    new_packages: tuple[validation.NewPackageData, ...] = ()


@dataclass(frozen=True)
class RevisionResult:
    """O que a revisão fez: a revisão gravada, a SM e os códigos incluídos e ajustados."""

    revision: int
    revision_date: date
    change_code: str
    new_codes: tuple[str, ...]
    adjusted_codes: tuple[str, ...]
    alteration: str


def create_revision(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: RevisionRequest,
    reference_date: date,
) -> RevisionResult:
    """Cria a revisão da EAP a partir da SM aprovada com impacto em escopo (papel Gestor).

    A SM vem da Governança já aprovada, com impacto em escopo e ainda não incorporada; a revisão
    ajusta peso, quantidade e término dos pacotes afetados, inclui os pacotes novos e reescala os
    pesos livres para a soma fechar 100 exatos, congelando o peso de todos os pacotes de nível 3.
    A revisão e a marca da SM na Governança entram na mesma transação.
    """
    rbac.require_module(user, MODULE)
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(REVISION_MANAGER_MESSAGE)
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    project_id = scope.require_project()
    if not request.adjustments and not request.new_packages:
        raise InvalidDataError(REVISION_EMPTY_MESSAGE)
    source = _revision_source(session, change_code=request.change_code, project_id=project_id)
    justification = request.justification.strip()
    if len(justification) < validation.JUSTIFICATION_MIN_CHARACTERS:
        raise InvalidDataError(
            {validation.FIELD_JUSTIFICATION: validation.REVISION_JUSTIFICATION_MESSAGE}
        )
    parameters = _parameters(session, reference_date=reference_date)
    items = tuple(_items_by_project(session, [project_id]).get(project_id, ()))
    packages = {item.code: item for item in items if item.level == LEVEL_PACKAGE}
    fixed = _adjustment_weights(
        packages=packages, adjustments=request.adjustments, parameters=parameters
    )
    _require_new_packages(request.new_packages, items=items, parameters=parameters)
    fixed_total = sum(fixed.values(), Decimal(0)) + sum(
        (data.weight for data in request.new_packages), Decimal(0)
    )
    problem = validation.revision_fixed_weight_error(fixed_total)
    if problem:
        raise InvalidDataError({validation.FIELD_WEIGHT: problem})
    _apply_adjustments(session, user=user, packages=packages, adjustments=request.adjustments)
    created = _create_revision_packages(
        session,
        user=user,
        project_id=project_id,
        items=items,
        known=tuple(packages.values()),
        new_packages=request.new_packages,
        reference_date=reference_date,
    )
    fixed.update({item.code: item.weight or Decimal(0) for item in created})
    _rescale_free_weights(session, user=user, packages=packages, fixed=fixed)
    frozen = _packages_by_code(session, project_id)
    total_problem = validation.hundred_rule_error(
        [item.weight or Decimal(0) for item in frozen.values()]
    )
    if total_problem:
        raise InvalidDataError({validation.FIELD_WEIGHT: total_problem})
    adjusted_codes = tuple(adjustment.code for adjustment in request.adjustments)
    new_codes = tuple(item.code for item in created)
    alteration = _alteration(new_codes, adjusted_codes)
    revision = _next_revision(session, project_id=project_id)
    record = recording.create(
        session,
        user_id=user.id,
        record=EapRevision(
            project_id=project_id,
            change_id=source.change_id,
            approved_by_id=user.person_id,
            revision=revision,
            revision_date=reference_date,
            alteration=alteration,
            justification=justification,
        ),
    )
    _freeze_revision(session, revision_id=record.id, packages=tuple(frozen.values()))
    from src.modulos.governanca import service as governanca

    governanca.incorporate_eap_revision(
        session, user=user, change_id=source.change_id, revision=revision
    )
    return RevisionResult(
        revision=revision,
        revision_date=reference_date,
        change_code=source.code,
        new_codes=new_codes,
        adjusted_codes=adjusted_codes,
        alteration=alteration,
    )


@dataclass(frozen=True)
class BreakdownRequest:
    """O desdobramento pedido pela tela: o pacote novo (recurso desdobramento) já validado."""

    package: validation.NewPackageData


@dataclass(frozen=True)
class BreakdownResult:
    """O que o desdobramento fez: o pacote criado, a origem e se ela ficou encerrada."""

    code: str
    source_code: str
    source_closed: bool


def breakdown_package(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: BreakdownRequest,
    reference_date: date,
) -> BreakdownResult:
    """Desdobra um pacote de planejamento em um de trabalho, sem mudar o total do projeto.

    O peso sai da origem para o pacote novo, o previsto é o da origem e, com peso zero, a origem
    fica encerrada: sai da árvore, mas o desdobramento continua legível. Não cria revisão; a
    escrita pede Membro, como o dicionário (o protótipo não pede papel Gestor).
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    project_id = scope.require_project()
    data = request.package
    if data.resource != validation.BREAKDOWN:
        raise InvalidDataError({validation.FIELD_RESOURCE: validation.RESOURCE_MESSAGE})
    items = tuple(_items_by_project(session, [project_id]).get(project_id, ()))
    packages = {item.code: item for item in items if item.level == LEVEL_PACKAGE}
    origin = packages.get(data.source_code or "")
    if origin is None or origin.kind != calculations.PLANNING_PACKAGE:
        raise InvalidDataError({validation.FIELD_ORIGIN: validation.ORIGIN_MESSAGE})
    if data.weight > (origin.weight or Decimal(0)):
        raise InvalidDataError(
            {
                validation.FIELD_WEIGHT: validation.BREAKDOWN_WEIGHT_MESSAGE.format(
                    code=origin.code, weight=_plain_weight(origin.weight)
                )
            }
        )
    parent = next((item for item in items if item.code == data.parent_code), None)
    if parent is None or parent.level != LEVEL_SUB_AREA:
        raise InvalidDataError({validation.FIELD_PARENT: validation.PARENT_MESSAGE})
    code = _next_package_code(tuple(packages.values()), parent)
    created = _create_eap_package(
        session,
        user=user,
        project_id=project_id,
        data=data,
        code=code,
        parent=parent,
        kind=calculations.WORK_PACKAGE,
        predicted=origin.predicted or Decimal(0),
    )
    remaining = (origin.weight or Decimal(0)) - data.weight
    recording.update(
        session,
        user_id=user.id,
        record=origin,
        changes={"weight": remaining},
        version=origin.version,
    )
    revision = _current_revision(session, project_id=project_id)
    recording.create(
        session,
        user_id=user.id,
        record=EapBreakdown(
            project_id=project_id,
            source_item_id=origin.id,
            target_item_id=created.id,
            by_id=user.person_id,
            revision=revision,
            applied_on=reference_date,
            weight=data.weight,
            justification=data.justification.strip(),
        ),
    )
    return BreakdownResult(code=code, source_code=origin.code, source_closed=remaining <= 0)


@dataclass(frozen=True)
class EapChoice:
    """Uma opção dos formulários da EAP: o valor que o formulário envia e o texto que a pessoa lê."""

    value: str
    text: str


@dataclass(frozen=True)
class EapFormOptions:
    """O que os formulários da revisão, do pacote novo e da importação oferecem e conferem.

    As listas saem do projeto do escopo e dos cadastros; ``states`` e ``limits`` são o que as
    regras da validação leem, na mesma forma em que a fachada da revisão as lê.
    """

    subareas: tuple[EapChoice, ...]
    planning_packages: tuple[EapChoice, ...]
    work_packages: tuple[EapChoice, ...]
    changes: tuple[EapChoice, ...]
    stage_models: tuple[Mapping[str, Any], ...]
    units: tuple[configuracoes.MeasureUnitSummary, ...]
    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]
    eac_codes: tuple[str, ...]
    states: Mapping[str, validation.PackageState]
    limits: validation.RevisionLimits
    next_revision: int

    def unit_choices(self) -> tuple[tuple[str, str], ...]:
        """As unidades como pares ``(valor, texto)`` para um seletor."""
        return tuple((unit.code, unit.code) for unit in self.units)

    def company_choices(self) -> tuple[tuple[str, str], ...]:
        """As empresas como pares ``(valor, texto)`` para um seletor."""
        return tuple((str(item.id), item.name) for item in self.companies)

    def person_choices(self) -> tuple[tuple[str, str], ...]:
        """As pessoas como pares ``(valor, texto)`` para um seletor."""
        return tuple((str(item.id), item.name) for item in self.people)


def revision_form_options(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> EapFormOptions:
    """As listas e os limites dos formulários da revisão, do pacote novo e da importação.

    Lê o projeto do escopo numa passada: as subáreas, os pacotes de planejamento com peso a
    desdobrar, as SMs aprovadas com impacto em escopo pendentes de incorporação, os modelos de
    etapas e os tetos de peso dos parâmetros vigentes, mais os cadastros (unidades, empresas,
    pessoas e itens da EAC) que os formulários mostram e a importação confere. O Portfólio é
    recusado, como nas demais escritas da EAP.
    """
    rbac.require_module(user, MODULE)
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    from src.modulos.financeiro import service as financeiro
    from src.modulos.governanca import service as governanca

    project_id = scope.require_project()
    items = tuple(_items_by_project(session, [project_id]).get(project_id, ()))
    parameters = _parameters(session, reference_date=reference_date)
    levels = financeiro.eac_item_levels(session, project_id=project_id)
    titles = {
        change.code: change.title
        for change in governanca.approved_changes(session, project_id=project_id)
    }
    return EapFormOptions(
        subareas=tuple(
            EapChoice(value=item.code, text=f"{item.code} · {item.description}")
            for item in items
            if item.level == LEVEL_SUB_AREA
        ),
        planning_packages=tuple(
            EapChoice(
                value=item.code,
                text=(
                    f"{item.code} · {item.description} · {_plain_weight(item.weight)}% a desdobrar"
                ),
            )
            for item in items
            if item.level == LEVEL_PACKAGE
            and item.kind == calculations.PLANNING_PACKAGE
            and (item.weight or Decimal(0)) > 0
        ),
        work_packages=tuple(
            EapChoice(
                value=item.code,
                text=f"{item.code} · {item.description} · {_plain_weight(item.weight)}%",
            )
            for item in items
            if item.level == LEVEL_PACKAGE
        ),
        changes=tuple(
            EapChoice(
                value=source.code,
                text=_change_label(source.code, titles.get(source.code, "")),
            )
            for source in governanca.eap_revision_sources(session, project_id=project_id)
        ),
        stage_models=parameters.stage_models,
        units=tuple(configuracoes.list_measure_units(session)),
        companies=tuple(configuracoes.list_company_options(session)),
        people=tuple(configuracoes.list_person_options(session)),
        eac_codes=tuple(sorted(code for code, level in levels.items() if level >= LEVEL_PACKAGE)),
        states=_package_states(items),
        limits=validation.RevisionLimits(
            max_package_weight=parameters.max_package_weight,
            max_estimated_weight=parameters.max_estimated_weight,
        ),
        next_revision=_next_revision(session, project_id=project_id),
    )


def _package_states(items: Sequence[EapItem]) -> dict[str, validation.PackageState]:
    """O estado de cada item do projeto como as regras da revisão e da importação o leem."""
    return {
        item.code: validation.PackageState(
            code=item.code,
            level=item.level,
            kind=item.kind or "",
            criterion=item.criterion,
            weight=item.weight or Decimal(0),
            quantity=item.quantity,
            executed=item.executed,
            start=item.start,
            finish=item.finish,
        )
        for item in items
    }


def _change_label(code: str, title: str) -> str:
    """A SM como um select a mostra: ``SM-... · Título``."""
    return f"{code} · {title}" if title else code


def _revision_source(session: Session, *, change_code: str, project_id: int) -> ChangeEapSource:
    """A SM aprovada com impacto em escopo pendente do projeto, ou a recusa do protótipo."""
    from src.modulos.governanca import service as governanca

    wanted = (change_code or "").strip()
    ids = governanca.change_ids_by_code(session, codes=[wanted])
    source = governanca.change_eap_source(session, change_id=ids[wanted]) if wanted in ids else None
    if (
        source is None
        or source.project_id != project_id
        or not source.approved
        or not source.scope_impact
        or source.incorporated_revision is not None
    ):
        raise InvalidDataError(validation.CHANGE_MESSAGE)
    return source


def _adjustment_weights(
    *,
    packages: Mapping[str, EapItem],
    adjustments: Sequence[validation.RevisionAdjustment],
    parameters: EapParameters,
) -> dict[str, Decimal]:
    """O peso fixo de cada ajuste, depois de conferir o pacote e os limites do parâmetro."""
    fixed: dict[str, Decimal] = {}
    for adjustment in adjustments:
        if adjustment.code not in packages:
            raise InvalidDataError(
                validation.REVISION_PACKAGE_NOT_FOUND_MESSAGE.format(code=adjustment.code)
            )
        _require_revision_weight(adjustment.weight, parameters=parameters)
        fixed[adjustment.code] = adjustment.weight
    return fixed


def _require_new_packages(
    new_packages: Sequence[validation.NewPackageData],
    *,
    items: Sequence[EapItem],
    parameters: EapParameters,
) -> None:
    """Confere cada pacote novo antes de qualquer escrita: recurso, subárea, peso e código."""
    subareas = {item.code for item in items if item.level == LEVEL_SUB_AREA}
    levels = {item.code: item.level for item in items}
    for data in new_packages:
        if data.resource != validation.REVISION:
            raise InvalidDataError({validation.FIELD_RESOURCE: validation.RESOURCE_MESSAGE})
        if data.parent_code not in subareas:
            raise InvalidDataError({validation.FIELD_PARENT: validation.PARENT_MESSAGE})
        _require_revision_weight(data.weight, parameters=parameters)
        if data.code is not None:
            problem = validation.package_code_error(data.code, levels=levels)
            if problem:
                raise InvalidDataError({validation.FIELD_CODE: problem})
            levels[data.code] = LEVEL_PACKAGE


def _require_revision_weight(weight: Decimal, *, parameters: EapParameters) -> None:
    """O peso de um pacote da revisão: maior que zero e até o máximo do parâmetro."""
    if weight <= 0:
        raise InvalidDataError({validation.FIELD_WEIGHT: validation.PACKAGE_WEIGHT_ZERO_MESSAGE})
    if weight > parameters.max_package_weight:
        raise InvalidDataError(
            {
                validation.FIELD_WEIGHT: validation.REVISION_WEIGHT_MAX_MESSAGE.format(
                    maximum=parameters.max_package_weight
                )
            }
        )


def _apply_adjustments(
    session: Session,
    *,
    user: User,
    packages: Mapping[str, EapItem],
    adjustments: Sequence[validation.RevisionAdjustment],
) -> None:
    """Ajusta o peso, a quantidade (em Unidades) e o término dos pacotes afetados."""
    for adjustment in adjustments:
        package = packages[adjustment.code]
        changes: dict[str, Any] = {"weight": adjustment.weight}
        if adjustment.quantity is not None and package.criterion == calculations.CRITERION_UNITS:
            changes["quantity"] = adjustment.quantity
        if adjustment.finish is not None:
            changes["finish"] = adjustment.finish
        recording.update(
            session,
            user_id=user.id,
            record=package,
            changes=changes,
            version=package.version,
        )


def _create_revision_packages(
    session: Session,
    *,
    user: User,
    project_id: int,
    items: Sequence[EapItem],
    known: Sequence[EapItem],
    new_packages: Sequence[validation.NewPackageData],
    reference_date: date,
) -> tuple[EapItem, ...]:
    """Cria os pacotes novos da revisão, com o código informado ou o seguinte da sua subárea."""
    subareas = {item.code: item for item in items if item.level == LEVEL_SUB_AREA}
    live = list(known)
    created: list[EapItem] = []
    for data in new_packages:
        parent = subareas.get(data.parent_code)
        if parent is None:
            raise InvalidDataError({validation.FIELD_PARENT: validation.PARENT_MESSAGE})
        code = data.code if data.code is not None else _next_package_code(live, parent)
        item = _create_eap_package(
            session,
            user=user,
            project_id=project_id,
            data=data,
            code=code,
            parent=parent,
            kind=data.kind,
            predicted=calculations.eap_linear_predicted(data.start, data.finish, reference_date),
        )
        live.append(item)
        created.append(item)
    return tuple(created)


def _create_eap_package(
    session: Session,
    *,
    user: User,
    project_id: int,
    data: validation.NewPackageData,
    code: str,
    parent: EapItem,
    kind: str,
    predicted: Decimal,
) -> EapItem:
    """O pacote novo da EAP, com as entradas iniciais do critério e as etapas do modelo a zero."""
    item = recording.create(
        session,
        user_id=user.id,
        record=EapItem(
            project_id=project_id,
            parent_id=parent.id,
            eac_item_id=_eac_item_id(session, project_id=project_id, code=data.eac_code),
            unit_id=_unit_id(session, data.unit),
            company_id=data.company_id,
            owner_id=data.owner_id,
            code=code,
            description=data.description,
            level=LEVEL_PACKAGE,
            kind=kind,
            criterion=data.criterion,
            model=data.model,
            quantity=data.quantity,
            executed=_initial_executed(data.criterion),
            state=_initial_state(data.criterion),
            estimated_pct=_initial_estimated(data.criterion),
            weight=data.weight,
            predicted=predicted,
            start=data.start,
            finish=data.finish,
            deliverable=data.deliverable,
            acceptance=data.acceptance,
        ),
    )
    for order, step in enumerate(data.steps, start=1):
        recording.create(
            session,
            user_id=user.id,
            record=EapItemStep(
                item_id=item.id,
                order=order,
                name=step.name,
                weight=step.weight,
                pct=Decimal(0),
            ),
        )
    return item


def _initial_executed(criterion: str | None) -> Decimal | None:
    return Decimal(0) if criterion == calculations.CRITERION_UNITS else None


def _initial_state(criterion: str | None) -> str | None:
    if criterion in (
        calculations.CRITERION_MILESTONE_0_100,
        calculations.CRITERION_MILESTONE_50_50,
    ):
        return calculations.MILESTONE_NOT_STARTED
    return None


def _initial_estimated(criterion: str | None) -> Decimal | None:
    return Decimal(0) if criterion == calculations.CRITERION_ESTIMATED else None


def _unit_id(session: Session, code: str) -> int | None:
    """O id da unidade de medida pelo código; recusa a unidade que não existe no cadastro."""
    if not code:
        return None
    found = next(
        (unit.id for unit in configuracoes.list_measure_units(session) if unit.code == code), None
    )
    if found is None:
        raise InvalidDataError({validation.FIELD_UNIT: validation.UNIT_MESSAGE})
    return found


def _next_package_code(known: Sequence[EapItem], parent: EapItem) -> str:
    """O código seguinte da subárea, considerando os filhos que já existem (inclusive encerrados)."""
    highest = 0
    for item in known:
        if item.parent_id != parent.id:
            continue
        suffix = item.code.rsplit(".", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{parent.code}.{highest + 1}"


def _rescale_free_weights(
    session: Session,
    *,
    user: User,
    packages: Mapping[str, EapItem],
    fixed: Mapping[str, Decimal],
) -> None:
    """Reescala os pacotes livres para a sobra, fechando os 100% com os pesos fixos."""
    free = [item for item in packages.values() if _is_free_package(item, fixed)]
    target = calculations.PERCENT - sum(fixed.values(), Decimal(0))
    weights = calculations.eap_rescale_weights(
        [(item.code, item.weight or Decimal(0)) for item in free], target
    )
    for item in free:
        recording.update(
            session,
            user_id=user.id,
            record=item,
            changes={"weight": weights[item.code]},
            version=item.version,
        )


def _is_free_package(item: EapItem, fixed: Mapping[str, Decimal]) -> bool:
    return item.code not in fixed and (item.weight or Decimal(0)) > 0


def _packages_by_code(session: Session, project_id: int) -> dict[str, EapItem]:
    """Os pacotes de nível 3 do projeto pelo código, na ordem de cadastro."""
    statement = (
        select(EapItem)
        .where(EapItem.project_id == project_id, EapItem.level == LEVEL_PACKAGE)
        .order_by(EapItem.id)
    )
    return {item.code: item for item in session.scalars(statement)}


def _next_revision(session: Session, *, project_id: int) -> int:
    """O número da revisão a gravar: 0 quando o projeto ainda não tem nenhuma."""
    latest = session.scalar(
        select(func.max(EapRevision.revision)).where(EapRevision.project_id == project_id)
    )
    return 0 if latest is None else latest + 1


def _current_revision(session: Session, *, project_id: int) -> int:
    """A revisão vigente do projeto: a maior gravada, ou 0 quando não há nenhuma."""
    latest = session.scalar(
        select(func.max(EapRevision.revision)).where(EapRevision.project_id == project_id)
    )
    return latest or 0


def _freeze_revision(session: Session, *, revision_id: int, packages: Sequence[EapItem]) -> None:
    """Congela o peso de cada pacote de nível 3 na revisão (fato histórico da D5b)."""
    session.add_all(
        EapRevisionItem(revision_id=revision_id, item_id=item.id, weight=item.weight or Decimal(0))
        for item in packages
    )
    session.flush()


def _alteration(new_codes: Sequence[str], adjusted_codes: Sequence[str]) -> str:
    """A alteração da revisão no formato do protótipo: o que entrou, o que mudou e o reescalado."""
    parts: list[str] = []
    if new_codes:
        parts.append(_listed("Pacote", "Pacotes", new_codes, "incluído", "incluídos"))
    if adjusted_codes:
        parts.append(_listed("Pacote", "Pacotes", adjusted_codes, "ajustado", "ajustados"))
    parts.append("demais pesos reescalados")
    return "; ".join(parts)


def _listed(singular: str, plural: str, codes: Sequence[str], one: str, many: str) -> str:
    return f"{singular if len(codes) == 1 else plural} {', '.join(codes)} {one if len(codes) == 1 else many}"


def _plain_weight(value: Decimal | None) -> str:
    """O peso sem zeros à direita: ``3.00`` vira ``3`` e ``2.50`` vira ``2.5``."""
    text = format(value or Decimal(0), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


# ── Apoio da árvore ───────────────────────────────────────────────────────


def _scope_projects(
    scope: Scope, projects: Sequence[configuracoes.ProjectSummary]
) -> tuple[configuracoes.ProjectSummary, ...]:
    if scope.is_portfolio:
        return tuple(projects)
    project = next((item for item in projects if item.id == scope.project_id), None)
    if project is None:
        raise InvalidDataError(EAP_PROJECT_NOT_FOUND_MESSAGE)
    return (project,)


def _items_by_project(
    session: Session, project_ids: Sequence[int]
) -> dict[int, tuple[EapItem, ...]]:
    if not project_ids:
        return {}
    statement = select(EapItem).where(EapItem.project_id.in_(project_ids)).order_by(EapItem.id)
    grouped: dict[int, list[EapItem]] = {}
    for item in session.scalars(statement):
        grouped.setdefault(item.project_id, []).append(item)
    return {project_id: tuple(group) for project_id, group in grouped.items()}


def _lookups(session: Session, items: Sequence[EapItem]) -> _Lookups:
    from src.modulos.financeiro import service as financeiro

    eac_ids = sorted({item.eac_item_id for item in items if item.eac_item_id is not None})
    return _Lookups(
        companies={item.id: item.name for item in configuracoes.list_company_options(session)},
        people={item.id: item.name for item in configuracoes.list_person_options(session)},
        units={item.id: item.code for item in configuracoes.list_measure_units(session)},
        eac_codes=financeiro.eac_item_codes(session, eac_ids),
    )


def _children_by_parent(
    items: Sequence[EapItem],
) -> dict[int | None, tuple[EapItem, ...]]:
    grouped: dict[int | None, list[EapItem]] = {}
    for item in items:
        grouped.setdefault(item.parent_id, []).append(item)
    return {
        parent_id: tuple(sorted(group, key=lambda item: _code_key(item.code)))
        for parent_id, group in grouped.items()
    }


def _steps_by_item(session: Session, item_ids: Sequence[int]) -> dict[int, tuple[EapItemStep, ...]]:
    if not item_ids:
        return {}
    statement = (
        select(EapItemStep)
        .where(EapItemStep.item_id.in_(item_ids))
        .order_by(EapItemStep.item_id, EapItemStep.order, EapItemStep.id)
    )
    grouped: dict[int, list[EapItemStep]] = {}
    for step in session.scalars(statement):
        grouped.setdefault(step.item_id, []).append(step)
    return {item_id: tuple(group) for item_id, group in grouped.items()}


def _measurements_by_item(
    session: Session, item_ids: Sequence[int], lookups: _Lookups
) -> dict[int, tuple[EapMeasurementView, ...]]:
    if not item_ids:
        return {}
    statement = (
        select(EapMeasurement)
        .where(EapMeasurement.item_id.in_(item_ids))
        .order_by(EapMeasurement.item_id, EapMeasurement.measured_on, EapMeasurement.id)
    )
    grouped: dict[int, list[EapMeasurementView]] = {}
    for record in session.scalars(statement):
        grouped.setdefault(record.item_id, []).append(
            EapMeasurementView(
                id=record.id,
                measured_on=record.measured_on,
                from_pct=record.from_pct,
                to_pct=record.to_pct,
                author=lookups.person(record.author_id),
                note=record.note or "",
            )
        )
    return {item_id: tuple(group) for item_id, group in grouped.items()}


def _area_nodes(snapshot: _ProjectSnapshot) -> tuple[EapNode, ...]:
    return tuple(node for node in snapshot.nodes if node.level == LEVEL_AREA)


def _used_changes(revisions: Sequence[EapRevisionView]) -> frozenset[int]:
    return frozenset(view.change_id for view in revisions if view.change_id is not None)


def _totals_of(node: EapNode) -> calculations.EapTotals:
    return calculations.EapTotals(
        weight=node.weight,
        predicted=node.predicted,
        actual=node.actual,
        start=node.start,
        finish=node.finish,
        packages=node.packages,
        planning=node.planning,
        overdue=node.overdue,
        not_started=node.not_started,
    )


def _share_of(value: Decimal, base: Decimal | None) -> Decimal | None:
    """The share of the value in the base, in %, with one place; ``None`` without a base."""
    if base is None or base == 0:
        return None
    return (value / base * calculations.PERCENT).quantize(
        calculations.ONE_PLACE, rounding=ROUND_HALF_UP
    )


def _weight_of(nodes: Sequence[EapNode]) -> Decimal:
    total = sum((node.weight for node in nodes), Decimal(0))
    return total.quantize(calculations.TWO_PLACES, rounding=ROUND_HALF_UP)


def _spi(actual: Decimal, predicted: Decimal) -> Decimal | None:
    if predicted == 0:
        return None
    return (actual / predicted).quantize(calculations.TWO_PLACES, rounding=ROUND_HALF_UP)


def _code_key(code: str) -> tuple[int, ...]:
    return tuple(int(part) for part in code.split(".") if part.isdigit())


def _project_label(project: configuracoes.ProjectSummary) -> str:
    return f"{project.code} · {project.name}"
