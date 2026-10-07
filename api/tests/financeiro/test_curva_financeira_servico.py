"""Fachada da Curva S financeira (ISSUE-042, HU-093): congelamento e leitura.

O congelamento entra no ``create_revision`` da EAC, na mesma transação: o planejado de cada mês é
o total da revisão distribuído pelo perfil da curva física vigente — ou pela distribuição linear
das datas dos pacotes da EAP quando ela não existe — e a revisão nova recongela sem apagar a
anterior. A leitura une os meses do planejado com os do ERP, acumula comprometido e realizado até
o corte, calcula a tendência sem dado posterior ao corte e soma os projetos na carteira.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from src.core.rbac import GeneralProfile
from src.core.scope import Scope
from src.modulos.financeiro import calculations, service
from src.modulos.financeiro.models import (
    CurvaFinanceiraMonth,
    CurvaFinanceiraRevision,
    EacRevision,
    EacRevisionItem,
)
from src.modulos.governanca.models import ChangeImpact, ChangeRequest
from src.modulos.planejamento import service as planejamento
from src.modulos.planejamento.models import EapItem, EapMeasurement, EapRevision, EapRevisionItem
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario, user_of

D = Decimal
HOJE = REFERENCE_DATE
PORTFOLIO = Scope(project_id=None, source="padrao")
JUSTIFICATIVA = "Revisão de teste da Curva S financeira."
MESES_2026 = tuple(date(2026, mes, 1) for mes in range(1, 13))


def _escopo(project) -> Scope:
    return Scope(project_id=project.id, source="url")


def _gestor(cenario: EacScenario):
    return user_of(cenario.manager, cenario.session, GeneralProfile.MANAGER)


def _visao(cenario: EacScenario, scope: Scope | None = None) -> service.FinancialCurveOverview:
    return service.financial_curve_overview(
        cenario.session, scope=scope or _escopo(cenario.first), reference_date=HOJE
    )


def _pacote(cenario: EacScenario, *, project=None) -> EapItem:
    """O pacote de nível 3 com peso 100 e as datas do ano, sem revisão congelada."""
    projeto = project or cenario.first
    session = cenario.session
    area = EapItem(project_id=projeto.id, code="1", description="Obra civil", level=1)
    session.add(area)
    session.flush()
    sub = EapItem(
        project_id=projeto.id, parent_id=area.id, code="1.1", description="Fundações", level=2
    )
    session.add(sub)
    session.flush()
    item = EapItem(
        project_id=projeto.id,
        parent_id=sub.id,
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
    return item


def _curva_fisica(cenario: EacScenario, *, project=None, to_pct: str = "61.8") -> EapRevision:
    """A curva física congelada do projeto, com a medição de setembro."""
    projeto = project or cenario.first
    session = cenario.session
    item = _pacote(cenario, project=projeto)
    revision = EapRevision(
        project_id=projeto.id,
        approved_by_id=projeto.manager_id,
        revision=0,
        revision_date=date(2026, 1, 5),
        alteration="Linha de base",
        justification="Linha de base aprovada no teste da curva.",
    )
    session.add(revision)
    session.flush()
    session.add(EapRevisionItem(revision_id=revision.id, item_id=item.id, weight=D("100")))
    session.add(
        EapMeasurement(
            item_id=item.id,
            author_id=cenario.member.person_id,
            measured_on=date(2026, 9, 15),
            from_pct=D("0"),
            to_pct=D(to_pct),
            note="Boletim",
        )
    )
    session.flush()
    planejamento.freeze_curve(
        session, project_id=projeto.id, revision_id=revision.id, reference_date=HOJE
    )
    return revision


def _sm_aprovada(
    cenario: EacScenario, *, valor_cents: int, code: str = "SM-TN-2026-0420"
) -> ChangeRequest:
    session = cenario.session
    change = ChangeRequest(
        project_id=cenario.first.id,
        requester_id=cenario.member.person_id,
        code=code,
        title="Inclusão de escopo com custo",
        kind="Custo",
        origin="Cliente",
        priority="Normal",
        request_date=date(2026, 9, 1),
        description=JUSTIFICATIVA,
        situation="Aprovada",
    )
    session.add(change)
    session.flush()
    session.add(
        ChangeImpact(
            change_id=change.id,
            analyst_id=cenario.member.person_id,
            analysis_date=date(2026, 9, 2),
            cost_cents=valor_cents,
            term_days=0,
            scope="Sem impacto",
            quality="Sem impacto",
            risks="Sem impacto",
            safety="Sem impacto",
            contract="Sem impacto",
            affects_contract_milestone=False,
        )
    )
    session.flush()
    return change


def _congelar(cenario: EacScenario, *, total_cents: int, project=None) -> EacRevision:
    """A revisão da EAC congelada direto no teste, para a leitura da curva."""
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
    service.freeze_financial_curve(session, revision=record)
    session.flush()
    return record


def _erp(cenario: EacScenario, *, deltas, project=None) -> None:
    """Os fatos do ERP de janeiro em diante, um por mês, no item 1.1.1."""
    projeto = project or cenario.first
    linhas = tuple(
        service.ErpCostLine(
            item_id=cenario.items[f"{projeto.code}:1.1.1"],
            month=date(2026, index + 1, 1),
            committed_cents=committed,
            actual_cents=actual,
        )
        for index, (committed, actual) in enumerate(deltas)
    )
    service.import_erp_costs(
        cenario.session,
        projeto_id=projeto.id,
        linhas=linhas,
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )


def _registros(cenario: EacScenario, *, project=None) -> list[CurvaFinanceiraRevision]:
    projeto = project or cenario.first
    return list(
        cenario.session.scalars(
            select(CurvaFinanceiraRevision)
            .where(CurvaFinanceiraRevision.project_id == projeto.id)
            .order_by(CurvaFinanceiraRevision.id)
        )
    )


def _meses(session, record: CurvaFinanceiraRevision) -> list[date]:
    rows = session.scalars(
        select(CurvaFinanceiraMonth)
        .where(CurvaFinanceiraMonth.revision_id == record.id)
        .order_by(CurvaFinanceiraMonth.month)
    )
    return [row.month for row in rows]


def _planejado(session, record: CurvaFinanceiraRevision) -> list[int]:
    rows = session.scalars(
        select(CurvaFinanceiraMonth)
        .where(CurvaFinanceiraMonth.revision_id == record.id)
        .order_by(CurvaFinanceiraMonth.month)
    )
    return [row.planned_cents for row in rows]


# ── Congelamento ─────────────────────────────────────────────────────────


def test_congela_no_create_revision_e_recongela_na_revisao_nova(cenario: EacScenario) -> None:
    _curva_fisica(cenario)
    perfil = planejamento.curva_fisica_overview(
        cenario.session, scope=_escopo(cenario.first), reference_date=HOJE
    ).series

    primeira_sm = _sm_aprovada(cenario, valor_cents=100_000)
    primeira = service.create_revision(
        cenario.session,
        user=_gestor(cenario),
        scope=_escopo(cenario.first),
        request=service.RevisionRequest(
            change_id=primeira_sm.id,
            justification=JUSTIFICATIVA,
            adjustments=(service.AdjustmentRequest(code="1.1.1", delta_cents=100_000),),
        ),
        reference_date=HOJE,
    )

    registros = _registros(cenario)
    assert len(registros) == 1
    assert registros[0].eac_revision_id == primeira.id
    assert _meses(cenario.session, registros[0]) == list(perfil.months)
    esperado = list(calculations.curva_financeira_planejado(perfil.baseline, primeira.total_cents))
    assert _planejado(cenario.session, registros[0]) == esperado
    assert esperado[-1] == primeira.total_cents

    segunda_sm = _sm_aprovada(cenario, valor_cents=50_000, code="SM-TN-2026-0421")
    segunda = service.create_revision(
        cenario.session,
        user=_gestor(cenario),
        scope=_escopo(cenario.first),
        request=service.RevisionRequest(
            change_id=segunda_sm.id,
            justification=JUSTIFICATIVA,
            adjustments=(service.AdjustmentRequest(code="1.1.2", delta_cents=50_000),),
        ),
        reference_date=HOJE,
    )

    registros = _registros(cenario)
    assert [registro.eac_revision_id for registro in registros] == [primeira.id, segunda.id]
    assert _planejado(cenario.session, registros[0]) == esperado, "a curva antiga fica"
    assert _planejado(cenario.session, registros[1]) == list(
        calculations.curva_financeira_planejado(perfil.baseline, segunda.total_cents)
    )


def test_sem_curva_fisica_o_perfil_vem_das_datas_da_eap(cenario: EacScenario) -> None:
    _pacote(cenario)

    sm = _sm_aprovada(cenario, valor_cents=100_000)
    revisao = service.create_revision(
        cenario.session,
        user=_gestor(cenario),
        scope=_escopo(cenario.first),
        request=service.RevisionRequest(
            change_id=sm.id,
            justification=JUSTIFICATIVA,
            adjustments=(service.AdjustmentRequest(code="1.1.1", delta_cents=100_000),),
        ),
        reference_date=HOJE,
    )

    registros = _registros(cenario)
    assert len(registros) == 1
    assert _meses(cenario.session, registros[0]) == list(MESES_2026)
    perfil = planejamento.linear_curve_profile(
        cenario.session, project_id=cenario.first.id, reference_date=HOJE
    )
    assert perfil is not None
    assert _planejado(cenario.session, registros[0]) == list(
        calculations.curva_financeira_planejado(perfil[1], revisao.total_cents)
    )
    assert _planejado(cenario.session, registros[0])[0] == 582_282
    assert _planejado(cenario.session, registros[0])[-1] == revisao.total_cents == 7_101_000


def test_sem_curva_nem_datas_nao_congela(cenario: EacScenario) -> None:
    sm = _sm_aprovada(cenario, valor_cents=100_000)
    service.create_revision(
        cenario.session,
        user=_gestor(cenario),
        scope=_escopo(cenario.first),
        request=service.RevisionRequest(change_id=sm.id, justification=JUSTIFICATIVA),
        reference_date=HOJE,
    )

    assert _registros(cenario) == []
    assert _visao(cenario).is_empty


# ── Leitura ──────────────────────────────────────────────────────────────


def test_serie_acumulada_com_os_fatos_do_erp(cenario: EacScenario) -> None:
    _curva_fisica(cenario)
    _congelar(cenario, total_cents=100_000_000)
    _erp(cenario, deltas=[(5_000_000, 3_000_000)] * 8)

    view = _visao(cenario)
    series = view.series

    assert view.revision == 0
    assert series.months == MESES_2026
    assert series.cut_index == 8
    assert series.planned[0] == 8_200_000
    assert series.planned[8] == 73_400_000
    assert series.planned[-1] == 100_000_000
    assert series.actual[0] == 3_000_000
    assert series.actual[7] == 24_000_000
    assert series.actual[8] == 24_000_000
    assert series.actual[9] is None
    assert series.committed[7] == 40_000_000
    assert series.committed[9] is None
    assert view.points[8].is_cut
    assert view.kpis is not None
    assert (
        view.kpis.budget_cents,
        view.kpis.planned_cents,
        view.kpis.actual_cents,
    ) == (100_000_000, 73_400_000, 24_000_000)
    assert view.kpis.committed_cents == 40_000_000
    assert view.kpis.deviation_cents == 24_000_000 - 73_400_000
    assert view.kpis.committed_pct == D("40.0")


def test_tendencia_nao_usa_dado_posterior_ao_corte(cenario: EacScenario) -> None:
    _curva_fisica(cenario)
    _congelar(cenario, total_cents=100_000_000)
    _erp(cenario, deltas=[(5_000_000, 3_000_000)] * 8)

    antes = _visao(cenario)
    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.first.id,
        linhas=(
            service.ErpCostLine(
                item_id=cenario.items[f"{cenario.first.code}:1.1.1"],
                month=date(2026, 10, 1),
                committed_cents=99_000_000,
                actual_cents=99_000_000,
            ),
        ),
        importado_por_id=cenario.member.person_id,
        hoje=date(2026, 10, 31),
    )
    depois = _visao(cenario)

    assert antes.series.trend == depois.series.trend
    assert antes.series.trend[:8] == (None,) * 8
    assert antes.series.trend[8] == 24_000_000
    assert antes.series.trend[-1] == calculations.estimate_at_completion_by_cpi(
        100_000_000, 61_800_000, 24_000_000
    )
    assert depois.series.actual[9] is None
    assert depois.series.committed[9] is None
    assert depois.points[9].trend_cents == depois.series.trend[9]


def test_carteira_soma_os_projetos(cenario: EacScenario) -> None:
    _curva_fisica(cenario)
    _congelar(cenario, total_cents=100_000_000)
    _erp(cenario, deltas=[(5_000_000, 3_000_000)] * 8)
    _curva_fisica(cenario, project=cenario.second, to_pct="50")
    _congelar(cenario, project=cenario.second, total_cents=50_000_000)
    _erp(cenario, project=cenario.second, deltas=[(2_000_000, 1_000_000)] * 8)

    projeto = _visao(cenario)
    outro = _visao(cenario, _escopo(cenario.second))
    carteira = _visao(cenario, PORTFOLIO)

    assert carteira.kpis is not None
    assert carteira.kpis.budget_cents == 150_000_000
    assert carteira.series.months == MESES_2026
    for index in range(len(MESES_2026)):
        assert (
            carteira.series.planned[index]
            == projeto.series.planned[index] + outro.series.planned[index]
        )
    assert carteira.series.actual[7] == 24_000_000 + 8_000_000
    assert carteira.series.committed[7] == 40_000_000 + 16_000_000
    assert carteira.series.actual[8] == 24_000_000 + 8_000_000
    assert carteira.series.actual[9] is None
    assert carteira.series.trend[-1] == projeto.series.trend[-1] + outro.series.trend[-1]
    assert carteira.points[8].is_cut
    assert carteira.kpis.committed_pct is not None


def test_sem_curva_a_carteira_e_vazia(cenario: EacScenario) -> None:
    carteira = _visao(cenario, PORTFOLIO)

    assert carteira.is_portfolio
    assert carteira.is_empty
    assert carteira.kpis is None
