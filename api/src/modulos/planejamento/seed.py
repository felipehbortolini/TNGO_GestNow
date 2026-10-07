"""Parte do módulo Planejamento na carga de demonstração (D6, ISSUE-008).

Cada issue do módulo acrescenta aqui a sua parte, como uma função chamada por ``load``:
o 6WLA (ISSUE-045) grava as atividades, as semanas e as restrições do protótipo
(``lookahead``) e o Relato do período (ISSUE-044) grava os relatos (``seed_relato``). Os cadastros que o protótipo numera (projeto, empresa, pessoa) são
achados pela chave de negócio (código, nome), porque os ids do banco não são os do mock.
As datas das restrições andam com ``shift_date``; o início do horizonte não é gravado,
sai do calendário (``calculations.lookahead_window_start``).

A EAP (ISSUE-036) é a parte ``planejamento-eap``: a árvore de níveis 1 a 3 do mock (pai pelo
código), as etapas dos pacotes de Etapas, as medições, as revisões e o desdobramento. Ela roda
depois de Financeiro e Governança, porque o item aponta o item da EAC pelo ``eacCodigo`` e a
revisão aponta a SM pelo ``smRef``, e as duas fachadas são lidas, nunca as tabelas alheias (D9).
As revisões congelam os pesos correntes de todos os pacotes do projeto; o mock conta 35 na Rev 0
e 37 na Rev 2 do projeto 1 enquanto a EAP corrente tem 38 pacotes, porque o mock não guarda o
histórico de pesos — o vigente vem do próprio item e o número de pacotes da revisão sai dos
pesos congelados (D5b). As datas andam com ``shift_date``, como nas demais partes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.core import recording
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import seed_relato, service
from src.modulos.planejamento.models import (
    EapBreakdown,
    EapItem,
    EapItemStep,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
)

PART_NAME = "planejamento"
EAP_PART_NAME = "planejamento-eap"
ADMIN_PROFILE = "Admin"


def load(session: Session, reference_date: date) -> None:
    """Write the part of the Planning module, inside the caller's transaction."""
    _load_lookahead(session, reference_date)
    seed_relato.load_reports(session, reference_date)


def _load_lookahead(session: Session, reference_date: date) -> None:
    """The 6WLA of the prototype: ``lookahead`` with its weeks and restrictions."""
    author = _author(session)
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


def _author(session: Session) -> configuracoes.CollaboratorAccess:
    """O Admin da demonstração, autor dos registros que a carga grava."""
    return next(
        item
        for item in configuracoes.list_active_access(session)
        if item.general_profile == ADMIN_PROFILE
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


# ── EAP: árvore, revisões e desdobramento (ISSUE-036) ────────────────────


@dataclass(frozen=True)
class _EapLoad:
    """O que toda parte da EAP carrega: o autor, os ids resolvidos e a data da carga."""

    author_id: int
    ids: _RegisterIds
    reference_date: date


def load_eap(session: Session, reference_date: date) -> None:
    """Grava a EAP do protótipo, dentro da transação de quem chama.

    A árvore vem do mock com o pai pelo código; as etapas, as medições, as revisões e o
    desdobramento vêm nas coleções próprias. O item da EAC e a SM das revisões são achados
    pelas fachadas do Financeiro e da Governança (D9), que já rodaram.
    """
    author = _author(session)
    load = _EapLoad(
        author_id=author.id,
        ids=_RegisterIds.read(session),
        reference_date=reference_date,
    )
    items = _load_eap_items(session, load)
    _load_eap_revisions(session, load, items=items)
    _load_eap_breakdowns(session, load, items=items)


def _load_eap_items(session: Session, load: _EapLoad) -> dict[tuple[int, str], EapItem]:
    """Grava a árvore inteira e devolve cada item pelo projeto e código."""
    ids = load.ids
    units = {item.code: item.id for item in configuracoes.list_measure_units(session)}
    eac_ids = _eac_ids(session, ids=ids)
    created: dict[tuple[int, str], EapItem] = {}
    sources = sorted(
        prototype_collection("eap"),
        key=lambda source: (source["projetoId"], _code_key(source["codigo"])),
    )
    for source in sources:
        project_id = ids.project(source["projetoId"])
        parent = created.get((project_id, _parent_code(source["codigo"])))
        item = recording.create(
            session,
            user_id=load.author_id,
            record=EapItem(
                project_id=project_id,
                parent_id=None if parent is None else parent.id,
                eac_item_id=eac_ids.get((source["projetoId"], source.get("eacCodigo") or "")),
                unit_id=units.get(source.get("unidade") or ""),
                company_id=ids.company(source.get("empresaId")),
                owner_id=ids.person(source.get("responsavelId")),
                code=source["codigo"],
                description=source["descricao"],
                level=source["nivel"],
                kind=source.get("tipo"),
                criterion=source.get("criterio"),
                model=source.get("modelo"),
                quantity=_decimal_or_none(source.get("quantidade")),
                executed=_decimal_or_none(source.get("executado")),
                state=source.get("estado"),
                estimated_pct=_decimal_or_none(source.get("estimadoPct")),
                weight=_decimal_or_none(source.get("peso")),
                predicted=_decimal_or_none(source.get("previsto")),
                start=_shifted_date(source.get("inicio"), load.reference_date),
                finish=_shifted_date(source.get("termino"), load.reference_date),
                deliverable=source.get("entregavel"),
                acceptance=source.get("aceitacao"),
            ),
        )
        created[(project_id, source["codigo"])] = item
        _load_eap_steps(session, item=item, source=source)
        _load_eap_measurements(session, load, item=item, source=source)
    session.flush()
    return created


def _load_eap_steps(session: Session, *, item: EapItem, source: dict[str, Any]) -> None:
    """As etapas do critério Etapas, na ordem do mock, com o percentual corrente."""
    for order, step in enumerate(source.get("etapas") or (), start=1):
        session.add(
            EapItemStep(
                item_id=item.id,
                order=order,
                name=step["nome"],
                weight=Decimal(str(step["peso"])),
                pct=Decimal(str(step["pct"])),
            )
        )


def _load_eap_measurements(
    session: Session, load: _EapLoad, *, item: EapItem, source: dict[str, Any]
) -> None:
    """As medições do pacote, com a data deslocada, como fatos imutáveis."""
    for measurement in source.get("medicoes") or []:
        recording.create(
            session,
            user_id=load.author_id,
            record=EapMeasurement(
                item_id=item.id,
                author_id=load.ids.person(measurement["porId"]) or load.author_id,
                measured_on=shift_date(
                    date.fromisoformat(measurement["data"]), load.reference_date
                ),
                from_pct=Decimal(str(measurement["de"])),
                to_pct=Decimal(str(measurement["para"])),
                note=measurement.get("obs"),
            ),
        )


def _load_eap_revisions(
    session: Session, load: _EapLoad, *, items: dict[tuple[int, str], EapItem]
) -> None:
    """As revisões do mock, cada uma congelando os pesos correntes dos pacotes do projeto."""
    from src.modulos.governanca import service as governanca

    ids = load.ids
    changes = governanca.change_ids_by_code(
        session,
        codes=[
            source["smRef"] for source in prototype_collection("eapRevisoes") if source.get("smRef")
        ],
    )
    packages = _packages_by_project(items)
    for source in prototype_collection("eapRevisoes"):
        project_id = ids.project(source["projetoId"])
        revision = recording.create(
            session,
            user_id=load.author_id,
            record=EapRevision(
                project_id=project_id,
                change_id=changes.get(source.get("smRef") or ""),
                approved_by_id=ids.person(source["aprovadoPorId"]) or load.author_id,
                revision=source["revisao"],
                revision_date=shift_date(date.fromisoformat(source["data"]), load.reference_date),
                alteration=source["alteracao"],
                justification=source["justificativa"],
            ),
        )
        session.add_all(
            EapRevisionItem(
                revision_id=revision.id,
                item_id=item.id,
                weight=item.weight or Decimal(0),
            )
            for item in packages.get(project_id, ())
        )
        session.flush()


def _load_eap_breakdowns(
    session: Session, load: _EapLoad, *, items: dict[tuple[int, str], EapItem]
) -> None:
    """O desdobramento do mock: do pacote de planejamento para o pacote de trabalho."""
    ids = load.ids
    for source in prototype_collection("eapDesdobramentos"):
        project_id = ids.project(source["projetoId"])
        recording.create(
            session,
            user_id=load.author_id,
            record=EapBreakdown(
                project_id=project_id,
                source_item_id=items[(project_id, source["origem"])].id,
                target_item_id=items[(project_id, source["destino"])].id,
                by_id=ids.person(source["porId"]) or load.author_id,
                revision=source["revisao"],
                applied_on=shift_date(date.fromisoformat(source["data"]), load.reference_date),
                weight=Decimal(str(source["peso"])),
                justification=source["justificativa"],
            ),
        )


def _packages_by_project(
    items: dict[tuple[int, str], EapItem],
) -> dict[int, tuple[EapItem, ...]]:
    """Os pacotes (nível 3) de cada projeto, na ordem em que a árvore os gravou."""
    grouped: dict[int, list[EapItem]] = {}
    for (project_id, _code), item in items.items():
        if item.level == service.LEVEL_PACKAGE:
            grouped.setdefault(project_id, []).append(item)
    return {project_id: tuple(group) for project_id, group in grouped.items()}


def _eac_ids(session: Session, *, ids: _RegisterIds) -> dict[tuple[int, str], int]:
    """O id de cada item da EAC que o mock aponta, pelo projeto e código (fachada do Financeiro)."""
    from src.modulos.financeiro import service as financeiro

    eac: dict[tuple[int, str], int] = {}
    sources = prototype_collection("eap")
    for mock_project_id in sorted({source["projetoId"] for source in sources}):
        codes = [
            source["eacCodigo"]
            for source in sources
            if source["projetoId"] == mock_project_id and source.get("eacCodigo")
        ]
        found = financeiro.eac_item_ids_by_code(
            session, project_id=ids.project(mock_project_id), codes=codes
        )
        eac.update({(mock_project_id, code): item_id for code, item_id in found.items()})
    return eac


def _parent_code(code: str) -> str:
    return code.rsplit(".", maxsplit=1)[0]


def _code_key(code: str) -> tuple[int, ...]:
    return tuple(int(part) for part in code.split("."))


def _decimal_or_none(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _shifted_date(value: str | None, reference_date: date) -> date | None:
    return None if value is None else shift_date(date.fromisoformat(value), reference_date)


register(PART_NAME, load)
register(EAP_PART_NAME, load_eap)
