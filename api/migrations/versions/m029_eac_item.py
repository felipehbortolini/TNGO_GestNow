"""eac item

Revision ID: m029
Revises: 0003
Create Date: 2026-10-06 10:00:00.000000

Cost breakdown item (ISSUE-029): the three-level tree of the Estrutura Analítica de Custos, as
in ``docs/MODELO-DE-DADOS.md``. No aggregated value is a column; the revisions and the transfers
come with ISSUE-030.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m029"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eac_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("pai_id", sa.BigInteger(), nullable=True),
        sa.Column("unidade_id", sa.BigInteger(), nullable=True),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("tipo_custo", sa.Text(), nullable=True),
        sa.Column("quantidade", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("preco_unitario_centavos", sa.BigInteger(), nullable=True),
        sa.Column("capex", sa.Boolean(), nullable=True),
        sa.Column("centro_custo", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["pai_id"], ["eac_item.id"], name=op.f("fk_eac_item_pai_id")),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_eac_item_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_eac_item_responsavel_id")
        ),
        sa.ForeignKeyConstraint(
            ["unidade_id"], ["unidade.id"], name=op.f("fk_eac_item_unidade_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eac_item")),
        sa.UniqueConstraint("projeto_id", "codigo", name=op.f("uq_eac_item_projeto_id_codigo")),
    )


def downgrade() -> None:
    op.drop_table("eac_item")
