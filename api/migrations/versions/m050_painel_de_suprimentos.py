"""Painel de suprimentos: os agregados do processo no pacote (ISSUE-063).

O painel lê o resultado comercial do pacote para os indicadores de saving de negociação e de
competitividade. O processo vivo (ISSUE-059/060) é a fonte; estas três colunas guardam o resumo
que a carga histórica do protótipo trazia no pacote (``primeiraPropostaCentavos``,
``propostasValidas`` e ``fornecedorUnico``): a fachada prefere o processo quando existe e cai na
coluna para os pacotes antigos. Adjudicado, saving e avanço continuam calculados (D6).

Revision ID: m050
Revises: m049
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m050"
down_revision: str | None = "m049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the commercial outcome columns of the package."""
    op.add_column(
        "pacote_compra", sa.Column("primeira_proposta_centavos", sa.BigInteger(), nullable=True)
    )
    op.add_column("pacote_compra", sa.Column("propostas_validas", sa.Integer(), nullable=True))
    op.add_column("pacote_compra", sa.Column("fornecedor_unico", sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Drop the commercial outcome columns."""
    op.drop_column("pacote_compra", "fornecedor_unico")
    op.drop_column("pacote_compra", "propostas_validas")
    op.drop_column("pacote_compra", "primeira_proposta_centavos")
