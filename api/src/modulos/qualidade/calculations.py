"""Pure calculations of the Quality module: the vocabulary and the rules of the RNC (ISSUE-068).

Every formula here is pure and receives the reference date as an argument (D6): nothing reads
the clock. The deadline of the treatment comes from the severity and the parameters in force
(``prazoTratamentoDias``); the situation decides whether the report is active, in treatment,
overdue and what the next step is. The recurrence is not a column: it is counted from the
audit trail of the record, where each ineffective verification left the fact (D5b).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

SITUATION_OPEN = "Aberta"
SITUATION_ANALYSIS = "Em análise de causa"
SITUATION_ACTION = "Ação corretiva"
SITUATION_VERIFICATION = "Verificação de eficácia"
SITUATION_CLOSED = "Encerrada"
SITUATION_CANCELLED = "Cancelada"

SITUATIONS: tuple[str, ...] = (
    SITUATION_OPEN,
    SITUATION_ANALYSIS,
    SITUATION_ACTION,
    SITUATION_VERIFICATION,
    SITUATION_CLOSED,
    SITUATION_CANCELLED,
)
TREATMENT_SITUATIONS = frozenset({SITUATION_OPEN, SITUATION_ANALYSIS, SITUATION_ACTION})
ACTIVE_SITUATIONS = frozenset(SITUATIONS[:4])
CANCELLABLE_SITUATIONS = frozenset({SITUATION_OPEN, SITUATION_ANALYSIS})

SEVERITIES: tuple[str, ...] = ("Crítica", "Maior", "Menor")
SEVERITY_KEYS: Mapping[str, str] = {"Crítica": "critica", "Maior": "maior", "Menor": "menor"}

ORIGINS: tuple[str, ...] = (
    "Inspeção",
    "Inspeção de fabricação",
    "Auditoria",
    "Fornecedor",
    "Processo",
    "Cliente",
)
DISPOSITIONS: tuple[str, ...] = (
    "Retrabalho",
    "Reparo",
    "Usar como está",
    "Rejeitar",
    "Reclassificar",
)
DISPOSITIONS_WITH_CONCESSION: tuple[str, ...] = ("Reparo", "Usar como está")
METHODS: tuple[str, ...] = ("5 porquês", "Diagrama de Ishikawa", "Árvore de causas")

NEXT_STEPS: Mapping[str, str] = {
    SITUATION_OPEN: "Atribuir a análise de causa",
    SITUATION_ANALYSIS: "Registrar causa raiz, disposição e ações",
    SITUATION_ACTION: "Concluir as ações e enviar para verificação",
    SITUATION_VERIFICATION: "Verificar a eficácia",
    SITUATION_CLOSED: "",
    SITUATION_CANCELLED: "",
}


def treatment_deadline(start: date, severity: str, treatment_days: Mapping[str, int]) -> date:
    """The treatment deadline: the start date plus the days of the severity (parameters)."""
    return start + timedelta(days=treatment_days[SEVERITY_KEYS[severity]])


def is_active(situation: str) -> bool:
    """Whether the RNC is still in the active flow (not closed nor cancelled)."""
    return situation in ACTIVE_SITUATIONS


def is_in_treatment(situation: str) -> bool:
    """Whether the deadline of the treatment still applies (from Aberta to Ação corretiva)."""
    return situation in TREATMENT_SITUATIONS


def is_overdue(deadline: date, situation: str, reference_date: date) -> bool:
    """Whether the treatment deadline passed while the RNC is still in treatment."""
    return is_in_treatment(situation) and deadline < reference_date


def days_overdue(deadline: date, situation: str, reference_date: date) -> int:
    """How many days the treatment deadline is overdue; zero when it is not."""
    if not is_overdue(deadline, situation, reference_date):
        return 0
    return (reference_date - deadline).days


def is_verification_overdue(
    situation: str, verification_expected: date | None, reference_date: date
) -> bool:
    """Whether the effectiveness verification is overdue (waiting and expected before today)."""
    if situation != SITUATION_VERIFICATION or verification_expected is None:
        return False
    return verification_expected < reference_date


def days_open(rnc_date: date, closing_date: date | None, reference_date: date) -> int:
    """How long the RNC has been open: from its date to the closing, or to the reference."""
    return ((closing_date or reference_date) - rnc_date).days


def next_step(situation: str) -> str:
    """What the flow waits for next, as the screen writes it; empty when the RNC is done."""
    return NEXT_STEPS.get(situation, "")


def recurrence_count(
    transitions: Iterable[tuple[Mapping[str, object] | None, Mapping[str, object] | None]],
) -> int:
    """How many ineffective verifications the RNC had, counted from its audit trail (D5b).

    Each ineffective verification is the only step that returns the report from the
    effectiveness check to the corrective action, so each such transition counts one; later
    updates while it stays in the corrective action do not count again.
    """
    return sum(
        1
        for before, after in transitions
        if after
        and after.get("situacao") == SITUATION_ACTION
        and before is not None
        and before.get("situacao") == SITUATION_VERIFICATION
    )


def average_treatment_days(days: Iterable[int]) -> int | None:
    """The mean treatment time of the closed RNCs, rounded half up (the prototype's rule)."""
    values = list(days)
    if not values:
        return None
    mean = Decimal(sum(values)) / Decimal(len(values))
    return int(mean.quantize(Decimal(1), rounding=ROUND_HALF_UP))
