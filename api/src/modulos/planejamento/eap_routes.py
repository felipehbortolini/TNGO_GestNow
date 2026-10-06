"""Route blueprint of the EAP screen (ISSUE-036, D14), all under ``/api/planejamento/eap``.

* ``GET /eap`` is the content of the screen (KPIs, tree, revisions and splits) for the scope of
  the request, with the filters ``busca``, ``nivel``, ``criterio`` and ``situacao``; in the
  Portfólio the tree is read-only (project and main packages);
* ``GET /eap/pacotes/{item_id}/dicionario`` is the dictionary of a package: what it delivers,
  who does it, how it is measured and the history of its measurements;
* ``GET /eap/excel`` and ``GET /eap/imprimivel`` are the two exports of the platform, with the
  same filters, so the file has what the screen shows.

The routes read the request and draw the answer; every rule is in ``eap_service``. Registering
the advance (ISSUE-037) and the revisions (ISSUE-038) add their routes to this blueprint.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario
from src.core.errors import InvalidDataError
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, describe_scope, format_value
from src.core.printable import printable_response
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import eap_calculations as calculations
from src.modulos.planejamento import eap_export, eap_service
from src.modulos.planejamento.eap_calculations import TreeRow
from src.modulos.planejamento.eap_service import EapFilters, EapView, PackageDictionary

bp = func.Blueprint()

CONTENT_ROUTE = "planejamento/eap"
DICTIONARY_ROUTE = "planejamento/eap/pacotes/{item_id}/dicionario"
EXCEL_ROUTE = "planejamento/eap/excel"
PRINTABLE_ROUTE = "planejamento/eap/imprimivel"

CONTENT_TEMPLATE = "planejamento/eap_conteudo.html"
DICTIONARY_TEMPLATE = "planejamento/eap_dicionario.html"

DICTIONARY_TARGET = "eap-dicionario"
CONTENT_TARGET = "eap-conteudo"
ITEM_PARAMETER = "item_id"
TONE_CLASSES = {
    calculations.OK: "ok",
    calculations.WARNING: "warn",
    calculations.DANGER: "erro",
}

# Reading the EAP is reading the module (a supplier reaches neither the screen nor the file).
READ_ACCESS = Access(module=eap_service.MODULE)


@dataclass(frozen=True)
class LineView:
    """A line of the tree as the table prints it: the row, its texts and what can be opened."""

    row: TreeRow
    criterion: str
    quantity: str
    executed: str
    weight: str
    weight_in_parent: str
    start: str
    end: str
    planned: str
    real: str
    deviation: str
    tone: str
    has_children: bool
    can_open_dictionary: bool
    description_suffix: str


# ── Tela ─────────────────────────────────────────────────────────────────


@bp.route(route=CONTENT_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eap_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The content of the EAP screen: the KPIs, the tree, the revisions and the splits."""
    view = _view_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTENT_TEMPLATE, context=_content_context(view), request=req
    )


@bp.route(route=EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def eap_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the EAP: the download of the screen, with the same filters."""
    return excel_response(_document_of(req, session, context))


@bp.route(route=PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eap_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the EAP: what the PDF button mounts and prints."""
    return printable_response(_document_of(req, session, context), req)


@bp.route(route=DICTIONARY_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eap_dictionary(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The dictionary of a package of the project in scope."""
    dictionary = eap_service.package_dictionary(
        session,
        user=context.user,
        scope=context.scope,
        item_id=_item_id_of(req),
        reference_date=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=DICTIONARY_TEMPLATE, context=_dictionary_context(dictionary), request=req
    )


# ── Montagem ─────────────────────────────────────────────────────────────


def _view_of(req: func.HttpRequest, session: Session, context: RequestContext) -> EapView:
    """The EAP of the request; the only place of the reading routes that reads the clock."""
    return eap_service.eap_view(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.params),
        reference_date=calendario.today(),
    )


def _document_of(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    view = _view_of(req, session, context)
    return eap_export.eap_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _filters_of(source: Mapping[str, str | None]) -> EapFilters:
    """The filters of the tree from a query: an unreadable level is the deepest, an unknown value is none."""
    raw_level = (source.get("nivel") or "").strip()
    criterion = (source.get("criterio") or "").strip()
    situation = (source.get("situacao") or "").strip()
    return EapFilters(
        search=(source.get("busca") or "").strip(),
        level=int(raw_level) if raw_level.isdigit() else calculations.PACKAGE_LEVEL,
        criterion=criterion
        if criterion in (*calculations.CRITERIA, calculations.FILTER_PLANNING)
        else "",
        situation=situation
        if situation
        in (
            calculations.SITUATION_BEHIND,
            calculations.SITUATION_OVERDUE,
            calculations.SITUATION_PLANNING,
        )
        else "",
    )


def _item_id_of(req: func.HttpRequest) -> int:
    raw = req.route_params.get(ITEM_PARAMETER) or ""
    if not raw.isdigit():
        raise InvalidDataError(eap_service.NOT_FOUND_MESSAGE)
    return int(raw)


def _content_context(view: EapView) -> dict[str, object]:
    return {
        "view": view,
        "linhas": [_line_view(view, row) for row in view.rows],
        "resultado": _result_of(view),
        "kpis": _kpis(view),
        "pesos": _percent(view.summary.weight_total, 2),
        "peso_planejamento": _percent(view.summary.planning_weight, 2),
        "revisoes": [_revision_line(item) for item in view.revisions],
        "desdobramentos": [_split_line(item) for item in view.splits],
        "referencia": _date(view.reference_date),
        "limite_menor": _number(view.bands[0]),
        "limite_maior": _number(view.bands[1]),
        "alvo_dicionario": DICTIONARY_TARGET,
        "alvo_conteudo": CONTENT_TARGET,
    }


def _result_of(view: EapView) -> str:
    if view.is_empty:
        return "vazio-origem"
    return "vazio-filtro" if view.has_no_match else "conteudo"


def _line_view(view: EapView, row: TreeRow) -> LineView:
    is_package = row.level == calculations.PACKAGE_LEVEL and not view.is_portfolio
    is_planning = is_package and not row.is_work
    return LineView(
        row=row,
        criterion=eap_export.criterion_text(row),
        quantity=_number(row.quantity) if row.criterion == calculations.UNITS else "",
        executed=_number(row.executed) if row.criterion == calculations.UNITS else "",
        weight=_percent(row.weight, 2),
        weight_in_parent=_percent(row.weight_in_parent, 1),
        start=_date(row.start_date),
        end=_date(row.end_date),
        planned=_percent(row.planned, 1),
        real="" if is_planning else _percent(row.real, 1),
        deviation="" if is_planning else _signed(row.deviation),
        tone="" if is_planning else TONE_CLASSES.get(row.band or "", ""),
        has_children=row.code in view.parents,
        can_open_dictionary=is_package and row.item_id is not None,
        description_suffix=" (pacote de planejamento)" if is_planning else "",
    )


@dataclass(frozen=True)
class _Kpi:
    """A KPI of the screen: its label, its value, its tone, the line under it and the icon."""

    label: str
    value: str
    tone: str
    note: str
    icon: str
    expected_label: str = ""
    expected: str = ""


def _kpis(view: EapView) -> list[_Kpi]:
    summary = view.summary
    current = view.current_revision
    baseline = (
        _number(Decimal(current.package_count))
        if current is not None and current.package_count is not None
        else "·"
    )
    package_note = (
        f"{summary.project_count} projetos · {summary.area_count} pacotes principais"
        if view.is_portfolio
        else _project_note(view)
    )
    return [
        _Kpi(
            label="Avanço físico ponderado" if view.is_portfolio else "Avanço físico real",
            value=_percent(summary.real, 1),
            tone=TONE_CLASSES.get(summary.band or "", "neutro"),
            note=f"desvio {_signed(summary.deviation)} p.p.",
            icon="chartLine",
            expected_label="Previsto",
            expected=_percent(summary.planned, 1),
        ),
        _Kpi(
            label="Pacotes de trabalho",
            value=str(summary.work_count),
            tone="info",
            note=package_note,
            icon="layers",
            expected_label="Linha de base" if not view.is_portfolio else "",
            expected=baseline if not view.is_portfolio else "",
        ),
        _Kpi(
            label="Término vencido",
            value=str(summary.overdue_count),
            tone="erro" if summary.overdue_count else "ok",
            note=f"{summary.behind_count} pacotes com desvio abaixo de -{_number(view.bands[1])} p.p.",
            icon="calendar",
            expected_label="Esperado",
            expected="0",
        ),
    ]


def _project_note(view: EapView) -> str:
    summary = view.summary
    note = f"{summary.area_count} áreas · {summary.subarea_count} subáreas"
    if summary.planning_count:
        note += (
            f" · {summary.planning_count} de planejamento ({_percent(summary.planning_weight, 2)})"
        )
    return note


@dataclass(frozen=True)
class RevisionLine:
    """A revision as the list prints it."""

    project: str
    name: str
    revised_on: str
    package_count: str
    change: str
    change_code: str
    justification: str
    approved_by: str
    is_baseline: bool
    is_current: bool


def _revision_line(item: eap_service.RevisionView) -> RevisionLine:
    return RevisionLine(
        project=item.project_label,
        name=f"Rev {item.number}",
        revised_on=_date(item.revised_on),
        package_count="" if item.package_count is None else str(item.package_count),
        change=item.change,
        change_code=item.change_code or "",
        justification=item.justification,
        approved_by=item.approved_by,
        is_baseline=item.number == 0,
        is_current=item.is_current,
    )


@dataclass(frozen=True)
class SplitLine:
    """A split as the list prints it."""

    split_on: str
    source: str
    target: str
    weight: str
    justification: str
    by: str


def _split_line(item: eap_service.SplitView) -> SplitLine:
    return SplitLine(
        split_on=_date(item.split_on),
        source=item.source,
        target=item.target,
        weight=_percent(item.weight, 2),
        justification=item.justification,
        by=item.by,
    )


def _dictionary_context(dictionary: PackageDictionary) -> dict[str, object]:
    row = dictionary.row
    return {
        "dicionario": dictionary,
        "linha": row,
        "tipo": "Pacote de trabalho"
        if row.is_work
        else "Pacote de planejamento (peso reservado, sem medição)",
        "criterio": eap_export.criterion_text(row)
        + (f" · {dictionary.stage_model}" if dictionary.stage_model else ""),
        "peso": _percent(row.weight, 2),
        "peso_no_nivel": _percent(row.weight_in_parent, 1),
        "inicio": _date(row.start_date),
        "termino": _date(row.end_date),
        "previsto": _percent(row.planned, 1),
        "real": _percent(row.real, 1),
        "desvio": _signed(row.deviation),
        "tom": TONE_CLASSES.get(row.band or "", ""),
        "quantidade": _number(row.quantity) if row.criterion == calculations.UNITS else "",
        "executado": _number(row.executed) if row.criterion == calculations.UNITS else "",
        "etapas": [
            (stage.name, _number(stage.weight), _percent(stage.percent, 0))
            for stage in dictionary.stages
        ],
        "medicoes": [
            (
                _date(item.measured_on),
                _percent(item.from_percent, 1),
                _percent(item.to_percent, 1),
                item.author,
                item.note,
            )
            for item in dictionary.measurements
        ],
        "alvo_dicionario": DICTIONARY_TARGET,
    }


def _percent(value: Decimal | None, digits: int) -> str:
    return "" if value is None else format_value(ValueKind.PERCENT, value, digits)


def _number(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format_value(ValueKind.DECIMAL, value, 2)
    return text.removesuffix(",00")


def _signed(value: Decimal) -> str:
    text = format_value(ValueKind.DECIMAL, value, 1)
    return f"+{text}" if value > 0 else text


def _date(value: date | None) -> str:
    return "" if value is None else format_value(ValueKind.DATE, value)
