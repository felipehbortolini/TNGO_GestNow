"""The export of the screen Dashboards e KPIs: one ``Document`` for the Excel and the printable.

What the prototype exported leaves here: the five KPIs with their reference, the charts (status
by origin, open actions by responsible, status by project in the Portfólio, previstas x concluídas
by month) and the table Desempenho por responsável. The Excel has no chart, so the numbers behind
each chart go as tables of their own. The tables are aggregates: the project is a column of the
table itself (or the whole scope), never a per-row project.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
    CellValue,
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
from src.modulos.central_acoes.calculations import MonthCount, ResponsibleTally
from src.modulos.central_acoes.panel_service import (
    REPORT_ORIGIN_LABEL,
    Dashboard,
    ProjectLine,
    ResponsibleLine,
)

TITLE = "Central de Ações: dashboards e KPIs"
ORIGIN_LABEL = "Origem"

STATUS_SERIES = (
    {"id": "em_dia", "rotulo": "Em dia", "papel": "info"},
    {"id": "atrasadas", "rotulo": "Atrasadas", "papel": "erro"},
    {"id": "concluidas", "rotulo": "Concluídas", "papel": "ok"},
)
OPEN_SERIES = STATUS_SERIES[:2]
MONTH_NAMES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def month_label(month: str) -> str:
    """``2026-09`` as ``set/2026``, the way the chart and the table write the month."""
    year, _, number = month.partition("-")
    return f"{MONTH_NAMES[int(number) - 1]}/{year}"


def build_document(
    *,
    panel: Dashboard,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the panel for the origin filter in force."""
    tables = [_origin_table(panel)]
    if scope.is_portfolio:
        tables.append(_project_table(panel))
    tables.append(_responsible_table(panel))
    tables.append(_month_table(panel))
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=((ORIGIN_LABEL, panel.origin or REPORT_ORIGIN_LABEL),),
        kpis=_kpis(panel),
        charts=charts_of(panel, portfolio=scope.is_portfolio),
        tables=tuple(tables),
        paper=Paper.A4,
    )


def charts_of(panel: Dashboard, *, portfolio: bool) -> tuple[Chart, ...]:
    """The charts of the panel, in the order of the screen: the same ones the printable carries."""
    charts = [_origin_chart(panel), _responsible_chart(panel)]
    if portfolio:
        charts.append(_project_chart(panel))
    charts.append(_month_chart(panel))
    return tuple(charts)


def _kpis(panel: Dashboard) -> tuple[Kpi, ...]:
    counts = panel.counts
    share = panel.overdue_share
    on_planned = panel.on_planned_share
    return (
        Kpi(
            "Total de ações",
            counts.total,
            f"Referência: {panel.universe}",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status=f"{counts.open} em andamento",
        ),
        Kpi(
            "Em dia",
            counts.on_time,
            f"Esperado: {counts.open}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status="Prazo vigente ainda não venceu",
        ),
        Kpi(
            "Atrasadas",
            counts.overdue,
            "Meta: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if counts.overdue else Tone.OK,
            status="Sem atrasadas" if share is None else f"{share}% das abertas",
        ),
        Kpi(
            "Concluídas",
            counts.completed,
            f"Previsto: {panel.due_by_reference}",
            ValueKind.INTEGER,
            tone=Tone.OK,
            status="Com data de conclusão",
        ),
        Kpi(
            "Concluídas no prazo original",
            on_planned,
            "Esperado: 100%",
            ValueKind.PERCENT,
            digits=0,
            tone=None if on_planned is None else (Tone.OK if on_planned == 100 else Tone.WARN),
            status=f"{panel.completed_on_planned} de {counts.completed} sem replanejar",
        ),
    )


def _status_values(tally: ResponsibleTally) -> dict[str, int]:
    return {"em_dia": tally.on_time, "atrasadas": tally.overdue, "concluidas": tally.completed}


def _pareto(
    title: str, series: Sequence[dict[str, str]], categories: list[dict[str, object]]
) -> Chart:
    return Chart(
        title,
        "pareto",
        {
            "titulo": title,
            "eixo_esquerdo": "Nº de ações",
            "eixo_direito": "% acumulado",
            "status": list(series),
            "categorias": categories,
        },
    )


def _origin_chart(panel: Dashboard) -> Chart:
    return _pareto(
        "Status por origem",
        STATUS_SERIES,
        [{"rotulo": line.origin, "valores": _status_values(line.tally)} for line in panel.origins],
    )


def _responsible_chart(panel: Dashboard) -> Chart:
    return _pareto(
        "Ações abertas por responsável",
        OPEN_SERIES,
        [
            {"rotulo": line.name, "valores": _status_values(line.tally)}
            for line in panel.top_responsibles
        ],
    )


def _project_chart(panel: Dashboard) -> Chart:
    return _pareto(
        "Status por projeto",
        STATUS_SERIES,
        [{"rotulo": line.code, "valores": _status_values(line.tally)} for line in panel.projects],
    )


def _month_chart(panel: Dashboard) -> Chart:
    categories = [
        {"id": item.month, "rotulo": month_label(item.month), "papel": "neutro"}
        for item in panel.months
    ]
    return Chart(
        "Previstas x concluídas por mês",
        "comparativo-barras",
        {
            "titulo": "Previstas x concluídas por mês",
            "paineis": [
                {
                    "titulo": "Ações por mês",
                    "categorias": categories,
                    "linhas": [
                        {
                            "rotulo": "Previstas",
                            "valores": {item.month: item.planned for item in panel.months},
                        },
                        {
                            "rotulo": "Concluídas",
                            "valores": {item.month: item.completed for item in panel.months},
                        },
                    ],
                }
            ],
        },
    )


def _status_columns(first: Column) -> tuple[Column, ...]:
    return (
        first,
        Column("Em dia", ValueKind.INTEGER),
        Column("Atrasadas", ValueKind.INTEGER),
        Column("Concluídas", ValueKind.INTEGER),
        Column("Total", ValueKind.INTEGER),
    )


def _status_cells(tally: ResponsibleTally) -> tuple[Cell | CellValue, ...]:
    return (
        tally.on_time,
        Cell(tally.overdue, Tone.ERROR if tally.overdue else None),
        tally.completed,
        tally.total,
    )


def _origin_table(panel: Dashboard) -> Table:
    return Table(
        title="Status por origem",
        columns=_status_columns(Column(ORIGIN_LABEL, width=18)),
        rows=tuple(row(line.origin, *_status_cells(line.tally)) for line in panel.origins),
        per_project=False,
    )


def _project_table(panel: Dashboard) -> Table:
    def line_row(line: ProjectLine) -> Row:
        return row(line.label, *_status_cells(line.tally))

    return Table(
        title="Status por projeto",
        columns=_status_columns(Column("Projeto", width=36)),
        rows=tuple(line_row(line) for line in panel.projects),
        per_project=False,
    )


def _responsible_table(panel: Dashboard) -> Table:
    return Table(
        title="Desempenho por responsável",
        columns=(
            Column("Responsável", width=28),
            Column("Abertas", ValueKind.INTEGER),
            Column("Atrasadas", ValueKind.INTEGER),
            Column("% atrasadas", ValueKind.PERCENT, digits=0),
            Column("Concluídas", ValueKind.INTEGER),
            Column("Maior atraso (dias)", ValueKind.INTEGER),
        ),
        rows=tuple(_responsible_row(line) for line in panel.responsibles),
        per_project=False,
    )


def _responsible_row(line: ResponsibleLine) -> Row:
    tally = line.tally
    return row(
        line.name,
        tally.open,
        Cell(tally.overdue, Tone.ERROR if tally.overdue else None),
        tally.overdue_share,
        tally.completed,
        tally.longest_delay or None,
    )


def _month_table(panel: Dashboard) -> Table:
    def month_row(item: MonthCount) -> Row:
        return row(month_label(item.month), item.planned, item.completed)

    return Table(
        title="Previstas x concluídas por mês",
        columns=(
            Column("Mês", width=14),
            Column("Previstas", ValueKind.INTEGER),
            Column("Concluídas", ValueKind.INTEGER),
        ),
        rows=tuple(month_row(item) for item in panel.months),
        per_project=False,
    )
