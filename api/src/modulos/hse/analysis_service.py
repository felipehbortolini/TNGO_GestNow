"""Facade of the risk analyses of HSE: APR/JSA and HAZOP studies and their recommendations (ISSUE-074).

A study has a code, a type, an area, a date, participants and recommendations (responsible,
deadline, status). Every write goes through ``core.recording``; the module never reads a table of
another module (D9):

* a recommendation becomes an action of the Central by ``create_recommendation_action``: origin
  ``HSE``, reference the code of the study and item the number of the recommendation; the link
  back to the study is resolved by ``origin_links`` (``hse.origins``);
* the status stays in step both ways, inside one transaction: closing the recommendation here
  completes its action (``close_from_origin``), and completing the action in the Central closes
  the recommendation (the reaction of the origin ``HSE``); a replanned action moves the deadline of
  the recommendation;
* ``list_analyses`` and ``find_analysis`` read the studies; the indicator *recommendations closed
  over issued* is ``calculations.recommendations_closed_rate``.

Nothing here reads the clock: the routes obtain the date from ``core.calendario``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import numbering, origin_links, rbac, recording
from src.core.errors import InvalidDataError
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.models import Action
from src.modulos.central_acoes.origins import ActionEvent
from src.modulos.central_acoes.validation import NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, origins, validation
from src.modulos.hse.calculations import (
    RECOMMENDATION_CLOSED,
    RecommendationCounts,
)
from src.modulos.hse.models import RiskAnalysis, RiskAnalysisParticipant, RiskRecommendation
from src.modulos.hse.service import Names, names_of, register_choices
from src.modulos.hse.validation import AnalysisInput, ClosingRecommendationInput

ORIGIN = origins.ORIGIN
CODE_PREFIXES = ("APR-", "HAZOP-")
NOT_FOUND = "Estudo não encontrado."
RECOMMENDATION_NOT_FOUND = "Recomendação não encontrada."
ACTION_EXISTS = "Já existe uma ação na Central para esta recomendação."
UNKNOWN_PROJECT = "O projeto informado não existe."


@dataclass(frozen=True)
class AnalysisSaved:
    """What a save of a study did: its id and the code it received."""

    id: int
    code: str


@dataclass(frozen=True)
class RecommendationRef:
    """One recommendation of one study: the code of the study and the number of the item."""

    code: str
    position: int


@dataclass(frozen=True)
class RecommendationRow:
    """One recommendation as the screen reads it, with its action of the Central when it has one."""

    id: int
    position: int
    description: str
    responsible_id: int
    responsible_name: str
    due_date: date
    status: str
    closed_on: date | None
    evidence: str
    overdue: bool
    version: int
    action_id: int | None = None
    action_status: str = ""


@dataclass(frozen=True)
class AnalysisRow:
    """One study with its participants, recommendations and the count of the recommendations."""

    id: int
    project_id: int
    project_label: str
    code: str
    kind: str
    area: str
    title: str
    studied_on: date
    participant_ids: tuple[int, ...]
    participant_names: tuple[str, ...]
    recommendations: tuple[RecommendationRow, ...]
    counts: RecommendationCounts
    version: int


@dataclass(frozen=True)
class AnalysisFilter:
    """What the list may be cut by: the type, a search text and only the studies with open items."""

    kind: str = ""
    search: str = ""
    only_open: bool = False


@dataclass(frozen=True)
class AnalysisListing:
    """The studies of the scope that pass the filter, the size of the universe and the totals."""

    rows: tuple[AnalysisRow, ...]
    universe: int
    counts: RecommendationCounts

    @property
    def closed_rate(self) -> Decimal | None:
        """Recommendations closed over issued of the studies listed, in percent, or ``None``."""
        return calculations.recommendations_closed_rate(self.counts.closed, self.counts.issued)


def normalize(text: str) -> str:
    """The text without accents, in lower case and trimmed: how the search compares."""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def is_analysis_code(reference: str) -> bool:
    """Whether the reference of an origin ``HSE`` names a risk analysis (APR or HAZOP)."""
    return reference.startswith(CODE_PREFIXES)


# ── Writing ──────────────────────────────────────────────────────────────────────────────────


def reserve_code(session: Session, *, project_id: int, kind: str, reference_date: date) -> str:
    """The next code of the type in the project: the numbering lock, then the highest suffix."""
    project = configuracoes.find_project(session, project_id)
    if project is None:
        raise InvalidDataError({"projeto": UNKNOWN_PROJECT})
    reserved = numbering.next_number(
        session, project=project, kind=kind.lower(), reference_date=reference_date
    )
    prefix, _, digits = reserved.rpartition("-")
    codes = session.scalars(select(RiskAnalysis.code).where(RiskAnalysis.code.like(f"{prefix}-%")))
    suffixes = [int(code[len(prefix) + 1 :]) for code in codes if code[len(prefix) + 1 :].isdigit()]
    return f"{prefix}-{max(int(digits), *(number + 1 for number in suffixes), 1):04d}"


def save_analysis(
    session: Session, *, user: User, data: AnalysisInput, reference_date: date
) -> AnalysisSaved:
    """Record a study with its participants and recommendations; 422 by field when it fails."""
    rbac.require(user, Permission.WRITE)
    if configuracoes.find_project(session, data.project_id) is None:
        raise InvalidDataError({"projeto": UNKNOWN_PROJECT})
    problems = validation.analysis_problems(
        data, register_choices(session), reference_date=reference_date
    )
    code = (data.code or "").strip()
    if code and session.scalar(select(RiskAnalysis.id).where(RiskAnalysis.code == code)):
        problems["codigo"] = validation.CODE_TAKEN
    if problems or data.studied_on is None:
        raise InvalidDataError(problems)
    analysis = recording.create(
        session,
        user_id=user.id,
        record=RiskAnalysis(
            project_id=data.project_id,
            code=code
            or reserve_code(
                session, project_id=data.project_id, kind=data.kind, reference_date=reference_date
            ),
            kind=data.kind,
            area=data.area.strip(),
            title=data.title.strip(),
            studied_on=data.studied_on,
        ),
    )
    for person_id in dict.fromkeys(data.participant_ids):
        session.add(RiskAnalysisParticipant(analysis_id=analysis.id, person_id=person_id))
    for position, item in enumerate(data.recommendations, start=1):
        _create_recommendation(
            session, user=user, analysis_id=analysis.id, position=position, item=item
        )
    session.flush()
    return AnalysisSaved(id=analysis.id, code=analysis.code)


def _create_recommendation(
    session: Session,
    *,
    user: User,
    analysis_id: int,
    position: int,
    item: validation.RecommendationInput,
) -> None:
    if item.responsible_id is None or item.due_date is None:
        raise InvalidDataError({"recomendacoes": validation.RECOMMENDATIONS_REQUIRED})
    recording.create(
        session,
        user_id=user.id,
        record=RiskRecommendation(
            analysis_id=analysis_id,
            responsible_id=item.responsible_id,
            position=position,
            description=item.description.strip(),
            due_date=item.due_date,
            status=item.status,
            closed_on=item.closed_on,
            evidence=item.evidence.strip() or None,
        ),
    )


def close_recommendation(
    session: Session,
    *,
    user: User,
    target: RecommendationRef,
    data: ClosingRecommendationInput,
    reference_date: date,
) -> None:
    """Close a recommendation and complete its action of the Central, in the same transaction."""
    rbac.require(user, Permission.WRITE)
    analysis, recommendation = _recommendation(session, target.code, target.position)
    problems = validation.recommendation_closing_problems(data, reference_date=reference_date)
    if recommendation.status == RECOMMENDATION_CLOSED:
        problems["geral"] = validation.ALREADY_CLOSED
    if problems or data.closed_on is None:
        raise InvalidDataError(problems)
    recording.update(
        session,
        user_id=user.id,
        record=recommendation,
        changes={
            "status": RECOMMENDATION_CLOSED,
            "closed_on": data.closed_on,
            "evidence": data.evidence.strip() or None,
        },
        version=data.version,
    )
    actions.close_from_origin(
        session,
        user=user,
        origin=origin_links.OriginRef(
            kind=ORIGIN, reference=analysis.code, item=str(target.position)
        ),
        completed_on=data.closed_on,
        reference_date=reference_date,
    )


def create_recommendation_action(
    session: Session, *, user: User, code: str, position: int, reference_date: date
) -> int:
    """Open the action of the Central for a recommendation, with the link back to the study."""
    rbac.require(user, Permission.WRITE)
    analysis, recommendation = _recommendation(session, code, position)
    if str(position) in _action_items(session, user, analysis.code, reference_date):
        raise InvalidDataError({"geral": ACTION_EXISTS})
    created = actions.create_action(
        session,
        user=user,
        new=NewAction(
            project_id=analysis.project_id,
            origin=ORIGIN,
            origin_ref=analysis.code,
            item=str(position),
            group=f"{analysis.kind} · Recomendação",
            subject=recommendation.description,
            description=f"{analysis.title} ({analysis.area})",
            requester_id=user.person_id,
            responsible_id=recommendation.responsible_id,
            planned_date=recommendation.due_date,
            completed_on=recommendation.closed_on,
        ),
        reference_date=reference_date,
    )
    return created.id


def _recommendation(
    session: Session, code: str, position: int
) -> tuple[RiskAnalysis, RiskRecommendation]:
    analysis = session.scalars(select(RiskAnalysis).where(RiskAnalysis.code == code)).one_or_none()
    if analysis is None:
        raise InvalidDataError({"geral": NOT_FOUND})
    recommendation = session.scalars(
        select(RiskRecommendation).where(
            RiskRecommendation.analysis_id == analysis.id, RiskRecommendation.position == position
        )
    ).one_or_none()
    if recommendation is None:
        raise InvalidDataError({"geral": RECOMMENDATION_NOT_FOUND})
    return analysis, recommendation


def _action_items(session: Session, user: User, code: str, reference_date: date) -> set[str]:
    found = actions.list_actions_of_origin(
        session, user=user, origin_kind=ORIGIN, reference=code, reference_date=reference_date
    )
    return {item.item for item in found if item.item}


# ── The Central tells the study what happened to the action ─────────────────────────────────


def react_to_action(session: Session, user: User, action: Action, event: ActionEvent) -> bool:
    """An action of a recommendation was completed or replanned in the Central: follow it.

    Returns ``False`` when the action is not of a risk analysis. A completed action closes the
    recommendation on the date it was completed; a replanned one moves the deadline. A recommendation
    that is already closed is left as it is.
    """
    code = action.origin_ref or ""
    if not is_analysis_code(code):
        return False
    if not (action.item or "").isdigit():
        return True
    try:
        _, recommendation = _recommendation(session, code, int(action.item or "0"))
    except InvalidDataError:
        return True
    if recommendation.status == RECOMMENDATION_CLOSED:
        return True
    changes: dict[str, object] = {}
    if event is ActionEvent.COMPLETED and action.completed_on is not None:
        changes = {"status": RECOMMENDATION_CLOSED, "closed_on": action.completed_on}
    elif event is ActionEvent.REPLANNED and action.replanned_date is not None:
        changes = {"due_date": action.replanned_date}
    if changes:
        recording.update(
            session,
            user_id=user.id,
            record=recommendation,
            changes=changes,
            version=recommendation.version,
        )
    return True


def _analysis_link(reference: origin_links.OriginRef) -> str | None:
    if not is_analysis_code(reference.reference):
        return None
    return origin_links.link_to_screen("hse/analises_risco", busca=reference.reference)


origins.register_action_handler(react_to_action)
origins.register_link_builder(_analysis_link)


# ── Reading ──────────────────────────────────────────────────────────────────────────────────


def _recommendation_row(
    row: RiskRecommendation, names: Names, reference_date: date
) -> RecommendationRow:
    return RecommendationRow(
        id=row.id,
        position=row.position,
        description=row.description,
        responsible_id=row.responsible_id,
        responsible_name=names.person(row.responsible_id),
        due_date=row.due_date,
        status=row.status,
        closed_on=row.closed_on,
        evidence=row.evidence or "",
        overdue=calculations.is_recommendation_overdue(row.status, row.due_date, reference_date),
        version=row.version,
    )


def _rows_of(
    session: Session, analyses: Sequence[RiskAnalysis], names: Names, reference_date: date
) -> list[AnalysisRow]:
    ids = [item.id for item in analyses]
    recommendations = session.scalars(
        select(RiskRecommendation)
        .where(RiskRecommendation.analysis_id.in_(ids))
        .order_by(RiskRecommendation.analysis_id, RiskRecommendation.position)
    ).all()
    participants = session.scalars(
        select(RiskAnalysisParticipant)
        .where(RiskAnalysisParticipant.analysis_id.in_(ids))
        .order_by(RiskAnalysisParticipant.id)
    ).all()
    return [
        _analysis_row(
            item,
            names,
            reference_date,
            [row for row in recommendations if row.analysis_id == item.id],
            [row.person_id for row in participants if row.analysis_id == item.id],
        )
        for item in analyses
    ]


def _analysis_row(
    item: RiskAnalysis,
    names: Names,
    reference_date: date,
    recommendations: Iterable[RiskRecommendation],
    participant_ids: Collection[int],
) -> AnalysisRow:
    lines = tuple(_recommendation_row(row, names, reference_date) for row in recommendations)
    return AnalysisRow(
        id=item.id,
        project_id=item.project_id,
        project_label=names.project(item.project_id),
        code=item.code,
        kind=item.kind,
        area=item.area,
        title=item.title,
        studied_on=item.studied_on,
        participant_ids=tuple(participant_ids),
        participant_names=tuple(names.person(person_id) for person_id in participant_ids),
        recommendations=lines,
        counts=calculations.count_recommendations(
            ((line.status, line.due_date) for line in lines), reference_date
        ),
        version=item.version,
    )


def _matches(row: AnalysisRow, filters: AnalysisFilter) -> bool:
    if filters.kind and row.kind != filters.kind:
        return False
    if filters.only_open and not row.counts.open:
        return False
    text = normalize(filters.search)
    haystack = normalize(f"{row.code} {row.title} {row.area}")
    return not text or text in haystack


def list_analyses(
    session: Session, *, scope: Scope, filters: AnalysisFilter, reference_date: date
) -> AnalysisListing:
    """The studies of the scope, the most recent first, with the totals of their recommendations."""
    statement = select(RiskAnalysis).order_by(
        RiskAnalysis.studied_on.desc(), RiskAnalysis.id.desc()
    )
    if scope.project_id is not None:
        statement = statement.where(RiskAnalysis.project_id == scope.project_id)
    analyses = list(session.scalars(statement))
    rows = _rows_of(session, analyses, names_of(session), reference_date)
    shown = tuple(row for row in rows if _matches(row, filters))
    total = RecommendationCounts()
    for row in shown:
        total = total.plus(row.counts)
    return AnalysisListing(rows=shown, universe=len(rows), counts=total)


def find_analysis(
    session: Session, *, user: User, code: str, reference_date: date
) -> AnalysisRow | None:
    """One study with the action of the Central that each recommendation already has."""
    analysis = session.scalars(select(RiskAnalysis).where(RiskAnalysis.code == code)).one_or_none()
    if analysis is None:
        return None
    row = _rows_of(session, [analysis], names_of(session), reference_date)[0]
    found = {
        item.item: item
        for item in actions.list_actions_of_origin(
            session,
            user=user,
            origin_kind=ORIGIN,
            reference=code,
            reference_date=reference_date,
        )
        if item.item
    }
    lines = tuple(_with_action(line, found.get(str(line.position))) for line in row.recommendations)
    return AnalysisRow(**{**row.__dict__, "recommendations": lines})


def _with_action(line: RecommendationRow, record: actions.ActionRecord | None) -> RecommendationRow:
    if record is None:
        return line
    return RecommendationRow(
        **{**line.__dict__, "action_id": record.id, "action_status": record.status_label}
    )
