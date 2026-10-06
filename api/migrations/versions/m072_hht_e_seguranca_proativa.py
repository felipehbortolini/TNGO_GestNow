"""hht e seguranca proativa

Revision ID: m072
Revises: 0003
Create Date: 2026-10-06 10:00:00.000000

HHT and the proactive safety records (ISSUE-072): ``hht``, ``hse_mensal``, ``hse_inspecao``,
``hse_inspecao_item``, ``hse_observacao`` and ``hse_dds``, as drawn in
``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m072"
down_revision: str | None = "0003"
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
        "hht",
        _id(),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("mes", sa.Date(), nullable=False),
        sa.Column("efetivo_medio", sa.Integer(), nullable=False),
        sa.Column("hht", sa.Numeric(14, 2), nullable=False),
        _version(),
        _fk("hht", "projeto_id", "projeto.id"),
        _fk("hht", "empresa_id", "empresa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hht")),
        sa.UniqueConstraint(
            "projeto_id", "mes", "empresa_id", name=op.f("uq_hht_projeto_id_mes_empresa_id")
        ),
    )
    op.create_table(
        "hse_mensal",
        _id(),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("mes", sa.Date(), nullable=False),
        sa.Column("desvios", sa.Integer(), nullable=False),
        sa.Column("observacoes", sa.Integer(), nullable=False),
        sa.Column("dds_programados", sa.Integer(), nullable=False),
        sa.Column("dds_realizados", sa.Integer(), nullable=False),
        sa.Column("itens_inspecionados", sa.Integer(), nullable=False),
        sa.Column("itens_conformes", sa.Integer(), nullable=False),
        _version(),
        _fk("hse_mensal", "projeto_id", "projeto.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hse_mensal")),
        sa.UniqueConstraint("projeto_id", "mes", name=op.f("uq_hse_mensal_projeto_id_mes")),
    )
    op.create_table(
        "hse_inspecao",
        _id(),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        _version(),
        _fk("hse_inspecao", "projeto_id", "projeto.id"),
        _fk("hse_inspecao", "empresa_id", "empresa.id"),
        _fk("hse_inspecao", "responsavel_id", "pessoa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hse_inspecao")),
    )
    op.create_table(
        "hse_inspecao_item",
        _id(),
        sa.Column("inspecao_id", sa.BigInteger(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("conforme", sa.Boolean(), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        _fk("hse_inspecao_item", "inspecao_id", "hse_inspecao.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hse_inspecao_item")),
    )
    op.create_table(
        "hse_observacao",
        _id(),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("observado_id", sa.BigInteger(), nullable=True),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        _version(),
        _fk("hse_observacao", "projeto_id", "projeto.id"),
        _fk("hse_observacao", "empresa_id", "empresa.id"),
        _fk("hse_observacao", "observado_id", "pessoa.id"),
        _fk("hse_observacao", "responsavel_id", "pessoa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hse_observacao")),
    )
    op.create_table(
        "hse_dds",
        _id(),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("tema", sa.Text(), nullable=False),
        sa.Column("participantes", sa.Integer(), nullable=False),
        _version(),
        _fk("hse_dds", "projeto_id", "projeto.id"),
        _fk("hse_dds", "empresa_id", "empresa.id"),
        _fk("hse_dds", "responsavel_id", "pessoa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hse_dds")),
    )


def downgrade() -> None:
    op.drop_table("hse_dds")
    op.drop_table("hse_observacao")
    op.drop_table("hse_inspecao_item")
    op.drop_table("hse_inspecao")
    op.drop_table("hse_mensal")
    op.drop_table("hht")
