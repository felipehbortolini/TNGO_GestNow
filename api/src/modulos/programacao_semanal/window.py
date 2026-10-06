"""The programming window: when a contractor may write its own schedule (D10).

The rule belongs to the company, not to the person: everyone of the same company
shares one window per project. Three ways in, checked in this order:

1. **Liberação extraordinária**: an absolute interval opened for one week. It
   overrides everything else, in both directions: inside the interval the window
   is open even on the wrong weekday; outside it the week is closed even if the
   regular rule would allow it. That is the point of an exception.
2. **Semanas liberadas**: the set of weeks the company may touch at all.
3. **Janela regular**: weekday plus opening hours (Friday, 09:00 to 15:00).

The decision is pure: it takes the window and the instant, never the clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

WEEKDAY_NAMES = {
    1: "Segunda-feira",
    2: "Terça-feira",
    3: "Quarta-feira",
    4: "Quinta-feira",
    5: "Sexta-feira",
    6: "Sábado",
    7: "Domingo",
}

NO_WINDOW_MESSAGE = "Fornecedor sem janela cadastrada."
EXTRA_OPEN_MESSAGE = "Liberação extraordinária ativa."
EXTRA_CLOSED_MESSAGE = "Fora do período da liberação extraordinária."
ANY_DAY_MESSAGE = "Sem restrição de dia — qualquer dia das semanas liberadas."


@dataclass(frozen=True)
class WindowDay:
    """A weekday (ISO, 1 is Monday) and the hours the regular window is open in it."""

    weekday: int
    opens: time
    closes: time


@dataclass(frozen=True)
class ExtraRelease:
    """An interval opened for one week, whatever the regular rule says."""

    week: str
    opens: datetime
    closes: datetime


@dataclass(frozen=True)
class Window:
    """The window of one company in one project."""

    company_id: int
    days: tuple[WindowDay, ...] = ()
    weeks: frozenset[str] = frozenset()
    extras: tuple[ExtraRelease, ...] = ()


@dataclass(frozen=True)
class WindowDecision:
    """Whether the window is open for a week, and the sentence that says why."""

    is_open: bool
    reason: str


def hours_text(moment: time) -> str:
    """``08:00``: how a time of the window is written."""
    return f"{moment.hour:02d}:{moment.minute:02d}"


def decide(week: str, window: Window | None, at: datetime) -> WindowDecision:
    """Whether the window is open for ``week`` at the instant ``at``, and why."""
    if window is None:
        return WindowDecision(is_open=False, reason=NO_WINDOW_MESSAGE)

    extra = _extra_decision(week, window, at)
    if extra is not None:
        return extra

    if week not in window.weeks:
        return WindowDecision(
            is_open=False, reason=f"A semana {week} não está liberada para esta empresa."
        )

    return _weekday_decision(window, at)


def _extra_decision(week: str, window: Window, at: datetime) -> WindowDecision | None:
    """The exception for this week, when there is one; ``None`` otherwise."""
    for extra in window.extras:
        if extra.week != week:
            continue
        if extra.opens <= at <= extra.closes:
            return WindowDecision(is_open=True, reason=EXTRA_OPEN_MESSAGE)
        return WindowDecision(is_open=False, reason=EXTRA_CLOSED_MESSAGE)
    return None


def _weekday_decision(window: Window, at: datetime) -> WindowDecision:
    """Weekday and opening hours: the regular rule."""
    for rule in window.days:
        if rule.weekday != at.isoweekday():
            continue
        if _within_hours(at, rule):
            return WindowDecision(
                is_open=True, reason=f"Janela aberta até {hours_text(rule.closes)}."
            )
        return WindowDecision(
            is_open=False,
            reason=(
                f"Janela fechada agora — hoje ela vale das {hours_text(rule.opens)} "
                f"às {hours_text(rule.closes)}."
            ),
        )

    if not window.days:
        return WindowDecision(is_open=True, reason=ANY_DAY_MESSAGE)
    names = ", ".join(WEEKDAY_NAMES.get(rule.weekday, str(rule.weekday)) for rule in window.days)
    return WindowDecision(
        is_open=False, reason=f"Hoje não é dia de programar. Dia liberado: {names}."
    )


def _within_hours(at: datetime, rule: WindowDay) -> bool:
    """Opening hours are read to the minute, both ends included."""
    minute = (at.hour, at.minute)
    return (rule.opens.hour, rule.opens.minute) <= minute <= (rule.closes.hour, rule.closes.minute)
