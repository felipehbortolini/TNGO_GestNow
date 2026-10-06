"""Who may do what in the Weekly Scheduling, decided on the server (D7, D10).

The app's profiles become the two axes of D7. The Weekly Scheduling roles (Planejador,
Fiscal, Encarregado, Fornecedor) are given per project and count only in the project
they were given in; the Admin of the general profile does everything, in every
project; a supplier has no general axis at all, so for it everything comes from its
roles. A Visualizador may well be Planejador: the axes are independent.

| Ação | Quem |
|---|---|
| Criar atividade | Planejador, Fornecedor ou Admin |
| Editar atividade | Planejador, Fiscal, Fornecedor ou Admin |
| Validar a programação e definir o fiscal | Planejador ou Admin |
| Lançar o realizado | Encarregado, Fornecedor ou Admin |
| Aprovar ou reabrir o realizado | O Fiscal da atividade ou Admin |
| Publicar (e editar o publicado) | Planejador ou Admin |
| Excluir atividade | Admin |

Pure functions over ``rbac.User``: the facade calls them, the screen only draws what
they allow.
"""

from __future__ import annotations

from src.core import rbac
from src.core.rbac import Permission, ScheduleRole, User

CREATE_DENIED = "Seu perfil não cria programação."
EDIT_DENIED = "Seu perfil não edita programação."
PUBLISHED_LOCKED = "Programação publicada não pode ser editada."
DELETE_DENIED = "Somente o Administrador exclui atividades."
VALIDATE_DENIED = "Seu perfil não valida programação."
REPORT_DENIED = "Seu perfil não registra o realizado."
APPROVE_DENIED = "Somente o fiscal responsável pela atividade aprova o realizado."
REOPEN_DENIED = "Somente o fiscal responsável pela atividade reabre o realizado."
PUBLISH_DENIED = "Seu perfil não publica programação."


def is_admin(user: User) -> bool:
    """Whether the general profile is Admin (a supplier never is: it has no general axis)."""
    return rbac.can(user, Permission.ADMINISTER)


def can_create(user: User, project_id: int) -> bool:
    """Whether the user may create activities in the project."""
    return is_admin(user) or rbac.has_schedule_role(
        user, project_id, ScheduleRole.PLANNER, ScheduleRole.SUPPLIER
    )


def can_create_somewhere(user: User) -> bool:
    """Whether the user may create in some project: what the Portfólio button asks before it picks one."""
    if is_admin(user):
        return True
    creators = {ScheduleRole.PLANNER, ScheduleRole.SUPPLIER}
    return any(role in creators for _project_id, role in user.schedule_roles)


def can_edit(user: User, project_id: int) -> bool:
    """Whether the user may edit activities in the project."""
    return is_admin(user) or rbac.has_schedule_role(
        user, project_id, ScheduleRole.PLANNER, ScheduleRole.INSPECTOR, ScheduleRole.SUPPLIER
    )


def can_publish(user: User, project_id: int) -> bool:
    """Whether the user may publish in the project: the one who may also edit the published."""
    return is_admin(user) or rbac.has_schedule_role(user, project_id, ScheduleRole.PLANNER)


def can_validate(user: User, project_id: int) -> bool:
    """Whether the user may validate the programming and name the inspector."""
    return is_admin(user) or rbac.has_schedule_role(user, project_id, ScheduleRole.PLANNER)


def can_report(user: User, project_id: int) -> bool:
    """Whether the user may report the done: the foreman and the supplier (and the Admin)."""
    return is_admin(user) or rbac.has_schedule_role(
        user, project_id, ScheduleRole.FOREMAN, ScheduleRole.SUPPLIER
    )


def can_approve(user: User, project_id: int, inspector_id: int | None) -> bool:
    """Whether the user approves (or reopens) the done of an activity: its own inspector, or the Admin."""
    if is_admin(user):
        return True
    has_role = rbac.has_schedule_role(user, project_id, ScheduleRole.INSPECTOR)
    return has_role and inspector_id is not None and inspector_id == user.person_id


def can_delete(user: User) -> bool:
    """Whether the user may delete an activity: the Admin only."""
    return is_admin(user)


def is_supplier(user: User) -> bool:
    """Whether the window of a company binds the user: the supplier bond."""
    return user.bond is rbac.Bond.SUPPLIER
