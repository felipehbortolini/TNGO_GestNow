"""Route blueprint for the Home module (ISSUE-079 e ISSUE-080).

Prefixo ``/api/inicio``:

* ``GET inicio/resumo`` desenha o fragmento do Início (o contexto em etiquetas, os
  oito indicadores-chave, a carteira de projetos no Portfólio, os pontos de atenção
  e os cards dos módulos) no alvo ``inicio-conteudo``, com a data de referência
  injetada (``calendario.today()``);
* ``GET inicio/resumo/excel`` baixa a planilha do resumo;
* ``GET inicio/resumo/imprimivel`` desenha a folha que o botão PDF monta e imprime;
* ``GET inicio/ponderacao`` desenha o modal da ponderação (alvo ``ponderacao-modal``);
* ``POST inicio/ponderacao/previa`` re-renderiza o modal com a prévia dos pesos, sem
  gravar; ``POST inicio/ponderacao/gravar`` grava a versão nova dos parâmetros e
  responde a marca que fecha o modal com a carteira atualizada.

O resumo é READ (``Access(module="inicio")``): o Visualizador vê tudo. A prévia e a
gravação da ponderação são MANAGE (Gestor ou Admin; Membro recebe 403). O fornecedor
não alcança nem o Início (D7). A rota lê a requisição e desenha a resposta; toda
regra mora na fachada.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import InvalidDataError
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.inicio import calculations, export, service, validation

bp = func.Blueprint()

HOME_ROUTE = "/api/inicio/resumo"
HOME_TARGET = "inicio-conteudo"
HOME_TEMPLATE = "inicio/home.html"

CAMINHO_ROUTE = "inicio/resumo"
CAMINHO_EXCEL_ROUTE = "inicio/resumo/excel"
CAMINHO_PRINTABLE_ROUTE = "inicio/resumo/imprimivel"

PONDERATION_ROUTE = "/api/inicio/ponderacao"
PONDERATION_PREVIEW_ROUTE = "/api/inicio/ponderacao/previa"
PONDERATION_SAVE_ROUTE = "/api/inicio/ponderacao/gravar"

CAMINHO_PONDERATION_ROUTE = "inicio/ponderacao"
CAMINHO_PONDERATION_PREVIEW_ROUTE = "inicio/ponderacao/previa"
CAMINHO_PONDERATION_SAVE_ROUTE = "inicio/ponderacao/gravar"

PONDERATION_TEMPLATE = "inicio/ponderacao.html"
PONDERATION_SAVED_TEMPLATE = "inicio/ponderacao_salvo.html"

PONDERATION_MODAL_TARGET = "ponderacao-modal"
CARTEIRA_TARGET = "carteira-conteudo"

PONDERATION_PAGE_CLASS = "pagina--inicio-home"

PONDERATION_SAVED_MESSAGE = "Ponderação da carteira atualizada."

READ = Access(module=service.MODULE)
MANAGE = Access(module=service.MODULE, permission=Permission.MANAGE)


@bp.route(route=CAMINHO_ROUTE, methods=["GET"])
@fragment_route(access=READ)
def home_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Início no escopo do request: o contexto, os indicadores, a carteira, a atenção e os cards."""
    overview = service.home_overview(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=HOME_TEMPLATE,
        context=_home_context(
            overview=overview,
            pode_ponderar=overview.is_portfolio and _can_manage(context),
        ),
        request=req,
        target_id=HOME_TARGET,
    )


@bp.route(route=CAMINHO_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ)
def home_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A planilha do resumo: os indicadores, os pontos de atenção e os cards."""
    return excel_response(_document(req, session, context))


@bp.route(route=CAMINHO_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ)
def home_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A folha imprimível do mesmo documento: o botão PDF a monta e chama a impressão."""
    return printable_response(_document(req, session, context), req)


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """O documento do resumo no corte de hoje; o único lugar da tela que lê o relógio (D6)."""
    del req
    today = calendario.today()
    overview = service.home_overview(
        session, user=context.user, scope=context.scope, reference_date=today
    )
    return export.build_document(
        overview=overview,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


# ── A ponderação da carteira (ISSUE-080) ─────────────────────────────────


@bp.route(route=CAMINHO_PONDERATION_ROUTE, methods=["GET"])
@fragment_route(access=READ)
def ponderation_modal(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O modal da ponderação: os critérios e as notas vigentes e os pesos atuais da carteira."""
    view = service.ponderation_view(session, user=context.user, reference_date=calendario.today())
    return AlpineAjaxResponse(
        template_name=PONDERATION_TEMPLATE,
        context=_ponderation_context(view),
        request=req,
        target_id=PONDERATION_MODAL_TARGET,
        root_class=PONDERATION_PAGE_CLASS,
    )


@bp.route(route=CAMINHO_PONDERATION_PREVIEW_ROUTE, methods=["POST"])
@fragment_route(access=MANAGE)
def ponderation_preview(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A prévia dos pesos com o que foi digitado: redesha o modal, sem gravar nada."""
    form = validation.read_form(req.form)
    reference_date = calendario.today()
    view = service.ponderation_view(session, user=context.user, reference_date=reference_date)
    preview = service.ponderation_preview(
        session,
        user=context.user,
        criteria=form.weights,
        grades=form.grades,
        reference_date=reference_date,
    )
    return AlpineAjaxResponse(
        template_name=PONDERATION_TEMPLATE,
        context=_ponderation_context(view, values=form.values, preview=preview),
        request=req,
        target_id=PONDERATION_MODAL_TARGET,
        root_class=PONDERATION_PAGE_CLASS,
    )


@bp.route(route=CAMINHO_PONDERATION_SAVE_ROUTE, methods=["POST"])
@fragment_route(access=MANAGE)
def ponderation_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava a ponderação (422 por campo) e devolve a marca que fecha o modal com a carteira nova."""
    form = validation.read_form(req.form)
    reference_date = calendario.today()
    try:
        service.save_ponderation(
            session,
            user=context.user,
            criteria=form.weights,
            grades=form.grades,
            justification=form.justification,
            reference_date=reference_date,
        )
    except InvalidDataError as error:
        view = service.ponderation_view(session, user=context.user, reference_date=reference_date)
        return AlpineAjaxResponse(
            template_name=PONDERATION_TEMPLATE,
            context=_ponderation_context(view, values=form.values, errors=_field_messages(error)),
            request=req,
            target_id=PONDERATION_MODAL_TARGET,
            root_class=PONDERATION_PAGE_CLASS,
            status_code=422,
        )
    overview = service.home_overview(
        session, user=context.user, scope=context.scope, reference_date=reference_date
    )
    return AlpineAjaxResponse(
        template_name=PONDERATION_SAVED_TEMPLATE,
        context=_carteira_context(overview),
        request=req,
        toast=PONDERATION_SAVED_MESSAGE,
    )


def _field_messages(error: InvalidDataError) -> Mapping[str, str]:
    """As mensagens do erro por campo; um erro sem campo cai em ``geral``."""
    return error.detail if isinstance(error.detail, Mapping) else {"geral": str(error)}


def _home_context(*, overview: service.HomeOverview, pode_ponderar: bool) -> dict[str, object]:
    """O que o fragmento imprime: a visão, os formatadores, os endereços e quem pode ponderar."""
    return {
        "visao": overview,
        "pode_ponderar": pode_ponderar,
        "url_excel": f"{HOME_ROUTE}/excel",
        "url_pdf": f"{HOME_ROUTE}/imprimivel",
        **_carteira_context(overview),
    }


def _carteira_context(overview: service.HomeOverview) -> dict[str, object]:
    """O que a carteira e a ponderação precisam: a visão e os formatadores de leitura."""
    return {
        "visao": overview,
        "formatar_data": _format_date,
        "formatar_moeda": calculations.compact_brl,
        "formatar_pct": calculations.percent_text,
        "formatar_indice": calculations.index_text,
        "formatar_num": calculations.integer_text,
        "tom_indice": calculations.index_tone,
    }


def _ponderation_context(
    view: service.PonderationView,
    *,
    values: Mapping[str, str] | None = None,
    preview: service.PonderationPreview | None = None,
    errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """O que o modal imprime: a visão, os valores digitados, a prévia e os erros por campo."""
    found = errors or {}
    return {
        "visao": view,
        "valores": _ponderation_values(view, values),
        "previa": preview,
        "erros": found,
        "mensagens": [message for message in found.values() if message],
        "formatar_pct": calculations.percent_text,
        "formatar_num": calculations.input_number,
    }


def _ponderation_values(
    view: service.PonderationView, posted: Mapping[str, str] | None
) -> dict[str, str]:
    """O que cada campo do modal mostra: os valores vigentes, cobertos pelo que foi digitado."""
    values: dict[str, str] = {}
    for criterion in view.criteria:
        values[validation.weight_field(criterion.id)] = calculations.input_number(criterion.weight)
    for project in view.projects:
        for criterion_id, grade in project.grades.items():
            values[validation.grade_field(project.project_id, criterion_id)] = str(grade)
    if posted:
        values.update(posted)
    return values


def _can_manage(context: RequestContext) -> bool:
    """O perfil pode gerir a ponderação (Gestor ou Admin): o botão do modal aparece para ele."""
    return rbac.can(context.user, Permission.MANAGE)


def _format_date(value: date | None) -> str:
    """``25/09/2026``: a data como a barra de contexto e a exportação a escrevem."""
    return "" if value is None else format_value(ValueKind.DATE, value)
