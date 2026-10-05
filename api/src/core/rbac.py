"""Permissions on two axes, decided on the server and never on the screen (D7).

The **general profile** (Visualizador, Membro, Gestor or Admin: one, required)
governs modules 01 to 08, Início, the report and Configurações through *sets of
permissions*: each profile maps to the permissions it holds, and a facade or a
route asks for the one it needs. The **Weekly Scheduling roles** (Planejador,
Fiscal, Encarregado, Fornecedor: zero or more) are given per project and count
only in the project where they were given. The two axes are independent: a
Visualizador may be Planejador, and the profile says nothing about the roles.

The **bond** cuts the access before any permission is read (D7). A Fornecedor
sees only the Programação Semanal, and in it only its own company, so a
supplier holds no general permission at all and every other module answers
403; a Cliente and a Timenow collaborator see what the general profile allows.

Everything here is pure: it takes the ``User`` that the login resolved
(``core.auth``) and either answers a boolean, which the navigation uses to
decide what to show, or raises ``AccessDeniedError`` — 403 with the message the
person reads (D14). The facade of each module calls these functions itself:
the cut by bond is applied on the server, in the facade, never on the screen.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from src.core.errors import AccessDeniedError
from src.core.navigation import Screen


class GeneralProfile(StrEnum):
    """The general profile of a collaborator (``colaborador.perfil_geral``)."""

    VIEWER = "Visualizador"
    MEMBER = "Membro"
    MANAGER = "Gestor"
    ADMIN = "Admin"


class Bond(StrEnum):
    """The relation of the collaborator with the organization (``colaborador.vinculo``)."""

    TIMENOW = "Timenow"
    SUPPLIER = "Fornecedor"
    CLIENT = "Cliente"


class ScheduleRole(StrEnum):
    """A Weekly Scheduling role, given per project (``colaborador_papel_programacao.papel``)."""

    PLANNER = "Planejador"
    INSPECTOR = "Fiscal"
    FOREMAN = "Encarregado"
    SUPPLIER = "Fornecedor"


class Permission(StrEnum):
    """What a facade or a route may ask of the general profile."""

    # Read the screens and the records of a module.
    VIEW = "ver"
    # Create and edit records.
    WRITE = "gravar"
    # Approve, decide, close, delete and reverse: the steps that need a manager.
    MANAGE = "gerir"
    # Read the restricted HSE fields and their attachments (LGPD, Q35).
    VIEW_RESTRICTED = "ver_restrito"
    # Open Configurações and edit its parameters.
    CONFIGURE = "configurar"
    # Administer people and registers: Colaboradores and the Admin-only steps.
    ADMINISTER = "administrar"


_MEMBER_PERMISSIONS = frozenset({Permission.VIEW, Permission.WRITE})
_MANAGER_PERMISSIONS = _MEMBER_PERMISSIONS | {
    Permission.MANAGE,
    Permission.VIEW_RESTRICTED,
    Permission.CONFIGURE,
}

PROFILE_PERMISSIONS: Mapping[GeneralProfile, frozenset[Permission]] = MappingProxyType(
    {
        GeneralProfile.VIEWER: frozenset({Permission.VIEW}),
        GeneralProfile.MEMBER: _MEMBER_PERMISSIONS,
        GeneralProfile.MANAGER: _MANAGER_PERMISSIONS,
        GeneralProfile.ADMIN: frozenset(Permission),
    }
)

# The only module a supplier reaches (D7): the folder of the Programação Semanal.
SUPPLIER_MODULES = frozenset({"programacao_semanal"})

# What a module asks beyond reading it, by the folder of the module; the
# modules that are not here ask only for ``VIEW``. Configurações appears only
# for Gestor and Admin (HU-007).
MODULE_PERMISSION: Mapping[str, Permission] = MappingProxyType(
    {"configuracoes": Permission.CONFIGURE}
)

# What one screen asks beyond its module, by screen key (``<module>/<id>``).
# Colaboradores is Admin only: it is where access is granted and revoked.
SCREEN_PERMISSION: Mapping[str, Permission] = MappingProxyType(
    {"configuracoes/colaboradores": Permission.ADMINISTER}
)

SUPPLIER_SCOPE_MESSAGE = "O acesso de fornecedor é só à Programação Semanal da própria empresa."
COMPANY_MISSING_MESSAGE = (
    "O seu cadastro de fornecedor está sem empresa. Peça a um administrador para corrigi-lo."
)
OWN_COMPANY_MESSAGE = "Você acessa apenas os dados da sua empresa."


@dataclass(frozen=True)
class User:
    """The collaborator behind a request: who, with which profile, bond and roles.

    ``id`` is the collaborator (the author of every trail line) and
    ``person_id`` is the person of the register (the one the records point
    to, for the segregation of duties). ``schedule_roles`` holds one
    ``(project_id, role)`` pair per role given.
    """

    id: int
    person_id: int
    name: str
    email: str
    general_profile: GeneralProfile
    bond: Bond
    company_id: int | None = None
    schedule_roles: frozenset[tuple[int, ScheduleRole]] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Conflict:
    """A person who already did a step that the step being done may not share (D7).

    ``person_id`` is the person of the register who did the other step, or
    ``None`` when nobody did it yet (then there is no conflict); ``message``
    is what the screen shows when the refusal happens.
    """

    person_id: int | None
    message: str


# ── General profile ──────────────────────────────────────────────────────


def can(user: User, permission: Permission) -> bool:
    """Whether the general profile grants the permission; a supplier has no general axis."""
    if user.bond is Bond.SUPPLIER:
        return False
    return permission in PROFILE_PERMISSIONS[user.general_profile]


def require(user: User, permission: Permission) -> None:
    """Refuse with 403 when the user lacks the permission; the message says who may."""
    if not can(user, permission):
        raise AccessDeniedError(_denial_message(user, permission))


# ── Modules and screens ──────────────────────────────────────────────────


def can_use_module(user: User, module: str) -> bool:
    """Whether the user reaches a module, by the folder of the module (``financeiro``)."""
    if user.bond is Bond.SUPPLIER:
        return module in SUPPLIER_MODULES
    return can(user, _module_permission(module))


def require_module(user: User, module: str) -> None:
    """Refuse with 403 when the user does not reach the module."""
    if not can_use_module(user, module):
        raise AccessDeniedError(_denial_message(user, _module_permission(module)))


def can_open_screen(user: User, screen: Screen) -> bool:
    """Whether the user may open a screen: its module and, if it has one, its own permission."""
    if not can_use_module(user, screen.module):
        return False
    required = SCREEN_PERMISSION.get(screen.key)
    return required is None or can(user, required)


def require_screen(user: User, screen: Screen) -> None:
    """Refuse with 403, naming the screen, when the user may not open it."""
    if not can_open_screen(user, screen):
        raise AccessDeniedError(_screen_message(user, screen))


# ── Bond: the company of a supplier ──────────────────────────────────────


def company_scope(user: User) -> int | None:
    """The company a query must be cut to: the supplier's own, ``None`` for everyone else.

    A supplier without a company is refused instead of seeing everything: the
    cut by bond fails closed.
    """
    if user.bond is not Bond.SUPPLIER:
        return None
    if user.company_id is None:
        raise AccessDeniedError(COMPANY_MISSING_MESSAGE)
    return user.company_id


def require_company(user: User, company_id: int | None) -> None:
    """Refuse with 403 when a supplier reaches for the data of another company."""
    own = company_scope(user)
    if own is not None and own != company_id:
        raise AccessDeniedError(OWN_COMPANY_MESSAGE)


# ── Weekly Scheduling roles, per project ─────────────────────────────────


def schedule_roles_in(user: User, project_id: int) -> frozenset[ScheduleRole]:
    """The Weekly Scheduling roles the user holds in one project, and only in it."""
    return frozenset(role for given_in, role in user.schedule_roles if given_in == project_id)


def has_schedule_role(user: User, project_id: int, *roles: ScheduleRole) -> bool:
    """Whether the user holds at least one of the roles in the project."""
    return not schedule_roles_in(user, project_id).isdisjoint(roles)


def require_schedule_role(user: User, project_id: int, *roles: ScheduleRole) -> None:
    """Refuse with 403 when the user holds none of the roles in the project."""
    if not has_schedule_role(user, project_id, *roles):
        wanted = _alternatives([role.value for role in roles])
        message = f"Esta operação exige o papel de {wanted} na Programação Semanal deste projeto."
        raise AccessDeniedError(message)


# ── Segregation of duties ────────────────────────────────────────────────


def require_segregation(user: User, *conflicts: Conflict) -> None:
    """Refuse with 403 when the user is one of the people the step may not share (D7).

    Who elaborates does not approve; who answers for a plan does not approve
    it; who validates a lesson is not its author; who verifies is not who
    executed. Each conflict carries the person who did the other step and
    the message of the refusal, so a step with two conflicts (the approver of
    an award is neither the buyer nor who recommended) lists both.
    """
    for conflict in conflicts:
        if conflict.person_id is not None and conflict.person_id == user.person_id:
            raise AccessDeniedError(conflict.message)


# ── Messages ─────────────────────────────────────────────────────────────


def _module_permission(module: str) -> Permission:
    return MODULE_PERMISSION.get(module, Permission.VIEW)


def _alternatives(names: Sequence[str]) -> str:
    """How a message lists who may: ``A``, ``A ou B``, ``A, B ou C``."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} ou {names[-1]}"


def _holders(permission: Permission) -> str:
    """The profiles that hold the permission, as a message lists them."""
    names = [
        profile.value for profile in GeneralProfile if permission in PROFILE_PERMISSIONS[profile]
    ]
    return _alternatives(names)


def _denial_message(user: User, permission: Permission) -> str:
    if user.bond is Bond.SUPPLIER:
        return SUPPLIER_SCOPE_MESSAGE
    return (
        f"Esta operação exige o perfil {_holders(permission)}. "
        f"O seu perfil é {user.general_profile}."
    )


def _screen_message(user: User, screen: Screen) -> str:
    if user.bond is Bond.SUPPLIER:
        return SUPPLIER_SCOPE_MESSAGE
    required = SCREEN_PERMISSION.get(screen.key) or _module_permission(screen.module)
    return (
        f"A tela «{screen.title}» exige o perfil {_holders(required)}. "
        f"O seu perfil é {user.general_profile}."
    )
