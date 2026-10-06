"""What the facade hands to the screen: the activity as read, and the row of the matrix (D10).

``ActivityView`` is the read model of one activity: the row of the table with the names
of its registers resolved, the figures computed and what the user may do with it.
``MatrixRow`` is that view worded for the matrix: the same columns as the app (item,
atividade, execução, grade dos sete dias, situação, semana, PPC, ações).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.modulos.programacao_semanal import calculations, flow, presentation
from src.modulos.programacao_semanal.calculations import ActivityFigures
from src.modulos.programacao_semanal.presentation import DayCell, MenuItem

NO_NAME = presentation.DASH


@dataclass(frozen=True)
class ActivityView:
    """One activity of the week, with its registers named, its figures and what the user may do."""

    id: int
    version: int
    project_id: int
    project_label: str
    week: str
    unique_id: str
    item: int
    description: str
    location_id: int | None
    location: str
    company_id: int
    company: str
    foreman_id: int | None
    foreman: str
    inspector_id: int | None
    inspector: str
    unit_id: int | None
    unit: str
    planned_headline: float
    figures: ActivityFigures
    situation: str
    approval: str
    notes: str
    comments: str
    can_edit: bool = False
    can_delete: bool = False
    actions: flow.Actions = flow.NO_ACTIONS


@dataclass(frozen=True)
class MatrixRow:
    """A row of the matrix as the template prints it: every text already decided."""

    id: int
    version: int
    item_text: str
    description: str
    unique_id: str
    project_label: str
    location: str
    headline_text: str
    unit: str
    company: str
    foreman: str
    inspector: str
    days: list[DayCell]
    situation_label: str
    situation_tone: str
    approval_label: str
    approval_tone: str
    done_text: str
    planned_text: str
    ppc_text: str
    band: str
    ppc_width: float
    row_class: str
    can_edit: bool
    can_delete: bool
    button: MenuItem
    menu: list[MenuItem]


def build_row(view: ActivityView, dates: list[date]) -> MatrixRow:
    """The matrix row of an activity; ``dates`` are the seven dates of its week."""
    figures = view.figures
    return MatrixRow(
        id=view.id,
        version=view.version,
        item_text=f"{view.item:02d}",
        description=view.description,
        unique_id=view.unique_id,
        project_label=view.project_label,
        location=view.location,
        headline_text=presentation.format_quantity(view.planned_headline, view.unit),
        unit=view.unit,
        company=view.company,
        foreman=view.foreman or NO_NAME,
        inspector=view.inspector or NO_NAME,
        days=presentation.day_cells(figures, view.unit, dates),
        situation_label=presentation.SITUATION_SHORT_LABELS.get(view.situation, view.situation),
        situation_tone=presentation.SITUATION_TONES.get(view.situation, "neutral"),
        approval_label=_approval_label(view),
        approval_tone=_approval_tone(view),
        done_text=presentation.format_quantity(figures.done_total, view.unit),
        planned_text=presentation.format_quantity(figures.planned_total, view.unit),
        ppc_text=presentation.format_percent(figures.ppc, 0),
        band=figures.band,
        ppc_width=min(figures.ppc, 100.0),
        row_class=_row_class(figures),
        can_edit=view.can_edit,
        can_delete=view.can_delete,
        button=presentation.menu_item(view.actions.next_action),
        menu=[presentation.menu_item(key) for key in view.actions.menu],
    )


def _approval_label(view: ActivityView) -> str:
    if view.approval == calculations.APPROVAL_APPROVED:
        return "Aprovado"
    return "Aguarda fiscal" if view.figures.has_done else "Sem realizado"


def _approval_tone(view: ActivityView) -> str:
    if view.approval == calculations.APPROVAL_APPROVED:
        return "ok"
    return "warn" if view.figures.has_done else "neutral"


def _row_class(figures: ActivityFigures) -> str:
    """The row is marked when it has done work and the band is not the high one."""
    if not figures.has_done:
        return ""
    if figures.band == calculations.BAND_LOW:
        return "is-critica"
    return "is-atencao" if figures.band == calculations.BAND_MEDIUM else ""
