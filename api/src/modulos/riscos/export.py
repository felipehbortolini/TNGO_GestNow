"""The export of the screens of Riscos: one ``Document``, the Excel and the printable version (D12).

What the screen shows is what leaves. The register prints the five KPIs with their reference, the
line of active filters and the table of the risks of the filter, with the same content the
prototype exported (``Nº``, ``Risco`` with the category, ``Natureza``, ``Dono``, the two
assessments written as ``12 (P3 x I4, Alto)``, ``Estratégia``, the actions, ``Próx. revisão`` and
``Situação``). The ficha of the risk (ISSUE-065) prints the situation as KPIs, the identification,
the response plan, the linked actions, the reviews and the history, as the prototype exported it.
In the Portfólio the table opens with ``Projeto`` (HU-016). The register table is wide, so the
printable version asks for A3 landscape.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

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
    format_value,
    project_label,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.riscos import calculations, presentation
from src.modulos.riscos.ficha_service import ActionView, ReviewLine, RiskSheet
from src.modulos.riscos.panel_service import (
    AgendaEntry,
    BandStyle,
    MatrixCell,
    Movement,
    RiskMatrix,
    RiskPanel,
)
from src.modulos.riscos.service import AssessmentView, BandCount, RiskLine, RiskListing
from src.modulos.riscos.validation import INHERENT, RiskFilters

TITLE = "Registro de riscos"
TABLE_TITLE = "Riscos"
SHEET_TITLE = "Ficha do risco"
NOT_ASSESSED = "não avaliado"
NEVER_REVIEWED = "sem data"
OVERDUE_SUFFIX = " (vencida)"
FIELD_COLUMNS = (Column("Campo", width=32), Column("Valor", width=90))

SITUATION_TONES = {
    "Identificado": Tone.NEUTRAL,
    "Em análise": Tone.WARN,
    "Em tratamento": Tone.INFO,
    "Monitorado": Tone.OK,
    "Materializado": Tone.ERROR,
    "Encerrado": Tone.NEUTRAL,
}


def build_document(
    *,
    listing: RiskListing,
    filters: RiskFilters,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the screen for the filters in force: KPIs, filters and the table."""
    labels = project_labels(listing)
    bands = listing.parameters.scale.bands
    owners = dict(listing.owners)
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            (
                "Filtros",
                presentation.summary(
                    filters,
                    bands=bands,
                    owners=owners,
                    review_alert_days=listing.parameters.review_alert_days,
                ),
            ),
            ("Avaliação exibida", "Inerente" if filters.assessment == INHERENT else "Residual"),
            ("Riscos no filtro", str(listing.total)),
        ),
        kpis=_kpis(listing),
        tables=(_table(listing.lines, labels),),
        paper=Paper.A3,
    )


def project_labels(listing: RiskListing) -> dict[int, str]:
    """``TN-001 · Nome do projeto`` by project id, for the column Projeto."""
    return {item.id: f"{item.code} · {item.name}" for item in listing.projects}


def assessment_text(view: AssessmentView | None) -> str:
    """The assessment as the prototype exported it: ``12 (P3 x I4, Alto)``."""
    if view is None:
        return NOT_ASSESSED
    return f"{view.score} (P{view.probability} x I{view.impact}, {view.severity.name})"


def _band_kpi(count: BandCount, assessment: str, *, heavy: Tone) -> Kpi:
    shown = "inerente" if assessment == INHERENT else "residual"
    detail = (
        f"{count.threats} ameaça(s)"
        + (f" · {count.opportunities} oportunidade(s)" if count.opportunities else "")
        if count.total
        else "nenhum na faixa"
    )
    return Kpi(
        f"{count.band.name}s ({shown})",
        count.total,
        f"Meta: {count.goal}",
        ValueKind.INTEGER,
        tone=heavy if count.total else Tone.OK,
        status=detail,
    )


def _kpis(listing: RiskListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    kpis = [_band_kpi(summary.top, summary.assessment, heavy=Tone.ERROR)]
    if summary.second is not None:
        kpis.append(_band_kpi(summary.second, summary.assessment, heavy=Tone.WARN))
    kpis.extend(
        (
            Kpi(
                "Em tratamento",
                summary.in_treatment,
                f"Esperado: {summary.expected_in_treatment}",
                ValueKind.INTEGER,
                tone=Tone.INFO,
                status="plano aprovado e ações em curso",
            ),
            Kpi(
                "Revisão vencida",
                len(summary.overdue),
                "Esperado: 0",
                ValueKind.INTEGER,
                tone=Tone.ERROR if summary.overdue else Tone.OK,
                status="próxima revisão anterior a hoje",
            ),
            Kpi(
                "Ativos",
                summary.active,
                f"Referência: de {summary.registered} registrados",
                ValueKind.INTEGER,
                tone=Tone.NEUTRAL,
                status=f"{summary.unassessed} sem avaliação",
            ),
        )
    )
    return tuple(kpis)


def _table(lines: Sequence[RiskLine], labels: Mapping[int, str]) -> Table:
    return Table(
        title=TABLE_TITLE,
        columns=(
            Column("Nº", width=20),
            Column("Risco", width=60),
            Column("Natureza", width=14),
            Column("Dono", width=22),
            Column("Inerente", width=24),
            Column("Residual", width=24),
            Column("Estratégia", width=16),
            Column("Ações", width=22),
            Column("Próx. revisão", width=20),
            Column("Situação", width=16),
        ),
        rows=tuple(_row(line, labels) for line in lines),
    )


def _actions_text(line: RiskLine) -> str:
    counts = line.actions
    suffix = f" ({counts.overdue} atrasadas)" if counts.overdue else ""
    return f"{counts.open} abertas de {counts.total}{suffix}"


def _review_text(line: RiskLine) -> str:
    if line.next_review is None:
        return NEVER_REVIEWED if line.active else "encerrado"
    text = line.next_review.strftime("%d/%m/%Y")
    return text + OVERDUE_SUFFIX if line.review_overdue else text


def _row(line: RiskLine, labels: Mapping[int, str]) -> Row:
    return row(
        line.code,
        f"{line.title} · {line.category_label}",
        line.nature,
        line.owner_name,
        assessment_text(line.inherent),
        assessment_text(line.residual),
        line.strategy or "sem plano",
        _actions_text(line),
        _review_text(line),
        Cell(line.situation, SITUATION_TONES.get(line.situation, Tone.NEUTRAL)),
        project=labels.get(line.project_id),
    )


# ── Ficha do risco (ISSUE-065) ────────────────────────────────────────────────────────────────


def ficha_document(
    sheet: RiskSheet, *, scope: Scope, projects: Sequence[ProjectLike], today: date
) -> Document:
    """The ficha of a risk: the situation as KPIs and one table per block of the prototype."""
    line = sheet.line
    return Document(
        title=f"{SHEET_TITLE} {line.code}",
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(("Projeto", sheet.project_label), ("Título", line.title)),
        kpis=_sheet_kpis(sheet),
        tables=(
            _fields_table("Identificação", _identification_fields(sheet)),
            _fields_table("Avaliação", _assessment_fields(sheet)),
            _fields_table("Plano de resposta", _plan_fields(sheet)),
            _actions_table(sheet),
            _reviews_table(sheet),
            _history_table(sheet),
        ),
        paper=Paper.A4,
    )


def _sheet_kpis(sheet: RiskSheet) -> tuple[Kpi, ...]:
    line = sheet.line
    inherent = assessment_text(line.inherent)
    residual = assessment_text(line.residual)
    return (
        Kpi(
            "Inerente",
            inherent if line.inherent else NOT_ASSESSED,
            "Sem tratamento",
            tone=SITUATION_TONES.get(line.situation, Tone.NEUTRAL),
        ),
        Kpi("Residual", residual if line.residual else NOT_ASSESSED, "Com o plano de resposta"),
        Kpi("VME atual", line.vme_cents, "Probabilidade média x impacto em custo", ValueKind.MONEY),
        Kpi(
            "Situação",
            line.situation,
            "Etapa do fluxo",
            tone=SITUATION_TONES.get(line.situation, Tone.NEUTRAL),
        ),
        Kpi(
            "Próxima revisão",
            line.next_review,
            "Cadência pela severidade",
            ValueKind.DATE,
        ),
    )


def _fields_table(title: str, fields: Sequence[tuple[str, str]]) -> Table:
    return Table(
        title=title,
        columns=FIELD_COLUMNS,
        rows=tuple(row(label, value) for label, value in fields),
        per_project=False,
    )


def _identification_fields(sheet: RiskSheet) -> list[tuple[str, str]]:
    line = sheet.line
    return [
        ("Número", line.code),
        ("Natureza", line.nature),
        ("Categoria (RBS)", line.category_label),
        ("Causa", line.cause),
        ("Evento (título)", line.title),
        ("Consequência", line.consequence),
        ("Descrição", line.description or ""),
        ("Dono do risco", sheet.owner_name),
        ("Identificado por", sheet.identified_by_name),
        ("Identificado em", _date(line.identified_on)),
        ("Origem", line.origin or line.origin_type),
        ("Gatilho (sinal de alerta)", line.trigger or ""),
        ("Projeto", sheet.project_label),
    ]


def _assessment_fields(sheet: RiskSheet) -> list[tuple[str, str]]:
    line = sheet.line
    current = line.current
    fields = [
        ("Inerente (P x I)", _pi(line.inherent)),
        ("Residual (P x I)", _pi(line.residual)),
        ("Dimensão de maior impacto", line.dimension or ""),
        ("Impacto em prazo (dias)", str(line.schedule_impact_days)),
        ("Impacto em custo", _money(line.cost_impact_cents)),
        ("VME inerente", _money(sheet.vme_inherent_cents)),
        ("VME atual", _money(line.vme_cents)),
        ("Severidade-alvo", line.target_severity or "sem plano"),
        ("Risco à vida", "Sim" if line.life_risk else "Não"),
    ]
    if current is not None:
        fields.append(("Avaliação vigente", f"{current.score} ({current.severity.name})"))
    return fields


def _plan_fields(sheet: RiskSheet) -> list[tuple[str, str]]:
    line = sheet.line
    if not line.has_plan:
        return [("Plano de resposta", "não definido")]
    approval = {
        "": "não exigida",
        "Pendente": f"pendente desde {_date(sheet.approval.requested_at)}"
        if sheet.approval
        else "pendente",
        "Aprovado": f"aprovado em {_date(sheet.approval.decided_at)}"
        if sheet.approval
        else "aprovado",
        "Devolvido": f"devolvido em {_date(sheet.approval.decided_at)}"
        if sheet.approval
        else "devolvido",
    }.get(sheet.approval_situation, sheet.approval_situation)
    return [
        ("Estratégia", line.strategy or ""),
        ("Plano de resposta", line.plan or ""),
        ("Instrumento", line.instrument or ""),
        ("Solicitação de mudança (08)", sheet.change.code if sheet.change else ""),
        ("Severidade-alvo", line.target_severity or ""),
        ("Responsável pelo plano", sheet.plan_responsible_name),
        ("Aprovação da gerência do projeto", approval),
    ]


def _pi(view: AssessmentView | None) -> str:
    if view is None:
        return NOT_ASSESSED
    return f"P{view.probability} x I{view.impact}"


def _money(cents: int) -> str:
    return format_value(ValueKind.MONEY, cents)


def _date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _actions_table(sheet: RiskSheet) -> Table:
    return Table(
        title="Ações vinculadas",
        columns=(
            Column("Item", width=8),
            Column("Ação", width=60),
            Column("Responsável", width=24),
            Column("Prevista", ValueKind.DATE, width=16),
            Column("Situação", width=18),
        ),
        rows=tuple(
            row(
                action.item or "",
                action.subject,
                action.responsible_name,
                action.due_date,
                Cell(action.status_label, _action_tone(action)),
            )
            for action in sheet.actions
        ),
        per_project=False,
    )


def _action_tone(action: ActionView) -> Tone:
    if action.status == "concluida":
        return Tone.OK
    if action.status == "atrasada":
        return Tone.ERROR
    return Tone.INFO


def _reviews_table(sheet: RiskSheet) -> Table:
    return Table(
        title="Revisões",
        columns=(
            Column("Data", ValueKind.DATE, width=14),
            Column("Tipo", width=14),
            Column("Situação apurada", width=28),
            Column("De", ValueKind.INTEGER, width=8),
            Column("Para", ValueKind.INTEGER, width=8),
            Column("Comentário", width=60),
            Column("Por", width=24),
        ),
        rows=tuple(
            row(
                review.reviewed_on,
                _review_kind(review),
                review.assessed_situation,
                review.score_from,
                review.score_to,
                review.body or "",
                review.author_name,
            )
            for review in reversed(sheet.reviews)
        ),
        per_project=False,
    )


def _review_kind(review: ReviewLine) -> str:
    if review.kind == INHERENT:
        return "Avaliação inicial"
    if review.kind == "residual":
        return "Avaliação residual"
    return "Revisão periódica"


def _history_table(sheet: RiskSheet) -> Table:
    return Table(
        title="Histórico",
        columns=(
            Column("Quando", width=20),
            Column("Quem", width=24),
            Column("O que mudou", width=90),
        ),
        rows=tuple(
            row(line.moment.strftime("%d/%m/%Y %H:%M"), line.author_name, line.text)
            for line in sheet.history
        ),
        per_project=False,
    )


# ── Matriz e painel de riscos (ISSUE-066) ─────────────────────────────────────────────────────

MATRIX_TITLE = "Matriz de riscos 5x5"
MATRIX_DISTRIBUTION_TITLE = "Distribuição por probabilidade e impacto"
MATRIX_MOVEMENT_TITLE = "Movimentação inerente para residual"
PANEL_TITLE = "Painel de riscos"
PANEL_CATEGORY_TITLE = "Exposição por categoria (RBS)"
PANEL_EVOLUTION_TITLE = "Evolução do score residual das ameaças"
PANEL_EVOLUTION_TABLE_TITLE = "Evolução mensal do score residual"
PANEL_AGENDA_TITLE = "Pauta de escalonamento"
NOT_EVALUATED = "não avaliado"
NO_REDUCTION_NOTE = "Sem redução: pauta de escalonamento"
OPPORTUNITY_NOTE = "Oportunidade"
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

# The palette of the visuals in the four tones of the export: alerta and atencao share the amber
# (the document has no orange) and roxo reads as info.
DOCUMENT_TONES: Mapping[str, Tone] = {
    "ok": Tone.OK,
    "alerta": Tone.WARN,
    "atencao": Tone.WARN,
    "erro": Tone.ERROR,
    "info": Tone.INFO,
    "roxo": Tone.INFO,
    "neutro": Tone.NEUTRAL,
}


def matrix_document(
    matrix: RiskMatrix, *, scope: Scope, projects: Sequence[ProjectLike], today: date
) -> Document:
    """A matriz como documento: a distribuição por célula e a movimentação inerente-residual."""
    labels = _project_labels(projects)
    return Document(
        title=MATRIX_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Avaliação exibida", "Inerente" if matrix.assessment == INHERENT else "Residual"),
            ("Natureza", matrix.nature or "Ameaças e oportunidades"),
            ("Escala", matrix.parameters.scale.name),
            (
                "Faixas",
                " · ".join(
                    f"{style.band.name} {style.minimum} a {style.maximum}" for style in matrix.bands
                ),
            ),
            ("Riscos ativos na matriz", str(matrix.total)),
        ),
        tables=(_distribution_table(matrix), _movement_table(matrix, labels)),
        paper=Paper.A3,
    )


def matrix_chart(matrix: RiskMatrix) -> dict[str, object]:
    """O ``data-dados`` da Matriz Formatada, variante grade (D11): a célula filtra o registro."""
    probabilities = {band.level: band.name for band in matrix.parameters.probabilities}
    impacts = matrix.parameters.impacts
    cells = {(cell.probability, cell.impact): cell for cell in matrix.cells}
    levels = range(calculations.MIN_LEVEL, calculations.MAX_LEVEL + 1)
    return {
        "titulo": f"Matriz P x I {matrix.assessment}",
        "subtitulo": matrix.nature or "Ameaças e oportunidades",
        "variante": "grade",
        "rotulo_linhas": "Probabilidade x Impacto",
        "casas": 0,
        "colunas": [
            {"id": f"i{level}", "rotulo": str(level), "sub": impacts[level - 1]} for level in levels
        ],
        "linhas": [
            {
                "id": f"p{probability}",
                "rotulo": f"{probability} · {probabilities.get(probability, '')}".strip(),
                "valores": {
                    f"i{impact}": _matrix_cell_data(cells[(probability, impact)])
                    for impact in levels
                },
            }
            for probability in range(calculations.MAX_LEVEL, calculations.MIN_LEVEL - 1, -1)
        ],
        "faixas": [_band_style_data(style, legend=False) for style in matrix.bands],
        "legenda": [_band_style_data(style, legend=True) for style in matrix.bands],
    }


def _matrix_cell_data(cell: MatrixCell) -> dict[str, object]:
    """A célula do visual: a contagem, a faixa da posição, a fórmula e o link quando tem risco."""
    data: dict[str, object] = {
        "valor": len(cell.risks),
        "faixa": cell.severity.id,
        "apoio": f"{cell.probability} x {cell.impact} = {cell.score}",
    }
    if cell.href:
        data["id"] = f"p{cell.probability}|i{cell.impact}"
        data["href"] = cell.href
    else:
        data["selecionavel"] = False
    return data


def _band_style_data(style: BandStyle, *, legend: bool) -> dict[str, object]:
    label = style.band.name
    if legend:
        label = f"{label} ({style.minimum} a {style.maximum})"
    return {
        "id": style.band.id,
        "rotulo": label,
        "tom": style.tone,
        "nivel": style.level,
        "icone": style.icon,
    }


def _distribution_table(matrix: RiskMatrix) -> Table:
    probabilities = {band.level: band.name for band in matrix.parameters.probabilities}
    impacts = matrix.parameters.impacts
    levels = range(calculations.MIN_LEVEL, calculations.MAX_LEVEL + 1)
    columns = (
        Column("Probabilidade \\ Impacto", width=32),
        *(Column(f"I{level} {impacts[level - 1]}") for level in levels),
    )
    counted: dict[int, dict[int, MatrixCell]] = {}
    for cell in matrix.cells:
        counted.setdefault(cell.probability, {})[cell.impact] = cell
    rows = tuple(
        row(
            f"P{probability} {probabilities.get(probability, '')}".strip(),
            *(_distribution_cell(counted[probability][impact], matrix) for impact in levels),
        )
        for probability in range(calculations.MAX_LEVEL, calculations.MIN_LEVEL - 1, -1)
    )
    return Table(title=MATRIX_DISTRIBUTION_TITLE, columns=columns, rows=rows, per_project=False)


def _distribution_cell(cell: MatrixCell, matrix: RiskMatrix) -> Cell:
    tone = DOCUMENT_TONES.get(matrix.styles_by_band[cell.severity.id].tone, Tone.NEUTRAL)
    if not cell.risks:
        return Cell("0", tone)
    codes = ", ".join(risk.code for risk in cell.risks)
    return Cell(f"{len(cell.risks)} ({codes})", tone)


def _movement_table(matrix: RiskMatrix, labels: Mapping[int, str]) -> Table:
    return Table(
        title=MATRIX_MOVEMENT_TITLE,
        columns=(
            Column("Nº", width=20),
            Column("Risco", width=60),
            Column("Inerente", ValueKind.INTEGER, width=10),
            Column("Residual", ValueKind.INTEGER, width=10),
            Column("Observação", width=30),
        ),
        rows=tuple(
            row(
                item.code,
                item.title,
                item.inherent_score,
                item.residual_score,
                _movement_observation(item),
                project=labels.get(item.project_id),
            )
            for item in matrix.movement
        ),
    )


def _movement_observation(item: Movement) -> str:
    if item.no_reduction:
        return NO_REDUCTION_NOTE
    if item.nature != calculations.THREAT:
        return OPPORTUNITY_NOTE
    return ""


def panel_document(
    panel: RiskPanel, *, scope: Scope, projects: Sequence[ProjectLike], today: date
) -> Document:
    """O painel como documento: os indicadores, a evolução, as categorias e a pauta (D12)."""
    labels = _project_labels(projects)
    return Document(
        title=PANEL_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Data de referência", today.strftime("%d/%m/%Y")),
            ("Riscos ativos", str(panel.summary.active)),
        ),
        kpis=_panel_kpis(panel),
        charts=(Chart(PANEL_EVOLUTION_TITLE, "linhas-multiplas", panel_evolution_chart(panel)),),
        tables=(
            _panel_categories_table(panel),
            _panel_evolution_table(panel),
            _panel_agenda_table(panel, labels),
        ),
    )


def panel_evolution_chart(panel: RiskPanel) -> dict[str, object]:
    """O ``data-dados`` da evolução (linhas-multiplas): as quantidades de cada mês (D11)."""
    return {
        "titulo": PANEL_EVOLUTION_TITLE,
        "casas": 0,
        "unidade": "",
        "base_zero": True,
        "suavizar": False,
        "series": [{"id": "score", "rotulo": "Score residual somado", "papel": "realizado"}],
        "periodos": [
            {
                "ano": int(item.month[:4]),
                "mes": int(item.month[5:]),
                "valores": {"score": item.score},
            }
            for item in panel.evolution
        ],
        "altura": 320,
    }


def _panel_kpis(panel: RiskPanel) -> tuple[Kpi, ...]:
    summary = panel.summary
    kpis = [_panel_band_kpi(summary.top)]
    if summary.second is not None:
        kpis.append(_panel_band_kpi(summary.second))
    meta = (
        f"Meta: ≥ {panel.reduction_target_pct}%"
        if panel.reduction_target_pct is not None
        else "Meta: —"
    )
    kpis.extend(
        (
            Kpi(
                "Exposição (VME)",
                summary.exposure_cents,
                "Ameaças ativas",
                ValueKind.MONEY,
                tone=Tone.INFO,
                status="probabilidade média da faixa x impacto em custo",
            ),
            Kpi(
                "Revisão vencida",
                len(summary.overdue),
                "Esperado: 0",
                ValueKind.INTEGER,
                tone=Tone.ERROR if summary.overdue else Tone.OK,
                status=f"{summary.active} riscos ativos",
            ),
            Kpi(
                "Redução média",
                panel.reduction_avg_pct,
                meta,
                ValueKind.PERCENT,
                digits=0,
                tone=Tone.INFO,
                status="inerente para residual, ameaças com avaliação residual",
            ),
        )
    )
    return tuple(kpis)


def _panel_band_kpi(count: BandCount) -> Kpi:
    detail = f"{count.threats} ameaça(s)"
    if count.opportunities:
        detail += f" · {count.opportunities} oportunidade(s)"
    return Kpi(
        f"{count.band.name}s (residual)",
        count.total,
        f"Meta: {count.goal}",
        ValueKind.INTEGER,
        tone=Tone.ERROR if count.total else Tone.OK,
        status=detail if count.total else "nenhum na faixa",
    )


def _panel_categories_table(panel: RiskPanel) -> Table:
    return Table(
        title=PANEL_CATEGORY_TITLE,
        columns=(
            Column("Categoria", width=32),
            Column("Score residual somado", ValueKind.INTEGER),
            Column("Riscos", ValueKind.INTEGER),
            Column("VME", ValueKind.MONEY),
        ),
        rows=tuple(
            row(item.group, item.score, item.risks, item.vme_cents) for item in panel.categories
        ),
        per_project=False,
    )


def _panel_evolution_table(panel: RiskPanel) -> Table:
    return Table(
        title=PANEL_EVOLUTION_TABLE_TITLE,
        columns=(Column("Mês", width=14), Column("Score residual somado", ValueKind.INTEGER)),
        rows=tuple(row(_month_label(item.month), item.score) for item in panel.evolution),
        per_project=False,
    )


def _panel_agenda_table(panel: RiskPanel, labels: Mapping[int, str]) -> Table:
    return Table(
        title=PANEL_AGENDA_TITLE,
        columns=(
            Column("Nº", width=20),
            Column("Risco", width=60),
            Column("Residual", width=14),
            Column("Motivo", width=60),
            Column("Dono", width=22),
        ),
        rows=tuple(
            row(
                item.code,
                f"{item.title} · {item.category_label}",
                _agenda_score(item),
                " · ".join(item.reasons),
                item.owner_name,
                project=labels.get(item.project_id),
            )
            for item in panel.agenda
        ),
    )


def _agenda_score(item: AgendaEntry) -> str:
    if item.score is None or item.severity is None:
        return NOT_EVALUATED
    return f"{item.score} {item.severity.name}"


def _month_label(month: str) -> str:
    """``2026-09`` as the prototype printed it: ``set/26``."""
    year, number = int(month[:4]), int(month[5:])
    return f"{MONTH_SHORT_NAMES[number - 1]}/{year % 100:02d}"


def _project_labels(projects: Sequence[ProjectLike]) -> dict[int, str]:
    return {item.id: project_label(item) for item in projects}
