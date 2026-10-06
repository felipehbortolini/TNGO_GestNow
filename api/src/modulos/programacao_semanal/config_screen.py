"""What the configuration screen prints: parameters, window cards and the week pills (D10, ISSUE-054).

The route calls ``context`` and hands the result to ``configuracao.html``. Everything the
template shows is decided here, in Python. The keys are Portuguese, like the interface.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.core import calendario
from src.modulos.programacao_semanal import configuration, weeks
from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.configuration import CompanyWindow, ProjectConfiguration
from src.modulos.programacao_semanal.service import Caller

BASE_URL = "/api/programacao-semanal/configuracoes"
PARAMETERS_URL = f"{BASE_URL}/parametros"
WINDOW_URL = f"{BASE_URL}/janelas"
YEARS_IN_SELECTOR = 3
MONTHS_IN_QUARTER = 3
READ_ONLY_MESSAGE = "Somente o planejador do projeto ou o administrador altera esta configuração."
PORTFOLIO_MESSAGE = (
    "No Portfólio a configuração é só de leitura: escolha um projeto para ver e ajustar a dele."
)


def context(session: Session, *, caller: Caller) -> dict[str, Any]:
    """The context of the screen: the read-only overview in the Portfólio, the project otherwise."""
    if caller.scope.is_portfolio:
        return _portfolio_context(session)
    project = configuration.project_configuration(session, caller=caller)
    return _project_context(project, caller=caller)


def _portfolio_context(session: Session) -> dict[str, Any]:
    rows = configuration.portfolio_overview(session)
    return {
        "portfolio": True,
        "aviso": PORTFOLIO_MESSAGE,
        "linhas": [
            {
                "projeto": row.project,
                "meta_aderencia": _number(row.parameters.adherence_target),
                "meta_ppc": _number(row.parameters.ppc_target),
                "exige_justificativa": row.parameters.requires_deviation_note,
                "limite_desvio": _number(row.parameters.deviation_limit),
                "janelas": row.windows,
            }
            for row in rows
        ],
    }


def _project_context(project: ProjectConfiguration, *, caller: Caller) -> dict[str, Any]:
    today = calendario.in_product_timezone(caller.now).date()
    parameters = project.parameters
    return {
        "portfolio": False,
        "projeto": project.project,
        "pode_editar": project.can_edit,
        "aviso": "" if project.can_edit else READ_ONLY_MESSAGE,
        "parametros_url": PARAMETERS_URL,
        "janela_url": WINDOW_URL,
        "parametros": {
            "meta_aderencia": _number(parameters.adherence_target),
            "meta_ppc": _number(parameters.ppc_target),
            "semana_referencia": parameters.reference_week,
            "exige_justificativa": parameters.requires_deviation_note,
            "limite_desvio": _number(parameters.deviation_limit),
            "versao": project.version if project.version is not None else "",
        },
        "semana_atual": weeks.of_date(today),
        "anos": _years(today.year, current_week=weeks.of_date(today)),
        "janelas": [_card(item, caller=caller) for item in project.windows],
    }


def _card(item: CompanyWindow, *, caller: Caller) -> dict[str, Any]:
    window = item.window
    decision = configuration.current_week_status(window, caller=caller)
    chosen = {day.weekday: day for day in (window.days if window else ())}
    return {
        "empresa_id": item.company_id,
        "empresa": item.company,
        "versao": item.version if item.version is not None else "",
        "aberta": decision.is_open,
        "motivo": decision.reason,
        "semanas": sorted(window.weeks if window else (), key=weeks.sort_key),
        "quantidade_semanas": len(window.weeks) if window else 0,
        "dias": [_day_row(weekday, chosen.get(weekday)) for weekday in window_rules.WEEKDAY_NAMES],
        "extras": [_extra_row(extra) for extra in (window.extras if window else ())],
    }


def _day_row(weekday: int, day: window_rules.WindowDay | None) -> dict[str, Any]:
    opens = day.opens if day else configuration.DEFAULT_OPENS
    closes = day.closes if day else configuration.DEFAULT_CLOSES
    return {
        "n": weekday,
        "nome": window_rules.WEEKDAY_NAMES[weekday],
        "marcado": day is not None,
        "abre": window_rules.hours_text(opens),
        "fecha": window_rules.hours_text(closes),
    }


def _extra_row(extra: window_rules.ExtraRelease) -> dict[str, str]:
    return {
        "semana": extra.week,
        "abre": _moment_text(extra.opens),
        "fecha": _moment_text(extra.closes),
    }


def _moment_text(moment: Any) -> str:
    return calendario.in_product_timezone(moment).strftime("%d/%m/%Y %H:%M")


def _years(first_year: int, *, current_week: str) -> list[dict[str, Any]]:
    """Every ISO week of the next years, as pills with their quarter, for the shortcuts."""
    current_key = weeks.sort_key(current_week)
    years = []
    for year in range(first_year, first_year + YEARS_IN_SELECTOR):
        pills = []
        for number in range(1, weeks.weeks_in_year(year) + 1):
            week = weeks.reference(year, number)
            start = weeks.start(week)
            quarter = ((start.month - 1) // MONTHS_IN_QUARTER) + 1 if start else 1
            pills.append(
                {
                    "id": week,
                    "numero": f"{number:02d}",
                    "trimestre": quarter,
                    "passada": weeks.sort_key(week) < current_key,
                    "periodo": weeks.period_label(week),
                }
            )
        years.append({"ano": year, "semanas": pills})
    return years


def _number(value: float) -> str:
    """A percentage as the field shows it: ``60`` and ``12,5``."""
    return f"{value:g}".replace(".", ",")
