"""Persistence models of the Financeiro module (D5).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case,
as in ``docs/MODELO-DE-DADOS.md``. This slice (ISSUE-029) owns the cost breakdown item; the
revisions, the transfers and the projections of the item arrive with ISSUE-030.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base
from src.core.money import Centavos


class EacItem(Base):
    """Item of the Estrutura Analítica de Custos, in three levels (package, subpackage, item).

    No aggregated value is a column (D5b): the budgeted value of an item is its quantity times
    its unit price, and the totals of the packages are sums made by the facade.
    """

    __tablename__ = "eac_item"
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    parent_id: Mapped[int | None] = mapped_column("pai_id", ForeignKey("eac_item.id"))
    unit_id: Mapped[int | None] = mapped_column("unidade_id", ForeignKey("unidade.id"))
    responsible_id: Mapped[int | None] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    level: Mapped[int] = mapped_column("nivel", Integer)
    cost_type: Mapped[str | None] = mapped_column("tipo_custo", Text)
    quantity: Mapped[Decimal | None] = mapped_column("quantidade", Numeric(18, 4))
    unit_price_cents: Mapped[int | None] = mapped_column("preco_unitario_centavos", Centavos)
    capex: Mapped[bool | None] = mapped_column("capex", Boolean)
    cost_center: Mapped[str | None] = mapped_column("centro_custo", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)
