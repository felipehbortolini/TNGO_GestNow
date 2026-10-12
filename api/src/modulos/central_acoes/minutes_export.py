"""The exports of the minutes: the list of Atas and the ficha of one ata (D12, ISSUE-021).

What the screen shows is what leaves. The list exports the columns the prototype exported (number,
revision, date, subject, main company, meeting type, open and overdue actions), with ``Projeto`` in
the Portfólio (HU-016); the ficha exports the data of the meeting as header lines and two tables,
the executing companies and the attendance list with the open actions of each person.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core import translations
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


def _label(text: str, idioma: str) -> str:
    """O texto de interface da Central no idioma do request (D13)."""
    return translations.translate("central_acoes", text, idioma)


def build_list_document(
    *,
    listing: MinutesListing,
    search: str,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """The document of the list of minutes for the search in force."""
    context = [(_label(COUNT_LABEL, idioma), str(listing.total))]
    if search:
        context.insert(0, (_label(SEARCH_LABEL, idioma), search))
    return Document(
        namespace="central_acoes",
        title=_label(LIST_TITLE, idioma),
        scope_label=describe_scope(scope, projects, idioma),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=tuple(context),
        tables=(_list_table(listing.rows, idioma),),
        idioma=idioma,
    )


def _list_table(rows: Sequence[MinutesRow], idioma: str) -> Table:
    return Table(
        title=_label(LIST_TABLE_TITLE, idioma),
        columns=(
            Column(_label("Número", idioma), width=16),
            Column("Rev", ValueKind.INTEGER),
            Column(_label("Data", idioma), ValueKind.DATE),
            Column(_label("Assunto", idioma), width=60),
            Column(_label("Empresa principal", idioma), width=26),
            Column(_label("Tipo de reunião", idioma), width=26),
            Column(_label("Ações abertas", idioma), ValueKind.INTEGER),
            Column(_label("Atrasadas", idioma), ValueKind.INTEGER),
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


def build_sheet_document(
    *, sheet: MinutesSheet, items: ItemListing, today: date, idioma: str = "pt"
) -> Document:
    """The document of the ficha: the data, the companies, the attendance and the items."""
    record = sheet.record
    counts = sheet.counts
    return Document(
        namespace="central_acoes",
        title=f"{_label('Ata', idioma)} {record.number} Rev {record.revision}",
        scope_label=sheet.project_label,
        generated_on=today,
        context=(
            (_label("Data", idioma), translations.format_date(record.meeting_date, idioma)),
            (_label("Tipo de reunião", idioma), record.meeting_type),
            (_label("Diretoria", idioma), record.board),
            (_label("Unidade", idioma), sheet.unit_name),
            (_label("Elaborado por", idioma), sheet.prepared_by_name),
            (_label("Assunto", idioma), record.subject),
            (_label("Empresa principal", idioma), sheet.main_company_name or "—"),
            (
                _label("Ações", idioma),
                _label("{total} ({open} abertas, {overdue} atrasadas)", idioma).format(
                    total=counts.total, open=counts.open, overdue=counts.overdue
                ),
            ),
        ),
        tables=(
            Table(
                title=_label(SHEET_COMPANIES_TITLE, idioma),
                columns=(
                    Column(_label("Empresa", idioma), width=40),
                    Column(_label("Principal", idioma), width=12),
                ),
                rows=tuple(
                    row(
                        company.name,
                        _label("Sim", idioma) if company.is_main else _label("Não", idioma),
                    )
                    for company in sheet.companies
                ),
                per_project=False,
            ),
            Table(
                title=_label(SHEET_ATTENDANCE_TITLE, idioma),
                columns=(
                    Column(_label("Nome", idioma), width=30),
                    Column(_label("Função", idioma), width=26),
                    Column(_label("Empresa", idioma), width=26),
                    Column("E-mail", width=34),
                    Column(_label("Ações abertas nesta ata", idioma), ValueKind.INTEGER),
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
            _items_table(items, idioma),
        ),
        idioma=idioma,
    )


def _items_table(items: ItemListing, idioma: str) -> Table:
    return Table(
        title=_label(SHEET_ITEMS_TITLE, idioma),
        columns=(
            Column(_label("Item", idioma), width=8),
            Column(_label("Grupo", idioma), width=18),
            Column(_label("Tipo", idioma), width=12),
            Column(_label("Assunto / Descrição", idioma), width=56),
            Column(_label("Responsável", idioma), width=24),
            Column(_label("Prevista", idioma), ValueKind.DATE),
            Column(_label("Replanejada", idioma), ValueKind.DATE),
            Column(_label("Status", idioma), width=14),
        ),
        rows=tuple(_item_row(item, idioma) for group in items.groups for item in group.items),
        per_project=False,
    )


def _item_row(item: ItemRow, idioma: str) -> Row:
    return row(
        item.item,
        item.group,
        _label(item.kind, idioma),
        f"{item.subject} · {item.description}" if item.description else item.subject,
        item.responsible_name,
        item.planned_date,
        item.replanned_date,
        _label(item.status_label, idioma),
    )
