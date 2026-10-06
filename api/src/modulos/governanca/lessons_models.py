"""Persistence models of the lessons learned of the Governança module (ISSUE-027).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case (D5), as in
``docs/MODELO-DE-DADOS.md``, section "08 Governança". The value sets below are the vocabulary of the
lesson: they feed the CHECK constraints, the validation and the screens, so a spelling lives in one
place. ``reusos`` is not a column: it is the count of ``licao_aplicacao``.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base
from src.core.money import Centavos

LESSON_TYPES = ("A repetir", "A evitar")
LESSON_PHASES = (
    "Iniciação",
    "Engenharia",
    "Suprimentos",
    "Construção",
    "Comissionamento",
    "Encerramento",
)
LESSON_AREAS = (
    "Escopo",
    "Cronograma",
    "Custos",
    "Qualidade",
    "Recursos",
    "Comunicações",
    "Riscos",
    "Aquisições",
    "Partes interessadas",
    "SMS",
)

SITUATION_DRAFT = "Rascunho"
SITUATION_VALIDATING = "Em validação"
SITUATION_VALIDATED = "Validada"
SITUATION_PUBLISHED = "Publicada"
LESSON_SITUATIONS = (
    SITUATION_DRAFT,
    SITUATION_VALIDATING,
    SITUATION_VALIDATED,
    SITUATION_PUBLISHED,
)

APPLICABILITY_PROJECT = "Projeto"
APPLICABILITY_CORPORATE = "Corporativa"
LESSON_APPLICABILITIES = (APPLICABILITY_PROJECT, APPLICABILITY_CORPORATE)

ORIGIN_MINUTES = "Ata"
ORIGIN_PUNCH = "Punch list"
ORIGIN_CONTRACT = "Contrato"
ORIGIN_SUPPLY = "Suprimentos"
ORIGIN_RISK = "Risco"
ORIGIN_NCR = "RNC"
ORIGIN_HSE = "HSE"
ORIGIN_CHANGE = "Mudança"
ORIGIN_WORKSHOP = "Workshop de lições"
ORIGIN_CLOSING = "Encerramento do projeto"
ORIGIN_DIRECT = "Registro direto"

# The origins that point to a record of another module: the number of the record is required and
# confirmed by the facade of the owner.
MODULE_ORIGINS = (
    ORIGIN_MINUTES,
    ORIGIN_PUNCH,
    ORIGIN_CONTRACT,
    ORIGIN_SUPPLY,
    ORIGIN_RISK,
    ORIGIN_NCR,
    ORIGIN_HSE,
    ORIGIN_CHANGE,
)
FREE_ORIGINS = (ORIGIN_WORKSHOP, ORIGIN_CLOSING, ORIGIN_DIRECT)
LESSON_ORIGINS = (*MODULE_ORIGINS, *FREE_ORIGINS)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join("'" + value.replace("'", "''") + "'" for value in values)
    return f"{column} IN ({quoted})"


class Lesson(Base):
    """Lição aprendida: origem rastreável, classificação, causa, impactos e a situação do fluxo."""

    __tablename__ = "licao"
    __table_args__ = (
        CheckConstraint(_in_list("tipo", LESSON_TYPES), name="tipo"),
        CheckConstraint(_in_list("fase", LESSON_PHASES), name="fase"),
        CheckConstraint(_in_list("area", LESSON_AREAS), name="area"),
        CheckConstraint(_in_list("origem", LESSON_ORIGINS), name="origem"),
        CheckConstraint(_in_list("aplicabilidade", LESSON_APPLICABILITIES), name="aplicabilidade"),
        CheckConstraint(_in_list("situacao", LESSON_SITUATIONS), name="situacao"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    discipline_id: Mapped[int | None] = mapped_column("disciplina_id", ForeignKey("disciplina.id"))
    author_id: Mapped[int] = mapped_column("autor_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text, unique=True)
    title: Mapped[str] = mapped_column("titulo", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    phase: Mapped[str] = mapped_column("fase", Text)
    area: Mapped[str] = mapped_column("area", Text)
    origin: Mapped[str] = mapped_column("origem", Text)
    origin_ref: Mapped[str | None] = mapped_column("origem_ref", Text)
    what_happened: Mapped[str] = mapped_column("aconteceu", Text)
    cause: Mapped[str] = mapped_column("causa", Text)
    term_impact_days: Mapped[int] = mapped_column("impacto_prazo_dias", Integer)
    cost_impact_cents: Mapped[int] = mapped_column("impacto_custo_centavos", Centavos)
    recommendation: Mapped[str] = mapped_column("recomendacao", Text)
    applicability: Mapped[str] = mapped_column("aplicabilidade", Text)
    situation: Mapped[str] = mapped_column("situacao", Text)
    registered_on: Mapped[date] = mapped_column("data", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class LessonKeyword(Base):
    """Palavra-chave da lição, para a busca do acervo (fato sem ``versao``)."""

    __tablename__ = "licao_palavra_chave"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lesson_id: Mapped[int] = mapped_column("licao_id", ForeignKey("licao.id"))
    word: Mapped[str] = mapped_column("palavra", Text)


class LessonApplication(Base):
    """Cada reuso registrado: projeto, data, como, e a ação da Central ou o risco gerados."""

    __tablename__ = "licao_aplicacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lesson_id: Mapped[int] = mapped_column("licao_id", ForeignKey("licao.id"))
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    action_id: Mapped[int | None] = mapped_column("acao_id", ForeignKey("acao.id"))
    risk_id: Mapped[int | None] = mapped_column("risco_id", BigInteger)
    registered_by_id: Mapped[int] = mapped_column("registrado_por_id", ForeignKey("pessoa.id"))
    applied_on: Mapped[date] = mapped_column("data", Date)
    how: Mapped[str] = mapped_column("como", Text)


class LessonHistory(Base):
    """Linha do histórico da lição: quem fez o quê e quando, com o comentário da devolução (fato)."""

    __tablename__ = "licao_historico"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lesson_id: Mapped[int] = mapped_column("licao_id", ForeignKey("licao.id"))
    person_id: Mapped[int] = mapped_column("pessoa_id", ForeignKey("pessoa.id"))
    moment: Mapped[datetime] = mapped_column("data_hora", DateTime(timezone=True))
    text: Mapped[str] = mapped_column("texto", Text)
