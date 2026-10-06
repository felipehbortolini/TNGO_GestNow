"""eap: arvore, etapas, medicoes, revisoes e desdobramentos

Revision ID: m036
Revises: m072
Create Date: 2026-10-06 12:00:00.000000

The EAP of the Planejamento module (ISSUE-036), as in ``docs/MODELO-DE-DADOS.md``:
``eap_item``, ``eap_item_etapa``, ``eap_medicao``, ``eap_revisao``, ``eap_revisao_item`` and
``eap_desdobramento``. No indicator is a column: progress, deviation and the totals of the levels
are calculated.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m036"
down_revision: str | None = "m049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eap_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("pai_id", sa.BigInteger(), nullable=True),
        sa.Column("eac_item_id", sa.BigInteger(), nullable=True),
        sa.Column("unidade_id", sa.BigInteger(), nullable=True),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=True),
        sa.Column("criterio", sa.Text(), nullable=True),
        sa.Column("modelo", sa.Text(), nullable=True),
        sa.Column("quantidade", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("peso", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("previsto", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("inicio", sa.Date(), nullable=True),
        sa.Column("termino", sa.Date(), nullable=True),
        sa.Column("entregavel", sa.Text(), nullable=True),
        sa.Column("aceitacao", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["eac_item_id"], ["eac_item.id"], name=op.f("fk_eap_item_eac_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_eap_item_empresa_id")
        ),
        sa.ForeignKeyConstraint(["pai_id"], ["eap_item.id"], name=op.f("fk_eap_item_pai_id")),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_eap_item_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_eap_item_responsavel_id")
        ),
        sa.ForeignKeyConstraint(
            ["unidade_id"], ["unidade.id"], name=op.f("fk_eap_item_unidade_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eap_item")),
        sa.UniqueConstraint("projeto_id", "codigo", name=op.f("uq_eap_item_projeto_id_codigo")),
    )
    op.create_table(
        "eap_item_etapa",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("peso", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["eap_item.id"], name=op.f("fk_eap_item_etapa_item_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eap_item_etapa")),
    )
    op.create_table(
        "eap_medicao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("autor_id", sa.BigInteger(), nullable=True),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("de", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("para", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["autor_id"], ["pessoa.id"], name=op.f("fk_eap_medicao_autor_id")),
        sa.ForeignKeyConstraint(["item_id"], ["eap_item.id"], name=op.f("fk_eap_medicao_item_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eap_medicao")),
    )
    op.create_table(
        "eap_revisao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=True),
        sa.Column("aprovado_por_id", sa.BigInteger(), nullable=True),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("alteracao", sa.Text(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["aprovado_por_id"], ["pessoa.id"], name=op.f("fk_eap_revisao_aprovado_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_eap_revisao_mudanca_id")
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_eap_revisao_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eap_revisao")),
        sa.UniqueConstraint(
            "projeto_id", "revisao", name=op.f("uq_eap_revisao_projeto_id_revisao")
        ),
    )
    op.create_table(
        "eap_revisao_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("revisao_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("peso", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["eap_item.id"], name=op.f("fk_eap_revisao_item_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["revisao_id"], ["eap_revisao.id"], name=op.f("fk_eap_revisao_item_revisao_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eap_revisao_item")),
        sa.UniqueConstraint(
            "revisao_id", "item_id", name=op.f("uq_eap_revisao_item_revisao_id_item_id")
        ),
    )
    op.create_table(
        "eap_desdobramento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("origem_item_id", sa.BigInteger(), nullable=False),
        sa.Column("destino_item_id", sa.BigInteger(), nullable=False),
        sa.Column("por_id", sa.BigInteger(), nullable=True),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("peso", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["destino_item_id"], ["eap_item.id"], name=op.f("fk_eap_desdobramento_destino_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["origem_item_id"], ["eap_item.id"], name=op.f("fk_eap_desdobramento_origem_item_id")
        ),
        sa.ForeignKeyConstraint(
            ["por_id"], ["pessoa.id"], name=op.f("fk_eap_desdobramento_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_eap_desdobramento_projeto_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eap_desdobramento")),
    )


def downgrade() -> None:
    op.drop_table("eap_desdobramento")
    op.drop_table("eap_revisao_item")
    op.drop_table("eap_revisao")
    op.drop_table("eap_medicao")
    op.drop_table("eap_item_etapa")
    op.drop_table("eap_item")
