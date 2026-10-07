"""Excel and printable version of the Financeiro screens (D12).

One ``Document`` per screen, and the two outputs come from it, so the paper never has less than
the spreadsheet. The EAC exports the structure as the screen shows it: the lines the filters
leave, the root line (code 0) with the total, and, in the Portfólio, the weight of each project.
The revisions and the reallocations of ISSUE-030 come in the same document, as the screen shows
them: the frozen baseline of each revision with its variation, and the applied and pending
transfers with the free balance of the origin. The contract of ISSUE-032 brings its own document:
the KPIs of the ficha, the cascade of the value and the tables of measurements and addenda.
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
    Row,
    Table,
    Tone,
    ValueKind,
    format_value,
    row,
)
from src.modulos.financeiro.calculations import (
    LEAF_LEVEL,
    SITUATION_APPROVED,
    SITUATION_INVOICED,
    SITUATION_PAID,
    SITUATION_RETURNED,
    SITUATION_UNDER_REVIEW,
    TreeRow,
)
from src.modulos.financeiro.service import (
    PORTFOLIO_LABEL,
    AddendumView,
    ContractView,
    EacView,
    MapaControleView,
    MapaRow,
    MeasurementView,
    ReallocationRow,
    RevisionRow,
)

PROJECT_TITLE = "EAC: estrutura analítica de custos"
PORTFOLIO_TITLE = "EAC da carteira: projetos e pacotes principais"
TABLE_TITLE = "Estrutura analítica de custos"
REVISIONS_TITLE = "Revisões do orçamento"
REALLOCATIONS_TITLE = "Remanejamentos"
BUDGET_REFERENCE = "Quantidade x preço unitário dos itens"
APPLIED_SITUATION = "Aplicado"

MAP_TITLE = "Mapa de controle da EAC"
MAP_PORTFOLIO_TITLE = "Mapa de controle da carteira"
MAP_TABLE_TITLE = "Mapa de controle"
MAP_DEVIATION_REFERENCE = "Projeção no término menos orçado atual; positivo é sobrecusto"
MAP_CURRENT_REFERENCE = "Linha de base mais remanejamentos"
MAP_PROJECTION_REFERENCE = "Estimativa vigente da equipe ou do fechamento"
ERP_REFERENCE = "Fechamento do mês do ERP"


def eac_document(
    view: EacView,
    *,
    scope_label: str,
    generated_on: date,
    revisions: Sequence[RevisionRow] = (),
    reallocations: Sequence[ReallocationRow] = (),
) -> Document:
    """The EAC as a document: the KPIs of the screen, the tree, the revisions and the reallocations.

    ``scope_label`` is the line of the scope (``describe_scope``), made by the route.
    """
    return Document(
        title=PORTFOLIO_TITLE if view.is_portfolio else PROJECT_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        context=_context(view),
        kpis=_kpis(view),
        tables=(
            _tree_table(view),
            _revisions_table(revisions),
            _reallocations_table(reallocations),
        ),
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


# ── Revisões e remanejamentos (ISSUE-030) ────────────────────────────────


def _revisions_table(lines: Sequence[RevisionRow]) -> Table:
    return Table(
        title=REVISIONS_TITLE,
        columns=(
            Column("Revisão", width=18),
            Column("Data", ValueKind.DATE),
            Column("Total", ValueKind.MONEY),
            Column("Variação", ValueKind.MONEY),
            Column("SM", width=20),
            Column("Justificativa", width=60),
            Column("Aprovado por", width=24),
        ),
        rows=tuple(
            row(
                f"Rev {line.view.revision}",
                line.view.revision_date,
                line.view.total_cents,
                line.variation_cents,
                line.view.change_code,
                line.view.justification,
                line.view.approved_by,
                project=line.project_label,
            )
            for line in lines
        ),
    )


def _reallocations_table(lines: Sequence[ReallocationRow]) -> Table:
    return Table(
        title=REALLOCATIONS_TITLE,
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Origem", width=34),
            Column("Destino", width=34),
            Column("Valor", ValueKind.MONEY),
            Column("SM", width=20),
            Column("Situação", width=22),
            Column("Saldo livre da origem", ValueKind.MONEY),
            Column("Justificativa", width=60),
            Column("Registrado por", width=24),
        ),
        rows=tuple(
            row(
                line.view.applied_on,
                _item_label(line.view.source_code, line.view.source_description),
                _item_label(line.view.target_code, line.view.target_description),
                line.view.value_cents,
                line.view.change_code,
                APPLIED_SITUATION if line.view.applied else line.view.situation,
                line.view.free_balance_cents,
                line.view.justification,
                line.view.author,
                project=line.project_label,
            )
            for line in lines
        ),
    )


def _item_label(code: str, description: str) -> str:
    return f"{code} · {description}" if description else code


# ── Mapa de controle (ISSUE-031) ─────────────────────────────────────────


def mapa_document(view: MapaControleView, *, scope_label: str, generated_on: date) -> Document:
    """O mapa de controle como documento: os KPIs do escopo e a tabela item a item.

    ``scope_label`` é a linha do escopo (``describe_scope``), montada pela rota. No Portfólio
    cada linha é um projeto e a coluna Projeto entra pelo mecanismo genérico (HU-016).
    """
    return Document(
        title=MAP_PORTFOLIO_TITLE if view.is_portfolio else MAP_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        kpis=_mapa_kpis(view),
        tables=(_mapa_table(view),),
    )


def _mapa_kpis(view: MapaControleView) -> tuple[Kpi, ...]:
    total = view.total
    tone = _deviation_tone(total.deviation_cents)
    return (
        Kpi("Orçado atual", total.current_cents, MAP_CURRENT_REFERENCE, ValueKind.MONEY),
        Kpi("Comprometido", total.committed_cents, ERP_REFERENCE, ValueKind.MONEY, tone=Tone.INFO),
        Kpi("Realizado", total.actual_cents, ERP_REFERENCE, ValueKind.MONEY, tone=Tone.INFO),
        Kpi(
            "Projeção no término",
            total.projection_cents,
            MAP_PROJECTION_REFERENCE,
            ValueKind.MONEY,
            tone=tone,
            status=total.band.label,
        ),
        Kpi(
            "Desvio no término",
            total.deviation_cents,
            MAP_DEVIATION_REFERENCE,
            ValueKind.MONEY,
            tone=tone,
            status=total.band.label,
        ),
    )


def _mapa_table(view: MapaControleView) -> Table:
    return Table(
        title=MAP_TABLE_TITLE,
        columns=(
            Column("Código", width=14),
            Column("Descrição", width=44),
            Column("Orçado", ValueKind.MONEY),
            Column("Remanejamentos", ValueKind.MONEY),
            Column("Orçado atual", ValueKind.MONEY),
            Column("Comprometido", ValueKind.MONEY),
            Column("Realizado", ValueKind.MONEY),
            Column("Saldo a comprometer", ValueKind.MONEY),
            Column("Projeção no término", ValueKind.MONEY),
            Column("Desvio", ValueKind.MONEY),
            Column("Desvio %", ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(_mapa_row(line) for line in view.rows),
        totals=_mapa_totals(view.total),
    )


def _mapa_row(line: MapaRow) -> Row:
    tone = _deviation_tone(line.deviation_cents)
    return row(
        line.code,
        line.description,
        line.baseline_cents,
        line.reallocation_cents,
        line.current_cents,
        line.committed_cents,
        line.actual_cents,
        line.saldo_cents,
        line.projection_cents,
        Cell(line.deviation_cents, tone),
        Cell(line.deviation_percent, tone),
        project=line.project_label or PORTFOLIO_LABEL,
    )


def _mapa_totals(total: MapaRow) -> tuple[Cell, ...]:
    tone = _deviation_tone(total.deviation_cents)
    return (
        Cell(),
        Cell(total.description),
        Cell(total.baseline_cents),
        Cell(total.reallocation_cents),
        Cell(total.current_cents),
        Cell(total.committed_cents),
        Cell(total.actual_cents),
        Cell(total.saldo_cents),
        Cell(total.projection_cents),
        Cell(total.deviation_cents, tone),
        Cell(total.deviation_percent, tone),
    )


def _deviation_tone(deviation_cents: int) -> Tone:
    if deviation_cents > 0:
        return Tone.ERROR
    if deviation_cents < 0:
        return Tone.OK
    return Tone.NEUTRAL


# ── Ficha do contrato (ISSUE-032) ────────────────────────────────────────


CONTRACT_TITLE = "Contrato {number}"
CONTRACT_CASCADE_TITLE = "Composição do valor"
CONTRACT_MEASUREMENTS_TITLE = "Medições"
CONTRACT_ADDENDA_TITLE = "Aditivos"
CONTRACT_MEASURED_REFERENCE = "Disponível a medir = saldo a faturar - em análise"
CONTRACT_BALANCE_REFERENCE = "Valor atual - medido aprovado"
CONTRACT_NO_EXTRA_DAYS = "No prazo original"

_SITUATION_TONES = {
    SITUATION_UNDER_REVIEW: Tone.WARN,
    SITUATION_APPROVED: Tone.INFO,
    SITUATION_INVOICED: Tone.INFO,
    SITUATION_PAID: Tone.OK,
    SITUATION_RETURNED: Tone.ERROR,
}
_CASCADE_FORMAT = {"divisor": 100, "moeda": "BRL", "casas": 0}


def contrato_document(view: ContractView, *, scope_label: str, generated_on: date) -> Document:
    """A ficha do contrato como documento: os KPIs, a cascata e as tabelas de medições e aditivos.

    ``scope_label`` é a linha do escopo (``describe_scope``), montada pela rota. O gráfico da
    cascata só aparece no imprimível: o Excel leva os mesmos números na tabela "Composição do
    valor", para nenhum dos dois ter menos que o outro.
    """
    return Document(
        title=CONTRACT_TITLE.format(number=view.number),
        scope_label=scope_label,
        generated_on=generated_on,
        context=_contract_context(view),
        kpis=_contract_kpis(view),
        charts=(
            Chart(
                CONTRACT_CASCADE_TITLE,
                "cascata-contrato",
                {
                    "titulo": CONTRACT_CASCADE_TITLE,
                    "formato": dict(_CASCADE_FORMAT),
                    "etapas": [dict(step) for step in view.cascade],
                },
            ),
        ),
        tables=(_cascade_table(view), _measurements_table(view), _addenda_table(view)),
    )


def _contract_context(view: ContractView) -> tuple[tuple[str, str], ...]:
    return (
        ("Contratada", view.company),
        ("Objeto", view.object),
        ("Modalidade", view.modality),
        ("Item da EAC", view.eac_code),
        ("Início", format_value(ValueKind.DATE, view.start)),
        ("Término original", format_value(ValueKind.DATE, view.original_end)),
        ("Gestor do contrato", view.manager),
        ("Fiscal", view.fiscal),
        ("Retenção contratual", f"{view.retention_pct}%"),
        ("Prazo de notificação de claims", f"{view.claim_notice_days} dias"),
        ("Situação", view.situation),
    )


def _contract_kpis(view: ContractView) -> tuple[Kpi, ...]:
    extra_days = (view.current_end - view.original_end).days
    status = f"+{extra_days} dias sobre o original" if extra_days > 0 else CONTRACT_NO_EXTRA_DAYS
    return (
        Kpi(
            "Valor atual",
            view.current_value_cents,
            f"Linha de base: {format_value(ValueKind.MONEY, view.original_value_cents)}",
            ValueKind.MONEY,
            status=f"Aditivos: {format_value(ValueKind.MONEY, view.addenda_cents)}",
        ),
        Kpi(
            "Medido aprovado",
            view.measured_cents,
            CONTRACT_MEASURED_REFERENCE,
            ValueKind.MONEY,
            tone=Tone.INFO,
            status=(
                "Disponível a medir: "
                f"{format_value(ValueKind.MONEY, view.available_to_measure_cents)}"
            ),
        ),
        Kpi(
            "Saldo a faturar",
            view.balance_to_invoice_cents,
            CONTRACT_BALANCE_REFERENCE,
            ValueKind.MONEY,
            tone=Tone.INFO,
            status=f"Retenção contratual: {view.retention_pct}%",
        ),
        Kpi(
            "Término vigente",
            view.current_end,
            f"Original: {format_value(ValueKind.DATE, view.original_end)}",
            ValueKind.DATE,
            tone=Tone.WARN if extra_days > 0 else Tone.OK,
            status=status,
        ),
    )


def _cascade_table(view: ContractView) -> Table:
    return Table(
        title=CONTRACT_CASCADE_TITLE,
        columns=(Column("Etapa", width=34), Column("Valor", ValueKind.MONEY)),
        rows=tuple(row(str(step["rotulo"]), step["valor"]) for step in view.cascade),
    )


def _measurements_table(view: ContractView) -> Table:
    return Table(
        title=CONTRACT_MEASUREMENTS_TITLE,
        columns=(
            Column("Nº", width=10),
            Column("Período", ValueKind.DATE),
            Column("Valor bruto", ValueKind.MONEY),
            Column("Retenção", ValueKind.MONEY),
            Column("Valor líquido", ValueKind.MONEY),
            Column("Situação", width=16),
            Column("Motivo da devolução", width=40),
        ),
        rows=tuple(_measurement_row(line) for line in view.measurements),
    )


def _measurement_row(line: MeasurementView) -> Row:
    return row(
        line.number,
        line.period,
        line.gross_cents,
        line.retention_cents,
        line.net_cents,
        Cell(line.situation, _SITUATION_TONES.get(line.situation)),
        line.return_reason,
    )


def _addenda_table(view: ContractView) -> Table:
    return Table(
        title=CONTRACT_ADDENDA_TITLE,
        columns=(
            Column("Nº", width=10),
            Column("Data", ValueKind.DATE),
            Column("Valor", ValueKind.MONEY),
            Column("Dias", ValueKind.INTEGER),
            Column("Motivo", width=48),
            Column("SM", width=20),
        ),
        rows=tuple(_addendum_row(line) for line in view.addenda),
    )


def _addendum_row(line: AddendumView) -> Row:
    return row(
        line.number,
        line.signed_on,
        line.value_cents,
        line.days,
        line.reason,
        line.change_code,
    )
