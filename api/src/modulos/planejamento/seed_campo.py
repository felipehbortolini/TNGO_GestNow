"""Horas efetivas na carga de demonstração (ISSUE-047, D6).

Chamado pela parte ``planejamento-campo`` que ``seed.py`` registra depois das demais partes do
módulo. Lê as jornadas, as rodadas da amostragem (com os motivos de parada e trânsito) e as
paralisações dos mocks do protótipo (``jornadasCampo``, ``amostragens`` e ``paralisacoes``) e
grava pela fachada, com a trilha.

As datas andam em dias inteiros (``shift_date``), como no resto da carga. Os cadastros que o
protótipo numera (projeto, empresa, pessoa) são achados pela chave de negócio (código, nome),
porque os ids do banco não são os do mock; o encarregado é o texto digitado pela fiscalização,
como no protótipo, e não um cadastro.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, shift_date
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, service

ADMIN_PROFILE = "Admin"


def load_field(session: Session, reference_date: date) -> None:
    """Grava as jornadas, as rodadas e as paralisações do protótipo, deslocadas para a execução."""
    author = _author(session)
    ids = _Ids.read(session)
    for source in prototype_collection("jornadasCampo"):
        service.load_field_day(
            session,
            author_id=author.id,
            data=_field_day(
                source, ids=ids, author_id=author.person_id, reference_date=reference_date
            ),
        )
    for source in prototype_collection("amostragens"):
        service.load_work_sample(
            session,
            author_id=author.id,
            data=_work_sample(
                source, ids=ids, author_id=author.person_id, reference_date=reference_date
            ),
        )
    for source in prototype_collection("paralisacoes"):
        service.load_stoppage(
            session,
            author_id=author.id,
            data=_stoppage(
                source, ids=ids, author_id=author.person_id, reference_date=reference_date
            ),
        )


def _author(session: Session) -> configuracoes.CollaboratorAccess:
    """O Admin da demonstração, autor dos registros que a carga grava."""
    return next(
        item
        for item in configuracoes.list_active_access(session)
        if item.general_profile == ADMIN_PROFILE
    )


@dataclass(frozen=True)
class _Ids:
    """Os ids deste banco para os ids do mock: projeto por código, cadastro pelo nome."""

    projects: Mapping[int, int]
    companies: Mapping[int, int]
    people: Mapping[int, int]

    @classmethod
    def read(cls, session: Session) -> _Ids:
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
        return self.projects[mock_id]

    def company(self, mock_id: int) -> int:
        return self.companies[mock_id]

    def person(self, mock_id: int | None) -> int | None:
        return self.people[mock_id] if mock_id is not None else None


def _field_day(
    source: Mapping[str, Any], *, ids: _Ids, author_id: int, reference_date: date
) -> service.LoadedFieldDay:
    return service.LoadedFieldDay(
        project_id=ids.project(source["projetoId"]),
        company_id=ids.company(source["empresaId"]),
        recorded_by_id=ids.person(source.get("registradoPorId")) or author_id,
        day=_shifted_day(source["data"], reference_date),
        area=source["area"],
        foreman=source["encarregado"],
        crew=int(source["efetivo"]),
        morning=_shift_times(source["manha"]),
        afternoon=_shift_times(source["tarde"]),
        notes=source.get("observacoes") or None,
    )


def _work_sample(
    source: Mapping[str, Any], *, ids: _Ids, author_id: int, reference_date: date
) -> service.LoadedWorkSample:
    reasons = tuple(
        service.LoadedSampleReason(kind=kind, reason=item["motivo"], quantity=int(item["qtd"]))
        for kind, campo in (
            (calculations.SAMPLE_STOPPED, "motivosParado"),
            (calculations.SAMPLE_TRANSIT, "motivosTransito"),
        )
        for item in source.get(campo, ())
    )
    return service.LoadedWorkSample(
        project_id=ids.project(source["projetoId"]),
        company_id=ids.company(source["empresaId"]),
        observer_id=ids.person(source.get("observadorId")) or author_id,
        day=_shifted_day(source["data"], reference_date),
        hour=time.fromisoformat(source["hora"]),
        area=source["area"],
        foreman=source["encarregado"],
        working=int(source["trabalhando"]),
        transit=int(source["transito"]),
        stopped=int(source["parado"]),
        reasons=reasons,
    )


def _stoppage(
    source: Mapping[str, Any], *, ids: _Ids, author_id: int, reference_date: date
) -> service.LoadedStoppage:
    return service.LoadedStoppage(
        project_id=ids.project(source["projetoId"]),
        company_id=ids.company(source["empresaId"]),
        recorded_by_id=ids.person(source.get("registradoPorId")) or author_id,
        day=_shifted_day(source["data"], reference_date),
        area=source["area"],
        kind=source["tipo"],
        resource=source["recurso"],
        quantity=Decimal(str(source["quantidade"])),
        start=time.fromisoformat(source["inicio"]),
        end=time.fromisoformat(source["termino"]),
        reason=source["motivo"],
        responsibility=source["responsabilidade"],
        description=source.get("descricao") or None,
    )


def _shifted_day(text: str, reference_date: date) -> date:
    return shift_date(date.fromisoformat(text), reference_date)


def _shift_times(source: Mapping[str, Any]) -> calculations.ShiftTimes:
    return calculations.ShiftTimes(
        arrival=time.fromisoformat(source["chegada"]),
        start=time.fromisoformat(source["inicio"]),
        end=time.fromisoformat(source["termino"]),
    )
