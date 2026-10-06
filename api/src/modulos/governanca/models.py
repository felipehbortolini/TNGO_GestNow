"""Persistence models of the Governança module: the change request (SM) and its analysis and decision.

Class and attribute names are English (D1); tables and columns are Portuguese snake_case (D5),
exactly as in ``docs/MODELO-DE-DADOS.md``, section "08 Governança". The value sets below are the
vocabulary of the SM: they feed the CHECK constraints of the database, the validation and the
screens, so a spelling lives in one place.

Two kinds of column point to tables that belong to modules that arrive later and carry no database
foreign key yet (``eac_item_id`` of Financeiro, ``licao_id`` of the lessons of this module): the
migration of the owner of each table adds the constraint, as D9 asks for any link whose other end
is not there when the slice is written.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base
from src.core.money import Centavos

TYPE_REALLOCATION = "Remanejamento de orçamento"
TYPE_RESERVE_RELEASE = "Liberação de reserva"

CHANGE_TYPES = (
    "Escopo",
    "Prazo",
    "Custo",
    "Qualidade/Especificação",
    "Contratual",
    TYPE_REALLOCATION,
    TYPE_RESERVE_RELEASE,
)
CHANGE_ORIGINS = ("Cliente", "Contratada", "Engenharia", "Interna", "Legal/regulatória")
PRIORITY_NORMAL = "Normal"
PRIORITY_EMERGENCY = "Emergencial"
CHANGE_PRIORITIES = (PRIORITY_NORMAL, "Urgente", PRIORITY_EMERGENCY)

SITUATION_REGISTERED = "Registrada"
SITUATION_ANALYSIS = "Em análise de impacto"
SITUATION_AWAITING = "Aguardando comitê"
SITUATION_APPROVED = "Aprovada"
SITUATION_APPROVED_WITH_CONDITIONS = "Aprovada com condições"
SITUATION_REJECTED = "Rejeitada"
SITUATION_POSTPONED = "Adiada"
SITUATION_IMPLEMENTING = "Em implementação"
SITUATION_CLOSED = "Encerrada"
SITUATION_CANCELLED = "Cancelada"

CHANGE_SITUATIONS = (
    SITUATION_REGISTERED,
    SITUATION_ANALYSIS,
    SITUATION_AWAITING,
    SITUATION_APPROVED,
    SITUATION_APPROVED_WITH_CONDITIONS,
    SITUATION_REJECTED,
    SITUATION_POSTPONED,
    SITUATION_IMPLEMENTING,
    SITUATION_CLOSED,
    SITUATION_CANCELLED,
)

AUTHORITY_MANAGER = "Gerente do projeto"
AUTHORITY_COMMITTEE = "Comitê"
CHANGE_AUTHORITIES = (AUTHORITY_MANAGER, AUTHORITY_COMMITTEE)

SOURCE_MANAGEMENT_RESERVE = "Reserva gerencial"
RESOURCE_SOURCES = ("Aditivo de orçamento", "Reserva de contingência", SOURCE_MANAGEMENT_RESERVE)
RELEASE_RESERVES = ("Contingência", "Gerencial")
DECISION_RESULTS = (
    SITUATION_APPROVED,
    SITUATION_APPROVED_WITH_CONDITIONS,
    SITUATION_REJECTED,
    SITUATION_POSTPONED,
)

# The situations in which an SM counts as approved: the decision was positive and the SM went on.
APPROVED_SITUATIONS = (
    SITUATION_APPROVED,
    SITUATION_APPROVED_WITH_CONDITIONS,
    SITUATION_IMPLEMENTING,
    SITUATION_CLOSED,
)
# The situations that end the life of an SM: nothing else happens to it.
TERMINAL_SITUATIONS = (SITUATION_REJECTED, SITUATION_CLOSED, SITUATION_CANCELLED)
# The situations in which the requester or a Gestor may still cancel: before the decision.
CANCELLABLE_SITUATIONS = (
    SITUATION_REGISTERED,
    SITUATION_ANALYSIS,
    SITUATION_AWAITING,
    SITUATION_POSTPONED,
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join("'" + value.replace("'", "''") + "'" for value in values)
    return f"{column} IN ({quoted})"


class ChangeRequest(Base):
    """Solicitação de mudança (SM): tipo, origem, prioridade, situação, alçada e encerramento."""

    __tablename__ = "mudanca"
    __table_args__ = (
        CheckConstraint(_in_list("tipo", CHANGE_TYPES), name="tipo"),
        CheckConstraint(_in_list("origem", CHANGE_ORIGINS), name="origem"),
        CheckConstraint(_in_list("prioridade", CHANGE_PRIORITIES), name="prioridade"),
        CheckConstraint(_in_list("situacao", CHANGE_SITUATIONS), name="situacao"),
        CheckConstraint(
            "alcada IS NULL OR " + _in_list("alcada", CHANGE_AUTHORITIES), name="alcada"
        ),
        CheckConstraint(
            "fonte_recurso IS NULL OR " + _in_list("fonte_recurso", RESOURCE_SOURCES),
            name="fonte_recurso",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    requester_id: Mapped[int] = mapped_column("solicitante_id", ForeignKey("pessoa.id"))
    closed_by_id: Mapped[int | None] = mapped_column("encerrado_por_id", ForeignKey("pessoa.id"))
    lesson_id: Mapped[int | None] = mapped_column("licao_id", BigInteger)
    code: Mapped[str] = mapped_column("codigo", Text, unique=True)
    title: Mapped[str] = mapped_column("titulo", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    origin: Mapped[str] = mapped_column("origem", Text)
    priority: Mapped[str] = mapped_column("prioridade", Text)
    request_date: Mapped[date] = mapped_column("data_solicitacao", Date)
    description: Mapped[str] = mapped_column("descricao", Text)
    resource_source: Mapped[str | None] = mapped_column("fonte_recurso", Text)
    authority: Mapped[str | None] = mapped_column("alcada", Text)
    situation: Mapped[str] = mapped_column("situacao", Text)
    emergency: Mapped[bool] = mapped_column("emergencial", Boolean, server_default=text("false"))
    emergency_justification: Mapped[str | None] = mapped_column("justificativa_emergencial", Text)
    implementation_start: Mapped[date | None] = mapped_column("data_inicio_implementacao", Date)
    closing_date: Mapped[date | None] = mapped_column("data_encerramento", Date)
    closed_schedule: Mapped[bool | None] = mapped_column("encerrou_cronograma", Boolean)
    closed_contract: Mapped[bool | None] = mapped_column("encerrou_contrato", Boolean)
    closed_risks: Mapped[bool | None] = mapped_column("encerrou_riscos", Boolean)
    eac_revision: Mapped[int | None] = mapped_column("eac_revisao_incorporada", Integer)
    eap_revision: Mapped[int | None] = mapped_column("eap_revisao_incorporada", Integer)
    closing_note: Mapped[str | None] = mapped_column("encerramento_observacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ChangeAnalysis(Base):
    """Análise em andamento: responsável, início, prazo e conclusão (uma rodada por reapresentação)."""

    __tablename__ = "mudanca_analise"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    start_date: Mapped[date] = mapped_column("data_inicio", Date)
    deadline: Mapped[date] = mapped_column("prazo", Date)
    concluded_on: Mapped[date | None] = mapped_column("concluida_em", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ChangeImpact(Base):
    """Análise de impacto: custo em centavos, prazo em dias e as demais dimensões; a última vale."""

    __tablename__ = "mudanca_impacto"
    __table_args__ = (
        CheckConstraint(
            "liberacao_reserva IS NULL OR " + _in_list("liberacao_reserva", RELEASE_RESERVES),
            name="liberacao_reserva",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    analyst_id: Mapped[int] = mapped_column("analista_id", ForeignKey("pessoa.id"))
    analysis_date: Mapped[date] = mapped_column("data_analise", Date)
    cost_cents: Mapped[int] = mapped_column("custo_centavos", Centavos)
    term_days: Mapped[int] = mapped_column("prazo_dias", Integer)
    scope: Mapped[str] = mapped_column("escopo", Text)
    quality: Mapped[str] = mapped_column("qualidade", Text)
    risks: Mapped[str] = mapped_column("riscos", Text)
    safety: Mapped[str] = mapped_column("sms", Text)
    contract: Mapped[str] = mapped_column("contrato", Text)
    affects_contract_milestone: Mapped[bool] = mapped_column("afeta_marco_contratual", Boolean)
    activities: Mapped[str | None] = mapped_column("atividades", Text)
    release_reserve: Mapped[str | None] = mapped_column("liberacao_reserva", Text)
    release_value_cents: Mapped[int | None] = mapped_column("liberacao_valor_centavos", Centavos)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ChangeImpactEacItem(Base):
    """Item da EAC afetado pela análise (fato sem ``versao``); o vínculo com ``eac_item`` vem depois."""

    __tablename__ = "mudanca_impacto_eac_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    impact_id: Mapped[int] = mapped_column("impacto_id", ForeignKey("mudanca_impacto.id"))
    eac_item_id: Mapped[int] = mapped_column("eac_item_id", BigInteger)


class ChangeReallocation(Base):
    """Transferência proposta entre itens da EAC e a sua aplicação (fato sem ``versao``)."""

    __tablename__ = "mudanca_remanejamento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    source_item_id: Mapped[int] = mapped_column("origem_item_id", BigInteger)
    target_item_id: Mapped[int] = mapped_column("destino_item_id", BigInteger)
    applied_by_id: Mapped[int | None] = mapped_column("aplicado_por_id", ForeignKey("pessoa.id"))
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    applied: Mapped[bool] = mapped_column("aplicado", Boolean, server_default=text("false"))
    applied_on: Mapped[date | None] = mapped_column("aplicado_em", Date)
    eac_revision: Mapped[int | None] = mapped_column("revisao_eac", Integer)


class ChangeDecision(Base):
    """Cada decisão registrada, inclusive as adiadas: data, resultado, condições e justificativa."""

    __tablename__ = "mudanca_decisao"
    __table_args__ = (CheckConstraint(_in_list("resultado", DECISION_RESULTS), name="resultado"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    decision_date: Mapped[date] = mapped_column("data", Date)
    result: Mapped[str] = mapped_column("resultado", Text)
    conditions: Mapped[str | None] = mapped_column("condicoes", Text)
    justification: Mapped[str] = mapped_column("justificativa", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ChangeDecisionParticipant(Base):
    """Participante da decisão, para conferir o quórum (fato sem ``versao``)."""

    __tablename__ = "mudanca_decisao_participante"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column("decisao_id", ForeignKey("mudanca_decisao.id"))
    person_id: Mapped[int] = mapped_column("pessoa_id", ForeignKey("pessoa.id"))
