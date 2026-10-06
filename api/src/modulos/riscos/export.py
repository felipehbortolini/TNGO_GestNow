"""The export of the screen Registro: one ``Document``, the Excel and the printable version (D12).

What the screen shows is what leaves: the five KPIs with their reference, the line of active
filters and the table of the risks of the filter, with the same content the prototype exported
(``Nº``, ``Risco`` with the category, ``Natureza``, ``Dono``, the two assessments written as
``12 (P3 x I4, Alto)``, ``Estratégia``, the actions, ``Próx. revisão`` and ``Situação``). In the
Portfólio the table opens with ``Projeto`` (HU-016). The table is wide, so the printable
version asks for A3 landscape.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
from src.modulos.riscos import presentation
from src.modulos.riscos.service import AssessmentView, BandCount, RiskLine, RiskListing
from src.modulos.riscos.validation import INHERENT, RiskFilters

TITLE = "Registro de riscos"
TABLE_TITLE = "Riscos"
NOT_ASSESSED = "não avaliado"
NEVER_REVIEWED = "sem data"
OVERDUE_SUFFIX = " (vencida)"

SITUATION_TONES = {
    "Identificado": Tone.NEUTRAL,
    "Em análise": Tone.WARN,
    "Em tratamento": Tone.INFO,
    "Monitorado": Tone.OK,
    "Materializado": Tone.ERROR,
    "Encerrado": Tone.NEUTRAL,
}


def build_document(
    *,
    listing: RiskListing,
    filters: RiskFilters,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the screen for the filters in force: KPIs, filters and the table."""
    labels = project_labels(listing)
    bands = listing.parameters.scale.bands
    owners = dict(listing.owners)
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            (
                "Filtros",
                presentation.summary(
                    filters,
                    bands=bands,
                    owners=owners,
                    review_alert_days=listing.parameters.review_alert_days,
                ),
            ),
            ("Avaliação exibida", "Inerente" if filters.assessment == INHERENT else "Residual"),
            ("Riscos no filtro", str(listing.total)),
        ),
        kpis=_kpis(listing),
        tables=(_table(listing.lines, labels),),
        paper=Paper.A3,
    )


def project_labels(listing: RiskListing) -> dict[int, str]:
    """``TN-001 · Nome do projeto`` by project id, for the column Projeto."""
    return {item.id: f"{item.code} · {item.name}" for item in listing.projects}


def assessment_text(view: AssessmentView | None) -> str:
    """The assessment as the prototype exported it: ``12 (P3 x I4, Alto)``."""
    if view is None:
        return NOT_ASSESSED
    return f"{view.score} (P{view.probability} x I{view.impact}, {view.severity.name})"


def _band_kpi(count: BandCount, assessment: str, *, heavy: Tone) -> Kpi:
    shown = "inerente" if assessment == INHERENT else "residual"
    detail = (
        f"{count.threats} ameaça(s)"
        + (f" · {count.opportunities} oportunidade(s)" if count.opportunities else "")
        if count.total
        else "nenhum na faixa"
    )
    return Kpi(
        f"{count.band.name}s ({shown})",
        count.total,
        f"Meta: {count.goal}",
        ValueKind.INTEGER,
        tone=heavy if count.total else Tone.OK,
        status=detail,
    )


def _kpis(listing: RiskListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    kpis = [_band_kpi(summary.top, summary.assessment, heavy=Tone.ERROR)]
    if summary.second is not None:
        kpis.append(_band_kpi(summary.second, summary.assessment, heavy=Tone.WARN))
    kpis.extend(
        (
            Kpi(
                "Em tratamento",
                summary.in_treatment,
                f"Esperado: {summary.expected_in_treatment}",
                ValueKind.INTEGER,
                tone=Tone.INFO,
                status="plano aprovado e ações em curso",
            ),
            Kpi(
                "Revisão vencida",
                len(summary.overdue),
                "Esperado: 0",
                ValueKind.INTEGER,
                tone=Tone.ERROR if summary.overdue else Tone.OK,
                status="próxima revisão anterior a hoje",
            ),
            Kpi(
                "Ativos",
                summary.active,
                f"Referência: de {summary.registered} registrados",
                ValueKind.INTEGER,
                tone=Tone.NEUTRAL,
                status=f"{summary.unassessed} sem avaliação",
            ),
        )
    )
    return tuple(kpis)


def _table(lines: Sequence[RiskLine], labels: Mapping[int, str]) -> Table:
    return Table(
        title=TABLE_TITLE,
        columns=(
            Column("Nº", width=20),
            Column("Risco", width=60),
            Column("Natureza", width=14),
            Column("Dono", width=22),
            Column("Inerente", width=24),
            Column("Residual", width=24),
            Column("Estratégia", width=16),
            Column("Ações", width=22),
            Column("Próx. revisão", width=20),
            Column("Situação", width=16),
        ),
        rows=tuple(_row(line, labels) for line in lines),
    )


def _actions_text(line: RiskLine) -> str:
    counts = line.actions
    suffix = f" ({counts.overdue} atrasadas)" if counts.overdue else ""
    return f"{counts.open} abertas de {counts.total}{suffix}"


def _review_text(line: RiskLine) -> str:
    if line.next_review is None:
        return NEVER_REVIEWED if line.active else "encerrado"
    text = line.next_review.strftime("%d/%m/%Y")
    return text + OVERDUE_SUFFIX if line.review_overdue else text


def _row(line: RiskLine, labels: Mapping[int, str]) -> Row:
    return row(
        line.code,
        f"{line.title} · {line.category_label}",
        line.nature,
        line.owner_name,
        assessment_text(line.inherent),
        assessment_text(line.residual),
        line.strategy or "sem plano",
        _actions_text(line),
        _review_text(line),
        Cell(line.situation, SITUATION_TONES.get(line.situation, Tone.NEUTRAL)),
        project=labels.get(line.project_id),
    )
