"""Exports of the HSE screens: one ``Document`` each, the Excel and the printable version (D12).

What a screen shows is what leaves: the HHT screen exports its four indicators with their
reference, the HHT table and the labour histogram; the screen Inspeções e observações exports its
four indicators and the four lists (monthly closings, inspections, observations and DDS); the
screen Ocorrências exports its four indicators and the list, with the same columns the prototype
exported; the screen Análises de risco exports its four indicators and the study list. In the
Portfólio every table opens with ``Projeto`` (HU-016). The name of the person observed leaves
only for who may read it (Q35); the restricted data of an occurrence never leaves, because the
list does not carry it.

O painel (ISSUE-075) exporta os três blocos de indicadores do protótipo (mês, acumulado e
proativos, com o bloco no rótulo), as duas tabelas da pirâmide com os nomes dos níveis, a tabela
da evolução mensal com a TF e a TRIF de cada mês e as listas por área e por empresa. Todas as
tabelas do painel são agregadas do escopo (sem a coluna ``Projeto``, como o protótipo).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from src.core.export_document import (
    Cell,
    Chart,
    Column,
    Document,
    Kpi,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    format_value,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.hse import calculations, painel_service, service
from src.modulos.hse.calculations import HseIndicators, ProactiveSummary
from src.modulos.hse.painel_service import HsePanel

HOURS_TITLE = "Horas trabalhadas (HHT)"
PROACTIVE_TITLE = "Inspeções, observações e DDS"
OCCURRENCES_TITLE = "Ocorrências HSE"
ANALYSES_TITLE = "Análises de risco (APR/HAZOP)"
PANEL_TITLE = "Painel HSE"
HOURS_FILE = "hht-hse"
PROACTIVE_FILE = "inspecoes-hse"
OCCURRENCES_FILE = "ocorrencias-hse"
ANALYSES_FILE = "analises-risco-hse"
PANEL_FILE = "painel-hse"
PANEL_PYRAMID_TITLE = "Pirâmide de segurança"
PANEL_PYRAMID_MONTH_TITLE = "Pirâmide de segurança · mês"
PANEL_PYRAMID_ACCUMULATED_TITLE = "Pirâmide de segurança · acumulado"
PANEL_EVOLUTION_TITLE = "Evolução mensal de TF e TRIF"
PANEL_AREA_TITLE = "Ocorrências por área"
PANEL_COMPANY_TITLE = "Ocorrências por empresa"
NONE = "·"
WITHIN_DEADLINE = "no prazo"


def hours_document(
    screen: service.HoursScreen,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    names: service.Names,
    today: date,
    idioma: str = "pt",
) -> Document:
    """The document of the HHT screen: indicators, the HHT table and the labour histogram."""
    return Document(
        namespace="hse",
        idioma=idioma,
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
    data: ProactiveData,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """The document of the screen Inspeções e observações: indicators and the four lists."""
    return Document(
        namespace="hse",
        idioma=idioma,
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


def occurrences_document(
    screen: service.OccurrenceScreen,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """The document of the occurrence screen: its four indicators and the list, as it is shown."""
    return Document(
        namespace="hse",
        idioma=idioma,
        title=OCCURRENCES_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        kpis=_occurrence_kpis(screen),
        tables=(_occurrence_table(screen.rows),),
    )


def _occurrence_kpis(screen: service.OccurrenceScreen) -> tuple[Kpi, ...]:
    summary = screen.summary
    deadlines = screen.deadlines
    limits = (
        f"Limites: {deadlines.communication_hours} h, "
        f"{deadlines.investigation_hours} h e {deadlines.report_days} dias"
    )
    return (
        Kpi(
            "Ocorrências no projeto",
            summary.total,
            f"Referência: de {screen.universe} registradas",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status="Pelo filtro em tela",
        ),
        Kpi(
            "Em aberto",
            summary.open_count,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.open_count else Tone.OK,
            status="Não encerradas",
        ),
        Kpi(
            "Alto potencial (HiPo) em aberto",
            summary.hipo_open,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.hipo_open else Tone.OK,
            status="HiPo sem encerramento",
        ),
        Kpi(
            "Fora do prazo",
            summary.overdue,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.overdue else Tone.OK,
            status=f"Comunicação, investigação ou relatório · {limits}",
        ),
    )


def _occurrence_table(rows: Sequence[service.OccurrenceRow]) -> Table:
    return Table(
        title="Ocorrências",
        columns=(
            Column("Nº", width=18),
            Column("Data / hora", width=18),
            Column("Área", width=22),
            Column("Empresa", width=24),
            Column("Tipo / nível", width=26),
            Column("Potencial", width=22),
            Column("Situação", width=16),
            Column("Prazos", width=34),
        ),
        rows=tuple(
            row(
                line.code,
                line.moment_text,
                line.area,
                line.company_name,
                _type_text(line),
                _potential_text(line),
                line.situation,
                _deadlines_text(line),
                project=line.project_label,
            )
            for line in rows
        ),
    )


def _type_text(line: service.OccurrenceRow) -> str:
    if line.level is None:
        return line.kind
    return f"{line.kind} ({line.level_name})"


def _potential_text(line: service.OccurrenceRow) -> str:
    if line.environmental:
        return line.environmental_severity or NONE
    if line.band is None:
        return NONE
    return f"{line.band.name} (P{line.potential_p} x I{line.potential_i})"


def _deadlines_text(line: service.OccurrenceRow) -> str:
    badges: list[str] = []
    if line.communication_overdue:
        badges.append("Comunicação fora do prazo")
    if line.investigation_late == "fora":
        badges.append("Investigação fora do prazo")
    elif line.investigation_late == "vencido":
        badges.append("Investigação vencida")
    if line.report_required:
        if line.report_late == "fora":
            badges.append("Relatório final fora do prazo")
        elif line.report_late == "vencido":
            badges.append("Relatório final vencido")
    return "; ".join(badges) if badges else WITHIN_DEADLINE


def analyses_document(
    screen: service.AnalysisScreen,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """O documento da tela Análises de risco: os quatro indicadores e a lista de estudos."""
    return Document(
        namespace="hse",
        idioma=idioma,
        title=ANALYSES_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        kpis=_analysis_kpis(screen),
        tables=(_analysis_table(screen.rows),),
    )


def _analysis_kpis(screen: service.AnalysisScreen) -> tuple[Kpi, ...]:
    summary = screen.summary
    emitted = summary.open + summary.closed
    return (
        Kpi(
            "Estudos registrados",
            len(screen.rows),
            f"Referência: de {screen.universe} registrados",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status="Pelo filtro em tela",
        ),
        Kpi(
            "Recomendações abertas",
            summary.open,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.open else Tone.OK,
            status="Não fechadas",
        ),
        Kpi(
            "Recomendações atrasadas",
            summary.overdue,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.overdue else Tone.OK,
            status="Abertas com o prazo vencido",
        ),
        Kpi(
            "Recomendações fechadas",
            summary.closed_pct if summary.closed_pct is not None else NONE,
            "Esperado: 100%",
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
            status=f"{summary.closed} de {emitted} emitidas",
        ),
    )


def _analysis_table(rows: Sequence[service.AnalysisRow]) -> Table:
    return Table(
        title="Estudos",
        columns=(
            Column("Nº", width=18),
            Column("Tipo", width=10),
            Column("Área", width=22),
            Column("Título", width=40),
            Column("Data", ValueKind.DATE),
            Column("Participantes", ValueKind.INTEGER),
            Column("Recomendações", width=36),
        ),
        rows=tuple(
            row(
                line.code,
                line.kind,
                line.area,
                line.title,
                line.held_on,
                line.participants,
                _recommendations_text(line),
                project=line.project_label,
            )
            for line in rows
        ),
    )


def _recommendations_text(line: service.AnalysisRow) -> str:
    opened = f"{line.open_count} aberta{'' if line.open_count == 1 else 's'}"
    if line.overdue_count:
        opened += f" ({line.overdue_count} atrasada{'' if line.overdue_count == 1 else 's'})"
    closed = f"{line.closed_count} fechada{'' if line.closed_count == 1 else 's'}"
    return f"{opened}, {closed}"


def panel_document(
    panel: HsePanel,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """O painel como documento: os indicadores, as pirâmides, a evolução e as listas (D12).

    Os três blocos de indicadores do protótipo (mês, acumulado e proativos) viram KPIs com o
    bloco no rótulo; o vazio de origem (sem HHT) sai sem indicadores nem tabelas.
    """
    return Document(
        namespace="hse",
        idioma=idioma,
        title=PANEL_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=_panel_context(panel),
        kpis=_panel_kpis(panel, portfolio=scope.is_portfolio),
        charts=_panel_charts(panel),
        tables=_panel_tables(panel),
    )


def _panel_context(panel: HsePanel) -> tuple[tuple[str, str], ...]:
    """As linhas extras do cabeçalho: o período lido e a base das taxas, como a linha de período."""
    reference = ("Data de referência", _date_text(panel.reference_date))
    if panel.month is None or panel.window_start is None or panel.window_end is None:
        return (reference,)
    return (
        ("Mês selecionado", calculations.month_display(panel.month)),
        (
            "Acumulado",
            (
                f"{calculations.month_display(panel.window_start)}"
                f" a {calculations.month_display(panel.window_end)}"
            ),
        ),
        (
            "Base das taxas",
            f"{_integer_text(panel.base)} HHT ({calculations.rate_base_name(panel.base)})",
        ),
        ("Referência da pirâmide", panel.reference.name),
        reference,
    )


def _panel_kpis(panel: HsePanel, *, portfolio: bool) -> tuple[Kpi, ...]:
    """Os indicadores do protótipo, por bloco (mês, acumulado e proativos), no rótulo."""
    month = panel.month_indicators
    accumulated = panel.accumulated_indicators
    if month is None or accumulated is None:
        return ()
    return (
        *_reactive_kpis(month, block="No mês", footer="no mês"),
        *_reactive_kpis(accumulated, block="Acumulado", footer="no acumulado"),
        _days_kpi(panel, accumulated, portfolio=portfolio),
        _actions_kpi(accumulated),
        *_panel_proactive_kpis(panel, accumulated),
    )


def _reactive_kpis(indicators: HseIndicators, *, block: str, footer: str) -> tuple[Kpi, ...]:
    """Os quatro indicadores reativos de uma janela (TF, TRIF, TG e HiPo)."""
    return (
        Kpi(
            label=f"{block} · Taxa de frequência (TF)",
            value=indicators.tf,
            reference="Esperado: 0,00",
            kind=ValueKind.DECIMAL,
            digits=2,
            tone=Tone.ERROR if indicators.lti else Tone.OK,
            status=(
                _plural(indicators.lti, "acidente com afastamento", "acidentes com afastamento")
                + f" {footer}"
            ),
        ),
        Kpi(
            label=f"{block} · Lesões registráveis (TRIF)",
            value=indicators.trif,
            reference="Esperado: 0,00",
            kind=ValueKind.DECIMAL,
            digits=2,
            tone=Tone.WARN if indicators.registrable else Tone.OK,
            status=_plural(indicators.registrable, "lesão registrável", "lesões registráveis"),
        ),
        Kpi(
            label=f"{block} · Taxa de gravidade (TG)",
            value=indicators.tg,
            reference="Esperado: 0,0",
            kind=ValueKind.DECIMAL,
            digits=1,
            tone=Tone.INFO,
            status="dias perdidos e debitados x base / HHT",
        ),
        Kpi(
            label=f"{block} · Alto potencial (HiPo)",
            value=indicators.hipo,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=Tone.ERROR if indicators.hipo else Tone.OK,
            status=_plural(indicators.hipo, "ocorrência", "ocorrências") + f" {footer}",
        ),
    )


def _days_kpi(panel: HsePanel, indicators: HseIndicators, *, portfolio: bool) -> Kpi:
    """Dias sem afastamento: o valor do acumulado e o esperado desde o início do projeto."""
    expected = calculations.days_without_leave(None, panel.project_start, panel.reference_date)
    return Kpi(
        label="Acumulado · Dias sem afastamento",
        value=0 if indicators.days_without_leave is None else indicators.days_without_leave,
        reference=(
            f"Esperado: {_integer_text(expected)}" if expected is not None else "Esperado: ·"
        ),
        kind=ValueKind.INTEGER,
        tone=Tone.NEUTRAL,
        status=_days_footer(panel, portfolio=portfolio),
    )


def _days_footer(panel: HsePanel, *, portfolio: bool) -> str:
    if panel.last_lti is not None:
        return f"última LTI em {_date_text(panel.last_lti)}"
    if panel.project_start is not None:
        inicio = "da carteira" if portfolio else "do projeto"
        return f"desde o início {inicio} ({_date_text(panel.project_start)})"
    return "nenhum acidente com afastamento registrado"


def _actions_kpi(indicators: HseIndicators) -> Kpi:
    """Ações HSE no prazo contra a meta da tela (o protótipo tinha o limiar no código da página)."""
    pct = indicators.actions_on_time_pct
    return Kpi(
        label="Acumulado · Ações HSE no prazo",
        value=pct,
        reference=f"Meta: ≥ {painel_service.ACTIONS_ON_TIME_TARGET}%",
        kind=ValueKind.PERCENT,
        digits=1,
        tone=(
            Tone.OK
            if pct is not None and pct >= painel_service.ACTIONS_ON_TIME_TARGET
            else Tone.WARN
        ),
        status="ações vencidas com a conclusão até o prazo",
    )


def _panel_proactive_kpis(panel: HsePanel, indicators: HseIndicators) -> tuple[Kpi, ...]:
    """Os seis indicadores proativos do protótipo."""
    return (
        Kpi(
            label="Proativo · DDS realizados",
            value=indicators.dds_pct,
            reference="Meta: 100%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            label="Proativo · Conformidade em inspeções",
            value=indicators.conformity_pct,
            reference="Esperado: 100%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            label="Proativo · Observações / 10 mil HHT",
            value=indicators.observations_per_10k,
            reference=f"Meta: ≥ {_integer_text(panel.observations_target)}",
            kind=ValueKind.DECIMAL,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            label="Proativo · Relato de quase acidentes",
            value=indicators.almost_miss_report,
            reference=(
                "Referência: "
                + format_value(ValueKind.DECIMAL, panel.reference.almost_miss_ratio, 1)
            ),
            kind=ValueKind.DECIMAL,
            digits=1,
            tone=Tone.INFO,
            status="quase acidentes por lesão registrável",
        ),
        Kpi(
            label="Proativo · Recomendações fechadas (APR/HAZOP)",
            value=indicators.recommendations_pct,
            reference="Esperado: 100%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            label="Proativo · Incidentes ambientais",
            value=indicators.environmental,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=Tone.WARN if indicators.environmental else Tone.OK,
        ),
    )


def _panel_charts(panel: HsePanel) -> tuple[Chart, ...]:
    """Os dois visuais do painel (D11): a pirâmide dupla e a evolução mensal de TF e TRIF."""
    if panel.is_empty:
        return ()
    return (
        Chart(
            PANEL_PYRAMID_TITLE,
            "piramide-seguranca",
            painel_service.pyramid_chart(panel),
        ),
        Chart(
            PANEL_EVOLUTION_TITLE,
            "linhas-multiplas",
            painel_service.evolution_chart(panel),
        ),
    )


def _panel_tables(panel: HsePanel) -> tuple[Table, ...]:
    """As tabelas por trás dos visuais, como o protótipo as exportava (todas agregadas)."""
    if panel.is_empty:
        return ()
    return (
        _panel_pyramid_table(panel, PANEL_PYRAMID_MONTH_TITLE, month=True),
        _panel_pyramid_table(panel, PANEL_PYRAMID_ACCUMULATED_TITLE, month=False),
        _panel_evolution_table(panel),
        _panel_group_table(PANEL_AREA_TITLE, "Área", panel.by_area),
        _panel_group_table(PANEL_COMPANY_TITLE, "Empresa", panel.by_company),
    )


def _panel_pyramid_table(panel: HsePanel, title: str, *, month: bool) -> Table:
    indicators = panel.month_indicators if month else panel.accumulated_indicators
    levels = indicators.pyramid if indicators is not None else (0, 0, 0, 0, 0)
    return Table(
        title=title,
        columns=(Column("Nível", width=24), Column("Ocorrências", ValueKind.INTEGER)),
        rows=tuple(
            row(f"{position}. {calculations.pyramid_level_name(position)}", value)
            for position, value in enumerate(levels, start=1)
        ),
        per_project=False,
    )


def _panel_evolution_table(panel: HsePanel) -> Table:
    return Table(
        title=PANEL_EVOLUTION_TITLE,
        columns=(
            Column("Mês", width=12),
            Column("TF (com afastamento)", ValueKind.DECIMAL, digits=2),
            Column("TRIF (registráveis)", ValueKind.DECIMAL, digits=2),
        ),
        rows=tuple(
            row(calculations.month_display(point.month), point.tf, point.trif)
            for point in panel.evolution
        ),
        per_project=False,
    )


def _panel_group_table(
    title: str, header: str, lines: Sequence[painel_service.HseGroupLine]
) -> Table:
    return Table(
        title=title,
        columns=(Column(header, width=40), Column("Ocorrências", ValueKind.INTEGER)),
        rows=tuple(row(line.name, line.total) for line in lines),
        per_project=False,
    )


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _date_text(value: date) -> str:
    return value.strftime("%d/%m/%Y")
