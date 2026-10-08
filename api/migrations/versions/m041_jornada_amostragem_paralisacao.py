"""Horas efetivas: jornada, amostragem e paralisações (ISSUE-047).

As quatro tabelas do campo, como em ``docs/MODELO-DE-DADOS.md``: a jornada da
fiscalização por frente e dia, a rodada da amostragem do trabalho com os seus
motivos e a paralisação de efetivo ou de máquina. O ``encarregado`` é o texto
digitado pela fiscalização, como no protótipo; o inspetor de campo da carga é o
único cadastro apontado. Os motivos entram e saem com a rodada e não têm
``versao`` própria.

Revision ID: m041
Revises: m040
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m041"
down_revision: str | None = "m040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the field day, the work sampling with its reasons and the stoppage."""
    op.create_table(
        "jornada_campo",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("registrado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("encarregado", sa.Text(), nullable=False),
        sa.Column("efetivo", sa.Integer(), nullable=False),
        sa.Column("manha_chegada", sa.Time(), nullable=False),
        sa.Column("manha_inicio", sa.Time(), nullable=False),
        sa.Column("manha_termino", sa.Time(), nullable=False),
        sa.Column("tarde_chegada", sa.Time(), nullable=False),
        sa.Column("tarde_inicio", sa.Time(), nullable=False),
        sa.Column("tarde_termino", sa.Time(), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_jornada_campo_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_jornada_campo_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por_id"], ["pessoa.id"], name=op.f("fk_jornada_campo_registrado_por_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jornada_campo")),
        sa.UniqueConstraint(
            "projeto_id",
            "data",
            "empresa_id",
            "area",
            "encarregado",
            name=op.f("uq_jornada_campo_projeto_id_data_empresa_id_area_encarregado"),
        ),
    )
    op.create_table(
        "amostragem",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("observador_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("hora", sa.Time(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("encarregado", sa.Text(), nullable=False),
        sa.Column("trabalhando", sa.Integer(), nullable=False),
        sa.Column("transito", sa.Integer(), nullable=False),
        sa.Column("parado", sa.Integer(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_amostragem_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_amostragem_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["observador_id"], ["pessoa.id"], name=op.f("fk_amostragem_observador_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_amostragem")),
    )
    op.create_table(
        "amostragem_motivo",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("amostragem_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["amostragem_id"], ["amostragem.id"], name=op.f("fk_amostragem_motivo_amostragem_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_amostragem_motivo")),
        sa.UniqueConstraint(
            "amostragem_id",
            "tipo",
            "motivo",
            name=op.f("uq_amostragem_motivo_amostragem_id_tipo_motivo"),
        ),
    )
    op.create_table(
        "paralisacao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("registrado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("recurso", sa.Text(), nullable=False),
        sa.Column("quantidade", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("inicio", sa.Time(), nullable=False),
        sa.Column("termino", sa.Time(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("responsabilidade", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_paralisacao_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_paralisacao_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por_id"], ["pessoa.id"], name=op.f("fk_paralisacao_registrado_por_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paralisacao")),
    )


def downgrade() -> None:
    """Drop the stoppage, the reasons, the sampling round and the field day."""
    op.drop_table("paralisacao")
    op.drop_table("amostragem_motivo")
    op.drop_table("amostragem")
    op.drop_table("jornada_campo")
