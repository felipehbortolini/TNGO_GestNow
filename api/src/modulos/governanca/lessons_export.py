"""Export of the Acervo de lições (D12, ISSUE-027): the Excel and the printable version.

One ``Document`` gives both outputs (``core.excel`` and ``core.printable``), with the columns the
prototype exported. In the Portfólio the table opens with the ``Projeto`` column (HU-016).
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
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.governanca import lessons_presentation as presentation
from src.modulos.governanca.lessons_service import Acervo, LessonFilter

ACERVO_TITLE = "Acervo de lições aprendidas"


def acervo_document(
    acervo: Acervo,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    filters: LessonFilter,
    today: date,
) -> Document:
    """The Acervo de lições: one table with every lesson the filters let through."""
    return Document(
        title=ACERVO_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=_filter_context(filters),
        tables=(_lessons_table(acervo),),
        paper=Paper.A3,
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
