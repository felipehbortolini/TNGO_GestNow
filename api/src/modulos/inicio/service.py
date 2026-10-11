"""Fachada do Início (ISSUE-079 e ISSUE-080, D6, D9): o resumo do projeto ou do Portfólio.

O Início é uma leitura: cada indicador-chave, cada ponto de atenção, cada selo
dos cards e cada linha da carteira sai da fachada do módulo dono, com a data de
referência injetada — nenhuma fórmula de dono é duplicada e nenhuma tabela
alheia é lida (D9). A fachada monta os textos que a tela lê (``HomeKpi``,
``HomeAttention``, ``HomeCard`` e ``PortfolioRow``) e devolve tudo em
``HomeOverview``; o fragmento só desenha.

O escopo é o do request (D8): no projeto valem os indicadores dele; no
Portfólio, os consolidados, com o código do projeto nos pontos de atenção, a
carteira de projetos (ISSUE-080) e a ponderação editável pelo Gestor ou Admin.

Todo registro pertence a um projeto: as linhas da carteira leem os donos por
projeto (``Scope(project_id=...)``) e os totais reusam as leituras consolidadas
que os indicadores já fizeram. A gravação da ponderação cria uma versão nova do
grupo ``portfolio`` dos parâmetros e substitui as notas dela, numa transação só.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from src.core import navigation, rbac
from src.core.errors import InvalidDataError
from src.core.export_document import ValueKind
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.central_acoes.calculations import StatusCounts, StatusFilter
from src.modulos.central_acoes.validation import ActionFilters
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes import validation as configuracoes_validation
from src.modulos.configuracoes.models import ParameterVersion
from src.modulos.configuracoes.service import ProjectSummary
from src.modulos.financeiro import calculations as financeiro_calculations
from src.modulos.financeiro import service as financeiro
from src.modulos.governanca import service as governanca
from src.modulos.hse import painel_service as hse_painel
from src.modulos.inicio import calculations, validation
from src.modulos.planejamento import service as planejamento
from src.modulos.qualidade import painel_service as qualidade_painel
from src.modulos.qualidade import service as qualidade
from src.modulos.qualidade.validation import SITUATION_ALL, RncFilters
from src.modulos.riscos import panel_service as riscos_painel
from src.modulos.suprimentos import service as suprimentos
from src.modulos.suprimentos.validation import OrderFilters

MODULE = "inicio"

# As telas de destino dos indicadores e dos pontos de atenção, no endereço público (kebab-case).
ACTIONS_URL = "/central-acoes/acoes?status=atrasada"
PLANNING_URL = "/planejamento/kpis"
COST_URL = "/financeiro/kpis"
ORDERS_URL = "/suprimentos/diligenciamento?faixa=critico"
RISKS_URL = "/riscos/registro"
RISKS_REVIEW_URL = "/riscos/registro?revisao=vencidas"
RNCS_URL = "/qualidade/rnc?situacao=ativas"
RNC_SEARCH_URL = "/qualidade/rnc?busca={code}"
HSE_URL = "/hse/painel"
HSE_OCCURRENCES_URL = "/hse/ocorrencias?hipo=1"
CHANGES_URL = "/governanca/mudancas?" + urlencode({"situacao": "Aguardando comitê"})
PUNCH_URL = "/planejamento/punch-list?sistema={system_id}"
CONTRACTS_URL = "/financeiro/contratos?busca={code}"
CHANGE_SHEET_URL = "/governanca/mudanca?codigo={code}"

# A primeira tela de cada módulo dono: o destino do card, lido da lista de navegação (D2).
CARD_MODULES: tuple[str, ...] = (
    "central_acoes",
    "planejamento",
    "financeiro",
    "suprimentos",
    "riscos",
    "qualidade",
    "hse",
    "governanca",
)

# O rótulo de cada módulo dono, como os indicadores e a exportação o escrevem.
MODULE_LABELS: dict[str, str] = {
    "central_acoes": "01 Central de Ações",
    "planejamento": "02 Planejamento",
    "financeiro": "03 Gestão Financeira",
    "suprimentos": "04 Suprimentos",
    "riscos": "05 Gestão de Riscos",
    "qualidade": "06 Gestão da Qualidade",
    "hse": "07 HSE",
    "governanca": "08 Governança",
}

# A descrição de cada módulo nos cards: os textos do protótipo (home.js).
CARD_DESCRIPTIONS: dict[str, str] = {
    "central_acoes": "Ações de todas as origens, atas e dashboards.",
    "planejamento": "EAP, Curva S, KPIs, 6WLA, programação semanal, produtividade e punch list.",
    "financeiro": "EAC, mapa de controle, desembolso, Curva S e contratos.",
    "suprimentos": "Plano de compras, RFx, diligenciamento e fornecedores.",
    "riscos": "Registro, matriz P x I, ficha e painel de riscos.",
    "qualidade": "Não conformidades, inspeções e ITP, auditorias.",
    "hse": "Ocorrências, pirâmide de segurança, inspeções e HHT.",
    "governanca": "Gestão de mudanças e lições aprendidas.",
}

# Quantas ações atrasadas entram nos pontos de atenção: 3 no projeto, 4 no Portfólio (protótipo).
ATTENTION_ACTIONS_PROJECT = 3
ATTENTION_ACTIONS_PORTFOLIO = 4

_ONE_PLACE = Decimal("0.1")
_HUNDRED = Decimal(100)

# O prefixo do código do projeto no Portfólio: recebe o projeto e devolve ``TN-... · ``.
Prefixer = Callable[[int], str]


@dataclass(frozen=True)
class HomeProject:
    """O projeto do escopo como a barra de contexto o imprime."""

    id: int
    code: str
    name: str
    budget_cents: int | None
    expected_end_date: date | None

    @property
    def label(self) -> str:
        """``TN-2026-014 · Construção de uma nova fábrica``."""
        return f"{self.code} · {self.name}"


@dataclass(frozen=True)
class HomeKpi:
    """Um indicador-chave: o texto da tela e o valor que a exportação leva."""

    key: str
    module: str
    module_label: str
    label: str
    icon: str
    tone: str
    value: str
    export_value: int | Decimal | None
    export_kind: ValueKind
    reference: str
    footer: str
    badge: str
    status: str
    url: str


@dataclass(frozen=True)
class HomeAttention:
    """Um ponto de atenção calculado: o nível, o texto e o link para a tela dona."""

    level: str
    module: str
    title: str
    detail: str
    url: str


@dataclass(frozen=True)
class HomeBadge:
    """Um selo de card: o texto e o tom do Design System."""

    text: str
    tone: str


@dataclass(frozen=True)
class HomeCard:
    """Um card de módulo: o título, a descrição, o destino e os selos calculados."""

    module: str
    title: str
    icon: str
    description: str
    url: str
    badges: tuple[HomeBadge, ...]


@dataclass(frozen=True)
class PortfolioRow:
    """Uma linha da carteira de projetos: o projeto, o peso e os indicadores do Início dele.

    Cada número sai da mesma fachada dona que o Início do projeto lê, no mesmo
    corte (D9): o peso de ``financeiro.portfolio_weights``; o BAC, o CPI, a
    projeção e o VAC de ``cost_kpis_overview``; o previsto, o real, o SPI e os
    términos de ``planning_kpis_overview``; os riscos no topo de ``risk_panel``;
    os pedidos críticos de ``list_panel`` e as ações atrasadas de
    ``count_by_status``. ``health`` é o pior entre o SPI e o CPI.
    """

    project_id: int
    code: str
    name: str
    weight: Decimal
    budget_cents: int
    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    cpi: Decimal | None
    projection_cents: int | None
    vac_cents: int | None
    baseline_finish: date | None
    trend_finish: date | None
    critical_risks: int
    critical_orders: int
    overdue_actions: int
    health: str | None

    @property
    def health_label(self) -> str:
        """``Em dia``, ``Atenção`` ou ``Crítico``: o rótulo da situação."""
        return calculations.health_label(self.health)


@dataclass(frozen=True)
class PortfolioTotals:
    """O rodapé da carteira: as somas em reais e os índices consolidados do Portfólio."""

    project_count: int
    budget_cents: int
    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    cpi: Decimal | None
    projection_cents: int | None
    vac_cents: int | None
    baseline_finish: date | None
    trend_finish: date | None
    critical_risks: int
    critical_orders: int
    overdue_actions: int


@dataclass(frozen=True)
class PonderationCriterionView:
    """Um critério da ponderação vigente: o que o modal edita e lê."""

    id: str
    name: str
    source: str
    weight: Decimal


@dataclass(frozen=True)
class PonderationProjectView:
    """Um projeto da ponderação: o código, o peso atual na carteira e as notas vigentes."""

    project_id: int
    code: str
    name: str
    weight: Decimal
    grades: Mapping[str, int]


@dataclass(frozen=True)
class PonderationView:
    """O modal da ponderação: os critérios e as notas vigentes, os pesos atuais e quem pode salvar."""

    reference_date: date
    criteria: tuple[PonderationCriterionView, ...]
    grade_minimum: int
    grade_maximum: int
    weights_total: Decimal
    projects: tuple[PonderationProjectView, ...]
    can_save: bool


@dataclass(frozen=True)
class PonderationPreviewRow:
    """O peso que um projeto teria com os critérios e as notas digitados."""

    project_id: int
    code: str
    weight: Decimal


@dataclass(frozen=True)
class PonderationPreview:
    """A prévia da ponderação: os pesos resultantes, calculados sem gravar."""

    rows: tuple[PonderationPreviewRow, ...]


@dataclass(frozen=True)
class HomeOverview:
    """O resumo do Início: o contexto, os oito indicadores, a atenção, a carteira e os cards.

    ``budget_cents`` e ``expected_end_date`` são o orçamento e o término do escopo:
    os do projeto ou, no Portfólio, a soma dos orçamentos e o término mais distante
    (a mesma leitura do protótipo). ``portfolio_rows``, ``portfolio_totals`` e
    ``portfolio_note`` só existem no Portfólio (ISSUE-080).
    """

    reference_date: date
    is_portfolio: bool
    scope_label: str
    project: HomeProject | None
    project_count: int
    budget_cents: int | None
    expected_end_date: date | None
    kpis: tuple[HomeKpi, ...]
    attention: tuple[HomeAttention, ...]
    cards: tuple[HomeCard, ...]
    portfolio_rows: tuple[PortfolioRow, ...] = ()
    portfolio_totals: PortfolioTotals | None = None
    portfolio_note: str = ""

    @property
    def is_empty(self) -> bool:
        """Sem projeto nenhum no escopo não há resumo: a tela mostra o vazio de origem."""
        return self.project is None and self.project_count == 0


@dataclass(frozen=True)
class _Owners:
    """O que cada fachada dona devolveu, lido uma vez e reaproveitado pelos indicadores."""

    actions: StatusCounts
    overdue_actions: central_acoes.ActionListing
    planning: planejamento.PlanningKpisOverview
    punch: planejamento.PunchListing
    cost: financeiro.CostKpisOverview
    contracts: financeiro.ContractsOverview
    supply: suprimentos.PanelListing
    critical_orders: suprimentos.OrderListing
    risks: riscos_painel.RiskPanel
    quality: qualidade_painel.QualityIndicators
    rncs: qualidade.RncListing
    hse: hse_painel.HsePanel
    changes: governanca.RegisterOverview


def home_overview(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> HomeOverview:
    """O resumo do escopo na data de referência, montado pelas fachadas dos módulos donos."""
    rbac.require_module(user, MODULE)
    projects = configuracoes.list_projects(session)
    chosen = _chosen_project(projects, scope)
    if chosen is None and scope.is_portfolio and not projects:
        return _empty_overview(scope=scope, reference_date=reference_date)
    owners = _read_owners(session, user=user, scope=scope, reference_date=reference_date)
    codes = {project.id: project.code for project in projects}
    portfolio_rows: tuple[PortfolioRow, ...] = ()
    portfolio_totals: PortfolioTotals | None = None
    portfolio_note = ""
    if scope.is_portfolio:
        portfolio_rows = _portfolio_rows(
            session, user=user, projects=projects, reference_date=reference_date
        )
        portfolio_totals = _portfolio_totals(owners, rows=portfolio_rows)
        portfolio_note = _portfolio_note(session, reference_date=reference_date)
    return HomeOverview(
        reference_date=reference_date,
        is_portfolio=scope.is_portfolio,
        scope_label=_scope_label(chosen, scope),
        project=chosen,
        project_count=len(projects),
        budget_cents=_scope_budget(chosen, projects, scope=scope),
        expected_end_date=_scope_end_date(chosen, projects, scope=scope),
        kpis=_kpis(owners),
        attention=_attention(owners, scope=scope, codes=codes),
        cards=_cards(owners),
        portfolio_rows=portfolio_rows,
        portfolio_totals=portfolio_totals,
        portfolio_note=portfolio_note,
    )


# ── A leitura dos donos ──────────────────────────────────────────────────


def _read_owners(session: Session, *, user: User, scope: Scope, reference_date: date) -> _Owners:
    """Lê as fachadas donas na data de referência: cada número sai do seu dono (D9)."""
    return _Owners(
        actions=central_acoes.count_by_status(
            session, user=user, scope=scope, reference_date=reference_date
        ),
        overdue_actions=central_acoes.list_actions(
            session,
            user=user,
            scope=scope,
            filters=ActionFilters(status=StatusFilter.OVERDUE),
            reference_date=reference_date,
        ),
        planning=planejamento.planning_kpis_overview(
            session, scope=scope, reference_date=reference_date
        ),
        punch=planejamento.punch_overview(
            session,
            user=user,
            scope=scope,
            punch_filter=planejamento.PunchFilter(),
            reference_date=reference_date,
        ),
        cost=financeiro.cost_kpis_overview(session, scope=scope, reference_date=reference_date),
        contracts=financeiro.contracts_overview(
            session, user=user, scope=scope, reference_date=reference_date
        ),
        supply=suprimentos.list_panel(
            session, user=user, scope=scope, reference_date=reference_date
        ),
        critical_orders=suprimentos.list_orders(
            session,
            user=user,
            scope=scope,
            filters=OrderFilters(band="critico"),
            reference_date=reference_date,
        ),
        risks=riscos_painel.risk_panel(
            session, user=user, scope=scope, reference_date=reference_date
        ),
        quality=qualidade_painel.quality_indicators(
            session, user=user, scope=scope, reference_date=reference_date
        ),
        rncs=qualidade.list_rncs(
            session,
            user=user,
            scope=scope,
            filters=RncFilters(situation=SITUATION_ALL),
            reference_date=reference_date,
        ),
        hse=hse_painel.panel(
            session,
            user=user,
            scope=scope,
            reference_date=reference_date,
            month=None,
            pyramid_kind=None,
        ),
        changes=governanca.register_overview(
            session,
            user=user,
            scope=scope,
            filters=governanca.ChangeFilter(),
            reference_date=reference_date,
        ),
    )


# ── Os oito indicadores ──────────────────────────────────────────────────


def _kpis(owners: _Owners) -> tuple[HomeKpi, ...]:
    """Os oito indicadores-chave, na ordem dos módulos, com a referência de gestão."""
    return (
        _actions_kpi(owners.actions),
        _spi_kpi(owners.planning),
        _cpi_kpi(owners.cost),
        _orders_kpi(owners.supply),
        _risks_kpi(owners.risks),
        _rncs_kpi(owners.quality),
        _hse_kpi(owners.hse),
        _changes_kpi(owners.changes),
    )


def _actions_kpi(counts: StatusCounts) -> HomeKpi:
    overdue = counts.overdue
    return HomeKpi(
        key="acoes",
        module="central_acoes",
        module_label=MODULE_LABELS["central_acoes"],
        label="Ações atrasadas",
        icon="taskList",
        tone="erro" if overdue else "ok",
        value=calculations.integer_text(overdue),
        export_value=overdue,
        export_kind=ValueKind.INTEGER,
        reference="Esperado 0",
        footer=f"de {calculations.integer_text(counts.open)} ações em aberto",
        badge="",
        status="Atrasadas" if overdue else "Nenhuma atrasada",
        url=ACTIONS_URL,
    )


def _spi_kpi(planning: planejamento.PlanningKpisOverview) -> HomeKpi:
    indicators = planning.indicators
    spi = indicators.spi
    label = "SPI ponderado da carteira" if planning.is_portfolio else "SPI (desempenho de prazo)"
    footer = ""
    if spi is not None:
        delta = calculations.delta_text(spi, indicators.previous_spi)
        position = (
            f"real {calculations.percent_text(indicators.actual)}"
            f" x previsto {calculations.percent_text(indicators.predicted)}"
        )
        footer = f"{delta} · {position}" if delta else position
    return HomeKpi(
        key="spi",
        module="planejamento",
        module_label=MODULE_LABELS["planejamento"],
        label=label,
        icon="chartLine",
        tone=calculations.index_tone(spi),
        value=calculations.index_text(spi),
        export_value=spi,
        export_kind=ValueKind.DECIMAL,
        reference="Meta ≥ 1,00",
        footer=footer,
        badge="",
        status=_index_status(spi),
        url=PLANNING_URL,
    )


def _cpi_kpi(cost: financeiro.CostKpisOverview) -> HomeKpi:
    cpi = cost.indicators.cpi if cost.indicators is not None else None
    label = "CPI da carteira" if cost.is_portfolio else "CPI (desempenho de custo)"
    footer = ""
    if cpi is not None:
        delta = calculations.delta_text(cpi, cost.previous.cpi if cost.previous else None)
        projection = (
            f"projeção {calculations.compact_brl(cost.projection_cents)}"
            f" ({calculations.signed_percent_text(_projection_deviation_pct(cost))})"
        )
        footer = f"{delta} · {projection}" if delta else projection
    return HomeKpi(
        key="cpi",
        module="financeiro",
        module_label=MODULE_LABELS["financeiro"],
        label=label,
        icon="money",
        tone=calculations.index_tone(cpi),
        value=calculations.index_text(cpi),
        export_value=cpi,
        export_kind=ValueKind.DECIMAL,
        reference="Meta ≥ 1,00",
        footer=footer,
        badge="",
        status=_index_status(cpi),
        url=COST_URL,
    )


def _projection_deviation_pct(cost: financeiro.CostKpisOverview) -> Decimal | None:
    """O desvio da projeção no término contra o BAC, em pontos percentuais."""
    if cost.projection_cents is None or not cost.budget_cents:
        return None
    deviation = Decimal(cost.projection_cents - cost.budget_cents) / Decimal(cost.budget_cents)
    return (deviation * _HUNDRED).quantize(_ONE_PLACE, rounding=ROUND_HALF_UP)


def _orders_kpi(supply: suprimentos.PanelListing) -> HomeKpi:
    orders = supply.summary.orders
    return HomeKpi(
        key="pedidos",
        module="suprimentos",
        module_label=MODULE_LABELS["suprimentos"],
        label="Pedidos críticos",
        icon="cart",
        tone="erro" if orders.critical else "ok",
        value=calculations.integer_text(orders.critical),
        export_value=orders.critical,
        export_kind=ValueKind.INTEGER,
        reference="Esperado 0",
        footer=(
            "folga negativa em relação ao ROS · "
            f"{calculations.integer_text(orders.lli_critical)} de longo prazo"
        ),
        badge="",
        status="Críticos" if orders.critical else "Nenhum crítico",
        url=ORDERS_URL,
    )


def _risks_kpi(risks: riscos_painel.RiskPanel) -> HomeKpi:
    summary = risks.summary
    top = summary.top
    footer = f"exposição {calculations.compact_brl(summary.exposure_cents)}"
    if summary.second is not None:
        second = summary.second
        footer = f"{calculations.integer_text(second.total)} {second.band.name.lower()} · {footer}"
    return HomeKpi(
        key="riscos",
        module="riscos",
        module_label=MODULE_LABELS["riscos"],
        label=f"Riscos {top.band.name.lower()}s",
        icon="warning",
        tone="erro" if top.total else "ok",
        value=calculations.integer_text(top.total),
        export_value=top.total,
        export_kind=ValueKind.INTEGER,
        reference="Esperado 0",
        footer=footer,
        badge="",
        status="Críticos" if top.total else "Nenhum crítico",
        url=RISKS_URL,
    )


def _rncs_kpi(quality: qualidade_painel.QualityIndicators) -> HomeKpi:
    tone = "erro" if quality.overdue_rncs else ("warn" if quality.open_rncs else "ok")
    return HomeKpi(
        key="rncs",
        module="qualidade",
        module_label=MODULE_LABELS["qualidade"],
        label="Não conformidades abertas",
        icon="shield",
        tone=tone,
        value=calculations.integer_text(quality.open_rncs),
        export_value=quality.open_rncs,
        export_kind=ValueKind.INTEGER,
        reference="Limite 0 vencidas",
        footer=(
            f"{calculations.plural(quality.overdue_rncs, 'vencida')} · "
            f"inspeções aprovadas {calculations.percent_text(quality.inspection_approval_pct)}"
        ),
        badge="",
        status="Com vencidas" if quality.overdue_rncs else "Em aberto",
        url=RNCS_URL,
    )


def _hse_kpi(hse: hse_painel.HsePanel) -> HomeKpi:
    accumulated = hse.accumulated_indicators
    days = None if accumulated is None else accumulated.days_without_leave
    tf = None if accumulated is None else accumulated.tf
    hipo = 0 if hse.month_indicators is None else hse.month_indicators.hipo
    return HomeKpi(
        key="hse",
        module="hse",
        module_label=MODULE_LABELS["hse"],
        label="Dias sem acidente com afastamento",
        icon="hardHat",
        tone="warn" if hipo else "ok",
        value="sem registro" if days is None else calculations.integer_text(days),
        export_value=days,
        export_kind=ValueKind.INTEGER,
        reference="Esperado desde o início do projeto",
        footer=f"TF {calculations.decimal_text(tf, digits=2)}",
        badge=f"{calculations.plural(hipo, 'HiPo')} no mês" if hipo else "",
        status="Sem afastamento" if days is not None else "Sem registro",
        url=HSE_URL,
    )


def _changes_kpi(changes: governanca.RegisterOverview) -> HomeKpi:
    summary = changes.summary
    scope_text = "do orçamento da carteira" if changes.is_portfolio else "do orçamento"
    percent = calculations.percent_text(summary.approved_value_percent)
    approved = f"{calculations.compact_brl(summary.approved_value_cents)} aprovados"
    footer = (
        f"{approved} ({percent} {scope_text})" if percent != "-" else f"{approved} {scope_text}"
    )
    return HomeKpi(
        key="mudancas",
        module="governanca",
        module_label=MODULE_LABELS["governanca"],
        label="Mudanças aguardando comitê",
        icon="landmark",
        tone="info" if summary.awaiting_committee else "ok",
        value=calculations.integer_text(summary.awaiting_committee),
        export_value=summary.awaiting_committee,
        export_kind=ValueKind.INTEGER,
        reference="Esperado 0",
        footer=footer,
        badge="",
        status="Aguardando comitê" if summary.awaiting_committee else "Nenhuma aguardando",
        url=CHANGES_URL,
    )


def _index_status(value: Decimal | None) -> str:
    if value is None:
        return "Sem dados"
    if value >= 1:
        return "Dentro da meta"
    return "Atenção" if value >= calculations.ATTENTION_INDEX else "Abaixo da meta"


# ── A carteira de projetos (ISSUE-080) ───────────────────────────────────


def _portfolio_rows(
    session: Session,
    *,
    user: User,
    projects: list[ProjectSummary],
    reference_date: date,
) -> tuple[PortfolioRow, ...]:
    """As linhas da carteira, uma por projeto, lidas das fachadas donas no mesmo corte.

    O peso sai de uma leitura só da ponderação; cada projeto é lido no seu
    escopo, como o Início dele, e a linha junta os dois lados: prazo
    (``planning_kpis_overview``) e custo (``cost_kpis_overview``). A ordem é a
    do protótipo: do maior peso para o menor.
    """
    weights = financeiro.portfolio_weights(session, reference_date=reference_date)
    rows: list[PortfolioRow] = []
    for project in projects:
        scope = Scope(project_id=project.id, source="url")
        planning = planejamento.planning_kpis_overview(
            session, scope=scope, reference_date=reference_date
        )
        cost = financeiro.cost_kpis_overview(session, scope=scope, reference_date=reference_date)
        risks = riscos_painel.risk_panel(
            session, user=user, scope=scope, reference_date=reference_date
        )
        supply = suprimentos.list_panel(
            session, user=user, scope=scope, reference_date=reference_date
        )
        actions = central_acoes.count_by_status(
            session, user=user, scope=scope, reference_date=reference_date
        )
        weight = weights.get(project.id)
        cpi = None if cost.indicators is None else cost.indicators.cpi
        rows.append(
            PortfolioRow(
                project_id=project.id,
                code=project.code,
                name=project.name,
                weight=Decimal(0) if weight is None else weight.weight,
                budget_cents=cost.budget_cents,
                predicted=planning.indicators.predicted,
                actual=planning.indicators.actual,
                deviation_pp=planning.indicators.deviation_pp,
                spi=planning.indicators.spi,
                cpi=cpi,
                projection_cents=cost.projection_cents,
                vac_cents=cost.vac_cents,
                baseline_finish=planning.indicators.baseline_finish,
                trend_finish=planning.indicators.trend_finish,
                critical_risks=risks.summary.top.total,
                critical_orders=supply.summary.orders.critical,
                overdue_actions=actions.overdue,
                health=calculations.health_band(planning.indicators.spi, cpi),
            )
        )
    return tuple(sorted(rows, key=lambda row: row.weight, reverse=True))


def _portfolio_totals(owners: _Owners, *, rows: tuple[PortfolioRow, ...]) -> PortfolioTotals:
    """O rodapé da carteira: as somas em reais e os índices consolidados do Portfólio.

    Os totais não releem nada: o Portfólio já leu os consolidados para os
    indicadores — a soma do BAC, da projeção e do VAC, o previsto, o real, o SPI
    e o CPI da carteira e as contagens de riscos, pedidos e ações.
    """
    indicators = owners.planning.indicators
    cost = owners.cost
    return PortfolioTotals(
        project_count=len(rows),
        budget_cents=cost.budget_cents,
        predicted=indicators.predicted,
        actual=indicators.actual,
        deviation_pp=indicators.deviation_pp,
        spi=indicators.spi,
        cpi=None if cost.indicators is None else cost.indicators.cpi,
        projection_cents=cost.projection_cents,
        vac_cents=cost.vac_cents,
        baseline_finish=indicators.baseline_finish,
        trend_finish=indicators.trend_finish,
        critical_risks=owners.risks.summary.top.total,
        critical_orders=owners.supply.summary.orders.critical,
        overdue_actions=owners.actions.overdue,
    )


def _portfolio_note(session: Session, *, reference_date: date) -> str:
    """``Peso na carteira pela ponderação composta: Valor ... 60% · ...`` (protótipo)."""
    criteria = _criteria_views(session, reference_date=reference_date)
    if not criteria:
        return ""
    summary = " · ".join(
        f"{criterion.name} {calculations.input_number(criterion.weight)}%" for criterion in criteria
    )
    return f"Peso na carteira pela ponderação composta: {summary}. Posição na data de referência."


# ── A ponderação da carteira (ISSUE-080) ─────────────────────────────────


def ponderation_view(session: Session, *, user: User, reference_date: date) -> PonderationView:
    """O modal da ponderação: os critérios e as notas vigentes, com os pesos atuais da carteira.

    A leitura é a do Início: quem vê a tela abre o modal; quem pode gravar é o
    Gestor ou o Admin (``can_save``), e a prévia e a gravação exigem
    ``Permission.MANAGE`` na rota e na fachada.
    """
    rbac.require_module(user, MODULE)
    projects = configuracoes.list_projects(session)
    group = configuracoes.current_group(session, group="portfolio", reference_date=reference_date)
    criteria = _criteria_views(session, reference_date=reference_date)
    grades = configuracoes.portfolio_grades(session, reference_date=reference_date)
    weights = financeiro.portfolio_weights(session, reference_date=reference_date)
    minimum, maximum = _grade_bounds(group)
    return PonderationView(
        reference_date=reference_date,
        criteria=criteria,
        grade_minimum=minimum,
        grade_maximum=maximum,
        weights_total=sum((criterion.weight for criterion in criteria), Decimal(0)),
        projects=tuple(
            PonderationProjectView(
                project_id=project.id,
                code=project.code,
                name=project.name,
                weight=weights[project.id].weight if project.id in weights else Decimal(0),
                grades=dict(grades.get(project.id, {})),
            )
            for project in projects
        ),
        can_save=rbac.can(user, Permission.MANAGE),
    )


def ponderation_preview(
    session: Session,
    *,
    user: User,
    criteria: Mapping[str, str],
    grades: Mapping[int, Mapping[str, str]],
    reference_date: date,
) -> PonderationPreview:
    """A prévia dos pesos com os valores digitados, sem gravar nada.

    Chama a fórmula do dono (``financeiro.calculations.portfolio_weights``) com
    os orçamentos vigentes da carteira (``financeiro.service.current_budgets``);
    um campo vazio ou inválido vale zero, como o protótipo calculava na tela.
    """
    rbac.require(user, Permission.MANAGE)
    views = _criteria_views(session, reference_date=reference_date)
    projects = configuracoes.list_projects(session)
    budgets = financeiro.current_budgets(session)
    inputs = [
        financeiro_calculations.WeightInput(
            project_id=project.id,
            budget_cents=budgets.get(project.id, 0),
            grades={
                criterion.id: validation.parse_grade(
                    grades.get(project.id, {}).get(criterion.id, "")
                )
                or 0
                for criterion in views
                if criterion.source == "nota"
            },
        )
        for project in projects
    ]
    weights = financeiro_calculations.portfolio_weights(inputs, _preview_criteria(views, criteria))
    return PonderationPreview(
        rows=tuple(
            PonderationPreviewRow(
                project_id=project.id,
                code=project.code,
                weight=weights[project.id].weight if project.id in weights else Decimal(0),
            )
            for project in projects
        )
    )


def save_ponderation(
    session: Session,
    *,
    user: User,
    criteria: Mapping[str, str],
    grades: Mapping[int, Mapping[str, str]],
    justification: str,
    reference_date: date,
) -> ParameterVersion:
    """Grava a ponderação: valida, cria a versão nova do grupo portfolio e substitui as notas.

    A defesa em profundidade repete o ``Permission.MANAGE`` da rota (Gestor ou
    Admin; Membro recebe 403). O grupo inteiro vigente vai com os critérios
    trocados e a justificativa; a versão nova nasce com as notas da anterior
    (``save_parameter_group``) e a substituição grava as digitadas, com a
    trilha. Toda recusa é mensagem por campo (``InvalidDataError``, 422).
    """
    rbac.require(user, Permission.MANAGE)
    projects = configuracoes.list_projects(session)
    group = configuracoes.current_group(session, group="portfolio", reference_date=reference_date)
    views = _criteria_views(session, reference_date=reference_date)
    minimum, maximum = _grade_bounds(group)
    errors = _justification_errors(justification)
    payloads, weight_errors = _posted_weight_payloads(group, views, criteria)
    errors.update(weight_errors)
    if not weight_errors and payloads:
        message = configuracoes_validation.portfolio_weights_error({"criterios": payloads})
        if message:
            errors[validation.weight_field(views[0].id)] = message
    posted_grades, grade_errors = _posted_grade_payloads(
        projects, views, grades, minimum=minimum, maximum=maximum
    )
    errors.update(grade_errors)
    if errors:
        raise InvalidDataError(errors)
    version = configuracoes.save_parameter_group(
        session,
        author_id=user.id,
        group="portfolio",
        values={**group, "criterios": payloads},
        effective_from=reference_date,
        justification=justification,
    )
    configuracoes.replace_portfolio_grades(
        session, version=version, grades=posted_grades, author_id=user.id
    )
    return version


def _criteria_views(
    session: Session, *, reference_date: date
) -> tuple[PonderationCriterionView, ...]:
    """Os critérios da versão vigente do grupo portfolio: id, nome, fonte e peso."""
    group = configuracoes.current_group(session, group="portfolio", reference_date=reference_date)
    configured = group.get("criterios") or []
    return tuple(
        PonderationCriterionView(
            id=str(item["id"]),
            name=str(item.get("nome") or item["id"]),
            source=str(item.get("fonte", "nota")),
            weight=Decimal(str(item.get("peso", 0))),
        )
        for item in configured
        if isinstance(item, Mapping) and item.get("id")
    )


def _grade_bounds(group: Mapping[str, Any]) -> tuple[int, int]:
    """A faixa de notas do grupo vigente: ``notaMinima`` e ``notaMaxima`` (1 a 5)."""
    return _int_or(group.get("notaMinima"), 1), _int_or(group.get("notaMaxima"), 5)


def _int_or(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _preview_criteria(
    views: tuple[PonderationCriterionView, ...], posted: Mapping[str, str]
) -> list[financeiro_calculations.WeightCriterion]:
    """Os critérios digitados como o dono os calcula; campo vazio ou inválido vale zero."""
    return [
        financeiro_calculations.WeightCriterion(
            id=view.id,
            weight=validation.parse_weight(posted.get(view.id, "")) or Decimal(0),
            source=view.source,
        )
        for view in views
    ]


def _posted_weight_payloads(
    group: Mapping[str, Any],
    views: tuple[PonderationCriterionView, ...],
    posted: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Os critérios vigentes com o peso digitado e os erros por campo quando o peso não vale."""
    configured = {
        str(item["id"]): item
        for item in group.get("criterios") or []
        if isinstance(item, Mapping) and item.get("id")
    }
    payloads: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for view in views:
        payload = dict(
            configured.get(view.id, {"id": view.id, "nome": view.name, "fonte": view.source})
        )
        value = validation.parse_weight(posted.get(view.id, ""))
        if value is None or not validation.WEIGHT_MIN <= value <= validation.WEIGHT_MAX:
            errors[validation.weight_field(view.id)] = validation.WEIGHT_RANGE_MESSAGE
        else:
            payload["peso"] = _weight_payload(value)
        payloads.append(payload)
    return payloads, errors


def _weight_payload(value: Decimal) -> int | float:
    """O peso como o grupo o guarda: inteiro quando não tem casas (``60``), senão decimal."""
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _posted_grade_payloads(
    projects: list[ProjectSummary],
    views: tuple[PonderationCriterionView, ...],
    grades: Mapping[int, Mapping[str, str]],
    *,
    minimum: int,
    maximum: int,
) -> tuple[dict[int, dict[str, int]], dict[str, str]]:
    """As notas digitadas por projeto e critério de fonte nota e os erros por campo."""
    note_criteria = [view for view in views if view.source == "nota"]
    payloads: dict[int, dict[str, int]] = {}
    errors: dict[str, str] = {}
    for project in projects:
        posted = grades.get(project.id, {})
        values: dict[str, int] = {}
        for criterion in note_criteria:
            value = validation.parse_grade(posted.get(criterion.id, ""))
            if value is None or not minimum <= value <= maximum:
                errors[validation.grade_field(project.id, criterion.id)] = validation.grade_message(
                    minimum, maximum
                )
                continue
            values[criterion.id] = value
        payloads[project.id] = values
    return payloads, errors


def _justification_errors(justification: str) -> dict[str, str]:
    message = validation.justification_error(justification)
    return {} if message is None else {validation.JUSTIFICATION_FIELD: message}


# ── Os pontos de atenção ─────────────────────────────────────────────────


def _attention(
    owners: _Owners, *, scope: Scope, codes: dict[int, str]
) -> tuple[HomeAttention, ...]:
    """Os pontos de atenção calculados, na ordem do protótipo, com o código no Portfólio."""
    prefix = _prefixer(scope, codes)
    entries: list[HomeAttention] = []
    entries.extend(_attention_actions(owners.overdue_actions, prefix=prefix, scope=scope))
    entries.extend(_attention_orders(owners.critical_orders, prefix=prefix))
    entries.extend(_attention_punch(owners.punch))
    entries.extend(_attention_risks(owners.risks, prefix=prefix))
    entries.extend(_attention_claims(owners.contracts, prefix=prefix))
    entries.extend(_attention_changes(owners.changes, prefix=prefix))
    entries.extend(_attention_rncs(owners.rncs, prefix=prefix))
    entries.extend(_attention_hipo(owners.hse))
    return tuple(entries)


def _attention_actions(
    listing: central_acoes.ActionListing, *, prefix: Prefixer, scope: Scope
) -> list[HomeAttention]:
    """As ações mais atrasadas: 3 no projeto, 4 no Portfólio, da mais atrasada para a menos."""
    limit = ATTENTION_ACTIONS_PORTFOLIO if scope.is_portfolio else ATTENTION_ACTIONS_PROJECT
    ordered = sorted(listing.rows, key=lambda row: -row.record.days_overdue)[:limit]
    return [
        HomeAttention(
            level="danger",
            module="central_acoes",
            title=f"{prefix(row.record.project_id)}{row.record.subject}",
            detail=(
                f"{' '.join(filter(None, (row.record.origin, row.record.origin_ref)))} · "
                f"{calculations.plural(row.record.days_overdue, 'dia')} de atraso"
            ),
            url=ACTIONS_URL,
        )
        for row in ordered
    ]


def _attention_orders(
    listing: suprimentos.OrderListing, *, prefix: Prefixer
) -> list[HomeAttention]:
    """Os pedidos com folga negativa em relação ao ROS."""
    return [
        HomeAttention(
            level="danger",
            module="suprimentos",
            title=f"{prefix(line.project_id)}{line.number} {line.description}",
            detail=f"Folga de {line.slack_days} dias em relação ao ROS",
            url=ORDERS_URL,
        )
        for line in listing.lines
        if line.slack_days is not None
    ]


def _attention_punch(listing: planejamento.PunchListing) -> list[HomeAttention]:
    """Cada sistema bloqueado por item de categoria A em aberto, com o seu próprio link.

    O bloco de sistema não diz a que projeto pertence, então no Portfólio o alerta
    sai sem o código do projeto: o sistema e o link filtrado o identificam.
    """
    return [
        HomeAttention(
            level="warning",
            module="planejamento",
            title=f"Sistema {block.label} bloqueado por item A",
            detail=(
                f"{calculations.plural(block.a_open, 'item A aberto', 'itens A abertos')}"
                " na Punch list"
            ),
            url=PUNCH_URL.format(system_id=block.system_id),
        )
        for block in listing.blocks
        if block.a_open > 0
    ]


def _attention_risks(
    risk_panel: riscos_painel.RiskPanel, *, prefix: Prefixer
) -> list[HomeAttention]:
    """Os riscos com a revisão periódica vencida."""
    return [
        HomeAttention(
            level="warning",
            module="riscos",
            title=f"{prefix(line.project_id)}{line.code} com revisão vencida",
            detail=line.title,
            url=RISKS_REVIEW_URL,
        )
        for line in risk_panel.summary.overdue
    ]


def _attention_claims(
    contracts: financeiro.ContractsOverview, *, prefix: Prefixer
) -> list[HomeAttention]:
    """Os claims abertos notificados fora do prazo contratual."""
    return [
        HomeAttention(
            level="warning",
            module="financeiro",
            title=f"{prefix(claim.project_id)}{claim.code} notificado fora do prazo contratual",
            detail=(
                f"{claim.contract_number} · "
                f"{calculations.plural(claim.notification_days, 'dia')} entre evento e notificação"
            ),
            url=CONTRACTS_URL.format(code=claim.code),
        )
        for claim in contracts.claims
        if claim.notification_late and claim.is_open
    ]


def _attention_changes(
    changes: governanca.RegisterOverview, *, prefix: Prefixer
) -> list[HomeAttention]:
    """A emergencial sem ratificação do Comitê e a análise de impacto vencida."""
    entries: list[HomeAttention] = []
    for row in changes.rows:
        if row.ratification_overdue:
            entries.append(
                HomeAttention(
                    level="danger",
                    module="governanca",
                    title=(
                        f"{prefix(row.project_id)}{row.code} emergencial sem ratificação do Comitê"
                    ),
                    detail="Prazo de ratificação vencido",
                    url=CHANGE_SHEET_URL.format(code=row.code),
                )
            )
        elif row.analysis_overdue:
            entries.append(
                HomeAttention(
                    level="warning",
                    module="governanca",
                    title=f"{prefix(row.project_id)}{row.code} com análise de impacto vencida",
                    detail=row.title,
                    url=CHANGE_SHEET_URL.format(code=row.code),
                )
            )
    return entries


def _attention_rncs(listing: qualidade.RncListing, *, prefix: Prefixer) -> list[HomeAttention]:
    """As RNC com prazo de tratamento vencido ou críticas em aberto."""
    return [
        HomeAttention(
            level="danger" if line.severity == "Crítica" else "warning",
            module="qualidade",
            title=(
                f"{prefix(line.project_id)}{line.code}"
                + (" com prazo de tratamento vencido" if line.overdue else " crítica em aberto")
            ),
            detail=line.description,
            url=RNC_SEARCH_URL.format(code=line.code),
        )
        for line in listing.lines
        if line.overdue or (line.active and line.severity == "Crítica")
    ]


def _attention_hipo(hse: hse_painel.HsePanel) -> list[HomeAttention]:
    """As ocorrências de alto potencial (HiPo) do mês da leitura do painel."""
    hipo = 0 if hse.month_indicators is None else hse.month_indicators.hipo
    if not hipo:
        return []
    return [
        HomeAttention(
            level="danger",
            module="hse",
            title=(
                f"{calculations.plural(hipo, 'ocorrência', 'ocorrências')} de alto potencial no mês"
            ),
            detail="Relatório final exigido",
            url=HSE_OCCURRENCES_URL,
        )
    ]


# ── Os cards dos módulos ─────────────────────────────────────────────────


def _cards(owners: _Owners) -> tuple[HomeCard, ...]:
    """Os oito cards dos módulos, com o selo calculado de cada um."""
    badges: dict[str, HomeBadge] = {
        "central_acoes": HomeBadge(
            f"{calculations.integer_text(owners.actions.overdue)} atrasadas",
            tone="erro" if owners.actions.overdue else "ok",
        ),
        "planejamento": HomeBadge(
            f"{calculations.integer_text(owners.punch.kpis.open_a)} itens A abertos",
            tone="warn" if owners.punch.kpis.open_a else "ok",
        ),
        "financeiro": HomeBadge(
            f"{calculations.integer_text(owners.contracts.summary.open_claims)} claims em aberto",
            tone="warn" if owners.contracts.summary.open_claims else "ok",
        ),
        "suprimentos": HomeBadge(
            f"aderência ao plano {calculations.percent_text(owners.supply.summary.adherence_pct)}",
            tone="info",
        ),
        "riscos": HomeBadge(
            f"{calculations.integer_text(len(owners.risks.summary.overdue))} revisão vencida",
            tone="warn" if owners.risks.summary.overdue else "ok",
        ),
        "qualidade": HomeBadge(
            f"{calculations.integer_text(owners.quality.open_rncs)} RNC abertas",
            tone="warn" if owners.quality.open_rncs else "ok",
        ),
        "hse": HomeBadge(
            f"TRIF {calculations.decimal_text(_hse_trif(owners.hse), digits=2)}",
            tone="info",
        ),
        "governanca": HomeBadge(
            f"{calculations.integer_text(owners.changes.summary.in_analysis)} em análise de impacto",
            tone="info",
        ),
    }
    screens = {module_id: _module_screen(module_id) for module_id in CARD_MODULES}
    return tuple(
        HomeCard(
            module=module_id,
            title=navigation.module_of(screens[module_id]).label,
            icon=navigation.module_of(screens[module_id]).icon,
            description=CARD_DESCRIPTIONS[module_id],
            url=navigation.public_path(screens[module_id]),
            badges=(badges[module_id],),
        )
        for module_id in CARD_MODULES
    )


def _hse_trif(hse: hse_painel.HsePanel) -> Decimal | None:
    accumulated = hse.accumulated_indicators
    return None if accumulated is None else accumulated.trif


def _module_screen(module_id: str) -> navigation.Screen:
    """A primeira tela listada do módulo dono: o destino do card."""
    module = next(item for item in navigation.modules() if item.id == module_id)
    return module.landing


# ── O contexto ───────────────────────────────────────────────────────────


def _chosen_project(projects: list[ProjectSummary], scope: Scope) -> HomeProject | None:
    found = next((project for project in projects if project.id == scope.project_id), None)
    if found is None:
        return None
    return HomeProject(
        id=found.id,
        code=found.code,
        name=found.name,
        budget_cents=found.budget_cents,
        expected_end_date=found.expected_end_date,
    )


def _scope_label(chosen: HomeProject | None, scope: Scope) -> str:
    if scope.is_portfolio:
        return "Portfólio de projetos"
    return chosen.label if chosen is not None else f"Projeto {scope.project_id}"


def _scope_budget(
    chosen: HomeProject | None, projects: list[ProjectSummary], *, scope: Scope
) -> int | None:
    """O orçamento do escopo: o do projeto ou a soma do Portfólio (protótipo)."""
    if not scope.is_portfolio:
        return None if chosen is None else chosen.budget_cents
    budgets = [project.budget_cents for project in projects if project.budget_cents is not None]
    return sum(budgets) if budgets else None


def _scope_end_date(
    chosen: HomeProject | None, projects: list[ProjectSummary], *, scope: Scope
) -> date | None:
    """O término previsto do escopo: o do projeto ou o mais distante do Portfólio (protótipo)."""
    if not scope.is_portfolio:
        return None if chosen is None else chosen.expected_end_date
    ends = [
        project.expected_end_date for project in projects if project.expected_end_date is not None
    ]
    return max(ends) if ends else None


def _empty_overview(*, scope: Scope, reference_date: date) -> HomeOverview:
    """O Portfólio sem projetos: a tela mostra o vazio de origem."""
    return HomeOverview(
        reference_date=reference_date,
        is_portfolio=scope.is_portfolio,
        scope_label="Portfólio de projetos",
        project=None,
        project_count=0,
        budget_cents=None,
        expected_end_date=None,
        kpis=(),
        attention=(),
        cards=(),
    )


def _prefixer(scope: Scope, codes: dict[int, str]) -> Callable[[int], str]:
    """``TN-2026-014 · `` no Portfólio; vazio no projeto (o protótipo prefixa o código lá)."""

    def prefix(project_id: int) -> str:
        if not scope.is_portfolio:
            return ""
        code = codes.get(project_id, "")
        return f"{code} · " if code else ""

    return prefix
