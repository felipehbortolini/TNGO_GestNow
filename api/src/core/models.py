"""Platform persistence models: clients, numbering, audit, attachments and notifications.

Class and attribute names are English (D1); tables and columns are Portuguese
snake_case (D5), matching ``docs/MODELO-DE-DADOS.md``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ACTIVE_SERVER_DEFAULT, VERSION_SERVER_DEFAULT, Base


class Client(Base):
    """Cliente do projeto (nome, sigla, ativo)."""

    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nome", Text)
    acronym: Mapped[str | None] = mapped_column("sigla", Text)
    active: Mapped[bool] = mapped_column("ativo", Boolean, server_default=ACTIVE_SERVER_DEFAULT)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class NumberingSequence(Base):
    """Próximo número por projeto e tipo, travado por linha na transação."""

    __tablename__ = "sequencia_numeracao"
    __table_args__ = (UniqueConstraint("projeto_id", "tipo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    kind: Mapped[str] = mapped_column("tipo", Text)
    next_value: Mapped[int] = mapped_column("proximo_valor", BigInteger)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class SeedRun(Base):
    """Parte da carga de demonstração já aplicada; rodar de novo não duplica (ISSUE-008)."""

    __tablename__ = "carga_demonstracao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nome", Text, unique=True)
    executed_at: Mapped[datetime] = mapped_column(
        "executada_em", DateTime(timezone=True), server_default=func.now()
    )


class AuditEntry(Base):
    """Trilha de auditoria só de inclusão, gravada na transação da mudança."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    user_id: Mapped[int] = mapped_column("usuario_id", ForeignKey("colaborador.id"))
    occurred_at: Mapped[datetime] = mapped_column("data_hora", DateTime(timezone=True))
    entity: Mapped[str] = mapped_column("entidade", Text)
    record_id: Mapped[int] = mapped_column("registro_id", BigInteger)
    action: Mapped[str] = mapped_column("acao", Text)
    before: Mapped[dict[str, Any] | None] = mapped_column("antes", JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column("depois", JSONB)


class Attachment(Base):
    """Metadados do arquivo e o registro de origem (D5a)."""

    __tablename__ = "anexo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    uploaded_by_id: Mapped[int] = mapped_column("enviado_por_id", ForeignKey("colaborador.id"))
    name: Mapped[str] = mapped_column("nome", Text)
    mime_type: Mapped[str] = mapped_column("tipo_mime", Text)
    size_bytes: Mapped[int] = mapped_column("tamanho_bytes", BigInteger)
    file_hash: Mapped[str] = mapped_column("hash", Text)
    origin_table: Mapped[str] = mapped_column("origem_tabela", Text)
    origin_record_id: Mapped[int] = mapped_column("origem_registro_id", BigInteger)
    uploaded_at: Mapped[datetime] = mapped_column(
        "enviado_em", DateTime(timezone=True), server_default=func.now()
    )


class Notification(Base):
    """Registro de envio (follow-up, pauta, tesouraria) e a referência ao registro."""

    __tablename__ = "notificacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    originated_by_id: Mapped[int] = mapped_column("originado_por_id", ForeignKey("colaborador.id"))
    kind: Mapped[str] = mapped_column("tipo", Text)
    channel: Mapped[str] = mapped_column("canal", Text)
    recipients: Mapped[str] = mapped_column("destinatarios", Text)
    subject: Mapped[str] = mapped_column("assunto", Text)
    body: Mapped[str] = mapped_column("corpo", Text)
    situation: Mapped[str] = mapped_column("situacao", Text)
    reference_entity: Mapped[str | None] = mapped_column("referencia_entidade", Text)
    reference_record_id: Mapped[int | None] = mapped_column("referencia_registro_id", BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        "criado_em", DateTime(timezone=True), server_default=func.now()
    )
