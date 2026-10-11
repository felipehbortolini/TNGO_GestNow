"""Persistence models for the Management reporting module.

Análise do período (ISSUE-081, D6): o texto executivo e analítico de um módulo num tipo
(Semanal ou Mensal) e período de um projeto, com o comentário de cada desvio negativo
detectado gravado pela chave do desvio. Um registro por projeto, módulo, tipo e período;
``projeto_id`` nulo identifica a análise do Portfólio (ISSUE-082). Class and attribute names
are English (D1); tables and columns are Portuguese snake_case (D5), matching
``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import VERSION_SERVER_DEFAULT, Base


class Analysis(Base):
    """Análise do período: o texto executivo de um módulo num tipo e período de um projeto."""

    __tablename__ = "analise_periodo"
    __table_args__ = (
        UniqueConstraint(
            "projeto_id",
            "modulo",
            "tipo",
            "periodo",
            postgresql_nulls_not_distinct=True,
            name="uq_analise_periodo_projeto_modulo_tipo_periodo",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    created_by_id: Mapped[int] = mapped_column("criado_por_id", ForeignKey("pessoa.id"))
    updated_by_id: Mapped[int] = mapped_column("atualizado_por_id", ForeignKey("pessoa.id"))
    module: Mapped[str] = mapped_column("modulo", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    period: Mapped[str] = mapped_column("periodo", Text)
    text: Mapped[str] = mapped_column("analise", Text)
    created_at: Mapped[datetime] = mapped_column(
        "criado_em", DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        "atualizado_em", DateTime(timezone=True), server_default=func.now()
    )
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    deviations: Mapped[list[AnalysisDeviation]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="AnalysisDeviation.id",
    )


class AnalysisDeviation(Base):
    """Comentário de um desvio negativo da análise: a chave, o indicador e o comentário.

    Sem ``versao`` própria: o comentário é protegido pela versão da análise, dona do agregado.
    """

    __tablename__ = "analise_periodo_desvio"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column("analise_id", ForeignKey("analise_periodo.id"))
    key: Mapped[str] = mapped_column("chave", Text)
    indicator: Mapped[str] = mapped_column("indicador", Text)
    comment: Mapped[str] = mapped_column("comentario", Text)

    analysis: Mapped[Analysis] = relationship(back_populates="deviations")
