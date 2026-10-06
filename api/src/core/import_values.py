"""From the cell of the spreadsheet to the typed value of the importer (D12, ISSUE-018).

One function per rule, each with its own name and test: ``convert`` turns what a person typed
or Excel stored in a cell into the value of its column, or into the short reason it cannot
(``número inválido``, ``data inválida (use dd/mm/aaaa)``...), which the check prints after the
name of the column. The rules are those of the prototype's ``importar.js``:

* ``TEXT``: the trimmed text; with ``options`` it must be one of them, ignoring case and
  accents, and the value is the option as the module wrote it;
* ``INTEGER``, ``DECIMAL``, ``PERCENT``: a number. A text may carry ``R$``, ``%`` and spaces;
  with a comma, the dots are thousands separators (``1.234,5`` is 1234.5); without one, the dot
  is the decimal mark. A percent cell (number format with ``%``) holds a fraction and is read
  back as percentage points (``0.453`` is 45.3); a text or a plain number already is in points;
* ``MONEY``: reais in the cell, **integer cents** in the value (``1234,56`` is 123456), rounded
  half up like every money in the product;
* ``DATE``: a date cell, a text ``dd/mm/aaaa`` (``dd/mm/aa`` is 20aa) or ``aaaa-mm-dd``, or the
  serial number Excel keeps; a day that does not exist (``31/02/2026``) is invalid.

A blank cell is not converted: whether it is allowed is the column's ``required``.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from src.core.export_document import ValueKind
from src.core.spreadsheet_reader import RawCell

NUMBER_PROBLEM = "número inválido"
INTEGER_PROBLEM = "número inteiro inválido"
MONEY_PROBLEM = "valor inválido"
DATE_PROBLEM = "data inválida (use dd/mm/aaaa)"
RANGE_PROBLEM = "número fora do limite"
OPTION_PROBLEM = "valor fora da lista ({options})"

# No number of a spreadsheet of this product comes near this; it keeps a typo from
# overflowing the cents column.
MAX_ABSOLUTE_NUMBER = Decimal(10) ** 15

# Excel counts days from 1899-12-30 (the 1900 leap-year bug is already folded into it); the last
# serial that still is a valid date is 9999-12-31.
EXCEL_EPOCH = date(1899, 12, 30)
MAX_EXCEL_SERIAL = 2_958_465

_NUMBER_TEXT = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)")
_NUMBER_DECORATION = re.compile(r"R\$|%|\s")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_BR_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})")
_SPACES = re.compile(r"\s+")
_TWO_DIGIT_YEAR = 2


@dataclass(frozen=True)
class Converted:
    """The value of the cell in the type of its column, or the reason it cannot be."""

    value: Any = None
    problem: str | None = None


def normalize_text(text: object) -> str:
    """The text without accents, in lower case and with single spaces: how headers and options match."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    bare = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _SPACES.sub(" ", bare).strip().casefold()


def is_blank(value: object) -> bool:
    """Whether the cell holds nothing a person typed: empty, or only spaces."""
    return value is None or (isinstance(value, str) and not value.strip())


def convert(cell: RawCell, kind: ValueKind, *, options: Sequence[str] = ()) -> Converted:
    """The value of a non-blank cell in the type of its column, or the reason it cannot."""
    if kind is ValueKind.TEXT:
        return _convert_text(cell.value, options)
    if kind is ValueKind.DATE:
        return _convert_date(cell.value)
    return _convert_number(cell, kind)


# ── Text and options ─────────────────────────────────────────────────────


def text_of(value: object) -> str:
    """The cell as text: a whole number has no ``.0`` and a date is written dd/mm/aaaa."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime):
        return value.date().strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value).strip()


def _convert_text(value: object, options: Sequence[str]) -> Converted:
    text = text_of(value)
    if not options:
        return Converted(value=text)
    wanted = normalize_text(text)
    chosen = next((option for option in options if normalize_text(option) == wanted), None)
    if chosen is None:
        return Converted(problem=OPTION_PROBLEM.format(options=", ".join(options)))
    return Converted(value=chosen)


# ── Numbers ──────────────────────────────────────────────────────────────


def number_of(value: object) -> Decimal | None:
    """The cell as a finite decimal number, or ``None`` when it is not one (a bool never is)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        number = Decimal(repr(value))
    elif isinstance(value, int | Decimal):
        number = Decimal(value)
    elif isinstance(value, str):
        number = _number_from_text(value)
    else:
        return None
    return number if number is not None and number.is_finite() else None


def _number_from_text(text: str) -> Decimal | None:
    cleaned = _NUMBER_DECORATION.sub("", text)
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    if _NUMBER_TEXT.fullmatch(cleaned) is None:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _convert_number(cell: RawCell, kind: ValueKind) -> Converted:
    number = number_of(cell.value)
    problem = MONEY_PROBLEM if kind is ValueKind.MONEY else NUMBER_PROBLEM
    if number is None:
        return Converted(problem=problem)
    if abs(number) > MAX_ABSOLUTE_NUMBER:
        return Converted(problem=RANGE_PROBLEM)
    if kind is ValueKind.INTEGER:
        return _integer(number)
    if kind is ValueKind.MONEY:
        return Converted(value=cents_of(number))
    if kind is ValueKind.PERCENT:
        return Converted(value=percent_points_of(cell, number))
    return Converted(value=number)


def _integer(number: Decimal) -> Converted:
    if number != number.to_integral_value():
        return Converted(problem=INTEGER_PROBLEM)
    return Converted(value=int(number))


def cents_of(reais: Decimal) -> int:
    """Reais as integer cents, rounded half up: ``1234.56`` is 123456 and ``0.005`` is 1."""
    return int((reais * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def percent_points_of(cell: RawCell, number: Decimal) -> Decimal:
    """Percentage points: a number cell formatted as percent holds a fraction, so it is times 100."""
    if isinstance(cell.value, str) or "%" not in cell.number_format:
        return number
    return number * 100


# ── Dates ────────────────────────────────────────────────────────────────


def _convert_date(value: object) -> Converted:
    found = date_of(value)
    if found is None:
        return Converted(problem=DATE_PROBLEM)
    return Converted(value=found)


def date_of(value: object) -> date | None:
    """The cell as a date, or ``None`` when it is not a real one."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return _date_from_serial(value)
    if isinstance(value, str):
        return _date_from_text(value.strip())
    return None


def _date_from_serial(serial: float) -> date | None:
    if not math.isfinite(serial):
        return None
    days = int(serial)
    if not 1 <= days <= MAX_EXCEL_SERIAL:
        return None
    return EXCEL_EPOCH + timedelta(days=days)


def _date_from_text(text: str) -> date | None:
    iso = _ISO_DATE.match(text)
    if iso is not None:
        return _valid_date(int(iso[1]), int(iso[2]), int(iso[3]))
    brazilian = _BR_DATE.fullmatch(text)
    if brazilian is None:
        return None
    year = brazilian[3]
    full_year = int(year) + 2000 if len(year) == _TWO_DIGIT_YEAR else int(year)
    return _valid_date(full_year, int(brazilian[2]), int(brazilian[1]))


def _valid_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
