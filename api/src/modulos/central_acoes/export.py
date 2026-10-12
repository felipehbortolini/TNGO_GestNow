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

from src.core import translations
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


def _label(text: str, idioma: str) -> str:
    """O texto de interface da Central no idioma do request (D13)."""
    return translations.translate("central_acoes", text, idioma)


def build_document(
    *,
    listing: ActionListing,
    filters: ActionFilters,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """The document of the screen for the filters in force: KPIs, filters and the table."""
    return Document(
        namespace="central_acoes",
        title=_label(TITLE, idioma),
        scope_label=describe_scope(scope, projects, idioma),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            (
                _label(FILTERS_LABEL, idioma),
                presentation.summary(filters, listing.responsibles, idioma),
            ),
            (_label(ACTION_COUNT_LABEL, idioma), str(listing.total)),
        ),
        kpis=_kpis(listing, idioma),
        tables=(_table(listing.rows, idioma),),
        paper=Paper.A3,
        idioma=idioma,
    )


def _kpis(listing: ActionListing, idioma: str) -> tuple[Kpi, ...]:
    counts = listing.counts
    share = listing.overdue_share
    return (
        Kpi(
            _label("Em dia", idioma),
            counts.on_time,
            _label("Esperado: {value}", idioma).format(value=counts.open),
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=_label("Prazo vigente ainda não venceu", idioma),
        ),
        Kpi(
            _label("Atrasadas", idioma),
            counts.overdue,
            _label("Meta: 0", idioma),
            ValueKind.INTEGER,
            tone=Tone.ERROR if counts.overdue else Tone.OK,
            status=(
                _label("Sem atrasadas", idioma)
                if share is None
                else _label("{value}% das abertas", idioma).format(value=share)
            ),
        ),
        Kpi(
            _label("Concluídas", idioma),
            counts.completed,
            _label("Previsto: {value}", idioma).format(value=listing.due_by_reference),
            ValueKind.INTEGER,
            tone=Tone.OK,
            status=_label("Com data de conclusão", idioma),
        ),
        Kpi(
            _label("Total de ações", idioma),
            counts.total,
            _label("Referência: {value}", idioma).format(value=listing.universe),
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status=_label("{value} em andamento", idioma).format(value=counts.open),
        ),
    )


def _table(rows: Sequence[ActionRow], idioma: str) -> Table:
    return Table(
        title=_label(TABLE_TITLE, idioma),
        columns=(
            Column(_label("Origem", idioma), width=14),
            Column(_label("Referência", idioma), width=20),
            Column(_label("Item", idioma), width=8),
            Column(_label("Assunto", idioma), width=40),
            Column(_label("Descrição", idioma), width=50),
            Column(_label("Grupo", idioma), width=22),
            Column(_label("Solicitante", idioma), width=22),
            Column(_label("Responsável", idioma), width=22),
            Column(_label("Prazo vigente", idioma), ValueKind.DATE),
            Column(_label("Prevista", idioma), ValueKind.DATE),
            Column(_label("Replanejada", idioma), ValueKind.DATE),
            Column(_label("Conclusão", idioma), ValueKind.DATE),
            Column(_label("Status", idioma), width=14),
            Column(_label("Dias de atraso", idioma), ValueKind.INTEGER),
        ),
        rows=tuple(_row(line, idioma) for line in rows),
    )


def _row(line: ActionRow, idioma: str) -> Row:
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
        Cell(_label(record.status_label, idioma), STATUS_TONES[record.status]),
        record.days_overdue or None,
        project=line.project_label,
    )
