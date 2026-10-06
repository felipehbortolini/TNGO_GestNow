"""punch list

Revision ID: m049
Revises: m072
Create Date: 2026-10-06 12:00:00.000000

The Punch list (ISSUE-049): ``punch_item``, as drawn in ``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m049"
down_revision: str | None = "m074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fk(column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=op.f(f"fk_punch_item_{column}"))


def upgrade() -> None:
    op.create_table(
        "punch_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("sistema_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=False),
        sa.Column("identificado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("verificado_por_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("subsistema", sa.Text(), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column("disciplina", sa.Text(), nullable=False),
        sa.Column("categoria", sa.Text(), nullable=False),
        sa.Column("marco", sa.Text(), nullable=False),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("abertura", sa.Date(), nullable=False),
        sa.Column("prazo", sa.Date(), nullable=False),
        sa.Column("fechamento", sa.Date(), nullable=True),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("comentario_tratamento", sa.Text(), nullable=True),
        sa.Column("comentario_verificacao", sa.Text(), nullable=True),
        sa.Column("justificativa_cancelamento", sa.Text(), nullable=True),
        sa.Column("reprovacoes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _fk("projeto_id", "projeto.id"),
        _fk("sistema_id", "sistema.id"),
        _fk("empresa_id", "empresa.id"),
        _fk("responsavel_id", "pessoa.id"),
        _fk("identificado_por_id", "pessoa.id"),
        _fk("verificado_por_id", "pessoa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_punch_item")),
        sa.UniqueConstraint("projeto_id", "codigo", name=op.f("uq_punch_item_projeto_id_codigo")),
    )


def downgrade() -> None:
    op.drop_table("punch_item")
