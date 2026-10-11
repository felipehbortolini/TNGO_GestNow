"""Route blueprint for the Home module (ISSUE-079).

Prefixo ``/api/inicio``:

* ``GET inicio/resumo`` desenha o fragmento do Início (o contexto em etiquetas, os
  oito indicadores-chave, os pontos de atenção e os cards dos módulos) no alvo
  ``inicio-conteudo``, com a data de referência injetada (``calendario.today()``);
* ``GET inicio/resumo/excel`` baixa a planilha do resumo;
* ``GET inicio/resumo/imprimivel`` desenha a folha que o botão PDF monta e imprime.

As três rotas são READ (``Access(module="inicio")``): o Visualizador vê o resumo.
O Visualizador e os demais perfis alcançam todos os módulos donos; o fornecedor
não alcança nem o Início (D7). A rota lê a requisição e desenha a resposta;
toda regra mora na fachada.
"""

from __future__ import annotations

from datetime import date

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.inicio import calculations, export, service

bp = func.Blueprint()

HOME_ROUTE = "/api/inicio/resumo"
HOME_TARGET = "inicio-conteudo"
HOME_TEMPLATE = "inicio/home.html"

CAMINHO_ROUTE = "inicio/resumo"
CAMINHO_EXCEL_ROUTE = "inicio/resumo/excel"
CAMINHO_PRINTABLE_ROUTE = "inicio/resumo/imprimivel"

READ = Access(module=service.MODULE)


@bp.route(route=CAMINHO_ROUTE, methods=["GET"])
@fragment_route(access=READ)
def home_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Início no escopo do request: o contexto, os indicadores, a atenção e os cards."""
    overview = service.home_overview(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=HOME_TEMPLATE,
        context=_home_context(overview),
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


def _home_context(overview: service.HomeOverview) -> dict[str, object]:
    """O que o fragmento imprime: a visão e os formatadores e endereços de exportação."""
    return {
        "visao": overview,
        "url_excel": f"{HOME_ROUTE}/excel",
        "url_pdf": f"{HOME_ROUTE}/imprimivel",
        "formatar_data": _format_date,
        "formatar_moeda": calculations.compact_brl,
    }


def _format_date(value: date | None) -> str:
    """``25/09/2026``: a data como a barra de contexto e a exportação a escrevem."""
    return "" if value is None else format_value(ValueKind.DATE, value)
