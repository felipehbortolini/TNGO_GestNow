"""Business facade of the Procurement module: supplier qualification and performance (ISSUE-057).

The supplier register is global: ``fornecedor`` is the qualification of a company of the
Configurações register, with its categories, its documents with validity and the history of
situation changes. Documents in day, the performance and the contracted value are never stored:
they are calculated on every read from the documents, from the Financeiro facade
(``company_performance``) and from the reference date the caller hands in.

Writes go through ``core.recording`` (trail, version and transaction together, D5): the
qualification, its documents (each with its own ``versao``) and the history facts. A change of
situation requires a justification, and Restrito and Bloqueado require the reason; the history
row is a fact and records de/para/author/justificativa.

The final evaluation of a contract (ISSUE-034) updates the existing qualification through
``apply_final_evaluation``, registered as a listener of the Financeiro (D9): class A and B
qualify, C restricts and D blocks, inside the same transaction of the evaluation.

Public API (stable; a change needs an issue of its own): ``list_suppliers``, ``find_supplier``,
``create_supplier``, ``save_qualification`` and ``apply_final_evaluation``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit, rbac, recording
from src.core.errors import InvalidDataError
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Company
from src.modulos.financeiro import service as financeiro
from src.modulos.suprimentos import calculations, validation
from src.modulos.suprimentos.models import (
    Supplier,
    SupplierCategory,
    SupplierDocument,
    SupplierHistory,
)
from src.modulos.suprimentos.validation import (
    DocumentInput,
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
