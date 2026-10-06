"""The export of the screen Ações: one ``Document``, the Excel and the printable version (D12, ISSUE-019).

What the screen shows is what leaves: the four KPIs with their reference (the ones the prototype
printed), the line of active filters and the table of the actions of the filter, with every
column the screen has plus the ones it hides by default (group, requester, completion date).
In the Portfólio the table opens with ``Projeto`` (HU-016). The table is wide (fourteen columns),
so the printable version asks for A3 landscape, as the Mapa de controle does.
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
from src.modulos.central_acoes import presentation
from src.modulos.central_acoes.calculations import ActionStatus
from src.modulos.central_acoes.service import ActionListing, ActionRow
from src.modulos.central_acoes.validation import ActionFilters

TITLE = "Central de Ações"
TABLE_TITLE = "Ações"
FILTERS_LABEL = "Filtros"
ACTION_COUNT_LABEL = "Ações no filtro"

STATUS_TONES = {
    ActionStatus.COMPLETED: Tone.OK,
    ActionStatus.OVERDUE: Tone.ERROR,
    ActionStatus.IN_PROGRESS: Tone.INFO,
    ActionStatus.INFORMATION: Tone.NEUTRAL,
}


def build_document(
    *,
    listing: ActionListing,
    filters: ActionFilters,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the screen for the filters in force: KPIs, filters and the table."""
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            (FILTERS_LABEL, presentation.summary(filters, listing.responsibles)),
            (ACTION_COUNT_LABEL, str(listing.total)),
        ),
        kpis=_kpis(listing),
        tables=(_table(listing.rows),),
        paper=Paper.A3,
    )


def _kpis(listing: ActionListing) -> tuple[Kpi, ...]:
    counts = listing.counts
    share = listing.overdue_share
    return (
        Kpi(
            "Em dia",
            counts.on_time,
            f"Esperado: {counts.open}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status="Prazo vigente ainda não venceu",
        ),
        Kpi(
            "Atrasadas",
            counts.overdue,
            "Meta: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if counts.overdue else Tone.OK,
            status="Sem atrasadas" if share is None else f"{share}% das abertas",
        ),
        Kpi(
            "Concluídas",
            counts.completed,
            f"Previsto: {listing.due_by_reference}",
            ValueKind.INTEGER,
            tone=Tone.OK,
            status="Com data de conclusão",
        ),
        Kpi(
            "Total de ações",
            counts.total,
            f"Referência: {listing.universe}",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status=f"{counts.open} em andamento",
        ),
    )


def _table(rows: Sequence[ActionRow]) -> Table:
    return Table(
        title=TABLE_TITLE,
        columns=(
            Column("Origem", width=14),
            Column("Referência", width=20),
            Column("Item", width=8),
            Column("Assunto", width=40),
            Column("Descrição", width=50),
            Column("Grupo", width=22),
            Column("Solicitante", width=22),
            Column("Responsável", width=22),
            Column("Prazo vigente", ValueKind.DATE),
            Column("Prevista", ValueKind.DATE),
            Column("Replanejada", ValueKind.DATE),
            Column("Conclusão", ValueKind.DATE),
            Column("Status", width=14),
            Column("Dias de atraso", ValueKind.INTEGER),
        ),
        rows=tuple(_row(line) for line in rows),
    )


def _row(line: ActionRow) -> Row:
    record = line.record
    return row(
        record.origin,
        record.origin_ref,
        record.item,
        record.subject,
        record.description,
        record.group,
        line.requester_name,
        line.responsible_name,
        record.due_date,
        record.planned_date,
        record.replanned_date,
        record.completed_on,
        Cell(record.status_label, STATUS_TONES[record.status]),
        record.days_overdue or None,
        project=line.project_label,
    )
