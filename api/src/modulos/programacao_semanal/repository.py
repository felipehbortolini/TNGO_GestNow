"""Reads of the tables of the Weekly Scheduling: the queries the facade composes (D10).

Only this module's own tables, only reads. The writes go through ``core.recording``
in the facade, and the registers of other modules (companies, people, locations,
units) come from the facade of Configurações, never from here.
"""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.models import (
    Activity,
    ActivityDay,
    ScheduleSettings,
    ScheduleWindow,
    WindowExtraRelease,
    WindowWeek,
    WindowWeekday,
)


def settings_of(session: Session, project_id: int) -> ScheduleSettings | None:
    """The configuration row of the project, or ``None`` while it still has the defaults."""
    statement = select(ScheduleSettings).where(ScheduleSettings.project_id == project_id)
    return session.scalars(statement).one_or_none()


def all_settings(session: Session) -> list[ScheduleSettings]:
    """The configuration rows of every project, by project: what the Portfólio reads."""
    return list(session.scalars(select(ScheduleSettings).order_by(ScheduleSettings.project_id)))


def windows_by_company(session: Session, *, project_id: int) -> dict[int, ScheduleWindow]:
    """The window rows of the project by company."""
    statement = select(ScheduleWindow).where(ScheduleWindow.project_id == project_id)
    return {row.company_id: row for row in session.scalars(statement)}


def window_counts(session: Session) -> dict[int, int]:
    """How many companies have a window, by project."""
    statement = select(ScheduleWindow.project_id, func.count(ScheduleWindow.id)).group_by(
        ScheduleWindow.project_id
    )
    return {int(project_id): int(total) for project_id, total in session.execute(statement)}


def find_activity(session: Session, activity_id: int) -> Activity | None:
    """The activity with the id, or ``None``."""
    return session.get(Activity, activity_id)


def activities(
    session: Session, *, project_id: int | None, week: str | None, company_id: int | None
) -> list[Activity]:
    """The activities of a project (every project when ``None``) and week, cut to one company.

    ``week=None`` means every week; the order is the item of the week, then the id.
    """
    statement = select(Activity).order_by(Activity.week, Activity.item, Activity.id)
    if project_id is not None:
        statement = statement.where(Activity.project_id == project_id)
    if week is not None:
        statement = statement.where(Activity.week == week)
    if company_id is not None:
        statement = statement.where(Activity.company_id == company_id)
    return list(session.scalars(statement))


def days_by_activity(
    session: Session, activity_ids: Collection[int]
) -> dict[int, list[ActivityDay]]:
    """The days of each activity, Monday first."""
    if not activity_ids:
        return {}
    statement = (
        select(ActivityDay)
        .where(ActivityDay.activity_id.in_(activity_ids))
        .order_by(ActivityDay.activity_id, ActivityDay.day)
    )
    grouped: dict[int, list[ActivityDay]] = {}
    for day in session.scalars(statement):
        grouped.setdefault(day.activity_id, []).append(day)
    return grouped


def next_item(session: Session, *, project_id: int, week: str) -> int:
    """The item the next activity of the week takes: the highest item so far plus one."""
    statement = select(func.coalesce(func.max(Activity.item), 0)).where(
        Activity.project_id == project_id, Activity.week == week
    )
    return int(session.scalar(statement) or 0) + 1


def unique_id_taken(
    session: Session, *, project_id: int, week: str, unique_id: str, excluding: int | None = None
) -> bool:
    """Whether the ID is already used by another activity of the week of the project."""
    statement = select(Activity.id).where(
        Activity.project_id == project_id,
        Activity.week == week,
        Activity.unique_id == unique_id,
    )
    if excluding is not None:
        statement = statement.where(Activity.id != excluding)
    return session.scalars(statement.limit(1)).first() is not None


def weeks_with_activity(
    session: Session, *, project_id: int | None, company_id: int | None
) -> set[str]:
    """Every week that has at least one activity (in the project and company when given)."""
    statement = select(Activity.week).distinct()
    if project_id is not None:
        statement = statement.where(Activity.project_id == project_id)
    if company_id is not None:
        statement = statement.where(Activity.company_id == company_id)
    return set(session.scalars(statement))


def released_weeks(session: Session, *, project_id: int | None, company_id: int | None) -> set[str]:
    """Every week released in some window (of the project and company when given)."""
    statement = (
        select(WindowWeek.week)
        .distinct()
        .join(ScheduleWindow, ScheduleWindow.id == WindowWeek.window_id)
    )
    if project_id is not None:
        statement = statement.where(ScheduleWindow.project_id == project_id)
    if company_id is not None:
        statement = statement.where(ScheduleWindow.company_id == company_id)
    return set(session.scalars(statement))


def window_of(session: Session, *, project_id: int, company_id: int) -> window_rules.Window | None:
    """The window of the company in the project, or ``None`` when it has none."""
    statement = select(ScheduleWindow).where(
        ScheduleWindow.project_id == project_id, ScheduleWindow.company_id == company_id
    )
    row = session.scalars(statement).one_or_none()
    if row is None:
        return None
    weekdays = session.scalars(
        select(WindowWeekday)
        .where(WindowWeekday.window_id == row.id)
        .order_by(WindowWeekday.weekday, WindowWeekday.opens, WindowWeekday.id)
    )
    weeks = session.scalars(select(WindowWeek.week).where(WindowWeek.window_id == row.id))
    extras = session.scalars(
        select(WindowExtraRelease)
        .where(WindowExtraRelease.window_id == row.id)
        .order_by(WindowExtraRelease.opens, WindowExtraRelease.id)
    )
    return window_rules.Window(
        company_id=row.company_id,
        days=tuple(
            window_rules.WindowDay(weekday=day.weekday, opens=day.opens, closes=day.closes)
            for day in weekdays
        ),
        weeks=frozenset(weeks),
        extras=tuple(
            window_rules.ExtraRelease(week=extra.week, opens=extra.opens, closes=extra.closes)
            for extra in extras
        ),
    )
