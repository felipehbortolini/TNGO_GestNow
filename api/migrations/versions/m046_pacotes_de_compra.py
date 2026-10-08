"""Plano de compras: pacotes e marcos de aquisição (ISSUE-058).

As duas tabelas do módulo `suprimentos` como estão em ``docs/MODELO-DE-DADOS.md``: o pacote
(``pacote_compra``, UK por projeto e código, ligado a um item da EAC, a um comprador do cadastro
de pessoas e a uma disciplina do cadastro de disciplinas) e as três camadas de cada marco de
aquisição na mesma linha (``pacote_compra_marco``, UK por pacote e marco). Etapa, folga e
adjudicado não têm coluna: são calculados na leitura.

Revision ID: m046
Revises: m043
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m046"
down_revision: str | None = "m043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the purchase package and its acquisition milestones."""
    op.create_table(
        "pacote_compra",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("eac_item_id", sa.BigInteger(), nullable=False),
        sa.Column("comprador_id", sa.BigInteger(), nullable=False),
        sa.Column("disciplina_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("escopo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("modalidade", sa.Text(), nullable=False),
        sa.Column("lli", sa.Boolean(), nullable=False),
        sa.Column("estimativa_centavos", sa.BigInteger(), nullable=False),
        sa.Column("ros", sa.Date(), nullable=False),
        sa.Column("emergencial", sa.Boolean(), nullable=False),
        sa.Column("gate_lli_data", sa.Date(), nullable=True),
        sa.Column("gate_lli_referencia", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_pacote_compra_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["eac_item_id"], ["eac_item.id"], name=op.f("fk_pacote_compra_eac_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["comprador_id"], ["pessoa.id"], name=op.f("fk_pacote_compra_comprador_id")
        ),
        sa.ForeignKeyConstraint(
            ["disciplina_id"], ["disciplina.id"], name=op.f("fk_pacote_compra_disciplina_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pacote_compra")),
        sa.UniqueConstraint(
            "projeto_id", "codigo", name=op.f("uq_pacote_compra_projeto_id_codigo")
        ),
    )
    op.create_table(
        "pacote_compra_marco",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pacote_id", sa.BigInteger(), nullable=False),
        sa.Column("marco", sa.Text(), nullable=False),
        sa.Column("data_plano", sa.Date(), nullable=True),
        sa.Column("data_previsao", sa.Date(), nullable=True),
        sa.Column("data_real", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pacote_id"], ["pacote_compra.id"], name=op.f("fk_pacote_compra_marco_pacote_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pacote_compra_marco")),
        sa.UniqueConstraint(
            "pacote_id", "marco", name=op.f("uq_pacote_compra_marco_pacote_id_marco")
        ),
    )


def downgrade() -> None:
    """Drop the packages and their milestones."""
    op.drop_table("pacote_compra_marco")
    op.drop_table("pacote_compra")
