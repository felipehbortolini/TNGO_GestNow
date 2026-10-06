"""Facade of the panel and of the follow-up of the Central de Ações (D12, ISSUE-020).

Both read the same list of actions as the screen Ações (``service.list_actions``), so a count of
the panel is the count of the list in the same scope. Nothing here writes the table ``acao``; the
follow-up writes only through the notification port (a ``notificacao`` row and its trail line per
responsible). Nothing reads the clock: the routes hand the reference date in.

* ``dashboard(session, *, user, scope, origin, reference_date) -> Dashboard``;
* ``plan_follow_up(session, *, user, request) -> FollowUpPlan``: who would receive what, for the filter in force;
* ``send_follow_up(session, *, user, request, channel=None) -> FollowUpResult``: one notification per responsible, simulated while the
  e-mail sending is off.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.orm import Session

from src.core import config, notification, rbac
from src.core.errors import InvalidDataError
from src.core.notification import NotificationChannel, NotificationRequest
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import calculations, follow_up, origins, service
from src.modulos.central_acoes.calculations import (
    ActionDates,
    FollowUpAction,
    FollowUpGroup,
    MonthCount,
    ResponsibleTally,
    StatusCounts,
    StatusFilter,
)
from src.modulos.central_acoes.validation import ActionFilters
from src.modulos.configuracoes import service as configuracoes

NO_OPEN_ACTIONS_MESSAGE = "Nenhuma ação em aberto no filtro atual."
NO_ADDRESS_MESSAGE = "Nenhum responsável com e-mail cadastrado: {names}."
REPORT_ORIGIN_LABEL = "Todas as origens"


@dataclass(frozen=True)
class OriginLine:
    """One origin of the panel: how many actions it has in each status."""

    origin: str
    tally: ResponsibleTally


@dataclass(frozen=True)
class ProjectLine:
    """One project of the panel (Portfólio only)."""

    project_id: int
    code: str
    label: str
    tally: ResponsibleTally


@dataclass(frozen=True)
class ResponsibleLine:
    """One responsible of the panel: the numbers of their actions."""

    responsible_id: int
    name: str
    tally: ResponsibleTally


@dataclass(frozen=True)
class Dashboard:
    """What the screen Dashboards e KPIs shows for an origin filter and a scope."""

    origin: str
    counts: StatusCounts
    due_by_reference: int
    universe: int
    completed_on_planned: int
    origins: tuple[OriginLine, ...]
    projects: tuple[ProjectLine, ...]
    responsibles: tuple[ResponsibleLine, ...]
    top_responsibles: tuple[ResponsibleLine, ...]
    months: tuple[MonthCount, ...]

    @property
    def overdue_share(self) -> int | None:
        """Atrasadas as a whole percentage of the open ones."""
        return calculations.overdue_share_of_open(self.counts)

    @property
    def on_planned_share(self) -> int | None:
        """Concluídas no prazo original as a whole percentage of the completed ones."""
        return calculations.whole_percent(self.completed_on_planned, self.counts.completed)


def dashboard(
    session: Session, *, user: User, scope: Scope, origin: str, reference_date: date
) -> Dashboard:
    """The panel: the KPIs and the groupings by origin, project, responsible and month."""
    listing = service.list_actions(
        session,
        user=user,
        scope=scope,
        filters=ActionFilters(origin=origin, status=StatusFilter.ALL),
        reference_date=reference_date,
    )
    records = [line.record for line in listing.rows]
    dates = [_dates_of(record) for record in records]
    by_person = _by_responsible(listing.rows)
    return Dashboard(
        origin=origin,
        counts=listing.counts,
        due_by_reference=listing.due_by_reference,
        universe=listing.universe,
        completed_on_planned=calculations.completed_on_planned_count(dates),
        origins=_origin_lines(records),
        projects=_project_lines(session, records) if scope.is_portfolio else (),
        responsibles=tuple(sorted(by_person.values(), key=_by_delay)),
        top_responsibles=_top(by_person),
        months=tuple(calculations.monthly_planned_vs_completed(dates)),
    )


def _dates_of(record: service.ActionRecord) -> ActionDates:
    return ActionDates(
        kind=record.kind,
        planned_date=record.planned_date,
        replanned_date=record.replanned_date,
        completed_on=record.completed_on,
    )


def _tally(records: Sequence[service.ActionRecord]) -> ResponsibleTally:
    return calculations.responsible_tally((item.status, item.days_overdue) for item in records)


def _origin_lines(records: Sequence[service.ActionRecord]) -> tuple[OriginLine, ...]:
    return tuple(
        OriginLine(origin=name, tally=_tally(listed))
        for name in origins.ORIGINS
        if (listed := [item for item in records if item.origin == name])
    )


def _project_lines(
    session: Session, records: Sequence[service.ActionRecord]
) -> tuple[ProjectLine, ...]:
    return tuple(
        ProjectLine(
            project_id=project.id,
            code=project.code,
            label=f"{project.code} · {project.name}",
            tally=_tally([item for item in records if item.project_id == project.id]),
        )
        for project in configuracoes.list_projects(session)
    )


def _by_responsible(rows: Sequence[service.ActionRow]) -> dict[int, ResponsibleLine]:
    grouped: dict[int, list[service.ActionRow]] = {}
    for line in rows:
        grouped.setdefault(line.record.responsible_id, []).append(line)
    return {
        person: ResponsibleLine(
            responsible_id=person,
            name=listed[0].responsible_name,
            tally=_tally([line.record for line in listed]),
        )
        for person, listed in sorted(grouped.items())
    }


def _by_delay(line: ResponsibleLine) -> tuple[int, str, int]:
    """The table of the panel: the most overdue first, then by name."""
    return (-line.tally.overdue, line.name.casefold(), line.responsible_id)


def _top(by_person: dict[int, ResponsibleLine]) -> tuple[ResponsibleLine, ...]:
    ranked = calculations.top_open_responsibles(
        {person: line.tally for person, line in by_person.items()}
    )
    return tuple(by_person[person] for person in ranked)


# ── Follow-up ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FollowUpEntry:
    """One responsible of the follow-up: who, to which address and the message they get."""

    group: FollowUpGroup
    name: str
    email: str
    project_id: int
    subject: str
    body: str


@dataclass(frozen=True)
class FollowUpPlan:
    """What a follow-up for the filter in force would do, before anyone confirms it."""

    entries: tuple[FollowUpEntry, ...]
    simulated: bool

    @property
    def action_count(self) -> int:
        """How many open actions the follow-up covers."""
        return sum(len(entry.group.actions) for entry in self.entries)

    @property
    def addressed(self) -> tuple[FollowUpEntry, ...]:
        """The responsibles that have an e-mail in the register: the ones that receive."""
        return tuple(entry for entry in self.entries if entry.email)

    @property
    def without_address(self) -> tuple[FollowUpEntry, ...]:
        """The responsibles with no e-mail in the register: shown, never sent."""
        return tuple(entry for entry in self.entries if not entry.email)


@dataclass(frozen=True)
class FollowUpResult:
    """What the send did: the outcomes of the port, the people left out and the notice."""

    outcomes: tuple[notification.NotificationOutcome, ...]
    without_address: tuple[str, ...]
    notice: str
    toast_kind: str


@dataclass(frozen=True)
class FollowUpRequest:
    """What the follow-up reads: the scope, the filters of the list and the reference date."""

    scope: Scope
    filters: ActionFilters
    reference_date: date


def is_simulated() -> bool:
    """Whether the e-mail sending is off, so a follow-up is only recorded as ``simulado``."""
    return config.email_sending() != config.EMAIL_SENDING_ON


def plan_follow_up(session: Session, *, user: User, request: FollowUpRequest) -> FollowUpPlan:
    """The open actions of the filter (origin, responsible and search) grouped by responsible."""
    rbac.require_module(user, service.MODULE)
    rbac.require(user, Permission.MANAGE)
    listing = service.list_actions(
        session,
        user=user,
        scope=request.scope,
        filters=replace(request.filters, status=StatusFilter.ALL, page=1),
        reference_date=request.reference_date,
    )
    items = [_follow_up_action(line) for line in listing.rows]
    people = configuracoes.find_people(session, {item.responsible_id for item in items})
    names = {person: summary.name for person, summary in people.items()}
    groups = calculations.group_for_follow_up(items, names)
    return FollowUpPlan(
        entries=tuple(
            _entry(group, people.get(group.responsible_id), request.reference_date)
            for group in groups
        ),
        simulated=is_simulated(),
    )


def send_follow_up(
    session: Session,
    *,
    user: User,
    request: FollowUpRequest,
    channel: NotificationChannel | None = None,
) -> FollowUpResult:
    """One notification per responsible with an address; each one leaves a row and a trail line.

    Refuses with 422 when there is nothing open in the filter or nobody has an address. A person
    without address is named in the notice, never silently skipped.
    """
    plan = plan_follow_up(session, user=user, request=request)
    if not plan.entries:
        raise InvalidDataError(NO_OPEN_ACTIONS_MESSAGE)
    if not plan.addressed:
        names = ", ".join(entry.name for entry in plan.without_address)
        raise InvalidDataError(NO_ADDRESS_MESSAGE.format(names=names))
    outcomes = tuple(
        notification.send(
            session,
            user_id=user.id,
            request=NotificationRequest(
                kind=notification.FOLLOW_UP,
                project_id=entry.project_id,
                recipients=[entry.email],
                subject=entry.subject,
                body=entry.body,
            ),
            channel=channel,
        )
        for entry in plan.addressed
    )
    missing = tuple(entry.name for entry in plan.without_address)
    text, kind = follow_up.result_notice([item.situation for item in outcomes], missing)
    return FollowUpResult(outcomes=outcomes, without_address=missing, notice=text, toast_kind=kind)


def _follow_up_action(line: service.ActionRow) -> FollowUpAction:
    record = line.record
    return FollowUpAction(
        action_id=record.id,
        project_id=record.project_id,
        responsible_id=record.responsible_id,
        label=record.origin_ref or record.origin,
        subject=record.subject,
        due_date=record.due_date,
        status=record.status,
        days_overdue=record.days_overdue,
    )


def _entry(
    group: FollowUpGroup, person: configuracoes.PersonSummary | None, reference_date: date
) -> FollowUpEntry:
    name = person.name if person is not None else service.UNKNOWN_PERSON_NAME
    return FollowUpEntry(
        group=group,
        name=name,
        email=person.email if person is not None else "",
        project_id=group.actions[0].project_id,
        subject=follow_up.message_subject(group),
        body=follow_up.message_body(group, name=name, reference_date=reference_date),
    )
