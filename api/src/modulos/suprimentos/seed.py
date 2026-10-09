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

The 14 orders of the mock (``pedidos``, from the suprimentos and the portfolio mocks) enter with
their six manufacturing milestones, tied to the real package and company; the ``recebimento`` of
the mock is loaded by its own part (``suprimentos-diligenciamento``, ISSUE-061) and no new
diligence action is created by the load: the ones the mock carries already come in the
``central_acoes`` part. The orders continue the numbering series on emission (ISSUE-060).

The receipts of the orders the mock already delivered (PED-2026-0003, 0006 and 0008) enter with
their date, check, damages and pending items (``suprimentos-diligenciamento``); the evidence is
not loaded: the demonstration has no files (DIVERGENCIAS, anexo). The OTD and the slack are
calculated on reading from the delivery already loaded with the orders.
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
from src.modulos.financeiro.models import Contract
from src.modulos.suprimentos import calculations, service
from src.modulos.suprimentos.models import (
    DeliveryReceipt,
    PackageMilestone,
    ProcessInvitee,
    ProcessNegotiation,
    ProcessProposal,
    PurchaseOrder,
    PurchaseOrderMilestone,
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
ORDERS_PART_NAME = "suprimentos-pedidos"
DILIGENCE_PART_NAME = "suprimentos-diligenciamento"
PANEL_PART_NAME = "suprimentos-painel"


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


# ── The purchase orders (ISSUE-060) ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _OrderLookups:
    """What the order load needs to turn ids of the prototype into ids of the database."""

    user: User
    reference_date: date
    packages: Mapping[int, int]
    project_of_package: Mapping[int, int]
    companies: Mapping[int, int]

    def shifted(self, value: str | None) -> date | None:
        """A date of the prototype moved to the reference date of the run."""
        return shift_date(date.fromisoformat(value), self.reference_date) if value else None

    def required(self, value: str | None) -> date:
        """A date the mock always carries; without it the load fails loud."""
        shifted = self.shifted(value)
        if shifted is None:
            message = "Data obrigatória ausente no mock dos pedidos."
            raise LookupError(message)
        return shifted


def load_orders(session: Session, reference_date: date) -> None:
    """Write the orders of the prototype with their six manufacturing milestones."""
    lookups = _order_lookups(session, reference_date)
    for source in prototype_collection("pedidos"):
        _record_order(session, lookups, source)


def _order_lookups(session: Session, reference_date: date) -> _OrderLookups:
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
    real_companies = {
        company.name: company.id for company in configuracoes.list_company_summaries(session)
    }
    return _OrderLookups(
        user=user,
        reference_date=reference_date,
        packages={
            source["id"]: real_packages[(projects[source["projetoId"]], source["codigo"])]
            for source in prototype_collection("pacotes")
        },
        project_of_package={
            source["id"]: projects[source["projetoId"]]
            for source in prototype_collection("pacotes")
        },
        companies={
            company["id"]: real_companies[company["nome"]]
            for company in prototype_collection("empresas")
        },
    )


def _record_order(session: Session, lookups: _OrderLookups, source: Mapping[str, Any]) -> None:
    package_id = lookups.packages[source["pacoteId"]]
    order = recording.create(
        session,
        user_id=lookups.user.id,
        record=PurchaseOrder(
            project_id=lookups.project_of_package[source["pacoteId"]],
            package_id=package_id,
            company_id=lookups.companies[source["fornecedorId"]],
            number=source["numero"],
            description=source["descricao"],
            value_cents=int(source["valorCentavos"]),
            lli=bool(source["lli"]),
            emission=lookups.required(source["emissao"]),
            contractual_date=lookups.required(source["dataContratual"]),
            forecast=lookups.required(source["previsao"]),
            ros=lookups.required(source["ros"]),
            delivery=lookups.shifted(source.get("entrega")),
        ),
    )
    for position, milestone in enumerate(source["marcos"], start=1):
        recording.create(
            session,
            user_id=lookups.user.id,
            record=PurchaseOrderMilestone(
                order_id=order.id,
                position=position,
                name=milestone["nome"],
                baseline_date=lookups.required(milestone["lb"]),
                forecast_date=lookups.required(milestone["previsao"]),
                real_date=lookups.shifted(milestone.get("realizada")),
            ),
        )


register(ORDERS_PART_NAME, load_orders)


# ── The receipts of the delivered orders (ISSUE-061) ─────────────────────────────────────────


def load_receipts(session: Session, reference_date: date) -> None:
    """Write the receipt of every order the mock already delivered, with its pending items."""
    lookups = _order_lookups(session, reference_date)
    for source in prototype_collection("pedidos"):
        receipt = source.get("recebimento")
        if receipt:
            _record_receipt(session, lookups, source, receipt)


def _record_receipt(
    session: Session,
    lookups: _OrderLookups,
    source: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    order = session.scalars(
        select(PurchaseOrder).where(PurchaseOrder.number == source["numero"])
    ).one()
    recording.create(
        session,
        user_id=lookups.user.id,
        record=DeliveryReceipt(
            order_id=order.id,
            on=lookups.required(receipt["data"]),
            checked=bool(receipt.get("conferido")),
            damaged=bool(receipt.get("avarias")),
            damage_description=receipt.get("descricaoAvarias") or None,
            pending=receipt.get("pendencias") or None,
        ),
    )


register(DILIGENCE_PART_NAME, load_receipts)


# ── The panel (ISSUE-063) ────────────────────────────────────────────────────────────────────


def load_panel(session: Session, reference_date: date) -> None:
    """Fecha a ligação dos contratos com o pacote e carrega o resultado comercial do protótipo.

    O mock dos contratos aponta o ``pacoteCompra`` de cada contrato nascido de um pacote (PC-01,
    PC-02 e PC-13 do projeto 1, entre outros); a parte do Financeiro deixa a ligação nula porque
    a ``pacote_compra`` nasce depois dela, e é aqui que ela se fecha. Os agregados comerciais do
    processo (a primeira proposta vencedora, as propostas válidas e o fornecedor único) vêm do
    mock dos pacotes: o painel prefere o processo vivo quando existe e cai nestas colunas para os
    pacotes que a carga trouxe (DECISION, ISSUE-063).
    """
    del reference_date
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if access is None:
        message = f"O Admin da demonstração ({ADMIN_EMAIL}) não está no cadastro."
        raise LookupError(message)
    real_projects = {project.code: project.id for project in configuracoes.list_projects(session)}
    projects = {
        source["id"]: real_projects[source["codigo"]] for source in prototype_collection("projetos")
    }
    packages = {
        (package.project_id, package.code): package
        for package in session.scalars(select(PurchasePackage))
    }
    _link_panel_contracts(session, user_id=access.id, projects=projects, packages=packages)
    _load_panel_outcomes(session, user_id=access.id, projects=projects, packages=packages)


def _link_panel_contracts(
    session: Session,
    *,
    user_id: int,
    projects: Mapping[int, int],
    packages: Mapping[tuple[int, str], PurchasePackage],
) -> None:
    """Aponta cada contrato do mock ao pacote que o originou (``pacoteCompra``)."""
    contracts = {contract.number: contract for contract in session.scalars(select(Contract))}
    for source in prototype_collection("contratos"):
        code = source.get("pacoteCompra")
        if not code:
            continue
        contract = contracts.get(source["numero"])
        package = packages.get((projects[source["projetoId"]], code))
        if contract is None or package is None or contract.purchase_package_id == package.id:
            continue
        recording.update(
            session,
            user_id=user_id,
            record=contract,
            changes={"purchase_package_id": package.id},
            version=contract.version,
        )


def _load_panel_outcomes(
    session: Session,
    *,
    user_id: int,
    projects: Mapping[int, int],
    packages: Mapping[tuple[int, str], PurchasePackage],
) -> None:
    """Grava a primeira proposta, as propostas válidas e o fornecedor único do mock."""
    for source in prototype_collection("pacotes"):
        package = packages.get((projects[source["projetoId"]], source["codigo"]))
        if package is None:
            continue
        changes = _panel_outcome_changes(package, source)
        if changes:
            recording.update(
                session,
                user_id=user_id,
                record=package,
                changes=changes,
                version=package.version,
            )


def _panel_outcome_changes(
    package: PurchasePackage, source: Mapping[str, Any]
) -> dict[str, object]:
    """Os campos do resultado comercial que o mock muda no pacote, sem repetir o que já está lá."""
    changes: dict[str, object] = {}
    first = source.get("primeiraPropostaCentavos")
    if first is not None and package.first_proposal_cents != int(first):
        changes["first_proposal_cents"] = int(first)
    if "propostasValidas" in source:
        valid = int(source["propostasValidas"])
        if package.valid_proposals != valid:
            changes["valid_proposals"] = valid
        single = bool(source.get("fornecedorUnico"))
        if package.single_supplier != single:
            changes["single_supplier"] = single
    return changes


register(PANEL_PART_NAME, load_panel)
