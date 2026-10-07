"""Carga de demonstração deslocada e base de produção vazia (ISSUE-008).

O deslocamento de uma data conhecida, a idempotência da carga, a cobertura de
perfis, papéis e vínculos, e o preparo de produção com o primeiro Admin.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

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
from src.core import config
from src.core.auth import _user_of
from src.core.errors import InvalidDataError
from src.core.models import AuditEntry, Client, SeedRun
from src.core.scope import Scope
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
)
from src.modulos.riscos.models import Risk

# A demonstração inteira: a plataforma e a parte de cada módulo, na ordem em que entram.
PARTS = [
    "plataforma",
    "central_acoes",
    "financeiro",
    "financeiro-custos",
    "governanca",
    "governanca-licoes",
    "governanca-eac",
    "financeiro-contratos",
    "financeiro-contratos-avaliacoes",
    "hse",
    "planejamento",
    "planejamento-eap",
    "planejamento-curva",
    "programacao_semanal",
    "riscos",
    "financeiro-contratos-fluxos",
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
