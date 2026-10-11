"""analise do periodo

Revision ID: m075
Revises: m074
Create Date: 2026-10-10 15:00:00.000000

Análise do período (ISSUE-081): ``analise_periodo`` — o texto executivo de um módulo
(02 Planejamento, 03 Gestão Financeira ou 04 Suprimentos), por tipo (Semanal ou Mensal) e
período, de um projeto; ``projeto_id`` nulo identifica a análise do Portfólio (ISSUE-082),
tratado no índice único com ``NULLS NOT DISTINCT`` — e ``analise_periodo_desvio`` — o
comentário de cada desvio negativo detectado, pela chave do desvio, sem ``versao`` própria
(protegida pela versão da análise) —, como em ``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m075"
down_revision: str | None = "m074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False)


def _version() -> sa.Column:
    return sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=op.f(f"fk_{table}_{column}"))


def upgrade() -> None:
    op.create_table(
        "analise_periodo",
        _id(),
        sa.Column("projeto_id", sa.BigInteger(), nullable=True),
        sa.Column("criado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("atualizado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("modulo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("periodo", sa.Text(), nullable=False),
        sa.Column("analise", sa.Text(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _version(),
        _fk("analise_periodo", "projeto_id", "projeto.id"),
        _fk("analise_periodo", "criado_por_id", "pessoa.id"),
        _fk("analise_periodo", "atualizado_por_id", "pessoa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analise_periodo")),
        sa.UniqueConstraint(
            "projeto_id",
            "modulo",
            "tipo",
            "periodo",
            postgresql_nulls_not_distinct=True,
            name=op.f("uq_analise_periodo_projeto_modulo_tipo_periodo"),
        ),
    )
    op.create_table(
        "analise_periodo_desvio",
        _id(),
        sa.Column("analise_id", sa.BigInteger(), nullable=False),
        sa.Column("chave", sa.Text(), nullable=False),
        sa.Column("indicador", sa.Text(), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=False),
        _fk("analise_periodo_desvio", "analise_id", "analise_periodo.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analise_periodo_desvio")),
    )


def downgrade() -> None:
    op.drop_table("analise_periodo_desvio")
    op.drop_table("analise_periodo")
