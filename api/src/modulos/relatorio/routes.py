"""Route blueprint for the Management reporting module.

Análise do período (ISSUE-081, D6), prefix ``/api/relatorio/analise``. O modal abre de cinco
telas dos módulos 02, 03 e 04 e é feito de fragmentos:

* ``GET  analise/periodo?modulo=`` é o passo 1: o tipo e os períodos, com a situação de cada
  um; ``POST analise/periodo`` redesenha o passo 1 com o tipo trocado;
* ``GET  analise/formulario?modulo=&tipo=&periodo=`` é o passo 2: o resumo do período, o texto
  e um campo por desvio detectado; ``POST analise/formulario`` redesenha o passo 2 com o que
  foi digitado;
* ``POST analise/copiar`` é "Copiar do período anterior": o texto do período anterior, para
  revisão (sem anterior, o formulário fica como está e o aviso vai no toast);
* ``POST analise/gravar`` grava (422 por campo, 409 para a versão vencida, 403 abaixo de
  Membro) e responde a marca que fecha o modal;
* ``POST analise/excluir`` exclui (403 abaixo de Gestor) e responde a marca da exclusão.

Relatório gerencial (ISSUE-083, D12), prefix ``/api/relatorio/gerencial``:

* ``GET  gerencial?tipo=&periodo=&secoes=`` desenha as folhas do relatório no escopo do request
  (``?projeto=portfolio|<id>``); tipo ou período inválidos respondem 422 com a mensagem do
  formulário;
* ``GET  gerencial/excel?tipo=&periodo=&secoes=`` baixa a planilha do mesmo relatório pela porta
  canônica (D12): os indicadores das folhas, as tabelas e as análises do período; é rota de
  arquivo, sem o gate do Alpine, e uma recusa sai em texto simples com o status;
* ``GET  gerencial/emissao`` abre o modal de emissão e ``POST gerencial/emissao`` o redesenha
  com o escopo, o tipo e o período trocados, com a situação real de relatos e análises.

As três rotas são READ: o Visualizador vê o relatório, baixa o Excel e vê a situação que o
modal mostra.

The routes read the request and draw the answer; every rule is in the facade.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.relatorio import calculations, export, service, validation

bp = func.Blueprint()

ANALYSIS_ROUTE = "relatorio/analise"

ANALYSIS_MODAL_TARGET = "analise-modal"

ANALYSIS_PAGE_CLASS = "pagina--relatorio-analise"

PICKER_TEMPLATE = "relatorio/analise_periodo.html"

FORM_TEMPLATE = "relatorio/analise_formulario.html"

SAVED_TEMPLATE = "relatorio/analise_salvo.html"

DELETED_TEMPLATE = "relatorio/analise_excluido.html"

REPORT_ROUTE = "relatorio/gerencial"

REPORT_EXCEL_ROUTE = f"{REPORT_ROUTE}/excel"

REPORT_TARGET = "gerencial-conteudo"

REPORT_MODAL_TARGET = "relatorio-modal"

REPORT_PAGE_CLASS = "pagina--relatorio-gerencial"

SHEETS_TEMPLATE = "relatorio/folhas.html"

EMISSION_TEMPLATE = "relatorio/emissao.html"

READ_ACCESS = Access(module=service.MODULE)

WRITE_ACCESS = Access(module=service.MODULE, permission=Permission.WRITE)

MANAGE_ACCESS = Access(module=service.MODULE, permission=Permission.MANAGE)

NO_PREVIOUS_MESSAGE = "Não há análise registrada no período anterior."

COPIED_MESSAGE = "Texto de {label} copiado para revisão. Atualize os números e a tendência."

DELETED_MESSAGE = "Análise excluída."

SAVED_MESSAGE = "Análise {kind} de {label} {verb}."

# O campo de cada comentário no formulário: ``desvio_0``; a chave viaja no ``desvio_chave_0``.
_COMMENT_FIELD = re.compile(r"desvio_(\d+)")


@dataclass(frozen=True)
class Reply:
    """Como uma resposta difere da simples: o status e o toast que vai junto."""

    status_code: int = 200
    toast: str | None = None
    toast_kind: str = "ok"


@dataclass(frozen=True)
class FormState:
    """O que o formulário guarda entre o envio e a resposta: a identidade e o que foi digitado."""

    module: str = ""
    kind: str = ""
    period: str = ""
    analysis_id: int | None = None
    version: str = ""
    text: str = ""
    comments: Mapping[str, str] = field(default_factory=dict)


# ── O passo 1 ──────────────────────────────────────────────────────────────


@bp.route(route=f"{ANALYSIS_ROUTE}/periodo", methods=["GET", "POST"])
@fragment_route(access=WRITE_ACCESS)
def analysis_period_picker(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O passo 1: o tipo e os períodos do módulo, com a situação de cada um."""
    values = _values_of(req)
    module = values.get("modulo", "")
    kind = values.get("tipo") or validation.WEEKLY
    view = service.analysis_options(
        session,
        user=context.user,
        scope=context.scope,
        module=module,
        kind=kind,
        reference_date=calendario.today(),
    )
    return _picker_response(req, view)


# ── O passo 2 ──────────────────────────────────────────────────────────────


@bp.route(route=f"{ANALYSIS_ROUTE}/formulario", methods=["GET", "POST"])
@fragment_route(access=WRITE_ACCESS)
def analysis_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O passo 2: o resumo, o texto e os desvios do módulo, tipo e período."""
    values = _values_of(req)
    state = FormState(
        module=values.get("modulo", ""),
        kind=values.get("tipo", ""),
        period=values.get("periodo", ""),
        analysis_id=_integer(values.get("id")),
        version=values.get("versao", ""),
        text=values.get("analise", ""),
    )
    view = service.analysis_view(
        session,
        user=context.user,
        scope=context.scope,
        module=state.module,
        kind=state.kind,
        period=state.period,
        reference_date=calendario.today(),
    )
    return _form_response(req, context, view, text=state.text if state.text else None)


@bp.route(route=f"{ANALYSIS_ROUTE}/copiar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def analysis_copy(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Copiar do período anterior: o texto do anterior, para revisão."""
    state = _read_state(req)
    view = service.analysis_view(
        session,
        user=context.user,
        scope=context.scope,
        module=state.module,
        kind=state.kind,
        period=state.period,
        reference_date=calendario.today(),
    )
    previous = view.previous
    if previous is None:
        reply = Reply(toast=NO_PREVIOUS_MESSAGE, toast_kind="aviso")
        return _form_response(req, context, view, text=state.text or None, reply=reply)
    reply = Reply(toast=COPIED_MESSAGE.format(label=previous.label), toast_kind="info")
    return _form_response(req, context, view, text=previous.text, reply=reply)


@bp.route(route=f"{ANALYSIS_ROUTE}/gravar", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def analysis_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava a análise: 422 por campo com o formulário preenchido, 409 na versão vencida."""
    state = _read_state(req)
    try:
        saved = service.save_analysis(
            session,
            user=context.user,
            scope=context.scope,
            request=_request_of(state),
            reference_date=calendario.today(),
        )
    except InvalidDataError as error:
        errors = error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}
        return _refilled(req, session, context, state, errors=errors, reply=Reply(status_code=422))
    except VersionConflictError as error:
        return _refilled(
            req, session, context, state, errors={"geral": str(error)}, reply=Reply(status_code=409)
        )
    verb = "atualizada" if state.analysis_id is not None else "registrada"
    return AlpineAjaxResponse(
        template_name=SAVED_TEMPLATE,
        context={},
        request=req,
        target_id=ANALYSIS_MODAL_TARGET,
        root_class=ANALYSIS_PAGE_CLASS,
        toast=SAVED_MESSAGE.format(kind=saved.kind.lower(), label=saved.period_label, verb=verb),
    )


@bp.route(route=f"{ANALYSIS_ROUTE}/excluir", methods=["POST"])
@fragment_route(access=MANAGE_ACCESS)
def analysis_delete(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Exclui a análise e responde a marca que fecha o modal; o período fica pendente outra vez."""
    form = req.form
    try:
        service.delete_analysis(
            session,
            user=context.user,
            scope=context.scope,
            analysis_id=_integer(form.get("id")) or 0,
            version=form.get("versao"),
        )
    except (InvalidDataError, VersionConflictError) as error:
        status = 409 if isinstance(error, VersionConflictError) else 422
        return _refilled(
            req,
            session,
            context,
            _read_state(req),
            errors={"geral": str(error)},
            reply=Reply(status_code=status),
        )
    return AlpineAjaxResponse(
        template_name=DELETED_TEMPLATE,
        context={},
        request=req,
        target_id=ANALYSIS_MODAL_TARGET,
        root_class=ANALYSIS_PAGE_CLASS,
        toast=DELETED_MESSAGE,
    )


# ── O relatório gerencial (ISSUE-083) ──────────────────────────────────────


@bp.route(route=REPORT_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def report_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """As folhas do relatório para o escopo do request, o tipo, o período e as seções."""
    params = req.params
    view = service.report_view(
        session,
        user=context.user,
        scope=context.scope,
        kind=(params.get("tipo") or "").strip(),
        period=(params.get("periodo") or "").strip(),
        sections=_sections_of(req),
        reference_date=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=SHEETS_TEMPLATE,
        context=_sheets_context(view),
        request=req,
        target_id=REPORT_TARGET,
        root_class=REPORT_PAGE_CLASS,
    )


@bp.route(route=REPORT_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def report_sheets_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A planilha do relatório: os indicadores das folhas, as tabelas e as análises do período."""
    params = req.params
    hoje = calendario.today()
    view = service.report_view(
        session,
        user=context.user,
        scope=context.scope,
        kind=(params.get("tipo") or "").strip(),
        period=(params.get("periodo") or "").strip(),
        sections=_sections_of(req),
        reference_date=hoje,
    )
    return excel_response(export.build_document(sheets=view, today=hoje))


@bp.route(route=f"{REPORT_ROUTE}/emissao", methods=["GET", "POST"])
@fragment_route(access=READ_ACCESS)
def report_emission(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O modal de emissão: o escopo, o tipo, o período e a situação de relatos e análises."""
    values = _values_of(req)
    scope = service.report_scope(
        session, fallback=context.scope, requested=values.get("escopo", "")
    )
    view = service.report_status(
        session,
        user=context.user,
        scope=scope,
        kind=(values.get("tipo") or "").strip(),
        period=(values.get("periodo") or "").strip(),
        reference_date=calendario.today(),
        sections=_sections_of(req),
    )
    return AlpineAjaxResponse(
        template_name=EMISSION_TEMPLATE,
        context={"visao": view},
        request=req,
        target_id=REPORT_MODAL_TARGET,
        root_class=REPORT_PAGE_CLASS,
    )


def _sections_of(req: func.HttpRequest) -> tuple[str, ...]:
    """As seções pedidas: os checkboxes do POST ou o ``secoes`` em csv do endereço."""
    if req.method == "POST":
        return tuple(part.strip() for part in req.form.getlist("secoes") if part.strip())
    return tuple(
        part.strip() for part in (req.params.get("secoes") or "").split(",") if part.strip()
    )


def _sheets_context(view: service.ReportSheets) -> dict[str, Any]:
    """O que as folhas precisam: a visão e os formatadores, como nos fragmentos da análise."""
    return {
        "visao": view,
        "formatar_pct": calculations.format_percent,
        "formatar_pct_sinal": calculations.format_percent_signed,
        "formatar_indice": calculations.format_index,
        "formatar_pp": calculations.format_pp,
        "formatar_mes": calculations.format_month,
        "formatar_data": calculations.format_date,
        "formatar_num": calculations.format_number,
        "formatar_num0": calculations.format_number0,
        "formatar_num1": calculations.format_number1,
        "formatar_num2": calculations.format_number2,
        "formatar_mil": calculations.format_thousands,
        "formatar_moeda": calculations.format_money,
        "formatar_moeda_mil": calculations.format_money_thousands,
        "formatar_moeda_compacta": calculations.format_money_compact,
    }


# ── Respostas ──────────────────────────────────────────────────────────────


def _picker_response(req: func.HttpRequest, view: service.AnalysisPeriodsView) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=PICKER_TEMPLATE,
        context={"visao": view, "tipos": validation.KINDS, "limites": validation.LIMITS},
        request=req,
        target_id=ANALYSIS_MODAL_TARGET,
        root_class=ANALYSIS_PAGE_CLASS,
    )


def _form_response(
    req: func.HttpRequest,
    context: RequestContext,
    view: service.AnalysisView,
    *,
    text: str | None = None,
    comments: Mapping[str, str] | None = None,
    errors: Mapping[str, str] | None = None,
    reply: Reply | None = None,
) -> func.HttpResponse:
    """O passo 2 desenhado para a leitura, com o texto e os comentários que o formulário mostra."""
    reply = reply or Reply()
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context=_form_context(
            view,
            text=text,
            comments=comments,
            errors=errors,
            pode_excluir=rbac.can(context.user, Permission.MANAGE),
        ),
        request=req,
        target_id=ANALYSIS_MODAL_TARGET,
        root_class=ANALYSIS_PAGE_CLASS,
        status_code=reply.status_code,
        toast=reply.toast,
        toast_tipo=reply.toast_kind,
    )


def _refilled(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    state: FormState,
    *,
    errors: Mapping[str, str],
    reply: Reply,
) -> func.HttpResponse:
    """O passo 2 outra vez com o que a pessoa digitou, com as mensagens no lugar de cada campo."""
    view = service.analysis_view(
        session,
        user=context.user,
        scope=context.scope,
        module=state.module,
        kind=state.kind,
        period=state.period,
        reference_date=calendario.today(),
    )
    return _form_response(
        req, context, view, text=state.text, comments=state.comments, errors=errors, reply=reply
    )


def _form_context(
    view: service.AnalysisView,
    *,
    text: str | None,
    comments: Mapping[str, str] | None,
    errors: Mapping[str, str] | None,
    pode_excluir: bool,
) -> dict[str, Any]:
    """O que o formulário do passo 2 precisa: a visão, o texto, as linhas de desvio e os erros."""
    found = errors or {}
    known = {validation.FIELD_TEXT} | {
        validation.comment_field(index) for index in range(len(view.deviations))
    }
    return {
        "visao": view,
        "texto": view.text if text is None else text,
        "linhas": tuple(
            _deviation_row(index, deviation, comments=comments, errors=found)
            for index, deviation in enumerate(view.deviations)
        ),
        "erros": found,
        "mensagens": [message for key, message in found.items() if key not in known],
        "atualizado": _updated_text(view.record),
        "limites": validation.LIMITS,
        "pode_excluir": pode_excluir,
        "formatar_pct": calculations.format_percent,
        "formatar_indice": calculations.format_index,
        "formatar_moeda": calculations.format_money,
        "formatar_mes": calculations.format_month,
        "formatar_pp": calculations.format_pp,
        "formatar_num": calculations.format_number,
        "formatar_num2": calculations.format_number2,
    }


def _updated_text(record: service.AnalysisRecordView | None) -> str:
    """Quando o registro foi atualizado, no fuso do produto; vazio quando não há registro."""
    if record is None:
        return ""
    return f"{calendario.in_product_timezone(record.updated_at):%d/%m/%Y %H:%M}"


def _deviation_row(
    index: int,
    deviation: service.AnalysisDeviationView,
    *,
    comments: Mapping[str, str] | None,
    errors: Mapping[str, str],
) -> dict[str, Any]:
    """Uma linha de desvio: o índice, o desvio, o comentário que o textarea mostra e o erro."""
    value = deviation.comment if comments is None else comments.get(deviation.key, "")
    return {
        "indice": index,
        "desvio": deviation,
        "valor": value,
        "erro": errors.get(validation.comment_field(index)),
    }


# ── Lendo a requisição ─────────────────────────────────────────────────────


def _values_of(req: func.HttpRequest) -> Mapping[str, str]:
    """Os campos do formulário no POST e os parâmetros do endereço no GET."""
    return req.form if req.method == "POST" else req.params


def _read_state(req: func.HttpRequest) -> FormState:
    """O formulário do passo 2 como foi enviado: a identidade, o texto e os comentários."""
    form = req.form
    indexes = sorted({int(found[1]) for key in form if (found := _COMMENT_FIELD.fullmatch(key))})
    comments = {
        key: form.get(validation.comment_field(index), "")
        for index in indexes
        if (key := form.get(f"desvio_chave_{index}", ""))
    }
    return FormState(
        module=form.get("modulo", ""),
        kind=form.get("tipo", ""),
        period=form.get("periodo", ""),
        analysis_id=_integer(form.get("id")),
        version=form.get("versao", ""),
        text=form.get("analise", ""),
        comments=comments,
    )


def _request_of(state: FormState) -> service.AnalysisRequest:
    return service.AnalysisRequest(
        module=state.module,
        kind=state.kind,
        period=state.period,
        analysis_id=state.analysis_id,
        version=state.version or None,
        text=state.text,
        comments=state.comments,
    )


def _integer(value: str | None) -> int | None:
    """O número em um campo, ou ``None`` quando ele está vazio ou não é um."""
    try:
        return int(value) if value else None
    except ValueError:
        return None
