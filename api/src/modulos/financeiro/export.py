"""Excel and printable version of the Financeiro screens (D12).

One ``Document`` per screen, and the two outputs come from it, so the paper never has less than
the spreadsheet. The EAC exports the structure as the screen shows it: the lines the filters
leave, the root line (code 0) with the total, and, in the Portfólio, the weight of each project.
"""

from __future__ import annotations

from datetime import date

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
from src.modulos.financeiro.calculations import LEAF_LEVEL, TreeRow
from src.modulos.financeiro.service import PORTFOLIO_LABEL, EacView

PROJECT_TITLE = "EAC: estrutura analítica de custos"
PORTFOLIO_TITLE = "EAC da carteira: projetos e pacotes principais"
TABLE_TITLE = "Estrutura analítica de custos"
BUDGET_REFERENCE = "Quantidade x preço unitário dos itens"


def eac_document(view: EacView, *, scope_label: str, generated_on: date) -> Document:
    """The EAC as a document: the KPIs of the screen and the tree, one line per row of the table.

    ``scope_label`` is the line of the scope (``describe_scope``), made by the route.
    """
    return Document(
        title=PORTFOLIO_TITLE if view.is_portfolio else PROJECT_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        context=_context(view),
        kpis=_kpis(view),
        tables=(_tree_table(view),),
    )


def _context(view: EacView) -> tuple[tuple[str, str], ...]:
    parts = [text for text in (view.filters.search, view.filters.cost_type) if text]
    return (("Filtro", " · ".join(parts)),) if parts else ()


def _kpis(view: EacView) -> tuple[Kpi, ...]:
    summary = view.summary
    if view.is_portfolio:
        return (
            Kpi(
                "Orçamento vigente da carteira",
                summary.budget_cents,
                BUDGET_REFERENCE,
                ValueKind.MONEY,
                tone=Tone.NEUTRAL,
                status="Soma dos projetos",
            ),
            Kpi(
                "Projetos",
                summary.project_count,
                f"Cadastrados: {summary.registered_project_count}",
                ValueKind.INTEGER,
                tone=Tone.INFO,
                status=f"{summary.package_count} pacotes principais",
            ),
        )
    return (
        Kpi(
            "Orçamento vigente",
            summary.budget_cents,
            BUDGET_REFERENCE,
            ValueKind.MONEY,
            tone=Tone.NEUTRAL,
            status="Total do projeto",
        ),
        Kpi(
            "Itens de custo",
            summary.item_count,
            f"{summary.package_count} pacotes",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{summary.subpackage_count} subpacotes",
        ),
    )


def _tree_table(view: EacView) -> Table:
    columns = [
        Column("Código", width=14),
        Column("Descrição", width=44),
        Column("Tipo de custo", width=16),
        Column("Un.", width=8),
        Column("Qtd.", ValueKind.DECIMAL),
        Column("Preço unitário", ValueKind.MONEY),
        Column("Valor orçado", ValueKind.MONEY),
        Column("CAPEX/OPEX", width=12),
        Column("Centro de custo", width=16),
        Column("Responsável", width=22),
    ]
    if view.is_portfolio:
        columns.append(Column("Peso na carteira", ValueKind.PERCENT))
    rows = tuple(_row_of(line, portfolio=view.is_portfolio) for line in view.rows)
    return Table(
        title=TABLE_TITLE,
        columns=tuple(columns),
        rows=rows if not view.is_empty else (),
        totals=_filtered_totals(view, len(columns)),
    )


def _row_of(line: TreeRow, *, portfolio: bool) -> Row:
    cells: list[Cell | CellValue] = [
        line.code,
        line.description,
        line.cost_type,
        line.unit,
        line.quantity,
        line.unit_price_cents,
        line.budget_cents,
        _classification(line),
        line.cost_center,
        line.responsible,
    ]
    if portfolio:
        cells.append(line.weight)
    return row(*cells, project=line.project_label or PORTFOLIO_LABEL)


def _classification(line: TreeRow) -> str | None:
    if line.level < LEAF_LEVEL or line.capex is None:
        return None
    return "CAPEX" if line.capex else "OPEX"


def _filtered_totals(view: EacView, column_count: int) -> tuple[Cell, ...] | None:
    if view.filtered_total_cents is None or view.is_empty:
        return None
    cells = [Cell() for _ in range(column_count)]
    cells[0] = Cell("Total filtrado")
    cells[6] = Cell(view.filtered_total_cents)
    return tuple(cells)
