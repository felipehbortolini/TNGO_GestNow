"""Routes of the matrix and the panel of Riscos (ISSUE-066, D11, D12, D14).

Prefix ``/api/riscos/``. The matrix is one fragment, ``matriz-conteudo``: the Inerente/Residual
switch, the nature filter, the 5 x 5 visual of the library (the cell carries the register filtered
by ``celula``), the legend by the bands of the active scale and the movement from the inherent to
the residual score. The panel is one fragment, ``painel-conteudo``: the five indicators, the
exposure by category of the RBS, the monthly evolution reconstructed from the history (never a
stored series) and the escalation agenda; the send of the agenda opens in the modal
(``riscos-pauta-modal``) and goes through the notification port, recorded as ``simulado`` while
the e-mail sending is off.

* ``GET  matriz`` and ``matriz/excel``/``matriz/imprimivel``   the matrix and its two exports;
* ``GET  painel`` and ``painel/excel``/``painel/imprimivel``   the panel and its two exports;
* ``GET/POST painel/pauta``                                    the modal and the send of the agenda.

The rules are in ``panel_service``; the routes only read the request, call it and draw the answer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, notification, origin_links, rbac, translations
from src.core.errors import DomainError, InvalidDataError
from src.core.excel import excel_response
from src.core.export_document import Document
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.riscos import export, panel_service, presentation, routes
from src.modulos.riscos.calculations import OPPORTUNITY, THREAT
from src.modulos.riscos.panel_service import RiskMatrix, RiskPanel
from src.modulos.riscos.service import BandCount
from src.modulos.riscos.validation import INHERENT, RESIDUAL, RiskFilters

bp = func.Blueprint()


def _label(text: str, idioma: str) -> str:
    """O texto de interface do módulo no idioma do request (D13)."""
    return translations.translate("riscos", text, idioma)


def _chart_data(data: Mapping[str, object], idioma: str) -> dict[str, object]:
    """O JSON do gráfico no idioma do request: textos pelo catálogo e os rótulos do motor (D13)."""
    translated = _translated_strings(data, idioma)
    especificos = data.get("rotulos")
    if not isinstance(especificos, Mapping):
        especificos = {}
    translated["rotulos"] = translations.rotulos_de_grafico(idioma, dict(especificos))
    return translated


def _translated_strings(data: Mapping[str, object], idioma: str) -> dict[str, object]:
    """Os textos de dentro do JSON (títulos, séries, eixos) no idioma; a forma fica igual."""
    translated: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, str):
            translated[key] = translations.translate("riscos", value, idioma)
        elif isinstance(value, Mapping):
            translated[key] = _translated_strings(value, idioma)
        elif isinstance(value, list):
            translated[key] = [
                _translated_strings(item, idioma)
                if isinstance(item, Mapping)
                else translations.translate("riscos", item, idioma)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            translated[key] = value
    return translated


def _notice(text: str, req: func.HttpRequest) -> str:
    """O aviso de uma gravação no idioma do request (D13)."""
    return translations.translate("riscos", text, translations.language_of(req))


MODULE = "riscos"
READ = Access(module=MODULE)
WRITE = Access(module=MODULE, permission=Permission.WRITE)

MATRIX_TARGET = "matriz-conteudo"
MATRIX_TEMPLATE = "riscos/matriz.html"
MATRIX_ROUTE = "/api/riscos/matriz"

PANEL_TARGET = "painel-conteudo"
PANEL_TEMPLATE = "riscos/painel.html"
PANEL_ROUTE = "/api/riscos/painel"
PANEL_MODAL_TARGET = "riscos-pauta-modal"
AGENDA_TEMPLATE = "riscos/pauta_envio.html"

NATURES = (
    ("", "Natureza: todas"),
    (THREAT, "Somente ameaças"),
    (OPPORTUNITY, "Somente oportunidades"),
)
SEND_BUTTON = "Enviar por e-mail"


@dataclass(frozen=True)
class PanelKpi:
    """Um indicador do painel, já escrito como a pessoa o lê."""

    label: str
    icon: str
    tone: str
    value: str
    reference: str
    footer: str
    url: str
    active: bool


@dataclass(frozen=True)
class AgendaResult:
    """O que o modal mostra depois do envio da pauta."""

    aviso: str
    simulado: bool
    erro: bool


@dataclass(frozen=True)
class AgendaForm:
    """O formulário do envio: o destinatário do cadastro e a mensagem sugerida."""

    destinatario: str
    mensagem: str


# ── Matriz P x I ─────────────────────────────────────────────────────────────────────────────


@bp.route(route="riscos/matriz", methods=["GET"])
@fragment_route(access=READ)
def risk_matrix_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A matriz do escopo: o alternador, a natureza, o visual 5x5, a legenda e a movimentação."""
    return _matrix_response(req, session, context)


@bp.route(route="riscos/matriz/excel", methods=["GET"])
@file_route(access=READ)
def risk_matrix_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da matriz: a distribuição por célula e a movimentação inerente-residual."""
    return excel_response(_matrix_document(req, session, context))


@bp.route(route="riscos/matriz/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def risk_matrix_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A folha imprimível da matriz: o mesmo documento, para o botão PDF."""
    return printable_response(_matrix_document(req, session, context), req)


def _matrix_response(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    matrix = _matrix(req, session, context)
    return AlpineAjaxResponse(
        template_name=MATRIX_TEMPLATE,
        context=_matrix_context(session, context, matrix, translations.language_of(req)),
        request=req,
        target_id=MATRIX_TARGET,
    )


def _matrix(req: func.HttpRequest, session: Session, context: RequestContext) -> RiskMatrix:
    return panel_service.risk_matrix(
        session,
        user=context.user,
        scope=context.scope,
        assessment=_assessment(req),
        nature=_nature(req),
        reference_date=calendario.today(),
    )


def _assessment(req: func.HttpRequest) -> str:
    return INHERENT if req.params.get("aval") == INHERENT else RESIDUAL


def _nature(req: func.HttpRequest) -> str:
    chosen = req.params.get("natureza", "")
    return chosen if chosen in (THREAT, OPPORTUNITY) else ""


def _matrix_context(
    session: Session, context: RequestContext, matrix: RiskMatrix, idioma: str = "pt"
) -> dict[str, object]:
    return {
        "matriz": matrix,
        "grafico": _chart_data(export.matrix_chart(matrix), idioma),
        "link_inerente": _matrix_link(INHERENT, matrix.nature),
        "link_residual": _matrix_link(RESIDUAL, matrix.nature),
        "naturezas": NATURES,
        "link_registro": presentation.screen_address(
            RiskFilters(assessment=matrix.assessment, nature=matrix.nature)
        ),
        "url_excel": f"{MATRIX_ROUTE}/excel{_matrix_query(matrix)}",
        "url_pdf": f"{MATRIX_ROUTE}/imprimivel{_matrix_query(matrix)}",
        "portfolio": context.scope.is_portfolio,
        "rotulos_de_projeto": _project_labels(session),
        "link_da_ficha": _ficha_link,
        "tons_das_faixas": {style.band.id: style.tone for style in matrix.bands},
        "situacao": "vazio-origem" if matrix.registered == 0 else "conteudo",
    }


def _matrix_link(assessment: str, nature: str) -> str:
    parameters = {"aval": assessment}
    if nature:
        parameters["natureza"] = nature
    return f"{MATRIX_ROUTE}?{urlencode(parameters)}"


def _matrix_query(matrix: RiskMatrix) -> str:
    parameters: dict[str, str] = {}
    if matrix.assessment == INHERENT:
        parameters["aval"] = INHERENT
    if matrix.nature:
        parameters["natureza"] = matrix.nature
    return f"?{urlencode(parameters)}" if parameters else ""


def _matrix_document(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    return export.matrix_document(
        _matrix(req, session, context),
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
        idioma=context.idioma,
    )


# ── Painel de riscos ─────────────────────────────────────────────────────────────────────────


@bp.route(route="riscos/painel", methods=["GET"])
@fragment_route(access=READ)
def risk_panel_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O painel do escopo: os indicadores, as categorias, a evolução e a pauta."""
    panel = _panel(session, context)
    return AlpineAjaxResponse(
        template_name=PANEL_TEMPLATE,
        context=_panel_context(session, context, panel, translations.language_of(req)),
        request=req,
        target_id=PANEL_TARGET,
    )


@bp.route(route="riscos/painel/excel", methods=["GET"])
@file_route(access=READ)
def risk_panel_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do painel: os indicadores, a evolução, as categorias e a pauta."""
    del req
    return excel_response(_panel_document(session, context))


@bp.route(route="riscos/painel/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def risk_panel_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A folha imprimível do painel: o mesmo documento, para o botão PDF."""
    return printable_response(_panel_document(session, context), req)


def _panel(session: Session, context: RequestContext) -> RiskPanel:
    return panel_service.risk_panel(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
    )


def _panel_context(
    session: Session, context: RequestContext, panel: RiskPanel, idioma: str = "pt"
) -> dict[str, object]:
    scale = panel.parameters.scale
    return {
        "painel": panel,
        "kpis": _panel_kpis(panel),
        "grafico": _chart_data(export.panel_evolution_chart(panel), idioma),
        "maximo_da_categoria": max((item.score for item in panel.categories), default=0) or 1,
        "portfolio": context.scope.is_portfolio,
        "rotulos_de_projeto": _project_labels(session),
        "link_da_ficha": _ficha_link,
        "link_registro": presentation.screen_address(RiskFilters()),
        "url_excel": f"{PANEL_ROUTE}/excel",
        "url_pdf": f"{PANEL_ROUTE}/imprimivel",
        "etiqueta_de_faixa": lambda band: routes._severity_tone(band, scale),
        "formatar_moeda": routes._format_money,
        "pode_gravar": rbac.can(context.user, Permission.WRITE),
        "rotulo_do_envio": SEND_BUTTON,
        "resumo_da_pauta": _agenda_summary(panel),
        "situacao": "vazio-origem" if panel.summary.registered == 0 else "conteudo",
    }


def _agenda_summary(panel: RiskPanel) -> str:
    """A frase do protótipo acima da pauta: quantos riscos exigem a decisão do gerente."""
    if not panel.agenda:
        return "Nenhum risco exige decisão do gerente do projeto"
    count = panel_service.plural(len(panel.agenda), "risco exige", "riscos exigem")
    return (
        f"{count} decisão do gerente do projeto: severidade fora do alvo perto do prazo, "
        "sem redução após o plano, plano aguardando aprovação, gatilho ocorrido ou revisão vencida"
    )


def _panel_kpis(panel: RiskPanel) -> list[PanelKpi]:
    summary = panel.summary
    cards = [_band_card(summary.top, "erro", "warning")]
    if summary.second is not None:
        cards.append(_band_card(summary.second, "warn", "errorCircle"))
    cards.append(
        PanelKpi(
            label="Exposição (VME)",
            icon="money",
            tone="neutro",
            value=routes._format_money(summary.exposure_cents),
            reference="Ameaças ativas",
            footer="probabilidade média da faixa x impacto em custo",
            url="",
            active=False,
        )
    )
    cards.append(
        PanelKpi(
            label="Revisão vencida",
            icon="calendar",
            tone="erro" if summary.overdue else "ok",
            value=str(len(summary.overdue)),
            reference="Esperado: 0",
            footer=panel_service.plural(summary.active, "risco ativo", "riscos ativos"),
            url=presentation.screen_address(RiskFilters(review="vencidas")),
            active=False,
        )
    )
    cards.append(
        PanelKpi(
            label="Redução média",
            icon="sort",
            tone="info",
            value="—" if panel.reduction_avg_pct is None else f"{panel.reduction_avg_pct}%",
            reference=(
                f"Meta: ≥ {panel.reduction_target_pct}%"
                if panel.reduction_target_pct is not None
                else "Meta: —"
            ),
            footer="inerente para residual, ameaças com avaliação residual",
            url="",
            active=False,
        )
    )
    return cards


def _band_card(count: BandCount, tone: str, icon: str) -> PanelKpi:
    footer = panel_service.plural(count.threats, "ameaça", "ameaças")
    if count.opportunities:
        footer += " · " + panel_service.plural(count.opportunities, "oportunidade", "oportunidades")
    return PanelKpi(
        label=f"{count.band.name}s",
        icon=icon,
        tone=tone if count.total else "ok",
        value=str(count.total),
        reference=f"Meta: {count.goal}",
        footer=footer if count.total else "nenhum na faixa",
        url=presentation.screen_address(RiskFilters(severities=(count.band.id,))),
        active=False,
    )


def _panel_document(session: Session, context: RequestContext) -> Document:
    return export.panel_document(
        _panel(session, context),
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=calendario.today(),
        idioma=context.idioma,
    )


# ── Envio da pauta ───────────────────────────────────────────────────────────────────────────


def _agenda_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A recusa dentro do modal da pauta: a mensagem no corpo onde a pessoa está olhando."""
    mensagens = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": mensagens},
        request=req,
        target_id=PANEL_MODAL_TARGET,
        status_code=routes._error_status(error),
        toast=mensagens[0] if mensagens else _notice("Não foi possível concluir.", req),
        toast_tipo="erro",
    )


@bp.route(route="riscos/painel/pauta", methods=["GET"])
@fragment_route(access=WRITE, on_error=_agenda_error)
def risk_panel_agenda_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O modal do envio: o destinatário do cadastro e a mensagem padrão do protótipo."""
    panel = _panel(session, context)
    target = panel_service.agenda_target(session, scope=context.scope, panel=panel)
    formulario = AgendaForm(
        destinatario=target.email,
        mensagem=panel_service.agenda_default_message(
            panel, scope_label=target.scope_label, reference_date=calendario.today()
        ),
    )
    return _agenda_response(req, target.scope_label, formulario=formulario, resultado=None)


@bp.route(route="riscos/painel/pauta", methods=["POST"])
@fragment_route(access=WRITE, on_error=_agenda_error)
def risk_panel_agenda_send(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Envia a pauta ao gerente e responde o que foi registrado, com o toast."""
    outcome = panel_service.send_risk_agenda(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
        message=req.form.get("mensagem", ""),
    )
    resultado = AgendaResult(
        aviso=outcome.notice,
        simulado=outcome.situation == notification.SIMULATED,
        erro=outcome.situation == notification.FAILED,
    )
    return _agenda_response(
        req,
        _scope_label(session, context),
        formulario=None,
        resultado=resultado,
        toast=_notice(outcome.notice, req),
        toast_tipo=outcome.toast_kind,
    )


def _agenda_response(
    req: func.HttpRequest,
    escopo: str,
    *,
    formulario: AgendaForm | None,
    resultado: AgendaResult | None,
    toast: str | None = None,
    toast_tipo: str = "ok",
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name=AGENDA_TEMPLATE,
        context={"formulario": formulario, "resultado": resultado, "escopo": escopo},
        request=req,
        target_id=PANEL_MODAL_TARGET,
        toast=toast,
        toast_tipo=toast_tipo,
    )


# ── Common helpers ───────────────────────────────────────────────────────────────────────────


def _ficha_link(code: str) -> str:
    return origin_links.link_to_screen("riscos/ficha", codigo=code) or ""


def _project_labels(session: Session) -> dict[int, str]:
    return {
        project.id: f"{project.code} · {project.name}"
        for project in configuracoes.list_projects(session)
    }


def _scope_label(session: Session, context: RequestContext) -> str:
    project_id = context.scope.project_id
    if project_id is None:
        return "Portfólio"
    project = configuracoes.find_project(session, project_id)
    return f"{project.code} · {project.name}" if project is not None else ""
