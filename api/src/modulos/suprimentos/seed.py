"""Parts of the Procurement module in the demonstration load (ISSUE-057/058/059, D6/Q15).

The 17 qualifications of the prototype (``fornecedores``), with their categories, documents and
the situation history, enter through the facade (``core.recording``, inside the caller's
transaction), with the companies of the platform part and the people of the mock. Every date is
shifted by ``shift_date``; on 25/09/2026 (the oracle) nothing moves and the dates of the mock
come out whole. The companies of the Weekly Scheduling (the demonstration adds three) stay
without qualification and show up as "Sem qualificação", as any company of the register does.

The 28 packages of the plan (``pacotes``) enter with the seven acquisition milestones of the
prototype, each with its plan and the forecast and real layers the mock carries; the
``plano.entrega`` of the mock has no place in the model and is left out (DECISION, ISSUE-058).
The EAC item of each package is resolved by the code of the mock through the Financeiro facade;
the codes the mock linked to level-2 items are loaded as they are, since only a new package is
required to be tied to a level-3 item. The gate LLI rides in the package; the codes come from
the project sequence of the mock.

The four processes of the mock (``processos``) enter with their invitees, proposals and
negotiations; the free names outside the register stay in ``nome`` (the prototype accepted
them). The history of each process goes to the audit trail, the entity the facade reads the feed
from. The recommendation and the approval of the mock ride in the columns ISSUE-060 fills. The
PDF of a proposal is not loaded: the demonstration has no files (DIVERGENCIAS, anexo).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core import audit, recording
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service as financeiro
from src.modulos.suprimentos import calculations, service
from src.modulos.suprimentos.models import (
    PackageMilestone,
    ProcessInvitee,
    ProcessNegotiation,
    ProcessProposal,
    PurchasePackage,
    PurchaseProcess,
    Supplier,
    SupplierCategory,
    SupplierDocument,
    SupplierHistory,
)

PART_NAME = "suprimentos-fornecedores"
PACKAGES_PART_NAME = "suprimentos-pacotes"
PROCESSES_PART_NAME = "suprimentos-processos"


@dataclass(frozen=True)
class _Lookups:
    """What the conversion needs to turn ids of the prototype into ids of the database."""

    user: User
    reference_date: date
    companies: Mapping[int, int]
    people: Mapping[int, int]

    def shifted(self, value: str | None) -> date | None:
        """A date of the prototype moved to the reference date of the run."""
        if not value:
            return None
        return shift_date(date.fromisoformat(value), self.reference_date)

    def person(self, mock_id: int | None) -> int | None:
        """The person of the register behind an id of the prototype."""
        return None if mock_id is None else self.people[mock_id]


def load(session: Session, reference_date: date) -> None:
    """Write the qualifications of the prototype, with their history."""
    lookups = _lookups(session, reference_date)
    for source in prototype_collection("fornecedores"):
        _record(session, lookups, source)


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
    ids_by_name = {
        company.name: company.id for company in configuracoes.list_company_summaries(session)
    }
    ids_by_email = {
        person.email.lower(): person.id for person in configuracoes.list_people(session)
    }
    return _Lookups(
        user=user,
        reference_date=reference_date,
        companies={
            company["id"]: ids_by_name[company["nome"]]
            for company in prototype_collection("empresas")
        },
        people={
            person["id"]: ids_by_email[person["email"].lower()]
            for person in prototype_collection("pessoas")
        },
    )


def _record(session: Session, lookups: _Lookups, source: Mapping[str, Any]) -> None:
    supplier = recording.create(
        session,
        user_id=lookups.user.id,
        record=Supplier(
            company_id=lookups.companies[source["empresaId"]],
            situation=source["situacao"],
            validity=lookups.shifted(source.get("validadeQualificacao")),
            observation=source.get("observacao"),
        ),
    )
    for category in source["categorias"]:
        recording.create(
            session,
            user_id=lookups.user.id,
            record=SupplierCategory(supplier_id=supplier.id, category=category),
        )
    for document in source["documentos"]:
        recording.create(
            session,
            user_id=lookups.user.id,
            record=SupplierDocument(
                supplier_id=supplier.id,
                name=document["nome"],
                validity=lookups.shifted(document.get("validade")),
            ),
        )
    for entry in source.get("historico", ()):
        recording.create(
            session,
            user_id=lookups.user.id,
            record=SupplierHistory(
                supplier_id=supplier.id,
                by_id=lookups.person(entry["porId"]),
                on=lookups.shifted(entry["data"]),
                from_situation=entry.get("de"),
                to_situation=entry["para"],
                justification=entry["justificativa"],
            ),
        )


register(PART_NAME, load)


# ── The purchase plan (ISSUE-058) ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _PackageLookups:
    """What the plan load needs to turn ids of the prototype into ids of the database."""

    user: User
    reference_date: date
    projects: Mapping[int, int]
    people: Mapping[int, int]
    disciplines: Mapping[str, int]
    eac_items: Mapping[tuple[int, str], int]

    def shifted(self, value: str | None) -> date | None:
        """A date of the prototype moved to the reference date of the run."""
        return shift_date(date.fromisoformat(value), self.reference_date) if value else None

    def required(self, value: str | None) -> date:
        """A date the mock always carries; without it the load fails loud."""
        shifted = self.shifted(value)
        if shifted is None:
            message = "Data obrigatória ausente no mock dos pacotes."
            raise LookupError(message)
        return shifted


def load_packages(session: Session, reference_date: date) -> None:
    """Write the 28 packages of the prototype with the seven milestones of each."""
    lookups = _package_lookups(session, reference_date)
    for source in prototype_collection("pacotes"):
        _record_package(session, lookups, source)


def _package_lookups(session: Session, reference_date: date) -> _PackageLookups:
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
    real_projects = {project.code: project.id for project in configuracoes.list_projects(session)}
    projects = {
        source["id"]: real_projects[source["codigo"]] for source in prototype_collection("projetos")
    }
    people = {
        source["id"]: person_id
        for source in prototype_collection("pessoas")
        if (person_id := configuracoes.find_person_id_by_email(session, source["email"]))
    }
    disciplines = {
        name: discipline_id
        for discipline_id, name in configuracoes.discipline_names_by_id(session).items()
    }
    eac_items = _eac_items(session, projects)
    return _PackageLookups(
        user=user,
        reference_date=reference_date,
        projects=projects,
        people=people,
        disciplines=disciplines,
        eac_items=eac_items,
    )


def _eac_items(session: Session, projects: Mapping[int, int]) -> dict[tuple[int, str], int]:
    """The id of every EAC item the mock names, by project of the mock and code."""
    items: dict[tuple[int, str], int] = {}
    for mock_project_id, project_id in projects.items():
        codes = [
            source["codigo"]
            for source in prototype_collection("eac")
            if source["projetoId"] == mock_project_id
        ]
        found = financeiro.eac_item_ids_by_code(session, project_id=project_id, codes=codes)
        items.update({(mock_project_id, code): item_id for code, item_id in found.items()})
    return items


def _record_package(session: Session, lookups: _PackageLookups, source: Mapping[str, Any]) -> None:
    gate = source.get("gateLli") or {}
    package = recording.create(
        session,
        user_id=lookups.user.id,
        record=PurchasePackage(
            project_id=lookups.projects[source["projetoId"]],
            eac_item_id=lookups.eac_items[(source["projetoId"], source["eacCodigo"])],
            buyer_id=lookups.people[source["compradorId"]],
            discipline_id=lookups.disciplines.get(source["disciplina"]),
            code=source["codigo"],
            scope=source["escopo"],
            kind=source["tipo"],
            modality=source["modalidade"],
            lli=source["lli"],
            estimate_cents=source["estimativaCentavos"],
            ros=lookups.required(source["ros"]),
            emergency=source.get("emergencial", False),
            gate_lli_date=lookups.shifted(gate.get("data")),
            gate_lli_reference=gate.get("referencia"),
        ),
    )
    _record_milestones(session, lookups, package=package, source=source)


def _record_milestones(
    session: Session,
    lookups: _PackageLookups,
    *,
    package: PurchasePackage,
    source: Mapping[str, Any],
) -> None:
    """The seven acquisition milestones: the plan, the forecast and the real of the mock.

    The ``plano.entrega`` of the prototype is not a milestone of the model and stays out.
    """
    plan = source.get("plano") or {}
    forecast = source.get("previsao") or {}
    real = source.get("real") or {}
    for key in calculations.MILESTONE_KEYS:
        recording.create(
            session,
            user_id=lookups.user.id,
            record=PackageMilestone(
                package_id=package.id,
                milestone=key,
                plan_date=lookups.shifted(plan.get(key)),
                forecast_date=lookups.shifted(forecast.get(key)),
                real_date=lookups.shifted(real.get(key)),
            ),
        )


register(PACKAGES_PART_NAME, load_packages)


# ── The purchase processes (ISSUE-059) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class _ProcessLookups:
    """What the process load needs to turn ids of the prototype into ids of the database."""

    user: User
    reference_date: date
    packages: Mapping[int, int]
    project_of_package: Mapping[int, int]
    people: Mapping[int, int]
    companies: Mapping[int, int]
    companies_by_name: Mapping[str, int]

    def shifted(self, value: str | None) -> date | None:
        """A date of the prototype moved to the reference date of the run."""
        return shift_date(date.fromisoformat(value), self.reference_date) if value else None

    def required(self, value: str | None) -> date:
        """A date the mock always carries; without it the load fails loud."""
        shifted = self.shifted(value)
        if shifted is None:
            message = "Data obrigatória ausente no mock dos processos."
            raise LookupError(message)
        return shifted

    def person(self, mock_id: int | None) -> int | None:
        """The person of the register behind an id of the prototype."""
        return None if mock_id is None else self.people.get(mock_id)

    def company(self, mock_id: int | None) -> int | None:
        """The company of the register behind an id of the prototype."""
        return None if mock_id is None else self.companies.get(mock_id)


def load_processes(session: Session, reference_date: date) -> None:
    """Write the processes of the prototype with their invitees, proposals and negotiations."""
    lookups = _process_lookups(session, reference_date)
    for source in prototype_collection("processos"):
        _record_process(session, lookups, source)


def _process_lookups(session: Session, reference_date: date) -> _ProcessLookups:
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
    real_projects = {project.code: project.id for project in configuracoes.list_projects(session)}
    projects = {
        source["id"]: real_projects[source["codigo"]] for source in prototype_collection("projetos")
    }
    real_packages = {
        (project_id, code): package_id
        for project_id, code, package_id in session.execute(
            select(PurchasePackage.project_id, PurchasePackage.code, PurchasePackage.id)
        )
    }
    packages = {
        source["id"]: real_packages[(projects[source["projetoId"]], source["codigo"])]
        for source in prototype_collection("pacotes")
    }
    companies_by_name = {
        company.name: company.id for company in configuracoes.list_company_summaries(session)
    }
    ids_by_email = {
        person.email.lower(): person.id for person in configuracoes.list_people(session)
    }
    return _ProcessLookups(
        user=user,
        reference_date=reference_date,
        packages=packages,
        project_of_package={
            source["id"]: projects[source["projetoId"]]
            for source in prototype_collection("pacotes")
        },
        people={
            person["id"]: ids_by_email[person["email"].lower()]
            for person in prototype_collection("pessoas")
        },
        companies={
            company["id"]: companies_by_name[company["nome"]]
            for company in prototype_collection("empresas")
        },
        companies_by_name=companies_by_name,
    )


def _record_process(session: Session, lookups: _ProcessLookups, source: Mapping[str, Any]) -> None:
    recommendation = source.get("recomendacao") or {}
    approval = source.get("aprovacao") or {}
    process = recording.create(
        session,
        user_id=lookups.user.id,
        record=PurchaseProcess(
            package_id=lookups.packages[source["pacoteId"]],
            number=source["numero"],
            weight_technical=source["pesoTecnico"],
            weight_commercial=source["pesoComercial"],
            proposals_deadline=lookups.required(source["dataLimitePropostas"]),
            recommendation_on=lookups.shifted(recommendation.get("data")),
            recommendation_company_id=lookups.company(recommendation.get("fornecedorId")),
            recommendation_value_cents=recommendation.get("valorCentavos"),
            recommendation_by_id=lookups.person(recommendation.get("porId")),
            recommendation_justification=recommendation.get("justificativa"),
            approval_on=lookups.shifted(approval.get("data")),
            approval_by_id=lookups.person(approval.get("porId")),
            approval_band=approval.get("alcada"),
            approval_opinion=approval.get("parecer"),
        ),
    )
    for name in source["convidados"]:
        company_id = lookups.companies_by_name.get(name)
        recording.create(
            session,
            user_id=lookups.user.id,
            record=ProcessInvitee(
                process_id=process.id, company_id=company_id, name=None if company_id else name
            ),
        )
    for proposal in source["propostas"]:
        company_id = lookups.company(proposal.get("fornecedorId"))
        recording.create(
            session,
            user_id=lookups.user.id,
            record=ProcessProposal(
                process_id=process.id,
                company_id=company_id,
                name=None if company_id else proposal["fornecedor"],
                received=lookups.required(proposal["recebida"]),
                value_cents=proposal["valorCentavos"],
                deadline_days=proposal["prazoDias"],
                validity=lookups.shifted(proposal.get("validade")),
                technical_score=proposal.get("notaTecnica"),
                technically_approved=proposal.get("tecnicamenteAprovada"),
                deviations=proposal.get("desvios") or None,
            ),
        )
    for negotiation in source.get("negociacoes", ()):
        company_id = lookups.companies_by_name.get(negotiation["fornecedor"])
        recording.create(
            session,
            user_id=lookups.user.id,
            record=ProcessNegotiation(
                process_id=process.id,
                company_id=company_id,
                name=None if company_id else negotiation["fornecedor"],
                on=lookups.required(negotiation["data"]),
                value_cents=negotiation["valorCentavos"],
                observation=negotiation.get("observacao") or None,
            ),
        )
    for entry in source.get("historico", ()):
        audit.append(
            session,
            audit.TrailLine(
                user_id=lookups.user.id,
                entity=service.PROCESS_HISTORY_ENTITY,
                record_id=process.id,
                action=audit.CREATED,
                after={
                    "data": lookups.required(entry["data"]).isoformat(),
                    "etapa": entry["etapa"],
                    "por_id": lookups.person(entry.get("porId")),
                    "texto": entry["texto"],
                },
                project_id=lookups.project_of_package[source["pacoteId"]],
            ),
        )


register(PROCESSES_PART_NAME, load_processes)
