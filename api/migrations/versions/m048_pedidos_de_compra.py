"""Pedidos de compra: o pedido e os seus marcos de fabricação (ISSUE-060).

As duas tabelas do módulo `suprimentos` como estão em ``docs/MODELO-DE-DADOS.md``: o pedido de
compra que a emissão de um processo de equipamento/material cria (``pedido``, UK por número,
ligado ao pacote e ao fornecedor) e os seis marcos de fabricação (``pedido_marco``) com as três
camadas na mesma linha (LB contratual, previsão e realizada). A entrega é registrada no
``recebimento`` (ISSUE-061); folga, situação e OTD são calculados na leitura.

A migração também fecha a chave estrangeira de ``contrato.pacote_compra_id`` para
``pacote_compra``, que a parte 1 do modelo desenhou e a ISSUE-058/060 acrescenta (D9): o contrato
de um serviço/EPC nasce da adjudicação do processo daquele pacote.

Revision ID: m048
Revises: m047
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m048"
down_revision: str | None = "m047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the purchase order and its manufacturing milestones; tie the contract to the package."""
    op.create_table(
        "pedido",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("pacote_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("lli", sa.Boolean(), nullable=False),
        sa.Column("emissao", sa.Date(), nullable=False),
        sa.Column("data_contratual", sa.Date(), nullable=False),
        sa.Column("previsao", sa.Date(), nullable=False),
        sa.Column("ros", sa.Date(), nullable=False),
        sa.Column("entrega", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_pedido_projeto_id")),
        sa.ForeignKeyConstraint(
            ["pacote_id"], ["pacote_compra.id"], name=op.f("fk_pedido_pacote_id")
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"], name=op.f("fk_pedido_empresa_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pedido")),
        sa.UniqueConstraint("numero", name=op.f("uq_pedido_numero")),
    )
    op.create_table(
        "pedido_marco",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pedido_id", sa.BigInteger(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("data_lb", sa.Date(), nullable=True),
        sa.Column("data_previsao", sa.Date(), nullable=True),
        sa.Column("data_realizada", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pedido_id"], ["pedido.id"], name=op.f("fk_pedido_marco_pedido_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pedido_marco")),
        sa.UniqueConstraint("pedido_id", "ordem", name=op.f("uq_pedido_marco_pedido_id_ordem")),
    )
    op.create_foreign_key(
        op.f("fk_contrato_pacote_compra_id"),
        "contrato",
        "pacote_compra",
        ["pacote_compra_id"],
        ["id"],
    )


def downgrade() -> None:
    """Drop the contract link, the manufacturing milestones and the order."""
    op.drop_constraint(op.f("fk_contrato_pacote_compra_id"), "contrato", type_="foreignkey")
    op.drop_table("pedido_marco")
    op.drop_table("pedido")
