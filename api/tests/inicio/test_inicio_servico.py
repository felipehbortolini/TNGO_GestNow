"""A fachada do Início (ISSUE-079): os oito indicadores e os pontos de atenção calculados.

Cada indicador sai da fachada do módulo dono no mesmo corte: o teste relê cada dono e compara o
número (D9). No Portfólio os consolidados valem e os pontos de atenção abrem com o código do
projeto; sem projeto nenhum no escopo, o resumo sai vazio (o vazio de origem da tela).
"""

from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

from src.core.auth import _user_of
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service as financeiro
from src.modulos.governanca import service as governanca
from src.modulos.hse import painel_service as hse_painel
from src.modulos.inicio import service
from src.modulos.planejamento import service as planejamento
from src.modulos.qualidade import painel_service as qualidade_painel
from src.modulos.riscos import panel_service as riscos_painel
from src.modulos.suprimentos import service as suprimentos
from tests.identidades import criar_colaborador
from tests.inicio.conftest import Demonstracao

KPI_ORDER = ("acoes", "spi", "cpi", "pedidos", "riscos", "rncs", "hse", "mudancas")
PREFIXED_MODULES = (
    "central_acoes",
    "suprimentos",
    "riscos",
    "financeiro",
    "qualidade",
    "governanca",
)


def _kpis(visao: service.HomeOverview) -> dict[str, service.HomeKpi]:
    return {kpi.key: kpi for kpi in visao.kpis}


def test_os_oito_indicadores_batem_com_as_fachadas_donas(demonstracao: Demonstracao) -> None:
    session = demonstracao.session
    scope = Scope(project_id=demonstracao.project_id, source="url")
    reference_date = demonstracao.reference_date
    visao = service.home_overview(
        session, user=demonstracao.admin, scope=scope, reference_date=reference_date
    )

    assert [kpi.key for kpi in visao.kpis] == list(KPI_ORDER), "a ordem dos módulos"
    kpis = _kpis(visao)

    counts = central_acoes.count_by_status(
        session, user=demonstracao.admin, scope=scope, reference_date=reference_date
    )
    assert kpis["acoes"].export_value == counts.overdue
    assert kpis["acoes"].footer == f"de {counts.open} ações em aberto"
    assert kpis["acoes"].url == "/central-acoes/acoes?status=atrasada"

    planning = planejamento.planning_kpis_overview(
        session, scope=scope, reference_date=reference_date
    )
    assert kpis["spi"].export_value == planning.indicators.spi
    assert kpis["spi"].url == "/planejamento/kpis"

    cost = financeiro.cost_kpis_overview(session, scope=scope, reference_date=reference_date)
    assert kpis["cpi"].export_value == cost.indicators.cpi
    assert kpis["cpi"].url == "/financeiro/kpis"

    supply = suprimentos.list_panel(
        session, user=demonstracao.admin, scope=scope, reference_date=reference_date
    )
    assert kpis["pedidos"].export_value == supply.summary.orders.critical
    assert str(supply.summary.orders.lli_critical) in kpis["pedidos"].footer
    assert kpis["pedidos"].url == "/suprimentos/diligenciamento?faixa=critico"

    risks = riscos_painel.risk_panel(
        session, user=demonstracao.admin, scope=scope, reference_date=reference_date
    )
    assert kpis["riscos"].export_value == risks.summary.top.total
    assert kpis["riscos"].url == "/riscos/registro"

    quality = qualidade_painel.quality_indicators(
        session, user=demonstracao.admin, scope=scope, reference_date=reference_date
    )
    assert kpis["rncs"].export_value == quality.open_rncs
    assert kpis["rncs"].url == "/qualidade/rnc?situacao=ativas"

    hse = hse_painel.panel(
        session,
        user=demonstracao.admin,
        scope=scope,
        reference_date=reference_date,
        month=None,
        pyramid_kind=None,
    )
    assert kpis["hse"].export_value == hse.accumulated_indicators.days_without_leave
    assert kpis["hse"].url == "/hse/painel"

    changes = governanca.register_overview(
        session,
        user=demonstracao.admin,
        scope=scope,
        filters=governanca.ChangeFilter(),
        reference_date=reference_date,
    )
    assert kpis["mudancas"].export_value == changes.summary.awaiting_committee
    query = parse_qs(urlparse(kpis["mudancas"].url).query)
    assert query["situacao"] == ["Aguardando comitê"], "o filtro da situação aguardando comitê"


def test_os_pontos_de_atencao_do_projeto_1(demonstracao: Demonstracao) -> None:
    visao = service.home_overview(
        demonstracao.session,
        user=demonstracao.admin,
        scope=Scope(project_id=demonstracao.project_id, source="url"),
        reference_date=demonstracao.reference_date,
    )
    titles = [item.title for item in visao.attention]

    assert titles[:3] == [
        "Contratar consultoria credenciada",
        "Sondagem complementar nas fundações F-20 a F-28",
        "Negociar antecipação do embarque do britador",
    ], "as três ações mais atrasadas, da maior para a menor"
    assert "CLM-TN-2026-0003 notificado fora do prazo contratual" in titles
    assert "RNC-TN-2026-0004 com prazo de tratamento vencido" in titles
    assert "RSK-TN-2026-0003 com revisão vencida" in titles
    assert "1 ocorrência de alto potencial no mês" in titles
    assert "Sistema 210 Moagem bloqueado por item A" in titles

    claims = next(item for item in visao.attention if item.module == "financeiro")
    assert claims.url == "/financeiro/contratos?busca=CLM-TN-2026-0003"
    rnc = next(item for item in visao.attention if item.module == "qualidade")
    assert rnc.level == "warning" and rnc.url == "/qualidade/rnc?busca=RNC-TN-2026-0004"
    assert all(not title.startswith("TN-") for title in titles), (
        "no projeto o título não repete o código do projeto"
    )


def test_o_portfolio_consolida_e_prefixa_o_codigo_nos_alertas(demonstracao: Demonstracao) -> None:
    session = demonstracao.session
    scope = Scope(project_id=None, source="padrao")
    reference_date = demonstracao.reference_date
    visao = service.home_overview(
        session, user=demonstracao.admin, scope=scope, reference_date=reference_date
    )

    assert visao.is_portfolio and not visao.is_empty
    assert visao.budget_cents == 7_020_000_000, "a soma dos orçamentos da carteira"
    assert str(visao.expected_end_date) == "2027-06-30", "o término mais distante"

    kpis = _kpis(visao)
    counts = central_acoes.count_by_status(
        session, user=demonstracao.admin, scope=scope, reference_date=reference_date
    )
    assert kpis["acoes"].export_value == counts.overdue
    assert kpis["spi"].label == "SPI ponderado da carteira"
    assert kpis["cpi"].label == "CPI da carteira"
    assert "da carteira" in kpis["mudancas"].footer

    prefixed = [item for item in visao.attention if item.module in PREFIXED_MODULES]
    assert prefixed, "o Portfólio tem pontos de atenção"
    assert all(item.title.startswith("TN-") for item in prefixed), (
        "no Portfólio o código do projeto abre o título"
    )


def test_o_portfolio_sem_projetos_sai_vazio(db_session: Session) -> None:
    criar_colaborador(db_session, email="membro@vazio.example.invalid")
    acesso = configuracoes.find_access_by_email(db_session, "membro@vazio.example.invalid")
    assert acesso is not None
    visao = service.home_overview(
        db_session,
        user=_user_of(acesso),
        scope=Scope(project_id=None, source="padrao"),
        reference_date=date(2026, 9, 25),
    )

    assert visao.is_empty
    assert visao.kpis == () and visao.attention == () and visao.cards == ()
    assert visao.project is None and visao.project_count == 0
