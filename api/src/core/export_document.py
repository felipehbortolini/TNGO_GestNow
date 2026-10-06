"""What a screen hands to the export: one description, two outputs (D12).

A screen builds a ``Document`` once (title, scope, generation date, KPIs with
their management reference, charts and tables) and gets both exports from it:
the Excel (``core.excel``) and the printable version (``core.printable``),
which the browser turns into a PDF. Because the same description feeds both,
nothing the Excel exports is missing on paper and the other way round ("nem uma
coluna a menos").

The document holds data, never pixels: a table cell is a value with an optional
``Tone`` (the situation colors of the Design System), and each output draws it
with the tokens of ``app/ds/tokens.css``. Money travels as integer cents
(``ValueKind.MONEY``) and reaches the reader in full reais; the generation date
is an argument, read from the clock only at the edge of the route
(``calendario.today()``).

In the Portfólio every table opens with the ``Projeto`` column (HU-016), filled
from the ``project`` of each row; a table that is not per project says so with
``per_project=False``. A document that breaks its own contract (a row with the
wrong number of cells, a Portfólio row without its project, a text in a
number column) fails loud with ``InvalidDocumentError``: it is a mistake of the
screen that built it, found in the test of that screen.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from src.core.money import format_brl

if TYPE_CHECKING:
    from src.core.navigation_view import ProjectLike
    from src.core.scope import Scope

PRODUCT_NAME = "Timenow GestNow"
PORTFOLIO_LABEL = "Portfólio"
PROJECT_HEADER = "Projeto"
SCOPE_HEADING = "Escopo"
GENERATED_HEADING = "Gerado em"

type CellValue = str | int | float | Decimal | date | None


class InvalidDocumentError(ValueError):
    """The document breaks the contract of the export: a mistake of the screen, not of the data."""

    def __init__(self, problem: str) -> None:
        super().__init__(problem)


class Tone(StrEnum):
    """The situation colors of the Design System; the value is the suffix of its CSS classes."""

    OK = "ok"
    WARN = "warn"
    ERROR = "erro"
    INFO = "info"
    NEUTRAL = "neutro"


class ValueKind(StrEnum):
    """What a column or a KPI holds: it decides the format on paper and in the spreadsheet.

    ``DECIMAL`` and ``PERCENT`` take their decimal places from ``digits``
    (``PERCENT`` holds percentage points: ``45.3`` is ``45,3%``). ``MONEY`` holds
    integer cents and always reaches the reader in full reais, never in
    thousands. ``DATE`` holds a ``datetime.date``.
    """

    TEXT = "texto"
    INTEGER = "inteiro"
    DECIMAL = "decimal"
    PERCENT = "percentual"
    MONEY = "dinheiro"
    DATE = "data"


class Paper(StrEnum):
    """The paper of the printable version and of the print setup of the spreadsheet (landscape)."""

    A4 = "a4"
    A3 = "a3"


@dataclass(frozen=True)
class Column:
    """A column: its header, what it holds and, for the Excel, an optional width in characters."""

    header: str
    kind: ValueKind = ValueKind.TEXT
    digits: int = 2
    width: int | None = None


@dataclass(frozen=True)
class Cell:
    """A value and, when the situation deserves a color, its tone."""

    value: CellValue = None
    tone: Tone | None = None


@dataclass(frozen=True)
class Row:
    """The cells of a row, in the order of the columns, and the project the row belongs to.

    ``project`` is the text of the ``Projeto`` column (``project_label``); it is
    required only in the Portfólio.
    """

    cells: tuple[Cell, ...]
    project: str | None = None


@dataclass(frozen=True)
class Table:
    """A titled table; ``totals`` is the closing row, one cell per column, when the screen has one."""

    title: str
    columns: tuple[Column, ...]
    rows: tuple[Row, ...] = ()
    totals: tuple[Cell, ...] | None = None
    per_project: bool = True


@dataclass(frozen=True)
class Kpi:
    """An indicator with the management reference it is read against (target or band).

    ``reference`` is written the way the screen shows it (``Meta: 95%``);
    ``status`` is the situation in words, so the color never stands alone.
    """

    label: str
    value: CellValue
    reference: str
    kind: ValueKind = ValueKind.TEXT
    digits: int = 2
    tone: Tone | None = None
    status: str = ""


@dataclass(frozen=True)
class Chart:
    """A chart of the printable version: the ``data-grafico`` type and its ``data-dados``.

    The Excel has no chart: a screen that wants the numbers behind it in the
    spreadsheet adds them as a table.
    """

    title: str
    kind: str
    data: Mapping[str, Any]


@dataclass(frozen=True)
class Document:
    """Everything an export carries: the identification, the KPIs, the charts and the tables.

    ``scope_label`` and ``portfolio`` come from the scope of the request
    (``describe_scope(scope, projects)`` and ``scope.is_portfolio``);
    ``context`` holds the extra lines of the header, as ``(label, value)``
    pairs (``("Período", "S39/2026")``).
    """

    title: str
    scope_label: str
    generated_on: date
    portfolio: bool = False
    context: tuple[tuple[str, str], ...] = ()
    kpis: tuple[Kpi, ...] = ()
    charts: tuple[Chart, ...] = ()
    tables: tuple[Table, ...] = ()
    paper: Paper = Paper.A4

    def __post_init__(self) -> None:
        for table in self.tables:
            _check_table(table, portfolio=self.portfolio)


def row(*cells: Cell | CellValue, project: str | None = None) -> Row:
    """A row from plain values, with ``Cell`` for the ones that carry a tone."""
    return Row(
        cells=tuple(cell if isinstance(cell, Cell) else Cell(cell) for cell in cells),
        project=project,
    )


def project_label(project: ProjectLike) -> str:
    """``TN-001 · Nome do projeto``: how a project is named in the scope selector and in exports."""
    return f"{project.code} · {project.name}"


def describe_scope(scope: Scope, projects: Sequence[ProjectLike]) -> str:
    """``Portfólio`` or ``TN-001 · Nome do projeto``: the scope line of every export header."""
    if scope.is_portfolio:
        return PORTFOLIO_LABEL
    chosen = next((project for project in projects if project.id == scope.project_id), None)
    return project_label(chosen) if chosen is not None else f"Projeto {scope.project_id}"


def resolve_tables(document: Document) -> tuple[Table, ...]:
    """The tables as they are exported: in the Portfólio each one opens with ``Projeto`` (HU-016)."""
    if not document.portfolio:
        return document.tables
    return tuple(
        _with_project_column(table) if _adds_project_column(table) else table
        for table in document.tables
    )


# ── Values as a person reads them ────────────────────────────────────────


def format_value(kind: ValueKind, value: CellValue, digits: int = 2) -> str:
    """The text of a value: ``1.234,50``, ``45,3%``, ``R$ 1.234,56`` or ``05/10/2026``.

    ``None`` is the empty text. Both outputs use it, so paper and spreadsheet
    agree on how a number is written.
    """
    if value is None:
        return ""
    return _FORMATTERS[kind](value, digits)


def number_of(value: CellValue) -> Decimal:
    """The value as a finite decimal number; a text or a date in a number column is a mistake."""
    number = _decimal_or_none(value)
    if number is None or not number.is_finite():
        problem = f"Valor numérico esperado, recebido {value!r}."
        raise InvalidDocumentError(problem)
    return number


def cents_of(value: CellValue) -> int:
    """The integer cents of a money value; a fraction of a cent is a mistake."""
    number = number_of(value)
    if number != number.to_integral_value():
        problem = f"Valor em centavos esperado (inteiro), recebido {value!r}."
        raise InvalidDocumentError(problem)
    return int(number)


def date_of(value: CellValue) -> date:
    """The value as a date; anything else in a date column is a mistake."""
    found = value if isinstance(value, date) else None
    if found is None:
        problem = f"Data esperada, recebido {value!r}."
        raise InvalidDocumentError(problem)
    return found


# ── Internals ────────────────────────────────────────────────────────────

# The thousands and decimal separators of Brazilian Portuguese: ``1,234.50`` becomes ``1.234,50``.
_PT_BR_SEPARATORS = str.maketrans({",": ".", ".": ","})


def _decimal_or_none(value: CellValue) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, int | Decimal):
        return Decimal(value)
    return None


def _decimal_text(number: Decimal, digits: int) -> str:
    rounded = number.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    text = f"{abs(rounded):,.{digits}f}".translate(_PT_BR_SEPARATORS)
    return f"-{text}" if rounded < 0 else text


def _text(value: CellValue, _digits: int) -> str:
    return str(value)


def _integer(value: CellValue, _digits: int) -> str:
    return _decimal_text(number_of(value), 0)


def _decimal(value: CellValue, digits: int) -> str:
    return _decimal_text(number_of(value), digits)


def _percent(value: CellValue, digits: int) -> str:
    return f"{_decimal_text(number_of(value), digits)}%"


def _money(value: CellValue, _digits: int) -> str:
    return format_brl(cents_of(value))


def _date(value: CellValue, _digits: int) -> str:
    return date_of(value).strftime("%d/%m/%Y")


_FORMATTERS: Mapping[ValueKind, Callable[[CellValue, int], str]] = {
    ValueKind.TEXT: _text,
    ValueKind.INTEGER: _integer,
    ValueKind.DECIMAL: _decimal,
    ValueKind.PERCENT: _percent,
    ValueKind.MONEY: _money,
    ValueKind.DATE: _date,
}


def _adds_project_column(table: Table) -> bool:
    """Whether the Portfólio gives the table its ``Projeto`` column: it asks for it and has none."""
    return table.per_project and all(column.header != PROJECT_HEADER for column in table.columns)


def _with_project_column(table: Table) -> Table:
    return replace(
        table,
        columns=(Column(PROJECT_HEADER), *table.columns),
        rows=tuple(replace(item, cells=(Cell(item.project), *item.cells)) for item in table.rows),
        totals=None if table.totals is None else (Cell(), *table.totals),
    )


def _check_table(table: Table, *, portfolio: bool) -> None:
    width = len(table.columns)
    needs_project = portfolio and _adds_project_column(table)
    for number, item in enumerate(table.rows, start=1):
        if len(item.cells) != width:
            problem = (
                f"Tabela «{table.title}», linha {number}: {len(item.cells)} células "
                f"para {width} colunas."
            )
            raise InvalidDocumentError(problem)
        if needs_project and not item.project:
            problem = (
                f"Tabela «{table.title}», linha {number}: no Portfólio toda linha traz o projeto."
            )
            raise InvalidDocumentError(problem)
    if table.totals is not None and len(table.totals) != width:
        problem = f"Tabela «{table.title}»: a linha de totais tem {len(table.totals)} células para {width} colunas."
        raise InvalidDocumentError(problem)
