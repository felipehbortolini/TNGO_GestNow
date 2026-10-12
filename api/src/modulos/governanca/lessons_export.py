"""Export of the Acervo de lições (D12, ISSUE-027/ISSUE-028): the Excel and the printable version.

One ``Document`` gives both outputs (``core.excel`` and ``core.printable``), with the columns the
prototype exported. In the Portfólio the table opens with the ``Projeto`` column (HU-016), and the
tables of the Painel (fase, área, situação, mais reusadas e projetos sem registro) go with it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core import translations
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


def _label(text: str, idioma: str) -> str:
    """O texto de interface da Governança no idioma do request (D13)."""
    return translations.translate("governanca", text, idioma)


def acervo_document(
    acervo: Acervo,
    *,
    panel: LessonPanel,
    scope: Scope,
    projects: Sequence[ProjectLike],
    filters: LessonFilter,
    today: date,
    idioma: str = "pt",
) -> Document:
    """The Acervo de lições: the table of the filters and the tables of the Painel."""
    return Document(
        namespace="governanca",
        title=_label(ACERVO_TITLE, idioma),
        scope_label=describe_scope(scope, projects, idioma),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=_filter_context(filters, idioma),
        charts=panel_charts.charts_of(panel, idioma),
        tables=(
            _lessons_table(acervo, idioma),
            _panel_group_table(
                _label("Lições por fase", idioma), _label("Fase", idioma), panel.by_phase, idioma
            ),
            _panel_group_table(
                _label("Lições por área de conhecimento", idioma),
                _label("Área", idioma),
                panel.by_area,
                idioma,
            ),
            _panel_situation_table(panel, idioma),
            _panel_reused_table(panel, idioma),
            _panel_projects_table(panel, idioma),
        ),
        paper=Paper.A3,
        idioma=idioma,
    )


def _panel_group_table(
    title: str, label: str, lines: Sequence[LessonGroupLine], idioma: str
) -> Table:
    return Table(
        title=title,
        columns=(
            Column(label, width=30),
            Column(_label("Lições", idioma), ValueKind.INTEGER),
            Column(_label("A repetir", idioma), ValueKind.INTEGER),
            Column(_label("A evitar", idioma), ValueKind.INTEGER),
            Column(_label("Publicadas", idioma), ValueKind.INTEGER),
        ),
        rows=tuple(
            row(line.label, line.total, line.to_repeat, line.to_avoid, line.published)
            for line in lines
        ),
        per_project=False,
    )


def _panel_situation_table(panel: LessonPanel, idioma: str) -> Table:
    return Table(
        title=_label("Lições por situação", idioma),
        columns=(
            Column(_label("Situação", idioma), width=30),
            Column(_label("Lições", idioma), ValueKind.INTEGER),
        ),
        rows=tuple(
            row(Cell(line.label, presentation.situation_tone(line.label)), line.total)
            for line in panel.by_situation
        ),
        per_project=False,
    )


def _panel_reused_table(panel: LessonPanel, idioma: str) -> Table:
    return Table(
        title=_label("Lições mais reusadas", idioma),
        columns=(
            Column(_label("Lição", idioma), width=18),
            Column(_label("Título", idioma), width=44),
            Column(_label("Tipo", idioma)),
            Column(_label("Reusos", idioma), ValueKind.INTEGER),
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


def _panel_projects_table(panel: LessonPanel, idioma: str) -> Table:
    return Table(
        title=_label("Projetos sem registro de lição no período", idioma),
        columns=(Column(_label("Projeto", idioma), width=40),),
        rows=tuple(
            row(project_label(item), project=project_label(item))
            for item in panel.projects_without_record
        ),
    )


def _filter_context(filters: LessonFilter, idioma: str) -> tuple[tuple[str, str], ...]:
    labelled = (
        (_label("Tipo", idioma), filters.kind),
        (_label("Situação", idioma), filters.situation),
        (_label("Fase", idioma), filters.phase),
        (_label("Área", idioma), filters.area),
        (_label("Disciplina", idioma), filters.discipline),
        (_label("Origem", idioma), filters.origin),
        (_label("Aplicabilidade", idioma), filters.applicability),
        (_label("Busca", idioma), filters.search),
    )
    return tuple((label, value) for label, value in labelled if value)


def _lessons_table(acervo: Acervo, idioma: str) -> Table:
    return Table(
        title=_label("Lições", idioma),
        columns=(
            Column(_label("Código", idioma), width=18),
            Column(_label("Título", idioma), width=44),
            Column(_label("Tipo", idioma)),
            Column(_label("Situação", idioma), width=14),
            Column(_label("Fase", idioma)),
            Column(_label("Área", idioma)),
            Column(_label("Disciplina", idioma)),
            Column(_label("Aplicabilidade", idioma)),
            Column(_label("Origem", idioma), width=30),
            Column(_label("Recomendação", idioma), width=60),
            Column(_label("Prazo (dias)", idioma), ValueKind.INTEGER),
            Column(_label("Custo", idioma), ValueKind.MONEY),
            Column(_label("Reusos", idioma), ValueKind.INTEGER),
            Column(_label("Data", idioma), ValueKind.DATE),
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
