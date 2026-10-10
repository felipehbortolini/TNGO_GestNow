"""Routes of the Análises de risco (APR/HAZOP) screen (D14, ISSUE-074).

Prefix ``/api/hse/analises-risco``. The screen is one fragment (``analises-risco-conteudo``): the
four indicators, the filters and the list, with a "Ver estudo" action on each line. Filters, page
and search are plain GETs of the same route with the state in the query string. The ficha, the
new study form and the closing form open in the modal (``analises-risco-modal-corpo``): a GET
draws them, a POST saves and answers the refreshed list with a hidden marker that reopens the
ficha; a refusal (422, 409, 403) answers the form again, filled in, in the modal.

* ``GET  analises-risco`` the screen (filters and page by query);
* ``GET  analises-risco/excel`` and ``analises-risco/imprimivel`` the two exports;
* ``GET  analises-risco/{codigo}/ficha`` the ficha (recommendations with the action status);
* ``GET/POST analises-risco/nova`` the new study with its recommendations;
* ``GET/POST analises-risco/{codigo}/recomendacoes/{ordem}/fechar`` the closing of a
  recommendation (the manual closing also concludes its action in the Central, D9);
* ``POST analises-risco/{codigo}/recomendacoes/{ordem}/acao`` the recommendation action in the
  Central (origin ``HSE``).

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import DomainError, InvalidDataError
from src.core.excel import excel_response
from src.core.export_document import ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import export, forms, models, service, validation
from src.modulos.hse.routes import _attempt, _field_errors, _helpers, _status

bp = func.Blueprint()

MODULE = "hse"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

CONTENT_TARGET = "analises-risco-conteudo"
MODAL_TARGET = "analises-risco-modal-corpo"
ROUTE = "/api/hse/analises-risco"
NOT_FOUND = "Estudo não encontrado."
RECOMMENDATION_NOT_FOUND = "Recomendação não encontrada."
PAGE_SIZE = 20

SCREEN_TEMPLATE = "hse/analises_risco.html"
NEW_TEMPLATE = "hse/analise_risco_nova.html"
SHEET_TEMPLATE = "hse/analise_risco_ficha.html"
CLOSE_TEMPLATE = "hse/analise_risco_fechar.html"

NEW_FIELDS = frozenset({"tipo", "area", "titulo", "data", "participantes", "recomendacoes"})
CLOSE_FIELDS = frozenset({"data", "evidencia"})


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


def _query(form: Mapping[str, str]) -> dict[str, str]:
    """O estado da tela que o formulário carregou de volta (``busca=...&pagina=2``)."""
    return dict(parse_qsl(form.get("consulta", "")))


@dataclass(frozen=True)
class _Page:
    """A slice of the list: the rows of the page and where the page sits."""

    rows: tuple[Any, ...]
    page: int
    page_count: int
    total: int


def _paginate(rows: Sequence[Any], page: int) -> _Page:
    page_count = max(1, -(-len(rows) // PAGE_SIZE))
    current = min(max(page, 1), page_count)
    start = (current - 1) * PAGE_SIZE
    return _Page(
        rows=tuple(rows[start : start + PAGE_SIZE]),
        page=current,
        page_count=page_count,
        total=len(rows),
    )


def _state_of(filters: validation.AnalysisFilters) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "busca": filters.search,
            "tipo": filters.kind,
            "abertas": "1" if filters.open_only else "",
        }.items()
        if value
    }


def _page_link(state: Mapping[str, str], page: int, page_count: int) -> str:
    if page < 1 or page > page_count:
        return ""
    return f"{ROUTE}?{urlencode({**state, 'pagina': page})}"


def _analysis_kpis(screen: service.AnalysisScreen) -> list[dict[str, str]]:
    summary = screen.summary
    emitted = summary.open + summary.closed

    def number(value: int) -> str:
        return format_value(ValueKind.INTEGER, value)

    def share(value: Decimal | None) -> str:
        return "·" if value is None else format_value(ValueKind.PERCENT, value, 1)

    return [
        {
            "rotulo": "Estudos registrados",
            "valor": number(len(screen.rows)),
            "icone": "table",
            "tom": "primary",
            "referencia": f"Referência: de {number(screen.universe)} registrados",
            "rodape": "Pelo filtro em tela",
        },
        {
            "rotulo": "Recomendações abertas",
            "valor": number(summary.open),
            "icone": "clock",
            "tom": "warn" if summary.open else "ok",
            "referencia": "Esperado: 0",
            "rodape": "Não fechadas",
        },
        {
            "rotulo": "Recomendações atrasadas",
            "valor": number(summary.overdue),
            "icone": "warning",
            "tom": "erro" if summary.overdue else "ok",
            "referencia": "Esperado: 0",
            "rodape": "Abertas com o prazo vencido",
        },
        {
            "rotulo": "Recomendações fechadas",
            "valor": share(summary.closed_pct),
            "icone": "checkCircle",
            "tom": "info",
            "referencia": "Esperado: 100%",
            "rodape": f"{number(summary.closed)} de {number(emitted)} emitidas",
        },
    ]


def _screen_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: validation.AnalysisFilters,
    page: int,
    notice: str | None = None,
    abrir_ficha: str | None = None,
) -> func.HttpResponse:
    today = calendario.today()
    screen = service.analyses_screen(
        session, scope=context.scope, filters=filters, reference_date=today
    )
    shown = _paginate(screen.rows, page)
    state = _state_of(filters)
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={
            "kpis": _analysis_kpis(screen),
            "linhas": shown.rows,
            "total": shown.total,
            "pagina": shown.page,
            "pagina_total": shown.page_count,
            "link_anterior": _page_link(state, shown.page - 1, shown.page_count),
            "link_proximo": _page_link(state, shown.page + 1, shown.page_count),
            "consulta": urlencode({**state, "pagina": shown.page}),
            "url_excel": f"{ROUTE}/excel?{urlencode(state)}",
            "url_pdf": f"{ROUTE}/imprimivel?{urlencode(state)}",
            "filtros": filters,
            "tem_filtro": bool(state),
            "tipos": models.ANALYSIS_TYPES,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "portfolio": context.scope.is_portfolio,
            "abrir_ficha": abrir_ficha,
            **_helpers(),
        },
        request=req,
        target_id=CONTENT_TARGET,
        toast=notice,
    )


def _document(
    session: Session, context: RequestContext, filters: validation.AnalysisFilters
) -> Any:
    today = calendario.today()
    screen = service.analyses_screen(
        session, scope=context.scope, filters=filters, reference_date=today
    )
    return export.analyses_document(
        screen,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


@bp.route(route="hse/analises-risco", methods=["GET"])
@fragment_route(access=READ)
def risk_study_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A tela: indicadores, filtros, lista e páginas, para os filtros da query."""
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_analysis_filters(req.params),
        page=validation.parse_page(req.params),
    )


@bp.route(route="hse/analises-risco/excel", methods=["GET"])
@file_route(access=READ)
def risk_study_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do que a tela lista, com os indicadores."""
    return excel_response(
        _document(session, context, validation.parse_analysis_filters(req.params))
    )


@bp.route(route="hse/analises-risco/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def risk_study_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do mesmo documento: o que o botão PDF monta e imprime."""
    return printable_response(
        _document(session, context, validation.parse_analysis_filters(req.params)), req
    )


# ── Ficha ────────────────────────────────────────────────────────────────────────────────────


def _sheet_or_refuse(session: Session, context: RequestContext, code: str) -> service.AnalysisSheet:
    sheet = service.analysis_sheet(
        session,
        user=context.user,
        code=code,
        reference_date=calendario.today(),
        project_id=context.scope.project_id,
    )
    if sheet is None:
        raise InvalidDataError(NOT_FOUND)
    return sheet


def _recommendation_of(sheet: service.AnalysisSheet, position: int) -> service.RecommendationRow:
    found = next((line for line in sheet.line.recommendations if line.position == position), None)
    if found is None:
        raise InvalidDataError(RECOMMENDATION_NOT_FOUND)
    return found


@bp.route(route="hse/analises-risco/{codigo}/ficha", methods=["GET"])
@fragment_route(access=READ)
def risk_study_sheet_fragment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A ficha do estudo: participantes e recomendações, com o status da ação de cada uma."""
    code = (req.route_params.get("codigo") or "").strip()
    sheet = _sheet_or_refuse(session, context, code)
    return AlpineAjaxResponse(
        template_name=SHEET_TEMPLATE,
        context={
            "ficha": sheet,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "consulta": urlencode(_query(req.form) or dict(req.params)),
            **_helpers(),
        },
        request=req,
        target_id=MODAL_TARGET,
    )


# ── Nova análise ─────────────────────────────────────────────────────────────────────────────


def _selected_participants(valores: Mapping[str, str]) -> set[str]:
    getlist = getattr(valores, "getlist", None)
    if getlist is not None:
        return {str(item) for item in getlist("participantes")}
    raw = valores.get("participantes")
    return {str(raw)} if raw else set()


def _recommendation_rows(
    form: Mapping[str, str],
) -> tuple[validation.AnalysisRecommendationInput, ...]:
    rows = forms.recommendation_rows(form)
    return rows or (validation.AnalysisRecommendationInput("", None, None),)


def _new_context(
    session: Session,
    *,
    valores: Mapping[str, str],
    erros: Mapping[str, str],
    consulta: str,
) -> dict[str, Any]:
    today = calendario.today()
    return {
        "valores": valores,
        "erros": erros,
        "erros_gerais": [message for name, message in erros.items() if name not in NEW_FIELDS],
        "consulta": consulta,
        "referencia": today.isoformat(),
        "tipos": models.ANALYSIS_TYPES,
        "pessoas": service.person_options(session),
        "participantes": _selected_participants(valores),
        "recomendacoes": _recommendation_rows(valores),
        "recomendacao_vazia": validation.AnalysisRecommendationInput("", None, None),
        **_helpers(),
    }


@dataclass(frozen=True)
class _NewForm:
    """O que o formulário da nova análise lembra: o que foi digitado e a recusa."""

    valores: Mapping[str, str]
    erros: Mapping[str, str]
    consulta: str


def _new_form(
    req: func.HttpRequest,
    session: Session,
    state: _NewForm,
    *,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=NEW_TEMPLATE,
        context=_new_context(
            session, valores=state.valores, erros=state.erros, consulta=state.consulta
        ),
        request=req,
        target_id=MODAL_TARGET,
        status_code=status_code,
    )


@bp.route(route="hse/analises-risco/nova", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def risk_study_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário vazio, no projeto do escopo."""
    context.scope.require_project()
    return _new_form(req, session, _NewForm({}, {}, req.params.get("consulta", "")))


@bp.route(route="hse/analises-risco/nova", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def risk_study_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o estudo com os participantes e as recomendações na mesma transação."""
    form = req.form
    data = forms.parse_analysis(form, project_id=context.scope.require_project())
    result, error = _attempt(
        session,
        lambda: service.save_analysis(
            session, user=context.user, data=data, reference_date=calendario.today()
        ),
    )
    if error is not None or result is None:
        return _new_form(
            req,
            session,
            _NewForm(form, _field_errors(error), form.get("consulta", "")),
            status_code=_status(error) if error is not None else 422,
        )
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_analysis_filters(_query(form)),
        page=validation.parse_page(_query(form)),
        notice=f"Estudo {result.code} registrado.",
        abrir_ficha=result.code,
    )


# ── Fechamento da recomendação ───────────────────────────────────────────────────────────────


def _close_context(
    sheet: service.AnalysisSheet,
    *,
    recomendacao: service.RecommendationRow,
    valores: Mapping[str, str],
    erros: Mapping[str, str],
    consulta: str,
) -> dict[str, Any]:
    return {
        "linha": sheet.line,
        "recomendacao": recomendacao,
        "valores": valores,
        "erros": erros,
        "erros_gerais": [message for name, message in erros.items() if name not in CLOSE_FIELDS],
        "referencia": calendario.today().isoformat(),
        "consulta": consulta,
        **_helpers(),
    }


@bp.route(route="hse/analises-risco/{codigo}/recomendacoes/{ordem}/fechar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def risk_study_close_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do fechamento de uma recomendação."""
    code = (req.route_params.get("codigo") or "").strip()
    ordem = validation.parse_id(req.route_params.get("ordem"))
    if ordem is None:
        raise InvalidDataError(RECOMMENDATION_NOT_FOUND)
    sheet = _sheet_or_refuse(session, context, code)
    return AlpineAjaxResponse(
        template_name=CLOSE_TEMPLATE,
        context=_close_context(
            sheet,
            recomendacao=_recommendation_of(sheet, ordem),
            valores={},
            erros={},
            consulta=req.params.get("consulta", ""),
        ),
        request=req,
        target_id=MODAL_TARGET,
    )


@bp.route(route="hse/analises-risco/{codigo}/recomendacoes/{ordem}/fechar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def risk_study_close_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Fecha a recomendação e conclui a ação vinculada, na mesma transação (D9)."""
    form = req.form
    code = (req.route_params.get("codigo") or "").strip()
    ordem = validation.parse_id(req.route_params.get("ordem"))
    if ordem is None:
        raise InvalidDataError(RECOMMENDATION_NOT_FOUND)
    data = forms.parse_recommendation_closure(form)
    _, error = _attempt(
        session,
        lambda: service.close_recommendation(
            session,
            user=context.user,
            code=code,
            position=ordem,
            data=data,
            reference_date=calendario.today(),
            project_id=context.scope.project_id,
        ),
    )
    if error is not None:
        sheet = _sheet_or_refuse(session, context, code)
        return AlpineAjaxResponse(
            template_name=CLOSE_TEMPLATE,
            context=_close_context(
                sheet,
                recomendacao=_recommendation_of(sheet, ordem),
                valores=form,
                erros=_field_errors(error),
                consulta=form.get("consulta", ""),
            ),
            request=req,
            target_id=MODAL_TARGET,
            status_code=_status(error),
        )
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_analysis_filters(_query(form)),
        page=validation.parse_page(_query(form)),
        notice="Recomendação fechada.",
        abrir_ficha=code,
    )


# ── Ação na Central ──────────────────────────────────────────────────────────────────────────


@bp.route(route="hse/analises-risco/{codigo}/recomendacoes/{ordem}/acao", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def risk_study_action_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cria a ação da recomendação na Central (origem HSE) na mesma transação."""
    form = req.form
    code = (req.route_params.get("codigo") or "").strip()
    ordem = validation.parse_id(req.route_params.get("ordem"))
    if ordem is None:
        raise InvalidDataError(RECOMMENDATION_NOT_FOUND)
    _, error = _attempt(
        session,
        lambda: service.create_recommendation_action(
            session,
            user=context.user,
            code=code,
            position=ordem,
            reference_date=calendario.today(),
            project_id=context.scope.project_id,
        ),
    )
    if error is not None:
        raise error
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_analysis_filters(_query(form)),
        page=validation.parse_page(_query(form)),
        notice="Ação criada na Central.",
        abrir_ficha=code,
    )
