"""Fachada das reservas de contingência e gerencial (ISSUE-041, HU-094).

A visão do projeto traz as duas reservas com saldo, consumo, liberação, pedido em SMs abertas,
limite de consumo pelo avanço físico e burn da curva congelada; a da carteira soma os projetos,
traz a tabela por projeto e o burn da união; sem reserva a visão é vazia. A composição soma a
linha de base de custo e o orçamento do projeto, e o mapa de controle ganha a faixa Reservas com
a resposta "o saldo cobre o desvio projetado?".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import azure.functions as func
from sqlalchemy import select

from src.core import auth
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project, Unit
from src.modulos.financeiro import calculations, routes, service
from src.modulos.financeiro.models import Reserve, ReserveMovement
from src.modulos.governanca import models as governanca_models
from src.modulos.governanca.models import ChangeImpact, ChangeRequest
from src.modulos.planejamento import service as planejamento
from src.modulos.planejamento.models import EapItem, EapMeasurement, EapRevision, EapRevisionItem
from tests.financeiro.conftest import MEMBER_EMAIL, REFERENCE_DATE, EacScenario
from tests.identidades import cabecalho_do_principal

D = Decimal
HOJE = REFERENCE_DATE
PORTFOLIO = Scope(project_id=None, source="padrao")
EAC_FIRST_CENTS = 7_001_000
EAC_SECOND_CENTS = 5_000_000


def _escopo(project: Project) -> Scope:
    return Scope(project_id=project.id, source="url")


def _reservar(
    cenario: EacScenario,
    *,
    kind: str,
    value_cents: int,
    project: Project | None = None,
    dia: date = date(2026, 1, 5),
) -> Reserve:
    projeto = project or cenario.first
    reserve = Reserve(
        project_id=projeto.id,
        kind=kind,
        calculation_basis="Constituída na linha de base do projeto.",
    )
    cenario.session.add(reserve)
    cenario.session.flush()
    cenario.session.add(
        ReserveMovement(
            reserve_id=reserve.id,
            change_id=None,
            registered_by_id=cenario.member.person_id,
            kind=calculations.MOVEMENT_CONSTITUTION,
            registered_on=dia,
            value_cents=value_cents,
            justification="Constituída na linha de base do projeto.",
        )
    )
    cenario.session.flush()
    return reserve


def _movimento(
    cenario: EacScenario,
    reserve: Reserve,
    *,
    kind: str,
    value_cents: int,
    dia: date = HOJE,
) -> None:
    cenario.session.add(
        ReserveMovement(
            reserve_id=reserve.id,
            change_id=None,
            registered_by_id=cenario.member.person_id,
            kind=kind,
            registered_on=dia,
            value_cents=value_cents,
            justification="Movimento da reserva no teste.",
        )
    )
    cenario.session.flush()


@dataclass(frozen=True)
class Pedido:
    """Uma SM aberta que pede reserva, como o teste a monta."""

    code: str
    custo_cents: int = 0
    source: str | None = None
    release_kind: str | None = None
    release_cents: int | None = None
    situacao: str = governanca_models.SITUATION_AWAITING


def _mudanca_aberta(
    cenario: EacScenario, pedido: Pedido, *, project: Project | None = None
) -> ChangeRequest:
    projeto = project or cenario.first
    change = ChangeRequest(
        project_id=projeto.id,
        requester_id=cenario.member.person_id,
        code=pedido.code,
        title=f"Pedido de reserva {pedido.code}",
        kind=governanca_models.TYPE_RESERVE_RELEASE if pedido.release_kind else "Custo",
        origin="Interna",
        priority="Normal",
        request_date=date(2026, 9, 10),
        description="Pedido de reserva da demonstração.",
        resource_source=pedido.source,
        situation=pedido.situacao,
    )
    cenario.session.add(change)
    cenario.session.flush()
    cenario.session.add(
        ChangeImpact(
            change_id=change.id,
            analyst_id=cenario.member.person_id,
            analysis_date=date(2026, 9, 12),
            cost_cents=pedido.custo_cents,
            term_days=0,
            scope="Sem impacto",
            quality="Sem impacto",
            risks="Sem impacto",
            safety="Sem impacto",
            contract="Sem impacto",
            affects_contract_milestone=False,
            release_reserve=pedido.release_kind,
            release_value_cents=pedido.release_cents,
        )
    )
    cenario.session.flush()
    return change


def _curva(
    cenario: EacScenario,
    *,
    project: Project | None = None,
    periodo: tuple[date, date] = (date(2026, 1, 1), date(2026, 6, 30)),
    to_pct: str = "50",
) -> None:
    projeto = project or cenario.first
    start, finish = periodo
    session = cenario.session
    unit = session.scalars(select(Unit)).first()
    assert unit is not None
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
        start=start,
        finish=finish,
        quantity=D("100"),
        executed=D("100"),
        unit_id=unit.id,
    )
    session.add(item)
    session.flush()
    revision = EapRevision(
        project_id=projeto.id,
        approved_by_id=projeto.manager_id,
        revision=0,
        revision_date=date(2026, 1, 5),
        alteration="Linha de base",
        justification="Linha de base aprovada no gate de investimento.",
    )
    session.add(revision)
    session.flush()
    session.add(EapRevisionItem(revision_id=revision.id, item_id=item.id, weight=D("100")))
    session.add(
        EapMeasurement(
            item_id=item.id,
            author_id=cenario.member.person_id,
            measured_on=date(2026, 3, 15),
            from_pct=D("0"),
            to_pct=D(to_pct),
            note="Boletim",
        )
    )
    session.flush()
    planejamento.freeze_curve(
        session, project_id=projeto.id, revision_id=revision.id, reference_date=HOJE
    )


def _visao(cenario: EacScenario, scope: Scope | None = None) -> service.ContingencyOverview:
    return service.contingency_overview(
        cenario.session, scope=scope or _escopo(cenario.first), reference_date=HOJE
    )


# ── Visão do projeto ─────────────────────────────────────────────────────


def test_sem_reservas_a_visao_e_vazia(cenario: EacScenario) -> None:
    view = _visao(cenario)

    assert view.is_empty
    assert view.contingency is None
    assert view.management is None
    assert view.movements == ()
    assert view.burn == ()
    assert view.alerts == ()
    assert view.eac_current_cents == 0

    carteira = _visao(cenario, PORTFOLIO)
    assert carteira.is_empty
    assert carteira.projects == ()


def test_visao_soma_constituicao_consumo_e_liberacao(cenario: EacScenario) -> None:
    contingency = _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _reservar(cenario, kind=calculations.RESERVE_MANAGEMENT, value_cents=5_000_000)
    _movimento(
        cenario,
        contingency,
        kind=calculations.MOVEMENT_CONSUMPTION,
        value_cents=-3_000_000,
        dia=date(2026, 8, 20),
    )
    _movimento(
        cenario,
        contingency,
        kind=calculations.MOVEMENT_RELEASE,
        value_cents=-1_000_000,
        dia=date(2026, 9, 1),
    )

    view = _visao(cenario)

    assert view.contingency is not None
    assert (
        view.contingency.total_cents,
        view.contingency.consumed_cents,
        view.contingency.released_cents,
        view.contingency.balance_cents,
    ) == (20_000_000, 3_000_000, 1_000_000, 16_000_000)
    assert view.contingency.consumption_pct == D("15.0")
    assert view.contingency.balance_after_analysis_cents == 16_000_000
    assert view.management is not None
    assert view.management.balance_cents == 5_000_000
    assert view.eac_current_cents == EAC_FIRST_CENTS
    assert view.cost_baseline_cents == EAC_FIRST_CENTS + 16_000_000
    assert view.project_budget_cents == EAC_FIRST_CENTS + 16_000_000 + 5_000_000
    assert [(line.reserve_kind, line.kind, line.balance_cents) for line in view.movements] == [
        (calculations.RESERVE_CONTINGENCY, calculations.MOVEMENT_CONSTITUTION, 20_000_000),
        (calculations.RESERVE_MANAGEMENT, calculations.MOVEMENT_CONSTITUTION, 5_000_000),
        (calculations.RESERVE_CONTINGENCY, calculations.MOVEMENT_CONSUMPTION, 17_000_000),
        (calculations.RESERVE_CONTINGENCY, calculations.MOVEMENT_RELEASE, 16_000_000),
    ], "cada movimento leva o saldo corrente da própria reserva, não a soma das duas"
    assert view.movements[-1].situation == service.SITUATION_EFFECTIVE
    assert view.expected_balance_cents is None


def test_sms_em_analise_entram_no_saldo_apos_analise_e_no_extrato(cenario: EacScenario) -> None:
    _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _mudanca_aberta(
        cenario,
        Pedido(
            code="SM-TN-2026-0001",
            custo_cents=4_000_000,
            source=calculations.RESERVE_SOURCE_CONTINGENCY,
        ),
    )
    _mudanca_aberta(
        cenario,
        Pedido(
            code="SM-TN-2026-0002",
            release_kind=calculations.RESERVE_CONTINGENCY,
            release_cents=2_000_000,
        ),
    )
    _mudanca_aberta(
        cenario,
        Pedido(
            code="SM-TN-2026-0003",
            custo_cents=1_000_000,
            source=calculations.RESERVE_SOURCE_CONTINGENCY,
            situacao=governanca_models.SITUATION_REJECTED,
        ),
    )

    view = _visao(cenario)

    assert view.contingency is not None
    assert view.contingency.in_analysis_cents == 6_000_000
    assert view.contingency.balance_after_analysis_cents == 14_000_000
    assert view.analysis_count == 2
    em_analise = [line for line in view.movements if line.kind == calculations.MOVEMENT_IN_ANALYSIS]
    assert [(line.change_code, line.value_cents, line.balance_cents) for line in em_analise] == [
        ("SM-TN-2026-0001", -4_000_000, None),
        ("SM-TN-2026-0002", -2_000_000, None),
    ]
    assert all(line.situation == governanca_models.SITUATION_AWAITING for line in em_analise)


def test_burn_usa_a_curva_congelada_e_o_limite_a_tolerancia(cenario: EacScenario) -> None:
    _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _curva(cenario, to_pct="50")

    view = _visao(cenario)

    assert view.physical_actual == D("50.0")
    assert view.physical_predicted is not None
    assert view.tolerance_pp == D("10")
    assert view.consumption_limit_pct == D("60.0")
    assert [point.month for point in view.burn] == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
        date(2026, 4, 1),
        date(2026, 5, 1),
        date(2026, 6, 1),
    ]
    assert view.burn[-1].actual_cents == 20_000_000
    assert view.expected_balance_cents == view.burn[-1].expected_cents
    assert view.expected_balance_cents < 20_000_000


def test_limite_de_consumo_usa_a_tolerancia_do_parametro(cenario: EacScenario) -> None:
    session = cenario.session
    configuracoes.seed_initial_parameters(
        session, author_id=cenario.member.id, effective_from=date(2026, 1, 1)
    )
    configuracoes.save_parameter_group(
        session,
        author_id=cenario.member.id,
        group="financeiro",
        values={
            "faixasDesvio": [1, 5, 10],
            "contingencia": {"toleranciaConsumoPP": 5, "coberturaMinimaPct": 100},
        },
        effective_from=date(2026, 9, 1),
        justification="Ajuste da tolerância do consumo da contingência.",
    )
    _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _curva(cenario, to_pct="50")

    view = _visao(cenario)

    assert view.tolerance_pp == D("5")
    assert view.consumption_limit_pct == D("55.0")


def test_alertas_de_consumo_e_de_analise(cenario: EacScenario) -> None:
    contingency = _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _movimento(
        cenario,
        contingency,
        kind=calculations.MOVEMENT_CONSUMPTION,
        value_cents=-13_000_000,
        dia=date(2026, 5, 10),
    )
    _mudanca_aberta(
        cenario,
        Pedido(
            code="SM-TN-2026-0001",
            custo_cents=8_000_000,
            source=calculations.RESERVE_SOURCE_CONTINGENCY,
        ),
    )
    _curva(cenario, to_pct="50")

    view = _visao(cenario)

    assert view.contingency is not None
    assert view.contingency.consumption_pct == D("65.0")
    assert view.contingency.in_analysis_cents == 8_000_000
    assert view.contingency.balance_cents == 7_000_000
    kinds = [alert.kind for alert in view.alerts]
    assert kinds == [service.RESERVE_ALERT_CONSUMPTION, service.RESERVE_ALERT_ANALYSIS]
    assert "Consumo da contingência (65,0%)" in view.alerts[0].text
    assert "acima do saldo" in view.alerts[1].text


# ── Visão da carteira ────────────────────────────────────────────────────


def test_visao_da_carteira_soma_os_projetos_e_tem_tabela(cenario: EacScenario) -> None:
    _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _reservar(cenario, kind=calculations.RESERVE_MANAGEMENT, value_cents=5_000_000)
    _reservar(
        cenario,
        kind=calculations.RESERVE_CONTINGENCY,
        value_cents=10_000_000,
        project=cenario.second,
    )
    _mudanca_aberta(
        cenario,
        Pedido(
            code="SM-TN-2026-0001",
            custo_cents=8_000_000,
            source=calculations.RESERVE_SOURCE_CONTINGENCY,
        ),
    )

    view = _visao(cenario, PORTFOLIO)

    assert view.is_portfolio
    assert view.scope_label == "Portfólio"
    assert view.contingency is not None
    assert (view.contingency.total_cents, view.contingency.balance_cents) == (
        30_000_000,
        30_000_000,
    )
    assert view.contingency.in_analysis_cents == 8_000_000
    assert view.management is not None
    assert view.management.balance_cents == 5_000_000
    assert view.eac_current_cents == EAC_FIRST_CENTS + EAC_SECOND_CENTS
    assert view.cost_baseline_cents == EAC_FIRST_CENTS + EAC_SECOND_CENTS + 30_000_000
    assert view.project_budget_cents == EAC_FIRST_CENTS + EAC_SECOND_CENTS + 30_000_000 + 5_000_000
    assert [row.project_code for row in view.projects] == ["TN-EAC-001", "TN-EAC-002"]
    assert view.projects[0].contingency is not None
    assert view.projects[0].contingency.in_analysis_cents == 8_000_000
    assert view.projects[1].management is None
    assert view.analysis_count == 1
    assert {line.project_label for line in view.movements} == {"TN-EAC-001", "TN-EAC-002"}
    assert view.alerts == ()


def test_burn_da_carteira_une_os_meses_e_para_no_corte_mais_novo(cenario: EacScenario) -> None:
    _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _reservar(
        cenario,
        kind=calculations.RESERVE_CONTINGENCY,
        value_cents=10_000_000,
        project=cenario.second,
    )
    _curva(cenario)
    _curva(
        cenario,
        project=cenario.second,
        periodo=(date(2026, 3, 1), date(2026, 11, 30)),
    )

    projeto = _visao(cenario)
    outro = _visao(cenario, _escopo(cenario.second))
    carteira = _visao(cenario, PORTFOLIO)

    assert carteira.burn[0].month == date(2026, 1, 1)
    assert carteira.burn[-1].month == date(2026, 11, 1)
    assert carteira.burn[0].expected_cents == projeto.burn[0].expected_cents + 10_000_000
    assert carteira.burn[0].actual_cents == 20_000_000 + 10_000_000
    assert carteira.burn[-1].actual_cents is None
    assert carteira.burn[8].month == date(2026, 9, 1)
    assert carteira.burn[8].actual_cents is not None
    assert outro.burn[6].actual_cents == 10_000_000
    assert carteira.expected_balance_cents == carteira.burn[8].expected_cents


# ── Mapa de controle e painel ────────────────────────────────────────────


def test_mapa_de_controle_mostra_a_faixa_reservas(cenario: EacScenario) -> None:
    _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _reservar(cenario, kind=calculations.RESERVE_MANAGEMENT, value_cents=5_000_000)
    _mudanca_aberta(
        cenario,
        Pedido(
            code="SM-TN-2026-0001",
            custo_cents=4_000_000,
            source=calculations.RESERVE_SOURCE_CONTINGENCY,
        ),
    )

    view = service.mapa_controle(cenario.session, scope=_escopo(cenario.first), reference_date=HOJE)

    assert view.reserves is not None
    assert view.reserves.contingency_balance_cents == 20_000_000
    assert view.reserves.contingency_consumption_pct == D("0.0")
    assert view.reserves.in_analysis_cents == 4_000_000
    assert view.reserves.management_balance_cents == 5_000_000
    assert view.reserves.covers_deviation

    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.first.id,
        linhas=(
            service.ErpCostLine(
                item_id=cenario.items["TN-EAC-001:2.1.1"],
                month=date(2026, 8, 1),
                projection_cents=30_000_000,
            ),
        ),
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )

    depois = service.mapa_controle(
        cenario.session, scope=_escopo(cenario.first), reference_date=HOJE
    )
    assert depois.total.deviation_cents == 30_000_000 - 6_000_000
    assert depois.reserves is not None
    assert not depois.reserves.covers_deviation


def test_sem_reservas_o_mapa_nao_tem_a_faixa(cenario: EacScenario) -> None:
    view = service.mapa_controle(cenario.session, scope=_escopo(cenario.first), reference_date=HOJE)

    assert view.reserves is None


def test_a_rota_do_mapa_traz_a_faixa_reservas(cenario: EacScenario) -> None:
    _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)

    resposta = routes.mapa_content(_requisicao_mapa(cenario.first))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Reservas" in corpo
    assert "Contingência com saldo de R$ 200.000,00" in corpo


def _requisicao_mapa(project: Project) -> func.HttpRequest:
    headers = {
        "X-Alpine-Request": "true",
        "X-Alpine-Target": "mapa-conteudo",
        auth.PRINCIPAL_HEADER: cabecalho_do_principal(MEMBER_EMAIL),
    }
    return func.HttpRequest(
        method="GET",
        url="/api/financeiro/mapa-de-controle",
        headers=headers,
        params={"projeto": str(project.id)},
        route_params={},
        body=b"",
    )


def test_consumo_da_contingencia_do_escopo(cenario: EacScenario) -> None:
    assert service.contingency_consumption(cenario.session, scope=_escopo(cenario.first)) is None

    contingency = _reservar(cenario, kind=calculations.RESERVE_CONTINGENCY, value_cents=20_000_000)
    _movimento(
        cenario,
        contingency,
        kind=calculations.MOVEMENT_CONSUMPTION,
        value_cents=-3_000_000,
    )

    project = service.contingency_consumption(cenario.session, scope=_escopo(cenario.first))
    assert project is not None
    assert (project.total_cents, project.consumed_cents, project.balance_cents) == (
        20_000_000,
        3_000_000,
        17_000_000,
    )

    portfolio = service.contingency_consumption(cenario.session, scope=PORTFOLIO)
    assert portfolio is not None
    assert portfolio.balance_cents == 17_000_000
