"""Business facade of the EAP (ISSUE-036, D5, D6, D8).

The EAP is read per scope: one project, with its root line (code 0) and the totals added on the
server, or the Portfólio, read-only, with a line per project and one per main package (D8). The
real of a package is never stored (D5b, D6): it is the last measurement of the package read
through its measuring criterion. Measuring (ISSUE-037) and revising (ISSUE-038) come later; this
facade reads, and gives the demonstration load the doors to write the tree, the measurements, the
revisions and the splits through ``recording`` and the trail.

Nothing here reads the clock: the routes pass the reference date.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import audit, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service as financeiro
from src.modulos.governanca import service as governanca
from src.modulos.planejamento import eap_calculations as calculations
from src.modulos.planejamento.eap_calculations import (
    EapLine,
    EapSummary,
    PortfolioEap,
    ProjectIdentity,
    Rules,
    StageLine,
    TreeRow,
)
from src.modulos.planejamento.models import (
    EapItem,
    EapItemStage,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
    EapSplit,
)

MODULE = "planejamento"
PORTFOLIO_LABEL = "Portfólio"
PORTFOLIO_ROOT_DESCRIPTION = "Portfólio de projetos"
PARAMETER_GROUP = "eap"

NOT_FOUND_MESSAGE = "Pacote da EAP não encontrado."
UNKNOWN_PROJECT_MESSAGE = "O projeto escolhido não existe."
PORTFOLIO_READ_ONLY_MESSAGE = (
    "A EAP do Portfólio é somente leitura. Abra o projeto para ver o dicionário do pacote."
)
OTHER_PROJECT_MESSAGE = (
    "O pacote pertence a outro projeto. Abra o projeto dele para ver o dicionário."
)
ONLY_PACKAGES_MESSAGE = "Só os pacotes (nível 3) têm dicionário."


@dataclass(frozen=True)
class EapFilters:
    """What the person typed in the filters of the tree: search, deepest level, criterion, situation."""

    search: str = ""
    level: int = calculations.PACKAGE_LEVEL
    criterion: str = ""
    situation: str = ""

    @property
    def is_active(self) -> bool:
        """Whether a text, a criterion or a situation narrows the tree (the level only cuts depth)."""
        return bool(self.search.strip() or self.criterion or self.situation)


@dataclass(frozen=True)
class RevisionView:
    """A revision of the EAP as the list prints it; ``package_count`` is empty without frozen weights."""

    project_id: int
    project_label: str
    number: int
    revised_on: date
    package_count: int | None
    change: str
    change_code: str | None
    justification: str
    approved_by: str
    is_current: bool


@dataclass(frozen=True)
class SplitView:
    """A split of a planning package into a work package, as the list prints it."""

    split_on: date
    source: str
    target: str
    weight: Decimal
    justification: str
    by: str


@dataclass(frozen=True)
class EapView:
    """Everything the EAP screen, its Excel and its printable version print."""

    scope_label: str
    is_portfolio: bool
    rows: tuple[TreeRow, ...]
    full_rows: tuple[TreeRow, ...]
    parents: frozenset[str]
    summary: EapSummary
    filters: EapFilters
    max_level: int
    bands: tuple[Decimal, Decimal]
    revisions: tuple[RevisionView, ...]
    splits: tuple[SplitView, ...]
    reference_date: date

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no EAP at all (the empty state of origin)."""
        return len(self.full_rows) <= 1

    @property
    def has_no_match(self) -> bool:
        """Whether the filters hide every line (the empty state of the filter)."""
        return not self.is_empty and len(self.rows) <= 1

    @property
    def current_revision(self) -> RevisionView | None:
        """The revision in force of the project (none in the Portfólio, where each project has one)."""
        return next((item for item in self.revisions if item.is_current), None)

    @property
    def weight_rule_holds(self) -> bool:
        """Whether the weights of the packages add up to 100% (regra dos 100%)."""
        return calculations.weights_close_at_100(self.summary.weight_total)


# ── Leitura da EAP ───────────────────────────────────────────────────────


def eap_view(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: EapFilters,
    reference_date: date,
) -> EapView:
    """The EAP of the scope: one project or the Portfólio, both read-only on this screen."""
    rbac.require_module(user, MODULE)
    projects = configuracoes.list_projects(session)
    bands = _bands(session, reference_date)
    rules = Rules(bands=bands, reference_date=reference_date)
    lines = _lines_by_project(session, [project.id for project in projects])
    people = {person.id: person.name for person in configuracoes.list_people(session)}
    trees = {
        project.id: calculations.build_project_tree(
            lines[project.id], identity=_identity(project, people), rules=rules
        )
        for project in projects
        if lines.get(project.id)
    }
    scoped = _scoped(session, projects, trees, rules=rules, scope=scope)
    level = min(max(filters.level, 1), scoped.max_level)
    rows = calculations.filter_tree(
        scoped.rows,
        search=filters.search,
        max_level=level,
        leaf_filters={"criterio": filters.criterion, "situacao": filters.situation},
    )
    revisions = _revisions(session, projects, scope)
    return EapView(
        scope_label=scoped.label,
        is_portfolio=scope.is_portfolio,
        rows=rows,
        full_rows=scoped.rows,
        parents=calculations.parent_codes(rows),
        summary=scoped.summary,
        filters=EapFilters(
            search=filters.search.strip(),
            level=level,
            criterion=filters.criterion,
            situation=filters.situation,
        ),
        max_level=scoped.max_level,
        bands=bands,
        revisions=revisions,
        splits=_splits(session, scope, revisions),
        reference_date=reference_date,
    )


@dataclass(frozen=True)
class _Scoped:
    """The tree, the indicators, the deepest level and the label of the scope of the request."""

    rows: tuple[TreeRow, ...]
    summary: EapSummary
    max_level: int
    label: str


def _scoped(
    session: Session,
    projects: Sequence[configuracoes.ProjectSummary],
    trees: Mapping[int, tuple[TreeRow, ...]],
    *,
    rules: Rules,
    scope: Scope,
) -> _Scoped:
    if scope.is_portfolio:
        rows = _portfolio_rows(session, projects, trees, rules, reference_date=rules.reference_date)
        return _Scoped(
            rows=rows,
            summary=_portfolio_summary(rows, trees),
            max_level=calculations.PORTFOLIO_AREA_LEVEL,
            label=PORTFOLIO_LABEL,
        )
    project = _project_of(projects, scope)
    rows = trees.get(project.id, ())
    return _Scoped(
        rows=rows,
        summary=calculations.summarize(rows, portfolio=False) if rows else _empty(),
        max_level=calculations.PACKAGE_LEVEL,
        label=_label(project),
    )


def _empty() -> EapSummary:
    zero = calculations.ZERO
    return EapSummary(
        planned=zero,
        real=zero,
        deviation=zero,
        band=None,
        weight_total=zero,
        work_count=0,
        planning_count=0,
        planning_weight=zero,
        area_count=0,
        subarea_count=0,
        overdue_count=0,
        behind_count=0,
        project_count=0,
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


def _identity(project: configuracoes.ProjectSummary, people: Mapping[int, str]) -> ProjectIdentity:
    return ProjectIdentity(
        project_id=project.id,
        label=_label(project),
        description=project.name,
        manager=people.get(project.manager_id) if project.manager_id else None,
    )


def _portfolio_rows(
    session: Session,
    projects: Sequence[configuracoes.ProjectSummary],
    trees: Mapping[int, tuple[TreeRow, ...]],
    rules: Rules,
    *,
    reference_date: date,
) -> tuple[TreeRow, ...]:
    weights = financeiro.portfolio_weights(session, reference_date=reference_date)
    entries = [
        PortfolioEap(
            number=number,
            identity=ProjectIdentity(
                project_id=project.id,
                label=_label(project),
                description=project.name,
                manager=trees[project.id][0].responsible,
            ),
            rows=trees[project.id],
            weight=weights[project.id].weight if project.id in weights else None,
        )
        for number, project in enumerate(projects, start=1)
        if project.id in trees
    ]
    return calculations.build_portfolio_tree(
        entries, root_description=PORTFOLIO_ROOT_DESCRIPTION, rules=rules
    )


def _portfolio_summary(
    rows: Sequence[TreeRow], trees: Mapping[int, tuple[TreeRow, ...]]
) -> EapSummary:
    summary = calculations.summarize(rows, portfolio=True) if rows else _empty()
    behind = calculations.portfolio_behind_count(
        [calculations.summarize(tree, portfolio=False) for tree in trees.values()]
    )
    return _with_behind(summary, behind)


def _with_behind(summary: EapSummary, behind: int) -> EapSummary:
    return replace(summary, behind_count=behind)


def _group(session: Session, reference_date: date) -> Mapping[str, Any]:
    """The ``eap`` parameters in force on the date; the initial ones when no version exists yet."""
    group = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    )
    return group or configuracoes.INITIAL_PARAMETERS[PARAMETER_GROUP]


def _bands(session: Session, reference_date: date) -> tuple[Decimal, Decimal]:
    """The deviation bands of the parameters in force (2 and 5 p.p. by default), as positive limits."""
    configured = _group(session, reference_date).get("faixasDesvioPP") or []
    if len(configured) != len(calculations.DEFAULT_BANDS):
        return calculations.DEFAULT_BANDS
    return (Decimal(str(configured[0])), Decimal(str(configured[1])))


def _stage_models(session: Session, reference_date: date) -> dict[str, str]:
    models = _group(session, reference_date).get("modelosEtapas") or []
    return {str(model["id"]): str(model["nome"]) for model in models}


def _lines_by_project(session: Session, project_ids: Sequence[int]) -> dict[int, list[EapLine]]:
    """The items of the projects with the names resolved and the real of each package calculated."""
    if not project_ids:
        return {}
    items = list(
        session.scalars(
            select(EapItem).where(EapItem.project_id.in_(project_ids)).order_by(EapItem.id)
        )
    )
    item_ids = [item.id for item in items]
    stages = _stages_of(session, item_ids)
    measured = _last_percent_of(session, item_ids)
    people = {person.id: person.name for person in configuracoes.list_people(session)}
    units = {unit.id: unit.code for unit in configuracoes.list_measure_units(session)}
    companies = configuracoes.list_company_names(session)
    eac_codes = financeiro.eac_item_codes(
        session, [item.eac_item_id for item in items if item.eac_item_id]
    )
    grouped: dict[int, list[EapLine]] = {}
    for item in items:
        progress = calculations.package_state(
            kind=item.kind,
            criterion=item.criterion,
            quantity=item.quantity,
            stages=stages.get(item.id, ()),
            measured_percent=measured.get(item.id),
        )
        grouped.setdefault(item.project_id, []).append(
            EapLine(
                id=item.id,
                parent_id=item.parent_id,
                code=item.code,
                description=item.description,
                level=item.level,
                kind=item.kind,
                criterion=item.criterion,
                stage_model=item.stage_model,
                unit=units.get(item.unit_id) if item.unit_id else None,
                quantity=item.quantity,
                executed=progress.entries.executed
                if item.criterion == calculations.UNITS
                else None,
                weight=item.weight,
                planned=item.planned,
                real=progress.real,
                start_date=item.start_date,
                end_date=item.end_date,
                company=companies.get(item.company_id) if item.company_id else None,
                responsible=people.get(item.responsible_id) if item.responsible_id else None,
                eac_code=eac_codes.get(item.eac_item_id) if item.eac_item_id else None,
                version=item.version,
            )
        )
    return grouped


def _stages_of(session: Session, item_ids: Sequence[int]) -> dict[int, tuple[StageLine, ...]]:
    statement = (
        select(EapItemStage)
        .where(EapItemStage.item_id.in_(item_ids))
        .order_by(EapItemStage.item_id, EapItemStage.order)
    )
    grouped: dict[int, list[StageLine]] = {}
    for stage in session.scalars(statement):
        grouped.setdefault(stage.item_id, []).append(
            StageLine(name=stage.name, weight=stage.weight)
        )
    return {item_id: tuple(stages) for item_id, stages in grouped.items()}


def _last_percent_of(session: Session, item_ids: Sequence[int]) -> dict[int, Decimal]:
    """The accumulated percentage of the last measurement of each package (date, then id)."""
    statement = (
        select(EapMeasurement)
        .where(EapMeasurement.item_id.in_(item_ids))
        .order_by(EapMeasurement.measured_on, EapMeasurement.id)
    )
    return {
        measurement.item_id: measurement.to_percent for measurement in session.scalars(statement)
    }


# ── Revisões e desdobramentos ────────────────────────────────────────────


def _revisions(
    session: Session, projects: Sequence[configuracoes.ProjectSummary], scope: Scope
) -> tuple[RevisionView, ...]:
    """The revisions of the scope, the newest first; in the Portfólio only the one in force of each project."""
    wanted = {
        project.id: project
        for project in projects
        if scope.is_portfolio or project.id == scope.project_id
    }
    records = list(
        session.scalars(
            select(EapRevision)
            .where(EapRevision.project_id.in_(wanted))
            .order_by(EapRevision.project_id, EapRevision.number)
        )
    )
    current = {record.project_id: record.number for record in records}
    counts = _frozen_counts(session, [record.id for record in records])
    codes = governanca.change_codes(
        session, [record.change_id for record in records if record.change_id]
    )
    names = configuracoes.person_names(
        session, [record.approved_by_id for record in records if record.approved_by_id]
    )
    views = [
        RevisionView(
            project_id=record.project_id,
            project_label=_label(wanted[record.project_id]),
            number=record.number,
            revised_on=record.revised_on,
            package_count=counts.get(record.id),
            change=record.change,
            change_code=codes.get(record.change_id) if record.change_id else None,
            justification=record.justification,
            approved_by=names.get(record.approved_by_id, "") if record.approved_by_id else "",
            is_current=record.number == current[record.project_id],
        )
        for record in records
    ]
    if scope.is_portfolio:
        views = [view for view in views if view.is_current]
    return tuple(sorted(views, key=lambda view: (view.project_label, -view.number)))


def _frozen_counts(session: Session, revision_ids: Sequence[int]) -> dict[int, int]:
    """The packages of each revision that has frozen weights; a revision without them is left out."""
    if not revision_ids:
        return {}
    statement = select(EapRevisionItem.revision_id, EapRevisionItem.weight).where(
        EapRevisionItem.revision_id.in_(revision_ids)
    )
    grouped: dict[int, list[Decimal]] = {}
    for row in session.execute(statement):
        grouped.setdefault(row.revision_id, []).append(row.weight)
    return {
        revision_id: calculations.revision_package_count(weights)
        for revision_id, weights in grouped.items()
    }


def _splits(
    session: Session, scope: Scope, revisions: Sequence[RevisionView]
) -> tuple[SplitView, ...]:
    """The splits of the revision in force of the project; the Portfólio lists none."""
    current = next((item for item in revisions if item.is_current), None)
    if scope.is_portfolio or current is None:
        return ()
    records = list(
        session.scalars(
            select(EapSplit)
            .where(EapSplit.project_id == scope.project_id, EapSplit.revision == current.number)
            .order_by(EapSplit.split_on.desc(), EapSplit.id.desc())
        )
    )
    labels = _item_labels(
        session,
        {item for record in records for item in (record.source_item_id, record.target_item_id)},
    )
    names = configuracoes.person_names(
        session, [record.by_id for record in records if record.by_id]
    )
    return tuple(
        SplitView(
            split_on=record.split_on,
            source=labels.get(record.source_item_id, ""),
            target=labels.get(record.target_item_id, ""),
            weight=record.weight,
            justification=record.justification,
            by=names.get(record.by_id, "") if record.by_id else "",
        )
        for record in records
    )


def _item_labels(session: Session, item_ids: set[int]) -> dict[int, str]:
    if not item_ids:
        return {}
    statement = select(EapItem.id, EapItem.code, EapItem.description).where(
        EapItem.id.in_(item_ids)
    )
    return {row.id: f"{row.code} {row.description}" for row in session.execute(statement)}


# ── Dicionário do pacote ─────────────────────────────────────────────────


@dataclass(frozen=True)
class MeasurementView:
    """A measurement of the package as the dictionary prints it."""

    measured_on: date
    from_percent: Decimal
    to_percent: Decimal
    author: str
    note: str


@dataclass(frozen=True)
class StageView:
    """A stage of the package: name, weight in the package and the percentage done."""

    name: str
    weight: Decimal
    percent: Decimal


@dataclass(frozen=True)
class PackageDictionary:
    """The dictionary of a package: what it delivers, who does it, how it is measured and its history."""

    row: TreeRow
    stage_model: str
    stages: tuple[StageView, ...]
    measurements: tuple[MeasurementView, ...]
    deliverable: str
    acceptance: str
    reference_date: date


def package_dictionary(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    reference_date: date,
) -> PackageDictionary:
    """The dictionary of a package (nível 3) of the project in scope; the Portfólio has none."""
    rbac.require_module(user, MODULE)
    if scope.is_portfolio:
        raise AccessDeniedError(PORTFOLIO_READ_ONLY_MESSAGE)
    item = session.get(EapItem, item_id)
    if item is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    if item.project_id != scope.project_id:
        raise AccessDeniedError(OTHER_PROJECT_MESSAGE)
    if item.level < calculations.PACKAGE_LEVEL:
        raise InvalidDataError(ONLY_PACKAGES_MESSAGE)
    rules = Rules(bands=_bands(session, reference_date), reference_date=reference_date)
    project = next(
        entry for entry in configuracoes.list_projects(session) if entry.id == item.project_id
    )
    people = {person.id: person.name for person in configuracoes.list_people(session)}
    lines = _lines_by_project(session, [item.project_id])[item.project_id]
    tree = calculations.build_project_tree(lines, identity=_identity(project, people), rules=rules)
    row = next(entry for entry in tree if entry.item_id == item.id)
    return PackageDictionary(
        row=row,
        stage_model=_stage_models(session, reference_date).get(item.stage_model or "", ""),
        stages=_stage_views(session, item),
        measurements=_measurement_views(session, item.id, people),
        deliverable=item.deliverable or "",
        acceptance=item.acceptance or "",
        reference_date=reference_date,
    )


def _stage_views(session: Session, item: EapItem) -> tuple[StageView, ...]:
    if item.criterion != calculations.STAGES:
        return ()
    stages = _stages_of(session, [item.id]).get(item.id, ())
    measured = _last_percent_of(session, [item.id]).get(item.id)
    state = calculations.package_state(
        kind=item.kind,
        criterion=item.criterion,
        quantity=item.quantity,
        stages=stages,
        measured_percent=measured,
    )
    return tuple(
        StageView(name=stage.name, weight=stage.weight, percent=stage.percent)
        for stage in state.entries.stages
    )


def _measurement_views(
    session: Session, item_id: int, people: Mapping[int, str]
) -> tuple[MeasurementView, ...]:
    statement = (
        select(EapMeasurement)
        .where(EapMeasurement.item_id == item_id)
        .order_by(EapMeasurement.measured_on.desc(), EapMeasurement.id.desc())
    )
    return tuple(
        MeasurementView(
            measured_on=record.measured_on,
            from_percent=record.from_percent,
            to_percent=record.to_percent,
            author=people.get(record.author_id, "") if record.author_id else "",
            note=record.note or "",
        )
        for record in session.scalars(statement)
    )


# ── Carga de demonstração ────────────────────────────────────────────────


@dataclass(frozen=True)
class NewPackage:
    """The data of an item of the EAP to create: the place in the tree and what the package carries."""

    project_id: int
    code: str
    description: str
    level: int
    parent_id: int | None = None
    kind: str | None = None
    criterion: str | None = None
    stage_model: str | None = None
    unit_id: int | None = None
    quantity: Decimal | None = None
    weight: Decimal | None = None
    planned: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    company_id: int | None = None
    responsible_id: int | None = None
    eac_item_id: int | None = None
    deliverable: str | None = None
    acceptance: str | None = None


def create_item(session: Session, *, user_id: int, new: NewPackage) -> int:
    """Create an item of the tree through ``recording`` and return its id.

    The screen of ISSUE-036 never calls this: weights and structure change only by a revision
    (ISSUE-038). It is the door of the demonstration load and of the flows that follow.
    """
    item = EapItem(
        project_id=new.project_id,
        parent_id=new.parent_id,
        eac_item_id=new.eac_item_id,
        unit_id=new.unit_id,
        company_id=new.company_id,
        responsible_id=new.responsible_id,
        code=new.code,
        description=new.description,
        level=new.level,
        kind=new.kind,
        criterion=new.criterion,
        stage_model=new.stage_model,
        quantity=new.quantity,
        weight=new.weight,
        planned=new.planned,
        start_date=new.start_date,
        end_date=new.end_date,
        deliverable=new.deliverable,
        acceptance=new.acceptance,
    )
    recording.create(session, user_id=user_id, record=item)
    return item.id


def add_stages(
    session: Session, *, user_id: int, item_id: int, stages: Sequence[tuple[str, Decimal]]
) -> None:
    """Write the stages of a package of the Etapas criterion, in order, with the trail."""
    for order, (name, weight) in enumerate(stages, start=1):
        _add_fact(
            session,
            user_id=user_id,
            record=EapItemStage(item_id=item_id, order=order, name=name, weight=weight),
        )


@dataclass(frozen=True)
class NewMeasurement:
    """A measurement to write: the package, the date, the accumulated percentage before and after."""

    item_id: int
    measured_on: date
    from_percent: Decimal
    to_percent: Decimal
    author_id: int | None = None
    note: str | None = None


def add_measurement(session: Session, *, user_id: int, new: NewMeasurement) -> None:
    """Write a measurement, an immutable fact, with the trail."""
    _add_fact(
        session,
        user_id=user_id,
        record=EapMeasurement(
            item_id=new.item_id,
            author_id=new.author_id,
            measured_on=new.measured_on,
            from_percent=new.from_percent,
            to_percent=new.to_percent,
            note=new.note,
        ),
    )


@dataclass(frozen=True)
class NewRevision:
    """A revision to write: its place in the project, who approved it and the weights it freezes."""

    project_id: int
    number: int
    revised_on: date
    change: str
    justification: str
    change_id: int | None = None
    approved_by_id: int | None = None
    frozen_weights: Mapping[int, Decimal] | None = None


def create_revision(session: Session, *, user_id: int, new: NewRevision) -> int:
    """Create a revision and freeze the weights it carries (exception of D5b); return its id."""
    revision = EapRevision(
        project_id=new.project_id,
        change_id=new.change_id,
        approved_by_id=new.approved_by_id,
        number=new.number,
        revised_on=new.revised_on,
        change=new.change,
        justification=new.justification,
    )
    recording.create(session, user_id=user_id, record=revision)
    for item_id, weight in (new.frozen_weights or {}).items():
        _add_fact(
            session,
            user_id=user_id,
            record=EapRevisionItem(revision_id=revision.id, item_id=item_id, weight=weight),
        )
    return revision.id


@dataclass(frozen=True)
class NewSplit:
    """A split to write: the planning package, the work package that receives the weight, and why."""

    project_id: int
    source_item_id: int
    target_item_id: int
    revision: int
    split_on: date
    weight: Decimal
    justification: str
    by_id: int | None = None


def add_split(session: Session, *, user_id: int, new: NewSplit) -> None:
    """Write a split of a planning package, an immutable fact, with the trail."""
    _add_fact(
        session,
        user_id=user_id,
        record=EapSplit(
            project_id=new.project_id,
            source_item_id=new.source_item_id,
            target_item_id=new.target_item_id,
            by_id=new.by_id,
            revision=new.revision,
            split_on=new.split_on,
            weight=new.weight,
            justification=new.justification,
        ),
    )


def _add_fact(session: Session, *, user_id: int, record: Any) -> None:
    """Insert a record that has no version of its own and leave the trail line of creation."""
    session.add(record)
    session.flush()
    audit.created(session, user_id=user_id, entity=record.__tablename__, record=record)


def package_count(session: Session, *, project_id: int) -> int:
    """How many packages (level 3) the project has on its EAP."""
    statement = (
        select(func.count())
        .select_from(EapItem)
        .where(EapItem.project_id == project_id, EapItem.level == calculations.PACKAGE_LEVEL)
    )
    return session.scalar(statement) or 0
