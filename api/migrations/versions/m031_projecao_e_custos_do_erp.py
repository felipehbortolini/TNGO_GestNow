"""Projeção no término e custos do ERP (ISSUE-031).

As duas tabelas que o mapa de controle acrescenta, como em ``docs/MODELO-DE-DADOS.md``: o
histórico da projeção no término de cada item (fato imutável, sem ``versao``; a vigente é a
última linha do item) e os custos do ERP por item e mês, com a unicidade item + mês. Os fatos do
ERP alimentam a Curva S financeira e o valor agregado.

Revision ID: m031
Revises: m030
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m031"
down_revision: str | None = "m030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the projection history and the ERP costs per item and month."""
    op.create_table(
        "eac_projecao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("autor_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["autor_id"], ["pessoa.id"], name=op.f("fk_eac_projecao_autor_id")),
        sa.ForeignKeyConstraint(["item_id"], ["eac_item.id"], name=op.f("fk_eac_projecao_item_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eac_projecao")),
    )
    op.create_table(
        "custo_erp",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("importado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("mes", sa.Date(), nullable=False),
        sa.Column("comprometido_centavos", sa.BigInteger(), nullable=True),
        sa.Column("realizado_centavos", sa.BigInteger(), nullable=True),
        sa.Column("projecao_centavos", sa.BigInteger(), nullable=True),
        sa.Column(
            "importado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["importado_por_id"], ["pessoa.id"], name=op.f("fk_custo_erp_importado_por_id")
        ),
        sa.ForeignKeyConstraint(["item_id"], ["eac_item.id"], name=op.f("fk_custo_erp_item_id")),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_custo_erp_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custo_erp")),
        sa.UniqueConstraint("item_id", "mes", name=op.f("uq_custo_erp_item_id_mes")),
    )


def downgrade() -> None:
    """Drop the ERP costs and the projection history."""
    op.drop_table("custo_erp")
    op.drop_table("eac_projecao")
