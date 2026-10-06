"""O teste-oráculo da plataforma: demonstração em 25/09/2026, números do protótipo.

Nesta issue o oráculo afirma só o que já existe (os projetos do portfólio, os
cadastros, os colaboradores e os parâmetros iniciais); cada issue de módulo
acrescenta as suas afirmações no próprio pacote de testes, via
``register_check``, e este teste as roda todas.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga.registro import DEMO_ANCHOR
from src.modulos.configuracoes.models import (
    Collaborator,
    CollaboratorScheduleRole,
    Company,
    Discipline,
    Location,
    Person,
    PortfolioWeight,
    Project,
    System,
    Unit,
)
from src.modulos.configuracoes.service import current_versions
from tests.oraculo import (
    OracleContext,
    harness,
    register_check,
    registered_checks,
    test_oraculo_6wla,  # noqa: F401 - registra as afirmações do 6WLA
)

MOCK_PEOPLE_EMAILS = (
    "leonardo.gomes@exemplo.com",
    "joao.gestor@exemplo.com",
    "maria.souza@exemplo.com",
    "marina.alves@exemplo.com",
    "carlos.nunes@exemplo.com",
    "renata.lima@exemplo.com",
    "diego.matos@exemplo.com",
    "ana.prado@exemplo.com",
    "paulo.serra@exemplo.com",
    "beatriz.rocha@exemplo.com",
    "fabio.teixeira@exemplo.com",
    "rafael.costa@exemplo.com",
    "juliana.reis@exemplo.com",
    "paula.menezes@exemplo.com",
    "ricardo.tavares@exemplo.com",
    "sonia.ribeiro@exemplo.com",
    "hugo.fontes@exemplo.com",
    "otavio.lins@exemplo.com",
)


def _afirmar_projetos_do_portfolio(context: OracleContext) -> None:
    projects = context.session.scalars(select(Project).order_by(Project.code)).all()
    assert [project.code for project in projects] == [
        "TN-2026-014",
        "TN-2026-021",
        "TN-2026-027",
    ], "codigos dos projetos do portfolio"
    assert [project.budget_cents for project in projects] == [
        4460000000,
        1820000000,
        740000000,
    ], "orcamentos em centavos"
    first = projects[0]
    assert first.name == "Construção de uma nova fábrica"
    assert str(first.start_date) == "2026-01-05"
    assert str(first.expected_end_date) == "2027-03-31"


def _project_by_code(context: OracleContext, code: str) -> Project:
    return context.session.scalars(select(Project).where(Project.code == code)).one()


def _afirmar_cadastros_de_apoio(context: OracleContext) -> None:
    session = context.session
    first = _project_by_code(context, "TN-2026-014")
    systems = session.scalars(select(System)).all()
    assert len(systems) == 9, "sistemas convertidos do prototipo"
    assert {system.code for system in systems if system.project_id == first.id} == {
        "210",
        "310",
        "420",
        "510",
    }
    assert len(session.scalars(select(Location)).all()) == 15, (
        "9 locais do mock-base + 6 da demonstracao da Programacao Semanal (ISSUE-051)"
    )
    assert len(session.scalars(select(Discipline)).all()) == 12, "disciplinas"
    assert len(session.scalars(select(Unit)).all()) == 14, (
        "11 unidades do mock-base + kg, und e h da demonstracao da Programacao Semanal (ISSUE-051)"
    )
    assert len(session.scalars(select(Company)).all()) == 21, (
        "18 empresas do mock-base + 3 da demonstracao da Programacao Semanal (ISSUE-051)"
    )


def _afirmar_pessoas_e_colaboradores(context: OracleContext) -> None:
    session = context.session
    emails = set(session.scalars(select(Person.email)).all())
    assert set(MOCK_PEOPLE_EMAILS) <= emails, "pessoas do mock-base"
    assert "visualizador@cliente.demo" in emails, "pessoa de demonstracao do vinculo Cliente"

    profiles = set(session.scalars(select(Collaborator.general_profile)).all())
    assert profiles == {"Admin", "Gestor", "Membro", "Visualizador"}, "perfis gerais"
    bonds = set(session.scalars(select(Collaborator.bond)).all())
    assert bonds == {"Timenow", "Fornecedor", "Cliente"}, "tres vinculos"
    roles = set(session.scalars(select(CollaboratorScheduleRole.role)).all())
    assert roles == {"Planejador", "Fiscal", "Encarregado", "Fornecedor"}, "papeis da PS"
    for code in ("TN-2026-014", "TN-2026-021", "TN-2026-027"):
        project = _project_by_code(context, code)
        project_roles = set(
            session.scalars(
                select(CollaboratorScheduleRole.role).where(
                    CollaboratorScheduleRole.project_id == project.id
                )
            ).all()
        )
        assert project_roles == {
            "Planejador",
            "Fiscal",
            "Encarregado",
            "Fornecedor",
        }, f"papeis do projeto {code}"


def _afirmar_parametros_e_ponderacao(context: OracleContext) -> None:
    versions = current_versions(context.session, reference_date=DEMO_ANCHOR)
    assert len(versions) == 14, "14 grupos de parametros na versao 1"
    assert all(version.version == 1 for version in versions.values())
    weights = context.session.scalars(select(PortfolioWeight)).all()
    projects = {
        project.id: project.code for project in context.session.scalars(select(Project)).all()
    }
    by_project: dict[str, dict[str, int]] = {}
    for weight in weights:
        by_project.setdefault(projects[weight.project_id], {})[weight.criterion] = weight.grade
    assert by_project["TN-2026-014"] == {"estrategico": 5, "complexidade": 5}
    assert by_project["TN-2026-021"] == {"estrategico": 4, "complexidade": 4}
    assert by_project["TN-2026-027"] == {"estrategico": 3, "complexidade": 2}


register_check("projetos do portfolio", _afirmar_projetos_do_portfolio)
register_check("cadastros de apoio", _afirmar_cadastros_de_apoio)
register_check("pessoas e colaboradores", _afirmar_pessoas_e_colaboradores)
register_check("parametros e ponderacao", _afirmar_parametros_e_ponderacao)


def test_oraculo_com_a_data_25_09_2026(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    assert registered_checks(), "nenhuma afirmacao registrada"

    failures: list[str] = []
    for description, check in registered_checks():
        try:
            check(context)
        except AssertionError as error:
            failures.append(f"{description}: {error}")
    assert not failures, "Afirmacoes do oraculo falharam:\n" + "\n".join(failures)
