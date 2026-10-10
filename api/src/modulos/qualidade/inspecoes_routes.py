"""Routes of Inspeções e ITP, the second screen of the Quality module (ISSUE-069, D14).

Prefix ``/api/qualidade/inspecoes``. The screen is one fragment, ``inspecoes-conteudo``:
context line, the five KPIs, the ITP table, the filters and the list of the inspections with
the pagination. Everything that changes the view (a filter, a page) is a plain GET of the same
route with the filters in the query string, answered with the same fragment. The ficha of the
ITP and the forms (new ITP, new revision, approval of the client and the inspection) open in
the modal (``inspecoes-modal-corpo``): a GET draws them, a POST saves and answers the refreshed
list; a refusal (422, 409, 403) answers the form again, filled in, in the modal. In the
Portfólio the forms ask for the project before opening.

* ``GET  inspecoes``                              the screen (filters and page by query);
* ``GET  inspecoes/excel`` and ``inspecoes/imprimivel``  the two exports of what the screen shows;
* ``GET  inspecoes/{codigo}/ficha``               the ficha of the ITP with its points;
* ``GET/POST inspecoes/itp/novo``                 Novo ITP (revision 0);
* ``GET/POST inspecoes/itp/{codigo}/revisao``     Nova revisão (volta a pedir a aprovação);
* ``GET/POST inspecoes/itp/{codigo}/aprovacao``   Aprovação do cliente (Gestor);
* ``GET/POST inspecoes/inspecao``                 Registrar inspeção em ponto de ITP aprovado.

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, origin_links, rbac
from src.core.errors import AccessDeniedError, DomainError, InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.export_document import Document
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.qualidade import export, service, validation
from src.modulos.qualidade.calculations import POINT_RESPONSIBLES
from src.modulos.qualidade.service import InspectionSummary, ItpLine
from src.modulos.qualidade.validation import (
    InspectionFilters,
    InspectionInput,
    ItpApprovalInput,
    ItpFilters,
    ItpInput,
    ItpPointInput,
)

bp = func.Blueprint()

MODULE = "qualidade"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)
MANAGE = Access(module=MODULE, permission=Permission.MANAGE)

CONTENT_TARGET = "inspecoes-conteudo"
MODAL_TARGET = "inspecoes-modal-corpo"
ROUTE = "/api/qualidade/inspecoes"

SCREEN_TEMPLATE = "qualidade/inspecoes.html"
PROJECT_TEMPLATE = "qualidade/inspecoes_projeto.html"
ITP_FORM_TEMPLATE = "qualidade/inspecoes_itp_form.html"
APPROVAL_TEMPLATE = "qualidade/inspecoes_aprovacao.html"
FICHA_TEMPLATE = "qualidade/inspecoes_ficha.html"
INSPECTION_TEMPLATE = "qualidade/inspecoes_inspecao.html"

ITP_SAVED_NOTICE = "ITP {code} gravada. Registre a aprovação do cliente antes das inspeções."
REVISION_SAVED_NOTICE = (
    "Revisão {revision} de {code} gravada. Registre a aprovação do cliente antes das inspeções."
)
APPROVED_NOTICE = "ITP {code} aprovado pelo cliente."
INSPECTION_NOTICE = "Inspeção {code} registrada."
CHOOSE_PROJECT_MESSAGE = "Escolha o projeto do ITP."


def _error_status(error: DomainError) -> int:
    """The status of a refusal: 403, 409 for a stale screen, 422 for data that does not hold up."""
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


def _field_errors(error: DomainError | None) -> dict[str, str]:
    if error is None:
        return {}
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return dict(error.detail)
    return {"geral": str(error)}


def _attempt(session: Session, work: Callable[[], object]) -> DomainError | None:
    """Run a write inside a savepoint: a refusal leaves nothing behind, not even a half write."""
    try:
        with session.begin_nested():
            work()
    except (InvalidDataError, VersionConflictError) as error:
        return error
    return None


def _modal_error(
    req: func.HttpRequest, error: DomainError, *, target: str = MODAL_TARGET
) -> func.HttpResponse:
    """A refusal inside the modal: the message in the modal body, where the person is looking."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=target,
        status_code=_error_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


def _consulta_of(req: func.HttpRequest) -> str:
    """The query string of the list, carried by the forms so the save keeps the filters."""
    return req.form.get("consulta", "") or req.params.get("consulta", "")


def _form_filters(form: Mapping[str, str]) -> InspectionFilters:
    """The filters of the list as the form carried them, not the fields of the form itself."""
    return validation.parse_inspection_filters(dict(parse_qsl(form.get("consulta", ""))))


@dataclass(frozen=True)
class KpiCard:
    """A KPI of the screen: the number, what it is read against and the situation in words."""

    label: str
    icon: str
    tone: str
    value: str
    unit: str
    reference: str
    footer: str


# ── The screen ───────────────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/inspecoes", methods=["GET"])
@fragment_route(access=READ)
def inspection_list_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The screen: KPIs, the ITP table, the filters and the inspections of the query."""
    return _screen(req, session, context, filters=validation.parse_inspection_filters(req.params))


@bp.route(route="qualidade/inspecoes/excel", methods=["GET"])
@file_route(access=READ)
def inspection_list_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the screen: the KPIs, the plans and the inspections of the filter."""
    return excel_response(_document(req, session, context))


@bp.route(route="qualidade/inspecoes/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def inspection_list_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


# ── Ficha do ITP ─────────────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/inspecoes/{codigo}/ficha", methods=["GET"])
@fragment_route(access=READ)
def itp_sheet_fragment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The ficha of one ITP: the approval and the points of the current revision."""
    line = _itp_line(session, context, req)
    if line is None:
        return _not_found(req)
    return AlpineAjaxResponse(
        template_name=FICHA_TEMPLATE,
        context={
            "itp": line,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "pode_gerir": rbac.can(context.user, Permission.MANAGE),
            "formatar_data": _format_date,
        },
        request=req,
        target_id=MODAL_TARGET,
    )


# ── Novo ITP e nova revisão ──────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/inspecoes/itp/novo", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def itp_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new ITP; in the Portfólio the project is asked first."""
    project_id = context.scope.project_id or validation.parse_id(req.params.get("projeto"))
    if project_id is None:
        return _project_choice(req, session, destino=f"{ROUTE}/itp/novo")
    return _itp_form(req, session, state=_ItpFormState(project_id=project_id, values={}), code=None)


@bp.route(route="qualidade/inspecoes/itp/novo", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def itp_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the ITP and answer the refreshed list, or the form with its messages."""
    project_id = context.scope.project_id or validation.parse_id(req.form.get("projeto"))
    if project_id is None:
        raise InvalidDataError(CHOOSE_PROJECT_MESSAGE)
    data = _itp_input(req.form, project_id=project_id)
    outcome: list[service.ItpResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.create_itp(
                session, user=context.user, data=data, reference_date=calendario.today()
            )
        ),
    )
    if error is not None or not outcome:
        return _itp_form(
            req,
            session,
            state=_ItpFormState(
                project_id=project_id, values=dict(req.form), errors=_field_errors(error)
            ),
            code=None,
            status=_error_status(error) if error else 200,
        )
    return _screen(
        req,
        session,
        context,
        filters=InspectionFilters(),
        after=ITP_SAVED_NOTICE.format(code=outcome[0].code),
    )


@bp.route(route="qualidade/inspecoes/itp/{codigo}/revisao", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def itp_revision_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new revision of the ITP, filled in with the current points."""
    line = _itp_line(session, context, req)
    if line is None:
        return _not_found(req)
    return _itp_form(
        req,
        session,
        state=_ItpFormState(project_id=line.project_id, values=_itp_values(line)),
        code=line.code,
    )


@bp.route(route="qualidade/inspecoes/itp/{codigo}/revisao", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def itp_revision_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Write the next revision and answer the refreshed list, or the form with its messages."""
    line = _itp_line(session, context, req)
    if line is None:
        return _not_found(req)
    data = _itp_input(req.form, project_id=line.project_id)
    outcome: list[service.ItpResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.revise_itp(
                session,
                user=context.user,
                code=line.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _itp_form(
            req,
            session,
            state=_ItpFormState(
                project_id=line.project_id,
                values=dict(req.form),
                errors=_field_errors(error),
            ),
            code=line.code,
            status=_error_status(error) if error else 200,
        )
    return _screen(
        req,
        session,
        context,
        filters=_form_filters(req.form),
        after=REVISION_SAVED_NOTICE.format(revision=outcome[0].revision, code=line.code),
    )


def _itp_form(
    req: func.HttpRequest,
    session: Session,
    *,
    state: _ItpFormState,
    code: str | None,
    status: int = 200,
) -> func.HttpResponse:
    """The ITP form, empty or filled in with the current points or the messages of a refusal."""
    return AlpineAjaxResponse(
        template_name=ITP_FORM_TEMPLATE,
        context={
            "projeto": configuracoes.find_project(session, state.project_id),
            "projeto_id": state.project_id,
            "codigo": code,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "visiveis": _visible_points(state.values),
            "disciplinas": configuracoes.list_discipline_names(session),
            "empresas": configuracoes.list_company_options(session),
            "responsaveis": POINT_RESPONSIBLES,
            "tipos_ponto": validation.POINT_TYPES,
            "max_pontos": validation.MAX_POINTS,
            "consulta": _consulta_of(req),
            "notificacao_horas": service.notification_minimum_hours(
                session, reference_date=calendario.today()
            ),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


# ── Aprovação do cliente ─────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/inspecoes/itp/{codigo}/aprovacao", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def itp_approval_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The approval of the client of the current revision: Gestor only, once per revision."""
    line = _itp_line(session, context, req)
    if line is None:
        return _not_found(req)
    return _approval_fragment(
        req, line=line, values={"data": calendario.today().isoformat()}, errors={}
    )


@bp.route(route="qualidade/inspecoes/itp/{codigo}/aprovacao", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def itp_approval_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the approval and answer the refreshed list, or the form with its messages."""
    line = _itp_line(session, context, req)
    if line is None:
        return _not_found(req)
    data = ItpApprovalInput(
        reference=req.form.get("referencia", ""),
        approval_date=validation.parse_date(req.form.get("data")),
    )
    error = _attempt(
        session,
        lambda: service.approve_itp(
            session,
            user=context.user,
            code=line.code,
            data=data,
            reference_date=calendario.today(),
        ),
    )
    if error is not None:
        return _approval_fragment(
            req,
            line=line,
            values=dict(req.form),
            errors=_field_errors(error),
            status=_error_status(error),
        )
    return _screen(
        req,
        session,
        context,
        filters=_form_filters(req.form),
        after=APPROVED_NOTICE.format(code=line.code),
    )


def _approval_fragment(
    req: func.HttpRequest,
    *,
    line: ItpLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=APPROVAL_TEMPLATE,
        context={
            "itp": line,
            "valores": dict(values),
            "erros": dict(errors),
            "consulta": _consulta_of(req),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


# ── Registrar inspeção ───────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/inspecoes/inspecao", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def inspection_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of an inspection; in the Portfólio the project is asked first."""
    project_id = context.scope.project_id or validation.parse_id(req.params.get("projeto"))
    if project_id is None:
        return _project_choice(req, session, destino=f"{ROUTE}/inspecao")
    return _inspection_fragment(
        req,
        session,
        context,
        project_id=project_id,
        values={},
        errors={},
        itp_param=validation.parse_id(req.params.get("itp")),
    )


@bp.route(route="qualidade/inspecoes/inspecao", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def inspection_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the inspection; a rejection opens the RNC in the same transaction (D9)."""
    project_id = context.scope.project_id or validation.parse_id(req.form.get("projeto"))
    if project_id is None:
        raise InvalidDataError(CHOOSE_PROJECT_MESSAGE)
    data = _inspection_input(req.form, project_id=project_id)
    outcome: list[service.InspectionResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.record_inspection(
                session, user=context.user, data=data, reference_date=calendario.today()
            )
        ),
    )
    if error is not None or not outcome:
        return _inspection_fragment(
            req,
            session,
            context,
            project_id=project_id,
            values=dict(req.form),
            errors=_field_errors(error),
            itp_param=validation.parse_id(req.form.get("itpId")),
            status=_error_status(error) if error else 200,
        )
    result = outcome[0]
    notice = INSPECTION_NOTICE.format(code=result.code)
    if result.rnc_code:
        notice = f"{notice} {result.rnc_code} aberta."
    if result.warnings:
        notice = f"{notice} {result.warnings[0]}"
    return _screen(
        req,
        session,
        context,
        filters=_form_filters(req.form),
        after=notice,
        after_tipo="aviso" if (result.rnc_code or result.warnings) else "ok",
        avisos=result.warnings,
    )


def _inspection_fragment(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    project_id: int,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    itp_param: int | None,
    status: int = 200,
) -> func.HttpResponse:
    """The inspection form, with the points of the chosen ITP of the project."""
    itps = [
        line
        for line in service.list_itps(
            session,
            user=context.user,
            scope=Scope(project_id=project_id, source="padrao"),
            filters=ItpFilters(),
            reference_date=calendario.today(),
        ).lines
        if line.project_id == project_id and line.approved_by_client
    ]
    chosen_id = validation.parse_id(values.get("itpId")) or itp_param
    chosen = next((line for line in itps if line.id == chosen_id), itps[0] if itps else None)
    return AlpineAjaxResponse(
        template_name=INSPECTION_TEMPLATE,
        context={
            "projeto_id": project_id,
            "valores": dict(values),
            "erros": dict(errors),
            "itps": itps,
            "itp": chosen,
            "pontos": chosen.points if chosen is not None else (),
            "pessoas": configuracoes.list_person_options(session),
            "resultados": validation.INSPECTION_RESULTS,
            "severidades": validation.SEVERITIES,
            "tipos_ponto": validation.POINT_TYPES,
            "referencia": calendario.today().isoformat(),
            "consulta": _consulta_of(req),
            "url_inspecao": f"{ROUTE}/inspecao",
            "notificacao_horas": service.notification_minimum_hours(
                session, reference_date=calendario.today()
            ),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


# ── Drawing the screen ───────────────────────────────────────────────────────────────────────


def _screen(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: InspectionFilters,
    after: str | None = None,
    after_tipo: str = "ok",
    avisos: tuple[str, ...] = (),
) -> func.HttpResponse:
    """The list fragment for the filters, with an optional toast and the warnings of a save."""
    today = calendario.today()
    itps = service.list_itps(
        session,
        user=context.user,
        scope=context.scope,
        filters=ItpFilters(),
        reference_date=today,
    )
    listing = service.list_inspections(
        session, user=context.user, scope=context.scope, filters=filters
    )
    summary = service.inspecoes_summary(
        session, user=context.user, scope=context.scope, reference_date=today
    )
    meta = _meta_pct(session, today)
    shown = replace(filters, page=listing.page)
    query = _query_string(shown)
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={
            "itps": itps,
            "listagem": listing,
            "resumo": summary,
            "filtros": shown,
            "meta": meta,
            "kpis": _kpi_cards(summary, meta),
            "consulta": query,
            "parametro_consulta": urlencode({"consulta": query}) if query else "",
            "url_excel": _address(shown, path=f"{ROUTE}/excel"),
            "url_pdf": _address(shown, path=f"{ROUTE}/imprimivel"),
            "portfolio": context.scope.is_portfolio,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "pode_gerir": rbac.can(context.user, Permission.MANAGE),
            "resultados": validation.INSPECTION_RESULTS,
            "tipos_ponto": validation.POINT_TYPES,
            "link_limpar": _address(InspectionFilters()),
            "link_anterior": _page_link(shown, shown.page - 1, listing.page_count),
            "link_proximo": _page_link(shown, shown.page + 1, listing.page_count),
            "pagina_inicial": (shown.page - 1) * validation.PAGE_SIZE + 1,
            "pagina_final": min(shown.page * validation.PAGE_SIZE, listing.total),
            "tem_filtro": shown != InspectionFilters(),
            "avisos": tuple(avisos),
            "formatar_data": _format_date,
            "link_rnc": lambda code: origin_links.link_to_screen("qualidade/rnc", busca=code),
        },
        request=req,
        target_id=CONTENT_TARGET,
        toast=after,
        toast_tipo=after_tipo,
    )


def _project_choice(req: func.HttpRequest, session: Session, *, destino: str) -> func.HttpResponse:
    """The Portfólio asks for the project before it opens the form (HU-016)."""
    return AlpineAjaxResponse(
        template_name=PROJECT_TEMPLATE,
        context={
            "projetos": configuracoes.list_projects(session),
            "destino": destino,
            "consulta": req.params.get("consulta", ""),
        },
        request=req,
        target_id=MODAL_TARGET,
    )


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """The export document of the screen for the filters of the query."""
    today = calendario.today()
    filters = replace(validation.parse_inspection_filters(req.params), page=1)
    itps = service.list_itps(
        session,
        user=context.user,
        scope=context.scope,
        filters=ItpFilters(),
        reference_date=today,
    )
    return export.build_inspecoes_document(
        itps=itps,
        inspections=service.list_inspections(
            session, user=context.user, scope=context.scope, filters=filters
        ),
        summary=service.inspecoes_summary(
            session, user=context.user, scope=context.scope, reference_date=today
        ),
        filters=filters,
        scope=context.scope,
        projects=configuracoes.list_project_details(session),
        today=today,
        meta_pct=_meta_pct(session, today),
    )


def _meta_pct(session: Session, reference_date: date) -> Decimal:
    """The approval target of the inspections, from the parameters in force."""
    return Decimal(
        str(service.parameters(session, reference_date=reference_date)["metaAprovacaoInspecaoPct"])
    )


def _kpi_cards(summary: InspectionSummary, meta: Decimal) -> list[KpiCard]:
    pending = summary.itps - summary.itps_approved
    if summary.approval_pct is None:
        approval_tone = "info"
    else:
        approval_tone = "ok" if summary.approval_pct >= meta else "warn"
    return [
        KpiCard(
            label="Inspeções registradas",
            icon="clipboardCheck",
            tone="info",
            value=str(summary.registered),
            unit="",
            reference=f"Previsto: {summary.points} pontos",
            footer=f"{summary.with_remark} com ressalva",
        ),
        KpiCard(
            label="Aprovação nas inspeções",
            icon="checkCircle",
            tone=approval_tone,
            value="·" if summary.approval_pct is None else _decimal_text(summary.approval_pct),
            unit="" if summary.approval_pct is None else "%",
            reference=f"Meta: {meta:.0f}%",
            footer="ressalva conta como aprovada",
        ),
        KpiCard(
            label="Reprovadas",
            icon="warning",
            tone="erro" if summary.rejected else "ok",
            value=str(summary.rejected),
            unit="",
            reference="Esperado: 0",
            footer=(
                f"{summary.rejected_open_rnc} RNC em aberto"
                if summary.rejected_open_rnc == 1
                else f"{summary.rejected_open_rnc} RNCs em aberto"
            ),
        ),
        KpiCard(
            label="ITPs aprovados pelo cliente",
            icon="shield",
            tone="warn" if pending else "ok",
            value=str(summary.itps_approved),
            unit=f"de {summary.itps}",
            reference="Meta: 100%",
            footer=(f"{pending} aguardando aprovação" if pending else "todos aprovados"),
        ),
        KpiCard(
            label="Pontos já inspecionados",
            icon="checkCircle",
            tone="info",
            value=str(summary.covered_points),
            unit=f"de {summary.points}",
            reference="Meta: 100%",
            footer="ao menos um registro no ponto",
        ),
    ]


def _query_string(filters: InspectionFilters, *, with_page: bool = True) -> str:
    values: dict[str, str] = {}
    if filters.search:
        values["busca"] = filters.search
    if filters.itp_id is not None:
        values["itp"] = str(filters.itp_id)
    if filters.result:
        values["resultado"] = filters.result
    if filters.point_type:
        values["tipo"] = filters.point_type
    if with_page and filters.page > 1:
        values["pagina"] = str(filters.page)
    return urlencode(values)


def _address(filters: InspectionFilters, *, path: str = ROUTE, **overrides: str) -> str:
    """The address of the screen (or of an export) with the filters and the overrides."""
    updated = replace(filters, **overrides) if overrides else filters
    query = _query_string(updated, with_page=path == ROUTE)
    return f"{path}?{query}" if query else path


def _page_link(filters: InspectionFilters, page: int, page_count: int) -> str:
    if page < 1 or page > page_count or page == filters.page:
        return ""
    return _address(replace(filters, page=page))


@dataclass(frozen=True)
class _ItpFormState:
    """What the ITP form remembers: the project, what was typed and the messages."""

    project_id: int
    values: Mapping[str, str]
    errors: Mapping[str, str] = field(default_factory=dict)


def _itp_input(form: Mapping[str, str], *, project_id: int) -> ItpInput:
    return ItpInput(
        project_id=project_id,
        title=form.get("titulo", ""),
        discipline=form.get("disciplina", ""),
        company_id=validation.parse_id(form.get("empresaId")),
        points=_points_input(form),
        version=form.get("versao"),
    )


def _points_input(form: Mapping[str, str]) -> tuple[ItpPointInput, ...]:
    """The point blocks of the form, in order; a block with nothing filled is left out."""
    result: list[ItpPointInput] = []
    for position in range(1, validation.MAX_POINTS + 1):
        activity = form.get(f"ponto{position}_atividade", "")
        point_type = form.get(f"ponto{position}_tipo", "")
        criterion = form.get(f"ponto{position}_criterio", "")
        reference = form.get(f"ponto{position}_referencia", "")
        responsible = form.get(f"ponto{position}_responsavel", "")
        if not any(
            part.strip() for part in (activity, point_type, criterion, reference, responsible)
        ):
            continue
        result.append(
            ItpPointInput(
                activity=activity,
                point_type=point_type,
                criterion=criterion,
                reference=reference,
                responsible=responsible,
            )
        )
    return tuple(result)


def _inspection_input(form: Mapping[str, str], *, project_id: int) -> InspectionInput:
    return InspectionInput(
        project_id=project_id,
        itp_id=validation.parse_id(form.get("itpId")),
        point_id=validation.parse_id(form.get("pontoId")),
        inspection_date=validation.parse_date(form.get("data")),
        inspector_id=validation.parse_id(form.get("inspetorId")),
        result=form.get("resultado", ""),
        observation=form.get("observacao", ""),
        severity=form.get("severidade", ""),
        containment=form.get("contencao", ""),
        notification=validation.parse_date(form.get("notificacao")),
    )


def _itp_values(line: ItpLine) -> dict[str, str]:
    """The current revision as the form values, so the revision opens filled in."""
    values = {
        "titulo": line.title,
        "disciplina": line.discipline,
        "empresaId": str(line.company_id),
        "versao": str(line.version),
    }
    for position, point in enumerate(line.points, start=1):
        values[f"ponto{position}_atividade"] = point.activity
        values[f"ponto{position}_tipo"] = point.point_type
        values[f"ponto{position}_criterio"] = point.criterion
        values[f"ponto{position}_referencia"] = point.reference
        values[f"ponto{position}_responsavel"] = point.responsible
    return values


def _visible_points(values: Mapping[str, str]) -> int:
    """How many point blocks the form shows: the filled ones, at least one."""
    filled = 0
    for position in range(1, validation.MAX_POINTS + 1):
        if any(
            (values.get(f"ponto{position}_{field}") or "").strip()
            for field in ("atividade", "tipo", "criterio", "referencia", "responsavel")
        ):
            filled = position
    return max(1, filled)


def _itp_line(session: Session, context: RequestContext, req: func.HttpRequest) -> ItpLine | None:
    code = req.route_params.get("codigo") or ""
    return service.itp_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )


def _not_found(req: func.HttpRequest) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": [service.ITP_NOT_FOUND_MESSAGE]},
        request=req,
        target_id=MODAL_TARGET,
        status_code=404,
        toast=service.ITP_NOT_FOUND_MESSAGE,
        toast_tipo="aviso",
    )


def _format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _decimal_text(value: Decimal) -> str:
    """A decimal as the screen writes it: one decimal place, comma, no trailing zeros."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")
