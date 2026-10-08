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

Public API (stable; a change needs an issue of its own): ``list_suppliers``, ``find_supplier``,
``create_supplier``, ``save_qualification``, ``apply_final_evaluation``, ``list_packages``,
``find_package``, ``package_options``, ``create_package``, ``update_package`` and
``change_package``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit, rbac, recording, versioning
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
    PurchasePackage,
    Supplier,
    SupplierCategory,
    SupplierDocument,
    SupplierHistory,
)
from src.modulos.suprimentos.validation import (
    DocumentInput,
    PackageChangeInput,
    PackageFilters,
    PackageInput,
    QualificationInput,
    SupplierFilters,
    SupplierInput,
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
