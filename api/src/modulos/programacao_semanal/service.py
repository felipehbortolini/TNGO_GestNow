"""Business facade of the Weekly Scheduling: the week, the window and the flow (D10).

The matrix of the week and the programming by the supplier (ISSUE-051), the flow of
five steps (ISSUE-052) and the change requests with the governance panel (ISSUE-053):
the planner validates and names the inspector, the foreman or the supplier reports the
done work by shift, the inspector approves or reopens it, and the planner publishes it;
the supplier asks for a change on what is closed for editing and the planner applies
(reopening the activity) or refuses it. The rules are the app's, adapted as D10 says:
the app's "ambiente" is the project of the scope (D8, with the Portfólio read-only),
companies, people and locations come from Configurações (``configuracoes.registers``),
the roles are the per-project roles of D7 and every write leaves the trail with before
and after (D5b).

* **A supplier sees and writes only its own company**, always, with the cut made
  here and never on the screen: a list is cut by ``rbac.company_scope``, and
  reaching for another company's activity is 403 (``rbac.require_company``).
* **The window binds the supplier**: outside it the write is refused with the message
  of the app. The Timenow team writes as support, without the window.
* **No project, no write**: in the Portfólio the matrix is read-only and the write asks
  for a project (``Scope.require_project``).
* **Every step belongs to a role of the project**: validating, reporting, approving and
  publishing are refused with 403 for the others (D7); the situation and the approval of
  the done work are distinct states, as in the app.
* **A change request is for the closed item**: publicada or approved, exactly where
  the app offers the button; the planner decides and applying reopens the activity.
* **The configuration is per project** (ISSUE-054): the parameters and the windows of
  each company are edited by the Planner of the project or the Admin, effective at once
  and with the before and after in the single trail; a project without a row reads the
  app's defaults, and ``ensure_settings`` writes the row with them (ISSUE-078 calls it).

Nothing here reads the clock: the caller passes the instant in the ``Caller``
(``core.calendario.now``). Every write goes through ``core.recording`` with the
version the screen opened.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.core import audit, calendario, rbac, recording, versioning
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry
from src.core.rbac import ScheduleRole, User
from src.core.scope import Scope
from src.modulos.configuracoes import registers
from src.modulos.configuracoes.registers import Option
from src.modulos.programacao_semanal import (
    calculations,
    permissions,
    presentation,
    repository,
    validation,
    weeks,
)
from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.models import (
    Activity,
    ActivityDay,
    ChangeRequest,
    ScheduleSettings,
    ScheduleWindow,
    WindowExtraRelease,
    WindowWeek,
    WindowWeekday,
)
from src.modulos.programacao_semanal.validation import (
    ActivityForm,
    ApprovalForm,
    DecisionForm,
    DoneForm,
    ValidationForm,
)
from src.modulos.programacao_semanal.views import (
    ActivityView,
    ChangeRequestView,
    GovernanceLine,
    GovernancePanel,
    GovernanceTrailEvent,
    RequestQueue,
    SituationCounts,
    WindowView,
)

NOT_FOUND_MESSAGE = "Atividade não encontrada."
INVALID_WEEK_MESSAGE = validation.INVALID_WEEK_MESSAGE
HAS_REQUESTS_MESSAGE = "A atividade tem pedidos de alteração e não pode ser excluída."
PORTFOLIO_READ_ONLY = "No Portfólio a programação é só de leitura: escolha um projeto para gravar."
TIMENOW_SUPPORT = "Equipe Timenow — programação liberada como apoio."
LOCATION_MISSING = (
    "O local escolhido não está cadastrado neste projeto. Cadastre em Configurações, em Locais."
)
COMPANY_MISSING = "A empresa escolhida não está cadastrada. Cadastre em Configurações, em Empresas."
UNIT_MISSING = "A unidade escolhida não está cadastrada. Cadastre em Configurações, em Unidades."
FOREMAN_MISSING = (
    "A pessoa escolhida não tem o papel de Encarregado neste projeto. "
    "Dê o papel em Configurações, em Colaboradores."
)
INSPECTOR_MISSING = (
    "A pessoa escolhida não tem o papel de Fiscal neste projeto. "
    "Dê o papel em Configurações, em Colaboradores."
)

# The messages of the flow (ISSUE-052), as the app has them.
ONLY_DRAFT_VALIDATED = "Só programação em elaboração pode ser validada."
INSPECTOR_REQUIRED = (
    "Escolha um fiscal — a lista vem dos colaboradores com o papel de Fiscal neste projeto."
)
APPROVAL_FROZEN = "O realizado já foi aprovado pelo fiscal e não pode mudar."
REPORT_BEFORE_VALIDATION = (
    "A programação ainda não foi validada pelo planejador — não há o que reportar."
)
NEGATIVE_DONE = "Quantidade realizada não pode ser negativa."
APPROVE_AFTER_VALIDATION = "O realizado só chega ao fiscal depois da validação do planejador."
NOTHING_TO_APPROVE = "Não há realizado registrado para aprovar."
REOPEN_NOT_APPROVED = "Este realizado não está aprovado."
REOPEN_REASON_REQUIRED = "Explique por que está reabrindo o realizado."
ONLY_VALIDATED_PUBLISHED = "Só programação validada pode ser publicada."
DEVIATION_DEMANDS_NOTE = (
    "O realizado está {deviation:.0f}% distante do previsto (limite de {limit:g}%). "
    "Explique o desvio para salvar."
)

# The change requests (ISSUE-053), as the app has them.
REQUEST_PENDING = "pendente"
REQUEST_APPLIED = "aplicado"
REQUEST_REJECTED = "rejeitado"
REQUEST_SITUATIONS = (REQUEST_PENDING, REQUEST_APPLIED, REQUEST_REJECTED)

REQUEST_MIN_REASON = 10
REQUEST_MIN_ANSWER = 5
REQUEST_RESOLVED_LIMIT = 20
TRAIL_LIMIT = 40
REQUEST_NOT_FOUND_MESSAGE = "Pedido não encontrado."
REQUEST_REASON_REQUIRED = "Explique o que precisa mudar, e por quê, em uma frase."
REQUEST_ANSWER_REQUIRED = "Diga por que o pedido está sendo recusado."
REQUEST_ALREADY_DECIDED = "Este pedido já foi decidido."
REQUEST_EDITABLE = (
    "A atividade ainda está aberta para edição: o pedido de alteração é para o que "
    "está publicado ou com o realizado aprovado."
)
REQUEST_OPEN_TOAST = "Pedido registrado para {unique_id}."
REQUEST_APPLY_TOAST = "{unique_id} liberado para alteração."
REQUEST_REJECT_TOAST = "Pedido de {unique_id} recusado."

# The module's entities the governance trail reads; the day lines stay out so a single
# report of seven days does not bury the transitions with seven entries at once.
TRAIL_ENTITIES = (
    Activity.__tablename__,
    ChangeRequest.__tablename__,
    ScheduleWindow.__tablename__,
    ScheduleSettings.__tablename__,
)

# How the history of the detail panel names the transitions a trail line caused.
_TRAIL_SITUATION_LABELS = {
    calculations.SITUATION_VALIDATED: "Programação validada",
    calculations.SITUATION_PUBLISHED: "Programação publicada",
}
_TRAIL_APPROVAL_LABELS = {
    calculations.APPROVAL_APPROVED: "Realizado aprovado",
    calculations.APPROVAL_PENDING: "Realizado reaberto",
}

# The defaults of the app for a project that has no configuration row yet (D10); the
# configuration screen (ISSUE-054) writes the row, and ``ensure_settings`` creates it.
DEFAULT_ADHERENCE_TARGET = validation.DEFAULT_ADHERENCE_TARGET
DEFAULT_PPC_TARGET = validation.DEFAULT_PPC_TARGET
DEFAULT_DEVIATION_LIMIT = validation.DEFAULT_DEVIATION_LIMIT

# The configuration of the schedule (ISSUE-054), as the app words it.
SETTINGS_SAVED = "Parâmetros da programação salvos."
WINDOW_SAVED = "Janela de {company} atualizada."
CONFIGURATION_COMPANY_MISSING = "A empresa escolhida não está cadastrada."

SORTABLE = (
    "item",
    "id",
    "atividade",
    "local",
    "empresa",
    "encarregado",
    "fiscal",
    "situacao",
    "previsto",
    "realizado",
    "ppc",
)
BANDS = (calculations.BAND_HIGH, calculations.BAND_MEDIUM, calculations.BAND_LOW)

# Fields a free-text search looks into, as the app does.
_SEARCH_FIELDS = ("unique_id", "description", "location", "company", "foreman", "inspector")


@dataclass(frozen=True)
class Caller:
    """Who asks, in which scope and when: what the facade receives from the route.

    ``now`` is the instant of the request (``core.calendario.now``), the only place the
    clock enters; the window and the dates of the week are decided from it.
    """

    user: User
    scope: Scope
    now: datetime


@dataclass(frozen=True)
class ScheduleParameters:
    """The parameters of the project's schedule: the targets and the deviation rule."""

    adherence_target: float = DEFAULT_ADHERENCE_TARGET
    ppc_target: float = DEFAULT_PPC_TARGET
    reference_week: str = ""
    requires_deviation_note: bool = True
    deviation_limit: float = DEFAULT_DEVIATION_LIMIT


@dataclass(frozen=True)
class Filters:
    """What the toolbar and the refinement panel ask of the week."""

    location_id: int | None = None
    company_id: int | None = None
    foreman_id: int | None = None
    inspector_id: int | None = None
    situation: str = ""
    approval: str = ""
    band: str = ""
    search: str = ""
    sort: str = ""
    direction: str = "asc"

    @property
    def active_count(self) -> int:
        """How many refinements are on, for the badge of the button."""
        refinements = (
            self.location_id,
            self.company_id,
            self.foreman_id,
            self.inspector_id,
            self.situation,
            self.approval,
            self.band,
            self.search,
        )
        return sum(1 for value in refinements if value)


def parse_filters(params: Mapping[str, str | None]) -> Filters:
    """Read the filters of the query string; anything unknown reads as "no filter"."""
    situation = _text(params, "situacao")
    approval = _text(params, "aprovacao")
    band = _text(params, "ppc")
    sort = _text(params, "ordena")
    return Filters(
        location_id=validation.parse_id(params.get("local")),
        company_id=validation.parse_id(params.get("empresa")),
        foreman_id=validation.parse_id(params.get("encarregado")),
        inspector_id=validation.parse_id(params.get("responsavel")),
        situation=situation if situation in calculations.SITUATIONS else "",
        approval=approval if approval in calculations.APPROVALS else "",
        band=band if band in BANDS else "",
        search=_text(params, "busca"),
        sort=sort if sort in SORTABLE else "",
        direction="desc" if _text(params, "ordem").lower() == "desc" else "asc",
    )


@dataclass(frozen=True)
class WeekSummary:
    """The numbers of the strip above the matrix."""

    total: int
    adherence: float
    mean_ppc: float
    awaiting_inspector: int
    low_band: int


@dataclass(frozen=True)
class WindowStatus:
    """What the banner says about the window, and whether the user may start a write now."""

    is_supplier: bool
    is_portfolio: bool
    is_open: bool
    reason: str
    company: str
    can_create: bool
    can_pick_project: bool = False


@dataclass(frozen=True)
class FormOptions:
    """The registers the select fields of the form and the filters offer."""

    locations: list[Option]
    companies: list[Option]
    units: list[Option]
    foremen: list[Option]
    inspectors: list[Option]


@dataclass(frozen=True)
class NewActivity:
    """Everything one activity is born with: the write every path shares."""

    project_id: int
    company_id: int
    week: str
    unique_id: str
    item: int
    description: str
    planned_headline: float
    author_person_id: int
    at: datetime
    location_id: int | None = None
    unit_id: int | None = None
    inspector_id: int | None = None
    foreman_id: int | None = None
    planned_days: tuple[float, ...] = (0.0,) * calculations.DAYS
    day_shift: tuple[float, ...] = (0.0,) * calculations.DAYS
    night_shift: tuple[float, ...] = (0.0,) * calculations.DAYS
    situation: str = calculations.SITUATION_DRAFT
    approval: str = calculations.APPROVAL_PENDING
    supplier_notes: str = ""
    approved_at: datetime | None = None
    published_at: datetime | None = None


# ── Parameters and weeks ─────────────────────────────────────────────────


def today_of(now: datetime) -> date:
    """The date of an instant in the product's timezone: the "hoje" of the week."""
    return calendario.in_product_timezone(now).date()


def parameters_of(session: Session, project_id: int | None) -> ScheduleParameters:
    """The parameters of the project; the app's defaults for the Portfólio and a new project."""
    row = repository.settings_of(session, project_id) if project_id is not None else None
    if row is None:
        return ScheduleParameters()
    return ScheduleParameters(
        adherence_target=row.adherence_target,
        ppc_target=row.ppc_target,
        reference_week=row.reference_week or "",
        requires_deviation_note=row.requires_deviation_note,
        deviation_limit=row.deviation_limit,
    )


def default_week(session: Session, *, caller: Caller) -> str:
    """The week a screen opens on: the project's reference week, or the current one."""
    reference = parameters_of(session, caller.scope.project_id).reference_week
    return reference if weeks.is_valid(reference) else weeks.of_date(today_of(caller.now))


def resolve_week(session: Session, *, caller: Caller, raw: str | None) -> str:
    """The week asked for in the address; the default one when it is empty or not a real week."""
    asked = (raw or "").strip()
    if weeks.is_valid(asked):
        return weeks.reference(*weeks.parts(asked))
    return default_week(session, caller=caller)


def horizon_weeks(session: Session, *, caller: Caller) -> list[weeks.WeekInfo]:
    """The weeks with data plus the ones released for programming and the ones around, in order."""
    project_id = caller.scope.project_id
    company_id = rbac.company_scope(caller.user)
    found = set(weeks.horizon(default_week(session, caller=caller), back=1, ahead=1))
    found |= repository.weeks_with_activity(session, project_id=project_id, company_id=company_id)
    found |= repository.released_weeks(session, project_id=project_id, company_id=company_id)
    return [
        weeks.describe(week) for week in sorted(found, key=weeks.sort_key) if weeks.is_valid(week)
    ]


# ── Reading the week ─────────────────────────────────────────────────────


def list_activities(
    session: Session, *, caller: Caller, week: str, filters: Filters | None = None
) -> list[ActivityView]:
    """The activities of the week the user may see, filtered and sorted.

    A supplier gets only its own company, whatever the screen asked (D7). In the
    Portfólio every project is read, and nothing can be edited.
    """
    rows = repository.activities(
        session,
        project_id=caller.scope.project_id,
        week=week,
        company_id=rbac.company_scope(caller.user),
    )
    views = _views(session, caller=caller, activities=rows)
    return apply_filters(views, filters or Filters())


def week_summary(views: list[ActivityView]) -> WeekSummary:
    """The strip: how many, adherence, mean PPC, waiting for the inspector, low band."""
    figures = [view.figures for view in views]
    return WeekSummary(
        total=len(views),
        adherence=calculations.schedule_adherence(figures),
        mean_ppc=calculations.mean_ppc(figures),
        awaiting_inspector=sum(
            1
            for view in views
            if view.approval == calculations.APPROVAL_PENDING and view.figures.has_done
        ),
        low_band=sum(1 for view in views if view.figures.band == calculations.BAND_LOW),
    )


def get_activity(session: Session, *, caller: Caller, activity_id: int) -> ActivityView:
    """One activity for the form, or 403 when it belongs to another company (D7)."""
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    return _views(session, caller=caller, activities=[activity])[0]


def window_status(session: Session, *, caller: Caller, week: str) -> WindowStatus:
    """The state of the window for the user in the week, to say it and to enable the button."""
    user = caller.user
    supplier = permissions.is_supplier(user)
    if caller.scope.is_portfolio:
        return WindowStatus(
            is_supplier=supplier,
            is_portfolio=True,
            is_open=False,
            reason=PORTFOLIO_READ_ONLY,
            company="",
            can_create=False,
            can_pick_project=permissions.can_create_somewhere(user),
        )
    project_id = caller.scope.require_project()
    allowed = permissions.can_create(user, project_id)
    if not supplier:
        return WindowStatus(
            is_supplier=False,
            is_portfolio=False,
            is_open=True,
            reason=TIMENOW_SUPPORT,
            company="",
            can_create=allowed,
        )
    company_id = rbac.company_scope(user) or 0
    decision = _decision(
        session, project_id=project_id, company_id=company_id, week=week, now=caller.now
    )
    names = registers.company_names(session, [company_id])
    return WindowStatus(
        is_supplier=True,
        is_portfolio=False,
        is_open=decision.is_open,
        reason=decision.reason,
        company=names.get(company_id, ""),
        can_create=allowed and decision.is_open,
    )


def form_options(session: Session, *, user: User, project_id: int) -> FormOptions:
    """The registers the form offers; a supplier sees only its own company and its own foremen."""
    company_id = rbac.company_scope(user)
    return FormOptions(
        locations=registers.list_locations(session, project_id=project_id),
        companies=registers.list_companies(session, only=company_id),
        units=registers.list_measure_units(session),
        foremen=registers.list_people_with_role(
            session,
            project_id=project_id,
            role=ScheduleRole.FOREMAN.value,
            company_id=company_id,
        ),
        inspectors=registers.list_people_with_role(
            session, project_id=project_id, role=ScheduleRole.INSPECTOR.value
        ),
    )


def next_item(session: Session, *, project_id: int, week: str) -> int:
    """The item the next activity of the week takes, to show it in the form."""
    return repository.next_item(session, project_id=project_id, week=week)


def form_of(view: ActivityView) -> ActivityForm:
    """The form of an activity as the edit screen fills it."""
    return ActivityForm(
        week=view.week,
        unique_id=view.unique_id,
        description=view.description,
        notes=view.notes,
        location_id=view.location_id,
        company_id=view.company_id,
        foreman_id=view.foreman_id,
        inspector_id=view.inspector_id,
        unit_id=view.unit_id,
        headline=view.planned_headline,
        planned_days=view.figures.planned_days,
    )


@dataclass(frozen=True)
class FormScreen:
    """What the drawer of an activity needs: the typed values, the registers and the item."""

    form: ActivityForm
    week: str
    view: ActivityView | None
    item: int
    options: FormOptions


def open_form(
    session: Session,
    *,
    caller: Caller,
    activity_id: int | None,
    week: str,
    typed: ActivityForm | None = None,
) -> FormScreen:
    """Prepare the drawer of a new or an existing activity; ``typed`` refills it after a 422.

    Needs a project (D8) and the right to program (or to edit) in it, else 403.
    """
    user = caller.user
    project_id = caller.scope.require_project()
    view = None
    if activity_id is None:
        if not permissions.can_create(user, project_id):
            raise AccessDeniedError(permissions.CREATE_DENIED)
        item = next_item(session, project_id=project_id, week=week)
    else:
        if not permissions.can_edit(user, project_id):
            raise AccessDeniedError(permissions.EDIT_DENIED)
        view = get_activity(session, caller=caller, activity_id=activity_id)
        item = view.item
        week = view.week
    if typed is not None:
        form = typed
    elif view is not None:
        form = form_of(view)
    else:
        form = ActivityForm(week=week, company_id=rbac.company_scope(user))
    options = form_options(session, user=user, project_id=project_id)
    return FormScreen(form=form, week=week, view=view, item=item, options=options)


# ── The panels of the flow ───────────────────────────────────────────────


@dataclass(frozen=True)
class FlowScreen:
    """What a panel of the flow needs: the activity, the parameters and the registers."""

    view: ActivityView
    parameters: ScheduleParameters
    options: FormOptions


def flow_screen(session: Session, *, caller: Caller, activity_id: int) -> FlowScreen:
    """The activity of the scope with the parameters and registers of its project.

    No transition permission is asked here: the openers check it, and the re-render of
    a refused save reuses this to draw the panel again.
    """
    view = get_activity(session, caller=caller, activity_id=activity_id)
    return FlowScreen(
        view=view,
        parameters=parameters_of(session, view.project_id),
        options=form_options(session, user=caller.user, project_id=view.project_id),
    )


def open_validation(session: Session, *, caller: Caller, activity_id: int) -> FlowScreen:
    """The panel of validation: the planner or the Admin, in the project."""
    project_id = caller.scope.require_project()
    if not permissions.can_validate(caller.user, project_id):
        raise AccessDeniedError(permissions.VALIDATE_DENIED)
    return flow_screen(session, caller=caller, activity_id=activity_id)


def open_report(session: Session, *, caller: Caller, activity_id: int) -> FlowScreen:
    """The panel of the done work: who reports, over a validated and open activity."""
    project_id = caller.scope.require_project()
    if not permissions.can_report(caller.user, project_id):
        raise AccessDeniedError(permissions.REPORT_DENIED)
    screen = flow_screen(session, caller=caller, activity_id=activity_id)
    activity = screen.view
    if activity.approval == calculations.APPROVAL_APPROVED:
        raise AccessDeniedError(APPROVAL_FROZEN)
    if activity.situation == calculations.SITUATION_DRAFT:
        raise AccessDeniedError(REPORT_BEFORE_VALIDATION)
    return screen


def open_approval(session: Session, *, caller: Caller, activity_id: int) -> FlowScreen:
    """The panel of approval or reopening: the inspector or the Admin, in the project."""
    project_id = caller.scope.require_project()
    if not permissions.can_approve(caller.user, project_id):
        raise AccessDeniedError(permissions.APPROVE_DENIED)
    return flow_screen(session, caller=caller, activity_id=activity_id)


def open_detail(session: Session, *, caller: Caller, activity_id: int) -> FlowScreen:
    """The read-only panel of an activity; in the Portfólio it reads every project (D8)."""
    return flow_screen(session, caller=caller, activity_id=activity_id)


# ── Writing ──────────────────────────────────────────────────────────────


def create_activity(session: Session, *, caller: Caller, form: ActivityForm) -> Activity:
    """Create an activity of the project in the scope, as the person who programs.

    Refuses with 422 in the Portfólio (no project), 403 when the user may not program
    here or the window is closed, and 422 with one message per field when the data does
    not hold up.
    """
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_create(user, project_id):
        raise AccessDeniedError(permissions.CREATE_DENIED)

    form = replace(form, week=form.week or default_week(session, caller=caller))
    form = _with_supplier_company(user, form)
    if weeks.is_valid(form.week):
        _require_window_open(
            session, caller=caller, company_id=form.company_id or 0, week=form.week
        )
    _raise_errors(session, user=user, project_id=project_id, form=form, excluding=None)

    return store_activity(
        session,
        author_id=user.id,
        new=NewActivity(
            project_id=project_id,
            company_id=_company_of(form),
            week=form.week,
            unique_id=form.unique_id,
            item=repository.next_item(session, project_id=project_id, week=form.week),
            description=form.description,
            planned_headline=form.headline,
            author_person_id=user.person_id,
            at=caller.now,
            location_id=form.location_id,
            unit_id=form.unit_id,
            inspector_id=form.inspector_id,
            foreman_id=form.foreman_id,
            planned_days=form.planned_days,
            supplier_notes=form.notes,
        ),
    )


def update_activity(
    session: Session,
    *,
    caller: Caller,
    activity_id: int,
    form: ActivityForm,
    version: str | None,
) -> Activity:
    """Change the programming of an activity, with the version the screen opened (D5).

    The week stays the activity's own. A published activity only the planner or the Admin
    edit; a supplier edits only inside its window and only its own company's.
    """
    user = caller.user
    project_id = caller.scope.require_project()
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    if not permissions.can_edit(user, project_id):
        raise AccessDeniedError(permissions.EDIT_DENIED)
    published = activity.situation == calculations.SITUATION_PUBLISHED
    if published and not permissions.can_publish(user, project_id):
        raise AccessDeniedError(permissions.PUBLISHED_LOCKED)
    _require_window_open(session, caller=caller, company_id=activity.company_id, week=activity.week)

    form = _with_supplier_company(user, replace(form, week=activity.week), activity=activity)
    form = replace(form, inspector_id=form.inspector_id or activity.inspector_id)
    _raise_errors(session, user=user, project_id=project_id, form=form, excluding=activity.id)

    changes: dict[str, Any] = {
        "unique_id": form.unique_id,
        "description": form.description,
        "location_id": form.location_id,
        "company_id": _company_of(form),
        "unit_id": form.unit_id,
        "inspector_id": form.inspector_id,
        "foreman_id": form.foreman_id,
        "planned_headline": form.headline,
        "supplier_notes": form.notes,
        "updated_by_id": user.person_id,
        "updated_at": caller.now,
    }
    recording.update(session, user_id=user.id, record=activity, changes=changes, version=version)
    _change_planned_days(session, user_id=user.id, activity=activity, planned=form.planned_days)
    return activity


def delete_activity(
    session: Session, *, caller: Caller, activity_id: int, version: str | None
) -> Activity:
    """Delete an activity and its days: the Admin only, and only without change requests."""
    user = caller.user
    caller.scope.require_project()
    if not permissions.can_delete(user):
        raise AccessDeniedError(permissions.DELETE_DENIED)
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    requests = session.scalar(
        select(func.count())
        .select_from(ChangeRequest)
        .where(ChangeRequest.activity_id == activity.id)
    )
    if requests:
        raise InvalidDataError(HAS_REQUESTS_MESSAGE)

    for day in _days_of(session, activity.id):
        line = _day_line(user.id, activity.project_id, day, audit.DELETED, audit.snapshot(day))
        session.execute(delete(ActivityDay).where(ActivityDay.id == day.id))
        audit.append(session, line)
    recording.delete(session, user_id=user.id, record=activity, version=version)
    return activity


def store_activity(session: Session, *, author_id: int, new: NewActivity) -> Activity:
    """Write one activity and its seven days with the trail, after the checks of the caller.

    The path every creation shares: the form of the screen goes through the checks of
    ``create_activity`` and ends here; the demonstration load and the spreadsheet import
    arrive with their own state (situation, approval, done) and end here too.
    """
    activity = Activity(
        project_id=new.project_id,
        company_id=new.company_id,
        location_id=new.location_id,
        unit_id=new.unit_id,
        inspector_id=new.inspector_id,
        foreman_id=new.foreman_id,
        created_by_id=new.author_person_id,
        updated_by_id=new.author_person_id,
        approved_by_id=new.inspector_id if new.approved_at else None,
        week=new.week,
        unique_id=new.unique_id,
        item=new.item,
        description=new.description,
        planned_headline=new.planned_headline,
        situation=new.situation,
        approval=new.approval,
        supplier_notes=new.supplier_notes,
        timenow_comments="",
        created_at=new.at,
        updated_at=new.at,
        approved_at=new.approved_at,
        published_at=new.published_at,
    )
    recording.create(session, user_id=author_id, record=activity)
    planned = calculations.seven_days(new.planned_days)
    day_shift = calculations.seven_days(new.day_shift)
    night_shift = calculations.seven_days(new.night_shift)
    for index in range(calculations.DAYS):
        day = ActivityDay(
            activity_id=activity.id,
            day=index + 1,
            planned=planned[index],
            done_day_shift=day_shift[index],
            done_night_shift=night_shift[index],
        )
        session.add(day)
        session.flush()
        audit.append(session, _day_line(author_id, new.project_id, day, audit.CREATED, before=None))
    return activity


def store_settings(
    session: Session,
    *,
    author_id: int,
    project_id: int,
    parameters: ScheduleParameters,
) -> ScheduleSettings:
    """Write the parameters row of a project with the trail (the demonstration load).

    The configuration screen (ISSUE-054) edits the row; until then a project without a row
    reads the defaults of the app (``parameters_of``).
    """
    row = ScheduleSettings(
        project_id=project_id,
        adherence_target=parameters.adherence_target,
        ppc_target=parameters.ppc_target,
        reference_week=parameters.reference_week or None,
        requires_deviation_note=parameters.requires_deviation_note,
        deviation_limit=parameters.deviation_limit,
    )
    recording.create(session, user_id=author_id, record=row)
    return row


def store_window(
    session: Session, *, author_id: int, project_id: int, rules: window_rules.Window
) -> ScheduleWindow:
    """Write the window of a company in a project: its weekdays, released weeks and extras."""
    row = ScheduleWindow(project_id=project_id, company_id=rules.company_id)
    recording.create(session, user_id=author_id, record=row)
    _write_window_rules(session, row, rules)
    session.flush()
    return row


# ── The configuration of the project (ISSUE-054) ─────────────────────────


@dataclass(frozen=True)
class SettingsWindow:
    """One company's window as the configuration screen reads it."""

    company_id: int
    company: str
    version: int | None
    days: tuple[window_rules.WindowDay, ...]
    weeks: tuple[str, ...]
    extras: tuple[window_rules.ExtraRelease, ...]
    is_open: bool
    reason: str


@dataclass(frozen=True)
class ScheduleConfiguration:
    """The configuration of the scope: the parameters and the windows of the project."""

    project_id: int | None
    project_label: str
    is_portfolio: bool
    can_edit: bool
    has_row: bool
    settings_version: int | None
    parameters: ScheduleParameters
    windows: list[SettingsWindow]


def configuration_of(session: Session, *, caller: Caller) -> ScheduleConfiguration:
    """The parameters and the windows of the project; in the Portfólio only the notice (D8).

    The parameters come from the row when the project has one and from the app's defaults
    when it does not; the windows are one per company of the register, with the state of
    the reference week. Nothing here writes: the screen of the Portfólio is read-only.
    """
    project_id = caller.scope.project_id
    parameters = parameters_of(session, project_id)
    if project_id is None:
        return ScheduleConfiguration(
            project_id=None,
            project_label="",
            is_portfolio=True,
            can_edit=False,
            has_row=False,
            settings_version=None,
            parameters=parameters,
            windows=[],
        )
    row = repository.settings_of(session, project_id)
    week = default_week(session, caller=caller)
    now_local = calendario.in_product_timezone(caller.now)
    return ScheduleConfiguration(
        project_id=project_id,
        project_label=registers.project_labels(session, {project_id}).get(project_id, ""),
        is_portfolio=False,
        can_edit=permissions.can_manage_settings(caller.user, project_id),
        has_row=row is not None,
        settings_version=row.version if row is not None else None,
        parameters=parameters,
        windows=[
            _settings_window(
                session,
                option,
                project_id=project_id,
                week=week,
                now=now_local,
            )
            for option in _configuration_companies(session, caller.user)
        ],
    )


def _configuration_companies(session: Session, user: User) -> list[Option]:
    """The companies the configuration lists: every one, or only the supplier's own (D7)."""
    return registers.list_companies(session, only=rbac.company_scope(user))


def _settings_window(
    session: Session, option: Option, *, project_id: int, week: str, now: datetime
) -> SettingsWindow:
    """One company's window with its rules and the open-or-closed state of the week."""
    row = repository.window_row_of(session, project_id=project_id, company_id=option.id)
    window = repository.window_of_row(session, row) if row is not None else None
    decision = window_rules.decide(week, window, now)
    return SettingsWindow(
        company_id=option.id,
        company=option.label,
        version=row.version if row is not None else None,
        days=window.days if window is not None else (),
        weeks=tuple(sorted(window.weeks, key=weeks.sort_key)) if window is not None else (),
        extras=window.extras if window is not None else (),
        is_open=decision.is_open,
        reason=decision.reason,
    )


def ensure_settings(session: Session, *, author_id: int, project_id: int) -> ScheduleSettings:
    """The configuration row of a project, created with the app's defaults (D10, ISSUE-078).

    A project is born with the values the app gave a new environment (60/75/15, the
    deviation rule on); the creation of a project calls this, and a project that still
    lived on the defaults gets its row on the first save of the configuration screen.
    """
    row = repository.settings_of(session, project_id)
    if row is not None:
        return row
    row = ScheduleSettings(
        project_id=project_id,
        adherence_target=DEFAULT_ADHERENCE_TARGET,
        ppc_target=DEFAULT_PPC_TARGET,
        reference_week=None,
        requires_deviation_note=True,
        deviation_limit=DEFAULT_DEVIATION_LIMIT,
    )
    recording.create(session, user_id=author_id, record=row)
    return row


def save_parameters(
    session: Session,
    *,
    caller: Caller,
    form: validation.ScheduleSettingsForm,
    version: str | None,
) -> ScheduleSettings:
    """Write the parameters of the project, effective at once, with before and after (D10).

    Only the Planner of the project or the Admin; unlike the general parameters of the
    platform there is no versioning with justification — the single trail keeps the before
    and the after, and the next request already reads the new value.
    """
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_manage_settings(user, project_id):
        raise AccessDeniedError(permissions.SETTINGS_DENIED)
    errors = validation.settings_errors(form)
    if errors:
        raise InvalidDataError(errors)

    row = repository.settings_of(session, project_id)
    if row is None:
        row = ScheduleSettings(
            project_id=project_id,
            adherence_target=form.adherence_target,
            ppc_target=form.ppc_target,
            reference_week=form.reference_week or None,
            requires_deviation_note=form.requires_deviation_note,
            deviation_limit=form.deviation_limit,
        )
        recording.create(session, user_id=user.id, record=row)
        return row
    recording.update(
        session,
        user_id=user.id,
        record=row,
        changes={
            "adherence_target": form.adherence_target,
            "ppc_target": form.ppc_target,
            "reference_week": form.reference_week or None,
            "requires_deviation_note": form.requires_deviation_note,
            "deviation_limit": form.deviation_limit,
        },
        version=version,
    )
    return row


def save_window(
    session: Session,
    *,
    caller: Caller,
    form: validation.WindowForm,
    version: str | None,
) -> ScheduleWindow:
    """Write the window of a company: its days, released weeks and extraordinary releases.

    The rules replace the previous set, as the app saves them; the trail keeps the before
    and the after with the rules, not just the row. Creating a window has no version to
    compare; editing one demands the version the screen opened (409).
    """
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_manage_settings(user, project_id):
        raise AccessDeniedError(permissions.SETTINGS_DENIED)
    errors = validation.window_errors(form)
    company_id = form.company_id
    if company_id is None:
        raise InvalidDataError(errors or {"empresa": validation.WINDOW_COMPANY_REQUIRED})
    if not _offers(registers.list_companies(session), company_id):
        raise InvalidDataError({**errors, "empresa": CONFIGURATION_COMPANY_MISSING})
    if errors:
        raise InvalidDataError(errors)

    row = repository.window_row_of(session, project_id=project_id, company_id=company_id)
    before = _window_snapshot(session, row)
    current = repository.window_of_row(session, row) if row is not None else None
    if row is None:
        row = ScheduleWindow(project_id=project_id, company_id=company_id)
        session.add(row)
        session.flush()
        action = audit.CREATED
    else:
        versioning.require(session, row, version)
        _clear_window_rules(session, row)
        versioning.advance(row)
        session.flush()
        action = audit.UPDATED

    catalog = validation.merge_extras(current.extras if current is not None else (), form)
    _write_window_rules(
        session, row, validation.window_of(form, company_id=company_id, extras=catalog)
    )
    session.flush()
    audit.append(
        session,
        audit.TrailLine(
            user_id=user.id,
            entity=ScheduleWindow.__tablename__,
            record_id=row.id,
            action=action,
            before=before,
            after=_window_snapshot(session, row),
            project_id=project_id,
            occurred_at=caller.now,
        ),
    )
    return row


# ── The five steps of the flow ───────────────────────────────────────────


def validate_activity(
    session: Session,
    *,
    caller: Caller,
    activity_id: int,
    form: ValidationForm,
    version: str | None,
) -> Activity:
    """Validate an activity of the week and name the inspector who approves the done work.

    The planner (or the Admin) only validates what is still in elaboration, and the
    inspector is required: a validated programming without one is a pending question
    that only shows up later, when someone looks for who approves.
    """
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_validate(user, project_id):
        raise AccessDeniedError(permissions.VALIDATE_DENIED)
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    if activity.situation != calculations.SITUATION_DRAFT:
        raise InvalidDataError(ONLY_DRAFT_VALIDATED)
    if form.inspector_id is None or not _offers(
        form_options(session, user=user, project_id=project_id).inspectors, form.inspector_id
    ):
        raise InvalidDataError({"responsavel": INSPECTOR_REQUIRED})

    changes: dict[str, Any] = {
        "situation": calculations.SITUATION_VALIDATED,
        "inspector_id": form.inspector_id,
        "updated_by_id": user.person_id,
        "updated_at": caller.now,
    }
    if form.comments:
        changes["timenow_comments"] = _append_comment(activity, form.comments, user, caller.now)
    recording.update(session, user_id=user.id, record=activity, changes=changes, version=version)
    return activity


def report_done(
    session: Session,
    *,
    caller: Caller,
    activity_id: int,
    form: DoneForm,
    version: str | None,
) -> Activity:
    """Report what was produced, by shift and day; the deviation rule demands a note.

    Only over validated programming and while the done work is not approved (the
    approval freezes it). The rule of the deviation is the app's: when the total is
    farther from the plan than the parameter's limit, the note is required.
    """
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_report(user, project_id):
        raise AccessDeniedError(permissions.REPORT_DENIED)
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    if activity.approval == calculations.APPROVAL_APPROVED:
        raise AccessDeniedError(APPROVAL_FROZEN)
    if activity.situation == calculations.SITUATION_DRAFT:
        raise AccessDeniedError(REPORT_BEFORE_VALIDATION)
    if any(value < 0 for value in form.day_shift + form.night_shift):
        raise InvalidDataError({"dias_realizado": NEGATIVE_DONE})

    notes = form.notes.strip()
    _require_deviation_note(
        session, project_id=project_id, activity=activity, done=form, notes=notes
    )
    changes: dict[str, Any] = {
        "updated_by_id": user.person_id,
        "updated_at": caller.now,
    }
    if notes:
        changes["supplier_notes"] = notes
    recording.update(session, user_id=user.id, record=activity, changes=changes, version=version)
    _change_done_days(
        session,
        user_id=user.id,
        activity=activity,
        day_shift=form.day_shift,
        night_shift=form.night_shift,
    )
    return activity


def approve_activity(
    session: Session,
    *,
    caller: Caller,
    activity_id: int,
    form: ApprovalForm,
    version: str | None,
) -> Activity:
    """Approve the done work of an activity: from here on it is frozen for the supplier."""
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_approve(user, project_id):
        raise AccessDeniedError(permissions.APPROVE_DENIED)
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    if activity.situation == calculations.SITUATION_DRAFT:
        raise InvalidDataError(APPROVE_AFTER_VALIDATION)
    if not _days_of(session, activity.id) or not _figures_of(session, activity).has_done:
        raise InvalidDataError(NOTHING_TO_APPROVE)

    changes: dict[str, Any] = {
        "approval": calculations.APPROVAL_APPROVED,
        "approved_by_id": user.person_id,
        "approved_at": caller.now,
        "updated_by_id": user.person_id,
        "updated_at": caller.now,
    }
    if form.comments:
        changes["timenow_comments"] = _append_comment(activity, form.comments, user, caller.now)
    recording.update(session, user_id=user.id, record=activity, changes=changes, version=version)
    return activity


def reopen_activity(
    session: Session,
    *,
    caller: Caller,
    activity_id: int,
    form: ApprovalForm,
    version: str | None,
) -> Activity:
    """Reopen an approved done work, with the reason; the supplier may report again."""
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_approve(user, project_id):
        raise AccessDeniedError(permissions.REOPEN_DENIED)
    if not form.reason:
        raise InvalidDataError({"motivo": REOPEN_REASON_REQUIRED})
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    if activity.approval != calculations.APPROVAL_APPROVED:
        raise InvalidDataError(REOPEN_NOT_APPROVED)

    comment = _append_comment(activity, f"Realizado reaberto: {form.reason}", user, caller.now)
    recording.update(
        session,
        user_id=user.id,
        record=activity,
        changes={
            "approval": calculations.APPROVAL_PENDING,
            "timenow_comments": comment,
            "updated_by_id": user.person_id,
            "updated_at": caller.now,
        },
        version=version,
    )
    return activity


def publish_activity(
    session: Session, *, caller: Caller, activity_id: int, version: str | None
) -> Activity:
    """Publish a validated activity: it reaches everyone and closes the edition of the item."""
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_publish(user, project_id):
        raise AccessDeniedError(permissions.PUBLISH_DENIED)
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    if activity.situation != calculations.SITUATION_VALIDATED:
        raise InvalidDataError(ONLY_VALIDATED_PUBLISHED)
    _publish(session, user=user, activity=activity, at=caller.now, version=version)
    return activity


def publish_week(session: Session, *, caller: Caller, week: str) -> int:
    """Publish every validated activity of the week the user sees, in one action.

    Publishing one by one is the kind of repetition that gets abandoned halfway,
    leaving a week half published — which reads as a data problem and is really a
    workflow problem. Returns how many were published.
    """
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_publish(user, project_id):
        raise AccessDeniedError(permissions.PUBLISH_DENIED)
    activities = repository.activities(
        session, project_id=project_id, week=week, company_id=rbac.company_scope(user)
    )
    published = 0
    for activity in activities:
        if activity.situation != calculations.SITUATION_VALIDATED:
            continue
        _publish(
            session, user=user, activity=activity, at=caller.now, version=str(activity.version)
        )
        published += 1
    return published


# ── The history of one activity ──────────────────────────────────────────


@dataclass(frozen=True)
class TrailEvent:
    """One line of the activity's history, already worded for the panel."""

    label: str
    actor: str
    when: str


def detail_events(session: Session, *, activity_id: int, limit: int = 20) -> list[TrailEvent]:
    """The most recent trail lines of the activity, newest first.

    The lines of the days stay out: a single report of seven days would spawn seven
    entries at once and bury the transitions the panel exists to show.
    """
    entries = repository.trail_entries(
        session, entity=Activity.__tablename__, record_id=activity_id, limit=limit
    )
    return [
        TrailEvent(
            label=_trail_label(entry),
            actor=audit.author_name(session, entry.user_id) or presentation.DASH,
            when=calendario.in_product_timezone(entry.occurred_at).strftime("%d/%m/%Y %H:%M"),
        )
        for entry in entries
    ]


# ── The governance of the schedule (ISSUE-053) ───────────────────────────
#
# The change request exists because published programming and approved done work
# stop being editable and sometimes have to change anyway; without the queue that
# becomes a phone call to whoever administers, who edits it directly and leaves no
# trace. Applying does not change the data by itself: it records the decision,
# reopens the item and writes the agreement in the comments — whoever wants the
# change makes it on the normal screen.


@dataclass
class _Group:
    """The accumulator of one company's week, while the panel reads the activities."""

    company: str
    project_id: int
    project_label: str
    week: str
    total: int = 0
    draft: int = 0
    validated: int = 0
    published: int = 0
    pending: int = 0
    inspector: str = ""
    updated_at: datetime | None = None
    figures: list[calculations.ActivityFigures] = field(default_factory=list)


def governance_panel(session: Session, *, caller: Caller) -> GovernancePanel:
    """The control list by company and week, the indicators and the windows.

    The numbers are the app's (``dados.governanca``): the line counts the activities of
    the company and the week, the pending approvals that already have done work, the last
    non-empty inspector and the weighted adherence; the indicators count the situations of
    every activity of the scope. The cut by company is the supplier's, as always (D7).
    """
    user = caller.user
    activities = repository.activities(
        session,
        project_id=caller.scope.project_id,
        week=None,
        company_id=rbac.company_scope(user),
    )
    days = repository.days_by_activity(session, [activity.id for activity in activities])
    names = _Names.load(session, activities)
    figures = {
        activity.id: _figures_for(days.get(activity.id, []), activity.planned_headline)
        for activity in activities
    }

    groups: dict[tuple[int, str], _Group] = {}
    for activity in activities:
        figure = figures[activity.id]
        group = groups.setdefault(
            (activity.company_id, activity.week),
            _Group(
                company=names.companies.get(activity.company_id, ""),
                project_id=activity.project_id,
                project_label=names.projects.get(activity.project_id, ""),
                week=activity.week,
            ),
        )
        group.total += 1
        if activity.situation == calculations.SITUATION_DRAFT:
            group.draft += 1
        elif activity.situation == calculations.SITUATION_VALIDATED:
            group.validated += 1
        elif activity.situation == calculations.SITUATION_PUBLISHED:
            group.published += 1
        if activity.approval == calculations.APPROVAL_PENDING and figure.has_done:
            group.pending += 1
        inspector = names.people.get(activity.inspector_id or 0, "")
        if inspector:
            group.inspector = inspector
        group.figures.append(figure)
        updated = activity.updated_at
        if group.updated_at is None or updated > group.updated_at:
            group.updated_at = updated

    lines = [
        GovernanceLine(
            company_id=company_id,
            company=group.company,
            project_id=group.project_id,
            project_label=group.project_label,
            week=group.week,
            period=weeks.period_label(group.week),
            total=group.total,
            draft=group.draft,
            validated=group.validated,
            published=group.published,
            pending=group.pending,
            inspector=group.inspector,
            adherence=calculations.schedule_adherence(group.figures),
            updated_at_text=_moment_text(group.updated_at),
        )
        for (company_id, _week), group in groups.items()
    ]
    lines.sort(key=lambda line: (weeks.sort_key(line.week), line.company), reverse=True)

    reference_week = default_week(session, caller=caller)
    windows = _window_views(session, caller=caller, week=reference_week)
    project_id = caller.scope.project_id
    return GovernancePanel(
        lines=lines,
        situations=_situation_counts(activities, figures),
        active_companies=len({activity.company_id for activity in activities}),
        open_windows=sum(1 for window in windows if window.is_open),
        windows=windows,
        reference_week=reference_week,
        reference_period=weeks.period_label(reference_week),
        is_portfolio=caller.scope.is_portfolio,
        can_decide=project_id is not None and permissions.can_decide_requests(user, project_id),
        can_view_trail=permissions.can_view_trail(user, project_id),
    )


def _situation_counts(
    activities: list[Activity], figures: dict[int, calculations.ActivityFigures]
) -> SituationCounts:
    """How many activities of the scope are in each state, with the app's reading of pending."""
    return SituationCounts(
        total=len(activities),
        draft=sum(1 for a in activities if a.situation == calculations.SITUATION_DRAFT),
        validated=sum(1 for a in activities if a.situation == calculations.SITUATION_VALIDATED),
        published=sum(1 for a in activities if a.situation == calculations.SITUATION_PUBLISHED),
        approved=sum(1 for a in activities if a.approval == calculations.APPROVAL_APPROVED),
        pending=sum(
            1
            for a in activities
            if a.approval == calculations.APPROVAL_PENDING and figures[a.id].has_done
        ),
        no_done=sum(1 for a in activities if not figures[a.id].has_done),
    )


def _window_views(session: Session, *, caller: Caller, week: str) -> list[WindowView]:
    """The windows of the scope, as the panel reads them: open now in the reference week, or not."""
    rows = repository.windows(
        session,
        project_id=caller.scope.project_id,
        company_id=rbac.company_scope(caller.user),
    )
    companies = registers.company_names(session, {row.company_id for row in rows})
    projects = registers.project_labels(session, {row.project_id for row in rows})
    now_local = calendario.in_product_timezone(caller.now)
    views = []
    for row in rows:
        window = repository.window_of(session, project_id=row.project_id, company_id=row.company_id)
        decision = window_rules.decide(week, window, now_local)
        first = window.days[0] if window and window.days else None
        views.append(
            WindowView(
                company_id=row.company_id,
                company=companies.get(row.company_id, ""),
                project_id=row.project_id,
                project_label=projects.get(row.project_id, ""),
                is_open=decision.is_open,
                reason=decision.reason,
                released_count=len(window.weeks) if window else 0,
                weekday_label=window_rules.WEEKDAY_NAMES.get(first.weekday, "") if first else "",
                opens=window_rules.hours_text(first.opens) if first else "",
                closes=window_rules.hours_text(first.closes) if first else "",
                extras=len(window.extras) if window else 0,
            )
        )
    return views


def request_queue(session: Session, *, caller: Caller) -> RequestQueue:
    """The change requests of the scope, split between what waits and what was decided."""
    user = caller.user
    rows = repository.change_requests(
        session, project_id=caller.scope.project_id, company_id=rbac.company_scope(user)
    )
    views = _request_views(session, rows)
    pending = [view for view in views if view.situation == REQUEST_PENDING]
    resolved = [view for view in views if view.situation != REQUEST_PENDING][
        :REQUEST_RESOLVED_LIMIT
    ]
    project_id = caller.scope.project_id
    return RequestQueue(
        pending=pending,
        resolved=resolved,
        total_pending=len(pending),
        can_decide=project_id is not None and permissions.can_decide_requests(user, project_id),
        is_portfolio=caller.scope.is_portfolio,
    )


def open_request(session: Session, *, caller: Caller, activity_id: int) -> ActivityView:
    """The activity of a change request, ensured to be out of the editing path."""
    caller.scope.require_project()
    view = get_activity(session, caller=caller, activity_id=activity_id)
    if not _closed_for_editing(view.situation, view.approval):
        raise InvalidDataError(REQUEST_EDITABLE)
    return view


def request_change(
    session: Session, *, caller: Caller, activity_id: int, reason: str
) -> ChangeRequest:
    """Put a change request in the queue: any profile that sees the item may open one.

    The reason is required, as the app demands it; the item has to be closed for
    editing (published or with the done approved), which is where the app offers it.
    """
    text = (reason or "").strip()
    if len(text) < REQUEST_MIN_REASON:
        raise InvalidDataError({"motivo": REQUEST_REASON_REQUIRED})

    caller.scope.require_project()
    activity = _activity_of(session, caller=caller, activity_id=activity_id)
    if not _closed_for_editing(activity.situation, activity.approval):
        raise InvalidDataError(REQUEST_EDITABLE)

    request = ChangeRequest(
        activity_id=activity.id,
        requested_by_id=caller.user.person_id,
        decided_by_id=None,
        reason=text,
        situation=REQUEST_PENDING,
        requested_at=caller.now,
        decided_at=None,
        answer=None,
    )
    session.add(request)
    session.flush()
    audit.append(
        session,
        audit.TrailLine(
            user_id=caller.user.id,
            entity=ChangeRequest.__tablename__,
            record_id=request.id,
            action=audit.CREATED,
            before=None,
            after=audit.snapshot(request),
            project_id=activity.project_id,
            occurred_at=caller.now,
        ),
    )
    return request


def decide_request(
    session: Session,
    *,
    caller: Caller,
    request_id: int,
    form: DecisionForm,
) -> ChangeRequestView:
    """Apply or refuse a change request; applying reopens the activity.

    Only the planner (or the Admin) decides. A refusal demands an answer, as the app
    demands it. Applying has one concrete effect beyond the record: an approved done
    work goes back to pending, so the item is once again free to change; the decision
    becomes a comment on the activity, and both rows leave the trail with before and
    after.
    """
    user = caller.user
    project_id = caller.scope.require_project()
    if not permissions.can_decide_requests(user, project_id):
        raise AccessDeniedError(permissions.DECIDE_DENIED)
    request = _request_of(session, caller=caller, request_id=request_id)
    if request.situation != REQUEST_PENDING:
        raise InvalidDataError(REQUEST_ALREADY_DECIDED)
    if not form.apply and len(form.answer) < REQUEST_MIN_ANSWER:
        raise InvalidDataError({"resposta": REQUEST_ANSWER_REQUIRED})

    before = audit.snapshot(request)
    versioning.require(session, request, form.version)
    request.situation = REQUEST_APPLIED if form.apply else REQUEST_REJECTED
    request.decided_by_id = user.person_id
    request.decided_at = caller.now
    request.answer = form.answer or None
    versioning.advance(request)
    session.flush()
    activity = session.get(Activity, request.activity_id)
    if activity is not None:
        audit.append(
            session,
            audit.TrailLine(
                user_id=user.id,
                entity=ChangeRequest.__tablename__,
                record_id=request.id,
                action=audit.UPDATED,
                before=before,
                after=audit.snapshot(request),
                project_id=activity.project_id,
                occurred_at=caller.now,
            ),
        )
        _answer_activity(session, user=user, request=request, activity=activity, at=caller.now)
    return _request_views(session, [request])[0]


def governance_trail(
    session: Session, *, caller: Caller, limit: int = TRAIL_LIMIT
) -> list[GovernanceTrailEvent]:
    """The audit trail of the schedule, newest first, worded for the screen.

    It is the platform's single trail (``core.audit``) filtered to the module's
    entities: the activity, the change request, the window and the configuration.
    The day lines stay out, as in the history of one activity.
    """
    if not permissions.can_view_trail(caller.user, caller.scope.project_id):
        raise AccessDeniedError(permissions.TRAIL_DENIED)
    entries = repository.trail_of_module(
        session,
        project_id=caller.scope.project_id,
        entities=TRAIL_ENTITIES,
        limit=limit,
    )
    companies = _trail_companies(session, entries)
    return [
        GovernanceTrailEvent(
            label=_governance_label(entry),
            summary=_governance_summary(entry, companies),
            actor=audit.author_name(session, entry.user_id) or presentation.DASH,
            when=calendario.in_product_timezone(entry.occurred_at).strftime("%d/%m/%Y %H:%M"),
        )
        for entry in entries
    ]


def _answer_activity(
    session: Session,
    *,
    user: User,
    request: ChangeRequest,
    activity: Activity,
    at: datetime,
) -> None:
    """Write the decision on the activity: the comment, the reopened approval and the trail."""
    applied = request.situation == REQUEST_APPLIED
    verdict = "liberado para alteração" if applied else "recusado"
    text = f"Pedido de alteração {verdict}: {request.reason}"
    if request.answer:
        text += f" — {request.answer}"
    changes: dict[str, Any] = {
        "timenow_comments": _append_comment(activity, text, user, at),
        "updated_by_id": user.person_id,
        "updated_at": at,
    }
    if applied and activity.approval == calculations.APPROVAL_APPROVED:
        changes["approval"] = calculations.APPROVAL_PENDING
    recording.update(
        session,
        user_id=user.id,
        record=activity,
        changes=changes,
        version=str(activity.version),
    )


# ── Internals ────────────────────────────────────────────────────────────


def _text(params: Mapping[str, str | None], name: str) -> str:
    return (params.get(name) or "").strip()


def _company_of(form: ActivityForm) -> int:
    """The company of a form that already passed the required fields."""
    if form.company_id is None:
        raise InvalidDataError({"empresa": "Informe a empresa."})
    return form.company_id


def _decision(
    session: Session, *, project_id: int, company_id: int, week: str, now: datetime
) -> window_rules.WindowDecision:
    window = repository.window_of(session, project_id=project_id, company_id=company_id)
    return window_rules.decide(week, window, calendario.in_product_timezone(now))


def _require_window_open(session: Session, *, caller: Caller, company_id: int, week: str) -> None:
    """The window binds the supplier: refuse with the reason when it is closed."""
    if not permissions.is_supplier(caller.user):
        return
    decision = _decision(
        session,
        project_id=caller.scope.require_project(),
        company_id=company_id,
        week=week,
        now=caller.now,
    )
    if not decision.is_open:
        raise AccessDeniedError(decision.reason)


def _with_supplier_company(
    user: User, form: ActivityForm, *, activity: Activity | None = None
) -> ActivityForm:
    """A supplier writes for its own company: another one is 403, none given is its own."""
    own = rbac.company_scope(user)
    if own is None:
        kept = activity.company_id if activity is not None else None
        return replace(form, company_id=form.company_id or kept)
    if form.company_id is not None:
        rbac.require_company(user, form.company_id)
    return replace(form, company_id=own)


def _raise_errors(
    session: Session, *, user: User, project_id: int, form: ActivityForm, excluding: int | None
) -> None:
    """Run every pass of validation and raise one 422 with a message per field."""
    errors = validation.pure_errors(form)
    if form.week and not weeks.is_valid(form.week):
        errors["semana"] = INVALID_WEEK_MESSAGE
    errors = {**_register_errors(session, user=user, project_id=project_id, form=form), **errors}
    taken = bool(form.week and form.unique_id) and repository.unique_id_taken(
        session,
        project_id=project_id,
        week=form.week,
        unique_id=form.unique_id,
        excluding=excluding,
    )
    if taken and "id_exclusiva" not in errors:
        errors["id_exclusiva"] = f"A ID “{form.unique_id}” já existe na semana {form.week}."
    if errors:
        raise InvalidDataError(errors)


def _register_errors(
    session: Session, *, user: User, project_id: int, form: ActivityForm
) -> dict[str, str]:
    """Every register the person chose has to exist where the form offers it."""
    options = form_options(session, user=user, project_id=project_id)
    checks = (
        (
            "local",
            form.location_id,
            options.locations,
            LOCATION_MISSING,
        ),
        (
            "empresa",
            form.company_id,
            options.companies,
            COMPANY_MISSING,
        ),
        (
            "unidade",
            form.unit_id,
            options.units,
            UNIT_MISSING,
        ),
        (
            "encarregado",
            form.foreman_id,
            options.foremen,
            FOREMAN_MISSING,
        ),
        (
            "responsavel",
            form.inspector_id,
            options.inspectors,
            INSPECTOR_MISSING,
        ),
    )
    errors: dict[str, str] = {}
    for name, chosen, offered, message in checks:
        if chosen is not None and all(option.id != chosen for option in offered):
            errors[name] = message
    return errors


def _activity_of(session: Session, *, caller: Caller, activity_id: int) -> Activity:
    """The activity of the scope; another project's is not found, another company's is 403."""
    activity = repository.find_activity(session, activity_id)
    project_id = caller.scope.project_id
    if activity is None or (project_id is not None and activity.project_id != project_id):
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    rbac.require_company(caller.user, activity.company_id)
    return activity


def _days_of(session: Session, activity_id: int) -> list[ActivityDay]:
    return repository.days_by_activity(session, [activity_id]).get(activity_id, [])


def _change_planned_days(
    session: Session, *, user_id: int, activity: Activity, planned: tuple[float, ...]
) -> None:
    """Rewrite the planned of each day that changed, with a trail line for each."""
    values = calculations.seven_days(planned)
    for day in _days_of(session, activity.id):
        new_value = values[day.day - 1]
        if day.planned == new_value:
            continue
        before = audit.snapshot(day)
        day.planned = new_value
        session.flush()
        audit.append(
            session, _day_line(user_id, activity.project_id, day, audit.UPDATED, before=before)
        )


def _change_done_days(
    session: Session,
    *,
    user_id: int,
    activity: Activity,
    day_shift: tuple[float, ...],
    night_shift: tuple[float, ...],
) -> None:
    """Rewrite the done of each day that changed, with a trail line for each."""
    day_values = calculations.seven_days(day_shift)
    night_values = calculations.seven_days(night_shift)
    for day in _days_of(session, activity.id):
        new_day = day_values[day.day - 1]
        new_night = night_values[day.day - 1]
        if day.done_day_shift == new_day and day.done_night_shift == new_night:
            continue
        before = audit.snapshot(day)
        day.done_day_shift = new_day
        day.done_night_shift = new_night
        session.flush()
        audit.append(
            session, _day_line(user_id, activity.project_id, day, audit.UPDATED, before=before)
        )


def _figures_for(days: list[ActivityDay], headline: float) -> calculations.ActivityFigures:
    """The figures of an activity from its day rows and its weekly headline."""
    return calculations.figures_of(
        [day.planned for day in days],
        [day.done_day_shift for day in days],
        [day.done_night_shift for day in days],
        headline=headline,
    )


def _figures_of(session: Session, activity: Activity) -> calculations.ActivityFigures:
    """The figures of an activity as it is stored, both shifts."""
    return _figures_for(_days_of(session, activity.id), activity.planned_headline)


def _submitted_figures(
    session: Session, activity: Activity, done: DoneForm
) -> calculations.ActivityFigures:
    """The figures of an activity with the done work being submitted (not yet stored)."""
    days = _days_of(session, activity.id)
    return calculations.figures_of(
        [day.planned for day in days],
        done.day_shift,
        done.night_shift,
        headline=activity.planned_headline,
    )


def _require_deviation_note(
    session: Session, *, project_id: int, activity: Activity, done: DoneForm, notes: str
) -> None:
    """The app's rule: a deviation past the limit is only saved with a justification."""
    parameters = parameters_of(session, project_id)
    if not parameters.requires_deviation_note or notes:
        return
    figures = _submitted_figures(session, activity, done)
    if not figures.planned_total:
        return
    deviation = calculations.deviation_percent(figures.done_total, figures.planned_total)
    if deviation > parameters.deviation_limit:
        raise InvalidDataError(
            {
                "observacoes": DEVIATION_DEMANDS_NOTE.format(
                    deviation=deviation, limit=parameters.deviation_limit
                )
            }
        )


def _publish(
    session: Session, *, user: User, activity: Activity, at: datetime, version: int | str | None
) -> None:
    """The write of a publication, shared by the single action and the week's action."""
    recording.update(
        session,
        user_id=user.id,
        record=activity,
        changes={
            "situation": calculations.SITUATION_PUBLISHED,
            "published_at": at,
            "updated_by_id": user.person_id,
            "updated_at": at,
        },
        version=version,
    )


def _append_comment(activity: Activity, text: str, user: User, at: datetime) -> str:
    """The comment of the app: stamped, signed, appended to what was already there."""
    stamp = calendario.in_product_timezone(at).strftime("%d/%m %H:%M")
    line = f"[{stamp} · {user.name}] {text}"
    return f"{activity.timenow_comments or ''}\n{line}".strip()


def _trail_label(entry: AuditEntry) -> str:
    """What a trail line of an activity means, read from the transition it caused."""
    if entry.action == audit.CREATED:
        return "Atividade criada"
    if entry.action == audit.DELETED:
        return "Atividade excluída"
    before, after = entry.before or {}, entry.after or {}
    transitions = (
        ("situacao", _TRAIL_SITUATION_LABELS, "Programação validada"),
        ("aprovacao_realizado", _TRAIL_APPROVAL_LABELS, "Realizado reaberto"),
        ("responsavel_id", {}, "Fiscal definido"),
        ("observacoes_fornecedor", {}, "Realizado lançado"),
    )
    for field_name, labels, fallback in transitions:
        if before.get(field_name) != after.get(field_name):
            return labels.get(after.get(field_name), fallback)
    if before.get("comentarios_timenow") != after.get("comentarios_timenow"):
        return _comment_label(after.get("comentarios_timenow"))
    return "Atividade alterada"


def _comment_label(comment: str | None) -> str:
    """The meaning of an appended comment: the change request decision or a plain note."""
    new_line = (comment or "").rsplit("\n", 1)[-1]
    if "Pedido de alteração liberado" in new_line:
        return "Pedido de alteração aplicado"
    if "Pedido de alteração recusado" in new_line:
        return "Pedido de alteração recusado"
    return "Comentário registrado"


def _moment_text(moment: datetime | None) -> str:
    """An instant as the screens print it; empty for none."""
    if moment is None:
        return ""
    return calendario.in_product_timezone(moment).strftime("%d/%m/%Y %H:%M")


def _request_of(session: Session, *, caller: Caller, request_id: int) -> ChangeRequest:
    """The change request of the scope, with the company cut of the supplier (D7)."""
    request = repository.find_change_request(session, request_id)
    if request is None:
        raise InvalidDataError(REQUEST_NOT_FOUND_MESSAGE)
    activity = session.get(Activity, request.activity_id)
    project_id = caller.scope.project_id
    if activity is None or (project_id is not None and activity.project_id != project_id):
        raise InvalidDataError(REQUEST_NOT_FOUND_MESSAGE)
    rbac.require_company(caller.user, activity.company_id)
    return request


def _request_views(session: Session, requests: list[ChangeRequest]) -> list[ChangeRequestView]:
    """The requests with their activity and the names of who asked and decided."""
    if not requests:
        return []
    activities = {
        activity.id: activity
        for activity in repository.activities_by_ids(
            session, [request.activity_id for request in requests]
        )
    }
    companies = registers.company_names(
        session, {activity.company_id for activity in activities.values()}
    )
    projects = registers.project_labels(
        session, {activity.project_id for activity in activities.values()}
    )
    people = registers.person_names(
        session,
        {
            person_id
            for request in requests
            for person_id in (request.requested_by_id, request.decided_by_id)
            if person_id is not None
        },
    )
    views = []
    for request in requests:
        activity = activities.get(request.activity_id)
        if activity is None:
            continue
        views.append(
            ChangeRequestView(
                id=request.id,
                version=request.version,
                activity_id=activity.id,
                unique_id=activity.unique_id,
                description=activity.description,
                company_id=activity.company_id,
                company=companies.get(activity.company_id, ""),
                week=activity.week,
                project_id=activity.project_id,
                project_label=projects.get(activity.project_id, ""),
                reason=request.reason,
                situation=request.situation,
                requested_by=people.get(request.requested_by_id, ""),
                requested_at_text=_moment_text(request.requested_at),
                decided_by=people.get(request.decided_by_id or 0, ""),
                decided_at_text=_moment_text(request.decided_at),
                answer=request.answer or "",
            )
        )
    return views


def _trail_companies(session: Session, entries: list[AuditEntry]) -> dict[int, str]:
    """The company names a trail line may name, for the lines of a window."""
    ids = set()
    for entry in entries:
        for side in (entry.before, entry.after):
            if side and side.get("empresa_id") is not None:
                ids.add(int(side["empresa_id"]))
    return registers.company_names(session, ids)


def _governance_label(entry: AuditEntry) -> str:
    """What a line of the module's trail means, read from the entity and the transition."""
    action = entry.action
    if entry.entity == ChangeRequest.__tablename__:
        if action == audit.CREATED:
            return "Pedido de alteração aberto"
        situation = (entry.after or {}).get("situacao")
        return {
            REQUEST_APPLIED: "Pedido de alteração aplicado",
            REQUEST_REJECTED: "Pedido de alteração recusado",
        }.get(situation, "Pedido de alteração alterado")
    if entry.entity == Activity.__tablename__:
        return _trail_label(entry)
    if entry.entity == ScheduleWindow.__tablename__:
        return {
            audit.CREATED: "Janela de programação criada",
            audit.DELETED: "Janela de programação excluída",
        }.get(action, "Janela alterada")
    return {
        audit.CREATED: "Configuração da programação gravada",
    }.get(action, "Configuração da programação alterada")


def _governance_summary(entry: AuditEntry, companies: dict[int, str]) -> str:
    """The line under the label: the item, the week, the reason or the company of a window."""
    after, before = entry.after or {}, entry.before or {}
    if entry.entity == ChangeRequest.__tablename__:
        text = after.get("motivo") or before.get("motivo") or ""
        answer = after.get("resposta")
        return f"{text} — resposta: {answer}" if answer else text
    if entry.entity == Activity.__tablename__:
        unique_id = after.get("id_exclusiva") or before.get("id_exclusiva") or ""
        week = after.get("semana") or before.get("semana") or ""
        return " · ".join(part for part in (unique_id, week) if part)
    if entry.entity == ScheduleWindow.__tablename__:
        company_id = after.get("empresa_id") or before.get("empresa_id")
        return companies.get(int(company_id), "") if company_id is not None else ""
    return ""


def _offers(options: list[Option], chosen: int) -> bool:
    """Whether one of the offered registers has the chosen id."""
    return any(option.id == chosen for option in options)


def _day_line(
    user_id: int, project_id: int, day: ActivityDay, action: str, before: dict[str, Any] | None
) -> audit.TrailLine:
    """The trail line of a day, tagged with the project (the days have no version of their own)."""
    return audit.TrailLine(
        user_id=user_id,
        entity=day.__tablename__,
        record_id=day.id,
        action=action,
        before=before,
        after=None if action == audit.DELETED else audit.snapshot(day),
        project_id=project_id,
    )


def _write_window_rules(session: Session, row: ScheduleWindow, rules: window_rules.Window) -> None:
    """Write the children of a window row: its weekdays, released weeks and extras."""
    for day in rules.days:
        session.add(
            WindowWeekday(window_id=row.id, weekday=day.weekday, opens=day.opens, closes=day.closes)
        )
    for week in sorted(rules.weeks, key=weeks.sort_key):
        session.add(WindowWeek(window_id=row.id, week=week))
    for extra in rules.extras:
        session.add(
            WindowExtraRelease(
                window_id=row.id, week=extra.week, opens=extra.opens, closes=extra.closes
            )
        )


def _clear_window_rules(session: Session, row: ScheduleWindow) -> None:
    """Drop the children of a window row: saving the window replaces the whole rule set."""
    for model in (WindowWeekday, WindowWeek, WindowExtraRelease):
        session.execute(delete(model).where(model.window_id == row.id))


def _window_snapshot(session: Session, row: ScheduleWindow | None) -> dict[str, Any] | None:
    """A window row with its rules, keyed by column name: what the trail shows as before/after."""
    if row is None:
        return None
    window = repository.window_of_row(session, row)
    return {
        "id": row.id,
        "projeto_id": row.project_id,
        "empresa_id": row.company_id,
        "versao": row.version,
        "dias": [
            {
                "dia_semana": day.weekday,
                "abre": window_rules.hours_text(day.opens),
                "fecha": window_rules.hours_text(day.closes),
            }
            for day in window.days
        ],
        "semanas": sorted(window.weeks, key=weeks.sort_key),
        "extras": [
            {
                "semana": extra.week,
                "abre": extra.opens.isoformat(),
                "fecha": extra.closes.isoformat(),
            }
            for extra in window.extras
        ],
    }


@dataclass(frozen=True)
class _Names:
    """The names of the registers an activity points to, resolved once for the whole list."""

    companies: dict[int, str]
    locations: dict[int, str]
    units: dict[int, str]
    people: dict[int, str]
    projects: dict[int, str]

    @classmethod
    def load(cls, session: Session, activities: list[Activity]) -> _Names:
        """One query per register for the whole list, never one per row."""

        def ids(values: list[int | None]) -> set[int]:
            return {value for value in values if value is not None}

        people = [a.foreman_id for a in activities] + [a.inspector_id for a in activities]
        return cls(
            companies=registers.company_names(session, ids([a.company_id for a in activities])),
            locations=registers.location_names(session, ids([a.location_id for a in activities])),
            units=registers.unit_codes(session, ids([a.unit_id for a in activities])),
            people=registers.person_names(session, ids(people)),
            projects=registers.project_labels(session, ids([a.project_id for a in activities])),
        )


def _views(session: Session, *, caller: Caller, activities: list[Activity]) -> list[ActivityView]:
    """The activities with their registers named, their figures and what the user may do."""
    if not activities:
        return []
    days = repository.days_by_activity(session, [activity.id for activity in activities])
    names = _Names.load(session, activities)
    return [
        _view(activity, days.get(activity.id, []), names, caller=caller) for activity in activities
    ]


def _view(
    activity: Activity, days: list[ActivityDay], names: _Names, *, caller: Caller
) -> ActivityView:
    figures = calculations.figures_of(
        [day.planned for day in days],
        [day.done_day_shift for day in days],
        [day.done_night_shift for day in days],
        headline=activity.planned_headline,
    )
    # The Portfólio is read-only: nothing is editable or deletable from there (D8).
    editable = not caller.scope.is_portfolio
    user = caller.user
    project_id = activity.project_id
    return ActivityView(
        id=activity.id,
        version=activity.version,
        project_id=project_id,
        project_label=names.projects.get(project_id, ""),
        week=activity.week,
        unique_id=activity.unique_id,
        item=activity.item,
        description=activity.description,
        location_id=activity.location_id,
        location=names.locations.get(activity.location_id or 0, ""),
        company_id=activity.company_id,
        company=names.companies.get(activity.company_id, ""),
        foreman_id=activity.foreman_id,
        foreman=names.people.get(activity.foreman_id or 0, ""),
        inspector_id=activity.inspector_id,
        inspector=names.people.get(activity.inspector_id or 0, ""),
        unit_id=activity.unit_id,
        unit=names.units.get(activity.unit_id or 0, ""),
        planned_headline=activity.planned_headline,
        figures=figures,
        situation=activity.situation,
        approval=activity.approval,
        notes=activity.supplier_notes or "",
        comments=activity.timenow_comments or "",
        next_action=(
            permissions.next_action(
                user,
                project_id,
                situation=activity.situation,
                approval=activity.approval,
                has_done=figures.has_done,
            )
            if editable
            else permissions.ACTION_VIEW
        ),
        can_edit=editable and _may_edit(user, activity),
        can_delete=editable and permissions.can_delete(user),
        can_validate=editable and permissions.can_validate(user, project_id),
        can_report=editable and permissions.can_report(user, project_id),
        can_approve=editable and permissions.can_approve(user, project_id),
        can_publish=editable and permissions.can_publish(user, project_id),
        can_request_change=editable and _closed_for_editing(activity.situation, activity.approval),
    )


def _closed_for_editing(situation: str, approval: str) -> bool:
    """Whether the item is out of the editing path: published or with the done approved.

    It is exactly where the app offers the change request, and the same condition the
    facade demands before writing one.
    """
    return (
        situation == calculations.SITUATION_PUBLISHED or approval == calculations.APPROVAL_APPROVED
    )


def _may_edit(user: User, activity: Activity) -> bool:
    """Whether the roles let the user edit this activity (the window is checked on the write)."""
    if not permissions.can_edit(user, activity.project_id):
        return False
    published = activity.situation == calculations.SITUATION_PUBLISHED
    return not published or permissions.can_publish(user, activity.project_id)


def apply_filters(views: list[ActivityView], filters: Filters) -> list[ActivityView]:
    """The views the filters keep, in the order the filters ask for."""
    kept = [view for view in views if _matches(view, filters)]
    return _sorted(kept, filters)


def _matches(view: ActivityView, filters: Filters) -> bool:
    checks = (
        filters.location_id is None or view.location_id == filters.location_id,
        filters.company_id is None or view.company_id == filters.company_id,
        filters.foreman_id is None or view.foreman_id == filters.foreman_id,
        filters.inspector_id is None or view.inspector_id == filters.inspector_id,
        not filters.situation or view.situation == filters.situation,
        not filters.approval or view.approval == filters.approval,
        not filters.band or view.figures.band == filters.band,
        _found(view, filters.search),
    )
    return all(checks)


def _found(view: ActivityView, search: str) -> bool:
    if not search:
        return True
    needle = search.lower()
    return any(needle in str(getattr(view, field)).lower() for field in _SEARCH_FIELDS)


def _sort_key(view: ActivityView, key: str) -> float | str:
    """The value a column sorts by: numbers as numbers, texts without regard to case."""
    figures = view.figures
    values: dict[str, float | str] = {
        "item": view.item,
        "id": view.unique_id.lower(),
        "atividade": view.description.lower(),
        "local": view.location.lower(),
        "empresa": view.company.lower(),
        "encarregado": view.foreman.lower(),
        "fiscal": view.inspector.lower(),
        "situacao": view.situation,
        "previsto": figures.planned_total,
        "realizado": figures.done_total,
        "ppc": figures.ppc,
    }
    return values[key]


def _sorted(views: list[ActivityView], filters: Filters) -> list[ActivityView]:
    if not filters.sort:
        return sorted(views, key=lambda view: view.item)
    return sorted(
        views, key=lambda view: _sort_key(view, filters.sort), reverse=filters.direction == "desc"
    )
