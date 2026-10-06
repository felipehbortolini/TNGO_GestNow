"""Persistence models for the Risk management module (D5, ISSUE-064).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case (D5),
exactly as in ``docs/MODELO-DE-DADOS.md``. Score, severity, VME, exposure and the review
situation are never columns: they are calculated on every query (D6, ``calculations``).

``risco.ata_id``, ``risco.mudanca_id``, ``risco.licao_id`` and ``risco.encerramento_mudanca_id``
are plain columns in this slice: the foreign keys arrive with the issues that own those tables
(minutes, changes, lessons). ``risco.identificado_em`` is the identification date the form asks
for (added to the model with this slice).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base
from src.core.money import Centavos

FALSE_SERVER_DEFAULT = text("false")


class RiskCategory(Base):
    """Categoria da RBS: o grupo (nível 1) e o nome da subcategoria (nível 2)."""

    __tablename__ = "risco_categoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group: Mapped[str] = mapped_column("grupo", Text)
    name: Mapped[str] = mapped_column("nome", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class Risk(Base):
    """Risco (ameaça ou oportunidade) do projeto, com identificação, plano e encerramento."""

    __tablename__ = "risco"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    category_id: Mapped[int] = mapped_column("categoria_id", ForeignKey("risco_categoria.id"))
    owner_id: Mapped[int] = mapped_column("dono_id", ForeignKey("pessoa.id"))
    identified_by_id: Mapped[int] = mapped_column("identificado_por_id", ForeignKey("pessoa.id"))
    ata_id: Mapped[int | None] = mapped_column("ata_id", BigInteger)
    change_id: Mapped[int | None] = mapped_column("mudanca_id", BigInteger)
    lesson_id: Mapped[int | None] = mapped_column("licao_id", BigInteger)
    plan_responsible_id: Mapped[int | None] = mapped_column(
        "responsavel_plano_id", ForeignKey("pessoa.id")
    )
    closed_by_id: Mapped[int | None] = mapped_column("encerrado_por_id", ForeignKey("pessoa.id"))
    hidden_by_id: Mapped[int | None] = mapped_column("ocultado_por_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text, unique=True)
    title: Mapped[str] = mapped_column("titulo", Text)
    nature: Mapped[str] = mapped_column("natureza", Text)
    origin_type: Mapped[str] = mapped_column("origem_tipo", Text)
    origin: Mapped[str | None] = mapped_column("origem", Text)
    cause: Mapped[str] = mapped_column("causa", Text)
    consequence: Mapped[str] = mapped_column("consequencia", Text)
    description: Mapped[str | None] = mapped_column("descricao", Text)
    trigger: Mapped[str | None] = mapped_column("gatilho", Text)
    life_risk: Mapped[bool] = mapped_column(
        "risco_vida", Boolean, server_default=FALSE_SERVER_DEFAULT
    )
    dimension: Mapped[str | None] = mapped_column("dimensao", Text)
    schedule_impact_days: Mapped[int] = mapped_column(
        "impacto_prazo_dias", Integer, server_default=text("0")
    )
    cost_impact_cents: Mapped[int] = mapped_column(
        "impacto_custo_centavos", Centavos, server_default=text("0")
    )
    strategy: Mapped[str | None] = mapped_column("estrategia", Text)
    plan: Mapped[str | None] = mapped_column("plano", Text)
    target_severity: Mapped[str | None] = mapped_column("severidade_alvo", Text)
    target_date: Mapped[date | None] = mapped_column("prazo_alvo", Date)
    response_cost_cents: Mapped[int | None] = mapped_column("custo_resposta_centavos", Centavos)
    instrument: Mapped[str | None] = mapped_column("instrumento", Text)
    cadence_days: Mapped[int | None] = mapped_column("cadencia_dias", Integer)
    last_review: Mapped[date | None] = mapped_column("ultima_revisao", Date)
    next_review: Mapped[date | None] = mapped_column("proxima_revisao", Date)
    situation: Mapped[str] = mapped_column("situacao", Text)
    closing_reason: Mapped[str | None] = mapped_column("encerramento_motivo", Text)
    closing_date: Mapped[date | None] = mapped_column("encerramento_data", Date)
    closing_schedule_impact_days: Mapped[int | None] = mapped_column(
        "encerramento_impacto_prazo_dias", Integer
    )
    closing_cost_impact_cents: Mapped[int | None] = mapped_column(
        "encerramento_impacto_custo_centavos", Centavos
    )
    closing_change_id: Mapped[int | None] = mapped_column("encerramento_mudanca_id", BigInteger)
    hidden: Mapped[bool] = mapped_column("oculto", Boolean, server_default=FALSE_SERVER_DEFAULT)
    deletion_reason: Mapped[str | None] = mapped_column("motivo_exclusao", Text)
    hidden_at: Mapped[datetime | None] = mapped_column("ocultado_em", DateTime(timezone=True))
    identified_on: Mapped[date] = mapped_column("identificado_em", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class RiskAssessment(Base):
    """Cada avaliação inerente ou residual: P, I e as seis dimensões; fato imutável."""

    __tablename__ = "risco_avaliacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column("risco_id", ForeignKey("risco.id"))
    author_id: Mapped[int] = mapped_column("autor_id", ForeignKey("pessoa.id"))
    kind: Mapped[str] = mapped_column("tipo", Text)
    probability: Mapped[int] = mapped_column("p", Integer)
    impact: Mapped[int] = mapped_column("i", Integer)
    schedule_dimension: Mapped[int | None] = mapped_column("dim_prazo", Integer)
    cost_dimension: Mapped[int | None] = mapped_column("dim_custo", Integer)
    scope_dimension: Mapped[int | None] = mapped_column("dim_escopo", Integer)
    safety_dimension: Mapped[int | None] = mapped_column("dim_sms", Integer)
    image_dimension: Mapped[int | None] = mapped_column("dim_imagem", Integer)
    legal_dimension: Mapped[int | None] = mapped_column("dim_legal", Integer)
    assessed_on: Mapped[date] = mapped_column("data", Date)


class RiskReview(Base):
    """Cada revisão periódica do risco (linha do tempo da ficha, ISSUE-065)."""

    __tablename__ = "risco_revisao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column("risco_id", ForeignKey("risco.id"))
    author_id: Mapped[int] = mapped_column("autor_id", ForeignKey("pessoa.id"))
    reviewed_on: Mapped[date] = mapped_column("data", Date)
    kind: Mapped[str] = mapped_column("tipo", Text)
    assessed_situation: Mapped[str] = mapped_column("situacao_apurada", Text)
    score_from: Mapped[int | None] = mapped_column("score_de", Integer)
    score_to: Mapped[int] = mapped_column("score_para", Integer)
    probability: Mapped[int] = mapped_column("p", Integer)
    impact: Mapped[int] = mapped_column("i", Integer)
    trigger_occurred: Mapped[bool] = mapped_column(
        "gatilho", Boolean, server_default=FALSE_SERVER_DEFAULT
    )
    body: Mapped[str | None] = mapped_column("texto", Text)


class RiskPlanApproval(Base):
    """Cada pedido de aprovação do plano de resposta e a decisão (ISSUE-065)."""

    __tablename__ = "risco_plano_aprovacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column("risco_id", ForeignKey("risco.id"))
    by_id: Mapped[int | None] = mapped_column("por_id", ForeignKey("pessoa.id"))
    situation: Mapped[str] = mapped_column("situacao", Text)
    requested_at: Mapped[datetime | None] = mapped_column("solicitada_em", DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column("decidida_em", DateTime(timezone=True))
    justification: Mapped[str | None] = mapped_column("justificativa", Text)
