"""Exports of the Weekly scheduling: the governance panel and the change requests (D12).

One ``Document`` feeds both outputs (``core.excel`` and ``core.printable``): the four
indicators of the panel, the control list by company and week and the queue of change
requests, pending and decided. In the Portfólio every row carries its project and the
generic layer opens the ``Projeto`` column (HU-016). The trail stays on the screen,
as in the app: the audit has its own screen reading, not an export.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
    Column,
    Document,
    Kpi,
    Paper,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.programacao_semanal.views import (
    ChangeRequestView,
    GovernancePanel,
    RequestQueue,
)

GOVERNANCE_TITLE = "Governança da programação"
CONTROL_TITLE = "Lista de controle"
QUEUE_TITLE = "Pedidos de alteração"

REQUEST_TONES = {
    "pendente": Tone.WARN,
    "aplicado": Tone.OK,
    "rejeitado": Tone.NEUTRAL,
}


def governance_document(
    panel: GovernancePanel,
    queue: RequestQueue,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The governance screen as a document: the indicators, the control list and the queue."""
    return Document(
        title=GOVERNANCE_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Semana de referência", panel.reference_week),),
        kpis=_kpis(panel),
        tables=(_control_table(panel), _queue_table(queue)),
        paper=Paper.A4,
    )


def _kpis(panel: GovernancePanel) -> tuple[Kpi, ...]:
    return (
        Kpi(
            "Contratadas ativas",
            panel.active_companies,
            "Contratadas com atividade no histórico",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Janelas abertas hoje",
            panel.open_windows,
            f"Na semana {panel.reference_week}",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Aguardando fiscal",
            panel.situations.pending,
            "Realizado lançado sem aprovação",
            kind=ValueKind.INTEGER,
        ),
        Kpi(
            "Atividades no histórico",
            panel.situations.total,
            "Todas as semanas",
            kind=ValueKind.INTEGER,
        ),
    )


def _control_table(panel: GovernancePanel) -> Table:
    return Table(
        title=CONTROL_TITLE,
        columns=(
            Column("Contratada", width=24),
            Column("Semana"),
            Column("Programações", ValueKind.INTEGER),
            Column("Em elaboração", ValueKind.INTEGER),
            Column("Validadas", ValueKind.INTEGER),
            Column("Publicadas", ValueKind.INTEGER),
            Column("Pendências", ValueKind.INTEGER),
            Column("Aderência", ValueKind.PERCENT, digits=0),
            Column("Fiscal", width=24),
            Column("Última alteração", width=20),
        ),
        rows=tuple(
            row(
                line.company,
                line.week,
                line.total,
                line.draft,
                line.validated,
                line.published,
                line.pending,
                line.adherence,
                line.inspector or "—",
                line.updated_at_text or "—",
                project=line.project_label,
            )
            for line in panel.lines
        ),
    )


def _queue_table(queue: RequestQueue) -> Table:
    return Table(
        title=QUEUE_TITLE,
        columns=(
            Column("ID exclusiva"),
            Column("Contratada", width=24),
            Column("Semana"),
            Column("Motivo", width=60),
            Column("Situação", width=20),
            Column("Solicitado por", width=24),
            Column("Solicitado em", width=18),
            Column("Decidido por", width=24),
            Column("Decidido em", width=18),
            Column("Resposta", width=60),
        ),
        rows=tuple(_queue_row(view) for view in (*queue.pending, *queue.resolved)),
    )


def _queue_row(view: ChangeRequestView) -> Row:
    return row(
        view.unique_id,
        view.company,
        view.week,
        view.reason,
        Cell(view.situation, REQUEST_TONES.get(view.situation)),
        view.requested_by,
        view.requested_at_text,
        view.decided_by,
        view.decided_at_text,
        view.answer,
        project=view.project_label,
    )
