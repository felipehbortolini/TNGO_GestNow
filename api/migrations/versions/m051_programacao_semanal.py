"""programacao semanal

Revision ID: m051
Revises: 0003
Create Date: 2026-10-06 10:00:00.000000

The tables of the Weekly Scheduling as ``docs/MODELO-DE-DADOS.md`` states them
(section 8, ISSUE-051): the configuration of the project, the activity with its
seven days, the change requests and the window of each company with its weekdays,
released weeks and extraordinary releases.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m051"
down_revision: str | None = "m044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUANTITY = sa.Numeric(14, 2, asdecimal=False)
PERCENT = sa.Numeric(7, 2, asdecimal=False)


def upgrade() -> None:
    op.create_table(
        "programacao_configuracao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("meta_aderencia", PERCENT, nullable=False),
        sa.Column("meta_ppc", PERCENT, nullable=False),
        sa.Column("semana_referencia", sa.Text(), nullable=True),
        sa.Column(
            "exige_justificativa_desvio",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("limite_desvio_justificativa", PERCENT, nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_programacao_configuracao_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programacao_configuracao")),
        sa.UniqueConstraint("projeto_id", name=op.f("uq_programacao_configuracao_projeto_id")),
    )
    op.create_table(
        "programacao_atividade",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("local_id", sa.BigInteger(), nullable=True),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("unidade_id", sa.BigInteger(), nullable=True),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=True),
        sa.Column("encarregado_id", sa.BigInteger(), nullable=True),
        sa.Column("criado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("atualizado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("aprovado_por_id", sa.BigInteger(), nullable=True),
        sa.Column("semana", sa.Text(), nullable=False),
        sa.Column("id_exclusiva", sa.Text(), nullable=False),
        sa.Column("item", sa.Integer(), nullable=False),
        sa.Column("atividade", sa.Text(), nullable=False),
        sa.Column("prod_prevista", QUANTITY, nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("aprovacao_realizado", sa.Text(), nullable=False),
        sa.Column("observacoes_fornecedor", sa.Text(), nullable=True),
        sa.Column("comentarios_timenow", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aprovado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publicado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_programacao_atividade_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["local_id"], ["local.id"], name=op.f("fk_programacao_atividade_local_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_programacao_atividade_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["unidade_id"], ["unidade.id"], name=op.f("fk_programacao_atividade_unidade_id")
        ),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_programacao_atividade_responsavel_id")
        ),
        sa.ForeignKeyConstraint(
            ["encarregado_id"], ["pessoa.id"], name=op.f("fk_programacao_atividade_encarregado_id")
        ),
        sa.ForeignKeyConstraint(
            ["criado_por_id"], ["pessoa.id"], name=op.f("fk_programacao_atividade_criado_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["atualizado_por_id"],
            ["pessoa.id"],
            name=op.f("fk_programacao_atividade_atualizado_por_id"),
        ),
        sa.ForeignKeyConstraint(
            ["aprovado_por_id"],
            ["pessoa.id"],
            name=op.f("fk_programacao_atividade_aprovado_por_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programacao_atividade")),
        sa.UniqueConstraint(
            "projeto_id",
            "semana",
            "id_exclusiva",
            name=op.f("uq_programacao_atividade_projeto_id_semana_id_exclusiva"),
        ),
    )
    op.create_table(
        "programacao_dia",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("atividade_id", sa.BigInteger(), nullable=False),
        sa.Column("dia", sa.Integer(), nullable=False),
        sa.Column("previsto", QUANTITY, server_default=sa.text("0"), nullable=False),
        sa.Column("realizado_dia", QUANTITY, server_default=sa.text("0"), nullable=False),
        sa.Column("realizado_noite", QUANTITY, server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(
            ["atividade_id"],
            ["programacao_atividade.id"],
            name=op.f("fk_programacao_dia_atividade_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programacao_dia")),
        sa.UniqueConstraint(
            "atividade_id", "dia", name=op.f("uq_programacao_dia_atividade_id_dia")
        ),
    )
    op.create_table(
        "programacao_pedido_alteracao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("atividade_id", sa.BigInteger(), nullable=False),
        sa.Column("solicitado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("decidido_por_id", sa.BigInteger(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("solicitado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decidido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resposta", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["atividade_id"],
            ["programacao_atividade.id"],
            name=op.f("fk_programacao_pedido_alteracao_atividade_id"),
        ),
        sa.ForeignKeyConstraint(
            ["solicitado_por_id"],
            ["pessoa.id"],
            name=op.f("fk_programacao_pedido_alteracao_solicitado_por_id"),
        ),
        sa.ForeignKeyConstraint(
            ["decidido_por_id"],
            ["pessoa.id"],
            name=op.f("fk_programacao_pedido_alteracao_decidido_por_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programacao_pedido_alteracao")),
    )
    op.create_table(
        "programacao_janela",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_programacao_janela_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_programacao_janela_empresa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programacao_janela")),
        sa.UniqueConstraint(
            "projeto_id", "empresa_id", name=op.f("uq_programacao_janela_projeto_id_empresa_id")
        ),
    )
    op.create_table(
        "programacao_janela_dia",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("janela_id", sa.BigInteger(), nullable=False),
        sa.Column("dia_semana", sa.Integer(), nullable=False),
        sa.Column("abre", sa.Time(), nullable=False),
        sa.Column("fecha", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(
            ["janela_id"],
            ["programacao_janela.id"],
            name=op.f("fk_programacao_janela_dia_janela_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programacao_janela_dia")),
    )
    op.create_table(
        "programacao_janela_semana",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("janela_id", sa.BigInteger(), nullable=False),
        sa.Column("semana", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["janela_id"],
            ["programacao_janela.id"],
            name=op.f("fk_programacao_janela_semana_janela_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programacao_janela_semana")),
    )
    op.create_table(
        "programacao_liberacao_extra",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("janela_id", sa.BigInteger(), nullable=False),
        sa.Column("semana", sa.Text(), nullable=False),
        sa.Column("abre", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["janela_id"],
            ["programacao_janela.id"],
            name=op.f("fk_programacao_liberacao_extra_janela_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programacao_liberacao_extra")),
    )


def downgrade() -> None:
    op.drop_table("programacao_liberacao_extra")
    op.drop_table("programacao_janela_semana")
    op.drop_table("programacao_janela_dia")
    op.drop_table("programacao_janela")
    op.drop_table("programacao_pedido_alteracao")
    op.drop_table("programacao_dia")
    op.drop_table("programacao_atividade")
    op.drop_table("programacao_configuracao")
