"""The export of the register and of the plan: one ``Document``, the Excel and the print (D12).

What the screen shows is what leaves: the six KPIs of the register (or the five of the plan),
the line of active filters and the table, with the same content the prototype exported. The
register is global, so its table declares itself not per project; the plan table is per project
and in the Portfólio opens with ``Projeto`` (HU-016). The adjudicated and saving columns of the
plan travel empty while the process (ISSUE-059) and the order (ISSUE-061) do not exist
(DECISION, ISSUE-058).
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
    row,
)
from src.core.money import format_brl
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.suprimentos import calculations, service
from src.modulos.suprimentos.validation import PackageFilters, SupplierFilters

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
