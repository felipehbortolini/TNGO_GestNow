"""Avaliação de desempenho da contratada (ISSUE-034).

As duas tabelas da avaliação, como em ``docs/MODELO-DE-DADOS.md``: a avaliação mensal ou final,
com o avaliador e a versão de parâmetros usada, e o peso e a nota de cada critério gravados nela
(exceção da D5b: a avaliação permanece com os pesos vigentes na data em que foi feita). A nota
ponderada e a classe são calculadas, não são coluna.

Revision ID: m034
Revises: m033
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m034"
down_revision: str | None = "m033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the evaluations and their criteria."""
    op.create_table(
        "contrato_avaliacao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contrato_id", sa.BigInteger(), nullable=False),
        sa.Column("avaliador_id", sa.BigInteger(), nullable=False),
        sa.Column("parametro_versao_id", sa.BigInteger(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["avaliador_id"], ["pessoa.id"], name=op.f("fk_contrato_avaliacao_avaliador_id")
        ),
        sa.ForeignKeyConstraint(
            ["contrato_id"], ["contrato.id"], name=op.f("fk_contrato_avaliacao_contrato_id")
        ),
        sa.ForeignKeyConstraint(
            ["parametro_versao_id"],
            ["parametro_versao.id"],
            name=op.f("fk_contrato_avaliacao_parametro_versao_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato_avaliacao")),
    )
    op.create_table(
        "contrato_avaliacao_criterio",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("avaliacao_id", sa.BigInteger(), nullable=False),
        sa.Column("criterio", sa.Text(), nullable=False),
        sa.Column("peso", sa.Integer(), nullable=False),
        sa.Column("nota", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["avaliacao_id"],
            ["contrato_avaliacao.id"],
            name=op.f("fk_contrato_avaliacao_criterio_avaliacao_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato_avaliacao_criterio")),
        sa.UniqueConstraint(
            "avaliacao_id",
            "criterio",
            name=op.f("uq_contrato_avaliacao_criterio_avaliacao_id_criterio"),
        ),
    )


def downgrade() -> None:
    """Drop the criteria, then the evaluations."""
    op.drop_table("contrato_avaliacao_criterio")
    op.drop_table("contrato_avaliacao")
