"""The calculated panel of Qualidade (ISSUE-071, D6, D11): the indicators and the panel.

The indicators are the numbers of ``indicadoresQualidadeDe`` of the prototype and are public on
purpose: the Início (ISSUE-079) reads them later. The panel adds the series of the six months
ending on the month of the reference date, the Pareto by discipline, the RNC by origin, the
performance by company, the treatment agenda and the overdue audits. Nothing here reads the
clock: the reference date is an argument and every number is calculated on the query.

Nothing is duplicated either: the deadlines, the overdue treatment and verification, the
pending concession and the recurrence come from ``service`` lines (``calculations``); the
approval of the inspections, the conformity and the adherence come from the pure formulas of
``calculations``. The cancelled RNC are out of the aggregations of the panel, as in the
prototype; the cost of the non-quality KPI sums them all, also as in the prototype.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.qualidade import calculations, service

MODULE = "qualidade"
PANEL_MONTHS = 6
CRITICAL_SEVERITY = calculations.SEVERITIES[0]
ONE_DECIMAL = Decimal("0.1")


@dataclass(frozen=True)
class QualityIndicators:
    """The quality indicators of the scope, without filters (what the panel and the Início read)."""

    open_rncs: int
    closed_rncs: int
    overdue_rncs: int
    overdue_verifications: int
    critical_open_rncs: int
    average_treatment_days: int | None
    first_time_effectiveness_pct: Decimal | None
    inspections: int
    rejected_inspections: int
    inspection_approval_pct: Decimal | None
    inspection_approval_target_pct: Decimal
    audit_conformity_pct: Decimal | None
    audit_conformity_target_pct: Decimal
    audits_done: int
    audits_due: int
    audit_program_adherence_pct: Decimal | None
    overdue_audits: int
    open_audit_nonconformities: int
    itps: int
    itps_without_approval: int
    non_quality_cost_cents: int


@dataclass(frozen=True)
class QualityMonthPoint:
    """One month of the series: the flows of the RNC, the inspections and the approval."""

    month: str
    opened: int
    closed: int
    open: int
    inspections: int
    approval_pct: Decimal | None


@dataclass(frozen=True)
class QualityGroupLine:
    """One group of the Pareto by discipline or by origin: the total, the share and the accumulated."""

    name: str
    total: int
    active: int
    cost_cents: int
    pct: Decimal
    accumulated_pct: Decimal


@dataclass(frozen=True)
class QualityCompanyLine:
    """The performance of one company: inspections, rejections, RNC, cost and approval."""

    company_id: int
    company_name: str
    inspections: int
    rejected: int
    rncs: int
    cost_cents: int
    approval_pct: Decimal | None


@dataclass(frozen=True)
class QualityAgendaEntry:
    """One RNC of the treatment agenda, with the reasons that put it there."""

    line: service.RncLine
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class QualityPanel:
    """Everything the panel shows: the indicators, the series, the groups and the agenda."""

    indicators: QualityIndicators
    series: tuple[QualityMonthPoint, ...]
    by_discipline: tuple[QualityGroupLine, ...]
    by_origin: tuple[QualityGroupLine, ...]
    by_company: tuple[QualityCompanyLine, ...]
    agenda: tuple[QualityAgendaEntry, ...]
    overdue_audits: tuple[service.AuditLine, ...]
    reference_date: date
    treatment_limit: str
    registered: int

    @property
    def is_empty(self) -> bool:
        """Whether the scope still has no RNC, inspection, audit nor ITP to show."""
        return not self.registered


@dataclass
class _CompanyAccumulator:
    """The running totals of one company while the panel is being calculated."""

    name: str
    inspections: int = 0
    rejected: int = 0
    rncs: int = 0
    cost_cents: int = 0


@dataclass
class _GroupAccumulator:
    """The running totals of one group of the Pareto while the panel is being calculated."""

    total: int = 0
    active: int = 0
    cost_cents: int = 0


@dataclass(frozen=True)
class _Records:
    """The records of the scope as the query read them, with the date and the parameters."""

    reference_date: date
    parameters: Mapping[str, Any]
    lines: Sequence[service.RncLine]
    inspections: Sequence[service.InspectionLine]
    audits: Sequence[service.AuditLine]
    itps: Sequence[service.ItpLine]


def quality_indicators(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> QualityIndicators:
    """The indicators of the scope on the date: RNC, inspections, audits, ITP and the cost."""
    rbac.require_module(user, MODULE)
    return _indicators(_records(session, user=user, scope=scope, reference_date=reference_date))


def quality_panel(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> QualityPanel:
    """The panel of the scope: the indicators, the six months, the groups, the agenda and the alert."""
    rbac.require_module(user, MODULE)
    records = _records(session, user=user, scope=scope, reference_date=reference_date)
    return QualityPanel(
        indicators=_indicators(records),
        series=quality_series(
            records.lines, records.inspections, reference_date=records.reference_date
        ),
        by_discipline=_group_lines(records.lines, lambda line: line.discipline),
        by_origin=_group_lines(records.lines, lambda line: line.origin),
        by_company=_company_lines(records.lines, records.inspections),
        agenda=_agenda(records.lines),
        overdue_audits=tuple(audit for audit in records.audits if audit.overdue),
        reference_date=records.reference_date,
        treatment_limit=treatment_limit_days(records.parameters.get("prazoTratamentoDias", {})),
        registered=(
            len(records.lines) + len(records.inspections) + len(records.audits) + len(records.itps)
        ),
    )


def _records(session: Session, *, user: User, scope: Scope, reference_date: date) -> _Records:
    return _Records(
        reference_date=reference_date,
        parameters=service.parameters(session, reference_date=reference_date),
        lines=service._lines(
            session, user=user, project_id=scope.project_id, reference_date=reference_date
        ),
        inspections=service._inspection_lines(session, project_id=scope.project_id),
        audits=service._audit_lines(
            session, project_id=scope.project_id, reference_date=reference_date
        ),
        itps=service._itp_lines(
            session, project_id=scope.project_id, reference_date=reference_date
        ),
    )


# ── Indicadores ──────────────────────────────────────────────────────────────────────────────


def _indicators(records: _Records) -> QualityIndicators:
    """The composition of the indicators from the lines of the scope (the prototype's formulas)."""
    lines = records.lines
    summary = service._summary(lines)
    closed = [line for line in lines if line.situation == calculations.SITUATION_CLOSED]
    rejected = [item for item in records.inspections if item.result == calculations.RESULT_REJECTED]
    done = [audit for audit in records.audits if audit.situation == calculations.AUDIT_DONE]
    due = [audit for audit in records.audits if audit.audit_date <= records.reference_date]
    due_done = [audit for audit in due if audit.situation == calculations.AUDIT_DONE]
    verified = sum(audit.items_verified or 0 for audit in done)
    conforming = sum(audit.items_conforming or 0 for audit in done)
    return QualityIndicators(
        open_rncs=summary.active,
        closed_rncs=summary.closed,
        overdue_rncs=summary.overdue,
        overdue_verifications=summary.verification_overdue,
        critical_open_rncs=summary.critical,
        average_treatment_days=summary.average_days,
        first_time_effectiveness_pct=calculations.first_time_effectiveness_pct(
            line.recurrence_count for line in closed
        ),
        inspections=len(records.inspections),
        rejected_inspections=len(rejected),
        inspection_approval_pct=calculations.inspection_approval_rate(
            item.result for item in records.inspections
        ),
        inspection_approval_target_pct=_parameter_pct(
            records.parameters, "metaAprovacaoInspecaoPct"
        ),
        audit_conformity_pct=calculations.audit_conformity_rate(conforming, verified),
        audit_conformity_target_pct=_parameter_pct(
            records.parameters, "metaConformidadeAuditoriaPct"
        ),
        audits_done=len(done),
        audits_due=len(due),
        audit_program_adherence_pct=calculations.audit_program_adherence(len(due_done), len(due)),
        overdue_audits=sum(1 for audit in records.audits if audit.overdue),
        open_audit_nonconformities=sum(audit.open_nc for audit in records.audits),
        itps=len(records.itps),
        itps_without_approval=sum(1 for itp in records.itps if not itp.approved_by_client),
        non_quality_cost_cents=summary.cost_cents,
    )


def _parameter_pct(parameters: Mapping[str, Any], key: str) -> Decimal:
    """A target of the parameters in force, as a decimal of percentage points."""
    return Decimal(str(parameters.get(key, 0)))


def treatment_limit_days(treatment_days: Mapping[str, int]) -> str:
    """``15 a 45 dias``: the band of the treatment deadlines, from the parameters in force."""
    values = [int(value) for value in treatment_days.values()]
    if not values:
        return "·"
    return f"{min(values)} a {max(values)} dias"


# ── Série dos 6 meses ────────────────────────────────────────────────────────────────────────


def quality_series(
    lines: Sequence[service.RncLine],
    inspections: Sequence[service.InspectionLine],
    *,
    reference_date: date,
) -> tuple[QualityMonthPoint, ...]:
    """The six months ending on the month of the reference date, as the prototype drew them."""
    points: list[QualityMonthPoint] = []
    for month in _months(reference_date):
        in_month = [item for item in inspections if _month_of(item.inspection_date) == month]
        points.append(
            QualityMonthPoint(
                month=month,
                opened=sum(1 for line in lines if _month_of(line.rnc_date) == month),
                closed=sum(
                    1
                    for line in lines
                    if line.situation == calculations.SITUATION_CLOSED
                    and line.closing_date is not None
                    and _month_of(line.closing_date) == month
                ),
                open=sum(
                    1
                    for line in lines
                    if _month_of(line.rnc_date) <= month
                    and (line.closing_date is None or _month_of(line.closing_date) > month)
                ),
                inspections=len(in_month),
                approval_pct=calculations.inspection_approval_rate(
                    item.result for item in in_month
                ),
            )
        )
    return tuple(points)


def _months(reference_date: date) -> list[str]:
    current = calendario.period_of(calendario.MONTHLY, reference_date)
    labels: list[str] = []
    for offset in range(-(PANEL_MONTHS - 1), 1):
        label = calendario.add_periods(calendario.MONTHLY, current, offset)
        if label is not None:
            labels.append(label)
    return labels


def _month_of(value: date) -> str:
    return f"{value.year}-{value.month:02d}"


# ── Pareto por disciplina, RNC por origem e empresas ─────────────────────────────────────────


def _group_lines(
    lines: Sequence[service.RncLine], key: Callable[[service.RncLine], str]
) -> tuple[QualityGroupLine, ...]:
    """The non-cancelled RNC grouped, sorted by total desc and cost desc, with the accumulated.

    The tie between totals is broken by the cost of the group, as in the prototype; the order
    of the lines is stable, so a double tie keeps the order of the register.
    """
    grouped: dict[str, _GroupAccumulator] = {}
    for line in lines:
        if line.situation == calculations.SITUATION_CANCELLED:
            continue
        item = grouped.setdefault(key(line), _GroupAccumulator())
        item.total += 1
        item.active += 1 if line.active else 0
        item.cost_cents += line.cost_cents
    ordered = sorted(grouped.items(), key=lambda pair: (-pair[1].total, -pair[1].cost_cents))
    overall = sum(item.total for _, item in ordered)
    accumulated = 0
    result: list[QualityGroupLine] = []
    for name, item in ordered:
        accumulated += item.total
        result.append(
            QualityGroupLine(
                name=name,
                total=item.total,
                active=item.active,
                cost_cents=item.cost_cents,
                pct=_share(item.total, overall) or Decimal(0),
                accumulated_pct=_share(accumulated, overall) or Decimal(0),
            )
        )
    return tuple(result)


def _company_lines(
    lines: Sequence[service.RncLine], inspections: Sequence[service.InspectionLine]
) -> tuple[QualityCompanyLine, ...]:
    """The performance by company: inspections and rejections from the records, RNC and cost.

    ``Aprovação = (inspeções - reprovadas) / inspeções``; the order is RNC desc and cost desc,
    as in the prototype; the company with no inspection has no approval (``·``).
    """
    grouped: dict[int, _CompanyAccumulator] = {}
    for inspection in inspections:
        item = grouped.setdefault(
            inspection.company_id, _CompanyAccumulator(name=inspection.company_name)
        )
        item.inspections += 1
        if inspection.result == calculations.RESULT_REJECTED:
            item.rejected += 1
    for line in lines:
        if line.situation == calculations.SITUATION_CANCELLED:
            continue
        item = grouped.setdefault(line.company_id, _CompanyAccumulator(name=line.company_name))
        item.rncs += 1
        item.cost_cents += line.cost_cents
    ordered = sorted(grouped.items(), key=lambda pair: (-pair[1].rncs, -pair[1].cost_cents))
    return tuple(
        QualityCompanyLine(
            company_id=company_id,
            company_name=item.name,
            inspections=item.inspections,
            rejected=item.rejected,
            rncs=item.rncs,
            cost_cents=item.cost_cents,
            approval_pct=_share(item.inspections - item.rejected, item.inspections),
        )
        for company_id, item in ordered
    )


def _share(part: int, whole: int) -> Decimal | None:
    """The share in points, one decimal, half up; no whole gives ``None`` (the screen's ``·``)."""
    if not whole:
        return None
    return (Decimal(part) / Decimal(whole) * 100).quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


# ── Pauta de tratamento ──────────────────────────────────────────────────────────────────────


def _agenda(lines: Sequence[service.RncLine]) -> tuple[QualityAgendaEntry, ...]:
    """The RNC that need a decision: overdue, verification overdue, critical or with concession.

    The reasons are the four of the prototype and the order is the overdue days desc; the sort
    is stable, so the ties keep the order of the register.
    """
    entries: list[QualityAgendaEntry] = []
    for line in lines:
        if not (
            line.overdue
            or line.verification_overdue
            or (line.active and line.severity == CRITICAL_SEVERITY)
            or line.concession_pending
        ):
            continue
        entries.append(QualityAgendaEntry(line=line, reasons=_agenda_reasons(line)))
    entries.sort(key=lambda entry: -entry.line.days_overdue)
    return tuple(entries)


def _agenda_reasons(line: service.RncLine) -> tuple[str, ...]:
    reasons: list[str] = []
    if line.overdue:
        days = line.days_overdue
        reasons.append(f"prazo de tratamento vencido há {days} {'dia' if days == 1 else 'dias'}")
    if line.verification_overdue:
        reasons.append("verificação de eficácia vencida")
    if line.active and line.severity == CRITICAL_SEVERITY:
        reasons.append("severidade crítica")
    if line.concession_pending:
        reasons.append("concessão do cliente pendente")
    return tuple(reasons)
