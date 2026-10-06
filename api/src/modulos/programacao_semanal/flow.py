"""The five-step flow of an activity and what each person is offered at each step (D10, HU-73 to HU-77).

    elaborar -> validar -> lançar o realizado -> aprovar -> publicar

Each step has its own owner: the supplier writes the programming, the planner validates it
and names the inspector, the foreman or the supplier reports what was done, the inspector
approves it (or reopens it with a reason) and the planner publishes. The rules here are pure:
they receive the state of the activity and what the user may do, and answer. They read no
clock and no database; the facade decides the rights (``permissions``) and writes.

The button of the row is the **next action** of whoever looks, and the menu holds only what
the profile may still do, never the same step twice.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.errors import InvalidDataError
from src.modulos.programacao_semanal import calculations

# The steps a row can offer; ``VIEW`` is the button of whoever has no step to do.
VALIDATE = "validar"
APPROVE = "aprovar"
REPORT = "lancar"
PUBLISH = "publicar"
VIEW = "ver"
REOPEN = "reabrir"
EDIT = "editar"
DELETE = "excluir"
DETAIL = "detalhe"

REPORT_AFTER_APPROVAL = "O realizado já foi aprovado pelo fiscal e não pode mudar."
REPORT_BEFORE_VALIDATION = (
    "A programação ainda não foi validada pelo planejador — não há o que reportar."
)
VALIDATE_ONLY_DRAFT = "Só programação em elaboração pode ser validada."
APPROVE_BEFORE_VALIDATION = "O realizado só chega ao fiscal depois da validação do planejador."
APPROVE_WITHOUT_DONE = "Não há realizado registrado para aprovar."
REOPEN_NOT_APPROVED = "Este realizado não está aprovado."
REOPEN_NEEDS_REASON = "Explique por que está reabrindo o realizado."
PUBLISH_ONLY_VALIDATED = "Só programação validada pode ser publicada."


@dataclass(frozen=True)
class Rights:
    """What the user may do with one activity, as ``permissions`` decided for its project."""

    validate: bool = False
    report: bool = False
    approve: bool = False
    publish: bool = False
    edit: bool = False
    delete: bool = False


@dataclass(frozen=True)
class State:
    """Where the activity is in the flow: its situation, the approval of the done and whether it has done."""

    situation: str
    approval: str
    has_done: bool


@dataclass(frozen=True)
class Actions:
    """The button of the row and the items of its menu, by step."""

    next_action: str = VIEW
    menu: tuple[str, ...] = ()


NO_ACTIONS = Actions()


def next_action(rights: Rights, state: State) -> str:
    """The one step this person should do to this activity now: validate, approve, report, publish or view.

    The order is the order of the flow, not of convenience: approving is tested before
    reporting because, when a done is waiting for the inspector, the next step is its
    approval, even for the Admin, who can do both.
    """
    draft = state.situation == calculations.SITUATION_DRAFT
    approved = state.approval == calculations.APPROVAL_APPROVED
    if rights.validate and draft:
        return VALIDATE
    if rights.approve and not draft and not approved and state.has_done:
        return APPROVE
    if rights.report and not draft and not approved:
        return REPORT
    if rights.publish and state.situation == calculations.SITUATION_VALIDATED and approved:
        return PUBLISH
    return VIEW


def menu_of(rights: Rights, state: State, principal: str) -> tuple[str, ...]:
    """The items of the menu: what the profile may do, without the step already in the button."""
    draft = state.situation == calculations.SITUATION_DRAFT
    approved = state.approval == calculations.APPROVAL_APPROVED
    wanted = (
        (DETAIL, principal != VIEW),
        (EDIT, rights.edit),
        (REPORT, rights.report and not draft and not approved),
        (VALIDATE, rights.validate and draft),
        (APPROVE, rights.approve and not draft and not approved and state.has_done),
        (REOPEN, rights.approve and approved),
        (PUBLISH, rights.publish and state.situation == calculations.SITUATION_VALIDATED),
        (DELETE, rights.delete),
    )
    return tuple(key for key, allowed in wanted if allowed and key != principal)


def actions_of(rights: Rights, state: State) -> Actions:
    """The button and the menu of one row for one user."""
    principal = next_action(rights, state)
    return Actions(next_action=principal, menu=menu_of(rights, state, principal))


def check_can_validate(situation: str) -> None:
    """Only a programming still in drafting is validated."""
    if situation != calculations.SITUATION_DRAFT:
        raise InvalidDataError(VALIDATE_ONLY_DRAFT)


def check_can_report(situation: str, approval: str) -> None:
    """The done is reported after the validation and until the inspector approves it."""
    if approval == calculations.APPROVAL_APPROVED:
        raise InvalidDataError(REPORT_AFTER_APPROVAL)
    if situation == calculations.SITUATION_DRAFT:
        raise InvalidDataError(REPORT_BEFORE_VALIDATION)


def check_can_approve(situation: str, *, has_done: bool) -> None:
    """The inspector approves a validated programming that has done reported."""
    if situation == calculations.SITUATION_DRAFT:
        raise InvalidDataError(APPROVE_BEFORE_VALIDATION)
    if not has_done:
        raise InvalidDataError(APPROVE_WITHOUT_DONE)


def check_can_reopen(approval: str) -> None:
    """Only an approved done is reopened."""
    if approval != calculations.APPROVAL_APPROVED:
        raise InvalidDataError(REOPEN_NOT_APPROVED)


def check_can_publish(situation: str) -> None:
    """Only a validated programming is published."""
    if situation != calculations.SITUATION_VALIDATED:
        raise InvalidDataError(PUBLISH_ONLY_VALIDATED)
