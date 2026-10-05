"""carga de demonstracao

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05 18:00:00.000000

Registry of the demonstration load (ISSUE-008): one row per registered part
already written, so running the load again duplicates nothing.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carga_demonstracao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column(
            "executada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_carga_demonstracao")),
        sa.UniqueConstraint("nome", name=op.f("uq_carga_demonstracao_nome")),
    )


def downgrade() -> None:
    op.drop_table("carga_demonstracao")
