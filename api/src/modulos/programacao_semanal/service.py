"""Business facade of the Weekly Scheduling: the week, the window and the activity (D10).

This slice (ISSUE-051) is the matrix of the week and the programming by the supplier:
who sees which activities, who writes, and when. The rules are the app's, adapted as
D10 says: the app's "ambiente" is the project of the scope (D8, with the Portfólio
read-only), companies, people and locations come from Configurações
(``configuracoes.registers``), the roles are the per-project roles of D7 and every
write leaves the trail with before and after (D5b).

* **A supplier sees and writes only its own company**, always, with the cut made
  here and never on the screen: a list is cut by ``rbac.company_scope``, and
  reaching for another company's activity is 403 (``rbac.require_company``).
* **The window binds the supplier**: outside it the write is refused with the message
  of the app. The Timenow team writes as support, without the window.
* **No project, no write**: in the Portfólio the matrix is read-only and the write asks
  for a project (``Scope.require_project``).

Nothing here reads the clock: the caller passes the instant in the ``Caller``
(``core.calendario.now``). Every write goes through ``core.recording`` with the
version the screen opened.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.core import audit, calendario, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import ScheduleRole, User
from src.core.scope import Scope
from src.modulos.configuracoes import registers
from src.modulos.configuracoes.registers import Option
from src.modulos.programacao_semanal import (
    calculations,
    flow,
    permissions,
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
from src.modulos.programacao_semanal.validation import ActivityForm
from src.modulos.programacao_semanal.views import ActivityView

NOT_FOUND_MESSAGE = "Atividade não encontrada."
INVALID_WEEK_MESSAGE = "Informe uma semana válida, no formato S.30/2026."
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

# The defaults of the app for a project that has no configuration row yet (D10); the
# configuration screen (ISSUE-054) writes the row.
DEFAULT_ADHERENCE_TARGET = 60.0
DEFAULT_PPC_TARGET = 75.0
DEFAULT_DEVIATION_LIMIT = 15.0

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
    session.flush()
    return row


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


def load_activity(session: Session, *, caller: Caller, activity_id: int) -> Activity:
    """The activity of the scope for a step of the flow: not found is 422, another company's is 403."""
    return _activity_of(session, caller=caller, activity_id=activity_id)


def change_done_days(
    session: Session,
    *,
    user_id: int,
    activity: Activity,
    day_shift: tuple[float, ...],
    night_shift: tuple[float, ...],
) -> None:
    """Rewrite the done of each day that changed (both shifts), with a trail line for each."""
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


def activity_figures(session: Session, activity: Activity) -> calculations.ActivityFigures:
    """The figures of the activity as stored now: what the deviation and the approval read."""
    days = _days_of(session, activity.id)
    return calculations.figures_of(
        [day.planned for day in days],
        [day.done_day_shift for day in days],
        [day.done_night_shift for day in days],
        headline=activity.planned_headline,
    )


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
    return ActivityView(
        id=activity.id,
        version=activity.version,
        project_id=activity.project_id,
        project_label=names.projects.get(activity.project_id, ""),
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
        can_edit=editable and _may_edit(caller.user, activity),
        can_delete=editable and permissions.can_delete(caller.user),
        actions=_actions(activity, figures, caller=caller),
    )


def _actions(
    activity: Activity, figures: calculations.ActivityFigures, *, caller: Caller
) -> flow.Actions:
    """The button of the next step and the menu of the row, for the user who looks (HU-77)."""
    if caller.scope.is_portfolio:
        return flow.NO_ACTIONS
    user, project_id = caller.user, activity.project_id
    rights = flow.Rights(
        validate=permissions.can_validate(user, project_id),
        report=permissions.can_report(user, project_id),
        approve=permissions.can_approve(user, project_id, activity.inspector_id),
        publish=permissions.can_publish(user, project_id),
        edit=_may_edit(user, activity),
        delete=permissions.can_delete(user),
    )
    state = flow.State(
        situation=activity.situation, approval=activity.approval, has_done=figures.has_done
    )
    return flow.actions_of(rights, state)


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
