"""Business facade of the Financeiro module: the EAC tree and the weighting of the portfolio (D5, D8).

This is the only door to the tables of the module. The tree is read per scope: one project, with
its root line (code 0) and the totals added on the server in cents, or the Portfólio, read-only,
with a line per project and one per main package (D8). The cadastral edit of an item changes no
value of the budget, so it needs no SM, but it needs a justification and stays in the history of
the item (the trail of the platform, ``audit``). Everything that changes a value belongs to
ISSUE-030.

Nothing here reads the clock: the routes pass the reference date.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import (
    attachment_origins,
    attachments,
    audit,
    calendario,
    notification,
    numbering,
    rbac,
    recording,
)
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.file_storage import FileStorage
from src.core.models import AuditEntry
from src.core.money import format_brl
from src.core.notification import NotificationChannel, NotificationRequest
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import calculations, validation
from src.modulos.financeiro.calculations import (
    ItemLine,
    PortfolioProject,
    ProjectWeight,
    TreeRow,
    WeightCriterion,
    WeightInput,
)
from src.modulos.financeiro.models import (
    Contract,
    ContractAddendum,
    ContractClaim,
    ContractEvaluation,
    ContractEvaluationCriterion,
    ContractMeasurement,
    ContractPaymentMilestone,
    ContractTimeExtension,
    CurvaFinanceiraMonth,
    CurvaFinanceiraRevision,
    EacItem,
    EacProjection,
    EacReallocation,
    EacRevision,
    EacRevisionItem,
    ErpCost,
    Reserve,
    ReserveMovement,
)

if TYPE_CHECKING:
    from src.modulos.governanca.service import OpenReserveRequest, ProposedTransfer
    from src.modulos.planejamento.calculations import CurvaFisicaSeries

MODULE = "financeiro"
REGISTRY_ENTITY = "eac_item.cadastro"
PORTFOLIO_LABEL = "Portfólio"
PORTFOLIO_ROOT_DESCRIPTION = "Portfólio de projetos"
COMMITTED_CENTS = 0

PORTFOLIO_READ_ONLY_MESSAGE = (
    "A EAC do Portfólio é somente leitura. Abra o projeto para editar um item."
)
OTHER_PROJECT_MESSAGE = "O item pertence a outro projeto. Abra o projeto dele para editar."
NOT_FOUND_MESSAGE = "Item da EAC não encontrado."
UNKNOWN_PROJECT_MESSAGE = "O projeto escolhido não existe."
ONLY_ITEMS_MESSAGE = "Só os itens de custo (nível 3) têm cadastro editável."
REVISION_DENIED_MESSAGE = "A revisão da EAC exige papel Gestor."

DEFAULT_CRITERIA = (WeightCriterion(id="valor", weight=Decimal(100), source="orcamento"),)

# The label of each cadastral field, as the history of the item prints it.
FIELD_LABELS = {
    "description": "descrição",
    "cost_type": "tipo de custo",
    "capex": "classificação",
    "cost_center": "centro de custo",
    "responsible_id": "responsável",
}


@dataclass(frozen=True)
class EacFilters:
    """What the person typed in the filters of the tree: search, deepest level and cost type."""

    search: str = ""
    level: int = calculations.LEAF_LEVEL
    cost_type: str = ""

    @property
    def is_active(self) -> bool:
        """Whether a text or a cost type narrows the tree (the level only cuts depth)."""
        return bool(self.search.strip() or self.cost_type)


@dataclass(frozen=True)
class EacSummary:
    """The counts and the budget the KPIs of the screen read, all counted on the server."""

    budget_cents: int
    item_count: int
    package_count: int
    subpackage_count: int
    project_count: int
    registered_project_count: int


@dataclass(frozen=True)
class EacView:
    """Everything the EAC screen, its Excel and its printable version print."""

    scope_label: str
    is_portfolio: bool
    rows: tuple[TreeRow, ...]
    full_rows: tuple[TreeRow, ...]
    parents: frozenset[str]
    summary: EacSummary
    filters: EacFilters
    max_level: int
    filtered_total_cents: int | None
    can_edit: bool

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no EAC at all (the empty state of origin)."""
        return len(self.full_rows) <= 1

    @property
    def has_no_match(self) -> bool:
        """Whether the filters hide every line (the empty state of the filter)."""
        return not self.is_empty and len(self.rows) <= 1


# ── Leitura da árvore ────────────────────────────────────────────────────


def eac_view(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: EacFilters,
    reference_date: date,
) -> EacView:
    """The EAC of the scope: one project (editable) or the Portfólio (read-only)."""
    projects = configuracoes.list_projects(session)
    lines = _lines_by_project(session, [project.id for project in projects])
    scope_label = PORTFOLIO_LABEL
    if scope.is_portfolio:
        weights = _weights_of(session, projects, lines, reference_date=reference_date)
        full_rows = _portfolio_rows(session, projects, lines, weights)
        max_level = calculations.PORTFOLIO_MAIN_LEVEL
        summary = _portfolio_summary(full_rows, projects, lines)
    else:
        project = _project_of(projects, scope)
        scope_label = _label(project)
        items = lines.get(project.id, [])
        full_rows = (
            calculations.build_project_tree(
                items,
                project_id=project.id,
                project_label=_label(project),
                root_description=project.name,
            )
            if items
            else ()
        )
        max_level = calculations.LEAF_LEVEL
        summary = _project_summary(full_rows)
    level = min(max(filters.level, 1), max_level)
    rows = calculations.filter_tree(
        full_rows, search=filters.search, max_level=level, cost_type=filters.cost_type
    )
    return EacView(
        scope_label=PORTFOLIO_LABEL if scope.is_portfolio else scope_label,
        is_portfolio=scope.is_portfolio,
        rows=rows,
        full_rows=full_rows,
        parents=calculations.parent_codes(rows),
        summary=summary,
        filters=EacFilters(search=filters.search.strip(), level=level, cost_type=filters.cost_type),
        max_level=max_level,
        filtered_total_cents=calculations.filtered_total_cents(rows) if filters.is_active else None,
        can_edit=not scope.is_portfolio and rbac.can(user, Permission.WRITE),
    )


def _project_of(
    projects: Sequence[configuracoes.ProjectSummary], scope: Scope
) -> configuracoes.ProjectSummary:
    project = next((item for item in projects if item.id == scope.project_id), None)
    if project is None:
        raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)
    return project


def _label(project: configuracoes.ProjectSummary) -> str:
    return f"{project.code} · {project.name}"


def _portfolio_rows(
    session: Session,
    projects: Sequence[configuracoes.ProjectSummary],
    lines: Mapping[int, Sequence[ItemLine]],
    weights: Mapping[int, ProjectWeight],
) -> tuple[TreeRow, ...]:
    people = {person.id: person.name for person in configuracoes.list_people(session)}
    return calculations.build_portfolio_tree(
        [
            PortfolioProject(
                id=project.id,
                label=_label(project),
                manager=people.get(project.manager_id) if project.manager_id else None,
                items=lines.get(project.id, []),
                weight=weights[project.id].weight if project.id in weights else None,
            )
            for project in projects
        ],
        root_description=PORTFOLIO_ROOT_DESCRIPTION,
    )


def _project_summary(rows: Sequence[TreeRow]) -> EacSummary:
    return EacSummary(
        budget_cents=rows[0].budget_cents if rows else 0,
        item_count=sum(1 for row in rows if row.level >= calculations.LEAF_LEVEL),
        package_count=sum(1 for row in rows if row.level == 1),
        subpackage_count=sum(1 for row in rows if row.level == calculations.PORTFOLIO_MAIN_LEVEL),
        project_count=1 if rows else 0,
        registered_project_count=1,
    )


def _portfolio_summary(
    rows: Sequence[TreeRow],
    projects: Sequence[configuracoes.ProjectSummary],
    lines: Mapping[int, Sequence[ItemLine]],
) -> EacSummary:
    return EacSummary(
        budget_cents=rows[0].budget_cents,
        item_count=sum(
            1 for items in lines.values() for item in items if item.level >= calculations.LEAF_LEVEL
        ),
        package_count=sum(1 for row in rows if row.level == calculations.PORTFOLIO_MAIN_LEVEL),
        subpackage_count=0,
        project_count=sum(1 for row in rows if row.level == 1),
        registered_project_count=len(projects),
    )


def _lines_by_project(session: Session, project_ids: Sequence[int]) -> dict[int, list[ItemLine]]:
    """The items of the projects, with the names resolved and the base in force of each one.

    An item of a project with a revision takes the frozen base of the latest revision plus the
    reallocations applied and not yet consolidated; without a revision, quantity x unit price.
    """
    if not project_ids:
        return {}
    people = {person.id: person.name for person in configuracoes.list_people(session)}
    units = {unit.id: unit.code for unit in configuracoes.list_measure_units(session)}
    statement = select(EacItem).where(EacItem.project_id.in_(project_ids)).order_by(EacItem.id)
    records: dict[int, list[EacItem]] = {}
    for item in session.scalars(statement):
        records.setdefault(item.project_id, []).append(item)
    grouped: dict[int, list[ItemLine]] = {}
    for project_id, project_records in records.items():
        plain = [_item_line(record, people=people, units=units) for record in project_records]
        bases = _current_bases(session, project_id=project_id, items=plain)
        grouped[project_id] = [replace(line, base_cents=bases.get(line.id, 0)) for line in plain]
    return grouped


def _item_line(
    item: EacItem,
    *,
    people: Mapping[int, str],
    units: Mapping[int, str],
    base_cents: int | None = None,
) -> ItemLine:
    return ItemLine(
        id=item.id,
        parent_id=item.parent_id,
        code=item.code,
        description=item.description,
        level=item.level,
        cost_type=item.cost_type,
        unit=units.get(item.unit_id) if item.unit_id else None,
        quantity=item.quantity,
        unit_price_cents=item.unit_price_cents,
        base_cents=base_cents,
        capex=item.capex,
        cost_center=item.cost_center,
        responsible=people.get(item.responsible_id) if item.responsible_id else None,
        version=item.version,
    )


def _latest_revision(session: Session, *, project_id: int) -> int | None:
    statement = (
        select(EacRevision.revision)
        .where(EacRevision.project_id == project_id)
        .order_by(EacRevision.revision.desc())
        .limit(1)
    )
    return session.scalars(statement).one_or_none()


def _revision_bases(session: Session, *, project_id: int, revision: int) -> dict[int, int]:
    statement = (
        select(EacRevisionItem.item_id, EacRevisionItem.base_cents)
        .join(EacRevision, EacRevision.id == EacRevisionItem.revision_id)
        .where(EacRevision.project_id == project_id, EacRevision.revision == revision)
    )
    return {row.item_id: row.base_cents for row in session.execute(statement)}


def _current_bases(
    session: Session, *, project_id: int, items: Sequence[ItemLine]
) -> dict[int, int]:
    """Orçado atual of every item of the project, in cents (frozen revision plus reallocations)."""
    latest = _latest_revision(session, project_id=project_id)
    revision_bases = (
        _revision_bases(session, project_id=project_id, revision=latest)
        if latest is not None
        else {}
    )
    statement = (
        select(EacReallocation)
        .where(EacReallocation.project_id == project_id)
        .order_by(EacReallocation.id)
    )
    reallocations = [
        calculations.ReallocationLine(
            source_item_id=row.source_item_id,
            target_item_id=row.target_item_id,
            value_cents=row.value_cents,
            revision=row.revision,
        )
        for row in session.scalars(statement)
    ]
    return calculations.current_base_cents(
        items,
        revision_bases=revision_bases,
        latest_revision=latest,
        reallocations=reallocations,
    )


# ── Orçamento vigente e ponderação da carteira ───────────────────────────


def current_budgets(
    session: Session, *, project_ids: Sequence[int] | None = None
) -> dict[int, int]:
    """Orçamento vigente of each project on the EAC, in cents.

    The sum of the budgeted values of its items; a project without EAC keeps the budget of its
    register (as the prototype did), and ``0`` when it has none.
    """
    projects = [
        project
        for project in configuracoes.list_projects(session)
        if project_ids is None or project.id in project_ids
    ]
    lines = _lines_by_project(session, [project.id for project in projects])
    return {project.id: _budget_of(project, lines) for project in projects}


def _budget_of(
    project: configuracoes.ProjectSummary, lines: Mapping[int, Sequence[ItemLine]]
) -> int:
    items = lines.get(project.id, [])
    if items:
        return calculations.project_total_cents(items)
    return project.budget_cents or 0


def portfolio_weights(session: Session, *, reference_date: date) -> dict[int, ProjectWeight]:
    """Ponderação da carteira: the weight (%) of each project, closed at 100,00 (D8, HU-035).

    The first criterion is the budget in force on the EAC; the others are the grades of 1 to 5 of
    the portfolio parameters in force on the reference date. Editing the weighting is Configurações.
    """
    projects = configuracoes.list_projects(session)
    lines = _lines_by_project(session, [project.id for project in projects])
    return _weights_of(session, projects, lines, reference_date=reference_date)


def _weights_of(
    session: Session,
    projects: Sequence[configuracoes.ProjectSummary],
    lines: Mapping[int, Sequence[ItemLine]],
    *,
    reference_date: date,
) -> dict[int, ProjectWeight]:
    grades = configuracoes.portfolio_grades(session, reference_date=reference_date)
    inputs = [
        WeightInput(
            project_id=project.id,
            budget_cents=_budget_of(project, lines),
            grades=grades.get(project.id, {}),
        )
        for project in projects
    ]
    return calculations.portfolio_weights(inputs, _criteria(session, reference_date))


def _criteria(session: Session, reference_date: date) -> list[WeightCriterion]:
    group = configuracoes.current_group(session, group="portfolio", reference_date=reference_date)
    configured = group.get("criterios") or []
    criteria = [
        WeightCriterion(
            id=str(criterion["id"]),
            weight=Decimal(str(criterion.get("peso", 0))),
            source=str(criterion.get("fonte", "nota")),
        )
        for criterion in configured
    ]
    return criteria or list(DEFAULT_CRITERIA)


# ── Criação do item (carga e ISSUE-030) ──────────────────────────────────


@dataclass(frozen=True)
class NewItem:
    """The data of an item to create: the place in the tree, the quantity and the price."""

    project_id: int
    code: str
    description: str
    level: int
    parent_id: int | None = None
    unit_id: int | None = None
    responsible_id: int | None = None
    cost_type: str | None = None
    quantity: Decimal | None = None
    unit_price_cents: int | None = None
    capex: bool | None = None
    cost_center: str | None = None


def create_item(session: Session, *, user_id: int, new: NewItem) -> int:
    """Create an item of the tree through ``recording`` and return its id.

    The screen of ISSUE-029 never calls this: a new item changes the budget, so it goes through an
    SM (ISSUE-030). It is the door of the demonstration load and of the flows that follow.
    """
    item = EacItem(
        project_id=new.project_id,
        parent_id=new.parent_id,
        unit_id=new.unit_id,
        responsible_id=new.responsible_id,
        code=new.code,
        description=new.description,
        level=new.level,
        cost_type=new.cost_type,
        quantity=new.quantity,
        unit_price_cents=new.unit_price_cents,
        capex=new.capex,
        cost_center=new.cost_center,
    )
    recording.create(session, user_id=user_id, record=item)
    return item.id


# ── Cadastro do item ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class RegistryHistoryEntry:
    """A change of the cadastral data of an item: when, who, which fields and why."""

    occurred_on: date
    author: str
    fields: tuple[str, ...]
    justification: str


@dataclass(frozen=True)
class ItemForm:
    """What the edit form of an item shows: the item as it is now and its cadastral history."""

    row: TreeRow
    history: tuple[RegistryHistoryEntry, ...]
    people: tuple[configuracoes.PersonSummary, ...]
    responsible_id: int | None
    description: str
    cost_type: str
    capex: bool
    cost_center: str
    version: int


@dataclass(frozen=True)
class RegistryResult:
    """What a cadastral edit did: the fields it changed (none when nothing differed)."""

    item_id: int
    changed_fields: tuple[str, ...]


def item_form(session: Session, *, user: User, scope: Scope, item_id: int) -> ItemForm:
    """The edit form of an item, with its history; refused in the Portfólio and for other roles."""
    item = _editable_item(session, user=user, scope=scope, item_id=item_id)
    return _form_of(session, item)


def _form_of(session: Session, item: EacItem) -> ItemForm:
    lines = _lines_by_project(session, [item.project_id])[item.project_id]
    tree = calculations.build_project_tree(
        lines, project_id=item.project_id, project_label="", root_description=""
    )
    return ItemForm(
        row=next(row for row in tree if row.item_id == item.id),
        history=item_history(session, item_id=item.id),
        people=tuple(configuracoes.list_people(session)),
        responsible_id=item.responsible_id,
        description=item.description,
        cost_type=item.cost_type or "",
        capex=bool(item.capex),
        cost_center=item.cost_center or "",
        version=item.version,
    )


def edit_item_registry(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    form: Mapping[str, str | None],
) -> RegistryResult:
    """Change the cadastral data of an item: with a justification, never a value of the budget.

    Description, cost type, classification, cost center and responsible need no SM, but a change
    without justification is refused (422). The change goes through ``recording`` (version and
    trail of the record) and leaves its own line in the history of the item, with the fields and
    the justification. Nothing differing writes nothing.
    """
    item = _editable_item(session, user=user, scope=scope, item_id=item_id)
    people = {person.id: person.name for person in configuracoes.list_people(session)}
    edit = validation.parse_registry_edit(form, responsible_ids=set(people))
    changes = _registry_changes(item, edit)
    if not changes:
        return RegistryResult(item_id=item.id, changed_fields=())
    before = _display_values(item, people, changes)
    recording.update(
        session,
        user_id=user.id,
        record=item,
        changes=changes,
        version=form.get(validation.FIELD_VERSION),
    )
    labels = [FIELD_LABELS[field] for field in changes]
    audit.append(
        session,
        audit.TrailLine(
            user_id=user.id,
            entity=REGISTRY_ENTITY,
            record_id=item.id,
            action=audit.UPDATED,
            before=before,
            after={
                **_display_values(item, people, changes),
                "campos": labels,
                "justificativa": edit.justification,
            },
            project_id=item.project_id,
        ),
    )
    return RegistryResult(item_id=item.id, changed_fields=tuple(labels))


def item_history(session: Session, *, item_id: int) -> tuple[RegistryHistoryEntry, ...]:
    """The cadastral history of an item, the most recent change first."""
    statement = (
        select(AuditEntry)
        .where(AuditEntry.entity == REGISTRY_ENTITY, AuditEntry.record_id == item_id)
        .order_by(AuditEntry.occurred_at.desc(), AuditEntry.id.desc())
    )
    return tuple(
        RegistryHistoryEntry(
            occurred_on=calendario.in_product_timezone(entry.occurred_at).date(),
            author=audit.author_name(session, entry.user_id) or "",
            fields=tuple((entry.after or {}).get("campos", ())),
            justification=str((entry.after or {}).get("justificativa", "")),
        )
        for entry in session.scalars(statement)
    )


def _editable_item(session: Session, *, user: User, scope: Scope, item_id: int) -> EacItem:
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    if scope.is_portfolio:
        raise AccessDeniedError(PORTFOLIO_READ_ONLY_MESSAGE)
    item = session.get(EacItem, item_id)
    if item is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    if item.project_id != scope.project_id:
        raise AccessDeniedError(OTHER_PROJECT_MESSAGE)
    if item.level < calculations.LEAF_LEVEL:
        raise InvalidDataError(ONLY_ITEMS_MESSAGE)
    return item


def _registry_changes(item: EacItem, edit: validation.RegistryEdit) -> dict[str, Any]:
    wanted: dict[str, Any] = {
        "description": edit.description,
        "cost_type": edit.cost_type,
        "capex": edit.capex,
        "cost_center": edit.cost_center,
        "responsible_id": edit.responsible_id,
    }
    return {
        field: value
        for field, value in wanted.items()
        if _normalized(getattr(item, field)) != _normalized(value)
    }


def _normalized(value: Any) -> Any:
    return "" if value is None else value


def _display_values(
    item: EacItem, people: Mapping[int, str], fields: Mapping[str, Any]
) -> dict[str, str]:
    """The values of the changed fields as a person reads them, keyed by the field's label."""
    shown: dict[str, str] = {}
    for field in fields:
        value = getattr(item, field)
        if field == "capex":
            text = "CAPEX" if value else "OPEX"
        elif field == "responsible_id":
            text = people.get(value, "") if value else ""
        else:
            text = "" if value is None else str(value)
        shown[FIELD_LABELS[field]] = text
    return shown


def eac_item_ids_by_code(
    session: Session, *, project_id: int, codes: Sequence[str]
) -> dict[str, int]:
    """The id of each EAC item of the project named by its code; a code that is not there is left out.

    What other modules read to link a record to an item (Governança, ISSUE-024). Whether the item is a
    cost item (level 3) is checked by the EAC revisions (ISSUE-030).
    """
    wanted = {code.strip() for code in codes if code.strip()}
    if not wanted:
        return {}
    statement = select(EacItem.code, EacItem.id).where(
        EacItem.project_id == project_id, EacItem.code.in_(wanted)
    )
    return {row.code: row.id for row in session.execute(statement)}


def eac_item_codes(session: Session, item_ids: Sequence[int]) -> dict[int, str]:
    """The code of each EAC item by its id, for a screen that lists the items another module linked."""
    if not item_ids:
        return {}
    statement = select(EacItem.id, EacItem.code).where(EacItem.id.in_(set(item_ids)))
    return {row.id: row.code for row in session.execute(statement)}


def eac_item_labels(session: Session, item_ids: Sequence[int]) -> dict[int, tuple[str, str]]:
    """O código e a descrição de cada item da EAC, por id, para a tela que os lista (D9).

    Leitura aditiva para o plano de compras: o pacote guarda o id do item e a lista precisa do
    código e da descrição, inclusive dos itens de nível 2 que o mock já vinculava.
    """
    wanted = set(item_ids)
    if not wanted:
        return {}
    statement = select(EacItem.id, EacItem.code, EacItem.description).where(EacItem.id.in_(wanted))
    return {row.id: (row.code, row.description) for row in session.execute(statement)}


def eac_item_levels_by_code(
    session: Session, *, project_id: int, codes: Sequence[str]
) -> dict[str, int]:
    """The level of each EAC item of the project named by its code; a code absent is left out."""
    wanted = {code.strip() for code in codes if code.strip()}
    if not wanted:
        return {}
    statement = select(EacItem.code, EacItem.level).where(
        EacItem.project_id == project_id, EacItem.code.in_(wanted)
    )
    return {row.code: row.level for row in session.execute(statement)}


def eac_item_levels(session: Session, *, project_id: int) -> dict[str, int]:
    """The level of every EAC item of the project, by code: the places a new item can be born."""
    statement = select(EacItem.code, EacItem.level).where(EacItem.project_id == project_id)
    return {row.code: row.level for row in session.execute(statement)}


# ── Remanejamento por SM (ISSUE-030) ─────────────────────────────────────


REALLOCATION_FIELD = "remanejamentos"
REALLOCATION_EMPTY_MESSAGE = "Inclua ao menos uma transferência (origem, destino e valor)."
REALLOCATION_SAME_ITEM_MESSAGE = "O destino precisa ser diferente da origem."
REALLOCATION_VALUE_MESSAGE = "Informe um valor maior que zero."
REALLOCATION_SOURCE_MESSAGE = "A origem {code} precisa ser item de custo (nível 3) da EAC."
REALLOCATION_TARGET_MESSAGE = "O destino {code} precisa ser item de custo (nível 3) da EAC."
REALLOCATION_TARGET_UNKNOWN_MESSAGE = "O item de destino {code} não existe na EAC do projeto."
NEW_ITEM_CODE_MESSAGE = "Já existe item com o código {code} na EAC."
REVISION_CHANGE_UNKNOWN_MESSAGE = "A SM informada não é do projeto desta revisão."
REVISION_ALREADY_INCORPORATED_MESSAGE = (
    "O custo desta SM já foi incorporado por uma revisão da EAC."
)
REVISION_JUSTIFICATION_MESSAGE = "Informe a justificativa da revisão."
REVISION_ITEM_UNKNOWN_MESSAGE = "O item {code} não é item de custo (nível 3) da EAC."
REVISION_NEW_ITEM_DUPLICATE_MESSAGE = "Item novo repetido: {code}."
REVISION_NEW_ITEM_VALUE_MESSAGE = "O item novo {code} precisa de um valor maior ou igual a zero."

DEFAULT_REALLOCATION_PRIORITY = "Normal"


@dataclass(frozen=True)
class NewItemRequest:
    """O item novo que um remanejamento cria, com o lugar na árvore e os atributos cadastrais."""

    code: str
    description: str
    parent_id: int | None = None
    unit_id: int | None = None
    cost_type: str | None = None
    capex: bool | None = None
    cost_center: str | None = None
    responsible_id: int | None = None
    quantity: Decimal | None = None
    unit_price_cents: int | None = None


@dataclass(frozen=True)
class TransferRequest:
    """Uma transferência da SM: origem, destino, valor e o item novo do destino, quando é o caso."""

    source_code: str
    target_code: str
    value_cents: int
    new_item: NewItemRequest | None = None


@dataclass(frozen=True)
class ReallocationRequest:
    """O remanejamento pedido pela tela da EAC: o título, a justificativa e as transferências."""

    justification: str
    transfers: tuple[TransferRequest, ...]
    title: str = ""
    priority: str = DEFAULT_REALLOCATION_PRIORITY


@dataclass(frozen=True)
class CreatedReallocation:
    """A SM de remanejamento criada: o que a tela da EAC precisa para abri-la."""

    id: int
    code: str
    project_id: int


class ReallocationChange(Protocol):
    """A SM que aplica transferências, como a fachada do Financeiro a lê (dona: Governança)."""

    id: int
    project_id: int
    title: str


def reallocate(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: ReallocationRequest,
    reference_date: date,
) -> CreatedReallocation:
    """Open the SM of a budget reallocation with its transfers, as the EAC screen asks (HU-088).

    The origin needs the free balance (the current budget less the committed and the balance
    reserved by other open SMs); the destination is an item of level 3 or an item new, which is
    born here with base zero because ``mudanca_remanejamento`` points at it (its value only
    arrives with the approval). The transfers are written by the Governança facade, the owner of
    the table.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    project_id = scope.require_project()
    if not request.transfers:
        raise InvalidDataError({REALLOCATION_FIELD: REALLOCATION_EMPTY_MESSAGE})
    items = _lines_by_project(session, [project_id]).get(project_id, [])
    _check_transfer_requests(request.transfers, items)
    new_ids = _create_new_items(session, user_id=user.id, project_id=project_id, request=request)
    transfers = _proposed_transfers(request.transfers, items, new_ids)
    _check_sources_free(session, project_id=project_id, items=items, transfers=transfers)
    from src.modulos.governanca import service as governanca

    created = governanca.create_reallocation_change(
        session,
        user=user,
        proposal=governanca.NewReallocation(
            project_id=project_id,
            title=_reallocation_title(request),
            justification=request.justification,
            transfers=transfers,
            priority=request.priority,
        ),
        reference_date=reference_date,
    )
    return CreatedReallocation(id=created.id, code=created.code, project_id=created.project_id)


def _check_transfer_requests(
    transfers: Sequence[TransferRequest], items: Sequence[ItemLine]
) -> None:
    by_code = {item.code: item for item in items}
    new_codes: set[str] = set()
    for transfer in transfers:
        if not isinstance(transfer.value_cents, int) or transfer.value_cents <= 0:
            raise InvalidDataError({REALLOCATION_FIELD: REALLOCATION_VALUE_MESSAGE})
        if transfer.source_code == transfer.target_code:
            raise InvalidDataError({REALLOCATION_FIELD: REALLOCATION_SAME_ITEM_MESSAGE})
        source = by_code.get(transfer.source_code)
        if source is None or source.level < calculations.LEAF_LEVEL:
            raise InvalidDataError(
                {REALLOCATION_FIELD: REALLOCATION_SOURCE_MESSAGE.format(code=transfer.source_code)}
            )
        if transfer.new_item is None:
            target = by_code.get(transfer.target_code)
            if target is None or target.level < calculations.LEAF_LEVEL:
                raise InvalidDataError(
                    {
                        REALLOCATION_FIELD: REALLOCATION_TARGET_MESSAGE.format(
                            code=transfer.target_code
                        )
                    }
                )
            continue
        if (
            transfer.new_item.code != transfer.target_code
            or transfer.target_code in by_code
            or transfer.target_code in new_codes
        ):
            raise InvalidDataError(
                {REALLOCATION_FIELD: NEW_ITEM_CODE_MESSAGE.format(code=transfer.target_code)}
            )
        new_codes.add(transfer.target_code)


def _create_new_items(
    session: Session, *, user_id: int, project_id: int, request: ReallocationRequest
) -> dict[str, int]:
    created: dict[str, int] = {}
    for transfer in request.transfers:
        spec = transfer.new_item
        if spec is None:
            continue
        created[spec.code] = create_item(
            session,
            user_id=user_id,
            new=NewItem(
                project_id=project_id,
                code=spec.code,
                description=spec.description,
                level=calculations.LEAF_LEVEL,
                parent_id=spec.parent_id,
                unit_id=spec.unit_id,
                responsible_id=spec.responsible_id,
                cost_type=spec.cost_type,
                capex=spec.capex,
                cost_center=spec.cost_center,
                quantity=spec.quantity,
                unit_price_cents=spec.unit_price_cents,
            ),
        )
    return created


def _proposed_transfers(
    transfers: Sequence[TransferRequest],
    items: Sequence[ItemLine],
    new_ids: Mapping[str, int],
) -> tuple[ProposedTransfer, ...]:
    from src.modulos.governanca.service import ProposedTransfer

    by_code = {item.code: item for item in items}
    proposed: list[ProposedTransfer] = []
    for transfer in transfers:
        if transfer.new_item is not None:
            target_id = new_ids[transfer.target_code]
        else:
            target_id = by_code[transfer.target_code].id
        proposed.append(
            ProposedTransfer(
                source_item_id=by_code[transfer.source_code].id,
                target_item_id=target_id,
                value_cents=transfer.value_cents,
                new_item=transfer.new_item is not None,
            )
        )
    return tuple(proposed)


def _check_sources_free(
    session: Session,
    *,
    project_id: int,
    items: Sequence[ItemLine],
    transfers: Sequence[ProposedTransfer],
) -> None:
    bases = _current_bases(session, project_id=project_id, items=items)
    reservations = _reservations(session, project_id=project_id)
    codes = {item.id: item.code for item in items}
    values: dict[int, int] = {}
    for transfer in transfers:
        values[transfer.source_item_id] = (
            values.get(transfer.source_item_id, 0) + transfer.value_cents
        )
    for source_id, value_cents in values.items():
        free = calculations.free_balance_cents(
            source_id,
            base_cents=bases.get(source_id, 0),
            committed_cents=COMMITTED_CENTS,
            reservations=reservations,
        )
        validation.check_reallocation_balance(
            item_code=codes.get(source_id, ""), value_cents=value_cents, free_cents=free
        )


def _reservations(
    session: Session, *, project_id: int, exclude_change_id: int | None = None
) -> tuple[calculations.ReservationLine, ...]:
    """The balance reserved by other open SMs: their transfers not yet applied to the EAC."""
    from src.modulos.governanca import service as governanca

    return tuple(
        calculations.ReservationLine(
            source_item_id=line.source_item_id, value_cents=line.value_cents
        )
        for line in governanca.pending_reallocations(
            session, project_id=project_id, exclude_change_id=exclude_change_id
        )
    )


# ── Opções dos formulários da tela (ISSUE-030) ───────────────────────────


@dataclass(frozen=True)
class EacOption:
    """Um item da EAC como os selects da tela o listam, com o saldo livre e o próximo código."""

    code: str
    description: str
    free_balance_cents: int | None = None
    next_code: str = ""


@dataclass(frozen=True)
class RevisionSourceOption:
    """Uma SM aprovada com custo ainda não incorporada: a origem possível de uma revisão."""

    change_id: int
    code: str
    cost_cents: int


def free_balances(session: Session, *, project_id: int) -> dict[int, int]:
    """O saldo livre de cada item de custo do projeto, em centavos, por id do item."""
    items = _lines_by_project(session, [project_id]).get(project_id, [])
    return _free_balances(session, project_id=project_id, items=items)


def _free_balances(
    session: Session, *, project_id: int, items: Sequence[ItemLine]
) -> dict[int, int]:
    bases = _current_bases(session, project_id=project_id, items=items)
    reservations = _reservations(session, project_id=project_id)
    return {
        item.id: calculations.free_balance_cents(
            item.id,
            base_cents=bases.get(item.id, 0),
            committed_cents=COMMITTED_CENTS,
            reservations=reservations,
        )
        for item in items
        if item.level >= calculations.LEAF_LEVEL
    }


def item_options(session: Session, *, project_id: int) -> tuple[EacOption, ...]:
    """Os itens de custo (nível 3) do projeto, com o saldo livre: origem e destino do remanejamento."""
    items = _lines_by_project(session, [project_id]).get(project_id, [])
    balances = _free_balances(session, project_id=project_id, items=items)
    return tuple(
        EacOption(
            code=item.code,
            description=item.description,
            free_balance_cents=balances.get(item.id, 0),
        )
        for item in items
        if item.level >= calculations.LEAF_LEVEL
    )


@dataclass(frozen=True)
class CostItemBalance:
    """Um item de custo (nível 3) com o saldo a comprometer, como o plano de compras o lê (D9)."""

    item_id: int
    code: str
    description: str
    saldo_cents: int


def cost_item_balances(
    session: Session, *, project_id: int, reference_date: date
) -> tuple[CostItemBalance, ...]:
    """Os itens de custo do projeto com o saldo a comprometer na data de referência (D9).

    Leitura aditiva para o plano de compras: o saldo é o do mapa de controle (orçado atual menos
    o comprometido do ERP), calculado na hora; nada é gravado. O item de nível 3 é a folha que
    um pacote pode custear.
    """
    projects = configuracoes.list_projects(session)
    project = next((item for item in projects if item.id == project_id), None)
    if project is None:
        return ()
    bands = _deviation_bands(session, reference_date=reference_date)
    columns = _project_columns(session, project, bands=bands, reference_date=reference_date)
    return tuple(
        CostItemBalance(
            item_id=row.item_id,
            code=row.code,
            description=row.description,
            saldo_cents=row.saldo_cents,
        )
        for row in columns.rows
        if row.level == calculations.LEAF_LEVEL and row.item_id is not None
    )


def subpackage_options(session: Session, *, project_id: int) -> tuple[EacOption, ...]:
    """Os subpacotes (nível 2) do projeto, com o próximo código livre: onde um item novo nasce."""
    items = _lines_by_project(session, [project_id]).get(project_id, [])
    codes = [item.code for item in items]
    return tuple(
        EacOption(
            code=item.code,
            description=item.description,
            next_code=calculations.next_item_code(item.code, codes),
        )
        for item in items
        if item.level == calculations.PORTFOLIO_MAIN_LEVEL
    )


def next_revision(session: Session, *, project_id: int) -> int:
    """O número da próxima revisão do projeto: a última mais um; zero sem nenhuma revisão."""
    latest = _latest_revision(session, project_id=project_id)
    return 0 if latest is None else latest + 1


def revision_source_options(
    session: Session, *, project_id: int
) -> tuple[RevisionSourceOption, ...]:
    """As SM aprovadas com custo que a revisão pode incorporar, pela fachada da Governança."""
    from src.modulos.governanca import service as governanca

    return tuple(
        RevisionSourceOption(
            change_id=source.change_id, code=source.code, cost_cents=source.cost_cents
        )
        for source in governanca.eac_revision_sources(session, project_id=project_id)
    )


def _reallocation_title(request: ReallocationRequest) -> str:
    title = request.title.strip()
    if title:
        return title
    if len(request.transfers) == 1:
        transfer = request.transfers[0]
        return (
            f"Remanejamento de {format_brl(transfer.value_cents)} do item "
            f"{transfer.source_code} para o item {transfer.target_code}"
        )
    total = sum(transfer.value_cents for transfer in request.transfers)
    return f"Remanejamento de {format_brl(total)} na EAC"


def apply_reallocations(
    session: Session,
    *,
    change: ReallocationChange,
    user: User,
    reference_date: date,
) -> int:
    """Apply the approved transfers to the EAC, inside the decision transaction (HU-088, D9).

    The free balance is checked again, now without the reserve of the own SM, because other
    SMs may have entered the queue since the request. Each applied line lands in
    ``eac_remanejamento`` pointing at the next revision (the one that will consolidate it; zero
    without any revision), and the transfers of the SM are marked applied in the same
    transaction. The committed part enters with the control map (ISSUE-031).
    """
    from src.modulos.governanca import service as governanca

    transfers = governanca.pending_change_transfers(session, change_id=change.id)
    if not transfers:
        return 0
    items = _lines_by_project(session, [change.project_id]).get(change.project_id, [])
    bases = _current_bases(session, project_id=change.project_id, items=items)
    codes = {item.id: item.code for item in items}
    latest = _latest_revision(session, project_id=change.project_id)
    revision = 0 if latest is None else latest + 1
    reservations = _reservations(session, project_id=change.project_id, exclude_change_id=change.id)
    values: dict[int, int] = {}
    for transfer in transfers:
        values[transfer.source_item_id] = (
            values.get(transfer.source_item_id, 0) + transfer.value_cents
        )
    for source_id, value_cents in values.items():
        free = calculations.free_balance_cents(
            source_id,
            base_cents=bases.get(source_id, 0),
            committed_cents=COMMITTED_CENTS,
            reservations=reservations,
        )
        validation.check_reallocation_balance(
            item_code=codes.get(source_id, ""), value_cents=value_cents, free_cents=free
        )
    for transfer in transfers:
        if transfer.target_item_id not in bases:
            raise InvalidDataError(
                {
                    REALLOCATION_FIELD: REALLOCATION_TARGET_UNKNOWN_MESSAGE.format(
                        code=transfer.target_item_id
                    )
                }
            )
        recording.create(
            session,
            user_id=user.id,
            record=EacReallocation(
                project_id=change.project_id,
                source_item_id=transfer.source_item_id,
                target_item_id=transfer.target_item_id,
                applied_by_id=user.person_id,
                change_id=change.id,
                revision=revision,
                applied_on=reference_date,
                value_cents=transfer.value_cents,
                new_item=transfer.new_item,
                justification=change.title,
            ),
        )
    governanca.mark_reallocations_applied(
        session,
        change_id=change.id,
        applied_by_id=user.person_id,
        applied_on=reference_date,
        revision=revision,
    )
    return len(transfers)


# ── Revisões da EAC (ISSUE-030) ──────────────────────────────────────────


@dataclass(frozen=True)
class AdjustmentRequest:
    """O ajuste de valor de um item da EAC na revisão: o código e o delta em centavos."""

    code: str
    delta_cents: int


@dataclass(frozen=True)
class RevisionItemRequest:
    """O item novo que a revisão cria, com o valor que a SM aprovada financia."""

    code: str
    description: str
    base_cents: int
    parent_id: int | None = None
    unit_id: int | None = None
    cost_type: str | None = None
    capex: bool | None = None
    cost_center: str | None = None
    responsible_id: int | None = None
    quantity: Decimal | None = None
    unit_price_cents: int | None = None


@dataclass(frozen=True)
class RevisionRequest:
    """A revisão pedida pela tela da EAC: a SM que a origina, a justificativa e o que muda."""

    change_id: int
    justification: str
    adjustments: tuple[AdjustmentRequest, ...] = ()
    new_items: tuple[RevisionItemRequest, ...] = ()


@dataclass(frozen=True)
class RevisionView:
    """Uma revisão da EAC como a tela e os exports a leem, com o total das linhas congeladas."""

    id: int
    project_id: int
    revision: int
    change_id: int | None
    change_code: str
    approved_by: str
    revision_date: date
    justification: str
    total_cents: int


@dataclass(frozen=True)
class ReallocationView:
    """Um remanejamento aplicado ou pendente, como a tela da EAC o lista."""

    id: int
    change_id: int
    change_code: str
    situation: str
    source_code: str
    target_code: str
    value_cents: int
    new_item: bool
    applied: bool
    applied_on: date | None
    revision: int
    justification: str
    free_balance_cents: int | None = None
    source_description: str = ""
    target_description: str = ""
    author: str = ""


@dataclass(frozen=True)
class ReallocationList:
    """Os remanejamentos da EAC: os aplicados (da revisão pedida) e os pendentes de decisão."""

    applied: tuple[ReallocationView, ...]
    pending: tuple[ReallocationView, ...]


def revisions(session: Session, *, project_id: int) -> tuple[RevisionView, ...]:
    """The revisions of the project, oldest first, each with the frozen total of its items."""
    records = session.scalars(
        select(EacRevision)
        .where(EacRevision.project_id == project_id)
        .order_by(EacRevision.revision)
    ).all()
    if not records:
        return ()
    totals = {
        row[0]: int(row[1] or 0)
        for row in session.execute(
            select(EacRevisionItem.revision_id, func.sum(EacRevisionItem.base_cents))
            .where(EacRevisionItem.revision_id.in_([record.id for record in records]))
            .group_by(EacRevisionItem.revision_id)
        )
    }
    from src.modulos.governanca import service as governanca

    codes = governanca.change_codes(
        session, change_ids=[record.change_id for record in records if record.change_id]
    )
    names = configuracoes.person_names(session, [record.approved_by_id for record in records])
    return tuple(
        RevisionView(
            id=record.id,
            project_id=record.project_id,
            revision=record.revision,
            change_id=record.change_id,
            change_code=codes.get(record.change_id or 0, ""),
            approved_by=names.get(record.approved_by_id, ""),
            revision_date=record.revision_date,
            justification=record.justification,
            total_cents=totals.get(record.id, 0),
        )
        for record in records
    )


def reallocations(
    session: Session, *, project_id: int, revision: int | None = None
) -> ReallocationList:
    """The reallocations of the project: the applied ones (optionally of one revision) and the pending.

    A pending line carries the free balance of its origin as it stands without the reserve of its
    own SM, so the screen shows how much still fits.
    """
    from src.modulos.governanca import service as governanca

    items = _lines_by_project(session, [project_id]).get(project_id, [])
    codes = {item.id: item.code for item in items}
    descriptions = {item.id: item.description for item in items}
    statement = (
        select(EacReallocation)
        .where(EacReallocation.project_id == project_id)
        .order_by(EacReallocation.id)
    )
    applied_rows = [
        row for row in session.scalars(statement) if revision is None or row.revision == revision
    ]
    change_codes = governanca.change_codes(
        session, change_ids=[row.change_id for row in applied_rows if row.change_id]
    )
    applied_names = configuracoes.person_names(session, [row.applied_by_id for row in applied_rows])
    applied = tuple(
        ReallocationView(
            id=row.id,
            change_id=row.change_id or 0,
            change_code=change_codes.get(row.change_id or 0, ""),
            situation="",
            source_code=codes.get(row.source_item_id, ""),
            target_code=codes.get(row.target_item_id, ""),
            value_cents=row.value_cents,
            new_item=row.new_item,
            applied=True,
            applied_on=row.applied_on,
            revision=row.revision,
            justification=row.justification or "",
            source_description=descriptions.get(row.source_item_id, ""),
            target_description=descriptions.get(row.target_item_id, ""),
            author=applied_names.get(row.applied_by_id, ""),
        )
        for row in applied_rows
    )
    pending_lines = governanca.pending_reallocations(session, project_id=project_id)
    pending_names = configuracoes.person_names(
        session, [line.requester_id for line in pending_lines]
    )
    bases = _current_bases(session, project_id=project_id, items=items)
    pending = tuple(
        ReallocationView(
            id=line.transfer_id,
            change_id=line.change_id,
            change_code=line.change_code,
            situation=line.situation,
            source_code=codes.get(line.source_item_id, ""),
            target_code=codes.get(line.target_item_id, ""),
            value_cents=line.value_cents,
            new_item=line.new_item,
            applied=False,
            applied_on=None,
            revision=0,
            justification=line.justification,
            free_balance_cents=calculations.free_balance_cents(
                line.source_item_id,
                base_cents=bases.get(line.source_item_id, 0),
                committed_cents=COMMITTED_CENTS,
                reservations=tuple(
                    calculations.ReservationLine(
                        source_item_id=other.source_item_id, value_cents=other.value_cents
                    )
                    for other in pending_lines
                    if other.change_id != line.change_id
                ),
            ),
            source_description=descriptions.get(line.source_item_id, ""),
            target_description=descriptions.get(line.target_item_id, ""),
            author=pending_names.get(line.requester_id, ""),
        )
        for line in pending_lines
    )
    return ReallocationList(applied=applied, pending=pending)


def create_revision(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: RevisionRequest,
    reference_date: date,
) -> RevisionView:
    """Create the revision of the EAC from an approved SM with cost (HU-087, Gestor only).

    The revision only exists from an approved SM whose cost is not incorporated yet; the sum of
    the increases (the adjustments plus the new items) cannot exceed the approved cost. The
    revision consolidates the reallocations already applied and freezes the baseline of every
    item of level 3, including the items new, which are born here. Writing
    ``eac_revisao_incorporada`` on the SM belongs to the Governança facade.
    """
    rbac.require_module(user, MODULE)
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(REVISION_DENIED_MESSAGE)
    project_id = scope.require_project()
    from src.modulos.governanca import service as governanca

    source = governanca.change_eac_source(session, change_id=request.change_id)
    if source is None or source.project_id != project_id:
        raise InvalidDataError({validation.FIELD_REVISION_CHANGE: REVISION_CHANGE_UNKNOWN_MESSAGE})
    if source.incorporated_revision is not None:
        raise InvalidDataError(
            {validation.FIELD_REVISION_CHANGE: REVISION_ALREADY_INCORPORATED_MESSAGE}
        )
    validation.check_revision_source(
        validation.RevisionSource(
            change_id=source.change_id, approved=source.approved, cost_cents=source.cost_cents
        )
    )
    justification = request.justification.strip()
    if not justification:
        raise InvalidDataError(
            {validation.FIELD_REVISION_JUSTIFICATION: REVISION_JUSTIFICATION_MESSAGE}
        )
    items = _lines_by_project(session, [project_id]).get(project_id, [])
    deltas = _adjustment_deltas(items, request.adjustments)
    _check_new_items(items, request.new_items)
    increase = sum(item.base_cents for item in request.new_items) + sum(
        adjustment.delta_cents for adjustment in request.adjustments
    )
    validation.check_new_item_cost(value_cents=increase, approved_cents=source.cost_cents)
    new_ids = _create_revision_items(
        session, user_id=user.id, project_id=project_id, request=request
    )
    bases = _current_bases(session, project_id=project_id, items=items)
    latest = _latest_revision(session, project_id=project_id)
    revision = 0 if latest is None else latest + 1
    record = recording.create(
        session,
        user_id=user.id,
        record=EacRevision(
            project_id=project_id,
            change_id=source.change_id,
            approved_by_id=user.person_id,
            revision=revision,
            revision_date=reference_date,
            justification=justification,
        ),
    )
    frozen = [
        EacRevisionItem(
            revision_id=record.id,
            item_id=item.id,
            base_cents=bases.get(item.id, 0) + deltas.get(item.id, 0),
        )
        for item in items
        if item.level >= calculations.LEAF_LEVEL
    ]
    frozen.extend(
        EacRevisionItem(
            revision_id=record.id, item_id=new_ids[item.code], base_cents=item.base_cents
        )
        for item in request.new_items
    )
    session.add_all(frozen)
    session.flush()
    freeze_financial_curve(session, revision=record)
    governanca.incorporate_eac_revision(
        session, user=user, change_id=source.change_id, revision=revision
    )
    return RevisionView(
        id=record.id,
        project_id=project_id,
        revision=revision,
        change_id=source.change_id,
        change_code=source.code,
        approved_by=user.name,
        revision_date=reference_date,
        justification=justification,
        total_cents=sum(line.base_cents for line in frozen),
    )


def _adjustment_deltas(
    items: Sequence[ItemLine], adjustments: Sequence[AdjustmentRequest]
) -> dict[int, int]:
    leaves = {item.code: item for item in items if item.level >= calculations.LEAF_LEVEL}
    deltas: dict[int, int] = {}
    for adjustment in adjustments:
        item = leaves.get(adjustment.code)
        if item is None:
            raise InvalidDataError(
                {
                    validation.FIELD_REVISION_ITEMS: REVISION_ITEM_UNKNOWN_MESSAGE.format(
                        code=adjustment.code
                    )
                }
            )
        deltas[item.id] = deltas.get(item.id, 0) + adjustment.delta_cents
    return deltas


def _check_new_items(items: Sequence[ItemLine], new_items: Sequence[RevisionItemRequest]) -> None:
    codes = {item.code for item in items}
    seen: set[str] = set()
    for item in new_items:
        if item.code in codes:
            raise InvalidDataError(
                {validation.FIELD_REVISION_ITEMS: NEW_ITEM_CODE_MESSAGE.format(code=item.code)}
            )
        if item.code in seen:
            raise InvalidDataError(
                {
                    validation.FIELD_REVISION_ITEMS: REVISION_NEW_ITEM_DUPLICATE_MESSAGE.format(
                        code=item.code
                    )
                }
            )
        if item.base_cents < 0:
            raise InvalidDataError(
                {
                    validation.FIELD_REVISION_ITEMS: REVISION_NEW_ITEM_VALUE_MESSAGE.format(
                        code=item.code
                    )
                }
            )
        seen.add(item.code)


def _create_revision_items(
    session: Session, *, user_id: int, project_id: int, request: RevisionRequest
) -> dict[str, int]:
    created: dict[str, int] = {}
    for item in request.new_items:
        created[item.code] = create_item(
            session,
            user_id=user_id,
            new=NewItem(
                project_id=project_id,
                code=item.code,
                description=item.description,
                level=calculations.LEAF_LEVEL,
                parent_id=item.parent_id,
                unit_id=item.unit_id,
                responsible_id=item.responsible_id,
                cost_type=item.cost_type,
                capex=item.capex,
                cost_center=item.cost_center,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
            ),
        )
    return created


# ── As tabelas de revisões e remanejamentos da tela ──────────────────────


@dataclass(frozen=True)
class RevisionRow:
    """Uma revisão como a tabela da tela e os exports a leem, com o projeto e a variação."""

    view: RevisionView
    project_label: str
    variation_cents: int | None
    is_current: bool


@dataclass(frozen=True)
class ReallocationRow:
    """Um remanejamento como a tabela da tela e os exports o leem, com o projeto."""

    view: ReallocationView
    project_label: str


def revision_rows(session: Session, *, project_ids: Sequence[int]) -> tuple[RevisionRow, ...]:
    """As revisões dos projetos, cada uma com a variação sobre a revisão anterior do mesmo projeto."""
    labels = {project.id: _label(project) for project in configuracoes.list_projects(session)}
    rows: list[RevisionRow] = []
    for project_id in project_ids:
        views = revisions(session, project_id=project_id)
        previous: int | None = None
        for index, view in enumerate(views):
            rows.append(
                RevisionRow(
                    view=view,
                    project_label=labels.get(project_id, ""),
                    variation_cents=None if previous is None else view.total_cents - previous,
                    is_current=index == len(views) - 1,
                )
            )
            previous = view.total_cents
    return tuple(rows)


def reallocation_rows(
    session: Session, *, project_ids: Sequence[int]
) -> tuple[ReallocationRow, ...]:
    """Os remanejamentos aplicados e pendentes dos projetos, na ordem em que a tela os lista."""
    labels = {project.id: _label(project) for project in configuracoes.list_projects(session)}
    rows: list[ReallocationRow] = []
    for project_id in project_ids:
        listing = reallocations(session, project_id=project_id)
        rows.extend(
            ReallocationRow(view=view, project_label=labels.get(project_id, ""))
            for view in (*listing.applied, *listing.pending)
        )
    return tuple(rows)


# ── Mapa de controle, projeção e custos do ERP (ISSUE-031) ───────────────


PROJECTION_ITEM_MESSAGE = "A projeção no término é de um item de custo (nível 3) da EAC."
ERP_ITEM_MESSAGE = "A linha do ERP aponta para um item que não é de custo (nível 3) do projeto."
ERP_VALUE_MESSAGE = "Os valores do custo do ERP não podem ser negativos."
ERP_EMPTY_MESSAGE = (
    "A linha do ERP precisa de ao menos um valor: comprometido, realizado ou projeção."
)


@dataclass(frozen=True)
class ProjectionView:
    """A projeção no término de um item como o mapa e o histórico a mostram."""

    item_id: int
    value_cents: int
    on: date
    origin: str
    author: str
    justification: str


@dataclass(frozen=True)
class ErpCostLine:
    """Uma linha do fechamento do ERP: o item, o mês e os três valores, em centavos."""

    item_id: int
    month: date
    committed_cents: int | None = None
    actual_cents: int | None = None
    projection_cents: int | None = None


@dataclass(frozen=True)
class MapaRow:
    """Uma linha do mapa de controle: item, subtotal de pacote ou a linha do escopo.

    As colunas aditivas vêm dos fatos; o remanejamento, o saldo, o desvio, o percentual e a faixa
    do mapa de calor são calculados aqui.
    """

    code: str
    description: str
    level: int
    item_id: int | None
    project_id: int | None
    project_label: str | None
    baseline_cents: int
    reallocation_cents: int
    current_cents: int
    committed_cents: int
    actual_cents: int
    saldo_cents: int
    projection_cents: int
    deviation_cents: int
    deviation_percent: Decimal | None
    band: calculations.DeviationBand


@dataclass(frozen=True)
class MapaReserveSummary:
    """A faixa Reservas do mapa: o saldo das reservas e a cobertura do desvio projetado."""

    contingency_balance_cents: int
    contingency_consumption_pct: Decimal | None
    in_analysis_cents: int
    management_balance_cents: int
    covers_deviation: bool


@dataclass(frozen=True)
class MapaControleView:
    """O mapa de controle do escopo: as linhas, a linha do projeto (ou do portfólio) e as faixas."""

    scope_label: str
    is_portfolio: bool
    rows: tuple[MapaRow, ...]
    total: MapaRow
    bands: tuple[Decimal, ...]
    reserves: MapaReserveSummary | None


@dataclass(frozen=True)
class _MapPlace:
    """Onde uma linha do mapa fica: código, descrição, nível e o projeto de origem."""

    code: str
    description: str
    level: int
    item_id: int | None = None
    project_id: int | None = None
    project_label: str | None = None


@dataclass(frozen=True)
class _MapAmounts:
    """As colunas aditivas de uma linha, já subtotalizadas; os derivados saem no mapa."""

    baseline_cents: int
    current_cents: int
    committed_cents: int
    actual_cents: int
    projection_cents: int


@dataclass(frozen=True)
class _ProjectColumns:
    """O que a leitura de um projeto devolve: as linhas e os totais de nível 1."""

    rows: tuple[MapaRow, ...]
    amounts: _MapAmounts


def update_projection(
    session: Session,
    *,
    item_id: int,
    valor_centavos: int,
    justificativa: str,
    autor_id: int,
    hoje: date,
) -> ProjectionView:
    """Atualizar a projeção no término de um item, com histórico e justificativa (HU-090).

    A projeção exige justificativa, não pode ser negativa nem ficar abaixo do realizado do item
    (a regra do protótipo) e entra como fato manual datado; a vigente passa a ser a última. O
    ``autor_id`` é a pessoa do cadastro que informa, e a trilha nomeia o colaborador dela.
    """
    item = session.get(EacItem, item_id)
    if item is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    if item.level < calculations.LEAF_LEVEL:
        raise InvalidDataError(PROJECTION_ITEM_MESSAGE)
    actual = _erp_totals(session, item_ids=[item.id], cutoff=hoje).get(
        item.id, calculations.ErpTotals(committed_cents=0, actual_cents=0)
    )
    form = validation.parse_projection_form(
        {
            validation.FIELD_PROJECTION: format_brl(valor_centavos),
            validation.FIELD_JUSTIFICATION: justificativa,
        },
        actual_cents=actual.actual_cents,
    )
    collaborator_id, person_id = _operator_ids(session, autor_id)
    record = recording.create(
        session,
        user_id=collaborator_id,
        record=EacProjection(
            item_id=item.id,
            author_id=person_id,
            projected_on=hoje,
            value_cents=form.value_cents,
            origin=calculations.MANUAL_ORIGIN,
            justification=form.justification,
        ),
    )
    return _projection_view(session, record)


def import_erp_costs(
    session: Session,
    *,
    projeto_id: int,
    linhas: Sequence[ErpCostLine],
    importado_por_id: int,
    hoje: date,
) -> int:
    """Gravar o fechamento do ERP: um fato por item e mês, substituindo o mês reimportado.

    É a fachada da confirmação da importação (a leitura e a conferência são da rota). O mesmo item
    e mês reimportado atualiza a linha, nunca a duplica; o mês é normalizado para o primeiro dia e
    o ``importado_em`` vem do relógio. Devolve quantos fatos foram gravados. O ``importado_por_id``
    é a pessoa do cadastro que importa, e a trilha nomeia o colaborador dela.
    """
    if not linhas:
        return 0
    collaborator_id, person_id = _operator_ids(session, importado_por_id)
    items = _cost_items_of(session, project_id=projeto_id)
    existing = _erp_costs_of(session, item_ids=[line.item_id for line in linhas])
    now = calendario.now()
    for line in linhas:
        _check_erp_line(line, items=items, hoje=hoje)
        month = line.month.replace(day=1)
        record = existing.get((line.item_id, month))
        if record is None:
            recording.create(
                session,
                user_id=collaborator_id,
                record=ErpCost(
                    project_id=projeto_id,
                    item_id=line.item_id,
                    imported_by_id=person_id,
                    month=month,
                    committed_cents=line.committed_cents,
                    actual_cents=line.actual_cents,
                    projection_cents=line.projection_cents,
                    imported_at=now,
                ),
            )
            continue
        before = audit.snapshot(record)
        record.committed_cents = line.committed_cents
        record.actual_cents = line.actual_cents
        record.projection_cents = line.projection_cents
        record.imported_by_id = person_id
        record.imported_at = now
        session.flush()
        audit.changed(
            session,
            user_id=collaborator_id,
            entity=record.__tablename__,
            record=record,
            before=before,
        )
    return len(linhas)


def _check_erp_line(line: ErpCostLine, *, items: Mapping[int, EacItem], hoje: date) -> None:
    item = items.get(line.item_id)
    if item is None or item.level < calculations.LEAF_LEVEL:
        raise InvalidDataError({validation.FIELD_ERP_ITEM: ERP_ITEM_MESSAGE})
    if (line.month.year, line.month.month) > (hoje.year, hoje.month):
        raise InvalidDataError({validation.FIELD_ERP_MONTH: validation.ERP_MONTH_IN_THE_FUTURE})
    values = (line.committed_cents, line.actual_cents, line.projection_cents)
    if any(value is not None and value < 0 for value in values):
        raise InvalidDataError({validation.FIELD_ERP_VALUES: ERP_VALUE_MESSAGE})
    if all(value is None for value in values):
        raise InvalidDataError({validation.FIELD_ERP_VALUES: ERP_EMPTY_MESSAGE})
    if (
        line.projection_cents is not None
        and line.actual_cents is not None
        and line.projection_cents < line.actual_cents
    ):
        raise InvalidDataError(
            {validation.FIELD_ERP_PROJECTION: validation.PROJECTION_BELOW_ACTUAL}
        )


def _cost_items_of(session: Session, *, project_id: int) -> dict[int, EacItem]:
    statement = select(EacItem).where(EacItem.project_id == project_id)
    return {item.id: item for item in session.scalars(statement)}


def _erp_costs_of(session: Session, *, item_ids: Sequence[int]) -> dict[tuple[int, date], ErpCost]:
    if not item_ids:
        return {}
    statement = select(ErpCost).where(ErpCost.item_id.in_(sorted(set(item_ids))))
    return {(row.item_id, row.month): row for row in session.scalars(statement)}


def _operator_ids(session: Session, operator_id: int) -> tuple[int, int]:
    """O (colaborador, pessoa) de quem opera: ``operator_id`` é a pessoa; sem acesso, o colaborador."""
    for access in configuracoes.list_active_access(session):
        if access.person_id == operator_id:
            return access.id, access.person_id
    access = configuracoes.find_access(session, operator_id)
    if access is not None:
        return access.id, access.person_id
    return operator_id, operator_id


def _projection_view(session: Session, record: EacProjection) -> ProjectionView:
    names = configuracoes.person_names(session, [record.author_id])
    return ProjectionView(
        item_id=record.item_id,
        value_cents=record.value_cents,
        on=record.projected_on,
        origin=record.origin,
        author=names.get(record.author_id, ""),
        justification=record.justification,
    )


def mapa_controle(session: Session, *, scope: Scope, reference_date: date) -> MapaControleView:
    """O mapa de controle do escopo: item a item no projeto, um registro por projeto na carteira.

    As colunas aditivas vêm dos fatos: a linha de base congelada da última revisão, os
    remanejamentos aplicados e ainda não consolidados, o comprometido e o realizado dos custos do
    ERP somados até a data de referência e a projeção vigente (manual ou do fechamento). Os
    subtotais de pacote e subpacote, a linha do projeto e a faixa do mapa de calor (parâmetros
    vigentes) são calculados aqui. Na carteira, cada linha é um projeto com EAC.
    """
    bands = _deviation_bands(session, reference_date=reference_date)
    projects = configuracoes.list_projects(session)
    if scope.is_portfolio:
        return _portfolio_map(session, projects, bands=bands, reference_date=reference_date)
    project = _project_of(projects, scope)
    columns = _project_columns(session, project, bands=bands, reference_date=reference_date)
    total = _map_row(
        _MapPlace(
            code=calculations.ROOT_CODE,
            description=project.name,
            level=0,
            project_id=project.id,
            project_label=_label(project),
        ),
        columns.amounts,
        bands=bands,
    )
    return MapaControleView(
        scope_label=_label(project),
        is_portfolio=False,
        rows=columns.rows,
        total=total,
        bands=bands,
        reserves=_map_reserves(
            session, project_ids=[project.id], deviation_cents=total.deviation_cents
        ),
    )


def _portfolio_map(
    session: Session,
    projects: Sequence[configuracoes.ProjectSummary],
    *,
    bands: tuple[Decimal, ...],
    reference_date: date,
) -> MapaControleView:
    rows: list[MapaRow] = []
    for number, project in enumerate(projects, start=1):
        columns = _project_columns(session, project, bands=bands, reference_date=reference_date)
        if not columns.rows:
            continue
        rows.append(
            _map_row(
                _MapPlace(
                    code=str(number),
                    description=_label(project),
                    level=1,
                    project_id=project.id,
                    project_label=_label(project),
                ),
                columns.amounts,
                bands=bands,
            )
        )
    total = _map_row(
        _MapPlace(code=calculations.ROOT_CODE, description=PORTFOLIO_ROOT_DESCRIPTION, level=0),
        _sum_amounts(rows),
        bands=bands,
    )
    return MapaControleView(
        scope_label=PORTFOLIO_LABEL,
        is_portfolio=True,
        rows=tuple(rows),
        total=total,
        bands=bands,
        reserves=_map_reserves(
            session,
            project_ids=[project.id for project in projects],
            deviation_cents=total.deviation_cents,
        ),
    )


def _project_columns(
    session: Session,
    project: configuracoes.ProjectSummary,
    *,
    bands: tuple[Decimal, ...],
    reference_date: date,
) -> _ProjectColumns:
    items = _lines_by_project(session, [project.id]).get(project.id, [])
    if not items:
        return _ProjectColumns(rows=(), amounts=_MapAmounts(0, 0, 0, 0, 0))
    label = _label(project)
    item_ids = [item.id for item in items]
    baselines = _baseline_bases(session, project_id=project.id, items=items)
    currents = _current_bases(session, project_id=project.id, items=items)
    erp = _erp_totals(session, item_ids=item_ids, cutoff=reference_date)
    committed = {item.id: erp[item.id].committed_cents if item.id in erp else 0 for item in items}
    actual = {item.id: erp[item.id].actual_cents if item.id in erp else 0 for item in items}
    projected = calculations.projected_total_cents(
        items, current_bases=currents, facts=_projection_facts(session, item_ids=item_ids)
    )
    baseline_totals = _leveled_totals(items, baselines)
    current_totals = _leveled_totals(items, currents)
    committed_totals = _leveled_totals(items, committed)
    actual_totals = _leveled_totals(items, actual)
    rows = tuple(
        _map_row(
            _MapPlace(
                code=item.code,
                description=item.description,
                level=item.level,
                item_id=item.id,
                project_id=project.id,
                project_label=label,
            ),
            _MapAmounts(
                baseline_cents=baseline_totals.get(item.id, 0),
                current_cents=current_totals.get(item.id, 0),
                committed_cents=committed_totals.get(item.id, 0),
                actual_cents=actual_totals.get(item.id, 0),
                projection_cents=projected.by_item.get(item.id, 0),
            ),
            bands=bands,
        )
        for item in sorted(items, key=lambda item: calculations.code_key(item.code))
    )
    amounts = _MapAmounts(
        baseline_cents=_top_total(items, baseline_totals),
        current_cents=_top_total(items, current_totals),
        committed_cents=_top_total(items, committed_totals),
        actual_cents=_top_total(items, actual_totals),
        projection_cents=projected.total_cents,
    )
    return _ProjectColumns(rows=rows, amounts=amounts)


def _map_row(place: _MapPlace, amounts: _MapAmounts, *, bands: tuple[Decimal, ...]) -> MapaRow:
    """A linha do mapa: as colunas aditivas prontas e o saldo, o desvio e a faixa calculados."""
    deviation = calculations.deviation_cents(amounts.projection_cents, amounts.current_cents)
    percent = calculations.deviation_percent(deviation, amounts.current_cents)
    return MapaRow(
        code=place.code,
        description=place.description,
        level=place.level,
        item_id=place.item_id,
        project_id=place.project_id,
        project_label=place.project_label,
        baseline_cents=amounts.baseline_cents,
        reallocation_cents=calculations.reallocation_cents(
            amounts.current_cents, amounts.baseline_cents
        ),
        current_cents=amounts.current_cents,
        committed_cents=amounts.committed_cents,
        actual_cents=amounts.actual_cents,
        saldo_cents=calculations.saldo_a_comprometer_cents(
            amounts.current_cents, amounts.committed_cents
        ),
        projection_cents=amounts.projection_cents,
        deviation_cents=deviation,
        deviation_percent=percent,
        band=calculations.deviation_band(percent, bands),
    )


def _sum_amounts(rows: Sequence[MapaRow]) -> _MapAmounts:
    return _MapAmounts(
        baseline_cents=sum(row.baseline_cents for row in rows),
        current_cents=sum(row.current_cents for row in rows),
        committed_cents=sum(row.committed_cents for row in rows),
        actual_cents=sum(row.actual_cents for row in rows),
        projection_cents=sum(row.projection_cents for row in rows),
    )


def _baseline_bases(
    session: Session, *, project_id: int, items: Sequence[ItemLine]
) -> dict[int, int]:
    """Linha de base de cada item: a base congelada da última revisão, sem os remanejamentos."""
    latest = _latest_revision(session, project_id=project_id)
    revision_bases = (
        _revision_bases(session, project_id=project_id, revision=latest)
        if latest is not None
        else {}
    )
    return calculations.baseline_base_cents(
        items, revision_bases=revision_bases, latest_revision=latest
    )


def _leveled_totals(items: Sequence[ItemLine], values: Mapping[int, int]) -> dict[int, int]:
    """Os subtotais de uma coluna: o valor do item e a soma dos filhos nos pacotes e subpacotes."""
    return calculations.item_totals(
        [replace(item, base_cents=values.get(item.id, 0)) for item in items]
    )


def _top_total(items: Sequence[ItemLine], totals: Mapping[int, int]) -> int:
    """O total do projeto em uma coluna: a soma dos pacotes (nível 1)."""
    return sum(totals.get(item.id, 0) for item in items if item.level == 1)


def _erp_totals(
    session: Session, *, item_ids: Sequence[int], cutoff: date
) -> dict[int, calculations.ErpTotals]:
    """Comprometido e realizado de cada item, somando os meses do ERP até a data de corte."""
    if not item_ids:
        return {}
    statement = select(ErpCost).where(ErpCost.item_id.in_(sorted(set(item_ids))))
    facts = [
        calculations.ErpCostFact(
            item_id=row.item_id,
            month=row.month,
            committed_cents=row.committed_cents,
            actual_cents=row.actual_cents,
            projection_cents=row.projection_cents,
        )
        for row in session.scalars(statement)
    ]
    return calculations.erp_totals_until(facts, cutoff=cutoff)


def projection_cents_by_item(session: Session, *, item_ids: Sequence[int]) -> dict[int, int]:
    """A projeção no término vigente de cada item, em centavos: a do fato mais recente."""
    facts = _projection_facts(session, item_ids=item_ids)
    return {
        item_id: fact.value_cents
        for item_id, fact in calculations.latest_projections(facts).items()
    }


def _projection_facts(
    session: Session, *, item_ids: Sequence[int]
) -> tuple[calculations.ProjectionFact, ...]:
    """Os fatos de projeção dos itens: os manuais e os dos fechamentos do ERP."""
    if not item_ids:
        return ()
    wanted = sorted(set(item_ids))
    facts: list[calculations.ProjectionFact] = []
    manual = (
        select(EacProjection).where(EacProjection.item_id.in_(wanted)).order_by(EacProjection.id)
    )
    facts.extend(
        calculations.ProjectionFact(
            item_id=row.item_id,
            value_cents=row.value_cents,
            on=row.projected_on,
            origin=row.origin,
        )
        for row in session.scalars(manual)
    )
    closed = (
        select(ErpCost)
        .where(ErpCost.item_id.in_(wanted), ErpCost.projection_cents.is_not(None))
        .order_by(ErpCost.id)
    )
    facts.extend(
        calculations.ProjectionFact(
            item_id=row.item_id,
            value_cents=int(row.projection_cents or 0),
            on=row.month,
            origin=calculations.ERP_ORIGIN,
        )
        for row in session.scalars(closed)
    )
    return tuple(facts)


def _deviation_bands(session: Session, *, reference_date: date) -> tuple[Decimal, ...]:
    """As faixas vigentes do mapa de calor: o parâmetro do grupo financeiro ou o padrão."""
    group = configuracoes.current_group(session, group=MODULE, reference_date=reference_date)
    configured = group.get("faixasDesvio")
    bands = (
        tuple(Decimal(str(band)) for band in configured)
        if isinstance(configured, Sequence) and not isinstance(configured, str)
        else ()
    )
    if len(bands) != 3:
        return tuple(Decimal(str(band)) for band in calculations.DEFAULT_DEVIATION_BANDS)
    return bands


# ── Ficha do contrato: medições e aditivos (ISSUE-032) ───────────────────


CONTRACT_NOT_FOUND_MESSAGE = "Contrato não encontrado."
CONTRACT_OTHER_PROJECT_MESSAGE = (
    "O contrato pertence a outro projeto. Abra o projeto dele para operar."
)
MEASUREMENT_NOT_FOUND_MESSAGE = "Medição do contrato não encontrada."
ADDENDUM_SM_MESSAGE = "A SM informada não é do projeto do contrato ou não está aprovada."
MILESTONE_NOT_FOUND_MESSAGE = "Marco de pagamento não encontrado."
CLAIM_NOT_FOUND_MESSAGE = "Claim do contrato não encontrado."
EXTENSION_NOT_FOUND_MESSAGE = "Extensão de prazo não encontrada."
EXTENSION_CLAIM_MESSAGE = "O claim de origem não pertence ao contrato."
CLAIM_DECISION_MESSAGE = "A decisão do claim é Acordado ou Rejeitado."
ATTACHMENT_TABLE = "contrato"
MILESTONE_ATTACHMENT_TABLE = "contrato_marco_pagamento"
CLAIM_ATTACHMENT_TABLE = "contrato_claim"
DEFAULT_CODE_PATTERN = "TN-2026"
CLAIM_CODE_KIND = "CLM"
EXTENSION_CODE_KIND = "EOT"
CLAIM_SM_ORIGIN_CONTRACTOR = "Contratada"
CLAIM_SM_ORIGIN_CLIENT = "Cliente"
CLAIM_SM_ORIGIN_INTERNAL = "Interna"
CLAIM_SM_KIND = {
    validation.CLAIM_KIND_TIME: "Prazo",
    validation.CLAIM_KIND_COST: "Custo",
    validation.CLAIM_KIND_BOTH: "Contratual",
}
CLAIM_DECISIONS = (calculations.CLAIM_AGREED, calculations.CLAIM_REJECTED)
CHANGE_PRIORITY_NORMAL = "Normal"


@dataclass(frozen=True)
class MeasurementView:
    """Uma medição da ficha: período, bruto, retenção, líquido, a situação e a versão do registro."""

    id: int
    number: str
    period: date
    gross_cents: int
    retention_cents: int
    net_cents: int
    milestone_id: int | None
    situation: str
    return_reason: str
    version: int = 1


@dataclass(frozen=True)
class AddendumView:
    """Um aditivo da ficha: data, valor, dias, motivo e as origens (SM e claim)."""

    id: int
    number: str
    signed_on: date
    value_cents: int
    days: int
    reason: str
    change_id: int | None
    change_code: str
    claim_id: int | None


@dataclass(frozen=True)
class MilestoneView:
    """Um marco da ficha: percentual, valor e retenção calculados, e a evidência da aprovação."""

    id: int
    number: str
    description: str
    criteria: str
    pct: int
    value_cents: int
    retention_cents: int
    expected_on: date
    completed_on: date | None
    situation: str
    attachment_id: int | None
    has_evidence: bool
    version: int = 1


@dataclass(frozen=True)
class ClaimView:
    """Um claim da ficha: datas, valores, situação e o alerta de notificação fora do prazo."""

    id: int
    code: str
    direction: str
    kind: str
    cause: str
    description: str
    clause: str
    event_date: date
    notification_date: date
    claimed_cents: int
    claimed_days: int
    recognized_cents: int | None
    recognized_days: int | None
    situation: str
    closed_on: date | None
    change_id: int | None
    change_code: str
    notification_days: int
    notification_late: bool
    risk_code: str = ""
    version: int = 1


@dataclass(frozen=True)
class ExtensionView:
    """Uma EOT da ficha: dias, classificação, decisão e a SM da linha de base do cronograma."""

    id: int
    code: str
    claim_id: int | None
    claim_code: str
    event: str
    requested_days: int
    granted_days: int | None
    classification: str
    method: str
    affected_milestone: str
    requested_on: date
    decided_on: date | None
    situation: str
    change_id: int | None
    change_code: str
    is_open: bool
    version: int = 1


@dataclass(frozen=True)
class ContractView:
    """A ficha do contrato: campos comuns, cascata, saldo e as listas do contrato."""

    id: int
    project_id: int
    number: str
    company: str
    object: str
    modality: str
    eac_code: str
    purchase_package_id: int | None
    manager: str
    fiscal: str
    start: date
    original_end: date
    current_end: date
    retention_pct: int
    claim_notice_days: int
    situation: str
    original_value_cents: int
    addenda_cents: int
    current_value_cents: int
    measured_cents: int
    balance_to_invoice_cents: int
    available_to_measure_cents: int
    cascade: tuple[dict[str, Any], ...]
    measurements: tuple[MeasurementView, ...]
    addenda: tuple[AddendumView, ...]
    milestone_pct_total: int
    milestones: tuple[MilestoneView, ...]
    claims: tuple[ClaimView, ...]
    extensions: tuple[ExtensionView, ...]
    evaluations: tuple[EvaluationView, ...]
    evaluation_trend: tuple[dict[str, int], ...]


def contract_detail(session: Session, *, user: User, contract_id: int) -> ContractView:
    """A ficha do contrato: campos comuns, cascata, saldo a faturar e as listas.

    O valor atual é o original mais os aditivos e o saldo a faturar é o valor atual menos o
    medido aprovado, ambos calculados na leitura; o disponível a medir desconta ainda as
    medições Em análise, como no protótipo. As listas vêm da mais recente para a mais antiga,
    com a retenção do contrato em cada medição; os marcos vêm na ordem de cadastro, com o valor
    e a retenção calculados e a soma dos percentuais, e os claims trazem o alerta de notificação
    fora do prazo do contrato. As avaliações vêm da mais recente para a mais antiga, com os pesos
    congelados em cada critério e a série do Gráfico de Áreas de Avaliação. Quem lê precisa
    alcançar o módulo.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.VIEW)
    contract = _contract_or_refuse(session, contract_id)
    addenda = _addendum_rows(session, contract_id=contract_id)
    measurements = _measurement_rows(session, contract_id=contract_id)
    milestones = _milestone_rows(session, contract_id=contract_id)
    claims = _claim_rows(session, contract_id=contract_id)
    extensions = _extension_rows(session, contract_id=contract_id)
    evaluations = _evaluation_views(session, _evaluation_rows(session, contract_id=contract_id))
    addendum_lines = _addendum_lines(addenda)
    measurement_lines = _measurement_lines(measurements)
    current = calculations.contract_current_value_cents(
        contract.original_value_cents, addendum_lines
    )
    measured = calculations.contract_measured_cents(measurement_lines)
    balance = calculations.contract_balance_to_invoice_cents(current, measured)
    people = configuracoes.person_names(session, [contract.manager_id, contract.fiscal_id])
    companies = configuracoes.list_company_names(session)
    codes = eac_item_codes(session, [contract.eac_item_id] if contract.eac_item_id else [])
    change_codes = _change_codes(
        session,
        [
            *(row.change_id for row in addenda),
            *(row.change_id for row in claims),
            *(row.change_id for row in extensions),
        ],
    )
    claim_codes = {row.id: row.code for row in claims}
    risk_codes = _risk_codes(session, [row.risk_id for row in claims])
    return ContractView(
        id=contract.id,
        project_id=contract.project_id,
        number=contract.number,
        company=companies.get(contract.company_id, ""),
        object=contract.object,
        modality=contract.modality,
        eac_code=codes.get(contract.eac_item_id or 0, ""),
        purchase_package_id=contract.purchase_package_id,
        manager=people.get(contract.manager_id, ""),
        fiscal=people.get(contract.fiscal_id, ""),
        start=contract.start,
        original_end=contract.original_end,
        current_end=contract.current_end,
        retention_pct=contract.retention_pct,
        claim_notice_days=contract.claim_notice_days,
        situation=contract.situation,
        original_value_cents=contract.original_value_cents,
        addenda_cents=sum(row.value_cents for row in addenda),
        current_value_cents=current,
        measured_cents=measured,
        balance_to_invoice_cents=balance,
        available_to_measure_cents=balance - _under_review_cents(measurements),
        cascade=calculations.contract_cascade_steps(
            original_cents=contract.original_value_cents,
            addenda=addendum_lines,
            measurements=measurement_lines,
        ),
        measurements=tuple(_measurement_view(contract, row) for row in measurements),
        addenda=tuple(_addendum_view(row, change_codes=change_codes) for row in addenda),
        milestone_pct_total=calculations.milestone_pct_total([row.pct for row in milestones]),
        milestones=tuple(_milestone_view(current, contract, row) for row in milestones),
        claims=tuple(
            _claim_view(contract, row, change_codes=change_codes, risk_codes=risk_codes)
            for row in claims
        ),
        extensions=tuple(
            _extension_view(row, claim_codes=claim_codes, change_codes=change_codes)
            for row in extensions
        ),
        evaluations=evaluations,
        evaluation_trend=_evaluation_trend(evaluations),
    )


def create_measurement(
    session: Session,
    *,
    user: User,
    scope: Scope,
    contract_id: int,
    form: Mapping[str, str | None],
) -> MeasurementView:
    """Registra um boletim de medição Em análise, conferindo o saldo disponível do contrato.

    O valor bruto não pode superar o valor atual menos o medido aprovado menos o que já está
    Em análise; o número é o próximo da sequência do contrato (``BM-01``, ``BM-02``...) e a
    retenção do contrato sai calculada na leitura. A operação é de quem gere o contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=contract_id)
    parsed = validation.parse_measurement_form(form)
    validation.check_measurement_balance(
        value_cents=parsed.value_cents,
        available_cents=_available_to_measure_cents(session, contract=contract),
    )
    record = recording.create(
        session,
        user_id=user.id,
        record=ContractMeasurement(
            contract_id=contract.id,
            milestone_id=parsed.milestone_id,
            number=_next_measurement_number(session, contract_id=contract.id),
            period=parsed.period,
            gross_cents=parsed.value_cents,
            situation=calculations.SITUATION_UNDER_REVIEW,
        ),
    )
    return _measurement_view(contract, record)


def transition_measurement(
    session: Session,
    *,
    user: User,
    scope: Scope,
    measurement_id: int,
    target: str,
    form: Mapping[str, str | None] | None = None,
) -> MeasurementView:
    """Move a medição no fluxo e, na aprovação, alimenta o realizado do item da EAC.

    A situação atual só admite a próxima do fluxo (Em análise → Aprovada ou Devolvida com
    motivo; Aprovada → Faturada; Faturada → Paga), e a decisão é de quem gere o contrato. A
    aprovação soma o bruto ao realizado do item da EAC do contrato, no mês do período, por um
    fato de ``custo_erp`` (upsert por item e mês): sem fato no mês ele nasce com o bruto
    aprovado; com fato, o bruto entra somado ao realizado. O próprio fluxo impede reprocessar
    a mesma medição (a Aprovada não volta a Em análise), então o bruto entra uma vez; um mês
    reimportado do ERP substitui o fato e a contribuição da medição se perde, como no mapa.
    A medição de marco acompanha o faturamento e o pagamento: o marco vai a Faturado ou Pago
    junto, como no protótipo.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    measurement = session.get(ContractMeasurement, measurement_id)
    if measurement is None:
        raise InvalidDataError(MEASUREMENT_NOT_FOUND_MESSAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=measurement.contract_id)
    validation.check_measurement_transition(measurement.situation, target)
    fields = form or {}
    changes: dict[str, Any] = {"situation": target}
    if target == calculations.SITUATION_RETURNED:
        changes["return_reason"] = validation.parse_return_form(fields)
    recording.update(
        session,
        user_id=user.id,
        record=measurement,
        changes=changes,
        version=fields.get(validation.FIELD_VERSION),
    )
    if target == calculations.SITUATION_APPROVED:
        _apply_measurement_to_eac(session, user=user, contract=contract, measurement=measurement)
    if target in (calculations.SITUATION_INVOICED, calculations.SITUATION_PAID):
        _apply_measurement_to_milestone(session, user=user, measurement=measurement, target=target)
    return _measurement_view(contract, measurement)


def create_addendum(
    session: Session,
    *,
    user: User,
    scope: Scope,
    contract_id: int,
    form: Mapping[str, str | None],
) -> AddendumView:
    """Registra um aditivo aprovado e prorroga o término vigente do contrato.

    O aditivo nasce aprovado ao ser registrado e valor negativo é supressão; o valor atual
    fica calculado na leitura. O término vigente passa a ser o original mais os dias de todos
    os aditivos e é gravado na mesma transação; a SM de origem, quando informada, precisa ser
    aprovada e do projeto do contrato, conferida pela fachada da Governança. A operação é de
    quem gere o contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=contract_id)
    parsed = validation.parse_addendum_form(form)
    _check_addendum_change(session, contract=contract, change_id=parsed.change_id)
    existing = _addendum_rows(session, contract_id=contract.id)
    lines = (
        *_addendum_lines(existing),
        calculations.ContractAddendumLine(value_cents=parsed.value_cents, days=parsed.days),
    )
    record = recording.create(
        session,
        user_id=user.id,
        record=ContractAddendum(
            contract_id=contract.id,
            change_id=parsed.change_id,
            claim_id=parsed.claim_id,
            number=_next_addendum_number(session, contract_id=contract.id),
            signed_on=parsed.signed_on,
            value_cents=parsed.value_cents,
            days=parsed.days,
            reason=parsed.reason,
        ),
    )
    current_end = calculations.contract_current_end_date(contract.original_end, lines)
    if current_end != contract.current_end:
        recording.update(
            session,
            user_id=user.id,
            record=contract,
            changes={"current_end": current_end},
            version=contract.version,
        )
    change_codes = _change_codes(session, [parsed.change_id])
    return _addendum_view(record, change_codes=change_codes)


# ── Marcos, claims e EOT (ISSUE-033) ─────────────────────────────────────


def create_milestone(
    session: Session,
    *,
    user: User,
    scope: Scope,
    contract_id: int,
    form: Mapping[str, str | None],
) -> MilestoneView:
    """Cadastra um marco Previsto, com o percentual que ainda cabe nos 100% do contrato.

    Descrição, critério de aceite, percentual inteiro e data prevista são obrigatórios; a soma
    dos percentuais dos marcos não pode passar de 100%, como o protótipo impede. O valor e a
    retenção saem do percentual sobre o valor atual do contrato, calculados na leitura. A
    operação é de quem gere o contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=contract_id)
    parsed = validation.parse_milestone_form(form)
    milestones = _milestone_rows(session, contract_id=contract.id)
    used = calculations.milestone_pct_total([row.pct for row in milestones])
    validation.check_milestone_pct(used_pct=used, new_pct=parsed.pct)
    record = recording.create(
        session,
        user_id=user.id,
        record=ContractPaymentMilestone(
            contract_id=contract.id,
            number=_next_milestone_number(session, contract_id=contract.id),
            description=parsed.description,
            acceptance_criteria=parsed.criteria,
            pct=parsed.pct,
            expected_on=parsed.expected_on,
            situation=calculations.MILESTONE_FORECAST,
        ),
    )
    return _milestone_view(_current_value_cents(session, contract=contract), contract, record)


def send_milestone_evidence(
    session: Session,
    *,
    user: User,
    scope: Scope,
    milestone_id: int,
    form: Mapping[str, str | None],
    reference_date: date,
    file_name: str | None = None,
    content: bytes = b"",
    storage: FileStorage | None = None,
) -> MilestoneView:
    """Envia a evidência do marco: grava a data de conclusão e o anexo que a comprova.

    A data de conclusão é obrigatória e o arquivo é um anexo de verdade do marco, pelo mecanismo
    de anexos (D5a), com os limites do grupo Anexos vigentes; a aprovação só passa a aceitar o
    marco com esse anexo gravado. A operação é de quem gere o contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    milestone, contract = _milestone_and_contract(session, scope=scope, milestone_id=milestone_id)
    validation.check_milestone_transition(milestone.situation, calculations.MILESTONE_EVIDENCE_SENT)
    completed_on = validation.parse_milestone_evidence_form(form)
    attachment = attachments.upload(
        session,
        user=user,
        new=attachments.NewAttachment(
            origin_table=MILESTONE_ATTACHMENT_TABLE,
            origin_record_id=milestone.id,
            file_name=file_name,
            content=content,
        ),
        reference_date=reference_date,
        storage=storage,
    )
    recording.update(
        session,
        user_id=user.id,
        record=milestone,
        changes={
            "situation": calculations.MILESTONE_EVIDENCE_SENT,
            "completed_on": completed_on,
            "attachment_id": attachment.id,
        },
        version=form.get(validation.FIELD_VERSION),
    )
    return _milestone_view(_current_value_cents(session, contract=contract), contract, milestone)


def approve_milestone(
    session: Session,
    *,
    user: User,
    scope: Scope,
    milestone_id: int,
    form: Mapping[str, str | None] | None = None,
) -> MilestoneView:
    """Aprova o marco (Evidência enviada → Aprovado), com o aceite do fiscal e do gestor.

    A aprovação exige o anexo de evidência gravado (D5a); o registro do aceite é de quem gere o
    contrato, como o protótipo pede.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    milestone, contract = _milestone_and_contract(session, scope=scope, milestone_id=milestone_id)
    validation.check_milestone_transition(milestone.situation, calculations.MILESTONE_APPROVED)
    validation.check_milestone_evidence(has_evidence=milestone.attachment_id is not None)
    recording.update(
        session,
        user_id=user.id,
        record=milestone,
        changes={"situation": calculations.MILESTONE_APPROVED},
        version=(form or {}).get(validation.FIELD_VERSION),
    )
    return _milestone_view(_current_value_cents(session, contract=contract), contract, milestone)


def transition_milestone(
    session: Session,
    *,
    user: User,
    scope: Scope,
    milestone_id: int,
    target: str,
    form: Mapping[str, str | None] | None = None,
) -> MilestoneView:
    """Move o marco no fluxo de faturamento (Aprovado → Faturado → Pago).

    A situação atual só admite a próxima, como no protótipo; a medição vinculada ao marco
    acompanha o faturamento e o pagamento por ``transition_measurement``. A operação é de quem
    gere o contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    milestone, contract = _milestone_and_contract(session, scope=scope, milestone_id=milestone_id)
    validation.check_milestone_transition(milestone.situation, target)
    recording.update(
        session,
        user_id=user.id,
        record=milestone,
        changes={"situation": target},
        version=(form or {}).get(validation.FIELD_VERSION),
    )
    return _milestone_view(_current_value_cents(session, contract=contract), contract, milestone)


def create_claim(
    session: Session,
    *,
    user: User,
    scope: Scope,
    contract_id: int,
    form: Mapping[str, str | None],
) -> ClaimView:
    """Registra um claim Notificado, com o código sequencial do projeto (``CLM-...-0001``).

    Direção, tipo e causa vêm das listas do contrato e o valor/dias pleiteados seguem o tipo
    (Prazo pede dias, Custo pede valor e Prazo e custo pede os dois). O risco de origem, quando
    informado, é conferido pela fachada da Riscos no projeto do contrato e gravado em
    ``risco_id`` (ISSUE-067). O alerta de notificação compara a data da notificação com o prazo
    do contrato e viaja na visão. A operação é de quem gere o contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=contract_id)
    parsed = validation.parse_claim_form(form)
    risk_id, risk_code = _claim_risk(session, contract=contract, code=parsed.risk_code)
    prefix = _code_prefix(session, contract=contract, kind=CLAIM_CODE_KIND)
    record = recording.create(
        session,
        user_id=user.id,
        record=ContractClaim(
            contract_id=contract.id,
            risk_id=risk_id,
            code=_next_code(
                session.scalars(
                    select(ContractClaim.code).where(ContractClaim.code.startswith(prefix))
                ).all(),
                prefix=prefix,
            ),
            direction=parsed.direction,
            kind=parsed.kind,
            cause=parsed.cause,
            description=parsed.description,
            clause=parsed.clause,
            event_date=parsed.event_date,
            notification_date=parsed.notification_date,
            claimed_cents=parsed.claimed_cents,
            claimed_days=parsed.claimed_days,
            situation=calculations.CLAIM_NOTIFIED,
        ),
    )
    return _claim_view(
        contract,
        record,
        change_codes={},
        risk_codes={risk_id: risk_code} if risk_id and risk_code else {},
    )


def _claim_risk(session: Session, *, contract: Contract, code: str) -> tuple[int | None, str]:
    """O risco do claim: opcional, do projeto do contrato, resolvido pela fachada da Riscos (D9)."""
    from src.modulos.riscos import service as riscos

    wanted = (code or "").strip()
    if not wanted:
        return None, ""
    risk = riscos.risk_by_code(session, code=wanted)
    if risk is None or risk.project_id != contract.project_id:
        raise InvalidDataError({validation.FIELD_CLAIM_RISK: validation.CLAIM_RISK_NOT_FOUND})
    return risk.id, risk.code


def update_claim(
    session: Session,
    *,
    user: User,
    scope: Scope,
    claim_id: int,
    form: Mapping[str, str | None],
    reference_date: date,
) -> ClaimView:
    """Atualiza um claim no fluxo, com o parecer e o reconhecido do acordo.

    A situação atual só admite a próxima do fluxo e o parecer é obrigatório; o reconhecido só
    entra no Acordado, que também abre a SM na Governança pela fachada dela, na mesma
    transação, e grava o vínculo em ``mudanca_id``. No Rejeitado o reconhecido zera e no
    Encerrado entra a data de referência, como o protótipo faz. A operação é de quem gere o
    contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    claim, contract = _claim_and_contract(session, scope=scope, claim_id=claim_id)
    parsed = validation.parse_claim_update_form(form, claimed_cents=claim.claimed_cents)
    validation.check_claim_transition(claim.situation, parsed.target)
    changes: dict[str, Any] = {"situation": parsed.target}
    if parsed.target == calculations.CLAIM_AGREED:
        changes["recognized_cents"] = parsed.recognized_cents
        changes["recognized_days"] = parsed.recognized_days
        changes["change_id"] = _create_claim_change(
            session,
            user=user,
            contract=contract,
            claim=claim,
            statement=parsed.statement,
            reference_date=reference_date,
        )
    elif parsed.target == calculations.CLAIM_REJECTED:
        changes["recognized_cents"] = 0
        changes["recognized_days"] = 0
    elif parsed.target == calculations.CLAIM_CLOSED:
        changes["closed_on"] = reference_date
    recording.update(
        session,
        user_id=user.id,
        record=claim,
        changes=changes,
        version=form.get(validation.FIELD_VERSION),
    )
    return _claim_view(
        contract,
        claim,
        change_codes=_change_codes(session, [claim.change_id]),
        risk_codes=_risk_codes(session, [claim.risk_id]),
    )


def decide_claim(
    session: Session,
    *,
    user: User,
    scope: Scope,
    claim_id: int,
    form: Mapping[str, str | None],
    reference_date: date,
) -> ClaimView:
    """A decisão de mérito do claim: Acordado (com a SM) ou Rejeitado.

    É a porta restrita de ``update_claim`` para a decisão; a negociação e as demais transições
    usam ``update_claim``. A operação é de quem gere o contrato.
    """
    target = (form.get(validation.FIELD_CLAIM_SITUATION) or "").strip()
    if target not in CLAIM_DECISIONS:
        raise InvalidDataError({validation.FIELD_CLAIM_SITUATION: CLAIM_DECISION_MESSAGE})
    return update_claim(
        session,
        user=user,
        scope=scope,
        claim_id=claim_id,
        form=form,
        reference_date=reference_date,
    )


def create_extension(
    session: Session,
    *,
    user: User,
    scope: Scope,
    contract_id: int,
    form: Mapping[str, str | None],
    reference_date: date,
) -> ExtensionView:
    """Registra uma EOT Solicitada, com o claim de origem opcional do contrato.

    O evento causador, os dias solicitados, o marco contratual afetado e o método de análise de
    atraso são obrigatórios; o claim de origem, quando informado, precisa ser do contrato. A
    data da solicitação é a data de referência, como o protótipo. A operação é de quem gere o
    contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=contract_id)
    parsed = validation.parse_extension_form(form)
    _check_extension_claim(session, contract=contract, claim_id=parsed.claim_id)
    prefix = _code_prefix(session, contract=contract, kind=EXTENSION_CODE_KIND)
    record = recording.create(
        session,
        user_id=user.id,
        record=ContractTimeExtension(
            contract_id=contract.id,
            claim_id=parsed.claim_id,
            code=_next_code(
                session.scalars(
                    select(ContractTimeExtension.code).where(
                        ContractTimeExtension.code.startswith(prefix)
                    )
                ).all(),
                prefix=prefix,
            ),
            event=parsed.event,
            requested_days=parsed.requested_days,
            method=parsed.method,
            affected_milestone=parsed.affected_milestone,
            requested_on=reference_date,
            situation=calculations.EXTENSION_REQUESTED,
        ),
    )
    return _extension_view(
        record,
        claim_codes=_claim_codes(session, [parsed.claim_id]),
        change_codes={},
    )


def decide_extension(
    session: Session,
    *,
    user: User,
    scope: Scope,
    extension_id: int,
    form: Mapping[str, str | None],
    reference_date: date,
) -> ExtensionView:
    """Decide a EOT; a concessão prorroga o término vigente e cria a SM do cronograma.

    Concedida integral ou parcialmente exige os dias concedidos e a classificação, prorroga
    ``termino_vigente`` por eles e abre a SM na Governança pela fachada dela, na mesma
    transação, gravando o vínculo em ``mudanca_id``; a Negada encerra a análise sem efeito no
    contrato. A situação atual só admite a decisão do fluxo, e a operação é de quem gere o
    contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    extension, contract = _extension_and_contract(session, scope=scope, extension_id=extension_id)
    parsed = validation.parse_extension_decision_form(form, requested_days=extension.requested_days)
    validation.check_extension_transition(extension.situation, parsed.target)
    granted = parsed.target in (
        calculations.EXTENSION_GRANTED,
        calculations.EXTENSION_PARTIALLY_GRANTED,
    )
    changes: dict[str, Any] = {
        "situation": parsed.target,
        "decided_on": reference_date,
        "granted_days": parsed.granted_days,
        "classification": parsed.classification or None,
    }
    if granted:
        new_end = calculations.extension_new_end_date(contract.current_end, parsed.granted_days)
        recording.update(
            session,
            user_id=user.id,
            record=contract,
            changes={"current_end": new_end},
            version=contract.version,
        )
        changes["change_id"] = _create_extension_change(
            session,
            user=user,
            contract=contract,
            extension=extension,
            target=parsed.target,
            statement=parsed.statement,
            reference_date=reference_date,
        )
    recording.update(
        session,
        user_id=user.id,
        record=extension,
        changes=changes,
        version=form.get(validation.FIELD_VERSION),
    )
    return _extension_view(
        extension,
        claim_codes=_claim_codes(session, [extension.claim_id]),
        change_codes=_change_codes(session, [extension.change_id]),
    )


def _create_claim_change(
    session: Session,
    *,
    user: User,
    contract: Contract,
    claim: ContractClaim,
    statement: str,
    reference_date: date,
) -> int:
    """A SM do claim acordado, pela fachada da Governança, na transação do chamador (D9)."""
    from src.modulos.governanca import service as governanca

    form: Mapping[str, str] = {
        "titulo": f"Claim {claim.code} acordado",
        "tipo": CLAIM_SM_KIND[claim.kind],
        "origem": _claim_sm_origin(claim.direction),
        "prioridade": CHANGE_PRIORITY_NORMAL,
        "data_solicitacao": reference_date.isoformat(),
        "descricao": f"Claim {claim.code}: {claim.description} Parecer: {statement}",
    }
    created = governanca.create_change(
        session,
        user=user,
        scope=Scope(project_id=contract.project_id, source="url"),
        form=form,
        reference_date=reference_date,
    )
    return created.id


def _create_extension_change(
    session: Session,
    *,
    user: User,
    contract: Contract,
    extension: ContractTimeExtension,
    target: str,
    statement: str,
    reference_date: date,
) -> int:
    """A SM da EOT concedida para a linha de base do cronograma, pela fachada da Governança."""
    from src.modulos.governanca import service as governanca

    form: Mapping[str, str] = {
        "titulo": f"EOT {extension.code}: {target}",
        "tipo": "Prazo",
        "origem": _extension_sm_origin(session, extension=extension),
        "prioridade": CHANGE_PRIORITY_NORMAL,
        "data_solicitacao": reference_date.isoformat(),
        "descricao": f"EOT {extension.code}: {extension.event} Parecer: {statement}",
    }
    created = governanca.create_change(
        session,
        user=user,
        scope=Scope(project_id=contract.project_id, source="url"),
        form=form,
        reference_date=reference_date,
    )
    return created.id


def _claim_sm_origin(direction: str) -> str:
    if direction == validation.CLAIM_DIRECTION_CONTRACTOR:
        return CLAIM_SM_ORIGIN_CONTRACTOR
    return CLAIM_SM_ORIGIN_CLIENT


def _extension_sm_origin(session: Session, *, extension: ContractTimeExtension) -> str:
    if extension.claim_id is None:
        return CLAIM_SM_ORIGIN_INTERNAL
    claim = session.get(ContractClaim, extension.claim_id)
    return _claim_sm_origin(claim.direction) if claim is not None else CLAIM_SM_ORIGIN_INTERNAL


def _check_extension_claim(session: Session, *, contract: Contract, claim_id: int | None) -> None:
    """O claim de origem da EOT, quando informado, precisa existir e ser do contrato."""
    if claim_id is None:
        return
    claim = session.get(ContractClaim, claim_id)
    if claim is None or claim.contract_id != contract.id:
        raise InvalidDataError({validation.FIELD_EXTENSION_CLAIM: EXTENSION_CLAIM_MESSAGE})


def _milestone_and_contract(
    session: Session, *, scope: Scope, milestone_id: int
) -> tuple[ContractPaymentMilestone, Contract]:
    milestone = session.get(ContractPaymentMilestone, milestone_id)
    if milestone is None:
        raise InvalidDataError(MILESTONE_NOT_FOUND_MESSAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=milestone.contract_id)
    return milestone, contract


def _claim_and_contract(
    session: Session, *, scope: Scope, claim_id: int
) -> tuple[ContractClaim, Contract]:
    claim = session.get(ContractClaim, claim_id)
    if claim is None:
        raise InvalidDataError(CLAIM_NOT_FOUND_MESSAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=claim.contract_id)
    return claim, contract


def _extension_and_contract(
    session: Session, *, scope: Scope, extension_id: int
) -> tuple[ContractTimeExtension, Contract]:
    extension = session.get(ContractTimeExtension, extension_id)
    if extension is None:
        raise InvalidDataError(EXTENSION_NOT_FOUND_MESSAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=extension.contract_id)
    return extension, contract


def _current_value_cents(session: Session, *, contract: Contract) -> int:
    """Valor atual do contrato na leitura: original mais os aditivos aprovados."""
    addenda = _addendum_lines(_addendum_rows(session, contract_id=contract.id))
    return calculations.contract_current_value_cents(contract.original_value_cents, addenda)


def _code_prefix(session: Session, *, contract: Contract, kind: str) -> str:
    """O prefixo do código do projeto (``CLM-TN-2026-``), como o protótipo o monta."""
    project = configuracoes.find_project(session, contract.project_id)
    pattern = (project.ata_pattern if project is not None else None) or DEFAULT_CODE_PATTERN
    return f"{kind}-{pattern}-"


def _next_code(codes: Sequence[str], *, prefix: str) -> str:
    """O próximo código sequencial do prefixo: o maior número existente mais um, com 4 dígitos."""
    numbers = [
        int(code[len(prefix) :])
        for code in codes
        if code.startswith(prefix) and code[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1:04d}"


def _contract_or_refuse(session: Session, contract_id: int) -> Contract:
    contract = session.get(Contract, contract_id)
    if contract is None:
        raise InvalidDataError(CONTRACT_NOT_FOUND_MESSAGE)
    return contract


def _contract_in_scope(session: Session, *, scope: Scope, contract_id: int) -> Contract:
    project_id = scope.require_project()
    contract = _contract_or_refuse(session, contract_id)
    if contract.project_id != project_id:
        raise AccessDeniedError(CONTRACT_OTHER_PROJECT_MESSAGE)
    return contract


def _measurement_rows(session: Session, *, contract_id: int) -> list[ContractMeasurement]:
    statement = (
        select(ContractMeasurement)
        .where(ContractMeasurement.contract_id == contract_id)
        .order_by(ContractMeasurement.id.desc())
    )
    return list(session.scalars(statement))


def _addendum_rows(session: Session, *, contract_id: int) -> list[ContractAddendum]:
    statement = (
        select(ContractAddendum)
        .where(ContractAddendum.contract_id == contract_id)
        .order_by(ContractAddendum.id.desc())
    )
    return list(session.scalars(statement))


def _measurement_lines(
    rows: Sequence[ContractMeasurement],
) -> tuple[calculations.ContractMeasurementLine, ...]:
    return tuple(
        calculations.ContractMeasurementLine(value_cents=row.gross_cents, situation=row.situation)
        for row in rows
    )


def _addendum_lines(
    rows: Sequence[ContractAddendum],
) -> tuple[calculations.ContractAddendumLine, ...]:
    return tuple(
        calculations.ContractAddendumLine(value_cents=row.value_cents, days=row.days)
        for row in rows
    )


def _measurement_view(contract: Contract, row: ContractMeasurement) -> MeasurementView:
    retention = _retention_cents(row.gross_cents, contract.retention_pct)
    return MeasurementView(
        id=row.id,
        number=row.number,
        period=row.period,
        gross_cents=row.gross_cents,
        retention_cents=retention,
        net_cents=row.gross_cents - retention,
        milestone_id=row.milestone_id,
        situation=row.situation,
        return_reason=row.return_reason or "",
        version=row.version,
    )


def _addendum_view(row: ContractAddendum, *, change_codes: Mapping[int, str]) -> AddendumView:
    return AddendumView(
        id=row.id,
        number=row.number,
        signed_on=row.signed_on,
        value_cents=row.value_cents,
        days=row.days,
        reason=row.reason,
        change_id=row.change_id,
        change_code=change_codes.get(row.change_id or 0, ""),
        claim_id=row.claim_id,
    )


def _milestone_rows(session: Session, *, contract_id: int) -> list[ContractPaymentMilestone]:
    statement = (
        select(ContractPaymentMilestone)
        .where(ContractPaymentMilestone.contract_id == contract_id)
        .order_by(ContractPaymentMilestone.id)
    )
    return list(session.scalars(statement))


def _claim_rows(session: Session, *, contract_id: int) -> list[ContractClaim]:
    statement = (
        select(ContractClaim)
        .where(ContractClaim.contract_id == contract_id)
        .order_by(ContractClaim.id.desc())
    )
    return list(session.scalars(statement))


def _extension_rows(session: Session, *, contract_id: int) -> list[ContractTimeExtension]:
    statement = (
        select(ContractTimeExtension)
        .where(ContractTimeExtension.contract_id == contract_id)
        .order_by(ContractTimeExtension.id.desc())
    )
    return list(session.scalars(statement))


def _milestone_view(
    current_value_cents: int, contract: Contract, row: ContractPaymentMilestone
) -> MilestoneView:
    value = calculations.milestone_value_cents(current_value_cents, row.pct)
    return MilestoneView(
        id=row.id,
        number=row.number,
        description=row.description,
        criteria=row.acceptance_criteria,
        pct=row.pct,
        value_cents=value,
        retention_cents=calculations.milestone_retention_cents(value, contract.retention_pct),
        expected_on=row.expected_on,
        completed_on=row.completed_on,
        situation=row.situation,
        attachment_id=row.attachment_id,
        has_evidence=row.attachment_id is not None,
        version=row.version,
    )


def _claim_view(
    contract: Contract,
    row: ContractClaim,
    *,
    change_codes: Mapping[int, str],
    risk_codes: Mapping[int, str] | None = None,
) -> ClaimView:
    deadline = calculations.claim_notification_deadline(row.event_date, contract.claim_notice_days)
    return ClaimView(
        id=row.id,
        code=row.code,
        direction=row.direction,
        kind=row.kind,
        cause=row.cause,
        description=row.description,
        clause=row.clause or "",
        event_date=row.event_date,
        notification_date=row.notification_date,
        claimed_cents=row.claimed_cents,
        claimed_days=row.claimed_days,
        recognized_cents=row.recognized_cents,
        recognized_days=row.recognized_days,
        situation=row.situation,
        closed_on=row.closed_on,
        change_id=row.change_id,
        change_code=change_codes.get(row.change_id or 0, ""),
        notification_days=(row.notification_date - row.event_date).days,
        notification_late=calculations.claim_notification_late(row.notification_date, deadline),
        risk_code=(risk_codes or {}).get(row.risk_id or 0, ""),
        version=row.version,
    )


def _risk_codes(session: Session, risk_ids: Sequence[int | None]) -> dict[int, str]:
    """O código de cada risco pelo id, pela fachada da Riscos (D9)."""
    from src.modulos.riscos import service as riscos

    labels = riscos.risk_labels(session, risk_ids=[risk_id for risk_id in risk_ids if risk_id])
    return {risk_id: label.code for risk_id, label in labels.items()}


@dataclass(frozen=True)
class ClaimOfRisk:
    """Um claim que aponta o risco, como a ficha do risco o mostra (D9)."""

    code: str
    description: str
    situation: str


def claims_of_risk(session: Session, *, risk_id: int) -> tuple[ClaimOfRisk, ...]:
    """Os claims vinculados ao risco, lidos na tabela do próprio Financeiro (D9)."""
    statement = (
        select(ContractClaim).where(ContractClaim.risk_id == risk_id).order_by(ContractClaim.code)
    )
    return tuple(
        ClaimOfRisk(code=row.code, description=row.description, situation=row.situation)
        for row in session.scalars(statement)
    )


def _extension_view(
    row: ContractTimeExtension,
    *,
    claim_codes: Mapping[int, str],
    change_codes: Mapping[int, str],
) -> ExtensionView:
    return ExtensionView(
        id=row.id,
        code=row.code,
        claim_id=row.claim_id,
        claim_code=claim_codes.get(row.claim_id or 0, ""),
        event=row.event,
        requested_days=row.requested_days,
        granted_days=row.granted_days,
        classification=row.classification or "",
        method=row.method,
        affected_milestone=row.affected_milestone,
        requested_on=row.requested_on,
        decided_on=row.decided_on,
        situation=row.situation,
        change_id=row.change_id,
        change_code=change_codes.get(row.change_id or 0, ""),
        is_open=row.situation
        in (calculations.EXTENSION_REQUESTED, calculations.EXTENSION_UNDER_REVIEW),
        version=row.version,
    )


def _claim_codes(session: Session, claim_ids: Sequence[int | None]) -> dict[int, str]:
    wanted = [claim_id for claim_id in claim_ids if claim_id is not None]
    if not wanted:
        return {}
    statement = select(ContractClaim).where(ContractClaim.id.in_(wanted))
    return {row.id: row.code for row in session.scalars(statement)}


def _retention_cents(gross_cents: int, retention_pct: int) -> int:
    """Retenção da medição: o bruto pela retenção do contrato, em centavos, meio centavo para cima."""
    return int(
        (Decimal(gross_cents * retention_pct) / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    )


def _under_review_cents(rows: Sequence[ContractMeasurement]) -> int:
    return sum(
        row.gross_cents for row in rows if row.situation == calculations.SITUATION_UNDER_REVIEW
    )


def _available_to_measure_cents(session: Session, *, contract: Contract) -> int:
    measurements = _measurement_rows(session, contract_id=contract.id)
    addenda = _addendum_lines(_addendum_rows(session, contract_id=contract.id))
    current = calculations.contract_current_value_cents(contract.original_value_cents, addenda)
    measured = calculations.contract_measured_cents(_measurement_lines(measurements))
    balance = calculations.contract_balance_to_invoice_cents(current, measured)
    return balance - _under_review_cents(measurements)


def _next_measurement_number(session: Session, *, contract_id: int) -> str:
    count = session.scalar(
        select(func.count())
        .select_from(ContractMeasurement)
        .where(ContractMeasurement.contract_id == contract_id)
    )
    return f"BM-{(count or 0) + 1:02d}"


def _next_addendum_number(session: Session, *, contract_id: int) -> str:
    count = session.scalar(
        select(func.count())
        .select_from(ContractAddendum)
        .where(ContractAddendum.contract_id == contract_id)
    )
    return f"AD-{(count or 0) + 1:02d}"


def _next_milestone_number(session: Session, *, contract_id: int) -> str:
    count = session.scalar(
        select(func.count())
        .select_from(ContractPaymentMilestone)
        .where(ContractPaymentMilestone.contract_id == contract_id)
    )
    return f"M{(count or 0) + 1}"


def _apply_measurement_to_milestone(
    session: Session, *, user: User, measurement: ContractMeasurement, target: str
) -> None:
    """A medição de marco acompanha o faturamento e o pagamento, como no protótipo.

    A medição Faturada leva o marco a Faturado e a Paga leva a Pago; sem marco vinculado ou
    quando ele já está na situação de destino, nada muda.
    """
    if measurement.milestone_id is None:
        return
    milestone = session.get(ContractPaymentMilestone, measurement.milestone_id)
    if milestone is None:
        return
    wanted = (
        calculations.MILESTONE_INVOICED
        if target == calculations.SITUATION_INVOICED
        else calculations.MILESTONE_PAID
    )
    if milestone.situation == wanted:
        return
    recording.update(
        session,
        user_id=user.id,
        record=milestone,
        changes={"situation": wanted},
        version=str(milestone.version),
    )


def _apply_measurement_to_eac(
    session: Session, *, user: User, contract: Contract, measurement: ContractMeasurement
) -> None:
    """Soma o bruto aprovado ao realizado do item da EAC do contrato, no mês do período."""
    if contract.eac_item_id is None:
        return
    month = measurement.period.replace(day=1)
    statement = select(ErpCost).where(
        ErpCost.item_id == contract.eac_item_id, ErpCost.month == month
    )
    fact = session.scalars(statement).one_or_none()
    if fact is None:
        recording.create(
            session,
            user_id=user.id,
            record=ErpCost(
                project_id=contract.project_id,
                item_id=contract.eac_item_id,
                imported_by_id=user.person_id,
                month=month,
                actual_cents=measurement.gross_cents,
                imported_at=calendario.now(),
            ),
        )
        return
    before = audit.snapshot(fact)
    fact.actual_cents = (fact.actual_cents or 0) + measurement.gross_cents
    fact.imported_by_id = user.person_id
    fact.imported_at = calendario.now()
    session.flush()
    audit.changed(session, user_id=user.id, entity=fact.__tablename__, record=fact, before=before)


def _check_addendum_change(session: Session, *, contract: Contract, change_id: int | None) -> None:
    """A SM do aditivo precisa existir, ser do projeto do contrato e estar aprovada."""
    if change_id is None:
        return
    from src.modulos.governanca import service as governanca

    source = governanca.change_eac_source(session, change_id=change_id)
    if source is None or source.project_id != contract.project_id or not source.approved:
        raise InvalidDataError({validation.FIELD_ADDENDUM_CHANGE: ADDENDUM_SM_MESSAGE})


def _change_codes(session: Session, change_ids: Sequence[int | None]) -> dict[int, str]:
    """O código de cada SM por id, lido da fachada da Governança (D9)."""
    wanted = [change_id for change_id in change_ids if change_id is not None]
    if not wanted:
        return {}
    from src.modulos.governanca import service as governanca

    return governanca.change_codes(session, change_ids=wanted)


@dataclass(frozen=True)
class ChangeOption:
    """Uma SM aprovada do projeto como o select de origem do aditivo a lista."""

    id: int
    code: str
    title: str


def change_options(session: Session, *, project_id: int) -> tuple[ChangeOption, ...]:
    """As SM aprovadas do projeto, para o select do aditivo, pela fachada da Governança (D9)."""
    from src.modulos.governanca import service as governanca

    return tuple(
        ChangeOption(id=option.id, code=option.code, title=option.title)
        for option in governanca.approved_changes(session, project_id=project_id)
    )


def contract_by_number(session: Session, *, user: User, number: str) -> ContractView:
    """A ficha do contrato pelo número, como a tela de detalhe a abre (ISSUE-032).

    Número vazio ou desconhecido é recusado com a mensagem da ficha; a leitura não é filtrada
    pelo escopo — quem alcança o módulo lê o contrato, como no protótipo —, mas a escrita
    continua exigindo o projeto do contrato.
    """
    wanted = number.strip()
    contract_id = (
        session.scalar(select(Contract.id).where(Contract.number == wanted)) if wanted else None
    )
    if contract_id is None:
        raise InvalidDataError(CONTRACT_NOT_FOUND_MESSAGE)
    return contract_detail(session, user=user, contract_id=contract_id)


# ── O contrato e o compromisso da adjudicação do 04 (ISSUE-060, D9) ──────────────────────────


PURCHASE_CONTRACT_SITUATION = "Em execução"
PURCHASE_CONTRACT_PREFIX = "CT"
CLAIMS_GROUP = "claims"
CLAIM_NOTICE_KEY = "prazoNotificacaoPadraoDias"
DEFAULT_CLAIM_NOTICE_DAYS = 30
PROJECT_MANAGER_MISSING_MESSAGE = "O projeto não tem gerente definido para o contrato."
FIELD_CONTRACT_FISCAL = "fiscal"
FISCAL_UNKNOWN_MESSAGE = "O fiscal informado não está no cadastro."


@dataclass(frozen=True)
class CreatedContract:
    """O contrato que a adjudicação de um serviço/EPC cria: identidade e número."""

    id: int
    number: str


def create_purchase_contract(
    session: Session,
    *,
    user: User,
    project_id: int,
    company_id: int,
    eac_item_id: int | None,
    purchase_package_id: int,
    object: str,
    modality: str,
    value_cents: int,
    emission: date,
    start: date,
    end: date,
    fiscal_id: int | None,
    retention_pct: int,
) -> CreatedContract:
    """Cria o contrato de um processo de serviço/EPC adjudicado, na transação do chamador (D9).

    O gestor é o gerente do projeto e o prazo de notificação do claim vem do grupo ``claims`` em
    vigor, como o protótipo; o número segue a série global de três dígitos (``CT-2026-001``). A
    fachada recusa (422) um projeto sem gerente ou um fiscal fora do cadastro; o contrato nasce
    Em execução, com a trilha da plataforma.
    """
    rbac.require(user, Permission.WRITE)
    project = next(
        (item for item in configuracoes.list_projects(session) if item.id == project_id), None
    )
    if project is None:
        raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)
    if project.manager_id is None:
        raise InvalidDataError(PROJECT_MANAGER_MISSING_MESSAGE)
    if fiscal_id is None or fiscal_id not in configuracoes.person_names(session, {fiscal_id}):
        raise InvalidDataError({FIELD_CONTRACT_FISCAL: FISCAL_UNKNOWN_MESSAGE})
    values = configuracoes.current_group(session, group=CLAIMS_GROUP, reference_date=emission)
    notice = values.get(CLAIM_NOTICE_KEY, DEFAULT_CLAIM_NOTICE_DAYS)
    if isinstance(notice, bool) or not isinstance(notice, int) or notice < 0:
        notice = DEFAULT_CLAIM_NOTICE_DAYS
    number = _next_contract_number(session, reference_date=emission)
    record = recording.create(
        session,
        user_id=user.id,
        record=Contract(
            project_id=project_id,
            company_id=company_id,
            eac_item_id=eac_item_id,
            purchase_package_id=purchase_package_id,
            manager_id=project.manager_id,
            fiscal_id=fiscal_id,
            number=number,
            object=object,
            modality=modality,
            original_value_cents=value_cents,
            start=start,
            original_end=end,
            current_end=end,
            retention_pct=retention_pct,
            claim_notice_days=notice,
            situation=PURCHASE_CONTRACT_SITUATION,
        ),
    )
    return CreatedContract(id=record.id, number=record.number)


def _next_contract_number(session: Session, *, reference_date: date) -> str:
    """O próximo número da série global de contratos do ano, como o protótipo numerava."""
    numbers = list(session.scalars(select(Contract.number)))
    return numbering.next_series_number(
        numbers, prefix=PURCHASE_CONTRACT_PREFIX, year=reference_date.year
    )


def contract_number_by_package(session: Session, *, package_id: int) -> str | None:
    """O número do contrato nascido do pacote do plano, para a ficha do processo (D9)."""
    return session.scalar(select(Contract.number).where(Contract.purchase_package_id == package_id))


@dataclass(frozen=True)
class PurchaseContractRef:
    """O contrato nascido de um pacote do plano: número e valor original (D9, ISSUE-063)."""

    number: str
    value_cents: int


def purchase_contracts_by_package(
    session: Session, package_ids: Collection[int]
) -> dict[int, PurchaseContractRef]:
    """Os contratos nascidos dos pacotes informados, por pacote: número e valor original.

    Leitura aditiva para o painel de suprimentos: o contrato é o documento emitido do serviço/EPC
    e o seu valor é o adjudicado do pacote. O primeiro contrato de um pacote vence, como o
    ``pedido`` do pacote (a emissão cria um só).
    """
    if not package_ids:
        return {}
    statement = select(Contract).where(Contract.purchase_package_id.in_(package_ids))
    contracts: dict[int, PurchaseContractRef] = {}
    for contract in session.scalars(statement):
        if contract.purchase_package_id is None:
            continue
        contracts.setdefault(
            contract.purchase_package_id,
            PurchaseContractRef(number=contract.number, value_cents=contract.original_value_cents),
        )
    return contracts


def commit_purchase_cost(
    session: Session,
    *,
    user: User,
    project_id: int,
    item_id: int,
    on: date,
    value_cents: int,
) -> None:
    """Compromete o valor do pedido/contrato no item da EAC, no mês da emissão (D9).

    O comprometido é um fato de ``custo_erp`` por item e mês, como o realizado da medição: a
    linha do mês é atualizada, nunca duplicada. Um item que não é de custo (nível 3) do projeto
    não recebe o fato, como o protótipo deixava de somar.
    """
    rbac.require(user, Permission.WRITE)
    item = session.get(EacItem, item_id)
    if item is None or item.project_id != project_id or item.level < calculations.LEAF_LEVEL:
        return
    month = on.replace(day=1)
    statement = select(ErpCost).where(ErpCost.item_id == item_id, ErpCost.month == month)
    fact = session.scalars(statement).one_or_none()
    if fact is None:
        recording.create(
            session,
            user_id=user.id,
            record=ErpCost(
                project_id=project_id,
                item_id=item_id,
                imported_by_id=user.person_id,
                month=month,
                committed_cents=value_cents,
                imported_at=calendario.now(),
            ),
        )
        return
    before = audit.snapshot(fact)
    fact.committed_cents = (fact.committed_cents or 0) + value_cents
    fact.imported_by_id = user.person_id
    fact.imported_at = calendario.now()
    session.flush()
    audit.changed(session, user_id=user.id, entity=fact.__tablename__, record=fact, before=before)


# ── Avaliação de desempenho da contratada (ISSUE-034) ────────────────────


EVALUATION_GROUP = "avaliacaoContratada"
EVALUATION_ATTACHMENT_TABLE = "contrato_avaliacao"
EVALUATION_ACTION_ORIGIN = "Contrato"
EVALUATION_ACTION_GROUP = "Avaliação da contratada"
EVALUATION_PLAN_DAYS = 15
EVALUATION_EVIDENCE_FIELD = "evidencias"
EVALUATION_PARAMETERS_MISSING = "Os parâmetros da avaliação de contratada não estão configurados."
EVALUATION_EVIDENCE_REQUIRED = "A nota {limit} ou menor em algum critério exige anexo de evidência."
EVALUATION_DUPLICATE_MESSAGE = "Já existe avaliação {kind} neste período."
EVALUATION_LESSON_PHASE = "Encerramento"
EVALUATION_LESSON_AREA = "Aquisições"
EVALUATION_LESSON_REPEAT = "A repetir"
EVALUATION_LESSON_AVOID = "A evitar"


@dataclass(frozen=True)
class EvaluationCriterionSpec:
    """Um critério dos parâmetros vigentes: o id, o nome e o peso que ele grava na avaliação."""

    id: str
    name: str
    weight: int


@dataclass(frozen=True)
class EvaluationSettings:
    """O grupo da avaliação vigente: os critérios, as classes e a nota que exige plano."""

    criteria: tuple[EvaluationCriterionSpec, ...]
    classes: tuple[calculations.EvaluationClass, ...]
    plan_limit: int


@dataclass(frozen=True)
class EvaluationCriterionView:
    """O peso e a nota de um critério, congelados na avaliação (D5b)."""

    criterion: str
    weight: int
    note: int


@dataclass(frozen=True)
class EvaluationView:
    """Uma avaliação da ficha: período, tipo, avaliador, nota, classe, plano e evidência."""

    id: int
    period: date
    kind: str
    evaluator: str
    comment: str
    score: int | None
    score_class: str
    class_description: str
    requires_plan: bool
    criteria: tuple[EvaluationCriterionView, ...]
    has_evidence: bool
    version: int = 1


# ── Ligação com o cadastro de fornecedores (D9, ISSUE-057) ───────────────


@dataclass(frozen=True)
class FinalEvaluation:
    """A avaliação final de um contrato, como o módulo que a escuta a recebe (D9, ISSUE-057)."""

    company_id: int
    contract_number: str
    period: date
    score: int
    score_class: str


FinalEvaluationListener = Callable[[Session, User, "FinalEvaluation", date], None]
_final_evaluation_listeners: list[FinalEvaluationListener] = []


def register_final_evaluation_listener(listener: FinalEvaluationListener) -> None:
    """Diz quem atualiza a qualificação do fornecedor quando a avaliação é final (D9, ISSUE-057)."""
    if listener not in _final_evaluation_listeners:
        _final_evaluation_listeners.append(listener)


def _notify_final_evaluation(
    session: Session, user: User, evaluation: FinalEvaluation, reference_date: date
) -> None:
    """Avisa cada ouvinte registrado, dentro da transação da avaliação (D9)."""
    for listener in _final_evaluation_listeners:
        listener(session, user, evaluation, reference_date)


def create_evaluation(
    session: Session,
    *,
    user: User,
    scope: Scope,
    contract_id: int,
    form: Mapping[str, str | None],
    reference_date: date,
    file_name: str | None = None,
    content: bytes = b"",
    storage: FileStorage | None = None,
) -> EvaluationView:
    """Registra a avaliação de desempenho da contratada, com os pesos congelados dos parâmetros.

    A versão vigente do grupo ``avaliacaoContratada`` dá os critérios, as classes e a nota que
    exige plano; cada critério entra na avaliação com o seu peso e a nota, então mudar o
    parâmetro depois não muda a avaliação gravada (D5b). A nota 1 ou 2 em algum critério exige
    um anexo de evidência e abre a ação de plano de melhoria na Central, com origem Contrato e
    vínculo no número do contrato; a avaliação final abre a lição em Rascunho pela fachada de
    Lições, com origem no contrato. A ação e a lição entram na mesma transação da avaliação
    (D9). A operação é de quem gere o contrato.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    contract = _contract_in_scope(session, scope=scope, contract_id=contract_id)
    version = configuracoes.current_version(
        session, group=EVALUATION_GROUP, reference_date=reference_date
    )
    if version is None:
        raise InvalidDataError(EVALUATION_PARAMETERS_MISSING)
    settings = _settings_of(configuracoes.parameter_values(session, version))
    parsed = validation.parse_evaluation_form(
        form, criteria_ids=[criterion.id for criterion in settings.criteria]
    )
    _check_evaluation_duplicate(
        session, contract_id=contract.id, period=parsed.period, kind=parsed.kind
    )
    notes = parsed.notes
    requires_plan = calculations.evaluation_requires_plan(notes, settings.plan_limit)
    if requires_plan and not content:
        raise InvalidDataError(
            {
                EVALUATION_EVIDENCE_FIELD: EVALUATION_EVIDENCE_REQUIRED.format(
                    limit=settings.plan_limit
                )
            }
        )
    record = recording.create(
        session,
        user_id=user.id,
        record=ContractEvaluation(
            contract_id=contract.id,
            evaluator_id=user.person_id,
            parameter_version_id=version.id,
            period=parsed.period,
            kind=parsed.kind,
            comment=parsed.comment or None,
        ),
    )
    criteria = [
        ContractEvaluationCriterion(
            evaluation_id=record.id,
            criterion=spec.id,
            weight=spec.weight,
            note=notes[spec.id],
        )
        for spec in settings.criteria
    ]
    session.add_all(criteria)
    session.flush()
    if content:
        attachments.upload(
            session,
            user=user,
            new=attachments.NewAttachment(
                origin_table=EVALUATION_ATTACHMENT_TABLE,
                origin_record_id=record.id,
                file_name=file_name,
                content=content,
            ),
            reference_date=reference_date,
            storage=storage,
        )
    if requires_plan:
        _create_evaluation_plan_action(
            session,
            user=user,
            contract=contract,
            period=parsed.period,
            weak=_weak_criterion_names(settings, notes),
            reference_date=reference_date,
        )
    if parsed.kind == calculations.EVALUATION_KIND_FINAL:
        _create_evaluation_lesson(
            session,
            user=user,
            contract=contract,
            score=_weighted_score(settings, notes) or 0,
            requires_plan=requires_plan,
            reference_date=reference_date,
        )
    view = _evaluation_view(
        session, record, criteria=criteria, settings=settings, evaluator=user.name
    )
    if parsed.kind == calculations.EVALUATION_KIND_FINAL and view.score is not None:
        _notify_final_evaluation(
            session,
            user,
            FinalEvaluation(
                company_id=contract.company_id,
                contract_number=contract.number,
                period=parsed.period,
                score=view.score,
                score_class=view.score_class,
            ),
            reference_date,
        )
    return view


def _evaluation_rows(session: Session, *, contract_id: int) -> list[ContractEvaluation]:
    statement = (
        select(ContractEvaluation)
        .where(ContractEvaluation.contract_id == contract_id)
        .order_by(ContractEvaluation.period.desc(), ContractEvaluation.id.desc())
    )
    return list(session.scalars(statement))


def _evaluation_criteria_by_evaluation(
    session: Session, evaluation_ids: Sequence[int]
) -> dict[int, list[ContractEvaluationCriterion]]:
    if not evaluation_ids:
        return {}
    statement = (
        select(ContractEvaluationCriterion)
        .where(ContractEvaluationCriterion.evaluation_id.in_(evaluation_ids))
        .order_by(ContractEvaluationCriterion.id)
    )
    grouped: dict[int, list[ContractEvaluationCriterion]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.evaluation_id, []).append(row)
    return grouped


def _evaluation_views(
    session: Session, rows: Sequence[ContractEvaluation]
) -> tuple[EvaluationView, ...]:
    criteria_by_evaluation = _evaluation_criteria_by_evaluation(session, [row.id for row in rows])
    names = configuracoes.person_names(session, [row.evaluator_id for row in rows])
    settings_by_period: dict[date, EvaluationSettings] = {}
    views: list[EvaluationView] = []
    for row in rows:
        settings = settings_by_period.get(row.period)
        if settings is None:
            settings = _evaluation_settings(session, reference_date=row.period)
            settings_by_period[row.period] = settings
        views.append(
            _evaluation_view(
                session,
                row,
                criteria=criteria_by_evaluation.get(row.id, []),
                settings=settings,
                evaluator=names.get(row.evaluator_id, ""),
            )
        )
    return tuple(views)


def _evaluation_view(
    session: Session,
    row: ContractEvaluation,
    *,
    criteria: Sequence[ContractEvaluationCriterion],
    settings: EvaluationSettings,
    evaluator: str,
) -> EvaluationView:
    notes = {criterion.criterion: criterion.note for criterion in criteria}
    weights = {criterion.criterion: criterion.weight for criterion in criteria}
    score = calculations.evaluation_weighted_score(notes, weights)
    chosen = calculations.evaluation_class(score, settings.classes)
    return EvaluationView(
        id=row.id,
        period=row.period,
        kind=row.kind,
        evaluator=evaluator,
        comment=row.comment or "",
        score=score,
        score_class=chosen.name if chosen else "",
        class_description=chosen.description if chosen else "",
        requires_plan=calculations.evaluation_requires_plan(notes, settings.plan_limit),
        criteria=tuple(
            EvaluationCriterionView(criterion=item.criterion, weight=item.weight, note=item.note)
            for item in criteria
        ),
        has_evidence=attachments.has_evidence(
            session, origin_table=EVALUATION_ATTACHMENT_TABLE, origin_record_id=row.id
        ),
        version=row.version,
    )


def _evaluation_facts(
    evaluations: Sequence[EvaluationView],
) -> tuple[calculations.EvaluationFact, ...]:
    """As avaliações como fatos de nota: o período e as notas e pesos congelados dos critérios."""
    return tuple(
        calculations.EvaluationFact(
            period=evaluation.period,
            notes={item.criterion: item.note for item in evaluation.criteria},
            weights={item.criterion: item.weight for item in evaluation.criteria},
        )
        for evaluation in evaluations
    )


def _evaluation_trend(
    evaluations: Sequence[EvaluationView],
) -> tuple[dict[str, int], ...]:
    return calculations.evaluation_trend_points(_evaluation_facts(evaluations))


def _settings_of(values: Mapping[str, Any]) -> EvaluationSettings:
    """O grupo como a fachada o entrega, com o valor inicial de cada parte que faltar."""
    initial = configuracoes.INITIAL_PARAMETERS[EVALUATION_GROUP]
    criteria = values.get("criterios") or initial["criterios"]
    classes = values.get("classes") or initial["classes"]
    limit = values.get("notaExigePlano") or initial["notaExigePlano"]
    return EvaluationSettings(
        criteria=tuple(
            EvaluationCriterionSpec(
                id=str(criterion["id"]),
                name=str(criterion.get("nome") or criterion["id"]),
                weight=int(criterion["peso"]),
            )
            for criterion in criteria
        ),
        classes=tuple(
            calculations.EvaluationClass(
                name=str(item["classe"]),
                minimum=int(item["minimo"]),
                description=str(item.get("descricao", "")),
            )
            for item in classes
        ),
        plan_limit=int(limit),
    )


def _evaluation_settings(session: Session, *, reference_date: date) -> EvaluationSettings:
    """O grupo da avaliação vigente na data; sem versão, os valores iniciais do grupo."""
    values = configuracoes.current_group(
        session, group=EVALUATION_GROUP, reference_date=reference_date
    )
    return _settings_of(values)


def _weighted_score(settings: EvaluationSettings, notes: Mapping[str, int]) -> int | None:
    weights = {criterion.id: criterion.weight for criterion in settings.criteria}
    return calculations.evaluation_weighted_score(notes, weights)


def _weak_criterion_names(
    settings: EvaluationSettings, notes: Mapping[str, int]
) -> tuple[str, ...]:
    return tuple(
        criterion.name
        for criterion in settings.criteria
        if notes.get(criterion.id, 0) <= settings.plan_limit
    )


def _check_evaluation_duplicate(
    session: Session, *, contract_id: int, period: date, kind: str
) -> None:
    found = session.scalar(
        select(ContractEvaluation.id).where(
            ContractEvaluation.contract_id == contract_id,
            ContractEvaluation.period == period,
            ContractEvaluation.kind == kind,
        )
    )
    if found is not None:
        raise InvalidDataError(
            {
                validation.FIELD_EVALUATION_PERIOD: EVALUATION_DUPLICATE_MESSAGE.format(
                    kind=kind.lower()
                )
            }
        )


def _create_evaluation_plan_action(
    session: Session,
    *,
    user: User,
    contract: Contract,
    period: date,
    weak: Sequence[str],
    reference_date: date,
) -> int:
    """A ação de plano de melhoria, pela costura única da Central, na transação do chamador."""
    from src.modulos.central_acoes import service as central_acoes
    from src.modulos.central_acoes.validation import NewAction

    company = configuracoes.list_company_names(session).get(contract.company_id, "")
    created = central_acoes.create_action(
        session,
        user=user,
        new=NewAction(
            project_id=contract.project_id,
            origin=EVALUATION_ACTION_ORIGIN,
            origin_ref=contract.number,
            subject=f"Plano de melhoria da {company}",
            description=(
                f"Notas baixas em {', '.join(weak)} na avaliação de {_period_text(period)}."
            ),
            requester_id=user.person_id,
            responsible_id=contract.manager_id,
            planned_date=reference_date + timedelta(days=EVALUATION_PLAN_DAYS),
            group=EVALUATION_ACTION_GROUP,
        ),
        reference_date=reference_date,
    )
    return created.id


def _create_evaluation_lesson(
    session: Session,
    *,
    user: User,
    contract: Contract,
    score: int,
    requires_plan: bool,
    reference_date: date,
) -> int:
    """A lição em Rascunho da avaliação final, pela fachada de Lições, na transação do chamador."""
    from src.modulos.governanca import lessons_models as lessons
    from src.modulos.governanca import lessons_service
    from src.modulos.governanca.lessons_validation import DraftInput

    company = configuracoes.list_company_names(session).get(contract.company_id, "")
    created = lessons_service.create_draft_lesson(
        session,
        user=user,
        project_id=contract.project_id,
        draft=DraftInput(
            title=f"Avaliação final do contrato {contract.number}",
            kind=EVALUATION_LESSON_AVOID if requires_plan else EVALUATION_LESSON_REPEAT,
            phase=EVALUATION_LESSON_PHASE,
            area=EVALUATION_LESSON_AREA,
            origin=lessons.ORIGIN_CONTRACT,
            origin_ref=contract.number,
            what_happened=(
                f"Avaliação final da contratada {company} no contrato {contract.number}: "
                f"nota {score}."
            ),
            cause=f"Desempenho da contratada no encerramento do contrato {contract.number}.",
            recommendation=(
                "Considerar o resultado da avaliação de desempenho na qualificação do "
                "fornecedor e nas próximas contratações."
            ),
        ),
        reference_date=reference_date,
    )
    return created.id


def _period_text(period: date) -> str:
    return f"{period.month:02d}/{period.year}"


# ── Visão consolidada da administração contratual (ISSUE-035) ────────────


@dataclass(frozen=True)
class ContractOverviewRow:
    """Um contrato da lista consolidada: valor atual, medido, saldo, término, claims e avaliação."""

    id: int
    project_id: int
    project_label: str
    number: str
    company: str
    object: str
    modality: str
    situation: str
    start: date
    original_end: date
    current_end: date
    days_added: int
    original_value_cents: int
    addenda_cents: int
    current_value_cents: int
    measured_cents: int
    measured_pct: Decimal | None
    balance_to_invoice_cents: int
    open_claims: int
    exposure_cents: int
    last_evaluation: EvaluationView | None


@dataclass(frozen=True)
class ClaimOverviewRow:
    """Um claim da lista consolidada, com o contrato, o prazo de notificação e o alerta."""

    id: int
    project_id: int
    project_label: str
    contract_id: int
    contract_number: str
    code: str
    direction: str
    kind: str
    cause: str
    description: str
    event_date: date
    notification_date: date
    notification_days: int
    notification_late: bool
    notice_days: int
    claimed_cents: int
    claimed_days: int
    recognized_cents: int | None
    recognized_days: int | None
    situation: str
    closed_on: date | None
    is_open: bool


@dataclass(frozen=True)
class ExtensionOverviewRow:
    """Uma EOT da lista consolidada, com o contrato, o claim de origem e os dias."""

    id: int
    project_id: int
    project_label: str
    contract_id: int
    contract_number: str
    code: str
    claim_code: str
    event: str
    requested_days: int
    granted_days: int | None
    classification: str
    method: str
    affected_milestone: str
    requested_on: date
    decided_on: date | None
    situation: str
    is_open: bool


@dataclass(frozen=True)
class MilestoneOverviewRow:
    """Um marco da lista consolidada, com o valor calculado e o atraso dos pendentes."""

    id: int
    project_id: int
    project_label: str
    contract_id: int
    contract_number: str
    number: str
    description: str
    criteria: str
    pct: int
    value_cents: int
    expected_on: date
    completed_on: date | None
    situation: str
    is_late: bool
    late_days: int


@dataclass(frozen=True)
class EvaluationOverviewRow:
    """Uma avaliação da lista consolidada, com o contrato, a empresa e a nota/classe da ficha."""

    view: EvaluationView
    project_id: int
    project_label: str
    contract_id: int
    contract_number: str
    company: str


@dataclass(frozen=True)
class ContractsOverview:
    """A visão consolidada da administração contratual: as listas, o resumo e os indicadores."""

    scope_label: str
    is_portfolio: bool
    contracts: tuple[ContractOverviewRow, ...]
    claims: tuple[ClaimOverviewRow, ...]
    extensions: tuple[ExtensionOverviewRow, ...]
    milestones: tuple[MilestoneOverviewRow, ...]
    evaluations: tuple[EvaluationOverviewRow, ...]
    summary: calculations.ContractsSummary
    indicators: calculations.ContractIndicators

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no contract at all (the empty state of origin)."""
        return not self.contracts


@dataclass(frozen=True)
class _ContractValues:
    """O que a leitura de um contrato calcula: os aditivos, o valor atual, o medido e o saldo."""

    addenda_cents: int
    current_cents: int
    measured_cents: int
    balance_cents: int


@dataclass(frozen=True)
class _ContractSlice:
    """O que a leitura de um contrato devolve para a visão consolidada: as linhas e os fatos."""

    contract: ContractOverviewRow
    claims: tuple[ClaimOverviewRow, ...]
    extensions: tuple[ExtensionOverviewRow, ...]
    milestones: tuple[MilestoneOverviewRow, ...]
    evaluations: tuple[EvaluationOverviewRow, ...]
    contract_fact: calculations.ContractFact
    claim_facts: tuple[calculations.ClaimFact, ...]
    extension_facts: tuple[calculations.ExtensionFact, ...]
    milestone_facts: tuple[calculations.MilestoneFact, ...]
    last_evaluation_fact: calculations.EvaluationFact | None


def contracts_overview(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> ContractsOverview:
    """A visão consolidada da administração contratual do escopo (HU-098).

    As listas são as cinco abas da tela (contratos, claims, EOTs, marcos e avaliações) e cada
    valor sai das fatias anteriores: o valor atual, o medido, o saldo e o percentual do contrato,
    o valor do marco, o alerta de notificação e o atraso do marco; a nota e a classe de cada
    avaliação vêm dos pesos congelados. O resumo e os indicadores fecham a leitura, com a data de
    referência injetada. Quem lê precisa alcançar o módulo.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.VIEW)
    projects = configuracoes.list_projects(session)
    chosen = _overview_projects(projects, scope)
    labels = {project.id: _label(project) for project in chosen}
    companies = configuracoes.list_company_names(session)
    slices = [
        _contract_slice(
            session,
            contract=contract,
            project=project,
            label=labels[project.id],
            companies=companies,
            reference_date=reference_date,
        )
        for project in chosen
        for contract in _project_contracts(session, project_id=project.id)
    ]
    facts = calculations.ContractFacts(
        contracts=tuple(item.contract_fact for item in slices),
        claims=tuple(fact for item in slices for fact in item.claim_facts),
        extensions=tuple(fact for item in slices for fact in item.extension_facts),
        milestones=tuple(fact for item in slices for fact in item.milestone_facts),
        evaluations=tuple(
            item.last_evaluation_fact for item in slices if item.last_evaluation_fact is not None
        ),
    )
    return ContractsOverview(
        scope_label=PORTFOLIO_LABEL if scope.is_portfolio else labels[chosen[0].id],
        is_portfolio=scope.is_portfolio,
        contracts=tuple(sorted((item.contract for item in slices), key=lambda row: row.number)),
        claims=tuple(
            sorted(
                (row for item in slices for row in item.claims),
                key=lambda row: row.code,
                reverse=True,
            )
        ),
        extensions=tuple(
            sorted(
                (row for item in slices for row in item.extensions),
                key=lambda row: row.code,
                reverse=True,
            )
        ),
        milestones=tuple(
            sorted(
                (row for item in slices for row in item.milestones),
                key=lambda row: (row.expected_on, row.id),
            )
        ),
        evaluations=tuple(
            sorted(
                (row for item in slices for row in item.evaluations),
                key=lambda row: (row.view.period, row.view.id),
                reverse=True,
            )
        ),
        summary=calculations.contracts_summary(facts, reference_date=reference_date),
        indicators=calculations.contract_indicators(facts, reference_date=reference_date),
    )


def _overview_projects(
    projects: Sequence[configuracoes.ProjectSummary], scope: Scope
) -> tuple[configuracoes.ProjectSummary, ...]:
    """Os projetos do escopo: todos no Portfólio, só o escolhido no projeto."""
    if scope.is_portfolio:
        return tuple(projects)
    return (_project_of(projects, scope),)


# ── Desempenho por empresa, para o cadastro de fornecedores (D9, ISSUE-057) ──


@dataclass(frozen=True)
class CompanyContractRecord:
    """Um contrato do escopo com a empresa: número, objeto e valor original em centavos."""

    company_id: int
    number: str
    object: str
    original_value_cents: int


@dataclass(frozen=True)
class CompanyEvaluationRecord:
    """Uma avaliação da empresa, já calculada: período, tipo, contrato, nota e classe."""

    company_id: int
    contract_number: str
    period: date
    kind: str
    score: int | None
    score_class: str
    class_description: str


@dataclass(frozen=True)
class CompanyPerformance:
    """O desempenho de uma empresa no escopo: os contratos e as avaliações deles."""

    contracts: tuple[CompanyContractRecord, ...]
    evaluations: tuple[CompanyEvaluationRecord, ...]


def company_performance(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> dict[int, CompanyPerformance]:
    """Os contratos do escopo e as avaliações de cada empresa (o 04 lê o desempenho aqui).

    O cadastro de fornecedores é global, mas o desempenho é do escopo: no Portfólio entram os
    contratos dos três projetos e, no projeto aberto, só os dele. A nota e a classe de cada
    avaliação saem dos pesos congelados (D5b); a avaliação com período depois da data de
    referência de quem lê não conta.
    """
    rbac.require_module(user, MODULE)
    chosen = _overview_projects(configuracoes.list_projects(session), scope)
    project_ids = [project.id for project in chosen]
    if not project_ids:
        return {}
    contracts = list(
        session.scalars(
            select(Contract)
            .where(Contract.project_id.in_(project_ids))
            .order_by(Contract.number, Contract.id)
        )
    )
    records: dict[int, list[CompanyContractRecord]] = {}
    evaluations: dict[int, list[CompanyEvaluationRecord]] = {}
    for contract in contracts:
        records.setdefault(contract.company_id, []).append(
            CompanyContractRecord(
                company_id=contract.company_id,
                number=contract.number,
                object=contract.object,
                original_value_cents=contract.original_value_cents,
            )
        )
        for view in _evaluation_views(session, _evaluation_rows(session, contract_id=contract.id)):
            if view.period > reference_date:
                continue
            evaluations.setdefault(contract.company_id, []).append(
                CompanyEvaluationRecord(
                    company_id=contract.company_id,
                    contract_number=contract.number,
                    period=view.period,
                    kind=view.kind,
                    score=view.score,
                    score_class=view.score_class,
                    class_description=view.class_description,
                )
            )
    return {
        company_id: CompanyPerformance(
            contracts=tuple(records.get(company_id, ())),
            evaluations=tuple(
                sorted(evaluations.get(company_id, ()), key=lambda item: (item.period, item.kind))
            ),
        )
        for company_id in {*records, *evaluations}
    }


def _project_contracts(session: Session, *, project_id: int) -> list[Contract]:
    statement = select(Contract).where(Contract.project_id == project_id).order_by(Contract.number)
    return list(session.scalars(statement))


def _contract_slice(
    session: Session,
    *,
    contract: Contract,
    project: configuracoes.ProjectSummary,
    label: str,
    companies: Mapping[int, str],
    reference_date: date,
) -> _ContractSlice:
    """A leitura de um contrato: as cinco listas da visão e os fatos dos indicadores."""
    values = _contract_values(session, contract=contract)
    claims = tuple(
        _claim_overview_row(contract, row, project=project, label=label)
        for row in _claim_rows(session, contract_id=contract.id)
    )
    milestones = tuple(
        _milestone_overview_row(
            contract,
            row,
            project=project,
            label=label,
            current_value_cents=values.current_cents,
            reference_date=reference_date,
        )
        for row in _milestone_rows(session, contract_id=contract.id)
    )
    extension_rows = _extension_rows(session, contract_id=contract.id)
    claim_codes = _claim_codes(session, [row.claim_id for row in extension_rows])
    extensions = tuple(
        _extension_overview_row(
            contract, row, project=project, label=label, claim_codes=claim_codes
        )
        for row in extension_rows
    )
    evaluations = tuple(
        EvaluationOverviewRow(
            view=view,
            project_id=project.id,
            project_label=label,
            contract_id=contract.id,
            contract_number=contract.number,
            company=companies.get(contract.company_id, ""),
        )
        for view in _evaluation_views(session, _evaluation_rows(session, contract_id=contract.id))
    )
    claim_facts = tuple(_claim_fact(row) for row in claims)
    contract_row = _contract_overview_row(
        contract,
        project=project,
        label=label,
        companies=companies,
        claim_facts=claim_facts,
        evaluations=evaluations,
        values=values,
    )
    return _ContractSlice(
        contract=contract_row,
        claims=claims,
        extensions=extensions,
        milestones=milestones,
        evaluations=evaluations,
        contract_fact=_contract_fact(contract_row),
        claim_facts=claim_facts,
        extension_facts=tuple(_extension_fact(row) for row in extensions),
        milestone_facts=tuple(_milestone_fact(row) for row in milestones),
        last_evaluation_fact=(
            _evaluation_facts((evaluations[0].view,))[0] if evaluations else None
        ),
    )


def _contract_values(session: Session, *, contract: Contract) -> _ContractValues:
    """Os valores calculados do contrato, pelas fórmulas da ficha (ISSUE-032)."""
    addenda = _addendum_lines(_addendum_rows(session, contract_id=contract.id))
    measurements = _measurement_lines(_measurement_rows(session, contract_id=contract.id))
    current = calculations.contract_current_value_cents(contract.original_value_cents, addenda)
    measured = calculations.contract_measured_cents(measurements)
    return _ContractValues(
        addenda_cents=sum(line.value_cents for line in addenda),
        current_cents=current,
        measured_cents=measured,
        balance_cents=calculations.contract_balance_to_invoice_cents(current, measured),
    )


def _contract_overview_row(
    contract: Contract,
    *,
    project: configuracoes.ProjectSummary,
    label: str,
    companies: Mapping[int, str],
    claim_facts: Sequence[calculations.ClaimFact],
    evaluations: Sequence[EvaluationOverviewRow],
    values: _ContractValues,
) -> ContractOverviewRow:
    return ContractOverviewRow(
        id=contract.id,
        project_id=project.id,
        project_label=label,
        number=contract.number,
        company=companies.get(contract.company_id, ""),
        object=contract.object,
        modality=contract.modality,
        situation=contract.situation,
        start=contract.start,
        original_end=contract.original_end,
        current_end=contract.current_end,
        days_added=(contract.current_end - contract.original_end).days,
        original_value_cents=contract.original_value_cents,
        addenda_cents=values.addenda_cents,
        current_value_cents=values.current_cents,
        measured_cents=values.measured_cents,
        measured_pct=calculations.contract_measured_percent(
            values.measured_cents, values.current_cents
        ),
        balance_to_invoice_cents=values.balance_cents,
        open_claims=calculations.open_claim_count(claim_facts),
        exposure_cents=calculations.claim_exposure_cents(
            claim_facts, direction=calculations.CLAIM_DIRECTION_CONTRACTOR
        ),
        last_evaluation=evaluations[0].view if evaluations else None,
    )


def _claim_overview_row(
    contract: Contract,
    row: ContractClaim,
    *,
    project: configuracoes.ProjectSummary,
    label: str,
) -> ClaimOverviewRow:
    deadline = calculations.claim_notification_deadline(row.event_date, contract.claim_notice_days)
    return ClaimOverviewRow(
        id=row.id,
        project_id=project.id,
        project_label=label,
        contract_id=contract.id,
        contract_number=contract.number,
        code=row.code,
        direction=row.direction,
        kind=row.kind,
        cause=row.cause,
        description=row.description,
        event_date=row.event_date,
        notification_date=row.notification_date,
        notification_days=(row.notification_date - row.event_date).days,
        notification_late=calculations.claim_notification_late(row.notification_date, deadline),
        notice_days=contract.claim_notice_days,
        claimed_cents=row.claimed_cents,
        claimed_days=row.claimed_days,
        recognized_cents=row.recognized_cents,
        recognized_days=row.recognized_days,
        situation=row.situation,
        closed_on=row.closed_on,
        is_open=row.situation in calculations.CLAIM_OPEN_SITUATIONS,
    )


def _extension_overview_row(
    contract: Contract,
    row: ContractTimeExtension,
    *,
    project: configuracoes.ProjectSummary,
    label: str,
    claim_codes: Mapping[int, str],
) -> ExtensionOverviewRow:
    return ExtensionOverviewRow(
        id=row.id,
        project_id=project.id,
        project_label=label,
        contract_id=contract.id,
        contract_number=contract.number,
        code=row.code,
        claim_code=claim_codes.get(row.claim_id or 0, ""),
        event=row.event,
        requested_days=row.requested_days,
        granted_days=row.granted_days,
        classification=row.classification or "",
        method=row.method,
        affected_milestone=row.affected_milestone,
        requested_on=row.requested_on,
        decided_on=row.decided_on,
        situation=row.situation,
        is_open=row.situation
        in (calculations.EXTENSION_REQUESTED, calculations.EXTENSION_UNDER_REVIEW),
    )


def _milestone_overview_row(
    contract: Contract,
    row: ContractPaymentMilestone,
    *,
    project: configuracoes.ProjectSummary,
    label: str,
    current_value_cents: int,
    reference_date: date,
) -> MilestoneOverviewRow:
    is_late = calculations.milestone_is_late(row.expected_on, row.situation, reference_date)
    return MilestoneOverviewRow(
        id=row.id,
        project_id=project.id,
        project_label=label,
        contract_id=contract.id,
        contract_number=contract.number,
        number=row.number,
        description=row.description,
        criteria=row.acceptance_criteria,
        pct=row.pct,
        value_cents=calculations.milestone_value_cents(current_value_cents, row.pct),
        expected_on=row.expected_on,
        completed_on=row.completed_on,
        situation=row.situation,
        is_late=is_late,
        late_days=(
            calculations.milestone_late_days(row.expected_on, reference_date) if is_late else 0
        ),
    )


def _contract_fact(row: ContractOverviewRow) -> calculations.ContractFact:
    evaluation = row.last_evaluation
    return calculations.ContractFact(
        start=row.start,
        original_end=row.original_end,
        evaluation_class=(evaluation.score_class or None) if evaluation is not None else None,
    )


def _claim_fact(row: ClaimOverviewRow) -> calculations.ClaimFact:
    return calculations.ClaimFact(
        direction=row.direction,
        situation=row.situation,
        claimed_cents=row.claimed_cents,
        event_date=row.event_date,
        notification_date=row.notification_date,
        notice_days=row.notice_days,
        recognized_cents=row.recognized_cents,
        closed_on=row.closed_on,
    )


def _extension_fact(row: ExtensionOverviewRow) -> calculations.ExtensionFact:
    return calculations.ExtensionFact(
        requested_days=row.requested_days, granted_days=row.granted_days
    )


def _milestone_fact(row: MilestoneOverviewRow) -> calculations.MilestoneFact:
    return calculations.MilestoneFact(
        value_cents=row.value_cents, expected_on=row.expected_on, situation=row.situation
    )


def read_contract_origin(
    session: Session, *, user: User, record_id: int
) -> attachment_origins.OriginRecord | None:
    """Quem lê os anexos de um contrato: quem alcança o módulo (D5a)."""
    rbac.require_module(user, MODULE)
    contract = session.get(Contract, record_id)
    if contract is None:
        return None
    return attachment_origins.OriginRecord(project_id=contract.project_id)


def read_milestone_origin(
    session: Session, *, user: User, record_id: int
) -> attachment_origins.OriginRecord | None:
    """Quem lê a evidência de um marco: quem alcança o módulo (D5a)."""
    rbac.require_module(user, MODULE)
    milestone = session.get(ContractPaymentMilestone, record_id)
    if milestone is None:
        return None
    contract = session.get(Contract, milestone.contract_id)
    if contract is None:
        return None
    return attachment_origins.OriginRecord(project_id=contract.project_id)


def read_claim_origin(
    session: Session, *, user: User, record_id: int
) -> attachment_origins.OriginRecord | None:
    """Quem lê os documentos de um claim: quem alcança o módulo (D5a)."""
    rbac.require_module(user, MODULE)
    claim = session.get(ContractClaim, record_id)
    if claim is None:
        return None
    contract = session.get(Contract, claim.contract_id)
    if contract is None:
        return None
    return attachment_origins.OriginRecord(project_id=contract.project_id)


def read_evaluation_origin(
    session: Session, *, user: User, record_id: int
) -> attachment_origins.OriginRecord | None:
    """Quem lê a evidência de uma avaliação: quem alcança o módulo (D5a)."""
    rbac.require_module(user, MODULE)
    evaluation = session.get(ContractEvaluation, record_id)
    if evaluation is None:
        return None
    contract = session.get(Contract, evaluation.contract_id)
    if contract is None:
        return None
    return attachment_origins.OriginRecord(project_id=contract.project_id)


def _contract_exists(session: Session, reference: str) -> bool:
    """O contrato que uma lição aponta, pelo número: a conferência da fachada de Lições (D9)."""
    return session.scalar(select(Contract.id).where(Contract.number == reference)) is not None


def _register_lesson_origin() -> None:
    """Diz à fachada de Lições como confirmar o número do contrato (D9)."""
    from src.modulos.governanca import lessons_models as lessons
    from src.modulos.governanca import lessons_service

    lessons_service.register_origin(lessons.ORIGIN_CONTRACT, _contract_exists)


# ── Reservas (ISSUE-041) ─────────────────────────────────────────────────


DEFAULT_CONSUMPTION_TOLERANCE_PP = Decimal(10)
DEFAULT_COVERAGE_MINIMUM_PCT = 100
SITUATION_EFFECTIVE = "Efetivado"
RESERVE_ALERT_CONSUMPTION = "consumo"
RESERVE_ALERT_ANALYSIS = "analise"
RESERVE_ALERT_COVERAGE = "cobertura"


@dataclass(frozen=True)
class ReserveStateEntry:
    """O estado de uma reserva: o constituído, o consumo, a liberação, o saldo e o pedido em aberto."""

    kind: str
    total_cents: int
    consumed_cents: int
    released_cents: int
    balance_cents: int
    open_request_cents: int = 0


@dataclass(frozen=True)
class ReserveState:
    """O estado das reservas de um projeto, por tipo: o saldo e o pedido em SMs abertas."""

    entries: Mapping[str, ReserveStateEntry]

    def entry(self, kind: str) -> ReserveStateEntry | None:
        """O estado da reserva do tipo, ou ``None`` quando o projeto não a constituiu."""
        return self.entries.get(kind)


class ReserveChange(Protocol):
    """A SM que movimenta a reserva, como a fachada do Financeiro a lê (dona: Governança)."""

    id: int
    project_id: int
    title: str


@dataclass(frozen=True)
class ContingencyConsumption:
    """O consumo da reserva de contingência, como o painel de mudanças o mostra."""

    total_cents: int
    consumed_cents: int
    balance_cents: int


@dataclass(frozen=True)
class ReserveLine:
    """Uma reserva na tela: o constituído, o consumo, a liberação, o saldo e o pedido em análise."""

    kind: str
    total_cents: int
    consumed_cents: int
    released_cents: int
    balance_cents: int
    in_analysis_cents: int
    balance_after_analysis_cents: int
    consumption_pct: Decimal | None


@dataclass(frozen=True)
class ReserveAlert:
    """Um alerta da tela de Contingência: o consumo acima do limite ou o pedido acima do saldo."""

    kind: str
    text: str


@dataclass(frozen=True)
class ReserveMovementView:
    """Uma linha do extrato da reserva: o fato, a situação e o saldo corrente da própria reserva."""

    on: date
    kind: str
    reserve_kind: str
    value_cents: int
    situation: str
    change_code: str | None
    description: str
    balance_cents: int | None
    project_label: str | None = None


@dataclass(frozen=True)
class ContingencyProjectRow:
    """A linha de um projeto na tabela da carteira."""

    project_id: int
    project_code: str
    project_label: str
    contingency: ReserveLine | None
    management: ReserveLine | None
    consumption_limit_pct: Decimal | None
    alerts: tuple[ReserveAlert, ...]

    @property
    def alert_count(self) -> int:
        """Quantos alertas o projeto tem."""
        return len(self.alerts)


@dataclass(frozen=True)
class ContingencyThreatView:
    """Uma ameaça ativa da cobertura: o VME e as SMs que a citam na análise de impacto."""

    project_id: int
    code: str
    title: str
    severity: str
    situation: str
    vme_cents: int
    change_codes: tuple[str, ...] = ()
    project_code: str = ""


@dataclass(frozen=True)
class ContingencyOverview:
    """A tela de Contingência do escopo: as reservas, o extrato, o burn, a composição e os alertas."""

    is_portfolio: bool
    scope_label: str
    contingency: ReserveLine | None
    management: ReserveLine | None
    physical_actual: Decimal | None
    physical_predicted: Decimal | None
    consumption_limit_pct: Decimal | None
    tolerance_pp: Decimal
    eac_current_cents: int
    cost_baseline_cents: int
    project_budget_cents: int
    movements: tuple[ReserveMovementView, ...]
    burn: tuple[calculations.ReserveBurnPoint, ...]
    expected_balance_cents: int | None
    analysis_count: int
    alerts: tuple[ReserveAlert, ...]
    projects: tuple[ContingencyProjectRow, ...] = ()
    exposure_cents: int = 0
    coverage_pct: Decimal | None = None
    coverage_minimum_pct: int = 100
    threats: tuple[ContingencyThreatView, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no reserve at all: the empty state of the screen."""
        return self.contingency is None and self.management is None


@dataclass(frozen=True)
class _ProjectReserves:
    """O que a leitura de um projeto devolve: as reservas, o extrato, o burn e os alertas."""

    project: configuracoes.ProjectSummary
    contingency: ReserveLine | None
    management: ReserveLine | None
    movements: tuple[ReserveMovementView, ...]
    burn: tuple[calculations.ReserveBurnPoint, ...]
    physical_actual: Decimal | None
    physical_predicted: Decimal | None
    consumption_limit_pct: Decimal | None
    expected_balance_cents: int | None
    analysis_count: int
    alerts: tuple[ReserveAlert, ...]
    eac_current_cents: int
    exposure_cents: int = 0
    coverage_pct: Decimal | None = None
    threats: tuple[ContingencyThreatView, ...] = ()


def reserve_kind_for_source(source: str | None) -> str | None:
    """O tipo de reserva da fonte do recurso da SM, ou ``None`` quando a fonte é outra."""
    return calculations.RESERVE_KIND_BY_SOURCE.get(source or "")


def reserve_state(
    session: Session, *, project_id: int, exclude_change_id: int | None = None
) -> ReserveState:
    """O estado das reservas do projeto: saldo por tipo e pedido em SMs abertas por tipo.

    O saldo é a soma dos movimentos (constituição positiva, consumo e liberação negativos) e o
    pedido soma as SMs abertas com a fonte da reserva e as de liberação daquela reserva. A SM
    informada em ``exclude_change_id`` fica de fora quando o próprio pedido está sendo conferido.
    """
    entries = _reserve_entries(session, project_id=project_id)
    if not entries:
        return ReserveState(entries={})
    totals = _open_reserve_request_totals(
        session, project_id=project_id, exclude_change_id=exclude_change_id
    )
    for kind, value in totals.items():
        if kind in entries:
            entries[kind] = replace(entries[kind], open_request_cents=value)
    return ReserveState(entries=entries)


def check_reserve_consumption(
    session: Session,
    *,
    project_id: int,
    source: str,
    value_cents: int,
    exclude_change_id: int | None = None,
) -> None:
    """Recusa (422) o consumo acima do saldo da reserva da fonte, nomeando a reserva.

    O projeto sem a reserva constituída é recusado com a mensagem própria; uma fonte que não é de
    reserva não passa por aqui.
    """
    kind = reserve_kind_for_source(source)
    if kind is None or value_cents <= 0:
        return
    entry = reserve_state(
        session, project_id=project_id, exclude_change_id=exclude_change_id
    ).entry(kind)
    if entry is None:
        raise InvalidDataError(validation.reserve_missing_error())
    message = validation.reserve_consumption_error(
        value_cents, entry.balance_cents, reserve_source=source
    )
    if message:
        raise InvalidDataError(message)


def check_reserve_release(
    session: Session,
    *,
    project_id: int,
    reserve_kind: str,
    value_cents: int,
    exclude_change_id: int | None = None,
) -> None:
    """Recusa (422) a liberação acima do saldo menos o pedido em outras SMs abertas da reserva."""
    if value_cents <= 0:
        return
    entry = reserve_state(
        session, project_id=project_id, exclude_change_id=exclude_change_id
    ).entry(reserve_kind)
    if entry is None:
        raise InvalidDataError(validation.reserve_missing_error())
    message = validation.reserve_release_error(
        value_cents, entry.balance_cents, entry.open_request_cents
    )
    if message:
        raise InvalidDataError(message)


def record_reserve_consumption(
    session: Session,
    *,
    user: User,
    change: ReserveChange,
    source: str,
    value_cents: int,
    on: date,
) -> None:
    """Grava o consumo da reserva na aprovação da SM: movimento negativo com a data da decisão."""
    kind = reserve_kind_for_source(source)
    if kind is None:
        return
    _record_reserve_movement(
        session,
        user=user,
        change=change,
        movement_kind=calculations.MOVEMENT_CONSUMPTION,
        reserve_kind=kind,
        value_cents=value_cents,
        on=on,
    )


def record_reserve_release(
    session: Session,
    *,
    user: User,
    change: ReserveChange,
    reserve_kind: str,
    value_cents: int,
    on: date,
) -> None:
    """Grava a liberação da reserva na aprovação da SM: movimento negativo com a data da decisão."""
    _record_reserve_movement(
        session,
        user=user,
        change=change,
        movement_kind=calculations.MOVEMENT_RELEASE,
        reserve_kind=reserve_kind,
        value_cents=value_cents,
        on=on,
    )


def contingency_consumption(session: Session, *, scope: Scope) -> ContingencyConsumption | None:
    """O consumo da reserva de contingência do escopo, ou ``None`` sem reserva constituída."""
    projects = [
        project
        for project in configuracoes.list_projects(session)
        if scope.is_portfolio or project.id == scope.project_id
    ]
    total = consumed = balance = 0
    found = False
    for project in projects:
        entry = _reserve_entries(session, project_id=project.id).get(
            calculations.RESERVE_CONTINGENCY
        )
        if entry is None:
            continue
        found = True
        total += entry.total_cents
        consumed += entry.consumed_cents
        balance += entry.balance_cents
    if not found:
        return None
    return ContingencyConsumption(total_cents=total, consumed_cents=consumed, balance_cents=balance)


def contingency_overview(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> ContingencyOverview:
    """A tela de Contingência do escopo: as reservas, o extrato, o burn e a composição (HU-094).

    No projeto, as reservas de contingência e gerencial com o saldo, o consumo, a liberação, o
    pedido em SMs abertas e o limite de consumo (avanço físico real mais a tolerância); o burn usa
    os meses da Curva S física congelada. No Portfólio, a soma dos projetos com a tabela por
    projeto e o burn da união. A cobertura é o saldo da contingência sobre a exposição de VME das
    ameaças ativas do 05, lida pela fachada da Riscos, contra a meta do grupo ``financeiro``.
    """
    projects = configuracoes.list_projects(session)
    tolerance = _consumption_tolerance(session, reference_date=reference_date)
    coverage_minimum = _coverage_minimum(session, reference_date=reference_date)
    if scope.is_portfolio:
        return _portfolio_contingency(
            session,
            user=user,
            projects=projects,
            reference_date=reference_date,
            tolerance_pp=tolerance,
            coverage_minimum=coverage_minimum,
        )
    project = _project_of(projects, scope)
    part = _project_reserves(
        session,
        user=user,
        project=project,
        reference_date=reference_date,
        tolerance_pp=tolerance,
        coverage_minimum=coverage_minimum,
    )
    if part is None:
        return _empty_contingency(
            is_portfolio=False,
            scope_label=_label(project),
            tolerance_pp=tolerance,
            coverage_minimum=coverage_minimum,
        )
    composition = calculations.reserve_composition(
        part.eac_current_cents,
        part.contingency.balance_cents if part.contingency else 0,
        part.management.balance_cents if part.management else 0,
    )
    return ContingencyOverview(
        is_portfolio=False,
        scope_label=_label(project),
        contingency=part.contingency,
        management=part.management,
        physical_actual=part.physical_actual,
        physical_predicted=part.physical_predicted,
        consumption_limit_pct=part.consumption_limit_pct,
        tolerance_pp=tolerance,
        eac_current_cents=part.eac_current_cents,
        cost_baseline_cents=composition.cost_baseline_cents,
        project_budget_cents=composition.project_budget_cents,
        movements=part.movements,
        burn=part.burn,
        expected_balance_cents=part.expected_balance_cents,
        analysis_count=part.analysis_count,
        alerts=part.alerts,
        exposure_cents=part.exposure_cents,
        coverage_pct=part.coverage_pct,
        coverage_minimum_pct=coverage_minimum,
        threats=part.threats,
    )


def _reserve_entries(session: Session, *, project_id: int) -> dict[str, ReserveStateEntry]:
    reserves = session.scalars(
        select(Reserve).where(Reserve.project_id == project_id).order_by(Reserve.id)
    ).all()
    if not reserves:
        return {}
    by_id = {reserve.id: reserve.kind for reserve in reserves}
    entries = {
        reserve.kind: ReserveStateEntry(
            kind=reserve.kind,
            total_cents=0,
            consumed_cents=0,
            released_cents=0,
            balance_cents=0,
        )
        for reserve in reserves
    }
    statement = select(ReserveMovement).where(ReserveMovement.reserve_id.in_(list(by_id)))
    for movement in session.scalars(statement):
        kind = by_id[movement.reserve_id]
        entry = entries[kind]
        if movement.kind == calculations.MOVEMENT_CONSTITUTION:
            entry = replace(entry, total_cents=entry.total_cents + movement.value_cents)
        elif movement.kind == calculations.MOVEMENT_CONSUMPTION:
            entry = replace(entry, consumed_cents=entry.consumed_cents - movement.value_cents)
        elif movement.kind == calculations.MOVEMENT_RELEASE:
            entry = replace(entry, released_cents=entry.released_cents - movement.value_cents)
        entries[kind] = replace(entry, balance_cents=entry.balance_cents + movement.value_cents)
    return entries


def _open_reserve_request_totals(
    session: Session, *, project_id: int, exclude_change_id: int | None = None
) -> dict[str, int]:
    totals: dict[str, int] = {}
    for request in _open_requests(
        session, project_id=project_id, exclude_change_id=exclude_change_id
    ):
        kind = _request_kind(request)
        if kind is None:
            continue
        totals[kind] = totals.get(kind, 0) + request.value_cents
    return totals


def _open_requests(
    session: Session, *, project_id: int, exclude_change_id: int | None = None
) -> tuple[OpenReserveRequest, ...]:
    from src.modulos.governanca import service as governanca

    return governanca.open_reserve_requests(
        session, project_id=project_id, exclude_change_id=exclude_change_id
    )


def _request_kind(request: OpenReserveRequest) -> str | None:
    return request.release_kind or calculations.RESERVE_KIND_BY_SOURCE.get(request.source or "")


def _record_reserve_movement(
    session: Session,
    *,
    user: User,
    change: ReserveChange,
    movement_kind: str,
    reserve_kind: str,
    value_cents: int,
    on: date,
) -> None:
    reserve = session.scalars(
        select(Reserve).where(Reserve.project_id == change.project_id, Reserve.kind == reserve_kind)
    ).one_or_none()
    if reserve is None:
        raise InvalidDataError(validation.reserve_missing_error())
    recording.create(
        session,
        user_id=user.id,
        record=ReserveMovement(
            reserve_id=reserve.id,
            change_id=change.id,
            registered_by_id=user.person_id,
            kind=movement_kind,
            registered_on=on,
            value_cents=-abs(value_cents),
            justification=change.title,
        ),
    )


def _consumption_tolerance(session: Session, *, reference_date: date) -> Decimal:
    group = configuracoes.current_group(session, group=MODULE, reference_date=reference_date)
    contingency = group.get("contingencia")
    raw = contingency.get("toleranciaConsumoPP") if isinstance(contingency, Mapping) else None
    return Decimal(str(raw)) if raw is not None else DEFAULT_CONSUMPTION_TOLERANCE_PP


def _coverage_minimum(session: Session, *, reference_date: date) -> int:
    """A meta da cobertura do grupo ``financeiro`` (``coberturaMinimaPct``), nunca no código."""
    group = configuracoes.current_group(session, group=MODULE, reference_date=reference_date)
    contingency = group.get("contingencia")
    raw = contingency.get("coberturaMinimaPct") if isinstance(contingency, Mapping) else None
    return int(raw) if raw is not None else DEFAULT_COVERAGE_MINIMUM_PCT


def _project_reserves(
    session: Session,
    *,
    user: User,
    project: configuracoes.ProjectSummary,
    reference_date: date,
    tolerance_pp: Decimal,
    coverage_minimum: int,
) -> _ProjectReserves | None:
    reserves = session.scalars(
        select(Reserve).where(Reserve.project_id == project.id).order_by(Reserve.id)
    ).all()
    if not reserves:
        return None
    by_id = {reserve.id: reserve for reserve in reserves}
    statement = (
        select(ReserveMovement)
        .where(ReserveMovement.reserve_id.in_(list(by_id)))
        .order_by(ReserveMovement.registered_on, ReserveMovement.id)
    )
    movements = list(session.scalars(statement))
    requests = _open_requests(session, project_id=project.id)
    lines = {
        reserve.kind: _reserve_line(
            kind=reserve.kind,
            movements=[row for row in movements if row.reserve_id == reserve.id],
            requests=requests,
        )
        for reserve in reserves
    }
    contingency = lines.get(calculations.RESERVE_CONTINGENCY)
    management = lines.get(calculations.RESERVE_MANAGEMENT)
    series = _curve_series(session, project_id=project.id, reference_date=reference_date)
    physical_actual, physical_predicted = _physical_indicators(series)
    limit = calculations.reserve_consumption_limit(physical_actual, tolerance_pp)
    contingency_movements = [
        row for row in movements if by_id[row.reserve_id].kind == calculations.RESERVE_CONTINGENCY
    ]
    burn, expected = _project_burn(
        series=series, contingency=contingency, movements=contingency_movements
    )
    threats = _threat_views(
        session, user=user, project_id=project.id, reference_date=reference_date
    )
    exposure = sum(threat.vme_cents for threat in threats)
    balance = contingency.balance_cents if contingency is not None else 0
    coverage = _coverage_pct(balance, exposure)
    return _ProjectReserves(
        project=project,
        contingency=contingency,
        management=management,
        movements=_movement_views(
            session, reserves_by_id=by_id, movements=movements, requests=requests
        ),
        burn=burn,
        physical_actual=physical_actual,
        physical_predicted=physical_predicted,
        consumption_limit_pct=limit,
        expected_balance_cents=expected,
        analysis_count=sum(
            1 for request in requests if _request_kind(request) == calculations.RESERVE_CONTINGENCY
        ),
        alerts=_reserve_alerts(
            contingency=contingency,
            limit=limit,
            coverage=coverage,
            coverage_minimum=coverage_minimum,
        ),
        eac_current_cents=_eac_current_cents(session, project_id=project.id),
        exposure_cents=exposure,
        coverage_pct=coverage,
        threats=threats,
    )


def _threat_views(
    session: Session, *, user: User, project_id: int, reference_date: date
) -> tuple[ContingencyThreatView, ...]:
    """As ameaças ativas do projeto pela fachada da Riscos, com as SMs que as citam (D9)."""
    from src.modulos.governanca import service as governanca
    from src.modulos.riscos import service as riscos

    threats = riscos.active_threats(
        session,
        user=user,
        scope=Scope(project_id=project_id, source="padrao"),
        reference_date=reference_date,
    )
    mentions = governanca.change_codes_citing_risks(
        session, project_id=project_id, codes=[threat.code for threat in threats]
    )
    return tuple(
        ContingencyThreatView(
            project_id=project_id,
            code=threat.code,
            title=threat.title,
            severity=threat.current.severity.name if threat.current is not None else "",
            situation=threat.situation,
            vme_cents=threat.vme_cents,
            change_codes=mentions.get(threat.code, ()),
        )
        for threat in threats
    )


def _coverage_pct(balance_cents: int, exposure_cents: int) -> Decimal | None:
    """A cobertura do saldo sobre a exposição: saldo dividido pela exposição, uma casa (protótipo)."""
    if not exposure_cents:
        return None
    value = Decimal(balance_cents) / Decimal(exposure_cents) * 100
    return value.quantize(calculations.ONE_PLACE, rounding=ROUND_HALF_UP)


def _reserve_line(
    *,
    kind: str,
    movements: Sequence[ReserveMovement],
    requests: Sequence[OpenReserveRequest],
) -> ReserveLine:
    total = sum(
        row.value_cents for row in movements if row.kind == calculations.MOVEMENT_CONSTITUTION
    )
    consumed = -sum(
        row.value_cents for row in movements if row.kind == calculations.MOVEMENT_CONSUMPTION
    )
    released = -sum(
        row.value_cents for row in movements if row.kind == calculations.MOVEMENT_RELEASE
    )
    balance = sum(row.value_cents for row in movements)
    in_analysis = sum(request.value_cents for request in requests if _request_kind(request) == kind)
    return ReserveLine(
        kind=kind,
        total_cents=total,
        consumed_cents=consumed,
        released_cents=released,
        balance_cents=balance,
        in_analysis_cents=in_analysis,
        balance_after_analysis_cents=calculations.reserve_after_analysis(balance, in_analysis),
        consumption_pct=calculations.reserve_consumption_pct(consumed, total),
    )


def _movement_views(
    session: Session,
    *,
    reserves_by_id: Mapping[int, Reserve],
    movements: Sequence[ReserveMovement],
    requests: Sequence[OpenReserveRequest],
) -> tuple[ReserveMovementView, ...]:
    """As linhas do extrato: os fatos e os pedidos em análise, com o saldo corrente da reserva.

    O saldo é o da própria reserva (contingência e gerencial independentes), como o protótipo o
    calcula dentro do extrato de cada uma antes de juntá-los: a linha "Em análise" não altera
    saldo algum. A ordenação final por data preserva a ordem de cada reserva, então o saldo
    corrente de cada uma sai correto na leitura única.
    """
    from src.modulos.governanca import service as governanca

    codes = governanca.change_codes(
        session, change_ids=[row.change_id for row in movements if row.change_id is not None]
    )
    lines = [
        ReserveMovementView(
            on=row.registered_on,
            kind=row.kind,
            reserve_kind=reserves_by_id[row.reserve_id].kind,
            value_cents=row.value_cents,
            situation=SITUATION_EFFECTIVE,
            change_code=codes.get(row.change_id) if row.change_id else None,
            description=row.justification,
            balance_cents=None,
        )
        for row in movements
    ]
    for request in requests:
        kind = _request_kind(request)
        if kind is None:
            continue
        lines.append(
            ReserveMovementView(
                on=request.request_date,
                kind=calculations.MOVEMENT_IN_ANALYSIS,
                reserve_kind=kind,
                value_cents=-request.value_cents,
                situation=request.situation,
                change_code=request.code,
                description=request.title,
                balance_cents=None,
            )
        )
    lines.sort(key=lambda line: line.on)
    balances: dict[str, int] = {}
    result: list[ReserveMovementView] = []
    for line in lines:
        if line.kind == calculations.MOVEMENT_IN_ANALYSIS:
            result.append(line)
            continue
        balance = balances.get(line.reserve_kind, 0) + line.value_cents
        balances[line.reserve_kind] = balance
        result.append(replace(line, balance_cents=balance))
    return tuple(result)


def _curve_series(session: Session, *, project_id: int, reference_date: date) -> CurvaFisicaSeries:
    from src.modulos.planejamento import service as planejamento

    overview = planejamento.curva_fisica_overview(
        session,
        scope=Scope(project_id=project_id, source="url"),
        reference_date=reference_date,
    )
    return overview.series


def _physical_indicators(
    series: CurvaFisicaSeries,
) -> tuple[Decimal | None, Decimal | None]:
    if not series.months or series.cut_index < 0:
        return None, None
    index = series.cut_index
    actual = series.real[index] if index < len(series.real) else None
    predicted = series.baseline[index] if index < len(series.baseline) else None
    return actual, predicted


def _project_burn(
    *,
    series: CurvaFisicaSeries,
    contingency: ReserveLine | None,
    movements: Sequence[ReserveMovement],
) -> tuple[tuple[calculations.ReserveBurnPoint, ...], int | None]:
    if contingency is None or not series.months:
        return (), None
    lines = [
        calculations.ReserveMovementLine(
            kind=row.kind,
            value_cents=row.value_cents,
            on=row.registered_on,
            change_id=row.change_id,
        )
        for row in movements
    ]
    burn = calculations.reserve_burn(
        series.months, series.baseline, series.cut_index, contingency.total_cents, lines
    )
    return burn, _expected_of(burn)


def _expected_of(burn: Sequence[calculations.ReserveBurnPoint]) -> int | None:
    known = [point for point in burn if point.actual_cents is not None]
    return known[-1].expected_cents if known else None


def _reserve_alerts(
    *,
    contingency: ReserveLine | None,
    limit: Decimal | None,
    coverage: Decimal | None = None,
    coverage_minimum: int = DEFAULT_COVERAGE_MINIMUM_PCT,
) -> tuple[ReserveAlert, ...]:
    if contingency is None:
        return ()
    alerts: list[ReserveAlert] = []
    pct = contingency.consumption_pct
    if pct is not None and limit is not None and pct > limit:
        alerts.append(
            ReserveAlert(
                kind=RESERVE_ALERT_CONSUMPTION,
                text=(
                    f"Consumo da contingência ({_decimal_text(pct)}%) acima do avanço físico real "
                    f"mais a tolerância ({_decimal_text(limit)}%)."
                ),
            )
        )
    if coverage is not None and coverage < coverage_minimum:
        alerts.append(
            ReserveAlert(
                kind=RESERVE_ALERT_COVERAGE,
                text=(
                    f"Saldo cobre {_decimal_text(coverage)}% da exposição das ameaças ativas "
                    f"(meta {coverage_minimum}%)."
                ),
            )
        )
    if contingency.in_analysis_cents > contingency.balance_cents:
        alerts.append(
            ReserveAlert(
                kind=RESERVE_ALERT_ANALYSIS,
                text=(
                    f"SMs em análise pedem {format_brl(contingency.in_analysis_cents)} da "
                    f"contingência, acima do saldo ({format_brl(contingency.balance_cents)})."
                ),
            )
        )
    return tuple(alerts)


def _decimal_text(value: Decimal) -> str:
    return str(value).replace(".", ",")


def _portfolio_contingency(
    session: Session,
    *,
    user: User,
    projects: Sequence[configuracoes.ProjectSummary],
    reference_date: date,
    tolerance_pp: Decimal,
    coverage_minimum: int,
) -> ContingencyOverview:
    parts = [
        part
        for project in projects
        if (
            part := _project_reserves(
                session,
                user=user,
                project=project,
                reference_date=reference_date,
                tolerance_pp=tolerance_pp,
                coverage_minimum=coverage_minimum,
            )
        )
        is not None
    ]
    contingency = _sum_lines([part.contingency for part in parts])
    management = _sum_lines([part.management for part in parts])
    if contingency is None and management is None:
        return _empty_contingency(
            is_portfolio=True,
            scope_label=PORTFOLIO_LABEL,
            tolerance_pp=tolerance_pp,
            coverage_minimum=coverage_minimum,
        )
    burn = calculations.reserve_burn_union(
        [
            calculations.ReserveBurnSeries(
                total_cents=part.contingency.total_cents, points=part.burn
            )
            for part in parts
            if part.contingency is not None
        ]
    )
    physical_actual = _weighted_physical(parts)
    eac_current = sum(part.eac_current_cents for part in parts)
    composition = calculations.reserve_composition(
        eac_current,
        contingency.balance_cents if contingency else 0,
        management.balance_cents if management else 0,
    )
    exposure = sum(part.exposure_cents for part in parts)
    return ContingencyOverview(
        is_portfolio=True,
        scope_label=PORTFOLIO_LABEL,
        contingency=contingency,
        management=management,
        physical_actual=physical_actual,
        physical_predicted=None,
        consumption_limit_pct=calculations.reserve_consumption_limit(physical_actual, tolerance_pp),
        tolerance_pp=tolerance_pp,
        eac_current_cents=eac_current,
        cost_baseline_cents=composition.cost_baseline_cents,
        project_budget_cents=composition.project_budget_cents,
        movements=tuple(
            replace(line, project_label=part.project.code)
            for part in parts
            for line in part.movements
        ),
        burn=burn,
        expected_balance_cents=_expected_of(burn),
        analysis_count=sum(part.analysis_count for part in parts),
        alerts=tuple(
            ReserveAlert(kind=alert.kind, text=f"{part.project.code}: {alert.text}")
            for part in parts
            for alert in part.alerts
        ),
        projects=tuple(_project_row(part) for part in parts),
        exposure_cents=exposure,
        coverage_pct=_coverage_pct(contingency.balance_cents if contingency else 0, exposure),
        coverage_minimum_pct=coverage_minimum,
        threats=tuple(
            replace(threat, project_code=part.project.code)
            for part in parts
            for threat in part.threats
        ),
    )


def _sum_lines(lines: Sequence[ReserveLine | None]) -> ReserveLine | None:
    present = [line for line in lines if line is not None]
    if not present:
        return None
    total = sum(line.total_cents for line in present)
    consumed = sum(line.consumed_cents for line in present)
    released = sum(line.released_cents for line in present)
    balance = sum(line.balance_cents for line in present)
    in_analysis = sum(line.in_analysis_cents for line in present)
    return ReserveLine(
        kind=present[0].kind,
        total_cents=total,
        consumed_cents=consumed,
        released_cents=released,
        balance_cents=balance,
        in_analysis_cents=in_analysis,
        balance_after_analysis_cents=calculations.reserve_after_analysis(balance, in_analysis),
        consumption_pct=calculations.reserve_consumption_pct(consumed, total),
    )


def _project_row(part: _ProjectReserves) -> ContingencyProjectRow:
    return ContingencyProjectRow(
        project_id=part.project.id,
        project_code=part.project.code,
        project_label=_label(part.project),
        contingency=part.contingency,
        management=part.management,
        consumption_limit_pct=part.consumption_limit_pct,
        alerts=part.alerts,
    )


def _weighted_physical(parts: Sequence[_ProjectReserves]) -> Decimal | None:
    weighted: list[tuple[Decimal, int]] = []
    for part in parts:
        if (
            part.physical_actual is not None
            and part.contingency is not None
            and part.contingency.total_cents > 0
        ):
            weighted.append((part.physical_actual, part.contingency.total_cents))
    total = sum(weight for _, weight in weighted)
    if not total:
        return None
    value = sum((actual * weight for actual, weight in weighted), Decimal(0)) / total
    return value.quantize(calculations.ONE_PLACE, rounding=ROUND_HALF_UP)


def _eac_current_cents(session: Session, *, project_id: int) -> int:
    items = _lines_by_project(session, [project_id]).get(project_id, [])
    return calculations.project_total_cents(items) if items else 0


def _map_reserves(
    session: Session, *, project_ids: Sequence[int], deviation_cents: int
) -> MapaReserveSummary | None:
    states = [reserve_state(session, project_id=project_id) for project_id in project_ids]
    contingency = [
        entry
        for state in states
        if (entry := state.entry(calculations.RESERVE_CONTINGENCY)) is not None
    ]
    management = [
        entry
        for state in states
        if (entry := state.entry(calculations.RESERVE_MANAGEMENT)) is not None
    ]
    if not contingency and not management:
        return None
    total = sum(entry.total_cents for entry in contingency)
    consumed = sum(entry.consumed_cents for entry in contingency)
    balance = sum(entry.balance_cents for entry in contingency)
    return MapaReserveSummary(
        contingency_balance_cents=balance,
        contingency_consumption_pct=calculations.reserve_consumption_pct(consumed, total),
        in_analysis_cents=sum(entry.open_request_cents for entry in contingency),
        management_balance_cents=sum(entry.balance_cents for entry in management),
        covers_deviation=deviation_cents <= 0 or balance >= deviation_cents,
    )


def _empty_contingency(
    *,
    is_portfolio: bool,
    scope_label: str,
    tolerance_pp: Decimal,
    coverage_minimum: int = DEFAULT_COVERAGE_MINIMUM_PCT,
) -> ContingencyOverview:
    return ContingencyOverview(
        is_portfolio=is_portfolio,
        scope_label=scope_label,
        contingency=None,
        management=None,
        physical_actual=None,
        physical_predicted=None,
        consumption_limit_pct=None,
        tolerance_pp=tolerance_pp,
        eac_current_cents=0,
        cost_baseline_cents=0,
        project_budget_cents=0,
        movements=(),
        burn=(),
        expected_balance_cents=None,
        analysis_count=0,
        alerts=(),
        coverage_minimum_pct=coverage_minimum,
    )


# ── Curva S financeira e KPIs de custo (ISSUE-042) ───────────────────────


@dataclass(frozen=True)
class FinancialCurveSeries:
    """As séries acumuladas da Curva S financeira: os meses, o corte e as quatro linhas."""

    months: tuple[date, ...]
    cut_index: int
    planned: tuple[int, ...]
    committed: tuple[int | None, ...]
    actual: tuple[int | None, ...]
    trend: tuple[int | None, ...]


@dataclass(frozen=True)
class FinancialCurvePoint:
    """Um mês da tabela período a período: o acumulado das quatro linhas e o corte."""

    month: date
    planned_cents: int
    committed_cents: int | None
    actual_cents: int | None
    trend_cents: int | None
    is_cut: bool


@dataclass(frozen=True)
class FinancialCurveKpis:
    """Os KPIs do topo da Curva S financeira, no corte."""

    budget_cents: int
    planned_cents: int
    committed_cents: int | None
    actual_cents: int | None
    trend_cents: int | None
    deviation_cents: int | None
    committed_pct: Decimal | None


@dataclass(frozen=True)
class FinancialCurveOverview:
    """A Curva S financeira do escopo: a revisão vigente, as séries, a tabela e os KPIs."""

    reference_date: date
    is_portfolio: bool
    scope_label: str
    project_id: int | None
    revision: int | None
    revision_date: date | None
    series: FinancialCurveSeries
    points: tuple[FinancialCurvePoint, ...]
    kpis: FinancialCurveKpis | None

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no frozen financial curve: the empty state of origin."""
        return not self.series.months


@dataclass(frozen=True)
class CostKpiMonth:
    """Um mês do valor agregado: PV, EV, AC, os desvios e os índices acumulados até ele."""

    month: date
    pv_cents: int
    ev_cents: int
    ac_cents: int
    cv_cents: int
    sv_cents: int
    cpi: Decimal | None
    spi: Decimal | None
    eac_by_cpi_cents: int | None
    tcpi: Decimal | None


@dataclass(frozen=True)
class CostKpiProjectRow:
    """A linha de um projeto na tabela de desempenho de custo da carteira."""

    project_id: int
    project_code: str
    project_label: str
    bac_cents: int
    ev_cents: int
    ac_cents: int
    cpi: Decimal | None
    spi: Decimal | None
    projection_cents: int | None
    vac_cents: int | None
    contingency_pct: Decimal | None


@dataclass(frozen=True)
class CostKpisOverview:
    """Os KPIs de custo do escopo: o corte, os índices, a série mês a mês e a tabela."""

    reference_date: date
    is_portfolio: bool
    scope_label: str
    project_id: int | None
    cut_month: date | None
    budget_cents: int
    indicators: calculations.CostIndicators | None
    projection_cents: int | None
    vac_cents: int | None
    committed_cents: int | None
    committed_pct: Decimal | None
    contingency_total_cents: int
    contingency_consumed_cents: int
    contingency_pct: Decimal | None
    actual: CostKpiMonth | None
    previous: CostKpiMonth | None
    history: tuple[CostKpiMonth, ...]
    projects: tuple[CostKpiProjectRow, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no EAC and curve to aggregate: the empty state of origin."""
        return self.actual is None


@dataclass(frozen=True)
class _FinancialRecord:
    """A revisão congelada da curva de um projeto, como o banco a guarda."""

    project_id: int
    revision: int
    revision_date: date
    total_cents: int
    months: tuple[date, ...]
    planned: tuple[int, ...]


@dataclass(frozen=True)
class _FrozenFinancialCurve:
    """A curva de um projeto pronta: orçamento, séries e a curva física do valor agregado."""

    project_id: int
    revision: int
    revision_date: date
    budget_cents: int
    series: FinancialCurveSeries
    physical: CurvaFisicaSeries


def freeze_financial_curve(session: Session, *, revision: EacRevision) -> None:
    """Congela a linha de base da Curva S financeira na revisão da EAC (D5b, HU-093).

    O planejado de cada mês é o total da revisão distribuído pelo perfil da curva física vigente
    do projeto; sem curva física congelada, o perfil é a distribuição linear das datas dos pacotes
    de nível 3 da EAP; sem pacote com peso e datas, não há o que congelar. A revisão nova
    recongela e a anterior fica. A revisão da curva e os seus meses entram na transação do
    chamador — é o gancho do ``create_revision`` da EAC.
    """
    profile = _financial_profile(
        session, project_id=revision.project_id, reference_date=revision.revision_date
    )
    if profile is None:
        return
    months, baseline = profile
    record = CurvaFinanceiraRevision(
        project_id=revision.project_id,
        eac_revision_id=revision.id,
        generated_at=calendario.now(),
    )
    session.add(record)
    session.flush()
    planned = calculations.curva_financeira_planejado(
        baseline, _revision_total_cents(session, revision=revision)
    )
    session.add_all(
        CurvaFinanceiraMonth(revision_id=record.id, month=month, planned_cents=cents)
        for month, cents in zip(months, planned, strict=True)
    )
    session.flush()


def _financial_profile(
    session: Session, *, project_id: int, reference_date: date
) -> tuple[tuple[date, ...], tuple[Decimal, ...]] | None:
    from src.modulos.planejamento import service as planejamento

    overview = planejamento.curva_fisica_overview(
        session, scope=Scope(project_id=project_id, source="url"), reference_date=reference_date
    )
    if not overview.is_empty:
        return overview.series.months, overview.series.baseline
    return planejamento.linear_curve_profile(
        session, project_id=project_id, reference_date=reference_date
    )


def _revision_total_cents(session: Session, *, revision: EacRevision) -> int:
    statement = select(EacRevisionItem.base_cents).where(EacRevisionItem.revision_id == revision.id)
    return sum(session.scalars(statement))


def financial_curve_overview(
    session: Session, *, scope: Scope, reference_date: date
) -> FinancialCurveOverview:
    """A Curva S financeira do escopo: a linha de base congelada da revisão vigente (HU-093).

    No projeto a curva é a da revisão vigente da EAC: o planejado congelado, o comprometido e o
    realizado acumulados dos fatos do ERP até o corte, a tendência calculada e a tabela período a
    período. No Portfólio os valores dos projetos somam em reais, no calendário da união dos
    meses; a tendência é a soma das linhas dos projetos. Sem curva congelada, a visão sai vazia.
    """
    projects = configuracoes.list_projects(session)
    if scope.is_portfolio:
        return _portfolio_financial_curve(session, projects=projects, reference_date=reference_date)
    project = _project_of(projects, scope)
    curve = _frozen_financial_curves(
        session, _current_financial_records(session, [project.id]), reference_date=reference_date
    ).get(project.id)
    if curve is None:
        return _empty_financial_curve(
            reference_date=reference_date, is_portfolio=False, scope_label=_label(project)
        )
    return FinancialCurveOverview(
        reference_date=reference_date,
        is_portfolio=False,
        scope_label=_label(project),
        project_id=project.id,
        revision=curve.revision,
        revision_date=curve.revision_date,
        series=curve.series,
        points=_financial_points(curve.series),
        kpis=_financial_kpis(curve.series, budget_cents=curve.budget_cents),
    )


def _portfolio_financial_curve(
    session: Session,
    *,
    projects: Sequence[configuracoes.ProjectSummary],
    reference_date: date,
) -> FinancialCurveOverview:
    curves = {
        project_id: curve
        for project_id, curve in _frozen_financial_curves(
            session,
            _current_financial_records(session, [project.id for project in projects]),
            reference_date=reference_date,
        ).items()
        if curve.series.months
    }
    if not curves:
        return _empty_financial_curve(
            reference_date=reference_date, is_portfolio=True, scope_label=PORTFOLIO_LABEL
        )
    series = _summed_financial_series(curves, reference_date=reference_date)
    return FinancialCurveOverview(
        reference_date=reference_date,
        is_portfolio=True,
        scope_label=PORTFOLIO_LABEL,
        project_id=None,
        revision=None,
        revision_date=None,
        series=series,
        points=_financial_points(series),
        kpis=_financial_kpis(
            series, budget_cents=sum(curve.budget_cents for curve in curves.values())
        ),
    )


def _summed_financial_series(
    curves: Mapping[int, _FrozenFinancialCurve], *, reference_date: date
) -> FinancialCurveSeries:
    """A curva da carteira: os meses na união dos projetos e a soma das quatro linhas.

    O comprometido e o realizado somam os projetos até o mês de corte mais novo; a tendência
    soma dali em diante. Um projeto sem o mês de outro não quebra a soma: antes do início vale
    zero e depois do seu fim vale o último acumulado, como a linha reta da carteira.
    """
    months = tuple(sorted({month for curve in curves.values() for month in curve.series.months}))
    cut_index = _cut_index(months, reference_date)
    cut_month = months[cut_index] if cut_index >= 0 else None
    return FinancialCurveSeries(
        months=months,
        cut_index=cut_index,
        planned=tuple(
            sum(
                _series_at(curve.series.months, curve.series.planned, month) or 0
                for curve in curves.values()
            )
            for month in months
        ),
        committed=tuple(
            None
            if cut_month is None or month > cut_month
            else _sum_optional(
                _series_at(curve.series.months, curve.series.committed, month)
                for curve in curves.values()
            )
            for month in months
        ),
        actual=tuple(
            None
            if cut_month is None or month > cut_month
            else _sum_optional(
                _series_at(curve.series.months, curve.series.actual, month)
                for curve in curves.values()
            )
            for month in months
        ),
        trend=tuple(
            None
            if cut_month is None or month < cut_month
            else _sum_optional(
                _series_at(curve.series.months, curve.series.trend, month)
                for curve in curves.values()
            )
            for month in months
        ),
    )


def _current_financial_records(
    session: Session, project_ids: Sequence[int]
) -> dict[int, _FinancialRecord]:
    """A curva congelada vigente de cada projeto: a da maior revisão da EAC."""
    if not project_ids:
        return {}
    curves = session.scalars(
        select(CurvaFinanceiraRevision).where(
            CurvaFinanceiraRevision.project_id.in_(sorted(set(project_ids)))
        )
    ).all()
    if not curves:
        return {}
    revisions = {
        revision.id: revision
        for revision in session.scalars(
            select(EacRevision).where(
                EacRevision.id.in_({curve.eac_revision_id for curve in curves})
            )
        )
    }
    latest: dict[int, CurvaFinanceiraRevision] = {}
    for curve in curves:
        revision = revisions.get(curve.eac_revision_id)
        if revision is None:
            continue
        current = latest.get(curve.project_id)
        if current is None or revision.revision > revisions[current.eac_revision_id].revision:
            latest[curve.project_id] = curve
    totals = _revision_totals(
        session, revision_ids=[curve.eac_revision_id for curve in latest.values()]
    )
    months: dict[int, list[CurvaFinanceiraMonth]] = {}
    for row in session.scalars(
        select(CurvaFinanceiraMonth)
        .where(CurvaFinanceiraMonth.revision_id.in_({curve.id for curve in latest.values()}))
        .order_by(CurvaFinanceiraMonth.revision_id, CurvaFinanceiraMonth.month)
    ):
        months.setdefault(row.revision_id, []).append(row)
    records: dict[int, _FinancialRecord] = {}
    for project_id, curve in latest.items():
        revision = revisions[curve.eac_revision_id]
        rows = months.get(curve.id, [])
        if not rows:
            continue
        records[project_id] = _FinancialRecord(
            project_id=project_id,
            revision=revision.revision,
            revision_date=revision.revision_date,
            total_cents=totals.get(curve.eac_revision_id, 0),
            months=tuple(row.month for row in rows),
            planned=tuple(row.planned_cents for row in rows),
        )
    return records


def _revision_totals(session: Session, *, revision_ids: Sequence[int]) -> dict[int, int]:
    if not revision_ids:
        return {}
    statement = (
        select(EacRevisionItem.revision_id, func.sum(EacRevisionItem.base_cents))
        .where(EacRevisionItem.revision_id.in_(sorted(set(revision_ids))))
        .group_by(EacRevisionItem.revision_id)
    )
    return {row[0]: int(row[1] or 0) for row in session.execute(statement)}


def _frozen_financial_curves(
    session: Session,
    records: Mapping[int, _FinancialRecord],
    *,
    reference_date: date,
) -> dict[int, _FrozenFinancialCurve]:
    if not records:
        return {}
    erp_months = _erp_months_by_project(session, project_ids=list(records))
    facts = _erp_facts_by_project(session, project_ids=list(records))
    curves: dict[int, _FrozenFinancialCurve] = {}
    for project_id, record in records.items():
        months = tuple(sorted({*record.months, *erp_months.get(project_id, ())}))
        if not months:
            continue
        planned = tuple(_planned_at(record, month) for month in months)
        points = calculations.curva_financeira_erp(
            facts.get(project_id, ()), months, cutoff=reference_date
        )
        committed = tuple(point.committed_cents for point in points)
        actual = tuple(point.actual_cents for point in points)
        cut_index = _cut_index(months, reference_date)
        physical = _curve_series(session, project_id=project_id, reference_date=reference_date)
        curves[project_id] = _FrozenFinancialCurve(
            project_id=project_id,
            revision=record.revision,
            revision_date=record.revision_date,
            budget_cents=record.total_cents,
            series=FinancialCurveSeries(
                months=months,
                cut_index=cut_index,
                planned=planned,
                committed=committed,
                actual=actual,
                trend=_curve_trend(
                    physical,
                    months,
                    planned,
                    actual,
                    cut_index,
                    budget_cents=record.total_cents,
                ),
            ),
            physical=physical,
        )
    return curves


def _erp_months_by_project(
    session: Session, *, project_ids: Sequence[int]
) -> dict[int, tuple[date, ...]]:
    statement = (
        select(ErpCost.project_id, ErpCost.month)
        .where(ErpCost.project_id.in_(sorted(set(project_ids))))
        .distinct()
        .order_by(ErpCost.project_id, ErpCost.month)
    )
    grouped: dict[int, list[date]] = {}
    for project_id, month in session.execute(statement):
        grouped.setdefault(project_id, []).append(month)
    return {project_id: tuple(months) for project_id, months in grouped.items()}


def _erp_facts_by_project(
    session: Session, *, project_ids: Sequence[int]
) -> dict[int, tuple[calculations.ErpCostFact, ...]]:
    statement = select(ErpCost).where(ErpCost.project_id.in_(sorted(set(project_ids))))
    grouped: dict[int, list[calculations.ErpCostFact]] = {}
    for row in session.scalars(statement):
        grouped.setdefault(row.project_id, []).append(
            calculations.ErpCostFact(
                item_id=row.item_id,
                month=row.month,
                committed_cents=row.committed_cents,
                actual_cents=row.actual_cents,
                projection_cents=row.projection_cents,
            )
        )
    return {project_id: tuple(facts) for project_id, facts in grouped.items()}


def _planned_at(record: _FinancialRecord, month: date) -> int:
    if not record.months:
        return 0
    if month in record.months:
        return record.planned[record.months.index(month)]
    if month < record.months[0]:
        return 0
    return record.planned[-1]


def _cut_index(months: Sequence[date], reference_date: date) -> int:
    cut_month = reference_date.replace(day=1)
    index = -1
    for position, month in enumerate(months):
        if month <= cut_month:
            index = position
    return index


def _series_at[T](months: Sequence[date], values: Sequence[T | None], month: date) -> T | None:
    """O valor acumulado da série num mês: antes do início, nada; depois do fim, o último."""
    if not months:
        return None
    if month < months[0]:
        return None
    if month > months[-1]:
        return next((value for value in reversed(values) if value is not None), None)
    return values[months.index(month)]


def _sum_optional(values: Iterable[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _curve_trend(
    physical: CurvaFisicaSeries,
    months: Sequence[date],
    planned: Sequence[int],
    actual: Sequence[int | None],
    cut_index: int,
    *,
    budget_cents: int,
) -> tuple[int | None, ...]:
    """A tendência da curva: EV do avanço físico no corte sobre o BAC da revisão vigente."""
    if cut_index < 0:
        return (None,) * len(months)
    physical_actual, _ = _physical_indicators(physical)
    value = calculations.value_aggregated_month(
        month=months[cut_index],
        bac_cents=budget_cents,
        physical_actual_pct=physical_actual,
        pv_cents=planned[cut_index],
        ac_cents=actual[cut_index],
    )
    ev_cents = value.ev_cents if value is not None else 0
    return calculations.curva_financeira_trend(
        planned, actual, cut_index, bac_cents=budget_cents, ev_cents=ev_cents
    )


def _financial_points(series: FinancialCurveSeries) -> tuple[FinancialCurvePoint, ...]:
    return tuple(
        FinancialCurvePoint(
            month=month,
            planned_cents=series.planned[index],
            committed_cents=series.committed[index],
            actual_cents=series.actual[index],
            trend_cents=series.trend[index],
            is_cut=index == series.cut_index,
        )
        for index, month in enumerate(series.months)
    )


def _financial_kpis(
    series: FinancialCurveSeries, *, budget_cents: int
) -> FinancialCurveKpis | None:
    if series.cut_index < 0:
        return None
    index = series.cut_index
    planned = series.planned[index]
    committed = series.committed[index]
    actual = series.actual[index]
    trend = next((value for value in reversed(series.trend) if value is not None), None)
    return FinancialCurveKpis(
        budget_cents=budget_cents,
        planned_cents=planned,
        committed_cents=committed,
        actual_cents=actual,
        trend_cents=trend,
        deviation_cents=None if actual is None else actual - planned,
        committed_pct=(
            None if committed is None else calculations.committed_percent(committed, budget_cents)
        ),
    )


def _empty_financial_curve(
    *, reference_date: date, is_portfolio: bool, scope_label: str
) -> FinancialCurveOverview:
    empty = FinancialCurveSeries(
        months=(), cut_index=-1, planned=(), committed=(), actual=(), trend=()
    )
    return FinancialCurveOverview(
        reference_date=reference_date,
        is_portfolio=is_portfolio,
        scope_label=scope_label,
        project_id=None,
        revision=None,
        revision_date=None,
        series=empty,
        points=(),
        kpis=None,
    )


def cost_kpis_overview(session: Session, *, scope: Scope, reference_date: date) -> CostKpisOverview:
    """Os KPIs de custo do escopo: CPI, SPI, CV, VAC, contingência e comprometido (HU-092).

    O EV é o avanço físico real sobre o BAC, o PV a linha de base e o AC o realizado acumulado do
    ERP; a série mês a mês acumula os índices até cada mês e a variação compara o corte com o mês
    anterior. No Portfólio o PV, o EV e o AC somam os projetos e o CPI e o SPI saem da soma. Sem
    EAC ou sem curva congelada, a visão sai vazia.
    """
    projects = configuracoes.list_projects(session)
    if scope.is_portfolio:
        return _portfolio_cost_kpis(session, projects=projects, reference_date=reference_date)
    project = _project_of(projects, scope)
    return _project_cost_kpis(session, project=project, reference_date=reference_date)


def _project_cost_kpis(
    session: Session,
    *,
    project: configuracoes.ProjectSummary,
    reference_date: date,
) -> CostKpisOverview:
    curve = _frozen_financial_curves(
        session, _current_financial_records(session, [project.id]), reference_date=reference_date
    ).get(project.id)
    if curve is None or not curve.physical.months:
        return _empty_cost_kpis(
            reference_date=reference_date, is_portfolio=False, scope_label=_label(project)
        )
    history = _value_history(curve)
    cut_value = _value_at_cut(curve)
    actual = None if cut_value is None else _cost_kpi_month(cut_value, bac_cents=curve.budget_cents)
    indicators = (
        None
        if actual is None
        else calculations.cost_indicators(
            bac_cents=curve.budget_cents,
            ev_cents=actual.ev_cents,
            pv_cents=actual.pv_cents,
            ac_cents=actual.ac_cents,
        )
    )
    projection = _project_projection_cents(session, project_id=project.id)
    committed = _committed_at_cut(curve)
    contingency = contingency_consumption(session, scope=Scope(project_id=project.id, source="url"))
    return CostKpisOverview(
        reference_date=reference_date,
        is_portfolio=False,
        scope_label=_label(project),
        project_id=project.id,
        cut_month=_curve_cut_month(curve),
        budget_cents=curve.budget_cents,
        indicators=indicators,
        projection_cents=projection,
        vac_cents=(
            None
            if projection is None
            else calculations.estimate_variance(curve.budget_cents, projection)
        ),
        committed_cents=committed,
        committed_pct=(
            None
            if committed is None
            else calculations.committed_percent(committed, curve.budget_cents)
        ),
        contingency_total_cents=contingency.total_cents if contingency is not None else 0,
        contingency_consumed_cents=(contingency.consumed_cents if contingency is not None else 0),
        contingency_pct=(
            None
            if contingency is None
            else calculations.reserve_consumption_pct(
                contingency.consumed_cents, contingency.total_cents
            )
        ),
        actual=actual,
        previous=_previous_of(history, _curve_cut_month(curve)),
        history=history,
    )


def _portfolio_cost_kpis(
    session: Session,
    *,
    projects: Sequence[configuracoes.ProjectSummary],
    reference_date: date,
) -> CostKpisOverview:
    curves = {
        project_id: curve
        for project_id, curve in _frozen_financial_curves(
            session,
            _current_financial_records(session, [project.id for project in projects]),
            reference_date=reference_date,
        ).items()
        if curve.physical.months and curve.series.months
    }
    if not curves:
        return _empty_cost_kpis(
            reference_date=reference_date, is_portfolio=True, scope_label=PORTFOLIO_LABEL
        )
    budget = sum(curve.budget_cents for curve in curves.values())
    months = tuple(sorted({month for curve in curves.values() for month in curve.series.months}))
    cut_index = _cut_index(months, reference_date)
    cut_month = months[cut_index] if cut_index >= 0 else None
    history = _portfolio_value_history(curves, months, cut_month, bac_cents=budget)
    actual = next((row for row in history if row.month == cut_month), None)
    indicators = (
        None
        if actual is None
        else calculations.cost_indicators(
            bac_cents=budget,
            ev_cents=actual.ev_cents,
            pv_cents=actual.pv_cents,
            ac_cents=actual.ac_cents,
        )
    )
    projection = _portfolio_projection_cents(session, project_ids=list(curves))
    committed = _portfolio_committed(curves, cut_month)
    contingency = contingency_consumption(session, scope=Scope(project_id=None, source="url"))
    by_id = {project.id: project for project in projects}
    return CostKpisOverview(
        reference_date=reference_date,
        is_portfolio=True,
        scope_label=PORTFOLIO_LABEL,
        project_id=None,
        cut_month=cut_month,
        budget_cents=budget,
        indicators=indicators,
        projection_cents=projection,
        vac_cents=None
        if projection is None
        else calculations.estimate_variance(budget, projection),
        committed_cents=committed,
        committed_pct=(
            None if committed is None else calculations.committed_percent(committed, budget)
        ),
        contingency_total_cents=contingency.total_cents if contingency is not None else 0,
        contingency_consumed_cents=(contingency.consumed_cents if contingency is not None else 0),
        contingency_pct=(
            None
            if contingency is None
            else calculations.reserve_consumption_pct(
                contingency.consumed_cents, contingency.total_cents
            )
        ),
        actual=actual,
        previous=_previous_of(history, cut_month),
        history=history,
        projects=tuple(
            _cost_kpi_project_row(session, curves[project_id], project=by_id.get(project_id))
            for project_id in sorted(curves)
        ),
    )


def _cost_kpi_project_row(
    session: Session,
    curve: _FrozenFinancialCurve,
    *,
    project: configuracoes.ProjectSummary | None,
) -> CostKpiProjectRow:
    cut_value = _value_at_cut(curve)
    projection = _project_projection_cents(session, project_id=curve.project_id)
    contingency = contingency_consumption(
        session, scope=Scope(project_id=curve.project_id, source="url")
    )
    return CostKpiProjectRow(
        project_id=curve.project_id,
        project_code=project.code if project is not None else "",
        project_label=_label(project) if project is not None else "",
        bac_cents=curve.budget_cents,
        ev_cents=cut_value.ev_cents if cut_value is not None else 0,
        ac_cents=cut_value.ac_cents if cut_value is not None else 0,
        cpi=cut_value.cpi if cut_value is not None else None,
        spi=cut_value.spi if cut_value is not None else None,
        projection_cents=projection,
        vac_cents=(
            None
            if projection is None
            else calculations.estimate_variance(curve.budget_cents, projection)
        ),
        contingency_pct=(
            None
            if contingency is None
            else calculations.reserve_consumption_pct(
                contingency.consumed_cents, contingency.total_cents
            )
        ),
    )


def _value_history(curve: _FrozenFinancialCurve) -> tuple[CostKpiMonth, ...]:
    rows: list[CostKpiMonth] = []
    for month in curve.series.months:
        value = _project_value_at(curve, month)
        if value is None:
            continue
        rows.append(_cost_kpi_month(value, bac_cents=curve.budget_cents))
    return tuple(rows)


def _portfolio_value_history(
    curves: Mapping[int, _FrozenFinancialCurve],
    months: Sequence[date],
    cut_month: date | None,
    *,
    bac_cents: int,
) -> tuple[CostKpiMonth, ...]:
    if cut_month is None:
        return ()
    rows: list[CostKpiMonth] = []
    for month in months:
        if month > cut_month:
            break
        values = [
            value
            for curve in curves.values()
            if (value := _project_value_at(curve, month)) is not None
        ]
        if not values:
            continue
        rows.append(_sum_cost_kpi_month(values, month=month, bac_cents=bac_cents))
    return tuple(rows)


def _project_value_at(
    curve: _FrozenFinancialCurve, month: date
) -> calculations.ValueAggregatedMonth | None:
    physical = _physical_at(curve.physical, month)
    if physical is None:
        return None
    return calculations.value_aggregated_month(
        month=month,
        bac_cents=curve.budget_cents,
        physical_actual_pct=physical,
        pv_cents=_series_at(curve.series.months, curve.series.planned, month) or 0,
        ac_cents=_series_at(curve.series.months, curve.series.actual, month),
    )


def _physical_at(physical: CurvaFisicaSeries, month: date) -> Decimal | None:
    if month not in physical.months:
        return None
    return physical.real[physical.months.index(month)]


def _value_at_cut(curve: _FrozenFinancialCurve) -> calculations.ValueAggregatedMonth | None:
    cut_month = _curve_cut_month(curve)
    return None if cut_month is None else _project_value_at(curve, cut_month)


def _curve_cut_month(curve: _FrozenFinancialCurve) -> date | None:
    if curve.series.cut_index < 0:
        return None
    return curve.series.months[curve.series.cut_index]


def _cost_kpi_month(value: calculations.ValueAggregatedMonth, *, bac_cents: int) -> CostKpiMonth:
    return CostKpiMonth(
        month=value.month,
        pv_cents=value.pv_cents,
        ev_cents=value.ev_cents,
        ac_cents=value.ac_cents,
        cv_cents=value.cv_cents,
        sv_cents=value.sv_cents,
        cpi=value.cpi,
        spi=value.spi,
        eac_by_cpi_cents=calculations.estimate_at_completion_by_cpi(
            bac_cents, value.ev_cents, value.ac_cents
        ),
        tcpi=calculations.to_complete_performance_index(bac_cents, value.ev_cents, value.ac_cents),
    )


def _sum_cost_kpi_month(
    values: Sequence[calculations.ValueAggregatedMonth], *, month: date, bac_cents: int
) -> CostKpiMonth:
    ev_cents = sum(value.ev_cents for value in values)
    pv_cents = sum(value.pv_cents for value in values)
    ac_cents = sum(value.ac_cents for value in values)
    return CostKpiMonth(
        month=month,
        pv_cents=pv_cents,
        ev_cents=ev_cents,
        ac_cents=ac_cents,
        cv_cents=calculations.cost_variance(ev_cents, ac_cents),
        sv_cents=calculations.schedule_variance(ev_cents, pv_cents),
        cpi=calculations.cost_performance_index(ev_cents, ac_cents),
        spi=calculations.cost_schedule_index(ev_cents, pv_cents),
        eac_by_cpi_cents=calculations.estimate_at_completion_by_cpi(bac_cents, ev_cents, ac_cents),
        tcpi=calculations.to_complete_performance_index(bac_cents, ev_cents, ac_cents),
    )


def _previous_of(history: Sequence[CostKpiMonth], cut_month: date | None) -> CostKpiMonth | None:
    if cut_month is None:
        return None
    previous_month = (cut_month - timedelta(days=1)).replace(day=1)
    return next((row for row in history if row.month == previous_month), None)


def _committed_at_cut(curve: _FrozenFinancialCurve) -> int | None:
    cut_month = _curve_cut_month(curve)
    if cut_month is None:
        return None
    return _series_at(curve.series.months, curve.series.committed, cut_month)


def _portfolio_committed(
    curves: Mapping[int, _FrozenFinancialCurve], cut_month: date | None
) -> int | None:
    if cut_month is None:
        return None
    return _sum_optional(_committed_at_cut(curve) for curve in curves.values())


def _project_projection_cents(session: Session, *, project_id: int) -> int | None:
    items = _lines_by_project(session, [project_id]).get(project_id, [])
    if not items:
        return None
    projected = calculations.projected_total_cents(
        items,
        current_bases=_current_bases(session, project_id=project_id, items=items),
        facts=_projection_facts(session, item_ids=[item.id for item in items]),
    )
    return projected.total_cents


def _portfolio_projection_cents(session: Session, *, project_ids: Sequence[int]) -> int | None:
    projections = [
        projection
        for project_id in project_ids
        if (projection := _project_projection_cents(session, project_id=project_id)) is not None
    ]
    return sum(projections) if projections else None


def _empty_cost_kpis(
    *, reference_date: date, is_portfolio: bool, scope_label: str
) -> CostKpisOverview:
    return CostKpisOverview(
        reference_date=reference_date,
        is_portfolio=is_portfolio,
        scope_label=scope_label,
        project_id=None,
        cut_month=None,
        budget_cents=0,
        indicators=None,
        projection_cents=None,
        vac_cents=None,
        committed_cents=None,
        committed_pct=None,
        contingency_total_cents=0,
        contingency_consumed_cents=0,
        contingency_pct=None,
        actual=None,
        previous=None,
        history=(),
    )


# ── Cronograma de desembolso (ISSUE-043) ─────────────────────────────────

TREASURY_EMAIL = "tesouraria@exemplo.com"
TREASURY_SUBJECT = "Cronograma de desembolso de {month} em diante"
TREASURY_BODY = (
    "Cronograma de desembolso atualizado com o fechamento de {cut}. Saldo a desembolsar: {balance}."
)
NO_DISBURSEMENT_MESSAGE = "O projeto não tem cronograma de desembolso para enviar."
MONTH_NAMES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


@dataclass(frozen=True)
class DisbursementItem:
    """Uma linha da tabela item x mês: o saldo a pagar e a distribuição pelos meses futuros."""

    code: str
    description: str
    level: int
    project_id: int
    project_label: str
    balance_cents: int
    amounts: tuple[int, ...]


@dataclass(frozen=True)
class DisbursementKpis:
    """Os KPIs do topo do cronograma, como o protótipo os mostra."""

    actual_until_cut_cents: int
    planned_until_cut_cents: int
    balance_cents: int
    planned_balance_cents: int
    next_three_cents: int
    planned_next_three_cents: int
    cut_actual_cents: int | None
    cut_planned_cents: int | None
    projection_cents: int
    actual_pct: Decimal | None
    peak_month: date | None


@dataclass(frozen=True)
class DisbursementOverview:
    """O cronograma de desembolso do escopo: o histograma, a tabela item x mês e os KPIs."""

    reference_date: date
    is_portfolio: bool
    scope_label: str
    project_id: int | None
    cut_index: int
    months: tuple[date, ...]
    histogram: tuple[calculations.DisbursementMonth, ...]
    items: tuple[DisbursementItem, ...]
    totals: tuple[int, ...]
    balance_cents: int
    projection_cents: int
    actual_until_cut_cents: int
    kpis: DisbursementKpis | None

    @property
    def cut_month(self) -> date | None:
        """O mês do corte, ou ``None`` quando a data de referência antecede a curva."""
        return self.months[self.cut_index] if 0 <= self.cut_index < len(self.months) else None

    @property
    def future_months(self) -> tuple[date, ...]:
        """Os meses depois do corte: as colunas da tabela item x mês."""
        return self.months[self.cut_index + 1 :]

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no financial curve: the empty state of origin."""
        return not self.months


@dataclass(frozen=True)
class _ProjectAmounts:
    """O que a distribuição lê de um projeto: o saldo a pagar por item e a projeção no término."""

    balances_by_item: Mapping[int, int]
    projection_cents: int


@dataclass(frozen=True)
class _ProjectDisbursement:
    """Um projeto pronto para o cronograma: a curva, os itens, os saldos e os marcos."""

    project: configuracoes.ProjectSummary
    curve: _FrozenFinancialCurve
    items: tuple[ItemLine, ...]
    amounts: _ProjectAmounts
    milestones: Mapping[int, tuple[calculations.PaymentMilestone, ...]]


def disbursement_overview(
    session: Session, *, scope: Scope, reference_date: date
) -> DisbursementOverview:
    """O cronograma de desembolso do escopo: o saldo a pagar distribuído pelos meses (HU-091).

    No projeto, cada item da EAC tem o saldo a pagar (a projeção no término menos o realizado do
    ERP) distribuído pelos marcos futuros dos contratos do item e, no que sobrar, pelo perfil da
    projeção; a soma dos meses futuros de cada item é o seu saldo. O histograma mensal mostra o
    previsto da linha de base, o realizado dos fatos do ERP até o corte e o projetado distribuído.
    Na carteira os meses são a união dos meses dos projetos e os valores somam por mês, com uma
    linha por projeto e os seus pacotes. Sem curva financeira congelada, a visão sai vazia.
    """
    projects = configuracoes.list_projects(session)
    if scope.is_portfolio:
        return _portfolio_disbursement(session, projects=projects, reference_date=reference_date)
    project = _project_of(projects, scope)
    return _project_disbursement(session, project=project, reference_date=reference_date)


def _project_disbursement(
    session: Session, *, project: configuracoes.ProjectSummary, reference_date: date
) -> DisbursementOverview:
    parts = _project_parts(session, projects=(project,), reference_date=reference_date)
    if not parts:
        return _empty_disbursement(
            reference_date=reference_date, is_portfolio=False, scope_label=_label(project)
        )
    part = parts[0]
    label = _label(project)
    future = part.curve.series.months[part.curve.series.cut_index + 1 :]
    amounts = _distribute_items(
        part.items,
        balances=part.amounts.balances_by_item,
        months=future,
        profile=_disbursement_profile(part.curve),
        milestones=part.milestones,
    )
    totals = _level_one_totals(part.items, amounts)
    balance = _level_one_sum(part.items, part.amounts.balances_by_item)
    actual_until_cut = _actual_until_cut(part.curve.series)
    histogram = calculations.disbursement_histogram(
        part.curve.series.months,
        planned_cumulative=part.curve.series.planned,
        actual_cumulative=part.curve.series.actual,
        projected_cumulative=part.curve.series.trend,
        cut_index=part.curve.series.cut_index,
    )
    return DisbursementOverview(
        reference_date=reference_date,
        is_portfolio=False,
        scope_label=label,
        project_id=project.id,
        cut_index=part.curve.series.cut_index,
        months=part.curve.series.months,
        histogram=histogram,
        items=_item_rows(
            part.items,
            balances=part.amounts.balances_by_item,
            amounts=amounts,
            project=project,
            label=label,
        ),
        totals=totals,
        balance_cents=balance,
        projection_cents=part.amounts.projection_cents,
        actual_until_cut_cents=actual_until_cut,
        kpis=_disbursement_kpis(
            histogram=histogram,
            cut_index=part.curve.series.cut_index,
            future=future,
            totals=totals,
            balance_cents=balance,
            projection_cents=part.amounts.projection_cents,
            actual_until_cut_cents=actual_until_cut,
        ),
    )


def _portfolio_disbursement(
    session: Session,
    *,
    projects: Sequence[configuracoes.ProjectSummary],
    reference_date: date,
) -> DisbursementOverview:
    parts = _project_parts(session, projects=projects, reference_date=reference_date)
    if not parts:
        return _empty_disbursement(
            reference_date=reference_date, is_portfolio=True, scope_label=PORTFOLIO_LABEL
        )
    series = _summed_financial_series(
        {part.project.id: part.curve for part in parts}, reference_date=reference_date
    )
    future = series.months[series.cut_index + 1 :]
    rows: list[DisbursementItem] = []
    totals = [0] * len(future)
    balance = 0
    projection = 0
    for number, part in enumerate(parts, start=1):
        label = _label(part.project)
        amounts = _distribute_items(
            part.items,
            balances=part.amounts.balances_by_item,
            months=future,
            profile=_disbursement_profile(part.curve),
            milestones=part.milestones,
        )
        level_one = [item for item in part.items if item.level == 1]
        part_totals = tuple(
            sum(amounts[item.id][index] for item in level_one) for index in range(len(future))
        )
        part_balance = _level_one_sum(part.items, part.amounts.balances_by_item)
        rows.append(
            DisbursementItem(
                code=str(number),
                description=label,
                level=1,
                project_id=part.project.id,
                project_label=label,
                balance_cents=part_balance,
                amounts=part_totals,
            )
        )
        for item in sorted(level_one, key=lambda item: calculations.code_key(item.code)):
            rows.append(
                DisbursementItem(
                    code=f"{number}.{item.code}",
                    description=item.description,
                    level=2,
                    project_id=part.project.id,
                    project_label=label,
                    balance_cents=part.amounts.balances_by_item.get(item.id, 0),
                    amounts=amounts[item.id],
                )
            )
        totals = [total + value for total, value in zip(totals, part_totals, strict=True)]
        balance += part_balance
        projection += part.amounts.projection_cents
    actual_until_cut = _actual_until_cut(series)
    histogram = calculations.disbursement_histogram(
        series.months,
        planned_cumulative=series.planned,
        actual_cumulative=series.actual,
        projected_cumulative=series.trend,
        cut_index=series.cut_index,
    )
    return DisbursementOverview(
        reference_date=reference_date,
        is_portfolio=True,
        scope_label=PORTFOLIO_LABEL,
        project_id=None,
        cut_index=series.cut_index,
        months=series.months,
        histogram=histogram,
        items=tuple(rows),
        totals=tuple(totals),
        balance_cents=balance,
        projection_cents=projection,
        actual_until_cut_cents=actual_until_cut,
        kpis=_disbursement_kpis(
            histogram=histogram,
            cut_index=series.cut_index,
            future=future,
            totals=totals,
            balance_cents=balance,
            projection_cents=projection,
            actual_until_cut_cents=actual_until_cut,
        ),
    )


def _project_parts(
    session: Session, *, projects: Sequence[configuracoes.ProjectSummary], reference_date: date
) -> tuple[_ProjectDisbursement, ...]:
    """Os projetos com curva congelada e itens, prontos para o cronograma; sem curva, fora."""
    curves = _frozen_financial_curves(
        session,
        _current_financial_records(session, [project.id for project in projects]),
        reference_date=reference_date,
    )
    lines = _lines_by_project(session, [project.id for project in projects])
    parts: list[_ProjectDisbursement] = []
    for project in projects:
        curve = curves.get(project.id)
        items = tuple(lines.get(project.id, ()))
        if curve is None or not curve.series.months or not items:
            continue
        parts.append(
            _ProjectDisbursement(
                project=project,
                curve=curve,
                items=items,
                amounts=_project_amounts(
                    session, project_id=project.id, items=items, reference_date=reference_date
                ),
                milestones=_milestones_by_item(
                    session,
                    project_id=project.id,
                    item_ids=[item.id for item in items],
                    reference_date=reference_date,
                ),
            )
        )
    return tuple(parts)


def _project_amounts(
    session: Session, *, project_id: int, items: Sequence[ItemLine], reference_date: date
) -> _ProjectAmounts:
    """O saldo a pagar de cada item: a projeção no término menos o realizado, nunca negativo.

    A projeção de um item é a vigente do fato mais recente, com os pacotes somando os filhos; o
    realizado soma os fatos do ERP até a data de corte e sobe pelos pacotes, como no mapa de
    controle.
    """
    item_ids = [item.id for item in items]
    projected = calculations.projected_total_cents(
        items,
        current_bases=_current_bases(session, project_id=project_id, items=items),
        facts=_projection_facts(session, item_ids=item_ids),
    )
    erp = _erp_totals(session, item_ids=item_ids, cutoff=reference_date)
    actual = _leveled_totals(
        items, {item_id: totals.actual_cents for item_id, totals in erp.items()}
    )
    return _ProjectAmounts(
        balances_by_item={
            item.id: max(0, projected.by_item.get(item.id, 0) - actual.get(item.id, 0))
            for item in items
        },
        projection_cents=projected.total_cents,
    )


def _milestones_by_item(
    session: Session, *, project_id: int, item_ids: Sequence[int], reference_date: date
) -> dict[int, tuple[calculations.PaymentMilestone, ...]]:
    """Os marcos futuros dos contratos de cada item da EAC, com o valor do percentual.

    Marco elegível é o de data depois da data de referência e valor positivo; o passado e o sem
    valor não entram, e o que sobrar do saldo segue o perfil. Contrato sem item da EAC não
    alimenta o cronograma.
    """
    wanted = set(item_ids)
    grouped: dict[int, list[calculations.PaymentMilestone]] = {}
    for contract in _project_contracts(session, project_id=project_id):
        if contract.eac_item_id is None or contract.eac_item_id not in wanted:
            continue
        addenda = _addendum_lines(_addendum_rows(session, contract_id=contract.id))
        current = calculations.contract_current_value_cents(contract.original_value_cents, addenda)
        for row in _milestone_rows(session, contract_id=contract.id):
            if row.expected_on <= reference_date:
                continue
            value = calculations.milestone_value_cents(current, row.pct)
            if value > 0:
                grouped.setdefault(contract.eac_item_id, []).append(
                    calculations.PaymentMilestone(
                        month=row.expected_on.replace(day=1), value_cents=value
                    )
                )
    return {item_id: tuple(rows) for item_id, rows in grouped.items()}


def _disbursement_profile(curve: _FrozenFinancialCurve) -> Mapping[date, int]:
    """O perfil mensal da projeção, que recebe o que sobra do saldo depois dos marcos.

    O protótipo distribui o saldo pelo perfil da projeção no término; no servidor o perfil é a
    variação mensal da tendência da curva financeira (a projeção distribuída nos meses), com a
    variação do planejado como reserva. Sem os dois, o saldo fecha no último mês.
    """
    trend = calculations.monthly_amounts(curve.series.trend)
    profile = {month: max(0, trend[index] or 0) for index, month in enumerate(curve.series.months)}
    if any(profile.values()):
        return profile
    planned = calculations.monthly_amounts(curve.series.planned)
    return {month: max(0, planned[index] or 0) for index, month in enumerate(curve.series.months)}


def _distribute_items(
    items: Sequence[ItemLine],
    *,
    balances: Mapping[int, int],
    months: Sequence[date],
    profile: Mapping[date, int],
    milestones: Mapping[int, tuple[calculations.PaymentMilestone, ...]],
) -> dict[int, tuple[int, ...]]:
    weights = tuple(profile.get(month, 0) for month in months)
    return {
        item.id: calculations.distribute_balance(
            balances.get(item.id, 0), months, weights, milestones.get(item.id, ())
        )
        for item in items
    }


def _item_rows(
    items: Sequence[ItemLine],
    *,
    balances: Mapping[int, int],
    amounts: Mapping[int, tuple[int, ...]],
    project: configuracoes.ProjectSummary,
    label: str,
) -> tuple[DisbursementItem, ...]:
    return tuple(
        DisbursementItem(
            code=item.code,
            description=item.description,
            level=item.level,
            project_id=project.id,
            project_label=label,
            balance_cents=balances.get(item.id, 0),
            amounts=amounts.get(item.id, ()),
        )
        for item in sorted(items, key=lambda item: calculations.code_key(item.code))
    )


def _level_one_totals(
    items: Sequence[ItemLine], amounts: Mapping[int, tuple[int, ...]]
) -> tuple[int, ...]:
    if not amounts:
        return ()
    length = len(next(iter(amounts.values())))
    return tuple(
        sum(amounts.get(item.id, (0,) * length)[index] for item in items if item.level == 1)
        for index in range(length)
    )


def _level_one_sum(items: Sequence[ItemLine], balances: Mapping[int, int]) -> int:
    return sum(balances.get(item.id, 0) for item in items if item.level == 1)


def _actual_until_cut(series: FinancialCurveSeries) -> int:
    if series.cut_index < 0:
        return 0
    return series.actual[series.cut_index] or 0


def _disbursement_kpis(
    *,
    histogram: Sequence[calculations.DisbursementMonth],
    cut_index: int,
    future: Sequence[date],
    totals: Sequence[int],
    balance_cents: int,
    projection_cents: int,
    actual_until_cut_cents: int,
) -> DisbursementKpis | None:
    """Os KPIs do topo: o realizado no corte, o saldo, os três meses seguintes e o pico."""
    if not histogram:
        return None
    cut_row = histogram[cut_index] if 0 <= cut_index < len(histogram) else None
    future_rows = histogram[cut_index + 1 :]
    until_cut = histogram[: cut_index + 1] if cut_index >= 0 else []
    peak_index = max(range(len(totals)), key=lambda index: totals[index]) if totals else None
    return DisbursementKpis(
        actual_until_cut_cents=actual_until_cut_cents,
        planned_until_cut_cents=sum(row.planned_cents or 0 for row in until_cut),
        balance_cents=balance_cents,
        planned_balance_cents=sum(row.planned_cents or 0 for row in future_rows),
        next_three_cents=sum(totals[:3]),
        planned_next_three_cents=sum(row.planned_cents or 0 for row in future_rows[:3]),
        cut_actual_cents=cut_row.actual_cents if cut_row is not None else None,
        cut_planned_cents=cut_row.planned_cents if cut_row is not None else None,
        projection_cents=projection_cents,
        actual_pct=calculations.share_percent(actual_until_cut_cents, projection_cents),
        peak_month=future[peak_index] if peak_index is not None else None,
    )


def _empty_disbursement(
    *, reference_date: date, is_portfolio: bool, scope_label: str
) -> DisbursementOverview:
    return DisbursementOverview(
        reference_date=reference_date,
        is_portfolio=is_portfolio,
        scope_label=scope_label,
        project_id=None,
        cut_index=-1,
        months=(),
        histogram=(),
        items=(),
        totals=(),
        balance_cents=0,
        projection_cents=0,
        actual_until_cut_cents=0,
        kpis=None,
    )


def treasury_sendable_project(scope: Scope, overview: DisbursementOverview) -> int:
    """O projeto do envio à tesouraria, recusando o escopo sem projeto e o sem cronograma."""
    project_id = scope.require_project()
    if overview.is_empty or overview.cut_month is None or not overview.future_months:
        raise InvalidDataError(NO_DISBURSEMENT_MESSAGE)
    return project_id


def treasury_default_message(overview: DisbursementOverview) -> str:
    """A mensagem do protótipo, com o mês do fechamento e o saldo a desembolsar."""
    if overview.cut_month is None:
        return ""
    return TREASURY_BODY.format(
        cut=_short_month(overview.cut_month), balance=format_brl(overview.balance_cents)
    )


def send_to_treasury(
    session: Session,
    *,
    user: User,
    scope: Scope,
    reference_date: date,
    recipient: str | None = None,
    message: str | None = None,
    channel: NotificationChannel | None = None,
) -> notification.NotificationOutcome:
    """Envia o cronograma de desembolso à tesouraria pela porta de notificação (HU-091).

    O destinatário e a mensagem vêm do formulário da tela; sem eles valem os do protótipo — a
    tesouraria e o corpo com o mês do fechamento e o saldo a desembolsar. O assunto diz de que
    mês em diante o cronograma vai. Só o perfil com escrita envia, e o envio pertence a um
    projeto: no Portfólio a visão consolidada não é registro de um projeto. O registro e a linha
    da trilha entram na transação do chamador; desligado, tudo fica como ``simulado``.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    overview = disbursement_overview(session, scope=scope, reference_date=reference_date)
    project_id = treasury_sendable_project(scope, overview)
    return notification.send(
        session,
        user_id=user.id,
        request=NotificationRequest(
            kind=notification.TREASURY,
            project_id=project_id,
            recipients=[recipient or TREASURY_EMAIL],
            subject=TREASURY_SUBJECT.format(month=_short_month(overview.future_months[0])),
            body=message or treasury_default_message(overview),
        ),
        channel=channel,
    )


def _short_month(month: date) -> str:
    """O mês no formato curto do protótipo: ``set/26``."""
    return f"{MONTH_NAMES[month.month - 1]}/{month.year % 100:02d}"


attachment_origins.register(
    attachment_origins.OriginType(table=ATTACHMENT_TABLE, module=MODULE, read=read_contract_origin)
)
attachment_origins.register(
    attachment_origins.OriginType(
        table=MILESTONE_ATTACHMENT_TABLE, module=MODULE, read=read_milestone_origin
    )
)
attachment_origins.register(
    attachment_origins.OriginType(
        table=CLAIM_ATTACHMENT_TABLE, module=MODULE, read=read_claim_origin
    )
)
attachment_origins.register(
    attachment_origins.OriginType(
        table=EVALUATION_ATTACHMENT_TABLE, module=MODULE, read=read_evaluation_origin
    )
)
_register_lesson_origin()
