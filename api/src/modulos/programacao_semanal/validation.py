"""Input validation of the activity of the Weekly Scheduling (D10).

The pure passes: what was filled, and whether the daily plan adds up to the weekly
figure. The passes that need the database (the register the person chose, the
repeated ID) live in the facade. Messages are the app's, field by field; the keys
are the names of the form fields, in Portuguese like the rest of the interface.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.modulos.programacao_semanal import calculations

# Tolerance of the sum of the days against the weekly figure, as the app has it.
SUM_TOLERANCE = 0.51

# (form field, how the message names it)
REQUIRED_FIELDS = (
    ("semana", "a semana"),
    ("id_exclusiva", "a ID exclusiva"),
    ("atividade", "a descrição da atividade"),
    ("local", "o local"),
    ("empresa", "a empresa"),
    ("encarregado", "o encarregado"),
    ("unidade", "a unidade"),
)

MAX_UNIQUE_ID_LENGTH = 40

# A register id never has more digits than this; the cap keeps ``int`` away from absurd input.
MAX_ID_DIGITS = 18


@dataclass(frozen=True)
class ActivityForm:
    """What the person typed in the form of an activity, still as text and numbers."""

    week: str = ""
    unique_id: str = ""
    description: str = ""
    notes: str = ""
    location_id: int | None = None
    company_id: int | None = None
    foreman_id: int | None = None
    inspector_id: int | None = None
    unit_id: int | None = None
    headline: float = 0.0
    planned_days: tuple[float, ...] = field(default_factory=lambda: (0.0,) * calculations.DAYS)

    @property
    def planned_sum(self) -> float:
        """The sum of the planned days, rounded as the app rounds it."""
        return round(sum(self.planned_days), 2)


def parse_form(values: Mapping[str, str | None]) -> ActivityForm:
    """Read the form fields (``local``, ``dias_previsto_0``...) into an ``ActivityForm``."""
    days = calculations.seven_days(
        [values.get(f"dias_previsto_{index}") for index in range(calculations.DAYS)]
    )
    return ActivityForm(
        week=_text(values, "semana"),
        unique_id=_text(values, "id_exclusiva"),
        description=_text(values, "atividade"),
        notes=_text(values, "observacoes"),
        location_id=parse_id(values.get("local")),
        company_id=parse_id(values.get("empresa")),
        foreman_id=parse_id(values.get("encarregado")),
        inspector_id=parse_id(values.get("responsavel")),
        unit_id=parse_id(values.get("unidade")),
        headline=calculations.to_number(values.get("prod_prevista")),
        planned_days=tuple(days),
    )


def required_errors(form: ActivityForm) -> dict[str, str]:
    """Every required field that is empty, with the message of the app."""
    filled = {
        "semana": form.week,
        "id_exclusiva": form.unique_id,
        "atividade": form.description,
        "local": form.location_id,
        "empresa": form.company_id,
        "encarregado": form.foreman_id,
        "unidade": form.unit_id,
    }
    errors = {name: f"Informe {label}." for name, label in REQUIRED_FIELDS if not filled.get(name)}
    if len(form.unique_id) > MAX_UNIQUE_ID_LENGTH and "id_exclusiva" not in errors:
        errors["id_exclusiva"] = f"A ID exclusiva tem no máximo {MAX_UNIQUE_ID_LENGTH} caracteres."
    return errors


def quantity_errors(form: ActivityForm) -> dict[str, str]:
    """The daily plan has to add up to the weekly figure (tolerance of half a unit)."""
    errors: dict[str, str] = {}
    total = form.planned_sum
    headline = form.headline

    if total <= 0:
        errors["dias_previsto"] = "Distribua a produção prevista ao longo da semana."
    if headline <= 0:
        errors["prod_prevista"] = "Informe a produção prevista na semana."
    elif total > 0 and abs(total - headline) > SUM_TOLERANCE:
        errors["dias_previsto"] = (
            f"A soma dos dias ({total:g}) não bate com a produção prevista ({headline:g})."
        )
    return errors


def pure_errors(form: ActivityForm) -> dict[str, str]:
    """The passes that need no database: filled in, and the account closes."""
    return {**required_errors(form), **quantity_errors(form)}


def _text(values: Mapping[str, str | None], name: str) -> str:
    return str(values.get(name) or "").strip()


def parse_id(raw: str | None) -> int | None:
    """The id of a register chosen in a select; ``None`` for empty or anything but digits."""
    text = (raw or "").strip()
    if not (text.isascii() and text.isdecimal()) or len(text) > MAX_ID_DIGITS:
        return None
    return int(text)
