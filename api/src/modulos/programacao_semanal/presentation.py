"""How the matrix reads: numbers and day cells as a person sees them (D10).

The app's formatting, in Python so a template never decides a number: the measure of a
cell that is sixty pixels wide, the percentage, the seven-day grid with its states.
Pure functions over the figures of ``calculations``; no database, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.modulos.programacao_semanal import calculations
from src.modulos.programacao_semanal.calculations import ActivityFigures

# A countable unit never takes a decimal: "2,0 und" is noise.
INTEGER_UNITS = frozenset({"und", "unid", "un", "pç", "pc", "peça", "peca"})
THOUSAND = 1_000
HUNDRED_THOUSAND = 100_000
HUNDRED = 100
DECIMAL_TOLERANCE = 0.05
DASH = "—"

SITUATION_TONES = {
    calculations.SITUATION_DRAFT: "warn",
    calculations.SITUATION_VALIDATED: "fix",
    calculations.SITUATION_PUBLISHED: "ok",
}
SITUATION_SHORT_LABELS = {
    calculations.SITUATION_DRAFT: "Elaboração",
    calculations.SITUATION_VALIDATED: "Validada",
    calculations.SITUATION_PUBLISHED: "Publicada",
}


def format_number(value: float | None, digits: int = 1) -> str:
    """``1234.5`` as ``1.234,5``: Brazilian numbers, never ``1234.5`` on a screen."""
    number = float(value or 0)
    grouped = f"{number:,.{digits}f}"
    return grouped.replace(",", " ").replace(".", ",").replace(" ", ".")


def format_quantity(value: object, unit: str = "") -> str:
    """A quantity for a cell that is sixty pixels wide; the unit changes how it reads.

    A countable unit (``und``) never takes a decimal; from 100 on the decimal says
    nothing; below 100 it is the information (2,5 m³ is not 3 m³); from a hundred
    thousand it reads as ``123 mil``. Zero is a dash and not ``0``: the difference
    between "did not produce" and "had no plan" is what the matrix has to show.
    """
    number = calculations.to_number(value)
    if number == 0:
        return DASH
    if abs(number) >= HUNDRED_THOUSAND:
        return format_number(number / THOUSAND, 0) + " mil"
    if (unit or "").strip().lower() in INTEGER_UNITS:
        return format_number(number, 0)
    if abs(number) >= HUNDRED or abs(number - round(number)) < DECIMAL_TOLERANCE:
        return format_number(number, 0)
    return format_number(number, 1)


def format_percent(value: float | None, digits: int = 0) -> str:
    """``45,3%``: a percentage the way the matrix and the strip print it."""
    return f"{format_number(value, digits)}%"


@dataclass(frozen=True)
class DayCell:
    """One day of the grid: the planned line and the done line, already worded."""

    planned_text: str
    planned_title: str
    planned_classes: str
    done_text: str
    done_title: str
    done_classes: str
    has_night: bool


def day_cells(figures: ActivityFigures, unit: str, dates: list[date]) -> list[DayCell]:
    """The seven cells of the grid, Monday first.

    The color marks the exception, not the rule: delivering a little under the plan is
    the common case and stays neutral; what stands out is the day planned that did not
    produce, the production without a plan and the day that hit the target.
    """
    cells = []
    for index in range(calculations.DAYS):
        planned = figures.planned_days[index]
        done = figures.day_totals[index]
        night = figures.night_shift[index]
        label = _day_label(index, dates)
        state, meaning = _day_state(planned, done)
        weekend = " is-fds" if index >= calculations.DAYS - 2 else ""
        planned_text = format_quantity(planned, unit)
        done_text = format_quantity(done, unit)
        cells.append(
            DayCell(
                planned_text=planned_text,
                planned_title=f"{label} — previsto {planned_text} {unit}".rstrip(),
                planned_classes=f"dia dia--prev{weekend}{' is-nulo' if not planned else ''}",
                done_text=done_text,
                done_title=(
                    f"{label} — {meaning}. Previsto {planned_text}, realizado {done_text} {unit}"
                    + (" (inclui turno noite)" if night else "")
                ).replace("  ", " "),
                done_classes=f"dia dia--real {state}{weekend}".replace("  ", " "),
                has_night=bool(night),
            )
        )
    return cells


def _day_label(index: int, dates: list[date]) -> str:
    name = calculations.DAY_NAMES[index]
    if not dates:
        return name
    return f"{name} {dates[index]:%d/%m}"


def _day_state(planned: float, done: float) -> tuple[str, str]:
    """The CSS state of the done cell of a day and what it means."""
    if planned and not done:
        return "is-parado", "dia programado sem produção registrada"
    if done and not planned:
        return "is-extra", "produção sem previsão para o dia"
    if done and done >= planned:
        return "is-batido", "meta do dia atingida"
    if not planned and not done:
        return "is-nulo", "sem previsão e sem produção"
    return "", "abaixo do previsto no dia"
