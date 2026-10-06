"""Business facade for the Planning module.

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
from datetime import date
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from src.core import audit, rbac, recording
from src.core.errors import InvalidDataError
from src.core.import_values import normalize_text
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, validation
from src.modulos.planejamento.models import Lookahead, LookaheadConstraint, LookaheadWeek

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
