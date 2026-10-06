"""Punch list na carga de demonstração (ISSUE-049, D6).

Chamado por ``seed.load``. Lê os 20 itens dos mocks do protótipo (``prototype_collection("punch")``)
e grava pela fachada, com a trilha: os itens dos projetos 1 e 2, nas cinco situações, com os
códigos do protótipo. As datas andam com ``shift_date``. As ações da Central dos itens (menos as
do item cancelado) já vêm da carga da Central, que as derivava no protótipo (``acaoDoPunch``), por
isso aqui só entra o item. Os cadastros que o protótipo numera (projeto, sistema, empresa, pessoa)
são achados pela chave de negócio, porque os ids do banco não são os do mock. A evidência do
protótipo era só o nome de um arquivo; o arquivo de verdade não existe na demonstração, então um
item que vai ser fechado na demonstração recebe o anexo da evidência pela tela.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, shift_date
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import punch_service as service
from src.modulos.planejamento.punch_validation import ItemInput

ADMIN_PROFILE = "Admin"


def load_items(session: Session, reference_date: date) -> None:
    """Write the items of the prototype, shifted to the reference date of the run."""
    author = next(
        item
        for item in configuracoes.list_active_access(session)
        if item.general_profile == ADMIN_PROFILE
    )
    ids = _Ids.read(session)
    last_numbers: dict[int, int] = {}
    for source in prototype_collection("punch"):
        project_id = ids.projects[source["projetoId"]]
        service.load_item(session, user_id=author.id, item=_item(source, ids, reference_date))
        suffix = int(source["codigo"].rsplit("-", 1)[1])
        last_numbers[project_id] = max(last_numbers.get(project_id, 0), suffix)
    for project_id, last_number in last_numbers.items():
        service.continue_numbering(session, project_id=project_id, last_number=last_number)


def _item(source: dict[str, Any], ids: _Ids, reference_date: date) -> service.LoadedItem:
    closing = source.get("fechamento")
    verifier = source.get("verificadoPorId")
    return service.LoadedItem(
        project_id=ids.projects[source["projetoId"]],
        code=source["codigo"],
        data=ItemInput(
            system_id=ids.systems[source["sistemaId"]],
            subsystem=source["subsistema"],
            tag=source["tag"],
            discipline=source["disciplina"],
            category=source["categoria"],
            milestone=source["marco"],
            origin=source["origem"],
            description=source["descricao"],
            company_id=ids.companies[source["empresaId"]],
            responsible_id=ids.people[source["responsavelId"]],
            identified_by_id=ids.people[source["identificadoPorId"]],
            due_date=_shifted(source["prazo"], reference_date),
        ),
        opened_on=_shifted(source["abertura"], reference_date),
        situation=source["situacao"],
        closed_on=_shifted(closing, reference_date) if closing else None,
        verified_by_id=ids.people[verifier] if verifier is not None else None,
        cancellation_reason=source.get("justificativaCancelamento"),
    )


def _shifted(value: str, reference_date: date) -> date:
    return shift_date(date.fromisoformat(value), reference_date)


class _Ids:
    """The ids of this database for the mock ids: projects by code, systems by project and code."""

    def __init__(
        self,
        projects: dict[int, int],
        systems: dict[int, int],
        companies: dict[int, int],
        people: dict[int, int],
    ) -> None:
        self.projects = projects
        self.systems = systems
        self.companies = companies
        self.people = people

    @classmethod
    def read(cls, session: Session) -> _Ids:
        project_by_code = {item.code: item.id for item in configuracoes.list_projects(session)}
        projects = {
            source["id"]: project_by_code[source["codigo"]]
            for source in prototype_collection("projetos")
        }
        system_by_key = {
            (item.project_id, item.code): item.id for item in configuracoes.list_systems(session)
        }
        company_by_name = {
            item.name: item.id for item in configuracoes.list_company_options(session)
        }
        person_by_name = {item.name: item.id for item in configuracoes.list_person_options(session)}
        return cls(
            projects=projects,
            systems={
                source["id"]: system_by_key[(projects[source["projetoId"]], source["codigo"])]
                for source in prototype_collection("sistemas")
            },
            companies={
                source["id"]: company_by_name[source["nome"]]
                for source in prototype_collection("empresas")
            },
            people={
                source["id"]: person_by_name[source["nome"]]
                for source in prototype_collection("pessoas")
            },
        )
