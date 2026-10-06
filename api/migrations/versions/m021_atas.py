"""atas da central

Revision ID: m021
Revises: m019
Create Date: 2026-10-06 11:00:00.000000

Minutes of the Central de Ações (ISSUE-021): ``ata``, ``ata_empresa`` and ``ata_participante``, as
drawn in ``docs/MODELO-DE-DADOS.md``, and the foreign key of ``acao.ata_id`` that the migration of
the actions (m019) left as a plain column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m021"
down_revision: str | None = "m024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ata",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("unidade_id", sa.BigInteger(), nullable=True),
        sa.Column("elaborado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_principal_id", sa.BigInteger(), nullable=True),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("tipo_reuniao", sa.Text(), nullable=False),
        sa.Column("diretoria", sa.Text(), nullable=False),
        sa.Column("assunto", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_ata_projeto_id")),
        sa.ForeignKeyConstraint(["unidade_id"], ["unidade.id"], name=op.f("fk_ata_unidade_id")),
        sa.ForeignKeyConstraint(
            ["elaborado_por_id"], ["pessoa.id"], name=op.f("fk_ata_elaborado_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_principal_id"], ["empresa.id"], name=op.f("fk_ata_empresa_principal_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ata")),
        sa.UniqueConstraint(
            "projeto_id", "numero", "revisao", name=op.f("uq_ata_projeto_id_numero_revisao")
        ),
    )
    op.create_table(
        "ata_empresa",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ata_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["ata_id"], ["ata.id"], name=op.f("fk_ata_empresa_ata_id")),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_ata_empresa_empresa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ata_empresa")),
        sa.UniqueConstraint("ata_id", "empresa_id", name=op.f("uq_ata_empresa_ata_id_empresa_id")),
    )
    op.create_table(
        "ata_participante",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ata_id", sa.BigInteger(), nullable=False),
        sa.Column("pessoa_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["ata_id"], ["ata.id"], name=op.f("fk_ata_participante_ata_id")),
        sa.ForeignKeyConstraint(
            ["pessoa_id"], ["pessoa.id"], name=op.f("fk_ata_participante_pessoa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ata_participante")),
        sa.UniqueConstraint(
            "ata_id", "pessoa_id", name=op.f("uq_ata_participante_ata_id_pessoa_id")
        ),
    )
    op.create_foreign_key(op.f("fk_acao_ata_id"), "acao", "ata", ["ata_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(op.f("fk_acao_ata_id"), "acao", type_="foreignkey")
    op.drop_table("ata_participante")
    op.drop_table("ata_empresa")
    op.drop_table("ata")
