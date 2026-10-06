"""Links back to the record that originated another record (D9, HU-055, ISSUE-019).

An action of the Central, a lesson, a risk suggestion: each one points back to the
record that generated it by a **kind** (``Risco``, ``RNC``, ``Ata``) and a **reference**
(the code the owner module gave the record). The platform cannot know the screen of a
module that has not been written yet, and a module never reads the screens of another,
so each module registers here the **link type** of its own records, with the function
that builds the address.

``resolve`` answers the screen with an ``OriginLink``: the reference to print and, when
the kind is registered and the builder knows the record, the address to open. A kind that
no module registered yet (its issue has not arrived) resolves to the reference **without
a link**: the screen prints the text and no anchor, never a dead link.

A module registers its type when it is imported, at the end of its facade::

    origin_links.register(
        OriginLinkType(
            kind="Risco",
            build=lambda ref: origin_links.link_to_screen("riscos/ficha", codigo=ref.reference),
        )
    )

The registry has the same shape as ``attachment_origins`` and ``carga.registro``: the
platform owns the mechanism, each module its entry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

from src.core import navigation


@dataclass(frozen=True)
class OriginRef:
    """What a builder receives: the kind of the origin, its reference and, when known, its id.

    ``item`` names one item of the record (the recommendation of a risk analysis) for the calls
    that act on the actions of that item only.
    """

    kind: str
    reference: str
    record_id: int | None = None
    item: str | None = None


@dataclass(frozen=True)
class OriginLink:
    """What a screen prints for an origin: the reference and, when there is one, the address."""

    reference: str
    url: str | None

    @property
    def has_link(self) -> bool:
        """Whether the screen draws an anchor, or only the text of the reference."""
        return self.url is not None


LinkBuilder = Callable[[OriginRef], str | None]


@dataclass(frozen=True)
class OriginLinkType:
    """One kind of origin: its name and the function of its module that builds the address."""

    kind: str
    build: LinkBuilder


_TYPES: dict[str, OriginLinkType] = {}


def register(link_type: OriginLinkType) -> None:
    """Register the link type of a module; two modules cannot share a kind.

    Registering the very same type again does nothing, so a module imported twice does not
    fail; a different type under a taken kind does.
    """
    known = _TYPES.get(link_type.kind)
    if known is not None and known != link_type:
        message = f"O tipo de origem {link_type.kind} já está registrado por outro módulo."
        raise ValueError(message)
    _TYPES[link_type.kind] = link_type


def find(kind: str) -> OriginLinkType | None:
    """The link type registered for the kind, or ``None`` when no module registered it yet."""
    return _TYPES.get(kind)


def registered() -> list[OriginLinkType]:
    """The registered link types, in registration order."""
    return list(_TYPES.values())


def resolve(kind: str, reference: str | None, *, record_id: int | None = None) -> OriginLink:
    """The link of an origin: the address when the kind is registered, only the text otherwise."""
    shown = (reference or "").strip()
    link_type = _TYPES.get(kind)
    if link_type is None or not shown:
        return OriginLink(reference=shown, url=None)
    url = link_type.build(OriginRef(kind=kind, reference=shown, record_id=record_id))
    return OriginLink(reference=shown, url=url)


def link_to_screen(screen_key: str, **parameters: str | int) -> str | None:
    """The public address of a screen of the navigation list, with its query, for a builder.

    The scope is not written here: the link carries ``data-tn-tela``, and the shell keeps the
    scope of the person. A key that is not in the list gives ``None`` (no link).
    """
    screen = navigation.find_screen(screen_key)
    if screen is None:
        return None
    path = navigation.public_path(screen)
    return f"{path}?{urlencode(parameters)}" if parameters else path
