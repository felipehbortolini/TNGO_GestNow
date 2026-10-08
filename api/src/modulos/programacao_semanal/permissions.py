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
| Lançar o realizado (turno dia e noite) | Encarregado, Fornecedor ou Admin |
| Aprovar e reabrir o realizado | Fiscal ou Admin |
| Publicar (e editar o publicado) | Planejador ou Admin |
| Excluir atividade | Admin |
| Decidir pedido de alteração | Planejador ou Admin |
| Editar a configuração (parâmetros e janelas) | Planejador no projeto ou Admin |
| Ver a trilha de auditoria | Planejador no projeto, Admin fora dele |

``next_action`` is the queue of the five steps in the order of the process
(``validar`` → ``lancar`` → ``aprovar`` → ``publicar`` → ``ver``): the one thing
the person looking at the row should do with it right now, resolved from the roles
and the state. The profile with no step falls in ``ver``, which is all it does.

Pure functions over ``rbac.User``: the facade calls them, the screen only draws what
they allow.
"""

from __future__ import annotations

from src.core import rbac
from src.core.rbac import Permission, ScheduleRole, User
from src.modulos.programacao_semanal import calculations

CREATE_DENIED = "Seu perfil não cria programação."
EDIT_DENIED = "Seu perfil não edita programação."
SETTINGS_DENIED = "Só o Planejador deste projeto ou o Admin alteram a configuração da programação."
VALIDATE_DENIED = "Seu perfil não valida programação."
REPORT_DENIED = "Seu perfil não registra o realizado."
APPROVE_DENIED = "Seu perfil não aprova o realizado."
REOPEN_DENIED = "Seu perfil não reabre o realizado."
PUBLISH_DENIED = "Seu perfil não publica programação."
PUBLISHED_LOCKED = "Programação publicada não pode ser editada."
IMPORT_DENIED = "Só o Planejador deste projeto ou o Admin importam a planilha da semana."
DECIDE_DENIED = "Seu perfil não decide pedidos de alteração."
TRAIL_DENIED = "Seu perfil não vê a trilha de auditoria da programação."
DELETE_DENIED = "Somente o Administrador exclui atividades."

ACTION_VALIDATE = "validar"
ACTION_REPORT = "lancar"
ACTION_APPROVE = "aprovar"
ACTION_PUBLISH = "publicar"
ACTION_VIEW = "ver"
ACTIONS = (ACTION_VALIDATE, ACTION_REPORT, ACTION_APPROVE, ACTION_PUBLISH, ACTION_VIEW)


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


def can_validate(user: User, project_id: int) -> bool:
    """Whether the user may validate the programming and name the inspector."""
    return is_admin(user) or rbac.has_schedule_role(user, project_id, ScheduleRole.PLANNER)


def can_report(user: User, project_id: int) -> bool:
    """Whether the user may report the done work, day and night shift."""
    return is_admin(user) or rbac.has_schedule_role(
        user, project_id, ScheduleRole.FOREMAN, ScheduleRole.SUPPLIER
    )


def can_approve(user: User, project_id: int) -> bool:
    """Whether the user may approve (and reopen) the reported work."""
    return is_admin(user) or rbac.has_schedule_role(user, project_id, ScheduleRole.INSPECTOR)


def can_publish(user: User, project_id: int) -> bool:
    """Whether the user may publish in the project: the one who may also edit the published."""
    return is_admin(user) or rbac.has_schedule_role(user, project_id, ScheduleRole.PLANNER)


def can_delete(user: User) -> bool:
    """Whether the user may delete an activity: the Admin only."""
    return is_admin(user)


def can_decide_requests(user: User, project_id: int) -> bool:
    """Whether the user applies or refuses change requests: the Planner or the Admin."""
    return is_admin(user) or rbac.has_schedule_role(user, project_id, ScheduleRole.PLANNER)


def can_manage_settings(user: User, project_id: int) -> bool:
    """Whether the user edits the project's configuration: the Planner or the Admin (D10)."""
    return is_admin(user) or rbac.has_schedule_role(user, project_id, ScheduleRole.PLANNER)


def can_import(user: User, project_id: int) -> bool:
    """Whether the user imports the week's spreadsheet: the Planner or the Admin, as the app.

    The app gave ``importar`` to the Planejador and the Admin only; the supplier and the
    viewer never import. The role is per project (D7), so the Planner of another project
    does not import here.
    """
    return is_admin(user) or rbac.has_schedule_role(user, project_id, ScheduleRole.PLANNER)


def can_view_trail(user: User, project_id: int | None) -> bool:
    """Whether the user reads the module's audit trail: the Planner in the project, Admin anywhere.

    The app gave ``ver_auditoria`` to the Admin and the Planejador only; the supplier
    never sees the trail. In the Portfólio the roles are per project, so only the Admin.
    """
    if is_admin(user):
        return True
    return project_id is not None and rbac.has_schedule_role(user, project_id, ScheduleRole.PLANNER)


def next_action(
    user: User, project_id: int, *, situation: str, approval: str, has_done: bool
) -> str:
    """The one step of the queue that is this person's turn in this activity, right now.

    Matches the role with the state: the inspector sees ``aprovar`` where the
    supplier sees ``lancar``, and both see ``publicar`` once the done work is
    approved and only the release is missing. Whoever holds no step — the viewer —
    falls in ``ver``.

    **The order of the tests is the order of the flow, not of convenience.**
    ``aprovar`` is checked before ``lancar`` because, when there is done work
    waiting for the inspector, the next step is the approval — including for an
    Admin, who may do both; in the reverse order the Admin's button would offer
    ``lancar`` over a report that is already waiting.

    It is ordering of the screen, not authorisation: the button points at the same
    endpoint as the menu, and every endpoint decides the access by itself.
    """
    draft = situation == calculations.SITUATION_DRAFT
    if can_validate(user, project_id) and draft:
        return ACTION_VALIDATE
    if (
        can_approve(user, project_id)
        and not draft
        and approval == calculations.APPROVAL_PENDING
        and has_done
    ):
        return ACTION_APPROVE
    if can_report(user, project_id) and not draft and approval != calculations.APPROVAL_APPROVED:
        return ACTION_REPORT
    if (
        can_publish(user, project_id)
        and situation == calculations.SITUATION_VALIDATED
        and approval == calculations.APPROVAL_APPROVED
    ):
        return ACTION_PUBLISH
    return ACTION_VIEW


def is_supplier(user: User) -> bool:
    """Whether the window of a company binds the user: the supplier bond."""
    return user.bond is rbac.Bond.SUPPLIER
