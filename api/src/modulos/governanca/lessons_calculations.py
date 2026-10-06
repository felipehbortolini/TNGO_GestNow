"""Pure rules of the lessons learned (ISSUE-027): visibility, search, order, actions and drafts.

Every function is a business rule with a name; none reads the clock or the database. The reference date
and the facts come as arguments, so each rule has a test with its boundary.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.core.import_values import normalize_text
from src.modulos.governanca import calculations
from src.modulos.governanca import lessons_models as lm

KEYWORD_SEPARATORS = re.compile(r"[,;]")
KEYWORDS_MAXIMUM = 8
RECOMMENDATION_MINIMUM = 20
PANEL_TOP_REUSED = 5

# The words the prototype wrote in the free text of the origin, and the origin each one stands for.
ORIGIN_BY_WORD = {
    "Ata": lm.ORIGIN_MINUTES,
    "Punch": lm.ORIGIN_PUNCH,
    "Contrato": lm.ORIGIN_CONTRACT,
    "Claim": lm.ORIGIN_CONTRACT,
    "Avaliação": lm.ORIGIN_CONTRACT,
    "Suprimentos": lm.ORIGIN_SUPPLY,
    "Processo": lm.ORIGIN_SUPPLY,
    "Pedido": lm.ORIGIN_SUPPLY,
    "Risco": lm.ORIGIN_RISK,
    "RNC": lm.ORIGIN_NCR,
    "Ocorrência": lm.ORIGIN_HSE,
    "Mudança": lm.ORIGIN_CHANGE,
    "Workshop": lm.ORIGIN_WORKSHOP,
    "Encerramento": lm.ORIGIN_CLOSING,
}
ORIGIN_LABELS = {
    lm.ORIGIN_MINUTES: "Ata (01)",
    lm.ORIGIN_PUNCH: "Punch list (02)",
    lm.ORIGIN_CONTRACT: "Contrato ou claim (03)",
    lm.ORIGIN_SUPPLY: "Suprimentos (04)",
    lm.ORIGIN_RISK: "Risco encerrado (05)",
    lm.ORIGIN_NCR: "RNC (06)",
    lm.ORIGIN_HSE: "Ocorrência HSE (07)",
    lm.ORIGIN_CHANGE: "Mudança (08)",
}
# The knowledge area each type of change teaches (the lesson born at the closing of an SM).
AREA_BY_CHANGE_TYPE = {
    "Escopo": "Escopo",
    "Prazo": "Cronograma",
    "Custo": "Custos",
    "Qualidade/Especificação": "Qualidade",
    "Contratual": "Aquisições",
    "Remanejamento de orçamento": "Custos",
    "Liberação de reserva": "Custos",
}
DEFAULT_CHANGE_AREA = "Escopo"
_REFERENCE = re.compile(r"^(?P<word>.*?)\s+(?P<ref>[A-Z]{2,}-[A-Z0-9-]*\d)$")
_SITUATION_ORDER = {
    lm.SITUATION_PUBLISHED: 0,
    lm.SITUATION_VALIDATED: 1,
    lm.SITUATION_VALIDATING: 2,
    lm.SITUATION_DRAFT: 3,
}


def origin_label(origin: str) -> str:
    """How the screen names an origin: the module origins carry the number of their module."""
    return ORIGIN_LABELS.get(origin, origin)


def origin_of_text(text: str) -> tuple[str, str | None]:
    """The origin and the reference of the free text of the prototype (``Claim CLM-TN-2026-0004``)."""
    stripped = (text or "").strip()
    found = _REFERENCE.match(stripped)
    word = found.group("word") if found else stripped
    reference = found.group("ref") if found else None
    origin = ORIGIN_BY_WORD.get(word.split(" ")[0] if word else "", lm.ORIGIN_DIRECT)
    if reference is None and origin in lm.MODULE_ORIGINS:
        return lm.ORIGIN_DIRECT, None
    return origin, reference


def is_module_origin(origin: str) -> bool:
    """Whether the origin points to a record of another module, whose number is required."""
    return origin in lm.MODULE_ORIGINS


def parse_keywords(raw: str | None) -> list[str]:
    """The keywords of the field: separated by comma or semicolon, trimmed, blanks dropped."""
    return [word.strip() for word in KEYWORD_SEPARATORS.split(raw or "") if word.strip()]


def is_lesson_visible(
    *, lesson_project_id: int, applicability: str, situation: str, scope_project_id: int | None
) -> bool:
    """Whether the lesson belongs to the acervo of the scope.

    The Portfólio (no project) sees every lesson. A project sees its own, whatever the situation,
    and the lessons of other projects only when they are published as Corporativa.
    """
    if scope_project_id is None or lesson_project_id == scope_project_id:
        return True
    return situation == lm.SITUATION_PUBLISHED and applicability == lm.APPLICABILITY_CORPORATE


def search_matches(query: str | None, text: str) -> bool:
    """Whether every word of the query is in the text, ignoring case and accents."""
    words = normalize_text(query or "").split()
    target = normalize_text(text)
    return all(word in target for word in words)


def lesson_order_key(situation: str, registered_on: date) -> tuple[int, int]:
    """The order of the acervo: published first, then validated, in validation, draft; newest first."""
    return (_SITUATION_ORDER.get(situation, len(_SITUATION_ORDER)), -registered_on.toordinal())


def can_edit_draft(*, situation: str, is_author: bool, can_write: bool, can_manage: bool) -> bool:
    """Only a draft is edited or sent, and only by its author (with write) or by a Gestor."""
    return situation == lm.SITUATION_DRAFT and (can_manage or (can_write and is_author))


@dataclass(frozen=True)
class LessonActions:
    """What the user may do with a lesson now: the buttons of the card and of the sheet."""

    send: bool
    edit: bool
    validate: bool
    publish: bool
    apply: bool


def lesson_actions(
    situation: str, *, is_author: bool, can_write: bool, can_manage: bool
) -> LessonActions:
    """The actions open to the user: who validates is a Gestor who is not the author (segregation)."""
    editable = can_edit_draft(
        situation=situation, is_author=is_author, can_write=can_write, can_manage=can_manage
    )
    return LessonActions(
        send=editable,
        edit=editable,
        validate=situation == lm.SITUATION_VALIDATING and can_manage and not is_author,
        publish=situation == lm.SITUATION_VALIDATED and can_manage,
        apply=situation == lm.SITUATION_PUBLISHED and can_write,
    )


def is_ready_to_send(*, recommendation: str, has_discipline: bool) -> bool:
    """Whether a draft is complete enough to go to validation: discipline and a 20-character recommendation."""
    return has_discipline and len(recommendation.strip()) >= RECOMMENDATION_MINIMUM


def next_application_item(items_so_far: int) -> str:
    """The item number of the next action a lesson generates in the Central: one more than so far."""
    return str(items_so_far + 1)


@dataclass(frozen=True)
class ChangeLessonDraft:
    """The text of the lesson born at the closing of an SM, as the prototype wrote it."""

    area: str
    what_happened: str
    cause: str
    keywords: tuple[str, ...]
    term_days: int
    cost_cents: int


@dataclass(frozen=True)
class ChangeFacts:
    """What the closing of an SM tells the lesson: its text, type, origin and approved impact."""

    title: str
    description: str
    kind: str
    origin: str
    term_days: int | None
    cost_cents: int | None


def lesson_draft_for_change(change: ChangeFacts) -> ChangeLessonDraft:
    """The facts of the draft lesson of a closed SM: area by type, impacts never below zero."""
    return ChangeLessonDraft(
        area=AREA_BY_CHANGE_TYPE.get(change.kind, DEFAULT_CHANGE_AREA),
        what_happened=f"{change.title}. {change.description}",
        cause=f"Mudança {change.kind.lower()} de origem {change.origin.lower()}.",
        keywords=(change.kind, change.origin, "mudança"),
        term_days=max(0, change.term_days or 0),
        cost_cents=max(0, change.cost_cents or 0),
    )


@dataclass(frozen=True)
class AcervoCounts:
    """The line over the acervo: the lessons of the scope and how many are shared with the organization."""

    own: int
    corporate: int


def acervo_counts(lessons: list[tuple[int, str]], *, scope_project_id: int | None) -> AcervoCounts:
    """Own lessons (all of them in the Portfólio) and the Corporativa ones, among the visible lessons.

    ``lessons`` holds ``(project id, applicability)`` of each lesson visible in the scope.
    """
    own = sum(
        1 for project_id, _ in lessons if scope_project_id is None or project_id == scope_project_id
    )
    corporate = sum(
        1 for _, applicability in lessons if applicability == lm.APPLICABILITY_CORPORATE
    )
    return AcervoCounts(own=own, corporate=corporate)


def published_by_phase(lessons: list[tuple[str, str]]) -> dict[str, int]:
    """The kickoff checklist: published lessons of each phase, every phase present (zero when none).

    ``lessons`` holds ``(phase, situation)`` of each lesson visible in the scope.
    """
    counts = dict.fromkeys(lm.LESSON_PHASES, 0)
    for phase, situation in lessons:
        if situation == lm.SITUATION_PUBLISHED and phase in counts:
            counts[phase] += 1
    return counts


# ── Painel do acervo (ISSUE-028) ─────────────────────────────────────────


def days_since_last(last_registered_on: date | None, reference_date: date) -> int | None:
    """Dias desde a última lição do escopo; ``None`` quando ainda não há lição."""
    if last_registered_on is None:
        return None
    return (reference_date - last_registered_on).days


def is_registration_alert(
    last_registered_on: date | None, reference_date: date, alert_days: int
) -> bool:
    """O alerta do parâmetro: sem lição, ou a última há mais de ``alert_days`` dias.

    A fronteira é do protótipo (``ultima < REF - dias``): exatamente ``alert_days`` dias atrás
    ainda não é alerta.
    """
    if last_registered_on is None:
        return True
    return (reference_date - last_registered_on).days > alert_days


def reuse_rate(*, published: int, reused: int) -> Decimal | None:
    """Taxa de reuso: publicadas com aplicação registrada sobre as publicadas; ``None`` sem publicada."""
    if not published:
        return None
    return (Decimal(reused) * calculations.PERCENT / Decimal(published)).quantize(
        calculations.ONE_TENTH, rounding=ROUND_HALF_UP
    )


@dataclass(frozen=True)
class LessonGroupLine:
    """Uma linha do painel por fase ou por área: total, os dois tipos e as publicadas."""

    label: str
    total: int
    to_repeat: int
    to_avoid: int
    published: int


def lines_by_phase(facts: Iterable[tuple[str, str, str]]) -> tuple[LessonGroupLine, ...]:
    """Lições por fase, na ordem do vocabulário; a fase sem lição fica zerada (checklist).

    ``facts`` holds ``(phase, kind, situation)`` of each lesson visible in the scope.
    """
    return tuple(_group_lines(facts, lm.LESSON_PHASES))


def lines_by_area(facts: Iterable[tuple[str, str, str]]) -> tuple[LessonGroupLine, ...]:
    """Lições por área: só as áreas com lição, da maior para a menor (empate na ordem do vocabulário)."""
    position = {label: index for index, label in enumerate(lm.LESSON_AREAS)}
    filled = [line for line in _group_lines(facts, lm.LESSON_AREAS) if line.total]
    return tuple(sorted(filled, key=lambda line: (-line.total, position[line.label])))


def _group_lines(
    facts: Iterable[tuple[str, str, str]], order: Sequence[str]
) -> list[LessonGroupLine]:
    counts: dict[str, list[int]] = {label: [0, 0, 0, 0] for label in order}
    for label, kind, situation in facts:
        if label not in counts:
            continue
        line = counts[label]
        line[0] += 1
        if kind == lm.LESSON_TYPES[0]:
            line[1] += 1
        elif kind == lm.LESSON_TYPES[1]:
            line[2] += 1
        if situation == lm.SITUATION_PUBLISHED:
            line[3] += 1
    return [LessonGroupLine(label, *counts[label]) for label in order]


def projects_without_record(
    *,
    records: Mapping[int, date | None],
    project_ids: Iterable[int],
    reference_date: date,
    alert_days: int,
) -> tuple[int, ...]:
    """Os projetos do escopo sem lição registrada na janela do parâmetro (qualquer situação conta).

    ``records`` holds the date of the latest lesson of each project (``None`` when it has none).
    """
    return tuple(
        project_id
        for project_id in project_ids
        if is_registration_alert(records.get(project_id), reference_date, alert_days)
    )
