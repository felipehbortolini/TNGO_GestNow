"""Part of the RNC list in the demonstration load (ISSUE-068, D6/Q15).

The 10 reports of the prototype (``rncs``: the six of ``mock-qualidade`` and the four the
portfolio mock adds for the other projects) enter through the facade (``service.record_rnc``),
with the columns the mock already had: situation, disposition, concession, root cause,
deadline, effectiveness and cost. Every date is shifted by ``shift_date``; on 25/09/2026 (the
oracle) nothing moves and the numbers of the prototype come out whole: 4 open reports in the
project 1 (0002, 0004, 0005 and 0006), 0004 with the treatment deadline overdue.

The corrective actions with origin ``RNC`` are seeded by the Central de Ações, whose part runs
before this one; the numbering of each project continues after the highest loaded number, so
the first report a person opens does not collide with the demonstration
(``numbering.start_after``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core import numbering
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import lessons_service
from src.modulos.qualidade import service
from src.modulos.qualidade.models import Rnc

PART_NAME = "qualidade-rnc"
HISTORY_HOUR = time(9, 0)


@dataclass(frozen=True)
class _Lookups:
    """What the conversion needs to turn ids of the prototype into ids of the database."""

    user: User
    reference_date: date
    people: Mapping[int, int]
    projects: Mapping[int, int]
    companies_by_id: Mapping[int, str]
    companies: Mapping[str, int]
    disciplines: Mapping[str, int]

    def shifted(self, value: str | None) -> date:
        """A date of the prototype moved to the reference date of the run."""
        if not value:
            message = "Data obrigatória ausente na RNC do protótipo."
            raise LookupError(message)
        return shift_date(date.fromisoformat(value), self.reference_date)

    def maybe_shifted(self, value: str | None) -> date | None:
        """A date of the prototype moved to the reference date of the run; empty stays empty."""
        return None if not value else self.shifted(value)

    def moment(self, value: str | None) -> datetime | None:
        """A date of the prototype as a moment of the day, in UTC."""
        day = self.maybe_shifted(value)
        return None if day is None else datetime.combine(day, HISTORY_HOUR, tzinfo=UTC)

    def person(self, mock_id: int | None) -> int | None:
        """The person of the register behind an id of the prototype."""
        return None if mock_id is None else self.people[mock_id]


def load(session: Session, reference_date: date) -> None:
    """Write the reports of the prototype and continue the numbering of each project."""
    lookups = _lookups(session, reference_date)
    for source in prototype_collection("rncs"):
        _record(session, lookups, source)
    _start_numbering(session, lookups)


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
        companies_by_id={
            company["id"]: company["nome"] for company in prototype_collection("empresas")
        },
        companies={item.name: item.id for item in configuracoes.list_company_options(session)},
        disciplines={
            name: discipline_id
            for discipline_id, name in configuracoes.discipline_names_by_id(session).items()
        },
    )


def _record(session: Session, lookups: _Lookups, source: Mapping[str, Any]) -> None:
    rnc = _rnc_of(session, lookups, source)
    service.record_rnc(
        session,
        user=lookups.user,
        rnc=rnc,
        history_text=(
            f"RNC aberta ({rnc.origin}{(f' {rnc.origin_ref}' if rnc.origin_ref else '')}). "
            f"Contenção: {rnc.containment}."
        ),
        moment=lookups.moment(source["data"]),
    )


def _rnc_of(session: Session, lookups: _Lookups, source: Mapping[str, Any]) -> Rnc:
    """One report of the mock as the table keeps it: identification, analysis and effectiveness."""
    concession = source.get("concessao") or {}
    effectiveness = source.get("eficacia") or {}
    company = lookups.companies_by_id[source["empresaId"]]
    return Rnc(
        project_id=lookups.projects[source["projetoId"]],
        discipline_id=lookups.disciplines[source["disciplina"]],
        company_id=lookups.companies[company],
        responsible_id=lookups.person(source.get("responsavelId")),
        opened_by_id=_opened_by(lookups, source.get("abertaPorId")),
        verified_by_id=lookups.person(effectiveness.get("porId")),
        lesson_id=_lesson_id(session, source.get("licaoRef")),
        code=source["codigo"],
        rnc_date=lookups.shifted(source["data"]),
        origin=source["origem"],
        origin_ref=source.get("origemRef"),
        description=source["descricao"],
        severity=source["severidade"],
        containment=source["contencao"],
        disposition=source.get("disposicao"),
        concession_reference=concession.get("referencia"),
        concession_date=lookups.maybe_shifted(concession.get("data")),
        method=source.get("metodo"),
        root_cause=source.get("causaRaiz"),
        deadline=lookups.shifted(source["prazo"]),
        closing_date=lookups.maybe_shifted(source.get("encerramento")),
        situation=source["situacao"],
        cost_cents=source.get("custoNaoQualidadeCentavos") or 0,
        verification_expected=lookups.maybe_shifted(source.get("verificacaoPrevista")),
        effectiveness_date=lookups.maybe_shifted(effectiveness.get("data")),
        effectiveness=effectiveness.get("eficaz") if effectiveness else None,
        effectiveness_text=effectiveness.get("texto") if effectiveness else None,
    )


def _opened_by(lookups: _Lookups, mock_id: int | None) -> int:
    person = lookups.person(mock_id)
    if person is None:
        message = f"A pessoa {mock_id} da abertura da RNC não está no mock."
        raise LookupError(message)
    return person


def _lesson_id(session: Session, code: str | None) -> int | None:
    if not code:
        return None
    found = lessons_service.lesson_id_by_code(session, code)
    if found is None:
        message = f"Lição do protótipo não carregada: {code}."
        raise LookupError(message)
    return found


def _start_numbering(session: Session, lookups: _Lookups) -> None:
    """Continue the series of each project after the highest loaded number."""
    for project_id in set(lookups.projects.values()):
        project = configuracoes.find_project(session, project_id)
        if project is None:
            continue
        codes: Sequence[str] = session.scalars(
            select(Rnc.code).where(Rnc.project_id == project_id)
        ).all()
        suffixes = [code.rpartition("-")[2] for code in codes]
        last = max((int(text) for text in suffixes if text.isdigit()), default=0)
        if last:
            numbering.start_after(session, project=project, kind="rnc", last_number=last)


register(PART_NAME, load)
