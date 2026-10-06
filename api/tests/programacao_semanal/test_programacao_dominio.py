"""Domain rules of the Weekly Scheduling that the screen would show plausible and wrong.

Ported from ``test_dominio.py`` of the app (weeks, figures, window): same cases, same
borders, with the names of the code in English.
"""

from __future__ import annotations

from datetime import datetime, time

import pytest

from src.modulos.programacao_semanal import calculations, weeks
from src.modulos.programacao_semanal import window as window_rules

# ── Weeks ───────────────────────────────────────────────────────────────


def test_reference_round_trip() -> None:
    assert weeks.parts("S.30/2026") == (2026, 30)
    assert weeks.reference(2026, 30) == "S.30/2026"


def test_week_opens_on_monday_and_closes_on_sunday() -> None:
    first, last = weeks.start("S.30/2026"), weeks.end("S.30/2026")
    assert first is not None
    assert last is not None
    assert first.weekday() == 0
    assert last.weekday() == 6
    assert (last - first).days == 6


def test_week_has_seven_dates_monday_first() -> None:
    dates = weeks.week_dates("S.30/2026")
    assert [day.weekday() for day in dates] == [0, 1, 2, 3, 4, 5, 6]


def test_invalid_reference_does_not_blow_up() -> None:
    assert weeks.start("qualquer coisa") is None
    assert weeks.parts("") == (0, 0)
    assert weeks.week_dates("qualquer coisa") == []
    assert not weeks.is_valid("S.54/2026")


def test_year_of_53_weeks() -> None:
    """2026 has 53 ISO weeks: fixing 52 would break the turn of the year."""
    assert weeks.weeks_in_year(2026) == 53
    assert weeks.start("S.53/2026") is not None


def test_shift_crosses_the_year() -> None:
    assert weeks.shift("S.53/2026", 1) == "S.01/2027"
    assert weeks.shift("S.01/2027", -1) == "S.53/2026"


def test_order_is_chronological_across_years() -> None:
    references = ["S.02/2027", "S.51/2026", "S.01/2027"]
    assert sorted(references, key=weeks.sort_key) == ["S.51/2026", "S.01/2027", "S.02/2027"]


def test_week_of_a_sunday_is_the_week_that_ends_on_it() -> None:
    last = weeks.end("S.30/2026")
    assert last is not None
    assert weeks.of_date(last) == "S.30/2026"
    assert weeks.of_date(weeks.week_dates("S.31/2026")[0]) == "S.31/2026"


# ── Figures ─────────────────────────────────────────────────────────────


def figures(planned: list[float], day: list[float] | None = None, night: list[float] | None = None):
    return calculations.figures_of(planned, day, night, headline=sum(planned))


def test_ppc_sums_both_shifts() -> None:
    result = figures([10] * 7, day=[5] * 7, night=[5] * 7)
    assert result.planned_total == 70
    assert result.done_total == 70
    assert result.ppc == 100


def test_number_accepts_the_brazilian_format() -> None:
    assert calculations.to_number("1.234,5") == 1234.5
    assert calculations.to_number("1234.5") == 1234.5
    assert calculations.to_number("") == 0.0
    assert calculations.to_number(None) == 0.0
    assert calculations.to_number("não é número") == 0.0


def test_seven_days_normalizes_any_input() -> None:
    assert calculations.seven_days([1, 2]) == [1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert len(calculations.seven_days(list(range(20)))) == 7
    assert calculations.seven_days(None) == [0.0] * 7


def test_adherence_weighs_by_size_and_mean_ppc_does_not() -> None:
    """A big activity at 50% and a small one at 100%: adherence ~50, the mean PPC is 75."""
    big = figures([100] * 7, day=[50] * 7)
    small = figures([1] * 7, day=[1] * 7)
    assert calculations.schedule_adherence([big, small]) == pytest.approx(50.5, abs=0.1)
    assert calculations.mean_ppc([big, small]) == 75.0


@pytest.mark.parametrize(
    ("value", "band"),
    [
        (80, "alta"),
        (79.9, "media"),
        (60, "media"),
        (59.9, "baixa"),
        (0, "baixa"),
    ],
)
def test_band_at_the_borders(value: float, band: str) -> None:
    assert calculations.performance_band(value) == band


def test_zero_planned_does_not_divide_by_zero() -> None:
    result = figures([0] * 7, day=[10] * 7)
    assert result.ppc == 0.0
    assert calculations.schedule_adherence([result]) == 0.0


def test_day_totals_add_the_night_shift_of_each_day() -> None:
    result = figures([10] * 7, day=[1, 2, 3, 0, 0, 0, 0], night=[0, 1, 0, 0, 0, 0, 4])
    assert result.day_totals == (1.0, 3.0, 3.0, 0.0, 0.0, 0.0, 4.0)


# ── Window of programming ───────────────────────────────────────────────

FRIDAY = datetime(2026, 7, 24, 10, 0)  # noqa: DTZ001 - fixed clock of the test
SATURDAY = datetime(2026, 7, 25, 10, 0)  # noqa: DTZ001

REGULAR = window_rules.Window(
    company_id=1,
    days=(window_rules.WindowDay(weekday=5, opens=time(8, 0), closes=time(15, 0)),),
    weeks=frozenset({"S.31/2026"}),
)


def test_open_on_the_day_and_hour() -> None:
    assert window_rules.decide("S.31/2026", REGULAR, FRIDAY).is_open


def test_closed_out_of_hours() -> None:
    decision = window_rules.decide("S.31/2026", REGULAR, FRIDAY.replace(hour=16))
    assert not decision.is_open
    assert "15:00" in decision.reason


def test_hours_are_read_to_the_minute_with_both_ends_included() -> None:
    assert window_rules.decide("S.31/2026", REGULAR, FRIDAY.replace(hour=15, minute=0)).is_open
    assert not window_rules.decide("S.31/2026", REGULAR, FRIDAY.replace(hour=15, minute=1)).is_open
    assert window_rules.decide("S.31/2026", REGULAR, FRIDAY.replace(hour=8, minute=0)).is_open


def test_closed_on_the_wrong_weekday() -> None:
    assert not window_rules.decide("S.31/2026", REGULAR, SATURDAY).is_open


def test_closed_for_a_week_not_released() -> None:
    decision = window_rules.decide("S.40/2026", REGULAR, FRIDAY)
    assert not decision.is_open
    assert "S.40/2026" in decision.reason


def test_no_window_registered_is_closed() -> None:
    assert not window_rules.decide("S.31/2026", None, FRIDAY).is_open


def test_extra_release_opens_on_the_wrong_day() -> None:
    extra = window_rules.ExtraRelease(
        week="S.40/2026",
        opens=datetime(2026, 7, 25, 0, 0),  # noqa: DTZ001
        closes=datetime(2026, 7, 26, 23, 59),  # noqa: DTZ001
    )
    window = window_rules.Window(
        company_id=1, days=REGULAR.days, weeks=REGULAR.weeks, extras=(extra,)
    )
    decision = window_rules.decide("S.40/2026", window, SATURDAY)
    assert decision.is_open
    assert "extraordinária" in decision.reason


def test_extra_release_also_closes_what_was_released() -> None:
    """The exception wins in BOTH directions: that is its point."""
    extra = window_rules.ExtraRelease(
        week="S.31/2026",
        opens=datetime(2026, 1, 1, 0, 0),  # noqa: DTZ001
        closes=datetime(2026, 1, 2, 0, 0),  # noqa: DTZ001
    )
    window = window_rules.Window(
        company_id=1, days=REGULAR.days, weeks=REGULAR.weeks, extras=(extra,)
    )
    assert not window_rules.decide("S.31/2026", window, FRIDAY).is_open


def test_no_weekday_configured_releases_any_day() -> None:
    window = window_rules.Window(company_id=1, days=(), weeks=REGULAR.weeks)
    assert window_rules.decide("S.31/2026", window, SATURDAY).is_open
