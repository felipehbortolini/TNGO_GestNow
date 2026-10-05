"""Migrations test: an empty schema reaches the last migration and matches the models."""

from __future__ import annotations

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, make_url, select, text
from sqlalchemy.orm import Session

from src.core import database
from src.core.models import Client

API_DIR = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    """The Alembic configuration used by the application and by the tests."""
    return Config(str(API_DIR / "alembic.ini"))


def head_revision() -> str:
    """The last migration revision in the repository."""
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    assert head is not None
    return head


def test_banco_de_teste_nao_e_o_gestnow(banco_de_teste: str) -> None:
    database_name = make_url(banco_de_teste).database
    assert database_name == "gestnow_teste"
    assert database_name != "gestnow"


def test_banco_vazio_sobe_ate_a_ultima_migracao() -> None:
    with database.get_engine().connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert revision == head_revision()


def test_esquema_migrado_bate_com_os_modelos() -> None:
    database.import_all_models()
    with database.get_engine().connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, database.Base.metadata)
    assert differences == []


def test_gravacao_do_teste_e_desfeita_no_fim(db_session: Session) -> None:
    db_session.add(Client(name="Cliente de teste", active=True))
    db_session.commit()

    assert db_session.scalar(select(func.count()).select_from(Client)) == 1

    # Another connection never sees the test row: it lives in the outer
    # transaction that the fixture rolls back at the end.
    with database.get_engine().connect() as connection:
        visible_rows = connection.execute(text("SELECT count(*) FROM cliente")).scalar_one()
    assert visible_rows == 0
