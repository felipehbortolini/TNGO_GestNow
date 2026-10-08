"""Exports for the Planning module.

Relato do período (ISSUE-044): the ``Document`` the Excel and the printable version share, with
the same content the prototype exported: the indicators, the table of the reports, the table of
the activities and the table of the attention points with the risk tied to each. What the list
shows after the filter is what goes out; in the Portfólio each table opens with ``Projeto``.


The 6WLA (ISSUE-045) hands the generic export one ``Document`` built from the
board the screen shows, so what the Excel and the printable version carry is the
same as the screen: the indicators with their reference, the grid of six weeks
and the restrictions. The data of the Gantt and of the Galeria (D11) is built
here too: the server sends the facts, the library draws them.

The WBS (ISSUE-036) hands the export the same document the screen shows: the
indicators, the tree with the criterion and the deviation of each node, the
revisions and the breakdowns of the revision in force. In the Portfólio the tree
is the projects and their main packages, read-only, with ``Projeto`` in every
table (D8).


The physical S-curve (ISSUE-039) hands the export the same document the screen
shows: the indicators, the weekly chart (D11), the month-by-month table and, in
the read-only Portfólio, the composition of the portfolio with the projects and
their weights; the ``Projeto`` column comes from the generic mechanism (HU-016).

The planning KPIs (ISSUE-040) hands the export the same document the screen
shows: the indicators with their management reference, the SPI per month and the
forecast x actual charts (D11) and the advance per area — per project in the
Portfólio, with the ``Projeto`` column — carrying the numbers behind the charts
as tables for the Excel.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Any

from src.core import calendario
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
    format_value,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.planejamento import calculations
from src.modulos.planejamento.service import (
    LEVEL_PACKAGE,
    PORTFOLIO_LABEL,
    ActivityView,
    CapacityAreaRow,
    CompanySampleRow,
    ConstraintView,
    CurvaFisicaComposition,
    CurvaFisicaIndicators,
    CurvaFisicaOverview,
    CurvaFisicaPoint,
    EapBreakdownView,
    EapNode,
    EapOverview,
    EapRevisionView,
    FieldDayView,
    HoursOverview,
    LookaheadBoard,
    PerformanceBlock,
    PerformanceOverview,
    PeriodCoverage,
    PlanningKpiLine,
    PlanningKpisOverview,
    QuantitiesOverview,
    QuantityItemView,
    ReportSummary,
    ReportView,
    StoppageView,
    WorkSampleView,
)
from src.modulos.planejamento.validation import OPPORTUNITY

TITLE = "Relato do período"


NO_VALUE = "·"


REGISTERED = "Registrado"


PENDING = "Pendente"


# The width of the long texts of the sheets, in characters.
PERIOD_WIDTH = 34


TEXT_WIDTH = 60


@dataclass(frozen=True)
class ReportExport:
    """What the screen hands to the export: the indicators, the reports kept by the filter, the type."""

    summary: ReportSummary
    reports: Sequence[ReportView]
    kind: str = ""


def build_document(
    data: ReportExport, *, scope: Scope, projects: Sequence[ProjectLike], today: date
) -> Document:
    """The document of the screen: the indicators and the three tables, as the list shows them."""
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Tipo", data.kind or "Todos"),),
        kpis=_report_kpis(data.summary),
        tables=(
            _reports_table(data.reports),
            _activities_table(data.reports),
            _points_table(data.reports),
        ),
        paper=Paper.A4,
    )


def _report_kpis(summary: ReportSummary) -> tuple[Kpi, ...]:
    return (
        _coverage_kpi("Semana anterior", summary.previous_week, is_portfolio=summary.is_portfolio),
        _coverage_kpi("Mês anterior", summary.previous_month, is_portfolio=summary.is_portfolio),
        _points_kpi(summary),
        Kpi(
            "Relatos registrados",
            summary.total,
            f"Previsto: {summary.expected_total}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=(
                f"{calculations.plural(summary.weekly_total, 'semanal', 'semanais')} · "
                f"{calculations.plural(summary.monthly_total, 'mensal', 'mensais')}"
            ),
        ),
    )


def _coverage_kpi(label: str, coverage: PeriodCoverage, *, is_portfolio: bool) -> Kpi:
    """The last closed period: registered or pending, or in the Portfólio the projects that did."""
    tone = Tone.OK if coverage.is_complete else Tone.WARN
    if is_portfolio:
        return Kpi(
            label,
            coverage.registered,
            f"Esperado: {coverage.expected}",
            ValueKind.INTEGER,
            tone=tone,
            status=f"{coverage.name} · projetos com relato",
        )
    return Kpi(
        label,
        REGISTERED if coverage.is_complete else PENDING,
        f"Esperado: {REGISTERED}",
        tone=tone,
        status=coverage.name,
    )


def _points_kpi(summary: ReportSummary) -> Kpi:
    last = summary.last_weekly
    reference = NO_VALUE if summary.reference_points is None else str(summary.reference_points)
    if last is None:
        return Kpi(
            "Pontos de atenção (último semanal)",
            NO_VALUE,
            f"Referência: {reference}",
            tone=Tone.INFO,
            status="nenhum relato semanal",
        )
    return Kpi(
        "Pontos de atenção (último semanal)",
        len(last.points),
        f"Referência: {reference}",
        ValueKind.INTEGER,
        tone=Tone.WARN if last.threats else Tone.INFO,
        status=f"{calculations.points_summary(last.threats, last.opportunities)} · {last.short_name}",
    )


def _reports_table(reports: Sequence[ReportView]) -> Table:
    return Table(
        title="Relatos registrados",
        columns=(
            Column("Período", width=PERIOD_WIDTH),
            Column("Atividades do período", ValueKind.INTEGER),
            Column("Próximo período", ValueKind.INTEGER),
            Column("Pontos de atenção", width=PERIOD_WIDTH),
            Column("Atualizado", width=PERIOD_WIDTH),
        ),
        rows=tuple(_report_row(report) for report in reports),
    )


def _report_row(report: ReportView) -> Row:
    points = f"{len(report.points)}"
    if report.points:
        points += f" ({calculations.points_summary(report.threats, report.opportunities)})"
    return row(
        f"{report.kind} · {report.name}",
        len(report.activities),
        len(report.next_activities),
        points,
        f"{updated_text(report)} · {report.updated_by}",
        project=report.project_label,
    )


def updated_text(report: ReportView) -> str:
    """When the report was last saved, in the timezone of the product: ``21/09/2026 16:20``."""
    return calendario.in_product_timezone(report.updated_at).strftime("%d/%m/%Y %H:%M")


def _activities_table(reports: Sequence[ReportView]) -> Table:
    rows: list[Row] = []
    for report in reports:
        rows.extend(
            row(
                report.kind,
                report.name,
                "Atividades do período",
                line,
                project=report.project_label,
            )
            for line in report.activities
        )
        rows.extend(
            row(
                report.kind,
                report.name,
                "Atividades do próximo período",
                line,
                project=report.project_label,
            )
            for line in report.next_activities
        )
    return Table(
        title="Atividades",
        columns=(
            Column("Tipo"),
            Column("Período", width=PERIOD_WIDTH),
            Column("Campo", width=PERIOD_WIDTH),
            Column("Atividade", width=TEXT_WIDTH),
        ),
        rows=tuple(rows),
    )


def _points_table(reports: Sequence[ReportView]) -> Table:
    rows = tuple(
        row(
            report.kind,
            report.name,
            point.description,
            Cell(point.nature, Tone.OK if point.nature == OPPORTUNITY else Tone.WARN),
            point.risk,
            project=report.project_label,
        )
        for report in reports
        for point in report.points
    )
    return Table(
        title="Pontos de atenção e riscos",
        columns=(
            Column("Tipo"),
            Column("Período", width=PERIOD_WIDTH),
            Column("Ponto de atenção", width=TEXT_WIDTH),
            Column("Natureza do risco"),
            Column("Risco atrelado", width=TEXT_WIDTH),
        ),
        rows=rows,
    )


DOCUMENT_TITLE = "6WLA: planejamento de 6 semanas"


GRID_TITLE = "Grade de 6 semanas"


CONSTRAINTS_TITLE = "Restrições"


MARK = "X"


_GANTT_LABELS = {
    "colunaEsquerda": "Atividade",
    "concluidas": "Prontas",
    "concluida": "Pronta",
    "criticas": "Restrição vencida",
    "foraDoPrazo": "Com restrição aberta",
    "emExecucao": "Programada",
}


_SITUATION_LABELS = {
    "vencida": ("Restrição vencida", "erro"),
    "com_restricao": ("Com restrição", "alerta"),
    "pronta": ("Pronta", "ok"),
}


_STATUS_TONES = {"Vencida": Tone.ERROR, "Aberta": Tone.WARN, "Removida": Tone.OK}


def week_caption(week: calculations.LookaheadWeekInfo) -> str:
    """``S40 28/09``: the label of a week and its Monday, as the grid header writes it."""
    return f"{week.label} {week.start:%d/%m}"


def horizon_text(board: LookaheadBoard) -> str:
    """``S40 (28/09) a S45 (02/11)``: the horizon the board covers."""
    first, last = board.weeks[0], board.weeks[-1]
    return f"{first.label} ({first.start:%d/%m}) a {last.label} ({last.start:%d/%m})"


def constraints_summary(activity: ActivityView) -> str:
    """``2 abertas, 1 vencidas``: the constraints column of the grid, as the prototype exported it."""
    return f"{activity.open_constraints} abertas, {activity.overdue_constraints} vencidas"


def lookahead_document(
    board: LookaheadBoard,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    constraints_label: str,
) -> Document:
    """The 6WLA as the exports carry it: indicators, the Gantt, the grid and the restrictions."""
    return Document(
        title=DOCUMENT_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=board.reference_date,
        portfolio=scope.is_portfolio,
        context=(("Horizonte", horizon_text(board)), ("Restrições listadas", constraints_label)),
        kpis=_kpis(board),
        charts=(Chart(GRID_TITLE, "gantt", gantt_data(board)),),
        tables=(_grid_table(board), _constraints_table(board)),
    )


def _kpis(board: LookaheadBoard) -> tuple[Kpi, ...]:
    figures = board.figures
    ready_tone = Tone.OK if figures.short_term_ready == figures.short_term_activities else Tone.WARN
    return (
        Kpi(
            "Atividades no horizonte",
            figures.activities,
            f"Referência: {horizon_text(board)}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
        Kpi(
            "Prontas nas 2 próximas semanas",
            figures.short_term_ready,
            f"Meta: {figures.short_term_activities}",
            ValueKind.INTEGER,
            tone=ready_tone,
            status="Sem restrição aberta; podem ir para a programação",
        ),
        Kpi(
            "Restrições abertas",
            figures.open_constraints,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if figures.open_constraints else Tone.OK,
            status=f"de {figures.total_constraints} identificadas",
        ),
        Kpi(
            "Restrições vencidas",
            figures.overdue_constraints,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if figures.overdue_constraints else Tone.OK,
            status="Data necessária já passou",
        ),
        Kpi(
            "Índice de remoção",
            figures.removal_index,
            "Meta: 100%",
            ValueKind.PERCENT,
            digits=0,
            tone=Tone.INFO,
            status="Restrições removidas ÷ identificadas",
        ),
    )


def _grid_table(board: LookaheadBoard) -> Table:
    columns = (
        Column("ID", width=10),
        Column("Atividade", width=48),
        Column("Responsável", width=24),
        *(Column(week_caption(week), width=12) for week in board.weeks),
        Column("Restrições", width=22),
    )
    rows = tuple(
        row(
            activity.code,
            f"{activity.name} · {activity.area} · {activity.discipline}",
            activity.owner_name,
            *(MARK if marked else "" for marked in activity.planned),
            Cell(constraints_summary(activity), _situation_tone(activity)),
            project=activity.project_label,
        )
        for activity in board.activities
    )
    return Table(title=GRID_TITLE, columns=columns, rows=rows)


def _situation_tone(activity: ActivityView) -> Tone:
    if activity.overdue_constraints:
        return Tone.ERROR
    return Tone.WARN if activity.open_constraints else Tone.OK


def _constraints_table(board: LookaheadBoard) -> Table:
    columns = (
        Column("Atividade", width=48),
        Column("Tipo", width=18),
        Column("Restrição", width=44),
        Column("Responsável", width=24),
        Column("Necessária até", ValueKind.DATE, width=16),
        Column("Removida em", ValueKind.DATE, width=16),
        Column("Situação", width=12),
    )
    rows = tuple(
        row(
            f"{item.activity_code} {item.activity_name}",
            item.kind,
            item.description,
            item.owner_name,
            item.due_date,
            item.removal_date,
            Cell(item.status, _STATUS_TONES[item.status]),
            project=item.project_label,
        )
        for item in board.constraints
    )
    return Table(title=CONSTRAINTS_TITLE, columns=columns, rows=rows)


def gantt_data(board: LookaheadBoard) -> dict[str, Any]:
    """The ``data-dados`` of the Gantt: one bar per activity, from its first to its last week.

    The prototype grid became the library Gantt (D11): ``atrasada`` marks an
    activity planned in the first two weeks with an open restriction, ``critica``
    one with an overdue restriction and ``concluida`` one that is ready.
    """
    window_start = board.weeks[0].start
    activities = []
    for activity in board.activities:
        span = calculations.activity_span(activity.planned, window_start)
        label, role = _SITUATION_LABELS[activity.situation]
        activities.append(
            {
                "id": str(activity.id),
                "wbs": activity.code,
                "nome": activity.name,
                "inicio": span[0].isoformat() if span else None,
                "fim": span[1].isoformat() if span else None,
                "concluida": activity.is_ready,
                "critica": activity.overdue_constraints > 0,
                "atrasada": activity.has_short_term_risk,
                "situacao": {"rotulo": label, "papel": role},
            }
        )
    last = calendario.add_days(window_start, calculations.LOOKAHEAD_WEEKS * 7 - 1)
    return {
        "titulo": GRID_TITLE,
        "hoje": board.reference_date.isoformat(),
        "inicio": window_start.isoformat(),
        "fim": last.isoformat(),
        "atividades": activities,
        "rotulos": dict(_GANTT_LABELS),
    }


def gallery_data(constraints: Sequence[ConstraintView]) -> dict[str, Any]:
    """The ``data-dados`` of the Galeria: one card per open restriction, the overdue ones first."""
    open_ones = [item for item in constraints if item.is_open]
    open_ones.sort(key=lambda item: (not item.is_overdue, item.due_date, item.id))
    return {
        "titulo": "Restrições abertas",
        "contador": "Restrições abertas",
        "itens": [_card(item) for item in open_ones],
    }


def _card(item: ConstraintView) -> Mapping[str, Any]:
    return {
        "titulo": f"{item.activity_code} · {item.activity_name}",
        "meta": [
            {"rotulo": "Tipo", "valor": item.kind},
            {"rotulo": "Responsável", "valor": item.owner_name},
            {"rotulo": "Necessária até", "valor": _date_text(item.due_date)},
            {"rotulo": "Situação", "valor": item.status},
        ],
        "texto": item.description,
    }


def _date_text(value: date) -> str:
    return f"{value:%d/%m/%Y}"


# ── EAP: a árvore, as revisões e os desdobramentos (ISSUE-036) ────────────

EAP_TITLE = "EAP: estrutura analítica do projeto"
EAP_PORTFOLIO_TITLE = "EAP da carteira: projetos e pacotes principais"
EAP_TREE_TITLE = "Estrutura analítica do projeto"
EAP_REVISIONS_TITLE = "Revisões da EAP"
EAP_BREAKDOWNS_TITLE = "Desdobramentos da revisão vigente"
EAP_ZERO_REFERENCE = "Esperado: 0"
EAP_PORTFOLIO_PACKAGES_REFERENCE = "Pacotes dos projetos da carteira"
EAP_NO_MEASUREMENT = "Sem medição"

_BAND_TONES = {
    calculations.SUCCESS_BAND: Tone.OK,
    calculations.WARNING_BAND: Tone.WARN,
    calculations.DANGER_BAND: Tone.ERROR,
}


def eap_document(visao: EapOverview, *, scope_label: str, generated_on: date) -> Document:
    """A EAP como documento: os KPIs, a árvore, as revisões e os desdobramentos da vigente.

    ``scope_label`` é a linha do escopo (``describe_scope``), montada pela rota. No Portfólio a
    árvore traz uma linha por projeto e as áreas dos projetos, somente leitura (D8), e a coluna
    ``Projeto`` entra em cada tabela pelo mecanismo genérico (HU-016).
    """
    tables = [_eap_tree_table(visao), _eap_revisions_table(visao.revisions)]
    if visao.breakdowns:
        tables.append(_eap_breakdowns_table(visao.breakdowns))
    return Document(
        title=EAP_PORTFOLIO_TITLE if visao.is_portfolio else EAP_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=visao.is_portfolio,
        context=_eap_context(visao),
        kpis=eap_kpis(visao),
        tables=tuple(tables),
    )


def eap_kpis(visao: EapOverview) -> tuple[Kpi, ...]:
    """Os indicadores da EAP, os mesmos da faixa do topo da tela."""
    indicadores = visao.indicators
    current = visao.current_revision
    baseline = (
        f"Linha de base: {current.package_count}"
        if current is not None
        else EAP_PORTFOLIO_PACKAGES_REFERENCE
    )
    return (
        Kpi(
            "Avanço físico real",
            indicadores.actual,
            f"Previsto: {format_value(ValueKind.PERCENT, indicadores.predicted, 1)}",
            ValueKind.PERCENT,
            digits=1,
            tone=_BAND_TONES.get(visao.root.band or ""),
            status=(
                f"Desvio {eap_deviation_text(indicadores.deviation_pp)} p.p. na data de referência"
            ),
        ),
        Kpi(
            "Pacotes de trabalho",
            indicadores.work_packages,
            baseline,
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=_packages_status(visao),
        ),
        Kpi(
            "Término vencido",
            indicadores.overdue,
            EAP_ZERO_REFERENCE,
            ValueKind.INTEGER,
            tone=Tone.ERROR if indicadores.overdue else Tone.OK,
            status=f"{indicadores.late} com desvio abaixo da faixa de alerta",
        ),
        Kpi(
            "SMs a incorporar",
            len(visao.pending_changes),
            EAP_ZERO_REFERENCE,
            ValueKind.INTEGER,
            tone=Tone.WARN if visao.pending_changes else Tone.OK,
            status=(
                "Aprovadas com impacto em escopo, fora da EAP"
                if visao.pending_changes
                else "EAP em dia com as SMs"
            ),
        ),
    )


def eap_deviation_text(value: Decimal) -> str:
    """O desvio em p.p. com sinal explícito no positivo, como a tela o escreve: ``+1,2``."""
    return signed_decimal_text(value, 1)


def signed_decimal_text(value: Decimal | None, digits: int = 1) -> str:
    """Um valor com sinal explícito no positivo, como a tela o escreve: ``+6,03``."""
    if value is None:
        return ""
    text = format_value(ValueKind.DECIMAL, value, digits)
    return f"+{text}" if value > 0 else text


def _packages_status(visao: EapOverview) -> str:
    indicadores = visao.indicators
    text = f"{calculations.plural(indicadores.areas, 'área')} · "
    text += calculations.plural(indicadores.subareas, "subárea")
    if indicadores.planning_packages:
        text += " · " + calculations.plural(
            indicadores.planning_packages, "de planejamento", "de planejamento"
        )
        if indicadores.planning_weight is not None:
            text += f" ({format_value(ValueKind.PERCENT, indicadores.planning_weight)})"
    return text


def _eap_context(visao: EapOverview) -> tuple[tuple[str, str], ...]:
    lines = [("Referência", format_value(ValueKind.DATE, visao.reference_date))]
    current = visao.current_revision
    if current is not None:
        lines.append(
            (
                "Revisão vigente",
                f"Rev {current.revision} de {format_value(ValueKind.DATE, current.revision_date)}",
            )
        )
    return tuple(lines)


def _eap_tree_table(visao: EapOverview) -> Table:
    return Table(
        title=EAP_TREE_TITLE,
        columns=(
            Column("Código", width=14),
            Column("Descrição", width=48),
            Column("Critério de medição", width=22),
            Column("Peso", ValueKind.PERCENT),
            Column("Previsto", ValueKind.PERCENT, digits=1),
            Column("Real", ValueKind.PERCENT, digits=1),
            Column("Desvio (p.p.)", ValueKind.DECIMAL, digits=1),
            Column("Início LB", ValueKind.DATE),
            Column("Término LB", ValueKind.DATE),
            Column("Situação", width=16),
            Column("Item da EAC", width=14),
            Column("Empresa", width=24),
            Column("Responsável", width=24),
        ),
        rows=tuple(_eap_tree_row(node) for node in visao.nodes),
    )


def _eap_tree_row(node: EapNode) -> Row:
    return row(
        node.code,
        node.description,
        eap_criterion_text(node),
        node.weight,
        node.predicted,
        node.actual,
        Cell(node.deviation_pp, _BAND_TONES.get(node.band or "")),
        node.start,
        node.finish,
        Cell(eap_situation_text(node), eap_situation_tone(node)),
        node.eac_code,
        node.company_name,
        node.owner_name,
        project=node.project_label or PORTFOLIO_LABEL,
    )


def eap_criterion_text(node: EapNode) -> str:
    """O critério de medição como o protótipo o escreve; vazio fora do pacote."""
    if node.level != LEVEL_PACKAGE:
        return ""
    if node.is_planning_package:
        return EAP_NO_MEASUREMENT
    if node.criterion == calculations.CRITERION_UNITS:
        return f"{node.criterion} ({node.unit})"
    return node.criterion or ""


def eap_situation_text(node: EapNode) -> str:
    """A situação do pacote em palavras; fora do pacote a célula fica vazia."""
    if node.is_planning_package:
        return calculations.PLANNING_PACKAGE
    if node.level != LEVEL_PACKAGE:
        return ""
    if node.overdue:
        return "Vencido"
    if node.not_started:
        return "Não iniciado"
    return "Em andamento"


def eap_situation_tone(node: EapNode) -> Tone | None:
    """A cor da situação: vencido em erro, não iniciado em alerta, planejamento em neutro."""
    if node.is_planning_package:
        return Tone.NEUTRAL
    if node.level != LEVEL_PACKAGE:
        return None
    if node.overdue:
        return Tone.ERROR
    if node.not_started:
        return Tone.WARN
    return Tone.OK


def _eap_revisions_table(revisions: Sequence[EapRevisionView]) -> Table:
    return Table(
        title=EAP_REVISIONS_TITLE,
        columns=(
            Column("Revisão", width=14),
            Column("Data", ValueKind.DATE),
            Column("Pacotes", ValueKind.INTEGER),
            Column("Alteração", width=48),
            Column("SM", width=20),
            Column("Justificativa", width=60),
            Column("Aprovado por", width=24),
        ),
        rows=tuple(
            row(
                f"Rev {revisao.revision}",
                revisao.revision_date,
                revisao.package_count,
                revisao.alteration,
                revisao.change_code,
                revisao.justification,
                revisao.approved_by,
                project=revisao.project_label or PORTFOLIO_LABEL,
            )
            for revisao in revisions
        ),
    )


def _eap_breakdowns_table(breakdowns: Sequence[EapBreakdownView]) -> Table:
    return Table(
        title=EAP_BREAKDOWNS_TITLE,
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Pacote de planejamento", width=44),
            Column("Pacote de trabalho", width=44),
            Column("Peso", ValueKind.PERCENT),
            Column("Justificativa", width=60),
            Column("Registrado por", width=24),
        ),
        rows=tuple(
            row(
                item.applied_on,
                _breakdown_source_label(item),
                _code_label(item.target_code, item.target_description),
                item.weight,
                item.justification,
                item.author,
            )
            for item in breakdowns
        ),
        per_project=False,
    )


def _breakdown_source_label(item: EapBreakdownView) -> str:
    """O pacote de planejamento de origem; encerrado pelo desdobramento, a célula o diz."""
    label = _code_label(item.source_code, item.source_description)
    return f"{label} (encerrado)" if item.source_closed else label


def _code_label(code: str, description: str) -> str:
    return f"{code} · {description}" if description else code


# ── Curva S física (ISSUE-039) ────────────────────────────────────────────

CURVA_FISICA_TITLE = "Curva S física"
CURVA_FISICA_PORTFOLIO_TITLE = "Curva S física da carteira"
CURVA_FISICA_POINTS_TITLE = "Curva S período a período"
CURVA_FISICA_COMPOSITION_TITLE = "Composição da carteira"
CURVA_FISICA_CHART_TITLE = "Curva S"

MONTH_NAMES = (
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)


def curva_fisica_month_label(month: date | None) -> str:
    """``set/26``: o mês da curva como o protótipo o escreve."""
    if month is None:
        return ""
    return f"{MONTH_NAMES[month.month - 1]}/{month.year % 100:02d}"


def curva_fisica_finish_text(item: CurvaFisicaComposition) -> str:
    """``set/26 · LB fev/27``: o término pela tendência com a linha de base ao lado."""
    trend = curva_fisica_month_label(item.trend_finish)
    baseline = curva_fisica_month_label(item.baseline_finish)
    if not trend:
        return f"LB {baseline}" if baseline else NO_VALUE
    return f"{trend} · LB {baseline}" if baseline else trend


def deviation_tone(value: Decimal | None) -> Tone | None:
    """A cor de um desvio em p.p.: negativo em erro, zero ou positivo em ok."""
    if value is None:
        return None
    return Tone.ERROR if value < 0 else Tone.OK


def spi_tone(value: Decimal | None) -> Tone:
    """A cor do SPI: 1 ou mais em ok, de 0,95 a 0,99 em alerta, abaixo em erro."""
    if value is None:
        return Tone.NEUTRAL
    if value >= 1:
        return Tone.OK
    return Tone.WARN if value >= Decimal("0.95") else Tone.ERROR


def curva_fisica_kpis(visao: CurvaFisicaOverview) -> tuple[Kpi, ...]:
    """Os indicadores da Curva S física, os mesmos da faixa do topo da tela."""
    indicadores = visao.indicators
    cut = curva_fisica_month_label(indicadores.cut_month)
    baseline_finish = curva_fisica_month_label(indicadores.baseline_finish) or NO_VALUE
    late = (
        indicadores.trend_finish is not None
        and indicadores.baseline_finish is not None
        and indicadores.trend_finish > indicadores.baseline_finish
    )
    return (
        Kpi(
            "Previsto acumulado",
            indicadores.predicted,
            f"Linha de base: 100% em {baseline_finish}",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
            status=f"linha de base em {cut}" if cut else "",
        ),
        Kpi(
            "Real acumulado",
            indicadores.actual,
            f"Previsto: {format_value(ValueKind.PERCENT, indicadores.predicted, 1)}",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
            status=_real_status(indicadores),
        ),
        Kpi(
            "Desvio",
            indicadores.deviation_pp,
            "Meta: ≥ 0",
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.ERROR if indicadores.deviation_pp < 0 else Tone.OK,
            status="real menos previsto",
        ),
        Kpi(
            "SPI",
            indicadores.spi,
            "Meta: ≥ 1,00",
            ValueKind.DECIMAL,
            digits=2,
            tone=spi_tone(indicadores.spi),
            status=(
                f"mês anterior {format_value(ValueKind.DECIMAL, indicadores.previous_spi, 2)}"
                if indicadores.previous_spi is not None
                else ""
            ),
        ),
        Kpi(
            "Término pela tendência",
            indicadores.trend_finish,
            f"Linha de base: {baseline_finish}",
            ValueKind.DATE,
            tone=Tone.ERROR if late else Tone.OK,
        ),
    )


def _real_status(indicadores: CurvaFisicaIndicators) -> str:
    """``+1,2 p.p. no mês``: o quanto o real andou desde o mês anterior."""
    if indicadores.previous_actual is None:
        return ""
    return f"{eap_deviation_text(indicadores.actual - indicadores.previous_actual)} p.p. no mês"


def curva_fisica_document(
    visao: CurvaFisicaOverview, *, scope_label: str, generated_on: date
) -> Document:
    """A Curva S física como documento: os indicadores, o gráfico, a tabela e a carteira."""
    tables: list[Table] = [_curve_points_table(visao)]
    if visao.is_portfolio:
        tables.append(_curve_composition_table(visao))
    return Document(
        title=CURVA_FISICA_PORTFOLIO_TITLE if visao.is_portfolio else CURVA_FISICA_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=visao.is_portfolio,
        context=_curve_context(visao),
        kpis=curva_fisica_kpis(visao),
        charts=(Chart(CURVA_FISICA_CHART_TITLE, "curva-s-linha", visao.chart),),
        tables=tuple(tables),
    )


def _curve_context(visao: CurvaFisicaOverview) -> tuple[tuple[str, str], ...]:
    lines = [("Referência", format_value(ValueKind.DATE, visao.reference_date))]
    cut = curva_fisica_month_label(visao.indicators.cut_month)
    if cut:
        lines.append(("Corte", cut))
    if visao.revision is not None and visao.revision_date is not None:
        lines.append(
            (
                "Revisão da EAP",
                f"Rev {visao.revision} de {format_value(ValueKind.DATE, visao.revision_date)}",
            )
        )
    return tuple(lines)


def _curve_points_table(visao: CurvaFisicaOverview) -> Table:
    return Table(
        title=CURVA_FISICA_POINTS_TITLE,
        columns=(
            Column("Mês", width=16),
            Column("Previsto no mês (p.p.)", ValueKind.DECIMAL, digits=1),
            Column("Previsto acumulado", ValueKind.PERCENT, digits=1),
            Column("Real no mês (p.p.)", ValueKind.DECIMAL, digits=1),
            Column("Real acumulado", ValueKind.PERCENT, digits=1),
            Column("Tendência", ValueKind.PERCENT, digits=1),
            Column("Desvio (p.p.)", ValueKind.DECIMAL, digits=1),
        ),
        rows=tuple(_curve_point_row(point) for point in visao.points),
        per_project=False,
    )


def _curve_point_row(point: CurvaFisicaPoint) -> Row:
    return row(
        f"{curva_fisica_month_label(point.month)}{' · corte' if point.is_cut else ''}",
        point.month_predicted,
        point.predicted,
        point.month_actual,
        point.actual,
        point.trend,
        Cell(point.deviation_pp, deviation_tone(point.deviation_pp)),
    )


def _curve_composition_table(visao: CurvaFisicaOverview) -> Table:
    return Table(
        title=CURVA_FISICA_COMPOSITION_TITLE,
        columns=(
            Column("Peso na carteira", ValueKind.PERCENT),
            Column("Previsto acumulado", ValueKind.PERCENT, digits=1),
            Column("Real acumulado", ValueKind.PERCENT, digits=1),
            Column("Desvio (p.p.)", ValueKind.DECIMAL, digits=1),
            Column("SPI", ValueKind.DECIMAL, digits=2),
            Column("Contribuição para o desvio (p.p.)", ValueKind.DECIMAL, digits=2),
            Column("Término pela tendência", width=20),
        ),
        rows=tuple(
            row(
                item.weight,
                item.predicted,
                item.actual,
                Cell(item.deviation_pp, deviation_tone(item.deviation_pp)),
                Cell(item.spi, spi_tone(item.spi)),
                Cell(item.contribution_pp, deviation_tone(item.contribution_pp)),
                curva_fisica_finish_text(item),
                project=item.project_label,
            )
            for item in visao.composition
        ),
    )


# ── KPIs de planejamento (ISSUE-040) ──────────────────────────────────────

PLANNING_KPIS_TITLE = "KPIs de prazo"
PLANNING_SPI_TITLE = "SPI por mês"
PLANNING_AREAS_TITLE = "Avanço por área"
PLANNING_PORTFOLIO_AREAS_TITLE = "Avanço por projeto"
PLANNING_PROJECT_WEIGHTED = "Projeto (ponderado)"
PLANNING_PORTFOLIO_WEIGHTED = "Carteira (ponderado)"

PLANNING_SPI_REFERENCE = "Meta: ≥ 1,00"
PLANNING_DEVIATION_REFERENCE = "Meta: ≥ 0"
PLANNING_ZERO_REFERENCE = "Esperado: 0"
PLANNING_NO_WORST_STATUS = "Nenhuma área com previsto até o corte"

_AREAS_WIDTH = 44


def planning_comparison_title(visao: PlanningKpisOverview) -> str:
    """``Previsto x real por projeto`` na carteira e ``por área`` no projeto."""
    return "Previsto x real por projeto" if visao.is_portfolio else "Previsto x real por área"


def planning_areas_title(visao: PlanningKpisOverview) -> str:
    """``Avanço por projeto`` na carteira e ``Avanço por área`` no projeto."""
    return PLANNING_PORTFOLIO_AREAS_TITLE if visao.is_portfolio else PLANNING_AREAS_TITLE


def planning_kpis(visao: PlanningKpisOverview) -> tuple[Kpi, ...]:
    """Os indicadores dos KPIs, os mesmos da faixa do topo da tela e da exportação."""
    indicadores = visao.indicators
    cut = curva_fisica_month_label(indicadores.cut_month)
    return (
        Kpi(
            "SPI ponderado da carteira" if visao.is_portfolio else "SPI do projeto",
            indicadores.spi,
            PLANNING_SPI_REFERENCE,
            ValueKind.DECIMAL,
            digits=2,
            tone=spi_tone(indicadores.spi),
            status=_spi_status(indicadores),
        ),
        Kpi(
            "Previsto x real",
            indicadores.actual,
            f"Previsto: {format_value(ValueKind.PERCENT, indicadores.predicted, 1)}",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
            status=f"acumulado em {cut}" if cut else "",
        ),
        Kpi(
            "Desvio acumulado",
            indicadores.deviation_pp,
            PLANNING_DEVIATION_REFERENCE,
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.ERROR if indicadores.deviation_pp < 0 else Tone.OK,
            status="real menos previsto",
        ),
        _worst_kpi(visao),
        Kpi(
            "Pacotes com término vencido",
            visao.overdue_packages,
            PLANNING_ZERO_REFERENCE,
            ValueKind.INTEGER,
            tone=Tone.ERROR if visao.overdue_packages else Tone.OK,
            status=(
                "Término da linha de base já passou"
                if visao.overdue_packages
                else "Nenhum pacote vencido"
            ),
        ),
        Kpi(
            "SMs a incorporar",
            visao.pending_changes,
            PLANNING_ZERO_REFERENCE,
            ValueKind.INTEGER,
            tone=Tone.WARN if visao.pending_changes else Tone.OK,
            status=(
                "Aprovadas com impacto em escopo, fora da EAP"
                if visao.pending_changes
                else "EAP em dia com as SMs"
            ),
        ),
    )


def _spi_status(indicadores: CurvaFisicaIndicators) -> str:
    """``+0,03 vs. mês anterior``: o quanto o SPI andou desde o mês anterior."""
    if indicadores.spi is None or indicadores.previous_spi is None:
        return ""
    return f"{signed_decimal_text(indicadores.spi - indicadores.previous_spi, 2)} vs. mês anterior"


def _worst_kpi(visao: PlanningKpisOverview) -> Kpi:
    """O maior desvio de área — ou de projeto na carteira — contra o limite da faixa."""
    label = "Maior desvio por projeto" if visao.is_portfolio else "Maior desvio por área"
    reference = f"Limite: ≥ -{format_value(ValueKind.DECIMAL, visao.bands[0], 0)}"
    worst = visao.worst
    if worst is None:
        return Kpi(label, NO_VALUE, reference, tone=Tone.NEUTRAL, status=PLANNING_NO_WORST_STATUS)
    name = worst.code if visao.is_portfolio else worst.name
    return Kpi(
        label,
        worst.deviation_pp,
        reference,
        ValueKind.DECIMAL,
        digits=1,
        tone=Tone.WARN,
        status=(
            f"{name}: real {format_value(ValueKind.PERCENT, worst.actual, 0)} "
            f"x previsto {format_value(ValueKind.PERCENT, worst.predicted, 0)}"
        ),
    )


def planning_kpis_document(
    visao: PlanningKpisOverview, *, scope_label: str, generated_on: date
) -> Document:
    """Os KPIs de prazo como documento: indicadores, gráficos e as duas tabelas."""
    return Document(
        title=PLANNING_KPIS_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=visao.is_portfolio,
        context=_planning_context(visao),
        kpis=planning_kpis(visao),
        charts=(
            Chart(PLANNING_SPI_TITLE, "linhas-multiplas", visao.spi_chart),
            Chart(planning_comparison_title(visao), "comparativo-barras", visao.comparison_chart),
        ),
        tables=(_planning_spi_table(visao), _planning_areas_table(visao)),
    )


def _planning_context(visao: PlanningKpisOverview) -> tuple[tuple[str, str], ...]:
    lines = [("Referência", format_value(ValueKind.DATE, visao.reference_date))]
    cut = curva_fisica_month_label(visao.indicators.cut_month)
    if cut:
        lines.append(("Corte", cut))
    return tuple(lines)


def _planning_spi_table(visao: PlanningKpisOverview) -> Table:
    """O SPI mês a mês: os números por trás do gráfico, para o Excel."""
    months = visao.curve.series.months[: len(visao.spi_series)]
    return Table(
        title=PLANNING_SPI_TITLE,
        columns=(Column("Mês", width=16), Column("SPI", ValueKind.DECIMAL, digits=2)),
        rows=tuple(
            row(curva_fisica_month_label(month), Cell(spi, spi_tone(spi)))
            for month, spi in zip(months, visao.spi_series, strict=True)
        ),
        per_project=False,
    )


def _planning_areas_table(visao: PlanningKpisOverview) -> Table:
    is_portfolio = visao.is_portfolio
    return Table(
        title=planning_areas_title(visao),
        columns=(
            Column("Projeto" if is_portfolio else "Área", width=_AREAS_WIDTH),
            Column(
                "Peso na carteira" if is_portfolio else "Peso",
                ValueKind.PERCENT,
                digits=1 if is_portfolio else 0,
            ),
            Column("Previsto", ValueKind.PERCENT, digits=1),
            Column("Real", ValueKind.PERCENT, digits=1),
            Column("Desvio (p.p.)", ValueKind.DECIMAL, digits=1),
            Column(
                "SPI do projeto" if is_portfolio else "SPI da área", ValueKind.DECIMAL, digits=2
            ),
            Column("Contribuição (p.p.)", ValueKind.DECIMAL, digits=1),
        ),
        rows=tuple(_planning_area_row(item, is_portfolio=is_portfolio) for item in visao.rows),
        totals=_planning_totals(visao),
    )


def _planning_area_row(item: PlanningKpiLine, *, is_portfolio: bool) -> Row:
    return row(
        f"{item.code} · {item.name}" if is_portfolio else item.name,
        item.weight,
        item.predicted,
        item.actual,
        Cell(item.deviation_pp, deviation_tone(item.deviation_pp)),
        Cell(item.spi, spi_tone(item.spi)),
        item.contribution_pp,
    )


def _planning_totals(visao: PlanningKpisOverview) -> tuple[Cell, ...]:
    """O rodapé ponderado: peso somado, previsto, real e desvio que fecham com a Curva S."""
    weight = sum((item.weight for item in visao.rows), Decimal(0))
    indicadores = visao.indicators
    return (
        Cell(PLANNING_PORTFOLIO_WEIGHTED if visao.is_portfolio else PLANNING_PROJECT_WEIGHTED),
        Cell(weight),
        Cell(indicadores.predicted),
        Cell(indicadores.actual),
        Cell(indicadores.deviation_pp, deviation_tone(indicadores.deviation_pp)),
        Cell(),
        Cell(),
    )


# ── Produtividade: quantidades e apontamento (ISSUE-046) ──────────────────


PRODUCTIVITY_TITLE = "Produtividade: plano de quantidades da linha de base"


PRODUCTIVITY_GROUPS_TITLE = "Quantidades por grupo"


PRODUCTIVITY_ITEMS_TITLE = "Plano x realizado por item"


PRODUCTIVITY_CHART_TITLE = "Produção semanal"


PRODUCTIVITY_ACCUMULATED_TITLE = "Avanço acumulado"


def productivity_week_caption(week: str) -> str:
    """O rótulo de uma semana ISO como a tela o lê: ``S39 · 21/09 a 27/09``."""
    day = calendario.week_start(week)
    if day is None:
        return week
    last = calendario.add_days(day, 6)
    return f"S{day.isocalendar()[1]:02d} · {day:%d/%m} a {last:%d/%m}"


def productivity_week_short(week: str) -> str:
    """O número curto da semana ISO (``S39``), como a grade do formulário escreve."""
    day = calendario.week_start(week)
    return f"S{day.isocalendar()[1]:02d}" if day is not None else week


def quantity_text(value: Decimal | None, places: int) -> str:
    """Uma quantidade na escrita brasileira, com as casas da unidade (ou ``·``)."""
    return NO_VALUE if value is None else format_value(ValueKind.DECIMAL, value, places)


def index_text(value: Decimal | None) -> str:
    """Um índice (HH por unidade, SPI ou FP) com duas casas (ou ``·``)."""
    return NO_VALUE if value is None else format_value(ValueKind.DECIMAL, value, 2)


def percent_text(value: Decimal | None, places: int = 1) -> str:
    """Um percentual na escrita brasileira (ou ``·``)."""
    return NO_VALUE if value is None else format_value(ValueKind.PERCENT, value, places)


def productivity_document(
    visao: QuantitiesOverview, *, scope_label: str, generated_on: date
) -> Document:
    """O documento da aba Quantidades: os indicadores, os gráficos e as duas tabelas."""
    return Document(
        title=PRODUCTIVITY_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=visao.is_portfolio,
        context=_productivity_context(visao),
        kpis=productivity_kpis(visao),
        charts=(
            Chart(PRODUCTIVITY_CHART_TITLE, "curva-s-barra-linha", visao.weekly),
            Chart(PRODUCTIVITY_ACCUMULATED_TITLE, "curva-s-linha", visao.accumulated),
        ),
        tables=(_productivity_groups_table(visao), _productivity_items_table(visao)),
        paper=Paper.A4,
    )


def _productivity_context(visao: QuantitiesOverview) -> tuple[tuple[str, str], ...]:
    company = next(
        (
            option.label
            for option in visao.company_options
            if option.value == str(visao.filter.company_id)
        ),
        "Todas",
    )
    return (
        ("Semana de corte", productivity_week_caption(visao.cut_week)),
        ("Empresa", company or "Todas"),
        ("Grupo", visao.filter.group or "Todos"),
    )


def productivity_kpis(visao: QuantitiesOverview) -> tuple[Kpi, ...]:
    """Os indicadores da aba Quantidades, os mesmos da faixa do topo da tela."""
    indicadores = visao.indicators
    parameters = visao.parameters
    return (
        Kpi(
            "Avanço por quantidades",
            indicadores.pct_real,
            f"Previsto: {percent_text(indicadores.pct_prev)}",
            ValueKind.PERCENT,
            digits=1,
            tone=spi_tone(indicadores.spi),
            status=f"SPI de quantidades: {index_text(indicadores.spi)}",
        ),
        Kpi(
            "Aderência da semana",
            indicadores.week_adherence,
            f"Meta: ≥ {percent_text(parameters.adherence_bands[1], 0)}",
            ValueKind.PERCENT,
            digits=1,
            tone=_adherence_tone(indicadores.week_adherence, parameters),
            status=f"Média de {parameters.window_weeks} semanas: {percent_text(indicadores.window_adherence, 0)}",
        ),
        Kpi(
            "Fator de produtividade",
            indicadores.pf_window,
            f"Meta: ≤ {index_text(parameters.pf_bands[0])}",
            ValueKind.DECIMAL,
            digits=2,
            tone=_pf_tone(indicadores.pf_window, parameters),
            status=f"Acumulado: {index_text(indicadores.pf)}",
        ),
        Kpi(
            "Apontamentos pendentes",
            indicadores.pending,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if indicadores.pending else Tone.OK,
            status=f"Itens ativos sem apontamento em {productivity_week_caption(visao.cut_week)}",
        ),
        Kpi(
            "Tendência de atraso",
            indicadores.late_trend,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if indicadores.late_trend else Tone.OK,
            status="Itens com término previsto depois da linha de base",
        ),
    )


def _adherence_tone(value: Decimal | None, parameters: Any) -> Tone:
    if value is None:
        return Tone.INFO
    if value >= parameters.adherence_bands[1]:
        return Tone.OK
    return Tone.WARN if value >= parameters.adherence_bands[0] else Tone.ERROR


def _pf_tone(value: Decimal | None, parameters: Any) -> Tone:
    if value is None:
        return Tone.INFO
    if value <= parameters.pf_bands[0]:
        return Tone.OK
    return Tone.WARN if value <= parameters.pf_bands[1] else Tone.ERROR


def _productivity_groups_table(visao: QuantitiesOverview) -> Table:
    return Table(
        title=PRODUCTIVITY_GROUPS_TITLE,
        columns=(
            Column("Grupo"),
            Column("Unidade"),
            Column("Itens", ValueKind.INTEGER),
            Column("Total da LB", ValueKind.DECIMAL, digits=1),
            Column("Previsto até o corte", ValueKind.DECIMAL, digits=1),
            Column("Realizado acumulado", ValueKind.DECIMAL, digits=1),
            Column("% real (prev.)", ValueKind.PERCENT, digits=1),
            Column("Previsto na semana", ValueKind.DECIMAL, digits=1),
            Column("Realizado na semana", ValueKind.DECIMAL, digits=1),
        ),
        rows=tuple(
            row(
                grupo.group,
                grupo.unit,
                grupo.items,
                grupo.total,
                grupo.prev_acum,
                grupo.real_acum,
                Cell(
                    grupo.pct_real,
                    deviation_tone((grupo.pct_real or Decimal(0)) - (grupo.pct_prev or Decimal(0))),
                ),
                grupo.prev_week,
                grupo.real_week,
            )
            for grupo in visao.groups
        ),
    )


def _productivity_items_table(visao: QuantitiesOverview) -> Table:
    return Table(
        title=PRODUCTIVITY_ITEMS_TITLE,
        columns=(
            Column("Item"),
            Column("Empresa"),
            Column("Grupo"),
            Column("Unidade"),
            Column("Total da LB", ValueKind.DECIMAL, digits=1),
            Column("Índice HH por unidade", ValueKind.DECIMAL, digits=2),
            Column("Realizado acumulado", ValueKind.DECIMAL, digits=1),
            Column("Previsto até o corte", ValueKind.DECIMAL, digits=1),
            Column("% real (prev.)", ValueKind.PERCENT, digits=1),
            Column("Realizado na semana", ValueKind.DECIMAL, digits=1),
            Column("Previsto na semana", ValueKind.DECIMAL, digits=1),
            Column("Aderência da semana", ValueKind.PERCENT, digits=0),
            Column("FP", ValueKind.DECIMAL, digits=2),
            Column("Término pela tendência"),
            Column("Situação da LB"),
        ),
        rows=tuple(_productivity_item_row(item) for item in visao.items),
    )


def _productivity_item_row(item: QuantityItemView) -> Row:
    figures = item.figures
    return row(
        f"{item.code} · {item.kind}",
        item.company_name,
        item.group,
        item.unit,
        item.total,
        item.index_hh,
        figures.real_acum,
        figures.prev_acum,
        Cell(figures.pct_real, deviation_tone(figures.deviation_pp)),
        figures.real_week,
        figures.prev_week,
        figures.week_adherence,
        figures.pf,
        (
            productivity_week_caption(figures.trend_week)
            if figures.trend_week
            else ("no prazo" if figures.deviation_weeks == 0 else NO_VALUE)
        ),
        f"Aprovada rev {item.revision}" if item.approved else "Em elaboração",
        project=item.project_label,
    )


# ── Horas efetivas: jornada, amostragem e paralisação (ISSUE-047) ──────────


HOURS_TITLE = "Produtividade: horas efetivas e amostragem do trabalho"


HOURS_CAPACITY_TITLE = "Capacidade produtiva e jornada"


HOURS_FIELD_DAYS_TITLE = "Registros de jornada"


HOURS_AREAS_TITLE = "Capacidade produtiva por área (CWA)"


HOURS_STOP_REASONS_TITLE = "Pareto dos motivos de parada"


HOURS_TRANSIT_REASONS_TITLE = "Motivos em trânsito"


HOURS_SAMPLE_TITLE = "Amostragem por empresa e encarregado"


HOURS_SAMPLES_TITLE = "Rodadas de observação"


HOURS_AREA_STOPPAGE_TITLE = "Por área (CWA)"


HOURS_STOPPAGE_REASONS_TITLE = "Efetivo paralisado por motivo"


HOURS_STOPPAGE_RESPONSIBILITY_TITLE = "Efetivo paralisado por responsabilidade"


HOURS_STOPPAGES_TITLE = "Registros de paralisação"


def hours_document(visao: HoursOverview, *, scope_label: str, generated_on: date) -> Document:
    """O documento da aba Horas efetivas: os indicadores, o Pareto e as tabelas."""
    return Document(
        title=HOURS_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=visao.is_portfolio,
        context=_hours_context(visao),
        kpis=hours_kpis(visao),
        charts=(stop_reason_chart(visao),),
        tables=(
            _field_days_table(visao),
            _capacity_areas_table(visao),
            _reason_table(HOURS_STOP_REASONS_TITLE, visao.stop_reasons),
            _reason_table(HOURS_TRANSIT_REASONS_TITLE, visao.transit_reasons),
            _sample_companies_table(visao),
            _samples_table(visao),
            _stoppages_table(visao),
            _stoppage_totals_table(HOURS_STOPPAGE_REASONS_TITLE, visao, attribute="by_reason"),
            _stoppage_totals_table(
                HOURS_STOPPAGE_RESPONSIBILITY_TITLE,
                visao,
                attribute="by_responsibility",
            ),
        ),
        paper=Paper.A4,
    )


def _hours_context(visao: HoursOverview) -> tuple[tuple[str, str], ...]:
    company = next(
        (
            option.label
            for option in visao.company_options
            if option.value == str(visao.filter.company_id)
        ),
        "Todas",
    )
    period = next(
        (option.label for option in visao.period_options if option.value == visao.filter.period),
        "",
    )
    return (
        ("Semana de corte", productivity_week_caption(visao.cut_week)),
        ("Período", period),
        ("Empresa", company or "Todas"),
        ("Área (CWA)", visao.filter.area or "Todas"),
        ("Encarregado", visao.filter.foreman or "Todos"),
    )


def hours_kpis(visao: HoursOverview) -> tuple[Kpi, ...]:
    """Os indicadores da aba Horas efetivas, os mesmos dos cartões do topo da tela."""
    capacidade = visao.capacity
    amostragem = visao.sample_summary
    paradas = visao.stoppage_summary
    parameters = visao.parameters
    return (
        Kpi(
            "Capacidade produtiva (CP)",
            capacidade.capacity,
            f"Meta: ≥ {hours_text(parameters.daily_hours * parameters.utilization_pct / 100, 2)} h",
            ValueKind.DECIMAL,
            digits=2,
            tone=_band_tone(
                calculations.utilization_band(
                    capacidade.utilization, target=parameters.utilization_pct
                )
            ),
            status=(
                f"manhã {hours_text(capacidade.morning_capacity, 2)} h · "
                f"tarde {hours_text(capacidade.afternoon_capacity, 2)} h"
            ),
        ),
        Kpi(
            "Utilização da jornada",
            capacidade.utilization,
            f"Meta: ≥ {percent_text(parameters.utilization_pct, 0)}",
            ValueKind.PERCENT,
            digits=1,
            tone=_band_tone(
                calculations.utilization_band(
                    capacidade.utilization, target=parameters.utilization_pct
                )
            ),
            status=f"CP ÷ jornada de {hours_text(parameters.daily_hours, 1)} h",
        ),
        Kpi(
            "Atraso médio de início",
            capacidade.morning_delay_min,
            f"Limite: ≤ {hours_text(parameters.delay_bands[0], 0)} min",
            ValueKind.INTEGER,
            tone=_band_tone(
                calculations.start_delay_band(capacidade.morning_delay_min, parameters.delay_bands)
            ),
            status=f"manhã, da chegada ao início · tarde {hours_text(capacidade.afternoon_delay_min, 0)} min",
        ),
        Kpi(
            "HH efetivas",
            capacidade.effective_hh,
            "Esperado: 0 improdutivas",
            ValueKind.DECIMAL,
            digits=0,
            tone=Tone.INFO,
            status="CP x efetivo nas frentes registradas",
        ),
        Kpi(
            "HH improdutivas na frente",
            capacidade.idle_hh,
            "Esperado: 0",
            ValueKind.DECIMAL,
            digits=0,
            tone=Tone.WARN if capacidade.idle_hh else Tone.OK,
            status="(jornada - CP) x efetivo",
        ),
        Kpi(
            "Trabalhando",
            amostragem.working_pct,
            f"Meta: ≥ {percent_text(parameters.working_pct, 0)}",
            ValueKind.PERCENT,
            digits=1,
            tone=_band_tone(
                calculations.working_band(amostragem.working_pct, target=parameters.working_pct)
            ),
            status=f"{amostragem.people} pessoas observadas",
        ),
        Kpi(
            "Em trânsito",
            amostragem.transit_pct,
            "Esperado: 0 parado",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.WARN,
            status=f"{amostragem.transit} pessoas",
        ),
        Kpi(
            "Parado",
            amostragem.stopped_pct,
            "Esperado: 0",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.ERROR,
            status=f"{amostragem.stopped} pessoas",
        ),
        Kpi(
            "Efetivo paralisado",
            paradas.crew_hours,
            "Esperado: 0",
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.ERROR if paradas.crew_hours else Tone.OK,
            status="Hhora · pessoas x horas paradas",
        ),
        Kpi(
            "Máquinas e equipamentos parados",
            paradas.machine_hours,
            "Esperado: 0",
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.WARN if paradas.machine_hours else Tone.OK,
            status="Mhora · unidades x horas paradas",
        ),
        Kpi(
            "Responsabilidade do cliente",
            paradas.client_hours,
            "Esperado: 0",
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.WARN if paradas.client_hours else Tone.OK,
            status="pleito potencial · externas em Hhora",
        ),
        Kpi(
            "Clima",
            paradas.weather_hours,
            "Esperado: 0",
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.INFO,
            status="tempo excusável sem compensação",
        ),
    )


def _band_tone(band: str | None) -> Tone:
    return {
        "success": Tone.OK,
        "warning": Tone.WARN,
        "danger": Tone.ERROR,
    }.get(band or "", Tone.INFO)


def hours_text(value: Decimal | None, places: int) -> str:
    """Uma hora ou média na escrita brasileira (ou ``·``)."""
    return NO_VALUE if value is None else format_value(ValueKind.DECIMAL, value, places)


def hours_clock(value: time | None) -> str:
    """Um horário como a tela o lê: ``HH:MM`` (ou ``·``)."""
    return NO_VALUE if value is None else value.strftime("%H:%M")


def stop_reason_chart(visao: HoursOverview) -> Chart:
    """O ``data-dados`` do Pareto dos motivos de parada (D11): o servidor manda o total."""
    return Chart(
        HOURS_STOP_REASONS_TITLE,
        "pareto",
        {
            "titulo": HOURS_STOP_REASONS_TITLE,
            "eixo_esquerdo": "Pessoas paradas",
            "eixo_direito": "% acumulado",
            "status": [{"id": "total", "rotulo": "Pessoas paradas", "papel": "erro"}],
            "categorias": [
                {"rotulo": row.reason, "valores": {"total": row.total}}
                for row in visao.stop_reasons
            ],
        },
    )


def _field_days_table(visao: HoursOverview) -> Table:
    return Table(
        title=HOURS_FIELD_DAYS_TITLE,
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Empresa"),
            Column("Área (CWA)"),
            Column("Encarregado"),
            Column("Efetivo", ValueKind.INTEGER),
            Column("Manhã (chegada · início · término)"),
            Column("Tarde (chegada · início · término)"),
            Column("Atraso (min)", ValueKind.INTEGER),
            Column("CP (h/dia)", ValueKind.DECIMAL, digits=2),
            Column("Utilização", ValueKind.PERCENT, digits=0),
            Column("HH efetivas", ValueKind.DECIMAL, digits=1),
            Column("HH improdutivas", ValueKind.DECIMAL, digits=1),
        ),
        rows=tuple(_field_day_row(view) for view in visao.field_days),
    )


def _field_day_row(view: FieldDayView) -> Row:
    figures = view.figures
    return row(
        view.day,
        view.company_name,
        view.area,
        view.foreman,
        view.crew,
        f"{hours_clock(figures.morning.arrival)} · {hours_clock(figures.morning.start)} · {hours_clock(figures.morning.end)}",
        f"{hours_clock(figures.afternoon.arrival)} · {hours_clock(figures.afternoon.start)} · {hours_clock(figures.afternoon.end)}",
        figures.morning_delay_min + figures.afternoon_delay_min,
        figures.capacity,
        figures.utilization,
        figures.effective_hh,
        figures.idle_hh,
        project=view.project_label,
    )


def _capacity_areas_table(visao: HoursOverview) -> Table:
    return Table(
        title=HOURS_AREAS_TITLE,
        columns=(
            Column("Área (CWA)"),
            Column("CP (h/dia)", ValueKind.DECIMAL, digits=2),
            Column("Utilização", ValueKind.PERCENT, digits=0),
            Column("Efetivo paralisado (Hhora)", ValueKind.DECIMAL, digits=1),
            Column("Máq./equip. parados (Mhora)", ValueKind.DECIMAL, digits=1),
            Column("Jornadas", ValueKind.INTEGER),
        ),
        rows=tuple(_capacity_area_row(line) for line in visao.by_area),
    )


def _capacity_area_row(line: CapacityAreaRow) -> Row:
    return row(
        line.area,
        line.capacity,
        line.utilization,
        line.crew_hours,
        line.machine_hours,
        line.records,
    )


def _reason_table(title: str, rows: Sequence[calculations.ReasonTotal]) -> Table:
    return Table(
        title=title,
        columns=(
            Column("Motivo"),
            Column("Pessoas", ValueKind.INTEGER),
            Column("%", ValueKind.PERCENT, digits=1),
            Column("% acumulado", ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(row(line.reason, line.total, line.percent, line.accumulated) for line in rows),
    )


def _sample_companies_table(visao: HoursOverview) -> Table:
    return Table(
        title=HOURS_SAMPLE_TITLE,
        columns=(
            Column("Empresa / encarregado"),
            Column("Rodadas", ValueKind.INTEGER),
            Column("Pessoas observadas", ValueKind.INTEGER),
            Column("% trabalhando", ValueKind.PERCENT, digits=1),
            Column("% em trânsito", ValueKind.PERCENT, digits=1),
            Column("% parado", ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(_sample_company_rows(visao.sample_companies)),
    )


def _sample_company_rows(companies: Sequence[CompanySampleRow]) -> list[Row]:
    rows: list[Row] = []
    for company in companies:
        rows.append(
            row(
                company.company_name,
                company.share.records,
                company.share.people,
                company.share.working_pct,
                company.share.transit_pct,
                company.share.stopped_pct,
            )
        )
        rows.extend(
            row(
                f"    {foreman.foreman}",
                foreman.share.records,
                foreman.share.people,
                foreman.share.working_pct,
                foreman.share.transit_pct,
                foreman.share.stopped_pct,
            )
            for foreman in company.foremen
        )
    return rows


def _samples_table(visao: HoursOverview) -> Table:
    return Table(
        title=HOURS_SAMPLES_TITLE,
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Hora"),
            Column("Empresa"),
            Column("Área (CWA)"),
            Column("Encarregado"),
            Column("Trabalhando", ValueKind.INTEGER),
            Column("Em trânsito", ValueKind.INTEGER),
            Column("Parado", ValueKind.INTEGER),
            Column("% trabalhando", ValueKind.PERCENT, digits=0),
        ),
        rows=tuple(_sample_row(view) for view in visao.samples),
    )


def _sample_row(view: WorkSampleView) -> Row:
    return row(
        view.day,
        hours_clock(view.hour),
        view.company_name,
        view.area,
        view.foreman,
        view.working,
        view.transit,
        view.stopped,
        view.working_pct,
        project=view.project_label,
    )


def _stoppages_table(visao: HoursOverview) -> Table:
    return Table(
        title=HOURS_STOPPAGES_TITLE,
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Empresa"),
            Column("Área (CWA)"),
            Column("Tipo"),
            Column("Recurso parado"),
            Column("Quantidade", ValueKind.DECIMAL, digits=0),
            Column("Início"),
            Column("Término"),
            Column("Horas", ValueKind.DECIMAL, digits=2),
            Column("Hhora / Mhora", ValueKind.DECIMAL, digits=1),
            Column("Motivo"),
            Column("Responsabilidade"),
        ),
        rows=tuple(_stoppage_row(view) for view in visao.stoppages),
    )


def _stoppage_row(view: StoppageView) -> Row:
    return row(
        view.day,
        view.company_name,
        view.area,
        view.kind,
        view.resource,
        view.quantity,
        hours_clock(view.start),
        hours_clock(view.end),
        view.figures.hours,
        view.figures.total,
        view.reason,
        view.responsibility,
        project=view.project_label,
    )


def _stoppage_totals_table(title: str, visao: HoursOverview, *, attribute: str) -> Table:
    totals = getattr(visao.stoppage_summary, attribute)
    return Table(
        title=title,
        columns=(
            Column("Chave"),
            Column("Hhora", ValueKind.DECIMAL, digits=1),
            Column("Eventos", ValueKind.INTEGER),
        ),
        rows=tuple(row(item.key, item.total, item.events) for item in totals),
    )


# ── KPIs de performance (ISSUE-048) ────────────────────────────────────────


PERFORMANCE_TITLE = "Produtividade: KPIs de performance"


PERFORMANCE_COMPANIES_TITLE = "Performance por empresa"


PERFORMANCE_TREND_TITLE = "Tendência semanal por empresa"


PERFORMANCE_ADHERENCE_TITLE = "Aderência semanal por empresa"


PERFORMANCE_WORKING_TITLE = "% trabalhando por empresa"


PERFORMANCE_SITUATION_ALERT = "Alerta"


PERFORMANCE_SITUATION_ATTENTION = "Atenção"


PERFORMANCE_SITUATION_OK = "No plano"


def performance_document(
    visao: PerformanceOverview, *, scope_label: str, generated_on: date
) -> Document:
    """O documento da aba KPIs de performance: indicadores, gráficos e as duas tabelas."""
    return Document(
        title=PERFORMANCE_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=visao.is_portfolio,
        context=_performance_context(visao),
        kpis=performance_kpis(visao),
        charts=(
            Chart(PERFORMANCE_ADHERENCE_TITLE, "curva-s-linha", visao.adherence_chart),
            Chart(PERFORMANCE_WORKING_TITLE, "curva-s-linha", visao.working_chart),
        ),
        tables=(_performance_companies_table(visao), _performance_trend_table(visao)),
        paper=Paper.A4,
    )


def _performance_context(visao: PerformanceOverview) -> tuple[tuple[str, str], ...]:
    return (
        ("Semana de corte", productivity_week_caption(visao.cut_week)),
        ("Empresa", visao.selected.company_name or "Todas as empresas"),
        (
            "Janela de avaliação",
            (
                f"{productivity_week_caption(visao.window_weeks[0])} a "
                f"{productivity_week_caption(visao.window_weeks[-1])}"
            ),
        ),
    )


def performance_kpis(visao: PerformanceOverview) -> tuple[Kpi, ...]:
    """Os indicadores da faixa da aba, os mesmos do bloco selecionado."""
    block = visao.selected
    parameters = visao.parameters
    quantities = block.quantities
    schedule = block.schedule
    return (
        Kpi(
            "Avanço por quantidades",
            quantities.pct_real,
            f"Previsto: {percent_text(quantities.pct_prev)}",
            ValueKind.PERCENT,
            digits=1,
            tone=_band_tone(block.bands.spi),
            status="em horas ganhas",
        ),
        Kpi(
            "SPI de quantidades",
            quantities.spi,
            f"Meta: ≥ {index_text(parameters.spi_bands[1])}",
            ValueKind.DECIMAL,
            digits=2,
            tone=_band_tone(block.bands.spi),
            status="horas ganhas ÷ previstas na LB",
        ),
        Kpi(
            f"Aderência ({parameters.window_weeks} semanas)",
            quantities.window_adherence,
            f"Meta: ≥ {percent_text(parameters.adherence_bands[1], 0)}",
            ValueKind.PERCENT,
            digits=1,
            tone=_band_tone(block.bands.adherence),
            status=f"semana de corte: {percent_text(quantities.week_adherence, 0)}",
        ),
        Kpi(
            "Fator de produtividade",
            quantities.pf_window,
            f"Meta: ≤ {index_text(parameters.pf_bands[0])}",
            ValueKind.DECIMAL,
            digits=2,
            tone=_band_tone(block.bands.pf),
            status=f"acumulado {index_text(quantities.pf)} · 1,00 = orçado",
        ),
        Kpi(
            "Tendência de atraso",
            schedule.slip_weeks,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if schedule.slip_weeks else Tone.OK,
            status=(
                f"SPI(t) {index_text(schedule.spi_t)} · "
                f"{quantities.pending} apontamento(s) pendente(s)"
            ),
        ),
        Kpi(
            "Capacidade produtiva (CP)",
            block.capacity.capacity,
            f"Meta: ≥ {hours_text(parameters.daily_hours * parameters.utilization_pct / 100, 2)} h",
            ValueKind.DECIMAL,
            digits=2,
            tone=_band_tone(block.bands.utilization),
            status=f"utilização {percent_text(block.capacity.utilization)}",
        ),
        Kpi(
            "Pessoas trabalhando",
            block.sample.working_pct,
            f"Meta: ≥ {percent_text(parameters.working_pct, 0)}",
            ValueKind.PERCENT,
            digits=1,
            tone=_band_tone(block.bands.working),
            status=f"parado {percent_text(block.sample.stopped_pct)}",
        ),
        Kpi(
            "Efetivo paralisado",
            block.stoppages.crew_hours,
            "Esperado: 0",
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.WARN if block.stoppages.crew_hours else Tone.OK,
            status=(
                f"{percent_text(block.stoppage_share, 2)} das HH disponíveis · "
                f"cliente {hours_text(block.stoppages.client_hours, 1)}"
            ),
        ),
        Kpi(
            "Máquinas e equipamentos parados",
            block.stoppages.machine_hours,
            "Esperado: 0",
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.WARN if block.stoppages.machine_hours else Tone.OK,
            status=f"{block.stoppages.events} evento(s) de paralisação",
        ),
        Kpi(
            "HH improdutivas na frente",
            block.capacity.idle_hh,
            "Esperado: 0",
            ValueKind.DECIMAL,
            digits=0,
            tone=Tone.WARN if block.capacity.idle_hh else Tone.OK,
            status="(jornada - CP) x efetivo",
        ),
    )


def _performance_companies_table(visao: PerformanceOverview) -> Table:
    return Table(
        title=PERFORMANCE_COMPANIES_TITLE,
        columns=(
            Column("Empresa"),
            Column("Avanço real x prev."),
            Column("SPI", ValueKind.DECIMAL, digits=2),
            Column("Aderência", ValueKind.PERCENT, digits=1),
            Column("FP", ValueKind.DECIMAL, digits=2),
            Column("CP (h/dia)", ValueKind.DECIMAL, digits=2),
            Column("% trabalhando", ValueKind.PERCENT, digits=1),
            Column("Hhora parada", ValueKind.DECIMAL, digits=1),
            Column("Mhora parada", ValueKind.DECIMAL, digits=1),
            Column("Situação"),
        ),
        rows=tuple(_performance_company_row(block) for block in visao.companies),
    )


def _performance_company_row(block: PerformanceBlock) -> Row:
    quantities = block.quantities
    return row(
        block.company_name,
        f"{percent_text(quantities.pct_real, 1)} / {percent_text(quantities.pct_prev, 1)}",
        Cell(quantities.spi, tone=_band_tone(block.bands.spi)),
        Cell(quantities.window_adherence, tone=_band_tone(block.bands.adherence)),
        Cell(quantities.pf_window, tone=_band_tone(block.bands.pf)),
        Cell(block.capacity.capacity, tone=_band_tone(block.bands.utilization)),
        Cell(block.sample.working_pct, tone=_band_tone(block.bands.working)),
        block.stoppages.crew_hours,
        block.stoppages.machine_hours,
        _performance_situation(block),
        project=block.project_label,
    )


def _performance_situation(block: PerformanceBlock) -> Cell:
    if block.alerts:
        return Cell(PERFORMANCE_SITUATION_ALERT, tone=Tone.ERROR)
    if block.attentions:
        return Cell(PERFORMANCE_SITUATION_ATTENTION, tone=Tone.WARN)
    return Cell(PERFORMANCE_SITUATION_OK, tone=Tone.OK)


def _performance_trend_table(visao: PerformanceOverview) -> Table:
    return Table(
        title=PERFORMANCE_TREND_TITLE,
        columns=(
            Column("Semana"),
            Column("Empresa"),
            Column("FP", ValueKind.DECIMAL, digits=2),
            Column("Aderência", ValueKind.PERCENT, digits=1),
            Column("% trabalhando", ValueKind.PERCENT, digits=1),
            Column("CP (h/dia)", ValueKind.DECIMAL, digits=2),
        ),
        rows=tuple(_performance_trend_rows(visao)),
    )


def _performance_trend_rows(visao: PerformanceOverview) -> list[Row]:
    rows: list[Row] = []
    for week in reversed(visao.trend_weeks):
        for block in visao.companies:
            data = next((item for item in block.trend if item.week == week), None)
            if data is None or not any(
                value is not None
                for value in (data.pf, data.adherence, data.working_pct, data.capacity)
            ):
                continue
            rows.append(
                row(
                    productivity_week_short(week),
                    block.company_name,
                    data.pf,
                    data.adherence,
                    data.working_pct,
                    data.capacity,
                    project=block.project_label,
                )
            )
    return rows
