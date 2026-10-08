"""Punch list na carga de demonstração (ISSUE-049, D6).

A parte ``planejamento-punch`` grava os itens do protótipo (``punch``) nos sistemas do cadastro
de apoio (``sistema``, já carregado pela plataforma), com as datas deslocadas para a data de
referência. A numeração de cada projeto continua depois do maior código do mock, para o
primeiro item gerado por uma pessoa não colidir com a série. As ações de origem Punch list não
nascem aqui: a parte ``central_acoes`` já as derivou uma a uma (``acaoDoPunch``) e a fachada
desta fatia só as mantém em dia (``service.close_from_origin``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import prototype_collection, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core import numbering, recording
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import System
from src.modulos.planejamento.models import PunchItem
from src.modulos.planejamento.service import PUNCH_KIND


def load_punch(session: Session, reference_date: date) -> None:
    """Grava os itens da punch list do protótipo, dentro da transação de quem chama."""
    author_id = _author_id(session)
    project_ids = {item.code: item.id for item in configuracoes.list_projects(session)}
    people = {person.email.lower(): person.id for person in configuracoes.list_people(session)}
    last_numbers: dict[int, int] = {}
    for source in prototype_collection("punch"):
        project_id = project_ids[_project_code(source)]
        recording.create(
            session,
            user_id=author_id,
            record=PunchItem(
                project_id=project_id,
                system_id=_system_id(session, project_id, source),
                company_id=_company_id(session, source),
                owner_id=people[_person_email(source["responsavelId"])],
                identified_by_id=people[_person_email(source["identificadoPorId"])],
                verified_by_id=_verified_by(people, source),
                code=source["codigo"],
                subsystem=source["subsistema"],
                tag=source["tag"],
                discipline=source["disciplina"],
                category=source["categoria"],
                milestone=source["marco"],
                origin=source["origem"],
                description=source["descricao"],
                opened_on=shift_date(date.fromisoformat(source["abertura"]), reference_date),
                due_date=shift_date(date.fromisoformat(source["prazo"]), reference_date),
                closed_on=_shifted(source.get("fechamento"), reference_date),
                situation=source["situacao"],
            ),
        )
        last_numbers[project_id] = max(last_numbers.get(project_id, 0), _suffix(source["codigo"]))
    for project_id, last_number in last_numbers.items():
        project = configuracoes.find_project(session, project_id)
        if project is not None:
            numbering.start_after(
                session, project=project, kind=PUNCH_KIND, last_number=last_number
            )


def _author_id(session: Session) -> int:
    """O Admin da demonstração, autor dos registros que a carga grava."""
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if access is None:
        message = f"O Admin da demonstração ({ADMIN_EMAIL}) não está no cadastro."
        raise LookupError(message)
    return access.id


def _project_code(source: Mapping[str, Any]) -> str:
    projects = {project["id"]: project["codigo"] for project in prototype_collection("projetos")}
    return projects[source["projetoId"]]


def _person_email(mock_id: int) -> str:
    people = {person["id"]: person["email"] for person in prototype_collection("pessoas")}
    return people[mock_id].lower()


def _system_id(session: Session, project_id: int, source: Mapping[str, Any]) -> int:
    """O sistema do cadastro de apoio pelo código do mock, dentro do projeto."""
    code = {system["id"]: system["codigo"] for system in prototype_collection("sistemas")}[
        source["sistemaId"]
    ]
    found = session.scalar(
        select(System.id).where(System.project_id == project_id, System.code == code)
    )
    if found is None:
        message = f"O sistema {code} do mock não está no cadastro do projeto."
        raise LookupError(message)
    return found


def _company_id(session: Session, source: Mapping[str, Any]) -> int:
    name = {company["id"]: company["nome"] for company in prototype_collection("empresas")}[
        source["empresaId"]
    ]
    found = next(
        (
            option.id
            for option in configuracoes.list_company_options(session)
            if option.name == name
        ),
        None,
    )
    if found is None:
        message = f"A empresa {name} do mock não está no cadastro."
        raise LookupError(message)
    return found


def _verified_by(people: Mapping[str, int], source: Mapping[str, Any]) -> int | None:
    mock_id = source.get("verificadoPorId")
    return None if mock_id is None else people[_person_email(mock_id)]


def _shifted(value: str | None, reference_date: date) -> date | None:
    return None if value is None else shift_date(date.fromisoformat(value), reference_date)


def _suffix(code: str) -> int:
    return int(code.rsplit("-", 1)[1])
