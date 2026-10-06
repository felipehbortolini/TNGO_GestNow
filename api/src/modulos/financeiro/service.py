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
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit, calendario, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry
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
from src.modulos.financeiro.models import EacItem

MODULE = "financeiro"
REGISTRY_ENTITY = "eac_item.cadastro"
PORTFOLIO_LABEL = "Portfólio"
PORTFOLIO_ROOT_DESCRIPTION = "Portfólio de projetos"

PORTFOLIO_READ_ONLY_MESSAGE = (
    "A EAC do Portfólio é somente leitura. Abra o projeto para editar um item."
)
OTHER_PROJECT_MESSAGE = "O item pertence a outro projeto. Abra o projeto dele para editar."
NOT_FOUND_MESSAGE = "Item da EAC não encontrado."
UNKNOWN_PROJECT_MESSAGE = "O projeto escolhido não existe."
ONLY_ITEMS_MESSAGE = "Só os itens de custo (nível 3) têm cadastro editável."

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
    """The items of the projects, with the names of the unit and the responsible resolved."""
    if not project_ids:
        return {}
    people = {person.id: person.name for person in configuracoes.list_people(session)}
    units = {unit.id: unit.code for unit in configuracoes.list_measure_units(session)}
    statement = select(EacItem).where(EacItem.project_id.in_(project_ids)).order_by(EacItem.id)
    grouped: dict[int, list[ItemLine]] = {}
    for item in session.scalars(statement):
        grouped.setdefault(item.project_id, []).append(
            ItemLine(
                id=item.id,
                parent_id=item.parent_id,
                code=item.code,
                description=item.description,
                level=item.level,
                cost_type=item.cost_type,
                unit=units.get(item.unit_id) if item.unit_id else None,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                capex=item.capex,
                cost_center=item.cost_center,
                responsible=people.get(item.responsible_id) if item.responsible_id else None,
                version=item.version,
            )
        )
    return grouped


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
