"""Route blueprint of the lessons learned of Governança (ISSUE-027): the Acervo and the flow.

Every route declares its ``Access`` (D14) and only reads the request, calls the facade
(``lessons_service``) and draws the answer; the rules are in ``lessons_calculations``,
``lessons_validation`` and ``lessons_service``.

* ``GET /api/governanca/licoes`` is the acervo: the whole fragment on the first load and, when a filter
  is applied (the form asks for ``licoes-resumo`` and ``licoes-cartoes``), only those two blocks;
  ``POST`` registers a lesson (302 to the acervo with the lesson open, 422 gives the form back);
* ``GET /api/governanca/licoes/excel`` and ``/imprimivel`` are the two exports of the acervo;
* ``GET /api/governanca/licoes/nova`` is the form of the new lesson (the Portfólio asks for the project);
* ``GET /api/governanca/licoes/ver?codigo=`` is the sheet of a lesson (404 when it does not exist);
* ``GET`` and ``POST .../editar`` edit a draft; ``POST .../enviar`` sends it to validation;
* ``GET`` and ``POST .../validar`` validate, validate and publish, or return it; ``POST .../publicar``
  publishes a validated lesson (403 for who is not a Gestor, and for the author who validates);
* ``GET`` and ``POST .../aplicar`` register the reuse in a project and, when asked, open the action.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import InvalidDataError
from src.core.excel import excel_response
from src.core.export_document import Document
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse, redirect_to
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import lessons_calculations as calc
from src.modulos.governanca import lessons_export as export
from src.modulos.governanca import lessons_models as lm
from src.modulos.governanca import lessons_presentation as presentation
from src.modulos.governanca import lessons_service as service
from src.modulos.governanca import lessons_validation as validation

bp = func.Blueprint()

MODULE = service.MODULE

PAGE_ROUTE = "governanca/licoes"
EXCEL_ROUTE = "governanca/licoes/excel"
PRINTABLE_ROUTE = "governanca/licoes/imprimivel"
NEW_ROUTE = "governanca/licoes/nova"
VIEW_ROUTE = "governanca/licoes/ver"
EDIT_ROUTE = "governanca/licoes/editar"
SEND_ROUTE = "governanca/licoes/enviar"
VALIDATE_ROUTE = "governanca/licoes/validar"
PUBLISH_ROUTE = "governanca/licoes/publicar"
APPLY_ROUTE = "governanca/licoes/aplicar"
PAGE_ADDRESS = "/governanca/licoes"

PAGE_TEMPLATE = "governanca/licoes.html"
PARTS_TEMPLATE = "governanca/licoes_partes.html"
VIEW_TEMPLATE = "governanca/licao_ver.html"
NOT_FOUND_TEMPLATE = "governanca/licao_nao_encontrada.html"
FORM_TEMPLATE = "governanca/licao_form.html"
VALIDATE_TEMPLATE = "governanca/licao_validar.html"
APPLY_TEMPLATE = "governanca/licao_aplicar.html"

FILTERED_BLOCKS = ("licoes-resumo", "licoes-cartoes")
TARGET_HEADER = "X-Alpine-Target"
CODE_PARAMETER = "codigo"
FILTER_PARAMETERS = {
    "busca": "search",
    "tipo": "kind",
    "situacao": "situation",
    "fase": "phase",
    "area": "area",
    "disciplina": "discipline",
    "origem": "origin",
    "aplicabilidade": "applicability",
}

READ_ACCESS = Access(module=MODULE)
WRITE_ACCESS = Access(module=MODULE, permission=Permission.WRITE)

LESSON_FORM_FIELDS = (
    validation.FIELD_TITLE,
    validation.FIELD_KIND,
    validation.FIELD_PHASE,
    validation.FIELD_AREA,
    validation.FIELD_DISCIPLINE,
    validation.FIELD_ORIGIN,
    validation.FIELD_ORIGIN_REF,
    validation.FIELD_WHAT_HAPPENED,
    validation.FIELD_CAUSE,
    validation.FIELD_TERM_DAYS,
    validation.FIELD_COST,
    validation.FIELD_RECOMMENDATION,
    validation.FIELD_KEYWORDS,
    validation.FIELD_APPLICABILITY,
    validation.FIELD_VERSION,
)
DECISION_FORM_FIELDS = (
    validation.FIELD_RESULT,
    validation.FIELD_APPLICABILITY,
    validation.FIELD_COMMENT,
    validation.FIELD_VERSION,
)
APPLICATION_FORM_FIELDS = (
    validation.FIELD_PROJECT,
    validation.FIELD_DATE,
    validation.FIELD_HOW,
    validation.FIELD_GENERATE,
    validation.FIELD_RESPONSIBLE,
    validation.FIELD_PLANNED,
)


@dataclass(frozen=True)
class FormState:
    """What a form fragment prints: the lesson it is about, the values, the messages and the status."""

    code: str
    values: Mapping[str, str]
    errors: Mapping[str, str] = field(default_factory=dict)
    status_code: int = 200


@dataclass(frozen=True)
class KickoffButton:
    """A button of the kickoff checklist: a phase, its published lessons and whether it is on."""

    phase: str
    count: int
    active: bool


# ── The acervo ───────────────────────────────────────────────────────────


@bp.route(route=PAGE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def lesson_acervo(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Acervo de lições: kickoff checklist, filters and the cards (or the two blocks a filter replaces)."""
    filters = _filters_of(req)
    acervo = service.acervo(session, user=context.user, scope=context.scope, filters=filters)
    template = PARTS_TEMPLATE if _asks_for_parts(req) else PAGE_TEMPLATE
    return AlpineAjaxResponse(
        template_name=template,
        context=_acervo_context(session, acervo, filters, context),
        request=req,
    )


@bp.route(route=EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def lesson_acervo_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the acervo, with the filters of the screen."""
    return excel_response(_document(req, session, context))


@bp.route(route=PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def lesson_acervo_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the acervo: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    filters = _filters_of(req)
    acervo = service.acervo(session, user=context.user, scope=context.scope, filters=filters)
    return export.acervo_document(
        acervo,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        filters=filters,
        today=calendario.today(),
    )


def _filters_of(req: func.HttpRequest) -> service.LessonFilter:
    values = {
        field: (req.params.get(parameter) or "").strip() or None
        for parameter, field in FILTER_PARAMETERS.items()
    }
    return service.LessonFilter(**values)


def _asks_for_parts(req: func.HttpRequest) -> bool:
    targets = (req.headers.get(TARGET_HEADER) or "").split()
    return all(block in targets for block in FILTERED_BLOCKS)


def _query_of(filters: service.LessonFilter) -> str:
    """The filters as the address of the exports carries them: ``?situacao=Publicada&busca=solda``."""
    pairs = {
        parameter: getattr(filters, field)
        for parameter, field in FILTER_PARAMETERS.items()
        if getattr(filters, field)
    }
    return f"?{urlencode(pairs)}" if pairs else ""


def _acervo_context(
    session: Session,
    acervo: service.Acervo,
    filters: service.LessonFilter,
    context: RequestContext,
) -> dict[str, Any]:
    project = (
        configuracoes.find_project(session, context.scope.project_id)
        if context.scope.project_id is not None
        else None
    )
    options = service.form_options(session, user=context.user)
    return {
        "linhas": acervo.rows,
        "total_no_escopo": acervo.total_in_scope,
        "portfolio": acervo.is_portfolio,
        "linha_do_escopo": presentation.scope_line(
            is_portfolio=acervo.is_portfolio,
            project_code=project.code if project else "",
            own=acervo.counts.own,
            corporate=acervo.counts.corporate,
        ),
        "kickoff": [
            KickoffButton(
                phase=phase,
                count=count,
                active=filters.phase == phase and filters.situation == lm.SITUATION_PUBLISHED,
            )
            for phase, count in acervo.published_by_phase.items()
        ],
        "situacao_publicada": lm.SITUATION_PUBLISHED,
        "filtros": filters,
        "consulta": _query_of(filters),
        "contagem": presentation.plural(len(acervo.rows), "lição encontrada", "lições encontradas"),
        "pode_registrar": rbac.can(context.user, Permission.WRITE),
        "tipos": lm.LESSON_TYPES,
        "situacoes": lm.LESSON_SITUATIONS,
        "fases": lm.LESSON_PHASES,
        "areas": lm.LESSON_AREAS,
        "disciplinas": options.disciplines,
        "origens": [(origin, calc.origin_label(origin)) for origin in lm.LESSON_ORIGINS],
        "aplicabilidades": lm.LESSON_APPLICABILITIES,
        "excel_url": f"/api/{EXCEL_ROUTE}",
        "pdf_url": f"/api/{PRINTABLE_ROUTE}",
        **_presenters(),
    }


def _presenters() -> dict[str, Any]:
    """The functions the fragments call to write a situation, a type and an impact."""
    return {
        "pill_situacao": presentation.situation_pill,
        "pill_tipo": presentation.kind_pill,
        "texto_impacto": presentation.impact_text,
        "plural": presentation.plural,
    }


def _address(code: str, project_id: int) -> str:
    return f"{PAGE_ADDRESS}?codigo={quote(code)}&projeto={project_id}"


def _field_messages(error: InvalidDataError) -> dict[str, str]:
    """The message of each field; a message that is not of a field goes under ``geral``."""
    if isinstance(error.detail, Mapping):
        return {field: message for field, message in error.detail.items() if message}
    return {"geral": str(error.detail)}


def _code_of(req: func.HttpRequest) -> str:
    return (req.form.get(CODE_PARAMETER) or req.params.get(CODE_PARAMETER) or "").strip()


# ── The sheet ────────────────────────────────────────────────────────────


@bp.route(route=VIEW_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def lesson_sheet(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The sheet of the lesson: its text, reuses, history and the actions open to the user."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    sheet = service.find_lesson_sheet(session, user=context.user, code=code)
    if sheet is None:
        return AlpineAjaxResponse(
            template_name=NOT_FOUND_TEMPLATE, context={}, request=req, status_code=404
        )
    return AlpineAjaxResponse(
        template_name=VIEW_TEMPLATE,
        context={
            "ficha": sheet,
            "linha": sheet.row,
            "acoes": sheet.row.actions,
            "origem_url": sheet.row.origin_url,
            "action_enviar": f"/api/{SEND_ROUTE}",
            "action_publicar": f"/api/{PUBLISH_ROUTE}",
            **_presenters(),
        },
        request=req,
    )


# ── The lesson: new, edit and send ───────────────────────────────────────


def _lesson_form_response(
    req: func.HttpRequest, session: Session, context: RequestContext, state: FormState
) -> func.HttpResponse:
    code, values = state.code, state.values
    options = service.form_options(session, user=context.user)
    origin_options = list(options.origins)
    current_origin = values.get(validation.FIELD_ORIGIN)
    if current_origin and current_origin not in origin_options:
        origin_options.append(current_origin)
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={
            "codigo": code,
            "valores": values,
            "erros": state.errors,
            "tipos": lm.LESSON_TYPES,
            "fases": lm.LESSON_PHASES,
            "areas": lm.LESSON_AREAS,
            "disciplinas": options.disciplines,
            "origens": [(origin, calc.origin_label(origin)) for origin in origin_options],
            "aplicabilidades": lm.LESSON_APPLICABILITIES,
            "action": f"/api/{EDIT_ROUTE if code else PAGE_ROUTE}",
        },
        request=req,
        status_code=state.status_code,
    )


@bp.route(route=NEW_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lesson_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the new lesson, for the project of the scope (a Portfólio asks for the project)."""
    context.scope.require_project()
    values = {
        validation.FIELD_APPLICABILITY: lm.APPLICABILITY_PROJECT,
        validation.FIELD_ORIGIN: lm.ORIGIN_DIRECT,
        validation.FIELD_TERM_DAYS: "0",
        validation.FIELD_COST: "0,00",
    }
    return _lesson_form_response(req, session, context, FormState(code="", values=values))


@bp.route(route=PAGE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lesson_register(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the lesson (HU-129): it gets the number of the project and opens in the acervo."""
    try:
        created = service.create_lesson(
            session,
            user=context.user,
            scope=context.scope,
            form=req.form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        values = {field: req.form.get(field) or "" for field in LESSON_FORM_FIELDS}
        return _lesson_form_response(
            req,
            session,
            context,
            FormState(code="", values=values, errors=_field_messages(error), status_code=422),
        )
    return redirect_to(_address(created.code, created.project_id))


@bp.route(route=EDIT_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lesson_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a draft lesson with what it holds, for its author or a Gestor."""
    form = service.edit_form(session, user=context.user, code=_code_of(req))
    return _lesson_form_response(
        req, session, context, FormState(code=form.code, values=form.values)
    )


@bp.route(route=EDIT_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lesson_edit(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the draft lesson (and send it to validation when the form says so)."""
    code = _code_of(req)
    try:
        saved = service.update_lesson(session, user=context.user, code=code, form=req.form)
    except InvalidDataError as error:
        values = {field: req.form.get(field) or "" for field in LESSON_FORM_FIELDS}
        return _lesson_form_response(
            req,
            session,
            context,
            FormState(code=code, values=values, errors=_field_messages(error), status_code=422),
        )
    return redirect_to(_address(saved.code, saved.project_id))


@bp.route(route=SEND_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lesson_send(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Send the draft to validation (Rascunho to Em validação)."""
    sent = service.send_for_validation(
        session,
        user=context.user,
        code=_code_of(req),
        version=req.form.get(validation.FIELD_VERSION),
    )
    return redirect_to(_address(sent.code, sent.project_id))


# ── Validation and publication ───────────────────────────────────────────


def _decision_response(req: func.HttpRequest, state: FormState) -> func.HttpResponse:
    code, values = state.code, state.values
    return AlpineAjaxResponse(
        template_name=VALIDATE_TEMPLATE,
        context={
            "codigo": code,
            "valores": values,
            "erros": state.errors,
            "resultados": validation.VALIDATION_RESULTS,
            "aplicabilidades": lm.LESSON_APPLICABILITIES,
            "action": f"/api/{VALIDATE_ROUTE}",
        },
        request=req,
        status_code=state.status_code,
    )


@bp.route(route=VALIDATE_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lesson_validate_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the validator, only for a Gestor who is not the author (403 says why not)."""
    form = service.validation_form_values(session, user=context.user, code=_code_of(req))
    return _decision_response(req, FormState(code=form.code, values=form.values))


@bp.route(route=VALIDATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lesson_validate(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Validate, validate and publish, or return to Rascunho with a comment (HU-129)."""
    code = _code_of(req)
    try:
        decided = service.decide_validation(session, user=context.user, code=code, form=req.form)
    except InvalidDataError as error:
        values = {field: req.form.get(field) or "" for field in DECISION_FORM_FIELDS}
        return _decision_response(
            req,
            FormState(code=code, values=values, errors=_field_messages(error), status_code=422),
        )
    return redirect_to(_address(decided.code, decided.project_id))


@bp.route(route=PUBLISH_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lesson_publish(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Publish a validated lesson in the acervo (Gestor only)."""
    published = service.publish_lesson(
        session,
        user=context.user,
        code=_code_of(req),
        version=req.form.get(validation.FIELD_VERSION),
    )
    return redirect_to(_address(published.code, published.project_id))


# ── Apply in a project ───────────────────────────────────────────────────


def _application_response(
    req: func.HttpRequest, session: Session, context: RequestContext, state: FormState
) -> func.HttpResponse:
    code, values = state.code, state.values
    return AlpineAjaxResponse(
        template_name=APPLY_TEMPLATE,
        context={
            "codigo": code,
            "valores": values,
            "erros": state.errors,
            "projetos": service.reachable_projects(session, user=context.user, code=code),
            "pessoas": service.person_options(session),
            "hoje": calendario.today().isoformat(),
            "action": f"/api/{APPLY_ROUTE}",
        },
        request=req,
        status_code=state.status_code,
    )


@bp.route(route=APPLY_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lesson_apply_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the reuse, only for a published lesson."""
    form = service.application_form_values(
        session, user=context.user, code=_code_of(req), reference_date=calendario.today()
    )
    return _application_response(
        req, session, context, FormState(code=form.code, values=form.values)
    )


@bp.route(route=APPLY_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lesson_apply(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the reuse and, when asked, the action in the Central with the link back."""
    code = _code_of(req)
    try:
        applied = service.apply_lesson(
            session,
            user=context.user,
            code=code,
            form=req.form,
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        values = {field: req.form.get(field) or "" for field in APPLICATION_FORM_FIELDS}
        return _application_response(
            req,
            session,
            context,
            FormState(code=code, values=values, errors=_field_messages(error), status_code=422),
        )
    return redirect_to(_address(applied.code, applied.project_id))
