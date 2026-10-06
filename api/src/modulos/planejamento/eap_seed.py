"""EAP in the demonstration load (ISSUE-036, D6).

Called by ``seed.load``. Reads the ``eap``, ``eapRevisoes`` and ``eapDesdobramentos`` collections
of the prototype and writes them through the facade: the three-level tree of each project (110
items, 38 packages in the project 1), the stages, the measurements, the revisions and the splits.
The progress of a package is not a column (D5b): the prototype kept the entries of the criterion
(stages done, executed quantity, milestone state, estimate), so the load writes the measurements
that reproduce them. The three measurements of the prototype go as they are; a package with
progress and no measurement gets one, dated on the reference date, from zero to its progress.

The prototype kept no weights per revision. The load freezes the weights of the revision in force
of each project (the current ones, plus the weight a split took out of the planning package after
the revision was approved); the earlier revisions keep no frozen weights and show no package count.
Every date moves with ``shift_date``; the codes of the register (project, company, person) are
found by their business key, because the ids of the database are not the ones of the mock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service as financeiro
from src.modulos.governanca import service as governanca
from src.modulos.planejamento import eap_calculations as calculations
from src.modulos.planejamento import eap_service as service
from src.modulos.planejamento.eap_calculations import PackageEntries, StageLine

LOAD_NOTE = "Avanço da carga de demonstração."


def load_eap(session: Session, reference_date: date) -> None:
    """Write the EAP of every project of the prototype, inside the caller's transaction."""
    admin = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if admin is None:
        return
    load = _Load(
        session=session,
        author_id=admin.id,
        ids=_RegisterIds.read(session),
        reference_date=reference_date,
    )
    tree = _load_tree(load)
    _load_revisions(load, tree)


class _RegisterIds:
    """The ids of this database for the mock ids: projects by code, companies and people by name."""

    def __init__(
        self,
        projects: dict[int, int],
        companies: dict[int, int],
        people: dict[int, int],
        units: dict[str, int],
    ) -> None:
        self._projects = projects
        self._companies = companies
        self._people = people
        self.units = units

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
            units={unit.code: unit.id for unit in configuracoes.list_measure_units(session)},
        )

    def project(self, mock_id: int) -> int:
        return self._projects[mock_id]

    def company(self, mock_id: int | None) -> int | None:
        return self._companies[mock_id] if mock_id is not None else None

    def person(self, mock_id: int | None) -> int | None:
        return self._people[mock_id] if mock_id is not None else None


def _decimal(value: Any) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _day(text: str | None, reference_date: date) -> date | None:
    return shift_date(date.fromisoformat(text), reference_date) if text else None


@dataclass(frozen=True)
class _Tree:
    """What the load wrote: the id and the weight of each item, by project (database id) and code."""

    items: dict[tuple[int, str], int]
    weights: dict[tuple[int, str], Decimal]


@dataclass(frozen=True)
class _Load:
    """What every step of the load shares: the session, the author, the register ids and the date."""

    session: Session
    author_id: int
    ids: _RegisterIds
    reference_date: date


def _load_tree(load: _Load) -> _Tree:
    """Write the items, stages and measurements; return what the revisions need to freeze weights."""
    session, author_id, ids = load.session, load.author_id, load.ids
    created: dict[tuple[int, str], int] = {}
    weights: dict[tuple[int, str], Decimal] = {}
    sources = sorted(
        prototype_collection("eap"),
        key=lambda item: (item["projetoId"], calculations.code_key(item["codigo"])),
    )
    eac_ids: dict[int, dict[str, int]] = {}
    for source in sources:
        project_id = ids.project(source["projetoId"])
        if project_id not in eac_ids:
            codes = [
                item["eacCodigo"]
                for item in sources
                if item["projetoId"] == source["projetoId"] and item.get("eacCodigo")
            ]
            eac_ids[project_id] = financeiro.eac_item_ids_by_code(
                session, project_id=project_id, codes=codes
            )
        parent_code = calculations.CODE_SEPARATOR.join(
            source["codigo"].split(calculations.CODE_SEPARATOR)[:-1]
        )
        item_id = service.create_item(
            session,
            user_id=author_id,
            new=_new_package(
                source,
                load=load,
                project_id=project_id,
                parent_id=created.get((project_id, parent_code)),
                eac_item_id=eac_ids[project_id].get(source.get("eacCodigo") or ""),
            ),
        )
        created[(project_id, source["codigo"])] = item_id
        if source.get("peso"):
            weights[(project_id, source["codigo"])] = Decimal(str(source["peso"]))
        if source["nivel"] == calculations.PACKAGE_LEVEL:
            _load_package_detail(load, item_id, source)
    return _Tree(items=created, weights=weights)


def _new_package(
    source: dict[str, Any],
    *,
    load: _Load,
    project_id: int,
    parent_id: int | None,
    eac_item_id: int | None,
) -> service.NewPackage:
    ids, reference_date = load.ids, load.reference_date
    return service.NewPackage(
        project_id=project_id,
        code=source["codigo"],
        description=source["descricao"],
        level=source["nivel"],
        parent_id=parent_id,
        kind=source.get("tipo"),
        criterion=source.get("criterio"),
        stage_model=source.get("modelo"),
        unit_id=ids.units.get(source.get("unidade") or ""),
        quantity=_decimal(source.get("quantidade")),
        weight=_decimal(source.get("peso")),
        planned=_decimal(source.get("previsto")),
        start_date=_day(source.get("inicio"), reference_date),
        end_date=_day(source.get("termino"), reference_date),
        company_id=ids.company(source.get("empresaId")),
        responsible_id=ids.person(source.get("responsavelId")),
        eac_item_id=eac_item_id,
        deliverable=source.get("entregavel"),
        acceptance=source.get("aceitacao"),
    )


def _load_package_detail(load: _Load, item_id: int, source: dict[str, Any]) -> None:
    """The stages and the measurements of a package: the ones of the prototype and, if needed, one more."""
    session, author_id, ids = load.session, load.author_id, load.ids
    reference_date = load.reference_date
    stages = [(stage["nome"], Decimal(str(stage["peso"]))) for stage in source.get("etapas") or []]
    if stages:
        service.add_stages(session, user_id=author_id, item_id=item_id, stages=stages)
    real = _prototype_progress(source)
    last = Decimal(0)
    for measurement in source.get("medicoes") or []:
        last = Decimal(str(measurement["para"]))
        service.add_measurement(
            session,
            user_id=author_id,
            new=service.NewMeasurement(
                item_id=item_id,
                measured_on=shift_date(date.fromisoformat(measurement["data"]), reference_date),
                from_percent=Decimal(str(measurement["de"])),
                to_percent=last,
                author_id=ids.person(measurement.get("porId")),
                note=measurement.get("obs"),
            ),
        )
    if real != last:
        service.add_measurement(
            session,
            user_id=author_id,
            new=service.NewMeasurement(
                item_id=item_id,
                measured_on=reference_date,
                from_percent=last,
                to_percent=real,
                author_id=ids.person(source.get("responsavelId")),
                note=LOAD_NOTE,
            ),
        )


def _prototype_progress(source: dict[str, Any]) -> Decimal:
    """The real of the package the prototype showed, from the entries of its criterion."""
    entries = PackageEntries(
        stages=tuple(
            StageLine(
                name=stage["nome"],
                weight=Decimal(str(stage["peso"])),
                percent=Decimal(str(stage["pct"])),
            )
            for stage in source.get("etapas") or []
        ),
        executed=_decimal(source.get("executado")),
        state=source.get("estado"),
        estimated_percent=_decimal(source.get("estimadoPct")),
    )
    return calculations.package_progress(
        kind=source.get("tipo"),
        criterion=source.get("criterio"),
        quantity=_decimal(source.get("quantidade")),
        entries=entries,
    )


def _load_revisions(load: _Load, tree: _Tree) -> None:
    """The revisions and the splits; the weights are frozen only in the revision in force."""
    session, author_id, ids = load.session, load.author_id, load.ids
    reference_date = load.reference_date
    revisions = prototype_collection("eapRevisoes")
    change_ids = governanca.change_ids_by_code(
        session, codes=[item["smRef"] for item in revisions if item.get("smRef")]
    )
    current = _current_numbers(revisions)
    for source in sorted(revisions, key=lambda item: (item["projetoId"], item["revisao"])):
        project_id = ids.project(source["projetoId"])
        service.create_revision(
            session,
            user_id=author_id,
            new=service.NewRevision(
                project_id=project_id,
                number=source["revisao"],
                revised_on=shift_date(date.fromisoformat(source["data"]), reference_date),
                change=source["alteracao"],
                justification=source["justificativa"],
                change_id=change_ids.get(source.get("smRef") or ""),
                approved_by_id=ids.person(source.get("aprovadoPorId")),
                frozen_weights=(
                    _frozen_weights(tree, ids, source)
                    if source["revisao"] == current[source["projetoId"]]
                    else None
                ),
            ),
        )
    _load_splits(load, tree)


def _current_numbers(revisions: list[dict[str, Any]]) -> dict[int, int]:
    numbers: dict[int, int] = {}
    for item in revisions:
        numbers[item["projetoId"]] = max(numbers.get(item["projetoId"], 0), item["revisao"])
    return numbers


def _frozen_weights(tree: _Tree, ids: _RegisterIds, revision: dict[str, Any]) -> dict[int, Decimal]:
    """The weights of the packages in the revision: the current ones, as they stood on its date.

    A split made after the revision was approved moved weight from the planning package to a new
    package, so the revision holds the planning package with the weight it had and not the new one.
    """
    project_id = ids.project(revision["projetoId"])
    weights = {
        code: weight
        for (pid, code), weight in tree.weights.items()
        if pid == project_id and _is_package(code, tree, project_id)
    }
    for split in prototype_collection("eapDesdobramentos"):
        if (
            split["projetoId"] == revision["projetoId"]
            and split["revisao"] == revision["revisao"]
            and split["data"] > revision["data"]
        ):
            weights[split["origem"]] = weights.get(split["origem"], Decimal(0)) + Decimal(
                str(split["peso"])
            )
            weights.pop(split["destino"], None)
    return {tree.items[(project_id, code)]: weight for code, weight in weights.items()}


def _is_package(code: str, tree: _Tree, project_id: int) -> bool:
    """Whether the code is a package: only the packages (three levels of code) carry weight."""
    return (project_id, code) in tree.items and code.count(calculations.CODE_SEPARATOR) == (
        calculations.PACKAGE_LEVEL - 1
    )


def _load_splits(load: _Load, tree: _Tree) -> None:
    session, author_id, ids = load.session, load.author_id, load.ids
    reference_date = load.reference_date
    for source in prototype_collection("eapDesdobramentos"):
        project_id = ids.project(source["projetoId"])
        service.add_split(
            session,
            user_id=author_id,
            new=service.NewSplit(
                project_id=project_id,
                source_item_id=tree.items[(project_id, source["origem"])],
                target_item_id=tree.items[(project_id, source["destino"])],
                revision=source["revisao"],
                split_on=shift_date(date.fromisoformat(source["data"]), reference_date),
                weight=Decimal(str(source["peso"])),
                justification=source["justificativa"],
                by_id=ids.person(source.get("porId")),
            ),
        )
