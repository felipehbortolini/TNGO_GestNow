"""The origin ``HSE`` of the actions of the Central: one reaction and one link, shared by the screens.

The Central keeps one reaction and one link type per origin (D9), and the origin ``HSE`` serves
more than one record: the recommendations of the risk analyses (ISSUE-074) and, later, the
occurrences. Each part registers here the handler for the references it owns; the first handler
that recognises the reference answers, the others are not asked.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from src.core import origin_links
from src.core.rbac import User
from src.modulos.central_acoes import origins
from src.modulos.central_acoes.models import Action
from src.modulos.central_acoes.origins import ActionEvent

ORIGIN = "HSE"

ActionHandler = Callable[[Session, User, Action, ActionEvent], bool]
LinkBuilder = Callable[[origin_links.OriginRef], str | None]

_handlers: list[ActionHandler] = []
_builders: list[LinkBuilder] = []


def register_action_handler(handler: ActionHandler) -> None:
    """Register how a part of HSE reacts to its actions; it answers ``True`` when the action is its."""
    if handler not in _handlers:
        _handlers.append(handler)


def register_link_builder(builder: LinkBuilder) -> None:
    """Register how a part of HSE builds the address of its records; ``None`` when not its own."""
    if builder not in _builders:
        _builders.append(builder)


def react(session: Session, user: User, action: Action, event: ActionEvent) -> None:
    """Tell the part of HSE that owns the record of the action what happened to it."""
    for handler in _handlers:
        if handler(session, user, action, event):
            return


def link(reference: origin_links.OriginRef) -> str | None:
    """The address of the record of origin, from the first part that knows its reference."""
    for builder in _builders:
        url = builder(reference)
        if url is not None:
            return url
    return None


origins.register_reaction(ORIGIN, react)
origin_links.register(origin_links.OriginLinkType(kind=ORIGIN, build=link))
