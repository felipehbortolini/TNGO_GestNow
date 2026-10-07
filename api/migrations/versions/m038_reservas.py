"""Reservas de contingência e gerencial (ISSUE-041).

As duas tabelas da tela Contingência, como em ``docs/MODELO-DE-DADOS.md``: a reserva de cada
projeto e tipo, com a base de cálculo da constituição, e o extrato de movimentos (constituição,
consumo por SM aprovada ou liberação). O saldo não é coluna: é a soma dos movimentos (D5b).

Revision ID: m038
Revises: m037
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m038"
down_revision: str | None = "m037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the reserve of each project and type and its movement statement."""
    op.create_table(
        "reserva",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("base_calculo", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"], name=op.f("fk_reserva_projeto_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reserva")),
        sa.UniqueConstraint("projeto_id", "tipo", name=op.f("uq_reserva_projeto_id_tipo")),
    )
    op.create_table(
        "reserva_movimento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("reserva_id", sa.BigInteger(), nullable=False),
        sa.Column("mudanca_id", sa.BigInteger(), nullable=True),
        sa.Column("registrado_por_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mudanca_id"], ["mudanca.id"], name=op.f("fk_reserva_movimento_mudanca_id")
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por_id"],
            ["pessoa.id"],
            name=op.f("fk_reserva_movimento_registrado_por_id"),
        ),
        sa.ForeignKeyConstraint(
            ["reserva_id"], ["reserva.id"], name=op.f("fk_reserva_movimento_reserva_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reserva_movimento")),
    )


def downgrade() -> None:
    """Drop the movement statement and the reserve."""
    op.drop_table("reserva_movimento")
    op.drop_table("reserva")
