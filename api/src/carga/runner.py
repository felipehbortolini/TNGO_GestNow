"""Runs the initial load according to the app mode (D6, D15, ISSUE-008).

In demonstration the platform applies every registered part once, inside the
caller's transaction, and records the part in ``carga_demonstracao`` so
running again duplicates nothing. In production the base is born empty: only
the initial parameters and the first Admin, whose e-mail comes from the
environment, are written.
"""

from __future__ import annotations

import importlib
import pkgutil
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

import src.modulos
from src.carga.registro import RegisteredLoader, registered, shift_date
from src.core import config
from src.core.models import SeedRun

# Reexported so a module's seed only imports ``src.carga``.
__all__ = [
    "ProductionStartError",
    "run_demonstration",
    "run_for_mode",
    "run_production",
    "shift_date",
]


class ProductionStartError(RuntimeError):
    """Raised when production start cannot run for lack of configuration."""


# The platform part carries the projects and registers every module needs,
# so it always runs first, wherever it sits in the registration order.
PLATFORM_PART = "plataforma"


def run_for_mode(session: Session, *, reference_date: date) -> list[str]:
    """Apply the load the configured app mode calls for.

    Returns the names of the demonstration parts effectively written; an
    empty list means everything was already there (idempotent re-run).
    """
    if config.app_mode() == config.PRODUCTION:
        admin_email = config.admin_email()
        if not admin_email:
            message = (
                f"Defina {config.ADMIN_EMAIL_VARIABLE} com o e-mail do primeiro Admin "
                "para iniciar a base de produção."
            )
            raise ProductionStartError(message)
        run_production(session, reference_date=reference_date, admin_email=admin_email)
        return []
    return run_demonstration(session, reference_date=reference_date)


def run_demonstration(session: Session, *, reference_date: date) -> list[str]:
    """Register and run each demonstration part missing from ``carga_demonstracao``."""
    _ensure_platform_part()
    _import_module_parts()
    written: list[str] = []
    for loader in _ordered_loaders():
        if _already_ran(session, loader.name):
            continue
        loader.run(session, reference_date)
        session.add(SeedRun(name=loader.name))
        session.flush()
        written.append(loader.name)
    return written


def run_production(session: Session, *, reference_date: date, admin_email: str) -> None:
    """Start an empty production base: the first Admin and the initial parameters."""
    from src.carga import producao

    producao.start(session, reference_date=reference_date, admin_email=admin_email)


def _ensure_platform_part() -> None:
    """Import the platform part so its loader is registered before the modules'."""
    importlib.import_module("src.carga.plataforma")


def _import_module_parts() -> None:
    """Import each module's ``seed.py``, when it exists, to register its part."""
    names = sorted(item.name for item in pkgutil.iter_modules(src.modulos.__path__))
    for name in names:
        target = f"src.modulos.{name}.seed"
        try:
            importlib.import_module(target)
        except ModuleNotFoundError as error:
            if error.name == target:
                continue
            raise


def _already_ran(session: Session, name: str) -> bool:
    statement = select(SeedRun.id).where(SeedRun.name == name).limit(1)
    return session.scalar(statement) is not None


def _ordered_loaders() -> list[RegisteredLoader]:
    """The registered parts with the platform first and the rest in registration order."""
    loaders = registered()
    loaders.sort(key=lambda loader: loader.name != PLATFORM_PART)
    return loaders
