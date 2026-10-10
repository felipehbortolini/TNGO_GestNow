"""Persistence models for the HSE module: the monthly hours, the proactive records (ISSUE-072),
the occurrence with its investigation and the restricted data (ISSUE-073) and the risk analyses
(ISSUE-074).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case (D5),
as in ``docs/MODELO-DE-DADOS.md``. A month is stored as the first day of the month. The
occurrence carries the deadlines in force at its registration (D5b) and the restricted row
(nome e dados médicos) is a separate table with one row per occurrence (Q35). A risk analysis
reunites participants (without ``versao``: they enter and leave with the study) and carries its
recommendations with the closing date and the evidence, columns added to the diagram in the
same delivery (D5b).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base

ZERO_SERVER_DEFAULT = text("0")
FALSE_SERVER_DEFAULT = text("false")

# The pyramid of occurrence types: levels 1 to 4 by type; Ambiental is out of the pyramid and
# has a severity of its own. The vocabulary lives in one place: it feeds the CHECK constraints,
# the validation and the screens.
OCCURRENCE_TYPE_LEVELS: dict[str, int] = {
    "Fatalidade": 1,
    "Acidente com afastamento": 1,
    "Trabalho restrito": 2,
    "Tratamento médico": 2,
    "Primeiros socorros": 2,
    "Dano material": 3,
    "Quase acidente": 4,
}
OCCURRENCE_TYPES: tuple[str, ...] = (*OCCURRENCE_TYPE_LEVELS, "Ambiental")
SITUATION_REGISTERED = "Registrada"
SITUATION_INVESTIGATING = "Em investigação"
SITUATION_ACTIONS = "Ações definidas"
SITUATION_TREATING = "Em tratamento"
SITUATION_CLOSED = "Encerrada"
OCCURRENCE_SITUATIONS: tuple[str, ...] = (
    SITUATION_REGISTERED,
    SITUATION_INVESTIGATING,
    SITUATION_ACTIONS,
    SITUATION_TREATING,
    SITUATION_CLOSED,
)
ENVIRONMENTAL_SUBTYPES: tuple[str, ...] = ("Vazamento", "Emissão", "Resíduo", "Outro")
ENVIRONMENTAL_SEVERITIES: tuple[str, ...] = ("Baixa", "Moderada", "Alta")
INVESTIGATION_METHODS: tuple[str, ...] = ("5 porquês", "Árvore de causas")

# The risk analyses (APR/JSA and HAZOP) and their recommendations: the vocabulary of the type
# and of the situation feeds the CHECK constraints, the validation and the screens.
ANALYSIS_TYPES: tuple[str, ...] = ("APR", "HAZOP")
RECOMMENDATION_OPEN = "Aberta"
RECOMMENDATION_CLOSED = "Fechada"
RECOMMENDATION_SITUATIONS: tuple[str, ...] = (RECOMMENDATION_OPEN, RECOMMENDATION_CLOSED)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join("'" + value.replace("'", "''") + "'" for value in values)
    return f"{column} IN ({quoted})"


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


class Occurrence(Base):
    """Ocorrência sem dado pessoal: gravidade potencial (P x I), HiPo, prazos gravados e fluxo.

    O prazo vigente na data do registro fica gravado (D5b): mudar o parâmetro depois não muda a
    ocorrência. O nome e os dados médicos moram em ``ocorrencia_restrito`` (Q35); a investigação,
    em ``ocorrencia_investigacao``.
    """

    __tablename__ = "ocorrencia"
    __table_args__ = (
        UniqueConstraint("projeto_id", "codigo"),
        CheckConstraint(_in_list("tipo", OCCURRENCE_TYPES), name="tipo"),
        CheckConstraint(_in_list("situacao", OCCURRENCE_SITUATIONS), name="situacao"),
        CheckConstraint(
            "subtipo IS NULL OR " + _in_list("subtipo", ENVIRONMENTAL_SUBTYPES), name="subtipo"
        ),
        CheckConstraint(
            "severidade_ambiental IS NULL OR "
            + _in_list("severidade_ambiental", ENVIRONMENTAL_SEVERITIES),
            name="severidade_ambiental",
        ),
        CheckConstraint("potencial_p IS NULL OR potencial_p BETWEEN 1 AND 5", name="potencial_p"),
        CheckConstraint("potencial_i IS NULL OR potencial_i BETWEEN 1 AND 5", name="potencial_i"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    happened_at: Mapped[datetime] = mapped_column("data_hora", DateTime(timezone=True))
    kind: Mapped[str] = mapped_column("tipo", Text)
    subtype: Mapped[str | None] = mapped_column("subtipo", Text)
    area: Mapped[str] = mapped_column("area", Text)
    place: Mapped[str | None] = mapped_column("local", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    role: Mapped[str | None] = mapped_column("funcao", Text)
    people_involved: Mapped[int] = mapped_column(
        "pessoas_envolvidas", Integer, server_default=ZERO_SERVER_DEFAULT
    )
    potential_p: Mapped[int | None] = mapped_column("potencial_p", Integer)
    potential_i: Mapped[int | None] = mapped_column("potencial_i", Integer)
    hipo: Mapped[bool] = mapped_column("hipo", Boolean, server_default=FALSE_SERVER_DEFAULT)
    environmental: Mapped[bool] = mapped_column(
        "ambiental", Boolean, server_default=FALSE_SERVER_DEFAULT
    )
    environmental_severity: Mapped[str | None] = mapped_column("severidade_ambiental", Text)
    immediate_cause: Mapped[str | None] = mapped_column("causa_imediata", Text)
    communication_hours: Mapped[int] = mapped_column("comunicacao_horas", Integer)
    communication_deadline_hours: Mapped[int] = mapped_column("prazo_comunicacao_horas", Integer)
    investigation_deadline_hours: Mapped[int] = mapped_column("prazo_investigacao_horas", Integer)
    report_deadline_days: Mapped[int] = mapped_column("prazo_relatorio_dias", Integer)
    situation: Mapped[str] = mapped_column("situacao", Text)
    closed_on: Mapped[date | None] = mapped_column("data_encerramento", Date)
    effectiveness: Mapped[str | None] = mapped_column("eficacia", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class OccurrenceRestricted(Base):
    """Acesso restrito da ocorrência (LGPD, Q35): nome e dados médicos; um por ocorrência.

    O Membro preenche junto com o registro; só Gestor e Admin leem de volta, inclusive os anexos
    com esses dados (``attachment_origins`` com ``restricted``).
    """

    __tablename__ = "ocorrencia_restrito"
    __table_args__ = (UniqueConstraint("ocorrencia_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurrence_id: Mapped[int] = mapped_column("ocorrencia_id", ForeignKey("ocorrencia.id"))
    name: Mapped[str | None] = mapped_column("nome", Text)
    real_gravity: Mapped[int | None] = mapped_column("gravidade_real", Integer)
    days_lost: Mapped[int] = mapped_column(
        "dias_perdidos", Integer, server_default=ZERO_SERVER_DEFAULT
    )
    days_charged: Mapped[int] = mapped_column(
        "dias_debitados", Integer, server_default=ZERO_SERVER_DEFAULT
    )
    cat: Mapped[bool] = mapped_column("cat", Boolean, server_default=FALSE_SERVER_DEFAULT)
    medical_notes: Mapped[str | None] = mapped_column("descricao_medica", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class OccurrenceInvestigation(Base):
    """Investigação da ocorrência (método, causa raiz, data e responsável); fato sem ``versao``."""

    __tablename__ = "ocorrencia_investigacao"
    __table_args__ = (CheckConstraint(_in_list("metodo", INVESTIGATION_METHODS), name="metodo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurrence_id: Mapped[int] = mapped_column("ocorrencia_id", ForeignKey("ocorrencia.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    method: Mapped[str] = mapped_column("metodo", Text)
    root_cause: Mapped[str] = mapped_column("causa_raiz", Text)
    investigated_on: Mapped[date] = mapped_column("data", Date)


class RiskAnalysis(Base):
    """Estudo de risco (APR/JSA ou HAZOP): tipo, área, título e data; UK projeto + código."""

    __tablename__ = "analise_risco"
    __table_args__ = (
        UniqueConstraint("projeto_id", "codigo"),
        CheckConstraint(_in_list("tipo", ANALYSIS_TYPES), name="tipo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    area: Mapped[str] = mapped_column("area", Text)
    title: Mapped[str] = mapped_column("titulo", Text)
    held_on: Mapped[date] = mapped_column("data", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class RiskAnalysisParticipant(Base):
    """Participante do estudo; sem ``versao``, entra e sai com o estudo."""

    __tablename__ = "analise_risco_participante"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column("analise_id", ForeignKey("analise_risco.id"))
    person_id: Mapped[int] = mapped_column("pessoa_id", ForeignKey("pessoa.id"))


class RiskAnalysisRecommendation(Base):
    """Recomendação de um estudo: descrição, responsável, prazo e situação.

    O fechamento guarda a data de conclusão e a evidência (colunas acrescentadas ao MODELO §12
    na mesma entrega da ISSUE-074, D5b); uma recomendação aberta com o prazo vencido conta como
    atrasada, calculada na leitura (``calculations.recommendation_overdue``).
    """

    __tablename__ = "analise_risco_recomendacao"
    __table_args__ = (
        CheckConstraint(_in_list("situacao", RECOMMENDATION_SITUATIONS), name="situacao"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column("analise_id", ForeignKey("analise_risco.id"))
    responsible_id: Mapped[int] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    position: Mapped[int] = mapped_column("ordem", Integer)
    description: Mapped[str] = mapped_column("descricao", Text)
    due_date: Mapped[date] = mapped_column("prazo", Date)
    situation: Mapped[str] = mapped_column("situacao", Text)
    closed_on: Mapped[date | None] = mapped_column("data_conclusao", Date)
    evidence: Mapped[str | None] = mapped_column("evidencia", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)
