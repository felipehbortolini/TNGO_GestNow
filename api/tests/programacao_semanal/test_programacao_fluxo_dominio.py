"""Pure rules of the five-step flow: the deviation, the next action and the menu (ISSUE-052).

Ports of the app's tests of the next action (``test_dominio.py``) plus the boundaries of the
deviation that asks for a justification.
"""

from __future__ import annotations

import pytest

from src.core.errors import InvalidDataError
from src.modulos.programacao_semanal import calculations, flow
from src.modulos.programacao_semanal.flow import Rights, State

DRAFT = calculations.SITUATION_DRAFT
VALIDATED = calculations.SITUATION_VALIDATED
PUBLISHED = calculations.SITUATION_PUBLISHED
PENDING = calculations.APPROVAL_PENDING
APPROVED = calculations.APPROVAL_APPROVED

PLANNER = Rights(validate=True, publish=True, edit=True)
SUPPLIER = Rights(report=True, edit=True)
INSPECTOR = Rights(approve=True, edit=True)
VIEWER = Rights()
ADMIN = Rights(validate=True, report=True, approve=True, publish=True, edit=True, delete=True)


def _state(situation: str, approval: str, *, has_done: bool) -> State:
    return State(situation=situation, approval=approval, has_done=has_done)


# ── Deviation that asks for a justification ──────────────────────────────


@pytest.mark.parametrize(
    ("planned", "done", "expected"),
    [
        (100.0, 100.0, 0.0),
        (100.0, 115.0, 15.0),
        (100.0, 85.0, 15.0),
        (200.0, 100.0, 50.0),
        (0.0, 50.0, 0.0),
    ],
)
def test_deviation_is_the_distance_from_the_planned_in_percent(
    planned: float, done: float, expected: float
) -> None:
    assert calculations.deviation_percent(planned, done) == pytest.approx(expected)


def test_deviation_exactly_at_the_limit_needs_no_note() -> None:
    assert not calculations.needs_deviation_note(100.0, 115.0, limit=15.0, required=True)


def test_deviation_just_above_the_limit_needs_a_note_up_or_down() -> None:
    assert calculations.needs_deviation_note(100.0, 115.01, limit=15.0, required=True)
    assert calculations.needs_deviation_note(100.0, 84.9, limit=15.0, required=True)


def test_rule_switched_off_never_needs_a_note() -> None:
    assert not calculations.needs_deviation_note(100.0, 400.0, limit=15.0, required=False)


def test_activity_without_plan_never_needs_a_note() -> None:
    assert not calculations.needs_deviation_note(0.0, 40.0, limit=15.0, required=True)


# ── Next action: the button of the row ───────────────────────────────────


def test_inspector_sees_approve_where_the_supplier_sees_report() -> None:
    waiting = _state(VALIDATED, PENDING, has_done=True)

    assert flow.next_action(INSPECTOR, waiting) == flow.APPROVE
    assert flow.next_action(SUPPLIER, waiting) == flow.REPORT


def test_planner_validates_the_draft() -> None:
    assert flow.next_action(PLANNER, _state(DRAFT, PENDING, has_done=False)) == flow.VALIDATE


def test_viewer_only_views() -> None:
    for situation in (DRAFT, VALIDATED, PUBLISHED):
        for approval in (PENDING, APPROVED):
            assert flow.next_action(VIEWER, _state(situation, approval, has_done=True)) == flow.VIEW


def test_approved_done_turns_into_publish() -> None:
    approved = _state(VALIDATED, APPROVED, has_done=True)

    assert flow.next_action(PLANNER, approved) == flow.PUBLISH
    assert flow.next_action(ADMIN, approved) == flow.PUBLISH


def test_published_does_not_offer_publish_again() -> None:
    assert flow.next_action(PLANNER, _state(PUBLISHED, APPROVED, has_done=True)) == flow.VIEW


def test_admin_walks_the_queue_in_the_order_of_the_flow() -> None:
    steps = [
        (_state(DRAFT, PENDING, has_done=False), flow.VALIDATE),
        (_state(VALIDATED, PENDING, has_done=False), flow.REPORT),
        (_state(VALIDATED, PENDING, has_done=True), flow.APPROVE),
        (_state(VALIDATED, APPROVED, has_done=True), flow.PUBLISH),
        (_state(PUBLISHED, APPROVED, has_done=True), flow.VIEW),
    ]

    assert [flow.next_action(ADMIN, state) for state, _ in steps] == [step for _, step in steps]


# ── The menu: only what the profile may do, never the button twice ───────


def test_menu_never_repeats_the_step_of_the_button() -> None:
    for state in (
        _state(DRAFT, PENDING, has_done=False),
        _state(VALIDATED, PENDING, has_done=True),
        _state(VALIDATED, APPROVED, has_done=True),
    ):
        actions = flow.actions_of(ADMIN, state)
        assert actions.next_action not in actions.menu


def test_viewer_has_no_menu() -> None:
    actions = flow.actions_of(VIEWER, _state(VALIDATED, PENDING, has_done=True))

    assert actions == flow.Actions(next_action=flow.VIEW, menu=())


def test_menu_changes_with_the_profile() -> None:
    state = _state(VALIDATED, PENDING, has_done=True)

    assert flow.actions_of(SUPPLIER, state).menu == (flow.DETAIL, flow.EDIT)
    assert flow.actions_of(INSPECTOR, state).menu == (flow.DETAIL, flow.EDIT)
    assert flow.actions_of(PLANNER, state).menu == (flow.EDIT, flow.PUBLISH)


def test_approved_done_offers_reopen_to_the_inspector_only() -> None:
    approved = _state(VALIDATED, APPROVED, has_done=True)

    assert flow.REOPEN in flow.actions_of(INSPECTOR, approved).menu
    assert flow.REOPEN not in flow.actions_of(SUPPLIER, approved).menu
    assert flow.REOPEN not in flow.actions_of(PLANNER, approved).menu


def test_delete_stays_last_in_the_menu() -> None:
    menu = flow.actions_of(ADMIN, _state(DRAFT, PENDING, has_done=False)).menu

    assert menu[-1] == flow.DELETE


# ── The guards of each step ──────────────────────────────────────────────


def test_guards_refuse_a_step_out_of_place() -> None:
    with pytest.raises(InvalidDataError):
        flow.check_can_validate(VALIDATED)
    with pytest.raises(InvalidDataError):
        flow.check_can_report(DRAFT, PENDING)
    with pytest.raises(InvalidDataError):
        flow.check_can_report(VALIDATED, APPROVED)
    with pytest.raises(InvalidDataError):
        flow.check_can_approve(DRAFT, has_done=True)
    with pytest.raises(InvalidDataError):
        flow.check_can_approve(VALIDATED, has_done=False)
    with pytest.raises(InvalidDataError):
        flow.check_can_reopen(PENDING)
    with pytest.raises(InvalidDataError):
        flow.check_can_publish(DRAFT)


def test_guards_accept_the_step_in_its_place() -> None:
    flow.check_can_validate(DRAFT)
    flow.check_can_report(VALIDATED, PENDING)
    flow.check_can_approve(VALIDATED, has_done=True)
    flow.check_can_reopen(APPROVED)
    flow.check_can_publish(VALIDATED)
