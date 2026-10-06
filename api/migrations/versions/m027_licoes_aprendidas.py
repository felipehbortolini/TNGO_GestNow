"""licoes aprendidas

Revision ID: m027
Revises: 0003
Create Date: 2026-10-06 13:00:00.000000

The lessons learned of Governança (ISSUE-027): the lesson, its keywords, each reuse (application in a
project) and the history of the flow, as in ``docs/MODELO-DE-DADOS.md``. ``licao_historico`` is new in
the model: the comment of a return to Rascunho and each step of the flow live there. The foreign key
``mudanca.licao_id`` that ISSUE-023 left open is added here, because ``licao`` now exists.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m027"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "licao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("disciplina_id", sa.BigInteger(), nullable=True),
        sa.Column("autor_id", sa.BigInteger(), nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("fase", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("origem_ref", sa.Text(), nullable=True),
        sa.Column("aconteceu", sa.Text(), nullable=False),
        sa.Column("causa", sa.Text(), nullable=False),
        sa.Column("impacto_prazo_dias", sa.Integer(), nullable=False),
        sa.Column("impacto_custo_centavos", sa.BigInteger(), nullable=False),
        sa.Column("recomendacao", sa.Text(), nullable=False),
        sa.Column("aplicabilidade", sa.Text(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("tipo IN ('A repetir', 'A evitar')", name=op.f("ck_licao_tipo")),
        sa.CheckConstraint(
            "fase IN ('Iniciação', 'Engenharia', 'Suprimentos', 'Construção', "
            "'Comissionamento', 'Encerramento')",
            name=op.f("ck_licao_fase"),
        ),
        sa.CheckConstraint(
            "area IN ('Escopo', 'Cronograma', 'Custos', 'Qualidade', 'Recursos', 'Comunicações', "
            "'Riscos', 'Aquisições', 'Partes interessadas', 'SMS')",
            name=op.f("ck_licao_area"),
        ),
        sa.CheckConstraint(
            "origem IN ('Ata', 'Punch list', 'Contrato', 'Suprimentos', 'Risco', 'RNC', 'HSE', "
            "'Mudança', 'Workshop de lições', 'Encerramento do projeto', 'Registro direto')",
            name=op.f("ck_licao_origem"),
        ),
        sa.CheckConstraint(
            "aplicabilidade IN ('Projeto', 'Corporativa')", name=op.f("ck_licao_aplicabilidade")
        ),
        sa.CheckConstraint(
            "situacao IN ('Rascunho', 'Em validação', 'Validada', 'Publicada')",
            name=op.f("ck_licao_situacao"),
        ),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_licao_projeto_id")),
        sa.ForeignKeyConstraint(
            ["disciplina_id"], ["disciplina.id"], name=op.f("fk_licao_disciplina_id")
        ),
        sa.ForeignKeyConstraint(["autor_id"], ["pessoa.id"], name=op.f("fk_licao_autor_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_licao")),
        sa.UniqueConstraint("codigo", name=op.f("uq_licao_codigo")),
    )
    op.create_table(
        "licao_palavra_chave",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("licao_id", sa.BigInteger(), nullable=False),
        sa.Column("palavra", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["licao_id"], ["licao.id"], name=op.f("fk_licao_palavra_chave_licao_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_licao_palavra_chave")),
    )
    op.create_table(
        "licao_aplicacao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("licao_id", sa.BigInteger(), nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("acao_id", sa.BigInteger(), nullable=True),
        sa.Column("risco_id", sa.BigInteger(), nullable=True),
        sa.Column("registrado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("como", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["licao_id"], ["licao.id"], name=op.f("fk_licao_aplicacao_licao_id")
        ),
        sa.ForeignKeyConstraint(
            ["projeto_id"], ["projeto.id"], name=op.f("fk_licao_aplicacao_projeto_id")
        ),
        sa.ForeignKeyConstraint(["acao_id"], ["acao.id"], name=op.f("fk_licao_aplicacao_acao_id")),
        sa.ForeignKeyConstraint(
            ["registrado_por_id"], ["pessoa.id"], name=op.f("fk_licao_aplicacao_registrado_por_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_licao_aplicacao")),
    )
    op.create_table(
        "licao_historico",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("licao_id", sa.BigInteger(), nullable=False),
        sa.Column("pessoa_id", sa.BigInteger(), nullable=False),
        sa.Column("data_hora", sa.DateTime(timezone=True), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["licao_id"], ["licao.id"], name=op.f("fk_licao_historico_licao_id")
        ),
        sa.ForeignKeyConstraint(
            ["pessoa_id"], ["pessoa.id"], name=op.f("fk_licao_historico_pessoa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_licao_historico")),
    )
    op.create_foreign_key(op.f("fk_mudanca_licao_id"), "mudanca", "licao", ["licao_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(op.f("fk_mudanca_licao_id"), "mudanca", type_="foreignkey")
    op.drop_table("licao_historico")
    op.drop_table("licao_aplicacao")
    op.drop_table("licao_palavra_chave")
    op.drop_table("licao")
