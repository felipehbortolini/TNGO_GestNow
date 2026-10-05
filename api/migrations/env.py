"""Alembic environment: one migration file per module slice, one database.

The URL always comes from ``GESTNOW_DATABASE_URL`` (D5); the revision files
live in ``migrations/versions`` and are created by each module issue with
``alembic revision --autogenerate --rev-id NNNN -m <modulo>``. The metadata
imports the platform models and the models of every module, so autogenerate
sees the whole schema.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Make `src` importable regardless of the directory the command runs from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core import database

config = context.config

if config.config_file_name is not None:
    # Running the migrations in-process (tests, prepare_database) must not silence the
    # application loggers that were created before this file ran.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

database.import_all_models()
target_metadata = database.Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a connection, emitting SQL to stdout."""
    context.configure(
        url=database.normalize_url(database.database_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""
    connectable = create_engine(
        database.normalize_url(database.database_url()), poolclass=pool.NullPool
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
