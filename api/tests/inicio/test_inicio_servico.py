"""A fachada do Início (ISSUE-079 e ISSUE-080): indicadores, atenção, carteira e ponderação.

Cada indicador e cada linha da carteira saem da fachada do módulo dono no mesmo corte: o teste
relê cada dono e compara o número (D9). No Portfólio os consolidados valem, a carteira lê os
donos por projeto e os pontos de atenção abrem com o código do projeto; sem projeto nenhum no
escopo, o resumo sai vazio (o vazio de origem da tela). A ponderação é a leitura do modal, a
prévia que não grava e a gravação que cria a versão nova com a justificativa, as notas digitadas
e a trilha — e o Membro recebe 403.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.auth import _user_of
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import ParameterVersion
from src.modulos.financeiro import calculations as financeiro_calculations
from src.modulos.financeiro import service as financeiro
from src.modulos.governanca import service as governanca
from src.modulos.hse import painel_service as hse_painel
from src.modulos.inicio import calculations, service
from src.modulos.planejamento import service as planejamento
from src.modulos.qualidade import painel_service as qualidade_painel
from src.modulos.riscos import panel_service as riscos_painel
from src.modulos.suprimentos import service as suprimentos
from tests.identidades import criar_colaborador
from tests.inicio.conftest import Cenario, Demonstracao

KPI_ORDER = ("acoes", "spi", "cpi", "pedidos", "riscos", "rncs", "hse", "mudancas")
PREFIXED_MODULES = (
    "central_acoes",
    "suprimentos",
    "riscos",
    "financeiro",
    "qualidade",
    "governanca",
)
PORTFOLIO_SCOPE = Scope(project_id=None, source="padrao")

PESOS_DA_DEMONSTRACAO = {
    "TN-2026-014": Decimal("55.36"),
    "TN-2026-021": Decimal("29.34"),
    "TN-2026-027": Decimal("15.30"),
}


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


def _portfolio(demonstracao: Demonstracao) -> service.HomeOverview:
    return service.home_overview(
        demonstracao.session,
        user=demonstracao.admin,
        scope=PORTFOLIO_SCOPE,
        reference_date=demonstracao.reference_date,
    )


def _version_count(session: Session, group: str) -> int:
    statement = (
        select(func.count()).select_from(ParameterVersion).where(ParameterVersion.group == group)
    )
    return session.scalar(statement) or 0


# ── A carteira de projetos (ISSUE-080) ───────────────────────────────────


def test_a_carteira_do_portfolio_bate_com_o_inicio_de_cada_projeto(
    demonstracao: Demonstracao,
) -> None:
    session = demonstracao.session
    reference_date = demonstracao.reference_date
    visao = _portfolio(demonstracao)

    assert [row.code for row in visao.portfolio_rows] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ], "do maior peso para o menor, como o protótipo"
    assert {row.code: row.weight for row in visao.portfolio_rows} == PESOS_DA_DEMONSTRACAO
    assert sum(row.weight for row in visao.portfolio_rows) == Decimal("100.00")

    weights = financeiro.portfolio_weights(session, reference_date=reference_date)
    for row in visao.portfolio_rows:
        scope = Scope(project_id=row.project_id, source="url")
        cost = financeiro.cost_kpis_overview(session, scope=scope, reference_date=reference_date)
        planning = planejamento.planning_kpis_overview(
            session, scope=scope, reference_date=reference_date
        )
        risks = riscos_painel.risk_panel(
            session, user=demonstracao.admin, scope=scope, reference_date=reference_date
        )
        supply = suprimentos.list_panel(
            session, user=demonstracao.admin, scope=scope, reference_date=reference_date
        )
        actions = central_acoes.count_by_status(
            session, user=demonstracao.admin, scope=scope, reference_date=reference_date
        )
        cpi = None if cost.indicators is None else cost.indicators.cpi

        assert row.weight == weights[row.project_id].weight
        assert row.budget_cents == cost.budget_cents
        assert row.cpi == cpi
        assert row.projection_cents == cost.projection_cents
        assert row.vac_cents == cost.vac_cents
        assert row.predicted == planning.indicators.predicted
        assert row.actual == planning.indicators.actual
        assert row.spi == planning.indicators.spi
        assert row.deviation_pp == planning.indicators.deviation_pp
        assert row.baseline_finish == planning.indicators.baseline_finish
        assert row.trend_finish == planning.indicators.trend_finish
        assert row.critical_risks == risks.summary.top.total
        assert row.critical_orders == supply.summary.orders.critical
        assert row.overdue_actions == actions.overdue
        assert row.health == calculations.health_band(row.spi, cpi)


def test_os_totais_da_carteira_sao_as_somas_e_os_consolidados(
    demonstracao: Demonstracao,
) -> None:
    session = demonstracao.session
    reference_date = demonstracao.reference_date
    visao = _portfolio(demonstracao)
    totals = visao.portfolio_totals
    assert totals is not None

    cost = financeiro.cost_kpis_overview(
        session, scope=PORTFOLIO_SCOPE, reference_date=reference_date
    )
    planning = planejamento.planning_kpis_overview(
        session, scope=PORTFOLIO_SCOPE, reference_date=reference_date
    )
    risks = riscos_painel.risk_panel(
        session, user=demonstracao.admin, scope=PORTFOLIO_SCOPE, reference_date=reference_date
    )
    supply = suprimentos.list_panel(
        session, user=demonstracao.admin, scope=PORTFOLIO_SCOPE, reference_date=reference_date
    )
    actions = central_acoes.count_by_status(
        session, user=demonstracao.admin, scope=PORTFOLIO_SCOPE, reference_date=reference_date
    )

    assert totals.project_count == len(visao.portfolio_rows) == 3
    assert totals.budget_cents == cost.budget_cents
    assert totals.budget_cents == sum(row.budget_cents for row in visao.portfolio_rows)
    assert totals.spi == planning.indicators.spi
    assert totals.predicted == planning.indicators.predicted
    assert totals.actual == planning.indicators.actual
    assert totals.cpi == (cost.indicators.cpi if cost.indicators else None)
    assert totals.projection_cents == cost.projection_cents
    assert totals.vac_cents == cost.vac_cents
    assert totals.baseline_finish == planning.indicators.baseline_finish
    assert totals.trend_finish == planning.indicators.trend_finish
    assert totals.critical_risks == risks.summary.top.total
    assert totals.critical_orders == supply.summary.orders.critical
    assert totals.overdue_actions == actions.overdue


def test_a_situacao_da_carteira_e_o_pior_dos_indices() -> None:
    assert calculations.health_band(Decimal("1.00"), Decimal("0.98")) == "ok"
    assert calculations.health_band(Decimal("0.99"), Decimal("0.97")) == "warn", (
        "o CPI tem a faixa dele"
    )
    assert calculations.health_band(Decimal("0.94"), Decimal("0.98")) == "warn"
    assert calculations.health_band(Decimal("0.89"), Decimal("0.98")) == "erro"
    assert calculations.health_band(Decimal("0.97"), Decimal("0.92")) == "erro"
    assert calculations.health_band(Decimal("0.92"), None) == "warn"
    assert calculations.health_band(None, None) is None
    assert calculations.health_label("warn") == "Atenção"


# ── A ponderação da carteira (ISSUE-080) ─────────────────────────────────


def test_a_visao_da_ponderacao_traz_criterios_notas_e_pesos(demonstracao: Demonstracao) -> None:
    session = demonstracao.session
    reference_date = demonstracao.reference_date
    view = service.ponderation_view(session, user=demonstracao.admin, reference_date=reference_date)

    assert [criterion.id for criterion in view.criteria] == ["valor", "estrategico", "complexidade"]
    assert [criterion.weight for criterion in view.criteria] == [
        Decimal("60"),
        Decimal("25"),
        Decimal("15"),
    ]
    assert (view.grade_minimum, view.grade_maximum) == (1, 5)
    assert view.weights_total == Decimal("100")
    assert view.can_save is True
    assert [project.code for project in view.projects] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ]

    grades = configuracoes.portfolio_grades(session, reference_date=reference_date)
    weights = financeiro.portfolio_weights(session, reference_date=reference_date)
    for project in view.projects:
        assert project.grades == grades[project.project_id]
        assert project.weight == weights[project.project_id].weight


def test_o_membro_nao_previa_nem_grava_a_ponderacao(cenario: Cenario) -> None:
    reference_date = date(2026, 9, 25)
    with pytest.raises(AccessDeniedError):
        service.ponderation_preview(
            cenario.session,
            user=cenario.membro,
            criteria={"valor": "60"},
            grades={},
            reference_date=reference_date,
        )
    with pytest.raises(AccessDeniedError):
        service.save_ponderation(
            cenario.session,
            user=cenario.membro,
            criteria={"valor": "60"},
            grades={},
            justification="Justificativa com mais de dez caracteres.",
            reference_date=reference_date,
        )


def test_a_previa_nao_grava_e_bate_com_a_formula_do_dono(demonstracao: Demonstracao) -> None:
    session = demonstracao.session
    reference_date = demonstracao.reference_date
    before = _version_count(session, "portfolio")
    view = service.ponderation_view(session, user=demonstracao.admin, reference_date=reference_date)
    criteria = {
        criterion.id: calculations.input_number(criterion.weight) for criterion in view.criteria
    }
    grades = {
        project.project_id: {key: str(value) for key, value in project.grades.items()}
        for project in view.projects
    }

    preview = service.ponderation_preview(
        session,
        user=demonstracao.admin,
        criteria=criteria,
        grades=grades,
        reference_date=reference_date,
    )

    assert _version_count(session, "portfolio") == before, "a prévia não grava"
    assert {row.code: row.weight for row in preview.rows} == PESOS_DA_DEMONSTRACAO
    assert sum(row.weight for row in preview.rows) == Decimal("100.00")

    projects = configuracoes.list_projects(session)
    budgets = financeiro.current_budgets(session)
    expected = financeiro_calculations.portfolio_weights(
        [
            financeiro_calculations.WeightInput(
                project_id=project.id,
                budget_cents=budgets[project.id],
                grades={
                    criterion.id: int(grades[project.id][criterion.id])
                    for criterion in view.criteria
                    if criterion.source == "nota"
                },
            )
            for project in projects
        ],
        [
            financeiro_calculations.WeightCriterion(
                id=criterion.id,
                weight=criterion.weight,
                source=criterion.source,
            )
            for criterion in view.criteria
        ],
    )
    assert {row.project_id: row.weight for row in preview.rows} == {
        project_id: weight.weight for project_id, weight in expected.items()
    }

    changed = service.ponderation_preview(
        session,
        user=demonstracao.admin,
        criteria={"valor": "50", "estrategico": "30", "complexidade": "20"},
        grades={
            project.project_id: {"estrategico": "5", "complexidade": "1"}
            for project in view.projects
        },
        reference_date=reference_date,
    )
    assert sum(row.weight for row in changed.rows) == Decimal("100.00")
    assert {row.code: row.weight for row in changed.rows} != PESOS_DA_DEMONSTRACAO
    assert _version_count(session, "portfolio") == before, "a prévia alterada também não grava"


def test_gravar_a_ponderacao_cria_a_versao_nova_com_as_notas_digitadas(
    demonstracao: Demonstracao,
) -> None:
    session = demonstracao.session
    reference_date = demonstracao.reference_date
    before = _version_count(session, "portfolio")
    projects = configuracoes.list_projects(session)
    grades = {project.id: {"estrategico": 4, "complexidade": 2} for project in projects}

    version = service.save_ponderation(
        session,
        user=demonstracao.admin,
        criteria={"valor": "50", "estrategico": "30", "complexidade": "20"},
        grades=grades,
        justification="Revisão da ponderação aprovada no comitê de outubro.",
        reference_date=reference_date,
    )

    assert _version_count(session, "portfolio") == before + 1
    assert version.version == before + 1
    assert version.justification == "Revisão da ponderação aprovada no comitê de outubro."
    assert version.author_id == demonstracao.admin.id

    group = configuracoes.current_group(session, group="portfolio", reference_date=reference_date)
    assert [criterion["peso"] for criterion in group["criterios"]] == [50, 30, 20]
    vigentes = configuracoes.portfolio_grades(session, reference_date=reference_date)
    for project in projects:
        assert vigentes[project.id] == {"estrategico": 4, "complexidade": 2}


def test_a_gravacao_recusa_sem_justificativa_sem_soma_100_e_nota_fora_da_faixa(
    demonstracao: Demonstracao,
) -> None:
    session = demonstracao.session
    reference_date = demonstracao.reference_date
    before = _version_count(session, "portfolio")
    projects = configuracoes.list_projects(session)
    grades = {project.id: {"estrategico": 3, "complexidade": 3} for project in projects}
    pesos = {"valor": "60", "estrategico": "25", "complexidade": "15"}

    with pytest.raises(InvalidDataError) as curta:
        service.save_ponderation(
            session,
            user=demonstracao.admin,
            criteria=pesos,
            grades=grades,
            justification="curta",
            reference_date=reference_date,
        )
    assert "justificativa" in curta.value.detail

    with pytest.raises(InvalidDataError) as soma:
        service.save_ponderation(
            session,
            user=demonstracao.admin,
            criteria={**pesos, "complexidade": "10"},
            grades=grades,
            justification="Justificativa com mais de dez caracteres.",
            reference_date=reference_date,
        )
    assert peso_message(soma.value) == (
        "Os pesos dos critérios de ponderação do portfólio devem somar 100% (atual: 95%)."
    )

    with pytest.raises(InvalidDataError) as fora:
        service.save_ponderation(
            session,
            user=demonstracao.admin,
            criteria=pesos,
            grades={project.id: {"estrategico": 6, "complexidade": 3} for project in projects},
            justification="Justificativa com mais de dez caracteres.",
            reference_date=reference_date,
        )
    campo = f"nota_{projects[0].id}_estrategico"
    assert fora.value.detail[campo] == "Nota inteira de 1 a 5."

    assert _version_count(session, "portfolio") == before, "a recusa não grava versão"


def peso_message(error: InvalidDataError) -> str:
    """A mensagem da soma dos pesos, no campo do primeiro critério (o dono a escreve)."""
    assert isinstance(error.detail, dict)
    return next(
        message
        for field, message in error.detail.items()
        if field.startswith("peso_") and "somar 100%" in message
    )
