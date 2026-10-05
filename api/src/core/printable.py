"""The printable version of a screen (D12): the sheet the PDF button opens and prints.

There is no PDF library, on the server or in the browser. The server renders the
printable version of the screen from the same ``Document`` the Excel uses (header
with the logo and the context, KPIs with their reference, charts and tables) as
the fragment ``comum/imprimivel.html``; the button ``data-tn-pdf`` (``ds/ui.js``)
fetches it, mounts it in the page and calls ``window.print()``; the person
chooses "Salvar como PDF". The paper is the job of ``app/ds/print.css``: A4
landscape by default, A3 landscape when the document asks (``Paper.A3``), no
navigation on the paper, the table header repeated on every page, rows that do
not break and the colors kept.

This module only turns the document into what the template prints: every value
already formatted as a person reads it, and the CSS classes of alignment and
tone decided here, so the template has no logic and a test reaches all of it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import azure.functions as func

from src.core.export_document import (
    Cell,
    Chart,
    Column,
    Document,
    Kpi,
    Table,
    Tone,
    ValueKind,
    format_value,
    resolve_tables,
)
from src.core.responses import AlpineAjaxResponse

TEMPLATE = "comum/imprimivel.html"

# The columns that read better to the right (numbers) or at the center (dates).
_ALIGNMENT = {
    ValueKind.INTEGER: "direita",
    ValueKind.DECIMAL: "direita",
    ValueKind.PERCENT: "direita",
    ValueKind.MONEY: "direita",
    ValueKind.DATE: "centro",
}


@dataclass(frozen=True)
class SheetColumn:
    """The header of a printed table: its text and its CSS classes."""

    header: str
    css: str


@dataclass(frozen=True)
class SheetCell:
    """A printed cell: the text a person reads and its CSS classes (alignment and tone)."""

    text: str
    css: str


@dataclass(frozen=True)
class SheetTable:
    """A printed table, with ``rows`` and ``totals`` already formatted."""

    title: str
    columns: tuple[SheetColumn, ...]
    rows: tuple[tuple[SheetCell, ...], ...]
    totals: tuple[SheetCell, ...] | None


@dataclass(frozen=True)
class SheetKpi:
    """A printed indicator: value, situation in words and the reference it is read against."""

    label: str
    value: str
    reference: str
    status: str
    css: str


@dataclass(frozen=True)
class Sheet:
    """Everything ``comum/imprimivel.html`` prints.

    ``paper`` is ``a4`` or ``a3`` (the sheet root takes the class that makes
    ``print.css`` pick the page); ``file_title`` becomes the title of the page
    while it prints, which the browser offers as the name of the PDF.
    """

    title: str
    scope_label: str
    generated_on: str
    context: tuple[tuple[str, str], ...]
    paper: str
    file_title: str
    kpis: tuple[SheetKpi, ...]
    charts: tuple[Chart, ...]
    tables: tuple[SheetTable, ...]


def build_sheet(document: Document) -> Sheet:
    """The document as the template prints it; in the Portfólio each table opens with ``Projeto``."""
    return Sheet(
        title=document.title,
        scope_label=document.scope_label,
        generated_on=format_value(ValueKind.DATE, document.generated_on),
        context=document.context,
        paper=document.paper.value,
        file_title=_file_title(document),
        kpis=tuple(_kpi(kpi) for kpi in document.kpis),
        charts=document.charts,
        tables=tuple(_table(table) for table in resolve_tables(document)),
    )


def printable_response(document: Document, req: func.HttpRequest) -> func.HttpResponse:
    """The fragment of the printable version, for the fetch of ``data-tn-pdf`` (``ds/ui.js``).

    The root takes its id from ``X-Alpine-Target``, which the button sends.
    """
    return AlpineAjaxResponse(
        template_name=TEMPLATE,
        context={"folha": build_sheet(document)},
        request=req,
    )


# ── Internals ────────────────────────────────────────────────────────────


def _file_title(document: Document) -> str:
    """``Mapa de controle - Portfólio - 2026-10-05``: what the browser suggests as the PDF name."""
    return f"{document.title} - {document.scope_label} - {document.generated_on.isoformat()}"


def _classes(base: str, *modifiers: str | None) -> str:
    """``folha__td folha__td--direita folha__td--ok``: the base class and one per modifier."""
    return " ".join([base, *(f"{base}--{modifier}" for modifier in modifiers if modifier)])


def _tone(tone: Tone | None) -> str | None:
    return None if tone is None else tone.value


def _kpi(kpi: Kpi) -> SheetKpi:
    return SheetKpi(
        label=kpi.label,
        value=format_value(kpi.kind, kpi.value, kpi.digits),
        reference=kpi.reference,
        status=kpi.status,
        css=_classes("folha__kpi", _tone(kpi.tone)),
    )


def _table(table: Table) -> SheetTable:
    return SheetTable(
        title=table.title,
        columns=tuple(
            SheetColumn(column.header, _classes("folha__th", _ALIGNMENT.get(column.kind)))
            for column in table.columns
        ),
        rows=tuple(_cells(table.columns, item.cells, total=False) for item in table.rows),
        totals=None if table.totals is None else _cells(table.columns, table.totals, total=True),
    )


def _cells(
    columns: Sequence[Column], cells: Sequence[Cell], *, total: bool
) -> tuple[SheetCell, ...]:
    return tuple(
        SheetCell(
            text=format_value(column.kind, cell.value, column.digits),
            css=_classes(
                "folha__td",
                _ALIGNMENT.get(column.kind),
                _tone(cell.tone),
                "total" if total else None,
            ),
        )
        for column, cell in zip(columns, cells, strict=True)
    )
