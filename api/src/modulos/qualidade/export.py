"""The export of the Quality screens: the RNC list (ISSUE-068), the ITP list (ISSUE-069) and the
panel (ISSUE-071).

What the screen shows is what leaves. In the RNC list: the five KPIs of the prototype with
their reference, the line of the filters in force and the table of the reports with the same
columns the prototype exported. In Inspeções e ITP: the five KPIs, the table of the plans
(points by type, inspections and approval, the client) and the table of the inspections. In
the panel: the five KPIs, the four visuals of the screen (the Excel carries the numbers behind
each one as a table) and the treatment agenda and the performance by company. In the Portfólio
the tables open with ``Projeto`` (HU-016), except the ones aggregated by company or by group.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.core.export_document import (
    Cell,
    Chart,
    Column,
    Document,
    Kpi,
    Paper,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    project_label,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.qualidade.painel_service import QualityGroupLine, QualityPanel
from src.modulos.qualidade.service import (
    AuditLine,
    AuditListing,
    AuditSummary,
    InspectionLine,
    InspectionListing,
    InspectionSummary,
    ItpLine,
    ItpListing,
    RncLine,
    RncListing,
    RncSummary,
)
from src.modulos.qualidade.validation import AuditFilters, InspectionFilters, RncFilters

TITLE = "Não conformidades (RNC)"
TABLE_TITLE = "Relatórios de não conformidade"
NOT_ASSESSED = "·"

SITUATION_TONES = {
    "Aberta": Tone.NEUTRAL,
    "Em análise de causa": Tone.WARN,
    "Ação corretiva": Tone.INFO,
    "Verificação de eficácia": Tone.INFO,
    "Encerrada": Tone.OK,
    "Cancelada": Tone.NEUTRAL,
}

COLUMNS: tuple[Column, ...] = (
    Column("Nº", width=22),
    Column("Data", ValueKind.DATE, width=12),
    Column("Não conformidade", width=52),
    Column("Origem", width=22),
    Column("Disciplina", width=16),
    Column("Empresa", width=22),
    Column("Severidade", width=12),
    Column("Situação", width=22),
    Column("Próxima etapa", width=30),
    Column("Prazo", ValueKind.DATE, width=12),
    Column("Ações na Central", width=16),
    Column("Disposição", width=16),
    Column("Custo", ValueKind.MONEY, width=16),
)


def build_document(
    *,
    listing: RncListing,
    filters: RncFilters,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    verification_days: int,
) -> Document:
    """The document of the list for the filters in force: the KPIs and the table."""
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", filters_text(filters, listing)),
            ("RNC no filtro", str(listing.total)),
        ),
        kpis=_kpis(listing.summary, verification_days=verification_days),
        tables=(_table(listing),),
        paper=Paper.A3,
    )


def filters_text(filters: RncFilters, listing: RncListing) -> str:
    """The filters in force as one line, the way the export header writes them."""
    parts: list[str] = []
    if filters.search:
        parts.append(f"busca «{filters.search}»")
    if filters.situation == "ativas":
        parts.append("em aberto")
    elif filters.situation == "vencidas":
        parts.append("vencidas")
    elif filters.situation != "todas":
        parts.append(filters.situation)
    if filters.severity:
        parts.append(filters.severity)
    if filters.discipline:
        parts.append(filters.discipline)
    if filters.origin:
        parts.append(filters.origin)
    if filters.company_id is not None:
        names = {item.id: item.name for item in listing.companies}
        parts.append(names.get(filters.company_id, ""))
    return " · ".join(part for part in parts if part) or "Todas"


def _kpis(summary: RncSummary, *, verification_days: int) -> tuple[Kpi, ...]:
    open_tone = Tone.ERROR if summary.active else Tone.OK
    overdue_tone = Tone.ERROR if summary.overdue else Tone.OK
    cost_tone = Tone.ERROR if summary.cost_cents else Tone.OK
    average = (
        f"tempo médio de {summary.average_days} dias"
        if summary.average_days is not None
        else "sem encerramento"
    )
    return (
        Kpi(
            label="RNC em aberto",
            value=summary.active,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=open_tone,
            status=f"{summary.critical} crítica(s)",
        ),
        Kpi(
            label="Prazo de tratamento vencido",
            value=summary.overdue,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=overdue_tone,
            status="antes da verificação de eficácia",
        ),
        Kpi(
            label="Em verificação de eficácia",
            value=summary.in_verification,
            reference=f"Limite: {verification_days} dias",
            kind=ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{summary.verification_overdue} vencida(s)",
        ),
        Kpi(
            label="Encerradas",
            value=summary.closed,
            reference=f"de {summary.registered} registradas",
            kind=ValueKind.INTEGER,
            tone=Tone.OK,
            status=average,
        ),
        Kpi(
            label="Custo da não qualidade",
            value=summary.cost_cents,
            reference="Esperado: R$ 0,00",
            kind=ValueKind.MONEY,
            tone=cost_tone,
            status="retrabalho, reparo, ensaios e perdas",
        ),
    )


def _table(listing: RncListing) -> Table:
    return Table(
        title=TABLE_TITLE,
        columns=COLUMNS,
        rows=tuple(_row(line) for line in listing.lines),
    )


def _row(line: RncLine) -> Row:
    return row(
        line.code,
        line.rnc_date,
        line.description,
        line.origin + (f" {line.origin_ref}" if line.origin_ref else ""),
        line.discipline,
        line.company_name,
        Cell(line.severity),
        Cell(line.situation, SITUATION_TONES.get(line.situation)),
        line.next_step or NOT_ASSESSED,
        line.deadline,
        f"{line.actions.open} de {line.actions.total}",
        line.disposition or NOT_ASSESSED,
        line.cost_cents,
    )


# ── Inspeções e ITP (ISSUE-069) ──────────────────────────────────────────────────────────────

INSPECOES_TITLE = "Inspeções e ITP"
ITP_TABLE_TITLE = "Planos de inspeção e testes (ITP)"
INSPECTION_TABLE_TITLE = "Registros de inspeção"

RESULT_TONES = {
    "Aprovado": Tone.OK,
    "Aprovado com ressalva": Tone.WARN,
    "Reprovado": Tone.ERROR,
}

ITP_COLUMNS: tuple[Column, ...] = (
    Column("ITP", width=24),
    Column("Título", width=44),
    Column("Disciplina", width=16),
    Column("Empresa", width=22),
    Column("Pontos", ValueKind.INTEGER, width=10),
    Column("H · W · R", width=12),
    Column("Inspeções", ValueKind.INTEGER, width=12),
    Column("Aprovação", ValueKind.PERCENT, digits=1, width=12),
    Column("Cliente", width=12),
)

INSPECTION_COLUMNS: tuple[Column, ...] = (
    Column("Nº", width=22),
    Column("Data", ValueKind.DATE, width=12),
    Column("Ponto", width=44),
    Column("ITP", width=22),
    Column("Tipo", width=8),
    Column("Inspetor", width=22),
    Column("Resultado", width=22),
    Column("Observação", width=44),
    Column("RNC", width=24),
)


def build_inspecoes_document(
    *,
    itps: ItpListing,
    inspections: InspectionListing,
    summary: InspectionSummary,
    filters: InspectionFilters,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    meta_pct: Decimal,
) -> Document:
    """The document of Inspeções e ITP: the KPIs, the plans and the inspections of the filter."""
    return Document(
        title=INSPECOES_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", inspecoes_filters_text(filters, itps)),
            ("Registros no filtro", str(inspections.total)),
        ),
        kpis=_inspecoes_kpis(summary, meta_pct=meta_pct),
        tables=(_itp_table(itps), _inspection_table(inspections)),
        paper=Paper.A3,
    )


def inspecoes_filters_text(filters: InspectionFilters, itps: ItpListing) -> str:
    """The filters in force as one line, the way the export header writes them."""
    parts: list[str] = []
    if filters.search:
        parts.append(f"busca «{filters.search}»")
    if filters.itp_id is not None:
        code = next((line.code for line in itps.lines if line.id == filters.itp_id), "")
        parts.append(code or "ITP")
    if filters.result:
        parts.append(filters.result)
    if filters.point_type:
        parts.append(f"ponto {filters.point_type}")
    return " · ".join(parts) or "Todas"


def _inspecoes_kpis(summary: InspectionSummary, *, meta_pct: Decimal) -> tuple[Kpi, ...]:
    pending = summary.itps - summary.itps_approved
    approval_tone = (
        Tone.OK
        if summary.approval_pct is not None and summary.approval_pct >= meta_pct
        else Tone.WARN
    )
    return (
        Kpi(
            label="Inspeções registradas",
            value=summary.registered,
            reference=f"Previsto: {summary.points} pontos",
            kind=ValueKind.INTEGER,
            tone=Tone.INFO,
            status=f"{summary.with_remark} com ressalva",
        ),
        Kpi(
            label="Aprovação nas inspeções",
            value=summary.approval_pct,
            reference=f"Meta: {meta_pct:.0f}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=approval_tone,
            status="ressalva conta como aprovada",
        ),
        Kpi(
            label="Reprovadas",
            value=summary.rejected,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=Tone.ERROR if summary.rejected else Tone.OK,
            status=f"{summary.rejected_open_rnc} RNC em aberto",
        ),
        Kpi(
            label="ITPs aprovados pelo cliente",
            value=summary.itps_approved,
            reference=f"de {summary.itps}",
            kind=ValueKind.INTEGER,
            tone=Tone.WARN if pending else Tone.OK,
            status="aguardando aprovação" if pending else "todos aprovados",
        ),
        Kpi(
            label="Pontos já inspecionados",
            value=summary.covered_points,
            reference=f"de {summary.points}",
            kind=ValueKind.INTEGER,
            tone=Tone.INFO,
            status="ao menos um registro no ponto",
        ),
    )


def _itp_table(itps: ItpListing) -> Table:
    return Table(
        title=ITP_TABLE_TITLE,
        columns=ITP_COLUMNS,
        rows=tuple(_itp_row(line) for line in itps.lines),
    )


def _itp_row(line: ItpLine) -> Row:
    counts = line.point_type_counts
    return row(
        f"{line.code} rev {line.revision}",
        line.title,
        line.discipline,
        line.company_name,
        line.total_points,
        f"H {counts['H']} · W {counts['W']} · R {counts['R']}",
        line.inspections,
        line.approval_pct,
        Cell(
            "Aprovado" if line.approved_by_client else "Pendente",
            Tone.OK if line.approved_by_client else Tone.WARN,
        ),
        project=line.project_code,
    )


def _inspection_table(inspections: InspectionListing) -> Table:
    return Table(
        title=INSPECTION_TABLE_TITLE,
        columns=INSPECTION_COLUMNS,
        rows=tuple(_inspection_row(line) for line in inspections.lines),
    )


def _inspection_row(line: InspectionLine) -> Row:
    itp = line.itp_code or line.itp_title
    rnc = line.rnc_code + (f" · {line.rnc_situation}" if line.rnc_code else "")
    return row(
        line.code,
        line.inspection_date,
        line.point,
        itp,
        line.point_type,
        line.inspector_name,
        Cell(line.result, RESULT_TONES.get(line.result)),
        line.observation,
        rnc,
        project=line.project_code,
    )


# ── Auditorias (ISSUE-070) ───────────────────────────────────────────────────────────────────

AUDITORIAS_TITLE = "Auditorias"
AUDIT_TABLE_TITLE = "Programa de auditorias"

AUDIT_SITUATION_TONES = {
    "Planejada": Tone.INFO,
    "Realizada": Tone.OK,
}

AUDIT_COLUMNS: tuple[Column, ...] = (
    Column("Nº", width=22),
    Column("Data", ValueKind.DATE, width=12),
    Column("Escopo", width=52),
    Column("Auditor líder", width=22),
    Column("Situação", width=14),
    Column("Conformidade", ValueKind.PERCENT, digits=1, width=14),
    Column("Resultado", width=28),
)


def build_auditorias_document(
    *,
    listing: AuditListing,
    filters: AuditFilters,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    meta_pct: Decimal,
) -> Document:
    """The document of the programme: the five KPIs and the table of the audits of the filter."""
    return Document(
        title=AUDITORIAS_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", auditorias_filters_text(filters)),
            ("Auditorias no filtro", str(listing.total)),
        ),
        kpis=_auditorias_kpis(listing.summary, meta_pct=meta_pct),
        tables=(_audit_table(listing),),
        paper=Paper.A3,
    )


def auditorias_filters_text(filters: AuditFilters) -> str:
    """The filters in force as one line, the way the export header writes them."""
    parts: list[str] = []
    if filters.search:
        parts.append(f"busca «{filters.search}»")
    if filters.situation:
        parts.append(filters.situation)
    if filters.audit_type:
        parts.append(filters.audit_type)
    return " · ".join(parts) or "Todas"


def _auditorias_kpis(summary: AuditSummary, *, meta_pct: Decimal) -> tuple[Kpi, ...]:
    next_audit = summary.next_audit
    conformity_tone = (
        Tone.OK if summary.conformity is not None and summary.conformity >= meta_pct else Tone.WARN
    )
    open_nc = summary.open_nc
    return (
        Kpi(
            label="Aderência ao programa",
            value=summary.adherence,
            reference="Meta: 100%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=Tone.WARN if summary.overdue else Tone.OK,
            status=f"{summary.done} de {summary.due} previstas até hoje",
        ),
        Kpi(
            label="Auditorias atrasadas",
            value=summary.overdue,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=Tone.ERROR if summary.overdue else Tone.OK,
            status="data planejada vencida sem resultado",
        ),
        Kpi(
            label="Conformidade nas auditorias",
            value=summary.conformity,
            reference=f"Meta: {meta_pct:.0f}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=conformity_tone,
            status=f"{summary.conforming_items} de {summary.verified_items} itens",
        ),
        Kpi(
            label="Não conformidades de auditoria",
            value=summary.nc,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=Tone.WARN if open_nc else Tone.OK,
            status=f"{open_nc} RNC em aberto" if open_nc == 1 else f"{open_nc} RNCs em aberto",
        ),
        Kpi(
            label="Próxima auditoria",
            value=next_audit.audit_date if next_audit is not None else None,
            reference=(
                f"Linha de base: {next_audit.baseline_date}" if next_audit is not None else "·"
            ),
            kind=ValueKind.DATE,
            tone=Tone.INFO,
            status=(
                f"{next_audit.code} · {next_audit.auditee_name}"
                if next_audit is not None
                else "nenhuma planejada"
            ),
        ),
    )


def _audit_table(listing: AuditListing) -> Table:
    return Table(
        title=AUDIT_TABLE_TITLE,
        columns=AUDIT_COLUMNS,
        rows=tuple(_audit_row(line) for line in listing.lines),
    )


def _audit_row(line: AuditLine) -> Row:
    counts = line.finding_counts
    result = (
        f"NC {counts.get('Não conformidade', 0)}, "
        f"Obs. {counts.get('Observação', 0)}, "
        f"OM {counts.get('Oportunidade de melhoria', 0)}"
        if line.situation == "Realizada"
        else NOT_ASSESSED
    )
    return row(
        line.code,
        line.performed_on or line.audit_date,
        f"{line.scope} ({line.audit_type}, {line.auditee_name})",
        line.lead_auditor_name,
        Cell("Atrasada" if line.overdue else line.situation, _audit_situation_tone(line)),
        line.conformity_pct,
        result,
        project=line.project_code,
    )


def _audit_situation_tone(line: AuditLine) -> Tone:
    if line.overdue:
        return Tone.ERROR
    return AUDIT_SITUATION_TONES.get(line.situation, Tone.NEUTRAL)


# ── Painel da qualidade (ISSUE-071) ──────────────────────────────────────────────────────────

PANEL_TITLE = "Painel da qualidade"
PANEL_MONTH_CHART_TITLE = "RNC por mês"
PANEL_APPROVAL_CHART_TITLE = "Aprovação em inspeções"
PANEL_DISCIPLINE_CHART_TITLE = "Pareto de RNC por disciplina"
PANEL_ORIGIN_CHART_TITLE = "RNC por origem"
PANEL_MONTH_TABLE_TITLE = "RNC por mês"
PANEL_APPROVAL_TABLE_TITLE = "Aprovação em inspeções por mês"
PANEL_DISCIPLINE_TABLE_TITLE = "RNC por disciplina"
PANEL_ORIGIN_TABLE_TITLE = "RNC por origem"
PANEL_AGENDA_TITLE = "Pauta de tratamento"
PANEL_COMPANY_TITLE = "Desempenho por empresa"

MONTH_SHORT_NAMES = (
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)

SEVERITY_TONES = {
    "Crítica": Tone.ERROR,
    "Maior": Tone.WARN,
    "Menor": Tone.INFO,
}

PANEL_MONTH_COLUMNS: tuple[Column, ...] = (
    Column("Mês", width=14),
    Column("Abertas", ValueKind.INTEGER, width=12),
    Column("Encerradas", ValueKind.INTEGER, width=12),
    Column("Em aberto", ValueKind.INTEGER, width=12),
)

PANEL_APPROVAL_COLUMNS: tuple[Column, ...] = (
    Column("Mês", width=14),
    Column("Inspeções", ValueKind.INTEGER, width=12),
    Column("Aprovação", ValueKind.PERCENT, digits=1, width=14),
)

PANEL_GROUP_COLUMNS: tuple[Column, ...] = (
    Column("Grupo", width=32),
    Column("RNC", ValueKind.INTEGER, width=10),
    Column("Percentual", ValueKind.PERCENT, digits=1, width=14),
    Column("Acumulado", ValueKind.PERCENT, digits=1, width=14),
)

PANEL_AGENDA_COLUMNS: tuple[Column, ...] = (
    Column("Nº", width=22),
    Column("Não conformidade", width=52),
    Column("Disciplina", width=16),
    Column("Empresa", width=22),
    Column("Severidade", width=12),
    Column("Situação", width=22),
    Column("Atraso (dias)", ValueKind.INTEGER, width=12),
    Column("Motivo", width=52),
)

PANEL_COMPANY_COLUMNS: tuple[Column, ...] = (
    Column("Empresa", width=32),
    Column("Inspeções", ValueKind.INTEGER, width=12),
    Column("Reprovadas", ValueKind.INTEGER, width=12),
    Column("Aprovação", ValueKind.PERCENT, digits=1, width=12),
    Column("RNC", ValueKind.INTEGER, width=10),
    Column("Custo da não qualidade", ValueKind.MONEY, width=22),
)


def build_panel_document(
    panel: QualityPanel,
    *,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """O painel como documento: os indicadores, os gráficos e as tabelas por trás deles (D12)."""
    labels = {project.id: project_label(project) for project in projects}
    return Document(
        title=PANEL_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Data de referência", panel.reference_date.strftime("%d/%m/%Y")),
            ("RNC no escopo", str(panel.registered)),
        ),
        kpis=_panel_kpis(panel),
        charts=panel_charts(panel),
        tables=(
            _panel_month_table(panel),
            _panel_approval_table(panel),
            _panel_group_table(PANEL_DISCIPLINE_TABLE_TITLE, panel.by_discipline),
            _panel_group_table(PANEL_ORIGIN_TABLE_TITLE, panel.by_origin),
            _panel_agenda_table(panel, labels),
            _panel_company_table(panel),
        ),
    )


def panel_charts(panel: QualityPanel) -> tuple[Chart, ...]:
    """Os quatro visuais do painel, na ordem da tela."""
    return (
        Chart(PANEL_MONTH_CHART_TITLE, "curva-s-barra-linha", panel_month_chart(panel)),
        Chart(PANEL_APPROVAL_CHART_TITLE, "linhas-multiplas", panel_approval_chart(panel)),
        Chart(PANEL_DISCIPLINE_CHART_TITLE, "pareto", panel_discipline_chart(panel)),
        Chart(PANEL_ORIGIN_CHART_TITLE, "comparativo-barras", panel_origin_chart(panel)),
    )


def panel_month_chart(panel: QualityPanel) -> dict[str, object]:
    """O ``data-dados`` do RNC por mês (curva-s-barra-linha): a quantidade de cada mês."""
    return {
        "titulo": PANEL_MONTH_CHART_TITLE,
        "modo": "periodo",
        "formato": "numero",
        "unidade": "",
        "casas": 0,
        "series": [
            {"id": "abertas", "rotulo": "Abertas", "papel": "atencao"},
            {"id": "encerradas", "rotulo": "Encerradas", "papel": "realizado"},
        ],
        "periodos": [
            {
                "ano": int(point.month[:4]),
                "mes": int(point.month[5:]),
                "valores": {"abertas": point.opened, "encerradas": point.closed},
            }
            for point in panel.series
        ],
    }


def panel_approval_chart(panel: QualityPanel) -> dict[str, object]:
    """O ``data-dados`` da aprovação em inspeções (linhas-multiplas), com a meta em tracejado."""
    return {
        "titulo": PANEL_APPROVAL_CHART_TITLE,
        "base_zero": True,
        "eixo": {"min": 0, "max": 100},
        "casas": 1,
        "unidade": "%",
        "suavizar": False,
        "series": [{"id": "aprovacao", "rotulo": "Aprovação", "papel": "realizado"}],
        "referencias": [
            {
                "valor": float(panel.indicators.inspection_approval_target_pct),
                "rotulo": "Meta",
                "papel": "linha-base",
            }
        ],
        "periodos": [
            {
                "ano": int(point.month[:4]),
                "mes": int(point.month[5:]),
                "valores": {
                    "aprovacao": None if point.approval_pct is None else float(point.approval_pct)
                },
            }
            for point in panel.series
        ],
    }


def panel_discipline_chart(panel: QualityPanel) -> dict[str, object]:
    """O ``data-dados`` do Pareto de RNC por disciplina (pareto): a quantidade de cada grupo."""
    return {
        "titulo": PANEL_DISCIPLINE_CHART_TITLE,
        "eixo_esquerdo": "RNC",
        "eixo_direito": "% acumulado",
        "status": [{"id": "rnc", "rotulo": "RNC", "papel": "erro"}],
        "categorias": [
            {"rotulo": line.name, "valores": {"rnc": line.total}} for line in panel.by_discipline
        ],
    }


def panel_origin_chart(panel: QualityPanel) -> dict[str, object]:
    """O ``data-dados`` do RNC por origem (comparativo-barras): uma barra com um trecho por origem."""
    categories = [
        {"id": f"origem-{position}", "rotulo": line.name}
        for position, line in enumerate(panel.by_origin, start=1)
    ]
    values = {
        f"origem-{position}": line.total for position, line in enumerate(panel.by_origin, start=1)
    }
    return {
        "titulo": PANEL_ORIGIN_CHART_TITLE,
        "paineis": [
            {
                "titulo": PANEL_ORIGIN_CHART_TITLE,
                "categorias": categories,
                "linhas": [{"rotulo": "RNC", "valores": values}],
            }
        ]
        if categories
        else [],
    }


def _panel_kpis(panel: QualityPanel) -> tuple[Kpi, ...]:
    indicators = panel.indicators
    open_tone = (
        Tone.ERROR
        if indicators.overdue_rncs or indicators.critical_open_rncs
        else Tone.WARN
        if indicators.open_rncs
        else Tone.OK
    )
    approval_tone = (
        Tone.OK
        if indicators.inspection_approval_pct is not None
        and indicators.inspection_approval_pct >= indicators.inspection_approval_target_pct
        else Tone.WARN
    )
    conformity_tone = (
        Tone.OK
        if indicators.audit_conformity_pct is not None
        and indicators.audit_conformity_pct >= indicators.audit_conformity_target_pct
        else Tone.WARN
    )
    effectiveness = (
        ""
        if indicators.first_time_effectiveness_pct is None
        else f" · {_percent_text(indicators.first_time_effectiveness_pct)}% eficazes na 1ª verificação"
    )
    return (
        Kpi(
            label="RNC em aberto",
            value=indicators.open_rncs,
            reference="Esperado: 0",
            kind=ValueKind.INTEGER,
            tone=open_tone,
            status=(
                f"{_plural(indicators.overdue_rncs, 'vencida', 'vencidas')} · "
                f"{_plural(indicators.critical_open_rncs, 'crítica', 'críticas')}"
            ),
        ),
        Kpi(
            label="Tempo médio de tratamento",
            value=indicators.average_treatment_days,
            reference=f"Limite: {panel.treatment_limit}",
            kind=ValueKind.INTEGER,
            tone=Tone.INFO,
            status=(
                _plural(indicators.closed_rncs, "RNC encerrada", "RNCs encerradas") + effectiveness
                if indicators.closed_rncs
                else "sem encerramento"
            ),
        ),
        Kpi(
            label="Aprovação em inspeções",
            value=indicators.inspection_approval_pct,
            reference=f"Meta: {indicators.inspection_approval_target_pct:.0f}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=approval_tone,
            status=(
                f"{_plural(indicators.rejected_inspections, 'reprovada', 'reprovadas')} "
                f"em {indicators.inspections} · ressalva conta como aprovada"
            ),
        ),
        Kpi(
            label="Conformidade em auditorias",
            value=indicators.audit_conformity_pct,
            reference=f"Meta: {indicators.audit_conformity_target_pct:.0f}%",
            kind=ValueKind.PERCENT,
            digits=1,
            tone=conformity_tone,
            status=(
                f"programa {_percent_text(indicators.audit_program_adherence_pct)} cumprido · "
                f"{_plural(indicators.overdue_audits, 'atrasada', 'atrasadas')}"
            ),
        ),
        Kpi(
            label="Custo da não qualidade",
            value=indicators.non_quality_cost_cents,
            reference="Esperado: R$ 0,00",
            kind=ValueKind.MONEY,
            tone=Tone.ERROR if indicators.non_quality_cost_cents else Tone.OK,
            status="soma das RNC (retrabalho, reparo, ensaios e perdas)",
        ),
    )


def _panel_month_table(panel: QualityPanel) -> Table:
    return Table(
        title=PANEL_MONTH_TABLE_TITLE,
        columns=PANEL_MONTH_COLUMNS,
        rows=tuple(
            row(_month_label(point.month), point.opened, point.closed, point.open)
            for point in panel.series
        ),
        per_project=False,
    )


def _panel_approval_table(panel: QualityPanel) -> Table:
    return Table(
        title=PANEL_APPROVAL_TABLE_TITLE,
        columns=PANEL_APPROVAL_COLUMNS,
        rows=tuple(
            row(_month_label(point.month), point.inspections, point.approval_pct)
            for point in panel.series
        ),
        per_project=False,
    )


def _panel_group_table(title: str, lines: Sequence[QualityGroupLine]) -> Table:
    return Table(
        title=title,
        columns=PANEL_GROUP_COLUMNS,
        rows=tuple(row(line.name, line.total, line.pct, line.accumulated_pct) for line in lines),
        per_project=False,
    )


def _panel_agenda_table(panel: QualityPanel, labels: Mapping[int, str]) -> Table:
    return Table(
        title=PANEL_AGENDA_TITLE,
        columns=PANEL_AGENDA_COLUMNS,
        rows=tuple(
            row(
                entry.line.code,
                entry.line.description,
                entry.line.discipline,
                entry.line.company_name,
                Cell(entry.line.severity, SEVERITY_TONES.get(entry.line.severity)),
                entry.line.situation,
                entry.line.days_overdue,
                " · ".join(entry.reasons),
                project=labels.get(entry.line.project_id),
            )
            for entry in panel.agenda
        ),
    )


def _panel_company_table(panel: QualityPanel) -> Table:
    return Table(
        title=PANEL_COMPANY_TITLE,
        columns=PANEL_COMPANY_COLUMNS,
        rows=tuple(
            row(
                line.company_name,
                line.inspections,
                line.rejected,
                line.approval_pct,
                line.rncs,
                line.cost_cents,
            )
            for line in panel.by_company
        ),
        per_project=False,
    )


def _percent_text(value: Decimal | None) -> str:
    """A share as the prototype writes the status: rounded to the unit (``67``)."""
    if value is None:
        return "·"
    return str(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _month_label(month: str) -> str:
    """``2026-09`` as the prototype printed it: ``set/26``."""
    year, number = int(month[:4]), int(month[5:])
    return f"{MONTH_SHORT_NAMES[number - 1]}/{year % 100:02d}"
