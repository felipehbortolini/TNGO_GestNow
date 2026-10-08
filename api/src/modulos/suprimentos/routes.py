"""Routes of the Procurement module: the supplier register and its forms (D14, ISSUE-057).

Prefix ``/api/suprimentos/``. The screen is one fragment, ``fornecedores-conteudo``: the KPIs,
the toolbar and the table of the register. Everything that changes the view (a KPI, a page, the
search, a filter) is a plain GET of the same route with the filters in the query string,
answered with the same fragment. The forms open in a modal (``fornecedor-modal-corpo``): Novo
fornecedor and Atualizar qualificação draw by GET and save by POST, and Desempenho e histórico is
a read-only fragment. A refusal (422, 409, 403) answers the form again, filled in, in the modal.

* ``GET  fornecedores``                         the register (filters and page by query);
* ``GET  fornecedores/excel`` and ``fornecedores/imprimivel``   the two exports;
* ``GET/POST fornecedores/novo``                Novo fornecedor (creates the company);
* ``GET/POST fornecedores/{empresa_id}/qualificacao``   Atualizar qualificação;
* ``GET  fornecedores/{empresa_id}/desempenho`` Desempenho e histórico.

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
from src.modulos.suprimentos import calculations, export, service, validation
from src.modulos.suprimentos.validation import (
    DocumentInput,
    QualificationInput,
    SupplierFilters,
    SupplierInput,
)

bp = func.Blueprint()

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
    value: int
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
