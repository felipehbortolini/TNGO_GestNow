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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import audit, calendario, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry
from src.core.money import format_brl
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
    EacItem,
    EacReallocation,
    EacRevision,
    EacRevisionItem,
)

if TYPE_CHECKING:
    from src.modulos.governanca.service import ProposedTransfer

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
