"""Registry of the demonstration-load parts and the date shift (D6, ISSUE-008).

Every module owns its part of the load: a ``carga.py`` inside the module
package calls :func:`register` at import time with its name and a function
that writes the converted records with the session it receives. The platform
loads its own part first, so the projects and registers every module needs
already exist; then the runner walks the registry in order.

The converted mocks are anchored on 25/09/2026, the prototype's fixed
reference date. The load receives the date of the run and shifts every date
by ``reference_date - DEMO_ANCHOR``; the oracle harness passes the anchor
itself, which means no shift at all (D6/Q15).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

DEMO_ANCHOR = date(2026, 9, 25)

Loader = Callable[[Session, date], None]


@dataclass(frozen=True)
class RegisteredLoader:
    """One part of the demonstration load: a name and the function that writes it."""

    name: str
    run: Loader


_LOADERS: dict[str, RegisteredLoader] = {}


def register(name: str, loader: Loader) -> None:
    """Register one part of the load under a unique name."""
    if name in _LOADERS:
        message = f"A carga de demonstração já tem uma parte registrada como {name}."
        raise ValueError(message)
    _LOADERS[name] = RegisteredLoader(name=name, run=loader)


def registered() -> list[RegisteredLoader]:
    """The registered parts, in registration order (the platform part first)."""
    return list(_LOADERS.values())


def shift_date(original: date, reference_date: date) -> date:
    """Move a prototype date to the run's reference date, keeping the scenario's spacing."""
    return original + (reference_date - DEMO_ANCHOR)
