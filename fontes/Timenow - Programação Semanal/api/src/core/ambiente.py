"""The active environment — the context that says whose data we touch.

An environment is resolved per request (or per test, script or seed),
never per process: Azure Functions runs synchronous handlers in a thread
pool of one process, and a module global would leak one client's
environment into another request. ``ContextVar`` stays correct in that
pool today and keeps being correct if some endpoint turns async later.

The context manager is the only way an environment becomes active::

    with ambiente_ativo("mccain"):
        ...

Outside it, ``slug_ativo()`` raises — no default environment, no guess.
The persistence port and the audit trail both read this context to
resolve their own path, which is what turns "fail closed" from a rule
into code.

This module imports nothing from ``core`` on purpose: ``repositorio``
and ``auditoria`` import from here, and the reverse direction would
cycle.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_ativo: ContextVar[str | None] = ContextVar("ambiente_ativo", default=None)


class SemAmbienteError(RuntimeError):
    """No environment is active — never touch a base without saying whose."""


def slug_ativo() -> str:
    """The slug of the active environment. Raises when there is none.

    This is the fail-closed door of the whole delivery: every piece of
    code that touches a base passes through here, and outside an
    ``ambiente_ativo`` block the answer is an exception — never a
    default environment, never a guess.
    """
    slug = _ativo.get()
    if not slug:
        raise SemAmbienteError(
            "Nenhum ambiente ativo — abra `with ambiente_ativo(slug)` antes de tocar a base."
        )
    return slug


@contextmanager
def ambiente_ativo(slug: str) -> Iterator[None]:
    """Open an environment for the current context, until the block ends.

    Sets the ``ContextVar`` on entry and resets it on exit — including
    on exception — so a failed request never leaves its environment
    behind for the next one on the same context.
    """
    token = _ativo.set(slug)
    try:
        yield
    finally:
        _ativo.reset(token)
