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
from src.modulos.programacao_semanal import screen, service, validation
from src.modulos.programacao_semanal.service import Caller
from src.modulos.programacao_semanal.validation import ActivityForm

bp = func.Blueprint()

ACCESS = Access(module="programacao_semanal")
TEMPLATE_DIR = "programacao_semanal"
SAVED_NEW = "Atividade criada."
SAVED_EDIT = "Atividade salva."
DELETED = "Atividade excluída."
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
