"""Importing a spreadsheet in steps: model, upload, check line by line, confirm (D12, HU-139, ISSUE-018).

The import is one flow of the server that every module reuses; a module only registers its
``Importer``: the columns, the validation of one line and the write of one line through its
own facade. The steps, and what each one may and may not do:

1. **Model**: ``model_document`` is the ``Document`` of the empty workbook the person downloads
   (``core.excel`` builds it, like every other spreadsheet): the header of the columns in the
   ``Dados`` sheet and, in ``Instruções``, what each column asks (required, format, example).
2. **Upload and check**: ``check`` reads the file (``core.spreadsheet_reader``: anything that is
   not an ``.xlsx`` is 422), finds the header, converts every cell to the type of its column
   (``core.import_values``) and asks the importer to validate each line. It returns the
   ``ImportPreview``: an **error** blocks its line, a **warning** does not, and every one has its
   reason and its line in the sheet. ``check`` never writes: what the importer's ``validate``
   receives is the session to read, nothing else.
3. **Confirm**: ``confirm`` reads and checks the same file again (it trusts nothing the screen
   says about it) and writes **every line that has no error, or none**: all the writes happen in
   one savepoint, so a refusal of any line undoes the ones before it. Lines with an error are not
   written; if there are any, the person must have acknowledged it. The file must be the very one
   that was checked (its digest travels from the check to the confirmation).
4. **Cancel** is closing the check: no step before the confirmation keeps anything, in the
   database or anywhere, so there is nothing to undo.

The server holds no state between the steps: the confirmation receives the file again, from the
form that still holds it. The writes go through the facade of the module that owns the table
(``Importer.save``), which leaves the trail and the version, inside the transaction of the
request. A line is numbered as Excel shows it, so the person finds it in the sheet.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy.orm import Session

from src.core import attachments, rbac
from src.core.errors import InvalidDataError
from src.core.export_document import (
    Column,
    Document,
    Table,
    ValueKind,
    describe_scope,
    format_value,
    row,
)
from src.core.import_values import convert, is_blank, normalize_text, text_of
from src.core.rbac import Permission
from src.core.spreadsheet_reader import (
    HEADER_SCAN_ROWS,
    MAX_DATA_ROWS,
    RawCell,
    SheetRow,
    read_rows,
)
from src.modulos.configuracoes import service as configuracoes

if TYPE_CHECKING:
    from src.core.rbac import User
    from src.core.scope import Scope

MODEL_SHEET = "Dados"
INSTRUCTIONS_SHEET = "Instruções"
MODEL_TITLE = "Modelo de importação"

YES = "Sim"
NO = "Não"

INSTRUCTIONS_HEADERS = ("Coluna", "Obrigatória", "Formato", "Exemplo")
INSTRUCTIONS_WIDTHS = (28, 14, 48, 28)
MIN_HEADER_WIDTH = 14
HEADER_WIDTH_PADDING = 4

# The format each kind of column asks, as the instructions sheet writes it.
FORMAT_HINTS: Mapping[ValueKind, str] = {
    ValueKind.TEXT: "texto",
    ValueKind.INTEGER: "número inteiro",
    ValueKind.DECIMAL: "número (ex.: 12,5)",
    ValueKind.PERCENT: "percentual (ex.: 45,5)",
    ValueKind.MONEY: "valor em reais (ex.: 1234,56)",
    ValueKind.DATE: "dd/mm/aaaa",
}
OPTIONS_HINT = "um de: {options}"

# What the check prints and what the confirmation refuses, in the words of the screen.
REQUIRED_PROBLEM = "obrigatório"
ROW_PROBLEM = "{header}: {problem}"
REPEATED_PROBLEM = "repete a linha {line} (mesmo valor em {columns})"
TOO_MANY_ROWS_MESSAGE = (
    "A planilha passa de {limit} linhas de dados. Divida a importação em planilhas menores."
)
MISSING_MESSAGE = "Colunas obrigatórias ausentes: {columns}. Baixe o modelo e ajuste a planilha."
NOT_CHECKED_MESSAGE = "Confira a planilha antes de importar: nada é gravado sem a conferência."
CHANGED_MESSAGE = "O arquivo mudou depois da conferência. Envie-o e confira de novo."
NOTHING_MESSAGE = "Nada a importar: nenhuma linha passou na conferência."
NOT_ACKNOWLEDGED_MESSAGE = (
    "Confirme que está ciente de que as linhas com erro não serão importadas."
)
ROW_REFUSED_MESSAGE = "Linha {line}: {reason} Nada foi importado."
UNKNOWN_IMPORTER_MESSAGE = "A importação pedida não existe."

# How much of the check the screen prints: every problem up to the cap, and a sample of the
# lines that will be written (the first lines, already converted).
PREVIEW_ROWS = 20
LISTED_PROBLEMS = 200

_KEY = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


class InvalidImporterError(ValueError):
    """The importer breaks the contract of the flow: a mistake of the module that registered it."""

    def __init__(self, problem: str) -> None:
        super().__init__(problem)


# ── What a module registers ──────────────────────────────────────────────


@dataclass(frozen=True)
class ImportColumn:
    """A column of the model: the field of the values, the header of the sheet and what it holds.

    ``options`` turns a text column into a list (the value is one of them, ignoring case and
    accents); ``example`` is the text the instructions sheet shows for the column.
    """

    field: str
    header: str
    kind: ValueKind = ValueKind.TEXT
    required: bool = False
    options: tuple[str, ...] = ()
    example: str = ""
    digits: int = 2

    @property
    def format_hint(self) -> str:
        """What the column asks of the person: ``dd/mm/aaaa``, ``um de: Sim, Não``..."""
        if self.options:
            return OPTIONS_HINT.format(options=", ".join(self.options))
        return FORMAT_HINTS[self.kind]


@dataclass(frozen=True)
class RowCheck:
    """What a module says of one line: the errors that block it and the warnings that do not."""

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


VALID = RowCheck()


@dataclass(frozen=True)
class ImportContext:
    """Who imports, in which scope and on which date: what the module's rules receive."""

    user: User
    scope: Scope
    reference_date: date


class RowValidator(Protocol):
    """The validation of one line, with its values already converted: it reads, it never writes."""

    def __call__(
        self, session: Session, *, values: Mapping[str, Any], context: ImportContext
    ) -> RowCheck:
        """The errors and the warnings of the line."""


class RowWriter(Protocol):
    """The write of one line, through the facade of the module that owns the table."""

    def __call__(
        self, session: Session, *, values: Mapping[str, Any], context: ImportContext
    ) -> object:
        """Write the line (trail and version come from ``core.recording``)."""


@dataclass(frozen=True)
class Importer:
    """The importer of a module: its columns, the validation of a line and its write.

    ``key`` names it in the address (``punch-list``); ``module`` is the folder of the module that
    owns the data (the person must reach it) and ``permission`` is what the import asks beyond
    that (writing, by default). ``unique`` lists the fields whose combination may not repeat in
    the file; what already exists in the database is for ``validate`` to say.
    """

    key: str
    title: str
    module: str
    columns: tuple[ImportColumn, ...]
    validate: RowValidator
    save: RowWriter
    permission: Permission = Permission.WRITE
    unique: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            problem = f"Importador «{self.key}»: a chave usa letras minúsculas, números e hífens."
            raise InvalidImporterError(problem)
        fields = [column.field for column in self.columns]
        headers = [normalize_text(column.header) for column in self.columns]
        if not fields or len(set(fields)) != len(fields) or len(set(headers)) != len(headers):
            problem = (
                f"Importador «{self.key}»: precisa de colunas, sem campo nem cabeçalho repetido."
            )
            raise InvalidImporterError(problem)
        if any(name not in fields for name in self.unique):
            problem = f"Importador «{self.key}»: a unicidade cita um campo que não existe."
            raise InvalidImporterError(problem)


_IMPORTERS: dict[str, Importer] = {}


def register(importer: Importer) -> None:
    """Register the importer of a module; two modules cannot share a key.

    Registering the very same importer again does nothing, so a module that is imported twice
    does not fail; a different one under a taken key does.
    """
    known = _IMPORTERS.get(importer.key)
    if known is not None and known != importer:
        message = f"O importador {importer.key} já está registrado por outro módulo."
        raise ValueError(message)
    _IMPORTERS[importer.key] = importer


def find(key: str) -> Importer | None:
    """The importer registered under the key, or ``None`` when no module registered it."""
    return _IMPORTERS.get(key)


def registered() -> list[Importer]:
    """The registered importers, in registration order."""
    return list(_IMPORTERS.values())


def require(key: str) -> Importer:
    """The importer registered under the key, or 422 when the address names none."""
    importer = find(key)
    if importer is None:
        raise InvalidDataError(UNKNOWN_IMPORTER_MESSAGE)
    return importer


def authorize(importer: Importer, user: User) -> None:
    """Refuse with 403 when the user does not reach the module of the importer or may not write."""
    rbac.require_module(user, importer.module)
    rbac.require(user, importer.permission)


# ── Step 1: the model ────────────────────────────────────────────────────


def model_document(session: Session, *, importer: Importer, context: ImportContext) -> Document:
    """The empty workbook of the importer: the header in ``Dados`` and the ``Instruções`` sheet."""
    authorize(importer, context.user)
    return Document(
        title=f"{MODEL_TITLE}: {importer.title}",
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=context.reference_date,
        tables=(_data_table(importer), _instructions_table(importer)),
    )


def _data_table(importer: Importer) -> Table:
    """Only the header: an example row would be imported by whoever forgot to delete it."""
    columns = tuple(
        Column(
            column.header,
            column.kind,
            column.digits,
            width=max(MIN_HEADER_WIDTH, len(column.header) + HEADER_WIDTH_PADDING),
        )
        for column in importer.columns
    )
    return Table(MODEL_SHEET, columns, per_project=False)


def _instructions_table(importer: Importer) -> Table:
    columns = tuple(
        Column(header, width=width)
        for header, width in zip(INSTRUCTIONS_HEADERS, INSTRUCTIONS_WIDTHS, strict=True)
    )
    rows = tuple(
        row(column.header, YES if column.required else NO, column.format_hint, column.example)
        for column in importer.columns
    )
    return Table(INSTRUCTIONS_SHEET, columns, rows=rows, per_project=False)


# ── Step 2: upload and check ─────────────────────────────────────────────


@dataclass(frozen=True)
class Upload:
    """The file as the browser sent it: its name and its bytes."""

    name: str | None
    content: bytes


@dataclass(frozen=True)
class CheckedRow:
    """A line of the sheet after the check: its values, how it reads, and why it passes or not."""

    number: int
    values: Mapping[str, Any]
    shown: tuple[str, ...]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def writable(self) -> bool:
        """Whether the line will be written: an error blocks it, a warning does not."""
        return not self.errors

    @property
    def problems(self) -> tuple[str, ...]:
        """Every reason of the line, errors first."""
        return self.errors + self.warnings


@dataclass(frozen=True)
class ImportPreview:
    """What the check found in the file: the lines, what is missing and what was ignored.

    ``missing`` are the required columns the file lacks (nothing is checked then) and
    ``ignored`` the headers of the file that are not in the model. ``digest`` identifies the
    checked file: the confirmation is only accepted for it.
    """

    file_name: str
    digest: str
    columns: tuple[ImportColumn, ...]
    rows: tuple[CheckedRow, ...]
    missing: tuple[str, ...] = ()
    ignored: tuple[str, ...] = ()

    @property
    def writable_rows(self) -> tuple[CheckedRow, ...]:
        """The lines the confirmation writes: with no error, with or without warning."""
        return tuple(item for item in self.rows if item.writable)

    @property
    def error_rows(self) -> tuple[CheckedRow, ...]:
        """The lines an error blocks."""
        return tuple(item for item in self.rows if not item.writable)

    @property
    def warning_rows(self) -> tuple[CheckedRow, ...]:
        """The lines that will be written in spite of a warning."""
        return tuple(item for item in self.rows if item.writable and item.warnings)

    @property
    def can_confirm(self) -> bool:
        """Whether there is something to write: the columns are there and a line passes."""
        return not self.missing and bool(self.writable_rows)

    @property
    def problem_rows(self) -> tuple[CheckedRow, ...]:
        """The lines to list as a problem, errors and warnings, up to the cap of the screen."""
        return tuple(item for item in self.rows if item.problems)[:LISTED_PROBLEMS]

    @property
    def unlisted_problems(self) -> int:
        """How many lines with a problem the cap left out of the list."""
        return max(0, sum(1 for item in self.rows if item.problems) - LISTED_PROBLEMS)

    @property
    def sample_rows(self) -> tuple[CheckedRow, ...]:
        """The first lines that will be written, as the table of the preview prints them."""
        return self.writable_rows[:PREVIEW_ROWS]


def check(
    session: Session, *, importer: Importer, upload: Upload, context: ImportContext
) -> ImportPreview:
    """Read the file and check every line; nothing is written (the 422 of a bad file comes from here)."""
    authorize(importer, context.user)
    sheet = read_rows(upload.name, upload.content)
    layout = _find_layout(sheet, importer.columns)
    return ImportPreview(
        file_name=attachments.clean_name(upload.name),
        digest=digest_of(upload),
        columns=importer.columns,
        rows=_check_rows(session, importer, layout, sheet, context),
        missing=layout.missing,
        ignored=layout.ignored,
    )


def digest_of(upload: Upload) -> str:
    """The identity of the file: what the check hands to the confirmation."""
    return hashlib.sha256(upload.content).hexdigest()


@dataclass(frozen=True)
class _Layout:
    """Where the columns are in the sheet: the header row, each field's position, what is off."""

    header_row: int
    positions: Mapping[str, int]
    missing: tuple[str, ...]
    ignored: tuple[str, ...]


def _find_layout(sheet: tuple[SheetRow, ...], columns: tuple[ImportColumn, ...]) -> _Layout:
    """The header is the row, among the first ones, that names the most columns of the model."""
    best_row: SheetRow | None = None
    best: dict[str, int] = {}
    for candidate in sheet[:HEADER_SCAN_ROWS]:
        found = _match_headers(candidate, columns)
        if len(found) > len(best):
            best_row, best = candidate, found
    missing = tuple(
        column.header
        for column in columns
        if column.field not in best and (column.required or not best)
    )
    return _Layout(
        header_row=best_row.number if best_row is not None else 0,
        positions=best,
        missing=missing,
        ignored=_ignored_headers(best_row, best),
    )


def _match_headers(candidate: SheetRow, columns: tuple[ImportColumn, ...]) -> dict[str, int]:
    """The position of each column of the model whose header is in the row (first one wins)."""
    wanted = {normalize_text(column.header): column.field for column in columns}
    found: dict[str, int] = {}
    for index, cell in enumerate(candidate.cells):
        if is_blank(cell.value):
            continue
        name = wanted.get(normalize_text(text_of(cell.value)))
        if name is not None and name not in found:
            found[name] = index
    return found


def _ignored_headers(header: SheetRow | None, positions: Mapping[str, int]) -> tuple[str, ...]:
    if header is None:
        return ()
    used = set(positions.values())
    return tuple(
        text_of(cell.value)
        for index, cell in enumerate(header.cells)
        if index not in used and not is_blank(cell.value)
    )


def _check_rows(
    session: Session,
    importer: Importer,
    layout: _Layout,
    sheet: tuple[SheetRow, ...],
    context: ImportContext,
) -> tuple[CheckedRow, ...]:
    """Every non-empty line under the header, checked; none when the file lacks a column."""
    if layout.missing or not layout.positions:
        return ()
    lines = [
        line
        for line in sheet
        if line.number > layout.header_row and not _is_empty(line, layout.positions)
    ]
    if len(lines) > MAX_DATA_ROWS:
        limit = format_value(ValueKind.INTEGER, MAX_DATA_ROWS)
        raise InvalidDataError(TOO_MANY_ROWS_MESSAGE.format(limit=limit))
    checker = _RowChecker(session, importer, layout, context)
    return tuple(checker.check(line) for line in lines)


def _is_empty(line: SheetRow, positions: Mapping[str, int]) -> bool:
    """A line with nothing in the columns of the model is spacing, not data."""
    return all(
        index >= len(line.cells) or is_blank(line.cells[index].value)
        for index in positions.values()
    )


class _RowChecker:
    """Checks the lines of one file in order: conversion, repetition in the file, then the module."""

    def __init__(
        self, session: Session, importer: Importer, layout: _Layout, context: ImportContext
    ) -> None:
        self._session = session
        self._importer = importer
        self._layout = layout
        self._context = context
        self._seen: dict[tuple[Any, ...], int] = {}

    def check(self, line: SheetRow) -> CheckedRow:
        """The values of the line, how it reads and the reasons it is blocked or only warned."""
        values: dict[str, Any] = {}
        shown: list[str] = []
        errors: list[str] = []
        for column in self._importer.columns:
            value, text, problem = self._read(column, line)
            values[column.field] = value
            shown.append(text)
            if problem:
                errors.append(ROW_PROBLEM.format(header=column.header, problem=problem))
        warnings: list[str] = []
        if not errors:
            errors.extend(self._repeated(values, line.number))
        if not errors:
            verdict = self._importer.validate(self._session, values=values, context=self._context)
            errors.extend(verdict.errors)
            warnings.extend(verdict.warnings)
        return CheckedRow(
            number=line.number,
            values=values,
            shown=tuple(shown),
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def _read(self, column: ImportColumn, line: SheetRow) -> tuple[Any, str, str | None]:
        """The value, its text for the preview and the problem of one cell."""
        position = self._layout.positions.get(column.field)
        cell = _cell_at(line, position)
        if cell is None or is_blank(cell.value):
            required = column.required and position is not None
            return None, "", REQUIRED_PROBLEM if required else None
        converted = convert(cell, column.kind, options=column.options)
        if converted.problem is not None:
            return None, text_of(cell.value), converted.problem
        return converted.value, _shown(column, converted.value), None

    def _repeated(self, values: Mapping[str, Any], number: int) -> list[str]:
        """The error of a line that repeats the key of an earlier one of the same file."""
        fields = self._importer.unique
        key = tuple(_comparable(values[name]) for name in fields)
        if not fields or any(part is None for part in key):
            return []
        first = self._seen.setdefault(key, number)
        if first == number:
            return []
        headers = [column.header for column in self._importer.columns if column.field in fields]
        return [REPEATED_PROBLEM.format(line=first, columns=", ".join(headers))]


def _cell_at(line: SheetRow, position: int | None) -> RawCell | None:
    if position is None or position >= len(line.cells):
        return None
    return line.cells[position]


def _comparable(value: Any) -> Any:
    return normalize_text(value) if isinstance(value, str) else value


def _shown(column: ImportColumn, value: Any) -> str:
    """The value as the preview prints it: ``R$ 1.234,56``, ``05/10/2026``, ``45,5%``."""
    if column.kind is ValueKind.TEXT:
        return str(value)
    return format_value(column.kind, value, column.digits)


# ── Step 3: confirm ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Confirmation:
    """What the person did on the check: the digest of the file it showed and the acknowledgement."""

    checked_digest: str | None
    acknowledged: bool = False


@dataclass(frozen=True)
class ImportResult:
    """What the confirmation did: the lines written and the ones an error left out."""

    file_name: str
    written: tuple[CheckedRow, ...]
    skipped: tuple[CheckedRow, ...]

    @property
    def with_warning(self) -> int:
        """How many of the written lines carried a warning."""
        return sum(1 for item in self.written if item.warnings)


def confirm(
    session: Session,
    *,
    importer: Importer,
    upload: Upload,
    context: ImportContext,
    confirmation: Confirmation,
) -> ImportResult:
    """Write every line without error, all or none, after checking the file again.

    The lines are written inside one savepoint: if the module refuses any of them, the ones
    before it are undone too and the refusal (422) names the line. The trail and the version of
    every record come from the facade the importer writes through.
    """
    authorize(importer, context.user)
    _require_checked(upload, confirmation)
    preview = check(session, importer=importer, upload=upload, context=context)
    _require_confirmable(preview, confirmation)
    _write_all(session, importer, preview.writable_rows, context)
    return ImportResult(
        file_name=preview.file_name, written=preview.writable_rows, skipped=preview.error_rows
    )


def _require_checked(upload: Upload, confirmation: Confirmation) -> None:
    """The confirmation is for the file that was checked, and only for it."""
    if not confirmation.checked_digest:
        raise InvalidDataError(NOT_CHECKED_MESSAGE)
    if confirmation.checked_digest != digest_of(upload):
        raise InvalidDataError(CHANGED_MESSAGE)


def _require_confirmable(preview: ImportPreview, confirmation: Confirmation) -> None:
    if preview.missing:
        raise InvalidDataError(MISSING_MESSAGE.format(columns=", ".join(preview.missing)))
    if not preview.writable_rows:
        raise InvalidDataError(NOTHING_MESSAGE)
    if preview.error_rows and not confirmation.acknowledged:
        raise InvalidDataError(NOT_ACKNOWLEDGED_MESSAGE)


def _write_all(
    session: Session,
    importer: Importer,
    rows: tuple[CheckedRow, ...],
    context: ImportContext,
) -> None:
    with session.begin_nested():
        for item in rows:
            _write_row(session, importer, item, context)


def _write_row(
    session: Session, importer: Importer, item: CheckedRow, context: ImportContext
) -> None:
    try:
        importer.save(session, values=item.values, context=context)
    except InvalidDataError as error:
        reason = str(error)
        raise InvalidDataError(
            ROW_REFUSED_MESSAGE.format(line=item.number, reason=reason)
        ) from error
