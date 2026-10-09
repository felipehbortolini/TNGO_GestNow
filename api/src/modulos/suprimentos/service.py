"""Business facade of the Procurement module: suppliers and the purchase plan (ISSUE-057/058).

The supplier register is global: ``fornecedor`` is the qualification of a company of the
Configurações register, with its categories, its documents with validity and the history of
situation changes. Documents in day, the performance and the contracted value are never stored:
they are calculated on every read from the documents, from the Financeiro facade
(``company_performance``) and from the reference date the caller hands in.

Writes go through ``core.recording`` (trail, version and transaction together, D5): the
qualification, its documents (each with its own ``versao``) and the history facts. A change of
situation requires a justification, and Restrito and Bloqueado require the reason; the history
row is a fact and records de/para/author/justificativa.

The purchase plan: ``list_packages``/``find_package`` read the package with its seven acquisition
milestones and calculate stage, slack and adjudication deviation on every query; ``create_package``
and ``update_package`` write the full plan before the requisition, and ``change_package`` writes
the four fields that may still change after it, with the justification. The saldo a comprometer
of the EAC item is read from the Financeiro on every query (D9). The history of the package
travels in the audit trail, as the ISSUE-004 decision determines; the future fields
(adjudicated, supplier, saving) are empty until the process (ISSUE-059) and the order
(ISSUE-061) exist (DECISION, ISSUE-058).

The final evaluation of a contract (ISSUE-034) updates the existing qualification through
``apply_final_evaluation``, registered as a listener of the Financeiro (D9): class A and B
qualify, C restricts and D blocks, inside the same transaction of the evaluation.

The purchase process (ISSUE-059): ``list_processes`` and ``find_process`` read the RFx of each
package with its invitees, proposals, negotiations, history and everything calculated (stage,
scores, ranking, approval band); ``start_requisition``, ``issue_rfx``, ``register_proposal``,
``close_receipt``, ``equalize_technically``, ``equalize_commercially`` and
``register_negotiation`` run the actions, each one writing the real date of the corresponding
milestone of the package and a line of the process history in the audit trail. The proposal's
PDF is a real attachment (D5a), registered here as the origin type ``processo_proposta``.

The close of the flow (ISSUE-060): ``recommend_award`` fills the recommendation of the process
(only a technically approved proposal of a registered supplier; another one, or one that is not
the best score or not qualified, demands a justification), ``return_recommendation`` sends it
back to negotiation with the reason, ``approve_award`` writes the approval of the band with the
segregation of duties and the limit of the saldo a comprometer of the EAC item (read from the
Financeiro, D9), and ``emit_order_or_contract`` creates the order (equipment/material) or the
contract through the Financeiro facade (service/EPC), commits the value in ``custo_erp`` and
opens the diligence action in the Central when the order is born with negative slack, everything
in the caller's transaction.

The expediting and the receipt (ISSUE-061): ``list_orders``/``find_order`` read each order with
its six manufacturing milestones, the receipt and the feed, and calculate the situation, the
slack against the ROS and the OTD on every query; ``update_order_milestone`` realizes a milestone
or reprograms a forecast (with the cascade), ``register_receipt`` records the delivery at the
site with its evidence (a real attachment, D5a), ``open_diligence_action`` opens the action of a
critical order by hand and the ERP import (``apply_order_import_row``) writes one milestone per
line. Every path that meets a critical order calls ``_open_diligence_action``, which never opens
a second action for the same order. The OTD of the orders feeds the performance of the supplier
(ISSUE-057), read by ``_universe`` from the orders of the scope.

The map of purchases (ISSUE-062): ``list_mas``/``find_mas_package`` read each package with its
twelve milestones in the two halves of the map: the seven acquisition ones come from the plan
(ISSUE-058), the five of manufacturing and delivery from the order (ISSUE-061) or estimated by
the emission shares when the package still has no order; the process (ISSUE-059) gives the number
and the recommended value. The situation of each milestone, the line situation, the progress
weighted by the value of the package and its index are calculated on every query, never stored:
the map is a view of the plan, the processes and the expediting.

The panel (ISSUE-063): ``list_panel`` composes the plan, the map and the orders into the nine
indicators of the prototype (adherence, cycle, the two savings, competitiveness, OTD, critical
orders, emergency purchases and committed against budget), the three accumulated curves
(contracting, saving and the advancement of the map) and the orders by slack. The adjudicated
value of a package is the order's, the recommendation's or the contract's that was born from it
(service/EPC, read from the Financeiro, D9); the winner's first proposal, the valid proposals and
the single-supplier flag prefer the live process and fall back to the columns the historical load
brought (ISSUE-063).

Public API (stable; a change needs an issue of its own): ``list_suppliers``, ``find_supplier``,
``create_supplier``, ``save_qualification``, ``apply_final_evaluation``, ``list_packages``,
``find_package``, ``package_options``, ``create_package``, ``update_package``,
``change_package``, ``list_processes``, ``find_process``, ``process_options``,
``planned_packages``, ``start_requisition``, ``issue_rfx``, ``register_proposal``,
``close_receipt``, ``equalize_technically``, ``equalize_commercially``,
``register_negotiation``, ``recommend_award``, ``return_recommendation``, ``approve_award``,
``emit_order_or_contract``, ``list_orders``, ``find_order``, ``update_order_milestone``,
``register_receipt``, ``open_diligence_action``, ``order_import_problems``,
``apply_order_import_row``, ``list_mas``, ``find_mas_package`` and ``list_panel``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import attachment_origins, attachments, audit, numbering, rbac, recording, versioning
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.export_document import project_label
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Company
from src.modulos.financeiro import service as financeiro
from src.modulos.suprimentos import calculations, validation
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
from src.modulos.suprimentos.validation import (
    ApprovalInput,
    ClosingInput,
    CommercialInput,
    DocumentInput,
    EmissionInput,
    MasFilters,
    MilestoneInput,
    NegotiationInput,
    OrderFilters,
    PackageChangeInput,
    PackageFilters,
    PackageInput,
    ProposalInput,
    QualificationInput,
    ReceiptInput,
    RecommendationInput,
    RequisitionInput,
    ReturnInput,
    RfxInput,
    SuggestedRiskInput,
    SupplierFilters,
    SupplierInput,
    TechnicalInput,
)

MODULE = "suprimentos"
GERENCIADORA = "Gerenciadora"
NO_QUALIFICATION = "Sem qualificação"
INITIAL_JUSTIFICATION = "Cadastro inicial."

NOT_FOUND_MESSAGE = "Fornecedor não encontrado."
UNKNOWN_COMPANY_MESSAGE = "A empresa informada não existe no cadastro."
DUPLICATE_COMPANY_MESSAGE = "Já existe empresa com este nome."
DOCUMENT_NOT_FOUND_MESSAGE = "O documento informado não pertence a este fornecedor."
FINAL_EVALUATION_JUSTIFICATION = (
    "Avaliação final do contrato {contract}: nota {score} (classe {score_class})."
)


@dataclass(frozen=True)
class DocumentLine:
    """One document of the list: the row, its validity and how it reads against today."""

    id: int
    name: str
    validity: date | None
    version: int
    expired: bool
    expiring: bool


@dataclass(frozen=True)
class EvaluationLine:
    """One contract evaluation of the company, already calculated by the Financeiro."""

    period: date
    kind: str
    contract_number: str
    score: int | None
    score_class: str
    class_description: str


@dataclass(frozen=True)
class ContractLine:
    """One contract of the company in the scope."""

    number: str
    object: str
    value_cents: int


@dataclass(frozen=True)
class SupplierOrderLine:
    """One order of the company in the scope, with the dates the OTD reads (ISSUE-061)."""

    number: str
    description: str
    value_cents: int
    delivery: date | None
    contractual_date: date


@dataclass(frozen=True)
class HistoryLine:
    """One change of situation of the qualification, with its author."""

    date: date
    from_situation: str | None
    to_situation: str
    author: str
    justification: str


@dataclass(frozen=True)
class SupplierLine:
    """One line of the register: the company, its qualification and what is calculated."""

    company_id: int
    name: str
    kind: str | None
    registered: bool
    situation: str
    validity: date | None
    observation: str
    version: int | None
    categories: tuple[str, ...]
    documents: tuple[DocumentLine, ...]
    evaluations: tuple[EvaluationLine, ...]
    contracts: tuple[ContractLine, ...]
    orders: tuple[SupplierOrderLine, ...]
    history: tuple[HistoryLine, ...]
    contracted_cents: int
    reference_date: date

    @property
    def documents_up_to_date(self) -> bool:
        """Every document in day; a supplier with no document at all counts as in day."""
        return all(not document.expired for document in self.documents)

    @property
    def expired_documents(self) -> tuple[DocumentLine, ...]:
        """The documents already expired, for the warning of the line."""
        return tuple(document for document in self.documents if document.expired)

    @property
    def qualification_expired(self) -> bool:
        """Whether the qualification validity already passed the line's reference date."""
        return self.validity is not None and self.validity < self.reference_date

    @property
    def qualification_expiring(self) -> bool:
        """Whether the qualification expires within the alert window of the line."""
        if self.validity is None or self.qualification_expired:
            return False
        return (self.validity - self.reference_date).days <= calculations.QUALIFICATION_ALERT_DAYS

    @property
    def last_evaluation(self) -> EvaluationLine | None:
        """The newest evaluation (the list is ascending by period)."""
        return self.evaluations[-1] if self.evaluations else None

    @property
    def mean_score(self) -> Decimal | None:
        """The mean of the evaluation scores, one decimal, or ``None`` without evaluations."""
        return calculations.average_score(
            evaluation.score for evaluation in self.evaluations if evaluation.score is not None
        )

    @property
    def otd(self) -> Decimal | None:
        """The OTD of the orders of the company: deliveries up to the contractual date (ISSUE-061)."""
        return calculations.on_time_delivery(
            (order.delivery, order.contractual_date) for order in self.orders
        )

    @property
    def delivered_orders(self) -> tuple[SupplierOrderLine, ...]:
        """The orders already delivered, the base of the OTD."""
        return tuple(order for order in self.orders if order.delivery is not None)

    @property
    def orders_on_time(self) -> int:
        """How many deliveries happened up to the contractual date."""
        return sum(
            1
            for order in self.delivered_orders
            if order.delivery is not None and order.delivery <= order.contractual_date
        )


@dataclass(frozen=True)
class SupplierSummary:
    """The six KPIs of the register, counted on the whole universe (the filters cut the table)."""

    companies: int
    registered: int
    qualified: int
    in_qualification: int
    restricted_or_blocked: int
    blocked: int
    expired_documents: int
    validity_due: int

    @property
    def unregistered(self) -> int:
        """Companies of the register still without qualification."""
        return self.companies - self.registered


@dataclass(frozen=True)
class SupplierListing:
    """What the register shows for a filter: the lines, the KPIs and the filter choices."""

    lines: tuple[SupplierLine, ...]
    summary: SupplierSummary
    categories: tuple[str, ...]
    filters: SupplierFilters
    page: int

    @property
    def total(self) -> int:
        """How many suppliers the filter holds, whatever the page."""
        return len(self.lines)

    @property
    def page_count(self) -> int:
        """How many pages the list has; an empty list still has one."""
        return max(1, -(-len(self.lines) // validation.PAGE_SIZE))

    @property
    def page_lines(self) -> tuple[SupplierLine, ...]:
        """The lines of the current page."""
        start = (self.page - 1) * validation.PAGE_SIZE
        return self.lines[start : start + validation.PAGE_SIZE]


@dataclass(frozen=True)
class SaveResult:
    """What saving the qualification answers: the company and whether the cadastro was born."""

    company_id: int
    created: bool
    company_name: str


# ── Reading ──────────────────────────────────────────────────────────────────────────────────


def list_suppliers(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: SupplierFilters,
    reference_date: date,
) -> SupplierListing:
    """The register for the filters: the lines, the KPIs of the universe and the choices."""
    universe = _universe(session, user=user, scope=scope, reference_date=reference_date)
    shown = tuple(line for line in universe if _matches(line, filters))
    page = min(max(filters.page, 1), max(1, -(-len(shown) // validation.PAGE_SIZE)))
    return SupplierListing(
        lines=shown,
        summary=_summary(universe),
        categories=tuple(sorted({name for line in universe for name in line.categories})),
        filters=filters,
        page=page,
    )


def find_supplier(
    session: Session, *, user: User, scope: Scope, company_id: int, reference_date: date
) -> SupplierLine | None:
    """The line of one company, or ``None`` when it is not in the register."""
    for line in _universe(session, user=user, scope=scope, reference_date=reference_date):
        if line.company_id == company_id:
            return line
    return None


def _universe(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> tuple[SupplierLine, ...]:
    """Every company of the register (the Geranciadora is not a supplier), by name."""
    rbac.require_module(user, MODULE)
    companies = [
        company
        for company in configuracoes.list_company_summaries(session)
        if company.kind != GERENCIADORA
    ]
    suppliers = _suppliers_by_company(session, [company.id for company in companies])
    supplier_ids = [supplier.id for supplier in suppliers.values()]
    categories = _categories_by_supplier(session, supplier_ids)
    documents = _documents_by_supplier(session, supplier_ids)
    history = _history_by_supplier(session, supplier_ids)
    authors = configuracoes.person_names(
        session, {row.by_id for rows in history.values() for row in rows}
    )
    performance = financeiro.company_performance(
        session, user=user, scope=scope, reference_date=reference_date
    )
    orders = _orders_by_company(session, user=user, scope=scope)
    return tuple(
        _line_of(
            company_id=company.id,
            name=company.name,
            kind=company.kind,
            supplier=suppliers.get(company.id),
            categories=categories.get(_supplier_id(suppliers.get(company.id)), ()),
            documents=documents.get(_supplier_id(suppliers.get(company.id)), ()),
            history=history.get(_supplier_id(suppliers.get(company.id)), ()),
            authors=authors,
            performance=performance.get(company.id),
            orders=orders.get(company.id, ()),
            reference_date=reference_date,
        )
        for company in companies
    )


def _orders_by_company(
    session: Session, *, user: User, scope: Scope
) -> dict[int, tuple[SupplierOrderLine, ...]]:
    """The orders of the scope, by company: what the OTD of the supplier reads (ISSUE-061)."""
    rbac.require_module(user, MODULE)
    projects = configuracoes.list_projects(session)
    wanted = [
        project.id for project in projects if scope.is_portfolio or project.id == scope.project_id
    ]
    if not wanted:
        return {}
    statement = (
        select(PurchaseOrder)
        .where(PurchaseOrder.project_id.in_(wanted))
        .order_by(PurchaseOrder.number)
    )
    grouped: dict[int, list[SupplierOrderLine]] = {}
    for order in session.scalars(statement):
        grouped.setdefault(order.company_id, []).append(
            SupplierOrderLine(
                number=order.number,
                description=order.description,
                value_cents=order.value_cents,
                delivery=order.delivery,
                contractual_date=order.contractual_date,
            )
        )
    return {company_id: tuple(rows) for company_id, rows in grouped.items()}


def _supplier_id(supplier: Supplier | None) -> int:
    return supplier.id if supplier is not None else 0


def _line_of(
    *,
    company_id: int,
    name: str,
    kind: str | None,
    supplier: Supplier | None,
    categories: Sequence[SupplierCategory],
    documents: Sequence[SupplierDocument],
    history: Sequence[SupplierHistory],
    authors: Mapping[int, str],
    performance: financeiro.CompanyPerformance | None,
    orders: Sequence[SupplierOrderLine],
    reference_date: date,
) -> SupplierLine:
    evaluations = tuple(
        EvaluationLine(
            period=item.period,
            kind=item.kind,
            contract_number=item.contract_number,
            score=item.score,
            score_class=item.score_class,
            class_description=item.class_description,
        )
        for item in (performance.evaluations if performance else ())
    )
    contracts = tuple(
        ContractLine(number=item.number, object=item.object, value_cents=item.original_value_cents)
        for item in (performance.contracts if performance else ())
    )
    return SupplierLine(
        company_id=company_id,
        name=name,
        kind=kind,
        registered=supplier is not None,
        situation=supplier.situation if supplier else NO_QUALIFICATION,
        validity=supplier.validity if supplier else None,
        observation=(supplier.observation or "") if supplier else "",
        version=supplier.version if supplier else None,
        categories=tuple(category.category for category in categories),
        documents=tuple(
            DocumentLine(
                id=document.id,
                name=document.name,
                validity=document.validity,
                version=document.version,
                expired=calculations.document_is_expired(document.validity, reference_date),
                expiring=calculations.document_is_expiring(document.validity, reference_date),
            )
            for document in documents
        ),
        evaluations=evaluations,
        contracts=contracts,
        orders=tuple(orders),
        history=tuple(
            HistoryLine(
                date=row.on,
                from_situation=row.from_situation,
                to_situation=row.to_situation,
                author=authors.get(row.by_id, ""),
                justification=row.justification,
            )
            for row in history
        ),
        contracted_cents=sum(contract.value_cents for contract in contracts),
        reference_date=reference_date,
    )


def _matches(line: SupplierLine, filters: SupplierFilters) -> bool:
    if filters.situation == NO_QUALIFICATION:
        if line.registered:
            return False
    elif filters.situation and line.situation != filters.situation:
        return False
    if filters.category and filters.category not in line.categories:
        return False
    if filters.search:
        searched = " ".join(
            (line.name, line.kind or "", " ".join(line.categories), line.observation)
        )
        if _normalize(filters.search) not in _normalize(searched):
            return False
    return True


def _summary(universe: Sequence[SupplierLine]) -> SupplierSummary:
    registered = [line for line in universe if line.registered]
    return SupplierSummary(
        companies=len(universe),
        registered=len(registered),
        qualified=sum(1 for line in registered if line.situation == calculations.QUALIFIED),
        in_qualification=sum(
            1 for line in registered if line.situation == calculations.IN_QUALIFICATION
        ),
        restricted_or_blocked=sum(
            1
            for line in registered
            if line.situation in (calculations.RESTRICTED, calculations.BLOCKED)
        ),
        blocked=sum(1 for line in registered if line.situation == calculations.BLOCKED),
        expired_documents=sum(1 for line in registered if not line.documents_up_to_date),
        validity_due=sum(
            1 for line in registered if line.qualification_expired or line.qualification_expiring
        ),
    )


def _suppliers_by_company(session: Session, company_ids: Collection[int]) -> dict[int, Supplier]:
    if not company_ids:
        return {}
    statement = select(Supplier).where(Supplier.company_id.in_(company_ids))
    return {supplier.company_id: supplier for supplier in session.scalars(statement)}


def _categories_by_supplier(
    session: Session, supplier_ids: Collection[int]
) -> dict[int, list[SupplierCategory]]:
    if not supplier_ids:
        return {}
    statement = (
        select(SupplierCategory)
        .where(SupplierCategory.supplier_id.in_(supplier_ids))
        .order_by(SupplierCategory.category, SupplierCategory.id)
    )
    grouped: dict[int, list[SupplierCategory]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.supplier_id, []).append(row)
    return grouped


def _documents_by_supplier(
    session: Session, supplier_ids: Collection[int]
) -> dict[int, list[SupplierDocument]]:
    if not supplier_ids:
        return {}
    statement = (
        select(SupplierDocument)
        .where(SupplierDocument.supplier_id.in_(supplier_ids))
        .order_by(SupplierDocument.id)
    )
    grouped: dict[int, list[SupplierDocument]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.supplier_id, []).append(row)
    return grouped


def _history_by_supplier(
    session: Session, supplier_ids: Collection[int]
) -> dict[int, list[SupplierHistory]]:
    if not supplier_ids:
        return {}
    statement = (
        select(SupplierHistory)
        .where(SupplierHistory.supplier_id.in_(supplier_ids))
        .order_by(SupplierHistory.on, SupplierHistory.id)
    )
    grouped: dict[int, list[SupplierHistory]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.supplier_id, []).append(row)
    return grouped


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


# ── Writing ──────────────────────────────────────────────────────────────────────────────────


def create_supplier(
    session: Session, *, user: User, data: SupplierInput, reference_date: date
) -> SaveResult:
    """Create the company of the cadastro and its first qualification (Em qualificação).

    The company is written by the Configurações facade, the owner of ``empresa``; the
    qualification, the categories, the documents and the history enter through this facade, in
    the same transaction (D5, D9).
    """
    rbac.require(user, Permission.WRITE)
    problems = validation.creation_problems(data)
    if configuracoes.find_company_id_by_name(session, data.name) is not None:
        problems["nome"] = DUPLICATE_COMPANY_MESSAGE
    if problems:
        raise InvalidDataError(problems)
    company = configuracoes.create_company(
        session, author_id=user.id, name=data.name, kind=data.kind
    )
    save_qualification(
        session,
        user=user,
        company_id=company.id,
        data=QualificationInput(
            situation=calculations.IN_QUALIFICATION,
            categories=data.categories,
            documents=data.documents,
            observation=data.observation,
        ),
        reference_date=reference_date,
        company=company,
    )
    return SaveResult(company_id=company.id, created=True, company_name=company.name)


def save_qualification(
    session: Session,
    *,
    user: User,
    company_id: int,
    data: QualificationInput,
    reference_date: date,
    company: configuracoes.CompanySummary | Company | None = None,
) -> SaveResult:
    """Create or update the qualification of a company, with categories, documents and history.

    A change of situation demands a justification and Restrito or Bloqueado demand the reason
    (``validation``); the history row is a fact with de/para/author/justificativa, and it only
    exists when the situation really changes (as in the prototype). Documents are edited by row,
    each with its own version; a document without id is born now.
    """
    rbac.require(user, Permission.WRITE)
    chosen = company or _company(session, company_id)
    if chosen is None:
        raise InvalidDataError({"empresa": UNKNOWN_COMPANY_MESSAGE})
    supplier = _supplier_of_company(session, company_id)
    previous = supplier.situation if supplier is not None else None
    problems = validation.qualification_problems(
        data, previous_situation=previous, reference_date=reference_date
    )
    if problems:
        raise InvalidDataError(problems)
    if supplier is None:
        supplier = recording.create(
            session,
            user_id=user.id,
            record=Supplier(
                company_id=company_id,
                situation=data.situation,
                validity=data.validity,
                observation=data.observation.strip() or None,
            ),
        )
        created = True
    else:
        changes = _supplier_changes(supplier, data)
        if changes:
            recording.update(
                session, user_id=user.id, record=supplier, changes=changes, version=data.version
            )
        created = False
    _replace_categories(session, user=user, supplier=supplier, categories=data.categories)
    _save_documents(session, user=user, supplier=supplier, documents=data.documents)
    _record_history(
        session,
        user=user,
        supplier=supplier,
        previous=previous,
        data=data,
        reference_date=reference_date,
    )
    return SaveResult(company_id=company_id, created=created, company_name=chosen.name)


def _supplier_changes(supplier: Supplier, data: QualificationInput) -> dict[str, object]:
    changes: dict[str, object] = {}
    observation = data.observation.strip() or None
    if supplier.situation != data.situation:
        changes["situation"] = data.situation
    if supplier.validity != data.validity:
        changes["validity"] = data.validity
    if supplier.observation != observation:
        changes["observation"] = observation
    return changes


def _replace_categories(
    session: Session, *, user: User, supplier: Supplier, categories: Sequence[str]
) -> None:
    """The categories of the supplier become exactly the informed ones, with the trail."""
    existing = list(
        session.scalars(select(SupplierCategory).where(SupplierCategory.supplier_id == supplier.id))
    )
    wanted = set(categories)
    for row in existing:
        if row.category not in wanted:
            before = audit.snapshot(row)
            session.delete(row)
            session.flush()
            audit.deleted(
                session,
                user_id=user.id,
                entity=row.__tablename__,
                record=row,
                before=before,
            )
    known = {row.category for row in existing}
    for category in categories:
        if category not in known:
            recording.create(
                session,
                user_id=user.id,
                record=SupplierCategory(supplier_id=supplier.id, category=category),
            )


def _save_documents(
    session: Session, *, user: User, supplier: Supplier, documents: Sequence[DocumentInput]
) -> None:
    """Each informed document: the existing row is edited (with its version), a new one is born."""
    for document in documents:
        if document.id is None:
            recording.create(
                session,
                user_id=user.id,
                record=SupplierDocument(
                    supplier_id=supplier.id,
                    name=document.name.strip(),
                    validity=document.validity,
                ),
            )
            continue
        row = session.get(SupplierDocument, document.id)
        if row is None or row.supplier_id != supplier.id:
            raise InvalidDataError({"documentos": DOCUMENT_NOT_FOUND_MESSAGE})
        changes = _document_changes(row, document)
        if changes:
            recording.update(
                session,
                user_id=user.id,
                record=row,
                changes=changes,
                version=document.version,
            )


def _document_changes(row: SupplierDocument, document: DocumentInput) -> dict[str, object]:
    changes: dict[str, object] = {}
    name = document.name.strip()
    if row.name != name:
        changes["name"] = name
    if row.validity != document.validity:
        changes["validity"] = document.validity
    return changes


def _record_history(
    session: Session,
    *,
    user: User,
    supplier: Supplier,
    previous: str | None,
    data: QualificationInput,
    reference_date: date,
) -> None:
    """The change of situation becomes a fact; the same situation does not (as the prototype)."""
    if previous == data.situation:
        return
    recording.create(
        session,
        user_id=user.id,
        record=SupplierHistory(
            supplier_id=supplier.id,
            by_id=user.person_id,
            on=reference_date,
            from_situation=previous,
            to_situation=data.situation,
            justification=data.justification.strip() or INITIAL_JUSTIFICATION,
        ),
    )


def _company(session: Session, company_id: int) -> configuracoes.CompanySummary | None:
    for company in configuracoes.list_company_summaries(session):
        if company.id == company_id:
            return company
    return None


def _supplier_of_company(session: Session, company_id: int) -> Supplier | None:
    return session.scalars(select(Supplier).where(Supplier.company_id == company_id)).one_or_none()


# ── The purchase plan (ISSUE-058) ────────────────────────────────────────────────────────────

HISTORY_ENTITY = "pacote_compra.historico"
INCLUSION_NOTE = "Pacote incluído no plano de compras."
IMPORT_NOTE = "Importado do plano de compras (planilha)."
BASELINE_NOTE = "Ajuste do plano antes da requisição."

CREATION_LABEL = "criacao"
IMPORT_LABEL = "importacao"
PLAN_LABEL = "plano"

# The history of the package speaks the Portuguese of the columns, as the trail does.
HISTORY_FIELDS: Mapping[str, str] = {
    "scope": "escopo",
    "kind": "tipo",
    "modality": "modalidade",
    "discipline_id": "disciplina",
    "buyer_id": "comprador",
    "eac_item_id": "item da EAC",
    "estimate_cents": "estimativa",
    "ros": "ros",
    "lli": "lli",
    "emergency": "emergencial",
    "gate_lli_date": "gate LLI",
    "gate_lli_reference": "gate LLI",
}


@dataclass(frozen=True)
class MilestoneLine:
    """One acquisition milestone with its three layers, as the screen reads it."""

    key: str
    label: str
    plan: date | None
    forecast: date | None
    real: date | None
    version: int


@dataclass(frozen=True)
class PackageLine:
    """One package of the plan: the record, its milestones and everything calculated from them."""

    id: int
    project_id: int
    project_label: str
    code: str
    scope: str
    kind: str
    modality: str
    discipline_id: int | None
    discipline: str
    buyer_id: int
    buyer: str
    eac_item_id: int
    eac_code: str
    eac_description: str
    estimate_cents: int
    ros: date | None
    lli: bool
    emergency: bool
    gate_date: date | None
    gate_reference: str
    version: int
    milestones: tuple[MilestoneLine, ...]
    reference_date: date
    # The process (ISSUE-059) and the order (ISSUE-061) do not exist yet: these read empty.
    adjudicated_cents: int | None = None
    supplier: str | None = None
    saving_cents: int | None = None
    # The commercial outcome the load brought from the prototype (ISSUE-063): the panel prefers
    # the live process and falls back to these when the package has none.
    first_proposal_cents: int | None = None
    valid_proposals: int | None = None
    single_supplier: bool | None = None

    def milestone(self, key: str) -> MilestoneLine | None:
        """The milestone named by key, or ``None`` when the package has no such row."""
        return next((item for item in self.milestones if item.key == key), None)

    @property
    def requisition_real(self) -> date | None:
        """The real date of the requisition; from it on the baseline is frozen."""
        requisition = self.milestone(calculations.REQUISITION_MILESTONE)
        return requisition.real if requisition is not None else None

    @property
    def frozen(self) -> bool:
        """Whether the baseline is frozen: the requisition already has a real date."""
        return calculations.lb_frozen(self.requisition_real)

    @property
    def plan_order(self) -> date | None:
        """The planned date of the order/contract milestone."""
        order = self.milestone(calculations.ORDER_MILESTONE)
        return order.plan if order is not None else None

    @property
    def stage(self) -> str:
        """The stage the real dates lead to."""
        return calculations.package_stage({item.key: item.real for item in self.milestones})

    @property
    def slack_days(self) -> int | None:
        """The planned slack: the ROS minus the planned order date."""
        return calculations.planned_slack_days(self.ros, self.plan_order)

    @property
    def adjudication(self) -> MilestoneLine | None:
        """The adjudication milestone."""
        return self.milestone(calculations.ADJUDICATION_MILESTONE)

    @property
    def adjudication_deviation_days(self) -> int | None:
        """The deviation of the adjudication against its LB; positive is late."""
        adjudication = self.adjudication
        return calculations.adjudication_deviation_days(
            adjudication.plan if adjudication else None,
            adjudication.real if adjudication else None,
            adjudication.forecast if adjudication else None,
            self.reference_date,
        )

    @property
    def adjudication_overdue(self) -> bool:
        """Whether the adjudication is late: not done and past its LB or forecast."""
        adjudication = self.adjudication
        return calculations.adjudication_overdue(
            adjudication.plan if adjudication else None,
            adjudication.real if adjudication else None,
            adjudication.forecast if adjudication else None,
            self.reference_date,
        )


@dataclass(frozen=True)
class PackageSummary:
    """The KPIs of the plan, counted on the whole universe (the filters cut the table)."""

    packages: int
    estimated_cents: int
    with_baseline: int
    lli: int
    lli_critical: int
    forecast_until_reference: int
    overdue: int
    # The adjudicated packages and the saving depend on the process and the order: empty for now.
    adjudicated: int | None = None
    saving_cents: int | None = None


@dataclass(frozen=True)
class PackageListing:
    """What the plan shows for a filter: the lines, the KPIs and the filter choices."""

    lines: tuple[PackageLine, ...]
    summary: PackageSummary
    filters: PackageFilters
    page: int

    @property
    def total(self) -> int:
        """How many packages the filter holds, whatever the page."""
        return len(self.lines)

    @property
    def page_count(self) -> int:
        """How many pages the list has; an empty list still has one."""
        return max(1, -(-len(self.lines) // validation.PACKAGE_PAGE_SIZE))

    @property
    def page_lines(self) -> tuple[PackageLine, ...]:
        """The lines of the current page."""
        start = (self.page - 1) * validation.PACKAGE_PAGE_SIZE
        return self.lines[start : start + validation.PACKAGE_PAGE_SIZE]


@dataclass(frozen=True)
class PackageOptions:
    """What the package forms list: buyers, disciplines and the cost items of the EAC."""

    buyers: tuple[configuracoes.RegisterOption, ...]
    disciplines: tuple[configuracoes.RegisterOption, ...]
    eac_items: tuple[financeiro.CostItemBalance, ...]

    @property
    def eac_items_by_code(self) -> dict[str, financeiro.CostItemBalance]:
        """The cost items by code: how the form and the checks resolve the chosen item."""
        return {item.code: item for item in self.eac_items}


@dataclass(frozen=True)
class PackageSave:
    """What saving a package answers: the record and whether it was born now."""

    package_id: int
    code: str
    created: bool


# ── Reading the plan ─────────────────────────────────────────────────────────────────────────


def list_packages(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: PackageFilters,
    reference_date: date,
) -> PackageListing:
    """The plan for the filters: the lines and the KPIs of the whole universe."""
    universe = _package_universe(session, user=user, scope=scope, reference_date=reference_date)
    shown = tuple(line for line in universe if _matches_package(line, filters))
    page = min(max(filters.page, 1), max(1, -(-len(shown) // validation.PACKAGE_PAGE_SIZE)))
    return PackageListing(
        lines=shown,
        summary=_package_summary(universe),
        filters=filters,
        page=page,
    )


def find_package(
    session: Session, *, user: User, scope: Scope, package_id: int, reference_date: date
) -> PackageLine | None:
    """The line of one package, or ``None`` when it is not in the scope."""
    for line in _package_universe(session, user=user, scope=scope, reference_date=reference_date):
        if line.id == package_id:
            return line
    return None


def package_options(
    session: Session, *, user: User, project_id: int, reference_date: date
) -> PackageOptions:
    """The choices of the forms: people of the cadastro, disciplines and cost items of the EAC.

    The saldo a comprometer of each EAC item is read from the Financeiro on this query (D9);
    the item is always from the project the package belongs to.
    """
    rbac.require_module(user, MODULE)
    disciplines = configuracoes.discipline_names_by_id(session)
    return PackageOptions(
        buyers=tuple(configuracoes.list_person_options(session)),
        disciplines=tuple(
            configuracoes.RegisterOption(id=discipline_id, name=name)
            for discipline_id, name in disciplines.items()
        ),
        eac_items=financeiro.cost_item_balances(
            session, project_id=project_id, reference_date=reference_date
        ),
    )


def _package_universe(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> tuple[PackageLine, ...]:
    """Every package of the scope, by project and code, with its milestones and names."""
    rbac.require_module(user, MODULE)
    projects = configuracoes.list_projects(session)
    wanted = [
        project for project in projects if scope.is_portfolio or project.id == scope.project_id
    ]
    if not wanted:
        return ()
    statement = (
        select(PurchasePackage)
        .where(PurchasePackage.project_id.in_([project.id for project in wanted]))
        .order_by(PurchasePackage.project_id, PurchasePackage.code)
    )
    packages = list(session.scalars(statement))
    milestones = _milestones_by_package(session, [package.id for package in packages])
    labels = {project.id: project_label(project) for project in projects}
    buyers = configuracoes.person_names(session, {package.buyer_id for package in packages})
    disciplines = configuracoes.discipline_names_by_id(session)
    eac_items = financeiro.eac_item_labels(session, [package.eac_item_id for package in packages])
    return tuple(
        _package_line(
            package,
            project=labels.get(package.project_id, ""),
            milestones=milestones.get(package.id, ()),
            buyers=buyers,
            disciplines=disciplines,
            eac_items=eac_items,
            reference_date=reference_date,
        )
        for package in packages
    )


def _milestones_by_package(
    session: Session, package_ids: Collection[int]
) -> dict[int, tuple[PackageMilestone, ...]]:
    if not package_ids:
        return {}
    statement = select(PackageMilestone).where(PackageMilestone.package_id.in_(package_ids))
    grouped: dict[int, dict[str, PackageMilestone]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.package_id, {})[row.milestone] = row
    return {
        package_id: tuple(rows[key] for key in calculations.MILESTONE_KEYS if key in rows)
        for package_id, rows in grouped.items()
    }


def _package_line(
    package: PurchasePackage,
    *,
    project: str,
    milestones: Sequence[PackageMilestone],
    buyers: Mapping[int, str],
    disciplines: Mapping[int, str],
    eac_items: Mapping[int, tuple[str, str]],
    reference_date: date,
) -> PackageLine:
    code, description = eac_items.get(package.eac_item_id, ("", ""))
    return PackageLine(
        id=package.id,
        project_id=package.project_id,
        project_label=project,
        code=package.code,
        scope=package.scope,
        kind=package.kind,
        modality=package.modality,
        discipline_id=package.discipline_id,
        discipline=disciplines.get(package.discipline_id or 0, ""),
        buyer_id=package.buyer_id,
        buyer=buyers.get(package.buyer_id, ""),
        eac_item_id=package.eac_item_id,
        eac_code=code,
        eac_description=description,
        estimate_cents=package.estimate_cents,
        ros=package.ros,
        lli=package.lli,
        emergency=package.emergency,
        gate_date=package.gate_lli_date,
        gate_reference=package.gate_lli_reference or "",
        first_proposal_cents=package.first_proposal_cents,
        valid_proposals=package.valid_proposals,
        single_supplier=package.single_supplier,
        version=package.version,
        milestones=tuple(
            MilestoneLine(
                key=row.milestone,
                label=calculations.MILESTONE_LABELS.get(row.milestone, row.milestone),
                plan=row.plan_date,
                forecast=row.forecast_date,
                real=row.real_date,
                version=row.version,
            )
            for row in milestones
        ),
        reference_date=reference_date,
    )


def _matches_package(line: PackageLine, filters: PackageFilters) -> bool:
    if filters.kind and line.kind != filters.kind:
        return False
    if filters.lli_only and not line.lli:
        return False
    if filters.search:
        searched = " ".join(
            (
                line.code,
                line.scope,
                line.eac_code,
                line.eac_description,
                line.buyer,
                line.discipline,
            )
        )
        if _normalize(filters.search) not in _normalize(searched):
            return False
    return True


def _package_summary(universe: Sequence[PackageLine]) -> PackageSummary:
    return PackageSummary(
        packages=len(universe),
        estimated_cents=sum(line.estimate_cents for line in universe),
        with_baseline=sum(
            1
            for line in universe
            if (adjudication := line.adjudication) is not None and adjudication.plan is not None
        ),
        lli=sum(1 for line in universe if line.lli),
        lli_critical=sum(
            1
            for line in universe
            if line.lli and line.slack_days is not None and line.slack_days < 0
        ),
        forecast_until_reference=sum(
            1
            for line in universe
            if (adjudication := line.adjudication) is not None
            and adjudication.plan is not None
            and adjudication.plan <= line.reference_date
        ),
        overdue=sum(1 for line in universe if line.adjudication_overdue),
    )


# ── Writing the plan ─────────────────────────────────────────────────────────────────────────


def create_package(
    session: Session,
    *,
    user: User,
    project_id: int,
    data: PackageInput,
    reference_date: date,
    note: str = INCLUSION_NOTE,
) -> PackageSave:
    """Create a package of the plan, always tied to a cost item of the project's EAC.

    The code follows the project sequence; the three intermediate plan dates are derived from
    the informed ones and the whole plan is born as the seven milestones of the baseline. The
    emergency justification and the gate reference ride in the history line of the trail.
    """
    rbac.require(user, Permission.WRITE)
    options = package_options(
        session, user=user, project_id=project_id, reference_date=reference_date
    )
    problems = validation.package_problems(
        data,
        eac_items=options.eac_items_by_code,
        discipline_ids={choice.id for choice in options.disciplines},
        buyer_ids={choice.id for choice in options.buyers},
    )
    if problems:
        raise InvalidDataError(problems)
    item = options.eac_items_by_code.get(data.eac_code.strip())
    if item is None:
        raise InvalidDataError({"eac": validation.EAC_REQUIRED})
    plan = calculations.derived_plan_dates(
        requisition=_required_date(data.requisition, validation.PLAN_DATE_REQUIRED),
        rfx=_required_date(data.rfx, validation.PLAN_DATE_REQUIRED),
        adjudication=_required_date(data.adjudication, validation.PLAN_DATE_REQUIRED),
        order=_required_date(data.order, validation.PLAN_DATE_REQUIRED),
    )
    gate = data.lli and data.anticipated_fid
    package = recording.create(
        session,
        user_id=user.id,
        record=PurchasePackage(
            project_id=project_id,
            eac_item_id=item.item_id,
            buyer_id=_required_int(data.buyer_id, validation.CHOOSE_BUYER),
            discipline_id=data.discipline_id,
            code=_next_code(session, project_id),
            scope=data.scope.strip(),
            kind=data.kind,
            modality=data.modality,
            lli=data.lli,
            estimate_cents=_required_int(data.estimate_cents, validation.ESTIMATE_REQUIRED),
            ros=_required_date(data.ros, validation.ROS_REQUIRED),
            emergency=data.emergency,
            gate_lli_date=reference_date if gate else None,
            gate_lli_reference=data.gate_reference.strip() if gate else None,
        ),
    )
    _write_plan(session, user=user, package=package, plan=plan)
    _append_history(
        session,
        user=user,
        package=package,
        fields=(IMPORT_LABEL,) if note == IMPORT_NOTE else (CREATION_LABEL,),
        justification=note,
        reference_date=reference_date,
        emergency=data.emergency,
        emergency_justification=data.emergency_justification,
    )
    return PackageSave(package_id=package.id, code=package.code, created=True)


def update_package(
    session: Session, *, user: User, package_id: int, data: PackageInput, reference_date: date
) -> PackageSave:
    """Write the full plan of a package whose baseline is still editable.

    The frozen baseline is refused here too: after the requisition only ``change_package``
    writes. The three intermediate plan dates are derived again, and everything leaves the trail
    with before and after.
    """
    rbac.require(user, Permission.WRITE)
    package = _package_or_refuse(session, package_id)
    if calculations.lb_frozen(_requisition_real(session, package)):
        raise InvalidDataError({"geral": validation.FROZEN_BASELINE})
    options = package_options(
        session, user=user, project_id=package.project_id, reference_date=reference_date
    )
    problems = validation.package_problems(
        data,
        eac_items=options.eac_items_by_code,
        discipline_ids={choice.id for choice in options.disciplines},
        buyer_ids={choice.id for choice in options.buyers},
    )
    if problems:
        raise InvalidDataError(problems)
    item = options.eac_items_by_code.get(data.eac_code.strip())
    if item is None:
        raise InvalidDataError({"eac": validation.EAC_REQUIRED})
    plan = calculations.derived_plan_dates(
        requisition=_required_date(data.requisition, validation.PLAN_DATE_REQUIRED),
        rfx=_required_date(data.rfx, validation.PLAN_DATE_REQUIRED),
        adjudication=_required_date(data.adjudication, validation.PLAN_DATE_REQUIRED),
        order=_required_date(data.order, validation.PLAN_DATE_REQUIRED),
    )
    changes = _package_changes(package, data, item_id=item.item_id, reference_date=reference_date)
    rows = _milestone_rows(session, package_id=package.id)
    plan_changes = [
        key
        for key in calculations.MILESTONE_KEYS
        if key in rows and rows[key].plan_date != plan[key]
    ]
    if not changes and not plan_changes:
        return PackageSave(package_id=package.id, code=package.code, created=False)
    if changes:
        recording.update(
            session, user_id=user.id, record=package, changes=changes, version=data.version
        )
    else:
        versioning.require(session, package, data.version)
    for key in plan_changes:
        recording.update(
            session,
            user_id=user.id,
            record=rows[key],
            changes={"plan_date": plan[key]},
            version=rows[key].version,
        )
    fields = [*_history_fields(changes), PLAN_LABEL]
    _append_history(
        session,
        user=user,
        package=package,
        fields=fields,
        justification=BASELINE_NOTE,
        reference_date=reference_date,
        emergency=data.emergency,
        emergency_justification=data.emergency_justification,
    )
    return PackageSave(package_id=package.id, code=package.code, created=False)


def change_package(
    session: Session, *, user: User, package_id: int, data: PackageChangeInput, reference_date: date
) -> PackageSave:
    """Change what may still change after the requisition: scope, buyer, estimate and ROS.

    The justification is demanded when something really changes (10 characters and up) and the
    changed fields go to the history line of the trail; a frozen package keeps its four plan
    dates and the rest of the strategy untouched.
    """
    rbac.require(user, Permission.WRITE)
    package = _package_or_refuse(session, package_id)
    if not calculations.lb_frozen(_requisition_real(session, package)):
        raise InvalidDataError({"geral": validation.BASELINE_EDITABLE})
    changes = _frozen_changes(package, data)
    problems = validation.change_problems(data, changed=bool(changes))
    if problems:
        raise InvalidDataError(problems)
    if not changes:
        return PackageSave(package_id=package.id, code=package.code, created=False)
    recording.update(
        session, user_id=user.id, record=package, changes=changes, version=data.version
    )
    _append_history(
        session,
        user=user,
        package=package,
        fields=_history_fields(changes),
        justification=data.justification.strip(),
        reference_date=reference_date,
    )
    return PackageSave(package_id=package.id, code=package.code, created=False)


def _next_code(session: Session, project_id: int) -> str:
    codes = list(
        session.scalars(
            select(PurchasePackage.code).where(PurchasePackage.project_id == project_id)
        )
    )
    return calculations.next_package_code(codes)


def _write_plan(
    session: Session, *, user: User, package: PurchasePackage, plan: Mapping[str, date]
) -> None:
    for key in calculations.MILESTONE_KEYS:
        recording.create(
            session,
            user_id=user.id,
            record=PackageMilestone(package_id=package.id, milestone=key, plan_date=plan[key]),
        )


def _package_changes(
    package: PurchasePackage,
    data: PackageInput,
    *,
    item_id: int,
    reference_date: date,
) -> dict[str, object]:
    """The package fields that really change in the full edit (the plan dates have their own)."""
    changes: dict[str, object] = {}
    scope = data.scope.strip()
    values: Mapping[str, object] = {
        "scope": scope,
        "kind": data.kind,
        "modality": data.modality,
        "discipline_id": data.discipline_id,
        "buyer_id": data.buyer_id,
        "eac_item_id": item_id,
        "estimate_cents": data.estimate_cents,
        "ros": data.ros,
        "lli": data.lli,
        "emergency": data.emergency,
    }
    for field, value in values.items():
        if getattr(package, field) != value:
            changes[field] = value
    gate = data.lli and data.anticipated_fid
    gate_date = reference_date if gate else None
    gate_reference = data.gate_reference.strip() if gate else None
    if package.gate_lli_date != gate_date:
        changes["gate_lli_date"] = gate_date
    if (package.gate_lli_reference or None) != gate_reference:
        changes["gate_lli_reference"] = gate_reference
    return changes


def _frozen_changes(package: PurchasePackage, data: PackageChangeInput) -> dict[str, object]:
    """The four fields the frozen form may change, and only them."""
    changes: dict[str, object] = {}
    scope = data.scope.strip()
    values: Mapping[str, object] = {
        "scope": scope,
        "buyer_id": data.buyer_id,
        "estimate_cents": data.estimate_cents,
        "ros": data.ros,
    }
    for field, value in values.items():
        if getattr(package, field) != value:
            changes[field] = value
    return changes


def _history_fields(changes: Mapping[str, object]) -> list[str]:
    """The changed fields named as the history prints them, without repeats."""
    return list(dict.fromkeys(HISTORY_FIELDS.get(field, field) for field in changes))


def _append_history(
    session: Session,
    *,
    user: User,
    package: PurchasePackage,
    fields: Sequence[str],
    justification: str,
    reference_date: date,
    emergency: bool = False,
    emergency_justification: str = "",
) -> None:
    """The history line of the package, as the prototype kept it; it lives in the audit trail.

    The emergency justification has no column in the model of the plan, so it rides here, in the
    same trail line of the operation (DECISION, ISSUE-058).
    """
    after: dict[str, Any] = {
        "data": reference_date.isoformat(),
        "por_id": user.person_id,
        "campos": list(fields),
        "justificativa": justification,
    }
    if emergency:
        after["justificativa_emergencial"] = emergency_justification.strip()
    audit.append(
        session,
        audit.TrailLine(
            user_id=user.id,
            entity=HISTORY_ENTITY,
            record_id=package.id,
            action=audit.CREATED,
            after=after,
            project_id=package.project_id,
        ),
    )


def _milestone_rows(session: Session, *, package_id: int) -> dict[str, PackageMilestone]:
    statement = select(PackageMilestone).where(PackageMilestone.package_id == package_id)
    return {row.milestone: row for row in session.scalars(statement)}


def _requisition_real(session: Session, package: PurchasePackage) -> date | None:
    row = session.scalars(
        select(PackageMilestone).where(
            PackageMilestone.package_id == package.id,
            PackageMilestone.milestone == calculations.REQUISITION_MILESTONE,
        )
    ).one_or_none()
    return row.real_date if row is not None else None


def _package_or_refuse(session: Session, package_id: int) -> PurchasePackage:
    package = session.get(PurchasePackage, package_id)
    if package is None:
        raise InvalidDataError(validation.PACKAGE_NOT_FOUND)
    return package


def _required_int(value: int | None, message: str) -> int:
    """A value the checks already approved; ``None`` here is a mistake of the caller."""
    if value is None:
        raise InvalidDataError(message)
    return value


# ── The purchase process (ISSUE-059) ─────────────────────────────────────────────────────────

PROCESS_HISTORY_ENTITY = "processo_compra.historico"
PROPOSAL_ATTACHMENT_TABLE = "processo_proposta"

REQUISITION_NOTE = "Requisição registrada."
FIRST_PROPOSAL_NOTE = "Primeira proposta recebida."
PROCESS_GROUP = "suprimentos"

# The history of the process speaks the Portuguese of the prototype: the stage the action led
# to, the author (a person of the register) and the text of the feed.
HISTORY_DATE = "data"
HISTORY_STAGE = "etapa"
HISTORY_AUTHOR = "por_id"
HISTORY_TEXT = "texto"


@dataclass(frozen=True)
class ProcessParameters:
    """The suprimentos group in force: the minimum of proposals and the approval bands."""

    minimum_proposals: int
    approval_bands: tuple[tuple[int | None, str], ...]


@dataclass(frozen=True)
class ProcessStep:
    """One of the nine steps of the process bar, with its situation and its dates."""

    key: str
    label: str
    position: int
    situation: str
    date: date | None
    planned: date | None
    forecast: date | None


@dataclass(frozen=True)
class InviteeLine:
    """One invited supplier: the company of the register, or the free name of the prototype."""

    company_id: int | None
    name: str
    situation: str | None


@dataclass(frozen=True)
class ProposalLine:
    """One proposal, with everything the equalization map calculates on reading."""

    id: int
    company_id: int | None
    name: str
    received: date
    value_cents: int
    deadline_days: int
    validity: date | None
    technical_score: int | None
    technically_approved: bool | None
    deviations: str
    version: int
    qualification: str
    negotiated_cents: int | None
    commercial_score: Decimal | None
    final_score: Decimal | None
    rank: int | None


@dataclass(frozen=True)
class NegotiationLine:
    """One negotiation round of the process."""

    date: date
    name: str
    value_cents: int
    observation: str


@dataclass(frozen=True)
class ProcessHistoryLine:
    """One line of the process feed, read from the audit trail."""

    date: date
    stage: str
    author: str
    text: str


@dataclass(frozen=True)
class RecommendationLine:
    """The recommendation of the adjudication, as the ficha and the approval form read it."""

    date: date
    company_id: int
    name: str
    value_cents: int
    author: str
    justification: str


@dataclass(frozen=True)
class ApprovalLine:
    """The approval of the adjudication: who, when, in which band and the opinion."""

    date: date
    approver: str
    band: str
    opinion: str


@dataclass(frozen=True)
class ProcessLine:
    """One package of the scope with its process: the list and the ficha read this line."""

    package_id: int
    project_id: int
    project_label: str
    code: str
    scope: str
    kind: str
    modality: str
    lli: bool
    buyer: str
    estimate_cents: int
    ros: date | None
    eac_item_id: int
    eac_code: str
    eac_description: str
    eac_balance_cents: int | None
    process_id: int | None
    process_version: int | None
    number: str | None
    stage: str
    stage_index: int
    steps: tuple[ProcessStep, ...]
    weight_technical: int
    weight_commercial: int
    proposals_deadline: date | None
    requisition_real: date | None
    invitees: tuple[InviteeLine, ...]
    proposals: tuple[ProposalLine, ...]
    negotiations: tuple[NegotiationLine, ...]
    history: tuple[ProcessHistoryLine, ...]
    best: ProposalLine | None
    received_count: int
    approved_count: int
    minimum: int
    single_supplier: bool
    approval_band: str | None
    reference_value_cents: int
    reference_date: date
    recommendation: RecommendationLine | None = None
    approval: ApprovalLine | None = None
    order_number: str | None = None
    contract_number: str | None = None

    def step(self, key: str) -> ProcessStep | None:
        """The step named by key, or ``None`` when the process has no such step."""
        return next((item for item in self.steps if item.key == key), None)

    @property
    def adjudication_plan(self) -> date | None:
        """The LB of the approval milestone."""
        step = self.step(calculations.ADJUDICATION_MILESTONE)
        return step.planned if step is not None else None

    @property
    def adjudication_real(self) -> date | None:
        """The real date of the approval milestone."""
        step = self.step(calculations.ADJUDICATION_MILESTONE)
        return step.date if step is not None else None

    @property
    def adjudication_forecast(self) -> date | None:
        """The forecast of the approval milestone, when the package has one."""
        step = self.step(calculations.ADJUDICATION_MILESTONE)
        return step.forecast if step is not None else None

    @property
    def order_real(self) -> date | None:
        """The real date of the order/contract milestone."""
        step = self.step(calculations.ORDER_MILESTONE)
        return step.date if step is not None else None

    @property
    def cycle_days(self) -> int | None:
        """The days from the requisition to the order, or to the reference date."""
        return calculations.cycle_days(self.requisition_real, self.order_real, self.reference_date)


@dataclass(frozen=True)
class ProcessSummary:
    """The five KPIs of the process list, counted on the whole universe of the scope."""

    total: int
    in_progress: int
    expected_in_progress: int
    awaiting_approval: int
    mean_valid_proposals: Decimal | None
    single_supplier_count: int
    single_supplier_share: Decimal | None
    cycle_mean_days: int | None
    baseline_cycle_days: int | None
    minimum_proposals: int


@dataclass(frozen=True)
class ProcessListing:
    """What the process screen shows for a filter: the lines and the KPIs of the universe."""

    lines: tuple[ProcessLine, ...]
    summary: ProcessSummary
    filters: validation.ProcessFilters

    @property
    def total(self) -> int:
        """How many processes the filter holds."""
        return len(self.lines)


@dataclass(frozen=True)
class SupplierChoice:
    """A qualified company as the RFx form lists it: identity, situation and categories."""

    company_id: int
    name: str
    situation: str
    categories: tuple[str, ...]


@dataclass(frozen=True)
class PlannedPackage:
    """A package still without a real requisition: what the Nova requisição form lists."""

    id: int
    code: str
    scope: str
    plan_requisition: date | None


@dataclass(frozen=True)
class ProcessOptions:
    """The choices of the process forms: suppliers, companies and people of the register."""

    suppliers: tuple[SupplierChoice, ...]
    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]


@dataclass(frozen=True)
class ProcessSave:
    """What a process action answers: the package, its code, the RFx number and the document.

    ``document`` is the number of the order or of the contract the emission created; it stays
    ``None`` for the other actions.
    """

    package_id: int
    code: str
    number: str | None
    document: str | None = None


# ── Reading the process ──────────────────────────────────────────────────────────────────────


def list_processes(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: validation.ProcessFilters,
    reference_date: date,
) -> ProcessListing:
    """The processes of the scope for the filters: the lines and the KPIs of the universe."""
    universe = _process_universe(session, user=user, scope=scope, reference_date=reference_date)
    shown = tuple(line for line in universe if _matches_process(line, filters))
    minimum = (
        universe[0].minimum
        if universe
        else _process_parameters(session, reference_date=reference_date).minimum_proposals
    )
    return ProcessListing(
        lines=shown, summary=_process_summary(universe, minimum=minimum), filters=filters
    )


def find_process(
    session: Session, *, user: User, scope: Scope, package_id: int, reference_date: date
) -> ProcessLine | None:
    """The line of one package with its process, or ``None`` when it is not in the scope.

    The ficha is the only reader that needs the saldo a comprometer of the EAC item and the
    document the emission created, so the balance of the package's project and the order/contract
    numbers are read here and not on the list (D9).
    """
    line = _line_in_scope(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    if line is None:
        return None
    return replace(
        line,
        eac_balance_cents=_eac_balance(session, line=line, reference_date=reference_date),
        order_number=_order_number(session, package_id=package_id),
        contract_number=financeiro.contract_number_by_package(session, package_id=package_id),
    )


def _line_in_scope(
    session: Session, *, user: User, scope: Scope, package_id: int, reference_date: date
) -> ProcessLine | None:
    """The line of one package, without the saldo a comprometer of the EAC item."""
    for line in _process_universe(session, user=user, scope=scope, reference_date=reference_date):
        if line.package_id == package_id:
            return line
    return None


def process_options(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> ProcessOptions:
    """The choices of the forms: qualified suppliers, companies and people of the register."""
    rbac.require_module(user, MODULE)
    del scope, reference_date
    return ProcessOptions(
        suppliers=_supplier_choices(session),
        companies=_company_choices(session),
        people=tuple(configuracoes.list_person_options(session)),
    )


def planned_packages(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> tuple[PlannedPackage, ...]:
    """The packages of the scope still without a real requisition, by project and code."""
    rbac.require_module(user, MODULE)
    del reference_date
    packages = _scoped_packages(session, scope)
    milestones = _milestones_by_package(session, [package.id for package in packages])
    return tuple(
        PlannedPackage(
            id=package.id,
            code=package.code,
            scope=package.scope,
            plan_requisition=_plan_of(
                milestones.get(package.id, ()), calculations.REQUISITION_MILESTONE
            ),
        )
        for package in packages
        if _real_of(milestones.get(package.id, ()), calculations.REQUISITION_MILESTONE) is None
    )


def _process_universe(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> tuple[ProcessLine, ...]:
    """Every package of the scope with its process, by project and code."""
    rbac.require_module(user, MODULE)
    packages = _scoped_packages(session, scope)
    if not packages:
        return ()
    package_ids = [package.id for package in packages]
    milestones = _milestones_by_package(session, package_ids)
    processes = _processes_by_package(session, package_ids)
    process_ids = [process.id for process in processes.values()]
    invitees = _invitees_by_process(session, process_ids)
    proposals = _proposals_by_process(session, process_ids)
    negotiations = _negotiations_by_process(session, process_ids)
    histories = _history_by_process(session, process_ids)
    authors = configuracoes.person_names(
        session,
        {
            author
            for rows in histories.values()
            for row in rows
            if (author := (row.after or {}).get(HISTORY_AUTHOR)) is not None
        }
        | {
            author
            for process in processes.values()
            for author in (process.recommendation_by_id, process.approval_by_id)
            if author is not None
        },
    )
    situations = _supplier_situations(session)
    names_by_company = {
        company.id: company.name for company in configuracoes.list_company_summaries(session)
    }
    buyers = configuracoes.person_names(session, {package.buyer_id for package in packages})
    labels = {
        project.id: project_label(project) for project in configuracoes.list_projects(session)
    }
    eac_items = financeiro.eac_item_labels(session, [package.eac_item_id for package in packages])
    parameters = _process_parameters(session, reference_date=reference_date)
    return tuple(
        _process_line(
            package,
            milestones=milestones.get(package.id, ()),
            process=processes.get(package.id),
            invitees=invitees.get(_process_id(processes.get(package.id)), ()),
            proposals=proposals.get(_process_id(processes.get(package.id)), ()),
            negotiations=negotiations.get(_process_id(processes.get(package.id)), ()),
            history=histories.get(_process_id(processes.get(package.id)), ()),
            authors=authors,
            situations=situations,
            names_by_company=names_by_company,
            project=labels.get(package.project_id, ""),
            buyer=buyers.get(package.buyer_id, ""),
            eac=eac_items.get(package.eac_item_id, ("", "")),
            parameters=parameters,
            reference_date=reference_date,
        )
        for package in packages
    )


def _process_id(process: PurchaseProcess | None) -> int:
    return process.id if process is not None else 0


def _process_line(
    package: PurchasePackage,
    *,
    milestones: Sequence[PackageMilestone],
    process: PurchaseProcess | None,
    invitees: Sequence[ProcessInvitee],
    proposals: Sequence[ProcessProposal],
    negotiations: Sequence[ProcessNegotiation],
    history: Sequence[Any],
    authors: Mapping[int, str],
    situations: Mapping[int, str],
    names_by_company: Mapping[int, str],
    project: str,
    buyer: str,
    eac: tuple[str, str],
    parameters: ProcessParameters,
    reference_date: date,
) -> ProcessLine:
    """The line of one package: the process, its steps, its proposals and everything calculated."""
    stage = _stage_of(process, milestones=milestones, history=history)
    current = calculations.stage_index(stage)
    lines = _history_lines(history, authors=authors)
    proposal_lines, best = _proposal_lines(
        proposals,
        negotiations=negotiations,
        situations=situations,
        names_by_company=names_by_company,
        weight_technical=process.weight_technical if process is not None else 50,
        weight_commercial=process.weight_commercial if process is not None else 50,
    )
    approved = [line for line in proposal_lines if line.technically_approved]
    reference_value = package.estimate_cents
    if best is not None:
        reference_value = best.negotiated_cents or best.value_cents
    if process is not None and process.recommendation_value_cents is not None:
        reference_value = process.recommendation_value_cents
    return ProcessLine(
        package_id=package.id,
        project_id=package.project_id,
        project_label=project,
        code=package.code,
        scope=package.scope,
        kind=package.kind,
        modality=package.modality,
        lli=package.lli,
        buyer=buyer,
        estimate_cents=package.estimate_cents,
        ros=package.ros,
        eac_item_id=package.eac_item_id,
        eac_code=eac[0],
        eac_description=eac[1],
        eac_balance_cents=None,
        process_id=process.id if process is not None else None,
        process_version=process.version if process is not None else None,
        number=process.number if process is not None else None,
        stage=stage,
        stage_index=current,
        steps=_steps_of(
            milestones=milestones,
            process=process,
            proposals=proposals,
            negotiations=negotiations,
            current=current,
        ),
        weight_technical=process.weight_technical if process is not None else 50,
        weight_commercial=process.weight_commercial if process is not None else 50,
        proposals_deadline=process.proposals_deadline if process is not None else None,
        requisition_real=_real_of(milestones, calculations.REQUISITION_MILESTONE),
        invitees=tuple(
            InviteeLine(
                company_id=row.company_id,
                name=row.name or names_by_company.get(row.company_id or 0, ""),
                situation=situations.get(row.company_id or 0),
            )
            for row in invitees
        ),
        proposals=proposal_lines,
        negotiations=tuple(
            NegotiationLine(
                date=row.on,
                name=row.name or names_by_company.get(row.company_id or 0, ""),
                value_cents=row.value_cents,
                observation=row.observation or "",
            )
            for row in negotiations
        ),
        history=lines,
        best=best,
        received_count=len(proposals),
        approved_count=len(approved),
        minimum=parameters.minimum_proposals,
        single_supplier=calculations.single_supplier(len(invitees), parameters.minimum_proposals),
        approval_band=calculations.approval_band_for(reference_value, parameters.approval_bands),
        reference_value_cents=reference_value,
        reference_date=reference_date,
        recommendation=_recommendation_line(
            process, authors=authors, names_by_company=names_by_company
        ),
        approval=_approval_line(process, authors=authors),
    )


def _recommendation_line(
    process: PurchaseProcess | None,
    *,
    authors: Mapping[int, str],
    names_by_company: Mapping[int, str],
) -> RecommendationLine | None:
    """The recommendation of the process, or ``None`` when it has none."""
    if (
        process is None
        or process.recommendation_on is None
        or process.recommendation_company_id is None
        or process.recommendation_value_cents is None
    ):
        return None
    return RecommendationLine(
        date=process.recommendation_on,
        company_id=process.recommendation_company_id,
        name=names_by_company.get(process.recommendation_company_id, ""),
        value_cents=process.recommendation_value_cents,
        author=authors.get(process.recommendation_by_id or 0, ""),
        justification=process.recommendation_justification or "",
    )


def _approval_line(
    process: PurchaseProcess | None, *, authors: Mapping[int, str]
) -> ApprovalLine | None:
    """The approval of the process, or ``None`` when it has none."""
    if process is None or process.approval_on is None:
        return None
    return ApprovalLine(
        date=process.approval_on,
        approver=authors.get(process.approval_by_id or 0, ""),
        band=process.approval_band or "",
        opinion=process.approval_opinion or "",
    )


def _stage_of(
    process: PurchaseProcess | None,
    *,
    milestones: Sequence[PackageMilestone],
    history: Sequence[Any],
) -> str:
    """The stage of the process: the last recorded action, or the real dates of the package."""
    fallback = calculations.package_stage({row.milestone: row.real_date for row in milestones})
    if process is None:
        return fallback
    return calculations.process_stage(
        [str((row.after or {}).get(HISTORY_STAGE, "")) for row in history], fallback
    )


def _steps_of(
    *,
    milestones: Sequence[PackageMilestone],
    process: PurchaseProcess | None,
    proposals: Sequence[ProcessProposal],
    negotiations: Sequence[ProcessNegotiation],
    current: int,
) -> tuple[ProcessStep, ...]:
    """The nine steps of the bar, with the fact and the LB of each one."""
    first_proposal = min((row.received for row in proposals), default=None)
    last_negotiation = max((row.on for row in negotiations), default=None)
    facts: Mapping[str, date | None] = {
        calculations.REQUISITION_MILESTONE: _real_of(milestones, "requisicao"),
        "rfx": _real_of(milestones, "rfx"),
        "propostas": first_proposal,
        "eqTecnica": _real_of(milestones, "eqTecnica"),
        "eqComercial": _real_of(milestones, "eqComercial"),
        "negociacao": last_negotiation,
        "recomendacao": process.recommendation_on if process is not None else None,
        calculations.ADJUDICATION_MILESTONE: _real_of(milestones, "adjudicacao"),
        calculations.ORDER_MILESTONE: _real_of(milestones, "pedido"),
    }
    return tuple(
        ProcessStep(
            key=key,
            label=label,
            position=position,
            situation=calculations.step_situation(
                position, current=current, done=facts.get(key) is not None
            ),
            date=facts.get(key),
            planned=_plan_of(milestones, key),
            forecast=_forecast_of(milestones, key),
        )
        for position, (key, label) in enumerate(calculations.PROCESS_STEPS, start=1)
    )


def _proposal_lines(
    proposals: Sequence[ProcessProposal],
    *,
    negotiations: Sequence[ProcessNegotiation],
    situations: Mapping[int, str],
    names_by_company: Mapping[int, str],
    weight_technical: int,
    weight_commercial: int,
) -> tuple[tuple[ProposalLine, ...], ProposalLine | None]:
    """The proposals with their scores and rank, and the best one of the ranking."""
    lowest = min(
        (row.value_cents for row in proposals if row.technically_approved is True), default=None
    )
    scored: list[ProposalLine] = []
    for row in proposals:
        negotiated = _negotiated_cents(row, negotiations)
        commercial = (
            calculations.commercial_score(row.value_cents, lowest)
            if row.technically_approved is True
            else None
        )
        final = calculations.final_score(
            row.technical_score, commercial, weight_technical, weight_commercial
        )
        scored.append(
            ProposalLine(
                id=row.id,
                company_id=row.company_id,
                name=row.name or names_by_company.get(row.company_id or 0, ""),
                received=row.received,
                value_cents=row.value_cents,
                deadline_days=row.deadline_days,
                validity=row.validity,
                technical_score=row.technical_score,
                technically_approved=row.technically_approved,
                deviations=row.deviations or "",
                version=row.version,
                qualification=_qualification_of(row, situations),
                negotiated_cents=negotiated,
                commercial_score=commercial,
                final_score=final,
                rank=None,
            )
        )
    ranks = dict(
        calculations.proposal_ranking(
            [(line.id, line.final_score, line.value_cents) for line in scored]
        )
    )
    ranked = sorted(
        (replace(line, rank=ranks.get(line.id)) for line in scored),
        key=lambda line: (line.rank or 99, line.id),
    )
    best = next((line for line in ranked if line.rank == 1), None)
    return tuple(ranked), best


def _negotiated_cents(
    proposal: ProcessProposal, negotiations: Sequence[ProcessNegotiation]
) -> int | None:
    """The value of the last negotiation with this proposal's supplier, as the prototype read."""
    wanted = _proposal_key(proposal.company_id, proposal.name)
    for row in reversed(negotiations):
        if _proposal_key(row.company_id, row.name) == wanted:
            return row.value_cents
    return None


def _proposal_key(company_id: int | None, name: str | None) -> tuple[str, str]:
    if company_id is not None:
        return ("empresa", str(company_id))
    return ("nome", _normalize(name or ""))


def _qualification_of(proposal: ProcessProposal, situations: Mapping[int, str]) -> str:
    if proposal.company_id is None:
        return "Não cadastrado"
    return situations.get(proposal.company_id, NO_QUALIFICATION)


def _history_lines(
    history: Sequence[Any], *, authors: Mapping[int, str]
) -> tuple[ProcessHistoryLine, ...]:
    """The process feed, from the audit lines the actions and the load wrote."""
    lines: list[ProcessHistoryLine] = []
    for row in history:
        after = row.after or {}
        raw_date = after.get(HISTORY_DATE)
        if not raw_date:
            continue
        lines.append(
            ProcessHistoryLine(
                date=date.fromisoformat(str(raw_date)),
                stage=str(after.get(HISTORY_STAGE, "")),
                author=authors.get(after.get(HISTORY_AUTHOR), ""),
                text=str(after.get(HISTORY_TEXT, "")),
            )
        )
    return tuple(lines)


def _matches_process(line: ProcessLine, filters: validation.ProcessFilters) -> bool:
    if filters.situation == "andamento" and line.stage_index >= len(calculations.PROCESS_STEPS):
        return False
    if filters.search:
        searched = " ".join(
            (line.code, line.scope, line.number or "", line.best.name if line.best else "")
        )
        if _normalize(filters.search) not in _normalize(searched):
            return False
    return True


def _process_summary(universe: Sequence[ProcessLine], *, minimum: int) -> ProcessSummary:
    """The five KPIs of the prototype, counted on the whole universe of the scope."""
    last_stage = len(calculations.PROCESS_STEPS)
    valid = [line for line in universe if line.approved_count > 0]
    unique = [line for line in valid if line.single_supplier]
    concluded = [line for line in universe if line.stage == calculations.PROCESS_STAGES[-1]]
    cycles = [line.cycle_days for line in concluded if line.cycle_days is not None]
    share = Decimal(100) * len(unique) / len(valid) if valid else None
    return ProcessSummary(
        total=len(universe),
        in_progress=sum(1 for line in universe if line.stage_index < last_stage),
        expected_in_progress=sum(1 for line in universe if _expected_in_progress(line)),
        awaiting_approval=sum(
            1 for line in universe if line.stage == "Recomendação de adjudicação"
        ),
        mean_valid_proposals=_mean_decimal([line.approved_count for line in valid]),
        single_supplier_count=len(unique),
        single_supplier_share=_mean_decimal([share] if share is not None else []),
        cycle_mean_days=_mean_int(cycles),
        baseline_cycle_days=_mean_int(_baseline_cycles(concluded)),
        minimum_proposals=minimum,
    )


def _expected_in_progress(line: ProcessLine) -> bool:
    """Whether the LB planned the requisition until the reference and not the order yet."""
    requisition = line.step("requisicao")
    if requisition is None or requisition.planned is None:
        return False
    if requisition.planned > line.reference_date:
        return False
    order = line.step("pedido")
    return order is None or order.planned is None or order.planned > line.reference_date


def _baseline_cycles(concluded: Sequence[ProcessLine]) -> list[int]:
    """The planned cycle of the concluded processes: the requisition LB to the order LB."""
    cycles: list[int] = []
    for line in concluded:
        requisition = line.step("requisicao")
        order = line.step("pedido")
        if (
            requisition is not None
            and order is not None
            and requisition.planned is not None
            and order.planned is not None
        ):
            cycles.append((order.planned - requisition.planned).days)
    return cycles


def _mean_decimal(values: Sequence[int | Decimal]) -> Decimal | None:
    if not values:
        return None
    total = sum((Decimal(value) for value in values), Decimal(0))
    return (total / Decimal(len(values))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _mean_int(values: Sequence[int]) -> int | None:
    if not values:
        return None
    mean = Decimal(sum(values)) / Decimal(len(values))
    return int(mean.to_integral_value(rounding=ROUND_HALF_UP))


# ── Writing the process ──────────────────────────────────────────────────────────────────────


def start_requisition(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: RequisitionInput,
    reference_date: date,
) -> ProcessSave:
    """Registrar requisição: the real date of the requisition milestone and its history line.

    The requisition happens before the RFx exists, so the line of the history belongs to the
    package trail (``pacote_compra.historico``), the same the plan writes; the document and the
    observation of the prototype ride in it, since the model has no columns for them.
    """
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, calculations.STAGE_PLANNED)
    problems = validation.date_problem(data.date, reference_date=reference_date)
    if problems:
        raise InvalidDataError(problems)
    milestone = _milestone_row(
        session, package_id=package_id, key=calculations.REQUISITION_MILESTONE
    )
    recording.update(
        session,
        user_id=user.id,
        record=milestone,
        changes={"real_date": data.date, "forecast_date": None},
        version=milestone.version,
    )
    after: dict[str, Any] = {
        HISTORY_DATE: data.date.isoformat() if data.date else "",
        HISTORY_AUTHOR: user.person_id,
        "campos": [calculations.REQUISITION_MILESTONE],
        "justificativa": data.observation.strip() or REQUISITION_NOTE,
    }
    if data.document.strip():
        after["documento"] = data.document.strip()
    _append_trail(
        session,
        user=user,
        entity=HISTORY_ENTITY,
        record_id=package_id,
        project_id=line.project_id,
        after=after,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


def issue_rfx(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: RfxInput,
    reference_date: date,
) -> ProcessSave:
    """Emitir RFx: creates the process, its invitees and the milestones of the emission.

    The minimum of invitees is the parameter in force, unless the single supplier with its
    justification; a blocked supplier is refused (read from the qualification of this module).
    """
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Requisição")
    parameters = _process_parameters(session, reference_date=reference_date)
    choices = {choice.company_id: choice for choice in _supplier_choices(session)}
    known = {company.id for company in _company_choices(session)}
    blocked = [
        choices[company_id].name
        for company_id in data.invitees
        if company_id in choices and choices[company_id].situation == calculations.BLOCKED
    ]
    unknown = [company_id for company_id in data.invitees if company_id not in known]
    problems = validation.rfx_problems(
        data,
        reference_date=reference_date,
        minimum=parameters.minimum_proposals,
        blocked=blocked,
        unknown=[str(company_id) for company_id in unknown],
    )
    if problems:
        raise InvalidDataError(problems)
    process = recording.create(
        session,
        user_id=user.id,
        record=PurchaseProcess(
            package_id=package_id,
            number=_next_process_number(session, kind=line.kind, reference_date=reference_date),
            weight_technical=_required_int(data.weight_technical, validation.PLAN_DATE_REQUIRED),
            weight_commercial=_required_int(data.weight_commercial, validation.PLAN_DATE_REQUIRED),
            proposals_deadline=_required_date(data.deadline, validation.PLAN_DATE_REQUIRED),
        ),
    )
    _write_invitees(session, user=user, process=process, data=data)
    _write_real(
        session,
        user=user,
        package_id=package_id,
        key="rfx",
        value=_required_date(data.date, validation.PLAN_DATE_REQUIRED),
    )
    _write_forecast(
        session,
        user=user,
        package_id=package_id,
        key="propostas",
        value=_required_date(data.deadline, validation.PLAN_DATE_REQUIRED),
    )
    invitees = len(data.invitees) + len(data.other_invitees)
    after: dict[str, Any] = {
        HISTORY_DATE: data.date.isoformat() if data.date else "",
        HISTORY_STAGE: "RFx emitida",
        HISTORY_AUTHOR: user.person_id,
        HISTORY_TEXT: f"{process.number} emitida para {invitees} fornecedores.",
    }
    if data.single_supplier:
        after["justificativa_unico"] = data.single_justification.strip()
    _append_trail(
        session,
        user=user,
        entity=PROCESS_HISTORY_ENTITY,
        record_id=process.id,
        project_id=line.project_id,
        after=after,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=process.number)


def register_proposal(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: ProposalInput,
    reference_date: date,
    file_name: str | None = None,
    content: bytes = b"",
    storage: Any = None,
) -> ProcessSave:
    """Registrar proposta: the proposal and its PDF, which is a real attachment (D5a).

    The file is checked before anything is written, so a proposal without its PDF is refused
    with nothing in the database; the first proposal moves the stage to "Propostas recebidas".
    """
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "RFx emitida", "Propostas recebidas")
    process = _process_row(session, package_id)
    situations = _supplier_situations(session)
    blocked = (
        data.company_id is not None and situations.get(data.company_id) == calculations.BLOCKED
    )
    duplicated = any(
        _proposal_key(row.company_id, row.name) == _proposal_key(data.company_id, data.name)
        for row in line.proposals
    )
    problems = validation.proposal_problems(
        data, reference_date=reference_date, blocked=blocked, duplicated=duplicated
    )
    problems.update(_file_problems(file_name, len(content), session, reference_date))
    if problems:
        raise InvalidDataError(problems)
    proposal = recording.create(
        session,
        user_id=user.id,
        record=ProcessProposal(
            process_id=process.id,
            company_id=data.company_id,
            name=data.name.strip() or None,
            received=_required_date(data.received, validation.PLAN_DATE_REQUIRED),
            value_cents=_required_int(data.value_cents, validation.PROPOSAL_VALUE_REQUIRED),
            deadline_days=_required_int(data.deadline_days, validation.PROPOSAL_DEADLINE_REQUIRED),
            validity=data.validity,
        ),
    )
    attachments.upload(
        session,
        user=user,
        new=attachments.NewAttachment(
            origin_table=PROPOSAL_ATTACHMENT_TABLE,
            origin_record_id=proposal.id,
            file_name=file_name,
            content=content,
        ),
        reference_date=reference_date,
        storage=storage,
    )
    if line.stage == "RFx emitida":
        _append_process_history(
            session,
            user=user,
            line=line,
            process=process,
            stage="Propostas recebidas",
            text=FIRST_PROPOSAL_NOTE,
            reference_date=reference_date,
        )
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Propostas recebidas",
        text=f"Proposta de {_proposal_display(session, proposal)} registrada.",
        reference_date=reference_date,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


def close_receipt(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: ClosingInput,
    reference_date: date,
) -> ProcessSave:
    """Encerrar recebimento: closes the proposals and opens the technical equalization.

    Below the minimum of the parameter the flow only goes on with a justification (20 characters
    and up), unless the RFx was a single supplier.
    """
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Propostas recebidas")
    problems = validation.closing_problems(
        data,
        reference_date=reference_date,
        count=line.received_count,
        minimum=line.minimum,
        exception=line.single_supplier,
    )
    if problems:
        raise InvalidDataError(problems)
    process = _process_row(session, package_id)
    _write_real(
        session,
        user=user,
        package_id=package_id,
        key="propostas",
        value=_required_date(data.date, validation.PLAN_DATE_REQUIRED),
    )
    after_extra = (
        {"justificativa_minimo": data.justification.strip()} if data.justification.strip() else None
    )
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Equalização técnica",
        text=f"Recebimento encerrado com {line.received_count} propostas.",
        reference_date=reference_date,
        extra=after_extra,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


def equalize_technically(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: TechnicalInput,
    reference_date: date,
) -> ProcessSave:
    """Equalização técnica: the scores and the approval of every proposal, then the commercial.

    Every proposal gets its score; without any approval the flow stops, and below the minimum of
    approved proposals it only goes on with a justification (20 characters and up), unless the
    RFx was a single supplier.
    """
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Equalização técnica")
    process = _process_row(session, package_id)
    by_id = {row.id: row for row in _proposal_rows(session, process.id)}
    by_evaluation = {item.proposal_id: item for item in data.evaluations}
    missing = [
        _proposal_display(session, row)
        for row in by_id.values()
        if (item := by_evaluation.get(row.id)) is None or item.score is None
    ]
    approved_count = sum(
        1
        for row in by_id.values()
        if (item := by_evaluation.get(row.id)) is not None and item.approved
    )
    problems = validation.technical_score_problems(
        data, reference_date=reference_date, missing=missing
    )
    problems.update(
        validation.technical_approval_problems(
            data,
            approved_count=approved_count,
            minimum=line.minimum,
            single_supplier=line.single_supplier,
        )
    )
    if problems:
        raise InvalidDataError(problems)
    for item in data.evaluations:
        row = by_id.get(item.proposal_id)
        if row is None:
            continue
        changes = {
            "technical_score": item.score,
            "technically_approved": item.approved,
            "deviations": item.deviations.strip() or None,
        }
        if _proposal_changes(row, changes):
            recording.update(
                session, user_id=user.id, record=row, changes=changes, version=item.version
            )
    _write_real(
        session,
        user=user,
        package_id=package_id,
        key="eqTecnica",
        value=_required_date(data.date, validation.PLAN_DATE_REQUIRED),
    )
    total = len(by_id)
    after_extra: dict[str, Any] = {}
    if data.responsible_id is not None:
        after_extra["responsavel_id"] = data.responsible_id
    if data.opinion.strip():
        after_extra["parecer"] = data.opinion.strip()
    if data.justification.strip():
        after_extra["justificativa_minimo"] = data.justification.strip()
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Equalização comercial",
        text=f"Parecer técnico: {approved_count} de {total} propostas aprovadas.",
        reference_date=reference_date,
        extra=after_extra or None,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


def equalize_commercially(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: CommercialInput,
    reference_date: date,
) -> ProcessSave:
    """Equalização comercial: the weights of the map, the ranking and the negotiation stage."""
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Equalização comercial")
    problems = validation.commercial_problems(data, reference_date=reference_date)
    if problems:
        raise InvalidDataError(problems)
    process = _process_row(session, package_id)
    changes = {
        "weight_technical": _required_int(data.weight_technical, validation.WEIGHTS_TOTAL),
        "weight_commercial": _required_int(data.weight_commercial, validation.WEIGHTS_TOTAL),
    }
    if _process_changes(process, changes):
        recording.update(
            session, user_id=user.id, record=process, changes=changes, version=data.version
        )
    else:
        versioning.require(session, process, data.version)
    _write_real(
        session,
        user=user,
        package_id=package_id,
        key="eqComercial",
        value=_required_date(data.date, validation.PLAN_DATE_REQUIRED),
    )
    best = _best_name(session, process)
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Negociação",
        text=f"Mapa comercial concluído; melhor nota final: {best}.",
        reference_date=reference_date,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


def register_negotiation(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: NegotiationInput,
    reference_date: date,
) -> ProcessSave:
    """Registrar negociação: the round with an approved proposal, an immutable fact."""
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Negociação")
    process = _process_row(session, package_id)
    proposal = next(
        (row for row in _proposal_rows(session, process.id) if row.id == data.proposal_id), None
    )
    if proposal is None or proposal.technically_approved is not True:
        raise InvalidDataError({"fornecedor": validation.NEGOTIATION_APPROVED_ONLY})
    above = data.value_cents is not None and data.value_cents > proposal.value_cents
    problems = validation.negotiation_problems(
        data, reference_date=reference_date, above_proposal=above
    )
    if problems:
        raise InvalidDataError(problems)
    recording.create(
        session,
        user_id=user.id,
        record=ProcessNegotiation(
            process_id=process.id,
            company_id=proposal.company_id,
            name=proposal.name,
            on=_required_date(data.date, validation.PLAN_DATE_REQUIRED),
            value_cents=_required_int(data.value_cents, validation.NEGOTIATION_VALUE_REQUIRED),
            observation=data.observation.strip() or None,
        ),
    )
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Negociação",
        text=f"Negociação com {_proposal_display(session, proposal)} registrada.",
        reference_date=reference_date,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


# ── Recommendation, approval and emission (ISSUE-060) ────────────────────────────────────────

RECOMMENDATION_NOTE = "Recomendada a {name}."
RETURN_NOTE = "Recomendação devolvida: {reason}"
APPROVAL_NOTE = "Aprovada na alçada: {band}."
ORDER_NOTE = "Pedido {number} emitido; valor comprometido na EAC."
CONTRACT_NOTE = "Contrato {number} emitido; valor comprometido na EAC."

DILIGENCE_ORIGIN = "Suprimentos"
DILIGENCE_GROUP = "Diligenciamento"
DILIGENCE_DAYS = 7
DEFAULT_RETENTION_PCT = 5


def recommend_award(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: RecommendationInput,
    reference_date: date,
) -> ProcessSave:
    """Recomendar adjudicação: only an approved proposal of a registered supplier follows.

    Another proposal, one that is not the best score or a supplier that is not qualified demands
    the justification (20 characters and up); a blocked supplier is refused. The recommendation
    fills the columns ISSUE-060 added and moves the process to the approval stage.
    """
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Negociação")
    process = _process_row(session, package_id)
    proposal = next(
        (row for row in _proposal_rows(session, process.id) if row.id == data.proposal_id), None
    )
    proposal_line = next((item for item in line.proposals if item.id == data.proposal_id), None)
    approved = proposal is not None and proposal.technically_approved is True
    registered = proposal is not None and proposal.company_id is not None
    situations = _supplier_situations(session)
    qualification = situations.get(proposal.company_id) if registered else None
    blocked = qualification == calculations.BLOCKED
    not_best = proposal_line is None or proposal_line.rank != 1
    needs_justification = calculations.recommendation_requires_justification(
        proposal_line.rank if proposal_line is not None else None, qualification
    )
    problems = validation.recommendation_problems(
        data,
        reference_date=reference_date,
        situation=validation.ProposalSituation(
            approved=approved,
            registered=registered,
            blocked=blocked,
            name=_proposal_display(session, proposal),
            not_best=not_best,
            needs_justification=needs_justification,
        ),
    )
    if problems:
        raise InvalidDataError(problems)
    if proposal is None or proposal.company_id is None:
        raise InvalidDataError({"fornecedor": validation.RECOMMENDATION_APPROVED_ONLY})
    recording.update(
        session,
        user_id=user.id,
        record=process,
        changes={
            "recommendation_on": data.date,
            "recommendation_company_id": proposal.company_id,
            "recommendation_value_cents": _required_int(
                data.value_cents, validation.RECOMMENDATION_VALUE_REQUIRED
            ),
            "recommendation_by_id": user.person_id,
            "recommendation_justification": data.justification.strip() or None,
        },
        version=process.version,
    )
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Recomendação de adjudicação",
        text=RECOMMENDATION_NOTE.format(name=_proposal_display(session, proposal)),
        reference_date=reference_date,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


def return_recommendation(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: ReturnInput,
    reference_date: date,
) -> ProcessSave:
    """Devolver: the recommendation goes back to negotiation with the reason in the history."""
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Recomendação de adjudicação")
    problems = validation.return_problems(data)
    if problems:
        raise InvalidDataError(problems)
    process = _process_row(session, package_id)
    recording.update(
        session,
        user_id=user.id,
        record=process,
        changes={
            "recommendation_on": None,
            "recommendation_company_id": None,
            "recommendation_value_cents": None,
            "recommendation_by_id": None,
            "recommendation_justification": None,
        },
        version=process.version,
    )
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Negociação",
        text=RETURN_NOTE.format(reason=data.reason.strip()),
        reference_date=reference_date,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


def approve_award(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: ApprovalInput,
    reference_date: date,
) -> ProcessSave:
    """Aprovar adjudicação: the band of the recommendation, with the segregation of duties.

    Who approves may not be the buyer nor who recommended (403); an LLI contracted before the
    investment gate without its approval and a value above the saldo a comprometer of the EAC
    item are refused; the approval writes the real date of the adjudication milestone.
    """
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Recomendação de adjudicação")
    process = _process_row(session, package_id)
    value = process.recommendation_value_cents
    if value is None or process.recommendation_company_id is None:
        raise InvalidDataError({"geral": validation.PROCESS_NOT_FOUND})
    known = (
        configuracoes.person_names(session, {data.approver_id})
        if data.approver_id is not None
        else {}
    )
    problems = validation.approval_problems(
        data, reference_date=reference_date, approver_known=bool(known)
    )
    if problems:
        raise InvalidDataError(problems)
    package = session.get(PurchasePackage, package_id)
    if package is None:
        raise InvalidDataError(validation.PACKAGE_NOT_FOUND)
    if data.approver_id in (process.recommendation_by_id, package.buyer_id):
        raise AccessDeniedError(validation.SEGREGATION_MESSAGE)
    if calculations.lli_before_gate(
        lli=package.lli,
        requisition=line.requisition_real,
        project_start=_project_start(session, line.project_id),
        gate_date=package.gate_lli_date,
    ):
        raise InvalidDataError({"geral": validation.LLI_GATE_MESSAGE})
    balance = _eac_balance(session, line=line, reference_date=reference_date)
    if balance is not None:
        over = validation.eac_balance_problem(
            code=line.eac_code, balance_cents=balance, value_cents=value
        )
        if over is not None:
            raise InvalidDataError({"geral": over})
    parameters = _process_parameters(session, reference_date=reference_date)
    band = calculations.approval_band_for(value, parameters.approval_bands)
    recording.update(
        session,
        user_id=user.id,
        record=process,
        changes={
            "approval_on": data.date,
            "approval_by_id": data.approver_id,
            "approval_band": band,
            "approval_opinion": data.opinion.strip() or None,
        },
        version=process.version,
    )
    _write_real(
        session,
        user=user,
        package_id=package_id,
        key=calculations.ADJUDICATION_MILESTONE,
        value=_required_date(data.date, validation.PLAN_DATE_REQUIRED),
    )
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Aprovada",
        text=APPROVAL_NOTE.format(band=band or ""),
        reference_date=reference_date,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number)


def emit_order_or_contract(
    session: Session,
    *,
    user: User,
    scope: Scope,
    package_id: int,
    data: EmissionInput,
    reference_date: date,
) -> ProcessSave:
    """Emitir pedido ou contrato: everything in the caller's transaction, or nothing at all.

    An equipment/material package creates the order with the standard manufacturing schedule
    from the deadline of the proposal, and an order born with negative slack opens the diligence
    action in the Central; a service/EPC package creates the contract through the Financeiro
    facade (D9). The value is committed in ``custo_erp`` in the month of the emission and the
    real date of the order milestone closes the flow.
    """
    rbac.require(user, Permission.WRITE)
    line = _process_or_refuse(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    _require_stage(line, "Aprovada")
    process = _process_row(session, package_id)
    value = process.recommendation_value_cents
    company_id = process.recommendation_company_id
    if value is None or company_id is None:
        raise InvalidDataError({"geral": validation.PROCESS_NOT_FOUND})
    package = session.get(PurchasePackage, package_id)
    if package is None:
        raise InvalidDataError(validation.PACKAGE_NOT_FOUND)
    service = calculations.is_service(line.kind)
    known_fiscal = (
        configuracoes.person_names(session, {data.fiscal_id}) if data.fiscal_id is not None else {}
    )
    problems = validation.emission_problems(
        data, reference_date=reference_date, service=service, fiscal_known=bool(known_fiscal)
    )
    if problems:
        raise InvalidDataError(problems)
    emission = _required_date(data.date, validation.PLAN_DATE_REQUIRED)
    document = (
        _emit_contract(
            session,
            user=user,
            line=line,
            package=package,
            data=data,
            emission=emission,
            value_cents=value,
            company_id=company_id,
        )
        if service
        else _emit_order(
            session,
            user=user,
            line=line,
            package=package,
            data=data,
            emission=emission,
            value_cents=value,
            company_id=company_id,
            reference_date=reference_date,
        )
    )
    financeiro.commit_purchase_cost(
        session,
        user=user,
        project_id=line.project_id,
        item_id=line.eac_item_id,
        on=emission,
        value_cents=value,
    )
    _write_real(
        session,
        user=user,
        package_id=package_id,
        key=calculations.ORDER_MILESTONE,
        value=emission,
    )
    note = CONTRACT_NOTE if service else ORDER_NOTE
    _append_process_history(
        session,
        user=user,
        line=line,
        process=process,
        stage="Pedido/contrato emitido",
        text=note.format(number=document),
        reference_date=reference_date,
    )
    return ProcessSave(package_id=package_id, code=line.code, number=line.number, document=document)


def _emit_order(
    session: Session,
    *,
    user: User,
    line: ProcessLine,
    package: PurchasePackage,
    data: EmissionInput,
    emission: date,
    value_cents: int,
    company_id: int,
    reference_date: date,
) -> str:
    """The order of an equipment/material package, with its six manufacturing milestones."""
    deadline = _required_int(data.deadline_days, validation.PROPOSAL_DEADLINE_REQUIRED)
    contractual = emission + timedelta(days=deadline)
    number = _next_order_number(session, reference_date=emission)
    order = recording.create(
        session,
        user_id=user.id,
        record=PurchaseOrder(
            project_id=line.project_id,
            package_id=line.package_id,
            company_id=company_id,
            number=number,
            description=line.scope,
            value_cents=value_cents,
            lli=line.lli,
            emission=emission,
            contractual_date=contractual,
            forecast=contractual,
            ros=_required_date(package.ros, validation.ROS_REQUIRED),
        ),
    )
    for position, (name, planned) in enumerate(
        calculations.manufacturing_schedule(emission, contractual), start=1
    ):
        recording.create(
            session,
            user_id=user.id,
            record=PurchaseOrderMilestone(
                order_id=order.id,
                position=position,
                name=name,
                baseline_date=planned,
                forecast_date=planned,
            ),
        )
    slack = calculations.delivery_slack_days(order.ros, contractual)
    if slack is not None and slack < 0:
        _open_diligence_action(
            session,
            user=user,
            order=order,
            buyer_id=package.buyer_id,
            slack_days=slack,
            reference_date=reference_date,
        )
    return number


def _emit_contract(
    session: Session,
    *,
    user: User,
    line: ProcessLine,
    package: PurchasePackage,
    data: EmissionInput,
    emission: date,
    value_cents: int,
    company_id: int,
) -> str:
    """The contract of a service/EPC package, created by the Financeiro facade (D9)."""
    created = financeiro.create_purchase_contract(
        session,
        user=user,
        project_id=line.project_id,
        company_id=company_id,
        eac_item_id=line.eac_item_id,
        purchase_package_id=line.package_id,
        object=line.scope,
        modality=line.modality,
        value_cents=value_cents,
        emission=emission,
        start=data.start or package.ros or emission,
        end=_required_date(data.end, validation.CONTRACT_END_REQUIRED),
        fiscal_id=data.fiscal_id,
        retention_pct=(
            data.retention_pct if data.retention_pct is not None else DEFAULT_RETENTION_PCT
        ),
    )
    return created.number


def _open_diligence_action(
    session: Session,
    *,
    user: User,
    order: PurchaseOrder,
    buyer_id: int,
    slack_days: int,
    reference_date: date,
) -> bool:
    """The diligence action of a critical order, in the Central, never a second open one.

    The guard reads the open actions of the order from the Central
    (``count_actions_of_origin``): the milestone update, the ERP import and the manual button may
    all meet the same critical order, and only the first opens the action (ISSUE-061).
    """
    from src.modulos.central_acoes import service as central_acoes
    from src.modulos.central_acoes.service import OriginActionCount
    from src.modulos.central_acoes.validation import NewAction

    counts = central_acoes.count_actions_of_origin(
        session,
        user=user,
        origin_kind=DILIGENCE_ORIGIN,
        references=[order.number],
        reference_date=reference_date,
    )
    if counts.get(order.number, OriginActionCount()).open:
        return False
    central_acoes.create_action(
        session,
        user=user,
        new=NewAction(
            project_id=order.project_id,
            origin=DILIGENCE_ORIGIN,
            origin_ref=order.number,
            subject=f"Recuperar a folga do pedido {order.number}",
            description=(
                f"Previsão de entrega em {_brazilian_date(order.forecast)} passa a data necessária "
                f"na obra ({_brazilian_date(order.ros)}): folga de {slack_days} dias."
            ),
            requester_id=user.person_id,
            responsible_id=buyer_id,
            planned_date=reference_date + timedelta(days=DILIGENCE_DAYS),
            group=DILIGENCE_GROUP,
        ),
        reference_date=reference_date,
    )
    return True


def _brazilian_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


# ── The expediting and receiving (ISSUE-061) ─────────────────────────────────────────────────

# The history of the order travels in the audit trail, as the process history does: the entity
# the ficha reads the last updates from. The receipt's evidence is a real attachment (D5a).
ORDER_HISTORY_ENTITY = "pedido.historico"
RECEIPT_ATTACHMENT_TABLE = "recebimento"

# The names of the six manufacturing milestones, as the ERP import names them (position + 1).
DILIGENCE_MILESTONES: tuple[str, ...] = tuple(
    name for name, _ in calculations.MANUFACTURING_MILESTONES
)

RECEIPT_NOTE = "Recebimento na obra registrado."
RECEIPT_DAMAGE_NOTE = " Com avarias."
IMPORT_ORDER_NOTE = "Atualizado pela importação do ERP ({milestone})."
ORDER_NOT_FOUND_MESSAGE = validation.ORDER_NOT_FOUND
IMPORT_ORDER_MISSING = "pedido {number} não encontrado."
IMPORT_MILESTONE_INVALID = "marco inválido."
IMPORT_REALIZED_IN_FUTURE = "data realizada futura."
IMPORT_FORECAST_IN_PAST = "previsão anterior à data de referência."
IMPORT_RECEIPT_PENDING = "Conferência pendente (importado do ERP)."

# The columns of the order history line in the trail, the same shape of the process history.
ORDER_HISTORY_AUTHOR = "por_id"
ORDER_HISTORY_TEXT = "texto"
ORDER_HISTORY_DATE = "data"


@dataclass(frozen=True)
class OrderMilestoneLine:
    """One manufacturing milestone of an order, already read against the reference date."""

    position: int
    name: str
    baseline: date | None
    forecast: date | None
    real: date | None
    situation: str
    deviation_days: int | None
    days_overdue: int

    @property
    def done(self) -> bool:
        """Whether the milestone has a real date."""
        return self.real is not None


@dataclass(frozen=True)
class ReceiptLine:
    """The receipt of an order: the date, the check, the damages and the pending items."""

    id: int
    date: date
    checked: bool
    damaged: bool
    damage_description: str
    pending: str


@dataclass(frozen=True)
class OrderHistoryLine:
    """One line of the order feed, read from the audit trail."""

    date: date
    author: str
    text: str


@dataclass(frozen=True)
class OrderActionLine:
    """The open diligence action of the order, as the Central reports it."""

    subject: str
    due_date: date | None


@dataclass(frozen=True)
class OrderRiskLine:
    """O risco sugerido do pedido, resolvido pela origem no registro do 05 (D9, ISSUE-067)."""

    code: str
    title: str
    situation: str


@dataclass(frozen=True)
class OrderLine:
    """One order of the scope: the list, the ficha and the exports read this line."""

    id: int
    project_id: int
    project_label: str
    number: str
    package_id: int
    package_code: str
    company_id: int
    supplier: str
    description: str
    value_cents: int
    lli: bool
    emission: date
    contractual_date: date
    forecast: date
    ros: date
    delivery: date | None
    buyer_id: int | None
    buyer: str
    milestones: tuple[OrderMilestoneLine, ...]
    receipt: ReceiptLine | None
    action: OrderActionLine | None
    history: tuple[OrderHistoryLine, ...]
    risk: OrderRiskLine | None
    slack_days: int | None
    band: str
    situation: str
    critical: bool
    overdue_milestones: int
    version: int

    @property
    def delivered(self) -> bool:
        """Whether the order was received."""
        return self.delivery is not None

    @property
    def prediction(self) -> date:
        """The delivery forecast in force: the real one when delivered, else the forecast."""
        return self.delivery or self.forecast

    @property
    def contractual_delay_days(self) -> int | None:
        """The delay against the contractual date: positive is late."""
        return calculations.contractual_delay_days(self.contractual_date, self.prediction)

    @property
    def next_milestone(self) -> OrderMilestoneLine | None:
        """The first milestone without a real date, or ``None`` when all are done."""
        return next((row for row in self.milestones if not row.done), None)


@dataclass(frozen=True)
class OrderSummary:
    """The five KPIs of the screen, counted on the whole universe (the filters cut the table)."""

    open_orders: int
    open_cents: int
    expected_open: int
    critical: int
    lli_critical: int
    warning: int
    overdue_milestones: int
    delivered: int
    delivered_on_time: int
    otd: Decimal | None


@dataclass(frozen=True)
class OrderListing:
    """What the screen shows for a filter: the lines, the KPIs, the pending block and the page."""

    lines: tuple[OrderLine, ...]
    summary: OrderSummary
    pending: tuple[OrderLine, ...]
    filters: OrderFilters
    page: int

    @property
    def total(self) -> int:
        """How many orders the filter holds, whatever the page."""
        return len(self.lines)

    @property
    def page_count(self) -> int:
        """How many pages the list has; an empty list still has one."""
        return max(1, -(-len(self.lines) // validation.ORDER_PAGE_SIZE))

    @property
    def page_lines(self) -> tuple[OrderLine, ...]:
        """The lines of the current page."""
        start = (self.page - 1) * validation.ORDER_PAGE_SIZE
        return self.lines[start : start + validation.ORDER_PAGE_SIZE]


@dataclass(frozen=True)
class OrderSave:
    """What saving a milestone or a receipt answers: the order and whether an action was opened."""

    order_id: int
    number: str
    action_created: bool = False
    risk_code: str = ""


# ── Reading the orders ───────────────────────────────────────────────────────────────────────


def list_orders(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: OrderFilters,
    reference_date: date,
) -> OrderListing:
    """The orders of the scope for the filters: the lines, the KPIs of the universe and the page."""
    universe = _order_universe(session, user=user, scope=scope, reference_date=reference_date)
    shown = tuple(line for line in universe if _matches_order(line, filters))
    page = min(max(filters.page, 1), max(1, -(-len(shown) // validation.ORDER_PAGE_SIZE)))
    return OrderListing(
        lines=shown,
        summary=_order_summary(universe, reference_date=reference_date),
        pending=tuple(
            line
            for line in universe
            if line.critical and (line.action is None or line.risk is None)
        ),
        filters=filters,
        page=page,
    )


def find_order(
    session: Session,
    *,
    user: User,
    scope: Scope,
    reference_date: date,
    order_id: int | None = None,
    number: str | None = None,
) -> OrderLine | None:
    """The line of one order by id or by number, or ``None`` when it is not in the scope."""
    for line in _order_universe(session, user=user, scope=scope, reference_date=reference_date):
        if order_id is not None and line.id == order_id:
            return line
        if number is not None and line.number == number:
            return line
    return None


def _order_universe(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> tuple[OrderLine, ...]:
    """Every order of the scope, by number, with its milestones, receipt, action and history."""
    rbac.require_module(user, MODULE)
    projects = configuracoes.list_projects(session)
    wanted = [
        project for project in projects if scope.is_portfolio or project.id == scope.project_id
    ]
    if not wanted:
        return ()
    statement = (
        select(PurchaseOrder)
        .where(PurchaseOrder.project_id.in_([project.id for project in wanted]))
        .order_by(PurchaseOrder.number)
    )
    orders = list(session.scalars(statement))
    if not orders:
        return ()
    package_ids = {order.package_id for order in orders}
    packages = {
        package.id: package
        for package in session.scalars(
            select(PurchasePackage).where(PurchasePackage.id.in_(package_ids))
        )
    }
    milestones = _order_milestones_by_order(session, [order.id for order in orders])
    receipts = _receipts_by_order(session, [order.id for order in orders])
    history = _order_history_by_order(session, [order.id for order in orders])
    actions = _order_actions(session, user=user, orders=orders, reference_date=reference_date)
    risks = _order_risks(session, [order.number for order in orders])
    labels = {project.id: project_label(project) for project in projects}
    companies = configuracoes.list_company_names(session)
    buyers = configuracoes.person_names(
        session, {package.buyer_id for package in packages.values()}
    )
    authors = configuracoes.person_names(
        session,
        {
            author
            for rows in history.values()
            for line in rows
            if isinstance(line.after, Mapping)
            and isinstance(author := line.after.get(ORDER_HISTORY_AUTHOR), int)
        },
    )
    return tuple(
        _order_line(
            order,
            project=labels.get(order.project_id, ""),
            package=packages.get(order.package_id),
            supplier=companies.get(order.company_id, ""),
            buyers=buyers,
            milestones=milestones.get(order.id, ()),
            receipt=receipts.get(order.id),
            action=actions.get(order.number),
            history=history.get(order.id, ()),
            risk=risks.get(order.number),
            authors=authors,
            reference_date=reference_date,
        )
        for order in orders
    )


def _order_risks(session: Session, numbers: Sequence[str]) -> dict[str, OrderRiskLine]:
    """Os riscos sugeridos dos pedidos, pela fachada da Riscos (D9, ISSUE-067)."""
    from src.modulos.riscos import service as riscos

    found = riscos.diligence_risks(session, numbers=[number for number in numbers if number])
    return {
        number: OrderRiskLine(code=risk.code, title=risk.title, situation=risk.situation)
        for number, risk in found.items()
    }


def _order_milestones_by_order(
    session: Session, order_ids: Collection[int]
) -> dict[int, tuple[PurchaseOrderMilestone, ...]]:
    if not order_ids:
        return {}
    statement = (
        select(PurchaseOrderMilestone)
        .where(PurchaseOrderMilestone.order_id.in_(order_ids))
        .order_by(PurchaseOrderMilestone.order_id, PurchaseOrderMilestone.position)
    )
    grouped: dict[int, list[PurchaseOrderMilestone]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.order_id, []).append(row)
    return {order_id: tuple(rows) for order_id, rows in grouped.items()}


def _receipts_by_order(session: Session, order_ids: Collection[int]) -> dict[int, DeliveryReceipt]:
    if not order_ids:
        return {}
    statement = select(DeliveryReceipt).where(DeliveryReceipt.order_id.in_(order_ids))
    return {row.order_id: row for row in session.scalars(statement)}


def _order_history_by_order(session: Session, order_ids: Collection[int]) -> dict[int, list[Any]]:
    if not order_ids:
        return {}
    statement = (
        select(audit.AuditEntry)
        .where(
            audit.AuditEntry.entity == ORDER_HISTORY_ENTITY,
            audit.AuditEntry.record_id.in_(order_ids),
        )
        .order_by(audit.AuditEntry.occurred_at, audit.AuditEntry.id)
    )
    grouped: dict[int, list[Any]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.record_id, []).append(row)
    return grouped


def _order_actions(
    session: Session,
    *,
    user: User,
    orders: Sequence[PurchaseOrder],
    reference_date: date,
) -> dict[str, OrderActionLine]:
    """The open diligence action of each order, read from the Central (never from ``acao``)."""
    from src.modulos.central_acoes import service as central_acoes

    counts = central_acoes.count_actions_of_origin(
        session,
        user=user,
        origin_kind=DILIGENCE_ORIGIN,
        references=[order.number for order in orders],
        reference_date=reference_date,
    )
    return {
        number: OrderActionLine(subject=count.open_subject, due_date=count.open_due)
        for number, count in counts.items()
        if count.open and count.open_subject
    }


def _order_line(
    order: PurchaseOrder,
    *,
    project: str,
    package: PurchasePackage | None,
    supplier: str,
    buyers: Mapping[int, str],
    milestones: Sequence[PurchaseOrderMilestone],
    receipt: DeliveryReceipt | None,
    action: OrderActionLine | None,
    history: Sequence[Any],
    risk: OrderRiskLine | None,
    authors: Mapping[int, str],
    reference_date: date,
) -> OrderLine:
    rows = tuple(_milestone_line(row, reference_date=reference_date) for row in milestones)
    delivered = order.delivery is not None
    slack = calculations.required_on_site_slack(order.ros, order.delivery or order.forecast)
    band = calculations.slack_band(slack)
    overdue = sum(1 for row in rows if row.situation == calculations.MILESTONE_OVERDUE)
    situation = calculations.order_situation(
        delivered=delivered, band=band, has_overdue=overdue > 0
    )
    return OrderLine(
        id=order.id,
        project_id=order.project_id,
        project_label=project,
        number=order.number,
        package_id=order.package_id,
        package_code=package.code if package is not None else "",
        company_id=order.company_id,
        supplier=supplier,
        description=order.description,
        value_cents=order.value_cents,
        lli=order.lli,
        emission=order.emission,
        contractual_date=order.contractual_date,
        forecast=order.forecast,
        ros=order.ros,
        delivery=order.delivery,
        buyer_id=package.buyer_id if package is not None else None,
        buyer=buyers.get(package.buyer_id, "") if package is not None else "",
        milestones=rows,
        receipt=(
            ReceiptLine(
                id=receipt.id,
                date=receipt.on,
                checked=receipt.checked,
                damaged=receipt.damaged,
                damage_description=receipt.damage_description or "",
                pending=receipt.pending or "",
            )
            if receipt is not None
            else None
        ),
        action=action,
        history=tuple(
            OrderHistoryLine(
                date=line.occurred_at.date(),
                author=authors.get(_after_int(line.after, ORDER_HISTORY_AUTHOR), ""),
                text=str(_after(line.after, ORDER_HISTORY_TEXT)),
            )
            for line in history
        ),
        risk=risk,
        slack_days=slack,
        band=band,
        situation=situation,
        critical=not delivered and slack is not None and slack < 0,
        overdue_milestones=overdue,
        version=order.version,
    )


def _milestone_line(row: PurchaseOrderMilestone, *, reference_date: date) -> OrderMilestoneLine:
    read = calculations.milestone_situation(
        baseline=row.baseline_date,
        forecast=row.forecast_date,
        real=row.real_date,
        reference_date=reference_date,
    )
    return OrderMilestoneLine(
        position=row.position,
        name=row.name,
        baseline=row.baseline_date,
        forecast=row.forecast_date,
        real=row.real_date,
        situation=read.situation,
        deviation_days=read.deviation_days,
        days_overdue=read.days_overdue,
    )


def _after(after: Mapping[str, Any] | None, key: str) -> Any:
    return (after or {}).get(key)


def _after_int(after: Mapping[str, Any] | None, key: str) -> int:
    value = _after(after, key)
    return value if isinstance(value, int) else 0


def _matches_order(line: OrderLine, filters: OrderFilters) -> bool:
    if filters.situation == validation.ORDER_SITUATION_OPEN and line.delivered:
        return False
    if filters.band == "critico" and not line.critical:
        return False
    if filters.band == "atencao" and line.situation != calculations.ORDER_WARNING:
        return False
    if filters.band == "vencidos" and not line.overdue_milestones:
        return False
    if filters.search:
        searched = " ".join((line.number, line.description, line.supplier, line.package_code))
        if _normalize(filters.search) not in _normalize(searched):
            return False
    return True


def _order_summary(universe: Sequence[OrderLine], *, reference_date: date) -> OrderSummary:
    opened = [line for line in universe if not line.delivered]
    delivered = [line for line in universe if line.delivered]
    return OrderSummary(
        open_orders=len(opened),
        open_cents=sum(line.value_cents for line in opened),
        expected_open=sum(1 for line in universe if line.contractual_date > reference_date),
        critical=sum(1 for line in universe if line.critical),
        lli_critical=sum(1 for line in universe if line.critical and line.lli),
        warning=sum(1 for line in universe if line.situation == calculations.ORDER_WARNING),
        overdue_milestones=sum(line.overdue_milestones for line in universe),
        delivered=len(delivered),
        delivered_on_time=sum(
            1
            for line in delivered
            if line.contractual_delay_days is not None and line.contractual_delay_days <= 0
        ),
        otd=calculations.on_time_delivery(
            (line.delivery, line.contractual_date) for line in universe
        ),
    )


# ── Writing the milestone, the receipt and the action ────────────────────────────────────────


def update_order_milestone(
    session: Session,
    *,
    user: User,
    scope: Scope,
    order_id: int,
    data: MilestoneInput,
    reference_date: date,
) -> OrderSave:
    """Update one manufacturing milestone of an order: realize it or reprogram its forecast.

    The realization demands the previous milestone done and a date up to the reference; the
    forecast may not fall in the past and may drag the following milestones by the same amount
    of days (the cascade of the prototype). A negative slack opens the diligence action in the
    Central, once (the guard is in ``_open_diligence_action``).
    """
    rbac.require(user, Permission.WRITE)
    order = _order_or_refuse(session, scope=scope, order_id=order_id)
    rows = list(_order_milestones_by_order(session, [order.id]).get(order.id, ()))
    problems = _milestone_problems(rows, data, reference_date=reference_date)
    if problems:
        raise InvalidDataError(problems)
    text = _apply_milestone(session, user=user, rows=rows, data=data)
    _write_order_forecast(session, user=user, order=order, value=rows[-1].forecast_date)
    comment = data.comment.strip()
    _append_order_history(
        session,
        user=user,
        order=order,
        text=f"{text} {comment}".strip(),
        reference_date=reference_date,
    )
    created = _open_diligence_action_if_critical(
        session, user=user, order=order, reference_date=reference_date
    )
    return OrderSave(order_id=order.id, number=order.number, action_created=created)


def _milestone_problems(
    rows: Sequence[PurchaseOrderMilestone], data: MilestoneInput, *, reference_date: date
) -> dict[str, str]:
    if data.index is None or not 1 <= data.index <= len(rows):
        return {"marco": validation.MILESTONE_REQUIRED}
    row = rows[data.index - 1]
    previous = rows[data.index - 2] if data.index > 1 else None
    return validation.milestone_problems(
        data,
        validation.MilestoneContext(
            reference_date=reference_date,
            already_done=row.real_date is not None,
            is_delivery=data.index == len(rows),
            previous_name=previous.name if previous is not None else "",
            previous_real=previous.real_date if previous is not None else None,
        ),
    )


def _apply_milestone(
    session: Session,
    *,
    user: User,
    rows: Sequence[PurchaseOrderMilestone],
    data: MilestoneInput,
) -> str:
    """Write the milestone and, in a reprogramming, drag the following ones; the feed text."""
    index = data.index
    if index is None or not 1 <= index <= len(rows):
        raise InvalidDataError({"marco": validation.MILESTONE_REQUIRED})
    row = rows[index - 1]
    if data.kind == validation.MILESTONE_DONE:
        realized = data.realized
        if realized is None:
            raise InvalidDataError({"realizada": validation.PLAN_DATE_REQUIRED})
        recording.update(
            session,
            user_id=user.id,
            record=row,
            changes={"real_date": realized, "forecast_date": realized},
            version=row.version,
        )
        return f"{row.name} realizado. "
    forecast = data.forecast
    if forecast is None:
        raise InvalidDataError({"previsao": validation.PLAN_DATE_REQUIRED})
    delta = (forecast - row.forecast_date).days if row.forecast_date else 0
    recording.update(
        session,
        user_id=user.id,
        record=row,
        changes={"forecast_date": forecast},
        version=row.version,
    )
    if data.cascade and delta:
        for following in rows[index:]:
            if following.real_date is None and following.forecast_date is not None:
                recording.update(
                    session,
                    user_id=user.id,
                    record=following,
                    changes={"forecast_date": following.forecast_date + timedelta(days=delta)},
                    version=following.version,
                )
    _straighten_forecasts(session, user=user, rows=rows, start=index)
    return f"Previsão de {row.name} para {_brazilian_date(forecast)}. "


def _straighten_forecasts(
    session: Session, *, user: User, rows: Sequence[PurchaseOrderMilestone], start: int
) -> None:
    """The following forecasts never fall before the previous one, as the prototype kept them."""
    for index in range(start, len(rows)):
        following, previous = rows[index], rows[index - 1]
        if (
            following.real_date is None
            and following.forecast_date is not None
            and previous.forecast_date is not None
            and following.forecast_date < previous.forecast_date
        ):
            recording.update(
                session,
                user_id=user.id,
                record=following,
                changes={"forecast_date": previous.forecast_date},
                version=following.version,
            )


def _write_order_forecast(
    session: Session, *, user: User, order: PurchaseOrder, value: date | None
) -> None:
    if value is None or order.forecast == value:
        return
    recording.update(
        session,
        user_id=user.id,
        record=order,
        changes={"forecast": value},
        version=order.version,
    )


def register_receipt(
    session: Session,
    *,
    user: User,
    scope: Scope,
    order_id: int,
    data: ReceiptInput,
    reference_date: date,
    file_name: str | None = None,
    content: bytes = b"",
    storage: Any | None = None,
) -> OrderSave:
    """Register the receipt of an order at the site, with its evidence (D5a).

    The shipment must be done; the date is up to the reference and never before the shipment;
    damages demand their description. The delivery is written on the order and on the last
    milestone, and the receipt row keeps the check, the damages and the pending items.
    """
    rbac.require(user, Permission.WRITE)
    order = _order_or_refuse(session, scope=scope, order_id=order_id)
    rows = list(_order_milestones_by_order(session, [order.id]).get(order.id, ()))
    shipment = rows[4] if len(rows) >= 5 else None
    already = session.scalars(
        select(DeliveryReceipt).where(DeliveryReceipt.order_id == order.id)
    ).first()
    problems = validation.receipt_problems(
        data,
        reference_date=reference_date,
        already_received=order.delivery is not None or already is not None,
        shipment_real=shipment.real_date if shipment is not None else None,
    )
    if problems:
        raise InvalidDataError(problems)
    if file_name:
        problems = _file_problems(file_name, len(content), session, reference_date)
        if problems:
            raise InvalidDataError(problems)
    recording.update(
        session,
        user_id=user.id,
        record=order,
        changes={"delivery": data.date, "forecast": data.date},
        version=order.version,
    )
    if rows:
        delivery_row = rows[-1]
        recording.update(
            session,
            user_id=user.id,
            record=delivery_row,
            changes={"real_date": data.date, "forecast_date": data.date},
            version=delivery_row.version,
        )
    receipt = recording.create(
        session,
        user_id=user.id,
        record=DeliveryReceipt(
            order_id=order.id,
            on=data.date,  # type: ignore[arg-type]
            checked=data.checked,
            damaged=data.damaged,
            damage_description=data.damage_description.strip() or None,
            pending=data.pending.strip() or None,
        ),
    )
    if file_name:
        attachments.upload(
            session,
            user=user,
            new=attachments.NewAttachment(
                origin_table=RECEIPT_ATTACHMENT_TABLE,
                origin_record_id=receipt.id,
                file_name=file_name,
                content=content,
            ),
            reference_date=reference_date,
            storage=storage,
        )
    note = RECEIPT_NOTE + (RECEIPT_DAMAGE_NOTE if data.damaged else "")
    _append_order_history(session, user=user, order=order, text=note, reference_date=reference_date)
    return OrderSave(order_id=order.id, number=order.number)


def open_diligence_action(
    session: Session,
    *,
    user: User,
    scope: Scope,
    order_id: int,
    reference_date: date,
) -> OrderSave:
    """Open the diligence action of an order by hand, once (the button of the pending list)."""
    rbac.require(user, Permission.WRITE)
    order = _order_or_refuse(session, scope=scope, order_id=order_id)
    created = _open_diligence_action_if_critical(
        session, user=user, order=order, reference_date=reference_date, force=True
    )
    if not created:
        raise InvalidDataError(validation.DILIGENCE_ACTION_EXISTS.format(number=order.number))
    return OrderSave(order_id=order.id, number=order.number, action_created=True)


@dataclass(frozen=True)
class SuggestedRiskDefaults:
    """O que o modal de Registrar risco sugerido abre preenchido (os textos do protótipo)."""

    title: str
    probability: int
    impact: int
    impact_cost_cents: int
    owner_id: int | None
    cause: str
    consequence: str
    slack_days: int


def suggested_risk_defaults(
    session: Session, *, scope: Scope, order_id: int
) -> SuggestedRiskDefaults:
    """Os valores de partida do risco sugerido: título, P, I, custo, dono (comprador), causa.

    ``slack < -14`` ou o item LLI elevam o impacto de partida para 4, como o protótipo.
    """
    order = _order_or_refuse(session, scope=scope, order_id=order_id)
    package = session.get(PurchasePackage, order.package_id)
    supplier = configuracoes.list_company_names(session).get(order.company_id, "")
    slack = calculations.required_on_site_slack(order.ros, order.delivery or order.forecast)
    slack_days = slack if slack is not None else 0
    impact = 4 if order.lli or slack_days < -14 else 3
    return SuggestedRiskDefaults(
        title=f"Atraso na entrega de {order.description.lower()} compromete a montagem",
        probability=4,
        impact=impact,
        impact_cost_cents=0,
        owner_id=package.buyer_id if package is not None else None,
        cause=f"Fabricação atrasada no fornecedor {supplier}.",
        consequence="Frente de montagem parada aguardando o equipamento; impacto no caminho crítico.",
        slack_days=slack_days,
    )


def register_suggested_risk(
    session: Session,
    *,
    user: User,
    scope: Scope,
    order_id: int,
    data: SuggestedRiskInput,
    reference_date: date,
) -> OrderSave:
    """Registra o risco sugerido do diligenciamento pela fachada da Riscos, na mesma transação (D9).

    A descrição leva a folga e o ROS, o impacto em prazo é a folga negativa; a categoria da RBS,
    a origem ``Diligenciamento PED-...`` e a avaliação inerente são da fachada da Riscos. Um
    pedido não ganha dois riscos sugeridos (a fachada recusa a duplicidade).
    """
    from src.modulos.riscos import service as riscos

    rbac.require(user, Permission.WRITE)
    order = _order_or_refuse(session, scope=scope, order_id=order_id)
    problems = validation.suggested_risk_problems(data)
    if problems:
        raise InvalidDataError(problems)
    slack = calculations.required_on_site_slack(order.ros, order.delivery or order.forecast)
    slack_days = slack if slack is not None else 0
    result = riscos.create_suggested_risk(
        session,
        user=user,
        data=riscos.SuggestedRiskInput(
            project_id=order.project_id,
            order_number=order.number,
            title=data.title.strip(),
            owner_id=data.owner_id or user.person_id,
            cause=data.cause.strip(),
            consequence=data.consequence.strip(),
            description=(
                f"Folga de {slack_days} dias em relação à data necessária na obra "
                f"(ROS {_brazilian_date(order.ros)})."
            ),
            trigger="",
            probability=data.probability or 4,
            impact=data.impact or 3,
            schedule_impact_days=max(0, -slack_days),
            cost_impact_cents=data.cost_cents or 0,
        ),
        reference_date=reference_date,
    )
    return OrderSave(order_id=order.id, number=order.number, risk_code=result.code)


def _open_diligence_action_if_critical(
    session: Session,
    *,
    user: User,
    order: PurchaseOrder,
    reference_date: date,
    force: bool = False,
) -> bool:
    """Open the action when the order is critical (or by hand); never a second open one."""
    slack = calculations.required_on_site_slack(order.ros, order.delivery or order.forecast)
    if not force and (slack is None or slack >= 0):
        return False
    package = session.get(PurchasePackage, order.package_id)
    buyer_id = package.buyer_id if package is not None else user.person_id
    return _open_diligence_action(
        session,
        user=user,
        order=order,
        buyer_id=buyer_id,
        slack_days=slack if slack is not None else 0,
        reference_date=reference_date,
    )


def _append_order_history(
    session: Session, *, user: User, order: PurchaseOrder, text: str, reference_date: date
) -> None:
    """One line of the order feed, in the audit trail, as the process history does."""
    if not text:
        return
    _append_trail(
        session,
        user=user,
        entity=ORDER_HISTORY_ENTITY,
        record_id=order.id,
        project_id=order.project_id,
        after={
            ORDER_HISTORY_DATE: reference_date.isoformat(),
            ORDER_HISTORY_AUTHOR: user.person_id,
            ORDER_HISTORY_TEXT: text,
        },
    )


def _order_or_refuse(session: Session, *, scope: Scope, order_id: int) -> PurchaseOrder:
    order = session.get(PurchaseOrder, order_id)
    if order is None or not _order_in_scope(scope, order):
        raise InvalidDataError(ORDER_NOT_FOUND_MESSAGE)
    return order


def _order_in_scope(scope: Scope, order: PurchaseOrder) -> bool:
    return scope.is_portfolio or order.project_id == scope.project_id


# ── The ERP import of the order milestones ───────────────────────────────────────────────────


def order_import_problems(
    session: Session,
    *,
    scope: Scope,
    number: str,
    milestone: str,
    forecast: date | None,
    realized: date | None,
    reference_date: date,
) -> dict[str, str]:
    """One message per problem of an imported line: the order, the milestone and the dates."""
    if not number.strip():
        return {"pedido": IMPORT_ORDER_MISSING.format(number=number.strip())}
    order = _order_by_number(session, scope=scope, number=number.strip())
    if order is None:
        return {"pedido": IMPORT_ORDER_MISSING.format(number=number.strip())}
    if milestone.strip() not in DILIGENCE_MILESTONES:
        return {"marco": IMPORT_MILESTONE_INVALID}
    if realized is not None and realized > reference_date:
        return {"realizada": IMPORT_REALIZED_IN_FUTURE}
    if realized is None and forecast is not None and forecast < reference_date:
        return {"previsao": IMPORT_FORECAST_IN_PAST}
    return {}


def apply_order_import_row(
    session: Session,
    *,
    user: User,
    scope: Scope,
    number: str,
    milestone: str,
    forecast: date | None,
    realized: date | None,
    reference_date: date,
) -> None:
    """Write one imported line of the ERP: the forecast or the realization of one milestone.

    As the prototype's import did: a realized line writes the milestone and, on the delivery,
    the order and a receipt stub with the check pending; a forecast line only moves the forecast.
    A negative slack opens the diligence action, once.
    """
    rbac.require(user, Permission.WRITE)
    order = _order_by_number(session, scope=scope, number=number.strip())
    if order is None:
        raise InvalidDataError(IMPORT_ORDER_MISSING.format(number=number.strip()))
    rows = list(_order_milestones_by_order(session, [order.id]).get(order.id, ()))
    position = DILIGENCE_MILESTONES.index(milestone.strip()) + 1
    row = next((item for item in rows if item.position == position), None)
    if row is None:
        raise InvalidDataError(IMPORT_MILESTONE_INVALID)
    if realized is not None:
        recording.update(
            session,
            user_id=user.id,
            record=row,
            changes={"real_date": realized, "forecast_date": realized},
            version=row.version,
        )
        if position == len(DILIGENCE_MILESTONES):
            _write_order_delivery(session, user=user, order=order, value=realized)
    elif forecast is not None and row.real_date is None:
        recording.update(
            session,
            user_id=user.id,
            record=row,
            changes={"forecast_date": forecast},
            version=row.version,
        )
    if rows and rows[-1].forecast_date is not None:
        _write_order_forecast(session, user=user, order=order, value=rows[-1].forecast_date)
    _append_order_history(
        session,
        user=user,
        order=order,
        text=IMPORT_ORDER_NOTE.format(milestone=milestone.strip()),
        reference_date=reference_date,
    )
    _open_diligence_action_if_critical(
        session, user=user, order=order, reference_date=reference_date
    )


def _write_order_delivery(
    session: Session, *, user: User, order: PurchaseOrder, value: date
) -> None:
    """The delivery imported from the ERP: the order, the milestone and a receipt stub."""
    recording.update(
        session,
        user_id=user.id,
        record=order,
        changes={"delivery": value, "forecast": value},
        version=order.version,
    )
    already = session.scalars(
        select(DeliveryReceipt).where(DeliveryReceipt.order_id == order.id)
    ).first()
    if already is None:
        recording.create(
            session,
            user_id=user.id,
            record=DeliveryReceipt(
                order_id=order.id,
                on=value,
                checked=False,
                damaged=False,
                pending=IMPORT_RECEIPT_PENDING,
            ),
        )


def _order_by_number(session: Session, *, scope: Scope, number: str) -> PurchaseOrder | None:
    order = session.scalars(
        select(PurchaseOrder).where(PurchaseOrder.number == number)
    ).one_or_none()
    if order is None or not _order_in_scope(scope, order):
        return None
    return order


def read_receipt_origin(
    session: Session, *, user: User, record_id: int
) -> attachment_origins.OriginRecord | None:
    """Quem lê as evidências de um recebimento: quem alcança o módulo (D5a)."""
    rbac.require_module(user, MODULE)
    receipt = session.get(DeliveryReceipt, record_id)
    if receipt is None:
        return None
    order = session.get(PurchaseOrder, receipt.order_id)
    if order is None:
        return None
    return attachment_origins.OriginRecord(project_id=order.project_id)


attachment_origins.register(
    attachment_origins.OriginType(
        table=RECEIPT_ATTACHMENT_TABLE, module=MODULE, read=read_receipt_origin
    )
)


# ── Process internals ────────────────────────────────────────────────────────────────────────


def _scoped_packages(session: Session, scope: Scope) -> list[PurchasePackage]:
    """Every package of the scope, by project and code."""
    projects = configuracoes.list_projects(session)
    wanted = [
        project.id for project in projects if scope.is_portfolio or project.id == scope.project_id
    ]
    if not wanted:
        return []
    statement = (
        select(PurchasePackage)
        .where(PurchasePackage.project_id.in_(wanted))
        .order_by(PurchasePackage.project_id, PurchasePackage.code)
    )
    return list(session.scalars(statement))


def _processes_by_package(
    session: Session, package_ids: Collection[int]
) -> dict[int, PurchaseProcess]:
    if not package_ids:
        return {}
    statement = select(PurchaseProcess).where(PurchaseProcess.package_id.in_(package_ids))
    return {process.package_id: process for process in session.scalars(statement)}


def _process_row(session: Session, package_id: int) -> PurchaseProcess:
    process = session.scalars(
        select(PurchaseProcess).where(PurchaseProcess.package_id == package_id)
    ).one_or_none()
    if process is None:
        raise InvalidDataError(validation.PROCESS_NOT_FOUND)
    return process


def _invitees_by_process(
    session: Session, process_ids: Collection[int]
) -> dict[int, list[ProcessInvitee]]:
    if not process_ids:
        return {}
    statement = (
        select(ProcessInvitee)
        .where(ProcessInvitee.process_id.in_(process_ids))
        .order_by(ProcessInvitee.id)
    )
    grouped: dict[int, list[ProcessInvitee]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.process_id, []).append(row)
    return grouped


def _proposals_by_process(
    session: Session, process_ids: Collection[int]
) -> dict[int, list[ProcessProposal]]:
    if not process_ids:
        return {}
    statement = (
        select(ProcessProposal)
        .where(ProcessProposal.process_id.in_(process_ids))
        .order_by(ProcessProposal.id)
    )
    grouped: dict[int, list[ProcessProposal]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.process_id, []).append(row)
    return grouped


def _proposal_rows(session: Session, process_id: int) -> list[ProcessProposal]:
    statement = (
        select(ProcessProposal)
        .where(ProcessProposal.process_id == process_id)
        .order_by(ProcessProposal.id)
    )
    return list(session.scalars(statement))


def _negotiations_by_process(
    session: Session, process_ids: Collection[int]
) -> dict[int, list[ProcessNegotiation]]:
    if not process_ids:
        return {}
    statement = (
        select(ProcessNegotiation)
        .where(ProcessNegotiation.process_id.in_(process_ids))
        .order_by(ProcessNegotiation.id)
    )
    grouped: dict[int, list[ProcessNegotiation]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.process_id, []).append(row)
    return grouped


def _history_by_process(session: Session, process_ids: Collection[int]) -> dict[int, list[Any]]:
    if not process_ids:
        return {}
    statement = (
        select(audit.AuditEntry)
        .where(
            audit.AuditEntry.entity == PROCESS_HISTORY_ENTITY,
            audit.AuditEntry.record_id.in_(process_ids),
        )
        .order_by(audit.AuditEntry.occurred_at, audit.AuditEntry.id)
    )
    grouped: dict[int, list[Any]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.record_id, []).append(row)
    return grouped


def _supplier_situations(session: Session) -> dict[int, str]:
    """The situation of the qualification of each company (the module's own register)."""
    statement = select(Supplier.company_id, Supplier.situation)
    return {row.company_id: row.situation for row in session.execute(statement)}


def _supplier_choices(session: Session) -> tuple[SupplierChoice, ...]:
    """The qualified companies, by name: what the RFx form offers as invitees."""
    companies = {
        company.id: company
        for company in configuracoes.list_company_summaries(session)
        if company.kind != GERENCIADORA
    }
    suppliers = _suppliers_by_company(session, list(companies))
    categories = _categories_by_supplier(session, [supplier.id for supplier in suppliers.values()])
    choices = [
        SupplierChoice(
            company_id=company_id,
            name=companies[company_id].name,
            situation=supplier.situation,
            categories=tuple(category.category for category in categories.get(supplier.id, ())),
        )
        for company_id, supplier in suppliers.items()
    ]
    return tuple(sorted(choices, key=lambda choice: choice.name))


def _company_choices(session: Session) -> tuple[configuracoes.RegisterOption, ...]:
    """The companies of the register that may propose, by name."""
    return tuple(
        configuracoes.RegisterOption(id=company.id, name=company.name)
        for company in sorted(
            (
                company
                for company in configuracoes.list_company_summaries(session)
                if company.kind != GERENCIADORA
            ),
            key=lambda company: company.name,
        )
    )


def _process_parameters(session: Session, *, reference_date: date) -> ProcessParameters:
    """The minimum of proposals and the approval bands of the suprimentos group in force."""
    values = configuracoes.current_group(
        session, group=PROCESS_GROUP, reference_date=reference_date
    )
    initial = configuracoes.INITIAL_PARAMETERS[PROCESS_GROUP]
    minimum = values.get("propostasMinimas", initial["propostasMinimas"])
    bands = values.get("alcadas", initial["alcadas"])
    parsed: list[tuple[int | None, str]] = []
    for band in bands or ():
        if not isinstance(band, Mapping):
            continue
        ceiling = band.get("ate")
        name = band.get("papel")
        if isinstance(ceiling, bool) or not isinstance(ceiling, int):
            ceiling = None
        if isinstance(name, str) and name:
            parsed.append((ceiling, name))
    if not parsed:
        parsed = [(None, str(initial["alcadas"][-1]["papel"]))]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        minimum = int(initial["propostasMinimas"])
    return ProcessParameters(minimum_proposals=minimum, approval_bands=tuple(parsed))


def _milestones_by_package(
    session: Session, package_ids: Collection[int]
) -> dict[int, tuple[PackageMilestone, ...]]:
    if not package_ids:
        return {}
    statement = select(PackageMilestone).where(PackageMilestone.package_id.in_(package_ids))
    grouped: dict[int, dict[str, PackageMilestone]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.package_id, {})[row.milestone] = row
    return {
        package_id: tuple(rows[key] for key in calculations.MILESTONE_KEYS if key in rows)
        for package_id, rows in grouped.items()
    }


def _real_of(milestones: Sequence[PackageMilestone], key: str) -> date | None:
    row = next((item for item in milestones if item.milestone == key), None)
    return row.real_date if row is not None else None


def _plan_of(milestones: Sequence[PackageMilestone], key: str) -> date | None:
    row = next((item for item in milestones if item.milestone == key), None)
    return row.plan_date if row is not None else None


def _forecast_of(milestones: Sequence[PackageMilestone], key: str) -> date | None:
    row = next((item for item in milestones if item.milestone == key), None)
    return row.forecast_date if row is not None else None


def _milestone_row(session: Session, *, package_id: int, key: str) -> PackageMilestone:
    row = session.scalars(
        select(PackageMilestone).where(
            PackageMilestone.package_id == package_id, PackageMilestone.milestone == key
        )
    ).one_or_none()
    if row is None:
        raise InvalidDataError(validation.PACKAGE_NOT_FOUND)
    return row


def _write_real(session: Session, *, user: User, package_id: int, key: str, value: date) -> None:
    row = _milestone_row(session, package_id=package_id, key=key)
    recording.update(
        session,
        user_id=user.id,
        record=row,
        changes={"real_date": value, "forecast_date": None},
        version=row.version,
    )


def _write_forecast(
    session: Session, *, user: User, package_id: int, key: str, value: date
) -> None:
    row = _milestone_row(session, package_id=package_id, key=key)
    if row.real_date is not None:
        return
    recording.update(
        session,
        user_id=user.id,
        record=row,
        changes={"forecast_date": value},
        version=row.version,
    )


def _write_invitees(
    session: Session, *, user: User, process: PurchaseProcess, data: RfxInput
) -> None:
    for company_id in data.invitees:
        recording.create(
            session,
            user_id=user.id,
            record=ProcessInvitee(process_id=process.id, company_id=company_id),
        )
    for name in data.other_invitees:
        recording.create(
            session,
            user_id=user.id,
            record=ProcessInvitee(process_id=process.id, name=name),
        )


def _append_process_history(
    session: Session,
    *,
    user: User,
    line: ProcessLine,
    process: PurchaseProcess,
    stage: str,
    text: str,
    reference_date: date,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """One line of the process feed, in the audit trail, with the stage the action led to."""
    after: dict[str, Any] = {
        HISTORY_DATE: reference_date.isoformat(),
        HISTORY_STAGE: stage,
        HISTORY_AUTHOR: user.person_id,
        HISTORY_TEXT: text,
    }
    if extra:
        after.update(extra)
    _append_trail(
        session,
        user=user,
        entity=PROCESS_HISTORY_ENTITY,
        record_id=process.id,
        project_id=line.project_id,
        after=after,
    )


def _append_trail(
    session: Session,
    *,
    user: User,
    entity: str,
    record_id: int,
    project_id: int,
    after: Mapping[str, Any],
) -> None:
    audit.append(
        session,
        audit.TrailLine(
            user_id=user.id,
            entity=entity,
            record_id=record_id,
            action=audit.CREATED,
            after=dict(after),
            project_id=project_id,
        ),
    )


def _next_process_number(session: Session, *, kind: str, reference_date: date) -> str:
    numbers = list(session.scalars(select(PurchaseProcess.number)))
    return calculations.next_process_number(
        numbers, service=calculations.is_service(kind), year=reference_date.year
    )


def _best_name(session: Session, process: PurchaseProcess) -> str:
    proposals = _proposal_rows(session, process.id)
    lowest = min(
        (row.value_cents for row in proposals if row.technically_approved is True), default=None
    )
    entries = []
    for row in proposals:
        commercial = (
            calculations.commercial_score(row.value_cents, lowest)
            if row.technically_approved is True
            else None
        )
        entries.append(
            (
                row.id,
                calculations.final_score(
                    row.technical_score,
                    commercial,
                    process.weight_technical,
                    process.weight_commercial,
                ),
                row.value_cents,
            )
        )
    ranks = dict(calculations.proposal_ranking(entries))
    best_id = next((proposal_id for proposal_id, rank in ranks.items() if rank == 1), None)
    row = next((item for item in proposals if item.id == best_id), None)
    return _proposal_display(session, row) if row is not None else "·"


def _proposal_display(session: Session, proposal: ProcessProposal | None) -> str:
    """The name the feed prints for a proposal: the free name or the company of the register."""
    if proposal is None:
        return ""
    if proposal.name:
        return proposal.name
    return _company_name(session, proposal.company_id)


def _company_name(session: Session, company_id: int | None) -> str:
    if company_id is None:
        return ""
    return next(
        (
            company.name
            for company in configuracoes.list_company_summaries(session)
            if company.id == company_id
        ),
        "",
    )


def _proposal_changes(row: ProcessProposal, changes: Mapping[str, Any]) -> dict[str, Any]:
    return {field: value for field, value in changes.items() if getattr(row, field) != value}


def _process_changes(row: PurchaseProcess, changes: Mapping[str, Any]) -> dict[str, Any]:
    return {field: value for field, value in changes.items() if getattr(row, field) != value}


def _file_problems(
    file_name: str | None, size_bytes: int, session: Session, reference_date: date
) -> dict[str, str]:
    """The file of the proposal checked before anything is written (D5a)."""
    name = attachments.clean_name(file_name)
    if not name:
        return {attachments.FILE_FIELD: attachments.NO_FILE_MESSAGE}
    limits = attachments.current_limits(session, reference_date=reference_date)
    problem = attachments.file_problem(name, size_bytes, limits)
    return {attachments.FILE_FIELD: problem} if problem else {}


def _process_or_refuse(
    session: Session, *, user: User, scope: Scope, package_id: int, reference_date: date
) -> ProcessLine:
    line = _line_in_scope(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    if line is None:
        raise InvalidDataError(validation.PACKAGE_NOT_FOUND)
    return line


def _require_stage(line: ProcessLine, *expected: str) -> None:
    if line.stage not in expected:
        raise InvalidDataError({"geral": validation.ACTION_NOT_IN_STAGE.format(stage=line.stage)})


def _eac_balance(session: Session, *, line: ProcessLine, reference_date: date) -> int | None:
    """The saldo a comprometer of the package's EAC item, read from the Financeiro (D9)."""
    balances = financeiro.cost_item_balances(
        session, project_id=line.project_id, reference_date=reference_date
    )
    return next(
        (balance.saldo_cents for balance in balances if balance.item_id == line.eac_item_id), None
    )


def _project_start(session: Session, project_id: int) -> date | None:
    """The start of the project, which the LLI gate compares with the requisition."""
    project = next(
        (item for item in configuracoes.list_projects(session) if item.id == project_id), None
    )
    return project.start_date if project is not None else None


def _order_number(session: Session, *, package_id: int) -> str | None:
    """The number of the order the package originated, for the ficha of the process."""
    return session.scalar(
        select(PurchaseOrder.number).where(PurchaseOrder.package_id == package_id)
    )


def _next_order_number(session: Session, *, reference_date: date) -> str:
    """The next number of the global order series of the year, as the prototype numbered."""
    numbers = list(session.scalars(select(PurchaseOrder.number)))
    return numbering.next_series_number(
        numbers,
        prefix=calculations.PURCHASE_ORDER_PREFIX,
        year=reference_date.year,
        digits=4,
    )


def read_proposal_origin(
    session: Session, *, user: User, record_id: int
) -> attachment_origins.OriginRecord | None:
    """Quem lê o PDF de uma proposta: quem alcança o módulo (D5a)."""
    rbac.require_module(user, MODULE)
    proposal = session.get(ProcessProposal, record_id)
    if proposal is None:
        return None
    process = session.get(PurchaseProcess, proposal.process_id)
    if process is None:
        return None
    package = session.get(PurchasePackage, process.package_id)
    if package is None:
        return None
    return attachment_origins.OriginRecord(project_id=package.project_id)


attachment_origins.register(
    attachment_origins.OriginType(
        table=PROPOSAL_ATTACHMENT_TABLE, module=MODULE, read=read_proposal_origin
    )
)


def _required_date(value: date | None, message: str) -> date:
    """A date the checks already approved; ``None`` here is a mistake of the caller."""
    if value is None:
        raise InvalidDataError(message)
    return value


# ── The final evaluation of a contract (D9, ISSUE-034) ───────────────────────────────────────


def apply_final_evaluation(
    session: Session,
    user: User,
    evaluation: financeiro.FinalEvaluation,
    reference_date: date,
) -> None:
    """Update the qualification when the final evaluation of a contract is registered (D9).

    Only an existing qualification is updated: the cadastro of a supplier is a human act ("Novo
    fornecedor"), not a side effect of a contract. The class of the evaluation leads the
    situation (A and B qualify, C restricts, D blocks); the change is a new history fact with an
    automatic justification, in the same transaction of the evaluation.
    """
    supplier = _supplier_of_company(session, evaluation.company_id)
    if supplier is None:
        return
    situation = calculations.situation_for_evaluation_class(evaluation.score_class)
    if situation is None or situation == supplier.situation:
        return
    previous = supplier.situation
    recording.update(
        session,
        user_id=user.id,
        record=supplier,
        changes={"situation": situation},
        version=supplier.version,
    )
    recording.create(
        session,
        user_id=user.id,
        record=SupplierHistory(
            supplier_id=supplier.id,
            by_id=user.person_id,
            on=reference_date,
            from_situation=previous,
            to_situation=situation,
            justification=FINAL_EVALUATION_JUSTIFICATION.format(
                contract=evaluation.contract_number,
                score=evaluation.score,
                score_class=evaluation.score_class,
            ),
        ),
    )


financeiro.register_final_evaluation_listener(apply_final_evaluation)


# ── The map of purchases (ISSUE-062) ─────────────────────────────────────────────────────────

# The parameter of the group that carries the measurement weight of each of the twelve milestones.
MAS_WEIGHTS_KEY = "pesosMarcos"

# The twelve milestones in order: key, label, half and (for manufacturing) the position in the
# standard schedule of the order. The acquisition half has no position (``-1``).
MAS_MILESTONE_DEFINITIONS: tuple[tuple[str, str, str, int], ...] = (
    *(
        (key, label, calculations.MAS_ACQUISITION, -1)
        for key, label in calculations.ACQUISITION_MILESTONES
    ),
    *(
        (key, label, calculations.MAS_FABRICATION, position)
        for key, label, position in calculations.MAS_FABRICATION_MILESTONES
    ),
)


@dataclass(frozen=True)
class MasMilestoneLine:
    """One of the twelve milestones of the map, already read against the reference date.

    ``baseline`` is the LB (of the plan or of the order's contractual schedule; estimated for a
    package still without an order), ``forecast`` the reprogramming and ``real`` the realization;
    ``weight`` is the measurement weight of the parameter and ``applicable`` whether the milestone
    belongs to the package at all (the manufacturing half of a service/EPC package does not).
    """

    key: str
    label: str
    phase: str
    baseline: date | None
    forecast: date | None
    real: date | None
    weight: int
    applicable: bool
    estimated: bool
    situation: str
    deviation_days: int | None
    days_overdue: int

    @property
    def done(self) -> bool:
        """Whether the milestone has a real date."""
        return self.real is not None

    @property
    def display_date(self) -> date | None:
        """The date the cell shows: the real one, else the forecast, else the baseline."""
        return self.real or self.forecast or self.baseline


@dataclass(frozen=True)
class MasLine:
    """One package of the map: the record, its twelve milestones and everything calculated."""

    id: int
    project_id: int
    project_label: str
    code: str
    scope: str
    kind: str
    modality: str
    discipline_id: int | None
    discipline: str
    buyer_id: int
    buyer: str
    lli: bool
    supplier_id: int | None
    supplier: str
    eac_code: str
    eac_description: str
    estimate_cents: int
    adjudicated_cents: int | None
    value_cents: int
    process_number: str | None
    order_number: str | None
    contract_number: str | None
    ros: date | None
    delivery_forecast: date | None
    slack_days: int | None
    band: str
    situation: str
    concluded: bool
    delivered: bool
    stage: str
    milestones: tuple[MasMilestoneLine, ...]
    progress: calculations.MasProgress
    overdue_milestones: int
    late_milestones: int

    def milestone(self, key: str) -> MasMilestoneLine | None:
        """The milestone named by key, or ``None`` when the map has no such row."""
        return next((item for item in self.milestones if item.key == key), None)

    @property
    def service(self) -> bool:
        """Whether the package generates a contract: service and EPC."""
        return calculations.is_service(self.kind)

    @property
    def critical(self) -> bool:
        """Whether the line reads critical: negative slack and not concluded."""
        return self.situation == calculations.MAS_CRITICAL

    @property
    def with_baseline(self) -> bool:
        """Whether the line has any baseline at all."""
        return any(item.baseline is not None for item in self.milestones)

    @property
    def next_milestone(self) -> MasMilestoneLine | None:
        """The first applicable milestone without a real date, or ``None`` when all are done."""
        return next(
            (item for item in self.milestones if item.applicable and not item.done),
            None,
        )

    @property
    def current_stage(self) -> str:
        """Where the package reads: the situation when concluded, else the next milestone."""
        if self.concluded:
            return self.situation
        next_milestone = self.next_milestone
        return next_milestone.label if next_milestone is not None else self.stage

    @property
    def realized_pct(self) -> Decimal:
        """The realized progress of the package."""
        return self.progress.realized_pct

    @property
    def planned_pct(self) -> Decimal:
        """The planned progress of the package."""
        return self.progress.planned_pct


@dataclass(frozen=True)
class MasMilestoneColumn:
    """One column of the map: the milestone, its half and its measurement weight."""

    key: str
    label: str
    phase: str
    weight: int


@dataclass(frozen=True)
class MasMilestoneTotal:
    """The footer of a milestone column: realizados over previstos on the baseline."""

    key: str
    realized: int
    planned: int


@dataclass(frozen=True)
class MasSummary:
    """The KPIs of the map, counted on the whole universe (the filters cut the table)."""

    items: int
    with_baseline: int
    concluded: int
    on_time: int
    warning: int
    critical: int
    overdue_milestones: int
    late_milestones: int
    realized_milestones: int
    progress: calculations.MasProgress

    @property
    def realized_pct(self) -> Decimal:
        """The procurement progress realized, weighted by the value of the packages."""
        return self.progress.realized_pct

    @property
    def planned_pct(self) -> Decimal:
        """The procurement progress planned on the baseline."""
        return self.progress.planned_pct

    @property
    def index(self) -> Decimal | None:
        """Real over planned; ``None`` when nothing is planned yet."""
        return self.progress.index

    @property
    def late_share(self) -> Decimal | None:
        """The percentage of the realized milestones done after the baseline.

        One decimal, half up, as the prototype printed it (``marcosComAtraso / realizados * 100``);
        without any realization there is no share.
        """
        if not self.realized_milestones:
            return None
        value = (
            Decimal(self.late_milestones) / Decimal(self.realized_milestones) * calculations.HUNDRED
        )
        return value.quantize(calculations.ONE_TENTH, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MasListing:
    """What the map shows for a filter: the lines, the KPIs, the columns and the filter choices."""

    lines: tuple[MasLine, ...]
    summary: MasSummary
    columns: tuple[MasMilestoneColumn, ...]
    totals: tuple[MasMilestoneTotal, ...]
    filters: MasFilters
    buyers: tuple[configuracoes.RegisterOption, ...]
    suppliers: tuple[configuracoes.RegisterOption, ...]
    disciplines: tuple[configuracoes.RegisterOption, ...]
    reference_date: date

    @property
    def total(self) -> int:
        """How many packages the filter holds."""
        return len(self.lines)


# ── Reading the map ──────────────────────────────────────────────────────────────────────────


def list_mas(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: MasFilters,
    reference_date: date,
) -> MasListing:
    """The map for the filters: the lines, the KPIs of the whole universe and the columns."""
    universe = _mas_universe(session, user=user, scope=scope, reference_date=reference_date)
    shown = _mas_sorted(
        (line for line in universe if _matches_mas(line, filters)), order=filters.order
    )
    weights = _milestone_weights(session, reference_date=reference_date)
    columns = _mas_columns(filters.phase, weights=weights)
    return MasListing(
        lines=shown,
        summary=_mas_summary(universe),
        columns=columns,
        totals=_mas_totals(shown, columns=columns, reference_date=reference_date),
        filters=filters,
        buyers=_distinct_options((line.buyer_id, line.buyer) for line in universe),
        suppliers=_distinct_options(
            (line.supplier_id, line.supplier) for line in universe if line.supplier_id is not None
        ),
        disciplines=tuple(
            configuracoes.RegisterOption(id=discipline_id, name=name)
            for discipline_id, name in sorted(
                configuracoes.discipline_names_by_id(session).items(),
                key=lambda item: item[1],
            )
        ),
        reference_date=reference_date,
    )


def find_mas_package(
    session: Session, *, user: User, scope: Scope, package_id: int, reference_date: date
) -> MasLine | None:
    """The line of one package, or ``None`` when it is not in the scope."""
    for line in _mas_universe(session, user=user, scope=scope, reference_date=reference_date):
        if line.id == package_id:
            return line
    return None


def _mas_universe(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> tuple[MasLine, ...]:
    """Every package of the scope with its twelve milestones, order, process and contract."""
    packages = _package_universe(session, user=user, scope=scope, reference_date=reference_date)
    if not packages:
        return ()
    orders = _orders_by_package(session, [line.id for line in packages])
    milestones = _order_milestones_by_order(session, [order.id for order in orders.values()])
    processes = _processes_by_package(session, [line.id for line in packages])
    companies = configuracoes.list_company_names(session)
    contracts = financeiro.purchase_contracts_by_package(session, [line.id for line in packages])
    weights = _milestone_weights(session, reference_date=reference_date)
    built: list[MasLine] = []
    for line in packages:
        order = orders.get(line.id)
        built.append(
            _mas_line(
                line,
                order=order,
                order_milestones=milestones.get(order.id, ()) if order is not None else (),
                process=processes.get(line.id),
                contract=contracts.get(line.id),
                companies=companies,
                weights=weights,
                reference_date=reference_date,
            )
        )
    return tuple(built)


def _orders_by_package(session: Session, package_ids: Collection[int]) -> dict[int, PurchaseOrder]:
    """The order of each package, by package; the lowest id wins when there is more than one."""
    if not package_ids:
        return {}
    statement = (
        select(PurchaseOrder)
        .where(PurchaseOrder.package_id.in_(package_ids))
        .order_by(PurchaseOrder.id)
    )
    orders: dict[int, PurchaseOrder] = {}
    for order in session.scalars(statement):
        orders.setdefault(order.package_id, order)
    return orders


def _milestone_weights(session: Session, *, reference_date: date) -> Mapping[str, int]:
    """The measurement weight of each milestone, from the group ``suprimentos`` in force.

    The parameters arrive with the group (``pesosMarcos``, sum 100); without a version in force
    the initial values of the platform apply. A value that is not a whole number is ignored, as
    the facade ignores the malformed bands of the approval.
    """
    values = configuracoes.current_group(
        session, group=PROCESS_GROUP, reference_date=reference_date
    )
    initial = configuracoes.INITIAL_PARAMETERS[PROCESS_GROUP][MAS_WEIGHTS_KEY]
    raw = values.get(MAS_WEIGHTS_KEY, initial)
    weights: dict[str, int] = {}
    for key, value in (raw or {}).items():
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        weights[key] = value
    return weights or {key: int(value) for key, value in initial.items()}


def _mas_line(
    line: PackageLine,
    *,
    order: PurchaseOrder | None,
    order_milestones: Sequence[PurchaseOrderMilestone],
    process: PurchaseProcess | None,
    contract: financeiro.PurchaseContractRef | None,
    companies: Mapping[int, str],
    weights: Mapping[str, int],
    reference_date: date,
) -> MasLine:
    """The line of one package: the twelve milestones and everything calculated from them."""
    service = calculations.is_service(line.kind)
    milestones = tuple(
        _mas_milestone(
            line,
            key=key,
            label=label,
            phase=phase,
            position=position,
            service=service,
            order=order,
            order_milestones=order_milestones,
            weight=weights.get(key, 0),
            reference_date=reference_date,
        )
        for key, label, phase, position in MAS_MILESTONE_DEFINITIONS
    )
    order_value = order.value_cents if order is not None else None
    recommendation_value = process.recommendation_value_cents if process is not None else None
    contract_value = contract.value_cents if contract is not None else None
    adjudicated = next(
        (
            value
            for value in (order_value, recommendation_value, contract_value)
            if value is not None
        ),
        None,
    )
    supplier_id = _mas_supplier_id(order=order, process=process)
    delivery_forecast = _mas_delivery_forecast(line, milestones, service=service, order=order)
    slack = calculations.required_on_site_slack(line.ros, delivery_forecast)
    band = calculations.slack_band(slack)
    concluded = _mas_concluded(line, service=service, order=order)
    overdue = sum(1 for item in milestones if item.situation == calculations.MILESTONE_OVERDUE)
    return MasLine(
        id=line.id,
        project_id=line.project_id,
        project_label=line.project_label,
        code=line.code,
        scope=line.scope,
        kind=line.kind,
        modality=line.modality,
        discipline_id=line.discipline_id,
        discipline=line.discipline,
        buyer_id=line.buyer_id,
        buyer=line.buyer,
        lli=line.lli,
        supplier_id=supplier_id,
        supplier=companies.get(supplier_id, "") if supplier_id is not None else "",
        eac_code=line.eac_code,
        eac_description=line.eac_description,
        estimate_cents=line.estimate_cents,
        adjudicated_cents=adjudicated,
        value_cents=adjudicated if adjudicated is not None else line.estimate_cents,
        process_number=process.number if process is not None else None,
        order_number=order.number if order is not None else None,
        contract_number=contract.number if contract is not None else None,
        ros=line.ros,
        delivery_forecast=delivery_forecast,
        slack_days=slack,
        band=band,
        situation=calculations.mas_line_situation(
            concluded=concluded, service=service, band=band, has_overdue=overdue > 0
        ),
        concluded=concluded,
        delivered=order is not None and order.delivery is not None,
        stage=line.stage,
        milestones=milestones,
        progress=calculations.package_progress(
            (
                calculations.MasProgressMilestone(
                    weight=item.weight,
                    applicable=item.applicable,
                    baseline=item.baseline,
                    real=item.real,
                )
                for item in milestones
            ),
            reference_date=reference_date,
        ),
        overdue_milestones=overdue,
        late_milestones=sum(
            1 for item in milestones if item.situation == calculations.MILESTONE_LATE
        ),
    )


def _mas_milestone(
    line: PackageLine,
    *,
    key: str,
    label: str,
    phase: str,
    position: int,
    service: bool,
    order: PurchaseOrder | None,
    order_milestones: Sequence[PurchaseOrderMilestone],
    weight: int,
    reference_date: date,
) -> MasMilestoneLine:
    """One milestone of the map: the acquisition from the plan, the manufacturing from the order."""
    if phase == calculations.MAS_ACQUISITION:
        return _acquisition_milestone(
            line, key=key, label=label, weight=weight, reference_date=reference_date
        )
    if service:
        return _not_applicable_milestone(
            key=key, label=label, weight=weight, reference_date=reference_date
        )
    if order is not None:
        return _order_milestone(
            order_milestones,
            key=key,
            label=label,
            position=position,
            weight=weight,
            reference_date=reference_date,
        )
    return _estimated_milestone(
        line, key=key, label=label, position=position, weight=weight, reference_date=reference_date
    )


def _acquisition_milestone(
    line: PackageLine, *, key: str, label: str, weight: int, reference_date: date
) -> MasMilestoneLine:
    milestone = line.milestone(key)
    baseline = milestone.plan if milestone is not None else None
    real = milestone.real if milestone is not None else None
    forecast = None if real is not None else (milestone.forecast if milestone is not None else None)
    read = calculations.milestone_situation(
        baseline=baseline, forecast=forecast, real=real, reference_date=reference_date
    )
    return _mas_milestone_line(
        key=key,
        label=label,
        phase=calculations.MAS_ACQUISITION,
        baseline=baseline,
        forecast=forecast,
        real=real,
        weight=weight,
        applicable=True,
        estimated=False,
        read=read,
    )


def _not_applicable_milestone(
    *, key: str, label: str, weight: int, reference_date: date
) -> MasMilestoneLine:
    """A manufacturing milestone of a service/EPC package: the contract has no fabrication."""
    read = calculations.milestone_situation(
        baseline=None, forecast=None, real=None, reference_date=reference_date, applicable=False
    )
    return _mas_milestone_line(
        key=key,
        label=label,
        phase=calculations.MAS_FABRICATION,
        baseline=None,
        forecast=None,
        real=None,
        weight=weight,
        applicable=False,
        estimated=False,
        read=read,
    )


def _order_milestone(
    order_milestones: Sequence[PurchaseOrderMilestone],
    *,
    key: str,
    label: str,
    position: int,
    weight: int,
    reference_date: date,
) -> MasMilestoneLine:
    """The manufacturing milestone of a package with an order: the row of the contractual schedule."""
    row = next((item for item in order_milestones if item.position == position + 1), None)
    baseline = row.baseline_date if row is not None else None
    real = row.real_date if row is not None else None
    forecast = None if real is not None else (row.forecast_date if row is not None else None)
    read = calculations.milestone_situation(
        baseline=baseline, forecast=forecast, real=real, reference_date=reference_date
    )
    return _mas_milestone_line(
        key=key,
        label=label,
        phase=calculations.MAS_FABRICATION,
        baseline=baseline,
        forecast=forecast,
        real=real,
        weight=weight,
        applicable=True,
        estimated=False,
        read=read,
    )


def _estimated_milestone(
    line: PackageLine,
    *,
    key: str,
    label: str,
    position: int,
    weight: int,
    reference_date: date,
) -> MasMilestoneLine:
    """The manufacturing milestone of a package still without an order: estimated on the shares.

    The baseline interpolates between the planned order and the ROS and the forecast between the
    forecast order (or the planned one) and the ROS; the milestone reads as estimated so the
    screen and the exports carry the "LB estimada" warning.
    """
    pedido = line.milestone(calculations.ORDER_MILESTONE)
    start = pedido.plan if pedido is not None else None
    forecast_start = pedido.forecast if pedido is not None and pedido.forecast else start
    baseline = calculations.estimated_fabrication_date(start, line.ros, position)
    forecast = calculations.estimated_fabrication_date(forecast_start, line.ros, position)
    read = calculations.milestone_situation(
        baseline=baseline, forecast=forecast, real=None, reference_date=reference_date
    )
    return _mas_milestone_line(
        key=key,
        label=label,
        phase=calculations.MAS_FABRICATION,
        baseline=baseline,
        forecast=forecast,
        real=None,
        weight=weight,
        applicable=True,
        estimated=baseline is not None,
        read=read,
    )


def _mas_milestone_line(
    *,
    key: str,
    label: str,
    phase: str,
    baseline: date | None,
    forecast: date | None,
    real: date | None,
    weight: int,
    applicable: bool,
    estimated: bool,
    read: calculations.MilestoneSituation,
) -> MasMilestoneLine:
    return MasMilestoneLine(
        key=key,
        label=label,
        phase=phase,
        baseline=baseline,
        forecast=forecast,
        real=real,
        weight=weight,
        applicable=applicable,
        estimated=estimated,
        situation=read.situation,
        deviation_days=read.deviation_days,
        days_overdue=read.days_overdue,
    )


def _mas_supplier_id(*, order: PurchaseOrder | None, process: PurchaseProcess | None) -> int | None:
    """The supplier of the package: the order it was emitted to, or the recommended one."""
    if order is not None:
        return order.company_id
    if process is not None:
        return process.recommendation_company_id
    return None


def _mas_delivery_forecast(
    line: PackageLine,
    milestones: Sequence[MasMilestoneLine],
    *,
    service: bool,
    order: PurchaseOrder | None,
) -> date | None:
    """The delivery forecast of the line: the contract, the order or the estimated delivery.

    A service/EPC package has no fabrication: its date is the real, forecast or planned
    order/contract milestone. An equipment/material package with an order reads its delivery or
    forecast; without one, the forecast of the estimated delivery milestone.
    """
    pedido = line.milestone(calculations.ORDER_MILESTONE)
    if service:
        if pedido is None:
            return None
        return pedido.real or pedido.forecast or pedido.plan
    if order is not None:
        return order.delivery or order.forecast
    entrega = next((item for item in milestones if item.key == "entrega"), None)
    if entrega is None:
        return None
    return entrega.forecast or entrega.baseline


def _mas_concluded(line: PackageLine, *, service: bool, order: PurchaseOrder | None) -> bool:
    """Whether the package closed the cycle: delivered (equipment) or contracted (service)."""
    if service:
        pedido = line.milestone(calculations.ORDER_MILESTONE)
        return pedido is not None and pedido.real is not None
    return order is not None and order.delivery is not None


def _matches_mas(line: MasLine, filters: MasFilters) -> bool:
    conditions = [
        filters.discipline_id is None or line.discipline_id == filters.discipline_id,
        not filters.kind or line.kind == filters.kind,
        filters.lli != "sim" or line.lli,
        filters.lli != "nao" or not line.lli,
        filters.buyer_id is None or line.buyer_id == filters.buyer_id,
        filters.supplier_id is None or line.supplier_id == filters.supplier_id,
        not filters.situation or line.situation == filters.situation,
        not filters.overdue_only or line.overdue_milestones > 0,
    ]
    if not all(conditions):
        return False
    if not filters.search:
        return True
    searched = " ".join(
        (
            line.code,
            line.project_label,
            line.scope,
            line.supplier,
            line.order_number or "",
            line.contract_number or "",
            line.process_number or "",
            line.eac_code,
        )
    )
    return _normalize(filters.search) in _normalize(searched)


def _mas_sorted(lines: Iterable[MasLine], *, order: str) -> tuple[MasLine, ...]:
    """The lines in the order the filter chose: code, slack, value or progress."""
    if order == "folga":
        return tuple(
            sorted(
                lines,
                key=lambda line: (
                    line.concluded,
                    line.slack_days if line.slack_days is not None else 9999,
                ),
            )
        )
    if order == "valor":
        return tuple(sorted(lines, key=lambda line: -line.value_cents))
    if order == "avanco":
        return tuple(sorted(lines, key=lambda line: line.realized_pct))
    return tuple(sorted(lines, key=lambda line: _natural_key(line.code)))


def _natural_key(text: str) -> tuple[tuple[int, str], ...]:
    """The code split between text and digits, so ``PC-2`` comes before ``PC-14``."""
    parts = re.split(r"(\d+)", text)
    return tuple((1, part.zfill(12)) if part.isdigit() else (0, part) for part in parts if part)


def _mas_summary(universe: Sequence[MasLine]) -> MasSummary:
    return MasSummary(
        items=len(universe),
        with_baseline=sum(1 for line in universe if line.with_baseline),
        concluded=sum(1 for line in universe if line.concluded),
        on_time=sum(1 for line in universe if line.situation == calculations.MAS_ON_TIME),
        warning=sum(1 for line in universe if line.situation == calculations.MAS_WARNING),
        critical=sum(1 for line in universe if line.situation == calculations.MAS_CRITICAL),
        overdue_milestones=sum(line.overdue_milestones for line in universe),
        late_milestones=sum(line.late_milestones for line in universe),
        realized_milestones=sum(1 for line in universe for item in line.milestones if item.done),
        progress=calculations.procurement_progress(
            (line.progress, line.value_cents) for line in universe
        ),
    )


def _mas_columns(phase: str, *, weights: Mapping[str, int]) -> tuple[MasMilestoneColumn, ...]:
    """The visible columns of the table: the whole map or one of its two halves."""
    return tuple(
        MasMilestoneColumn(key=key, label=label, phase=item_phase, weight=weights.get(key, 0))
        for key, label, item_phase in calculations.MAS_MILESTONES
        if phase == validation.MAS_PHASE_ALL or item_phase == phase
    )


def _mas_totals(
    lines: Sequence[MasLine],
    *,
    columns: Sequence[MasMilestoneColumn],
    reference_date: date,
) -> tuple[MasMilestoneTotal, ...]:
    """The footer of the map: realizados over previstos on the baseline, per visible milestone."""
    totals: list[MasMilestoneTotal] = []
    for column in columns:
        milestones = [line.milestone(column.key) for line in lines]
        applicable = [item for item in milestones if item is not None and item.applicable]
        totals.append(
            MasMilestoneTotal(
                key=column.key,
                realized=sum(1 for item in applicable if item.done),
                planned=sum(
                    1
                    for item in applicable
                    if item.baseline is not None and item.baseline <= reference_date
                ),
            )
        )
    return tuple(totals)


def _distinct_options(
    pairs: Iterable[tuple[int, str]],
) -> tuple[configuracoes.RegisterOption, ...]:
    """The choices of a filter: the distinct non-empty pairs, by name."""
    names: dict[int, str] = {}
    for item_id, name in pairs:
        if name and item_id not in names:
            names[item_id] = name
    return tuple(
        configuracoes.RegisterOption(id=item_id, name=name)
        for item_id, name in sorted(names.items(), key=lambda item: item[1])
    )


# ── The panel (ISSUE-063) ────────────────────────────────────────────────────────────────────
#
# The panel is a calculated view of the plan, the processes, the orders and the contracts:
# nothing is stored for it. ``list_panel`` composes the same universes the other screens read
# (``_package_universe``, ``list_mas`` and ``list_orders``) and calculates the nine indicators of
# the prototype with ``calculations``, plus the three accumulated curves and the distribution of
# the packages by stage. The commercial outcome of a package prefers the live process; the
# columns of the historical load (ISSUE-063) are the fallback for the packages the load brought.


@dataclass(frozen=True)
class PanelStageCount:
    """How many packages of the plan are in one stage."""

    stage: str
    total: int


@dataclass(frozen=True)
class _PanelOutcome:
    """The commercial outcome of a package: adjudicated, first proposal, offers and single supplier."""

    adjudicated_cents: int | None
    first_proposal_cents: int | None
    valid_proposals: int | None
    single_supplier: bool | None


@dataclass(frozen=True)
class PanelSummary:
    """The nine indicators of the panel, counted on the whole universe.

    The KPIs of the plan (adherence, cycle, the two savings, competitiveness, emergency and
    committed against budget) read the packages; the order KPIs (critical, warning, OTD) come
    from the order universe, exactly as the expediting screen counts them. The adherence and OTD
    targets come from the group ``suprimentos`` in force.
    """

    packages: int
    planned_until_reference: int
    adjudicated_until_reference: int
    adherence_pct: Decimal | None
    adherence_target: int
    cycle_days: int | None
    cycle_baseline_days: int | None
    minimum_proposals: int
    estimate_cents: int
    adjudicated_cents: int
    saving_cents: int
    saving_pct: Decimal | None
    first_proposal_cents: int
    negotiation_saving_cents: int
    negotiation_saving_pct: Decimal | None
    offers_packages: int
    average_offers: Decimal | None
    single_supplier_pct: Decimal | None
    orders: OrderSummary
    otd_target: int
    emergency_cents: int
    emergency_pct: Decimal | None
    budget_cents: int
    committed_pct: Decimal | None


@dataclass(frozen=True)
class PanelListing:
    """What the panel shows: the nine indicators, the four visuals and the orders by slack."""

    summary: PanelSummary
    contracting: calculations.ContractingCurve
    saving: calculations.SavingCurve
    progress_curve: calculations.ProcurementCurve | None
    stages: tuple[PanelStageCount, ...]
    mas: MasListing
    reference_date: date

    @property
    def slack_lines(self) -> tuple[MasLine, ...]:
        """The packages with a delivery forecast, by slack: the table of the panel.

        The service/EPC packages stay out (the contract has no delivery) and so do the packages
        without any delivery date; the line keeps the package, the order or the stage, the next
        milestone, the forecast, the ROS, the slack and the situation.
        """
        lines = (
            line for line in self.mas.lines if not line.service and line.slack_days is not None
        )
        return tuple(sorted(lines, key=lambda line: (line.slack_days or 0, line.code)))


def list_panel(
    session: Session,
    *,
    user: User,
    scope: Scope,
    reference_date: date,
) -> PanelListing:
    """The panel of the scope: the indicators, the curves, the stages and the orders by slack."""
    rbac.require_module(user, MODULE)
    packages = _package_universe(session, user=user, scope=scope, reference_date=reference_date)
    processes = _processes_by_package(session, [line.id for line in packages])
    history = _history_by_process(session, [process.id for process in processes.values()])
    minimum = _process_parameters(session, reference_date=reference_date).minimum_proposals
    targets = _panel_targets(session, reference_date=reference_date)
    outcomes = _panel_outcomes(session, packages, processes=processes, minimum=minimum)
    mas = list_mas(
        session,
        user=user,
        scope=scope,
        filters=validation.MasFilters(),
        reference_date=reference_date,
    )
    orders = list_orders(
        session,
        user=user,
        scope=scope,
        filters=OrderFilters(situation=validation.ORDER_SITUATION_ALL),
        reference_date=reference_date,
    )
    return PanelListing(
        summary=_panel_summary(
            session,
            packages=packages,
            outcomes=outcomes,
            orders=orders.summary,
            minimum=minimum,
            targets=targets,
            reference_date=reference_date,
        ),
        contracting=calculations.contracting_curve(
            _panel_plan_adjudications(packages),
            _panel_real_adjudications(packages, outcomes),
            reference_date=reference_date,
        ),
        saving=calculations.saving_curve(
            _panel_saving_entries(packages, outcomes),
            reference_date=reference_date,
        ),
        progress_curve=calculations.procurement_curve(
            (
                (
                    [
                        calculations.ProgressCurveMilestone(
                            weight=item.weight,
                            applicable=item.applicable,
                            baseline=item.baseline,
                            forecast=item.forecast,
                            real=item.real,
                        )
                        for item in line.milestones
                    ],
                    line.value_cents,
                )
                for line in mas.lines
            ),
            reference_date=reference_date,
        ),
        stages=_panel_stages(packages, processes=processes, history=history),
        mas=mas,
        reference_date=reference_date,
    )


def _panel_outcomes(
    session: Session,
    packages: Sequence[PackageLine],
    *,
    processes: Mapping[int, PurchaseProcess],
    minimum: int,
) -> dict[int, _PanelOutcome]:
    """The commercial outcome of each package: the process wins, the loaded column follows.

    The adjudicated value is the order's, else the recommendation's, else the value of the
    contract born from the package (service/EPC, read from the Financeiro, D9). The winner's
    first proposal, the valid proposals and the single-supplier flag come from the live process
    when it exists and from the columns the load brought (ISSUE-063) when it does not.
    """
    package_ids = [line.id for line in packages]
    orders = _orders_by_package(session, package_ids)
    process_ids = [process.id for process in processes.values()]
    proposals = _proposals_by_process(session, process_ids)
    invitees = _invitees_by_process(session, process_ids)
    contracts = financeiro.purchase_contracts_by_package(session, package_ids)
    outcomes: dict[int, _PanelOutcome] = {}
    for line in packages:
        order = orders.get(line.id)
        process = processes.get(line.id)
        contract = contracts.get(line.id)
        adjudicated = next(
            (
                value
                for value in (
                    order.value_cents if order is not None else None,
                    process.recommendation_value_cents if process is not None else None,
                    contract.value_cents if contract is not None else None,
                )
                if value is not None
            ),
            None,
        )
        rows = proposals.get(process.id, ()) if process is not None else ()
        first = _winner_first_proposal(process, rows)
        if first is None:
            first = line.first_proposal_cents
        outcomes[line.id] = _PanelOutcome(
            adjudicated_cents=adjudicated,
            first_proposal_cents=first,
            valid_proposals=len(rows) if process is not None else line.valid_proposals,
            single_supplier=(
                len(invitees.get(process.id, ())) < minimum
                if process is not None
                else line.single_supplier
            ),
        )
    return outcomes


def _winner_first_proposal(
    process: PurchaseProcess | None, proposals: Sequence[ProcessProposal]
) -> int | None:
    """The value of the proposal of the recommended company: the winner's first proposal."""
    if process is None or process.recommendation_company_id is None:
        return None
    return next(
        (
            proposal.value_cents
            for proposal in proposals
            if proposal.company_id == process.recommendation_company_id
        ),
        None,
    )


def _panel_plan_adjudications(packages: Sequence[PackageLine]) -> list[date]:
    """The planned adjudication of every package, the plan of the contracting curve."""
    return [
        adjudication.plan
        for line in packages
        if (adjudication := line.adjudication) is not None and adjudication.plan is not None
    ]


def _panel_real_adjudications(
    packages: Sequence[PackageLine], outcomes: Mapping[int, _PanelOutcome]
) -> list[date]:
    """The real adjudication of the adjudicated packages, the real of the contracting curve."""
    return [
        adjudication.real
        for line in packages
        if outcomes[line.id].adjudicated_cents is not None
        and (adjudication := line.adjudication) is not None
        and adjudication.real is not None
    ]


def _panel_saving_entries(
    packages: Sequence[PackageLine], outcomes: Mapping[int, _PanelOutcome]
) -> list[tuple[date, int, int | None]]:
    """The saving of each adjudicated package: date, over the estimate and in the negotiation."""
    entries: list[tuple[date, int, int | None]] = []
    for line in packages:
        outcome = outcomes[line.id]
        adjudication = line.adjudication
        if outcome.adjudicated_cents is None or adjudication is None or adjudication.real is None:
            continue
        negotiation = (
            None
            if outcome.first_proposal_cents is None
            else outcome.first_proposal_cents - outcome.adjudicated_cents
        )
        entries.append(
            (adjudication.real, line.estimate_cents - outcome.adjudicated_cents, negotiation)
        )
    return entries


def _panel_stages(
    packages: Sequence[PackageLine],
    *,
    processes: Mapping[int, PurchaseProcess],
    history: Mapping[int, Sequence[Any]],
) -> tuple[PanelStageCount, ...]:
    """The distribution of the plan by stage, in the order of the flow; empty stages stay out.

    The stage of a package with a live process is the one of the last recorded action (the same
    reading of the process screen), so the PC-14 of the demonstration reads "Equalização
    comercial" even with the real dates stopping at the technical one, as the prototype did;
    without a process, the stage the real dates lead to.
    """
    totals: dict[str, int] = {}
    for line in packages:
        process = processes.get(line.id)
        stage = line.stage
        if process is not None:
            stage = calculations.process_stage(
                [
                    str((row.after or {}).get(HISTORY_STAGE, ""))
                    for row in history.get(process.id, ())
                ],
                line.stage,
            )
        totals[stage] = totals.get(stage, 0) + 1
    return tuple(
        PanelStageCount(stage=stage, total=totals[stage])
        for stage in calculations.PROCESS_STAGES
        if totals.get(stage)
    )


def _panel_targets(session: Session, *, reference_date: date) -> tuple[int, int]:
    """The adherence and OTD targets of the group ``suprimentos`` in force.

    Without a version in force the initial values of the platform apply; a value outside 0-100
    is ignored, as the facade ignores the malformed bands of the approval.
    """
    values = configuracoes.current_group(
        session, group=PROCESS_GROUP, reference_date=reference_date
    )
    initial = configuracoes.INITIAL_PARAMETERS[PROCESS_GROUP]

    def read(key: str) -> int:
        target = values.get(key, initial[key])
        if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target <= 100:
            return int(initial[key])
        return target

    return read("metaAderenciaPct"), read("metaOtdPct")


def _panel_summary(
    session: Session,
    *,
    packages: Sequence[PackageLine],
    outcomes: Mapping[int, _PanelOutcome],
    orders: OrderSummary,
    minimum: int,
    targets: tuple[int, int],
    reference_date: date,
) -> PanelSummary:
    """The nine indicators of the panel: the plan KPIs, the order KPIs and the two shares."""
    adjudicated = [line for line in packages if outcomes[line.id].adjudicated_cents is not None]
    planned_until = [
        line
        for line in packages
        if (adjudication := line.adjudication) is not None
        and adjudication.plan is not None
        and adjudication.plan <= reference_date
    ]
    adjudicated_until = [
        line for line in planned_until if outcomes[line.id].adjudicated_cents is not None
    ]
    cycles = [
        (order.real - requisition.real).days
        for line in adjudicated
        if (requisition := line.milestone(calculations.REQUISITION_MILESTONE)) is not None
        and requisition.real is not None
        and (order := line.milestone(calculations.ORDER_MILESTONE)) is not None
        and order.real is not None
    ]
    baseline_cycles = [
        (order.plan - requisition.plan).days
        for line in adjudicated
        if (requisition := line.milestone(calculations.REQUISITION_MILESTONE)) is not None
        and requisition.plan is not None
        and (order := line.milestone(calculations.ORDER_MILESTONE)) is not None
        and order.plan is not None
    ]
    estimate_cents = sum(line.estimate_cents for line in adjudicated)
    adjudicated_cents = sum(outcomes[line.id].adjudicated_cents or 0 for line in adjudicated)
    with_first = [
        line for line in adjudicated if outcomes[line.id].first_proposal_cents is not None
    ]
    first_proposal_cents = sum(outcomes[line.id].first_proposal_cents or 0 for line in with_first)
    negotiation_paid_cents = sum(outcomes[line.id].adjudicated_cents or 0 for line in with_first)
    offers = [
        value
        for line in packages
        if (value := outcomes[line.id].valid_proposals) is not None and value > 0
    ]
    single = [
        flag
        for line in packages
        if (valid := outcomes[line.id].valid_proposals) is not None
        and valid > 0
        and (flag := outcomes[line.id].single_supplier) is not None
    ]
    emergency_cents = sum(
        outcomes[line.id].adjudicated_cents or 0 for line in adjudicated if line.emergency
    )
    budget_cents = _panel_budget_cents(session, packages=adjudicated, reference_date=reference_date)
    return PanelSummary(
        packages=len(packages),
        planned_until_reference=len(planned_until),
        adjudicated_until_reference=len(adjudicated_until),
        adherence_pct=calculations.purchase_plan_adherence(
            len(adjudicated_until), len(planned_until)
        ),
        adherence_target=targets[0],
        cycle_days=calculations.average_cycle_days(cycles),
        cycle_baseline_days=calculations.average_cycle_days(baseline_cycles),
        minimum_proposals=minimum,
        estimate_cents=estimate_cents,
        adjudicated_cents=adjudicated_cents,
        saving_cents=estimate_cents - adjudicated_cents,
        saving_pct=calculations.saving_pct(estimate_cents, adjudicated_cents),
        first_proposal_cents=first_proposal_cents,
        negotiation_saving_cents=first_proposal_cents - negotiation_paid_cents,
        negotiation_saving_pct=calculations.saving_pct(
            first_proposal_cents, negotiation_paid_cents
        ),
        offers_packages=len(offers),
        average_offers=calculations.average_offers(offers),
        single_supplier_pct=calculations.single_supplier_share(single),
        orders=orders,
        otd_target=targets[1],
        emergency_cents=emergency_cents,
        emergency_pct=calculations.emergency_share(emergency_cents, adjudicated_cents),
        budget_cents=budget_cents,
        committed_pct=calculations.committed_over_budget(adjudicated_cents, budget_cents),
    )


def _panel_budget_cents(
    session: Session,
    *,
    packages: Sequence[PackageLine],
    reference_date: date,
) -> int:
    """The current budget of the EAC items the adjudicated packages cost (the map, D9).

    Read per project through the Financeiro facade (``mapa_controle``): in the Portfólio the map
    has one line per project, so the items are summed project by project. A package without an
    adjudicated value stays out, and two packages of the same item count it once.
    """
    wanted: dict[int, set[int]] = {}
    for line in packages:
        wanted.setdefault(line.project_id, set()).add(line.eac_item_id)
    total = 0
    for project_id, item_ids in wanted.items():
        view = financeiro.mapa_controle(
            session,
            scope=Scope(project_id=project_id, source="url"),
            reference_date=reference_date,
        )
        total += sum(row.current_cents for row in view.rows if row.item_id in item_ids)
    return total
