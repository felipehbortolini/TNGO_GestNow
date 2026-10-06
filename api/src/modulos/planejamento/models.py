"""Persistence models for the Planning module.

The 6WLA (ISSUE-045): the activities of the six-week horizon, the mark of each
week and the restrictions that hold an activity back. Class and attribute names
are English (D1); tables and columns are Portuguese snake_case (D5), matching
``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base


class Lookahead(Base):
    """Atividade do 6WLA: código, atividade, área, disciplina, empresa e responsável."""

    __tablename__ = "lookahead"
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    owner_id: Mapped[int | None] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    activity: Mapped[str] = mapped_column("atividade", Text)
    area: Mapped[str] = mapped_column("area", Text)
    discipline: Mapped[str] = mapped_column("disciplina", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class LookaheadWeek(Base):
    """Marcação de uma das seis semanas do horizonte; protegida pela versão da atividade."""

    __tablename__ = "lookahead_semana"
    __table_args__ = (UniqueConstraint("lookahead_id", "indice"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lookahead_id: Mapped[int] = mapped_column("lookahead_id", ForeignKey("lookahead.id"))
    index: Mapped[int] = mapped_column("indice", Integer)
    planned: Mapped[bool] = mapped_column("prevista", Boolean)


class LookaheadConstraint(Base):
    """Restrição da atividade: tipo, descrição, responsável, data necessária e remoção."""

    __tablename__ = "lookahead_restricao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lookahead_id: Mapped[int] = mapped_column("lookahead_id", ForeignKey("lookahead.id"))
    owner_id: Mapped[int | None] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    order: Mapped[int] = mapped_column("ordem", Integer)
    kind: Mapped[str] = mapped_column("tipo", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    due_date: Mapped[date] = mapped_column("necessaria", Date)
    removal_date: Mapped[date | None] = mapped_column("remocao", Date)
    removal_comment: Mapped[str | None] = mapped_column("comentario_remocao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)
