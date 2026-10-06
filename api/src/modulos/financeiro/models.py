"""Persistence models of the Financeiro module (D5).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case,
as in ``docs/MODELO-DE-DADOS.md``. This module owns the cost breakdown item, its revisions with
the frozen baseline of each item, the reallocations applied to it (ISSUE-029, ISSUE-030), the
projection history of the item and the costs imported from the ERP (ISSUE-031).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
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


class EacRevision(Base):
    """Revisão da EAC: Rev 0 é a linha de base; a revisão seguinte consolida remanejamentos e SM.

    O total não é coluna: é a soma das linhas de ``eac_revisao_item`` da revisão (D5b). A SM de
    origem é opcional no banco para a carga e para a linha de base, que nasce sem mudança.
    """

    __tablename__ = "eac_revisao"
    __table_args__ = (UniqueConstraint("projeto_id", "revisao"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    approved_by_id: Mapped[int] = mapped_column("aprovado_por_id", ForeignKey("pessoa.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    revision_date: Mapped[date] = mapped_column("data", Date)
    justification: Mapped[str] = mapped_column("justificativa", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class EacRevisionItem(Base):
    """Linha de base congelada de um item em uma revisão, em centavos.

    Fato histórico por definição (D5b): é o que permite comparar revisões depois. Sem ``versao``.
    """

    __tablename__ = "eac_revisao_item"
    __table_args__ = (UniqueConstraint("revisao_id", "item_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column("revisao_id", ForeignKey("eac_revisao.id"))
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eac_item.id"))
    base_cents: Mapped[int] = mapped_column("base_centavos", Centavos)


class EacReallocation(Base):
    """Remanejamento aplicado na EAC: origem, destino, valor, autor, SM e a revisão que consolida.

    A linha nasce na aprovação da SM (ISSUE-030); enquanto ela não é consolidada por uma revisão,
    ``revisao`` aponta para a próxima revisão (a que a consolidará). Fato imutável, sem ``versao``.
    """

    __tablename__ = "eac_remanejamento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    source_item_id: Mapped[int] = mapped_column("origem_item_id", ForeignKey("eac_item.id"))
    target_item_id: Mapped[int] = mapped_column("destino_item_id", ForeignKey("eac_item.id"))
    applied_by_id: Mapped[int] = mapped_column("por_id", ForeignKey("pessoa.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    applied_on: Mapped[date] = mapped_column("data", Date)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    new_item: Mapped[bool] = mapped_column("novo_item", Boolean, server_default=text("false"))
    justification: Mapped[str | None] = mapped_column("justificativa", Text)


class EacProjection(Base):
    """Projeção no término de um item, com a justificativa e quem a informou (ISSUE-031).

    A projeção vigente é a última linha do item; ``origem`` diz se ela veio do responsável ou do
    fechamento do ERP. Fato histórico por definição (D5b): sem ``versao``.
    """

    __tablename__ = "eac_projecao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eac_item.id"))
    author_id: Mapped[int] = mapped_column("autor_id", ForeignKey("pessoa.id"))
    projected_on: Mapped[date] = mapped_column("data", Date)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    origin: Mapped[str] = mapped_column("origem", Text)
    justification: Mapped[str] = mapped_column("justificativa", Text)


class ErpCost(Base):
    """Custos do ERP de um item em um mês: comprometido, realizado e projeção do fechamento.

    Fato mensal por item e mês (ISSUE-031), sem ``versao``; alimenta o mapa de controle e a
    Curva S financeira. Um mês reimportado atualiza a linha, nunca a duplica.
    """

    __tablename__ = "custo_erp"
    __table_args__ = (UniqueConstraint("item_id", "mes"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eac_item.id"))
    imported_by_id: Mapped[int] = mapped_column("importado_por_id", ForeignKey("pessoa.id"))
    month: Mapped[date] = mapped_column("mes", Date)
    committed_cents: Mapped[int | None] = mapped_column("comprometido_centavos", Centavos)
    actual_cents: Mapped[int | None] = mapped_column("realizado_centavos", Centavos)
    projection_cents: Mapped[int | None] = mapped_column("projecao_centavos", Centavos)
    imported_at: Mapped[datetime] = mapped_column(
        "importado_em", DateTime(timezone=True), server_default=func.now()
    )
