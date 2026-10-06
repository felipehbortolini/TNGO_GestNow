"""acoes da central

Revision ID: m019
Revises: 0003
Create Date: 2026-10-06 09:00:00.000000

Actions of the Central de Ações and their replans (ISSUE-019): ``acao`` and
``acao_replanejamento``, as drawn in ``docs/MODELO-DE-DADOS.md``. ``acao.ata_id`` is a plain
column here; the foreign key to ``ata`` is added by the migration of the minutes (ISSUE-021).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m019"
down_revision: str | None = "m029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "acao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("ata_id", sa.BigInteger(), nullable=True),
        sa.Column("solicitante_id", sa.BigInteger(), nullable=False),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=False),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("origem_ref", sa.Text(), nullable=True),
        sa.Column("item", sa.Text(), nullable=True),
        sa.Column("grupo", sa.Text(), nullable=True),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column(
            "contribuicao_probabilidade",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "contribuicao_impacto", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("assunto", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("data_prevista", sa.Date(), nullable=True),
        sa.Column("data_replanejada", sa.Date(), nullable=True),
        sa.Column("data_conclusao", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_acao_projeto_id")),
        sa.ForeignKeyConstraint(
            ["solicitante_id"], ["pessoa.id"], name=op.f("fk_acao_solicitante_id")
        ),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_acao_responsavel_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acao")),
    )
    op.create_table(
        "acao_replanejamento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("acao_id", sa.BigInteger(), nullable=False),
        sa.Column("autor_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("de", sa.Date(), nullable=False),
        sa.Column("para", sa.Date(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["acao_id"], ["acao.id"], name=op.f("fk_acao_replanejamento_acao_id")
        ),
        sa.ForeignKeyConstraint(
            ["autor_id"], ["pessoa.id"], name=op.f("fk_acao_replanejamento_autor_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acao_replanejamento")),
    )


def downgrade() -> None:
    op.drop_table("acao_replanejamento")
    op.drop_table("acao")
