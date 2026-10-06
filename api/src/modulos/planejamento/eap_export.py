"""Excel and printable version of the EAP screen (ISSUE-036, D12).

One ``Document`` and the two outputs come from it, so the paper never has less than the
spreadsheet: the KPIs of the screen, the structure as the screen shows it (the lines the filters
leave, the root line with the totals), the revisions and the splits of the revision in force.
In the Portfólio each table opens with ``Projeto`` and the weights are those of the portfolio.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.core.export_document import (
    Cell,
    CellValue,
    Column,
    Document,
    Kpi,
    Row,
    Table,
    Tone,
    ValueKind,
    row,
)
from src.modulos.planejamento import eap_calculations as calculations
from src.modulos.planejamento.eap_calculations import TreeRow
from src.modulos.planejamento.eap_service import (
    PORTFOLIO_LABEL,
    EapView,
    RevisionView,
    SplitView,
)

PROJECT_TITLE = "EAP: estrutura analítica do projeto"
PORTFOLIO_TITLE = "EAP da carteira: projetos e pacotes principais"
TREE_TITLE = "Estrutura analítica do projeto"
PORTFOLIO_TREE_TITLE = "Estrutura analítica da carteira"
REVISIONS_TITLE = "Revisões da EAP"
PORTFOLIO_REVISIONS_TITLE = "Revisão vigente da EAP por projeto"
SPLITS_TITLE = "Desdobramentos da revisão vigente"
NO_MEASUREMENT = "Sem medição"
OVERDUE_MARK = " (vencido)"

TONES = {
    calculations.OK: Tone.OK,
    calculations.WARNING: Tone.WARN,
    calculations.DANGER: Tone.ERROR,
}
BAND_WORDS = {
    calculations.OK: "Dentro da faixa",
    calculations.WARNING: "Atenção",
    calculations.DANGER: "Fora da faixa",
}


def criterion_text(line: TreeRow) -> str:
    """The short text of the measuring criterion of a package, as the table and the file print it."""
    if line.level != calculations.PACKAGE_LEVEL:
        return ""
    if not line.is_work:
        return NO_MEASUREMENT
    if line.criterion == calculations.UNITS:
        return f"{calculations.UNITS} ({line.unit or ''})"
    return line.criterion or ""


def eap_document(view: EapView, *, scope_label: str, generated_on: date) -> Document:
    """The EAP as a document: the KPIs of the screen and the tables, one line per row."""
    return Document(
        title=PORTFOLIO_TITLE if view.is_portfolio else PROJECT_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        context=_context(view),
        kpis=_kpis(view),
        tables=_tables(view),
    )


def _context(view: EapView) -> tuple[tuple[str, str], ...]:
    filters = view.filters
    parts = [text for text in (filters.search, filters.criterion, filters.situation) if text]
    lines: list[tuple[str, str]] = [("Data de referência", _date_text(view.reference_date))]
    if parts:
        lines.append(("Filtro", " · ".join(parts)))
    return tuple(lines)


def _date_text(value: date) -> str:
    return f"{value.day:02d}/{value.month:02d}/{value.year}"


def _kpis(view: EapView) -> tuple[Kpi, ...]:
    summary = view.summary
    bands = f"-{view.bands[0]:g} e -{view.bands[1]:g} p.p."
    tone = TONES.get(summary.band or "")
    packages_reference = (
        f"{summary.project_count} projetos · {summary.area_count} pacotes principais"
        if view.is_portfolio
        else _project_reference(view)
    )
    return (
        Kpi(
            "Avanço físico ponderado" if view.is_portfolio else "Avanço físico real",
            summary.real,
            f"Previsto {_percent(summary.planned)} · desvio {summary.deviation:+.1f} p.p.",
            ValueKind.PERCENT,
            digits=1,
            tone=tone,
            status=BAND_WORDS.get(summary.band or "", ""),
        ),
        Kpi(
            "Pacotes de trabalho",
            summary.work_count,
            packages_reference,
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{summary.planning_count} de planejamento",
        ),
        Kpi(
            "Término vencido",
            summary.overdue_count,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if summary.overdue_count else Tone.OK,
            status=f"{summary.behind_count} pacotes com desvio abaixo de -{view.bands[1]:g} p.p. (faixas {bands})",
        ),
    )


def _project_reference(view: EapView) -> str:
    summary = view.summary
    text = f"{summary.area_count} áreas · {summary.subarea_count} subáreas"
    current = view.current_revision
    if current is not None and current.package_count is not None:
        text += f" · linha de base: {current.package_count}"
    return text


def _percent(value: Decimal) -> str:
    return f"{value:.1f}".replace(".", ",") + "%"


def _tables(view: EapView) -> tuple[Table, ...]:
    tables = [_tree_table(view), _revisions_table(view)]
    if not view.is_portfolio:
        tables.append(_splits_table(view))
    return tuple(tables)


def _tree_table(view: EapView) -> Table:
    portfolio = view.is_portfolio
    columns = (
        Column("Código", width=14),
        Column("Descrição", width=44),
        Column("Critério de medição", width=22),
        Column("Un.", width=8),
        Column("Qtd.", ValueKind.DECIMAL),
        Column("Executado", ValueKind.DECIMAL),
        Column("Peso na carteira" if portfolio else "Peso", ValueKind.PERCENT),
        Column(
            "Peso no projeto" if portfolio else "Peso no nível acima", ValueKind.PERCENT, digits=1
        ),
        Column("Início LB", ValueKind.DATE),
        Column("Término LB", width=14),
        Column("Previsto", ValueKind.PERCENT, digits=1),
        Column("Real", ValueKind.PERCENT, digits=1),
        Column("Desvio (p.p.)", ValueKind.DECIMAL, digits=1),
        Column("Item da EAC", width=12),
        Column("Empresa", width=22),
        Column("Responsável", width=22),
    )
    return Table(
        title=PORTFOLIO_TREE_TITLE if portfolio else TREE_TITLE,
        columns=columns,
        rows=tuple(_tree_row(line) for line in view.rows) if not view.is_empty else (),
    )


def _tree_row(line: TreeRow) -> Row:
    is_planning = line.level == calculations.PACKAGE_LEVEL and not line.is_work
    cells: list[Cell | CellValue] = [
        line.code,
        line.description + (" (pacote de planejamento)" if is_planning else ""),
        criterion_text(line),
        line.unit if line.criterion == calculations.UNITS else None,
        line.quantity if line.criterion == calculations.UNITS else None,
        line.executed if line.criterion == calculations.UNITS else None,
        line.weight,
        line.weight_in_parent,
        line.start_date,
        _end_text(line),
        line.planned,
        None if is_planning else line.real,
        None if is_planning else Cell(line.deviation, TONES.get(line.band or "")),
        line.eac_code,
        line.company,
        line.responsible,
    ]
    return row(*cells, project=line.project_label or PORTFOLIO_LABEL)


def _end_text(line: TreeRow) -> str | None:
    if line.end_date is None:
        return None
    text = _date_text(line.end_date)
    return (
        text + OVERDUE_MARK
        if line.level == calculations.PACKAGE_LEVEL and line.is_overdue
        else text
    )


def _revisions_table(view: EapView) -> Table:
    return Table(
        title=PORTFOLIO_REVISIONS_TITLE if view.is_portfolio else REVISIONS_TITLE,
        columns=(
            Column("Revisão", width=12),
            Column("Data", ValueKind.DATE),
            Column("Pacotes", ValueKind.INTEGER),
            Column("Alteração", width=44),
            Column("SM", width=18),
            Column("Justificativa", width=60),
            Column("Aprovado por", width=22),
            Column("Situação", width=14),
        ),
        rows=tuple(_revision_row(item) for item in view.revisions),
    )


def _revision_row(item: RevisionView) -> Row:
    return row(
        f"Rev {item.number}",
        item.revised_on,
        item.package_count,
        item.change,
        item.change_code,
        item.justification,
        item.approved_by,
        _revision_situation(item),
        project=item.project_label,
    )


def _revision_situation(item: RevisionView) -> str:
    words = ["Linha de base"] if item.number == 0 else []
    if item.is_current:
        words.append("Vigente")
    return " · ".join(words)


def _splits_table(view: EapView) -> Table:
    return Table(
        title=SPLITS_TITLE,
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Pacote de planejamento", width=36),
            Column("Pacote de trabalho", width=36),
            Column("Peso", ValueKind.PERCENT),
            Column("Justificativa", width=60),
            Column("Registrado por", width=22),
        ),
        rows=tuple(_split_row(item) for item in view.splits),
    )


def _split_row(item: SplitView) -> Row:
    return row(
        item.split_on,
        item.source,
        item.target,
        item.weight,
        item.justification,
        item.by,
    )
