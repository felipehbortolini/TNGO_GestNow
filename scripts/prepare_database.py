"""Prepare the local Postgres for development: role, databases and migrations.

Reads the administration URL from ``GESTNOW_PG_ADMIN_URL`` (a user environment
variable the owner creates once, per the execution prompt). Creates the
application role and the ``gestnow`` and ``gestnow_teste`` databases when
missing, writes the application URL into ``api/local.settings.json`` (outside
git) and applies the Alembic migrations to ``gestnow``.

The script is idempotent and never prints a password.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"

import psycopg  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from psycopg import sql  # noqa: E402
from sqlalchemy import URL  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

APP_ROLE = "gestnow"
APP_DATABASE = "gestnow"
TEST_DATABASE = "gestnow_teste"
ADMIN_URL_VARIABLE = "GESTNOW_PG_ADMIN_URL"
DATABASE_URL_VARIABLE = "GESTNOW_DATABASE_URL"
LOCAL_SETTINGS_PATH = API_DIR / "local.settings.json"


class AdminUrlError(ValueError):
    """Raised when GESTNOW_PG_ADMIN_URL cannot be read."""

    def __init__(self) -> None:
        super().__init__(
            "GESTNOW_PG_ADMIN_URL precisa seguir "
            "postgresql://usuario:senha@host:porta/banco."
        )


def parse_admin_url(text: str) -> dict[str, Any]:
    """Read user, password, host, port and database from the administration URL.

    The execution prompt asks for percent-encoded special characters, but a
    password written with them unencoded is accepted: the last ``@`` before
    the host is the separator and the whole text before it is the password.
    """
    scheme, separator, rest = text.partition("://")
    if "postgres" not in scheme or not separator or not rest:
        raise AdminUrlError

    at_position = rest.rfind("@")
    if at_position == -1:
        raise AdminUrlError
    credentials, host_part = rest[:at_position], rest[at_position + 1 :]

    user, user_separator, password = credentials.partition(":")
    if not user or not user_separator or not password:
        raise AdminUrlError

    host, _, database = host_part.partition("/")
    hostname, port_separator, port_text = host.rpartition(":")
    if not port_separator:
        hostname, port_text = host, "5432"

    if "%" in password:
        password = unquote(password)

    return {
        "host": hostname or "localhost",
        "port": int(port_text) if port_text.isdigit() else 5432,
        "user": user,
        "password": password,
        "dbname": database.split("?")[0] or "postgres",
    }


def app_connection(admin_parameters: dict[str, Any]) -> dict[str, Any]:
    """Connection parameters of the application role on the gestnow database."""
    return {**admin_parameters, "user": APP_ROLE, "dbname": APP_DATABASE}


def app_url(admin_parameters: dict[str, Any]) -> URL:
    """Application URL with the password percent-encoded for storage."""
    return URL.create(
        drivername="postgresql+psycopg",
        username=APP_ROLE,
        password=admin_parameters["password"],
        host=admin_parameters["host"],
        port=admin_parameters["port"],
        database=APP_DATABASE,
    )


def ensure_role(connection: psycopg.Connection, password: str) -> bool:
    """Create the application role when missing; keep its password in sync. True if created."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        created = cursor.fetchone() is None
        if created:
            cursor.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(APP_ROLE)))
        cursor.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(APP_ROLE), sql.Literal(password)
            )
        )
    return created


def ensure_database(connection: psycopg.Connection, name: str) -> bool:
    """Create a database owned by the application role when missing. True if created."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        if cursor.fetchone() is not None:
            return False
        cursor.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(name), sql.Identifier(APP_ROLE)
            )
        )
    return True


def write_local_settings(url_text: str) -> None:
    """Write the application URL into api/local.settings.json (outside git)."""
    settings: dict[str, Any] = {}
    if LOCAL_SETTINGS_PATH.is_file():
        settings = json.loads(LOCAL_SETTINGS_PATH.read_text(encoding="utf-8"))
    values = settings.get("Values")
    if not isinstance(values, dict):
        values = {}
    values[DATABASE_URL_VARIABLE] = url_text
    settings["Values"] = values
    LOCAL_SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def current_revision(parameters: dict[str, Any]) -> str | None:
    """Read the applied migration revision from the application database."""
    with psycopg.connect(**parameters) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.alembic_version')")
            if cursor.fetchone()[0] is None:
                return None
            cursor.execute("SELECT version_num FROM alembic_version")
            row = cursor.fetchone()
    return row[0] if row else None


def apply_migrations(parameters: dict[str, Any], url: URL) -> str | None:
    """Apply every pending migration to the application database."""
    os.environ[DATABASE_URL_VARIABLE] = url.render_as_string(hide_password=False)
    config = Config(str(API_DIR / "alembic.ini"))
    if ScriptDirectory.from_config(config).get_current_head() is None:
        print("  migracoes: nenhuma revision ainda")
        return None
    command.upgrade(config, "head")
    return current_revision(parameters)


def prepare() -> int:
    admin_text = os.environ.get(ADMIN_URL_VARIABLE)
    if not admin_text:
        print(f"ERRO: a variavel {ADMIN_URL_VARIABLE} nao esta definida.")
        print("Ela e a URL de administracao do Postgres, criada uma vez como variavel de usuario:")
        print("  postgresql://postgres:SUA_SENHA@localhost:5432/postgres")
        print("O passo a passo esta em docs/issues/spec-migracao-gestnow/PROMPT-EXECUCAO.md (item 2).")
        print("Depois de criar, feche e reabra o prompt e rode o run.bat de novo.")
        return 1

    try:
        admin_parameters = parse_admin_url(admin_text)
    except AdminUrlError:
        print(f"ERRO: nao foi possivel ler {ADMIN_URL_VARIABLE}.")
        print("Use o formato postgresql://usuario:senha@host:porta/banco.")
        return 1

    print("Preparando o banco local do GestNow...")
    with psycopg.connect(**admin_parameters) as connection:
        connection.autocommit = True
        role_created = ensure_role(connection, admin_parameters["password"])
        app_created = ensure_database(connection, APP_DATABASE)
        test_created = ensure_database(connection, TEST_DATABASE)

    print(f"  papel {APP_ROLE}: {'criado' if role_created else 'ja existia'}")
    print(f"  banco {APP_DATABASE}: {'criado' if app_created else 'ja existia'}")
    print(f"  banco {TEST_DATABASE}: {'criado' if test_created else 'ja existia'}")

    write_local_settings(app_url(admin_parameters).render_as_string(hide_password=False))
    print("  configuracao local: api/local.settings.json (fora do git)")

    revision = apply_migrations(app_connection(admin_parameters), app_url(admin_parameters))
    print(f"  migracoes: revisao {revision}" if revision else "  migracoes: banco sem revision")
    print("Banco pronto.")
    return 0


def main() -> int:
    try:
        return prepare()
    except psycopg.Error as error:
        print(f"ERRO: falha do Postgres ({error}).")
        print("Confira se o servico esta rodando, a porta 5432 e a variavel GESTNOW_PG_ADMIN_URL.")
        return 1
    except (SQLAlchemyError, OSError, RuntimeError):
        print("ERRO: nao foi possivel aplicar as migracoes.")
        print("Confira a revisao em api/migrations/versions e rode o run.bat de novo.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
