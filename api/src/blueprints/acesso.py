"""Access blueprint — the screen of denied access and the profile switch of the demonstration.

``/api/acesso-negado`` is the screen the shell opens in the place of an address
the person may not open (HU-019): the whole screen, with the Design System's
guard, and the reason in words — a screen outside the profile or the bond, a
session that is missing, or an e-mail that is not in the register of
Colaboradores, in which case it says whom to ask and which account was used
(HU-002, HU-003). The navigation (``/api/nav``) is what sends the shell here;
the route answers 403, like every refusal.

``/api/demonstracao/perfil`` is the profile selector of the demonstration mode
(HU-004): it remembers in a cookie which collaborator the evaluator picked, so
the next requests resolve that person (``core.auth``). It exists only in
demonstration and only while there is no Microsoft login; in production it is
refused.
"""

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import auth, navigation, rbac, scope
from src.core.errors import AccessDeniedError, DomainError
from src.core.responses import AlpineAjaxResponse, redirect_to
from src.core.routing import OPEN, Access, RequestContext, fragment_route

bp = func.Blueprint()

HOME_ACTION_LABEL = "Voltar ao início"
SIGN_IN_ACTION_LABEL = "Entrar com a conta Microsoft"
OTHER_ACCOUNT_ACTION_LABEL = "Entrar com outra conta"


def _guard_context(error: AccessDeniedError) -> dict[str, object]:
    """What the guard prints for each kind of refusal."""
    if isinstance(error, auth.NotRegisteredError):
        return {
            "titulo": "Acesso negado",
            "mensagem": str(error),
            "orientacao": auth.ORIENTATION if error.email else None,
            "email": error.email,
            "acao_url": "/.auth/logout",
            "acao_rotulo": OTHER_ACCOUNT_ACTION_LABEL,
        }
    if isinstance(error, auth.SignInRequiredError):
        return {
            "titulo": "Entre para continuar",
            "mensagem": str(error),
            "acao_url": "/.auth/login/aad",
            "acao_rotulo": SIGN_IN_ACTION_LABEL,
        }
    return {
        "titulo": "Acesso negado",
        "mensagem": str(error),
        "acao_url": navigation.HOME_PATH,
        "acao_rotulo": HOME_ACTION_LABEL,
        "acao_tela": True,
    }


def _denied_screen(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """Draw the guard, with 403, for any refusal of access; other errors keep the common fragment."""
    if not isinstance(error, AccessDeniedError):
        return None
    return AlpineAjaxResponse(
        template_name="comum/acesso_negado.html",
        context=_guard_context(error),
        request=req,
        status_code=403,
    )


@bp.route(route="acesso-negado", methods=["GET"])
@fragment_route(access=Access(), on_error=_denied_screen)
def denied_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Say why the person may not open the address; a person who may is sent to the screen."""
    screen = navigation.screen_for_path(req.params.get("caminho"))
    if screen is None:
        return redirect_to(navigation.HOME_PATH)
    rbac.require_screen(context.user, screen)
    return redirect_to(navigation.scoped_url(screen, context.scope.parameter))


@bp.route(route="demonstracao/perfil", methods=["POST"])
@fragment_route(access=OPEN)
def switch_demo_profile(req: func.HttpRequest, session: Session) -> func.HttpResponse:
    """Remember the person the evaluator picked in the profile selector (demonstration only)."""
    auth.require_demo_selector(req)
    chosen = auth.choose_demo_collaborator(session, req.form.get("colaborador"))
    response = func.HttpResponse("")
    response.headers["Set-Cookie"] = auth.demo_cookie_header(
        chosen.id, secure=scope.is_secure_request(req)
    )
    return response
