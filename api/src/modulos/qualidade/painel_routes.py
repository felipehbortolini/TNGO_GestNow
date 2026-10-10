"""Routes of the Painel da qualidade (ISSUE-071, D11, D12, D14).

Prefix ``/api/qualidade/``. The panel is one fragment, ``painel-conteudo``: the five KPIs of the
prototype (the open RNC with the overdue and the critical, the average treatment with the band
of the deadlines, the approval of the inspections and the conformity of the audits against the
targets, and the cost of the non-quality), the alert of the overdue audits (hidden when there
is none), the four visuals of the library (the RNC by month, the approval with the dashed
target, the Pareto by discipline and the RNC by origin) and the two tables (the treatment
agenda and the performance by company). The charts travel as data (``data-grafico`` +
``data-dados``, D11); the fragment carries no ``<script>``. In the Portfólio the agenda opens
with the ``Projeto`` column (the company table stays aggregated by company, as the prototype).

* ``GET qualidade/painel`` and ``painel/excel``/``painel/imprimivel``   the panel and its exports.

The rules are in ``painel_service``; the routes only read the request, call it and draw the
answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, origin_links
from src.core.excel import excel_response
from src.core.export_document import Document
from src.core.printable import printable_response
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import service as configuracoes
from src.modulos.qualidade import export, painel_service
from src.modulos.qualidade.painel_service import QualityPanel

bp = func.Blueprint()

MODULE = "qualidade"
READ = Access(module=MODULE)

PANEL_TARGET = "painel-conteudo"
PANEL_TEMPLATE = "qualidade/painel.html"
PANEL_ROUTE = "/api/qualidade/painel"

SCREEN_RNC = "qualidade/rnc"
SCREEN_INSPECTIONS = "qualidade/inspecoes"
SCREEN_AUDITS = "qualidade/auditorias"
NOT_ASSESSED = "·"


@dataclass(frozen=True)
class KpiCard:
    """Um indicador do painel, já escrito como a pessoa o lê."""

    label: str
    icon: str
    tone: str
    value: str
    unit: str
    reference: str
    footer: str
    url: str


@bp.route(route="qualidade/painel", methods=["GET"])
@fragment_route(access=READ)
def quality_panel_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O painel do escopo: os indicadores, o alerta, os quatro gráficos e as duas tabelas."""
    panel = _panel(session, context)
    return AlpineAjaxResponse(
        template_name=PANEL_TEMPLATE,
        context=_panel_context(session, context, panel),
        request=req,
        target_id=PANEL_TARGET,
    )


@bp.route(route="qualidade/painel/excel", methods=["GET"])
@file_route(access=READ)
def quality_panel_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do painel: os indicadores, os números dos gráficos e as duas tabelas."""
    del req
    return excel_response(_panel_document(session, context))


@bp.route(route="qualidade/painel/imprimivel", methods=["GET"])
@fragment_route(access=READ)
def quality_panel_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A folha imprimível do painel: o mesmo documento, com os gráficos, para o botão PDF."""
    return printable_response(_panel_document(session, context), req)


def _panel(session: Session, context: RequestContext) -> QualityPanel:
    return painel_service.quality_panel(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
    )


def _panel_context(
    session: Session, context: RequestContext, panel: QualityPanel
) -> dict[str, object]:
    return {
        "painel": panel,
        "kpis": _kpi_cards(panel),
        "graficos": {
            "rnc_mes": export.panel_month_chart(panel),
            "aprovacao": export.panel_approval_chart(panel),
            "pareto": export.panel_discipline_chart(panel),
            "origem": export.panel_origin_chart(panel),
        },
        "alerta_auditorias": _audit_alert(panel),
        "portfolio": context.scope.is_portfolio,
        "rotulos_de_projeto": _project_labels(session),
        "link_rnc": origin_links.link_to_screen(SCREEN_RNC) or "",
        "link_da_rnc": _rnc_link,
        "url_excel": f"{PANEL_ROUTE}/excel",
        "url_pdf": f"{PANEL_ROUTE}/imprimivel",
        "formatar_data": _format_date,
        "formatar_moeda": _format_money,
        "formatar_decimal": _one_decimal,
        "formatar_percentual": _zero_decimals,
        "situacao": "vazio-origem" if panel.is_empty else "conteudo",
    }


def _kpi_cards(panel: QualityPanel) -> list[KpiCard]:
    """Os cinco indicadores do protótipo, cada um com a sua referência de gestão e o seu link."""
    indicators = panel.indicators
    open_tone = (
        "erro"
        if indicators.overdue_rncs or indicators.critical_open_rncs
        else "warn"
        if indicators.open_rncs
        else "ok"
    )
    approval_tone = (
        "info"
        if indicators.inspection_approval_pct is None
        else "ok"
        if indicators.inspection_approval_pct >= indicators.inspection_approval_target_pct
        else "warn"
    )
    conformity_tone = (
        "info"
        if indicators.audit_conformity_pct is None
        else "ok"
        if indicators.audit_conformity_pct >= indicators.audit_conformity_target_pct
        else "warn"
    )
    effectiveness = (
        ""
        if indicators.first_time_effectiveness_pct is None
        else (
            " · "
            f"{_zero_decimals(indicators.first_time_effectiveness_pct)}% eficazes na 1ª verificação"
        )
    )
    adherence = (
        NOT_ASSESSED
        if indicators.audit_program_adherence_pct is None
        else f"{_zero_decimals(indicators.audit_program_adherence_pct)}%"
    )
    return [
        KpiCard(
            label="RNC em aberto",
            icon="warning",
            tone=open_tone,
            value=str(indicators.open_rncs),
            unit="",
            reference="Esperado: 0",
            footer=(
                f"{_plural(indicators.overdue_rncs, 'vencida', 'vencidas')} · "
                f"{_plural(indicators.critical_open_rncs, 'crítica', 'críticas')}"
            ),
            url=origin_links.link_to_screen(SCREEN_RNC) or "",
        ),
        KpiCard(
            label="Tempo médio de tratamento",
            icon="clock",
            tone="info",
            value=(
                NOT_ASSESSED
                if indicators.average_treatment_days is None
                else str(indicators.average_treatment_days)
            ),
            unit="" if indicators.average_treatment_days is None else "dias",
            reference=f"Limite: {panel.treatment_limit}",
            footer=(
                _plural(indicators.closed_rncs, "RNC encerrada", "RNCs encerradas") + effectiveness
            ),
            url="",
        ),
        KpiCard(
            label="Aprovação em inspeções",
            icon="checkCircle",
            tone=approval_tone,
            value=(
                NOT_ASSESSED
                if indicators.inspection_approval_pct is None
                else _one_decimal(indicators.inspection_approval_pct)
            ),
            unit="" if indicators.inspection_approval_pct is None else "%",
            reference=f"Meta: {indicators.inspection_approval_target_pct:.0f}%",
            footer=(
                f"{_plural(indicators.rejected_inspections, 'reprovada', 'reprovadas')} "
                f"em {indicators.inspections}"
            ),
            url=origin_links.link_to_screen(SCREEN_INSPECTIONS) or "",
        ),
        KpiCard(
            label="Conformidade em auditorias",
            icon="shield",
            tone=conformity_tone,
            value=(
                NOT_ASSESSED
                if indicators.audit_conformity_pct is None
                else _one_decimal(indicators.audit_conformity_pct)
            ),
            unit="" if indicators.audit_conformity_pct is None else "%",
            reference=f"Meta: {indicators.audit_conformity_target_pct:.0f}%",
            footer=(
                f"programa {adherence} cumprido · "
                f"{_plural(indicators.overdue_audits, 'atrasada', 'atrasadas')}"
            ),
            url=origin_links.link_to_screen(SCREEN_AUDITS) or "",
        ),
        KpiCard(
            label="Custo da não qualidade",
            icon="money",
            tone="erro" if indicators.non_quality_cost_cents else "ok",
            value=_format_money(indicators.non_quality_cost_cents),
            unit="",
            reference=f"Esperado: {_format_money(0)}",
            footer="soma das RNC (retrabalho, reparo, ensaios e perdas)",
            url="",
        ),
    ]


def _audit_alert(panel: QualityPanel) -> tuple[str, str] | None:
    """O título e os detalhes do alerta de auditorias atrasadas; ``None`` quando não há nenhuma."""
    if not panel.overdue_audits:
        return None
    title = _plural(len(panel.overdue_audits), "auditoria atrasada", "auditorias atrasadas")
    details = "; ".join(
        f"{audit.code} {audit.scope} (planejada para {_format_date(audit.audit_date)})"
        for audit in panel.overdue_audits
    )
    return (title, details)


def _panel_document(session: Session, context: RequestContext) -> Document:
    """O documento do painel para o escopo da requisição; a leitura do relógio fica no serviço."""
    panel = _panel(session, context)
    return export.build_panel_document(
        panel,
        scope=context.scope,
        projects=configuracoes.list_project_details(session),
        today=panel.reference_date,
    )


def _project_labels(session: Session) -> dict[int, str]:
    return {
        project.id: f"{project.code} · {project.name}"
        for project in configuracoes.list_project_details(session)
    }


def _rnc_link(code: str) -> str:
    """O endereço da lista de RNC com a busca do número, como as telas irmãs linkam."""
    return origin_links.link_to_screen(SCREEN_RNC, busca=code) or ""


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _format_money(cents: int | None) -> str:
    if not cents:
        return "R$ 0,00"
    reais, centavos = divmod(cents, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def _one_decimal(value: Decimal) -> str:
    """A decimal as the prototype writes the KPI: one fixed decimal place, comma (``85,0``)."""
    return f"{value:.1f}".replace(".", ",")


def _zero_decimals(value: Decimal) -> str:
    """A decimal rounded to the unit as the prototype writes the targets and shares (``67``)."""
    return str(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
