"""Exports of the HSE screens: one ``Document`` each, the Excel and the printable version (D12).

What a screen shows is what leaves: the HHT screen exports its four indicators with their
reference, the HHT table and the labour histogram; the screen Inspeções e observações exports its
four indicators and the four lists (monthly closings, inspections, observations and DDS). In the
Portfólio every table opens with ``Projeto`` (HU-016). The name of the person observed leaves only
for who may read it (Q35).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from src.core.export_document import (
    Cell,
    Column,
    Document,
    Kpi,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.hse import calculations, service
from src.modulos.hse.calculations import ProactiveSummary

HOURS_TITLE = "Horas trabalhadas (HHT)"
PROACTIVE_TITLE = "Inspeções, observações e DDS"
HOURS_FILE = "hht-hse"
PROACTIVE_FILE = "inspecoes-hse"
NONE = "·"


def hours_document(
    screen: service.HoursScreen,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    names: service.Names,
    today: date,
) -> Document:
    """The document of the HHT screen: indicators, the HHT table and the labour histogram."""
    return Document(
        title=HOURS_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        kpis=_hours_kpis(screen),
        tables=(_hours_table(screen), _histogram_table(screen, names)),
    )


def _hours_kpis(screen: service.HoursScreen) -> tuple[Kpi, ...]:
    summary = screen.summary
    last = summary.last_month
    last_text = calculations.month_display(last) if last is not None else NONE
    planned = screen.planned_to_date
    planned_month = screen.planned_last_month
    return (
        Kpi(
            "HHT total registrado",
            summary.total_hours,
            f"Previsto: {_integer_text(planned.hours) if planned else NONE}",
            ValueKind.DECIMAL,
            digits=0,
            tone=Tone.INFO,
            status=f"Histograma de mão de obra até {last_text}",
        ),
        Kpi(
            "Meses com registro",
            summary.months_with_record,
            f"Esperado: {screen.expected_months}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status="Do início do projeto até o mês de referência",
        ),
        Kpi(
            "Efetivo médio (último mês)",
            summary.last_month_headcount if last is not None else NONE,
            f"Previsto: {planned_month.headcount if planned_month else NONE}",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status=last_text,
        ),
        Kpi(
            "Empresas com registro",
            summary.companies_with_record,
            f"Referência: de {screen.companies_expected} previstas",
            ValueKind.INTEGER,
            tone=Tone.INFO,
            status="Empresas que já lançaram HHT",
        ),
    )


def _integer_text(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _hours_table(screen: service.HoursScreen) -> Table:
    return Table(
        title="HHT por mês e empresa",
        columns=(
            Column("Mês", width=12),
            Column("Empresa", width=32),
            Column("Efetivo médio", ValueKind.INTEGER),
            Column("HHT", ValueKind.DECIMAL, digits=0),
            Column("Média horas / pessoa", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                line.month_text,
                line.company_name,
                line.headcount,
                line.hours,
                line.hours_per_person or None,
                project=line.project_label,
            )
            for line in screen.rows
        ),
    )


def _histogram_table(screen: service.HoursScreen, names: service.Names) -> Table:
    return Table(
        title="Histograma de mão de obra",
        columns=(
            Column("Mês", width=12),
            Column("HHT previsto", ValueKind.INTEGER),
            Column("HHT registrado", ValueKind.DECIMAL, digits=0),
            Column("Efetivo previsto", ValueKind.INTEGER),
            Column("Efetivo registrado", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                calculations.month_display(point.month),
                point.planned_hours,
                point.recorded_hours,
                point.planned_headcount,
                point.recorded_headcount,
                project=names.project(point.project_id),
            )
            for point in screen.histogram
        ),
    )


@dataclass(frozen=True)
class ProactiveData:
    """What the screen Inspeções e observações shows: the indicators and the four lists."""

    summary: ProactiveSummary
    closings: Sequence[service.ClosingRow]
    inspections: Sequence[service.InspectionRow]
    observations: Sequence[service.ObservationRow]
    talks: Sequence[service.TalkRow]
    show_observed: bool


def proactive_document(
    data: ProactiveData, *, scope: Scope, projects: Sequence[ProjectLike], today: date
) -> Document:
    """The document of the screen Inspeções e observações: indicators and the four lists."""
    return Document(
        title=PROACTIVE_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        kpis=_proactive_kpis(data.summary),
        tables=(
            _closing_table(data.closings),
            _inspection_table(data.inspections),
            _observation_table(data.observations, show_observed=data.show_observed),
            _talk_table(data.talks),
        ),
    )


def _proactive_kpis(summary: ProactiveSummary) -> tuple[Kpi, ...]:
    observations_low = (
        summary.observations_target is not None
        and summary.observations < summary.observations_target
    )
    deviations_low = (
        summary.deviations_target is not None and summary.deviations < summary.deviations_target
    )
    return (
        Kpi(
            "DDS realizados",
            summary.dds_rate if summary.dds_rate is not None else NONE,
            "Meta: 100%",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
            status=f"{summary.held_dds} de {summary.planned_dds} programados",
        ),
        Kpi(
            "Conformidade em inspeções",
            summary.conformity_rate if summary.conformity_rate is not None else NONE,
            "Esperado: 100%",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
            status=f"{summary.conforming_items} de {summary.inspected_items} itens",
        ),
        Kpi(
            "Observações comportamentais",
            summary.observations,
            _target_text(summary.observations_target),
            ValueKind.INTEGER,
            tone=Tone.WARN if observations_low else Tone.NEUTRAL,
            status="Abaixo da meta" if observations_low else "Na meta ou sem HHT de referência",
        ),
        Kpi(
            "Desvios (nível 5)",
            summary.deviations,
            _target_text(summary.deviations_target, prefix="Meta de relato"),
            ValueKind.INTEGER,
            tone=Tone.WARN if deviations_low else Tone.NEUTRAL,
            status="Atos e condições inseguras",
        ),
    )


def _target_text(target: int | None, *, prefix: str = "Meta") -> str:
    return f"{prefix}: {NONE}" if target is None else f"{prefix}: ≥ {target}"


def _closing_table(rows: Sequence[service.ClosingRow]) -> Table:
    return Table(
        title="Registros mensais",
        columns=(
            Column("Mês", width=12),
            Column("DDS realizados / programados", width=22),
            Column("Itens conformes / inspecionados", width=24),
            Column("Observações", ValueKind.INTEGER),
            Column("Desvios", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                line.month_text,
                f"{line.held_dds} / {line.planned_dds}",
                f"{line.conforming_items} / {line.inspected_items}",
                line.observations,
                line.deviations,
                project=line.project_label,
            )
            for line in rows
        ),
    )


def _inspection_table(rows: Sequence[service.InspectionRow]) -> Table:
    return Table(
        title="Inspeções de segurança",
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Área", width=24),
            Column("Empresa", width=24),
            Column("Responsável", width=24),
            Column("Itens", ValueKind.INTEGER),
            Column("Conformes", ValueKind.INTEGER),
            Column("Não conformes", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                line.inspected_on,
                line.area,
                line.company_name,
                line.responsible_name,
                len(line.items),
                line.conforming,
                _non_conforming_cell(line),
                project=line.project_label,
            )
            for line in rows
        ),
    )


def _non_conforming_cell(line: service.InspectionRow) -> Cell:
    missing = len(line.items) - line.conforming
    return Cell(missing, Tone.WARN if missing else None)


def _observation_table(rows: Sequence[service.ObservationRow], *, show_observed: bool) -> Table:
    columns = [
        Column("Data", ValueKind.DATE),
        Column("Área", width=24),
        Column("Tipo", width=20),
        Column("Descrição", width=50),
        Column("Empresa", width=24),
        Column("Responsável", width=24),
    ]
    if show_observed:
        columns.append(Column("Observado", width=24))
    columns.append(Column("Situação", width=12))
    return Table(
        title="Observações comportamentais",
        columns=tuple(columns),
        rows=tuple(_observation_row(line, show_observed=show_observed) for line in rows),
    )


def _observation_row(line: service.ObservationRow, *, show_observed: bool) -> Row:
    cells: list[Cell | str | date | None] = [
        line.observed_on,
        line.area,
        line.kind,
        line.description,
        line.company_name,
        line.responsible_name,
    ]
    if show_observed:
        cells.append(line.observed_name)
    cells.append(line.status)
    return row(*cells, project=line.project_label)


def _talk_table(rows: Sequence[service.TalkRow]) -> Table:
    return Table(
        title="DDS",
        columns=(
            Column("Data", ValueKind.DATE),
            Column("Tema", width=40),
            Column("Empresa", width=24),
            Column("Responsável", width=24),
            Column("Participantes", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                line.held_on,
                line.topic,
                line.company_name,
                line.responsible_name,
                line.participants,
                project=line.project_label,
            )
            for line in rows
        ),
    )
