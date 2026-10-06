"""Facade of the five-step flow: validate, report the done, approve, reopen and publish (D10, D7).

Every step is a write of the activity through ``core.recording`` (trail, version and
transaction together) and every step has its owner, decided here and never on the screen:

* **validate** (planner): drafting becomes validated and the inspector is named;
* **report the done** (foreman or supplier): the two shifts of the seven days; a deviation
  above the project's limit asks for a justification, as the app does;
* **approve** or **reopen** (the inspector of the activity): the done freezes, or goes back
  to the reporting with a reason;
* **publish** (planner): the validated programming is closed for editing.

The wrong role is 403 before any state is looked at; a step out of its place in the flow is
422 with the message of the app. Nothing here reads the clock: the instant comes in the ``Caller``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy.orm import Session

from src.core import calendario, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.modulos.configuracoes.registers import Option
from src.modulos.programacao_semanal import calculations, flow, permissions, service
from src.modulos.programacao_semanal.models import Activity
from src.modulos.programacao_semanal.service import Caller
from src.modulos.programacao_semanal.validation import DoneForm, done_errors
from src.modulos.programacao_semanal.views import ActivityView

INSPECTOR_REQUIRED = "Escolha um fiscal — a lista vem dos colaboradores com esse papel."
NOTHING_TO_PUBLISH = "Nenhuma programação validada aguardando publicação."
COMMENT_STAMP = "%d/%m %H:%M"


@dataclass(frozen=True)
class ValidationScreen:
    """What the drawer of the validation shows: the activity and the inspectors to choose from."""

    view: ActivityView
    inspectors: list[Option]


@dataclass(frozen=True)
class ReportScreen:
    """What the drawer of the done shows: the activity (with what was typed) and the deviation rule."""

    view: ActivityView
    parameters: service.ScheduleParameters


def _comment(activity: Activity, text: str, *, caller: Caller) -> str:
    """The comments of the Timenow team with one more line: ``[24/07 10:00 · Nome] texto``."""
    stamp = calendario.in_product_timezone(caller.now).strftime(COMMENT_STAMP)
    line = f"[{stamp} · {caller.user.name}] {text}"
    return f"{activity.timenow_comments or ''}\n{line}".strip()


def _touch(caller: Caller) -> dict[str, Any]:
    """The fields every step moves: who changed it and when."""
    return {"updated_by_id": caller.user.person_id, "updated_at": caller.now}


def _apply(
    session: Session,
    *,
    caller: Caller,
    activity: Activity,
    changes: dict[str, Any],
    version: str | None,
) -> Activity:
    recording.update(
        session,
        user_id=caller.user.id,
        record=activity,
        changes={**changes, **_touch(caller)},
        version=version,
    )
    return activity


def _view_of(session: Session, *, caller: Caller, activity: Activity) -> ActivityView:
    return service.get_activity(session, caller=caller, activity_id=activity.id)


# ── Validate ─────────────────────────────────────────────────────────────


def open_validation(session: Session, *, caller: Caller, activity_id: int) -> ValidationScreen:
    """The drawer of the validation: 403 unless the user is the planner (or the Admin) of the project."""
    project_id = caller.scope.require_project()
    activity = service.load_activity(session, caller=caller, activity_id=activity_id)
    if not permissions.can_validate(caller.user, project_id):
        raise AccessDeniedError(permissions.VALIDATE_DENIED)
    options = service.form_options(session, user=caller.user, project_id=project_id)
    return ValidationScreen(
        view=_view_of(session, caller=caller, activity=activity), inspectors=options.inspectors
    )


@dataclass(frozen=True)
class Validation:
    """What the planner sent: the inspector chosen, the comments to the supplier and the version."""

    inspector_id: int | None
    comments: str
    version: str | None


def validate_activity(
    session: Session, *, caller: Caller, activity_id: int, sent: Validation
) -> Activity:
    """Validate the programming and name the inspector, who then approves the done (HU-73)."""
    project_id = caller.scope.require_project()
    activity = service.load_activity(session, caller=caller, activity_id=activity_id)
    if not permissions.can_validate(caller.user, project_id):
        raise AccessDeniedError(permissions.VALIDATE_DENIED)
    flow.check_can_validate(activity.situation)
    options = service.form_options(session, user=caller.user, project_id=project_id)
    if sent.inspector_id is None or all(
        option.id != sent.inspector_id for option in options.inspectors
    ):
        raise InvalidDataError({"responsavel": INSPECTOR_REQUIRED})
    changes: dict[str, Any] = {
        "situation": calculations.SITUATION_VALIDATED,
        "inspector_id": sent.inspector_id,
    }
    if sent.comments:
        changes["timenow_comments"] = _comment(activity, sent.comments, caller=caller)
    return _apply(session, caller=caller, activity=activity, changes=changes, version=sent.version)


# ── Report the done ──────────────────────────────────────────────────────


def open_report(
    session: Session, *, caller: Caller, activity_id: int, typed: DoneForm | None = None
) -> ReportScreen:
    """The drawer of the done; ``typed`` refills it after a 422. 403 unless foreman, supplier or Admin."""
    project_id = caller.scope.require_project()
    activity = service.load_activity(session, caller=caller, activity_id=activity_id)
    if not permissions.can_report(caller.user, project_id):
        raise AccessDeniedError(permissions.REPORT_DENIED)
    view = _view_of(session, caller=caller, activity=activity)
    if typed is not None:
        view = _with_typed_done(view, typed)
    return ReportScreen(view=view, parameters=service.parameters_of(session, project_id))


def _with_typed_done(view: ActivityView, typed: DoneForm) -> ActivityView:
    """The view with the numbers the person typed, to draw the drawer again after an error."""
    figures = calculations.figures_of(
        view.figures.planned_days,
        typed.day_shift,
        typed.night_shift,
        headline=view.planned_headline,
    )
    return replace(view, figures=figures, notes=typed.note)


def report_done(
    session: Session,
    *,
    caller: Caller,
    activity_id: int,
    form: DoneForm,
    version: str | None,
) -> Activity:
    """Record the done of the two shifts; a big deviation needs its justification (HU-74)."""
    project_id = caller.scope.require_project()
    activity = service.load_activity(session, caller=caller, activity_id=activity_id)
    if not permissions.can_report(caller.user, project_id):
        raise AccessDeniedError(permissions.REPORT_DENIED)
    flow.check_can_report(activity.situation, activity.approval)
    errors = done_errors(form)
    if errors:
        raise InvalidDataError(errors)

    stored = service.activity_figures(session, activity)
    figures = calculations.figures_of(
        stored.planned_days,
        form.day_shift,
        form.night_shift,
        headline=activity.planned_headline,
    )
    parameters = service.parameters_of(session, project_id)
    needs_note = calculations.needs_deviation_note(
        figures.planned_total,
        figures.done_total,
        limit=parameters.deviation_limit,
        required=parameters.requires_deviation_note,
    )
    if needs_note and not form.note:
        deviation = calculations.deviation_percent(figures.planned_total, figures.done_total)
        raise InvalidDataError(
            {
                "observacoes": (
                    f"O realizado está {deviation:.0f}% distante do previsto "
                    f"(limite de {parameters.deviation_limit:g}%). Explique o desvio para salvar."
                )
            }
        )

    changes: dict[str, Any] = {"supplier_notes": form.note} if form.note else {}
    _apply(session, caller=caller, activity=activity, changes=changes, version=version)
    service.change_done_days(
        session,
        user_id=caller.user.id,
        activity=activity,
        day_shift=form.day_shift,
        night_shift=form.night_shift,
    )
    return activity


# ── Approve and reopen ───────────────────────────────────────────────────


def open_approval(session: Session, *, caller: Caller, activity_id: int) -> ActivityView:
    """The drawer of the approval: the done day by day, for the inspector of the activity (or the Admin)."""
    project_id = caller.scope.require_project()
    activity = service.load_activity(session, caller=caller, activity_id=activity_id)
    if not permissions.can_approve(caller.user, project_id, activity.inspector_id):
        raise AccessDeniedError(permissions.APPROVE_DENIED)
    return _view_of(session, caller=caller, activity=activity)


def approve_done(
    session: Session, *, caller: Caller, activity_id: int, comments: str, version: str | None
) -> Activity:
    """Approve the done: it freezes for the supplier (HU-75)."""
    project_id = caller.scope.require_project()
    activity = service.load_activity(session, caller=caller, activity_id=activity_id)
    if not permissions.can_approve(caller.user, project_id, activity.inspector_id):
        raise AccessDeniedError(permissions.APPROVE_DENIED)
    stored = service.activity_figures(session, activity)
    flow.check_can_approve(activity.situation, has_done=stored.has_done)
    changes: dict[str, Any] = {
        "approval": calculations.APPROVAL_APPROVED,
        "approved_by_id": caller.user.person_id,
        "approved_at": caller.now,
    }
    if comments:
        changes["timenow_comments"] = _comment(activity, comments, caller=caller)
    return _apply(session, caller=caller, activity=activity, changes=changes, version=version)


def reopen_done(
    session: Session, *, caller: Caller, activity_id: int, reason: str, version: str | None
) -> Activity:
    """Take the approval back, with the reason written in the comments (HU-75)."""
    project_id = caller.scope.require_project()
    activity = service.load_activity(session, caller=caller, activity_id=activity_id)
    if not permissions.can_approve(caller.user, project_id, activity.inspector_id):
        raise AccessDeniedError(permissions.REOPEN_DENIED)
    if not reason:
        raise InvalidDataError({"motivo": flow.REOPEN_NEEDS_REASON})
    flow.check_can_reopen(activity.approval)
    changes: dict[str, Any] = {
        "approval": calculations.APPROVAL_PENDING,
        "timenow_comments": _comment(activity, f"Realizado reaberto: {reason}", caller=caller),
    }
    return _apply(session, caller=caller, activity=activity, changes=changes, version=version)


# ── Publish ──────────────────────────────────────────────────────────────


def publish_activity(
    session: Session, *, caller: Caller, activity_id: int, version: str | None
) -> Activity:
    """Publish a validated programming: the edition of the activity ends (HU-76)."""
    project_id = caller.scope.require_project()
    activity = service.load_activity(session, caller=caller, activity_id=activity_id)
    if not permissions.can_publish(caller.user, project_id):
        raise AccessDeniedError(permissions.PUBLISH_DENIED)
    flow.check_can_publish(activity.situation)
    changes = {"situation": calculations.SITUATION_PUBLISHED, "published_at": caller.now}
    return _apply(session, caller=caller, activity=activity, changes=changes, version=version)


def publish_week(session: Session, *, caller: Caller, week: str) -> int:
    """Publish every validated activity of the week in one action; the count says how many went."""
    project_id = caller.scope.require_project()
    if not permissions.can_publish(caller.user, project_id):
        raise AccessDeniedError(permissions.PUBLISH_DENIED)
    published = 0
    for view in service.list_activities(session, caller=caller, week=week):
        if view.situation != calculations.SITUATION_VALIDATED:
            continue
        publish_activity(session, caller=caller, activity_id=view.id, version=str(view.version))
        published += 1
    return published
