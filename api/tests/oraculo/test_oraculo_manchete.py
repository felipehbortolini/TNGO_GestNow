"""A manchete do cenário (ISSUE-089): os números do HANDOVER numa afirmação só.

O teste-oráculo consolidado já afirma cada número no oráculo do módulo dono; esta
afirmação reúne a manchete da issue — BAC, CPI, SPI de custo, projeção no término,
ações atrasadas, pedidos críticos, riscos críticos, RNC abertas, dias sem
afastamento, pirâmide, aderência ao plano de compras, OTD, pesos da carteira e
exposição —, cada um pela fachada dona, no cenário da âncora (25/09/2026).

Nenhum número da manchete diverge do protótipo: a projeção de R$ 45,26 mi é a soma
das projeções por item (4.525.500.000 centavos) apresentada em milhões com duas
casas (ROUND_HALF_UP), como o oráculo da ISSUE-031 já fixa; as divergências
registradas em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md`` tocam os projetos 2 e 3 da EAC
e os planos das curvas, e não estes números do projeto 1.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.auth import _user_of
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from src.modulos.financeiro import service as financeiro
from src.modulos.hse import painel_service
from src.modulos.qualidade import service as qualidade
from src.modulos.riscos import service as riscos
from src.modulos.suprimentos import service as suprimentos
from src.modulos.suprimentos import validation as suprimentos_validation
from tests.oraculo import OracleContext, register_check

D = Decimal
PROJECT_CODE = "TN-2026-014"

BAC_CENTS = 4_460_000_000
CPI = D("0.96")
SPI = D("0.94")
PROJECTION_CENTS = 4_525_500_000
PROJECTION_MI = D("45.26")
OVERDUE_ACTIONS = 8
CRITICAL_ORDERS = 3
CRITICAL_RISKS = 2
OPEN_RNCS = 4
DAYS_WITHOUT_LEAVE = 263
PYRAMID = (0, 16, 31, 190, 1240)
ADHERENCE_PCT = D("92.9")
OTD_PCT = D("66.7")
PORTFOLIO_WEIGHTS = (D("55.36"), D("29.34"), D("15.30"))
EXPOSURE_CENTS = 340_000_000


def _project(context: OracleContext) -> Project:
    return context.session.scalars(select(Project).where(Project.code == PROJECT_CODE)).one()


def _scope(context: OracleContext) -> Scope:
    return Scope(project_id=_project(context).id, source="url")


def _admin(context: OracleContext) -> User:
    access = configuracoes.find_access_by_email(context.session, ADMIN_EMAIL)
    assert access is not None, "admin da demonstracao"
    return _user_of(access)


def _manager(context: OracleContext) -> User:
    access = next(
        item
        for item in configuracoes.list_active_access(context.session)
        if item.general_profile == "Gestor"
    )
    return _user_of(access)


def _panel(context: OracleContext):
    return painel_service.panel(
        context.session,
        user=_manager(context),
        scope=_scope(context),
        reference_date=context.reference_date,
        month=None,
        pyramid_kind=None,
    )


def _afirmar_a_manchete(context: OracleContext) -> None:
    session = context.session
    reference = context.reference_date
    scope = _scope(context)
    project = _project(context)

    budgets = financeiro.current_budgets(session)
    assert budgets[project.id] == BAC_CENTS, "BAC de R$ 44,6 mi no projeto 1"

    cost = financeiro.cost_kpis_overview(session, scope=scope, reference_date=reference)
    assert cost.indicators is not None
    assert cost.indicators.cpi == CPI, "CPI 0,96 no corte"
    assert cost.indicators.spi == SPI, "SPI de custo 0,94 no corte"

    mapa = financeiro.mapa_controle(session, scope=scope, reference_date=reference)
    assert mapa.total.projection_cents == PROJECTION_CENTS, (
        "projeção no término: a soma das projeções por item (4.525.500.000 centavos)"
    )
    millions = (D(mapa.total.projection_cents) / D(100_000_000)).quantize(
        D("0.01"), rounding=ROUND_HALF_UP
    )
    assert millions == PROJECTION_MI, "projeção no término de R$ 45,26 mi"

    counts = central_acoes.count_by_status(
        session, user=_admin(context), scope=scope, reference_date=reference
    )
    assert counts.overdue == OVERDUE_ACTIONS, "8 ações atrasadas no projeto 1"

    panel = _panel(context)
    accumulated = panel.accumulated_indicators
    assert accumulated is not None
    assert accumulated.days_without_leave == DAYS_WITHOUT_LEAVE, "263 dias sem afastamento"
    assert accumulated.pyramid == PYRAMID, "a pirâmide acumulada 0/16/31/190/1.240"

    purchases = suprimentos.list_panel(
        session, user=_admin(context), scope=scope, reference_date=reference
    )
    assert purchases.summary.orders.critical == CRITICAL_ORDERS, "3 pedidos críticos"
    assert purchases.summary.adherence_pct == ADHERENCE_PCT, "aderência ao plano de 92,9%"

    orders = suprimentos.list_orders(
        session,
        user=_admin(context),
        scope=scope,
        filters=suprimentos_validation.OrderFilters(situation="todos"),
        reference_date=reference,
    )
    assert orders.summary.otd == OTD_PCT, "OTD de 66,7%"

    summary = riscos.risk_summary(
        session,
        user=_admin(context),
        scope=scope,
        assessment="residual",
        reference_date=reference,
    )
    assert summary.top.total == CRITICAL_RISKS, "2 riscos críticos no residual"
    assert summary.exposure_cents == EXPOSURE_CENTS, "exposição de R$ 3,4 mi (ameaças)"

    reference_summary = qualidade.rnc_summary(
        session, user=_admin(context), scope=scope, reference_date=reference
    )
    assert reference_summary.active == OPEN_RNCS, "4 RNC abertas no projeto 1"

    weights = financeiro.portfolio_weights(session, reference_date=reference)
    projects = list(session.scalars(select(Project).order_by(Project.code)))
    assert [weights[item.id].weight for item in projects] == list(PORTFOLIO_WEIGHTS), (
        "os pesos da carteira 55,36 / 29,34 / 15,30"
    )


register_check("manchete: os numeros do cenario do HANDOVER", _afirmar_a_manchete)
