"""Persistence models for the Planning module.

Class and attribute names are English (D1); tables and columns are Portuguese snake_case
(D5), matching ``docs/MODELO-DE-DADOS.md``.

Relato do período (ISSUE-044): one ``relato`` per project, type and period; its activities
(``relato_atividade``) and attention points (``relato_ponto``) are the children of the
aggregate and are edited together with it, protected by the ``versao`` of the root.


The EAP (ISSUE-036): the three-level tree of the physical scope, the stages of a package, its
measurements, the revisions with the weights frozen in them and the splits of planning packages.
No indicator is a column (D5b): the progress of a package comes from its last measurement through
the measuring criterion, and the totals of the levels are sums made by the facade.

The 6WLA (ISSUE-045): the activities of the six-week horizon, the mark of each
week and the restrictions that hold an activity back. Class and attribute names
are English (D1); tables and columns are Portuguese snake_case (D5), matching
``docs/MODELO-DE-DADOS.md``.
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import VERSION_SERVER_DEFAULT, Base


class Report(Base):
    """Relato do período: o relato semanal (semana ISO) ou mensal (mês civil) de um projeto."""

    __tablename__ = "relato"
    __table_args__ = (UniqueConstraint("projeto_id", "tipo", "periodo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    created_by_id: Mapped[int] = mapped_column("criado_por_id", ForeignKey("pessoa.id"))
    updated_by_id: Mapped[int] = mapped_column("atualizado_por_id", ForeignKey("pessoa.id"))
    kind: Mapped[str] = mapped_column("tipo", Text)
    period: Mapped[str] = mapped_column("periodo", Text)
    created_at: Mapped[datetime] = mapped_column(
        "criado_em", DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        "atualizado_em", DateTime(timezone=True), server_default=func.now()
    )
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    activities: Mapped[list[ReportActivity]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportActivity.order",
    )
    points: Mapped[list[ReportPoint]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportPoint.order",
    )


class ReportActivity(Base):
    """Atividade do relato: uma linha do período ou do próximo período, na ordem digitada."""

    __tablename__ = "relato_atividade"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column("relato_id", ForeignKey("relato.id"))
    group: Mapped[str] = mapped_column("grupo", Text)
    order: Mapped[int] = mapped_column("ordem", Integer)
    text: Mapped[str] = mapped_column("texto", Text)

    report: Mapped[Report] = relationship(back_populates="activities")


class ReportPoint(Base):
    """Ponto de atenção do relato, com o risco atrelado (ameaça ou oportunidade).

    O risco é a leitura do planejamento e não tem vínculo com o registro do 05.
    """

    __tablename__ = "relato_ponto"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column("relato_id", ForeignKey("relato.id"))
    order: Mapped[int] = mapped_column("ordem", Integer)
    description: Mapped[str] = mapped_column("descricao", Text)
    nature: Mapped[str] = mapped_column("natureza", Text)
    risk: Mapped[str] = mapped_column("risco", Text)

    report: Mapped[Report] = relationship(back_populates="points")


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


<<<<<<< HEAD
class PunchItem(Base):
    """Item da punch list (ISSUE-049): sistema, TAG, categoria A/B/C, marco, fluxo e verificação."""

    __tablename__ = "punch_item"
=======
Percent = Numeric(7, 2)


class EapItem(Base):
    """Item of the EAP in three levels: area, subarea and package (work or planning).

    Only the packages carry weight, baseline dates, measuring criterion and progress. The progress
    is not a column (D5b): it is the last measurement read through the criterion.
    """

    __tablename__ = "eap_item"
>>>>>>> exec/ISSUE-036
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
<<<<<<< HEAD
    system_id: Mapped[int] = mapped_column("sistema_id", ForeignKey("sistema.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    identified_by_id: Mapped[int] = mapped_column("identificado_por_id", ForeignKey("pessoa.id"))
    verified_by_id: Mapped[int | None] = mapped_column("verificado_por_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    subsystem: Mapped[str] = mapped_column("subsistema", Text)
    tag: Mapped[str] = mapped_column("tag", Text)
    discipline: Mapped[str] = mapped_column("disciplina", Text)
    category: Mapped[str] = mapped_column("categoria", Text)
    milestone: Mapped[str] = mapped_column("marco", Text)
    origin: Mapped[str] = mapped_column("origem", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    opened_on: Mapped[date] = mapped_column("abertura", Date)
    due_date: Mapped[date] = mapped_column("prazo", Date)
    closed_on: Mapped[date | None] = mapped_column("fechamento", Date)
    situation: Mapped[str] = mapped_column("situacao", Text)
    treatment_comment: Mapped[str | None] = mapped_column("comentario_tratamento", Text)
    verification_comment: Mapped[str | None] = mapped_column("comentario_verificacao", Text)
    cancellation_reason: Mapped[str | None] = mapped_column("justificativa_cancelamento", Text)
    rejections: Mapped[int] = mapped_column("reprovacoes", Integer, server_default=text("0"))
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)
=======
    parent_id: Mapped[int | None] = mapped_column("pai_id", ForeignKey("eap_item.id"))
    eac_item_id: Mapped[int | None] = mapped_column("eac_item_id", ForeignKey("eac_item.id"))
    unit_id: Mapped[int | None] = mapped_column("unidade_id", ForeignKey("unidade.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    responsible_id: Mapped[int | None] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    level: Mapped[int] = mapped_column("nivel", Integer)
    kind: Mapped[str | None] = mapped_column("tipo", Text)
    criterion: Mapped[str | None] = mapped_column("criterio", Text)
    stage_model: Mapped[str | None] = mapped_column("modelo", Text)
    quantity: Mapped[Decimal | None] = mapped_column("quantidade", Numeric(18, 4))
    weight: Mapped[Decimal | None] = mapped_column("peso", Percent)
    planned: Mapped[Decimal | None] = mapped_column("previsto", Percent)
    start_date: Mapped[date | None] = mapped_column("inicio", Date)
    end_date: Mapped[date | None] = mapped_column("termino", Date)
    deliverable: Mapped[str | None] = mapped_column("entregavel", Text)
    acceptance: Mapped[str | None] = mapped_column("aceitacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class EapItemStage(Base):
    """Stage of a package of the Etapas criterion; the percentage done comes from the measurement."""

    __tablename__ = "eap_item_etapa"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eap_item.id"))
    order: Mapped[int] = mapped_column("ordem", Integer)
    name: Mapped[str] = mapped_column("nome", Text)
    weight: Mapped[Decimal] = mapped_column("peso", Percent)


class EapMeasurement(Base):
    """Dated measurement of a package (date, from, to, author, note): an immutable fact."""

    __tablename__ = "eap_medicao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eap_item.id"))
    author_id: Mapped[int | None] = mapped_column("autor_id", ForeignKey("pessoa.id"))
    measured_on: Mapped[date] = mapped_column("data", Date)
    from_percent: Mapped[Decimal] = mapped_column("de", Percent)
    to_percent: Mapped[Decimal] = mapped_column("para", Percent)
    note: Mapped[str | None] = mapped_column("observacao", Text)


class EapRevision(Base):
    """Revision of the EAP (Rev 0 is the baseline); the number of packages is calculated."""

    __tablename__ = "eap_revisao"
    __table_args__ = (UniqueConstraint("projeto_id", "revisao"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    approved_by_id: Mapped[int | None] = mapped_column("aprovado_por_id", ForeignKey("pessoa.id"))
    number: Mapped[int] = mapped_column("revisao", Integer)
    revised_on: Mapped[date] = mapped_column("data", Date)
    change: Mapped[str] = mapped_column("alteracao", Text)
    justification: Mapped[str] = mapped_column("justificativa", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class EapRevisionItem(Base):
    """Exception of D5b: the weight of each package frozen in the revision."""

    __tablename__ = "eap_revisao_item"
    __table_args__ = (UniqueConstraint("revisao_id", "item_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column("revisao_id", ForeignKey("eap_revisao.id"))
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eap_item.id"))
    weight: Mapped[Decimal] = mapped_column("peso", Percent)


class EapSplit(Base):
    """Split of a planning package into a work package: the weight moves, the total does not."""

    __tablename__ = "eap_desdobramento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    source_item_id: Mapped[int] = mapped_column("origem_item_id", ForeignKey("eap_item.id"))
    target_item_id: Mapped[int] = mapped_column("destino_item_id", ForeignKey("eap_item.id"))
    by_id: Mapped[int | None] = mapped_column("por_id", ForeignKey("pessoa.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    split_on: Mapped[date] = mapped_column("data", Date)
    weight: Mapped[Decimal] = mapped_column("peso", Percent)
    justification: Mapped[str] = mapped_column("justificativa", Text)
>>>>>>> exec/ISSUE-036
