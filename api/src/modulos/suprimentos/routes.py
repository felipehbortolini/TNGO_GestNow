"""Routes of the Procurement module: the supplier register and the purchase plan (D14).

Prefix ``/api/suprimentos/``. The supplier screen is one fragment, ``fornecedores-conteudo``:
the KPIs, the toolbar and the table of the register. Everything that changes the view (a KPI, a
page, the search, a filter) is a plain GET of the same route with the filters in the query
string, answered with the same fragment. The forms open in a modal (``fornecedor-modal-corpo``):
Novo fornecedor and Atualizar qualificação draw by GET and save by POST, and Desempenho e
histórico is a read-only fragment. A refusal (422, 409, 403) answers the form again, filled in,
in the modal.

* ``GET  fornecedores``                         the register (filters and page by query);
* ``GET  fornecedores/excel`` and ``fornecedores/imprimivel``   the two exports;
* ``GET/POST fornecedores/novo``                Novo fornecedor (creates the company);
* ``GET/POST fornecedores/{empresa_id}/qualificacao``   Atualizar qualificação;
* ``GET  fornecedores/{empresa_id}/desempenho`` Desempenho e histórico.

The purchase plan (ISSUE-058) follows the same shape, with ``plano-compras-conteudo`` and
``pacote-modal-corpo``: the plan with its KPIs and filters, the two exports, Novo pacote and the
edit of a package, which the server draws frozen (only scope, buyer, estimate and ROS) or full
according to the real date of the requisition. Excel import runs by the generic importer
(``/api/importacao/plano-de-compras``), registered here.

* ``GET  plano-de-compras`` and ``plano-de-compras/excel``/``imprimivel``   the plan;
* ``GET/POST plano-de-compras/novo``            Novo pacote;
* ``GET/POST plano-de-compras/{pacote_id}/editar``   Editar pacote (full or frozen).

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.suprimentos import calculations, export, importers, service, validation
from src.modulos.suprimentos.validation import (
    DocumentInput,
    PackageChangeInput,
    PackageFilters,
    PackageInput,
    QualificationInput,
    SupplierFilters,
    SupplierInput,
)

bp = func.Blueprint()

importers.register_importers()

MODULE = "suprimentos"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

CONTENT_TARGET = "fornecedores-conteudo"
MODAL_TARGET = "fornecedor-modal-corpo"
ROUTE = "/api/suprimentos/fornecedores"

SCREEN_TEMPLATE = "suprimentos/fornecedores.html"
FORM_TEMPLATE = "suprimentos/fornecedor_form.html"
QUALIFICATION_TEMPLATE = "suprimentos/fornecedor_qualificacao.html"
PERFORMANCE_TEMPLATE = "suprimentos/fornecedor_desempenho.html"

SAVED_NOTICE = "{name} cadastrado em qualificação."
QUALIFIED_NOTICE = "Qualificação de {name} atualizada."
NOT_FOUND_MESSAGE = service.NOT_FOUND_MESSAGE

SITUATION_TONES = {
    calculations.QUALIFIED: "pill--ok",
    calculations.IN_QUALIFICATION: "pill--info",
    calculations.RESTRICTED: "pill--warn",
    calculations.BLOCKED: "pill--erro",
    service.NO_QUALIFICATION: "pill--neutral",
}
CLASS_TONES = {"A": "pill--ok", "B": "pill--fix", "C": "pill--warn", "D": "pill--erro"}


def _error_status(error: DomainError) -> int:
    """The status of a refusal: 403, 409 for a stale screen, 422 for data that does not hold up."""
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


def _modal_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A refusal inside the modal: the message in the modal body, where the person is looking."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=MODAL_TARGET,
        status_code=_error_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


@dataclass(frozen=True)
class KpiCard:
    """A KPI of the register: the number, what it is read against and the link that filters by it."""

    label: str
    icon: str
    tone: str
    value: int | str
    reference: str
    footer: str
    url: str
    active: bool


@dataclass(frozen=True)
class _After:
    """What follows a save on the screen: the toast and what the fragment prints besides."""

    notice: str
    extra: Mapping[str, object]


# ── The screen ───────────────────────────────────────────────────────────────────────────────


@bp.route(route="suprimentos/fornecedores", methods=["GET"])
@fragment_route(access=READ)
def supplier_list(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The register: KPIs, toolbar and table, for the filters of the query string."""
    return _screen(req, session, context, filters=validation.parse_filters(req.params))


@bp.route(route="suprimentos/fornecedores/excel", methods=["GET"])
@file_route(access=READ)
def supplier_list_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the register: what the screen lists, with its KPIs."""
    return excel_response(_document(req, session, context))


@bp.route(route="suprimentos/fornecedores/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def supplier_list_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


# ── Novo fornecedor ──────────────────────────────────────────────────────────────────────────


@bp.route(route="suprimentos/fornecedores/novo", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def supplier_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new supplier: the company and its first qualification."""
    del session, context
    return _form(req, values={}, errors={}, documents=_default_documents())


@bp.route(route="suprimentos/fornecedores/novo", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def supplier_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the company of the cadastro and its qualification, or answer the form again."""
    form = req.form
    data = _supplier_input(form)
    today = calendario.today()
    result: list[service.SaveResult] = []
    error = _attempt(
        session,
        lambda: result.append(
            service.create_supplier(session, user=context.user, data=data, reference_date=today)
        ),
    )
    if error is not None or not result:
        return _form(
            req, values=dict(form), errors=_field_errors(error), documents=_posted_documents(form)
        )
    return _screen(
        req,
        session,
        context,
        filters=_filters_of(form.get("consulta", "")),
        after=_After(SAVED_NOTICE.format(name=result[0].company_name), {}),
    )


# ── Atualizar qualificação ───────────────────────────────────────────────────────────────────


@bp.route(route="suprimentos/fornecedores/{empresa_id}/qualificacao", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def supplier_qualification_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The qualification of one supplier, to update."""
    line = _company_line(session, context, req)
    return _form(
        req,
        values={
            "situacao": line.situation if line.registered else calculations.IN_QUALIFICATION,
            "validade": line.validity.isoformat() if line.validity else "",
            "categorias": ", ".join(line.categories),
            "observacao": line.observation,
            "versao": str(line.version) if line.version is not None else "",
        },
        errors={},
        documents=_line_documents(line),
        company_id=line.company_id,
        company_name=line.name,
    )


@bp.route(route="suprimentos/fornecedores/{empresa_id}/qualificacao", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def supplier_qualification_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the qualification, or answer the form again with the messages."""
    line = _company_line(session, context, req)
    form = req.form
    data = _qualification_input(form)
    today = calendario.today()
    outcome: list[service.SaveResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.save_qualification(
                session,
                user=context.user,
                company_id=line.company_id,
                data=data,
                reference_date=today,
            )
        ),
    )
    if error is not None or not outcome:
        return _form(
            req,
            values=dict(form),
            errors=_field_errors(error),
            documents=_posted_documents(form),
            company_id=line.company_id,
            company_name=line.name,
        )
    return _screen(
        req,
        session,
        context,
        filters=_filters_of(form.get("consulta", "")),
        after=_After(QUALIFIED_NOTICE.format(name=line.name), {}),
    )


# ── Desempenho e histórico ───────────────────────────────────────────────────────────────────


@bp.route(route="suprimentos/fornecedores/{empresa_id}/desempenho", methods=["GET"])
@fragment_route(access=READ)
def supplier_performance(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The performance and the history of one supplier, as the modal prints them."""
    line = _company_line(session, context, req)
    return AlpineAjaxResponse(
        template_name=PERFORMANCE_TEMPLATE,
        context={
            "fornecedor": line,
            "formatar_data": _format_date,
            "formatar_moeda": _format_money,
            "pill_da_classe": lambda name: CLASS_TONES.get(name, "pill--neutral"),
            "sem_qualificacao": service.NO_QUALIFICATION,
        },
        request=req,
        target_id=MODAL_TARGET,
    )


# ── Drawing the screen ───────────────────────────────────────────────────────────────────────


def _filters_of(query: str) -> SupplierFilters:
    return validation.parse_filters(dict(parse_qsl(query)))


def _screen(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: SupplierFilters,
    after: _After | None = None,
) -> func.HttpResponse:
    """The screen fragment for the filters, with an optional toast and extra context."""
    listing = service.list_suppliers(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={**_screen_context(listing, context), **(after.extra if after else {})},
        request=req,
        target_id=CONTENT_TARGET,
        toast=after.notice if after else None,
    )


def _screen_context(listing: service.SupplierListing, context: RequestContext) -> dict[str, object]:
    filters = listing.filters
    query = _query_string(filters)
    return {
        "listagem": listing,
        "filtros": filters,
        "kpis": _kpi_cards(listing),
        "situacoes": calculations.SITUATIONS,
        "sem_qualificacao": service.NO_QUALIFICATION,
        "link_anterior": _page_link(filters, listing.page - 1, listing.page_count),
        "link_proximo": _page_link(filters, listing.page + 1, listing.page_count),
        "link_limpar": _address(filters, busca="", situacao="", categoria="", pagina=1),
        "url_excel": _address(filters, pagina=1, path=f"{ROUTE}/excel"),
        "url_pdf": _address(filters, pagina=1, path=f"{ROUTE}/imprimivel"),
        "consulta": query,
        "parametro_consulta": urlencode({"consulta": query}),
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "pill_da_situacao": lambda situation: SITUATION_TONES.get(situation, "pill--neutral"),
        "pill_da_classe": lambda name: CLASS_TONES.get(name, "pill--neutral"),
        "formatar_data": _format_date,
        "formatar_moeda": _format_money,
        "pagina_inicial": (listing.page - 1) * validation.PAGE_SIZE + 1,
        "pagina_final": min(listing.page * validation.PAGE_SIZE, listing.total),
    }


def _kpi_cards(listing: service.SupplierListing) -> list[KpiCard]:
    summary = listing.summary
    filters = listing.filters
    restricted = summary.restricted_or_blocked
    expired = summary.expired_documents
    due = summary.validity_due
    return [
        KpiCard(
            label="Cadastrados",
            icon="building",
            tone="neutro",
            value=summary.registered,
            reference=f"Referência: de {summary.companies} empresas",
            footer=f"{summary.unregistered} empresas sem qualificação",
            url=_address(filters, situacao="", pagina=1),
            active=not filters.situation,
        ),
        KpiCard(
            label="Qualificados",
            icon="checkCircle",
            tone="ok",
            value=summary.qualified,
            reference=f"Referência: de {summary.registered} cadastrados",
            footer="",
            url=_address(filters, situacao=calculations.QUALIFIED, pagina=1),
            active=filters.situation == calculations.QUALIFIED,
        ),
        KpiCard(
            label="Em qualificação",
            icon="clock",
            tone="info",
            value=summary.in_qualification,
            reference=f"Referência: de {summary.registered} cadastrados",
            footer="",
            url=_address(filters, situacao=calculations.IN_QUALIFICATION, pagina=1),
            active=filters.situation == calculations.IN_QUALIFICATION,
        ),
        KpiCard(
            label="Restritos ou bloqueados",
            icon="lock",
            tone="warn" if restricted else "ok",
            value=restricted,
            reference="Esperado: 0",
            footer=f"{summary.blocked} bloqueados",
            url=_address(filters, situacao=calculations.RESTRICTED, pagina=1),
            active=filters.situation == calculations.RESTRICTED,
        ),
        KpiCard(
            label="Documentos vencidos",
            icon="file",
            tone="erro" if expired else "ok",
            value=expired,
            reference="Esperado: 0",
            footer="certidões e certificados fora da validade",
            url="",
            active=False,
        ),
        KpiCard(
            label="Qualificação a vencer",
            icon="calendar",
            tone="warn" if due else "ok",
            value=due,
            reference="Esperado: 0",
            footer="vencida ou vence em até 90 dias",
            url="",
            active=False,
        ),
    ]


def _page_link(filters: SupplierFilters, page: int, page_count: int) -> str:
    if page < 1 or page > page_count:
        return ""
    return _address(filters, pagina=page)


def _address(filters: SupplierFilters, *, path: str = ROUTE, **changes: object) -> str:
    """The address of the register with the current filters and the informed changes."""
    values: dict[str, object] = {
        "busca": filters.search,
        "situacao": filters.situation,
        "categoria": filters.category,
        "pagina": filters.page if filters.page > 1 else 1,
    }
    values.update(changes)
    clean = {name: str(value) for name, value in values.items() if value not in ("", 1, None)}
    query = urlencode(clean)
    return f"{path}?{query}" if query else path


def _query_string(filters: SupplierFilters) -> str:
    """The filters as the consulta parameter of the forms (without the page)."""
    clean = {
        name: value
        for name, value in (
            ("busca", filters.search),
            ("situacao", filters.situation),
            ("categoria", filters.category),
        )
        if value
    }
    return urlencode(clean)


def _format_date(value: date | None) -> str:
    """``25/09/2026``; the dash when there is no date."""
    return "—" if value is None else format_value(ValueKind.DATE, value)


def _format_money(cents: int | None) -> str:
    """``R$ 1.850.000,00`` from cents; the dash when there is no value."""
    return "—" if cents is None else format_value(ValueKind.MONEY, cents)


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """The document of the screen for the filters of the request; the only place with the clock."""
    filters = validation.parse_filters(req.params)
    today = calendario.today()
    listing = service.list_suppliers(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=today,
    )
    return export.build_document(
        listing=listing,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


# ── Drawing the forms ────────────────────────────────────────────────────────────────────────


def _company_line(
    session: Session, context: RequestContext, req: func.HttpRequest
) -> service.SupplierLine:
    company_id = validation.parse_id(req.route_params.get("empresa_id"))
    line = (
        None
        if company_id is None
        else service.find_supplier(
            session,
            user=context.user,
            scope=context.scope,
            company_id=company_id,
            reference_date=calendario.today(),
        )
    )
    if line is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return line


def _attempt(session: Session, work: Callable[[], object]) -> DomainError | None:
    """Run a write inside a savepoint: a refusal leaves nothing behind, not even a half write."""
    try:
        with session.begin_nested():
            work()
    except (InvalidDataError, VersionConflictError) as error:
        return error
    return None


def _field_errors(error: DomainError | None) -> dict[str, str]:
    if error is None:
        return {}
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return dict(error.detail)
    return {"geral": str(error)}


def _supplier_input(form: Mapping[str, str]) -> SupplierInput:
    return SupplierInput(
        name=form.get("nome", ""),
        kind=form.get("tipo", ""),
        categories=validation.categories_of(form.get("categorias", "")),
        documents=_documents_of(form),
        observation=form.get("observacao", ""),
    )


def _qualification_input(form: Mapping[str, str]) -> QualificationInput:
    return QualificationInput(
        situation=form.get("situacao", ""),
        categories=validation.categories_of(form.get("categorias", "")),
        documents=_documents_of(form),
        validity=validation.parse_date(form.get("validade")),
        observation=form.get("observacao", ""),
        justification=form.get("justificativa", ""),
        version=form.get("versao"),
    )


def _documents_of(form: Mapping[str, object]) -> tuple[DocumentInput, ...]:
    getlist = getattr(form, "getlist", None)
    if getlist is None:
        return ()
    return validation.parse_documents(
        getlist("documentoId"),
        getlist("documentoNome"),
        getlist("documentoValidade"),
        getlist("documentoVersao"),
    )


def _posted_documents(form: Mapping[str, object]) -> list[dict[str, str]]:
    """The document rows as the form sent them, for the 422 to come back filled in."""
    getlist = getattr(form, "getlist", None)
    if getlist is None:
        return []
    ids = getlist("documentoId")
    names = getlist("documentoNome")
    validities = getlist("documentoValidade")
    versions = getlist("documentoVersao")
    rows: list[dict[str, str]] = []
    for raw_id, name, validity, version in zip(ids, names, validities, versions, strict=False):
        rows.append({"id": raw_id, "nome": name, "validade": validity, "versao": version})
    return rows


def _default_documents() -> list[dict[str, str]]:
    """The three documents the prototype opens on a new supplier, with an empty validity."""
    return [
        {"id": "", "nome": name, "validade": "", "versao": ""}
        for name in validation.DEFAULT_DOCUMENTS
    ]


def _line_documents(line: service.SupplierLine) -> list[dict[str, str]]:
    """The documents of the supplier; a cadastro without documents falls back to the default three."""
    if not line.documents:
        return _default_documents()
    return [
        {
            "id": str(document.id),
            "nome": document.name,
            "validade": document.validity.isoformat() if document.validity else "",
            "versao": str(document.version),
        }
        for document in line.documents
    ]


def _form(
    req: func.HttpRequest,
    *,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    documents: list[dict[str, str]],
    company_id: int | None = None,
    company_name: str = "",
) -> func.HttpResponse:
    """The form of Novo fornecedor (without company) or of Atualizar qualificação (with company)."""
    return AlpineAjaxResponse(
        template_name=QUALIFICATION_TEMPLATE if company_id else FORM_TEMPLATE,
        context={
            "valores": dict(values),
            "erros": dict(errors),
            "documentos": documents,
            "empresa_id": company_id,
            "empresa_nome": company_name,
            "situacoes": calculations.SITUATIONS,
            "tipos": validation.KINDS,
            "referencia": calendario.today().isoformat(),
        },
        request=req,
        target_id=MODAL_TARGET,
    )


# ── The purchase plan (ISSUE-058) ────────────────────────────────────────────────────────────

PLAN_TARGET = "plano-compras-conteudo"
PACKAGE_MODAL_TARGET = "pacote-modal-corpo"
PLAN_ROUTE = "/api/suprimentos/plano-de-compras"

PLAN_TEMPLATE = "suprimentos/plano_compras.html"
PACKAGE_FORM_TEMPLATE = "suprimentos/pacote_form.html"

PACKAGE_SAVED_NOTICE = "Pacote {code} incluído no plano de compras."
PACKAGE_UPDATED_NOTICE = "Pacote {code} atualizado."
PACKAGE_NOT_FOUND_MESSAGE = validation.PACKAGE_NOT_FOUND

ETAPA_TONES = {
    calculations.STAGE_PLANNED: "pill--neutral",
    "Requisição": "pill--fix",
    "RFx emitida": "pill--fix",
    "Propostas recebidas": "pill--fix",
    "Equalização técnica": "pill--fix",
    "Equalização comercial": "pill--fix",
    "Aprovada": "pill--fix",
    "Pedido/contrato emitido": "pill--ok",
}
FOLGA_TONES = {
    calculations.SLACK_CRITICAL: "pill--erro",
    calculations.SLACK_WARNING: "pill--warn",
    calculations.SLACK_OK: "pill--ok",
}


def _package_modal_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A refusal inside the package modal: the message where the person is looking."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=PACKAGE_MODAL_TARGET,
        status_code=_error_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


@bp.route(route="suprimentos/plano-de-compras", methods=["GET"])
@fragment_route(access=READ)
def package_list(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The plan: KPIs, toolbar and table, for the filters of the query string."""
    return _plan_screen(req, session, context, filters=validation.parse_package_filters(req.params))


@bp.route(route="suprimentos/plano-de-compras/excel", methods=["GET"])
@file_route(access=READ)
def package_list_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the plan: what the screen lists, with its KPIs."""
    return excel_response(_plan_document(req, session, context))


@bp.route(route="suprimentos/plano-de-compras/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def package_list_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_plan_document(req, session, context), req)


# ── Novo pacote e edição ─────────────────────────────────────────────────────────────────────


@bp.route(route="suprimentos/plano-de-compras/novo", methods=["GET"])
@fragment_route(access=WRITE, on_error=_package_modal_error)
def package_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new package, with the saldo a comprometer of each item of the EAC."""
    return _package_form(req, session, context, package=None, values={}, errors={})


@bp.route(route="suprimentos/plano-de-compras/novo", methods=["POST"])
@fragment_route(access=WRITE, on_error=_package_modal_error)
def package_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the package of the plan, or answer the form again with the messages."""
    project_id = context.scope.require_project()
    form = req.form
    data = _package_input(form)
    today = calendario.today()
    saved: list[service.PackageSave] = []
    error = _attempt(
        session,
        lambda: saved.append(
            service.create_package(
                session, user=context.user, project_id=project_id, data=data, reference_date=today
            )
        ),
    )
    if error is not None or not saved:
        return _package_form(
            req,
            session,
            context,
            package=None,
            values=dict(form),
            errors=_field_errors(error),
            status_code=_form_status(error),
        )
    return _plan_screen(
        req,
        session,
        context,
        filters=_plan_filters_of(form.get("consulta", "")),
        after=_After(PACKAGE_SAVED_NOTICE.format(code=saved[0].code), {}),
    )


@bp.route(route="suprimentos/plano-de-compras/{pacote_id}/editar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_package_modal_error)
def package_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The package to edit: full before the requisition, frozen (four fields) after it."""
    line = _package_line(session, context, req)
    return _package_form(
        req, session, context, package=line, values=_package_values(line), errors={}
    )


@bp.route(route="suprimentos/plano-de-compras/{pacote_id}/editar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_package_modal_error)
def package_edit_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the package: the full plan, or the four fields the frozen baseline still allows."""
    line = _package_line(session, context, req)
    form = req.form
    today = calendario.today()
    if line.frozen:
        return _save_frozen_package(req, session, context, line=line, form=form, today=today)
    return _save_package_baseline(req, session, context, line=line, form=form, today=today)


def _save_package_baseline(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    line: service.PackageLine,
    form: Mapping[str, str],
    today: date,
) -> func.HttpResponse:
    data = _package_input(form)
    saved: list[service.PackageSave] = []
    error = _attempt(
        session,
        lambda: saved.append(
            service.update_package(
                session, user=context.user, package_id=line.id, data=data, reference_date=today
            )
        ),
    )
    if error is not None or not saved:
        return _package_form(
            req,
            session,
            context,
            package=line,
            values=dict(form),
            errors=_field_errors(error),
            status_code=_form_status(error),
        )
    return _plan_screen(
        req,
        session,
        context,
        filters=_plan_filters_of(form.get("consulta", "")),
        after=_After(PACKAGE_UPDATED_NOTICE.format(code=saved[0].code), {}),
    )


def _save_frozen_package(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    line: service.PackageLine,
    form: Mapping[str, str],
    today: date,
) -> func.HttpResponse:
    baseline = validation.frozen_baseline_problems(form.keys())
    if baseline:
        return _package_form(
            req,
            session,
            context,
            package=line,
            values=dict(form),
            errors=baseline,
            status_code=422,
        )
    data = _package_change_input(form)
    saved: list[service.PackageSave] = []
    error = _attempt(
        session,
        lambda: saved.append(
            service.change_package(
                session, user=context.user, package_id=line.id, data=data, reference_date=today
            )
        ),
    )
    if error is not None or not saved:
        return _package_form(
            req,
            session,
            context,
            package=line,
            values=dict(form),
            errors=_field_errors(error),
            status_code=_form_status(error),
        )
    return _plan_screen(
        req,
        session,
        context,
        filters=_plan_filters_of(form.get("consulta", "")),
        after=_After(PACKAGE_UPDATED_NOTICE.format(code=saved[0].code), {}),
    )


def _form_status(error: DomainError | None) -> int:
    """The status of a form re-rendered after a refusal: 409 for a stale screen, 422 otherwise."""
    return 409 if isinstance(error, VersionConflictError) else 422


# ── Drawing the plan ─────────────────────────────────────────────────────────────────────────


def _plan_filters_of(query: str) -> PackageFilters:
    return validation.parse_package_filters(dict(parse_qsl(query)))


def _plan_screen(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: PackageFilters,
    after: _After | None = None,
) -> func.HttpResponse:
    """The plan fragment for the filters, with an optional toast and extra context."""
    listing = service.list_packages(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=PLAN_TEMPLATE,
        context={**_plan_context(listing, context), **(after.extra if after else {})},
        request=req,
        target_id=PLAN_TARGET,
        toast=after.notice if after else None,
    )


def _plan_context(listing: service.PackageListing, context: RequestContext) -> dict[str, object]:
    filters = listing.filters
    return {
        "listagem": listing,
        "filtros": filters,
        "kpis": _plan_kpi_cards(listing),
        "tipos": validation.PACKAGE_TYPES,
        "link_anterior": _plan_page_link(filters, listing.page - 1, listing.page_count),
        "link_proximo": _plan_page_link(filters, listing.page + 1, listing.page_count),
        "link_limpar": _plan_address(filters, busca="", tipo="", lli="", pagina=1),
        "url_excel": _plan_address(filters, pagina=1, path=f"{PLAN_ROUTE}/excel"),
        "url_pdf": _plan_address(filters, pagina=1, path=f"{PLAN_ROUTE}/imprimivel"),
        "consulta": _plan_query_string(filters),
        "parametro_consulta": urlencode({"consulta": _plan_query_string(filters)}),
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "portfolio": context.scope.is_portfolio,
        "pill_da_etapa": lambda stage: ETAPA_TONES.get(stage, "pill--neutral"),
        "pill_da_folga": lambda days: FOLGA_TONES.get(calculations.slack_band(days), "pill--ok"),
        "formatar_data": _format_date,
        "formatar_moeda": _format_money,
        "resumo": listing.summary,
        "pagina_inicial": (listing.page - 1) * validation.PACKAGE_PAGE_SIZE + 1,
        "pagina_final": min(listing.page * validation.PACKAGE_PAGE_SIZE, listing.total),
    }


def _plan_kpi_cards(listing: service.PackageListing) -> list[KpiCard]:
    summary = listing.summary
    filters = listing.filters
    return [
        KpiCard(
            label="Pacotes no plano",
            icon="layers",
            tone="neutro",
            value=summary.packages,
            reference=f"Linha de base: {summary.with_baseline}",
            footer=f"{_format_money(summary.estimated_cents)} estimados",
            url=_plan_address(filters, tipo="", lli="", pagina=1),
            active=not filters.kind and not filters.lli_only,
        ),
        KpiCard(
            label="Adjudicados",
            icon="checkCircle",
            tone="neutro",
            value="—",
            reference=f"Previsto até hoje: {summary.forecast_until_reference}",
            footer="aguarda o processo de compra (ISSUE-059)",
            url="",
            active=False,
        ),
        KpiCard(
            label="Adjudicação atrasada",
            icon="clock",
            tone="warn" if summary.overdue else "ok",
            value=summary.overdue,
            reference="Esperado: 0",
            footer="LB da adjudicação vencida ou previsão após a LB",
            url="",
            active=False,
        ),
        KpiCard(
            label="Itens de longo prazo (LLI)",
            icon="calendar",
            tone="info",
            value=summary.lli,
            reference=f"Referência: de {summary.packages} pacotes",
            footer=f"{summary.lli_critical} com folga negativa",
            url=_plan_address(filters, lli="1", pagina=1),
            active=filters.lli_only,
        ),
        KpiCard(
            label="Saving sobre estimativa",
            icon="money",
            tone="ok",
            value="—",
            reference=f"Meta: ≥ {_format_money(0)}",
            footer="pacotes adjudicados",
            url="",
            active=False,
        ),
    ]


def _plan_page_link(filters: PackageFilters, page: int, page_count: int) -> str:
    if page < 1 or page > page_count:
        return ""
    return _plan_address(filters, pagina=page)


def _plan_address(filters: PackageFilters, *, path: str = PLAN_ROUTE, **changes: object) -> str:
    """The address of the plan with the current filters and the informed changes."""
    values: dict[str, object] = {
        "busca": filters.search,
        "tipo": filters.kind,
        "lli": "1" if filters.lli_only else "",
        "pagina": filters.page if filters.page > 1 else 1,
    }
    values.update(changes)
    clean = {name: str(value) for name, value in values.items() if value not in ("", 1, None)}
    query = urlencode(clean)
    return f"{path}?{query}" if query else path


def _plan_query_string(filters: PackageFilters) -> str:
    """The filters as the consulta parameter of the forms (without the page)."""
    clean = {
        name: value
        for name, value in (
            ("busca", filters.search),
            ("tipo", filters.kind),
            ("lli", "1" if filters.lli_only else ""),
        )
        if value
    }
    return urlencode(clean)


def _plan_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """The document of the plan for the filters of the request; the only place with the clock."""
    filters = validation.parse_package_filters(req.params)
    today = calendario.today()
    listing = service.list_packages(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=today,
    )
    return export.build_plan_document(
        listing=listing,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


# ── Drawing the package form ─────────────────────────────────────────────────────────────────


def _package_line(
    session: Session, context: RequestContext, req: func.HttpRequest
) -> service.PackageLine:
    package_id = validation.parse_id(req.route_params.get("pacote_id"))
    line = (
        None
        if package_id is None
        else service.find_package(
            session,
            user=context.user,
            scope=context.scope,
            package_id=package_id,
            reference_date=calendario.today(),
        )
    )
    if line is None:
        raise InvalidDataError(PACKAGE_NOT_FOUND_MESSAGE)
    return line


def _package_form(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    package: service.PackageLine | None,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status_code: int = 200,
) -> func.HttpResponse:
    """The modal body: Novo pacote (no package) or the full/frozen edit of one.

    A refusal re-renders it with 422 (or 409 for a stale screen), so the client puts the answer
    in the modal body declared by ``x-target.422`` and the person sees what to fix. The package
    already knows its project: in the Portfólio the edit opens with the EAC of the own package.
    """
    project_id = package.project_id if package is not None else context.scope.require_project()
    options = service.package_options(
        session, user=context.user, project_id=project_id, reference_date=calendario.today()
    )
    frozen = package.frozen if package is not None else False
    return AlpineAjaxResponse(
        template_name=PACKAGE_FORM_TEMPLATE,
        context={
            "valores": dict(values),
            "erros": dict(errors),
            "pacote": package,
            "congelado": frozen,
            "compradores": options.buyers,
            "disciplinas": options.disciplines,
            "itens_eac": options.eac_items,
            "tipos": validation.PACKAGE_TYPES,
            "modalidades": validation.PACKAGE_MODALITIES,
            "referencia": calendario.today().isoformat(),
            "formatar_data": _format_date,
            "formatar_moeda": _format_money,
            "rotulo_salvar": _save_label(package, frozen=frozen),
        },
        request=req,
        target_id=PACKAGE_MODAL_TARGET,
        status_code=status_code,
    )


def _save_label(package: service.PackageLine | None, *, frozen: bool) -> str:
    """The label of the submit button: a new package, a full save or a frozen change."""
    if frozen:
        return "Salvar alterações"
    if package is None:
        return "Incluir no plano"
    return "Salvar o plano"


def _package_values(line: service.PackageLine) -> dict[str, str]:
    """The package as the form opens it; the dates go in ISO, the money as the person reads it."""
    milestones = {item.key: item for item in line.milestones}
    return {
        "escopo": line.scope,
        "tipo": line.kind,
        "modalidade": line.modality,
        "disciplina": str(line.discipline_id or ""),
        "comprador": str(line.buyer_id),
        "eac": line.eac_code,
        "estimativa": format_value(ValueKind.MONEY, line.estimate_cents),
        "requisicao": _iso_of(milestones.get("requisicao")),
        "rfx": _iso_of(milestones.get("rfx")),
        "adjudicacao": _iso_of(milestones.get("adjudicacao")),
        "pedido": _iso_of(milestones.get("pedido")),
        "ros": line.ros.isoformat() if line.ros else "",
        "lli": "1" if line.lli else "",
        "antecipado": "1" if line.gate_date else "",
        "gate": line.gate_reference,
        "emergencial": "1" if line.emergency else "",
        "justEmergencial": "",
        "justificativa": "",
        "versao": str(line.version),
    }


def _iso_of(milestone: service.MilestoneLine | None) -> str:
    return milestone.plan.isoformat() if milestone is not None and milestone.plan else ""


def _package_input(form: Mapping[str, str]) -> PackageInput:
    return PackageInput(
        scope=form.get("escopo", ""),
        kind=form.get("tipo", ""),
        modality=form.get("modalidade", ""),
        discipline_id=validation.parse_id(form.get("disciplina")),
        buyer_id=validation.parse_id(form.get("comprador")),
        eac_code=form.get("eac", ""),
        estimate_cents=validation.parse_money(form.get("estimativa", "")),
        requisition=validation.parse_date(form.get("requisicao")),
        rfx=validation.parse_date(form.get("rfx")),
        adjudication=validation.parse_date(form.get("adjudicacao")),
        order=validation.parse_date(form.get("pedido")),
        ros=validation.parse_date(form.get("ros")),
        lli=validation.parse_flag(form.get("lli")),
        anticipated_fid=validation.parse_flag(form.get("antecipado")),
        gate_reference=form.get("gate", ""),
        emergency=validation.parse_flag(form.get("emergencial")),
        emergency_justification=form.get("justEmergencial", ""),
        version=(form.get("versao") or "").strip() or None,
    )


def _package_change_input(form: Mapping[str, str]) -> PackageChangeInput:
    return PackageChangeInput(
        scope=form.get("escopo", ""),
        buyer_id=validation.parse_id(form.get("comprador")),
        estimate_cents=validation.parse_money(form.get("estimativa", "")),
        ros=validation.parse_date(form.get("ros")),
        justification=form.get("justificativa", ""),
        version=(form.get("versao") or "").strip() or None,
    )
