"""Business facade of the Governança module: the register of changes (SM), the ficha and the cancellation.

Everything the routes and the seed ask of the module goes through here (D5, D9): reading needs the
module and writing needs the Membro permission; every write goes through ``core.recording`` (trail,
version and transaction together) and the number of a new change through ``core.numbering``. A module
never reads these tables directly. Nothing here reads the clock: the caller passes the reference date,
taken from ``core.calendario`` at the edge of the route.

What this slice (ISSUE-023) writes is the request and its cancellation. The analysis, the decision and
the implementation are written by ISSUE-024 and ISSUE-025; this slice only reads them for the ficha.
The points where other modules enter are marked where they will be wired (D9): the open actions of the
implementation (Central de Ações, ISSUE-025), the check of the EAC items against the cost level
(Financeiro, ISSUE-030), the balance of the reserves (Financeiro, ISSUE-041) and the revision of the EAP
(Planejamento).

ISSUE-024 adds the analysis: ``start_analysis`` takes the change to Em análise de impacto and
``conclude_analysis`` records the impact, the required authority and sends it to Aguardando comitê.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.core import attachment_origins, calendario, numbering, origin_links, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.import_values import normalize_text
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import minutes_service
from src.modulos.central_acoes import service as central_acoes
from src.modulos.central_acoes.calculations import ACTION
from src.modulos.central_acoes.service import OriginActionCount
from src.modulos.central_acoes.validation import MinutesFilters, NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service as financeiro
from src.modulos.governanca import (
    calculations,
    lessons_calculations,
    lessons_models,
    lessons_service,
    models,
    validation,
)
from src.modulos.governanca.calculations import (
    ChangeFigures,
    ChangeSummary,
    HistoryFacts,
    HistoryLine,
    NextStepFacts,
)
from src.modulos.governanca.lessons_validation import DraftInput
from src.modulos.governanca.models import (
    ChangeAnalysis,
    ChangeDecision,
    ChangeDecisionParticipant,
    ChangeImpact,
    ChangeImpactEacItem,
    ChangeReallocation,
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
class TransferLine:
    """A transfer between two EAC items as the ficha shows it: codes and amount."""

    source_code: str
    target_code: str
    value_cents: int
    applied: bool


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
    transfers: tuple[TransferLine, ...] = ()
    eac_item_codes: tuple[str, ...] = ()
    analysis_action: str | None = None

    @property
    def total_transferred_cents(self) -> int:
        """The sum moved between EAC items by the reallocations of the change."""
        return sum(line.value_cents for line in self.transfers)

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


@dataclass(frozen=True)
class ChangePanel:
    """O painel de mudanças: os indicadores, o Pareto, as contagens e os acumulados por mês."""

    summary: ChangeSummary
    situations: tuple[calculations.CountLine, ...]
    origins: tuple[calculations.ParetoLine, ...]
    kinds: tuple[calculations.CountLine, ...]
    months: tuple[calculations.ApprovedMonth, ...]
    approval_rate: Decimal | None
    mean_decision_days: int | None


def change_panel(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> ChangePanel:
    """O painel do escopo: indicadores, Pareto por origem, tipos e acumulados por mês (HU-130)."""
    rbac.require_module(user, MODULE)
    everything = _load(session)
    in_scope = [item for item in everything if _in_scope(item, scope)]
    figures = [_figures(item) for item in in_scope]
    projects = configuracoes.list_project_details(session)
    return ChangePanel(
        summary=_summary(
            in_scope, budget_cents=_scope_budget(scope, projects), reference_date=reference_date
        ),
        situations=calculations.count_lines(
            (item.situation for item in figures), models.CHANGE_SITUATIONS
        ),
        origins=calculations.pareto_lines(
            calculations.count_lines((item.origin for item in figures), ())
        ),
        kinds=calculations.count_lines((item.kind for item in figures), models.CHANGE_TYPES),
        months=calculations.approved_monthly(figures, reference_date),
        approval_rate=calculations.approval_rate(figures),
        mean_decision_days=calculations.mean_decision_days(figures),
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
    transfers = _transfer_lines(session, change)
    required = _required_authority(loaded, projects, parameters, transfers)
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
        transfers=tuple(transfers),
        eac_item_codes=_impact_item_codes(session, loaded.impact),
        analysis_action=_analysis_action(user, change),
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


# ── The analysis (ISSUE-024, HU-126) ─────────────────────────────────────

ANALYSIS_START_SITUATIONS = (models.SITUATION_REGISTERED,)
ANALYSIS_IMPACT_SITUATIONS = (
    models.SITUATION_ANALYSIS,
    models.SITUATION_AWAITING,
    models.SITUATION_POSTPONED,
)
ACTION_START = "iniciar"
ACTION_CONCLUDE = "concluir"
ACTION_REVIEW = "revisar"
START_ONLY_REGISTERED_MESSAGE = "A análise só pode ser iniciada em solicitação Registrada."
IMPACT_ONLY_IN_ANALYSIS_MESSAGE = (
    "A análise de impacto só pode ser registrada com a solicitação em análise "
    "(ou revista antes da decisão)."
)
ITEM_NOT_IN_EAC_MESSAGE = "O item {code} não existe na EAC do projeto."


@dataclass(frozen=True)
class AnalysisStartForm:
    """What the form that starts the analysis shows: the people to choose from and the usual deadline."""

    change: ChangeRequest
    people: tuple[configuracoes.PersonSummary, ...]
    suggested_deadline: date
    analysis_days: int


@dataclass(frozen=True)
class ImpactForm:
    """What the impact form shows: the change, the values it opens with and the references to read."""

    change: ChangeRequest
    values: dict[str, str]
    impact_version: int | None
    manager_limit_cents: int | None
    manager_limit_percent: Decimal
    is_review: bool

    @property
    def is_reallocation(self) -> bool:
        """Whether the change is a reallocation of the budget: it asks for the transfers."""
        return self.change.kind == models.TYPE_REALLOCATION

    @property
    def is_release(self) -> bool:
        """Whether the change is a release of reserve: it asks for the reserve and the amount."""
        return self.change.kind == models.TYPE_RESERVE_RELEASE


def may_analyse(user: User, change: ChangeRequest) -> bool:
    """Whether the user may start or write the analysis now: Membro and a situation that allows it."""
    return _analysis_action(user, change) is not None


def _analysis_action(user: User, change: ChangeRequest) -> str | None:
    if not rbac.can(user, Permission.WRITE):
        return None
    if change.situation in ANALYSIS_START_SITUATIONS:
        return ACTION_START
    if change.situation == models.SITUATION_ANALYSIS:
        return ACTION_CONCLUDE
    if change.situation in ANALYSIS_IMPACT_SITUATIONS:
        return ACTION_REVIEW
    return None


def analysis_start_form(
    session: Session, *, user: User, code: str, reference_date: date
) -> AnalysisStartForm:
    """The form that starts the analysis, or the refusal that says why it cannot start now."""
    change = _analysable_change(session, user=user, code=code, allowed=ANALYSIS_START_SITUATIONS)
    days = int(_parameters(session, reference_date)["prazoAnaliseDias"])
    return AnalysisStartForm(
        change=change,
        people=tuple(configuracoes.list_people(session)),
        suggested_deadline=calculations.analysis_deadline(reference_date, days),
        analysis_days=days,
    )


def start_analysis(
    session: Session, *, user: User, code: str, form: validation.Form, reference_date: date
) -> ChangeRequest:
    """Start the analysis: Registrada goes to Em análise de impacto with the usual deadline (HU-126).

    Refused with 403 without the Membro permission and with 422 when the change is not Registrada or
    the responsible or the deadline break a rule. The deadline suggested to the form is the start plus
    the days of the parameter ``prazoAnaliseDias``.
    """
    change = _analysable_change(session, user=user, code=code, allowed=ANALYSIS_START_SITUATIONS)
    _require_versions(form, validation.FIELD_VERSION)
    people_ids = frozenset(person.id for person in configuracoes.list_people(session))
    start = validation.validate_analysis_start(
        form, people_ids=people_ids, reference_date=reference_date
    )
    recording.create(
        session,
        user_id=user.id,
        record=ChangeAnalysis(
            change_id=change.id,
            responsible_id=start.responsible_id,
            start_date=reference_date,
            deadline=start.deadline,
        ),
    )
    recording.update(
        session,
        user_id=user.id,
        record=change,
        changes={"situation": models.SITUATION_ANALYSIS},
        version=form.get(validation.FIELD_VERSION),
    )
    return change


def impact_form(session: Session, *, user: User, code: str, reference_date: date) -> ImpactForm:
    """The impact form with the values already recorded, or the refusal that says why not."""
    change = _analysable_change(session, user=user, code=code, allowed=ANALYSIS_IMPACT_SITUATIONS)
    loaded = _load_one(session, change)
    parameters = _parameters(session, reference_date)
    percent = Decimal(str(parameters["alcadaGerentePctOrcamento"]))
    project = configuracoes.find_project(session, change.project_id)
    budget = project.budget_cents if project else None
    limit = calculations.minimum_change_authority(
        value_cents=0,
        budget_cents=budget,
        affects_contract_milestone=False,
        manager_limit_percent=percent,
    ).limit_cents
    return ImpactForm(
        change=change,
        values=_impact_values(session, loaded),
        impact_version=loaded.impact.version if loaded.impact else None,
        manager_limit_cents=limit if budget else None,
        manager_limit_percent=percent,
        is_review=loaded.impact is not None,
    )


def conclude_analysis(
    session: Session, *, user: User, code: str, form: validation.Form, reference_date: date
) -> ChangeRequest:
    """Record the impact analysis and send the change to the decision (HU-126).

    Everything is mandatory as ``validation.validate_impact`` says; the authority required is computed
    here, from the cost or the amount moved, the contract milestone and the source of the resource, and
    the analyst may raise it, never lower it. A change in analysis goes to Aguardando comitê; one
    already waiting or postponed has its analysis revised and keeps its situation. The EAC items are
    linked through Financeiro; checking that they are cost items (level 3) is ISSUE-030, and the
    balance of the reserves that warns about a cost above it is ISSUE-041.
    """
    change = _analysable_change(session, user=user, code=code, allowed=ANALYSIS_IMPACT_SITUATIONS)
    current = _latest(session, ChangeImpact, [change.id]).get(change.id)
    fields = [validation.FIELD_VERSION]
    if current is not None:
        fields.append(validation.FIELD_IMPACT_VERSION)
    _require_versions(form, *fields)
    project = configuracoes.find_project(session, change.project_id)
    parameters = _parameters(session, reference_date)
    rules = validation.ImpactRules(
        kind=change.kind,
        budget_cents=project.budget_cents if project else None,
        manager_limit_percent=Decimal(str(parameters["alcadaGerentePctOrcamento"])),
    )
    new = validation.validate_impact(form, rules=rules)
    item_ids = _resolve_items(session, change, new)
    impact = _write_impact(
        session,
        user=user,
        change=change,
        values=_impact_changes(new, person_id=user.person_id, day=reference_date),
        version=form.get(validation.FIELD_IMPACT_VERSION),
    )
    _replace_items(session, impact, [item_ids[code] for code in _all_codes(new)])
    _replace_transfers(session, change, new, item_ids)
    _conclude_running_analysis(session, user=user, change=change, day=reference_date)
    changes: dict[str, Any] = {
        "resource_source": new.resource_source,
        "authority": new.authority,
    }
    if change.situation == models.SITUATION_ANALYSIS:
        changes["situation"] = models.SITUATION_AWAITING
    recording.update(
        session,
        user_id=user.id,
        record=change,
        changes=changes,
        version=form.get(validation.FIELD_VERSION),
    )
    return change


def _require_versions(form: validation.Form, *fields: str) -> None:
    """Refuse with 422 before any write when the screen did not send the version it opened."""
    missing = {
        field: "A versão do registro não foi informada."
        for field in fields
        if not (form.get(field) or "").strip()
    }
    if missing:
        raise InvalidDataError(missing)


def _analysable_change(
    session: Session, *, user: User, code: str, allowed: Sequence[str]
) -> ChangeRequest:
    rbac.require_module(user, MODULE)
    change = _by_code(session, code)
    if change is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    rbac.require(user, Permission.WRITE)
    if change.situation not in allowed:
        raise InvalidDataError(
            START_ONLY_REGISTERED_MESSAGE
            if allowed == ANALYSIS_START_SITUATIONS
            else IMPACT_ONLY_IN_ANALYSIS_MESSAGE
        )
    return change


def _all_codes(new: validation.ImpactInput) -> list[str]:
    """The EAC items of the analysis: the ones typed and the ends of every transfer."""
    codes = list(new.item_codes)
    for transfer in new.transfers:
        codes.extend([transfer.source_code, transfer.target_code])
    return list(dict.fromkeys(codes))


def _resolve_items(
    session: Session, change: ChangeRequest, new: validation.ImpactInput
) -> dict[str, int]:
    codes = _all_codes(new)
    found = financeiro.eac_item_ids_by_code(session, project_id=change.project_id, codes=codes)
    messages: dict[str, str] = {}
    typed = set(new.item_codes)
    for code in codes:
        if code in found:
            continue
        field = validation.FIELD_EAC_ITEMS if code in typed else validation.FIELD_TRANSFERS
        messages.setdefault(field, ITEM_NOT_IN_EAC_MESSAGE.format(code=code))
    if messages:
        raise InvalidDataError(messages)
    return found


def _impact_changes(new: validation.ImpactInput, *, person_id: int, day: date) -> dict[str, Any]:
    return {
        "analyst_id": person_id,
        "analysis_date": day,
        "cost_cents": new.cost_cents,
        "term_days": new.term_days,
        "scope": new.scope,
        "quality": new.quality,
        "risks": new.risks,
        "safety": new.safety,
        "contract": new.contract,
        "affects_contract_milestone": new.affects_contract_milestone,
        "activities": new.activities or None,
        "release_reserve": new.release_reserve,
        "release_value_cents": new.release_cents,
    }


def _write_impact(
    session: Session,
    *,
    user: User,
    change: ChangeRequest,
    values: dict[str, Any],
    version: str | None,
) -> ChangeImpact:
    current = _latest(session, ChangeImpact, [change.id]).get(change.id)
    if current is None:
        record = ChangeImpact(change_id=change.id, **values)
        recording.create(session, user_id=user.id, record=record)
        return record
    recording.update(session, user_id=user.id, record=current, changes=values, version=version)
    return current


def _replace_items(session: Session, impact: ChangeImpact, item_ids: Sequence[int]) -> None:
    session.execute(delete(ChangeImpactEacItem).where(ChangeImpactEacItem.impact_id == impact.id))
    session.add_all(
        ChangeImpactEacItem(impact_id=impact.id, eac_item_id=item_id) for item_id in item_ids
    )
    session.flush()


def _replace_transfers(
    session: Session,
    change: ChangeRequest,
    new: validation.ImpactInput,
    item_ids: Mapping[str, int],
) -> None:
    """The proposed transfers of the change: the ones not yet applied are replaced by the new list."""
    session.execute(
        delete(ChangeReallocation).where(
            ChangeReallocation.change_id == change.id, ChangeReallocation.applied.is_(False)
        )
    )
    session.add_all(
        ChangeReallocation(
            change_id=change.id,
            source_item_id=item_ids[transfer.source_code],
            target_item_id=item_ids[transfer.target_code],
            value_cents=transfer.value_cents,
            applied=False,
        )
        for transfer in new.transfers
    )
    session.flush()


def _conclude_running_analysis(
    session: Session, *, user: User, change: ChangeRequest, day: date
) -> None:
    running = _latest(session, ChangeAnalysis, [change.id]).get(change.id)
    if running is None or running.concluded_on is not None:
        return
    recording.update(
        session,
        user_id=user.id,
        record=running,
        changes={"concluded_on": day},
        version=running.version,
    )


def _transfer_lines(session: Session, change: ChangeRequest) -> list[TransferLine]:
    rows = session.scalars(
        select(ChangeReallocation)
        .where(ChangeReallocation.change_id == change.id)
        .order_by(ChangeReallocation.id)
    ).all()
    codes = financeiro.eac_item_codes(
        session, [item for row in rows for item in (row.source_item_id, row.target_item_id)]
    )
    return [
        TransferLine(
            source_code=codes.get(row.source_item_id, ""),
            target_code=codes.get(row.target_item_id, ""),
            value_cents=row.value_cents,
            applied=row.applied,
        )
        for row in rows
    ]


def _impact_item_codes(session: Session, impact: ChangeImpact | None) -> tuple[str, ...]:
    if impact is None:
        return ()
    ids = session.scalars(
        select(ChangeImpactEacItem.eac_item_id)
        .where(ChangeImpactEacItem.impact_id == impact.id)
        .order_by(ChangeImpactEacItem.id)
    ).all()
    codes = financeiro.eac_item_codes(session, list(ids))
    return tuple(codes[item] for item in ids if item in codes)


def _impact_values(session: Session, loaded: _Loaded) -> dict[str, str]:
    """The values the impact form opens with: the ones recorded, as a person types them."""
    change, impact = loaded.change, loaded.impact
    values = {
        validation.FIELD_VERSION: str(change.version),
        validation.FIELD_SOURCE: change.resource_source or "",
        validation.FIELD_AUTHORITY: change.authority or "",
    }
    if impact is None:
        return values
    values.update(
        {
            validation.FIELD_IMPACT_VERSION: str(impact.version),
            validation.FIELD_COST: _money_input(impact.cost_cents),
            validation.FIELD_TERM_DAYS: str(impact.term_days),
            validation.FIELD_CONTRACT_MILESTONE: (
                validation.CHECKED_VALUE
                if impact.affects_contract_milestone
                else validation.UNCHECKED_VALUE
            ),
            validation.FIELD_SCOPE: impact.scope,
            validation.FIELD_QUALITY: impact.quality,
            validation.FIELD_RISKS: impact.risks,
            validation.FIELD_SAFETY: impact.safety,
            validation.FIELD_CONTRACT: impact.contract,
            validation.FIELD_ACTIVITIES: impact.activities or "",
            validation.FIELD_EAC_ITEMS: ", ".join(_impact_item_codes(session, impact)),
            validation.FIELD_RELEASE_RESERVE: impact.release_reserve or "",
            validation.FIELD_RELEASE_VALUE: _money_input(impact.release_value_cents or 0)
            if impact.release_value_cents
            else "",
        }
    )
    for number, line in enumerate(_transfer_lines(session, change), start=1):
        values[f"{validation.TRANSFER_SOURCE}_{number}"] = line.source_code
        values[f"{validation.TRANSFER_TARGET}_{number}"] = line.target_code
        values[f"{validation.TRANSFER_VALUE}_{number}"] = _money_input(line.value_cents)
    return values


def _money_input(cents: int) -> str:
    """Cents as the field of the form takes them: ``-1.234,56``."""
    reais, rest = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}{reais:,}".replace(",", ".") + f",{rest:02d}"


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


# ── The decision and the closing (ISSUE-025) ─────────────────────────────

IMPLEMENTATION_ORIGIN = "Mudança"
IMPLEMENTATION_GROUP = "Implementação"
DECISION_DENIED_MESSAGE = "Registrar a decisão exige papel Gestor."
CLOSING_DENIED_MESSAGE = "O encerramento exige papel Gestor."
UNKNOWN_PERSON_MESSAGE = "A pessoa informada não está no cadastro."


@dataclass(frozen=True)
class DecisionActionView:
    """Uma ação de implementação sugerida, com o nome do responsável para o formulário."""

    key: str
    module: str
    subject: str
    responsible_id: int | None
    responsible_name: str


@dataclass(frozen=True)
class DecisionAtaOption:
    """Uma ata do projeto que o modal Decisão oferece para vincular."""

    id: int
    label: str


@dataclass(frozen=True)
class DecisionForm:
    """O que o modal Decisão mostra: a ficha, quem decide e o que a aprovação gera."""

    sheet: ChangeSheet
    manager_id: int | None
    manager_name: str
    quorum: int
    impact_date: date | None
    actions: tuple[DecisionActionView, ...]
    atas: tuple[DecisionAtaOption, ...]
    people: tuple[configuracoes.RegisterOption, ...]
    default_participants: tuple[int, ...]
    default_planned: date


@dataclass(frozen=True)
class DecisionResult:
    """O que a decisão fez: a situação da SM e quantas ações nasceram na Central."""

    code: str
    situation: str
    actions_created: int


@dataclass(frozen=True)
class ClosingForm:
    """O que o modal Encerrar mostra: as confirmações devidas e as ações em aberto."""

    sheet: ChangeSheet
    open_actions: int
    schedule_required: bool
    contract_required: bool
    risks_required: bool
    lesson_title: str


@dataclass(frozen=True)
class ClosingResult:
    """O que o encerramento fez: o código da SM e o da lição, quando ela foi pedida."""

    code: str
    lesson_code: str | None


@dataclass(frozen=True)
class _Implementation:
    """O que a aprovação gera: as ações escolhidas, o prazo e as duas datas da transação."""

    actions: Sequence[DecisionActionView]
    planned_date: date | None
    decision_date: date
    reference_date: date


def decision_form(session: Session, *, user: User, code: str, reference_date: date) -> DecisionForm:
    """O formulário da decisão: o resumo da ficha, o quórum, as atas e as ações sugeridas."""
    rbac.require_module(user, MODULE)
    change = _decidable_change(session, code)
    sheet = find_change_sheet(session, user=user, code=code, reference_date=reference_date)
    if sheet is None:  # pragma: no cover - a mudança acabou de ser encontrada
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    parameters = _parameters(session, reference_date)
    manager_id, manager_name = _manager_of(session, change)
    committee = change.authority == models.AUTHORITY_COMMITTEE
    participants = [manager_id] if manager_id else []
    if committee:
        participants.append(user.person_id)
    return DecisionForm(
        sheet=sheet,
        manager_id=manager_id,
        manager_name=manager_name,
        quorum=int(parameters["quorumComite"]),
        impact_date=sheet.impact.analysis_date if sheet.impact else None,
        actions=_suggested_action_views(session, change, manager_id),
        atas=_ata_options(session, user, change, reference_date),
        people=tuple(configuracoes.list_person_options(session)),
        default_participants=tuple(dict.fromkeys(participants)),
        default_planned=calendario.add_days(reference_date, int(parameters["prazoAcoesDias"])),
    )


def decide_change(
    session: Session,
    *,
    user: User,
    code: str,
    form: Mapping[str, object],
    reference_date: date,
) -> DecisionResult:
    """Registra a decisão (HU-127): quórum e decisor conferidos, e a aprovação gera as ações.

    A decisão, os participantes, as ações de implementação na Central (origem ``Mudança``) e a
    mudança de situação entram na mesma transação: uma falha no meio desfaz tudo.
    """
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(DECISION_DENIED_MESSAGE)
    change = _decidable_change(session, code)
    loaded = _load_one(session, change)
    if loaded.impact is None or loaded.impact.analysis_date is None:
        raise InvalidDataError(validation.DECISION_IMPACT_REQUIRED)
    parameters = _parameters(session, reference_date)
    manager_id, manager_name = _manager_of(session, change)
    data = validation.parse_decision(form)
    facts = validation.DecisionFacts(
        authority=change.authority,
        manager_id=manager_id,
        manager_name=manager_name,
        quorum=int(parameters["quorumComite"]),
        impact_date=loaded.impact.analysis_date,
        reference_date=reference_date,
    )
    problems = validation.decision_problems(data, facts)
    if data.ata_id is not None and data.ata_id not in {
        option.id for option in _ata_options(session, user, change, reference_date)
    }:
        problems[validation.FIELD_ATA] = validation.DECISION_ATA_UNKNOWN
    if problems:
        raise InvalidDataError(problems)
    approved = data.result in models.APPROVED_SITUATIONS
    chosen = (
        tuple(
            action
            for action in _suggested_action_views(session, change, manager_id)
            if action.key in data.actions
        )
        if approved
        else ()
    )
    decision = recording.create(
        session,
        user_id=user.id,
        record=ChangeDecision(
            change_id=change.id,
            ata_id=data.ata_id,
            decision_date=cast("date", data.decision_date),
            result=data.result,
            conditions=data.conditions or None,
            justification=data.justification,
            reappear_on=data.reappear_on,
        ),
    )
    for person_id in data.participants:
        recording.create(
            session,
            user_id=user.id,
            record=ChangeDecisionParticipant(decision_id=decision.id, person_id=person_id),
        )
    created = (
        _create_implementation_actions(
            session,
            user=user,
            change=change,
            plan=_Implementation(
                actions=chosen,
                planned_date=data.planned_date,
                decision_date=cast("date", data.decision_date),
                reference_date=reference_date,
            ),
        )
        if approved
        else 0
    )
    changes: dict[str, object] = {
        "situation": models.SITUATION_IMPLEMENTING if approved else data.result
    }
    if data.result == models.SITUATION_REJECTED:
        changes["closing_date"] = data.decision_date
    recording.update(session, user_id=user.id, record=change, changes=changes, version=data.version)
    return DecisionResult(code=change.code, situation=change.situation, actions_created=created)


def resubmit_change(
    session: Session, *, user: User, code: str, reference_date: date
) -> CreatedChange:
    """Reapresenta a solicitação adiada: volta à pauta e a decisão anterior fica no histórico."""
    del reference_date  # a reapresentação não depende da data; a assinatura mantém o padrão
    rbac.require(user, Permission.WRITE)
    change = _by_code(session, code)
    if change is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    if change.situation != models.SITUATION_POSTPONED:
        raise InvalidDataError(validation.REOPEN_NOT_POSTPONED)
    recording.update(
        session,
        user_id=user.id,
        record=change,
        changes={"situation": models.SITUATION_AWAITING},
        version=change.version,
    )
    return CreatedChange(id=change.id, code=change.code, project_id=change.project_id)


def closing_form(session: Session, *, user: User, code: str, reference_date: date) -> ClosingForm:
    """O formulário do encerramento: a conferência das ações e o que a análise exige confirmar."""
    rbac.require_module(user, MODULE)
    change = _closable_change(session, code)
    sheet = find_change_sheet(session, user=user, code=code, reference_date=reference_date)
    if sheet is None:  # pragma: no cover - a mudança acabou de ser encontrada
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    impact = sheet.impact
    return ClosingForm(
        sheet=sheet,
        open_actions=_open_implementation_actions(session, user, change, reference_date),
        schedule_required=bool(impact and impact.term_days),
        contract_required=bool(impact and calculations.has_impact(impact.contract)),
        risks_required=bool(impact and calculations.has_impact(impact.risks)),
        lesson_title=change.title,
    )


def close_change(
    session: Session,
    *,
    user: User,
    code: str,
    form: validation.Form,
    reference_date: date,
) -> ClosingResult:
    """Encerra a mudança (HU-128): sem ação aberta, com as confirmações e a lição opcional."""
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(CLOSING_DENIED_MESSAGE)
    change = _closable_change(session, code)
    loaded = _load_one(session, change)
    open_actions = _open_implementation_actions(session, user, change, reference_date)
    data = validation.parse_closing(form)
    problems = validation.closing_problems(data, impact=loaded.impact, open_actions=open_actions)
    if problems:
        raise InvalidDataError(problems)
    lesson_id = None
    lesson_code = None
    if data.lesson is not None:
        created = lessons_service.create_draft_lesson(
            session,
            user=user,
            project_id=change.project_id,
            draft=_closing_lesson_draft(change, loaded.impact, data.lesson),
            reference_date=reference_date,
        )
        lesson_id = created.id
        lesson_code = created.code
    recording.update(
        session,
        user_id=user.id,
        record=change,
        changes={
            "situation": models.SITUATION_CLOSED,
            "closing_date": data.closing_date,
            "closed_schedule": data.schedule,
            "closed_contract": data.contract,
            "closed_risks": data.risks,
            "closing_note": data.note or None,
            "closed_by_id": user.person_id,
            "lesson_id": lesson_id,
        },
        version=data.version,
    )
    return ClosingResult(code=change.code, lesson_code=lesson_code)


def _decidable_change(session: Session, code: str) -> ChangeRequest:
    """A mudança que pode ser decidida agora: Aguardando comitê, com a análise concluída."""
    change = _by_code(session, code)
    if change is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    if change.situation != models.SITUATION_AWAITING:
        raise InvalidDataError(validation.DECISION_ONLY_AWAITING)
    loaded = _load_one(session, change)
    if loaded.impact is None or loaded.impact.analysis_date is None:
        raise InvalidDataError(validation.DECISION_IMPACT_REQUIRED)
    return change


def _closable_change(session: Session, code: str) -> ChangeRequest:
    change = _by_code(session, code)
    if change is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    if change.situation != models.SITUATION_IMPLEMENTING:
        raise InvalidDataError(validation.CLOSING_ONLY_IMPLEMENTING)
    return change


def _manager_of(session: Session, change: ChangeRequest) -> tuple[int | None, str]:
    project = configuracoes.find_project(session, change.project_id)
    manager_id = project.manager_person_id if project else None
    name = _names(session, [manager_id]).get(manager_id or 0, "")
    return manager_id, name


def _suggested_action_views(
    session: Session, change: ChangeRequest, manager_id: int | None
) -> tuple[DecisionActionView, ...]:
    loaded = _load_one(session, change)
    impact = loaded.impact
    if impact is None:
        return ()
    facts = calculations.ImpactFacts(
        cost_cents=impact.cost_cents,
        term_days=impact.term_days,
        quality=impact.quality,
        risks=impact.risks,
        safety=impact.safety,
        contract=impact.contract,
    )
    roles = {person.id: person.role for person in configuracoes.list_person_details(session)}
    suggested = calculations.suggested_change_actions(
        facts, code=change.code, manager_id=manager_id, roles=roles
    )
    names = _names(session, [action.responsible_id for action in suggested])
    return tuple(
        DecisionActionView(
            key=action.key,
            module=action.module,
            subject=action.subject,
            responsible_id=action.responsible_id,
            responsible_name=names.get(action.responsible_id or 0, ""),
        )
        for action in suggested
    )


def _ata_options(
    session: Session, user: User, change: ChangeRequest, reference_date: date
) -> tuple[DecisionAtaOption, ...]:
    listing = minutes_service.list_minutes(
        session,
        user=user,
        scope=Scope(project_id=change.project_id, source="padrao"),
        filters=MinutesFilters(),
        reference_date=reference_date,
    )
    return tuple(
        DecisionAtaOption(
            id=row.record.id,
            label=f"{row.record.number} Rev {row.record.revision} · "
            f"{row.record.meeting_date:%d/%m/%Y}",
        )
        for row in listing.rows
    )


def _open_implementation_actions(
    session: Session, user: User, change: ChangeRequest, reference_date: date
) -> int:
    counts = central_acoes.count_actions_of_origin(
        session,
        user=user,
        origin_kind=IMPLEMENTATION_ORIGIN,
        references=[change.code],
        reference_date=reference_date,
    )
    return counts.get(change.code, OriginActionCount()).open


def _create_implementation_actions(
    session: Session,
    *,
    user: User,
    change: ChangeRequest,
    plan: _Implementation,
) -> int:
    """Cria as ações aprovadas na Central, pela costura única, com origem ``Mudança`` e link."""
    for action in plan.actions:
        central_acoes.create_action(
            session,
            user=user,
            new=NewAction(
                project_id=change.project_id,
                origin=IMPLEMENTATION_ORIGIN,
                origin_ref=change.code,
                subject=action.subject,
                requester_id=user.person_id,
                responsible_id=action.responsible_id or user.person_id,
                planned_date=plan.planned_date,
                kind=ACTION,
                description=(
                    "Implementação da mudança aprovada em "
                    f"{plan.decision_date:%d/%m/%Y} ({action.module})."
                ),
                group=IMPLEMENTATION_GROUP,
                item=central_acoes.next_origin_item(
                    session, origin_kind=IMPLEMENTATION_ORIGIN, reference=change.code
                ),
            ),
            reference_date=plan.reference_date,
        )
    return len(plan.actions)


def _closing_lesson_draft(
    change: ChangeRequest, impact: ChangeImpact | None, lesson: validation.ClosingLesson
) -> DraftInput:
    """A lição do encerramento: o texto que a SM dá, o tipo e a recomendação que a pessoa escreveu."""
    facts = lessons_calculations.lesson_draft_for_change(
        lessons_calculations.ChangeFacts(
            title=change.title,
            description=change.description,
            kind=change.kind,
            origin=change.origin,
            term_days=impact.term_days if impact else None,
            cost_cents=impact.cost_cents if impact else None,
        )
    )
    return DraftInput(
        title=lesson.title,
        kind=lesson.kind,
        phase=lesson.phase,
        area=facts.area,
        origin=lessons_models.ORIGIN_CHANGE,
        origin_ref=change.code,
        what_happened=facts.what_happened,
        cause=facts.cause,
        recommendation=lesson.recommendation,
        discipline=lesson.discipline,
        term_days=facts.term_days,
        cost_cents=facts.cost_cents,
        keywords=facts.keywords,
    )


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
        origin=change.origin,
        kind=change.kind,
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
    transfers: Sequence[TransferLine],
) -> calculations.AuthorityLimit | None:
    """The minimum authority the rules ask for; ``None`` while there is no impact analysis."""
    if item.impact is None:
        return None
    project = projects.get(item.change.project_id)
    return calculations.required_change_authority(
        calculations.AuthorityFacts(
            kind=item.change.kind,
            resource_source=item.change.resource_source,
            cost_cents=item.impact.cost_cents,
            transferred_cents=sum(line.value_cents for line in transfers),
            budget_cents=project.budget_cents if project else None,
            affects_contract_milestone=item.impact.affects_contract_milestone,
        ),
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


def _build_change_link(reference: origin_links.OriginRef) -> str | None:
    """The address of the ficha of the change an action came from; none without the code."""
    if not reference.reference:
        return None
    return origin_links.link_to_screen("governanca/mudanca", codigo=reference.reference)


_register_attachment_origin()
origin_links.register(
    origin_links.OriginLinkType(kind=IMPLEMENTATION_ORIGIN, build=_build_change_link)
)
