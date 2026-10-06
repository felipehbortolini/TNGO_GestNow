"""Pure calculations of the Governança module: stage, next step, authority, deadlines and KPIs.

Nothing here reads the clock or the database: the facade (``service``) passes the facts of each
change and the reference date, and gets numbers back. Every rule has a business name (see the
LEIA-ME of the module) and a boundary test in ``api/tests/governanca/test_calculos.py``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from src.modulos.governanca import models

STAGE_NAMES = ("Solicitação", "Análise de impacto", "Decisão", "Implementação", "Encerramento")
LAST_STAGE = len(STAGE_NAMES) - 1

_STAGE_BY_SITUATION = {
    models.SITUATION_REGISTERED: 0,
    models.SITUATION_ANALYSIS: 1,
    models.SITUATION_AWAITING: 2,
    models.SITUATION_POSTPONED: 2,
    models.SITUATION_APPROVED: 3,
    models.SITUATION_APPROVED_WITH_CONDITIONS: 3,
    models.SITUATION_IMPLEMENTING: 3,
}

_NEXT_STEP_BY_SITUATION = {
    models.SITUATION_REGISTERED: "Iniciar a análise de impacto",
    models.SITUATION_POSTPONED: "Reapresentar para decisão",
    models.SITUATION_APPROVED: "Iniciar a implementação",
    models.SITUATION_APPROVED_WITH_CONDITIONS: "Iniciar a implementação",
}

_HOUR_REQUESTED = time(8, 0)
_HOUR_ANALYSED = time(10, 0)
_HOUR_DECIDED = time(15, 0)
_HOUR_IMPLEMENTING = time(9, 0)
_HOUR_CLOSED = time(17, 0)

ONE_TENTH = Decimal("0.1")
PERCENT = Decimal(100)


def change_stage(situation: str) -> int:
    """Etapa da mudança: the index (0 to 4) of the stage the situation sits in.

    Registrada is 0, Em análise de impacto 1, Aguardando comitê and Adiada 2, the approved ones and
    Em implementação 3; Encerrada, Rejeitada and Cancelada close the flow at 4.
    """
    return _STAGE_BY_SITUATION.get(situation, LAST_STAGE)


def is_open(situation: str) -> bool:
    """Whether the change still has a life ahead: it is not rejected, closed or cancelled."""
    return situation not in models.TERMINAL_SITUATIONS


def is_approved(situation: str) -> bool:
    """Whether the change counts as approved: decided positively and still on its way."""
    return situation in models.APPROVED_SITUATIONS


def days_between(start: date, end: date) -> int:
    """Whole calendar days from ``start`` to ``end`` (negative when ``end`` comes first)."""
    return (end - start).days


@dataclass(frozen=True)
class AuthorityLimit:
    """The authority the rules ask for and the cost the project manager may decide alone."""

    authority: str
    limit_cents: int


def minimum_change_authority(
    *,
    value_cents: int,
    budget_cents: int | None,
    affects_contract_milestone: bool,
    manager_limit_percent: Decimal | int | float,
) -> AuthorityLimit:
    """Alçada mínima da mudança: Gerente do projeto or Comitê.

    The Gerente decides when the value (cost or reallocated amount, in absolute terms) fits in the
    percentage of the project budget set in Configurações and the change does not touch a contract
    milestone; any other case goes to the Comitê. The analyst may raise the authority, never lower it.
    """
    percent = Decimal(str(manager_limit_percent or 0))
    limit = int((Decimal(budget_cents or 0) * percent / PERCENT).to_integral_value(ROUND_HALF_UP))
    manager_decides = abs(value_cents) <= limit and not affects_contract_milestone
    authority = models.AUTHORITY_MANAGER if manager_decides else models.AUTHORITY_COMMITTEE
    return AuthorityLimit(authority=authority, limit_cents=limit)


@dataclass(frozen=True)
class AuthorityFacts:
    """What decides the minimum authority of a change: its type, source, money and contract mark."""

    kind: str
    resource_source: str | None
    cost_cents: int
    transferred_cents: int
    budget_cents: int | None
    affects_contract_milestone: bool


def required_change_authority(
    facts: AuthorityFacts, *, manager_limit_percent: Decimal | int | float
) -> AuthorityLimit:
    """Alçada exigida da mudança: the minimum authority of the whole change, as the server computes it.

    The value is the larger of the absolute cost and the total moved between EAC items. A release of
    reserve and the source Reserva gerencial always go to the Comitê, whatever the value; any other
    change follows ``minimum_change_authority``. The analyst may raise the authority, never lower it.
    """
    value = max(abs(facts.cost_cents), abs(facts.transferred_cents))
    by_value = minimum_change_authority(
        value_cents=value,
        budget_cents=facts.budget_cents,
        affects_contract_milestone=facts.affects_contract_milestone,
        manager_limit_percent=manager_limit_percent,
    )
    always_committee = (
        facts.kind == models.TYPE_RESERVE_RELEASE
        or facts.resource_source == models.SOURCE_MANAGEMENT_RESERVE
    )
    if always_committee:
        return AuthorityLimit(
            authority=models.AUTHORITY_COMMITTEE, limit_cents=by_value.limit_cents
        )
    return by_value


def is_authority_lowered(chosen: str, required: str) -> bool:
    """Whether the chosen authority is below the required one: only the Gerente under the Comitê is."""
    return required == models.AUTHORITY_COMMITTEE and chosen != models.AUTHORITY_COMMITTEE


def analysis_deadline(start: date, analysis_days: int) -> date:
    """Prazo padrão da análise: the start of the analysis plus the days of the parameter."""
    return start + timedelta(days=analysis_days)


def emergency_ratification_due_date(start: date, ratification_days: int) -> date:
    """Prazo de ratificação emergencial: the start of the execution plus the configured days."""
    return start + timedelta(days=ratification_days)


def is_analysis_overdue(
    situation: str, analysis_deadline: date | None, reference_date: date
) -> bool:
    """Análise vencida: the change is in analysis and its deadline is before the reference date."""
    return (
        situation == models.SITUATION_ANALYSIS
        and analysis_deadline is not None
        and analysis_deadline < reference_date
    )


def is_emergency_pending(*, emergency: bool, has_decision: bool, situation: str) -> bool:
    """Ratificação pendente: executed ahead of the Comitê, still open and without a decision."""
    return emergency and not has_decision and is_open(situation)


def is_ratification_overdue(*, pending: bool, due_date: date | None, reference_date: date) -> bool:
    """Ratificação vencida: it is pending and its due date is before the reference date."""
    return pending and due_date is not None and due_date < reference_date


@dataclass(frozen=True)
class NextStepFacts:
    """What the orientation text of the next step reads of a change."""

    situation: str
    authority: str | None = None
    analysis_deadline: date | None = None
    open_actions: int = 0
    pending_eac_revision: bool = False
    pending_eap_revision: bool = False


def next_step(facts: NextStepFacts) -> str:
    """Próxima etapa: the orientation text of the list and of the ficha ('' when the flow ended)."""
    situation = facts.situation
    if situation == models.SITUATION_ANALYSIS:
        return "Concluir a análise de impacto" + _until(facts.analysis_deadline)
    if situation == models.SITUATION_AWAITING:
        return (
            "Decisão do gerente do projeto"
            if facts.authority == models.AUTHORITY_MANAGER
            else "Decisão do Comitê"
        )
    if situation == models.SITUATION_IMPLEMENTING:
        return _implementation_step(facts)
    return _NEXT_STEP_BY_SITUATION.get(situation, "")


def _until(deadline: date | None) -> str:
    return f" até {deadline:%d/%m/%Y}" if deadline is not None else ""


def _implementation_step(facts: NextStepFacts) -> str:
    if facts.open_actions:
        noun = "1 ação" if facts.open_actions == 1 else f"{facts.open_actions} ações"
        return f"Concluir {noun} de implementação"
    if facts.pending_eac_revision:
        return "Incorporar a SM na EAC (nova revisão)"
    if facts.pending_eap_revision:
        return "Incorporar a SM na EAP (nova revisão)"
    return "Encerrar a mudança"


@dataclass(frozen=True)
class ChangeFigures:
    """The numbers of one change that the KPIs add up: situation, dates, impact and decision."""

    situation: str
    request_date: date
    origin: str = ""
    kind: str = ""
    cost_cents: int | None = None
    term_days: int | None = None
    decision_date: date | None = None
    analysis_deadline: date | None = None
    emergency: bool = False


@dataclass(frozen=True)
class ChangeSummary:
    """The indicators of the Registro de mudanças for one scope."""

    total: int
    in_analysis: int
    overdue_analysis: int
    awaiting_committee: int
    postponed: int
    implementing: int
    approved: int
    approved_in_year: int
    year: int
    approved_value_cents: int
    approved_value_percent: Decimal | None
    approved_term_days: int
    mean_decision_days: int | None
    pending_emergencies: int


def summarize_changes(
    figures: Sequence[ChangeFigures], *, budget_cents: int | None, reference_date: date
) -> ChangeSummary:
    """Indicadores do registro: counts by situation, approved value and term, mean decision time.

    Valor aprovado acumulado is the sum of the cost of the approved changes, and its percentage is
    taken over the budget (``None`` without budget). Impacto de prazo acumulado is the sum of their
    days. Tempo médio de decisão is the mean of the days from request to decision over every change
    with a decision, rounded half up.
    """
    approved = [item for item in figures if is_approved(item.situation)]
    value = sum(item.cost_cents or 0 for item in approved)
    return ChangeSummary(
        total=len(figures),
        in_analysis=_count(figures, models.SITUATION_REGISTERED, models.SITUATION_ANALYSIS),
        overdue_analysis=sum(
            is_analysis_overdue(item.situation, item.analysis_deadline, reference_date)
            for item in figures
        ),
        awaiting_committee=_count(figures, models.SITUATION_AWAITING),
        postponed=_count(figures, models.SITUATION_POSTPONED),
        implementing=_count(figures, models.SITUATION_IMPLEMENTING),
        approved=len(approved),
        approved_in_year=sum(1 for item in approved if _decided_in(item, reference_date.year)),
        year=reference_date.year,
        approved_value_cents=value,
        approved_value_percent=percent_of(value, budget_cents),
        approved_term_days=sum(item.term_days or 0 for item in approved),
        mean_decision_days=mean_decision_days(figures),
        pending_emergencies=sum(1 for item in figures if _emergency_pending(item)),
    )


def _count(figures: Sequence[ChangeFigures], *situations: str) -> int:
    return sum(1 for item in figures if item.situation in situations)


def _decided_in(item: ChangeFigures, year: int) -> bool:
    return item.decision_date is not None and item.decision_date.year == year


def _emergency_pending(item: ChangeFigures) -> bool:
    return is_emergency_pending(
        emergency=item.emergency,
        has_decision=item.decision_date is not None,
        situation=item.situation,
    )


def percent_of(value_cents: int, budget_cents: int | None) -> Decimal | None:
    """Percentage of the budget with one decimal place, half up; ``None`` without a budget."""
    if not budget_cents:
        return None
    return (Decimal(value_cents) * PERCENT / Decimal(budget_cents)).quantize(
        ONE_TENTH, rounding=ROUND_HALF_UP
    )


def mean_decision_days(figures: Sequence[ChangeFigures]) -> int | None:
    """Tempo médio de decisão: whole days from request to decision, mean rounded half up.

    Only the changes that have a decision count; ``None`` when none has.
    """
    spans = [
        days_between(item.request_date, item.decision_date)
        for item in figures
        if item.decision_date is not None
    ]
    if not spans:
        return None
    count = len(spans)
    return (2 * sum(spans) + count) // (2 * count)


# ── Painel de mudanças (ISSUE-026) ───────────────────────────────────────


@dataclass(frozen=True)
class CountLine:
    """Uma linha de contagem do painel: o rótulo e o total."""

    label: str
    total: int


@dataclass(frozen=True)
class ParetoLine:
    """Uma linha do Pareto: total, participação e percentual acumulado (uma casa)."""

    label: str
    total: int
    percent: Decimal
    cumulative: Decimal


@dataclass(frozen=True)
class ApprovedMonth:
    """Um mês do painel: aprovadas e solicitadas, com o valor e o prazo acumulados até ele."""

    month: date
    approved: int
    requested: int
    value_cents: int
    term_days: int


def count_lines(labels: Iterable[str], order: Sequence[str]) -> tuple[CountLine, ...]:
    """As contagens por rótulo: primeiro a ordem fixa pedida, depois o resto em ordem alfabética."""
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    remaining = sorted(label for label in counts if label not in order)
    return tuple(
        CountLine(label, counts[label]) for label in (*order, *remaining) if label in counts
    )


def pareto_lines(lines: Sequence[CountLine]) -> tuple[ParetoLine, ...]:
    """O Pareto: maior total primeiro (empate pelo rótulo), com o acumulado fechando em 100%."""
    total = sum(line.total for line in lines)
    ordered = sorted(lines, key=lambda line: (-line.total, line.label))
    result: list[ParetoLine] = []
    accumulated = 0
    for line in ordered:
        accumulated += line.total
        result.append(
            ParetoLine(
                label=line.label,
                total=line.total,
                percent=(Decimal(line.total) * PERCENT / Decimal(total)).quantize(
                    ONE_TENTH, rounding=ROUND_HALF_UP
                ),
                cumulative=(Decimal(accumulated) * PERCENT / Decimal(total)).quantize(
                    ONE_TENTH, rounding=ROUND_HALF_UP
                ),
            )
        )
    return tuple(result)


def approval_rate(figures: Sequence[ChangeFigures]) -> Decimal | None:
    """Taxa de aprovação: aprovadas sobre decididas, sem as adiadas; ``None`` sem decisão."""
    approved = sum(1 for item in figures if is_approved(item.situation))
    rejected = sum(1 for item in figures if item.situation == models.SITUATION_REJECTED)
    decided = approved + rejected
    if not decided:
        return None
    return (Decimal(approved) * PERCENT / Decimal(decided)).quantize(
        ONE_TENTH, rounding=ROUND_HALF_UP
    )


def approved_monthly(
    figures: Sequence[ChangeFigures], reference_date: date
) -> tuple[ApprovedMonth, ...]:
    """Valor e prazo aprovados acumulados por mês, do primeiro pedido ao mês da referência.

    Cada mês conta as aprovadas e as solicitadas dele e acumula o valor e o prazo das aprovadas;
    as mudanças sem data de pedido não entram.
    """
    dated = [item for item in figures if item.request_date is not None]
    if not dated:
        return ()
    first = min(item.request_date for item in dated)
    approved = [
        item for item in figures if is_approved(item.situation) and item.decision_date is not None
    ]
    months: list[date] = []
    current = _month_start(first)
    last = _month_start(reference_date)
    while current <= last:
        months.append(current)
        current = _next_month(current)
    value = 0
    term = 0
    result: list[ApprovedMonth] = []
    for month in months:
        done = [
            item
            for item in approved
            if item.decision_date is not None and _month_start(item.decision_date) == month
        ]
        value += sum(item.cost_cents or 0 for item in done)
        term += sum(item.term_days or 0 for item in done)
        requested = sum(1 for item in dated if _month_start(item.request_date) == month)
        result.append(ApprovedMonth(month, len(done), requested, value, term))
    return tuple(result)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _next_month(value: date) -> date:
    index = value.year * 12 + value.month
    return date(index // 12, index % 12 + 1, 1)


@dataclass(frozen=True)
class HistoryFacts:
    """The dates and people of a change from which its history is read."""

    kind: str
    origin: str
    priority: str
    situation: str
    request_date: date
    requester_id: int
    analysis_date: date | None = None
    analyst_id: int | None = None
    authority: str | None = None
    decision_date: date | None = None
    decision_result: str | None = None
    decision_justification: str | None = None
    decision_by_id: int | None = None
    implementation_start: date | None = None
    emergency_execution: bool = False
    closing_date: date | None = None
    closed_by_id: int | None = None
    cancellation_note: str | None = None


@dataclass(frozen=True)
class HistoryLine:
    """One line of the Histórico tab: when, who (a person id) and what happened."""

    moment: datetime
    person_id: int | None
    text: str


def change_history(facts: HistoryFacts) -> list[HistoryLine]:
    """Histórico da mudança, newest first, built from the dates the change carries.

    The hour of each line is fixed by the kind of event (the register keeps dates, not instants),
    so the order of a day is always request, analysis, decision, implementation and closing.
    """
    lines = [
        HistoryLine(
            _at(facts.request_date, _HOUR_REQUESTED),
            facts.requester_id,
            f"Solicitação registrada ({facts.kind}, origem {facts.origin}, "
            f"prioridade {facts.priority}).",
        )
    ]
    if facts.analysis_date is not None:
        lines.append(_analysis_line(facts, facts.analysis_date))
    if facts.decision_date is not None:
        lines.append(_decision_line(facts, facts.decision_date))
    if facts.implementation_start is not None and not facts.emergency_execution:
        lines.append(
            HistoryLine(
                _at(facts.implementation_start, _HOUR_IMPLEMENTING), None, "Implementação iniciada."
            )
        )
    lines.extend(_closing_lines(facts))
    return sorted(lines, key=lambda line: line.moment, reverse=True)


def _analysis_line(facts: HistoryFacts, day: date) -> HistoryLine:
    authority = facts.authority or models.AUTHORITY_COMMITTEE
    return HistoryLine(
        _at(day, _HOUR_ANALYSED),
        facts.analyst_id,
        f"Análise de impacto concluída e enviada para decisão ({authority}).",
    )


def _decision_line(facts: HistoryFacts, day: date) -> HistoryLine:
    reason = f" {facts.decision_justification}" if facts.decision_justification else ""
    return HistoryLine(
        _at(day, _HOUR_DECIDED), facts.decision_by_id, f"Decisão: {facts.decision_result}.{reason}"
    )


def _closing_lines(facts: HistoryFacts) -> list[HistoryLine]:
    if facts.closing_date is None:
        return []
    moment = _at(facts.closing_date, _HOUR_CLOSED)
    if facts.situation == models.SITUATION_CANCELLED:
        note = f": {facts.cancellation_note}" if facts.cancellation_note else "."
        return [HistoryLine(moment, facts.closed_by_id, f"Solicitação cancelada{note}")]
    if facts.situation == models.SITUATION_CLOSED:
        return [
            HistoryLine(
                moment, facts.closed_by_id, "Mudança encerrada com as linhas de base atualizadas."
            )
        ]
    return []


def _at(day: date, hour: time) -> datetime:
    return datetime.combine(day, hour)


# ── Ações de implementação sugeridas pela análise (ISSUE-025) ────────────────────────────────

NO_IMPACT_TEXT = "sem impacto"

# A dimensão apontada pela análise, a chave da ação, o módulo dono e a função do responsável.
SUGGESTED_ACTION_RULES: tuple[tuple[str, str, str, str, str], ...] = (
    ("custo", "eac", "03", "Custos", "Incorporar a {code} na EAC (nova revisão do orçamento)"),
    (
        "prazo",
        "cronograma",
        "02",
        "Planejamento",
        "Atualizar a linha de base do cronograma e a Curva S ({code})",
    ),
    (
        "contrato",
        "contrato",
        "03",
        "Fiscal de contratos",
        "Formalizar o aditivo contratual da {code} ({detail})",
    ),
    ("riscos", "riscos", "05", "", "Revisar os riscos afetados pela {code} ({detail})"),
    (
        "sms",
        "sms",
        "07",
        "HSE",
        "Atualizar a análise de risco de SMS da {code} ({detail})",
    ),
    (
        "qualidade",
        "qualidade",
        "06",
        "Qualidade",
        "Atualizar especificação e plano de inspeção da {code} ({detail})",
    ),
)


@dataclass(frozen=True)
class ImpactFacts:
    """O que a análise de impacto apontou, como as ações sugeridas leem."""

    cost_cents: int | None
    term_days: int | None
    quality: str | None
    risks: str | None
    safety: str | None
    contract: str | None


@dataclass(frozen=True)
class SuggestedAction:
    """Uma ação de implementação sugerida pela análise: a chave, o módulo, o assunto e o dono."""

    key: str
    module: str
    subject: str
    responsible_id: int | None


def has_impact(text: str | None) -> bool:
    """Whether a dimension's text says there is an impact: filled in and not "sem impacto"."""
    return _plain(text or "") not in ("", NO_IMPACT_TEXT)


def person_for_role(
    role: str, fallback_id: int | None, roles: Mapping[int, str | None]
) -> int | None:
    """A pessoa com a função pedida, ou o fallback (o gerente do projeto) quando não há."""
    wanted = _plain(role)
    if wanted:
        for person_id, person_role in sorted(roles.items()):
            if _plain(person_role or "") == wanted:
                return person_id
    return fallback_id


def suggested_change_actions(
    impact: ImpactFacts, *, code: str, manager_id: int | None, roles: Mapping[int, str | None]
) -> tuple[SuggestedAction, ...]:
    """As ações que a aprovação cria na Central, pelo que a análise apontou (02, 03, 05, 06 e 07)."""
    facts = {
        "custo": bool(impact.cost_cents),
        "prazo": bool(impact.term_days),
        "contrato": has_impact(impact.contract),
        "riscos": has_impact(impact.risks),
        "sms": has_impact(impact.safety),
        "qualidade": has_impact(impact.quality),
    }
    details = {
        "contrato": impact.contract or "",
        "riscos": impact.risks or "",
        "sms": impact.safety or "",
        "qualidade": impact.quality or "",
    }
    actions: list[SuggestedAction] = []
    for dimension, key, module, role, template in SUGGESTED_ACTION_RULES:
        if not facts[dimension]:
            continue
        actions.append(
            SuggestedAction(
                key=key,
                module=module,
                subject=template.format(code=code, detail=details.get(dimension, "")),
                responsible_id=person_for_role(role, manager_id, roles),
            )
        )
    return tuple(actions)


def _plain(text: str) -> str:
    """Text without accents, trimmed and in lower case, for the comparisons of the rules."""
    decomposed = unicodedata.normalize("NFKD", text)
    return (
        "".join(char for char in decomposed if not unicodedata.combining(char)).strip().casefold()
    )
