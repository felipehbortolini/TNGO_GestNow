"""Apoio dos testes da EAP (ISSUE-036): dois projetos com árvore, medições, revisões e desdobramento.

O projeto A tem duas áreas, duas subáreas e quatro pacotes (um por critério visto nos testes) e o
projeto B um pacote sem medição. Os números esperados saem da regra do protótipo feita à mão:

* 1.1.1 Unidades (100 m³, executado 50): peso 50, previsto 60, real 50, término vencido;
* 1.1.2 Marco 0/100 concluído: peso 30, previsto 100, real 100;
* 1.1.3 Etapas (modelo de engenharia 40/30/30) com medição 20 e depois 40: peso 10, previsto 20, real 40;
* 2.1.1 Planejamento: peso 10, previsto 0, sem medição;
* subárea 1.1: peso 90, previsto 68,89, real 65,56; projeto A: previsto 62,00, real 59,00, desvio -3,0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.core.auth import _user_of
from src.core.rbac import User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Company, Project, Unit
from src.modulos.planejamento import eap_calculations as calculations
from src.modulos.planejamento import eap_service as service
from src.modulos.planejamento.eap_service import (
    NewMeasurement,
    NewPackage,
    NewRevision,
    NewSplit,
)
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto

HOJE = date(2026, 9, 25)
MEMBER_EMAIL = "membro-eap@example.invalid"
VIEWER_EMAIL = "visualizador-eap@example.invalid"
SUPPLIER_EMAIL = "fornecedor-eap@example.invalid"
D = Decimal


@dataclass(frozen=True)
class EapCadastro:
    """O cenário: os dois projetos, a empresa, os usuários e o id de cada item por projeto e código."""

    session: Session
    first: Project
    second: Project
    company: Company
    member: User
    viewer: User
    supplier: User
    items: dict[str, int]
    author_person_id: int

    def item(self, project: Project, code: str) -> int:
        """O id do item do projeto com o código."""
        return self.items[f"{project.code}:{code}"]


def _user(session: Session, email: str) -> User:
    access = configuracoes.find_access_by_email(session, email)
    if access is None:
        raise LookupError(email)
    return _user_of(access)


def montar_eap(session: Session) -> EapCadastro:
    """Cria o cenário dentro da transação do teste."""
    first = criar_projeto(session, codigo="TN-EAP-001", nome="Fábrica EAP")
    second = criar_projeto(session, codigo="TN-EAP-002", nome="Caldeira EAP")
    company = criar_empresa(session, "Montadora EAP")
    member = criar_colaborador(session, email=MEMBER_EMAIL, nome="Maria Membro", perfil="Membro")
    criar_colaborador(session, email=VIEWER_EMAIL, nome="Vera Visualizadora", perfil="Visualizador")
    criar_colaborador(
        session,
        email=SUPPLIER_EMAIL,
        perfil="Membro",
        vinculo="Fornecedor",
        empresa=company,
    )
    unit = Unit(kind="medida", code="m³", name="Metro cúbico")
    session.add(unit)
    session.flush()
    items: dict[str, int] = {}
    scenario = EapCadastro(
        session=session,
        first=first,
        second=second,
        company=company,
        member=_user(session, MEMBER_EMAIL),
        viewer=_user(session, VIEWER_EMAIL),
        supplier=_user(session, SUPPLIER_EMAIL),
        items=items,
        author_person_id=member.person_id,
    )
    _tree_of_first(scenario, unit.id)
    _tree_of_second(scenario)
    _revisions(scenario)
    return scenario


def _add(
    scenario: EapCadastro, project: Project, code: str, description: str, **fields: Any
) -> int:
    parent_code = ".".join(code.split(".")[:-1])
    item_id = service.create_item(
        scenario.session,
        user_id=scenario.member.id,
        new=NewPackage(
            project_id=project.id,
            code=code,
            description=description,
            level=len(code.split(".")),
            parent_id=scenario.items.get(f"{project.code}:{parent_code}"),
            **fields,
        ),
    )
    scenario.items[f"{project.code}:{code}"] = item_id
    return item_id


def _measure(
    scenario: EapCadastro, item_id: int, day: date, from_percent: str, to_percent: str
) -> None:
    service.add_measurement(
        scenario.session,
        user_id=scenario.member.id,
        new=NewMeasurement(
            item_id=item_id,
            measured_on=day,
            from_percent=D(from_percent),
            to_percent=D(to_percent),
            author_id=scenario.author_person_id,
            note="Medição de teste.",
        ),
    )


def _tree_of_first(scenario: EapCadastro, unit_id: int) -> None:
    project = scenario.first
    _add(scenario, project, "1", "Engenharia")
    _add(scenario, project, "1.1", "Projeto básico")
    _add(scenario, project, "2", "Montagem")
    _add(scenario, project, "2.1", "Montagem futura")
    common = {
        "company_id": scenario.company.id,
        "responsible_id": scenario.author_person_id,
        "deliverable": "Entregável de teste",
        "acceptance": "Aceite de teste",
    }
    units = _add(
        scenario,
        project,
        "1.1.1",
        "Fundações",
        kind=calculations.WORK,
        criterion=calculations.UNITS,
        unit_id=unit_id,
        quantity=D(100),
        weight=D(50),
        planned=D(60),
        start_date=date(2026, 1, 5),
        end_date=date(2026, 9, 1),
        **common,
    )
    milestone = _add(
        scenario,
        project,
        "1.1.2",
        "Licença",
        kind=calculations.WORK,
        criterion=calculations.MILESTONE_0_100,
        weight=D(30),
        planned=D(100),
        start_date=date(2026, 1, 5),
        end_date=date(2026, 8, 1),
        **common,
    )
    stages = _add(
        scenario,
        project,
        "1.1.3",
        "Projeto de processo",
        kind=calculations.WORK,
        criterion=calculations.STAGES,
        stage_model="engenharia",
        weight=D(10),
        planned=D(20),
        start_date=date(2026, 3, 2),
        end_date=date(2026, 12, 31),
        **common,
    )
    _add(
        scenario,
        project,
        "2.1.1",
        "Comissionamento a detalhar",
        kind=calculations.PLANNING,
        weight=D(10),
        planned=D(0),
        start_date=date(2026, 11, 1),
        end_date=date(2027, 3, 31),
    )
    service.add_stages(
        scenario.session,
        user_id=scenario.member.id,
        item_id=stages,
        stages=[("Elaboração", D(40)), ("Emissão para comentários", D(30)), ("Emissão", D(30))],
    )
    _measure(scenario, units, date(2026, 9, 20), "0", "50")
    _measure(scenario, milestone, date(2026, 7, 20), "0", "100")
    _measure(scenario, stages, date(2026, 9, 10), "0", "20")
    _measure(scenario, stages, date(2026, 9, 20), "20", "40")


def _tree_of_second(scenario: EapCadastro) -> None:
    project = scenario.second
    _add(scenario, project, "1", "Obra civil")
    _add(scenario, project, "1.1", "Fundações")
    _add(
        scenario,
        project,
        "1.1.1",
        "Estacas",
        kind=calculations.WORK,
        criterion=calculations.ESTIMATED,
        weight=D(100),
        planned=D(50),
        start_date=date(2026, 8, 1),
        end_date=date(2027, 1, 1),
    )


def _revisions(scenario: EapCadastro) -> None:
    first, second = scenario.first, scenario.second
    frozen_first = {
        scenario.item(first, "1.1.1"): D(50),
        scenario.item(first, "1.1.2"): D(30),
        scenario.item(first, "1.1.3"): D(10),
        scenario.item(first, "2.1.1"): D(10),
    }
    base = {"approved_by_id": scenario.author_person_id}
    for project, number, day, change, frozen in (
        (first, 0, date(2026, 1, 5), "Linha de base", None),
        (first, 1, date(2026, 5, 18), "Pacote 1.1.3 incluído", frozen_first),
        (second, 0, date(2026, 8, 1), "Linha de base", {scenario.item(second, "1.1.1"): D(100)}),
    ):
        service.create_revision(
            scenario.session,
            user_id=scenario.member.id,
            new=NewRevision(
                project_id=project.id,
                number=number,
                revised_on=day,
                change=change,
                justification=f"Justificativa da Rev {number}.",
                frozen_weights=frozen,
                **base,
            ),
        )
    service.add_split(
        scenario.session,
        user_id=scenario.member.id,
        new=NewSplit(
            project_id=first.id,
            source_item_id=scenario.item(first, "2.1.1"),
            target_item_id=scenario.item(first, "1.1.3"),
            revision=1,
            split_on=date(2026, 9, 10),
            weight=D("0.8"),
            justification="Plano detalhado.",
            by_id=scenario.author_person_id,
        ),
    )
