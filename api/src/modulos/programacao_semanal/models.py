"""Persistence models of the Weekly Scheduling module (D10, D5).

The tables of the app ``Timenow - Programação Semanal`` as the data model states
them (``docs/MODELO-DE-DADOS.md``, section 8): the configuration of the project, the
activity with its seven days, the change requests and the window of each company
with its weekdays, released weeks and extraordinary releases. Class and attribute
names are English (D1); tables and columns are Portuguese snake_case (D5).

The totals, the PPC, the band and the adherence are never stored: they are computed
(``calculations``). The people an activity points to (inspector, foreman, authors)
are ``pessoa`` rows: the register of Configurações, never a copy of a name. The
activity keeps ``project_id`` under that attribute name because the audit trail
reads it to tag the line with the project (``core.audit``).
"""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ACTIVE_SERVER_DEFAULT, VERSION_SERVER_DEFAULT, Base

# Quantities of production and percentages are read back as plain floats: the app
# computed with floats and rounds to two decimals, and so does ``calculations``.
Quantity = Numeric(14, 2, asdecimal=False)
Percent = Numeric(7, 2, asdecimal=False)


class ScheduleSettings(Base):
    """Configuração da programação do projeto (uma linha por projeto, D10)."""

    __tablename__ = "programacao_configuracao"
    __table_args__ = (UniqueConstraint("projeto_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    adherence_target: Mapped[float] = mapped_column("meta_aderencia", Percent)
    ppc_target: Mapped[float] = mapped_column("meta_ppc", Percent)
    reference_week: Mapped[str | None] = mapped_column("semana_referencia", Text)
    requires_deviation_note: Mapped[bool] = mapped_column(
        "exige_justificativa_desvio", Boolean, server_default=ACTIVE_SERVER_DEFAULT
    )
    deviation_limit: Mapped[float] = mapped_column("limite_desvio_justificativa", Percent)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Activity(Base):
    """Atividade da semana: a linha da matriz (semana ISO ``S.30/2026``, ID exclusiva e item)."""

    __tablename__ = "programacao_atividade"
    __table_args__ = (UniqueConstraint("projeto_id", "semana", "id_exclusiva"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    location_id: Mapped[int | None] = mapped_column("local_id", ForeignKey("local.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    unit_id: Mapped[int | None] = mapped_column("unidade_id", ForeignKey("unidade.id"))
    inspector_id: Mapped[int | None] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    foreman_id: Mapped[int | None] = mapped_column("encarregado_id", ForeignKey("pessoa.id"))
    created_by_id: Mapped[int] = mapped_column("criado_por_id", ForeignKey("pessoa.id"))
    updated_by_id: Mapped[int] = mapped_column("atualizado_por_id", ForeignKey("pessoa.id"))
    approved_by_id: Mapped[int | None] = mapped_column("aprovado_por_id", ForeignKey("pessoa.id"))
    week: Mapped[str] = mapped_column("semana", Text)
    unique_id: Mapped[str] = mapped_column("id_exclusiva", Text)
    item: Mapped[int] = mapped_column("item", Integer)
    description: Mapped[str] = mapped_column("atividade", Text)
    planned_headline: Mapped[float] = mapped_column("prod_prevista", Quantity)
    situation: Mapped[str] = mapped_column("situacao", Text)
    approval: Mapped[str] = mapped_column("aprovacao_realizado", Text)
    supplier_notes: Mapped[str | None] = mapped_column("observacoes_fornecedor", Text)
    timenow_comments: Mapped[str | None] = mapped_column("comentarios_timenow", Text)
    created_at: Mapped[datetime] = mapped_column("criado_em", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("atualizado_em", DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column("aprovado_em", DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column("publicado_em", DateTime(timezone=True))
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ActivityDay(Base):
    """Previsto e realizado de um dia da atividade (1 segunda a 7 domingo); sem versão própria."""

    __tablename__ = "programacao_dia"
    __table_args__ = (UniqueConstraint("atividade_id", "dia"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column("atividade_id", ForeignKey("programacao_atividade.id"))
    day: Mapped[int] = mapped_column("dia", Integer)
    planned: Mapped[float] = mapped_column("previsto", Quantity, server_default=text("0"))
    done_day_shift: Mapped[float] = mapped_column(
        "realizado_dia", Quantity, server_default=text("0")
    )
    done_night_shift: Mapped[float] = mapped_column(
        "realizado_noite", Quantity, server_default=text("0")
    )


class ChangeRequest(Base):
    """Pedido de alteração de uma atividade (motivo, situação, solicitante e decisão)."""

    __tablename__ = "programacao_pedido_alteracao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column("atividade_id", ForeignKey("programacao_atividade.id"))
    requested_by_id: Mapped[int] = mapped_column("solicitado_por_id", ForeignKey("pessoa.id"))
    decided_by_id: Mapped[int | None] = mapped_column("decidido_por_id", ForeignKey("pessoa.id"))
    reason: Mapped[str] = mapped_column("motivo", Text)
    situation: Mapped[str] = mapped_column("situacao", Text)
    requested_at: Mapped[datetime] = mapped_column("solicitado_em", DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column("decidido_em", DateTime(timezone=True))
    answer: Mapped[str | None] = mapped_column("resposta", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ScheduleWindow(Base):
    """Janela de programação de uma empresa num projeto (D10)."""

    __tablename__ = "programacao_janela"
    __table_args__ = (UniqueConstraint("projeto_id", "empresa_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class WindowWeekday(Base):
    """Dia da semana (1 segunda a 7 domingo) e horário em que a janela regular abre."""

    __tablename__ = "programacao_janela_dia"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    window_id: Mapped[int] = mapped_column("janela_id", ForeignKey("programacao_janela.id"))
    weekday: Mapped[int] = mapped_column("dia_semana", Integer)
    opens: Mapped[time] = mapped_column("abre", Time)
    closes: Mapped[time] = mapped_column("fecha", Time)


class WindowWeek(Base):
    """Semana liberada da janela."""

    __tablename__ = "programacao_janela_semana"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    window_id: Mapped[int] = mapped_column("janela_id", ForeignKey("programacao_janela.id"))
    week: Mapped[str] = mapped_column("semana", Text)


class WindowExtraRelease(Base):
    """Liberação extraordinária: uma semana e um intervalo absoluto que vencem as demais regras."""

    __tablename__ = "programacao_liberacao_extra"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    window_id: Mapped[int] = mapped_column("janela_id", ForeignKey("programacao_janela.id"))
    week: Mapped[str] = mapped_column("semana", Text)
    opens: Mapped[datetime] = mapped_column("abre", DateTime(timezone=True))
    closes: Mapped[datetime] = mapped_column("fecha", DateTime(timezone=True))
