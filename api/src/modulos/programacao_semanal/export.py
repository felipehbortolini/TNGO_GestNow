"""Exports of the Weekly scheduling: the governance, the week and the change requests (D12).

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
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
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
from src.modulos.programacao_semanal.service import ScheduleParameters, WeekSummary
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
