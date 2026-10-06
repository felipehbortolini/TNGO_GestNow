"""Persistence models for the Central actions module.

Owns the action of any origin (and the annotation of the minutes, ``tipo = Informação``) and
its replans (D5). Class and attribute names are English (D1); tables and columns are
Portuguese snake_case (D5), as in ``docs/MODELO-DE-DADOS.md``. The status of an action is
not a column: it is calculated on every query (D6, ``calculations.action_status``).

``acao.ata_id`` is a plain column in this slice: the table ``ata`` and the foreign key arrive
with the minutes (ISSUE-021).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base

FALSE_SERVER_DEFAULT = text("false")


class Action(Base):
    """Ação de qualquer origem, ou anotação da ata (`Informação`); o status é calculado."""

    __tablename__ = "acao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    ata_id: Mapped[int | None] = mapped_column("ata_id", BigInteger)
    requester_id: Mapped[int] = mapped_column("solicitante_id", ForeignKey("pessoa.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    origin: Mapped[str] = mapped_column("origem", Text)
    origin_ref: Mapped[str | None] = mapped_column("origem_ref", Text)
    item: Mapped[str | None] = mapped_column("item", Text)
    group: Mapped[str | None] = mapped_column("grupo", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    contributes_probability: Mapped[bool] = mapped_column(
        "contribuicao_probabilidade", Boolean, server_default=FALSE_SERVER_DEFAULT
    )
    contributes_impact: Mapped[bool] = mapped_column(
        "contribuicao_impacto", Boolean, server_default=FALSE_SERVER_DEFAULT
    )
    subject: Mapped[str] = mapped_column("assunto", Text)
    description: Mapped[str | None] = mapped_column("descricao", Text)
    planned_date: Mapped[date | None] = mapped_column("data_prevista", Date)
    replanned_date: Mapped[date | None] = mapped_column("data_replanejada", Date)
    completed_on: Mapped[date | None] = mapped_column("data_conclusao", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ActionReplan(Base):
    """Cada replanejamento: data do registro, de, para, autor e justificativa; fato imutável."""

    __tablename__ = "acao_replanejamento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    action_id: Mapped[int] = mapped_column("acao_id", ForeignKey("acao.id"))
    author_id: Mapped[int] = mapped_column("autor_id", ForeignKey("pessoa.id"))
    registered_on: Mapped[date] = mapped_column("data", Date)
    from_date: Mapped[date] = mapped_column("de", Date)
    to_date: Mapped[date] = mapped_column("para", Date)
    justification: Mapped[str] = mapped_column("justificativa", Text)
