"""The single fragment-route decorator: gate, unit of work and domain errors (D14).

Every screen endpoint goes through here, so no route repeats the gate,
forgets the transaction or invents its own error shape. The handler
receives ``(req, session)`` and works inside one transaction: the facade
of the owning module writes with that session, and the whole request
commits or rolls back together — including integrations between modules
(D5).

``on_error`` lets a screen that owns a form re-render it filled with what
the person typed (422 and 409); returning ``None`` falls back to the
common error fragment. User resolution and permission — the other half of
D14 — arrive with the login in ISSUE-011, which wraps this decorator.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

import azure.functions as func

from src.core import database
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.responses import AlpineAjaxResponse, is_alpine_request, redirect_to

ErrorRenderer = Callable[[func.HttpRequest, DomainError], func.HttpResponse | None]


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


def fragment_route(handler: Callable | None = None, *, on_error: ErrorRenderer | None = None):
    """Decorate a fragment endpoint with the gate, the transaction and the error map."""

    def decorator(endpoint: Callable) -> Callable:
        @functools.wraps(endpoint)
        def wrapper(req: func.HttpRequest) -> func.HttpResponse:
            if not is_alpine_request(req):
                return redirect_to("/index.html")
            try:
                with database.unidade_de_trabalho() as session:
                    return endpoint(req, session)
            except DomainError as error:
                if on_error is not None:
                    resposta = on_error(req, error)
                    if resposta is not None:
                        return resposta
                return error_response(error, req)

        return wrapper

    if handler is not None:
        return decorator(handler)
    return decorator


def _status_for(error: DomainError) -> int:
    if isinstance(error, AccessDeniedError):
        return 403
    if isinstance(error, VersionConflictError):
        return 409
    return 422
