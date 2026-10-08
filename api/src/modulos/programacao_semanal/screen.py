"""What the screen of the matrix prints around the rows: addresses, headers, chips and forms (D10).

The routes call these builders and hand the result to the Jinja fragments. Everything
the template shows is decided here, in Python: the address of each sort header, the
chips of the filters that are on, the strip of indicators, the day labels of the form.
The keys of the contexts are Portuguese, like the rest of the interface.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from src.core import attachments, calendario, rbac
from src.core.export_document import ValueKind, format_value
from src.core.spreadsheet_reader import MAX_DATA_ROWS, MAX_FILE_BYTES, MEGABYTE
from src.modulos.configuracoes import registers
from src.modulos.configuracoes.registers import Option
from src.modulos.programacao_semanal import (
    calculations,
    permissions,
    presentation,
    service,
    weeks,
)
from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.service import Caller, Filters, FlowScreen, FormOptions
from src.modulos.programacao_semanal.validation import (
    ActivityForm,
    ApprovalForm,
    DoneForm,
    ScheduleSettingsForm,
    ValidationForm,
    WindowForm,
)
from src.modulos.programacao_semanal.views import (
    ActivityView,
    ChangeRequestView,
    GovernanceLine,
    GovernancePanel,
    build_row,
)

BASE_URL = "/api/programacao-semanal"
MATRIX_URL = f"{BASE_URL}/programacoes"
FILTERS_URL = f"{MATRIX_URL}/filtros"
BANNER_URL = f"{MATRIX_URL}/janela"
FORM_URL = f"{BASE_URL}/atividades/formulario"
SAVE_URL = f"{BASE_URL}/atividades"
DELETE_URL = f"{BASE_URL}/atividades/excluir"
DETAIL_URL = f"{BASE_URL}/atividades/detalhe"
VALIDATE_FORM_URL = f"{BASE_URL}/validacoes/formulario"
VALIDATE_URL = f"{BASE_URL}/validacoes"
REPORT_FORM_URL = f"{BASE_URL}/realizados/formulario"
REPORT_URL = f"{BASE_URL}/realizados"
APPROVE_FORM_URL = f"{BASE_URL}/aprovacoes/formulario"
APPROVE_URL = f"{BASE_URL}/aprovacoes"
REOPEN_URL = f"{BASE_URL}/reaberturas"
PUBLISH_URL = f"{BASE_URL}/publicacoes"
PUBLISH_WEEK_URL = f"{BASE_URL}/publicacoes/semana"
GOVERNANCE_URL = f"{BASE_URL}/governanca"
GOVERNANCE_TRAIL_URL = f"{GOVERNANCE_URL}/trilha"
GOVERNANCE_EXCEL_URL = f"{GOVERNANCE_URL}/excel"
GOVERNANCE_PRINTABLE_URL = f"{GOVERNANCE_URL}/imprimivel"
QUEUE_URL = f"{BASE_URL}/pedidos"
REQUEST_FORM_URL = f"{QUEUE_URL}/formulario"
CONFIGURATION_URL = f"{BASE_URL}/configuracao"
SETTINGS_SAVE_URL = f"{CONFIGURATION_URL}/parametros"
WINDOW_SAVE_URL = f"{CONFIGURATION_URL}/janela"
IMPORT_URL = f"{BASE_URL}/importacao"
IMPORT_MODEL_URL = f"{IMPORT_URL}/modelo"
IMPORT_CHECK_URL = f"{IMPORT_URL}/conferir"
WEEK_EXCEL_URL = f"{BASE_URL}/semana/excel"
WEEK_PRINTABLE_URL = f"{BASE_URL}/semana/imprimivel"

# The app's week selector: the current year and the next two, one pill per ISO week.
SELECTOR_YEARS = 3
SELECTOR_QUARTERS = (1, 2, 3, 4)

# Where the button of the next action of each step opens its panel.
ACTION_URLS = {
    permissions.ACTION_VALIDATE: VALIDATE_FORM_URL,
    permissions.ACTION_APPROVE: APPROVE_FORM_URL,
    permissions.ACTION_REPORT: REPORT_FORM_URL,
    permissions.ACTION_VIEW: DETAIL_URL,
}

# (sort field, header text): the columns of the matrix that sort.
SORT_COLUMNS = (
    ("item", "#"),
    ("atividade", "Atividade"),
    ("empresa", "Execução"),
    ("situacao", "Situação"),
    ("realizado", "Semana"),
    ("ppc", "PPC"),
)

SITUATION_CHIPS = {
    calculations.SITUATION_DRAFT: "Em elaboração",
    calculations.SITUATION_VALIDATED: "Validada",
    calculations.SITUATION_PUBLISHED: "Publicada",
}
APPROVAL_CHIPS = {
    calculations.APPROVAL_PENDING: "Aguardando o fiscal",
    calculations.APPROVAL_APPROVED: "Realizado aprovado",
}
TONE_OF_BAND = {
    calculations.BAND_HIGH: "ok",
    calculations.BAND_MEDIUM: "warn",
    calculations.BAND_LOW: "erro",
}
NO_LABEL = presentation.DASH


@dataclass(frozen=True)
class SortHeader:
    """A column header that sorts: its text, where it goes and what it shows now."""

    label: str
    url: str
    active: bool
    arrow: str


@dataclass(frozen=True)
class Chip:
    """A filter that is on, worded, with the address that turns it off."""

    label: str
    url: str


def query(
    week: str,
    filters: Filters,
    *,
    sort: str | None = None,
    direction: str = "asc",
    drop: str = "",
) -> str:
    """The query string of the matrix for a week and its filters.

    ``drop`` leaves one filter out (a chip removes itself that way); ``sort`` replaces the
    current order; without it the order of the filters is kept.
    """
    pairs: list[tuple[str, str]] = [("semana", week)]
    fields = (
        ("local", filters.location_id),
        ("empresa", filters.company_id),
        ("encarregado", filters.foreman_id),
        ("responsavel", filters.inspector_id),
        ("situacao", filters.situation),
        ("aprovacao", filters.approval),
        ("ppc", filters.band),
        ("busca", filters.search),
    )
    pairs += [(name, str(value)) for name, value in fields if value and name != drop]
    chosen = sort if sort is not None else filters.sort
    if chosen:
        pairs += [
            ("ordena", chosen),
            ("ordem", direction if sort is not None else filters.direction),
        ]
    return urlencode(pairs)


def sort_headers(week: str, filters: Filters) -> dict[str, SortHeader]:
    """The sortable headers: clicking the active one flips the direction."""
    headers = {}
    for field, label in SORT_COLUMNS:
        active = filters.sort == field
        next_direction = "desc" if active and filters.direction != "desc" else "asc"
        arrow = "⇅" if not active else ("↓" if filters.direction == "desc" else "↑")
        headers[field] = SortHeader(
            label=label,
            url=f"{MATRIX_URL}?{query(week, filters, sort=field, direction=next_direction)}",
            active=active,
            arrow=arrow,
        )
    return headers


def chips(week: str, filters: Filters, options: FormOptions) -> list[Chip]:
    """One chip per filter that is on, each with the address that removes it."""
    wanted = (
        ("busca", bool(filters.search), f"Procurando por “{filters.search}”"),
        (
            "local",
            filters.location_id is not None,
            f"Frente: {_label(options.locations, filters.location_id)}",
        ),
        (
            "empresa",
            filters.company_id is not None,
            f"Contratada: {_label(options.companies, filters.company_id)}",
        ),
        (
            "encarregado",
            filters.foreman_id is not None,
            f"Encarregado: {_label(options.foremen, filters.foreman_id)}",
        ),
        (
            "responsavel",
            filters.inspector_id is not None,
            f"Fiscal: {_label(options.inspectors, filters.inspector_id)}",
        ),
        ("situacao", bool(filters.situation), SITUATION_CHIPS.get(filters.situation, "")),
        ("aprovacao", bool(filters.approval), APPROVAL_CHIPS.get(filters.approval, "")),
        ("ppc", bool(filters.band), _band_chip(filters.band)),
    )
    return [
        Chip(label=label, url=f"{MATRIX_URL}?{query(week, filters, drop=name)}")
        for name, active, label in wanted
        if active
    ]


def _band_chip(band: str) -> str:
    high, medium = calculations.HIGH_BAND, calculations.MEDIUM_BAND
    return {
        calculations.BAND_HIGH: f"PPC alto — {high:g}% ou mais",
        calculations.BAND_MEDIUM: f"PPC médio — {medium:g} a {high - 1:g}%",
        calculations.BAND_LOW: f"PPC baixo — abaixo de {medium:g}%",
    }.get(band, "")


def _label(options: list[Option], chosen: int | None) -> str:
    return next((option.label for option in options if option.id == chosen), NO_LABEL)


# ── The matrix and its strip ─────────────────────────────────────────────


def matrix_context(
    session: Session, *, caller: Caller, params: Mapping[str, str | None]
) -> dict[str, Any]:
    """The strip of indicators and the matrix of a week, for ``prog-resumo`` and ``prog-tabela``."""
    week = service.resolve_week(session, caller=caller, raw=params.get("semana"))
    filters = service.parse_filters(params)
    every_activity = service.list_activities(session, caller=caller, week=week)
    shown = service.apply_filters(every_activity, filters)
    summary = service.week_summary(every_activity)
    status = service.window_status(session, caller=caller, week=week)
    options = _options(session, caller)
    dates = weeks.week_dates(week)
    parameters = service.parameters_of(session, caller.scope.project_id)
    band = calculations.performance_band(summary.adherence)
    return {
        "semana": week,
        "periodo": weeks.period_label(week),
        "linhas": [build_row(view, dates) for view in shown],
        "cabecalhos": sort_headers(week, filters),
        "dias_rotulos": _day_headers(dates),
        "pastilhas": chips(week, filters, options),
        "filtrando": filters.active_count > 0,
        "total_na_semana": len(every_activity),
        "limpar_url": f"{MATRIX_URL}?{query(week, Filters())}",
        "janela": status,
        "somente_leitura": caller.scope.is_portfolio,
        "form_url": FORM_URL,
        "excluir_url": DELETE_URL,
        "acao_urls": ACTION_URLS,
        "publicar_url": PUBLISH_URL,
        "pedir_url": REQUEST_FORM_URL,
        "resumo": {
            "total": summary.total,
            "aderencia": presentation.format_percent(summary.adherence, 0),
            "aderencia_tom": TONE_OF_BAND[band],
            "ppc_medio": presentation.format_percent(summary.mean_ppc, 0),
            "aguardando": summary.awaiting_inspector,
            "baixa": summary.low_band,
            "meta_aderencia": presentation.format_percent(parameters.adherence_target, 0),
            "limite_baixa": f"{calculations.MEDIUM_BAND:g}",
            "todas_url": f"{MATRIX_URL}?{query(week, Filters())}",
            "aguardando_url": (
                f"{MATRIX_URL}?{query(week, Filters(approval=calculations.APPROVAL_PENDING))}"
            ),
            "baixa_url": f"{MATRIX_URL}?{query(week, Filters(band=calculations.BAND_LOW))}",
        },
    }


def filters_context(
    session: Session, *, caller: Caller, params: Mapping[str, str | None]
) -> dict[str, Any]:
    """The toolbar: the week selector, the search and the refinement panel."""
    week = service.resolve_week(session, caller=caller, raw=params.get("semana"))
    filters = service.parse_filters(params)
    status = service.window_status(session, caller=caller, week=week)
    project_id = caller.scope.project_id
    return {
        "semana": week,
        "semanas": service.horizon_weeks(session, caller=caller),
        "filtros": filters,
        "opcoes": _options(session, caller),
        "janela": status,
        "matriz_url": MATRIX_URL,
        "filtros_url": FILTERS_URL,
        "form_url": FORM_URL,
        "fornecedor": status.is_supplier,
        "no_portfolio": caller.scope.is_portfolio,
        "pode_publicar": project_id is not None
        and permissions.can_publish(caller.user, project_id),
        "publicar_semana_url": PUBLISH_WEEK_URL,
        "situacoes": SITUATION_CHIPS,
        "aprovacoes": APPROVAL_CHIPS,
        "faixas": {
            calculations.BAND_HIGH: f"Alta — {calculations.HIGH_BAND:g}% ou mais",
            calculations.BAND_MEDIUM: (
                f"Média — {calculations.MEDIUM_BAND:g} a {calculations.HIGH_BAND - 1:g}%"
            ),
            calculations.BAND_LOW: f"Baixa — abaixo de {calculations.MEDIUM_BAND:g}%",
        },
    }


def banner_context(
    session: Session, *, caller: Caller, params: Mapping[str, str | None]
) -> dict[str, Any]:
    """The banner of the window: who it binds, whether it is open and why."""
    week = service.resolve_week(session, caller=caller, raw=params.get("semana"))
    return {
        "semana": week,
        "periodo": weeks.period_label(week),
        "janela": service.window_status(session, caller=caller, week=week),
    }


# ── The panels of the flow ───────────────────────────────────────────────


def _version(view: ActivityView, version: str | None) -> int | str:
    """The version the panel carries: the one the screen opened, or the record's own."""
    return version if version is not None else view.version


def validation_context(
    *,
    opened: FlowScreen,
    typed: ValidationForm | None = None,
    errors: Mapping[str, str] | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """The panel of validation: the inspector to name and the comments to the supplier."""
    view = opened.view
    return {
        "atividade": view,
        "semana": view.week,
        "periodo": weeks.period_label(view.week),
        "versao": _version(view, version),
        "valores": typed or ValidationForm(inspector_id=view.inspector_id),
        "fiscais": opened.options.inspectors,
        "erros": dict(errors or {}),
        "unidade": view.unit,
        "previsto_texto": presentation.format_quantity(view.figures.planned_total, view.unit),
        "salvar_url": VALIDATE_URL,
    }


def report_context(
    *,
    opened: FlowScreen,
    typed: DoneForm | None = None,
    errors: Mapping[str, str] | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """The panel of the done work: both shifts, the plan of each day and the shortcuts."""
    view = opened.view
    figures = view.figures
    form = typed or DoneForm(
        day_shift=figures.day_shift, night_shift=figures.night_shift, notes=view.notes
    )
    dates = weeks.week_dates(view.week)
    return {
        "atividade": view,
        "semana": view.week,
        "periodo": weeks.period_label(view.week),
        "versao": _version(view, version),
        "dias": _form_days(view, dates),
        "dias_dia_json": json.dumps([_number_text(value) for value in form.day_shift]),
        "dias_noite_json": json.dumps([_number_text(value) for value in form.night_shift]),
        "dias_previsto_json": json.dumps([_number_text(value) for value in figures.planned_days]),
        "tem_noite": any(figures.night_shift),
        "limite_desvio": opened.parameters.deviation_limit,
        "exige_justificativa": opened.parameters.requires_deviation_note,
        "observacoes": form.notes,
        "erros": dict(errors or {}),
        "unidade": view.unit,
        "previsto_total_texto": presentation.format_quantity(figures.planned_total, view.unit),
        "salvar_url": REPORT_URL,
    }


def approval_context(
    *,
    opened: FlowScreen,
    typed: ApprovalForm | None = None,
    errors: Mapping[str, str] | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """The panel of the inspector: approve the done work, or reopen it with a reason."""
    view = opened.view
    figures = view.figures
    dates = weeks.week_dates(view.week)
    return {
        "atividade": view,
        "semana": view.week,
        "periodo": weeks.period_label(view.week),
        "versao": _version(view, version),
        "dias": presentation.day_cells(figures, view.unit, dates),
        "dias_rotulos": _day_headers(dates),
        "aprovando": view.approval == calculations.APPROVAL_PENDING and figures.has_done,
        "reabrindo": view.approval == calculations.APPROVAL_APPROVED,
        "valores": typed or ApprovalForm(),
        "erros": dict(errors or {}),
        "unidade": view.unit,
        "previsto_texto": presentation.format_quantity(figures.planned_total, view.unit),
        "realizado_texto": presentation.format_quantity(figures.done_total, view.unit),
        "ppc_texto": presentation.format_percent(figures.ppc, 0),
        "observacoes": view.notes,
        "aprovar_url": APPROVE_URL,
        "reabrir_url": REOPEN_URL,
    }


def detail_context(session: Session, *, opened: FlowScreen) -> dict[str, Any]:
    """The read-only panel of an activity: the ficha, the day grid and the history."""
    view = opened.view
    figures = view.figures
    dates = weeks.week_dates(view.week)
    return {
        "atividade": view,
        "semana": view.week,
        "periodo": weeks.period_label(view.week),
        "dias": presentation.day_cells(figures, view.unit, dates),
        "dias_rotulos": _day_headers(dates),
        "eventos": service.detail_events(session, activity_id=view.id),
        "situacao_label": presentation.SITUATION_SHORT_LABELS.get(view.situation, view.situation),
        "aprovacao_label": calculations.APPROVAL_LABELS.get(view.approval, view.approval),
        "unidade": view.unit,
        "previsto_texto": presentation.format_quantity(figures.planned_total, view.unit),
        "realizado_texto": presentation.format_quantity(figures.done_total, view.unit),
        "ppc_texto": presentation.format_percent(figures.ppc, 0),
        "pode_reabrir": view.can_approve and view.approval == calculations.APPROVAL_APPROVED,
        "aprovar_url": APPROVE_FORM_URL,
        "pode_pedir": view.can_request_change,
        "motivo_fechado": _closed_reason(view),
        "pedir_url": REQUEST_FORM_URL,
    }


def _closed_reason(view: ActivityView) -> str:
    """Why the item is closed for editing, where the change request is offered."""
    if view.situation == calculations.SITUATION_PUBLISHED:
        return "A programação foi publicada."
    return "O realizado foi aprovado pelo fiscal."


# ── The screen of the governance (ISSUE-053) ─────────────────────────────


def governance_context(session: Session, *, caller: Caller) -> dict[str, Any]:
    """The governance panel: the indicators, the control list, the windows and the queue."""
    panel = service.governance_panel(session, caller=caller)
    return {
        "linhas": [_governance_line(line) for line in panel.lines],
        "situacao": panel.situations,
        "kpis": _governance_kpis(panel),
        "janelas": panel.windows,
        "semana": panel.reference_week,
        "periodo": panel.reference_period,
        "portfolio": panel.is_portfolio,
        "pode_ver_trilha": panel.can_view_trail,
        "pedidos_url": QUEUE_URL,
        "trilha_url": GOVERNANCE_TRAIL_URL,
        "excel_url": GOVERNANCE_EXCEL_URL,
        "pdf_url": GOVERNANCE_PRINTABLE_URL,
    }


def _governance_line(line: GovernanceLine) -> dict[str, Any]:
    """One line of the control list with the adherence already coloured by its band."""
    return {
        "company": line.company,
        "project_label": line.project_label,
        "week": line.week,
        "period": line.period,
        "total": line.total,
        "draft": line.draft,
        "validated": line.validated,
        "published": line.published,
        "pending": line.pending,
        "inspector": line.inspector or NO_LABEL,
        "adherence_text": presentation.format_percent(line.adherence, 0),
        "adherence_tone": TONE_OF_BAND[calculations.performance_band(line.adherence)],
        "updated_at_text": line.updated_at_text or NO_LABEL,
    }


def _governance_kpis(panel: GovernancePanel) -> list[dict[str, Any]]:
    """The four cards above the panel, with the tone and the icon the app gave them."""
    return [
        {
            "label": "Contratadas ativas",
            "value": panel.active_companies,
            "tone": "neutro",
            "icone": "building",
        },
        {
            "label": "Janelas abertas hoje",
            "value": panel.open_windows,
            "tone": "info",
            "icone": "calendar",
        },
        {
            "label": "Aguardando fiscal",
            "value": panel.situations.pending,
            "tone": "warn",
            "icone": "clock",
        },
        {
            "label": "Atividades no histórico",
            "value": panel.situations.total,
            "tone": "ok",
            "icone": "taskList",
        },
    ]


def queue_context(
    session: Session,
    *,
    caller: Caller,
    erro_id: int | None = None,
    erro_mensagem: str = "",
    resposta_digitada: str = "",
) -> dict[str, Any]:
    """The queue of change requests: what waits for a decision and what was decided."""
    queue = service.request_queue(session, caller=caller)
    return {
        "pendentes": [_request_row(view) for view in queue.pending],
        "resolvidos": [_request_row(view) for view in queue.resolved],
        "total_pendentes": queue.total_pending,
        "pode_decidir": queue.can_decide,
        "portfolio": queue.is_portfolio,
        "pedidos_url": QUEUE_URL,
        "erro_id": erro_id,
        "erro_mensagem": erro_mensagem,
        "resposta_digitada": resposta_digitada,
    }


def _request_row(view: ChangeRequestView) -> dict[str, Any]:
    """One request of the queue, with the situation worded and the tones of the app."""
    return {
        "id": view.id,
        "version": view.version,
        "unique_id": view.unique_id,
        "description": view.description,
        "company": view.company,
        "week": view.week,
        "project_label": view.project_label,
        "reason": view.reason,
        "situation_label": presentation.REQUEST_SITUATION_LABELS.get(
            view.situation, view.situation
        ),
        "situation_tone": presentation.REQUEST_SITUATION_TONES.get(view.situation, "neutral"),
        "requested_by": view.requested_by,
        "requested_at_text": view.requested_at_text,
        "decided_by": view.decided_by,
        "decided_at_text": view.decided_at_text,
        "answer": view.answer,
    }


def trail_context(session: Session, *, caller: Caller) -> dict[str, Any]:
    """The module's audit trail, worded for the screen."""
    return {"eventos": service.governance_trail(session, caller=caller)}


def request_context(
    *,
    view: ActivityView,
    typed: str = "",
    errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The drawer of a change request: the item that is closed and the reason to type."""
    return {
        "atividade": view,
        "semana": view.week,
        "periodo": weeks.period_label(view.week),
        "motivo": typed,
        "erros": dict(errors or {}),
        "unidade": view.unit,
        "previsto_texto": presentation.format_quantity(view.figures.planned_total, view.unit),
        "motivo_fechado": _closed_reason(view),
        "salvar_url": QUEUE_URL,
    }


# ── The import and the outputs of the week (ISSUE-055) ───────────────────


def import_context(
    session: Session, *, caller: Caller, params: Mapping[str, str | None]
) -> dict[str, Any]:
    """The import tab: the week, the registers the sheet accepts and the outputs of the week.

    In the Portfólio the block only asks for a project (D8) and whoever cannot import
    sees why (D7); the Excel and the printable sheet stay available in both cases.
    """
    week = service.resolve_week(session, caller=caller, raw=params.get("semana"))
    project_id = caller.scope.project_id
    options = _options(session, caller)
    return {
        "semana": week,
        "periodo": weeks.period_label(week),
        "semanas": service.horizon_weeks(session, caller=caller),
        "portfolio": caller.scope.is_portfolio,
        "pode_importar": project_id is not None and permissions.can_import(caller.user, project_id),
        "cadastros": {
            "locais": [option.label for option in options.locations],
            "empresas": [option.label for option in options.companies],
            "unidades": [option.label for option in options.units],
            "encarregados": [option.label for option in options.foremen],
            "fiscais": [option.label for option in options.inspectors],
        },
        "limite_mb": MAX_FILE_BYTES // MEGABYTE,
        "limite_linhas": format_value(ValueKind.INTEGER, MAX_DATA_ROWS),
        "campo_arquivo": attachments.FILE_FIELD,
        "painel_url": IMPORT_URL,
        "modelo_url": IMPORT_MODEL_URL,
        "conferir_url": IMPORT_CHECK_URL,
        "excel_url": f"{WEEK_EXCEL_URL}?{urlencode({'semana': week})}",
        "pdf_url": f"{WEEK_PRINTABLE_URL}?{urlencode({'semana': week})}",
    }


# ── The configuration of the schedule (ISSUE-054) ────────────────────────


@dataclass(frozen=True)
class SettingsSubmission:
    """The typed parameters when the save was refused: the form shows them again."""

    errors: Mapping[str, str]
    values: ScheduleSettingsForm
    version: str


@dataclass(frozen=True)
class WindowSubmission:
    """The typed window when the save was refused: the errors, the values and the company."""

    errors: Mapping[str, str]
    values: WindowForm
    company_id: int | None
    version: str


def configuration_context(
    session: Session,
    *,
    caller: Caller,
    settings: SettingsSubmission | None = None,
    windows: WindowSubmission | None = None,
) -> dict[str, Any]:
    """The whole configuration of the project: the parameters and the windows by company.

    In the Portfólio the screen only says to choose a project (D8): the blocks of the
    forms are not built at all. A supplier sees only its own company's window (D7).
    """
    configuration = service.configuration_of(session, caller=caller)
    data: dict[str, Any] = {
        "portfolio": configuration.is_portfolio,
        "pode_editar": configuration.can_edit,
        "projeto_rotulo": configuration.project_label,
        "usa_padroes": configuration.project_id is not None and not configuration.has_row,
        "salvar_parametros_url": SETTINGS_SAVE_URL,
        "salvar_janela_url": WINDOW_SAVE_URL,
    }
    if not configuration.is_portfolio:
        data.update(_settings_block(session, caller, configuration, settings))
        data.update(_windows_block(session, caller, configuration, windows))
    return data


def _settings_block(
    session: Session,
    caller: Caller,
    configuration: service.ScheduleConfiguration,
    submission: SettingsSubmission | None,
) -> dict[str, Any]:
    """The parameters block: the current values (or the typed ones) and the reference weeks."""
    parameters = configuration.parameters
    typed = submission.values if submission is not None else None
    return {
        "parametros": {
            "meta_aderencia": _number_text(
                typed.adherence_target if typed else parameters.adherence_target
            ),
            "meta_ppc": _number_text(typed.ppc_target if typed else parameters.ppc_target),
            "semana_referencia": typed.reference_week if typed else parameters.reference_week,
            "exige_justificativa_desvio": (
                typed.requires_deviation_note if typed else parameters.requires_deviation_note
            ),
            "limite_desvio_justificativa": _number_text(
                typed.deviation_limit if typed else parameters.deviation_limit
            ),
        },
        "referencia_semanas": _reference_weeks(session, caller, parameters.reference_week),
        "versao_parametros": (
            submission.version if submission is not None else (configuration.settings_version or "")
        ),
        "erros_parametros": dict(submission.errors) if submission is not None else {},
    }


def _reference_weeks(session: Session, caller: Caller, reference: str) -> list[weeks.WeekInfo]:
    """The weeks the reference select offers: the horizon of the screen plus a distant reference."""
    options = service.horizon_weeks(session, caller=caller)
    if (
        reference
        and weeks.is_valid(reference)
        and all(option.id != reference for option in options)
    ):
        options.append(weeks.describe(reference))
        options.sort(key=lambda option: weeks.sort_key(option.id))
    return options


def _windows_block(
    session: Session,
    caller: Caller,
    configuration: service.ScheduleConfiguration,
    submission: WindowSubmission | None,
) -> dict[str, Any]:
    """The windows block: one card per company, the day selector and the week pills."""
    week = service.default_week(session, caller=caller)
    today = service.today_of(caller.now)
    return {
        "janelas": [_window_values(window, submission) for window in configuration.windows],
        "dias_semana": [
            {"valor": number, "nome": name} for number, name in window_rules.WEEKDAY_NAMES.items()
        ],
        "anos": _selector_years(week, today),
        "trimestres": SELECTOR_QUARTERS,
        "semana_atual": week,
        "periodo_atual": weeks.period_label(week),
        "erros_janela": dict(submission.errors) if submission is not None else {},
        "editando_janela": submission.company_id if submission is not None else None,
    }


def _window_values(
    window: service.SettingsWindow, submission: WindowSubmission | None
) -> dict[str, Any]:
    """One company's window as its card prints it, with the typed values when refused."""
    typed = (
        submission.values
        if submission is not None and submission.company_id == window.company_id
        else None
    )
    submitted_version = submission.version if submission is not None else ""
    day = window.days[0] if window.days else None
    return {
        "company_id": window.company_id,
        "empresa": window.company,
        "aberta": window.is_open,
        "motivo": window.reason,
        "versao": submitted_version if typed else (window.version or ""),
        "dia": (typed.weekday if typed else (str(day.weekday) if day else "")),
        "abre": (typed.opens if typed else (window_rules.hours_text(day.opens) if day else "")),
        "fecha": (typed.closes if typed else (window_rules.hours_text(day.closes) if day else "")),
        "semanas": list(typed.weeks) if typed else list(window.weeks),
        "quantidade_semanas": len(typed.weeks) if typed else len(window.weeks),
        "extra_semana": typed.extra_week if typed else "",
        "extra_abre": typed.extra_opens if typed else "",
        "extra_fecha": typed.extra_closes if typed else "",
        "extras": [
            {
                "semana": extra.week,
                "abre": _moment_text(extra.opens),
                "fecha": _moment_text(extra.closes),
            }
            for extra in window.extras
        ],
    }


def _selector_years(reference: str, today: date) -> list[dict[str, Any]]:
    """The ISO weeks of the selector, grouped by year, as the pills print them (the app's 3)."""
    start_year, _number = weeks.parts(reference)
    return [
        {
            "ano": year,
            "semanas": [_pill(week, today) for week in _year_weeks(year)],
        }
        for year in range(start_year, start_year + SELECTOR_YEARS)
    ]


def _year_weeks(year: int) -> list[str]:
    return [weeks.reference(year, number) for number in range(1, weeks.weeks_in_year(year) + 1)]


def _pill(week: str, today: date) -> dict[str, Any]:
    """One week of the pill grid: its number, the period of the title and its quarter."""
    info = weeks.describe(week)
    first = info.first_day
    last = info.last_day
    return {
        "id": week,
        "numero": f"{info.number:02d}",
        "periodo": info.period,
        "tri": ((first.month - 1) // 3) + 1 if first else 1,
        "passada": bool(last and last < today),
    }


def _moment_text(moment: datetime) -> str:
    """An instant of an extraordinary release as it prints on the chip."""
    return calendario.in_product_timezone(moment).strftime("%d/%m/%Y %H:%M")


def _form_days(view: ActivityView, dates: list[Any]) -> list[dict[str, Any]]:
    """The seven days of a form: the label, the date and the plan already worded."""
    figures = view.figures
    return [
        {
            "indice": index,
            "rotulo": calculations.DAY_LABELS[index],
            "nome": calculations.DAY_NAMES[index],
            "data": f"{dates[index]:%d/%m}" if dates else "",
            "fim_de_semana": index >= calculations.DAYS - 2,
            "previsto_texto": presentation.format_quantity(figures.planned_days[index], view.unit),
        }
        for index in range(calculations.DAYS)
    ]


def _options(session: Session, caller: Caller) -> FormOptions:
    """The registers of the project in the scope; empty lists in the Portfólio (D8)."""
    project_id = caller.scope.project_id
    if project_id is None:
        return FormOptions(
            locations=[],
            companies=registers.list_companies(session, only=rbac.company_scope(caller.user)),
            units=[],
            foremen=[],
            inspectors=[],
        )
    return service.form_options(session, user=caller.user, project_id=project_id)


def _day_headers(dates: list[Any]) -> list[dict[str, Any]]:
    """The head of the grid of days: ``2ª`` to ``Dom``, with the name and the date in the title."""
    headers = []
    for index in range(calculations.DAYS):
        title = calculations.DAY_NAMES[index]
        if dates:
            title += f" · {dates[index]:%d/%m}"
        headers.append(
            {
                "rotulo": calculations.DAY_LABELS[index],
                "titulo": title,
                "fim_de_semana": index >= calculations.DAYS - 2,
            }
        )
    return headers


# ── The form of an activity ──────────────────────────────────────────────


def form_context(
    *,
    caller: Caller,
    screen: service.FormScreen,
    errors: Mapping[str, str] | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """The drawer of an activity: the values, the registers it offers and the errors."""
    form = screen.form
    week = form.week or screen.week
    dates = weeks.week_dates(week)
    days = [
        {
            "indice": index,
            "rotulo": calculations.DAY_LABELS[index],
            "nome": calculations.DAY_NAMES[index],
            "data": f"{dates[index]:%d/%m}" if dates else "",
            "fim_de_semana": index >= calculations.DAYS - 2,
        }
        for index in range(calculations.DAYS)
    ]
    view = screen.view
    return {
        "nova": view is None,
        "atividade_id": view.id if view else "",
        "versao": version if version is not None else (view.version if view else ""),
        "semana": week,
        "periodo": weeks.period_label(week),
        "item": f"{screen.item:02d}",
        "valores": form,
        "dias": days,
        "dias_json": json.dumps([_number_text(value) for value in form.planned_days]),
        "prevista_texto": _number_text(form.headline),
        "opcoes": screen.options,
        "erros": dict(errors or {}),
        "fornecedor": permissions.is_supplier(caller.user),
        "empresa_do_fornecedor": _supplier_company(screen.options),
        "salvar_url": SAVE_URL,
        "titulo": "Nova atividade" if view is None else f"Editar {view.unique_id}",
    }


def _number_text(value: float) -> float | int:
    """A number for the form: whole when it is whole (``180`` and not ``180.0``)."""
    return int(value) if float(value).is_integer() else value


def _supplier_company(options: FormOptions) -> str:
    """The label of the only company a supplier sees in the form."""
    return options.companies[0].label if len(options.companies) == 1 else ""


def empty_form(week: str, company_id: int | None) -> ActivityForm:
    """The form of a new activity: the week of the screen and, for a supplier, its company."""
    return ActivityForm(week=week, company_id=company_id)
