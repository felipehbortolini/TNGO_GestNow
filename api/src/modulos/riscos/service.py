"""Business facade of the Risk management module: the register and the assessment (ISSUE-064).

Score, severity, VME and exposure are never stored: every read calculates them with the active
scale and the probabilities of the parameters (group Riscos) and the reference date the caller
hands in. A record is written only through ``core.recording`` (trail, version and transaction
together); the actions of a risk live in the Central de Ações and are read through its facade
(``central_acoes.service.count_actions_of_origin``), never from the table ``acao``.

Public API (stable; a change needs an issue of its own):

* reading: ``list_risks``, ``find_risk``, ``risk_summary``, ``list_categories``, ``ata_options``;
* writing: ``save_risk``, ``assess_risk``, ``delete_risk``, ``restore_risk``, ``create_category``
  and ``record_history`` (a risk that already has a history: the demonstration load);
* ``preview_score``: the preview of the form, calculated on the server.

Deleting is logical (``oculto``), asks for the Gestor, is refused with an open action or for a
closed risk, and keeps reason, author and date; only the Admin sees and restores what was
deleted. The code ``RSK-...-0001`` is reserved when the record is written and counts only the
numeric suffixes (``calculations.next_code_number``).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit, calendario, numbering, origin_links, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import GeneralProfile, Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.service import OriginActionCount
from src.modulos.configuracoes import service as configuracoes
from src.modulos.riscos import calculations, validation
from src.modulos.riscos.calculations import (
    DIMENSIONS,
    THREAT,
    Band,
    RiskParameters,
)
from src.modulos.riscos.models import (
    Risk,
    RiskAssessment,
    RiskCategory,
    RiskPlanApproval,
    RiskReview,
)
from src.modulos.riscos.validation import (
    INHERENT,
    RESIDUAL,
    AssessmentInput,
    DeletionInput,
    RiskFilters,
    RiskInput,
)

MODULE = "riscos"
ORIGIN_KIND = "Risco"
PARAMETER_GROUP = "riscos"

NOT_FOUND_MESSAGE = "Risco não encontrado."
CLOSED_MESSAGE = "Risco encerrado não pode ser editado nem reavaliado. Reabra o risco antes."
DELETE_CLOSED_MESSAGE = "Risco encerrado não é excluído: já saiu da carteira ativa."
DELETE_OPEN_ACTIONS_MESSAGE = "Risco com ação em aberto não pode ser excluído: {count} em aberto."
DELETE_FORBIDDEN_MESSAGE = "Excluir risco exige perfil Gestor."
RESTORE_FORBIDDEN_MESSAGE = "Somente Admin restaura riscos excluídos."
NOT_DELETED_MESSAGE = "Risco não está excluído."
UNKNOWN_PROJECT_MESSAGE = "O projeto informado não existe."
UNKNOWN_OWNER_MESSAGE = "O dono precisa estar no cadastro de pessoas."
UNKNOWN_CATEGORY_MESSAGE = "A categoria da RBS não existe."
DUPLICATE_NOTICE = (
    "Já existe risco com o mesmo evento no projeto ({code}). Verifique se não é duplicidade."
)
PARAMETERS_MISSING_MESSAGE = "Os parâmetros de Riscos ainda não foram cadastrados."

SITUATION_IDENTIFIED = "Identificado"
SITUATION_ANALYSIS = "Em análise"
SITUATION_TREATMENT = "Em tratamento"
SITUATION_MONITORED = "Monitorado"
APPROVAL_PENDING = "Pendente"
OPPORTUNITY_REDUCED = {
    "Risco reduzido": "Benefício reduzido",
    "Risco agravado": "Benefício ampliado",
}


@dataclass(frozen=True)
class AssessmentView:
    """One assessment as it is read: P, I, the dimensions, the score and the band it falls in."""

    probability: int
    impact: int
    dimensions: Mapping[str, int | None]
    score: int
    severity: Band
    assessed_on: date


@dataclass(frozen=True)
class RiskLine:
    """One risk of the register: the columns and everything calculated from them."""

    id: int
    project_id: int
    code: str
    title: str
    nature: str
    category_id: int
    category_group: str
    category_name: str
    owner_id: int
    owner_name: str
    identified_on: date
    origin_type: str
    origin: str | None
    ata_id: int | None
    cause: str
    consequence: str
    description: str | None
    trigger: str | None
    life_risk: bool
    cost_impact_cents: int
    schedule_impact_days: int
    strategy: str | None
    plan: str | None
    target_severity: str | None
    situation: str
    hidden: bool
    deletion_reason: str | None
    version: int
    cadence_days: int | None
    next_review: date | None
    inherent: AssessmentView | None
    residual: AssessmentView | None
    current: AssessmentView | None
    vme_cents: int
    active: bool
    review_overdue: bool
    days_to_review: int | None
    never_reviewed: bool
    plan_pending: bool
    actions: OriginActionCount

    @property
    def category_label(self) -> str:
        """``Grupo > Subcategoria``, how the register prints and filters the category."""
        return f"{self.category_group} > {self.category_name}"

    @property
    def has_plan(self) -> bool:
        """Whether a response plan (strategy and text) exists: it enables the residual."""
        return bool(self.strategy and self.plan)

    @property
    def is_system_origin(self) -> bool:
        """An origin generated by other modules (Diligenciamento, Claim...): not editable."""
        return self.origin_type not in validation.MANUAL_ORIGINS

    def displayed(self, kind: str) -> AssessmentView | None:
        """The assessment the register shows: the inherent one, or the residual (else inherent)."""
        return self.inherent if kind == INHERENT else self.current


@dataclass(frozen=True)
class BandCount:
    """A KPI of severity: how many active risks are in the band, the goal and the nature split."""

    band: Band
    total: int
    threats: int
    opportunities: int
    goal: int


@dataclass(frozen=True)
class RiskSummary:
    """The five KPIs of the register for the assessment shown, and what the notice needs."""

    assessment: str
    active: int
    registered: int
    unassessed: int
    top: BandCount
    second: BandCount | None
    in_treatment: int
    expected_in_treatment: int
    overdue: tuple[RiskLine, ...]
    exposure_cents: int


@dataclass(frozen=True)
class ProjectOption:
    """A project of the scope with what the context line prints."""

    id: int
    code: str
    name: str
    client_acronym: str
    risk_pattern: str | None
    appetite: Band | None


@dataclass(frozen=True)
class RiskListing:
    """What the register shows for a filter: the lines, the KPIs and the choices of the filter."""

    lines: tuple[RiskLine, ...]
    summary: RiskSummary
    parameters: RiskParameters
    projects: tuple[ProjectOption, ...]
    categories: tuple[RiskCategory, ...]
    owners: tuple[tuple[int, str], ...]
    page: int
    closed_hidden: int

    @property
    def total(self) -> int:
        """How many risks the filter holds, whatever the page."""
        return len(self.lines)

    @property
    def page_count(self) -> int:
        """How many pages the list has; an empty list still has one."""
        return max(1, -(-len(self.lines) // validation.PAGE_SIZE))

    @property
    def page_lines(self) -> tuple[RiskLine, ...]:
        """The lines of the current page."""
        start = (self.page - 1) * validation.PAGE_SIZE
        return self.lines[start : start + validation.PAGE_SIZE]


@dataclass(frozen=True)
class SaveResult:
    """What saving the identification answers: the code and the warnings that do not block."""

    code: str
    created: bool
    notices: tuple[str, ...]


@dataclass(frozen=True)
class AssessmentResult:
    """What an assessment answers: the score, the band and what the screen should warn about."""

    code: str
    score: int
    severity: Band
    requires_plan: bool
    manager_alert: bool
    situation: str


@dataclass(frozen=True)
class ScorePreview:
    """The preview of the form: the least impact, the score, the band, the VME and the cadence."""

    minimum_impact: int
    impact: int | None
    score: int | None
    severity: Band | None
    mean_pct: Decimal | None
    cadence_days: int | None
    vme_cents: int | None


@dataclass(frozen=True)
class AtaOption:
    """A minute the form may point to as the origin of a risk."""

    id: int
    label: str


AtaProvider = Callable[[Session, int], Sequence[AtaOption]]
_ata_providers: list[AtaProvider] = []


def register_ata_options(provider: AtaProvider) -> None:
    """The module of the minutes says how the form lists the minutes of a project (ISSUE-021)."""
    if provider not in _ata_providers:
        _ata_providers.append(provider)


def ata_options(session: Session, project_id: int) -> list[AtaOption]:
    """The minutes of the project the form offers; empty until the module of the minutes is in."""
    return [option for provider in _ata_providers for option in provider(session, project_id)]


# ── Reading ──────────────────────────────────────────────────────────────────────────────────


def parameters(session: Session, *, reference_date: date) -> RiskParameters:
    """The group Riscos of the parameters in force on the date, as the calculations read it."""
    values = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    )
    if not values:
        raise InvalidDataError(PARAMETERS_MISSING_MESSAGE)
    return calculations.parameters_from_values(values)


def can_see_deleted(user: User) -> bool:
    """Only the Admin sees, and restores, the risks deleted logically."""
    return user.general_profile is GeneralProfile.ADMIN


def list_categories(session: Session) -> list[RiskCategory]:
    """The RBS catalogue, by group and name."""
    statement = select(RiskCategory).order_by(RiskCategory.group, RiskCategory.name)
    return list(session.scalars(statement).all())


def list_risks(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: RiskFilters,
    reference_date: date,
) -> RiskListing:
    """The register for the scope and the filters: lines, KPIs and the options of the filter."""
    rbac.require_module(user, MODULE)
    params = parameters(session, reference_date=reference_date)
    show_deleted = filters.include_deleted and can_see_deleted(user)
    universe = _lines(
        _Ctx(session, user, reference_date),
        project_id=scope.project_id,
        include_hidden=show_deleted,
        params=params,
    )
    based = [line for line in universe if _matches_rest(line, filters, params)]
    shown = [line for line in based if _matches_situation(line, filters)]
    shown.sort(key=lambda line: _sort_key(line, filters.assessment))
    closed_hidden = sum(1 for line in based if not line.active and not line.hidden) - sum(
        1 for line in shown if not line.active and not line.hidden
    )
    page = min(max(filters.page, 1), max(1, -(-len(shown) // validation.PAGE_SIZE)))
    return RiskListing(
        lines=tuple(shown),
        summary=_summary(universe, filters.assessment, params),
        parameters=params,
        projects=_project_options(session, scope, params),
        categories=tuple(list_categories(session)),
        owners=_owner_options(universe),
        page=page,
        closed_hidden=closed_hidden,
    )


def risk_summary(
    session: Session, *, user: User, scope: Scope, assessment: str, reference_date: date
) -> RiskSummary:
    """The KPIs of the register for the scope, without a filter (what the oracle reads)."""
    rbac.require_module(user, MODULE)
    params = parameters(session, reference_date=reference_date)
    universe = _lines(
        _Ctx(session, user, reference_date),
        project_id=scope.project_id,
        include_hidden=False,
        params=params,
    )
    return _summary(universe, assessment, params)


def find_risk(session: Session, *, user: User, code: str, reference_date: date) -> RiskLine | None:
    """The risk with the code, or ``None``; a deleted one only appears to the Admin."""
    rbac.require_module(user, MODULE)
    risk = session.scalars(select(Risk).where(Risk.code == code)).one_or_none()
    if risk is None or (risk.hidden and not can_see_deleted(user)):
        return None
    params = parameters(session, reference_date=reference_date)
    return _build_lines(
        session, user=user, risks=[risk], params=params, reference_date=reference_date
    )[0]


def preview_score(
    session: Session,
    *,
    user: User,
    data: AssessmentInput,
    reference_date: date,
) -> ScorePreview:
    """The score the form previews: the server calculates, the screen only shows it."""
    rbac.require_module(user, MODULE)
    params = parameters(session, reference_date=reference_date)
    least = calculations.resulting_impact(data.dimensions)
    impact = max(data.impact or 0, least)
    probability = data.probability or 0
    valid = (
        calculations.MIN_LEVEL <= probability <= calculations.MAX_LEVEL
        and calculations.MIN_LEVEL <= impact <= calculations.MAX_LEVEL
    )
    if not valid:
        return ScorePreview(least, impact or None, None, None, None, None, None)
    score = calculations.risk_score(probability, impact)
    band = calculations.risk_severity(score, params.scale, life_risk=data.life_risk)
    vme = (
        None
        if data.cost_impact_cents is None
        else calculations.expected_monetary_value(
            probability, data.cost_impact_cents, params.probabilities
        )
    )
    return ScorePreview(
        minimum_impact=least,
        impact=impact,
        score=score,
        severity=band,
        mean_pct=calculations.probability_mean_pct(probability, params.probabilities),
        cadence_days=calculations.review_cadence(band.id, params.cadence_days),
        vme_cents=vme,
    )


# ── Writing ──────────────────────────────────────────────────────────────────────────────────


def save_risk(session: Session, *, user: User, data: RiskInput, reference_date: date) -> SaveResult:
    """Create the risk (the code is reserved here) or edit its identification.

    ``data.code`` is the risk being edited, ``None`` for a new one; ``data.project_id`` is the
    project of a new risk.
    """
    rbac.require(user, Permission.WRITE)
    existing = _editable(session, data.code) if data.code else None
    problems = validation.identification_problems(
        data,
        reference_date=reference_date,
        system_origin=existing is not None and _is_system_origin(existing),
    )
    problems.update(_identification_register_problems(session, data, existing))
    target = existing.project_id if existing else data.project_id
    if existing is None and (target is None or not _project_exists(session, target)):
        problems["projeto"] = UNKNOWN_PROJECT_MESSAGE
    if problems:
        raise InvalidDataError(problems)
    # Sem problemas, o projeto está definido: a edição traz o dono do risco e a inclusão passou
    # pela checagem acima.
    project_id = cast(int, target)
    notices = _duplicate_notices(session, project_id, data.title, ignore=existing)
    ctx = _Ctx(session, user, reference_date)
    if existing is None:
        return SaveResult(
            _create_risk(ctx, data, project_id=project_id).code, created=True, notices=notices
        )
    _update_identification(ctx, existing, data)
    return SaveResult(existing.code, created=False, notices=notices)


def assess_risk(
    session: Session,
    *,
    user: User,
    code: str,
    data: AssessmentInput,
    reference_date: date,
) -> AssessmentResult:
    """Record an inherent or residual assessment: the only place P and I change besides the review."""
    rbac.require(user, Permission.WRITE)
    ctx = _Ctx(session, user, reference_date)
    risk = _editable(session, code)
    params = parameters(session, reference_date=reference_date)
    latest = _latest_assessments(session, [risk.id]).get(risk.id, {})
    _check_assessment(risk, data)
    score = calculations.risk_score(data.probability or 0, data.impact or 0)
    before = _previous_score(latest, data.kind)
    _check_assessment_rules(risk, data, score=score, before=before, latest=latest)
    band = calculations.risk_severity(score, params.scale, life_risk=data.life_risk)
    previous_band = (
        None
        if before is None
        else calculations.risk_severity(before, params.scale, life_risk=risk.life_risk)
    )
    had_plan = bool(risk.strategy and risk.plan)
    _write_assessment(ctx, risk, data, before)
    situation = _update_after_assessment(ctx, risk, data, params)
    is_top = calculations.severity_rank(band.id, params.scale) == len(params.scale.bands) - 1
    is_threat = risk.nature == THREAT
    return AssessmentResult(
        code=risk.code,
        score=score,
        severity=band,
        requires_plan=is_top and is_threat and not had_plan,
        manager_alert=is_top
        and is_threat
        and (previous_band is None or previous_band.id != band.id),
        situation=situation,
    )


def _check_assessment(risk: Risk, data: AssessmentInput) -> None:
    """The field problems and the rule that the residual waits for the response plan."""
    problems = validation.assessment_problems(data)
    if data.kind not in validation.ASSESSMENT_KINDS:
        problems["tipo"] = validation.CHOOSE_KIND
    elif data.kind == RESIDUAL and not (risk.strategy and risk.plan):
        problems["tipo"] = validation.RESIDUAL_NEEDS_PLAN
    if problems:
        raise InvalidDataError(problems)


def delete_risk(
    session: Session,
    *,
    user: User,
    code: str,
    data: DeletionInput,
    reference_date: date,
) -> None:
    """Delete logically: Gestor, no open action, not closed; reason, author and date are kept."""
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(DELETE_FORBIDDEN_MESSAGE)
    risk = _visible(session, user, code)
    if not calculations.is_active(risk.situation):
        raise InvalidDataError(DELETE_CLOSED_MESSAGE)
    counts = actions.count_actions_of_origin(
        session,
        user=user,
        origin_kind=ORIGIN_KIND,
        references=[risk.code],
        reference_date=reference_date,
    )
    open_count = counts.get(risk.code, OriginActionCount()).open
    if open_count:
        raise InvalidDataError(DELETE_OPEN_ACTIONS_MESSAGE.format(count=open_count))
    problems = validation.deletion_problems(data)
    if problems:
        raise InvalidDataError(problems)
    recording.update(
        session,
        user_id=user.id,
        record=risk,
        changes={
            "hidden": True,
            "deletion_reason": validation.deletion_reason_text(data),
            "hidden_by_id": user.person_id,
            "hidden_at": calendario.now(),
        },
        version=data.version,
    )


def restore_risk(session: Session, *, user: User, code: str) -> None:
    """Restore a deleted risk: only the Admin sees it, so only the Admin restores it."""
    if not can_see_deleted(user):
        raise AccessDeniedError(RESTORE_FORBIDDEN_MESSAGE)
    risk = _visible(session, user, code)
    if not risk.hidden:
        raise InvalidDataError(NOT_DELETED_MESSAGE)
    recording.update(
        session,
        user_id=user.id,
        record=risk,
        changes={
            "hidden": False,
            "deletion_reason": None,
            "hidden_by_id": None,
            "hidden_at": None,
        },
        version=risk.version,
    )


def create_category(session: Session, *, user: User, group: str, name: str) -> RiskCategory:
    """Quick registration of a category of the RBS from the form of the risk."""
    rbac.require(user, Permission.WRITE)
    problems = validation.category_problems(group, name)
    cleaned_group, cleaned_name = group.strip(), name.strip()
    taken = any(
        _normalize(item.group) == _normalize(cleaned_group)
        and _normalize(item.name) == _normalize(cleaned_name)
        for item in list_categories(session)
    )
    if taken:
        problems["nome"] = validation.CATEGORY_DUPLICATED
    if problems:
        raise InvalidDataError(problems)
    category = RiskCategory(group=cleaned_group, name=cleaned_name)
    recording.create(session, user_id=user.id, record=category)
    return category


@dataclass(frozen=True)
class RiskHistory:
    """A risk with the history it already has: its assessments, reviews and approvals."""

    risk: Risk
    assessments: Sequence[RiskAssessment] = ()
    reviews: Sequence[RiskReview] = ()
    approvals: Sequence[RiskPlanApproval] = ()


def record_history(session: Session, *, user: User, history: RiskHistory) -> Risk:
    """Record a risk that already has a history (the load of the demonstration, a migration).

    The risk keeps the code, the dates and the situation it came with; its assessments, reviews
    and approvals are facts and enter in the order given, each one with its trail line.
    """
    rbac.require(user, Permission.WRITE)
    risk = history.risk
    recording.create(session, user_id=user.id, record=risk)
    for fact in (*history.assessments, *history.reviews, *history.approvals):
        fact.risk_id = risk.id
        session.add(fact)
        session.flush()
        audit.created(session, user_id=user.id, entity=fact.__tablename__, record=fact)
    return risk


def reserve_code(session: Session, *, project_id: int, reference_date: date) -> str:
    """Reserve the next code of the project: the numbering lock, then the highest numeric suffix."""
    project = configuracoes.find_project(session, project_id)
    if project is None:
        raise InvalidDataError({"projeto": UNKNOWN_PROJECT_MESSAGE})
    reserved = numbering.next_number(
        session, project=project, kind="risco", reference_date=reference_date
    )
    prefix, _, digits = reserved.rpartition("-")
    codes = session.scalars(select(Risk.code).where(Risk.code.like(f"{prefix}-%"))).all()
    number = max(int(digits), calculations.next_code_number(codes, prefix))
    return calculations.format_code(prefix, number)


# ── Internals: writing ───────────────────────────────────────────────────────────────────────


def _project_exists(session: Session, project_id: int) -> bool:
    return configuracoes.find_project(session, project_id) is not None


def _visible(session: Session, user: User, code: str) -> Risk:
    risk = session.scalars(select(Risk).where(Risk.code == code)).one_or_none()
    if risk is None or (risk.hidden and not can_see_deleted(user)):
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return risk


def _editable(session: Session, code: str | None) -> Risk:
    risk = session.scalars(select(Risk).where(Risk.code == code)).one_or_none()
    if risk is None or risk.hidden:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    if not calculations.is_active(risk.situation):
        raise InvalidDataError(CLOSED_MESSAGE)
    return risk


def _is_system_origin(risk: Risk) -> bool:
    return risk.origin_type not in validation.MANUAL_ORIGINS


def _identification_register_problems(
    session: Session, data: RiskInput, existing: Risk | None
) -> dict[str, str]:
    problems: dict[str, str] = {}
    if data.category_id and session.get(RiskCategory, data.category_id) is None:
        problems["categoria"] = UNKNOWN_CATEGORY_MESSAGE
    if data.owner_id and not configuracoes.find_people(session, [data.owner_id]):
        problems["donoId"] = UNKNOWN_OWNER_MESSAGE
    if existing and existing.strategy and data.nature != existing.nature:
        problems["natureza"] = validation.NATURE_LOCKED
    return problems


def _duplicate_notices(
    session: Session, project_id: int, title: str, *, ignore: Risk | None
) -> tuple[str, ...]:
    wanted = _normalize(title)
    statement = select(Risk).where(Risk.project_id == project_id, Risk.hidden.is_(False))
    for other in session.scalars(statement):
        same = other is not ignore and _normalize(other.title) == wanted
        if same:
            return (DUPLICATE_NOTICE.format(code=other.code),)
    return ()


def _ata_origin(session: Session, data: RiskInput, project_id: int) -> tuple[int | None, str]:
    if data.origin_type != validation.ATA_ORIGIN:
        return None, data.origin_type
    label = next(
        (option.label for option in ata_options(session, project_id) if option.id == data.ata_id),
        "",
    )
    return data.ata_id, f"Ata {label}".strip() if label else validation.ATA_ORIGIN


def _create_risk(ctx: _Ctx, data: RiskInput, *, project_id: int) -> Risk:
    ata_id, origin = _ata_origin(ctx.session, data, project_id)
    risk = Risk(
        project_id=project_id,
        category_id=data.category_id,
        owner_id=data.owner_id,
        identified_by_id=ctx.user.person_id,
        ata_id=ata_id,
        code=reserve_code(ctx.session, project_id=project_id, reference_date=ctx.reference_date),
        title=data.title.strip(),
        nature=data.nature,
        origin_type=data.origin_type,
        origin=origin,
        cause=data.cause.strip(),
        consequence=data.consequence.strip(),
        description=data.description.strip() or None,
        trigger=data.trigger.strip() or None,
        situation=SITUATION_IDENTIFIED,
        identified_on=data.identified_on,
    )
    recording.create(ctx.session, user_id=ctx.user.id, record=risk)
    return risk


def _update_identification(ctx: _Ctx, risk: Risk, data: RiskInput) -> None:
    changes: dict[str, object] = {
        "category_id": data.category_id,
        "owner_id": data.owner_id,
        "title": data.title.strip(),
        "nature": data.nature,
        "cause": data.cause.strip(),
        "consequence": data.consequence.strip(),
        "description": data.description.strip() or None,
        "trigger": data.trigger.strip() or None,
        "identified_on": data.identified_on,
    }
    if not _is_system_origin(risk):
        ata_id, origin = _ata_origin(ctx.session, data, risk.project_id)
        changes.update({"origin_type": data.origin_type, "ata_id": ata_id, "origin": origin})
    recording.update(
        ctx.session, user_id=ctx.user.id, record=risk, changes=changes, version=data.version
    )


def _previous_score(latest: Mapping[str, RiskAssessment], kind: str) -> int | None:
    reference = (
        latest.get(RESIDUAL) or latest.get(INHERENT) if kind == RESIDUAL else latest.get(INHERENT)
    )
    return None if reference is None else reference.probability * reference.impact


def _check_assessment_rules(
    risk: Risk,
    data: AssessmentInput,
    *,
    score: int,
    before: int | None,
    latest: Mapping[str, RiskAssessment],
) -> None:
    """The rules that need the history: residual above inherent, and the justification."""
    problems: dict[str, str] = {}
    base = latest.get(INHERENT)
    base_score = None if base is None else base.probability * base.impact
    if data.kind == RESIDUAL and calculations.residual_exceeds_inherent(
        risk.nature, score, base_score
    ):
        problems["p"] = validation.RESIDUAL_ABOVE_INHERENT
    justified = len((data.justification or "").strip()) >= validation.MIN_TEXT
    if calculations.justification_required(before, score) and not justified:
        problems["justificativa"] = validation.JUSTIFICATION_REQUIRED
    if problems:
        raise InvalidDataError(problems)


def _dimension_columns(dimensions: Mapping[str, int | None]) -> dict[str, int | None]:
    columns = {
        "prazo": "schedule_dimension",
        "custo": "cost_dimension",
        "escopo": "scope_dimension",
        "sms": "safety_dimension",
        "imagem": "image_dimension",
        "legal": "legal_dimension",
    }
    return {column: dimensions.get(key) or None for key, column in columns.items()}


def _write_assessment(ctx: _Ctx, risk: Risk, data: AssessmentInput, before: int | None) -> None:
    """The assessment and its line of the timeline, both facts: they are never edited."""
    score = calculations.risk_score(data.probability or 0, data.impact or 0)
    assessment = RiskAssessment(
        risk_id=risk.id,
        author_id=ctx.user.person_id,
        kind=data.kind,
        probability=data.probability,
        impact=data.impact,
        assessed_on=ctx.reference_date,
        **_dimension_columns(data.dimensions),
    )
    ctx.session.add(assessment)
    ctx.session.flush()
    audit.created(
        ctx.session, user_id=ctx.user.id, entity=assessment.__tablename__, record=assessment
    )
    review = RiskReview(
        risk_id=risk.id,
        author_id=ctx.user.person_id,
        reviewed_on=ctx.reference_date,
        kind=data.kind,
        assessed_situation=_assessed_situation(before, score),
        score_from=before,
        score_to=score,
        probability=data.probability,
        impact=data.impact,
        trigger_occurred=False,
        body=(data.justification or "").strip()
        or ("Avaliação inicial." if before is None else "Avaliação residual."),
    )
    ctx.session.add(review)
    ctx.session.flush()
    audit.created(ctx.session, user_id=ctx.user.id, entity=review.__tablename__, record=review)


def _assessed_situation(before: int | None, score: int) -> str:
    if before is None:
        return "Avaliação inicial"
    if score < before:
        return "Risco reduzido"
    return "Risco agravado" if score > before else "Sem mudança"


def _update_after_assessment(
    ctx: _Ctx, risk: Risk, data: AssessmentInput, params: RiskParameters
) -> str:
    """Life risk, impacts, cadence and next review, and the situation the assessment moves."""
    latest = _latest_assessments(ctx.session, [risk.id]).get(risk.id, {})
    current = latest.get(RESIDUAL) or latest[INHERENT]
    score = calculations.risk_score(current.probability, current.impact)
    band = calculations.risk_severity(score, params.scale, life_risk=data.life_risk)
    cadence = calculations.review_cadence(band.id, params.cadence_days)
    changes: dict[str, object] = {
        "life_risk": data.life_risk,
        "dimension": _worst_dimension(data.dimensions),
        "cadence_days": cadence,
        "last_review": ctx.reference_date,
        "next_review": ctx.reference_date + timedelta(days=cadence),
        "situation": _situation_after(ctx, risk, data),
    }
    if data.schedule_impact_days is not None:
        changes["schedule_impact_days"] = data.schedule_impact_days
    if data.cost_impact_cents is not None:
        changes["cost_impact_cents"] = data.cost_impact_cents
    recording.update(
        ctx.session,
        user_id=ctx.user.id,
        record=risk,
        changes=changes,
        version=data.version or risk.version,
    )
    return risk.situation


def _worst_dimension(dimensions: Mapping[str, int | None]) -> str | None:
    worst = calculations.resulting_impact(dimensions)
    return next((label for key, label in DIMENSIONS if dimensions.get(key) == worst), None)


def _situation_after(ctx: _Ctx, risk: Risk, data: AssessmentInput) -> str:
    if risk.situation == SITUATION_IDENTIFIED:
        return SITUATION_ANALYSIS
    if data.kind != RESIDUAL or risk.situation != SITUATION_TREATMENT:
        return risk.situation
    pending = _latest_approvals(ctx.session, [risk.id]).get(risk.id) == APPROVAL_PENDING
    counts = actions.count_actions_of_origin(
        ctx.session,
        user=ctx.user,
        origin_kind=ORIGIN_KIND,
        references=[risk.code],
        reference_date=ctx.reference_date,
    ).get(risk.code, OriginActionCount())
    done = counts.total > 0 and counts.open == 0
    return SITUATION_MONITORED if done and not pending else risk.situation


# ── Internals: reading ───────────────────────────────────────────────────────────────────────


def _lines(
    ctx: _Ctx, *, project_id: int | None, include_hidden: bool, params: RiskParameters
) -> list[RiskLine]:
    statement = select(Risk).order_by(Risk.id)
    if project_id is not None:
        statement = statement.where(Risk.project_id == project_id)
    if not include_hidden:
        statement = statement.where(Risk.hidden.is_(False))
    risks = list(ctx.session.scalars(statement).all())
    return _build_lines(
        ctx.session,
        user=ctx.user,
        risks=risks,
        params=params,
        reference_date=ctx.reference_date,
    )


def _build_lines(
    session: Session,
    *,
    user: User,
    risks: Sequence[Risk],
    params: RiskParameters,
    reference_date: date,
) -> list[RiskLine]:
    ids = [risk.id for risk in risks]
    latest = _latest_assessments(session, ids)
    approvals = _latest_approvals(session, ids)
    reviewed = _reviewed_ids(session, ids)
    categories = {category.id: category for category in list_categories(session)}
    owners = configuracoes.find_people(session, {risk.owner_id for risk in risks})
    counts = actions.count_actions_of_origin(
        session,
        user=user,
        origin_kind=ORIGIN_KIND,
        references=[risk.code for risk in risks],
        reference_date=reference_date,
    )
    return [
        _line_of(
            risk,
            params=params,
            reference_date=reference_date,
            parts=_Parts(
                assessments=latest.get(risk.id, {}),
                approval=approvals.get(risk.id),
                reviewed=risk.id in reviewed,
                category=categories[risk.category_id],
                owner_name=owners[risk.owner_id].name if risk.owner_id in owners else "",
                actions=counts.get(risk.code, OriginActionCount()),
            ),
        )
        for risk in risks
    ]


@dataclass(frozen=True)
class _Ctx:
    """The session, the author and the reference date a private helper of a write needs."""

    session: Session
    user: User
    reference_date: date


@dataclass(frozen=True)
class _Parts:
    """What is read around a risk to build its line."""

    assessments: Mapping[str, RiskAssessment]
    approval: str | None
    reviewed: bool
    category: RiskCategory
    owner_name: str
    actions: OriginActionCount


def _view_of(
    assessment: RiskAssessment | None, risk: Risk, params: RiskParameters
) -> AssessmentView | None:
    if assessment is None:
        return None
    score = calculations.risk_score(assessment.probability, assessment.impact)
    return AssessmentView(
        probability=assessment.probability,
        impact=assessment.impact,
        dimensions={
            "prazo": assessment.schedule_dimension,
            "custo": assessment.cost_dimension,
            "escopo": assessment.scope_dimension,
            "sms": assessment.safety_dimension,
            "imagem": assessment.image_dimension,
            "legal": assessment.legal_dimension,
        },
        score=score,
        severity=calculations.risk_severity(score, params.scale, life_risk=risk.life_risk),
        assessed_on=assessment.assessed_on,
    )


def _line_of(
    risk: Risk, *, params: RiskParameters, reference_date: date, parts: _Parts
) -> RiskLine:
    inherent = _view_of(parts.assessments.get(INHERENT), risk, params)
    residual = _view_of(parts.assessments.get(RESIDUAL), risk, params)
    current = residual or inherent
    active = calculations.is_active(risk.situation)
    vme = (
        calculations.expected_monetary_value(
            current.probability, risk.cost_impact_cents, params.probabilities
        )
        if current
        else 0
    )
    return RiskLine(
        id=risk.id,
        project_id=risk.project_id,
        code=risk.code,
        title=risk.title,
        nature=risk.nature,
        category_id=risk.category_id,
        category_group=parts.category.group,
        category_name=parts.category.name,
        owner_id=risk.owner_id,
        owner_name=parts.owner_name,
        identified_on=risk.identified_on,
        origin_type=risk.origin_type,
        origin=risk.origin,
        ata_id=risk.ata_id,
        cause=risk.cause,
        consequence=risk.consequence,
        description=risk.description,
        trigger=risk.trigger,
        life_risk=risk.life_risk,
        cost_impact_cents=risk.cost_impact_cents,
        schedule_impact_days=risk.schedule_impact_days,
        strategy=risk.strategy,
        plan=risk.plan,
        target_severity=risk.target_severity,
        situation=risk.situation,
        hidden=risk.hidden,
        deletion_reason=risk.deletion_reason,
        version=risk.version,
        cadence_days=risk.cadence_days,
        next_review=risk.next_review,
        inherent=inherent,
        residual=residual,
        current=current,
        vme_cents=vme,
        active=active,
        review_overdue=calculations.is_review_overdue(
            risk.next_review, reference_date, active=active
        ),
        days_to_review=calculations.days_until(risk.next_review, reference_date),
        never_reviewed=not parts.reviewed and not parts.assessments,
        plan_pending=bool(risk.strategy and risk.plan) and parts.approval == APPROVAL_PENDING,
        actions=parts.actions,
    )


def _latest_assessments(
    session: Session, risk_ids: Collection[int]
) -> dict[int, dict[str, RiskAssessment]]:
    """The newest assessment of each kind, per risk."""
    latest: dict[int, dict[str, RiskAssessment]] = {}
    if not risk_ids:
        return latest
    statement = (
        select(RiskAssessment)
        .where(RiskAssessment.risk_id.in_(list(risk_ids)))
        .order_by(RiskAssessment.id)
    )
    for assessment in session.scalars(statement):
        latest.setdefault(assessment.risk_id, {})[assessment.kind] = assessment
    return latest


def _latest_approvals(session: Session, risk_ids: Collection[int]) -> dict[int, str]:
    """The situation of the newest approval request of each risk."""
    if not risk_ids:
        return {}
    statement = (
        select(RiskPlanApproval)
        .where(RiskPlanApproval.risk_id.in_(list(risk_ids)))
        .order_by(RiskPlanApproval.id)
    )
    return {item.risk_id: item.situation for item in session.scalars(statement)}


def _reviewed_ids(session: Session, risk_ids: Collection[int]) -> set[int]:
    if not risk_ids:
        return set()
    statement = select(RiskReview.risk_id).where(RiskReview.risk_id.in_(list(risk_ids)))
    return set(session.scalars(statement))


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return " ".join(plain.casefold().split())


def _sort_key(line: RiskLine, assessment: str) -> tuple[int, str]:
    shown = line.displayed(assessment)
    return (-(shown.score if shown else 0), line.code)


def _matches_situation(line: RiskLine, filters: RiskFilters) -> bool:
    if filters.situation == validation.SITUATION_ALL:
        return True
    if filters.situation == validation.SITUATION_ACTIVE:
        return line.active or (filters.include_closed and not line.hidden)
    return line.situation == filters.situation or (filters.include_closed and not line.active)


def _matches_rest(line: RiskLine, filters: RiskFilters, params: RiskParameters) -> bool:
    shown = line.displayed(filters.assessment)
    checks: Iterable[bool] = (
        not filters.nature or line.nature == filters.nature,
        not filters.category or filters.category in (line.category_group, line.category_label),
        not filters.strategy or line.strategy == filters.strategy,
        filters.owner_id is None or line.owner_id == filters.owner_id,
        not filters.severities or (shown is not None and shown.severity.id in filters.severities),
        _matches_cell(shown, filters),
        _matches_review(line, filters, params),
        filters.identified_from is None or line.identified_on >= filters.identified_from,
        filters.identified_until is None or line.identified_on <= filters.identified_until,
        _matches_search(line, filters.search),
    )
    return all(checks)


def _matches_cell(shown: AssessmentView | None, filters: RiskFilters) -> bool:
    if filters.probability is None or filters.impact is None:
        return True
    return (
        shown is not None
        and shown.probability == filters.probability
        and shown.impact == filters.impact
    )


def _matches_review(line: RiskLine, filters: RiskFilters, params: RiskParameters) -> bool:
    if filters.review == "vencidas":
        return line.review_overdue
    if filters.review == "proximas":
        remaining = line.days_to_review
        return line.active and remaining is not None and 0 <= remaining <= params.review_alert_days
    if filters.review == "sem":
        return line.never_reviewed
    return True


def _matches_search(line: RiskLine, search: str) -> bool:
    if not search:
        return True
    text = " ".join((line.code, line.title, line.cause, line.consequence, line.owner_name))
    return _normalize(search) in _normalize(text)


def _band_count(active: Sequence[RiskLine], band: Band, assessment: str) -> BandCount:
    in_band = [
        line
        for line in active
        if (shown := line.displayed(assessment)) and shown.severity.id == band.id
    ]
    goal = sum(
        1
        for line in active
        if (line.target_severity if line.has_plan and line.target_severity else _current_id(line))
        == band.id
    )
    opportunities = sum(1 for line in in_band if line.nature != THREAT)
    return BandCount(
        band=band,
        total=len(in_band),
        threats=len(in_band) - opportunities,
        opportunities=opportunities,
        goal=goal,
    )


def _current_id(line: RiskLine) -> str | None:
    return line.current.severity.id if line.current else None


def _summary(universe: Sequence[RiskLine], assessment: str, params: RiskParameters) -> RiskSummary:
    visible = [line for line in universe if not line.hidden]
    active = [line for line in visible if line.active]
    bands = list(reversed(params.scale.bands))
    treatment = [line for line in active if line.situation == SITUATION_TREATMENT]
    exposure = calculations.threat_exposure((line.nature, line.vme_cents) for line in active)
    return RiskSummary(
        assessment=assessment,
        active=len(active),
        registered=len(visible),
        unassessed=sum(1 for line in active if line.inherent is None),
        top=_band_count(active, bands[0], assessment),
        second=_band_count(active, bands[1], assessment) if len(bands) > 1 else None,
        in_treatment=len(treatment),
        expected_in_treatment=sum(
            1 for line in active if line.has_plan and line.strategy != "Aceitar"
        ),
        overdue=tuple(line for line in active if line.review_overdue),
        exposure_cents=exposure,
    )


def _project_options(
    session: Session, scope: Scope, params: RiskParameters
) -> tuple[ProjectOption, ...]:
    bands = {band.id: band for band in params.scale.bands}
    return tuple(
        ProjectOption(
            id=item.id,
            code=item.code,
            name=item.name,
            client_acronym=item.client_acronym,
            risk_pattern=item.risk_pattern,
            appetite=bands.get(item.risk_appetite or ""),
        )
        for item in configuracoes.list_project_risk_contexts(session)
        if scope.project_id in (None, item.id)
    )


def _owner_options(universe: Sequence[RiskLine]) -> tuple[tuple[int, str], ...]:
    names = {line.owner_id: line.owner_name for line in universe}
    return tuple(sorted(names.items(), key=lambda item: item[1]))


def with_page(filters: RiskFilters, page: int) -> RiskFilters:
    """The same filters on another page."""
    return replace(filters, page=page)


origin_links.register(
    origin_links.OriginLinkType(
        kind=ORIGIN_KIND,
        build=lambda ref: origin_links.link_to_screen("riscos/ficha", codigo=ref.reference),
    )
)
