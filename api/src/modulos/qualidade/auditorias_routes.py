"""Routes of Auditorias, the third screen of the Quality module (ISSUE-070, D14).

Prefix ``/api/qualidade/auditorias``. The screen is one fragment, ``auditorias-conteudo``:
the five KPIs, the filters (search, situation and type) and the programme with the result
column and the actions. Everything that changes the view (a filter, a search) is a plain GET
of the same route with the filters in the query string, answered with the same fragment. The
ficha and the forms (plan, reschedule and result) open in the modal
(``auditorias-modal-corpo``): a GET draws them, a POST saves and answers the refreshed list; a
refusal (422, 409, 403) answers the form again, filled in, in the modal. In the Portfólio the
form asks for the project before opening.

* ``GET  auditorias``                                the screen (filters by query);
* ``GET  auditorias/excel`` and ``auditorias/imprimivel``  the two exports of what the screen shows;
* ``GET  auditorias/{codigo}/ficha``                 the ficha with the findings and the reschedules;
* ``GET/POST auditorias/nova``                       Planejar auditoria;
* ``GET/POST auditorias/{codigo}/reprogramacao``     Reprogramar (só Planejada, com justificativa);
* ``GET/POST auditorias/{codigo}/resultado``         Registrar o resultado (cada NC abre RNC).

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
from src.modulos.configuracoes import service as configuracoes
from src.modulos.qualidade import export, service, validation
from src.modulos.qualidade.service import AuditLine, AuditSummary
from src.modulos.qualidade.validation import (
    AuditFilters,
    AuditFindingInput,
    AuditInput,
    AuditResultInput,
)

bp = func.Blueprint()

MODULE = "qualidade"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

CONTENT_TARGET = "auditorias-conteudo"
MODAL_TARGET = "auditorias-modal-corpo"
ROUTE = "/api/qualidade/auditorias"

SCREEN_TEMPLATE = "qualidade/auditorias.html"
PROJECT_TEMPLATE = "qualidade/auditorias_projeto.html"
FORM_TEMPLATE = "qualidade/auditorias_form.html"
FICHA_TEMPLATE = "qualidade/auditorias_ficha.html"
RESULT_TEMPLATE = "qualidade/auditorias_resultado.html"

AUDIT_SAVED_NOTICE = "Auditoria {code} planejada."
AUDIT_RESCHEDULED_NOTICE = "Auditoria reprogramada."
AUDIT_UPDATED_NOTICE = "Auditoria atualizada."
AUDIT_RESULT_NOTICE = "Resultado registrado."
CHOOSE_PROJECT_MESSAGE = "Escolha o projeto da auditoria."


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


def _form_filters(form: Mapping[str, str]) -> AuditFilters:
    """The filters of the list as the form carried them, not the fields of the form itself."""
    return validation.parse_audit_filters(dict(parse_qsl(form.get("consulta", ""))))


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


@bp.route(route="qualidade/auditorias", methods=["GET"])
@fragment_route(access=READ)
def audit_list_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The screen: KPIs, the filters and the programme of the query."""
    return _screen(req, session, context, filters=validation.parse_audit_filters(req.params))


@bp.route(route="qualidade/auditorias/excel", methods=["GET"])
@file_route(access=READ)
def audit_list_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the screen: the KPIs and the programme of the filter."""
    return excel_response(_document(req, session, context))


@bp.route(route="qualidade/auditorias/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def audit_list_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


# ── Ficha ────────────────────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/auditorias/{codigo}/ficha", methods=["GET"])
@fragment_route(access=READ)
def audit_sheet_fragment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The ficha of one audit: the record, the findings and the reschedules."""
    line = _audit_line(session, context, req)
    if line is None:
        return _not_found(req)
    consulta = req.params.get("consulta", "")
    return AlpineAjaxResponse(
        template_name=FICHA_TEMPLATE,
        context={
            "auditoria": line,
            "consulta": consulta,
            "parametro_consulta": urlencode({"consulta": consulta}) if consulta else "",
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "formatar_data": _format_date,
            "link_rnc": lambda code: origin_links.link_to_screen("qualidade/rnc", busca=code),
        },
        request=req,
        target_id=MODAL_TARGET,
    )


# ── Planejar e reprogramar ───────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/auditorias/nova", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def audit_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new audit; in the Portfólio the project is asked first."""
    project_id = context.scope.project_id or validation.parse_id(req.params.get("projeto"))
    if project_id is None:
        return _project_choice(req, session, destino=f"{ROUTE}/nova")
    return _audit_form(
        req, session, state=_AuditFormState(project_id=project_id, values={}), code=None
    )


@bp.route(route="qualidade/auditorias/nova", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def audit_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Plan the audit and answer the refreshed list, or the form with its messages."""
    project_id = context.scope.project_id or validation.parse_id(req.form.get("projeto"))
    if project_id is None:
        raise InvalidDataError(CHOOSE_PROJECT_MESSAGE)
    data = _audit_input(req.form, project_id=project_id)
    outcome: list[service.AuditResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.create_audit(
                session, user=context.user, data=data, reference_date=calendario.today()
            )
        ),
    )
    if error is not None or not outcome:
        return _audit_form(
            req,
            session,
            state=_AuditFormState(
                project_id=project_id, values=dict(req.form), errors=_field_errors(error)
            ),
            code=None,
            status=_error_status(error) if error else 200,
        )
    return _screen(
        req,
        session,
        context,
        filters=_form_filters(req.form),
        after=AUDIT_SAVED_NOTICE.format(code=outcome[0].code),
    )


@bp.route(route="qualidade/auditorias/{codigo}/reprogramacao", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def audit_reschedule_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the reschedule, filled in with the audit in force."""
    line = _audit_line(session, context, req)
    if line is None:
        return _not_found(req)
    return _audit_form(
        req,
        session,
        state=_AuditFormState(project_id=line.project_id, values=_audit_values(line)),
        code=line.code,
    )


@bp.route(route="qualidade/auditorias/{codigo}/reprogramacao", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def audit_reschedule_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the edit; a changed date leaves the reschedule fact and answers the refreshed list."""
    line = _audit_line(session, context, req)
    if line is None:
        return _not_found(req)
    data = _audit_input(req.form, project_id=line.project_id)
    outcome: list[service.AuditResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.save_audit(
                session,
                user=context.user,
                code=line.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _audit_form(
            req,
            session,
            state=_AuditFormState(
                project_id=line.project_id, values=dict(req.form), errors=_field_errors(error)
            ),
            code=line.code,
            status=_error_status(error) if error else 200,
        )
    notice = AUDIT_RESCHEDULED_NOTICE if outcome[0].rescheduled else AUDIT_UPDATED_NOTICE
    return _screen(req, session, context, filters=_form_filters(req.form), after=notice)


def _audit_form(
    req: func.HttpRequest,
    session: Session,
    *,
    state: _AuditFormState,
    code: str | None,
    status: int = 200,
) -> func.HttpResponse:
    """The form of the audit, empty or filled in with the record or the messages of a refusal."""
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={
            "projeto": configuracoes.find_project(session, state.project_id),
            "projeto_id": state.project_id,
            "codigo": code,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "tipos": validation.AUDIT_TYPES,
            "empresas": configuracoes.list_company_options(session),
            "pessoas": configuracoes.list_person_options(session),
            "referencia": calendario.today().isoformat(),
            "consulta": _consulta_of(req),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


# ── Registrar o resultado ────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/auditorias/{codigo}/resultado", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def audit_result_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the result of a planned audit."""
    line = _audit_line(session, context, req)
    if line is None:
        return _not_found(req)
    today = calendario.today()
    default_date = line.audit_date if line.audit_date <= today else today
    return _result_fragment(
        req,
        session,
        line=line,
        values={"data": default_date.isoformat()},
        errors={},
    )


@bp.route(route="qualidade/auditorias/{codigo}/resultado", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def audit_result_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the result; a Não conformidade opens the RNC in the same transaction (D9)."""
    line = _audit_line(session, context, req)
    if line is None:
        return _not_found(req)
    data = _result_input(req.form)
    outcome: list[service.AuditOutcome] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.record_result(
                session,
                user=context.user,
                code=line.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _result_fragment(
            req,
            session,
            line=line,
            values=dict(req.form),
            errors=_field_errors(error),
            status=_error_status(error) if error else 200,
        )
    result = outcome[0]
    notice = AUDIT_RESULT_NOTICE
    if result.rnc_codes:
        plural = "RNC aberta" if len(result.rnc_codes) == 1 else "RNCs abertas"
        notice = f"{notice} {len(result.rnc_codes)} {plural}: {', '.join(result.rnc_codes)}."
    return _screen(
        req,
        session,
        context,
        filters=_form_filters(req.form),
        after=notice,
        after_tipo="aviso" if result.rnc_codes else "ok",
    )


def _result_fragment(
    req: func.HttpRequest,
    session: Session,
    *,
    line: AuditLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    """The result form of the audit, with the conclusion calculated live in the screen."""
    today = calendario.today()
    return AlpineAjaxResponse(
        template_name=RESULT_TEMPLATE,
        context={
            "auditoria": line,
            "valores": dict(values),
            "erros": dict(errors),
            "visiveis": _visible_findings(values),
            "max_constatacoes": validation.MAX_FINDINGS,
            "tipos_constatacao": validation.FINDING_TYPES,
            "disciplinas": configuracoes.list_discipline_names(session),
            "severidades": validation.SEVERITIES,
            "meta": _meta_pct(session, today),
            "referencia": today.isoformat(),
            "consulta": _consulta_of(req),
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
    filters: AuditFilters,
    after: str | None = None,
    after_tipo: str = "ok",
) -> func.HttpResponse:
    """The programme fragment for the filters, with an optional toast of a save."""
    today = calendario.today()
    listing = service.list_audits(
        session, user=context.user, scope=context.scope, filters=filters, reference_date=today
    )
    meta = _meta_pct(session, today)
    query = _query_string(filters)
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={
            "listagem": listing,
            "filtros": filters,
            "kpis": _kpi_cards(listing.summary, meta),
            "meta": meta,
            "consulta": query,
            "parametro_consulta": urlencode({"consulta": query}) if query else "",
            "url_excel": _address(filters, path=f"{ROUTE}/excel"),
            "url_pdf": _address(filters, path=f"{ROUTE}/imprimivel"),
            "portfolio": context.scope.is_portfolio,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "tipos": validation.AUDIT_TYPES,
            "situacoes": (
                validation.AUDIT_SITUATIONS[0],
                validation.AUDIT_SITUATIONS[1],
                validation.AUDIT_FILTER_OVERDUE,
            ),
            "link_limpar": _address(AuditFilters()),
            "tem_filtro": filters != AuditFilters(),
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
    filters = validation.parse_audit_filters(req.params)
    return export.build_auditorias_document(
        listing=service.list_audits(
            session, user=context.user, scope=context.scope, filters=filters, reference_date=today
        ),
        filters=filters,
        scope=context.scope,
        projects=configuracoes.list_project_details(session),
        today=today,
        meta_pct=_meta_pct(session, today),
    )


def _meta_pct(session: Session, reference_date: date) -> Decimal:
    """The conformity target of the audits, from the parameters in force."""
    return Decimal(
        str(
            service.parameters(session, reference_date=reference_date)[
                "metaConformidadeAuditoriaPct"
            ]
        )
    )


def _kpi_cards(summary: AuditSummary, meta: Decimal) -> list[KpiCard]:
    next_audit = summary.next_audit
    if summary.conformity is None:
        conformity_value, conformity_unit, conformity_tone = "·", "", "info"
    else:
        conformity_value = _decimal_text(summary.conformity)
        conformity_unit = "%"
        conformity_tone = "ok" if summary.conformity >= meta else "warn"
    return [
        KpiCard(
            label="Aderência ao programa",
            icon="calendarClock",
            tone="warn" if summary.overdue else "ok",
            value="·" if summary.adherence is None else _decimal_text(summary.adherence),
            unit="" if summary.adherence is None else "%",
            reference="Meta: 100%",
            footer=f"{summary.done} de {summary.due} previstas até hoje",
        ),
        KpiCard(
            label="Auditorias atrasadas",
            icon="clock",
            tone="erro" if summary.overdue else "ok",
            value=str(summary.overdue),
            unit="",
            reference="Esperado: 0",
            footer="data planejada vencida sem resultado",
        ),
        KpiCard(
            label="Conformidade nas auditorias",
            icon="checkCircle",
            tone=conformity_tone,
            value=conformity_value,
            unit=conformity_unit,
            reference=f"Meta: {meta:.0f}%",
            footer=f"{summary.conforming_items} de {summary.verified_items} itens",
        ),
        KpiCard(
            label="Não conformidades de auditoria",
            icon="warning",
            tone="warn" if summary.open_nc else "ok",
            value=str(summary.nc),
            unit="",
            reference="Esperado: 0",
            footer=(
                f"{summary.open_nc} RNC em aberto"
                if summary.open_nc == 1
                else f"{summary.open_nc} RNCs em aberto"
            ),
        ),
        KpiCard(
            label="Próxima auditoria",
            icon="calendar",
            tone="info",
            value=(
                f"{next_audit.audit_date.day:02d}/{next_audit.audit_date.month:02d}"
                if next_audit is not None
                else "·"
            ),
            unit=str(next_audit.audit_date.year) if next_audit is not None else "",
            reference=(
                f"Linha de base: {_format_date(next_audit.baseline_date)}"
                if next_audit is not None
                else "Linha de base: ·"
            ),
            footer=(
                f"{next_audit.code} · {next_audit.auditee_name}"
                if next_audit is not None
                else "nenhuma planejada"
            ),
        ),
    ]


def _query_string(filters: AuditFilters) -> str:
    values: dict[str, str] = {}
    if filters.search:
        values["busca"] = filters.search
    if filters.situation:
        values["situacao"] = filters.situation
    if filters.audit_type:
        values["tipo"] = filters.audit_type
    return urlencode(values)


def _address(filters: AuditFilters, *, path: str = ROUTE, **overrides: str) -> str:
    """The address of the screen (or of an export) with the filters and the overrides."""
    updated = replace(filters, **overrides) if overrides else filters
    query = _query_string(updated)
    return f"{path}?{query}" if query else path


@dataclass(frozen=True)
class _AuditFormState:
    """What the form of the audit remembers: the project, what was typed and the messages."""

    project_id: int
    values: Mapping[str, str]
    errors: Mapping[str, str] = field(default_factory=dict)


def _audit_input(form: Mapping[str, str], *, project_id: int) -> AuditInput:
    return AuditInput(
        project_id=project_id,
        audit_type=form.get("tipo", ""),
        auditee_id=validation.parse_id(form.get("auditadoId")),
        lead_auditor_id=validation.parse_id(form.get("auditorId")),
        scope=form.get("escopo", ""),
        criterion=form.get("criterio", ""),
        audit_date=validation.parse_date(form.get("data")),
        justification=form.get("justificativa", ""),
        version=form.get("versao"),
    )


def _result_input(form: Mapping[str, str]) -> AuditResultInput:
    return AuditResultInput(
        performed_on=validation.parse_date(form.get("data")),
        items_verified=validation.parse_count(form.get("itensVerificados")),
        items_conforming=validation.parse_count(form.get("itensConformes")),
        summary=form.get("resumo", ""),
        findings=_findings_input(form),
        version=form.get("versao"),
    )


def _findings_input(form: Mapping[str, str]) -> tuple[AuditFindingInput, ...]:
    """The finding blocks of the form, in order; a block with nothing filled is left out."""
    result: list[AuditFindingInput] = []
    for position in range(1, validation.MAX_FINDINGS + 1):
        prefix = f"constatacao{position}_"
        finding_type = form.get(prefix + "tipo", "")
        description = form.get(prefix + "descricao", "")
        requirement = form.get(prefix + "requisito", "")
        discipline = form.get(prefix + "disciplina", "")
        severity = form.get(prefix + "severidade", "")
        if not any(
            part.strip() for part in (finding_type, description, requirement, discipline, severity)
        ):
            continue
        result.append(
            AuditFindingInput(
                finding_type=finding_type,
                description=description,
                requirement=requirement,
                discipline=discipline,
                severity=severity,
            )
        )
    return tuple(result)


def _audit_values(line: AuditLine) -> dict[str, str]:
    """The audit as the form values, so the reschedule opens filled in."""
    return {
        "tipo": line.audit_type,
        "auditadoId": str(line.auditee_id),
        "auditorId": str(line.lead_auditor_id),
        "escopo": line.scope,
        "criterio": line.criterion,
        "data": line.audit_date.isoformat(),
        "versao": str(line.version),
    }


def _visible_findings(values: Mapping[str, str]) -> int:
    """How many finding blocks the form shows: the filled ones, at least one."""
    filled = 0
    for position in range(1, validation.MAX_FINDINGS + 1):
        if any(
            (values.get(f"constatacao{position}_{suffix}") or "").strip()
            for suffix in ("tipo", "descricao", "requisito", "disciplina", "severidade")
        ):
            filled = position
    return max(1, filled)


def _audit_line(
    session: Session, context: RequestContext, req: func.HttpRequest
) -> AuditLine | None:
    code = req.route_params.get("codigo") or ""
    return service.audit_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )


def _not_found(req: func.HttpRequest) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": [service.AUDIT_NOT_FOUND_MESSAGE]},
        request=req,
        target_id=MODAL_TARGET,
        status_code=404,
        toast=service.AUDIT_NOT_FOUND_MESSAGE,
        toast_tipo="aviso",
    )


def _format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _decimal_text(value: Decimal) -> str:
    """A decimal as the screen writes it: one decimal place, comma, no trailing zeros."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")
