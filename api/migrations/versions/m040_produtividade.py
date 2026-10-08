"""Produtividade: quantidades da linha de base e apontamento (ISSUE-046).

As quatro tabelas da produtividade, como em ``docs/MODELO-DE-DADOS.md``: o item do
plano de quantidades, o total congelado de cada revisão da linha de base, a
distribuição semanal da revisão e o apontamento semanal da contratada. As três
últimas são a exceção da D5b: guardam o fato congelado e não têm ``versao``.

Revision ID: m040
Revises: m039
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m040"
down_revision: str | None = "m039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the quantity plan, its baseline revisions and the contractor report."""
    op.create_table(
        "produtividade_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("unidade_id", sa.BigInteger(), nullable=True),
        sa.Column("disciplina_id", sa.BigInteger(), nullable=True),
        sa.Column("aprovado_por_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("grupo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("casas", sa.Integer(), nullable=False),
        sa.Column("total", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("indice_hh", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("perfil", sa.Text(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=False),
        sa.Column("fim", sa.Date(), nullable=False),
        sa.Column("aprovado_em", sa.Date(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_produtividade_item_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_produtividade_item_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["unidade_id"], ["unidade.id"], name=op.f("fk_produtividade_item_unidade_id")
        ),
        sa.ForeignKeyConstraint(
            ["disciplina_id"], ["disciplina.id"], name=op.f("fk_produtividade_item_disciplina_id")
        ),
        sa.ForeignKeyConstraint(
            ["aprovado_por_id"], ["pessoa.id"], name=op.f("fk_produtividade_item_aprovado_por_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_produtividade_item")),
        sa.UniqueConstraint(
            "projeto_id", "codigo", name=op.f("uq_produtividade_item_projeto_id_codigo")
        ),
    )
    op.create_table(
        "produtividade_revisao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("por_id", sa.BigInteger(), nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=True),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("total", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("total_anterior", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("desde", sa.Text(), nullable=True),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["produtividade_item.id"], name=op.f("fk_produtividade_revisao_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["por_id"], ["pessoa.id"], name=op.f("fk_produtividade_revisao_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_produtividade_revisao_mudanca_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_produtividade_revisao")),
    )
    op.create_table(
        "produtividade_distribuicao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("revisao_id", sa.BigInteger(), nullable=False),
        sa.Column("semana", sa.Text(), nullable=False),
        sa.Column("previsto", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.ForeignKeyConstraint(
            ["revisao_id"],
            ["produtividade_revisao.id"],
            name=op.f("fk_produtividade_distribuicao_revisao_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_produtividade_distribuicao")),
        sa.UniqueConstraint(
            "revisao_id", "semana", name=op.f("uq_produtividade_distribuicao_revisao_id_semana")
        ),
    )
    op.create_table(
        "produtividade_apontamento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("semana", sa.Text(), nullable=False),
        sa.Column("realizado", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("hh", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("informado_em", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["produtividade_item.id"],
            name=op.f("fk_produtividade_apontamento_item_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_produtividade_apontamento")),
        sa.UniqueConstraint(
            "item_id", "semana", name=op.f("uq_produtividade_apontamento_item_id_semana")
        ),
    )


def downgrade() -> None:
    """Drop the weekly report, the distribution, the revisions and the item."""
    op.drop_table("produtividade_apontamento")
    op.drop_table("produtividade_distribuicao")
    op.drop_table("produtividade_revisao")
    op.drop_table("produtividade_item")
