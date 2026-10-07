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
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
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
    ConstraintView,
    EapBreakdownView,
    EapNode,
    EapOverview,
    EapRevisionView,
    LookaheadBoard,
    PeriodCoverage,
    ReportSummary,
    ReportView,
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
    text = format_value(ValueKind.DECIMAL, value, 1)
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
