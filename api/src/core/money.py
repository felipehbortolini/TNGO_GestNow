"""Money as integer cents (D5): reais only when the value reaches a screen.

The column type stores cents in a bigint and hands Python plain ints, so
arithmetic is exact and nothing formats itself. Formatting lives in
``format_brl``, used by the ``brl`` Jinja filter and, later, by the
exports.
"""

from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class Centavos(TypeDecorator[int]):
    """Bigint column of cents; the Python value is an int in cents."""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: int | None, dialect: Dialect) -> int | None:
        return None if value is None else int(value)

    def process_result_value(self, value: int | None, dialect: Dialect) -> int | None:
        return None if value is None else int(value)


def format_brl(cents: int | None) -> str:
    """Format cents as Brazilian reais, presentation only: ``123456`` -> ``R$ 1.234,56``."""
    if cents is None:
        return ""
    value = int(cents)
    reais, centavos = divmod(abs(value), 100)
    body = f"{reais:,}".replace(",", ".")
    sign = "-" if value < 0 else ""
    return f"{sign}R$ {body},{centavos:02d}"
