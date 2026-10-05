"""SQLAlchemy engine, session and migration helpers shared by the platform.

The connection URL comes from the ``GESTNOW_DATABASE_URL`` environment
variable in every environment (decision D5): nothing in the code distinguishes
the local Postgres from the Azure Database for PostgreSQL. Model classes are
English and point to Portuguese table and column names (D1, D5).
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import MetaData, create_engine, make_url, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql import select

DATABASE_URL_VARIABLE = "GESTNOW_DATABASE_URL"

# Deterministic constraint names keep the migrated schema comparable with the
# models by Alembic autogenerate (D5 asks for foreign keys and uniqueness in
# the database itself).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when the application database URL is missing."""

    def __init__(self) -> None:
        super().__init__(
            f"{DATABASE_URL_VARIABLE} nao esta definida. "
            "Rode o run.bat para preparar o banco local."
        )


class Base(DeclarativeBase):
    """Base class of every GestNow model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Defaults for the columns the application always writes explicitly but that
# no insert should have to remember (D5: version on every editable record).
VERSION_SERVER_DEFAULT = text("1")
ACTIVE_SERVER_DEFAULT = text("true")


def database_url() -> str:
    """Return the application database URL exactly as configured."""
    url = os.environ.get(DATABASE_URL_VARIABLE)
    if not url:
        raise DatabaseNotConfiguredError
    return url


def normalize_url(url: str) -> str:
    """Point a plain postgresql URL at the psycopg 3 driver.

    The owner writes ``postgresql://...`` (the libpq form, also used by the
    Azure connection string); SQLAlchemy needs the driver named because only
    psycopg 3 is installed.
    """
    parsed = make_url(url)
    if parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide engine, created on first use."""
    return create_engine(normalize_url(database_url()), pool_pre_ping=True)


def reset_engine() -> None:
    """Drop the cached engine so the next call rereads GESTNOW_DATABASE_URL."""
    get_engine.cache_clear()


def new_session() -> Session:
    """Open a session bound to the application engine."""
    return Session(bind=get_engine(), expire_on_commit=False)


@contextmanager
def unidade_de_trabalho() -> Iterator[Session]:
    """One transaction per request: everything writes together or nothing does (D5).

    The route opens it; the facade of the module receives the session and
    performs the whole flow — including integrations between modules —
    with it. Leaving the block commits; an exception rolls everything back
    and propagates.
    """
    session = new_session()
    try:
        with session.begin():
            yield session
    finally:
        session.close()


def import_all_models() -> None:
    """Import the platform models and the models of every module.

    Alembic autogenerate and the migration test compare the whole metadata;
    a model module that is not imported would be invisible and its tables
    would show up as drift.
    """
    importlib.import_module("src.core.models")
    import src.modulos

    modules = sorted(pkgutil.iter_modules(src.modulos.__path__), key=lambda item: item.name)
    for module in modules:
        importlib.import_module(f"src.modulos.{module.name}.models")


def database_report() -> dict[str, str | None]:
    """Report the database situation and migration revision for ``/api/health``."""
    try:
        with get_engine().connect() as connection:
            connection.execute(select(1))
            revision = _migration_revision(connection)
    except (SQLAlchemyError, DatabaseNotConfiguredError):
        return {"situacao": "erro", "revisao": None}
    return {"situacao": "ok", "revisao": revision}


def _migration_revision(connection: Connection) -> str | None:
    try:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError:
        return None
    return result.scalar_one_or_none()
