"""Input validation of the Weekly Scheduling: the activity and the panels of the flow (D10).

The pure passes: what was filled, whether the daily plan adds up to the weekly
figure, the reading of the panels of validation, done work and approval, and the
configuration of the project (the parameters and the window of a company). The
passes that need the database (the register the person chose, the repeated ID, the
deviation limit, the company of a window) live in the facade. Messages are the
app's, field by field; the keys are the names of the form fields, in Portuguese
like the rest of the interface.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, time

from src.core import calendario
from src.modulos.programacao_semanal import calculations, weeks
from src.modulos.programacao_semanal import window as window_rules

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

# The app's defaults for a project that has no configuration row yet (D10); the facade
# imports them to build the row, and ``parse_settings`` to refill an empty form.
DEFAULT_ADHERENCE_TARGET = 60.0
DEFAULT_PPC_TARGET = 75.0
DEFAULT_DEVIATION_LIMIT = 15.0

INVALID_WEEK_MESSAGE = "Informe uma semana válida, no formato S.30/2026."

# The window form: the app's defaults when the day is informed and the hours are empty.
WEEKDAY_VALUES = ("1", "2", "3", "4", "5", "6", "7")
DEFAULT_OPENS = "00:01"
DEFAULT_CLOSES = "23:59"

WINDOW_COMPANY_REQUIRED = "Informe a empresa da janela."
WINDOW_WEEKDAY_INVALID = "Escolha um dia da semana válido."
WINDOW_OPENS_REQUIRED = "Informe o horário de abertura."
WINDOW_CLOSES_REQUIRED = "Informe o horário de fechamento."
WINDOW_TIME_INVALID = "Informe um horário válido (HH:MM)."
WINDOW_CLOSES_BEFORE_OPENS = "O fechamento é antes da abertura."
WINDOW_WEEK_INVALID = "A semana “{week}” não é válida."
WINDOW_EXTRA_WEEK_INVALID = "Informe uma semana válida para a liberação extraordinária."
WINDOW_EXTRA_OPENS_REQUIRED = "Informe o início da liberação extraordinária."
WINDOW_EXTRA_CLOSES_REQUIRED = "Informe o fim da liberação extraordinária."
WINDOW_EXTRA_MOMENT_INVALID = "Informe uma data e hora válidas."
WINDOW_EXTRA_CLOSES_BEFORE_OPENS = "O fim da liberação é antes do início."


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


@dataclass(frozen=True)
class ValidationForm:
    """What the planner typed in the panel of validation: the inspector and the comments."""

    inspector_id: int | None = None
    comments: str = ""


@dataclass(frozen=True)
class DoneForm:
    """What was reported in the panel of the done work: both shifts and the justification."""

    day_shift: tuple[float, ...] = field(default_factory=lambda: (0.0,) * calculations.DAYS)
    night_shift: tuple[float, ...] = field(default_factory=lambda: (0.0,) * calculations.DAYS)
    notes: str = ""


@dataclass(frozen=True)
class ApprovalForm:
    """What the inspector typed in the panel of approval: the comments or the reason to reopen."""

    comments: str = ""
    reason: str = ""


@dataclass(frozen=True)
class DecisionForm:
    """What the planner chose in the queue of change requests: decide, answer and version."""

    apply: bool = False
    answer: str = ""
    version: str = ""


@dataclass(frozen=True)
class ScheduleSettingsForm:
    """What the planner typed in the parameters of the schedule, already as numbers."""

    adherence_target: float = DEFAULT_ADHERENCE_TARGET
    ppc_target: float = DEFAULT_PPC_TARGET
    reference_week: str = ""
    requires_deviation_note: bool = True
    deviation_limit: float = DEFAULT_DEVIATION_LIMIT


@dataclass(frozen=True)
class WindowForm:
    """What the planner typed in the window of one company, still as text.

    ``weekday`` is the ISO number as the select sends it (``1`` to ``7``); empty means
    any day of the released weeks. The times and the extraordinary release keep the raw
    text so the pure pass can refuse what is not a time or an instant.
    """

    company_id: int | None = None
    weekday: str = ""
    opens: str = ""
    closes: str = ""
    weeks: tuple[str, ...] = ()
    extra_week: str = ""
    extra_opens: str = ""
    extra_closes: str = ""
    remove_extra: str = ""


def parse_validation(values: Mapping[str, str | None]) -> ValidationForm:
    """Read the fields of the validation panel (``responsavel``, ``comentarios``)."""
    return ValidationForm(
        inspector_id=parse_id(values.get("responsavel")),
        comments=_text(values, "comentarios"),
    )


def parse_done(values: Mapping[str, str | None]) -> DoneForm:
    """Read the fields of the done panel (``dias_realizado_0``... and ``observacoes``)."""
    day_shift = calculations.seven_days(
        [values.get(f"dias_realizado_{index}") for index in range(calculations.DAYS)]
    )
    night_shift = calculations.seven_days(
        [values.get(f"dias_noite_{index}") for index in range(calculations.DAYS)]
    )
    return DoneForm(
        day_shift=tuple(day_shift),
        night_shift=tuple(night_shift),
        notes=_text(values, "observacoes"),
    )


def parse_approval(values: Mapping[str, str | None]) -> ApprovalForm:
    """Read the fields of the approval panel (``comentarios``) and of the reopen (``motivo``)."""
    return ApprovalForm(comments=_text(values, "comentarios"), reason=_text(values, "motivo"))


def parse_decision(values: Mapping[str, str | None]) -> DecisionForm:
    """Read the fields of the queue decision (``decisao``, ``resposta``, ``versao``)."""
    return DecisionForm(
        apply=_text(values, "decisao") == "aplicar",
        answer=_text(values, "resposta"),
        version=_text(values, "versao"),
    )


def parse_settings(values: Mapping[str, str | None]) -> ScheduleSettingsForm:
    """Read the parameters form (``meta_aderencia``, ``meta_ppc``...), with the app's defaults.

    The number fields are ``type=number`` on the screen; what arrives is read with the
    app's rule (``calculos.numero``): an empty or unreadable value falls back to the
    default, and the pure pass checks the range.
    """
    return ScheduleSettingsForm(
        adherence_target=calculations.to_number(
            values.get("meta_aderencia"), DEFAULT_ADHERENCE_TARGET
        ),
        ppc_target=calculations.to_number(values.get("meta_ppc"), DEFAULT_PPC_TARGET),
        reference_week=_text(values, "semana_referencia"),
        requires_deviation_note=_text(values, "exige_justificativa_desvio") == "sim",
        deviation_limit=calculations.to_number(
            values.get("limite_desvio_justificativa"), DEFAULT_DEVIATION_LIMIT
        ),
    )


def parse_window(
    values: Mapping[str, str | None], *, selected_weeks: Iterable[str] = ()
) -> WindowForm:
    """Read the window form; ``selected_weeks`` are the repeated ``semanas`` checkboxes."""
    return WindowForm(
        company_id=parse_id(values.get("empresa")),
        weekday=_text(values, "dia"),
        opens=_text(values, "abre"),
        closes=_text(values, "fecha"),
        weeks=tuple(
            sorted({week.strip() for week in selected_weeks if week.strip()}, key=weeks.sort_key)
        ),
        extra_week=_text(values, "extra_semana"),
        extra_opens=_text(values, "extra_abre"),
        extra_closes=_text(values, "extra_fecha"),
        remove_extra=_text(values, "remover_extra"),
    )


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


def settings_errors(form: ScheduleSettingsForm) -> dict[str, str]:
    """The pure pass of the parameters: the percentages in range and a real reference week."""
    errors: dict[str, str] = {}
    checks = (
        ("meta_aderencia", form.adherence_target, "a meta de aderência"),
        ("meta_ppc", form.ppc_target, "a meta de PPC"),
        ("limite_desvio_justificativa", form.deviation_limit, "o limite de desvio"),
    )
    for name, value, label in checks:
        if not 0 <= value <= 100:
            errors[name] = f"Informe {label} entre 0 e 100."
    if form.reference_week and not weeks.is_valid(form.reference_week):
        errors["semana_referencia"] = INVALID_WEEK_MESSAGE
    return errors


def window_errors(form: WindowForm) -> dict[str, str]:
    """The pure pass of the window: the day and hours, the released weeks and the exception."""
    errors: dict[str, str] = {}
    if form.company_id is None:
        errors["empresa"] = WINDOW_COMPANY_REQUIRED
    _weekday_errors(form, errors)
    _week_errors(form, errors)
    _extra_errors(form, errors)
    return errors


def window_of(
    form: WindowForm,
    *,
    company_id: int,
    extras: Sequence[window_rules.ExtraRelease] = (),
) -> window_rules.Window:
    """The window of a validated form; the facade merges the extraordinary releases."""
    rule = _day_rule(form)
    return window_rules.Window(
        company_id=company_id,
        days=(rule,) if rule is not None else (),
        weeks=frozenset(form.weeks),
        extras=tuple(extras),
    )


def merge_extras(
    current: Sequence[window_rules.ExtraRelease], form: WindowForm
) -> tuple[window_rules.ExtraRelease, ...]:
    """The extraordinary releases after the form: the removed one goes, the same week is replaced."""
    replaced = {form.remove_extra, form.extra_week} - {""}
    kept = [extra for extra in current if extra.week not in replaced]
    new = _new_extra(form)
    if new is not None:
        kept.append(new)
    return tuple(sorted(kept, key=lambda extra: (weeks.sort_key(extra.week), extra.opens)))


def _weekday_errors(form: WindowForm, errors: dict[str, str]) -> None:
    if form.weekday and form.weekday not in WEEKDAY_VALUES:
        errors["dia"] = WINDOW_WEEKDAY_INVALID
        return
    if not form.weekday:
        return
    opens, closes = _clock(form.opens), _clock(form.closes)
    if not form.opens:
        errors["abre"] = WINDOW_OPENS_REQUIRED
    elif opens is None:
        errors["abre"] = WINDOW_TIME_INVALID
    if not form.closes:
        errors["fecha"] = WINDOW_CLOSES_REQUIRED
    elif closes is None:
        errors["fecha"] = WINDOW_TIME_INVALID
    elif opens is not None and _minute(closes) < _minute(opens):
        errors["fecha"] = WINDOW_CLOSES_BEFORE_OPENS


def _week_errors(form: WindowForm, errors: dict[str, str]) -> None:
    for week in form.weeks:
        if not weeks.is_valid(week):
            errors["semanas"] = WINDOW_WEEK_INVALID.format(week=week)
            return


def _extra_errors(form: WindowForm, errors: dict[str, str]) -> None:
    if not form.extra_week:
        return
    if not weeks.is_valid(form.extra_week):
        errors["extra_semana"] = WINDOW_EXTRA_WEEK_INVALID
    opens, closes = _moment(form.extra_opens), _moment(form.extra_closes)
    if not form.extra_opens:
        errors["extra_abre"] = WINDOW_EXTRA_OPENS_REQUIRED
    elif opens is None:
        errors["extra_abre"] = WINDOW_EXTRA_MOMENT_INVALID
    if not form.extra_closes:
        errors["extra_fecha"] = WINDOW_EXTRA_CLOSES_REQUIRED
    elif closes is None:
        errors["extra_fecha"] = WINDOW_EXTRA_MOMENT_INVALID
    if opens is not None and closes is not None and closes <= opens:
        errors["extra_fecha"] = WINDOW_EXTRA_CLOSES_BEFORE_OPENS


def _day_rule(form: WindowForm) -> window_rules.WindowDay | None:
    """The regular rule of a validated form: its day and hours, or none for any-day windows."""
    if not form.weekday:
        return None
    return window_rules.WindowDay(
        weekday=int(form.weekday),
        opens=_clock(form.opens) or time(0, 1),
        closes=_clock(form.closes) or time(23, 59),
    )


def _new_extra(form: WindowForm) -> window_rules.ExtraRelease | None:
    if not form.extra_week:
        return None
    opens, closes = _moment(form.extra_opens), _moment(form.extra_closes)
    if opens is None or closes is None:
        return None
    return window_rules.ExtraRelease(week=form.extra_week, opens=opens, closes=closes)


def _clock(text: str) -> time | None:
    try:
        return time.fromisoformat(text)
    except ValueError:
        return None


def _minute(moment: time) -> tuple[int, int]:
    return (moment.hour, moment.minute)


def _moment(text: str) -> datetime | None:
    """A ``datetime-local`` instant in the product's timezone: the window compares aware instants."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment.replace(tzinfo=calendario.PRODUCT_TIMEZONE)
