"""Revisões da EAC, linha de base por revisão e remanejamentos (ISSUE-030).

As três tabelas que a ISSUE-029 deixou para esta fatia, como em ``docs/MODELO-DE-DADOS.md``: a
revisão, a linha de base congelada de cada item em cada revisão e o remanejamento aplicado. Os
vínculos da Governança com ``eac_item``, abertos sem chave estrangeira na ISSUE-023/024, entram
aqui: o dono da tabela chegou (D9).

Revision ID: m030
Revises: m025
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m030"
down_revision: str | None = "m025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the revisions, the frozen baseline of each item and the reallocations."""
    op.create_table(
        "eac_revisao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=True),
        sa.Column("aprovado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["aprovado_por_id"], ["pessoa.id"], name=op.f("fk_eac_revisao_aprovado_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_eac_revisao_mudanca_id")
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_eac_revisao_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eac_revisao")),
        sa.UniqueConstraint(
            "projeto_id", "revisao", name=op.f("uq_eac_revisao_projeto_id_revisao")
        ),
    )
    op.create_table(
        "eac_revisao_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("revisao_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("base_centavos", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["eac_item.id"], name=op.f("fk_eac_revisao_item_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["revisao_id"], ["eac_revisao.id"], name=op.f("fk_eac_revisao_item_revisao_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eac_revisao_item")),
        sa.UniqueConstraint(
            "revisao_id", "item_id", name=op.f("uq_eac_revisao_item_revisao_id_item_id")
        ),
    )
    op.create_table(
        "eac_remanejamento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("origem_item_id", sa.BigInteger(), nullable=False),
        sa.Column("destino_item_id", sa.BigInteger(), nullable=False),
        sa.Column("por_id", sa.BigInteger(), nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=True),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["destino_item_id"], ["eac_item.id"], name=op.f("fk_eac_remanejamento_destino_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_eac_remanejamento_mudanca_id")
        ),
        sa.ForeignKeyConstraint(
            ["origem_item_id"], ["eac_item.id"], name=op.f("fk_eac_remanejamento_origem_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["por_id"], ["pessoa.id"], name=op.f("fk_eac_remanejamento_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_eac_remanejamento_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eac_remanejamento")),
    )
    op.create_foreign_key(
        op.f("fk_mudanca_remanejamento_origem_item_id"),
        "mudanca_remanejamento",
        "eac_item",
        ["origem_item_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_mudanca_remanejamento_destino_item_id"),
        "mudanca_remanejamento",
        "eac_item",
        ["destino_item_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_mudanca_impacto_eac_item_eac_item_id"),
        "mudanca_impacto_eac_item",
        "eac_item",
        ["eac_item_id"],
        ["id"],
    )


def downgrade() -> None:
    """Take the governance links out and drop the three tables, in the reverse order."""
    op.drop_constraint(
        op.f("fk_mudanca_impacto_eac_item_eac_item_id"),
        "mudanca_impacto_eac_item",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_mudanca_remanejamento_destino_item_id"),
        "mudanca_remanejamento",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_mudanca_remanejamento_origem_item_id"),
        "mudanca_remanejamento",
        type_="foreignkey",
    )
    op.drop_table("eac_remanejamento")
    op.drop_table("eac_revisao_item")
    op.drop_table("eac_revisao")
