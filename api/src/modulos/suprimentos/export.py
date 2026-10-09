"""The export of the register, of the plan, of the process, of the expediting, of the map and of the panel: one ``Document``, the Excel and the print (D12).

What the screen shows is what leaves: the six KPIs of the register (or the five of the plan, of
the process and of the expediting, or the six of the map, or the nine of the panel), the line of
active filters and the table, with the same content the prototype exported. The register is
global, so its table declares itself not per project; the plan, the process, the expediting, the
map and the panel tables are per project and in the Portfólio open with ``Projeto`` (HU-016). The
expediting document also carries the manufacturing milestones of the order the request names, as
the prototype's export did. The adjudicated and saving columns of the plan travel empty while the
process (ISSUE-059) and the order (ISSUE-061) do not exist (DECISION, ISSUE-058); the process
document carries the equalization map when the request names a package, as the prototype's export
did.

The map of purchases (ISSUE-062) travels in A3 landscape (``Paper.A3``): the baseline, the
forecast-or-real date and the situation of each of the twelve milestones, the sides of the line
and the situation, with the tone of each situation cell, as the prototype's PDF and Excel did.

The panel (ISSUE-063) travels in A4 landscape (``Paper.A4``): the nine indicators, the four
visuals of the library (the contracting curve, the advancement of the map, the saving curve and
the packages by stage) and the orders by slack.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

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
from src.core.money import format_brl
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.suprimentos import calculations, service
from src.modulos.suprimentos.validation import (
    MAS_MODE_DATES,
    MAS_PHASE_ALL,
    OrderFilters,
    PackageFilters,
    ProcessFilters,
    SupplierFilters,
)

TITLE = "Fornecedores"
TABLE_TITLE = "Fornecedores e contratadas"
ALL_SUPPLIERS = "Todos os fornecedores"
DOCUMENTS_IN_DAY = "Válidos"
DOCUMENTS_EXPIRED = "Documentos vencidos"

PLAN_TITLE = "Plano de compras"
PLAN_TABLE_TITLE = "Pacotes de compra"
ALL_PACKAGES = "Todos os pacotes"

SITUATION_TONES = {
    calculations.QUALIFIED: Tone.OK,
    calculations.IN_QUALIFICATION: Tone.INFO,
    calculations.RESTRICTED: Tone.WARN,
    calculations.BLOCKED: Tone.ERROR,
    service.NO_QUALIFICATION: Tone.NEUTRAL,
}

STAGE_TONES = {
    calculations.STAGE_PLANNED: Tone.NEUTRAL,
    "Requisição": Tone.INFO,
    "RFx emitida": Tone.INFO,
    "Propostas recebidas": Tone.INFO,
    "Equalização técnica": Tone.INFO,
    "Equalização comercial": Tone.INFO,
    "Aprovada": Tone.INFO,
    "Pedido/contrato emitido": Tone.OK,
}

SLACK_TONES = {
    calculations.SLACK_CRITICAL: Tone.ERROR,
    calculations.SLACK_WARNING: Tone.WARN,
    calculations.SLACK_OK: Tone.OK,
}


def build_document(
    *,
    listing: service.SupplierListing,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the register for the filters in force: KPIs, filters and the table."""
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", filter_text(listing.filters)),
            ("Fornecedores no filtro", str(listing.total)),
        ),
        kpis=_kpis(listing),
        tables=(_table(listing.lines),),
        paper=Paper.A4,
    )


def filter_text(filters: SupplierFilters) -> str:
    """The active filters as one line, or the whole register when there is none."""
    parts: list[str] = []
    if filters.search:
        parts.append(f"Busca: {filters.search}")
    if filters.situation:
        parts.append(f"Situação: {filters.situation}")
    if filters.category:
        parts.append(f"Categoria: {filters.category}")
    return " · ".join(parts) if parts else ALL_SUPPLIERS


def evaluation_text(line: service.SupplierLine) -> str:
    """The performance as the prototype exported it: ``Classe A (86)``; empty without one."""
    evaluation = line.last_evaluation
    if evaluation is None or evaluation.score is None or not evaluation.score_class:
        return ""
    return f"Classe {evaluation.score_class} ({evaluation.score})"


def _kpis(listing: service.SupplierListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    return (
        Kpi(
            "Cadastrados",
            summary.registered,
            f"Referência: de {summary.companies} empresas",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status=f"{summary.unregistered} empresas sem qualificação",
        ),
        Kpi(
            "Qualificados",
            summary.qualified,
            f"Referência: de {summary.registered} cadastrados",
            ValueKind.INTEGER,
            tone=Tone.OK,
        ),
        Kpi(
            "Em qualificação",
            summary.in_qualification,
            f"Referência: de {summary.registered} cadastrados",
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
        Kpi(
            "Restritos ou bloqueados",
            summary.restricted_or_blocked,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.restricted_or_blocked else Tone.OK,
            status=f"{summary.blocked} bloqueados",
        ),
        Kpi(
            "Documentos vencidos",
            summary.expired_documents,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if summary.expired_documents else Tone.OK,
            status="certidões e certificados fora da validade",
        ),
        Kpi(
            "Qualificação a vencer",
            summary.validity_due,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.validity_due else Tone.OK,
            status="vencida ou vence em até 90 dias",
        ),
    )


def _table(lines: Sequence[service.SupplierLine]) -> Table:
    return Table(
        title=TABLE_TITLE,
        columns=(
            Column("Empresa", width=34),
            Column("Tipo", width=14),
            Column("Categorias", width=34),
            Column("Situação", width=18),
            Column("Validade", width=14, kind=ValueKind.DATE),
            Column("Documentos", width=24),
            Column("Desempenho", width=20),
            Column("Valor contratado", width=20, kind=ValueKind.MONEY),
        ),
        rows=tuple(_row(line) for line in lines),
        per_project=False,
    )


def _row(line: service.SupplierLine) -> Row:
    documents = DOCUMENTS_IN_DAY if line.documents_up_to_date else DOCUMENTS_EXPIRED
    return row(
        line.name,
        line.kind or "",
        ", ".join(line.categories),
        Cell(line.situation, SITUATION_TONES.get(line.situation, Tone.NEUTRAL)),
        line.validity,
        Cell(documents, Tone.OK if line.documents_up_to_date else Tone.ERROR),
        evaluation_text(line),
        line.contracted_cents,
    )


# ── The purchase plan (ISSUE-058) ────────────────────────────────────────────────────────────


def build_plan_document(
    *,
    listing: service.PackageListing,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the plan for the filters in force: KPIs, filters and the table."""
    return Document(
        title=PLAN_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", plan_filter_text(listing.filters)),
            ("Pacotes no filtro", str(listing.total)),
        ),
        kpis=_plan_kpis(listing),
        tables=(_plan_table(listing.lines),),
        paper=Paper.A3,
    )


def plan_filter_text(filters: PackageFilters) -> str:
    """The active filters as one line, or the whole plan when there is none."""
    parts: list[str] = []
    if filters.search:
        parts.append(f"Busca: {filters.search}")
    if filters.kind:
        parts.append(f"Tipo: {filters.kind}")
    if filters.lli_only:
        parts.append("Só itens de longo prazo (LLI)")
    return " · ".join(parts) if parts else ALL_PACKAGES


def _plan_kpis(listing: service.PackageListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    return (
        Kpi(
            "Pacotes no plano",
            summary.packages,
            f"Linha de base: {summary.with_baseline}",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status=f"{format_brl(summary.estimated_cents)} estimados",
        ),
        Kpi(
            "Adjudicados",
            "—",
            f"Previsto até hoje: {summary.forecast_until_reference}",
            ValueKind.TEXT,
            tone=Tone.NEUTRAL,
            status="aguarda o processo de compra (ISSUE-059)",
        ),
        Kpi(
            "Adjudicação atrasada",
            summary.overdue,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.overdue else Tone.OK,
            status="LB da adjudicação vencida ou previsão após a LB",
        ),
        Kpi(
            "Itens de longo prazo (LLI)",
            summary.lli,
            f"Referência: de {summary.packages} pacotes",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{summary.lli_critical} com folga negativa",
        ),
        Kpi(
            "Saving sobre estimativa",
            "—",
            f"Meta: ≥ {format_brl(0)}",
            ValueKind.TEXT,
            tone=Tone.OK,
            status="depende dos pacotes adjudicados",
        ),
    )


def _plan_table(lines: Sequence[service.PackageLine]) -> Table:
    return Table(
        title=PLAN_TABLE_TITLE,
        columns=(
            Column("Pacote", width=14),
            Column("Escopo", width=30),
            Column("Tipo", width=14),
            Column("Modalidade", width=16),
            Column("Disciplina", width=16),
            Column("Item da EAC", width=16),
            Column("Comprador", width=18),
            Column("Estimativa", width=18, kind=ValueKind.MONEY),
            Column("Requisição (LB)", width=14, kind=ValueKind.DATE),
            Column("RFx (LB)", width=14, kind=ValueKind.DATE),
            Column("Adjudicação (LB)", width=14, kind=ValueKind.DATE),
            Column("Pedido (LB)", width=14, kind=ValueKind.DATE),
            Column("ROS", width=12, kind=ValueKind.DATE),
            Column("Etapa", width=20),
            Column("Folga (dias)", width=12, kind=ValueKind.INTEGER),
            Column("Adjudicado", width=16, kind=ValueKind.MONEY),
            Column("Saving", width=16, kind=ValueKind.MONEY),
        ),
        rows=tuple(_plan_row(line) for line in lines),
    )


def _plan_row(line: service.PackageLine) -> Row:
    requisition = line.milestone(calculations.REQUISITION_MILESTONE)
    rfx = line.milestone("rfx")
    adjudication = line.adjudication
    order = line.milestone(calculations.ORDER_MILESTONE)
    slack = line.slack_days
    return row(
        line.code,
        line.scope,
        line.kind,
        line.modality,
        line.discipline,
        f"{line.eac_code} {line.eac_description}".strip(),
        line.buyer,
        line.estimate_cents,
        requisition.plan if requisition else None,
        rfx.plan if rfx else None,
        adjudication.plan if adjudication else None,
        order.plan if order else None,
        line.ros,
        Cell(line.stage, STAGE_TONES.get(line.stage, Tone.NEUTRAL)),
        Cell(
            slack,
            SLACK_TONES.get(calculations.slack_band(slack), Tone.NEUTRAL),
        ),
        line.adjudicated_cents,
        line.saving_cents,
        project=line.project_label,
    )


# ── The purchase process (ISSUE-059) ─────────────────────────────────────────────────────────

PROCESS_TITLE = "Processos de compra (RFx)"
PROCESS_TABLE_TITLE = "Processos de compra"
MAP_TABLE_TITLE = "Mapa de equalização"
ALL_PROCESSES = "Todos os processos"
IN_PROGRESS = "Em andamento"

TECHNICAL_TONES = {
    True: Tone.OK,
    False: Tone.ERROR,
    None: Tone.NEUTRAL,
}


def build_process_document(
    *,
    listing: service.ProcessListing,
    line: service.ProcessLine | None,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the process list, with the equalization map when a process is named."""
    tables = [_process_table(listing.lines)]
    if line is not None:
        tables.append(_map_table(line))
    return Document(
        title=PROCESS_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", process_filter_text(listing.filters)),
            ("Processos no filtro", str(listing.total)),
        ),
        kpis=_process_kpis(listing),
        tables=tuple(tables),
        paper=Paper.A3,
    )


def process_filter_text(filters: ProcessFilters) -> str:
    """The active filters as one line: the search and the situation shown."""
    situation = IN_PROGRESS if filters.situation == "andamento" else ALL_PROCESSES
    if filters.search:
        return f"Busca: {filters.search} · {situation}"
    return situation


def _process_kpis(listing: service.ProcessListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    minimum = summary.minimum_proposals
    mean = summary.mean_valid_proposals
    share = summary.single_supplier_share
    return (
        Kpi(
            "Em andamento",
            summary.in_progress,
            f"Previsto: {summary.expected_in_progress}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{summary.total} pacotes no plano",
        ),
        Kpi(
            "Aguardando aprovação",
            summary.awaiting_approval,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.awaiting_approval else Tone.OK,
            status="recomendação na alçada",
        ),
        Kpi(
            "Propostas válidas por processo",
            mean if mean is not None else "—",
            f"Meta: ≥ {minimum}",
            ValueKind.DECIMAL if mean is not None else ValueKind.TEXT,
            digits=1,
            tone=Tone.OK if mean is not None and mean >= minimum else Tone.WARN,
        ),
        Kpi(
            "Fornecedor único",
            share if share is not None else "—",
            "Esperado: 0%",
            ValueKind.PERCENT if share is not None else ValueKind.TEXT,
            digits=1,
            tone=Tone.WARN if summary.single_supplier_count else Tone.OK,
            status=f"{summary.single_supplier_count} processos com justificativa",
        ),
        Kpi(
            "Ciclo de compra",
            summary.cycle_mean_days if summary.cycle_mean_days is not None else "—",
            (
                "Linha de base: ·"
                if summary.baseline_cycle_days is None
                else f"Linha de base: {summary.baseline_cycle_days} dias"
            ),
            ValueKind.INTEGER if summary.cycle_mean_days is not None else ValueKind.TEXT,
            tone=Tone.NEUTRAL,
            status="requisição até o pedido emitido",
        ),
    )


def _process_table(lines: Sequence[service.ProcessLine]) -> Table:
    return Table(
        title=PROCESS_TABLE_TITLE,
        columns=(
            Column("Pacote", width=12),
            Column("Escopo", width=30),
            Column("Tipo", width=14),
            Column("RFx", width=14),
            Column("Etapa", width=22),
            Column("Propostas", width=24),
            Column("Melhor proposta", width=34),
            Column("Alçada", width=22),
            Column("Adjudicação (LB)", width=14, kind=ValueKind.DATE),
            Column("Adjudicação (real)", width=14, kind=ValueKind.DATE),
            Column("Adjudicação (previsão)", width=14, kind=ValueKind.DATE),
        ),
        rows=tuple(_process_row(line) for line in lines),
    )


def _process_row(line: service.ProcessLine) -> Row:
    return row(
        line.code,
        line.scope,
        line.kind,
        line.number or "",
        Cell(line.stage, STAGE_TONES.get(line.stage, Tone.NEUTRAL)),
        f"{line.received_count} recebidas · {line.approved_count} aprovadas"
        if line.process_id is not None
        else "",
        _best_text(line),
        line.approval_band or "",
        line.adjudication_plan,
        line.adjudication_real,
        line.adjudication_forecast,
        project=line.project_label,
    )


def _best_text(line: service.ProcessLine) -> str:
    if line.best is None:
        return f"estimativa {format_brl(line.estimate_cents)}"
    value = line.best.negotiated_cents or line.best.value_cents
    score = format_value(ValueKind.DECIMAL, line.best.final_score, 1)
    return f"{format_brl(value)} · {line.best.name} · nota {score}"


def _map_table(line: service.ProcessLine) -> Table:
    ordered = sorted(line.proposals, key=lambda proposal: (proposal.rank or 99, proposal.id))
    return Table(
        title=f"{MAP_TABLE_TITLE} {line.number or line.code}",
        columns=(
            Column("#", width=6, kind=ValueKind.INTEGER),
            Column("Fornecedor", width=30),
            Column("Qualificação", width=18),
            Column("Valor", width=18, kind=ValueKind.MONEY),
            Column("Negociado", width=18, kind=ValueKind.MONEY),
            Column("Prazo (dias)", width=12, kind=ValueKind.INTEGER),
            Column("Nota técnica", width=12, kind=ValueKind.INTEGER),
            Column("Técnica", width=14),
            Column("Nota comercial", width=14, kind=ValueKind.DECIMAL),
            Column("Nota final", width=12, kind=ValueKind.DECIMAL),
            Column("Desvios", width=40),
        ),
        rows=tuple(_map_row(proposal) for proposal in ordered),
        per_project=False,
    )


def _map_row(proposal: service.ProposalLine) -> Row:
    return row(
        proposal.rank,
        proposal.name,
        proposal.qualification,
        proposal.value_cents,
        proposal.negotiated_cents,
        proposal.deadline_days,
        proposal.technical_score,
        Cell(
            "Pendente"
            if proposal.technically_approved is None
            else ("Aprovada" if proposal.technically_approved else "Reprovada"),
            TECHNICAL_TONES[proposal.technically_approved],
        ),
        proposal.commercial_score,
        proposal.final_score,
        proposal.deviations,
    )


# ── The expediting and receiving (ISSUE-061) ─────────────────────────────────────────────────

ORDERS_TITLE = "Diligenciamento e recebimento"
ORDERS_TABLE_TITLE = "Pedidos em diligenciamento"
ORDER_MILESTONES_TITLE = "Marcos de fabricação do pedido"
ALL_ORDERS = "Todos os pedidos"
SITUATION_TONES_ORDER = {
    calculations.ORDER_DELIVERED: Tone.OK,
    calculations.ORDER_CRITICAL: Tone.ERROR,
    calculations.ORDER_WARNING: Tone.WARN,
    calculations.ORDER_ON_TIME: Tone.OK,
}
MILESTONE_TONES = {
    calculations.MILESTONE_ON_TIME: Tone.OK,
    calculations.MILESTONE_LATE: Tone.ERROR,
    calculations.MILESTONE_OVERDUE: Tone.ERROR,
    calculations.MILESTONE_FORECAST_LATE: Tone.WARN,
    calculations.MILESTONE_DUE_SOON: Tone.OK,
    calculations.MILESTONE_WITHOUT_DATE: Tone.NEUTRAL,
}


def build_orders_document(
    *,
    listing: service.OrderListing,
    line: service.OrderLine | None,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the expediting, with the milestones of the order the request names."""
    tables = [_orders_table(listing.lines)]
    if line is not None:
        tables.append(_order_milestones_table(line))
    return Document(
        title=ORDERS_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", orders_filter_text(listing.filters)),
            ("Pedidos no filtro", str(listing.total)),
        ),
        kpis=_orders_kpis(listing),
        tables=tuple(tables),
        paper=Paper.A3,
    )


def orders_filter_text(filters: OrderFilters) -> str:
    """The active filters as one line: the search and the orders shown."""
    parts: list[str] = []
    if filters.search:
        parts.append(f"Busca: {filters.search}")
    if filters.situation != "abertos":
        parts.append("Todos os pedidos")
    if filters.band:
        parts.append(f"Faixa: {filters.band}")
    return " · ".join(parts) if parts else ALL_ORDERS


def _orders_kpis(listing: service.OrderListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    return (
        Kpi(
            "Pedidos em aberto",
            summary.open_orders,
            f"Previsto: {summary.expected_open}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{format_brl(summary.open_cents)} a receber",
        ),
        Kpi(
            "Críticos",
            summary.critical,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if summary.critical else Tone.OK,
            status=f"{summary.lli_critical} de longo prazo (LLI) · previsão depois do ROS",
        ),
        Kpi(
            "Em atenção",
            summary.warning,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.warning else Tone.OK,
            status="folga de até 7 dias ou marco vencido",
        ),
        Kpi(
            "Marcos vencidos",
            summary.overdue_milestones,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if summary.overdue_milestones else Tone.OK,
            status="previsão passou sem realização",
        ),
        Kpi(
            "Entrega no prazo (OTD)",
            summary.otd if summary.otd is not None else "—",
            "Meta: ≥ 90,0%",
            ValueKind.PERCENT if summary.otd is not None else ValueKind.TEXT,
            digits=1,
            tone=Tone.OK if summary.otd is not None and summary.otd >= 90 else Tone.WARN,
            status=f"{summary.delivered_on_time} de {summary.delivered} entregas até a data contratual",
        ),
    )


def _orders_table(lines: Sequence[service.OrderLine]) -> Table:
    return Table(
        title=ORDERS_TABLE_TITLE,
        columns=(
            Column("Pedido", width=16),
            Column("Pacote", width=12),
            Column("Descrição", width=34),
            Column("Fornecedor", width=24),
            Column("Valor", width=18, kind=ValueKind.MONEY),
            Column("Próximo marco", width=22),
            Column("Data contratual", width=14, kind=ValueKind.DATE),
            Column("Previsão de entrega", width=16, kind=ValueKind.DATE),
            Column("ROS", width=12, kind=ValueKind.DATE),
            Column("Folga (dias)", width=12, kind=ValueKind.INTEGER),
            Column("Situação", width=14),
        ),
        rows=tuple(_order_row(line) for line in lines),
    )


def _order_row(line: service.OrderLine) -> Row:
    next_milestone = line.next_milestone
    return row(
        line.number,
        line.package_code,
        line.description,
        line.supplier,
        line.value_cents,
        next_milestone.name if next_milestone is not None else "Entregue",
        line.contractual_date,
        line.prediction,
        line.ros,
        Cell(line.slack_days, SLACK_TONES.get(line.band, Tone.NEUTRAL)),
        Cell(line.situation, SITUATION_TONES_ORDER.get(line.situation, Tone.NEUTRAL)),
        project=line.project_label,
    )


def _order_milestones_table(line: service.OrderLine) -> Table:
    return Table(
        title=f"{ORDER_MILESTONES_TITLE} {line.number}",
        columns=(
            Column("Marco", width=24),
            Column("LB (contratual)", width=16, kind=ValueKind.DATE),
            Column("Previsão", width=16, kind=ValueKind.DATE),
            Column("Realizado", width=16, kind=ValueKind.DATE),
            Column("Desvio (dias)", width=14, kind=ValueKind.INTEGER),
            Column("Situação", width=16),
        ),
        rows=tuple(_order_milestone_row(row) for row in line.milestones),
        per_project=False,
    )


def _order_milestone_row(milestone: service.OrderMilestoneLine) -> Row:
    return row(
        milestone.name,
        milestone.baseline,
        None if milestone.done else milestone.forecast,
        milestone.real,
        Cell(milestone.deviation_days, MILESTONE_TONES.get(milestone.situation, Tone.NEUTRAL)),
        Cell(milestone.situation, MILESTONE_TONES.get(milestone.situation, Tone.NEUTRAL)),
    )


# ── The map of purchases (ISSUE-062) ─────────────────────────────────────────────────────────

MAS_TITLE = "Mapa de Suprimentos (MAS)"
MAS_TABLE_TITLE = "Mapa de Suprimentos"
ALL_MAP_PACKAGES = "Todos os pacotes"

# The situation of a milestone in words, as the prototype abreviated it (``ABREV``).
MAS_SITUATION_TEXT: dict[str, str] = {
    calculations.MILESTONE_ON_TIME: "no prazo",
    calculations.MILESTONE_LATE: "com atraso",
    calculations.MILESTONE_OVERDUE: "vencido",
    calculations.MILESTONE_FORECAST_LATE: "previsão após LB",
    calculations.MILESTONE_DUE_SOON: "a vencer",
    calculations.MILESTONE_WITHOUT_DATE: "sem data",
    calculations.MILESTONE_NOT_APPLICABLE: "N/A",
}

# The colors of the cells (``COR`` of the prototype): a-vencer and sem-data stay without tone.
MAS_CELL_TONES: dict[str, Tone] = {
    calculations.MILESTONE_ON_TIME: Tone.OK,
    calculations.MILESTONE_LATE: Tone.ERROR,
    calculations.MILESTONE_OVERDUE: Tone.ERROR,
    calculations.MILESTONE_FORECAST_LATE: Tone.WARN,
    calculations.MILESTONE_NOT_APPLICABLE: Tone.NEUTRAL,
}

MAS_LINE_TONES: dict[str, Tone] = {
    calculations.MAS_CRITICAL: Tone.ERROR,
    calculations.MAS_WARNING: Tone.WARN,
    calculations.MAS_ON_TIME: Tone.OK,
    calculations.MAS_DELIVERED: Tone.OK,
    calculations.MAS_CONTRACTED: Tone.OK,
}

MAS_PROGRESS_TONES: dict[str, Tone] = {
    calculations.PROGRESS_ON_PACE: Tone.OK,
    calculations.PROGRESS_NEAR: Tone.WARN,
    calculations.PROGRESS_BELOW: Tone.ERROR,
}


def build_mas_document(
    *,
    listing: service.MasListing,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the map for the filters in force: KPIs, filters and the table, in A3."""
    return Document(
        title=MAS_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", mas_filter_text(listing)),
            ("Pacotes no filtro", str(listing.total)),
        ),
        kpis=_mas_kpis(listing),
        tables=(_mas_table(listing),),
        paper=Paper.A3,
    )


def mas_filter_text(listing: service.MasListing) -> str:
    """The active filters as one line, or the whole map when there is none."""
    parts = [part for part in _mas_filter_parts(listing) if part]
    return " · ".join(parts) if parts else ALL_MAP_PACKAGES


def _mas_filter_parts(listing: service.MasListing) -> list[str]:
    filters = listing.filters
    return [
        f"Busca: {filters.search}" if filters.search else "",
        "Células: desvio em dias" if filters.mode != MAS_MODE_DATES else "",
        (
            f"Marcos: {calculations.MAS_PHASE_LABELS.get(filters.phase, filters.phase)}"
            if filters.phase != MAS_PHASE_ALL
            else ""
        ),
        _option_filter("Disciplina", listing.disciplines, filters.discipline_id),
        f"Tipo: {filters.kind}" if filters.kind else "",
        "Só LLI" if filters.lli == "sim" else "",
        "Sem LLI" if filters.lli == "nao" else "",
        _option_filter("Comprador", listing.buyers, filters.buyer_id),
        _option_filter("Fornecedor", listing.suppliers, filters.supplier_id),
        f"Situação: {filters.situation}" if filters.situation else "",
        "Só pacotes com marco vencido" if filters.overdue_only else "",
    ]


def _option_filter(
    prefix: str, options: Sequence[configuracoes.RegisterOption], item_id: int | None
) -> str:
    """``Comprador: Ana`` for a chosen option, or the empty text when the filter is off."""
    if item_id is None:
        return ""
    return f"{prefix}: {_option_name(options, item_id)}"


def _option_name(options: Sequence[configuracoes.RegisterOption], item_id: int) -> str:
    """The name of a filter choice, or the id when it is not in the list."""
    return next((option.name for option in options if option.id == item_id), str(item_id))


def _mas_kpis(listing: service.MasListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    realized = summary.realized_milestones
    late_share = summary.late_share
    index = summary.index
    return (
        Kpi(
            "Itens no MAS",
            summary.items,
            f"Linha de base: {summary.with_baseline}",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status=f"{summary.concluded} concluídos (entregues ou contratados)",
        ),
        Kpi(
            "Críticos",
            summary.critical,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if summary.critical else Tone.OK,
            status="folga negativa em relação ao ROS",
        ),
        Kpi(
            "Em atenção",
            summary.warning,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.warning else Tone.OK,
            status="folga pequena ou marco vencido",
        ),
        Kpi(
            "Marcos vencidos",
            summary.overdue_milestones,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if summary.overdue_milestones else Tone.OK,
            status="previsão passou sem realização",
        ),
        Kpi(
            "Realizados com atraso",
            late_share if late_share is not None else "—",
            "Esperado: 0%",
            ValueKind.PERCENT if late_share is not None else ValueKind.TEXT,
            digits=1,
            tone=Tone.WARN,
            status=f"{summary.late_milestones} de {realized} marcos realizados depois da LB",
        ),
        Kpi(
            "Avanço de suprimentos",
            summary.realized_pct,
            f"Linha de base: {format_value(ValueKind.PERCENT, summary.planned_pct, 1)}",
            ValueKind.PERCENT,
            digits=1,
            tone=MAS_PROGRESS_TONES.get(calculations.progress_band(index), Tone.NEUTRAL),
            status=(
                f"índice {format_value(ValueKind.DECIMAL, index, 2)}"
                if index is not None
                else "sem linha de base"
            ),
        ),
    )


def _mas_table(listing: service.MasListing) -> Table:
    return Table(
        title=MAS_TABLE_TITLE,
        columns=_mas_columns(listing),
        rows=tuple(_mas_row(line, listing.columns) for line in listing.lines),
    )


def _mas_columns(listing: service.MasListing) -> tuple[Column, ...]:
    """The columns of the prototype's spreadsheet: the sides and three per visible milestone."""
    milestones = tuple(
        Column(title, kind=kind, width=width)
        for column in listing.columns
        for title, kind, width in (
            (f"{column.label} LB", ValueKind.DATE, 12),
            (f"{column.label} previsão ou real", ValueKind.DATE, 12),
            (f"{column.label} situação", ValueKind.TEXT, 18),
        )
    )
    return (
        Column("Pacote", width=12),
        Column("Escopo", width=30),
        Column("Tipo", width=12),
        Column("Disciplina", width=14),
        Column("LLI", width=6),
        Column("Item da EAC", width=14),
        Column("Fornecedor", width=22),
        Column("Comprador", width=18),
        Column("Estimativa", width=16, kind=ValueKind.MONEY),
        Column("Adjudicado", width=16, kind=ValueKind.MONEY),
        *milestones,
        Column("Processo", width=14),
        Column("Pedido ou contrato", width=16),
        Column("ROS", width=10, kind=ValueKind.DATE),
        Column("Previsão de entrega", width=12, kind=ValueKind.DATE),
        Column("Folga (dias)", width=8, kind=ValueKind.INTEGER),
        Column("Avanço real (%)", width=10, kind=ValueKind.PERCENT, digits=1),
        Column("Avanço LB (%)", width=10, kind=ValueKind.PERCENT, digits=1),
        Column("Situação", width=12),
    )


def _mas_row(line: service.MasLine, columns: Sequence[service.MasMilestoneColumn]) -> Row:
    milestones: list[Cell] = []
    for column in columns:
        milestone = line.milestone(column.key)
        if milestone is None:
            milestones.extend((Cell(), Cell(), Cell()))
            continue
        milestones.extend(
            (
                Cell(milestone.baseline),
                Cell(milestone.real or milestone.forecast),
                Cell(
                    mas_situation_text(milestone),
                    MAS_CELL_TONES.get(milestone.situation),
                ),
            )
        )
    return row(
        line.code,
        line.scope,
        line.kind,
        line.discipline,
        "Sim" if line.lli else "Não",
        f"{line.eac_code} {line.eac_description}".strip(),
        line.supplier,
        line.buyer,
        line.estimate_cents,
        line.adjudicated_cents,
        *milestones,
        line.process_number or "",
        line.order_number or line.contract_number or "",
        line.ros,
        line.delivery_forecast,
        Cell(line.slack_days, SLACK_TONES.get(line.band, Tone.NEUTRAL)),
        line.realized_pct,
        line.planned_pct,
        Cell(line.situation, MAS_LINE_TONES.get(line.situation, Tone.NEUTRAL)),
        project=line.project_label,
    )


def mas_situation_text(milestone: service.MasMilestoneLine) -> str:
    """``com atraso +3 d``: the situation of the milestone and its deviation against the LB.

    A deviation of zero travels without the days, as the prototype printed it (``m.desvio`` is
    falsy in JavaScript for zero); ``N/A`` never carries one.
    """
    text = MAS_SITUATION_TEXT.get(milestone.situation, milestone.situation)
    if not milestone.deviation_days:
        return text
    deviation = milestone.deviation_days
    days = f"+{deviation} d" if deviation > 0 else f"{deviation} d"
    return f"{text} {days}"


# ── The panel (ISSUE-063) ────────────────────────────────────────────────────────────────────
#
# The same builders feed the screen and the printable, so the numbers on paper are the ones of
# the screen: the nine indicators, the four visuals (the contracting curve, the advancement of
# the map, the saving curve and the packages by stage) and the orders by slack. The saving curve
# travels in R$ mil, as the other financial curves of the platform (D12).

PANEL_TITLE = "Painel de suprimentos"
PANEL_CONTRACTING_TITLE = "Curva de contratação"
PANEL_PROGRESS_TITLE = "Avanço físico de suprimentos"
PANEL_SAVING_TITLE = "Saving acumulado"
PANEL_STAGES_TITLE = "Pacotes por etapa"
PANEL_SLACK_TABLE_TITLE = "Pedidos por folga"
PANEL_SAVING_MIL = 100_000


def build_panel_document(
    *,
    listing: service.PanelListing,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the panel: the nine indicators, the four visuals and the orders by slack."""
    return Document(
        title=PANEL_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Referência", format_value(ValueKind.DATE, listing.reference_date)),),
        kpis=_panel_kpis(listing),
        charts=panel_charts(listing),
        tables=(_panel_slack_table(listing),),
        paper=Paper.A4,
    )


def panel_charts(listing: service.PanelListing) -> tuple[Chart, ...]:
    """The four visuals of the panel, in the order of the screen."""
    return (
        Chart(PANEL_CONTRACTING_TITLE, "curva-s-linha", panel_contracting_chart(listing)),
        Chart(PANEL_PROGRESS_TITLE, "curva-s-linha", panel_progress_chart(listing)),
        Chart(PANEL_SAVING_TITLE, "linhas-multiplas", panel_saving_chart(listing)),
        Chart(PANEL_STAGES_TITLE, "kpi-status", panel_stages_chart(listing)),
    )


def panel_contracting_chart(listing: service.PanelListing) -> dict[str, object]:
    """The ``data-dados`` of the contracting curve: the adjudicated packages accumulated."""
    curve = listing.contracting
    return {
        "titulo": PANEL_CONTRACTING_TITLE,
        "modo": "acumulado",
        "formato": "numero",
        "unidade": "",
        "casas": 0,
        "series": [
            {"id": "planejado", "rotulo": "Plano de compras", "papel": "linha-base"},
            {"id": "realizado", "rotulo": "Realizado", "papel": "realizado"},
        ],
        "periodos": [
            {
                "ano": month.year,
                "mes": month.month,
                "valores": {"planejado": planned, "realizado": realized},
            }
            for month, planned, realized in zip(
                curve.months, curve.planned, curve.realized, strict=True
            )
        ],
    }


def panel_progress_chart(listing: service.PanelListing) -> dict[str, object]:
    """The ``data-dados`` of the advancement curve: baseline, real and trend, in percent."""
    curve = listing.progress_curve
    periods = (
        []
        if curve is None
        else [
            {
                "ano": month.year,
                "mes": month.month,
                "valores": {
                    "linha-base": float(baseline),
                    "real": None if real is None else float(real),
                    "tendencia": None if trend is None else float(trend),
                },
            }
            for month, baseline, real, trend in zip(
                curve.months, curve.baseline, curve.real, curve.trend, strict=True
            )
        ]
    )
    return {
        "titulo": PANEL_PROGRESS_TITLE,
        "modo": "acumulado",
        "formato": "pct",
        "unidade": "%",
        "casas": 1,
        "eixo_max": 100,
        "series": [
            {"id": "linha-base", "rotulo": "Linha de base", "papel": "linha-base"},
            {"id": "real", "rotulo": "Real", "papel": "realizado"},
            {"id": "tendencia", "rotulo": "Tendência", "papel": "tendencia"},
        ],
        "periodos": periods,
    }


def panel_saving_chart(listing: service.PanelListing) -> dict[str, object]:
    """The ``data-dados`` of the saving curve, in R$ mil, by adjudication month."""
    curve = listing.saving
    return {
        "titulo": PANEL_SAVING_TITLE,
        "casas": 0,
        "unidade": "",
        "base_zero": False,
        "series": [
            {"id": "estimativa", "rotulo": "Sobre a estimativa", "papel": "realizado"},
            {"id": "negociacao", "rotulo": "Na negociação", "papel": "comprometido"},
        ],
        "periodos": [
            {
                "ano": month.year,
                "mes": month.month,
                "valores": {
                    "estimativa": None if estimated is None else estimated / PANEL_SAVING_MIL,
                    "negociacao": None if negotiation is None else negotiation / PANEL_SAVING_MIL,
                },
            }
            for month, estimated, negotiation in zip(
                curve.months, curve.estimated, curve.negotiation, strict=True
            )
        ],
    }


def panel_stages_chart(listing: service.PanelListing) -> dict[str, object]:
    """The ``data-dados`` of the packages by stage: the count of each stage of the plan."""
    return {
        "titulo": PANEL_STAGES_TITLE,
        "itens": [
            {"id": f"etapa-{index}", "rotulo": item.stage, "valor": item.total, "tom": "neutro"}
            for index, item in enumerate(listing.stages)
        ],
        "total": listing.summary.packages,
    }


def _panel_kpis(listing: service.PanelListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    orders = summary.orders
    adherence = summary.adherence_pct
    saving = summary.saving_pct
    negotiation = summary.negotiation_saving_pct
    offers = summary.average_offers
    otd = orders.otd
    emergency = summary.emergency_pct
    committed = summary.committed_pct
    return (
        Kpi(
            "Aderência ao plano de compras",
            adherence if adherence is not None else "—",
            f"Meta: ≥ {summary.adherence_target}%",
            ValueKind.PERCENT if adherence is not None else ValueKind.TEXT,
            digits=1,
            tone=(
                Tone.OK
                if adherence is not None and adherence >= summary.adherence_target
                else Tone.WARN
                if adherence is not None
                else Tone.NEUTRAL
            ),
            status=(
                f"{summary.adjudicated_until_reference} de "
                f"{summary.planned_until_reference} pacotes planejados até a data"
            ),
        ),
        Kpi(
            "Ciclo de compra",
            summary.cycle_days if summary.cycle_days is not None else "—",
            f"Linha de base: {format_value(ValueKind.INTEGER, summary.cycle_baseline_days)}"
            if summary.cycle_baseline_days is not None
            else "Linha de base: —",
            ValueKind.INTEGER if summary.cycle_days is not None else ValueKind.TEXT,
            tone=Tone.INFO,
            status="média entre requisição e pedido emitido",
        ),
        Kpi(
            "Saving sobre estimativa",
            summary.saving_cents,
            f"Meta: ≥ {format_value(ValueKind.MONEY, 0)}",
            ValueKind.MONEY,
            tone=Tone.OK if summary.saving_cents >= 0 else Tone.ERROR,
            status=(
                f"{format_value(ValueKind.PERCENT, saving, 1)} da estimativa dos pacotes adjudicados"
                if saving is not None
                else "sem pacotes adjudicados"
            ),
        ),
        Kpi(
            "Saving de negociação",
            summary.negotiation_saving_cents,
            f"Meta: ≥ {format_value(ValueKind.MONEY, 0)}",
            ValueKind.MONEY,
            tone=Tone.OK if summary.negotiation_saving_cents >= 0 else Tone.ERROR,
            status=(
                f"{format_value(ValueKind.PERCENT, negotiation, 1)} sobre a primeira proposta"
                if negotiation is not None
                else "sem primeira proposta registrada"
            ),
        ),
        Kpi(
            "Competitividade",
            offers if offers is not None else "—",
            f"Meta: ≥ {summary.minimum_proposals}",
            ValueKind.DECIMAL if offers is not None else ValueKind.TEXT,
            digits=1,
            tone=(
                Tone.OK if offers is not None and offers >= summary.minimum_proposals else Tone.WARN
            ),
            status=(
                f"válidas por processo · fornecedor único "
                f"{format_value(ValueKind.PERCENT, summary.single_supplier_pct, 1)}"
                if summary.single_supplier_pct is not None
                else "válidas por processo"
            ),
        ),
        Kpi(
            "Entrega no prazo (OTD)",
            otd if otd is not None else "—",
            f"Meta: ≥ {summary.otd_target}%",
            ValueKind.PERCENT if otd is not None else ValueKind.TEXT,
            digits=1,
            tone=(
                Tone.OK
                if otd is not None and otd >= summary.otd_target
                else Tone.WARN
                if otd is not None
                else Tone.NEUTRAL
            ),
            status=f"{orders.delivered_on_time} de {orders.delivered} entregas até a data contratual",
        ),
        Kpi(
            "Pedidos críticos",
            orders.critical,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if orders.critical else Tone.OK,
            status=f"folga negativa em relação ao ROS · {orders.lli_critical} de longo prazo",
        ),
        Kpi(
            "Compras emergenciais",
            emergency if emergency is not None else "—",
            "Esperado: 0%",
            ValueKind.PERCENT if emergency is not None else ValueKind.TEXT,
            digits=1,
            tone=Tone.WARN if emergency else Tone.OK,
            status=f"{format_value(ValueKind.MONEY, summary.emergency_cents)} do valor contratado",
        ),
        Kpi(
            "Comprometido x orçado",
            committed if committed is not None else "—",
            f"Limite: 100% · Orçado: {format_value(ValueKind.MONEY, summary.budget_cents)}",
            ValueKind.PERCENT if committed is not None else ValueKind.TEXT,
            digits=1,
            tone=Tone.ERROR if committed is not None and committed > 100 else Tone.NEUTRAL,
            status=(
                f"{format_value(ValueKind.MONEY, summary.adjudicated_cents)} adjudicado "
                "nos itens da EAC"
            ),
        ),
    )


def _panel_slack_table(listing: service.PanelListing) -> Table:
    return Table(
        title=PANEL_SLACK_TABLE_TITLE,
        columns=(
            Column("Pacote", width=12),
            Column("Escopo", width=30),
            Column("Fornecedor", width=22),
            Column("LLI", width=6),
            Column("Próximo marco", width=20),
            Column("Previsão de entrega", width=12, kind=ValueKind.DATE),
            Column("ROS", width=10, kind=ValueKind.DATE),
            Column("Folga (dias)", width=8, kind=ValueKind.INTEGER),
            Column("Situação", width=12),
        ),
        rows=tuple(_panel_slack_row(line) for line in listing.slack_lines),
    )


def _panel_slack_row(line: service.MasLine) -> Row:
    next_milestone = line.next_milestone
    return row(
        line.code,
        line.scope,
        line.supplier,
        "Sim" if line.lli else "Não",
        next_milestone.label if next_milestone is not None else line.current_stage,
        line.delivery_forecast,
        line.ros,
        Cell(line.slack_days, SLACK_TONES.get(line.band, Tone.NEUTRAL)),
        Cell(line.situation, MAS_LINE_TONES.get(line.situation, Tone.NEUTRAL)),
        project=line.project_label,
    )
