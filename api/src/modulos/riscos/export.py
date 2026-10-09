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
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.riscos import presentation
from src.modulos.riscos.ficha_service import ActionView, ReviewLine, RiskSheet
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
