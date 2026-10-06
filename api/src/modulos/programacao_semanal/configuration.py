"""Facade of the configuration of the schedule, one per project (D10, ISSUE-054).

The "ambiente" of the app is the project of the scope (D8). What the app kept in its
Configurações and belongs to the scheduling is here: the parameters (targets, the
deviation rule), the window of each company, the released weeks and the extraordinary
releases. Companies and people are the registers of Configurações, never copied.

* **Who edits**: the Planejador of the project or the Admin (``permissions.can_configure``).
  The Planejador of another project gets 403. Anyone who reaches the module reads, and a
  supplier reads only the window of its own company.
* **Valid at once**: the schedule reads the rows on the next request; nothing is cached.
* **The trail keeps before and after** of every change, with no justified versioning
  (windows and releases change every week). The parameters go through ``core.recording``;
  the window, whose columns hold no content, writes a trail line with the content of the
  window (weekdays, weeks, extras) before and after.
* **A new project is born with the defaults of the app**: ``create_default_settings``,
  which the creation of a project calls (ISSUE-078). A project that has no row yet reads
  the same defaults.
* **Portfólio is read-only**: ``portfolio_overview`` lists each project; saving asks for one.

Nothing here reads the clock: the instant comes in the ``Caller``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.core import audit, calendario, rbac, recording, versioning
from src.core.errors import AccessDeniedError, InvalidDataError
from src.modulos.configuracoes import registers
from src.modulos.configuracoes import service as registers_facade
from src.modulos.programacao_semanal import calculations, permissions, repository, weeks
from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.models import (
    ScheduleSettings,
    ScheduleWindow,
    WindowExtraRelease,
    WindowWeek,
    WindowWeekday,
)
from src.modulos.programacao_semanal.service import Caller, ScheduleParameters

MAX_PERCENT = 100.0
DEFAULT_OPENS = time(0, 1)
DEFAULT_CLOSES = time(23, 59)
WEEKDAYS = tuple(window_rules.WEEKDAY_NAMES)
COMPANY_MISSING = "A empresa escolhida não está cadastrada. Cadastre em Configurações, em Empresas."
PERCENT_MESSAGE = "{label} deve ser um número de 0 a 100."
REFERENCE_WEEK_MESSAGE = "A semana de referência deve ter o formato S.30/2026."
EXTRA_INCOMPLETE = (
    "Preencha a semana, a abertura e o fechamento para incluir a liberação extraordinária."
)
EXTRA_ORDER = "A liberação extraordinária precisa abrir antes de fechar."
EXTRA_WEEK_MESSAGE = "A semana da liberação extraordinária deve ter o formato S.30/2026."
EXTRA_MOMENT_MESSAGE = "Informe a abertura e o fechamento da liberação extraordinária por inteiro."
WEEK_MESSAGE = "Semana liberada inválida: {week}."
CLOCK_MESSAGE = "Informe o horário de {name} no formato 08:00."
DAY_ORDER = "Em {name}, a janela precisa abrir antes de fechar."


# ── The parameters ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParametersForm:
    """What the person typed in the parameters: numbers still as text, the switch as a flag."""

    adherence_target: str = ""
    ppc_target: str = ""
    reference_week: str = ""
    requires_deviation_note: bool = True
    deviation_limit: str = ""


def parse_parameters(values: Mapping[str, str | None]) -> ParametersForm:
    """Read ``meta_aderencia``, ``meta_ppc``, ``semana_referencia``, ``exige_justificativa_desvio`` and the limit."""
    return ParametersForm(
        adherence_target=_text(values, "meta_aderencia"),
        ppc_target=_text(values, "meta_ppc"),
        reference_week=_text(values, "semana_referencia"),
        requires_deviation_note=_text(values, "exige_justificativa_desvio") == "sim",
        deviation_limit=_text(values, "limite_desvio_justificativa"),
    )


def check_parameters(form: ParametersForm) -> tuple[ScheduleParameters, dict[str, str]]:
    """The parameters of the form, with the default for an empty number, and the errors by field."""
    defaults = ScheduleParameters()
    errors: dict[str, str] = {}
    adherence = _percent(
        form.adherence_target,
        field="meta_aderencia",
        label="A meta de aderência",
        default=defaults.adherence_target,
        errors=errors,
    )
    ppc = _percent(
        form.ppc_target,
        field="meta_ppc",
        label="A meta de PPC",
        default=defaults.ppc_target,
        errors=errors,
    )
    limit = _percent(
        form.deviation_limit,
        field="limite_desvio_justificativa",
        label="O limite de desvio",
        default=defaults.deviation_limit,
        errors=errors,
    )
    if form.reference_week and not weeks.is_valid(form.reference_week):
        errors["semana_referencia"] = REFERENCE_WEEK_MESSAGE
    parameters = ScheduleParameters(
        adherence_target=adherence,
        ppc_target=ppc,
        reference_week=form.reference_week,
        requires_deviation_note=form.requires_deviation_note,
        deviation_limit=limit,
    )
    return parameters, errors


def create_default_settings(session: Session, *, user_id: int, project_id: int) -> ScheduleSettings:
    """The configuration of a new project, with the values of the app; the one it has, if any.

    The creation of a project (ISSUE-078) calls this inside its own transaction.
    """
    existing = repository.settings_of(session, project_id)
    if existing is not None:
        return existing
    return _create_settings(
        session, user_id=user_id, project_id=project_id, parameters=ScheduleParameters()
    )


def save_parameters(
    session: Session, *, caller: Caller, form: ParametersForm, version: str | None
) -> ScheduleSettings:
    """Save the parameters of the project in the scope, with the trail of before and after."""
    project_id = _editable_project(caller)
    parameters, errors = check_parameters(form)
    if errors:
        raise InvalidDataError(errors)
    row = repository.settings_of(session, project_id)
    if row is None:
        return _create_settings(
            session, user_id=caller.user.id, project_id=project_id, parameters=parameters
        )
    changes = {
        "adherence_target": parameters.adherence_target,
        "ppc_target": parameters.ppc_target,
        "reference_week": parameters.reference_week or None,
        "requires_deviation_note": parameters.requires_deviation_note,
        "deviation_limit": parameters.deviation_limit,
    }
    recording.update(session, user_id=caller.user.id, record=row, changes=changes, version=version)
    return row


# ── The window of a company ───────────────────────────────────────────────


@dataclass(frozen=True)
class WeekdayInput:
    """A weekday the regular window opens in, with the hours as typed."""

    weekday: int
    opens: str = ""
    closes: str = ""


@dataclass(frozen=True)
class WindowForm:
    """What the person typed for the window of one company."""

    company_id: int | None = None
    days: tuple[WeekdayInput, ...] = ()
    weeks: tuple[str, ...] = ()
    extra_week: str = ""
    extra_opens: str = ""
    extra_closes: str = ""
    remove_extra: str = ""


def parse_window(values: Mapping[str, str | None], *, weeks_checked: Sequence[str]) -> WindowForm:
    """Read ``empresa``, ``dia_1``..``dia_7`` with ``abre_N`` and ``fecha_N``, the weeks and the extra."""
    days = tuple(
        WeekdayInput(weekday, _text(values, f"abre_{weekday}"), _text(values, f"fecha_{weekday}"))
        for weekday in WEEKDAYS
        if _text(values, f"dia_{weekday}")
    )
    return WindowForm(
        company_id=_id(values.get("empresa")),
        days=days,
        weeks=tuple(week.strip() for week in weeks_checked if week and week.strip()),
        extra_week=_text(values, "extra_semana"),
        extra_opens=_text(values, "extra_abre"),
        extra_closes=_text(values, "extra_fecha"),
        remove_extra=_text(values, "remover_extra"),
    )


def build_rules(
    form: WindowForm, *, company_id: int, current: window_rules.Window | None
) -> tuple[window_rules.Window, dict[str, str]]:
    """The window the form asks for (the extras kept, replaced or removed) and the errors by field."""
    errors: dict[str, str] = {}
    days = _days_of(form, errors)
    released = _weeks_of(form, errors)
    extras = _extras_of(form, current, errors)
    rules = window_rules.Window(
        company_id=company_id, days=days, weeks=frozenset(released), extras=extras
    )
    return rules, errors


def save_window(
    session: Session, *, caller: Caller, form: WindowForm, version: str | None
) -> ScheduleWindow:
    """Save the window of one company in the project, with the trail of its content before and after."""
    project_id = _editable_project(caller)
    company_id = _known_company(session, form.company_id)
    current = repository.window_of(session, project_id=project_id, company_id=company_id)
    rules, errors = build_rules(form, company_id=company_id, current=current)
    if errors:
        raise InvalidDataError(errors)
    row = repository.windows_by_company(session, project_id=project_id).get(company_id)
    if row is None:
        return _create_window(session, user_id=caller.user.id, project_id=project_id, rules=rules)
    versioning.require(session, row, version)
    if rules == current:
        return row
    _replace_content(session, window_id=row.id, rules=rules)
    versioning.advance(row)
    session.flush()
    _trail(
        session,
        user_id=caller.user.id,
        row=row,
        before=content_of(current) if current else None,
        after=content_of(rules),
    )
    return row


def content_of(rules: window_rules.Window) -> dict[str, Any]:
    """The content of a window as the trail keeps it: weekdays, released weeks and extras."""
    return {
        "empresa_id": rules.company_id,
        "dias": [
            {
                "dia_semana": day.weekday,
                "abre": window_rules.hours_text(day.opens),
                "fecha": window_rules.hours_text(day.closes),
            }
            for day in rules.days
        ],
        "semanas": sorted(rules.weeks, key=weeks.sort_key),
        "liberacoes_extraordinarias": [
            {
                "semana": extra.week,
                "abre": extra.opens.isoformat(),
                "fecha": extra.closes.isoformat(),
            }
            for extra in rules.extras
        ],
    }


# ── What the screen reads ─────────────────────────────────────────────────


@dataclass(frozen=True)
class CompanyWindow:
    """A company, its window (``None`` while it has none) and the version of the row."""

    company_id: int
    company: str
    window: window_rules.Window | None
    version: int | None


@dataclass(frozen=True)
class ProjectConfiguration:
    """The configuration of the project in the scope, as the screen reads it."""

    project_id: int
    project: str
    parameters: ScheduleParameters
    version: int | None
    can_edit: bool
    windows: tuple[CompanyWindow, ...]


@dataclass(frozen=True)
class PortfolioRow:
    """One project of the Portfólio: its parameters and how many companies have a window."""

    project_id: int
    project: str
    parameters: ScheduleParameters
    windows: int


def project_configuration(session: Session, *, caller: Caller) -> ProjectConfiguration:
    """The configuration of the project in the scope; a supplier sees only its own company."""
    project_id = caller.scope.require_project()
    row = repository.settings_of(session, project_id)
    rows = repository.windows_by_company(session, project_id=project_id)
    companies = registers.list_companies(session, only=rbac.company_scope(caller.user))
    windows = tuple(
        CompanyWindow(
            company_id=company.id,
            company=company.label,
            window=repository.window_of(session, project_id=project_id, company_id=company.id),
            version=rows[company.id].version if company.id in rows else None,
        )
        for company in companies
    )
    labels = registers.project_labels(session, [project_id])
    return ProjectConfiguration(
        project_id=project_id,
        project=labels.get(project_id, ""),
        parameters=_parameters_of(row),
        version=row.version if row else None,
        can_edit=permissions.can_configure(caller.user, project_id),
        windows=windows,
    )


def portfolio_overview(session: Session) -> list[PortfolioRow]:
    """Every project with its parameters (the defaults while it has no row): the Portfólio reads."""
    by_project = {row.project_id: row for row in repository.all_settings(session)}
    counts = repository.window_counts(session)
    return [
        PortfolioRow(
            project_id=project.id,
            project=f"{project.code} · {project.name}",
            parameters=_parameters_of(by_project.get(project.id)),
            windows=counts.get(project.id, 0),
        )
        for project in registers_facade.list_projects(session)
    ]


def current_week_status(
    window: window_rules.Window | None, *, caller: Caller
) -> window_rules.WindowDecision:
    """Whether the window is open for the current week at the instant of the request, and why."""
    week = weeks.of_date(calendario.in_product_timezone(caller.now).date())
    return window_rules.decide(week, window, caller.now)


# ── Internals ─────────────────────────────────────────────────────────────


def _text(values: Mapping[str, str | None], name: str) -> str:
    return str(values.get(name) or "").strip()


def _id(raw: str | None) -> int | None:
    text = (raw or "").strip()
    return int(text) if text.isascii() and text.isdecimal() and len(text) < 19 else None


def _percent(raw: str, *, field: str, label: str, default: float, errors: dict[str, str]) -> float:
    """A percentage from 0 to 100; empty is the default of the app, anything else is an error."""
    if not raw:
        return default
    number = calculations.to_number(raw, default=-1.0)
    if not 0.0 <= number <= MAX_PERCENT:
        errors[field] = PERCENT_MESSAGE.format(label=label)
        return default
    return round(number, 2)


def _parameters_of(row: ScheduleSettings | None) -> ScheduleParameters:
    if row is None:
        return ScheduleParameters()
    return ScheduleParameters(
        adherence_target=row.adherence_target,
        ppc_target=row.ppc_target,
        reference_week=row.reference_week or "",
        requires_deviation_note=row.requires_deviation_note,
        deviation_limit=row.deviation_limit,
    )


def _editable_project(caller: Caller) -> int:
    """The project of the scope when the user may configure it: the Portfólio asks for one (422)."""
    project_id = caller.scope.require_project()
    if not permissions.can_configure(caller.user, project_id):
        raise AccessDeniedError(permissions.CONFIGURE_DENIED)
    return project_id


def _known_company(session: Session, company_id: int | None) -> int:
    known = {company.id for company in registers.list_companies(session)}
    if company_id is None or company_id not in known:
        raise InvalidDataError({"empresa": COMPANY_MISSING})
    return company_id


def _create_settings(
    session: Session, *, user_id: int, project_id: int, parameters: ScheduleParameters
) -> ScheduleSettings:
    row = ScheduleSettings(
        project_id=project_id,
        adherence_target=parameters.adherence_target,
        ppc_target=parameters.ppc_target,
        reference_week=parameters.reference_week or None,
        requires_deviation_note=parameters.requires_deviation_note,
        deviation_limit=parameters.deviation_limit,
    )
    recording.create(session, user_id=user_id, record=row)
    return row


def _clock(text: str, default: time) -> time | None:
    """A time written ``08:00``, the default when empty, ``None`` when it is not a time."""
    if not text:
        return default
    try:
        parsed = time.fromisoformat(text)
    except ValueError:
        return None
    return time(parsed.hour, parsed.minute)


def _days_of(form: WindowForm, errors: dict[str, str]) -> tuple[window_rules.WindowDay, ...]:
    days: list[window_rules.WindowDay] = []
    for given in sorted(form.days, key=lambda item: item.weekday):
        name = window_rules.WEEKDAY_NAMES.get(given.weekday)
        if name is None:
            continue
        opens = _clock(given.opens, DEFAULT_OPENS)
        closes = _clock(given.closes, DEFAULT_CLOSES)
        if opens is None or closes is None:
            errors[f"dia_{given.weekday}"] = CLOCK_MESSAGE.format(name=name)
        elif opens > closes:
            errors[f"dia_{given.weekday}"] = DAY_ORDER.format(name=name)
        else:
            days.append(window_rules.WindowDay(weekday=given.weekday, opens=opens, closes=closes))
    return tuple(days)


def _weeks_of(form: WindowForm, errors: dict[str, str]) -> list[str]:
    released = sorted(set(form.weeks), key=weeks.sort_key)
    invalid = [week for week in released if not weeks.is_valid(week)]
    if invalid:
        errors["semanas"] = WEEK_MESSAGE.format(week=invalid[0])
    return [week for week in released if week not in invalid]


def _moment(text: str) -> datetime | None:
    """A ``datetime-local`` value read in the product's timezone, or ``None`` when it is not one."""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=calendario.PRODUCT_TIMEZONE) if parsed.tzinfo is None else parsed


def _extras_of(
    form: WindowForm, current: window_rules.Window | None, errors: dict[str, str]
) -> tuple[window_rules.ExtraRelease, ...]:
    kept = [
        extra
        for extra in (current.extras if current else ())
        if extra.week not in (form.remove_extra, form.extra_week)
    ]
    typed = (form.extra_week, form.extra_opens, form.extra_closes)
    if any(typed):
        added = _typed_extra(form, errors)
        if added is not None:
            kept.append(added)
    return tuple(sorted(kept, key=lambda extra: (extra.opens, weeks.sort_key(extra.week))))


def _typed_extra(form: WindowForm, errors: dict[str, str]) -> window_rules.ExtraRelease | None:
    if not (form.extra_week and form.extra_opens and form.extra_closes):
        errors["extra"] = EXTRA_INCOMPLETE
        return None
    if not weeks.is_valid(form.extra_week):
        errors["extra"] = EXTRA_WEEK_MESSAGE
        return None
    opens = _moment(form.extra_opens)
    closes = _moment(form.extra_closes)
    if opens is None or closes is None:
        errors["extra"] = EXTRA_MOMENT_MESSAGE
        return None
    if opens >= closes:
        errors["extra"] = EXTRA_ORDER
        return None
    return window_rules.ExtraRelease(week=form.extra_week, opens=opens, closes=closes)


def _create_window(
    session: Session, *, user_id: int, project_id: int, rules: window_rules.Window
) -> ScheduleWindow:
    row = ScheduleWindow(project_id=project_id, company_id=rules.company_id)
    session.add(row)
    session.flush()
    _replace_content(session, window_id=row.id, rules=rules)
    _trail(
        session,
        user_id=user_id,
        row=row,
        before=None,
        after=content_of(rules),
    )
    return row


def _replace_content(session: Session, *, window_id: int, rules: window_rules.Window) -> None:
    """Rewrite the weekdays, the released weeks and the extras of the window."""
    for table in (WindowWeekday, WindowWeek, WindowExtraRelease):
        session.execute(delete(table).where(table.window_id == window_id))
    for day in rules.days:
        session.add(
            WindowWeekday(
                window_id=window_id, weekday=day.weekday, opens=day.opens, closes=day.closes
            )
        )
    for week in sorted(rules.weeks, key=weeks.sort_key):
        session.add(WindowWeek(window_id=window_id, week=week))
    for extra in rules.extras:
        session.add(
            WindowExtraRelease(
                window_id=window_id, week=extra.week, opens=extra.opens, closes=extra.closes
            )
        )
    session.flush()


def _trail(
    session: Session,
    *,
    user_id: int,
    row: ScheduleWindow,
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> None:
    audit.append(
        session,
        audit.TrailLine(
            user_id=user_id,
            entity=row.__tablename__,
            record_id=row.id,
            action=audit.UPDATED if before else audit.CREATED,
            before=before,
            after=after,
            project_id=row.project_id,
        ),
    )
