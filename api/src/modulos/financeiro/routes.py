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
* ``POST /eac/revisoes/importar/conferir`` and ``.../confirmar`` are the two steps of the import
  of new items by spreadsheet: the check reads and never writes, and the confirmation checks
  again and creates the revision bound to the SM;
* ``GET /eac/excel`` and ``GET /eac/imprimivel`` are the two exports of the platform, with the
  same filters and the same tables the screen shows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario, database, importing
from src.core.errors import DomainError, InvalidDataError, VersionConflictError
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
from src.core.spreadsheet_reader import MAX_FILE_BYTES
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import export, importers, service, validation
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
IMPORT_CHECK_TEMPLATE = "comum/importacao_conferencia.html"

FORM_TARGET = "eac-formulario"
CONTENT_TARGET = "eac-conteudo"
REVISIONS_TARGET = "eac-revisoes"
REALLOCATIONS_TARGET = "eac-remanejamentos"
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
        context=_revisions_context(session, context.scope),
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
        context=_reallocations_context(session, context.scope),
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
    return AlpineAjaxResponse(
        template_name=IMPORT_CHECK_TEMPLATE, context=_check_context(preview), request=req
    )


@bp.route(route=IMPORT_CONFIRM_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_revision_error)
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


def _revisions_context(session: Session, scope: Scope, *, erro: str = "") -> dict[str, object]:
    return {
        "revisoes": service.revision_rows(session, project_ids=_project_ids(session, scope)),
        "carteira": scope.is_portfolio,
        "erro": erro,
    }


def _reallocations_context(session: Session, scope: Scope, *, erro: str = "") -> dict[str, object]:
    return {
        "remanejamentos": service.reallocation_rows(
            session, project_ids=_project_ids(session, scope)
        ),
        "carteira": scope.is_portfolio,
        "erro": erro,
    }


def _panels_context(
    session: Session, *, user: User, scope: Scope, filters: EacFilters, erro: str = ""
) -> dict[str, object]:
    view = service.eac_view(
        session, user=user, scope=scope, filters=filters, reference_date=calendario.today()
    )
    data = _content_context(view)
    data |= _revisions_context(session, scope, erro=erro)
    data |= _reallocations_context(session, scope, erro=erro)
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
