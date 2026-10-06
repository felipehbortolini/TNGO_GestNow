"""Parte do módulo Planejamento na carga de demonstração (D6, ISSUE-008).

Cada issue do módulo acrescenta aqui a sua parte, como uma função chamada por ``load``:
o 6WLA (ISSUE-045) grava as atividades, as semanas e as restrições do protótipo
(``lookahead``) o Relato do período (ISSUE-044) grava os relatos (``seed_relato``) e a EAP (ISSUE-036) grava a árvore, as medições, as revisões e os desdobramentos (``eap_seed``). Os cadastros que o protótipo numera (projeto, empresa, pessoa) são
achados pela chave de negócio (código, nome), porque os ids do banco não são os do mock.
As datas das restrições andam com ``shift_date``; o início do horizonte não é gravado,
sai do calendário (``calculations.lookahead_window_start``).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.modulos.configuracoes import service as configuracoes
<<<<<<< HEAD
from src.modulos.planejamento import seed_punch, seed_relato, service
=======
from src.modulos.planejamento import eap_seed, seed_relato, service
>>>>>>> exec/ISSUE-036

PART_NAME = "planejamento"
ADMIN_PROFILE = "Admin"


def load(session: Session, reference_date: date) -> None:
    """Write the part of the Planning module, inside the caller's transaction."""
    _load_lookahead(session, reference_date)
    seed_relato.load_reports(session, reference_date)
<<<<<<< HEAD
    seed_punch.load_items(session, reference_date)
=======
    eap_seed.load_eap(session, reference_date)
>>>>>>> exec/ISSUE-036


def _load_lookahead(session: Session, reference_date: date) -> None:
    """The 6WLA of the prototype: ``lookahead`` with its weeks and restrictions."""
    author = next(
        item
        for item in configuracoes.list_active_access(session)
        if item.general_profile == ADMIN_PROFILE
    )
    ids = _RegisterIds.read(session)
    for source in prototype_collection("lookahead"):
        service.load_activity(
            session,
            author_id=author.id,
            data=service.LoadedActivity(
                project_id=ids.project(source["projetoId"]),
                company_id=ids.company(source["empresaId"]),
                owner_id=ids.person(source["responsavelId"]),
                code=source["codigo"],
                activity=source["atividade"],
                area=source["area"],
                discipline=source["disciplina"],
                planned=tuple(bool(mark) for mark in source["semanas"]),
                constraints=tuple(
                    _constraint(item, ids, reference_date) for item in source["restricoes"]
                ),
            ),
        )


def _constraint(
    source: dict[str, Any], ids: _RegisterIds, reference_date: date
) -> service.LoadedConstraint:
    removal = source["remocao"]
    return service.LoadedConstraint(
        kind=source["tipo"],
        owner_id=ids.person(source["responsavelId"]),
        description=source["descricao"],
        due_date=shift_date(date.fromisoformat(source["necessaria"]), reference_date),
        removal_date=shift_date(date.fromisoformat(removal), reference_date) if removal else None,
    )


class _RegisterIds:
    """The ids of this database for the mock ids: projects by code, companies and people by name."""

    def __init__(
        self, projects: dict[int, int], companies: dict[int, int], people: dict[int, int]
    ) -> None:
        self._projects = projects
        self._companies = companies
        self._people = people

    @classmethod
    def read(cls, session: Session) -> _RegisterIds:
        project_by_code = {item.code: item.id for item in configuracoes.list_projects(session)}
        company_by_name = {
            item.name: item.id for item in configuracoes.list_company_options(session)
        }
        person_by_name = {item.name: item.id for item in configuracoes.list_person_options(session)}
        return cls(
            projects={
                source["id"]: project_by_code[source["codigo"]]
                for source in prototype_collection("projetos")
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

    def project(self, mock_id: int) -> int:
        return self._projects[mock_id]

    def company(self, mock_id: int | None) -> int | None:
        return self._companies[mock_id] if mock_id is not None else None

    def person(self, mock_id: int | None) -> int | None:
        return self._people[mock_id] if mock_id is not None else None


register(PART_NAME, load)
