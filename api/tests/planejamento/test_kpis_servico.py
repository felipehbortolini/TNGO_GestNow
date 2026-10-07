"""Fachada dos KPIs de planejamento (ISSUE-040): SPI, avanço por área e carteira.

O cenário reproduz o do protótipo no projeto 1: cinco áreas da EAP com pesos 15/30/25/25/5 e
médias 98/96, 80/78, 70/66, 38/30 e 0/0, que fecham o previsto 65,7 e o real 61,8 no corte de
set/2026 — o SPI de 0,94 do oráculo. A curva congelada usa os mesmos números e as medições dos
pacotes fecham o real; o projeto 2 tem um pacote único em 100/100 e a carteira pondera 75/25
pelos orçamentos, como na ISSUE-039. O projeto 3 não tem curva e serve ao estado vazio.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from src.modulos.governanca.models import ChangeImpact, ChangeRequest
from src.modulos.planejamento import calculations, service
from src.modulos.planejamento.models import (
    CurvaFisicaMonth,
    CurvaFisicaRevision,
    EapItem,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
)
from tests.apoio_6wla import HOJE
from tests.identidades import criar_projeto

D = Decimal
PORTFOLIO = Scope(project_id=None, source="padrao")

JUL = date(2026, 7, 1)
AUG = date(2026, 8, 1)
SEP = date(2026, 9, 1)
OCT = date(2026, 10, 1)

MESES = (JUL, AUG, SEP, OCT)

AREAS = (
    ("1", "Engenharia", "15", "98", "96", date(2026, 12, 31)),
    ("2", "Suprimentos", "30", "80", "78", date(2026, 12, 31)),
    ("3", "Obras civis", "25", "70", "66", date(2026, 12, 31)),
    ("4", "Montagem eletromecânica", "25", "38", "30", date(2026, 8, 31)),
    ("5", "Comissionamento", "5", "0", "0", date(2026, 12, 31)),
)


@dataclass(frozen=True)
class CenarioKpis:
    """O projeto dos KPIs, o da carteira e o projeto sem curva, na transação do teste."""

    session: Session
    projeto: Project
    outro: Project
    sem_curva: Project
    itens: dict[str, EapItem]

    @property
    def escopo(self) -> Scope:
        return Scope(project_id=self.projeto.id, source="url")


def _item(
    session: Session,
    project: Project,
    code: str,
    description: str,
    parent: EapItem | None = None,
    **fields: object,
) -> EapItem:
    item = EapItem(
        project_id=project.id,
        parent_id=parent.id if parent is not None else None,
        code=code,
        description=description,
        level=len(code.split(".")),
        **fields,
    )
    session.add(item)
    session.flush()
    return item


def _medicao(session: Session, autor_id: int, item: EapItem, dia: date, para: str) -> None:
    session.add(
        EapMeasurement(
            item_id=item.id,
            author_id=autor_id,
            measured_on=dia,
            from_pct=D("0"),
            to_pct=D(para),
            note="Boletim",
        )
    )
    session.flush()


def _congelar(
    session: Session, projeto: Project, itens: Sequence[EapItem], *, baseline: Sequence[str]
) -> None:
    """A revisão 0 com os pesos congelados e a linha de base do mock, congelada à mão."""
    revisao = EapRevision(
        project_id=projeto.id,
        approved_by_id=projeto.manager_id,
        revision=0,
        revision_date=date(2026, 1, 5),
        alteration="Linha de base",
        justification="Linha de base aprovada no gate de investimento.",
    )
    session.add(revisao)
    session.flush()
    for item in itens:
        session.add(
            EapRevisionItem(revision_id=revisao.id, item_id=item.id, weight=item.weight or D(0))
        )
    curva = CurvaFisicaRevision(project_id=projeto.id, eap_revision_id=revisao.id)
    session.add(curva)
    session.flush()
    session.add_all(
        CurvaFisicaMonth(revision_id=curva.id, month=month, baseline_pct=D(value))
        for month, value in zip(MESES, baseline, strict=True)
    )
    session.flush()


def _montar_projeto(session: Session, projeto: Project) -> dict[str, EapItem]:
    """As cinco áreas do cenário, cada uma com o seu pacote de trabalho."""
    itens: dict[str, EapItem] = {}
    for code, nome, peso, previsto, real, termino in AREAS:
        area = _item(session, projeto, code, nome)
        pacote = _item(
            session,
            projeto,
            f"{code}.1.1",
            f"Pacote de {nome}",
            area,
            kind="Trabalho",
            criterion="Percentual estimado",
            weight=D(peso),
            predicted=D(previsto),
            estimated_pct=D(real),
            start=date(2026, 1, 1),
            finish=termino,
        )
        if D(real) > 0:
            _medicao(session, projeto.manager_id, pacote, date(2026, 8, 15), real)
        itens[code] = pacote
    return itens


def _montar_outro(session: Session, projeto: Project) -> EapItem:
    """O projeto da carteira: uma área e um pacote único em 100/100."""
    area = _item(session, projeto, "1", "Engenharia")
    pacote = _item(
        session,
        projeto,
        "1.1.1",
        "Pacote único",
        area,
        kind="Trabalho",
        criterion="Percentual estimado",
        weight=D("100"),
        predicted=D("100"),
        estimated_pct=D("100"),
        start=date(2026, 1, 1),
        finish=date(2026, 12, 31),
    )
    _medicao(session, projeto.manager_id, pacote, date(2026, 8, 15), "100")
    return pacote


def _mudanca(session: Session, projeto: Project) -> ChangeRequest:
    """A SM aprovada com impacto em escopo que nenhuma revisão incorporou."""
    change = ChangeRequest(
        project_id=projeto.id,
        requester_id=projeto.manager_id,
        code="SM-TN-2026-0400",
        title="Inclusão do sistema de tratamento de efluentes",
        kind="Escopo",
        origin="Cliente",
        priority="Normal",
        request_date=date(2026, 9, 1),
        description="Descrição da mudança de teste.",
        situation="Aprovada",
    )
    session.add(change)
    session.flush()
    session.add(
        ChangeImpact(
            change_id=change.id,
            analyst_id=projeto.manager_id,
            analysis_date=date(2026, 9, 10),
            cost_cents=0,
            term_days=0,
            scope="Nova unidade de tratamento",
            quality="Sem impacto",
            risks="Sem impacto",
            safety="Sem impacto",
            contract="Sem impacto",
            affects_contract_milestone=False,
        )
    )
    session.flush()
    return change


@pytest.fixture
def cenario_kpis(sessao: Session) -> CenarioKpis:
    """O cenário do protótipo na transação do teste: 65,7/61,8 no corte e a carteira 75/25."""
    projeto = criar_projeto(sessao, codigo="TN-KPI-001", nome="Fábrica dos KPIs")
    outro = criar_projeto(sessao, codigo="TN-KPI-002", nome="Caldeira dos KPIs")
    sem_curva = criar_projeto(sessao, codigo="TN-KPI-003", nome="Projeto sem curva")
    projeto.budget_cents = 75_000_000
    outro.budget_cents = 25_000_000
    sessao.flush()
    itens = _montar_projeto(sessao, projeto)
    _congelar(sessao, projeto, tuple(itens.values()), baseline=("50.0", "60.0", "65.7", "100.0"))
    item_outro = _montar_outro(sessao, outro)
    _congelar(sessao, outro, (item_outro,), baseline=("80.0", "90.0", "100.0", "100.0"))
    _mudanca(sessao, projeto)
    return CenarioKpis(
        session=sessao, projeto=projeto, outro=outro, sem_curva=sem_curva, itens=itens
    )


def _visao(cenario: CenarioKpis, scope: Scope | None = None) -> service.PlanningKpisOverview:
    return service.planning_kpis_overview(
        cenario.session, scope=scope or cenario.escopo, reference_date=HOJE
    )


# ── Cálculos puros ───────────────────────────────────────────────────────


def test_spi_sem_previsto_nao_tem_indice() -> None:
    assert calculations.spi_index(D("61.8"), D("0")) is None
    assert calculations.spi_index(D("61.8"), None) is None
    assert calculations.spi_index(None, D("65.7")) is None


def test_spi_com_real_zero_e_com_duas_casas() -> None:
    assert calculations.spi_index(D("0"), D("65.7")) == D("0.00")
    assert calculations.spi_index(D("61.8"), D("65.7")) == D("0.94")
    assert calculations.spi_index(D("70"), D("65.7")) == D("1.07")


def test_spi_por_mes_para_no_ultimo_mes_com_real() -> None:
    baseline = (D("50.0"), D("60.0"), D("65.7"), D("100.0"))
    real = (D("0.0"), D("61.8"), D("61.8"), None)

    assert calculations.spi_series(baseline, real) == (D("0.00"), D("1.03"), D("0.94"))


def test_spi_por_mes_marca_mes_sem_previsto() -> None:
    assert calculations.spi_series((D("0"), D("60.0")), (D("10.0"), None)) == (None,)


def test_spi_por_mes_sem_real_nenhum_sai_vazio() -> None:
    assert calculations.spi_series((D("50.0"),), (None,)) == ()
    assert calculations.spi_series((), ()) == ()


def test_a_contribuicao_da_area_e_o_peso_vezes_o_real() -> None:
    assert calculations.area_contribution(D("15"), D("96")) == D("14.4")
    assert calculations.area_contribution(D("25"), D("30")) == D("7.5")


# ── O projeto ────────────────────────────────────────────────────────────


def test_o_spi_do_projeto_e_o_oraculo_no_corte(cenario_kpis: CenarioKpis) -> None:
    visao = _visao(cenario_kpis)

    assert not visao.is_empty
    assert not visao.is_portfolio
    assert visao.indicators.cut_month == SEP
    assert visao.indicators.predicted == D("65.7")
    assert visao.indicators.actual == D("61.8")
    assert visao.indicators.deviation_pp == D("-3.9")
    assert visao.indicators.spi == D("0.94")
    assert visao.indicators.previous_spi == D("1.03")
    assert visao.indicators.baseline_finish == OCT
    assert visao.spi_series == (D("0.00"), D("1.03"), D("0.94"))


def test_as_areas_batem_com_a_arvore_e_fecham_com_a_curva(cenario_kpis: CenarioKpis) -> None:
    visao = _visao(cenario_kpis)

    rows = {row.code: row for row in visao.rows}
    assert [row.code for row in visao.rows] == ["1", "2", "3", "4", "5"]
    engenharia = rows["1"]
    assert (engenharia.name, engenharia.weight) == ("Engenharia", D("15"))
    assert (engenharia.predicted, engenharia.actual) == (D("98"), D("96"))
    assert (engenharia.deviation_pp, engenharia.spi) == (D("-2.0"), D("0.98"))
    assert engenharia.contribution_pp == D("14.4")
    assert (rows["3"].band, rows["4"].band) == ("warning", "danger")
    assert rows["5"].spi is None
    previsto = calculations.eap_weighted_progress(
        [calculations.EapWeightedValue(row.weight, row.predicted) for row in visao.rows]
    )
    real = calculations.eap_weighted_progress(
        [calculations.EapWeightedValue(row.weight, row.actual) for row in visao.rows]
    )
    assert previsto == visao.indicators.predicted
    assert real == visao.indicators.actual
    assert sum((row.contribution_pp for row in visao.rows), D(0)) == visao.indicators.actual


def test_o_maior_desvio_aponta_a_area(cenario_kpis: CenarioKpis) -> None:
    visao = _visao(cenario_kpis)

    assert visao.worst is not None
    assert (visao.worst.code, visao.worst.name, visao.worst.deviation_pp) == (
        "4",
        "Montagem eletromecânica",
        D("-8.0"),
    )


def test_os_indicadores_da_eap_entram_na_visao(cenario_kpis: CenarioKpis) -> None:
    visao = _visao(cenario_kpis)

    assert visao.overdue_packages == 1
    assert visao.pending_changes == 1


# ── A carteira ───────────────────────────────────────────────────────────


def test_o_portfolio_pondera_pelos_pesos_da_carteira(cenario_kpis: CenarioKpis) -> None:
    visao = _visao(cenario_kpis, PORTFOLIO)

    assert visao.is_portfolio
    assert not visao.is_empty
    assert visao.project_id is None
    assert visao.indicators.spi == D("0.96")
    assert visao.overdue_packages == 1
    assert visao.pending_changes == 1
    rows = {row.code: row for row in visao.rows}
    assert set(rows) == {"TN-KPI-001", "TN-KPI-002"}
    fabrica = rows["TN-KPI-001"]
    assert (fabrica.weight, fabrica.predicted, fabrica.actual, fabrica.spi) == (
        D("75.00"),
        D("65.7"),
        D("61.8"),
        D("0.94"),
    )
    assert fabrica.contribution_pp == D("46.4")
    caldeira = rows["TN-KPI-002"]
    assert (caldeira.weight, caldeira.predicted, caldeira.actual, caldeira.spi) == (
        D("25.00"),
        D("100"),
        D("100"),
        D("1.00"),
    )
    assert caldeira.contribution_pp == D("25.0")
    assert visao.worst is not None
    assert visao.worst.code == "TN-KPI-001"
    soma = sum((row.weight * row.predicted for row in visao.rows), D(0))
    divisor = sum((row.weight for row in visao.rows), D(0))
    assert visao.indicators.predicted == (soma / divisor).quantize(D("0.1"))


# ── O vazio e os gráficos ────────────────────────────────────────────────


def test_sem_curva_a_visao_sai_vazia(cenario_kpis: CenarioKpis) -> None:
    visao = service.planning_kpis_overview(
        cenario_kpis.session,
        scope=Scope(project_id=cenario_kpis.sem_curva.id, source="url"),
        reference_date=HOJE,
    )

    assert visao.is_empty
    assert visao.rows == ()
    assert visao.worst is None
    assert visao.indicators.spi is None
    assert visao.spi_series == ()
    assert visao.spi_chart["periodos"] == []
    assert visao.comparison_chart["paineis"] == []


def test_os_graficos_seguem_o_contrato_da_biblioteca(cenario_kpis: CenarioKpis) -> None:
    visao = _visao(cenario_kpis)

    spi = visao.spi_chart
    assert spi["base_zero"] is False
    assert spi["casas"] == 2
    assert [serie["id"] for serie in spi["series"]] == ["spi"]
    assert spi["referencias"] == [{"valor": 1, "rotulo": "Meta (1,00)", "papel": "linha-base"}]
    assert [(item["ano"], item["mes"]) for item in spi["periodos"]] == [
        (2026, 7),
        (2026, 8),
        (2026, 9),
    ]
    assert [item["valores"]["spi"] for item in spi["periodos"]] == [0.0, 1.03, 0.94]

    painel = visao.comparison_chart["paineis"][0]
    assert [linha["rotulo"] for linha in painel["linhas"]] == ["Previsto", "Real"]
    assert [categoria["id"] for categoria in painel["categorias"]] == ["1", "2", "3", "4", "5"]
    assert all(categoria["favoravel"] == "sobe" for categoria in painel["categorias"])
    assert painel["categorias"][3]["papel"] == "erro"
    assert painel["linhas"][0]["valores"]["1"] == 98.0
    assert painel["linhas"][1]["valores"]["1"] == 96.0


def test_o_grafico_da_carteira_usa_o_codigo_do_projeto(cenario_kpis: CenarioKpis) -> None:
    visao = _visao(cenario_kpis, PORTFOLIO)

    painel = visao.comparison_chart["paineis"][0]
    rotulos = {categoria["id"]: categoria["rotulo"] for categoria in painel["categorias"]}
    assert rotulos == {"TN-KPI-001": "TN-KPI-001", "TN-KPI-002": "TN-KPI-002"}
    assert painel["linhas"][1]["valores"]["TN-KPI-001"] == 61.8
