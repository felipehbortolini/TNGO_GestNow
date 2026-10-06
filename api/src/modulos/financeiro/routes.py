"""Route blueprint of the Financeiro module (D14).

The EAC screen (ISSUE-029) and what hangs from it, all under ``/api/financeiro/eac``:

* ``GET /eac`` is the content of the screen (KPIs and tree) for the scope of the request, with the
  filters ``busca``, ``nivel`` and ``tipo``; in the Portfólio it is read-only;
* ``GET /eac/itens/{item_id}/editar`` is the cadastral edit form of an item, with its history;
* ``POST /eac/itens/{item_id}`` saves it: justification required, no SM, nothing of value;
* ``GET /eac/excel`` and ``GET /eac/imprimivel`` are the two exports of the platform, with the
  same filters, so the file has what the screen shows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, database
from src.core.errors import DomainError, InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.export_document import (
    Document,
    ValueKind,
    describe_scope,
    format_value,
)
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import (
    Access,
    RequestContext,
    authorize,
    file_route,
    fragment_route,
)
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import export, service, validation
from src.modulos.financeiro.calculations import LEAF_LEVEL, TreeRow
from src.modulos.financeiro.service import EacFilters, EacView, ItemForm

bp = func.Blueprint()

CONTENT_ROUTE = "financeiro/eac"
FORM_ROUTE = "financeiro/eac/itens/{item_id}/editar"
SAVE_ROUTE = "financeiro/eac/itens/{item_id}"
EXCEL_ROUTE = "financeiro/eac/excel"
PRINTABLE_ROUTE = "financeiro/eac/imprimivel"

CONTENT_TEMPLATE = "financeiro/eac.html"
FORM_TEMPLATE = "financeiro/eac_form.html"
SAVED_TEMPLATE = "financeiro/eac_salvo.html"

FORM_TARGET = "eac-formulario"
CONTENT_TARGET = "eac-conteudo"
SAVED_MESSAGE = "Item {code} atualizado; alteração registrada no histórico."
NOTHING_CHANGED_MESSAGE = "Nenhum dado alterado."
ITEM_PARAMETER = "item_id"

# Reading the EAC is reading the module; the edit asks to write (a supplier reaches neither).
READ_ACCESS = Access(module=service.MODULE, permission=Permission.VIEW)
WRITE_ACCESS = Access(module=service.MODULE, permission=Permission.WRITE)


@dataclass(frozen=True)
class LineView:
    """A line of the tree as the table prints it: the row, its texts and where it can go."""

    row: TreeRow
    quantity: str
    unit_price: str
    budget: str
    weight: str
    classification: str
    has_children: bool
    edit_query: str
    can_edit: bool


# ── Tela ─────────────────────────────────────────────────────────────────


@bp.route(route=CONTENT_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eac_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The content of the EAC screen: the KPIs and the tree of the scope, filtered."""
    view = _view_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTENT_TEMPLATE, context=_content_context(view), request=req
    )


@bp.route(route=EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def eac_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the EAC: the download of the screen, with the same filters."""
    return excel_response(_document_of(req, session, context))


@bp.route(route=PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eac_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the EAC: what the PDF button mounts and prints."""
    return printable_response(_document_of(req, session, context), req)


# ── Cadastro do item ─────────────────────────────────────────────────────


@bp.route(route=FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eac_item_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The edit form of the cadastral data of an item, with its history."""
    form = service.item_form(
        session, user=context.user, scope=context.scope, item_id=_item_id_of(req)
    )
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context=_form_context(form, values={}, problems={}, filters=_filters_of(req.params)),
        request=req,
    )


def _render_form_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The form again, with what the person typed, when the save is refused with 422 or 409."""
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            form = service.item_form(
                session, user=context.user, scope=context.scope, item_id=_item_id_of(req)
            )
    except DomainError:
        return None
    problems = error.detail if isinstance(error, InvalidDataError) else {}
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context=_form_context(
            form,
            values=_posted(req.form),
            problems=problems if isinstance(problems, Mapping) else {},
            filters=_filters_of(req.form),
            message=str(error) if isinstance(error, VersionConflictError) else "",
        ),
        request=req,
        target_id=FORM_TARGET,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=SAVE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_form_error)
def eac_item_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the cadastral edit of an item and answer the screen again, the form closed."""
    item_id = _item_id_of(req)
    result = service.edit_item_registry(
        session, user=context.user, scope=context.scope, item_id=item_id, form=_posted(req.form)
    )
    view = service.eac_view(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.form),
        reference_date=calendario.today(),
    )
    code = next((row.code for row in view.full_rows if row.item_id == item_id), "")
    return AlpineAjaxResponse(
        template_name=SAVED_TEMPLATE,
        context=_content_context(view),
        request=req,
        toast=SAVED_MESSAGE.format(code=code) if result.changed_fields else NOTHING_CHANGED_MESSAGE,
        toast_tipo="ok" if result.changed_fields else "aviso",
    )


# ── Montagem ─────────────────────────────────────────────────────────────


def _view_of(req: func.HttpRequest, session: Session, context: RequestContext) -> EacView:
    """The EAC of the request; the only place of the reading routes that reads the clock."""
    return service.eac_view(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.params),
        reference_date=calendario.today(),
    )


def _document_of(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    view = _view_of(req, session, context)
    return export.eac_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _filters_of(source: Mapping[str, str | None]) -> EacFilters:
    """The filters of the tree from a query or a form: an unreadable level is the deepest."""
    raw_level = (source.get("nivel") or "").strip()
    cost_type = (source.get("tipo") or "").strip()
    return EacFilters(
        search=(source.get("busca") or "").strip(),
        level=int(raw_level) if raw_level.isdigit() else LEAF_LEVEL,
        cost_type=cost_type if cost_type in validation.COST_TYPES else "",
    )


def _item_id_of(req: func.HttpRequest) -> int:
    raw = req.route_params.get(ITEM_PARAMETER) or ""
    if not raw.isdigit():
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return int(raw)


def _posted(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_DESCRIPTION,
        validation.FIELD_COST_TYPE,
        validation.FIELD_CLASSIFICATION,
        validation.FIELD_COST_CENTER,
        validation.FIELD_RESPONSIBLE,
        validation.FIELD_JUSTIFICATION,
        validation.FIELD_VERSION,
    )
    return {name: form.get(name) for name in names}


def _content_context(view: EacView) -> dict[str, object]:
    filter_query = _filter_query(view.filters)
    return {
        "view": view,
        "linhas": [_line_view(view, row, filter_query) for row in view.rows],
        "resultado": _result_of(view),
        "orcamento": _money(view.summary.budget_cents),
        "total_filtrado": _money(view.filtered_total_cents),
        "tipos_de_custo": validation.COST_TYPES,
        "alvo_formulario": FORM_TARGET,
        "alvo_conteudo": CONTENT_TARGET,
    }


def _line_view(view: EacView, row: TreeRow, filter_query: str) -> LineView:
    return LineView(
        row=row,
        quantity=_decimal(row.quantity),
        unit_price=_money(row.unit_price_cents),
        budget=_money(row.budget_cents),
        weight=_percent(row.weight),
        classification=_classification(row),
        has_children=row.code in view.parents,
        edit_query=filter_query,
        can_edit=view.can_edit and row.item_id is not None and row.level >= LEAF_LEVEL,
    )


def _result_of(view: EacView) -> str:
    if view.is_empty:
        return "vazio-origem"
    return "vazio-filtro" if view.has_no_match else "conteudo"


def _money(cents: int | None) -> str:
    return "" if cents is None else format_value(ValueKind.MONEY, cents)


def _decimal(value: Decimal | None) -> str:
    return "" if value is None else format_value(ValueKind.DECIMAL, value)


def _percent(value: Decimal | None) -> str:
    return "" if value is None else format_value(ValueKind.PERCENT, value)


def _classification(row: TreeRow) -> str:
    if row.level < LEAF_LEVEL or row.capex is None:
        return ""
    return "CAPEX" if row.capex else "OPEX"


def _filter_query(filters: EacFilters) -> str:
    """The filters as a query string, so the edit form can bring them back to the screen."""
    pairs = {"busca": filters.search, "nivel": str(filters.level), "tipo": filters.cost_type}
    return urlencode({key: value for key, value in pairs.items() if value})


def _form_context(
    form: ItemForm,
    *,
    values: Mapping[str, str | None],
    problems: Mapping[str, str],
    filters: EacFilters,
    message: str = "",
) -> dict[str, object]:
    return {
        "formulario": form,
        "valores": values,
        "erros": problems,
        "mensagem": message,
        "filtros": filters,
        "tipos_de_custo": validation.COST_TYPES,
        "classificacoes": validation.CLASSIFICATIONS,
        "orcado": _money(form.row.budget_cents),
        "preco": _money(form.row.unit_price_cents),
        "quantidade": _decimal(form.row.quantity),
        "unidade": form.row.unit or "",
        "alvo_conteudo": CONTENT_TARGET,
    }
