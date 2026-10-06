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
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from src.core import rbac
from src.modulos.configuracoes import registers
from src.modulos.configuracoes.registers import Option
from src.modulos.programacao_semanal import (
    calculations,
    permissions,
    presentation,
    service,
    weeks,
)
from src.modulos.programacao_semanal.service import Caller, Filters, FormOptions
from src.modulos.programacao_semanal.validation import ActivityForm
from src.modulos.programacao_semanal.views import build_row

BASE_URL = "/api/programacao-semanal"
MATRIX_URL = f"{BASE_URL}/programacoes"
FILTERS_URL = f"{MATRIX_URL}/filtros"
BANNER_URL = f"{MATRIX_URL}/janela"
FORM_URL = f"{BASE_URL}/atividades/formulario"
SAVE_URL = f"{BASE_URL}/atividades"
DELETE_URL = f"{BASE_URL}/atividades/excluir"

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
