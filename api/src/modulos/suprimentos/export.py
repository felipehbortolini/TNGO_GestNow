"""The export of the register, of the plan and of the process: one ``Document``, the Excel and the print (D12).

What the screen shows is what leaves: the six KPIs of the register (or the five of the plan and
of the process), the line of active filters and the table, with the same content the prototype
exported. The register is global, so its table declares itself not per project; the plan and the
process tables are per project and in the Portfólio open with ``Projeto`` (HU-016). The
adjudicated and saving columns of the plan travel empty while the process (ISSUE-059) and the
order (ISSUE-061) do not exist (DECISION, ISSUE-058); the process document carries the
equalization map when the request names a package, as the prototype's export did.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
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
from src.modulos.suprimentos import calculations, service
from src.modulos.suprimentos.validation import PackageFilters, ProcessFilters, SupplierFilters

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
