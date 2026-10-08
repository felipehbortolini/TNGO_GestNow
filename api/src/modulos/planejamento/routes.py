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
* ``GET  /pacotes/novo``, ``POST /pacotes``  the new package: the breakdown of a planning
  package or the inclusion by a new revision (ISSUE-038);
* ``GET  /revisoes/nova``, ``POST /revisoes``  the revision that adjusts one package from an
  approved change request with scope impact (Gestor);
* ``GET  /pacotes/importar/formulario``, ``POST /pacotes/importar/conferir`` and
  ``POST /pacotes/importar/confirmar``  the spreadsheet import of the packages (the
  ``eap-pacotes`` importer), whose confirmation creates the revision bound to the change
  request: the generic confirmation refuses, the module is the writer (like the EAC import);
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same content.

The physical S-curve (ISSUE-039), prefix ``/api/planejamento/curva-fisica``:

* ``GET  /``  the screen: the indicators, the weekly curve (D11), the month-by-month table and,
  in the read-only Portfólio, the composition of the portfolio with the ``Projeto`` column;
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same content, with the chart.

The planning KPIs (ISSUE-040), prefix ``/api/planejamento/kpis``:

* ``GET  /``  the screen: the indicators with their management reference, the SPI per month and
  the forecast x actual charts (D11) and the advance per area — per project in the Portfólio,
  with the ``Projeto`` column — with the weighted closing row;
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same content, with the charts.

The productivity (ISSUE-046, HU-065), prefix ``/api/planejamento/produtividade``:

* ``GET  /``  the screen: the global filters (``empresa``, ``corte``, ``grupo``) and the
  Quantidades tab — indicators, groups, the two charts of the DS library and the plan table;
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same content, with the filter;
* ``GET  /itens/novo``, ``/itens/{item_id}``, ``/itens/{item_id}/editar``,
  ``/itens/{item_id}/revisao`` and ``/apontamento``  the modals: the item form, the sheet, the
  revision form and the weekly report; the Portfólio asks for the project first;
* ``POST /itens`` and ``POST /itens/{item_id}``  create the item in elaboration or save the
  edit (an approved baseline only takes notes); the answer carries the modal, the filters and
  the content in one multi-target reply (422 per field, 409 for a stale version);
* ``POST /itens/formulario`` and ``POST /itens/{item_id}/revisao/formulario``  draw the form
  again with the distribution grid the server recalculated;
* ``POST /itens/{item_id}/aprovacao``  freezes the baseline (Gestor; whoever elaborated it
  receives 403), ``/exclusao`` removes a draft without entries and ``/revisoes`` revises the
  approved baseline with an approved change request and a justification;
* ``POST /apontamento``  registers or updates the week of the contractor (``?acao=recarregar``
  draws the grid again). The import goes through the generic flow (ISSUE-018).

The field hours (ISSUE-047), prefix ``/api/planejamento/produtividade/horas-efetivas``:

* ``GET  /``  the Horas efetivas tab: the filters (``empresa``, ``corte``, ``area``,
  ``encarregado`` and ``periodo``) and the three views — capacity, work sampling and stoppages
  — with the Pareto of the stop reasons (D11);
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same content, with the filter;
* ``GET  /jornadas/nova``, ``/jornadas/{registro_id}/editar`` and the same pair for
  ``/amostragens`` and ``/paralisacoes``  the modals of the field: the day, the observation
  round with its reason grid and the stoppage; the Portfólio asks for the project first;
* ``POST /jornadas`` and ``POST /jornadas/{registro_id}`` (and the pairs for samples and
  stoppages)  write the record; the answer carries the modal and the tab in one multi-target
  reply (422 per field, 409 for a stale version); the second day of the same front receives 422.

The performance KPIs (ISSUE-048), prefix ``/api/planejamento/produtividade/kpis``:

* ``GET  /``  the KPIs tab: the filters (``empresa`` and ``corte``), the indicators of the
  general block or of the chosen company, the table per company, the weekly trend and the two
  charts of the DS library (D11);
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same content, with the filter;
* ``GET  /acoes/nova``  the form of the plan of action of the chosen company, with the texts
  suggested by its indicators; the Portfólio asks for the project first;
* ``POST /acoes``  opens the plan in the Central (one open action per company and week); the
  second attempt receives 422; the answer carries the modal and the tab in one multi-target
  reply, and the Central links back to this tab with the company and the week.

The punch list (ISSUE-049), prefix ``/api/planejamento/punch``:

* ``GET  /``  the screen: the toolbar with the filters and the buttons, the indicators, the
  list of items (with the ``Projeto`` column in the Portfólio) and the empty modal;
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same list, with the filter;
* ``GET  /filtros``  the filter modal; ``GET /itens/novo`` and ``/itens/{id}/editar``  the item
  form (the Portfólio asks for the project first); ``GET /itens/{id}/verificacao``  the closing
  with verification, with the attachments of the item; ``GET /itens/{id}/cancelamento``  the
  cancellation;
* ``POST /itens`` and ``POST /itens/{id}``  create and save the item (422 per field, 409 for a
  stale version); ``POST /itens/{id}/tratar`` and ``/enviar``  move the flow; ``POST
  /itens/{id}/verificacao``  approves (422 without evidence, 403 for the executant) or rejects;
  ``POST /itens/{id}/cancelamento``  cancels with a justification. Every write answers the
  modal, the toolbar and the list in one multi-target reply, and the Central action follows.

The completion panel (ISSUE-050), prefix ``/api/planejamento/punch/painel``:

* ``GET  /``  the panel tab: the alert of the blocked systems, the release indicators per
  milestone, the burndown, the aging, the counts by discipline and company (the charts of the
  DS library, D11) and the table of systems by milestone (with ``Projeto`` in the Portfólio);
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same content, with the charts
  as tables in the spreadsheet; the screen answers the panel together with the list, and the
  tab is addressable by ``?aba=painel``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario, importing, rbac
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.export_document import Document, Kpi, ValueKind, describe_scope, format_value
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


EAP_PROGRESS_IMPORT_CHECK_TEMPLATE = "planejamento/eap_importacao_conferencia.html"


EAP_PROGRESS_IMPORT_RESULT_TEMPLATE = "planejamento/eap_importacao_resultado.html"


EAP_PAGE_CLASS = "pagina--planejamento-eap"


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
    """O formulário da importação do avanço: a data da medição, a planilha e os dois alvos."""
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
            "alvo_conteudo": EAP_CONTENT_TARGET,
        },
        request=req,
        root_class=EAP_PAGE_CLASS,
    )


@bp.route(route=f"{EAP_PROGRESS_IMPORT_BASE}/conferir", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_progress_import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Lê a planilha e responde o que cada linha vai gravar; nada é escrito.

    A resposta é multi-alvo — a conferência e o conteúdo — porque o formulário do modal
    declara os dois alvos no sucesso; o conteúdo volta como está, já que nada foi gravado.
    """
    measurement_date = _import_measurement_date(req)
    preview = importing.check(
        session,
        importer=importers.progress_importer(),
        upload=_upload_of(req),
        context=_import_context(context, measurement_date),
    )
    data = _progress_import_check_context(preview)
    data.update(_eap_content_context(_eap_overview(session, context)))
    return AlpineAjaxResponse(
        template_name=EAP_PROGRESS_IMPORT_CHECK_TEMPLATE,
        context=data,
        request=req,
    )


@bp.route(route=f"{EAP_PROGRESS_IMPORT_BASE}/confirmar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_progress_import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Checa a planilha de novo e grava o avanço das linhas sem erro, só na confirmação.

    A resposta é multi-alvo — o resultado e o conteúdo —, para a árvore mostrar o real das
    medições gravadas sem recarregar a tela.
    """
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
    data: dict[str, Any] = {"resultado": result, "importador": importer.title}
    data.update(_eap_content_context(_eap_overview(session, context)))
    return AlpineAjaxResponse(
        template_name=EAP_PROGRESS_IMPORT_RESULT_TEMPLATE,
        context=data,
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


# ── Revisões da EAP e desdobramento (ISSUE-038) ──────────────────────────


EAP_PACKAGE_FORM_TEMPLATE = "planejamento/eap_pacote_form.html"


EAP_PACKAGE_SAVED_TEMPLATE = "planejamento/eap_pacote_salvo.html"


EAP_REVISION_FORM_TEMPLATE = "planejamento/eap_revisao_form.html"


EAP_REVISION_SAVED_TEMPLATE = "planejamento/eap_revisao_salva.html"


EAP_PACKAGE_IMPORT_FORM_TEMPLATE = "planejamento/eap_pacotes_importacao_form.html"


EAP_PACKAGE_IMPORT_CHECK_TEMPLATE = "planejamento/eap_pacotes_importacao_conferencia.html"


EAP_PACKAGE_IMPORT_RESULT_TEMPLATE = "planejamento/eap_pacotes_importacao_resultado.html"


EAP_PACKAGE_ROUTE = f"{EAP_BASE}/pacotes"


EAP_PACKAGE_NEW_ROUTE = f"{EAP_PACKAGE_ROUTE}/novo"


EAP_REVISION_ROUTE = f"{EAP_BASE}/revisoes"


EAP_REVISION_NEW_ROUTE = f"{EAP_REVISION_ROUTE}/nova"


EAP_PACKAGE_IMPORT_BASE = f"{EAP_PACKAGE_ROUTE}/importar"


EAP_PACKAGE_IMPORT_TARGET = "eap-pacotes-importacao-resultado"


EAP_PACKAGE_RESOURCES = validation.PACKAGE_RESOURCES


EAP_KINDS = (calculations.WORK_PACKAGE, calculations.PLANNING_PACKAGE)


EAP_BREAKDOWN_MESSAGE = "Pacote {code} criado com peso desdobrado de {source}{closed}."


EAP_BREAKDOWN_CLOSED = " (pacote de planejamento encerrado)"


EAP_REVISION_PACKAGE_MESSAGE = "Pacote {code} incluído na Rev {revision}; demais pesos reescalados."


EAP_REVISION_MESSAGE = "Rev {revision} da EAP criada."


EAP_PACKAGE_IMPORT_MESSAGE = "Rev {revision} criada: {items}."


EAP_PACKAGE_IMPORT_ONE = "1 pacote novo"


EAP_PACKAGE_IMPORT_MANY = "{count} pacotes novos"


@bp.route(route=EAP_PACKAGE_NEW_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eap_package_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do pacote novo: o desdobramento ou a revisão, conforme ``recurso``."""
    resource = _package_resource(req.params.get(validation.FIELD_RESOURCE))
    return AlpineAjaxResponse(
        template_name=EAP_PACKAGE_FORM_TEMPLATE,
        context=_package_page(session, context, resource),
        request=req,
    )


@bp.route(route=EAP_PACKAGE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_package_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cria o pacote: desdobra o de planejamento ou abre a revisão (Gestor), em resposta multi-alvo."""
    resource = _package_resource(req.form.get(validation.FIELD_RESOURCE))
    options = _form_options(session, context)
    try:
        data = validation.parse_package_form(
            req.form,
            packages=options.states,
            limits=options.limits,
            stage_models=options.stage_models,
        )
        if data.resource == validation.BREAKDOWN:
            created = service.breakdown_package(
                session,
                user=context.user,
                scope=context.scope,
                request=service.BreakdownRequest(package=data),
                reference_date=calendario.today(),
            )
            toast = EAP_BREAKDOWN_MESSAGE.format(
                code=created.code,
                source=created.source_code,
                closed=EAP_BREAKDOWN_CLOSED if created.source_closed else "",
            )
        else:
            revision = service.create_revision(
                session,
                user=context.user,
                scope=context.scope,
                request=service.RevisionRequest(
                    change_code=data.change_code or "",
                    justification=data.justification,
                    new_packages=(data,),
                ),
                reference_date=calendario.today(),
            )
            toast = EAP_REVISION_PACKAGE_MESSAGE.format(
                code=revision.new_codes[0], revision=revision.revision
            )
    except (InvalidDataError, AccessDeniedError, VersionConflictError) as error:
        return _package_error(req, session, context, resource, error)
    return AlpineAjaxResponse(
        template_name=EAP_PACKAGE_SAVED_TEMPLATE,
        context=_saved_content_context(session, context),
        request=req,
        toast=toast,
    )


@bp.route(route=EAP_REVISION_NEW_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eap_revision_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da revisão: a SM aprovada pendente e os pacotes de nível 3 do projeto."""
    return AlpineAjaxResponse(
        template_name=EAP_REVISION_FORM_TEMPLATE,
        context=_revision_page(session, context),
        request=req,
    )


@bp.route(route=EAP_REVISION_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_revision_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Ajusta um pacote pela SM aprovada (Gestor) e reescala os pesos, em resposta multi-alvo."""
    try:
        options = _form_options(session, context)
        data = validation.parse_revision_form(
            req.form, packages=options.states, limits=options.limits
        )
        revision = service.create_revision(
            session,
            user=context.user,
            scope=context.scope,
            request=service.RevisionRequest(
                change_code=data.change_code,
                justification=data.justification,
                adjustments=(data.adjustment,),
            ),
            reference_date=calendario.today(),
        )
    except (InvalidDataError, AccessDeniedError, VersionConflictError) as error:
        return _revision_error(req, session, context, error)
    return AlpineAjaxResponse(
        template_name=EAP_REVISION_SAVED_TEMPLATE,
        context=_saved_content_context(session, context),
        request=req,
        toast=EAP_REVISION_MESSAGE.format(revision=revision.revision),
    )


def _package_resource(value: str | None) -> str:
    """O recurso do formulário: desdobramento ou revisão; qualquer outro vale o desdobramento."""
    chosen = (value or "").strip()
    return chosen if chosen in EAP_PACKAGE_RESOURCES else validation.BREAKDOWN


@dataclass(frozen=True)
class EapFormState:
    """O que um formulário da revisão já traz: os valores digitados e as mensagens."""

    values: Mapping[str, Any] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)
    message: str = ""


def _form_options(session: Session, context: RequestContext) -> service.EapFormOptions:
    return service.revision_form_options(
        session, user=context.user, scope=context.scope, reference_date=calendario.today()
    )


def _package_page(
    session: Session,
    context: RequestContext,
    resource: str,
    state: EapFormState | None = None,
) -> dict[str, Any]:
    """O que o formulário do pacote novo precisa: as listas, os valores digitados e as mensagens."""
    state = state or EapFormState()
    return {
        "opcoes": _form_options(session, context),
        "valores": dict(state.values),
        "erros": dict(state.errors),
        "mensagem": state.message,
        "recurso": resource,
        "tipos": EAP_KINDS,
        "criterios": calculations.EAP_CRITERIA,
        "formulario": True,
        "alvo_conteudo": EAP_CONTENT_TARGET,
        "alvo_formulario": EAP_FORM_TARGET,
    }


def _revision_page(
    session: Session,
    context: RequestContext,
    state: EapFormState | None = None,
) -> dict[str, Any]:
    """O que o formulário da revisão precisa: as listas, os valores digitados e as mensagens."""
    state = state or EapFormState()
    return {
        "opcoes": _form_options(session, context),
        "valores": dict(state.values),
        "erros": dict(state.errors),
        "mensagem": state.message,
        "formulario": True,
        "alvo_conteudo": EAP_CONTENT_TARGET,
        "alvo_formulario": EAP_FORM_TARGET,
    }


def _package_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    resource: str,
    error: InvalidDataError | AccessDeniedError | VersionConflictError,
) -> func.HttpResponse:
    """A criação recusada: o conteúdo atualizado e o formulário preenchido com o digitado."""
    errors = _field_errors(error)
    data = _eap_content_context(_eap_overview(session, context))
    state = EapFormState(values=req.form, errors=errors, message=str(error))
    data.update(_package_page(session, context, resource, state))
    return AlpineAjaxResponse(
        template_name=EAP_PACKAGE_SAVED_TEMPLATE,
        context=data,
        request=req,
        status_code=_error_status(error),
        toast=str(error),
        toast_tipo="erro",
    )


def _revision_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    error: InvalidDataError | AccessDeniedError | VersionConflictError,
) -> func.HttpResponse:
    """A revisão recusada: o conteúdo atualizado e o formulário preenchido com o digitado."""
    errors = _field_errors(error)
    data = _eap_content_context(_eap_overview(session, context))
    state = EapFormState(values=req.form, errors=errors, message=str(error))
    data.update(_revision_page(session, context, state))
    return AlpineAjaxResponse(
        template_name=EAP_REVISION_SAVED_TEMPLATE,
        context=data,
        request=req,
        status_code=_error_status(error),
        toast=str(error),
        toast_tipo="erro",
    )


def _field_errors(
    error: InvalidDataError | AccessDeniedError | VersionConflictError,
) -> Mapping[str, str]:
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return error.detail
    return {}


# ── Importação dos pacotes (ISSUE-038) ───────────────────────────────────


@dataclass(frozen=True)
class EapPackageImportResult:
    """O que a importação de pacotes criou: a revisão, a SM, os códigos novos e as linhas de fora."""

    revision: int
    change_code: str
    codes: tuple[str, ...]
    skipped: tuple[importing.CheckedRow, ...]
    file_name: str


@bp.route(route=f"{EAP_PACKAGE_IMPORT_BASE}/formulario", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eap_package_import_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da importação de pacotes: a SM, a justificativa da revisão e a planilha."""
    context.scope.require_project()
    importer = importers.packages_importer()
    options = _form_options(session, context)
    return AlpineAjaxResponse(
        template_name=EAP_PACKAGE_IMPORT_FORM_TEMPLATE,
        context={
            "titulo": importer.title,
            "fontes": options.changes,
            "campo_arquivo": attachments.FILE_FIELD,
            "limite_mb": MAX_FILE_BYTES // MEGABYTE,
            "limite_linhas": format_value(ValueKind.INTEGER, MAX_DATA_ROWS),
            "modelo_url": f"/api/importacao/{importer.key}/modelo",
            "conferir_url": f"/api/{EAP_PACKAGE_IMPORT_BASE}/conferir",
            "alvo_resultado": EAP_PACKAGE_IMPORT_TARGET,
            "alvo_conteudo": EAP_CONTENT_TARGET,
            "proxima_revisao": options.next_revision,
        },
        request=req,
        root_class=EAP_PAGE_CLASS,
    )


@bp.route(route=f"{EAP_PACKAGE_IMPORT_BASE}/conferir", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_package_import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Lê a planilha de pacotes e responde o que cada linha vai criar; nada é escrito.

    A resposta é multi-alvo — a conferência e o conteúdo —, como no avanço: o formulário do
    modal declara os dois e o conteúdo volta como está, já que nada foi gravado.
    """
    context.scope.require_project()
    preview = importing.check(
        session,
        importer=importers.packages_importer(),
        upload=_upload_of(req),
        context=_import_context(context, calendario.today()),
    )
    data = _package_import_check_context(preview)
    data.update(_eap_content_context(_eap_overview(session, context)))
    return AlpineAjaxResponse(
        template_name=EAP_PACKAGE_IMPORT_CHECK_TEMPLATE,
        context=data,
        request=req,
    )


@bp.route(route=f"{EAP_PACKAGE_IMPORT_BASE}/confirmar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eap_package_import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Checa a planilha de novo e cria a revisão com os pacotes das linhas sem erro.

    O importador ``eap-pacotes`` recusa a gravação genérica: quem grava é esta rota, pela
    revisão vinculada à SM (``create_revision``), tudo ou nada. As linhas com erro não entram e
    voltam no resultado, como na importação de itens da EAC.
    """
    context.scope.require_project()
    importer = importers.packages_importer()
    upload = _upload_of(req)
    preview = importing.check(
        session,
        importer=importer,
        upload=upload,
        context=_import_context(context, calendario.today()),
    )
    _require_package_importable(upload, preview, req.form)
    options = _form_options(session, context)
    change_code, justification = _package_import_terms(req.form)
    revision = service.create_revision(
        session,
        user=context.user,
        scope=context.scope,
        request=service.RevisionRequest(
            change_code=change_code,
            justification=justification,
            new_packages=importers.revision_packages(
                options=options,
                rows=preview.writable_rows,
                change_code=change_code,
                justification=justification,
            ),
        ),
        reference_date=calendario.today(),
    )
    data = _package_import_result_context(preview, revision)
    data.update(_eap_content_context(_eap_overview(session, context)))
    return AlpineAjaxResponse(
        template_name=EAP_PACKAGE_IMPORT_RESULT_TEMPLATE,
        context=data,
        request=req,
        toast=_package_import_notice(preview, revision),
        toast_tipo="aviso" if preview.error_rows else "ok",
    )


def _require_package_importable(
    upload: importing.Upload, preview: importing.ImportPreview, form: Mapping[str, str]
) -> None:
    """As guardas da confirmação genérica, antes de a revisão ser escrita."""
    digest = (form.get(IMPORT_CHECKED_FIELD) or "").strip()
    if not digest:
        raise InvalidDataError(importing.NOT_CHECKED_MESSAGE)
    if digest != importing.digest_of(upload):
        raise InvalidDataError(importing.CHANGED_MESSAGE)
    if preview.missing:
        raise InvalidDataError(importing.MISSING_MESSAGE.format(columns=", ".join(preview.missing)))
    if not preview.writable_rows:
        raise InvalidDataError(importing.NOTHING_MESSAGE)
    if preview.error_rows and form.get(IMPORT_ACKNOWLEDGED_FIELD) != IMPORT_ACKNOWLEDGED_VALUE:
        raise InvalidDataError(importing.NOT_ACKNOWLEDGED_MESSAGE)


def _package_import_terms(form: Mapping[str, str]) -> tuple[str, str]:
    """A SM e a justificativa do formulário, como a revisão as pede."""
    change_code = (form.get(validation.FIELD_CHANGE) or "").strip()
    if not change_code:
        raise InvalidDataError({validation.FIELD_CHANGE: validation.CHANGE_MESSAGE})
    justification = (form.get(validation.FIELD_JUSTIFICATION) or "").strip()
    if len(justification) < validation.JUSTIFICATION_MIN_CHARACTERS:
        raise InvalidDataError(
            {validation.FIELD_JUSTIFICATION: validation.REVISION_JUSTIFICATION_MESSAGE}
        )
    return change_code, justification


def _package_import_check_context(preview: importing.ImportPreview) -> dict[str, Any]:
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
        "confirmar_url": f"/api/{EAP_PACKAGE_IMPORT_BASE}/confirmar",
    }


def _package_import_result_context(
    preview: importing.ImportPreview, revision: service.RevisionResult
) -> dict[str, Any]:
    return {
        "resultado": EapPackageImportResult(
            revision=revision.revision,
            change_code=revision.change_code,
            codes=revision.new_codes,
            skipped=preview.error_rows,
            file_name=preview.file_name,
        ),
        "importador": importers.packages_importer().title,
    }


def _package_import_notice(
    preview: importing.ImportPreview, revision: service.RevisionResult
) -> str:
    """O aviso da confirmação: a revisão criada e as linhas com erro que ficaram de fora."""
    count = len(revision.new_codes)
    items = EAP_PACKAGE_IMPORT_ONE if count == 1 else EAP_PACKAGE_IMPORT_MANY.format(count=count)
    notice = EAP_PACKAGE_IMPORT_MESSAGE.format(revision=revision.revision, items=items)
    skipped = len(preview.error_rows)
    if not skipped:
        return notice
    left_out = (
        "1 linha com erro não entrou" if skipped == 1 else f"{skipped} linhas com erro não entraram"
    )
    return f"{notice} {left_out}."


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
        "pode_gerir": visao.can_manage,
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


# ── Curva S física (ISSUE-039) ────────────────────────────────────────────

CURVA_FISICA_BASE = "planejamento/curva-fisica"


CURVA_FISICA_TEMPLATE = "planejamento/curva_fisica.html"


CURVA_FISICA_CONTENT_TARGET = "curva-fisica-conteudo"


CURVA_FISICA_KPI_ICONS = ("chartLine", "checkCircle", "warning", "refresh", "calendar")


CURVA_FISICA_KPIS_SCREEN = "/planejamento/kpis"


@dataclass(frozen=True)
class CurvaFisicaKpiLine:
    """Um indicador da faixa do topo, já escrito como a pessoa o lê; o SPI leva o link da tela."""

    rotulo: str
    valor: str
    referencia: str
    situacao: str
    tom: str
    icone: str
    href: str = ""


@dataclass(frozen=True)
class CurvaFisicaPointLine:
    """Uma linha da tabela período a período, com o mês do corte marcado."""

    mes: str
    previsto_mes: str
    previsto: str
    real_mes: str
    real: str
    tendencia: str
    desvio: str
    tom: str
    corte: bool


@dataclass(frozen=True)
class CurvaFisicaCompositionLine:
    """Uma linha da composição da carteira: peso, avanço e contribuição para o desvio."""

    projeto: str
    peso: str
    previsto: str
    real: str
    desvio: str
    tom_desvio: str
    spi: str
    tom_spi: str
    contribuicao: str
    tom_contribuicao: str
    termino: str


@bp.route(route=CURVA_FISICA_BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def curva_fisica_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A Curva S física do escopo: indicadores, gráfico, tabela período a período e carteira."""
    return AlpineAjaxResponse(
        template_name=CURVA_FISICA_TEMPLATE,
        context=_curva_fisica_context(_curva_fisica_overview(session, context)),
        request=req,
    )


@bp.route(route=f"{CURVA_FISICA_BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def curva_fisica_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da Curva S física: indicadores, tabela e composição, no escopo do pedido."""
    del req
    return excel_response(_curva_fisica_document(session, context))


@bp.route(route=f"{CURVA_FISICA_BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def curva_fisica_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da Curva S física: o mesmo documento que o Excel carrega."""
    return printable_response(_curva_fisica_document(session, context), req)


def _curva_fisica_overview(
    session: Session, context: RequestContext
) -> service.CurvaFisicaOverview:
    """A Curva S física do escopo do pedido; a única leitura da rota que vê o relógio."""
    return service.curva_fisica_overview(
        session, scope=context.scope, reference_date=calendario.today()
    )


def _curva_fisica_document(session: Session, context: RequestContext) -> Document:
    return export.curva_fisica_document(
        _curva_fisica_overview(session, context),
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _curva_fisica_context(visao: service.CurvaFisicaOverview) -> dict[str, Any]:
    """O que o fragmento da Curva S imprime: a visão, as linhas, o gráfico e o subtítulo."""
    return {
        "visao": visao,
        "kpis": _curva_fisica_kpi_lines(visao),
        "linhas": _curva_fisica_point_lines(visao),
        "carteira": _curva_fisica_composition_lines(visao),
        "grafico": visao.chart,
        "situacao": "vazio-origem" if visao.is_empty else "conteudo",
        "subtitulo": _curva_fisica_subtitle(visao),
        "alvo_conteudo": CURVA_FISICA_CONTENT_TARGET,
    }


def _curva_fisica_subtitle(visao: service.CurvaFisicaOverview) -> str:
    cut = export.curva_fisica_month_label(visao.indicators.cut_month)
    text = f"Corte em {cut} · % acumulado por mês" if cut else "Sem corte na referência"
    if visao.is_portfolio:
        text += " · média ponderada pelos pesos dos projetos na carteira"
    return text


def _curva_fisica_kpi_lines(visao: service.CurvaFisicaOverview) -> list[CurvaFisicaKpiLine]:
    href = (
        f"{CURVA_FISICA_KPIS_SCREEN}?projeto={visao.project_id}"
        if visao.project_id is not None
        else f"{CURVA_FISICA_KPIS_SCREEN}?projeto=portfolio"
    )
    return [
        CurvaFisicaKpiLine(
            rotulo=kpi.label,
            valor=(
                export.signed_decimal_text(kpi.value)
                if kpi.label == "Desvio" and isinstance(kpi.value, Decimal)
                else format_value(kpi.kind, kpi.value, kpi.digits)
            ),
            referencia=kpi.reference,
            situacao=kpi.status,
            tom=kpi.tone.value if kpi.tone else "neutro",
            icone=icone,
            href=href if kpi.label == "SPI" else "",
        )
        for kpi, icone in zip(export.curva_fisica_kpis(visao), CURVA_FISICA_KPI_ICONS, strict=True)
    ]


def _curva_fisica_point_lines(visao: service.CurvaFisicaOverview) -> list[CurvaFisicaPointLine]:
    lines: list[CurvaFisicaPointLine] = []
    for point in visao.points:
        tone = export.deviation_tone(point.deviation_pp)
        lines.append(
            CurvaFisicaPointLine(
                mes=export.curva_fisica_month_label(point.month),
                previsto_mes=format_value(ValueKind.DECIMAL, point.month_predicted, 1),
                previsto=format_value(ValueKind.PERCENT, point.predicted, 1),
                real_mes=format_value(ValueKind.DECIMAL, point.month_actual, 1),
                real=format_value(ValueKind.PERCENT, point.actual, 1),
                tendencia=format_value(ValueKind.PERCENT, point.trend, 1),
                desvio=export.signed_decimal_text(point.deviation_pp),
                tom=tone.value if tone is not None else "neutro",
                corte=point.is_cut,
            )
        )
    return lines


def _curva_fisica_composition_lines(
    visao: service.CurvaFisicaOverview,
) -> list[CurvaFisicaCompositionLine]:
    lines: list[CurvaFisicaCompositionLine] = []
    for item in visao.composition:
        deviation_tone = export.deviation_tone(item.deviation_pp)
        contribution_tone = export.deviation_tone(item.contribution_pp)
        lines.append(
            CurvaFisicaCompositionLine(
                projeto=item.project_label,
                peso=format_value(ValueKind.PERCENT, item.weight),
                previsto=format_value(ValueKind.PERCENT, item.predicted, 1),
                real=format_value(ValueKind.PERCENT, item.actual, 1),
                desvio=export.signed_decimal_text(item.deviation_pp),
                tom_desvio=deviation_tone.value if deviation_tone is not None else "neutro",
                spi=format_value(ValueKind.DECIMAL, item.spi, 2),
                tom_spi=export.spi_tone(item.spi).value,
                contribuicao=export.signed_decimal_text(item.contribution_pp, 2),
                tom_contribuicao=(
                    contribution_tone.value if contribution_tone is not None else "neutro"
                ),
                termino=export.curva_fisica_finish_text(item),
            )
        )
    return lines


# ── KPIs de planejamento (ISSUE-040) ─────────────────────────────────────

KPIS_BASE = "planejamento/kpis"


KPIS_TEMPLATE = "planejamento/kpis.html"


KPIS_CONTENT_TARGET = "kpis-conteudo"


KPI_ICONS = ("refresh", "chartLine", "warning", "flag", "clock", "file")


@dataclass(frozen=True)
class PlanningKpiCard:
    """Um indicador da faixa do topo dos KPIs, já escrito como a pessoa o lê."""

    rotulo: str
    valor: str
    referencia: str
    situacao: str
    tom: str
    icone: str


@dataclass(frozen=True)
class PlanningRowLine:
    """Uma linha da tabela de avanço: a área ou o projeto com os valores já escritos."""

    rotulo: str
    peso: str
    previsto: str
    real: str
    desvio: str
    tom_desvio: str
    spi: str
    tom_spi: str
    contribuicao: str


@dataclass(frozen=True)
class PlanningFooterLine:
    """O rodapé ponderado da tabela de avanço, fechando com a Curva S."""

    rotulo: str
    peso: str
    previsto: str
    real: str
    desvio: str
    tom_desvio: str


@bp.route(route=KPIS_BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def planning_kpis_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Os KPIs do escopo: indicadores, gráficos e o avanço por área ou por projeto."""
    return AlpineAjaxResponse(
        template_name=KPIS_TEMPLATE,
        context=_planning_kpis_context(_planning_kpis_overview(session, context)),
        request=req,
    )


@bp.route(route=f"{KPIS_BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def planning_kpis_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel dos KPIs: indicadores, SPI por mês e avanço, no escopo do pedido."""
    del req
    return excel_response(_planning_kpis_document(session, context))


@bp.route(route=f"{KPIS_BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def planning_kpis_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível dos KPIs: o mesmo documento que o Excel carrega, com os gráficos."""
    return printable_response(_planning_kpis_document(session, context), req)


def _planning_kpis_overview(
    session: Session, context: RequestContext
) -> service.PlanningKpisOverview:
    """Os KPIs do escopo do pedido; a única leitura da rota que vê o relógio."""
    return service.planning_kpis_overview(
        session, scope=context.scope, reference_date=calendario.today()
    )


def _planning_kpis_document(session: Session, context: RequestContext) -> Document:
    return export.planning_kpis_document(
        _planning_kpis_overview(session, context),
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _planning_kpis_context(visao: service.PlanningKpisOverview) -> dict[str, Any]:
    """O que o fragmento dos KPIs imprime: a visão, os cartões, as linhas e o rodapé."""
    return {
        "visao": visao,
        "kpis": _planning_kpi_lines(visao),
        "linhas": _planning_row_lines(visao),
        "rodape": _planning_footer_line(visao),
        "situacao": "vazio-origem" if visao.is_empty else "conteudo",
        "alvo_conteudo": KPIS_CONTENT_TARGET,
    }


def _planning_kpi_lines(visao: service.PlanningKpisOverview) -> list[PlanningKpiCard]:
    return [
        PlanningKpiCard(
            rotulo=kpi.label,
            valor=_planning_kpi_text(kpi),
            referencia=kpi.reference,
            situacao=kpi.status,
            tom=kpi.tone.value if kpi.tone else "neutro",
            icone=icone,
        )
        for kpi, icone in zip(export.planning_kpis(visao), KPI_ICONS, strict=True)
    ]


def _planning_kpi_text(kpi: Kpi) -> str:
    """O valor do indicador como a tela o escreve: o desvio leva o sinal explícito no positivo."""
    value = kpi.value
    if isinstance(value, Decimal) and kpi.label.startswith(("Desvio", "Maior desvio")):
        return export.signed_decimal_text(value, kpi.digits)
    return format_value(kpi.kind, value, kpi.digits)


def _planning_row_lines(visao: service.PlanningKpisOverview) -> list[PlanningRowLine]:
    lines: list[PlanningRowLine] = []
    for item in visao.rows:
        desvio_tone = export.deviation_tone(item.deviation_pp)
        lines.append(
            PlanningRowLine(
                rotulo=f"{item.code} · {item.name}" if visao.is_portfolio else item.name,
                peso=format_value(ValueKind.PERCENT, item.weight, 1 if visao.is_portfolio else 0),
                previsto=format_value(ValueKind.PERCENT, item.predicted, 1),
                real=format_value(ValueKind.PERCENT, item.actual, 1),
                desvio=export.signed_decimal_text(item.deviation_pp),
                tom_desvio=desvio_tone.value if desvio_tone is not None else "neutro",
                spi=format_value(ValueKind.DECIMAL, item.spi, 2),
                tom_spi=export.spi_tone(item.spi).value,
                contribuicao=format_value(ValueKind.DECIMAL, item.contribution_pp, 1),
            )
        )
    return lines


def _planning_footer_line(visao: service.PlanningKpisOverview) -> PlanningFooterLine:
    weight = sum((item.weight for item in visao.rows), Decimal(0))
    deviation_tone = export.deviation_tone(visao.indicators.deviation_pp)
    return PlanningFooterLine(
        rotulo=(
            export.PLANNING_PORTFOLIO_WEIGHTED
            if visao.is_portfolio
            else export.PLANNING_PROJECT_WEIGHTED
        ),
        peso=format_value(ValueKind.PERCENT, weight, 0),
        previsto=format_value(ValueKind.PERCENT, visao.indicators.predicted, 1),
        real=format_value(ValueKind.PERCENT, visao.indicators.actual, 1),
        desvio=export.signed_decimal_text(visao.indicators.deviation_pp),
        tom_desvio=deviation_tone.value if deviation_tone is not None else "neutro",
    )


# ── Produtividade: quantidades, LB e apontamento (ISSUE-046) ──────────────


PRODUTIVIDADE_BASE = "planejamento/produtividade"


PRODUTIVIDADE_API = f"/api/{PRODUTIVIDADE_BASE}"


PROD_SCREEN = "planejamento/produtividade.html"


FILTERS_TEMPLATE = "planejamento/produtividade_filtros.html"


CONTENT_TEMPLATE = "planejamento/produtividade_conteudo.html"


PROD_ANSWER = "planejamento/produtividade_resposta.html"


MODAL_TEMPLATE = "planejamento/produtividade_modal.html"


ITEM_FORM_TEMPLATE = "planejamento/produtividade_item_form.html"


ITEM_FORM_INNER = "planejamento/_prod_item_form.html"


ITEM_DETAIL_TEMPLATE = "planejamento/produtividade_item_detalhe.html"


ITEM_DETAIL_INNER = "planejamento/_prod_item_detalhe.html"


REVISION_FORM_TEMPLATE = "planejamento/produtividade_revisao_form.html"


REVISION_FORM_INNER = "planejamento/_prod_revision_form.html"


ENTRY_FORM_TEMPLATE = "planejamento/produtividade_apontamento_form.html"


ENTRY_FORM_INNER = "planejamento/_prod_entry_form.html"


SAVED_INNER = "planejamento/_prod_salvo.html"


PROD_MODAL_TARGET = "produtividade-modal"


PROD_PAGE_CLASS = "pagina--planejamento-produtividade"


PLANNED_FIELD = re.compile(r"^previsto_(\d{4}-S\d{2})$")


ENTRY_REALIZED_FIELD = re.compile(r"^realizado_(\d+)$")


TONE_CLASSES = {"success": "ok", "warning": "warn", "danger": "erro", None: "info"}


ITEM_CREATED_MESSAGE = "{code} criado em elaboração: aprove a LB para entrar nos indicadores."


ITEM_UPDATED_MESSAGE = "{code} atualizado."


ITEM_APPROVED_MESSAGE = "Linha de base de {code} aprovada."


ITEM_DELETED_MESSAGE = "Item {code} excluído."


ITEM_REVISED_MESSAGE = "Linha de base de {code} revisada (rev {revision})."


ENTRIES_SAVED_MESSAGE = "{count} em {week}."


def _tone_class(band: str | None) -> str:
    return TONE_CLASSES.get(band, "info")


def _filter_values(values: Mapping[str, str]) -> dict[str, str]:
    """O filtro da tela como os formulários o devolvem: campos ocultos ``f_*``."""
    return {
        "corte": (values.get("corte") or "").strip(),
        "empresa": (values.get("empresa") or "").strip(),
        "grupo": (values.get("grupo") or "").strip(),
    }


def _posted_filter(values: Mapping[str, str]) -> service.QuantityFilter:
    """O filtro que o formulário do modal carregou nos campos ocultos."""
    return service.QuantityFilter(
        company_id=_integer(values.get("f_empresa")),
        group=(values.get("f_grupo") or "").strip(),
        cut_week=(values.get("f_corte") or "").strip(),
    )


def _quantities_context(
    session: Session,
    context: RequestContext,
    *,
    quantity_filter: service.QuantityFilter,
) -> dict[str, Any]:
    """O contexto da aba Quantidades: a visão do escopo e os auxiliares de escrita."""
    visao = service.quantities_overview(
        session,
        user=context.user,
        scope=context.scope,
        quantity_filter=quantity_filter,
        reference_date=calendario.today(),
    )
    return {
        "visao": visao,
        "filtro": _filter_values(
            {
                "corte": visao.filter.cut_week,
                "empresa": "" if visao.filter.company_id is None else str(visao.filter.company_id),
                "grupo": visao.filter.group,
            }
        ),
        "api": PRODUTIVIDADE_API,
        "rotulo_semana": export.productivity_week_caption,
        "semana_curta": export.productivity_week_short,
        "quantidade": export.quantity_text,
        "indice": export.index_text,
        "percentual": export.percent_text,
        "faixa_aderencia": lambda value: calculations.indicator_band(
            value, visao.parameters.adherence_bands, higher_is_better=True
        ),
        "faixa_pf": lambda value: calculations.indicator_band(
            value, visao.parameters.pf_bands, higher_is_better=False
        ),
        "faixa_spi": lambda value: calculations.indicator_band(
            value, visao.parameters.spi_bands, higher_is_better=True
        ),
        "tom": _tone_class,
        "corte": export.productivity_week_caption(visao.cut_week),
        "semana_atual": export.productivity_week_caption(visao.current_week),
    }


def _prod_form_context(session: Session, context: RequestContext, **valores: Any) -> dict[str, Any]:
    """O contexto de um formulário de modal: os auxiliares e nada da aba carregada."""
    del session
    return {
        "api": PRODUTIVIDADE_API,
        "rotulo_semana": export.productivity_week_caption,
        "semana_curta": export.productivity_week_short,
        "quantidade": export.quantity_text,
        "indice": export.index_text,
        "percentual": export.percent_text,
        "tom": _tone_class,
        "pode_gerir": rbac.can(context.user, Permission.MANAGE),
        "semana_corte": calendario.iso_week(calendario.today()),
        **valores,
    }


def _modal(
    req: func.HttpRequest, template: str, context: Mapping[str, Any], *, status_code: int = 200
) -> func.HttpResponse:
    """Um modal sozinho, para o pedido que o abre (alvo: ``produtividade-modal``)."""
    return AlpineAjaxResponse(
        template_name=template,
        context=dict(context),
        request=req,
        target_id=PROD_MODAL_TARGET,
        root_class=PROD_PAGE_CLASS,
        status_code=status_code,
    )


def _modal_answer(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    modal_template: str,
    filtro: service.QuantityFilter,
    valores: Mapping[str, Any],
    status_code: int = 200,
    toast: str | None = None,
    toast_tipo: str = "ok",
) -> func.HttpResponse:
    """A resposta com o modal, os filtros e o conteúdo: o que a gravação precisa atualizar.

    O modal carrega o formulário com as mensagens (422/409) ou o aviso de sucesso; a lista
    vem junto para a tela não precisar de uma segunda requisição.
    """
    page = _quantities_context(session, context, quantity_filter=filtro)
    page.update(valores)
    page["modal_template"] = modal_template
    return AlpineAjaxResponse(
        template_name=PROD_ANSWER,
        context=page,
        request=req,
        status_code=status_code,
        toast=toast,
        toast_tipo=toast_tipo,
    )


# ── A tela e as duas exportações ──────────────────────────────────────────


@bp.route(route=PRODUTIVIDADE_BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def productivity_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Os filtros, a aba Quantidades e a aba Horas efetivas do escopo, no corte pedido."""
    filtro = service.QuantityFilter(
        company_id=_integer(req.params.get("empresa")),
        group=(req.params.get("grupo") or "").strip(),
        cut_week=(req.params.get("corte") or "").strip(),
    )
    page = _quantities_context(session, context, quantity_filter=filtro)
    page.update(_hours_context(session, context, hours_filter=_hours_params(req.params)))
    page.update(
        _performance_context(session, context, performance_filter=_performance_params(req.params))
    )
    return AlpineAjaxResponse(
        template_name=PROD_SCREEN,
        context=page,
        request=req,
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def productivity_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da aba Quantidades, com o filtro de agora."""
    return excel_response(_quantities_document(req, session, context))


@bp.route(route=f"{PRODUTIVIDADE_BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def productivity_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da aba Quantidades: o que o botão PDF monta e imprime."""
    return printable_response(_quantities_document(req, session, context), req)


def _quantities_document(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    visao = service.quantities_overview(
        session,
        user=context.user,
        scope=context.scope,
        quantity_filter=service.QuantityFilter(
            company_id=_integer(req.params.get("empresa")),
            group=(req.params.get("grupo") or "").strip(),
            cut_week=(req.params.get("corte") or "").strip(),
        ),
        reference_date=calendario.today(),
    )
    return export.productivity_document(
        visao,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


# ── O modal do item: ficha, formulário, revisão e apontamento ─────────────


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/novo", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_new_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O item em branco; no Portfólio o shell pede o projeto antes."""
    context.scope.require_project()
    formulario = service.item_form(
        session,
        user=context.user,
        scope=context.scope,
        item_id=None,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        ITEM_FORM_TEMPLATE,
        _prod_form_context(
            session,
            context,
            item_id=None,
            formulario=formulario,
            filtro=_filter_values(req.params),
        ),
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/{{item_id}}", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def productivity_item_detail(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A ficha do item: indicadores no corte, semanas e histórico de revisões."""
    detalhe = service.item_detail(
        session,
        user=context.user,
        scope=context.scope,
        item_id=_route_id(req, "item_id"),
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        ITEM_DETAIL_TEMPLATE,
        _prod_form_context(
            session,
            context,
            detalhe=detalhe,
            filtro=_filter_values(req.params),
            pode_gravar=rbac.can(context.user, Permission.WRITE),
        ),
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/{{item_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_edit_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do item em elaboração, ou só as observações do aprovado."""
    item_id = _route_id(req, "item_id")
    formulario = service.item_form(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        ITEM_FORM_TEMPLATE,
        _prod_form_context(
            session,
            context,
            item_id=item_id,
            formulario=formulario,
            filtro=_filter_values(req.params),
        ),
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/{{item_id}}/revisao", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_revision_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da revisão da linha de base, com as SM aprovadas do projeto."""
    item_id = _route_id(req, "item_id")
    formulario = service.revision_form(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        REVISION_FORM_TEMPLATE,
        _prod_form_context(
            session,
            context,
            item_id=item_id,
            formulario=formulario,
            filtro=_filter_values(req.params),
        ),
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/apontamento", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_entry_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O apontamento da semana: os itens aprovados da empresa com o realizado de cada um."""
    company_id = _integer(req.params.get("empresa"))
    formulario = service.entry_form(
        session,
        user=context.user,
        scope=context.scope,
        company_id=company_id,
        week=req.params.get("semana") or "",
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        ENTRY_FORM_TEMPLATE,
        _prod_form_context(
            session,
            context,
            formulario=formulario,
            filtro=_filter_values(req.params),
        ),
    )


# ── As gravações ──────────────────────────────────────────────────────────


def _item_form_of(req: func.HttpRequest) -> validation.ItemForm:
    """O formulário do item como a validação o lê: os campos e o previsto de cada semana."""
    fields = _posted_values(req)
    planned = {
        found[1]: value
        for key, value in fields.items()
        if (found := PLANNED_FIELD.fullmatch(key)) is not None
    }
    return validation.ItemForm(fields=fields, planned=planned)


def _revision_form_of(req: func.HttpRequest) -> validation.RevisionForm:
    """O formulário da revisão como a validação o lê."""
    fields = _posted_values(req)
    planned = {
        found[1]: value
        for key, value in fields.items()
        if (found := PLANNED_FIELD.fullmatch(key)) is not None
    }
    return validation.RevisionForm(fields=fields, planned=planned)


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/formulario", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_item_form_reload(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário de novo com a grade recalculada (total, semanas, perfil ou unidade mudaram)."""
    form = _item_form_of(req)
    item_id = _integer(req.form.get("id"))
    formulario = service.item_form(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        form=form,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        ITEM_FORM_TEMPLATE,
        _prod_form_context(
            session,
            context,
            item_id=item_id,
            formulario=formulario,
            filtro=_posted_filter(req.form),
        ),
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/{{item_id}}/revisao/formulario", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_revision_form_reload(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da revisão com a grade livre recalculada (total, semana final ou perfil)."""
    item_id = _route_id(req, "item_id")
    formulario = service.revision_form(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        form=_revision_form_of(req),
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        REVISION_FORM_TEMPLATE,
        _prod_form_context(
            session,
            context,
            item_id=item_id,
            formulario=formulario,
            filtro=_posted_filter(req.form),
        ),
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_create_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cria o item em elaboração, com a distribuição calculada pelo servidor."""
    return _save_item(req, session, context, item_id=None)


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/{{item_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_update_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava a edição do item (ou só as observações, quando a LB está aprovada)."""
    return _save_item(req, session, context, item_id=_route_id(req, "item_id"))


def _save_item(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    item_id: int | None,
) -> func.HttpResponse:
    form = _item_form_of(req)
    filtro = _posted_filter(req.form)
    try:
        record = service.save_item(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        return _item_form_error(
            req,
            session,
            context,
            item_id=item_id,
            form=form,
            error=error,
            status_code=422,
            filtro=filtro,
        )
    except VersionConflictError as error:
        return _item_form_error(
            req,
            session,
            context,
            item_id=item_id,
            form=form,
            error=InvalidDataError(str(error)),
            status_code=409,
            filtro=filtro,
        )
    mensagem = (
        ITEM_UPDATED_MESSAGE.format(code=record.code)
        if item_id is not None
        else ITEM_CREATED_MESSAGE.format(code=record.code)
    )
    return _modal_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        filtro=filtro,
        valores={"mensagem": mensagem, "atualiza_conteudo": True},
        toast=mensagem,
    )


def _item_form_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    item_id: int | None,
    form: validation.ItemForm,
    error: InvalidDataError,
    status_code: int,
    filtro: service.QuantityFilter,
) -> func.HttpResponse:
    errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
    formulario = service.item_form(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        form=form,
        reference_date=calendario.today(),
        errors=errors,
    )
    return _modal_answer(
        req,
        session,
        context,
        modal_template=ITEM_FORM_INNER,
        filtro=filtro,
        valores={"formulario": formulario, "item_id": item_id},
        status_code=status_code,
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/{{item_id}}/aprovacao", methods=["POST"])
@fragment_route(access=MANAGE_ACCESS)
def productivity_approve_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Aprova a linha de base; quem elaborou recebe a recusa da segregação de funções."""
    item_id = _route_id(req, "item_id")
    filtro = _posted_filter(req.form)
    try:
        record = service.approve_item(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            version=req.form.get("versao"),
            reference_date=calendario.today(),
        )
    except (InvalidDataError, AccessDeniedError) as error:
        if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
            detail = dict(error.detail)
        else:
            detail = {"geral": str(error)}
        detalhe = service.item_detail(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            reference_date=calendario.today(),
        )
        return _modal_answer(
            req,
            session,
            context,
            modal_template=ITEM_DETAIL_INNER,
            filtro=filtro,
            valores={
                "detalhe": detalhe,
                "erro": detail.get("geral", str(error)),
                "pode_gravar": True,
            },
            status_code=403 if isinstance(error, AccessDeniedError) else 422,
        )
    mensagem = ITEM_APPROVED_MESSAGE.format(code=record.code)
    return _modal_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        filtro=filtro,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/{{item_id}}/exclusao", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_delete_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Exclui o item em elaboração sem apontamento."""
    item_id = _route_id(req, "item_id")
    filtro = _posted_filter(req.form)
    try:
        record = service.delete_item(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            version=req.form.get("versao"),
        )
    except (InvalidDataError, VersionConflictError) as error:
        return _modal_answer(
            req,
            session,
            context,
            modal_template=SAVED_INNER,
            filtro=filtro,
            valores={"mensagem": str(error), "erro": True},
            status_code=422,
            toast=str(error),
            toast_tipo="erro",
        )
    mensagem = ITEM_DELETED_MESSAGE.format(code=record.code)
    return _modal_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        filtro=filtro,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/itens/{{item_id}}/revisoes", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_revise_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Revisa a LB com a SM aprovada: congela as semanas passadas e redistribui o saldo."""
    item_id = _route_id(req, "item_id")
    filtro = _posted_filter(req.form)
    form = _revision_form_of(req)
    try:
        record = service.revise_item(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
        formulario = service.revision_form(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            reference_date=calendario.today(),
            errors=errors,
        )
        return _modal_answer(
            req,
            session,
            context,
            modal_template=REVISION_FORM_INNER,
            filtro=filtro,
            valores={"formulario": formulario, "item_id": item_id},
            status_code=422,
        )
    except VersionConflictError as error:
        formulario = service.revision_form(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            reference_date=calendario.today(),
            errors={"geral": str(error)},
        )
        return _modal_answer(
            req,
            session,
            context,
            modal_template=REVISION_FORM_INNER,
            filtro=filtro,
            valores={"formulario": formulario, "item_id": item_id},
            status_code=409,
        )
    mensagem = ITEM_REVISED_MESSAGE.format(code=record.code, revision=record.revision)
    return _modal_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        filtro=filtro,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


@bp.route(route=f"{PRODUTIVIDADE_BASE}/apontamento", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_register_entries(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava o apontamento da semana (upsert por item e semana)."""
    filtro = _posted_filter(req.form)
    company_id = _integer(req.form.get("empresa"))
    if req.params.get("acao") == "recarregar":
        return _entry_form_modal(req, session, context, company_id=company_id, filtro=filtro)
    form = _entry_form_of(req)
    if company_id is None:
        formulario = service.entry_form(
            session,
            user=context.user,
            scope=context.scope,
            company_id=None,
            week=form.week,
            reference_date=calendario.today(),
        )
        return _entry_form_error(
            req,
            session,
            context,
            replace(formulario, errors={"empresa": "Escolha a empresa."}),
            filtro,
        )
    try:
        count = service.register_entries(
            session,
            user=context.user,
            scope=context.scope,
            company_id=company_id,
            form=form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
        formulario = service.entry_form(
            session,
            user=context.user,
            scope=context.scope,
            company_id=company_id,
            week=form.week,
            reference_date=calendario.today(),
        )
        formulario = replace(formulario, errors=errors)
        formulario = _entry_values(formulario, form)
        return _entry_form_error(req, session, context, formulario, filtro)
    mensagem = ENTRIES_SAVED_MESSAGE.format(
        count=calculations.plural(count, "item apontado", "itens apontados"),
        week=export.productivity_week_caption(form.week),
    )
    return _modal_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        filtro=filtro,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


def _entry_form_modal(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    company_id: int | None,
    filtro: service.QuantityFilter,
) -> func.HttpResponse:
    formulario = service.entry_form(
        session,
        user=context.user,
        scope=context.scope,
        company_id=company_id,
        week=req.form.get("semana") or "",
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        ENTRY_FORM_TEMPLATE,
        _prod_form_context(session, context, formulario=formulario, filtro=filtro),
    )


def _entry_values(
    formulario: service.EntryFormView, form: validation.EntryForm
) -> service.EntryFormView:
    """As linhas digitadas de volta na grade, para o 422 não perder o que a pessoa escreveu."""
    rows = []
    for row in formulario.rows:
        realized, hh = form.lines.get(row.item.id, ("", ""))
        rows.append(
            replace(
                row,
                realized=_decimal_or_none(realized),
                hh=_decimal_or_none(hh),
            )
        )
    return replace(formulario, rows=tuple(rows))


def _decimal_or_none(text: str) -> Decimal | None:
    try:
        value = Decimal(text)
    except ArithmeticError:
        return None
    return value if value.is_finite() else None


def _entry_form_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    formulario: service.EntryFormView,
    filtro: service.QuantityFilter,
) -> func.HttpResponse:
    return _modal_answer(
        req,
        session,
        context,
        modal_template=ENTRY_FORM_INNER,
        filtro=filtro,
        valores={"formulario": formulario},
        status_code=422,
    )


def _entry_form_of(req: func.HttpRequest) -> validation.EntryForm:
    """O apontamento como a validação o lê: a semana e o realizado/HH de cada item."""
    lines: dict[int, tuple[str, str]] = {}
    for key, value in req.form.items():
        found = ENTRY_REALIZED_FIELD.fullmatch(key)
        if found is None:
            continue
        item_id = int(found[1])
        lines[item_id] = (value, req.form.get(f"hh_{item_id}", ""))
    return validation.EntryForm(week=req.form.get("semana", ""), lines=lines)


def _posted_values(req: func.HttpRequest) -> dict[str, str]:
    """Os campos de texto que o formulário mandou, como foram digitados."""
    return {key: value for key, value in req.form.items() if isinstance(value, str)}


# ── Horas efetivas da Produtividade: jornada, amostragem e paralisação ─────


HOURS_BASE = f"{PRODUTIVIDADE_BASE}/horas-efetivas"


HOURS_API = f"/api/{HOURS_BASE}"


HOURS_TEMPLATE = "planejamento/produtividade_horas.html"


HOURS_ANSWER = "planejamento/produtividade_horas_resposta.html"


FIELD_DAY_FORM_TEMPLATE = "planejamento/produtividade_jornada_form.html"


FIELD_DAY_FORM_INNER = "planejamento/_prod_jornada_form.html"


SAMPLE_FORM_TEMPLATE = "planejamento/produtividade_amostragem_form.html"


SAMPLE_FORM_INNER = "planejamento/_prod_amostragem_form.html"


STOPPAGE_FORM_TEMPLATE = "planejamento/produtividade_paralisacao_form.html"


STOPPAGE_FORM_INNER = "planejamento/_prod_paralisacao_form.html"


FIELD_DAY_CREATED_MESSAGE = "Jornada registrada."


FIELD_DAY_UPDATED_MESSAGE = "Jornada atualizada."


SAMPLE_CREATED_MESSAGE = "Rodada registrada."


SAMPLE_UPDATED_MESSAGE = "Rodada atualizada."


STOPPAGE_CREATED_MESSAGE = "Paralisação registrada."


STOPPAGE_UPDATED_MESSAGE = "Paralisação atualizada."


def _hours_params(params: Mapping[str, str]) -> service.HoursFilter:
    """O filtro da aba Horas efetivas como a URL o traz."""
    return service.HoursFilter(
        company_id=_integer(params.get("empresa")),
        area=(params.get("area") or "").strip(),
        foreman=(params.get("encarregado") or "").strip(),
        period=(params.get("periodo") or "").strip(),
        cut_week=(params.get("corte") or "").strip(),
    )


def _posted_hours_filter(values: Mapping[str, str]) -> service.HoursFilter:
    """O filtro que o formulário do modal carregou nos campos ocultos ``f_*``."""
    return service.HoursFilter(
        company_id=_integer(values.get("f_empresa")),
        area=(values.get("f_area") or "").strip(),
        foreman=(values.get("f_encarregado") or "").strip(),
        period=(values.get("f_periodo") or "").strip(),
        cut_week=(values.get("f_corte") or "").strip(),
    )


def _hours_filter_values(chosen: service.HoursFilter) -> dict[str, str]:
    return {
        "empresa": "" if chosen.company_id is None else str(chosen.company_id),
        "corte": chosen.cut_week,
        "area": chosen.area,
        "encarregado": chosen.foreman,
        "periodo": chosen.period,
    }


def _hours_context(
    session: Session, context: RequestContext, *, hours_filter: service.HoursFilter
) -> dict[str, Any]:
    """O contexto da aba Horas efetivas: a visão do escopo e os auxiliares de escrita."""
    visao = service.hours_overview(
        session,
        user=context.user,
        scope=context.scope,
        hours_filter=hours_filter,
        reference_date=calendario.today(),
    )
    parameters = visao.parameters
    return {
        "horas": visao,
        "filtro_horas": _hours_filter_values(visao.filter),
        "api_horas": HOURS_API,
        "tempo": export.hours_clock,
        "horas_num": export.hours_text,
        "percentual_horas": export.percent_text,
        "pareto_paradas": export.stop_reason_chart(visao).data,
        "rotulo_semana": export.productivity_week_caption,
        "tom": _tone_class,
        "faixa_utilizacao": lambda value: calculations.utilization_band(
            value, target=parameters.utilization_pct
        ),
        "faixa_trabalho": lambda value: calculations.working_band(
            value, target=parameters.working_pct
        ),
        "faixa_atraso": lambda value: calculations.start_delay_band(value, parameters.delay_bands),
    }


def _hours_form_context(
    context: RequestContext, hours_filter: service.HoursFilter, **valores: Any
) -> dict[str, Any]:
    """O contexto de um formulário do campo: os auxiliares e nada da aba carregada."""
    return {
        "api_horas": HOURS_API,
        "filtro_horas": _hours_filter_values(hours_filter),
        "horas_num": export.hours_text,
        "percentual_horas": export.percent_text,
        "hoje": calendario.today().isoformat(),
        "tom": _tone_class,
        "pode_gerir": rbac.can(context.user, Permission.MANAGE),
        **valores,
    }


def _hours_answer(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    modal_template: str,
    hours_filter: service.HoursFilter,
    valores: Mapping[str, Any],
    status_code: int = 200,
    toast: str | None = None,
    toast_tipo: str = "ok",
) -> func.HttpResponse:
    """A resposta com o modal e a aba Horas efetivas: o que a gravação precisa atualizar."""
    page = _hours_context(session, context, hours_filter=hours_filter)
    page.update(_hours_form_context(context, hours_filter, **valores))
    page["modal_template"] = modal_template
    return AlpineAjaxResponse(
        template_name=HOURS_ANSWER,
        context=page,
        request=req,
        status_code=status_code,
        toast=toast,
        toast_tipo=toast_tipo,
    )


@bp.route(route=HOURS_BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def productivity_hours(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A aba Horas efetivas do escopo, no período e nos filtros pedidos."""
    return AlpineAjaxResponse(
        template_name=HOURS_TEMPLATE,
        context=_hours_context(session, context, hours_filter=_hours_params(req.params)),
        request=req,
    )


@bp.route(route=f"{HOURS_BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def productivity_hours_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da aba Horas efetivas, com o filtro de agora."""
    return excel_response(_hours_document(req, session, context))


@bp.route(route=f"{HOURS_BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def productivity_hours_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da aba Horas efetivas: o que o botão PDF monta e imprime."""
    return printable_response(_hours_document(req, session, context), req)


def _hours_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    visao = service.hours_overview(
        session,
        user=context.user,
        scope=context.scope,
        hours_filter=_hours_params(req.params),
        reference_date=calendario.today(),
    )
    return export.hours_document(
        visao,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


# ── Os modais do campo ─────────────────────────────────────────────────────


@bp.route(route=f"{HOURS_BASE}/jornadas/nova", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_new_field_day(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A jornada em branco; no Portfólio o shell pede o projeto antes."""
    context.scope.require_project()
    formulario = service.field_day_form(
        session,
        user=context.user,
        scope=context.scope,
        day_id=None,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        FIELD_DAY_FORM_TEMPLATE,
        _hours_form_context(
            context, _hours_params(req.params), formulario=formulario, registro_id=None
        ),
    )


@bp.route(route=f"{HOURS_BASE}/jornadas/{{registro_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_edit_field_day(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A jornada em edição, com os horários e o efetivo do registro."""
    registro_id = _route_id(req, "registro_id")
    formulario = service.field_day_form(
        session,
        user=context.user,
        scope=context.scope,
        day_id=registro_id,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        FIELD_DAY_FORM_TEMPLATE,
        _hours_form_context(
            context, _hours_params(req.params), formulario=formulario, registro_id=registro_id
        ),
    )


@bp.route(route=f"{HOURS_BASE}/amostragens/nova", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_new_sample(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A rodada em branco; no Portfólio o shell pede o projeto antes."""
    context.scope.require_project()
    formulario = service.work_sample_form(
        session,
        user=context.user,
        scope=context.scope,
        sample_id=None,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        SAMPLE_FORM_TEMPLATE,
        _hours_form_context(
            context, _hours_params(req.params), formulario=formulario, registro_id=None
        ),
    )


@bp.route(route=f"{HOURS_BASE}/amostragens/{{registro_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_edit_sample(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A rodada em edição, com os motivos já registrados."""
    registro_id = _route_id(req, "registro_id")
    formulario = service.work_sample_form(
        session,
        user=context.user,
        scope=context.scope,
        sample_id=registro_id,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        SAMPLE_FORM_TEMPLATE,
        _hours_form_context(
            context, _hours_params(req.params), formulario=formulario, registro_id=registro_id
        ),
    )


@bp.route(route=f"{HOURS_BASE}/paralisacoes/nova", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_new_stoppage(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A paralisação em branco; no Portfólio o shell pede o projeto antes."""
    context.scope.require_project()
    formulario = service.stoppage_form(
        session,
        user=context.user,
        scope=context.scope,
        stoppage_id=None,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        STOPPAGE_FORM_TEMPLATE,
        _hours_form_context(
            context, _hours_params(req.params), formulario=formulario, registro_id=None
        ),
    )


@bp.route(route=f"{HOURS_BASE}/paralisacoes/{{registro_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_edit_stoppage(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A paralisação em edição, com o recurso e a janela do registro."""
    registro_id = _route_id(req, "registro_id")
    formulario = service.stoppage_form(
        session,
        user=context.user,
        scope=context.scope,
        stoppage_id=registro_id,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        STOPPAGE_FORM_TEMPLATE,
        _hours_form_context(
            context, _hours_params(req.params), formulario=formulario, registro_id=registro_id
        ),
    )


# ── As gravações do campo ──────────────────────────────────────────────────


def _field_day_form_of(req: func.HttpRequest) -> validation.FieldDayForm:
    return validation.FieldDayForm(fields=_posted_values(req))


def _work_sample_form_of(req: func.HttpRequest) -> validation.WorkSampleForm:
    """A rodada como a validação a lê: os campos e a grade de cada tipo de motivo."""
    fields = _posted_values(req)
    stopped = _grid_of(fields, validation.FIELD_STOPPED_PREFIX)
    transit = _grid_of(fields, validation.FIELD_TRANSIT_PREFIX)
    return validation.WorkSampleForm(fields=fields, stopped=stopped, transit=transit)


def _grid_of(fields: Mapping[str, str], prefix: str) -> dict[int, str]:
    found: dict[int, str] = {}
    for key, value in fields.items():
        if key.startswith(prefix) and key[len(prefix) :].isdigit():
            found[int(key[len(prefix) :])] = value
    return found


def _stoppage_form_of(req: func.HttpRequest) -> validation.StoppageForm:
    return validation.StoppageForm(fields=_posted_values(req))


@bp.route(route=f"{HOURS_BASE}/jornadas", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_create_field_day(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra a jornada do dia; a segunda da mesma frente e dia recebe a recusa."""
    return _save_field_day(req, session, context, day_id=None)


@bp.route(route=f"{HOURS_BASE}/jornadas/{{registro_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_update_field_day(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava a edição da jornada."""
    return _save_field_day(req, session, context, day_id=_route_id(req, "registro_id"))


def _save_field_day(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    day_id: int | None,
) -> func.HttpResponse:
    form = _field_day_form_of(req)
    filtro = _posted_hours_filter(req.form)
    try:
        service.save_field_day(
            session,
            user=context.user,
            scope=context.scope,
            day_id=day_id,
            form=form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        return _field_day_error(
            req, session, context, day_id=day_id, form=form, error=error, filtro=filtro
        )
    except VersionConflictError as error:
        return _field_day_error(
            req,
            session,
            context,
            day_id=day_id,
            form=form,
            error=InvalidDataError(str(error)),
            filtro=filtro,
            status_code=409,
        )
    mensagem = FIELD_DAY_UPDATED_MESSAGE if day_id is not None else FIELD_DAY_CREATED_MESSAGE
    return _hours_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        hours_filter=filtro,
        valores={"mensagem": mensagem, "atualiza_conteudo": True},
        toast=mensagem,
    )


def _field_day_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    day_id: int | None,
    form: validation.FieldDayForm,
    error: InvalidDataError,
    filtro: service.HoursFilter,
    status_code: int = 422,
) -> func.HttpResponse:
    errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
    formulario = service.field_day_form(
        session,
        user=context.user,
        scope=context.scope,
        day_id=day_id,
        form=form,
        reference_date=calendario.today(),
        errors=errors,
    )
    return _hours_answer(
        req,
        session,
        context,
        modal_template=FIELD_DAY_FORM_INNER,
        hours_filter=filtro,
        valores={"formulario": formulario, "registro_id": day_id},
        status_code=status_code,
    )


@bp.route(route=f"{HOURS_BASE}/amostragens", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_create_sample(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra a rodada de observação com os motivos."""
    return _save_sample(req, session, context, sample_id=None)


@bp.route(route=f"{HOURS_BASE}/amostragens/{{registro_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_update_sample(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava a edição da rodada, trocando os motivos junto."""
    return _save_sample(req, session, context, sample_id=_route_id(req, "registro_id"))


def _save_sample(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    sample_id: int | None,
) -> func.HttpResponse:
    form = _work_sample_form_of(req)
    filtro = _posted_hours_filter(req.form)
    try:
        service.save_work_sample(
            session,
            user=context.user,
            scope=context.scope,
            sample_id=sample_id,
            form=form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        return _sample_error(
            req, session, context, sample_id=sample_id, form=form, error=error, filtro=filtro
        )
    except VersionConflictError as error:
        return _sample_error(
            req,
            session,
            context,
            sample_id=sample_id,
            form=form,
            error=InvalidDataError(str(error)),
            filtro=filtro,
            status_code=409,
        )
    mensagem = SAMPLE_UPDATED_MESSAGE if sample_id is not None else SAMPLE_CREATED_MESSAGE
    return _hours_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        hours_filter=filtro,
        valores={"mensagem": mensagem, "atualiza_conteudo": True},
        toast=mensagem,
    )


def _sample_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    sample_id: int | None,
    form: validation.WorkSampleForm,
    error: InvalidDataError,
    filtro: service.HoursFilter,
    status_code: int = 422,
) -> func.HttpResponse:
    errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
    formulario = service.work_sample_form(
        session,
        user=context.user,
        scope=context.scope,
        sample_id=sample_id,
        form=form,
        reference_date=calendario.today(),
        errors=errors,
    )
    return _hours_answer(
        req,
        session,
        context,
        modal_template=SAMPLE_FORM_INNER,
        hours_filter=filtro,
        valores={"formulario": formulario, "registro_id": sample_id},
        status_code=status_code,
    )


@bp.route(route=f"{HOURS_BASE}/paralisacoes", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_create_stoppage(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra a paralisação de efetivo ou de máquina e equipamento."""
    return _save_stoppage(req, session, context, stoppage_id=None)


@bp.route(route=f"{HOURS_BASE}/paralisacoes/{{registro_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_update_stoppage(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava a edição da paralisação."""
    return _save_stoppage(req, session, context, stoppage_id=_route_id(req, "registro_id"))


def _save_stoppage(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    stoppage_id: int | None,
) -> func.HttpResponse:
    form = _stoppage_form_of(req)
    filtro = _posted_hours_filter(req.form)
    try:
        service.save_stoppage(
            session,
            user=context.user,
            scope=context.scope,
            stoppage_id=stoppage_id,
            form=form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        return _stoppage_error(
            req,
            session,
            context,
            stoppage_id=stoppage_id,
            form=form,
            error=error,
            filtro=filtro,
        )
    except VersionConflictError as error:
        return _stoppage_error(
            req,
            session,
            context,
            stoppage_id=stoppage_id,
            form=form,
            error=InvalidDataError(str(error)),
            filtro=filtro,
            status_code=409,
        )
    mensagem = STOPPAGE_UPDATED_MESSAGE if stoppage_id is not None else STOPPAGE_CREATED_MESSAGE
    return _hours_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        hours_filter=filtro,
        valores={"mensagem": mensagem, "atualiza_conteudo": True},
        toast=mensagem,
    )


def _stoppage_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    stoppage_id: int | None,
    form: validation.StoppageForm,
    error: InvalidDataError,
    filtro: service.HoursFilter,
    status_code: int = 422,
) -> func.HttpResponse:
    errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
    formulario = service.stoppage_form(
        session,
        user=context.user,
        scope=context.scope,
        stoppage_id=stoppage_id,
        form=form,
        reference_date=calendario.today(),
        errors=errors,
    )
    return _hours_answer(
        req,
        session,
        context,
        modal_template=STOPPAGE_FORM_INNER,
        hours_filter=filtro,
        valores={"formulario": formulario, "registro_id": stoppage_id},
        status_code=status_code,
    )


# ── KPIs de performance da Produtividade (ISSUE-048) ──────────────────────


PERFORMANCE_BASE = f"{PRODUTIVIDADE_BASE}/kpis"


PERFORMANCE_API = f"/api/{PERFORMANCE_BASE}"


PERFORMANCE_TEMPLATE = "planejamento/produtividade_kpis.html"


PERFORMANCE_ANSWER = "planejamento/produtividade_kpis_resposta.html"


PLAN_FORM_TEMPLATE = "planejamento/produtividade_plano_form.html"


PLAN_FORM_INNER = "planejamento/_prod_plano_form.html"


PERFORMANCE_TARGET = "produtividade-kpis"


PLAN_CREATED_MESSAGE = "Ação criada na Central ({reference})."


def _performance_params(params: Mapping[str, str]) -> service.PerformanceFilter:
    """O filtro da aba KPIs como a URL o traz."""
    return service.PerformanceFilter(
        company_id=_integer(params.get("empresa")),
        cut_week=(params.get("corte") or "").strip(),
    )


def _posted_performance_filter(values: Mapping[str, str]) -> service.PerformanceFilter:
    """O filtro que o formulário do modal carregou nos campos ocultos ``f_*``."""
    return service.PerformanceFilter(
        company_id=_integer(values.get("f_empresa")),
        cut_week=(values.get("f_corte") or "").strip(),
    )


def _performance_filter_values(chosen: service.PerformanceFilter) -> dict[str, str]:
    return {
        "empresa": "" if chosen.company_id is None else str(chosen.company_id),
        "corte": chosen.cut_week,
    }


def _performance_context(
    session: Session, context: RequestContext, *, performance_filter: service.PerformanceFilter
) -> dict[str, Any]:
    """O contexto da aba KPIs: a visão do escopo e os auxiliares de formatação."""
    visao = service.performance_overview(
        session,
        user=context.user,
        scope=context.scope,
        performance_filter=performance_filter,
        reference_date=calendario.today(),
    )
    parameters = visao.parameters
    return {
        "performance": visao,
        "filtro_performance": _performance_filter_values(visao.filter),
        "api_performance": PERFORMANCE_API,
        "rotulo_semana": export.productivity_week_caption,
        "semana_curta": export.productivity_week_short,
        "indice": export.index_text,
        "percentual": export.percent_text,
        "horas_num": export.hours_text,
        "tom": _tone_class,
        "rotulo_indicador": lambda key: service.INDICATOR_LABELS.get(key, key),
        "faixa_aderencia": lambda value: calculations.indicator_band(
            value, parameters.adherence_bands, higher_is_better=True
        ),
        "faixa_pf": lambda value: calculations.indicator_band(
            value, parameters.pf_bands, higher_is_better=False
        ),
        "faixa_spi": lambda value: calculations.indicator_band(
            value, parameters.spi_bands, higher_is_better=True
        ),
        "faixa_trabalho": lambda value: calculations.working_band(
            value, target=parameters.working_pct
        ),
        "faixa_utilizacao": lambda value: calculations.utilization_band(
            value, target=parameters.utilization_pct
        ),
    }


def _performance_form_context(
    context: RequestContext, performance_filter: service.PerformanceFilter, **valores: Any
) -> dict[str, Any]:
    """O contexto de um formulário do plano: os auxiliares e nada da aba carregada."""
    return {
        "api_performance": PERFORMANCE_API,
        "filtro_performance": _performance_filter_values(performance_filter),
        "rotulo_semana": export.productivity_week_caption,
        "semana_curta": export.productivity_week_short,
        "hoje": calendario.today().isoformat(),
        "tom": _tone_class,
        "pode_gerir": rbac.can(context.user, Permission.MANAGE),
        **valores,
    }


def _performance_answer(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    modal_template: str,
    performance_filter: service.PerformanceFilter,
    valores: Mapping[str, Any],
    status_code: int = 200,
    toast: str | None = None,
    toast_tipo: str = "ok",
) -> func.HttpResponse:
    """A resposta com o modal e a aba KPIs: o que a gravação do plano precisa atualizar."""
    page = _performance_context(session, context, performance_filter=performance_filter)
    page.update(_performance_form_context(context, performance_filter, **valores))
    page["modal_template"] = modal_template
    return AlpineAjaxResponse(
        template_name=PERFORMANCE_ANSWER,
        context=page,
        request=req,
        status_code=status_code,
        toast=toast,
        toast_tipo=toast_tipo,
    )


@bp.route(route=PERFORMANCE_BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def productivity_performance(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A aba KPIs de performance do escopo, na empresa e no corte pedidos."""
    return AlpineAjaxResponse(
        template_name=PERFORMANCE_TEMPLATE,
        context=_performance_context(
            session, context, performance_filter=_performance_params(req.params)
        ),
        request=req,
    )


@bp.route(route=f"{PERFORMANCE_BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def productivity_performance_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da aba KPIs, com o filtro de agora."""
    return excel_response(_performance_document(req, session, context))


@bp.route(route=f"{PERFORMANCE_BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def productivity_performance_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da aba KPIs: o que o botão PDF monta e imprime."""
    return printable_response(_performance_document(req, session, context), req)


def _performance_document(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    visao = service.performance_overview(
        session,
        user=context.user,
        scope=context.scope,
        performance_filter=_performance_params(req.params),
        reference_date=calendario.today(),
    )
    return export.performance_document(
        visao,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


@bp.route(route=f"{PERFORMANCE_BASE}/acoes/nova", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def productivity_new_performance_action(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O plano de ação em branco da empresa pedida; no Portfólio o shell pede o projeto antes."""
    context.scope.require_project()
    visao = service.performance_overview(
        session,
        user=context.user,
        scope=context.scope,
        performance_filter=_performance_params(req.params),
        reference_date=calendario.today(),
    )
    formulario = service.performance_action_form(
        session,
        user=context.user,
        block=visao.selected,
        cut_week=visao.cut_week,
        window_weeks=visao.parameters.window_weeks,
        form=None,
        reference_date=calendario.today(),
    )
    return _modal(
        req,
        PLAN_FORM_TEMPLATE,
        _performance_form_context(context, visao.filter, formulario=formulario),
    )


@bp.route(route=f"{PERFORMANCE_BASE}/acoes", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def productivity_create_performance_action(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cria o plano de ação na Central; a segunda da mesma empresa e semana recebe 422."""
    form = validation.ActionPlanForm(fields=_posted_values(req))
    filtro = _posted_performance_filter(req.form)
    try:
        criada = service.create_performance_action(
            session,
            user=context.user,
            scope=context.scope,
            form=form,
            cut_week=filtro.cut_week,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        return _performance_action_error(
            req, session, context, form=form, error=error, filtro=filtro
        )
    mensagem = PLAN_CREATED_MESSAGE.format(reference=criada.reference)
    return _performance_answer(
        req,
        session,
        context,
        modal_template=SAVED_INNER,
        performance_filter=filtro,
        valores={"mensagem": mensagem, "atualiza_conteudo": True},
        toast=mensagem,
    )


def _performance_action_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    form: validation.ActionPlanForm,
    error: InvalidDataError,
    filtro: service.PerformanceFilter,
    status_code: int = 422,
) -> func.HttpResponse:
    errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
    visao = service.performance_overview(
        session,
        user=context.user,
        scope=context.scope,
        performance_filter=filtro,
        reference_date=calendario.today(),
    )
    formulario = service.performance_action_form(
        session,
        user=context.user,
        block=visao.selected,
        cut_week=visao.cut_week,
        window_weeks=visao.parameters.window_weeks,
        form=form,
        reference_date=calendario.today(),
        errors=errors,
    )
    return _performance_answer(
        req,
        session,
        context,
        modal_template=PLAN_FORM_INNER,
        performance_filter=visao.filter,
        valores={"formulario": formulario},
        status_code=status_code,
    )


# ── Punch list (ISSUE-049) ────────────────────────────────────────────────


PUNCH_BASE = "planejamento/punch"


PUNCH_API = f"/api/{PUNCH_BASE}"


PUNCH_SCREEN_TEMPLATE = "planejamento/punch.html"


PUNCH_FILTERS_FORM_TEMPLATE = "planejamento/punch_filtros_form.html"


PUNCH_ITEM_FORM_TEMPLATE = "planejamento/punch_item_form.html"


PUNCH_ITEM_FORM_INNER = "planejamento/_punch_item_form.html"


PUNCH_VERIFICATION_FORM_TEMPLATE = "planejamento/punch_fechamento_form.html"


PUNCH_VERIFICATION_FORM_INNER = "planejamento/_punch_fechamento_form.html"


PUNCH_CANCELLATION_FORM_TEMPLATE = "planejamento/punch_cancelar_form.html"


PUNCH_CANCELLATION_FORM_INNER = "planejamento/_punch_cancelar_form.html"


PUNCH_ANSWER_TEMPLATE = "planejamento/punch_resposta.html"


PUNCH_SAVED_INNER = "planejamento/_punch_salvo.html"


PUNCH_ERROR_INNER = "planejamento/_punch_erro.html"


PUNCH_MODAL_TARGET = "punch-modal"


PUNCH_PAGE_CLASS = "pagina--planejamento-punch_list"


PUNCH_DASHBOARD_BASE = f"{PUNCH_BASE}/painel"


PUNCH_DASHBOARD_API = f"/api/{PUNCH_DASHBOARD_BASE}"


PUNCH_DASHBOARD_TEMPLATE = "planejamento/punch_painel.html"


PUNCH_DASHBOARD_TARGET = "punch-painel"


PUNCH_CREATED_MESSAGE = "{code} aberto; ação criada na Central."


PUNCH_UPDATED_MESSAGE = "{code} atualizado."


PUNCH_TREATED_MESSAGE = "{code} em tratamento."


PUNCH_SENT_MESSAGE = "{code} enviado para verificação."


PUNCH_CLOSED_MESSAGE = "{code} fechado."


PUNCH_REJECTED_MESSAGE = "{code} reprovado e devolvido para tratamento."


PUNCH_CANCELLED_MESSAGE = "{code} cancelado."


PUNCH_SITUATION_TONES = {
    "Aberto": "warn",
    "Em tratamento": "info",
    "Aguardando verificação": "fix",
    "Fechado": "ok",
    "Cancelado": "neutral",
}


PUNCH_CATEGORY_TONES = {"A": "erro", "B": "fix", "C": "info"}


def _punch_filter_values(chosen: service.PunchFilter) -> dict[str, str]:
    """O filtro como os formulários e a tela o leem."""
    return {
        "busca": chosen.search,
        "situacao": chosen.situation,
        "categoria": chosen.category,
        "sistema": "" if chosen.system_id is None else str(chosen.system_id),
        "disciplina": chosen.discipline,
        "empresa": "" if chosen.company_id is None else str(chosen.company_id),
        "vencidos": "1" if chosen.overdue else "",
    }


def _punch_params(params: Mapping[str, str]) -> service.PunchFilter:
    """O filtro que a URL trouxe."""
    return service.PunchFilter(
        search=(params.get("busca") or "").strip(),
        situation=(params.get("situacao") or validation.PUNCH_SITUATION_FILTER_OPEN).strip(),
        category=(params.get("categoria") or "").strip(),
        system_id=_integer(params.get("sistema")),
        discipline=(params.get("disciplina") or "").strip(),
        company_id=_integer(params.get("empresa")),
        overdue=(params.get("vencidos") or "") == "1",
    )


def _posted_punch_filter(values: Mapping[str, str]) -> service.PunchFilter:
    """O filtro que o formulário carregou nos campos ocultos ``f_*``."""
    return service.PunchFilter(
        search=(values.get("f_busca") or "").strip(),
        situation=(values.get("f_situacao") or "").strip(),
        category=(values.get("f_categoria") or "").strip(),
        system_id=_integer(values.get("f_sistema")),
        discipline=(values.get("f_disciplina") or "").strip(),
        company_id=_integer(values.get("f_empresa")),
        overdue=(values.get("f_vencidos") or "") == "1",
    )


def _punch_query(chosen: service.PunchFilter) -> str:
    """A consulta dos modais e da exportação, sem os valores que são o padrão da tela."""
    return urlencode(
        {
            key: value
            for key, value in _punch_filter_values(chosen).items()
            if value and not (key == "situacao" and value == validation.PUNCH_SITUATION_FILTER_OPEN)
        }
    )


def _punch_context(
    session: Session, context: RequestContext, *, punch_filter: service.PunchFilter
) -> dict[str, Any]:
    """O contexto da tela: a visão, as escolhas do filtro e os auxiliares de formatação."""
    visao = service.punch_overview(
        session,
        user=context.user,
        scope=context.scope,
        punch_filter=punch_filter,
        reference_date=calendario.today(),
    )
    return {
        "visao": visao,
        "filtro": _punch_filter_values(visao.filter),
        "opcoes": service.punch_filter_options(session, scope=context.scope),
        "api": PUNCH_API,
        "consulta": _punch_query(visao.filter),
        "hoje": calendario.today().isoformat(),
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "percentual": export.percent_text,
        "tom_situacao": lambda situacao: PUNCH_SITUATION_TONES.get(situacao, "neutral"),
        "tom_categoria": lambda categoria: PUNCH_CATEGORY_TONES.get(categoria, "neutral"),
        "formatar_data": _format_punch_date,
    }


def _punch_form_context(
    context: RequestContext, chosen: service.PunchFilter, **valores: Any
) -> dict[str, Any]:
    """O contexto de um formulário do modal: o filtro de volta e nada da lista carregada."""
    return {
        "api": PUNCH_API,
        "hoje": calendario.today().isoformat(),
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "consulta": _punch_query(chosen),
        "filtro": _punch_filter_values(chosen),
        "tom_situacao": lambda situacao: PUNCH_SITUATION_TONES.get(situacao, "neutral"),
        "tom_categoria": lambda categoria: PUNCH_CATEGORY_TONES.get(categoria, "neutral"),
        "formatar_data": _format_punch_date,
        **valores,
    }


def _punch_dashboard_context(session: Session, context: RequestContext) -> dict[str, Any]:
    """O contexto do painel da Punch list: a visão do escopo e os auxiliares de formatação."""
    painel = service.punch_dashboard(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
    )
    return {
        "painel": painel,
        "api_painel": PUNCH_DASHBOARD_API,
        "percentual": export.percent_text,
    }


def _punch_modal(
    req: func.HttpRequest,
    template: str,
    context: Mapping[str, Any],
    *,
    status_code: int = 200,
) -> func.HttpResponse:
    """Um modal sozinho, para o pedido que o abre (alvo: ``punch-modal``)."""
    return AlpineAjaxResponse(
        template_name=template,
        context=dict(context),
        request=req,
        target_id=PUNCH_MODAL_TARGET,
        root_class=PUNCH_PAGE_CLASS,
        status_code=status_code,
    )


def _punch_answer(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    modal_template: str,
    punch_filter: service.PunchFilter,
    valores: Mapping[str, Any],
    status_code: int = 200,
    toast: str | None = None,
    toast_tipo: str = "ok",
) -> func.HttpResponse:
    """A resposta com o modal, os filtros e a lista: o que a gravação precisa atualizar."""
    page = _punch_context(session, context, punch_filter=punch_filter)
    page.update(_punch_form_context(context, punch_filter, **valores))
    page["modal_template"] = modal_template
    return AlpineAjaxResponse(
        template_name=PUNCH_ANSWER_TEMPLATE,
        context=page,
        request=req,
        status_code=status_code,
        toast=toast,
        toast_tipo=toast_tipo,
    )


def _punch_errors(error: InvalidDataError) -> dict[str, str]:
    return dict(error.detail) if isinstance(error.detail, Mapping) else {"geral": str(error)}


def _format_punch_date(value: date | None) -> str:
    """``25/09/2026``; o travessão quando não há data."""
    return "—" if value is None else format_value(ValueKind.DATE, value)


@bp.route(route=PUNCH_BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def punch_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Os filtros, a lista, o painel e o modal vazio do escopo, no filtro da URL."""
    page = _punch_context(session, context, punch_filter=_punch_params(req.params))
    page.update(_punch_dashboard_context(session, context))
    return AlpineAjaxResponse(
        template_name=PUNCH_SCREEN_TEMPLATE,
        context=page,
        request=req,
    )


def _punch_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """O documento da lista para o filtro do pedido; o único lugar com o relógio."""
    chosen = _punch_params(req.params)
    visao = service.punch_overview(
        session,
        user=context.user,
        scope=context.scope,
        punch_filter=chosen,
        reference_date=calendario.today(),
    )
    return export.punch_document(
        visao,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
        options=service.punch_filter_options(session, scope=context.scope),
    )


@bp.route(route=f"{PUNCH_BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def punch_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da lista, com o filtro de agora."""
    return excel_response(_punch_document(req, session, context))


@bp.route(route=f"{PUNCH_BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def punch_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da lista: o que o botão PDF monta e imprime."""
    return printable_response(_punch_document(req, session, context), req)


@bp.route(route=f"{PUNCH_BASE}/filtros", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def punch_filters(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O modal de filtros, com as escolhas do escopo."""
    chosen = _punch_params(req.params)
    return _punch_modal(
        req,
        PUNCH_FILTERS_FORM_TEMPLATE,
        _punch_form_context(
            context,
            chosen,
            opcoes=service.punch_filter_options(session, scope=context.scope),
        ),
    )


@bp.route(route=f"{PUNCH_BASE}/itens/novo", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def punch_new_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do item em branco; no Portfólio o shell pede o projeto antes."""
    chosen = _punch_params(req.params)
    formulario = service.punch_item_form(session, user=context.user, scope=context.scope)
    return _punch_modal(
        req,
        PUNCH_ITEM_FORM_TEMPLATE,
        _punch_form_context(context, chosen, formulario=formulario),
    )


@bp.route(route=f"{PUNCH_BASE}/itens/{{item_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def punch_edit_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do item com o que está gravado."""
    chosen = _punch_params(req.params)
    formulario = service.punch_item_form(
        session, user=context.user, scope=context.scope, item_id=_route_id(req, "item_id")
    )
    return _punch_modal(
        req,
        PUNCH_ITEM_FORM_TEMPLATE,
        _punch_form_context(context, chosen, formulario=formulario),
    )


def _punch_item_error(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    item_id: int | None,
    form: validation.PunchItemForm,
    error: InvalidDataError,
    status_code: int,
    chosen: service.PunchFilter,
) -> func.HttpResponse:
    """O formulário do item de volta, preenchido e com as mensagens."""
    formulario = service.punch_item_form(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        form=form,
        errors=_punch_errors(error),
    )
    return _punch_answer(
        req,
        session,
        context,
        modal_template=PUNCH_ITEM_FORM_INNER,
        punch_filter=chosen,
        valores={"formulario": formulario},
        status_code=status_code,
        toast=error.messages()[0] if error.messages() else None,
        toast_tipo="erro",
    )


@bp.route(route=f"{PUNCH_BASE}/itens", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def punch_create_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Inclui o item e abre a ação da Central; o formulário volta com as mensagens no 422."""
    form = validation.PunchItemForm(fields=_posted_values(req))
    chosen = _posted_punch_filter(req.form)
    try:
        item = service.create_punch_item(
            session,
            user=context.user,
            scope=context.scope,
            form=form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        return _punch_item_error(
            req,
            session,
            context,
            item_id=None,
            form=form,
            error=error,
            status_code=422,
            chosen=chosen,
        )
    mensagem = PUNCH_CREATED_MESSAGE.format(code=item.code)
    return _punch_answer(
        req,
        session,
        context,
        modal_template=PUNCH_SAVED_INNER,
        punch_filter=chosen,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


@bp.route(route=f"{PUNCH_BASE}/itens/{{item_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def punch_update_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Salva o item aberto e espelha a ação ligada a ele."""
    item_id = _route_id(req, "item_id")
    form = validation.PunchItemForm(fields=_posted_values(req))
    chosen = _posted_punch_filter(req.form)
    try:
        item = service.update_punch_item(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            version=req.form.get("versao"),
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        return _punch_item_error(
            req,
            session,
            context,
            item_id=item_id,
            form=form,
            error=error,
            status_code=422,
            chosen=chosen,
        )
    except VersionConflictError as error:
        return _punch_item_error(
            req,
            session,
            context,
            item_id=item_id,
            form=form,
            error=InvalidDataError(str(error)),
            status_code=409,
            chosen=chosen,
        )
    mensagem = PUNCH_UPDATED_MESSAGE.format(code=item.code)
    return _punch_answer(
        req,
        session,
        context,
        modal_template=PUNCH_SAVED_INNER,
        punch_filter=chosen,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


def _punch_refusal(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    error: InvalidDataError | VersionConflictError | AccessDeniedError,
    chosen: service.PunchFilter,
) -> func.HttpResponse:
    """A recusa de uma transição: a lista de volta, o aviso do motivo e o status certo."""
    if isinstance(error, AccessDeniedError):
        status = 403
    elif isinstance(error, VersionConflictError):
        status = 409
    else:
        status = 422
    mensagens = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return _punch_answer(
        req,
        session,
        context,
        modal_template=PUNCH_ERROR_INNER,
        punch_filter=chosen,
        valores={"mensagens": mensagens},
        status_code=status,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=f"{PUNCH_BASE}/itens/{{item_id}}/tratar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def punch_treat_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Move o item aberto para Em tratamento."""
    item_id = _route_id(req, "item_id")
    chosen = _posted_punch_filter(req.form)
    try:
        item = service.treat_punch_item(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            version=req.form.get("versao"),
            reference_date=calendario.today(),
        )
    except (InvalidDataError, VersionConflictError, AccessDeniedError) as error:
        return _punch_refusal(req, session, context, error=error, chosen=chosen)
    mensagem = PUNCH_TREATED_MESSAGE.format(code=item.code)
    return _punch_answer(
        req,
        session,
        context,
        modal_template=PUNCH_SAVED_INNER,
        punch_filter=chosen,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


@bp.route(route=f"{PUNCH_BASE}/itens/{{item_id}}/enviar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def punch_send_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Envia o item em tratamento para a verificação."""
    item_id = _route_id(req, "item_id")
    chosen = _posted_punch_filter(req.form)
    try:
        item = service.send_punch_item_to_verification(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            version=req.form.get("versao"),
            reference_date=calendario.today(),
        )
    except (InvalidDataError, VersionConflictError, AccessDeniedError) as error:
        return _punch_refusal(req, session, context, error=error, chosen=chosen)
    mensagem = PUNCH_SENT_MESSAGE.format(code=item.code)
    return _punch_answer(
        req,
        session,
        context,
        modal_template=PUNCH_SAVED_INNER,
        punch_filter=chosen,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


@bp.route(route=f"{PUNCH_BASE}/itens/{{item_id}}/verificacao", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def punch_verification_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O fechamento com verificação: o resumo, os anexos do item e o resultado."""
    chosen = _punch_params(req.params)
    formulario = service.punch_verification_form(
        session, user=context.user, scope=context.scope, item_id=_route_id(req, "item_id")
    )
    return _punch_modal(
        req,
        PUNCH_VERIFICATION_FORM_TEMPLATE,
        _punch_form_context(context, chosen, formulario=formulario),
    )


@bp.route(route=f"{PUNCH_BASE}/itens/{{item_id}}/verificacao", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def punch_verify_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Aprova (exige evidência; o executante recebe 403) ou reprova a verificação do item."""
    item_id = _route_id(req, "item_id")
    form = validation.PunchVerificationForm(fields=_posted_values(req))
    chosen = _posted_punch_filter(req.form)
    try:
        item = service.verify_punch_item(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            version=req.form.get("versao"),
            reference_date=calendario.today(),
        )
    except AccessDeniedError as error:
        formulario = service.punch_verification_form(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            errors={"geral": str(error)},
        )
        return _punch_answer(
            req,
            session,
            context,
            modal_template=PUNCH_VERIFICATION_FORM_INNER,
            punch_filter=chosen,
            valores={"formulario": formulario},
            status_code=403,
            toast=str(error),
            toast_tipo="erro",
        )
    except InvalidDataError as error:
        formulario = service.punch_verification_form(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            errors=_punch_errors(error),
        )
        return _punch_answer(
            req,
            session,
            context,
            modal_template=PUNCH_VERIFICATION_FORM_INNER,
            punch_filter=chosen,
            valores={"formulario": formulario},
            status_code=422,
            toast=error.messages()[0] if error.messages() else None,
            toast_tipo="erro",
        )
    mensagem = (
        PUNCH_CLOSED_MESSAGE.format(code=item.code)
        if item.situation == validation.PUNCH_CLOSED
        else PUNCH_REJECTED_MESSAGE.format(code=item.code)
    )
    return _punch_answer(
        req,
        session,
        context,
        modal_template=PUNCH_SAVED_INNER,
        punch_filter=chosen,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


@bp.route(route=f"{PUNCH_BASE}/itens/{{item_id}}/cancelamento", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def punch_cancellation_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O cancelamento do item: a justificativa obrigatória."""
    chosen = _punch_params(req.params)
    formulario = service.punch_cancellation_form(
        session, user=context.user, scope=context.scope, item_id=_route_id(req, "item_id")
    )
    return _punch_modal(
        req,
        PUNCH_CANCELLATION_FORM_TEMPLATE,
        _punch_form_context(context, chosen, formulario=formulario),
    )


@bp.route(route=f"{PUNCH_BASE}/itens/{{item_id}}/cancelamento", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def punch_cancel_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cancela o item aberto com justificativa e encerra a ação ligada a ele."""
    item_id = _route_id(req, "item_id")
    form = validation.PunchCancellationForm(fields=_posted_values(req))
    chosen = _posted_punch_filter(req.form)
    try:
        item = service.cancel_punch_item(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            version=req.form.get("versao"),
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        formulario = service.punch_cancellation_form(
            session,
            user=context.user,
            scope=context.scope,
            item_id=item_id,
            form=form,
            errors=_punch_errors(error),
        )
        return _punch_answer(
            req,
            session,
            context,
            modal_template=PUNCH_CANCELLATION_FORM_INNER,
            punch_filter=chosen,
            valores={"formulario": formulario},
            status_code=422,
            toast=error.messages()[0] if error.messages() else None,
            toast_tipo="erro",
        )
    mensagem = PUNCH_CANCELLED_MESSAGE.format(code=item.code)
    return _punch_answer(
        req,
        session,
        context,
        modal_template=PUNCH_SAVED_INNER,
        punch_filter=chosen,
        valores={"mensagem": mensagem},
        toast=mensagem,
    )


# ── Painel da Punch list (ISSUE-050) ───────────────────────────────────────


@bp.route(route=PUNCH_DASHBOARD_BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def punch_dashboard(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O painel de completação do escopo: burndown, aging, contagens e liberação (HU-070)."""
    return AlpineAjaxResponse(
        template_name=PUNCH_DASHBOARD_TEMPLATE,
        context=_punch_dashboard_context(session, context),
        request=req,
    )


def _punch_dashboard_document(session: Session, context: RequestContext) -> Document:
    """O documento do painel: o mesmo conteúdo da tela para o Excel e a impressão."""
    painel = service.punch_dashboard(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
    )
    return export.punch_dashboard_document(
        painel,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


@bp.route(route=f"{PUNCH_DASHBOARD_BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def punch_dashboard_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do painel: indicadores, gráficos como tabelas e a liberação dos sistemas."""
    del req
    return excel_response(_punch_dashboard_document(session, context))


@bp.route(route=f"{PUNCH_DASHBOARD_BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def punch_dashboard_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do painel: o que o botão PDF monta e imprime."""
    return printable_response(_punch_dashboard_document(session, context), req)
