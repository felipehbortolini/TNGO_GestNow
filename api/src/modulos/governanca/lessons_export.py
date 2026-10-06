"""Export of the Acervo de lições (D12, ISSUE-027/ISSUE-028): the Excel and the printable version.

One ``Document`` gives both outputs (``core.excel`` and ``core.printable``), with the columns the
prototype exported. In the Portfólio the table opens with the ``Projeto`` column (HU-016), and the
tables of the Painel (fase, área, situação, mais reusadas e projetos sem registro) go with it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
    Column,
    Document,
    Paper,
    Table,
    ValueKind,
    describe_scope,
    project_label,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.governanca import lessons_panel as panel_charts
from src.modulos.governanca import lessons_presentation as presentation
from src.modulos.governanca.lessons_calculations import LessonGroupLine
from src.modulos.governanca.lessons_service import Acervo, LessonFilter, LessonPanel

ACERVO_TITLE = "Acervo de lições aprendidas"


def acervo_document(
    acervo: Acervo,
    *,
    panel: LessonPanel,
    scope: Scope,
    projects: Sequence[ProjectLike],
    filters: LessonFilter,
    today: date,
) -> Document:
    """The Acervo de lições: the table of the filters and the tables of the Painel."""
    return Document(
        title=ACERVO_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=_filter_context(filters),
        charts=panel_charts.charts_of(panel),
        tables=(
            _lessons_table(acervo),
            _panel_group_table("Lições por fase", "Fase", panel.by_phase),
            _panel_group_table("Lições por área de conhecimento", "Área", panel.by_area),
            _panel_situation_table(panel),
            _panel_reused_table(panel),
            _panel_projects_table(panel),
        ),
        paper=Paper.A3,
    )


def _panel_group_table(title: str, label: str, lines: Sequence[LessonGroupLine]) -> Table:
    return Table(
        title=title,
        columns=(
            Column(label, width=30),
            Column("Lições", ValueKind.INTEGER),
            Column("A repetir", ValueKind.INTEGER),
            Column("A evitar", ValueKind.INTEGER),
            Column("Publicadas", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(line.label, line.total, line.to_repeat, line.to_avoid, line.published)
            for line in lines
        ),
        per_project=False,
    )


def _panel_situation_table(panel: LessonPanel) -> Table:
    return Table(
        title="Lições por situação",
        columns=(Column("Situação", width=30), Column("Lições", ValueKind.INTEGER)),
        rows=tuple(
            row(Cell(line.label, presentation.situation_tone(line.label)), line.total)
            for line in panel.by_situation
        ),
        per_project=False,
    )


def _panel_reused_table(panel: LessonPanel) -> Table:
    return Table(
        title="Lições mais reusadas",
        columns=(
            Column("Lição", width=18),
            Column("Título", width=44),
            Column("Tipo"),
            Column("Reusos", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                item.code,
                item.title,
                Cell(item.kind, presentation.kind_tone(item.kind)),
                item.reuses,
                project=item.project_label,
            )
            for item in panel.most_reused
        ),
    )


def _panel_projects_table(panel: LessonPanel) -> Table:
    return Table(
        title="Projetos sem registro de lição no período",
        columns=(Column("Projeto", width=40),),
        rows=tuple(
            row(project_label(item), project=project_label(item))
            for item in panel.projects_without_record
        ),
    )


def _filter_context(filters: LessonFilter) -> tuple[tuple[str, str], ...]:
    labelled = (
        ("Tipo", filters.kind),
        ("Situação", filters.situation),
        ("Fase", filters.phase),
        ("Área", filters.area),
        ("Disciplina", filters.discipline),
        ("Origem", filters.origin),
        ("Aplicabilidade", filters.applicability),
        ("Busca", filters.search),
    )
    return tuple((label, value) for label, value in labelled if value)


def _lessons_table(acervo: Acervo) -> Table:
    return Table(
        title="Lições",
        columns=(
            Column("Código", width=18),
            Column("Título", width=44),
            Column("Tipo"),
            Column("Situação", width=14),
            Column("Fase"),
            Column("Área"),
            Column("Disciplina"),
            Column("Aplicabilidade"),
            Column("Origem", width=30),
            Column("Recomendação", width=60),
            Column("Prazo (dias)", ValueKind.INTEGER),
            Column("Custo", ValueKind.MONEY),
            Column("Reusos", ValueKind.INTEGER),
            Column("Data", ValueKind.DATE),
        ),
        rows=tuple(
            row(
                item.code,
                item.title,
                item.kind,
                Cell(item.situation, presentation.situation_tone(item.situation)),
                item.phase,
                item.area,
                item.discipline,
                item.applicability,
                _origin_text(item.origin_label, item.origin_ref),
                item.recommendation,
                item.term_days,
                item.cost_cents,
                item.reuses,
                item.registered_on,
                project=item.project_label,
            )
            for item in acervo.rows
        ),
    )


def _origin_text(label: str, reference: str | None) -> str:
    return f"{label} {reference}" if reference else label
