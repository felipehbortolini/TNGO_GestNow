"""The exports of the minutes: the list of Atas and the ficha of one ata (D12, ISSUE-021).

What the screen shows is what leaves. The list exports the columns the prototype exported (number,
revision, date, subject, main company, meeting type, open and overdue actions), with ``Projeto`` in
the Portfólio (HU-016); the ficha exports the data of the meeting as header lines and two tables,
the executing companies and the attendance list with the open actions of each person.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
    Column,
    Document,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.central_acoes.minutes_service import (
    ItemListing,
    ItemRow,
    MinutesListing,
    MinutesRow,
    MinutesSheet,
)

LIST_TITLE = "Central de Ações · Atas"
LIST_TABLE_TITLE = "Atas"
COUNT_LABEL = "Atas no filtro"
SEARCH_LABEL = "Busca"
SHEET_COMPANIES_TITLE = "Empresas executoras"
SHEET_ATTENDANCE_TITLE = "Lista de Presença"
SHEET_ITEMS_TITLE = "Anotações e Ações"


def build_list_document(
    *,
    listing: MinutesListing,
    search: str,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the list of minutes for the search in force."""
    context = [(COUNT_LABEL, str(listing.total))]
    if search:
        context.insert(0, (SEARCH_LABEL, search))
    return Document(
        title=LIST_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=tuple(context),
        tables=(_list_table(listing.rows),),
    )


def _list_table(rows: Sequence[MinutesRow]) -> Table:
    return Table(
        title=LIST_TABLE_TITLE,
        columns=(
            Column("Número", width=16),
            Column("Rev", ValueKind.INTEGER),
            Column("Data", ValueKind.DATE),
            Column("Assunto", width=60),
            Column("Empresa principal", width=26),
            Column("Tipo de reunião", width=26),
            Column("Ações abertas", ValueKind.INTEGER),
            Column("Atrasadas", ValueKind.INTEGER),
        ),
        rows=tuple(_list_row(line) for line in rows),
    )


def _list_row(line: MinutesRow) -> Row:
    record = line.record
    return row(
        record.number,
        record.revision,
        record.meeting_date,
        record.subject,
        line.main_company_name,
        record.meeting_type,
        line.open_count,
        Cell(line.overdue_count, Tone.ERROR if line.overdue_count else None),
        project=line.project_label,
    )


def build_sheet_document(*, sheet: MinutesSheet, items: ItemListing, today: date) -> Document:
    """The document of the ficha: the data, the companies, the attendance and the items."""
    record = sheet.record
    counts = sheet.counts
    return Document(
        title=f"Ata {record.number} Rev {record.revision}",
        scope_label=sheet.project_label,
        generated_on=today,
        context=(
            ("Data", f"{record.meeting_date:%d/%m/%Y}"),
            ("Tipo de reunião", record.meeting_type),
            ("Diretoria", record.board),
            ("Unidade", sheet.unit_name),
            ("Elaborado por", sheet.prepared_by_name),
            ("Assunto", record.subject),
            ("Empresa principal", sheet.main_company_name or "—"),
            (
                "Ações",
                f"{counts.total} ({counts.open} abertas, {counts.overdue} atrasadas)",
            ),
        ),
        tables=(
            Table(
                title=SHEET_COMPANIES_TITLE,
                columns=(Column("Empresa", width=40), Column("Principal", width=12)),
                rows=tuple(
                    row(company.name, "Sim" if company.is_main else "Não")
                    for company in sheet.companies
                ),
                per_project=False,
            ),
            Table(
                title=SHEET_ATTENDANCE_TITLE,
                columns=(
                    Column("Nome", width=30),
                    Column("Função", width=26),
                    Column("Empresa", width=26),
                    Column("E-mail", width=34),
                    Column("Ações abertas nesta ata", ValueKind.INTEGER),
                ),
                rows=tuple(
                    row(
                        attendee.person.name,
                        attendee.person.role,
                        attendee.company_name,
                        attendee.person.email,
                        attendee.open_count,
                    )
                    for attendee in sheet.attendees
                ),
                per_project=False,
            ),
            _items_table(items),
        ),
    )


def _items_table(items: ItemListing) -> Table:
    return Table(
        title=SHEET_ITEMS_TITLE,
        columns=(
            Column("Item", width=8),
            Column("Grupo", width=18),
            Column("Tipo", width=12),
            Column("Assunto / Descrição", width=56),
            Column("Responsável", width=24),
            Column("Prevista", ValueKind.DATE),
            Column("Replanejada", ValueKind.DATE),
            Column("Status", width=14),
        ),
        rows=tuple(_item_row(item) for group in items.groups for item in group.items),
        per_project=False,
    )


def _item_row(item: ItemRow) -> Row:
    return row(
        item.item,
        item.group,
        item.kind,
        f"{item.subject} · {item.description}" if item.description else item.subject,
        item.responsible_name,
        item.planned_date,
        item.replanned_date,
        item.status_label,
    )
