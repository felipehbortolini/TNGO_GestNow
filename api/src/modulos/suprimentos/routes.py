"""Routes of the Procurement module: the supplier register, the purchase plan and the process (D14).

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

The process screen (ISSUE-059/060) is one fragment, ``processos-conteudo``: the five KPIs, the
toolbar, the Etapas chart with the nine steps of each process and the ficha of the selected one.
The ficha also answers alone (``processo-ficha``) for the click on a chart line; the actions open
in a modal (``processo-modal-corpo``) drawn by GET and saved by POST, and a refusal answers the
form again, filled in. The actions are the requisition, the RFx, the proposal (its PDF is a real
attachment), the closing of the receipt, the three equalization/negotiation steps, the
recommendation of the award, the return, the approval by band and the emission of the order or
of the contract (ISSUE-060).

* ``GET  processos`` and ``processos/excel``/``imprimivel``   the list (and the map, with ``pacote``);
* ``GET  processos/ficha``                      the ficha of one process (``pacote``);
* ``GET/POST processos/requisicao``             Nova requisição;
* ``GET/POST processos/{pacote_id}/acao/{nome}``  the other actions of the flow.

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario, rbac
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.excel import excel_response
from src.core.export_document import CellValue, Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.suprimentos import calculations, export, importers, service, validation
from src.modulos.suprimentos.validation import (
    ApprovalInput,
    ClosingInput,
    CommercialInput,
    DocumentInput,
    EmissionInput,
    NegotiationInput,
    PackageChangeInput,
    PackageFilters,
    PackageInput,
    ProposalInput,
    QualificationInput,
    RecommendationInput,
    RequisitionInput,
    ReturnInput,
    RfxInput,
    SupplierFilters,
    SupplierInput,
    TechnicalEvaluation,
    TechnicalInput,
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


def _format_decimal(value: CellValue, digits: int = 1) -> str:
    """``95,2`` from a score; the dot when there is no value."""
    return "·" if value is None else format_value(ValueKind.DECIMAL, value, digits)


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


# ── The purchase process (ISSUE-059) ─────────────────────────────────────────────────────────

PROCESS_TARGET = "processos-conteudo"
FICHA_TARGET = "processo-ficha"
PROCESS_MODAL_TARGET = "processo-modal-corpo"
PROCESS_ROUTE = "/api/suprimentos/processos"

PROCESS_TEMPLATE = "suprimentos/processos.html"
FICHA_TEMPLATE = "suprimentos/processo_ficha.html"

REQUISITION_TEMPLATE = "suprimentos/processo_requisicao.html"
ACTION_TEMPLATES: Mapping[str, str] = {
    "rfx": "suprimentos/processo_rfx.html",
    "proposta": "suprimentos/processo_proposta.html",
    "encerrar-recebimento": "suprimentos/processo_encerrar.html",
    "equalizacao-tecnica": "suprimentos/processo_eq_tecnica.html",
    "equalizacao-comercial": "suprimentos/processo_eq_comercial.html",
    "negociacao": "suprimentos/processo_negociacao.html",
    "recomendacao": "suprimentos/processo_recomendacao.html",
    "devolver": "suprimentos/processo_devolver.html",
    "aprovar": "suprimentos/processo_aprovar.html",
    "emitir": "suprimentos/processo_emitir.html",
}

PROCESS_NOT_FOUND_MESSAGE = validation.PROCESS_NOT_FOUND
UNKNOWN_ACTION_MESSAGE = "Ação desconhecida."

REQUISITION_NOTICE = "Requisição de {code} registrada; marco realizado no MAS."
RFX_NOTICE = "{number} emitida."
PROPOSAL_NOTICE = "Proposta registrada em {number}."
CLOSING_NOTICE = "Recebimento encerrado; equalização técnica liberada."
TECHNICAL_NOTICE = "Equalização técnica concluída; mapa comercial liberado."
COMMERCIAL_NOTICE = "Mapa comercial concluído; processo em negociação."
NEGOTIATION_NOTICE = "Negociação registrada."
RECOMMENDATION_NOTICE = "Recomendação enviada para aprovação na alçada."
RETURN_NOTICE = "Recomendação devolvida para negociação."
APPROVAL_NOTICE = "Adjudicação aprovada; marco realizado no MAS."
ORDER_NOTICE = "Pedido {document} emitido; valor comprometido na EAC."
CONTRACT_NOTICE = "Contrato {document} emitido; valor comprometido na EAC."

# The actions each stage of the process offers (ISSUE-059/060): name, label, icon and tone.
STAGE_ACTIONS: Mapping[str, tuple[tuple[str, str, str, str], ...]] = {
    calculations.STAGE_PLANNED: (("requisicao", "Registrar requisição", "fileAdd", "primary"),),
    "Requisição": (("rfx", "Emitir RFx", "send", "primary"),),
    "RFx emitida": (("proposta", "Registrar proposta", "fileAdd", "primary"),),
    "Propostas recebidas": (
        ("proposta", "Registrar proposta", "fileAdd", "secondary"),
        ("encerrar-recebimento", "Encerrar recebimento", "check", "primary"),
    ),
    "Equalização técnica": (
        ("equalizacao-tecnica", "Equalização técnica", "checkCircle", "primary"),
    ),
    "Equalização comercial": (
        ("equalizacao-comercial", "Concluir equalização comercial", "money", "primary"),
    ),
    "Negociação": (
        ("negociacao", "Registrar negociação", "send", "secondary"),
        ("recomendacao", "Recomendar adjudicação", "checkCircle", "primary"),
    ),
    "Recomendação de adjudicação": (
        ("devolver", "Devolver", "chevronLeft", "secondary"),
        ("aprovar", "Aprovar adjudicação", "check", "primary"),
    ),
    "Aprovada": (("emitir", "Emitir pedido ou contrato", "file", "primary"),),
}

# The vocabulary of the Etapas chart: the states of the steps and of the line.
CHART_STATES: tuple[Mapping[str, object], ...] = (
    {"id": "concluido", "rotulo": "Concluído", "tom": "ok"},
    {"id": "andamento", "rotulo": "Em andamento", "tom": "alerta"},
    {"id": "futuro", "rotulo": "Não iniciado", "tom": "atencao"},
    {"id": "na", "rotulo": "Sem RFx", "tom": "cinza", "padrao": True},
)
STEP_CHART_STATES: Mapping[str, str] = {
    calculations.STEP_DONE: "concluido",
    calculations.STEP_CURRENT: "andamento",
    calculations.STEP_FUTURE: "futuro",
}


@dataclass(frozen=True)
class ActionButton:
    """One action the ficha offers for the current stage, as the modal opener reads it."""

    name: str
    label: str
    icon: str
    tone: str
    url: str


def _process_modal_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A refusal inside the process modal: the message where the person is looking."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=PROCESS_MODAL_TARGET,
        status_code=_error_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


# ── The list and the ficha ───────────────────────────────────────────────────────────────────


@bp.route(route="suprimentos/processos", methods=["GET"])
@fragment_route(access=READ)
def process_list(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The processes: KPIs, toolbar, the Etapas chart and the ficha of the selected one."""
    return _process_screen(
        req,
        session,
        context,
        filters=validation.parse_process_filters(req.params),
        selected=validation.parse_id(req.params.get("pacote")),
    )


@bp.route(route="suprimentos/processos/excel", methods=["GET"])
@file_route(access=READ)
def process_list_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the list, with the equalization map when a process is named."""
    return excel_response(_process_document(req, session, context))


@bp.route(route="suprimentos/processos/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def process_list_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document."""
    return printable_response(_process_document(req, session, context), req)


@bp.route(route="suprimentos/processos/ficha", methods=["GET"])
@fragment_route(access=READ)
def process_sheet(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The ficha of one process, for the click on a line of the chart."""
    package_id = validation.parse_id(req.params.get("pacote"))
    ficha = (
        None
        if package_id is None
        else _ficha_context(
            session,
            context,
            package_id=package_id,
            consulta=(req.params.get("consulta") or "").strip(),
        )
    )
    if ficha is None:
        raise InvalidDataError(PROCESS_NOT_FOUND_MESSAGE)
    return AlpineAjaxResponse(
        template_name=FICHA_TEMPLATE,
        context={"ficha": ficha},
        request=req,
        target_id=FICHA_TARGET,
    )


def _process_screen(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: validation.ProcessFilters,
    selected: int | None = None,
    after: _After | None = None,
) -> func.HttpResponse:
    """The screen fragment for the filters, with the ficha of the selected process."""
    listing = service.list_processes(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=calendario.today(),
    )
    consulta = _process_query_string(filters)
    ficha = (
        None
        if selected is None
        else _ficha_context(session, context, package_id=selected, consulta=consulta)
    )
    return AlpineAjaxResponse(
        template_name=PROCESS_TEMPLATE,
        context={
            "listagem": listing,
            "filtros": filters,
            "kpis": _process_kpi_cards(listing),
            "grafico": _chart_data(
                listing, consulta=consulta, portfolio=context.scope.is_portfolio
            ),
            "ficha": ficha,
            "link_limpar": _process_address(filters, busca=""),
            "url_excel": _process_address(filters, path=f"{PROCESS_ROUTE}/excel"),
            "url_pdf": _process_address(filters, path=f"{PROCESS_ROUTE}/imprimivel"),
            "consulta": consulta,
            "parametro_consulta": urlencode({"consulta": consulta}),
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "portfolio": context.scope.is_portfolio,
            "formatar_data": _format_date,
            "formatar_moeda": _format_money,
            **(after.extra if after else {}),
        },
        request=req,
        target_id=PROCESS_TARGET,
        toast=after.notice if after else None,
    )


def _ficha_context(
    session: Session, context: RequestContext, *, package_id: int, consulta: str
) -> dict[str, object] | None:
    """Everything the ficha prints, or ``None`` when the package is not in the scope."""
    today = calendario.today()
    line = service.find_process(
        session,
        user=context.user,
        scope=context.scope,
        package_id=package_id,
        reference_date=today,
    )
    if line is None:
        return None
    return {
        "linha": line,
        "acoes": _stage_actions(line, consulta=consulta),
        "anexos": _proposal_attachments(session, context, line, today=today),
        "documento": _emitted_document(line),
        "consulta": consulta,
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "url_excel": f"{PROCESS_ROUTE}/excel?pacote={line.package_id}",
        "url_pdf": f"{PROCESS_ROUTE}/imprimivel?pacote={line.package_id}",
        "mas_url": f"/suprimentos/mas?{urlencode({'busca': line.code})}",
        "formatar_data": _format_date,
        "formatar_moeda": _format_money,
        "formatar_numero": _format_decimal,
    }


def _emitted_document(line: service.ProcessLine) -> dict[str, str] | None:
    """The order or contract the emission created, as the ficha links to it."""
    if line.order_number:
        return {
            "tipo": "Pedido",
            "numero": line.order_number,
            "url": f"/suprimentos/diligenciamento?{urlencode({'pedido': line.order_number})}",
        }
    if line.contract_number:
        return {
            "tipo": "Contrato",
            "numero": line.contract_number,
            "url": f"/financeiro/contrato?{urlencode({'numero': line.contract_number})}",
        }
    return None


def _proposal_attachments(
    session: Session, context: RequestContext, line: service.ProcessLine, *, today: date
) -> dict[int, tuple[str, ...]]:
    """The names of the attachments of each proposal, read by the platform facade (D5a)."""
    names: dict[int, tuple[str, ...]] = {}
    for proposal in line.proposals:
        panel = attachments.panel(
            session,
            user=context.user,
            origin_table=service.PROPOSAL_ATTACHMENT_TABLE,
            origin_record_id=proposal.id,
            reference_date=today,
        )
        names[proposal.id] = tuple(entry.name for entry in panel.entries)
    return names


def _stage_actions(line: service.ProcessLine, *, consulta: str) -> tuple[ActionButton, ...]:
    """The buttons the ficha offers for the stage the process is in."""
    buttons: list[ActionButton] = []
    for name, label, icon, tone in STAGE_ACTIONS.get(line.stage, ()):
        if name == "requisicao":
            url = f"{PROCESS_ROUTE}/requisicao?pacote={line.package_id}"
        else:
            url = f"{PROCESS_ROUTE}/{line.package_id}/acao/{name}"
        if name == "emitir":
            label = "Emitir contrato" if calculations.is_service(line.kind) else "Emitir pedido"
        separator = "&" if "?" in url else "?"
        buttons.append(
            ActionButton(
                name=name,
                label=label,
                icon=icon,
                tone=tone,
                url=url + (f"{separator}{consulta}" if consulta else ""),
            )
        )
    return tuple(buttons)


def _chart_data(
    listing: service.ProcessListing, *, consulta: str, portfolio: bool
) -> dict[str, object]:
    """The Etapas chart of the list: one line per process with its nine steps."""
    return {
        "titulo": "Processos de compra (RFx)",
        "rotulo_linhas": "Pacote",
        "etapas": [{"id": key, "rotulo": label} for key, label in calculations.PROCESS_STEPS],
        "estados": [dict(state) for state in CHART_STATES],
        "colunas_datas": ["Adjudicação (LB)", "Adjudicação"],
        "linhas": [
            _chart_line(line, consulta=consulta, portfolio=portfolio) for line in listing.lines
        ],
    }


def _chart_line(line: service.ProcessLine, *, consulta: str, portfolio: bool) -> dict[str, object]:
    """One line of the chart: the tags, the general state and the nine steps with their dates."""
    if line.stage_index >= len(calculations.PROCESS_STEPS):
        general = "concluido"
    elif line.stage == calculations.STAGE_PLANNED:
        general = "na"
    else:
        general = "andamento"
    adjudication = line.adjudication_real or line.adjudication_forecast
    return {
        "id": line.package_id,
        "titulo": f"{line.code} — {line.scope}",
        "tags": _chart_tags(line, portfolio=portfolio),
        "estado": general,
        "etapas": {
            step.key: {
                "estado": STEP_CHART_STATES.get(step.situation, "futuro"),
                "data": _iso_of_step(step),
                "previsto": step.date is None and step.planned is not None,
            }
            for step in line.steps
        },
        "datas": [
            line.adjudication_plan.isoformat() if line.adjudication_plan else None,
            adjudication.isoformat() if adjudication else None,
        ],
        "href": f"{PROCESS_ROUTE}/ficha?pacote={line.package_id}"
        + (f"&{consulta}" if consulta else ""),
    }


def _chart_tags(line: service.ProcessLine, *, portfolio: bool) -> list[str]:
    """The short tags of the line: the RFx, the proposals, the best one and the approval band."""
    tags: list[str] = []
    if portfolio:
        tags.append(line.project_label.split(" · ")[0])
    if line.number:
        tags.append(line.number)
    tags.append(f"{line.received_count} propostas · {line.approved_count} aprovadas")
    if line.best is not None:
        score = format_value(ValueKind.DECIMAL, line.best.final_score, 1)
        tags.append(f"{line.best.name} · nota {score}")
    else:
        tags.append(f"estimativa {format_value(ValueKind.MONEY, line.estimate_cents)}")
    if line.approval_band:
        tags.append(f"Alçada: {line.approval_band}")
    return tags


def _iso_of_step(step: service.ProcessStep) -> str | None:
    value = step.date or step.planned
    return value.isoformat() if value else None


def _process_kpi_cards(listing: service.ProcessListing) -> list[KpiCard]:
    summary = listing.summary
    minimum = summary.minimum_proposals
    mean = summary.mean_valid_proposals
    share = summary.single_supplier_share
    return [
        KpiCard(
            label="Em andamento",
            icon="file",
            tone="info",
            value=summary.in_progress,
            reference=f"Previsto: {summary.expected_in_progress}",
            footer=f"{summary.total} pacotes no plano",
            url="",
            active=False,
        ),
        KpiCard(
            label="Aguardando aprovação",
            icon="clock",
            tone="warn" if summary.awaiting_approval else "ok",
            value=summary.awaiting_approval,
            reference="Esperado: 0",
            footer="recomendação na alçada",
            url="",
            active=False,
        ),
        KpiCard(
            label="Propostas válidas por processo",
            icon="checkCircle",
            tone="ok" if mean is not None and mean >= minimum else "warn",
            value="—" if mean is None else format_value(ValueKind.DECIMAL, mean, 1),
            reference=f"Meta: ≥ {minimum}",
            footer="",
            url="",
            active=False,
        ),
        KpiCard(
            label="Fornecedor único",
            icon="person",
            tone="warn" if summary.single_supplier_count else "ok",
            value="—" if share is None else f"{format_value(ValueKind.DECIMAL, share, 1)}%",
            reference="Esperado: 0%",
            footer=f"{summary.single_supplier_count} processos com justificativa",
            url="",
            active=False,
        ),
        KpiCard(
            label="Ciclo de compra",
            icon="refresh",
            tone="neutro",
            value="—" if summary.cycle_mean_days is None else summary.cycle_mean_days,
            reference=(
                "Linha de base: ·"
                if summary.baseline_cycle_days is None
                else f"Linha de base: {summary.baseline_cycle_days} dias"
            ),
            footer="requisição até o pedido emitido",
            url="",
            active=False,
        ),
    ]


def _process_filters_of(consulta: str) -> validation.ProcessFilters:
    return validation.parse_process_filters(dict(parse_qsl(consulta)))


def _process_query_string(filters: validation.ProcessFilters) -> str:
    """The filters as the consulta parameter of the forms and links (without the page)."""
    values = {"busca": filters.search}
    if filters.situation != "andamento":
        values["situacao"] = "todos"
    return urlencode({name: value for name, value in values.items() if value})


def _process_address(
    filters: validation.ProcessFilters, *, path: str = PROCESS_ROUTE, **changes: object
) -> str:
    """The address of the list with the current filters and the informed changes."""
    values: dict[str, object] = {
        "busca": filters.search,
        "situacao": "" if filters.situation == "andamento" else "todos",
    }
    values.update(changes)
    clean = {name: str(value) for name, value in values.items() if value not in ("", None)}
    query = urlencode(clean)
    return f"{path}?{query}" if query else path


def _process_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """The document of the screen for the filters of the request; the only place with the clock."""
    filters = validation.parse_process_filters(req.params)
    today = calendario.today()
    listing = service.list_processes(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=today,
    )
    package_id = validation.parse_id(req.params.get("pacote"))
    line = (
        None
        if package_id is None
        else service.find_process(
            session,
            user=context.user,
            scope=context.scope,
            package_id=package_id,
            reference_date=today,
        )
    )
    return export.build_process_document(
        listing=listing,
        line=line,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


# ── Nova requisição ──────────────────────────────────────────────────────────────────────────


@bp.route(route="suprimentos/processos/requisicao", methods=["GET"])
@fragment_route(access=WRITE, on_error=_process_modal_error)
def process_requisition_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of Nova requisição: the packages of the plan still without a requisition."""
    return _requisition_form(
        req,
        session,
        context,
        values={"pacote": (req.params.get("pacote") or "").strip()},
        errors={},
        consulta=(req.params.get("consulta") or "").strip(),
    )


@bp.route(route="suprimentos/processos/requisicao", methods=["POST"])
@fragment_route(access=WRITE, on_error=_process_modal_error)
def process_requisition_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registrar requisição: the real date of the milestone, or the form again with the messages."""
    form = req.form
    package_id = validation.parse_id(form.get("pacote"))
    data = _requisition_input(form)
    today = calendario.today()
    saved: list[service.ProcessSave] = []
    error = (
        InvalidDataError({"pacote": validation.PACKAGE_NOT_FOUND})
        if package_id is None
        else _attempt(
            session,
            lambda: saved.append(
                service.start_requisition(
                    session,
                    user=context.user,
                    scope=context.scope,
                    package_id=package_id,
                    data=data,
                    reference_date=today,
                )
            ),
        )
    )
    if error is not None or not saved:
        return _requisition_form(
            req,
            session,
            context,
            values=dict(form),
            errors=_field_errors(error),
            consulta=form.get("consulta", ""),
            status_code=_form_status(error),
        )
    return _process_screen(
        req,
        session,
        context,
        filters=_process_filters_of(form.get("consulta", "")),
        selected=saved[0].package_id,
        after=_After(REQUISITION_NOTICE.format(code=saved[0].code), {}),
    )


def _requisition_form(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    consulta: str = "",
    status_code: int = 200,
) -> func.HttpResponse:
    today = calendario.today()
    packages = service.planned_packages(
        session, user=context.user, scope=context.scope, reference_date=today
    )
    return AlpineAjaxResponse(
        template_name=REQUISITION_TEMPLATE,
        context={
            "valores": dict(values),
            "erros": dict(errors),
            "pacotes": packages,
            "consulta": consulta,
            "referencia": today.isoformat(),
            "formatar_data": _format_date,
        },
        request=req,
        target_id=PROCESS_MODAL_TARGET,
        status_code=status_code,
    )


# ── The actions of the flow ──────────────────────────────────────────────────────────────────


@bp.route(route="suprimentos/processos/{pacote_id}/acao/{nome}", methods=["GET"])
@fragment_route(access=WRITE, on_error=_process_modal_error)
def process_action_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of one action of the flow, for the stage the process is in."""
    line = _action_line(session, context, req)
    name = _action_name(req)
    return _action_form(req, session, context, name=name, line=line, values={}, errors={})


@bp.route(route="suprimentos/processos/{pacote_id}/acao/{nome}", methods=["POST"])
@fragment_route(access=WRITE, on_error=_process_modal_error)
def process_action_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Run one action of the flow, or answer the form again with the messages."""
    line = _action_line(session, context, req)
    name = _action_name(req)
    form = req.form
    error, saved = _run_action(
        req, session, context, name=name, line=line, form=form, today=calendario.today()
    )
    if error is not None or saved is None:
        return _action_form(
            req,
            session,
            context,
            name=name,
            line=line,
            values=dict(form),
            errors=_field_errors(error),
            status_code=_form_status(error),
        )
    return _process_screen(
        req,
        session,
        context,
        filters=_process_filters_of(form.get("consulta", "")),
        selected=line.package_id,
        after=_After(_action_notice(name, saved), {}),
    )


@dataclass(frozen=True)
class _ActionCall:
    """One action of the flow being run: what its runner needs to parse the form and call."""

    session: Session
    context: RequestContext
    line: service.ProcessLine
    form: Mapping[str, str]
    today: date
    file_name: str | None = None
    content: bytes = b""


ActionRunner = Callable[[_ActionCall], service.ProcessSave]


def _run_action(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    name: str,
    line: service.ProcessLine,
    form: Mapping[str, str],
    today: date,
) -> tuple[DomainError | None, service.ProcessSave | None]:
    """Parse the form of the action, call the facade inside a savepoint and answer what happened."""
    runner = ACTION_RUNNERS.get(name)
    if runner is None:
        raise InvalidDataError({"geral": UNKNOWN_ACTION_MESSAGE})
    file_name: str | None = None
    content = b""
    if name == "proposta":
        sent = req.files.get(attachments.FILE_FIELD)
        if sent is not None:
            file_name = sent.filename
            content = sent.stream.read()
    call = _ActionCall(
        session=session,
        context=context,
        line=line,
        form=form,
        today=today,
        file_name=file_name,
        content=content,
    )
    saved: list[service.ProcessSave] = []
    error = _attempt(session, lambda: saved.append(runner(call)))
    return error, (saved[0] if saved else None)


def _run_rfx(call: _ActionCall) -> service.ProcessSave:
    return service.issue_rfx(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_rfx_input(call.form),
        reference_date=call.today,
    )


def _run_proposal(call: _ActionCall) -> service.ProcessSave:
    return service.register_proposal(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_proposal_input(call.form),
        reference_date=call.today,
        file_name=call.file_name,
        content=call.content,
    )


def _run_closing(call: _ActionCall) -> service.ProcessSave:
    return service.close_receipt(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_closing_input(call.form),
        reference_date=call.today,
    )


def _run_technical(call: _ActionCall) -> service.ProcessSave:
    return service.equalize_technically(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_technical_input(call.form, call.line),
        reference_date=call.today,
    )


def _run_commercial(call: _ActionCall) -> service.ProcessSave:
    return service.equalize_commercially(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_commercial_input(call.form),
        reference_date=call.today,
    )


def _run_negotiation(call: _ActionCall) -> service.ProcessSave:
    return service.register_negotiation(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_negotiation_input(call.form),
        reference_date=call.today,
    )


def _run_recommendation(call: _ActionCall) -> service.ProcessSave:
    return service.recommend_award(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_recommendation_input(call.form),
        reference_date=call.today,
    )


def _run_return(call: _ActionCall) -> service.ProcessSave:
    return service.return_recommendation(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_return_input(call.form),
        reference_date=call.today,
    )


def _run_approval(call: _ActionCall) -> service.ProcessSave:
    return service.approve_award(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_approval_input(call.form),
        reference_date=call.today,
    )


def _run_emission(call: _ActionCall) -> service.ProcessSave:
    return service.emit_order_or_contract(
        call.session,
        user=call.context.user,
        scope=call.context.scope,
        package_id=call.line.package_id,
        data=_emission_input(call.form),
        reference_date=call.today,
    )


ACTION_RUNNERS: Mapping[str, ActionRunner] = {
    "rfx": _run_rfx,
    "proposta": _run_proposal,
    "encerrar-recebimento": _run_closing,
    "equalizacao-tecnica": _run_technical,
    "equalizacao-comercial": _run_commercial,
    "negociacao": _run_negotiation,
    "recomendacao": _run_recommendation,
    "devolver": _run_return,
    "aprovar": _run_approval,
    "emitir": _run_emission,
}


def _action_notice(name: str, saved: service.ProcessSave) -> str:
    if name == "rfx":
        return RFX_NOTICE.format(number=saved.number)
    if name == "proposta":
        return PROPOSAL_NOTICE.format(number=saved.number)
    if name == "emitir":
        notice = CONTRACT_NOTICE if (saved.document or "").startswith("CT-") else ORDER_NOTICE
        return notice.format(document=saved.document)
    notices = {
        "encerrar-recebimento": CLOSING_NOTICE,
        "equalizacao-tecnica": TECHNICAL_NOTICE,
        "equalizacao-comercial": COMMERCIAL_NOTICE,
        "negociacao": NEGOTIATION_NOTICE,
        "recomendacao": RECOMMENDATION_NOTICE,
        "devolver": RETURN_NOTICE,
        "aprovar": APPROVAL_NOTICE,
    }
    return notices.get(name, "")


def _action_line(
    session: Session, context: RequestContext, req: func.HttpRequest
) -> service.ProcessLine:
    package_id = validation.parse_id(req.route_params.get("pacote_id"))
    line = (
        None
        if package_id is None
        else service.find_process(
            session,
            user=context.user,
            scope=context.scope,
            package_id=package_id,
            reference_date=calendario.today(),
        )
    )
    if line is None:
        raise InvalidDataError(PROCESS_NOT_FOUND_MESSAGE)
    return line


def _action_name(req: func.HttpRequest) -> str:
    name = (req.route_params.get("nome") or "").strip()
    if name not in ACTION_TEMPLATES:
        raise InvalidDataError({"geral": UNKNOWN_ACTION_MESSAGE})
    return name


def _action_form(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    name: str,
    line: service.ProcessLine,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status_code: int = 200,
) -> func.HttpResponse:
    """The modal body of one action, filled in, for the GET and for a refusal."""
    today = calendario.today()
    consulta = (values.get("consulta") or req.params.get("consulta") or "").strip()
    extra = _action_context(session, context, name=name, line=line, today=today)
    return AlpineAjaxResponse(
        template_name=ACTION_TEMPLATES[name],
        context={
            "valores": dict(values),
            "erros": dict(errors),
            "linha": line,
            "consulta": consulta,
            "referencia": today.isoformat(),
            "formatar_data": _format_date,
            "formatar_moeda": _format_money,
            "formatar_numero": _format_decimal,
            **extra,
        },
        request=req,
        target_id=PROCESS_MODAL_TARGET,
        status_code=status_code,
    )


def _action_context(
    session: Session,
    context: RequestContext,
    *,
    name: str,
    line: service.ProcessLine,
    today: date,
) -> dict[str, object]:
    """What each action form needs besides the common values: choices and previews."""
    builders = {
        "rfx": _rfx_context,
        "proposta": _proposal_context,
        "encerrar-recebimento": _closing_context,
        "equalizacao-tecnica": _technical_context,
        "equalizacao-comercial": _commercial_context,
        "negociacao": _negotiation_context,
        "recomendacao": _recommendation_context,
        "devolver": _return_context,
        "aprovar": _approval_context,
        "emitir": _emission_context,
    }
    builder = builders.get(name)
    return builder(session, context, line, today) if builder is not None else {}


def _rfx_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    options = service.process_options(
        session, user=context.user, scope=context.scope, reference_date=today
    )
    propostas = line.step("propostas")
    return {
        "fornecedores": tuple(
            choice for choice in options.suppliers if choice.situation != calculations.BLOCKED
        ),
        "prazo_padrao": propostas.planned if propostas is not None else None,
    }


def _proposal_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    options = service.process_options(
        session, user=context.user, scope=context.scope, reference_date=today
    )
    return {
        "empresas": options.companies,
        "convidados": tuple(
            invitee.name for invitee in line.invitees if invitee.company_id is not None
        ),
    }


def _closing_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    del session, context, today
    return {
        "recebidas": line.received_count,
        "minimo": line.minimum,
        "abaixo": line.received_count < line.minimum and not line.single_supplier,
    }


def _technical_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    del line
    options = service.process_options(
        session, user=context.user, scope=context.scope, reference_date=today
    )
    return {"pessoas": options.people}


def _commercial_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    del session, context, today
    return {
        "peso_tecnico": line.weight_technical,
        "peso_comercial": line.weight_commercial,
        "propostas_dados": [
            {
                "fornecedor": proposal.name,
                "valor": proposal.value_cents,
                "notaTecnica": proposal.technical_score,
            }
            for proposal in line.proposals
            if proposal.technically_approved
        ],
    }


def _negotiation_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    del session, context, today
    return {
        "aprovadas": tuple(proposal for proposal in line.proposals if proposal.technically_approved)
    }


def _recommendation_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    """The approved proposals of the ranking and the saldo a comprometer of the EAC item."""
    del session, context, today
    best = line.best
    suggested = (
        format_value(ValueKind.MONEY, best.negotiated_cents or best.value_cents)
        if best is not None
        else ""
    )
    return {
        "aprovadas": tuple(
            proposal for proposal in line.proposals if proposal.technically_approved
        ),
        "melhor": best,
        "alcada": line.approval_band,
        "saldo": line.eac_balance_cents,
        "valor_sugerido": suggested,
    }


def _return_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    del session, context, line, today
    return {}


def _approval_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    """The people of the register for the approver select, with the recommendation in the line."""
    del line
    options = service.process_options(
        session, user=context.user, scope=context.scope, reference_date=today
    )
    return {"pessoas": options.people}


def _emission_context(
    session: Session, context: RequestContext, line: service.ProcessLine, today: date
) -> dict[str, object]:
    """What the emission form needs: the people for the fiscal and the deadline of the proposal."""
    options = service.process_options(
        session, user=context.user, scope=context.scope, reference_date=today
    )
    original = next(
        (
            proposal
            for proposal in line.proposals
            if line.recommendation is not None
            and proposal.company_id == line.recommendation.company_id
        ),
        None,
    )
    return {
        "pessoas": options.people,
        "servico": calculations.is_service(line.kind),
        "proposta": original,
    }


# ── Reading the forms of the actions ─────────────────────────────────────────────────────────


def _requisition_input(form: Mapping[str, str]) -> RequisitionInput:
    return RequisitionInput(
        date=validation.parse_date(form.get("data")),
        document=form.get("documento", ""),
        observation=form.get("observacao", ""),
    )


def _rfx_input(form: Mapping[str, str]) -> RfxInput:
    return RfxInput(
        date=validation.parse_date(form.get("data")),
        deadline=validation.parse_date(form.get("dataLimite")),
        weight_technical=validation.parse_points(form.get("pesoTecnico")),
        weight_commercial=validation.parse_points(form.get("pesoComercial")),
        invitees=_posted_ids(form, "convidados"),
        other_invitees=validation.names_of(form.get("outros", "")),
        single_supplier=validation.parse_flag(form.get("unico")),
        single_justification=form.get("justUnico", ""),
    )


def _proposal_input(form: Mapping[str, str]) -> ProposalInput:
    return ProposalInput(
        company_id=validation.parse_id(form.get("empresa")),
        name=form.get("nome", ""),
        received=validation.parse_date(form.get("data")),
        value_cents=validation.parse_money(form.get("valor", "")),
        deadline_days=validation.parse_positive_int(form.get("prazo")),
        validity=validation.parse_date(form.get("validade")),
    )


def _closing_input(form: Mapping[str, str]) -> ClosingInput:
    return ClosingInput(
        date=validation.parse_date(form.get("data")),
        justification=form.get("justificativa", ""),
    )


def _technical_input(form: Mapping[str, str], line: service.ProcessLine) -> TechnicalInput:
    evaluations = tuple(
        TechnicalEvaluation(
            proposal_id=proposal.id,
            score=validation.parse_points(form.get(f"nota_{proposal.id}")),
            approved=validation.parse_flag(form.get(f"aprovada_{proposal.id}")),
            deviations=form.get(f"desvios_{proposal.id}", ""),
            version=(form.get(f"versao_{proposal.id}") or "").strip() or None,
        )
        for proposal in line.proposals
    )
    return TechnicalInput(
        date=validation.parse_date(form.get("data")),
        evaluations=evaluations,
        responsible_id=validation.parse_id(form.get("responsavel")),
        opinion=form.get("parecer", ""),
        justification=form.get("justificativa", ""),
    )


def _commercial_input(form: Mapping[str, str]) -> CommercialInput:
    return CommercialInput(
        date=validation.parse_date(form.get("data")),
        weight_technical=validation.parse_points(form.get("pesoTecnico")),
        weight_commercial=validation.parse_points(form.get("pesoComercial")),
        version=(form.get("versao") or "").strip() or None,
    )


def _negotiation_input(form: Mapping[str, str]) -> NegotiationInput:
    return NegotiationInput(
        proposal_id=validation.parse_id(form.get("proposta")),
        value_cents=validation.parse_money(form.get("valor", "")),
        date=validation.parse_date(form.get("data")),
        observation=form.get("observacao", ""),
    )


def _recommendation_input(form: Mapping[str, str]) -> RecommendationInput:
    return RecommendationInput(
        proposal_id=validation.parse_id(form.get("proposta")),
        value_cents=validation.parse_money(form.get("valor", "")),
        date=validation.parse_date(form.get("data")),
        justification=form.get("justificativa", ""),
    )


def _return_input(form: Mapping[str, str]) -> ReturnInput:
    return ReturnInput(reason=form.get("motivo", ""))


def _approval_input(form: Mapping[str, str]) -> ApprovalInput:
    return ApprovalInput(
        approver_id=validation.parse_id(form.get("aprovador")),
        date=validation.parse_date(form.get("data")),
        opinion=form.get("parecer", ""),
    )


def _emission_input(form: Mapping[str, str]) -> EmissionInput:
    return EmissionInput(
        date=validation.parse_date(form.get("data")),
        deadline_days=validation.parse_positive_int(form.get("prazo")),
        start=validation.parse_date(form.get("inicio")),
        end=validation.parse_date(form.get("termino")),
        fiscal_id=validation.parse_id(form.get("fiscal")),
        retention_pct=validation.parse_points(form.get("retencao")),
    )


def _posted_ids(form: Mapping[str, object], field: str) -> tuple[int, ...]:
    """The repeated ids of a multi-select of the form, without the invalid ones."""
    getlist = getattr(form, "getlist", None)
    if getlist is None:
        return ()
    return tuple(
        parsed for raw in getlist(field) if (parsed := validation.parse_id(raw)) is not None
    )
