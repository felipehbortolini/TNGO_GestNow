"""Routes of the Risk management module: the screen Registro and its forms (D14, ISSUE-064).

Prefix ``/api/riscos/``. The screen is one fragment, ``registro-conteudo``: context line, KPIs,
notice, chips, toolbar and the table. Everything that changes the view (a KPI, a chip, the switch
Inerente/Residual, a page, the search, the filter modal) is a plain GET of the same route with the
filters in the query string, answered with the same fragment. The forms open in a modal
(``registro-modal-corpo``): a GET draws the form, a POST saves and answers the refreshed screen; a
refusal (422, 409, 403) answers the form again, filled in, in the modal.

* ``GET  registro``                         the screen (filters and page by query);
* ``GET  registro/excel`` and ``registro/imprimivel``   the two exports of what the screen shows;
* ``GET/POST novo``                         Novo risco (in the Portfólio the project comes first);
* ``GET/POST {codigo}/editar``              the identification of one risk;
* ``GET/POST {codigo}/avaliar``             the assessment, with ``GET previa`` as its preview;
* ``GET/POST {codigo}/excluir``             the logical deletion (Gestor);
* ``POST {codigo}/restaurar``               the restoration (Admin);
* ``GET categorias/nova`` and ``POST categorias``   the quick registration of a category.

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from urllib.parse import parse_qsl, urlencode

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
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.riscos import calculations, export, presentation, service, validation
from src.modulos.riscos.calculations import DIMENSIONS, Band, Scale
from src.modulos.riscos.validation import (
    AssessmentInput,
    DeletionInput,
    RiskFilters,
    RiskInput,
)

bp = func.Blueprint()

MODULE = "riscos"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)
MANAGE = Access(module=MODULE, permission=Permission.MANAGE)

CONTENT_TARGET = "registro-conteudo"
MODAL_TARGET = "registro-modal-corpo"
PREVIEW_TARGET = "risco-previa"
CATEGORY_TARGET = "risco-categoria-campo"

SCREEN_TEMPLATE = "riscos/registro.html"
PROJECT_TEMPLATE = "riscos/risco_projeto.html"
FORM_TEMPLATE = "riscos/risco_form.html"
ASSESS_TEMPLATE = "riscos/risco_avaliar.html"
PREVIEW_TEMPLATE = "riscos/risco_previa.html"
DELETE_TEMPLATE = "riscos/risco_excluir.html"
CATEGORY_FORM_TEMPLATE = "riscos/categoria_nova.html"
CATEGORY_FIELD_TEMPLATE = "riscos/categoria_campo.html"

SAVED_NOTICE = "Risco registrado: {code}."
EDITED_NOTICE = "Identificação do risco {code} alterada."
ASSESSED_NOTICE = "Avaliação {kind} registrada: {score} ({band})."
DELETED_NOTICE = "Risco {code} excluído."
RESTORED_NOTICE = "Risco {code} restaurado."
CATEGORY_NOTICE = "Categoria cadastrada."
INVALID_RISK_MESSAGE = "Informe o risco."
CHOOSE_PROJECT_MESSAGE = "Escolha o projeto do risco."

MONEY_FIELDS = ("impactoCustoCentavos",)
SEVERITY_TONES = ("pill--ok", "pill--fix", "pill--warn", "pill--erro")


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
    """A clickable KPI: the number, what it is read against and the link that filters by it."""

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


@dataclass(frozen=True)
class ChipLink:
    """A chip of the active filters with the address that removes it."""

    text: str
    removable: bool
    url: str


# ── The screen ───────────────────────────────────────────────────────────────────────────────


@bp.route(route="riscos/registro", methods=["GET"])
@fragment_route(access=READ)
def risk_register_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The screen: context, KPIs, notice, chips, toolbar and the table, for the filters."""
    return _screen(req, session, context, filters=validation.parse_filters(req.params))


@bp.route(route="riscos/registro/excel", methods=["GET"])
@file_route(access=READ)
def risk_register_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the risks of the filter: what the screen lists, with its KPIs."""
    return excel_response(_document(req, session, context))


@bp.route(route="riscos/registro/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def risk_register_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the same document: what the PDF button mounts and prints."""
    return printable_response(_document(req, session, context), req)


# ── Novo risco and edição ────────────────────────────────────────────────────────────────────


@bp.route(route="riscos/novo", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def new_risk_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of a new risk; in the Portfólio the project is asked first."""
    project_id = context.scope.project_id or validation.parse_id(req.params.get("projeto"))
    query = req.params.get("consulta", "")
    if project_id is None:
        return _project_choice(req, session, query=query)
    return _risk_form(
        req,
        session,
        context,
        state=_FormState(project_id=project_id, code=None, query=query, values={}),
    )


@bp.route(route="riscos/novo", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def new_risk_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the risk and answer the refreshed screen, or the form with its messages."""
    project_id = context.scope.project_id or validation.parse_id(req.form.get("projeto"))
    if project_id is None:
        raise InvalidDataError(CHOOSE_PROJECT_MESSAGE)
    return _save(req, session, context, project_id=project_id, code=None)


@bp.route(route="riscos/{codigo}/editar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def edit_risk_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The identification of one risk, to edit."""
    risk = _risk(session, context, req)
    state = _FormState(
        project_id=risk.project_id,
        code=risk.code,
        query=req.params.get("consulta", ""),
        values=_risk_values(risk),
        version=risk.version,
    )
    return _risk_form(req, session, context, state=state)


@bp.route(route="riscos/{codigo}/editar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def edit_risk_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the identification and answer the refreshed screen, or the form with its messages."""
    risk = _risk(session, context, req)
    return _save(req, session, context, project_id=risk.project_id, code=risk.code)


@bp.route(route="riscos/categorias/nova", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def new_category_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The quick registration of a category of the RBS."""
    del context
    return _category_form(req, session, values={}, errors={})


@bp.route(route="riscos/categorias", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def new_category_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Register the category and answer the field of the risk form with it chosen."""
    group, name = req.form.get("grupo", ""), req.form.get("nome", "")
    try:
        with session.begin_nested():
            category = service.create_category(session, user=context.user, group=group, name=name)
    except InvalidDataError as error:
        return _category_form(
            req,
            session,
            values={"grupo": group, "nome": name},
            errors=_field_errors(error),
            status=422,
        )
    return AlpineAjaxResponse(
        template_name=CATEGORY_FIELD_TEMPLATE,
        context={
            "categorias": service.list_categories(session),
            "valores": {"categoria": str(category.id)},
            "erros": {},
        },
        request=req,
        target_id=CATEGORY_TARGET,
        toast=CATEGORY_NOTICE,
    )


# ── Avaliação ────────────────────────────────────────────────────────────────────────────────


@bp.route(route="riscos/{codigo}/avaliar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def assess_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The assessment form, with the values of the chosen kind and the preview of its score."""
    risk = _risk(session, context, req)
    asked = req.params.get("tipo", "")
    kind = asked if asked in validation.ASSESSMENT_KINDS else None
    kind = kind or (validation.RESIDUAL if risk.has_plan else validation.INHERENT)
    if kind == validation.RESIDUAL and not risk.has_plan:
        kind = validation.INHERENT
    view = risk.residual or risk.inherent if kind == validation.RESIDUAL else risk.inherent
    values = _assessment_values(risk, view, kind)
    return _assess_form(
        req,
        session,
        context,
        state=_AssessState(risk=risk, query=req.params.get("consulta", ""), values=values),
    )


@bp.route(route="riscos/{codigo}/avaliar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def assess_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Record the assessment and answer the refreshed screen, or the form with its messages."""
    risk = _risk(session, context, req)
    data = _assessment_input(req.form)
    today = calendario.today()
    error: DomainError | None = None
    result: service.AssessmentResult | None = None
    try:
        with session.begin_nested():
            result = service.assess_risk(
                session, user=context.user, code=risk.code, data=data, reference_date=today
            )
    except (InvalidDataError, VersionConflictError) as caught:
        error = caught
    state = _AssessState(
        risk=risk,
        query=req.form.get("consulta", ""),
        values=dict(req.form),
        version=req.form.get("versao"),
    )
    if error is not None or result is None:
        return _assess_form(req, session, context, state=state, error=error)
    notice = ASSESSED_NOTICE.format(kind=data.kind, score=result.score, band=result.severity.name)
    return _screen(
        req,
        session,
        context,
        filters=_filters_of(state.query),
        after=_After(
            notice,
            {"alerta_do_gestor": result.manager_alert, "exige_plano": result.requires_plan},
        ),
    )


@bp.route(route="riscos/previa", methods=["GET"])
@fragment_route(access=READ)
def score_preview(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The preview of the score, calculated by the server from what the form has so far."""
    data = _assessment_input(req.params)
    today = calendario.today()
    preview = service.preview_score(session, user=context.user, data=data, reference_date=today)
    scale = service.parameters(session, reference_date=today).scale
    return _preview_response(req, preview, scale, kind=data.kind)


# ── Exclusão e restauração ───────────────────────────────────────────────────────────────────


@bp.route(route="riscos/{codigo}/excluir", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def delete_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the logical deletion: the reason and, for Outro, the note."""
    risk = _risk(session, context, req)
    state = _DeleteState(risk=risk, query=req.params.get("consulta", ""), version=risk.version)
    return _delete_form(req, state)


@bp.route(route="riscos/{codigo}/excluir", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def delete_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Delete logically and answer the refreshed screen, or the form with its messages."""
    risk = _risk(session, context, req)
    form = req.form
    data = DeletionInput(
        reason=form.get("motivo", ""),
        note=form.get("observacao", ""),
        version=form.get("versao"),
    )
    today = calendario.today()
    error = _attempt(
        session,
        lambda: service.delete_risk(
            session, user=context.user, code=risk.code, data=data, reference_date=today
        ),
    )
    query = form.get("consulta", "")
    if error is not None:
        stale = isinstance(error, VersionConflictError)
        stale = isinstance(error, VersionConflictError)
        state = _DeleteState(
            risk=risk,
            query=query,
            version=risk.version if stale else form.get("versao"),
            values={"motivo": data.reason, "observacao": data.note},
            errors=_field_errors(error),
        )
        return _delete_form(req, state, status=_error_status(error))
    return _screen(
        req,
        session,
        context,
        filters=_filters_of(query),
        after=_After(DELETED_NOTICE.format(code=risk.code), {}),
    )


@bp.route(route="riscos/{codigo}/restaurar", methods=["POST"])
@fragment_route(access=READ)
def restore_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Restore a deleted risk (Admin) and answer the refreshed screen."""
    code = req.route_params.get("codigo") or ""
    service.restore_risk(session, user=context.user, code=code)
    return _screen(
        req,
        session,
        context,
        filters=_filters_of(req.form.get("consulta", "")),
        after=_After(RESTORED_NOTICE.format(code=code), {}),
    )


# ── Drawing the screen ───────────────────────────────────────────────────────────────────────


def _filters_of(query: str) -> RiskFilters:
    return validation.parse_filters(dict(parse_qsl(query)))


def _screen(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: RiskFilters,
    after: _After | None = None,
) -> func.HttpResponse:
    """The screen fragment for the filters, with an optional toast and extra context."""
    listing = service.list_risks(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=calendario.today(),
    )
    shown = replace(filters, page=listing.page)
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={**_screen_context(listing, shown, context), **(after.extra if after else {})},
        request=req,
        target_id=CONTENT_TARGET,
        toast=after.notice if after else None,
    )


def _screen_context(
    listing: service.RiskListing, filters: RiskFilters, context: RequestContext
) -> dict[str, object]:
    params = listing.parameters
    owners = dict(listing.owners)
    query = presentation.query_string(filters)
    return {
        "listagem": listing,
        "filtros": filters,
        "kpis": _kpi_cards(listing, filters),
        "chips": _chips(listing, filters, owners),
        "contexto": _context_line(listing, context),
        "link_inerente": presentation.address(
            presentation.with_assessment(filters, validation.INHERENT)
        ),
        "link_residual": presentation.address(
            presentation.with_assessment(filters, validation.RESIDUAL)
        ),
        "link_anterior": _page_link(filters, filters.page - 1, listing.page_count),
        "link_proximo": _page_link(filters, filters.page + 1, listing.page_count),
        "link_limpar": presentation.address(presentation.cleared(filters)),
        "link_vencidas": presentation.address(presentation.with_review(filters, "vencidas")),
        "tem_filtro_extra": not presentation.is_default(filters),
        "url_excel": presentation.address(
            replace(filters, page=1), path=f"{presentation.ROUTE}/excel"
        ),
        "url_pdf": presentation.address(
            replace(filters, page=1), path=f"{presentation.ROUTE}/imprimivel"
        ),
        "url_matriz": origin_links.link_to_screen("riscos/matriz") or "",
        "link_da_ficha": _record_link,
        "consulta": query,
        "parametro_consulta": urlencode({"consulta": query}),
        "portfolio": context.scope.is_portfolio,
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "pode_gerir": rbac.can(context.user, Permission.MANAGE),
        "eh_admin": service.can_see_deleted(context.user),
        "rotulos_de_projeto": export.project_labels(listing),
        "cadencia_do_topo": _cadence_text(
            params.cadence_days.get(params.scale.bands[-1].id), params.scale.bands[-1]
        ),
        "faixas": tuple(reversed(params.scale.bands)),
        "estrategias": _strategies(),
        "situacoes": validation.SITUATIONS,
        "revisoes": _review_options(params.review_alert_days),
        "etiqueta_de_faixa": lambda band: _severity_tone(band, params.scale),
        "formatar_data": _format_date,
        "formatar_moeda": _format_money,
        "texto_da_avaliacao": export.assessment_text,
        "texto_da_cadencia": _cadence_text_of,
        "pagina_inicial": (filters.page - 1) * validation.PAGE_SIZE + 1,
        "pagina_final": min(filters.page * validation.PAGE_SIZE, listing.total),
    }


def _record_link(code: str) -> str:
    """The address of the ficha of a risk; the plain path while the ficha has no screen yet."""
    return origin_links.link_to_screen("riscos/ficha", codigo=code) or ""


def _strategies() -> tuple[str, ...]:
    return ("Mitigar", "Transferir", "Evitar", "Aceitar", "Explorar", "Melhorar", "Compartilhar")


def _review_options(days: int) -> tuple[tuple[str, str], ...]:
    return tuple(
        (value, presentation.REVIEW_TEXT[value].format(days=days))
        for value in validation.REVIEW_FILTERS
    )


def _cadence_text(days: int | None, band: Band) -> str:
    return f"a cada {days} dias" if days else band.name


def _cadence_text_of(days: int | None) -> str:
    return f"a cada {days} dias" if days else ""


def _severity_tone(band: Band | None, scale: Scale) -> str:
    """The pill of a band: the heaviest is red, the next amber, the lightest green."""
    if band is None:
        return "pill--neutral"
    rank = calculations.severity_rank(band.id, scale)
    last = len(scale.bands) - 1
    if rank == last:
        return SEVERITY_TONES[3]
    if rank == last - 1:
        return SEVERITY_TONES[2]
    return SEVERITY_TONES[0] if rank <= 0 else SEVERITY_TONES[1]


def _context_line(listing: service.RiskListing, context: RequestContext) -> list[tuple[str, str]]:
    """The labels of the context: project, client, numbering and appetite (or the portfolio)."""
    if context.scope.is_portfolio:
        head = [(f"Portfólio: {len(listing.projects)} projeto(s)", "outline")]
        return head + [
            (
                f"{item.code} · apetite {item.appetite.name if item.appetite else 'não definido'}",
                "outline",
            )
            for item in listing.projects
        ]
    if not listing.projects:
        return []
    item = listing.projects[0]
    return [
        (f"Projeto: {item.code}", "outline"),
        (f"Cliente: {item.client_acronym}", "outline"),
        (f"Numeração: {item.risk_pattern or 'RSK'}", "outline"),
        (f"Apetite: {item.appetite.name if item.appetite else 'não definido'}", "primary"),
    ]


def _kpi_cards(listing: service.RiskListing, filters: RiskFilters) -> list[KpiCard]:
    summary = listing.summary
    shown = "inerente" if filters.assessment == validation.INHERENT else "residual"
    cards = [_band_card(summary.top, filters, shown, tone="erro", icon="warning")]
    if summary.second is not None:
        cards.append(_band_card(summary.second, filters, shown, tone="warn", icon="errorCircle"))
    overdue = len(summary.overdue)
    cards.append(
        KpiCard(
            label="Em tratamento",
            icon="play",
            tone="info",
            value=summary.in_treatment,
            reference=f"Esperado: {summary.expected_in_treatment}",
            footer="plano aprovado e ações em curso",
            url=presentation.address(presentation.with_situation(filters, "Em tratamento")),
            active=filters.situation == "Em tratamento",
        )
    )
    cards.append(
        KpiCard(
            label="Revisão vencida",
            icon="calendar",
            tone="erro" if overdue else "ok",
            value=overdue,
            reference="Esperado: 0",
            footer="próxima revisão anterior a hoje",
            url=presentation.address(presentation.with_review(filters, "vencidas")),
            active=filters.review == "vencidas",
        )
    )
    cards.append(
        KpiCard(
            label="Ativos",
            icon="taskList",
            tone="neutro",
            value=summary.active,
            reference=f"Referência: de {summary.registered} registrados",
            footer=f"{summary.unassessed} sem avaliação",
            url=presentation.address(presentation.cleared(filters)),
            active=presentation.is_default(filters),
        )
    )
    return cards


def _band_card(
    count: service.BandCount, filters: RiskFilters, shown: str, *, tone: str, icon: str
) -> KpiCard:
    detail = f"{count.threats} ameaça(s)"
    if count.opportunities:
        detail += f" · {count.opportunities} oportunidade(s)"
    return KpiCard(
        label=f"{count.band.name}s ({shown})",
        icon=icon,
        tone=tone if count.total else "ok",
        value=count.total,
        reference=f"Meta: {count.goal}",
        footer=detail if count.total else "nenhum na faixa",
        url=presentation.address(presentation.with_severity(filters, count.band.id)),
        active=filters.severities == (count.band.id,),
    )


def _chips(
    listing: service.RiskListing, filters: RiskFilters, owners: Mapping[int, str]
) -> list[ChipLink]:
    chips = presentation.active_chips(
        filters,
        bands=listing.parameters.scale.bands,
        owners=owners,
        review_alert_days=listing.parameters.review_alert_days,
    )
    return [
        ChipLink(
            text=chip.text,
            removable=chip.removable,
            url=presentation.address(presentation.without(filters, chip.field)),
        )
        for chip in chips
    ]


def _page_link(filters: RiskFilters, page: int, page_count: int) -> str:
    if page < 1 or page > page_count:
        return ""
    return presentation.address(presentation.with_page(filters, page))


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
    listing = service.list_risks(
        session,
        user=context.user,
        scope=context.scope,
        filters=filters,
        reference_date=today,
    )
    return export.build_document(
        listing=listing,
        filters=filters,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
    )


# ── Drawing the forms ────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _FormState:
    """What the identification form remembers: the risk, the screen it came from, what was typed."""

    project_id: int
    code: str | None
    query: str
    values: Mapping[str, str]
    version: int | str | None = None


@dataclass(frozen=True)
class _AssessState:
    """What the assessment form remembers: the risk, the screen and what was typed."""

    risk: service.RiskLine
    query: str
    values: Mapping[str, str]
    version: int | str | None = None


def _risk(session: Session, context: RequestContext, req: func.HttpRequest) -> service.RiskLine:
    code = req.route_params.get("codigo") or ""
    risk = service.find_risk(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if risk is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return risk


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


def _project_choice(req: func.HttpRequest, session: Session, *, query: str) -> func.HttpResponse:
    """The Portfólio asks for the project before it opens the form (HU-016)."""
    return AlpineAjaxResponse(
        template_name=PROJECT_TEMPLATE,
        context={"projetos": configuracoes.list_projects(session), "consulta": query},
        request=req,
        target_id=MODAL_TARGET,
    )


def _risk_values(risk: service.RiskLine) -> dict[str, str]:
    return {
        "natureza": risk.nature,
        "categoria": str(risk.category_id),
        "causa": risk.cause,
        "titulo": risk.title,
        "consequencia": risk.consequence,
        "descricao": risk.description or "",
        "donoId": str(risk.owner_id),
        "identificadoEm": risk.identified_on.isoformat(),
        "origemTipo": risk.origin_type,
        "ataId": str(risk.ata_id or ""),
        "gatilho": risk.trigger or "",
    }


def _risk_input(form: Mapping[str, str], *, project_id: int, code: str | None) -> RiskInput:
    return RiskInput(
        nature=form.get("natureza", ""),
        category_id=validation.parse_id(form.get("categoria")),
        cause=form.get("causa", ""),
        title=form.get("titulo", ""),
        consequence=form.get("consequencia", ""),
        owner_id=validation.parse_id(form.get("donoId")),
        identified_on=validation.parse_date(form.get("identificadoEm")),
        origin_type=form.get("origemTipo", ""),
        ata_id=validation.parse_id(form.get("ataId")),
        description=form.get("descricao", ""),
        trigger=form.get("gatilho", ""),
        version=form.get("versao"),
        project_id=project_id,
        code=code,
    )


def _save(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    project_id: int,
    code: str | None,
) -> func.HttpResponse:
    """Save the identification; ``acao=avaliar`` opens the assessment of the saved risk next."""
    form = req.form
    data = _risk_input(form, project_id=project_id, code=code)
    today = calendario.today()
    outcome: list[service.SaveResult] = []
    error = _attempt(
        session,
        lambda: outcome.append(
            service.save_risk(session, user=context.user, data=data, reference_date=today)
        ),
    )
    state = _FormState(
        project_id=project_id,
        code=code,
        query=form.get("consulta", ""),
        values=dict(form),
        version=form.get("versao"),
    )
    if error is not None or not outcome:
        return _risk_form(req, session, context, state=state, error=error)
    result = outcome[0]
    notice = (SAVED_NOTICE if result.created else EDITED_NOTICE).format(code=result.code)
    assess_next = result.code if form.get("acao") == "avaliar" else None
    return _screen(
        req,
        session,
        context,
        filters=_filters_of(state.query),
        after=_After(notice, {"avaliar_codigo": assess_next, "avisos": result.notices}),
    )


def _risk_form(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    state: _FormState,
    error: DomainError | None = None,
) -> func.HttpResponse:
    """The identification form, empty or filled in with the messages of a refusal."""
    today = calendario.today()
    risk = (
        service.find_risk(session, user=context.user, code=state.code, reference_date=today)
        if state.code
        else None
    )
    stale = isinstance(error, VersionConflictError)
    version = risk.version if risk and (stale or state.version is None) else state.version
    values = dict(state.values)
    values.setdefault("natureza", validation.NATURES[0])
    values.setdefault("identificadoEm", today.isoformat())
    values.setdefault("origemTipo", "Manual")
    projects = {item.id: item for item in configuracoes.list_projects(session)}
    project = projects.get(state.project_id)
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={
            "risco": risk,
            "projeto": project,
            "projeto_id": state.project_id,
            "padrao": _pattern_of(session, state.project_id),
            "versao": version,
            "consulta": state.query,
            "valores": values,
            "erros": _field_errors(error),
            "categorias": service.list_categories(session),
            "pessoas": configuracoes.list_people(session),
            "atas": service.ata_options(session, state.project_id),
            "origens": validation.MANUAL_ORIGINS,
            "naturezas": validation.NATURES,
            "ata_origem": validation.ATA_ORIGIN,
            "referencia": today.isoformat(),
            "natureza_travada": bool(risk and risk.strategy),
            "origem_do_sistema": bool(risk and risk.is_system_origin),
            "ja_avaliado": bool(risk and risk.inherent),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=200 if error is None else _error_status(error),
    )


def _pattern_of(session: Session, project_id: int) -> str:
    for item in configuracoes.list_project_risk_contexts(session):
        if item.id == project_id:
            return item.risk_pattern or "RSK"
    return "RSK"


def _category_form(
    req: func.HttpRequest,
    session: Session,
    *,
    values: Mapping[str, str],
    errors: Mapping[str, str],
    status: int = 200,
) -> func.HttpResponse:
    groups = sorted({item.group for item in service.list_categories(session)})
    return AlpineAjaxResponse(
        template_name=CATEGORY_FORM_TEMPLATE,
        context={"grupos": groups, "valores": dict(values), "erros": dict(errors)},
        request=req,
        target_id="risco-categoria-modal",
        status_code=status,
    )


def _assessment_values(
    risk: service.RiskLine, view: service.AssessmentView | None, kind: str
) -> dict[str, str]:
    values = {
        "tipo": kind,
        "p": str(view.probability) if view else "",
        "i": str(view.impact) if view else "",
        "impactoPrazoDias": str(risk.schedule_impact_days or ""),
        "impactoCustoCentavos": _reais_text(risk.cost_impact_cents),
        "riscoVida": "1" if risk.life_risk else "",
    }
    for key, _ in DIMENSIONS:
        level = view.dimensions.get(key) if view else None
        values[f"d_{key}"] = str(level or "")
    return values


def _reais_text(cents: int) -> str:
    """Cents as the form types them: ``1.850.000,00``; empty when there is no cost."""
    if not cents:
        return ""
    return format_value(ValueKind.DECIMAL, cents / 100)


def _assessment_input(form: Mapping[str, str]) -> AssessmentInput:
    return AssessmentInput(
        kind=form.get("tipo", ""),
        probability=validation.parse_level(form.get("p")),
        impact=validation.parse_level(form.get("i")),
        dimensions={key: validation.parse_level(form.get(f"d_{key}")) for key, _ in DIMENSIONS},
        schedule_impact_days=validation.parse_days(form.get("impactoPrazoDias")),
        cost_impact_cents=validation.parse_cents(form.get("impactoCustoCentavos")),
        life_risk=form.get("riscoVida") == "1",
        justification=form.get("justificativa", ""),
        version=form.get("versao"),
    )


def _assess_form(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    state: _AssessState,
    error: DomainError | None = None,
) -> func.HttpResponse:
    """The assessment form with its preview; a stale version carries the current one."""
    today = calendario.today()
    params = service.parameters(session, reference_date=today)
    risk = state.risk
    stale = isinstance(error, VersionConflictError)
    version = risk.version if stale or state.version is None else state.version
    values = dict(state.values)
    data = _assessment_input(values)
    preview = service.preview_score(session, user=context.user, data=data, reference_date=today)
    return AlpineAjaxResponse(
        template_name=ASSESS_TEMPLATE,
        context={
            "risco": risk,
            "versao": version,
            "consulta": state.query,
            "valores": values,
            "erros": _field_errors(error),
            "parametros": params,
            "dimensoes": DIMENSIONS,
            "oportunidade": risk.nature != calculations.THREAT,
            "previa": preview,
            "escala": params.scale,
            "etiqueta_de_faixa": lambda band: _severity_tone(band, params.scale),
            "formatar_moeda": _format_money,
            "texto_da_cadencia": _cadence_text_of,
            "tipo_atual": data.kind,
            "anterior": risk.displayed(
                validation.INHERENT if data.kind == validation.INHERENT else validation.RESIDUAL
            ),
            "alvo_previa": PREVIEW_TARGET,
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=200 if error is None else _error_status(error),
    )


def _preview_response(
    req: func.HttpRequest, preview: service.ScorePreview, scale: Scale, *, kind: str
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=PREVIEW_TEMPLATE,
        context={
            "previa": preview,
            "escala": scale,
            "etiqueta_de_faixa": lambda band: _severity_tone(band, scale),
            "formatar_moeda": _format_money,
            "texto_da_cadencia": _cadence_text_of,
            "tipo_atual": kind,
        },
        request=req,
        target_id=PREVIEW_TARGET,
    )


@dataclass(frozen=True)
class _DeleteState:
    """What the exclusion form remembers: the risk, the screen, what was typed and the messages."""

    risk: service.RiskLine
    query: str
    version: int | str | None
    values: Mapping[str, str] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)


def _delete_form(
    req: func.HttpRequest, state: _DeleteState, *, status: int = 200
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=DELETE_TEMPLATE,
        context={
            "risco": state.risk,
            "consulta": state.query,
            "valores": dict(state.values),
            "erros": dict(state.errors),
            "versao": state.version,
            "motivos": validation.DELETION_REASONS,
            "motivo_outro": validation.OTHER_REASON,
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status,
    )
