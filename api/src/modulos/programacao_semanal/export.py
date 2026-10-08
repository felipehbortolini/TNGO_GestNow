"""Exports of the Weekly scheduling: the governance, the week, the dashboard (D12).

One ``Document`` feeds both outputs (``core.excel`` and ``core.printable``): the four
indicators of the panel, the control list by company and week and the queue of change
requests, pending and decided. In the Portfólio every row carries its project and the
generic layer opens the ``Projeto`` column (HU-016). The trail stays on the screen,
as in the app: the audit has its own screen reading, not an export.

The week has two documents (ISSUE-055): ``week_document`` is the app's workbook, with
its sheets — Resumo, Programação, Por contratada, Por frente, Por encarregado, Dia a
dia and Curva S —, and ``week_report_document`` is the app's printed sheet, with the
indicators, the matrix and the breakdowns of the paper. The two share the matrix, the
breakdowns and the day by day: neither is a raw dump.

The dashboard (ISSUE-056) has one document for both outputs: ``dashboard_document``
carries the indicators, the charts of the Design System library (the printable draws
them from ``data-grafico``/``data-dados``; the Excel has the numbers behind each one
as a table) and the tables of the rankings, the heatmap, the shifts and the
bottlenecks. ``dashboard_charts`` is the same tuple the screen mounts, so paper and
screen never drift apart.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
    Chart,
    Column,
    Document,
    Kpi,
    Paper,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.programacao_semanal import calculations, weeks
from src.modulos.programacao_semanal.service import (
    DashboardData,
    ScheduleParameters,
    WeekSummary,
)
from src.modulos.programacao_semanal.views import (
    ActivityView,
    ChangeRequestView,
    GovernancePanel,
    RequestQueue,
)

GOVERNANCE_TITLE = "Governança da programação"
CONTROL_TITLE = "Lista de controle"
QUEUE_TITLE = "Pedidos de alteração"

WEEK_TITLE = "Programação da semana"
SCHEDULE_TITLE = "Programação"
DAILY_TITLE = "Dia a dia"
CURVE_TITLE = "Curva S"
DASH = "—"

DASHBOARD_TITLE = "Dashboard da programação"
DASHBOARD_CURVE_TITLE = "Curva S do avanço"
DASHBOARD_WEEKLY_TITLE = "Previsto contra realizado"
DASHBOARD_ADHERENCE_TITLE = "Evolução da aderência por contratada"
DASHBOARD_HEATMAP_TITLE = "Mapa de calor — dia por frente"
DASHBOARD_DAILY_TITLE = "Produção por dia"
DASHBOARD_BOTTLENECK_TITLE = "O que travou a semana"

# (título da tabela, cabeçalho da coluna) de cada ranking do dashboard.
DASHBOARD_RANKINGS = {
    "company": ("Ranking por contratada", "Contratada"),
    "location": ("Ranking por frente", "Frente"),
    "foreman": ("Ranking por encarregado", "Encarregado"),
}

# (título da aba, cabeçalho da coluna) de cada quebra do app.
BREAKDOWNS = {
    "company": ("Por contratada", "Contratada"),
    "location": ("Por frente", "Frente"),
    "foreman": ("Por encarregado", "Encarregado"),
}

REQUEST_TONES = {
    "pendente": Tone.WARN,
    "aplicado": Tone.OK,
    "rejeitado": Tone.NEUTRAL,
}


def governance_document(
    panel: GovernancePanel,
    queue: RequestQueue,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The governance screen as a document: the indicators, the control list and the queue."""
    return Document(
        title=GOVERNANCE_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Semana de referência", panel.reference_week),),
        kpis=_kpis(panel),
        tables=(_control_table(panel), _queue_table(queue)),
        paper=Paper.A4,
    )


def _kpis(panel: GovernancePanel) -> tuple[Kpi, ...]:
    return (
        Kpi(
            "Contratadas ativas",
            panel.active_companies,
            "Contratadas com atividade no histórico",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Janelas abertas hoje",
            panel.open_windows,
            f"Na semana {panel.reference_week}",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Aguardando fiscal",
            panel.situations.pending,
            "Realizado lançado sem aprovação",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Atividades no histórico",
            panel.situations.total,
            "Todas as semanas",
            kind=ValueKind.INTEGER,
        ),
    )


def _control_table(panel: GovernancePanel) -> Table:
    return Table(
        title=CONTROL_TITLE,
        columns=(
            Column("Contratada", width=24),
            Column("Semana"),
            Column("Programações", ValueKind.INTEGER),
            Column("Em elaboração", ValueKind.INTEGER),
            Column("Validadas", ValueKind.INTEGER),
            Column("Publicadas", ValueKind.INTEGER),
            Column("Pendências", ValueKind.INTEGER),
            Column("Aderência", ValueKind.PERCENT, digits=0),
            Column("Fiscal", width=24),
            Column("Última alteração", width=20),
        ),
        rows=tuple(
            row(
                line.company,
                line.week,
                line.total,
                line.draft,
                line.validated,
                line.published,
                line.pending,
                line.adherence,
                line.inspector or "—",
                line.updated_at_text or "—",
                project=line.project_label,
            )
            for line in panel.lines
        ),
    )


def _queue_table(queue: RequestQueue) -> Table:
    return Table(
        title=QUEUE_TITLE,
        columns=(
            Column("ID exclusiva"),
            Column("Contratada", width=24),
            Column("Semana"),
            Column("Motivo", width=60),
            Column("Situação", width=20),
            Column("Solicitado por", width=24),
            Column("Solicitado em", width=18),
            Column("Decidido por", width=24),
            Column("Decidido em", width=18),
            Column("Resposta", width=60),
        ),
        rows=tuple(_queue_row(view) for view in (*queue.pending, *queue.resolved)),
    )


def _queue_row(view: ChangeRequestView) -> Row:
    return row(
        view.unique_id,
        view.company,
        view.week,
        view.reason,
        Cell(view.situation, REQUEST_TONES.get(view.situation)),
        view.requested_by,
        view.requested_at_text,
        view.decided_by,
        view.decided_at_text,
        view.answer,
        project=view.project_label,
    )


# ── The week: the workbook and the printed sheet (ISSUE-055) ─────────────


def week_document(
    week: str,
    views: list[ActivityView],
    summary: WeekSummary,
    curve: list[calculations.CurvePoint],
    parameters: ScheduleParameters,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The app's workbook: the summary, the matrix, the breakdowns, the day by day and the curve."""
    return Document(
        title=f"{WEEK_TITLE} {week}",
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Semana", week), ("Período", weeks.period_label(week))),
        kpis=_week_kpis(views, summary, parameters),
        tables=(
            _schedule_table(views),
            _breakdown_table("company", views),
            _breakdown_table("location", views),
            _breakdown_table("foreman", views),
            _daily_table(views),
            _curve_table(curve),
        ),
        paper=Paper.A4,
    )


def week_report_document(
    week: str,
    views: list[ActivityView],
    summary: WeekSummary,
    parameters: ScheduleParameters,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The app's printed sheet: the four indicators, the matrix and the breakdowns of the paper."""
    return Document(
        title=f"{WEEK_TITLE} {week}",
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Semana", week), ("Período", weeks.period_label(week))),
        kpis=_report_kpis(views, summary, parameters),
        tables=(
            _schedule_table(views),
            _breakdown_table("company", views),
            _breakdown_table("location", views),
            _daily_table(views),
        ),
        paper=Paper.A4,
    )


def _week_kpis(
    views: list[ActivityView], summary: WeekSummary, parameters: ScheduleParameters
) -> tuple[Kpi, ...]:
    """The app's cover: the indicators, the situation counts and the reference of each one."""
    situations = _situation_counts(views)
    return (
        Kpi(
            "Aderência geral",
            summary.adherence,
            f"meta {parameters.adherence_target:g}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=_meets(summary.adherence, parameters.adherence_target, Tone.OK, Tone.ERROR),
        ),
        Kpi(
            "PPC médio",
            summary.mean_ppc,
            f"meta {parameters.ppc_target:g}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=_meets(summary.mean_ppc, parameters.ppc_target, Tone.OK, Tone.WARN),
        ),
        Kpi("Atividades", summary.total, "na semana", kind=ValueKind.INTEGER),
        Kpi("Contratadas", _distinct(views, "company"), "com programação", kind=ValueKind.INTEGER),
        Kpi("Frentes", _distinct(views, "location"), "ativas", kind=ValueKind.INTEGER),
        Kpi(
            "Realizados pendentes",
            summary.awaiting_inspector,
            "aguardando o fiscal",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Em elaboração",
            situations[calculations.SITUATION_DRAFT],
            "na semana",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Validada",
            situations[calculations.SITUATION_VALIDATED],
            "na semana",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Publicada",
            situations[calculations.SITUATION_PUBLISHED],
            "na semana",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Realizado aprovado",
            situations[calculations.APPROVAL_APPROVED],
            "na semana",
            kind=ValueKind.INTEGER,
        ),
        Kpi("Sem realizado", situations["sem_realizado"], "na semana", kind=ValueKind.INTEGER),
    )


def _report_kpis(
    views: list[ActivityView], summary: WeekSummary, parameters: ScheduleParameters
) -> tuple[Kpi, ...]:
    """The four indicators the app's sheet leads with."""
    return (
        Kpi(
            "Aderência",
            summary.adherence,
            f"meta {parameters.adherence_target:g}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=_meets(summary.adherence, parameters.adherence_target, Tone.OK, Tone.ERROR),
        ),
        Kpi(
            "PPC médio",
            summary.mean_ppc,
            f"meta {parameters.ppc_target:g}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=_meets(summary.mean_ppc, parameters.ppc_target, Tone.OK, Tone.WARN),
        ),
        Kpi("Atividades", summary.total, "na semana", kind=ValueKind.INTEGER),
        Kpi("Contratadas", _distinct(views, "company"), "com programação", kind=ValueKind.INTEGER),
    )


def _meets(value: float, target: float, reached: Tone, missed: Tone) -> Tone:
    return reached if value >= target else missed


def _distinct(views: list[ActivityView], attribute: str) -> int:
    return len({getattr(view, attribute) for view in views if getattr(view, attribute)})


def _situation_counts(views: list[ActivityView]) -> dict[str, int]:
    """How many activities of the week are in each state, with the app's reading of pending."""
    return {
        calculations.SITUATION_DRAFT: sum(
            1 for view in views if view.situation == calculations.SITUATION_DRAFT
        ),
        calculations.SITUATION_VALIDATED: sum(
            1 for view in views if view.situation == calculations.SITUATION_VALIDATED
        ),
        calculations.SITUATION_PUBLISHED: sum(
            1 for view in views if view.situation == calculations.SITUATION_PUBLISHED
        ),
        calculations.APPROVAL_APPROVED: sum(
            1 for view in views if view.approval == calculations.APPROVAL_APPROVED
        ),
        "sem_realizado": sum(1 for view in views if not view.figures.has_done),
    }


def _schedule_table(views: list[ActivityView]) -> Table:
    """The app's ``Programação`` sheet: two lines per activity, the plan and the done work."""
    columns = (
        Column("Item", width=7),
        Column("ID Exclusiva", width=16),
        Column("Atividade", width=46),
        Column("Local", width=20),
        Column("Empresa", width=18),
        Column("Encarregado", width=22),
        Column("Fiscal", width=18),
        Column("Prev/Real", width=10),
        *(Column(label, ValueKind.DECIMAL, width=10) for label in calculations.DAY_LABELS),
        Column("Total", ValueKind.DECIMAL, width=12),
        Column("Unidade", width=10),
        Column("PPC %", ValueKind.PERCENT, digits=1, width=9),
        Column("Situação", width=15),
        Column("Realizado", width=13),
    )
    rows: list[Row] = []
    for view in views:
        rows.append(_planned_row(view))
        rows.append(_done_row(view))
    return Table(SCHEDULE_TITLE, columns, rows=tuple(rows))


def _planned_row(view: ActivityView) -> Row:
    return row(
        f"{view.item:02d}",
        view.unique_id,
        view.description,
        view.location,
        view.company,
        view.foreman or DASH,
        view.inspector or DASH,
        "Previsto",
        *(round(value, 2) for value in view.figures.planned_days),
        view.figures.planned_total,
        view.unit,
        None,
        calculations.SITUATION_LABELS.get(view.situation, view.situation),
        calculations.APPROVAL_LABELS.get(view.approval, view.approval),
        project=view.project_label,
    )


def _done_row(view: ActivityView) -> Row:
    return row(
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "Realizado",
        *view.figures.day_totals,
        view.figures.done_total,
        view.unit,
        view.figures.ppc,
        "",
        "",
        project=view.project_label,
    )


def _breakdown_table(attribute: str, views: list[ActivityView]) -> Table:
    """One breakdown of the app: the group, its activities, the totals, the adherence and the PPC."""
    title, header = BREAKDOWNS[attribute]
    return Table(
        title=title,
        columns=(
            Column(header, width=30),
            Column("Atividades", ValueKind.INTEGER),
            Column("Previsto", ValueKind.DECIMAL),
            Column("Realizado", ValueKind.DECIMAL),
            Column("Aderência %", ValueKind.PERCENT, digits=1),
            Column("PPC médio %", ValueKind.PERCENT, digits=1),
            Column("Pendências", ValueKind.INTEGER),
        ),
        rows=tuple(_breakdown_rows(attribute, views)),
        per_project=False,
    )


def _breakdown_rows(attribute: str, views: list[ActivityView]) -> list[Row]:
    """The groups sorted by adherence, worst first: a breakdown exists to show where to act."""
    groups: dict[str, list[ActivityView]] = {}
    for view in views:
        groups.setdefault(str(getattr(view, attribute) or DASH), []).append(view)
    lines: list[tuple[float, Row]] = []
    for key, items in groups.items():
        figures = [item.figures for item in items]
        adherence = calculations.schedule_adherence(figures)
        lines.append(
            (
                adherence,
                row(
                    key,
                    len(items),
                    round(sum(item.planned_total for item in figures), 2),
                    round(sum(item.done_total for item in figures), 2),
                    adherence,
                    calculations.mean_ppc(figures),
                    sum(1 for item in items if item.approval == calculations.APPROVAL_PENDING),
                ),
            )
        )
    lines.sort(key=lambda line: line[0])
    return [line for _, line in lines]


def _daily_table(views: list[ActivityView]) -> Table:
    """The app's ``Dia a dia`` sheet: the plan and both shifts, day by day."""
    return Table(
        title=DAILY_TITLE,
        columns=(
            Column("Dia", width=14),
            Column("Previsto", ValueKind.DECIMAL),
            Column("Realizado dia", ValueKind.DECIMAL),
            Column("Realizado noite", ValueKind.DECIMAL),
            Column("Realizado total", ValueKind.DECIMAL),
            Column("Aderência %", ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(_daily_rows(views)),
        per_project=False,
    )


def _daily_rows(views: list[ActivityView]) -> list[Row]:
    lines = []
    for index in range(calculations.DAYS):
        planned = round(sum(view.figures.planned_days[index] for view in views), 2)
        day = round(sum(view.figures.day_shift[index] for view in views), 2)
        night = round(sum(view.figures.night_shift[index] for view in views), 2)
        total = round(day + night, 2)
        adherence = round(total / planned * 100, 1) if planned else 0.0
        lines.append(row(calculations.DAY_NAMES[index], planned, day, night, total, adherence))
    return lines


def _curve_table(curve: list[calculations.CurvePoint]) -> Table:
    """The app's ``Curva S`` sheet: the three series of the horizon and their running totals."""
    return Table(
        title=CURVE_TITLE,
        columns=(
            Column("Semana", width=14),
            Column("Período", width=24),
            Column("Base %", ValueKind.PERCENT, digits=2),
            Column("Previsto %", ValueKind.PERCENT, digits=2),
            Column("Realizado %", ValueKind.PERCENT, digits=2),
            Column("Base acum. %", ValueKind.PERCENT, digits=2),
            Column("Previsto acum. %", ValueKind.PERCENT, digits=2),
            Column("Realizado acum. %", ValueKind.PERCENT, digits=2),
        ),
        rows=tuple(
            row(
                point.week,
                point.period,
                point.base,
                point.planned,
                point.done,
                point.base_accumulated,
                point.planned_accumulated,
                point.done_accumulated,
            )
            for point in curve
        ),
        per_project=False,
    )


# ── The dashboard: the charts and the document (ISSUE-056) ───────────────
#
# The same builders feed the screen and the printable, so the numbers on paper are
# the ones of the screen. The curve and the weekly chart send the quantity of each
# week; the evolution sends the pair (num, den) of the adherence, because the rate
# of a month is the sum of the done over the sum of the planned of its weeks and
# never the mean of the weekly rates (D11).


def _chart_period(week: str, values: dict[str, object]) -> dict[str, object] | None:
    """One week of a chart: the calendar decided here and the values by series id."""
    info = weeks.describe(week)
    if info.first_day is None:
        return None
    return {
        "ano": info.year,
        "mes": info.first_day.month,
        "semana": info.number,
        "valores": values,
    }


def _periods(
    points: list[dict[str, object] | None],
) -> list[dict[str, object]]:
    return [point for point in points if point is not None]


def curve_chart(data: DashboardData) -> Chart:
    """The S-curve of the advancement: base, planned and done accumulated, in percent."""
    return Chart(
        DASHBOARD_CURVE_TITLE,
        "curva-s-linha",
        {
            "titulo": DASHBOARD_CURVE_TITLE,
            "modo": "acumulado",
            "formato": "pct",
            "unidade": "%",
            "casas": 1,
            "eixo_max": 100,
            "series": [
                {"id": "base", "rotulo": "Base", "papel": "linha-base", "tipo": "valor"},
                {"id": "previsto", "rotulo": "Previsto", "papel": "previsto", "tipo": "valor"},
                {"id": "realizado", "rotulo": "Realizado", "papel": "realizado", "tipo": "valor"},
            ],
            "periodos": _periods(
                [
                    _chart_period(
                        point.week,
                        {
                            "base": point.base_accumulated,
                            "previsto": point.planned_accumulated,
                            "realizado": point.done_accumulated,
                        },
                    )
                    for point in data.curve
                ]
            ),
        },
    )


def weekly_chart(data: DashboardData) -> Chart:
    """Planned against done of each week, in percentage points of the horizon scope."""
    return Chart(
        DASHBOARD_WEEKLY_TITLE,
        "curva-s-barra-linha",
        {
            "titulo": DASHBOARD_WEEKLY_TITLE,
            "modo": "periodo",
            "formato": "pct",
            "unidade": "%",
            "casas": 1,
            "eixo_max": 100,
            "series": [
                {"id": "previsto", "rotulo": "Previsto", "papel": "previsto", "tipo": "valor"},
                {"id": "realizado", "rotulo": "Realizado", "papel": "realizado", "tipo": "valor"},
            ],
            "periodos": _periods(
                [
                    _chart_period(
                        point.week,
                        {"previsto": point.planned, "realizado": point.done},
                    )
                    for point in data.curve
                ]
            ),
        },
    )


def adherence_chart(data: DashboardData) -> Chart:
    """Adherence by contractor, week by week: a line per company and the target dashed.

    Each week carries the pair of the company — the done and the planned — and the
    target rides as a pair too, so the visual divides the sums at any grouping level.
    """
    identifiers = {
        company: f"serie-{index + 1}" for index, company in enumerate(data.evolution.series)
    }
    series: list[dict[str, object]] = [
        {"id": identifiers[company], "rotulo": company, "tipo": "razao"}
        for company in data.evolution.series
    ]
    series.append({"id": "meta", "rotulo": "Meta", "papel": "linha-base", "tipo": "razao"})
    target = data.parameters.adherence_target
    return Chart(
        DASHBOARD_ADHERENCE_TITLE,
        "curva-s-linha",
        {
            "titulo": DASHBOARD_ADHERENCE_TITLE,
            "modo": "periodo",
            "formato": "pct",
            "unidade": "%",
            "casas": 1,
            "casas_dica": 1,
            "eixo_max": 100,
            "series": series,
            "periodos": _periods(
                [
                    _chart_period(
                        point.week,
                        {
                            **{
                                identifiers[company]: {
                                    "num": total.done,
                                    "den": total.planned,
                                }
                                for company, total in point.totals.items()
                            },
                            "meta": {"num": target, "den": 100.0},
                        },
                    )
                    for point in data.evolution.points
                ]
            ),
        },
    )


def status_chart(block: calculations.StatusBlock) -> Chart:
    """One reading of the week as a strip of KPIs with state (HTML KPI Status)."""
    return Chart(
        block.title,
        "kpi-status",
        {
            "titulo": block.title,
            "itens": [
                {
                    "id": segment.key,
                    "rotulo": segment.label,
                    "valor": segment.value,
                    "tom": segment.tone,
                }
                for segment in block.segments
            ],
        },
    )


def heatmap_chart(data: DashboardData) -> Chart:
    """The day-by-front heatmap: the delivered share of each day, painted by the bands."""
    return Chart(
        DASHBOARD_HEATMAP_TITLE,
        "tabela-heatmap",
        {
            "titulo": DASHBOARD_HEATMAP_TITLE,
            "rotulo_linhas": "Frente",
            "casas": 1,
            "unidade": "%",
            "colunas": [
                {"id": f"dia-{index}", "rotulo": label}
                for index, label in enumerate(data.heatmap.columns)
            ],
            "linhas": [
                {
                    "id": f"frente-{index}",
                    "rotulo": row.label,
                    "valores": {f"dia-{day}": cell.percent for day, cell in enumerate(row.cells)},
                }
                for index, row in enumerate(data.heatmap.rows)
            ],
            "faixas": list(calculations.heat_faixas()),
        },
    )


def daily_chart(data: DashboardData) -> Chart:
    """The plan against the delivery of each weekday, in quantities of the week."""
    categories = [
        {
            "id": f"dia-{index}",
            "rotulo": shift.label,
            "papel": "neutro",
            "favoravel": "sobe",
        }
        for index, shift in enumerate(data.shifts)
    ]
    return Chart(
        DASHBOARD_DAILY_TITLE,
        "comparativo-barras",
        {
            "titulo": DASHBOARD_DAILY_TITLE,
            "paineis": [
                {
                    "titulo": "Previsto contra realizado por dia",
                    "categorias": categories,
                    "linhas": [
                        {
                            "rotulo": "Previsto",
                            "valores": {
                                f"dia-{index}": shift.planned
                                for index, shift in enumerate(data.shifts)
                            },
                        },
                        {
                            "rotulo": "Realizado",
                            "valores": {
                                f"dia-{index}": shift.done
                                for index, shift in enumerate(data.shifts)
                            },
                        },
                    ],
                }
            ],
        },
    )


def dashboard_charts(data: DashboardData) -> tuple[Chart, ...]:
    """The charts of the dashboard in the order of the screen: the same ones on paper."""
    return (
        adherence_chart(data),
        curve_chart(data),
        weekly_chart(data),
        *(status_chart(block) for block in data.status),
        heatmap_chart(data),
        daily_chart(data),
    )


def dashboard_document(
    data: DashboardData,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The dashboard as a document: the indicators, the charts and the numbers behind them."""
    return Document(
        title=DASHBOARD_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Semana", data.week), ("Período", data.period)),
        kpis=_dashboard_kpis(data),
        charts=dashboard_charts(data),
        tables=(
            _ranking_table(*DASHBOARD_RANKINGS["company"], data.by_company),
            _ranking_table(*DASHBOARD_RANKINGS["location"], data.by_location),
            _ranking_table(*DASHBOARD_RANKINGS["foreman"], data.by_foreman),
            _bottleneck_table(data.bottlenecks),
            _heatmap_table(data.heatmap),
            _shift_table(data.shifts),
            _curve_table(data.curve),
            _weekly_table(data.curve),
            _evolution_table(data.evolution),
        ),
        paper=Paper.A4,
    )


def _dashboard_kpis(data: DashboardData) -> tuple[Kpi, ...]:
    """The strip of the app: adherence, mean PPC, activities and contractors."""
    parameters = data.parameters
    summary = data.summary
    return (
        Kpi(
            "Aderência",
            summary.adherence,
            f"meta {parameters.adherence_target:g}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=_meets(summary.adherence, parameters.adherence_target, Tone.OK, Tone.ERROR),
        ),
        Kpi(
            "PPC médio",
            summary.mean_ppc,
            f"meta {parameters.ppc_target:g}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=_meets(summary.mean_ppc, parameters.ppc_target, Tone.OK, Tone.WARN),
        ),
        Kpi("Atividades", summary.total, "na semana", kind=ValueKind.INTEGER),
        Kpi("Contratadas", data.companies, "com programação", kind=ValueKind.INTEGER),
    )


def _ranking_table(title: str, header: str, lines: list[calculations.RankingLine]) -> Table:
    """One ranking of the dashboard: the group, its activities, the totals and the rates."""
    return Table(
        title=title,
        columns=(
            Column(header, width=30),
            Column("Atividades", ValueKind.INTEGER),
            Column("Previsto", ValueKind.DECIMAL),
            Column("Realizado", ValueKind.DECIMAL),
            Column("Aderência %", ValueKind.PERCENT, digits=1),
            Column("PPC médio %", ValueKind.PERCENT, digits=1),
            Column("Pendências", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                line.label,
                line.activities,
                line.planned,
                line.done,
                line.adherence,
                line.mean_ppc,
                line.pending,
            )
            for line in lines
        ),
        per_project=False,
    )


def _bottleneck_table(bottlenecks: list[calculations.Bottleneck]) -> Table:
    """The action list: the activities below the medium band, worst PPC first."""
    return Table(
        title=DASHBOARD_BOTTLENECK_TITLE,
        columns=(
            Column("ID exclusiva", width=16),
            Column("Atividade", width=40),
            Column("Contratada", width=20),
            Column("Frente", width=18),
            Column("Encarregado", width=20),
            Column("Previsto", ValueKind.DECIMAL),
            Column("Realizado", ValueKind.DECIMAL),
            Column("PPC %", ValueKind.PERCENT, digits=1),
            Column("Dias parados", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                item.identity,
                item.description,
                item.company,
                item.location or DASH,
                item.foreman or DASH,
                item.planned,
                item.done,
                item.ppc,
                item.idle_days,
                project=item.project_label,
            )
            for item in bottlenecks
        ),
    )


def _heatmap_table(heatmap: calculations.Heatmap) -> Table:
    """The numbers behind the heatmap: the delivered share of each day in each front."""
    return Table(
        title=DASHBOARD_HEATMAP_TITLE,
        columns=(
            Column("Frente", width=24),
            *(Column(label, ValueKind.PERCENT, digits=1) for label in heatmap.columns),
        ),
        rows=tuple(
            row(row_.label, *(cell.percent for cell in row_.cells)) for row_ in heatmap.rows
        ),
        per_project=False,
    )


def _shift_table(shifts: list[calculations.ShiftDay]) -> Table:
    """The shifts of the week, day by day: the plan, the day shift and the night shift."""
    return Table(
        title=DASHBOARD_DAILY_TITLE,
        columns=(
            Column("Dia", width=14),
            Column("Previsto", ValueKind.DECIMAL),
            Column("Turno dia", ValueKind.DECIMAL),
            Column("Turno noite", ValueKind.DECIMAL),
            Column("Realizado", ValueKind.DECIMAL),
            Column("Aderência %", ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(
            row(
                shift.name,
                shift.planned,
                shift.day_shift,
                shift.night_shift,
                shift.done,
                _ratio(shift.done, shift.planned),
            )
            for shift in shifts
        ),
        per_project=False,
    )


def _weekly_table(curve: list[calculations.CurvePoint]) -> Table:
    """The numbers behind the weekly chart: the planned and the done of each week."""
    return Table(
        title=DASHBOARD_WEEKLY_TITLE,
        columns=(
            Column("Semana", width=14),
            Column("Período", width=24),
            Column("Previsto %", ValueKind.PERCENT, digits=2),
            Column("Realizado %", ValueKind.PERCENT, digits=2),
        ),
        rows=tuple(row(point.week, point.period, point.planned, point.done) for point in curve),
        per_project=False,
    )


def _evolution_table(evolution: calculations.Evolution) -> Table:
    """The numbers behind the evolution: the adherence of each contractor in each week."""
    return Table(
        title=DASHBOARD_ADHERENCE_TITLE,
        columns=(
            Column("Semana", width=14),
            *(Column(company, ValueKind.PERCENT, digits=1) for company in evolution.series),
        ),
        rows=tuple(
            row(
                point.week,
                *(_ratio_of(point.totals.get(company)) for company in evolution.series),
            )
            for point in evolution.points
        ),
        per_project=False,
    )


def _ratio(done: float, planned: float) -> float | None:
    """The adherence of a pair, in percent; no plan means no rate."""
    if not planned:
        return None
    return round(done / planned * 100, 1)


def _ratio_of(total: calculations.CompanyWeek | None) -> float | None:
    if total is None:
        return None
    return _ratio(total.done, total.planned)
