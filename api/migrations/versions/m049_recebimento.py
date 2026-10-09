"""Recebimento do pedido: a conferência na obra (ISSUE-061).

A tabela como está em ``docs/MODELO-DE-DADOS.md``: uma linha por pedido recebido (``recebimento``,
UK implícita pelo fluxo — o pedido tem um só recebimento), com a data, a conferência, as avarias
com a descrição e as pendências; as evidências são ``anexo`` (tipo de origem ``recebimento``).
A entrega realizada no pedido e no marco ``Entrega`` é escrita na mesma transação.

Revision ID: m049
Revises: m048
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m049"
down_revision: str | None = "m048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the receipt of an order."""
    op.create_table(
        "recebimento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pedido_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("conferido", sa.Boolean(), nullable=False),
        sa.Column("avarias", sa.Boolean(), nullable=False),
        sa.Column("descricao_avarias", sa.Text(), nullable=True),
        sa.Column("pendencias", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pedido_id"], ["pedido.id"], name=op.f("fk_recebimento_pedido_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recebimento")),
    )


def downgrade() -> None:
    """Drop the receipt."""
    op.drop_table("recebimento")
