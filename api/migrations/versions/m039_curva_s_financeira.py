"""Curva S financeira (ISSUE-042).

As duas tabelas da Curva S financeira, como em ``docs/MODELO-DE-DADOS.md``: a linha de base
congelada a partir de uma revisão da EAC e o valor planejado em centavos de cada mês. O
comprometido, o realizado e a projeção da curva são calculados dos fatos (exceção da D5b).

Revision ID: m039
Revises: m038
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m039"
down_revision: str | None = "m038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the financial S-curve baseline of each EAC revision and its months."""
    op.create_table(
        "curva_financeira_revisao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("eac_revisao_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "gerada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["eac_revisao_id"],
            ["eac_revisao.id"],
            name=op.f("fk_curva_financeira_revisao_eac_revisao_id"),
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_curva_financeira_revisao_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_curva_financeira_revisao")),
        sa.UniqueConstraint(
            "projeto_id",
            "eac_revisao_id",
            name=op.f("uq_curva_financeira_revisao_projeto_id_eac_revisao_id"),
        ),
    )
    op.create_table(
        "curva_financeira_mes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("revisao_id", sa.BigInteger(), nullable=False),
        sa.Column("mes", sa.Date(), nullable=False),
        sa.Column("planejado_centavos", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revisao_id"],
            ["curva_financeira_revisao.id"],
            name=op.f("fk_curva_financeira_mes_revisao_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_curva_financeira_mes")),
        sa.UniqueConstraint(
            "revisao_id", "mes", name=op.f("uq_curva_financeira_mes_revisao_id_mes")
        ),
    )


def downgrade() -> None:
    """Drop the monthly planned value and the revision of the financial S-curve."""
    op.drop_table("curva_financeira_mes")
    op.drop_table("curva_financeira_revisao")
