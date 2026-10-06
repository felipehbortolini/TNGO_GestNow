"""Persistence models for the HSE module: the monthly hours, the proactive records (ISSUE-072).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case (D5),
as in ``docs/MODELO-DE-DADOS.md``. A month is stored as the first day of the month. The
occurrence tables arrive with ISSUE-073; the risk analysis tables are ISSUE-074.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base


class WorkedHours(Base):
    """HHT e efetivo médio de um mês e de uma empresa; um registro por mês e empresa."""

    __tablename__ = "hht"
    __table_args__ = (UniqueConstraint("projeto_id", "mes", "empresa_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    month: Mapped[date] = mapped_column("mes", Date)
    average_headcount: Mapped[int] = mapped_column("efetivo_medio", Integer)
    hours: Mapped[Decimal] = mapped_column("hht", Numeric(14, 2))
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class MonthlyClosing(Base):
    """Fechamento mensal da segurança proativa, um por mês: desvios, observações, DDS e itens."""

    __tablename__ = "hse_mensal"
    __table_args__ = (UniqueConstraint("projeto_id", "mes"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    month: Mapped[date] = mapped_column("mes", Date)
    deviations: Mapped[int] = mapped_column("desvios", Integer)
    observations: Mapped[int] = mapped_column("observacoes", Integer)
    planned_dds: Mapped[int] = mapped_column("dds_programados", Integer)
    held_dds: Mapped[int] = mapped_column("dds_realizados", Integer)
    inspected_items: Mapped[int] = mapped_column("itens_inspecionados", Integer)
    conforming_items: Mapped[int] = mapped_column("itens_conformes", Integer)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class SafetyInspection(Base):
    """Inspeção de segurança por checklist: data, área, empresa e responsável."""

    __tablename__ = "hse_inspecao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    inspected_on: Mapped[date] = mapped_column("data", Date)
    area: Mapped[str] = mapped_column("area", Text)
    note: Mapped[str | None] = mapped_column("observacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class SafetyInspectionItem(Base):
    """Item do checklist; sem versão própria, entra e sai com a inspeção."""

    __tablename__ = "hse_inspecao_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column("inspecao_id", ForeignKey("hse_inspecao.id"))
    position: Mapped[int] = mapped_column("ordem", Integer)
    description: Mapped[str] = mapped_column("descricao", Text)
    conforming: Mapped[bool] = mapped_column("conforme", Boolean)
    note: Mapped[str | None] = mapped_column("observacao", Text)


class BehaviorObservation(Base):
    """Observação comportamental: data, área, empresa, tipo, descrição e situação."""

    __tablename__ = "hse_observacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    observed_id: Mapped[int | None] = mapped_column("observado_id", ForeignKey("pessoa.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    observed_on: Mapped[date] = mapped_column("data", Date)
    area: Mapped[str] = mapped_column("area", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    status: Mapped[str] = mapped_column("situacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class SafetyTalk(Base):
    """DDS (diálogo diário de segurança): data, tema, responsável e número de participantes."""

    __tablename__ = "hse_dds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    held_on: Mapped[date] = mapped_column("data", Date)
    topic: Mapped[str] = mapped_column("tema", Text)
    participants: Mapped[int] = mapped_column("participantes", Integer)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class RiskAnalysis(Base):
    """Estudo de risco (APR/JSA ou HAZOP): código único, tipo, área, título e data."""

    __tablename__ = "analise_risco"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    code: Mapped[str] = mapped_column("codigo", Text, unique=True)
    kind: Mapped[str] = mapped_column("tipo", Text)
    area: Mapped[str] = mapped_column("area", Text)
    title: Mapped[str] = mapped_column("titulo", Text)
    studied_on: Mapped[date] = mapped_column("data", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class RiskAnalysisParticipant(Base):
    """Participante do estudo; sem versão própria, entra e sai com o estudo."""

    __tablename__ = "analise_risco_participante"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column("analise_id", ForeignKey("analise_risco.id"))
    person_id: Mapped[int] = mapped_column("pessoa_id", ForeignKey("pessoa.id"))


class RiskRecommendation(Base):
    """Recomendação do estudo: responsável, prazo e situação (Aberta ou Fechada)."""

    __tablename__ = "analise_risco_recomendacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column("analise_id", ForeignKey("analise_risco.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    position: Mapped[int] = mapped_column("ordem", Integer)
    description: Mapped[str] = mapped_column("descricao", Text)
    due_date: Mapped[date] = mapped_column("prazo", Date)
    status: Mapped[str] = mapped_column("situacao", Text)
    closed_on: Mapped[date | None] = mapped_column("concluida_em", Date)
    evidence: Mapped[str | None] = mapped_column("evidencia", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)
