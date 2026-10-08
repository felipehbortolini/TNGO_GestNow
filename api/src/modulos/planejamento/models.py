"""Persistence models for the Planning module.

Class and attribute names are English (D1); tables and columns are Portuguese snake_case
(D5), matching ``docs/MODELO-DE-DADOS.md``.

Relato do período (ISSUE-044): one ``relato`` per project, type and period; its activities
(``relato_atividade``) and attention points (``relato_ponto``) are the children of the
aggregate and are edited together with it, protected by the ``versao`` of the root.


The 6WLA (ISSUE-045): the activities of the six-week horizon, the mark of each
week and the restrictions that hold an activity back. Class and attribute names
are English (D1); tables and columns are Portuguese snake_case (D5), matching
``docs/MODELO-DE-DADOS.md``.

The WBS (ISSUE-036): the three-level breakdown, its baseline revisions with the
frozen weight of each package, the breakdown of a planning package and the dated
measurements. The entries of the measuring criterion (``executado``, ``estado``,
``estimado_pct`` and the ``pct`` of each step) are the current state of the
package; the real progress is calculated from them (D5b).

The physical S-curve (ISSUE-039): the baseline generated from the EAP revision
and frozen in its own revision (the D5b exception), with the percentage of each
month. The real comes from the dated measurements and the trend is calculated.

The productivity (ISSUE-046): the quantity plan of the baseline per company and
item (``produtividade_item``), the frozen total of each revision of the baseline
(``produtividade_revisao``), the weekly distribution of the revision
(``produtividade_distribuicao``) and the weekly report of the contractor
(``produtividade_apontamento``). The last three are the D5b exception: they keep
the frozen fact and have no ``versao`` of their own. The item carries the week
bounds as dates (Monday of the ISO week); the distribution and the report carry
the week label in text.

The field hours (ISSUE-047): the daily shift of the foreman front
(``jornada_campo``), the observation round of the work sampling
(``amostragem``) with its stop and transit reasons (``amostragem_motivo``) and
the stoppage of crew or machine (``paralisacao``). The foreman is the text the
inspector types, as in the prototype (``encarregado``), not a person register.
The capacity, the percentages, the Pareto, the Hhora and the Mhora are all
calculated; the reasons of a round enter and leave with it and have no
``versao`` of their own.
"""

from __future__ import annotations

from datetime import date, datetime, time
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
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import VERSION_SERVER_DEFAULT, Base

Quantity = Numeric(18, 4)

Percent = Numeric(7, 2)


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


class EapItem(Base):
    """Item da EAP em três níveis: área, subárea e pacote de trabalho ou de planejamento.

    As entradas do critério de medição (``executado``, ``estado``, ``estimado_pct`` e o ``pct``
    de cada etapa) são o estado corrente do pacote; o real é calculado delas (D5b). UK: projeto
    + código.
    """

    __tablename__ = "eap_item"
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    parent_id: Mapped[int | None] = mapped_column("pai_id", ForeignKey("eap_item.id"))
    eac_item_id: Mapped[int | None] = mapped_column("eac_item_id", ForeignKey("eac_item.id"))
    unit_id: Mapped[int | None] = mapped_column("unidade_id", ForeignKey("unidade.id"))
    company_id: Mapped[int | None] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    owner_id: Mapped[int | None] = mapped_column("responsavel_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    description: Mapped[str] = mapped_column("descricao", Text)
    level: Mapped[int] = mapped_column("nivel", Integer)
    kind: Mapped[str | None] = mapped_column("tipo", Text)
    criterion: Mapped[str | None] = mapped_column("criterio", Text)
    model: Mapped[str | None] = mapped_column("modelo", Text)
    quantity: Mapped[Decimal | None] = mapped_column("quantidade", Quantity)
    executed: Mapped[Decimal | None] = mapped_column("executado", Quantity)
    state: Mapped[str | None] = mapped_column("estado", Text)
    estimated_pct: Mapped[Decimal | None] = mapped_column("estimado_pct", Percent)
    weight: Mapped[Decimal | None] = mapped_column("peso", Percent)
    predicted: Mapped[Decimal | None] = mapped_column("previsto", Percent)
    start: Mapped[date | None] = mapped_column("inicio", Date)
    finish: Mapped[date | None] = mapped_column("termino", Date)
    deliverable: Mapped[str | None] = mapped_column("entregavel", Text)
    acceptance: Mapped[str | None] = mapped_column("aceitacao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class EapItemStep(Base):
    """Etapa do pacote no critério Etapas: ordem, nome, peso e o % concluído corrente.

    Instanciada do modelo de etapas dos parâmetros. Sem ``versao``: protegida pela versão do item.
    """

    __tablename__ = "eap_item_etapa"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eap_item.id"))
    order: Mapped[int] = mapped_column("ordem", Integer)
    name: Mapped[str] = mapped_column("nome", Text)
    weight: Mapped[Decimal] = mapped_column("peso", Percent)
    pct: Mapped[Decimal] = mapped_column("pct", Percent, server_default=text("0"))


class EapMeasurement(Base):
    """Medição do pacote: de qual avanço para qual, na data, com autor e observação.

    Fato imutável (D5b), sem ``versao``; o estado corrente do critério fica no item e nas etapas.
    """

    __tablename__ = "eap_medicao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eap_item.id"))
    author_id: Mapped[int] = mapped_column("autor_id", ForeignKey("pessoa.id"))
    measured_on: Mapped[date] = mapped_column("data", Date)
    from_pct: Mapped[Decimal] = mapped_column("de", Percent)
    to_pct: Mapped[Decimal] = mapped_column("para", Percent)
    note: Mapped[str | None] = mapped_column("observacao", Text)


class EapRevision(Base):
    """Revisão da EAP: Rev 0 é a linha de base; a seguinte consolida SM aprovada com escopo.

    A contagem de pacotes não é coluna: sai dos pesos congelados da revisão (D5b).
    UK: projeto + revisão.
    """

    __tablename__ = "eap_revisao"
    __table_args__ = (UniqueConstraint("projeto_id", "revisao"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    approved_by_id: Mapped[int] = mapped_column("aprovado_por_id", ForeignKey("pessoa.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    revision_date: Mapped[date] = mapped_column("data", Date)
    alteration: Mapped[str] = mapped_column("alteracao", Text)
    justification: Mapped[str] = mapped_column("justificativa", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class EapRevisionItem(Base):
    """Peso congelado de um pacote na revisão, para a revisão não mudar (exceção da D5b).

    Fato histórico por definição; sem ``versao``. UK: revisão + item.
    """

    __tablename__ = "eap_revisao_item"
    __table_args__ = (UniqueConstraint("revisao_id", "item_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column("revisao_id", ForeignKey("eap_revisao.id"))
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("eap_item.id"))
    weight: Mapped[Decimal] = mapped_column("peso", Percent)


class EapBreakdown(Base):
    """Desdobramento de pacote de planejamento em pacote de trabalho, sem mudar o total.

    Fato imutável, sem ``versao``: origem, destino, peso, autor, revisão e justificativa.
    """

    __tablename__ = "eap_desdobramento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    source_item_id: Mapped[int] = mapped_column("origem_item_id", ForeignKey("eap_item.id"))
    target_item_id: Mapped[int] = mapped_column("destino_item_id", ForeignKey("eap_item.id"))
    by_id: Mapped[int] = mapped_column("por_id", ForeignKey("pessoa.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    applied_on: Mapped[date] = mapped_column("data", Date)
    weight: Mapped[Decimal] = mapped_column("peso", Percent)
    justification: Mapped[str] = mapped_column("justificativa", Text)


class CurvaFisicaRevision(Base):
    """Linha de base da Curva S física, gerada da revisão vigente da EAP e congelada nela (D5b).

    Fato histórico por definição; sem ``versao``. UK: projeto + revisão da EAP.
    """

    __tablename__ = "curva_fisica_revisao"
    __table_args__ = (UniqueConstraint("projeto_id", "eap_revisao_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    eap_revision_id: Mapped[int] = mapped_column("eap_revisao_id", ForeignKey("eap_revisao.id"))
    generated_at: Mapped[datetime] = mapped_column(
        "gerada_em", DateTime(timezone=True), server_default=func.now()
    )


class CurvaFisicaMonth(Base):
    """Percentual da linha de base da Curva S física em cada mês da revisão (exceção da D5b).

    O real vem das medições da EAP e a tendência é calculada; sem ``versao``. UK: revisão + mês.
    """

    __tablename__ = "curva_fisica_mes"
    __table_args__ = (UniqueConstraint("revisao_id", "mes"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column("revisao_id", ForeignKey("curva_fisica_revisao.id"))
    month: Mapped[date] = mapped_column("mes", Date)
    baseline_pct: Mapped[Decimal] = mapped_column("baseline_pct", Percent)


class ProductivityItem(Base):
    """Item de quantidade da linha de base de uma empresa: o plano que a produtividade controla.

    O total é distribuído por semana pelo perfil (``produtividade_distribuicao``), a situação
    vai de ``Em elaboração`` (editável, fora dos indicadores) a ``Aprovada`` (distribuição
    congelada, D5b) e mudar a linha de base depois disso só por revisão com SM aprovada.
    UK: projeto + código.
    """

    __tablename__ = "produtividade_item"
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    unit_id: Mapped[int | None] = mapped_column("unidade_id", ForeignKey("unidade.id"))
    discipline_id: Mapped[int | None] = mapped_column("disciplina_id", ForeignKey("disciplina.id"))
    approved_by_id: Mapped[int | None] = mapped_column("aprovado_por_id", ForeignKey("pessoa.id"))
    code: Mapped[str] = mapped_column("codigo", Text)
    group: Mapped[str] = mapped_column("grupo", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    places: Mapped[int] = mapped_column("casas", Integer)
    total: Mapped[Decimal] = mapped_column("total", Quantity)
    index_hh: Mapped[Decimal] = mapped_column("indice_hh", Quantity)
    profile: Mapped[str] = mapped_column("perfil", Text)
    situation: Mapped[str] = mapped_column("situacao", Text)
    revision: Mapped[int] = mapped_column("revisao", Integer)
    start: Mapped[date] = mapped_column("inicio", Date)
    finish: Mapped[date] = mapped_column("fim", Date)
    approved_on: Mapped[date | None] = mapped_column("aprovado_em", Date)
    notes: Mapped[str | None] = mapped_column("observacoes", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    revisions: Mapped[list[ProductivityRevision]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ProductivityRevision.revision",
    )
    entries: Mapped[list[ProductivityEntry]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ProductivityEntry.week",
    )


class ProductivityRevision(Base):
    """Total congelado de cada revisão da linha de base de um item (exceção da D5b).

    A revisão 0 é a linha de base original, registrada por quem a elaborou; as seguintes
    consolidam uma SM aprovada e redistribuem o saldo. Sem ``versao``.
    """

    __tablename__ = "produtividade_revisao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("produtividade_item.id"))
    by_id: Mapped[int] = mapped_column("por_id", ForeignKey("pessoa.id"))
    change_id: Mapped[int | None] = mapped_column("mudanca_id", ForeignKey("mudanca.id"))
    revision: Mapped[int] = mapped_column("revisao", Integer)
    revision_date: Mapped[date] = mapped_column("data", Date)
    total: Mapped[Decimal] = mapped_column("total", Quantity)
    previous_total: Mapped[Decimal | None] = mapped_column("total_anterior", Quantity)
    since: Mapped[str | None] = mapped_column("desde", Text)
    justification: Mapped[str] = mapped_column("justificativa", Text)

    item: Mapped[ProductivityItem] = relationship(back_populates="revisions")
    distributions: Mapped[list[ProductivityDistribution]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="ProductivityDistribution.week",
    )


class ProductivityDistribution(Base):
    """Distribuição semanal congelada da linha de base dentro da revisão (exceção da D5b).

    UK: revisão + semana. Sem ``versao``.
    """

    __tablename__ = "produtividade_distribuicao"
    __table_args__ = (UniqueConstraint("revisao_id", "semana"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column("revisao_id", ForeignKey("produtividade_revisao.id"))
    week: Mapped[str] = mapped_column("semana", Text)
    planned: Mapped[Decimal] = mapped_column("previsto", Quantity)

    revision: Mapped[ProductivityRevision] = relationship(back_populates="distributions")


class ProductivityEntry(Base):
    """Apontamento semanal da contratada: realizado e HH apropriadas por item e semana.

    O ``informado_em`` só existe na semana em que a pessoa apontou; as semanas antigas da carga
    ficam sem data. UK: item + semana. Sem ``versao``.
    """

    __tablename__ = "produtividade_apontamento"
    __table_args__ = (UniqueConstraint("item_id", "semana"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column("item_id", ForeignKey("produtividade_item.id"))
    week: Mapped[str] = mapped_column("semana", Text)
    realized: Mapped[Decimal] = mapped_column("realizado", Quantity)
    hh: Mapped[Decimal] = mapped_column("hh", Quantity)
    informed_on: Mapped[date | None] = mapped_column("informado_em", Date)

    item: Mapped[ProductivityItem] = relationship(back_populates="entries")


class FieldDay(Base):
    """Jornada da fiscalização por frente (empresa, área e encarregado) e dia (ISSUE-047).

    Capacidade produtiva, utilização, HH efetivas e HH improdutivas são calculadas dos horários
    dos dois turnos e do efetivo. UK: projeto + data + empresa + área + encarregado (um registro
    por frente e dia, como o protótipo recusa).
    """

    __tablename__ = "jornada_campo"
    __table_args__ = (UniqueConstraint("projeto_id", "data", "empresa_id", "area", "encarregado"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    recorded_by_id: Mapped[int] = mapped_column("registrado_por_id", ForeignKey("pessoa.id"))
    day: Mapped[date] = mapped_column("data", Date)
    area: Mapped[str] = mapped_column("area", Text)
    foreman: Mapped[str] = mapped_column("encarregado", Text)
    crew: Mapped[int] = mapped_column("efetivo", Integer)
    morning_arrival: Mapped[time] = mapped_column("manha_chegada", Time)
    morning_start: Mapped[time] = mapped_column("manha_inicio", Time)
    morning_end: Mapped[time] = mapped_column("manha_termino", Time)
    afternoon_arrival: Mapped[time] = mapped_column("tarde_chegada", Time)
    afternoon_start: Mapped[time] = mapped_column("tarde_inicio", Time)
    afternoon_end: Mapped[time] = mapped_column("tarde_termino", Time)
    notes: Mapped[str | None] = mapped_column("observacoes", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)


class WorkSample(Base):
    """Rodada da amostragem do trabalho: pessoas trabalhando, em trânsito e paradas (ISSUE-047).

    Os motivos de cada parada e de cada trânsito são filhos da rodada (``amostragem_motivo``),
    editados junto com ela e protegidos pela ``versao`` da raiz, como o relato.
    """

    __tablename__ = "amostragem"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    observer_id: Mapped[int] = mapped_column("observador_id", ForeignKey("pessoa.id"))
    day: Mapped[date] = mapped_column("data", Date)
    hour: Mapped[time] = mapped_column("hora", Time)
    area: Mapped[str] = mapped_column("area", Text)
    foreman: Mapped[str] = mapped_column("encarregado", Text)
    working: Mapped[int] = mapped_column("trabalhando", Integer)
    transit: Mapped[int] = mapped_column("transito", Integer)
    stopped: Mapped[int] = mapped_column("parado", Integer)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)

    reasons: Mapped[list[WorkSampleReason]] = relationship(
        back_populates="sample",
        cascade="all, delete-orphan",
        order_by="WorkSampleReason.id",
    )


class WorkSampleReason(Base):
    """Motivo de cada parada ou trânsito da rodada, com a quantidade (ISSUE-047).

    Sem ``versao`` própria: entra junto com a rodada. UK: rodada + tipo + motivo.
    """

    __tablename__ = "amostragem_motivo"
    __table_args__ = (UniqueConstraint("amostragem_id", "tipo", "motivo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sample_id: Mapped[int] = mapped_column("amostragem_id", ForeignKey("amostragem.id"))
    kind: Mapped[str] = mapped_column("tipo", Text)
    reason: Mapped[str] = mapped_column("motivo", Text)
    quantity: Mapped[int] = mapped_column("quantidade", Integer)

    sample: Mapped[WorkSample] = relationship(back_populates="reasons")


class Stoppage(Base):
    """Paralisação de efetivo ou de máquina e equipamento na frente (ISSUE-047).

    Hhora = pessoas x horas no efetivo; Mhora = unidades x horas na máquina ou equipamento;
    os dois são calculados do tipo. Responsabilidade do cliente, da gerenciadora ou de
    terceiros é tempo potencialmente excusável (base de pleito em Contratos).
    """

    __tablename__ = "paralisacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column("projeto_id", ForeignKey("projeto.id"))
    company_id: Mapped[int] = mapped_column("empresa_id", ForeignKey("empresa.id"))
    recorded_by_id: Mapped[int] = mapped_column("registrado_por_id", ForeignKey("pessoa.id"))
    day: Mapped[date] = mapped_column("data", Date)
    area: Mapped[str] = mapped_column("area", Text)
    kind: Mapped[str] = mapped_column("tipo", Text)
    resource: Mapped[str] = mapped_column("recurso", Text)
    quantity: Mapped[Decimal] = mapped_column("quantidade", Quantity)
    start: Mapped[time] = mapped_column("inicio", Time)
    end: Mapped[time] = mapped_column("termino", Time)
    reason: Mapped[str] = mapped_column("motivo", Text)
    responsibility: Mapped[str] = mapped_column("responsabilidade", Text)
    description: Mapped[str | None] = mapped_column("descricao", Text)
    version: Mapped[int] = mapped_column("versao", Integer, server_default=VERSION_SERVER_DEFAULT)
