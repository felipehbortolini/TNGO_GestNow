"""integrações que chegam aos riscos

Revision ID: m067
Revises: m065
Create Date: 2026-10-09 18:00:00.000000

The last foreign key of the "Ligações entre módulos" table of ``docs/MODELO-DE-DADOS.md`` that
was still a plain column becomes real: ``licao_aplicacao.risco_id``, the risk that "Aplicar em
projeto" creates through the facade of Riscos (ISSUE-067). The table belongs to Governança and
the target to Riscos; the slice that writes the link is this one, so the constraint arrives
here. ``contrato_claim.risco_id`` and ``contrato.pacote_compra_id`` were already closed. No
column changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m067"
down_revision: str | None = "m065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMN = "risco_id"
TABLE = "licao_aplicacao"
TARGET = "risco"


def _name() -> str:
    return op.f(f"fk_{TABLE}_{COLUMN}")


def upgrade() -> None:
    op.create_foreign_key(_name(), TABLE, TARGET, [COLUMN], ["id"])


def downgrade() -> None:
    op.drop_constraint(_name(), TABLE, type_="foreignkey")
