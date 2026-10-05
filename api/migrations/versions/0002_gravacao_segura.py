"""gravacao segura

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05 16:20:00.000000

The audit trail is append-only for real: the trigger refuses UPDATE and
DELETE on ``auditoria`` at the database, so no route, facade or script
can rewrite history (D5b).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION = "tn_auditoria_somente_inclusao"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE FUNCTION {FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'A trilha de auditoria e somente de inclusao.';
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {FUNCTION}
        BEFORE UPDATE OR DELETE ON auditoria
        FOR EACH ROW EXECUTE FUNCTION {FUNCTION}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {FUNCTION} ON auditoria")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}()")
