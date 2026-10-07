"""Route blueprint of the Financeiro module (D14).

The EAC screen (ISSUE-029, ISSUE-030) and what hangs from it, all under ``/api/financeiro/eac``:

* ``GET /eac`` is the content of the screen (KPIs and tree) for the scope of the request, with the
  filters ``busca``, ``nivel`` and ``tipo``; in the Portfólio it is read-only;
* ``GET /eac/itens/{item_id}/editar`` is the cadastral edit form of an item, with its history;
* ``POST /eac/itens/{item_id}`` saves it: justification required, no SM, nothing of value;
* ``GET /eac/revisoes`` and ``GET /eac/remanejamentos`` are the two panels of the screen (the
  frozen baseline of each revision and the applied and pending transfers), in the Portfólio with
  a line per project;
* ``POST /eac/remanejamentos`` opens the SM of a reallocation (the value stays reserved in the
  origin until the decision); ``POST /eac/revisoes`` creates a revision from an approved SM with
  cost; ``POST /eac/itens`` creates a new item, financed by a reallocation or by a revision;
* ``GET /eac/revisoes/importar/formulario`` is the import form the modal of the screen opens;
  ``POST /eac/revisoes/importar/conferir`` and ``.../confirmar`` are the two steps of the import
  of new items by spreadsheet: the check reads and never writes (and answers the result with the
  two panels), and the confirmation checks again and creates the revision bound to the SM;
* ``GET /eac/excel`` and ``GET /eac/imprimivel`` are the two exports of the platform, with the
  same filters and the same tables the screen shows.

The map of ISSUE-031 lives under ``/api/financeiro/mapa-de-controle`` and ``/api/financeiro/custos``:

* ``GET /mapa-de-controle`` is the content of the map (KPIs and the lines of the scope) for one
  project or the Portfólio; ``GET /mapa-de-controle/excel`` and ``GET /mapa-de-controle/imprimivel``
  are its two exports, in full reais and with the ``Projeto`` column in the Portfólio;
* ``GET /mapa-de-controle/projecao/{item_id}/formulario`` is the projection form of an item and
  ``POST /mapa-de-controle/projecao/{item_id}`` saves it: justification required, the history of
  the item grows by one fact, and the refusal comes back in the form with 422;
* ``GET /custos/importar/formulario`` is the import form of the ERP closing; the check
  (``POST .../conferir``) reads and never writes and the confirmation (``POST .../confirmar``)
  checks the file again and writes one fact per item and month, replacing a reimported month.

The ficha do contrato of ISSUE-032 lives under ``/api/financeiro/contrato``, opened by the contract
number (``?numero=``): ``GET /contrato/resumo``, ``/contrato/medicoes`` and ``/contrato/aditivos``
are the content of each tab; ``GET /contrato/medicoes/nova``, ``/contrato/medicoes/{id}/devolucao``
and ``/contrato/aditivos/novo`` are the forms; ``POST /contrato/medicoes`` and
``POST /contrato/aditivos`` create the record; ``POST /contrato/medicoes/{id}/aprovar``,
``.../faturar``, ``.../pagar`` and ``.../devolver`` move the measurement through the flow; the
saved answers bring the panels again (a multi-target response, with the form emptied).
``GET /contrato/excel`` and ``GET /contrato/imprimivel`` are the two exports of the ficha.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario, database, importing, rbac
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.excel import excel_response
from src.core.export_document import (
    Document,
    ValueKind,
    describe_scope,
    format_value,
)
from src.core.import_values import normalize_text
from src.core.printable import printable_response
from src.core.rbac import Permission, User
from src.core.responses import AlpineAjaxResponse
from src.core.routing import (
    Access,
    RequestContext,
    authorize,
    file_route,
    fragment_route,
)
from src.core.scope import Scope
from src.core.spreadsheet_reader import MAX_DATA_ROWS, MAX_FILE_BYTES, MEGABYTE
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import calculations, export, importers, service, validation
from src.modulos.financeiro.calculations import LEAF_LEVEL, PORTFOLIO_MAIN_LEVEL, TreeRow
from src.modulos.financeiro.service import EacFilters, EacView, ItemForm

bp = func.Blueprint()

importers.register_importers()

CONTENT_ROUTE = "financeiro/eac"
FORM_ROUTE = "financeiro/eac/itens/{item_id}/editar"
SAVE_ROUTE = "financeiro/eac/itens/{item_id}"
REVISIONS_ROUTE = "financeiro/eac/revisoes"
REALLOCATIONS_ROUTE = "financeiro/eac/remanejamentos"
NEW_ITEM_ROUTE = "financeiro/eac/itens"
IMPORT_FORM_ROUTE = "financeiro/eac/revisoes/importar/formulario"
IMPORT_CHECK_ROUTE = "financeiro/eac/revisoes/importar/conferir"
IMPORT_CONFIRM_ROUTE = "financeiro/eac/revisoes/importar/confirmar"
EXCEL_ROUTE = "financeiro/eac/excel"
PRINTABLE_ROUTE = "financeiro/eac/imprimivel"

CONTENT_TEMPLATE = "financeiro/eac.html"
FORM_TEMPLATE = "financeiro/eac_form.html"
SAVED_TEMPLATE = "financeiro/eac_salvo.html"
REVISIONS_TEMPLATE = "financeiro/eac_revisoes.html"
REALLOCATIONS_TEMPLATE = "financeiro/eac_remanejamentos.html"
REVISION_SAVED_TEMPLATE = "financeiro/eac_revisao_salva.html"
REALLOCATION_SAVED_TEMPLATE = "financeiro/eac_remanejamento_salvo.html"
IMPORT_FORM_TEMPLATE = "financeiro/eac_importacao_form.html"
IMPORT_CHECK_TEMPLATE = "financeiro/eac_importacao_conferencia.html"

FORM_TARGET = "eac-formulario"
CONTENT_TARGET = "eac-conteudo"
REVISIONS_TARGET = "eac-revisoes"
REALLOCATIONS_TARGET = "eac-remanejamentos"
IMPORT_RESULT_TARGET = "eac-importacao-resultado"
SAVED_MESSAGE = "Item {code} atualizado; alteração registrada no histórico."
NOTHING_CHANGED_MESSAGE = "Nenhum dado alterado."
REALLOCATION_CREATED_MESSAGE = (
    "SM {code} registrada em Governança: o valor muda na EAC só depois da aprovação."
)
REVISION_CREATED_MESSAGE = "Rev {revision} criada: orçamento de {total}."
IMPORT_CONFIRMED_MESSAGE = "Rev {revision} criada: {items} ({total})."
IMPORT_ITEM = "1 item novo"
IMPORT_ITEMS = "{count} itens novos"
ITEM_PARAMETER = "item_id"

MAP_ROUTE = "financeiro/mapa-de-controle"
MAP_PROJECTION_FORM_ROUTE = "financeiro/mapa-de-controle/projecao/{item_id}/formulario"
MAP_PROJECTION_SAVE_ROUTE = "financeiro/mapa-de-controle/projecao/{item_id}"
MAP_EXCEL_ROUTE = "financeiro/mapa-de-controle/excel"
MAP_PRINTABLE_ROUTE = "financeiro/mapa-de-controle/imprimivel"
ERP_IMPORT_FORM_ROUTE = "financeiro/custos/importar/formulario"
ERP_IMPORT_CHECK_ROUTE = "financeiro/custos/importar/conferir"
ERP_IMPORT_CONFIRM_ROUTE = "financeiro/custos/importar/confirmar"

MAP_TEMPLATE = "financeiro/mapa_controle.html"
MAP_PROJECTION_FORM_TEMPLATE = "financeiro/mapa_projecao_form.html"
MAP_PROJECTION_SAVED_TEMPLATE = "financeiro/mapa_projecao_salvo.html"
ERP_IMPORT_FORM_TEMPLATE = "financeiro/custos_importacao_form.html"
ERP_IMPORT_CHECK_TEMPLATE = "financeiro/custos_importacao_conferencia.html"
ERP_IMPORT_RESULT_TEMPLATE = "financeiro/custos_importacao_resultado.html"

MAP_TARGET = "mapa-conteudo"
PROJECTION_FORM_TARGET = "mapa-projecao-formulario"

CONTRACT_CONTENT_BASE = "financeiro/contrato"
CONTRACT_RESUME_ROUTE = f"{CONTRACT_CONTENT_BASE}/resumo"
CONTRACT_MEASUREMENTS_ROUTE = f"{CONTRACT_CONTENT_BASE}/medicoes"
CONTRACT_ADDENDA_ROUTE = f"{CONTRACT_CONTENT_BASE}/aditivos"
CONTRACT_MEASUREMENT_FORM_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/nova"
CONTRACT_MEASUREMENT_CREATE_ROUTE = CONTRACT_MEASUREMENTS_ROUTE
CONTRACT_MEASUREMENT_APPROVE_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/aprovar"
CONTRACT_MEASUREMENT_INVOICE_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/faturar"
CONTRACT_MEASUREMENT_PAY_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/pagar"
CONTRACT_MEASUREMENT_RETURN_FORM_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/devolucao"
CONTRACT_MEASUREMENT_RETURN_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/devolver"
CONTRACT_ADDENDUM_FORM_ROUTE = f"{CONTRACT_ADDENDA_ROUTE}/novo"
CONTRACT_ADDENDUM_CREATE_ROUTE = CONTRACT_ADDENDA_ROUTE
CONTRACT_EXCEL_ROUTE = f"{CONTRACT_CONTENT_BASE}/excel"
CONTRACT_PRINTABLE_ROUTE = f"{CONTRACT_CONTENT_BASE}/imprimivel"

CONTRACT_RESUME_TEMPLATE = "financeiro/contrato_resumo.html"
CONTRACT_MEASUREMENTS_TEMPLATE = "financeiro/contrato_medicoes.html"
CONTRACT_ADDENDA_TEMPLATE = "financeiro/contrato_aditivos.html"
CONTRACT_SAVED_TEMPLATE = "financeiro/contrato_salvo.html"
CONTRACT_MEASUREMENT_FORM_TEMPLATE = "financeiro/contrato_medicao_form.html"
CONTRACT_MEASUREMENT_RETURN_TEMPLATE = "financeiro/contrato_medicao_devolucao.html"
CONTRACT_ADDENDUM_FORM_TEMPLATE = "financeiro/contrato_aditivo_form.html"

CONTRACT_RESUME_TARGET = "contrato-resumo"
CONTRACT_MEASUREMENTS_TARGET = "contrato-medicoes"
CONTRACT_ADDENDA_TARGET = "contrato-aditivos"
CONTRACT_FORM_TARGET = "contrato-formulario"

CONTRACT_NUMBER_PARAMETER = "numero"
CONTRACT_MEASUREMENT_PARAMETER = "medicao_id"

CONTRACT_MEASUREMENT_CREATED_MESSAGE = "Medição {number} registrada em análise."
CONTRACT_MEASUREMENT_MOVED_MESSAGE = "Medição {number}: {situation}."
CONTRACT_MEASUREMENT_RETURNED_MESSAGE = "Medição {number} devolvida à contratada."
CONTRACT_ADDENDUM_CREATED_MESSAGE = "Aditivo {number} registrado."
CONTRACT_ADDENDUM_EXTENDED_SUFFIX = " Término vigente prorrogado em {days} dias."

_SITUATION_PILLS = {
    calculations.SITUATION_UNDER_REVIEW: "warn",
    calculations.SITUATION_APPROVED: "fix",
    calculations.SITUATION_INVOICED: "fix",
    calculations.SITUATION_PAID: "ok",
    calculations.SITUATION_RETURNED: "erro",
}

MIL_CENTS = 100_000
MIL_ONE_PLACE = Decimal("0.1")
MAP_TITLE_PROJECT = "Mapa de controle da EAC"
MAP_TITLE_PORTFOLIO = "Mapa de controle da carteira"
MAP_ITEM_ROW_LABEL = "Código"
MAP_PROJECT_ROW_LABEL = "Projeto"
MAP_DESCRIPTION_ID = "descricao"
MAP_PERCENT_ID = "desvio_pct"
MAP_MONEY_COLUMNS: tuple[tuple[str, str, bool, str], ...] = (
    ("orcado", "Orçado", False, "baseline_cents"),
    ("remanejamentos", "Remanejamentos", True, "reallocation_cents"),
    ("atual", "Orçado atual", False, "current_cents"),
    ("comprometido", "Comprometido", False, "committed_cents"),
    ("realizado", "Realizado", False, "actual_cents"),
    ("saldo", "Saldo a comprometer", False, "saldo_cents"),
    ("projecao", "Projeção no término", False, "projection_cents"),
    ("desvio", "Desvio", True, "deviation_cents"),
)

PROJECTION_SAVED_MESSAGE = "Projeção de {code} atualizada."
PROJECTION_PORTFOLIO_MESSAGE = (
    "A projeção no término é de um item de um projeto. Abra o projeto para atualizá-la."
)
ERP_IMPORTED_MESSAGE = "{count} itens atualizados no mapa de controle."
ERP_IMPORTED_ONE_MESSAGE = "1 item atualizado no mapa de controle."
ERP_SKIPPED_SUFFIX = " {count} com erro não entraram."

# Reading the EAC is reading the module; the edit asks to write (a supplier reaches neither).
READ_ACCESS = Access(module=service.MODULE, permission=Permission.VIEW)
WRITE_ACCESS = Access(module=service.MODULE, permission=Permission.WRITE)

# The kinds of column the import preview aligns to the right.
_NUMERIC_KINDS = frozenset(
    {ValueKind.INTEGER, ValueKind.DECIMAL, ValueKind.PERCENT, ValueKind.MONEY}
)


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
    project_ids = _project_ids(session, context.scope)
    return export.eac_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
        revisions=service.revision_rows(session, project_ids=project_ids),
        reallocations=service.reallocation_rows(session, project_ids=project_ids),
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


# ── Revisões e remanejamentos (ISSUE-030) ────────────────────────────────


def _render_revision_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The panels again, with the refusal at the top of the revisions table."""
    return _render_panel_error(req, error, template=REVISION_SAVED_TEMPLATE)


def _render_reallocation_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """The panels again, with the refusal at the top of the reallocations table."""
    return _render_panel_error(req, error, template=REALLOCATION_SAVED_TEMPLATE)


def _render_new_item_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The panels again, with the refusal in the table of the recourse the person chose."""
    recourse = req.form.get(validation.FIELD_NEW_ITEM_RECOURSE) or validation.RECOURSE_REALLOCATION
    template = (
        REVISION_SAVED_TEMPLATE
        if recourse == validation.RECOURSE_REVISION
        else REALLOCATION_SAVED_TEMPLATE
    )
    return _render_panel_error(req, error, template=template)


@bp.route(route=REVISIONS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eac_revisions(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The revisions of the scope: the frozen baseline of each one, with the variation."""
    return AlpineAjaxResponse(
        template_name=REVISIONS_TEMPLATE,
        context=_revisions_context(
            session, context.scope, user=context.user, filters=_filters_of(req.params)
        ),
        request=req,
    )


@bp.route(route=REALLOCATIONS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eac_reallocations(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The reallocations of the scope: applied and pending, with the free balance of the origin."""
    return AlpineAjaxResponse(
        template_name=REALLOCATIONS_TEMPLATE,
        context=_reallocations_context(
            session, context.scope, user=context.user, filters=_filters_of(req.params)
        ),
        request=req,
    )


@bp.route(route=REALLOCATIONS_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_reallocation_error)
def eac_reallocate(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Open the SM of a budget reallocation, as the EAC screen asks; the value stays reserved."""
    form = validation.parse_reallocation_form(req.form)
    created = service.reallocate(
        session,
        user=context.user,
        scope=context.scope,
        request=_reallocation_request(form),
        reference_date=calendario.today(),
    )
    return _reallocation_saved(req, session, context, created)


@bp.route(route=REVISIONS_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_revision_error)
def eac_create_revision(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the revision of the EAC from an approved SM with cost (Gestor)."""
    form = validation.parse_revision_form(req.form)
    revision = service.create_revision(
        session,
        user=context.user,
        scope=context.scope,
        request=service.RevisionRequest(
            change_id=form.change_id,
            justification=form.justification,
            adjustments=(
                service.AdjustmentRequest(code=form.item_code, delta_cents=form.delta_cents),
            ),
        ),
        reference_date=calendario.today(),
    )
    return _revision_saved(req, session, context, revision)


@bp.route(route=NEW_ITEM_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_new_item_error)
def eac_new_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create an item of the EAC: by a reallocation SM or by a revision from an approved SM."""
    project_id = context.scope.require_project()
    form = validation.parse_new_item_form(
        req.form,
        parent_codes=_parent_codes(session, project_id),
        unit_codes={unit.code for unit in configuracoes.list_measure_units(session)},
        responsible_names={person.name for person in configuracoes.list_people(session)},
    )
    reference_date = calendario.today()
    if form.recourse == validation.RECOURSE_REVISION:
        revision = service.create_revision(
            session,
            user=context.user,
            scope=context.scope,
            request=service.RevisionRequest(
                change_id=form.change_id or 0,
                justification=form.justification,
                new_items=(_revision_item_of(form.item, session=session, project_id=project_id),),
            ),
            reference_date=reference_date,
        )
        return _revision_saved(req, session, context, revision)
    created = service.reallocate(
        session,
        user=context.user,
        scope=context.scope,
        request=_new_item_reallocation(form, session=session, project_id=project_id),
        reference_date=reference_date,
    )
    return _reallocation_saved(req, session, context, created)


@bp.route(route=IMPORT_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eac_import_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the import of items, opened in the modal of the EAC screen."""
    project_id = context.scope.require_project()
    return AlpineAjaxResponse(
        template_name=IMPORT_FORM_TEMPLATE,
        context={
            "fontes": service.revision_source_options(session, project_id=project_id),
            "filtros": _filters_of(req.params),
            "campo_arquivo": attachments.FILE_FIELD,
            "limite_mb": MAX_FILE_BYTES // MEGABYTE,
            "limite_linhas": MAX_DATA_ROWS,
        },
        request=req,
    )


@bp.route(route=IMPORT_CHECK_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eac_import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Read the spreadsheet of new items and answer what each line will do; nothing is written."""
    context.scope.require_project()
    preview = importing.check(
        session,
        importer=importers.eac_items_importer(),
        upload=_upload_of(req),
        context=_import_context(context),
    )
    data = _check_context(preview)
    data |= _panels_context(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.form),
    )
    data |= {
        "alvo_importacao": IMPORT_RESULT_TARGET,
        "alvo_revisoes": REVISIONS_TARGET,
        "alvo_conteudo": CONTENT_TARGET,
    }
    return AlpineAjaxResponse(template_name=IMPORT_CHECK_TEMPLATE, context=data, request=req)


@bp.route(route=IMPORT_CONFIRM_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eac_import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Check the file again and create the revision with the writable lines, all or none."""
    project_id = context.scope.require_project()
    upload = _upload_of(req)
    preview = importing.check(
        session,
        importer=importers.eac_items_importer(),
        upload=upload,
        context=_import_context(context),
    )
    _require_importable(upload, preview, req.form)
    form = validation.parse_revision_form(req.form, require_adjustment=False)
    revision = service.create_revision(
        session,
        user=context.user,
        scope=context.scope,
        request=service.RevisionRequest(
            change_id=form.change_id,
            justification=form.justification,
            new_items=importers.revision_items(
                session, project_id=project_id, rows=preview.writable_rows
            ),
        ),
        reference_date=calendario.today(),
    )
    count = len(preview.writable_rows)
    items = IMPORT_ITEM if count == 1 else IMPORT_ITEMS.format(count=count)
    return _revision_saved(
        req,
        session,
        context,
        revision,
        toast=IMPORT_CONFIRMED_MESSAGE.format(
            revision=revision.revision, items=items, total=_money(revision.total_cents)
        ),
    )


# ── Montagem das respostas ───────────────────────────────────────────────


def _project_ids(session: Session, scope: Scope) -> tuple[int, ...]:
    """The projects of the scope: the chosen one, or every project in the Portfólio."""
    if not scope.is_portfolio:
        return (scope.require_project(),)
    return tuple(project.id for project in configuracoes.list_projects(session))


def _revisions_context(
    session: Session,
    scope: Scope,
    *,
    user: User,
    filters: EacFilters,
    erro: str = "",
) -> dict[str, object]:
    project_id = None if scope.is_portfolio else scope.require_project()
    return {
        "revisoes": service.revision_rows(session, project_ids=_project_ids(session, scope)),
        "carteira": scope.is_portfolio,
        "erro": erro,
        "filtros": filters,
        "pode_gravar": project_id is not None and rbac.can(user, Permission.WRITE),
        "proxima_revisao": (
            service.next_revision(session, project_id=project_id) if project_id else 0
        ),
        "itens": service.item_options(session, project_id=project_id) if project_id else (),
        "fontes": (
            service.revision_source_options(session, project_id=project_id) if project_id else ()
        ),
    }


def _reallocations_context(
    session: Session,
    scope: Scope,
    *,
    user: User,
    filters: EacFilters,
    erro: str = "",
) -> dict[str, object]:
    project_id = None if scope.is_portfolio else scope.require_project()
    return {
        "remanejamentos": service.reallocation_rows(
            session, project_ids=_project_ids(session, scope)
        ),
        "carteira": scope.is_portfolio,
        "erro": erro,
        "filtros": filters,
        "pode_gravar": project_id is not None and rbac.can(user, Permission.WRITE),
        "itens": service.item_options(session, project_id=project_id) if project_id else (),
        "subpacotes": (
            service.subpackage_options(session, project_id=project_id) if project_id else ()
        ),
        "fontes": (
            service.revision_source_options(session, project_id=project_id) if project_id else ()
        ),
        "unidades": configuracoes.list_measure_units(session) if project_id else (),
        "pessoas": configuracoes.list_people(session) if project_id else (),
        "tipos_de_custo": validation.COST_TYPES,
        "classificacoes": validation.CLASSIFICATIONS,
        "prioridades": validation.PRIORITIES,
    }


def _panels_context(
    session: Session, *, user: User, scope: Scope, filters: EacFilters, erro: str = ""
) -> dict[str, object]:
    view = service.eac_view(
        session, user=user, scope=scope, filters=filters, reference_date=calendario.today()
    )
    data = _content_context(view)
    data |= _revisions_context(session, scope, user=user, filters=filters, erro=erro)
    data |= _reallocations_context(session, scope, user=user, filters=filters, erro=erro)
    data |= {"alvo_revisoes": REVISIONS_TARGET, "alvo_remanejamentos": REALLOCATIONS_TARGET}
    return data


def _reallocation_request(form: validation.ReallocationForm) -> service.ReallocationRequest:
    return service.ReallocationRequest(
        title=form.title,
        justification=form.justification,
        priority=form.priority,
        transfers=(
            service.TransferRequest(
                source_code=form.origin_code,
                target_code=form.target_code,
                value_cents=form.value_cents,
            ),
        ),
    )


def _new_item_reallocation(
    form: validation.NewItemForm, *, session: Session, project_id: int
) -> service.ReallocationRequest:
    return service.ReallocationRequest(
        justification=form.justification,
        priority=form.priority,
        transfers=(
            service.TransferRequest(
                source_code=form.origin_code,
                target_code=form.item.code,
                value_cents=form.item.budget_cents,
                new_item=_new_item_request(form.item, session=session, project_id=project_id),
            ),
        ),
    )


def _new_item_request(
    item: validation.NewItemInput, *, session: Session, project_id: int
) -> service.NewItemRequest:
    parents = service.eac_item_ids_by_code(session, project_id=project_id, codes=[item.parent_code])
    units = {
        normalize_text(unit.code): unit.id for unit in configuracoes.list_measure_units(session)
    }
    people = {
        normalize_text(person.name): person.id for person in configuracoes.list_people(session)
    }
    return service.NewItemRequest(
        code=item.code,
        description=item.description,
        parent_id=parents.get(item.parent_code),
        unit_id=units.get(normalize_text(item.unit_code)),
        cost_type=item.cost_type,
        capex=item.capex,
        cost_center=item.cost_center,
        responsible_id=people.get(normalize_text(item.responsible_name)),
        quantity=item.quantity,
        unit_price_cents=item.unit_price_cents,
    )


def _revision_item_of(
    item: validation.NewItemInput, *, session: Session, project_id: int
) -> service.RevisionItemRequest:
    request = _new_item_request(item, session=session, project_id=project_id)
    return service.RevisionItemRequest(
        code=request.code,
        description=request.description,
        base_cents=item.budget_cents,
        parent_id=request.parent_id,
        unit_id=request.unit_id,
        cost_type=request.cost_type,
        capex=request.capex,
        cost_center=request.cost_center,
        responsible_id=request.responsible_id,
        quantity=request.quantity,
        unit_price_cents=request.unit_price_cents,
    )


def _parent_codes(session: Session, project_id: int) -> set[str]:
    """The subpackages (level 2) of the project: where a new item can be born."""
    levels = service.eac_item_levels(session, project_id=project_id)
    return {code for code, level in levels.items() if level == PORTFOLIO_MAIN_LEVEL}


def _reallocation_saved(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    created: service.CreatedReallocation,
) -> func.HttpResponse:
    data = _panels_context(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.form),
    )
    return AlpineAjaxResponse(
        template_name=REALLOCATION_SAVED_TEMPLATE,
        context=data,
        request=req,
        toast=REALLOCATION_CREATED_MESSAGE.format(code=created.code),
        toast_tipo="ok",
    )


def _revision_saved(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    revision: service.RevisionView,
    *,
    toast: str | None = None,
) -> func.HttpResponse:
    data = _panels_context(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.form),
    )
    return AlpineAjaxResponse(
        template_name=REVISION_SAVED_TEMPLATE,
        context=data,
        request=req,
        toast=toast
        or REVISION_CREATED_MESSAGE.format(
            revision=revision.revision, total=_money(revision.total_cents)
        ),
        toast_tipo="ok",
    )


def _render_panel_error(
    req: func.HttpRequest, error: DomainError, *, template: str
) -> func.HttpResponse | None:
    """The panels again, with the refusal at the top of the one the person was editing."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            data = _panels_context(
                session,
                user=context.user,
                scope=context.scope,
                filters=_filters_of(req.form),
                erro=str(error),
            )
    except DomainError:
        return None
    return AlpineAjaxResponse(
        template_name=template,
        context=data,
        request=req,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


# ── Importação dos itens (ISSUE-030) ─────────────────────────────────────


def _import_context(context: RequestContext) -> importing.ImportContext:
    return importing.ImportContext(
        user=context.user, scope=context.scope, reference_date=calendario.today()
    )


def _upload_of(req: func.HttpRequest) -> importing.Upload:
    """The file of the form; at most one byte over the limit is read."""
    sent = req.files.get(attachments.FILE_FIELD)
    if sent is None:
        return importing.Upload(name=None, content=b"")
    return importing.Upload(name=sent.filename, content=sent.stream.read(MAX_FILE_BYTES + 1))


def _require_importable(
    upload: importing.Upload, preview: importing.ImportPreview, form: Mapping[str, str | None]
) -> None:
    """The guards of the generic confirmation, before the revision is written."""
    digest = (form.get(validation.FIELD_IMPORT_CHECKED) or "").strip()
    if not digest:
        raise InvalidDataError(importing.NOT_CHECKED_MESSAGE)
    if digest != importing.digest_of(upload):
        raise InvalidDataError(importing.CHANGED_MESSAGE)
    if preview.missing:
        raise InvalidDataError(importing.MISSING_MESSAGE.format(columns=", ".join(preview.missing)))
    if not preview.writable_rows:
        raise InvalidDataError(importing.NOTHING_MESSAGE)
    acknowledged = form.get(validation.FIELD_IMPORT_ACKNOWLEDGED)
    if preview.error_rows and acknowledged != validation.IMPORT_ACKNOWLEDGED_VALUE:
        raise InvalidDataError(importing.NOT_ACKNOWLEDGED_MESSAGE)


def _check_context(preview: importing.ImportPreview) -> dict[str, object]:
    return {
        "arquivo": preview.file_name,
        "preview": preview,
        "colunas": [
            {"cabecalho": column.header, "numerica": column.kind in _NUMERIC_KINDS}
            for column in preview.columns
        ],
        "lidas": len(preview.rows),
        "vao_gravar": len(preview.writable_rows),
        "com_aviso": len(preview.warning_rows),
        "com_erro": len(preview.error_rows),
        "campo_conferido": validation.FIELD_IMPORT_CHECKED,
        "campo_ciente": validation.FIELD_IMPORT_ACKNOWLEDGED,
        "valor_ciente": validation.IMPORT_ACKNOWLEDGED_VALUE,
        "confirmar_url": f"/api/{IMPORT_CONFIRM_ROUTE}",
    }


# ── Mapa de controle, projeção e custos do ERP (ISSUE-031) ───────────────


@dataclass(frozen=True)
class MapaLineView:
    """Uma linha do mapa como os fragmentos a imprimem: a linha e o texto de cada coluna."""

    row: service.MapaRow
    baseline: str
    reallocation: str
    current: str
    committed: str
    actual: str
    saldo: str
    projection: str
    deviation: str
    deviation_percent: str
    can_project: bool


@dataclass(frozen=True)
class ProjectionFormView:
    """O formulário da projeção no término: a linha do item e os valores vigentes."""

    row: service.MapaRow
    current: str
    committed: str
    actual: str
    projection: str


@bp.route(route=MAP_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def mapa_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O mapa de controle do escopo: item a item no projeto, um registro por projeto na carteira."""
    return AlpineAjaxResponse(
        template_name=MAP_TEMPLATE, context=_mapa_context(session, context), request=req
    )


@bp.route(route=MAP_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def mapa_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do mapa de controle: as colunas da tela em R$ integral; no Portfólio com Projeto."""
    del req
    return excel_response(_mapa_document_of(session, context))


@bp.route(route=MAP_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def mapa_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do mapa de controle: o mesmo documento que o Excel imprime."""
    return printable_response(_mapa_document_of(session, context), req)


@bp.route(route=MAP_PROJECTION_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def mapa_projection_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da projeção no término de um item, com os valores vigentes do mapa."""
    row = _projection_row(session, context, _item_id_of(req))
    return AlpineAjaxResponse(
        template_name=MAP_PROJECTION_FORM_TEMPLATE,
        context=_projection_context(row, values={}, problems={}),
        request=req,
    )


def _render_projection_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """O formulário da projeção de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            row = _projection_row(session, context, _item_id_of(req))
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=MAP_PROJECTION_FORM_TEMPLATE,
        context=_projection_context(row, values=_posted_projection(req.form), problems=problems),
        request=req,
        target_id=PROJECTION_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=MAP_PROJECTION_SAVE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_projection_error)
def mapa_projection_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Atualiza a projeção no término do item: justificativa obrigatória e fato no histórico."""
    item_id = _item_id_of(req)
    row = _projection_row(session, context, item_id)
    form = validation.parse_projection_form(req.form)
    service.update_projection(
        session,
        item_id=item_id,
        valor_centavos=form.value_cents,
        justificativa=form.justification,
        autor_id=context.user.person_id,
        hoje=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=MAP_PROJECTION_SAVED_TEMPLATE,
        context=_mapa_context(session, context),
        request=req,
        toast=PROJECTION_SAVED_MESSAGE.format(code=row.code),
        toast_tipo="ok",
    )


@bp.route(route=ERP_IMPORT_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def erp_import_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da importação dos custos do ERP, aberto no modal do mapa de controle."""
    del session
    context.scope.require_project()
    return AlpineAjaxResponse(
        template_name=ERP_IMPORT_FORM_TEMPLATE,
        context={
            "campo_arquivo": attachments.FILE_FIELD,
            "limite_mb": MAX_FILE_BYTES // MEGABYTE,
            "limite_linhas": MAX_DATA_ROWS,
        },
        request=req,
    )


@bp.route(route=ERP_IMPORT_CHECK_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def erp_import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Lê a planilha do fechamento e responde o que cada linha vai gravar; nada é escrito."""
    context.scope.require_project()
    preview = importing.check(
        session,
        importer=importers.erp_costs_importer(),
        upload=_upload_of(req),
        context=_import_context(context),
    )
    data = _erp_check_context(preview)
    data |= _mapa_context(session, context)
    return AlpineAjaxResponse(template_name=ERP_IMPORT_CHECK_TEMPLATE, context=data, request=req)


@bp.route(route=ERP_IMPORT_CONFIRM_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def erp_import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Checa a planilha de novo e grava o fechamento do mês por item e mês: só na confirmação."""
    context.scope.require_project()
    importer = importers.erp_costs_importer()
    result = importing.confirm(
        session,
        importer=importer,
        upload=_upload_of(req),
        context=_import_context(context),
        confirmation=importing.Confirmation(
            checked_digest=(req.form.get(validation.FIELD_IMPORT_CHECKED) or "").strip() or None,
            acknowledged=req.form.get(validation.FIELD_IMPORT_ACKNOWLEDGED)
            == validation.IMPORT_ACKNOWLEDGED_VALUE,
        ),
    )
    data: dict[str, object] = {
        "resultado": result,
        "importador": importer.title,
        "alvo_conteudo": MAP_TARGET,
    }
    data |= _mapa_context(session, context)
    return AlpineAjaxResponse(
        template_name=ERP_IMPORT_RESULT_TEMPLATE,
        context=data,
        request=req,
        toast=_erp_imported_notice(result),
        toast_tipo="aviso" if result.skipped else "ok",
    )


def _projection_row(session: Session, context: RequestContext, item_id: int) -> service.MapaRow:
    """A linha do item no mapa do escopo; no Portfólio ou fora do item do projeto, a rota recusa."""
    if context.scope.is_portfolio:
        raise AccessDeniedError(PROJECTION_PORTFOLIO_MESSAGE)
    view = service.mapa_controle(session, scope=context.scope, reference_date=calendario.today())
    row = next((line for line in view.rows if line.item_id == item_id), None)
    if row is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return row


def _projection_context(
    row: service.MapaRow, *, values: Mapping[str, str | None], problems: Mapping[str, str]
) -> dict[str, object]:
    return {
        "formulario": ProjectionFormView(
            row=row,
            current=_money(row.current_cents),
            committed=_money(row.committed_cents),
            actual=_money(row.actual_cents),
            projection=_money(row.projection_cents),
        ),
        "valores": values,
        "erros": problems,
        "alvo_conteudo": MAP_TARGET,
    }


def _posted_projection(form: Mapping[str, str | None]) -> dict[str, str | None]:
    return {
        validation.FIELD_PROJECTION: form.get(validation.FIELD_PROJECTION),
        validation.FIELD_JUSTIFICATION: form.get(validation.FIELD_JUSTIFICATION),
    }


def _mapa_document_of(session: Session, context: RequestContext) -> Document:
    view = service.mapa_controle(session, scope=context.scope, reference_date=calendario.today())
    return export.mapa_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _mapa_context(
    session: Session, context: RequestContext, *, erro: str = ""
) -> dict[str, object]:
    view = service.mapa_controle(session, scope=context.scope, reference_date=calendario.today())
    pode_gravar = not view.is_portfolio and rbac.can(context.user, Permission.WRITE)
    return {
        "mapa": view,
        "linhas": [_mapa_line(line, pode_gravar=pode_gravar) for line in view.rows],
        "total": _mapa_line(view.total, pode_gravar=False),
        "carteira": view.is_portfolio,
        "pode_gravar": pode_gravar,
        "resultado": "conteudo" if view.rows else "vazio-origem",
        "grafico": _mapa_grafico(view, pode_gravar=pode_gravar),
        "alvo_conteudo": MAP_TARGET,
        "alvo_formulario": PROJECTION_FORM_TARGET,
        "erro": erro,
    }


def _mapa_line(row: service.MapaRow, *, pode_gravar: bool) -> MapaLineView:
    return MapaLineView(
        row=row,
        baseline=_money(row.baseline_cents),
        reallocation=_delta_money(row.reallocation_cents),
        current=_money(row.current_cents),
        committed=_money(row.committed_cents),
        actual=_money(row.actual_cents),
        saldo=_money(row.saldo_cents),
        projection=_money(row.projection_cents),
        deviation=_signed_money(row.deviation_cents),
        deviation_percent=_percent(row.deviation_percent),
        can_project=pode_gravar and row.level >= LEAF_LEVEL and row.item_id is not None,
    )


def _mil(cents: int) -> float:
    """O valor em R$ mil, com uma casa, como a grade do mapa mostra (a exportação é integral)."""
    return float((Decimal(cents) / MIL_CENTS).quantize(MIL_ONE_PLACE, rounding=ROUND_HALF_UP))


def _mapa_grafico(view: service.MapaControleView, *, pode_gravar: bool) -> dict[str, object]:
    """O mapa no contrato do visual Tabela Heatmap (D11): R$ mil e o desvio pintado pelas faixas.

    As faixas são as dos parâmetros vigentes e chegam prontas no JSON; a coluna do desvio
    percentual é a única pintada, e o valor de cada item mostra o sinal e o ícone da faixa,
    nunca só a cor. Com escrita, a célula do desvio do item carrega o id que abre a projeção.
    """
    faixas = list(calculations.deviation_heatmap_faixas(view.bands))
    return {
        "titulo": MAP_TITLE_PORTFOLIO if view.is_portfolio else MAP_TITLE_PROJECT,
        "rotulo_linhas": MAP_PROJECT_ROW_LABEL if view.is_portfolio else MAP_ITEM_ROW_LABEL,
        "cabecalho": "horizontal",
        "casas": 1,
        "colunas": _mapa_grafico_colunas(view.total, carteira=view.is_portfolio),
        "linhas": [
            _mapa_grafico_linha(row, carteira=view.is_portfolio, pode_gravar=pode_gravar)
            for row in view.rows
        ],
        "total": {"linha": view.total.description, "coluna": False},
        "faixas": {"padrao": faixas, "total": faixas},
    }


def _mapa_grafico_colunas(total: service.MapaRow, *, carteira: bool) -> list[dict[str, object]]:
    colunas: list[dict[str, object]] = []
    if not carteira:
        colunas.append({"id": MAP_DESCRIPTION_ID, "rotulo": "Descrição", "calor": False})
    colunas.extend(
        {
            "id": coluna,
            "rotulo": rotulo,
            "calor": False,
            "casas": 1,
            "sinal": sinal,
            "total": _mil(getattr(total, campo)),
        }
        for coluna, rotulo, sinal, campo in MAP_MONEY_COLUMNS
    )
    colunas.append(_mapa_grafico_coluna_percentual(total.deviation_percent))
    return colunas


def _mapa_grafico_coluna_percentual(percent: Decimal | None) -> dict[str, object]:
    coluna: dict[str, object] = {
        "id": MAP_PERCENT_ID,
        "rotulo": "Desvio %",
        "casas": 1,
        "unidade": "%",
        "sinal": True,
        "somar": False,
    }
    if percent is not None:
        coluna["total"] = float(percent)
    return coluna


def _mapa_grafico_linha(
    row: service.MapaRow, *, carteira: bool, pode_gravar: bool
) -> dict[str, object]:
    valores: dict[str, object] = {
        coluna: _mil(getattr(row, campo)) for coluna, _rotulo, _sinal, campo in MAP_MONEY_COLUMNS
    }
    if not carteira:
        valores[MAP_DESCRIPTION_ID] = {"texto": row.description}
    valores[MAP_PERCENT_ID] = _mapa_grafico_celula_percentual(row, pode_gravar=pode_gravar)
    return {
        "id": row.code,
        "rotulo": row.project_label if carteira else row.code,
        "valores": valores,
    }


def _mapa_grafico_celula_percentual(row: service.MapaRow, *, pode_gravar: bool) -> object:
    percent = row.deviation_percent
    if percent is None:
        return None
    if pode_gravar and row.level >= LEAF_LEVEL and row.item_id is not None:
        return {"valor": float(percent), "selecionavel": True, "id": row.item_id}
    return float(percent)


def _signed_money(cents: int) -> str:
    return f"+{_money(cents)}" if cents > 0 else _money(cents)


def _delta_money(cents: int) -> str:
    return "" if cents == 0 else _signed_money(cents)


def _erp_check_context(preview: importing.ImportPreview) -> dict[str, object]:
    return {
        "arquivo": preview.file_name,
        "preview": preview,
        "colunas": [
            {"cabecalho": column.header, "numerica": column.kind in _NUMERIC_KINDS}
            for column in preview.columns
        ],
        "lidas": len(preview.rows),
        "vao_gravar": len(preview.writable_rows),
        "com_aviso": len(preview.warning_rows),
        "com_erro": len(preview.error_rows),
        "campo_conferido": validation.FIELD_IMPORT_CHECKED,
        "campo_ciente": validation.FIELD_IMPORT_ACKNOWLEDGED,
        "valor_ciente": validation.IMPORT_ACKNOWLEDGED_VALUE,
        "confirmar_url": f"/api/{ERP_IMPORT_CONFIRM_ROUTE}",
        "alvo_conteudo": MAP_TARGET,
    }


def _erp_imported_notice(result: importing.ImportResult) -> str:
    written = len(result.written)
    notice = (
        ERP_IMPORTED_ONE_MESSAGE if written == 1 else ERP_IMPORTED_MESSAGE.format(count=written)
    )
    if result.skipped:
        return notice + ERP_SKIPPED_SUFFIX.format(count=len(result.skipped))
    return notice


# ── Ficha do contrato: medições e aditivos (ISSUE-032) ───────────────────


@dataclass(frozen=True)
class MedicaoLineView:
    """Uma medição como a tabela a imprime: os textos prontos e as transições que a situação admite."""

    medicao: service.MeasurementView
    periodo: str
    bruto: str
    retencao: str
    liquido: str
    situacao_tom: str
    pode_aprovar: bool
    pode_faturar: bool
    pode_pagar: bool
    pode_devolver: bool


@bp.route(route=CONTRACT_RESUME_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_resumo(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Resumo da ficha: os KPIs, a cascata do valor e os dados do contrato."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_RESUME_TEMPLATE,
        context=_contrato_resumo_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_MEASUREMENTS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_medicoes(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """As medições da ficha, da mais recente para a mais antiga, com as transições do fluxo."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENTS_TEMPLATE,
        context=_contrato_medicoes_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_ADDENDA_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_aditivos(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Os aditivos da ficha, do mais recente para o mais antigo."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_ADDENDA_TEMPLATE,
        context=_contrato_aditivos_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def contrato_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da ficha: o Resumo com os KPIs e as tabelas de medições e aditivos."""
    return excel_response(_contrato_document_of(req, session, context))


@bp.route(route=CONTRACT_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da ficha: o mesmo documento do Excel, com a cascata desenhada."""
    return printable_response(_contrato_document_of(req, session, context), req)


@bp.route(route=CONTRACT_MEASUREMENT_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_medicao_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da medição nova, com o saldo disponível do contrato."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENT_FORM_TEMPLATE,
        context=_contrato_medicao_form_context(view, values={}, problems={}),
        request=req,
    )


def _render_medicao_form_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """O formulário da medição de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENT_FORM_TEMPLATE,
        context=_contrato_medicao_form_context(
            view,
            values=_posted_medicao(req.form),
            problems=problems,
            message="" if problems else str(error),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_MEASUREMENT_CREATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_medicao_form_error)
def contrato_medicao_create(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o boletim de medição Em análise e devolve a ficha atualizada."""
    view = _contract_of(req, session, context)
    medicao = service.create_measurement(
        session,
        user=context.user,
        scope=context.scope,
        contract_id=view.id,
        form=_posted_medicao(req.form),
    )
    return _contrato_saved(
        req,
        session,
        context,
        toast=CONTRACT_MEASUREMENT_CREATED_MESSAGE.format(number=medicao.number),
    )


def _render_contrato_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """A ficha de volta, com a recusa no painel das medições, no 422 ou no 409."""
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    data = _contrato_context(view, user=context.user)
    data["erro"] = str(error)
    return AlpineAjaxResponse(
        template_name=CONTRACT_SAVED_TEMPLATE,
        context=data,
        request=req,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_MEASUREMENT_APPROVE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_contrato_error)
def contrato_medicao_approve(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Aprova a medição: o bruto passa a contar como medido e alimenta a EAC."""
    return _move_measurement(req, session, context, target=calculations.SITUATION_APPROVED)


@bp.route(route=CONTRACT_MEASUREMENT_INVOICE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_contrato_error)
def contrato_medicao_invoice(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o faturamento da medição aprovada."""
    return _move_measurement(req, session, context, target=calculations.SITUATION_INVOICED)


@bp.route(route=CONTRACT_MEASUREMENT_PAY_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_contrato_error)
def contrato_medicao_pay(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o pagamento da medição faturada."""
    return _move_measurement(req, session, context, target=calculations.SITUATION_PAID)


@bp.route(route=CONTRACT_MEASUREMENT_RETURN_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_medicao_return_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da devolução da medição, com o motivo obrigatório."""
    view = _contract_of(req, session, context)
    medicao = _medicao_of(view, _medicao_id_of(req))
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENT_RETURN_TEMPLATE,
        context=_contrato_devolucao_context(view, medicao, values={}, problems={}),
        request=req,
    )


def _render_devolucao_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """O formulário da devolução de volta, com o motivo digitado, no 422 ou no 409."""
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
            medicao = _medicao_of(view, _medicao_id_of(req))
    except DomainError:
        return None
    problems = (
        error.detail
        if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping)
        else {}
    )
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENT_RETURN_TEMPLATE,
        context=_contrato_devolucao_context(
            view,
            medicao,
            values=_posted_transition(req.form),
            problems=problems,
            message=str(error) if isinstance(error, VersionConflictError) else "",
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_MEASUREMENT_RETURN_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_devolucao_error)
def contrato_medicao_return(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Devolve a medição à contratada, com o motivo obrigatório."""
    return _move_measurement(req, session, context, target=calculations.SITUATION_RETURNED)


@bp.route(route=CONTRACT_ADDENDUM_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_aditivo_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do aditivo novo, com as SM aprovadas do projeto."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_ADDENDUM_FORM_TEMPLATE,
        context=_contrato_aditivo_form_context(session, view, values={}, problems={}),
        request=req,
    )


def _render_aditivo_form_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """O formulário do aditivo de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=CONTRACT_ADDENDUM_FORM_TEMPLATE,
        context=_contrato_aditivo_form_context(
            session,
            view,
            values=_posted_aditivo(req.form),
            problems=problems,
            message="" if problems else str(error),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_ADDENDUM_CREATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_aditivo_form_error)
def contrato_aditivo_create(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o aditivo aprovado e prorroga o término vigente quando ele tem dias."""
    view = _contract_of(req, session, context)
    aditivo = service.create_addendum(
        session,
        user=context.user,
        scope=context.scope,
        contract_id=view.id,
        form=_posted_aditivo(req.form),
    )
    message = CONTRACT_ADDENDUM_CREATED_MESSAGE.format(number=aditivo.number)
    if aditivo.days:
        message += CONTRACT_ADDENDUM_EXTENDED_SUFFIX.format(days=aditivo.days)
    return _contrato_saved(req, session, context, toast=message)


# ── Montagem da ficha do contrato ────────────────────────────────────────


def _contract_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> service.ContractView:
    """A ficha do contrato do número pedido; número ausente ou desconhecido é 422."""
    return service.contract_by_number(
        session, user=context.user, number=req.params.get(CONTRACT_NUMBER_PARAMETER) or ""
    )


def _medicao_id_of(req: func.HttpRequest) -> int:
    raw = req.route_params.get(CONTRACT_MEASUREMENT_PARAMETER) or ""
    if not raw.isdigit():
        raise InvalidDataError(service.MEASUREMENT_NOT_FOUND_MESSAGE)
    return int(raw)


def _medicao_of(view: service.ContractView, medicao_id: int) -> service.MeasurementView:
    medicao = next((row for row in view.measurements if row.id == medicao_id), None)
    if medicao is None:
        raise InvalidDataError(service.MEASUREMENT_NOT_FOUND_MESSAGE)
    return medicao


def _move_measurement(
    req: func.HttpRequest, session: Session, context: RequestContext, *, target: str
) -> func.HttpResponse:
    view = _contract_of(req, session, context)
    medicao = _medicao_of(view, _medicao_id_of(req))
    moved = service.transition_measurement(
        session,
        user=context.user,
        scope=context.scope,
        measurement_id=medicao.id,
        target=target,
        form=_posted_transition(req.form),
    )
    return _contrato_saved(req, session, context, toast=_moved_message(moved))


def _moved_message(medicao: service.MeasurementView) -> str:
    if medicao.situation == calculations.SITUATION_RETURNED:
        return CONTRACT_MEASUREMENT_RETURNED_MESSAGE.format(number=medicao.number)
    return CONTRACT_MEASUREMENT_MOVED_MESSAGE.format(
        number=medicao.number, situation=medicao.situation.lower()
    )


def _contrato_saved(
    req: func.HttpRequest, session: Session, context: RequestContext, *, toast: str
) -> func.HttpResponse:
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_SAVED_TEMPLATE,
        context=_contrato_context(view, user=context.user),
        request=req,
        toast=toast,
        toast_tipo="ok",
    )


def _contrato_document_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    view = _contract_of(req, session, context)
    return export.contrato_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _contrato_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    data = _contrato_resumo_context(view, user=user)
    data |= _contrato_medicoes_context(view, user=user)
    data |= _contrato_aditivos_context(view, user=user)
    return data


def _contrato_resumo_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    return {
        "ficha": view,
        "pode_gerir": rbac.can(user, Permission.MANAGE),
        "cascata": _cascata_data(view),
        "anexos_url": f"/api/anexos?origem={service.ATTACHMENT_TABLE}&registro={view.id}",
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_medicoes_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    pode_gerir = rbac.can(user, Permission.MANAGE)
    return {
        "ficha": view,
        "pode_gerir": pode_gerir,
        "linhas": [_medicao_line(row, pode_gerir=pode_gerir) for row in view.measurements],
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_aditivos_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    return {
        "ficha": view,
        "pode_gerir": rbac.can(user, Permission.MANAGE),
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_medicao_form_context(
    view: service.ContractView,
    *,
    values: Mapping[str, str | None],
    problems: Mapping[str, str],
    message: str = "",
) -> dict[str, object]:
    return {
        "ficha": view,
        "valores": values,
        "erros": problems,
        "mensagem": message,
        "disponivel": _money(view.available_to_measure_cents),
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_devolucao_context(
    view: service.ContractView,
    medicao: service.MeasurementView,
    *,
    values: Mapping[str, str | None],
    problems: Mapping[str, str],
    message: str = "",
) -> dict[str, object]:
    return {
        "ficha": view,
        "medicao": medicao,
        "bruto": _money(medicao.gross_cents),
        "valores": values,
        "erros": problems,
        "mensagem": message,
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_aditivo_form_context(
    session: Session,
    view: service.ContractView,
    *,
    values: Mapping[str, str | None],
    problems: Mapping[str, str],
    message: str = "",
) -> dict[str, object]:
    return {
        "ficha": view,
        "valores": values,
        "erros": problems,
        "mensagem": message,
        "sms": service.change_options(session, project_id=view.project_id),
        "hoje": calendario.today(),
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _cascata_data(view: service.ContractView) -> dict[str, object]:
    return {
        "titulo": "Composição do valor do contrato",
        "formato": {"divisor": 100, "moeda": "BRL", "casas": 0},
        "etapas": [dict(step) for step in view.cascade],
    }


def _medicao_line(medicao: service.MeasurementView, *, pode_gerir: bool) -> MedicaoLineView:
    return MedicaoLineView(
        medicao=medicao,
        periodo=medicao.period.strftime("%m/%Y"),
        bruto=_money(medicao.gross_cents),
        retencao=_money(medicao.retention_cents),
        liquido=_money(medicao.net_cents),
        situacao_tom=_SITUATION_PILLS.get(medicao.situation, "neutral"),
        pode_aprovar=pode_gerir
        and validation.measurement_transition_allowed(
            medicao.situation, calculations.SITUATION_APPROVED
        ),
        pode_faturar=pode_gerir
        and validation.measurement_transition_allowed(
            medicao.situation, calculations.SITUATION_INVOICED
        ),
        pode_pagar=pode_gerir
        and validation.measurement_transition_allowed(
            medicao.situation, calculations.SITUATION_PAID
        ),
        pode_devolver=pode_gerir
        and validation.measurement_transition_allowed(
            medicao.situation, calculations.SITUATION_RETURNED
        ),
    )


def _posted_medicao(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_MEASUREMENT_PERIOD,
        validation.FIELD_MEASUREMENT_VALUE,
        validation.FIELD_MEASUREMENT_MILESTONE,
    )
    return {name: form.get(name) for name in names}


def _posted_transition(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (validation.FIELD_VERSION, validation.FIELD_MEASUREMENT_REASON)
    return {name: form.get(name) for name in names}


def _posted_aditivo(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_ADDENDUM_DATE,
        validation.FIELD_ADDENDUM_VALUE,
        validation.FIELD_ADDENDUM_DAYS,
        validation.FIELD_ADDENDUM_CHANGE,
        validation.FIELD_ADDENDUM_REASON,
    )
    return {name: form.get(name) for name in names}
