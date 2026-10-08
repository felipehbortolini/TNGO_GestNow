"""Business facade for the Planning module.

Relato do período (ISSUE-044, HU-046): the weekly (ISO week) and the monthly (civil month)
report of a project, two distinct records. A person registers what was done in the period,
what comes in the next one and the attention points, each with the risk tied to it (a threat
or an opportunity, the planning reading with no link to the 05 register). The period goes
from the start of the project to the current one: a future period is refused, a duplicate is
refused (the existing one is edited) and the type and the period never change after creation.

Writes go through here, in the transaction of the request. The report is an aggregate: the
activities and the attention points are its children, edited together and protected by the
``versao`` of the root, so the facade composes ``versioning`` and ``audit`` itself (the trail
carries the whole content, before and after). Nothing reads the clock: the caller passes the
date of reference, obtained from ``core.calendario``.


The 6WLA (ISSUE-045): the board of the six weeks, the activities and their
restrictions. Every function receives the session, the user, the scope and the
reference date as arguments; nothing here reads the clock (D6). Writing goes
through ``core.recording`` (trail, version and transaction together), and the
registers of other modules (projects, companies, people, disciplines) are read
through the facade of Configurações.

The WBS (ISSUE-036): the tree of the project (area, subarea and package) and the
read-only tree of the Portfólio (portfolio, project with its weight in the
portfolio and the areas), the dictionary of the package and the indicator of the
SMs still to incorporate. The real of each package comes from the current
entries of its measuring criterion (D5b), the nodes add up the children by
weight (the 100% rule) and the deviation uses the bands of the parameters in
force. The weight of the project in the portfolio and the EAC item of the
dictionary come from the Financeiro facade, imported locally (D9); the approved
SMs come from the Governança facade. Nothing here reads the clock (D6).

The physical S-curve (ISSUE-039): the frozen baseline of each EAP revision, the
real from the dated measurements of the packages (D6) and the trend by the rule
of the prototype. ``freeze_curve`` runs inside ``create_revision``; the read
side lives in ``curva_fisica_overview``, which also serves the weekly payload of
the DS curve. In the Portfólio the curve is the weighted average of the projects
by the weights of the portfolio (D8), in the calendar of the union of months.

The planning KPIs (ISSUE-040): ``planning_kpis_overview`` serves the SPI screen,
which calculates the advance with no record of its own. The rows are the level-1
areas of the EAP, whose weighted average closes with the physical S-curve; in
the Portfólio the rows are the projects with their weight in the portfolio and
the SPI is the weighted one of the portfolio. The attention figures of the EAP
(overdue packages and change requests still to incorporate) come from the same
reading of ``eap_overview``. The chart payloads follow the DS library (D11) and
the business labels live in the templates. Nothing here reads the clock (D6).

The field hours (ISSUE-047): ``hours_overview`` serves the Horas efetivas tab —
the journey of each front and day, the observation round of the work sampling
with its reasons, the stoppage of crew or machine, and the summaries (capacity,
share, Pareto, Hhora and Mhora) of the period. Writing goes through
``save_field_day``, ``save_work_sample`` and ``save_stoppage``, with the trail
and the version; the second day of the same front is refused. The foreman is
text typed by the inspector, as in the prototype, not a person register; the
observer and the recorder of the record are people. Nothing here reads the clock
(D6).

The performance KPIs (ISSUE-048): ``performance_overview`` serves the KPIs tab —
the general block and one per company (per project and company in the Portfólio)
with the quantities of the window of N weeks until the cut, the field summaries
of the same window, the schedule trend, the weekly trend of twelve weeks and the
bands of the five indicators. ``create_performance_action`` opens the plan of
action in the Central through the single seam (D9), one open action per company
and week, referenced as ``PRD-2026-S39-01``; the Central links back to this tab
with the company and the week. Nothing here reads the clock (D6).
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, selectinload

from src.core import audit, calendario, origin_links, rbac, recording, versioning
from src.core.audit import TrailLine
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.import_values import normalize_text
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, validation
from src.modulos.planejamento.models import (
    CurvaFisicaMonth,
    CurvaFisicaRevision,
    EapBreakdown,
    EapItem,
    EapItemStep,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
    FieldDay,
    Lookahead,
    LookaheadConstraint,
    LookaheadWeek,
    ProductivityDistribution,
    ProductivityEntry,
    ProductivityItem,
    ProductivityRevision,
    Report,
    ReportActivity,
    ReportPoint,
    Stoppage,
    WorkSample,
    WorkSampleReason,
)
from src.modulos.planejamento.validation import MONTHLY, WEEKLY, PointInput

if TYPE_CHECKING:
    from src.modulos.governanca.service import ChangeEapSource

MODULE = "planejamento"


# ── Produtividade: quantidades, LB e apontamento (ISSUE-046) ──────────────


PRODUCTIVITY_GROUP = "produtividade"


# First key of the advisory lock that serializes the code of a new item of a project.
ITEM_CODE_LOCK = 4601


ITEM_NOT_FOUND_MESSAGE = "O item da linha de base não foi encontrado."


ITEM_PROJECT_MESSAGE = "O item pertence a outro projeto: abra a tela no projeto dele."


ITEM_DELETE_MESSAGE = "Só item em elaboração e sem apontamento pode ser excluído."


ITEM_APPROVED_EDIT_MESSAGE = (
    "A linha de base aprovada só muda por revisão com SM aprovada; salve aqui só as observações."
)


ITEM_ALREADY_APPROVED_MESSAGE = "O item já está aprovado."


ITEM_ONLY_MANAGER_MESSAGE = "Só o papel Gestor aprova a linha de base."


ITEM_SELF_APPROVAL_MESSAGE = (
    "Quem elaborou a distribuição não pode aprová-la (segregação de funções)."
)


ITEM_DRAFT_REVISION_MESSAGE = "Item em elaboração não precisa de revisão: edite a distribuição."


PROFILE_LABELS: Mapping[str, str] = {
    "curvaS": "Curva S (rampa, pico e desmobilização)",
    "linear": "Linear (uniforme)",
    "inicio": "Concentrado no início",
    "fim": "Concentrado no fim",
}


DEFAULT_WINDOW_WEEKS = 4


DEFAULT_ADHERENCE_BANDS = (Decimal("75"), Decimal("90"))


DEFAULT_PF_BANDS = (Decimal("1"), Decimal("1.1"))


DEFAULT_SPI_BANDS = (Decimal("0.85"), Decimal("0.95"))


DEFAULT_DAILY_HOURS = Decimal("8.8")


DEFAULT_WORKING_PCT = Decimal("60")


DEFAULT_UTILIZATION_PCT = Decimal("75")


# The window of weeks the form offers around the reference week: one year back, 18 months ahead.
FORM_WEEKS_BACK = 52


FORM_WEEKS_AHEAD = 78


@dataclass(frozen=True)
class ProductivityParameters:
    """O grupo ``produtividade`` dos parâmetros vigentes, com os valores iniciais de reserva."""

    window_weeks: int
    adherence_bands: tuple[Decimal, Decimal]
    pf_bands: tuple[Decimal, Decimal]
    spi_bands: tuple[Decimal, Decimal]
    delay_bands: tuple[Decimal, Decimal]
    daily_hours: Decimal
    working_pct: Decimal
    utilization_pct: Decimal


@dataclass(frozen=True)
class QuantityFilter:
    """O filtro da aba Quantidades: empresa, grupo e semana de corte (vazio é o padrão)."""

    company_id: int | None = None
    group: str = ""
    cut_week: str = ""


@dataclass(frozen=True)
class QuantityItemView:
    """Um item do plano como a tela o lê, com os indicadores calculados no corte (D5b)."""

    id: int
    project_id: int
    project_code: str
    project_name: str
    code: str
    company_id: int
    company_name: str
    group: str
    kind: str
    discipline: str
    unit: str
    places: int
    total: Decimal
    index_hh: Decimal
    profile: str
    profile_name: str
    situation: str
    revision: int
    start_week: str
    finish_week: str
    approved_by: str
    approved_on: date | None
    notes: str
    version: int
    figures: calculations.ItemFigures

    @property
    def project_label(self) -> str:
        """``TN-2026-014 · Nome do projeto``: como o Portfólio nomeia o projeto de uma linha."""
        return f"{self.project_code} · {self.project_name}"

    @property
    def approved(self) -> bool:
        """Se a linha de base do item está aprovada (fora daqui ele não entra nos indicadores)."""
        return self.situation == calculations.ITEM_APPROVED


@dataclass(frozen=True)
class ItemRevisionView:
    """Uma revisão da linha de base como a ficha do item a lê."""

    revision: int
    revision_date: date
    author: str
    total: Decimal
    previous_total: Decimal | None
    change_code: str
    since: str
    justification: str


@dataclass(frozen=True)
class ItemDetailView:
    """A ficha do item: os indicadores, as semanas e o histórico de revisões."""

    item: QuantityItemView
    weeks: tuple[calculations.ItemWeek, ...]
    revisions: tuple[ItemRevisionView, ...]


@dataclass(frozen=True)
class QuantityOption:
    """Uma opção de filtro ou de formulário: o valor que viaja e o texto que se lê."""

    value: str
    label: str


@dataclass(frozen=True)
class QuantitiesOverview:
    """A aba Quantidades: filtros, indicadores, grupos, série e o plano de itens."""

    reference_date: date
    current_week: str
    cut_week: str
    cut_options: tuple[str, ...]
    company_options: tuple[QuantityOption, ...]
    group_options: tuple[str, ...]
    filter: QuantityFilter
    items: tuple[QuantityItemView, ...]
    groups: tuple[calculations.GroupSummary, ...]
    indicators: calculations.QuantityIndicators
    weekly: dict[str, Any]
    accumulated: dict[str, Any]
    unit_series: str
    draft_count: int
    parameters: ProductivityParameters
    is_portfolio: bool
    can_write: bool
    can_manage: bool


@dataclass(frozen=True)
class ItemFormOptions:
    """O que o formulário do item oferece: os cadastros, os grupos e as semanas da janela."""

    companies: tuple[configuracoes.RegisterOption, ...]
    units: tuple[configuracoes.MeasureUnitSummary, ...]
    disciplines: tuple[str, ...]
    groups: tuple[str, ...]
    profiles: tuple[QuantityOption, ...]
    week_options: tuple[str, ...]


@dataclass(frozen=True)
class ItemFormView:
    """O formulário do item pronto para o template: valores, grade, erros e o estado."""

    item: QuantityItemView | None
    fields: Mapping[str, str]
    planned: tuple[calculations.PlannedWeek, ...]
    weeks: tuple[str, ...]
    options: ItemFormOptions
    errors: Mapping[str, str]
    locked: bool
    default_total: Decimal | None


@dataclass(frozen=True)
class RevisionOption:
    """Uma SM aprovada do projeto que o formulário da revisão oferece."""

    code: str
    title: str


@dataclass(frozen=True)
class RevisionFormView:
    """O formulário da revisão pronto para o template: SM, grade livre e o congelado."""

    item: QuantityItemView
    fields: Mapping[str, str]
    frozen: tuple[calculations.PlannedWeek, ...]
    frozen_total: Decimal
    planned: tuple[calculations.PlannedWeek, ...]
    free_weeks: tuple[str, ...]
    first_free_week: str
    realized: Decimal
    options: ItemFormOptions
    changes: tuple[RevisionOption, ...]
    errors: Mapping[str, str]


@dataclass(frozen=True)
class EntryRow:
    """A linha do apontamento: o item, o previsto da semana e o apontamento que já existe."""

    item: QuantityItemView
    planned_week: Decimal
    realized: Decimal | None
    hh: Decimal | None


@dataclass(frozen=True)
class EntryFormView:
    """O formulário da semana pronta para o template: a grade dos itens da empresa."""

    week: str
    cut_week: str
    company_id: int | None
    company_options: tuple[QuantityOption, ...]
    week_options: tuple[str, ...]
    rows: tuple[EntryRow, ...]
    errors: Mapping[str, str]


def productivity_parameters(session: Session, *, reference_date: date) -> ProductivityParameters:
    """O grupo ``produtividade`` dos parâmetros vigentes, com os valores iniciais de reserva."""
    values = (
        configuracoes.current_group(
            session, group=PRODUCTIVITY_GROUP, reference_date=reference_date
        )
        or configuracoes.INITIAL_PARAMETERS[PRODUCTIVITY_GROUP]
    )
    return ProductivityParameters(
        window_weeks=_integer_value(values.get("semanasMedia"), DEFAULT_WINDOW_WEEKS),
        adherence_bands=_bands(values.get("aderenciaFaixas"), DEFAULT_ADHERENCE_BANDS),
        pf_bands=_bands(values.get("pfFaixas"), DEFAULT_PF_BANDS),
        spi_bands=_bands(values.get("spiFaixas"), DEFAULT_SPI_BANDS),
        delay_bands=_bands(values.get("atrasoInicioFaixasMin"), DEFAULT_DELAY_BANDS),
        daily_hours=_decimal_value(values.get("jornadaDiariaHoras"), DEFAULT_DAILY_HOURS),
        working_pct=_decimal_value(values.get("metaTrabalhandoPct"), DEFAULT_WORKING_PCT),
        utilization_pct=_decimal_value(values.get("metaUtilizacaoPct"), DEFAULT_UTILIZATION_PCT),
    )


def _bands(value: Any, default: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    if not isinstance(value, Sequence) or isinstance(value, str) or len(value) != 2:
        return default
    return (_decimal_value(value[0], default[0]), _decimal_value(value[1], default[1]))


def _integer_value(value: Any, default: int) -> int:
    try:
        found = int(value)
    except (TypeError, ValueError):
        return default
    return found if found > 0 else default


def quantities_overview(
    session: Session,
    *,
    user: User,
    scope: Scope,
    quantity_filter: QuantityFilter | None = None,
    reference_date: date,
) -> QuantitiesOverview:
    """A aba Quantidades do escopo: os filtros, o plano e os indicadores do corte.

    O corte vem do filtro, limitado à semana corrente; fora dele vale a semana corrente. Os
    indicadores e a série só contam os itens aprovados (D5b); os itens em elaboração aparecem
    na lista e no aviso, fora dos indicadores.
    """
    rbac.require_module(user, MODULE)
    chosen = quantity_filter or QuantityFilter()
    reference_week = calendario.iso_week(reference_date)
    cut_week = _cut_week(chosen.cut_week, reference_week)
    records = _items_in(session, scope)
    lookups = _item_lookups(session, records)
    reads = [
        _item_read(record, lookups=lookups, cut_week=cut_week, current_week=reference_week)
        for record in records
    ]
    kept = [item for item in reads if _passes_quantity_filter(item.view, chosen)]
    approved = [item for item in kept if item.view.approved]
    indicators = calculations.quantities_indicators([item.view.figures for item in approved])
    in_hours, unit_series = _series_mode(approved, chosen)
    series = calculations.quantities_series(
        [
            calculations.SeriesItem(
                total=item.view.total,
                index_hh=item.view.index_hh,
                planned=item.planned,
                reported=item.reported,
            )
            for item in approved
        ],
        current_week=reference_week,
        in_hours=in_hours,
        unit=unit_series,
    )
    return QuantitiesOverview(
        reference_date=reference_date,
        current_week=reference_week,
        cut_week=cut_week,
        cut_options=_cut_options(records, reference_week),
        company_options=_company_options(records, lookups),
        group_options=tuple(sorted({record.group for record in records})),
        filter=QuantityFilter(company_id=chosen.company_id, group=chosen.group, cut_week=cut_week),
        items=tuple(item.view for item in kept),
        groups=calculations.group_summaries(
            [
                calculations.GroupedItem(
                    group=item.view.group,
                    unit=item.view.unit,
                    places=item.view.places,
                    total=item.view.total,
                    figures=item.view.figures,
                )
                for item in approved
            ]
        ),
        indicators=indicators,
        weekly=calculations.weekly_chart(series),
        accumulated=calculations.accumulated_chart(series),
        unit_series=unit_series,
        draft_count=sum(1 for item in kept if not item.view.approved),
        parameters=productivity_parameters(session, reference_date=reference_date),
        is_portfolio=scope.is_portfolio,
        can_write=rbac.can(user, Permission.WRITE),
        can_manage=rbac.can(user, Permission.MANAGE),
    )


def _cut_week(requested: str, reference_week: str) -> str:
    """A semana de corte: a pedida quando válida e não futura; senão a semana corrente."""
    if not requested or calculations.week_start(requested) is None:
        return reference_week
    return requested if requested <= reference_week else reference_week


def _items_in(session: Session, scope: Scope) -> list[ProductivityItem]:
    statement = (
        select(ProductivityItem)
        .options(
            selectinload(ProductivityItem.revisions).selectinload(
                ProductivityRevision.distributions
            ),
            selectinload(ProductivityItem.entries),
        )
        .execution_options(populate_existing=True)
    )
    if scope.project_id is not None:
        statement = statement.where(ProductivityItem.project_id == scope.project_id)
    return list(session.scalars(statement.order_by(ProductivityItem.code, ProductivityItem.id)))


@dataclass(frozen=True)
class _ItemLookups:
    """Os nomes que a linha do plano e a ficha leem, carregados uma vez por consulta."""

    projects: Mapping[int, configuracoes.ProjectSummary]
    companies: Mapping[int, str]
    units: Mapping[int, str]
    disciplines: Mapping[int, str]
    people: Mapping[int, str]


def _item_lookups(session: Session, records: Sequence[ProductivityItem]) -> _ItemLookups:
    project_ids = {record.project_id for record in records}
    projects = {
        project.id: project
        for project in configuracoes.list_projects(session)
        if project.id in project_ids
    }
    return _ItemLookups(
        projects=projects,
        companies=configuracoes.list_company_names(session),
        units={unit.id: unit.code for unit in configuracoes.list_measure_units(session)},
        disciplines=configuracoes.discipline_names_by_id(session),
        people=configuracoes.person_names(
            session,
            {record.approved_by_id for record in records if record.approved_by_id is not None}
            | {revision.by_id for record in records for revision in record.revisions},
        ),
    )


@dataclass(frozen=True)
class _ItemRead:
    """Um item lido: o registro, a visão da tela e os fatos que a série semanal consome."""

    record: ProductivityItem
    view: QuantityItemView
    planned: tuple[calculations.PlannedWeek, ...]
    reported: tuple[calculations.ReportedWeek, ...]


def _item_read(
    record: ProductivityItem,
    *,
    lookups: _ItemLookups,
    cut_week: str,
    current_week: str,
    window_weeks: int = DEFAULT_WINDOW_WEEKS,
) -> _ItemRead:
    planned = _planned_of(record)
    reported = _reported_of(record)
    return _ItemRead(
        record=record,
        view=_item_view(
            record,
            lookups=lookups,
            planned=planned,
            reported=reported,
            cut_week=cut_week,
            current_week=current_week,
            window_weeks=window_weeks,
        ),
        planned=planned,
        reported=reported,
    )


def _item_view(
    record: ProductivityItem,
    *,
    lookups: _ItemLookups,
    planned: Sequence[calculations.PlannedWeek],
    reported: Sequence[calculations.ReportedWeek],
    cut_week: str,
    current_week: str,
    window_weeks: int = DEFAULT_WINDOW_WEEKS,
) -> QuantityItemView:
    project = lookups.projects[record.project_id]
    start_week = calendario.iso_week(record.start)
    finish_week = calendario.iso_week(record.finish)
    unit = lookups.units.get(record.unit_id, "")
    places = record.places
    figures = calculations.item_figures(
        start_week=start_week,
        finish_week=finish_week,
        total=record.total,
        index_hh=record.index_hh,
        places=places,
        situation=record.situation,
        planned=planned,
        reported=reported,
        cut_week=cut_week,
        current_week=current_week,
        window_weeks=window_weeks,
    )
    return QuantityItemView(
        id=record.id,
        project_id=record.project_id,
        project_code=project.code,
        project_name=project.name,
        code=record.code,
        company_id=record.company_id,
        company_name=lookups.companies.get(record.company_id, ""),
        group=record.group,
        kind=record.kind,
        discipline=(
            lookups.disciplines.get(record.discipline_id, "")
            if record.discipline_id is not None
            else ""
        ),
        unit=unit,
        places=places,
        total=record.total,
        index_hh=record.index_hh,
        profile=record.profile,
        profile_name=PROFILE_LABELS.get(record.profile, record.profile),
        situation=record.situation,
        revision=record.revision,
        start_week=start_week,
        finish_week=finish_week,
        approved_by=(
            lookups.people.get(record.approved_by_id, "")
            if record.approved_by_id is not None
            else ""
        ),
        approved_on=record.approved_on,
        notes=record.notes or "",
        version=record.version,
        figures=figures,
    )


def _planned_of(record: ProductivityItem) -> tuple[calculations.PlannedWeek, ...]:
    revision = _baseline_revision(record)
    if revision is None:
        return ()
    return tuple(
        calculations.PlannedWeek(week=line.week, planned=line.planned)
        for line in revision.distributions
    )


def _reported_of(record: ProductivityItem) -> tuple[calculations.ReportedWeek, ...]:
    return tuple(
        calculations.ReportedWeek(week=entry.week, realized=entry.realized, hh=entry.hh)
        for entry in record.entries
    )


def _baseline_revision(record: ProductivityItem) -> ProductivityRevision | None:
    if not record.revisions:
        return None
    return max(record.revisions, key=lambda item: item.revision)


def _passes_quantity_filter(view: QuantityItemView, chosen: QuantityFilter) -> bool:
    if chosen.company_id is not None and view.company_id != chosen.company_id:
        return False
    return not (chosen.group and view.group != chosen.group)


def _series_mode(approved: Sequence[_ItemRead], chosen: QuantityFilter) -> tuple[bool, str]:
    """A série sai em horas ganhas quando o filtro mistura unidades; senão, na unidade do grupo."""
    units = {item.view.unit for item in approved}
    in_hours = not chosen.group or len(units) > 1
    if in_hours:
        return True, "HH"
    return False, next(iter(units), "")


def _cut_options(records: Sequence[ProductivityItem], reference_week: str) -> tuple[str, ...]:
    starts = {
        calendario.iso_week(record.start)
        for record in records
        if calendario.iso_week(record.start) <= reference_week
    }
    first = min(starts, default=reference_week)
    return tuple(calculations.list_weeks(first, reference_week))


def _company_options(
    records: Sequence[ProductivityItem], lookups: _ItemLookups
) -> tuple[QuantityOption, ...]:
    ids = sorted({record.company_id for record in records})
    return tuple(
        QuantityOption(value=str(company_id), label=lookups.companies.get(company_id, ""))
        for company_id in ids
        if lookups.companies.get(company_id)
    )


def item_detail(
    session: Session, *, user: User, scope: Scope, item_id: int, reference_date: date
) -> ItemDetailView:
    """A ficha do item: a visão no corte, as semanas e o histórico de revisões."""
    rbac.require_module(user, MODULE)
    record = _scoped_item(session, scope, item_id)
    reference_week = calendario.iso_week(reference_date)
    lookups = _item_lookups(session, [record])
    read = _item_read(record, lookups=lookups, cut_week=reference_week, current_week=reference_week)
    changes = _revision_change_codes(session, project_id=record.project_id)
    names = configuracoes.person_names(session, {revision.by_id for revision in record.revisions})
    return ItemDetailView(
        item=read.view,
        weeks=calculations.item_weeks(
            start_week=read.view.start_week,
            total=record.total,
            index_hh=record.index_hh,
            places=record.places,
            situation=record.situation,
            planned=read.planned,
            reported=read.reported,
            current_week=reference_week,
        ),
        revisions=tuple(
            ItemRevisionView(
                revision=revision.revision,
                revision_date=revision.revision_date,
                author=names.get(revision.by_id, ""),
                total=revision.total,
                previous_total=revision.previous_total,
                change_code=(
                    changes.get(revision.change_id, "") if revision.change_id is not None else ""
                ),
                since=revision.since or "",
                justification=revision.justification,
            )
            for revision in sorted(record.revisions, key=lambda item: item.revision, reverse=True)
        ),
    )


def _revision_change_codes(session: Session, *, project_id: int) -> dict[int, str]:
    from src.modulos.governanca import service as governanca

    revision = session.scalars(
        select(ProductivityRevision.change_id)
        .join(ProductivityItem, ProductivityItem.id == ProductivityRevision.item_id)
        .where(ProductivityItem.project_id == project_id)
    ).all()
    return governanca.change_codes(
        session, change_ids=[found for found in revision if found is not None]
    )


# ── Formulários ───────────────────────────────────────────────────────────


def item_form_options(session: Session, *, reference_date: date) -> ItemFormOptions:
    """O que o formulário do item oferece: cadastros, grupos, perfis e a janela de semanas."""
    first = calculations.shift_week(calendario.iso_week(reference_date), -FORM_WEEKS_BACK)
    last = calculations.shift_week(calendario.iso_week(reference_date), FORM_WEEKS_AHEAD)
    return ItemFormOptions(
        companies=tuple(configuracoes.list_company_options(session)),
        units=tuple(configuracoes.list_measure_units(session)),
        disciplines=tuple(configuracoes.list_discipline_names(session)),
        groups=validation.QUANTITY_GROUPS,
        profiles=tuple(
            QuantityOption(value=profile, label=PROFILE_LABELS[profile])
            for profile in calculations.PROFILES
        ),
        week_options=(
            calculations.list_weeks(first, last) if first is not None and last is not None else ()
        ),
    )


def item_form(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int | None,
    form: validation.ItemForm | None,
    reference_date: date,
    errors: Mapping[str, str] | None = None,
) -> ItemFormView:
    """O formulário do item: em branco, reaberto com o que foi digitado, ou o item em edição."""
    rbac.require_module(user, MODULE)
    options = item_form_options(session, reference_date=reference_date)
    record = _scoped_item(session, scope, item_id) if item_id is not None else None
    view = _single_view(session, record, reference_date) if record is not None else None
    if form is not None:
        fields = dict(form.fields)
        planned = computed_planned(fields)
        return ItemFormView(
            item=view,
            fields=fields,
            planned=planned,
            weeks=tuple(line.week for line in planned),
            options=options,
            errors=errors or {},
            locked=False,
            default_total=None,
        )
    if view is not None and record is not None:
        fields = item_fields(view)
        planned = (
            ()
            if view.approved
            else tuple(
                calculations.PlannedWeek(week=line.week, planned=line.planned)
                for line in _planned_of(record)
            )
        )
        return ItemFormView(
            item=view,
            fields=fields,
            planned=planned,
            weeks=tuple(line.week for line in planned),
            options=options,
            errors=errors or {},
            locked=view.approved,
            default_total=view.total,
        )
    fields = _new_item_fields(reference_date)
    planned = computed_planned(fields)
    return ItemFormView(
        item=None,
        fields=fields,
        planned=planned,
        weeks=tuple(line.week for line in planned),
        options=options,
        errors=errors or {},
        locked=False,
        default_total=None,
    )


def _new_item_fields(reference_date: date) -> dict[str, str]:
    start = calculations.shift_week(calendario.iso_week(reference_date), 1) or ""
    finish = calculations.shift_week(calendario.iso_week(reference_date), 12) or ""
    return {
        "unidade": "m",
        "inicio": start,
        "fim": finish,
        "perfil": calculations.PROFILE_S_CURVE,
    }


def computed_planned(fields: Mapping[str, str]) -> tuple[calculations.PlannedWeek, ...]:
    """A grade do formulário calculada dos campos digitados: total, semanas, perfil e unidade."""
    total = _decimal_or_zero(fields.get("total"))
    unit = (fields.get("unidade") or "").strip()
    start_week = (fields.get("inicio") or "").strip()
    finish_week = (fields.get("fim") or "").strip()
    profile = (fields.get("perfil") or "").strip()
    if calculations.week_start(start_week) is None or calculations.week_start(finish_week) is None:
        return ()
    if finish_week < start_week:
        return ()
    weeks = calculations.list_weeks(start_week, finish_week)
    if not weeks or len(weeks) > validation.ITEM_MAX_WEEKS:
        return ()
    if profile not in calculations.PROFILES:
        profile = calculations.PROFILE_LINEAR
    places = calculations.places_for_unit(unit)
    values = calculations.distribute_total(total, len(weeks), profile, places)
    return tuple(
        calculations.PlannedWeek(week=week, planned=value)
        for week, value in zip(weeks, values, strict=True)
    )


def _decimal_or_zero(text: str | None) -> Decimal:
    try:
        value = Decimal((text or "").strip())
    except ArithmeticError:
        return Decimal(0)
    return value if value.is_finite() and value > 0 else Decimal(0)


def revision_form(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    form: validation.RevisionForm | None,
    reference_date: date,
    errors: Mapping[str, str] | None = None,
) -> RevisionFormView:
    """O formulário da revisão: o congelado, a grade livre e as SM aprovadas do projeto."""
    rbac.require_module(user, MODULE)
    record = _scoped_item(session, scope, item_id)
    if record.situation != calculations.ITEM_APPROVED:
        raise InvalidDataError(ITEM_DRAFT_REVISION_MESSAGE)
    options = item_form_options(session, reference_date=reference_date)
    reference_week = calendario.iso_week(reference_date)
    planned = _planned_of(record)
    frozen = calculations.frozen_planned(planned, reference_week)
    frozen_total = sum((line.planned for line in frozen), Decimal(0))
    first_free = calculations.first_free_week(calendario.iso_week(record.start), reference_week)
    view = _single_view(session, record, reference_date)
    changes = revision_change_options(session, project_id=record.project_id)
    fields = {
        "total": _plain_decimal(record.total),
        "fim": max(view.finish_week, first_free),
        "perfil": calculations.PROFILE_LINEAR,
    }
    if form is not None:
        fields = dict(form.fields)
    free_weeks = _free_weeks(fields, first_free)
    planned_free = frozen_revision_planned(
        fields, frozen_total=frozen_total, free_weeks=free_weeks, places=record.places
    )
    return RevisionFormView(
        item=view,
        fields=fields,
        frozen=frozen,
        frozen_total=frozen_total,
        planned=planned_free,
        free_weeks=free_weeks,
        first_free_week=first_free,
        realized=sum(
            (entry.realized for entry in record.entries if entry.week <= reference_week),
            Decimal(0),
        ),
        options=options,
        changes=changes,
        errors=errors or {},
    )


def _free_weeks(fields: Mapping[str, str], first_free: str) -> tuple[str, ...]:
    finish = (fields.get("fim") or "").strip()
    if calculations.week_start(finish) is None or finish < first_free:
        return ()
    weeks = calculations.list_weeks(first_free, finish)
    return weeks if len(weeks) <= validation.ITEM_MAX_WEEKS else ()


def frozen_revision_planned(
    fields: Mapping[str, str],
    *,
    frozen_total: Decimal,
    free_weeks: Sequence[str],
    places: int,
) -> tuple[calculations.PlannedWeek, ...]:
    """A grade livre do formulário da revisão: o saldo (novo total menos o congelado) no perfil."""
    total = _decimal_or_zero(fields.get("total"))
    profile = (fields.get("perfil") or "").strip()
    if profile not in calculations.PROFILES:
        profile = calculations.PROFILE_LINEAR
    balance = max(Decimal(0), total - frozen_total)
    values = calculations.distribute_total(balance, len(free_weeks), profile, places)
    return tuple(
        calculations.PlannedWeek(week=week, planned=value)
        for week, value in zip(free_weeks, values, strict=True)
    )


def revision_change_options(session: Session, *, project_id: int) -> tuple[RevisionOption, ...]:
    """As SM aprovadas do projeto, que a revisão da linha de base exige (D9)."""
    from src.modulos.governanca import service as governanca

    return tuple(
        RevisionOption(code=change.code, title=change.title)
        for change in governanca.approved_changes(session, project_id=project_id)
    )


def entry_form(
    session: Session,
    *,
    user: User,
    scope: Scope,
    company_id: int | None,
    week: str,
    reference_date: date,
) -> EntryFormView:
    """O formulário do apontamento: os itens aprovados da empresa na semana, com o que já existe."""
    rbac.require_module(user, MODULE)
    reference_week = calendario.iso_week(reference_date)
    cut_week = _cut_week(week, reference_week)
    records = [
        record
        for record in _items_in(session, scope)
        if company_id is None or record.company_id == company_id
    ]
    lookups = _item_lookups(session, records)
    rows: list[EntryRow] = []
    for record in records:
        read = _item_read(record, lookups=lookups, cut_week=cut_week, current_week=reference_week)
        if not read.view.approved or read.view.start_week > cut_week:
            continue
        entry = next((line for line in read.reported if line.week == cut_week), None)
        if read.view.figures.balance <= 0 and entry is None:
            continue
        planned_week = next(
            (line.planned for line in read.planned if line.week == cut_week), Decimal(0)
        )
        rows.append(
            EntryRow(
                item=read.view,
                planned_week=planned_week,
                realized=None if entry is None else entry.realized,
                hh=None if entry is None else entry.hh,
            )
        )
    return EntryFormView(
        week=cut_week,
        cut_week=cut_week,
        company_id=company_id,
        company_options=_company_options(records, lookups),
        week_options=tuple(reversed(_cut_options(records, reference_week)[-13:]))
        if records
        else (),
        rows=tuple(rows),
        errors={},
    )


def item_fields(view: QuantityItemView) -> dict[str, str]:
    """Os valores do formulário do item para a edição: os mesmos nomes que o formulário manda."""
    return {
        "empresa": str(view.company_id),
        "grupo": view.group,
        "tipo": view.kind,
        "disciplina": view.discipline,
        "unidade": view.unit,
        "total": _plain_decimal(view.total),
        "indiceHH": _plain_decimal(view.index_hh),
        "inicio": view.start_week,
        "fim": view.finish_week,
        "perfil": view.profile,
        "observacoes": view.notes,
        "versao": str(view.version),
    }


def _plain_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _single_view(
    session: Session,
    record: ProductivityItem | None,
    reference_date: date,
) -> QuantityItemView:
    if record is None:
        raise InvalidDataError(ITEM_NOT_FOUND_MESSAGE)
    lookups = _item_lookups(session, [record])
    reference_week = calendario.iso_week(reference_date)
    return _item_read(
        record, lookups=lookups, cut_week=reference_week, current_week=reference_week
    ).view


# ── Escrita ───────────────────────────────────────────────────────────────


def save_item(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int | None,
    form: validation.ItemForm,
    reference_date: date,
) -> ProductivityItem:
    """Cria o item em elaboração ou grava a edição; item aprovado só aceita observações.

    A segregação de funções da aprovação se apoia na revisão 0, que nasce com o item e
    guarda quem elaborou a distribuição (``por_id``).
    """
    rbac.require(user, Permission.WRITE)
    record = _scoped_item(session, scope, item_id) if item_id is not None else None
    if record is not None and record.situation == calculations.ITEM_APPROVED:
        notes = validation.parse_notes(form.fields)
        _update_item(
            session,
            user=user,
            record=record,
            changes={"notes": notes},
            version=form.fields.get("versao"),
        )
        return record
    data = validation.parse_item(form, item_choices(session))
    planned = tuple(
        calculations.PlannedWeek(week=week, planned=value) for week, value in data.planned
    )
    if record is not None:
        _update_item(
            session,
            user=user,
            record=record,
            changes=_item_changes(session, data),
            version=form.fields.get("versao"),
        )
        _replace_baseline(
            session,
            record=record,
            data=data,
            planned=planned,
            author_id=user.person_id,
            reference_date=reference_date,
        )
        return record
    project_id = scope.require_project()
    session.execute(select(func.pg_advisory_xact_lock(ITEM_CODE_LOCK, cast(project_id, Integer))))
    codes = list(
        session.scalars(
            select(ProductivityItem.code)
            .where(ProductivityItem.project_id == project_id)
            .order_by(ProductivityItem.id)
        )
    )
    record = ProductivityItem(
        project_id=project_id,
        company_id=data.company_id,
        unit_id=_unit_id_for(session, data.unit),
        discipline_id=_discipline_id_for(session, data.discipline),
        approved_by_id=None,
        code=calculations.next_item_code(codes),
        group=data.group,
        kind=data.kind,
        places=data.places,
        total=data.total,
        index_hh=data.index_hh,
        profile=data.profile,
        situation=calculations.ITEM_DRAFT,
        revision=0,
        start=_week_date(data.start_week),
        finish=_week_date(data.finish_week),
        approved_on=None,
        notes=data.notes,
    )
    session.add(record)
    session.flush()
    revision = ProductivityRevision(
        item_id=record.id,
        by_id=user.person_id,
        change_id=None,
        revision=0,
        revision_date=reference_date,
        total=data.total,
        previous_total=None,
        since=data.start_week,
        justification="Linha de base original do cronograma.",
    )
    session.add(revision)
    session.flush()
    revision.distributions = [
        ProductivityDistribution(week=line.week, planned=line.planned) for line in planned
    ]
    session.flush()
    record.revisions.append(revision)
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=ProductivityItem.__tablename__,
            record_id=record.id,
            action=audit.CREATED,
            after=_item_aggregate(record),
            project_id=project_id,
        ),
    )
    return record


def item_choices(session: Session) -> validation.ItemChoices:
    """As escolhas do formulário do item: ids de empresa, códigos de unidade e disciplinas."""
    return validation.ItemChoices(
        company_ids=frozenset(option.id for option in configuracoes.list_company_options(session)),
        units=frozenset(unit.code for unit in configuracoes.list_measure_units(session)),
        disciplines=frozenset(configuracoes.list_discipline_names(session)),
    )


def _item_changes(session: Session, data: validation.ItemData) -> dict[str, Any]:
    return {
        "company_id": data.company_id,
        "unit_id": _unit_id_for(session, data.unit),
        "discipline_id": _discipline_id_for(session, data.discipline),
        "group": data.group,
        "kind": data.kind,
        "places": data.places,
        "total": data.total,
        "index_hh": data.index_hh,
        "profile": data.profile,
        "start": _week_date(data.start_week),
        "finish": _week_date(data.finish_week),
        "notes": data.notes,
    }


def _replace_baseline(
    session: Session,
    *,
    record: ProductivityItem,
    data: validation.ItemData,
    planned: Sequence[calculations.PlannedWeek],
    author_id: int,
    reference_date: date,
) -> None:
    """Atualiza a revisão 0, que segue o item enquanto ele está em elaboração."""
    revision = _baseline_revision(record)
    if revision is None:
        revision = ProductivityRevision(
            item_id=record.id,
            by_id=author_id,
            change_id=None,
            revision=0,
            revision_date=reference_date,
            total=data.total,
            previous_total=None,
            since=data.start_week,
            justification="Linha de base original do cronograma.",
        )
        session.add(revision)
        session.flush()
    revision.total = data.total
    revision.since = data.start_week
    revision.revision_date = reference_date
    revision.distributions = [
        ProductivityDistribution(week=line.week, planned=line.planned) for line in planned
    ]
    session.flush()


def _update_item(
    session: Session,
    *,
    user: User,
    record: ProductivityItem,
    changes: Mapping[str, Any],
    version: str | None,
) -> None:
    """Aplica a mudança depois da conferência de versão, deixando a trilha do agregado."""
    before = _item_aggregate(record)
    versioning.require(session, record, version)
    for attribute, value in changes.items():
        setattr(record, attribute, value)
    versioning.advance(record)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=ProductivityItem.__tablename__,
            record_id=record.id,
            action=audit.UPDATED,
            before=before,
            after=_item_aggregate(record),
            project_id=record.project_id,
        ),
    )


def _item_aggregate(record: ProductivityItem) -> dict[str, Any]:
    """O item e os filhos congelados como a trilha os guarda, nos nomes em português."""
    return {
        **audit.snapshot(record),
        "revisoes": [
            {
                "revisao": revision.revision,
                "data": revision.revision_date.isoformat(),
                "por_id": revision.by_id,
                "mudanca_id": revision.change_id,
                "total": str(revision.total),
                "total_anterior": (
                    None if revision.previous_total is None else str(revision.previous_total)
                ),
                "desde": revision.since,
                "justificativa": revision.justification,
                "distribuicao": [
                    {"semana": line.week, "previsto": str(line.planned)}
                    for line in revision.distributions
                ],
            }
            for revision in record.revisions
        ],
    }


def approve_item(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    version: str | None,
    reference_date: date,
) -> ProductivityItem:
    """Aprova a linha de base (Gestor); quem elaborou não aprova (segregação de funções)."""
    rbac.require(user, Permission.MANAGE)
    record = _scoped_item(session, scope, item_id)
    if record.situation != calculations.ITEM_DRAFT:
        raise InvalidDataError(ITEM_ALREADY_APPROVED_MESSAGE)
    author = _baseline_author(record)
    if author == user.person_id:
        raise AccessDeniedError(ITEM_SELF_APPROVAL_MESSAGE)
    _update_item(
        session,
        user=user,
        record=record,
        changes={
            "situation": calculations.ITEM_APPROVED,
            "approved_by_id": user.person_id,
            "approved_on": reference_date,
        },
        version=version,
    )
    return record


def _baseline_author(record: ProductivityItem) -> int | None:
    revision = next((item for item in record.revisions if item.revision == 0), None)
    return revision.by_id if revision is not None else None


def delete_item(
    session: Session, *, user: User, scope: Scope, item_id: int, version: str | None
) -> ProductivityItem:
    """Exclui um item em elaboração sem apontamento; um item aprovado nunca é excluído."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_item(session, scope, item_id)
    if record.situation != calculations.ITEM_DRAFT or record.entries:
        raise InvalidDataError(ITEM_DELETE_MESSAGE)
    before = _item_aggregate(record)
    versioning.require(session, record, version)
    project_id = record.project_id
    session.delete(record)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=ProductivityItem.__tablename__,
            record_id=item_id,
            action=audit.DELETED,
            before=before,
            project_id=project_id,
        ),
    )
    return record


def revise_item(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    form: validation.RevisionForm,
    reference_date: date,
) -> ProductivityItem:
    """Revisa a LB aprovada com SM aprovada: congela as semanas até a atual e redistribui o saldo."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_item(session, scope, item_id)
    if record.situation != calculations.ITEM_APPROVED:
        raise InvalidDataError(ITEM_DRAFT_REVISION_MESSAGE)
    reference_week = calendario.iso_week(reference_date)
    planned = _planned_of(record)
    frozen = calculations.frozen_planned(planned, reference_week)
    frozen_total = sum((line.planned for line in frozen), Decimal(0))
    realized = sum(
        (entry.realized for entry in record.entries if entry.week <= reference_week),
        Decimal(0),
    )
    first_free = calculations.first_free_week(calendario.iso_week(record.start), reference_week)
    changes = revision_change_options(session, project_id=record.project_id)
    data = validation.parse_revision(
        form,
        validation.RevisionChoices(change_codes=frozenset(item.code for item in changes)),
        context=validation.RevisionContext(
            unit=_record_unit(session, record),
            places=record.places,
            realized=realized,
            frozen=frozen_total,
            first_free_week=first_free,
        ),
    )
    from src.modulos.governanca import service as governanca

    change_ids = governanca.change_ids_by_code(session, codes=[data.change_code])
    new_revision = ProductivityRevision(
        item_id=record.id,
        by_id=user.person_id,
        change_id=change_ids.get(data.change_code),
        revision=record.revision + 1,
        revision_date=reference_date,
        total=data.total,
        previous_total=record.total,
        since=data.planned[0][0] if data.planned else first_free,
        justification=data.justification,
    )
    before = _item_aggregate(record)
    versioning.require(session, record, form.fields.get("versao"))
    record.total = data.total
    record.finish = _week_date(data.finish_week)
    record.profile = data.profile
    record.revision = record.revision + 1
    session.add(new_revision)
    session.flush()
    new_revision.distributions = [
        ProductivityDistribution(week=line.week, planned=line.planned) for line in frozen
    ] + [ProductivityDistribution(week=week, planned=value) for week, value in data.planned]
    record.revisions.append(new_revision)
    versioning.advance(record)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=ProductivityItem.__tablename__,
            record_id=record.id,
            action=audit.UPDATED,
            before=before,
            after=_item_aggregate(record),
            project_id=record.project_id,
        ),
    )
    return record


def register_entries(
    session: Session,
    *,
    user: User,
    scope: Scope,
    company_id: int,
    form: validation.EntryForm,
    reference_date: date,
) -> int:
    """Grava o apontamento da semana, atualizando o que já existir (upsert por item e semana)."""
    rbac.require(user, Permission.WRITE)
    targets = _entry_targets(session, scope, company_id=company_id, form=form)
    data = validation.parse_entries(
        form, current_week=calendario.iso_week(reference_date), targets=targets
    )
    for line in data:
        record = _scoped_entry_item(session, scope, line.item_id)
        existing = session.scalars(
            select(ProductivityEntry).where(
                ProductivityEntry.item_id == record.id, ProductivityEntry.week == form.week
            )
        ).one_or_none()
        if existing is None:
            recording.create(
                session,
                user_id=user.id,
                record=ProductivityEntry(
                    item_id=record.id,
                    week=form.week,
                    realized=line.realized or Decimal(0),
                    hh=line.hh or Decimal(0),
                    informed_on=reference_date,
                ),
            )
            continue
        before = audit.snapshot(existing)
        existing.realized = line.realized or Decimal(0)
        existing.hh = line.hh or Decimal(0)
        existing.informed_on = reference_date
        session.flush()
        audit.changed(
            session,
            user_id=user.id,
            entity=existing.__tablename__,
            record=existing,
            before=before,
        )
    return len(data)


def _entry_targets(
    session: Session,
    scope: Scope,
    *,
    company_id: int,
    form: validation.EntryForm,
) -> dict[int, validation.EntryTarget]:
    """O item de cada linha do apontamento, com o acumulado das outras semanas."""
    targets: dict[int, validation.EntryTarget] = {}
    for item_id in form.lines:
        record = session.scalars(
            select(ProductivityItem).where(ProductivityItem.id == item_id)
        ).one_or_none()
        if record is None or record.company_id != company_id:
            continue
        if scope.project_id is not None and record.project_id != scope.project_id:
            continue
        others = session.scalar(
            select(func.coalesce(func.sum(ProductivityEntry.realized), 0)).where(
                ProductivityEntry.item_id == record.id, ProductivityEntry.week != form.week
            )
        )
        targets[item_id] = validation.EntryTarget(
            code=record.code,
            places=record.places,
            unit=_record_unit(session, record),
            approved=record.situation == calculations.ITEM_APPROVED,
            total=record.total,
            others=Decimal(others or 0),
        )
    return targets


def _scoped_entry_item(session: Session, scope: Scope, item_id: int) -> ProductivityItem:
    record = session.scalars(
        select(ProductivityItem)
        .execution_options(populate_existing=True)
        .where(ProductivityItem.id == item_id)
    ).one_or_none()
    if record is None:
        raise InvalidDataError(ITEM_NOT_FOUND_MESSAGE)
    if scope.project_id is not None and record.project_id != scope.project_id:
        raise InvalidDataError(ITEM_PROJECT_MESSAGE)
    return record


def import_item(
    session: Session,
    *,
    user: User,
    scope: Scope,
    form: validation.ItemForm,
    reference_date: date,
) -> str:
    """Importa uma linha da planilha: item novo em elaboração, distribuído pelo perfil."""
    record = save_item(
        session,
        user=user,
        scope=scope,
        item_id=None,
        form=form,
        reference_date=reference_date,
    )
    return record.code


def _scoped_item(session: Session, scope: Scope, item_id: int) -> ProductivityItem:
    record = session.scalars(
        select(ProductivityItem)
        .options(
            selectinload(ProductivityItem.revisions).selectinload(
                ProductivityRevision.distributions
            ),
            selectinload(ProductivityItem.entries),
        )
        .execution_options(populate_existing=True)
        .where(ProductivityItem.id == item_id)
    ).one_or_none()
    if record is None:
        raise InvalidDataError(ITEM_NOT_FOUND_MESSAGE)
    if scope.project_id is not None and record.project_id != scope.project_id:
        raise InvalidDataError(ITEM_PROJECT_MESSAGE)
    return record


def _unit_id_for(session: Session, unit_code: str) -> int | None:
    return next(
        (unit.id for unit in configuracoes.list_measure_units(session) if unit.code == unit_code),
        None,
    )


def _record_unit(session: Session, record: ProductivityItem) -> str:
    if record.unit_id is None:
        return ""
    return next(
        (
            unit.code
            for unit in configuracoes.list_measure_units(session)
            if unit.id == record.unit_id
        ),
        "",
    )


def _discipline_id_for(session: Session, discipline: str) -> int | None:
    if not discipline:
        return None
    for discipline_id, name in configuracoes.discipline_names_by_id(session).items():
        if name == discipline:
            return discipline_id
    return None


def _week_date(label: str) -> date:
    found = calculations.week_start(label)
    if found is None:
        raise InvalidDataError(validation.ITEM_WEEK_MESSAGE)
    return found


# ── Carga de demonstração ─────────────────────────────────────────────────


@dataclass(frozen=True)
class LoadedRevision:
    """Uma revisão do item na carga de demonstração, com a distribuição da revisão corrente."""

    revision: int
    revision_date: date
    by_id: int
    total: Decimal
    previous_total: Decimal | None
    change_id: int | None
    since: str | None
    justification: str
    planned: tuple[calculations.PlannedWeek, ...] = ()


@dataclass(frozen=True)
class LoadedEntry:
    """Um apontamento da carga de demonstração."""

    week: str
    realized: Decimal
    hh: Decimal
    informed_on: date | None


@dataclass(frozen=True)
class LoadedItem:
    """Um item do plano da carga de demonstração: ids do banco e datas já deslocadas."""

    project_id: int
    company_id: int
    unit_id: int | None
    discipline_id: int | None
    approved_by_id: int | None
    code: str
    group: str
    kind: str
    places: int
    total: Decimal
    index_hh: Decimal
    profile: str
    situation: str
    revision: int
    start: date
    finish: date
    approved_on: date | None
    notes: str | None
    revisions: tuple[LoadedRevision, ...]
    entries: tuple[LoadedEntry, ...]


def load_item(session: Session, *, author_id: int, data: LoadedItem) -> ProductivityItem:
    """Grava um item da demonstração com as revisões, a distribuição e os apontamentos."""
    record = recording.create(
        session,
        user_id=author_id,
        record=ProductivityItem(
            project_id=data.project_id,
            company_id=data.company_id,
            unit_id=data.unit_id,
            discipline_id=data.discipline_id,
            approved_by_id=data.approved_by_id,
            code=data.code,
            group=data.group,
            kind=data.kind,
            places=data.places,
            total=data.total,
            index_hh=data.index_hh,
            profile=data.profile,
            situation=data.situation,
            revision=data.revision,
            start=data.start,
            finish=data.finish,
            approved_on=data.approved_on,
            notes=data.notes,
        ),
    )
    for source in data.revisions:
        revision = recording.create(
            session,
            user_id=author_id,
            record=ProductivityRevision(
                item_id=record.id,
                by_id=source.by_id,
                change_id=source.change_id,
                revision=source.revision,
                revision_date=source.revision_date,
                total=source.total,
                previous_total=source.previous_total,
                since=source.since,
                justification=source.justification,
            ),
        )
        for line in source.planned:
            session.add(
                ProductivityDistribution(
                    revision_id=revision.id, week=line.week, planned=line.planned
                )
            )
    for entry in data.entries:
        recording.create(
            session,
            user_id=author_id,
            record=ProductivityEntry(
                item_id=record.id,
                week=entry.week,
                realized=entry.realized,
                hh=entry.hh,
                informed_on=entry.informed_on,
            ),
        )
    session.flush()
    return record


# The group of an activity: what was done in the period or what comes in the next one.
GROUP_PERIOD = "periodo"


GROUP_NEXT = "proximo"


NOT_FOUND_MESSAGE = "Relato não encontrado."


UNKNOWN_PROJECT_MESSAGE = "O projeto do relato não existe."


@dataclass(frozen=True)
class ReportDraft:
    """What a person typed: the type and period, the two lists of activities and the points."""

    kind: str = ""
    period: str = ""
    activities: tuple[str, ...] = ()
    next_activities: tuple[str, ...] = ()
    points: tuple[PointInput, ...] = ()


@dataclass(frozen=True)
class SaveRequest:
    """A save: the draft and, when it edits a report, its id and the version the screen opened."""

    draft: ReportDraft
    report_id: int | None = None
    version: str | None = None


@dataclass(frozen=True)
class ReportFilter:
    """The filter of the list: the type (empty is all) and the text to search for."""

    kind: str = ""
    search: str = ""


@dataclass(frozen=True)
class ReportView:
    """A report as the screens read it: identity, labels, content, counts and who wrote it last."""

    id: int
    project_id: int
    project_code: str
    project_name: str
    kind: str
    period: str
    name: str
    short_name: str
    next_name: str
    activities: tuple[str, ...]
    next_activities: tuple[str, ...]
    points: tuple[PointInput, ...]
    threats: int
    opportunities: int
    version: int
    updated_at: datetime
    updated_by: str

    @property
    def project_label(self) -> str:
        """``TN-2026-014 · Nome do projeto``: how the Portfólio names the project of a row."""
        return f"{self.project_code} · {self.project_name}"


@dataclass(frozen=True)
class NewReportChoices:
    """What the form of a new report offers: the project it will belong to and its periods."""

    project_label: str
    options: list[calculations.PeriodOption]


@dataclass(frozen=True)
class PeriodCoverage:
    """Whether a closed period was reported: how many projects of the scope did, of how many."""

    period: str
    name: str
    short_name: str
    registered: int
    expected: int

    @property
    def is_complete(self) -> bool:
        """Whether every project of the scope reported the period."""
        return self.registered >= self.expected


@dataclass(frozen=True)
class ReportSummary:
    """The indicators of the screen (HU-046): the last closed week and month, the points and the count."""

    previous_week: PeriodCoverage
    previous_month: PeriodCoverage
    last_weekly: ReportView | None
    reference_points: int | None
    total: int
    weekly_total: int
    monthly_total: int
    expected_total: int
    is_portfolio: bool


# ── Reading ────────────────────────────────────────────────────────────────


def list_reports(
    session: Session,
    *,
    user: User,
    scope: Scope,
    report_filter: ReportFilter | None = None,
) -> list[ReportView]:
    """The reports of the scope, the most recent period first, after the type and the search."""
    rbac.require_module(user, MODULE)
    chosen = report_filter or ReportFilter()
    views = _views(session, _reports_in(session, scope))
    kept = [view for view in views if _passes(view, chosen)]
    return sorted(
        kept,
        key=lambda view: (
            *calculations.report_order_key(view.kind, view.period),
            view.project_code,
        ),
    )


def report_summary(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> ReportSummary:
    """The indicators of the screen, read on the reference date for the projects of the scope."""
    rbac.require_module(user, MODULE)
    projects = _projects_in(session, scope)
    views = _views(session, _reports_in(session, scope))
    weekly = [view for view in views if view.kind == WEEKLY]
    last_weekly = max(weekly, key=lambda view: (view.period, view.id), default=None)
    return ReportSummary(
        previous_week=_coverage(WEEKLY, projects, views, reference_date),
        previous_month=_coverage(MONTHLY, projects, views, reference_date),
        last_weekly=last_weekly,
        reference_points=_reference_points(weekly, last_weekly),
        total=len(views),
        weekly_total=len(weekly),
        monthly_total=len(views) - len(weekly),
        expected_total=sum(
            calculations.expected_report_count(kind, project.start_date, reference_date)
            for project in projects.values()
            for kind in validation.KINDS
        ),
        is_portfolio=scope.is_portfolio,
    )


def get_report(session: Session, *, user: User, scope: Scope, report_id: int) -> ReportView:
    """One report of the scope, or 422 when there is none with that id in it."""
    rbac.require_module(user, MODULE)
    return _views(session, [_find(session, scope, report_id)])[0]


def find_report(
    session: Session, *, user: User, scope: Scope, kind: str, period: str
) -> ReportView | None:
    """The report of the project of the scope for the type and period, or ``None`` when absent.

    It is the address of the report manager's modal: type, period and open. In the Portfólio
    there is no project to look in, so there is no answer.
    """
    rbac.require_module(user, MODULE)
    if scope.project_id is None:
        return None
    report = _report_of(session, project_id=scope.project_id, kind=kind, period=period)
    return _views(session, [report])[0] if report is not None else None


def period_choices(
    session: Session, *, user: User, scope: Scope, kind: str, reference_date: date
) -> NewReportChoices:
    """The project of the scope and the periods the form offers for a new report of the type."""
    rbac.require_module(user, MODULE)
    project = _project(session, scope.require_project())
    taken = session.scalars(
        select(Report.period).where(Report.project_id == project.id, Report.kind == kind)
    ).all()
    return NewReportChoices(
        project_label=f"{project.code} · {project.name}",
        options=calculations.period_options(
            kind, project_start=project.start_date, reference_date=reference_date, taken=taken
        ),
    )


def previous_report(
    session: Session, *, user: User, scope: Scope, request: SaveRequest
) -> ReportView | None:
    """The report "Copiar do período anterior" brings: the latest of the same type before the period.

    The project and the period are those of the report being edited, or of the project of the
    scope and the period chosen in the form of a new one.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    project_id, kind, period = _target(session, scope, request)
    candidates = list(
        session.scalars(
            select(Report)
            .options(selectinload(Report.activities), selectinload(Report.points))
            .where(Report.project_id == project_id, Report.kind == kind)
        )
    )
    earlier = calculations.latest_period_before((report.period for report in candidates), period)
    chosen = next((report for report in candidates if report.period == earlier), None)
    return _views(session, [chosen])[0] if chosen is not None else None


# ── Writing ────────────────────────────────────────────────────────────────


def save_report(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: SaveRequest,
    reference_date: date,
) -> ReportView:
    """Create the report or save the edit of one, or refuse with 422 per field.

    Writing asks for Membro. A new report belongs to the project of the scope (in the Portfólio
    the screen asks for the project first). The type and the period of an existing report are
    kept: only the content changes. A stale version is refused with 409.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    existing = _find(session, scope, request.report_id) if request.report_id is not None else None
    project_id = existing.project_id if existing is not None else scope.require_project()
    kind = existing.kind if existing is not None else request.draft.kind
    period = existing.period if existing is not None else request.draft.period
    content = _content_of(request.draft)
    errors = _save_errors(
        session,
        project=_project(session, project_id),
        draft=ReportDraft(kind=kind, period=period, **content),
        is_new=existing is None,
        reference_date=reference_date,
    )
    if errors:
        raise InvalidDataError(errors)
    if existing is not None:
        report = _edit(
            session, user=user, report=existing, version=request.version, content=content
        )
    else:
        report = _assemble(
            project_id=project_id, kind=kind, period=period, person_id=user.person_id
        )
        fill_report(report, **content)
        insert_report(session, user_id=user.id, report=report)
    return _views(session, [report])[0]


def insert_report(session: Session, *, user_id: int, report: Report) -> Report:
    """Write an assembled report with the trail of its creation (the whole content, after).

    The screen creates through ``save_report``; the demonstration load calls this one, with the
    authors and the times of the prototype already on the report.
    """
    session.add(report)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user_id,
            entity=Report.__tablename__,
            record_id=report.id,
            action=audit.CREATED,
            after=_aggregate(report),
            project_id=report.project_id,
        ),
    )
    return report


def delete_report(
    session: Session, *, user: User, scope: Scope, report_id: int, version: str | None
) -> ReportView:
    """Delete the report, which leaves the period pending again; asks for Gestor.

    Returns the report as it was, for the message. A stale version is refused with 409.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    report = _find(session, scope, report_id)
    view = _views(session, [report])[0]
    before = _aggregate(report)
    versioning.require(session, report, version)
    session.delete(report)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=Report.__tablename__,
            record_id=view.id,
            action=audit.DELETED,
            before=before,
            project_id=view.project_id,
        ),
    )
    return view


# ── Rules of the save ──────────────────────────────────────────────────────


def _target(session: Session, scope: Scope, request: SaveRequest) -> tuple[int, str, str]:
    """The project, the type and the period a save is about: the report's own when it exists."""
    if request.report_id is None:
        return scope.require_project(), request.draft.kind, request.draft.period
    report = _find(session, scope, request.report_id)
    return report.project_id, report.kind, report.period


def _content_of(draft: ReportDraft) -> dict[str, Any]:
    """The content of the draft cleaned the way it is saved: lines trimmed, blank points dropped."""
    return {
        "activities": tuple(validation.clean_lines(draft.activities)),
        "next_activities": tuple(validation.clean_lines(draft.next_activities)),
        "points": tuple(validation.non_blank_points(draft.points)),
    }


def _save_errors(
    session: Session,
    *,
    project: configuracoes.ProjectSummary,
    draft: ReportDraft,
    is_new: bool,
    reference_date: date,
) -> dict[str, str]:
    """Every message of a save, by the field of the form: type, period, activities and points."""
    errors = validation.validate_kind(draft.kind)
    if not errors:
        problem = _period_problem(
            session, project=project, draft=draft, is_new=is_new, reference_date=reference_date
        )
        if problem:
            errors[validation.FIELD_PERIOD] = problem
    errors.update(validation.validate_activities(draft.activities, draft.next_activities))
    errors.update(validation.validate_points(draft.points))
    return errors


def _period_problem(
    session: Session,
    *,
    project: configuracoes.ProjectSummary,
    draft: ReportDraft,
    is_new: bool,
    reference_date: date,
) -> str | None:
    """The message for the period: not valid, before the project, in the future or already reported."""
    problem = calculations.report_period_error(
        draft.kind, draft.period, project_start=project.start_date, reference_date=reference_date
    )
    if problem is not None or not is_new:
        return problem
    already = _report_of(session, project_id=project.id, kind=draft.kind, period=draft.period)
    return _duplicate_message(draft.kind) if already is not None else None


def _duplicate_message(kind: str) -> str:
    return f"Já existe relato {kind.lower()} para este período; edite o registro existente."


def _assemble(*, project_id: int, kind: str, period: str, person_id: int) -> Report:
    """A report not yet written, authored and stamped now."""
    moment = calendario.now()
    return Report(
        project_id=project_id,
        created_by_id=person_id,
        updated_by_id=person_id,
        kind=kind,
        period=period,
        created_at=moment,
        updated_at=moment,
    )


def fill_report(
    report: Report,
    *,
    activities: Sequence[str],
    next_activities: Sequence[str],
    points: Sequence[PointInput],
) -> None:
    """Replace the children of the report with the content, in the order given.

    The screen goes through ``save_report``; the demonstration load assembles its reports with
    this and writes them with ``insert_report``.
    """
    report.activities = [
        *_activity_rows(GROUP_PERIOD, activities),
        *_activity_rows(GROUP_NEXT, next_activities),
    ]
    report.points = [
        ReportPoint(
            order=order, description=point.description, nature=point.nature, risk=point.risk
        )
        for order, point in enumerate(points, start=1)
    ]


def _activity_rows(group: str, lines: Sequence[str]) -> list[ReportActivity]:
    return [
        ReportActivity(group=group, order=order, text=line)
        for order, line in enumerate(lines, start=1)
    ]


def _edit(
    session: Session,
    *,
    user: User,
    report: Report,
    version: str | None,
    content: dict[str, Any],
) -> Report:
    """Save the content of an existing report after the version check, leaving the trail."""
    before = _aggregate(report)
    versioning.require(session, report, version)
    fill_report(report, **content)
    report.updated_by_id = user.person_id
    report.updated_at = calendario.now()
    versioning.advance(report)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=Report.__tablename__,
            record_id=report.id,
            action=audit.UPDATED,
            before=before,
            after=_aggregate(report),
            project_id=report.project_id,
        ),
    )
    return report


def _aggregate(report: Report) -> dict[str, Any]:
    """The report and its children as the trail keeps them, keyed by the Portuguese names."""
    return {
        **audit.snapshot(report),
        "atividades": [
            {"grupo": row.group, "ordem": row.order, "texto": row.text} for row in report.activities
        ],
        "pontos": [
            {
                "ordem": row.order,
                "descricao": row.description,
                "natureza": row.nature,
                "risco": row.risk,
            }
            for row in report.points
        ],
    }


# ── Reading helpers ────────────────────────────────────────────────────────


def _projects_in(session: Session, scope: Scope) -> dict[int, configuracoes.ProjectSummary]:
    """The projects of the scope by id: every project in the Portfólio, the chosen one otherwise."""
    return {
        project.id: project
        for project in configuracoes.list_projects(session)
        if scope.project_id is None or project.id == scope.project_id
    }


def _project(session: Session, project_id: int) -> configuracoes.ProjectSummary:
    for project in configuracoes.list_projects(session):
        if project.id == project_id:
            return project
    raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)


def _reports_in(session: Session, scope: Scope) -> list[Report]:
    statement = select(Report).options(selectinload(Report.activities), selectinload(Report.points))
    if scope.project_id is not None:
        statement = statement.where(Report.project_id == scope.project_id)
    return list(session.scalars(statement))


def _find(session: Session, scope: Scope, report_id: int) -> Report:
    """The report with the id inside the scope, or 422: an id of another project is not found."""
    report = session.get(Report, report_id)
    if report is None or (scope.project_id is not None and report.project_id != scope.project_id):
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return report


def _report_of(session: Session, *, project_id: int, kind: str, period: str) -> Report | None:
    statement = select(Report).where(
        Report.project_id == project_id, Report.kind == kind, Report.period == period
    )
    return session.scalars(statement).first()


def _views(session: Session, reports: Sequence[Report]) -> list[ReportView]:
    """The reports as the screens read them, with the project and the author named once."""
    if not reports:
        return []
    projects = {project.id: project for project in configuracoes.list_projects(session)}
    names = configuracoes.person_names(session, {report.updated_by_id for report in reports})
    return [_view(report, projects[report.project_id], names) for report in reports]


def _view(
    report: Report, project: configuracoes.ProjectSummary, names: dict[int, str]
) -> ReportView:
    points = tuple(
        PointInput(description=row.description, nature=row.nature, risk=row.risk)
        for row in report.points
    )
    threats, opportunities = calculations.nature_counts(point.nature for point in points)
    return ReportView(
        id=report.id,
        project_id=project.id,
        project_code=project.code,
        project_name=project.name,
        kind=report.kind,
        period=report.period,
        name=calculations.period_name(report.kind, report.period),
        short_name=calculations.short_period_name(report.kind, report.period),
        next_name=_next_name(report.kind, report.period),
        activities=_lines(report, GROUP_PERIOD),
        next_activities=_lines(report, GROUP_NEXT),
        points=points,
        threats=threats,
        opportunities=opportunities,
        version=report.version,
        updated_at=report.updated_at,
        updated_by=names.get(report.updated_by_id, ""),
    )


def _lines(report: Report, group: str) -> tuple[str, ...]:
    return tuple(row.text for row in report.activities if row.group == group)


def _next_name(kind: str, period: str) -> str:
    following = calculations.next_period(kind, period)
    return calculations.period_name(kind, following) if following is not None else ""


def _passes(view: ReportView, report_filter: ReportFilter) -> bool:
    """Whether the report stays in the list: the type, and the search in any of its texts."""
    if report_filter.kind and view.kind != report_filter.kind:
        return False
    needle = normalize_text(report_filter.search)
    if not needle:
        return True
    texts = [
        view.name,
        view.project_code,
        *view.activities,
        *view.next_activities,
        *(f"{point.description} {point.nature} {point.risk}" for point in view.points),
    ]
    return needle in normalize_text(" ".join(texts))


def _coverage(
    kind: str,
    projects: dict[int, configuracoes.ProjectSummary],
    views: Sequence[ReportView],
    reference_date: date,
) -> PeriodCoverage:
    """How many projects reported the last closed period of the type."""
    period = calculations.previous_period(kind, reference_date)
    reported = {view.project_id for view in views if view.kind == kind and view.period == period}
    return PeriodCoverage(
        period=period,
        name=calculations.period_name(kind, period),
        short_name=calculations.short_period_name(kind, period),
        registered=len(reported & projects.keys()),
        expected=len(projects),
    )


def _reference_points(weekly: Sequence[ReportView], last: ReportView | None) -> int | None:
    """The attention points of the weekly report before the last one, of the same project."""
    if last is None:
        return None
    of_project = {view.period: view for view in weekly if view.project_id == last.project_id}
    earlier = calculations.latest_period_before(of_project, last.period)
    return len(of_project[earlier].points) if earlier is not None else None


# First key of the advisory lock that serializes the code of a new activity of a project.
ACTIVITY_CODE_LOCK = 4501


ACTIVITY_NOT_FOUND_MESSAGE = "A atividade não existe mais. Recarregue a tela."


CONSTRAINT_NOT_FOUND_MESSAGE = "A restrição não existe mais. Recarregue a tela."


OTHER_PROJECT_MESSAGE = "O registro pertence a outro projeto: abra a tela no projeto dele."


ALREADY_REMOVED_MESSAGE = "A restrição já foi removida."


CHOOSE_ACTIVITY_MESSAGE = "Escolha a atividade da lista."


OPEN_CONSTRAINTS = "abertas"


ALL_CONSTRAINTS = "todas"


STATUS_OVERDUE = "Vencida"


STATUS_OPEN = "Aberta"


STATUS_REMOVED = "Removida"


@dataclass(frozen=True)
class LookaheadFilter:
    """What the person filtered: search text, discipline, only open restrictions and the list."""

    search: str = ""
    discipline: str = ""
    only_with_open_constraint: bool = False
    constraints: str = OPEN_CONSTRAINTS


@dataclass(frozen=True)
class ConstraintView:
    """A restriction as the screen and the exports read it."""

    id: int
    activity_id: int
    activity_code: str
    activity_name: str
    project_id: int
    project_label: str
    kind: str
    description: str
    owner_id: int | None
    owner_name: str
    due_date: date
    removal_date: date | None
    removal_comment: str | None
    is_open: bool
    is_overdue: bool
    version: int

    @property
    def status(self) -> str:
        """``Vencida``, ``Aberta`` or ``Removida``."""
        if self.is_overdue:
            return STATUS_OVERDUE
        return STATUS_OPEN if self.is_open else STATUS_REMOVED


@dataclass(frozen=True)
class ActivityView:
    """An activity of the horizon with its weeks, restrictions and counts."""

    id: int
    project_id: int
    project_label: str
    code: str
    name: str
    area: str
    discipline: str
    company_id: int | None
    company_name: str
    owner_id: int | None
    owner_name: str
    planned: tuple[bool, ...]
    constraints: tuple[ConstraintView, ...]
    version: int

    @property
    def open_constraints(self) -> int:
        """How many restrictions are still open."""
        return sum(1 for item in self.constraints if item.is_open)

    @property
    def overdue_constraints(self) -> int:
        """How many open restrictions are past the date they were needed."""
        return sum(1 for item in self.constraints if item.is_overdue)

    @property
    def is_ready(self) -> bool:
        """Free of open restrictions: it can go to the weekly schedule."""
        return calculations.activity_is_ready(self.open_constraints)

    @property
    def situation(self) -> str:
        """``vencida``, ``com_restricao`` or ``pronta``."""
        return calculations.activity_situation(self.open_constraints, self.overdue_constraints)

    @property
    def has_short_term_risk(self) -> bool:
        """Planned in the first two weeks with an open restriction: it must not be scheduled."""
        return calculations.has_open_constraint_in_short_term(self.planned, self.open_constraints)

    def week_at_risk(self, index: int) -> bool:
        """Whether the planned week ``index`` carries the orange mark."""
        return calculations.week_at_risk(index, self.planned, self.open_constraints)

    def counts(self) -> calculations.ActivityCounts:
        """What the indicators read of the activity."""
        return calculations.ActivityCounts(
            planned=self.planned,
            total_constraints=len(self.constraints),
            open_constraints=self.open_constraints,
            overdue_constraints=self.overdue_constraints,
        )


@dataclass(frozen=True)
class LookaheadBoard:
    """The 6WLA of a scope on a date: the weeks, the visible activities and the indicators.

    ``figures`` count every activity of the scope (the filters do not move the
    indicators, as in the prototype); ``activities`` and ``constraints`` are what
    the filters leave.
    """

    reference_date: date
    weeks: tuple[calculations.LookaheadWeekInfo, ...]
    activities: tuple[ActivityView, ...]
    constraints: tuple[ConstraintView, ...]
    figures: calculations.LookaheadFigures
    total_activities: int
    can_write: bool
    portfolio: bool


@dataclass(frozen=True)
class FormOptions:
    """What the forms offer: the register lists and the weeks of the horizon."""

    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]
    disciplines: tuple[str, ...]
    kinds: tuple[str, ...]
    weeks: tuple[calculations.LookaheadWeekInfo, ...]

    def company_choices(self) -> tuple[tuple[str, str], ...]:
        """The companies as ``(value, text)`` pairs for a selector."""
        return tuple((str(item.id), item.name) for item in self.companies)

    def person_choices(self) -> tuple[tuple[str, str], ...]:
        """The people as ``(value, text)`` pairs for a selector."""
        return tuple((str(item.id), item.name) for item in self.people)

    def discipline_choices(self) -> tuple[tuple[str, str], ...]:
        """The disciplines as ``(value, text)`` pairs for a selector."""
        return tuple((name, name) for name in self.disciplines)

    def kind_choices(self) -> tuple[tuple[str, str], ...]:
        """The restriction types as ``(value, text)`` pairs for a selector."""
        return tuple((name, name) for name in self.kinds)

    def choices(self) -> validation.RegisterChoices:
        """The same lists as the sets the validation checks the form against."""
        return validation.RegisterChoices(
            company_ids=frozenset(item.id for item in self.companies),
            person_ids=frozenset(item.id for item in self.people),
            disciplines=frozenset(self.disciplines),
        )


def can_write(user: User) -> bool:
    """Whether the profile may include and edit activities and restrictions."""
    return rbac.can(user, Permission.WRITE)


def form_options(session: Session, *, reference_date: date) -> FormOptions:
    """The register lists of the forms and the six weeks of the horizon of the date."""
    return FormOptions(
        companies=tuple(configuracoes.list_company_options(session)),
        people=tuple(configuracoes.list_person_options(session)),
        disciplines=tuple(configuracoes.list_discipline_names(session)),
        kinds=validation.CONSTRAINT_KINDS,
        weeks=calculations.lookahead_weeks(reference_date),
    )


def _register_choices(session: Session) -> validation.RegisterChoices:
    """The ids and names the register accepts in a form, for the validation."""
    return validation.RegisterChoices(
        company_ids=frozenset(item.id for item in configuracoes.list_company_options(session)),
        person_ids=frozenset(item.id for item in configuracoes.list_person_options(session)),
        disciplines=frozenset(configuracoes.list_discipline_names(session)),
    )


# ── Reading ──────────────────────────────────────────────────────────────


def lookahead_board(
    session: Session,
    *,
    user: User,
    scope: Scope,
    reference_date: date,
    filters: LookaheadFilter,
) -> LookaheadBoard:
    """The board of the scope: indicators over every activity, grid and list over the filtered."""
    activities = _activities_in_scope(session, scope=scope, reference_date=reference_date)
    visible = tuple(item for item in activities if _matches(item, filters))
    constraints = [constraint for item in visible for constraint in item.constraints]
    if filters.constraints == OPEN_CONSTRAINTS:
        constraints = [item for item in constraints if item.is_open]
    constraints.sort(key=lambda item: (item.due_date, item.id))
    return LookaheadBoard(
        reference_date=reference_date,
        weeks=calculations.lookahead_weeks(reference_date),
        activities=visible,
        constraints=tuple(constraints),
        figures=calculations.lookahead_figures([item.counts() for item in activities]),
        total_activities=len(activities),
        can_write=can_write(user),
        portfolio=scope.is_portfolio,
    )


def find_activity(
    session: Session, *, scope: Scope, activity_id: int, reference_date: date
) -> ActivityView:
    """One activity of the scope, with its restrictions."""
    record = _scoped_activity(session, scope, activity_id)
    return _activity_views(session, [record], reference_date=reference_date)[0]


def find_constraint(
    session: Session, *, scope: Scope, constraint_id: int, reference_date: date
) -> ConstraintView:
    """One restriction of the scope, with the activity it belongs to."""
    record = _scoped_constraint(session, scope, constraint_id)
    activity = find_activity(
        session, scope=scope, activity_id=record.lookahead_id, reference_date=reference_date
    )
    return next(item for item in activity.constraints if item.id == record.id)


def _matches(activity: ActivityView, filters: LookaheadFilter) -> bool:
    if filters.discipline and activity.discipline != filters.discipline:
        return False
    if filters.only_with_open_constraint and not activity.open_constraints:
        return False
    needle = normalize_text(filters.search)
    if not needle:
        return True
    haystack = normalize_text(
        " ".join(
            (
                activity.code,
                activity.name,
                activity.area,
                activity.discipline,
                activity.company_name,
                activity.project_label,
            )
        )
    )
    return needle in haystack


def _activities_in_scope(
    session: Session, *, scope: Scope, reference_date: date
) -> list[ActivityView]:
    statement = select(Lookahead).order_by(Lookahead.project_id, Lookahead.id)
    if not scope.is_portfolio:
        statement = statement.where(Lookahead.project_id == scope.project_id)
    return _activity_views(session, list(session.scalars(statement)), reference_date=reference_date)


def _activity_views(
    session: Session, records: Sequence[Lookahead], *, reference_date: date
) -> list[ActivityView]:
    """The views of the activities, with the weeks and the restrictions read in one query each."""
    if not records:
        return []
    ids = [record.id for record in records]
    weeks = _weeks_by_activity(session, ids)
    constraints = _constraints_by_activity(session, ids)
    names = _Names.read(session)
    views = []
    for record in records:
        activity_constraints = tuple(
            _constraint_view(item, record, names, reference_date=reference_date)
            for item in constraints.get(record.id, [])
        )
        views.append(
            ActivityView(
                id=record.id,
                project_id=record.project_id,
                project_label=names.project(record.project_id),
                code=record.code,
                name=record.activity,
                area=record.area,
                discipline=record.discipline,
                company_id=record.company_id,
                company_name=names.company(record.company_id),
                owner_id=record.owner_id,
                owner_name=names.person(record.owner_id),
                planned=weeks.get(record.id, (False,) * calculations.LOOKAHEAD_WEEKS),
                constraints=activity_constraints,
                version=record.version,
            )
        )
    return views


def _weeks_by_activity(session: Session, ids: Sequence[int]) -> dict[int, tuple[bool, ...]]:
    marks: dict[int, list[bool]] = {
        activity_id: [False] * calculations.LOOKAHEAD_WEEKS for activity_id in ids
    }
    statement = select(LookaheadWeek).where(LookaheadWeek.lookahead_id.in_(ids))
    for week in session.scalars(statement):
        marks[week.lookahead_id][week.index] = week.planned
    return {activity_id: tuple(values) for activity_id, values in marks.items()}


def _constraints_by_activity(
    session: Session, ids: Sequence[int]
) -> dict[int, list[LookaheadConstraint]]:
    statement = (
        select(LookaheadConstraint)
        .where(LookaheadConstraint.lookahead_id.in_(ids))
        .order_by(LookaheadConstraint.order, LookaheadConstraint.id)
    )
    grouped: dict[int, list[LookaheadConstraint]] = {}
    for item in session.scalars(statement):
        grouped.setdefault(item.lookahead_id, []).append(item)
    return grouped


@dataclass(frozen=True)
class _Names:
    """The names of the register entries a row mentions, read once per request."""

    projects: Mapping[int, str]
    companies: Mapping[int, str]
    people: Mapping[int, str]

    @classmethod
    def read(cls, session: Session) -> _Names:
        return cls(
            projects={
                project.id: f"{project.code} · {project.name}"
                for project in configuracoes.list_projects(session)
            },
            companies={item.id: item.name for item in configuracoes.list_company_options(session)},
            people={item.id: item.name for item in configuracoes.list_person_options(session)},
        )

    def project(self, project_id: int) -> str:
        return self.projects.get(project_id, "")

    def company(self, company_id: int | None) -> str:
        return self.companies.get(company_id, "") if company_id is not None else ""

    def person(self, person_id: int | None) -> str:
        return self.people.get(person_id, "") if person_id is not None else ""


def _constraint_view(
    item: LookaheadConstraint, activity: Lookahead, names: _Names, *, reference_date: date
) -> ConstraintView:
    return ConstraintView(
        id=item.id,
        activity_id=activity.id,
        activity_code=activity.code,
        activity_name=activity.activity,
        project_id=activity.project_id,
        project_label=names.project(activity.project_id),
        kind=item.kind,
        description=item.description,
        owner_id=item.owner_id,
        owner_name=names.person(item.owner_id),
        due_date=item.due_date,
        removal_date=item.removal_date,
        removal_comment=item.removal_comment,
        is_open=calculations.constraint_is_open(item.removal_date),
        is_overdue=calculations.constraint_is_overdue(
            item.due_date, item.removal_date, reference_date
        ),
        version=item.version,
    )


# ── Writing ──────────────────────────────────────────────────────────────


def create_activity(
    session: Session,
    *,
    user: User,
    scope: Scope,
    form: validation.ActivityForm,
) -> Lookahead:
    """Include an activity in the project of the scope, with the next code of the project."""
    rbac.require(user, Permission.WRITE)
    project_id = scope.require_project()
    data = validation.parse_activity(form, _register_choices(session))
    session.execute(
        select(func.pg_advisory_xact_lock(ACTIVITY_CODE_LOCK, cast(project_id, Integer)))
    )
    existing = list(
        session.scalars(
            select(Lookahead.code).where(Lookahead.project_id == project_id).order_by(Lookahead.id)
        )
    )
    record = recording.create(
        session,
        user_id=user.id,
        record=Lookahead(
            project_id=project_id,
            company_id=data.company_id,
            owner_id=data.owner_id,
            code=calculations.next_activity_code(existing),
            activity=data.activity,
            area=data.area,
            discipline=data.discipline,
        ),
    )
    for index, planned in enumerate(data.planned):
        week = LookaheadWeek(lookahead_id=record.id, index=index, planned=planned)
        session.add(week)
        session.flush()
        audit.created(session, user_id=user.id, entity=week.__tablename__, record=week)
    return record


def update_activity(
    session: Session,
    *,
    user: User,
    scope: Scope,
    activity_id: int,
    form: validation.ActivityForm,
) -> Lookahead:
    """Edit an activity; the version the screen opened (``versao``) must still be current."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_activity(session, scope, activity_id)
    data = validation.parse_activity(form, _register_choices(session))
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes={
            "company_id": data.company_id,
            "owner_id": data.owner_id,
            "activity": data.activity,
            "area": data.area,
            "discipline": data.discipline,
        },
        version=form.fields.get("versao"),
    )
    _replace_weeks(session, user=user, activity=record, planned=data.planned)
    return record


@dataclass(frozen=True)
class LoadedConstraint:
    """A restriction of the demonstration load: already typed, with the removal it carries."""

    kind: str
    owner_id: int | None
    description: str
    due_date: date
    removal_date: date | None


@dataclass(frozen=True)
class LoadedActivity:
    """An activity of the demonstration load: the register ids are the ones of this database."""

    project_id: int
    company_id: int | None
    owner_id: int | None
    code: str
    activity: str
    area: str
    discipline: str
    planned: tuple[bool, ...]
    constraints: tuple[LoadedConstraint, ...]


def load_activity(session: Session, *, author_id: int, data: LoadedActivity) -> Lookahead:
    """Write one activity of the demonstration load, with its weeks and restrictions, and the trail."""
    record = recording.create(
        session,
        user_id=author_id,
        record=Lookahead(
            project_id=data.project_id,
            company_id=data.company_id,
            owner_id=data.owner_id,
            code=data.code,
            activity=data.activity,
            area=data.area,
            discipline=data.discipline,
        ),
    )
    for index, planned in enumerate(data.planned):
        week = LookaheadWeek(lookahead_id=record.id, index=index, planned=planned)
        session.add(week)
        session.flush()
        audit.created(session, user_id=author_id, entity=week.__tablename__, record=week)
    for order, item in enumerate(data.constraints, start=1):
        recording.create(
            session,
            user_id=author_id,
            record=LookaheadConstraint(
                lookahead_id=record.id,
                owner_id=item.owner_id,
                order=order,
                kind=item.kind,
                description=item.description,
                due_date=item.due_date,
                removal_date=item.removal_date,
            ),
        )
    return record


def _replace_weeks(
    session: Session, *, user: User, activity: Lookahead, planned: tuple[bool, ...]
) -> None:
    """Move the six marks to the new values, leaving a trail line for each one that changed."""
    weeks = session.scalars(
        select(LookaheadWeek).where(LookaheadWeek.lookahead_id == activity.id)
    ).all()
    for week in weeks:
        if week.planned == planned[week.index]:
            continue
        before = audit.snapshot(week)
        week.planned = planned[week.index]
        session.flush()
        audit.changed(
            session, user_id=user.id, entity=week.__tablename__, record=week, before=before
        )


def create_constraint(
    session: Session,
    *,
    user: User,
    scope: Scope,
    raw: Mapping[str, str],
) -> LookaheadConstraint:
    """Register a restriction on the activity the form names (``atividade``); it starts open."""
    rbac.require(user, Permission.WRITE)
    activity = _scoped_activity(session, scope, _activity_id_of(raw), lock=True)
    data = validation.parse_constraint(raw, _register_choices(session))
    last_order = session.scalar(
        select(func.max(LookaheadConstraint.order)).where(
            LookaheadConstraint.lookahead_id == activity.id
        )
    )
    return recording.create(
        session,
        user_id=user.id,
        record=LookaheadConstraint(
            lookahead_id=activity.id,
            owner_id=data.owner_id,
            order=(last_order or 0) + 1,
            kind=data.kind,
            description=data.description,
            due_date=data.due_date,
        ),
    )


def _activity_id_of(raw: Mapping[str, str]) -> int:
    found = validation.parse_id(raw.get("atividade"))
    if found is None:
        raise InvalidDataError({"atividade": CHOOSE_ACTIVITY_MESSAGE})
    return found


def update_constraint(
    session: Session,
    *,
    user: User,
    scope: Scope,
    constraint_id: int,
    raw: Mapping[str, str],
) -> LookaheadConstraint:
    """Edit the type, owner, description and needed date of a restriction."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_constraint(session, scope, constraint_id)
    data = validation.parse_constraint(raw, _register_choices(session))
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes={
            "kind": data.kind,
            "owner_id": data.owner_id,
            "description": data.description,
            "due_date": data.due_date,
        },
        version=raw.get("versao"),
    )
    return record


def remove_constraint(
    session: Session,
    *,
    user: User,
    scope: Scope,
    constraint_id: int,
    raw: Mapping[str, str],
) -> LookaheadConstraint:
    """Register the removal of an open restriction: the date and, optionally, how it was removed."""
    rbac.require(user, Permission.WRITE)
    record = _scoped_constraint(session, scope, constraint_id)
    data = validation.parse_removal(raw)
    if not calculations.constraint_is_open(record.removal_date):
        raise InvalidDataError(ALREADY_REMOVED_MESSAGE)
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes={"removal_date": data.removal_date, "removal_comment": data.comment},
        version=raw.get("versao"),
    )
    return record


# ── The records of the scope ─────────────────────────────────────────────


def _require_in_scope(scope: Scope, project_id: int) -> None:
    if not scope.is_portfolio and scope.project_id != project_id:
        raise InvalidDataError(OTHER_PROJECT_MESSAGE)


def _scoped_activity(
    session: Session, scope: Scope, activity_id: int, *, lock: bool = False
) -> Lookahead:
    statement = select(Lookahead).where(Lookahead.id == activity_id)
    if lock:
        statement = statement.with_for_update()
    record = session.scalars(statement).one_or_none()
    if record is None:
        raise InvalidDataError(ACTIVITY_NOT_FOUND_MESSAGE)
    _require_in_scope(scope, record.project_id)
    return record


def _scoped_constraint(session: Session, scope: Scope, constraint_id: int) -> LookaheadConstraint:
    record = session.get(LookaheadConstraint, constraint_id)
    if record is None:
        raise InvalidDataError(CONSTRAINT_NOT_FOUND_MESSAGE)
    _scoped_activity(session, scope, record.lookahead_id)
    return record


def activity_fields(activity: ActivityView) -> dict[str, Any]:
    """The values of the activity form for an edit: the same names the form sends."""
    return {
        "atividade": activity.name,
        "area": activity.area,
        "disciplina": activity.discipline,
        "empresa": str(activity.company_id or ""),
        "responsavel": str(activity.owner_id or ""),
        "versao": str(activity.version),
    }


def constraint_fields(constraint: ConstraintView) -> dict[str, Any]:
    """The values of the restriction form for an edit: the same names the form sends."""
    return {
        "tipo": constraint.kind,
        "responsavel": str(constraint.owner_id or ""),
        "descricao": constraint.description,
        "necessaria": constraint.due_date.isoformat(),
        "versao": str(constraint.version),
    }


# ── EAP: árvore, dicionário e carteira (ISSUE-036) ───────────────────────


EAP_GROUP = "eap"

LEVEL_ROOT = 0


LEVEL_AREA = 1


LEVEL_SUB_AREA = 2


LEVEL_PACKAGE = 3


ROOT_CODE = "0"


PORTFOLIO_LABEL = "Portfólio"


PORTFOLIO_DESCRIPTION = "Portfólio de projetos"


EAP_PROJECT_NOT_FOUND_MESSAGE = "O projeto da EAP não existe."


PACKAGE_NOT_FOUND_MESSAGE = "Pacote da EAP não encontrado."


ONLY_PACKAGES_MESSAGE = "Só os pacotes (nível 3) têm dicionário editável."


EAP_PORTFOLIO_READ_ONLY_MESSAGE = (
    "A EAP do Portfólio é somente leitura. Abra o projeto para editar o dicionário."
)


DEFAULT_DEVIATION_BANDS = (Decimal(2), Decimal(5))


DEFAULT_MAX_PACKAGE_WEIGHT = Decimal(10)


DEFAULT_MAX_ESTIMATED_WEIGHT = Decimal(5)


@dataclass(frozen=True)
class EapMeasurementView:
    """A medição do pacote como o dicionário a mostra: quando, de quanto para quanto, quem e a nota."""

    id: int
    measured_on: date
    from_pct: Decimal
    to_pct: Decimal
    author: str
    note: str

    @property
    def is_reversal(self) -> bool:
        """Whether the progress went back: the dictionary marks the measurement of the reversal."""
        return self.to_pct < self.from_pct


@dataclass(frozen=True)
class EapNode:
    """Um nó da árvore da EAP: a linha 0, a área, a subárea ou o pacote.

    Os nós de nível 1 e 2 não têm peso próprio: o peso é a soma dos filhos (regra dos 100%),
    calculada pelo servidor. Os campos descritivos do pacote (critério, modelo, etapas, unidade,
    quantidade, estado, entregável, aceitação, empresa, responsável, item da EAC e medições) só
    valem para o nível 3.
    """

    id: int | None
    code: str
    level: int
    description: str
    project_id: int | None
    project_code: str
    project_label: str
    weight: Decimal
    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    band: str | None
    start: date | None
    finish: date | None
    packages: int
    planning: int
    overdue: bool
    not_started: bool
    weight_in_parent: Decimal | None = None
    weight_in_project: Decimal | None = None
    kind: str | None = None
    criterion: str | None = None
    model: str = ""
    unit: str = ""
    quantity: Decimal | None = None
    executed: Decimal | None = None
    state: str | None = None
    estimated_pct: Decimal | None = None
    deliverable: str = ""
    acceptance: str = ""
    company_id: int | None = None
    company_name: str = ""
    owner_id: int | None = None
    owner_name: str = ""
    eac_item_id: int | None = None
    eac_code: str = ""
    steps: tuple[calculations.EapStep, ...] = ()
    measurements: tuple[EapMeasurementView, ...] = ()
    version: int = 0

    @property
    def is_work_package(self) -> bool:
        """Pacote de trabalho: nível 3 fora do tipo Planejamento; é ele que mede avanço."""
        return self.level == LEVEL_PACKAGE and self.kind != calculations.PLANNING_PACKAGE

    @property
    def is_planning_package(self) -> bool:
        """Pacote de planejamento: peso reservado, sem medição até ser desdobrado."""
        return self.level == LEVEL_PACKAGE and self.kind == calculations.PLANNING_PACKAGE


@dataclass(frozen=True)
class EapIndicators:
    """Os indicadores da tela: o avanço, os pacotes, as áreas e as marcas de atenção."""

    actual: Decimal
    predicted: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    work_packages: int
    planning_packages: int
    planning_weight: Decimal | None
    areas: int
    subareas: int
    overdue: int
    not_started: int
    late: int
    projects: int


@dataclass(frozen=True)
class EapRevisionView:
    """Uma revisão da EAP: a linha de base ou a que incorporou uma SM aprovada.

    ``package_count`` sai dos pesos congelados da revisão (D5b) e ``change_code`` é o link da SM.
    No Portfólio a linha traz o projeto e quantas revisões ele tem.
    """

    revision: int
    revision_date: date
    alteration: str
    justification: str
    approved_by: str
    package_count: int
    id: int | None = None
    change_id: int | None = None
    change_code: str = ""
    project_id: int | None = None
    project_label: str = ""
    revision_count: int = 0


@dataclass(frozen=True)
class EapBreakdownView:
    """Um desdobramento da revisão vigente: de qual pacote de planejamento para qual de trabalho.

    ``source_closed`` diz que a origem ficou encerrada: peso zerado pelo desdobramento (ou origem
    ausente), ela sai da árvore mas o desdobramento continua legível.
    """

    id: int
    revision: int
    applied_on: date
    weight: Decimal
    source_code: str
    source_description: str
    target_code: str
    target_description: str
    author: str
    justification: str
    source_closed: bool = False


@dataclass(frozen=True)
class EapPendingChange:
    """Uma SM aprovada com impacto em escopo que nenhuma revisão da EAP incorporou ainda."""

    id: int
    code: str
    title: str
    project_id: int
    project_label: str


@dataclass(frozen=True)
class EapOverview:
    """A EAP do escopo: a árvore, os indicadores, as revisões e os desdobramentos da vigente."""

    reference_date: date
    is_portfolio: bool
    can_edit: bool
    can_manage: bool
    scope_label: str
    nodes: tuple[EapNode, ...]
    indicators: EapIndicators
    current_revision: EapRevisionView | None
    revisions: tuple[EapRevisionView, ...]
    breakdowns: tuple[EapBreakdownView, ...]
    pending_changes: tuple[EapPendingChange, ...]

    @property
    def root(self) -> EapNode:
        """A linha 0: o total do projeto ou do portfólio."""
        return self.nodes[0]

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no EAP: only the line 0 in the tree."""
        return len(self.nodes) <= 1


@dataclass(frozen=True)
class EapParameters:
    """Os parâmetros do grupo ``eap`` vigentes: as faixas, os limites e os modelos de etapas."""

    deviation_bands: tuple[Decimal, Decimal]
    max_package_weight: Decimal
    max_estimated_weight: Decimal
    stage_models: tuple[Mapping[str, Any], ...]

    def model_name(self, model: str | None) -> str:
        """O nome do modelo de etapas pelo id gravado no pacote; vazio sem modelo."""
        for candidate in self.stage_models:
            if str(candidate.get("id", "")) == (model or ""):
                return str(candidate.get("nome", ""))
        return ""


@dataclass(frozen=True)
class EapDictionaryOptions:
    """O que o formulário do dicionário oferece: as empresas, as pessoas e os itens da EAC."""

    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]
    eac_codes: tuple[str, ...]

    def company_choices(self) -> tuple[tuple[str, str], ...]:
        """As empresas como pares ``(valor, texto)`` para um seletor."""
        return tuple((str(item.id), item.name) for item in self.companies)

    def person_choices(self) -> tuple[tuple[str, str], ...]:
        """As pessoas como pares ``(valor, texto)`` para um seletor."""
        return tuple((str(item.id), item.name) for item in self.people)


@dataclass(frozen=True)
class _Lookups:
    """Os nomes que os nós mencionam, lidos uma vez por requisição."""

    companies: Mapping[int, str]
    people: Mapping[int, str]
    units: Mapping[int, str]
    eac_codes: Mapping[int, str]

    def company(self, company_id: int | None) -> str:
        return self.companies.get(company_id, "") if company_id is not None else ""

    def person(self, person_id: int | None) -> str:
        return self.people.get(person_id, "") if person_id is not None else ""

    def unit(self, unit_id: int | None) -> str:
        return self.units.get(unit_id, "") if unit_id is not None else ""

    def eac_code(self, item_id: int | None) -> str:
        return self.eac_codes.get(item_id, "") if item_id is not None else ""


@dataclass(frozen=True)
class _Reading:
    """O que toda leitura da EAP carrega: a sessão, os parâmetros vigentes, a data e os nomes."""

    session: Session
    parameters: EapParameters
    reference_date: date
    lookups: _Lookups


@dataclass(frozen=True)
class _TreeData:
    """Os itens do projeto já indexados: filhos, totais, etapas e medições."""

    by_parent: Mapping[int | None, tuple[EapItem, ...]]
    totals: Mapping[int, calculations.EapTotals]
    steps: Mapping[int, tuple[EapItemStep, ...]]
    measurements: Mapping[int, tuple[EapMeasurementView, ...]]


@dataclass(frozen=True)
class _ProjectSnapshot:
    """A EAP de um projeto lida uma vez: a árvore, os indicadores e as revisões."""

    nodes: tuple[EapNode, ...]
    indicators: EapIndicators
    revisions: tuple[EapRevisionView, ...]

    @property
    def root(self) -> EapNode:
        return self.nodes[0]

    @property
    def current_revision(self) -> EapRevisionView | None:
        current: EapRevisionView | None = None
        for view in self.revisions:
            if current is None or view.revision > current.revision:
                current = view
        return current


@dataclass(frozen=True)
class _PortfolioEntry:
    """Um projeto da carteira com EAP: a linha, o projeto, a EAP lida e o peso na carteira."""

    number: int
    project: configuracoes.ProjectSummary
    snapshot: _ProjectSnapshot
    weight: Decimal


# ── Leitura da árvore ─────────────────────────────────────────────────────


def eap_overview(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> EapOverview:
    """A EAP do escopo: a árvore do projeto (editável) ou a do Portfólio (somente leitura).

    The tree of the project carries the dictionary and the measurements of each package; the tree
    of the Portfólio has one line per project with EAP, with its weight in the portfolio, and one
    line per area, read-only, as the EAC does (D8). The real of each package comes from the
    current entries of its criterion and the nodes add up the children by weight (D5b). The
    reference date enters as an argument (D6).
    """
    rbac.require_module(user, MODULE)
    projects = _scope_projects(scope, configuracoes.list_projects(session))
    items_by_project = _items_by_project(session, [project.id for project in projects])
    reading = _Reading(
        session=session,
        parameters=_parameters(session, reference_date=reference_date),
        reference_date=reference_date,
        lookups=_lookups(
            session,
            items=[item for group in items_by_project.values() for item in group],
        ),
    )
    if scope.is_portfolio:
        return _portfolio_overview(
            reading, user=user, projects=projects, items_by_project=items_by_project
        )
    project = projects[0]
    return _project_overview(
        reading, user=user, project=project, items=items_by_project.get(project.id, ())
    )


def _project_overview(
    reading: _Reading,
    *,
    user: User,
    project: configuracoes.ProjectSummary,
    items: Sequence[EapItem],
) -> EapOverview:
    snapshot = _project_snapshot(reading, project, items)
    current = snapshot.current_revision
    breakdowns = _breakdowns(
        reading,
        project_id=project.id,
        revision=current.revision if current is not None else None,
        items=items,
    )
    pending = _pending_changes(
        reading.session,
        user=user,
        projects=(project,),
        used_by_project={project.id: _used_changes(snapshot.revisions)},
        reference_date=reading.reference_date,
    )
    return EapOverview(
        reference_date=reading.reference_date,
        is_portfolio=False,
        can_edit=rbac.can(user, Permission.WRITE),
        can_manage=rbac.can(user, Permission.MANAGE),
        scope_label=_project_label(project),
        nodes=snapshot.nodes,
        indicators=snapshot.indicators,
        current_revision=current,
        revisions=snapshot.revisions,
        breakdowns=breakdowns,
        pending_changes=pending,
    )


def _portfolio_overview(
    reading: _Reading,
    *,
    user: User,
    projects: Sequence[configuracoes.ProjectSummary],
    items_by_project: Mapping[int, tuple[EapItem, ...]],
) -> EapOverview:
    entries = _portfolio_entries(reading, projects, items_by_project)
    nodes: list[EapNode] = [_portfolio_root(reading, entries)]
    for entry in entries:
        nodes.append(_portfolio_project_node(reading, entry))
        nodes.extend(_portfolio_area_node(entry, area) for area in _area_nodes(entry.snapshot))
    pending = _pending_changes(
        reading.session,
        user=user,
        projects=[entry.project for entry in entries],
        used_by_project={
            entry.project.id: _used_changes(entry.snapshot.revisions) for entry in entries
        },
        reference_date=reading.reference_date,
    )
    return EapOverview(
        reference_date=reading.reference_date,
        is_portfolio=True,
        can_edit=False,
        can_manage=False,
        scope_label=PORTFOLIO_LABEL,
        nodes=tuple(nodes),
        indicators=_portfolio_indicators(nodes[0], entries),
        current_revision=None,
        revisions=_portfolio_revisions(entries),
        breakdowns=(),
        pending_changes=pending,
    )


def _portfolio_entries(
    reading: _Reading,
    projects: Sequence[configuracoes.ProjectSummary],
    items_by_project: Mapping[int, tuple[EapItem, ...]],
) -> tuple[_PortfolioEntry, ...]:
    """The projects with EAP, numbered in the order of the portfolio, with their weight in it."""
    from src.modulos.financeiro import service as financeiro

    weights = financeiro.portfolio_weights(reading.session, reference_date=reading.reference_date)
    entries: list[_PortfolioEntry] = []
    number = 0
    for project in projects:
        items = items_by_project.get(project.id, ())
        if not items:
            continue
        number += 1
        entries.append(
            _PortfolioEntry(
                number=number,
                project=project,
                snapshot=_project_snapshot(reading, project, items),
                weight=weights[project.id].weight if project.id in weights else Decimal(0),
            )
        )
    return tuple(entries)


def _portfolio_root(reading: _Reading, entries: Sequence[_PortfolioEntry]) -> EapNode:
    totals = calculations.eap_root_totals(
        [replace(_totals_of(entry.snapshot.root), weight=entry.weight) for entry in entries]
    )
    deviation = calculations.eap_deviation_pp(totals.actual, totals.predicted)
    return EapNode(
        id=None,
        code=ROOT_CODE,
        level=LEVEL_ROOT,
        description=PORTFOLIO_DESCRIPTION,
        project_id=None,
        project_code="",
        project_label=PORTFOLIO_LABEL,
        weight=totals.weight,
        predicted=totals.predicted,
        actual=totals.actual,
        deviation_pp=deviation,
        band=calculations.eap_deviation_band(deviation, reading.parameters.deviation_bands),
        start=totals.start,
        finish=totals.finish,
        packages=totals.packages,
        planning=totals.planning,
        overdue=totals.overdue,
        not_started=totals.not_started,
    )


def _portfolio_project_node(reading: _Reading, entry: _PortfolioEntry) -> EapNode:
    root = entry.snapshot.root
    return EapNode(
        id=None,
        code=str(entry.number),
        level=LEVEL_AREA,
        description=_project_label(entry.project),
        project_id=entry.project.id,
        project_code=entry.project.code,
        project_label=_project_label(entry.project),
        weight=entry.weight,
        predicted=root.predicted,
        actual=root.actual,
        deviation_pp=root.deviation_pp,
        band=root.band,
        start=root.start,
        finish=root.finish,
        packages=root.packages,
        planning=root.planning,
        overdue=root.overdue,
        not_started=root.not_started,
        weight_in_parent=entry.weight,
        owner_id=entry.project.manager_id,
        owner_name=reading.lookups.person(entry.project.manager_id),
    )


def _portfolio_area_node(entry: _PortfolioEntry, area: EapNode) -> EapNode:
    weight = (area.weight * entry.weight / calculations.PERCENT).quantize(
        calculations.TWO_PLACES, rounding=ROUND_HALF_UP
    )
    return replace(
        area,
        code=f"{entry.number}.{area.code}",
        level=LEVEL_SUB_AREA,
        project_id=entry.project.id,
        project_code=entry.project.code,
        project_label=_project_label(entry.project),
        weight=weight,
        weight_in_parent=area.weight,
        weight_in_project=area.weight,
    )


def _portfolio_indicators(root: EapNode, entries: Sequence[_PortfolioEntry]) -> EapIndicators:
    return EapIndicators(
        actual=root.actual,
        predicted=root.predicted,
        deviation_pp=root.deviation_pp,
        spi=calculations.spi_index(root.actual, root.predicted),
        work_packages=sum(entry.snapshot.indicators.work_packages for entry in entries),
        planning_packages=sum(entry.snapshot.indicators.planning_packages for entry in entries),
        planning_weight=None,
        areas=sum(entry.snapshot.indicators.areas for entry in entries),
        subareas=sum(entry.snapshot.indicators.subareas for entry in entries),
        overdue=sum(entry.snapshot.indicators.overdue for entry in entries),
        not_started=sum(entry.snapshot.indicators.not_started for entry in entries),
        late=sum(entry.snapshot.indicators.late for entry in entries),
        projects=len(entries),
    )


def _portfolio_revisions(entries: Sequence[_PortfolioEntry]) -> tuple[EapRevisionView, ...]:
    views: list[EapRevisionView] = []
    for entry in entries:
        current = entry.snapshot.current_revision
        if current is None:
            continue
        views.append(
            replace(
                current,
                project_id=entry.project.id,
                project_label=_project_label(entry.project),
                revision_count=len(entry.snapshot.revisions),
            )
        )
    return tuple(views)


def _project_snapshot(
    reading: _Reading, project: configuracoes.ProjectSummary, items: Sequence[EapItem]
) -> _ProjectSnapshot:
    nodes = _tree(reading, project, items)
    return _ProjectSnapshot(
        nodes=nodes,
        indicators=_indicators(nodes, projects=1),
        revisions=_revisions(reading.session, project_id=project.id),
    )


def _tree(
    reading: _Reading, project: configuracoes.ProjectSummary, items: Sequence[EapItem]
) -> tuple[EapNode, ...]:
    """The line 0 and every node of the project, depth first, in the order of the codes."""
    data = _tree_data(reading, items)
    roots = data.by_parent.get(None, ())
    nodes: list[EapNode] = [
        _root_node(
            reading, project, calculations.eap_root_totals([data.totals[root.id] for root in roots])
        )
    ]

    def append(item: EapItem, parent_weight: Decimal | None) -> None:
        node = _node(reading, project=project, item=item, data=data, parent_weight=parent_weight)
        nodes.append(node)
        for child in data.by_parent.get(item.id, ()):
            append(child, node.weight)

    for root in roots:
        append(root, None)
    return tuple(nodes)


def _tree_data(reading: _Reading, items: Sequence[EapItem]) -> _TreeData:
    live = [item for item in items if not _is_closed_package(item)]
    by_parent = _children_by_parent(live)
    steps = _steps_by_item(reading.session, [item.id for item in live])
    measurements = _measurements_by_item(
        reading.session, [item.id for item in live], reading.lookups
    )
    totals = _totals_by_item(
        live, by_parent=by_parent, steps=steps, reference_date=reading.reference_date
    )
    return _TreeData(by_parent=by_parent, totals=totals, steps=steps, measurements=measurements)


def _is_closed_package(item: EapItem) -> bool:
    """O pacote encerrado pelo desdobramento: nível 3 com peso zerado, fora da árvore."""
    return item.level == LEVEL_PACKAGE and (item.weight or Decimal(0)) <= 0


def _root_node(
    reading: _Reading, project: configuracoes.ProjectSummary, totals: calculations.EapTotals
) -> EapNode:
    deviation = calculations.eap_deviation_pp(totals.actual, totals.predicted)
    return EapNode(
        id=None,
        code=ROOT_CODE,
        level=LEVEL_ROOT,
        description=project.name,
        project_id=project.id,
        project_code=project.code,
        project_label=_project_label(project),
        weight=totals.weight,
        predicted=totals.predicted,
        actual=totals.actual,
        deviation_pp=deviation,
        band=calculations.eap_deviation_band(deviation, reading.parameters.deviation_bands),
        start=totals.start,
        finish=totals.finish,
        packages=totals.packages,
        planning=totals.planning,
        overdue=totals.overdue,
        not_started=totals.not_started,
    )


def _node(
    reading: _Reading,
    *,
    project: configuracoes.ProjectSummary,
    item: EapItem,
    data: _TreeData,
    parent_weight: Decimal | None,
) -> EapNode:
    totals = data.totals[item.id]
    deviation = calculations.eap_deviation_pp(totals.actual, totals.predicted)
    return EapNode(
        id=item.id,
        code=item.code,
        level=item.level,
        description=item.description,
        project_id=project.id,
        project_code=project.code,
        project_label=_project_label(project),
        weight=totals.weight,
        predicted=totals.predicted,
        actual=totals.actual,
        deviation_pp=deviation,
        band=calculations.eap_deviation_band(deviation, reading.parameters.deviation_bands),
        start=totals.start,
        finish=totals.finish,
        packages=totals.packages,
        planning=totals.planning,
        overdue=totals.overdue,
        not_started=totals.not_started,
        weight_in_parent=_share_of(totals.weight, parent_weight),
        kind=item.kind,
        criterion=item.criterion,
        model=reading.parameters.model_name(item.model),
        unit=reading.lookups.unit(item.unit_id),
        quantity=item.quantity,
        executed=item.executed,
        state=item.state,
        estimated_pct=item.estimated_pct,
        deliverable=item.deliverable or "",
        acceptance=item.acceptance or "",
        company_id=item.company_id,
        company_name=reading.lookups.company(item.company_id),
        owner_id=item.owner_id,
        owner_name=reading.lookups.person(item.owner_id),
        eac_item_id=item.eac_item_id,
        eac_code=reading.lookups.eac_code(item.eac_item_id),
        steps=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct)
            for step in data.steps.get(item.id, ())
        ),
        measurements=data.measurements.get(item.id, ()),
        version=item.version,
    )


def _totals_by_item(
    items: Sequence[EapItem],
    *,
    by_parent: Mapping[int | None, tuple[EapItem, ...]],
    steps: Mapping[int, tuple[EapItemStep, ...]],
    reference_date: date,
) -> dict[int, calculations.EapTotals]:
    """The totals of every item: the real of the criterion for a package, the children for the rest."""
    totals: dict[int, calculations.EapTotals] = {}

    def compute(item: EapItem) -> calculations.EapTotals:
        if item.id in totals:
            return totals[item.id]
        if item.level == LEVEL_PACKAGE:
            found = calculations.eap_package_totals(
                _package(item, steps.get(item.id, ())), reference_date=reference_date
            )
        else:
            found = calculations.eap_node_totals(
                [compute(child) for child in by_parent.get(item.id, ())]
            )
        totals[item.id] = found
        return found

    for item in items:
        compute(item)
    return totals


def _package(item: EapItem, steps: Sequence[EapItemStep]) -> calculations.EapPackage:
    return calculations.EapPackage(
        kind=item.kind or "",
        weight=item.weight or Decimal(0),
        predicted=item.predicted or Decimal(0),
        start=item.start,
        finish=item.finish,
        criterion=item.criterion,
        etapas=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct) for step in steps
        ),
        quantity=item.quantity,
        executed=item.executed,
        state=item.state,
        estimated_pct=item.estimated_pct,
    )


def _indicators(nodes: Sequence[EapNode], *, projects: int) -> EapIndicators:
    root = nodes[0]
    work = [node for node in nodes if node.is_work_package]
    planning = [node for node in nodes if node.is_planning_package]
    return EapIndicators(
        actual=root.actual,
        predicted=root.predicted,
        deviation_pp=root.deviation_pp,
        spi=calculations.spi_index(root.actual, root.predicted),
        work_packages=len(work),
        planning_packages=len(planning),
        planning_weight=_weight_of(planning),
        areas=sum(1 for node in nodes if node.level == LEVEL_AREA),
        subareas=sum(1 for node in nodes if node.level == LEVEL_SUB_AREA),
        overdue=sum(1 for node in work if node.overdue),
        not_started=sum(1 for node in work if node.not_started),
        late=sum(1 for node in work if node.band == calculations.DANGER_BAND),
        projects=projects,
    )


def _revisions(session: Session, *, project_id: int) -> tuple[EapRevisionView, ...]:
    """The revisions of the project, oldest first, with the frozen package count and the SM link."""
    from src.modulos.governanca import service as governanca

    records = list(
        session.scalars(
            select(EapRevision)
            .where(EapRevision.project_id == project_id)
            .order_by(EapRevision.revision, EapRevision.id)
        )
    )
    if not records:
        return ()
    counts = _revision_package_counts(session, [record.id for record in records])
    codes = governanca.change_codes(
        session,
        change_ids=[record.change_id for record in records if record.change_id is not None],
    )
    names = configuracoes.person_names(session, {record.approved_by_id for record in records})
    return tuple(
        EapRevisionView(
            id=record.id,
            revision=record.revision,
            revision_date=record.revision_date,
            alteration=record.alteration,
            justification=record.justification,
            approved_by=names.get(record.approved_by_id, ""),
            package_count=counts.get(record.id, 0),
            change_id=record.change_id,
            change_code=codes.get(record.change_id, "") if record.change_id is not None else "",
        )
        for record in records
    )


def _revision_package_counts(session: Session, revision_ids: Sequence[int]) -> dict[int, int]:
    """How many packages each revision froze: the level-3 items of ``eap_revisao_item``."""
    if not revision_ids:
        return {}
    statement = (
        select(EapRevisionItem.revision_id, func.count())
        .join(EapItem, EapItem.id == EapRevisionItem.item_id)
        .where(EapRevisionItem.revision_id.in_(revision_ids), EapItem.level == LEVEL_PACKAGE)
        .group_by(EapRevisionItem.revision_id)
    )
    counts: dict[int, int] = {}
    for row in session.execute(statement):
        counts[int(row[0])] = int(row[1])
    return counts


def _breakdowns(
    reading: _Reading,
    *,
    project_id: int,
    revision: int | None,
    items: Sequence[EapItem],
) -> tuple[EapBreakdownView, ...]:
    """The breakdowns of the current revision: from which planning package to which work package."""
    if revision is None:
        return ()
    records = list(
        reading.session.scalars(
            select(EapBreakdown)
            .where(EapBreakdown.project_id == project_id, EapBreakdown.revision == revision)
            .order_by(EapBreakdown.id)
        )
    )
    if not records:
        return ()
    by_id = {item.id: item for item in items}
    names = configuracoes.person_names(reading.session, {record.by_id for record in records})
    views: list[EapBreakdownView] = []
    for record in records:
        source = by_id.get(record.source_item_id)
        target = by_id.get(record.target_item_id)
        views.append(
            EapBreakdownView(
                id=record.id,
                revision=record.revision,
                applied_on=record.applied_on,
                weight=record.weight,
                source_code=source.code if source is not None else "",
                source_description=source.description if source is not None else "",
                target_code=target.code if target is not None else "",
                target_description=target.description if target is not None else "",
                author=names.get(record.by_id, ""),
                justification=record.justification,
                source_closed=source is None or _is_closed_package(source),
            )
        )
    return tuple(views)


def _pending_changes(
    session: Session,
    *,
    user: User,
    projects: Sequence[configuracoes.ProjectSummary],
    used_by_project: Mapping[int, frozenset[int]],
    reference_date: date,
) -> tuple[EapPendingChange, ...]:
    """As SMs aprovadas com impacto em escopo que nenhuma revisão da EAP incorporou ainda.

    The list comes from the Governança facade (the approved changes and their impact, through
    ``find_change_sheet``); the incorporation itself is the revision flow of ISSUE-038, so this is
    what the facades already give today. The scope-impact cut mirrors the prototype: an impact
    whose scope text is empty or says "sem impacto" does not count.
    """
    from src.modulos.governanca import service as governanca

    pending: list[EapPendingChange] = []
    for project in projects:
        used = used_by_project.get(project.id, frozenset())
        for change in governanca.approved_changes(session, project_id=project.id):
            if change.id in used:
                continue
            sheet = governanca.find_change_sheet(
                session, user=user, code=change.code, reference_date=reference_date
            )
            if sheet is None or not _has_scope_impact(sheet.impact):
                continue
            pending.append(
                EapPendingChange(
                    id=change.id,
                    code=change.code,
                    title=change.title,
                    project_id=project.id,
                    project_label=sheet.project_label,
                )
            )
    return tuple(pending)


def _has_scope_impact(impact: Any) -> bool:
    from src.modulos.governanca import calculations as governanca_calculations

    return governanca_calculations.has_scope_impact(impact.scope if impact is not None else "")


def _parameters(session: Session, *, reference_date: date) -> EapParameters:
    """The ``eap`` group in force on the date, with the initial values when there is no version."""
    values = (
        configuracoes.current_group(session, group=EAP_GROUP, reference_date=reference_date)
        or configuracoes.INITIAL_PARAMETERS[EAP_GROUP]
    )
    return EapParameters(
        deviation_bands=_deviation_bands(values),
        max_package_weight=_decimal_value(
            values.get("pesoMaximoPacotePct"), DEFAULT_MAX_PACKAGE_WEIGHT
        ),
        max_estimated_weight=_decimal_value(
            values.get("estimadoMaximoPct"), DEFAULT_MAX_ESTIMATED_WEIGHT
        ),
        stage_models=_stage_models(values),
    )


def _deviation_bands(values: Mapping[str, Any]) -> tuple[Decimal, Decimal]:
    raw = values.get("faixasDesvioPP")
    if not isinstance(raw, Sequence) or isinstance(raw, str) or len(raw) != 2:
        return DEFAULT_DEVIATION_BANDS
    return (
        _decimal_value(raw[0], DEFAULT_DEVIATION_BANDS[0]),
        _decimal_value(raw[1], DEFAULT_DEVIATION_BANDS[1]),
    )


def _decimal_value(value: Any, default: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return default


def _stage_models(values: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = values.get("modelosEtapas")
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return ()
    return tuple(item for item in raw if isinstance(item, Mapping))


# ── Escrita do dicionário ─────────────────────────────────────────────────


def update_dictionary(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    form: Mapping[str, str],
) -> EapItem:
    """Save the dictionary of a package: the descriptive fields, never the baseline.

    The description, the deliverable, the acceptance, the company, the owner and the EAC item are
    the dictionary (the prototype's ``eapEditarPacote``); the weight, the dates and the criterion
    belong to the baseline and only change through a revision (ISSUE-038). Writing asks for Membro
    and the Portfólio is refused: it is read-only (D8). A stale version is refused with 409.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    item = _editable_package(session, scope=scope, item_id=item_id)
    data = validation.parse_dictionary_form(
        form, _dictionary_choices(session, project_id=item.project_id)
    )
    recording.update(
        session,
        user_id=user.id,
        record=item,
        changes={
            "description": data.description,
            "deliverable": data.deliverable,
            "acceptance": data.acceptance,
            "company_id": data.company_id,
            "owner_id": data.owner_id,
            "eac_item_id": _eac_item_id(session, project_id=item.project_id, code=data.eac_code),
        },
        version=form.get("versao"),
    )
    return item


def _editable_package(session: Session, *, scope: Scope, item_id: int) -> EapItem:
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    item = session.get(EapItem, item_id)
    if item is None:
        raise InvalidDataError(PACKAGE_NOT_FOUND_MESSAGE)
    if item.project_id != scope.project_id:
        raise AccessDeniedError(OTHER_PROJECT_MESSAGE)
    if item.level != LEVEL_PACKAGE:
        raise InvalidDataError(ONLY_PACKAGES_MESSAGE)
    return item


def _dictionary_choices(session: Session, *, project_id: int) -> validation.DictionaryChoices:
    from src.modulos.financeiro import service as financeiro

    levels = financeiro.eac_item_levels(session, project_id=project_id)
    return validation.DictionaryChoices(
        company_ids=frozenset(item.id for item in configuracoes.list_company_options(session)),
        person_ids=frozenset(item.id for item in configuracoes.list_person_options(session)),
        eac_codes=frozenset(code for code, level in levels.items() if level >= LEVEL_PACKAGE),
    )


def _eac_item_id(session: Session, *, project_id: int, code: str | None) -> int | None:
    if not code:
        return None
    from src.modulos.financeiro import service as financeiro

    found = financeiro.eac_item_ids_by_code(session, project_id=project_id, codes=[code])
    return found.get(code)


def dictionary_node(
    session: Session, *, user: User, scope: Scope, item_id: int, reference_date: date
) -> EapNode:
    """O nó do pacote dentro do escopo, como a árvore o mostra; o Portfólio é recusado (D8).

    It is what the form of the dictionary opens on: the read-only Portfólio has no package to
    edit, an id that is not a package is refused and a project of the scope that does not exist
    comes back as the message of the tree.
    """
    rbac.require_module(user, MODULE)
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    overview = eap_overview(session, user=user, scope=scope, reference_date=reference_date)
    node = next((candidate for candidate in overview.nodes if candidate.id == item_id), None)
    if node is None:
        raise InvalidDataError(PACKAGE_NOT_FOUND_MESSAGE)
    if node.level != LEVEL_PACKAGE:
        raise InvalidDataError(ONLY_PACKAGES_MESSAGE)
    return node


def dictionary_options(session: Session, *, project_id: int) -> EapDictionaryOptions:
    """As listas do formulário do dicionário: empresas, pessoas e os itens de custo da EAC."""
    from src.modulos.financeiro import service as financeiro

    levels = financeiro.eac_item_levels(session, project_id=project_id)
    return EapDictionaryOptions(
        companies=tuple(configuracoes.list_company_options(session)),
        people=tuple(configuracoes.list_person_options(session)),
        eac_codes=tuple(sorted(code for code, level in levels.items() if level >= LEVEL_PACKAGE)),
    )


def dictionary_fields(node: EapNode) -> dict[str, str]:
    """Os valores do formulário do dicionário, com os mesmos nomes que o formulário envia."""
    return {
        "descricao": node.description,
        "entregavel": node.deliverable,
        "aceitacao": node.acceptance,
        "empresa": "" if node.company_id is None else str(node.company_id),
        "responsavel": "" if node.owner_id is None else str(node.owner_id),
        "eac": node.eac_code,
        "versao": str(node.version),
    }


# ── Medição do avanço (ISSUE-037) ─────────────────────────────────────────


PLANNING_PACKAGE_PROGRESS_MESSAGE = (
    "Pacote de planejamento não recebe medição: desdobre-o em pacotes de trabalho antes."
)


IMPORT_NOTE = "Importação do avanço"


@dataclass(frozen=True)
class ProgressView:
    """A medição registrada: o código do pacote, de quanto para quanto, o estorno e o item."""

    code: str
    from_pct: Decimal
    to_pct: Decimal
    is_reversal: bool
    item: EapItem


@dataclass(frozen=True)
class ProgressImport:
    """O resultado da importação: quantas linhas gravaram e o motivo de cada linha recusada."""

    applied: int
    errors: tuple[str, ...]


def register_progress(
    session: Session,
    *,
    user: User,
    scope: Scope,
    item_id: int,
    form: Mapping[str, str],
    reference_date: date,
) -> ProgressView:
    """Registra o avanço de um pacote de trabalho pelas entradas do seu critério.

    The entries of the criterion (the % of each step, the executed quantity, the milestone state
    or the estimated %) are written to the item and its steps, and the measurement is born as an
    immutable fact with the date, de/para, author and note. The accumulated progress does not go
    back: a reversal needs Gestor (403) and a justification of 10 characters or more (422), and
    the justification travels in the note. Writing asks for Membro, the date cannot pass the
    reference date and the Portfólio is read-only (D8). The version the screen opened protects
    the item (409).
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    item = _measurable_package(session, scope=scope, item_id=item_id)
    data = validation.parse_progress_form(
        form,
        _progress_package(
            item,
            _steps_of(session, item.id),
            unit=_unit_code(session, item.unit_id),
        ),
        reference_date=reference_date,
        is_manager=rbac.can(user, Permission.MANAGE),
        max_estimated_weight=_parameters(
            session, reference_date=reference_date
        ).max_estimated_weight,
    )
    _write_entries(
        session,
        user=user,
        item=item,
        entries=data.entries,
        version=form.get("versao"),
    )
    _record_measurement(
        session,
        user=user,
        item=item,
        measured_on=data.measured_on,
        from_pct=data.from_pct,
        to_pct=data.to_pct,
        note=data.note or None,
    )
    return ProgressView(
        code=item.code,
        from_pct=data.from_pct,
        to_pct=data.to_pct,
        is_reversal=calculations.eap_progress_regression(data.from_pct, data.to_pct),
        item=item,
    )


def progress_import_packages(
    session: Session, *, project_id: int
) -> dict[str, validation.ProgressPackage]:
    """Os pacotes de nível 3 do projeto como a importação do avanço os lê, sem gravar nada.

    É o que o importador de planilha usa para conferir cada linha: o real corrente do critério,
    a unidade e as etapas correntes, na transação da requisição.
    """
    return _progress_packages(
        session, tuple(_progress_items(session, project_id=project_id).values())
    )


def import_progress(
    session: Session,
    *,
    user: User,
    scope: Scope,
    rows: Sequence[validation.ImportRowInput],
    measurement_date: date,
    reference_date: date,
) -> ProgressImport:
    """Importa o avanço acumulado por pacote, linha a linha, sem estorno.

    Every line is checked on its own (``parse_import_rows``): a package that does not exist, a
    planning package, a milestone off its degrees, an executed quantity above the baseline and a
    line that regresses are refused with the motive; a line without change has nothing to write.
    An accepted line writes the entries and one measurement, dated with ``measurement_date`` and
    noted as an import. The import never reverses: a reversal only goes through the screen, with
    justification. Writing asks for Membro and the date cannot pass the reference date. Everything
    runs in the transaction the route opened.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    project_id = scope.require_project()
    if measurement_date > reference_date:
        raise InvalidDataError(
            {validation.FIELD_MEASURED_ON: validation.MEASUREMENT_DATE_FUTURE_MESSAGE}
        )
    items = _progress_items(session, project_id=project_id)
    packages = _progress_packages(session, tuple(items.values()))
    applied, errors = 0, []
    for row in rows:
        result = validation.parse_import_rows((row,), packages)[0]
        if result.error:
            errors.append(result.error)
            continue
        if result.entries is None or result.from_pct is None or result.to_pct is None:
            continue
        item = items[result.code]
        _write_entries(
            session,
            user=user,
            item=item,
            entries=result.entries,
            version=str(item.version),
        )
        _record_measurement(
            session,
            user=user,
            item=item,
            measured_on=measurement_date,
            from_pct=result.from_pct,
            to_pct=result.to_pct,
            note=IMPORT_NOTE,
        )
        packages[result.code] = replace(packages[result.code], current=result.to_pct)
        applied += 1
    return ProgressImport(applied=applied, errors=tuple(errors))


def _measurable_package(session: Session, *, scope: Scope, item_id: int) -> EapItem:
    """O pacote de trabalho do escopo que pode receber medição."""
    item = _editable_package(session, scope=scope, item_id=item_id)
    if item.kind == calculations.PLANNING_PACKAGE:
        raise InvalidDataError(PLANNING_PACKAGE_PROGRESS_MESSAGE)
    return item


def _write_entries(
    session: Session,
    *,
    user: User,
    item: EapItem,
    entries: validation.ProgressEntries,
    version: int | str | None,
) -> None:
    """Grava as entradas do critério no item e nas etapas, com a trilha de cada mudança."""
    recording.update(
        session,
        user_id=user.id,
        record=item,
        changes=_entry_changes(entries),
        version=version,
    )
    _save_steps(session, user=user, item=item, steps=entries.steps)


def _entry_changes(entries: validation.ProgressEntries) -> dict[str, Any]:
    """Os campos do item que o critério atualiza; as etapas mudam nas linhas filhas."""
    values = {
        "executed": entries.executed,
        "state": entries.state,
        "estimated_pct": entries.estimated_pct,
    }
    return {field: value for field, value in values.items() if value is not None}


def _save_steps(
    session: Session, *, user: User, item: EapItem, steps: Sequence[calculations.EapStep]
) -> None:
    """Grava o % concluído das etapas que mudaram, com a trilha de cada uma."""
    if not steps:
        return
    records = session.scalars(
        select(EapItemStep)
        .where(EapItemStep.item_id == item.id)
        .order_by(EapItemStep.order, EapItemStep.id)
    ).all()
    for record, step in zip(records, steps, strict=False):
        if step.pct is None or record.pct == step.pct:
            continue
        before = audit.snapshot(record)
        record.pct = step.pct
        session.flush()
        audit.changed(
            session, user_id=user.id, entity=record.__tablename__, record=record, before=before
        )


def _record_measurement(
    session: Session,
    *,
    user: User,
    item: EapItem,
    measured_on: date,
    from_pct: Decimal,
    to_pct: Decimal,
    note: str | None,
) -> EapMeasurement:
    """Grava a medição como fato imutável, com o autor sendo a pessoa do usuário."""
    return recording.create(
        session,
        user_id=user.id,
        record=EapMeasurement(
            item_id=item.id,
            author_id=user.person_id,
            measured_on=measured_on,
            from_pct=from_pct,
            to_pct=to_pct,
            note=note,
        ),
    )


def _progress_items(session: Session, *, project_id: int) -> dict[str, EapItem]:
    """Os pacotes (nível 3) do projeto pelo código, inclusive os de planejamento."""
    statement = (
        select(EapItem)
        .where(EapItem.project_id == project_id, EapItem.level == LEVEL_PACKAGE)
        .order_by(EapItem.id)
    )
    return {item.code: item for item in session.scalars(statement)}


def _progress_packages(
    session: Session, items: Sequence[EapItem]
) -> dict[str, validation.ProgressPackage]:
    """Os pacotes como a validação da importação os lê, com a unidade e as etapas correntes."""
    steps = _steps_by_item(session, [item.id for item in items])
    units = {unit.id: unit.code for unit in configuracoes.list_measure_units(session)}
    return {
        item.code: _progress_package(
            item, steps.get(item.id, ()), unit=units.get(item.unit_id or 0, "")
        )
        for item in items
    }


def _progress_package(
    item: EapItem, steps: Sequence[EapItemStep], *, unit: str
) -> validation.ProgressPackage:
    """O pacote de nível 3 com o real corrente e as entradas correntes do seu critério."""
    return validation.ProgressPackage(
        kind=item.kind or "",
        criterion=item.criterion,
        weight=item.weight or Decimal(0),
        current=_item_progress(item, steps),
        quantity=item.quantity,
        unit=unit,
        steps=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct) for step in steps
        ),
    )


def _item_progress(item: EapItem, steps: Sequence[EapItemStep]) -> Decimal:
    """O real corrente do pacote, calculado das entradas do critério (D5b)."""
    return calculations.eap_package_progress(
        item.criterion,
        etapas=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct) for step in steps
        ),
        quantity=item.quantity,
        executed=item.executed,
        state=item.state,
        estimated_pct=item.estimated_pct,
    )


def _steps_of(session: Session, item_id: int) -> tuple[EapItemStep, ...]:
    """As etapas correntes de um pacote, na ordem."""
    return _steps_by_item(session, [item_id]).get(item_id, ())


def _unit_code(session: Session, unit_id: int | None) -> str:
    """O código da unidade de medida do pacote; vazio sem unidade."""
    if unit_id is None:
        return ""
    return next(
        (unit.code for unit in configuracoes.list_measure_units(session) if unit.id == unit_id),
        "",
    )


# ── Revisões da EAP e desdobramento (ISSUE-038) ───────────────────────────


REVISION_MANAGER_MESSAGE = "Nova revisão da EAP exige papel Gestor."


REVISION_EMPTY_MESSAGE = "A revisão precisa alterar ao menos um pacote."


@dataclass(frozen=True)
class RevisionRequest:
    """O que a tela da EAP pede na revisão: a SM, a justificativa, os ajustes e os pacotes novos."""

    change_code: str
    justification: str
    adjustments: tuple[validation.RevisionAdjustment, ...] = ()
    new_packages: tuple[validation.NewPackageData, ...] = ()


@dataclass(frozen=True)
class RevisionResult:
    """O que a revisão fez: a revisão gravada, a SM e os códigos incluídos e ajustados."""

    revision: int
    revision_date: date
    change_code: str
    new_codes: tuple[str, ...]
    adjusted_codes: tuple[str, ...]
    alteration: str


def create_revision(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: RevisionRequest,
    reference_date: date,
) -> RevisionResult:
    """Cria a revisão da EAP a partir da SM aprovada com impacto em escopo (papel Gestor).

    A SM vem da Governança já aprovada, com impacto em escopo e ainda não incorporada; a revisão
    ajusta peso, quantidade e término dos pacotes afetados, inclui os pacotes novos e reescala os
    pesos livres para a soma fechar 100 exatos, congelando o peso de todos os pacotes de nível 3.
    A revisão e a marca da SM na Governança entram na mesma transação.
    """
    rbac.require_module(user, MODULE)
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(REVISION_MANAGER_MESSAGE)
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    project_id = scope.require_project()
    if not request.adjustments and not request.new_packages:
        raise InvalidDataError(REVISION_EMPTY_MESSAGE)
    source = _revision_source(session, change_code=request.change_code, project_id=project_id)
    justification = request.justification.strip()
    if len(justification) < validation.JUSTIFICATION_MIN_CHARACTERS:
        raise InvalidDataError(
            {validation.FIELD_JUSTIFICATION: validation.REVISION_JUSTIFICATION_MESSAGE}
        )
    parameters = _parameters(session, reference_date=reference_date)
    items = tuple(_items_by_project(session, [project_id]).get(project_id, ()))
    packages = {item.code: item for item in items if item.level == LEVEL_PACKAGE}
    fixed = _adjustment_weights(
        packages=packages, adjustments=request.adjustments, parameters=parameters
    )
    _require_new_packages(request.new_packages, items=items, parameters=parameters)
    fixed_total = sum(fixed.values(), Decimal(0)) + sum(
        (data.weight for data in request.new_packages), Decimal(0)
    )
    problem = validation.revision_fixed_weight_error(fixed_total)
    if problem:
        raise InvalidDataError({validation.FIELD_WEIGHT: problem})
    _apply_adjustments(session, user=user, packages=packages, adjustments=request.adjustments)
    created = _create_revision_packages(
        session,
        user=user,
        project_id=project_id,
        items=items,
        known=tuple(packages.values()),
        new_packages=request.new_packages,
        reference_date=reference_date,
    )
    fixed.update({item.code: item.weight or Decimal(0) for item in created})
    _rescale_free_weights(session, user=user, packages=packages, fixed=fixed)
    frozen = _packages_by_code(session, project_id)
    total_problem = validation.hundred_rule_error(
        [item.weight or Decimal(0) for item in frozen.values()]
    )
    if total_problem:
        raise InvalidDataError({validation.FIELD_WEIGHT: total_problem})
    adjusted_codes = tuple(adjustment.code for adjustment in request.adjustments)
    new_codes = tuple(item.code for item in created)
    alteration = _alteration(new_codes, adjusted_codes)
    revision = _next_revision(session, project_id=project_id)
    record = recording.create(
        session,
        user_id=user.id,
        record=EapRevision(
            project_id=project_id,
            change_id=source.change_id,
            approved_by_id=user.person_id,
            revision=revision,
            revision_date=reference_date,
            alteration=alteration,
            justification=justification,
        ),
    )
    _freeze_revision(session, revision_id=record.id, packages=tuple(frozen.values()))
    freeze_curve(
        session, project_id=project_id, revision_id=record.id, reference_date=reference_date
    )
    from src.modulos.governanca import service as governanca

    governanca.incorporate_eap_revision(
        session, user=user, change_id=source.change_id, revision=revision
    )
    return RevisionResult(
        revision=revision,
        revision_date=reference_date,
        change_code=source.code,
        new_codes=new_codes,
        adjusted_codes=adjusted_codes,
        alteration=alteration,
    )


@dataclass(frozen=True)
class BreakdownRequest:
    """O desdobramento pedido pela tela: o pacote novo (recurso desdobramento) já validado."""

    package: validation.NewPackageData


@dataclass(frozen=True)
class BreakdownResult:
    """O que o desdobramento fez: o pacote criado, a origem e se ela ficou encerrada."""

    code: str
    source_code: str
    source_closed: bool


def breakdown_package(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: BreakdownRequest,
    reference_date: date,
) -> BreakdownResult:
    """Desdobra um pacote de planejamento em um de trabalho, sem mudar o total do projeto.

    O peso sai da origem para o pacote novo, o previsto é o da origem e, com peso zero, a origem
    fica encerrada: sai da árvore, mas o desdobramento continua legível. Não cria revisão; a
    escrita pede Membro, como o dicionário (o protótipo não pede papel Gestor).
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    project_id = scope.require_project()
    data = request.package
    if data.resource != validation.BREAKDOWN:
        raise InvalidDataError({validation.FIELD_RESOURCE: validation.RESOURCE_MESSAGE})
    items = tuple(_items_by_project(session, [project_id]).get(project_id, ()))
    packages = {item.code: item for item in items if item.level == LEVEL_PACKAGE}
    origin = packages.get(data.source_code or "")
    if origin is None or origin.kind != calculations.PLANNING_PACKAGE:
        raise InvalidDataError({validation.FIELD_ORIGIN: validation.ORIGIN_MESSAGE})
    if data.weight > (origin.weight or Decimal(0)):
        raise InvalidDataError(
            {
                validation.FIELD_WEIGHT: validation.BREAKDOWN_WEIGHT_MESSAGE.format(
                    code=origin.code, weight=_plain_weight(origin.weight)
                )
            }
        )
    parent = next((item for item in items if item.code == data.parent_code), None)
    if parent is None or parent.level != LEVEL_SUB_AREA:
        raise InvalidDataError({validation.FIELD_PARENT: validation.PARENT_MESSAGE})
    code = _next_package_code(tuple(packages.values()), parent)
    created = _create_eap_package(
        session,
        user=user,
        project_id=project_id,
        data=data,
        code=code,
        parent=parent,
        kind=calculations.WORK_PACKAGE,
        predicted=origin.predicted or Decimal(0),
    )
    remaining = (origin.weight or Decimal(0)) - data.weight
    recording.update(
        session,
        user_id=user.id,
        record=origin,
        changes={"weight": remaining},
        version=origin.version,
    )
    revision = _current_revision(session, project_id=project_id)
    recording.create(
        session,
        user_id=user.id,
        record=EapBreakdown(
            project_id=project_id,
            source_item_id=origin.id,
            target_item_id=created.id,
            by_id=user.person_id,
            revision=revision,
            applied_on=reference_date,
            weight=data.weight,
            justification=data.justification.strip(),
        ),
    )
    return BreakdownResult(code=code, source_code=origin.code, source_closed=remaining <= 0)


@dataclass(frozen=True)
class EapChoice:
    """Uma opção dos formulários da EAP: o valor que o formulário envia e o texto que a pessoa lê."""

    value: str
    text: str


@dataclass(frozen=True)
class EapFormOptions:
    """O que os formulários da revisão, do pacote novo e da importação oferecem e conferem.

    As listas saem do projeto do escopo e dos cadastros; ``states`` e ``limits`` são o que as
    regras da validação leem, na mesma forma em que a fachada da revisão as lê.
    """

    subareas: tuple[EapChoice, ...]
    planning_packages: tuple[EapChoice, ...]
    work_packages: tuple[EapChoice, ...]
    changes: tuple[EapChoice, ...]
    stage_models: tuple[Mapping[str, Any], ...]
    units: tuple[configuracoes.MeasureUnitSummary, ...]
    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]
    eac_codes: tuple[str, ...]
    states: Mapping[str, validation.PackageState]
    limits: validation.RevisionLimits
    next_revision: int

    def unit_choices(self) -> tuple[tuple[str, str], ...]:
        """As unidades como pares ``(valor, texto)`` para um seletor."""
        return tuple((unit.code, unit.code) for unit in self.units)

    def company_choices(self) -> tuple[tuple[str, str], ...]:
        """As empresas como pares ``(valor, texto)`` para um seletor."""
        return tuple((str(item.id), item.name) for item in self.companies)

    def person_choices(self) -> tuple[tuple[str, str], ...]:
        """As pessoas como pares ``(valor, texto)`` para um seletor."""
        return tuple((str(item.id), item.name) for item in self.people)


def revision_form_options(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> EapFormOptions:
    """As listas e os limites dos formulários da revisão, do pacote novo e da importação.

    Lê o projeto do escopo numa passada: as subáreas, os pacotes de planejamento com peso a
    desdobrar, as SMs aprovadas com impacto em escopo pendentes de incorporação, os modelos de
    etapas e os tetos de peso dos parâmetros vigentes, mais os cadastros (unidades, empresas,
    pessoas e itens da EAC) que os formulários mostram e a importação confere. O Portfólio é
    recusado, como nas demais escritas da EAP.
    """
    rbac.require_module(user, MODULE)
    if scope.is_portfolio:
        raise AccessDeniedError(EAP_PORTFOLIO_READ_ONLY_MESSAGE)
    from src.modulos.financeiro import service as financeiro
    from src.modulos.governanca import service as governanca

    project_id = scope.require_project()
    items = tuple(_items_by_project(session, [project_id]).get(project_id, ()))
    parameters = _parameters(session, reference_date=reference_date)
    levels = financeiro.eac_item_levels(session, project_id=project_id)
    titles = {
        change.code: change.title
        for change in governanca.approved_changes(session, project_id=project_id)
    }
    return EapFormOptions(
        subareas=tuple(
            EapChoice(value=item.code, text=f"{item.code} · {item.description}")
            for item in items
            if item.level == LEVEL_SUB_AREA
        ),
        planning_packages=tuple(
            EapChoice(
                value=item.code,
                text=(
                    f"{item.code} · {item.description} · {_plain_weight(item.weight)}% a desdobrar"
                ),
            )
            for item in items
            if item.level == LEVEL_PACKAGE
            and item.kind == calculations.PLANNING_PACKAGE
            and (item.weight or Decimal(0)) > 0
        ),
        work_packages=tuple(
            EapChoice(
                value=item.code,
                text=f"{item.code} · {item.description} · {_plain_weight(item.weight)}%",
            )
            for item in items
            if item.level == LEVEL_PACKAGE
        ),
        changes=tuple(
            EapChoice(
                value=source.code,
                text=_change_label(source.code, titles.get(source.code, "")),
            )
            for source in governanca.eap_revision_sources(session, project_id=project_id)
        ),
        stage_models=parameters.stage_models,
        units=tuple(configuracoes.list_measure_units(session)),
        companies=tuple(configuracoes.list_company_options(session)),
        people=tuple(configuracoes.list_person_options(session)),
        eac_codes=tuple(sorted(code for code, level in levels.items() if level >= LEVEL_PACKAGE)),
        states=_package_states(items),
        limits=validation.RevisionLimits(
            max_package_weight=parameters.max_package_weight,
            max_estimated_weight=parameters.max_estimated_weight,
        ),
        next_revision=_next_revision(session, project_id=project_id),
    )


def _package_states(items: Sequence[EapItem]) -> dict[str, validation.PackageState]:
    """O estado de cada item do projeto como as regras da revisão e da importação o leem."""
    return {
        item.code: validation.PackageState(
            code=item.code,
            level=item.level,
            kind=item.kind or "",
            criterion=item.criterion,
            weight=item.weight or Decimal(0),
            quantity=item.quantity,
            executed=item.executed,
            start=item.start,
            finish=item.finish,
        )
        for item in items
    }


def _change_label(code: str, title: str) -> str:
    """A SM como um select a mostra: ``SM-... · Título``."""
    return f"{code} · {title}" if title else code


def _revision_source(session: Session, *, change_code: str, project_id: int) -> ChangeEapSource:
    """A SM aprovada com impacto em escopo pendente do projeto, ou a recusa do protótipo."""
    from src.modulos.governanca import service as governanca

    wanted = (change_code or "").strip()
    ids = governanca.change_ids_by_code(session, codes=[wanted])
    source = governanca.change_eap_source(session, change_id=ids[wanted]) if wanted in ids else None
    if (
        source is None
        or source.project_id != project_id
        or not source.approved
        or not source.scope_impact
        or source.incorporated_revision is not None
    ):
        raise InvalidDataError(validation.CHANGE_MESSAGE)
    return source


def _adjustment_weights(
    *,
    packages: Mapping[str, EapItem],
    adjustments: Sequence[validation.RevisionAdjustment],
    parameters: EapParameters,
) -> dict[str, Decimal]:
    """O peso fixo de cada ajuste, depois de conferir o pacote e os limites do parâmetro."""
    fixed: dict[str, Decimal] = {}
    for adjustment in adjustments:
        if adjustment.code not in packages:
            raise InvalidDataError(
                validation.REVISION_PACKAGE_NOT_FOUND_MESSAGE.format(code=adjustment.code)
            )
        _require_revision_weight(adjustment.weight, parameters=parameters)
        fixed[adjustment.code] = adjustment.weight
    return fixed


def _require_new_packages(
    new_packages: Sequence[validation.NewPackageData],
    *,
    items: Sequence[EapItem],
    parameters: EapParameters,
) -> None:
    """Confere cada pacote novo antes de qualquer escrita: recurso, subárea, peso e código."""
    subareas = {item.code for item in items if item.level == LEVEL_SUB_AREA}
    levels = {item.code: item.level for item in items}
    for data in new_packages:
        if data.resource != validation.REVISION:
            raise InvalidDataError({validation.FIELD_RESOURCE: validation.RESOURCE_MESSAGE})
        if data.parent_code not in subareas:
            raise InvalidDataError({validation.FIELD_PARENT: validation.PARENT_MESSAGE})
        _require_revision_weight(data.weight, parameters=parameters)
        if data.code is not None:
            problem = validation.package_code_error(data.code, levels=levels)
            if problem:
                raise InvalidDataError({validation.FIELD_CODE: problem})
            levels[data.code] = LEVEL_PACKAGE


def _require_revision_weight(weight: Decimal, *, parameters: EapParameters) -> None:
    """O peso de um pacote da revisão: maior que zero e até o máximo do parâmetro."""
    if weight <= 0:
        raise InvalidDataError({validation.FIELD_WEIGHT: validation.PACKAGE_WEIGHT_ZERO_MESSAGE})
    if weight > parameters.max_package_weight:
        raise InvalidDataError(
            {
                validation.FIELD_WEIGHT: validation.REVISION_WEIGHT_MAX_MESSAGE.format(
                    maximum=parameters.max_package_weight
                )
            }
        )


def _apply_adjustments(
    session: Session,
    *,
    user: User,
    packages: Mapping[str, EapItem],
    adjustments: Sequence[validation.RevisionAdjustment],
) -> None:
    """Ajusta o peso, a quantidade (em Unidades) e o término dos pacotes afetados."""
    for adjustment in adjustments:
        package = packages[adjustment.code]
        changes: dict[str, Any] = {"weight": adjustment.weight}
        if adjustment.quantity is not None and package.criterion == calculations.CRITERION_UNITS:
            changes["quantity"] = adjustment.quantity
        if adjustment.finish is not None:
            changes["finish"] = adjustment.finish
        recording.update(
            session,
            user_id=user.id,
            record=package,
            changes=changes,
            version=package.version,
        )


def _create_revision_packages(
    session: Session,
    *,
    user: User,
    project_id: int,
    items: Sequence[EapItem],
    known: Sequence[EapItem],
    new_packages: Sequence[validation.NewPackageData],
    reference_date: date,
) -> tuple[EapItem, ...]:
    """Cria os pacotes novos da revisão, com o código informado ou o seguinte da sua subárea."""
    subareas = {item.code: item for item in items if item.level == LEVEL_SUB_AREA}
    live = list(known)
    created: list[EapItem] = []
    for data in new_packages:
        parent = subareas.get(data.parent_code)
        if parent is None:
            raise InvalidDataError({validation.FIELD_PARENT: validation.PARENT_MESSAGE})
        code = data.code if data.code is not None else _next_package_code(live, parent)
        item = _create_eap_package(
            session,
            user=user,
            project_id=project_id,
            data=data,
            code=code,
            parent=parent,
            kind=data.kind,
            predicted=calculations.eap_linear_predicted(data.start, data.finish, reference_date),
        )
        live.append(item)
        created.append(item)
    return tuple(created)


def _create_eap_package(
    session: Session,
    *,
    user: User,
    project_id: int,
    data: validation.NewPackageData,
    code: str,
    parent: EapItem,
    kind: str,
    predicted: Decimal,
) -> EapItem:
    """O pacote novo da EAP, com as entradas iniciais do critério e as etapas do modelo a zero."""
    item = recording.create(
        session,
        user_id=user.id,
        record=EapItem(
            project_id=project_id,
            parent_id=parent.id,
            eac_item_id=_eac_item_id(session, project_id=project_id, code=data.eac_code),
            unit_id=_unit_id(session, data.unit),
            company_id=data.company_id,
            owner_id=data.owner_id,
            code=code,
            description=data.description,
            level=LEVEL_PACKAGE,
            kind=kind,
            criterion=data.criterion,
            model=data.model,
            quantity=data.quantity,
            executed=_initial_executed(data.criterion),
            state=_initial_state(data.criterion),
            estimated_pct=_initial_estimated(data.criterion),
            weight=data.weight,
            predicted=predicted,
            start=data.start,
            finish=data.finish,
            deliverable=data.deliverable,
            acceptance=data.acceptance,
        ),
    )
    for order, step in enumerate(data.steps, start=1):
        recording.create(
            session,
            user_id=user.id,
            record=EapItemStep(
                item_id=item.id,
                order=order,
                name=step.name,
                weight=step.weight,
                pct=Decimal(0),
            ),
        )
    return item


def _initial_executed(criterion: str | None) -> Decimal | None:
    return Decimal(0) if criterion == calculations.CRITERION_UNITS else None


def _initial_state(criterion: str | None) -> str | None:
    if criterion in (
        calculations.CRITERION_MILESTONE_0_100,
        calculations.CRITERION_MILESTONE_50_50,
    ):
        return calculations.MILESTONE_NOT_STARTED
    return None


def _initial_estimated(criterion: str | None) -> Decimal | None:
    return Decimal(0) if criterion == calculations.CRITERION_ESTIMATED else None


def _unit_id(session: Session, code: str) -> int | None:
    """O id da unidade de medida pelo código; recusa a unidade que não existe no cadastro."""
    if not code:
        return None
    found = next(
        (unit.id for unit in configuracoes.list_measure_units(session) if unit.code == code), None
    )
    if found is None:
        raise InvalidDataError({validation.FIELD_UNIT: validation.UNIT_MESSAGE})
    return found


def _next_package_code(known: Sequence[EapItem], parent: EapItem) -> str:
    """O código seguinte da subárea, considerando os filhos que já existem (inclusive encerrados)."""
    highest = 0
    for item in known:
        if item.parent_id != parent.id:
            continue
        suffix = item.code.rsplit(".", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{parent.code}.{highest + 1}"


def _rescale_free_weights(
    session: Session,
    *,
    user: User,
    packages: Mapping[str, EapItem],
    fixed: Mapping[str, Decimal],
) -> None:
    """Reescala os pacotes livres para a sobra, fechando os 100% com os pesos fixos."""
    free = [item for item in packages.values() if _is_free_package(item, fixed)]
    target = calculations.PERCENT - sum(fixed.values(), Decimal(0))
    weights = calculations.eap_rescale_weights(
        [(item.code, item.weight or Decimal(0)) for item in free], target
    )
    for item in free:
        recording.update(
            session,
            user_id=user.id,
            record=item,
            changes={"weight": weights[item.code]},
            version=item.version,
        )


def _is_free_package(item: EapItem, fixed: Mapping[str, Decimal]) -> bool:
    return item.code not in fixed and (item.weight or Decimal(0)) > 0


def _packages_by_code(session: Session, project_id: int) -> dict[str, EapItem]:
    """Os pacotes de nível 3 do projeto pelo código, na ordem de cadastro."""
    statement = (
        select(EapItem)
        .where(EapItem.project_id == project_id, EapItem.level == LEVEL_PACKAGE)
        .order_by(EapItem.id)
    )
    return {item.code: item for item in session.scalars(statement)}


def _next_revision(session: Session, *, project_id: int) -> int:
    """O número da revisão a gravar: 0 quando o projeto ainda não tem nenhuma."""
    latest = session.scalar(
        select(func.max(EapRevision.revision)).where(EapRevision.project_id == project_id)
    )
    return 0 if latest is None else latest + 1


def _current_revision(session: Session, *, project_id: int) -> int:
    """A revisão vigente do projeto: a maior gravada, ou 0 quando não há nenhuma."""
    latest = session.scalar(
        select(func.max(EapRevision.revision)).where(EapRevision.project_id == project_id)
    )
    return latest or 0


def _freeze_revision(session: Session, *, revision_id: int, packages: Sequence[EapItem]) -> None:
    """Congela o peso de cada pacote de nível 3 na revisão (fato histórico da D5b)."""
    session.add_all(
        EapRevisionItem(revision_id=revision_id, item_id=item.id, weight=item.weight or Decimal(0))
        for item in packages
    )
    session.flush()


def _alteration(new_codes: Sequence[str], adjusted_codes: Sequence[str]) -> str:
    """A alteração da revisão no formato do protótipo: o que entrou, o que mudou e o reescalado."""
    parts: list[str] = []
    if new_codes:
        parts.append(_listed("Pacote", "Pacotes", new_codes, "incluído", "incluídos"))
    if adjusted_codes:
        parts.append(_listed("Pacote", "Pacotes", adjusted_codes, "ajustado", "ajustados"))
    parts.append("demais pesos reescalados")
    return "; ".join(parts)


def _listed(singular: str, plural: str, codes: Sequence[str], one: str, many: str) -> str:
    return f"{singular if len(codes) == 1 else plural} {', '.join(codes)} {one if len(codes) == 1 else many}"


def _plain_weight(value: Decimal | None) -> str:
    """O peso sem zeros à direita: ``3.00`` vira ``3`` e ``2.50`` vira ``2.5``."""
    text = format(value or Decimal(0), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


# ── Apoio da árvore ───────────────────────────────────────────────────────


def _scope_projects(
    scope: Scope, projects: Sequence[configuracoes.ProjectSummary]
) -> tuple[configuracoes.ProjectSummary, ...]:
    if scope.is_portfolio:
        return tuple(projects)
    project = next((item for item in projects if item.id == scope.project_id), None)
    if project is None:
        raise InvalidDataError(EAP_PROJECT_NOT_FOUND_MESSAGE)
    return (project,)


def _items_by_project(
    session: Session, project_ids: Sequence[int]
) -> dict[int, tuple[EapItem, ...]]:
    if not project_ids:
        return {}
    statement = select(EapItem).where(EapItem.project_id.in_(project_ids)).order_by(EapItem.id)
    grouped: dict[int, list[EapItem]] = {}
    for item in session.scalars(statement):
        grouped.setdefault(item.project_id, []).append(item)
    return {project_id: tuple(group) for project_id, group in grouped.items()}


def _lookups(session: Session, items: Sequence[EapItem]) -> _Lookups:
    from src.modulos.financeiro import service as financeiro

    eac_ids = sorted({item.eac_item_id for item in items if item.eac_item_id is not None})
    return _Lookups(
        companies={item.id: item.name for item in configuracoes.list_company_options(session)},
        people={item.id: item.name for item in configuracoes.list_person_options(session)},
        units={item.id: item.code for item in configuracoes.list_measure_units(session)},
        eac_codes=financeiro.eac_item_codes(session, eac_ids),
    )


def _children_by_parent(
    items: Sequence[EapItem],
) -> dict[int | None, tuple[EapItem, ...]]:
    grouped: dict[int | None, list[EapItem]] = {}
    for item in items:
        grouped.setdefault(item.parent_id, []).append(item)
    return {
        parent_id: tuple(sorted(group, key=lambda item: _code_key(item.code)))
        for parent_id, group in grouped.items()
    }


def _steps_by_item(session: Session, item_ids: Sequence[int]) -> dict[int, tuple[EapItemStep, ...]]:
    if not item_ids:
        return {}
    statement = (
        select(EapItemStep)
        .where(EapItemStep.item_id.in_(item_ids))
        .order_by(EapItemStep.item_id, EapItemStep.order, EapItemStep.id)
    )
    grouped: dict[int, list[EapItemStep]] = {}
    for step in session.scalars(statement):
        grouped.setdefault(step.item_id, []).append(step)
    return {item_id: tuple(group) for item_id, group in grouped.items()}


def _measurements_by_item(
    session: Session, item_ids: Sequence[int], lookups: _Lookups
) -> dict[int, tuple[EapMeasurementView, ...]]:
    if not item_ids:
        return {}
    statement = (
        select(EapMeasurement)
        .where(EapMeasurement.item_id.in_(item_ids))
        .order_by(EapMeasurement.item_id, EapMeasurement.measured_on, EapMeasurement.id)
    )
    grouped: dict[int, list[EapMeasurementView]] = {}
    for record in session.scalars(statement):
        grouped.setdefault(record.item_id, []).append(
            EapMeasurementView(
                id=record.id,
                measured_on=record.measured_on,
                from_pct=record.from_pct,
                to_pct=record.to_pct,
                author=lookups.person(record.author_id),
                note=record.note or "",
            )
        )
    return {item_id: tuple(group) for item_id, group in grouped.items()}


def _area_nodes(snapshot: _ProjectSnapshot) -> tuple[EapNode, ...]:
    return tuple(node for node in snapshot.nodes if node.level == LEVEL_AREA)


def _used_changes(revisions: Sequence[EapRevisionView]) -> frozenset[int]:
    return frozenset(view.change_id for view in revisions if view.change_id is not None)


def _totals_of(node: EapNode) -> calculations.EapTotals:
    return calculations.EapTotals(
        weight=node.weight,
        predicted=node.predicted,
        actual=node.actual,
        start=node.start,
        finish=node.finish,
        packages=node.packages,
        planning=node.planning,
        overdue=node.overdue,
        not_started=node.not_started,
    )


def _share_of(value: Decimal, base: Decimal | None) -> Decimal | None:
    """The share of the value in the base, in %, with one place; ``None`` without a base."""
    if base is None or base == 0:
        return None
    return (value / base * calculations.PERCENT).quantize(
        calculations.ONE_PLACE, rounding=ROUND_HALF_UP
    )


def _weight_of(nodes: Sequence[EapNode]) -> Decimal:
    total = sum((node.weight for node in nodes), Decimal(0))
    return total.quantize(calculations.TWO_PLACES, rounding=ROUND_HALF_UP)


def _code_key(code: str) -> tuple[int, ...]:
    return tuple(int(part) for part in code.split(".") if part.isdigit())


def _project_label(project: configuracoes.ProjectSummary) -> str:
    return f"{project.code} · {project.name}"


# ── Curva S física (ISSUE-039) ────────────────────────────────────────────

CURVA_FISICA_PROJECT_NOT_FOUND_MESSAGE = "O projeto da Curva S não existe."


@dataclass(frozen=True)
class CurvaFisicaIndicators:
    """Os indicadores da Curva S na data de referência, com o mês anterior ao lado."""

    cut_month: date | None
    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    previous_predicted: Decimal | None
    previous_actual: Decimal | None
    previous_spi: Decimal | None
    trend_finish: date | None
    baseline_finish: date | None


@dataclass(frozen=True)
class CurvaFisicaPoint:
    """Um mês da tabela período a período: o acumulado, o incremento do mês e o desvio."""

    month: date
    month_predicted: Decimal
    predicted: Decimal
    month_actual: Decimal | None
    actual: Decimal | None
    trend: Decimal | None
    deviation_pp: Decimal | None
    is_cut: bool


@dataclass(frozen=True)
class CurvaFisicaComposition:
    """A linha de um projeto na composição da carteira, no corte da própria curva."""

    project_id: int
    project_label: str
    weight: Decimal
    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    contribution_pp: Decimal
    trend_finish: date | None
    baseline_finish: date | None


@dataclass(frozen=True)
class CurvaFisicaOverview:
    """A Curva S física do escopo: as séries, os indicadores, a tabela e o gráfico (D11)."""

    reference_date: date
    is_portfolio: bool
    scope_label: str
    project_id: int | None
    revision: int | None
    revision_date: date | None
    series: calculations.CurvaFisicaSeries
    indicators: CurvaFisicaIndicators
    points: tuple[CurvaFisicaPoint, ...]
    composition: tuple[CurvaFisicaComposition, ...]
    chart: Mapping[str, Any]

    @property
    def is_empty(self) -> bool:
        """Whether there is no frozen curve in the scope: the screen shows the empty state."""
        return not self.series.months


@dataclass(frozen=True)
class _CurveRecord:
    """A curva congelada de uma revisão como o banco a guarda: o calendário e a baseline."""

    eap_revision_id: int
    revision: int
    revision_date: date
    months: tuple[date, ...]
    baseline: tuple[Decimal, ...]


@dataclass(frozen=True)
class _FrozenCurve:
    """A curva de um projeto pronta: a revisão, os pacotes congelados e as três séries."""

    project_id: int
    revision: int
    revision_date: date
    packages: tuple[calculations.CurvaFisicaPackage, ...]
    series: calculations.CurvaFisicaSeries


def freeze_curve(
    session: Session, *, project_id: int, revision_id: int, reference_date: date
) -> None:
    """Congela a linha de base da Curva S física na revisão da EAP (D5b, HU-025).

    Os pacotes de nível 3 saem dos pesos congelados da revisão (``eap_revisao_item``) com as
    datas do item; o calendário e o previsto de cada mês vêm dos cálculos da curva. A revisão
    da curva e os seus meses entram na transação do chamador — é o gancho do ``create_revision``.
    """
    packages = _frozen_packages(session, (revision_id,)).get(revision_id, ())
    calendar = calculations.curva_fisica_months(packages, reference_date)
    baseline = calculations.curva_fisica_baseline(packages, calendar.months, reference_date)
    record = CurvaFisicaRevision(
        project_id=project_id,
        eap_revision_id=revision_id,
        generated_at=calendario.now(),
    )
    session.add(record)
    session.flush()
    session.add_all(
        CurvaFisicaMonth(revision_id=record.id, month=month, baseline_pct=pct)
        for month, pct in zip(calendar.months, baseline, strict=True)
    )
    session.flush()


def linear_curve_profile(
    session: Session, *, project_id: int, reference_date: date
) -> tuple[tuple[date, ...], tuple[Decimal, ...]] | None:
    """O perfil linear da curva a partir das datas e dos pesos correntes dos pacotes de nível 3.

    É a distribuição que o ``freeze_curve`` daria a uma revisão nova feita agora: os pacotes com
    peso e as duas datas entram no calendário e no previsto linear de cada mês. Serve de perfil ao
    congelamento da Curva S financeira de um projeto sem curva física congelada (ISSUE-042); sem
    pacote com peso e as duas datas, não há perfil.
    """
    items = session.scalars(
        select(EapItem).where(EapItem.project_id == project_id, EapItem.level == LEVEL_PACKAGE)
    ).all()
    packages = tuple(
        calculations.CurvaFisicaPackage(weight=item.weight, start=item.start, finish=item.finish)
        for item in items
        if item.weight is not None and item.weight > calculations.ZERO
    )
    calendar = calculations.curva_fisica_months(packages, reference_date)
    if not calendar.months:
        return None
    baseline = calculations.curva_fisica_baseline(packages, calendar.months, reference_date)
    return calendar.months, baseline


def curva_fisica_overview(
    session: Session, *, scope: Scope, reference_date: date
) -> CurvaFisicaOverview:
    """A Curva S física do escopo: baseline congelada, real das medições e tendência (D5b, D6).

    No projeto vale a curva da revisão vigente da EAP; sem revisão ou sem congelamento a visão
    sai vazia. No Portfólio a curva é a média ponderada das curvas dos projetos pelos pesos da
    carteira, no calendário da união dos meses (D8), e cada projeto entra na composição com o
    seu próprio corte. O gráfico sai em semanas ISO, no contrato da biblioteca do DS (D11).
    """
    projects = _curve_scope_projects(scope, configuracoes.list_projects(session))
    records = _current_curve_records(session, [project.id for project in projects])
    if scope.is_portfolio:
        return _portfolio_curve_overview(
            session, projects=projects, records=records, reference_date=reference_date
        )
    project = projects[0]
    record = records.get(project.id)
    if record is None:
        return _empty_curve_overview(
            reference_date=reference_date, is_portfolio=False, scope_label=_project_label(project)
        )
    curve = _frozen_curves(session, {project.id: record}, reference_date)[project.id]
    return CurvaFisicaOverview(
        reference_date=reference_date,
        is_portfolio=False,
        scope_label=_project_label(project),
        project_id=project.id,
        revision=curve.revision,
        revision_date=curve.revision_date,
        series=curve.series,
        indicators=_curve_indicators(curve.series),
        points=_curve_points(curve.series),
        composition=(),
        chart=_curve_chart(
            curve.series,
            is_portfolio=False,
            reference_date=reference_date,
            real_on=lambda day: _packages_real_on(curve.packages, day),
        ),
    )


def _portfolio_curve_overview(
    session: Session,
    *,
    projects: Sequence[configuracoes.ProjectSummary],
    records: Mapping[int, _CurveRecord],
    reference_date: date,
) -> CurvaFisicaOverview:
    """A Curva S física da carteira, ponderada pelos pesos dos projetos (D8)."""
    from src.modulos.financeiro import service as financeiro

    curves = {
        project_id: curve
        for project_id, curve in _frozen_curves(session, records, reference_date).items()
        if curve.series.months
    }
    if not curves:
        return _empty_curve_overview(
            reference_date=reference_date, is_portfolio=True, scope_label=PORTFOLIO_LABEL
        )
    labels = {project.id: _project_label(project) for project in projects}
    weights = financeiro.portfolio_weights(session, reference_date=reference_date)
    weight_of = {
        project_id: weights[project_id].weight if project_id in weights else calculations.ZERO
        for project_id in curves
    }
    months = _month_range(
        min(curve.series.months[0] for curve in curves.values()),
        max(curve.series.months[-1] for curve in curves.values()),
    )
    series = calculations.curva_fisica_portfolio(
        {project_id: curve.series for project_id, curve in curves.items()}, weight_of, months
    )
    divisor = sum(weight_of.values(), calculations.ZERO) or Decimal(1)
    frozen = tuple(curves.values())
    return CurvaFisicaOverview(
        reference_date=reference_date,
        is_portfolio=True,
        scope_label=PORTFOLIO_LABEL,
        project_id=None,
        revision=None,
        revision_date=None,
        series=series,
        indicators=_curve_indicators(series),
        points=_curve_points(series),
        composition=tuple(
            _curve_composition(labels[project_id], curves[project_id], weight_of[project_id])
            for project_id in curves
        ),
        chart=_curve_chart(
            series,
            is_portfolio=True,
            reference_date=reference_date,
            real_on=lambda day: _portfolio_real_on(frozen, weight_of, divisor, day),
        ),
    )


def _curve_composition(label: str, curve: _FrozenCurve, weight: Decimal) -> CurvaFisicaComposition:
    indicators = _curve_indicators(curve.series)
    return CurvaFisicaComposition(
        project_id=curve.project_id,
        project_label=label,
        weight=weight,
        predicted=indicators.predicted,
        actual=indicators.actual,
        deviation_pp=indicators.deviation_pp,
        spi=indicators.spi,
        contribution_pp=_round_two(weight * indicators.deviation_pp / calculations.PERCENT),
        trend_finish=indicators.trend_finish,
        baseline_finish=indicators.baseline_finish,
    )


def _curve_scope_projects(
    scope: Scope, projects: Sequence[configuracoes.ProjectSummary]
) -> tuple[configuracoes.ProjectSummary, ...]:
    if scope.is_portfolio:
        return tuple(projects)
    project = next((item for item in projects if item.id == scope.project_id), None)
    if project is None:
        raise InvalidDataError(CURVA_FISICA_PROJECT_NOT_FOUND_MESSAGE)
    return (project,)


def _empty_curve_overview(
    *, reference_date: date, is_portfolio: bool, scope_label: str
) -> CurvaFisicaOverview:
    empty = calculations.CurvaFisicaSeries(months=(), cut_index=-1, baseline=(), real=(), trend=())
    return CurvaFisicaOverview(
        reference_date=reference_date,
        is_portfolio=is_portfolio,
        scope_label=scope_label,
        project_id=None,
        revision=None,
        revision_date=None,
        series=empty,
        indicators=_curve_indicators(empty),
        points=(),
        composition=(),
        chart=_curve_chart(empty, is_portfolio=is_portfolio, reference_date=reference_date),
    )


def _current_curve_records(session: Session, project_ids: Sequence[int]) -> dict[int, _CurveRecord]:
    """A curva congelada vigente de cada projeto: a da maior revisão da EAP."""
    if not project_ids:
        return {}
    curves = session.scalars(
        select(CurvaFisicaRevision).where(CurvaFisicaRevision.project_id.in_(project_ids))
    ).all()
    if not curves:
        return {}
    revisions = {
        revision.id: revision
        for revision in session.scalars(
            select(EapRevision).where(
                EapRevision.id.in_({curve.eap_revision_id for curve in curves})
            )
        )
    }
    latest: dict[int, CurvaFisicaRevision] = {}
    for curve in curves:
        revision = revisions.get(curve.eap_revision_id)
        if revision is None:
            continue
        current = latest.get(curve.project_id)
        if current is None or revision.revision > revisions[current.eap_revision_id].revision:
            latest[curve.project_id] = curve
    months: dict[int, list[CurvaFisicaMonth]] = {}
    for row in session.scalars(
        select(CurvaFisicaMonth)
        .where(CurvaFisicaMonth.revision_id.in_({curve.id for curve in latest.values()}))
        .order_by(CurvaFisicaMonth.revision_id, CurvaFisicaMonth.month)
    ):
        months.setdefault(row.revision_id, []).append(row)
    records: dict[int, _CurveRecord] = {}
    for project_id, curve in latest.items():
        revision = revisions[curve.eap_revision_id]
        rows = months.get(curve.id, [])
        records[project_id] = _CurveRecord(
            eap_revision_id=curve.eap_revision_id,
            revision=revision.revision,
            revision_date=revision.revision_date,
            months=tuple(row.month for row in rows),
            baseline=tuple(row.baseline_pct for row in rows),
        )
    return records


def _frozen_packages(
    session: Session, revision_ids: Sequence[int]
) -> dict[int, tuple[calculations.CurvaFisicaPackage, ...]]:
    """Os pacotes congelados de cada revisão da EAP, cada um com as medições datadas do item."""
    if not revision_ids:
        return {}
    frozen = session.scalars(
        select(EapRevisionItem)
        .where(EapRevisionItem.revision_id.in_(revision_ids))
        .order_by(EapRevisionItem.revision_id, EapRevisionItem.item_id)
    ).all()
    item_ids = sorted({row.item_id for row in frozen})
    if not item_ids:
        return {}
    items = {
        item.id: item for item in session.scalars(select(EapItem).where(EapItem.id.in_(item_ids)))
    }
    measurements: dict[int, list[calculations.CurvaFisicaMeasurement]] = {}
    for record in session.scalars(
        select(EapMeasurement)
        .where(EapMeasurement.item_id.in_(item_ids))
        .order_by(EapMeasurement.item_id, EapMeasurement.measured_on, EapMeasurement.id)
    ):
        measurements.setdefault(record.item_id, []).append(
            calculations.CurvaFisicaMeasurement(
                measured_on=record.measured_on, to_pct=record.to_pct
            )
        )
    grouped: dict[int, list[calculations.CurvaFisicaPackage]] = {}
    for row in frozen:
        item = items.get(row.item_id)
        if item is None:
            continue
        grouped.setdefault(row.revision_id, []).append(
            calculations.CurvaFisicaPackage(
                weight=row.weight,
                start=item.start,
                finish=item.finish,
                measurements=tuple(measurements.get(row.item_id, ())),
            )
        )
    return {revision_id: tuple(group) for revision_id, group in grouped.items()}


def _frozen_curves(
    session: Session, records: Mapping[int, _CurveRecord], reference_date: date
) -> dict[int, _FrozenCurve]:
    packages = _frozen_packages(
        session, tuple(record.eap_revision_id for record in records.values())
    )
    curves: dict[int, _FrozenCurve] = {}
    for project_id, record in records.items():
        frozen = packages.get(record.eap_revision_id, ())
        real = calculations.curva_fisica_real(frozen, record.months, reference_date)
        cut = _last_real_index(real)
        curves[project_id] = _FrozenCurve(
            project_id=project_id,
            revision=record.revision,
            revision_date=record.revision_date,
            packages=frozen,
            series=calculations.CurvaFisicaSeries(
                months=record.months,
                cut_index=cut,
                baseline=record.baseline,
                real=real,
                trend=calculations.curva_fisica_trend(record.baseline, real, cut),
            ),
        )
    return curves


def _curve_indicators(series: calculations.CurvaFisicaSeries) -> CurvaFisicaIndicators:
    cut = series.cut_index
    if cut < 0:
        return CurvaFisicaIndicators(
            cut_month=None,
            predicted=calculations.ZERO,
            actual=calculations.ZERO,
            deviation_pp=calculations.ZERO,
            spi=None,
            previous_predicted=None,
            previous_actual=None,
            previous_spi=None,
            trend_finish=None,
            baseline_finish=None,
        )
    predicted = series.baseline[cut]
    actual = series.real[cut] or calculations.ZERO
    previous_predicted = series.baseline[cut - 1] if cut > 0 else None
    previous_actual = series.real[cut - 1] if cut > 0 else None
    return CurvaFisicaIndicators(
        cut_month=series.months[cut],
        predicted=predicted,
        actual=actual,
        deviation_pp=_round_one(actual - predicted),
        spi=calculations.spi_index(actual, predicted),
        previous_predicted=previous_predicted,
        previous_actual=previous_actual,
        previous_spi=(
            None
            if previous_predicted is None
            else calculations.spi_index(previous_actual or calculations.ZERO, previous_predicted)
        ),
        trend_finish=_first_month(series.months, series.trend),
        baseline_finish=_first_month(series.months, series.baseline),
    )


def _first_month(months: Sequence[date], values: Sequence[Decimal | None]) -> date | None:
    """O primeiro mês em que a série chega a 100%; sem chegar, não há término."""
    return next(
        (
            month
            for month, value in zip(months, values, strict=True)
            if value is not None and value >= calculations.PERCENT
        ),
        None,
    )


def _curve_points(series: calculations.CurvaFisicaSeries) -> tuple[CurvaFisicaPoint, ...]:
    points: list[CurvaFisicaPoint] = []
    for index, month in enumerate(series.months):
        predicted = series.baseline[index]
        actual = series.real[index]
        previous_predicted = series.baseline[index - 1] if index > 0 else calculations.ZERO
        previous_actual = series.real[index - 1] if index > 0 else None
        points.append(
            CurvaFisicaPoint(
                month=month,
                month_predicted=_round_one(predicted - previous_predicted),
                predicted=predicted,
                month_actual=(
                    None
                    if actual is None
                    else _round_one(actual - (previous_actual or calculations.ZERO))
                ),
                actual=actual,
                trend=series.trend[index],
                deviation_pp=None if actual is None else _round_one(actual - predicted),
                is_cut=index == series.cut_index,
            )
        )
    return tuple(points)


def _month_range(first: date, last: date) -> tuple[date, ...]:
    months: list[date] = []
    current = first
    while current <= last:
        months.append(current)
        current = (
            date(current.year + 1, 1, 1)
            if current.month == calculations.MONTHS_IN_YEAR
            else date(current.year, current.month + 1, 1)
        )
    return tuple(months)


def _month_last(month: date) -> date:
    return month.replace(day=monthrange(month.year, month.month)[1])


def _month_weeks(months: Sequence[date]) -> tuple[date, ...]:
    """As segundas-feiras das semanas ISO que cobrem os meses da curva."""
    current = months[0] - timedelta(days=months[0].weekday())
    last = _month_last(months[-1])
    weeks: list[date] = []
    while current <= last:
        weeks.append(current)
        current += timedelta(days=7)
    return tuple(weeks)


def _last_real_index(values: Sequence[Decimal | None]) -> int:
    """O índice da última semana ou mês com real; -1 quando nenhum tem."""
    for index in range(len(values) - 1, -1, -1):
        if values[index] is not None:
            return index
    return -1


def _interpolated(months: Sequence[date], values: Sequence[Decimal], day: date) -> Decimal:
    """O acumulado de um dia: interpolação linear dentro do mês, com 1 casa.

    O mês congelado vale no fim do mês civil; antes do primeiro mês a curva vale zero e depois
    do último fica no último valor. É a regra do relatório para a semana no meio do mês.
    """
    if day < months[0]:
        return calculations.ZERO
    if day > _month_last(months[-1]):
        return values[-1]
    for index, month in enumerate(months):
        last = _month_last(month)
        if day > last:
            continue
        previous = values[index - 1] if index > 0 else calculations.ZERO
        elapsed = Decimal((day - month).days)
        span = Decimal((last - month).days)
        value = previous + (values[index] - previous) * elapsed / span
        return value.quantize(calculations.ONE_PLACE, rounding=ROUND_HALF_UP)
    return values[-1]


def _packages_real_on(packages: Sequence[calculations.CurvaFisicaPackage], day: date) -> Decimal:
    """O real acumulado dos pacotes numa data: a soma ponderada da última medição até ela."""
    value = calculations.curva_fisica_real(packages, (day.replace(day=1),), day)[0]
    return value if value is not None else calculations.ZERO


def _portfolio_real_on(
    curves: Sequence[_FrozenCurve],
    weights: Mapping[int, Decimal],
    divisor: Decimal,
    day: date,
) -> Decimal:
    """O real da carteira numa data: a média ponderada dos reais dos projetos com curva."""
    total = sum(
        (
            weights.get(curve.project_id, calculations.ZERO)
            * _packages_real_on(curve.packages, day)
            for curve in curves
        ),
        calculations.ZERO,
    )
    return _round_one(total / divisor)


def _curve_chart(
    series: calculations.CurvaFisicaSeries,
    *,
    is_portfolio: bool,
    reference_date: date,
    real_on: Callable[[date], Decimal] | None = None,
) -> dict[str, Any]:
    """O ``data-dados`` da Curva S Linha (D11): semanas ISO, acumulado e sem real depois do corte.

    O baseline e a tendência saem da interpolação linear dentro do mês congelado; o real é a
    última medição até o fim da semana, limitado à referência; as semanas depois da referência
    ficam sem real. A tendência arranca no real da semana do corte, como no mês.
    """
    weeks = _month_weeks(series.months) if series.months else ()
    baseline: list[Decimal] = []
    realized: list[Decimal | None] = []
    for week in weeks:
        end = week + timedelta(days=6)
        baseline.append(_interpolated(series.months, series.baseline, end))
        as_of = min(end, reference_date)
        realized.append(None if week > reference_date or real_on is None else real_on(as_of))
    trend = calculations.curva_fisica_trend(baseline, realized, _last_real_index(realized))
    periods: list[dict[str, Any]] = []
    for index, week in enumerate(weeks):
        year, number, _ = week.isocalendar()
        actual = realized[index]
        tendency = trend[index]
        periods.append(
            {
                "ano": year,
                "mes": (week + timedelta(days=3)).month,
                "semana": number,
                "valores": {
                    "linha_base": float(baseline[index]),
                    "realizado": None if actual is None else float(actual),
                    "tendencia": None if tendency is None else float(tendency),
                },
            }
        )
    return {
        "titulo": "Curva S física da carteira" if is_portfolio else "Curva S física",
        "modo": "acumulado",
        "formato": "pct",
        "casas": 1,
        "casas_dica": 1,
        "series": [
            {"id": "linha_base", "rotulo": "Linha de Base", "papel": "linha-base"},
            {"id": "realizado", "rotulo": "Realizado", "papel": "realizado"},
            {"id": "tendencia", "rotulo": "Tendência", "papel": "tendencia"},
        ],
        "periodos": periods,
    }


def _round_one(value: Decimal) -> Decimal:
    return value.quantize(calculations.ONE_PLACE, rounding=ROUND_HALF_UP)


def _round_two(value: Decimal) -> Decimal:
    return value.quantize(calculations.TWO_PLACES, rounding=ROUND_HALF_UP)


# ── KPIs de planejamento (ISSUE-040) ──────────────────────────────────────


@dataclass(frozen=True)
class PlanningKpiLine:
    """Uma linha do avanço: a área da EAP (peso, previsto, real, desvio, SPI, contribuição, faixa)."""

    id: int | None
    project_id: int | None
    code: str
    name: str
    weight: Decimal
    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    contribution_pp: Decimal
    band: str | None


@dataclass(frozen=True)
class PlanningKpisOverview:
    """Os KPIs de planejamento do escopo: a curva, o SPI por mês e as linhas de avanço (D6, D11)."""

    reference_date: date
    scope_label: str
    curve: CurvaFisicaOverview
    spi_series: tuple[Decimal | None, ...]
    rows: tuple[PlanningKpiLine, ...]
    worst: PlanningKpiLine | None
    overdue_packages: int
    pending_changes: int
    bands: tuple[Decimal, Decimal]
    spi_chart: Mapping[str, Any]
    comparison_chart: Mapping[str, Any]

    @property
    def is_empty(self) -> bool:
        """Whether the scope has no frozen curve: the screen shows the empty state."""
        return self.curve.is_empty

    @property
    def is_portfolio(self) -> bool:
        """Whether the view is the portfolio: the rows are the projects, not the areas."""
        return self.curve.is_portfolio

    @property
    def project_id(self) -> int | None:
        """O projeto do escopo; ``None`` no Portfólio."""
        return self.curve.project_id

    @property
    def indicators(self) -> CurvaFisicaIndicators:
        """Os indicadores da curva: SPI, previsto, real, desvio, mês anterior e términos."""
        return self.curve.indicators


@dataclass(frozen=True)
class _KpiEap:
    """A leitura da EAP que os KPIs usam: os projetos, a árvore de cada um e as faixas de desvio."""

    projects: tuple[configuracoes.ProjectSummary, ...]
    snapshots: Mapping[int, _ProjectSnapshot]
    bands: tuple[Decimal, Decimal]

    @property
    def overdue(self) -> int:
        """Quantos pacotes de trabalho já passaram do término sem concluir."""
        return sum(snapshot.indicators.overdue for snapshot in self.snapshots.values())


def planning_kpis_overview(
    session: Session, *, scope: Scope, reference_date: date
) -> PlanningKpisOverview:
    """Os KPIs de planejamento do escopo: SPI, avanço por área (ou projeto) e atenção (D6).

    A curva é a da ISSUE-039 — a revisão vigente no projeto, a média ponderada da carteira no
    Portfólio — e o SPI por mês sai dela. As linhas por área são o nível 1 da árvore da EAP,
    lido como ``eap_overview`` o lê, com o real medido pelos pacotes; no Portfólio as linhas
    são os projetos da composição, com o peso da carteira. Os indicadores de atenção da EAP
    (pacotes vencidos e SMs a incorporar) saem da mesma leitura. Sem curva a visão sai vazia.
    Nada aqui lê o relógio (D6).
    """
    curve = curva_fisica_overview(session, scope=scope, reference_date=reference_date)
    spi = calculations.spi_series(curve.series.baseline, curve.series.real)
    eap = _kpi_eap(session, scope=scope, reference_date=reference_date)
    rows, worst = _kpi_rows(curve=curve, eap=eap)
    return PlanningKpisOverview(
        reference_date=reference_date,
        scope_label=curve.scope_label,
        curve=curve,
        spi_series=spi,
        rows=rows,
        worst=worst,
        overdue_packages=eap.overdue,
        pending_changes=_pending_change_count(session, eap=eap, is_portfolio=scope.is_portfolio),
        bands=eap.bands,
        spi_chart=_spi_chart(curve.series, spi),
        comparison_chart=_comparison_chart(rows, is_portfolio=scope.is_portfolio),
    )


def _kpi_rows(
    *, curve: CurvaFisicaOverview, eap: _KpiEap
) -> tuple[tuple[PlanningKpiLine, ...], PlanningKpiLine | None]:
    """As linhas de avanço — as áreas do projeto ou os projetos da carteira — e o pior desvio."""
    if curve.is_empty:
        return (), None
    if curve.is_portfolio:
        rows = _portfolio_kpi_rows(curve, eap=eap)
    else:
        rows = _area_kpi_rows(curve.project_id, eap=eap)
    return rows, _worst_row(rows)


def _area_kpi_rows(project_id: int | None, *, eap: _KpiEap) -> tuple[PlanningKpiLine, ...]:
    """As áreas de nível 1 da EAP do projeto, como a média ponderada que fecha com a curva."""
    if project_id is None:
        return ()
    snapshot = eap.snapshots.get(project_id)
    if snapshot is None:
        return ()
    return tuple(_area_kpi_row(node) for node in _area_nodes(snapshot))


def _area_kpi_row(node: EapNode) -> PlanningKpiLine:
    return PlanningKpiLine(
        id=node.id,
        project_id=node.project_id,
        code=node.code,
        name=node.description,
        weight=node.weight,
        predicted=node.predicted,
        actual=node.actual,
        deviation_pp=node.deviation_pp,
        spi=calculations.spi_index(node.actual, node.predicted),
        contribution_pp=calculations.area_contribution(node.weight, node.actual),
        band=node.band,
    )


def _portfolio_kpi_rows(curve: CurvaFisicaOverview, *, eap: _KpiEap) -> tuple[PlanningKpiLine, ...]:
    """Os projetos da composição da carteira: peso na carteira, avanço, SPI e contribuição."""
    projects = {project.id: project for project in eap.projects}
    rows: list[PlanningKpiLine] = []
    for item in curve.composition:
        project = projects.get(item.project_id)
        if project is None:
            continue
        rows.append(
            PlanningKpiLine(
                id=item.project_id,
                project_id=item.project_id,
                code=project.code,
                name=project.name,
                weight=item.weight,
                predicted=item.predicted,
                actual=item.actual,
                deviation_pp=item.deviation_pp,
                spi=item.spi,
                contribution_pp=calculations.area_contribution(item.weight, item.actual),
                band=calculations.eap_deviation_band(item.deviation_pp, eap.bands),
            )
        )
    return tuple(rows)


def _worst_row(rows: Sequence[PlanningKpiLine]) -> PlanningKpiLine | None:
    """A linha de pior desvio entre as que têm previsto: onde o atraso pesa mais."""
    candidates = [row for row in rows if row.predicted > 0]
    if not candidates:
        return None
    return min(candidates, key=lambda row: row.deviation_pp)


def _kpi_eap(session: Session, *, scope: Scope, reference_date: date) -> _KpiEap:
    """A árvore de cada projeto do escopo como ``eap_overview`` a lê, e as faixas de desvio.

    Os KPIs só precisam das áreas de nível 1 e dos vencidos: a leitura chama
    ``_project_snapshot`` direto, sem montar as linhas, os desdobramentos e as SMs da tela.
    """
    projects = _scope_projects(scope, configuracoes.list_projects(session))
    items_by_project = _items_by_project(session, [project.id for project in projects])
    parameters = _parameters(session, reference_date=reference_date)
    reading = _Reading(
        session=session,
        parameters=parameters,
        reference_date=reference_date,
        lookups=_lookups(
            session, items=[item for group in items_by_project.values() for item in group]
        ),
    )
    snapshots = {
        project.id: _project_snapshot(reading, project, items_by_project[project.id])
        for project in projects
        if items_by_project.get(project.id)
    }
    return _KpiEap(projects=projects, snapshots=snapshots, bands=parameters.deviation_bands)


def _pending_change_count(session: Session, *, eap: _KpiEap, is_portfolio: bool) -> int:
    """As SMs aprovadas com impacto em escopo que nenhuma revisão da EAP incorporou.

    A lista é a mesma da revisão (``eap_revision_sources``); no Portfólio ela só olha os
    projetos com EAP, como o ``eap_overview`` faz com as suas linhas.
    """
    from src.modulos.governanca import service as governanca

    projects = (
        [project for project in eap.projects if project.id in eap.snapshots]
        if is_portfolio
        else list(eap.projects)
    )
    return sum(
        len(governanca.eap_revision_sources(session, project_id=project.id)) for project in projects
    )


_KPI_BAND_PAPEIS = {
    calculations.SUCCESS_BAND: "ok",
    calculations.WARNING_BAND: "alerta",
    calculations.DANGER_BAND: "erro",
}


def _spi_chart(
    series: calculations.CurvaFisicaSeries, spi: Sequence[Decimal | None]
) -> dict[str, Any]:
    """O ``data-dados`` do SPI por mês (linhas-multiplas): o índice e a meta 1,00.

    Só os meses até o corte entram: depois dele não há real e não há índice. O eixo se
    ajusta ao dado (``base_zero`` falso), como a biblioteca recomenda para índices.
    """
    periodos = [
        {
            "ano": month.year,
            "mes": month.month,
            "valores": {"spi": None if value is None else float(value)},
        }
        for month, value in zip(series.months[: len(spi)], spi, strict=True)
    ]
    return {
        "titulo": "SPI por mês",
        "base_zero": False,
        "casas": 2,
        "unidade": "",
        "series": [{"id": "spi", "rotulo": "SPI", "papel": "realizado"}],
        "referencias": [{"valor": 1, "rotulo": "Meta (1,00)", "papel": "linha-base"}],
        "periodos": periodos,
    }


def _comparison_chart(rows: Sequence[PlanningKpiLine], *, is_portfolio: bool) -> dict[str, Any]:
    """O ``data-dados`` do previsto x real por área ou projeto (comparativo-barras).

    Cada categoria — a área ou o projeto — é um segmento das duas barras, o previsto e o
    real, com a variação de cada uma abaixo, colorida pelo sentido bom (subir é bom).
    """
    titulo = "Previsto x real por projeto" if is_portfolio else "Previsto x real por área"
    paineis: list[dict[str, Any]] = []
    if rows:
        paineis.append(
            {
                "titulo": "Avanço por projeto" if is_portfolio else "Avanço por área",
                "categorias": [
                    {
                        "id": row.code,
                        "rotulo": row.code if is_portfolio else row.name,
                        "papel": _KPI_BAND_PAPEIS.get(row.band or "", "neutro"),
                        "favoravel": "sobe",
                    }
                    for row in rows
                ],
                "linhas": [
                    {
                        "rotulo": "Previsto",
                        "valores": {row.code: float(row.predicted) for row in rows},
                    },
                    {
                        "rotulo": "Real",
                        "valores": {row.code: float(row.actual) for row in rows},
                    },
                ],
            }
        )
    return {"titulo": titulo, "paineis": paineis}


# ── Horas efetivas: jornada, amostragem e paralisações (ISSUE-047) ─────────


FIELD_DAY_NOT_FOUND_MESSAGE = "O registro de jornada não foi encontrado."


SAMPLE_NOT_FOUND_MESSAGE = "A rodada de amostragem não foi encontrada."


STOPPAGE_NOT_FOUND_MESSAGE = "O registro de paralisação não foi encontrado."


FIELD_PROJECT_MESSAGE = "O registro pertence a outro projeto: abra a tela no projeto dele."


FIELD_DAY_DUPLICATE_MESSAGE = (
    "Já existe registro desta frente (empresa, área e encarregado) nesta data. "
    "Edite o registro existente."
)


# As faixas do atraso de início em minutos, quando o parâmetro não traz as dele.
DEFAULT_DELAY_BANDS = (Decimal("15"), Decimal("30"))


PERIOD_WEEK_LABEL = "Semana de corte"


PERIOD_ALL_LABEL = "Desde o início"


@dataclass(frozen=True)
class HoursFilter:
    """O filtro da aba Horas efetivas: empresa, área, encarregado e período (vazio é o padrão)."""

    company_id: int | None = None
    area: str = ""
    foreman: str = ""
    period: str = calculations.PERIOD_WINDOW
    cut_week: str = ""


@dataclass(frozen=True)
class FieldDayView:
    """Uma jornada como a tela a lê, com as figuras calculadas dela (D6)."""

    id: int
    project_id: int
    project_code: str
    project_name: str
    company_id: int
    company_name: str
    day: date
    area: str
    foreman: str
    crew: int
    morning: calculations.ShiftTimes
    afternoon: calculations.ShiftTimes
    notes: str
    version: int
    figures: calculations.FieldDayFigures

    @property
    def project_label(self) -> str:
        """``TN-2026-014 · Nome do projeto``: como o Portfólio nomeia o projeto de uma linha."""
        return f"{self.project_code} · {self.project_name}"


@dataclass(frozen=True)
class WorkSampleReasonView:
    """Um motivo da rodada, de parada ou de trânsito, com a quantidade observada."""

    kind: str
    reason: str
    quantity: int


@dataclass(frozen=True)
class WorkSampleView:
    """Uma rodada da amostragem como a tela a lê, com os motivos das paradas e do trânsito."""

    id: int
    project_id: int
    project_code: str
    project_name: str
    company_id: int
    company_name: str
    day: date
    hour: time
    area: str
    foreman: str
    working: int
    transit: int
    stopped: int
    reasons: tuple[WorkSampleReasonView, ...]
    version: int

    @property
    def project_label(self) -> str:
        return f"{self.project_code} · {self.project_name}"

    @property
    def people(self) -> int:
        """As pessoas observadas na rodada: trabalhando, em trânsito e paradas."""
        return self.working + self.transit + self.stopped

    @property
    def working_pct(self) -> Decimal | None:
        if self.people <= 0:
            return None
        return calculations.round_percent(Decimal(self.working) / Decimal(self.people) * 100)


@dataclass(frozen=True)
class StoppageView:
    """Uma paralisação como a tela a lê, com as horas e o total (Hhora ou Mhora) calculados."""

    id: int
    project_id: int
    project_code: str
    project_name: str
    company_id: int
    company_name: str
    day: date
    area: str
    kind: str
    resource: str
    quantity: Decimal
    start: time
    end: time
    reason: str
    responsibility: str
    description: str
    version: int
    figures: calculations.StoppageFigures

    @property
    def project_label(self) -> str:
        return f"{self.project_code} · {self.project_name}"


@dataclass(frozen=True)
class CapacityAreaRow:
    """A linha do resumo por área: CP média, utilização, Hhora e Mhora do período."""

    area: str
    capacity: Decimal | None
    utilization: Decimal | None
    crew_hours: Decimal
    machine_hours: Decimal
    records: int


@dataclass(frozen=True)
class HoursDayRow:
    """A linha do resumo por dia: CP média e a distribuição da amostragem."""

    day: date
    capacity: Decimal | None
    working_pct: Decimal | None
    transit_pct: Decimal | None
    stopped_pct: Decimal | None


@dataclass(frozen=True)
class ForemanSampleRow:
    """O resumo da amostragem de um encarregado."""

    foreman: str
    share: calculations.SampleShare


@dataclass(frozen=True)
class CompanySampleRow:
    """O resumo da amostragem de uma empresa e dos encarregados dela."""

    company_id: int
    company_name: str
    share: calculations.SampleShare
    foremen: tuple[ForemanSampleRow, ...]


@dataclass(frozen=True)
class HoursOverview:
    """A aba Horas efetivas: filtros, capacidade, amostragem, paralisações e resumos."""

    reference_date: date
    current_week: str
    cut_week: str
    cut_options: tuple[str, ...]
    company_options: tuple[QuantityOption, ...]
    area_options: tuple[str, ...]
    foreman_options: tuple[str, ...]
    period_options: tuple[QuantityOption, ...]
    filter: HoursFilter
    window_start: date | None
    window_end: date
    capacity: calculations.CapacitySummary
    field_days: tuple[FieldDayView, ...]
    samples: tuple[WorkSampleView, ...]
    sample_summary: calculations.SampleShare
    stop_reasons: tuple[calculations.ReasonTotal, ...]
    transit_reasons: tuple[calculations.ReasonTotal, ...]
    sample_companies: tuple[CompanySampleRow, ...]
    stoppages: tuple[StoppageView, ...]
    stoppage_summary: calculations.StoppageSummary
    by_area: tuple[CapacityAreaRow, ...]
    by_day: tuple[HoursDayRow, ...]
    parameters: ProductivityParameters
    is_portfolio: bool
    can_write: bool


def hours_overview(
    session: Session,
    *,
    user: User,
    scope: Scope,
    hours_filter: HoursFilter | None = None,
    reference_date: date,
) -> HoursOverview:
    """A aba Horas efetivas do escopo: a jornada, a amostragem e as paralisações do período.

    O período vem do filtro (semana de corte, últimas N semanas ou desde o início) e o fim
    nunca passa da data de referência. As listas de opções vêm de todos os registros do
    escopo, para o filtro não se fechar sobre si mesmo.
    """
    rbac.require_module(user, MODULE)
    chosen = hours_filter or HoursFilter()
    parameters = productivity_parameters(session, reference_date=reference_date)
    reference_week = calendario.iso_week(reference_date)
    cut_week = _cut_week(chosen.cut_week, reference_week)
    period = chosen.period if chosen.period in calculations.PERIODS else calculations.PERIOD_WINDOW
    window_start, window_end = calculations.hours_window(
        period,
        cut_week=cut_week,
        window_weeks=parameters.window_weeks,
        reference_date=reference_date,
    )
    everything = _hours_records(session, scope)
    lookups = _hours_lookups(session, everything)
    kept = _hours_filtered(everything, chosen, start=window_start, end=window_end)
    field_days = _field_day_views(kept[0], lookups, parameters=parameters)
    samples = _sample_views(kept[1], lookups)
    stoppages = _stoppage_views(kept[2], lookups)
    figures = [view.figures for view in field_days]
    sample_counts = [
        calculations.SampleCounts(working=view.working, transit=view.transit, stopped=view.stopped)
        for view in samples
    ]
    return HoursOverview(
        reference_date=reference_date,
        current_week=reference_week,
        cut_week=cut_week,
        cut_options=_hours_cut_options(everything, reference_week),
        company_options=_hours_company_options(everything, lookups),
        area_options=_hours_areas(everything),
        foreman_options=_hours_foremen(everything, chosen),
        period_options=_period_options(parameters.window_weeks),
        filter=HoursFilter(
            company_id=chosen.company_id,
            area=chosen.area,
            foreman=chosen.foreman,
            period=period,
            cut_week=cut_week,
        ),
        window_start=window_start,
        window_end=window_end,
        capacity=calculations.capacity_summary(figures, daily_hours=parameters.daily_hours),
        field_days=field_days,
        samples=samples,
        sample_summary=calculations.sample_share(sample_counts),
        stop_reasons=calculations.reason_pareto(
            _reason_counts(samples, calculations.SAMPLE_STOPPED),
            catalog=calculations.STOP_REASONS,
        ),
        transit_reasons=calculations.reason_pareto(
            _reason_counts(samples, calculations.SAMPLE_TRANSIT),
            catalog=calculations.TRANSIT_REASONS,
        ),
        sample_companies=_company_samples(samples, lookups),
        stoppages=stoppages,
        stoppage_summary=calculations.stoppage_summary([view.figures for view in stoppages]),
        by_area=_capacity_areas(field_days, stoppages, daily_hours=parameters.daily_hours),
        by_day=_hours_days(field_days, samples, daily_hours=parameters.daily_hours),
        parameters=parameters,
        is_portfolio=scope.is_portfolio,
        can_write=rbac.can(user, Permission.WRITE),
    )


def _period_options(window_weeks: int) -> tuple[QuantityOption, ...]:
    return (
        QuantityOption(value=calculations.PERIOD_WEEK, label=PERIOD_WEEK_LABEL),
        QuantityOption(value=calculations.PERIOD_WINDOW, label=f"Últimas {window_weeks} semanas"),
        QuantityOption(value=calculations.PERIOD_ALL, label=PERIOD_ALL_LABEL),
    )


def _hours_cut_options(records: _HoursRecords, reference_week: str) -> tuple[str, ...]:
    days = (
        [record.day for record in records[0]]
        + [record.day for record in records[1]]
        + [record.day for record in records[2]]
    )
    weeks = {calendario.iso_week(day) for day in days if calendario.iso_week(day) <= reference_week}
    first = min(weeks, default=reference_week)
    return tuple(calculations.list_weeks(first, reference_week))


@dataclass(frozen=True)
class _HoursLookups:
    """Os nomes que as linhas do campo leem, carregados uma vez por consulta."""

    projects: Mapping[int, configuracoes.ProjectSummary]
    companies: Mapping[int, str]


def _hours_lookups(session: Session, records: _HoursRecords) -> _HoursLookups:
    project_ids = (
        {record.project_id for record in records[0]}
        | {record.project_id for record in records[1]}
        | {record.project_id for record in records[2]}
    )
    return _HoursLookups(
        projects={
            project.id: project
            for project in configuracoes.list_projects(session)
            if project.id in project_ids
        },
        companies=configuracoes.list_company_names(session),
    )


type _HoursRecords = tuple[list[FieldDay], list[WorkSample], list[Stoppage]]


def _hours_records(session: Session, scope: Scope) -> _HoursRecords:
    """Os três conjuntos do escopo: jornadas, rodadas (com os motivos) e paralisações."""
    field_days = select(FieldDay)
    samples = select(WorkSample).options(selectinload(WorkSample.reasons))
    stoppages = select(Stoppage)
    if scope.project_id is not None:
        field_days = field_days.where(FieldDay.project_id == scope.project_id)
        samples = samples.where(WorkSample.project_id == scope.project_id)
        stoppages = stoppages.where(Stoppage.project_id == scope.project_id)
    return (
        list(session.scalars(field_days.order_by(FieldDay.day, FieldDay.id))),
        list(session.scalars(samples.order_by(WorkSample.day, WorkSample.id))),
        list(session.scalars(stoppages.order_by(Stoppage.day, Stoppage.id))),
    )


def _hours_filtered(
    records: _HoursRecords, chosen: HoursFilter, *, start: date | None, end: date
) -> _HoursRecords:
    """Os registros que passam pelo filtro: empresa, área, encarregado e a janela do período.

    A paralisação não tem encarregado: como no protótipo, filtrar por encarregado a deixa fora.
    """
    return (
        [
            record
            for record in records[0]
            if _in_hours_window(record.day, start, end)
            and _passes_company(record.company_id, chosen)
            and (not chosen.area or record.area == chosen.area)
            and (not chosen.foreman or record.foreman == chosen.foreman)
        ],
        [
            record
            for record in records[1]
            if _in_hours_window(record.day, start, end)
            and _passes_company(record.company_id, chosen)
            and (not chosen.area or record.area == chosen.area)
            and (not chosen.foreman or record.foreman == chosen.foreman)
        ],
        [
            record
            for record in records[2]
            if _in_hours_window(record.day, start, end)
            and _passes_company(record.company_id, chosen)
            and (not chosen.area or record.area == chosen.area)
            and not chosen.foreman
        ],
    )


def _in_hours_window(day: date, start: date | None, end: date) -> bool:
    return (start is None or day >= start) and day <= end


def _passes_company(company_id: int, chosen: HoursFilter) -> bool:
    return chosen.company_id is None or company_id == chosen.company_id


def _hours_areas(records: _HoursRecords) -> tuple[str, ...]:
    areas = (
        {record.area for record in records[0]}
        | {record.area for record in records[1]}
        | {record.area for record in records[2]}
    )
    return tuple(sorted(areas))


def _hours_foremen(records: _HoursRecords, chosen: HoursFilter) -> tuple[str, ...]:
    foremen = {
        record.foreman
        for record in records[0] + records[1]
        if chosen.company_id is None or record.company_id == chosen.company_id
    }
    return tuple(sorted(foremen))


def _hours_company_options(
    records: _HoursRecords, lookups: _HoursLookups
) -> tuple[QuantityOption, ...]:
    ids = (
        {record.company_id for record in records[0]}
        | {record.company_id for record in records[1]}
        | {record.company_id for record in records[2]}
    )
    return tuple(
        QuantityOption(value=str(company_id), label=lookups.companies.get(company_id, ""))
        for company_id in sorted(ids)
        if lookups.companies.get(company_id)
    )


def _shift(morning_arrival: time, start: time, end: time) -> calculations.ShiftTimes:
    return calculations.ShiftTimes(arrival=morning_arrival, start=start, end=end)


def _field_day_views(
    records: Sequence[FieldDay],
    lookups: _HoursLookups,
    *,
    parameters: ProductivityParameters,
) -> tuple[FieldDayView, ...]:
    views = [
        FieldDayView(
            id=record.id,
            project_id=record.project_id,
            project_code=lookups.projects[record.project_id].code,
            project_name=lookups.projects[record.project_id].name,
            company_id=record.company_id,
            company_name=lookups.companies.get(record.company_id, ""),
            day=record.day,
            area=record.area,
            foreman=record.foreman,
            crew=record.crew,
            morning=_shift(record.morning_arrival, record.morning_start, record.morning_end),
            afternoon=_shift(
                record.afternoon_arrival, record.afternoon_start, record.afternoon_end
            ),
            notes=record.notes or "",
            version=record.version,
            figures=calculations.field_day_figures(
                day=record.day,
                crew=record.crew,
                morning=_shift(record.morning_arrival, record.morning_start, record.morning_end),
                afternoon=_shift(
                    record.afternoon_arrival, record.afternoon_start, record.afternoon_end
                ),
                daily_hours=parameters.daily_hours,
            ),
        )
        for record in records
    ]
    return tuple(sorted(views, key=lambda view: (view.day, view.id), reverse=True))


def _sample_views(
    records: Sequence[WorkSample], lookups: _HoursLookups
) -> tuple[WorkSampleView, ...]:
    views = [
        WorkSampleView(
            id=record.id,
            project_id=record.project_id,
            project_code=lookups.projects[record.project_id].code,
            project_name=lookups.projects[record.project_id].name,
            company_id=record.company_id,
            company_name=lookups.companies.get(record.company_id, ""),
            day=record.day,
            hour=record.hour,
            area=record.area,
            foreman=record.foreman,
            working=record.working,
            transit=record.transit,
            stopped=record.stopped,
            reasons=tuple(
                WorkSampleReasonView(
                    kind=reason.kind, reason=reason.reason, quantity=reason.quantity
                )
                for reason in record.reasons
            ),
            version=record.version,
        )
        for record in records
    ]
    return tuple(sorted(views, key=lambda view: (view.day, view.hour, view.id), reverse=True))


def _stoppage_views(
    records: Sequence[Stoppage], lookups: _HoursLookups
) -> tuple[StoppageView, ...]:
    views = [
        StoppageView(
            id=record.id,
            project_id=record.project_id,
            project_code=lookups.projects[record.project_id].code,
            project_name=lookups.projects[record.project_id].name,
            company_id=record.company_id,
            company_name=lookups.companies.get(record.company_id, ""),
            day=record.day,
            area=record.area,
            kind=record.kind,
            resource=record.resource,
            quantity=record.quantity,
            start=record.start,
            end=record.end,
            reason=record.reason,
            responsibility=record.responsibility,
            description=record.description or "",
            version=record.version,
            figures=calculations.stoppage_figures(
                day=record.day,
                kind=record.kind,
                reason=record.reason,
                responsibility=record.responsibility,
                quantity=record.quantity,
                start=record.start,
                end=record.end,
            ),
        )
        for record in records
    ]
    return tuple(sorted(views, key=lambda view: (view.day, view.id), reverse=True))


def _reason_counts(samples: Sequence[WorkSampleView], kind: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        for reason in sample.reasons:
            if reason.kind == kind:
                counts[reason.reason] = counts.get(reason.reason, 0) + reason.quantity
    return counts


def _company_samples(
    samples: Sequence[WorkSampleView], lookups: _HoursLookups
) -> tuple[CompanySampleRow, ...]:
    grouped: dict[int, list[WorkSampleView]] = {}
    for sample in samples:
        grouped.setdefault(sample.company_id, []).append(sample)
    rows: list[CompanySampleRow] = []
    for company_id, company_group in sorted(
        grouped.items(), key=lambda item: lookups.companies.get(item[0], "")
    ):
        foremen: dict[str, list[WorkSampleView]] = {}
        for sample in company_group:
            foremen.setdefault(sample.foreman, []).append(sample)
        rows.append(
            CompanySampleRow(
                company_id=company_id,
                company_name=lookups.companies.get(company_id, ""),
                share=calculations.sample_share([_counts_of(sample) for sample in company_group]),
                foremen=tuple(
                    ForemanSampleRow(
                        foreman=name,
                        share=calculations.sample_share(
                            [_counts_of(sample) for sample in foreman_group]
                        ),
                    )
                    for name, foreman_group in sorted(foremen.items())
                ),
            )
        )
    return tuple(rows)


def _counts_of(sample: WorkSampleView) -> calculations.SampleCounts:
    return calculations.SampleCounts(
        working=sample.working, transit=sample.transit, stopped=sample.stopped
    )


def _capacity_areas(
    field_days: Sequence[FieldDayView],
    stoppages: Sequence[StoppageView],
    *,
    daily_hours: Decimal,
) -> tuple[CapacityAreaRow, ...]:
    areas = {view.area for view in field_days} | {view.area for view in stoppages}
    rows: list[CapacityAreaRow] = []
    for area in sorted(areas):
        local_days = [view for view in field_days if view.area == area]
        local_stops = [view for view in stoppages if view.area == area]
        summary = calculations.capacity_summary(
            [view.figures for view in local_days], daily_hours=daily_hours
        )
        stops = calculations.stoppage_summary([view.figures for view in local_stops])
        rows.append(
            CapacityAreaRow(
                area=area,
                capacity=summary.capacity,
                utilization=summary.utilization,
                crew_hours=stops.crew_hours,
                machine_hours=stops.machine_hours,
                records=summary.records,
            )
        )
    return tuple(rows)


def _hours_days(
    field_days: Sequence[FieldDayView],
    samples: Sequence[WorkSampleView],
    *,
    daily_hours: Decimal,
) -> tuple[HoursDayRow, ...]:
    days = {view.day for view in field_days} | {view.day for view in samples}
    rows: list[HoursDayRow] = []
    for day in sorted(days):
        local_days = [view.figures for view in field_days if view.day == day]
        local_samples = [view for view in samples if view.day == day]
        share = calculations.sample_share([_counts_of(sample) for sample in local_samples])
        rows.append(
            HoursDayRow(
                day=day,
                capacity=calculations.capacity_summary(
                    local_days, daily_hours=daily_hours
                ).capacity,
                working_pct=share.working_pct,
                transit_pct=share.transit_pct,
                stopped_pct=share.stopped_pct,
            )
        )
    return tuple(rows)


# ── Escrita do campo: jornada, amostragem e paralisação (ISSUE-047) ────────


def _field_choices(session: Session) -> validation.FieldChoices:
    """As escolhas dos formulários do campo: as empresas do cadastro."""
    return validation.FieldChoices(
        company_ids=frozenset(option.id for option in configuracoes.list_company_options(session))
    )


def save_field_day(
    session: Session,
    *,
    user: User,
    scope: Scope,
    day_id: int | None,
    form: validation.FieldDayForm,
    reference_date: date,
) -> FieldDay:
    """Cria ou grava a jornada; a segunda jornada da mesma frente e dia é recusada."""
    rbac.require(user, Permission.WRITE)
    data = validation.parse_field_day(form, _field_choices(session), reference_date=reference_date)
    record = _scoped_field_day(session, scope, day_id) if day_id is not None else None
    project_id = record.project_id if record is not None else scope.require_project()
    _refuse_duplicate_field_day(
        session,
        project_id=project_id,
        data=data,
        exclude_id=None if record is None else record.id,
    )
    changes = _field_day_changes(data)
    if record is None:
        return recording.create(
            session,
            user_id=user.id,
            record=FieldDay(
                project_id=project_id,
                recorded_by_id=user.person_id,
                **changes,
            ),
        )
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes=changes,
        version=form.fields.get("versao"),
    )
    return record


def _field_day_changes(data: validation.FieldDayData) -> dict[str, Any]:
    return {
        "company_id": data.company_id,
        "day": data.day,
        "area": data.area,
        "foreman": data.foreman,
        "crew": data.crew,
        "morning_arrival": data.morning.arrival,
        "morning_start": data.morning.start,
        "morning_end": data.morning.end,
        "afternoon_arrival": data.afternoon.arrival,
        "afternoon_start": data.afternoon.start,
        "afternoon_end": data.afternoon.end,
        "notes": data.notes,
    }


def _refuse_duplicate_field_day(
    session: Session,
    *,
    project_id: int,
    data: validation.FieldDayData,
    exclude_id: int | None,
) -> None:
    """Recusa a segunda jornada da mesma frente (empresa, área e encarregado) no dia."""
    found = session.scalars(
        select(FieldDay.id).where(
            FieldDay.project_id == project_id,
            FieldDay.day == data.day,
            FieldDay.company_id == data.company_id,
            FieldDay.area == data.area,
            FieldDay.foreman == data.foreman,
        )
    ).all()
    if any(record_id != exclude_id for record_id in found):
        raise InvalidDataError(FIELD_DAY_DUPLICATE_MESSAGE)


def save_work_sample(
    session: Session,
    *,
    user: User,
    scope: Scope,
    sample_id: int | None,
    form: validation.WorkSampleForm,
    reference_date: date,
) -> WorkSample:
    """Cria ou grava a rodada da amostragem, trocando os motivos junto com ela."""
    rbac.require(user, Permission.WRITE)
    data = validation.parse_work_sample(
        form, _field_choices(session), reference_date=reference_date
    )
    record = _scoped_sample(session, scope, sample_id) if sample_id is not None else None
    project_id = record.project_id if record is not None else scope.require_project()
    stopped = sum(quantity for _, quantity in data.stopped_reasons)
    transit = sum(quantity for _, quantity in data.transit_reasons)
    if record is None:
        record = WorkSample(
            project_id=project_id,
            company_id=data.company_id,
            observer_id=user.person_id,
            day=data.day,
            hour=data.hour,
            area=data.area,
            foreman=data.foreman,
            working=data.working,
            transit=transit,
            stopped=stopped,
        )
        session.add(record)
        session.flush()
        record.reasons = _sample_reasons(data)
        session.flush()
        audit.append(
            session,
            TrailLine(
                user_id=user.id,
                entity=WorkSample.__tablename__,
                record_id=record.id,
                action=audit.CREATED,
                after=_sample_aggregate(record),
                project_id=project_id,
            ),
        )
        return record
    before = _sample_aggregate(record)
    versioning.require(session, record, form.fields.get("versao"))
    record.company_id = data.company_id
    record.day = data.day
    record.hour = data.hour
    record.area = data.area
    record.foreman = data.foreman
    record.working = data.working
    record.transit = transit
    record.stopped = stopped
    record.reasons = _sample_reasons(data)
    versioning.advance(record)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=WorkSample.__tablename__,
            record_id=record.id,
            action=audit.UPDATED,
            before=before,
            after=_sample_aggregate(record),
            project_id=record.project_id,
        ),
    )
    return record


def _sample_reasons(data: validation.WorkSampleData) -> list[WorkSampleReason]:
    return [
        WorkSampleReason(kind=calculations.SAMPLE_STOPPED, reason=reason, quantity=quantity)
        for reason, quantity in data.stopped_reasons
    ] + [
        WorkSampleReason(kind=calculations.SAMPLE_TRANSIT, reason=reason, quantity=quantity)
        for reason, quantity in data.transit_reasons
    ]


def _sample_aggregate(record: WorkSample) -> dict[str, Any]:
    """A rodada e os motivos como a trilha os guarda, nos nomes em português."""
    return {
        **audit.snapshot(record),
        "motivos": [
            {"tipo": reason.kind, "motivo": reason.reason, "quantidade": reason.quantity}
            for reason in record.reasons
        ],
    }


def save_stoppage(
    session: Session,
    *,
    user: User,
    scope: Scope,
    stoppage_id: int | None,
    form: validation.StoppageForm,
    reference_date: date,
) -> Stoppage:
    """Cria ou grava a paralisação de efetivo ou de máquina e equipamento."""
    rbac.require(user, Permission.WRITE)
    data = validation.parse_stoppage(form, _field_choices(session), reference_date=reference_date)
    record = _scoped_stoppage(session, scope, stoppage_id) if stoppage_id is not None else None
    project_id = record.project_id if record is not None else scope.require_project()
    changes = _stoppage_changes(data)
    if record is None:
        return recording.create(
            session,
            user_id=user.id,
            record=Stoppage(
                project_id=project_id,
                recorded_by_id=user.person_id,
                **changes,
            ),
        )
    recording.update(
        session,
        user_id=user.id,
        record=record,
        changes=changes,
        version=form.fields.get("versao"),
    )
    return record


def _stoppage_changes(data: validation.StoppageData) -> dict[str, Any]:
    return {
        "company_id": data.company_id,
        "day": data.day,
        "area": data.area,
        "kind": data.kind,
        "resource": data.resource,
        "quantity": data.quantity,
        "start": data.start,
        "end": data.end,
        "reason": data.reason,
        "responsibility": data.responsibility,
        "description": data.description,
    }


def _scoped_field_day(session: Session, scope: Scope, day_id: int) -> FieldDay:
    record = session.scalars(
        select(FieldDay).execution_options(populate_existing=True).where(FieldDay.id == day_id)
    ).one_or_none()
    if record is None:
        raise InvalidDataError(FIELD_DAY_NOT_FOUND_MESSAGE)
    if scope.project_id is not None and record.project_id != scope.project_id:
        raise InvalidDataError(FIELD_PROJECT_MESSAGE)
    return record


def _scoped_sample(session: Session, scope: Scope, sample_id: int) -> WorkSample:
    record = session.scalars(
        select(WorkSample)
        .options(selectinload(WorkSample.reasons))
        .execution_options(populate_existing=True)
        .where(WorkSample.id == sample_id)
    ).one_or_none()
    if record is None:
        raise InvalidDataError(SAMPLE_NOT_FOUND_MESSAGE)
    if scope.project_id is not None and record.project_id != scope.project_id:
        raise InvalidDataError(FIELD_PROJECT_MESSAGE)
    return record


def _scoped_stoppage(session: Session, scope: Scope, stoppage_id: int) -> Stoppage:
    record = session.scalars(
        select(Stoppage).execution_options(populate_existing=True).where(Stoppage.id == stoppage_id)
    ).one_or_none()
    if record is None:
        raise InvalidDataError(STOPPAGE_NOT_FOUND_MESSAGE)
    if scope.project_id is not None and record.project_id != scope.project_id:
        raise InvalidDataError(FIELD_PROJECT_MESSAGE)
    return record


# ── Carga do campo ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LoadedFieldDay:
    """Uma jornada da carga de demonstração, com os ids do banco e as datas já deslocadas."""

    project_id: int
    company_id: int
    recorded_by_id: int
    day: date
    area: str
    foreman: str
    crew: int
    morning: calculations.ShiftTimes
    afternoon: calculations.ShiftTimes
    notes: str | None


@dataclass(frozen=True)
class LoadedSampleReason:
    """Um motivo da rodada da carga de demonstração."""

    kind: str
    reason: str
    quantity: int


@dataclass(frozen=True)
class LoadedWorkSample:
    """Uma rodada da amostragem da carga de demonstração."""

    project_id: int
    company_id: int
    observer_id: int
    day: date
    hour: time
    area: str
    foreman: str
    working: int
    transit: int
    stopped: int
    reasons: tuple[LoadedSampleReason, ...]


@dataclass(frozen=True)
class LoadedStoppage:
    """Uma paralisação da carga de demonstração."""

    project_id: int
    company_id: int
    recorded_by_id: int
    day: date
    area: str
    kind: str
    resource: str
    quantity: Decimal
    start: time
    end: time
    reason: str
    responsibility: str
    description: str | None


def load_field_day(session: Session, *, author_id: int, data: LoadedFieldDay) -> FieldDay:
    """Grava uma jornada da demonstração, com a trilha."""
    return recording.create(
        session,
        user_id=author_id,
        record=FieldDay(
            project_id=data.project_id,
            company_id=data.company_id,
            recorded_by_id=data.recorded_by_id,
            day=data.day,
            area=data.area,
            foreman=data.foreman,
            crew=data.crew,
            morning_arrival=data.morning.arrival,
            morning_start=data.morning.start,
            morning_end=data.morning.end,
            afternoon_arrival=data.afternoon.arrival,
            afternoon_start=data.afternoon.start,
            afternoon_end=data.afternoon.end,
            notes=data.notes,
        ),
    )


def load_work_sample(session: Session, *, author_id: int, data: LoadedWorkSample) -> WorkSample:
    """Grava uma rodada da demonstração com os motivos, com a trilha do agregado."""
    record = WorkSample(
        project_id=data.project_id,
        company_id=data.company_id,
        observer_id=data.observer_id,
        day=data.day,
        hour=data.hour,
        area=data.area,
        foreman=data.foreman,
        working=data.working,
        transit=data.transit,
        stopped=data.stopped,
    )
    session.add(record)
    session.flush()
    record.reasons = [
        WorkSampleReason(kind=reason.kind, reason=reason.reason, quantity=reason.quantity)
        for reason in data.reasons
    ]
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=author_id,
            entity=WorkSample.__tablename__,
            record_id=record.id,
            action=audit.CREATED,
            after=_sample_aggregate(record),
            project_id=data.project_id,
        ),
    )
    return record


def load_stoppage(session: Session, *, author_id: int, data: LoadedStoppage) -> Stoppage:
    """Grava uma paralisação da demonstração, com a trilha."""
    return recording.create(
        session,
        user_id=author_id,
        record=Stoppage(
            project_id=data.project_id,
            company_id=data.company_id,
            recorded_by_id=data.recorded_by_id,
            day=data.day,
            area=data.area,
            kind=data.kind,
            resource=data.resource,
            quantity=data.quantity,
            start=data.start,
            end=data.end,
            reason=data.reason,
            responsibility=data.responsibility,
            description=data.description,
        ),
    )


# ── Formulários do campo (ISSUE-047) ───────────────────────────────────────


@dataclass(frozen=True)
class FieldFormOptions:
    """O que os formulários do campo oferecem: cadastros, sugestões e os catálogos."""

    companies: tuple[configuracoes.RegisterOption, ...]
    areas: tuple[str, ...]
    foremen: tuple[str, ...]
    stop_reasons: tuple[str, ...]
    transit_reasons: tuple[str, ...]
    stoppage_reasons: tuple[str, ...]
    responsibilities: tuple[str, ...]
    kinds: tuple[str, ...]


@dataclass(frozen=True)
class FieldDayFormView:
    """O formulário da jornada pronto para o template: valores, opções e erros."""

    record: FieldDayView | None
    fields: Mapping[str, str]
    options: FieldFormOptions
    errors: Mapping[str, str]


@dataclass(frozen=True)
class WorkSampleFormView:
    """O formulário da rodada pronto para o template: valores, opções e erros."""

    record: WorkSampleView | None
    fields: Mapping[str, str]
    options: FieldFormOptions
    errors: Mapping[str, str]


@dataclass(frozen=True)
class StoppageFormView:
    """O formulário da paralisação pronto para o template: valores, opções e erros."""

    record: StoppageView | None
    fields: Mapping[str, str]
    options: FieldFormOptions
    errors: Mapping[str, str]


def field_form_options(session: Session, scope: Scope) -> FieldFormOptions:
    """As opções dos formulários do campo: empresas, as áreas e encarregados já registrados."""
    records = _hours_records(session, scope)
    return FieldFormOptions(
        companies=tuple(configuracoes.list_company_options(session)),
        areas=_hours_areas(records),
        foremen=_hours_foremen(records, HoursFilter()),
        stop_reasons=calculations.STOP_REASONS,
        transit_reasons=calculations.TRANSIT_REASONS,
        stoppage_reasons=calculations.STOPPAGE_REASONS,
        responsibilities=calculations.RESPONSIBILITIES,
        kinds=calculations.STOPPAGE_KINDS,
    )


def field_day_form(
    session: Session,
    *,
    user: User,
    scope: Scope,
    day_id: int | None,
    form: validation.FieldDayForm | None,
    reference_date: date,
    errors: Mapping[str, str] | None = None,
) -> FieldDayFormView:
    """O formulário da jornada: em branco, reaberto com o que foi digitado, ou em edição."""
    rbac.require_module(user, MODULE)
    record = _scoped_field_day(session, scope, day_id) if day_id is not None else None
    view = _single_field_day(session, record, reference_date=reference_date)
    return FieldDayFormView(
        record=view,
        fields=_field_day_fields(record, form=form, reference_date=reference_date),
        options=field_form_options(session, scope),
        errors=errors or {},
    )


def _single_field_day(
    session: Session, record: FieldDay | None, *, reference_date: date
) -> FieldDayView | None:
    if record is None:
        return None
    lookups = _hours_lookups(session, ([record], [], []))
    parameters = productivity_parameters(session, reference_date=reference_date)
    return _field_day_views([record], lookups, parameters=parameters)[0]


def _field_day_fields(
    record: FieldDay | None,
    *,
    form: validation.FieldDayForm | None,
    reference_date: date,
) -> dict[str, str]:
    if form is not None:
        return dict(form.fields)
    if record is None:
        return {
            validation.FIELD_DAY_DATE: reference_date.isoformat(),
            validation.FIELD_DAY_MORNING: "07:30",
        }
    return {
        validation.FIELD_DAY_DATE: record.day.isoformat(),
        validation.FIELD_DAY_COMPANY: str(record.company_id),
        validation.FIELD_DAY_AREA: record.area,
        validation.FIELD_DAY_FOREMAN: record.foreman,
        validation.FIELD_DAY_CREW: str(record.crew),
        validation.FIELD_DAY_MORNING: _clock(record.morning_arrival),
        validation.FIELD_DAY_MORNING_START: _clock(record.morning_start),
        validation.FIELD_DAY_MORNING_END: _clock(record.morning_end),
        validation.FIELD_DAY_AFTERNOON: _clock(record.afternoon_arrival),
        validation.FIELD_DAY_AFTERNOON_START: _clock(record.afternoon_start),
        validation.FIELD_DAY_AFTERNOON_END: _clock(record.afternoon_end),
        validation.FIELD_DAY_NOTES: record.notes or "",
        "versao": str(record.version),
    }


def work_sample_form(
    session: Session,
    *,
    user: User,
    scope: Scope,
    sample_id: int | None,
    form: validation.WorkSampleForm | None,
    reference_date: date,
    errors: Mapping[str, str] | None = None,
) -> WorkSampleFormView:
    """O formulário da rodada: em branco, reaberto com o que foi digitado, ou em edição."""
    rbac.require_module(user, MODULE)
    record = _scoped_sample(session, scope, sample_id) if sample_id is not None else None
    view = None
    if record is not None:
        lookups = _hours_lookups(session, ([], [record], []))
        view = _sample_views([record], lookups)[0]
    return WorkSampleFormView(
        record=view,
        fields=_work_sample_fields(record, form=form, reference_date=reference_date),
        options=field_form_options(session, scope),
        errors=errors or {},
    )


def _work_sample_fields(
    record: WorkSample | None,
    *,
    form: validation.WorkSampleForm | None,
    reference_date: date,
) -> dict[str, str]:
    if form is not None:
        fields = dict(form.fields)
        for index, value in form.stopped.items():
            fields[f"{validation.FIELD_STOPPED_PREFIX}{index}"] = value
        for index, value in form.transit.items():
            fields[f"{validation.FIELD_TRANSIT_PREFIX}{index}"] = value
        return fields
    if record is None:
        return {
            validation.FIELD_DAY_DATE: reference_date.isoformat(),
            validation.FIELD_SAMPLE_HOUR: "09:30",
        }
    fields = {
        validation.FIELD_DAY_DATE: record.day.isoformat(),
        validation.FIELD_SAMPLE_HOUR: _clock(record.hour),
        validation.FIELD_DAY_COMPANY: str(record.company_id),
        validation.FIELD_DAY_AREA: record.area,
        validation.FIELD_DAY_FOREMAN: record.foreman,
        validation.FIELD_SAMPLE_WORKING: str(record.working),
        "versao": str(record.version),
    }
    for reason in record.reasons:
        if reason.kind == calculations.SAMPLE_STOPPED:
            prefix, catalog = validation.FIELD_STOPPED_PREFIX, calculations.STOP_REASONS
        else:
            prefix, catalog = validation.FIELD_TRANSIT_PREFIX, calculations.TRANSIT_REASONS
        if reason.reason in catalog:
            fields[f"{prefix}{catalog.index(reason.reason)}"] = str(reason.quantity)
    return fields


def stoppage_form(
    session: Session,
    *,
    user: User,
    scope: Scope,
    stoppage_id: int | None,
    form: validation.StoppageForm | None,
    reference_date: date,
    errors: Mapping[str, str] | None = None,
) -> StoppageFormView:
    """O formulário da paralisação: em branco, reaberto com o que foi digitado, ou em edição."""
    rbac.require_module(user, MODULE)
    record = _scoped_stoppage(session, scope, stoppage_id) if stoppage_id is not None else None
    view = None
    if record is not None:
        lookups = _hours_lookups(session, ([], [], [record]))
        view = _stoppage_views([record], lookups)[0]
    return StoppageFormView(
        record=view,
        fields=_stoppage_fields(record, form=form, reference_date=reference_date),
        options=field_form_options(session, scope),
        errors=errors or {},
    )


def _stoppage_fields(
    record: Stoppage | None,
    *,
    form: validation.StoppageForm | None,
    reference_date: date,
) -> dict[str, str]:
    if form is not None:
        return dict(form.fields)
    if record is None:
        return {
            validation.FIELD_DAY_DATE: reference_date.isoformat(),
            validation.FIELD_STOPPAGE_KIND: calculations.STOPPAGE_CREW,
            validation.FIELD_STOPPAGE_RESPONSIBILITY: calculations.RESPONSIBILITIES[0],
        }
    return {
        validation.FIELD_DAY_DATE: record.day.isoformat(),
        validation.FIELD_DAY_COMPANY: str(record.company_id),
        validation.FIELD_DAY_AREA: record.area,
        validation.FIELD_STOPPAGE_KIND: record.kind,
        validation.FIELD_STOPPAGE_RESOURCE: record.resource,
        validation.FIELD_STOPPAGE_QUANTITY: _plain_decimal(record.quantity),
        validation.FIELD_STOPPAGE_START: _clock(record.start),
        validation.FIELD_STOPPAGE_END: _clock(record.end),
        validation.FIELD_STOPPAGE_REASON: record.reason,
        validation.FIELD_STOPPAGE_RESPONSIBILITY: record.responsibility,
        validation.FIELD_STOPPAGE_DESCRIPTION: record.description or "",
        "versao": str(record.version),
    }


def _clock(value: time) -> str:
    return value.strftime("%H:%M")


# ── KPIs de performance da Produtividade (ISSUE-048) ──────────────────────


PERFORMANCE_ACTION_GROUP = "Produtividade"


PERFORMANCE_ACTION_DAYS = 14


ACTION_ALREADY_OPEN_MESSAGE = "Já existe ação aberta na Central para esta empresa e semana."


INDICATOR_LABELS: Mapping[str, str] = {
    "adherence": "aderência",
    "pf": "fator de produtividade",
    "spi": "SPI de quantidades",
    "working": "pessoas trabalhando",
    "utilization": "utilização da jornada",
}


@dataclass(frozen=True)
class PerformanceFilter:
    """O filtro da aba KPIs: a empresa e a semana de corte (vazio é o padrão)."""

    company_id: int | None = None
    cut_week: str = ""


@dataclass(frozen=True)
class PerformanceActionRef:
    """A ação aberta de uma empresa e semana: a referência e o endereço da lista da Central."""

    reference: str
    url: str | None


@dataclass(frozen=True)
class PerformanceBlock:
    """Um bloco da performance: as quantidades, o campo, a tendência e os alertas do recorte."""

    project_id: int | None
    project_code: str
    project_name: str
    company_id: int | None
    company_name: str
    quantities: calculations.QuantityIndicators
    capacity: calculations.CapacitySummary
    sample: calculations.SampleShare
    stoppages: calculations.StoppageSummary
    schedule: calculations.ScheduleTrend
    available_hh: Decimal
    stoppage_share: Decimal | None
    bands: calculations.PerformanceBands
    alerts: tuple[str, ...]
    attentions: tuple[str, ...]
    trend: tuple[calculations.TrendWeek, ...]
    action: PerformanceActionRef | None

    @property
    def project_label(self) -> str:
        """``TN-2026-014 · Nome do projeto``: como o Portfólio nomeia o projeto de uma linha."""
        return f"{self.project_code} · {self.project_name}"

    @property
    def label(self) -> str:
        """O nome da série: a empresa, com o projeto antes dela no Portfólio."""
        if not self.project_code:
            return self.company_name
        return f"{self.project_code} · {self.company_name}"

    @property
    def attention_keys(self) -> tuple[str, ...]:
        """Os indicadores fora da faixa, os alertas antes dos pontos de atenção."""
        return (*self.alerts, *self.attentions)

    @property
    def has_attention(self) -> bool:
        """Se a empresa tem indicador fora da faixa: é o que oferece o plano de ação."""
        return bool(self.attention_keys)


@dataclass(frozen=True)
class PerformanceOverview:
    """A aba KPIs de performance: filtros, blocos, tendência semanal e os gráficos (D11)."""

    reference_date: date
    current_week: str
    cut_week: str
    cut_options: tuple[str, ...]
    company_options: tuple[QuantityOption, ...]
    filter: PerformanceFilter
    window_weeks: tuple[str, ...]
    trend_weeks: tuple[str, ...]
    general: PerformanceBlock
    selected: PerformanceBlock
    companies: tuple[PerformanceBlock, ...]
    adherence_chart: dict[str, Any]
    working_chart: dict[str, Any]
    parameters: ProductivityParameters
    is_portfolio: bool
    can_write: bool


@dataclass(frozen=True)
class PerformanceFormOptions:
    """O que o formulário do plano oferece: as empresas e as pessoas do cadastro."""

    companies: tuple[configuracoes.RegisterOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]


@dataclass(frozen=True)
class PerformanceFormView:
    """O formulário do plano de ação pronto para o template: valores, opções e erros."""

    fields: Mapping[str, str]
    options: PerformanceFormOptions
    errors: Mapping[str, str]
    block: PerformanceBlock


@dataclass(frozen=True)
class _PerformanceContext:
    """O que todos os blocos da aba leem: os fatos do escopo e o corte, carregados uma vez."""

    session: Session
    user: User
    scope: Scope
    lookups: _ItemLookups
    reads: Sequence[_ItemRead]
    hours_records: _HoursRecords
    hours_lookups: _HoursLookups
    parameters: ProductivityParameters
    cut_week: str
    reference_date: date
    window_start: date | None
    window_end: date
    trend_weeks: tuple[str, ...]


@dataclass(frozen=True)
class _PerformanceField:
    """Os registros do campo de um recorte, já como a tela os lê."""

    field_days: tuple[FieldDayView, ...]
    samples: tuple[WorkSampleView, ...]
    stoppages: tuple[StoppageView, ...]


def performance_overview(
    session: Session,
    *,
    user: User,
    scope: Scope,
    performance_filter: PerformanceFilter | None = None,
    reference_date: date,
) -> PerformanceOverview:
    """A aba KPIs de performance do escopo, na janela de N semanas até a semana de corte.

    O bloco geral soma o escopo e cada empresa tem o seu (no Portfólio, por projeto e
    empresa, para a coluna Projeto). Os indicadores de quantidades vêm da janela do
    parâmetro; o campo, da mesma janela de datas, limitada à data de referência (D6).
    """
    rbac.require_module(user, MODULE)
    chosen = performance_filter or PerformanceFilter()
    parameters = productivity_parameters(session, reference_date=reference_date)
    reference_week = calendario.iso_week(reference_date)
    cut_week = _cut_week(chosen.cut_week, reference_week)
    records = _items_in(session, scope)
    lookups = _item_lookups(session, records)
    reads = [
        _item_read(
            record,
            lookups=lookups,
            cut_week=cut_week,
            current_week=reference_week,
            window_weeks=parameters.window_weeks,
        )
        for record in records
    ]
    hours_records = _hours_records(session, scope)
    hours_lookups = _hours_lookups(session, hours_records)
    window_start, window_end = calculations.hours_window(
        calculations.PERIOD_WINDOW,
        cut_week=cut_week,
        window_weeks=parameters.window_weeks,
        reference_date=reference_date,
    )
    context = _PerformanceContext(
        session=session,
        user=user,
        scope=scope,
        lookups=lookups,
        reads=reads,
        hours_records=hours_records,
        hours_lookups=hours_lookups,
        parameters=parameters,
        cut_week=cut_week,
        reference_date=reference_date,
        window_start=window_start,
        window_end=window_end,
        trend_weeks=_performance_trend_weeks(cut_week),
    )
    general = _performance_block(
        context, project_id=_performance_project_id(scope), company_id=None
    )
    companies = tuple(
        _performance_block(context, project_id=project_id, company_id=company_id)
        for project_id, company_id in _performance_groups(context)
    )
    adherence_chart, working_chart = _performance_charts(context, companies=companies)
    return PerformanceOverview(
        reference_date=reference_date,
        current_week=reference_week,
        cut_week=cut_week,
        cut_options=_cut_options(records, reference_week),
        company_options=_performance_company_options(context),
        filter=PerformanceFilter(company_id=chosen.company_id, cut_week=cut_week),
        window_weeks=_performance_window_weeks(cut_week, parameters.window_weeks),
        trend_weeks=context.trend_weeks,
        general=general,
        selected=_performance_selected(
            context, chosen=chosen, general=general, companies=companies
        ),
        companies=companies,
        adherence_chart=adherence_chart,
        working_chart=working_chart,
        parameters=parameters,
        is_portfolio=scope.is_portfolio,
        can_write=rbac.can(user, Permission.WRITE),
    )


def _performance_project_id(scope: Scope) -> int | None:
    return None if scope.is_portfolio else scope.project_id


def _performance_trend_weeks(cut_week: str) -> tuple[str, ...]:
    first = calculations.shift_week(cut_week, -(calculations.TREND_WEEKS - 1)) or cut_week
    return calculations.list_weeks(first, cut_week)


def _performance_window_weeks(cut_week: str, window_weeks: int) -> tuple[str, ...]:
    first = calculations.shift_week(cut_week, -(window_weeks - 1)) or cut_week
    return calculations.list_weeks(first, cut_week)


def _performance_groups(context: _PerformanceContext) -> tuple[tuple[int | None, int], ...]:
    """Os recortes por empresa (por projeto e empresa no Portfólio), na ordem da tela."""
    portfolio = context.scope.is_portfolio
    project_id = _performance_project_id(context.scope)
    keys = {
        (read.record.project_id if portfolio else project_id, read.view.company_id)
        for read in context.reads
    }
    for records in context.hours_records:
        for record in records:
            keys.add((record.project_id if portfolio else project_id, record.company_id))

    def order(key: tuple[int | None, int]) -> tuple[str, str, int]:
        project = context.lookups.projects.get(key[0]) if key[0] is not None else None
        return (
            project.code if project is not None else "",
            context.lookups.companies.get(key[1], ""),
            key[1],
        )

    return tuple(sorted(keys, key=order))


def _performance_company_options(context: _PerformanceContext) -> tuple[QuantityOption, ...]:
    ids = {read.view.company_id for read in context.reads}
    for records in context.hours_records:
        for record in records:
            ids.add(record.company_id)
    return tuple(
        QuantityOption(value=str(company_id), label=name)
        for company_id in sorted(ids)
        if (name := context.lookups.companies.get(company_id, ""))
    )


def _performance_selected(
    context: _PerformanceContext,
    *,
    chosen: PerformanceFilter,
    general: PerformanceBlock,
    companies: Sequence[PerformanceBlock],
) -> PerformanceBlock:
    """O bloco que a faixa de indicadores mostra: o geral ou o da empresa filtrada."""
    if chosen.company_id is None:
        return general
    if context.scope.is_portfolio:
        return _performance_block(context, project_id=None, company_id=chosen.company_id)
    return next((block for block in companies if block.company_id == chosen.company_id), general)


def _performance_block(
    context: _PerformanceContext,
    *,
    project_id: int | None,
    company_id: int | None,
) -> PerformanceBlock:
    """Um recorte da performance: quantidades, campo, tendência, faixas e ação aberta."""
    approved = [
        read
        for read in context.reads
        if read.view.approved
        and (project_id is None or read.record.project_id == project_id)
        and (company_id is None or read.view.company_id == company_id)
    ]
    window = _performance_field(
        context,
        project_id=project_id,
        company_id=company_id,
        start=context.window_start,
        end=context.window_end,
    )
    quantities = calculations.quantities_indicators([read.view.figures for read in approved])
    capacity = calculations.capacity_summary(
        [view.figures for view in window.field_days],
        daily_hours=context.parameters.daily_hours,
    )
    sample = calculations.sample_share(
        [
            calculations.SampleCounts(
                working=view.working, transit=view.transit, stopped=view.stopped
            )
            for view in window.samples
        ]
    )
    stoppages = calculations.stoppage_summary([view.figures for view in window.stoppages])
    available_exact = sum(
        (Decimal(view.crew) * context.parameters.daily_hours for view in window.field_days),
        Decimal(0),
    )
    available = calculations.round_quantity(available_exact, 0)
    bands = _performance_bands(
        quantities, sample=sample, capacity=capacity, parameters=context.parameters
    )
    alerts, attentions = calculations.performance_alerts(bands)
    earned = sum((read.view.figures.earned_hours for read in approved), Decimal(0))
    project = context.lookups.projects.get(project_id) if project_id is not None else None
    return PerformanceBlock(
        project_id=project_id,
        project_code=project.code if project is not None else "",
        project_name=project.name if project is not None else "",
        company_id=company_id,
        company_name=(
            context.lookups.companies.get(company_id, "") if company_id is not None else ""
        ),
        quantities=quantities,
        capacity=capacity,
        sample=sample,
        stoppages=stoppages,
        schedule=calculations.schedule_trend(
            _performance_planned_hours(approved), earned, cut_week=context.cut_week
        ),
        available_hh=available,
        stoppage_share=calculations.stoppage_share(stoppages.crew_hours, available_exact),
        bands=bands,
        alerts=alerts,
        attentions=attentions,
        trend=_performance_trend(
            context, approved=approved, project_id=project_id, company_id=company_id
        ),
        action=_open_performance_action(
            context.session,
            user=context.user,
            project_id=project_id,
            company_id=company_id,
            cut_week=context.cut_week,
            reference_date=context.reference_date,
        ),
    )


def _performance_bands(
    quantities: calculations.QuantityIndicators,
    *,
    sample: calculations.SampleShare,
    capacity: calculations.CapacitySummary,
    parameters: ProductivityParameters,
) -> calculations.PerformanceBands:
    return calculations.PerformanceBands(
        adherence=calculations.indicator_band(
            quantities.window_adherence, parameters.adherence_bands, higher_is_better=True
        ),
        pf=calculations.indicator_band(
            quantities.pf_window, parameters.pf_bands, higher_is_better=False
        ),
        spi=calculations.indicator_band(
            quantities.spi, parameters.spi_bands, higher_is_better=True
        ),
        working=calculations.working_band(sample.working_pct, target=parameters.working_pct),
        utilization=calculations.utilization_band(
            capacity.utilization, target=parameters.utilization_pct
        ),
    )


def _performance_planned_hours(
    approved: Sequence[_ItemRead],
) -> tuple[calculations.PlannedHours, ...]:
    """O previsto da LB somado por semana, em horas ganhas: a base do SPI(t) agregado."""
    hours: dict[str, Decimal] = {}
    for read in approved:
        for line in read.planned:
            hours[line.week] = hours.get(line.week, Decimal(0)) + line.planned * read.view.index_hh
    return tuple(calculations.PlannedHours(week=week, hours=hours[week]) for week in sorted(hours))


def _performance_field_records(
    context: _PerformanceContext,
    *,
    project_id: int | None,
    company_id: int | None,
    start: date | None,
    end: date | None,
    week: str | None,
) -> _HoursRecords:
    def keep(record: FieldDay | WorkSample | Stoppage) -> bool:
        if project_id is not None and record.project_id != project_id:
            return False
        if company_id is not None and record.company_id != company_id:
            return False
        if start is not None and record.day < start:
            return False
        if end is not None and record.day > end:
            return False
        return week is None or calendario.iso_week(record.day) == week

    records = context.hours_records
    return (
        [record for record in records[0] if keep(record)],
        [record for record in records[1] if keep(record)],
        [record for record in records[2] if keep(record)],
    )


def _performance_field(
    context: _PerformanceContext,
    *,
    project_id: int | None,
    company_id: int | None,
    start: date | None = None,
    end: date | None = None,
    week: str | None = None,
) -> _PerformanceField:
    records = _performance_field_records(
        context,
        project_id=project_id,
        company_id=company_id,
        start=start,
        end=end,
        week=week,
    )
    return _PerformanceField(
        field_days=tuple(
            _field_day_views(records[0], context.hours_lookups, parameters=context.parameters)
        ),
        samples=tuple(_sample_views(records[1], context.hours_lookups)),
        stoppages=tuple(_stoppage_views(records[2], context.hours_lookups)),
    )


def _performance_trend(
    context: _PerformanceContext,
    *,
    approved: Sequence[_ItemRead],
    project_id: int | None,
    company_id: int | None,
) -> tuple[calculations.TrendWeek, ...]:
    """A tendência semanal por empresa: FP, aderência, % trabalhando e CP de cada semana."""
    rows: dict[str, calculations.TrendInput] = {}
    for week in context.trend_weeks:
        data = _performance_trend_input(
            context, week=week, approved=approved, project_id=project_id, company_id=company_id
        )
        if data is not None:
            rows[week] = data
    return calculations.weekly_trend(context.trend_weeks, rows)


def _performance_trend_input(
    context: _PerformanceContext,
    *,
    week: str,
    approved: Sequence[_ItemRead],
    project_id: int | None,
    company_id: int | None,
) -> calculations.TrendInput | None:
    appropriated = Decimal(0)
    earned = Decimal(0)
    planned = Decimal(0)
    capped = Decimal(0)
    has_entry = False
    for read in approved:
        entry = next((line for line in read.reported if line.week == week), None)
        if entry is None:
            continue
        has_entry = True
        planned_week = next(
            (line.planned for line in read.planned if line.week == week), Decimal(0)
        )
        appropriated += entry.hh
        earned += entry.realized * read.view.index_hh
        planned += planned_week * read.view.index_hh
        capped += min(entry.realized, planned_week) * read.view.index_hh
    field = _performance_field(context, project_id=project_id, company_id=company_id, week=week)
    share = calculations.sample_share(
        [
            calculations.SampleCounts(
                working=view.working, transit=view.transit, stopped=view.stopped
            )
            for view in field.samples
        ]
    )
    if not has_entry and not field.field_days and not field.samples:
        return None
    return calculations.TrendInput(
        appropriated=appropriated,
        earned=earned,
        planned=planned,
        capped=capped,
        working=share.working,
        transit=share.transit,
        stopped=share.stopped,
        capacities=tuple(view.figures.capacity for view in field.field_days),
    )


def _performance_charts(
    context: _PerformanceContext, *, companies: Sequence[PerformanceBlock]
) -> tuple[dict[str, Any], dict[str, Any]]:
    adherence = [
        calculations.TrendSeries(
            label=block.label, ratios=tuple(row.adherence_ratio for row in block.trend)
        )
        for block in companies
    ]
    working = [
        calculations.TrendSeries(
            label=block.label, ratios=tuple(row.working_ratio for row in block.trend)
        )
        for block in companies
    ]
    return (
        calculations.ratio_chart(
            "Aderência semanal por empresa",
            weeks=context.trend_weeks,
            series=adherence,
            target=context.parameters.adherence_bands[1],
            target_label="Meta",
        ),
        calculations.ratio_chart(
            "% trabalhando por empresa",
            weeks=context.trend_weeks,
            series=working,
            target=context.parameters.working_pct,
            target_label="Meta",
        ),
    )


def _open_performance_action(
    session: Session,
    *,
    user: User,
    project_id: int | None,
    company_id: int | None,
    cut_week: str,
    reference_date: date,
) -> PerformanceActionRef | None:
    """A ação aberta da empresa na semana do corte, se houver (uma por empresa e semana)."""
    if project_id is None or company_id is None:
        return None
    from src.modulos.central_acoes import calculations as central_calculations
    from src.modulos.central_acoes import service as central_service
    from src.modulos.central_acoes.validation import ActionFilters

    reference = calculations.performance_action_reference(company_id, cut_week)
    listing = central_service.list_actions(
        session,
        user=user,
        scope=Scope(project_id=project_id, source="url"),
        filters=ActionFilters(
            search=reference,
            origin=calculations.PERFORMANCE_ORIGIN,
            status=central_calculations.StatusFilter.ALL,
        ),
        reference_date=reference_date,
    )
    found = next(
        (
            row.record
            for row in listing.rows
            if row.record.origin_ref == reference
            and row.record.status is not central_calculations.ActionStatus.COMPLETED
        ),
        None,
    )
    if found is None:
        return None
    return PerformanceActionRef(
        reference=reference,
        url=origin_links.link_to_screen("central_acoes/acoes", busca=reference),
    )


def performance_action_form(
    session: Session,
    *,
    user: User,
    block: PerformanceBlock,
    cut_week: str,
    window_weeks: int,
    form: validation.ActionPlanForm | None = None,
    reference_date: date,
    errors: Mapping[str, str] | None = None,
) -> PerformanceFormView:
    """O formulário do plano de ação: sugerido pelos indicadores da empresa, ou com o digitado."""
    rbac.require_module(user, MODULE)
    return PerformanceFormView(
        fields=_action_plan_fields(
            block,
            cut_week=cut_week,
            window_weeks=window_weeks,
            form=form,
            reference_date=reference_date,
        ),
        options=PerformanceFormOptions(
            companies=tuple(configuracoes.list_company_options(session)),
            people=tuple(configuracoes.list_person_options(session)),
        ),
        errors=errors or {},
        block=block,
    )


def _action_plan_fields(
    block: PerformanceBlock,
    *,
    cut_week: str,
    window_weeks: int,
    form: validation.ActionPlanForm | None,
    reference_date: date,
) -> dict[str, str]:
    if form is not None:
        return dict(form.fields)
    points = "; ".join(_indicator_suggestion(key, block) for key in block.attention_keys)
    subject = (
        f"Recuperar a produtividade: {block.company_name} ({_short_week(cut_week, reference_date)})"
    )
    description = (
        f"Indicadores fora da faixa na janela de avaliação ({window_weeks} semanas): {points}. "
        "Causas principais e contramedidas a definir com a contratada."
    )
    return {
        validation.FIELD_PLAN_COMPANY: ("" if block.company_id is None else str(block.company_id)),
        validation.FIELD_PLAN_SUBJECT: subject,
        validation.FIELD_PLAN_DESCRIPTION: description,
        validation.FIELD_PLAN_RESPONSIBLE: "",
        validation.FIELD_PLAN_DATE: calendario.add_days(
            reference_date, PERFORMANCE_ACTION_DAYS
        ).isoformat(),
    }


def _indicator_suggestion(key: str, block: PerformanceBlock) -> str:
    """O indicador fora da faixa como o texto sugerido do plano o escreve."""
    if key == "adherence":
        value = f"{_plain_number(block.quantities.window_adherence, 0)}%"
    elif key == "pf":
        value = _plain_number(block.quantities.pf_window, 2)
    elif key == "spi":
        value = _plain_number(block.quantities.spi, 2)
    elif key == "working":
        value = f"{_plain_number(block.sample.working_pct, 1)}%"
    else:
        value = f"{_plain_number(block.capacity.utilization, 1)}%"
    return f"{INDICATOR_LABELS[key]} {value}"


def _plain_number(value: Decimal | None, places: int) -> str:
    if value is None:
        return "·"
    return f"{value:.{places}f}".replace(".", ",")


def _short_week(week: str, reference_date: date) -> str:
    """A semana curta como a tela a lê: ``S39``, com o sufixo do ano quando muda."""
    year, _, number = week.partition("-S")
    short = f"S{number}"
    return short if year == str(reference_date.year) else f"{short}/{year[2:]}"


def _action_plan_choices(session: Session) -> validation.ActionPlanChoices:
    """As escolhas do plano: as empresas e as pessoas do cadastro."""
    return validation.ActionPlanChoices(
        company_ids=frozenset(option.id for option in configuracoes.list_company_options(session)),
        person_ids=frozenset(option.id for option in configuracoes.list_person_options(session)),
    )


def create_performance_action(
    session: Session,
    *,
    user: User,
    scope: Scope,
    form: validation.ActionPlanForm,
    cut_week: str,
    reference_date: date,
) -> PerformanceActionRef:
    """Cria o plano de ação na Central, pela costura única (D9), uma ação aberta por semana.

    A referência é a semana e a empresa (``PRD-2026-S39-01``); a segunda tentativa da mesma
    empresa e semana é recusada com 422. A ação nasce no projeto do escopo, no grupo
    Produtividade, com o item seguinte da referência.
    """
    rbac.require(user, Permission.WRITE)
    from src.modulos.central_acoes import service as central_service
    from src.modulos.central_acoes.validation import NewAction

    data = validation.parse_action_plan(
        form, _action_plan_choices(session), reference_date=reference_date
    )
    project_id = scope.require_project()
    resolved = _cut_week(cut_week, calendario.iso_week(reference_date))
    if (
        _open_performance_action(
            session,
            user=user,
            project_id=project_id,
            company_id=data.company_id,
            cut_week=resolved,
            reference_date=reference_date,
        )
        is not None
    ):
        raise InvalidDataError(ACTION_ALREADY_OPEN_MESSAGE)
    reference = calculations.performance_action_reference(data.company_id, resolved)
    central_service.create_action(
        session,
        user=user,
        new=NewAction(
            project_id=project_id,
            origin=calculations.PERFORMANCE_ORIGIN,
            origin_ref=reference,
            subject=data.subject,
            description=data.description,
            requester_id=user.person_id,
            responsible_id=data.responsible_id,
            planned_date=data.planned_date,
            group=PERFORMANCE_ACTION_GROUP,
            item=central_service.next_origin_item(
                session, origin_kind=calculations.PERFORMANCE_ORIGIN, reference=reference
            ),
        ),
        reference_date=reference_date,
    )
    return PerformanceActionRef(
        reference=reference,
        url=origin_links.link_to_screen("central_acoes/acoes", busca=reference),
    )


def _performance_action_link(reference: origin_links.OriginRef) -> str | None:
    """O endereço de volta da ação da Central: a aba KPIs com a empresa e a semana."""
    parts = calculations.performance_action_parts(reference.reference)
    if parts is None:
        return None
    cut_week, company_id = parts
    return origin_links.link_to_screen(
        "planejamento/produtividade", aba="kpis", empresa=company_id, corte=cut_week
    )


origin_links.register(
    origin_links.OriginLinkType(
        kind=calculations.PERFORMANCE_ORIGIN, build=_performance_action_link
    )
)
