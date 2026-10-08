"""Fornecedores: qualificação, categorias, documentos com validade e histórico (ISSUE-057).

As quatro tabelas do módulo `suprimentos` como estão em ``docs/MODELO-DE-DADOS.md``: a
qualificação de uma empresa do cadastro (``fornecedor``, UK por empresa), as suas categorias de
atuação (``fornecedor_categoria``), os documentos com validade (``fornecedor_documento``; o
arquivo é um ``anexo``) e as mudanças de situação (``fornecedor_historico``; o autor é uma
``pessoa``). O cadastro é global, como o de empresas e pessoas: nenhuma tabela tem projeto.

Revision ID: m043
Revises: m042
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m043"
down_revision: str | None = "m042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the qualification, the categories, the documents and the history."""
    op.create_table(
        "fornecedor",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("validade_qualificacao", sa.Date(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_fornecedor_empresa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fornecedor")),
        sa.UniqueConstraint("empresa_id", name=op.f("uq_fornecedor_empresa_id")),
    )
    op.create_table(
        "fornecedor_categoria",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fornecedor_id", sa.BigInteger(), nullable=False),
        sa.Column("categoria", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fornecedor_id"], ["fornecedor.id"], name=op.f("fk_fornecedor_categoria_fornecedor_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fornecedor_categoria")),
    )
    op.create_table(
        "fornecedor_documento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fornecedor_id", sa.BigInteger(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("validade", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["fornecedor_id"], ["fornecedor.id"], name=op.f("fk_fornecedor_documento_fornecedor_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fornecedor_documento")),
    )
    op.create_table(
        "fornecedor_historico",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fornecedor_id", sa.BigInteger(), nullable=False),
        sa.Column("por_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("de", sa.Text(), nullable=True),
        sa.Column("para", sa.Text(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fornecedor_id"], ["fornecedor.id"], name=op.f("fk_fornecedor_historico_fornecedor_id")
        ),
        sa.ForeignKeyConstraint(
            ["por_id"], ["pessoa.id"], name=op.f("fk_fornecedor_historico_por_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fornecedor_historico")),
    )


def downgrade() -> None:
    """Drop the four tables of the qualification."""
    op.drop_table("fornecedor_historico")
    op.drop_table("fornecedor_documento")
    op.drop_table("fornecedor_categoria")
    op.drop_table("fornecedor")
