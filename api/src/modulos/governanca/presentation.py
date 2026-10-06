"""How the Governança screens and exports write what the facade hands them (D12).

The texts of the KPI cards, the cost and term of a change and the tone of each situation live here once:
the fragments (Jinja) and the exports (``export``) read the same functions, so what is on the screen is
what is on paper and in the spreadsheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.core.export_document import Tone, ValueKind, format_value
from src.core.money import format_brl
from src.modulos.governanca import models
from src.modulos.governanca.service import (
    SITUATION_GROUP_ANALYSIS,
    SITUATION_GROUP_APPROVED,
    RegisterOverview,
)

NO_VALUE = "·"
TO_ANALYSE = "a analisar"

# The situation of a change as a person reads it: the tone of the pill on screen and of the cell on paper.
SITUATION_TONES: dict[str, Tone] = {
    models.SITUATION_REGISTERED: Tone.NEUTRAL,
    models.SITUATION_ANALYSIS: Tone.INFO,
    models.SITUATION_AWAITING: Tone.WARN,
    models.SITUATION_APPROVED: Tone.OK,
    models.SITUATION_APPROVED_WITH_CONDITIONS: Tone.OK,
    models.SITUATION_REJECTED: Tone.ERROR,
    models.SITUATION_POSTPONED: Tone.WARN,
    models.SITUATION_IMPLEMENTING: Tone.INFO,
    models.SITUATION_CLOSED: Tone.NEUTRAL,
    models.SITUATION_CANCELLED: Tone.NEUTRAL,
}

# The pill classes of the Design System by tone (``pill--ok``, ``pill--fix``...).
PILL_BY_TONE: dict[Tone, str] = {
    Tone.OK: "pill--ok",
    Tone.WARN: "pill--warn",
    Tone.ERROR: "pill--erro",
    Tone.INFO: "pill--fix",
    Tone.NEUTRAL: "pill--neutral",
}

_MILLION = 1_000_000
_BILLION = 1_000_000_000
_THOUSAND = 1_000


def situation_tone(situation: str) -> Tone:
    """The tone of a situation; an unknown one reads as neutral."""
    return SITUATION_TONES.get(situation, Tone.NEUTRAL)


def situation_pill(situation: str) -> str:
    """The pill class of a situation."""
    return PILL_BY_TONE[situation_tone(situation)]


def priority_pill(priority: str) -> str:
    """The pill class of a priority: Emergencial is an error, Urgente a warning, Normal is plain."""
    if priority == models.PRIORITY_EMERGENCY:
        return PILL_BY_TONE[Tone.ERROR]
    return (
        PILL_BY_TONE[Tone.WARN]
        if priority != models.PRIORITY_NORMAL
        else PILL_BY_TONE[Tone.NEUTRAL]
    )


def cost_text(cost_cents: int | None) -> str:
    """The cost impact: ``a analisar`` before the analysis, ``R$ 0``, ``+R$ 400.000,00`` or a reduction."""
    if cost_cents is None:
        return TO_ANALYSE
    if cost_cents == 0:
        return "R$ 0"
    sign = "+" if cost_cents > 0 else "-"
    return f"{sign}{format_brl(abs(cost_cents))}"


def term_text(term_days: int | None) -> str:
    """The term impact in days: ``a analisar``, ``0 dias``, ``+21 dias`` or ``-15 dias``."""
    if term_days is None:
        return TO_ANALYSE
    if term_days == 0:
        return "0 dias"
    sign = "+" if term_days > 0 else "-"
    return f"{sign}{plural(abs(term_days), 'dia')}"


def plural(count: int, singular: str, plural_text: str | None = None) -> str:
    """``1 dia``, ``2 dias``: the count with the noun in the right number."""
    noun = singular if count == 1 else (plural_text or f"{singular}s")
    return f"{format_value(ValueKind.INTEGER, count)} {noun}"


def compact_brl(cents: int | None) -> str:
    """The money in compact form as the cards read it: ``R$ 44,6 mi``, ``R$ 12 mil``, ``R$ 950``."""
    if cents is None:
        return NO_VALUE
    reais = Decimal(cents) / 100
    for limit, suffix in ((_BILLION, "bi"), (_MILLION, "mi"), (_THOUSAND, "mil")):
        if abs(reais) >= limit:
            return f"R$ {_one_decimal(reais / limit)} {suffix}"
    return f"R$ {_one_decimal(reais)}"


def _one_decimal(value: Decimal) -> str:
    text = f"{value:.1f}".replace(".", ",")
    return text.removesuffix(",0")


def percent_text(value: Decimal | None) -> str:
    """A percentage with one decimal place (``2,7%``), or the dot when there is no budget."""
    return NO_VALUE if value is None else format_value(ValueKind.PERCENT, value, digits=1)


@dataclass(frozen=True)
class KpiCard:
    """A KPI of the Registro de mudanças as the card and the export print it."""

    label: str
    value: str
    unit: str
    icon: str
    tone: Tone
    reference: str
    footer: str
    filter_value: str | None = None


def kpi_cards(overview: RegisterOverview) -> list[KpiCard]:
    """The six KPIs of the register, each read against its management reference.

    The first three are read against the counts of the scope; the approved value against the budget; the
    term against zero; the mean decision time against the mean of the whole portfolio.
    """
    return [
        _analysis_card(overview),
        _committee_card(overview),
        _approved_card(overview),
        _value_card(overview),
        _term_card(overview),
        _decision_time_card(overview),
    ]


def _count_text(count: int) -> str:
    return format_value(ValueKind.INTEGER, count)


def _analysis_card(overview: RegisterOverview) -> KpiCard:
    summary = overview.summary
    overdue = summary.overdue_analysis
    return KpiCard(
        label="Em análise",
        value=_count_text(summary.in_analysis),
        unit="",
        icon="search",
        tone=Tone.ERROR if overdue else Tone.INFO,
        reference=f"Referência: {_count_text(summary.total)}",
        footer=(
            plural(overdue, "análise vencida", "análises vencidas")
            if overdue
            else "registradas e em análise de impacto"
        ),
        filter_value=SITUATION_GROUP_ANALYSIS,
    )


def _committee_card(overview: RegisterOverview) -> KpiCard:
    summary = overview.summary
    waiting = summary.awaiting_committee
    return KpiCard(
        label="Aguardando comitê",
        value=_count_text(waiting),
        unit="",
        icon="taskList",
        tone=Tone.WARN if waiting else Tone.OK,
        reference=f"Referência: {_count_text(summary.total)}",
        footer=plural(summary.postponed, "adiada") if summary.postponed else "decisão pendente",
        filter_value=models.SITUATION_AWAITING,
    )


def _approved_card(overview: RegisterOverview) -> KpiCard:
    summary = overview.summary
    implementing = summary.implementing
    return KpiCard(
        label=f"Aprovadas em {summary.year}",
        value=_count_text(summary.approved_in_year),
        unit="",
        icon="checkCircle",
        tone=Tone.OK,
        reference=f"Referência: {_count_text(summary.approved)}",
        footer=(
            f"{_count_text(implementing)} em implementação"
            if implementing
            else "nenhuma em implementação"
        ),
        filter_value=SITUATION_GROUP_APPROVED,
    )


def _value_card(overview: RegisterOverview) -> KpiCard:
    summary = overview.summary
    return KpiCard(
        label="Valor aprovado acumulado",
        value=format_brl(summary.approved_value_cents),
        unit="",
        icon="money",
        tone=Tone.INFO,
        reference=f"Orçado: {compact_brl(overview.budget_cents)}",
        footer=f"{percent_text(summary.approved_value_percent)} do orçamento",
    )


def _term_card(overview: RegisterOverview) -> KpiCard:
    days = overview.summary.approved_term_days
    sign = "+" if days > 0 else ""
    return KpiCard(
        label="Impacto de prazo acumulado",
        value=f"{sign}{_count_text(days)}",
        unit="dias",
        icon="calendar",
        tone=Tone.WARN if days > 0 else Tone.OK,
        reference="Esperado: 0",
        footer="no caminho crítico, mudanças aprovadas",
    )


def _decision_time_card(overview: RegisterOverview) -> KpiCard:
    summary = overview.summary
    mean = summary.mean_decision_days
    reference = overview.portfolio_mean_decision_days
    pending = summary.pending_emergencies
    footer = "da solicitação à decisão"
    if pending:
        footer += " · " + plural(
            pending, "emergencial sem ratificação", "emergenciais sem ratificação"
        )
    return KpiCard(
        label="Tempo médio de decisão",
        value=NO_VALUE if mean is None else _count_text(mean),
        unit="" if mean is None else "dias",
        icon="clock",
        tone=Tone.INFO,
        reference=f"Referência: {NO_VALUE if reference is None else _count_text(reference)}",
        footer=footer,
    )
