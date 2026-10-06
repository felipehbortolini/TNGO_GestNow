"""registro de riscos

Revision ID: m064
Revises: 0003
Create Date: 2026-10-06 12:00:00.000000

Risk register (ISSUE-064): ``risco_categoria``, ``risco``, ``risco_avaliacao``, ``risco_revisao``
and ``risco_plano_aprovacao``, as drawn in ``docs/MODELO-DE-DADOS.md`` (``risco.identificado_em``
is the identification date of the form, added to the drawing with this slice). The columns
``ata_id``, ``mudanca_id``, ``licao_id`` and ``encerramento_mudanca_id`` are plain here; the
foreign keys come with the migrations of the minutes, the changes and the lessons.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m064"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FALSE = sa.text("false")
ZERO = sa.text("0")
ONE = sa.text("1")


def _id() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False)


def _bigint(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.BigInteger(), nullable=nullable)


def _text(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.Text(), nullable=nullable)


def _int(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.Integer(), nullable=nullable)


def _date(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.Date(), nullable=nullable)


def _flag(name: str) -> sa.Column:
    return sa.Column(name, sa.Boolean(), server_default=FALSE, nullable=False)


def _version() -> sa.Column:
    return sa.Column("versao", sa.Integer(), server_default=ONE, nullable=False)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}")
    )


def upgrade() -> None:
    op.create_table(
        "risco_categoria",
        _id(),
        _text("grupo", nullable=False),
        _text("nome", nullable=False),
        _version(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risco_categoria")),
    )
    op.create_table(
        "risco",
        _id(),
        _bigint("projeto_id", nullable=False),
        _bigint("categoria_id", nullable=False),
        _bigint("dono_id", nullable=False),
        _bigint("identificado_por_id", nullable=False),
        _bigint("ata_id"),
        _bigint("mudanca_id"),
        _bigint("licao_id"),
        _bigint("responsavel_plano_id"),
        _bigint("encerrado_por_id"),
        _bigint("ocultado_por_id"),
        _text("codigo", nullable=False),
        _text("titulo", nullable=False),
        _text("natureza", nullable=False),
        _text("origem_tipo", nullable=False),
        _text("origem"),
        _text("causa", nullable=False),
        _text("consequencia", nullable=False),
        _text("descricao"),
        _text("gatilho"),
        _flag("risco_vida"),
        _text("dimensao"),
        sa.Column("impacto_prazo_dias", sa.Integer(), server_default=ZERO, nullable=False),
        sa.Column("impacto_custo_centavos", sa.BigInteger(), server_default=ZERO, nullable=False),
        _text("estrategia"),
        _text("plano"),
        _text("severidade_alvo"),
        _date("prazo_alvo"),
        _bigint("custo_resposta_centavos"),
        _text("instrumento"),
        _int("cadencia_dias"),
        _date("ultima_revisao"),
        _date("proxima_revisao"),
        _text("situacao", nullable=False),
        _text("encerramento_motivo"),
        _date("encerramento_data"),
        _int("encerramento_impacto_prazo_dias"),
        _bigint("encerramento_impacto_custo_centavos"),
        _bigint("encerramento_mudanca_id"),
        _flag("oculto"),
        _text("motivo_exclusao"),
        sa.Column("ocultado_em", sa.DateTime(timezone=True), nullable=True),
        _date("identificado_em", nullable=False),
        _version(),
        _fk("risco", "projeto_id", "projeto"),
        _fk("risco", "categoria_id", "risco_categoria"),
        _fk("risco", "dono_id", "pessoa"),
        _fk("risco", "identificado_por_id", "pessoa"),
        _fk("risco", "responsavel_plano_id", "pessoa"),
        _fk("risco", "encerrado_por_id", "pessoa"),
        _fk("risco", "ocultado_por_id", "pessoa"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risco")),
        sa.UniqueConstraint("codigo", name=op.f("uq_risco_codigo")),
    )
    op.create_table(
        "risco_avaliacao",
        _id(),
        _bigint("risco_id", nullable=False),
        _bigint("autor_id", nullable=False),
        _text("tipo", nullable=False),
        _int("p", nullable=False),
        _int("i", nullable=False),
        _int("dim_prazo"),
        _int("dim_custo"),
        _int("dim_escopo"),
        _int("dim_sms"),
        _int("dim_imagem"),
        _int("dim_legal"),
        _date("data", nullable=False),
        _fk("risco_avaliacao", "risco_id", "risco"),
        _fk("risco_avaliacao", "autor_id", "pessoa"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risco_avaliacao")),
    )
    op.create_table(
        "risco_revisao",
        _id(),
        _bigint("risco_id", nullable=False),
        _bigint("autor_id", nullable=False),
        _date("data", nullable=False),
        _text("tipo", nullable=False),
        _text("situacao_apurada", nullable=False),
        _int("score_de"),
        _int("score_para", nullable=False),
        _int("p", nullable=False),
        _int("i", nullable=False),
        _flag("gatilho"),
        _text("texto"),
        _fk("risco_revisao", "risco_id", "risco"),
        _fk("risco_revisao", "autor_id", "pessoa"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risco_revisao")),
    )
    op.create_table(
        "risco_plano_aprovacao",
        _id(),
        _bigint("risco_id", nullable=False),
        _bigint("por_id"),
        _text("situacao", nullable=False),
        sa.Column("solicitada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decidida_em", sa.DateTime(timezone=True), nullable=True),
        _text("justificativa"),
        _fk("risco_plano_aprovacao", "risco_id", "risco"),
        _fk("risco_plano_aprovacao", "por_id", "pessoa"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risco_plano_aprovacao")),
    )


def downgrade() -> None:
    op.drop_table("risco_plano_aprovacao")
    op.drop_table("risco_revisao")
    op.drop_table("risco_avaliacao")
    op.drop_table("risco")
    op.drop_table("risco_categoria")
