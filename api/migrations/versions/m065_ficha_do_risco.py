"""ficha do risco

Revision ID: m065
Revises: m050
Create Date: 2026-10-09 12:00:00.000000

The links the risk record already had as plain columns become real foreign keys, as drawn in
``docs/MODELO-DE-DADOS.md`` (section "05 Riscos"): the minutes of the origin, the change request
of the strategy Evitar (``mudanca_id``), the change request of the materialized closing
(``encerramento_mudanca_id``) and the lesson of the closing (``licao_id``). The tables are owned
by Central de Ações (``ata``) and Governança (``mudanca``, ``licao``); ISSUE-065 is the slice
that writes those links, so the constraints arrive here. No column changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m065"
down_revision: str | None = "m050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LINKS = (
    ("ata_id", "ata"),
    ("mudanca_id", "mudanca"),
    ("licao_id", "licao"),
    ("encerramento_mudanca_id", "mudanca"),
)


def _name(column: str) -> str:
    return op.f(f"fk_risco_{column}")


def upgrade() -> None:
    for column, target in LINKS:
        op.create_foreign_key(_name(column), "risco", target, [column], ["id"])


def downgrade() -> None:
    for column, _target in LINKS:
        op.drop_constraint(_name(column), "risco", type_="foreignkey")
