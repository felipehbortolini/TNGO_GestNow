"""ocorrencias com investigacao e dados restritos (LGPD)

Revision ID: m073
Revises: m070
Create Date: 2026-10-10 09:00:00.000000

Ocorrências do 07 HSE (ISSUE-073): ``ocorrencia`` — o registro sem dado pessoal, com a
gravidade potencial (P x I), o HiPo, o ambiental com a severidade própria, as horas até a
comunicação e os **prazos vigentes gravados** (comunicação, investigação preliminar e
relatório final, D5b) —, ``ocorrencia_restrito`` — o acesso restrito da LGPD (Q35): nome e
dados médicos, um por ocorrência — e ``ocorrencia_investigacao`` — o fato da investigação
(método, causa raiz, data e responsável), sem ``versao`` —, como em
``docs/MODELO-DE-DADOS.md``. Os dois títulos (``data_encerramento`` e ``eficacia``) foram
acrescentados ao desenho na mesma entrega: o protótipo guardava o encerramento e o diagrama
não tinha onde. UK: projeto + código na ocorrência e a ocorrência no restrito.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m073"
down_revision: str | None = "m070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False)


def _version() -> sa.Column:
    return sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=op.f(f"fk_{table}_{column}"))


def upgrade() -> None:
    op.create_table(
        "ocorrencia",
        _id(),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("empresa_id", sa.BigInteger(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("data_hora", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("subtipo", sa.Text(), nullable=True),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("local", sa.Text(), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("funcao", sa.Text(), nullable=True),
        sa.Column("pessoas_envolvidas", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("potencial_p", sa.Integer(), nullable=True),
        sa.Column("potencial_i", sa.Integer(), nullable=True),
        sa.Column("hipo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ambiental", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("severidade_ambiental", sa.Text(), nullable=True),
        sa.Column("causa_imediata", sa.Text(), nullable=True),
        sa.Column("comunicacao_horas", sa.Integer(), nullable=False),
        sa.Column("prazo_comunicacao_horas", sa.Integer(), nullable=False),
        sa.Column("prazo_investigacao_horas", sa.Integer(), nullable=False),
        sa.Column("prazo_relatorio_dias", sa.Integer(), nullable=False),
        sa.Column("situacao", sa.Text(), nullable=False),
        sa.Column("data_encerramento", sa.Date(), nullable=True),
        sa.Column("eficacia", sa.Text(), nullable=True),
        _version(),
        sa.CheckConstraint(
            "tipo IN ('Fatalidade', 'Acidente com afastamento', 'Trabalho restrito', "
            "'Tratamento médico', 'Primeiros socorros', 'Dano material', 'Quase acidente', "
            "'Ambiental')",
            name=op.f("ck_ocorrencia_tipo"),
        ),
        sa.CheckConstraint(
            "situacao IN ('Registrada', 'Em investigação', 'Ações definidas', 'Em tratamento', "
            "'Encerrada')",
            name=op.f("ck_ocorrencia_situacao"),
        ),
        sa.CheckConstraint(
            "subtipo IS NULL OR subtipo IN ('Vazamento', 'Emissão', 'Resíduo', 'Outro')",
            name=op.f("ck_ocorrencia_subtipo"),
        ),
        sa.CheckConstraint(
            "severidade_ambiental IS NULL OR severidade_ambiental IN ('Baixa', 'Moderada', 'Alta')",
            name=op.f("ck_ocorrencia_severidade_ambiental"),
        ),
        sa.CheckConstraint(
            "potencial_p IS NULL OR potencial_p BETWEEN 1 AND 5",
            name=op.f("ck_ocorrencia_potencial_p"),
        ),
        sa.CheckConstraint(
            "potencial_i IS NULL OR potencial_i BETWEEN 1 AND 5",
            name=op.f("ck_ocorrencia_potencial_i"),
        ),
        _fk("ocorrencia", "projeto_id", "projeto.id"),
        _fk("ocorrencia", "empresa_id", "empresa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocorrencia")),
        sa.UniqueConstraint("projeto_id", "codigo", name=op.f("uq_ocorrencia_projeto_id_codigo")),
    )
    op.create_table(
        "ocorrencia_restrito",
        _id(),
        sa.Column("ocorrencia_id", sa.BigInteger(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=True),
        sa.Column("gravidade_real", sa.Integer(), nullable=True),
        sa.Column("dias_perdidos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("dias_debitados", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cat", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("descricao_medica", sa.Text(), nullable=True),
        _version(),
        _fk("ocorrencia_restrito", "ocorrencia_id", "ocorrencia.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocorrencia_restrito")),
        sa.UniqueConstraint("ocorrencia_id", name=op.f("uq_ocorrencia_restrito_ocorrencia_id")),
    )
    op.create_table(
        "ocorrencia_investigacao",
        _id(),
        sa.Column("ocorrencia_id", sa.BigInteger(), nullable=False),
        sa.Column("responsavel_id", sa.BigInteger(), nullable=False),
        sa.Column("metodo", sa.Text(), nullable=False),
        sa.Column("causa_raiz", sa.Text(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.CheckConstraint(
            "metodo IN ('5 porquês', 'Árvore de causas')",
            name=op.f("ck_ocorrencia_investigacao_metodo"),
        ),
        _fk("ocorrencia_investigacao", "ocorrencia_id", "ocorrencia.id"),
        _fk("ocorrencia_investigacao", "responsavel_id", "pessoa.id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocorrencia_investigacao")),
    )


def downgrade() -> None:
    op.drop_table("ocorrencia_investigacao")
    op.drop_table("ocorrencia_restrito")
    op.drop_table("ocorrencia")
