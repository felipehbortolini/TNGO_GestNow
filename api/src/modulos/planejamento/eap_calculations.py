"""Pure calculations of the EAP (ISSUE-036, D6, D8).

Every rule is one function, named after the business term in ``LEIA-ME.md``; nothing here reads
the clock, the database or the request: the reference date comes in as an argument. The numbers
follow ``GI.regras`` and ``GI.api.planejamento.eap`` of the prototype, in exact decimals: the
prototype rounds with ``Math.round`` (half toward plus infinity), which ``round_places`` repeats.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from src.core.import_values import normalize_text

ZERO = Decimal(0)
HUNDRED = Decimal(100)
HALF = Decimal("0.5")
TEN = Decimal(10)

AREA_LEVEL = 1
SUBAREA_LEVEL = 2
PACKAGE_LEVEL = 3
PORTFOLIO_PROJECT_LEVEL = 1
PORTFOLIO_AREA_LEVEL = 2
ROOT_CODE = "0"
CODE_SEPARATOR = "."

WORK = "Trabalho"
PLANNING = "Planejamento"

STAGES = "Etapas"
UNITS = "Unidades"
MILESTONE_0_100 = "Marco 0/100"
MILESTONE_50_50 = "Marco 50/50"
ESTIMATED = "Percentual estimado"
CRITERIA = (STAGES, UNITS, MILESTONE_0_100, MILESTONE_50_50, ESTIMATED)

NOT_STARTED = "Não iniciado"
STARTED = "Iniciado"
DONE = "Concluído"

OK = "success"
WARNING = "warning"
DANGER = "danger"

DEFAULT_BANDS = (Decimal(2), Decimal(5))
FILTER_PLANNING = "Planejamento"
SITUATION_BEHIND = "atrasado"
SITUATION_OVERDUE = "vencido"
SITUATION_PLANNING = "planejamento"


def round_places(value: Decimal, places: int) -> Decimal:
    """Round the way the prototype does (``Math.round``): half goes toward plus infinity."""
    factor = TEN**places
    return ((value * factor + HALF).to_integral_value(rounding=ROUND_FLOOR)) / factor


def code_key(code: str) -> tuple[int, ...]:
    """The sort key of a code: ``1.10`` comes after ``1.2``, as the numbers say."""
    return tuple(int(part) if part.isdigit() else 0 for part in code.split(CODE_SEPARATOR))


# ── Avanço do pacote pelo critério ───────────────────────────────────────


@dataclass(frozen=True)
class StageLine:
    """A stage of a package: its name, its weight inside the package and the percentage done."""

    name: str
    weight: Decimal
    percent: Decimal = ZERO


@dataclass(frozen=True)
class PackageEntries:
    """What the measuring criterion reads: stages, executed quantity, milestone state or estimate."""

    stages: tuple[StageLine, ...] = ()
    executed: Decimal | None = None
    state: str | None = None
    estimated_percent: Decimal | None = None


def entries_from_percent(
    criterion: str | None,
    percent: Decimal,
    *,
    quantity: Decimal | None,
    stages: Sequence[StageLine],
) -> PackageEntries:
    """The entries of the criterion that an accumulated percentage stands for (``entradasPorPercentual``).

    Stages fill in sequence; the executed quantity is the percentage of the baseline quantity;
    the milestones read the steps of the criterion; the estimate is the percentage itself.
    """
    if criterion == STAGES:
        return PackageEntries(stages=_fill_stages(stages, percent))
    if criterion == UNITS:
        executed = round_places((quantity or ZERO) * percent / HUNDRED, 2)
        return PackageEntries(executed=executed)
    if criterion in (MILESTONE_0_100, MILESTONE_50_50):
        return PackageEntries(state=_milestone_state(criterion, percent))
    if criterion == ESTIMATED:
        return PackageEntries(estimated_percent=round_places(percent, 2))
    return PackageEntries()


def _fill_stages(stages: Sequence[StageLine], percent: Decimal) -> tuple[StageLine, ...]:
    remaining = percent
    filled: list[StageLine] = []
    for stage in stages:
        used = min(stage.weight, max(ZERO, remaining))
        remaining -= used
        done = round_places(used / stage.weight * HUNDRED, 2) if stage.weight else ZERO
        filled.append(replace(stage, percent=done))
    return tuple(filled)


def _milestone_state(criterion: str, percent: Decimal) -> str:
    if percent == HUNDRED:
        return DONE
    if criterion == MILESTONE_50_50 and percent == HUNDRED / 2:
        return STARTED
    return NOT_STARTED


def package_progress(
    *,
    kind: str | None,
    criterion: str | None,
    quantity: Decimal | None,
    entries: PackageEntries,
) -> Decimal:
    """Avanço do pacote (``avancoPacoteEap``): the real percentage the criterion gives, 0 to 100.

    A planning package does not measure progress: it stays at 0. The result has two decimals.
    """
    if kind == PLANNING:
        return ZERO
    value = _criterion_value(criterion, quantity, entries)
    return round_places(max(ZERO, min(HUNDRED, value)), 2)


def _criterion_value(
    criterion: str | None, quantity: Decimal | None, entries: PackageEntries
) -> Decimal:
    if criterion == STAGES:
        return sum((stage.weight * stage.percent / HUNDRED for stage in entries.stages), ZERO)
    if criterion == UNITS:
        return _units_value(quantity, entries.executed)
    if criterion in (MILESTONE_0_100, MILESTONE_50_50):
        return _milestone_value(criterion, entries.state)
    return (entries.estimated_percent or ZERO) if criterion == ESTIMATED else ZERO


def _units_value(quantity: Decimal | None, executed: Decimal | None) -> Decimal:
    if quantity is None or quantity <= 0:
        return ZERO
    return min(HUNDRED, (executed or ZERO) / quantity * HUNDRED)


def _milestone_value(criterion: str, state: str | None) -> Decimal:
    if state == DONE:
        return HUNDRED
    return HUNDRED / 2 if criterion == MILESTONE_50_50 and state == STARTED else ZERO


@dataclass(frozen=True)
class PackageProgress:
    """The state of a package read from its last measurement: the real and the entries behind it."""

    real: Decimal
    entries: PackageEntries


def package_state(
    *,
    kind: str | None,
    criterion: str | None,
    quantity: Decimal | None,
    stages: Sequence[StageLine],
    measured_percent: Decimal | None,
) -> PackageProgress:
    """Real of a package from its last measurement: the percentage goes through the criterion.

    No measurement means no progress. The accumulated percentage of the measurement is turned
    into the entries of the criterion and the criterion gives the real (D6, single source).
    """
    entries = entries_from_percent(
        criterion, measured_percent or ZERO, quantity=quantity, stages=stages
    )
    real = package_progress(kind=kind, criterion=criterion, quantity=quantity, entries=entries)
    return PackageProgress(real=real, entries=entries)


def progress_from_measurement(
    *,
    kind: str | None,
    criterion: str | None,
    quantity: Decimal | None,
    stages: Sequence[StageLine],
    measured_percent: Decimal | None,
) -> Decimal:
    """The real of a package from its last measurement (see ``package_state``)."""
    return package_state(
        kind=kind,
        criterion=criterion,
        quantity=quantity,
        stages=stages,
        measured_percent=measured_percent,
    ).real


# ── Desvio, faixas e vencimento ──────────────────────────────────────────


def deviation_pp(real: Decimal, planned: Decimal) -> Decimal:
    """Desvio físico: real minus planned, in percentage points with one decimal."""
    return round_places(real - planned, 1)


def deviation_band(deviation: Decimal | None, bands: tuple[Decimal, Decimal]) -> str | None:
    """Faixa do desvio físico (``faixaDesvioFisico``): ``success``, ``warning`` or ``danger``.

    The limits are the parameter bands (-2 and -5 p.p.): at the limit the better band holds.
    """
    if deviation is None:
        return None
    if deviation >= -bands[0]:
        return OK
    return WARNING if deviation >= -bands[1] else DANGER


def package_is_overdue(
    *, kind: str | None, end_date: date | None, real: Decimal, reference_date: date
) -> bool:
    """Término vencido: a work package whose baseline end is before the reference date and is below 100%."""
    if kind == PLANNING or end_date is None:
        return False
    return end_date < reference_date and real < HUNDRED


def weights_close_at_100(total_weight: Decimal) -> bool:
    """Regra dos 100%: the weights of the packages add up to the whole project."""
    return total_weight == HUNDRED


def weighted_average(pairs: Sequence[tuple[Decimal, Decimal]]) -> Decimal:
    """Média ponderada pelo peso, two decimals; zero when the weights add up to zero."""
    total = sum((weight for weight, _ in pairs), ZERO)
    if not total:
        return ZERO
    return round_places(sum((weight * value for weight, value in pairs), ZERO) / total, 2)


# ── Árvore do projeto ────────────────────────────────────────────────────


@dataclass(frozen=True)
class EapLine:
    """An item of the EAP as the tree needs it, with the names resolved and the real calculated."""

    id: int
    parent_id: int | None
    code: str
    description: str
    level: int
    kind: str | None = None
    criterion: str | None = None
    stage_model: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    executed: Decimal | None = None
    weight: Decimal | None = None
    planned: Decimal | None = None
    real: Decimal = ZERO
    start_date: date | None = None
    end_date: date | None = None
    company: str | None = None
    responsible: str | None = None
    eac_code: str | None = None
    version: int = 1


@dataclass(frozen=True)
class Rules:
    """What the tree reads besides the items: the bands of the parameters and the reference date."""

    bands: tuple[Decimal, Decimal]
    reference_date: date


@dataclass(frozen=True)
class TreeRow:
    """A line of the tree: what the table, the Excel and the printable version print.

    ``level`` is 0 for the root line (the project, or the portfolio), 1 to 3 for area, subarea and
    package. In the Portfólio the levels mean portfolio, project and main package (area).
    """

    code: str
    description: str
    level: int
    weight: Decimal
    planned: Decimal
    real: Decimal
    deviation: Decimal
    band: str | None
    item_id: int | None = None
    project_id: int | None = None
    project_label: str | None = None
    is_root: bool = False
    is_work: bool = False
    is_overdue: bool = False
    kind: str | None = None
    criterion: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    executed: Decimal | None = None
    weight_in_parent: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    company: str | None = None
    responsible: str | None = None
    eac_code: str | None = None
    work_count: int = 0
    planning_count: int = 0
    overdue_count: int = 0


@dataclass(frozen=True)
class _Node:
    weight: Decimal
    planned: Decimal
    real: Decimal
    start_date: date | None
    end_date: date | None
    work_count: int
    planning_count: int
    overdue_count: int


def _leaf_node(line: EapLine, rules: Rules) -> _Node:
    is_work = line.kind != PLANNING
    overdue = package_is_overdue(
        kind=line.kind, end_date=line.end_date, real=line.real, reference_date=rules.reference_date
    )
    return _Node(
        weight=line.weight or ZERO,
        planned=line.planned or ZERO,
        real=line.real,
        start_date=line.start_date,
        end_date=line.end_date,
        work_count=1 if is_work else 0,
        planning_count=0 if is_work else 1,
        overdue_count=1 if overdue else 0,
    )


def _parent_node(children: Sequence[_Node]) -> _Node:
    weight = round_places(sum((child.weight for child in children), ZERO), 2)
    starts = [child.start_date for child in children if child.start_date]
    ends = [child.end_date for child in children if child.end_date]
    return _Node(
        weight=weight,
        planned=weighted_average([(child.weight, child.planned) for child in children]),
        real=weighted_average([(child.weight, child.real) for child in children]),
        start_date=min(starts) if starts else None,
        end_date=max(ends) if ends else None,
        work_count=sum(child.work_count for child in children),
        planning_count=sum(child.planning_count for child in children),
        overdue_count=sum(child.overdue_count for child in children),
    )


def _nodes_of(lines: Sequence[EapLine], rules: Rules) -> dict[int, _Node]:
    """The weight, the previous and the real of every item: leaves as stored, the rest by sum."""
    children: dict[int | None, list[EapLine]] = {}
    for line in lines:
        children.setdefault(line.parent_id, []).append(line)
    nodes: dict[int, _Node] = {}

    def node_of(line: EapLine) -> _Node:
        if line.level >= PACKAGE_LEVEL:
            nodes[line.id] = _leaf_node(line, rules)
        else:
            nodes[line.id] = _parent_node([node_of(child) for child in children.get(line.id, ())])
        return nodes[line.id]

    for line in children.get(None, ()):
        node_of(line)
    return nodes


def _row_of(line: EapLine, node: _Node, *, parent: _Node | None, rules: Rules) -> TreeRow:
    deviation = deviation_pp(node.real, node.planned)
    is_leaf = line.level >= PACKAGE_LEVEL
    is_work = is_leaf and line.kind != PLANNING
    in_parent = (
        round_places(node.weight / parent.weight * HUNDRED, 1)
        if parent is not None and parent.weight
        else None
    )
    return TreeRow(
        code=line.code,
        description=line.description,
        level=line.level,
        weight=node.weight,
        planned=node.planned,
        real=node.real,
        deviation=deviation,
        band=deviation_band(deviation, rules.bands),
        item_id=line.id,
        is_work=is_work,
        is_overdue=is_leaf and node.overdue_count > 0,
        kind=line.kind if is_leaf else None,
        criterion=line.criterion if is_work else None,
        unit=line.unit,
        quantity=line.quantity,
        executed=line.executed,
        weight_in_parent=in_parent,
        start_date=node.start_date,
        end_date=node.end_date,
        company=line.company,
        responsible=line.responsible,
        eac_code=line.eac_code,
        work_count=node.work_count,
        planning_count=node.planning_count,
        overdue_count=node.overdue_count,
    )


def _root_row(nodes: Sequence[_Node], *, code: str, description: str, rules: Rules) -> TreeRow:
    total = _parent_node(nodes)
    deviation = deviation_pp(total.real, total.planned)
    return TreeRow(
        code=code,
        description=description,
        level=0,
        weight=total.weight,
        planned=total.planned,
        real=total.real,
        deviation=deviation,
        band=deviation_band(deviation, rules.bands),
        is_root=True,
        start_date=total.start_date,
        end_date=total.end_date,
        work_count=total.work_count,
        planning_count=total.planning_count,
        overdue_count=total.overdue_count,
    )


@dataclass(frozen=True)
class ProjectIdentity:
    """The project a tree belongs to: id, label, root description and the manager."""

    project_id: int
    label: str
    description: str
    manager: str | None = None


def build_project_tree(
    lines: Sequence[EapLine], *, identity: ProjectIdentity, rules: Rules
) -> tuple[TreeRow, ...]:
    """The tree of a project: the root line (code 0) with the totals, then every item by code.

    Only the packages carry weight, the baseline and the real; areas, subareas and the total are
    the weighted average of the children, and the weight of each level is the sum of the weights
    below it (regra dos 100%).
    """
    nodes = _nodes_of(lines, rules)
    by_id = {line.id: line for line in lines}
    rows = tuple(
        replace(
            _row_of(
                line,
                nodes[line.id],
                parent=nodes.get(line.parent_id) if line.parent_id else None,
                rules=rules,
            ),
            project_id=identity.project_id,
            project_label=identity.label,
        )
        for line in sorted(by_id.values(), key=lambda item: code_key(item.code))
    )
    top = [nodes[line.id] for line in lines if line.level == AREA_LEVEL]
    root = replace(
        _root_row(top, code=ROOT_CODE, description=identity.description, rules=rules),
        project_id=identity.project_id,
        project_label=identity.label,
        responsible=identity.manager,
    )
    return (root, *rows)


# ── Árvore da carteira ───────────────────────────────────────────────────


@dataclass(frozen=True)
class PortfolioEap:
    """A project of the portfolio as the portfolio tree needs it: its tree and its weight."""

    number: int
    identity: ProjectIdentity
    rows: Sequence[TreeRow]
    weight: Decimal | None = None


def build_portfolio_tree(
    projects: Sequence[PortfolioEap], *, root_description: str, rules: Rules
) -> tuple[TreeRow, ...]:
    """The tree of the Portfólio: line 0 is the portfolio, level 1 each project, level 2 its areas.

    Each project weighs what the weighting of the portfolio says (D8); its areas weigh their
    weight in the project times the weight of the project. The projects without EAP do not
    appear, but keep their number, as in the prototype.
    """
    rows: list[TreeRow] = []
    weights: list[tuple[Decimal, Decimal, Decimal]] = []
    for project in projects:
        if len(project.rows) <= 1:
            continue
        weight = project.weight or ZERO
        total = project.rows[0]
        weights.append((weight, total.planned, total.real))
        rows.extend(_project_lines(project, weight))
    return (_portfolio_root(rows, weights, root_description, rules), *rows)


def _project_lines(project: PortfolioEap, weight: Decimal) -> list[TreeRow]:
    total, *items = project.rows
    number = str(project.number)
    lines = [
        replace(
            total,
            code=number,
            description=project.identity.label,
            level=PORTFOLIO_PROJECT_LEVEL,
            weight=weight,
            is_root=False,
        )
    ]
    for area in (item for item in items if item.level == AREA_LEVEL):
        lines.append(
            replace(
                area,
                code=f"{number}{CODE_SEPARATOR}{area.code}",
                level=PORTFOLIO_AREA_LEVEL,
                weight=round_places(area.weight * weight / HUNDRED, 2),
                weight_in_parent=area.weight,
            )
        )
    return lines


def _portfolio_root(
    rows: Sequence[TreeRow],
    weights: Sequence[tuple[Decimal, Decimal, Decimal]],
    description: str,
    rules: Rules,
) -> TreeRow:
    total_weight = sum((weight for weight, _, _ in weights), ZERO)
    divisor = total_weight or Decimal(1)
    planned = round_places(sum((w * p for w, p, _ in weights), ZERO) / divisor, 2)
    real = round_places(sum((w * r for w, _, r in weights), ZERO) / divisor, 2)
    deviation = deviation_pp(real, planned)
    projects = [row for row in rows if row.level == PORTFOLIO_PROJECT_LEVEL]
    starts = [row.start_date for row in projects if row.start_date]
    ends = [row.end_date for row in projects if row.end_date]
    return TreeRow(
        code=ROOT_CODE,
        description=description,
        level=0,
        weight=round_places(total_weight, 2),
        planned=planned,
        real=real,
        deviation=deviation,
        band=deviation_band(deviation, rules.bands),
        is_root=True,
        start_date=min(starts) if starts else None,
        end_date=max(ends) if ends else None,
        work_count=sum(row.work_count for row in projects),
        planning_count=sum(row.planning_count for row in projects),
        overdue_count=sum(row.overdue_count for row in projects),
    )


# ── Indicadores ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EapSummary:
    """The numbers of the KPIs: real, planned, deviation, the packages and what is late."""

    planned: Decimal
    real: Decimal
    deviation: Decimal
    band: str | None
    weight_total: Decimal
    work_count: int
    planning_count: int
    planning_weight: Decimal
    area_count: int
    subarea_count: int
    overdue_count: int
    behind_count: int
    project_count: int


def summarize(rows: Sequence[TreeRow], *, portfolio: bool) -> EapSummary:
    """The indicators of the EAP from the full tree (never from the filtered one)."""
    root = next((row for row in rows if row.is_root), None)
    leaves = [row for row in rows if row.level == PACKAGE_LEVEL and not portfolio]
    area_level = PORTFOLIO_AREA_LEVEL if portfolio else AREA_LEVEL
    return EapSummary(
        planned=root.planned if root else ZERO,
        real=root.real if root else ZERO,
        deviation=root.deviation if root else ZERO,
        band=root.band if root else None,
        weight_total=root.weight if root else ZERO,
        work_count=root.work_count if root else 0,
        planning_count=root.planning_count if root else 0,
        planning_weight=round_places(
            sum((row.weight for row in leaves if not row.is_work), ZERO), 2
        ),
        area_count=sum(1 for row in rows if row.level == area_level),
        subarea_count=sum(1 for row in rows if row.level == SUBAREA_LEVEL and not portfolio),
        overdue_count=root.overdue_count if root else 0,
        behind_count=sum(1 for row in leaves if row.is_work and row.band == DANGER),
        project_count=sum(1 for row in rows if row.level == PORTFOLIO_PROJECT_LEVEL and portfolio),
    )


def portfolio_behind_count(project_summaries: Sequence[EapSummary]) -> int:
    """Pacotes com desvio abaixo da faixa da carteira: the sum of the ones of each project."""
    return sum(summary.behind_count for summary in project_summaries)


# ── Filtros ──────────────────────────────────────────────────────────────


def filter_tree(
    rows: Sequence[TreeRow],
    *,
    search: str = "",
    max_level: int = PACKAGE_LEVEL,
    leaf_filters: Mapping[str, str] | None = None,
) -> tuple[TreeRow, ...]:
    """The lines that match the search and the package filters, with their ancestors, down to the level.

    ``leaf_filters`` carries ``criterio`` (a criterion, or ``Planejamento`` for the packages
    without measurement) and ``situacao`` (``atrasado``, ``vencido`` or ``planejamento``); they
    narrow the packages, and the ancestors of a match stay so the tree still reads as a tree. The
    root line always stays.
    """
    leaf_filters = {key: value for key, value in (leaf_filters or {}).items() if value}
    needle = normalize_text(search)
    roots = tuple(row for row in rows if row.is_root)
    body = [row for row in rows if not row.is_root and row.level <= max_level]
    if not needle and not leaf_filters:
        return (*roots, *body)
    wanted: set[str] = set()
    for row in body:
        if _matches(row, needle, leaf_filters):
            wanted.add(row.code)
            wanted.update(_ancestor_codes(row.code))
    return (*roots, *(row for row in body if row.code in wanted))


def _matches(row: TreeRow, needle: str, leaf_filters: Mapping[str, str]) -> bool:
    text_matches = not needle or needle in normalize_text(f"{row.code} {row.description}")
    return text_matches and (not leaf_filters or _leaf_passes(row, leaf_filters))


def _leaf_passes(row: TreeRow, leaf_filters: Mapping[str, str]) -> bool:
    if row.level != PACKAGE_LEVEL:
        return False
    criterion = leaf_filters.get("criterio", "")
    if criterion == FILTER_PLANNING and row.is_work:
        return False
    if criterion and criterion != FILTER_PLANNING and row.criterion != criterion:
        return False
    return _situation_passes(row, leaf_filters.get("situacao", ""))


def _situation_passes(row: TreeRow, situation: str) -> bool:
    if situation == SITUATION_BEHIND:
        return row.is_work and row.band == DANGER
    if situation == SITUATION_OVERDUE:
        return row.is_overdue
    if situation == SITUATION_PLANNING:
        return not row.is_work
    return True


def _ancestor_codes(code: str) -> list[str]:
    parts = code.split(CODE_SEPARATOR)
    return [CODE_SEPARATOR.join(parts[:size]) for size in range(1, len(parts))]


def parent_codes(rows: Sequence[TreeRow]) -> frozenset[str]:
    """The codes of the lines that have lines below them: the ones that get the toggle arrow."""
    parents = {CODE_SEPARATOR.join(row.code.split(CODE_SEPARATOR)[:-1]) for row in rows}
    parents.discard("")
    if any(row.is_root for row in rows) and any(not row.is_root for row in rows):
        parents.add(ROOT_CODE)
    return frozenset(parents)


def revision_package_count(frozen_weights: Sequence[Decimal]) -> int:
    """Pacotes da revisão: the packages (work and planning) with a frozen weight, counted on the server."""
    return sum(1 for weight in frozen_weights if weight > 0)
