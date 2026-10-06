"""analises de risco apr e hazop

Revision ID: m074
Revises: m072
Create Date: 2026-10-06 12:00:00.000000

Risk analyses (ISSUE-074): ``analise_risco``, ``analise_risco_participante`` and
``analise_risco_recomendacao``, as drawn in ``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m074"
down_revision: str | None = "m072"
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
        "analise_risco",
        _id(),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        _version(),
        _fk("analise_risco", "projeto_id", "projeto.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analise_risco")),
        sa.UniqueConstraint("codigo", name=op.f("uq_analise_risco_codigo")),
    )
    op.create_table(
        "analise_risco_participante",
        _id(),
        sa.Column("analise_id", sa.BigInteger(), nullable=False),
        sa.Column("pessoa_id", sa.BigInteger(), nullable=False),
        _fk("analise_risco_participante", "analise_id", "analise_risco.id"),
        _fk("analise_risco_participante", "pessoa_id", "pessoa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analise_risco_participante")),
    )
    op.create_table(
        "analise_risco_recomendacao",
        _id(),
        sa.Column("analise_id", sa.BigInteger(), nullable=False),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("prazo", sa.Date(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("concluida_em", sa.Date(), nullable=True),
        sa.Column("evidencia", sa.Text(), nullable=True),
        _version(),
        _fk("analise_risco_recomendacao", "analise_id", "analise_risco.id"),
        _fk("analise_risco_recomendacao", "responsavel_id", "pessoa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analise_risco_recomendacao")),
    )


def downgrade() -> None:
    op.drop_table("analise_risco_recomendacao")
    op.drop_table("analise_risco_participante")
    op.drop_table("analise_risco")
