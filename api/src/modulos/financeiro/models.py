"""Persistence models of the Financeiro module (D5).

Class and attribute names are English (D1); tables and columns are Portuguese snake_case,
as in ``docs/MODELO-DE-DADOS.md``. This module owns the cost breakdown item, its revisions with
the frozen baseline of each item, the reallocations applied to it (ISSUE-029, ISSUE-030), the
projection history of the item and the costs imported from the ERP (ISSUE-031), the contract
with its addenda and measurements (ISSUE-032), its payment milestones, claims and time
extensions (ISSUE-033), the contractor performance evaluation with its frozen criteria
(ISSUE-034), and the contingency and management reserves with their movement statement
(ISSUE-041).
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
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import VERSION_SERVER_DEFAULT, Base
from src.core.money import Centavos


class EacItem(Base):
    """Item of the Estrutura Analítica de Custos, in three levels (package, subpackage, item).

    No aggregated value is a column (D5b): the budgeted value of an item is its quantity times
    its unit price, and the totals of the packages are sums made by the facade.
    """

    __tablename__ = "eac_item"
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    parent_id: Mapped[int | None] = mapped_column("pai_id", ForeignKey("eac_item.id"))
    unit_id: Mapped[int | None] = mapped_column("unidade_id", ForeignKey("unidade.id"))
    responsible_id: Mapped[int | None] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    level: Mapped[int] = mapped_column("nivel", Integer)
    cost_type: Mapped[str | None] = mapped_column("tipo_custo", Text)
    quantity: Mapped[Decimal | None] = mapped_column("quantidade", Numeric(18, 4))
    unit_price_cents: Mapped[int | None] = mapped_column("preco_unitario_centavos", Centavos)
    capex: Mapped[bool | None] = mapped_column("capex", Boolean)
    cost_center: Mapped[str | None] = mapped_column("centro_custo", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class EacRevision(Base):
    """Revisão da EAC: Rev 0 é a linha de base; a revisão seguinte consolida remanejamentos e SM.

    O total não é coluna: é a soma das linhas de ``eac_revisao_item`` da revisão (D5b). A SM de
    origem é opcional no banco para a carga e para a linha de base, que nasce sem mudança.
    """

    __tablename__ = "eac_revisao"
    __table_args__ = (UniqueConstraint("projeto_id", "revisao"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    approved_by_id: Mapped[int] = mapped_column("aprovado_por_id", ForeignKey("pessoa.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    revision_date: Mapped[date] = mapped_column("data", Date)
    justification: Mapped[str] = mapped_column("justificativa", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class EacRevisionItem(Base):
    """Linha de base congelada de um item em uma revisão, em centavos.

    Fato histórico por definição (D5b): é o que permite comparar revisões depois. Sem ``versao``.
    """

    __tablename__ = "eac_revisao_item"
    __table_args__ = (UniqueConstraint("revisao_id", "item_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column("revisao_id", ForeignKey("eac_revisao.id"))
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eac_item.id"))
    base_cents: Mapped[int] = mapped_column("base_centavos", Centavos)


class EacReallocation(Base):
    """Remanejamento aplicado na EAC: origem, destino, valor, autor, SM e a revisão que consolida.

    A linha nasce na aprovação da SM (ISSUE-030); enquanto ela não é consolidada por uma revisão,
    ``revisao`` aponta para a próxima revisão (a que a consolidará). Fato imutável, sem ``versao``.
    """

    __tablename__ = "eac_remanejamento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    source_item_id: Mapped[int] = mapped_column("origem_item_id", ForeignKey("eac_item.id"))
    target_item_id: Mapped[int] = mapped_column("destino_item_id", ForeignKey("eac_item.id"))
    applied_by_id: Mapped[int] = mapped_column("por_id", ForeignKey("pessoa.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    applied_on: Mapped[date] = mapped_column("data", Date)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    new_item: Mapped[bool] = mapped_column("novo_item", Boolean, server_default=text("false"))
    justification: Mapped[str | None] = mapped_column("justificativa", Text)


class EacProjection(Base):
    """Projeção no término de um item, com a justificativa e quem a informou (ISSUE-031).

    A projeção vigente é a última linha do item; ``origem`` diz se ela veio do responsável ou do
    fechamento do ERP. Fato histórico por definição (D5b): sem ``versao``.
    """

    __tablename__ = "eac_projecao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eac_item.id"))
    author_id: Mapped[int] = mapped_column("autor_id", ForeignKey("pessoa.id"))
    projected_on: Mapped[date] = mapped_column("data", Date)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    origin: Mapped[str] = mapped_column("origem", Text)
    justification: Mapped[str] = mapped_column("justificativa", Text)


class ErpCost(Base):
    """Custos do ERP de um item em um mês: comprometido, realizado e projeção do fechamento.

    Fato mensal por item e mês (ISSUE-031), sem ``versao``; alimenta o mapa de controle e a
    Curva S financeira. Um mês reimportado atualiza a linha, nunca a duplica.
    """

    __tablename__ = "custo_erp"
    __table_args__ = (UniqueConstraint("item_id", "mes"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eac_item.id"))
    imported_by_id: Mapped[int] = mapped_column("importado_por_id", ForeignKey("pessoa.id"))
    month: Mapped[date] = mapped_column("mes", Date)
    committed_cents: Mapped[int | None] = mapped_column("comprometido_centavos", Centavos)
    actual_cents: Mapped[int | None] = mapped_column("realizado_centavos", Centavos)
    projection_cents: Mapped[int | None] = mapped_column("projecao_centavos", Centavos)
    imported_at: Mapped[datetime] = mapped_column(
        "importado_em", DateTime(timezone=True), server_default=func.now()
    )


class Reserve(Base):
    """Reserva de contingência ou gerencial do projeto, uma por tipo, com a base de cálculo.

    O saldo não é coluna (D5b): é a soma dos movimentos de ``reserva_movimento``. UK: projeto
    + tipo. A reserva de contingência integra a linha de base de custo; a gerencial fica fora
    dela e só o Comitê a libera (ISSUE-041).
    """

    __tablename__ = "reserva"
    __table_args__ = (UniqueConstraint("projeto_id", "tipo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    kind: Mapped[str] = mapped_column("tipo", Text)
    calculation_basis: Mapped[str] = mapped_column("base_calculo", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ReserveMovement(Base):
    """Movimento do extrato da reserva: constituição, consumo por SM aprovada ou liberação.

    Fato imutável, sem ``versao`` (D5b). O valor é assinado: a constituição entra positiva e o
    consumo e a liberação, negativos, de modo que o saldo é a soma dos movimentos. A SM de origem
    é opcional no banco porque a constituição nasce sem mudança.
    """

    __tablename__ = "reserva_movimento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reserve_id: Mapped[int] = mapped_column("reserva_id", ForeignKey("reserva.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    registered_by_id: Mapped[int] = mapped_column("registrado_por_id", ForeignKey("pessoa.id"))
    kind: Mapped[str] = mapped_column("tipo", Text)
    registered_on: Mapped[date] = mapped_column("data", Date)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    justification: Mapped[str] = mapped_column("justificativa", Text)


class Contract(Base):
    """Contrato da administração contratual: valor original, datas, retenção e prazos.

    ``pacote_compra_id`` entra como coluna sem chave estrangeira: a ``pacote_compra`` só nasce na
    ISSUE-058/060, que acrescenta a chave (D9). Valor atual, medido e saldo são calculados.
    """

    __tablename__ = "contrato"
    __table_args__ = (UniqueConstraint("numero"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    eac_item_id: Mapped[int | None] = mapped_column("eac_item_id", ForeignKey("eac_item.id"))
    purchase_package_id: Mapped[int | None] = mapped_column("pacote_compra_id", BigInteger)
    manager_id: Mapped[int] = mapped_column("gestor_id", ForeignKey("pessoa.id"))
    fiscal_id: Mapped[int] = mapped_column("fiscal_id", ForeignKey("pessoa.id"))
    number: Mapped[str] = mapped_column("numero", Text)
    object: Mapped[str] = mapped_column("objeto", Text)
    modality: Mapped[str] = mapped_column("modalidade", Text)
    original_value_cents: Mapped[int] = mapped_column("valor_original_centavos", Centavos)
    start: Mapped[date] = mapped_column("inicio", Date)
    original_end: Mapped[date] = mapped_column("termino_original", Date)
    current_end: Mapped[date] = mapped_column("termino_vigente", Date)
    retention_pct: Mapped[int] = mapped_column("retencao_pct", Integer)
    claim_notice_days: Mapped[int] = mapped_column("prazo_notificacao_claim_dias", Integer)
    situation: Mapped[str] = mapped_column("situacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ContractAddendum(Base):
    """Aditivo do contrato: valor e/ou dias, com motivo, SM e claim de origem.

    Fato imutável (D5b): sem ``versao``. O aditivo é aprovado ao ser registrado: soma ao valor
    atual e, quando tem dias, prorroga o término vigente.
    """

    __tablename__ = "contrato_aditivo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column("contrato_id", ForeignKey("contrato.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    claim_id: Mapped[int | None] = mapped_column("claim_id", ForeignKey("contrato_claim.id"))
    number: Mapped[str] = mapped_column("numero", Text)
    signed_on: Mapped[date] = mapped_column("data", Date)
    value_cents: Mapped[int] = mapped_column("valor_centavos", Centavos)
    days: Mapped[int] = mapped_column("dias", Integer)
    reason: Mapped[str] = mapped_column("motivo", Text)


class ContractMeasurement(Base):
    """Boletim de medição do contrato: período, valor bruto e a situação do fluxo.

    Retenção e líquido são calculados pela retenção do contrato; o marco vinculado é opcional.
    """

    __tablename__ = "contrato_medicao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column("contrato_id", ForeignKey("contrato.id"))
    milestone_id: Mapped[int | None] = mapped_column(
        "marco_id", ForeignKey("contrato_marco_pagamento.id")
    )
    number: Mapped[str] = mapped_column("numero", Text)
    period: Mapped[date] = mapped_column("periodo", Date)
    gross_cents: Mapped[int] = mapped_column("bruto_centavos", Centavos)
    situation: Mapped[str] = mapped_column("situacao", Text)
    return_reason: Mapped[str | None] = mapped_column("motivo_devolucao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ContractPaymentMilestone(Base):
    """Marco de pagamento: percentual do valor vigente, critério de aceite e evidência da aprovação.

    O valor e a retenção não são coluna: saem do percentual sobre o valor atual do contrato (D5b).
    A aprovação exige um ``anexo`` de evidência, guardado em ``anexo_id``.
    """

    __tablename__ = "contrato_marco_pagamento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column("contrato_id", ForeignKey("contrato.id"))
    attachment_id: Mapped[int | None] = mapped_column("anexo_id", ForeignKey("anexo.id"))
    number: Mapped[str] = mapped_column("numero", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    acceptance_criteria: Mapped[str] = mapped_column("criterio", Text)
    pct: Mapped[int] = mapped_column("pct", Integer)
    expected_on: Mapped[date] = mapped_column("data_prevista", Date)
    completed_on: Mapped[date | None] = mapped_column("data_conclusao", Date)
    situation: Mapped[str] = mapped_column("situacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ContractClaim(Base):
    """Pleito do contrato: direção, tipo, causa, datas, valores e dias pleiteados/reconhecidos.

    Exposição e taxa de reconhecimento são calculadas; o alerta de notificação fora do prazo
    compara a data da notificação com o prazo do contrato. O risco e a SM de origem entram por
    chave estrangeira opcional.
    """

    __tablename__ = "contrato_claim"
    __table_args__ = (UniqueConstraint("codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column("contrato_id", ForeignKey("contrato.id"))
    risk_id: Mapped[int | None] = mapped_column("risco_id", ForeignKey("risco.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    direction: Mapped[str] = mapped_column("direcao", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    cause: Mapped[str] = mapped_column("causa", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    clause: Mapped[str | None] = mapped_column("clausula", Text)
    event_date: Mapped[date] = mapped_column("data_evento", Date)
    notification_date: Mapped[date] = mapped_column("data_notificacao", Date)
    claimed_cents: Mapped[int] = mapped_column("pleiteado_centavos", Centavos)
    claimed_days: Mapped[int] = mapped_column("dias_pleiteados", Integer)
    recognized_cents: Mapped[int | None] = mapped_column("reconhecido_centavos", Centavos)
    recognized_days: Mapped[int | None] = mapped_column("dias_reconhecidos", Integer)
    situation: Mapped[str] = mapped_column("situacao", Text)
    closed_on: Mapped[date | None] = mapped_column("data_encerramento", Date)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ContractTimeExtension(Base):
    """Extensão de prazo (EOT): claim de origem, evento, dias, classificação e decisão.

    A concessão prorroga o término vigente do contrato e cria a SM do cronograma na mesma
    transação; o vínculo com a SM fica em ``mudanca_id``. Dias, classificação e decisão são
    nulos enquanto a EOT está pendente.
    """

    __tablename__ = "contrato_extensao_prazo"
    __table_args__ = (UniqueConstraint("codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column("contrato_id", ForeignKey("contrato.id"))
    claim_id: Mapped[int | None] = mapped_column("claim_id", ForeignKey("contrato_claim.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    event: Mapped[str] = mapped_column("evento", Text)
    requested_days: Mapped[int] = mapped_column("dias_solicitados", Integer)
    granted_days: Mapped[int | None] = mapped_column("dias_concedidos", Integer)
    classification: Mapped[str | None] = mapped_column("classificacao", Text)
    method: Mapped[str] = mapped_column("metodo", Text)
    affected_milestone: Mapped[str] = mapped_column("marco_afetado", Text)
    requested_on: Mapped[date] = mapped_column("data_solicitacao", Date)
    decided_on: Mapped[date | None] = mapped_column("data_decisao", Date)
    situation: Mapped[str] = mapped_column("situacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ContractEvaluation(Base):
    """Contractor performance evaluation: monthly during execution or final at closing.

    The weighted score and the class are not columns: they come from the notes and the weights
    frozen in the criteria (D5b, the contractor evaluation exception). ``parametro_versao_id``
    records the parameter version in force when the evaluation was made.
    """

    __tablename__ = "contrato_avaliacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column("contrato_id", ForeignKey("contrato.id"))
    evaluator_id: Mapped[int] = mapped_column("avaliador_id", ForeignKey("pessoa.id"))
    parameter_version_id: Mapped[int] = mapped_column(
        "parametro_versao_id", ForeignKey("parametro_versao.id")
    )
    period: Mapped[date] = mapped_column("periodo", Date)
    kind: Mapped[str] = mapped_column("tipo", Text)
    comment: Mapped[str | None] = mapped_column("comentario", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class ContractEvaluationCriterion(Base):
    """Weight and note of each criterion, frozen in the evaluation (D5b exception).

    The evaluation does not change when the parameter weights change: the frozen weight is the
    one in force on the date it was made. UK: evaluation + criterion. Without ``versao``.
    """

    __tablename__ = "contrato_avaliacao_criterio"
    __table_args__ = (UniqueConstraint("avaliacao_id", "criterio"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column("avaliacao_id", ForeignKey("contrato_avaliacao.id"))
    criterion: Mapped[str] = mapped_column("criterio", Text)
    weight: Mapped[int] = mapped_column("peso", Integer)
    note: Mapped[int] = mapped_column("nota", Integer)
