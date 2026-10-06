"""Part of the Central de Ações in the demonstration load (ISSUE-019, D6/Q15).

The 60 actions of the prototype (``acoes``) and the actions the prototype derived from the Punch
list (one per item that is not cancelled, ``punch``) enter through the single seam
(``service.create_action``), with the history they had: the replans with their justifications and
the completion date. Every date is shifted by ``shift_date``; on 25/09/2026 (the oracle) nothing
moves and the numbers of the prototype come out whole.

An Ata action has no reference in the mock: the prototype reads it from the minutes, so the
reference here is the number of the ata (``atas``). ``acao.ata_id`` keeps the id the prototype
gave the minutes: the minutes arrive with ISSUE-021, which seeds them with the same ids before it
adds the foreign key.

The Punch list actions are created here, not by the module of the Punch list: the prototype
derived them in the Central (``acaoDoPunch``), one for one, with the status in step. The Punch
list slice must keep them in step (``service.close_from_origin``) and never create them again.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.central_acoes import service
from src.modulos.central_acoes.calculations import ACTION
from src.modulos.central_acoes.validation import NewAction, ReplanEntry
from src.modulos.configuracoes import service as configuracoes

PART_NAME = "central_acoes"
PUNCH_ORIGIN = "Punch list"
PUNCH_CANCELLED = "Cancelado"
PUNCH_CLOSED = "Fechado"
ATA_ORIGIN = "Ata"


@dataclass(frozen=True)
class _Lookups:
    """What the conversion needs to turn ids of the prototype into ids of the database."""

    user: User
    reference_date: date
    people: Mapping[int, int]
    projects: Mapping[int, int]
    atas: Mapping[int, str]
    systems: Mapping[int, str]

    def shifted(self, value: str | None) -> date | None:
        """A date of the prototype moved to the reference date of the run."""
        if not value:
            return None
        return shift_date(date.fromisoformat(value), self.reference_date)

    def person(self, mock_id: int) -> int:
        """The person of the register behind an id of the prototype; unknown fails loud."""
        return self.people[mock_id]


def load(session: Session, reference_date: date) -> None:
    """Write the actions of the prototype and the ones derived from the Punch list."""
    lookups = _lookups(session, reference_date)
    for source in prototype_collection("acoes"):
        _create(session, lookups, _action_of(lookups, source))
    for item in prototype_collection("punch"):
        if item["situacao"] != PUNCH_CANCELLED:
            _create(session, lookups, _punch_action_of(lookups, item))


def _create(session: Session, lookups: _Lookups, new: NewAction) -> None:
    service.create_action(
        session, user=lookups.user, new=new, reference_date=lookups.reference_date
    )


def _lookups(session: Session, reference_date: date) -> _Lookups:
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if access is None:
        message = f"O Admin da demonstração ({ADMIN_EMAIL}) não está no cadastro."
        raise LookupError(message)
    user = User(
        id=access.id,
        person_id=access.person_id,
        name=access.name,
        email=access.email,
        general_profile=GeneralProfile(access.general_profile),
        bond=Bond(access.bond),
        company_id=access.company_id,
    )
    ids_by_email = {
        person.email.lower(): person.id for person in configuracoes.list_people(session)
    }
    ids_by_code = {project.code: project.id for project in configuracoes.list_projects(session)}
    return _Lookups(
        user=user,
        reference_date=reference_date,
        people={
            person["id"]: ids_by_email[person["email"].lower()]
            for person in prototype_collection("pessoas")
        },
        projects={
            project["id"]: ids_by_code[project["codigo"]]
            for project in prototype_collection("projetos")
        },
        atas={ata["id"]: ata["numero"] for ata in prototype_collection("atas")},
        systems={
            system["id"]: f"{system['codigo']} {system['nome']}"
            for system in prototype_collection("sistemas")
        },
    )


def _action_of(lookups: _Lookups, source: Mapping[str, Any]) -> NewAction:
    """One action of the mock as the seam receives it, with its replans and its completion."""
    contribution = source.get("contribuicao") or {}
    ata_id = source.get("ataId")
    origin_ref = source.get("origemRef") or (lookups.atas[ata_id] if ata_id else "")
    return NewAction(
        project_id=lookups.projects[source["projetoId"]],
        origin=source["origem"],
        origin_ref=origin_ref,
        subject=source["assunto"],
        requester_id=lookups.person(source["solicitanteId"]),
        responsible_id=lookups.person(source["responsavelId"]),
        planned_date=lookups.shifted(source.get("prevista")),
        kind=source["tipo"],
        description=source.get("descricao"),
        group=source.get("grupo"),
        item=source.get("item"),
        ata_id=ata_id,
        contributes_probability=bool(contribution.get("probabilidade")),
        contributes_impact=bool(contribution.get("impacto")),
        completed_on=lookups.shifted(source.get("conclusao")),
        replans=_replans_of(lookups, source.get("replanejamentos") or ()),
    )


def _replans_of(lookups: _Lookups, replans: Sequence[Mapping[str, Any]]) -> tuple[ReplanEntry, ...]:
    entries: list[ReplanEntry] = []
    for replan in replans:
        registered_on = lookups.shifted(replan["data"])
        from_date = lookups.shifted(replan["de"])
        to_date = lookups.shifted(replan["para"])
        if registered_on is None or from_date is None or to_date is None:
            message = "Replanejamento do protótipo sem alguma das três datas."
            raise ValueError(message)
        entries.append(
            ReplanEntry(
                author_id=lookups.person(replan["porId"]),
                registered_on=registered_on,
                from_date=from_date,
                to_date=to_date,
                justification=replan["justificativa"],
            )
        )
    return tuple(entries)


def _punch_action_of(lookups: _Lookups, item: Mapping[str, Any]) -> NewAction:
    """The action the prototype derived from a Punch list item (``acaoDoPunch``), one for one."""
    system = lookups.systems.get(item["sistemaId"], "")
    tag = f" · {item['tag']}" if item.get("tag") else ""
    description = f"Sistema {system}{tag} · categoria {item['categoria']} · {item['situacao']}"
    closed_on = (
        lookups.shifted(item.get("fechamento")) if item["situacao"] == PUNCH_CLOSED else None
    )
    return NewAction(
        project_id=lookups.projects[item["projetoId"]],
        origin=PUNCH_ORIGIN,
        origin_ref=item["codigo"],
        subject=item["descricao"],
        requester_id=lookups.person(item["identificadoPorId"]),
        responsible_id=lookups.person(item["responsavelId"]),
        planned_date=lookups.shifted(item["prazo"]),
        kind=ACTION,
        description=description,
        group=system,
        completed_on=closed_on,
    )


register(PART_NAME, load)
