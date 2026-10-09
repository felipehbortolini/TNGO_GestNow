"""Persistence models of the Procurement module: suppliers and the purchase plan (ISSUE-057/058).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case (D5),
exactly as in ``docs/MODELO-DE-DADOS.md``. ``fornecedor`` is the qualification of a company of
the register (``empresa``), not of a project: the cadastro is global, as the companies and the
people of Configurações are. Documents in day, performance and contracted value are never
columns: they are calculated on every read (D6) from the documents, from the evaluations of the
Financeiro and from its facade.

``pacote_compra`` is the package of the plan: a project link, an item of level 3 of the EAC, a
buyer, a discipline, the scope and the data of the contracting strategy. The three layers of
each acquisition milestone (plan/LB, forecast and real) live in the same row of
``pacote_compra_marco`` (ISSUE-004 decision); the history travels in the audit trail. Stage,
slack and adjudicated are never columns: they are calculated on every read from the milestones and
from the registros of the process (ISSUE-059) and of the order (ISSUE-061).

The purchase process (ISSUE-059) is the RFx of a package: its number, the technical and
commercial weights, the deadline of the proposals and the fields of the recommendation and of the
approval, which ISSUE-060 fills. The invited companies, the proposals and the negotiations are
separate rows; a supplier outside the register is kept by ``nome`` (the prototype accepted free
names), with ``empresa_id`` empty. Commercial and final scores, the ranking and the saving are
never columns: they are calculated on every read from the proposals, the weights and the
parameters in force. The history of the process travels in the audit trail.

``pedido`` is the purchase order the emission of an equipment/material process creates: the
package it came from, the supplier, the value and the dates of the contract. Its six
manufacturing milestones (``pedido_marco``) carry the contractual baseline, the forecast and the
real date in the same row (ISSUE-004 decision), exactly as the acquisition milestones of the
package do; slack, situation and OTD are never columns (ISSUE-061). The contract of a service/EPC
process is born in the Financeiro (``contrato.pacote_compra_id``, D9).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base
from src.core.money import Centavos


class Supplier(Base):
    """Qualificação de uma empresa do cadastro: situação, validade e observação (UK: empresa)."""

    __tablename__ = "fornecedor"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"), unique=True)
    situation: Mapped[str] = mapped_column("situacao", Text)
    validity: Mapped[date | None] = mapped_column("validade_qualificacao", Date)
    observation: Mapped[str | None] = mapped_column("observacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class SupplierCategory(Base):
    """Categoria de atuação da empresa qualificada. Sem ``versao`` própria."""

    __tablename__ = "fornecedor_categoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column("fornecedor_id", ForeignKey("fornecedor.id"))
    category: Mapped[str] = mapped_column("categoria", Text)


class SupplierDocument(Base):
    """Documento com validade do fornecedor; o arquivo é um ``anexo`` (D5a)."""

    __tablename__ = "fornecedor_documento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column("fornecedor_id", ForeignKey("fornecedor.id"))
    name: Mapped[str] = mapped_column("nome", Text)
    validity: Mapped[date | None] = mapped_column("validade", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class SupplierHistory(Base):
    """Mudança de situação da qualificação (de, para, autor e justificativa). Fato imutável."""

    __tablename__ = "fornecedor_historico"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column("fornecedor_id", ForeignKey("fornecedor.id"))
    by_id: Mapped[int] = mapped_column("por_id", ForeignKey("pessoa.id"))
    on: Mapped[date] = mapped_column("data", Date)
    from_situation: Mapped[str | None] = mapped_column("de", Text)
    to_situation: Mapped[str] = mapped_column("para", Text)
    justification: Mapped[str] = mapped_column("justificativa", Text)


class PurchasePackage(Base):
    """Pacote do plano de compras, ligado a um item da EAC do projeto (UK: projeto + código).

    O comprador vem do cadastro de pessoas e a disciplina do cadastro de disciplinas
    (Configurações). A LB fica congelada a partir da requisição com data real; depois disso só
    escopo, comprador, estimativa e ROS mudam, com justificativa na trilha.
    """

    __tablename__ = "pacote_compra"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    eac_item_id: Mapped[int] = mapped_column("eac_item_id", ForeignKey("eac_item.id"))
    buyer_id: Mapped[int] = mapped_column("comprador_id", ForeignKey("pessoa.id"))
    discipline_id: Mapped[int | None] = mapped_column("disciplina_id", ForeignKey("disciplina.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    scope: Mapped[str] = mapped_column("escopo", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    modality: Mapped[str] = mapped_column("modalidade", Text)
    lli: Mapped[bool] = mapped_column("lli", Boolean)
    estimate_cents: Mapped[int] = mapped_column("estimativa_centavos", Centavos)
    ros: Mapped[date] = mapped_column("ros", Date)
    emergency: Mapped[bool] = mapped_column("emergencial", Boolean)
    gate_lli_date: Mapped[date | None] = mapped_column("gate_lli_data", Date)
    gate_lli_reference: Mapped[str | None] = mapped_column("gate_lli_referencia", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)


class PurchaseProcess(Base):
    """Processo de compra (RFx) de um pacote, com o número único (ISSUE-059).

    Os pesos e a data-limite vêm da emissão da RFx; a recomendação e a aprovação são preenchidas
    pela ISSUE-060. Notas, ranking e saving não têm coluna: são calculados na leitura.
    """

    __tablename__ = "processo_compra"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column("pacote_id", ForeignKey("pacote_compra.id"))
    number: Mapped[str] = mapped_column("numero", Text, unique=True)
    weight_technical: Mapped[int] = mapped_column("peso_tecnico", Integer)
    weight_commercial: Mapped[int] = mapped_column("peso_comercial", Integer)
    proposals_deadline: Mapped[date] = mapped_column("data_limite_propostas", Date)
    recommendation_on: Mapped[date | None] = mapped_column("recomendacao_em", Date)
    recommendation_company_id: Mapped[int | None] = mapped_column(
        "recomendacao_fornecedor_id", ForeignKey("empresa.id")
    )
    recommendation_value_cents: Mapped[int | None] = mapped_column(
        "recomendacao_valor_centavos", Centavos
    )
    recommendation_by_id: Mapped[int | None] = mapped_column(
        "recomendacao_por_id", ForeignKey("pessoa.id")
    )
    recommendation_justification: Mapped[str | None] = mapped_column(
        "recomendacao_justificativa", Text
    )
    approval_on: Mapped[date | None] = mapped_column("aprovacao_em", Date)
    approval_by_id: Mapped[int | None] = mapped_column("aprovacao_por_id", ForeignKey("pessoa.id"))
    approval_band: Mapped[str | None] = mapped_column("aprovacao_alcada", Text)
    approval_opinion: Mapped[str | None] = mapped_column("aprovacao_parecer", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ProcessInvitee(Base):
    """Fornecedor convidado da RFx; sem cadastro, o ``nome`` fica no lugar da empresa."""

    __tablename__ = "processo_convidado"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    process_id: Mapped[int] = mapped_column("processo_id", ForeignKey("processo_compra.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    name: Mapped[str | None] = mapped_column("nome", Text)


class ProcessProposal(Base):
    """Proposta recebida; o PDF é um ``anexo`` do registro (D5a)."""

    __tablename__ = "processo_proposta"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    process_id: Mapped[int] = mapped_column("processo_id", ForeignKey("processo_compra.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    name: Mapped[str | None] = mapped_column("nome", Text)
    received: Mapped[date] = mapped_column("recebida", Date)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    deadline_days: Mapped[int] = mapped_column("prazo_dias", Integer)
    validity: Mapped[date | None] = mapped_column("validade", Date)
    technical_score: Mapped[int | None] = mapped_column("nota_tecnica", Integer)
    technically_approved: Mapped[bool | None] = mapped_column("tecnicamente_aprovada", Boolean)
    deviations: Mapped[str | None] = mapped_column("desvios", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ProcessNegotiation(Base):
    """Rodada de negociação: fato imutável, sem ``versao`` própria."""

    __tablename__ = "processo_negociacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    process_id: Mapped[int] = mapped_column("processo_id", ForeignKey("processo_compra.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    name: Mapped[str | None] = mapped_column("nome", Text)
    on: Mapped[date] = mapped_column("data", Date)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    observation: Mapped[str | None] = mapped_column("observacao", Text)


class PackageMilestone(Base):
    """Marco de aquisição do pacote com as três camadas na mesma linha (UK: pacote + marco).

    ``data_plano`` é a LB congelada, ``data_previsao`` a previsão e ``data_real`` o realizado;
    cada mudança passa por ``core.recording``, com o antes/depois na trilha (ISSUE-004).
    """

    __tablename__ = "pacote_compra_marco"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column("pacote_id", ForeignKey("pacote_compra.id"))
    milestone: Mapped[str] = mapped_column("marco", Text)
    plan_date: Mapped[date | None] = mapped_column("data_plano", Date)
    forecast_date: Mapped[date | None] = mapped_column("data_previsao", Date)
    real_date: Mapped[date | None] = mapped_column("data_real", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    __table_args__ = (UniqueConstraint("pacote_id", "marco"),)


class PurchaseOrder(Base):
    """Pedido de compra emitido na adjudicação de um equipamento/material (UK: número).

    O pedido nasce do processo aprovado e aponta o pacote (``pacote_id``) e o fornecedor
    (``empresa_id``); o valor e as datas vêm da recomendação e do prazo da proposta. A folga, a
    situação e o OTD não são colunas: são calculados na leitura (ISSUE-061).
    """

    __tablename__ = "pedido"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    package_id: Mapped[int] = mapped_column("pacote_id", ForeignKey("pacote_compra.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    number: Mapped[str] = mapped_column("numero", Text, unique=True)
    description: Mapped[str] = mapped_column("descricao", Text)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    lli: Mapped[bool] = mapped_column("lli", Boolean)
    emission: Mapped[date] = mapped_column("emissao", Date)
    contractual_date: Mapped[date] = mapped_column("data_contratual", Date)
    forecast: Mapped[date] = mapped_column("previsao", Date)
    ros: Mapped[date] = mapped_column("ros", Date)
    delivery: Mapped[date | None] = mapped_column("entrega", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class PurchaseOrderMilestone(Base):
    """Marco de fabricação do pedido com as três camadas na mesma linha (UK: pedido + ordem).

    ``ordem`` guarda a posição do marco no cronograma padrão (1 a 6); o desvio e a situação são
    calculados na leitura (ISSUE-061).
    """

    __tablename__ = "pedido_marco"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column("pedido_id", ForeignKey("pedido.id"))
    position: Mapped[int] = mapped_column("ordem", Integer)
    name: Mapped[str] = mapped_column("nome", Text)
    baseline_date: Mapped[date | None] = mapped_column("data_lb", Date)
    forecast_date: Mapped[date | None] = mapped_column("data_previsao", Date)
    real_date: Mapped[date | None] = mapped_column("data_realizada", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    __table_args__ = (UniqueConstraint("pedido_id", "ordem"),)
