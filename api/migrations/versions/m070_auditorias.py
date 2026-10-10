"""auditorias da qualidade

Revision ID: m070
Revises: m069
Create Date: 2026-10-10 12:00:00.000000

Auditorias do 06 Qualidade (ISSUE-070): ``auditoria_qualidade``, ``auditoria_constatacao`` e
``auditoria_reprogramacao``, como em ``docs/MODELO-DE-DADOS.md`` — o programa (tipo, auditado,
escopo, data, situação, realização, itens verificados e conformes e critério), as constatações
(cada Não conformidade abre a RNC pela FK ``rnc_id``, na mesma transação) e a reprogramação
justificada (data anterior, nova data, autor e momento). A coluna ``resumo`` (a conclusão da
auditoria) foi acrescentada na mesma entrega, porque o protótipo a coleta e a ficha a exibe e o
MODELO §11 não a tinha; o diagrama muda junto. UK: ``auditoria_qualidade`` por projeto + código.
A ``auditoria_qualidade.auditado`` fica como o MODELO desenha (o registro textual do auditado);
nesta fatia sem fonte, não preenchida.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m070"
down_revision: str | None = "m069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auditoria_qualidade",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("auditor_id", sa.BigInteger(), nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("auditado", sa.Text(), nullable=True),
        sa.Column("escopo", sa.Text(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("realizada_em", sa.Date(), nullable=True),
        sa.Column("itens_verificados", sa.Integer(), nullable=True),
        sa.Column("itens_conformes", sa.Integer(), nullable=True),
        sa.Column("criterio", sa.Text(), nullable=False),
        sa.Column("resumo", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('Contratada', 'Fornecedor', 'Interna')",
            name=op.f("ck_auditoria_qualidade_tipo"),
        ),
        sa.CheckConstraint(
            "situacao IN ('Planejada', 'Realizada')",
            name=op.f("ck_auditoria_qualidade_situacao"),
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_auditoria_qualidade_projeto_id")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_auditoria_qualidade_empresa_id")
        ),
        sa.ForeignKeyConstraint(
            ["auditor_id"], ["pessoa.id"], name=op.f("fk_auditoria_qualidade_auditor_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auditoria_qualidade")),
        sa.UniqueConstraint(
            "projeto_id", "codigo", name=op.f("uq_auditoria_qualidade_projeto_id_codigo")
        ),
    )
    op.create_table(
        "auditoria_constatacao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("auditoria_id", sa.BigInteger(), nullable=False),
        sa.Column("rnc_id", sa.BigInteger(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("requisito", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('Não conformidade', 'Observação', 'Oportunidade de melhoria')",
            name=op.f("ck_auditoria_constatacao_tipo"),
        ),
        sa.ForeignKeyConstraint(
            ["auditoria_id"],
            ["auditoria_qualidade.id"],
            name=op.f("fk_auditoria_constatacao_auditoria_id"),
        ),
        sa.ForeignKeyConstraint(
            ["rnc_id"], ["rnc.id"], name=op.f("fk_auditoria_constatacao_rnc_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auditoria_constatacao")),
    )
    op.create_table(
        "auditoria_reprogramacao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("auditoria_id", sa.BigInteger(), nullable=False),
        sa.Column("autor_id", sa.BigInteger(), nullable=False),
        sa.Column("data_anterior", sa.Date(), nullable=False),
        sa.Column("data_nova", sa.Date(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.Column(
            "registrada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["auditoria_id"],
            ["auditoria_qualidade.id"],
            name=op.f("fk_auditoria_reprogramacao_auditoria_id"),
        ),
        sa.ForeignKeyConstraint(
            ["autor_id"], ["pessoa.id"], name=op.f("fk_auditoria_reprogramacao_autor_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auditoria_reprogramacao")),
    )


def downgrade() -> None:
    op.drop_table("auditoria_reprogramacao")
    op.drop_table("auditoria_constatacao")
    op.drop_table("auditoria_qualidade")
