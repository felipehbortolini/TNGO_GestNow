"""Pure calculations of the Financeiro module (D6).

Every rule is one function, named after the business term in ``LEIA-ME.md``; nothing here reads
the clock, the database or the request. Money is integer cents (D5).
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from src.core.import_values import normalize_text

LEAF_LEVEL = 3
PORTFOLIO_MAIN_LEVEL = 2
WEIGHT_TOTAL = Decimal(100)
HUNDREDTHS = Decimal(100)
TWO_PLACES = Decimal("0.01")
BUDGET_SOURCE = "orcamento"
EQUAL_SHARE_FALLBACK = Decimal(1)
CODE_SEPARATOR = "."
ROOT_CODE = "0"


# ── Valor orçado ─────────────────────────────────────────────────────────


def budgeted_cents(quantity: Decimal | None, unit_price_cents: int | None) -> int:
    """Valor orçado: quantidade x preço unitário, in whole cents, half a cent rounding up."""
    if quantity is None or unit_price_cents is None:
        return 0
    return int((quantity * unit_price_cents).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def code_key(code: str) -> tuple[int, ...]:
    """The sort key of a code: ``1.10`` comes after ``1.2``, as the numbers say."""
    return tuple(int(part) if part.isdigit() else 0 for part in code.split(CODE_SEPARATOR))


# ── Árvore da EAC ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ItemLine:
    """An item of the breakdown as the tree needs it, with the names already resolved."""

    id: int
    parent_id: int | None
    code: str
    description: str
    level: int
    cost_type: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    unit_price_cents: int | None = None
    capex: bool | None = None
    cost_center: str | None = None
    responsible: str | None = None
    version: int = 1


@dataclass(frozen=True)
class TreeRow:
    """A line of the tree: what the table, the Excel and the printable version print.

    ``level`` is 0 for the root line (the project, or the portfolio), 1 to 3 for package,
    subpackage and item. In the Portfólio the levels mean portfolio, project and main package.
    ``item_id`` is set only for a line that is an item of a project.
    """

    code: str
    description: str
    level: int
    budget_cents: int
    item_id: int | None = None
    project_id: int | None = None
    project_label: str | None = None
    cost_type: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    unit_price_cents: int | None = None
    capex: bool | None = None
    cost_center: str | None = None
    responsible: str | None = None
    version: int | None = None
    weight: Decimal | None = None
    is_root: bool = False


def item_totals(items: Sequence[ItemLine]) -> dict[int, int]:
    """Valor orçado of every item: the product for an item, the sum of its children for the rest.

    Packages and subpackages add up on the server, in cents, from the items below them; a
    package without items is worth zero.
    """
    children: dict[int | None, list[ItemLine]] = {}
    for item in items:
        children.setdefault(item.parent_id, []).append(item)
    totals: dict[int, int] = {}

    def total_of(item: ItemLine) -> int:
        if item.level >= LEAF_LEVEL:
            totals[item.id] = budgeted_cents(item.quantity, item.unit_price_cents)
        else:
            totals[item.id] = sum(total_of(child) for child in children.get(item.id, ()))
        return totals[item.id]

    for item in children.get(None, ()):
        total_of(item)
    return totals


def project_total_cents(items: Sequence[ItemLine]) -> int:
    """Orçamento vigente of the project on the EAC: the sum of its packages (level 1)."""
    totals = item_totals(items)
    return sum(totals.get(item.id, 0) for item in items if item.level == 1)


def build_project_tree(
    items: Sequence[ItemLine], *, project_id: int, project_label: str, root_description: str
) -> tuple[TreeRow, ...]:
    """The tree of a project: the root line (code 0) with the total, then every item by code."""
    totals = item_totals(items)
    ordered = sorted(items, key=lambda item: code_key(item.code))
    rows = tuple(
        TreeRow(
            code=item.code,
            description=item.description,
            level=item.level,
            budget_cents=totals.get(item.id, 0),
            item_id=item.id,
            project_id=project_id,
            project_label=project_label,
            cost_type=item.cost_type,
            unit=item.unit,
            quantity=item.quantity,
            unit_price_cents=item.unit_price_cents,
            capex=item.capex if item.level >= LEAF_LEVEL else None,
            cost_center=item.cost_center,
            responsible=item.responsible,
            version=item.version,
        )
        for item in ordered
    )
    root = TreeRow(
        code=ROOT_CODE,
        description=root_description,
        level=0,
        budget_cents=sum(row.budget_cents for row in rows if row.level == 1),
        project_id=project_id,
        project_label=project_label,
        is_root=True,
    )
    return (root, *rows)


@dataclass(frozen=True)
class PortfolioProject:
    """A project of the portfolio as the portfolio tree needs it."""

    id: int
    label: str
    manager: str | None
    items: Sequence[ItemLine]
    weight: Decimal | None = None


def build_portfolio_tree(
    projects: Sequence[PortfolioProject], *, root_description: str
) -> tuple[TreeRow, ...]:
    """The tree of the Portfólio: line 0 is the portfolio, level 1 each project, level 2 its packages.

    The projects without items do not appear. The codes are the numbering of the portfolio: the
    project is ``1``, ``2``..., and its packages ``1.1``, ``1.2``... in the order of the projects.
    """
    rows: list[TreeRow] = []
    number = 0
    for project in projects:
        if not project.items:
            continue
        number += 1
        rows.extend(_project_lines(project, number))
    root = TreeRow(
        code=ROOT_CODE,
        description=root_description,
        level=0,
        budget_cents=sum(row.budget_cents for row in rows if row.level == 1),
        is_root=True,
    )
    return (root, *rows)


def _project_lines(project: PortfolioProject, number: int) -> list[TreeRow]:
    totals = item_totals(project.items)
    packages = sorted(
        (item for item in project.items if item.level == 1),
        key=lambda item: code_key(item.code),
    )
    lines = [
        TreeRow(
            code=str(number),
            description=project.label,
            level=1,
            budget_cents=sum(totals.get(package.id, 0) for package in packages),
            project_id=project.id,
            project_label=project.label,
            responsible=project.manager,
            weight=project.weight,
        )
    ]
    lines.extend(
        TreeRow(
            code=f"{number}{CODE_SEPARATOR}{package.code}",
            description=package.description,
            level=PORTFOLIO_MAIN_LEVEL,
            budget_cents=totals.get(package.id, 0),
            project_id=project.id,
            project_label=project.label,
            responsible=package.responsible,
        )
        for package in packages
    )
    return lines


def filter_tree(
    rows: Sequence[TreeRow],
    *,
    search: str = "",
    max_level: int = LEAF_LEVEL,
    cost_type: str = "",
) -> tuple[TreeRow, ...]:
    """The lines that match the search and the cost type, with their ancestors, down to the level.

    The root line always stays, filter or not. A line matches when the search is inside its code
    and description (accents and case ignored) and, if a cost type was chosen, when it is an item
    of that type. The ancestors of a match stay so the tree still reads as a tree.
    """
    needle = normalize_text(search)
    roots = tuple(row for row in rows if row.is_root)
    body = [row for row in rows if not row.is_root and row.level <= max_level]
    if not needle and not cost_type:
        return (*roots, *body)
    wanted: set[str] = set()
    for row in body:
        if _matches(row, needle, cost_type):
            wanted.add(row.code)
            wanted.update(_ancestor_codes(row.code))
    return (*roots, *(row for row in body if row.code in wanted))


def _matches(row: TreeRow, needle: str, cost_type: str) -> bool:
    text_matches = not needle or needle in normalize_text(f"{row.code} {row.description}")
    type_matches = not cost_type or (row.level >= LEAF_LEVEL and row.cost_type == cost_type)
    return text_matches and type_matches


def _ancestor_codes(code: str) -> list[str]:
    parts = code.split(CODE_SEPARATOR)
    return [CODE_SEPARATOR.join(parts[:size]) for size in range(1, len(parts))]


def filtered_total_cents(rows: Sequence[TreeRow]) -> int:
    """Total filtrado: the sum of the items shown, or of the shallowest level when none is shown."""
    body = [row for row in rows if not row.is_root]
    items = [row for row in body if row.level >= LEAF_LEVEL]
    if items:
        return sum(row.budget_cents for row in items)
    if not body:
        return 0
    shallowest = min(row.level for row in body)
    return sum(row.budget_cents for row in body if row.level == shallowest)


def parent_codes(rows: Sequence[TreeRow]) -> frozenset[str]:
    """The codes of the lines that have lines below them: the ones that get the toggle arrow."""
    parents = {CODE_SEPARATOR.join(row.code.split(CODE_SEPARATOR)[:-1]) for row in rows}
    parents.discard("")
    if any(row.is_root for row in rows) and any(not row.is_root for row in rows):
        parents.add(ROOT_CODE)
    return frozenset(parents)


# ── Ponderação da carteira ───────────────────────────────────────────────


@dataclass(frozen=True)
class WeightCriterion:
    """A criterion of the weighting: its id, its weight (%) and where its value comes from."""

    id: str
    weight: Decimal
    source: str


@dataclass(frozen=True)
class WeightInput:
    """What the weighting reads of a project: the budget in force on the EAC and its grades."""

    project_id: int
    budget_cents: int
    grades: Mapping[str, int]


@dataclass(frozen=True)
class ProjectWeight:
    """The weight of the project in the portfolio (%, two places) and each criterion's share."""

    weight: Decimal
    shares: Mapping[str, Decimal]


def largest_remainder[Key: Hashable](
    raw: Mapping[Key, Decimal], total: Decimal = WEIGHT_TOTAL
) -> dict[Key, Decimal]:
    """Maior resto: scale the values to the total in hundredths, so the sum is always exact.

    Each value is floored to hundredths and the hundredths that are missing go, one each, to the
    values with the largest remainders (a tie keeps the order of the input). When every value
    is zero the total is split equally, so the sum still closes.
    """
    if not raw:
        return {}
    target = int(total * HUNDREDTHS)
    values = raw if sum(raw.values(), Decimal(0)) > 0 else dict.fromkeys(raw, EQUAL_SHARE_FALLBACK)
    sum_values = sum(values.values(), Decimal(0))
    scaled = {key: value / sum_values * target for key, value in values.items()}
    floors = {
        key: int(value.to_integral_value(rounding=ROUND_FLOOR)) for key, value in scaled.items()
    }
    missing = target - sum(floors.values())
    by_remainder = sorted(scaled, key=lambda key: scaled[key] - floors[key], reverse=True)
    for key in by_remainder[:missing]:
        floors[key] += 1
    return {key: Decimal(cents) / HUNDREDTHS for key, cents in floors.items()}


def portfolio_weights(
    projects: Sequence[WeightInput], criteria: Sequence[WeightCriterion]
) -> dict[int, ProjectWeight]:
    """Ponderação da carteira: the weight of each project, closed at 100,00 by the largest remainder.

    The share of a project in a criterion is its value over the sum of the portfolio: the budget
    in force on the EAC for a criterion whose source is the budget, the grade (1 to 5) for the
    others; with a zero sum the shares are equal. The weight is the sum of the criteria weights
    times the shares, over the sum of the criteria weights.
    """
    shares = _criterion_shares(projects, criteria)
    criteria_sum = sum((criterion.weight for criterion in criteria), Decimal(0)) or Decimal(1)
    raw = {
        project.project_id: sum(
            (
                criterion.weight * shares[project.project_id][criterion.id] / HUNDREDTHS
                for criterion in criteria
            ),
            Decimal(0),
        )
        / criteria_sum
        * HUNDREDTHS
        for project in projects
    }
    weights = largest_remainder(raw)
    return {
        project.project_id: ProjectWeight(
            weight=weights[project.project_id],
            shares={
                key: share.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                for key, share in shares[project.project_id].items()
            },
        )
        for project in projects
    }


def _criterion_shares(
    projects: Sequence[WeightInput], criteria: Sequence[WeightCriterion]
) -> dict[int, dict[str, Decimal]]:
    shares: dict[int, dict[str, Decimal]] = {project.project_id: {} for project in projects}
    for criterion in criteria:
        values = {project.project_id: _value_of(project, criterion) for project in projects}
        total = sum(values.values(), Decimal(0))
        for project in projects:
            shares[project.project_id][criterion.id] = (
                values[project.project_id] / total * HUNDREDTHS
                if total
                else HUNDREDTHS / len(projects)
            )
    return shares


def _value_of(project: WeightInput, criterion: WeightCriterion) -> Decimal:
    if criterion.source == BUDGET_SOURCE:
        return Decimal(project.budget_cents)
    return Decimal(project.grades.get(criterion.id, 0))
