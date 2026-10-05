"""Carga de demonstração deslocada e base de produção vazia (ISSUE-008).

O deslocamento de uma data conhecida, a idempotência da carga, a cobertura de
perfis, papéis e vínculos, e o preparo de produção com o primeiro Admin.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.carga import (
    DEMO_ANCHOR,
    ProductionStartError,
    run_demonstration,
    run_for_mode,
)
from src.carga.plataforma import DATA_PATH
from src.core import config
from src.core.errors import InvalidDataError
from src.core.models import AuditEntry, Client, SeedRun
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

MOCK_PEOPLE = 18
DEMO_PEOPLE = MOCK_PEOPLE + 1
PROJECTS = 3
COMPANIES = 18
SYSTEMS = 9
LOCATIONS = 9
DISCIPLINES = 12
UNITS = 11
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
    assert first == ["plataforma"]

    second = run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    assert second == []
    assert _counts(db_session) == counts
    assert _count(db_session, SeedRun) == 1


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

    run = db_session.scalars(select(SeedRun)).one()
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

    assert written == ["plataforma"]
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
