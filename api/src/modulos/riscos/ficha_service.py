"""Business facade of the ficha do risco: plan, reviews, closing and reopening (ISSUE-065).

The ficha of a risk shows the inherent and the residual assessment, the situation, the alerts and
the timeline; this facade answers it and writes what its modals ask: the response plan (with the
approval of the manager, segregated from the person responsible for the plan, D7), the periodic
review (whose cadence comes from the severity and is never postponed), the closing (which creates
the lesson in Rascunho, the action of the materialized problem and the change request, all in the
same transaction, D9) and the reopening.

Everything the ficha reads of another module goes through its facade: the actions of the origin
``Risco`` through the Central de Ações, the changes and the lessons through Governança. Score,
severity, VME, the escalation agenda and the history are calculated on every query (D6); the
history is the audit trail, read by column diff.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.core import audit, calendario, notification, origin_links, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.export_document import ValueKind, format_value
from src.core.models import AuditEntry
from src.core.rbac import Conflict, Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.calculations import ActionStatus
from src.modulos.central_acoes.validation import NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import lessons_models as lessons
from src.modulos.governanca import lessons_service
from src.modulos.governanca import service as governanca
from src.modulos.governanca.lessons_validation import DraftInput
from src.modulos.riscos import calculations, service, validation
from src.modulos.riscos.calculations import Band, RiskParameters
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
    ActionInput,
    ApprovalInput,
    ClosingInput,
    PlanInput,
    ReopenInput,
    ReviewInput,
)

MODULE = "riscos"
ORIGIN_KIND = "Risco"
RISK_ENTITY = "risco"
HISTORY_ENTITY = "risco.historico"
PLAN_ACTION_GROUP = "Plano de resposta"
PROBLEM_ACTION_GROUP = "Problema"
APPROVAL_ENTITY = "risco_plano_aprovacao"

PLAN_CLOSED_MESSAGE = "Risco encerrado não pode ter o plano alterado."
REVIEW_CLOSED_MESSAGE = "Risco encerrado não recebe revisões."
ACTION_CLOSED_MESSAGE = "Risco encerrado não recebe novas ações."
APPROVAL_DENIED_MESSAGE = "Aprovação do plano exige perfil Gestor."
SELF_APPROVAL_MESSAGE = "O responsável pelo plano não pode aprová-lo (segregação de funções)."
CLOSING_DENIED_MESSAGE = (
    "Encerrar risco exige perfil Gestor. Membro pode propor o encerramento na revisão."
)
ALREADY_CLOSED_MESSAGE = "O risco já está encerrado."
REOPEN_DENIED_MESSAGE = "Reabrir risco exige perfil Gestor."
NOT_CLOSED_MESSAGE = "O risco não está encerrado."
UNKNOWN_PERSON_MESSAGE = "A pessoa informada não está no cadastro."
SM_TITLE = "Tratamento do risco materializado {code}"
SM_DESCRIPTION = "{title}. Impacto real: {days} dias e {money}."
SM_ACTION_SUBJECT = "Registrar SM da mudança de solução do risco {code}"
SM_ACTION_DESCRIPTION = (
    "Estratégia Evitar: registrar a solicitação de mudança no módulo 08 e vincular ao plano."
)
PROBLEM_ACTION_DESCRIPTION = "Risco materializado: tratar o problema."
SM_ACTION_DAYS = 7
LESSON_TITLE_LIMIT = 110
SITUATION_MATERIALIZED = "Materializado"
SITUATION_CLOSED = "Encerrado"
NOTIFY_SUBJECT = "Revisão do risco {code}"
NOTIFY_BODY = (
    "Revisão registrada em {date}: score de {previous} para {score} ({band}). "
    "Próxima revisão em {next}."
)
NOTIFY_NO_EMAIL = "O dono e o gestor do projeto não têm e-mail cadastrado: nada foi enviado."

# The columns of the identification whose change the history names.
IDENTIFICATION_FIELDS: tuple[tuple[str, str], ...] = (
    ("titulo", "evento"),
    ("causa", "causa"),
    ("consequencia", "consequência"),
    ("descricao", "descrição"),
    ("gatilho", "gatilho"),
    ("dono_id", "dono"),
    ("categoria_id", "categoria"),
    ("identificado_em", "data de identificação"),
    ("origem", "origem"),
    ("natureza", "natureza"),
)


@dataclass(frozen=True)
class ReviewLine:
    """One entry of the timeline of the ficha: an assessment or a periodic review."""

    reviewed_on: date
    author_name: str
    kind: str
    assessed_situation: str
    score_from: int | None
    score_to: int
    probability: int
    impact: int
    trigger_occurred: bool
    body: str | None
    severity_name: str | None


@dataclass(frozen=True)
class HistoryLine:
    """One line of the audit trail as the ficha prints it: when, who and what changed."""

    moment: datetime
    author_name: str
    text: str


@dataclass(frozen=True)
class ActionView:
    """One action of the response plan, read from the Central de Ações (D9)."""

    id: int
    item: str | None
    group: str | None
    subject: str
    description: str | None
    responsible_name: str
    planned_date: date | None
    replanned_date: date | None
    completed_on: date | None
    status: str
    status_label: str
    days_overdue: int
    contributes_probability: bool
    contributes_impact: bool
    url: str

    @property
    def due_date(self) -> date | None:
        """The deadline in force: the replanned date, or the planned one when never replanned."""
        return self.replanned_date or self.planned_date

    @property
    def overdue(self) -> bool:
        """Whether the action is past its deadline on the reference date."""
        return self.status == ActionStatus.OVERDUE.value


@dataclass(frozen=True)
class RecordLink:
    """A record of another module the ficha points back to: the number, the title and the situation."""

    code: str
    title: str
    situation: str


@dataclass(frozen=True)
class RiskSheet:
    """Everything the ficha shows: the line of the risk, the plan, the timeline and the history."""

    line: service.RiskLine
    project_label: str
    owner_name: str
    identified_by_name: str
    plan_responsible_name: str
    closed_by_name: str
    approval: RiskPlanApproval | None
    reviews: tuple[ReviewLine, ...]
    history: tuple[HistoryLine, ...]
    actions: tuple[ActionView, ...]
    pauta: tuple[str, ...]
    trigger_on: date | None
    cadence_days: int | None
    vme_inherent_cents: int
    change: RecordLink | None
    closing_change: RecordLink | None
    lesson: RecordLink | None

    @property
    def approval_situation(self) -> str:
        """The situation of the newest approval row; empty when the plan never asked for one."""
        return self.approval.situation if self.approval else ""

    @property
    def approval_pending(self) -> bool:
        """Whether the plan awaits the manager's decision."""
        return self.approval_situation == validation.APPROVAL_PENDING

    @property
    def approval_returned(self) -> bool:
        """Whether the manager returned the plan for revision."""
        return self.approval_situation == validation.APPROVAL_RETURNED


@dataclass(frozen=True)
class PlanResult:
    """What saving the plan answers: the situation, the pending approval and the residual."""

    code: str
    situation: str
    approval_pending: bool
    enables_residual: bool


@dataclass(frozen=True)
class ApprovalResult:
    """What the approval decision answers: the situation of the risk."""

    code: str
    situation: str


@dataclass(frozen=True)
class ReviewResult:
    """What a periodic review answers: the score, what follows it and the notification."""

    code: str
    score: int
    severity: Band
    closes_with: str | None
    re_assess: bool
    notification: str | None


@dataclass(frozen=True)
class ClosingResult:
    """What the closing answers: the situation and the records created in the same transaction."""

    code: str
    situation: str
    lesson_code: str
    change_code: str | None
    action_item: str | None


@dataclass(frozen=True)
class ReopenResult:
    """What the reopening answers: the situation the risk came back to."""

    code: str
    situation: str


@dataclass(frozen=True)
class ActionResult:
    """What creating an action answers: the item created in the Central de Ações."""

    item: str | None
    subject: str


@dataclass(frozen=True)
class _Ctx:
    """The session, the user, the reference date and the parameters a read of the ficha needs."""

    session: Session
    user: User
    reference_date: date
    parameters: RiskParameters


# ── Reading: the ficha ───────────────────────────────────────────────────────────────────────


def find_risk_sheet(
    session: Session, *, user: User, code: str, reference_date: date
) -> RiskSheet | None:
    """The ficha of the risk with the code, or ``None``; a deleted one only appears to the Admin."""
    rbac.require_module(user, MODULE)
    risk = session.scalars(select(Risk).where(Risk.code == code)).one_or_none()
    if risk is None or (risk.hidden and not service.can_see_deleted(user)):
        return None
    params = service.parameters(session, reference_date=reference_date)
    line = service._build_lines(
        session, user=user, risks=[risk], params=params, reference_date=reference_date
    )[0]
    return _sheet_of(_Ctx(session, user, reference_date, params), risk, line)


def sibling_risks(
    session: Session, *, user: User, code: str, reference_date: date
) -> tuple[service.RiskLine, ...]:
    """The other risks of the project: the options of the reason Duplicado at the closing."""
    rbac.require_module(user, MODULE)
    risk = session.scalars(select(Risk).where(Risk.code == code)).one_or_none()
    if risk is None:
        return ()
    params = service.parameters(session, reference_date=reference_date)
    lines = service._lines(
        service._Ctx(session, user, reference_date),
        project_id=risk.project_id,
        include_hidden=False,
        params=params,
    )
    return tuple(line for line in lines if line.code != code)


def _sheet_of(ctx: _Ctx, risk: Risk, line: service.RiskLine) -> RiskSheet:
    names = configuracoes.find_people(
        ctx.session,
        {
            risk.owner_id,
            risk.identified_by_id,
            risk.plan_responsible_id or 0,
            risk.closed_by_id or 0,
        },
    )
    trigger_on = line.trigger_on
    return RiskSheet(
        line=line,
        project_label=_project_label(ctx, risk.project_id),
        owner_name=names[risk.owner_id].name if risk.owner_id in names else "",
        identified_by_name=(
            names[risk.identified_by_id].name if risk.identified_by_id in names else ""
        ),
        plan_responsible_name=(
            names[risk.plan_responsible_id].name if risk.plan_responsible_id in names else ""
        ),
        closed_by_name=names[risk.closed_by_id].name if risk.closed_by_id in names else "",
        approval=_latest_approval(ctx.session, risk.id),
        reviews=_reviews_of(ctx, risk),
        history=_history_of(ctx.session, risk),
        actions=_actions_of(ctx, risk),
        pauta=_pauta_of(ctx, risk, line, trigger_on),
        trigger_on=trigger_on,
        cadence_days=_cadence_of(ctx, line),
        vme_inherent_cents=_inherent_vme(ctx, risk, line),
        change=_change_link(ctx, risk.change_id, risk.project_id),
        closing_change=_change_link(ctx, risk.closing_change_id, risk.project_id),
        lesson=_lesson_link(ctx, risk.lesson_id),
    )


def _project_label(ctx: _Ctx, project_id: int) -> str:
    for item in configuracoes.list_project_risk_contexts(ctx.session):
        if item.id == project_id:
            return f"{item.code} · {item.name}"
    return ""


def _latest_approval(session: Session, risk_id: int) -> RiskPlanApproval | None:
    statement = (
        select(RiskPlanApproval)
        .where(RiskPlanApproval.risk_id == risk_id)
        .order_by(RiskPlanApproval.id.desc())
        .limit(1)
    )
    return session.scalars(statement).first()


def _reviews_of(ctx: _Ctx, risk: Risk) -> tuple[ReviewLine, ...]:
    """The timeline, newest first: every assessment and every review of the risk."""
    statement = (
        select(RiskReview).where(RiskReview.risk_id == risk.id).order_by(RiskReview.id.desc())
    )
    rows = list(ctx.session.scalars(statement).all())
    names = configuracoes.person_names(ctx.session, {row.author_id for row in rows})
    return tuple(
        ReviewLine(
            reviewed_on=row.reviewed_on,
            author_name=names.get(row.author_id, ""),
            kind=row.kind,
            assessed_situation=row.assessed_situation,
            score_from=row.score_from,
            score_to=row.score_to,
            probability=row.probability,
            impact=row.impact,
            trigger_occurred=row.trigger_occurred,
            body=row.body,
            severity_name=_severity_name(ctx.parameters, row.score_to, life_risk=risk.life_risk),
        )
        for row in rows
    )


def _severity_name(params: RiskParameters, score: int, *, life_risk: bool) -> str:
    return calculations.risk_severity(score, params.scale, life_risk=life_risk).name


def _cadence_of(ctx: _Ctx, line: service.RiskLine) -> int | None:
    if line.current is None:
        return None
    return calculations.review_cadence(line.current.severity.id, ctx.parameters.cadence_days)


def _inherent_vme(ctx: _Ctx, risk: Risk, line: service.RiskLine) -> int:
    if line.inherent is None:
        return 0
    return calculations.expected_monetary_value(
        line.inherent.probability, risk.cost_impact_cents, ctx.parameters.probabilities
    )


def _pauta_of(
    ctx: _Ctx, risk: Risk, line: service.RiskLine, trigger_on: date | None
) -> tuple[str, ...]:
    facts = calculations.PautaFacts(
        active=line.active,
        situation=line.situation,
        nature=line.nature,
        inherent_band_id=line.inherent.severity.id if line.inherent else None,
        current_band_id=line.current.severity.id if line.current else None,
        inherent_score=line.inherent.score if line.inherent else None,
        residual_score=line.residual.score if line.residual else None,
        has_plan=line.has_plan,
        plan_pending=line.plan_pending,
        target_band_id=risk.target_severity,
        days_to_target=calculations.days_until(risk.target_date, ctx.reference_date),
        review_overdue=line.review_overdue,
        trigger_on=trigger_on,
    )
    return calculations.pauta_reasons(facts, ctx.parameters)


def _actions_of(ctx: _Ctx, risk: Risk) -> tuple[ActionView, ...]:
    records = actions.actions_of_origin(
        ctx.session,
        user=ctx.user,
        origin_kind=ORIGIN_KIND,
        reference=risk.code,
        reference_date=ctx.reference_date,
    )
    names = configuracoes.person_names(ctx.session, {row.responsible_id for row in records})
    url = origin_links.link_to_screen("central_acoes/acoes", busca=risk.code, status="todos") or ""
    return tuple(
        ActionView(
            id=row.id,
            item=row.item,
            group=row.group,
            subject=row.subject,
            description=row.description,
            responsible_name=names.get(row.responsible_id, ""),
            planned_date=row.planned_date,
            replanned_date=row.replanned_date,
            completed_on=row.completed_on,
            status=row.status.value,
            status_label=row.status_label,
            days_overdue=row.days_overdue,
            contributes_probability=row.contributes_probability,
            contributes_impact=row.contributes_impact,
            url=url,
        )
        for row in _by_item(records)
    )


def _by_item(records: Sequence[actions.ActionRecord]) -> list[actions.ActionRecord]:
    return sorted(records, key=lambda row: _item_number(row.item))


def _item_number(item: str | None) -> int:
    text = (item or "").strip()
    return int(text) if text.isdigit() else 0


def _change_link(ctx: _Ctx, change_id: int | None, project_id: int) -> RecordLink | None:
    if not change_id:
        return None
    for option in governanca.change_options(ctx.session, project_id=project_id):
        if option.id == change_id:
            return RecordLink(option.code, option.title, option.situation)
    return None


def _lesson_link(ctx: _Ctx, lesson_id: int | None) -> RecordLink | None:
    if not lesson_id:
        return None
    for option in lessons_service.lesson_options(ctx.session, lesson_ids=[lesson_id]):
        return RecordLink(option.code, option.title, option.situation)
    return None


# ── Reading: the history ─────────────────────────────────────────────────────────────────────


def _history_of(session: Session, risk: Risk) -> tuple[HistoryLine, ...]:
    """The audit trail of the risk and its facts, newest first, as the ficha prints it."""
    assessment_ids = select(RiskAssessment.id).where(RiskAssessment.risk_id == risk.id)
    review_ids = select(RiskReview.id).where(RiskReview.risk_id == risk.id)
    approval_ids = select(RiskPlanApproval.id).where(RiskPlanApproval.risk_id == risk.id)
    statement = (
        select(AuditEntry)
        .where(
            or_(
                and_(
                    AuditEntry.entity.in_((RISK_ENTITY, HISTORY_ENTITY)),
                    AuditEntry.record_id == risk.id,
                ),
                and_(
                    AuditEntry.entity == "risco_avaliacao",
                    AuditEntry.record_id.in_(assessment_ids),
                ),
                and_(
                    AuditEntry.entity == "risco_revisao",
                    AuditEntry.record_id.in_(review_ids),
                ),
                and_(
                    AuditEntry.entity == APPROVAL_ENTITY,
                    AuditEntry.record_id.in_(approval_ids),
                ),
            )
        )
        .order_by(AuditEntry.occurred_at.desc(), AuditEntry.id.desc())
    )
    lines: list[HistoryLine] = []
    for entry in session.scalars(statement).all():
        text = _history_text(entry)
        if not text:
            continue
        lines.append(
            HistoryLine(
                moment=calendario.in_product_timezone(entry.occurred_at),
                author_name=audit.author_name(session, entry.user_id),
                text=text,
            )
        )
    return tuple(lines)


def _history_text(entry: AuditEntry) -> str | None:
    after = entry.after or {}
    before = entry.before or {}
    if entry.entity == HISTORY_ENTITY:
        return str(after.get("texto") or "")
    if entry.entity == RISK_ENTITY:
        return _risk_history_text(entry.action, before, after)
    if entry.entity == "risco_avaliacao":
        score = int(after.get("p") or 0) * int(after.get("i") or 0)
        return f"Avaliação {after.get('tipo')} registrada: {score} (P{after.get('p')} x I{after.get('i')})."
    if entry.entity == "risco_revisao":
        return _review_history_text(after)
    if entry.entity == APPROVAL_ENTITY:
        return _approval_history_text(after)
    return None


def _risk_history_text(
    action: str, before: Mapping[str, Any], after: Mapping[str, Any]
) -> str | None:
    if action == audit.CREATED:
        origin = after.get("origem") or after.get("origem_tipo") or "Manual"
        return f"Risco criado (origem: {origin})."
    if action == audit.DELETED:
        return "Risco excluído."
    transition = _risk_transition_text(before, after)
    if transition is not None:
        return transition or None
    changed = [label for key, label in IDENTIFICATION_FIELDS if before.get(key) != after.get(key)]
    if changed:
        return "Identificação alterada: " + ", ".join(changed) + "."
    if before.get("situacao") != after.get("situacao"):
        return f"Situação alterada para {after.get('situacao')}."
    return "Risco alterado."


def _risk_transition_text(before: Mapping[str, Any], after: Mapping[str, Any]) -> str | None:
    """The meaning of a transition of the risk.

    ``None`` means the change is not a transition; an empty text means a fact line already tells
    what happened (the reopening justification, the assessment or the review), so this diff adds
    nothing.
    """
    if after.get("encerramento_motivo") and not before.get("encerramento_motivo"):
        return f"Risco encerrado: {after['encerramento_motivo']}."
    covered = (
        (before.get("encerramento_motivo") and not after.get("encerramento_motivo"))
        or before.get("ultima_revisao") != after.get("ultima_revisao")
        or before.get("proxima_revisao") != after.get("proxima_revisao")
    )
    if covered:
        return ""
    if before.get("oculto") != after.get("oculto"):
        if after.get("oculto"):
            return "Risco excluído (exclusão lógica)."
        return "Risco restaurado pelo Admin."
    if before.get("estrategia") != after.get("estrategia") or before.get("plano") != after.get(
        "plano"
    ):
        verb = "registrado" if not before.get("estrategia") else "alterado"
        return f"Plano de resposta {verb}: {after.get('estrategia')}."
    return None


def _review_history_text(after: Mapping[str, Any]) -> str | None:
    if after.get("tipo") != "revisao":
        return None
    previous, score = after.get("score_de"), after.get("score_para")
    if previous == score:
        text = "Revisão registrada, sem mudança de severidade."
    else:
        text = f"Revisão registrada: score de {previous} para {score}."
    if after.get("gatilho"):
        text += " Gatilho ocorreu: reavaliação obrigatória."
    return text


def _approval_history_text(after: Mapping[str, Any]) -> str | None:
    situation = after.get("situacao")
    if situation == validation.APPROVAL_PENDING:
        return "Plano aguardando aprovação da gerência do projeto."
    if situation == validation.APPROVAL_APPROVED:
        return "Plano de resposta aprovado pela gerência do projeto."
    if situation == validation.APPROVAL_RETURNED:
        return "Plano de resposta devolvido para revisão."
    return None


# ── Writing: the response plan ───────────────────────────────────────────────────────────────


def save_plan(
    session: Session,
    *,
    user: User,
    code: str,
    data: PlanInput,
    reference_date: date,
) -> PlanResult:
    """Record the response plan and, when the inherent band asks for it, the pending approval.

    The residual only exists after the plan; for a threat the target cannot sit above the
    inherent band; a plan of a threat rated Alto or heavier needs a linked action, except under
    the strategy Aceitar. The manager's approval is born Pendente and is decided by someone other
    than the person responsible for the plan (D7).
    """
    rbac.require(user, Permission.WRITE)
    risk = _active(session, user, code, PLAN_CLOSED_MESSAGE)
    ctx = _Ctx(
        session, user, reference_date, service.parameters(session, reference_date=reference_date)
    )
    latest = service._latest_assessments(session, [risk.id]).get(risk.id, {})
    inherent = latest.get(INHERENT)
    if inherent is None:
        raise InvalidDataError(validation.PLAN_NEEDS_ASSESSMENT)
    inherent_band = calculations.risk_severity(
        inherent.probability * inherent.impact, ctx.parameters.scale, life_risk=risk.life_risk
    )
    rules = validation.PlanRules(
        nature=risk.nature,
        inherent_band=inherent_band,
        scale=ctx.parameters.scale,
        reference_date=reference_date,
        current_target=risk.target_date,
    )
    problems = validation.plan_problems(data, rules)
    problems.update(_plan_register_problems(ctx, risk, data, inherent_band))
    if problems:
        raise InvalidDataError(problems)
    first = not (risk.strategy and risk.plan)
    created_action = _plan_side_effects(ctx, risk, data)
    required = (
        calculations.is_top_band(inherent_band.id, ctx.parameters.scale) or data.require_approval
    )
    approval_pending = _write_plan(
        ctx, risk, data, _PlanWrite(required=required, first=first, created_action=created_action)
    )
    return PlanResult(
        code=risk.code,
        situation=risk.situation,
        approval_pending=approval_pending,
        enables_residual=first,
    )


@dataclass(frozen=True)
class _PlanWrite:
    """What the plan write needs besides the risk and the form: the approval and the first plan."""

    required: bool
    first: bool
    created_action: str | None


def _plan_register_problems(
    ctx: _Ctx, risk: Risk, data: PlanInput, inherent_band: Band
) -> dict[str, str]:
    """The plan checks that need the registers: the responsible, the SM and the linked action."""
    problems: dict[str, str] = {}
    if data.plan_responsible_id and not configuracoes.find_people(
        ctx.session, [data.plan_responsible_id]
    ):
        problems["responsavelPlanoId"] = UNKNOWN_PERSON_MESSAGE
    change_code = (data.change_code or "").strip()
    if (
        data.strategy == "Evitar"
        and change_code not in ("", validation.NEW_CHANGE)
        and _change_id_of(ctx, risk.project_id, change_code) is None
    ):
        problems["smRef"] = validation.SM_NOT_FOUND
    counts = actions.count_actions_of_origin(
        ctx.session,
        user=ctx.user,
        origin_kind=ORIGIN_KIND,
        references=[risk.code],
        reference_date=ctx.reference_date,
    )
    needs_action = calculations.requires_response_action(
        risk.nature, inherent_band.id, data.strategy, ctx.parameters.scale
    )
    if needs_action and counts.get(risk.code, actions.OriginActionCount()).total == 0:
        problems["acoes"] = validation.ACTION_REQUIRED.format(band=inherent_band.name)
    return problems


def _change_id_of(ctx: _Ctx, project_id: int, change_code: str) -> int | None:
    wanted = (change_code or "").strip()
    for option in governanca.change_options(ctx.session, project_id=project_id):
        if option.code == wanted:
            return option.id
    return None


def _plan_side_effects(ctx: _Ctx, risk: Risk, data: PlanInput) -> str | None:
    """The action the strategy Evitar asks for ("nova") is created before the plan is written."""
    if data.strategy != "Evitar" or (data.change_code or "").strip() != validation.NEW_CHANGE:
        return None
    created = _create_action(
        ctx,
        risk,
        ActionInput(
            subject=SM_ACTION_SUBJECT.format(code=risk.code),
            description=SM_ACTION_DESCRIPTION,
            requester_id=ctx.user.person_id,
            responsible_id=data.plan_responsible_id,
            planned_date=ctx.reference_date + timedelta(days=SM_ACTION_DAYS),
        ),
        group=PLAN_ACTION_GROUP,
    )
    return created.item


def _write_plan(ctx: _Ctx, risk: Risk, data: PlanInput, write: _PlanWrite) -> bool:
    """Write the plan, its approval row and the situation; answers whether approval is pending."""
    content_changed = _plan_changed(risk, data)
    pending = _approval_row(
        ctx, risk, required=write.required, first=write.first, changed=content_changed
    )
    situation = _plan_situation(risk, data, pending=pending, created_action=write.created_action)
    change_id = None
    if data.strategy == "Evitar" and (data.change_code or "").strip() != validation.NEW_CHANGE:
        change_id = _change_id_of(ctx, risk.project_id, data.change_code)
    recording.update(
        ctx.session,
        user_id=ctx.user.id,
        record=risk,
        changes={
            "strategy": data.strategy,
            "plan": data.plan.strip(),
            "instrument": data.instrument if data.strategy == "Transferir" else None,
            "change_id": change_id,
            "target_severity": data.target_severity,
            "target_date": data.target_date,
            "response_cost_cents": data.response_cost_cents,
            "plan_responsible_id": data.plan_responsible_id,
            "situation": situation,
        },
        version=data.version or risk.version,
    )
    _append_history(
        ctx,
        risk,
        f"Plano de resposta {'registrado' if write.first else 'alterado'}: {data.strategy}.",
    )
    return pending


def _plan_changed(risk: Risk, data: PlanInput) -> bool:
    return (
        risk.strategy != data.strategy
        or (risk.plan or "").strip() != (data.plan or "").strip()
        or risk.target_severity != data.target_severity
        or risk.target_date != data.target_date
    )


def _approval_row(ctx: _Ctx, risk: Risk, *, required: bool, first: bool, changed: bool) -> bool:
    """Append the approval row the plan asks for; answers whether the plan awaits a decision."""
    latest = _latest_approval(ctx.session, risk.id)
    if not required:
        if latest is not None and latest.situation != validation.APPROVAL_NOT_REQUIRED:
            recording.create(
                ctx.session,
                user_id=ctx.user.id,
                record=RiskPlanApproval(
                    risk_id=risk.id,
                    situation=validation.APPROVAL_NOT_REQUIRED,
                    requested_at=calendario.now(),
                ),
            )
        return False
    already_decided = latest is not None and latest.situation == validation.APPROVAL_APPROVED
    if already_decided and not (first or changed):
        return False
    recording.create(
        ctx.session,
        user_id=ctx.user.id,
        record=RiskPlanApproval(
            risk_id=risk.id,
            situation=validation.APPROVAL_PENDING,
            requested_at=calendario.now(),
        ),
    )
    return True


def _plan_situation(
    risk: Risk, data: PlanInput, *, pending: bool, created_action: str | None
) -> str:
    if pending:
        return service.SITUATION_ANALYSIS
    if data.strategy == "Aceitar":
        return service.SITUATION_MONITORED
    if risk.situation in (service.SITUATION_IDENTIFIED, service.SITUATION_ANALYSIS):
        return service.SITUATION_TREATMENT
    if created_action is not None:
        return service.SITUATION_TREATMENT
    return risk.situation


def approve_plan(
    session: Session, *, user: User, code: str, data: ApprovalInput, reference_date: date
) -> ApprovalResult:
    """Decide the pending approval of the plan; the plan's responsible cannot decide it (D7)."""
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(APPROVAL_DENIED_MESSAGE)
    risk = _active(session, user, code, PLAN_CLOSED_MESSAGE)
    ctx = _Ctx(
        session, user, reference_date, service.parameters(session, reference_date=reference_date)
    )
    latest = _latest_approval(session, risk.id)
    if latest is None or latest.situation != validation.APPROVAL_PENDING:
        raise InvalidDataError(validation.NO_PENDING_APPROVAL)
    rbac.require_segregation(user, Conflict(risk.plan_responsible_id, SELF_APPROVAL_MESSAGE))
    problems = validation.approval_problems(data)
    if problems:
        raise InvalidDataError(problems)
    comment = (data.comment or "").strip()
    recording.create(
        session,
        user_id=user.id,
        record=RiskPlanApproval(
            risk_id=risk.id,
            by_id=user.person_id,
            situation=data.decision,
            requested_at=latest.requested_at,
            decided_at=calendario.now(),
            justification=comment or None,
        ),
    )
    situation = risk.situation
    if data.decision == validation.APPROVAL_APPROVED:
        situation = (
            service.SITUATION_MONITORED
            if risk.strategy == "Aceitar"
            else service.SITUATION_TREATMENT
        )
    recording.update(
        session,
        user_id=user.id,
        record=risk,
        changes={"situation": situation},
        version=data.version or risk.version,
    )
    verb = "aprovado" if data.decision == validation.APPROVAL_APPROVED else "devolvido para revisão"
    _append_history(ctx, risk, f"Plano de resposta {verb} pela gerência do projeto.")
    return ApprovalResult(code=risk.code, situation=situation)


# ── Writing: the periodic review ─────────────────────────────────────────────────────────────


def review_risk(
    session: Session,
    *,
    user: User,
    code: str,
    data: ReviewInput,
    reference_date: date,
) -> ReviewResult:
    """Record a periodic review: it writes the new assessment, the timeline and the next review.

    The cadence comes from the severity of the reviewed score; the next review may be anticipated
    and never postponed past it. A trigger that occurred forces the re-evaluation and takes the
    risk to the escalation agenda.
    """
    rbac.require(user, Permission.WRITE)
    risk = _active(session, user, code, REVIEW_CLOSED_MESSAGE)
    ctx = _Ctx(
        session, user, reference_date, service.parameters(session, reference_date=reference_date)
    )
    current_kind, current = _current_assessment(ctx, risk)
    if current is None:
        raise InvalidDataError(validation.REVIEW_NEEDS_ASSESSMENT)
    current_score = current.probability * current.impact
    rules = _review_rules(ctx, risk, data, current_score)
    problems = validation.review_problems(data, rules)
    if problems:
        raise InvalidDataError(problems)
    facts = _ReviewFacts(
        kind=current_kind,
        current=current,
        previous_score=current_score,
        score=(data.probability or 0) * (data.impact or 0),
        band=rules.current_band,
    )
    _write_review(ctx, risk, data, facts)
    notification_notice = _notify_review(ctx, risk, data, facts)
    return ReviewResult(
        code=risk.code,
        score=facts.score,
        severity=facts.band,
        closes_with=_closing_of(data.assessed_situation),
        re_assess=data.trigger,
        notification=notification_notice,
    )


@dataclass(frozen=True)
class _ReviewFacts:
    """What the review writes: the kind of the assessment, the scores and the new band."""

    kind: str
    current: RiskAssessment
    previous_score: int
    score: int
    band: Band


def _current_assessment(ctx: _Ctx, risk: Risk) -> tuple[str, RiskAssessment | None]:
    latest = service._latest_assessments(ctx.session, [risk.id]).get(risk.id, {})
    if RESIDUAL in latest:
        return RESIDUAL, latest[RESIDUAL]
    return INHERENT, latest.get(INHERENT)


def _review_rules(
    ctx: _Ctx, risk: Risk, data: ReviewInput, current_score: int
) -> validation.ReviewRules:
    """The rules read the new score when it holds up, so the cadence is the one of the new band."""
    valid = (
        data.probability is not None
        and data.impact is not None
        and calculations.MIN_LEVEL <= data.probability <= calculations.MAX_LEVEL
        and calculations.MIN_LEVEL <= data.impact <= calculations.MAX_LEVEL
    )
    score = (data.probability or 0) * (data.impact or 0) if valid else current_score
    band = calculations.risk_severity(score, ctx.parameters.scale, life_risk=risk.life_risk)
    return validation.ReviewRules(
        reference_date=ctx.reference_date,
        last_review=risk.last_review,
        current_score=current_score,
        current_band=band,
        cadence_days=calculations.review_cadence(band.id, ctx.parameters.cadence_days),
    )


def _write_review(ctx: _Ctx, risk: Risk, data: ReviewInput, facts: _ReviewFacts) -> None:
    """The reviewed assessment and the review line, both facts with their trail line."""
    reviewed_on = data.reviewed_on or ctx.reference_date
    assessment = RiskAssessment(
        risk_id=risk.id,
        author_id=ctx.user.person_id,
        kind=facts.kind,
        probability=data.probability,
        impact=data.impact,
        assessed_on=reviewed_on,
        **_clamped_dimensions(facts.current, data.impact or 0),
    )
    recording.create(ctx.session, user_id=ctx.user.id, record=assessment)
    review = RiskReview(
        risk_id=risk.id,
        author_id=ctx.user.person_id,
        reviewed_on=reviewed_on,
        kind="revisao",
        assessed_situation=data.assessed_situation,
        score_from=facts.previous_score,
        score_to=facts.score,
        probability=data.probability,
        impact=data.impact,
        trigger_occurred=data.trigger,
        body=(data.comment or "").strip(),
    )
    recording.create(ctx.session, user_id=ctx.user.id, record=review)
    next_review = data.next_review or reviewed_on
    recording.update(
        ctx.session,
        user_id=ctx.user.id,
        record=risk,
        changes={
            "last_review": reviewed_on,
            "next_review": next_review,
            "cadence_days": (next_review - reviewed_on).days,
        },
        version=data.version or risk.version,
    )
    _append_history(
        ctx, risk, f"Revisão registrada: score de {facts.previous_score} para {facts.score}."
    )


def _clamped_dimensions(current: RiskAssessment, impact: int) -> dict[str, int | None]:
    columns = {
        "prazo": "schedule_dimension",
        "custo": "cost_dimension",
        "escopo": "scope_dimension",
        "sms": "safety_dimension",
        "imagem": "image_dimension",
        "legal": "legal_dimension",
    }
    return {
        column: None if (level := getattr(current, column)) is None else min(level, impact)
        for column in columns.values()
    }


def _closing_of(assessed_situation: str) -> str | None:
    if assessed_situation == "Risco materializado":
        return validation.MATERIALIZED
    if assessed_situation == "Risco superado":
        return "Superado"
    return None


def _notify_review(ctx: _Ctx, risk: Risk, data: ReviewInput, facts: _ReviewFacts) -> str | None:
    """Notify the owner and the manager, through the port, when the form asks for it."""
    if not data.notify:
        return None
    manager_id = _manager_of(ctx, risk.project_id)
    people = configuracoes.find_people(ctx.session, {risk.owner_id, manager_id or 0})
    recipients = tuple(person.email for person in people.values() if person.email)
    if not recipients:
        return NOTIFY_NO_EMAIL
    outcome = notification.send(
        ctx.session,
        user_id=ctx.user.id,
        request=notification.NotificationRequest(
            kind=notification.RISK_REVIEW,
            project_id=risk.project_id,
            recipients=recipients,
            subject=NOTIFY_SUBJECT.format(code=risk.code),
            body=NOTIFY_BODY.format(
                date=calendario.now().strftime("%d/%m/%Y"),
                previous=facts.previous_score,
                score=facts.score,
                band=facts.band.name,
                next=(data.next_review or ctx.reference_date).strftime("%d/%m/%Y"),
            ),
            reference_entity=RISK_ENTITY,
            reference_record_id=risk.id,
        ),
    )
    return outcome.notice


def _manager_of(ctx: _Ctx, project_id: int) -> int | None:
    project = configuracoes.find_project(ctx.session, project_id)
    return None if project is None else project.manager_person_id


# ── Writing: the closing and the reopening ───────────────────────────────────────────────────


def close_risk(
    session: Session,
    *,
    user: User,
    code: str,
    data: ClosingInput,
    reference_date: date,
) -> ClosingResult:
    """Close the risk (Gestor): lesson always, the problem action and the SM when materialized.

    The closing is refused with an open action, except when the risk materialized; the lesson is
    born in Rascunho through the facade of Lições, the action goes through the Central and the
    change request through Governança, all in the caller's transaction (D9).
    """
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(CLOSING_DENIED_MESSAGE)
    risk = service._visible(session, user, code)
    if not calculations.is_active(risk.situation):
        raise InvalidDataError(ALREADY_CLOSED_MESSAGE)
    ctx = _Ctx(
        session, user, reference_date, service.parameters(session, reference_date=reference_date)
    )
    problems = _closing_problems(ctx, risk, data)
    if problems:
        raise InvalidDataError(problems)
    lesson = _write_lesson(ctx, risk, data)
    materialized = data.reason == validation.MATERIALIZED
    action_item = _write_problem_action(ctx, risk, data) if materialized else None
    created_change = _write_closing_change(ctx, risk, data) if materialized else None
    situation = SITUATION_MATERIALIZED if materialized else SITUATION_CLOSED
    recording.update(
        session,
        user_id=user.id,
        record=risk,
        changes={
            "situation": situation,
            "closing_reason": data.reason,
            "closing_date": data.closed_on,
            "closing_schedule_impact_days": data.real_schedule_days if materialized else None,
            "closing_cost_impact_cents": data.real_cost_cents if materialized else None,
            "closing_change_id": created_change.id if created_change else None,
            "lesson_id": lesson.id,
            "closed_by_id": user.person_id,
            "next_review": None,
        },
        version=data.version or risk.version,
    )
    return ClosingResult(
        code=risk.code,
        situation=situation,
        lesson_code=lesson.code,
        change_code=created_change.code if created_change else None,
        action_item=action_item,
    )


def _closing_problems(ctx: _Ctx, risk: Risk, data: ClosingInput) -> dict[str, str]:
    open_items = _open_action_items(ctx, risk)
    rules = validation.ClosingRules(
        reference_date=ctx.reference_date,
        identified_on=risk.identified_on,
        open_items=open_items,
        is_opportunity=risk.nature != calculations.THREAT,
    )
    problems = validation.closing_problems(data, rules)
    if (
        data.reason == validation.DUPLICATED
        and _duplicated_risk(ctx, risk, data.duplicated_code) is None
    ):
        problems["duplicadoDe"] = validation.CHOOSE_DUPLICATE
    if (
        data.reason == validation.MATERIALIZED
        and risk.nature == calculations.THREAT
        and data.generate_action
    ):
        problems.update(_problem_action_problems(ctx, data))
    return problems


def _open_action_items(ctx: _Ctx, risk: Risk) -> tuple[str, ...]:
    records = actions.actions_of_origin(
        ctx.session,
        user=ctx.user,
        origin_kind=ORIGIN_KIND,
        reference=risk.code,
        reference_date=ctx.reference_date,
    )
    return tuple(
        row.item or str(row.id) for row in records if row.status is not ActionStatus.COMPLETED
    )


def _duplicated_risk(ctx: _Ctx, risk: Risk, code: str) -> Risk | None:
    wanted = (code or "").strip()
    if not wanted or wanted == risk.code:
        return None
    statement = select(Risk).where(
        Risk.code == wanted, Risk.project_id == risk.project_id, Risk.id != risk.id
    )
    return ctx.session.scalars(statement).one_or_none()


def _problem_action_problems(ctx: _Ctx, data: ClosingInput) -> dict[str, str]:
    problems = validation.action_problems(
        ActionInput(
            subject=data.action_subject,
            requester_id=ctx.user.person_id,
            responsible_id=data.action_responsible_id,
            planned_date=data.action_planned_date,
        ),
        reference_date=ctx.reference_date,
    )
    if data.action_responsible_id and not configuracoes.find_people(
        ctx.session, [data.action_responsible_id]
    ):
        problems["responsavelId"] = UNKNOWN_PERSON_MESSAGE
    return {f"acao{field[0].upper()}{field[1:]}": message for field, message in problems.items()}


def _write_lesson(ctx: _Ctx, risk: Risk, data: ClosingInput) -> lessons_service.CreatedLesson:
    """The lesson learned is always written, in Rascunho, through the facade of Lições (D9)."""
    materialized = data.reason == validation.MATERIALIZED
    threat = risk.nature == calculations.THREAT
    category = ctx.session.get(RiskCategory, risk.category_id)
    return lessons_service.create_draft_lesson(
        ctx.session,
        user=ctx.user,
        project_id=risk.project_id,
        draft=DraftInput(
            title=_lesson_title(risk.title),
            kind="A evitar" if materialized and threat else "A repetir",
            phase="Construção",
            area="Riscos",
            origin=lessons.ORIGIN_RISK,
            origin_ref=risk.code,
            what_happened=f"Risco encerrado: {data.reason}.",
            cause=risk.cause,
            recommendation=(data.lesson or "").strip(),
            term_days=(data.real_schedule_days or 0) if materialized else 0,
            cost_cents=(data.real_cost_cents or 0) if materialized else 0,
            keywords=(category.group, category.name) if category else (),
        ),
        reference_date=ctx.reference_date,
    )


def _lesson_title(title: str) -> str:
    if len(title) <= LESSON_TITLE_LIMIT:
        return title
    return title[: LESSON_TITLE_LIMIT - 3] + "..."


def _write_problem_action(ctx: _Ctx, risk: Risk, data: ClosingInput) -> str | None:
    if risk.nature != calculations.THREAT or not data.generate_action:
        return None
    created = _create_action(
        ctx,
        risk,
        ActionInput(
            subject=data.action_subject,
            description=PROBLEM_ACTION_DESCRIPTION,
            requester_id=ctx.user.person_id,
            responsible_id=data.action_responsible_id,
            planned_date=data.action_planned_date,
        ),
        group=PROBLEM_ACTION_GROUP,
    )
    return created.item


def _write_closing_change(
    ctx: _Ctx, risk: Risk, data: ClosingInput
) -> governanca.CreatedChange | None:
    """The change request of a materialized threat that alters scope, schedule or cost (D9)."""
    if risk.nature != calculations.THREAT or not data.open_change:
        return None
    return governanca.create_change(
        ctx.session,
        user=ctx.user,
        scope=Scope(project_id=risk.project_id, source="padrao"),
        form={
            "titulo": SM_TITLE.format(code=risk.code),
            "tipo": _change_kind(risk.dimension),
            "origem": "Interna",
            "prioridade": "Urgente",
            "descricao": SM_DESCRIPTION.format(
                title=risk.title,
                days=data.real_schedule_days or 0,
                money=format_value(ValueKind.MONEY, data.real_cost_cents or 0),
            ),
            "data_solicitacao": (data.closed_on or ctx.reference_date).isoformat(),
        },
        reference_date=ctx.reference_date,
    )


def _change_kind(dimension: str | None) -> str:
    if dimension == "Custo":
        return "Custo"
    if dimension == "Escopo e qualidade":
        return "Escopo"
    return "Prazo"


def reopen_risk(
    session: Session, *, user: User, code: str, data: ReopenInput, reference_date: date
) -> ReopenResult:
    """Reopen a closed risk (Gestor, with justification): the situation comes back to where it was."""
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(REOPEN_DENIED_MESSAGE)
    risk = service._visible(session, user, code)
    if calculations.is_active(risk.situation):
        raise InvalidDataError(NOT_CLOSED_MESSAGE)
    problems = validation.reopen_problems(data)
    if problems:
        raise InvalidDataError(problems)
    ctx = _Ctx(
        session, user, reference_date, service.parameters(session, reference_date=reference_date)
    )
    situation = _previous_situation(ctx, risk)
    changes: dict[str, object] = {
        "situation": situation,
        "closing_reason": None,
        "closing_date": None,
        "closing_schedule_impact_days": None,
        "closing_cost_impact_cents": None,
        "closing_change_id": None,
        "lesson_id": None,
        "closed_by_id": None,
    }
    cadence = _cadence_of(
        ctx,
        service._build_lines(
            session, user=user, risks=[risk], params=ctx.parameters, reference_date=reference_date
        )[0],
    )
    if cadence is not None:
        changes["cadence_days"] = cadence
        changes["next_review"] = reference_date + timedelta(days=cadence)
    recording.update(
        session, user_id=user.id, record=risk, changes=changes, version=data.version or risk.version
    )
    _append_history(
        ctx, risk, f"Risco reaberto. Justificativa: {(data.justification or '').strip()}"
    )
    return ReopenResult(code=risk.code, situation=situation)


def _previous_situation(ctx: _Ctx, risk: Risk) -> str:
    """Where the risk was before the closing, read from the trail; the prototype's fallback else."""
    statement = (
        select(AuditEntry)
        .where(
            AuditEntry.entity == RISK_ENTITY,
            AuditEntry.record_id == risk.id,
            AuditEntry.action == audit.UPDATED,
        )
        .order_by(AuditEntry.occurred_at.desc(), AuditEntry.id.desc())
    )
    for entry in ctx.session.scalars(statement).all():
        before = entry.before or {}
        after = entry.after or {}
        previous = before.get("situacao")
        if after.get("situacao") in calculations.CLOSED_SITUATIONS and calculations.is_active(
            previous or ""
        ):
            return str(previous)
    if risk.strategy:
        return service.SITUATION_TREATMENT
    if _has_inherent(ctx, risk):
        return service.SITUATION_ANALYSIS
    return service.SITUATION_IDENTIFIED


def _has_inherent(ctx: _Ctx, risk: Risk) -> bool:
    latest = service._latest_assessments(ctx.session, [risk.id]).get(risk.id, {})
    return INHERENT in latest


# ── Writing: the action of the response plan ─────────────────────────────────────────────────


def create_risk_action(
    session: Session,
    *,
    user: User,
    code: str,
    data: ActionInput,
    reference_date: date,
) -> ActionResult:
    """Create an action of the response plan through the single seam of the Central (D9)."""
    rbac.require(user, Permission.WRITE)
    risk = _active(session, user, code, ACTION_CLOSED_MESSAGE)
    ctx = _Ctx(
        session, user, reference_date, service.parameters(session, reference_date=reference_date)
    )
    problems = validation.action_problems(data, reference_date=reference_date)
    ids = {data.requester_id or 0, data.responsible_id or 0}
    known = configuracoes.find_people(session, ids)
    if data.requester_id and data.requester_id not in known:
        problems["solicitanteId"] = UNKNOWN_PERSON_MESSAGE
    if data.responsible_id and data.responsible_id not in known:
        problems["responsavelId"] = UNKNOWN_PERSON_MESSAGE
    if problems:
        raise InvalidDataError(problems)
    created = _create_action(ctx, risk, data, group=PLAN_ACTION_GROUP)
    if risk.situation == service.SITUATION_MONITORED and risk.strategy:
        recording.update(
            session,
            user_id=user.id,
            record=risk,
            changes={"situation": service.SITUATION_TREATMENT},
            version=risk.version,
        )
    _append_history(ctx, risk, _action_history_text(ctx, created))
    return ActionResult(item=created.item, subject=created.subject)


def _action_history_text(ctx: _Ctx, created: actions.ActionRecord) -> str:
    text = f"Ação {created.item} criada ({created.subject}), responsável {_person_name(ctx, created.responsible_id)}"
    if created.planned_date is not None:
        text += f", prevista para {created.planned_date:%d/%m/%Y}"
    return text + "."


def _person_name(ctx: _Ctx, person_id: int) -> str:
    people = configuracoes.find_people(ctx.session, [person_id])
    return people[person_id].name if person_id in people else ""


def _create_action(ctx: _Ctx, risk: Risk, data: ActionInput, *, group: str) -> actions.ActionRecord:
    """The single seam of the Central: item sequential to the risk, origin and reference kept."""
    item = actions.next_origin_item(ctx.session, origin_kind=ORIGIN_KIND, reference=risk.code)
    return actions.create_action(
        ctx.session,
        user=ctx.user,
        new=NewAction(
            project_id=risk.project_id,
            origin=ORIGIN_KIND,
            origin_ref=risk.code,
            subject=(data.subject or "").strip(),
            requester_id=data.requester_id or ctx.user.person_id,
            responsible_id=data.responsible_id or ctx.user.person_id,
            planned_date=data.planned_date,
            description=(data.description or "").strip() or None,
            group=group,
            item=item,
            contributes_probability=data.contributes_probability,
            contributes_impact=data.contributes_impact,
        ),
        reference_date=ctx.reference_date,
    )


# ── Internals: writing ───────────────────────────────────────────────────────────────────────


def _active(session: Session, user: User, code: str, message: str) -> Risk:
    """The risk the flow may change: visible for the user and still in the active portfolio."""
    risk = service._visible(session, user, code)
    if not calculations.is_active(risk.situation):
        raise InvalidDataError(message)
    return risk


def _append_history(ctx: _Ctx, risk: Risk, text: str) -> None:
    """The rich line of the history: it has no column, so it rides the audit trail (D5b)."""
    audit.append(
        ctx.session,
        audit.TrailLine(
            user_id=ctx.user.id,
            entity=HISTORY_ENTITY,
            record_id=risk.id,
            action=audit.CREATED,
            after={"data": ctx.reference_date.isoformat(), "texto": text},
            project_id=risk.project_id,
        ),
    )


def _risk_exists(session: Session, reference: str) -> bool:
    """The risk a lesson of Governança points to, by its number (D9)."""
    return session.scalar(select(Risk.id).where(Risk.code == reference)) is not None


lessons_service.register_origin(lessons.ORIGIN_RISK, _risk_exists)
