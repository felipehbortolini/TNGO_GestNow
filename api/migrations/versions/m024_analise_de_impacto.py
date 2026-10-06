"""analise de impacto

Revision ID: m024
Revises: 0003
Create Date: 2026-10-06 11:00:00.000000

The release of a reserve asked by an SM of the type "Liberação de reserva" (ISSUE-024): which reserve
and how much, kept with the impact analysis that proposes it. The cost of such an SM is zero, so the
amount to release cannot live in ``custo_centavos``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m024"
down_revision: str | None = "m051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mudanca_impacto", sa.Column("liberacao_reserva", sa.Text(), nullable=True))
    op.add_column(
        "mudanca_impacto", sa.Column("liberacao_valor_centavos", sa.BigInteger(), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_mudanca_impacto_liberacao_reserva"),
        "mudanca_impacto",
        "liberacao_reserva IS NULL OR liberacao_reserva IN ('Contingência', 'Gerencial')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_mudanca_impacto_liberacao_reserva"), "mudanca_impacto", type_="check"
    )
    op.drop_column("mudanca_impacto", "liberacao_valor_centavos")
    op.drop_column("mudanca_impacto", "liberacao_reserva")
