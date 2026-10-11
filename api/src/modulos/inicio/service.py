"""Fachada do Início (ISSUE-079, D6, D9): o resumo consolidado do projeto ou do Portfólio.

O Início é uma leitura: cada indicador-chave, cada ponto de atenção e cada selo
dos cards sai da fachada do módulo dono, com a data de referência injetada —
nenhuma fórmula de dono é duplicada e nenhuma tabela alheia é lida (D9). A
fachada monta os textos que a tela lê (``HomeKpi``, ``HomeAttention`` e
``HomeCard``) e devolve tudo em ``HomeOverview``; o fragmento só desenha.

O escopo é o do request (D8): no projeto valem os indicadores dele; no
Portfólio, os consolidados, com o código do projeto nos pontos de atenção. A
tabela Carteira de projetos e a edição da ponderação pertencem à ISSUE-080 e
não entram aqui.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from src.core import navigation, rbac
from src.core.export_document import ValueKind
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.central_acoes.calculations import StatusCounts, StatusFilter
from src.modulos.central_acoes.validation import ActionFilters
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.service import ProjectSummary
from src.modulos.financeiro import service as financeiro
from src.modulos.governanca import service as governanca
from src.modulos.hse import painel_service as hse_painel
from src.modulos.inicio import calculations
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
class HomeOverview:
    """O resumo do Início: o contexto, os oito indicadores, a atenção e os oito cards.

    ``budget_cents`` e ``expected_end_date`` são o orçamento e o término do escopo:
    os do projeto ou, no Portfólio, a soma dos orçamentos e o término mais distante
    (a mesma leitura do protótipo).
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
