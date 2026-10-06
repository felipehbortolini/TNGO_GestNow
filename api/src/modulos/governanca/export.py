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


def register_document(
    overview: RegisterOverview,
    *,
    panel: ChangePanel,
    scope: Scope,
    projects: Sequence[ProjectLike],
    filters: ChangeFilter,
    today: date,
) -> Document:
    """The Registro de mudanças: the six KPIs, the table and the tables of the Painel."""
    return Document(
        title=REGISTER_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=_filter_context(filters),
        kpis=tuple(_kpi(card) for card in presentation.kpi_cards(overview)),
        charts=panel_charts.charts_of(panel),
        tables=(
            _changes_table(overview),
            _panel_situation_table(panel),
            _panel_pareto_table(panel),
            _panel_kind_table(panel),
            _panel_month_table(panel),
        ),
        paper=Paper.A4,
    )


def _panel_situation_table(panel: ChangePanel) -> Table:
    return Table(
        title="Mudanças por situação",
        columns=(Column("Situação", width=40), Column("Total", ValueKind.INTEGER)),
        rows=tuple(row(line.label, line.total) for line in panel.situations),
        per_project=False,
    )


def _panel_pareto_table(panel: ChangePanel) -> Table:
    return Table(
        title="Pareto por origem",
        columns=(
            Column("Origem", width=40),
            Column("Total", ValueKind.INTEGER),
            Column("%", ValueKind.PERCENT, digits=1),
            Column("% acumulado", ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(
            row(line.label, line.total, line.percent, line.cumulative) for line in panel.origins
        ),
        per_project=False,
    )


def _panel_kind_table(panel: ChangePanel) -> Table:
    return Table(
        title="Mudanças por tipo",
        columns=(Column("Tipo", width=40), Column("Total", ValueKind.INTEGER)),
        rows=tuple(row(line.label, line.total) for line in panel.kinds),
        per_project=False,
    )


def _panel_month_table(panel: ChangePanel) -> Table:
    return Table(
        title="Valor e prazo aprovados acumulados",
        columns=(
            Column("Mês", width=18),
            Column("Aprovadas", ValueKind.INTEGER),
            Column("Solicitadas", ValueKind.INTEGER),
            Column("Valor acumulado", ValueKind.MONEY),
            Column("Prazo acumulado (dias)", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                panel_charts.month_label(line.month),
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
    sheet: ChangeSheet, *, scope: Scope, projects: Sequence[ProjectLike], today: date
) -> Document:
    """The ficha of a change: the situation as KPIs and one table per tab."""
    return Document(
        title=f"{SHEET_TITLE_PREFIX} {sheet.change.code}",
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Projeto", sheet.project_label), ("Título", sheet.change.title)),
        kpis=_sheet_kpis(sheet),
        tables=(
            _fields_table("Solicitação", _request_fields(sheet)),
            _fields_table("Análise de impacto", _impact_fields(sheet)),
            _fields_table("Decisão", _decision_fields(sheet)),
            _fields_table("Implementação", _implementation_fields(sheet)),
            _history_table(sheet),
        ),
        paper=Paper.A4,
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


def _filter_context(filters: ChangeFilter) -> tuple[tuple[str, str], ...]:
    labelled = (
        ("Situação", filters.situation),
        ("Tipo", filters.kind),
        ("Origem", filters.origin),
        ("Prioridade", filters.priority),
        ("Alçada", filters.authority),
        ("Busca", filters.search),
    )
    return tuple((label, value) for label, value in labelled if value)


def _changes_table(overview: RegisterOverview) -> Table:
    return Table(
        title="Solicitações de mudança",
        columns=(
            Column("Nº", width=18),
            Column("Título", width=46),
            Column("Solicitada em", ValueKind.DATE),
            Column("Prioridade"),
            Column("Tipo · origem", width=34),
            Column("Custo", ValueKind.MONEY),
            Column("Prazo (dias)", ValueKind.INTEGER),
            Column("Situação", width=22),
            Column("Próxima etapa", width=40),
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
                item.next_step or _closed_text(item.closing_date),
                project=item.project_label,
            )
            for item in overview.rows
        ),
    )


def _closed_text(closing_date: date | None) -> str:
    return f"encerrada em {closing_date:%d/%m/%Y}" if closing_date else ""


# ── The ficha ────────────────────────────────────────────────────────────


def _sheet_kpis(sheet: ChangeSheet) -> tuple[Kpi, ...]:
    impact = sheet.impact
    return (
        Kpi(
            "Situação",
            sheet.change.situation,
            "Etapa do fluxo",
            tone=presentation.situation_tone(sheet.change.situation),
        ),
        Kpi("Impacto em custo", presentation.cost_text(impact.cost_cents if impact else None), ""),
        Kpi("Impacto em prazo", presentation.term_text(impact.term_days if impact else None), ""),
        Kpi("Alçada", sheet.change.authority or presentation.NO_VALUE, ""),
        Kpi("Próxima etapa", sheet.row.next_step or presentation.NO_VALUE, ""),
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


def _date(value: date | None) -> str:
    return f"{value:%d/%m/%Y}" if value else presentation.NO_VALUE


def _request_fields(sheet: ChangeSheet) -> list[tuple[str, str]]:
    change = sheet.change
    fields = [
        ("Número", change.code),
        ("Título", change.title),
        ("Tipo", change.kind),
        ("Origem", change.origin),
        ("Prioridade", change.priority),
        ("Solicitante", _text(sheet.requester_name)),
        ("Data da solicitação", _date(change.request_date)),
        ("Descrição e justificativa", change.description),
    ]
    if sheet.emergency_start is not None:
        fields.append(
            (
                "Execução emergencial",
                f"Iniciada em {_date(sheet.emergency_start)}. {change.emergency_justification or ''}",
            )
        )
    if change.situation == models.SITUATION_CANCELLED:
        who = f"{_date(change.closing_date)} por {_text(sheet.closed_by_name)}"
        fields.append(("Cancelamento", f"{who}: {change.closing_note or ''}"))
    return fields


def _impact_fields(sheet: ChangeSheet) -> list[tuple[str, str]]:
    impact = sheet.impact
    if impact is None:
        return [("Análise de impacto", NOT_REGISTERED)]
    return [
        ("Impacto em custo", presentation.cost_text(impact.cost_cents)),
        ("Impacto em prazo", presentation.term_text(impact.term_days)),
        (
            "Marco contratual",
            "Afeta marco contratual" if impact.affects_contract_milestone else "Sem impacto",
        ),
        ("Alçada de decisão", _text(sheet.change.authority)),
        ("Alçada mínima exigida", _text(sheet.required_authority)),
        (
            "Limite do gerente do projeto",
            format_brl(sheet.manager_limit_cents) if sheet.manager_limit_cents is not None else "·",
        ),
        ("Fonte do recurso", _text(sheet.change.resource_source)),
        ("Escopo", impact.scope),
        ("Qualidade e especificação", impact.quality),
        ("Riscos novos ou alterados", impact.risks),
        ("SMS", impact.safety),
        ("Contrato", impact.contract),
        ("Atividades do cronograma", _text(impact.activities)),
        ("Analista", _text(sheet.analyst_name)),
        ("Data da análise", _date(impact.analysis_date)),
    ]


def _decision_fields(sheet: ChangeSheet) -> list[tuple[str, str]]:
    if sheet.decision is None:
        return [("Decisão", NO_DECISION)]
    fields = _one_decision_fields(sheet.decision, sheet.change.authority)
    for earlier in sheet.previous_decisions:
        fields.append(
            (
                f"Decisão anterior ({_date(earlier.decision.decision_date)})",
                f"{earlier.decision.result}. {earlier.decision.justification}",
            )
        )
    return fields


def _one_decision_fields(view: DecisionView, authority: str | None) -> list[tuple[str, str]]:
    decision = view.decision
    fields = [
        ("Decisão", decision.result),
        ("Data", _date(decision.decision_date)),
        ("Alçada", _text(authority)),
        ("Participantes", ", ".join(view.participants) or presentation.NO_VALUE),
        ("Justificativa", decision.justification),
    ]
    if decision.conditions:
        fields.append(("Condições", decision.conditions))
    return fields


def _implementation_fields(sheet: ChangeSheet) -> list[tuple[str, str]]:
    change = sheet.change
    started = None if sheet.emergency_start else change.implementation_start
    fields = [
        ("Início da implementação", _date(started) if started else "não iniciada"),
        (
            "Nova revisão da EAC",
            f"Rev {change.eac_revision}" if change.eac_revision is not None else "pendente",
        ),
        (
            "Nova revisão da EAP",
            f"Rev {change.eap_revision}" if change.eap_revision is not None else "pendente",
        ),
    ]
    if change.situation == models.SITUATION_CLOSED:
        fields.append(("Encerramento", _date(change.closing_date)))
    return fields


def _history_table(sheet: ChangeSheet) -> Table:
    return Table(
        title="Histórico",
        columns=(
            Column("Quando", width=20),
            Column("Quem", width=28),
            Column("O que aconteceu", width=80),
        ),
        rows=tuple(
            row(f"{entry.moment:%d/%m/%Y %H:%M}", _text(entry.person_name), entry.text)
            for entry in sheet.history
        ),
        per_project=False,
    )
