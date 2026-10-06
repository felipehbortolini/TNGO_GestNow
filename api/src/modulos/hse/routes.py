"""Routes of the HSE module: the screens HHT and Inspeções e observações (D14, ISSUE-072).

Prefix ``/api/hse/``. Each screen is one fragment (``hht-conteudo``, ``inspecoes-conteudo``): the
indicators, the table and, in HHT, the labour histogram. Everything that changes the view (a tab,
a page) is a plain GET of the same route with the state in the query string. A record is created
or edited in a modal (``hse-modal-corpo``): a GET draws the form, a POST saves and answers the
refreshed screen; a refusal (422, 409, 403) answers the form again, filled in, in the modal. The
spreadsheet import is the generic ``/api/importacao/{chave}`` with the keys ``hht`` and
``hse-mensal`` (see ``importers``).

* ``GET  hht`` the screen; ``hht/excel`` and ``hht/imprimivel`` its two exports;
* ``GET/POST hht/novo`` and ``hht/{hht_id}/editar``: the HHT form (month and company locked on edit);
* ``GET  histograma`` the labour histogram alone, for the Cronograma de desembolso;
* ``GET  inspecoes?aba=&pagina=`` the screen, one tab per record (mensal, inspecao, observacao, dds);
* ``GET  inspecoes/excel`` and ``inspecoes/imprimivel``: the two exports of the screen;
* ``GET/POST inspecoes/{tipo}/novo`` and ``inspecoes/{tipo}/{registro_id}/editar``: the forms.

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any
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
from src.core.export_document import ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, export, forms, importers, service, validation
from src.modulos.hse.calculations import HistogramPoint

bp = func.Blueprint()

importers.register_importers()

MODULE = "hse"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

HOURS_TARGET = "hht-conteudo"
PROACTIVE_TARGET = "inspecoes-conteudo"
MODAL_TARGET = "hse-modal-corpo"

HOURS_TEMPLATE = "hse/hht.html"
PROACTIVE_TEMPLATE = "hse/inspecoes.html"
HISTOGRAM_TEMPLATE = "hse/histograma.html"
FORM_TEMPLATE = "hse/formulario.html"

HOURS_ROUTE = "/api/hse/hht"
PROACTIVE_ROUTE = "/api/hse/inspecoes"
NOT_FOUND = "Registro não encontrado."


def _status(error: DomainError) -> int:
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


def _field_errors(error: DomainError | None) -> dict[str, str]:
    if error is None:
        return {}
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return dict(error.detail)
    return {"geral": str(error)}


def _general_messages(errors: Mapping[str, str], shown: Sequence[forms.FormField]) -> list[str]:
    """The messages with no field on the form to carry them (a stale version, the project)."""
    names = {field.name for field in shown} | {"itens"}
    return [message for name, message in errors.items() if name not in names]


def _id(req: func.HttpRequest, name: str) -> int:
    parsed = validation.parse_id(req.route_params.get(name))
    if parsed is None:
        raise InvalidDataError(NOT_FOUND)
    return parsed


def _helpers() -> dict[str, Any]:
    """What the templates format with: numbers, percentages and dates in the notation of Brazil."""
    return {
        "numero": lambda value: format_value(ValueKind.DECIMAL, Decimal(value), 0),
        "percentual": lambda value, digits=1: format_value(ValueKind.PERCENT, value, digits),
        "data": lambda value: format_value(ValueKind.DATE, value),
    }


def _page_link(base: str, state: Mapping[str, str], page: int, page_count: int) -> str:
    if page < 1 or page > page_count:
        return ""
    return f"{base}?{urlencode({**state, 'pagina': page})}"


# ── HHT ──────────────────────────────────────────────────────────────────────────────────────


@bp.route(route="hse/hht", methods=["GET"])
@fragment_route(access=READ)
def hours_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The HHT screen: indicators, the table of the page and the labour histogram."""
    return _hours_response(req, session, context, page=validation.parse_page(req.params))


@bp.route(route="hse/hht/excel", methods=["GET"])
@file_route(access=READ)
def hours_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the HHT screen: indicators, the table and the histogram."""
    del req
    return excel_response(_hours_document(session, context))


@bp.route(route="hse/hht/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def hours_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_hours_document(session, context), req)


@bp.route(route="hse/histograma", methods=["GET"])
@fragment_route(access=READ)
def labour_histogram_fragment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The labour histogram alone: the Cronograma de desembolso asks for it where it shows it."""
    points = service.labour_histogram(
        session, scope=context.scope, reference_date=calendario.today()
    )
    names = service.names_of(session)
    return AlpineAjaxResponse(
        template_name=HISTOGRAM_TEMPLATE,
        context={
            "pontos": _histogram_rows(points, names),
            "maximo": _histogram_maximum(points),
            "portfolio": context.scope.is_portfolio,
            **_helpers(),
        },
        request=req,
    )


def _hours_document(session: Session, context: RequestContext) -> Any:
    today = calendario.today()
    screen = service.hours_screen(session, scope=context.scope, reference_date=today)
    return export.hours_document(
        screen,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        names=service.names_of(session),
        today=today,
    )


def _histogram_rows(points: Sequence[HistogramPoint], names: service.Names) -> list[dict[str, Any]]:
    return [
        {
            "projeto": names.project(point.project_id),
            "mes": calculations.month_display(point.month),
            "hht_previsto": format_value(ValueKind.INTEGER, point.planned_hours),
            "hht_previsto_valor": point.planned_hours,
            "hht_registrado": format_value(ValueKind.DECIMAL, point.recorded_hours, 0),
            "efetivo_previsto": format_value(ValueKind.INTEGER, point.planned_headcount),
            "efetivo_registrado": format_value(ValueKind.INTEGER, point.recorded_headcount),
        }
        for point in points
    ]


def _histogram_maximum(points: Sequence[HistogramPoint]) -> int:
    return max((point.planned_hours for point in points), default=0) or 1


def _hours_kpis(screen: service.HoursScreen) -> list[dict[str, str]]:
    summary = screen.summary
    last = summary.last_month
    last_text = calculations.month_display(last) if last is not None else "·"
    planned, planned_month = screen.planned_to_date, screen.planned_last_month

    def number(value: Decimal | int) -> str:
        return format_value(ValueKind.DECIMAL, Decimal(value), 0)

    return [
        {
            "rotulo": "HHT total registrado",
            "valor": number(summary.total_hours),
            "icone": "clock",
            "tom": "neutro",
            "referencia": f"Previsto: {number(planned.hours) if planned else '·'}",
            "rodape": f"histograma de mão de obra até {last_text}",
        },
        {
            "rotulo": "Meses com registro",
            "valor": number(summary.months_with_record),
            "icone": "calendar",
            "tom": "info",
            "referencia": f"Esperado: {number(screen.expected_months)}",
            "rodape": "",
        },
        {
            "rotulo": "Efetivo médio (último mês)",
            "valor": number(summary.last_month_headcount) if last is not None else "·",
            "icone": "person",
            "tom": "info",
            "referencia": f"Previsto: {number(planned_month.headcount) if planned_month else '·'}",
            "rodape": last_text if last is not None else "",
        },
        {
            "rotulo": "Empresas com registro",
            "valor": number(summary.companies_with_record),
            "icone": "building",
            "tom": "info",
            "referencia": f"Referência: de {number(screen.companies_expected)} previstas",
            "rodape": "",
        },
    ]


def _hours_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    page: int,
    notice: str | None = None,
) -> func.HttpResponse:
    today = calendario.today()
    screen = service.hours_screen(session, scope=context.scope, reference_date=today)
    shown = service.paginate(screen.rows, page)
    names = service.names_of(session)
    state: dict[str, str] = {}
    return AlpineAjaxResponse(
        template_name=HOURS_TEMPLATE,
        context={
            "kpis": _hours_kpis(screen),
            "linhas": shown.rows,
            "pagina": shown.page,
            "pagina_total": shown.page_count,
            "total": shown.total,
            "link_anterior": _page_link(HOURS_ROUTE, state, shown.page - 1, shown.page_count),
            "link_proximo": _page_link(HOURS_ROUTE, state, shown.page + 1, shown.page_count),
            "consulta": urlencode({"pagina": shown.page}),
            "url_excel": f"{HOURS_ROUTE}/excel",
            "url_pdf": f"{HOURS_ROUTE}/imprimivel",
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "portfolio": context.scope.is_portfolio,
            "pontos": _histogram_rows(screen.histogram, names),
            "maximo": _histogram_maximum(screen.histogram),
            **_helpers(),
        },
        request=req,
        target_id=HOURS_TARGET,
        toast=notice,
    )


@dataclass(frozen=True)
class _HoursForm:
    """What an HHT form remembers: the record being edited, what was typed and the refusal."""

    hours_id: int | None
    values: Mapping[str, str]
    error: DomainError | None = None
    query: str = ""


def _hours_form(req: func.HttpRequest, session: Session, state: _HoursForm) -> func.HttpResponse:
    today = calendario.today()
    fields = forms.hours_fields(
        state.values,
        companies=service.company_options(session),
        reference_date=today,
        locked=state.hours_id is not None,
    )
    errors = _field_errors(state.error)
    stale = isinstance(state.error, VersionConflictError)
    version = state.values.get("versao", "")
    if stale and state.hours_id is not None:
        current = service.find_hours(session, hours_id=state.hours_id)
        version = str(current.version) if current else version
    action = (
        f"{HOURS_ROUTE}/novo"
        if state.hours_id is None
        else f"{HOURS_ROUTE}/{state.hours_id}/editar"
    )
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={
            "acao": action,
            "alvo": HOURS_TARGET,
            "campos": forms.attach_errors(fields, errors),
            "erros_gerais": _general_messages(errors, fields),
            "versao": version,
            "consulta": state.query,
            "checklist": None,
            "rotulo_salvar": "Salvar HHT",
            "texto_de_apoio": (
                "Gravar de novo o mesmo mês e empresa atualiza o registro, sem duplicar."
                if state.hours_id is None
                else "Mês e empresa ficam bloqueados: para outro mês ou empresa, registre um novo HHT."
            ),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=200 if state.error is None else _status(state.error),
    )


@bp.route(route="hse/hht/novo", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def hours_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The empty HHT form of the project in scope."""
    context.scope.require_project()
    return _hours_form(req, session, _HoursForm(None, {}, query=req.params.get("pagina", "")))


@bp.route(route="hse/hht/novo", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def hours_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the HHT of a month and company; saving again updates the same record."""
    form = req.form
    data = forms.parse_hours(form, project_id=context.scope.require_project())
    today = calendario.today()
    result, error = _attempt(
        session,
        lambda: service.save_hours(session, user=context.user, data=data, reference_date=today),
    )
    if error is not None:
        return _hours_form(
            req, session, _HoursForm(None, dict(form), error, form.get("consulta", ""))
        )
    notice = "HHT registrado." if result.created else "HHT atualizado."
    return _hours_response(
        req, session, context, page=validation.parse_page(_query(form)), notice=notice
    )


@bp.route(route="hse/hht/{hht_id}/editar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def hours_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The HHT form of an existing record: the month and the company are locked."""
    del context
    row = service.find_hours(session, hours_id=_id(req, "hht_id"))
    if row is None:
        raise InvalidDataError(NOT_FOUND)
    return _hours_form(
        req,
        session,
        _HoursForm(row.id, forms.values_of_hours(row), query=req.params.get("pagina", "")),
    )


@bp.route(route="hse/hht/{hht_id}/editar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def hours_edit_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the HHT of the same month and company: the form cannot move the record."""
    form = req.form
    row = service.find_hours(session, hours_id=_id(req, "hht_id"))
    if row is None:
        raise InvalidDataError(NOT_FOUND)
    sent = forms.parse_hours(form, project_id=row.project_id)
    data = replace(sent, month=row.month, company_id=row.company_id)
    today = calendario.today()
    _, error = _attempt(
        session,
        lambda: service.save_hours(session, user=context.user, data=data, reference_date=today),
    )
    if error is not None:
        values = {
            **form,
            "mes": calculations.month_label(row.month),
            "empresa": str(row.company_id),
        }
        return _hours_form(
            req, session, _HoursForm(row.id, values, error, form.get("consulta", ""))
        )
    return _hours_response(
        req, session, context, page=validation.parse_page(_query(form)), notice="HHT atualizado."
    )


def _query(form: Mapping[str, str]) -> dict[str, str]:
    """The state of the screen a form was opened from (``pagina=2&aba=dds``) as a mapping."""
    return dict(parse_qsl(form.get("consulta", "")))


# ── Inspeções e observações ──────────────────────────────────────────────────────────────────

TAB_LABELS = (
    (forms.KIND_CLOSING, "Consolidado mensal", "mensal"),
    (forms.KIND_INSPECTION, "Inspeções", "inspecoes"),
    (forms.KIND_OBSERVATION, "Observações", "observacoes"),
    (forms.KIND_TALK, "DDS", "dds"),
)
NEW_LABELS = {
    forms.KIND_CLOSING: (
        "Registrar mês",
        "Consolidado do mês; grava (ou atualiza) o total informado",
    ),
    forms.KIND_INSPECTION: ("Registrar inspeção", "Checklist com itens conformes e não conformes"),
    forms.KIND_OBSERVATION: ("Registrar observação", "Observação comportamental"),
    forms.KIND_TALK: ("Registrar DDS", "Diálogo diário de segurança"),
}
EMPTY_TEXTS = {
    forms.KIND_CLOSING: "Registre o consolidado do mês (DDS, itens inspecionados, observações e desvios) ou importe a planilha.",
    forms.KIND_INSPECTION: "Registre as inspeções de segurança com o checklist de itens conformes e não conformes.",
    forms.KIND_OBSERVATION: "Registre as observações comportamentais feitas em campo.",
    forms.KIND_TALK: "Registre os diálogos diários de segurança com tema, data e participantes.",
}


def _tab(params: Mapping[str, str]) -> str:
    chosen = (params.get("aba") or "").strip()
    return chosen if chosen in forms.RECORD_KINDS else forms.KIND_CLOSING


def _proactive_kpis(summary: calculations.ProactiveSummary) -> list[dict[str, str]]:
    def number(value: int) -> str:
        return format_value(ValueKind.INTEGER, value)

    def rate(value: Decimal | None) -> str:
        return "·" if value is None else format_value(ValueKind.PERCENT, value, 1)

    def target(value: int | None, text: str) -> str:
        return f"{text}: ·" if value is None else f"{text}: ≥ {number(value)}"

    observations_low = (
        summary.observations_target is not None
        and summary.observations < summary.observations_target
    )
    deviations_low = (
        summary.deviations_target is not None and summary.deviations < summary.deviations_target
    )
    return [
        {
            "rotulo": "DDS realizados",
            "valor": rate(summary.dds_rate),
            "icone": "calendar",
            "tom": "info",
            "referencia": "Meta: 100%",
            "rodape": f"{number(summary.held_dds)} de {number(summary.planned_dds)} programados",
        },
        {
            "rotulo": "Conformidade em inspeções",
            "valor": rate(summary.conformity_rate),
            "icone": "checkCircle",
            "tom": "info",
            "referencia": "Esperado: 100%",
            "rodape": f"{number(summary.conforming_items)} de {number(summary.inspected_items)} itens",
        },
        {
            "rotulo": "Observações comportamentais",
            "valor": number(summary.observations),
            "icone": "eye",
            "tom": "warn" if observations_low else "neutro",
            "referencia": target(summary.observations_target, "Meta"),
            "rodape": "relato em campo por 10 mil HHT",
        },
        {
            "rotulo": "Desvios (nível 5)",
            "valor": number(summary.deviations),
            "icone": "taskList",
            "tom": "warn" if deviations_low else "neutro",
            "referencia": target(summary.deviations_target, "Meta de relato"),
            "rodape": "atos e condições inseguras",
        },
    ]


def _rows_of_tab(session: Session, context: RequestContext, tab: str) -> Sequence[Any]:
    scope = context.scope
    if tab == forms.KIND_INSPECTION:
        return service.list_inspections(session, scope=scope)
    if tab == forms.KIND_OBSERVATION:
        return service.list_observations(session, user=context.user, scope=scope)
    if tab == forms.KIND_TALK:
        return service.list_talks(session, scope=scope)
    return service.list_closings(session, scope=scope)


def _proactive_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    state: Mapping[str, str],
    notice: str | None = None,
) -> func.HttpResponse:
    today = calendario.today()
    tab = _tab(state)
    shown = service.paginate(_rows_of_tab(session, context, tab), validation.parse_page(state))
    counts = service.count_records(session, scope=context.scope)
    summary = service.proactive_summary(session, scope=context.scope, reference_date=today)
    base = {"aba": tab}
    title, subtitle = NEW_LABELS[tab]
    return AlpineAjaxResponse(
        template_name=PROACTIVE_TEMPLATE,
        context={
            "kpis": _proactive_kpis(summary),
            "abas": [
                {
                    "chave": key,
                    "rotulo": label,
                    "total": counts[count_key],
                    "url": f"{PROACTIVE_ROUTE}?{urlencode({'aba': key})}",
                }
                for key, label, count_key in TAB_LABELS
            ],
            "aba": tab,
            "linhas": shown.rows,
            "total": shown.total,
            "pagina": shown.page,
            "pagina_total": shown.page_count,
            "link_anterior": _page_link(PROACTIVE_ROUTE, base, shown.page - 1, shown.page_count),
            "link_proximo": _page_link(PROACTIVE_ROUTE, base, shown.page + 1, shown.page_count),
            "consulta": urlencode({**base, "pagina": shown.page}),
            "url_excel": f"{PROACTIVE_ROUTE}/excel",
            "url_pdf": f"{PROACTIVE_ROUTE}/imprimivel",
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "portfolio": context.scope.is_portfolio,
            "ver_observado": rbac.can(context.user, Permission.VIEW_RESTRICTED),
            "rotulo_novo": title,
            "subtitulo_novo": subtitle,
            "url_novo": f"{PROACTIVE_ROUTE}/{tab}/novo",
            "texto_vazio": EMPTY_TEXTS[tab],
            **_helpers(),
        },
        request=req,
        target_id=PROACTIVE_TARGET,
        toast=notice,
    )


@bp.route(route="hse/inspecoes", methods=["GET"])
@fragment_route(access=READ)
def proactive_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The screen: indicators and the table of the chosen tab, for the page in the query."""
    return _proactive_response(req, session, context, state=dict(req.params))


def _proactive_document(session: Session, context: RequestContext) -> Any:
    today = calendario.today()
    scope = context.scope
    data = export.ProactiveData(
        summary=service.proactive_summary(session, scope=scope, reference_date=today),
        closings=service.list_closings(session, scope=scope),
        inspections=service.list_inspections(session, scope=scope),
        observations=service.list_observations(session, user=context.user, scope=scope),
        talks=service.list_talks(session, scope=scope),
        show_observed=rbac.can(context.user, Permission.VIEW_RESTRICTED),
    )
    return export.proactive_document(
        data, scope=scope, projects=configuracoes.list_projects(session), today=today
    )


@bp.route(route="hse/inspecoes/excel", methods=["GET"])
@file_route(access=READ)
def proactive_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the screen: indicators and the four lists."""
    del req
    return excel_response(_proactive_document(session, context))


@bp.route(route="hse/inspecoes/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def proactive_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_proactive_document(session, context), req)


@dataclass(frozen=True)
class _RecordForm:
    """What a record form remembers: the tab, the record, what was typed and the refusal."""

    kind: str
    record_id: int | None
    values: Mapping[str, str]
    error: DomainError | None = None
    query: str = ""
    checklist: Sequence[forms.ChecklistRow] | None = None


def _kind(req: func.HttpRequest) -> str:
    chosen = req.route_params.get("tipo") or ""
    if chosen not in forms.RECORD_KINDS:
        raise InvalidDataError(NOT_FOUND)
    return chosen


def _load(session: Session, context: RequestContext, kind: str, record_id: int) -> Any:
    user = context.user
    found = {
        forms.KIND_CLOSING: lambda: service.find_closing(session, closing_id=record_id),
        forms.KIND_INSPECTION: lambda: service.find_inspection(session, inspection_id=record_id),
        forms.KIND_OBSERVATION: lambda: service.find_observation(
            session, user=user, observation_id=record_id
        ),
        forms.KIND_TALK: lambda: service.find_talk(session, talk_id=record_id),
    }[kind]()
    if found is None:
        raise InvalidDataError(NOT_FOUND)
    return found


_VALUES_OF: dict[str, Callable[[Any], dict[str, str]]] = {
    forms.KIND_CLOSING: forms.values_of_closing,
    forms.KIND_INSPECTION: forms.values_of_inspection,
    forms.KIND_OBSERVATION: forms.values_of_observation,
    forms.KIND_TALK: forms.values_of_talk,
}


def _record_fields(
    session: Session, context: RequestContext, state: _RecordForm
) -> tuple[forms.FormField, ...]:
    today = calendario.today()
    people = service.person_options(session)
    companies = service.company_options(session)
    values = state.values
    if state.kind == forms.KIND_CLOSING:
        return forms.closing_fields(
            values, reference_date=today, locked=state.record_id is not None
        )
    if state.kind == forms.KIND_INSPECTION:
        return forms.inspection_fields(
            _with_default_person(values, context),
            people=people,
            companies=companies,
            reference_date=today,
        )
    if state.kind == forms.KIND_OBSERVATION:
        return forms.observation_fields(
            _with_default_person(values, context),
            people=people,
            companies=companies,
            reference_date=today,
            show_observed=rbac.can(context.user, Permission.VIEW_RESTRICTED),
        )
    return forms.talk_fields(
        _with_default_person(values, context),
        people=people,
        companies=companies,
        reference_date=today,
    )


def _with_default_person(values: Mapping[str, str], context: RequestContext) -> dict[str, str]:
    """The person who opened the form is the responsible, until someone else is chosen."""
    return {"responsavel": str(context.user.person_id), **values}


def _record_form(
    req: func.HttpRequest, session: Session, context: RequestContext, state: _RecordForm
) -> func.HttpResponse:
    fields = _record_fields(session, context, state)
    errors = _field_errors(state.error)
    shown = forms.attach_errors(fields, errors)
    general = _general_messages(errors, fields)
    if "itens" in errors:
        general.append(errors["itens"])
    version = state.values.get("versao", "")
    if isinstance(state.error, VersionConflictError) and state.record_id is not None:
        version = str(_load(session, context, state.kind, state.record_id).version)
    path = f"{PROACTIVE_ROUTE}/{state.kind}"
    action = f"{path}/novo" if state.record_id is None else f"{path}/{state.record_id}/editar"
    title, subtitle = NEW_LABELS[state.kind]
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={
            "acao": action,
            "alvo": PROACTIVE_TARGET,
            "campos": shown,
            "erros_gerais": general,
            "versao": version,
            "consulta": state.query,
            "checklist": (
                forms.checklist_rows_of(_items_for(session, context, state), state.checklist)
                if state.kind == forms.KIND_INSPECTION
                else None
            ),
            "rotulo_salvar": title,
            "texto_de_apoio": subtitle if state.record_id is None else "",
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=200 if state.error is None else _status(state.error),
    )


def _items_for(
    session: Session, context: RequestContext, state: _RecordForm
) -> Sequence[Any] | None:
    if state.record_id is None:
        return None
    return _load(session, context, forms.KIND_INSPECTION, state.record_id).items


@bp.route(route="hse/inspecoes/{tipo}/novo", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def record_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The empty form of a record of the project in scope."""
    context.scope.require_project()
    state = _RecordForm(_kind(req), None, {}, query=_screen_query(req.params))
    return _record_form(req, session, context, state)


@bp.route(route="hse/inspecoes/{tipo}/{registro_id}/editar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def record_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of an existing record, filled in (the month of a closing is locked)."""
    kind = _kind(req)
    row = _load(session, context, kind, _id(req, "registro_id"))
    state = _RecordForm(kind, row.id, _VALUES_OF[kind](row), query=_screen_query(req.params))
    return _record_form(req, session, context, state)


def _screen_query(params: Mapping[str, str]) -> str:
    """The tab and page of the screen the form was opened from, to come back to it."""
    return urlencode({key: params[key] for key in ("aba", "pagina") if params.get(key)})


def _save_record(
    session: Session,
    context: RequestContext,
    *,
    kind: str,
    form: Mapping[str, str],
    record_id: int | None,
) -> Any:
    """Parse the form of the kind and save it through the facade; returns the ``SaveResult``."""
    today = calendario.today()
    user = context.user
    if record_id is None:
        project_id = context.scope.require_project()
    else:
        project_id = _load(session, context, kind, record_id).project_id
    if kind == forms.KIND_CLOSING:
        closing = forms.parse_closing(form, project_id=project_id)
        if record_id is not None:
            row = _load(session, context, kind, record_id)
            closing = replace(closing, month=row.month)
        return service.save_closing(session, user=user, data=closing, reference_date=today)
    if kind == forms.KIND_INSPECTION:
        return service.save_inspection(
            session,
            user=user,
            data=forms.parse_inspection(form, project_id=project_id),
            reference_date=today,
            inspection_id=record_id,
        )
    if kind == forms.KIND_OBSERVATION:
        return service.save_observation(
            session,
            user=user,
            data=forms.parse_observation(form, project_id=project_id),
            reference_date=today,
            observation_id=record_id,
        )
    return service.save_talk(
        session,
        user=user,
        data=forms.parse_talk(form, project_id=project_id),
        reference_date=today,
        talk_id=record_id,
    )


def _record_saved(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    kind: str,
    record_id: int | None,
) -> func.HttpResponse:
    form = req.form
    result, error = _attempt(
        session,
        lambda: _save_record(session, context, kind=kind, form=form, record_id=record_id),
    )
    if error is not None:
        state = _RecordForm(
            kind,
            record_id,
            _locked_values(session, context, kind, record_id, form),
            error,
            form.get("consulta", ""),
            forms.checklist_of(form) if kind == forms.KIND_INSPECTION else None,
        )
        return _record_form(req, session, context, state)
    notice = f"{NEW_LABELS[kind][0].replace('Registrar ', '').capitalize()} {'registrado' if result.created else 'atualizado'}."
    return _proactive_response(req, session, context, state=_query(form), notice=notice)


def _locked_values(
    session: Session,
    context: RequestContext,
    kind: str,
    record_id: int | None,
    form: Mapping[str, str],
) -> dict[str, str]:
    values = dict(form)
    if kind == forms.KIND_CLOSING and record_id is not None:
        row = _load(session, context, kind, record_id)
        values["mes"] = calculations.month_label(row.month)
    return values


@bp.route(route="hse/inspecoes/{tipo}/novo", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def record_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record a new inspection, observation, DDS or monthly closing (the closing upserts)."""
    return _record_saved(req, session, context, kind=_kind(req), record_id=None)


@bp.route(route="hse/inspecoes/{tipo}/{registro_id}/editar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def record_edit_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the changes of an existing record, with the version the screen opened."""
    return _record_saved(req, session, context, kind=_kind(req), record_id=_id(req, "registro_id"))
