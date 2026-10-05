"""Persistence models of the Configurações module.

Owns the project register and the support registers consumed by every module
(D5): empresa, pessoa, colaborador e papéis, parâmetros versionados, sistemas,
unidades, locais, disciplinas e catálogos. Class and attribute names are
English (D1); tables and columns are Portuguese snake_case (D5), matching
``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core import models as plataforma
from src.core.database import ACTIVE_SERVER_DEFAULT, VERSION_SERVER_DEFAULT, Base


class Project(Base):
    """Cadastro do projeto: código, nome, PEP, padrões, gerente, datas e orçamento."""

    __tablename__ = "projeto"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column("cliente_id", ForeignKey("cliente.id"))
    manager_id: Mapped[int] = mapped_column("gerente_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text, unique=True)
    name: Mapped[str] = mapped_column("nome", Text)
    pep: Mapped[str | None] = mapped_column("pep", Text)
    ata_pattern: Mapped[str | None] = mapped_column("padrao_ata", Text)
    risk_pattern: Mapped[str | None] = mapped_column("padrao_risco", Text)
    punch_pattern: Mapped[str | None] = mapped_column("padrao_punch", Text)
    risk_appetite: Mapped[str | None] = mapped_column("apetite_risco", Text)
    start_date: Mapped[date | None] = mapped_column("inicio", Date)
    expected_end_date: Mapped[date | None] = mapped_column("termino_previsto", Date)
    budget_cents: Mapped[int | None] = mapped_column("orcamento_centavos", BigInteger)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Company(Base):
    """Empresa contratada, fornecedor ou gerenciadora (nome e tipo)."""

    __tablename__ = "empresa"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nome", Text)
    kind: Mapped[str | None] = mapped_column("tipo", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Person(Base):
    """Pessoa do cadastro (nome, função, empresa e e-mail único de acesso)."""

    __tablename__ = "pessoa"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    name: Mapped[str] = mapped_column("nome", Text)
    role: Mapped[str | None] = mapped_column("funcao", Text)
    email: Mapped[str] = mapped_column("email", Text, unique=True)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Collaborator(Base):
    """Pessoa com acesso: perfil geral, vínculo e empresa (D7)."""

    __tablename__ = "colaborador"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column("pessoa_id", ForeignKey("pessoa.id"), unique=True)
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    general_profile: Mapped[str] = mapped_column("perfil_geral", Text)
    bond: Mapped[str] = mapped_column("vinculo", Text)
    active: Mapped[bool] = mapped_column("ativo", Boolean, server_default=ACTIVE_SERVER_DEFAULT)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class CollaboratorScheduleRole(Base):
    """Papel do colaborador na Programação Semanal, por projeto."""

    __tablename__ = "colaborador_papel_programacao"
    __table_args__ = (UniqueConstraint("colaborador_id", "projeto_id", "papel"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    collaborator_id: Mapped[int] = mapped_column("colaborador_id", ForeignKey("colaborador.id"))
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    role: Mapped[str] = mapped_column("papel", Text)


class ParameterVersion(Base):
    """Versão de um grupo de parâmetros; nada é editado, cada gravação cria uma versão."""

    __tablename__ = "parametro_versao"
    __table_args__ = (UniqueConstraint("grupo", "versao"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column("autor_id", ForeignKey("colaborador.id"))
    group: Mapped[str] = mapped_column("grupo", Text)
    version: Mapped[int] = mapped_column("versao", Integer)
    effective_from: Mapped[date] = mapped_column("vigencia_inicio", Date)
    justification: Mapped[str] = mapped_column("justificativa", Text)
    created_at: Mapped[datetime] = mapped_column(
        "criado_em", DateTime(timezone=True), server_default=func.now()
    )


class ParameterValue(Base):
    """Valor de um parâmetro na versão, em linha tipada (inclui listas por ordem)."""

    __tablename__ = "parametro_valor"
    __table_args__ = (UniqueConstraint("versao_id", "chave", "ordem"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column("versao_id", ForeignKey("parametro_versao.id"))
    key: Mapped[str] = mapped_column("chave", Text)
    order: Mapped[int] = mapped_column("ordem", Integer)
    value_type: Mapped[str] = mapped_column("tipo", Text)
    value: Mapped[str] = mapped_column("valor", Text)


class PortfolioWeight(Base):
    """Nota de 1 a 5 de cada projeto por critério da carteira, dentro da versão do grupo."""

    __tablename__ = "portfolio_ponderacao"
    __table_args__ = (UniqueConstraint("versao_id", "projeto_id", "criterio"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column("versao_id", ForeignKey("parametro_versao.id"))
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    criterion: Mapped[str] = mapped_column("criterio", Text)
    grade: Mapped[int] = mapped_column("nota", Integer)


class System(Base):
    """Cadastro de apoio de sistemas do projeto (usado pelo punch list)."""

    __tablename__ = "sistema"
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    name: Mapped[str] = mapped_column("nome", Text)
    area: Mapped[str | None] = mapped_column("area", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Unit(Base):
    """Cadastro de apoio de unidades: de medida ou organizacional, por tipo."""

    __tablename__ = "unidade"
    __table_args__ = (UniqueConstraint("tipo", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column("tipo", Text)
    code: Mapped[str] = mapped_column("codigo", Text)
    name: Mapped[str] = mapped_column("nome", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Location(Base):
    """Cadastro de apoio de locais do projeto (código e nome)."""

    __tablename__ = "local"
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    name: Mapped[str] = mapped_column("nome", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Discipline(Base):
    """Cadastro de apoio de disciplinas (Civil, Mecânica, Tubulação e afins)."""

    __tablename__ = "disciplina"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nome", Text, unique=True)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Catalog(Base):
    """Cadastro de apoio dos catálogos genéricos, por grupo."""

    __tablename__ = "catalogo"
    __table_args__ = (UniqueConstraint("grupo", "nome"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group: Mapped[str] = mapped_column("grupo", Text)
    name: Mapped[str] = mapped_column("nome", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class CatalogItem(Base):
    """Itens de cada catálogo (chave, valor, ordem e ativo)."""

    __tablename__ = "catalogo_item"
    __table_args__ = (UniqueConstraint("catalogo_id", "chave"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    catalog_id: Mapped[int] = mapped_column("catalogo_id", ForeignKey("catalogo.id"))
    key: Mapped[str] = mapped_column("chave", Text)
    value: Mapped[str] = mapped_column("valor", Text)
    order: Mapped[int] = mapped_column("ordem", Integer)
    active: Mapped[bool] = mapped_column("ativo", Boolean, server_default=ACTIVE_SERVER_DEFAULT)


# The platform import above keeps the cross-module foreign keys
# (cliente.id, projeto.id, colaborador.id) resolvable whenever this module is
# imported; SQLAlchemy resolves string targets at mapper configuration time.
_ = plataforma.Client
