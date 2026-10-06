"""Persistence models for the Central actions module.

Owns the action of any origin (and the annotation of the minutes, ``tipo = Informação``) and
its replans (D5). Class and attribute names are English (D1); tables and columns are
Portuguese snake_case (D5), as in ``docs/MODELO-DE-DADOS.md``. The status of an action is
not a column: it is calculated on every query (D6, ``calculations.action_status``).

The minutes (``ata``, ``ata_empresa``, ``ata_participante``) arrived with ISSUE-021, which also
turned ``acao.ata_id`` into a foreign key. A revision is a row of its own: the lineage is the
``numero``, and the revisions of one number are ordered by ``revisao``.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base

FALSE_SERVER_DEFAULT = text("false")


class Action(Base):
    """Ação de qualquer origem, ou anotação da ata (`Informação`); o status é calculado."""

    __tablename__ = "acao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    ata_id: Mapped[int | None] = mapped_column("ata_id", ForeignKey("ata.id"))
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


class Minutes(Base):
    """Cabeçalho de uma revisão de ata; a linhagem é o `numero` e as revisões se ordenam por `revisao`."""

    __tablename__ = "ata"
    __table_args__ = (UniqueConstraint("projeto_id", "numero", "revisao"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    unit_id: Mapped[int | None] = mapped_column("unidade_id", ForeignKey("unidade.id"))
    prepared_by_id: Mapped[int] = mapped_column("elaborado_por_id", ForeignKey("pessoa.id"))
    main_company_id: Mapped[int | None] = mapped_column(
        "empresa_principal_id", ForeignKey("empresa.id")
    )
    number: Mapped[str] = mapped_column("numero", Text)
    revision: Mapped[int] = mapped_column("revisao", Integer)
    meeting_date: Mapped[date] = mapped_column("data", Date)
    meeting_type: Mapped[str] = mapped_column("tipo_reuniao", Text)
    board: Mapped[str] = mapped_column("diretoria", Text)
    subject: Mapped[str] = mapped_column("assunto", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class MinutesCompany(Base):
    """Empresa executora convocada para a ata; protegida pela versão da ata."""

    __tablename__ = "ata_empresa"
    __table_args__ = (UniqueConstraint("ata_id", "empresa_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    minutes_id: Mapped[int] = mapped_column("ata_id", ForeignKey("ata.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))


class MinutesParticipant(Base):
    """Pessoa da lista de presença da ata; protegida pela versão da ata."""

    __tablename__ = "ata_participante"
    __table_args__ = (UniqueConstraint("ata_id", "pessoa_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    minutes_id: Mapped[int] = mapped_column("ata_id", ForeignKey("ata.id"))
    person_id: Mapped[int] = mapped_column("pessoa_id", ForeignKey("pessoa.id"))
