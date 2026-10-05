"""Shell blueprint — the fragments the shell asks for: navigation, scope picker and glossary.

``/api/nav`` serves the sidebar and the module tabs in one multi-target
response, both drawn from the single navigation list (D2) and cut to what the
collaborator behind the request may open (D7). It also resolves the scope of
the request (D8) and remembers it in a cookie, so every navigation leaves the
URL and the cookie in agreement. For someone the register of Colaboradores does
not let in, it answers 403 with a minimal sidebar and the shell opens the
screen of denied access (HU-002, HU-003). ``/api/escopo/projetos`` is the
project choice of the inclusion mechanism, and ``/api/glossario`` feeds the
hint of the siglas (HU-018). Every route here asks only for identity: the
modules' own rules are enforced by their routes and facades.

Add a screen: append one entry to ``api/src/core/navegacao.json``. The icon
name must exist in ``app/ds/icons.js``.
"""

import re
from dataclasses import dataclass

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import auth, navigation, navigation_view, scope
from src.core.errors import AccessDeniedError, DomainError
from src.core.glossary import load_glossary
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, fragment_route
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


def _nav_denied(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The minimal sidebar for someone the register does not let in, with 403 (HU-002, HU-003).

    The two roots the shell asked for come back, so nothing is left empty; the
    sidebar points the shell to the screen of denied access.
    """
    if not isinstance(error, AccessDeniedError):
        return None
    email = error.email if isinstance(error, auth.NotRegisteredError) else None
    return AlpineAjaxResponse(
        template_name="nav/navegacao_negada.html",
        context={
            "email": email,
            "tela": navigation_view.DENIAL_ROUTE,
            "titulo": navigation_view.DENIED_PAGE_TITLE,
        },
        request=req,
        status_code=403,
    )


@bp.route(route="nav", methods=["GET"])
@fragment_route(access=Access(), on_error=_nav_denied)
def main_nav(req: func.HttpRequest, session: Session, context: RequestContext) -> func.HttpResponse:
    """Return the sidebar and the module tabs, and remember the scope in a cookie."""
    projects = configuracoes.list_projects(session)
    demo = auth.demo_selector(session, req, context.user)
    view = navigation_view.build(
        req.params.get("caminho"), context.scope, projects, context.user, demo
    )

    response = AlpineAjaxResponse(
        template_name="nav/navegacao.html",
        context={"nav": view},
        request=req,
        toast=_rejected_notice(context.scope, view.scope_label),
        toast_tipo="aviso",
    )
    response.headers["Set-Cookie"] = scope.cookie_header(
        context.scope, secure=scope.is_secure_request(req)
    )
    return response


@bp.route(route="escopo/projetos", methods=["GET"])
@fragment_route(access=Access())
def choose_project(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
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
@fragment_route(access=Access())
def glossary(req: func.HttpRequest, session: Session, context: RequestContext) -> func.HttpResponse:
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
