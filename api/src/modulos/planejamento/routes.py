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
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, export, service, validation
from src.modulos.planejamento.validation import PointInput

bp = func.Blueprint()


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
