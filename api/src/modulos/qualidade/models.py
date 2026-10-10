"""Persistence model of the Quality module: the RNC (ISSUE-068) and the ITP (ISSUE-069).

Class and attribute names are English (D1); the table and the columns are Portuguese
snake_case (D5), exactly as in ``docs/MODELO-DE-DADOS.md``. Situation, deadline, overdue,
next step and recurrence are never columns: they are calculated on every read (D6,
``calculations``); the recurrence is read from the audit trail of the record. ``licao_id`` is
a real foreign key to the lesson of Governança, written when the effectiveness closes the
report (D9).

The ITP is the plan (``itp``), its revisions (``itp_revisao``) and the inspection points of
each revision (``itp_ponto``); the inspection (``inspecao``) records one point as a fact of
the moment — the point and its type are copied into the row. The FAT of the procurement
diligence writes an inspection without a point of ITP, identified by ``pedido_id``; the
notification of the client (the W point) is the ``notificacao`` column added with the rule.
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
from src.core.money import Centavos

ZERO_SERVER_DEFAULT = text("0")


class Rnc(Base):
    """Relatório de não conformidade (RNC) do projeto, com o fluxo até o encerramento."""

    __tablename__ = "rnc"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    discipline_id: Mapped[int] = mapped_column("disciplina_id", ForeignKey("disciplina.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    responsible_id: Mapped[int | None] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    opened_by_id: Mapped[int] = mapped_column("aberta_por_id", ForeignKey("pessoa.id"))
    verified_by_id: Mapped[int | None] = mapped_column("eficacia_por_id", ForeignKey("pessoa.id"))
    lesson_id: Mapped[int | None] = mapped_column("licao_id", ForeignKey("licao.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    rnc_date: Mapped[date] = mapped_column("data", Date)
    origin: Mapped[str] = mapped_column("origem", Text)
    origin_ref: Mapped[str | None] = mapped_column("origem_ref", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    severity: Mapped[str] = mapped_column("severidade", Text)
    containment: Mapped[str] = mapped_column("contencao", Text)
    disposition: Mapped[str | None] = mapped_column("disposicao", Text)
    concession_reference: Mapped[str | None] = mapped_column("concessao_referencia", Text)
    concession_date: Mapped[date | None] = mapped_column("concessao_data", Date)
    method: Mapped[str | None] = mapped_column("metodo", Text)
    root_cause: Mapped[str | None] = mapped_column("causa_raiz", Text)
    deadline: Mapped[date] = mapped_column("prazo", Date)
    closing_date: Mapped[date | None] = mapped_column("encerramento", Date)
    situation: Mapped[str] = mapped_column("situacao", Text)
    cost_cents: Mapped[int] = mapped_column(
        "custo_nao_qualidade_centavos", Centavos, server_default=ZERO_SERVER_DEFAULT
    )
    verification_expected: Mapped[date | None] = mapped_column("verificacao_prevista", Date)
    effectiveness_date: Mapped[date | None] = mapped_column("eficacia_data", Date)
    effectiveness: Mapped[bool | None] = mapped_column("eficacia_eficaz", Boolean)
    effectiveness_text: Mapped[str | None] = mapped_column("eficacia_texto", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)


class Itp(Base):
    """Plano de inspeção e testes (ITP) do projeto: o código e a revisão vigente."""

    __tablename__ = "itp"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    discipline_id: Mapped[int] = mapped_column("disciplina_id", ForeignKey("disciplina.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    title: Mapped[str] = mapped_column("titulo", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    __table_args__ = (UniqueConstraint("codigo"),)


class ItpRevision(Base):
    """Uma revisão do ITP: a data e a aprovação do cliente (volta a pedir a cada revisão)."""

    __tablename__ = "itp_revisao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    itp_id: Mapped[int] = mapped_column("itp_id", ForeignKey("itp.id"))
    approved_by_id: Mapped[int | None] = mapped_column("aprovacao_por_id", ForeignKey("pessoa.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    revision_date: Mapped[date] = mapped_column("data", Date)
    approved_by_client: Mapped[bool] = mapped_column("aprovado_cliente", Boolean)
    approval_reference: Mapped[str | None] = mapped_column("aprovacao_referencia", Text)
    approval_date: Mapped[date | None] = mapped_column("aprovacao_data", Date)


class ItpPoint(Base):
    """Um ponto do ITP (H, W ou R): pertence à revisão vigente, com a ordem do plano."""

    __tablename__ = "itp_ponto"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column("revisao_id", ForeignKey("itp_revisao.id"))
    order: Mapped[int] = mapped_column("ordem", Integer)
    activity: Mapped[str] = mapped_column("atividade", Text)
    point_type: Mapped[str] = mapped_column("tipo", Text)
    criterion: Mapped[str] = mapped_column("criterio", Text)
    reference: Mapped[str] = mapped_column("referencia", Text)
    responsible: Mapped[str] = mapped_column("responsavel", Text)


class Inspection(Base):
    """Registro de inspeção de um ponto do ITP, ou do FAT do pedido (sem ponto de ITP)."""

    __tablename__ = "inspecao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    itp_point_id: Mapped[int | None] = mapped_column("itp_ponto_id", ForeignKey("itp_ponto.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    inspector_id: Mapped[int] = mapped_column("inspetor_id", ForeignKey("pessoa.id"))
    rnc_id: Mapped[int | None] = mapped_column("rnc_id", ForeignKey("rnc.id"))
    order_id: Mapped[int | None] = mapped_column("pedido_id", ForeignKey("pedido.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    point: Mapped[str] = mapped_column("ponto", Text)
    point_type: Mapped[str] = mapped_column("tipo_ponto", Text)
    inspection_date: Mapped[date] = mapped_column("data", Date)
    result: Mapped[str] = mapped_column("resultado", Text)
    observation: Mapped[str] = mapped_column("observacao", Text)
    notification: Mapped[date | None] = mapped_column("notificacao", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)
