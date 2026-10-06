"""Export blueprint: the reference routes of the two exports every screen has (D12, ISSUE-017).

A screen builds one ``Document`` (``core.export_document``) and gets both exports from it,
each one a route of the module that owns the screen:

* the **Excel** is a download, the download exception of the Padrão: ``file_route`` (the access
  of every route, no Alpine gate, a refusal in plain text) and ``core.excel.excel_response``;
  the button ``data-tn-excel`` of ``ds/ui.js`` takes the file;
* the **PDF** is the printable version: ``fragment_route`` and
  ``core.printable.printable_response``; the button ``data-tn-pdf`` of ``ds/ui.js`` fetches the
  fragment, mounts it and calls ``window.print()``, and the person chooses "Salvar como PDF".
  There is no PDF library, on the server or in the browser.

The two routes here are the example a module copies, with fictional data, and
``app/exemplos/exportacao.html`` is the page that shows the buttons at work. They exist only in
the demonstration mode (403 in production): fictional data has no place there. What a module
needs is in ``api/README.md``, section "Exportação".

* ``GET /api/exportacao/exemplo/excel`` is the workbook;
* ``GET /api/exportacao/exemplo/imprimivel`` is the printable fragment; ``?papel=a3`` asks for
  A3 landscape, which a real screen fixes in its own ``Document`` (``Paper.A3``, as the MAS does).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, config
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.excel import excel_response
from src.core.export_document import (
    Cell,
    Chart,
    Column,
    Document,
    Kpi,
    Paper,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    project_label,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes

bp = func.Blueprint()

EXCEL_ROUTE = "exportacao/exemplo/excel"
PRINTABLE_ROUTE = "exportacao/exemplo/imprimivel"

EXAMPLE_TITLE = "Exemplo de exportação"
EXAMPLE_NOTE = ("Dados", "fictícios, só para mostrar o mecanismo")
DEMONSTRATION_ONLY_MESSAGE = "O exemplo de exportação só existe no modo demonstração."
UNKNOWN_PAPER_MESSAGE = "Papel desconhecido: use a4 ou a3."
PAPER_PARAMETER = "papel"

# Exporting is reading: whoever may view the data may take it out (a supplier has no general
# permission, so it is refused). A module asks for the access of its own screen.
EXAMPLE_ACCESS = Access(permission=Permission.VIEW)


@dataclass(frozen=True)
class _Activity:
    """A fictional activity: what the example table prints for each project in scope."""

    name: str
    start_offset_days: int
    quantity: int
    progress: Decimal
    value_cents: int
    status: str
    tone: Tone
    meaning: str


ACTIVITIES = (
    _Activity(
        name="Atividade de exemplo A",
        start_offset_days=-30,
        quantity=120,
        progress=Decimal(100),
        value_cents=450_000_00,
        status="No prazo",
        tone=Tone.OK,
        meaning="Dentro do previsto",
    ),
    _Activity(
        name="Atividade de exemplo B",
        start_offset_days=-10,
        quantity=80,
        progress=Decimal("62.5"),
        value_cents=275_000_00,
        status="Atenção",
        tone=Tone.WARN,
        meaning="Perto do limite",
    ),
    _Activity(
        name="Atividade de exemplo C",
        start_offset_days=5,
        quantity=40,
        progress=Decimal(10),
        value_cents=100_000_00,
        status="Atrasada",
        tone=Tone.ERROR,
        meaning="Passou do previsto",
    ),
)

# The contract of the chart (``app/ds/graficos/comparativo-barras.js``): the server sends the
# quantities and the library draws the bars and the variation.
CHART_DATA = {
    "titulo": "Linha de base x Atual",
    "paineis": [
        {
            "titulo": "Atividades por situação",
            "categorias": [
                {"id": "no_prazo", "rotulo": "No prazo", "papel": "ok", "favoravel": "sobe"},
                {"id": "atencao", "rotulo": "Atenção", "papel": "alerta", "favoravel": "desce"},
                {"id": "atrasadas", "rotulo": "Atrasadas", "papel": "erro", "favoravel": "desce"},
            ],
            "linhas": [
                {
                    "rotulo": "Linha de base",
                    "valores": {"no_prazo": 24, "atencao": 6, "atrasadas": 0},
                },
                {"rotulo": "Atual", "valores": {"no_prazo": 20, "atencao": 7, "atrasadas": 3}},
            ],
        }
    ],
}


@bp.route(route=EXCEL_ROUTE, methods=["GET"])
@file_route(access=EXAMPLE_ACCESS)
def example_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the example: the download every screen offers."""
    return excel_response(_document_of_request(req, session, context))


@bp.route(route=PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=EXAMPLE_ACCESS)
def example_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the example: what the PDF button mounts and prints."""
    return printable_response(_document_of_request(req, session, context), req)


def example_document(
    *, scope: Scope, projects: Sequence[ProjectLike], paper: Paper, today: date
) -> Document:
    """The fictional document: every kind of value, a tone, KPIs with reference and a chart.

    ``today`` is an argument, as in every calculation: only the route reads the clock.
    """
    in_scope = _projects_in(scope, projects)
    return Document(
        title=EXAMPLE_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(EXAMPLE_NOTE,),
        kpis=_kpis(today),
        charts=(Chart("Gráfico de exemplo", "comparativo-barras", CHART_DATA),),
        tables=(_activities_table(in_scope, today), _legend_table()),
        paper=paper,
    )


def _document_of_request(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    """The example for the scope of the request; the only place that reads the clock."""
    if config.app_mode() != config.DEMONSTRATION:
        raise AccessDeniedError(DEMONSTRATION_ONLY_MESSAGE)
    return example_document(
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        paper=_paper_of(req),
        today=calendario.today(),
    )


def _paper_of(req: func.HttpRequest) -> Paper:
    raw = (req.params.get(PAPER_PARAMETER) or Paper.A4.value).strip().lower()
    try:
        return Paper(raw)
    except ValueError:
        raise InvalidDataError(UNKNOWN_PAPER_MESSAGE) from None


def _projects_in(scope: Scope, projects: Sequence[ProjectLike]) -> tuple[ProjectLike, ...]:
    """The Portfólio has every project; a project scope has only its own."""
    if scope.is_portfolio:
        return tuple(projects)
    return tuple(project for project in projects if project.id == scope.project_id)


def _kpis(today: date) -> tuple[Kpi, ...]:
    return (
        Kpi(
            "Avanço",
            Decimal("87.5"),
            "Meta: 90%",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.WARN,
            status="Atenção",
        ),
        Kpi(
            "Desembolso",
            1_250_000_00,
            "Orçado: R$ 1.500.000,00",
            ValueKind.MONEY,
            tone=Tone.OK,
            status="Dentro do orçado",
        ),
        Kpi(
            "Atividades concluídas",
            18,
            "Previsto: 20",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status="Em andamento",
        ),
        Kpi(
            "Próximo marco",
            calendario.add_days(today, 14),
            "Data prevista",
            ValueKind.DATE,
            tone=Tone.INFO,
            status="Futuro",
        ),
    )


def _activities_table(projects: Sequence[ProjectLike], today: date) -> Table:
    """One row per activity and project; empty in a Portfólio without projects."""
    rows: tuple[Row, ...] = tuple(
        row(
            activity.name,
            calendario.add_days(today, activity.start_offset_days),
            activity.quantity,
            activity.progress,
            activity.value_cents,
            Cell(activity.status, activity.tone),
            project=project_label(project),
        )
        for project in projects
        for activity in ACTIVITIES
    )
    return Table(
        title="Atividades de exemplo",
        columns=(
            Column("Atividade", width=34),
            Column("Início", ValueKind.DATE),
            Column("Quantidade", ValueKind.INTEGER),
            Column("Avanço", ValueKind.PERCENT, digits=1),
            Column("Valor", ValueKind.MONEY),
            Column("Situação"),
        ),
        rows=rows,
        totals=_totals(len(projects)) if projects else None,
    )


def _totals(project_count: int) -> tuple[Cell, ...]:
    return (
        Cell("Total"),
        Cell(),
        Cell(sum(activity.quantity for activity in ACTIVITIES) * project_count),
        Cell(),
        Cell(sum(activity.value_cents for activity in ACTIVITIES) * project_count),
        Cell(),
    )


def _legend_table() -> Table:
    """A table that is not per project: the Portfólio does not give it the ``Projeto`` column."""
    return Table(
        title="Legenda das situações",
        columns=(Column("Situação"), Column("Significado")),
        rows=tuple(
            row(Cell(activity.status, activity.tone), activity.meaning) for activity in ACTIVITIES
        ),
        per_project=False,
    )
