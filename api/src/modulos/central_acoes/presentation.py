"""What the screen Ações and its exports print around the data: chips, summaries and addresses.

The filters live in the query string of the route (``status``, ``origem``, ``responsavel``,
``busca``, ``visao`` and ``pagina``), so a KPI, a chip, the switch between list and kanban and a
page are all plain links that change one thing and keep the rest. The two exports take the same
query, so what is printed or downloaded is exactly what is on the screen.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from urllib.parse import urlencode

from src.modulos.central_acoes import calculations
from src.modulos.central_acoes.calculations import StatusFilter
from src.modulos.central_acoes.service import ResponsibleOption
from src.modulos.central_acoes.validation import KANBAN_VIEW, LIST_VIEW, ActionFilters

ROUTE = "/api/central-acoes/acoes"


class FilterField(StrEnum):
    """The filters a chip can remove; the value is the query parameter it clears."""

    STATUS = "status"
    ORIGIN = "origem"
    RESPONSIBLE = "responsavel"
    SEARCH = "busca"


@dataclass(frozen=True)
class Chip:
    """An active filter as the screen shows it: the text and the address that removes it."""

    field: FilterField
    text: str
    removable: bool


def query_string(filters: ActionFilters, view: str = LIST_VIEW) -> str:
    """The query of the screen for the filters and the view; what is default is left out."""
    parameters: dict[str, str] = {}
    if filters.status is not StatusFilter.OPEN:
        parameters[FilterField.STATUS] = filters.status.value
    if filters.origin:
        parameters[FilterField.ORIGIN] = filters.origin
    if filters.responsible_id is not None:
        parameters[FilterField.RESPONSIBLE] = str(filters.responsible_id)
    if filters.search:
        parameters[FilterField.SEARCH] = filters.search
    if view == KANBAN_VIEW:
        parameters["visao"] = KANBAN_VIEW
    if filters.page > 1:
        parameters["pagina"] = str(filters.page)
    return urlencode(parameters)


def address(filters: ActionFilters, view: str = LIST_VIEW, *, path: str = ROUTE) -> str:
    """The address of ``path`` carrying the filters and the view."""
    query = query_string(filters, view)
    return f"{path}?{query}" if query else path


def with_status(filters: ActionFilters, status: StatusFilter) -> ActionFilters:
    """The filters with another status and back on the first page (a KPI link)."""
    return replace(filters, status=status, page=1)


def with_page(filters: ActionFilters, page: int) -> ActionFilters:
    """The filters on another page (the previous and next links)."""
    return replace(filters, page=page)


def without(filters: ActionFilters, field: FilterField) -> ActionFilters:
    """The filters with one of them cleared (a chip link); the status goes back to Em andamento."""
    if field is FilterField.STATUS:
        return replace(filters, status=StatusFilter.OPEN, page=1)
    if field is FilterField.ORIGIN:
        return replace(filters, origin="", page=1)
    if field is FilterField.RESPONSIBLE:
        return replace(filters, responsible_id=None, page=1)
    return replace(filters, search="", page=1)


def cleared() -> ActionFilters:
    """No filter at all: the default view of the screen."""
    return ActionFilters()


def active_chips(filters: ActionFilters, responsibles: Sequence[ResponsibleOption]) -> list[Chip]:
    """The chips of the active filters; the status is always there, fixed while it is the default."""
    status_text = calculations.STATUS_FILTER_LABELS[filters.status]
    chips = [
        Chip(
            FilterField.STATUS,
            f"Status: {status_text}",
            removable=filters.status is not StatusFilter.OPEN,
        )
    ]
    if filters.origin:
        chips.append(Chip(FilterField.ORIGIN, f"Origem: {filters.origin}", removable=True))
    if filters.responsible_id is not None:
        name = next((item.name for item in responsibles if item.id == filters.responsible_id), "")
        chips.append(
            Chip(
                FilterField.RESPONSIBLE,
                f"Responsável: {name or filters.responsible_id}",
                removable=True,
            )
        )
    if filters.search:
        chips.append(Chip(FilterField.SEARCH, f"Busca: {filters.search}", removable=True))
    return chips


def has_extra_filters(filters: ActionFilters) -> bool:
    """Whether anything beyond the default filter is on: it decides the ``Limpar filtros`` link."""
    return bool(
        filters.origin
        or filters.search
        or filters.responsible_id is not None
        or filters.status is not StatusFilter.OPEN
    )


def summary(filters: ActionFilters, responsibles: Sequence[ResponsibleOption]) -> str:
    """The active filters in one line, as the exports print them."""
    return " · ".join(chip.text for chip in active_chips(filters, responsibles))
