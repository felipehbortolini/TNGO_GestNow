"""Rotas do Painel HSE (ISSUE-075, D11, D12, D14).

Prefixo ``/api/hse/painel``. O painel é um fragmento, ``painel-conteudo``: a barra de filtros
(ano, mês e a referência da pirâmide, na query), a linha de período, os três blocos de
indicadores do protótipo (no mês, acumulado e proativos), os dois visuais da biblioteca (a
pirâmide dupla e a evolução mensal de TF e TRIF, D11) e as listas por área e por empresa. Os
gráficos viajam como dados (``data-grafico`` + ``data-dados``); o fragmento não traz ``<script>``.
Excel e PDF saem pelos mecanismos genéricos (``data-tn-excel`` e ``data-tn-pdf``, D12), com a
query da tela: o export lê o mesmo ano, mês e referência.

* ``GET hse/painel``   o painel (``ano``, ``mes`` e ``referencia`` na query);
* ``GET hse/painel/excel`` e ``hse/painel/imprimivel``   as duas exportações.

No Portfólio os indicadores são do escopo inteiro e as listas por área e por empresa são
agregadas (sem a coluna ``Projeto``, como o protótipo). As regras estão em ``painel_service``;
as rotas só leem a requisição, chamam e desenham a resposta.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, origin_links
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, export, painel_service
from src.modulos.hse.calculations import HseIndicators
from src.modulos.hse.painel_service import HsePanel

bp = func.Blueprint()

MODULE = "hse"
READ = Access(module=MODULE)

PANEL_TARGET = "painel-conteudo"
PANEL_TEMPLATE = "hse/painel.html"
PANEL_ROUTE = "/api/hse/painel"
SCREEN_OCCURRENCES = "hse/ocorrencias"
SCREEN_HOURS = "hse/hht"
NOT_ASSESSED = "·"


@bp.route(route="hse/painel", methods=["GET"])
@fragment_route(access=READ)
def hse_panel_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O painel do escopo: os filtros, os indicadores, os gráficos e as duas listas."""
    panel = _panel(session, context, params=req.params)
    return AlpineAjaxResponse(
        template_name=PANEL_TEMPLATE,
        context=_panel_context(context, panel),
        request=req,
        target_id=PANEL_TARGET,
    )


@bp.route(route="hse/painel/excel", methods=["GET"])
@file_route(access=READ)
def hse_panel_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do painel: os indicadores, as tabelas das pirâmides, a evolução e as listas."""
    return excel_response(_panel_document(session, context, params=req.params))


@bp.route(route="hse/painel/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def hse_panel_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A folha imprimível do painel: o mesmo documento, com os gráficos, para o botão PDF."""
    return printable_response(_panel_document(session, context, params=req.params), req)


def _panel(session: Session, context: RequestContext, *, params: Mapping[str, str]) -> HsePanel:
    """O painel da query: o ano e o mês escolhem a janela e a referência sobrepõe o parâmetro."""
    months = painel_service.panel_months(session, scope=context.scope)
    month = painel_service.resolve_month(
        months,
        year=params.get("ano"),
        requested=calculations.parse_month(params.get("mes")),
    )
    return painel_service.panel(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
        month=month,
        pyramid_kind=params.get("referencia"),
    )


def _panel_document(
    session: Session, context: RequestContext, *, params: Mapping[str, str]
) -> Document:
    """O documento do painel para o escopo e a query da requisição; o relógio fica na rota."""
    panel = _panel(session, context, params=params)
    return export.panel_document(
        panel,
        scope=context.scope,
        projects=configuracoes.list_projects(session),
        today=panel.reference_date,
    )


def _panel_context(context: RequestContext, panel: HsePanel) -> dict[str, object]:
    query = urlencode(_state(panel))
    month = panel.month_indicators
    accumulated = panel.accumulated_indicators
    return {
        "painel": panel,
        "kpis_mes": [] if month is None else _reactive_kpis(month, footer="no mês"),
        "kpis_acumulado": (
            []
            if accumulated is None
            else [
                *_reactive_kpis(accumulated, footer="no acumulado"),
                _days_kpi(panel, accumulated, portfolio=context.scope.is_portfolio),
                _actions_kpi(accumulated),
            ]
        ),
        "kpis_proativos": ([] if accumulated is None else _proactive_kpis(panel, accumulated)),
        "grafico_piramide": ({} if panel.is_empty else painel_service.pyramid_chart(panel)),
        "grafico_evolucao": ({} if panel.is_empty else painel_service.evolution_chart(panel)),
        "anos": panel.years,
        "meses": panel.month_options,
        "mes_selecionado": (
            calculations.month_label(panel.month) if panel.month is not None else ""
        ),
        "referencia": panel.reference.kind,
        "linha_periodo": _period_line(panel),
        "maximo_area": _maximum(panel.by_area),
        "maximo_empresa": _maximum(panel.by_company),
        "url_excel": f"{PANEL_ROUTE}/excel?{query}" if query else f"{PANEL_ROUTE}/excel",
        "url_pdf": (f"{PANEL_ROUTE}/imprimivel?{query}" if query else f"{PANEL_ROUTE}/imprimivel"),
        "link_ocorrencias": origin_links.link_to_screen(SCREEN_OCCURRENCES) or "",
        "link_hht": origin_links.link_to_screen(SCREEN_HOURS) or "",
        "portfolio": context.scope.is_portfolio,
        "situacao": "vazio-origem" if panel.is_empty else "conteudo",
    }


def _state(panel: HsePanel) -> dict[str, str]:
    """O estado efetivo da tela (ano, mês e referência), como a exportação o relê."""
    if panel.month is None:
        return {}
    return {
        "ano": panel.year,
        "mes": calculations.month_label(panel.month),
        "referencia": panel.reference.kind,
    }


def _period_line(panel: HsePanel) -> str:
    """``Mês: Set/2026 · Acumulado: Jan/2026 a Set/2026 · base 1.000.000 HHT (NBR 14280)``."""
    if panel.month is None or panel.window_start is None or panel.window_end is None:
        return ""
    return (
        f"Mês: {calculations.month_display(panel.month)}"
        f" · Acumulado: {calculations.month_display(panel.window_start)}"
        f" a {calculations.month_display(panel.window_end)}"
        f" · base {_integer_text(panel.base)} HHT ({calculations.rate_base_name(panel.base)})"
    )


def _reactive_kpis(indicators: HseIndicators, *, footer: str) -> list[dict[str, str]]:
    """Os quatro indicadores reativos do protótipo (TF, TRIF, TG e HiPo)."""
    return [
        {
            "rotulo": "Taxa de frequência (TF)",
            "valor": _decimal_text(indicators.tf, 2),
            "icone": "warning",
            "tom": "erro" if indicators.lti else "ok",
            "referencia": "Esperado: 0,00",
            "rodape": (
                _plural(indicators.lti, "acidente com afastamento", "acidentes com afastamento")
                + f" {footer}"
            ),
        },
        {
            "rotulo": "Lesões registráveis (TRIF)",
            "valor": _decimal_text(indicators.trif, 2),
            "icone": "errorCircle",
            "tom": "warn" if indicators.registrable else "ok",
            "referencia": "Esperado: 0,00",
            "rodape": _plural(indicators.registrable, "lesão registrável", "lesões registráveis"),
        },
        {
            "rotulo": "Taxa de gravidade (TG)",
            "valor": _decimal_text(indicators.tg, 1),
            "icone": "clock",
            "tom": "info",
            "referencia": "Esperado: 0,0",
            "rodape": "dias perdidos e debitados x base / HHT",
        },
        {
            "rotulo": "Alto potencial (HiPo)",
            "valor": str(indicators.hipo),
            "icone": "sparkle",
            "tom": "erro" if indicators.hipo else "ok",
            "referencia": "Esperado: 0",
            "rodape": _plural(indicators.hipo, "ocorrência", "ocorrências") + f" {footer}",
        },
    ]


def _days_kpi(panel: HsePanel, indicators: HseIndicators, *, portfolio: bool) -> dict[str, str]:
    """Dias sem afastamento: o valor do acumulado e o esperado desde o início do projeto."""
    expected = calculations.days_without_leave(None, panel.project_start, panel.reference_date)
    return {
        "rotulo": "Dias sem afastamento",
        "valor": str(indicators.days_without_leave or 0),
        "icone": "calendar",
        "tom": "neutro",
        "referencia": (
            f"Esperado: {expected}" if expected is not None else f"Esperado: {NOT_ASSESSED}"
        ),
        "rodape": _days_footer(panel, portfolio=portfolio),
    }


def _days_footer(panel: HsePanel, *, portfolio: bool) -> str:
    if panel.last_lti is not None:
        return f"última LTI em {_date_text(panel.last_lti)}"
    if panel.project_start is not None:
        inicio = "da carteira" if portfolio else "do projeto"
        return f"desde o início {inicio} ({_date_text(panel.project_start)})"
    return "nenhum acidente com afastamento registrado"


def _actions_kpi(indicators: HseIndicators) -> dict[str, str]:
    """Ações HSE no prazo contra a meta da tela (o protótipo tinha o limiar no código da página)."""
    pct = indicators.actions_on_time_pct
    return {
        "rotulo": "Ações HSE no prazo",
        "valor": _percent_text(pct),
        "icone": "checkCircle",
        "tom": (
            "ok" if pct is not None and pct >= painel_service.ACTIONS_ON_TIME_TARGET else "warn"
        ),
        "referencia": f"Meta: ≥ {painel_service.ACTIONS_ON_TIME_TARGET}%",
        "rodape": "",
    }


def _proactive_kpis(panel: HsePanel, indicators: HseIndicators) -> list[dict[str, str]]:
    """Os seis indicadores proativos do protótipo."""
    return [
        {
            "rotulo": "DDS realizados",
            "valor": _percent_text(indicators.dds_pct),
            "icone": "calendar",
            "tom": "info",
            "referencia": "Meta: 100%",
            "rodape": "",
        },
        {
            "rotulo": "Conformidade em inspeções",
            "valor": _percent_text(indicators.conformity_pct),
            "icone": "checkCircle",
            "tom": "info",
            "referencia": "Esperado: 100%",
            "rodape": "",
        },
        {
            "rotulo": "Observações / 10 mil HHT",
            "valor": _decimal_text(indicators.observations_per_10k, 1),
            "icone": "eye",
            "tom": "info",
            "referencia": f"Meta: ≥ {panel.observations_target}",
            "rodape": "",
        },
        {
            "rotulo": "Relato de quase acidentes",
            "valor": _decimal_text(indicators.almost_miss_report, 1),
            "icone": "search",
            "tom": "info",
            "referencia": (
                "Referência: "
                + format_value(ValueKind.DECIMAL, panel.reference.almost_miss_ratio, 1)
            ),
            "rodape": "quase acidentes por lesão registrável",
        },
        {
            "rotulo": "Recomendações fechadas (APR/HAZOP)",
            "valor": _percent_text(indicators.recommendations_pct),
            "icone": "file",
            "tom": "info",
            "referencia": "Esperado: 100%",
            "rodape": "",
        },
        {
            "rotulo": "Incidentes ambientais",
            "valor": str(indicators.environmental),
            "icone": "errorCircle",
            "tom": "warn" if indicators.environmental else "ok",
            "referencia": "Esperado: 0",
            "rodape": "",
        },
    ]


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _maximum(lines: Sequence[painel_service.HseGroupLine]) -> int:
    """O maior total das listas, para a barra proporcional do template (1 sem ocorrências)."""
    return max((line.total for line in lines), default=0) or 1


def _integer_text(value: int) -> str:
    return format_value(ValueKind.INTEGER, value)


def _decimal_text(value: Decimal | None, digits: int) -> str:
    return NOT_ASSESSED if value is None else format_value(ValueKind.DECIMAL, value, digits)


def _percent_text(value: Decimal | None) -> str:
    return NOT_ASSESSED if value is None else format_value(ValueKind.PERCENT, value, 1)


def _date_text(value: date) -> str:
    return format_value(ValueKind.DATE, value)
