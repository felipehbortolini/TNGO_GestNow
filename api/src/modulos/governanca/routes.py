"""Route blueprint of the Governança module: the Registro de mudanças and the ficha of a change.

ISSUE-023 brings the screens ``governanca/mudancas`` (the register, with its KPIs and filters) and
``governanca/mudanca`` (the ficha, with the stage bar and the five tabs in reading), the new request and
the cancellation. Every route declares its ``Access`` (D14) and only reads the request, calls the facade
(``service``) and draws the answer; the rules are in ``calculations``, ``validation`` and ``service``.

* ``GET /api/governanca/mudancas`` is the register: the whole fragment on the first load and, when a
  filter is applied (the form asks for ``mudancas-kpis`` and ``mudancas-tabela``), only those two blocks;
* ``GET /api/governanca/mudancas/excel`` and ``/imprimivel`` are the two exports of the register;
* ``GET /api/governanca/mudancas/nova`` is the form of the new request and ``POST /api/governanca/mudancas``
  registers it (422 gives the form back filled, success goes to the ficha);
* ``GET /api/governanca/mudanca?codigo=`` is the ficha, with ``/excel`` and ``/imprimivel``;
* ``GET`` and ``POST /api/governanca/mudanca/cancelar`` are the cancellation with its justification;
* ``GET`` and ``POST /api/governanca/mudanca/analise/iniciar`` start the analysis (responsible and
  deadline) and ``GET`` and ``POST /api/governanca/mudanca/analise`` conclude, or revise, the impact
  analysis (ISSUE-024); a 422 gives the form back filled, success goes to the ficha.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import quote, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import AccessDeniedError, DomainError, InvalidDataError
from src.core.excel import excel_response
from src.core.export_document import Document
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse, redirect_to
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import (
    calculations,
    export,
    lessons_models,
    models,
    presentation,
    service,
    validation,
)

bp = func.Blueprint()

MODULE = service.MODULE

REGISTER_ROUTE = "governanca/mudancas"
REGISTER_EXCEL_ROUTE = "governanca/mudancas/excel"
REGISTER_PRINTABLE_ROUTE = "governanca/mudancas/imprimivel"
NEW_ROUTE = "governanca/mudancas/nova"
SHEET_ROUTE = "governanca/mudanca"
SHEET_PAGE = "/governanca/mudanca"
SHEET_EXCEL_ROUTE = "governanca/mudanca/excel"
SHEET_PRINTABLE_ROUTE = "governanca/mudanca/imprimivel"
CANCEL_ROUTE = "governanca/mudanca/cancelar"
START_ANALYSIS_ROUTE = "governanca/mudanca/analise/iniciar"
IMPACT_ROUTE = "governanca/mudanca/analise"
DECISION_ROUTE = "governanca/mudanca/decisao"
REOPEN_ROUTE = "governanca/mudanca/reapresentar"
CLOSING_ROUTE = "governanca/mudanca/encerrar"

REGISTER_TEMPLATE = "governanca/mudancas.html"
REGISTER_PARTS_TEMPLATE = "governanca/mudancas_partes.html"
NEW_TEMPLATE = "governanca/mudanca_nova.html"
SHEET_TEMPLATE = "governanca/mudanca.html"
NOT_FOUND_TEMPLATE = "governanca/mudanca_nao_encontrada.html"
CANCEL_TEMPLATE = "governanca/mudanca_cancelar.html"
START_ANALYSIS_TEMPLATE = "governanca/mudanca_analise_iniciar.html"
IMPACT_TEMPLATE = "governanca/mudanca_analise.html"
DECISION_TEMPLATE = "governanca/mudanca_decisao.html"
REOPEN_TEMPLATE = "governanca/mudanca_reapresentar.html"
CLOSING_TEMPLATE = "governanca/mudanca_encerrar.html"

SHEET_TARGET = "mudanca-ficha"
DECIDED_NOTICE = "Decisão registrada."
RESUBMITTED_NOTICE = "Solicitação reapresentada para decisão."
CLOSED_NOTICE = "Mudança encerrada."

# The two blocks the filter form replaces; their presence in the request header picks the short answer.
FILTERED_BLOCKS = ("mudancas-kpis", "mudancas-tabela")
TARGET_HEADER = "X-Alpine-Target"

CODE_PARAMETER = "codigo"
FILTER_PARAMETERS = {
    "situacao": "situation",
    "tipo": "kind",
    "origem": "origin",
    "prioridade": "priority",
    "alcada": "authority",
    "busca": "search",
}

# Reading the module is enough to see the register; registering and cancelling is writing.
READ_ACCESS = Access(module=MODULE)
WRITE_ACCESS = Access(module=MODULE, permission=Permission.WRITE)

SITUATION_OPTIONS = (
    (service.SITUATION_GROUP_OPEN, "Situação: em aberto"),
    (service.SITUATION_GROUP_ANALYSIS, "Situação: em análise"),
    (service.SITUATION_GROUP_APPROVED, "Situação: aprovadas"),
    *((situation, situation) for situation in models.CHANGE_SITUATIONS),
)

PROJECT_LABEL_FIELD = "projeto_rotulo"

NEW_FORM_FIELDS = (
    PROJECT_LABEL_FIELD,
    validation.FIELD_TITLE,
    validation.FIELD_KIND,
    validation.FIELD_ORIGIN,
    validation.FIELD_PRIORITY,
    validation.FIELD_REQUEST_DATE,
    validation.FIELD_DESCRIPTION,
    validation.FIELD_EARLY_EXECUTION,
    validation.FIELD_EMERGENCY_START,
    validation.FIELD_EMERGENCY_JUSTIFICATION,
)


# ── The register ─────────────────────────────────────────────────────────


@bp.route(route=REGISTER_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def change_register(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Registro de mudanças: KPIs, filters and the table (or only the two blocks a filter replaces)."""
    filters = _filters_of(req)
    overview = service.register_overview(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=calendario.today(),
    )
    template = REGISTER_PARTS_TEMPLATE if _asks_for_parts(req) else REGISTER_TEMPLATE
    return AlpineAjaxResponse(
        template_name=template,
        context=_register_context(overview, filters, context),
        request=req,
    )


@bp.route(route=REGISTER_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def change_register_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the register, with the filters of the screen."""
    return excel_response(_register_document(req, session, context))


@bp.route(route=REGISTER_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def change_register_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the register: what the PDF button mounts and prints."""
    return printable_response(_register_document(req, session, context), req)


def _register_document(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    filters = _filters_of(req)
    today = calendario.today()
    overview = service.register_overview(
        session, user=context.user, scope=context.scope, filters=filters, reference_date=today
    )
    return export.register_document(
        overview,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        filters=filters,
        today=today,
    )


def _filters_of(req: func.HttpRequest) -> service.ChangeFilter:
    values = {
        field: (req.params.get(parameter) or "").strip() or None
        for parameter, field in FILTER_PARAMETERS.items()
    }
    return service.ChangeFilter(**values)


def _asks_for_parts(req: func.HttpRequest) -> bool:
    targets = (req.headers.get(TARGET_HEADER) or "").split()
    return all(block in targets for block in FILTERED_BLOCKS)


def _query_of(filters: service.ChangeFilter) -> str:
    """The filters as the address of the exports carries them: ``?situacao=abertas&busca=pipe``."""
    pairs = {
        parameter: getattr(filters, field)
        for parameter, field in FILTER_PARAMETERS.items()
        if getattr(filters, field)
    }
    return f"?{urlencode(pairs)}" if pairs else ""


def _register_context(
    overview: service.RegisterOverview, filters: service.ChangeFilter, context: RequestContext
) -> dict[str, Any]:
    count = len(overview.rows)
    return {
        "cartoes": presentation.kpi_cards(overview),
        "linhas": overview.rows,
        "total_no_escopo": overview.total_in_scope,
        "portfolio": overview.is_portfolio,
        "filtros": filters,
        "consulta": _query_of(filters),
        "contagem": presentation.plural(
            count, "solicitação encontrada", "solicitações encontradas"
        ),
        "pode_registrar": rbac.can(context.user, Permission.WRITE),
        "opcoes_situacao": SITUATION_OPTIONS,
        "tipos": models.CHANGE_TYPES,
        "origens": models.CHANGE_ORIGINS,
        "prioridades": models.CHANGE_PRIORITIES,
        "alcadas": models.CHANGE_AUTHORITIES,
        "excel_url": f"/api/{REGISTER_EXCEL_ROUTE}",
        "pdf_url": f"/api/{REGISTER_PRINTABLE_ROUTE}",
        **_presenters(),
    }


def _presenters() -> dict[str, Any]:
    """The functions the fragments call to write a situation, a priority, a cost and a term."""
    return {
        "pill_situacao": presentation.situation_pill,
        "pill_prioridade": presentation.priority_pill,
        "texto_custo": presentation.cost_text,
        "texto_prazo": presentation.term_text,
    }


# ── The new request ──────────────────────────────────────────────────────


def _new_form_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The form again, filled with what the person typed and the message under each field."""
    if not isinstance(error, InvalidDataError):
        return None
    values = {field: req.form.get(field) or "" for field in NEW_FORM_FIELDS}
    return _new_form_response(
        req,
        values=values,
        today=calendario.today(),
        errors=_field_messages(error),
        status_code=422,
    )


def _field_messages(error: InvalidDataError) -> dict[str, str]:
    """The message of each field; a message that is not of a field goes under ``geral``."""
    if isinstance(error.detail, Mapping):
        return {field: message for field, message in error.detail.items() if message}
    return {"geral": str(error.detail)}


def _new_form_response(
    req: func.HttpRequest,
    *,
    values: Mapping[str, str],
    today: date,
    errors: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=NEW_TEMPLATE,
        context={
            "valores": values,
            "erros": errors or {},
            "tipos": models.CHANGE_TYPES,
            "origens": models.CHANGE_ORIGINS,
            "prioridades": models.CHANGE_PRIORITIES,
            "prioridade_emergencial": models.PRIORITY_EMERGENCY,
            "hoje": today.isoformat(),
            "action": f"/api/{REGISTER_ROUTE}",
        },
        request=req,
        status_code=status_code,
    )


@bp.route(route=NEW_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def new_change_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the new request, for the project of the scope (a Portfólio asks for the project)."""
    project = configuracoes.find_project(session, context.scope.require_project())
    today = calendario.today()
    label = f"{project.code} · {project.name}" if project else ""
    return _new_form_response(
        req,
        values={validation.FIELD_REQUEST_DATE: today.isoformat(), PROJECT_LABEL_FIELD: label},
        today=today,
    )


@bp.route(route=REGISTER_ROUTE, methods=["POST"])
@fragment_route(on_error=_new_form_error, access=WRITE_ACCESS)
def register_change(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the request (HU-125): it gets the number of the project and goes to its ficha."""
    created = service.create_change(
        session,
        user=context.user,
        scope=context.scope,
        form=req.form,
        reference_date=calendario.today(),
    )
    return redirect_to(_sheet_address(created.code, created.project_id))


# ── The ficha ────────────────────────────────────────────────────────────


@bp.route(route=SHEET_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def change_sheet(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The ficha of the change: stage bar and the five tabs, in reading."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    sheet = service.find_change_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        return AlpineAjaxResponse(
            template_name=NOT_FOUND_TEMPLATE, context={}, request=req, status_code=404
        )
    return AlpineAjaxResponse(
        template_name=SHEET_TEMPLATE,
        context=_sheet_context(
            sheet,
            code,
            pode_gerir=rbac.can(context.user, Permission.MANAGE),
            pode_escrever=rbac.can(context.user, Permission.WRITE),
        ),
        request=req,
    )


@bp.route(route=SHEET_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def change_sheet_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the ficha."""
    return excel_response(_sheet_document(req, session, context))


@bp.route(route=SHEET_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def change_sheet_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the ficha."""
    return printable_response(_sheet_document(req, session, context), req)


def _sheet_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    today = calendario.today()
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    sheet = service.find_change_sheet(session, user=context.user, code=code, reference_date=today)
    if sheet is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return export.sheet_document(
        sheet,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


def _sheet_context(
    sheet: service.ChangeSheet, code: str, *, pode_gerir: bool, pode_escrever: bool
) -> dict[str, Any]:
    query = urlencode({CODE_PARAMETER: code})
    change = sheet.change
    pending = calculations.is_emergency_pending(
        emergency=change.emergency,
        has_decision=sheet.decision is not None,
        situation=change.situation,
    )
    return {
        "ficha": sheet,
        "etapas": _stage_bar(sheet),
        "pode_gerir": pode_gerir,
        "pode_escrever": pode_escrever,
        "ratificacao_pendente": pending,
        "ratificacao_vencida": calculations.is_ratification_overdue(
            pending=pending,
            due_date=sheet.ratification_due,
            reference_date=calendario.today(),
        ),
        "excel_url": f"/api/{SHEET_EXCEL_ROUTE}?{query}",
        "pdf_url": f"/api/{SHEET_PRINTABLE_ROUTE}?{query}",
        "cancelar_url": f"/api/{CANCEL_ROUTE}?{query}",
        "iniciar_analise_url": f"/api/{START_ANALYSIS_ROUTE}?{query}",
        "analise_url": f"/api/{IMPACT_ROUTE}?{query}",
        "decisao_url": f"/api/{DECISION_ROUTE}?{query}",
        "reapresentar_url": f"/api/{REOPEN_ROUTE}?{query}",
        "encerrar_url": f"/api/{CLOSING_ROUTE}?{query}",
        "eac_url": f"/financeiro/eac?projeto={sheet.change.project_id}",
        "anexos_url": f"/api/anexos?origem={service.ORIGIN_TABLE}&registro={sheet.change.id}",
        "tipo_emergencial": models.PRIORITY_EMERGENCY,
        **_presenters(),
    }


@dataclass(frozen=True)
class _Step:
    """A step of the stage bar: its name and where the change stands in relation to it."""

    name: str
    state: str


def _stage_bar(sheet: service.ChangeSheet) -> list[_Step]:
    """The five stages: done before the current one, current at it; a closed flow is done at the end."""
    names = [*calculations.STAGE_NAMES[:-1], sheet.final_stage_name]
    closed = not sheet.is_open
    steps = []
    for index, name in enumerate(names):
        last = index == len(names) - 1
        if index < sheet.stage or (closed and last):
            state = "feita"
        elif index == sheet.stage:
            state = "atual"
        else:
            state = "futura"
        steps.append(_Step(name=name, state=state))
    return steps


def _sheet_address(code: str, project_id: int) -> str:
    return f"{SHEET_PAGE}?codigo={quote(code)}&projeto={project_id}"


# ── The cancellation ─────────────────────────────────────────────────────


def _cancel_form_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The form again with the justification that was typed; a refusal (403) takes the common answer."""
    if isinstance(error, AccessDeniedError):
        return None
    values = {
        validation.FIELD_JUSTIFICATION: req.form.get(validation.FIELD_JUSTIFICATION) or "",
        validation.FIELD_VERSION: req.form.get(validation.FIELD_VERSION) or "",
    }
    errors = (
        _field_messages(error) if isinstance(error, InvalidDataError) else {"geral": str(error)}
    )
    return _cancel_form_response(
        req,
        code=(req.form.get(CODE_PARAMETER) or "").strip(),
        values=values,
        errors=errors,
        status_code=409 if not isinstance(error, InvalidDataError) else 422,
    )


def _cancel_form_response(
    req: func.HttpRequest,
    *,
    code: str,
    values: Mapping[str, str],
    errors: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=CANCEL_TEMPLATE,
        context={
            "codigo": code,
            "valores": values,
            "erros": errors or {},
            "action": f"/api/{CANCEL_ROUTE}",
        },
        request=req,
        status_code=status_code,
    )


@bp.route(route=CANCEL_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def cancel_change_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The cancellation form, for who may cancel the change now (403 or 422 say why not)."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    change = service.cancellable_change(session, user=context.user, code=code)
    return _cancel_form_response(
        req,
        code=change.code,
        values={validation.FIELD_VERSION: str(change.version)},
    )


@bp.route(route=CANCEL_ROUTE, methods=["POST"])
@fragment_route(on_error=_cancel_form_error, access=WRITE_ACCESS)
def cancel_change_request(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cancel the change with its justification (HU-125) and go back to its ficha."""
    code = (req.form.get(CODE_PARAMETER) or "").strip()
    change = service.cancel_change(
        session,
        user=context.user,
        code=code,
        form=req.form,
        reference_date=calendario.today(),
    )
    return redirect_to(_sheet_address(change.code, change.project_id))


# ── The analysis (ISSUE-024) ─────────────────────────────────────────────

IMPACT_FORM_ROWS = tuple(range(1, validation.TRANSFER_ROWS + 1))


def _start_form_response(
    req: func.HttpRequest,
    *,
    form: service.AnalysisStartForm,
    values: Mapping[str, str],
    errors: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=START_ANALYSIS_TEMPLATE,
        context={
            "codigo": form.change.code,
            "valores": values,
            "erros": errors or {},
            "pessoas": form.people,
            "prazo_dias": form.analysis_days,
            "action": f"/api/{START_ANALYSIS_ROUTE}",
        },
        request=req,
        status_code=status_code,
    )


@bp.route(route=START_ANALYSIS_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def start_analysis_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form that starts the analysis, with the usual deadline of the parameter."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    form = service.analysis_start_form(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    values = {
        validation.FIELD_DEADLINE: form.suggested_deadline.isoformat(),
        validation.FIELD_VERSION: str(form.change.version),
    }
    return _start_form_response(req, form=form, values=values)


@bp.route(route=START_ANALYSIS_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def start_analysis(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Start the analysis (HU-126) and go back to the ficha; a 422 gives the form back filled."""
    code = (req.form.get(CODE_PARAMETER) or "").strip()
    today = calendario.today()
    try:
        change = service.start_analysis(
            session, user=context.user, code=code, form=req.form, reference_date=today
        )
    except InvalidDataError as error:
        form = service.analysis_start_form(
            session, user=context.user, code=code, reference_date=today
        )
        values = {
            field: req.form.get(field) or ""
            for field in (
                validation.FIELD_RESPONSIBLE,
                validation.FIELD_DEADLINE,
                validation.FIELD_VERSION,
            )
        }
        return _start_form_response(
            req, form=form, values=values, errors=_field_messages(error), status_code=422
        )
    return redirect_to(_sheet_address(change.code, change.project_id))


def _impact_form_response(
    req: func.HttpRequest,
    *,
    form: service.ImpactForm,
    values: Mapping[str, str],
    errors: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=IMPACT_TEMPLATE,
        context={
            "codigo": form.change.code,
            "tipo": form.change.kind,
            "valores": values,
            "erros": errors or {},
            "fontes": models.RESOURCE_SOURCES,
            "alcadas": models.CHANGE_AUTHORITIES,
            "reservas": models.RELEASE_RESERVES,
            "linhas": IMPACT_FORM_ROWS,
            "eh_remanejamento": form.is_reallocation,
            "eh_liberacao": form.is_release,
            "revisao": form.is_review,
            "limite_gerente": form.manager_limit_cents,
            "percentual_gerente": form.manager_limit_percent,
            "action": f"/api/{IMPACT_ROUTE}",
        },
        request=req,
        status_code=status_code,
    )


@bp.route(route=IMPACT_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def impact_analysis_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The impact analysis form, with what is already recorded when the analysis is being revised."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    form = service.impact_form(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    return _impact_form_response(req, form=form, values=form.values)


@bp.route(route=IMPACT_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def conclude_impact_analysis(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Conclude the impact analysis (HU-126) and go back to the ficha; a 422 gives the form back filled."""
    code = (req.form.get(CODE_PARAMETER) or "").strip()
    today = calendario.today()
    try:
        change = service.conclude_analysis(
            session, user=context.user, code=code, form=req.form, reference_date=today
        )
    except InvalidDataError as error:
        form = service.impact_form(session, user=context.user, code=code, reference_date=today)
        values = {field: req.form.get(field) or "" for field in req.form}
        return _impact_form_response(
            req, form=form, values=values, errors=_field_messages(error), status_code=422
        )
    return redirect_to(_sheet_address(change.code, change.project_id))


# ── The decision, the resubmission and the closing (ISSUE-025) ───────────


def _sheet_again(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    code: str,
    notice: str,
) -> func.HttpResponse:
    """A ficha refreshed behind the modal, with the toast of what happened."""
    sheet = service.find_change_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        return AlpineAjaxResponse(
            template_name=NOT_FOUND_TEMPLATE, context={}, request=req, status_code=404
        )
    return AlpineAjaxResponse(
        template_name=SHEET_TEMPLATE,
        context=_sheet_context(
            sheet,
            code,
            pode_gerir=rbac.can(context.user, Permission.MANAGE),
            pode_escrever=rbac.can(context.user, Permission.WRITE),
        ),
        request=req,
        target_id=SHEET_TARGET,
        toast=notice,
    )


def _decision_values(req: func.HttpRequest) -> dict[str, object]:
    """O formulário da decisão com os dois campos de lista como sequências."""
    values: dict[str, object] = dict(req.form)
    values[validation.FIELD_PARTICIPANTS] = req.form.getlist(validation.FIELD_PARTICIPANTS)
    values[validation.FIELD_ACTIONS] = req.form.getlist(validation.FIELD_ACTIONS)
    return values


def _decision_form_response(
    req: func.HttpRequest,
    *,
    form: service.DecisionForm,
    values: Mapping[str, object],
    errors: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=DECISION_TEMPLATE,
        context={
            "formulario": form,
            "valores": values,
            "erros": errors or {},
            "hoje": calendario.today().isoformat(),
            "action": f"/api/{DECISION_ROUTE}",
        },
        request=req,
        status_code=status_code,
    )


@bp.route(route=DECISION_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def decision_form_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The decision form: the quorum, the committee minutes and the suggested actions."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    form = service.decision_form(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    values: dict[str, object] = {
        validation.FIELD_DECISION_DATE: calendario.today().isoformat(),
        validation.FIELD_PARTICIPANTS: [str(person) for person in form.default_participants],
        validation.FIELD_ACTIONS: [action.key for action in form.actions],
        validation.FIELD_PLANNED: form.default_planned.isoformat(),
        validation.FIELD_VERSION: str(form.sheet.change.version),
    }
    return _decision_form_response(req, form=form, values=values)


@bp.route(route=DECISION_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def decide_change_request(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the decision (HU-127); a refusal gives the form back, with the message."""
    code = (req.form.get(CODE_PARAMETER) or "").strip()
    today = calendario.today()
    try:
        result = service.decide_change(
            session,
            user=context.user,
            code=code,
            form=_decision_values(req),
            reference_date=today,
        )
    except InvalidDataError as error:
        form = service.decision_form(session, user=context.user, code=code, reference_date=today)
        return _decision_form_response(
            req,
            form=form,
            values=_decision_values(req),
            errors=_field_messages(error),
            status_code=422,
        )
    notice = DECIDED_NOTICE
    if result.actions_created:
        notice += f" {result.actions_created} ação(ões) na Central."
    return _sheet_again(req, session, context, code=code, notice=notice)


def _reopen_form_response(
    req: func.HttpRequest,
    *,
    code: str,
    version: int | str | None,
    errors: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=REOPEN_TEMPLATE,
        context={
            "codigo": code,
            "versao": version,
            "erros": errors or {},
            "action": f"/api/{REOPEN_ROUTE}",
        },
        request=req,
        status_code=status_code,
    )


@bp.route(route=REOPEN_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def reopen_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The confirmation of the resubmission of a postponed request."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    sheet = service.find_change_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return _reopen_form_response(req, code=code, version=sheet.change.version)


@bp.route(route=REOPEN_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def reopen_request(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Reapresenta a solicitação adiada: volta à pauta e a decisão anterior fica no histórico."""
    code = (req.form.get(CODE_PARAMETER) or "").strip()
    try:
        change = service.resubmit_change(
            session, user=context.user, code=code, reference_date=calendario.today()
        )
    except InvalidDataError as error:
        return _reopen_form_response(
            req,
            code=code,
            version=req.form.get(validation.FIELD_VERSION),
            errors=_field_messages(error),
            status_code=422,
        )
    return _sheet_again(req, session, context, code=change.code, notice=RESUBMITTED_NOTICE)


def _closing_form_response(
    req: func.HttpRequest,
    *,
    form: service.ClosingForm,
    values: Mapping[str, object],
    errors: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=CLOSING_TEMPLATE,
        context={
            "formulario": form,
            "valores": values,
            "erros": errors or {},
            "hoje": calendario.today().isoformat(),
            "tipos_licao": lessons_models.LESSON_TYPES,
            "fases_licao": lessons_models.LESSON_PHASES,
            "action": f"/api/{CLOSING_ROUTE}",
        },
        request=req,
        status_code=status_code,
    )


@bp.route(route=CLOSING_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def closing_form_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The closing form: the conference of the implementation and the confirmations due."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    form = service.closing_form(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    values: dict[str, object] = {
        validation.FIELD_DECISION_DATE: calendario.today().isoformat(),
        validation.FIELD_VERSION: str(form.sheet.change.version),
    }
    return _closing_form_response(req, form=form, values=values)


@bp.route(route=CLOSING_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def close_change_request(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Encerra a mudança (HU-128); sem ação aberta e com as confirmações devidas."""
    code = (req.form.get(CODE_PARAMETER) or "").strip()
    today = calendario.today()
    try:
        result = service.close_change(
            session,
            user=context.user,
            code=code,
            form=req.form,
            reference_date=today,
        )
    except InvalidDataError as error:
        form = service.closing_form(session, user=context.user, code=code, reference_date=today)
        return _closing_form_response(
            req,
            form=form,
            values={field: req.form.get(field) or "" for field in req.form},
            errors=_field_messages(error),
            status_code=422,
        )
    notice = CLOSED_NOTICE
    if result.lesson_code:
        notice += f" Lição {result.lesson_code} criada em Rascunho."
    return _sheet_again(req, session, context, code=result.code, notice=notice)
