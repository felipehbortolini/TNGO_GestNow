"""solicitacao de mudanca

Revision ID: m023
Revises: 0003
Create Date: 2026-10-06 09:00:00.000000

The tables of the change request (SM) of Governança (ISSUE-023): the request, the analysis in
progress, the impact analysis and its EAC items, the proposed reallocations, the decisions and
their participants, as in ``docs/MODELO-DE-DADOS.md``. ``eac_item_id`` (Financeiro) and ``licao_id``
(lessons) carry no foreign key yet: the migration that creates ``eac_item`` and ``licao`` adds it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m023"
down_revision: str | None = "m019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mudanca",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("solicitante_id", sa.BigInteger(), nullable=False),
        sa.Column("encerrado_por_id", sa.BigInteger(), nullable=True),
        sa.Column("licao_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("prioridade", sa.Text(), nullable=False),
        sa.Column("data_solicitacao", sa.Date(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("fonte_recurso", sa.Text(), nullable=True),
        sa.Column("alcada", sa.Text(), nullable=True),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("emergencial", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("justificativa_emergencial", sa.Text(), nullable=True),
        sa.Column("data_inicio_implementacao", sa.Date(), nullable=True),
        sa.Column("data_encerramento", sa.Date(), nullable=True),
        sa.Column("encerrou_cronograma", sa.Boolean(), nullable=True),
        sa.Column("encerrou_contrato", sa.Boolean(), nullable=True),
        sa.Column("encerrou_riscos", sa.Boolean(), nullable=True),
        sa.Column("eac_revisao_incorporada", sa.Integer(), nullable=True),
        sa.Column("eap_revisao_incorporada", sa.Integer(), nullable=True),
        sa.Column("encerramento_observacao", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('Escopo', 'Prazo', 'Custo', 'Qualidade/Especificação', 'Contratual', "
            "'Remanejamento de orçamento', 'Liberação de reserva')",
            name=op.f("ck_mudanca_tipo"),
        ),
        sa.CheckConstraint(
            "origem IN ('Cliente', 'Contratada', 'Engenharia', 'Interna', 'Legal/regulatória')",
            name=op.f("ck_mudanca_origem"),
        ),
        sa.CheckConstraint(
            "prioridade IN ('Normal', 'Urgente', 'Emergencial')",
            name=op.f("ck_mudanca_prioridade"),
        ),
        sa.CheckConstraint(
            "situacao IN ('Registrada', 'Em análise de impacto', 'Aguardando comitê', "
            "'Aprovada', 'Aprovada com condições', 'Rejeitada', 'Adiada', 'Em implementação', "
            "'Encerrada', 'Cancelada')",
            name=op.f("ck_mudanca_situacao"),
        ),
        sa.CheckConstraint(
            "alcada IS NULL OR alcada IN ('Gerente do projeto', 'Comitê')",
            name=op.f("ck_mudanca_alcada"),
        ),
        sa.CheckConstraint(
            "fonte_recurso IS NULL OR fonte_recurso IN ('Aditivo de orçamento', "
            "'Reserva de contingência', 'Reserva gerencial')",
            name=op.f("ck_mudanca_fonte_recurso"),
        ),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_mudanca_projeto_id")),
        sa.ForeignKeyConstraint(
            ["solicitante_id"], ["pessoa.id"], name=op.f("fk_mudanca_solicitante_id")
        ),
        sa.ForeignKeyConstraint(
            ["encerrado_por_id"], ["pessoa.id"], name=op.f("fk_mudanca_encerrado_por_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mudanca")),
        sa.UniqueConstraint("codigo", name=op.f("uq_mudanca_codigo")),
    )
    op.create_table(
        "mudanca_analise",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=False),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("prazo", sa.Date(), nullable=False),
        sa.Column("concluida_em", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_mudanca_analise_mudanca_id")
        ),
        sa.ForeignKeyConstraint(
            ["responsavel_id"], ["pessoa.id"], name=op.f("fk_mudanca_analise_responsavel_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mudanca_analise")),
    )
    op.create_table(
        "mudanca_impacto",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=False),
        sa.Column("analista_id", sa.BigInteger(), nullable=False),
        sa.Column("data_analise", sa.Date(), nullable=False),
        sa.Column("custo_centavos", sa.BigInteger(), nullable=False),
        sa.Column("prazo_dias", sa.Integer(), nullable=False),
        sa.Column("escopo", sa.Text(), nullable=False),
        sa.Column("qualidade", sa.Text(), nullable=False),
        sa.Column("riscos", sa.Text(), nullable=False),
        sa.Column("sms", sa.Text(), nullable=False),
        sa.Column("contrato", sa.Text(), nullable=False),
        sa.Column("afeta_marco_contratual", sa.Boolean(), nullable=False),
        sa.Column("atividades", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_mudanca_impacto_mudanca_id")
        ),
        sa.ForeignKeyConstraint(
            ["analista_id"], ["pessoa.id"], name=op.f("fk_mudanca_impacto_analista_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mudanca_impacto")),
    )
    op.create_table(
        "mudanca_impacto_eac_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("impacto_id", sa.BigInteger(), nullable=False),
        sa.Column("eac_item_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["impacto_id"],
            ["mudanca_impacto.id"],
            name=op.f("fk_mudanca_impacto_eac_item_impacto_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mudanca_impacto_eac_item")),
    )
    op.create_table(
        "mudanca_remanejamento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=False),
        sa.Column("origem_item_id", sa.BigInteger(), nullable=False),
        sa.Column("destino_item_id", sa.BigInteger(), nullable=False),
        sa.Column("aplicado_por_id", sa.BigInteger(), nullable=True),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("aplicado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("aplicado_em", sa.Date(), nullable=True),
        sa.Column("revisao_eac", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_mudanca_remanejamento_mudanca_id")
        ),
        sa.ForeignKeyConstraint(
            ["aplicado_por_id"],
            ["pessoa.id"],
            name=op.f("fk_mudanca_remanejamento_aplicado_por_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mudanca_remanejamento")),
    )
    op.create_table(
        "mudanca_decisao",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("resultado", sa.Text(), nullable=False),
        sa.Column("condicoes", sa.Text(), nullable=True),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "resultado IN ('Aprovada', 'Aprovada com condições', 'Rejeitada', 'Adiada')",
            name=op.f("ck_mudanca_decisao_resultado"),
        ),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_mudanca_decisao_mudanca_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mudanca_decisao")),
    )
    op.create_table(
        "mudanca_decisao_participante",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("decisao_id", sa.BigInteger(), nullable=False),
        sa.Column("pessoa_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["decisao_id"],
            ["mudanca_decisao.id"],
            name=op.f("fk_mudanca_decisao_participante_decisao_id"),
        ),
        sa.ForeignKeyConstraint(
            ["pessoa_id"], ["pessoa.id"], name=op.f("fk_mudanca_decisao_participante_pessoa_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mudanca_decisao_participante")),
    )


def downgrade() -> None:
    op.drop_table("mudanca_decisao_participante")
    op.drop_table("mudanca_decisao")
    op.drop_table("mudanca_remanejamento")
    op.drop_table("mudanca_impacto_eac_item")
    op.drop_table("mudanca_impacto")
    op.drop_table("mudanca_analise")
    op.drop_table("mudanca")
