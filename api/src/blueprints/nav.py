"""Shell blueprint — the fragments the shell asks for: navigation, scope picker and glossary.

``/api/nav`` serves the sidebar and the module tabs in one multi-target
response, both drawn from the single navigation list (D2). It also resolves the
scope of the request (D8) and remembers it in a cookie, so every navigation
leaves the URL and the cookie in agreement. ``/api/escopo/projetos`` is the
project choice of the inclusion mechanism, and ``/api/glossario`` feeds the
hint of the siglas (HU-018).

Add a screen: append one entry to ``api/src/core/navegacao.json``. The icon
name must exist in ``app/ds/icons.js``.
"""

import re
from dataclasses import dataclass

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import navigation, navigation_view, scope
from src.core.glossary import load_glossary
from src.core.responses import AlpineAjaxResponse
from src.core.routing import fragment_route
from src.modulos.configuracoes import service as configuracoes

bp = func.Blueprint()

# The name of an inclusion action travels in the URL (``?acao=nova``): lower
# case words only, so nothing but a plain token can come back to the screen.
_ACTION_TOKEN = re.compile(r"[a-z0-9_-]{1,40}")


@dataclass(frozen=True)
class ProjectChoice:
    """A project of the picker and the address that reopens the screen in it."""

    code: str
    name: str
    url: str


@bp.route(route="nav", methods=["GET"])
@fragment_route
def main_nav(req: func.HttpRequest, session: Session) -> func.HttpResponse:
    """Return the sidebar and the module tabs, and remember the scope in a cookie."""
    projects = configuracoes.list_projects(session)
    current_scope = scope.resolve_scope(req, {project.id for project in projects})
    view = navigation_view.build(req.params.get("caminho"), current_scope, projects)

    response = AlpineAjaxResponse(
        template_name="nav/navegacao.html",
        context={"nav": view},
        request=req,
        toast=_rejected_notice(current_scope, view.scope_label),
        toast_tipo="aviso",
    )
    response.headers["Set-Cookie"] = scope.cookie_header(
        current_scope, secure=scope.is_secure_request(req)
    )
    return response


@bp.route(route="escopo/projetos", methods=["GET"])
@fragment_route
def choose_project(req: func.HttpRequest, session: Session) -> func.HttpResponse:
    """List the projects as links that reopen the current screen in the chosen one (D8)."""
    screen = navigation.screen_for_path(req.params.get("caminho"))
    path = navigation.public_path(screen) if screen is not None else navigation.HOME_PATH
    action = req.params.get("acao") or ""
    suffix = f"&acao={action}" if _ACTION_TOKEN.fullmatch(action) else ""
    choices = [
        ProjectChoice(
            code=project.code,
            name=project.name,
            url=f"{path}?{scope.QUERY_PARAMETER}={project.id}{suffix}",
        )
        for project in configuracoes.list_projects(session)
    ]
    return AlpineAjaxResponse(
        template_name="nav/escolher_projeto.html",
        context={"opcoes": choices},
        request=req,
    )


@bp.route(route="glossario", methods=["GET"])
@fragment_route
def glossary(req: func.HttpRequest, session: Session) -> func.HttpResponse:
    """Return the siglas and their meanings, read from CONTEXT.md, for the hint (HU-018)."""
    return AlpineAjaxResponse(
        template_name="nav/glossario.html",
        context={"glossario": load_glossary()},
        request=req,
    )


def _rejected_notice(current_scope: scope.Scope, label: str) -> str | None:
    """Say so when the scope asked for does not exist, instead of silently showing other data."""
    if current_scope.rejected is None:
        return None
    return f"O escopo «{current_scope.rejected}» não existe. Mostrando {label}."
