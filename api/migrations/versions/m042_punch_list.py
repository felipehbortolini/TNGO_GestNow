"""Punch list: o item da completação e a sua verificação (ISSUE-049).

A tabela ``punch_item``, como em ``docs/MODELO-DE-DADOS.md``: o item da punch
list com a hierarquia (sistema, subsistema, TAG), a disciplina, a categoria A, B
ou C, o marco vinculado, a origem, a empresa executante, o responsável e a
verificação. A evidência do fechamento é um ``anexo`` (D5a), não uma coluna; o
bloqueio do sistema por item A aberto é calculado. UK: projeto + código.

O cadastro de apoio ``sistema`` (código, nome, área) já existe desde a 0001
(plataforma) e é lido aqui e pelas telas de planejamento; esta migração não o
cria de novo.

Revision ID: m042
Revises: m041
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m042"
down_revision: str | None = "m041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the punch list item."""
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
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_punch_item_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["sistema_id"], ["sistema.id"], name=op.f("fk_punch_item_sistema_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_punch_item_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_punch_item_responsavel_id")
        ),
        sa.ForeignKeyConstraint(
            ["identificado_por_id"],
            ["pessoa.id"],
            name=op.f("fk_punch_item_identificado_por_id"),
        ),
        sa.ForeignKeyConstraint(
            ["verificado_por_id"], ["pessoa.id"], name=op.f("fk_punch_item_verificado_por_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_punch_item")),
        sa.UniqueConstraint("projeto_id", "codigo", name=op.f("uq_punch_item_projeto_id_codigo")),
    )


def downgrade() -> None:
    """Drop the punch list item."""
    op.drop_table("punch_item")
