"""Routes of the screen Análises de risco: APR/JSA and HAZOP studies and their recommendations (D14, ISSUE-074).

Prefix ``/api/hse/analises-de-risco``. The screen is one fragment (``analises-conteudo``) with two
blocks the filter form replaces on its own (``analises-kpis`` and ``analises-tabela``). A study opens
in a modal (``hse-modal-corpo``): a GET draws it, and each gesture (close a recommendation, create
its action) answers the body of the study again; a refusal (422, 409, 403) answers the form again,
filled in, in the modal.

* ``GET  analises-de-risco?busca=&tipo=&situacao=&pagina=`` the screen;
* ``GET  analises-de-risco/excel`` and ``analises-de-risco/imprimivel`` its two exports;
* ``GET/POST analises-de-risco/novo`` the form of a new study of the project in scope;
* ``GET  analises-de-risco/{codigo}`` the study with its recommendations and actions;
* ``GET/POST analises-de-risco/{codigo}/recomendacoes/{ordem}/fechar`` close a recommendation;
* ``POST analises-de-risco/{codigo}/recomendacoes/{ordem}/acao`` create its action in the Central.

The rules are in ``analysis_service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

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
from src.core.export_document import ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import analysis_export, analysis_service, service, validation
from src.modulos.hse.analysis_service import AnalysisFilter, AnalysisListing, RecommendationRef
from src.modulos.hse.validation import (
    AnalysisInput,
    ClosingRecommendationInput,
    RecommendationInput,
)

bp = func.Blueprint()

MODULE = "hse"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

ROUTE = "/api/hse/analises-de-risco"
TARGET = "analises-conteudo"
FILTERED_BLOCKS = ("analises-kpis", "analises-tabela")
MODAL_TARGET = "hse-modal-corpo"
TARGET_HEADER = "X-Alpine-Target"

SCREEN_TEMPLATE = "hse/analises_risco.html"
PARTS_TEMPLATE = "hse/analises_risco_partes.html"
NEW_TEMPLATE = "hse/analise_nova.html"
VIEW_TEMPLATE = "hse/analise_ver.html"
CLOSE_TEMPLATE = "hse/analise_fechar.html"

KIND_OPTIONS = (("APR", "APR / JSA"), ("HAZOP", "HAZOP"))
RECOMMENDATION_SLOTS = 10
INITIAL_ROWS = 3
NOT_FOUND = "Estudo não encontrado."
STATUS_OF = {AccessDeniedError: 403, VersionConflictError: 409}


def _status(error: DomainError) -> int:
    return STATUS_OF.get(type(error), 422)


def _helpers() -> dict[str, Any]:
    """What the templates format with: numbers and dates in the notation of Brazil."""
    return {
        "numero": lambda value: format_value(ValueKind.DECIMAL, Decimal(value), 0),
        "data": lambda value: format_value(ValueKind.DATE, value),
    }


def _modal_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A refusal inside the modal: the message in the modal body, where the person is looking."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=MODAL_TARGET,
        status_code=_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


def _attempt(session: Session, work: Callable[[], Any]) -> tuple[Any, DomainError | None]:
    """Run a write in a savepoint: a refusal leaves nothing behind, not even a half write."""
    try:
        with session.begin_nested():
            return work(), None
    except (InvalidDataError, VersionConflictError) as error:
        return None, error


def _errors_of(error: DomainError | None) -> dict[str, str]:
    if error is None:
        return {}
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return {str(name): str(message) for name, message in error.detail.items()}
    return {"geral": str(error)}


def _general_messages(errors: Mapping[str, str], shown: tuple[str, ...]) -> list[str]:
    """The messages with no field on the form to carry them (a stale version, the project)."""
    return [message for name, message in errors.items() if name not in shown]


def _position(req: func.HttpRequest) -> int:
    parsed = validation.parse_id(req.route_params.get("ordem"))
    if parsed is None:
        raise InvalidDataError({"geral": analysis_service.RECOMMENDATION_NOT_FOUND})
    return parsed


def _code(req: func.HttpRequest) -> str:
    return (req.route_params.get("codigo") or "").strip()


# ── The screen ───────────────────────────────────────────────────────────────────────────────


def _filters_of(params: Mapping[str, str]) -> AnalysisFilter:
    kind = (params.get("tipo") or "").strip()
    return AnalysisFilter(
        kind=kind if kind in validation.ANALYSIS_KINDS else "",
        search=(params.get("busca") or "").strip(),
        only_open=params.get("situacao") == "abertas",
    )


def _query_of(filters: AnalysisFilter) -> dict[str, str]:
    pairs = {"busca": filters.search, "tipo": filters.kind}
    if filters.only_open:
        pairs["situacao"] = "abertas"
    return {name: value for name, value in pairs.items() if value}


def _page_link(query: Mapping[str, str], page: int, page_count: int) -> str:
    if page < 1 or page > page_count:
        return ""
    return f"{ROUTE}?{urlencode({**query, 'pagina': page})}"


def _kpis(listing: AnalysisListing) -> list[dict[str, str]]:
    counts = listing.counts
    rate = listing.closed_rate
    return [
        {
            "rotulo": "Estudos registrados",
            "valor": format_value(ValueKind.INTEGER, len(listing.rows)),
            "icone": "file",
            "tom": "info",
            "referencia": f"Referência: de {format_value(ValueKind.INTEGER, listing.universe)} registrados",
        },
        {
            "rotulo": "Recomendações abertas",
            "valor": format_value(ValueKind.INTEGER, counts.open),
            "icone": "clock",
            "tom": "warn" if counts.open else "ok",
            "referencia": "Esperado: 0",
        },
        {
            "rotulo": "Recomendações atrasadas",
            "valor": format_value(ValueKind.INTEGER, counts.overdue),
            "icone": "warning",
            "tom": "erro" if counts.overdue else "ok",
            "referencia": "Esperado: 0",
        },
        {
            "rotulo": "Recomendações fechadas",
            "valor": "·" if rate is None else format_value(ValueKind.PERCENT, rate, 1),
            "icone": "checkCircle",
            "tom": "info",
            "referencia": "Esperado: 100%",
        },
    ]


def _is_partial(req: func.HttpRequest) -> bool:
    targets = (req.headers.get(TARGET_HEADER) or "").split()
    return any(block in FILTERED_BLOCKS for block in targets)


def _screen_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    params: Mapping[str, str],
    notice: str | None = None,
) -> func.HttpResponse:
    filters = _filters_of(params)
    listing = _listing(session, context, filters)
    shown = service.paginate(listing.rows, validation.parse_page(params))
    query = _query_of(filters)
    partial = _is_partial(req)
    exact = [row for row in listing.rows if filters.search and row.code == filters.search]
    return AlpineAjaxResponse(
        template_name=PARTS_TEMPLATE if partial else SCREEN_TEMPLATE,
        context={
            "kpis": _kpis(listing),
            "filtros": filters,
            "tipos": KIND_OPTIONS,
            "linhas": shown.rows,
            "total": len(listing.rows),
            "universo": listing.universe,
            "pagina": shown.page,
            "pagina_total": shown.page_count,
            "link_anterior": _page_link(query, shown.page - 1, shown.page_count),
            "link_proximo": _page_link(query, shown.page + 1, shown.page_count),
            "url_excel": f"{ROUTE}/excel?{urlencode(query)}",
            "url_pdf": f"{ROUTE}/imprimivel?{urlencode(query)}",
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "portfolio": context.scope.is_portfolio,
            "auto_abrir": exact[0] if exact and not partial else None,
            **_helpers(),
        },
        request=req,
        target_id=TARGET,
        toast=notice,
    )


def _listing(session: Session, context: RequestContext, filters: AnalysisFilter) -> AnalysisListing:
    """The studies of the scope that pass the filter, as of today."""
    return analysis_service.list_analyses(
        session, scope=context.scope, filters=filters, reference_date=calendario.today()
    )


@bp.route(route="hse/analises-de-risco", methods=["GET"])
@fragment_route(access=READ)
def analysis_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The screen: indicators, filter and the table of studies for the page in the query."""
    return _screen_response(req, session, context, params=dict(req.params))


def _document(session: Session, context: RequestContext, params: Mapping[str, str]) -> Any:
    listing = _listing(session, context, _filters_of(params))
    return analysis_export.analysis_document(
        listing,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
    )


@bp.route(route="hse/analises-de-risco/excel", methods=["GET"])
@file_route(access=READ)
def analysis_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the screen: the indicators and the studies of the list in view."""
    return excel_response(_document(session, context, dict(req.params)))


@bp.route(route="hse/analises-de-risco/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def analysis_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_document(session, context, dict(req.params)), req)


# ── A new study ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _NewForm:
    """What the new-study form remembers: what was typed and the refusal that came with it."""

    values: Mapping[str, Any] = field(default_factory=dict)
    error: DomainError | None = None


def _typed_values(form: Any) -> dict[str, Any]:
    values: dict[str, Any] = dict(form.items())
    values["participantes"] = list(form.getlist("participantes"))
    return values


def _recommendation_inputs(form: Mapping[str, str]) -> tuple[RecommendationInput, ...]:
    """The recommendation rows that have a description, in order; blank rows are ignored."""
    rows = []
    for slot in range(1, RECOMMENDATION_SLOTS + 1):
        description = (form.get(f"rec_descricao_{slot}") or "").strip()
        if description:
            rows.append(
                RecommendationInput(
                    description=description,
                    responsible_id=validation.parse_id(form.get(f"rec_responsavel_{slot}")),
                    due_date=validation.parse_date(form.get(f"rec_prazo_{slot}")),
                )
            )
    return tuple(rows)


def _parse_analysis(form: Any, *, project_id: int) -> AnalysisInput:
    return AnalysisInput(
        project_id=project_id,
        kind=(form.get("tipo") or "").strip(),
        area=(form.get("area") or "").strip(),
        title=(form.get("titulo") or "").strip(),
        studied_on=validation.parse_date(form.get("data")),
        participant_ids=tuple(
            item
            for item in (validation.parse_id(raw) for raw in form.getlist("participantes"))
            if item is not None
        ),
        recommendations=_recommendation_inputs(form),
    )


def _new_form(req: func.HttpRequest, session: Session, state: _NewForm) -> func.HttpResponse:
    errors = _errors_of(state.error)
    shown = (
        "tipo",
        "data",
        "area",
        "titulo",
        "participantes",
        "recomendacoes",
    )
    typed_rows = max(
        (
            slot
            for slot in range(1, RECOMMENDATION_SLOTS + 1)
            if state.values.get(f"rec_descricao_{slot}")
        ),
        default=0,
    )
    rows = [item for item in errors if item.startswith("recomendacao_")]
    return AlpineAjaxResponse(
        template_name=NEW_TEMPLATE,
        context={
            "acao": f"{ROUTE}/novo",
            "alvo": TARGET,
            "valores": state.values,
            "erros": errors,
            "erros_gerais": _general_messages(errors, (*shown, *rows)),
            "tipos": KIND_OPTIONS,
            "pessoas": service.person_options(session),
            "linhas": RECOMMENDATION_SLOTS,
            "visiveis": max(INITIAL_ROWS, typed_rows),
            "hoje": calendario.today().isoformat(),
            "rotulo_salvar": "Registrar estudo",
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=200 if state.error is None else _status(state.error),
    )


@bp.route(route="hse/analises-de-risco/novo", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def analysis_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The empty form of a study of the project in scope."""
    context.scope.require_project()
    return _new_form(req, session, _NewForm())


@bp.route(route="hse/analises-de-risco/novo", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def analysis_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the study and answer the screen with the new study in the table."""
    project_id = context.scope.require_project()
    form = req.form
    saved, error = _attempt(
        session,
        lambda: analysis_service.save_analysis(
            session,
            user=context.user,
            data=_parse_analysis(form, project_id=project_id),
            reference_date=calendario.today(),
        ),
    )
    if error is not None:
        return _new_form(req, session, _NewForm(_typed_values(form), error))
    return _screen_response(
        req, session, context, params={}, notice=f"Estudo {saved.code} registrado."
    )


# ── One study and its recommendations ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Answer:
    """What a gesture on the study says back: the toast, the refusal messages and the status."""

    notice: str | None = None
    errors: tuple[str, ...] = ()
    status_code: int = 200


def _study_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    code: str,
    answer: _Answer | None = None,
) -> func.HttpResponse:
    study = analysis_service.find_analysis(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if study is None:
        raise InvalidDataError({"geral": NOT_FOUND})
    answer = answer or _Answer()
    return AlpineAjaxResponse(
        template_name=VIEW_TEMPLATE,
        context={
            "estudo": study,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "erros_gerais": list(answer.errors),
            **_helpers(),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=answer.status_code,
        toast=answer.notice,
    )


@bp.route(route="hse/analises-de-risco/{codigo}", methods=["GET"])
@fragment_route(access=READ, on_error=_modal_error)
def analysis_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The study with its recommendations and the action of the Central that each one has."""
    return _study_response(req, session, context, code=_code(req))


@dataclass(frozen=True)
class _ClosingState:
    """What the closing form remembers: the recommendation, what was typed and the refusal."""

    position: int
    values: Mapping[str, str] = field(default_factory=dict)
    error: DomainError | None = None


def _closing_form(
    req: func.HttpRequest, session: Session, context: RequestContext, state: _ClosingState
) -> func.HttpResponse:
    study = analysis_service.find_analysis(
        session, user=context.user, code=_code(req), reference_date=calendario.today()
    )
    found = [
        item for item in (study.recommendations if study else ()) if item.position == state.position
    ]
    if study is None or not found:
        raise InvalidDataError({"geral": NOT_FOUND})
    errors = _errors_of(state.error)
    return AlpineAjaxResponse(
        template_name=CLOSE_TEMPLATE,
        context={
            "estudo": study,
            "recomendacao": found[0],
            "valores": state.values,
            "erros": errors,
            "erros_gerais": _general_messages(errors, ("data", "evidencia")),
            "versao": found[0].version,
            "hoje": calendario.today().isoformat(),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=200 if state.error is None else _status(state.error),
    )


@bp.route(route="hse/analises-de-risco/{codigo}/recomendacoes/{ordem}/fechar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def recommendation_close_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form that closes a recommendation: the completion date and the evidence."""
    return _closing_form(req, session, context, _ClosingState(position=_position(req)))


@bp.route(route="hse/analises-de-risco/{codigo}/recomendacoes/{ordem}/fechar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def recommendation_close_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Close the recommendation (and complete its action) and answer the study again."""
    code, position, form = _code(req), _position(req), req.form
    _, error = _attempt(
        session,
        lambda: analysis_service.close_recommendation(
            session,
            user=context.user,
            target=RecommendationRef(code=code, position=position),
            data=ClosingRecommendationInput(
                closed_on=validation.parse_date(form.get("data")),
                evidence=(form.get("evidencia") or "").strip(),
                version=form.get("versao"),
            ),
            reference_date=calendario.today(),
        ),
    )
    if error is not None:
        return _closing_form(
            req,
            session,
            context,
            _ClosingState(position=position, values=dict(form.items()), error=error),
        )
    return _study_response(
        req, session, context, code=code, answer=_Answer(notice="Recomendação fechada.")
    )


@bp.route(route="hse/analises-de-risco/{codigo}/recomendacoes/{ordem}/acao", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def recommendation_action(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the action of the Central for the recommendation, with the link back to the study."""
    code, position = _code(req), _position(req)
    _, error = _attempt(
        session,
        lambda: analysis_service.create_recommendation_action(
            session,
            user=context.user,
            code=code,
            position=position,
            reference_date=calendario.today(),
        ),
    )
    if error is not None:
        refused = _Answer(errors=tuple(_errors_of(error).values()), status_code=_status(error))
        return _study_response(req, session, context, code=code, answer=refused)
    return _study_response(
        req, session, context, code=code, answer=_Answer(notice="Ação criada na Central.")
    )
