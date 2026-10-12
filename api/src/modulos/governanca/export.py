"""Exports of the Governança module: the Registro de mudanças and the ficha of a change (D12).

Each screen builds one ``Document`` and the platform gives the Excel and the printable version from it
(``core.excel`` and ``core.printable``), so the two carry the same: the KPIs with their reference and
the table with every column of the list. In the Portfólio the list opens with the ``Projeto`` column
(HU-016). The ficha is of one project, so its tables are not per project and the project is named in the
header. The texts of the KPIs and of the cost and term come from ``presentation``: paper and screen agree.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core import translations
from src.core.export_document import (
    Cell,
    Column,
    Document,
    Kpi,
    Paper,
    Table,
    ValueKind,
    describe_scope,
    row,
)
from src.core.money import format_brl
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.governanca import models, presentation
from src.modulos.governanca import panel as panel_charts
from src.modulos.governanca.presentation import KpiCard
from src.modulos.governanca.service import (
    ChangeFilter,
    ChangePanel,
    ChangeSheet,
    DecisionView,
    RegisterOverview,
)

REGISTER_TITLE = "Registro de mudanças"
SHEET_TITLE_PREFIX = "Solicitação de mudança"
NOT_REGISTERED = "Não registrada."
NO_DECISION = "Sem decisão."

FIELD_COLUMNS = (Column("Campo", width=30), Column("Valor", width=90))


def _label(text: str, idioma: str) -> str:
    """O texto de interface da Governança no idioma do request (D13)."""
    return translations.translate("governanca", text, idioma)


def register_document(
    overview: RegisterOverview,
    *,
    panel: ChangePanel,
    scope: Scope,
    projects: Sequence[ProjectLike],
    filters: ChangeFilter,
    today: date,
    idioma: str = "pt",
) -> Document:
    """The Registro de mudanças: the six KPIs, the table and the tables of the Painel."""
    return Document(
        namespace="governanca",
        title=_label(REGISTER_TITLE, idioma),
        scope_label=describe_scope(scope, projects, idioma),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=_filter_context(filters, idioma),
        kpis=tuple(_kpi(card) for card in presentation.kpi_cards(overview, idioma)),
        charts=panel_charts.charts_of(panel, idioma),
        tables=(
            _changes_table(overview, idioma),
            _panel_situation_table(panel, idioma),
            _panel_pareto_table(panel, idioma),
            _panel_kind_table(panel, idioma),
            _panel_month_table(panel, idioma),
        ),
        paper=Paper.A4,
        idioma=idioma,
    )


def _panel_situation_table(panel: ChangePanel, idioma: str) -> Table:
    return Table(
        title=_label("Mudanças por situação", idioma),
        columns=(
            Column(_label("Situação", idioma), width=40),
            Column(_label("Total", idioma), ValueKind.INTEGER),
        ),
        rows=tuple(row(line.label, line.total) for line in panel.situations),
        per_project=False,
    )


def _panel_pareto_table(panel: ChangePanel, idioma: str) -> Table:
    return Table(
        title=_label("Pareto por origem", idioma),
        columns=(
            Column(_label("Origem", idioma), width=40),
            Column(_label("Total", idioma), ValueKind.INTEGER),
            Column("%", ValueKind.PERCENT, digits=1),
            Column(_label("% acumulado", idioma), ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(
            row(line.label, line.total, line.percent, line.cumulative) for line in panel.origins
        ),
        per_project=False,
    )


def _panel_kind_table(panel: ChangePanel, idioma: str) -> Table:
    return Table(
        title=_label("Mudanças por tipo", idioma),
        columns=(
            Column(_label("Tipo", idioma), width=40),
            Column(_label("Total", idioma), ValueKind.INTEGER),
        ),
        rows=tuple(row(line.label, line.total) for line in panel.kinds),
        per_project=False,
    )


def _panel_month_table(panel: ChangePanel, idioma: str) -> Table:
    return Table(
        title=_label("Valor e prazo aprovados acumulados", idioma),
        columns=(
            Column(_label("Mês", idioma), width=18),
            Column(_label("Aprovadas", idioma), ValueKind.INTEGER),
            Column(_label("Solicitadas", idioma), ValueKind.INTEGER),
            Column(_label("Valor acumulado", idioma), ValueKind.MONEY),
            Column(_label("Prazo acumulado (dias)", idioma), ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                panel_charts.month_label(line.month, idioma),
                line.approved,
                line.requested,
                line.value_cents,
                line.term_days,
            )
            for line in panel.months
        ),
        per_project=False,
    )


def sheet_document(
    sheet: ChangeSheet,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """The ficha of a change: the situation as KPIs and one table per tab."""
    return Document(
        namespace="governanca",
        title=f"{_label(SHEET_TITLE_PREFIX, idioma)} {sheet.change.code}",
        scope_label=describe_scope(scope, projects, idioma),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            (_label("Projeto", idioma), sheet.project_label),
            (_label("Título", idioma), sheet.change.title),
        ),
        kpis=_sheet_kpis(sheet, idioma),
        tables=(
            _fields_table(_label("Solicitação", idioma), _request_fields(sheet, idioma)),
            _fields_table(_label("Análise de impacto", idioma), _impact_fields(sheet, idioma)),
            _fields_table(_label("Decisão", idioma), _decision_fields(sheet, idioma)),
            _fields_table(_label("Implementação", idioma), _implementation_fields(sheet, idioma)),
            _history_table(sheet, idioma),
        ),
        paper=Paper.A4,
        idioma=idioma,
    )


# ── The register ─────────────────────────────────────────────────────────


def _kpi(card: KpiCard) -> Kpi:
    unit = f" {card.unit}" if card.unit else ""
    return Kpi(
        label=card.label,
        value=f"{card.value}{unit}",
        reference=card.reference,
        tone=card.tone,
        status=card.footer,
    )


def _filter_context(filters: ChangeFilter, idioma: str) -> tuple[tuple[str, str], ...]:
    labelled = (
        (_label("Situação", idioma), filters.situation),
        (_label("Tipo", idioma), filters.kind),
        (_label("Origem", idioma), filters.origin),
        (_label("Prioridade", idioma), filters.priority),
        (_label("Alçada", idioma), filters.authority),
        (_label("Busca", idioma), filters.search),
    )
    return tuple((label, value) for label, value in labelled if value)


def _changes_table(overview: RegisterOverview, idioma: str) -> Table:
    return Table(
        title=_label("Solicitações de mudança", idioma),
        columns=(
            Column("Nº", width=18),
            Column(_label("Título", idioma), width=46),
            Column(_label("Solicitada em", idioma), ValueKind.DATE),
            Column(_label("Prioridade", idioma)),
            Column(_label("Tipo · origem", idioma), width=34),
            Column(_label("Custo", idioma), ValueKind.MONEY),
            Column(_label("Prazo (dias)", idioma), ValueKind.INTEGER),
            Column(_label("Situação", idioma), width=22),
            Column(_label("Próxima etapa", idioma), width=40),
        ),
        rows=tuple(
            row(
                item.code,
                item.title,
                item.request_date,
                item.priority,
                f"{item.kind} · {item.origin}",
                item.cost_cents,
                item.term_days,
                Cell(item.situation, presentation.situation_tone(item.situation)),
                item.next_step or _closed_text(item.closing_date, idioma),
                project=item.project_label,
            )
            for item in overview.rows
        ),
    )


def _closed_text(closing_date: date | None, idioma: str) -> str:
    if not closing_date:
        return ""
    template = _label("encerrada em {date}", idioma)
    return template.format(date=translations.format_date(closing_date, idioma))


# ── The ficha ────────────────────────────────────────────────────────────


def _sheet_kpis(sheet: ChangeSheet, idioma: str) -> tuple[Kpi, ...]:
    impact = sheet.impact
    return (
        Kpi(
            _label("Situação", idioma),
            sheet.change.situation,
            _label("Etapa do fluxo", idioma),
            tone=presentation.situation_tone(sheet.change.situation),
        ),
        Kpi(
            _label("Impacto em custo", idioma),
            presentation.cost_text(impact.cost_cents if impact else None, idioma),
            "",
        ),
        Kpi(
            _label("Impacto em prazo", idioma),
            presentation.term_text(impact.term_days if impact else None, idioma),
            "",
        ),
        Kpi(_label("Alçada", idioma), sheet.change.authority or presentation.NO_VALUE, ""),
        Kpi(_label("Próxima etapa", idioma), sheet.row.next_step or presentation.NO_VALUE, ""),
    )


def _fields_table(title: str, fields: Sequence[tuple[str, str]]) -> Table:
    return Table(
        title=title,
        columns=FIELD_COLUMNS,
        rows=tuple(row(label, value) for label, value in fields),
        per_project=False,
    )


def _text(value: str | None) -> str:
    return value if value else presentation.NO_VALUE


def _date(value: date | None, idioma: str) -> str:
    return translations.format_date(value, idioma) if value else presentation.NO_VALUE


def _request_fields(sheet: ChangeSheet, idioma: str) -> list[tuple[str, str]]:
    change = sheet.change
    fields = [
        (_label("Número", idioma), change.code),
        (_label("Título", idioma), change.title),
        (_label("Tipo", idioma), change.kind),
        (_label("Origem", idioma), change.origin),
        (_label("Prioridade", idioma), change.priority),
        (_label("Solicitante", idioma), _text(sheet.requester_name)),
        (_label("Data da solicitação", idioma), _date(change.request_date, idioma)),
        (_label("Descrição e justificativa", idioma), change.description),
    ]
    if sheet.emergency_start is not None:
        fields.append(
            (
                _label("Execução emergencial", idioma),
                _label("Iniciada em {date}. {justification}", idioma).format(
                    date=_date(sheet.emergency_start, idioma),
                    justification=change.emergency_justification or "",
                ),
            )
        )
    if change.situation == models.SITUATION_CANCELLED:
        who = _label("{date} por {name}", idioma).format(
            date=_date(change.closing_date, idioma), name=_text(sheet.closed_by_name)
        )
        fields.append((_label("Cancelamento", idioma), f"{who}: {change.closing_note or ''}"))
    return fields


def _impact_fields(sheet: ChangeSheet, idioma: str) -> list[tuple[str, str]]:
    impact = sheet.impact
    if impact is None:
        return [(_label("Análise de impacto", idioma), _label(NOT_REGISTERED, idioma))]
    return [
        (_label("Impacto em custo", idioma), presentation.cost_text(impact.cost_cents, idioma)),
        (_label("Impacto em prazo", idioma), presentation.term_text(impact.term_days, idioma)),
        (
            _label("Marco contratual", idioma),
            _label(
                "Afeta marco contratual" if impact.affects_contract_milestone else "Sem impacto",
                idioma,
            ),
        ),
        (_label("Alçada de decisão", idioma), _text(sheet.change.authority)),
        (_label("Alçada mínima exigida", idioma), _text(sheet.required_authority)),
        (
            _label("Limite do gerente do projeto", idioma),
            format_brl(sheet.manager_limit_cents) if sheet.manager_limit_cents is not None else "·",
        ),
        (_label("Fonte do recurso", idioma), _text(sheet.change.resource_source)),
        (_label("Escopo", idioma), impact.scope),
        (_label("Qualidade e especificação", idioma), impact.quality),
        (_label("Riscos novos ou alterados", idioma), impact.risks),
        (_label("SMS", idioma), impact.safety),
        (_label("Contrato", idioma), impact.contract),
        (_label("Atividades do cronograma", idioma), _text(impact.activities)),
        (_label("Analista", idioma), _text(sheet.analyst_name)),
        (_label("Data da análise", idioma), _date(impact.analysis_date, idioma)),
    ]


def _decision_fields(sheet: ChangeSheet, idioma: str) -> list[tuple[str, str]]:
    if sheet.decision is None:
        return [(_label("Decisão", idioma), _label(NO_DECISION, idioma))]
    fields = _one_decision_fields(sheet.decision, sheet.change.authority, idioma)
    for earlier in sheet.previous_decisions:
        fields.append(
            (
                _label("Decisão anterior ({date})", idioma).format(
                    date=_date(earlier.decision.decision_date, idioma)
                ),
                f"{earlier.decision.result}. {earlier.decision.justification}",
            )
        )
    return fields


def _one_decision_fields(
    view: DecisionView, authority: str | None, idioma: str
) -> list[tuple[str, str]]:
    decision = view.decision
    fields = [
        (_label("Decisão", idioma), decision.result),
        (_label("Data", idioma), _date(decision.decision_date, idioma)),
        (_label("Alçada", idioma), _text(authority)),
        (_label("Participantes", idioma), ", ".join(view.participants) or presentation.NO_VALUE),
        (_label("Justificativa", idioma), decision.justification),
    ]
    if decision.conditions:
        fields.append((_label("Condições", idioma), decision.conditions))
    return fields


def _implementation_fields(sheet: ChangeSheet, idioma: str) -> list[tuple[str, str]]:
    change = sheet.change
    started = None if sheet.emergency_start else change.implementation_start
    fields = [
        (
            _label("Início da implementação", idioma),
            _date(started, idioma) if started else _label("não iniciada", idioma),
        ),
        (
            _label("Nova revisão da EAC", idioma),
            f"Rev {change.eac_revision}"
            if change.eac_revision is not None
            else _label("pendente", idioma),
        ),
        (
            _label("Nova revisão da EAP", idioma),
            f"Rev {change.eap_revision}"
            if change.eap_revision is not None
            else _label("pendente", idioma),
        ),
    ]
    if change.situation == models.SITUATION_CLOSED:
        fields.append((_label("Encerramento", idioma), _date(change.closing_date, idioma)))
    return fields


def _history_table(sheet: ChangeSheet, idioma: str) -> Table:
    return Table(
        title=_label("Histórico", idioma),
        columns=(
            Column(_label("Quando", idioma), width=20),
            Column(_label("Quem", idioma), width=28),
            Column(_label("O que aconteceu", idioma), width=80),
        ),
        rows=tuple(
            row(
                f"{entry.moment:%d/%m/%Y %H:%M}",
                _text(entry.person_name),
                entry.text,
            )
            for entry in sheet.history
        ),
        per_project=False,
    )
