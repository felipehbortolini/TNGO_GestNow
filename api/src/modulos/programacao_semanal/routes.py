"""Route blueprint of the Weekly scheduling: the matrix of the week and the activity (D10).

Every route declares its ``Access`` (the module, so a supplier reaches it and a bond
without the module does not), resolves the scope and hands the facade a ``Caller``. The
cut by company, the window and the project are decided in ``service``, never here.

Targets of the screen (fixed ids, a multi-target answer): ``prog-janela`` (banner of the
window), ``prog-filtros`` (toolbar), ``prog-resumo`` (strip) and ``prog-tabela`` (matrix);
``drawer`` is the panel of the form.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario
from src.core.errors import InvalidDataError, VersionConflictError
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, fragment_route
from src.modulos.programacao_semanal import screen, service, validation, workflow
from src.modulos.programacao_semanal.models import Activity
from src.modulos.programacao_semanal.service import Caller
from src.modulos.programacao_semanal.validation import ActivityForm

bp = func.Blueprint()

ACCESS = Access(module="programacao_semanal")
TEMPLATE_DIR = "programacao_semanal"
SAVED_NEW = "Atividade criada."
SAVED_EDIT = "Atividade salva."
DELETED = "Atividade excluída."
GENERAL_ERROR = "_"
VALIDATED = "Programação de {id} validada."
DONE_SAVED = "Realizado de {id} registrado — PPC de {ppc:.0f}%."
APPROVED = "Realizado de {id} aprovado."
REOPENED = "Realizado de {id} reaberto."
PUBLISHED = "{id} publicada."
WEEK_PUBLISHED = "{count} programação(ões) publicada(s)."
CONFLICT_HINT = " Feche o painel e abra a atividade de novo para ver a versão salva."


def _caller(context: RequestContext) -> Caller:
    """The facade's view of the request: who, in which scope, at which instant."""
    return Caller(user=context.user, scope=context.scope, now=calendario.now())


def _body(req: func.HttpRequest) -> dict[str, str]:
    """The fields of a submitted form, as the plain text they were typed."""
    return {name: str(value) for name, value in req.form.items()}


@dataclass(frozen=True)
class _Answer:
    """How a route answers with the matrix: the template, the week it redraws and the toast."""

    template: str
    params: Mapping[str, str | None] | None = None
    toast: str | None = None


def _page(
    req: func.HttpRequest, context: RequestContext, session: Session, answer: _Answer
) -> func.HttpResponse:
    """The strip and the matrix of the week, with whatever else the answer carries."""
    data = screen.matrix_context(
        session,
        caller=_caller(context),
        params=req.params if answer.params is None else answer.params,
    )
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/{answer.template}",
        context=data,
        request=req,
        toast=answer.toast,
    )


@bp.route(route="programacao-semanal/programacoes", methods=["GET"])
@fragment_route(access=ACCESS)
def matrix(req: func.HttpRequest, session: Session, context: RequestContext) -> func.HttpResponse:
    """The strip of indicators and the matrix of the week, with its filters and order."""
    return _page(req, context, session, _Answer("matriz.html"))


@bp.route(route="programacao-semanal/programacoes/filtros", methods=["GET"])
@fragment_route(access=ACCESS)
def toolbar(req: func.HttpRequest, session: Session, context: RequestContext) -> func.HttpResponse:
    """The toolbar: week selector, search and the refinement panel."""
    data = screen.filters_context(session, caller=_caller(context), params=req.params)
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/filtros.html", context=data, request=req
    )


@bp.route(route="programacao-semanal/programacoes/janela", methods=["GET"])
@fragment_route(access=ACCESS)
def window_banner(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The banner of the window: who it binds, whether it is open and why."""
    data = screen.banner_context(session, caller=_caller(context), params=req.params)
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/janela.html", context=data, request=req
    )


@bp.route(route="programacao-semanal/atividades/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def activity_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The drawer of a new activity (``semana``) or of an existing one (``atividade``)."""
    caller = _caller(context)
    week = service.resolve_week(session, caller=caller, raw=req.params.get("semana"))
    opened = service.open_form(
        session,
        caller=caller,
        activity_id=validation.parse_id(req.params.get("atividade")),
        week=week,
    )
    data = screen.form_context(caller=caller, screen=opened)
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/formulario.html", context=data, request=req
    )


@dataclass(frozen=True)
class _Submitted:
    """What came in the form of a save: the typed values, which activity and the version."""

    form: ActivityForm
    activity_id: int | None
    version: str


def _form_with_errors(
    session: Session,
    req: func.HttpRequest,
    context: RequestContext,
    error: InvalidDataError | VersionConflictError,
    submitted: _Submitted,
) -> func.HttpResponse:
    """The drawer again, with what the person typed and the message next to the fields.

    Both errors are raised by the facade before any write, so the transaction holds nothing to undo.
    """
    caller = _caller(context)
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        errors = dict(error.detail)
    else:
        text = str(error) + (CONFLICT_HINT if isinstance(error, VersionConflictError) else "")
        errors = {GENERAL_ERROR: text}
    opened = service.open_form(
        session,
        caller=caller,
        activity_id=submitted.activity_id,
        week=submitted.form.week,
        typed=submitted.form,
    )
    data = screen.form_context(
        caller=caller, screen=opened, errors=errors, version=submitted.version
    )
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/formulario.html",
        context=data,
        request=req,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=next(iter(errors.values()), None),
        toast_tipo="erro",
    )


def _reopenable(error: InvalidDataError | VersionConflictError) -> bool:
    """Whether the drawer can be drawn again: field errors and conflicts, not a plain message."""
    return isinstance(error, VersionConflictError) or isinstance(error.detail, Mapping)


@bp.route(route="programacao-semanal/atividades", methods=["POST"])
@fragment_route(access=ACCESS)
def save_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create (no ``atividade_id``) or change an activity; 422/409 give the form back filled."""
    caller = _caller(context)
    values = _body(req)
    form = validation.parse_form(values)
    activity_id = validation.parse_id(values.get("atividade_id"))
    version = values.get("versao") or ""
    try:
        if activity_id is None:
            service.create_activity(session, caller=caller, form=form)
        else:
            service.update_activity(
                session, caller=caller, activity_id=activity_id, form=form, version=version
            )
    except (InvalidDataError, VersionConflictError) as error:
        if not _reopenable(error):
            raise
        return _form_with_errors(
            session, req, context, error, _Submitted(form, activity_id, version)
        )
    toast = SAVED_NEW if activity_id is None else SAVED_EDIT
    answer = _Answer("salvo.html", params={"semana": form.week}, toast=toast)
    return _page(req, context, session, answer)


@bp.route(route="programacao-semanal/atividades/excluir", methods=["POST"])
@fragment_route(access=ACCESS)
def delete_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Delete an activity (Admin only) and redraw the strip and the matrix."""
    values = {**_body(req), **req.params}
    activity_id = validation.parse_id(values.get("atividade"))
    if activity_id is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    service.delete_activity(
        session,
        caller=_caller(context),
        activity_id=activity_id,
        version=values.get("versao") or None,
    )
    return _page(req, context, session, _Answer("salvo.html", toast=DELETED))


# ── The steps of the flow (ISSUE-052) ────────────────────────────────────


def _activity_id(values: Mapping[str, str]) -> int:
    """The activity a step is about; without it the answer is the plain "not found"."""
    activity_id = validation.parse_id(values.get("atividade_id") or values.get("atividade"))
    if activity_id is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return activity_id


def _errors_of(error: InvalidDataError | VersionConflictError) -> dict[str, str]:
    """The messages of a refusal, by field; a conflict or a plain message goes under ``_``."""
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return dict(error.detail)
    hint = CONFLICT_HINT if isinstance(error, VersionConflictError) else ""
    return {GENERAL_ERROR: str(error) + hint}


def _drawer_again(
    req: func.HttpRequest,
    template: str,
    data: dict[str, object],
    error: InvalidDataError | VersionConflictError,
) -> func.HttpResponse:
    """The drawer of a step again, with what was typed, the messages and 409 or 422."""
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/{template}",
        context=data,
        request=req,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=next(iter(_errors_of(error).values()), None),
        toast_tipo="erro",
    )


def _step_done(
    req: func.HttpRequest, context: RequestContext, session: Session, activity: Activity, toast: str
) -> func.HttpResponse:
    """A step that worked: the drawer closes and the strip and the matrix of the week redraw."""
    answer = _Answer("salvo.html", params={"semana": activity.week}, toast=toast)
    return _page(req, context, session, answer)


@bp.route(route="programacao-semanal/atividades/detalhe", methods=["GET"])
@fragment_route(access=ACCESS)
def activity_detail(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The read-only drawer of an activity: the days, the notes and the comments."""
    caller = _caller(context)
    view = service.get_activity(session, caller=caller, activity_id=_activity_id(req.params))
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/detalhe.html",
        context=screen.detail_context(view),
        request=req,
    )


@bp.route(route="programacao-semanal/validacoes/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def validation_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The drawer that validates the programming and names the inspector (HU-73)."""
    opened = workflow.open_validation(
        session, caller=_caller(context), activity_id=_activity_id(req.params)
    )
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/validacao.html",
        context=screen.validation_context(opened),
        request=req,
    )


@bp.route(route="programacao-semanal/validacoes", methods=["POST"])
@fragment_route(access=ACCESS)
def validate_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Validate the programming: the planner names the inspector and the done is released."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values)
    sent = workflow.Validation(
        inspector_id=validation.parse_id(values.get("responsavel")),
        comments=(values.get("comentarios") or "").strip(),
        version=values.get("versao") or "",
    )
    try:
        activity = workflow.validate_activity(
            session, caller=caller, activity_id=activity_id, sent=sent
        )
    except (InvalidDataError, VersionConflictError) as error:
        if not _reopenable(error):
            raise
        opened = workflow.open_validation(session, caller=caller, activity_id=activity_id)
        data = screen.validation_context(opened, errors=_errors_of(error), typed=sent)
        return _drawer_again(req, "validacao.html", data, error)
    return _step_done(req, context, session, activity, VALIDATED.format(id=activity.unique_id))


@bp.route(route="programacao-semanal/realizados/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def report_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The drawer of the done by shift, with "= previsto" and "copiar a semana" (HU-74)."""
    opened = workflow.open_report(
        session, caller=_caller(context), activity_id=_activity_id(req.params)
    )
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/realizado.html",
        context=screen.report_context(opened),
        request=req,
    )


@bp.route(route="programacao-semanal/realizados", methods=["POST"])
@fragment_route(access=ACCESS)
def report_done(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the done of the two shifts; the deviation above the limit asks for a justification."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values)
    form = validation.parse_done(values)
    version = values.get("versao") or ""
    try:
        activity = workflow.report_done(
            session, caller=caller, activity_id=activity_id, form=form, version=version
        )
    except (InvalidDataError, VersionConflictError) as error:
        if not _reopenable(error):
            raise
        opened = workflow.open_report(session, caller=caller, activity_id=activity_id, typed=form)
        data = screen.report_context(opened, errors=_errors_of(error), version=version)
        return _drawer_again(req, "realizado.html", data, error)
    ppc = service.activity_figures(session, activity).ppc
    toast = DONE_SAVED.format(id=activity.unique_id, ppc=ppc)
    return _step_done(req, context, session, activity, toast)


@bp.route(route="programacao-semanal/aprovacoes/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def approval_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The drawer of the approval: the done day by day, before the inspector signs it (HU-75)."""
    view = workflow.open_approval(
        session, caller=_caller(context), activity_id=_activity_id(req.params)
    )
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/aprovacao.html",
        context=screen.approval_context(view),
        request=req,
    )


@bp.route(route="programacao-semanal/aprovacoes", methods=["POST"])
@fragment_route(access=ACCESS)
def approve_done(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Approve the done: it freezes for the supplier."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values)
    version = values.get("versao") or ""
    try:
        activity = workflow.approve_done(
            session,
            caller=caller,
            activity_id=activity_id,
            comments=(values.get("comentarios") or "").strip(),
            version=version,
        )
    except VersionConflictError as error:
        view = workflow.open_approval(session, caller=caller, activity_id=activity_id)
        data = screen.approval_context(view, errors=_errors_of(error), version=version)
        return _drawer_again(req, "aprovacao.html", data, error)
    return _step_done(req, context, session, activity, APPROVED.format(id=activity.unique_id))


@bp.route(route="programacao-semanal/reaberturas/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def reopen_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The drawer that reopens an approved done, asking the reason."""
    view = workflow.open_approval(
        session, caller=_caller(context), activity_id=_activity_id(req.params)
    )
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/reabertura.html",
        context=screen.reopen_context(view),
        request=req,
    )


@bp.route(route="programacao-semanal/reaberturas", methods=["POST"])
@fragment_route(access=ACCESS)
def reopen_done(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Reopen the done with the reason: it goes back to the reporting."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values)
    reason = (values.get("motivo") or "").strip()
    version = values.get("versao") or ""
    try:
        activity = workflow.reopen_done(
            session, caller=caller, activity_id=activity_id, reason=reason, version=version
        )
    except (InvalidDataError, VersionConflictError) as error:
        if not _reopenable(error):
            raise
        view = workflow.open_approval(session, caller=caller, activity_id=activity_id)
        data = screen.reopen_context(view, errors=_errors_of(error), version=version, reason=reason)
        return _drawer_again(req, "reabertura.html", data, error)
    return _step_done(req, context, session, activity, REOPENED.format(id=activity.unique_id))


@bp.route(route="programacao-semanal/publicacoes", methods=["POST"])
@fragment_route(access=ACCESS)
def publish_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Publish one validated activity: its edition ends."""
    values = {**_body(req), **req.params}
    activity = workflow.publish_activity(
        session,
        caller=_caller(context),
        activity_id=_activity_id(values),
        version=values.get("versao") or "",
    )
    return _step_done(req, context, session, activity, PUBLISHED.format(id=activity.unique_id))


@bp.route(route="programacao-semanal/publicacoes/semana", methods=["POST"])
@fragment_route(access=ACCESS)
def publish_week(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Publish every validated activity of the week in one action."""
    caller = _caller(context)
    values = {**_body(req), **req.params}
    week = service.resolve_week(session, caller=caller, raw=values.get("semana"))
    count = workflow.publish_week(session, caller=caller, week=week)
    answer = _Answer(
        "salvo.html",
        params={"semana": week},
        toast=WEEK_PUBLISHED.format(count=count) if count else workflow.NOTHING_TO_PUBLISH,
    )
    return _page(req, context, session, answer)
