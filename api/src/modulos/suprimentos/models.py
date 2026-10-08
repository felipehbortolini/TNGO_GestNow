"""Persistence models of the Procurement module: suppliers and the purchase plan (ISSUE-057/058).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case (D5),
exactly as in ``docs/MODELO-DE-DADOS.md``. ``fornecedor`` is the qualification of a company of
the register (``empresa``), not of a project: the cadastro is global, as the companies and the
people of Configurações are. Documents in day, performance and contracted value are never
columns: they are calculated on every read (D6) from the documents, from the evaluations of the
Financeiro and from its facade.

``pacote_compra`` is the package of the plan: a project link, an item of level 3 of the EAC, a
buyer, a discipline, the scope and the data of the contracting strategy. The three layers of
each acquisition milestone (plan/LB, forecast and real) live in the same row of
``pacote_compra_marco`` (ISSUE-004 decision); the history travels in the audit trail. Stage,
slack and adjudicated are never columns: they are calculated on every read from the milestones and
from the registros of the process (ISSUE-059) and of the order (ISSUE-061).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base
from src.core.money import Centavos


class Supplier(Base):
    """Qualificação de uma empresa do cadastro: situação, validade e observação (UK: empresa)."""

    __tablename__ = "fornecedor"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"), unique=True)
    situation: Mapped[str] = mapped_column("situacao", Text)
    validity: Mapped[date | None] = mapped_column("validade_qualificacao", Date)
    observation: Mapped[str | None] = mapped_column("observacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class SupplierCategory(Base):
    """Categoria de atuação da empresa qualificada. Sem ``versao`` própria."""

    __tablename__ = "fornecedor_categoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column("fornecedor_id", ForeignKey("fornecedor.id"))
    category: Mapped[str] = mapped_column("categoria", Text)


class SupplierDocument(Base):
    """Documento com validade do fornecedor; o arquivo é um ``anexo`` (D5a)."""

    __tablename__ = "fornecedor_documento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column("fornecedor_id", ForeignKey("fornecedor.id"))
    name: Mapped[str] = mapped_column("nome", Text)
    validity: Mapped[date | None] = mapped_column("validade", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class SupplierHistory(Base):
    """Mudança de situação da qualificação (de, para, autor e justificativa). Fato imutável."""

    __tablename__ = "fornecedor_historico"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column("fornecedor_id", ForeignKey("fornecedor.id"))
    by_id: Mapped[int] = mapped_column("por_id", ForeignKey("pessoa.id"))
    on: Mapped[date] = mapped_column("data", Date)
    from_situation: Mapped[str | None] = mapped_column("de", Text)
    to_situation: Mapped[str] = mapped_column("para", Text)
    justification: Mapped[str] = mapped_column("justificativa", Text)


class PurchasePackage(Base):
    """Pacote do plano de compras, ligado a um item da EAC do projeto (UK: projeto + código).

    O comprador vem do cadastro de pessoas e a disciplina do cadastro de disciplinas
    (Configurações). A LB fica congelada a partir da requisição com data real; depois disso só
    escopo, comprador, estimativa e ROS mudam, com justificativa na trilha.
    """

    __tablename__ = "pacote_compra"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    eac_item_id: Mapped[int] = mapped_column("eac_item_id", ForeignKey("eac_item.id"))
    buyer_id: Mapped[int] = mapped_column("comprador_id", ForeignKey("pessoa.id"))
    discipline_id: Mapped[int | None] = mapped_column("disciplina_id", ForeignKey("disciplina.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    scope: Mapped[str] = mapped_column("escopo", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    modality: Mapped[str] = mapped_column("modalidade", Text)
    lli: Mapped[bool] = mapped_column("lli", Boolean)
    estimate_cents: Mapped[int] = mapped_column("estimativa_centavos", Centavos)
    ros: Mapped[date] = mapped_column("ros", Date)
    emergency: Mapped[bool] = mapped_column("emergencial", Boolean)
    gate_lli_date: Mapped[date | None] = mapped_column("gate_lli_data", Date)
    gate_lli_reference: Mapped[str | None] = mapped_column("gate_lli_referencia", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)


class PackageMilestone(Base):
    """Marco de aquisição do pacote com as três camadas na mesma linha (UK: pacote + marco).

    ``data_plano`` é a LB congelada, ``data_previsao`` a previsão e ``data_real`` o realizado;
    cada mudança passa por ``core.recording``, com o antes/depois na trilha (ISSUE-004).
    """

    __tablename__ = "pacote_compra_marco"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column("pacote_id", ForeignKey("pacote_compra.id"))
    milestone: Mapped[str] = mapped_column("marco", Text)
    plan_date: Mapped[date | None] = mapped_column("data_plano", Date)
    forecast_date: Mapped[date | None] = mapped_column("data_previsao", Date)
    real_date: Mapped[date | None] = mapped_column("data_real", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    __table_args__ = (UniqueConstraint("pacote_id", "marco"),)
