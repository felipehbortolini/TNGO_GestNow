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

from src.core import translations
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


def _label(text: str, idioma: str) -> str:
    """O texto de interface da Central no idioma do request (D13)."""
    return translations.translate("central_acoes", text, idioma)


def _series(series: Sequence[dict[str, str]], idioma: str) -> list[dict[str, str]]:
    return [{**item, "rotulo": _label(item["rotulo"], idioma)} for item in series]


def month_label(month: str, idioma: str = "pt") -> str:
    """``2026-09`` as ``set/2026``, the way the chart and the table write the month."""
    year, _, number = month.partition("-")
    return f"{translations.mes_curto(int(number), idioma)}/{year}"


def build_document(
    *,
    panel: Dashboard,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """The document of the panel for the origin filter in force."""
    tables = [_origin_table(panel, idioma)]
    if scope.is_portfolio:
        tables.append(_project_table(panel, idioma))
    tables.append(_responsible_table(panel, idioma))
    tables.append(_month_table(panel, idioma))
    return Document(
        title=_label(TITLE, idioma),
        scope_label=describe_scope(scope, projects, idioma),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            (_label(ORIGIN_LABEL, idioma), panel.origin or _label(REPORT_ORIGIN_LABEL, idioma)),
        ),
        kpis=_kpis(panel, idioma),
        charts=charts_of(panel, portfolio=scope.is_portfolio, idioma=idioma),
        tables=tuple(tables),
        paper=Paper.A4,
        idioma=idioma,
    )


def charts_of(panel: Dashboard, *, portfolio: bool, idioma: str = "pt") -> tuple[Chart, ...]:
    """The charts of the panel, in the order of the screen: the same ones the printable carries."""
    charts = [_origin_chart(panel, idioma), _responsible_chart(panel, idioma)]
    if portfolio:
        charts.append(_project_chart(panel, idioma))
    charts.append(_month_chart(panel, idioma))
    return tuple(charts)


def _kpis(panel: Dashboard, idioma: str) -> tuple[Kpi, ...]:
    counts = panel.counts
    share = panel.overdue_share
    on_planned = panel.on_planned_share
    return (
        Kpi(
            _label("Total de ações", idioma),
            counts.total,
            _label("Referência: {value}", idioma).format(value=panel.universe),
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status=_label("{value} em andamento", idioma).format(value=counts.open),
        ),
        Kpi(
            _label("Em dia", idioma),
            counts.on_time,
            _label("Esperado: {value}", idioma).format(value=counts.open),
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=_label("Prazo vigente ainda não venceu", idioma),
        ),
        Kpi(
            _label("Atrasadas", idioma),
            counts.overdue,
            _label("Meta: 0", idioma),
            ValueKind.INTEGER,
            tone=Tone.ERROR if counts.overdue else Tone.OK,
            status=(
                _label("Sem atrasadas", idioma)
                if share is None
                else _label("{value}% das abertas", idioma).format(value=share)
            ),
        ),
        Kpi(
            _label("Concluídas", idioma),
            counts.completed,
            _label("Previsto: {value}", idioma).format(value=panel.due_by_reference),
            ValueKind.INTEGER,
            tone=Tone.OK,
            status=_label("Com data de conclusão", idioma),
        ),
        Kpi(
            _label("Concluídas no prazo original", idioma),
            on_planned,
            _label("Esperado: 100%", idioma),
            ValueKind.PERCENT,
            digits=0,
            tone=None if on_planned is None else (Tone.OK if on_planned == 100 else Tone.WARN),
            status=_label("{done} de {total} sem replanejar", idioma).format(
                done=panel.completed_on_planned, total=counts.completed
            ),
        ),
    )


def _status_values(tally: ResponsibleTally) -> dict[str, int]:
    return {"em_dia": tally.on_time, "atrasadas": tally.overdue, "concluidas": tally.completed}


def _pareto(
    title: str,
    series: Sequence[dict[str, str]],
    categories: list[dict[str, object]],
    idioma: str,
) -> Chart:
    return Chart(
        title,
        "pareto",
        {
            "titulo": title,
            "eixo_esquerdo": _label("Nº de ações", idioma),
            "eixo_direito": _label("% acumulado", idioma),
            "status": list(series),
            "categorias": categories,
            "rotulos": translations.rotulos_de_grafico(idioma),
        },
    )


def _origin_chart(panel: Dashboard, idioma: str) -> Chart:
    return _pareto(
        _label("Status por origem", idioma),
        _series(STATUS_SERIES, idioma),
        [
            {"rotulo": _label(line.origin, idioma), "valores": _status_values(line.tally)}
            for line in panel.origins
        ],
        idioma,
    )


def _responsible_chart(panel: Dashboard, idioma: str) -> Chart:
    return _pareto(
        _label("Ações abertas por responsável", idioma),
        _series(OPEN_SERIES, idioma),
        [
            {"rotulo": line.name, "valores": _status_values(line.tally)}
            for line in panel.top_responsibles
        ],
        idioma,
    )


def _project_chart(panel: Dashboard, idioma: str) -> Chart:
    return _pareto(
        _label("Status por projeto", idioma),
        _series(STATUS_SERIES, idioma),
        [{"rotulo": line.code, "valores": _status_values(line.tally)} for line in panel.projects],
        idioma,
    )


def _month_chart(panel: Dashboard, idioma: str) -> Chart:
    categories = [
        {"id": item.month, "rotulo": month_label(item.month, idioma), "papel": "neutro"}
        for item in panel.months
    ]
    title = _label("Previstas x concluídas por mês", idioma)
    return Chart(
        title,
        "comparativo-barras",
        {
            "titulo": title,
            "paineis": [
                {
                    "titulo": _label("Ações por mês", idioma),
                    "categorias": categories,
                    "linhas": [
                        {
                            "rotulo": _label("Previstas", idioma),
                            "valores": {item.month: item.planned for item in panel.months},
                        },
                        {
                            "rotulo": _label("Concluídas", idioma),
                            "valores": {item.month: item.completed for item in panel.months},
                        },
                    ],
                }
            ],
            "rotulos": translations.rotulos_de_grafico(idioma),
        },
    )


def _status_columns(first: Column, idioma: str) -> tuple[Column, ...]:
    return (
        first,
        Column(_label("Em dia", idioma), ValueKind.INTEGER),
        Column(_label("Atrasadas", idioma), ValueKind.INTEGER),
        Column(_label("Concluídas", idioma), ValueKind.INTEGER),
        Column(_label("Total", idioma), ValueKind.INTEGER),
    )


def _status_cells(tally: ResponsibleTally) -> tuple[Cell | CellValue, ...]:
    return (
        tally.on_time,
        Cell(tally.overdue, Tone.ERROR if tally.overdue else None),
        tally.completed,
        tally.total,
    )


def _origin_table(panel: Dashboard, idioma: str) -> Table:
    return Table(
        title=_label("Status por origem", idioma),
        columns=_status_columns(Column(_label(ORIGIN_LABEL, idioma), width=18), idioma),
        rows=tuple(
            row(_label(line.origin, idioma), *_status_cells(line.tally)) for line in panel.origins
        ),
        per_project=False,
    )


def _project_table(panel: Dashboard, idioma: str) -> Table:
    def line_row(line: ProjectLine) -> Row:
        return row(line.label, *_status_cells(line.tally))

    return Table(
        title=_label("Status por projeto", idioma),
        columns=_status_columns(Column(_label("Projeto", idioma), width=36), idioma),
        rows=tuple(line_row(line) for line in panel.projects),
        per_project=False,
    )


def _responsible_table(panel: Dashboard, idioma: str) -> Table:
    return Table(
        title=_label("Desempenho por responsável", idioma),
        columns=(
            Column(_label("Responsável", idioma), width=28),
            Column(_label("Abertas", idioma), ValueKind.INTEGER),
            Column(_label("Atrasadas", idioma), ValueKind.INTEGER),
            Column(_label("% atrasadas", idioma), ValueKind.PERCENT, digits=0),
            Column(_label("Concluídas", idioma), ValueKind.INTEGER),
            Column(_label("Maior atraso (dias)", idioma), ValueKind.INTEGER),
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


def _month_table(panel: Dashboard, idioma: str) -> Table:
    def month_row(item: MonthCount) -> Row:
        return row(month_label(item.month, idioma), item.planned, item.completed)

    return Table(
        title=_label("Previstas x concluídas por mês", idioma),
        columns=(
            Column(_label("Mês", idioma), width=14),
            Column(_label("Previstas", idioma), ValueKind.INTEGER),
            Column(_label("Concluídas", idioma), ValueKind.INTEGER),
        ),
        rows=tuple(month_row(item) for item in panel.months),
        per_project=False,
    )
