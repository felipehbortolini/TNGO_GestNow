"""Facade of the matrix: the cut by company, the window, the Portfólio and the writes (D7, D8, D10)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import func, select

from src.core import calendario
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.core.scope import Scope
from src.modulos.programacao_semanal import service
from src.modulos.programacao_semanal.models import Activity, ActivityDay
from src.modulos.programacao_semanal.service import NewActivity
from src.modulos.programacao_semanal.validation import ActivityForm
from tests.cenario_programacao import SATURDAY_MORNING, WEEK, Scenario


def _store(scenario: Scenario, company_id: int, unique_id: str, foreman_id: int) -> Activity:
    return service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=company_id,
            week=WEEK,
            unique_id=unique_id,
            item=1,
            description=f"Serviço {unique_id}",
            planned_headline=70.0,
            author_person_id=scenario.planner.person_id,
            at=calendario.now(),
            location_id=scenario.location_id,
            unit_id=scenario.unit_id,
            foreman_id=foreman_id,
            planned_days=(10.0,) * 7,
            day_shift=(5.0,) * 7,
        ),
    )


def _form(scenario: Scenario, *, company_id: int | None, foreman_id: int, unique_id: str = "N-1"):
    return ActivityForm(
        week=WEEK,
        unique_id=unique_id,
        description="Nova atividade",
        location_id=scenario.location_id,
        company_id=company_id,
        foreman_id=foreman_id,
        unit_id=scenario.unit_id,
        headline=70.0,
        planned_days=(10.0,) * 7,
    )


# ── The supplier sees and writes only its own company ───────────────────


def test_supplier_lists_only_its_own_company(scenario: Scenario) -> None:
    _store(scenario, scenario.company_a, "A-1", scenario.foreman_a)
    _store(scenario, scenario.company_b, "B-1", scenario.foreman_b)

    own = service.list_activities(
        scenario.session, caller=scenario.caller(scenario.supplier_a), week=WEEK
    )
    everyone = service.list_activities(
        scenario.session, caller=scenario.caller(scenario.planner), week=WEEK
    )

    assert [view.unique_id for view in own] == ["A-1"]
    assert sorted(view.unique_id for view in everyone) == ["A-1", "B-1"]


def test_supplier_opening_another_company_activity_is_403(scenario: Scenario) -> None:
    other = _store(scenario, scenario.company_b, "B-1", scenario.foreman_b)

    with pytest.raises(AccessDeniedError):
        service.get_activity(
            scenario.session, caller=scenario.caller(scenario.supplier_a), activity_id=other.id
        )


def test_supplier_writing_for_another_company_is_403(scenario: Scenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.create_activity(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            form=_form(scenario, company_id=scenario.company_b, foreman_id=scenario.foreman_a),
        )


def test_supplier_cannot_edit_or_delete_another_company_activity(scenario: Scenario) -> None:
    other = _store(scenario, scenario.company_b, "B-1", scenario.foreman_b)
    caller = scenario.caller(scenario.supplier_a)

    with pytest.raises(AccessDeniedError):
        service.update_activity(
            scenario.session,
            caller=caller,
            activity_id=other.id,
            form=_form(scenario, company_id=None, foreman_id=scenario.foreman_a),
            version=str(other.version),
        )
    with pytest.raises(AccessDeniedError):
        service.delete_activity(
            scenario.session, caller=caller, activity_id=other.id, version=str(other.version)
        )


def test_supplier_without_a_company_is_refused_instead_of_seeing_everything(
    scenario: Scenario,
) -> None:
    broken = replace(scenario.supplier_a, company_id=None)
    with pytest.raises(AccessDeniedError):
        service.list_activities(scenario.session, caller=scenario.caller(broken), week=WEEK)


def test_supplier_form_options_hold_only_its_own_company_and_foremen(scenario: Scenario) -> None:
    options = service.form_options(
        scenario.session, user=scenario.supplier_a, project_id=scenario.project_id
    )

    assert [option.id for option in options.companies] == [scenario.company_a]
    assert [option.id for option in options.foremen] == [scenario.foreman_a]


# ── The window binds the supplier, not the Timenow team ─────────────────


def test_supplier_creates_inside_the_window_with_its_own_company(scenario: Scenario) -> None:
    created = service.create_activity(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a),
        form=_form(scenario, company_id=None, foreman_id=scenario.foreman_a),
    )

    assert created.company_id == scenario.company_a
    days = scenario.session.scalars(
        select(ActivityDay).where(ActivityDay.activity_id == created.id)
    ).all()
    assert len(days) == 7


def test_programming_outside_the_window_is_refused_with_the_reason(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.supplier_a, now=SATURDAY_MORNING)

    with pytest.raises(AccessDeniedError) as refused:
        service.create_activity(
            scenario.session,
            caller=caller,
            form=_form(scenario, company_id=None, foreman_id=scenario.foreman_a),
        )

    assert "Hoje não é dia de programar" in str(refused.value)


def test_supplier_without_a_window_is_refused(scenario: Scenario) -> None:
    with pytest.raises(AccessDeniedError) as refused:
        service.create_activity(
            scenario.session,
            caller=scenario.caller(scenario.supplier_b),
            form=_form(scenario, company_id=None, foreman_id=scenario.foreman_b),
        )

    assert "sem janela" in str(refused.value).lower()


def test_planner_writes_outside_the_window(scenario: Scenario) -> None:
    created = service.create_activity(
        scenario.session,
        caller=scenario.caller(scenario.planner, now=SATURDAY_MORNING),
        form=_form(scenario, company_id=scenario.company_b, foreman_id=scenario.foreman_b),
    )

    assert created.company_id == scenario.company_b


def test_window_status_tells_the_supplier_whether_it_may_start(scenario: Scenario) -> None:
    opened = service.window_status(
        scenario.session, caller=scenario.caller(scenario.supplier_a), week=WEEK
    )
    closed = service.window_status(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a, now=SATURDAY_MORNING),
        week=WEEK,
    )

    assert opened.is_supplier
    assert opened.is_open
    assert opened.can_create
    assert not closed.is_open
    assert not closed.can_create


def test_viewer_cannot_create(scenario: Scenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.create_activity(
            scenario.session,
            caller=scenario.caller(scenario.viewer),
            form=_form(scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a),
        )


# ── The Portfólio is read-only and asks for a project ───────────────────


def test_portfolio_matrix_is_read_only_and_asks_for_a_project(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner, project=False)

    status = service.window_status(scenario.session, caller=caller, week=WEEK)
    with pytest.raises(InvalidDataError) as refused:
        service.create_activity(
            scenario.session,
            caller=caller,
            form=_form(scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a),
        )

    assert status.is_portfolio
    assert not status.can_create
    assert "projeto" in str(refused.value)


def test_portfolio_reads_the_activities_of_every_project(scenario: Scenario) -> None:
    _store(scenario, scenario.company_a, "A-1", scenario.foreman_a)

    seen = service.list_activities(
        scenario.session, caller=scenario.caller(scenario.planner, project=False), week=WEEK
    )

    assert [view.unique_id for view in seen] == ["A-1"]


def test_another_project_activity_is_not_found(scenario: Scenario) -> None:
    activity = _store(scenario, scenario.company_a, "A-1", scenario.foreman_a)
    other = service.Caller(
        user=scenario.planner,
        scope=Scope(project_id=scenario.other_project_id, source="url"),
        now=calendario.now(),
    )

    with pytest.raises(InvalidDataError):
        service.get_activity(scenario.session, caller=other, activity_id=activity.id)


# ── Validation, versions and the trail ──────────────────────────────────


def test_days_that_do_not_add_up_are_422_with_a_message_per_field(scenario: Scenario) -> None:
    form = _form(scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a)
    broken = ActivityForm(**{**form.__dict__, "headline": 100.0, "unique_id": ""})

    with pytest.raises(InvalidDataError) as refused:
        service.create_activity(
            scenario.session, caller=scenario.caller(scenario.planner), form=broken
        )

    assert set(refused.value.detail) >= {"id_exclusiva", "dias_previsto"}


def test_the_sum_of_the_days_has_a_tolerance_of_half_a_unit(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)
    form = _form(scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a)

    inside = ActivityForm(**{**form.__dict__, "headline": 70.5, "unique_id": "T-1"})
    outside = ActivityForm(**{**form.__dict__, "headline": 70.6, "unique_id": "T-2"})

    assert service.create_activity(scenario.session, caller=caller, form=inside).id
    with pytest.raises(InvalidDataError):
        service.create_activity(scenario.session, caller=caller, form=outside)


def test_unique_id_cannot_repeat_in_the_week(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)
    form = _form(scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a)
    service.create_activity(scenario.session, caller=caller, form=form)

    with pytest.raises(InvalidDataError) as refused:
        service.create_activity(scenario.session, caller=caller, form=form)

    assert "id_exclusiva" in refused.value.detail


def test_items_follow_the_order_of_entry_in_the_week(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)
    first = service.create_activity(
        scenario.session,
        caller=caller,
        form=_form(scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a),
    )
    second = service.create_activity(
        scenario.session,
        caller=caller,
        form=_form(
            scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a, unique_id="N-2"
        ),
    )

    assert (first.item, second.item) == (1, 2)


def test_update_checks_the_version_the_screen_opened(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)
    created = service.create_activity(
        scenario.session,
        caller=caller,
        form=_form(scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a),
    )
    changed = _form(
        scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a, unique_id="N-1"
    )
    changed = ActivityForm(**{**changed.__dict__, "description": "Descrição nova"})

    service.update_activity(
        scenario.session,
        caller=caller,
        activity_id=created.id,
        form=changed,
        version=str(created.version),
    )

    with pytest.raises(VersionConflictError):
        service.update_activity(
            scenario.session, caller=caller, activity_id=created.id, form=changed, version="1"
        )


def test_every_write_leaves_the_trail(scenario: Scenario) -> None:
    caller = scenario.caller(scenario.planner)
    before = scenario.session.scalar(select(func.count()).select_from(AuditEntry))

    created = service.create_activity(
        scenario.session,
        caller=caller,
        form=_form(scenario, company_id=scenario.company_a, foreman_id=scenario.foreman_a),
    )

    after = scenario.session.scalar(select(func.count()).select_from(AuditEntry))
    assert created.id
    assert after >= before + 8


def test_only_the_admin_deletes(scenario: Scenario) -> None:
    activity = _store(scenario, scenario.company_a, "A-1", scenario.foreman_a)

    with pytest.raises(AccessDeniedError):
        service.delete_activity(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            activity_id=activity.id,
            version=str(activity.version),
        )


def test_filters_and_the_strip_of_the_week(scenario: Scenario) -> None:
    _store(scenario, scenario.company_a, "A-1", scenario.foreman_a)
    _store(scenario, scenario.company_b, "B-1", scenario.foreman_b)
    caller = scenario.caller(scenario.planner)

    filtered = service.list_activities(
        scenario.session,
        caller=caller,
        week=WEEK,
        filters=service.parse_filters({"empresa": str(scenario.company_b)}),
    )
    summary = service.week_summary(
        service.list_activities(scenario.session, caller=caller, week=WEEK)
    )

    assert [view.unique_id for view in filtered] == ["B-1"]
    assert summary.total == 2
    assert summary.adherence == pytest.approx(50.0)
    assert summary.awaiting_inspector == 2
