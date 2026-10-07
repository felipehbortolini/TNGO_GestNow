"""Fachada dos KPIs de custo (ISSUE-042, HU-092): corte, série mês a mês e carteira.

O cenário de 25/09/2026 vem do protótipo: BAC de R$ 44,6 mi na revisão congelada, EV de 61,8%
do avanço físico real sobre o BAC, PV de 65,7% da linha de base e AC de R$ 28,7 mi dão CPI 0,96
e SPI de custo 0,94; a projeção no término de R$ 45,25 mi dá o VAC de menos R$ 655 mil, o
comprometido fecha 92,2% do orçamento e a contingência consumida, 15,0%. A série acumula os
índices até cada mês (o anterior do corte aparece como variação) e a carteira soma o PV, o EV e
o AC dos projetos, com o CPI e o SPI saindo da soma.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.core.scope import Scope
from src.modulos.financeiro import calculations, service
from src.modulos.financeiro.models import (
    CurvaFinanceiraMonth,
    CurvaFinanceiraRevision,
    EacRevision,
    EacRevisionItem,
    Reserve,
    ReserveMovement,
)
from src.modulos.planejamento import service as planejamento
from src.modulos.planejamento.models import EapItem, EapMeasurement, EapRevision, EapRevisionItem
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario

D = Decimal
HOJE = REFERENCE_DATE
PORTFOLIO = Scope(project_id=None, source="padrao")
JUSTIFICATIVA = "Revisão de teste dos KPIs de custo."
BAC = 4_460_000_000
EV = 2_756_280_000
PV = 2_930_220_000
AC = 2_870_000_000
PROJECTION = 4_525_500_000
SECOND_TOTAL = 2_000_000_000

PROFILE = (
    D("2.1"),
    D("5.4"),
    D("10.2"),
    D("16.8"),
    D("24.5"),
    D("33.0"),
    D("42.1"),
    D("54.0"),
    D("65.7"),
    D("75.8"),
    D("84.2"),
    D("90.6"),
    D("95.1"),
    D("98.4"),
    D("100"),
    D("100"),
)
MONTHS = (
    date(2026, 1, 1),
    date(2026, 2, 1),
    date(2026, 3, 1),
    date(2026, 4, 1),
    date(2026, 5, 1),
    date(2026, 6, 1),
    date(2026, 7, 1),
    date(2026, 8, 1),
    date(2026, 9, 1),
    date(2026, 10, 1),
    date(2026, 11, 1),
    date(2026, 12, 1),
    date(2027, 1, 1),
    date(2027, 2, 1),
    date(2027, 3, 1),
    date(2027, 4, 1),
)
PLANNED = calculations.curva_financeira_planejado(PROFILE, BAC)
REAL_PCT = ("2.1", "5.4", "10.2", "16.8", "24.5", "33.0", "42.1", "54.0", "61.8")
COMMITTED_DELTAS = (
    448_000_000,
    920_000_000,
    0,
    652_000_000,
    480_000_000,
    800_000_000,
    400_000_000,
    260_000_000,
    153_000_000,
)
ACTUAL_DELTAS = (
    90_000_000,
    155_000_000,
    195_000_000,
    260_000_000,
    310_000_000,
    350_000_000,
    400_000_000,
    520_000_000,
    590_000_000,
)
SECOND_MONTHS = tuple(date(2026, mes, 1) for mes in range(1, 13))
SECOND_PLANNED = tuple(SECOND_TOTAL * (index + 1) // 12 for index in range(12))
SECOND_REAL_PCT = ("10", "15", "20", "25", "30", "35", "40", "45", "50")


def _escopo(project) -> Scope:
    return Scope(project_id=project.id, source="url")


def _visao(cenario: EacScenario, scope: Scope | None = None) -> service.CostKpisOverview:
    return service.cost_kpis_overview(
        cenario.session, scope=scope or _escopo(cenario.first), reference_date=HOJE
    )


def _fisica(cenario: EacScenario, *, project=None, real_pct=REAL_PCT) -> None:
    """O pacote com as medições mensais até setembro e a curva física congelada."""
    projeto = project or cenario.first
    session = cenario.session
    item = EapItem(
        project_id=projeto.id,
        code="1.1.1",
        description="Estacas",
        level=3,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("100"),
        predicted=D("100"),
        start=date(2026, 1, 1),
        finish=date(2026, 12, 31),
        quantity=D("100"),
        executed=D("100"),
    )
    session.add(item)
    session.flush()
    revision = EapRevision(
        project_id=projeto.id,
        approved_by_id=projeto.manager_id,
        revision=0,
        revision_date=date(2026, 1, 5),
        alteration="Linha de base",
        justification="Linha de base aprovada no teste dos KPIs.",
    )
    session.add(revision)
    session.flush()
    session.add(EapRevisionItem(revision_id=revision.id, item_id=item.id, weight=D("100")))
    for index, pct in enumerate(real_pct):
        session.add(
            EapMeasurement(
                item_id=item.id,
                author_id=cenario.member.person_id,
                measured_on=date(2026, index + 1, 15),
                from_pct=D("0"),
                to_pct=D(pct),
                note="Boletim",
            )
        )
    session.flush()
    planejamento.freeze_curve(
        session, project_id=projeto.id, revision_id=revision.id, reference_date=HOJE
    )


def _financeira(cenario: EacScenario, *, project=None, total_cents: int, months, planned) -> None:
    """A revisão da EAC e a curva financeira congelada com o planejado exato do cenário."""
    projeto = project or cenario.first
    session = cenario.session
    record = EacRevision(
        project_id=projeto.id,
        change_id=None,
        approved_by_id=projeto.manager_id,
        revision=0,
        revision_date=date(2026, 1, 5),
        justification=JUSTIFICATIVA,
    )
    session.add(record)
    session.flush()
    session.add(
        EacRevisionItem(
            revision_id=record.id,
            item_id=cenario.items[f"{projeto.code}:1.1.1"],
            base_cents=total_cents,
        )
    )
    session.flush()
    curve = CurvaFinanceiraRevision(project_id=projeto.id, eac_revision_id=record.id)
    session.add(curve)
    session.flush()
    session.add_all(
        CurvaFinanceiraMonth(revision_id=curve.id, month=month, planned_cents=value)
        for month, value in zip(months, planned, strict=True)
    )
    session.flush()


def _erp_projeto(cenario: EacScenario) -> None:
    linhas = tuple(
        service.ErpCostLine(
            item_id=cenario.items[f"{cenario.first.code}:1.1.1"],
            month=date(2026, index + 1, 1),
            committed_cents=committed,
            actual_cents=actual,
            projection_cents=PROJECTION if index == len(ACTUAL_DELTAS) - 1 else None,
        )
        for index, (committed, actual) in enumerate(
            zip(COMMITTED_DELTAS, ACTUAL_DELTAS, strict=True)
        )
    )
    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.first.id,
        linhas=linhas,
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )


def _erp_segundo(cenario: EacScenario) -> None:
    item_id = cenario.items[f"{cenario.second.code}:1.1.1"]
    linhas = (
        service.ErpCostLine(
            item_id=item_id,
            month=date(2026, 1, 1),
            committed_cents=1_200_000_000,
            actual_cents=100_000_000,
        ),
        *(
            service.ErpCostLine(
                item_id=item_id,
                month=date(2026, index, 1),
                actual_cents=100_000_000,
            )
            for index in range(2, 10)
        ),
    )
    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.second.id,
        linhas=linhas,
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )


def _reserva(cenario: EacScenario) -> None:
    session = cenario.session
    reserve = Reserve(
        project_id=cenario.first.id,
        kind=calculations.RESERVE_CONTINGENCY,
        calculation_basis="Constituída na linha de base do projeto.",
    )
    session.add(reserve)
    session.flush()
    session.add(
        ReserveMovement(
            reserve_id=reserve.id,
            change_id=None,
            registered_by_id=cenario.member.person_id,
            kind=calculations.MOVEMENT_CONSTITUTION,
            registered_on=date(2026, 1, 5),
            value_cents=20_000_000,
            justification="Constituída na linha de base do projeto.",
        )
    )
    session.add(
        ReserveMovement(
            reserve_id=reserve.id,
            change_id=None,
            registered_by_id=cenario.member.person_id,
            kind=calculations.MOVEMENT_CONSUMPTION,
            registered_on=date(2026, 5, 10),
            value_cents=-3_000_000,
            justification="Consumo aprovado na SM.",
        )
    )
    session.flush()


@pytest.fixture
def cenario_custo(cenario: EacScenario) -> EacScenario:
    _fisica(cenario)
    _financeira(cenario, total_cents=BAC, months=MONTHS, planned=PLANNED)
    _erp_projeto(cenario)
    _reserva(cenario)
    return cenario


# ── KPIs do corte ────────────────────────────────────────────────────────


def test_kpis_do_corte_com_os_numeros_do_cenario(cenario_custo: EacScenario) -> None:
    view = _visao(cenario_custo)

    assert not view.is_empty
    assert view.cut_month == date(2026, 9, 1)
    assert view.budget_cents == BAC
    assert view.actual is not None
    assert (view.actual.ev_cents, view.actual.pv_cents, view.actual.ac_cents) == (EV, PV, AC)
    assert view.indicators is not None
    assert view.indicators.cpi == D("0.96")
    assert view.indicators.spi == D("0.94")
    assert view.indicators.cv_cents == -113_720_000
    assert view.indicators.sv_cents == -173_940_000
    assert view.indicators.eac_by_cpi_cents == 4_644_012_945
    assert view.indicators.tcpi == D("1.07")
    assert view.projection_cents == PROJECTION
    assert view.vac_cents == -65_500_000
    assert view.committed_cents == 4_113_000_000
    assert view.committed_pct == D("92.2")
    assert view.contingency_total_cents == 20_000_000
    assert view.contingency_consumed_cents == 3_000_000
    assert view.contingency_pct == D("15.0")
    assert view.projects == ()


def test_variacao_mes_a_mes_e_tabela_de_valor_agregado(cenario_custo: EacScenario) -> None:
    view = _visao(cenario_custo)

    assert [row.month for row in view.history] == [date(2026, mes, 1) for mes in range(1, 10)]
    assert view.previous is not None
    assert view.previous.month == date(2026, 8, 1)
    assert view.previous.pv_cents == 2_408_400_000
    assert view.previous.ev_cents == 2_408_400_000
    assert view.previous.ac_cents == 2_280_000_000
    assert view.previous.cpi == D("1.06")
    assert view.previous.spi == D("1.00")
    assert view.actual is not None
    assert view.actual.eac_by_cpi_cents == 4_644_012_945
    assert view.actual.tcpi == D("1.07")
    assert view.history[0].month == date(2026, 1, 1)
    assert view.history[-1].month == date(2026, 9, 1)


# ── Carteira ─────────────────────────────────────────────────────────────


def test_carteira_soma_pv_ev_ac_e_os_indices_da_soma(cenario_custo: EacScenario) -> None:
    _fisica(cenario_custo, project=cenario_custo.second, real_pct=SECOND_REAL_PCT)
    _financeira(
        cenario_custo,
        project=cenario_custo.second,
        total_cents=SECOND_TOTAL,
        months=SECOND_MONTHS,
        planned=SECOND_PLANNED,
    )
    _erp_segundo(cenario_custo)

    carteira = _visao(cenario_custo, PORTFOLIO)

    budget = BAC + SECOND_TOTAL
    ev = EV + 1_000_000_000
    pv = PV + 1_500_000_000
    ac = AC + 900_000_000
    assert carteira.is_portfolio
    assert carteira.scope_label == "Portfólio"
    assert carteira.budget_cents == budget
    assert carteira.actual is not None
    assert (carteira.actual.ev_cents, carteira.actual.pv_cents, carteira.actual.ac_cents) == (
        ev,
        pv,
        ac,
    )
    assert carteira.indicators == calculations.cost_indicators(
        bac_cents=budget, ev_cents=ev, pv_cents=pv, ac_cents=ac
    )
    assert carteira.indicators is not None
    assert carteira.indicators.cpi == calculations.cost_performance_index(ev, ac)
    assert carteira.indicators.spi == calculations.cost_schedule_index(ev, pv)
    assert carteira.projection_cents == PROJECTION + SECOND_TOTAL
    assert carteira.vac_cents == -65_500_000
    assert carteira.committed_cents == 4_113_000_000 + 1_200_000_000
    assert carteira.committed_pct == D("82.2")
    assert carteira.contingency_pct == D("15.0")
    assert [row.month for row in carteira.history] == [date(2026, mes, 1) for mes in range(1, 10)]
    assert len(carteira.projects) == 2
    assert carteira.projects[0].project_code == "TN-EAC-001"
    assert carteira.projects[0].cpi == D("0.96")
    assert carteira.projects[0].projection_cents == PROJECTION
    assert carteira.projects[0].vac_cents == -65_500_000
    assert carteira.projects[0].contingency_pct == D("15.0")
    assert carteira.projects[1].project_code == "TN-EAC-002"
    assert carteira.projects[1].ev_cents == 1_000_000_000
    assert carteira.projects[1].ac_cents == 900_000_000
    assert carteira.projects[1].contingency_pct is None


# ── Vazio de origem ──────────────────────────────────────────────────────


def test_vazio_de_origem_sem_curva(cenario: EacScenario) -> None:
    projeto = _visao(cenario)
    carteira = _visao(cenario, PORTFOLIO)

    assert projeto.is_empty
    assert projeto.indicators is None
    assert projeto.history == ()
    assert projeto.previous is None
    assert carteira.is_empty
    assert carteira.projects == ()


def test_sem_curva_financeira_o_corte_e_vazio(cenario: EacScenario) -> None:
    _fisica(cenario)

    view = _visao(cenario)

    assert view.is_empty
    assert view.cut_month is None
    assert view.history == ()
