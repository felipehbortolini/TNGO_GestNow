"""Pure calculations for the Central actions module (D6, ISSUE-019).

Every rule is one function with its business name, and the reference date is always an
argument: nothing here reads the clock. The status of an action is never stored; it is
calculated on every query from the dates of the action and the reference date.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from types import MappingProxyType

ACTION = "Ação"
INFORMATION = "Informação"

_INFORMATION_PREFIX = "inform"
_PERCENT = Decimal(100)


class ActionStatus(StrEnum):
    """The status of an action; the value is the key the screen filters and styles by."""

    INFORMATION = "info"
    COMPLETED = "concluida"
    OVERDUE = "atrasada"
    IN_PROGRESS = "andamento"


STATUS_LABELS: Mapping[ActionStatus, str] = MappingProxyType(
    {
        ActionStatus.INFORMATION: "Informação",
        ActionStatus.COMPLETED: "Concluída",
        ActionStatus.OVERDUE: "Atrasada",
        ActionStatus.IN_PROGRESS: "Em andamento",
    }
)


class StatusFilter(StrEnum):
    """What the status filter and the KPIs ask for; ``OPEN`` includes the overdue ones."""

    OPEN = "aberto"
    ON_TIME = "andamento"
    OVERDUE = "atrasada"
    COMPLETED = "concluida"
    ALL = "todos"


STATUS_FILTER_LABELS: Mapping[StatusFilter, str] = MappingProxyType(
    {
        StatusFilter.OPEN: "Em andamento (inclui atrasadas)",
        StatusFilter.ON_TIME: "Em dia",
        StatusFilter.OVERDUE: "Somente atrasadas",
        StatusFilter.COMPLETED: "Concluídas",
        StatusFilter.ALL: "Todos",
    }
)


@dataclass(frozen=True)
class ActionDates:
    """What the status of an action depends on: its kind and its three dates."""

    kind: str
    planned_date: date | None
    replanned_date: date | None
    completed_on: date | None


@dataclass(frozen=True)
class StatusCounts:
    """The four numbers of the KPIs, counted over the same actions."""

    on_time: int
    overdue: int
    completed: int

    @property
    def open(self) -> int:
        """Em andamento in the broad sense: the ones on time plus the overdue ones."""
        return self.on_time + self.overdue

    @property
    def total(self) -> int:
        """Every action counted, whatever its status."""
        return self.on_time + self.overdue + self.completed


def is_information(kind: str) -> bool:
    """Whether the item is an annotation of the minutes: an information is not an action."""
    return kind.strip().lower().startswith(_INFORMATION_PREFIX)


def effective_due_date(planned_date: date | None, replanned_date: date | None) -> date | None:
    """The deadline in force: the replanned date when there is one, otherwise the planned one."""
    return replanned_date or planned_date


def action_status(dates: ActionDates, reference_date: date) -> ActionStatus:
    """The status of an action on the reference date (the single status engine).

    Informação when the item is an annotation; Concluída when it has a completion date;
    Atrasada when the deadline in force is before the reference date (a deadline equal to
    the reference date is still on time); Em andamento otherwise.
    """
    if is_information(dates.kind):
        return ActionStatus.INFORMATION
    if dates.completed_on is not None:
        return ActionStatus.COMPLETED
    due = effective_due_date(dates.planned_date, dates.replanned_date)
    if due is not None and due < reference_date:
        return ActionStatus.OVERDUE
    return ActionStatus.IN_PROGRESS


def days_overdue(dates: ActionDates, reference_date: date) -> int:
    """Days between the deadline in force and the reference date; zero when not overdue."""
    if action_status(dates, reference_date) is not ActionStatus.OVERDUE:
        return 0
    due = effective_due_date(dates.planned_date, dates.replanned_date)
    return 0 if due is None else (reference_date - due).days


def overdue_action_count(actions: Iterable[ActionDates], reference_date: date) -> int:
    """Total de ações atrasadas: how many of the actions are Atrasada on the reference date."""
    return sum(
        1 for dates in actions if action_status(dates, reference_date) is ActionStatus.OVERDUE
    )


def matches_status_filter(status_filter: StatusFilter, status: ActionStatus) -> bool:
    """Whether a status passes the filter: Em andamento includes the overdue; Todos has no info."""
    if status is ActionStatus.INFORMATION:
        return False
    if status_filter is StatusFilter.ALL:
        return True
    if status_filter is StatusFilter.OPEN:
        return status in (ActionStatus.IN_PROGRESS, ActionStatus.OVERDUE)
    return status.value == status_filter.value


def counts_by_status(statuses: Iterable[ActionStatus]) -> StatusCounts:
    """The KPI numbers of a set of statuses; informations are not counted (they are not actions)."""
    collected = list(statuses)
    return StatusCounts(
        on_time=collected.count(ActionStatus.IN_PROGRESS),
        overdue=collected.count(ActionStatus.OVERDUE),
        completed=collected.count(ActionStatus.COMPLETED),
    )


def due_by_reference_count(actions: Iterable[ActionDates], reference_date: date) -> int:
    """Concluídas: Previsto: how many actions had their original deadline up to the reference."""
    return sum(
        1
        for dates in actions
        if dates.planned_date is not None and dates.planned_date <= reference_date
    )


def overdue_share_of_open(counts: StatusCounts) -> int | None:
    """Atrasadas as a whole percentage of the open ones; ``None`` when nothing is open."""
    if counts.open == 0:
        return None
    share = Decimal(counts.overdue) * _PERCENT / Decimal(counts.open)
    return int(share.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class RevisionEntry:
    """What the lineage of a minutes needs of one revision: its id, project, number and revision."""

    id: int
    project_id: int
    number: str
    revision: int


def latest_revision_ids(entries: Iterable[RevisionEntry]) -> frozenset[int]:
    """Ata mais recente de cada linhagem: o id da maior revisão de cada número do projeto.

    A lineage is the number inside one project; two projects may hold the same number. The list
    of minutes shows only these (HU-051).
    """
    latest: dict[tuple[int, str], RevisionEntry] = {}
    for entry in entries:
        key = (entry.project_id, entry.number)
        known = latest.get(key)
        if known is None or entry.revision > known.revision:
            latest[key] = entry
    return frozenset(entry.id for entry in latest.values())


# ── Painel e follow-up (ISSUE-020) ───────────────────────────────────────────────────────────

TOP_RESPONSIBLES = 10


@dataclass(frozen=True)
class ResponsibleTally:
    """What the panel counts for a group of actions: the three statuses and the longest delay."""

    on_time: int
    overdue: int
    completed: int
    longest_delay: int

    @property
    def open(self) -> int:
        """Abertas: the ones on time plus the overdue ones."""
        return self.on_time + self.overdue

    @property
    def total(self) -> int:
        """Every action counted, whatever its status."""
        return self.on_time + self.overdue + self.completed

    @property
    def overdue_share(self) -> int | None:
        """Atrasadas as a whole percentage of the open ones; ``None`` when nothing is open."""
        return whole_percent(self.overdue, self.open)


@dataclass(frozen=True)
class MonthCount:
    """Previstas x concluídas of one civil month (``2026-09``)."""

    month: str
    planned: int
    completed: int


@dataclass(frozen=True)
class FollowUpAction:
    """What the follow-up message says about an open action of one responsible."""

    action_id: int
    project_id: int
    responsible_id: int
    label: str
    subject: str
    due_date: date | None
    status: ActionStatus
    days_overdue: int


@dataclass(frozen=True)
class FollowUpGroup:
    """The open actions of one responsible, the longest delay first."""

    responsible_id: int
    actions: tuple[FollowUpAction, ...]

    @property
    def overdue_count(self) -> int:
        """How many of the actions are Atrasada."""
        return sum(1 for item in self.actions if item.status is ActionStatus.OVERDUE)


def whole_percent(part: int, whole: int) -> int | None:
    """``part`` as a whole percentage of ``whole`` (half up); ``None`` when ``whole`` is zero."""
    if whole == 0:
        return None
    share = Decimal(part) * _PERCENT / Decimal(whole)
    return int(share.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def responsible_tally(items: Iterable[tuple[ActionStatus, int]]) -> ResponsibleTally:
    """The panel numbers of a group from ``(status, days overdue)``; informations do not count."""
    collected = list(items)
    return ResponsibleTally(
        on_time=sum(1 for status, _ in collected if status is ActionStatus.IN_PROGRESS),
        overdue=sum(1 for status, _ in collected if status is ActionStatus.OVERDUE),
        completed=sum(1 for status, _ in collected if status is ActionStatus.COMPLETED),
        longest_delay=max(
            (days for status, days in collected if status is ActionStatus.OVERDUE), default=0
        ),
    )


def completed_on_planned_count(actions: Iterable[ActionDates]) -> int:
    """Concluídas no prazo original: completed on or before the planned date, never replanned out."""
    return sum(
        1
        for dates in actions
        if dates.completed_on is not None
        and dates.planned_date is not None
        and dates.completed_on <= dates.planned_date
    )


def monthly_planned_vs_completed(actions: Iterable[ActionDates]) -> list[MonthCount]:
    """Previstas x concluídas por mês: planned by the month of the deadline in force.

    A completed action also counts as planned in the month of its deadline, as the prototype
    does; the completions are counted in the month of the completion date.
    """
    planned: dict[str, int] = {}
    completed: dict[str, int] = {}
    for dates in actions:
        due = effective_due_date(dates.planned_date, dates.replanned_date)
        if due is not None:
            month = due.strftime("%Y-%m")
            planned[month] = planned.get(month, 0) + 1
        if dates.completed_on is not None:
            key = dates.completed_on.strftime("%Y-%m")
            completed[key] = completed.get(key, 0) + 1
    return [
        MonthCount(month=key, planned=planned.get(key, 0), completed=completed.get(key, 0))
        for key in sorted(planned.keys() | completed.keys())
    ]


def top_open_responsibles(
    tallies: Mapping[int, ResponsibleTally], limit: int = TOP_RESPONSIBLES
) -> list[int]:
    """Os que têm mais ações abertas (até ``limit``), as atrasadas desempatam, depois o id."""
    candidates = [key for key, tally in tallies.items() if tally.open > 0]
    ranked = sorted(candidates, key=lambda key: (-tallies[key].open, -tallies[key].overdue, key))
    return ranked[:limit]


def group_for_follow_up(
    items: Iterable[FollowUpAction], names: Mapping[int, str]
) -> list[FollowUpGroup]:
    """One group per responsible with open actions: the most overdue first, then by name.

    Only Em andamento and Atrasada enter; inside a group the longest delay comes first, then
    the closest deadline.
    """
    by_person: dict[int, list[FollowUpAction]] = {}
    for item in items:
        if item.status in (ActionStatus.IN_PROGRESS, ActionStatus.OVERDUE):
            by_person.setdefault(item.responsible_id, []).append(item)
    groups = [
        FollowUpGroup(
            responsible_id=person,
            actions=tuple(
                sorted(
                    listed,
                    key=lambda item: (
                        -item.days_overdue,
                        item.due_date is None,
                        item.due_date or date.min,
                        item.action_id,
                    ),
                )
            ),
        )
        for person, listed in by_person.items()
    ]
    return sorted(
        groups,
        key=lambda group: (
            -group.overdue_count,
            names.get(group.responsible_id, "").casefold(),
            group.responsible_id,
        ),
    )
