"""Business facade of the Governança module: the register of changes (SM), the ficha and the cancellation.

Everything the routes and the seed ask of the module goes through here (D5, D9): reading needs the
module and writing needs the Membro permission; every write goes through ``core.recording`` (trail,
version and transaction together) and the number of a new change through ``core.numbering``. A module
never reads these tables directly. Nothing here reads the clock: the caller passes the reference date,
taken from ``core.calendario`` at the edge of the route.

What this slice (ISSUE-023) writes is the request and its cancellation. The analysis, the decision and
the implementation are written by ISSUE-024 and ISSUE-025; this slice only reads them for the ficha.
The points where other modules enter are marked where they will be wired (D9): the open actions of the
implementation (Central de Ações, ISSUE-025), the EAC items and reallocations (Financeiro) and the
revision of the EAP (Planejamento).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import attachment_origins, numbering, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.import_values import normalize_text
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import calculations, models, validation
from src.modulos.governanca.calculations import (
    ChangeFigures,
    ChangeSummary,
    HistoryFacts,
    HistoryLine,
    NextStepFacts,
)
from src.modulos.governanca.models import (
    ChangeAnalysis,
    ChangeDecision,
    ChangeDecisionParticipant,
    ChangeImpact,
    ChangeRequest,
)

MODULE = "governanca"
NUMBERING_KIND = "mudanca"
ORIGIN_TABLE = "mudanca"

PARAMETER_GROUP = "mudancas"
DEFAULT_PARAMETERS: dict[str, Any] = {
    "alcadaGerentePctOrcamento": 1,
    "prazoAnaliseDias": 10,
    "quorumComite": 3,
    "prazoAcoesDias": 15,
    "ratificacaoDias": 7,
}

SITUATION_GROUP_OPEN = "abertas"
SITUATION_GROUP_ANALYSIS = "em-analise"
SITUATION_GROUP_APPROVED = "aprovadas"
SITUATION_GROUPS = (SITUATION_GROUP_OPEN, SITUATION_GROUP_ANALYSIS, SITUATION_GROUP_APPROVED)

NOT_FOUND_MESSAGE = "Solicitação de mudança não encontrada."
CANCEL_DENIED_MESSAGE = "Só o solicitante ou um Gestor pode cancelar a solicitação."
CANCEL_DECIDED_MESSAGE = "Mudança já decidida não pode ser cancelada"
CANCEL_REVERT_HINT = ": registre nova SM para reverter."
NOT_FOUND_PROJECT_MESSAGE = "Projeto não encontrado."


@dataclass(frozen=True)
class ChangeFilter:
    """The filters of the register: the situation (a group or one situation), the lists and the text."""

    situation: str | None = None
    kind: str | None = None
    origin: str | None = None
    priority: str | None = None
    authority: str | None = None
    search: str | None = None


@dataclass(frozen=True)
class ChangeRow:
    """One line of the register: what the list shows and the flags that make it an alert."""

    id: int
    project_id: int
    project_label: str
    code: str
    title: str
    request_date: date
    priority: str
    kind: str
    origin: str
    authority: str | None
    cost_cents: int | None
    term_days: int | None
    situation: str
    next_step: str
    closing_date: date | None
    emergency_pending: bool
    ratification_overdue: bool
    analysis_overdue: bool

    @property
    def is_alert(self) -> bool:
        """Whether the line is an alert: an overdue analysis or an overdue ratification."""
        return self.analysis_overdue or self.ratification_overdue


@dataclass(frozen=True)
class RegisterOverview:
    """The register for one scope: the filtered lines, the KPIs and the references they read."""

    rows: tuple[ChangeRow, ...]
    total_in_scope: int
    summary: ChangeSummary
    portfolio_mean_decision_days: int | None
    budget_cents: int | None
    is_portfolio: bool


@dataclass(frozen=True)
class DecisionView:
    """A decision with the names of the people who took part in it."""

    decision: ChangeDecision
    participants: tuple[str, ...]


@dataclass(frozen=True)
class HistoryEntry:
    """A line of the Histórico tab with the name of the person already resolved."""

    moment: datetime
    person_name: str
    text: str


@dataclass(frozen=True)
class ChangeSheet:
    """The ficha of a change: everything the five tabs read, ready to print."""

    change: ChangeRequest
    row: ChangeRow
    project_label: str
    requester_name: str
    stage: int
    final_stage_name: str
    analysis: ChangeAnalysis | None
    analysis_responsible: str
    impact: ChangeImpact | None
    analyst_name: str
    required_authority: str | None
    manager_limit_cents: int | None
    decision: DecisionView | None
    previous_decisions: tuple[DecisionView, ...]
    emergency_start: date | None
    ratification_due: date | None
    closed_by_name: str
    history: tuple[HistoryEntry, ...]
    can_cancel: bool
    possible_duplicate_code: str | None
    pending_eac_revision: bool

    @property
    def is_open(self) -> bool:
        """Whether the change is still open (not rejected, closed or cancelled)."""
        return calculations.is_open(self.change.situation)

    @property
    def is_approved(self) -> bool:
        """Whether the change counts as approved."""
        return calculations.is_approved(self.change.situation)


@dataclass(frozen=True)
class CreatedChange:
    """What the route needs after a request is registered: the code and the project of the ficha."""

    id: int
    code: str
    project_id: int


@dataclass(frozen=True)
class _Loaded:
    """A change with the latest of each of its parts, as the lists and the KPIs read it."""

    change: ChangeRequest
    impact: ChangeImpact | None
    decision: ChangeDecision | None
    analysis: ChangeAnalysis | None


# ── Reading ──────────────────────────────────────────────────────────────


def register_overview(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: ChangeFilter,
    reference_date: date,
) -> RegisterOverview:
    """The Registro de mudanças: lines in the scope after the filters, and the KPIs of the scope."""
    rbac.require_module(user, MODULE)
    projects = {project.id: project for project in configuracoes.list_project_details(session)}
    parameters = _parameters(session, reference_date)
    everything = _load(session)
    in_scope = [item for item in everything if _in_scope(item, scope)]
    rows = [
        _row(item, projects=projects, parameters=parameters, reference_date=reference_date)
        for item in in_scope
    ]
    visible = tuple(
        row for item, row in zip(in_scope, rows, strict=True) if _matches(item, row, filters)
    )
    budget = _scope_budget(scope, projects.values())
    return RegisterOverview(
        rows=visible,
        total_in_scope=len(rows),
        summary=_summary(in_scope, budget_cents=budget, reference_date=reference_date),
        portfolio_mean_decision_days=calculations.mean_decision_days(
            [_figures(item) for item in everything]
        ),
        budget_cents=budget,
        is_portfolio=scope.is_portfolio,
    )


def find_change_sheet(
    session: Session, *, user: User, code: str, reference_date: date
) -> ChangeSheet | None:
    """The ficha of the change with the code, or ``None`` when there is none."""
    rbac.require_module(user, MODULE)
    change = _by_code(session, code)
    if change is None:
        return None
    loaded = _load_one(session, change)
    projects = {project.id: project for project in configuracoes.list_project_details(session)}
    parameters = _parameters(session, reference_date)
    row = _row(loaded, projects=projects, parameters=parameters, reference_date=reference_date)
    decisions = _decision_views(session, change)
    names = _names(session, _sheet_person_ids(loaded))
    required = _required_authority(loaded, projects, parameters)
    return ChangeSheet(
        change=change,
        row=row,
        project_label=row.project_label,
        requester_name=names.get(change.requester_id, ""),
        stage=calculations.change_stage(change.situation),
        final_stage_name=_final_stage_name(change.situation),
        analysis=loaded.analysis,
        analysis_responsible=names.get(loaded.analysis.responsible_id, "")
        if loaded.analysis
        else "",
        impact=loaded.impact,
        analyst_name=names.get(loaded.impact.analyst_id, "") if loaded.impact else "",
        required_authority=required.authority if required else None,
        manager_limit_cents=required.limit_cents if required else None,
        decision=decisions[-1] if decisions else None,
        previous_decisions=tuple(decisions[:-1]),
        emergency_start=_emergency_start(change),
        ratification_due=_ratification_due(change, parameters),
        closed_by_name=names.get(change.closed_by_id, "") if change.closed_by_id else "",
        history=_history(loaded, decisions, names),
        can_cancel=_may_cancel(user, change),
        possible_duplicate_code=_possible_duplicate(session, change),
        pending_eac_revision=_pending_eac_revision(loaded),
    )


def read_change_origin(
    session: Session, *, user: User, record_id: int
) -> attachment_origins.OriginRecord | None:
    """Who may read the attachments of a change: whoever reaches the module (D5a)."""
    rbac.require_module(user, MODULE)
    change = session.get(ChangeRequest, record_id)
    if change is None:
        return None
    return attachment_origins.OriginRecord(project_id=change.project_id)


# ── Writing ──────────────────────────────────────────────────────────────


def create_change(
    session: Session,
    *,
    user: User,
    scope: Scope,
    form: validation.Form,
    reference_date: date,
) -> CreatedChange:
    """Register a request: it gets the number of the project and is born Registrada (HU-125).

    Refused with 403 without the Membro permission and with 422 when the scope is the Portfólio (every
    change belongs to a project) or a field breaks a rule. An emergency marked as executed ahead of the
    decision records its start (in ``data_inicio_implementacao``) and its justification.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    project_id = scope.require_project()
    project = configuracoes.find_project(session, project_id)
    if project is None:
        raise InvalidDataError(NOT_FOUND_PROJECT_MESSAGE)
    new = validation.validate_new_change(form, reference_date=reference_date)
    code = numbering.next_number(
        session, project=project, kind=NUMBERING_KIND, reference_date=reference_date
    )
    change = ChangeRequest(
        project_id=project.id,
        requester_id=user.person_id,
        code=code,
        title=new.title,
        kind=new.kind,
        origin=new.origin,
        priority=new.priority,
        request_date=new.request_date,
        description=new.description,
        situation=models.SITUATION_REGISTERED,
        emergency=new.is_emergency_execution,
        emergency_justification=new.emergency_justification,
        implementation_start=new.emergency_start,
    )
    recording.create(session, user_id=user.id, record=change)
    return CreatedChange(id=change.id, code=code, project_id=project.id)


def cancel_change(
    session: Session,
    *,
    user: User,
    code: str,
    form: validation.Form,
    reference_date: date,
) -> ChangeRequest:
    """Cancel a change before the decision, with a justification (HU-125).

    Only the requester or a Gestor may cancel (403 for everyone else). A change already decided is
    refused (422): it is not cancelled, a new SM is registered to revert it. The cancellation date, the
    person and the justification go to ``data_encerramento``, ``encerrado_por_id`` and
    ``encerramento_observacao``.
    """
    change = cancellable_change(session, user=user, code=code)
    justification = validation.validate_cancellation_justification(form)
    recording.update(
        session,
        user_id=user.id,
        record=change,
        changes={
            "situation": models.SITUATION_CANCELLED,
            "closing_date": reference_date,
            "closed_by_id": user.person_id,
            "closing_note": justification,
        },
        version=form.get(validation.FIELD_VERSION),
    )
    return change


def cancellable_change(session: Session, *, user: User, code: str) -> ChangeRequest:
    """The change the user may cancel now, or the refusal that says why not.

    404 is not a domain error here: an unknown code is 422. Refused with 403 without the Membro
    permission or when the user is neither the requester nor a Gestor, and with 422 after the decision.
    """
    rbac.require_module(user, MODULE)
    change = _by_code(session, code)
    if change is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    rbac.require(user, Permission.WRITE)
    _require_requester_or_manager(user, change)
    if change.situation not in models.CANCELLABLE_SITUATIONS:
        raise InvalidDataError(_not_cancellable_message(change.situation))
    return change


def may_cancel(user: User, change: ChangeRequest) -> bool:
    """Whether the user may cancel the change now: requester or Gestor, and before the decision."""
    return _may_cancel(user, change)


def _may_cancel(user: User, change: ChangeRequest) -> bool:
    return (
        change.situation in models.CANCELLABLE_SITUATIONS
        and rbac.can(user, Permission.WRITE)
        and _is_requester_or_manager(user, change)
    )


def _is_requester_or_manager(user: User, change: ChangeRequest) -> bool:
    return rbac.can(user, Permission.MANAGE) or change.requester_id == user.person_id


def _require_requester_or_manager(user: User, change: ChangeRequest) -> None:
    if not _is_requester_or_manager(user, change):
        raise AccessDeniedError(CANCEL_DENIED_MESSAGE)


def _not_cancellable_message(situation: str) -> str:
    approved = situation in {
        models.SITUATION_IMPLEMENTING,
        models.SITUATION_APPROVED,
        models.SITUATION_APPROVED_WITH_CONDITIONS,
    }
    return CANCEL_DECIDED_MESSAGE + (CANCEL_REVERT_HINT if approved else ".")


# ── The demonstration load (ISSUE-023, D6) ───────────────────────────────


@dataclass(frozen=True)
class SeedAnalysis:
    """The analysis in progress of a demonstration change."""

    responsible_person_id: int
    start_date: date
    deadline: date


@dataclass(frozen=True)
class SeedImpact:
    """The impact analysis of a demonstration change."""

    analyst_person_id: int
    analysis_date: date
    cost_cents: int
    term_days: int
    scope: str
    quality: str
    risks: str
    safety: str
    contract: str
    affects_contract_milestone: bool
    activities: str | None


@dataclass(frozen=True)
class SeedDecision:
    """The decision of a demonstration change with the people who took part."""

    decision_date: date
    result: str
    conditions: str | None
    justification: str
    participant_person_ids: tuple[int, ...]


@dataclass(frozen=True)
class SeedClosing:
    """What the closing of a demonstration change recorded."""

    closed_by_person_id: int | None = None
    schedule: bool | None = None
    contract: bool | None = None
    risks: bool | None = None
    note: str | None = None


@dataclass(frozen=True)
class SeedChange:
    """A change of the demonstration as the prototype keeps it, in the shape the facade writes."""

    project_id: int
    code: str
    requester_person_id: int
    title: str
    kind: str
    origin: str
    priority: str
    request_date: date
    description: str
    situation: str
    resource_source: str | None = None
    authority: str | None = None
    emergency_start: date | None = None
    emergency_justification: str | None = None
    implementation_start: date | None = None
    closing_date: date | None = None
    closing: SeedClosing = field(default_factory=SeedClosing)
    eac_revision: int | None = None
    eap_revision: int | None = None
    analysis: SeedAnalysis | None = None
    impact: SeedImpact | None = None
    decision: SeedDecision | None = None


class DemonstrationNumberError(RuntimeError):
    """The number the sequence of the project gave is not the one the prototype printed."""


def load_demonstration_change(
    session: Session, *, author_id: int, seed: SeedChange, reference_date: date
) -> ChangeRequest:
    """Write a demonstration change with its parts, in the author's name (the trail of D5b).

    The code is reserved from the sequence of the project, and it must be the one of the prototype: the
    next real request then continues the numbering without a gap or a repetition.
    """
    project = configuracoes.find_project(session, seed.project_id)
    if project is None:
        raise InvalidDataError(NOT_FOUND_PROJECT_MESSAGE)
    code = numbering.next_number(
        session, project=project, kind=NUMBERING_KIND, reference_date=reference_date
    )
    if code != seed.code:
        message = f"A numeração gerou {code}, mas a demonstração pede {seed.code}."
        raise DemonstrationNumberError(message)
    change = ChangeRequest(
        project_id=seed.project_id,
        requester_id=seed.requester_person_id,
        closed_by_id=seed.closing.closed_by_person_id,
        code=code,
        title=seed.title,
        kind=seed.kind,
        origin=seed.origin,
        priority=seed.priority,
        request_date=seed.request_date,
        description=seed.description,
        resource_source=seed.resource_source,
        authority=seed.authority,
        situation=seed.situation,
        emergency=seed.emergency_start is not None,
        emergency_justification=seed.emergency_justification,
        implementation_start=seed.emergency_start or seed.implementation_start,
        closing_date=seed.closing_date,
        closed_schedule=seed.closing.schedule,
        closed_contract=seed.closing.contract,
        closed_risks=seed.closing.risks,
        eac_revision=seed.eac_revision,
        eap_revision=seed.eap_revision,
        closing_note=seed.closing.note,
    )
    recording.create(session, user_id=author_id, record=change)
    _load_parts(session, author_id=author_id, change=change, seed=seed)
    return change


def _load_parts(
    session: Session, *, author_id: int, change: ChangeRequest, seed: SeedChange
) -> None:
    if seed.analysis is not None:
        recording.create(
            session,
            user_id=author_id,
            record=ChangeAnalysis(
                change_id=change.id,
                responsible_id=seed.analysis.responsible_person_id,
                start_date=seed.analysis.start_date,
                deadline=seed.analysis.deadline,
            ),
        )
    if seed.impact is not None:
        recording.create(session, user_id=author_id, record=_impact_record(change.id, seed.impact))
    if seed.decision is not None:
        _load_decision(session, author_id=author_id, change=change, decision=seed.decision)


def _impact_record(change_id: int, impact: SeedImpact) -> ChangeImpact:
    return ChangeImpact(
        change_id=change_id,
        analyst_id=impact.analyst_person_id,
        analysis_date=impact.analysis_date,
        cost_cents=impact.cost_cents,
        term_days=impact.term_days,
        scope=impact.scope,
        quality=impact.quality,
        risks=impact.risks,
        safety=impact.safety,
        contract=impact.contract,
        affects_contract_milestone=impact.affects_contract_milestone,
        activities=impact.activities,
    )


def _load_decision(
    session: Session, *, author_id: int, change: ChangeRequest, decision: SeedDecision
) -> None:
    record = ChangeDecision(
        change_id=change.id,
        decision_date=decision.decision_date,
        result=decision.result,
        conditions=decision.conditions,
        justification=decision.justification,
    )
    recording.create(session, user_id=author_id, record=record)
    for person_id in decision.participant_person_ids:
        session.add(ChangeDecisionParticipant(decision_id=record.id, person_id=person_id))
    session.flush()


# ── Internals: loading ───────────────────────────────────────────────────


def _by_code(session: Session, code: str) -> ChangeRequest | None:
    statement = select(ChangeRequest).where(ChangeRequest.code == (code or "").strip())
    return session.scalars(statement).one_or_none()


def _load(session: Session) -> list[_Loaded]:
    """Every change with the latest impact, decision and analysis, newest code first."""
    changes = session.scalars(select(ChangeRequest).order_by(ChangeRequest.code.desc())).all()
    ids = [change.id for change in changes]
    impacts = _latest(session, ChangeImpact, ids)
    decisions = _latest(session, ChangeDecision, ids)
    analyses = _latest(session, ChangeAnalysis, ids)
    return [
        _Loaded(change, impacts.get(change.id), decisions.get(change.id), analyses.get(change.id))
        for change in changes
    ]


def _load_one(session: Session, change: ChangeRequest) -> _Loaded:
    impacts = _latest(session, ChangeImpact, [change.id])
    decisions = _latest(session, ChangeDecision, [change.id])
    analyses = _latest(session, ChangeAnalysis, [change.id])
    return _Loaded(
        change, impacts.get(change.id), decisions.get(change.id), analyses.get(change.id)
    )


def _latest[T: (ChangeImpact, ChangeDecision, ChangeAnalysis)](
    session: Session, model: type[T], ids: Sequence[int]
) -> dict[int, T]:
    """The last row (highest id) of each change: the version in force of its part."""
    if not ids:
        return {}
    statement = select(model).where(model.change_id.in_(ids)).order_by(model.id)
    return {row.change_id: row for row in session.scalars(statement)}


def _parameters(session: Session, reference_date: date) -> Mapping[str, Any]:
    found = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    )
    return {**DEFAULT_PARAMETERS, **found}


def _in_scope(item: _Loaded, scope: Scope) -> bool:
    return scope.is_portfolio or item.change.project_id == scope.project_id


def _scope_budget(scope: Scope, projects: Iterable[configuracoes.ProjectDetail]) -> int | None:
    """The budget the approved value is read against: the project's, or the sum of the portfolio's."""
    chosen = [
        project for project in projects if scope.is_portfolio or project.id == scope.project_id
    ]
    return sum(project.budget_cents or 0 for project in chosen) or None


def _names(session: Session, person_ids: Iterable[int | None]) -> dict[int, str]:
    return configuracoes.person_names(session, [pid for pid in person_ids if pid is not None])


def _sheet_person_ids(loaded: _Loaded) -> list[int | None]:
    ids: list[int | None] = [loaded.change.requester_id, loaded.change.closed_by_id]
    if loaded.analysis is not None:
        ids.append(loaded.analysis.responsible_id)
    if loaded.impact is not None:
        ids.append(loaded.impact.analyst_id)
    return ids


# ── Internals: rows, KPIs and filters ────────────────────────────────────


def _figures(item: _Loaded) -> ChangeFigures:
    change = item.change
    return ChangeFigures(
        situation=change.situation,
        request_date=change.request_date,
        cost_cents=item.impact.cost_cents if item.impact else None,
        term_days=item.impact.term_days if item.impact else None,
        decision_date=item.decision.decision_date if item.decision else None,
        analysis_deadline=item.analysis.deadline if item.analysis else None,
        emergency=change.emergency,
    )


def _summary(
    items: Sequence[_Loaded], *, budget_cents: int | None, reference_date: date
) -> ChangeSummary:
    return calculations.summarize_changes(
        [_figures(item) for item in items], budget_cents=budget_cents, reference_date=reference_date
    )


def _row(
    item: _Loaded,
    *,
    projects: Mapping[int, configuracoes.ProjectDetail],
    parameters: Mapping[str, Any],
    reference_date: date,
) -> ChangeRow:
    change = item.change
    figures = _figures(item)
    due = _ratification_due(change, parameters)
    pending = calculations.is_emergency_pending(
        emergency=change.emergency,
        has_decision=item.decision is not None,
        situation=change.situation,
    )
    project = projects.get(change.project_id)
    return ChangeRow(
        id=change.id,
        project_id=change.project_id,
        project_label=f"{project.code} · {project.name}"
        if project
        else f"Projeto {change.project_id}",
        code=change.code,
        title=change.title,
        request_date=change.request_date,
        priority=change.priority,
        kind=change.kind,
        origin=change.origin,
        authority=change.authority,
        cost_cents=figures.cost_cents,
        term_days=figures.term_days,
        situation=change.situation,
        next_step=calculations.next_step(
            NextStepFacts(
                situation=change.situation,
                authority=change.authority,
                analysis_deadline=figures.analysis_deadline,
                pending_eac_revision=_pending_eac_revision(item),
            )
        ),
        closing_date=change.closing_date,
        emergency_pending=pending,
        ratification_overdue=calculations.is_ratification_overdue(
            pending=pending, due_date=due, reference_date=reference_date
        ),
        analysis_overdue=calculations.is_analysis_overdue(
            change.situation, figures.analysis_deadline, reference_date
        ),
    )


def _pending_eac_revision(item: _Loaded) -> bool:
    """The approved cost is not in a revision of the EAC yet (the revision is made in Financeiro)."""
    cost = item.impact.cost_cents if item.impact else 0
    return (
        calculations.is_approved(item.change.situation)
        and bool(cost)
        and (item.change.eac_revision is None)
    )


def _search_text(change: ChangeRequest) -> str:
    return normalize_text(
        " ".join([change.code, change.title, change.description, change.kind, change.origin])
    )


def _matches(item: _Loaded, row: ChangeRow, filters: ChangeFilter) -> bool:
    return (
        _matches_situation(row.situation, filters.situation)
        and _equal_or_unset(row.kind, filters.kind)
        and _equal_or_unset(row.origin, filters.origin)
        and _equal_or_unset(row.priority, filters.priority)
        and _equal_or_unset(row.authority, filters.authority)
        and (not filters.search or normalize_text(filters.search) in _search_text(item.change))
    )


def _equal_or_unset(value: str | None, wanted: str | None) -> bool:
    return not wanted or value == wanted


def _matches_situation(situation: str, wanted: str | None) -> bool:
    if not wanted:
        return True
    if wanted == SITUATION_GROUP_OPEN:
        return calculations.is_open(situation)
    if wanted == SITUATION_GROUP_ANALYSIS:
        return situation in {models.SITUATION_REGISTERED, models.SITUATION_ANALYSIS}
    if wanted == SITUATION_GROUP_APPROVED:
        return calculations.is_approved(situation)
    return situation == wanted


# ── Internals: the ficha ─────────────────────────────────────────────────


def _final_stage_name(situation: str) -> str:
    if situation == models.SITUATION_REJECTED:
        return models.SITUATION_REJECTED
    if situation == models.SITUATION_CANCELLED:
        return models.SITUATION_CANCELLED
    return calculations.STAGE_NAMES[calculations.LAST_STAGE]


def _required_authority(
    item: _Loaded,
    projects: Mapping[int, configuracoes.ProjectDetail],
    parameters: Mapping[str, Any],
) -> calculations.AuthorityLimit | None:
    """The minimum authority the rules ask for; ``None`` while there is no impact analysis."""
    if item.impact is None:
        return None
    project = projects.get(item.change.project_id)
    return calculations.minimum_change_authority(
        value_cents=item.impact.cost_cents,
        budget_cents=project.budget_cents if project else None,
        affects_contract_milestone=item.impact.affects_contract_milestone,
        manager_limit_percent=Decimal(str(parameters["alcadaGerentePctOrcamento"])),
    )


def _emergency_start(change: ChangeRequest) -> date | None:
    return change.implementation_start if change.emergency else None


def _ratification_due(change: ChangeRequest, parameters: Mapping[str, Any]) -> date | None:
    start = _emergency_start(change)
    if start is None:
        return None
    return calculations.emergency_ratification_due_date(start, int(parameters["ratificacaoDias"]))


def _decision_views(session: Session, change: ChangeRequest) -> list[DecisionView]:
    """Every decision of the change in order; the last is the one in force."""
    decisions = session.scalars(
        select(ChangeDecision)
        .where(ChangeDecision.change_id == change.id)
        .order_by(ChangeDecision.decision_date, ChangeDecision.id)
    ).all()
    if not decisions:
        return []
    participants = session.execute(
        select(ChangeDecisionParticipant.decision_id, ChangeDecisionParticipant.person_id)
        .where(ChangeDecisionParticipant.decision_id.in_([d.id for d in decisions]))
        .order_by(ChangeDecisionParticipant.id)
    ).all()
    names = _names(session, [person_id for _, person_id in participants])
    return [
        DecisionView(
            decision=decision,
            participants=tuple(
                names.get(person_id, "")
                for owner, person_id in participants
                if owner == decision.id
            ),
        )
        for decision in decisions
    ]


def _history(
    item: _Loaded, decisions: Sequence[DecisionView], names: Mapping[int, str]
) -> tuple[HistoryEntry, ...]:
    change = item.change
    last = decisions[-1].decision if decisions else None
    facts = HistoryFacts(
        kind=change.kind,
        origin=change.origin,
        priority=change.priority,
        situation=change.situation,
        request_date=change.request_date,
        requester_id=change.requester_id,
        analysis_date=item.impact.analysis_date if item.impact else None,
        analyst_id=item.impact.analyst_id if item.impact else None,
        authority=change.authority,
        decision_date=last.decision_date if last else None,
        decision_result=last.result if last else None,
        decision_justification=last.justification if last else None,
        implementation_start=change.implementation_start,
        emergency_execution=change.emergency,
        closing_date=change.closing_date,
        closed_by_id=change.closed_by_id,
        cancellation_note=change.closing_note,
    )
    return tuple(_entry(line, names) for line in calculations.change_history(facts))


def _entry(line: HistoryLine, names: Mapping[int, str]) -> HistoryEntry:
    name = names.get(line.person_id, "") if line.person_id is not None else ""
    return HistoryEntry(moment=line.moment, person_name=name, text=line.text)


def _possible_duplicate(session: Session, change: ChangeRequest) -> str | None:
    """The code of another open request of the project with the same title, when there is one."""
    if not calculations.is_open(change.situation):
        return None
    wanted = normalize_text(change.title)
    statement = select(ChangeRequest).where(
        ChangeRequest.project_id == change.project_id,
        ChangeRequest.id != change.id,
        ChangeRequest.situation.not_in(models.TERMINAL_SITUATIONS),
    )
    for other in session.scalars(statement):
        if normalize_text(other.title) == wanted:
            return other.code
    return None


def _register_attachment_origin() -> None:
    attachment_origins.register(
        attachment_origins.OriginType(table=ORIGIN_TABLE, module=MODULE, read=read_change_origin)
    )


_register_attachment_origin()
