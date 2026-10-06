"""Routes of the Central de Ações: the screen Ações, its exports and its forms (D14, ISSUE-019).

Prefix ``/api/central-acoes/``. The screen is one fragment, ``acoes-conteudo``: KPIs, chips,
toolbar and the list or the kanban. Everything that changes the view (a KPI, a chip, the switch
between list and kanban, a page, the search, the filter modal) is a plain GET of the same route
with the filters in the query string, answered with the same fragment. Replanning and completing
are forms opened in a modal (``acoes-modal-corpo``): a GET draws the form, a POST saves and
answers the refreshed screen; a refusal (422, 409, 403) answers the form again, filled in, in the
modal. The attachments of an action are the generic ``/api/anexos?origem=acao&registro=<id>``.

* ``GET  acoes``                          the screen (filters, view and page by query);
* ``GET  acoes/excel`` and ``acoes/imprimivel``  the two exports of what the screen shows;
* ``GET  acoes/{acao_id}/replanejar``     the replan form; ``POST`` saves (justification required);
* ``GET  acoes/{acao_id}/concluir``       the completion form; ``POST`` saves;
* ``GET  acoes/{acao_id}/historico``      the justifications of the replans.

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.central_acoes import calculations, export, presentation, service, validation
from src.modulos.central_acoes.calculations import ActionStatus, StatusFilter
from src.modulos.central_acoes.origins import ORIGINS
from src.modulos.central_acoes.validation import ActionFilters, CompletionRequest, ReplanRequest
from src.modulos.configuracoes import service as configuracoes

bp = func.Blueprint()

MODULE = "central_acoes"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

CONTENT_TARGET = "acoes-conteudo"
MODAL_TARGET = "acoes-modal-corpo"

LIST_TEMPLATE = "central_acoes/acoes.html"
REPLAN_TEMPLATE = "central_acoes/acoes_replanejar.html"
COMPLETE_TEMPLATE = "central_acoes/acoes_concluir.html"
HISTORY_TEMPLATE = "central_acoes/acoes_historico.html"

REPLANNED_NOTICE = "Replanejamento registrado."
COMPLETED_NOTICE = "Ação concluída."
INVALID_ACTION_MESSAGE = "Informe a ação."

STATUS_PILLS = {
    ActionStatus.IN_PROGRESS: "pill--fix",
    ActionStatus.OVERDUE: "pill--erro",
    ActionStatus.COMPLETED: "pill--ok",
    ActionStatus.INFORMATION: "pill--neutral",
}

# The kanban: one column per status, with the tone of its card.
BOARD_COLUMNS = (
    (ActionStatus.IN_PROGRESS, "Em dia", "info"),
    (ActionStatus.OVERDUE, "Atrasadas", "erro"),
    (ActionStatus.COMPLETED, "Concluídas", "ok"),
)


def _error_status(error: DomainError) -> int:
    """The status of a refusal: 403, 409 for a stale screen, 422 for data that does not hold up."""
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


def _modal_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A refusal inside the modal: the message in the modal body, where the person is looking."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=MODAL_TARGET,
        status_code=_error_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


@dataclass(frozen=True)
class Query:
    """What the query string of the screen says: the filters and the way they are shown."""

    filters: ActionFilters
    view: str

    @classmethod
    def of(cls, params: Mapping[str, str]) -> Query:
        """Read the filters, the view and the page from the parameters of a request."""
        return cls(filters=validation.parse_filters(params), view=validation.parse_view(params))


@dataclass(frozen=True)
class KpiCard:
    """A clickable KPI: the number, what it is read against and the link that filters by it."""

    status: StatusFilter
    label: str
    icon: str
    tone: str
    value: int
    reference_label: str
    reference_value: str
    footer: str
    url: str
    active: bool


@dataclass(frozen=True)
class BoardColumn:
    """A column of the kanban: its title, tone and the cards."""

    title: str
    tone: str
    rows: tuple[service.ActionRow, ...]


@dataclass(frozen=True)
class ChipLink:
    """A chip of the active filters with the address that removes it."""

    text: str
    removable: bool
    url: str


# ── The screen ───────────────────────────────────────────────────────────────────────────────


@bp.route(route="central-acoes/acoes", methods=["GET"])
@fragment_route(access=READ)
def list_actions_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The screen: KPIs, chips, toolbar and the list or the kanban, for the filters in the query."""
    return _screen(req, session, context, query=Query.of(req.params))


@bp.route(route="central-acoes/acoes/excel", methods=["GET"])
@file_route(access=READ)
def actions_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the actions of the filter: what the screen lists, with its KPIs."""
    return excel_response(_document(req, session, context))


@bp.route(route="central-acoes/acoes/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def actions_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


# ── The forms of the modal ───────────────────────────────────────────────────────────────────


@bp.route(route="central-acoes/acoes/{acao_id}/replanejar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def replan_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The replan form: the deadline in force, the new date and the justification."""
    return _form(
        session,
        context,
        template=REPLAN_TEMPLATE,
        state=_FormState(action_id=_action_id(req), query=req.params.get("consulta", ""), req=req),
    )


@bp.route(route="central-acoes/acoes/{acao_id}/replanejar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def replan_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Replan with a justification and answer the refreshed screen, or the form with its messages."""
    form = req.form
    request = ReplanRequest(
        action_id=_action_id(req),
        new_date=validation.parse_date(form.get("data")),
        justification=form.get("justificativa") or "",
        version=form.get("versao"),
    )
    today = calendario.today()
    error = _attempt(
        session,
        lambda: service.replan_action(
            session, user=context.user, request=request, reference_date=today
        ),
    )
    state = _FormState(
        action_id=request.action_id,
        query=form.get("consulta", ""),
        req=req,
        values={"data": form.get("data", ""), "justificativa": request.justification},
        version=form.get("versao"),
    )
    if error is not None:
        return _form(session, context, template=REPLAN_TEMPLATE, state=state, error=error)
    return _saved(req, session, context, state=state, notice=REPLANNED_NOTICE)


@bp.route(route="central-acoes/acoes/{acao_id}/concluir", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def complete_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The completion form: the completion date, today by default."""
    return _form(
        session,
        context,
        template=COMPLETE_TEMPLATE,
        state=_FormState(
            action_id=_action_id(req),
            query=req.params.get("consulta", ""),
            req=req,
            values={"data_conclusao": calendario.today().isoformat()},
        ),
    )


@bp.route(route="central-acoes/acoes/{acao_id}/concluir", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def complete_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Complete the action and answer the refreshed screen, or the form with its messages."""
    form = req.form
    request = CompletionRequest(
        action_id=_action_id(req),
        completed_on=validation.parse_date(form.get("data_conclusao")),
        version=form.get("versao"),
    )
    today = calendario.today()
    error = _attempt(
        session,
        lambda: service.complete_action(
            session, user=context.user, request=request, reference_date=today
        ),
    )
    state = _FormState(
        action_id=request.action_id,
        query=form.get("consulta", ""),
        req=req,
        values={"data_conclusao": form.get("data_conclusao", "")},
        version=form.get("versao"),
    )
    if error is not None:
        return _form(session, context, template=COMPLETE_TEMPLATE, state=state, error=error)
    return _saved(req, session, context, state=state, notice=COMPLETED_NOTICE)


@bp.route(route="central-acoes/acoes/{acao_id}/historico", methods=["GET"])
@fragment_route(access=READ, on_error=_modal_error)
def replan_history_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The justifications of the replans of one action, the most recent first."""
    action_id = _action_id(req)
    today = calendario.today()
    action = service.find_action(
        session, user=context.user, action_id=action_id, reference_date=today
    )
    if action is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    lines = service.replan_history(session, user=context.user, action_id=action_id)
    return AlpineAjaxResponse(
        template_name=HISTORY_TEMPLATE,
        context={
            "acao": action,
            "linhas": lines,
            "formatar_data": _format_date,
        },
        request=req,
        target_id=MODAL_TARGET,
    )


# ── Drawing ──────────────────────────────────────────────────────────────────────────────────


def _screen(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    query: Query,
    notice: str | None = None,
) -> func.HttpResponse:
    """The screen fragment for the filters and the view, with an optional toast."""
    listing = service.list_actions(
        session,
        user=context.user,
        scope=context.scope,
        filters=query.filters,
        reference_date=calendario.today(),
    )
    shown = replace(query.filters, page=listing.page)
    return AlpineAjaxResponse(
        template_name=LIST_TEMPLATE,
        context=_screen_context(listing, shown, query.view, context),
        request=req,
        target_id=CONTENT_TARGET,
        toast=notice,
    )


def _screen_context(
    listing: service.ActionListing, filters: ActionFilters, view: str, context: RequestContext
) -> dict[str, object]:
    query = presentation.query_string(filters, view)
    return {
        "listagem": listing,
        "filtros": filters,
        "visao": view,
        "kpis": _kpi_cards(listing, filters, view),
        "chips": _chips(listing, filters, view),
        "colunas_do_quadro": _board(listing),
        "links_de_visao": {
            "lista": presentation.address(filters, validation.LIST_VIEW),
            "kanban": presentation.address(filters, validation.KANBAN_VIEW),
        },
        "link_anterior": _page_link(filters, view, filters.page - 1, listing.page_count),
        "link_proximo": _page_link(filters, view, filters.page + 1, listing.page_count),
        "link_limpar": presentation.address(presentation.cleared(), view),
        "tem_filtro_extra": presentation.has_extra_filters(filters),
        "url_excel": presentation.address(
            replace(filters, page=1), path=f"{presentation.ROUTE}/excel"
        ),
        "url_pdf": presentation.address(
            replace(filters, page=1), path=f"{presentation.ROUTE}/imprimivel"
        ),
        "consulta": query,
        "parametro_consulta": urlencode({"consulta": query}),
        "origens": ORIGINS,
        "opcoes_de_status": _status_options(),
        "portfolio": context.scope.is_portfolio,
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "etiqueta_de_status": STATUS_PILLS,
        "formatar_data": _format_date,
        "pagina_inicial": (filters.page - 1) * validation.PAGE_SIZE + 1,
        "pagina_final": min(filters.page * validation.PAGE_SIZE, listing.total),
    }


def _status_options() -> list[tuple[str, str]]:
    return [(item.value, calculations.STATUS_FILTER_LABELS[item]) for item in StatusFilter]


def _kpi_cards(listing: service.ActionListing, filters: ActionFilters, view: str) -> list[KpiCard]:
    counts = listing.counts
    share = listing.overdue_share

    def link(status: StatusFilter) -> str:
        # Clicking the KPI that is already on goes back to the default filter, as in the prototype.
        target = StatusFilter.OPEN if filters.status is status else status
        return presentation.address(presentation.with_status(filters, target), view)

    return [
        KpiCard(
            status=StatusFilter.ON_TIME,
            label="Em dia",
            icon="clock",
            tone="info",
            value=counts.on_time,
            reference_label="Esperado",
            reference_value=str(counts.open),
            footer="prazo vigente ainda não venceu",
            url=link(StatusFilter.ON_TIME),
            active=filters.status is StatusFilter.ON_TIME,
        ),
        KpiCard(
            status=StatusFilter.OVERDUE,
            label="Atrasadas",
            icon="warning",
            tone="erro",
            value=counts.overdue,
            reference_label="Meta",
            reference_value="0",
            footer="" if share is None else f"{share}% das abertas",
            url=link(StatusFilter.OVERDUE),
            active=filters.status is StatusFilter.OVERDUE,
        ),
        KpiCard(
            status=StatusFilter.COMPLETED,
            label="Concluídas",
            icon="checkCircle",
            tone="ok",
            value=counts.completed,
            reference_label="Previsto",
            reference_value=str(listing.due_by_reference),
            footer="com data de conclusão",
            url=link(StatusFilter.COMPLETED),
            active=filters.status is StatusFilter.COMPLETED,
        ),
        KpiCard(
            status=StatusFilter.ALL,
            label="Total de ações",
            icon="taskList",
            tone="neutro",
            value=counts.total,
            reference_label="Referência",
            reference_value=str(listing.universe),
            footer=f"{counts.open} em andamento",
            url=link(StatusFilter.ALL),
            active=filters.status is StatusFilter.ALL,
        ),
    ]


def _chips(listing: service.ActionListing, filters: ActionFilters, view: str) -> list[ChipLink]:
    chips = presentation.active_chips(filters, listing.responsibles)
    return [
        ChipLink(
            text=chip.text,
            removable=chip.removable,
            url=presentation.address(presentation.without(filters, chip.field), view),
        )
        for chip in chips
    ]


def _board(listing: service.ActionListing) -> list[BoardColumn]:
    return [
        BoardColumn(title=title, tone=tone, rows=listing.board_column(status))
        for status, title, tone in BOARD_COLUMNS
    ]


def _page_link(filters: ActionFilters, view: str, page: int, page_count: int) -> str:
    if page < 1 or page > page_count:
        return ""
    return presentation.address(presentation.with_page(filters, page), view)


def _format_date(value: date | None) -> str:
    """``25/09/2026``; the dash when there is no date."""
    return "—" if value is None else format_value(ValueKind.DATE, value)


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """The document of the screen for the filters of the request; the only place with the clock."""
    filters = validation.parse_filters(req.params)
    today = calendario.today()
    listing = service.list_actions(
        session, user=context.user, scope=context.scope, filters=filters, reference_date=today
    )
    return export.build_document(
        listing=listing,
        filters=filters,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


# ── The forms ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _FormState:
    """What a form of the modal remembers: the action, the screen it came from and what was typed."""

    action_id: int
    query: str
    req: func.HttpRequest
    values: Mapping[str, str] | None = None
    version: int | str | None = None


def _form(
    session: Session,
    context: RequestContext,
    *,
    template: str,
    state: _FormState,
    error: DomainError | None = None,
) -> func.HttpResponse:
    """The form of the modal, empty or filled in with the messages of a refusal."""
    today = calendario.today()
    action = service.find_action(
        session, user=context.user, action_id=state.action_id, reference_date=today
    )
    if action is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    # A 409 means the screen was stale: the form carries the current version, so sending it
    # again is the person's informed choice. A 422 keeps the version the form was opened with.
    stale = isinstance(error, VersionConflictError)
    version = action.version if stale or state.version is None else state.version
    return AlpineAjaxResponse(
        template_name=template,
        context={
            "acao": action,
            "versao": version,
            "consulta": state.query,
            "valores": dict(state.values or {}),
            "erros": _field_errors(error),
            "referencia": today.isoformat(),
            "formatar_data": _format_date,
        },
        request=state.req,
        target_id=MODAL_TARGET,
        status_code=200 if error is None else _error_status(error),
    )


def _saved(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    state: _FormState,
    notice: str,
) -> func.HttpResponse:
    """After a save: the refreshed screen, with the filters the person had, and the toast."""
    query = Query.of(dict(parse_qsl(state.query)))
    return _screen(req, session, context, query=query, notice=notice)


def _attempt(session: Session, work: Callable[[], object]) -> DomainError | None:
    """Run a write inside a savepoint: a refusal leaves nothing behind, not even a half write.

    A reaction of the origin may refuse after the action changed; the savepoint undoes both, so
    the form can answer with the message while the transaction of the request stays clean.
    """
    try:
        with session.begin_nested():
            work()
    except (InvalidDataError, VersionConflictError) as error:
        return error
    return None


def _field_errors(error: DomainError | None) -> dict[str, str]:
    if error is None:
        return {}
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return dict(error.detail)
    return {"geral": str(error)}


def _action_id(req: func.HttpRequest) -> int:
    parsed = validation.parse_id(req.route_params.get("acao_id"))
    if parsed is None:
        raise InvalidDataError(INVALID_ACTION_MESSAGE)
    return parsed
