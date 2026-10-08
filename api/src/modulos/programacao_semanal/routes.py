"""Route blueprint of the Weekly scheduling: the matrix of the week and the flow (D10).

Every route declares its ``Access`` (the module, so a supplier reaches it and a bond
without the module does not), resolves the scope and hands the facade a ``Caller``. The
cut by company, the window, the project and the role of each step are decided in
``service``, never here.

Targets of the screen (fixed ids, a multi-target answer): ``prog-janela`` (banner of the
window), ``prog-filtros`` (toolbar), ``prog-resumo`` (strip) and ``prog-tabela`` (matrix);
``drawer`` is the panel of a form. The panels of the flow (validation, done work,
approval) answer with the drawer plus the matrix on an error, so no declared target is
left without content; the publication answers with the strip and the matrix.
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
from src.modulos.programacao_semanal import screen, service, validation
from src.modulos.programacao_semanal.service import Caller
from src.modulos.programacao_semanal.validation import ActivityForm

bp = func.Blueprint()

ACCESS = Access(module="programacao_semanal")
TEMPLATE_DIR = "programacao_semanal"
SAVED_NEW = "Atividade criada."
SAVED_EDIT = "Atividade salva."
DELETED = "Atividade excluída."
NO_VALIDATED_TO_PUBLISH = "Nenhuma programação validada aguardando publicação."
GENERAL_ERROR = "_"
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


# ── The five steps of the flow ───────────────────────────────────────────


def _activity_id(raw: str | None) -> int:
    """The id of the activity of a panel, or the not-found message of the facade."""
    activity_id = validation.parse_id(raw)
    if activity_id is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return activity_id


def _errors_of(error: InvalidDataError | VersionConflictError) -> dict[str, str]:
    """The messages of a refused save, field by field; one general message otherwise."""
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return dict(error.detail)
    text = str(error) + (CONFLICT_HINT if isinstance(error, VersionConflictError) else "")
    return {GENERAL_ERROR: text}


def _panel(
    req: func.HttpRequest,
    context: RequestContext,
    session: Session,
    *,
    template: str,
    form: Mapping[str, object],
    week: str,
    status_code: int = 200,
    toast: str | None = None,
    with_matrix: bool = False,
) -> func.HttpResponse:
    """A panel of the flow: the drawer and, when asked, the strip and the matrix behind it."""
    data = dict(form)
    if with_matrix:
        data.update(
            screen.matrix_context(session, caller=_caller(context), params={"semana": week})
        )
    data["com_matriz"] = with_matrix
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/{template}",
        context=data,
        request=req,
        status_code=status_code,
        toast=toast,
        toast_tipo="erro" if status_code >= 400 else "ok",
    )


@bp.route(route="programacao-semanal/validacoes/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def validation_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The panel of validation: the inspector and the comments of the planner."""
    caller = _caller(context)
    opened = service.open_validation(
        session, caller=caller, activity_id=_activity_id(req.params.get("atividade"))
    )
    return _panel(
        req,
        context,
        session,
        template="validacao.html",
        form=screen.validation_context(opened=opened),
        week=opened.view.week,
    )


@bp.route(route="programacao-semanal/validacoes", methods=["POST"])
@fragment_route(access=ACCESS)
def save_validation(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Validate an activity and define the inspector; 422/409 give the panel back filled."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values.get("atividade_id"))
    version = values.get("versao") or ""
    form = validation.parse_validation(values)
    try:
        service.validate_activity(
            session, caller=caller, activity_id=activity_id, form=form, version=version
        )
    except (InvalidDataError, VersionConflictError) as error:
        errors = _errors_of(error)
        opened = service.flow_screen(session, caller=caller, activity_id=activity_id)
        return _panel(
            req,
            context,
            session,
            template="validacao.html",
            form=screen.validation_context(
                opened=opened, typed=form, errors=errors, version=version
            ),
            week=opened.view.week,
            status_code=409 if isinstance(error, VersionConflictError) else 422,
            toast=next(iter(errors.values()), None),
            with_matrix=True,
        )
    view = service.get_activity(session, caller=caller, activity_id=activity_id)
    return _page(
        req,
        context,
        session,
        _Answer(
            "salvo.html",
            params={"semana": view.week},
            toast=f"{view.unique_id} validada para {view.inspector}.",
        ),
    )


@bp.route(route="programacao-semanal/realizados/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def done_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The panel of the done work: both shifts, with the shortcuts of the app."""
    caller = _caller(context)
    opened = service.open_report(
        session, caller=caller, activity_id=_activity_id(req.params.get("atividade"))
    )
    return _panel(
        req,
        context,
        session,
        template="realizado.html",
        form=screen.report_context(opened=opened),
        week=opened.view.week,
    )


@bp.route(route="programacao-semanal/realizados", methods=["POST"])
@fragment_route(access=ACCESS)
def save_report(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Report the done work by shift; the deviation rule may demand a note (422)."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values.get("atividade_id"))
    version = values.get("versao") or ""
    form = validation.parse_done(values)
    try:
        service.report_done(
            session, caller=caller, activity_id=activity_id, form=form, version=version
        )
    except (InvalidDataError, VersionConflictError) as error:
        errors = _errors_of(error)
        opened = service.flow_screen(session, caller=caller, activity_id=activity_id)
        return _panel(
            req,
            context,
            session,
            template="realizado.html",
            form=screen.report_context(opened=opened, typed=form, errors=errors, version=version),
            week=opened.view.week,
            status_code=409 if isinstance(error, VersionConflictError) else 422,
            toast=next(iter(errors.values()), None),
            with_matrix=True,
        )
    view = service.get_activity(session, caller=caller, activity_id=activity_id)
    return _page(
        req,
        context,
        session,
        _Answer(
            "salvo.html",
            params={"semana": view.week},
            toast=(f"Realizado de {view.unique_id} registrado — PPC de {view.figures.ppc:.0f}%."),
        ),
    )


@bp.route(route="programacao-semanal/aprovacoes/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def approval_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The panel of the inspector: approve the done work, or reopen it with a reason."""
    caller = _caller(context)
    opened = service.open_approval(
        session, caller=caller, activity_id=_activity_id(req.params.get("atividade"))
    )
    return _panel(
        req,
        context,
        session,
        template="aprovacao.html",
        form=screen.approval_context(opened=opened),
        week=opened.view.week,
    )


@bp.route(route="programacao-semanal/aprovacoes", methods=["POST"])
@fragment_route(access=ACCESS)
def save_approval(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Approve the done work of an activity; the supplier may no longer change it."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values.get("atividade_id"))
    version = values.get("versao") or ""
    form = validation.parse_approval(values)
    try:
        service.approve_activity(
            session, caller=caller, activity_id=activity_id, form=form, version=version
        )
    except (InvalidDataError, VersionConflictError) as error:
        errors = _errors_of(error)
        opened = service.flow_screen(session, caller=caller, activity_id=activity_id)
        return _panel(
            req,
            context,
            session,
            template="aprovacao.html",
            form=screen.approval_context(opened=opened, typed=form, errors=errors, version=version),
            week=opened.view.week,
            status_code=409 if isinstance(error, VersionConflictError) else 422,
            toast=next(iter(errors.values()), None),
            with_matrix=True,
        )
    view = service.get_activity(session, caller=caller, activity_id=activity_id)
    return _page(
        req,
        context,
        session,
        _Answer(
            "salvo.html",
            params={"semana": view.week},
            toast=f"Realizado de {view.unique_id} aprovado.",
        ),
    )


@bp.route(route="programacao-semanal/reaberturas", methods=["POST"])
@fragment_route(access=ACCESS)
def reopen_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Reopen an approved done work, with the reason; the supplier may report again."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values.get("atividade_id"))
    version = values.get("versao") or ""
    form = validation.parse_approval(values)
    try:
        service.reopen_activity(
            session, caller=caller, activity_id=activity_id, form=form, version=version
        )
    except (InvalidDataError, VersionConflictError) as error:
        errors = _errors_of(error)
        opened = service.flow_screen(session, caller=caller, activity_id=activity_id)
        return _panel(
            req,
            context,
            session,
            template="aprovacao.html",
            form=screen.approval_context(opened=opened, typed=form, errors=errors, version=version),
            week=opened.view.week,
            status_code=409 if isinstance(error, VersionConflictError) else 422,
            toast=next(iter(errors.values()), None),
            with_matrix=True,
        )
    view = service.get_activity(session, caller=caller, activity_id=activity_id)
    return _page(
        req,
        context,
        session,
        _Answer(
            "salvo.html",
            params={"semana": view.week},
            toast=f"Realizado de {view.unique_id} reaberto.",
        ),
    )


@bp.route(route="programacao-semanal/publicacoes", methods=["POST"])
@fragment_route(access=ACCESS)
def publish(req: func.HttpRequest, session: Session, context: RequestContext) -> func.HttpResponse:
    """Publish one validated activity, closing its edition."""
    values = {**_body(req), **req.params}
    caller = _caller(context)
    activity_id = _activity_id(values.get("atividade"))
    service.publish_activity(
        session,
        caller=caller,
        activity_id=activity_id,
        version=values.get("versao") or None,
    )
    view = service.get_activity(session, caller=caller, activity_id=activity_id)
    return _page(
        req,
        context,
        session,
        _Answer("salvo.html", params={"semana": view.week}, toast=f"{view.unique_id} publicada."),
    )


@bp.route(route="programacao-semanal/publicacoes/semana", methods=["POST"])
@fragment_route(access=ACCESS)
def publish_week(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Publish every validated activity of the week in one action."""
    caller = _caller(context)
    values = {**_body(req), **req.params}
    week = service.resolve_week(session, caller=caller, raw=values.get("semana"))
    published = service.publish_week(session, caller=caller, week=week)
    toast = f"{published} programação(ões) publicada(s)." if published else NO_VALIDATED_TO_PUBLISH
    return _page(req, context, session, _Answer("salvo.html", params={"semana": week}, toast=toast))


@bp.route(route="programacao-semanal/atividades/detalhe", methods=["GET"])
@fragment_route(access=ACCESS)
def activity_detail(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The read-only panel of one activity: the ficha, the day grid and the history."""
    caller = _caller(context)
    opened = service.open_detail(
        session, caller=caller, activity_id=_activity_id(req.params.get("atividade"))
    )
    return _panel(
        req,
        context,
        session,
        template="detalhe.html",
        form=screen.detail_context(session, opened=opened),
        week=opened.view.week,
    )
