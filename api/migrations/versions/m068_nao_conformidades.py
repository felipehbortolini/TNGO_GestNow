"""nao conformidades (rnc)

Revision ID: m068
Revises: m067
Create Date: 2026-10-09 09:00:00.000000

RNC do 06 Qualidade (ISSUE-068): ``rnc``, como em ``docs/MODELO-DE-DADOS.md`` — a não
conformidade com a disciplina, a empresa, o responsável pela análise, quem abriu, quem
verificou a eficácia e a lição do encerramento; a situação, a severidade, a origem, a
disposição e o método com CHECK; o custo da não qualidade em centavos e a trilha da
eficácia. A reincidência é calculada da trilha (não há coluna); a evidência da abertura
é um ``anexo`` (D5a), não uma coluna. UK: projeto + código.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m068"
down_revision: str | None = "m067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rnc",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("disciplina_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=False),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=True),
        sa.Column("aberta_por_id", sa.BigInteger(), nullable=False),
        sa.Column("eficacia_por_id", sa.BigInteger(), nullable=True),
        sa.Column("licao_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("origem_ref", sa.Text(), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("severidade", sa.Text(), nullable=False),
        sa.Column("contencao", sa.Text(), nullable=False),
        sa.Column("disposicao", sa.Text(), nullable=True),
        sa.Column("concessao_referencia", sa.Text(), nullable=True),
        sa.Column("concessao_data", sa.Date(), nullable=True),
        sa.Column("metodo", sa.Text(), nullable=True),
        sa.Column("causa_raiz", sa.Text(), nullable=True),
        sa.Column("prazo", sa.Date(), nullable=False),
        sa.Column("encerramento", sa.Date(), nullable=True),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column(
            "custo_nao_qualidade_centavos",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("verificacao_prevista", sa.Date(), nullable=True),
        sa.Column("eficacia_data", sa.Date(), nullable=True),
        sa.Column("eficacia_eficaz", sa.Boolean(), nullable=True),
        sa.Column("eficacia_texto", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "situacao IN ('Aberta', 'Em análise de causa', 'Ação corretiva', "
            "'Verificação de eficácia', 'Encerrada', 'Cancelada')",
            name=op.f("ck_rnc_situacao"),
        ),
        sa.CheckConstraint(
            "origem IN ('Inspeção', 'Inspeção de fabricação', 'Auditoria', 'Fornecedor', "
            "'Processo', 'Cliente')",
            name=op.f("ck_rnc_origem"),
        ),
        sa.CheckConstraint(
            "severidade IN ('Crítica', 'Maior', 'Menor')", name=op.f("ck_rnc_severidade")
        ),
        sa.CheckConstraint(
            "disposicao IS NULL OR disposicao IN ('Retrabalho', 'Reparo', 'Usar como está', "
            "'Rejeitar', 'Reclassificar')",
            name=op.f("ck_rnc_disposicao"),
        ),
        sa.CheckConstraint(
            "metodo IS NULL OR metodo IN ('5 porquês', 'Diagrama de Ishikawa', 'Árvore de causas')",
            name=op.f("ck_rnc_metodo"),
        ),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_rnc_projeto_id")),
        sa.ForeignKeyConstraint(
            ["disciplina_id"], ["disciplina.id"], name=op.f("fk_rnc_disciplina_id")
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"], name=op.f("fk_rnc_empresa_id")),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_rnc_responsavel_id")
        ),
        sa.ForeignKeyConstraint(
            ["aberta_por_id"], ["pessoa.id"], name=op.f("fk_rnc_aberta_por_id")
        ),
        sa.ForeignKeyConstraint(
            ["eficacia_por_id"], ["pessoa.id"], name=op.f("fk_rnc_eficacia_por_id")
        ),
        sa.ForeignKeyConstraint(["licao_id"], ["licao.id"], name=op.f("fk_rnc_licao_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rnc")),
        sa.UniqueConstraint("projeto_id", "codigo", name=op.f("uq_rnc_projeto_id_codigo")),
    )


def downgrade() -> None:
    op.drop_table("rnc")
