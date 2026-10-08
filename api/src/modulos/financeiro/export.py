"""Excel and printable version of the Financeiro screens (D12).

One ``Document`` per screen, and the two outputs come from it, so the paper never has less than
the spreadsheet. The EAC exports the structure as the screen shows it: the lines the filters
leave, the root line (code 0) with the total, and, in the Portfólio, the weight of each project.
The revisions and the reallocations of ISSUE-030 come in the same document, as the screen shows
them: the frozen baseline of each revision with its variation, and the applied and pending
transfers with the free balance of the origin. The contract of ISSUE-032 brings its own document:
the KPIs of the ficha, the cascade of the value and the tables of measurements and addenda. The
contractor evaluation of ISSUE-034 brings the period, the type, the evaluator, each criterion with
the note and the weight frozen in the evaluation, the score and the class. The consolidated vision
of ISSUE-035 brings the KPIs of contract administration and the five tables (contracts, claims,
EOT, payment milestones and evaluations) of the scope, with the filters of the screen. The
Contingência of ISSUE-041 brings its own document: the four indicators, the chart of the real
against the expected balance (and, for the spreadsheet, the same numbers in the burn table), the
composition of the budget, the statement of movements and, in the Portfólio, the table per project.
The Curva S financeira and the KPIs de custo of ISSUE-042 bring one document each: the indicators,
the chart (the four series of the curve and the CPI against the SPI) and the tables, with the
portfolio table of the cost performance of each project. The Cronograma de desembolso of
ISSUE-043 brings the four indicators, the monthly chart of the three series (previsto, realizado
and projetado) and the item x month table of the balance to pay.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

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
    CLAIM_AGREED,
    CLAIM_CLOSED,
    CLAIM_IN_DISPUTE,
    CLAIM_IN_NEGOTIATION,
    CLAIM_NOTIFIED,
    CLAIM_REJECTED,
    CLAIM_UNDER_REVIEW,
    EXTENSION_DENIED,
    EXTENSION_GRANTED,
    EXTENSION_PARTIALLY_GRANTED,
    EXTENSION_REQUESTED,
    EXTENSION_UNDER_REVIEW,
    LEAF_LEVEL,
    MILESTONE_APPROVED,
    MILESTONE_EVIDENCE_SENT,
    MILESTONE_FORECAST,
    MILESTONE_INVOICED,
    MILESTONE_PAID,
    SITUATION_APPROVED,
    SITUATION_INVOICED,
    SITUATION_PAID,
    SITUATION_RETURNED,
    SITUATION_UNDER_REVIEW,
    TreeRow,
    milestone_is_late,
    milestone_late_days,
)
from src.modulos.financeiro.service import (
    PORTFOLIO_LABEL,
    AddendumView,
    ClaimView,
    ContingencyOverview,
    ContingencyProjectRow,
    ContractsOverview,
    ContractView,
    CostKpiMonth,
    CostKpiProjectRow,
    CostKpisOverview,
    DisbursementItem,
    DisbursementOverview,
    EacView,
    EvaluationCriterionSpec,
    EvaluationCriterionView,
    EvaluationView,
    ExtensionView,
    FinancialCurveOverview,
    MapaControleView,
    MapaRow,
    MeasurementView,
    MilestoneView,
    ReallocationRow,
    ReserveLine,
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


# ── Marcos, claims e EOT da ficha (ISSUE-033) ────────────────────────────


CONTRACT_MILESTONES_TITLE = "Marcos de pagamento"
CONTRACT_CLAIMS_TITLE = "Claims"
CONTRACT_EXTENSIONS_TITLE = "Extensões de prazo"

_MILESTONE_TONES = {
    MILESTONE_FORECAST: Tone.NEUTRAL,
    MILESTONE_EVIDENCE_SENT: Tone.WARN,
    MILESTONE_APPROVED: Tone.INFO,
    MILESTONE_INVOICED: Tone.INFO,
    MILESTONE_PAID: Tone.OK,
}
_CLAIM_TONES = {
    CLAIM_NOTIFIED: Tone.WARN,
    CLAIM_UNDER_REVIEW: Tone.WARN,
    CLAIM_IN_NEGOTIATION: Tone.WARN,
    CLAIM_AGREED: Tone.OK,
    CLAIM_REJECTED: Tone.ERROR,
    CLAIM_IN_DISPUTE: Tone.ERROR,
    CLAIM_CLOSED: Tone.NEUTRAL,
}
_EXTENSION_TONES = {
    EXTENSION_REQUESTED: Tone.WARN,
    EXTENSION_UNDER_REVIEW: Tone.WARN,
    EXTENSION_GRANTED: Tone.OK,
    EXTENSION_PARTIALLY_GRANTED: Tone.OK,
    EXTENSION_DENIED: Tone.ERROR,
}


def contrato_marcos_document(
    view: ContractView, *, scope_label: str, generated_on: date
) -> Document:
    """Os marcos de pagamento da ficha como documento, com o atraso e a soma dos percentuais.

    ``generated_on`` é a data de referência do atraso, como o protótipo comparava a data
    prevista com o dia corrente; o mesmo conteúdo da aba vai para o Excel e o imprimível.
    """
    return Document(
        title=CONTRACT_TITLE.format(number=view.number),
        scope_label=scope_label,
        generated_on=generated_on,
        context=_contract_context(view),
        tables=(_milestones_table(view, reference_date=generated_on),),
    )


def contrato_claims_document(
    view: ContractView, *, scope_label: str, generated_on: date
) -> Document:
    """Os claims da ficha como documento, com o alerta de notificação fora do prazo."""
    return Document(
        title=CONTRACT_TITLE.format(number=view.number),
        scope_label=scope_label,
        generated_on=generated_on,
        context=_contract_context(view),
        tables=(_claims_table(view),),
    )


def contrato_extensoes_document(
    view: ContractView, *, scope_label: str, generated_on: date
) -> Document:
    """As extensões de prazo da ficha como documento, com a decisão e a SM da linha de base."""
    return Document(
        title=CONTRACT_TITLE.format(number=view.number),
        scope_label=scope_label,
        generated_on=generated_on,
        context=_contract_context(view),
        tables=(_extensions_table(view),),
    )


def _milestones_table(view: ContractView, *, reference_date: date) -> Table:
    columns = (
        Column("Nº", width=10),
        Column("Marco", width=44),
        Column("Critério de aceite", width=40),
        Column("%", ValueKind.INTEGER),
        Column("Valor", ValueKind.MONEY),
        Column("Retenção", ValueKind.MONEY),
        Column("Prevista", ValueKind.DATE),
        Column("Atraso (dias)", ValueKind.INTEGER),
        Column("Conclusão", ValueKind.DATE),
        Column("Situação", width=16),
        Column("Evidência", width=12),
    )
    totals: tuple[Cell, ...] = (
        Cell(),
        Cell("Total"),
        Cell(),
        Cell(view.milestone_pct_total),
        Cell(sum(line.value_cents for line in view.milestones)),
        Cell(),
        Cell(),
        Cell(),
        Cell(),
        Cell(),
        Cell(),
    )
    return Table(
        title=CONTRACT_MILESTONES_TITLE,
        columns=columns,
        rows=tuple(_milestone_row(line, reference_date=reference_date) for line in view.milestones),
        totals=totals,
    )


def _milestone_row(line: MilestoneView, *, reference_date: date) -> Row:
    late = milestone_is_late(line.expected_on, line.situation, reference_date)
    return row(
        line.number,
        line.description,
        line.criteria,
        line.pct,
        line.value_cents,
        line.retention_cents,
        line.expected_on,
        milestone_late_days(line.expected_on, reference_date) if late else None,
        line.completed_on,
        Cell(line.situation, _MILESTONE_TONES.get(line.situation)),
        "Anexada" if line.has_evidence else "",
    )


def _claims_table(view: ContractView) -> Table:
    columns = (
        Column("Código", width=20),
        Column("Direção", width=16),
        Column("Tipo", width=14),
        Column("Causa", width=24),
        Column("Descrição", width=48),
        Column("Cláusula", width=10),
        Column("Evento", ValueKind.DATE),
        Column("Notificação", ValueKind.DATE),
        Column("Dias após o evento", ValueKind.INTEGER),
        Column("Fora do prazo", width=12),
        Column("Pleiteado", ValueKind.MONEY),
        Column("Dias pleiteados", ValueKind.INTEGER),
        Column("Reconhecido", ValueKind.MONEY),
        Column("Dias reconhecidos", ValueKind.INTEGER),
        Column("Situação", width=16),
        Column("SM", width=20),
        Column("Encerrado em", ValueKind.DATE),
    )
    return Table(
        title=CONTRACT_CLAIMS_TITLE,
        columns=columns,
        rows=tuple(_claim_row(line) for line in view.claims),
    )


def _claim_row(line: ClaimView) -> Row:
    late_tone = Tone.ERROR if line.notification_late else Tone.OK
    return row(
        line.code,
        line.direction,
        line.kind,
        line.cause,
        line.description,
        line.clause,
        line.event_date,
        line.notification_date,
        line.notification_days,
        Cell("Sim" if line.notification_late else "Não", late_tone),
        line.claimed_cents,
        line.claimed_days,
        line.recognized_cents,
        line.recognized_days,
        Cell(line.situation, _CLAIM_TONES.get(line.situation)),
        line.change_code,
        line.closed_on,
    )


def _extensions_table(view: ContractView) -> Table:
    columns = (
        Column("Código", width=20),
        Column("Claim", width=20),
        Column("Evento causador", width=48),
        Column("Solicitados", ValueKind.INTEGER),
        Column("Concedidos", ValueKind.INTEGER),
        Column("Classificação", width=26),
        Column("Método", width=28),
        Column("Marco afetado", width=32),
        Column("Solicitada em", ValueKind.DATE),
        Column("Decidida em", ValueKind.DATE),
        Column("Situação", width=22),
        Column("SM", width=20),
    )
    return Table(
        title=CONTRACT_EXTENSIONS_TITLE,
        columns=columns,
        rows=tuple(_extension_row(line) for line in view.extensions),
    )


def _extension_row(line: ExtensionView) -> Row:
    return row(
        line.code,
        line.claim_code,
        line.event,
        line.requested_days,
        line.granted_days,
        line.classification,
        line.method,
        line.affected_milestone,
        line.requested_on,
        line.decided_on,
        Cell(line.situation, _EXTENSION_TONES.get(line.situation)),
        line.change_code,
    )


# ── Avaliação de desempenho da contratada (ISSUE-034) ────────────────────


CONTRACT_EVALUATIONS_TITLE = "Avaliações"

_EVALUATION_CLASS_TONES = {"A": Tone.OK, "B": Tone.INFO, "C": Tone.WARN, "D": Tone.ERROR}


def contrato_avaliacoes_document(
    view: ContractView,
    *,
    criteria: Sequence[EvaluationCriterionSpec],
    scope_label: str,
    generated_on: date,
) -> Document:
    """As avaliações da ficha como documento: período, tipo, avaliador, critérios, nota e classe.

    Cada critério entra em uma coluna com o seu nome e a célula leva a nota e o peso congelados na
    avaliação (D5b), então mudar os parâmetros depois não muda a leitura. O mesmo conteúdo da aba
    vai para o Excel e o imprimível.
    """
    return Document(
        title=CONTRACT_TITLE.format(number=view.number),
        scope_label=scope_label,
        generated_on=generated_on,
        context=_contract_context(view),
        tables=(_evaluations_table(view, criteria=criteria),),
    )


def _evaluations_table(view: ContractView, *, criteria: Sequence[EvaluationCriterionSpec]) -> Table:
    columns = (
        Column("Período", ValueKind.DATE),
        Column("Tipo", width=10),
        Column("Avaliador", width=24),
        *(Column(criterion.name, width=14) for criterion in criteria),
        Column("Nota", ValueKind.INTEGER),
        Column("Classe", width=10),
    )
    return Table(
        title=CONTRACT_EVALUATIONS_TITLE,
        columns=columns,
        rows=tuple(_evaluation_row(line, criteria=criteria) for line in view.evaluations),
    )


def _evaluation_row(line: EvaluationView, *, criteria: Sequence[EvaluationCriterionSpec]) -> Row:
    congeladas = {item.criterion: item for item in line.criteria}
    return row(
        line.period,
        line.kind,
        line.evaluator,
        *(_criterion_note(congeladas.get(criterion.id)) for criterion in criteria),
        line.score,
        Cell(line.score_class, _EVALUATION_CLASS_TONES.get(line.score_class)),
    )


def _criterion_note(criterion: EvaluationCriterionView | None) -> str:
    return "·" if criterion is None else f"{criterion.note} · {criterion.weight}%"


# ── Visão consolidada da administração contratual (ISSUE-035) ────────────


CONTRACTS_TITLE = "Contratos: administração contratual"
CONTRACTS_TABLE_TITLE = "Contratos"
CONTRACTS_SCOPE_REFERENCE = "Contratos do escopo"
CONTRACTS_ZERO_REFERENCE = "Esperado: 0"
CONTRACTS_EXPOSURE_REFERENCE = "Esperado: R$ 0,00"
CONTRACTS_LIMIT_REFERENCE = "Limite: ≤ 10%"
CONTRACTS_EXTENSION_LIMIT = 10


def contratos_consolidado_document(
    view: ContractsOverview,
    *,
    scope_label: str,
    generated_on: date,
    filtered: ContractsOverview | None = None,
    filter_label: str = "",
) -> Document:
    """A visão consolidada como documento: os KPIs do escopo e as cinco tabelas (HU-098).

    Os KPIs e os indicadores saem do escopo inteiro, como a tela os mostra; as tabelas saem de
    ``filtered``, a cópia com os filtros aplicados (sem ela, do próprio escopo). No Portfólio a
    coluna Projeto entra pelo mecanismo genérico (HU-016) e o nome do arquivo é montado pela rota.
    """
    tables_view = view if filtered is None else filtered
    context = (("Filtro", filter_label),) if filter_label else ()
    return Document(
        title=CONTRACTS_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        context=context,
        kpis=_contratos_kpis(view),
        tables=(
            _consolidated_contracts_table(tables_view),
            _consolidated_claims_table(tables_view),
            _consolidated_extensions_table(tables_view),
            _consolidated_milestones_table(tables_view),
            _consolidated_evaluations_table(tables_view),
        ),
    )


def _contratos_kpis(view: ContractsOverview) -> tuple[Kpi, ...]:
    summary = view.summary
    indicators = view.indicators
    total_cents = sum(item.current_value_cents for item in view.contracts)
    paid_forecast = indicators.paid_forecast_percent
    average_score = indicators.average_score
    return (
        Kpi(
            "Contratos",
            summary.contracts,
            CONTRACTS_SCOPE_REFERENCE,
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{format_value(ValueKind.MONEY, total_cents)} em valor atual",
        ),
        Kpi(
            "Exposição de claims",
            indicators.contractor_exposure_cents,
            CONTRACTS_EXPOSURE_REFERENCE,
            ValueKind.MONEY,
            tone=Tone.WARN if indicators.contractor_exposure_cents else Tone.OK,
            status=_open_claims_text(summary.open_claims),
        ),
        Kpi(
            "Notificados fora do prazo",
            summary.late_notifications,
            CONTRACTS_ZERO_REFERENCE,
            ValueKind.INTEGER,
            tone=Tone.ERROR if summary.late_notifications else Tone.OK,
            status="risco de preclusão do pleito",
        ),
        Kpi(
            "Marcos atrasados",
            summary.late_milestones,
            CONTRACTS_ZERO_REFERENCE,
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.late_milestones else Tone.OK,
            status=(
                ""
                if paid_forecast is None
                else (
                    "pago "
                    f"{format_value(ValueKind.PERCENT, paid_forecast, digits=1)}"
                    " do previsto até hoje"
                )
            ),
        ),
        Kpi(
            "Extensão de prazo",
            indicators.extension_percent,
            CONTRACTS_LIMIT_REFERENCE,
            ValueKind.PERCENT,
            digits=1,
            tone=(
                Tone.WARN
                if indicators.extension_percent is not None
                and indicators.extension_percent > CONTRACTS_EXTENSION_LIMIT
                else Tone.INFO
            ),
            status=(
                f"{indicators.granted_days} de {indicators.requested_days} "
                "dias solicitados concedidos"
            ),
        ),
        Kpi(
            "Contratadas C ou D",
            summary.contractors_c_or_d,
            CONTRACTS_ZERO_REFERENCE,
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.contractors_c_or_d else Tone.OK,
            status=(
                ""
                if average_score is None
                else f"nota média {format_value(ValueKind.DECIMAL, average_score, digits=1)}"
            ),
        ),
    )


def _open_claims_text(count: int) -> str:
    if count == 1:
        return "1 claim aberto"
    return f"{count} claims abertos"


def _evaluation_text(evaluation: EvaluationView | None) -> str:
    if evaluation is None or not evaluation.score_class:
        return ""
    if evaluation.score is None:
        return evaluation.score_class
    return f"{evaluation.score_class} ({evaluation.score})"


def _period_label(period: date) -> str:
    return period.strftime("%m/%Y")


def _consolidated_contracts_table(view: ContractsOverview) -> Table:
    return Table(
        title=CONTRACTS_TABLE_TITLE,
        columns=(
            Column("Nº", width=16),
            Column("Contratada", width=32),
            Column("Objeto", width=40),
            Column("Modalidade", width=18),
            Column("Valor atual", ValueKind.MONEY),
            Column("Medido", ValueKind.PERCENT, digits=1),
            Column("Saldo a faturar", ValueKind.MONEY),
            Column("Término vigente", ValueKind.DATE),
            Column("Dias aditados", ValueKind.INTEGER),
            Column("Claims abertos", ValueKind.INTEGER),
            Column("Última avaliação", width=16),
        ),
        rows=tuple(
            row(
                item.number,
                item.company,
                item.object,
                item.modality,
                item.current_value_cents,
                item.measured_pct,
                item.balance_to_invoice_cents,
                item.current_end,
                item.days_added,
                item.open_claims,
                Cell(
                    _evaluation_text(item.last_evaluation),
                    _EVALUATION_CLASS_TONES.get(
                        item.last_evaluation.score_class if item.last_evaluation else ""
                    ),
                ),
                project=item.project_label,
            )
            for item in view.contracts
        ),
    )


def _consolidated_claims_table(view: ContractsOverview) -> Table:
    return Table(
        title=CONTRACT_CLAIMS_TITLE,
        columns=(
            Column("Código", width=20),
            Column("Contrato", width=16),
            Column("Direção", width=16),
            Column("Tipo", width=14),
            Column("Causa", width=24),
            Column("Descrição", width=48),
            Column("Evento", ValueKind.DATE),
            Column("Notificação", ValueKind.DATE),
            Column("Dias após o evento", ValueKind.INTEGER),
            Column("Fora do prazo", width=12),
            Column("Pleiteado", ValueKind.MONEY),
            Column("Dias pleiteados", ValueKind.INTEGER),
            Column("Reconhecido", ValueKind.MONEY),
            Column("Dias reconhecidos", ValueKind.INTEGER),
            Column("Situação", width=18),
        ),
        rows=tuple(
            row(
                item.code,
                item.contract_number,
                item.direction,
                item.kind,
                item.cause,
                item.description,
                item.event_date,
                item.notification_date,
                item.notification_days,
                Cell(
                    "Sim" if item.notification_late else "Não",
                    Tone.ERROR if item.notification_late else Tone.OK,
                ),
                item.claimed_cents,
                item.claimed_days,
                item.recognized_cents,
                item.recognized_days,
                Cell(item.situation, _CLAIM_TONES.get(item.situation)),
                project=item.project_label,
            )
            for item in view.claims
        ),
    )


def _consolidated_extensions_table(view: ContractsOverview) -> Table:
    return Table(
        title=CONTRACT_EXTENSIONS_TITLE,
        columns=(
            Column("Código", width=20),
            Column("Contrato", width=16),
            Column("Claim", width=20),
            Column("Evento causador", width=48),
            Column("Solicitados", ValueKind.INTEGER),
            Column("Concedidos", ValueKind.INTEGER),
            Column("Classificação", width=26),
            Column("Método", width=28),
            Column("Marco afetado", width=32),
            Column("Solicitada em", ValueKind.DATE),
            Column("Decidida em", ValueKind.DATE),
            Column("Situação", width=22),
        ),
        rows=tuple(
            row(
                item.code,
                item.contract_number,
                item.claim_code,
                item.event,
                item.requested_days,
                item.granted_days,
                item.classification,
                item.method,
                item.affected_milestone,
                item.requested_on,
                item.decided_on,
                Cell(item.situation, _EXTENSION_TONES.get(item.situation)),
                project=item.project_label,
            )
            for item in view.extensions
        ),
    )


def _consolidated_milestones_table(view: ContractsOverview) -> Table:
    return Table(
        title=CONTRACT_MILESTONES_TITLE,
        columns=(
            Column("Contrato", width=16),
            Column("Nº", width=10),
            Column("Marco", width=44),
            Column("Critério de aceite", width=40),
            Column("%", ValueKind.INTEGER),
            Column("Valor", ValueKind.MONEY),
            Column("Prevista", ValueKind.DATE),
            Column("Atraso (dias)", ValueKind.INTEGER),
            Column("Conclusão", ValueKind.DATE),
            Column("Situação", width=18),
        ),
        rows=tuple(
            row(
                item.contract_number,
                item.number,
                item.description,
                item.criteria,
                item.pct,
                item.value_cents,
                item.expected_on,
                Cell(item.late_days, Tone.ERROR) if item.is_late else None,
                item.completed_on,
                Cell(item.situation, _MILESTONE_TONES.get(item.situation)),
                project=item.project_label,
            )
            for item in view.milestones
        ),
    )


def _consolidated_evaluations_table(view: ContractsOverview) -> Table:
    return Table(
        title=CONTRACT_EVALUATIONS_TITLE,
        columns=(
            Column("Contrato", width=16),
            Column("Contratada", width=32),
            Column("Período", width=12),
            Column("Tipo", width=10),
            Column("Avaliador", width=24),
            Column("Nota", ValueKind.INTEGER),
            Column("Classe", width=10),
            Column("Plano de melhoria", width=16),
            Column("Comentário", width=48),
        ),
        rows=tuple(
            row(
                item.contract_number,
                item.company,
                _period_label(item.view.period),
                item.view.kind,
                item.view.evaluator,
                item.view.score,
                Cell(item.view.score_class, _EVALUATION_CLASS_TONES.get(item.view.score_class)),
                "Exigido" if item.view.requires_plan else "",
                item.view.comment,
                project=item.project_label,
            )
            for item in view.evaluations
        ),
    )


# ── Contingência e reservas (ISSUE-041) ──────────────────────────────────


CONTINGENCY_TITLE = "Contingência e reservas"
CONTINGENCY_CHART_TITLE = "Saldo da contingência"
CONTINGENCY_BURN_TITLE = "Saldo real x previsto"
CONTINGENCY_COMPOSITION_TITLE = "Linha de base de custo e reservas"
CONTINGENCY_MOVEMENTS_TITLE = "Extrato de movimentos"
CONTINGENCY_PROJECTS_TITLE = "Reservas por projeto"

CONTINGENCY_KPI_SALDO = "Saldo da contingência"
CONTINGENCY_KPI_CONSUMPTION = "Consumo da contingência"
CONTINGENCY_KPI_ANALYSIS = "Pedido em SMs em análise"
CONTINGENCY_KPI_MANAGEMENT = "Reserva gerencial"

CONTINGENCY_MANAGEMENT_STATUS = "fora da linha de base · só o Comitê libera"
CONTINGENCY_NO_VALUE = "·"
CONTINGENCY_MIL_CENTS = 100_000
CONTINGENCY_MIL_ONE_PLACE = Decimal("0.1")

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


def contingencia_document(
    view: ContingencyOverview, *, scope_label: str, generated_on: date
) -> Document:
    """A tela de Contingência como documento: os indicadores, o gráfico, a composição e o extrato.

    ``scope_label`` é a linha do escopo (``describe_scope``), montada pela rota. O Excel não tem
    gráfico: os números do burn vão na tabela "Saldo da contingência", para nenhum dos dois ter
    menos que o outro. No Portfólio a tabela por projeto entra antes do extrato e a coluna Projeto
    vem pelo mecanismo genérico (HU-016).
    """
    return Document(
        title=CONTINGENCY_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        kpis=contingencia_kpis(view),
        charts=(Chart(CONTINGENCY_CHART_TITLE, "linhas-multiplas", contingencia_chart(view)),),
        tables=_contingencia_tables(view),
    )


def contingencia_kpis(view: ContingencyOverview) -> tuple[Kpi, ...]:
    """Os quatro indicadores da tela, com a referência de gestão e a situação em palavras."""
    contingency = view.contingency
    management = view.management
    consumption_high = _contingency_consumption_high(view)
    return (
        Kpi(
            CONTINGENCY_KPI_SALDO,
            contingency.balance_cents if contingency is not None else None,
            f"Previsto: {_contingency_money(view.expected_balance_cents)}",
            ValueKind.MONEY,
            tone=_contingency_balance_tone(view),
            status=_contingency_balance_status(contingency),
        ),
        Kpi(
            CONTINGENCY_KPI_CONSUMPTION,
            contingency.consumption_pct if contingency is not None else None,
            f"Limite: {_contingency_percent(view.consumption_limit_pct)}",
            ValueKind.PERCENT,
            digits=1,
            tone=(
                Tone.WARN
                if consumption_high
                else Tone.OK
                if contingency is not None
                else Tone.NEUTRAL
            ),
            status=_contingency_limit_status(view),
        ),
        Kpi(
            CONTINGENCY_KPI_ANALYSIS,
            contingency.in_analysis_cents if contingency is not None else None,
            "Saldo se aprovadas: "
            f"{_contingency_money(contingency.balance_after_analysis_cents if contingency else None)}",
            ValueKind.MONEY,
            tone=_contingency_analysis_tone(contingency),
            status=_contingency_analysis_status(view.analysis_count),
        ),
        Kpi(
            CONTINGENCY_KPI_MANAGEMENT,
            management.balance_cents if management is not None else None,
            f"Constituída: {_contingency_money(management.total_cents if management else None)}",
            ValueKind.MONEY,
            tone=(
                Tone.WARN
                if management is not None and management.balance_cents < management.total_cents
                else Tone.INFO
                if management is not None
                else Tone.NEUTRAL
            ),
            status=CONTINGENCY_MANAGEMENT_STATUS,
        ),
    )


def contingencia_chart(view: ContingencyOverview) -> dict[str, object]:
    """O ``data-dados`` do saldo real x previsto (linhas-multiplas), em R$ mil.

    O real é o saldo após os consumos e liberações do mês e fica nulo depois do corte; o previsto
    é o constituído menos a parte vencida pelo avanço planejado, como o protótipo o desenhava.
    """
    return {
        "titulo": CONTINGENCY_CHART_TITLE,
        "casas": 0,
        "unidade": "",
        "series": [
            {"id": "real", "rotulo": "Saldo real", "papel": "realizado"},
            {"id": "previsto", "rotulo": "Saldo previsto pelo avanço", "papel": "linha-base"},
        ],
        "periodos": [
            {
                "ano": point.month.year,
                "mes": point.month.month,
                "valores": {
                    "real": None
                    if point.actual_cents is None
                    else _contingency_mil(point.actual_cents),
                    "previsto": _contingency_mil(point.expected_cents),
                },
            }
            for point in view.burn
        ],
    }


def _contingencia_tables(view: ContingencyOverview) -> tuple[Table, ...]:
    tables = [
        _contingencia_composition_table(view),
        _contingencia_burn_table(view),
        _contingencia_movements_table(view),
    ]
    if view.is_portfolio:
        tables.insert(0, _contingencia_projects_table(view))
    return tuple(tables)


def _contingencia_composition_table(view: ContingencyOverview) -> Table:
    contingency = view.contingency.balance_cents if view.contingency else 0
    management = view.management.balance_cents if view.management else 0
    return Table(
        title=CONTINGENCY_COMPOSITION_TITLE,
        columns=(Column("Composição", width=52), Column("Valor", ValueKind.MONEY)),
        rows=(
            row("Orçado atual da EAC (linha de base de medição)", view.eac_current_cents),
            row("Saldo da reserva de contingência", contingency),
            row("Linha de base de custo", view.cost_baseline_cents),
            row("Saldo da reserva gerencial", management),
            row("Orçamento do projeto", view.project_budget_cents),
        ),
        per_project=False,
    )


def _contingencia_burn_table(view: ContingencyOverview) -> Table:
    return Table(
        title=CONTINGENCY_BURN_TITLE,
        columns=(
            Column("Mês", width=12),
            Column("Saldo previsto", ValueKind.MONEY),
            Column("Saldo real", ValueKind.MONEY),
        ),
        rows=tuple(
            row(_month_label(point.month), point.expected_cents, point.actual_cents)
            for point in view.burn
        ),
        per_project=False,
    )


def _contingencia_movements_table(view: ContingencyOverview) -> Table:
    return Table(
        title=CONTINGENCY_MOVEMENTS_TITLE,
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Reserva", width=14),
            Column("Movimento", width=14),
            Column("Descrição", width=48),
            Column("SM", width=20),
            Column("Situação", width=18),
            Column("Valor", ValueKind.MONEY),
            Column("Saldo", ValueKind.MONEY),
        ),
        rows=tuple(
            row(
                line.on,
                line.reserve_kind,
                line.kind,
                line.description,
                line.change_code,
                line.situation,
                line.value_cents,
                line.balance_cents,
                project=line.project_label,
            )
            for line in view.movements
        ),
    )


def _contingencia_projects_table(view: ContingencyOverview) -> Table:
    columns = (
        Column("Projeto", width=32),
        Column("Constituída", ValueKind.MONEY),
        Column("Consumida", ValueKind.MONEY),
        Column("Saldo", ValueKind.MONEY),
        Column("Consumo", ValueKind.PERCENT, digits=1),
        Column("Em análise", ValueKind.MONEY),
        Column("Reserva gerencial", ValueKind.MONEY),
    )
    return Table(
        title=CONTINGENCY_PROJECTS_TITLE,
        columns=columns,
        rows=tuple(_contingencia_project_row(item) for item in view.projects),
        totals=_contingencia_projects_totals(view),
        per_project=False,
    )


def _contingencia_project_row(item: ContingencyProjectRow) -> Row:
    contingency = item.contingency
    management = item.management
    return row(
        item.project_label,
        contingency.total_cents if contingency else None,
        contingency.consumed_cents if contingency else None,
        contingency.balance_cents if contingency else None,
        (
            Cell(contingency.consumption_pct, _contingency_row_tone(item, contingency))
            if contingency
            else None
        ),
        contingency.in_analysis_cents if contingency else None,
        management.balance_cents if management else None,
    )


def _contingencia_projects_totals(view: ContingencyOverview) -> tuple[Cell, ...]:
    contingency = view.contingency
    management = view.management
    return (
        Cell("Total"),
        Cell(contingency.total_cents if contingency else None),
        Cell(contingency.consumed_cents if contingency else None),
        Cell(contingency.balance_cents if contingency else None),
        Cell(contingency.consumption_pct if contingency else None),
        Cell(contingency.in_analysis_cents if contingency else None),
        Cell(management.balance_cents if management else None),
    )


def _contingency_row_tone(item: ContingencyProjectRow, contingency: ReserveLine) -> Tone | None:
    limit = item.consumption_limit_pct
    pct = contingency.consumption_pct
    if limit is None or pct is None or pct <= limit:
        return None
    return Tone.ERROR


def _contingency_consumption_high(view: ContingencyOverview) -> bool:
    contingency = view.contingency
    if contingency is None or contingency.consumption_pct is None:
        return False
    limit = view.consumption_limit_pct
    return limit is not None and contingency.consumption_pct > limit


def _contingency_balance_tone(view: ContingencyOverview) -> Tone:
    contingency = view.contingency
    if contingency is None:
        return Tone.NEUTRAL
    if contingency.balance_cents < 0:
        return Tone.ERROR
    return Tone.WARN if _contingency_consumption_high(view) else Tone.OK


def _contingency_analysis_tone(contingency: ReserveLine | None) -> Tone:
    if contingency is None:
        return Tone.NEUTRAL
    if contingency.in_analysis_cents > contingency.balance_cents:
        return Tone.ERROR
    return Tone.WARN if contingency.in_analysis_cents else Tone.OK


def _contingency_balance_status(contingency: ReserveLine | None) -> str:
    if contingency is None:
        return ""
    status = (
        f"constituída {_contingency_money(contingency.total_cents)}"
        f" · consumida {_contingency_money(contingency.consumed_cents)}"
    )
    if contingency.released_cents:
        status += f" · liberada {_contingency_money(contingency.released_cents)}"
    return status


def _contingency_limit_status(view: ContingencyOverview) -> str:
    physical = view.physical_actual
    advance = (
        CONTINGENCY_NO_VALUE if physical is None else format_value(ValueKind.DECIMAL, physical, 1)
    )
    return (
        f"avanço físico real {advance} + tolerância de "
        f"{_contingency_points(view.tolerance_pp)} p.p."
    )


def _contingency_analysis_status(count: int) -> str:
    if count == 1:
        return "1 SM aguardando decisão"
    return f"{count} SMs aguardando decisão"


def _contingency_money(cents: int | None) -> str:
    return CONTINGENCY_NO_VALUE if cents is None else format_value(ValueKind.MONEY, cents)


def _contingency_percent(value: Decimal | None) -> str:
    return CONTINGENCY_NO_VALUE if value is None else format_value(ValueKind.PERCENT, value, 1)


def _contingency_points(value: Decimal) -> str:
    text = format_value(ValueKind.DECIMAL, value, 1)
    return text[:-2] if text.endswith(",0") else text


def _contingency_mil(cents: int) -> float:
    return float(
        (Decimal(cents) / CONTINGENCY_MIL_CENTS).quantize(
            CONTINGENCY_MIL_ONE_PLACE, rounding=ROUND_HALF_UP
        )
    )


def _month_label(month: date) -> str:
    return f"{MONTH_NAMES[month.month - 1]}/{month.year}"


# ── Curva S financeira e KPIs de custo (ISSUE-042) ───────────────────────


CURVA_FINANCEIRA_TITLE = "Curva S financeira"
CURVA_FINANCEIRA_POINTS_TITLE = "Período a período"
CURVA_FINANCEIRA_CHART_TITLE = "Curva S financeira"
CUSTOS_KPIS_TITLE = "KPIs de custo"
CUSTOS_KPIS_CHART_TITLE = "CPI e SPI por mês"
CUSTOS_KPIS_VALUE_CHART_TITLE = "Valor agregado acumulado"
CUSTOS_KPIS_SUMMARY_TITLE = "Valor agregado na data de corte"
CUSTOS_KPIS_POINTS_TITLE = "Período a período"
CUSTOS_KPIS_PROJECTS_TITLE = "Desempenho de custo por projeto"

CUSTOS_KPIS_INDEX_REFERENCE = "Meta: ≥ 1,00"
CUSTOS_KPIS_VARIATION_REFERENCE = "Meta: ≥ 0"

FINANCIAL_NO_VALUE = "·"
FINANCIAL_MIL_CENTS = 100_000
FINANCIAL_MIL_ONE_PLACE = Decimal("0.1")


@dataclass(frozen=True)
class CustosResumoItem:
    """Uma linha do resumo do valor agregado: a sigla, o nome, o valor, o tom e a leitura."""

    sigla: str
    nome: str
    value: int | Decimal | None
    kind: ValueKind
    tone: Tone | None
    leitura: str


def curva_financeira_document(
    view: FinancialCurveOverview, *, scope_label: str, generated_on: date
) -> Document:
    """A Curva S financeira como documento: os indicadores, o gráfico e a tabela período a período.

    ``scope_label`` é a linha do escopo (``describe_scope``), montada pela rota. A tabela vale para
    o projeto e para o Portfólio: a série da carteira já é a soma em reais dos projetos.
    """
    return Document(
        title=CURVA_FINANCEIRA_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        context=_curva_financeira_context(view),
        kpis=curva_financeira_kpis(view),
        charts=(
            Chart(CURVA_FINANCEIRA_CHART_TITLE, "curva-s-linha", curva_financeira_chart(view)),
        ),
        tables=(_curva_financeira_points_table(view),),
    )


def curva_financeira_kpis(view: FinancialCurveOverview) -> tuple[Kpi, ...]:
    """Os quatro indicadores da Curva S financeira, os mesmos da faixa do topo da tela."""
    kpis = view.kpis
    if kpis is None:
        return ()
    cut = _financial_cut_month(view)
    return (
        Kpi(
            "Planejado acumulado",
            kpis.planned_cents,
            f"Orçado: {_financial_money(kpis.budget_cents)}",
            ValueKind.MONEY,
            tone=Tone.INFO,
            status=(
                f"linha de base de custo em {curva_financeira_month_label(cut)}" if cut else ""
            ),
        ),
        Kpi(
            "Realizado acumulado",
            kpis.actual_cents,
            f"Previsto: {_financial_money(kpis.planned_cents)}",
            ValueKind.MONEY,
            tone=Tone.INFO,
            status=_financial_deviation_status(kpis.deviation_cents),
        ),
        Kpi(
            "Comprometido acumulado",
            kpis.committed_cents,
            f"Orçado: {_financial_money(kpis.budget_cents)}",
            ValueKind.MONEY,
            tone=Tone.INFO,
            status=(
                f"{format_value(ValueKind.PERCENT, kpis.committed_pct, 1)} do orçamento"
                if kpis.committed_pct is not None
                else ""
            ),
        ),
        Kpi(
            "Projeção no término",
            kpis.trend_cents,
            f"Orçado: {_financial_money(kpis.budget_cents)}",
            ValueKind.MONEY,
            tone=(
                Tone.NEUTRAL
                if kpis.trend_cents is None
                else Tone.ERROR
                if kpis.trend_cents > kpis.budget_cents
                else Tone.OK
            ),
            status=_financial_trend_status(kpis.trend_cents, kpis.budget_cents),
        ),
    )


def _financial_trend_status(trend_cents: int | None, budget_cents: int) -> str:
    if trend_cents is None:
        return ""
    above = trend_cents > budget_cents
    return (
        "projeção acima do orçado pelo desempenho (BAC ÷ CPI)"
        if above
        else "projeção dentro do orçado pelo desempenho (BAC ÷ CPI)"
    )


def _financial_deviation_status(deviation_cents: int | None) -> str:
    if deviation_cents is None:
        return ""
    return f"{_financial_signed_money(deviation_cents)} em relação ao planejado"


def curva_financeira_chart(view: FinancialCurveOverview) -> dict[str, object]:
    """O ``data-dados`` da Curva S financeira (curva-s-linha), em R$ mil.

    As quatro séries acumuladas: o planejado congelado, o comprometido e o realizado até o corte e a
    tendência a partir dele. Um mês sem valor de uma série quebra a linha dela.
    """
    series = view.series
    return {
        "titulo": (
            f"{CURVA_FINANCEIRA_CHART_TITLE} da carteira"
            if view.is_portfolio
            else CURVA_FINANCEIRA_CHART_TITLE
        ),
        "modo": "acumulado",
        "formato": "numero",
        "unidade": "",
        "casas": 0,
        "series": [
            {"id": "planejado", "rotulo": "Planejado", "papel": "linha-base"},
            {"id": "comprometido", "rotulo": "Comprometido", "papel": "comprometido"},
            {"id": "realizado", "rotulo": "Realizado", "papel": "realizado"},
            {"id": "tendencia", "rotulo": "Tendência", "papel": "tendencia"},
        ],
        "periodos": [
            {
                "ano": month.year,
                "mes": month.month,
                "valores": {
                    "planejado": _financial_mil(series.planned[index]),
                    "comprometido": _financial_mil_or_none(series.committed[index]),
                    "realizado": _financial_mil_or_none(series.actual[index]),
                    "tendencia": _financial_mil_or_none(series.trend[index]),
                },
            }
            for index, month in enumerate(series.months)
        ],
    }


def _curva_financeira_context(view: FinancialCurveOverview) -> tuple[tuple[str, str], ...]:
    lines = [("Referência", format_value(ValueKind.DATE, view.reference_date))]
    cut = _financial_cut_month(view)
    if cut is not None:
        lines.append(("Corte", curva_financeira_month_label(cut)))
    if view.revision is not None and view.revision_date is not None:
        lines.append(
            (
                "Revisão da EAC",
                f"Rev {view.revision} de {format_value(ValueKind.DATE, view.revision_date)}",
            )
        )
    return tuple(lines)


def _curva_financeira_points_table(view: FinancialCurveOverview) -> Table:
    return Table(
        title=CURVA_FINANCEIRA_POINTS_TITLE,
        columns=(
            Column("Mês", width=16),
            Column("Planejado no mês", ValueKind.MONEY),
            Column("Planejado acumulado", ValueKind.MONEY),
            Column("Comprometido acumulado", ValueKind.MONEY),
            Column("Realizado no mês", ValueKind.MONEY),
            Column("Realizado acumulado", ValueKind.MONEY),
            Column("Projeção acumulada", ValueKind.MONEY),
            Column("Realizado menos planejado", ValueKind.MONEY),
        ),
        rows=tuple(_curva_financeira_point_row(view, index) for index in range(len(view.points))),
        per_project=False,
    )


def _curva_financeira_point_row(view: FinancialCurveOverview, index: int) -> Row:
    point = view.points[index]
    previous = view.points[index - 1] if index > 0 else None
    planned_month = point.planned_cents - (previous.planned_cents if previous else 0)
    actual_month = (
        None
        if point.actual_cents is None
        else point.actual_cents
        - (previous.actual_cents if previous and previous.actual_cents is not None else 0)
    )
    deviation = None if point.actual_cents is None else point.actual_cents - point.planned_cents
    label = curva_financeira_month_label(point.month) + (" · corte" if point.is_cut else "")
    return row(
        label,
        planned_month,
        point.planned_cents,
        point.committed_cents,
        actual_month,
        point.actual_cents,
        point.trend_cents,
        Cell(deviation, None if deviation is None else _deviation_tone(deviation)),
    )


def custos_kpis_document(
    view: CostKpisOverview, *, scope_label: str, generated_on: date
) -> Document:
    """Os KPIs de custo como documento: os indicadores, os dois gráficos e as três tabelas.

    No Portfólio a tabela de desempenho por projeto entra antes do resumo do valor agregado, e a
    coluna Projeto vem pelo mecanismo genérico (HU-016).
    """
    tables: list[Table] = []
    if view.is_portfolio:
        tables.append(_custos_kpis_projects_table(view))
    tables.append(_custos_kpis_summary_table(view))
    tables.append(_custos_kpis_value_table(view))
    return Document(
        title=CUSTOS_KPIS_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        context=_custos_kpis_context(view),
        kpis=custos_kpis(view),
        charts=(
            Chart(CUSTOS_KPIS_CHART_TITLE, "linhas-multiplas", custos_kpis_chart(view)),
            Chart(CUSTOS_KPIS_VALUE_CHART_TITLE, "linhas-multiplas", custos_valor_chart(view)),
        ),
        tables=tuple(tables),
    )


def custos_kpis(view: CostKpisOverview) -> tuple[Kpi, ...]:
    """Os seis indicadores da tela, com a referência de gestão e a variação no rodapé."""
    indicators = view.indicators
    actual = view.actual
    if indicators is None or actual is None:
        return ()
    previous = view.previous
    return (
        Kpi(
            "CPI (desempenho de custo)",
            indicators.cpi,
            CUSTOS_KPIS_INDEX_REFERENCE,
            ValueKind.DECIMAL,
            digits=2,
            tone=financial_index_tone(indicators.cpi),
            status=_financial_index_status(indicators.cpi, previous.cpi if previous else None),
        ),
        Kpi(
            "SPI de custo (desempenho de prazo)",
            indicators.spi,
            CUSTOS_KPIS_INDEX_REFERENCE,
            ValueKind.DECIMAL,
            digits=2,
            tone=financial_index_tone(indicators.spi),
            status=_financial_index_status(indicators.spi, previous.spi if previous else None),
        ),
        Kpi(
            "CV (variação de custo)",
            actual.cv_cents,
            CUSTOS_KPIS_VARIATION_REFERENCE,
            ValueKind.MONEY,
            tone=Tone.ERROR if actual.cv_cents < 0 else Tone.OK,
            status=(
                f"EV menos AC · mês anterior {_financial_signed_money(previous.cv_cents)}"
                if previous is not None
                else "EV menos AC"
            ),
        ),
        Kpi(
            "VAC (variação no término)",
            view.vac_cents,
            CUSTOS_KPIS_VARIATION_REFERENCE,
            ValueKind.MONEY,
            tone=(
                Tone.NEUTRAL
                if view.vac_cents is None
                else Tone.ERROR
                if view.vac_cents < 0
                else Tone.OK
            ),
            status="orçamento menos projeção no término",
        ),
        Kpi(
            "Contingência consumida",
            view.contingency_pct,
            f"Constituída: {_financial_money(view.contingency_total_cents)}",
            ValueKind.PERCENT,
            digits=1,
            tone=(
                Tone.WARN
                if view.contingency_pct is not None and view.contingency_pct > Decimal("50")
                else Tone.OK
            ),
            status=(
                f"{_financial_money(view.contingency_consumed_cents)} de "
                f"{_financial_money(view.contingency_total_cents)}"
            ),
        ),
        Kpi(
            "Comprometido",
            view.committed_pct,
            f"Orçado: {_financial_money(view.budget_cents)}",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
            status=(
                f"{_financial_money(view.committed_cents)} do orçamento"
                if view.committed_cents is not None
                else ""
            ),
        ),
    )


def _financial_index_status(current: Decimal | None, previous: Decimal | None) -> str:
    if current is None or previous is None:
        return ""
    delta = current - previous
    if delta == 0:
        return "estável vs. mês anterior"
    sign = "+" if delta > 0 else "-"
    return f"{sign}{format_value(ValueKind.DECIMAL, abs(delta), 2)} vs. mês anterior"


def custos_kpis_chart(view: CostKpisOverview) -> dict[str, object]:
    """O ``data-dados`` do CPI e do SPI mês a mês (linhas-multiplas), com a meta em 1,00.

    Só os meses com valor agregado entram: depois do corte não há realizado e não há índice. O eixo
    se ajusta ao dado (``base_zero`` falso), como a biblioteca recomenda para índices.
    """
    return {
        "titulo": CUSTOS_KPIS_CHART_TITLE,
        "base_zero": False,
        "casas": 2,
        "unidade": "",
        "series": [
            {"id": "cpi", "rotulo": "CPI", "papel": "realizado"},
            {"id": "spi", "rotulo": "SPI", "papel": "previsto"},
        ],
        "referencias": [{"valor": 1, "rotulo": "Meta (1,00)", "papel": "linha-base"}],
        "periodos": [
            {
                "ano": row.month.year,
                "mes": row.month.month,
                "valores": {
                    "cpi": None if row.cpi is None else float(row.cpi),
                    "spi": None if row.spi is None else float(row.spi),
                },
            }
            for row in view.history
        ],
    }


def _custos_kpis_context(view: CostKpisOverview) -> tuple[tuple[str, str], ...]:
    lines = [("Referência", format_value(ValueKind.DATE, view.reference_date))]
    if view.cut_month is not None:
        lines.append(("Corte", curva_financeira_month_label(view.cut_month)))
    return tuple(lines)


def custos_valor_chart(view: CostKpisOverview) -> dict[str, object]:
    """O ``data-dados`` do valor agregado acumulado (linhas-multiplas), em R$ mil.

    As três séries acumuladas de cada mês até o corte: o PV da linha de base, o EV do avanço físico
    real e o AC do realizado do ERP.
    """
    return {
        "titulo": CUSTOS_KPIS_VALUE_CHART_TITLE,
        "formato": "numero",
        "unidade": "",
        "casas": 0,
        "series": [
            {"id": "pv", "rotulo": "PV (planejado)", "papel": "linha-base"},
            {"id": "ev", "rotulo": "EV (agregado)", "papel": "realizado"},
            {"id": "ac", "rotulo": "AC (custo real)", "papel": "previsto"},
        ],
        "periodos": [
            {
                "ano": row.month.year,
                "mes": row.month.month,
                "valores": {
                    "pv": _financial_mil(row.pv_cents),
                    "ev": _financial_mil(row.ev_cents),
                    "ac": _financial_mil(row.ac_cents),
                },
            }
            for row in view.history
        ],
    }


def custos_kpis_resumo(view: CostKpisOverview) -> tuple[CustosResumoItem, ...]:
    """As dez linhas do resumo do valor agregado, com a leitura do protótipo."""
    indicators = view.indicators
    actual = view.actual
    if indicators is None or actual is None:
        return ()
    return (
        CustosResumoItem(
            "BAC",
            "Orçamento no término",
            view.budget_cents,
            ValueKind.MONEY,
            None,
            "Orçado atual da EAC",
        ),
        CustosResumoItem(
            "PV",
            "Valor planejado",
            actual.pv_cents,
            ValueKind.MONEY,
            None,
            "Avanço físico previsto x BAC",
        ),
        CustosResumoItem(
            "EV",
            "Valor agregado",
            actual.ev_cents,
            ValueKind.MONEY,
            None,
            "Avanço físico real x BAC",
        ),
        CustosResumoItem(
            "AC", "Custo real", actual.ac_cents, ValueKind.MONEY, None, "Realizado acumulado"
        ),
        CustosResumoItem(
            "CV",
            "Variação de custo",
            actual.cv_cents,
            ValueKind.MONEY,
            _financial_variance_tone(actual.cv_cents),
            "Gastou mais do que agregou" if actual.cv_cents < 0 else "Agregou mais do que gastou",
        ),
        CustosResumoItem(
            "SV",
            "Variação de prazo",
            actual.sv_cents,
            ValueKind.MONEY,
            _financial_variance_tone(actual.sv_cents),
            "Agregou menos do que o planejado"
            if actual.sv_cents < 0
            else "Agregou mais do que o planejado",
        ),
        CustosResumoItem(
            "EAC (CPI)",
            "Estimativa no término pelo CPI",
            indicators.eac_by_cpi_cents,
            ValueKind.MONEY,
            None,
            "BAC ÷ CPI: se o desempenho de custo se mantiver",
        ),
        CustosResumoItem(
            "Projeção",
            "Projeção no término (bottom-up)",
            view.projection_cents,
            ValueKind.MONEY,
            None,
            "Soma das projeções dos responsáveis por item",
        ),
        CustosResumoItem(
            "VAC",
            "Variação no término",
            view.vac_cents,
            ValueKind.MONEY,
            _financial_variance_tone(view.vac_cents),
            "BAC menos projeção no término",
        ),
        CustosResumoItem(
            "TCPI",
            "Índice de desempenho a completar",
            indicators.tcpi,
            ValueKind.DECIMAL,
            financial_index_tone(indicators.tcpi),
            "Precisa render mais do que até agora para fechar no BAC"
            if indicators.tcpi is not None and indicators.tcpi > 1
            else "Fecha no BAC mantendo o ritmo",
        ),
    )


def _custos_kpis_summary_table(view: CostKpisOverview) -> Table:
    return Table(
        title=CUSTOS_KPIS_SUMMARY_TITLE,
        columns=(
            Column("Indicador", width=16),
            Column("Descrição", width=36),
            Column("Valor", ValueKind.MONEY),
            Column("Índice", ValueKind.DECIMAL, digits=2),
            Column("Leitura", width=48),
        ),
        rows=tuple(_custos_kpis_summary_row(item) for item in custos_kpis_resumo(view)),
        per_project=False,
    )


def _custos_kpis_summary_row(item: CustosResumoItem) -> Row:
    money = Cell(item.value, item.tone) if item.kind is ValueKind.MONEY else Cell()
    index = Cell(item.value, item.tone) if item.kind is ValueKind.DECIMAL else Cell()
    return row(item.sigla, item.nome, money, index, item.leitura)


def _custos_kpis_value_table(view: CostKpisOverview) -> Table:
    return Table(
        title=CUSTOS_KPIS_POINTS_TITLE,
        columns=(
            Column("Mês", width=16),
            Column("PV", ValueKind.MONEY),
            Column("EV", ValueKind.MONEY),
            Column("AC", ValueKind.MONEY),
            Column("CV", ValueKind.MONEY),
            Column("SV", ValueKind.MONEY),
            Column("CPI", ValueKind.DECIMAL, digits=2),
            Column("SPI", ValueKind.DECIMAL, digits=2),
            Column("EAC pelo CPI", ValueKind.MONEY),
            Column("TCPI", ValueKind.DECIMAL, digits=2),
        ),
        rows=tuple(
            _custos_kpis_value_row(row, cut=row.month == view.cut_month) for row in view.history
        ),
        per_project=False,
    )


def _custos_kpis_value_row(item: CostKpiMonth, *, cut: bool) -> Row:
    label = curva_financeira_month_label(item.month) + (" · corte" if cut else "")
    return row(
        label,
        item.pv_cents,
        item.ev_cents,
        item.ac_cents,
        Cell(item.cv_cents, _financial_variance_tone(item.cv_cents)),
        Cell(item.sv_cents, _financial_variance_tone(item.sv_cents)),
        Cell(item.cpi, financial_index_tone(item.cpi)),
        Cell(item.spi, financial_index_tone(item.spi)),
        item.eac_by_cpi_cents,
        item.tcpi,
    )


def _custos_kpis_projects_table(view: CostKpisOverview) -> Table:
    return Table(
        title=CUSTOS_KPIS_PROJECTS_TITLE,
        columns=(
            Column("BAC", ValueKind.MONEY),
            Column("EV", ValueKind.MONEY),
            Column("AC", ValueKind.MONEY),
            Column("CPI", ValueKind.DECIMAL, digits=2),
            Column("SPI", ValueKind.DECIMAL, digits=2),
            Column("Projeção no término", ValueKind.MONEY),
            Column("VAC", ValueKind.MONEY),
            Column("Contingência consumida", ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(_custos_kpis_project_row(item) for item in view.projects),
    )


def _custos_kpis_project_row(item: CostKpiProjectRow) -> Row:
    return row(
        item.bac_cents,
        item.ev_cents,
        item.ac_cents,
        Cell(item.cpi, financial_index_tone(item.cpi)),
        Cell(item.spi, financial_index_tone(item.spi)),
        item.projection_cents,
        Cell(item.vac_cents, _financial_variance_tone(item.vac_cents)),
        item.contingency_pct,
        project=item.project_label,
    )


def _financial_variance_tone(value: int | None) -> Tone | None:
    """A cor de um desvio de custo: negativo em erro, zero ou positivo em ok; sem valor, sem cor."""
    if value is None:
        return None
    return Tone.ERROR if value < 0 else Tone.OK


def financial_index_tone(value: Decimal | None) -> Tone:
    """A cor de um índice de custo: 1 ou mais em ok, de 0,95 a 0,99 em alerta, abaixo em erro."""
    if value is None:
        return Tone.NEUTRAL
    if value >= 1:
        return Tone.OK
    return Tone.WARN if value >= Decimal("0.95") else Tone.ERROR


def _financial_cut_month(view: FinancialCurveOverview) -> date | None:
    if view.series.cut_index < 0:
        return None
    return view.series.months[view.series.cut_index]


def _financial_money(cents: int | None) -> str:
    return FINANCIAL_NO_VALUE if cents is None else format_value(ValueKind.MONEY, cents)


def _financial_signed_money(cents: int) -> str:
    if cents > 0:
        return f"+{_financial_money(cents)}"
    return _financial_money(cents)


def _financial_mil(cents: int) -> float:
    return float(
        (Decimal(cents) / FINANCIAL_MIL_CENTS).quantize(
            FINANCIAL_MIL_ONE_PLACE, rounding=ROUND_HALF_UP
        )
    )


def _financial_mil_or_none(cents: int | None) -> float | None:
    return None if cents is None else _financial_mil(cents)


def curva_financeira_month_label(month: date | None) -> str:
    """``set/26``: o mês da curva como o protótipo o escreve."""
    if month is None:
        return ""
    return f"{MONTH_NAMES[month.month - 1]}/{month.year % 100:02d}"


# ── Cronograma de desembolso (ISSUE-043) ─────────────────────────────────


DESEMBOLSO_TITLE = "Cronograma de desembolso"
DESEMBOLSO_CHART_TITLE = "Desembolso mensal"
DESEMBOLSO_BALANCE_TITLE = "Saldo a pagar por mês"


def desembolso_document(
    view: DisbursementOverview, *, scope_label: str, generated_on: date, level: int
) -> Document:
    """O cronograma como documento: os indicadores, o gráfico mensal e a tabela item x mês.

    ``scope_label`` é a linha do escopo (``describe_scope``), montada pela rota, e ``level`` é o
    nível que o seletor do protótipo pediu. A tabela lista os itens até esse nível com saldo a
    pagar, com o total do rodapé; no Portfólio a coluna Projeto vem pelo mecanismo genérico
    (HU-016).
    """
    return Document(
        title=DESEMBOLSO_TITLE,
        scope_label=scope_label,
        generated_on=generated_on,
        portfolio=view.is_portfolio,
        context=_desembolso_context(view),
        kpis=desembolso_kpis(view),
        charts=(Chart(DESEMBOLSO_CHART_TITLE, "curva-s-barra-linha", desembolso_chart(view)),),
        tables=(_desembolso_months_table(view), _desembolso_table(view, level=level)),
    )


def desembolso_kpis(view: DisbursementOverview) -> tuple[Kpi, ...]:
    """Os quatro indicadores do topo, com o previsto da linha de base na referência."""
    kpis = view.kpis
    if kpis is None:
        return ()
    future = view.future_months
    return (
        Kpi(
            "Realizado até o corte",
            kpis.actual_until_cut_cents,
            f"Previsto: {_financial_money(kpis.planned_until_cut_cents)}",
            ValueKind.MONEY,
            tone=Tone.INFO,
            status=(
                f"{format_value(ValueKind.PERCENT, kpis.actual_pct, 1)} da projeção no término"
                if kpis.actual_pct is not None
                else ""
            ),
        ),
        Kpi(
            "Saldo a desembolsar",
            kpis.balance_cents,
            f"Previsto: {_financial_money(kpis.planned_balance_cents)}",
            ValueKind.MONEY,
            tone=Tone.INFO,
            status=(
                f"de {curva_financeira_month_label(future[0])} a "
                f"{curva_financeira_month_label(future[-1])}"
                if future
                else ""
            ),
        ),
        Kpi(
            "Próximos 3 meses",
            kpis.next_three_cents,
            f"Previsto: {_financial_money(kpis.planned_next_three_cents)}",
            ValueKind.MONEY,
            tone=Tone.WARN,
            status=", ".join(curva_financeira_month_label(month) for month in future[:3]),
        ),
        Kpi(
            "Mês de corte",
            kpis.cut_actual_cents,
            f"Previsto: {_financial_money(kpis.cut_planned_cents)}",
            ValueKind.MONEY,
            tone=_desembolso_cut_tone(kpis.cut_actual_cents, kpis.cut_planned_cents),
            status=_desembolso_cut_status(view, kpis.peak_month),
        ),
    )


def _desembolso_cut_tone(actual_cents: int | None, planned_cents: int | None) -> Tone:
    if actual_cents is None or planned_cents is None:
        return Tone.NEUTRAL
    return Tone.WARN if actual_cents > planned_cents else Tone.OK


def _desembolso_cut_status(view: DisbursementOverview, peak_month: date | None) -> str:
    cut = curva_financeira_month_label(view.cut_month)
    if peak_month is None:
        return cut
    return f"{cut} · pico {curva_financeira_month_label(peak_month)}"


def desembolso_chart(view: DisbursementOverview) -> dict[str, object]:
    """O ``data-dados`` do desembolso mensal (curva-s-barra-linha), em R$ mil.

    As três séries do protótipo: o previsto da linha de base, o realizado até o corte e o
    projetado depois dele; um mês sem valor quebra a barra e a linha da série.
    """
    return {
        "titulo": DESEMBOLSO_CHART_TITLE,
        "modo": "periodo",
        "formato": "numero",
        "unidade": "",
        "casas": 0,
        "series": [
            {"id": "previsto", "rotulo": "Previsto", "papel": "previsto"},
            {"id": "realizado", "rotulo": "Realizado", "papel": "realizado"},
            {"id": "projetado", "rotulo": "Projetado", "papel": "tendencia"},
        ],
        "periodos": [
            {
                "ano": row.month.year,
                "mes": row.month.month,
                "valores": {
                    "previsto": _financial_mil_or_none(row.planned_cents),
                    "realizado": _financial_mil_or_none(row.actual_cents),
                    "projetado": _financial_mil_or_none(row.projected_cents),
                },
            }
            for row in view.histogram
        ],
    }


def desembolso_visible_items(
    view: DisbursementOverview, *, level: int
) -> tuple[DisbursementItem, ...]:
    """As linhas que a tela e a exportação mostram: os itens até o nível pedido com saldo a pagar."""
    return tuple(item for item in view.items if item.level <= level and item.balance_cents > 0)


def desembolso_row_description(item: DisbursementItem) -> str:
    """A descrição da linha; na linha de projeto do Portfólio, só o nome, sem repetir o rótulo."""
    if item.level == 1 and item.description == item.project_label:
        _, _, name = item.project_label.partition(" · ")
        return name or item.description
    return item.description


def _desembolso_context(view: DisbursementOverview) -> tuple[tuple[str, str], ...]:
    lines = [("Referência", format_value(ValueKind.DATE, view.reference_date))]
    if view.cut_month is not None:
        lines.append(("Corte", curva_financeira_month_label(view.cut_month)))
    return tuple(lines)


def _desembolso_months_table(view: DisbursementOverview) -> Table:
    """Os números por trás do gráfico: o previsto, o realizado e o projetado de cada mês."""
    return Table(
        title=DESEMBOLSO_CHART_TITLE,
        columns=(
            Column("Mês", width=16),
            Column("Previsto", ValueKind.MONEY),
            Column("Realizado", ValueKind.MONEY),
            Column("Projetado", ValueKind.MONEY),
        ),
        rows=tuple(
            row(
                curva_financeira_month_label(item.month),
                item.planned_cents,
                item.actual_cents,
                item.projected_cents,
            )
            for item in view.histogram
        ),
        per_project=False,
    )


def _desembolso_table(view: DisbursementOverview, *, level: int) -> Table:
    return Table(
        title=DESEMBOLSO_BALANCE_TITLE,
        columns=(
            Column("Código", width=12),
            Column("Descrição", width=48),
            Column("Saldo a pagar", ValueKind.MONEY),
            *(
                Column(curva_financeira_month_label(month), ValueKind.MONEY)
                for month in view.future_months
            ),
        ),
        rows=tuple(_desembolso_row(item) for item in desembolso_visible_items(view, level=level)),
        totals=(
            Cell(),
            Cell("Total"),
            Cell(view.balance_cents),
            *(Cell(value) for value in view.totals),
        ),
    )


def _desembolso_row(item: DisbursementItem) -> Row:
    return row(
        item.code,
        desembolso_row_description(item),
        item.balance_cents,
        *item.amounts,
        project=item.project_label,
    )
