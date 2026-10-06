"""Facade of the five-step flow: who may do each step, the guards and the numbers (D7, D10, ISSUE-052)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import select

from src.core import audit, calendario
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.core.rbac import ScheduleRole, User
from src.modulos.configuracoes.models import Company
from src.modulos.programacao_semanal import calculations, service, workflow
from src.modulos.programacao_semanal.models import Activity, ActivityDay
from src.modulos.programacao_semanal.service import NewActivity
from src.modulos.programacao_semanal.validation import DoneForm
from src.modulos.programacao_semanal.workflow import Validation
from tests.cenario_programacao import WEEK, Scenario, make_admin, make_user

DRAFT = calculations.SITUATION_DRAFT
VALIDATED = calculations.SITUATION_VALIDATED
PUBLISHED = calculations.SITUATION_PUBLISHED
PENDING = calculations.APPROVAL_PENDING
APPROVED = calculations.APPROVAL_APPROVED


@dataclass(frozen=True)
class Cast:
    """The people of the flow, one per role, besides the ones of the scenario."""

    inspector: User
    other_inspector: User
    foreman: User
    admin: User


@pytest.fixture
def cast(scenario: Scenario) -> Cast:
    session, project = scenario.session, scenario.project_id
    company = session.get(Company, scenario.company_a)
    return Cast(
        inspector=make_user(
            session,
            email="fl-fiscal@example.invalid",
            project_id=project,
            role=ScheduleRole.INSPECTOR,
        ),
        other_inspector=make_user(
            session,
            email="fl-fiscal2@example.invalid",
            project_id=project,
            role=ScheduleRole.INSPECTOR,
        ),
        foreman=make_user(
            session,
            email="fl-enc@example.invalid",
            project_id=project,
            role=ScheduleRole.FOREMAN,
            company=company,
        ),
        admin=make_admin(session, email="fl-admin@example.invalid"),
    )


def _store(
    scenario: Scenario,
    unique_id: str = "F-1",
    *,
    state: tuple[str, str] = (DRAFT, PENDING),
    inspector: User | None = None,
    amounts: tuple[float, float] = (10.0, 0.0),
) -> Activity:
    """An activity of company A: the (situation, approval) and the (planned, done) of each day."""
    situation, approval = state
    planned, done = amounts
    return service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=scenario.company_a,
            week=WEEK,
            unique_id=unique_id,
            item=1,
            description=f"Serviço {unique_id}",
            planned_headline=planned * 7,
            author_person_id=scenario.planner.person_id,
            at=calendario.now(),
            location_id=scenario.location_id,
            unit_id=scenario.unit_id,
            inspector_id=inspector.person_id if inspector else None,
            foreman_id=scenario.foreman_a,
            planned_days=(planned,) * 7,
            day_shift=(done,) * 7,
            situation=situation,
            approval=approval,
        ),
    )


def _version(activity: Activity) -> str:
    return str(activity.version)


def _validate(scenario: Scenario, user: User, activity: Activity, inspector: User | None):
    return workflow.validate_activity(
        scenario.session,
        caller=scenario.caller(user),
        activity_id=activity.id,
        sent=Validation(
            inspector_id=inspector.person_id if inspector else None,
            comments="",
            version=_version(activity),
        ),
    )


def _report(scenario: Scenario, user: User, activity: Activity, form: DoneForm):
    return workflow.report_done(
        scenario.session,
        caller=scenario.caller(user),
        activity_id=activity.id,
        form=form,
        version=_version(activity),
    )


def _approve(scenario: Scenario, user: User, activity: Activity):
    return workflow.approve_done(
        scenario.session,
        caller=scenario.caller(user),
        activity_id=activity.id,
        comments="",
        version=_version(activity),
    )


def _publish(scenario: Scenario, user: User, activity: Activity):
    return workflow.publish_activity(
        scenario.session,
        caller=scenario.caller(user),
        activity_id=activity.id,
        version=_version(activity),
    )


def _days(value: float) -> tuple[float, ...]:
    return (value,) * 7


# ── Validate ─────────────────────────────────────────────────────────────


def test_planner_validates_and_names_the_inspector(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario)

    _validate(scenario, scenario.planner, activity, cast.inspector)

    assert activity.situation == VALIDATED
    assert activity.inspector_id == cast.inspector.person_id


def test_validation_comment_carries_the_author_and_the_time(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario)

    workflow.validate_activity(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        activity_id=activity.id,
        sent=Validation(
            inspector_id=cast.inspector.person_id,
            comments="Conferir a frente",
            version=_version(activity),
        ),
    )

    assert activity.timenow_comments.startswith("[24/07 10:00 · ")
    assert activity.timenow_comments.endswith("Conferir a frente")


@pytest.mark.parametrize("who", ["supplier_a", "viewer"])
def test_only_the_planner_validates_scenario_roles(
    scenario: Scenario, cast: Cast, who: str
) -> None:
    activity = _store(scenario)

    with pytest.raises(AccessDeniedError):
        _validate(scenario, getattr(scenario, who), activity, cast.inspector)

    assert activity.situation == DRAFT


@pytest.mark.parametrize("who", ["inspector", "foreman"])
def test_only_the_planner_validates_flow_roles(scenario: Scenario, cast: Cast, who: str) -> None:
    activity = _store(scenario)

    with pytest.raises(AccessDeniedError):
        _validate(scenario, getattr(cast, who), activity, cast.inspector)


def test_admin_validates_in_any_project_role(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario)

    _validate(scenario, cast.admin, activity, cast.inspector)

    assert activity.situation == VALIDATED


def test_validation_needs_an_inspector_of_the_project(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario)

    with pytest.raises(InvalidDataError) as none_chosen:
        _validate(scenario, scenario.planner, activity, None)
    with pytest.raises(InvalidDataError) as not_inspector:
        _validate(scenario, scenario.planner, activity, cast.foreman)

    assert "responsavel" in none_chosen.value.detail
    assert "responsavel" in not_inspector.value.detail
    assert activity.situation == DRAFT


def test_only_a_draft_is_validated(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING))

    with pytest.raises(InvalidDataError):
        _validate(scenario, scenario.planner, activity, cast.inspector)


# ── Report the done ──────────────────────────────────────────────────────


def _done(day: float = 10.0, night: float = 0.0, note: str = "") -> DoneForm:
    return DoneForm(day_shift=_days(day), night_shift=_days(night), note=note)


def test_supplier_reports_the_two_shifts_and_the_numbers_follow(
    scenario: Scenario, cast: Cast
) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    _report(scenario, scenario.supplier_a, activity, _done(day=8.0, night=2.0))

    figures = service.activity_figures(scenario.session, activity)
    assert figures.done_total == 70.0
    assert figures.ppc == 100.0
    assert figures.band == calculations.BAND_HIGH
    assert activity.approval == PENDING


def test_foreman_reports_too(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    _report(scenario, cast.foreman, activity, _done())

    assert service.activity_figures(scenario.session, activity).done_total == 70.0


@pytest.mark.parametrize("who", ["planner", "viewer", "supplier_b"])
def test_other_profiles_do_not_report(scenario: Scenario, cast: Cast, who: str) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    with pytest.raises(AccessDeniedError):
        _report(scenario, getattr(scenario, who), activity, _done())


def test_inspector_does_not_report(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    with pytest.raises(AccessDeniedError):
        _report(scenario, cast.inspector, activity, _done())


def test_nothing_is_reported_before_the_validation_or_after_the_approval(
    scenario: Scenario, cast: Cast
) -> None:
    draft = _store(scenario, "F-1")
    approved = _store(
        scenario, "F-2", state=(VALIDATED, APPROVED), inspector=cast.inspector, amounts=(10.0, 10.0)
    )

    with pytest.raises(InvalidDataError):
        _report(scenario, scenario.supplier_a, draft, _done())
    with pytest.raises(InvalidDataError):
        _report(scenario, scenario.supplier_a, approved, _done(day=1.0))


def test_deviation_above_the_limit_without_justification_is_refused(
    scenario: Scenario, cast: Cast
) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    with pytest.raises(InvalidDataError) as refused:
        _report(scenario, scenario.supplier_a, activity, _done(day=5.0))

    assert "observacoes" in refused.value.detail
    assert service.activity_figures(scenario.session, activity).done_total == 0.0


def test_deviation_exactly_at_the_limit_is_accepted_without_justification(
    scenario: Scenario, cast: Cast
) -> None:
    activity = _store(
        scenario, state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(100.0, 0.0)
    )

    _report(scenario, scenario.supplier_a, activity, _done(day=115.0))

    assert service.activity_figures(scenario.session, activity).done_total == 805.0


def test_deviation_with_justification_is_accepted_and_kept(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    _report(scenario, scenario.supplier_a, activity, _done(day=5.0, note="Chuva na frente"))

    assert activity.supplier_notes == "Chuva na frente"


def test_the_rule_can_be_switched_off_in_the_project(scenario: Scenario, cast: Cast) -> None:
    service.store_settings(
        scenario.session,
        author_id=scenario.author_id,
        project_id=scenario.project_id,
        parameters=service.ScheduleParameters(requires_deviation_note=False),
    )
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    _report(scenario, scenario.supplier_a, activity, _done(day=1.0))

    assert service.activity_figures(scenario.session, activity).done_total == 7.0


def test_a_negative_quantity_is_refused(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)
    form = DoneForm(day_shift=(10.0, 10.0, 10.0, 10.0, 10.0, 10.0, -1.0), note="x")

    with pytest.raises(InvalidDataError) as refused:
        _report(scenario, scenario.supplier_a, activity, form)

    assert "dias_realizado" in refused.value.detail


def test_reporting_leaves_the_trail_of_the_days_and_checks_the_version(
    scenario: Scenario, cast: Cast
) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)
    stale = _version(activity)

    _report(scenario, scenario.supplier_a, activity, _done())

    day_lines = scenario.session.scalars(
        select(AuditEntry).where(AuditEntry.entity == ActivityDay.__tablename__)
    ).all()
    assert any(line.action == audit.UPDATED for line in day_lines)
    with pytest.raises(VersionConflictError):
        workflow.report_done(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=_done(day=11.0),
            version=stale,
        )


# ── Approve and reopen ───────────────────────────────────────────────────


def test_the_inspector_of_the_activity_approves_and_the_done_freezes(
    scenario: Scenario, cast: Cast
) -> None:
    activity = _store(
        scenario, state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(10.0, 10.0)
    )

    _approve(scenario, cast.inspector, activity)

    assert activity.approval == APPROVED
    assert activity.approved_by_id == cast.inspector.person_id
    assert activity.approved_at is not None
    with pytest.raises(InvalidDataError):
        _report(scenario, scenario.supplier_a, activity, _done(day=9.0))


@pytest.mark.parametrize("who", ["other_inspector", "foreman"])
def test_only_the_inspector_of_the_activity_approves(
    scenario: Scenario, cast: Cast, who: str
) -> None:
    activity = _store(
        scenario, state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(10.0, 10.0)
    )

    with pytest.raises(AccessDeniedError):
        _approve(scenario, getattr(cast, who), activity)

    assert activity.approval == PENDING


@pytest.mark.parametrize("who", ["planner", "supplier_a", "viewer"])
def test_the_other_profiles_do_not_approve(scenario: Scenario, cast: Cast, who: str) -> None:
    activity = _store(
        scenario, state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(10.0, 10.0)
    )

    with pytest.raises(AccessDeniedError):
        _approve(scenario, getattr(scenario, who), activity)


def test_admin_approves_any_activity(scenario: Scenario, cast: Cast) -> None:
    activity = _store(
        scenario, state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(10.0, 10.0)
    )

    _approve(scenario, cast.admin, activity)

    assert activity.approval == APPROVED


def test_approval_needs_a_validated_programming_with_done(scenario: Scenario, cast: Cast) -> None:
    draft = _store(scenario, "F-1", amounts=(10.0, 10.0), inspector=cast.inspector)
    empty = _store(scenario, "F-2", state=(VALIDATED, PENDING), inspector=cast.inspector)

    with pytest.raises(InvalidDataError):
        _approve(scenario, cast.inspector, draft)
    with pytest.raises(InvalidDataError):
        _approve(scenario, cast.inspector, empty)


def _reopen(scenario: Scenario, user: User, activity: Activity, reason: str):
    return workflow.reopen_done(
        scenario.session,
        caller=scenario.caller(user),
        activity_id=activity.id,
        reason=reason,
        version=_version(activity),
    )


def test_the_inspector_reopens_with_a_reason_and_the_supplier_reports_again(
    scenario: Scenario, cast: Cast
) -> None:
    activity = _store(
        scenario, state=(VALIDATED, APPROVED), inspector=cast.inspector, amounts=(10.0, 10.0)
    )

    _reopen(scenario, cast.inspector, activity, "Medição divergente")

    assert activity.approval == PENDING
    assert "Realizado reaberto: Medição divergente" in activity.timenow_comments
    _report(scenario, scenario.supplier_a, activity, _done(day=9.0, note="Ajuste"))


def test_reopening_needs_a_reason_an_approved_done_and_the_right_person(
    scenario: Scenario, cast: Cast
) -> None:
    approved = _store(
        scenario, "F-1", state=(VALIDATED, APPROVED), inspector=cast.inspector, amounts=(10.0, 10.0)
    )
    pending = _store(
        scenario, "F-2", state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(10.0, 10.0)
    )

    with pytest.raises(InvalidDataError) as no_reason:
        _reopen(scenario, cast.inspector, approved, "")
    with pytest.raises(InvalidDataError):
        _reopen(scenario, cast.inspector, pending, "Motivo")
    with pytest.raises(AccessDeniedError):
        _reopen(scenario, scenario.planner, approved, "Motivo")
    with pytest.raises(AccessDeniedError):
        _reopen(scenario, cast.other_inspector, approved, "Motivo")

    assert "motivo" in no_reason.value.detail
    assert approved.approval == APPROVED


# ── Publish ──────────────────────────────────────────────────────────────


def test_planner_publishes_the_validated_programming_and_the_edition_ends(
    scenario: Scenario, cast: Cast
) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    _publish(scenario, scenario.planner, activity)

    assert activity.situation == PUBLISHED
    assert activity.published_at is not None
    with pytest.raises(AccessDeniedError):
        service.update_activity(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=service.form_of(
                service.get_activity(
                    scenario.session,
                    caller=scenario.caller(scenario.planner),
                    activity_id=activity.id,
                )
            ),
            version=_version(activity),
        )


@pytest.mark.parametrize("who", ["supplier_a", "viewer"])
def test_only_the_planner_publishes(scenario: Scenario, cast: Cast, who: str) -> None:
    activity = _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector)

    with pytest.raises(AccessDeniedError):
        _publish(scenario, getattr(scenario, who), activity)
    with pytest.raises(AccessDeniedError):
        _publish(scenario, cast.inspector, activity)


def test_only_a_validated_programming_is_published(scenario: Scenario, cast: Cast) -> None:
    draft = _store(scenario, "F-1")
    published = _store(scenario, "F-2", state=(PUBLISHED, APPROVED), inspector=cast.inspector)

    with pytest.raises(InvalidDataError):
        _publish(scenario, scenario.planner, draft)
    with pytest.raises(InvalidDataError):
        _publish(scenario, scenario.planner, published)


def test_publishing_the_week_takes_only_the_validated_ones(scenario: Scenario, cast: Cast) -> None:
    draft = _store(scenario, "F-1")
    first = _store(scenario, "F-2", state=(VALIDATED, PENDING), inspector=cast.inspector)
    second = _store(scenario, "F-3", state=(VALIDATED, PENDING), inspector=cast.inspector)

    count = workflow.publish_week(
        scenario.session, caller=scenario.caller(scenario.planner), week=WEEK
    )

    assert count == 2
    assert (draft.situation, first.situation, second.situation) == (DRAFT, PUBLISHED, PUBLISHED)
    with pytest.raises(AccessDeniedError):
        workflow.publish_week(
            scenario.session, caller=scenario.caller(scenario.supplier_a), week=WEEK
        )


def test_every_step_leaves_the_trail_with_before_and_after(scenario: Scenario, cast: Cast) -> None:
    activity = _store(scenario)

    _validate(scenario, scenario.planner, activity, cast.inspector)

    line = scenario.session.scalars(
        select(AuditEntry)
        .where(AuditEntry.entity == Activity.__tablename__, AuditEntry.record_id == activity.id)
        .where(AuditEntry.action == audit.UPDATED)
    ).one()
    assert line.before["situacao"] == DRAFT
    assert line.after["situacao"] == VALIDATED


# ── The button and the menu change with the profile; the numbers of the week ─


def _actions_for(scenario: Scenario, user: User) -> tuple[str, tuple[str, ...]]:
    views = service.list_activities(scenario.session, caller=scenario.caller(user), week=WEEK)
    actions = views[0].actions
    return actions.next_action, actions.menu


def test_the_button_and_the_menu_change_with_the_profile(scenario: Scenario, cast: Cast) -> None:
    _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(10.0, 10.0))

    assert _actions_for(scenario, scenario.supplier_a)[0] == "lancar"
    assert _actions_for(scenario, cast.inspector)[0] == "aprovar"
    assert _actions_for(scenario, cast.other_inspector)[0] == "ver"
    assert _actions_for(scenario, scenario.planner)[0] == "ver"
    assert _actions_for(scenario, scenario.planner)[1] == ("editar", "publicar")
    assert _actions_for(scenario, scenario.viewer) == ("ver", ())


def test_the_portfolio_offers_only_to_look(scenario: Scenario, cast: Cast) -> None:
    _store(scenario, state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(10.0, 10.0))

    views = service.list_activities(
        scenario.session, caller=scenario.caller(scenario.planner, project=False), week=WEEK
    )

    assert views[0].actions.next_action == "ver"
    assert views[0].actions.menu == ()


def test_ppc_per_activity_and_the_weighted_adherence_of_the_set(
    scenario: Scenario, cast: Cast
) -> None:
    _store(
        scenario, "F-1", state=(VALIDATED, PENDING), inspector=cast.inspector, amounts=(100.0, 50.0)
    )
    _store(
        scenario,
        "F-2",
        state=(VALIDATED, PENDING),
        inspector=cast.inspector,
        amounts=(300.0, 270.0),
    )

    views = service.list_activities(
        scenario.session, caller=scenario.caller(scenario.planner), week=WEEK
    )
    summary = service.week_summary(views)

    by_id = {view.unique_id: view.figures for view in views}
    assert by_id["F-1"].ppc == 50.0
    assert by_id["F-1"].band == calculations.BAND_LOW
    assert by_id["F-2"].ppc == 90.0
    assert by_id["F-2"].band == calculations.BAND_HIGH
    assert summary.adherence == 80.0
    assert summary.mean_ppc == 70.0
