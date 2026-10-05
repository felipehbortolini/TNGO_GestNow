"""Who is calling: the Static Web Apps principal in Azure, the profile selector in demonstration (D7).

The identity of a request comes from one of two places, never both:

* **The principal that Static Web Apps hands to the API** in the
  ``x-ms-client-principal`` header (base64 of a JSON; the e-mail is
  ``userDetails``). The provider accepts any Microsoft account, so having an
  account proves nothing: the **register of Colaboradores is the source of
  truth** of who enters. An e-mail outside the register, or switched off in it,
  is refused with the screen of denied access, which says whom to ask. Whenever
  the header is present it decides, even in demonstration; a malformed one is
  refused, never replaced by the selector.
* **The profile selector of the demonstration mode** (``GESTNOW_MODO`` unset or
  ``demonstracao``), only while there is no principal. The sidebar lets the
  evaluator pick any active collaborator; the choice is the id in the
  ``gestnow_demo_perfil`` cookie, written by ``/api/demonstracao/perfil``. With
  no choice the demonstration enters as the first active Admin. In production the
  selector does not exist and the cookie is ignored: no principal means no
  entry.

The result is the ``User`` of ``core.rbac`` — profile, bond, company and the
Weekly Scheduling roles per project — which the route decorator hands to the
facades. The header is trusted because the API is reachable only through Static
Web Apps, which sets it (the publication guide, ISSUE-092, confirms it).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeGuard

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import config
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import Bond, GeneralProfile, ScheduleRole, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.service import CollaboratorAccess

PRINCIPAL_HEADER = "x-ms-client-principal"
DEMO_COOKIE = "gestnow_demo_perfil"

# A collaborator id never has more digits than this; the cap keeps ``int`` away
# from absurd input that comes straight from a cookie or a form.
MAX_ID_DIGITS = 18

# The orientation of the screen of denied access (HU-003): the register is
# kept by the administrators, so they are who releases an e-mail.
ORIENTATION = (
    "Peça a um administrador do GestNow para cadastrar o seu e-mail em "
    "Configurações > Colaboradores. Depois de cadastrado, é só entrar de novo."
)
SIGN_IN_MESSAGE = "Entre com a sua conta Microsoft para continuar."
NOT_REGISTERED_MESSAGE = "Este e-mail não está cadastrado no GestNow."
INACTIVE_MESSAGE = "O seu acesso ao GestNow está desativado."
UNKNOWN_PROFILE_MESSAGE = (
    "O seu cadastro tem um perfil, vínculo ou papel que o GestNow não conhece."
)
EMPTY_REGISTER_MESSAGE = (
    "Nenhum colaborador ativo no cadastro. Rode a carga de demonstração para criar as pessoas."
)
DEMO_ONLY_MESSAGE = "A troca de perfil só existe no modo demonstração, sem login Microsoft."
DEMO_CHOICE_MESSAGE = "Escolha uma pessoa cadastrada e ativa."


class SignInRequiredError(AccessDeniedError):
    """There is no valid identity in the request: the person has to sign in."""

    def __init__(self) -> None:
        super().__init__(SIGN_IN_MESSAGE)


class NotRegisteredError(AccessDeniedError):
    """The e-mail is not in the register of Colaboradores, or its access was switched off.

    ``email`` is the account the person used, so the screen can tell the
    administrator which e-mail to register; it is ``None`` when there is none
    (demonstration with an empty register).
    """

    def __init__(self, email: str | None, message: str = NOT_REGISTERED_MESSAGE) -> None:
        self.email = email
        super().__init__(message)


@dataclass(frozen=True)
class DemoChoice:
    """One person of the demonstration selector: the id of the collaborator and the label."""

    id: int
    label: str


@dataclass(frozen=True)
class DemoSelector:
    """The demonstration selector as the sidebar prints it: the people and who is active."""

    options: tuple[DemoChoice, ...]
    current_id: int


# ── The request ──────────────────────────────────────────────────────────


def principal_email(req: func.HttpRequest) -> str | None:
    """The e-mail of the Static Web Apps principal, or ``None`` when the header is absent.

    A header that is not base64 of a JSON, or that carries no e-mail, is
    refused: it never falls back to another identity.
    """
    raw = req.headers.get(PRINCIPAL_HEADER)
    if not raw:
        return None
    email = _email_of(_decode_principal(raw))
    if email is None:
        raise SignInRequiredError
    return email


def resolve_user(session: Session, req: func.HttpRequest) -> User:
    """The collaborator behind the request, or the refusal that sends the person to the right screen.

    Raises ``SignInRequiredError`` without identity and ``NotRegisteredError``
    for an e-mail outside the register or an inactive collaborator (both are
    403, ``AccessDeniedError``).
    """
    email = principal_email(req)
    if email is not None:
        return _registered_user(session, email)
    if config.app_mode() == config.DEMONSTRATION:
        return _demonstration_user(session, req)
    raise SignInRequiredError


# ── The demonstration selector ───────────────────────────────────────────


def demo_selector_enabled(req: func.HttpRequest) -> bool:
    """Whether the selector exists: demonstration mode and no Static Web Apps principal."""
    return config.app_mode() == config.DEMONSTRATION and not req.headers.get(PRINCIPAL_HEADER)


def require_demo_selector(req: func.HttpRequest) -> None:
    """Refuse with 403 when the selector does not exist (production, or a real login)."""
    if not demo_selector_enabled(req):
        raise AccessDeniedError(DEMO_ONLY_MESSAGE)


def demo_selector(session: Session, req: func.HttpRequest, user: User) -> DemoSelector | None:
    """The selector the sidebar prints for the user, or ``None`` when it does not exist."""
    if not demo_selector_enabled(req):
        return None
    options = tuple(
        DemoChoice(id=access.id, label=f"{access.name} · {access.general_profile} · {access.bond}")
        for access in configuracoes.list_active_access(session)
    )
    return DemoSelector(options=options, current_id=user.id)


def choose_demo_collaborator(session: Session, raw_id: str | None) -> CollaboratorAccess:
    """The active collaborator the person picked, or 422 when the choice names nobody."""
    access = configuracoes.find_access(session, int(raw_id)) if _is_id(raw_id) else None
    if access is None or not access.active:
        raise InvalidDataError({"colaborador": DEMO_CHOICE_MESSAGE})
    return access


def demo_cookie_header(collaborator_id: int, *, secure: bool) -> str:
    """The ``Set-Cookie`` value that remembers the chosen person for the browser session.

    ``HttpOnly`` because only the server reads it; no ``Max-Age``, so the
    choice lasts until the browser closes and the next visit starts as Admin.
    """
    attributes = [f"{DEMO_COOKIE}={collaborator_id}", "Path=/", "SameSite=Lax", "HttpOnly"]
    if secure:
        attributes.append("Secure")
    return "; ".join(attributes)


# ── Reading the principal ────────────────────────────────────────────────


def _decode_principal(raw: str) -> Mapping[str, Any]:
    try:
        data = json.loads(base64.b64decode(raw, validate=True))
    except ValueError:
        # Not base64, not UTF-8 or not JSON: all subclasses of ValueError.
        raise SignInRequiredError from None
    return data if isinstance(data, Mapping) else {}


def _email_of(principal: Mapping[str, Any]) -> str | None:
    """The e-mail of the principal: ``userDetails``, when it looks like one."""
    details = principal.get("userDetails")
    if not isinstance(details, str):
        return None
    email = details.strip().lower()
    return email if "@" in email and " " not in email else None


# ── Reading the register ─────────────────────────────────────────────────


def _registered_user(session: Session, email: str) -> User:
    access = configuracoes.find_access_by_email(session, email)
    if access is None:
        raise NotRegisteredError(email)
    if not access.active:
        raise NotRegisteredError(email, INACTIVE_MESSAGE)
    return _user_of(access)


def _demonstration_user(session: Session, req: func.HttpRequest) -> User:
    """The person chosen in the selector, or the first active Admin when nobody was chosen."""
    chosen_id = _cookie_id(req)
    if chosen_id is not None:
        chosen = configuracoes.find_access(session, chosen_id)
        if chosen is not None and chosen.active:
            return _user_of(chosen)
    admin = next(
        (
            access
            for access in configuracoes.list_active_access(session)
            if access.general_profile == GeneralProfile.ADMIN
        ),
        None,
    )
    if admin is None:
        raise NotRegisteredError(None, EMPTY_REGISTER_MESSAGE)
    return _user_of(admin)


def _user_of(access: CollaboratorAccess) -> User:
    """The ``User`` of a collaborator; a value the platform does not know is refused (fails closed)."""
    try:
        profile = GeneralProfile(access.general_profile)
        bond = Bond(access.bond)
        roles = frozenset(
            (project_id, ScheduleRole(role)) for project_id, role in access.schedule_roles
        )
    except ValueError:
        raise NotRegisteredError(access.email, UNKNOWN_PROFILE_MESSAGE) from None
    return User(
        id=access.id,
        person_id=access.person_id,
        name=access.name,
        email=access.email,
        general_profile=profile,
        bond=bond,
        company_id=access.company_id,
        schedule_roles=roles,
    )


def _cookie_id(req: func.HttpRequest) -> int | None:
    """The collaborator id in the demonstration cookie, or ``None`` when absent or not a number."""
    header = req.headers.get("Cookie") or ""
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == DEMO_COOKIE and _is_id(value):
            return int(value)
    return None


def _is_id(value: str | None) -> TypeGuard[str]:
    """Whether the text is a plain id; the cap keeps ``int`` away from absurd input."""
    return (
        value is not None and value.isascii() and value.isdecimal() and len(value) <= MAX_ID_DIGITS
    )
