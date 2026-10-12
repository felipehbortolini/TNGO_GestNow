"""Route blueprint of the Weekly scheduling: the matrix of the week and the flow (D10).

Every route declares its ``Access`` (the module, so a supplier reaches it and a bond
without the module does not), resolves the scope and hands the facade a ``Caller``. The
cut by company, the window, the project and the role of each step are decided in
``service``, never here.

Targets of the screen (fixed ids, a multi-target answer): ``prog-janela`` (banner of the
window), ``prog-filtros`` (toolbar), ``prog-resumo`` (strip) and ``prog-tabela`` (matrix);
``drawer`` is the panel of a form. The panels of the flow (validation, done work,
approval) answer with the drawer plus the matrix on an error, so no declared target is
left without content; the publication answers with the strip and the matrix. The
governance screen (ISSUE-053) adds ``gov-painel``, ``gov-pedidos`` and ``gov-trilha``:
the panel, the queue of change requests and the module's audit trail. The configuration
screen (ISSUE-054) adds ``config-painel`` (the whole panel), ``config-parametros`` and
``config-janelas``: each block saves and re-renders on its own target. The dashboard
(ISSUE-056) uses ``dash-filtros`` (the toolbar, which stays where it is) and
``dash-painel`` (the whole panel of indicators, charts and tables); its exports leave
by the generic document (``excel_response`` and ``printable_response``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario, importing, translations
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind
from src.core.printable import printable_response
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.core.spreadsheet_reader import MAX_FILE_BYTES
from src.modulos.configuracoes import registers
from src.modulos.configuracoes import service as configuracoes
from src.modulos.programacao_semanal import (
    export,
    importers,
    permissions,
    screen,
    service,
    validation,
)
from src.modulos.programacao_semanal.screen import SettingsSubmission, WindowSubmission
from src.modulos.programacao_semanal.service import Caller
from src.modulos.programacao_semanal.validation import ActivityForm
from src.modulos.programacao_semanal.views import ActivityView

bp = func.Blueprint()

importers.register_importers()

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


def _notice(text: str, req: func.HttpRequest) -> str:
    """The notice of a write in the language of the request (D13)."""
    return translations.translate("programacao_semanal", text, translations.language_of(req))


def _errors_in_language(errors: Mapping[str, str], req: func.HttpRequest) -> dict[str, str]:
    """The refusal of each field in the language of the request (D13)."""
    idioma = translations.language_of(req)
    return {
        field: translations.translate("programacao_semanal", message, idioma)
        for field, message in errors.items()
    }


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
        errors = _errors_in_language(dict(error.detail), req)
    else:
        text = str(error) + (CONFLICT_HINT if isinstance(error, VersionConflictError) else "")
        text = translations.translate("programacao_semanal", text, translations.language_of(req))
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
    toast = _notice(SAVED_NEW if activity_id is None else SAVED_EDIT, req)
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
    return _page(req, context, session, _Answer("salvo.html", toast=_notice(DELETED, req)))


# ── The five steps of the flow ───────────────────────────────────────────


def _activity_id(raw: str | None) -> int:
    """The id of the activity of a panel, or the not-found message of the facade."""
    activity_id = validation.parse_id(raw)
    if activity_id is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return activity_id


def _errors_of(
    error: InvalidDataError | VersionConflictError, req: func.HttpRequest
) -> dict[str, str]:
    """The messages of a refused save, field by field; one general message otherwise."""
    idioma = translations.language_of(req)
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return _errors_in_language(dict(error.detail), req)
    text = str(error) + (CONFLICT_HINT if isinstance(error, VersionConflictError) else "")
    return {GENERAL_ERROR: translations.translate("programacao_semanal", text, idioma)}


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
        errors = _errors_of(error, req)
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
            toast=_notice("{id} validada para {inspector}.", req).format(
                id=view.unique_id, inspector=view.inspector
            ),
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
        errors = _errors_of(error, req)
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
            toast=_notice("Realizado de {id} registrado — PPC de {ppc}%.", req).format(
                id=view.unique_id, ppc=f"{view.figures.ppc:.0f}"
            ),
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
        errors = _errors_of(error, req)
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
            toast=_notice("Realizado de {id} aprovado.", req).format(id=view.unique_id),
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
        errors = _errors_of(error, req)
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
            toast=_notice("Realizado de {id} reaberto.", req).format(id=view.unique_id),
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
        _Answer(
            "salvo.html",
            params={"semana": view.week},
            toast=_notice("{id} publicada.", req).format(id=view.unique_id),
        ),
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
    toast = (
        _notice("{count} programação(ões) publicada(s).", req).format(count=published)
        if published
        else _notice(NO_VALIDATED_TO_PUBLISH, req)
    )
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


# ── The governance and the change requests (ISSUE-053) ───────────────────


def _request_id(raw: str | None) -> int:
    """The id of the change request in the address, or the not-found message."""
    request_id = validation.parse_id(raw)
    if request_id is None:
        raise InvalidDataError(service.REQUEST_NOT_FOUND_MESSAGE)
    return request_id


@bp.route(route="programacao-semanal/governanca", methods=["GET"])
@fragment_route(access=ACCESS)
def governance_panel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The governance panel: the indicators, the control list, the windows and the queue."""
    data = screen.governance_context(session, caller=_caller(context))
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/painel.html", context=data, request=req
    )


@bp.route(route="programacao-semanal/governanca/trilha", methods=["GET"])
@fragment_route(access=ACCESS)
def governance_trail(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The module's audit trail: who changed what, and when."""
    data = screen.trail_context(session, caller=_caller(context))
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/trilha.html", context=data, request=req
    )


@bp.route(route="programacao-semanal/governanca/excel", methods=["GET"])
@file_route(access=ACCESS)
def governance_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the panel and of the queue."""
    return excel_response(_governance_document(session, context, req))


@bp.route(route="programacao-semanal/governanca/imprimivel", methods=["GET"])
@fragment_route(access=ACCESS)
def governance_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the panel and of the queue: what the PDF button mounts."""
    return printable_response(_governance_document(session, context, req), req)


def _governance_document(
    session: Session, context: RequestContext, req: func.HttpRequest
) -> Document:
    caller = _caller(context)
    panel = service.governance_panel(session, caller=caller)
    queue = service.request_queue(session, caller=caller)
    return export.governance_document(
        panel,
        queue,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
        idioma=translations.language_of(req),
    )


@bp.route(route="programacao-semanal/pedidos", methods=["GET"])
@fragment_route(access=ACCESS)
def request_queue(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The queue of change requests: what waits for a decision, and what was decided."""
    data = screen.queue_context(session, caller=_caller(context))
    return AlpineAjaxResponse(template_name=f"{TEMPLATE_DIR}/fila.html", context=data, request=req)


@bp.route(route="programacao-semanal/pedidos/formulario", methods=["GET"])
@fragment_route(access=ACCESS)
def request_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The drawer of a change request: the item that is closed and the reason to type."""
    caller = _caller(context)
    view = service.open_request(
        session, caller=caller, activity_id=_activity_id(req.params.get("atividade"))
    )
    return _panel(
        req,
        context,
        session,
        template="pedido.html",
        form=screen.request_context(view=view),
        week=view.week,
    )


@bp.route(route="programacao-semanal/pedidos", methods=["POST"])
@fragment_route(access=ACCESS)
def open_request(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Put a change request in the queue; 422 gives the drawer back filled."""
    caller = _caller(context)
    values = _body(req)
    activity_id = _activity_id(values.get("atividade_id"))
    reason = values.get("motivo") or ""
    try:
        request = service.request_change(
            session, caller=caller, activity_id=activity_id, reason=reason
        )
    except InvalidDataError as error:
        errors = _errors_of(error, req)
        view = service.get_activity(session, caller=caller, activity_id=activity_id)
        return _panel(
            req,
            context,
            session,
            template="pedido.html",
            form=screen.request_context(view=view, typed=reason, errors=errors),
            week=view.week,
            status_code=422,
            toast=next(iter(errors.values()), None),
            with_matrix=True,
        )
    view = service.get_activity(session, caller=caller, activity_id=request.activity_id)
    data = screen.matrix_context(session, caller=caller, params={"semana": view.week})
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/pedido_salvo.html",
        context=data,
        request=req,
        toast=_notice(service.REQUEST_OPEN_TOAST, req).format(unique_id=view.unique_id),
    )


def _queue_answer(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    status_code: int = 200,
    toast: str | None = None,
    erro_id: int | None = None,
    erro_mensagem: str = "",
    resposta_digitada: str = "",
) -> func.HttpResponse:
    """The queue and the trail again, behind the modal of the decision."""
    caller = _caller(context)
    data = screen.queue_context(
        session,
        caller=caller,
        erro_id=erro_id,
        erro_mensagem=erro_mensagem,
        resposta_digitada=resposta_digitada,
    )
    data.update(screen.trail_context(session, caller=caller))
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/fila_resposta.html",
        context=data,
        request=req,
        status_code=status_code,
        toast=toast,
        toast_tipo="erro" if status_code >= 400 else "ok",
    )


@bp.route(route="programacao-semanal/pedidos/{id}/decisao", methods=["POST"])
@fragment_route(access=ACCESS)
def decide_request(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Apply or refuse a change request; applying reopens the activity."""
    caller = _caller(context)
    values = _body(req)
    request_id = _request_id(req.route_params.get("id") or req.params.get("id"))
    form = validation.parse_decision(values)
    try:
        decided = service.decide_request(session, caller=caller, request_id=request_id, form=form)
    except (InvalidDataError, VersionConflictError) as error:
        errors = _errors_of(error, req)
        message = next(iter(errors.values()), None)
        return _queue_answer(
            req,
            session,
            context,
            status_code=409 if isinstance(error, VersionConflictError) else 422,
            toast=message,
            erro_id=request_id,
            erro_mensagem=message or "",
            resposta_digitada=form.answer,
        )
    template = service.REQUEST_APPLY_TOAST if form.apply else service.REQUEST_REJECT_TOAST
    toast = _notice(template, req).format(unique_id=decided.unique_id)
    return _queue_answer(req, session, context, toast=toast)


# ── The configuration of the schedule (ISSUE-054) ────────────────────────

CONFIGURATION_TEMPLATE = "configuracao.html"
SETTINGS_TEMPLATE = "parametros.html"
WINDOWS_TEMPLATE = "janelas.html"


@bp.route(route="programacao-semanal/configuracao", methods=["GET"])
@fragment_route(access=ACCESS)
def configuration(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The configuration of the project: the parameters and the windows by company."""
    data = screen.configuration_context(session, caller=_caller(context))
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/{CONFIGURATION_TEMPLATE}", context=data, request=req
    )


def _settings_answer(
    req: func.HttpRequest,
    context: RequestContext,
    session: Session,
    *,
    submission: SettingsSubmission | None = None,
    status_code: int = 200,
    toast: str | None = None,
) -> func.HttpResponse:
    """The parameters block again, with the error messages next to the fields when refused."""
    data = screen.configuration_context(session, caller=_caller(context), settings=submission)
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/{SETTINGS_TEMPLATE}",
        context=data,
        request=req,
        status_code=status_code,
        toast=toast,
        toast_tipo="erro" if status_code >= 400 else "ok",
    )


@bp.route(route="programacao-semanal/configuracao/parametros", methods=["POST"])
@fragment_route(access=ACCESS)
def save_settings(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the parameters of the schedule (Planner or Admin); 422/409 give the form back."""
    caller = _caller(context)
    values = _body(req)
    form = validation.parse_settings(values)
    version = values.get("versao") or ""
    try:
        service.save_parameters(session, caller=caller, form=form, version=version)
    except (InvalidDataError, VersionConflictError) as error:
        errors = _errors_of(error, req)
        return _settings_answer(
            req,
            context,
            session,
            submission=SettingsSubmission(errors=errors, values=form, version=version),
            status_code=409 if isinstance(error, VersionConflictError) else 422,
            toast=next(iter(errors.values()), None),
        )
    return _settings_answer(req, context, session, toast=_notice(service.SETTINGS_SAVED, req))


def _windows_answer(
    req: func.HttpRequest,
    context: RequestContext,
    session: Session,
    *,
    submission: WindowSubmission | None = None,
    status_code: int = 200,
    toast: str | None = None,
) -> func.HttpResponse:
    """The windows block again: all the cards, the refused one with its messages."""
    data = screen.configuration_context(session, caller=_caller(context), windows=submission)
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/{WINDOWS_TEMPLATE}",
        context=data,
        request=req,
        status_code=status_code,
        toast=toast,
        toast_tipo="erro" if status_code >= 400 else "ok",
    )


@bp.route(route="programacao-semanal/configuracao/janela", methods=["POST"])
@fragment_route(access=ACCESS)
def save_window(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the window of a company (Planner or Admin); 422/409 give the card back filled."""
    caller = _caller(context)
    values = _body(req)
    form = validation.parse_window(values, selected_weeks=req.form.getlist("semanas"))
    version = values.get("versao") or ""
    try:
        service.save_window(session, caller=caller, form=form, version=version)
    except (InvalidDataError, VersionConflictError) as error:
        errors = _errors_of(error, req)
        return _windows_answer(
            req,
            context,
            session,
            submission=WindowSubmission(
                errors=errors, values=form, company_id=form.company_id, version=version
            ),
            status_code=409 if isinstance(error, VersionConflictError) else 422,
            toast=next(iter(errors.values()), None),
        )
    company_id = form.company_id or 0
    company = registers.company_names(session, {company_id}).get(company_id, "")
    return _windows_answer(
        req, context, session, toast=_notice(service.WINDOW_SAVED, req).format(company=company)
    )


# ── The import and the outputs of the week (ISSUE-055) ───────────────────
#
# The import is the generic flow of D12 with the app's importer: the model, the
# check line by line (nothing written) and the confirmation, which writes every
# line without error, all or none, with the digest of the checked file. The
# model is a download (``file_route``: the browser opens it as a file, without
# the Alpine gate). The Excel and the printable sheet of the week come from the
# same module: the app's workbook and the app's printed sheet. The handlers are
# named ``week_import_*`` because the generic blueprint of the platform already
# owns the ``import_check``/``import_confirm`` names of the Azure Functions host.

IMPORT_BASE = "programacao-semanal/importacao"
WEEK_EXCEL_ROUTE = "programacao-semanal/semana/excel"
WEEK_PRINTABLE_ROUTE = "programacao-semanal/semana/imprimivel"

CHECKED_FIELD = "conferido"
ACKNOWLEDGED_FIELD = "ciente"
ACKNOWLEDGED_VALUE = "sim"

_NUMERIC_KINDS = frozenset(
    {ValueKind.INTEGER, ValueKind.DECIMAL, ValueKind.PERCENT, ValueKind.MONEY}
)


def _require_import(context: RequestContext) -> int:
    """The import is the Planner of the project or the Admin, as the app's ``importar`` (D7)."""
    project_id = context.scope.require_project()
    if not permissions.can_import(context.user, project_id):
        raise AccessDeniedError(permissions.IMPORT_DENIED)
    return project_id


def _import_context(context: RequestContext) -> importing.ImportContext:
    """Who imports, in which scope and today: the only place of the flow that reads the clock."""
    return importing.ImportContext(
        user=context.user, scope=context.scope, reference_date=calendario.today()
    )


def _upload_of(req: func.HttpRequest) -> importing.Upload:
    """The file of the form; at most one byte over the limit is read."""
    sent = req.files.get(attachments.FILE_FIELD)
    if sent is None:
        return importing.Upload(name=None, content=b"")
    return importing.Upload(name=sent.filename, content=sent.stream.read(MAX_FILE_BYTES + 1))


@bp.route(route=IMPORT_BASE, methods=["GET"])
@fragment_route(access=ACCESS)
def week_import(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The import and print tab: the model, the upload and the week's outputs."""
    data = screen.import_context(session, caller=_caller(context), params=req.params)
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/importacao.html", context=data, request=req
    )


@bp.route(route=f"{IMPORT_BASE}/modelo", methods=["GET"])
@file_route(access=ACCESS)
def week_import_model(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The blank model (.xlsx) of the importer, with the app's columns and instructions."""
    del req
    _require_import(context)
    importer = importers.programacao_importer()
    document = importing.model_document(
        session, importer=importer, context=_import_context(context)
    )
    return excel_response(document)


def _check_context(preview: importing.ImportPreview) -> dict[str, Any]:
    """What the check fragment prints: the preview, the counts and where the confirmation goes."""
    return {
        "arquivo": preview.file_name,
        "preview": preview,
        "colunas": [
            {"cabecalho": column.header, "numerica": column.kind in _NUMERIC_KINDS}
            for column in preview.columns
        ],
        "lidas": len(preview.rows),
        "vao_gravar": len(preview.writable_rows),
        "com_aviso": len(preview.warning_rows),
        "com_erro": len(preview.error_rows),
        "campo_conferido": CHECKED_FIELD,
        "campo_ciente": ACKNOWLEDGED_FIELD,
        "valor_ciente": ACKNOWLEDGED_VALUE,
        "confirmar_url": f"/api/{IMPORT_BASE}/confirmar",
    }


@bp.route(route=f"{IMPORT_BASE}/conferir", methods=["POST"])
@fragment_route(access=ACCESS)
def week_import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Read the spreadsheet and answer what each line will do; nothing is written."""
    _require_import(context)
    preview = importing.check(
        session,
        importer=importers.programacao_importer(),
        upload=_upload_of(req),
        context=_import_context(context),
    )
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/importacao_conferencia.html",
        context=_check_context(preview),
        request=req,
    )


def _import_notice(result: importing.ImportResult, req: func.HttpRequest) -> str:
    """The toast: how many lines entered and, when an error left some out, how many did not."""
    written = len(result.written)
    imported = _notice("1 linha importada" if written == 1 else "{n} linhas importadas", req)
    if written != 1:
        imported = imported.format(n=written)
    if not result.skipped:
        return f"{imported}."
    skipped = len(result.skipped)
    left_out = _notice(
        "1 com erro não entrou" if skipped == 1 else "{n} com erro não entraram", req
    )
    if skipped != 1:
        left_out = left_out.format(n=skipped)
    return f"{imported}; {left_out}."


def _imported_week(result: importing.ImportResult) -> str:
    """The one week the written lines landed on, for the link back to the matrix."""
    weeks_written = {
        str(item.values.get(importers.FIELD_WEEK) or "").strip() for item in result.written
    }
    weeks_written.discard("")
    return next(iter(weeks_written)) if len(weeks_written) == 1 else ""


@bp.route(route=f"{IMPORT_BASE}/confirmar", methods=["POST"])
@fragment_route(access=ACCESS)
def week_import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Write every line without error, all or none, after checking the file again."""
    _require_import(context)
    importer = importers.programacao_importer()
    result = importing.confirm(
        session,
        importer=importer,
        upload=_upload_of(req),
        context=_import_context(context),
        confirmation=importing.Confirmation(
            checked_digest=(req.form.get(CHECKED_FIELD) or "").strip() or None,
            acknowledged=req.form.get(ACKNOWLEDGED_FIELD) == ACKNOWLEDGED_VALUE,
        ),
    )
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/importacao_resultado.html",
        context={
            "resultado": result,
            "importador": importer.title,
            "semana": _imported_week(result),
        },
        request=req,
        toast=_import_notice(result, req),
        toast_tipo="aviso" if result.skipped else "ok",
    )


def _week_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> tuple[Caller, str, list[ActivityView]]:
    """The week asked, its caller and the activities the user sees (the cut is the facade's)."""
    caller = _caller(context)
    week = service.resolve_week(session, caller=caller, raw=req.params.get("semana"))
    return caller, week, service.list_activities(session, caller=caller, week=week)


@bp.route(route=WEEK_EXCEL_ROUTE, methods=["GET"])
@file_route(access=ACCESS)
def week_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The workbook of the week: the app's sheets, the matrix and the S-curve."""
    caller, week, views = _week_of(req, session, context)
    document = export.week_document(
        week,
        views,
        service.week_summary(views),
        service.week_curve(session, caller=caller, week=week),
        service.parameters_of(session, caller.scope.project_id),
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
        idioma=translations.language_of(req),
    )
    return excel_response(document)


@bp.route(route=WEEK_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=ACCESS)
def week_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable sheet of the week: what the PDF button mounts and prints."""
    caller, week, views = _week_of(req, session, context)
    document = export.week_report_document(
        week,
        views,
        service.week_summary(views),
        service.parameters_of(session, caller.scope.project_id),
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
        idioma=translations.language_of(req),
    )
    return printable_response(document, req)


# ── The dashboard (ISSUE-056) ────────────────────────────────────────────
#
# The panel and its toolbar answer on fixed targets (``dash-painel`` and
# ``dash-filtros``); the exports leave by the generic document, with the same week
# and filters the screen is showing. The charts are the library's: the server sends
# the quantities in ``data-dados`` and the visual aggregates by period.

DASHBOARD_BASE = "programacao-semanal/dashboard"
DASHBOARD_EXCEL_ROUTE = f"{DASHBOARD_BASE}/excel"
DASHBOARD_PRINTABLE_ROUTE = f"{DASHBOARD_BASE}/imprimivel"


@bp.route(route=DASHBOARD_BASE, methods=["GET"])
@fragment_route(access=ACCESS)
def dashboard(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The dashboard panel: the indicators, the charts and the tables of the week."""
    data = screen.dashboard_context(session, caller=_caller(context), params=req.params)
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/dashboard.html", context=data, request=req
    )


@bp.route(route=f"{DASHBOARD_BASE}/filtros", methods=["GET"])
@fragment_route(access=ACCESS)
def dashboard_filters(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The toolbar of the dashboard: the week and the cuts of the app."""
    data = screen.dashboard_filters_context(session, caller=_caller(context), params=req.params)
    return AlpineAjaxResponse(
        template_name=f"{TEMPLATE_DIR}/dashboard_filtros.html", context=data, request=req
    )


def _dashboard_document(
    session: Session,
    context: RequestContext,
    req: func.HttpRequest,
    params: Mapping[str, str | None],
) -> Document:
    caller = _caller(context)
    week = service.resolve_week(session, caller=caller, raw=params.get("semana"))
    data = service.dashboard_data(
        session,
        caller=caller,
        week=week,
        filters=service.parse_filters(params),
    )
    return export.dashboard_document(
        data,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
        idioma=translations.language_of(req),
    )


@bp.route(route=DASHBOARD_EXCEL_ROUTE, methods=["GET"])
@file_route(access=ACCESS)
def dashboard_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the dashboard: the indicators and the numbers behind each chart."""
    return excel_response(_dashboard_document(session, context, req, req.params))


@bp.route(route=DASHBOARD_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=ACCESS)
def dashboard_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable dashboard: the same panel on the sheet of the Design System."""
    return printable_response(_dashboard_document(session, context, req, req.params), req)
