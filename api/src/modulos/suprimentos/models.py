"""Persistence models of the Procurement module: supplier qualification (ISSUE-057).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case (D5),
exactly as in ``docs/MODELO-DE-DADOS.md``. ``fornecedor`` is the qualification of a company of
the register (``empresa``), not of a project: the cadastro is global, as the companies and the
people of Configurações are. Documents in day, performance and contracted value are never
columns: they are calculated on every read (D6) from the documents, from the evaluations of the
Financeiro and from its facade.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base


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
