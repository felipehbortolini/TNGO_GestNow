"""Marcos de pagamento, claims e extensões de prazo (ISSUE-033).

As três tabelas da administração contratual que fecham a ficha do contrato, como em
``docs/MODELO-DE-DADOS.md``: o marco de pagamento com critério, percentual e a evidência da
aprovação (``anexo``); o claim com direção, tipo, causa, datas, valores e dias pleiteados e
reconhecidos, risco e SM vinculados; e a EOT com claim de origem, dias, classificação, método e a
SM criada na concessão. Valor e retenção do marco, exposição e alerta de notificação são
calculados, não são coluna.

A mesma migração acrescenta as chaves estrangeiras que a m032 deixou adiadas (D9):
``contrato_aditivo.claim_id`` passa a apontar para ``contrato_claim`` e ``contrato_medicao.marco_id``
para ``contrato_marco_pagamento``.

Revision ID: m033
Revises: m032
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m033"
down_revision: str | None = "m032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the milestones, the claims and the time extensions, and close the delayed FKs."""
    op.create_table(
        "contrato_marco_pagamento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contrato_id", sa.BigInteger(), nullable=False),
        sa.Column("anexo_id", sa.BigInteger(), nullable=True),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("criterio", sa.Text(), nullable=False),
        sa.Column("pct", sa.Integer(), nullable=False),
        sa.Column("data_prevista", sa.Date(), nullable=False),
        sa.Column("data_conclusao", sa.Date(), nullable=True),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["anexo_id"], ["anexo.id"], name=op.f("fk_contrato_marco_pagamento_anexo_id")
        ),
        sa.ForeignKeyConstraint(
            ["contrato_id"], ["contrato.id"], name=op.f("fk_contrato_marco_pagamento_contrato_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato_marco_pagamento")),
    )
    op.create_table(
        "contrato_claim",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contrato_id", sa.BigInteger(), nullable=False),
        sa.Column("risco_id", sa.BigInteger(), nullable=True),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("direcao", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("causa", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("clausula", sa.Text(), nullable=True),
        sa.Column("data_evento", sa.Date(), nullable=False),
        sa.Column("data_notificacao", sa.Date(), nullable=False),
        sa.Column("pleiteado_centavos", sa.BigInteger(), nullable=False),
        sa.Column("dias_pleiteados", sa.Integer(), nullable=False),
        sa.Column("reconhecido_centavos", sa.BigInteger(), nullable=True),
        sa.Column("dias_reconhecidos", sa.Integer(), nullable=True),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("data_encerramento", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["contrato_id"], ["contrato.id"], name=op.f("fk_contrato_claim_contrato_id")
        ),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_contrato_claim_mudanca_id")
        ),
        sa.ForeignKeyConstraint(
            ["risco_id"], ["risco.id"], name=op.f("fk_contrato_claim_risco_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato_claim")),
        sa.UniqueConstraint("codigo", name=op.f("uq_contrato_claim_codigo")),
    )
    op.create_table(
        "contrato_extensao_prazo",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contrato_id", sa.BigInteger(), nullable=False),
        sa.Column("claim_id", sa.BigInteger(), nullable=True),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("evento", sa.Text(), nullable=False),
        sa.Column("dias_solicitados", sa.Integer(), nullable=False),
        sa.Column("dias_concedidos", sa.Integer(), nullable=True),
        sa.Column("classificacao", sa.Text(), nullable=True),
        sa.Column("metodo", sa.Text(), nullable=False),
        sa.Column("marco_afetado", sa.Text(), nullable=False),
        sa.Column("data_solicitacao", sa.Date(), nullable=False),
        sa.Column("data_decisao", sa.Date(), nullable=True),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["contrato_claim.id"], name=op.f("fk_contrato_extensao_prazo_claim_id")
        ),
        sa.ForeignKeyConstraint(
            ["contrato_id"],
            ["contrato.id"],
            name=op.f("fk_contrato_extensao_prazo_contrato_id"),
        ),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_contrato_extensao_prazo_mudanca_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato_extensao_prazo")),
        sa.UniqueConstraint("codigo", name=op.f("uq_contrato_extensao_prazo_codigo")),
    )
    op.create_foreign_key(
        op.f("fk_contrato_aditivo_claim_id"),
        "contrato_aditivo",
        "contrato_claim",
        ["claim_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_contrato_medicao_marco_id"),
        "contrato_medicao",
        "contrato_marco_pagamento",
        ["marco_id"],
        ["id"],
    )


def downgrade() -> None:
    """Drop the delayed FKs, then the EOT, the claims and the milestones, in that order."""
    op.drop_constraint(op.f("fk_contrato_medicao_marco_id"), "contrato_medicao", type_="foreignkey")
    op.drop_constraint(op.f("fk_contrato_aditivo_claim_id"), "contrato_aditivo", type_="foreignkey")
    op.drop_table("contrato_extensao_prazo")
    op.drop_table("contrato_claim")
    op.drop_table("contrato_marco_pagamento")
