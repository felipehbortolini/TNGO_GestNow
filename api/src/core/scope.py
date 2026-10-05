"""Project scope of a request: the Portfólio or one project (D8).

The scope is resolved per request, never stored on the server: the ``projeto``
parameter of the URL wins, then the cookie, and the Portfólio is the default.
The value ``portfolio`` means the whole portfolio; a number is a project id.
A value that names no existing project is not trusted: the resolution falls to
the next source and the rejected text travels in ``Scope.rejected`` so the
screen can say what happened instead of silently showing other data.

This layer is what hands the scope to the facades (D8): a route resolves it
once and passes the ``Scope`` to the facade of its module, which filters by
``project_id`` — or, for a record that must belong to a project, asks
``require_project``. The cookie only remembers the last scope (HU-013); the
URL stays the authority, so two tabs on different projects never mix.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

import azure.functions as func
from sqlalchemy.orm import Session

from src.core.errors import InvalidDataError
from src.modulos.configuracoes import service as configuracoes

QUERY_PARAMETER = "projeto"
COOKIE_NAME = "gestnow_projeto"
PORTFOLIO_PARAMETER = "portfolio"

# One year: the cookie is a convenience, and every navigation renews it.
COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60

# A project id never has more digits than this; the cap keeps ``int`` away
# from absurd inputs coming straight from the URL.
MAX_PROJECT_ID_DIGITS = 18

ScopeSource = Literal["url", "cookie", "padrao"]

PROJECT_REQUIRED_MESSAGE = (
    "Escolha um projeto para incluir o registro: no Portfólio, todo registro pertence a um projeto."
)


@dataclass(frozen=True)
class Scope:
    """Where the data of a request comes from: the Portfólio or one project."""

    project_id: int | None
    source: ScopeSource
    rejected: str | None = None

    @property
    def is_portfolio(self) -> bool:
        """``True`` when the scope is the whole portfolio (no project chosen)."""
        return self.project_id is None

    @property
    def parameter(self) -> str:
        """The value that goes in the URL and in the cookie."""
        return PORTFOLIO_PARAMETER if self.project_id is None else str(self.project_id)

    def require_project(self) -> int:
        """The project id, for a record that must belong to one (D8).

        In the Portfólio there is no project to attach the record to, so the
        facade refuses with a message the screen shows next to the form.
        """
        if self.project_id is None:
            raise InvalidDataError(PROJECT_REQUIRED_MESSAGE)
        return self.project_id


def resolve_scope(req: func.HttpRequest, valid_project_ids: Collection[int]) -> Scope:
    """Resolve the scope of a request: URL, then cookie, then the Portfólio.

    ``valid_project_ids`` are the projects that exist; a numeric value outside
    them is rejected like a malformed one.
    """
    rejected: str | None = None
    candidates: tuple[tuple[ScopeSource, str | None], ...] = (
        ("url", req.params.get(QUERY_PARAMETER)),
        ("cookie", _cookie_value(req)),
    )
    for source, raw in candidates:
        text = (raw or "").strip()
        if not text:
            continue
        value = text.lower()
        if value == PORTFOLIO_PARAMETER:
            return Scope(project_id=None, source=source, rejected=rejected)
        project_id = _project_id(value)
        if project_id is not None and project_id in valid_project_ids:
            return Scope(project_id=project_id, source=source, rejected=rejected)
        rejected = rejected or text
    return Scope(project_id=None, source="padrao", rejected=rejected)


def scope_of(session: Session, req: func.HttpRequest) -> Scope:
    """Resolve the scope against the projects that exist in the database.

    The route calls it and hands the result to the facade of its module; the
    list of projects comes from the facade of Configurações, the owner of the
    project register (D5).
    """
    projects = configuracoes.list_projects(session)
    return resolve_scope(req, {project.id for project in projects})


def cookie_header(scope: Scope, *, secure: bool) -> str:
    """The ``Set-Cookie`` value that remembers the scope (HU-013).

    ``HttpOnly`` because only the server reads it; ``Secure`` when the request
    came over HTTPS (always, in Azure), left off on the local HTTP server.
    """
    attributes = [
        f"{COOKIE_NAME}={scope.parameter}",
        "Path=/",
        f"Max-Age={COOKIE_MAX_AGE_SECONDS}",
        "SameSite=Lax",
        "HttpOnly",
    ]
    if secure:
        attributes.append("Secure")
    return "; ".join(attributes)


def is_secure_request(req: func.HttpRequest) -> bool:
    """Whether the request reached the app over HTTPS, directly or behind the proxy."""
    forwarded = req.headers.get("X-Forwarded-Proto") or ""
    if forwarded.split(",")[0].strip().lower() == "https":
        return True
    return req.url.lower().startswith("https://")


def _project_id(value: str) -> int | None:
    """The id written in ``value``, or ``None`` when it is not a plain number."""
    if not (value.isascii() and value.isdecimal()) or len(value) > MAX_PROJECT_ID_DIGITS:
        return None
    return int(value)


def _cookie_value(req: func.HttpRequest) -> str | None:
    """The scope cookie of the request, read without trusting the rest of the header."""
    header = req.headers.get("Cookie") or ""
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME:
            return value
    return None
