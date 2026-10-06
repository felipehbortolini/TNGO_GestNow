"""6wla: atividades do horizonte, semanas e restrições

Revision ID: m045
Revises: 0003
Create Date: 2026-10-06 10:00:00.000000

The 6WLA of the Planejamento module (ISSUE-045): ``lookahead``,
``lookahead_semana`` and ``lookahead_restricao``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m045"
down_revision: str | None = "m023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lookahead",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("atividade", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("disciplina", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_lookahead_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_lookahead_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_lookahead_responsavel_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lookahead")),
        sa.UniqueConstraint("projeto_id", "codigo", name=op.f("uq_lookahead_projeto_id_codigo")),
    )
    op.create_table(
        "lookahead_semana",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("lookahead_id", sa.BigInteger(), nullable=False),
        sa.Column("indice", sa.Integer(), nullable=False),
        sa.Column("prevista", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lookahead_id"], ["lookahead.id"], name=op.f("fk_lookahead_semana_lookahead_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lookahead_semana")),
        sa.UniqueConstraint(
            "lookahead_id", "indice", name=op.f("uq_lookahead_semana_lookahead_id_indice")
        ),
    )
    op.create_table(
        "lookahead_restricao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("lookahead_id", sa.BigInteger(), nullable=False),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("necessaria", sa.Date(), nullable=False),
        sa.Column("remocao", sa.Date(), nullable=True),
        sa.Column("comentario_remocao", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["lookahead_id"], ["lookahead.id"], name=op.f("fk_lookahead_restricao_lookahead_id")
        ),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_lookahead_restricao_responsavel_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lookahead_restricao")),
    )


def downgrade() -> None:
    op.drop_table("lookahead_restricao")
    op.drop_table("lookahead_semana")
    op.drop_table("lookahead")
