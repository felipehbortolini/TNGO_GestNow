"""Decisão da mudança: o vínculo com a ata do comitê e a data de reapresentação (ISSUE-025).

O modelo aceito de ``mudanca_decisao`` não tinha como guardar a ata opcional do comitê (Central)
nem o "reapresentar em" da decisão adiada; a ficha do protótipo mostra os dois. As duas colunas
entram aqui, com a chave estrangeira para ``ata``, que já existe (ISSUE-021).

Revision ID: m025
Revises: m072
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "m025"
down_revision: str | None = "m072"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add the committee minutes and the reappearance date to the decision."""
    op.add_column("mudanca_decisao", sa.Column("ata_id", sa.BigInteger(), nullable=True))
    op.add_column("mudanca_decisao", sa.Column("reapresentar_em", sa.Date(), nullable=True))
    op.create_foreign_key(
        op.f("fk_mudanca_decisao_ata_id"),
        "mudanca_decisao",
        "ata",
        ["ata_id"],
        ["id"],
    )


def downgrade() -> None:
    """Take the two columns out, in the reverse order."""
    op.drop_constraint(op.f("fk_mudanca_decisao_ata_id"), "mudanca_decisao", type_="foreignkey")
    op.drop_column("mudanca_decisao", "reapresentar_em")
    op.drop_column("mudanca_decisao", "ata_id")
