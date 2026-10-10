"""The export of the RNC list: one ``Document``, the Excel and the printable version (D12).

What the screen shows is what leaves: the five KPIs of the prototype (RNC em aberto, prazo
vencido, em verificação de eficácia, encerradas e custo da não qualidade) with their
reference, the line of the filters in force and the table of the reports with the same
columns the prototype exported. In the Portfólio the table opens with ``Projeto`` (HU-016).
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
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.qualidade.service import RncLine, RncListing, RncSummary
from src.modulos.qualidade.validation import RncFilters

TITLE = "Não conformidades (RNC)"
TABLE_TITLE = "Relatórios de não conformidade"
NOT_ASSESSED = "·"

SITUATION_TONES = {
    "Aberta": Tone.NEUTRAL,
    "Em análise de causa": Tone.WARN,
    "Ação corretiva": Tone.INFO,
    "Verificação de eficácia": Tone.INFO,
    "Encerrada": Tone.OK,
    "Cancelada": Tone.NEUTRAL,
}

COLUMNS: tuple[Column, ...] = (
    Column("Nº", width=22),
    Column("Data", ValueKind.DATE, width=12),
    Column("Não conformidade", width=52),
    Column("Origem", width=22),
    Column("Disciplina", width=16),
    Column("Empresa", width=22),
    Column("Severidade", width=12),
    Column("Situação", width=22),
    Column("Próxima etapa", width=30),
    Column("Prazo", ValueKind.DATE, width=12),
    Column("Ações na Central", width=16),
    Column("Disposição", width=16),
    Column("Custo", ValueKind.MONEY, width=16),
)


def build_document(
    *,
    listing: RncListing,
    filters: RncFilters,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    verification_days: int,
) -> Document:
    """The document of the list for the filters in force: the KPIs and the table."""
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", filters_text(filters, listing)),
            ("RNC no filtro", str(listing.total)),
        ),
        kpis=_kpis(listing.summary, verification_days=verification_days),
        tables=(_table(listing),),
        paper=Paper.A3,
    )


def filters_text(filters: RncFilters, listing: RncListing) -> str:
    """The filters in force as one line, the way the export header writes them."""
    parts: list[str] = []
    if filters.search:
        parts.append(f"busca «{filters.search}»")
    if filters.situation == "ativas":
        parts.append("em aberto")
    elif filters.situation == "vencidas":
        parts.append("vencidas")
    elif filters.situation != "todas":
        parts.append(filters.situation)
    if filters.severity:
        parts.append(filters.severity)
    if filters.discipline:
        parts.append(filters.discipline)
    if filters.origin:
        parts.append(filters.origin)
    if filters.company_id is not None:
        names = {item.id: item.name for item in listing.companies}
        parts.append(names.get(filters.company_id, ""))
    return " · ".join(part for part in parts if part) or "Todas"


def _kpis(summary: RncSummary, *, verification_days: int) -> tuple[Kpi, ...]:
    open_tone = Tone.ERROR if summary.active else Tone.OK
    overdue_tone = Tone.ERROR if summary.overdue else Tone.OK
    cost_tone = Tone.ERROR if summary.cost_cents else Tone.OK
    average = (
        f"tempo médio de {summary.average_days} dias"
        if summary.average_days is not None
        else "sem encerramento"
    )
    return (
        Kpi(
            label="RNC em aberto",
            value=summary.active,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=open_tone,
            status=f"{summary.critical} crítica(s)",
        ),
        Kpi(
            label="Prazo de tratamento vencido",
            value=summary.overdue,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=overdue_tone,
            status="antes da verificação de eficácia",
        ),
        Kpi(
            label="Em verificação de eficácia",
            value=summary.in_verification,
            reference=f"Limite: {verification_days} dias",
            kind=ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{summary.verification_overdue} vencida(s)",
        ),
        Kpi(
            label="Encerradas",
            value=summary.closed,
            reference=f"de {summary.registered} registradas",
            kind=ValueKind.INTEGER,
            tone=Tone.OK,
            status=average,
        ),
        Kpi(
            label="Custo da não qualidade",
            value=summary.cost_cents,
            reference="Esperado: R$ 0,00",
            kind=ValueKind.MONEY,
            tone=cost_tone,
            status="retrabalho, reparo, ensaios e perdas",
        ),
    )


def _table(listing: RncListing) -> Table:
    return Table(
        title=TABLE_TITLE,
        columns=COLUMNS,
        rows=tuple(_row(line) for line in listing.lines),
    )


def _row(line: RncLine) -> Row:
    return row(
        line.code,
        line.rnc_date,
        line.description,
        line.origin + (f" {line.origin_ref}" if line.origin_ref else ""),
        line.discipline,
        line.company_name,
        Cell(line.severity),
        Cell(line.situation, SITUATION_TONES.get(line.situation)),
        line.next_step or NOT_ASSESSED,
        line.deadline,
        f"{line.actions.open} de {line.actions.total}",
        line.disposition or NOT_ASSESSED,
        line.cost_cents,
    )
