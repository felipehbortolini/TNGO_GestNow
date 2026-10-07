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
EOT, payment milestones and evaluations) of the scope, with the filters of the screen.
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
    ContractsOverview,
    ContractView,
    EacView,
    EvaluationCriterionSpec,
    EvaluationCriterionView,
    EvaluationView,
    ExtensionView,
    MapaControleView,
    MapaRow,
    MeasurementView,
    MilestoneView,
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
