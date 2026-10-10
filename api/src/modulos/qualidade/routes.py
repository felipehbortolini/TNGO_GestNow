"""Routes of the Quality module: the RNC screen, its ficha and its forms (D14, ISSUE-068).

Prefix ``/api/qualidade/``. The screen is one fragment, ``rnc-conteudo``: context line, KPIs,
the filters, the list with the next step and the actions, and the pagination. Everything that
changes the view (a KPI, a filter, a page) is a plain GET of the same route with the filters in
the query string, answered with the same fragment. The ficha and the forms open in the modal
(``rnc-modal-corpo``): a GET draws them, a POST saves and answers the refreshed list; a refusal
(422, 409, 403) answers the form again, filled in, in the modal. After a save the list carries a
hidden marker that reopens the ficha with the new state.

* ``GET  rnc``                                the screen (filters and page by query);
* ``GET  rnc/excel`` and ``rnc/imprimivel``   the two exports of what the screen shows;
* ``GET  rnc/{codigo}/ficha``                 the ficha (actions, history and attachments);
* ``GET/POST rnc/nova``                       Nova RNC (in the Portfólio the project comes first);
* ``GET/POST rnc/{codigo}/responsavel``       Atribuir a análise;
* ``GET/POST rnc/{codigo}/analise``           Registrar a análise (cria as ações na Central);
* ``GET/POST rnc/{codigo}/acoes``             Nova ação corretiva;
* ``GET/POST rnc/{codigo}/verificacao``       Enviar para verificação de eficácia;
* ``GET/POST rnc/{codigo}/eficacia``          Verificar a eficácia (Gestor);
* ``GET/POST rnc/{codigo}/cancelamento``      Cancelar a RNC (Gestor);
* ``GET/POST rnc/{codigo}/custo``             Atualizar o custo da não qualidade.

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, origin_links, rbac
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.excel import excel_response
from src.core.export_document import Document
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.qualidade import calculations, export, service, validation
from src.modulos.qualidade.service import RncLine, RncListing, RncSheet
from src.modulos.qualidade.validation import (
    ActionInput,
    AnalysisInput,
    CancellationInput,
    CostInput,
    OpeningInput,
    ResponsibleInput,
    RncFilters,
    VerificationInput,
)

bp = func.Blueprint()

MODULE = "qualidade"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)
MANAGE = Access(module=MODULE, permission=Permission.MANAGE)

CONTENT_TARGET = "rnc-conteudo"
MODAL_TARGET = "rnc-modal-corpo"
ROUTE = "/api/qualidade/rnc"

SCREEN_TEMPLATE = "qualidade/rnc.html"
PROJECT_TEMPLATE = "qualidade/rnc_projeto.html"
FORM_TEMPLATE = "qualidade/rnc_form.html"
FICHA_TEMPLATE = "qualidade/rnc_ficha.html"
ASSIGN_TEMPLATE = "qualidade/rnc_atribuir.html"
ANALYSIS_TEMPLATE = "qualidade/rnc_analise.html"
ACTION_TEMPLATE = "qualidade/rnc_acao.html"
VERIFICATION_TEMPLATE = "qualidade/rnc_verificacao.html"
EFFECTIVENESS_TEMPLATE = "qualidade/rnc_eficacia.html"
CANCELLATION_TEMPLATE = "qualidade/rnc_cancelar.html"
COST_TEMPLATE = "qualidade/rnc_custo.html"

OPENED_NOTICE = "RNC aberta: {code}. Prazo de tratamento: {deadline}."
ASSIGNED_NOTICE = "Análise atribuída."
ANALYZED_NOTICE = "Análise registrada; {count} ação(ões) corretiva(s) na Central."
ACTION_NOTICE = "Ação corretiva criada na Central."
VERIFICATION_NOTICE = "Verificação de eficácia prevista para {date}."
EFFECTIVENESS_NOTICE = "Eficácia verificada: RNC encerrada."
INEFFECTIVE_NOTICE = "Ação ineficaz: a RNC voltou para Ação corretiva."
CANCELLED_NOTICE = "RNC cancelada."
COST_NOTICE = "Custo da não qualidade atualizado."
CHOOSE_PROJECT_MESSAGE = "Escolha o projeto da RNC."


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


def _form_filters(form: Mapping[str, str]) -> RncFilters:
    """The filters of the list as the form carried them, not the fields of the form itself."""
    return validation.parse_filters(dict(parse_qsl(form.get("consulta", ""))))


def _lesson_url(sheet: service.RncSheet) -> str | None:
    if not sheet.lesson_code:
        return None
    return origin_links.link_to_screen("governanca/licoes", busca=sheet.lesson_code)


@dataclass(frozen=True)
class KpiCard:
    """A clickable KPI: the number, what it is read against and the link that filters by it."""

    label: str
    icon: str
    tone: str
    value: str
    reference: str
    footer: str
    url: str
    active: bool


@dataclass(frozen=True)
class _After:
    """What follows a save on the screen: the toast, the ficha to reopen and the notice."""

    notice: str
    ficha_code: str | None = None


# ── The screen ───────────────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/rnc", methods=["GET"])
@fragment_route(access=READ)
def rnc_list_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The screen: context, KPIs, filters, list and pagination, for the filters of the query."""
    return _screen(req, session, context, filters=validation.parse_filters(req.params))


@bp.route(route="qualidade/rnc/excel", methods=["GET"])
@file_route(access=READ)
def rnc_list_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the reports of the filter: what the screen lists, with its KPIs."""
    return excel_response(_document(req, session, context))


@bp.route(route="qualidade/rnc/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def rnc_list_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


# ── Ficha ────────────────────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/rnc/{codigo}/ficha", methods=["GET"])
@fragment_route(access=READ)
def rnc_sheet_fragment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The ficha of one RNC: the flow buttons, the record, the actions and the history."""
    sheet = _sheet(session, context, req)
    if sheet is None:
        return _not_found(req)
    consulta = req.params.get("consulta", "")
    people = configuracoes.find_people(session, {action.responsible_id for action in sheet.actions})
    return AlpineAjaxResponse(
        template_name=FICHA_TEMPLATE,
        context={
            "ficha": sheet,
            "consulta": consulta,
            "parametro_consulta": urlencode({"consulta": consulta}) if consulta else "",
            "nomes": {person_id: person.name for person_id, person in people.items()},
            "lesson_url": _lesson_url(sheet),
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "pode_gerir": rbac.can(context.user, Permission.MANAGE),
            "formatar_data": _format_date,
            "formatar_moeda": _format_money,
        },
        request=req,
        target_id=MODAL_TARGET,
    )


# ── Abertura ─────────────────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/rnc/nova", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new RNC; in the Portfólio the project is asked first."""
    project_id = context.scope.project_id or validation.parse_id(req.params.get("projeto"))
    if project_id is None:
        return _project_choice(req, session)
    return _rnc_form(
        req,
        session,
        state=_FormState(project_id=project_id, values={}),
    )


@bp.route(route="qualidade/rnc/nova", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Open the RNC and answer the refreshed list, or the form with its messages."""
    project_id = context.scope.project_id or validation.parse_id(req.form.get("projeto"))
    if project_id is None:
        raise InvalidDataError(CHOOSE_PROJECT_MESSAGE)
    data = _opening_input(req.form, project_id=project_id)
    today = calendario.today()
    outcome: list[service.OpeningResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.open_rnc(session, user=context.user, data=data, reference_date=today)
        ),
    )
    if error is not None or not outcome:
        return _rnc_form(
            req,
            session,
            state=_FormState(
                project_id=project_id, values=dict(req.form), errors=_field_errors(error)
            ),
            status=_error_status(error) if error else 200,
        )
    result = outcome[0]
    return _screen(
        req,
        session,
        context,
        filters=RncFilters(situation=validation.SITUATION_ACTIVE),
        after=_After(
            OPENED_NOTICE.format(code=result.code, deadline=_format_date(result.deadline)),
            ficha_code=result.code,
        ),
    )


# ── Análise de causa ─────────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/rnc/{codigo}/responsavel", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_assign_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The assignment of the analysis: who answers for the root cause."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    return _assign_fragment(req, session, line=line, values={}, errors={})


@bp.route(route="qualidade/rnc/{codigo}/responsavel", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_assign_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Assign the analysis and answer the refreshed list with the ficha reopened."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    data = ResponsibleInput(
        responsible_id=validation.parse_id(req.form.get("responsavelId")),
        version=req.form.get("versao"),
    )
    error = _attempt(
        session,
        lambda: service.assign_analysis(
            session, user=context.user, code=line.code, data=data, reference_date=calendario.today()
        ),
    )
    if error is not None:
        return _assign_fragment(
            req,
            session,
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
        after=_After(ASSIGNED_NOTICE, line.code),
    )


def _assign_fragment(
    req: func.HttpRequest,
    session: Session,
    *,
    line: RncLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=ASSIGN_TEMPLATE,
        context={
            "rnc": line,
            "valores": dict(values),
            "erros": dict(errors),
            "pessoas": configuracoes.list_person_options(session),
            "consulta": _consulta_of(req),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


@bp.route(route="qualidade/rnc/{codigo}/analise", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_analysis_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The analysis form: method, root cause, disposition, concession, cost and actions."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    values: dict[str, str] = {"custoCentavos": validation.reais_text(line.cost_cents) or "0,00"}
    return _analysis_fragment(req, session, line=line, values=values, errors={})


@bp.route(route="qualidade/rnc/{codigo}/analise", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_analysis_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the analysis and answer the refreshed list with the ficha reopened."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    data = _analysis_input(req.form)
    outcome: list[service.AnalysisResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.record_analysis(
                session,
                user=context.user,
                code=line.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _analysis_fragment(
            req,
            session,
            line=line,
            values=dict(req.form),
            errors=_field_errors(error),
            status=_error_status(error) if error else 200,
        )
    return _screen(
        req,
        session,
        context,
        filters=_form_filters(req.form),
        after=_After(ANALYZED_NOTICE.format(count=outcome[0].created_actions), line.code),
    )


def _analysis_fragment(
    req: func.HttpRequest,
    session: Session,
    *,
    line: RncLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=ANALYSIS_TEMPLATE,
        context={
            "rnc": line,
            "valores": dict(values),
            "erros": dict(errors),
            "pessoas": configuracoes.list_person_options(session),
            "metodos": validation.METHODS,
            "disposicoes": validation.DISPOSITIONS,
            "concessao": validation.DISPOSITIONS_WITH_CONCESSION,
            "max_acoes": validation.MAX_ACTIONS,
            "consulta": _consulta_of(req),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


@bp.route(route="qualidade/rnc/{codigo}/acoes", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_action_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of one more corrective action, while the RNC is in Ação corretiva."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    return _action_fragment(req, session, line=line, values={}, errors={})


@bp.route(route="qualidade/rnc/{codigo}/acoes", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_action_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the corrective action in the Central and answer the refreshed list."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    actions = _actions_input(req.form)
    error = _attempt(
        session,
        lambda: service.add_actions(
            session,
            user=context.user,
            code=line.code,
            actions_input=actions,
            reference_date=calendario.today(),
        ),
    )
    if error is not None:
        return _action_fragment(
            req,
            session,
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
        after=_After(ACTION_NOTICE, line.code),
    )


def _action_fragment(
    req: func.HttpRequest,
    session: Session,
    *,
    line: RncLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=ACTION_TEMPLATE,
        context={
            "rnc": line,
            "valores": dict(values),
            "erros": dict(errors),
            "pessoas": configuracoes.list_person_options(session),
            "consulta": _consulta_of(req),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


# ── Verificação de eficácia ──────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/rnc/{codigo}/verificacao", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_verification_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The confirmation of the sending to the effectiveness verification."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    return AlpineAjaxResponse(
        template_name=VERIFICATION_TEMPLATE,
        context={
            "rnc": line,
            "consulta": req.params.get("consulta", ""),
            "dias": service.verification_days(session, reference_date=calendario.today()),
        },
        request=req,
        target_id=MODAL_TARGET,
    )


@bp.route(route="qualidade/rnc/{codigo}/verificacao", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_verification_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Send to the verification: refused with an open action or a missing concession."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    expected: list[date] = []
    error = _attempt(
        session,
        lambda: expected.append(
            service.send_to_verification(
                session,
                user=context.user,
                code=line.code,
                version=req.form.get("versao"),
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not expected:
        return _modal_error(req, error or InvalidDataError("Não foi possível enviar."))
    return _screen(
        req,
        session,
        context,
        filters=_form_filters(req.form),
        after=_After(VERIFICATION_NOTICE.format(date=_format_date(expected[0])), line.code),
    )


@bp.route(route="qualidade/rnc/{codigo}/eficacia", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def rnc_effectiveness_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The effectiveness verification: Gestor only, never who answered for the analysis."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    values = {"data": calendario.today().isoformat()}
    return _effectiveness_fragment(req, line=line, values=values, errors={})


@bp.route(route="qualidade/rnc/{codigo}/eficacia", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def rnc_effectiveness_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Verify the effectiveness and answer the refreshed list with the ficha reopened."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    data = _verification_input(req.form)
    outcome: list[service.EffectivenessResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.verify_effectiveness(
                session,
                user=context.user,
                code=line.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _effectiveness_fragment(
            req,
            line=line,
            values=dict(req.form),
            errors=_field_errors(error),
            status=_error_status(error) if error else 200,
        )
    result = outcome[0]
    notice = EFFECTIVENESS_NOTICE if result.closed else INEFFECTIVE_NOTICE
    if result.lesson_code:
        notice = f"{notice} Lição {result.lesson_code} em Rascunho."
    return _screen(
        req,
        session,
        context,
        filters=_form_filters(req.form),
        after=_After(notice, line.code),
    )


def _effectiveness_fragment(
    req: func.HttpRequest,
    *,
    line: RncLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=EFFECTIVENESS_TEMPLATE,
        context={
            "rnc": line,
            "valores": dict(values),
            "erros": dict(errors),
            "referencia": calendario.today().isoformat(),
            "consulta": _consulta_of(req),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


# ── Cancelamento e custo ─────────────────────────────────────────────────────────────────────


@bp.route(route="qualidade/rnc/{codigo}/cancelamento", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def rnc_cancellation_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The cancellation of the RNC: Gestor, only before the corrective action."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    return _cancellation_fragment(req, line=line, values={}, errors={})


@bp.route(route="qualidade/rnc/{codigo}/cancelamento", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def rnc_cancellation_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cancel the RNC and answer the refreshed list with the ficha reopened."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    data = CancellationInput(reason=req.form.get("motivo", ""), version=req.form.get("versao"))
    error = _attempt(
        session,
        lambda: service.cancel_rnc(
            session,
            user=context.user,
            code=line.code,
            data=data,
            reference_date=calendario.today(),
        ),
    )
    if error is not None:
        return _cancellation_fragment(
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
        after=_After(CANCELLED_NOTICE, line.code),
    )


def _cancellation_fragment(
    req: func.HttpRequest,
    *,
    line: RncLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=CANCELLATION_TEMPLATE,
        context={
            "rnc": line,
            "valores": dict(values),
            "erros": dict(errors),
            "consulta": _consulta_of(req),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


@bp.route(route="qualidade/rnc/{codigo}/custo", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_cost_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The update of the cost of the non-quality of an active RNC."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    values = {"custoCentavos": validation.reais_text(line.cost_cents) or "0,00"}
    return _cost_fragment(req, line=line, values=values, errors={})


@bp.route(route="qualidade/rnc/{codigo}/custo", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def rnc_cost_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Update the cost with its composition and answer the refreshed list."""
    line = _line(session, context, req)
    if line is None:
        return _not_found(req)
    cents = validation.parse_cents(req.form.get("custoCentavos"))
    data = CostInput(
        cost_cents=cents,
        justification=req.form.get("justificativa", ""),
        version=req.form.get("versao"),
    )
    error = _attempt(
        session,
        lambda: service.update_cost(
            session,
            user=context.user,
            code=line.code,
            data=data,
            reference_date=calendario.today(),
        ),
    )
    if error is not None:
        return _cost_fragment(
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
        after=_After(COST_NOTICE, line.code),
    )


def _cost_fragment(
    req: func.HttpRequest,
    *,
    line: RncLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=COST_TEMPLATE,
        context={
            "rnc": line,
            "valores": dict(values),
            "erros": dict(errors),
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
    filters: RncFilters,
    after: _After | None = None,
) -> func.HttpResponse:
    """The list fragment for the filters, with an optional toast and the ficha to reopen."""
    listing = service.list_rncs(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=calendario.today(),
    )
    shown = replace(filters, page=listing.page)
    ficha_code = after.ficha_code if after else _exact_code(listing, shown.search)
    verification_days = service.verification_days(session, reference_date=calendario.today())
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={
            "listagem": listing,
            "filtros": shown,
            "kpis": _kpi_cards(listing, shown, verification_days=verification_days),
            "consulta": _query_string(shown),
            "parametro_consulta": (
                urlencode({"consulta": _query_string(shown)}) if _query_string(shown) else ""
            ),
            "url_excel": _address(shown, path=f"{ROUTE}/excel"),
            "url_pdf": _address(shown, path=f"{ROUTE}/imprimivel"),
            "portfolio": context.scope.is_portfolio,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "pode_gerir": rbac.can(context.user, Permission.MANAGE),
            "situacoes": validation.SITUATIONS,
            "severidades": validation.SEVERITIES,
            "origens": validation.ORIGINS,
            "link_limpar": _address(RncFilters()),
            "link_anterior": _page_link(shown, shown.page - 1, listing.page_count),
            "link_proximo": _page_link(shown, shown.page + 1, listing.page_count),
            "pagina_inicial": (shown.page - 1) * validation.PAGE_SIZE + 1,
            "pagina_final": min(shown.page * validation.PAGE_SIZE, listing.total),
            "tem_filtro": shown != RncFilters(),
            "abrir_ficha": ficha_code,
            "formatar_data": _format_date,
            "dias_verificacao": verification_days,
        },
        request=req,
        target_id=CONTENT_TARGET,
        toast=after.notice if after else None,
    )


def _project_choice(req: func.HttpRequest, session: Session) -> func.HttpResponse:
    """The Portfólio asks for the project before it opens the form (HU-016)."""
    return AlpineAjaxResponse(
        template_name=PROJECT_TEMPLATE,
        context={
            "projetos": configuracoes.list_projects(session),
            "consulta": req.params.get("consulta", ""),
        },
        request=req,
        target_id=MODAL_TARGET,
    )


def _rnc_form(
    req: func.HttpRequest,
    session: Session,
    *,
    state: _FormState,
    status: int = 200,
) -> func.HttpResponse:
    """The opening form of the RNC, empty or filled in with the messages of a refusal."""
    project = configuracoes.find_project(session, state.project_id)
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={
            "projeto": project,
            "projeto_id": state.project_id,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "referencia": calendario.today().isoformat(),
            "disciplinas": configuracoes.list_discipline_names(session),
            "empresas": configuracoes.list_company_options(session),
            "origens": validation.ORIGINS,
            "severidades": validation.SEVERITIES,
            "prazo_dias": service.treatment_days(session, reference_date=calendario.today()),
            "consulta": _consulta_of(req),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """The export document of the list for the filters of the query."""
    filters = validation.parse_filters(req.params)
    listing = service.list_rncs(
        session,
        user=context.user,
        scope=context.scope,
        filters=replace(filters, page=1),
        reference_date=calendario.today(),
    )
    return export.build_document(
        listing=listing,
        filters=replace(filters, page=1),
        scope=context.scope,
        projects=configuracoes.list_project_details(session),
        today=calendario.today(),
        verification_days=service.verification_days(session, reference_date=calendario.today()),
    )


def _kpi_cards(
    listing: RncListing, filters: RncFilters, *, verification_days: int
) -> list[KpiCard]:
    summary = listing.summary
    return [
        KpiCard(
            label="RNC em aberto",
            icon="warning",
            tone="warn" if summary.active else "ok",
            value=str(summary.active),
            reference="Esperado: 0",
            footer=f"{summary.critical} crítica(s)",
            url=_address(filters, situation=validation.SITUATION_ACTIVE),
            active=filters.situation == validation.SITUATION_ACTIVE,
        ),
        KpiCard(
            label="Prazo de tratamento vencido",
            icon="clock",
            tone="erro" if summary.overdue else "ok",
            value=str(summary.overdue),
            reference="Esperado: 0",
            footer="antes da verificação de eficácia",
            url=_address(filters, situation=validation.SITUATION_OVERDUE),
            active=filters.situation == validation.SITUATION_OVERDUE,
        ),
        KpiCard(
            label="Em verificação de eficácia",
            icon="checkCircle",
            tone="info",
            value=str(summary.in_verification),
            reference=f"Limite: {verification_days} dias",
            footer=f"{summary.verification_overdue} vencida(s)",
            url=_address(filters, situation=calculations.SITUATION_VERIFICATION),
            active=filters.situation == calculations.SITUATION_VERIFICATION,
        ),
        KpiCard(
            label="Encerradas",
            icon="shield",
            tone="ok",
            value=str(summary.closed),
            reference=f"de {summary.registered} registradas",
            footer=(
                f"tempo médio de {summary.average_days} dias"
                if summary.average_days is not None
                else "sem encerramento"
            ),
            url=_address(filters, situation=calculations.SITUATION_CLOSED),
            active=filters.situation == calculations.SITUATION_CLOSED,
        ),
        KpiCard(
            label="Custo da não qualidade",
            icon="money",
            tone="erro" if summary.cost_cents else "ok",
            value=_format_money(summary.cost_cents),
            reference="Esperado: R$ 0,00",
            footer="retrabalho, reparo, ensaios e perdas",
            url="",
            active=False,
        ),
    ]


def _query_string(filters: RncFilters, *, with_page: bool = True) -> str:
    values: dict[str, str] = {}
    if filters.search:
        values["busca"] = filters.search
    if filters.situation != validation.SITUATION_ACTIVE:
        values["situacao"] = filters.situation
    if filters.severity:
        values["severidade"] = filters.severity
    if filters.discipline:
        values["disciplina"] = filters.discipline
    if filters.origin:
        values["origem"] = filters.origin
    if filters.company_id is not None:
        values["empresa"] = str(filters.company_id)
    if with_page and filters.page > 1:
        values["pagina"] = str(filters.page)
    return urlencode(values)


def _address(filters: RncFilters, *, path: str = ROUTE, **overrides: str) -> str:
    """The address of the screen (or of an export) with the filters and the overrides."""
    updated = replace(filters, **overrides) if overrides else filters
    query = _query_string(updated, with_page=path == ROUTE)
    return f"{path}?{query}" if query else path


def _page_link(filters: RncFilters, page: int, page_count: int) -> str:
    if page < 1 or page > page_count or page == filters.page:
        return ""
    return _address(replace(filters, page=page))


def _exact_code(listing: RncListing, search: str) -> str | None:
    if not search:
        return None
    wanted = search.strip()
    for line in listing.lines:
        if line.code == wanted:
            return line.code
    return None


@dataclass(frozen=True)
class _FormState:
    """What the opening form remembers: the project, what was typed and the messages."""

    project_id: int
    values: Mapping[str, str] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)


def _opening_input(form: Mapping[str, str], *, project_id: int) -> OpeningInput:
    return OpeningInput(
        project_id=project_id,
        rnc_date=validation.parse_date(form.get("data")),
        origin=form.get("origem", ""),
        origin_ref=form.get("origemRef", ""),
        discipline=form.get("disciplina", ""),
        company_id=validation.parse_id(form.get("empresaId")),
        severity=form.get("severidade", ""),
        description=form.get("descricao", ""),
        containment=form.get("contencao", ""),
    )


def _actions_input(form: Mapping[str, str]) -> tuple[ActionInput, ...]:
    """The action blocks of the form, in order; a block with nothing filled is left out."""
    result: list[ActionInput] = []
    for position in range(1, validation.MAX_ACTIONS + 1):
        subject = form.get(f"acao{position}_assunto", "")
        responsible = form.get(f"acao{position}_responsavel", "")
        planned = form.get(f"acao{position}_prevista", "")
        description = form.get(f"acao{position}_descricao", "")
        if not any((subject.strip(), responsible.strip(), planned.strip(), description.strip())):
            continue
        result.append(
            ActionInput(
                subject=subject,
                responsible_id=validation.parse_id(responsible),
                planned_date=validation.parse_date(planned),
                description=description,
            )
        )
    return tuple(result)


def _analysis_input(form: Mapping[str, str]) -> AnalysisInput:
    cents = validation.parse_cents(form.get("custoCentavos"))
    return AnalysisInput(
        method=form.get("metodo", ""),
        root_cause=form.get("causaRaiz", ""),
        disposition=form.get("disposicao", ""),
        actions=_actions_input(form),
        concession_reference=form.get("concessaoReferencia", ""),
        concession_date=validation.parse_date(form.get("concessaoData")),
        cost_cents=0 if cents is None else cents,
    )


def _verification_input(form: Mapping[str, str]) -> VerificationInput:
    effective = form.get("eficaz")
    return VerificationInput(
        effective=True if effective == "sim" else False if effective == "nao" else None,
        text=form.get("texto", ""),
        checked_on=validation.parse_date(form.get("data")),
        register_lesson=form.get("registrarLicao") == "1",
        lesson_title=form.get("licaoTitulo", ""),
        lesson_recommendation=form.get("licaoRecomendacao", ""),
    )


def _line(session: Session, context: RequestContext, req: func.HttpRequest) -> RncLine | None:
    code = req.route_params.get("codigo") or ""
    return service.find_rnc(
        session, user=context.user, code=code, reference_date=calendario.today()
    )


def _sheet(session: Session, context: RequestContext, req: func.HttpRequest) -> RncSheet | None:
    code = req.route_params.get("codigo") or ""
    return service.rnc_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )


def _not_found(req: func.HttpRequest) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": [service.NOT_FOUND_MESSAGE]},
        request=req,
        target_id=MODAL_TARGET,
        status_code=404,
        toast=service.NOT_FOUND_MESSAGE,
        toast_tipo="aviso",
    )


def _format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _format_money(cents: int | None) -> str:
    if not cents:
        return "R$ 0,00"
    reais, centavos = divmod(cents, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"
