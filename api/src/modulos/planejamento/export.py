"""Exports for the Planning module.

The 6WLA (ISSUE-045) hands the generic export one ``Document`` built from the
board the screen shows, so what the Excel and the printable version carry is the
same as the screen: the indicators with their reference, the grid of six weeks
and the restrictions. The data of the Gantt and of the Galeria (D11) is built
here too: the server sends the facts, the library draws them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from src.core import calendario
from src.core.export_document import (
    Cell,
    Chart,
    Column,
    Document,
    Kpi,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.planejamento import calculations
from src.modulos.planejamento.service import ActivityView, ConstraintView, LookaheadBoard

DOCUMENT_TITLE = "6WLA: planejamento de 6 semanas"
GRID_TITLE = "Grade de 6 semanas"
CONSTRAINTS_TITLE = "Restrições"
MARK = "X"

_GANTT_LABELS = {
    "colunaEsquerda": "Atividade",
    "concluidas": "Prontas",
    "concluida": "Pronta",
    "criticas": "Restrição vencida",
    "foraDoPrazo": "Com restrição aberta",
    "emExecucao": "Programada",
}
_SITUATION_LABELS = {
    "vencida": ("Restrição vencida", "erro"),
    "com_restricao": ("Com restrição", "alerta"),
    "pronta": ("Pronta", "ok"),
}
_STATUS_TONES = {"Vencida": Tone.ERROR, "Aberta": Tone.WARN, "Removida": Tone.OK}


def week_caption(week: calculations.LookaheadWeekInfo) -> str:
    """``S40 28/09``: the label of a week and its Monday, as the grid header writes it."""
    return f"{week.label} {week.start:%d/%m}"


def horizon_text(board: LookaheadBoard) -> str:
    """``S40 (28/09) a S45 (02/11)``: the horizon the board covers."""
    first, last = board.weeks[0], board.weeks[-1]
    return f"{first.label} ({first.start:%d/%m}) a {last.label} ({last.start:%d/%m})"


def constraints_summary(activity: ActivityView) -> str:
    """``2 abertas, 1 vencidas``: the constraints column of the grid, as the prototype exported it."""
    return f"{activity.open_constraints} abertas, {activity.overdue_constraints} vencidas"


def lookahead_document(
    board: LookaheadBoard,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    constraints_label: str,
) -> Document:
    """The 6WLA as the exports carry it: indicators, the Gantt, the grid and the restrictions."""
    return Document(
        title=DOCUMENT_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=board.reference_date,
        portfolio=scope.is_portfolio,
        context=(("Horizonte", horizon_text(board)), ("Restrições listadas", constraints_label)),
        kpis=_kpis(board),
        charts=(Chart(GRID_TITLE, "gantt", gantt_data(board)),),
        tables=(_grid_table(board), _constraints_table(board)),
    )


def _kpis(board: LookaheadBoard) -> tuple[Kpi, ...]:
    figures = board.figures
    ready_tone = Tone.OK if figures.short_term_ready == figures.short_term_activities else Tone.WARN
    return (
        Kpi(
            "Atividades no horizonte",
            figures.activities,
            f"Referência: {horizon_text(board)}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
        Kpi(
            "Prontas nas 2 próximas semanas",
            figures.short_term_ready,
            f"Meta: {figures.short_term_activities}",
            ValueKind.INTEGER,
            tone=ready_tone,
            status="Sem restrição aberta; podem ir para a programação",
        ),
        Kpi(
            "Restrições abertas",
            figures.open_constraints,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if figures.open_constraints else Tone.OK,
            status=f"de {figures.total_constraints} identificadas",
        ),
        Kpi(
            "Restrições vencidas",
            figures.overdue_constraints,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if figures.overdue_constraints else Tone.OK,
            status="Data necessária já passou",
        ),
        Kpi(
            "Índice de remoção",
            figures.removal_index,
            "Meta: 100%",
            ValueKind.PERCENT,
            digits=0,
            tone=Tone.INFO,
            status="Restrições removidas ÷ identificadas",
        ),
    )


def _grid_table(board: LookaheadBoard) -> Table:
    columns = (
        Column("ID", width=10),
        Column("Atividade", width=48),
        Column("Responsável", width=24),
        *(Column(week_caption(week), width=12) for week in board.weeks),
        Column("Restrições", width=22),
    )
    rows = tuple(
        row(
            activity.code,
            f"{activity.name} · {activity.area} · {activity.discipline}",
            activity.owner_name,
            *(MARK if marked else "" for marked in activity.planned),
            Cell(constraints_summary(activity), _situation_tone(activity)),
            project=activity.project_label,
        )
        for activity in board.activities
    )
    return Table(title=GRID_TITLE, columns=columns, rows=rows)


def _situation_tone(activity: ActivityView) -> Tone:
    if activity.overdue_constraints:
        return Tone.ERROR
    return Tone.WARN if activity.open_constraints else Tone.OK


def _constraints_table(board: LookaheadBoard) -> Table:
    columns = (
        Column("Atividade", width=48),
        Column("Tipo", width=18),
        Column("Restrição", width=44),
        Column("Responsável", width=24),
        Column("Necessária até", ValueKind.DATE, width=16),
        Column("Removida em", ValueKind.DATE, width=16),
        Column("Situação", width=12),
    )
    rows = tuple(
        row(
            f"{item.activity_code} {item.activity_name}",
            item.kind,
            item.description,
            item.owner_name,
            item.due_date,
            item.removal_date,
            Cell(item.status, _STATUS_TONES[item.status]),
            project=item.project_label,
        )
        for item in board.constraints
    )
    return Table(title=CONSTRAINTS_TITLE, columns=columns, rows=rows)


def gantt_data(board: LookaheadBoard) -> dict[str, Any]:
    """The ``data-dados`` of the Gantt: one bar per activity, from its first to its last week.

    The prototype grid became the library Gantt (D11): ``atrasada`` marks an
    activity planned in the first two weeks with an open restriction, ``critica``
    one with an overdue restriction and ``concluida`` one that is ready.
    """
    window_start = board.weeks[0].start
    activities = []
    for activity in board.activities:
        span = calculations.activity_span(activity.planned, window_start)
        label, role = _SITUATION_LABELS[activity.situation]
        activities.append(
            {
                "id": str(activity.id),
                "wbs": activity.code,
                "nome": activity.name,
                "inicio": span[0].isoformat() if span else None,
                "fim": span[1].isoformat() if span else None,
                "concluida": activity.is_ready,
                "critica": activity.overdue_constraints > 0,
                "atrasada": activity.has_short_term_risk,
                "situacao": {"rotulo": label, "papel": role},
            }
        )
    last = calendario.add_days(window_start, calculations.LOOKAHEAD_WEEKS * 7 - 1)
    return {
        "titulo": GRID_TITLE,
        "hoje": board.reference_date.isoformat(),
        "inicio": window_start.isoformat(),
        "fim": last.isoformat(),
        "atividades": activities,
        "rotulos": dict(_GANTT_LABELS),
    }


def gallery_data(constraints: Sequence[ConstraintView]) -> dict[str, Any]:
    """The ``data-dados`` of the Galeria: one card per open restriction, the overdue ones first."""
    open_ones = [item for item in constraints if item.is_open]
    open_ones.sort(key=lambda item: (not item.is_overdue, item.due_date, item.id))
    return {
        "titulo": "Restrições abertas",
        "contador": "Restrições abertas",
        "itens": [_card(item) for item in open_ones],
    }


def _card(item: ConstraintView) -> Mapping[str, Any]:
    return {
        "titulo": f"{item.activity_code} · {item.activity_name}",
        "meta": [
            {"rotulo": "Tipo", "valor": item.kind},
            {"rotulo": "Responsável", "valor": item.owner_name},
            {"rotulo": "Necessária até", "valor": _date_text(item.due_date)},
            {"rotulo": "Situação", "valor": item.status},
        ],
        "texto": item.description,
    }


def _date_text(value: date) -> str:
    return f"{value:%d/%m/%Y}"
