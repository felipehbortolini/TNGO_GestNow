"""curva S fisica

Revision ID: m037
Revises: m036
Create Date: 2026-10-07 10:00:00.000000

The physical S-curve of the Planejamento module (ISSUE-039): the baseline frozen
per EAP revision and its monthly percentages, as in ``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m037"
down_revision: str | None = "m036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERCENT = sa.Numeric(precision=7, scale=2)


def upgrade() -> None:
    """Create the physical S-curve baseline of each EAP revision and its months."""
    op.create_table(
        "curva_fisica_revisao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("eap_revisao_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "gerada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["eap_revisao_id"],
            ["eap_revisao.id"],
            name=op.f("fk_curva_fisica_revisao_eap_revisao_id"),
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_curva_fisica_revisao_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_curva_fisica_revisao")),
        sa.UniqueConstraint(
            "projeto_id",
            "eap_revisao_id",
            name=op.f("uq_curva_fisica_revisao_projeto_id_eap_revisao_id"),
        ),
    )
    op.create_table(
        "curva_fisica_mes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("revisao_id", sa.BigInteger(), nullable=False),
        sa.Column("mes", sa.Date(), nullable=False),
        sa.Column("baseline_pct", PERCENT, nullable=False),
        sa.ForeignKeyConstraint(
            ["revisao_id"],
            ["curva_fisica_revisao.id"],
            name=op.f("fk_curva_fisica_mes_revisao_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_curva_fisica_mes")),
        sa.UniqueConstraint("revisao_id", "mes", name=op.f("uq_curva_fisica_mes_revisao_id_mes")),
    )


def downgrade() -> None:
    """Drop the monthly baseline and the revision of the physical S-curve."""
    op.drop_table("curva_fisica_mes")
    op.drop_table("curva_fisica_revisao")
