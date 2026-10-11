"""Oráculo do Início (ISSUE-079 e ISSUE-080): os números do protótipo em 25/09/2026.

Na demonstração com a data injetada, o projeto 1 (TN-2026-014) tem os números do cenário do
HANDOVER: 8 ações atrasadas, SPI 0,94, CPI 0,96, 3 pedidos críticos, 2 riscos críticos, 4 RNC
abertas, 263 dias sem acidentes com afastamento e 3 mudanças aguardando comitê. Os pontos de
atenção que os dados sustentam aparecem calculados: o claim CLM-TN-2026-0003 notificado fora do
prazo (56 dias entre evento e notificação), a RNC-TN-2026-0004 com o prazo de tratamento vencido,
o RSK-TN-2026-0003 com a revisão vencida, os três sistemas bloqueados por item A e a ocorrência
de alto potencial (HiPo) do mês. No Portfólio os consolidados somam 14 ações atrasadas, 4 pedidos
críticos, 4 riscos críticos, 7 RNC abertas e 5 mudanças aguardando comitê.

A carteira do Portfólio traz os pesos do protótipo — fábrica 55,36%, caldeira 29,34% e torre
15,30%, fechados em 100,00% — e cada linha repete os números do Início do projeto (SPI, CPI,
pedidos, riscos e ações). A prévia com os critérios vigentes devolve os mesmos pesos.
"""

from __future__ import annotations

from decimal import Decimal

from src.core.scope import Scope
from src.modulos.inicio import calculations, service
from tests.inicio.conftest import Demonstracao

CARTEIRA_EXPECTED = (
    ("TN-2026-014", Decimal("55.36")),
    ("TN-2026-021", Decimal("29.34")),
    ("TN-2026-027", Decimal("15.30")),
)

PROJECT_EXPECTED = {
    "acoes": 8,
    "spi": Decimal("0.94"),
    "cpi": Decimal("0.96"),
    "pedidos": 3,
    "riscos": 2,
    "rncs": 4,
    "hse": 263,
    "mudancas": 3,
}

PORTFOLIO_EXPECTED = {
    "acoes": 14,
    "spi": Decimal("0.94"),
    "cpi": Decimal("0.97"),
    "pedidos": 4,
    "riscos": 4,
    "rncs": 7,
    "hse": 263,
    "mudancas": 5,
}


def _afirmar_os_numeros(visao: service.HomeOverview, expected: dict[str, object]) -> None:
    kpis = {kpi.key: kpi for kpi in visao.kpis}
    for key, value in expected.items():
        assert kpis[key].export_value == value, f"{key} no corte"


def test_oraculo_do_inicio_do_projeto_1(demonstracao: Demonstracao) -> None:
    visao = service.home_overview(
        demonstracao.session,
        user=demonstracao.admin,
        scope=Scope(project_id=demonstracao.project_id, source="url"),
        reference_date=demonstracao.reference_date,
    )

    _afirmar_os_numeros(visao, PROJECT_EXPECTED)

    kpis = {kpi.key: kpi for kpi in visao.kpis}
    assert kpis["acoes"].footer == "de 33 ações em aberto"
    assert kpis["spi"].footer == "0,01 acima vs. mês anterior · real 61,8% x previsto 65,7%"
    assert kpis["cpi"].footer == "0,02 abaixo vs. mês anterior · projeção R$ 45,3 mi (+1,5%)"
    assert kpis["riscos"].footer == "1 alto · exposição R$ 3,4 mi"
    assert kpis["rncs"].footer == "1 vencida · inspeções aprovadas 85,0%"
    assert kpis["hse"].badge == "1 HiPo no mês"
    assert kpis["mudancas"].footer == "R$ 1,2 mi aprovados (2,7% do orçamento)"

    titles = {item.title for item in visao.attention}
    assert "CLM-TN-2026-0003 notificado fora do prazo contratual" in titles
    assert "RNC-TN-2026-0004 com prazo de tratamento vencido" in titles
    assert "RSK-TN-2026-0003 com revisão vencida" in titles
    assert "1 ocorrência de alto potencial no mês" in titles
    assert "Sistema 210 Moagem bloqueado por item A" in titles
    assert "PED-2026-0001 Moinho de bolas 5,0 x 7,5 m" in titles

    cards = {card.module: card for card in visao.cards}
    assert [badge.text for badge in cards["central_acoes"].badges] == ["8 atrasadas"]
    assert [badge.text for badge in cards["planejamento"].badges] == ["4 itens A abertos"]
    assert [badge.text for badge in cards["financeiro"].badges] == ["2 claims em aberto"]
    assert [badge.text for badge in cards["suprimentos"].badges] == ["aderência ao plano 92,9%"]
    assert [badge.text for badge in cards["riscos"].badges] == ["1 revisão vencida"]
    assert [badge.text for badge in cards["qualidade"].badges] == ["4 RNC abertas"]
    assert [badge.text for badge in cards["hse"].badges] == ["TRIF 8,88"]
    assert [badge.text for badge in cards["governanca"].badges] == ["2 em análise de impacto"]


def test_oraculo_do_inicio_do_portfolio(demonstracao: Demonstracao) -> None:
    visao = service.home_overview(
        demonstracao.session,
        user=demonstracao.admin,
        scope=Scope(project_id=None, source="padrao"),
        reference_date=demonstracao.reference_date,
    )

    _afirmar_os_numeros(visao, PORTFOLIO_EXPECTED)

    kpis = {kpi.key: kpi for kpi in visao.kpis}
    assert kpis["mudancas"].footer == "R$ 1,4 mi aprovados (2,0% do orçamento da carteira)"
    assert visao.budget_cents == 7_020_000_000, "44,6 + 18,2 + 7,4 mi"
    assert str(visao.expected_end_date) == "2027-06-30", "o término mais distante"


def test_oraculo_da_carteira_do_portfolio(demonstracao: Demonstracao) -> None:
    visao = service.home_overview(
        demonstracao.session,
        user=demonstracao.admin,
        scope=Scope(project_id=None, source="padrao"),
        reference_date=demonstracao.reference_date,
    )

    assert [(row.code, row.weight) for row in visao.portfolio_rows] == list(CARTEIRA_EXPECTED)
    assert sum(row.weight for row in visao.portfolio_rows) == Decimal("100.00")
    assert visao.portfolio_totals is not None
    assert visao.portfolio_totals.budget_cents == 7_020_000_000, "a soma dos orçamentos vigentes"

    fabrica = visao.portfolio_rows[0]
    assert fabrica.overdue_actions == 8
    assert fabrica.spi == Decimal("0.94")
    assert fabrica.cpi == Decimal("0.96")
    assert fabrica.critical_orders == 3
    assert fabrica.critical_risks == 2
    assert fabrica.health == "warn", "SPI 0,94 e CPI 0,96 ficam na atenção"
    assert fabrica.health_label == "Atenção"

    for row in visao.portfolio_rows:
        assert row.health == calculations.health_band(row.spi, row.cpi)
        assert row.health in {"ok", "warn", "erro"}


def test_oraculo_da_previa_com_os_criterios_vigentes(demonstracao: Demonstracao) -> None:
    session = demonstracao.session
    reference_date = demonstracao.reference_date
    view = service.ponderation_view(session, user=demonstracao.admin, reference_date=reference_date)
    preview = service.ponderation_preview(
        session,
        user=demonstracao.admin,
        criteria={
            criterion.id: calculations.input_number(criterion.weight) for criterion in view.criteria
        },
        grades={
            project.project_id: {key: str(value) for key, value in project.grades.items()}
            for project in view.projects
        },
        reference_date=reference_date,
    )

    assert {row.code: row.weight for row in preview.rows} == dict(CARTEIRA_EXPECTED)
    assert sum(row.weight for row in preview.rows) == Decimal("100.00")
