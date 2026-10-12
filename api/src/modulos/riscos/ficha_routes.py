"""Routes of the ficha do risco: plan, approval, action, review, closing and reopening (ISSUE-065).

Prefix ``/api/riscos/``. The ficha is one fragment, ``ficha-conteudo``: the alerts, the band with
the inherent and the residual assessment, the buttons with the next step and the five tabs
(Identificação, Avaliação, Resposta e ações, Monitoramento and Histórico). Every modal is a
fragment: a GET draws the form, a POST writes and answers the refreshed ficha; a refusal (422,
409, 403) answers the form again, filled in, in the modal.

* ``GET  ficha``, ``ficha/excel`` and ``ficha/imprimivel``   the screen and its two exports;
* ``GET/POST {codigo}/ficha/editar`` and ``{codigo}/ficha/avaliar``   the identification and the
  assessment of the register, answered into the ficha;
* ``GET/POST {codigo}/plano`` and ``{codigo}/plano/aprovacao``   the response plan and the
  manager's decision (the plan's responsible cannot approve it, D7);
* ``GET/POST {codigo}/acoes``                                the action, through the Central (D9);
* ``GET/POST {codigo}/revisoes``                             the periodic review;
* ``GET/POST {codigo}/encerramento``                         the closing (Gestor);
* ``GET/POST {codigo}/reabertura``                           the reopening (Gestor).

The rules are in ``ficha_service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac, translations
from src.core.errors import AccessDeniedError, DomainError, InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.export_document import Document
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.central_acoes import service as actions
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import service as governanca
from src.modulos.riscos import calculations, export, ficha_service, routes, service, validation

bp = func.Blueprint()


def _label(text: str, idioma: str) -> str:
    """O texto de interface do módulo no idioma do request (D13)."""
    return translations.translate("riscos", text, idioma)


def _notice(text: str | None, req: func.HttpRequest) -> str | None:
    """O aviso de uma gravação no idioma do request (D13)."""
    if not text:
        return text
    return translations.translate("riscos", text, translations.language_of(req))


MODULE = "riscos"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)
MANAGE = Access(module=MODULE, permission=Permission.MANAGE)

FICHA_TARGET = routes.FICHA_TARGET
FICHA_MODAL = "ficha-modal-corpo"
CODE_PARAMETER = "codigo"
MOTIVO_PARAMETER = "motivo"

FICHA_TEMPLATE = "riscos/ficha.html"
NOT_FOUND_TEMPLATE = "riscos/risco_nao_encontrado.html"
PLAN_TEMPLATE = "riscos/risco_plano.html"
APPROVAL_TEMPLATE = "riscos/risco_plano_aprovacao.html"
ACTION_TEMPLATE = "riscos/risco_acao.html"
REVIEW_TEMPLATE = "riscos/risco_revisao.html"
CLOSING_TEMPLATE = "riscos/risco_encerrar.html"
REOPEN_TEMPLATE = "riscos/risco_reabrir.html"

PLAN_SAVED_NOTICE = "Plano de resposta salvo. Situação: {situation}."
PLAN_PENDING_NOTICE = "Plano de resposta salvo e aguardando aprovação da gerência do projeto."
APPROVED_NOTICE = "Plano de resposta aprovado."
RETURNED_NOTICE = "Plano de resposta devolvido ao responsável."
ACTION_SAVED_NOTICE = "Ação {item} criada na Central de Ações."
REVIEW_NOTICE = "Revisão registrada. Próxima em {next}."
CLOSED_NOTICE = "Risco encerrado ({situation}). Lição {lesson} criada no acervo (08)."
CLOSED_CHANGE_NOTICE = " Solicitação de mudança {code} registrada no módulo 08."
CLOSED_ACTION_NOTICE = " Ação {item} criada na Central para tratar o problema."
REOPENED_NOTICE = "Risco reaberto. Situação: {situation}."
NO_EMAIL_NOTICE = ficha_service.NOTIFY_NO_EMAIL


@dataclass(frozen=True)
class FichaAfter:
    """What a write on the ficha answers besides the refreshed screen: the toast and the markers."""

    notice: str | None = None
    toast_tipo: str = "ok"
    extra: Mapping[str, object] = field(default_factory=dict)


def _ficha_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A refusal inside a modal of the ficha: the message in the modal body."""
    return routes._modal_error(req, error, target=FICHA_MODAL)


def _error_status(error: DomainError) -> int:
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


def _field_errors(error: DomainError | None) -> dict[str, str]:
    return routes._field_errors(error)


def _risk(session: Session, context: RequestContext, req: func.HttpRequest) -> service.RiskLine:
    return routes._risk(session, context, req)


# ── The ficha and its exports ────────────────────────────────────────────────────────────────


@bp.route(route="riscos/ficha", methods=["GET"])
@fragment_route(access=READ)
def risk_ficha_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The ficha of the risk: alerts, band, buttons and the five tabs."""
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    return ficha_response(req, session, context, code=code)


@bp.route(route="riscos/ficha/excel", methods=["GET"])
@file_route(access=READ)
def risk_ficha_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the ficha: the same content the screen shows."""
    return excel_response(_ficha_document(req, session, context))


@bp.route(route="riscos/ficha/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def risk_ficha_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the ficha: what the PDF button mounts and prints."""
    return printable_response(_ficha_document(req, session, context), req)


def _ficha_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    code = (req.params.get(CODE_PARAMETER) or "").strip()
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return export.ficha_document(
        sheet,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
        idioma=context.idioma,
    )


def ficha_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    code: str,
    after: FichaAfter | None = None,
) -> func.HttpResponse:
    """The ficha fragment, with the toast and the markers a write left behind."""
    today = calendario.today()
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=code, reference_date=today
    )
    if sheet is None:
        return AlpineAjaxResponse(
            template_name=NOT_FOUND_TEMPLATE,
            context={},
            request=req,
            target_id=FICHA_TARGET,
            status_code=404,
        )
    return AlpineAjaxResponse(
        template_name=FICHA_TEMPLATE,
        context=_ficha_context(session, sheet, context, today, after),
        request=req,
        target_id=FICHA_TARGET,
        toast=_notice(after.notice, req) if after else None,
        toast_tipo=after.toast_tipo if after else "ok",
    )


def _ficha_context(
    session: Session,
    sheet: ficha_service.RiskSheet,
    context: RequestContext,
    today: date,
    after: FichaAfter | None,
) -> dict[str, object]:
    code = sheet.line.code
    query = urlencode({CODE_PARAMETER: code, "projeto": context.scope.parameter})
    extra = dict(after.extra) if after else {}
    parameters = service.parameters(session, reference_date=today)
    line = sheet.line
    return {
        "ficha": sheet,
        "linha": line,
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "pode_gerir": rbac.can(context.user, Permission.MANAGE),
        "eh_admin": service.can_see_deleted(context.user),
        "acoes_abertas": sum(1 for action in sheet.actions if action.status != "concluida"),
        "exige_acao": line.has_plan
        and calculations.requires_response_action(
            line.nature,
            line.inherent.severity.id if line.inherent else None,
            line.strategy or "",
            parameters.scale,
        ),
        "url_excel": f"/api/riscos/ficha/excel?{query}",
        "url_pdf": f"/api/riscos/ficha/imprimivel?{query}",
        "url_editar": f"/api/riscos/{code}/ficha/editar",
        "url_avaliar": f"/api/riscos/{code}/ficha/avaliar",
        "url_plano": f"/api/riscos/{code}/plano",
        "url_aprovar": f"/api/riscos/{code}/plano/aprovacao",
        "url_acao": f"/api/riscos/{code}/acoes",
        "url_revisar": f"/api/riscos/{code}/revisoes",
        "url_encerrar": f"/api/riscos/{code}/encerramento",
        "url_reabrir": f"/api/riscos/{code}/reabertura",
        "formatar_data": routes._format_date,
        "formatar_moeda": routes._format_money,
        "texto_da_cadencia": routes._cadence_text_of,
        "etiqueta_de_faixa": lambda band: routes._severity_tone(band, parameters.scale),
        "texto_da_apurada": _apurada_text,
        "dimensoes": calculations.DIMENSIONS,
        **extra,
    }


def _apurada_text(situation: str, nature: str) -> str:
    if nature != calculations.OPPORTUNITY:
        return situation
    return service.OPPORTUNITY_APURADA.get(situation, situation)


# ── Edição e avaliação, respondidas na ficha ─────────────────────────────────────────────────


@bp.route(route="riscos/{codigo}/ficha/editar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_ficha_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The identification of the risk, to edit from the ficha."""
    risk = _risk(session, context, req)
    state = routes._FormState(
        project_id=risk.project_id,
        code=risk.code,
        query="",
        values=routes._risk_values(risk),
        version=risk.version,
        destino=routes.DESTINO_FICHA,
    )
    return routes._risk_form(req, session, context, state=state, modal_target=FICHA_MODAL)


@bp.route(route="riscos/{codigo}/ficha/editar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_ficha_edit_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the identification and answer the refreshed ficha."""
    risk = _risk(session, context, req)
    return routes._save(
        req,
        session,
        context,
        project_id=risk.project_id,
        code=risk.code,
        destino=routes.DESTINO_FICHA,
        modal_target=FICHA_MODAL,
    )


@bp.route(route="riscos/{codigo}/ficha/avaliar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_ficha_assess_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The assessment form of the risk, opened from the ficha."""
    return routes._assess_page(
        req, session, context, destino=routes.DESTINO_FICHA, modal_target=FICHA_MODAL
    )


@bp.route(route="riscos/{codigo}/ficha/avaliar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_ficha_assess_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the assessment and answer the refreshed ficha."""
    return routes._assess_submit(
        req, session, context, destino=routes.DESTINO_FICHA, modal_target=FICHA_MODAL
    )


# ── Plano de resposta e aprovação ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _PlanState:
    """What the plan form remembers: the ficha, what was typed and the messages of a refusal."""

    sheet: ficha_service.RiskSheet
    values: Mapping[str, str]
    errors: Mapping[str, str] = field(default_factory=dict)


def _plan_values(sheet: ficha_service.RiskSheet) -> dict[str, str]:
    line = sheet.line
    return {
        "estrategia": line.strategy or "",
        "plano": line.plan or "",
        "instrumento": line.instrument or "",
        "smRef": sheet.change.code if sheet.change else "",
        "severidadeAlvo": line.target_severity or "",
        "prazoAlvo": line.target_date.isoformat() if line.target_date else "",
        "custoRespostaCentavos": routes._reais_text(line.response_cost_cents or 0),
        "responsavelPlanoId": str(line.plan_responsible_id or line.owner_id),
        "exigirAprovacao": "1" if sheet.approval_pending else "",
    }


def _plan_input(form: Mapping[str, str]) -> validation.PlanInput:
    return validation.PlanInput(
        strategy=form.get("estrategia", ""),
        plan=form.get("plano", ""),
        instrument=form.get("instrumento", ""),
        change_code=form.get("smRef", ""),
        target_severity=form.get("severidadeAlvo", ""),
        target_date=validation.parse_date(form.get("prazoAlvo")),
        response_cost_cents=validation.parse_cents(form.get("custoRespostaCentavos")),
        plan_responsible_id=validation.parse_id(form.get("responsavelPlanoId")),
        require_approval=form.get("exigirAprovacao") == "1",
        version=form.get("versao"),
    )


@bp.route(route="riscos/{codigo}/plano", methods=["GET"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_plan_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The response plan form, with the values and the linked actions it already has."""
    risk = _risk(session, context, req)
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=risk.code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return _plan_response(req, session, state=_PlanState(sheet, _plan_values(sheet)))


@bp.route(route="riscos/{codigo}/plano", methods=["POST"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_plan_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the plan and answer the refreshed ficha, or the form with its messages."""
    risk = _risk(session, context, req)
    data = _plan_input(req.form)
    outcome: list[ficha_service.PlanResult] = []
    error = routes._attempt(
        session,
        lambda: outcome.append(
            ficha_service.save_plan(
                session,
                user=context.user,
                code=risk.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _plan_again(req, session, context, code=risk.code, values=req.form, error=error)
    result = outcome[0]
    notice = (
        PLAN_PENDING_NOTICE
        if result.approval_pending
        else PLAN_SAVED_NOTICE.format(situation=result.situation)
    )
    return ficha_response(req, session, context, code=risk.code, after=FichaAfter(notice=notice))


def _plan_again(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    code: str,
    values: Mapping[str, str],
    error: DomainError | None,
) -> func.HttpResponse:
    """The plan form again, filled in, with the messages of a refusal."""
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        return ficha_response(req, session, context, code=code)
    state = _PlanState(sheet, values, _field_errors(error))
    return _plan_response(
        req, session, state=state, status_code=_error_status(error) if error else 200
    )


def _plan_response(
    req: func.HttpRequest,
    session: Session,
    *,
    state: _PlanState,
    status_code: int = 200,
) -> func.HttpResponse:
    risk = state.sheet.line
    parameters = service.parameters(session, reference_date=calendario.today())
    needs_action = calculations.requires_response_action(
        risk.nature,
        risk.inherent.severity.id if risk.inherent else None,
        state.values.get("estrategia", ""),
        parameters.scale,
    )
    return AlpineAjaxResponse(
        template_name=PLAN_TEMPLATE,
        context={
            "risco": risk,
            "ficha": state.sheet,
            "versao": state.values.get("versao") or risk.version,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "faixas": tuple(reversed(parameters.scale.bands)),
            "estrategias": validation.PLAN_STRATEGIES.get(risk.nature, ()),
            "instrumentos": validation.INSTRUMENTS,
            "nova_sm": validation.NEW_CHANGE,
            "mudancas": governanca.change_options(session, project_id=risk.project_id),
            "pessoas": configuracoes.list_people(session),
            "acoes": state.sheet.actions,
            "exige_acao": needs_action,
            "formatar_moeda": routes._format_money,
            "etiqueta_de_faixa": lambda band: routes._severity_tone(band, parameters.scale),
        },
        request=req,
        target_id=FICHA_MODAL,
        status_code=status_code,
    )


@bp.route(route="riscos/{codigo}/plano/aprovacao", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_ficha_error)
def risk_plan_approval_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The manager's decision on the plan: approve or return it for revision."""
    risk = _risk(session, context, req)
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=risk.code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return _approval_response(
        req,
        state=_ApprovalState(sheet, {"decisao": "", "comentario": "", "versao": str(risk.version)}),
    )


@dataclass(frozen=True)
class _ApprovalState:
    """What the approval form remembers: the ficha and what was typed."""

    sheet: ficha_service.RiskSheet
    values: Mapping[str, str]
    errors: Mapping[str, str] = field(default_factory=dict)


@bp.route(route="riscos/{codigo}/plano/aprovacao", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_ficha_error)
def risk_plan_approval_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the decision and answer the refreshed ficha, or the form with its messages."""
    risk = _risk(session, context, req)
    data = validation.ApprovalInput(
        decision=req.form.get("decisao", ""),
        comment=req.form.get("comentario", ""),
        version=req.form.get("versao"),
    )
    outcome: list[ficha_service.ApprovalResult] = []
    error = routes._attempt(
        session,
        lambda: outcome.append(
            ficha_service.approve_plan(
                session,
                user=context.user,
                code=risk.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        sheet = ficha_service.find_risk_sheet(
            session, user=context.user, code=risk.code, reference_date=calendario.today()
        )
        if sheet is None:
            return ficha_response(req, session, context, code=risk.code)
        state = _ApprovalState(sheet, dict(req.form), _field_errors(error))
        return _approval_response(
            req, state=state, status_code=_error_status(error) if error else 200
        )
    notice = APPROVED_NOTICE if data.decision == validation.APPROVAL_APPROVED else RETURNED_NOTICE
    return ficha_response(req, session, context, code=risk.code, after=FichaAfter(notice=notice))


def _approval_response(
    req: func.HttpRequest, *, state: _ApprovalState, status_code: int = 200
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=APPROVAL_TEMPLATE,
        context={
            "risco": state.sheet.line,
            "ficha": state.sheet,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "decisoes": validation.APPROVAL_DECISIONS,
            "formatar_data": routes._format_date,
        },
        request=req,
        target_id=FICHA_MODAL,
        status_code=status_code,
    )


# ── Ação da Central ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _ActionState:
    """What the action form remembers: the ficha, what was typed and the messages."""

    sheet: ficha_service.RiskSheet
    values: Mapping[str, str]
    errors: Mapping[str, str] = field(default_factory=dict)


def _action_values(sheet: ficha_service.RiskSheet, user_person_id: int) -> dict[str, str]:
    line = sheet.line
    return {
        "assunto": "",
        "descricao": "",
        "solicitanteId": str(user_person_id),
        "responsavelId": str(line.owner_id),
        "prevista": calendario.today().isoformat(),
        "contribuicao": "",
    }


def _action_input(form: Mapping[str, str]) -> validation.ActionInput:
    return validation.ActionInput(
        subject=form.get("assunto", ""),
        description=form.get("descricao", ""),
        requester_id=validation.parse_id(form.get("solicitanteId")),
        responsible_id=validation.parse_id(form.get("responsavelId")),
        planned_date=validation.parse_date(form.get("prevista")),
        contributes_probability=form.get("contribuicaoProbabilidade") == "1",
        contributes_impact=form.get("contribuicaoImpacto") == "1",
    )


@bp.route(route="riscos/{codigo}/acoes", methods=["GET"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_action_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The action of the response plan: it is born in the Central with origin Risco."""
    risk = _risk(session, context, req)
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=risk.code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return _action_response(
        req,
        session,
        state=_ActionState(sheet, _action_values(sheet, context.user.person_id)),
    )


@bp.route(route="riscos/{codigo}/acoes", methods=["POST"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_action_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the action and answer the refreshed ficha; "Salvar e nova" reopens the form."""
    risk = _risk(session, context, req)
    data = _action_input(req.form)
    outcome: list[ficha_service.ActionResult] = []
    error = routes._attempt(
        session,
        lambda: outcome.append(
            ficha_service.create_risk_action(
                session,
                user=context.user,
                code=risk.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _action_again(req, session, context, code=risk.code, values=req.form, error=error)
    result = outcome[0]
    extra: dict[str, object] = {}
    if req.form.get("acao") == "nova":
        extra["abrir_url"] = f"/api/riscos/{risk.code}/acoes"
        extra["abrir_titulo"] = f"Nova ação do risco {risk.code}"
    return ficha_response(
        req,
        session,
        context,
        code=risk.code,
        after=FichaAfter(notice=ACTION_SAVED_NOTICE.format(item=result.item or ""), extra=extra),
    )


def _action_again(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    code: str,
    values: Mapping[str, str],
    error: DomainError | None,
) -> func.HttpResponse:
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        return ficha_response(req, session, context, code=code)
    state = _ActionState(sheet, dict(values), _field_errors(error))
    return _action_response(
        req, session, state=state, status_code=_error_status(error) if error else 200
    )


def _action_response(
    req: func.HttpRequest,
    session: Session,
    *,
    state: _ActionState,
    status_code: int = 200,
) -> func.HttpResponse:
    risk = state.sheet.line
    return AlpineAjaxResponse(
        template_name=ACTION_TEMPLATE,
        context={
            "risco": risk,
            "ficha": state.sheet,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "item": _next_item(session, risk.code),
            "pessoas": configuracoes.list_people(session),
            "oportunidade": risk.nature != calculations.THREAT,
        },
        request=req,
        target_id=FICHA_MODAL,
        status_code=status_code,
    )


def _next_item(session: Session, code: str) -> str:
    return actions.next_origin_item(session, origin_kind=ficha_service.ORIGIN_KIND, reference=code)


# ── Revisão periódica ────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _ReviewState:
    """What the review form remembers: the ficha, what was typed and the messages."""

    sheet: ficha_service.RiskSheet
    values: Mapping[str, str]
    errors: Mapping[str, str] = field(default_factory=dict)


def _review_values(sheet: ficha_service.RiskSheet, reference_date: date) -> dict[str, str]:
    line = sheet.line
    view = line.current
    return {
        "data": reference_date.isoformat(),
        "situacaoApurada": "Sem mudança",
        "p": str(view.probability) if view else "",
        "i": str(view.impact) if view else "",
        "comentario": "",
        "gatilho": "nao",
        "proximaRevisao": (reference_date + timedelta(days=sheet.cadence_days or 30)).isoformat(),
        "notificar": "",
    }


def _review_input(form: Mapping[str, str]) -> validation.ReviewInput:
    return validation.ReviewInput(
        reviewed_on=validation.parse_date(form.get("data")),
        assessed_situation=form.get("situacaoApurada", ""),
        probability=validation.parse_level(form.get("p")),
        impact=validation.parse_level(form.get("i")),
        comment=form.get("comentario", ""),
        trigger=form.get("gatilho") == "sim",
        next_review=validation.parse_date(form.get("proximaRevisao")),
        notify=form.get("notificar") == "1",
        version=form.get("versao"),
    )


@bp.route(route="riscos/{codigo}/revisoes", methods=["GET"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_review_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The periodic review form, with the cadence the current severity suggests."""
    risk = _risk(session, context, req)
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=risk.code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    values = _review_values(sheet, calendario.today())
    values["versao"] = str(risk.version)
    return _review_response(req, session, state=_ReviewState(sheet, values))


@bp.route(route="riscos/{codigo}/revisoes", methods=["POST"])
@fragment_route(access=WRITE, on_error=_ficha_error)
def risk_review_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the review and answer the refreshed ficha, or the form with its messages."""
    risk = _risk(session, context, req)
    data = _review_input(req.form)
    outcome: list[ficha_service.ReviewResult] = []
    error = routes._attempt(
        session,
        lambda: outcome.append(
            ficha_service.review_risk(
                session,
                user=context.user,
                code=risk.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _review_again(req, session, context, code=risk.code, values=req.form, error=error)
    result = outcome[0]
    extra: dict[str, object] = {}
    if result.closes_with:
        extra["abrir_url"] = (
            f"/api/riscos/{risk.code}/encerramento?{urlencode({MOTIVO_PARAMETER: result.closes_with})}"
        )
        extra["abrir_titulo"] = f"Encerrar risco {risk.code}"
    elif result.re_assess:
        extra["abrir_url"] = f"/api/riscos/{risk.code}/ficha/avaliar"
        extra["abrir_titulo"] = f"Avaliação do risco {risk.code}"
    notice = REVIEW_NOTICE.format(next=routes._format_date(data.next_review))
    if result.notification:
        notice = f"{notice} {result.notification}"
    return ficha_response(
        req, session, context, code=risk.code, after=FichaAfter(notice=notice, extra=extra)
    )


def _review_again(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    code: str,
    values: Mapping[str, str],
    error: DomainError | None,
) -> func.HttpResponse:
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        return ficha_response(req, session, context, code=code)
    state = _ReviewState(sheet, dict(values), _field_errors(error))
    return _review_response(
        req, session, state=state, status_code=_error_status(error) if error else 200
    )


def _review_response(
    req: func.HttpRequest,
    session: Session,
    *,
    state: _ReviewState,
    status_code: int = 200,
) -> func.HttpResponse:
    risk = state.sheet.line
    parameters = service.parameters(session, reference_date=calendario.today())
    return AlpineAjaxResponse(
        template_name=REVIEW_TEMPLATE,
        context={
            "risco": risk,
            "ficha": state.sheet,
            "versao": state.values.get("versao") or risk.version,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "parametros": parameters,
            "apuracoes": validation.APURACOES,
            "rotulo_avaliacao": "residual" if risk.residual else "inerente",
            "gatilho_texto": risk.trigger or "",
            "texto_da_apurada": _apurada_text,
            "texto_da_cadencia": routes._cadence_text_of,
        },
        request=req,
        target_id=FICHA_MODAL,
        status_code=status_code,
    )


# ── Encerramento e reabertura ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _ClosingState:
    """What the closing form remembers: the ficha, the other risks, what was typed and the messages."""

    sheet: ficha_service.RiskSheet
    others: tuple[service.RiskLine, ...]
    values: Mapping[str, str]
    errors: Mapping[str, str] = field(default_factory=dict)


def _closing_values(
    sheet: ficha_service.RiskSheet, reason: str, reference_date: date
) -> dict[str, str]:
    line = sheet.line
    return {
        "motivo": reason,
        "data": reference_date.isoformat(),
        "duplicadoDe": "",
        "impactoRealPrazoDias": "0",
        "impactoRealCustoCentavos": "0,00",
        "gerarAcao": "1",
        "acaoAssunto": f"Tratar o problema decorrente do risco {line.code}",
        "acaoResponsavelId": str(line.owner_id),
        "acaoPrevista": (reference_date + timedelta(days=7)).isoformat(),
        "abrirSm": "",
        "licao": "",
        "versao": str(line.version),
    }


def _closing_input(form: Mapping[str, str]) -> validation.ClosingInput:
    return validation.ClosingInput(
        reason=form.get("motivo", ""),
        closed_on=validation.parse_date(form.get("data")),
        duplicated_code=form.get("duplicadoDe", ""),
        real_schedule_days=validation.parse_days(form.get("impactoRealPrazoDias")),
        real_cost_cents=validation.parse_cents(form.get("impactoRealCustoCentavos")),
        generate_action=form.get("gerarAcao") == "1",
        action_subject=form.get("acaoAssunto", ""),
        action_responsible_id=validation.parse_id(form.get("acaoResponsavelId")),
        action_planned_date=validation.parse_date(form.get("acaoPrevista")),
        open_change=form.get("abrirSm") == "1",
        lesson=form.get("licao", ""),
        version=form.get("versao"),
    )


@bp.route(route="riscos/{codigo}/encerramento", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_ficha_error)
def risk_closing_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The closing form: the reason, the real impact, the records it creates and the lesson."""
    risk = _risk(session, context, req)
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=risk.code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    reason = req.params.get(MOTIVO_PARAMETER, "")
    if reason not in validation.CLOSING_REASONS:
        reason = ""
    others = ficha_service.sibling_risks(
        session, user=context.user, code=risk.code, reference_date=calendario.today()
    )
    return _closing_response(
        req,
        session,
        state=_ClosingState(sheet, others, _closing_values(sheet, reason, calendario.today())),
    )


@bp.route(route="riscos/{codigo}/encerramento", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_ficha_error)
def risk_closing_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Close the risk and answer the refreshed ficha, or the form with its messages."""
    risk = _risk(session, context, req)
    data = _closing_input(req.form)
    outcome: list[ficha_service.ClosingResult] = []
    error = routes._attempt(
        session,
        lambda: outcome.append(
            ficha_service.close_risk(
                session,
                user=context.user,
                code=risk.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _closing_again(req, session, context, code=risk.code, values=req.form, error=error)
    result = outcome[0]
    notice = CLOSED_NOTICE.format(situation=result.situation, lesson=result.lesson_code)
    if result.change_code:
        notice += CLOSED_CHANGE_NOTICE.format(code=result.change_code)
    if result.action_item:
        notice += CLOSED_ACTION_NOTICE.format(item=result.action_item)
    return ficha_response(
        req, session, context, code=risk.code, after=FichaAfter(notice=notice, toast_tipo="ok")
    )


def _closing_again(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    code: str,
    values: Mapping[str, str],
    error: DomainError | None,
) -> func.HttpResponse:
    sheet = ficha_service.find_risk_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        return ficha_response(req, session, context, code=code)
    others = ficha_service.sibling_risks(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    state = _ClosingState(sheet, others, dict(values), _field_errors(error))
    return _closing_response(
        req, session, state=state, status_code=_error_status(error) if error else 200
    )


def _closing_response(
    req: func.HttpRequest,
    session: Session,
    *,
    state: _ClosingState,
    status_code: int = 200,
) -> func.HttpResponse:
    risk = state.sheet.line
    return AlpineAjaxResponse(
        template_name=CLOSING_TEMPLATE,
        context={
            "risco": risk,
            "ficha": state.sheet,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "motivos": validation.CLOSING_REASONS,
            "materializado": validation.MATERIALIZED,
            "duplicado": validation.DUPLICATED,
            "pessoas": configuracoes.list_people(session),
            "outros": state.others,
            "oportunidade": risk.nature != calculations.THREAT,
            "abertas": tuple(a for a in state.sheet.actions if a.status != "concluida"),
        },
        request=req,
        target_id=FICHA_MODAL,
        status_code=status_code,
    )


@bp.route(route="riscos/{codigo}/reabertura", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_ficha_error)
def risk_reopen_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The reopening form: the justification, always required (Gestor)."""
    risk = _risk(session, context, req)
    return _reopen_response(req, risk, values={"justificativa": "", "versao": str(risk.version)})


@bp.route(route="riscos/{codigo}/reabertura", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_ficha_error)
def risk_reopen_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Reopen the risk and answer the refreshed ficha, or the form with its messages."""
    risk = _risk(session, context, req)
    data = validation.ReopenInput(
        justification=req.form.get("justificativa", ""), version=req.form.get("versao")
    )
    outcome: list[ficha_service.ReopenResult] = []
    error = routes._attempt(
        session,
        lambda: outcome.append(
            ficha_service.reopen_risk(
                session,
                user=context.user,
                code=risk.code,
                data=data,
                reference_date=calendario.today(),
            )
        ),
    )
    if error is not None or not outcome:
        return _reopen_response(
            req,
            risk,
            values=dict(req.form),
            errors=_field_errors(error),
            status_code=_error_status(error) if error else 200,
        )
    return ficha_response(
        req,
        session,
        context,
        code=risk.code,
        after=FichaAfter(notice=REOPENED_NOTICE.format(situation=outcome[0].situation)),
    )


def _reopen_response(
    req: func.HttpRequest,
    risk: service.RiskLine,
    *,
    values: Mapping[str, str],
    errors: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=REOPEN_TEMPLATE,
        context={"risco": risk, "valores": dict(values), "erros": dict(errors or {})},
        request=req,
        target_id=FICHA_MODAL,
        status_code=status_code,
    )
