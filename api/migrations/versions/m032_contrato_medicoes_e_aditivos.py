"""Ficha do contrato: contrato, aditivos e medições (ISSUE-032).

As três tabelas da administração contratual, como em ``docs/MODELO-DE-DADOS.md``: o contrato com
valor original, datas, gestor, fiscal, retenção e prazo de notificação de claim; o aditivo
aprovado (valor e/ou dias) com a SM e o claim de origem; e o boletim de medição com período, valor
bruto, situação e motivo da devolução. Valor atual, medido e saldo são calculados, não são coluna.

``contrato.pacote_compra_id``, ``contrato_aditivo.claim_id`` e ``contrato_medicao.marco_id`` entram
como ``bigint`` sem chave estrangeira: as tabelas ``pacote_compra`` (ISSUE-058/060) e
``contrato_claim``/``contrato_marco_pagamento`` (ISSUE-033) ainda não existem; a migração da issue
que criar cada uma acrescenta a sua chave (D9).

Revision ID: m032
Revises: m031
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m032"
down_revision: str | None = "m031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the contract, its addenda and its measurements."""
    op.create_table(
        "contrato",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("eac_item_id", sa.BigInteger(), nullable=True),
        sa.Column("pacote_compra_id", sa.BigInteger(), nullable=True),
        sa.Column("gestor_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_id", sa.BigInteger(), nullable=False),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("objeto", sa.Text(), nullable=False),
        sa.Column("modalidade", sa.Text(), nullable=False),
        sa.Column("valor_original_centavos", sa.BigInteger(), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=False),
        sa.Column("termino_original", sa.Date(), nullable=False),
        sa.Column("termino_vigente", sa.Date(), nullable=False),
        sa.Column("retencao_pct", sa.Integer(), nullable=False),
        sa.Column("prazo_notificacao_claim_dias", sa.Integer(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["eac_item_id"], ["eac_item.id"], name=op.f("fk_contrato_eac_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_contrato_empresa_id")
        ),
        sa.ForeignKeyConstraint(["fiscal_id"], ["pessoa.id"], name=op.f("fk_contrato_fiscal_id")),
        sa.ForeignKeyConstraint(["gestor_id"], ["pessoa.id"], name=op.f("fk_contrato_gestor_id")),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_contrato_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato")),
        sa.UniqueConstraint("numero", name=op.f("uq_contrato_numero")),
    )
    op.create_table(
        "contrato_aditivo",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contrato_id", sa.BigInteger(), nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=True),
        sa.Column("claim_id", sa.BigInteger(), nullable=True),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("dias", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contrato_id"], ["contrato.id"], name=op.f("fk_contrato_aditivo_contrato_id")
        ),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_contrato_aditivo_mudanca_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato_aditivo")),
    )
    op.create_table(
        "contrato_medicao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contrato_id", sa.BigInteger(), nullable=False),
        sa.Column("marco_id", sa.BigInteger(), nullable=True),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("bruto_centavos", sa.BigInteger(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("motivo_devolucao", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["contrato_id"], ["contrato.id"], name=op.f("fk_contrato_medicao_contrato_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato_medicao")),
    )


def downgrade() -> None:
    """Drop the measurements, the addenda and the contract, in the reverse order."""
    op.drop_table("contrato_medicao")
    op.drop_table("contrato_aditivo")
    op.drop_table("contrato")
