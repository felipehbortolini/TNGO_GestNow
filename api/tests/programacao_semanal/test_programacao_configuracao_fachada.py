"""Facade of the configuration of the schedule: who edits, the defaults, the limits and the trail (D10, ISSUE-054)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, time
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit, calendario
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.core.rbac import ScheduleRole
from src.modulos.programacao_semanal import configuration, repository, service
from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.configuration import ParametersForm, WeekdayInput, WindowForm
from tests.cenario_programacao import FRIDAY_MORNING, WEEK, Scenario, make_admin, make_user

SETTINGS_TABLE = "programacao_configuracao"
WINDOW_TABLE = "programacao_janela"
NEXT_WEEK = "S.32/2026"


def _form(**changes: Any) -> ParametersForm:
    base = ParametersForm(
        adherence_target="50", ppc_target="80", deviation_limit="20", requires_deviation_note=True
    )
    return replace(base, **changes)


def _trail(session: Session, table: str) -> list[AuditEntry]:
    statement = select(AuditEntry).where(AuditEntry.entity == table).order_by(AuditEntry.id)
    return list(session.scalars(statement))


def _window_form(scenario: Scenario, **changes: Any) -> WindowForm:
    base = WindowForm(
        company_id=scenario.company_a,
        days=(WeekdayInput(1, "07:00", "12:00"),),
        weeks=(WEEK, NEXT_WEEK),
    )
    return replace(base, **changes)


def _window_version(scenario: Scenario, company_id: int) -> str:
    rows = repository.windows_by_company(scenario.session, project_id=scenario.project_id)
    return str(rows[company_id].version)


# ── Who edits ─────────────────────────────────────────────────────────────


def test_the_planner_of_the_project_edits_the_parameters(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)

    configuration.save_parameters(
        scenario.session, caller=caller, form=_form(adherence_target="50"), version=None
    )

    parameters = service.parameters_of(scenario.session, scenario.project_id)
    assert parameters.adherence_target == 50.0
    assert parameters.ppc_target == 80.0
    assert parameters.deviation_limit == 20.0


def test_the_admin_edits_in_any_project(scenario: Scenario) -> None:
    admin = make_admin(scenario.session, email="cfg-admin@example.invalid")

    configuration.save_parameters(
        scenario.session, caller=scenario.caller(admin), form=_form(), version=None
    )

    assert service.parameters_of(scenario.session, scenario.project_id).ppc_target == 80.0


def test_the_planner_of_another_project_gets_403(scenario: Scenario) -> None:
    elsewhere = make_user(
        scenario.session,
        email="cfg-plan-outro@example.invalid",
        project_id=scenario.other_project_id,
        role=ScheduleRole.PLANNER,
    )

    with pytest.raises(AccessDeniedError):
        configuration.save_parameters(
            scenario.session, caller=scenario.caller(elsewhere), form=_form(), version=None
        )
    with pytest.raises(AccessDeniedError):
        configuration.save_window(
            scenario.session,
            caller=scenario.caller(elsewhere),
            form=_window_form(scenario),
            version=_window_version(scenario, scenario.company_a),
        )


@pytest.mark.parametrize("who", ["viewer", "supplier_a"])
def test_a_viewer_and_a_supplier_do_not_edit(scenario: Scenario, who: str) -> None:
    caller = scenario.caller(getattr(scenario, who))

    with pytest.raises(AccessDeniedError):
        configuration.save_parameters(scenario.session, caller=caller, form=_form(), version=None)


def test_in_the_portfolio_saving_asks_for_a_project(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner, project=False)

    with pytest.raises(InvalidDataError):
        configuration.save_parameters(scenario.session, caller=caller, form=_form(), version=None)


# ── Valid at once, and the trail ──────────────────────────────────────────


def test_a_change_is_read_on_the_next_request_and_the_trail_keeps_before_and_after(
    scenario: Scenario,
) -> None:
    configuration.create_default_settings(
        scenario.session, user_id=scenario.author_id, project_id=scenario.project_id
    )
    row = repository.settings_of(scenario.session, scenario.project_id)
    assert row is not None

    configuration.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=_form(adherence_target="55", deviation_limit="12,5"),
        version=str(row.version),
    )

    assert service.parameters_of(scenario.session, scenario.project_id).deviation_limit == 12.5
    changed = [
        line for line in _trail(scenario.session, SETTINGS_TABLE) if line.action == audit.UPDATED
    ]
    assert len(changed) == 1
    assert changed[0].before["meta_aderencia"] == 60.0
    assert changed[0].after["meta_aderencia"] == 55.0
    assert changed[0].before["limite_desvio_justificativa"] == 15.0
    assert changed[0].after["limite_desvio_justificativa"] == 12.5
    assert changed[0].project_id == scenario.project_id


def test_a_stale_version_is_a_conflict(scenario: Scenario) -> None:
    configuration.create_default_settings(
        scenario.session, user_id=scenario.author_id, project_id=scenario.project_id
    )
    caller = scenario.caller(scenario.planner)
    configuration.save_parameters(scenario.session, caller=caller, form=_form(), version="1")

    with pytest.raises(VersionConflictError):
        configuration.save_parameters(scenario.session, caller=caller, form=_form(), version="1")


# ── The defaults of the app ───────────────────────────────────────────────


def test_a_new_project_is_born_with_the_defaults_of_the_app(scenario: Scenario) -> None:
    row = configuration.create_default_settings(
        scenario.session, user_id=scenario.author_id, project_id=scenario.other_project_id
    )

    assert row.adherence_target == 60.0
    assert row.ppc_target == 75.0
    assert row.deviation_limit == 15.0
    assert row.requires_deviation_note is True
    assert row.reference_week is None
    created = _trail(scenario.session, SETTINGS_TABLE)
    assert [line.action for line in created] == [audit.CREATED]


def test_the_defaults_are_created_once(scenario: Scenario) -> None:
    first = configuration.create_default_settings(
        scenario.session, user_id=scenario.author_id, project_id=scenario.other_project_id
    )
    second = configuration.create_default_settings(
        scenario.session, user_id=scenario.author_id, project_id=scenario.other_project_id
    )

    assert first.id == second.id
    assert len(_trail(scenario.session, SETTINGS_TABLE)) == 1


def test_a_project_changing_one_does_not_change_another(scenario: Scenario) -> None:
    configuration.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=_form(adherence_target="40"),
        version=None,
    )

    assert (
        service.parameters_of(scenario.session, scenario.other_project_id).adherence_target == 60.0
    )


# ── The limits of the numbers ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("typed", "accepted"),
    [("0", True), ("100", True), ("100,01", False), ("-1", False), ("abc", False), ("nan", False)],
)
def test_the_targets_go_from_0_to_100(typed: str, *, accepted: bool) -> None:
    parameters, errors = configuration.check_parameters(_form(ppc_target=typed))

    assert ("meta_ppc" not in errors) is accepted
    if accepted:
        assert parameters.ppc_target == float(typed.replace(",", "."))


def test_an_empty_number_is_the_default_of_the_app() -> None:
    parameters, errors = configuration.check_parameters(
        _form(adherence_target="", ppc_target="", deviation_limit="")
    )

    assert not errors
    assert (parameters.adherence_target, parameters.ppc_target, parameters.deviation_limit) == (
        60.0,
        75.0,
        15.0,
    )


def test_the_reference_week_has_the_format_of_the_app() -> None:
    assert "semana_referencia" in configuration.check_parameters(_form(reference_week="2026-31"))[1]
    assert "semana_referencia" not in configuration.check_parameters(_form(reference_week=WEEK))[1]


# ── The window of a company ───────────────────────────────────────────────


def test_the_window_changes_at_once_and_the_trail_keeps_its_content_before_and_after(
    scenario: Scenario,
) -> None:
    configuration.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=_window_form(scenario),
        version=_window_version(scenario, scenario.company_a),
    )

    window = repository.window_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert window is not None
    assert [(day.weekday, day.opens, day.closes) for day in window.days] == [(1, time(7), time(12))]
    assert window.weeks == frozenset({WEEK, NEXT_WEEK})
    line = _trail(scenario.session, WINDOW_TABLE)[-1]
    assert line.action == audit.UPDATED
    assert line.before["dias"] == [{"dia_semana": 5, "abre": "08:00", "fecha": "15:00"}]
    assert line.after["dias"] == [{"dia_semana": 1, "abre": "07:00", "fecha": "12:00"}]
    assert line.before["semanas"] == [WEEK]
    assert line.after["semanas"] == [WEEK, NEXT_WEEK]


def test_the_new_window_is_what_the_supplier_meets_on_the_next_request(scenario: Scenario) -> None:
    configuration.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=_window_form(scenario, days=(), weeks=(NEXT_WEEK,)),
        version=_window_version(scenario, scenario.company_a),
    )

    caller = scenario.caller(scenario.supplier_a, now=FRIDAY_MORNING)
    assert service.window_status(scenario.session, caller=caller, week=WEEK).is_open is False
    assert service.window_status(scenario.session, caller=caller, week=NEXT_WEEK).is_open is True


def test_a_company_without_a_window_gets_one_created_with_the_trail(scenario: Scenario) -> None:
    configuration.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=_window_form(scenario, company_id=scenario.company_b),
        version=None,
    )

    window = repository.window_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_b
    )
    assert window is not None
    assert window.weeks == frozenset({WEEK, NEXT_WEEK})
    line = _trail(scenario.session, WINDOW_TABLE)[-1]
    assert line.action == audit.CREATED
    assert line.before is None
    assert line.after["semanas"] == [WEEK, NEXT_WEEK]


def test_saving_the_same_window_leaves_no_trail(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)
    same = _window_form(scenario, days=(WeekdayInput(5, "08:00", "15:00"),), weeks=(WEEK,))
    before = len(_trail(scenario.session, WINDOW_TABLE))

    configuration.save_window(
        scenario.session,
        caller=caller,
        form=same,
        version=_window_version(scenario, scenario.company_a),
    )

    assert len(_trail(scenario.session, WINDOW_TABLE)) == before


def test_a_stale_window_version_is_a_conflict(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)
    version = _window_version(scenario, scenario.company_a)
    configuration.save_window(
        scenario.session, caller=caller, form=_window_form(scenario), version=version
    )

    with pytest.raises(VersionConflictError):
        configuration.save_window(
            scenario.session,
            caller=caller,
            form=_window_form(scenario, weeks=(WEEK,)),
            version=version,
        )


def test_the_company_has_to_be_registered(scenario: Scenario) -> None:
    with pytest.raises(InvalidDataError):
        configuration.save_window(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            form=_window_form(scenario, company_id=999999),
            version=None,
        )


@pytest.mark.parametrize(
    ("opens", "closes", "accepted"),
    [("08:00", "08:00", True), ("08:00", "07:59", False), ("", "", True), ("8h", "15:00", False)],
)
def test_the_hours_of_a_weekday_open_before_they_close(
    opens: str, closes: str, *, accepted: bool
) -> None:
    form = WindowForm(company_id=1, days=(WeekdayInput(2, opens, closes),))

    rules, errors = configuration.build_rules(form, company_id=1, current=None)

    assert (not errors) is accepted
    if accepted and not opens:
        assert rules.days[0].opens == time(0, 1)
        assert rules.days[0].closes == time(23, 59)


def test_a_week_that_is_not_a_week_is_refused() -> None:
    form = WindowForm(company_id=1, weeks=("S.31/2026", "semana 9"))

    rules, errors = configuration.build_rules(form, company_id=1, current=None)

    assert "semanas" in errors
    assert rules.weeks == frozenset({"S.31/2026"})


# ── The extraordinary releases ────────────────────────────────────────────


def test_an_extra_release_is_added_replaced_and_removed(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)

    def saved(**fields: str) -> None:
        configuration.save_window(
            scenario.session,
            caller=caller,
            form=_window_form(scenario, weeks=(WEEK,), **fields),
            version=_window_version(scenario, scenario.company_a),
        )

    saved(extra_week=NEXT_WEEK, extra_opens="2026-08-03T08:00", extra_closes="2026-08-03T12:00")
    window = repository.window_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert window is not None and len(window.extras) == 1
    assert window.extras[0].opens == datetime(2026, 8, 3, 8, 0, tzinfo=calendario.PRODUCT_TIMEZONE)

    saved(extra_week=NEXT_WEEK, extra_opens="2026-08-04T08:00", extra_closes="2026-08-04T12:00")
    window = repository.window_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert window is not None and len(window.extras) == 1
    assert window.extras[0].opens.day == 4

    saved(remove_extra=NEXT_WEEK)
    window = repository.window_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert window is not None and window.extras == ()


def test_an_extra_release_opens_a_week_that_the_regular_rule_closes(scenario: Scenario) -> None:
    configuration.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=_window_form(
            scenario,
            weeks=(WEEK,),
            extra_week=WEEK,
            extra_opens="2026-07-25T08:00",
            extra_closes="2026-07-25T12:00",
        ),
        version=_window_version(scenario, scenario.company_a),
    )
    window = repository.window_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )

    saturday = datetime(2026, 7, 25, 10, 0, tzinfo=calendario.PRODUCT_TIMEZONE)
    assert window_rules.decide(WEEK, window, saturday).is_open is True


@pytest.mark.parametrize(
    ("week", "opens", "closes"),
    [
        (NEXT_WEEK, "2026-08-03T08:00", ""),
        ("", "2026-08-03T08:00", "2026-08-03T12:00"),
        ("S.99/2026", "2026-08-03T08:00", "2026-08-03T12:00"),
        (NEXT_WEEK, "2026-08-03T12:00", "2026-08-03T12:00"),
        (NEXT_WEEK, "2026-08-03T12:00", "2026-08-03T08:00"),
        (NEXT_WEEK, "ontem", "hoje"),
    ],
)
def test_an_incomplete_or_backwards_extra_release_is_refused(
    week: str, opens: str, closes: str
) -> None:
    form = WindowForm(company_id=1, extra_week=week, extra_opens=opens, extra_closes=closes)

    _rules, errors = configuration.build_rules(form, company_id=1, current=None)

    assert "extra" in errors


# ── What the screen reads ─────────────────────────────────────────────────


def test_a_supplier_reads_only_the_window_of_its_own_company(scenario: Scenario) -> None:
    project = configuration.project_configuration(
        scenario.session, caller=scenario.caller(scenario.supplier_a)
    )

    assert [item.company_id for item in project.windows] == [scenario.company_a]
    assert project.can_edit is False


def test_the_planner_reads_every_company_and_may_edit(scenario: Scenario) -> None:
    project = configuration.project_configuration(
        scenario.session, caller=scenario.caller(scenario.planner)
    )

    assert {item.company_id for item in project.windows} >= {scenario.company_a, scenario.company_b}
    assert project.can_edit is True
    assert project.parameters.adherence_target == 60.0


def test_the_portfolio_lists_each_project_with_its_parameters(scenario: Scenario) -> None:
    configuration.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=_form(adherence_target="45"),
        version=None,
    )

    rows = {row.project_id: row for row in configuration.portfolio_overview(scenario.session)}

    assert rows[scenario.project_id].parameters.adherence_target == 45.0
    assert rows[scenario.project_id].windows == 1
    assert rows[scenario.other_project_id].parameters.adherence_target == 60.0
    assert rows[scenario.other_project_id].windows == 0
