"""Routes of the panel and of the follow-up of the Central de Ações (D12, D14, ISSUE-020).

Prefix ``/api/central-acoes/``.

* ``GET  painel``                 the screen Dashboards e KPIs, one fragment (``painel-conteudo``);
  the origin filter is the query ``origem``;
* ``GET  painel/excel`` and ``painel/imprimivel``  the two exports of what the screen shows;
* ``GET  acoes/followup``         the modal of the follow-up: who gets what, for the filters of
  the list in the query (the same ones of the screen Ações), and the "simulado" notice while the
  e-mail sending is off;
* ``POST acoes/followup``         send: one notification per responsible, through the port; the
  modal answers what was recorded. Only who may manage (Gestor, Admin) sends.

The rules are in ``panel_service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Mapping

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, navigation
from src.core.excel import excel_response
from src.core.export_document import Document
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.central_acoes import panel_export, panel_service, presentation, validation
from src.modulos.central_acoes.origins import ORIGINS
from src.modulos.central_acoes.routes import MODAL_TARGET, _modal_error
from src.modulos.configuracoes import service as configuracoes

bp = func.Blueprint()

MODULE = "central_acoes"
READ = Access(module=MODULE)
MANAGE = Access(module=MODULE, permission=Permission.MANAGE)

PANEL_TARGET = "painel-conteudo"
PANEL_TEMPLATE = "central_acoes/painel.html"
FOLLOW_UP_TEMPLATE = "central_acoes/acoes_followup.html"
ACTIONS_SCREEN = "central_acoes/acoes"


def _origin_of(params: Mapping[str, str]) -> str:
    chosen = (params.get("origem") or "").strip()
    return chosen if chosen in ORIGINS else ""


def _panel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> panel_service.Dashboard:
    """The panel of the request: the only place of this screen that reads the clock."""
    return panel_service.dashboard(
        session,
        user=context.user,
        scope=context.scope,
        origin=_origin_of(req.params),
        reference_date=calendario.today(),
    )


# ── The screen and its exports ───────────────────────────────────────────────────────────────


@bp.route(route="central-acoes/painel", methods=["GET"])
@fragment_route(access=READ)
def panel_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The panel: KPIs, charts and the table of the responsibles, for the origin filter."""
    panel = _panel(req, session, context)
    screen = navigation.find_screen(ACTIONS_SCREEN)
    actions_path = navigation.public_path(screen) if screen is not None else "/"
    return AlpineAjaxResponse(
        template_name=PANEL_TEMPLATE,
        context={
            "painel": panel,
            "graficos": panel_export.charts_of(panel, portfolio=context.scope.is_portfolio),
            "origens": ORIGINS,
            "origem": panel.origin,
            "portfolio": context.scope.is_portfolio,
            "caminho_das_acoes": actions_path,
            "mes": panel_export.month_label,
            "url_excel": _export_address("painel/excel", panel.origin),
            "url_pdf": _export_address("painel/imprimivel", panel.origin),
        },
        request=req,
        target_id=PANEL_TARGET,
    )


def _export_address(path: str, origin: str) -> str:
    query = f"?origem={origin}" if origin else ""
    return f"/api/central-acoes/{path}{query}"


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    return panel_export.build_document(
        panel=_panel(req, session, context),
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
    )


@bp.route(route="central-acoes/painel/excel", methods=["GET"])
@file_route(access=READ)
def panel_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the panel: the KPIs and the tables behind the charts."""
    return excel_response(_document(req, session, context))


@bp.route(route="central-acoes/painel/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def panel_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


# ── The follow-up ────────────────────────────────────────────────────────────────────────────


def _follow_up_request(
    req: func.HttpRequest, context: RequestContext
) -> panel_service.FollowUpRequest:
    return panel_service.FollowUpRequest(
        scope=context.scope,
        filters=validation.parse_filters(req.params),
        reference_date=calendario.today(),
    )


@bp.route(route="central-acoes/acoes/followup", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def follow_up_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The preview of the follow-up: one line per responsible and the message each one gets."""
    request = _follow_up_request(req, context)
    plan = panel_service.plan_follow_up(session, user=context.user, request=request)
    return AlpineAjaxResponse(
        template_name=FOLLOW_UP_TEMPLATE,
        context={
            "plano": plan,
            "resultado": None,
            "consulta": presentation.query_string(request.filters),
        },
        request=req,
        target_id=MODAL_TARGET,
    )


@bp.route(route="central-acoes/acoes/followup", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def follow_up_send(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Send one follow-up per responsible and answer what was recorded, with the toast."""
    request = _follow_up_request(req, context)
    result = panel_service.send_follow_up(session, user=context.user, request=request)
    return AlpineAjaxResponse(
        template_name=FOLLOW_UP_TEMPLATE,
        context={
            "plano": None,
            "resultado": result,
            "consulta": presentation.query_string(request.filters),
        },
        request=req,
        target_id=MODAL_TARGET,
        toast=result.notice,
        toast_tipo=result.toast_kind,
    )
