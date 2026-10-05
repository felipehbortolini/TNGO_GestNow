"""Test infrastructure: every test runs on ``gestnow_teste``, isolated by transaction.

The session fixture recreates the public schema of ``gestnow_teste`` from the
migrations at each pytest run — an empty database goes up to the last
migration — and points ``GESTNOW_DATABASE_URL`` at it. The URL is always the
application URL with the database name plus ``_teste``: no test can touch the
``gestnow`` database.

Tests that write request the ``db_session`` fixture and run inside a
transaction that is rolled back when the test ends, so no data crosses between
tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import make_url, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core import config, database

API_DIR = Path(__file__).resolve().parent.parent
TEST_DATABASE_SUFFIX = "_teste"


class TestDatabaseError(RuntimeError):
    """Raised when the test database cannot be derived from the application URL."""


def build_test_url(app_url: str) -> str:
    """Derive the test database URL and refuse to touch anything but a ``_teste`` database."""
    parsed = make_url(app_url)
    name = parsed.database or ""
    if not name or name.endswith(TEST_DATABASE_SUFFIX):
        message = (
            f"A URL da aplicacao precisa apontar para um banco sem o sufixo {TEST_DATABASE_SUFFIX}."
        )
        raise TestDatabaseError(message)
    return parsed.set(database=f"{name}{TEST_DATABASE_SUFFIX}").render_as_string(
        hide_password=False
    )


def recreate_schema(engine: Engine) -> None:
    """Drop and recreate the public schema, so the migrations build it again."""
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


def run_migrations() -> None:
    """Apply every migration to the test database (GESTNOW_DATABASE_URL already points at it)."""
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")


@pytest.fixture(scope="session", autouse=True)
def banco_de_teste() -> Iterator[str]:
    """Recreate ``gestnow_teste`` from the migrations and point the app at it."""
    config.load_local_settings()
    app_url = os.environ.get(database.DATABASE_URL_VARIABLE)
    if not app_url:
        pytest.exit(
            "GESTNOW_DATABASE_URL nao definida. Rode o run.bat para preparar o banco local.",
            returncode=1,
        )

    try:
        test_url = build_test_url(app_url)
    except TestDatabaseError:
        pytest.exit(
            "Nao foi possivel derivar a URL do banco de teste a partir da URL da aplicacao.",
            returncode=1,
        )

    os.environ[database.DATABASE_URL_VARIABLE] = test_url
    database.reset_engine()
    engine = database.get_engine()

    try:
        recreate_schema(engine)
        run_migrations()
    except SQLAlchemyError as error:
        pytest.exit(
            f"Nao foi possivel preparar o gestnow_teste ({type(error).__name__}). "
            "Rode o run.bat para criar o banco e confira se o servico do Postgres esta rodando.",
            returncode=1,
        )

    yield test_url
    engine.dispose()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A session inside an outer transaction that is rolled back when the test ends."""
    engine = database.get_engine()
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
