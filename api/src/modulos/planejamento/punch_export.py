"""Excel and PDF of the Punch list (D12, ISSUE-049): one description, two outputs.

The same content the prototype exported (``GI.exportar.registrar`` of ``punch-list.js``): the
indicators, the table of the items of the filter and the table of the systems with the release
by milestone. In the Portfólio each table opens with the Projeto column.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
    Column,
    Document,
    Kpi,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.planejamento import punch_calculations as calc
from src.modulos.planejamento import punch_service as service

DOCUMENT_TITLE = "Punch list"
ITEMS_TITLE = "Itens da Punch list"
SYSTEMS_TITLE = "Sistemas e liberação por marco"
BLOCKED = "Bloqueado"
RELEASED = "Liberado"

_SITUATION_TONE = {
    calc.OPEN: Tone.WARN,
    calc.IN_TREATMENT: Tone.INFO,
    calc.AWAITING_VERIFICATION: Tone.INFO,
    calc.CLOSED: Tone.OK,
    calc.CANCELLED: Tone.NEUTRAL,
}
_CATEGORY_TONE = {"A": Tone.ERROR, "B": Tone.INFO, "C": Tone.NEUTRAL}


def count_text(total: int) -> str:
    """``3 itens`` or ``1 item``: the line of the count under the filters."""
    return f"{total} {'item' if total == 1 else 'itens'} no filtro atual"


def punch_document(
    board: service.PunchBoard,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    generated_on: date,
) -> Document:
    """The Punch list as the exports carry it: indicators, items of the filter and systems."""
    return Document(
        title=DOCUMENT_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=generated_on,
        portfolio=scope.is_portfolio,
        context=(("Itens", count_text(len(board.rows))),),
        kpis=_kpis(board.figures),
        tables=(_items_table(board), _systems_table(board)),
    )


def _kpis(figures: service.Figures) -> tuple[Kpi, ...]:
    closed_reference = f"Meta: {figures.valid}"
    return (
        Kpi(
            "Abertos",
            figures.open,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if figures.open else Tone.OK,
        ),
        Kpi(
            "Categoria A abertos",
            figures.open_a,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if figures.open_a else Tone.OK,
            status="Impedem o marco seguinte",
        ),
        Kpi(
            "Aguardando verificação",
            figures.awaiting,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
        Kpi(
            "Vencidos",
            figures.overdue,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if figures.overdue else Tone.OK,
            status="O prazo passou e o item segue aberto",
        ),
        Kpi(
            "Fechados",
            figures.closed,
            closed_reference,
            ValueKind.INTEGER,
            tone=Tone.OK,
            status=_closed_status(figures),
        ),
    )


def _closed_status(figures: service.Figures) -> str:
    percentage = figures.closed_percentage
    return "" if percentage is None else f"{percentage}% dos itens válidos"


def _items_table(board: service.PunchBoard) -> Table:
    columns = (
        Column("Número", width=18),
        Column("Categoria", width=11),
        Column("Sistema", width=30),
        Column("Subsistema", width=18),
        Column("TAG", width=14),
        Column("Disciplina", width=14),
        Column("Descrição", width=48),
        Column("Marco", width=20),
        Column("Origem", width=14),
        Column("Responsável", width=22),
        Column("Empresa", width=20),
        Column("Abertura", ValueKind.DATE, width=12),
        Column("Prazo", ValueKind.DATE, width=12),
        Column("Idade (dias)", ValueKind.INTEGER, width=11),
        Column("Situação", width=22),
    )
    return Table(
        ITEMS_TITLE,
        columns,
        tuple(_item_row(item) for item in board.rows),
    )


def _item_row(item: service.PunchRow) -> Row:
    return row(
        item.code,
        Cell(f"Categoria {item.category}", _CATEGORY_TONE[item.category]),
        item.system_label,
        item.subsystem,
        item.tag,
        item.discipline,
        item.description,
        item.milestone,
        item.origin,
        item.responsible_name,
        item.company_name,
        item.opened_on,
        item.due_date,
        item.age_days,
        Cell(
            f"{item.situation} (vencido)" if item.is_overdue else item.situation,
            _SITUATION_TONE[item.situation],
        ),
        project=item.project_label,
    )


def _systems_table(board: service.PunchBoard) -> Table:
    columns = (
        Column("Sistema", width=34),
        Column("Área", width=22),
        Column("A abertos", ValueKind.INTEGER, width=11),
        Column("B abertos", ValueKind.INTEGER, width=11),
        Column("C abertos", ValueKind.INTEGER, width=11),
        *(Column(milestone, width=24) for milestone in calc.PANEL_MILESTONES),
    )
    return Table(
        SYSTEMS_TITLE,
        columns,
        tuple(_system_row(item) for item in board.systems),
    )


def _system_row(item: service.SystemRow) -> Row:
    return row(
        item.label,
        item.area,
        item.open_a,
        item.open_b,
        item.open_c,
        *(
            Cell(f"{BLOCKED} ({count})", Tone.ERROR) if count else Cell(RELEASED, Tone.OK)
            for count in item.blocks
        ),
        project=item.project_label,
    )
