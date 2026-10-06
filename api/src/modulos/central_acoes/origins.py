"""The origins of an action and how each module reacts to the life of its actions (D9, ISSUE-019).

The Central is the single seam of action: every module that generates an action calls
``service.create_action`` with its origin and the reference of its own record. The status of
the action and the status of the record of origin stay in step in two directions:

* **action to origin**: when an action is replanned or completed in the Central, the module
  that owns the origin is told by its **reaction**, inside the same transaction, so either
  both change or none does. A module registers its reaction when it is imported::

      origins.register_reaction("Risco", react_to_risk_action)

  The reaction receives the session, the user, the action and the event, and may refuse with a
  domain error (the whole request is then undone);
* **origin to action**: when the record of origin changes by its own screen (a punch item is
  closed), its module calls ``service.close_from_origin``.

An origin with no registered reaction needs nothing from the Central: the action simply
follows its own dates.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from src.core.rbac import User
    from src.modulos.central_acoes.models import Action

ORIGINS: tuple[str, ...] = (
    "Ata",
    "Punch list",
    "Contrato",
    "Suprimentos",
    "Risco",
    "RNC",
    "HSE",
    "Mudança",
    "Lição",
    "Produtividade",
)

# The status of these actions is decided where they are treated: the Central shows them and
# links to the record, but replanning and completing happen in the owner module.
TREATED_AT_SOURCE: frozenset[str] = frozenset({"Punch list"})


class ActionEvent(StrEnum):
    """What happened to an action in the Central that the module of its origin may care about."""

    REPLANNED = "replanejada"
    COMPLETED = "concluida"


Reaction = Callable[[Session, "User", "Action", ActionEvent], None]

_REACTIONS: dict[str, Reaction] = {}


def register_reaction(origin: str, reaction: Reaction) -> None:
    """Register how the module of an origin reacts; one reaction per origin."""
    if origin not in ORIGINS:
        message = f"A origem {origin} não é uma origem de ação da Central."
        raise ValueError(message)
    known = _REACTIONS.get(origin)
    if known is not None and known is not reaction:
        message = f"A origem {origin} já tem uma reação registrada por outro módulo."
        raise ValueError(message)
    _REACTIONS[origin] = reaction


def reaction_for(origin: str) -> Reaction | None:
    """The reaction registered for the origin, or ``None`` when the module registered none."""
    return _REACTIONS.get(origin)


def react(session: Session, user: User, action: Action, event: ActionEvent) -> None:
    """Tell the module of the origin what happened, inside the transaction of the change."""
    reaction = _REACTIONS.get(action.origin)
    if reaction is not None:
        reaction(session, user, action, event)
