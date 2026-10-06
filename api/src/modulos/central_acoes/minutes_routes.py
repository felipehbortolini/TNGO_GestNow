"""Routes of the minutes of the Central de Ações: Atas, nova ata and the ficha (D14, ISSUE-021).

Prefix ``/api/central-acoes/``. The list is one fragment (``atas-conteudo``) that is asked again
with the search in the query; the ficha is another (``ata-ficha``). The forms open in a modal
whose body is a fragment too: a GET draws the form, a POST saves and answers the refreshed ficha
(or, for a new ata, redirects to its ficha); a refusal (422, 409, 403) answers the form again,
filled in, with the message.

* ``GET  atas``                         the list (search and page by query);
* ``GET  atas/excel`` and ``atas/imprimivel``   the two exports of what the list shows;
* ``GET  atas/nova``                    the form of a new ata (the scope must be a project);
* ``POST atas``                         generates the ata and goes to its ficha (422 by field);
* ``GET  ata?id=``                      the ficha: data of the meeting and the attendance list;
* ``GET  ata/excel`` and ``ata/imprimivel``     the two exports of the ficha;
* ``GET/POST ata/empresas``             main and executing companies of the ata;
* ``GET/POST ata/convidados``           search and add guests to the attendance list;
* ``GET/POST ata/retirar``              take a person off the list (refused with an open action).

The rules are in ``minutes_service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, origin_links, rbac
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
from src.core.responses import AlpineAjaxResponse, redirect_to
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.central_acoes import minutes_export, minutes_service, validation
from src.modulos.central_acoes.minutes_service import MinutesSheet
from src.modulos.central_acoes.validation import (
    AttendanceRequest,
    CompaniesRequest,
    MinutesFilters,
    NewMinutes,
)
from src.modulos.configuracoes import service as configuracoes

bp = func.Blueprint()

MODULE = "central_acoes"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

LIST_TARGET = "atas-conteudo"
LIST_MODAL_TARGET = "atas-modal-corpo"
SHEET_TARGET = "ata-ficha"
SHEET_MODAL_TARGET = "ata-modal-corpo"

LIST_ROUTE = "/api/central-acoes/atas"
SHEET_ROUTE = "/api/central-acoes/ata"
SHEET_SCREEN = "central_acoes/ata"

LIST_TEMPLATE = "central_acoes/atas.html"
NEW_TEMPLATE = "central_acoes/atas_nova.html"
SHEET_TEMPLATE = "central_acoes/ata.html"
NOT_FOUND_TEMPLATE = "central_acoes/ata_nao_encontrada.html"
COMPANIES_TEMPLATE = "central_acoes/ata_empresas.html"
GUESTS_TEMPLATE = "central_acoes/ata_convidados.html"
WITHDRAW_TEMPLATE = "central_acoes/ata_retirar.html"

TAB_DATA = "dados"
TAB_ATTENDANCE = "presenca"
TABS = (TAB_DATA, TAB_ATTENDANCE)

CREATED_NOTICE = "Ata gerada."
COMPANIES_NOTICE = "Empresas atualizadas."
GUESTS_NOTICE = "Convidados adicionados."
WITHDRAWN_NOTICE = "Participante retirado."
INVALID_MINUTES_MESSAGE = "Informe a ata."
GUEST_LIST_LIMIT = 100

NEW_FORM_FIELDS = (
    "data",
    "tipo_reuniao",
    "diretoria",
    "unidade",
    "elaborado_por",
    "assunto",
    "empresa_principal",
)


def _error_status(error: DomainError) -> int:
    """403, 409 for a stale screen, 422 for data that does not hold up."""
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


def _modal_error(target: str) -> Callable[[func.HttpRequest, DomainError], func.HttpResponse]:
    """A refusal inside the modal: the message in the modal body, where the person is looking."""

    def render(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
        messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
        return AlpineAjaxResponse(
            template_name="comum/erro.html",
            context={"mensagens": messages},
            request=req,
            target_id=target,
            status_code=_error_status(error),
            toast=messages[0] if messages else "Não foi possível concluir.",
            toast_tipo="erro",
        )

    return render


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


def _format_date(value: date | None) -> str:
    """``25/09/2026``; the dash when there is no date."""
    return "—" if value is None else format_value(ValueKind.DATE, value)


def _sheet_address(minutes_id: int, project_id: int | None = None) -> str:
    """The public address of the ficha; with the project when the scope has to follow."""
    parameters: dict[str, str | int] = {"id": minutes_id}
    if project_id is not None:
        parameters["projeto"] = project_id
    return origin_links.link_to_screen(SHEET_SCREEN, **parameters) or ""


def _id_of(req: func.HttpRequest, name: str = "id") -> int:
    raw = req.form.get(name) if req.method == "POST" else req.params.get(name)
    parsed = validation.parse_id(raw)
    if parsed is None:
        raise InvalidDataError(INVALID_MINUTES_MESSAGE)
    return parsed


def _tab_of(req: func.HttpRequest) -> str:
    raw = (req.form.get("aba") if req.method == "POST" else req.params.get("aba")) or ""
    return raw if raw in TABS else TAB_DATA


# ── The list ─────────────────────────────────────────────────────────────────────────────────


@bp.route(route="central-acoes/atas", methods=["GET"])
@fragment_route(access=READ)
def list_minutes_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The list of minutes: the latest revision of each one, with search and page."""
    filters = validation.parse_minutes_filters(req.params)
    listing = minutes_service.list_minutes(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=LIST_TEMPLATE,
        context=_list_context(listing, filters, context),
        request=req,
        target_id=LIST_TARGET,
    )


def _list_query(filters: MinutesFilters, *, page: int) -> str:
    parameters: dict[str, str] = {}
    if filters.search:
        parameters["busca"] = filters.search
    if page > 1:
        parameters["pagina"] = str(page)
    return urlencode(parameters)


def _list_address(filters: MinutesFilters, *, page: int, path: str = LIST_ROUTE) -> str:
    query = _list_query(filters, page=page)
    return f"{path}?{query}" if query else path


def _list_context(
    listing: minutes_service.MinutesListing, filters: MinutesFilters, context: RequestContext
) -> dict[str, object]:
    shown = MinutesFilters(search=filters.search, page=listing.page)
    start = (listing.page - 1) * validation.MINUTES_PAGE_SIZE
    return {
        "listagem": listing,
        "filtros": shown,
        "portfolio": context.scope.is_portfolio,
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "link_anterior": (_list_address(shown, page=listing.page - 1) if listing.page > 1 else ""),
        "link_proximo": (
            _list_address(shown, page=listing.page + 1) if listing.page < listing.page_count else ""
        ),
        "link_limpar": LIST_ROUTE,
        "url_excel": _list_address(shown, page=1, path=f"{LIST_ROUTE}/excel"),
        "url_pdf": _list_address(shown, page=1, path=f"{LIST_ROUTE}/imprimivel"),
        "url_nova": f"{LIST_ROUTE}/nova",
        "endereco_da_ficha": _sheet_address,
        "formatar_data": _format_date,
        "pagina_inicial": start + 1,
        "pagina_final": min(start + validation.MINUTES_PAGE_SIZE, listing.total),
    }


def _list_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    """The document of the list for the search of the request; the only place with the clock."""
    filters = validation.parse_minutes_filters(req.params)
    today = calendario.today()
    listing = minutes_service.list_minutes(
        session, user=context.user, scope=context.scope, filters=filters, reference_date=today
    )
    return minutes_export.build_list_document(
        listing=listing,
        search=filters.search,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


@bp.route(route="central-acoes/atas/excel", methods=["GET"])
@file_route(access=READ)
def minutes_list_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the list of minutes: what the screen lists."""
    return excel_response(_list_document(req, session, context))


@bp.route(route="central-acoes/atas/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def minutes_list_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_list_document(req, session, context), req)


# ── The new ata ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _NewForm:
    """What the form of a new ata prints: the project, what was typed and the refusal, if any."""

    project_label: str
    values: Mapping[str, object]
    errors: Mapping[str, str]
    status_code: int = 200


def _new_form(session: Session, req: func.HttpRequest, form: _NewForm) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=NEW_TEMPLATE,
        context={
            "valores": form.values,
            "erros": form.errors,
            "rotulo_do_projeto": form.project_label,
            "tipos_de_reuniao": validation.MEETING_TYPES,
            "unidades": configuracoes.list_organizational_units(session),
            "pessoas": configuracoes.list_person_options(session),
            "empresas": configuracoes.list_company_options(session),
            "limite_do_assunto": validation.MAX_SUBJECT_LENGTH,
            "action": LIST_ROUTE,
        },
        request=req,
        target_id=LIST_MODAL_TARGET,
        status_code=form.status_code,
    )


def _project_label(session: Session, project_id: int) -> str:
    project = configuracoes.find_project(session, project_id)
    return f"{project.code} · {project.name}" if project else ""


@bp.route(route="central-acoes/atas/nova", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error(LIST_MODAL_TARGET))
def new_minutes_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new ata, for the project of the scope (the Portfólio asks for the project)."""
    project_id = context.scope.require_project()
    values = {
        "data": calendario.today().isoformat(),
        "elaborado_por": str(context.user.person_id),
        "empresas": [],
    }
    return _new_form(
        session,
        req,
        _NewForm(project_label=_project_label(session, project_id), values=values, errors={}),
    )


def _new_minutes_of(req: func.HttpRequest, *, project_id: int) -> NewMinutes:
    form = req.form
    return NewMinutes(
        project_id=project_id,
        meeting_date=validation.parse_date(form.get("data")),
        meeting_type=(form.get("tipo_reuniao") or "").strip(),
        board=form.get("diretoria") or "",
        unit_id=validation.parse_id(form.get("unidade")),
        prepared_by_id=validation.parse_id(form.get("elaborado_por")),
        subject=form.get("assunto") or "",
        company_ids=validation.parse_ids(form.getlist("empresas")),
        main_company_id=validation.parse_id(form.get("empresa_principal")),
    )


@bp.route(route="central-acoes/atas", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error(LIST_MODAL_TARGET))
def create_minutes_route(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Generate the ata with the number of the project and go to its ficha (HU-051)."""
    project_id = context.scope.require_project()
    new = _new_minutes_of(req, project_id=project_id)
    created: list[minutes_service.MinutesRecord] = []
    today = calendario.today()
    error = _attempt(
        session,
        lambda: created.append(
            minutes_service.create_minutes(
                session, user=context.user, new=new, reference_date=today
            )
        ),
    )
    if error is not None:
        values: dict[str, object] = {field: req.form.get(field) or "" for field in NEW_FORM_FIELDS}
        values["empresas"] = list(req.form.getlist("empresas"))
        refused = _NewForm(
            project_label=_project_label(session, project_id),
            values=values,
            errors=_field_errors(error),
            status_code=_error_status(error),
        )
        return _new_form(session, req, refused)
    return redirect_to(_sheet_address(created[0].id, project_id))


# ── The ficha ────────────────────────────────────────────────────────────────────────────────


def _sheet_of(session: Session, context: RequestContext, minutes_id: int) -> MinutesSheet | None:
    return minutes_service.find_minutes(
        session, user=context.user, minutes_id=minutes_id, reference_date=calendario.today()
    )


def _sheet_context(sheet: MinutesSheet, context: RequestContext, *, tab: str) -> dict[str, object]:
    minutes_id = sheet.record.id
    can_write = rbac.can(context.user, Permission.WRITE)
    query = urlencode({"id": minutes_id})
    return {
        "ficha": sheet,
        "aba": tab,
        "pode_editar": can_write and sheet.is_latest,
        "url_excel": f"{SHEET_ROUTE}/excel?{query}",
        "url_pdf": f"{SHEET_ROUTE}/imprimivel?{query}",
        "url_empresas": f"{SHEET_ROUTE}/empresas?{urlencode({'id': minutes_id, 'aba': TAB_DATA})}",
        "url_convidados": f"{SHEET_ROUTE}/convidados?"
        + urlencode({"id": minutes_id, "aba": TAB_ATTENDANCE}),
        "endereco_de_retirada": lambda person_id: (
            f"{SHEET_ROUTE}/retirar?"
            + urlencode({"id": minutes_id, "pessoa": person_id, "aba": TAB_ATTENDANCE})
        ),
        "url_vigente": _sheet_address(sheet.latest_id),
        "formatar_data": _format_date,
    }


def _sheet_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    state: _ModalState,
    notice: str | None = None,
) -> func.HttpResponse:
    sheet = _sheet_of(session, context, state.minutes_id)
    if sheet is None:
        return AlpineAjaxResponse(
            template_name=NOT_FOUND_TEMPLATE,
            context={},
            request=req,
            target_id=SHEET_TARGET,
            status_code=404,
        )
    return AlpineAjaxResponse(
        template_name=SHEET_TEMPLATE,
        context=_sheet_context(sheet, context, tab=state.tab),
        request=req,
        target_id=SHEET_TARGET,
        toast=notice,
    )


@bp.route(route="central-acoes/ata", methods=["GET"])
@fragment_route(access=READ)
def minutes_sheet(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The ficha: the strip, the Dados da Reunião and the Lista de Presença."""
    parsed = validation.parse_id(req.params.get("id"))
    state = _ModalState(parsed or 0, _tab_of(req), {})
    return _sheet_response(req, session, context, state=state)


def _sheet_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    sheet = _sheet_of(session, context, _id_of(req))
    if sheet is None:
        raise InvalidDataError(minutes_service.NOT_FOUND_MESSAGE)
    return minutes_export.build_sheet_document(sheet=sheet, today=calendario.today())


@bp.route(route="central-acoes/ata/excel", methods=["GET"])
@file_route(access=READ)
def minutes_sheet_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the ficha: the data of the meeting, the companies and the attendance."""
    return excel_response(_sheet_document(req, session, context))


@bp.route(route="central-acoes/ata/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def minutes_sheet_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the ficha: what the PDF button mounts and prints."""
    return printable_response(_sheet_document(req, session, context), req)


# ── The modals of the ficha ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _ModalState:
    """What a modal form remembers: the ata, the tab to come back to and what was typed."""

    minutes_id: int
    tab: str
    values: Mapping[str, object]
    version: int | str | None = None


def _modal_context(
    sheet: MinutesSheet, state: _ModalState, error: DomainError | None
) -> dict[str, object]:
    stale = isinstance(error, VersionConflictError)
    version = sheet.record.version if stale or state.version is None else state.version
    return {
        "ficha": sheet,
        "aba": state.tab,
        "versao": version,
        "valores": dict(state.values),
        "erros": _field_errors(error),
    }


def _open_sheet(session: Session, context: RequestContext, minutes_id: int) -> MinutesSheet:
    sheet = _sheet_of(session, context, minutes_id)
    if sheet is None:
        raise InvalidDataError(minutes_service.NOT_FOUND_MESSAGE)
    if not sheet.is_latest:
        raise InvalidDataError(minutes_service.READ_ONLY_MESSAGE)
    return sheet


@dataclass(frozen=True)
class _ModalPage:
    """One modal form to draw: its template, what it remembers, extra data and the refusal."""

    template: str
    state: _ModalState
    extra: Mapping[str, object] | None = None
    error: DomainError | None = None


def _modal_form(
    req: func.HttpRequest, session: Session, context: RequestContext, page: _ModalPage
) -> func.HttpResponse:
    sheet = _open_sheet(session, context, page.state.minutes_id)
    page_context = _modal_context(sheet, page.state, page.error) | dict(page.extra or {})
    return AlpineAjaxResponse(
        template_name=page.template,
        context=page_context,
        request=req,
        target_id=SHEET_MODAL_TARGET,
        status_code=200 if page.error is None else _error_status(page.error),
    )


def _saved(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    state: _ModalState,
    notice: str,
) -> func.HttpResponse:
    return _sheet_response(req, session, context, state=state, notice=notice)


# Companies


def _company_extra(session: Session) -> dict[str, object]:
    return {"empresas": configuracoes.list_company_options(session)}


@bp.route(route="central-acoes/ata/empresas", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error(SHEET_MODAL_TARGET))
def companies_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The executing companies of the ata, with the main one."""
    sheet = _open_sheet(session, context, _id_of(req))
    values = {
        "empresa_principal": str(sheet.record.main_company_id or ""),
        "empresas": [str(company.id) for company in sheet.companies],
    }
    page = _ModalPage(
        COMPANIES_TEMPLATE,
        _ModalState(sheet.record.id, _tab_of(req), values),
        _company_extra(session),
    )
    return _modal_form(req, session, context, page)


@bp.route(route="central-acoes/ata/empresas", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error(SHEET_MODAL_TARGET))
def companies_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the companies; a company with an open action of its people is refused (HU-054)."""
    form = req.form
    request = CompaniesRequest(
        minutes_id=_id_of(req),
        main_company_id=validation.parse_id(form.get("empresa_principal")),
        company_ids=validation.parse_ids(form.getlist("empresas")),
        version=form.get("versao"),
    )
    error = _attempt(
        session,
        lambda: minutes_service.set_companies(session, user=context.user, request=request),
    )
    state = _ModalState(
        request.minutes_id,
        _tab_of(req),
        {
            "empresa_principal": form.get("empresa_principal") or "",
            "empresas": list(form.getlist("empresas")),
        },
        version=request.version,
    )
    if error is not None:
        page = _ModalPage(COMPANIES_TEMPLATE, state, _company_extra(session), error)
        return _modal_form(req, session, context, page)
    return _saved(req, session, context, state=state, notice=COMPANIES_NOTICE)


# Guests


def _guest_extra(
    session: Session, context: RequestContext, minutes_id: int, search: str
) -> dict[str, object]:
    candidates = minutes_service.guest_candidates(
        session, user=context.user, minutes_id=minutes_id, search=search
    )
    return {
        "candidatos": candidates[:GUEST_LIST_LIMIT],
        "total_de_candidatos": len(candidates),
        "limite": GUEST_LIST_LIMIT,
        "empresas_por_id": configuracoes.list_company_names(session),
        "busca": search,
    }


@bp.route(route="central-acoes/ata/convidados", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error(SHEET_MODAL_TARGET))
def guests_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The search of guests: the people of the register who are not in the list yet."""
    minutes_id = _id_of(req)
    search = (req.params.get("busca") or "").strip()[: validation.MAX_SEARCH_LENGTH]
    page = _ModalPage(
        GUESTS_TEMPLATE,
        _ModalState(minutes_id, _tab_of(req), {}),
        _guest_extra(session, context, minutes_id, search),
    )
    return _modal_form(req, session, context, page)


@bp.route(route="central-acoes/ata/convidados", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error(SHEET_MODAL_TARGET))
def guests_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Add the chosen people to the attendance list."""
    form = req.form
    request = AttendanceRequest(
        minutes_id=_id_of(req),
        person_ids=validation.parse_ids(form.getlist("pessoas")),
        version=form.get("versao"),
    )
    error = _attempt(
        session, lambda: minutes_service.add_guests(session, user=context.user, request=request)
    )
    state = _ModalState(request.minutes_id, _tab_of(req), {}, version=request.version)
    if error is not None:
        extra = _guest_extra(session, context, request.minutes_id, "")
        return _modal_form(req, session, context, _ModalPage(GUESTS_TEMPLATE, state, extra, error))
    return _saved(req, session, context, state=state, notice=GUESTS_NOTICE)


# Withdrawal


def _withdraw_extra(sheet: MinutesSheet, person_id: int) -> dict[str, object]:
    attendee = next((item for item in sheet.attendees if item.person.id == person_id), None)
    return {"participante": attendee, "pessoa_id": person_id}


@bp.route(route="central-acoes/ata/retirar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error(SHEET_MODAL_TARGET))
def withdraw_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The confirmation of taking a person off the attendance list."""
    sheet = _open_sheet(session, context, _id_of(req))
    page = _ModalPage(
        WITHDRAW_TEMPLATE,
        _ModalState(sheet.record.id, _tab_of(req), {}),
        _withdraw_extra(sheet, _id_of(req, "pessoa")),
    )
    return _modal_form(req, session, context, page)


@bp.route(route="central-acoes/ata/retirar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error(SHEET_MODAL_TARGET))
def withdraw_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Take the person off the list; refused with the message when she holds an open action."""
    minutes_id = _id_of(req)
    person_id = _id_of(req, "pessoa")
    version = req.form.get("versao")
    error = _attempt(
        session,
        lambda: minutes_service.remove_attendee(
            session,
            user=context.user,
            minutes_id=minutes_id,
            person_id=person_id,
            version=version,
        ),
    )
    state = _ModalState(minutes_id, _tab_of(req), {}, version=version)
    if error is not None:
        sheet = _open_sheet(session, context, minutes_id)
        extra = _withdraw_extra(sheet, person_id)
        page = _ModalPage(WITHDRAW_TEMPLATE, state, extra, error)
        return _modal_form(req, session, context, page)
    return _saved(req, session, context, state=state, notice=WITHDRAWN_NOTICE)
