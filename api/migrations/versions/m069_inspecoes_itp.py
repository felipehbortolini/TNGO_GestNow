"""inspecoes e ITP

Revision ID: m069
Revises: m068
Create Date: 2026-10-10 09:00:00.000000

Inspeções e ITP do 06 Qualidade (ISSUE-069): ``itp``, ``itp_revisao``, ``itp_ponto`` e
``inspecao``, como em ``docs/MODELO-DE-DADOS.md`` — o plano de inspeção e testes com a
revisão vigente e os seus pontos (H, W e R), e o registro de inspeção por ponto. O
``itp_ponto_id`` e o ``pedido_id`` são nulos na inspeção: o FAT do diligenciamento grava a
inspeção sem ponto de ITP e é identificado pelo pedido. A ``notificacao`` ao cliente do
ponto W (e do H) foi acrescentada na mesma entrega, para a antecedência mínima do parâmetro;
o MODELO §11 muda junto. UK: ``itp`` pelo código e ``inspecao`` por projeto + código.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m069"
down_revision: str | None = "m068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "itp",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("disciplina_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_itp_projeto_id")),
        sa.ForeignKeyConstraint(
            ["disciplina_id"], ["disciplina.id"], name=op.f("fk_itp_disciplina_id")
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"], name=op.f("fk_itp_empresa_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_itp")),
        sa.UniqueConstraint("codigo", name=op.f("uq_itp_codigo")),
    )
    op.create_table(
        "itp_revisao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("itp_id", sa.BigInteger(), nullable=False),
        sa.Column("aprovacao_por_id", sa.BigInteger(), nullable=True),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("aprovado_cliente", sa.Boolean(), nullable=False),
        sa.Column("aprovacao_referencia", sa.Text(), nullable=True),
        sa.Column("aprovacao_data", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["itp_id"], ["itp.id"], name=op.f("fk_itp_revisao_itp_id")),
        sa.ForeignKeyConstraint(
            ["aprovacao_por_id"],
            ["pessoa.id"],
            name=op.f("fk_itp_revisao_aprovacao_por_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_itp_revisao")),
    )
    op.create_table(
        "itp_ponto",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("revisao_id", sa.BigInteger(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("atividade", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("criterio", sa.Text(), nullable=False),
        sa.Column("referencia", sa.Text(), nullable=False),
        sa.Column("responsavel", sa.Text(), nullable=False),
        sa.CheckConstraint("tipo IN ('H', 'W', 'R')", name=op.f("ck_itp_ponto_tipo")),
        sa.ForeignKeyConstraint(
            ["revisao_id"], ["itp_revisao.id"], name=op.f("fk_itp_ponto_revisao_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_itp_ponto")),
    )
    op.create_table(
        "inspecao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("itp_ponto_id", sa.BigInteger(), nullable=True),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("inspetor_id", sa.BigInteger(), nullable=False),
        sa.Column("rnc_id", sa.BigInteger(), nullable=True),
        sa.Column("pedido_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("ponto", sa.Text(), nullable=False),
        sa.Column("tipo_ponto", sa.Text(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("resultado", sa.Text(), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=False),
        sa.Column("notificacao", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("tipo_ponto IN ('H', 'W', 'R')", name=op.f("ck_inspecao_tipo_ponto")),
        sa.CheckConstraint(
            "resultado IN ('Aprovado', 'Aprovado com ressalva', 'Reprovado')",
            name=op.f("ck_inspecao_resultado"),
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_inspecao_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["itp_ponto_id"], ["itp_ponto.id"], name=op.f("fk_inspecao_itp_ponto_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_inspecao_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["inspetor_id"], ["pessoa.id"], name=op.f("fk_inspecao_inspetor_id")
        ),
        sa.ForeignKeyConstraint(["rnc_id"], ["rnc.id"], name=op.f("fk_inspecao_rnc_id")),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido.id"], name=op.f("fk_inspecao_pedido_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inspecao")),
        sa.UniqueConstraint("projeto_id", "codigo", name=op.f("uq_inspecao_projeto_id_codigo")),
    )


def downgrade() -> None:
    op.drop_table("inspecao")
    op.drop_table("itp_ponto")
    op.drop_table("itp_revisao")
    op.drop_table("itp")
