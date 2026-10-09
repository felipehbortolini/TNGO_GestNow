"""Processos de compra: processo, convidados, propostas e negociações (ISSUE-059).

As quatro tabelas do módulo `suprimentos` como estão em ``docs/MODELO-DE-DADOS.md``: o processo
de compra (RFx) de um pacote (``processo_compra``, UK por número, com os pesos, a data-limite e
os campos da recomendação e da aprovação que a ISSUE-060 preenche), os fornecedores convidados
(``processo_convidado``), as propostas recebidas (``processo_proposta``; o PDF é um ``anexo``) e
as rodadas de negociação (``processo_negociacao``, fato imutável). O convidado, a proposta e a
negociação guardam ``nome`` quando o fornecedor não está no cadastro, como o protótipo aceitava;
notas, ranking e saving não têm coluna: são calculados na leitura.

Revision ID: m047
Revises: m046
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m047"
down_revision: str | None = "m046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the process, its invitees, its proposals and its negotiations."""
    op.create_table(
        "processo_compra",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pacote_id", sa.BigInteger(), nullable=False),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("peso_tecnico", sa.Integer(), nullable=False),
        sa.Column("peso_comercial", sa.Integer(), nullable=False),
        sa.Column("data_limite_propostas", sa.Date(), nullable=False),
        sa.Column("recomendacao_em", sa.Date(), nullable=True),
        sa.Column("recomendacao_fornecedor_id", sa.BigInteger(), nullable=True),
        sa.Column("recomendacao_valor_centavos", sa.BigInteger(), nullable=True),
        sa.Column("recomendacao_por_id", sa.BigInteger(), nullable=True),
        sa.Column("recomendacao_justificativa", sa.Text(), nullable=True),
        sa.Column("aprovacao_em", sa.Date(), nullable=True),
        sa.Column("aprovacao_por_id", sa.BigInteger(), nullable=True),
        sa.Column("aprovacao_alcada", sa.Text(), nullable=True),
        sa.Column("aprovacao_parecer", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pacote_id"], ["pacote_compra.id"], name=op.f("fk_processo_compra_pacote_id")
        ),
        sa.ForeignKeyConstraint(
            ["recomendacao_fornecedor_id"],
            ["empresa.id"],
            name=op.f("fk_processo_compra_recomendacao_fornecedor_id"),
        ),
        sa.ForeignKeyConstraint(
            ["recomendacao_por_id"],
            ["pessoa.id"],
            name=op.f("fk_processo_compra_recomendacao_por_id"),
        ),
        sa.ForeignKeyConstraint(
            ["aprovacao_por_id"], ["pessoa.id"], name=op.f("fk_processo_compra_aprovacao_por_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processo_compra")),
        sa.UniqueConstraint("numero", name=op.f("uq_processo_compra_numero")),
    )
    op.create_table(
        "processo_convidado",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("processo_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("nome", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["processo_id"], ["processo_compra.id"], name=op.f("fk_processo_convidado_processo_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_processo_convidado_empresa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processo_convidado")),
    )
    op.create_table(
        "processo_proposta",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("processo_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("nome", sa.Text(), nullable=True),
        sa.Column("recebida", sa.Date(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("prazo_dias", sa.Integer(), nullable=False),
        sa.Column("validade", sa.Date(), nullable=True),
        sa.Column("nota_tecnica", sa.Integer(), nullable=True),
        sa.Column("tecnicamente_aprovada", sa.Boolean(), nullable=True),
        sa.Column("desvios", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["processo_id"], ["processo_compra.id"], name=op.f("fk_processo_proposta_processo_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_processo_proposta_empresa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processo_proposta")),
    )
    op.create_table(
        "processo_negociacao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("processo_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("nome", sa.Text(), nullable=True),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["processo_id"], ["processo_compra.id"], name=op.f("fk_processo_negociacao_processo_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_processo_negociacao_empresa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processo_negociacao")),
    )


def downgrade() -> None:
    """Drop the negotiations, the proposals, the invitees and the process."""
    op.drop_table("processo_negociacao")
    op.drop_table("processo_proposta")
    op.drop_table("processo_convidado")
    op.drop_table("processo_compra")
