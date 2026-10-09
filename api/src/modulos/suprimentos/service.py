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

Public API (stable; a change needs an issue of its own): ``list_suppliers``, ``find_supplier``,
``create_supplier``, ``save_qualification``, ``apply_final_evaluation``, ``list_packages``,
``find_package``, ``package_options``, ``create_package``, ``update_package``,
``change_package``, ``list_processes``, ``find_process``, ``process_options``,
``planned_packages``, ``start_requisition``, ``issue_rfx``, ``register_proposal``,
``close_receipt``, ``equalize_technically``, ``equalize_commercially`` and
``register_negotiation``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import attachment_origins, attachments, audit, rbac, recording, versioning
from src.core.errors import InvalidDataError
from src.core.export_document import project_label
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Company
from src.modulos.financeiro import service as financeiro
from src.modulos.suprimentos import calculations, validation
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
from src.modulos.suprimentos.validation import (
    ClosingInput,
    CommercialInput,
    DocumentInput,
    NegotiationInput,
    PackageChangeInput,
    PackageFilters,
    PackageInput,
    ProposalInput,
    QualificationInput,
    RequisitionInput,
    RfxInput,
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
            reference_date=reference_date,
        )
        for company in companies
    )


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
    """What a process action answers: the package, its code and the RFx number, when it has one."""

    package_id: int
    code: str
    number: str | None


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

    The ficha is the only reader that needs the saldo a comprometer of the EAC item, so the
    balance of the package's project is read here and not on the list (D9).
    """
    line = _line_in_scope(
        session, user=user, scope=scope, package_id=package_id, reference_date=reference_date
    )
    if line is None:
        return None
    return replace(
        line,
        eac_balance_cents=_eac_balance(session, line=line, reference_date=reference_date),
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
