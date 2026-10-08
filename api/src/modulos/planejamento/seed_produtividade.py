"""Produtividade na carga de demonstração (ISSUE-046, D6).

Chamado pela parte ``planejamento-produtividade`` que ``seed.py`` registra depois das demais
partes do módulo. Lê o plano de quantidades dos mocks do protótipo
(``prototype_collection("produtividadeItens")``: 14 itens dos três projetos, com a distribuição
semanal, os apontamentos e as revisões) e grava pela fachada, com a trilha.

As datas andam com ``shift_date`` como no resto da carga; as semanas ISO andam em semanas
inteiras (a diferença entre a semana da âncora e a semana da execução), para a distribuição e o
corte continuarem coerentes com o protótipo. A distribuição do mock pertence à revisão vigente
do item; as revisões anteriores ficam só com o total congelado, porque o mock não guarda a
distribuição antiga. A SM da revisão é resolvida pela fachada da Governança (D9), que já rodou.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.carga import DEMO_ANCHOR, prototype_collection, shift_date
from src.core import calendario
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, service

ADMIN_PROFILE = "Admin"


def load_items(session: Session, reference_date: date) -> None:
    """Grava os 14 itens do plano de quantidades do protótipo, deslocados para a execução."""
    weeks = _week_offset(reference_date)
    author = _author(session)
    ids = _Ids.read(session)
    changes = _change_ids(session)
    for source in prototype_collection("produtividadeItens"):
        service.load_item(
            session,
            author_id=author.id,
            data=service.LoadedItem(
                project_id=ids.project(source["projetoId"]),
                company_id=ids.companies[source["empresaId"]],
                unit_id=ids.unit(source.get("unidade")),
                discipline_id=ids.discipline(source.get("disciplina")),
                approved_by_id=ids.person(source.get("aprovadoPorId")),
                code=source["codigo"],
                group=source["grupo"],
                kind=source["tipo"],
                places=int(source["casas"]),
                total=Decimal(str(source["total"])),
                index_hh=Decimal(str(source["indiceHH"])),
                profile=source["perfil"],
                situation=source["situacao"],
                revision=int(source["revisao"]),
                start=_week_date(source["inicio"], weeks),
                finish=_week_date(source["fim"], weeks),
                approved_on=_shifted(source.get("aprovadoEm"), reference_date),
                notes=source.get("observacoes") or None,
                revisions=tuple(
                    _revision(
                        item=source,
                        source=revision,
                        weeks=weeks,
                        ids=ids,
                        changes=changes,
                        reference_date=reference_date,
                    )
                    for revision in source.get("revisoes", ())
                ),
                entries=tuple(
                    _entry(entry, weeks=weeks, reference_date=reference_date)
                    for entry in source.get("apontamentos", ())
                ),
            ),
        )


def _author(session: Session) -> configuracoes.CollaboratorAccess:
    """O Admin da demonstração, autor dos registros que a carga grava."""
    return next(
        item
        for item in configuracoes.list_active_access(session)
        if item.general_profile == ADMIN_PROFILE
    )


def _week_offset(reference_date: date) -> int:
    """Quantas semanas inteiras separam a semana da âncora da semana da execução."""
    return (
        calculations.weeks_between(
            calendario.iso_week(DEMO_ANCHOR), calendario.iso_week(reference_date)
        )
        or 0
    )


def _week(label: str, weeks: int) -> str:
    return calculations.shift_week(label, weeks) or label


def _week_date(label: str, weeks: int) -> date:
    found = calculations.week_start(_week(label, weeks))
    if found is None:
        message = f"A semana {label} do protótipo não é válida."
        raise ValueError(message)
    return found


def _shifted(text: str | None, reference_date: date) -> date | None:
    return None if not text else shift_date(date.fromisoformat(text), reference_date)


@dataclass(frozen=True)
class _Ids:
    """Os ids deste banco para os ids do mock: projeto por código, cadastro pelo nome ou código."""

    projects: Mapping[int, int]
    companies: Mapping[int, int]
    people: Mapping[int, int]
    units: Mapping[str, int]
    disciplines: Mapping[str, int]

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
            units={unit.code: unit.id for unit in configuracoes.list_measure_units(session)},
            disciplines={
                name: discipline_id
                for discipline_id, name in configuracoes.discipline_names_by_id(session).items()
            },
        )

    def project(self, mock_id: int) -> int:
        return self.projects[mock_id]

    def company(self, mock_id: int | None) -> int | None:
        return self.companies[mock_id] if mock_id is not None else None

    def person(self, mock_id: int | None) -> int | None:
        return self.people[mock_id] if mock_id is not None else None

    def unit(self, code: str | None) -> int | None:
        return self.units.get(code or "")

    def discipline(self, name: str | None) -> int | None:
        return self.disciplines.get(name or "")


def _change_ids(session: Session) -> dict[str, int]:
    """O id de cada SM do mock pelo código, pela fachada da Governança (D9)."""
    from src.modulos.governanca import service as governanca

    codes = [
        source["smRef"]
        for item in prototype_collection("produtividadeItens")
        for source in item.get("revisoes", ())
        if source.get("smRef")
    ]
    return governanca.change_ids_by_code(session, codes=codes)


def _revision(
    *,
    item: Mapping[str, Any],
    source: Mapping[str, Any],
    weeks: int,
    ids: _Ids,
    changes: Mapping[str, int],
    reference_date: date,
) -> service.LoadedRevision:
    """Uma revisão do item: a distribuição só entra na revisão vigente do mock."""
    revision = int(source["rev"])
    return service.LoadedRevision(
        revision=revision,
        revision_date=shift_date(date.fromisoformat(source["data"]), reference_date),
        by_id=ids.person(source["porId"]) or 0,
        total=Decimal(str(source["total"])),
        previous_total=(
            Decimal(str(source["totalAnterior"])) if source.get("totalAnterior") else None
        ),
        change_id=changes.get(source.get("smRef") or ""),
        since=_week(source["desde"], weeks) if source.get("desde") else None,
        justification=source["justificativa"],
        planned=(_distribution(item, weeks=weeks) if revision == int(item["revisao"]) else ()),
    )


def _distribution(item: Mapping[str, Any], *, weeks: int) -> tuple[calculations.PlannedWeek, ...]:
    return tuple(
        calculations.PlannedWeek(
            week=_week(line["semana"], weeks), planned=Decimal(str(line["previsto"]))
        )
        for line in item.get("distribuicao", ())
    )


def _entry(source: Mapping[str, Any], *, weeks: int, reference_date: date) -> service.LoadedEntry:
    return service.LoadedEntry(
        week=_week(source["semana"], weeks),
        realized=Decimal(str(source["realizado"])),
        hh=Decimal(str(source["hh"] or 0)),
        informed_on=_shifted(source.get("informadoEm"), reference_date),
    )
