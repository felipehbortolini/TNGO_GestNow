"""Route blueprint for the Planning module.

Relato do período (ISSUE-044, HU-046), prefix ``/api/planejamento/relatos``. The screen is one
panel (indicators and table) plus the modals Novo, Editar, Ver and Copiar, all fragments:

* ``GET  relatos`` is the panel for the filter (``tipo``, ``busca``);
* ``GET  relatos/ver?id=`` is the modal Ver; ``GET relatos/abrir?tipo=&periodo=`` is the address
  of the report manager's modal: it opens the report of the period, or the form for it;
* ``GET  relatos/formulario`` is the form (``id`` edits, ``tipo`` and ``periodo`` start a new
  one); ``POST relatos/formulario`` draws it again with what was typed (type changed, a point
  added with ``acao=adicionar-ponto`` or removed with ``acao=remover-ponto&indice=``);
* ``POST relatos/copiar`` is "Copiar do período anterior"; ``POST relatos/gravar`` saves (422
  per field, 409 for a stale version, 403 below Membro); ``POST relatos/excluir`` deletes (403
  below Gestor);
* ``GET  relatos/excel`` and ``GET relatos/imprimivel`` are the two exports of the list.


The 6WLA (ISSUE-045), prefix ``/api/planejamento/6wla``:

* ``GET  /``  the screen: filters and content (indicators, Gantt, grid, restrictions, Galeria);
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same board;
* ``GET  /atividades/nova``, ``POST /atividades``  include an activity (needs a project);
* ``GET  /atividades/{atividade_id}/editar``, ``POST /atividades/{atividade_id}``  edit it;
* ``GET  /restricoes/nova``, ``POST /restricoes``  register a restriction (``?atividade=``);
* ``GET  /restricoes/{restricao_id}/editar``, ``POST /restricoes/{restricao_id}``  edit it;
* ``GET  /restricoes/{restricao_id}/remover``, ``POST /restricoes/{restricao_id}/remocao``  remove it.

The routes read the request and draw the answer; every rule is in the facade. A write answers
three blocks at once (form, filters and content), because Alpine AJAX empties a declared target
that does not come back: the form is shown again with the messages on 422 and 409, and emptied
on success.

The EAP (ISSUE-036), prefix ``/api/planejamento/eap``:

* ``GET  /``  the screen: indicators, tree, revisions and the breakdowns of the revision in
  force, in the read-only Portfólio with the ``Projeto`` column;
* ``GET  /itens/{item_id}/dicionario``  the dictionary form of the package;
* ``POST /itens/{item_id}/dicionario``  saves it (Membro; 422 per field, 409 for a stale
  version, 403 in the Portfólio) and answers the content and the form in one multi-target reply;
* ``GET  /itens/{item_id}/avanco``  the progress form of the package, with the entries of its
  criterion (ISSUE-037);
* ``POST /itens/{item_id}/avanco``  registers the progress (Membro; 422 per field, 403 for a
  reversal without Gestor, 409 for a stale version) answering the content and the form;
* ``GET  /importar/formulario``, ``POST /importar/conferir`` and ``POST /importar/confirmar``
  the spreadsheet import of the progress (the ``eap-avanco`` importer): the check reads and
  shows each line, the confirmation writes the lines without error, dated with the form date;
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same content.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario, importing, rbac
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, describe_scope, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.core.spreadsheet_reader import MAX_DATA_ROWS, MAX_FILE_BYTES, MEGABYTE
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, export, importers, service, validation
from src.modulos.planejamento.validation import PointInput

bp = func.Blueprint()

importers.register_importers()


ROUTE = "planejamento/relatos"


PANEL_TEMPLATE = "planejamento/relato_painel.html"


VIEW_TEMPLATE = "planejamento/relato_ver.html"


FORM_TEMPLATE = "planejamento/relato_formulario.html"


SAVED_TEMPLATE = "planejamento/relato_salvo.html"


# The places the answers go: the panel of the screen and the body of the open modal.
PANEL_TARGET = "relato-painel"


MODAL_TARGET = "relato-modal"


# The styles of the screen are scoped by the class of its root, and a modal lives outside it.
PAGE_CLASS = "pagina--planejamento-relato"


READ_ACCESS = Access(module=service.MODULE)


WRITE_ACCESS = Access(module=service.MODULE, permission=Permission.WRITE)


MANAGE_ACCESS = Access(module=service.MODULE, permission=Permission.MANAGE)


ACTION_ADD_POINT = "adicionar-ponto"


ACTION_REMOVE_POINT = "remover-ponto"


# The most rows of points the form reads: more than this is not a typo, it is abuse.
MAX_POINT_ROWS = 100


_POINT_FIELD = re.compile(r"ponto_(\d+)_(?:descricao|natureza|risco)")


NO_PREVIOUS_MESSAGE = "Não há relato {kind} anterior para copiar."


COPIED_MESSAGE = (
    "Copiado de {name}: o próximo período virou atividades do período e os pontos de atenção "
    "foram trazidos para revisão."
)


NOT_REPORTED_MESSAGE = "Ainda não há relato para este período."


DELETED_MESSAGE = "Relato excluído."


SAVED_MESSAGE = "Relato {kind} de {name} {verb}."


@dataclass(frozen=True)
class Reply:
    """How an answer differs from the plain one: its status and the toast that goes with it."""

    status_code: int = 200
    toast: str | None = None
    toast_kind: str = "ok"


@dataclass(frozen=True)
class FormState:
    """What the form holds: the identity, the texts as typed, the points and the messages."""

    report_id: int | None = None
    version: str = ""
    kind: str = ""
    period: str = ""
    activities: str = ""
    next_activities: str = ""
    points: tuple[PointInput, ...] = ()
    errors: Mapping[str, str] = field(default_factory=dict)


# ── The panel and the modals that only read ────────────────────────────────


@bp.route(route=ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def report_panel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The indicators and the table, after the type and the search of the filter."""
    return _panel_response(req, session, context, _filter_of(req.params))


@bp.route(route=f"{ROUTE}/ver", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def report_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The modal Ver: the whole report, with the risk tied to each attention point."""
    report = service.get_report(
        session,
        user=context.user,
        scope=context.scope,
        report_id=_integer(req.params.get("id")) or 0,
    )
    return _view_response(req, context, report)


@bp.route(route=f"{ROUTE}/abrir", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def report_open(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The address with type, period and open: the report of the period, or the form to fill it."""
    kind = req.params.get("tipo", "")
    period = req.params.get("periodo", "")
    report = service.find_report(
        session, user=context.user, scope=context.scope, kind=kind, period=period
    )
    if report is not None:
        return _view_response(req, context, report)
    if not rbac.can(context.user, Permission.WRITE):
        raise InvalidDataError(NOT_REPORTED_MESSAGE)
    return _form_response(req, session, context, FormState(kind=kind, period=period))


# ── The form ───────────────────────────────────────────────────────────────


@bp.route(route=f"{ROUTE}/formulario", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def report_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new report, or of the one with the ``id``."""
    report_id = _integer(req.params.get("id"))
    if report_id is None:
        state = FormState(
            kind=req.params.get("tipo") or validation.WEEKLY,
            period=req.params.get("periodo", ""),
            points=(PointInput(),),
        )
        return _form_response(req, session, context, state)
    report = service.get_report(
        session, user=context.user, scope=context.scope, report_id=report_id
    )
    return _form_response(req, session, context, _state_of(report))


@bp.route(route=f"{ROUTE}/formulario", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def report_form_reload(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form again with what was typed: after the type changed, or a point added or removed."""
    state = _read_state(req)
    action = req.params.get("acao")
    if action == ACTION_ADD_POINT and len(state.points) < validation.MAX_POINTS:
        state = replace(state, points=(*state.points, PointInput()))
    elif action == ACTION_REMOVE_POINT:
        index = _integer(req.params.get("indice"))
        state = replace(
            state,
            points=tuple(point for position, point in enumerate(state.points) if position != index),
        )
    return _form_response(req, session, context, state)


@bp.route(route=f"{ROUTE}/copiar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def report_copy(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Copiar do período anterior: the next period of the previous report, and its points to review."""
    state = _read_state(req)
    previous = service.previous_report(
        session, user=context.user, scope=context.scope, request=_request_of(state)
    )
    if previous is None:
        kind = (_kind_of(session, context, state) or "").lower()
        reply = Reply(toast=NO_PREVIOUS_MESSAGE.format(kind=kind), toast_kind="aviso")
        return _form_response(req, session, context, state, reply)
    copied = replace(
        state,
        activities="\n".join(previous.next_activities),
        points=previous.points,
        errors={},
    )
    reply = Reply(toast=COPIED_MESSAGE.format(name=previous.name))
    return _form_response(req, session, context, copied, reply)


@bp.route(route=f"{ROUTE}/gravar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def report_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the report: 422 per field with the form filled, 409 for a stale version."""
    state = _read_state(req)
    try:
        saved = service.save_report(
            session,
            user=context.user,
            scope=context.scope,
            request=_request_of(state),
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
        points = tuple(validation.non_blank_points(state.points))
        refilled = replace(state, errors=errors, points=points)
        return _form_response(req, session, context, refilled, Reply(status_code=422))
    except VersionConflictError as error:
        stale = replace(state, errors={"geral": str(error)})
        return _form_response(req, session, context, stale, Reply(status_code=409))
    verb = "atualizado" if state.report_id is not None else "registrado"
    return AlpineAjaxResponse(
        template_name=SAVED_TEMPLATE,
        context={},
        request=req,
        target_id=MODAL_TARGET,
        toast=SAVED_MESSAGE.format(kind=saved.kind.lower(), name=saved.name, verb=verb),
    )


@bp.route(route=f"{ROUTE}/excluir", methods=["POST"])
@fragment_route(access=MANAGE_ACCESS)
def report_delete(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Delete the report and answer the panel again; the period is pending once more.

    A refusal of the facade (stale version, report gone) comes back as the panel with the
    message as a toast: the person stays where the action started, with the list refreshed.
    """
    form = req.form
    report_filter = _filter_of(form)
    try:
        service.delete_report(
            session,
            user=context.user,
            scope=context.scope,
            report_id=_integer(form.get("id")) or 0,
            version=form.get("versao"),
        )
    except (InvalidDataError, VersionConflictError) as error:
        refused = Reply(toast=str(error), toast_kind="erro")
        return _panel_response(req, session, context, report_filter, refused)
    return _panel_response(req, session, context, report_filter, Reply(toast=DELETED_MESSAGE))


# ── The two exports of the list ────────────────────────────────────────────


@bp.route(route=f"{ROUTE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def report_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of what the list shows: the indicators and the three tables."""
    return excel_response(_document(req, session, context))


@bp.route(route=f"{ROUTE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def report_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of what the list shows: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    report_filter = _filter_of(req.params)
    data = export.ReportExport(
        summary=service.report_summary(
            session, user=context.user, scope=context.scope, reference_date=calendario.today()
        ),
        reports=service.list_reports(
            session, user=context.user, scope=context.scope, report_filter=report_filter
        ),
        kind=report_filter.kind,
    )
    return export.build_document(
        data,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
    )


# ── Answers ────────────────────────────────────────────────────────────────


def _panel_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    report_filter: service.ReportFilter,
    reply: Reply | None = None,
) -> func.HttpResponse:
    reply = reply or Reply()
    summary = service.report_summary(
        session, user=context.user, scope=context.scope, reference_date=calendario.today()
    )
    reports = service.list_reports(
        session, user=context.user, scope=context.scope, report_filter=report_filter
    )
    return AlpineAjaxResponse(
        template_name=PANEL_TEMPLATE,
        context={
            "resumo": summary,
            "linhas": [_row_of(report) for report in reports],
            "textos": _texts_of(summary),
            "situacao": _situation(summary.total, len(reports)),
            "portfolio": context.scope.is_portfolio,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "pode_excluir": rbac.can(context.user, Permission.MANAGE),
        },
        request=req,
        target_id=PANEL_TARGET,
        status_code=reply.status_code,
        toast=reply.toast,
        toast_tipo=reply.toast_kind,
    )


def _row_of(report: service.ReportView) -> dict[str, Any]:
    """A row of the table: the report, when it was saved and its points in words."""
    return {
        "relato": report,
        "atualizado": export.updated_text(report),
        "pontos": calculations.points_summary(report.threats, report.opportunities),
    }


def _texts_of(summary: service.ReportSummary) -> dict[str, str]:
    """The texts of the indicators that carry a count in words."""
    last = summary.last_weekly
    return {
        "pontos": calculations.points_summary(last.threats, last.opportunities) if last else "",
        "contagem": (
            f"{calculations.plural(summary.weekly_total, 'semanal', 'semanais')} · "
            f"{calculations.plural(summary.monthly_total, 'mensal', 'mensais')}"
        ),
    }


def _situation(total: int, shown: int) -> str:
    """The state of the screen the panel reports: ready, empty at the origin or empty by filter."""
    if shown:
        return "pronto"
    return "vazio-origem" if total == 0 else "vazio-filtro"


def _view_response(
    req: func.HttpRequest, context: RequestContext, report: service.ReportView
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=VIEW_TEMPLATE,
        context={
            "relato": report,
            "atualizado": export.updated_text(report),
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
        },
        request=req,
        target_id=MODAL_TARGET,
        root_class=PAGE_CLASS,
    )


def _form_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    state: FormState,
    reply: Reply | None = None,
) -> func.HttpResponse:
    """The form drawn for the state: a new report offers the free periods, an edit shows its own."""
    reply = reply or Reply()
    page = _form_page(session, context, state)
    messages = [text for key, text in state.errors.items() if key not in page["campos"]]
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={**page, "mensagens": messages},
        request=req,
        target_id=MODAL_TARGET,
        root_class=PAGE_CLASS,
        status_code=reply.status_code,
        toast=reply.toast,
        toast_tipo=reply.toast_kind,
    )


def _form_page(session: Session, context: RequestContext, state: FormState) -> dict[str, Any]:
    """What the template of the form needs, for a new report or for the edit of one."""
    page: dict[str, Any] = {
        "estado": state,
        "limites": {
            "linhas": validation.MAX_LINES,
            "linha": validation.MAX_LINE_CHARACTERS,
            "pontos": validation.MAX_POINTS,
            "ponto": validation.MAX_POINT_CHARACTERS,
        },
        "tipos": validation.KINDS,
        "naturezas": validation.NATURES,
        "erros": state.errors,
        "linhas_pontos": _point_rows(state),
        "campos": _field_names(state),
    }
    if state.report_id is None:
        kind = state.kind if state.kind in validation.KINDS else validation.WEEKLY
        choices = service.period_choices(
            session,
            user=context.user,
            scope=context.scope,
            kind=kind,
            reference_date=calendario.today(),
        )
        page.update(
            novo=True,
            tipo=kind,
            projeto=choices.project_label,
            opcoes=choices.options,
            periodo=calculations.choose_period(choices.options, state.period),
        )
        return page
    report = service.get_report(
        session, user=context.user, scope=context.scope, report_id=state.report_id
    )
    page.update(novo=False, relato=report, tipo=report.kind, projeto=report.project_label)
    return page


def _point_rows(state: FormState) -> list[dict[str, Any]]:
    """The points as the template draws them: the values and the messages of each row."""
    return [
        {
            "indice": index,
            "ponto": point,
            "erros": {
                name: state.errors.get(validation.point_field(index, name))
                for name in ("descricao", "natureza", "risco")
            },
        }
        for index, point in enumerate(state.points)
    ]


def _field_names(state: FormState) -> set[str]:
    """The fields of the form that show their own message; any other goes to the top of it."""
    names = {
        validation.FIELD_KIND,
        validation.FIELD_PERIOD,
        validation.FIELD_ACTIVITIES,
        validation.FIELD_NEXT_ACTIVITIES,
        validation.FIELD_POINTS,
    }
    for index in range(len(state.points)):
        names.update(
            validation.point_field(index, name) for name in ("descricao", "natureza", "risco")
        )
    return names


# ── Reading the request ────────────────────────────────────────────────────


def _filter_of(values: Mapping[str, str]) -> service.ReportFilter:
    """The filter of the list from the query or the form: a type that is not one means all."""
    kind = values.get("tipo", "")
    return service.ReportFilter(
        kind=kind if kind in validation.KINDS else "", search=values.get("busca", "").strip()
    )


def _integer(value: str | None) -> int | None:
    """The number in a field, or ``None`` when it is empty or not one."""
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _read_state(req: func.HttpRequest) -> FormState:
    form = req.form
    return FormState(
        report_id=_integer(form.get("id")),
        version=form.get("versao", ""),
        kind=form.get("tipo", ""),
        period=form.get("periodo", ""),
        activities=form.get("atividades_periodo", ""),
        next_activities=form.get("atividades_proximo", ""),
        points=_read_points(form),
    )


def _read_points(form: Mapping[str, str]) -> tuple[PointInput, ...]:
    """The rows of points of the form, in the order of the form and as typed."""
    indexes = sorted({int(found[1]) for key in form if (found := _POINT_FIELD.fullmatch(key))})
    return tuple(
        PointInput(
            description=form.get(validation.point_field(index, "descricao"), ""),
            nature=form.get(validation.point_field(index, "natureza"), ""),
            risk=form.get(validation.point_field(index, "risco"), ""),
        )
        for index in indexes[:MAX_POINT_ROWS]
    )


def _request_of(state: FormState) -> service.SaveRequest:
    return service.SaveRequest(
        draft=service.ReportDraft(
            kind=state.kind,
            period=state.period,
            activities=tuple(state.activities.splitlines()),
            next_activities=tuple(state.next_activities.splitlines()),
            points=state.points,
        ),
        report_id=state.report_id,
        version=state.version or None,
    )


def _state_of(report: service.ReportView) -> FormState:
    """The form of an existing report: its texts one per line, and its points."""
    return FormState(
        report_id=report.id,
        version=str(report.version),
        kind=report.kind,
        period=report.period,
        activities="\n".join(report.activities),
        next_activities="\n".join(report.next_activities),
        points=report.points,
    )


def _kind_of(session: Session, context: RequestContext, state: FormState) -> str:
    """The type of the report the form is about: the report's own when it is an edit."""
    if state.report_id is None:
        return state.kind
    return service.get_report(
        session, user=context.user, scope=context.scope, report_id=state.report_id
    ).kind


MODULE = "planejamento"


BASE = "planejamento/6wla"


API_BASE = f"/api/{BASE}"


SCREEN_TEMPLATE = "planejamento/6wla.html"


LOOKAHEAD_FORM_TEMPLATE = "planejamento/6wla_formulario.html"


ANSWER_TEMPLATE = "planejamento/6wla_resposta.html"


ACTIVITY_FORM = "planejamento/6wla_form_atividade.html"


CONSTRAINT_FORM = "planejamento/6wla_form_restricao.html"


REMOVAL_FORM = "planejamento/6wla_form_remocao.html"


INVALID_ID_MESSAGE = "O endereço não indica um registro válido."


TRUE_VALUES = frozenset({"1", "on", "true"})


CONSTRAINT_LISTS = {
    service.OPEN_CONSTRAINTS: "Abertas",
    service.ALL_CONSTRAINTS: "Todas",
}


@dataclass(frozen=True)
class FormScreen:
    """A form of the 6WLA: which fragment draws it, where it posts and what it shows."""

    template: str
    title: str
    action: str
    values: Mapping[str, Any]
    errors: Mapping[str, str] = field(default_factory=dict)
    subtitle: str = ""
    message: str = ""
    weeks: tuple[str, ...] = ()
    activity: service.ActivityView | None = None
    activities: tuple[service.ActivityView, ...] = ()
    status_code: int = 200


# ── The screen and the exports ───────────────────────────────────────────


@bp.route(route=BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def lookahead_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Filters and content of the 6WLA for the scope and the filters of the request."""
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context=_board_context(req, session, context),
        request=req,
    )


@bp.route(route=f"{BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def lookahead_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the board the screen shows (same filters)."""
    return excel_response(_lookahead_document(req, session, context))


@bp.route(route=f"{BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def lookahead_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the board: what the PDF button mounts and prints."""
    return printable_response(_lookahead_document(req, session, context), req)


def _filters_of(req: func.HttpRequest) -> service.LookaheadFilter:
    params = req.params
    constraints = params.get("restricoes") or service.OPEN_CONSTRAINTS
    return service.LookaheadFilter(
        search=(params.get("busca") or "").strip(),
        discipline=(params.get("disciplina") or "").strip(),
        only_with_open_constraint=(params.get("so_restricao") or "") in TRUE_VALUES,
        constraints=constraints if constraints in CONSTRAINT_LISTS else service.OPEN_CONSTRAINTS,
    )


def _board_context(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: service.LookaheadFilter | None = None,
) -> dict[str, Any]:
    """What the screen fragments print: the board, the filters, the Gantt and the Galeria."""
    chosen = filters if filters is not None else _filters_of(req)
    reference_date = calendario.today()
    board = service.lookahead_board(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=reference_date,
        filters=chosen,
    )
    return {
        "board": board,
        "filtros": chosen,
        "disciplinas": configuracoes.list_discipline_names(session),
        "listas_de_restricoes": CONSTRAINT_LISTS,
        "gantt": export.gantt_data(board),
        "galeria": export.gallery_data(board.constraints),
        "legenda_semana": export.week_caption,
        "horizonte": export.horizon_text(board),
        "indice_de_remocao": format_value(ValueKind.PERCENT, board.figures.removal_index, 0) or "·",
        "api": API_BASE,
    }


def _lookahead_document(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    filters = _filters_of(req)
    board = service.lookahead_board(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
        filters=filters,
    )
    return export.lookahead_document(
        board,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        constraints_label=CONSTRAINT_LISTS[filters.constraints],
    )


# ── The forms ────────────────────────────────────────────────────────────


@bp.route(route=f"{BASE}/atividades/nova", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_new_activity_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The empty activity form; in the Portfólio it asks for a project first."""
    context.scope.require_project()
    screen = FormScreen(
        template=ACTIVITY_FORM,
        title="Nova atividade",
        action=f"{API_BASE}/atividades",
        values={},
    )
    return _lookahead_form_response(req, session, screen)


@bp.route(route=f"{BASE}/atividades/{{atividade_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_edit_activity_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The activity form filled with the activity and the version the screen opens."""
    activity = _find_activity(session, context, _route_id(req, "atividade_id"))
    screen = FormScreen(
        template=ACTIVITY_FORM,
        title=f"Editar {activity.code}",
        action=f"{API_BASE}/atividades/{activity.id}",
        values=service.activity_fields(activity),
        weeks=_marked(activity),
        activity=activity,
    )
    return _lookahead_form_response(req, session, screen)


@bp.route(route=f"{BASE}/restricoes/nova", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_new_constraint_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The empty restriction form; ``?atividade=`` preselects the activity."""
    screen = _constraint_screen(session, context, values={"atividade": req.params.get("atividade")})
    return _lookahead_form_response(req, session, screen)


@bp.route(route=f"{BASE}/restricoes/{{restricao_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_edit_constraint_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The restriction form filled with the restriction and the version the screen opens."""
    constraint = _find_constraint(session, context, _route_id(req, "restricao_id"))
    screen = FormScreen(
        template=CONSTRAINT_FORM,
        title=f"Editar restrição de {constraint.activity_code}",
        action=f"{API_BASE}/restricoes/{constraint.id}",
        values=service.constraint_fields(constraint),
        activity=_find_activity(session, context, constraint.activity_id),
    )
    return _lookahead_form_response(req, session, screen)


@bp.route(route=f"{BASE}/restricoes/{{restricao_id}}/remover", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_removal_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The removal form: the date (today by default) and how the restriction was removed."""
    constraint = _find_constraint(session, context, _route_id(req, "restricao_id"))
    screen = FormScreen(
        template=REMOVAL_FORM,
        title="Remover restrição",
        action=f"{API_BASE}/restricoes/{constraint.id}/remocao",
        values={
            "remocao": calendario.today().isoformat(),
            "versao": str(constraint.version),
        },
        activity=_find_activity(session, context, constraint.activity_id),
        subtitle=f"{constraint.activity_code} · {constraint.description}",
    )
    return _lookahead_form_response(req, session, screen)


def _constraint_screen(
    session: Session, context: RequestContext, *, values: Mapping[str, Any]
) -> FormScreen:
    board = service.lookahead_board(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
        filters=service.LookaheadFilter(),
    )
    return FormScreen(
        template=CONSTRAINT_FORM,
        title="Nova restrição",
        action=f"{API_BASE}/restricoes",
        values={key: value for key, value in values.items() if value},
        activities=board.activities,
    )


def _lookahead_form_response(
    req: func.HttpRequest, session: Session, screen: FormScreen
) -> func.HttpResponse:
    """The form alone, for the request that opens it (target: the form block)."""
    return AlpineAjaxResponse(
        template_name=LOOKAHEAD_FORM_TEMPLATE,
        context=_form_context(session, screen),
        request=req,
        status_code=screen.status_code,
    )


def _form_context(session: Session, screen: FormScreen) -> dict[str, Any]:
    return {
        "formulario": screen,
        "opcoes": service.form_options(session, reference_date=calendario.today()),
    }


# ── The writes ───────────────────────────────────────────────────────────


@bp.route(route=f"{BASE}/atividades", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_create_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Include the activity; the answer is the refreshed screen, or the form with the messages."""
    screen = FormScreen(
        template=ACTIVITY_FORM,
        title="Nova atividade",
        action=f"{API_BASE}/atividades",
        values=_values_of(req),
        weeks=tuple(req.form.getlist("semanas")),
    )

    def save() -> str:
        record = service.create_activity(
            session, user=context.user, scope=context.scope, form=_activity_form_of(req)
        )
        return f"Atividade {record.code} incluída."

    return _save(req, session, context, screen=screen, save=save)


@bp.route(route=f"{BASE}/atividades/{{atividade_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_update_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Edit the activity; 409 when someone saved it since the screen opened it."""
    activity_id = _route_id(req, "atividade_id")
    screen = FormScreen(
        template=ACTIVITY_FORM,
        title="Editar atividade",
        action=f"{API_BASE}/atividades/{activity_id}",
        values=_values_of(req),
        weeks=tuple(req.form.getlist("semanas")),
        activity=_find_activity(session, context, activity_id),
    )

    def save() -> str:
        record = service.update_activity(
            session,
            user=context.user,
            scope=context.scope,
            activity_id=activity_id,
            form=_activity_form_of(req),
        )
        return f"Atividade {record.code} atualizada."

    return _save(req, session, context, screen=screen, save=save)


@bp.route(route=f"{BASE}/restricoes", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_create_constraint(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the restriction on the chosen activity."""
    screen = _constraint_screen(session, context, values=_values_of(req))

    def save() -> str:
        service.create_constraint(
            session, user=context.user, scope=context.scope, raw=_values_of(req)
        )
        return "Restrição registrada."

    return _save(req, session, context, screen=screen, save=save)


@bp.route(route=f"{BASE}/restricoes/{{restricao_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_update_constraint(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Edit the restriction; 409 when someone saved it since the screen opened it."""
    constraint_id = _route_id(req, "restricao_id")
    constraint = _find_constraint(session, context, constraint_id)
    screen = FormScreen(
        template=CONSTRAINT_FORM,
        title=f"Editar restrição de {constraint.activity_code}",
        action=f"{API_BASE}/restricoes/{constraint_id}",
        values=_values_of(req),
        activity=_find_activity(session, context, constraint.activity_id),
    )

    def save() -> str:
        service.update_constraint(
            session,
            user=context.user,
            scope=context.scope,
            constraint_id=constraint_id,
            raw=_values_of(req),
        )
        return "Restrição atualizada."

    return _save(req, session, context, screen=screen, save=save)


@bp.route(route=f"{BASE}/restricoes/{{restricao_id}}/remocao", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_remove_constraint(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the removal of the restriction."""
    constraint_id = _route_id(req, "restricao_id")
    constraint = _find_constraint(session, context, constraint_id)
    screen = FormScreen(
        template=REMOVAL_FORM,
        title="Remover restrição",
        action=f"{API_BASE}/restricoes/{constraint_id}/remocao",
        values=_values_of(req),
        activity=_find_activity(session, context, constraint.activity_id),
        subtitle=f"{constraint.activity_code} · {constraint.description}",
    )

    def save() -> str:
        service.remove_constraint(
            session,
            user=context.user,
            scope=context.scope,
            constraint_id=constraint_id,
            raw=_values_of(req),
        )
        return "Restrição removida."

    return _save(req, session, context, screen=screen, save=save)


def _save(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    screen: FormScreen,
    save: Callable[[], str],
) -> func.HttpResponse:
    """Run the write and answer the three blocks: refreshed on success, form with messages if not."""
    try:
        notice = save()
    except InvalidDataError as error:
        return _answer(req, session, context, screen=_with_error(screen, error, 422))
    except VersionConflictError as error:
        return _answer(
            req, session, context, screen=_with_error(screen, InvalidDataError(str(error)), 409)
        )
    return _answer(req, session, context, screen=None, notice=notice)


def _with_error(screen: FormScreen, error: InvalidDataError, status_code: int) -> FormScreen:
    detail = error.detail
    errors = dict(detail) if isinstance(detail, Mapping) else {}
    return FormScreen(
        template=screen.template,
        title=screen.title,
        action=screen.action,
        values=screen.values,
        errors=errors,
        subtitle=screen.subtitle,
        message="" if errors else str(error),
        weeks=screen.weeks,
        activity=screen.activity,
        activities=screen.activities,
        status_code=status_code,
    )


def _answer(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    screen: FormScreen | None,
    notice: str | None = None,
) -> func.HttpResponse:
    """Form, filters and content in one answer; the filters come back reset to the default."""
    page = _board_context(req, session, context, filters=service.LookaheadFilter())
    page.update(_form_context(session, screen) if screen else {"formulario": None})
    failed = screen is not None
    return AlpineAjaxResponse(
        template_name=ANSWER_TEMPLATE,
        context=page,
        request=req,
        status_code=screen.status_code if screen else 200,
        toast=None if failed else notice,
        toast_tipo="ok",
    )


# ── The request ──────────────────────────────────────────────────────────


def _values_of(req: func.HttpRequest) -> dict[str, str]:
    """The text fields the form sent, as they were typed."""
    return {key: value for key, value in req.form.items() if isinstance(value, str)}


def _activity_form_of(req: func.HttpRequest) -> validation.ActivityForm:
    return validation.ActivityForm(fields=_values_of(req), weeks=req.form.getlist("semanas"))


def _route_id(req: func.HttpRequest, name: str) -> int:
    found = validation.parse_id(req.route_params.get(name))
    if found is None:
        raise InvalidDataError(INVALID_ID_MESSAGE)
    return found


def _marked(activity: service.ActivityView) -> tuple[str, ...]:
    return tuple(str(index) for index, planned in enumerate(activity.planned) if planned)


def _find_activity(
    session: Session, context: RequestContext, activity_id: int
) -> service.ActivityView:
    return service.find_activity(
        session, scope=context.scope, activity_id=activity_id, reference_date=calendario.today()
    )


def _find_constraint(
    session: Session, context: RequestContext, constraint_id: int
) -> service.ConstraintView:
    return service.find_constraint(
        session,
        scope=context.scope,
        constraint_id=constraint_id,
        reference_date=calendario.today(),
    )


# ── EAP: árvore, dicionário e carteira (ISSUE-036) ───────────────────────

EAP_BASE = "planejamento/eap"


EAP_TEMPLATE = "planejamento/eap.html"


EAP_DICTIONARY_FORM_TEMPLATE = "planejamento/eap_dicionario_form.html"


EAP_DICTIONARY_SAVED_TEMPLATE = "planejamento/eap_dicionario_salvo.html"


EAP_CONTENT_TARGET = "eap-conteudo"


EAP_FORM_TARGET = "eap-formulario"


EAP_ITEM_PARAMETER = "item_id"


EAP_SAVED_MESSAGE = "Pacote {code} atualizado."


EAP_KPI_ICONS = ("chartLine", "layers", "warning", "file")


EAP_BAND_TONES = {"success": "ok", "warning": "warn", "danger": "erro", None: "neutral"}


EAP_SITUATION_TONES = {"ok": "ok", "warn": "warn", "erro": "erro", "neutro": "neutral"}


@dataclass(frozen=True)
class EapKpiLine:
    """Um indicador da faixa do topo, já escrito como a pessoa o lê."""

    rotulo: str
    valor: str
    referencia: str
    situacao: str
    tom: str
    icone: str


@dataclass(frozen=True)
class EapNodeLine:
    """Uma linha da árvore: o nó e os textos de cada coluna, prontos para o fragmento."""

    no: service.EapNode
    peso: str
    peso_no_pai: str
    previsto: str
    real: str
    desvio: str
    tom: str
    criterio: str
    inicio: str
    termino: str
    situacao: str
    tom_situacao: str
    has_children: bool = False
    real_num: str = "0"


@dataclass(frozen=True)
class EapMeasurementLine:
    """Uma medição do dicionário: quando, de quanto para quanto, quem e a nota."""

    quando: str
    de: str
    para: str
    autor: str
    nota: str
    estorno: bool


@bp.route(route=EAP_BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eap_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A EAP do escopo: indicadores, árvore, revisões e desdobramentos da revisão vigente."""
    return AlpineAjaxResponse(
        template_name=EAP_TEMPLATE,
        context=_eap_content_context(_eap_overview(session, context)),
        request=req,
    )


@bp.route(route=f"{EAP_BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def eap_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da EAP: indicadores, árvore, revisões e desdobramentos, no escopo do pedido."""
    del req
    return excel_response(_eap_document(session, context))


@bp.route(route=f"{EAP_BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eap_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da EAP: o mesmo documento que o Excel carrega."""
    return printable_response(_eap_document(session, context), req)


@bp.route(route=f"{EAP_BASE}/itens/{{item_id}}/dicionario", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eap_dictionary_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do dicionário do pacote, com os valores vigentes e as listas do cadastro."""
    node = _dictionary_node(req, session, context)
    return AlpineAjaxResponse(
        template_name=EAP_DICTIONARY_FORM_TEMPLATE,
        context=_dictionary_page(session, context, node),
        request=req,
    )


@bp.route(route=f"{EAP_BASE}/itens/{{item_id}}/dicionario", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_dictionary_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava o dicionário: 422 por campo e 409 de versão vencida voltam com o conteúdo junto."""
    item_id = _route_id(req, EAP_ITEM_PARAMETER)
    try:
        item = service.update_dictionary(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=req.form,
        )
    except (InvalidDataError, VersionConflictError) as error:
        return _dictionary_error(req, session, context, item_id, error)
    data = _saved_content_context(session, context)
    return AlpineAjaxResponse(
        template_name=EAP_DICTIONARY_SAVED_TEMPLATE,
        context=data,
        request=req,
        toast=EAP_SAVED_MESSAGE.format(code=item.code),
    )


# ── Avanço do pacote (ISSUE-037) ─────────────────────────────────────────


EAP_PROGRESS_FORM_TEMPLATE = "planejamento/eap_avanco_form.html"


EAP_PROGRESS_SAVED_TEMPLATE = "planejamento/eap_avanco_salvo.html"


EAP_PROGRESS_IMPORT_FORM_TEMPLATE = "planejamento/eap_importacao_form.html"


EAP_PROGRESS_IMPORT_BASE = f"{EAP_BASE}/importar"


EAP_PROGRESS_IMPORT_TARGET = "eap-importacao-resultado"


EAP_PROGRESS_MESSAGE = "Avanço de {code} registrado: {from_pct} para {to_pct}."


IMPORT_CHECKED_FIELD = "conferido"


IMPORT_ACKNOWLEDGED_FIELD = "ciente"


IMPORT_ACKNOWLEDGED_VALUE = "sim"


_IMPORT_NUMERIC_KINDS = frozenset(
    {ValueKind.INTEGER, ValueKind.DECIMAL, ValueKind.PERCENT, ValueKind.MONEY}
)


@bp.route(route=f"{EAP_BASE}/itens/{{item_id}}/avanco", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eap_progress_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do avanço do pacote, com as entradas do seu critério e a data de hoje."""
    node = _progress_node(session, context, _route_id(req, EAP_ITEM_PARAMETER))
    return AlpineAjaxResponse(
        template_name=EAP_PROGRESS_FORM_TEMPLATE,
        context=_progress_page(node),
        request=req,
    )


@bp.route(route=f"{EAP_BASE}/itens/{{item_id}}/avanco", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_progress_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o avanço: 422 por campo, 403 do estorno e 409 de versão vencida voltam com o form."""
    item_id = _route_id(req, EAP_ITEM_PARAMETER)
    try:
        registered = service.register_progress(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=req.form,
            reference_date=calendario.today(),
        )
    except (InvalidDataError, AccessDeniedError, VersionConflictError) as error:
        return _progress_error(req, session, context, item_id, error)
    return AlpineAjaxResponse(
        template_name=EAP_PROGRESS_SAVED_TEMPLATE,
        context=_saved_content_context(session, context),
        request=req,
        toast=EAP_PROGRESS_MESSAGE.format(
            code=registered.code,
            from_pct=format_value(ValueKind.PERCENT, registered.from_pct, 1),
            to_pct=format_value(ValueKind.PERCENT, registered.to_pct, 1),
        ),
    )


def _progress_node(session: Session, context: RequestContext, item_id: int) -> service.EapNode:
    """O pacote de trabalho do escopo que pode receber medição; o de planejamento é recusado."""
    node = service.dictionary_node(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        reference_date=calendario.today(),
    )
    if node.is_planning_package:
        raise InvalidDataError(service.PLANNING_PACKAGE_PROGRESS_MESSAGE)
    return node


def _progress_page(
    node: service.EapNode,
    *,
    values: Mapping[str, str] | None = None,
    errors: Mapping[str, str] | None = None,
    message: str = "",
) -> dict[str, Any]:
    """O que o formulário do avanço precisa: o nó, os valores, as entradas e as mensagens."""
    return {
        "no": node,
        "valores": _progress_fields(node) if values is None else values,
        "erros": dict(errors or {}),
        "mensagem": message,
        "hoje": calendario.today().isoformat(),
        "estados": _milestone_states(node.criterion),
        "criterio": export.eap_criterion_text(node),
        "peso": format_value(ValueKind.PERCENT, node.weight),
        "previsto": format_value(ValueKind.PERCENT, node.predicted, 1),
        "real": format_value(ValueKind.PERCENT, node.actual, 1),
        "formulario": True,
        "alvo_conteudo": EAP_CONTENT_TARGET,
        "alvo_formulario": EAP_FORM_TARGET,
    }


def _progress_fields(node: service.EapNode) -> dict[str, str]:
    """Os valores iniciais do formulário do avanço: a data de hoje e as entradas correntes."""
    values = {
        "data": calendario.today().isoformat(),
        "versao": str(node.version),
        "obs": "",
        "justificativa": "",
        "executado": _plain_decimal(node.executed),
        "estado": node.state or "",
        "estimadoPct": _plain_decimal(node.estimated_pct),
    }
    for index, step in enumerate(node.steps):
        values[f"etapa{index}"] = _plain_decimal(step.pct)
    return values


def _milestone_states(criterion: str | None) -> tuple[str, ...]:
    """As situações que o marco aceita; as demais entradas do form não usam a lista."""
    if criterion == calculations.CRITERION_MILESTONE_0_100:
        return calculations.MILESTONE_0_100_STATES
    if criterion == calculations.CRITERION_MILESTONE_50_50:
        return calculations.MILESTONE_50_50_STATES
    return ()


def _plain_decimal(value: Decimal | None) -> str:
    """O número sem zeros à direita: ``90.0000`` vira ``90`` e ``0`` continua ``0``."""
    if value is None:
        return ""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _progress_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    item_id: int,
    error: InvalidDataError | AccessDeniedError | VersionConflictError,
) -> func.HttpResponse:
    """A gravação recusada: o conteúdo atualizado e o formulário preenchido com o digitado."""
    node = _progress_node(session, context, item_id)
    errors: Mapping[str, str] = (
        error.detail
        if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping)
        else {}
    )
    data = _eap_content_context(_eap_overview(session, context))
    data.update(_progress_page(node, values=req.form, errors=errors, message=str(error)))
    return AlpineAjaxResponse(
        template_name=EAP_PROGRESS_SAVED_TEMPLATE,
        context=data,
        request=req,
        status_code=_error_status(error),
        toast=str(error),
        toast_tipo="erro",
    )


def _error_status(error: InvalidDataError | AccessDeniedError | VersionConflictError) -> int:
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


# ── Importação do avanço (ISSUE-037) ─────────────────────────────────────


@bp.route(route=f"{EAP_PROGRESS_IMPORT_BASE}/formulario", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eap_progress_import_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da importação do avanço: a data da medição e a planilha."""
    del session
    context.scope.require_project()
    importer = importers.progress_importer()
    return AlpineAjaxResponse(
        template_name=EAP_PROGRESS_IMPORT_FORM_TEMPLATE,
        context={
            "titulo": importer.title,
            "campo_arquivo": attachments.FILE_FIELD,
            "limite_mb": MAX_FILE_BYTES // MEGABYTE,
            "limite_linhas": format_value(ValueKind.INTEGER, MAX_DATA_ROWS),
            "modelo_url": f"/api/importacao/{importer.key}/modelo",
            "conferir_url": f"/api/{EAP_PROGRESS_IMPORT_BASE}/conferir",
            "data": calendario.today().isoformat(),
            "alvo_resultado": EAP_PROGRESS_IMPORT_TARGET,
        },
        request=req,
    )


@bp.route(route=f"{EAP_PROGRESS_IMPORT_BASE}/conferir", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_progress_import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Lê a planilha e responde o que cada linha vai gravar; nada é escrito."""
    measurement_date = _import_measurement_date(req)
    preview = importing.check(
        session,
        importer=importers.progress_importer(),
        upload=_upload_of(req),
        context=_import_context(context, measurement_date),
    )
    return AlpineAjaxResponse(
        template_name="comum/importacao_conferencia.html",
        context=_progress_import_check_context(preview),
        request=req,
    )


@bp.route(route=f"{EAP_PROGRESS_IMPORT_BASE}/confirmar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_progress_import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Checa a planilha de novo e grava o avanço das linhas sem erro, só na confirmação."""
    measurement_date = _import_measurement_date(req)
    importer = importers.progress_importer()
    result = importing.confirm(
        session,
        importer=importer,
        upload=_upload_of(req),
        context=_import_context(context, measurement_date),
        confirmation=importing.Confirmation(
            checked_digest=(req.form.get(IMPORT_CHECKED_FIELD) or "").strip() or None,
            acknowledged=req.form.get(IMPORT_ACKNOWLEDGED_FIELD) == IMPORT_ACKNOWLEDGED_VALUE,
        ),
    )
    return AlpineAjaxResponse(
        template_name="comum/importacao_resultado.html",
        context={"resultado": result, "importador": importer.title},
        request=req,
        toast=_progress_import_notice(result),
        toast_tipo="aviso" if result.skipped else "ok",
    )


def _import_measurement_date(req: func.HttpRequest) -> date:
    """A data da medição do formulário; uma data futura é recusada antes de ler a planilha."""
    text = (req.form.get(validation.FIELD_MEASURED_ON) or "").strip()
    try:
        found = date.fromisoformat(text)
    except ValueError as error:
        raise InvalidDataError(
            {validation.FIELD_MEASURED_ON: validation.MEASUREMENT_DATE_REQUIRED_MESSAGE}
        ) from error
    if found > calendario.today():
        raise InvalidDataError(
            {validation.FIELD_MEASURED_ON: validation.MEASUREMENT_DATE_FUTURE_MESSAGE}
        )
    return found


def _import_context(context: RequestContext, measurement_date: date) -> importing.ImportContext:
    """Quem importa, em que escopo e na data da medição: as regras do importador recebem essa data."""
    return importing.ImportContext(
        user=context.user, scope=context.scope, reference_date=measurement_date
    )


def _upload_of(req: func.HttpRequest) -> importing.Upload:
    """O arquivo do formulário; no máximo um byte acima do limite é lido, como no mecanismo genérico."""
    sent = req.files.get(attachments.FILE_FIELD)
    if sent is None:
        return importing.Upload(name=None, content=b"")
    return importing.Upload(name=sent.filename, content=sent.stream.read(MAX_FILE_BYTES + 1))


def _progress_import_check_context(preview: importing.ImportPreview) -> dict[str, Any]:
    """O que o fragmento da conferência imprime: a prévia, as colunas e onde confirmar."""
    return {
        "arquivo": preview.file_name,
        "preview": preview,
        "colunas": [
            {"cabecalho": column.header, "numerica": column.kind in _IMPORT_NUMERIC_KINDS}
            for column in preview.columns
        ],
        "lidas": len(preview.rows),
        "vao_gravar": len(preview.writable_rows),
        "com_aviso": len(preview.warning_rows),
        "com_erro": len(preview.error_rows),
        "campo_conferido": IMPORT_CHECKED_FIELD,
        "campo_ciente": IMPORT_ACKNOWLEDGED_FIELD,
        "valor_ciente": IMPORT_ACKNOWLEDGED_VALUE,
        "confirmar_url": f"/api/{EAP_PROGRESS_IMPORT_BASE}/confirmar",
    }


def _progress_import_notice(result: importing.ImportResult) -> str:
    """O aviso da confirmação: quantas linhas entraram e quantas ficaram de fora."""
    written = len(result.written)
    imported = "1 linha importada" if written == 1 else f"{written} linhas importadas"
    if not result.skipped:
        return f"{imported}."
    skipped = len(result.skipped)
    left_out = "1 com erro não entrou" if skipped == 1 else f"{skipped} com erro não entraram"
    return f"{imported}; {left_out}."


# ── Montagem das respostas da EAP ────────────────────────────────────────


def _eap_overview(session: Session, context: RequestContext) -> service.EapOverview:
    """A EAP do escopo do pedido; a única leitura da rota que vê o relógio."""
    return service.eap_overview(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
    )


def _eap_document(session: Session, context: RequestContext) -> Document:
    return export.eap_document(
        _eap_overview(session, context),
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _eap_content_context(visao: service.EapOverview) -> dict[str, Any]:
    """O que os fragmentos da EAP imprimem: a visão, os indicadores e as linhas da árvore."""
    return {
        "visao": visao,
        "kpis": _eap_kpi_lines(visao),
        "linhas": _eap_node_lines(visao),
        "situacao": "vazio-origem" if visao.is_empty else "conteudo",
        "pode_editar": visao.can_edit,
        "alvo_conteudo": EAP_CONTENT_TARGET,
        "alvo_formulario": EAP_FORM_TARGET,
    }


def _eap_kpi_lines(visao: service.EapOverview) -> list[EapKpiLine]:
    return [
        EapKpiLine(
            rotulo=kpi.label,
            valor=format_value(kpi.kind, kpi.value, kpi.digits),
            referencia=kpi.reference,
            situacao=kpi.status,
            tom=kpi.tone.value if kpi.tone else "neutro",
            icone=icone,
        )
        for kpi, icone in zip(export.eap_kpis(visao), EAP_KPI_ICONS, strict=True)
    ]


def _eap_node_lines(visao: service.EapOverview) -> list[EapNodeLine]:
    codes = [node.code for node in visao.nodes]
    return [_eap_node_line(node, has_children=_has_children(node, codes)) for node in visao.nodes]


def _has_children(node: service.EapNode, codes: Sequence[str]) -> bool:
    """Se a linha abre: a raiz quando a árvore tem mais de uma, as demais pelo prefixo do código."""
    if node.level == service.LEVEL_ROOT:
        return len(codes) > 1
    return any(code.startswith(f"{node.code}.") for code in codes)


def _eap_node_line(node: service.EapNode, *, has_children: bool) -> EapNodeLine:
    situation_tone = export.eap_situation_tone(node)
    return EapNodeLine(
        no=node,
        peso=format_value(ValueKind.PERCENT, node.weight),
        peso_no_pai=(
            ""
            if node.weight_in_parent is None
            else format_value(ValueKind.PERCENT, node.weight_in_parent, 1)
        ),
        previsto=format_value(ValueKind.PERCENT, node.predicted, 1),
        real=("" if node.is_planning_package else format_value(ValueKind.PERCENT, node.actual, 1)),
        desvio="" if node.is_planning_package else export.eap_deviation_text(node.deviation_pp),
        tom=EAP_BAND_TONES.get(node.band, "neutral"),
        criterio=export.eap_criterion_text(node),
        inicio=format_value(ValueKind.DATE, node.start),
        termino=format_value(ValueKind.DATE, node.finish),
        situacao=export.eap_situation_text(node),
        tom_situacao=(
            "" if situation_tone is None else EAP_SITUATION_TONES.get(situation_tone.value, "")
        ),
        has_children=has_children,
        real_num=str(node.actual),
    )


def _dictionary_node(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> service.EapNode:
    return service.dictionary_node(
        session,
        user=context.user,
        scope=context.scope,
        item_id=_route_id(req, EAP_ITEM_PARAMETER),
        reference_date=calendario.today(),
    )


def _dictionary_page(
    session: Session,
    context: RequestContext,
    node: service.EapNode,
    *,
    values: Mapping[str, str] | None = None,
    errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """O que o formulário do dicionário precisa: o nó, os valores, as listas e as mensagens."""
    options = service.dictionary_options(session, project_id=context.scope.require_project())
    return {
        "no": node,
        "opcoes": options,
        "valores": service.dictionary_fields(node) if values is None else values,
        "erros": dict(errors or {}),
        "medicoes": _measurement_lines(node),
        "mensagem": "",
        "peso": format_value(ValueKind.PERCENT, node.weight),
        "inicio": format_value(ValueKind.DATE, node.start),
        "termino": format_value(ValueKind.DATE, node.finish),
        "criterio": export.eap_criterion_text(node),
        "formulario": True,
        "alvo_conteudo": EAP_CONTENT_TARGET,
        "alvo_formulario": EAP_FORM_TARGET,
    }


def _measurement_lines(node: service.EapNode) -> list[EapMeasurementLine]:
    """As medições do pacote, da mais nova para a mais antiga, como o dicionário as lê."""
    return [
        EapMeasurementLine(
            quando=format_value(ValueKind.DATE, medicao.measured_on),
            de=format_value(ValueKind.PERCENT, medicao.from_pct, 1),
            para=format_value(ValueKind.PERCENT, medicao.to_pct, 1),
            autor=medicao.author,
            nota=medicao.note,
            estorno=medicao.is_reversal,
        )
        for medicao in reversed(node.measurements)
    ]


def _saved_content_context(session: Session, context: RequestContext) -> dict[str, Any]:
    """O conteúdo atualizado e o formulário fechado: a resposta multi-alvo da gravação."""
    data = _eap_content_context(_eap_overview(session, context))
    data["formulario"] = None
    return data


def _dictionary_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    item_id: int,
    error: InvalidDataError | VersionConflictError,
) -> func.HttpResponse:
    """A gravação recusada: o conteúdo volta atualizado e o formulário, preenchido com o digitado."""
    node = service.dictionary_node(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        reference_date=calendario.today(),
    )
    errors: Mapping[str, str] = (
        error.detail
        if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping)
        else {}
    )
    data = _eap_content_context(_eap_overview(session, context))
    data.update(_dictionary_page(session, context, node, values=req.form, errors=errors))
    data["mensagem"] = str(error)
    return AlpineAjaxResponse(
        template_name=EAP_DICTIONARY_SAVED_TEMPLATE,
        context=data,
        request=req,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )
