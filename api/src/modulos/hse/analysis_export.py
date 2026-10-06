"""Export of the screen Análises de risco: one ``Document`` for the Excel and the printable version.

Same content as the prototype: the four indicators with their reference and the table of studies,
with the recommendations of each one summed up in a cell. In the Portfólio the table opens with
``Projeto`` (HU-016).
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
from src.modulos.hse.analysis_service import AnalysisListing, AnalysisRow
from src.modulos.hse.calculations import RecommendationCounts

TITLE = "Análises de risco (APR/HAZOP)"
FILE = "analises-risco-hse"
NONE = "·"
EXPECTED_ZERO = "Esperado: 0"


def analysis_document(
    listing: AnalysisListing, *, scope: Scope, projects: Sequence[ProjectLike], today: date
) -> Document:
    """The document of the screen: indicators and the studies of the list in view."""
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        kpis=_kpis(listing),
        tables=(_table(listing.rows),),
    )


def _kpis(listing: AnalysisListing) -> tuple[Kpi, ...]:
    counts = listing.counts
    rate = listing.closed_rate
    return (
        Kpi(
            "Estudos registrados",
            len(listing.rows),
            f"Referência: de {listing.universe} registrados",
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
        Kpi(
            "Recomendações abertas",
            counts.open,
            EXPECTED_ZERO,
            ValueKind.INTEGER,
            tone=Tone.WARN if counts.open else Tone.OK,
            status="Com pendências" if counts.open else "Nenhuma aberta",
        ),
        Kpi(
            "Recomendações atrasadas",
            counts.overdue,
            EXPECTED_ZERO,
            ValueKind.INTEGER,
            tone=Tone.ERROR if counts.overdue else Tone.OK,
            status="Fora do prazo" if counts.overdue else "Nenhuma atrasada",
        ),
        Kpi(
            "Recomendações fechadas",
            rate if rate is not None else NONE,
            "Esperado: 100%",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
    )


def _table(rows: Sequence[AnalysisRow]) -> Table:
    return Table(
        title="Estudos",
        columns=(
            Column("Nº", width=20),
            Column("Tipo", width=12),
            Column("Área", width=24),
            Column("Título", width=40),
            Column("Data", ValueKind.DATE),
            Column("Participantes", ValueKind.INTEGER),
            Column("Recomendações", width=40),
        ),
        rows=tuple(_row(item) for item in rows),
    )


def _tone(counts: RecommendationCounts) -> Tone:
    if counts.overdue:
        return Tone.ERROR
    return Tone.WARN if counts.open else Tone.OK


def _row(item: AnalysisRow) -> Row:
    counts = item.counts
    return row(
        item.code,
        "HAZOP" if item.kind == "HAZOP" else "APR / JSA",
        item.area,
        item.title,
        item.studied_on,
        len(item.participant_ids),
        Cell(
            f"{counts.open} abertas ({counts.overdue} atrasadas), {counts.closed} fechadas",
            _tone(counts),
        ),
        project=item.project_label,
    )
