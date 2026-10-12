"""Routes of the Ocorrências screen (D14, ISSUE-073).

Prefix ``/api/hse/ocorrencias``. The screen is one fragment (``ocorrencias-conteudo``): the four
indicators, the filters and the list, with the actions of the flow on each line. Filters, page and
search are plain GETs of the same route with the state in the query string. The ficha and the forms
open in the modal (``ocorrencias-modal-corpo``): a GET draws them, a POST saves and answers the
refreshed list with a hidden marker that reopens the ficha; a refusal (422, 409, 403) answers the
form again, filled in, in the modal.

* ``GET  ocorrencias`` the screen (filters and page by query);
* ``GET  ocorrencias/excel`` and ``ocorrencias/imprimivel`` the two exports;
* ``GET  ocorrencias/{codigo}/ficha`` the ficha (investigation, actions, history, lesson);
* ``GET/POST ocorrencias/nova`` the new occurrence (with the restricted data, Q35);
* ``GET/POST ocorrencias/{codigo}/investigar`` the preliminary investigation;
* ``GET/POST ocorrencias/{codigo}/acoes`` a corrective action in the Central;
* ``GET/POST ocorrencias/{codigo}/tratamento`` the start of the treatment;
* ``GET/POST ocorrencias/{codigo}/encerrar`` the closing with the effectiveness (Gestor);
* ``GET  ocorrencias/{codigo}/restrito`` the restricted block (Gestor and Admin only, Q35).

The rules are in ``service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, origin_links, rbac, translations
from src.core.errors import DomainError, InvalidDataError
from src.core.excel import excel_response
from src.core.export_document import ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import export, forms, models, service, validation
from src.modulos.hse.routes import _attempt, _field_errors, _helpers, _status

bp = func.Blueprint()


def _label(text: str, idioma: str) -> str:
    """O texto de interface do módulo no idioma do request (D13)."""
    return translations.translate("hse", text, idioma)


def _notice(text: str | None, req: func.HttpRequest) -> str | None:
    """O aviso de uma gravação no idioma do request (D13)."""
    if not text:
        return text
    return translations.translate("hse", text, translations.language_of(req))


MODULE = "hse"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)
MANAGE = Access(module=MODULE, permission=Permission.MANAGE)
RESTRICTED = Access(module=MODULE, permission=Permission.VIEW_RESTRICTED)

CONTENT_TARGET = "ocorrencias-conteudo"
MODAL_TARGET = "ocorrencias-modal-corpo"
RESTRICTED_TARGET = "ocorrencia-restrito"
ROUTE = "/api/hse/ocorrencias"
NOT_FOUND = "Ocorrência não encontrada."
PAGE_SIZE = 20

SCREEN_TEMPLATE = "hse/ocorrencias.html"
SHEET_TEMPLATE = "hse/ocorrencia_ficha.html"
NEW_TEMPLATE = "hse/ocorrencia_nova.html"
INVESTIGATION_TEMPLATE = "hse/ocorrencia_investigar.html"
ACTION_TEMPLATE = "hse/ocorrencia_acao.html"
TREATMENT_TEMPLATE = "hse/ocorrencia_tratamento.html"
CLOSE_TEMPLATE = "hse/ocorrencia_encerrar.html"
RESTRICTED_TEMPLATE = "hse/ocorrencia_restrito.html"

# The choices of the new form that do not come from the register: the same lists of the prototype.
GRAVITY_CHOICES = (
    ("1", "Sem lesão · dano leve ou nenhum"),
    ("2", "Lesão leve · ou dano moderado"),
    ("3", "Lesão moderada · ou dano considerável"),
    ("4", "Lesão grave · com afastamento"),
    ("5", "Fatalidade"),
)
PROBABILITY_CHOICES = (
    ("1", "Muito baixa · raramente ocorre"),
    ("2", "Baixa · já ocorreu antes"),
    ("3", "Média · pode ocorrer"),
    ("4", "Alta · ocorre com frequência"),
    ("5", "Muito alta · condição recorrente"),
)
IMPACT_CHOICES = (
    ("1", "Leve · primeiros socorros"),
    ("2", "Moderado · tratamento médico"),
    ("3", "Sério · afastamento"),
    ("4", "Grave · invalidez"),
    ("5", "Catastrófico · fatalidade"),
)

NEW_FIELDS = frozenset(
    {
        "data",
        "hora",
        "area",
        "empresa",
        "tipo",
        "subtipo",
        "severidade",
        "descricao",
        "funcao",
        "pessoas",
        "potencial",
        "gravidade",
        "causa_imediata",
        "comunicacao",
        "dias_perdidos",
        "dias_debitados",
        "medica",
    }
)
INVESTIGATION_FIELDS = frozenset({"metodo", "causa_raiz", "data"})
ACTION_FIELDS = frozenset({"assunto", "descricao", "responsavel", "prevista", "acoes"})
CLOSE_FIELDS = frozenset({"eficacia", "data", "titulo", "recomendacao"})


def _modal_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A refusal inside the modal: the message in the modal body, where the person is looking."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=MODAL_TARGET,
        status_code=_status(error),
        toast=messages[0] if messages else _notice("Não foi possível concluir.", req),
        toast_tipo="erro",
    )


def _general_messages(errors: Mapping[str, str], shown: frozenset[str]) -> list[str]:
    """As mensagens sem campo no formulário para carregá-las (a versão, o registro)."""
    return [message for name, message in errors.items() if name not in shown]


def _query(form: Mapping[str, str]) -> dict[str, str]:
    """O estado da tela que o formulário carregou de volta (``busca=...&pagina=2``)."""
    return dict(parse_qsl(form.get("consulta", "")))


@dataclass(frozen=True)
class _Page:
    """A slice of the list: the rows of the page and where the page sits."""

    rows: tuple[Any, ...]
    page: int
    page_count: int
    total: int


def _paginate(rows: Sequence[Any], page: int) -> _Page:
    page_count = max(1, -(-len(rows) // PAGE_SIZE))
    current = min(max(page, 1), page_count)
    start = (current - 1) * PAGE_SIZE
    return _Page(
        rows=tuple(rows[start : start + PAGE_SIZE]),
        page=current,
        page_count=page_count,
        total=len(rows),
    )


def _state_of(filters: validation.OccurrenceFilters) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "busca": filters.search,
            "situacao": filters.situation,
            "tipo": filters.kind,
            "hipo": "1" if filters.hipo else "",
        }.items()
        if value
    }


def _page_link(state: Mapping[str, str], page: int, page_count: int) -> str:
    if page < 1 or page > page_count:
        return ""
    return f"{ROUTE}?{urlencode({**state, 'pagina': page})}"


def _occurrence_kpis(screen: service.OccurrenceScreen) -> list[dict[str, str]]:
    summary = screen.summary
    deadlines = screen.deadlines

    def number(value: int) -> str:
        return format_value(ValueKind.INTEGER, value)

    return [
        {
            "rotulo": "Ocorrências no projeto",
            "valor": number(summary.total),
            "icone": "warning",
            "tom": "info",
            "referencia": f"Referência: de {number(screen.universe)} registradas",
            "rodape": "O nível 5 (desvios) vem do consolidado mensal",
        },
        {
            "rotulo": "Em aberto",
            "valor": number(summary.open_count),
            "icone": "clock",
            "tom": "warn" if summary.open_count else "ok",
            "referencia": "Esperado: 0",
            "rodape": "Não encerradas",
        },
        {
            "rotulo": "Alto potencial (HiPo) em aberto",
            "valor": number(summary.hipo_open),
            "icone": "target",
            "tom": "erro" if summary.hipo_open else "ok",
            "referencia": "Esperado: 0",
            "rodape": "HiPo sem encerramento",
        },
        {
            "rotulo": "Fora do prazo (comunicação, investigação ou relatório)",
            "valor": number(summary.overdue),
            "icone": "errorCircle",
            "tom": "erro" if summary.overdue else "ok",
            "referencia": "Esperado: 0",
            "rodape": (
                f"Limites: {deadlines.communication_hours} h, "
                f"{deadlines.investigation_hours} h e {deadlines.report_days} dias"
            ),
        },
    ]


def _screen_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    filters: validation.OccurrenceFilters,
    page: int,
    notice: str | None = None,
    abrir_ficha: str | None = None,
) -> func.HttpResponse:
    today = calendario.today()
    screen = service.occurrences_screen(
        session, scope=context.scope, filters=filters, reference_date=today
    )
    shown = _paginate(screen.rows, page)
    state = _state_of(filters)
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={
            "kpis": _occurrence_kpis(screen),
            "linhas": shown.rows,
            "total": shown.total,
            "pagina": shown.page,
            "pagina_total": shown.page_count,
            "link_anterior": _page_link(state, shown.page - 1, shown.page_count),
            "link_proximo": _page_link(state, shown.page + 1, shown.page_count),
            "consulta": urlencode({**state, "pagina": shown.page}),
            "url_excel": f"{ROUTE}/excel?{urlencode(state)}",
            "url_pdf": f"{ROUTE}/imprimivel?{urlencode(state)}",
            "filtros": filters,
            "tem_filtro": bool(state),
            "situacoes": models.OCCURRENCE_SITUATIONS,
            "tipos": models.OCCURRENCE_TYPES,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "pode_gerir": rbac.can(context.user, Permission.MANAGE),
            "portfolio": context.scope.is_portfolio,
            "abrir_ficha": abrir_ficha,
            **_helpers(),
        },
        request=req,
        target_id=CONTENT_TARGET,
        toast=_notice(notice, req),
    )


def _document(
    session: Session, context: RequestContext, filters: validation.OccurrenceFilters
) -> Any:
    today = calendario.today()
    screen = service.occurrences_screen(
        session, scope=context.scope, filters=filters, reference_date=today
    )
    return export.occurrences_document(
        screen,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=today,
        idioma=context.idioma,
    )


@bp.route(route="hse/ocorrencias", methods=["GET"])
@fragment_route(access=READ)
def occurrence_list_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A tela: indicadores, filtros, lista e páginas, para os filtros da query."""
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_filters(req.params),
        page=validation.parse_page(req.params),
    )


@bp.route(route="hse/ocorrencias/excel", methods=["GET"])
@file_route(access=READ)
def occurrence_list_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do que a tela lista, com os indicadores."""
    return excel_response(_document(session, context, validation.parse_filters(req.params)))


@bp.route(route="hse/ocorrencias/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def occurrence_list_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do mesmo documento: o que o botão PDF monta e imprime."""
    return printable_response(
        _document(session, context, validation.parse_filters(req.params)), req
    )


# ── Ficha ────────────────────────────────────────────────────────────────────────────────────


def _link_to_lesson(code: str | None) -> str | None:
    if not code:
        return None
    return origin_links.link_to_screen("governanca/licoes", busca=code)


@bp.route(route="hse/ocorrencias/{codigo}/ficha", methods=["GET"])
@fragment_route(access=READ)
def occurrence_sheet_fragment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A ficha da ocorrência: investigação, ações da Central, histórico e a lição do HiPo."""
    code = (req.route_params.get("codigo") or "").strip()
    sheet = service.occurrence_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(NOT_FOUND)
    names = service.names_of(session)
    return AlpineAjaxResponse(
        template_name=SHEET_TEMPLATE,
        context={
            "ficha": sheet,
            "pode_gravar": rbac.can(context.user, Permission.WRITE),
            "pode_gerir": rbac.can(context.user, Permission.MANAGE),
            "ver_restrito": rbac.can(context.user, Permission.VIEW_RESTRICTED),
            "url_restrito": f"{ROUTE}/{sheet.line.code}/restrito",
            "alvo_restrito": RESTRICTED_TARGET,
            "lesson_url": _link_to_lesson(sheet.lesson_code),
            "nomes": {
                record.responsible_id: names.person(record.responsible_id)
                for record in sheet.actions
            },
            "consulta": urlencode(_query(req.form) or dict(req.params)),
            **_helpers(),
        },
        request=req,
        target_id=MODAL_TARGET,
    )


# ── Nova ocorrência ─────────────────────────────────────────────────────────────────────────


def _new_context(
    session: Session,
    *,
    valores: Mapping[str, str],
    erros: Mapping[str, str],
    consulta: str,
) -> dict[str, Any]:
    today = calendario.today()
    deadlines = service.deadlines_in_force(session, reference_date=today)
    return {
        "valores": valores,
        "erros": erros,
        "erros_gerais": [message for name, message in erros.items() if name not in NEW_FIELDS],
        "consulta": consulta,
        "referencia": today.isoformat(),
        "empresas": service.company_options(session),
        "tipos": models.OCCURRENCE_TYPES,
        "subtipos": models.ENVIRONMENTAL_SUBTYPES,
        "severidades": models.ENVIRONMENTAL_SEVERITIES,
        "causas": validation.IMMEDIATE_CAUSES,
        "gravidades": GRAVITY_CHOICES,
        "probabilidades": PROBABILITY_CHOICES,
        "impactos": IMPACT_CHOICES,
        "prazo_comunicacao": deadlines.communication_hours,
        **_helpers(),
    }


@dataclass(frozen=True)
class _NewForm:
    """O que o formulário da nova ocorrência lembra: o que foi digitado e a recusa."""

    valores: Mapping[str, str]
    erros: Mapping[str, str]
    consulta: str


def _new_form(
    req: func.HttpRequest,
    session: Session,
    state: _NewForm,
    *,
    status_code: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=NEW_TEMPLATE,
        context=_new_context(
            session, valores=state.valores, erros=state.erros, consulta=state.consulta
        ),
        request=req,
        target_id=MODAL_TARGET,
        status_code=status_code,
    )


@bp.route(route="hse/ocorrencias/nova", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def occurrence_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário vazio, no projeto do escopo."""
    context.scope.require_project()
    return _new_form(req, session, _NewForm({}, {}, req.params.get("consulta", "")))


@bp.route(route="hse/ocorrencias/nova", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def occurrence_new_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra a ocorrência com o prazo vigente gravado e o restrito na mesma transação."""
    form = req.form
    data = forms.parse_occurrence(form, project_id=context.scope.require_project())
    result, error = _attempt(
        session,
        lambda: service.save_occurrence(
            session, user=context.user, data=data, reference_date=calendario.today()
        ),
    )
    if error is not None or result is None:
        return _new_form(
            req,
            session,
            _NewForm(dict(form), _field_errors(error), form.get("consulta", "")),
            status_code=_status(error) if error is not None else 422,
        )
    notice = f"Ocorrência {result.code} registrada."
    if result.avisos:
        notice = f"{notice} {' '.join(result.avisos)}"
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_filters(_query(form)),
        page=validation.parse_page(_query(form)),
        notice=notice,
        abrir_ficha=result.code,
    )


# ── Investigação ────────────────────────────────────────────────────────────────────────────


def _sheet_or_refuse(
    session: Session, context: RequestContext, code: str
) -> service.OccurrenceSheet:
    sheet = service.occurrence_sheet(
        session, user=context.user, code=code, reference_date=calendario.today()
    )
    if sheet is None:
        raise InvalidDataError(NOT_FOUND)
    return sheet


def _investigation_context(
    sheet: service.OccurrenceSheet,
    *,
    valores: Mapping[str, str],
    erros: Mapping[str, str],
    consulta: str,
) -> dict[str, Any]:
    today = calendario.today()
    return {
        "linha": sheet.line,
        "valores": valores,
        "erros": erros,
        "erros_gerais": [
            message for name, message in erros.items() if name not in INVESTIGATION_FIELDS
        ],
        "referencia": today.isoformat(),
        "metodos": models.INVESTIGATION_METHODS,
        "consulta": consulta,
    }


@bp.route(route="hse/ocorrencias/{codigo}/investigar", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def occurrence_investigate_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da investigação preliminar."""
    sheet = _sheet_or_refuse(session, context, (req.route_params.get("codigo") or "").strip())
    return AlpineAjaxResponse(
        template_name=INVESTIGATION_TEMPLATE,
        context=_investigation_context(
            sheet, valores={}, erros={}, consulta=req.params.get("consulta", "")
        ),
        request=req,
        target_id=MODAL_TARGET,
    )


@bp.route(route="hse/ocorrencias/{codigo}/investigar", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def occurrence_investigate_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra a investigação e move a ocorrência para Em investigação."""
    form = req.form
    code = (req.route_params.get("codigo") or "").strip()
    data = forms.parse_investigation(form)
    result, error = _attempt(
        session,
        lambda: service.record_investigation(
            session,
            user=context.user,
            code=code,
            data=data,
            reference_date=calendario.today(),
        ),
    )
    if error is not None or result is None:
        sheet = _sheet_or_refuse(session, context, code)
        return AlpineAjaxResponse(
            template_name=INVESTIGATION_TEMPLATE,
            context=_investigation_context(
                sheet,
                valores=dict(form),
                erros=_field_errors(error),
                consulta=form.get("consulta", ""),
            ),
            request=req,
            target_id=MODAL_TARGET,
            status_code=_status(error) if error is not None else 422,
        )
    notice = "Investigação registrada."
    if result.late:
        notice = f"{notice} Atenção: fora do prazo preliminar."
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_filters(_query(form)),
        page=validation.parse_page(_query(form)),
        notice=notice,
        abrir_ficha=code,
    )


# ── Ação corretiva ──────────────────────────────────────────────────────────────────────────


def _action_context(
    session: Session,
    sheet: service.OccurrenceSheet,
    *,
    valores: Mapping[str, str],
    erros: Mapping[str, str],
    consulta: str,
) -> dict[str, Any]:
    return {
        "linha": sheet.line,
        "valores": valores,
        "erros": erros,
        "erros_gerais": [message for name, message in erros.items() if name not in ACTION_FIELDS],
        "pessoas": service.person_options(session),
        "referencia": calendario.today().isoformat(),
        "consulta": consulta,
    }


@bp.route(route="hse/ocorrencias/{codigo}/acoes", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def occurrence_action_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário de uma ação corretiva."""
    sheet = _sheet_or_refuse(session, context, (req.route_params.get("codigo") or "").strip())
    return AlpineAjaxResponse(
        template_name=ACTION_TEMPLATE,
        context=_action_context(
            session, sheet, valores={}, erros={}, consulta=req.params.get("consulta", "")
        ),
        request=req,
        target_id=MODAL_TARGET,
    )


@bp.route(route="hse/ocorrencias/{codigo}/acoes", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def occurrence_action_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cria a ação corretiva na Central (origem HSE) na mesma transação."""
    form = req.form
    code = (req.route_params.get("codigo") or "").strip()
    data = forms.parse_corrective_action(form)
    _, error = _attempt(
        session,
        lambda: service.define_corrective_actions(
            session,
            user=context.user,
            code=code,
            actions_input=(data,),
            reference_date=calendario.today(),
        ),
    )
    if error is not None:
        sheet = _sheet_or_refuse(session, context, code)
        return AlpineAjaxResponse(
            template_name=ACTION_TEMPLATE,
            context=_action_context(
                session,
                sheet,
                valores=dict(form),
                erros=_field_errors(error),
                consulta=form.get("consulta", ""),
            ),
            request=req,
            target_id=MODAL_TARGET,
            status_code=_status(error),
        )
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_filters(_query(form)),
        page=validation.parse_page(_query(form)),
        notice="Ação corretiva criada na Central.",
        abrir_ficha=code,
    )


# ── Tratamento ──────────────────────────────────────────────────────────────────────────────


@bp.route(route="hse/ocorrencias/{codigo}/tratamento", methods=["GET"])
@fragment_route(access=WRITE, on_error=_modal_error)
def occurrence_treatment_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A confirmação do início do tratamento."""
    sheet = _sheet_or_refuse(session, context, (req.route_params.get("codigo") or "").strip())
    return AlpineAjaxResponse(
        template_name=TREATMENT_TEMPLATE,
        context={"linha": sheet.line, "consulta": req.params.get("consulta", "")},
        request=req,
        target_id=MODAL_TARGET,
    )


@bp.route(route="hse/ocorrencias/{codigo}/tratamento", methods=["POST"])
@fragment_route(access=WRITE, on_error=_modal_error)
def occurrence_treatment_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Inicia o tratamento da ocorrência."""
    form = req.form
    code = (req.route_params.get("codigo") or "").strip()
    _, error = _attempt(
        session, lambda: service.start_treatment(session, user=context.user, code=code)
    )
    if error is not None:
        raise error
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_filters(_query(form)),
        page=validation.parse_page(_query(form)),
        notice="Tratamento iniciado.",
        abrir_ficha=code,
    )


# ── Encerramento (Gestor) ───────────────────────────────────────────────────────────────────


def _close_context(
    sheet: service.OccurrenceSheet,
    *,
    valores: Mapping[str, str],
    erros: Mapping[str, str],
    consulta: str,
) -> dict[str, Any]:
    return {
        "linha": sheet.line,
        "valores": valores,
        "erros": erros,
        "erros_gerais": [message for name, message in erros.items() if name not in CLOSE_FIELDS],
        "referencia": calendario.today().isoformat(),
        "evento": sheet.line.moment_text,
        "acoes_abertas": sheet.open_actions,
        "consulta": consulta,
    }


@bp.route(route="hse/ocorrencias/{codigo}/encerrar", methods=["GET"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def occurrence_close_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do encerramento com a verificação de eficácia."""
    sheet = _sheet_or_refuse(session, context, (req.route_params.get("codigo") or "").strip())
    return AlpineAjaxResponse(
        template_name=CLOSE_TEMPLATE,
        context=_close_context(
            sheet, valores={}, erros={}, consulta=req.params.get("consulta", "")
        ),
        request=req,
        target_id=MODAL_TARGET,
    )


@bp.route(route="hse/ocorrencias/{codigo}/encerrar", methods=["POST"])
@fragment_route(access=MANAGE, on_error=_modal_error)
def occurrence_close_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Encerra a ocorrência; um HiPo exige a lição e a abre em Rascunho na mesma transação."""
    form = req.form
    code = (req.route_params.get("codigo") or "").strip()
    data = forms.parse_closure(form)
    result, error = _attempt(
        session,
        lambda: service.close_occurrence(
            session,
            user=context.user,
            code=code,
            data=data,
            reference_date=calendario.today(),
        ),
    )
    if error is not None or result is None:
        sheet = _sheet_or_refuse(session, context, code)
        return AlpineAjaxResponse(
            template_name=CLOSE_TEMPLATE,
            context=_close_context(
                sheet,
                valores=dict(form),
                erros=_field_errors(error),
                consulta=form.get("consulta", ""),
            ),
            request=req,
            target_id=MODAL_TARGET,
            status_code=_status(error) if error is not None else 422,
        )
    notice = "Ocorrência encerrada."
    if result.report_late:
        notice = f"{notice} Atenção: relatório final fora do prazo."
    if result.lesson_code:
        notice = f"{notice} Lição {result.lesson_code} criada em Rascunho."
    return _screen_response(
        req,
        session,
        context,
        filters=validation.parse_filters(_query(form)),
        page=validation.parse_page(_query(form)),
        notice=notice,
        abrir_ficha=code,
    )


# ── O campo restrito (Q35) ──────────────────────────────────────────────────────────────────


@bp.route(route="hse/ocorrencias/{codigo}/restrito", methods=["GET"])
@fragment_route(access=RESTRICTED, on_error=_modal_error)
def occurrence_restricted_fragment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O bloco restrito da ficha: só Gestor e Admin (403 para os demais, Q35)."""
    code = (req.route_params.get("codigo") or "").strip()
    restricted = service.restricted_view(session, user=context.user, code=code)
    if restricted is None:
        raise InvalidDataError(NOT_FOUND)
    return AlpineAjaxResponse(
        template_name=RESTRICTED_TEMPLATE,
        context={
            "restrito": restricted,
            "gravidades": GRAVITY_CHOICES,
            **_helpers(),
        },
        request=req,
        target_id=RESTRICTED_TARGET,
    )
