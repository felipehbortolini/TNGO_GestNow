"""What the register and its exports print around the data: chips, summaries and addresses.

The filters live in the query string (``situacao``, ``natureza``, ``severidade``, ``categoria``,
``estrategia``, ``dono``, ``revisao``, ``de``, ``ate``, ``encerrados``, ``excluidos``, ``p``,
``i``, ``aval``, ``busca`` and ``pagina``), so a KPI, a chip, the switch Inerente/Residual and a
page are plain links that change one thing and keep the rest. The two exports take the same
query: what is printed or downloaded is exactly what is on the screen.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode

from src.modulos.riscos.calculations import Band
from src.modulos.riscos.validation import (
    INHERENT,
    REVIEW_FILTERS,
    SITUATION_ACTIVE,
    SITUATION_ALL,
    RiskFilters,
)

ROUTE = "/api/riscos/registro"

REVIEW_TEXT = {
    "vencidas": "Vencidas",
    "proximas": "Vencem em {days} dias",
    "sem": "Sem revisão registrada",
}
SITUATION_TEXT = {SITUATION_ACTIVE: "Ativos", SITUATION_ALL: "Todas"}


class FilterField(StrEnum):
    """The filters a chip can remove."""

    SITUATION = "situacao"
    NATURE = "natureza"
    SEVERITY = "severidade"
    CELL = "celula"
    CATEGORY = "categoria"
    STRATEGY = "estrategia"
    OWNER = "dono"
    REVIEW = "revisao"
    PERIOD = "periodo"
    CLOSED = "encerrados"
    DELETED = "excluidos"
    SEARCH = "busca"


@dataclass(frozen=True)
class Chip:
    """An active filter as the screen shows it: the text and whether it can be removed."""

    field: FilterField
    text: str
    removable: bool


def query_parameters(filters: RiskFilters) -> dict[str, str]:
    """The query of the filters; what is default is left out."""
    parameters = {
        "busca": filters.search,
        "natureza": filters.nature,
        "categoria": filters.category,
        "severidade": ",".join(filters.severities),
        "estrategia": filters.strategy,
        "dono": str(filters.owner_id) if filters.owner_id is not None else "",
        "revisao": filters.review,
    }
    parameters = {name: value for name, value in parameters.items() if value}
    if filters.situation != SITUATION_ACTIVE:
        parameters["situacao"] = filters.situation
    parameters.update(_flag_parameters(filters))
    if filters.assessment == INHERENT:
        parameters["aval"] = INHERENT
    if filters.page > 1:
        parameters["pagina"] = str(filters.page)
    return parameters


def _flag_parameters(filters: RiskFilters) -> dict[str, str]:
    parameters: dict[str, str] = {}
    if filters.identified_from:
        parameters["de"] = filters.identified_from.isoformat()
    if filters.identified_until:
        parameters["ate"] = filters.identified_until.isoformat()
    if filters.include_closed:
        parameters["encerrados"] = "1"
    if filters.include_deleted:
        parameters["excluidos"] = "1"
    if filters.probability and filters.impact:
        parameters["p"] = str(filters.probability)
        parameters["i"] = str(filters.impact)
    return parameters


def query_string(filters: RiskFilters) -> str:
    """The query of the screen for the filters."""
    return urlencode(query_parameters(filters))


def address(filters: RiskFilters, *, path: str = ROUTE) -> str:
    """The address of ``path`` carrying the filters."""
    query = query_string(filters)
    return f"{path}?{query}" if query else path


def with_assessment(filters: RiskFilters, assessment: str) -> RiskFilters:
    """The filters showing the other assessment (the switch Inerente/Residual)."""
    return replace(filters, assessment=assessment, page=1)


def with_page(filters: RiskFilters, page: int) -> RiskFilters:
    """The filters on another page (the previous and next links)."""
    return replace(filters, page=page)


def with_severity(filters: RiskFilters, band_id: str) -> RiskFilters:
    """A KPI of severity: only that band; the same click again goes back to all of them."""
    already = filters.severities == (band_id,)
    return replace(filters, severities=() if already else (band_id,), page=1)


def with_situation(filters: RiskFilters, situation: str) -> RiskFilters:
    """The KPI Em tratamento: that situation; the same click again goes back to the active ones."""
    chosen = SITUATION_ACTIVE if filters.situation == situation else situation
    return replace(filters, situation=chosen, page=1)


def with_review(filters: RiskFilters, review: str) -> RiskFilters:
    """The KPI Revisão vencida: that filter; the same click again clears it."""
    return replace(filters, review="" if filters.review == review else review, page=1)


def cleared(filters: RiskFilters) -> RiskFilters:
    """No filter at all, keeping only the assessment the person is looking at."""
    return RiskFilters(assessment=filters.assessment)


def without(filters: RiskFilters, field: FilterField) -> RiskFilters:
    """The filters with one of them cleared (a chip link)."""
    cleared_values: Mapping[FilterField, dict[str, Any]] = {
        FilterField.SITUATION: {"situation": SITUATION_ACTIVE},
        FilterField.NATURE: {"nature": ""},
        FilterField.SEVERITY: {"severities": ()},
        FilterField.CELL: {"probability": None, "impact": None},
        FilterField.CATEGORY: {"category": ""},
        FilterField.STRATEGY: {"strategy": ""},
        FilterField.OWNER: {"owner_id": None},
        FilterField.REVIEW: {"review": ""},
        FilterField.PERIOD: {"identified_from": None, "identified_until": None},
        FilterField.CLOSED: {"include_closed": False},
        FilterField.DELETED: {"include_deleted": False},
        FilterField.SEARCH: {"search": ""},
    }
    return replace(filters, page=1, **cleared_values[field])


def is_default(filters: RiskFilters) -> bool:
    """Whether nothing beyond the default view is on (the search does not count, as in the prototype)."""
    return replace(filters, search="", page=1) == RiskFilters(assessment=filters.assessment)


def active_chips(
    filters: RiskFilters,
    *,
    bands: Sequence[Band],
    owners: Mapping[int, str],
    review_alert_days: int,
) -> list[Chip]:
    """The chips of the active filters; Situação, Natureza and Severidade are always there."""
    chips = [
        Chip(
            FilterField.SITUATION,
            f"Situação: {SITUATION_TEXT.get(filters.situation, filters.situation)}",
            removable=filters.situation != SITUATION_ACTIVE,
        ),
        Chip(
            FilterField.NATURE,
            f"Natureza: {filters.nature or 'Todas'}",
            removable=bool(filters.nature),
        ),
    ]
    names = [band.name for band in bands if band.id in filters.severities]
    chips.append(
        Chip(
            FilterField.SEVERITY,
            f"Severidade: {', '.join(names) if names else 'Todas'}",
            removable=bool(names),
        )
    )
    chips.extend(_optional_chips(filters, owners, review_alert_days))
    return chips


def _optional_chips(
    filters: RiskFilters, owners: Mapping[int, str], review_alert_days: int
) -> list[Chip]:
    chips: list[Chip] = []
    if filters.probability and filters.impact:
        text = f"Célula: P{filters.probability} x I{filters.impact} ({filters.assessment})"
        chips.append(Chip(FilterField.CELL, text, removable=True))
    labelled = (
        (FilterField.CATEGORY, "Categoria", filters.category),
        (FilterField.STRATEGY, "Estratégia", filters.strategy),
        (
            FilterField.OWNER,
            "Dono",
            owners.get(filters.owner_id, str(filters.owner_id)) if filters.owner_id else "",
        ),
        (
            FilterField.REVIEW,
            "Revisão",
            REVIEW_TEXT[filters.review].format(days=review_alert_days)
            if filters.review in REVIEW_FILTERS
            else "",
        ),
    )
    chips.extend(
        Chip(field, f"{label}: {value}", removable=True)
        for field, label, value in labelled
        if value
    )
    if filters.identified_from or filters.identified_until:
        start = (
            filters.identified_from.strftime("%d/%m/%Y") if filters.identified_from else "início"
        )
        end = filters.identified_until.strftime("%d/%m/%Y") if filters.identified_until else "hoje"
        chips.append(Chip(FilterField.PERIOD, f"Identificado: {start} a {end}", removable=True))
    if filters.include_closed:
        chips.append(Chip(FilterField.CLOSED, "Inclui encerrados", removable=True))
    if filters.include_deleted:
        chips.append(Chip(FilterField.DELETED, "Inclui excluídos", removable=True))
    if filters.search:
        chips.append(Chip(FilterField.SEARCH, f"Busca: {filters.search}", removable=True))
    return chips


def summary(
    filters: RiskFilters,
    *,
    bands: Sequence[Band],
    owners: Mapping[int, str],
    review_alert_days: int,
) -> str:
    """The active filters in one line, as the exports print them."""
    chips = active_chips(filters, bands=bands, owners=owners, review_alert_days=review_alert_days)
    return " · ".join(chip.text for chip in chips)
