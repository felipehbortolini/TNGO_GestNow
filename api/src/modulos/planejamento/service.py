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
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, selectinload

from src.core import audit, calendario, rbac, recording, versioning
from src.core.audit import TrailLine
from src.core.errors import InvalidDataError
from src.core.import_values import normalize_text
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, validation
from src.modulos.planejamento.models import (
    Lookahead,
    LookaheadConstraint,
    LookaheadWeek,
    Report,
    ReportActivity,
    ReportPoint,
)
from src.modulos.planejamento.validation import MONTHLY, WEEKLY, PointInput

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
