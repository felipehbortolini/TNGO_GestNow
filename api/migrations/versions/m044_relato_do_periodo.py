"""relato do periodo

Revision ID: m044
Revises: m045
Create Date: 2026-10-06 09:00:00.000000

Relato do período (ISSUE-044): the weekly or monthly report of a project, with its
activities and attention points as children of the aggregate.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m044"
down_revision: str | None = "m045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "relato",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("criado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("atualizado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("periodo", sa.Text(), nullable=False),
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
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["atualizado_por_id"], ["pessoa.id"], name=op.f("fk_relato_atualizado_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["criado_por_id"], ["pessoa.id"], name=op.f("fk_relato_criado_por_id")
        ),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_relato_projeto_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_relato")),
        sa.UniqueConstraint(
            "projeto_id", "tipo", "periodo", name=op.f("uq_relato_projeto_id_tipo_periodo")
        ),
    )
    op.create_table(
        "relato_atividade",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("relato_id", sa.BigInteger(), nullable=False),
        sa.Column("grupo", sa.Text(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["relato_id"], ["relato.id"], name=op.f("fk_relato_atividade_relato_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_relato_atividade")),
    )
    op.create_table(
        "relato_ponto",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("relato_id", sa.BigInteger(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("natureza", sa.Text(), nullable=False),
        sa.Column("risco", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["relato_id"], ["relato.id"], name=op.f("fk_relato_ponto_relato_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_relato_ponto")),
    )


def downgrade() -> None:
    op.drop_table("relato_ponto")
    op.drop_table("relato_atividade")
    op.drop_table("relato")
