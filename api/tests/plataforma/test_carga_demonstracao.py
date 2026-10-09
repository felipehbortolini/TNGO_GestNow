"""Carga de demonstração deslocada e base de produção vazia (ISSUE-008).

O deslocamento de uma data conhecida, a idempotência da carga, a cobertura de
perfis, papéis e vínculos, e o preparo de produção com o primeiro Admin.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.carga import (
    DEMO_ANCHOR,
    ProductionStartError,
    prototype_collection,
    run_demonstration,
    run_for_mode,
)
from src.carga.plataforma import DATA_PATH
from src.core import calendario, config, numbering
from src.core.auth import _user_of
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry, Client, SeedRun
from src.core.scope import Scope
from src.modulos.central_acoes.models import Action
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import (
    Collaborator,
    CollaboratorScheduleRole,
    Company,
    Discipline,
    Location,
    ParameterVersion,
    Person,
    PortfolioWeight,
    Project,
    System,
    Unit,
)
from src.modulos.financeiro import service as financeiro
from src.modulos.financeiro.calculations import MOVEMENT_CONSUMPTION, MOVEMENT_IN_ANALYSIS
from src.modulos.financeiro.models import (
    Contract,
    ContractAddendum,
    ContractClaim,
    ContractEvaluation,
    ContractEvaluationCriterion,
    ContractMeasurement,
    ContractPaymentMilestone,
    ContractTimeExtension,
    EacItem,
    Reserve,
    ReserveMovement,
)
from src.modulos.governanca.models import ChangeRequest
from src.modulos.planejamento import calculations
from src.modulos.planejamento import service as planejamento
from src.modulos.planejamento.models import (
    EapBreakdown,
    EapItem,
    EapItemStep,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
    FieldDay,
    ProductivityDistribution,
    ProductivityEntry,
    ProductivityItem,
    ProductivityRevision,
    PunchItem,
    Stoppage,
    WorkSample,
    WorkSampleReason,
)
from src.modulos.programacao_semanal import permissions
from src.modulos.programacao_semanal import service as programacao_semanal
from src.modulos.programacao_semanal.models import Activity
from src.modulos.programacao_semanal.views import ActivityView
from src.modulos.riscos.models import Risk
from src.modulos.suprimentos import service as suprimentos
from src.modulos.suprimentos import validation as suprimentos_validation
from src.modulos.suprimentos.models import (
    PackageMilestone,
    ProcessInvitee,
    ProcessNegotiation,
    ProcessProposal,
    PurchaseOrder,
    PurchaseOrderMilestone,
    PurchasePackage,
    PurchaseProcess,
    Supplier,
    SupplierCategory,
    SupplierDocument,
    SupplierHistory,
)

# A demonstração inteira: a plataforma e a parte de cada módulo, na ordem em que entram.
PARTS = [
    "plataforma",
    "central_acoes",
    "financeiro",
    "financeiro-custos",
    "governanca",
    "governanca-licoes",
    "governanca-eac",
    "financeiro-curva",
    "financeiro-reservas",
    "financeiro-contratos",
    "financeiro-contratos-avaliacoes",
    "hse",
    "planejamento",
    "planejamento-eap",
    "planejamento-curva",
    "planejamento-produtividade",
    "planejamento-campo",
    "planejamento-punch",
    "programacao_semanal",
    "riscos",
    "financeiro-contratos-fluxos",
    "suprimentos-fornecedores",
    "suprimentos-pacotes",
    "suprimentos-processos",
    "suprimentos-pedidos",
]
MOCK_PEOPLE = 18
# O mock-base, a pessoa de demonstração do vínculo Cliente e as pessoas das demais cargas.
DEMO_PEOPLE = 31
PROJECTS = 3
COMPANIES = 21  # 18 do mock-base + 3 da Programação Semanal
SYSTEMS = 9
LOCATIONS = 15  # 9 do mock-base + 6 da Programação Semanal
DISCIPLINES = 12
UNITS = 14  # 11 do mock-base + kg, und e h da Programação Semanal
PARAMETER_GROUPS = 14


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _counts(session: Session) -> dict[str, int]:
    return {
        "clientes": _count(session, Client),
        "projetos": _count(session, Project),
        "empresas": _count(session, Company),
        "pessoas": _count(session, Person),
        "colaboradores": _count(session, Collaborator),
        "sistemas": _count(session, System),
        "locais": _count(session, Location),
        "disciplinas": _count(session, Discipline),
        "unidades": _count(session, Unit),
        "parametros": _count(session, ParameterVersion),
    }


def test_carga_desloca_as_datas_pela_diferenca_ate_hoje(db_session: Session) -> None:
    reference_date = DEMO_ANCHOR + timedelta(days=20)

    run_demonstration(db_session, reference_date=reference_date)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    assert project.start_date == date(2026, 1, 5) + timedelta(days=20)
    assert project.expected_end_date == date(2027, 3, 31) + timedelta(days=20)


def test_sem_deslocamento_na_ancora_do_prototipo(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-027")).one()
    assert project.start_date == date(2026, 6, 1)
    assert project.expected_end_date == date(2027, 2, 26)


def test_carga_de_demonstracao_e_idempotente(db_session: Session) -> None:
    first = run_demonstration(db_session, reference_date=DEMO_ANCHOR)
    counts = _counts(db_session)
    assert sorted(first) == sorted(PARTS)

    second = run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert second == []
    assert _counts(db_session) == counts
    assert _count(db_session, SeedRun) == len(PARTS)


def test_carga_cobre_os_numeros_da_plataforma(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    counts = _counts(db_session)
    assert counts["clientes"] == 1
    assert counts["projetos"] == PROJECTS
    assert counts["empresas"] == COMPANIES
    assert counts["pessoas"] == DEMO_PEOPLE
    assert counts["colaboradores"] == DEMO_PEOPLE
    assert counts["sistemas"] == SYSTEMS
    assert counts["locais"] == LOCATIONS
    assert counts["disciplinas"] == DISCIPLINES
    assert counts["unidades"] == UNITS
    assert counts["parametros"] == PARAMETER_GROUPS

    projects = db_session.scalars(select(Project).order_by(Project.code)).all()
    assert [project.code for project in projects] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ]
    assert [project.budget_cents for project in projects] == [
        4460000000,
        1820000000,
        740000000,
    ]
    assert db_session.scalars(select(Client)).one().acronym == "MHS"


def test_carga_grava_os_contratos_do_mock(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, Contract) == 9
    assert _count(db_session, ContractAddendum) == 3
    assert _count(db_session, ContractMeasurement) == 33

    contract = db_session.scalars(select(Contract).where(Contract.number == "CT-2026-011")).one()
    project = db_session.scalars(select(Project).where(Project.id == contract.project_id)).one()
    assert project.code == "TN-2026-014"
    item = db_session.scalars(select(EacItem).where(EacItem.id == contract.eac_item_id)).one()
    assert item.code == "1.2"
    assert contract.purchase_package_id is None
    assert (contract.start, contract.current_end) == (date(2026, 1, 12), date(2026, 11, 20))

    addendum = db_session.scalars(
        select(ContractAddendum).where(ContractAddendum.contract_id == contract.id)
    ).one()
    change = db_session.scalars(
        select(ChangeRequest).where(ChangeRequest.id == addendum.change_id)
    ).one()
    assert change.code == "SM-TN-2026-0001"
    claim = db_session.scalars(
        select(ContractClaim).where(ContractClaim.id == addendum.claim_id)
    ).one()
    assert claim.code == "CLM-TN-2026-0005"

    measurement = db_session.scalars(
        select(ContractMeasurement).where(
            ContractMeasurement.contract_id == contract.id,
            ContractMeasurement.number == "BM-01",
        )
    ).one()
    assert (measurement.period, measurement.gross_cents, measurement.situation) == (
        date(2026, 1, 1),
        34_500_000,
        "Paga",
    )
    milestone = db_session.scalars(
        select(ContractPaymentMilestone).where(
            ContractPaymentMilestone.id == measurement.milestone_id
        )
    ).one()
    assert (milestone.number, milestone.pct, milestone.situation) == ("M1", 10, "Pago")


def test_carga_grava_as_avaliacoes_do_mock(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, ContractEvaluation) == 10
    assert _count(db_session, ContractEvaluationCriterion) == 60

    contract = db_session.scalars(select(Contract).where(Contract.number == "CT-2026-014")).one()
    evaluation = db_session.scalars(
        select(ContractEvaluation).where(
            ContractEvaluation.contract_id == contract.id,
            ContractEvaluation.period == date(2026, 7, 1),
        )
    ).one()
    assert evaluation.kind == "Mensal"
    assert evaluation.comment == "Mobilização dentro do plano."
    evaluator = db_session.scalars(select(Person).where(Person.id == evaluation.evaluator_id)).one()
    assert evaluator.email == "rafael.costa@exemplo.com"
    version = db_session.scalars(
        select(ParameterVersion).where(ParameterVersion.id == evaluation.parameter_version_id)
    ).one()
    assert (version.group, version.version) == ("avaliacaoContratada", 1)

    criteria = db_session.scalars(
        select(ContractEvaluationCriterion)
        .where(ContractEvaluationCriterion.evaluation_id == evaluation.id)
        .order_by(ContractEvaluationCriterion.id)
    ).all()
    assert [(row.criterion, row.weight, row.note) for row in criteria] == [
        ("hse", 25, 4),
        ("qualidade", 20, 4),
        ("prazo", 20, 3),
        ("gestao", 15, 3),
        ("recursos", 10, 4),
        ("documentacao", 10, 3),
    ]


def test_carga_grava_os_fluxos_do_contrato(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, ContractPaymentMilestone) == 14
    assert _count(db_session, ContractClaim) == 7
    assert _count(db_session, ContractTimeExtension) == 4

    claim = db_session.scalars(
        select(ContractClaim).where(ContractClaim.code == "CLM-TN-2026-0004")
    ).one()
    risk = db_session.scalars(select(Risk).where(Risk.code == "RSK-TN-2026-0003")).one()
    assert claim.risk_id == risk.id
    assert claim.change_id is not None
    assert claim.recognized_cents == 40_000_000
    assert claim.recognized_days == 21
    assert claim.closed_on == date(2026, 7, 10)

    extension = db_session.scalars(
        select(ContractTimeExtension).where(ContractTimeExtension.code == "EOT-TN-2026-0001")
    ).one()
    assert (extension.claim_id, extension.granted_days, extension.situation) == (
        claim.id,
        21,
        "Concedida parcialmente",
    )
    assert extension.requested_on == date(2026, 4, 20)
    assert extension.decided_on == date(2026, 7, 10)


def test_carga_grava_a_eap_do_mock(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, EapItem) == 110
    assert _count(db_session, EapItemStep) == 154
    assert _count(db_session, EapMeasurement) == 388
    assert _count(db_session, EapRevision) == 5
    assert _count(db_session, EapRevisionItem) == 144
    assert _count(db_session, EapBreakdown) == 1

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    access = configuracoes.find_access_by_email(db_session, "leonardo.gomes@exemplo.com")
    assert access is not None
    visao = planejamento.eap_overview(
        db_session,
        user=_user_of(access),
        scope=Scope(project_id=project.id, source="url"),
        reference_date=DEMO_ANCHOR,
    )

    assert (visao.indicators.work_packages, visao.indicators.planning_packages) == (37, 1)
    assert visao.indicators.overdue == 2
    assert visao.current_revision is not None
    assert (visao.current_revision.revision, visao.current_revision.package_count) == (2, 38)
    assert [(item.source_code, item.target_code) for item in visao.breakdowns] == [
        ("5.2.1", "5.2.2")
    ]
    assert [node.code for node in visao.nodes if node.is_work_package and node.overdue] == [
        "2.1.1",
        "3.2.1",
    ]


def test_oraculo_da_curva_s_fisica_com_a_data_deslocada(db_session: Session) -> None:
    """O oráculo da ISSUE-039: o previsto e o real do protótipo no corte, com a data deslocada.

    A referência fica dentro do mês do corte (a âncora mais cinco dias); um deslocamento que
    atravesse o mês move o corte junto, como manda a data viva (D6). A série inteira é comparada
    mês a mês com o mock, com a tolerância de um décimo que o arredondamento das medições
    proporcionais pode gastar.
    """
    reference_date = DEMO_ANCHOR + timedelta(days=5)
    run_demonstration(db_session, reference_date=reference_date)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    visao = planejamento.curva_fisica_overview(
        db_session,
        scope=Scope(project_id=project.id, source="url"),
        reference_date=reference_date,
    )
    mock = next(
        source for source in prototype_collection("curvaFisica") if source["projetoId"] == 1
    )

    assert visao.indicators.cut_month == date(2026, 9, 1), "o mês do corte"
    assert visao.indicators.predicted == Decimal("65.7"), "o previsto do protótipo no corte"
    assert visao.indicators.actual == Decimal("61.8"), "o real do protótipo no corte"
    assert list(visao.series.baseline) == [Decimal(str(value)) for value in mock["baseline"]], (
        "a linha de base congelada é a do mock convertido"
    )

    tolerance = Decimal("0.1")
    for month, expected, found in zip(
        visao.series.months, mock["real"], visao.series.real, strict=True
    ):
        if expected is None:
            continue
        assert found is not None
        assert abs(found - Decimal(str(expected))) <= tolerance, (
            f"o real de {month}: {found} contra {expected} do protótipo"
        )

    carteira = planejamento.curva_fisica_overview(
        db_session,
        scope=Scope(project_id=None, source="padrao"),
        reference_date=reference_date,
    )
    assert not carteira.is_empty, "a carteira tem a união das curvas"
    assert carteira.indicators.cut_month == date(2026, 9, 1), "o corte da carteira"
    assert len(carteira.composition) == 3, "os três projetos na composição"


def test_oraculo_dos_kpis_de_planejamento_com_a_data_deslocada(db_session: Session) -> None:
    """O oráculo da ISSUE-040: o SPI e o avanço por área do protótipo, com a data deslocada.

    A mesma referência do oráculo da Curva S (a âncora mais cinco dias), que mantém o corte em
    set/26. O previsto e o real do projeto 1 são os da curva (65,7% e 61,8%), o SPI é 0,94 e as
    áreas da EAP batem com o mock de ``avancoAreas``; a soma ponderada fecha com a curva. A
    carteira devolve uma linha por projeto, com o peso da ponderação.
    """
    reference_date = DEMO_ANCHOR + timedelta(days=5)
    run_demonstration(db_session, reference_date=reference_date)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    visao = planejamento.planning_kpis_overview(
        db_session,
        scope=Scope(project_id=project.id, source="url"),
        reference_date=reference_date,
    )
    mock = [source for source in prototype_collection("avancoAreas") if source["projetoId"] == 1]

    assert not visao.is_empty, "há curva congelada no projeto 1"
    assert visao.indicators.cut_month == date(2026, 9, 1), "o mês do corte"
    assert visao.indicators.predicted == Decimal("65.7"), "o previsto da curva no corte"
    assert visao.indicators.actual == Decimal("61.8"), "o real da curva no corte"
    assert visao.indicators.spi == Decimal("0.94"), "o SPI de 0,94 do oráculo"

    assert [row.name for row in visao.rows] == [source["area"] for source in mock], (
        "as áreas de nível 1 da EAP são as do mock"
    )
    for row, source in zip(visao.rows, mock, strict=True):
        assert (row.weight, row.predicted, row.actual) == (
            Decimal(str(source["peso"])),
            Decimal(str(source["previsto"])),
            Decimal(str(source["real"])),
        ), f"o avanço da área {row.name}: os números do protótipo"

    previsto = calculations.eap_weighted_progress(
        [calculations.EapWeightedValue(row.weight, row.predicted) for row in visao.rows]
    )
    real = calculations.eap_weighted_progress(
        [calculations.EapWeightedValue(row.weight, row.actual) for row in visao.rows]
    )
    assert (previsto, real) == (visao.indicators.predicted, visao.indicators.actual), (
        "a soma ponderada das áreas fecha com a Curva S"
    )

    carteira = planejamento.planning_kpis_overview(
        db_session,
        scope=Scope(project_id=None, source="padrao"),
        reference_date=reference_date,
    )
    assert carteira.is_portfolio, "a carteira é o escopo padrão"
    assert not carteira.is_empty, "a carteira tem a união das curvas"
    assert [row.code for row in carteira.rows] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ], "uma linha por projeto com curva"
    assert all(row.weight > 0 for row in carteira.rows), "cada projeto tem peso na carteira"


def test_oraculo_das_reservas_com_a_data_deslocada(db_session: Session) -> None:
    """O oráculo da ISSUE-041: as reservas do protótipo no projeto 1, com a data deslocada.

    A mesma referência do oráculo da Curva S (a âncora mais cinco dias), que mantém o corte em
    set/26: o limite de consumo é o avanço físico real (61,8%) mais a tolerância de 10 p.p. =
    71,8%. O consumo de 40 mi vem da SM-TN-2026-0004, aprovada com a fonte da reserva; as SMs ainda
    em análise (36 e 12 mi) não geram movimento e somam 48 mi no pedido derivado. A carteira soma os
    três projetos (saldo de 269 mi), a reserva gerencial fica fora da linha de base de custo e o
    total da carteira fecha a soma dos projetos.
    """
    reference_date = DEMO_ANCHOR + timedelta(days=5)
    run_demonstration(db_session, reference_date=reference_date)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    visao = financeiro.contingency_overview(
        db_session,
        scope=Scope(project_id=project.id, source="url"),
        reference_date=reference_date,
    )

    assert visao.contingency is not None, "o projeto 1 tem a reserva de contingência do mock"
    assert (
        visao.contingency.total_cents,
        visao.contingency.consumed_cents,
        visao.contingency.balance_cents,
    ) == (200_000_000, 40_000_000, 160_000_000)
    assert visao.contingency.consumption_pct == Decimal("20.0")
    assert visao.contingency.in_analysis_cents == 48_000_000
    assert visao.contingency.balance_after_analysis_cents == 112_000_000
    assert visao.analysis_count == 2
    assert visao.management is not None, "o projeto 1 tem a reserva gerencial do mock"
    assert (visao.management.total_cents, visao.management.balance_cents) == (
        90_000_000,
        90_000_000,
    )
    assert visao.physical_actual == Decimal("61.8"), "o real da curva no corte"
    assert visao.consumption_limit_pct == Decimal("71.8"), "o real mais a tolerância de 10 p.p."
    assert visao.cost_baseline_cents == visao.eac_current_cents + 160_000_000, (
        "a linha de base de custo é o orçado atual da EAC mais o saldo da contingência"
    )
    assert visao.project_budget_cents == visao.cost_baseline_cents + 90_000_000, (
        "o orçamento do projeto soma a reserva gerencial, fora da linha de base"
    )

    consumos = [line for line in visao.movements if line.kind == MOVEMENT_CONSUMPTION]
    assert [(line.change_code, line.value_cents, line.balance_cents) for line in consumos] == [
        ("SM-TN-2026-0004", -40_000_000, 160_000_000)
    ], "o consumo aprovado com a fonte da reserva é o único movimento negativo do projeto"
    em_analise = [line for line in visao.movements if line.kind == MOVEMENT_IN_ANALYSIS]
    assert [(line.change_code, line.value_cents) for line in em_analise] == [
        ("SM-TN-2026-0006", -36_000_000),
        ("SM-TN-2026-0003", -12_000_000),
    ], "as SMs abertas aparecem como Em análise, sem efeito no saldo"

    assert _count(db_session, Reserve) == PROJECTS * 2, "as duas reservas de cada projeto"
    assert _count(db_session, ReserveMovement) == PROJECTS * 2 + 2, (
        "as constituições mais os dois consumos aprovados; as SMs em análise não geram movimento"
    )

    carteira = financeiro.contingency_overview(
        db_session,
        scope=Scope(project_id=None, source="padrao"),
        reference_date=reference_date,
    )
    assert carteira.is_portfolio
    assert carteira.contingency is not None
    assert carteira.contingency.balance_cents == 269_000_000, "160 + 72 + 37 mi da carteira"
    assert carteira.management is not None
    assert carteira.management.balance_cents == 141_000_000, "90 + 36 + 15 mi da carteira"
    assert [row.project_code for row in carteira.projects] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ]


def test_oraculo_da_curva_s_financeira_e_dos_kpis_de_custo(db_session: Session) -> None:
    """O oráculo da ISSUE-042: a curva financeira e os KPIs de custo do protótipo no corte.

    A mesma referência do oráculo da Curva S física (a âncora mais cinco dias), que mantém o corte
    em set/26. O planejado de jan/26 é o do mock convertido (93.660.000 centavos); o realizado de
    ago/26 é 2.280.000.000 e o do corte, 2.870.000.000; o comprometido fecha 4.113.000.000. O EV é
    o avanço físico real (61,8%) sobre o BAC e o AC, o realizado do ERP: CPI 0,96, SPI de custo
    0,94, CV de menos 113.720.000, a EAC pelo CPI de 4.644.012.945 e o TCPI de 1,07 (divergências
    registradas em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``, "pendente de aceite"). Na carteira, o PV,
    o EV e o AC são a soma dos projetos.
    """
    reference_date = DEMO_ANCHOR + timedelta(days=5)
    run_demonstration(db_session, reference_date=reference_date)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    curve = financeiro.financial_curve_overview(
        db_session, scope=Scope(project_id=project.id, source="url"), reference_date=reference_date
    )

    assert curve.series.months[curve.series.cut_index] == date(2026, 9, 1), "o mês do corte"
    assert curve.series.planned[0] == 93_660_000, "o planejado de 2026-01 do protótipo"
    august = curve.series.months.index(date(2026, 8, 1))
    assert curve.series.actual[august] == 2_280_000_000, "o realizado de 2026-08 do protótipo"
    assert curve.series.actual[curve.series.cut_index] == 2_870_000_000, "o realizado do corte"
    assert curve.series.committed[curve.series.cut_index] == 4_113_000_000, (
        "o comprometido do corte"
    )
    assert curve.kpis is not None
    assert curve.kpis.committed_pct == Decimal("92.2")
    assert curve.kpis.trend_cents == 4_644_012_945, "a tendência chega à EAC pelo CPI"

    kpis = financeiro.cost_kpis_overview(
        db_session, scope=Scope(project_id=project.id, source="url"), reference_date=reference_date
    )
    assert kpis.indicators is not None
    assert (kpis.indicators.cpi, kpis.indicators.spi) == (Decimal("0.96"), Decimal("0.94"))
    assert kpis.indicators.cv_cents == -113_720_000
    assert kpis.indicators.eac_by_cpi_cents == 4_644_012_945
    assert kpis.indicators.tcpi == Decimal("1.07")
    assert kpis.vac_cents == -65_500_000
    assert (kpis.committed_cents, kpis.committed_pct) == (4_113_000_000, Decimal("92.2"))

    views = [
        financeiro.cost_kpis_overview(
            db_session,
            scope=Scope(project_id=item.id, source="url"),
            reference_date=reference_date,
        )
        for item in db_session.scalars(select(Project).order_by(Project.code))
    ]
    totals = {"pv_cents": 0, "ev_cents": 0, "ac_cents": 0}
    for view in views:
        actual = view.actual
        assert actual is not None, "os três projetos têm valor agregado no corte"
        totals["pv_cents"] += actual.pv_cents
        totals["ev_cents"] += actual.ev_cents
        totals["ac_cents"] += actual.ac_cents

    carteira = financeiro.cost_kpis_overview(
        db_session, scope=Scope(project_id=None, source="padrao"), reference_date=reference_date
    )
    assert carteira.actual is not None
    assert (carteira.actual.pv_cents, carteira.actual.ev_cents, carteira.actual.ac_cents) == (
        totals["pv_cents"],
        totals["ev_cents"],
        totals["ac_cents"],
    ), "a carteira soma o PV, o EV e o AC dos projetos"
    assert [row.project_code for row in carteira.projects] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ]


def test_oraculo_do_cronograma_de_desembolso(db_session: Session) -> None:
    """O oráculo da ISSUE-043: o saldo a desembolsar do protótipo, com a data deslocada.

    A mesma referência do oráculo da Curva S financeira (a âncora mais cinco dias), que mantém
    o corte em set/26. No projeto 1, a projeção no término fecha em R$ 45.255.000,00 e o
    realizado do ERP, em R$ 28.700.000,00, deixando R$ 16.555.000,00 a desembolsar; a soma dos
    meses futuros de cada item é o seu saldo (o invariante da distribuição) e o histograma traz
    o previsto, o realizado e o projetado do mês. A carteira soma os três projetos.
    """
    reference_date = DEMO_ANCHOR + timedelta(days=5)
    run_demonstration(db_session, reference_date=reference_date)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    visao = financeiro.disbursement_overview(
        db_session,
        scope=Scope(project_id=project.id, source="url"),
        reference_date=reference_date,
    )

    assert visao.cut_month == date(2026, 9, 1), "o mês do corte"
    assert visao.future_months[0] == date(2026, 10, 1), "os meses a desembolsar começam em out/26"
    assert visao.projection_cents == 4_525_500_000, "a projeção no término do protótipo"
    assert visao.actual_until_cut_cents == 2_870_000_000, "o realizado do ERP até o corte"
    assert visao.balance_cents == 1_655_500_000, "R$ 16.555.000,00 a desembolsar"
    assert visao.balance_cents == visao.projection_cents - visao.actual_until_cut_cents

    for item in visao.items:
        assert sum(item.amounts) == item.balance_cents, (
            f"a soma dos meses futuros do item {item.code} é o seu saldo"
        )
    assert sum(visao.totals) == visao.balance_cents, "o rodapé fecha o saldo do escopo"

    meses = {linha.month: linha for linha in visao.histogram}
    setembro = meses[date(2026, 9, 1)]
    assert setembro.actual_cents == 590_000_000, "o realizado de set/26 do fechamento"
    assert setembro.projected_cents is None, "o projetado só existe depois do corte"
    outubro = meses[date(2026, 10, 1)]
    assert outubro.planned_cents == 450_460_000
    assert outubro.actual_cents is None, "depois do corte não há realizado"
    assert outubro.projected_cents is not None, "a tendência mensal entra como projetado"

    assert visao.kpis is not None
    assert visao.kpis.actual_pct == Decimal("63.4")

    carteira = financeiro.disbursement_overview(
        db_session, scope=Scope(project_id=None, source="padrao"), reference_date=reference_date
    )
    assert carteira.is_portfolio
    assert carteira.balance_cents == 3_399_500_000, "16.555 + 12.430 + 5.010 mil da carteira"
    assert [row.code for row in carteira.items if row.level == 1] == ["1", "2", "3"]
    assert carteira.totals == tuple(
        sum(row.amounts[index] for row in carteira.items if row.level == 1)
        for index in range(len(carteira.future_months))
    )


def test_oraculo_da_produtividade_com_a_data_deslocada(db_session: Session) -> None:
    """O oráculo da ISSUE-046: o plano de quantidades do protótipo, com a data deslocada.

    O mock traz 14 itens dos três projetos, 170 apontamentos e a distribuição da revisão
    vigente de cada item (328 semanas). No projeto 1, no corte de S39 e sem deslocamento, o
    avanço por quantidades fecha em 59,2% contra 67,5% previstos, SPI 0,88, FP 1,08 (janela
    1,12) e aderência da semana 80,7%; o atraso aparece em 8 itens ativos.
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, ProductivityItem) == 14
    assert _count(db_session, ProductivityRevision) == 15
    assert _count(db_session, ProductivityDistribution) == 328
    assert _count(db_session, ProductivityEntry) == 170

    totals = {
        project.code: db_session.scalar(
            select(func.sum(ProductivityItem.total)).where(
                ProductivityItem.project_id == project.id
            )
        )
        for project in db_session.scalars(select(Project)).all()
    }
    assert totals == {
        "TN-2026-014": Decimal("173214"),
        "TN-2026-021": Decimal("2002"),
        "TN-2026-027": Decimal("1108"),
    }

    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    user = _user_of(admin)
    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    scope = Scope(project_id=project.id, source="url")
    visao = planejamento.quantities_overview(
        db_session, user=user, scope=scope, reference_date=DEMO_ANCHOR
    )
    assert visao.cut_week == "2026-S39"
    assert visao.current_week == "2026-S39"
    assert len(visao.items) == 9
    assert visao.draft_count == 1, "o QTD-06 está em elaboração"
    indicators = visao.indicators
    assert (
        indicators.pct_prev,
        indicators.pct_real,
        indicators.spi,
        indicators.pf,
        indicators.pf_window,
    ) == (Decimal("67.5"), Decimal("59.2"), Decimal("0.88"), Decimal("1.08"), Decimal("1.12"))
    assert (indicators.week_adherence, indicators.window_adherence) == (
        Decimal("80.7"),
        Decimal("79.7"),
    )
    assert (indicators.pending, indicators.late_trend) == (2, 8)
    assert len(visao.weekly["periodos"]) == 51
    assert [(row.group, row.total, row.real_acum) for row in visao.groups] == [
        ("Aço", Decimal("3030"), Decimal("1987.2")),
        ("Cabo elétrico", Decimal("146000"), Decimal("21509")),
        ("Concreto", Decimal("14200"), Decimal("11797")),
        ("Painel elétrico", Decimal("64"), Decimal("14")),
        ("Tubulação", Decimal("420"), Decimal("137.3")),
    ]

    qtd01 = next(item for item in visao.items if item.code == "QTD-01")
    detalhe = planejamento.item_detail(
        db_session, user=user, scope=scope, item_id=qtd01.id, reference_date=DEMO_ANCHOR
    )
    assert (len(detalhe.weeks), detalhe.weeks[0].week, detalhe.weeks[-1].week) == (
        25,
        "2026-S24",
        "2026-S48",
    )
    assert [(row.revision, row.total, row.change_code) for row in detalhe.revisions] == [
        (0, Decimal("1850"), "")
    ]

    qtd08 = next(item for item in visao.items if item.code == "QTD-08")
    assert (qtd08.revision, qtd08.total, qtd08.figures.real_acum) == (
        1,
        Decimal("14200"),
        Decimal("11797"),
    )

    carteira = planejamento.quantities_overview(
        db_session,
        user=user,
        scope=Scope(project_id=None, source="padrao"),
        reference_date=DEMO_ANCHOR,
    )
    assert carteira.is_portfolio
    assert len(carteira.items) == 14
    assert carteira.unit_series == "HH", "a carteira mistura unidades"
    assert (carteira.indicators.pct_real, carteira.indicators.spi) == (
        Decimal("55.9"),
        Decimal("0.87"),
    )


def test_oraculo_das_horas_efetivas_com_a_data_deslocada(db_session: Session) -> None:
    """O oráculo da ISSUE-047: a jornada, a amostragem e as paralisações do protótipo.

    O mock traz 180 jornadas, 360 rodadas e 31 paralisações nos três projetos; no projeto 1
    (TN-2026-014), desde o início e sem deslocamento, são 120 jornadas, 240 rodadas e 25
    paralisações: CP média de 6,81 h/dia (utilização 77,4%), 22.870 HH efetivas e 6.691 HH
    improdutivas, 55,26% trabalhando, o Pareto de paradas começando no direcionamento da
    liderança (686) e fechando no direito de recusa (47), e 750,0 Hhora e 58,5 Mhora parados.
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, FieldDay) == 180
    assert _count(db_session, WorkSample) == 360
    assert _count(db_session, WorkSampleReason) == 2411
    assert _count(db_session, Stoppage) == 31
    project_1 = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    dias = db_session.scalar(
        select(func.count()).select_from(FieldDay).where(FieldDay.project_id == project_1.id)
    )
    rodadas = db_session.scalar(
        select(func.count()).select_from(WorkSample).where(WorkSample.project_id == project_1.id)
    )
    paradas = db_session.scalar(
        select(func.count()).select_from(Stoppage).where(Stoppage.project_id == project_1.id)
    )
    assert (dias, rodadas, paradas) == (120, 240, 25)

    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    user = _user_of(admin)
    scope = Scope(project_id=project_1.id, source="url")
    visao = planejamento.hours_overview(
        db_session,
        user=user,
        scope=scope,
        hours_filter=planejamento.HoursFilter(period="tudo"),
        reference_date=DEMO_ANCHOR,
    )
    assert visao.cut_week == "2026-S39"
    assert visao.current_week == "2026-S39"
    assert (visao.window_start, visao.window_end) == (None, DEMO_ANCHOR)

    capacidade = visao.capacity
    assert capacidade.records == 120
    assert capacidade.capacity == Decimal("6.81")
    assert capacidade.utilization == Decimal("77.4")
    assert capacidade.effective_hh == Decimal("22870")
    assert capacidade.idle_hh == Decimal("6691")
    assert (capacidade.morning_delay_min, capacidade.afternoon_delay_min) == (
        Decimal("32"),
        Decimal("7"),
    )
    assert capacidade.lunch_min == Decimal("88")

    amostragem = visao.sample_summary
    assert (amostragem.records, amostragem.people) == (240, 5711)
    assert (
        amostragem.working_pct,
        amostragem.transit_pct,
        amostragem.stopped_pct,
    ) == (Decimal("55.26"), Decimal("9.93"), Decimal("34.81"))
    assert (visao.stop_reasons[0].reason, visao.stop_reasons[0].total) == (
        "Direcionamento da liderança para execução",
        686,
    )
    assert (visao.stop_reasons[-1].reason, visao.stop_reasons[-1].total) == (
        "Direito de recusa (trabalho seguro)",
        47,
    )
    assert visao.stop_reasons[0].accumulated == Decimal("34.5")
    assert [row.reason for row in visao.transit_reasons] == [
        "Material / insumo / acessório",
        "Água / banheiro",
        "Ferramenta",
        "Máquina / equipamento",
        "Entre frentes de serviço",
    ]

    resumo = visao.stoppage_summary
    assert resumo.events == 25
    assert resumo.crew_hours == Decimal("750.0")
    assert resumo.machine_hours == Decimal("58.5")
    assert resumo.client_hours == Decimal("372.0")
    assert resumo.weather_hours == Decimal("127.3")
    assert resumo.by_responsibility[0].key == "Cliente"
    assert visao.by_area[0].area == "Flotação 310"

    carteira = planejamento.hours_overview(
        db_session,
        user=user,
        scope=Scope(project_id=None, source="padrao"),
        hours_filter=planejamento.HoursFilter(period="tudo"),
        reference_date=DEMO_ANCHOR,
    )
    assert carteira.is_portfolio
    assert len(carteira.field_days) == 180
    assert len(carteira.samples) == 360
    assert len(carteira.stoppages) == 31


def test_oraculo_dos_kpis_de_produtividade_com_a_data_deslocada(db_session: Session) -> None:
    """O oráculo da ISSUE-048: os KPIs de performance do protótipo, na janela do corte.

    No projeto 1 (TN-2026-014), no corte S39 e sem deslocamento, a janela de 4 semanas até o
    corte fecha o avanço de 59,2% x 67,5% previstos (SPI de quantidades 0,88), o FP de 1,12 nas
    últimas 4 semanas, a CP de 6,81 h/dia e 55,26% trabalhando; a Alfa Montagens, com indicador
    fora da faixa, tem o plano de ação aberto na Central desde S38 (PRD-2026-S38-01).
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    user = _user_of(admin)
    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    scope = Scope(project_id=project.id, source="url")
    visao = planejamento.performance_overview(
        db_session, user=user, scope=scope, reference_date=DEMO_ANCHOR
    )

    assert visao.cut_week == "2026-S39"
    assert (visao.window_weeks[0], visao.window_weeks[-1]) == ("2026-S36", "2026-S39")
    geral = visao.general
    assert (geral.quantities.pct_real, geral.quantities.pct_prev, geral.quantities.spi) == (
        Decimal("59.2"),
        Decimal("67.5"),
        Decimal("0.88"),
    )
    assert geral.quantities.pf_window == Decimal("1.12")
    assert geral.capacity.capacity == Decimal("6.81")
    assert geral.capacity.utilization == Decimal("77.4")
    assert geral.sample.working_pct == Decimal("55.26")
    assert (geral.stoppages.crew_hours, geral.stoppages.machine_hours) == (
        Decimal("638.7"),
        Decimal("39.5"),
    )
    assert (geral.schedule.spi_t, geral.schedule.slip_weeks) == (Decimal("0.94"), 4)

    alfa = next(bloco for bloco in visao.companies if bloco.company_name == "Alfa Montagens")
    assert (alfa.quantities.pct_real, alfa.quantities.spi) == (Decimal("43.5"), Decimal("0.83"))
    assert alfa.quantities.pf_window == Decimal("1.15")
    assert alfa.quantities.window_adherence == Decimal("78.8")
    assert alfa.capacity.capacity == Decimal("6.60")
    assert alfa.sample.working_pct == Decimal("50.90")
    assert alfa.alerts == ("pf", "spi")
    assert alfa.attentions == ("adherence", "working")
    assert alfa.schedule.spi_t == Decimal("0.89")

    zeta = next(bloco for bloco in visao.companies if bloco.company_name == "Zeta Civil")
    assert (zeta.quantities.pct_real, zeta.quantities.spi) == (Decimal("80.7"), Decimal("0.92"))
    assert zeta.quantities.pf_window == Decimal("1.06")

    anterior = planejamento.performance_overview(
        db_session,
        user=user,
        scope=scope,
        performance_filter=planejamento.PerformanceFilter(cut_week="2026-S38"),
        reference_date=DEMO_ANCHOR,
    )
    alfa_anterior = next(
        bloco for bloco in anterior.companies if bloco.company_name == "Alfa Montagens"
    )
    assert alfa_anterior.action is not None
    assert alfa_anterior.action.reference == f"PRD-2026-S38-{alfa.company_id:02d}"
    assert alfa.action is None


def test_oraculo_da_punch_list_com_a_data_deslocada(db_session: Session) -> None:
    """O oráculo da ISSUE-049: os itens do protótipo, o bloqueio dos sistemas e a ação na Central.

    O mock traz 20 itens (16 no projeto 1 e 4 no projeto 2), um cancelado sem ação derivada; no
    projeto 1, sem deslocamento, são 12 abertos (4 da categoria A), 2 aguardando verificação e
    2 vencidos no prazo, com 3 fechados. O sistema 420 fica bloqueado para a Completação
    mecânica pelo item A aberto e os sistemas 210, 310 e 420 para o Comissionamento; o item
    PL-TN-2026-0001, fechado, tem a ação concluída na data do fechamento, como o protótipo
    derivava (``acaoDoPunch``).
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, PunchItem) == 20
    project_1 = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    do_projeto = db_session.scalar(
        select(func.count()).select_from(PunchItem).where(PunchItem.project_id == project_1.id)
    )
    assert do_projeto == 16

    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    user = _user_of(admin)
    visao = planejamento.punch_overview(
        db_session,
        user=user,
        scope=Scope(project_id=project_1.id, source="url"),
        punch_filter=planejamento.PunchFilter(),
        reference_date=DEMO_ANCHOR,
    )

    assert (
        visao.kpis.opened,
        visao.kpis.open_a,
        visao.kpis.verifying,
        visao.kpis.overdue,
        visao.kpis.closed,
        visao.kpis.valid,
    ) == (12, 4, 2, 2, 3, 15)
    assert [bloco.code for bloco in visao.blocked_for("Completação mecânica")] == ["420"]
    assert [bloco.code for bloco in visao.blocked_for("Comissionamento")] == ["210", "310", "420"]
    assert len(visao.blocked_for("Aceite definitivo")) == 4

    acoes = db_session.scalars(
        select(Action).where(Action.origin == "Punch list", Action.project_id == project_1.id)
    ).all()
    assert len(acoes) == 15, "o item cancelado não gera ação, como o protótipo"
    por_referencia = {acao.origin_ref: acao for acao in acoes}
    assert por_referencia["PL-TN-2026-0001"].completed_on == date(2026, 8, 20)
    assert por_referencia["PL-TN-2026-0003"].completed_on is None
    todas = planejamento.punch_overview(
        db_session,
        user=user,
        scope=Scope(project_id=project_1.id, source="url"),
        punch_filter=planejamento.PunchFilter(situation=""),
        reference_date=DEMO_ANCHOR,
    )
    fechado = next(item for item in todas.rows if item.code == "PL-TN-2026-0001")
    aberto = next(item for item in todas.rows if item.code == "PL-TN-2026-0003")
    assert (fechado.situation, fechado.action is not None) == ("Fechado", True)
    assert (aberto.situation, aberto.overdue, aberto.action is not None) == (
        "Em tratamento",
        True,
        True,
    )

    carteira = planejamento.punch_overview(
        db_session,
        user=user,
        scope=Scope(project_id=None, source="padrao"),
        punch_filter=planejamento.PunchFilter(situation=""),
        reference_date=DEMO_ANCHOR,
    )
    assert carteira.is_portfolio
    assert len(carteira.rows) == 20, "a carteira traz os itens dos dois projetos, cancelado incluso"
    assert {item.project_code for item in carteira.rows} == {"TN-2026-014", "TN-2026-021"}


def test_oraculo_do_painel_da_punch_list(db_session: Session) -> None:
    """O oráculo da ISSUE-050: o aging, as contagens, a liberação por marco e o burndown.

    No projeto 1, na âncora: 3 itens abertos na faixa até 7 dias, 7 na de 8 a 30 e 2 acima de 30,
    por categoria; os abertos por disciplina, empresa e sistema; os sistemas 210, 310 e 420
    bloqueados para a Completação mecânica ou o Comissionamento (75,0% e 25,0% liberados) e o
    Aceite definitivo bloqueado pelos 4 sistemas; o burndown acumulado dos 15 itens válidos,
    fechando com 15 abertos, 3 fechados e 12 em aberto.
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    project_1 = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    user = _user_of(admin)
    painel = planejamento.punch_dashboard(
        db_session,
        user=user,
        scope=Scope(project_id=project_1.id, source="url"),
        reference_date=DEMO_ANCHOR,
    )

    assert not painel.is_empty
    assert [
        (linha.label, linha.counts.a, linha.counts.b, linha.counts.c) for linha in painel.aging
    ] == [
        ("Até 7 dias", 1, 1, 1),
        ("8 a 30 dias", 3, 3, 1),
        ("Mais de 30 dias", 0, 2, 0),
    ]
    assert [(linha.label, linha.counts.total) for linha in painel.disciplines] == [
        ("Arquitetura", 1),
        ("Automação", 1),
        ("Civil", 1),
        ("Elétrica", 1),
        ("Instrumentação", 2),
        ("Mecânica", 3),
        ("Tubulação", 3),
    ]
    assert [
        (linha.label, linha.counts.a, linha.counts.b, linha.counts.c) for linha in painel.companies
    ] == [
        ("Alfa Montagens", 4, 6, 0),
        ("Zeta Civil", 0, 0, 2),
    ]
    assert [
        (sistema.code, sistema.a_open, sistema.b_open, sistema.c_open) for sistema in painel.systems
    ] == [
        ("210", 2, 2, 0),
        ("310", 1, 3, 0),
        ("420", 1, 0, 0),
        ("510", 0, 1, 2),
    ]
    assert [
        (liberacao.milestone, liberacao.systems, liberacao.blocked, liberacao.released_pct)
        for liberacao in painel.releases
    ] == [
        ("Completação mecânica", 4, 1, Decimal("75.0")),
        ("Comissionamento", 4, 3, Decimal("25.0")),
        ("Aceite definitivo", 4, 4, Decimal("0.0")),
    ]
    assert [sistema.code for sistema in painel.blocked_systems] == ["210", "310", "420"]

    assert [point.week for point in painel.burndown] == [
        date(2026, 7, 27),
        date(2026, 8, 3),
        date(2026, 8, 10),
        date(2026, 8, 17),
        date(2026, 8, 24),
        date(2026, 8, 31),
        date(2026, 9, 7),
        date(2026, 9, 14),
        date(2026, 9, 21),
        date(2026, 9, 28),
    ]
    assert [(point.opened, point.closed, point.balance) for point in painel.burndown] == [
        (0, 0, 0),
        (1, 0, 1),
        (2, 0, 2),
        (4, 0, 4),
        (4, 2, 2),
        (6, 2, 4),
        (8, 3, 5),
        (11, 3, 8),
        (14, 3, 11),
        (15, 3, 12),
    ]
    assert painel.burndown_chart["modo"] == "acumulado"
    assert [serie["rotulo"] for serie in painel.burndown_chart["series"]] == [
        "Abertos (acumulado)",
        "Fechados (acumulado)",
        "Saldo em aberto",
    ]
    assert [grafico["linhas"][0]["rotulo"] for grafico in painel.aging_chart["paineis"]] == [
        "Até 7 dias",
        "8 a 30 dias",
        "Mais de 30 dias",
    ]


def test_oraculo_do_fluxo_da_programacao_semanal(db_session: Session) -> None:
    """O oráculo da ISSUE-052: os estados do fluxo e a fila da próxima ação, com a carga.

    Na âncora, o projeto 1 (TN-2026-014) tem as 92 atividades do app: 47 publicadas com o
    realizado aprovado, 1 publicada com o realizado pendente (o pedido de alteração
    aplicado pela ISSUE-053 reabre o item, como o app faria), 8 validadas com o realizado
    aprovado, 11 validadas aguardando o fiscal e 25 em elaboração. Na semana S.34/2026, a
    aderência fecha em 66,19% (PPC médio de 65,86%, 4 aguardando o fiscal e 2 na faixa
    baixa); a próxima ação de cada perfil segue a fila do app (validar → lançar → aprovar
    → publicar → ver).
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    states = {
        (row.situation, row.approval): row.total
        for row in db_session.execute(
            select(Activity.situation, Activity.approval, func.count().label("total"))
            .where(Activity.project_id == project.id)
            .group_by(Activity.situation, Activity.approval)
        )
    }
    assert states == {
        ("publicada", "aprovado"): 47,
        ("publicada", "pendente"): 1,
        ("validada", "aprovado"): 8,
        ("validada", "pendente"): 11,
        ("em_elaboracao", "pendente"): 25,
    }

    accesses = {access.email: access for access in configuracoes.list_active_access(db_session)}
    planner = _user_of(accesses["planejador@timenow.com.br"])
    fiscal = _user_of(accesses["fiscal@timenow.com.br"])
    supplier = _user_of(accesses["programacao@mroscoe.com.br"])
    scope = Scope(project_id=project.id, source="url")
    caller = programacao_semanal.Caller(user=planner, scope=scope, now=calendario.now())

    def views_of(week: str) -> dict[str, ActivityView]:
        return {
            view.unique_id: view
            for view in programacao_semanal.list_activities(db_session, caller=caller, week=week)
        }

    def action(view: ActivityView, user) -> str:
        return permissions.next_action(
            user,
            project.id,
            situation=view.situation,
            approval=view.approval,
            has_done=view.figures.has_done,
        )

    week_34 = views_of("S.34/2026")
    summary = programacao_semanal.week_summary(list(week_34.values()))
    assert (summary.total, summary.adherence, summary.mean_ppc) == (12, 66.19, 65.86)
    assert (summary.awaiting_inspector, summary.low_band) == (4, 2)

    assert action(week_34["PRD-ELT-015"], planner) == "publicar"
    assert action(week_34["CAL-ISO-018"], planner) == "ver"
    assert action(week_34["CAL-ISO-018"], fiscal) == "aprovar"
    assert action(week_34["PS1-CON-021"], supplier) == "lancar"
    assert action(views_of("S.35/2026")["SUB-TRF-010"], planner) == "validar"
    assert action(views_of("S.30/2026")["PRD-ELT-015"], planner) == "ver"


def test_oraculo_da_governanca_da_programacao_semanal(db_session: Session) -> None:
    """O oráculo da ISSUE-053: o painel por empresa/semana, a fila e a trilha, com a carga.

    Numa sexta da semana S.35/2026 (28/08/2026, 10:00 de São Paulo), com a janela de
    M. Roscoe aberta, o projeto TN-2026-014 tem 26 linhas de controle (92 atividades
    em 3 contratadas), 1 janela aberta e 17 pendências de aprovação com realizado. A
    fila tem os três pedidos da carga: PS2-PIN-011 pendente, CAL-TUB-012 aplicado
    (o realizado aprovado volta a pendente) e SUB-TRF-010 recusado. A trilha é a
    auditoria única filtrada pelas entidades do módulo, sem as linhas de dia.
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    accesses = {access.email: access for access in configuracoes.list_active_access(db_session)}
    planner = _user_of(accesses["planejador@timenow.com.br"])
    supplier = _user_of(accesses["programacao@mroscoe.com.br"])
    scope = Scope(project_id=project.id, source="url")
    friday = datetime(2026, 8, 28, 13, 0, tzinfo=UTC)
    caller = programacao_semanal.Caller(user=planner, scope=scope, now=friday)

    panel = programacao_semanal.governance_panel(db_session, caller=caller)
    assert (panel.reference_week, panel.reference_period) == ("S.35/2026", "24/08 a 30/08/2026")
    assert (len(panel.lines), panel.active_companies, panel.open_windows) == (26, 3, 1)
    counts = panel.situations
    assert (
        counts.total,
        counts.draft,
        counts.validated,
        counts.published,
        counts.approved,
        counts.pending,
        counts.no_done,
    ) == (92, 25, 19, 48, 55, 17, 20)

    lines = {(line.company, line.week): line for line in panel.lines}
    assert (panel.lines[0].company, panel.lines[0].week) == ("M. Roscoe", "S.39/2026")
    roscoe_34 = lines[("M. Roscoe", "S.34/2026")]
    assert (
        roscoe_34.total,
        roscoe_34.validated,
        roscoe_34.published,
        roscoe_34.pending,
        roscoe_34.adherence,
        roscoe_34.inspector,
    ) == (5, 5, 0, 1, 72.79, "Marcos Duarte")
    elmec_31 = lines[("Elmec Montagens", "S.31/2026")]
    assert (
        elmec_31.total,
        elmec_31.published,
        elmec_31.pending,
        elmec_31.adherence,
        elmec_31.updated_at_text,
    ) == (3, 3, 1, 41.88, "17/08/2026 08:30")
    assert lines[("Bremmer", "S.32/2026")].updated_at_text == "08/08/2026 07:15"

    windows = {window.company: window for window in panel.windows}
    assert windows["M. Roscoe"].is_open
    assert (
        windows["M. Roscoe"].released_count,
        windows["M. Roscoe"].weekday_label,
        windows["M. Roscoe"].opens,
        windows["M. Roscoe"].closes,
    ) == (3, "Sexta-feira", "00:01", "23:59")
    assert not windows["Bremmer"].is_open
    assert not windows["Elmec Montagens"].is_open

    queue = programacao_semanal.request_queue(db_session, caller=caller)
    assert queue.total_pending == 1
    assert [view.unique_id for view in queue.pending] == ["PS2-PIN-011"]
    assert [(view.unique_id, view.situation) for view in queue.resolved] == [
        ("CAL-TUB-012", "aplicado"),
        ("SUB-TRF-010", "rejeitado"),
    ]
    assert queue.resolved[0].answer == "Liberado: ajuste o previsto e lance o realizado corrigido."

    supplier_caller = programacao_semanal.Caller(user=supplier, scope=scope, now=friday)
    supplier_queue = programacao_semanal.request_queue(db_session, caller=supplier_caller)
    assert [view.unique_id for view in supplier_queue.pending] == ["PS2-PIN-011"]
    assert supplier_queue.resolved == []
    supplier_panel = programacao_semanal.governance_panel(db_session, caller=supplier_caller)
    assert {line.company for line in supplier_panel.lines} == {"M. Roscoe"}
    assert supplier_panel.situations.total == 37
    assert not supplier_panel.can_view_trail

    applied = db_session.scalars(
        select(Activity)
        .where(Activity.unique_id == "CAL-TUB-012")
        .where(Activity.week == "S.31/2026")
    ).one()
    assert applied.approval == "pendente"
    assert "Pedido de alteração liberado para alteração" in (applied.timenow_comments or "")

    pedido_entries = db_session.scalar(
        select(func.count())
        .select_from(AuditEntry)
        .where(AuditEntry.entity == "programacao_pedido_alteracao")
    )
    assert pedido_entries == 5
    trail = programacao_semanal.governance_trail(db_session, caller=caller, limit=200)
    labels = Counter(event.label for event in trail)
    assert labels == {
        "Atividade criada": 92,
        "Realizado reaberto": 1,
        "Pedido de alteração aberto": 3,
        "Pedido de alteração aplicado": 1,
        "Pedido de alteração recusado": 2,
        "Janela de programação criada": 3,
        "Configuração da programação gravada": 1,
    }
    with pytest.raises(AccessDeniedError):
        programacao_semanal.governance_trail(db_session, caller=supplier_caller)


def test_oraculo_do_dashboard_da_programacao_semanal(db_session: Session) -> None:
    """O oráculo da ISSUE-056: os indicadores do dashboard, com a carga.

    Na semana S.34/2026 do projeto TN-2026-014, a aderência fecha em 66,19% (PPC
    médio de 65,86%), com 3 contratadas e 6 frentes; o ranking vai de Elmec
    Montagens (59,82%) a M. Roscoe (72,79%); a faixa de PPC tem 10 médias e 2
    baixas; os dois gargalos são CAL-TUB-012 e CAL-ISO-018; a evolução tem as três
    contratadas, com o par (previsto, realizado) de cada semana, e o fornecedor
    M. Roscoe vê só a própria empresa. O dashboard lê a mesma ``week_summary`` da
    matriz (o oráculo da ISSUE-052) e o mesmo horizonte da curva (a ISSUE-055).
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    accesses = {access.email: access for access in configuracoes.list_active_access(db_session)}
    planner = _user_of(accesses["planejador@timenow.com.br"])
    supplier = _user_of(accesses["programacao@mroscoe.com.br"])
    scope = Scope(project_id=project.id, source="url")
    friday = datetime(2026, 8, 28, 13, 0, tzinfo=UTC)
    caller = programacao_semanal.Caller(user=planner, scope=scope, now=friday)

    data = programacao_semanal.dashboard_data(db_session, caller=caller, week="S.34/2026")
    summary = data.summary
    assert (summary.total, summary.adherence, summary.mean_ppc) == (12, 66.19, 65.86)
    assert (data.companies, data.locations) == (3, 6)

    assert [
        (line.label, line.activities, line.adherence, line.pending) for line in data.by_company
    ] == [
        ("Elmec Montagens", 3, 59.82, 2),
        ("Bremmer", 4, 62.47, 1),
        ("M. Roscoe", 5, 72.79, 1),
    ]
    assert [segment.value for segment in data.status[1].segments] == [8, 4, 0]
    assert [segment.value for segment in data.status[2].segments] == [0, 10, 2]

    assert [(item.identity, item.ppc) for item in data.bottlenecks] == [
        ("CAL-TUB-012", 55.87),
        ("CAL-ISO-018", 59.22),
    ]

    assert (data.shifts[0].planned, data.shifts[0].day_shift, data.shifts[0].night_shift) == (
        2006.2,
        1187.8,
        202.7,
    )
    assert data.shifts[-1].night_shift == 0.0

    assert [row.label for row in data.heatmap.rows] == [
        "Base Caldeira",
        "Potato Storage 1",
        "Potato Storage 2",
        "Potato Storage 3",
        "Prédio de Produção",
        "Subestação",
    ]
    assert data.heatmap.rows[0].cells[0].percent == 59.4
    assert data.heatmap.rows[0].cells[-1].percent == 14.8

    assert data.curve[-1].planned_accumulated == pytest.approx(100.0, abs=0.02)
    assert data.curve[-1].done_accumulated == 55.0
    assert data.evolution.series == ("Bremmer", "Elmec Montagens", "M. Roscoe")
    roscoe_30 = data.evolution.points[0].totals["M. Roscoe"]
    assert (roscoe_30.planned, roscoe_30.done) == (4347.7, 2235.4)

    supplier_caller = programacao_semanal.Caller(user=supplier, scope=scope, now=friday)
    supplier_data = programacao_semanal.dashboard_data(
        db_session, caller=supplier_caller, week="S.34/2026"
    )
    assert supplier_data.summary.total == 5
    assert supplier_data.evolution.series == ("M. Roscoe",)


def test_oraculo_do_cadastro_de_fornecedores_com_a_carga(db_session: Session) -> None:
    """O oráculo da ISSUE-057: as 17 qualificações do mock, com a data deslocada.

    Na âncora, as 17 qualificações do protótipo entram com as 22 categorias e os 62 documentos
    convertidos: 14 Qualificado, 1 Em qualificação, 1 Restrito e 1 "Qualificado com restrição"
    (a quinta situação do mock, que o protótipo exibe crua). Só a certidão trabalhista da Zeta
    Civil (15/09/2026) está vencida e só a validade da Zeta Civil vence em até 90 dias; o
    histórico é um: a Gama Válvulas passou de Qualificado a Restrito em 12/09/2026, por Paulo
    Serra. A Gerenciadora não é fornecedor e fica fora do cadastro; as três empresas da
    Programação Semanal ficam "Sem qualificação", como qualquer empresa do cadastro. O desempenho
    é do escopo (os contratos do Financeiro): a Alfa Montagens tem o CT-2026-014, R$ 4,8 milhões
    contratados e a avaliação de set/26 valendo 63, classe C; a Tau Construções só tem contratos
    dos projetos 2 e 3 e, no projeto 1, o valor contratado é zero — o cadastro é global, mas o
    desempenho segue o projeto aberto.
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, Supplier) == 17, "as qualificações do mock"
    assert _count(db_session, SupplierCategory) == 22
    assert _count(db_session, SupplierDocument) == 62
    assert _count(db_session, SupplierHistory) == 1

    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    user = _user_of(admin)
    listagem = suprimentos.list_suppliers(
        db_session,
        user=user,
        scope=Scope(project_id=None, source="padrao"),
        filters=suprimentos_validation.SupplierFilters(),
        reference_date=DEMO_ANCHOR,
    )

    resumo = listagem.summary
    assert (resumo.companies, resumo.registered, resumo.unregistered) == (20, 17, 3), (
        "as 21 empresas menos a Gerenciadora; as três da Programação Semanal sem qualificação"
    )
    assert (
        resumo.qualified,
        resumo.in_qualification,
        resumo.restricted_or_blocked,
        resumo.blocked,
    ) == (14, 1, 1, 0)
    assert (resumo.expired_documents, resumo.validity_due) == (1, 1)

    por_nome = {linha.name: linha for linha in listagem.lines}
    assert "Timenow Gerenciadora" not in por_nome, "a Gerenciadora não é fornecedor"
    assert sorted(linha.name for linha in listagem.lines if not linha.registered) == [
        "Bremmer",
        "Elmec Montagens",
        "M. Roscoe",
    ]
    assert all(
        linha.situation == "Sem qualificação" for linha in listagem.lines if not linha.registered
    )

    gama = por_nome["Gama Válvulas"]
    assert gama.situation == "Restrito"
    assert gama.categories == ("Válvulas",)
    historico = [
        (row.date, row.from_situation, row.to_situation, row.author) for row in gama.history
    ]
    assert historico == [(date(2026, 9, 12), "Qualificado", "Restrito", "Paulo Serra")]

    zeta = por_nome["Zeta Civil"]
    assert not zeta.documents_up_to_date
    assert [document.name for document in zeta.expired_documents] == [
        "Certidão negativa de débitos trabalhistas"
    ]
    assert zeta.qualification_expiring and not zeta.qualification_expired

    tau = por_nome["Tau Construções"]
    assert tau.situation == "Qualificado com restrição", "a quinta situação do mock, crua"
    assert tau.contracted_cents == 275_000_000, "CT-2026-022 + CT-2026-027 na carteira"

    alfa = por_nome["Alfa Montagens"]
    assert alfa.contracted_cents == 480_000_000, "o CT-2026-014"
    assert alfa.last_evaluation is not None
    assert (alfa.last_evaluation.score, alfa.last_evaluation.score_class) == (63, "C")
    assert alfa.mean_score == Decimal("67.0")

    project = db_session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    tau_no_projeto = suprimentos.find_supplier(
        db_session,
        user=user,
        scope=Scope(project_id=project.id, source="url"),
        company_id=tau.company_id,
        reference_date=DEMO_ANCHOR,
    )
    assert tau_no_projeto is not None
    assert tau_no_projeto.contracted_cents == 0, "o desempenho segue o projeto aberto"


def test_oraculo_do_plano_de_compras_com_a_carga(db_session: Session) -> None:
    """O oráculo da ISSUE-058: os 28 pacotes do mock com as três camadas dos sete marcos.

    Na âncora, os 28 pacotes do protótipo entram assim: 14 do projeto 1, 8 do projeto 2 e 6 do
    projeto 3; 196 marcos (28 vezes 7), todos com a linha de base, 17 com previsão e 172 com
    data real; 7 pacotes LLI (4 deles com o gate aprovado) e nenhum emergencial. A etapa sai
    das datas reais dos marcos: 23 pacotes chegaram a Pedido/contrato emitido, 2 a Propostas
    recebidas, 1 a Equalização técnica, 1 a Requisição e 1 ainda está Planejado (TR-PC-06, o
    único com a LB editável). O vínculo à EAC reproduz o mock: 20 pacotes em itens de nível 3 e
    8 nos itens de nível 2 que o protótipo já usava — só um pacote novo exige o nível 3. A
    adjudicação atrasada são 4 e o ``plano.entrega`` do mock não vira marco (o modelo o ignora).
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, PurchasePackage) == 28, "os pacotes do mock"
    assert _count(db_session, PackageMilestone) == 196, "28 pacotes vezes 7 marcos"
    projetos = {project.code: project.id for project in db_session.scalars(select(Project))}
    assert _pacotes_no(db_session, projetos["TN-2026-014"]) == 14
    assert _pacotes_no(db_session, projetos["TN-2026-021"]) == 8
    assert _pacotes_no(db_session, projetos["TN-2026-027"]) == 6

    marcos = db_session.scalars(select(PackageMilestone)).all()
    assert sum(1 for row in marcos if row.plan_date is not None) == 196
    assert sum(1 for row in marcos if row.forecast_date is not None) == 17
    assert sum(1 for row in marcos if row.real_date is not None) == 172

    assert _count_where(db_session, PurchasePackage.lli.is_(True)) == 7
    assert _count_where(db_session, PurchasePackage.emergency.is_(True)) == 0
    assert _count_where(db_session, PurchasePackage.gate_lli_date.is_not(None)) == 4
    com_gate = db_session.scalars(
        select(PurchasePackage).where(PurchasePackage.gate_lli_reference.is_not(None))
    ).all()
    assert all(row.gate_lli_reference and "LLI" in row.gate_lli_reference for row in com_gate)

    nivel3 = db_session.scalar(
        select(func.count())
        .select_from(PurchasePackage)
        .join(EacItem, EacItem.id == PurchasePackage.eac_item_id)
        .where(EacItem.level == 3)
    )
    assert nivel3 == 20, "20 pacotes em itens de custo e 8 nos itens de nível 2 do mock"

    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    listagem = suprimentos.list_packages(
        db_session,
        user=_user_of(admin),
        scope=Scope(project_id=None, source="padrao"),
        filters=suprimentos_validation.PackageFilters(),
        reference_date=DEMO_ANCHOR,
    )
    resumo = listagem.summary
    assert resumo.packages == 28
    assert resumo.estimated_cents == 6_447_000_000
    assert (resumo.with_baseline, resumo.forecast_until_reference, resumo.overdue) == (28, 26, 4)
    assert (resumo.lli, resumo.lli_critical) == (7, 0)
    assert resumo.adjudicated is None and resumo.saving_cents is None
    etapas = Counter(line.stage for line in listagem.lines)
    assert etapas == {
        "Pedido/contrato emitido": 23,
        "Propostas recebidas": 2,
        "Equalização técnica": 1,
        "Requisição": 1,
        "Planejado": 1,
    }
    congelados = sum(1 for line in listagem.lines if line.frozen)
    assert congelados == 27, "só o TR-PC-06 ainda tem a LB editável"

    primeiro = next(line for line in listagem.lines if line.code == "PC-01")
    assert primeiro.project_label.startswith("TN-2026-014")
    assert primeiro.stage == "Pedido/contrato emitido"
    assert primeiro.slack_days == 4, "ROS 12/01/2026 menos o pedido planejado de 08/01/2026"
    assert primeiro.eac_code == "1.2"
    assert primeiro.buyer == "Diego Matos"


def test_oraculo_dos_processos_de_compra_com_a_carga(db_session: Session) -> None:
    """O oráculo da ISSUE-059: os quatro processos do mock, com o PC-14 em equalização comercial.

    Na âncora, os quatro processos do protótipo entram com 16 convidados, 13 propostas e 1
    negociação; os nomes sem cadastro (Sistemas Nu, Xi Controles, Ômicron Automação, Épsilon
    Instrumentos, Chi Ventiladores, Psi Fluidos e Ômega Drives) ficam no `nome`. O PC-14
    (RFQ-2026-014) está em **Equalização comercial**, a etapa da última linha do histórico — a
    mesma da verificação da issue —, com 4 propostas, 3 aprovadas e a melhor a Teta Automação
    (nota final 95,2, sem negociação); a Sistemas Nu, reprovada, fica fora do ranking. O PC-12
    (RFQ-2026-012) chegou ao pedido com o ciclo de 67 dias e a negociação de R$ 300.000,00; o
    CB-PC-05 está em Propostas recebidas e o TR-PC-04 em Equalização técnica. A lista padrão
    mostra 5 processos (o filtro de andamento corta os 23 no pedido) e o filtro "todos", 28.
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, PurchaseProcess) == 4, "os processos do mock"
    assert _count(db_session, ProcessInvitee) == 16
    assert _count(db_session, ProcessProposal) == 13
    assert _count(db_session, ProcessNegotiation) == 1
    historico = db_session.scalar(
        select(func.count())
        .select_from(AuditEntry)
        .where(AuditEntry.entity == suprimentos.PROCESS_HISTORY_ENTITY)
    )
    assert historico == 14, "as linhas de histórico dos quatro processos"

    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    user = _user_of(admin)
    scope = Scope(project_id=None, source="padrao")
    listagem = suprimentos.list_processes(
        db_session,
        user=user,
        scope=scope,
        filters=suprimentos_validation.ProcessFilters(),
        reference_date=DEMO_ANCHOR,
    )

    assert listagem.total == 5, "o filtro padrão corta os processos no pedido"
    assert listagem.summary.in_progress == 5
    assert listagem.summary.awaiting_approval == 0
    assert listagem.summary.single_supplier_count == 0
    assert listagem.summary.mean_valid_proposals == Decimal("2.3")
    assert listagem.summary.cycle_mean_days is not None, "os pacotes no pedido têm ciclo"

    completa = suprimentos.list_processes(
        db_session,
        user=user,
        scope=scope,
        filters=suprimentos_validation.ProcessFilters(situation=""),
        reference_date=DEMO_ANCHOR,
    )
    assert completa.total == 28

    por_codigo = {linha.code: linha for linha in completa.lines}
    pc14 = por_codigo["PC-14"]
    assert (pc14.stage, pc14.stage_index) == ("Equalização comercial", 5), (
        "o PC-14 fica pronto para a equalização comercial, como a issue cita"
    )
    assert pc14.number == "RFQ-2026-014"
    assert pc14.received_count == 4
    assert pc14.approved_count == 3
    assert pc14.minimum == 3 and pc14.single_supplier is False
    assert pc14.invitees[0].name == "Teta Automação"
    assert pc14.best is not None
    assert pc14.best.name == "Teta Automação"
    assert (pc14.best.commercial_score, pc14.best.final_score, pc14.best.rank) == (
        Decimal("100.0"),
        Decimal("95.2"),
        1,
    )
    assert pc14.best.qualification == "Em qualificação"
    reprovada = next(proposta for proposta in pc14.proposals if proposta.name == "Sistemas Nu")
    assert reprovada.rank is None and reprovada.technically_approved is False
    assert pc14.approval_band == "Gerente de suprimentos"
    assert [passo.situation for passo in pc14.steps][:5] == [
        "concluido",
        "concluido",
        "concluido",
        "concluido",
        "andamento",
    ]

    pc12 = por_codigo["PC-12"]
    assert pc12.stage == "Pedido/contrato emitido"
    assert pc12.cycle_days == 67, "requisição 06/04/2026 ao pedido 12/06/2026"
    assert pc12.negotiations[0].value_cents == 30_000_000
    assert pc12.best is not None and pc12.best.negotiated_cents == 30_000_000
    assert pc12.best.final_score == Decimal("93.6")
    processo = db_session.scalars(
        select(PurchaseProcess).where(PurchaseProcess.package_id == pc12.package_id)
    ).one()
    assert processo.recommendation_value_cents == 30_000_000
    assert processo.approval_band == "Gerente de suprimentos"

    assert por_codigo["CB-PC-05"].stage == "Propostas recebidas"
    assert por_codigo["TR-PC-04"].stage == "Equalização técnica"


def test_oraculo_dos_pedidos_de_compra_com_a_carga(db_session: Session) -> None:
    """O oráculo da ISSUE-060: os 14 pedidos do mock com os seis marcos de fabricação.

    Na âncora, os pedidos do protótipo entram assim: 14 pedidos (10 do projeto 1, 3 do projeto 2
    e 1 do projeto 3) com 84 marcos (14 vezes 6), todos com a LB contratual e a previsão; 3 já
    entregues (PED-2026-0003, 0006 e 0008) e 3 nascidos com folga negativa (0001, 0002 e 0004).
    O pedido da PC-12 (PED-2026-0010) fica ligado ao pacote e à Teta Automação, com os R$ 300.000
    negociados; o ``recebimento`` do mock não vira tabela (ISSUE-061) e nenhuma ação nova de
    diligenciamento é criada pela carga (a do PED-2026-0011 já vem do mock da Central).
    """
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert _count(db_session, PurchaseOrder) == 14, "os pedidos do mock"
    assert _count(db_session, PurchaseOrderMilestone) == 84, "14 pedidos vezes 6 marcos"
    marcos = db_session.scalars(select(PurchaseOrderMilestone)).all()
    assert all(row.baseline_date is not None for row in marcos)
    assert all(row.forecast_date is not None for row in marcos)
    assert sum(1 for row in marcos if row.real_date is not None) == 44, (
        "os marcos realizados do mock"
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.delivery.is_not(None))
        )
        == 3
    ), "três pedidos já recebidos no mock"

    pc12 = db_session.scalars(
        select(PurchaseOrder)
        .join(PurchasePackage, PurchasePackage.id == PurchaseOrder.package_id)
        .where(PurchasePackage.code == "PC-12")
    ).one()
    assert pc12.number == "PED-2026-0010"
    assert pc12.value_cents == 30_000_000, "o valor negociado da PC-12"
    assert pc12.lli is False
    assert pc12.emission == date(2026, 6, 12)
    assert pc12.contractual_date == date(2026, 11, 5)
    assert pc12.forecast == date(2026, 11, 5)
    assert pc12.ros == date(2026, 11, 20)
    assert configuracoes.list_company_names(db_session)[pc12.company_id] == "Teta Automação"
    marcos_do_pedido = db_session.scalars(
        select(PurchaseOrderMilestone)
        .where(PurchaseOrderMilestone.order_id == pc12.id)
        .order_by(PurchaseOrderMilestone.position)
    ).all()
    assert [row.name for row in marcos_do_pedido] == [
        "Aprovação de documentos",
        "Matéria-prima",
        "Fabricação",
        "Inspeção / FAT",
        "Embarque",
        "Entrega",
    ]
    assert marcos_do_pedido[-1].baseline_date == date(2026, 11, 5)

    admin = next(
        access
        for access in configuracoes.list_active_access(db_session)
        if access.general_profile == "Admin"
    )
    scope = Scope(project_id=None, source="padrao")
    linha = suprimentos.find_process(
        db_session,
        user=_user_of(admin),
        scope=scope,
        package_id=pc12.package_id,
        reference_date=DEMO_ANCHOR,
    )
    assert linha is not None
    assert linha.order_number == "PED-2026-0010", "a ficha do processo mostra o pedido emitido"
    assert linha.contract_number is None

    proximo_pedido = numbering.next_series_number(
        list(db_session.scalars(select(PurchaseOrder.number))),
        prefix="PED",
        year=2026,
        digits=4,
    )
    assert proximo_pedido == "PED-2026-0015", (
        "o README cita 0012; a divergência está registrada (mocks completos)"
    )
    proximo_contrato = numbering.next_series_number(
        list(db_session.scalars(select(Contract.number))), prefix="CT", year=2026
    )
    assert proximo_contrato == "CT-2026-029", (
        "o README cita 015; a divergência está registrada (mocks completos)"
    )


def _pacotes_no(db_session: Session, project_id: int) -> int:
    return (
        db_session.scalar(
            select(func.count())
            .select_from(PurchasePackage)
            .where(PurchasePackage.project_id == project_id)
        )
        or 0
    )


def _count_where(db_session: Session, *conditions: Any) -> int:
    return (
        db_session.scalar(select(func.count()).select_from(PurchasePackage).where(*conditions)) or 0
    )


def test_carga_cobre_perfis_papeis_e_vinculos(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    profiles = set(db_session.scalars(select(Collaborator.general_profile)).all())
    assert profiles == {"Admin", "Gestor", "Membro", "Visualizador"}

    bonds = set(db_session.scalars(select(Collaborator.bond)).all())
    assert bonds == {"Timenow", "Fornecedor", "Cliente"}

    roles = set(db_session.scalars(select(CollaboratorScheduleRole.role)).all())
    assert roles == {"Planejador", "Fiscal", "Encarregado", "Fornecedor"}

    for project in db_session.scalars(select(Project)).all():
        project_roles = set(
            db_session.scalars(
                select(CollaboratorScheduleRole.role).where(
                    CollaboratorScheduleRole.project_id == project.id
                )
            ).all()
        )
        assert project_roles == {"Planejador", "Fiscal", "Encarregado", "Fornecedor"}


def test_carga_grava_a_trilha_e_a_marca_de_execucao(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    run = db_session.scalars(select(SeedRun).where(SeedRun.name == "plataforma")).one()
    assert run.name == "plataforma"
    entities = set(db_session.scalars(select(AuditEntry.entity)).all())
    assert {"projeto", "empresa", "pessoa", "colaborador", "sistema"} <= entities


def test_ancora_dos_dados_convertidos_bate_com_o_prototipo() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert data["ancora"] == DEMO_ANCHOR.isoformat()
    assert [project["codigo"] for project in data["projetos"]] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ]


def test_base_de_producao_nasce_vazia_com_o_primeiro_admin(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)
    monkeypatch.setenv(config.ADMIN_EMAIL_VARIABLE, "primeiro.admin@empresa.exemplo")

    run_for_mode(db_session, reference_date=DEMO_ANCHOR)
    counts = _counts(db_session)

    assert run_for_mode(db_session, reference_date=DEMO_ANCHOR) == []
    assert _counts(db_session) == counts
    assert counts["clientes"] == 0
    assert counts["projetos"] == 0
    assert counts["empresas"] == 0
    assert counts["pessoas"] == 1
    assert counts["colaboradores"] == 1
    assert counts["parametros"] == PARAMETER_GROUPS
    assert _count(db_session, SeedRun) == 0

    collaborator = db_session.scalars(select(Collaborator)).one()
    assert collaborator.general_profile == "Admin"
    assert collaborator.bond == "Timenow"
    person = db_session.scalars(select(Person)).one()
    assert person.email == "primeiro.admin@empresa.exemplo"


def test_producao_sem_o_email_do_admin_falha_alto(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)
    monkeypatch.delenv(config.ADMIN_EMAIL_VARIABLE, raising=False)

    with pytest.raises(ProductionStartError):
        run_for_mode(db_session, reference_date=DEMO_ANCHOR)


def test_email_invalido_do_admin_falha_com_mensagem(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)
    monkeypatch.setenv(config.ADMIN_EMAIL_VARIABLE, "sem-arroba")

    with pytest.raises(InvalidDataError):
        run_for_mode(db_session, reference_date=DEMO_ANCHOR)


def test_modo_desconhecido_falha_alto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.APP_MODE_VARIABLE, "homologacao")

    with pytest.raises(config.InvalidApplicationModeError):
        config.app_mode()


def test_carga_de_demonstracao_com_o_modo_padrao(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(config.APP_MODE_VARIABLE, raising=False)

    written = run_for_mode(db_session, reference_date=DEMO_ANCHOR)

    assert sorted(written) == sorted(PARTS)
    assert _count(db_session, Project) == PROJECTS


def test_pesos_da_ponderacao_entram_na_versao_do_portfolio(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    weights = db_session.scalars(select(PortfolioWeight)).all()
    assert len(weights) == PROJECTS * 2
    by_project = {
        project.code: {
            weight.criterion: weight.grade for weight in weights if weight.project_id == project.id
        }
        for project in db_session.scalars(select(Project)).all()
    }
    assert by_project["TN-2026-014"] == {"estrategico": 5, "complexidade": 5}
    assert by_project["TN-2026-021"] == {"estrategico": 4, "complexidade": 4}
    assert by_project["TN-2026-027"] == {"estrategico": 3, "complexidade": 2}
