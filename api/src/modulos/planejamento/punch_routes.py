"""Routes of the Punch list (ISSUE-049, HU-068, HU-069), prefix ``/api/planejamento/punch-list``.

One screen, built like the HSE screens: the content (filters, indicators, alert of blocked systems,
items and systems) is one fragment, and every form is a fragment that opens in a modal.

* ``GET  /``                     the content for the filters of the query (``situacao``, ``categoria``,
  ``sistema``, ``disciplina``, ``empresa``, ``busca``; ``item=`` opens the list on one code);
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same filters;
* ``GET  /filtros``              the modal Filtros;
* ``GET  /novo``, ``POST /novo``  the modal Novo item (needs a project);
* ``GET  /{item_id}/editar``, ``POST /{item_id}/editar``  edit an open item;
* ``POST /{item_id}/tratar``     Aberto goes to Em tratamento;
* ``GET  /{item_id}/enviar``, ``POST /{item_id}/enviar``  send to verification (evidence needed);
* ``GET  /{item_id}/verificar``, ``POST /{item_id}/verificar``  the modal Fechamento com verificação;
* ``GET  /{item_id}/cancelar``, ``POST /{item_id}/cancelar``  cancel with a justification.

The import of the spreadsheet is the platform's (``/api/importacao/punch-list``).

The routes read the request and draw the answer; every rule is in the facade
(``punch_service``). A refusal of the data (422) or of the version (409) draws the form again with
the messages under the fields; a refusal of the person (403) is the message in the modal.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.excel import excel_response
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import punch_calculations as calc
from src.modulos.planejamento import punch_export as export
from src.modulos.planejamento import punch_importers as importers
from src.modulos.planejamento import punch_service as service
from src.modulos.planejamento import punch_validation as validation

bp = func.Blueprint()

importers.register_importers()

MODULE = service.MODULE
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

BASE = "planejamento/punch-list"
API = f"/api/{BASE}"
SCREEN_TEMPLATE = "planejamento/punch_list.html"
FORM_TEMPLATE = "planejamento/punch_formulario.html"
CONTENT_TARGET = "punch-conteudo"
MODAL_TARGET = "punch-modal-corpo"
NOT_FOUND = "O endereço não indica um item válido."


@dataclass(frozen=True)
class FormScreen:
    """A form of the Punch list: where it posts, what it shows and what it remembers."""

    action: str
    kind: str
    fields: tuple[dict[str, Any], ...] = ()
    values: Mapping[str, str] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)
    item: service.PunchRow | None = None
    query: str = ""
    save_label: str = "Salvar"
    support_text: str = ""
    danger: bool = False
    status_code: int = 200


# ── The screen and the exports ───────────────────────────────────────────


@bp.route(route=BASE, methods=["GET"])
@fragment_route(access=READ)
def punch_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The content of the screen for the scope and the filters of the request."""
    return _screen_response(req, session, context, query=req.params)


@bp.route(route=f"{BASE}/excel", methods=["GET"])
@file_route(access=READ)
def punch_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the list the screen shows (same filters)."""
    return excel_response(_document(req, session, context))


@bp.route(route=f"{BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def punch_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


def _document(req: func.HttpRequest, session: Session, context: RequestContext):
    today = calendario.today()
    board = service.punch_board(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=today,
        filters=_filters_of(req.params),
    )
    return export.punch_document(
        board,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        generated_on=today,
    )


def _filters_of(params: Mapping[str, str]) -> service.PunchFilter:
    item = (params.get("item") or "").strip()
    situation = params.get("situacao")
    if situation is None:
        situation = "" if item else service.ALL_OPEN
    if situation not in ("", service.ALL_OPEN, *calc.SITUATIONS):
        situation = service.ALL_OPEN
    return service.PunchFilter(
        situation=situation,
        category=params.get("categoria", "") if params.get("categoria") in calc.CATEGORIES else "",
        system_id=validation.whole_number(params.get("sistema")),
        discipline=params.get("disciplina", "")
        if params.get("disciplina") in calc.DISCIPLINES
        else "",
        company_id=validation.whole_number(params.get("empresa")),
        search=item or (params.get("busca") or "").strip(),
    )


def _query_of(filters: service.PunchFilter) -> str:
    """The filters as a query string: what the buttons and the forms carry to reload the screen."""
    values = {
        "situacao": filters.situation,
        "categoria": filters.category,
        "sistema": "" if filters.system_id is None else filters.system_id,
        "disciplina": filters.discipline,
        "empresa": "" if filters.company_id is None else filters.company_id,
        "busca": filters.search,
    }
    return urlencode(values)


def _screen_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    query: Mapping[str, str],
    toast: str | None = None,
) -> func.HttpResponse:
    today = calendario.today()
    filters = _filters_of(query)
    board = service.punch_board(
        session, user=context.user, scope=context.scope, reference_date=today, filters=filters
    )
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={
            "board": board,
            "filtros": filters,
            "consulta": _query_of(filters),
            "api": API,
            "links_kpi": _kpi_links(filters),
            "situacoes": calc.SITUATIONS,
            "excel": f"{API}/excel?{_query_of(filters)}",
            "pdf": f"{API}/imprimivel?{_query_of(filters)}",
        },
        request=req,
        target_id=CONTENT_TARGET,
        toast=toast,
    )


def _kpi_links(filters: service.PunchFilter) -> dict[str, str]:
    """The address of each indicator that filters the list, keeping the rest of the filters."""

    def link(**changes: str) -> str:
        values = {
            "situacao": filters.situation,
            "categoria": "",
            "sistema": "" if filters.system_id is None else str(filters.system_id),
            "disciplina": filters.discipline,
            "empresa": "" if filters.company_id is None else str(filters.company_id),
            "busca": filters.search,
        }
        values.update(changes)
        return f"{API}?{urlencode(values)}"

    return {
        "abertos": link(situacao=service.ALL_OPEN),
        "a": link(situacao=service.ALL_OPEN, categoria="A"),
        "aguardando": link(situacao=calc.AWAITING_VERIFICATION),
        "fechados": link(situacao=calc.CLOSED),
    }


# ── Modals: filters and forms ────────────────────────────────────────────


@bp.route(route=f"{BASE}/filtros", methods=["GET"])
@fragment_route(access=READ, on_error=lambda req, error: _modal_error(req, error))
def punch_filters_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The modal Filtros: the same fields of the query, applied to the content."""
    filters = _filters_of(req.params)
    options = service.form_options(session, project_id=context.scope.project_id or 0)
    systems = [
        item for item in configuracoes.list_systems(session) if _in_scope(context, item.project_id)
    ]
    return AlpineAjaxResponse(
        template_name="planejamento/punch_filtros.html",
        context={
            "filtros": filters,
            "situacoes": calc.SITUATIONS,
            "categorias": calc.CATEGORIES,
            "disciplinas": calc.DISCIPLINES,
            "sistemas": [(item.id, f"{item.code} {item.name}") for item in systems],
            "empresas": options.companies,
            "api": API,
            "alvo": CONTENT_TARGET,
        },
        request=req,
        target_id=MODAL_TARGET,
    )


@bp.route(route=f"{BASE}/novo", methods=["GET"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The empty form of an item of the project in scope."""
    project_id = context.scope.require_project()
    screen = FormScreen(
        action=f"{API}/novo",
        kind="item",
        fields=_item_fields(session, project_id=project_id, values={}, errors={}),
        query=req.params.get("consulta", ""),
        save_label="Abrir item",
        support_text="O item gera uma ação na Central de Ações, com origem Punch list.",
    )
    return _form_response(req, screen)


@bp.route(route=f"{BASE}/novo", methods=["POST"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Open an item: numbered, with its action in the Central."""
    form = req.form
    project_id = context.scope.require_project()
    today = calendario.today()
    data = validation.item_from_form(form)
    record, error = _attempt(
        session,
        lambda: service.create_item(
            session, user=context.user, scope=context.scope, data=data, reference_date=today
        ),
    )
    if error is not None:
        screen = _item_screen_again(session, error, form=form, item=None, project_id=project_id)
        return _form_response(req, screen)
    return _screen_response(
        req,
        session,
        context,
        query=_query_form(form),
        toast=f"{record.code} aberto; ação criada na Central.",
    )


@bp.route(route=f"{BASE}/{{item_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of an open item, filled, with the version the screen opens."""
    item = _find(req, session, context)
    screen = FormScreen(
        action=f"{API}/{item.id}/editar",
        kind="item",
        fields=_item_fields(
            session, project_id=item.project_id, values=service.item_fields(item), errors={}
        ),
        values=service.item_fields(item),
        item=item,
        query=req.params.get("consulta", ""),
        save_label="Salvar item",
    )
    return _form_response(req, screen)


@bp.route(route=f"{BASE}/{{item_id}}/editar", methods=["POST"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_edit_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save an open item: the version the screen opened must still be current."""
    form = req.form
    item = _find(req, session, context)
    edit = service.ItemEdit(
        item_id=item.id, data=validation.item_from_form(form), version=form.get("versao")
    )
    _, error = _attempt(
        session,
        lambda: service.update_item(session, user=context.user, scope=context.scope, edit=edit),
    )
    if error is not None:
        screen = _item_screen_again(
            session, error, form=form, item=item, project_id=item.project_id
        )
        return _form_response(req, screen)
    return _screen_response(
        req,
        session,
        context,
        query=_query_form(form),
        toast=f"{item.code} atualizado.",
    )


@bp.route(route=f"{BASE}/{{item_id}}/tratar", methods=["POST"])
@fragment_route(access=WRITE, on_error=lambda req, error: _toast_error(req, error))
def punch_start(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Aberto goes to Em tratamento."""
    form = req.form
    item = _find(req, session, context)
    service.start_treatment(
        session, user=context.user, scope=context.scope, item_id=item.id, version=form.get("versao")
    )
    return _screen_response(
        req,
        session,
        context,
        query=_query_form(form),
        toast=f"{item.code} em tratamento.",
    )


@bp.route(route=f"{BASE}/{{item_id}}/enviar", methods=["GET"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_submit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The modal that sends the item to verification: the evidence and what was done."""
    item = _find(req, session, context)
    return _form_response(req, _submit_screen(item, query=req.params.get("consulta", "")))


@bp.route(route=f"{BASE}/{{item_id}}/enviar", methods=["POST"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_submit_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Em tratamento goes to Aguardando verificação; without evidence it is 422."""
    form = req.form
    item = _find(req, session, context)
    request = service.TreatmentRequest(
        item_id=item.id, comment=form.get("comentario", ""), version=form.get("versao")
    )
    _, error = _attempt(
        session,
        lambda: service.submit_for_verification(
            session, user=context.user, scope=context.scope, request=request
        ),
    )
    if error is not None:
        screen = _submit_screen(item, query=form.get("consulta", ""), values=form, error=error)
        return _form_response(req, _with_current_version(session, screen, error))
    return _screen_response(
        req,
        session,
        context,
        query=_query_form(form),
        toast=f"{item.code} enviado para verificação.",
    )


@bp.route(route=f"{BASE}/{{item_id}}/verificar", methods=["GET"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_verify_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The modal Fechamento com verificação: evidence, treatment, result and comment."""
    item = _find(req, session, context)
    return _form_response(req, _verify_screen(item, query=req.params.get("consulta", "")))


@bp.route(route=f"{BASE}/{{item_id}}/verificar", methods=["POST"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_verify_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Verify the closing: 403 for the executant, 422 without evidence, closes or rejects."""
    form = req.form
    item = _find(req, session, context)
    request = service.VerificationRequest(
        item_id=item.id,
        result=form.get("resultado", ""),
        comment=form.get("comentario", ""),
        version=form.get("versao"),
    )
    today = calendario.today()
    done, error = _attempt(
        session,
        lambda: service.verify_item(
            session,
            user=context.user,
            scope=context.scope,
            request=request,
            reference_date=today,
        ),
    )
    if error is not None:
        screen = _verify_screen(item, query=form.get("consulta", ""), values=form, error=error)
        return _form_response(req, _with_current_version(session, screen, error))
    closed = done.situation == calc.CLOSED
    notice = (
        f"{item.code} fechado." if closed else f"{item.code} reprovado e devolvido para tratamento."
    )
    return _screen_response(req, session, context, query=_query_form(form), toast=notice)


@bp.route(route=f"{BASE}/{{item_id}}/cancelar", methods=["GET"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_cancel_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The modal that cancels an item: the justification is required."""
    item = _find(req, session, context)
    return _form_response(req, _cancel_screen(item, query=req.params.get("consulta", "")))


@bp.route(route=f"{BASE}/{{item_id}}/cancelar", methods=["POST"])
@fragment_route(access=WRITE, on_error=lambda req, error: _modal_error(req, error))
def punch_cancel_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cancel the item; its action in the Central is closed with it."""
    form = req.form
    item = _find(req, session, context)
    request = service.CancellationRequest(
        item_id=item.id, justification=form.get("justificativa", ""), version=form.get("versao")
    )
    today = calendario.today()
    _, error = _attempt(
        session,
        lambda: service.cancel_item(
            session, user=context.user, scope=context.scope, request=request, reference_date=today
        ),
    )
    if error is not None:
        screen = _cancel_screen(item, query=form.get("consulta", ""), values=form, error=error)
        return _form_response(req, _with_current_version(session, screen, error))
    return _screen_response(
        req,
        session,
        context,
        query=_query_form(form),
        toast=f"{item.code} cancelado.",
    )


# ── Screens of the forms ─────────────────────────────────────────────────


def _submit_screen(
    item: service.PunchRow,
    *,
    query: str,
    values: Mapping[str, str] | None = None,
    error: DomainError | None = None,
) -> FormScreen:
    values = values or {}
    errors = _errors_of(error)
    fields = (
        _field(
            "comentario", "O que foi feito", "textarea", values, errors, required=True, full=True
        ),
    )
    return FormScreen(
        action=f"{API}/{item.id}/enviar",
        kind="enviar",
        fields=fields,
        values={"versao": str(item.version)},
        errors=errors,
        item=item,
        query=query,
        save_label="Enviar para verificação",
        support_text=(
            "A evidência (foto ou documento) é obrigatória: anexe o arquivo abaixo antes de enviar."
        ),
        status_code=_status_of(error),
    )


def _verify_screen(
    item: service.PunchRow,
    *,
    query: str,
    values: Mapping[str, str] | None = None,
    error: DomainError | None = None,
) -> FormScreen:
    values = values or {}
    errors = _errors_of(error)
    results = (
        (validation.APPROVED, "Aprovado: fechar o item"),
        (validation.REJECTED, "Reprovado: volta para tratamento"),
    )
    fields = (
        _field("resultado", "Resultado", "select", values, errors, required=True, options=results),
        _field("comentario", "Comentário", "textarea", values, errors, full=True),
    )
    return FormScreen(
        action=f"{API}/{item.id}/verificar",
        kind="verificar",
        fields=fields,
        values={"versao": str(item.version)},
        errors=errors,
        item=item,
        query=query,
        save_label="Registrar verificação",
        support_text=(
            "Quem verifica precisa ser diferente do executante (segregação de funções). "
            "O verificador é você."
        ),
        status_code=_status_of(error),
    )


def _cancel_screen(
    item: service.PunchRow,
    *,
    query: str,
    values: Mapping[str, str] | None = None,
    error: DomainError | None = None,
) -> FormScreen:
    values = values or {}
    errors = _errors_of(error)
    fields = (
        _field(
            "justificativa", "Justificativa", "textarea", values, errors, required=True, full=True
        ),
    )
    return FormScreen(
        action=f"{API}/{item.id}/cancelar",
        kind="cancelar",
        fields=fields,
        values={"versao": str(item.version)},
        errors=errors,
        item=item,
        query=query,
        save_label="Cancelar item",
        danger=True,
        status_code=_status_of(error),
    )


def _item_fields(
    session: Session, *, project_id: int, values: Mapping[str, str], errors: Mapping[str, str]
) -> tuple[dict[str, Any], ...]:
    options = service.form_options(session, project_id=project_id)
    people = tuple((str(item.id), item.name) for item in options.people)
    return (
        _field(
            "sistema",
            "Sistema",
            "select",
            values,
            errors,
            required=True,
            options=tuple((str(item.id), item.label) for item in options.systems),
        ),
        _field("subsistema", "Subsistema", "text", values, errors, required=True),
        _field("tag", "TAG", "text", values, errors, required=True),
        _field(
            "disciplina",
            "Disciplina",
            "select",
            values,
            errors,
            required=True,
            options=_pairs(calc.DISCIPLINES),
        ),
        _field(
            "categoria",
            "Categoria",
            "select",
            values,
            errors,
            required=True,
            options=(
                ("A", "A: impede o marco seguinte"),
                ("B", "B: não impede a operação"),
                ("C", "C: melhoria ou acabamento"),
            ),
        ),
        _field(
            "marco",
            "Marco vinculado",
            "select",
            values,
            errors,
            required=True,
            options=_pairs(calc.MILESTONES),
        ),
        _field(
            "origem",
            "Origem",
            "select",
            values,
            errors,
            required=True,
            options=_pairs(calc.ORIGINS),
        ),
        _field("prazo", "Prazo", "date", values, errors, required=True),
        _field("descricao", "Descrição", "textarea", values, errors, required=True, full=True),
        _field(
            "empresa",
            "Empresa executante",
            "select",
            values,
            errors,
            required=True,
            options=tuple((str(item.id), item.name) for item in options.companies),
        ),
        _field(
            "responsavel", "Responsável", "select", values, errors, required=True, options=people
        ),
        _field(
            "identificado_por",
            "Identificado por",
            "select",
            values,
            errors,
            required=True,
            options=people,
        ),
    )


def _pairs(options: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((option, option) for option in options)


def _field(
    name: str,
    label: str,
    kind: str,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    **extras: Any,
) -> dict[str, Any]:
    """One field of a form: ``required``, ``full`` and ``options`` come as keyword extras."""
    return {
        "name": name,
        "label": label,
        "kind": kind,
        "value": values.get(name, ""),
        "error": errors.get(name, ""),
        "required": extras.get("required", False),
        "full": extras.get("full", False),
        "options": extras.get("options", ()),
    }


# ── The answers of the forms ─────────────────────────────────────────────


def _form_response(req: func.HttpRequest, screen: FormScreen) -> func.HttpResponse:
    shown = {name for item in screen.fields for name in (item["name"],)} | {"anexo"}
    general = [text for name, text in screen.errors.items() if name not in shown]
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={
            "formulario": screen,
            "erros_gerais": general,
            "erro_anexo": screen.errors.get("anexo", ""),
            "alvo": CONTENT_TARGET,
            "versao": screen.values.get("versao", ""),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=screen.status_code,
    )


def _item_screen_again(
    session: Session,
    error: DomainError,
    *,
    form: Mapping[str, str],
    item: service.PunchRow | None,
    project_id: int,
) -> FormScreen:
    errors = _errors_of(error)
    screen = FormScreen(
        action=f"{API}/novo" if item is None else f"{API}/{item.id}/editar",
        kind="item",
        fields=_item_fields(session, project_id=project_id, values=form, errors=errors),
        values={"versao": form.get("versao", "")},
        errors=errors,
        item=item,
        query=form.get("consulta", ""),
        save_label="Abrir item" if item is None else "Salvar item",
        status_code=_status_of(error),
    )
    return _with_current_version(session, screen, error)


def _with_current_version(session: Session, screen: FormScreen, error: DomainError) -> FormScreen:
    """After a 409 the form carries the version now in force, so the next save can succeed."""
    if not isinstance(error, VersionConflictError) or screen.item is None:
        return screen
    current = session.get(service.PunchItem, screen.item.id)
    if current is None:
        return screen
    return FormScreen(
        action=screen.action,
        kind=screen.kind,
        fields=screen.fields,
        values={**screen.values, "versao": str(current.version)},
        errors=screen.errors,
        item=screen.item,
        query=screen.query,
        save_label=screen.save_label,
        support_text=screen.support_text,
        danger=screen.danger,
        status_code=screen.status_code,
    )


def _attempt(session: Session, work: Callable[[], Any]) -> tuple[Any, DomainError | None]:
    """Run a write in a savepoint: a refusal of the data leaves nothing behind, not a half write."""
    try:
        with session.begin_nested():
            return work(), None
    except (InvalidDataError, VersionConflictError) as error:
        return None, error


def _errors_of(error: DomainError | None) -> dict[str, str]:
    if error is None:
        return {}
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return dict(error.detail)
    return {"geral": str(error)}


def _status_of(error: DomainError | None) -> int:
    if error is None:
        return 200
    return 409 if isinstance(error, VersionConflictError) else 422


def _query_form(form: Mapping[str, str]) -> dict[str, str]:
    """The filters a form carried in its ``consulta`` field, as a mapping."""
    return dict(parse_qsl(form.get("consulta", "")))


def _find(req: func.HttpRequest, session: Session, context: RequestContext) -> service.PunchRow:
    item_id = validation.whole_number(req.route_params.get("item_id"))
    if item_id is None:
        raise InvalidDataError(NOT_FOUND)
    return service.find_item(
        session,
        user=context.user,
        scope=context.scope,
        item_id=item_id,
        reference_date=calendario.today(),
    )


def _in_scope(context: RequestContext, project_id: int) -> bool:
    return context.scope.is_portfolio or context.scope.project_id == project_id


def _status(error: DomainError) -> int:
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
        status_code=_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


def _toast_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """A refusal of a button with no modal: the toast says it, the screen stays as it is."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=CONTENT_TARGET + "-aviso",
        status_code=_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )
