"""The single fragment-route decorator: gate, user, scope, permission and domain errors (D14).

Every screen endpoint goes through here, so no route repeats the gate,
forgets the transaction or invents its own error shape. The handler
receives ``(req, session)`` and works inside one transaction: the facade
of the owning module writes with that session, and the whole request
commits or rolls back together — including integrations between modules
(D5).

``access`` is the other half of D14 (ISSUE-011): a route that declares what it
demands of the caller (an ``Access``) gets the collaborator behind the request
resolved by ``core.auth``, the scope of the request resolved by ``core.scope``,
and the module and the permission checked by ``core.rbac``, all before the
handler runs. The handler then receives ``(req, session, context)``, where the
``RequestContext`` carries the ``user`` and the ``scope`` to hand to the facade.
A caller that may not gets 403 with the message for the screen. A route
decorated without ``access`` — or with ``OPEN`` — resolves no user: that is for
the platform routes that must work for someone the register does not know yet
(the profile switch of the demonstration); every route of a module declares its
``Access``, and a test guards it.

``on_error`` lets a screen that owns a form re-render it filled with what
the person typed (422 and 409); returning ``None`` falls back to the
common error fragment.

``download_route`` is the exception of the Padrão (D14, ISSUE-017): a route
that answers with a file (the Excel of a screen, an attachment) and not with a
fragment. The browser asks for a file without the Alpine header, so the gate
does not apply, but everything else does: the same ``Access``, the same user
and scope, the same transaction and the same error map. A download that is
refused answers 403 with the message in the toast header, like any route.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import auth, database, rbac
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.rbac import Permission, User
from src.core.responses import AlpineAjaxResponse, is_alpine_request, redirect_to
from src.core.scope import Scope, scope_of

ErrorRenderer = Callable[[func.HttpRequest, DomainError], func.HttpResponse | None]

# The attribute of a decorated function that carries its ``Access``, so a test
# can prove that every registered route declared one.
ACCESS_ATTRIBUTE = "access"


@dataclass(frozen=True)
class Access:
    """What a route demands of its caller (D14).

    ``identity`` is whether a collaborator of the register must be behind the
    request; the default is yes. ``module`` is the folder of the module the
    route belongs to (``financeiro``): the caller must reach it, which already
    means reading it and applies the cut by bond. ``permission`` is what the
    route asks beyond reading: ``Permission.WRITE`` for a route that saves,
    ``Permission.MANAGE`` for one that approves. Both are optional: a platform
    route may ask only for identity.
    """

    identity: bool = True
    module: str | None = None
    permission: Permission | None = None


# For the routes that resolve no user: the explicit way to say so.
OPEN = Access(identity=False)


@dataclass(frozen=True)
class RequestContext:
    """What a route with ``access`` hands to its handler: the user and the scope."""

    user: User
    scope: Scope


def authorize(session: Session, req: func.HttpRequest, access: Access) -> RequestContext:
    """Resolve the user and the scope of the request and check the access it declares.

    Raises ``AccessDeniedError`` (403) when the caller is not in the register,
    does not reach the module or lacks the permission.
    """
    user = auth.resolve_user(session, req)
    if access.module is not None:
        rbac.require_module(user, access.module)
    if access.permission is not None:
        rbac.require(user, access.permission)
    return RequestContext(user=user, scope=scope_of(session, req))


def error_response(error: DomainError, req: func.HttpRequest) -> func.HttpResponse:
    """Render a domain error into the fragment the screen expects: 403, 409 or 422."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        status_code=_status_for(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


def fragment_route(
    handler: Callable | None = None,
    *,
    on_error: ErrorRenderer | None = None,
    access: Access | None = None,
):
    """Decorate a fragment endpoint with the gate, the transaction, the access and the error map."""

    def decorator(endpoint: Callable) -> Callable:
        @functools.wraps(endpoint)
        def wrapper(req: func.HttpRequest) -> func.HttpResponse:
            if not is_alpine_request(req):
                return redirect_to("/index.html")
            try:
                with database.unidade_de_trabalho() as session:
                    if access is None or not access.identity:
                        return endpoint(req, session)
                    return endpoint(req, session, authorize(session, req, access))
            except DomainError as error:
                if on_error is not None:
                    resposta = on_error(req, error)
                    if resposta is not None:
                        return resposta
                return error_response(error, req)

        _present_as_azure_function(wrapper, access)
        return wrapper

    if handler is not None:
        return decorator(handler)
    return decorator


def download_route(*, access: Access) -> Callable[[Callable], Callable]:
    """Decorate a download endpoint: no Alpine gate, but the same access as any route (D14).

    The handler receives ``(req, session, context)`` and returns the file
    (``responses.file_response``). Unlike a fragment route, ``access`` is
    required: a download that does not say who may take it is a mistake, so
    the user is always resolved and the module and the permission always
    checked before the handler runs.
    """

    def decorator(endpoint: Callable) -> Callable:
        @functools.wraps(endpoint)
        def wrapper(req: func.HttpRequest) -> func.HttpResponse:
            try:
                with database.unidade_de_trabalho() as session:
                    return endpoint(req, session, authorize(session, req, access))
            except DomainError as error:
                return error_response(error, req)

        _present_as_azure_function(wrapper, access)
        return wrapper

    return decorator


# The Azure Functions worker reads the signature of the registered function and
# binds each parameter to a binding of the trigger: ``req`` is the HTTP
# trigger, and a parameter without a binding is refused when the host indexes
# the app. ``functools.wraps`` makes ``inspect.signature`` follow ``__wrapped__``
# to the endpoint, whose ``session`` and ``context`` have no binding. Fixing the
# signature to ``req`` alone shows the worker the function it expects.
_FUNCTION_SIGNATURE = inspect.Signature(
    [
        inspect.Parameter(
            "req", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=func.HttpRequest
        )
    ],
    return_annotation=func.HttpResponse,
)


def _present_as_azure_function(wrapper: Callable[..., Any], access: Access | None) -> None:
    """Make the wrapper look like the plain ``(req)`` function and carry its ``Access``."""
    wrapper.__dict__["__signature__"] = _FUNCTION_SIGNATURE
    wrapper.__annotations__ = {"req": func.HttpRequest, "return": func.HttpResponse}
    wrapper.__dict__[ACCESS_ATTRIBUTE] = access


def _status_for(error: DomainError) -> int:
    if isinstance(error, AccessDeniedError):
        return 403
    if isinstance(error, VersionConflictError):
        return 409
    return 422
