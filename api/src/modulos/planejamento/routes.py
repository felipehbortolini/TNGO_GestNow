"""Route blueprint for the Planning module.

The 6WLA (ISSUE-045), prefix ``/api/planejamento/6wla``:

* ``GET  /``  the screen: filters and content (indicators, Gantt, grid, restrictions, Galeria);
* ``GET  /excel`` and ``GET /imprimivel``  the two exports of the same board;
* ``GET  /atividades/nova``, ``POST /atividades``  include an activity (needs a project);
* ``GET  /atividades/{atividade_id}/editar``, ``POST /atividades/{atividade_id}``  edit it;
* ``GET  /restricoes/nova``, ``POST /restricoes``  register a restriction (``?atividade=``);
* ``GET  /restricoes/{restricao_id}/editar``, ``POST /restricoes/{restricao_id}``  edit it;
* ``GET  /restricoes/{restricao_id}/remover``, ``POST /restricoes/{restricao_id}/remocao``  remove it.

The routes read the request and draw the answer; every rule is in the facade. A write answers
three blocks at once (form, filters and content), because Alpine AJAX empties a declared target
that does not come back: the form is shown again with the messages on 422 and 409, and emptied
on success.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario
from src.core.errors import InvalidDataError, VersionConflictError
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import export, service, validation

bp = func.Blueprint()

MODULE = "planejamento"
BASE = "planejamento/6wla"
API_BASE = f"/api/{BASE}"
READ_ACCESS = Access(module=MODULE)
WRITE_ACCESS = Access(module=MODULE, permission=Permission.WRITE)

SCREEN_TEMPLATE = "planejamento/6wla.html"
FORM_TEMPLATE = "planejamento/6wla_formulario.html"
ANSWER_TEMPLATE = "planejamento/6wla_resposta.html"

ACTIVITY_FORM = "planejamento/6wla_form_atividade.html"
CONSTRAINT_FORM = "planejamento/6wla_form_restricao.html"
REMOVAL_FORM = "planejamento/6wla_form_remocao.html"

INVALID_ID_MESSAGE = "O endereço não indica um registro válido."
TRUE_VALUES = frozenset({"1", "on", "true"})
CONSTRAINT_LISTS = {
    service.OPEN_CONSTRAINTS: "Abertas",
    service.ALL_CONSTRAINTS: "Todas",
}


@dataclass(frozen=True)
class FormScreen:
    """A form of the 6WLA: which fragment draws it, where it posts and what it shows."""

    template: str
    title: str
    action: str
    values: Mapping[str, Any]
    errors: Mapping[str, str] = field(default_factory=dict)
    subtitle: str = ""
    message: str = ""
    weeks: tuple[str, ...] = ()
    activity: service.ActivityView | None = None
    activities: tuple[service.ActivityView, ...] = ()
    status_code: int = 200


# ── The screen and the exports ───────────────────────────────────────────


@bp.route(route=BASE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def lookahead_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Filters and content of the 6WLA for the scope and the filters of the request."""
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context=_board_context(req, session, context),
        request=req,
    )


@bp.route(route=f"{BASE}/excel", methods=["GET"])
@file_route(access=READ_ACCESS)
def lookahead_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the board the screen shows (same filters)."""
    return excel_response(_document(req, session, context))


@bp.route(route=f"{BASE}/imprimivel", methods=["GET"])
@fragment_route(access=READ_ACCESS)
def lookahead_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the board: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


def _filters_of(req: func.HttpRequest) -> service.LookaheadFilter:
    params = req.params
    constraints = params.get("restricoes") or service.OPEN_CONSTRAINTS
    return service.LookaheadFilter(
        search=(params.get("busca") or "").strip(),
        discipline=(params.get("disciplina") or "").strip(),
        only_with_open_constraint=(params.get("so_restricao") or "") in TRUE_VALUES,
        constraints=constraints if constraints in CONSTRAINT_LISTS else service.OPEN_CONSTRAINTS,
    )


def _board_context(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: service.LookaheadFilter | None = None,
) -> dict[str, Any]:
    """What the screen fragments print: the board, the filters, the Gantt and the Galeria."""
    chosen = filters if filters is not None else _filters_of(req)
    reference_date = calendario.today()
    board = service.lookahead_board(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=reference_date,
        filters=chosen,
    )
    return {
        "board": board,
        "filtros": chosen,
        "disciplinas": configuracoes.list_discipline_names(session),
        "listas_de_restricoes": CONSTRAINT_LISTS,
        "gantt": export.gantt_data(board),
        "galeria": export.gallery_data(board.constraints),
        "legenda_semana": export.week_caption,
        "horizonte": export.horizon_text(board),
        "indice_de_remocao": format_value(ValueKind.PERCENT, board.figures.removal_index, 0) or "·",
        "api": API_BASE,
    }


def _document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    filters = _filters_of(req)
    board = service.lookahead_board(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
        filters=filters,
    )
    return export.lookahead_document(
        board,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        constraints_label=CONSTRAINT_LISTS[filters.constraints],
    )


# ── The forms ────────────────────────────────────────────────────────────


@bp.route(route=f"{BASE}/atividades/nova", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_new_activity_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The empty activity form; in the Portfólio it asks for a project first."""
    context.scope.require_project()
    screen = FormScreen(
        template=ACTIVITY_FORM,
        title="Nova atividade",
        action=f"{API_BASE}/atividades",
        values={},
    )
    return _form_response(req, session, screen)


@bp.route(route=f"{BASE}/atividades/{{atividade_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_edit_activity_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The activity form filled with the activity and the version the screen opens."""
    activity = _find_activity(session, context, _route_id(req, "atividade_id"))
    screen = FormScreen(
        template=ACTIVITY_FORM,
        title=f"Editar {activity.code}",
        action=f"{API_BASE}/atividades/{activity.id}",
        values=service.activity_fields(activity),
        weeks=_marked(activity),
        activity=activity,
    )
    return _form_response(req, session, screen)


@bp.route(route=f"{BASE}/restricoes/nova", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_new_constraint_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The empty restriction form; ``?atividade=`` preselects the activity."""
    screen = _constraint_screen(session, context, values={"atividade": req.params.get("atividade")})
    return _form_response(req, session, screen)


@bp.route(route=f"{BASE}/restricoes/{{restricao_id}}/editar", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_edit_constraint_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The restriction form filled with the restriction and the version the screen opens."""
    constraint = _find_constraint(session, context, _route_id(req, "restricao_id"))
    screen = FormScreen(
        template=CONSTRAINT_FORM,
        title=f"Editar restrição de {constraint.activity_code}",
        action=f"{API_BASE}/restricoes/{constraint.id}",
        values=service.constraint_fields(constraint),
        activity=_find_activity(session, context, constraint.activity_id),
    )
    return _form_response(req, session, screen)


@bp.route(route=f"{BASE}/restricoes/{{restricao_id}}/remover", methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_removal_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The removal form: the date (today by default) and how the restriction was removed."""
    constraint = _find_constraint(session, context, _route_id(req, "restricao_id"))
    screen = FormScreen(
        template=REMOVAL_FORM,
        title="Remover restrição",
        action=f"{API_BASE}/restricoes/{constraint.id}/remocao",
        values={
            "remocao": calendario.today().isoformat(),
            "versao": str(constraint.version),
        },
        activity=_find_activity(session, context, constraint.activity_id),
        subtitle=f"{constraint.activity_code} · {constraint.description}",
    )
    return _form_response(req, session, screen)


def _constraint_screen(
    session: Session, context: RequestContext, *, values: Mapping[str, Any]
) -> FormScreen:
    board = service.lookahead_board(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
        filters=service.LookaheadFilter(),
    )
    return FormScreen(
        template=CONSTRAINT_FORM,
        title="Nova restrição",
        action=f"{API_BASE}/restricoes",
        values={key: value for key, value in values.items() if value},
        activities=board.activities,
    )


def _form_response(
    req: func.HttpRequest, session: Session, screen: FormScreen
) -> func.HttpResponse:
    """The form alone, for the request that opens it (target: the form block)."""
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context=_form_context(session, screen),
        request=req,
        status_code=screen.status_code,
    )


def _form_context(session: Session, screen: FormScreen) -> dict[str, Any]:
    return {
        "formulario": screen,
        "opcoes": service.form_options(session, reference_date=calendario.today()),
    }


# ── The writes ───────────────────────────────────────────────────────────


@bp.route(route=f"{BASE}/atividades", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_create_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Include the activity; the answer is the refreshed screen, or the form with the messages."""
    screen = FormScreen(
        template=ACTIVITY_FORM,
        title="Nova atividade",
        action=f"{API_BASE}/atividades",
        values=_values_of(req),
        weeks=tuple(req.form.getlist("semanas")),
    )

    def save() -> str:
        record = service.create_activity(
            session, user=context.user, scope=context.scope, form=_activity_form_of(req)
        )
        return f"Atividade {record.code} incluída."

    return _save(req, session, context, screen=screen, save=save)


@bp.route(route=f"{BASE}/atividades/{{atividade_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_update_activity(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Edit the activity; 409 when someone saved it since the screen opened it."""
    activity_id = _route_id(req, "atividade_id")
    screen = FormScreen(
        template=ACTIVITY_FORM,
        title="Editar atividade",
        action=f"{API_BASE}/atividades/{activity_id}",
        values=_values_of(req),
        weeks=tuple(req.form.getlist("semanas")),
        activity=_find_activity(session, context, activity_id),
    )

    def save() -> str:
        record = service.update_activity(
            session,
            user=context.user,
            scope=context.scope,
            activity_id=activity_id,
            form=_activity_form_of(req),
        )
        return f"Atividade {record.code} atualizada."

    return _save(req, session, context, screen=screen, save=save)


@bp.route(route=f"{BASE}/restricoes", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_create_constraint(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the restriction on the chosen activity."""
    screen = _constraint_screen(session, context, values=_values_of(req))

    def save() -> str:
        service.create_constraint(
            session, user=context.user, scope=context.scope, raw=_values_of(req)
        )
        return "Restrição registrada."

    return _save(req, session, context, screen=screen, save=save)


@bp.route(route=f"{BASE}/restricoes/{{restricao_id}}", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_update_constraint(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Edit the restriction; 409 when someone saved it since the screen opened it."""
    constraint_id = _route_id(req, "restricao_id")
    constraint = _find_constraint(session, context, constraint_id)
    screen = FormScreen(
        template=CONSTRAINT_FORM,
        title=f"Editar restrição de {constraint.activity_code}",
        action=f"{API_BASE}/restricoes/{constraint_id}",
        values=_values_of(req),
        activity=_find_activity(session, context, constraint.activity_id),
    )

    def save() -> str:
        service.update_constraint(
            session,
            user=context.user,
            scope=context.scope,
            constraint_id=constraint_id,
            raw=_values_of(req),
        )
        return "Restrição atualizada."

    return _save(req, session, context, screen=screen, save=save)


@bp.route(route=f"{BASE}/restricoes/{{restricao_id}}/remocao", methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def lookahead_remove_constraint(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the removal of the restriction."""
    constraint_id = _route_id(req, "restricao_id")
    constraint = _find_constraint(session, context, constraint_id)
    screen = FormScreen(
        template=REMOVAL_FORM,
        title="Remover restrição",
        action=f"{API_BASE}/restricoes/{constraint_id}/remocao",
        values=_values_of(req),
        activity=_find_activity(session, context, constraint.activity_id),
        subtitle=f"{constraint.activity_code} · {constraint.description}",
    )

    def save() -> str:
        service.remove_constraint(
            session,
            user=context.user,
            scope=context.scope,
            constraint_id=constraint_id,
            raw=_values_of(req),
        )
        return "Restrição removida."

    return _save(req, session, context, screen=screen, save=save)


def _save(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    screen: FormScreen,
    save: Callable[[], str],
) -> func.HttpResponse:
    """Run the write and answer the three blocks: refreshed on success, form with messages if not."""
    try:
        notice = save()
    except InvalidDataError as error:
        return _answer(req, session, context, screen=_with_error(screen, error, 422))
    except VersionConflictError as error:
        return _answer(
            req, session, context, screen=_with_error(screen, InvalidDataError(str(error)), 409)
        )
    return _answer(req, session, context, screen=None, notice=notice)


def _with_error(screen: FormScreen, error: InvalidDataError, status_code: int) -> FormScreen:
    detail = error.detail
    errors = dict(detail) if isinstance(detail, Mapping) else {}
    return FormScreen(
        template=screen.template,
        title=screen.title,
        action=screen.action,
        values=screen.values,
        errors=errors,
        subtitle=screen.subtitle,
        message="" if errors else str(error),
        weeks=screen.weeks,
        activity=screen.activity,
        activities=screen.activities,
        status_code=status_code,
    )


def _answer(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    screen: FormScreen | None,
    notice: str | None = None,
) -> func.HttpResponse:
    """Form, filters and content in one answer; the filters come back reset to the default."""
    page = _board_context(req, session, context, filters=service.LookaheadFilter())
    page.update(_form_context(session, screen) if screen else {"formulario": None})
    failed = screen is not None
    return AlpineAjaxResponse(
        template_name=ANSWER_TEMPLATE,
        context=page,
        request=req,
        status_code=screen.status_code if screen else 200,
        toast=None if failed else notice,
        toast_tipo="ok",
    )


# ── The request ──────────────────────────────────────────────────────────


def _values_of(req: func.HttpRequest) -> dict[str, str]:
    """The text fields the form sent, as they were typed."""
    return {key: value for key, value in req.form.items() if isinstance(value, str)}


def _activity_form_of(req: func.HttpRequest) -> validation.ActivityForm:
    return validation.ActivityForm(fields=_values_of(req), weeks=req.form.getlist("semanas"))


def _route_id(req: func.HttpRequest, name: str) -> int:
    found = validation.parse_id(req.route_params.get(name))
    if found is None:
        raise InvalidDataError(INVALID_ID_MESSAGE)
    return found


def _marked(activity: service.ActivityView) -> tuple[str, ...]:
    return tuple(str(index) for index, planned in enumerate(activity.planned) if planned)


def _find_activity(
    session: Session, context: RequestContext, activity_id: int
) -> service.ActivityView:
    return service.find_activity(
        session, scope=context.scope, activity_id=activity_id, reference_date=calendario.today()
    )


def _find_constraint(
    session: Session, context: RequestContext, constraint_id: int
) -> service.ConstraintView:
    return service.find_constraint(
        session,
        scope=context.scope,
        constraint_id=constraint_id,
        reference_date=calendario.today(),
    )
