"""Business facade of the Quality module: the non-conformity report (ISSUE-068).

The RNC follows the prototype's flow: Aberta, Em análise de causa, Ação corretiva,
Verificação de eficácia, Encerrada; Cancelada only before the corrective action. The deadline
of the treatment comes from the severity and the parameters in force; the corrective actions
are written in the Central de Ações through its facade, with origin ``RNC`` and the number of
the report (D9), in the same transaction; closing with an effective verification opens the
optional lesson in Rascunho through the facade of Governança, and the id is kept in
``rnc.licao_id``. Nothing here reads the clock: the routes pass the reference date.

Public API (stable; a change needs an issue of its own):

* reading: ``list_rncs``, ``rnc_summary``, ``find_rnc``, ``rnc_sheet``, ``parameters``;
* writing: ``open_rnc``, ``assign_analysis``, ``record_analysis``, ``add_actions``,
  ``send_to_verification``, ``verify_effectiveness``, ``cancel_rnc``, ``update_cost`` and
  ``record_rnc`` (a report that already exists, the demonstration load);
* the seams of other modules: ``read_rnc_origin`` (attachments) and the origin check of the
  lessons of Governança.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import attachment_origins, audit, calendario, numbering, origin_links, rbac, recording
from src.core.attachment_origins import OriginRecord, OriginType
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry
from src.core.rbac import Conflict, Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.service import ActionRecord, OriginActionCount
from src.modulos.central_acoes.validation import NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import lessons_models as lessons
from src.modulos.governanca import lessons_service
from src.modulos.governanca.lessons_validation import DraftInput
from src.modulos.qualidade import calculations, validation
from src.modulos.qualidade.models import Inspection, Itp, ItpPoint, ItpRevision, Rnc
from src.modulos.qualidade.validation import (
    ActionInput,
    AnalysisInput,
    CancellationInput,
    CostInput,
    OpeningInput,
    ResponsibleInput,
    RncFilters,
    VerificationInput,
)

MODULE = "qualidade"
ORIGIN_KIND = "RNC"
PARAMETER_GROUP = "qualidade"
ENTITY = "rnc"
HISTORY_ENTITY = "rnc.historico"
ACTION_GROUP = "Ação corretiva"
NUMBERING_KIND = "rnc"

NOT_FOUND_MESSAGE = "RNC não encontrada."
ANALYSIS_STARTED_MESSAGE = "A análise desta RNC já foi iniciada."
ANALYSIS_NOT_ASSIGNED_MESSAGE = "Atribua a análise antes de registrar a causa raiz."
ACTIONS_ONLY_IN_ACTION_MESSAGE = "Novas ações só na etapa Ação corretiva."
NOT_IN_ACTION_MESSAGE = "A RNC não está na etapa Ação corretiva."
NO_ACTIONS_MESSAGE = "Inclua ao menos uma ação corretiva antes da verificação."
OPEN_ACTIONS_MESSAGE = (
    "Existe{m} {count} ação corretiva em aberto. Conclua-as na Central antes da verificação."
)
CONCESSION_MISSING_MESSAGE = "Registre a concessão do cliente antes da verificação."
NOT_IN_VERIFICATION_MESSAGE = "A RNC não está na etapa de verificação de eficácia."
VERIFICATION_FORBIDDEN_MESSAGE = "Verificar a eficácia exige perfil Gestor."
SELF_VERIFICATION_MESSAGE = (
    "Quem respondeu pela análise não verifica a própria eficácia (segregação de funções)."
)
CANCELLATION_FORBIDDEN_MESSAGE = "Cancelar RNC exige perfil Gestor."
CANCELLATION_TOO_LATE_MESSAGE = "Só é possível cancelar antes da ação corretiva."
COST_NOT_ACTIVE_MESSAGE = "RNC encerrada ou cancelada não muda de custo."
PARAMETERS_MISSING_MESSAGE = "Os parâmetros de Qualidade ainda não foram cadastrados."
UNKNOWN_PERSON_MESSAGE = "A pessoa informada não está no cadastro."

ACTION_DESCRIPTION = "Ação corretiva da RNC {code}."


@dataclass(frozen=True)
class RncLine:
    """One RNC as the screens read it: the columns and everything calculated from them."""

    id: int
    project_id: int
    project_code: str
    code: str
    rnc_date: date
    origin: str
    origin_ref: str | None
    discipline_id: int
    discipline: str
    company_id: int
    company_name: str
    responsible_id: int | None
    responsible_name: str
    opened_by_id: int
    opened_by_name: str
    verified_by_id: int | None
    verified_by_name: str
    lesson_id: int | None
    description: str
    severity: str
    containment: str
    disposition: str | None
    concession_reference: str | None
    concession_date: date | None
    method: str | None
    root_cause: str | None
    deadline: date
    closing_date: date | None
    situation: str
    cost_cents: int
    verification_expected: date | None
    effectiveness_date: date | None
    effective: bool | None
    effectiveness_text: str | None
    version: int
    active: bool
    in_treatment: bool
    overdue: bool
    days_overdue: int
    days_open: int
    verification_overdue: bool
    next_step: str
    recurrence_count: int
    actions: OriginActionCount

    @property
    def requires_concession(self) -> bool:
        """Whether the disposition demands the client's concession (Reparo, Usar como está)."""
        return self.disposition in validation.DISPOSITIONS_WITH_CONCESSION

    @property
    def concession_pending(self) -> bool:
        """Whether the concession is still missing."""
        return self.requires_concession and not self.concession_reference

    @property
    def actions_open(self) -> int:
        """How many corrective actions are still open in the Central."""
        return self.actions.open


@dataclass(frozen=True)
class RncSummary:
    """The KPIs of the list for the scope, without filters (what the oracle reads)."""

    active: int
    critical: int
    overdue: int
    in_verification: int
    verification_overdue: int
    closed: int
    registered: int
    average_days: int | None
    cost_cents: int


@dataclass(frozen=True)
class RncListing:
    """What the list shows for a filter: the lines, the KPIs and the choices of the filter."""

    lines: tuple[RncLine, ...]
    summary: RncSummary
    disciplines: tuple[str, ...]
    companies: tuple[configuracoes.RegisterOption, ...]
    projects: tuple[configuracoes.ProjectDetail, ...]
    person_options: tuple[configuracoes.RegisterOption, ...]
    page: int

    @property
    def total(self) -> int:
        """How many RNCs the filter holds, whatever the page."""
        return len(self.lines)

    @property
    def page_count(self) -> int:
        """How many pages the list has; an empty list still has one."""
        return max(1, -(-len(self.lines) // validation.PAGE_SIZE))

    @property
    def page_lines(self) -> tuple[RncLine, ...]:
        """The lines of the current page."""
        start = (self.page - 1) * validation.PAGE_SIZE
        return self.lines[start : start + validation.PAGE_SIZE]


@dataclass(frozen=True)
class HistoryLine:
    """One line of the history of the report, as the ficha prints it."""

    moment: datetime
    author_name: str
    text: str


@dataclass(frozen=True)
class RncSheet:
    """The ficha of one RNC: the line, the corrective actions, the history and the lesson."""

    line: RncLine
    actions: tuple[ActionRecord, ...]
    history: tuple[HistoryLine, ...]
    lesson_code: str | None


@dataclass(frozen=True)
class OpeningResult:
    """What opening answers: the number and the treatment deadline."""

    code: str
    deadline: date


@dataclass(frozen=True)
class AnalysisResult:
    """What the analysis answers: the number and how many corrective actions were created."""

    code: str
    created_actions: int


@dataclass(frozen=True)
class EffectivenessResult:
    """What the verification answers: whether it closed and the lesson opened."""

    code: str
    closed: bool
    lesson_code: str | None


def parameters(session: Session, *, reference_date: date) -> Mapping[str, Any]:
    """The group Qualidade of the parameters in force on the date."""
    values = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    )
    if not values:
        raise InvalidDataError(PARAMETERS_MISSING_MESSAGE)
    return values


def treatment_days(session: Session, *, reference_date: date) -> Mapping[str, int]:
    """The days of the treatment by severity, from the parameters in force."""
    return parameters(session, reference_date=reference_date)["prazoTratamentoDias"]


def verification_days(session: Session, *, reference_date: date) -> int:
    """How many days ahead the effectiveness verification is expected, from the parameters."""
    return int(parameters(session, reference_date=reference_date)["verificacaoEficaciaDias"])


# ── Reading ──────────────────────────────────────────────────────────────────────────────────


def list_rncs(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: RncFilters,
    reference_date: date,
) -> RncListing:
    """The list for the scope and the filters: lines, KPIs and the choices of the filter."""
    rbac.require_module(user, MODULE)
    universe = _lines(
        session, user=user, project_id=scope.project_id, reference_date=reference_date
    )
    based = [line for line in universe if _matches(line, filters)]
    shown = [line for line in based if _matches_situation(line, filters.situation)]
    shown.sort(key=_sort_key, reverse=True)
    page = min(max(filters.page, 1), max(1, -(-len(shown) // validation.PAGE_SIZE)))
    return RncListing(
        lines=tuple(shown),
        summary=_summary(universe),
        disciplines=tuple(configuracoes.list_discipline_names(session)),
        companies=tuple(configuracoes.list_company_options(session)),
        projects=tuple(configuracoes.list_project_details(session)),
        person_options=tuple(configuracoes.list_person_options(session)),
        page=page,
    )


def rnc_summary(session: Session, *, user: User, scope: Scope, reference_date: date) -> RncSummary:
    """The KPIs of the scope, without filters (what the oracle reads)."""
    rbac.require_module(user, MODULE)
    return _summary(
        _lines(session, user=user, project_id=scope.project_id, reference_date=reference_date)
    )


def find_rnc(session: Session, *, user: User, code: str, reference_date: date) -> RncLine | None:
    """The RNC with the number, or ``None``."""
    rbac.require_module(user, MODULE)
    rnc = _by_code(session, code)
    if rnc is None:
        return None
    return _build_lines(session, user=user, records=[rnc], reference_date=reference_date)[0]


def rnc_sheet(session: Session, *, user: User, code: str, reference_date: date) -> RncSheet | None:
    """The ficha: the line, the actions of the Central, the history and the lesson of closing."""
    line = find_rnc(session, user=user, code=code, reference_date=reference_date)
    if line is None:
        return None
    records = actions.actions_of_origin(
        session,
        user=user,
        origin_kind=ORIGIN_KIND,
        reference=line.code,
        reference_date=reference_date,
    )
    lesson_code = _lesson_code(session, line.lesson_id)
    return RncSheet(
        line=line,
        actions=records,
        history=_history_of(session, line.id),
        lesson_code=lesson_code,
    )


def _lesson_code(session: Session, lesson_id: int | None) -> str | None:
    if not lesson_id:
        return None
    options = lessons_service.lesson_options(session, lesson_ids=[lesson_id])
    return options[0].code if options else None


def _history_of(session: Session, rnc_id: int) -> tuple[HistoryLine, ...]:
    """The rich lines of the history: the audit trail of the entity ``rnc.historico`` (D5b)."""
    statement = (
        select(AuditEntry)
        .where(AuditEntry.entity == HISTORY_ENTITY, AuditEntry.record_id == rnc_id)
        .order_by(AuditEntry.occurred_at.desc(), AuditEntry.id.desc())
    )
    lines: list[HistoryLine] = []
    for entry in session.scalars(statement).all():
        after = entry.after or {}
        text = str(after.get("texto") or "")
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


def _lines(
    session: Session, *, user: User, project_id: int | None, reference_date: date
) -> list[RncLine]:
    statement = select(Rnc).order_by(Rnc.id)
    if project_id is not None:
        statement = statement.where(Rnc.project_id == project_id)
    records = list(session.scalars(statement).all())
    return _build_lines(session, user=user, records=records, reference_date=reference_date)


def _build_lines(
    session: Session,
    *,
    user: User,
    records: Sequence[Rnc],
    reference_date: date,
) -> list[RncLine]:
    ids = [record.id for record in records]
    disciplines = configuracoes.discipline_names_by_id(session)
    companies = configuracoes.list_company_names(session)
    projects = {item.id: item.code for item in configuracoes.list_project_details(session)}
    people_ids = {
        person_id
        for record in records
        for person_id in (record.responsible_id, record.opened_by_id, record.verified_by_id)
        if person_id is not None
    }
    people = configuracoes.find_people(session, people_ids)
    counts = actions.count_actions_of_origin(
        session,
        user=user,
        origin_kind=ORIGIN_KIND,
        references=[record.code for record in records],
        reference_date=reference_date,
    )
    recurrences = _recurrences(session, ids)
    return [
        _line_of(
            record,
            reference_date=reference_date,
            discipline=disciplines.get(record.discipline_id, ""),
            company=companies.get(record.company_id, ""),
            project_code=projects.get(record.project_id, ""),
            people={person_id: person.name for person_id, person in people.items()},
            action_count=counts.get(record.code, OriginActionCount()),
            recurrence=recurrences.get(record.id, 0),
        )
        for record in records
    ]


def _line_of(
    record: Rnc,
    *,
    reference_date: date,
    discipline: str,
    company: str,
    project_code: str,
    people: Mapping[int, str],
    action_count: OriginActionCount,
    recurrence: int,
) -> RncLine:
    return RncLine(
        id=record.id,
        project_id=record.project_id,
        project_code=project_code,
        code=record.code,
        rnc_date=record.rnc_date,
        origin=record.origin,
        origin_ref=record.origin_ref,
        discipline_id=record.discipline_id,
        discipline=discipline,
        company_id=record.company_id,
        company_name=company,
        responsible_id=record.responsible_id,
        responsible_name=people.get(record.responsible_id or 0, ""),
        opened_by_id=record.opened_by_id,
        opened_by_name=people.get(record.opened_by_id, ""),
        verified_by_id=record.verified_by_id,
        verified_by_name=people.get(record.verified_by_id or 0, ""),
        lesson_id=record.lesson_id,
        description=record.description,
        severity=record.severity,
        containment=record.containment,
        disposition=record.disposition,
        concession_reference=record.concession_reference,
        concession_date=record.concession_date,
        method=record.method,
        root_cause=record.root_cause,
        deadline=record.deadline,
        closing_date=record.closing_date,
        situation=record.situation,
        cost_cents=record.cost_cents,
        verification_expected=record.verification_expected,
        effectiveness_date=record.effectiveness_date,
        effective=record.effectiveness,
        effectiveness_text=record.effectiveness_text,
        version=record.version,
        active=calculations.is_active(record.situation),
        in_treatment=calculations.is_in_treatment(record.situation),
        overdue=calculations.is_overdue(record.deadline, record.situation, reference_date),
        days_overdue=calculations.days_overdue(record.deadline, record.situation, reference_date),
        days_open=calculations.days_open(record.rnc_date, record.closing_date, reference_date),
        verification_overdue=calculations.is_verification_overdue(
            record.situation, record.verification_expected, reference_date
        ),
        next_step=calculations.next_step(record.situation),
        recurrence_count=recurrence,
        actions=action_count,
    )


def _recurrences(session: Session, rnc_ids: Collection[int]) -> dict[int, int]:
    """How many ineffective verifications each RNC had, counted from its audit trail (D5b)."""
    wanted = [rnc_id for rnc_id in rnc_ids if rnc_id]
    if not wanted:
        return {}
    statement = select(AuditEntry).where(
        AuditEntry.entity == ENTITY,
        AuditEntry.action == audit.UPDATED,
        AuditEntry.record_id.in_(wanted),
    )
    grouped: dict[int, list[tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]]] = {}
    for entry in session.scalars(statement):
        grouped.setdefault(entry.record_id, []).append((entry.before, entry.after))
    return {
        rnc_id: calculations.recurrence_count(transitions)
        for rnc_id, transitions in grouped.items()
    }


def _summary(universe: Sequence[RncLine]) -> RncSummary:
    active = [line for line in universe if line.active]
    closed = [line for line in universe if line.situation == calculations.SITUATION_CLOSED]
    in_verification = [
        line for line in universe if line.situation == calculations.SITUATION_VERIFICATION
    ]
    return RncSummary(
        active=len(active),
        critical=sum(1 for line in active if line.severity == "Crítica"),
        overdue=sum(1 for line in universe if line.overdue),
        in_verification=len(in_verification),
        verification_overdue=sum(1 for line in in_verification if line.verification_overdue),
        closed=len(closed),
        registered=sum(
            1 for line in universe if line.situation != calculations.SITUATION_CANCELLED
        ),
        average_days=calculations.average_treatment_days(line.days_open for line in closed),
        cost_cents=sum(line.cost_cents for line in universe),
    )


def _matches(line: RncLine, filters: RncFilters) -> bool:
    """The filters besides the situation: severity, discipline, origin, company and search."""
    if filters.severity and line.severity != filters.severity:
        return False
    if filters.discipline and line.discipline != filters.discipline:
        return False
    if filters.origin and line.origin != filters.origin:
        return False
    if filters.company_id is not None and line.company_id != filters.company_id:
        return False
    if filters.search:
        wanted = _normalize(filters.search)
        haystack = " ".join(
            part
            for part in (
                line.code,
                line.description,
                line.origin_ref or "",
                line.discipline,
                line.company_name,
            )
            if part
        )
        return wanted in _normalize(haystack)
    return True


def _matches_situation(line: RncLine, situation: str) -> bool:
    if situation == validation.SITUATION_ACTIVE:
        return line.active
    if situation == validation.SITUATION_OVERDUE:
        return line.overdue or line.verification_overdue
    if situation == validation.SITUATION_ALL:
        return True
    return line.situation == situation


def _sort_key(line: RncLine) -> tuple[date, str]:
    return (line.rnc_date, line.code)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _by_code(session: Session, code: str) -> Rnc | None:
    return session.scalars(select(Rnc).where(Rnc.code == code)).one_or_none()


def _editable(session: Session, code: str) -> Rnc:
    rnc = _by_code(session, code)
    if rnc is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return rnc


# ── Writing ──────────────────────────────────────────────────────────────────────────────────


def open_rnc(
    session: Session, *, user: User, data: OpeningInput, reference_date: date
) -> OpeningResult:
    """Open the RNC: the code is reserved here and the deadline follows the severity."""
    rbac.require(user, Permission.WRITE)
    project = (
        configuracoes.find_project(session, data.project_id)
        if data.project_id is not None
        else None
    )
    known_companies = {item.id for item in configuracoes.list_company_options(session)}
    problems = validation.opening_problems(
        data,
        reference_date=reference_date,
        discipline_names=configuracoes.list_discipline_names(session),
        project_known=project is not None,
        company_known=data.company_id is not None and data.company_id in known_companies,
    )
    if problems:
        raise InvalidDataError(problems)
    project_ok = cast(configuracoes.ProjectDetail, project)
    rnc_date = cast(date, data.rnc_date)
    deadline = calculations.treatment_deadline(
        rnc_date, data.severity, treatment_days(session, reference_date=reference_date)
    )
    rnc = Rnc(
        project_id=project_ok.id,
        discipline_id=_discipline_id(session, data.discipline),
        company_id=cast(int, data.company_id),
        responsible_id=None,
        opened_by_id=user.person_id,
        verified_by_id=None,
        lesson_id=None,
        code=numbering.next_number(
            session, project=project_ok, kind=NUMBERING_KIND, reference_date=reference_date
        ),
        rnc_date=rnc_date,
        origin=data.origin,
        origin_ref=(data.origin_ref or "").strip() or None,
        description=data.description.strip(),
        severity=data.severity,
        containment=data.containment.strip(),
        disposition=None,
        concession_reference=None,
        concession_date=None,
        method=None,
        root_cause=None,
        deadline=deadline,
        closing_date=None,
        situation=calculations.SITUATION_OPEN,
        cost_cents=0,
        verification_expected=None,
        effectiveness_date=None,
        effectiveness=None,
        effectiveness_text=None,
    )
    recording.create(session, user_id=user.id, record=rnc)
    _append_history(
        session,
        user=user,
        rnc=rnc,
        reference_date=reference_date,
        text=(
            f"RNC aberta ({rnc.origin}{(f' {rnc.origin_ref}' if rnc.origin_ref else '')}). "
            f"Contenção: {rnc.containment}."
        ),
    )
    return OpeningResult(code=rnc.code, deadline=deadline)


def assign_analysis(
    session: Session, *, user: User, code: str, data: ResponsibleInput, reference_date: date
) -> None:
    """Assign the root cause analysis: only from ``Aberta``, to a person of the register."""
    rbac.require(user, Permission.WRITE)
    rnc = _editable(session, code)
    if rnc.situation != calculations.SITUATION_OPEN:
        raise InvalidDataError(ANALYSIS_STARTED_MESSAGE)
    known = configuracoes.find_people(session, [data.responsible_id] if data.responsible_id else [])
    problems = validation.responsible_problems(
        data, person_known=bool(data.responsible_id and data.responsible_id in known)
    )
    if problems:
        raise InvalidDataError(problems)
    responsible_id = cast(int, data.responsible_id)
    recording.update(
        session,
        user_id=user.id,
        record=rnc,
        changes={
            "responsible_id": responsible_id,
            "situation": calculations.SITUATION_ANALYSIS,
        },
        version=data.version or rnc.version,
    )
    _append_history(
        session,
        user=user,
        rnc=rnc,
        reference_date=reference_date,
        text=f"Análise de causa atribuída a {_person_name(session, responsible_id)}.",
    )


def record_analysis(
    session: Session, *, user: User, code: str, data: AnalysisInput, reference_date: date
) -> AnalysisResult:
    """Record the analysis: the root cause, the disposition and at least one action in the Central."""
    rbac.require(user, Permission.WRITE)
    rnc = _editable(session, code)
    if rnc.situation != calculations.SITUATION_ANALYSIS:
        raise InvalidDataError(ANALYSIS_NOT_ASSIGNED_MESSAGE)
    people = configuracoes.find_people(
        session, [action.responsible_id for action in data.actions if action.responsible_id]
    )
    problems = validation.analysis_problems(
        data, reference_date=reference_date, people_known=people
    )
    if problems:
        raise InvalidDataError(problems)
    changes: dict[str, object] = {
        "method": data.method,
        "root_cause": data.root_cause.strip(),
        "disposition": data.disposition,
        "concession_reference": (
            data.concession_reference.strip()
            if data.disposition in validation.DISPOSITIONS_WITH_CONCESSION
            else None
        ),
        "concession_date": (
            data.concession_date
            if data.disposition in validation.DISPOSITIONS_WITH_CONCESSION
            else None
        ),
        "cost_cents": data.cost_cents,
        "situation": calculations.SITUATION_ACTION,
    }
    recording.update(
        session,
        user_id=user.id,
        record=rnc,
        changes=changes,
        version=data.version or rnc.version,
    )
    created = _create_actions(
        session, user=user, rnc=rnc, actions_input=data.actions, reference_date=reference_date
    )
    concession = f" (concessão {rnc.concession_reference})" if rnc.concession_reference else ""
    _append_history(
        session,
        user=user,
        rnc=rnc,
        reference_date=reference_date,
        text=(
            f"Análise registrada ({rnc.method}). Causa raiz: {rnc.root_cause} "
            f"Disposição: {rnc.disposition}{concession}. {_plural(created, 'ação corretiva criada', 'ações corretivas criadas')} na Central."
        ),
    )
    return AnalysisResult(code=rnc.code, created_actions=created)


def add_actions(
    session: Session,
    *,
    user: User,
    code: str,
    actions_input: Sequence[ActionInput],
    reference_date: date,
) -> int:
    """Add corrective actions while the RNC is in ``Ação corretiva``."""
    rbac.require(user, Permission.WRITE)
    rnc = _editable(session, code)
    if rnc.situation != calculations.SITUATION_ACTION:
        raise InvalidDataError(ACTIONS_ONLY_IN_ACTION_MESSAGE)
    if not actions_input:
        raise InvalidDataError({"acoes": validation.ACTIONS_REQUIRED})
    people = configuracoes.find_people(
        session, [action.responsible_id for action in actions_input if action.responsible_id]
    )
    problems = validation.actions_problems(
        actions_input, reference_date=reference_date, people_known=people
    )
    if problems:
        raise InvalidDataError(problems)
    created = _create_actions(
        session, user=user, rnc=rnc, actions_input=actions_input, reference_date=reference_date
    )
    _append_history(
        session,
        user=user,
        rnc=rnc,
        reference_date=reference_date,
        text=f"{_plural(created, 'ação corretiva criada', 'ações corretivas criadas')} na Central.",
    )
    return created


def send_to_verification(
    session: Session,
    *,
    user: User,
    code: str,
    version: int | str | None,
    reference_date: date,
) -> date:
    """Send to the effectiveness verification once every corrective action is completed."""
    rbac.require(user, Permission.WRITE)
    rnc = _editable(session, code)
    if rnc.situation != calculations.SITUATION_ACTION:
        raise InvalidDataError(NOT_IN_ACTION_MESSAGE)
    counts = actions.count_actions_of_origin(
        session,
        user=user,
        origin_kind=ORIGIN_KIND,
        references=[rnc.code],
        reference_date=reference_date,
    ).get(rnc.code, OriginActionCount())
    if counts.total == 0:
        raise InvalidDataError(NO_ACTIONS_MESSAGE)
    if counts.open:
        raise InvalidDataError(
            OPEN_ACTIONS_MESSAGE.format(m="m" if counts.open > 1 else "", count=counts.open)
        )
    if rnc.disposition in validation.DISPOSITIONS_WITH_CONCESSION and not rnc.concession_reference:
        raise InvalidDataError(CONCESSION_MISSING_MESSAGE)
    expected = reference_date + timedelta(
        days=verification_days(session, reference_date=reference_date)
    )
    recording.update(
        session,
        user_id=user.id,
        record=rnc,
        changes={
            "situation": calculations.SITUATION_VERIFICATION,
            "verification_expected": expected,
        },
        version=version or rnc.version,
    )
    _append_history(
        session,
        user=user,
        rnc=rnc,
        reference_date=reference_date,
        text=f"Ações concluídas; verificação de eficácia prevista para {_br(expected)}.",
    )
    return expected


def verify_effectiveness(
    session: Session, *, user: User, code: str, data: VerificationInput, reference_date: date
) -> EffectivenessResult:
    """Verify the effectiveness: Gestor, never who answered for the analysis (D7).

    Effective closes the RNC and opens the optional lesson in Rascunho through the facade of
    Governança, keeping its id; ineffective sends the RNC back to ``Ação corretiva``.
    """
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(VERIFICATION_FORBIDDEN_MESSAGE)
    rnc = _editable(session, code)
    if rnc.situation != calculations.SITUATION_VERIFICATION:
        raise InvalidDataError(NOT_IN_VERIFICATION_MESSAGE)
    rbac.require_segregation(
        user, Conflict(person_id=rnc.responsible_id, message=SELF_VERIFICATION_MESSAGE)
    )
    problems = validation.verification_problems(
        data, reference_date=reference_date, opened_on=rnc.rnc_date
    )
    if problems:
        raise InvalidDataError(problems)
    checked_on = cast(date, data.checked_on)
    changes: dict[str, object] = {
        "effectiveness_date": checked_on,
        "effectiveness": bool(data.effective),
        "effectiveness_text": data.text.strip(),
        "verified_by_id": user.person_id,
    }
    lesson_code: str | None = None
    if data.effective:
        if data.register_lesson:
            created = _write_lesson(
                session, user=user, rnc=rnc, data=data, reference_date=checked_on
            )
            changes["lesson_id"] = created.id
            lesson_code = created.code
        changes.update(
            {
                "situation": calculations.SITUATION_CLOSED,
                "closing_date": checked_on,
                "verification_expected": None,
            }
        )
    else:
        changes.update(
            {
                "situation": calculations.SITUATION_ACTION,
                "verification_expected": None,
            }
        )
    recording.update(
        session, user_id=user.id, record=rnc, changes=changes, version=data.version or rnc.version
    )
    if data.effective:
        extra = f" Lição {lesson_code} em Rascunho." if lesson_code else ""
        text = f"Eficácia verificada e RNC encerrada: {rnc.effectiveness_text}{extra}"
    else:
        text = (
            f"Ação ineficaz: {rnc.effectiveness_text} "
            "A RNC volta para Ação corretiva; registre novas ações."
        )
    _append_history(session, user=user, rnc=rnc, reference_date=reference_date, text=text)
    return EffectivenessResult(code=rnc.code, closed=bool(data.effective), lesson_code=lesson_code)


def cancel_rnc(
    session: Session,
    *,
    user: User,
    code: str,
    data: CancellationInput,
    reference_date: date,
) -> None:
    """Cancel the RNC: Gestor, only before the corrective action, with the reason."""
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(CANCELLATION_FORBIDDEN_MESSAGE)
    rnc = _editable(session, code)
    if rnc.situation not in calculations.CANCELLABLE_SITUATIONS:
        raise InvalidDataError(CANCELLATION_TOO_LATE_MESSAGE)
    problems = validation.cancellation_problems(data)
    if problems:
        raise InvalidDataError(problems)
    recording.update(
        session,
        user_id=user.id,
        record=rnc,
        changes={
            "situation": calculations.SITUATION_CANCELLED,
            "closing_date": reference_date,
        },
        version=data.version or rnc.version,
    )
    _append_history(
        session,
        user=user,
        rnc=rnc,
        reference_date=reference_date,
        text=f"RNC cancelada: {data.reason.strip()}.",
    )


def update_cost(
    session: Session, *, user: User, code: str, data: CostInput, reference_date: date
) -> None:
    """Update the cost of the non-quality, with the composition: an active RNC only."""
    rbac.require(user, Permission.WRITE)
    rnc = _editable(session, code)
    if not calculations.is_active(rnc.situation):
        raise InvalidDataError(COST_NOT_ACTIVE_MESSAGE)
    problems = validation.cost_problems(data)
    if problems:
        raise InvalidDataError(problems)
    before = rnc.cost_cents
    recording.update(
        session,
        user_id=user.id,
        record=rnc,
        changes={"cost_cents": cast(int, data.cost_cents)},
        version=data.version or rnc.version,
    )
    _append_history(
        session,
        user=user,
        rnc=rnc,
        reference_date=reference_date,
        text=(
            f"Custo da não qualidade de {_money(before)} para {_money(rnc.cost_cents)}: "
            f"{data.justification.strip()}."
        ),
    )


def record_rnc(
    session: Session,
    *,
    user: User,
    rnc: Rnc,
    history_text: str,
    moment: datetime | None = None,
) -> Rnc:
    """Record a report that already exists, with its trail (the demonstration load, a migration)."""
    rbac.require(user, Permission.WRITE)
    recording.create(session, user_id=user.id, record=rnc)
    audit.append(
        session,
        audit.TrailLine(
            user_id=user.id,
            entity=HISTORY_ENTITY,
            record_id=rnc.id,
            action=audit.CREATED,
            after={"data": (moment or calendario.now()).date().isoformat(), "texto": history_text},
            project_id=rnc.project_id,
            occurred_at=moment,
        ),
    )
    return rnc


# ── ITP e inspeções (ISSUE-069) ──────────────────────────────────────────────────────────────

ITP_PREFIX = "ITP"
INSPECTION_PREFIX = "INS"
INSPECTION_DIGITS = 4
ITP_DIGITS = 2
FAT_POINT_PREFIX = "Inspeção em fábrica (FAT)"
FAT_ITP_LABEL = "Inspeção em fábrica (04)"
FAT_RESULT_REQUIRED = "Informe o resultado da inspeção em fábrica."
INSPECTION_APPROVAL_FORBIDDEN_MESSAGE = "Registrar a aprovação do ITP exige papel Gestor."
ITP_NOT_FOUND_MESSAGE = "ITP não encontrado."


@dataclass(frozen=True)
class ItpPointLine:
    """One point of the current revision of the ITP, as the screens read it."""

    id: int
    order: int
    activity: str
    point_type: str
    criterion: str
    reference: str
    responsible: str


@dataclass(frozen=True)
class ItpLine:
    """One ITP as the screens read it: the record and everything calculated from it."""

    id: int
    project_id: int
    project_code: str
    code: str
    title: str
    discipline_id: int
    discipline: str
    company_id: int
    company_name: str
    revision: int
    revision_date: date
    approved_by_client: bool
    approval_reference: str | None
    approval_date: date | None
    points: tuple[ItpPointLine, ...]
    inspections: int
    approved: int
    rejected: int
    approval_pct: Decimal | None
    covered_points: int
    last_inspection: date | None
    version: int

    @property
    def total_points(self) -> int:
        """How many points the current revision has."""
        return len(self.points)

    @property
    def point_type_counts(self) -> dict[str, int]:
        """How many points of each type (H, W and R)."""
        counts = {"H": 0, "W": 0, "R": 0}
        for point in self.points:
            counts[point.point_type] = counts.get(point.point_type, 0) + 1
        return counts


@dataclass(frozen=True)
class ItpListing:
    """What the ITP table shows: the lines and the choices of the filter."""

    lines: tuple[ItpLine, ...]
    disciplines: tuple[str, ...]
    projects: tuple[configuracoes.ProjectDetail, ...]

    @property
    def total(self) -> int:
        """How many ITPs the filter holds."""
        return len(self.lines)


@dataclass(frozen=True)
class ItpResult:
    """What saving an ITP answers: the number and the revision written."""

    code: str
    revision: int


@dataclass(frozen=True)
class InspectionLine:
    """One inspection as the screens read it: the record and what it points to."""

    id: int
    project_id: int
    project_code: str
    code: str
    point: str
    point_type: str
    inspection_date: date
    company_id: int
    company_name: str
    inspector_id: int
    inspector_name: str
    result: str
    observation: str
    notification: date | None
    itp_point_id: int | None
    itp_id: int | None
    itp_code: str
    itp_title: str
    rnc_id: int | None
    rnc_code: str
    rnc_situation: str
    order_id: int | None
    order_number: str
    version: int


@dataclass(frozen=True)
class InspectionSummary:
    """The KPIs of the screen for the scope, without filters (what the oracle reads)."""

    itps: int
    itps_approved: int
    points: int
    covered_points: int
    registered: int
    approved: int
    with_remark: int
    rejected: int
    rejected_open_rnc: int
    approval_pct: Decimal | None


@dataclass(frozen=True)
class InspectionListing:
    """What the inspection list shows for a filter: the lines and the page."""

    lines: tuple[InspectionLine, ...]
    page: int

    @property
    def total(self) -> int:
        """How many inspections the filter holds, whatever the page."""
        return len(self.lines)

    @property
    def page_count(self) -> int:
        """How many pages the list has; an empty list still has one."""
        return max(1, -(-len(self.lines) // validation.PAGE_SIZE))

    @property
    def page_lines(self) -> tuple[InspectionLine, ...]:
        """The lines of the current page."""
        start = (self.page - 1) * validation.PAGE_SIZE
        return self.lines[start : start + validation.PAGE_SIZE]


@dataclass(frozen=True)
class InspectionResult:
    """What recording an inspection answers: the number, the RNC opened and the warnings."""

    code: str
    rnc_code: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FatInspectionResult:
    """What the FAT of the diligence answers: the number of the inspection it wrote."""

    code: str


def list_itps(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: validation.ItpFilters,
    reference_date: date,
) -> ItpListing:
    """The ITPs of the scope for the filters: the lines and the choices of the filter."""
    rbac.require_module(user, MODULE)
    lines = [
        line
        for line in _itp_lines(session, project_id=scope.project_id, reference_date=reference_date)
        if _matches_itp(line, filters)
    ]
    return ItpListing(
        lines=tuple(lines),
        disciplines=tuple(configuracoes.list_discipline_names(session)),
        projects=tuple(configuracoes.list_project_details(session)),
    )


def itp_sheet(session: Session, *, user: User, code: str, reference_date: date) -> ItpLine | None:
    """The ficha of one ITP: the line with the points of the current revision."""
    rbac.require_module(user, MODULE)
    itp = _itp_by_code(session, code)
    if itp is None:
        return None
    lines = _itp_lines(
        session, project_id=itp.project_id, codes=[code], reference_date=reference_date
    )
    return lines[0] if lines else None


def list_inspections(
    session: Session,
    *,
    user: User,
    scope: Scope,
    filters: validation.InspectionFilters,
) -> InspectionListing:
    """The inspections of the scope for the filters, most recent first (the prototype's order)."""
    rbac.require_module(user, MODULE)
    shown = list(_inspection_lines(session, project_id=scope.project_id))
    shown = [line for line in shown if _matches_inspection(line, filters)]
    shown.sort(key=lambda line: (line.inspection_date, line.code), reverse=True)
    page = min(max(filters.page, 1), max(1, -(-len(shown) // validation.PAGE_SIZE)))
    return InspectionListing(lines=tuple(shown), page=page)


def inspecoes_summary(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> InspectionSummary:
    """The KPIs of the screen for the scope, without filters (what the oracle reads)."""
    rbac.require_module(user, MODULE)
    itps = _itp_lines(session, project_id=scope.project_id, reference_date=reference_date)
    inspections = _inspection_lines(session, project_id=scope.project_id)
    rejected = [line for line in inspections if line.result == calculations.RESULT_REJECTED]
    open_rnc = _open_rnc_ids(session, {line.rnc_id for line in rejected})
    return InspectionSummary(
        itps=len(itps),
        itps_approved=sum(1 for line in itps if line.approved_by_client),
        points=sum(line.total_points for line in itps),
        covered_points=sum(line.covered_points for line in itps),
        registered=len(inspections),
        approved=sum(1 for line in inspections if calculations.approved_inspection(line.result)),
        with_remark=sum(
            1 for line in inspections if line.result == calculations.RESULT_APPROVED_WITH_REMARK
        ),
        rejected=len(rejected),
        rejected_open_rnc=sum(1 for line in rejected if line.rnc_id in open_rnc),
        approval_pct=calculations.inspection_approval_rate(line.result for line in inspections),
    )


def create_itp(
    session: Session, *, user: User, data: validation.ItpInput, reference_date: date
) -> ItpResult:
    """Create the ITP (revision 0) with its points; the approval of the client comes later."""
    rbac.require(user, Permission.WRITE)
    project = (
        configuracoes.find_project(session, data.project_id)
        if data.project_id is not None
        else None
    )
    known_companies = {item.id for item in configuracoes.list_company_options(session)}
    problems = validation.itp_problems(
        data,
        discipline_names=configuracoes.list_discipline_names(session),
        project_known=project is not None,
        company_known=data.company_id is not None and data.company_id in known_companies,
    )
    if problems:
        raise InvalidDataError(problems)
    project_ok = cast(configuracoes.ProjectDetail, project)
    itp = Itp(
        project_id=project_ok.id,
        discipline_id=_discipline_id(session, data.discipline),
        company_id=cast(int, data.company_id),
        code=_next_itp_code(session, project_ok, data.discipline, reference_date),
        title=data.title.strip(),
    )
    recording.create(session, user_id=user.id, record=itp)
    revision = _write_revision(
        session, user=user, itp=itp, revision=0, reference_date=reference_date
    )
    _write_points(session, user=user, revision=revision, points=data.points)
    return ItpResult(code=itp.code, revision=revision.revision)


def revise_itp(
    session: Session, *, user: User, code: str, data: validation.ItpInput, reference_date: date
) -> ItpResult:
    """Write the next revision: the approval resets and no point with an inspection may leave."""
    rbac.require(user, Permission.WRITE)
    itp = _itp_or_refuse(session, code)
    project = configuracoes.find_project(session, itp.project_id)
    known_companies = {item.id for item in configuracoes.list_company_options(session)}
    problems = validation.itp_problems(
        data,
        discipline_names=configuracoes.list_discipline_names(session),
        project_known=project is not None,
        company_known=data.company_id is not None and data.company_id in known_companies,
    )
    if problems:
        raise InvalidDataError(problems)
    current = _current_revision(session, itp.id)
    old_points = _revision_points(session, current.id) if current is not None else []
    matched = _match_points(old_points, data.points)
    kept = {point.id for point in matched.values()}
    used = _points_with_inspection(session, [point.id for point in old_points])
    removed = [point for point in old_points if point.id not in kept]
    in_use = [point.activity for point in removed if point.id in used]
    if in_use:
        raise InvalidDataError({"pontos": validation.POINTS_IN_USE.format(names=", ".join(in_use))})
    revision = _write_revision(
        session,
        user=user,
        itp=itp,
        revision=(current.revision if current is not None else -1) + 1,
        reference_date=reference_date,
    )
    for position, point_input in enumerate(data.points, start=1):
        point = matched.get(_normalized_activity(point_input.activity))
        if point is None:
            _write_points(
                session, user=user, revision=revision, points=(point_input,), start=position
            )
            continue
        point.revision_id = revision.id
        point.order = position
        point.activity = point_input.activity.strip()
        point.point_type = point_input.point_type
        point.criterion = point_input.criterion.strip()
        point.reference = (point_input.reference or "").strip()
        point.responsible = point_input.responsible or calculations.DEFAULT_POINT_RESPONSIBLE
    for point in removed:
        session.delete(point)
    session.flush()
    recording.update(
        session,
        user_id=user.id,
        record=itp,
        changes={
            "title": data.title.strip(),
            "discipline_id": _discipline_id(session, data.discipline),
            "company_id": cast(int, data.company_id),
        },
        version=data.version or itp.version,
    )
    return ItpResult(code=itp.code, revision=revision.revision)


def approve_itp(
    session: Session,
    *,
    user: User,
    code: str,
    data: validation.ItpApprovalInput,
    reference_date: date,
) -> None:
    """Record the approval of the client of the current revision: Gestor, once per revision."""
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(INSPECTION_APPROVAL_FORBIDDEN_MESSAGE)
    itp = _itp_or_refuse(session, code)
    revision = _current_revision(session, itp.id)
    if revision is None:
        raise InvalidDataError(ITP_NOT_FOUND_MESSAGE)
    problems = validation.approval_problems(
        data, reference_date=reference_date, already_approved=revision.approved_by_client
    )
    if problems:
        raise InvalidDataError(problems)
    revision.approved_by_client = True
    revision.approval_reference = data.reference.strip()
    revision.approval_date = cast(date, data.approval_date)
    revision.approved_by_id = user.person_id
    session.flush()


def record_inspection(
    session: Session, *, user: User, data: validation.InspectionInput, reference_date: date
) -> InspectionResult:
    """Record an inspection on a point of an approved ITP; a rejection opens the RNC here (D9)."""
    rbac.require(user, Permission.WRITE)
    itp = session.get(Itp, data.itp_id) if data.itp_id is not None else None
    revision = _current_revision(session, itp.id) if itp is not None else None
    point = session.get(ItpPoint, data.point_id) if data.point_id is not None else None
    point_known = point is not None and revision is not None and point.revision_id == revision.id
    inspector_known = bool(
        data.inspector_id
        and data.inspector_id in configuracoes.find_people(session, [data.inspector_id])
    )
    problems = validation.inspection_problems(
        data,
        validation.InspectionContext(
            reference_date=reference_date,
            itp_known=itp is not None,
            itp_approved=revision is not None and revision.approved_by_client,
            itp_code=itp.code if itp is not None else "",
            itp_revision=revision.revision if revision is not None else 0,
            point_known=point_known,
            point_type=point.point_type if point_known and point is not None else "",
            inspector_known=inspector_known,
        ),
    )
    if problems:
        raise InvalidDataError(problems)
    itp_ok = cast(Itp, itp)
    point_ok = cast(ItpPoint, point)
    inspection_date = cast(date, data.inspection_date)
    notification = data.notification if point_ok.point_type != calculations.POINT_TYPE_R else None
    warnings = tuple(
        warning
        for warning in (
            calculations.notification_warning(
                point_ok.point_type,
                notification,
                inspection_date,
                notification_minimum_hours(session, reference_date=reference_date),
            ),
        )
        if warning
    )
    code = _next_inspection_code(session, reference_date)
    rnc_code: str | None = None
    rnc_id: int | None = None
    if data.result == calculations.RESULT_REJECTED:
        opened = open_rnc(
            session,
            user=user,
            data=OpeningInput(
                project_id=itp_ok.project_id,
                rnc_date=inspection_date,
                origin=ORIGIN_KIND_INSPECTION,
                origin_ref=code,
                discipline=_discipline_name(session, itp_ok.discipline_id),
                company_id=itp_ok.company_id,
                severity=data.severity,
                description=f"{point_ok.activity} ({itp_ok.code}): {data.observation.strip()}",
                containment=data.containment,
            ),
            reference_date=reference_date,
        )
        rnc_code = opened.code
        rnc_id = _rnc_id(session, opened.code)
    inspection = Inspection(
        project_id=itp_ok.project_id,
        itp_point_id=point_ok.id,
        company_id=itp_ok.company_id,
        inspector_id=cast(int, data.inspector_id),
        rnc_id=rnc_id,
        order_id=None,
        code=code,
        point=point_ok.activity,
        point_type=point_ok.point_type,
        inspection_date=inspection_date,
        result=data.result,
        observation=(data.observation or "").strip(),
        notification=notification,
    )
    recording.create(session, user_id=user.id, record=inspection)
    return InspectionResult(code=inspection.code, rnc_code=rnc_code, warnings=warnings)


def record_fat_inspection(
    session: Session,
    *,
    user: User,
    project_id: int,
    order_id: int,
    order_number: str,
    supplier_company_id: int,
    result: str,
    inspected_on: date | None,
    inspector_id: int | None,
    reference_date: date,
) -> FatInspectionResult:
    """The FAT seam of Suprimentos (D9): write the inspection of the order without a point.

    The inspection has no point of ITP and is identified by ``pedido_id``; the point text
    carries the number of the order and the type is H, as the prototype wrote.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    problems: dict[str, str] = {}
    if result not in calculations.INSPECTION_RESULTS:
        problems["resultado"] = FAT_RESULT_REQUIRED
    if inspected_on is None:
        problems["data"] = validation.INSPECTION_DATE_REQUIRED
    elif inspected_on > reference_date:
        problems["data"] = validation.DATE_FUTURE
    if problems:
        raise InvalidDataError(problems)
    inspection = Inspection(
        project_id=project_id,
        itp_point_id=None,
        company_id=supplier_company_id,
        inspector_id=inspector_id or user.person_id,
        rnc_id=None,
        order_id=order_id,
        code=_next_inspection_code(session, reference_date),
        point=f"{FAT_POINT_PREFIX} {order_number}",
        point_type=calculations.POINT_TYPE_H,
        inspection_date=cast(date, inspected_on),
        result=result,
        observation="",
        notification=None,
    )
    recording.create(session, user_id=user.id, record=inspection)
    return FatInspectionResult(code=inspection.code)


def notification_minimum_hours(session: Session, *, reference_date: date) -> int:
    """The minimum lead of the notification of the client, from the parameters in force."""
    return int(parameters(session, reference_date=reference_date)["notificacaoClienteHoras"])


ORIGIN_KIND_INSPECTION = "Inspeção"


def _itp_lines(
    session: Session,
    *,
    project_id: int | None,
    reference_date: date,
    codes: Sequence[str] | None = None,
) -> list[ItpLine]:
    statement = select(Itp).order_by(Itp.code)
    if project_id is not None:
        statement = statement.where(Itp.project_id == project_id)
    if codes is not None:
        statement = statement.where(Itp.code.in_(codes))
    itps = list(session.scalars(statement).all())
    if not itps:
        return []
    itp_ids = [itp.id for itp in itps]
    revisions = list(
        session.scalars(
            select(ItpRevision)
            .where(ItpRevision.itp_id.in_(itp_ids))
            .order_by(ItpRevision.revision)
        ).all()
    )
    current: dict[int, ItpRevision] = {}
    for revision in revisions:
        current[revision.itp_id] = revision
    revision_ids = [revision.id for revision in current.values()]
    points = (
        list(
            session.scalars(
                select(ItpPoint)
                .where(ItpPoint.revision_id.in_(revision_ids))
                .order_by(ItpPoint.revision_id, ItpPoint.order)
            ).all()
        )
        if revision_ids
        else []
    )
    point_lines: dict[int, list[ItpPointLine]] = {revision_id: [] for revision_id in revision_ids}
    for point in points:
        point_lines[point.revision_id].append(
            ItpPointLine(
                id=point.id,
                order=point.order,
                activity=point.activity,
                point_type=point.point_type,
                criterion=point.criterion,
                reference=point.reference,
                responsible=point.responsible,
            )
        )
    aggregates = _inspection_aggregates(session, points)
    disciplines = configuracoes.discipline_names_by_id(session)
    companies = configuracoes.list_company_names(session)
    projects = {item.id: item.code for item in configuracoes.list_project_details(session)}
    lines: list[ItpLine] = []
    for itp in itps:
        revision = current.get(itp.id)
        revision_points = point_lines.get(revision.id, []) if revision is not None else []
        aggregate = aggregates.get(revision.id, _InspectionAggregate()) if revision else None
        aggregate = aggregate or _InspectionAggregate()
        lines.append(
            ItpLine(
                id=itp.id,
                project_id=itp.project_id,
                project_code=projects.get(itp.project_id, ""),
                code=itp.code,
                title=itp.title,
                discipline_id=itp.discipline_id,
                discipline=disciplines.get(itp.discipline_id, ""),
                company_id=itp.company_id,
                company_name=companies.get(itp.company_id, ""),
                revision=revision.revision if revision is not None else 0,
                revision_date=revision.revision_date if revision is not None else reference_date,
                approved_by_client=bool(revision is not None and revision.approved_by_client),
                approval_reference=revision.approval_reference if revision is not None else None,
                approval_date=revision.approval_date if revision is not None else None,
                points=tuple(revision_points),
                inspections=aggregate.inspections,
                approved=aggregate.approved,
                rejected=aggregate.rejected,
                approval_pct=calculations.inspection_approval_rate(aggregate.results),
                covered_points=calculations.covered_points(aggregate.point_ids),
                last_inspection=aggregate.last_inspection,
                version=itp.version,
            )
        )
    return lines


@dataclass(frozen=True)
class _InspectionAggregate:
    """The inspections of one ITP, grouped for the line: the counts and the covered points."""

    inspections: int = 0
    approved: int = 0
    rejected: int = 0
    results: tuple[str, ...] = ()
    point_ids: tuple[int | None, ...] = ()
    last_inspection: date | None = None


def _inspection_aggregates(
    session: Session, points: Sequence[ItpPoint]
) -> dict[int, _InspectionAggregate]:
    """Group the inspections of the points by the ITP of their current revision."""
    point_to_revision = {point.id: point.revision_id for point in points}
    if not point_to_revision:
        return {}
    grouped: dict[int, _InspectionAggregate] = {}
    rows = session.execute(
        select(
            Inspection.itp_point_id,
            Inspection.result,
            Inspection.inspection_date,
        ).where(Inspection.itp_point_id.in_(point_to_revision.keys()))
    ).all()
    for point_id, result, inspection_date in rows:
        revision_id = point_to_revision.get(point_id)
        if revision_id is None:
            continue
        previous = grouped.get(revision_id, _InspectionAggregate())
        grouped[revision_id] = _InspectionAggregate(
            inspections=previous.inspections + 1,
            approved=previous.approved + (1 if calculations.approved_inspection(result) else 0),
            rejected=previous.rejected + (1 if result == calculations.RESULT_REJECTED else 0),
            results=(*previous.results, result),
            point_ids=(*previous.point_ids, point_id),
            last_inspection=max(
                (value for value in (previous.last_inspection, inspection_date) if value),
                default=None,
            ),
        )
    return grouped


def _inspection_lines(session: Session, *, project_id: int | None) -> list[InspectionLine]:
    statement = select(Inspection).order_by(Inspection.id)
    if project_id is not None:
        statement = statement.where(Inspection.project_id == project_id)
    records = list(session.scalars(statement).all())
    if not records:
        return []
    point_ids = [record.itp_point_id for record in records if record.itp_point_id is not None]
    point_itp: dict[int, tuple[int, str, str]] = {}
    if point_ids:
        rows = session.execute(
            select(ItpPoint.id, Itp.id, Itp.code, Itp.title)
            .join(ItpRevision, ItpPoint.revision_id == ItpRevision.id)
            .join(Itp, ItpRevision.itp_id == Itp.id)
            .where(ItpPoint.id.in_(point_ids))
        ).all()
        point_itp = {row[0]: (row[1], row[2], row[3]) for row in rows}
    rnc_ids = {record.rnc_id for record in records if record.rnc_id is not None}
    rnc_situations: dict[int, tuple[str, str]] = {}
    if rnc_ids:
        for rnc in session.scalars(select(Rnc).where(Rnc.id.in_(rnc_ids))).all():
            rnc_situations[rnc.id] = (rnc.code, rnc.situation)
    companies = configuracoes.list_company_names(session)
    projects = {item.id: item.code for item in configuracoes.list_project_details(session)}
    people = configuracoes.find_people(
        session, {record.inspector_id for record in records if record.inspector_id}
    )
    lines: list[InspectionLine] = []
    for record in records:
        itp_id, itp_code, itp_title = point_itp.get(record.itp_point_id or 0, (None, "", ""))
        if itp_id is None:
            itp_title = FAT_ITP_LABEL if record.order_id is not None else ""
        rnc_code, rnc_situation = rnc_situations.get(record.rnc_id or 0, ("", ""))
        lines.append(
            InspectionLine(
                id=record.id,
                project_id=record.project_id,
                project_code=projects.get(record.project_id, ""),
                code=record.code,
                point=record.point,
                point_type=record.point_type,
                inspection_date=record.inspection_date,
                company_id=record.company_id,
                company_name=companies.get(record.company_id, ""),
                inspector_id=record.inspector_id,
                inspector_name=people[record.inspector_id].name
                if record.inspector_id in people
                else "",
                result=record.result,
                observation=record.observation,
                notification=record.notification,
                itp_point_id=record.itp_point_id,
                itp_id=itp_id,
                itp_code=itp_code,
                itp_title=itp_title,
                rnc_id=record.rnc_id,
                rnc_code=rnc_code,
                rnc_situation=rnc_situation,
                order_id=record.order_id,
                order_number=_fat_order_number(record.point) if record.order_id is not None else "",
                version=record.version,
            )
        )
    return lines


def _fat_order_number(point: str) -> str:
    """The number of the order inside the point text the FAT wrote (no cross-module read)."""
    prefix = f"{FAT_POINT_PREFIX} "
    return point[len(prefix) :] if point.startswith(prefix) else ""


def _open_rnc_ids(session: Session, rnc_ids: Collection[int | None]) -> set[int]:
    wanted = {rnc_id for rnc_id in rnc_ids if rnc_id is not None}
    if not wanted:
        return set()
    rows = session.execute(select(Rnc.id, Rnc.situation).where(Rnc.id.in_(wanted))).all()
    return {
        rnc_id
        for rnc_id, situation in rows
        if situation not in (calculations.SITUATION_CLOSED, calculations.SITUATION_CANCELLED)
    }


def _rnc_id(session: Session, code: str) -> int | None:
    return session.scalar(select(Rnc.id).where(Rnc.code == code))


def _matches_itp(line: ItpLine, filters: validation.ItpFilters) -> bool:
    if filters.discipline and line.discipline != filters.discipline:
        return False
    if filters.search:
        wanted = _normalize(filters.search)
        haystack = " ".join((line.code, line.title, line.discipline))
        return wanted in _normalize(haystack)
    return True


def _matches_inspection(line: InspectionLine, filters: validation.InspectionFilters) -> bool:
    if filters.itp_id is not None and line.itp_id != filters.itp_id:
        return False
    if filters.result and line.result != filters.result:
        return False
    if filters.point_type and line.point_type != filters.point_type:
        return False
    if filters.search:
        wanted = _normalize(filters.search)
        haystack = " ".join(
            part
            for part in (
                line.code,
                line.point,
                line.itp_code,
                line.itp_title,
                line.rnc_code,
                line.company_name,
            )
            if part
        )
        return wanted in _normalize(haystack)
    return True


def _itp_or_refuse(session: Session, code: str) -> Itp:
    itp = _itp_by_code(session, code)
    if itp is None:
        raise InvalidDataError(ITP_NOT_FOUND_MESSAGE)
    return itp


def _itp_by_code(session: Session, code: str) -> Itp | None:
    return session.scalars(select(Itp).where(Itp.code == code)).one_or_none()


def _current_revision(session: Session, itp_id: int) -> ItpRevision | None:
    return session.scalars(
        select(ItpRevision)
        .where(ItpRevision.itp_id == itp_id)
        .order_by(ItpRevision.revision.desc())
        .limit(1)
    ).one_or_none()


def _revision_points(session: Session, revision_id: int) -> list[ItpPoint]:
    return list(
        session.scalars(
            select(ItpPoint).where(ItpPoint.revision_id == revision_id).order_by(ItpPoint.order)
        ).all()
    )


def _write_revision(
    session: Session, *, user: User, itp: Itp, revision: int, reference_date: date
) -> ItpRevision:
    row = ItpRevision(
        itp_id=itp.id,
        approved_by_id=None,
        revision=revision,
        revision_date=reference_date,
        approved_by_client=False,
        approval_reference=None,
        approval_date=None,
    )
    return recording.create(session, user_id=user.id, record=row)


def _write_points(
    session: Session,
    *,
    user: User,
    revision: ItpRevision,
    points: Sequence[validation.ItpPointInput],
    start: int = 1,
) -> None:
    for offset, point in enumerate(points):
        row = ItpPoint(
            revision_id=revision.id,
            order=start + offset,
            activity=point.activity.strip(),
            point_type=point.point_type,
            criterion=point.criterion.strip(),
            reference=(point.reference or "").strip(),
            responsible=point.responsible or calculations.DEFAULT_POINT_RESPONSIBLE,
        )
        recording.create(session, user_id=user.id, record=row)


def _match_points(
    old_points: Sequence[ItpPoint], inputs: Sequence[validation.ItpPointInput]
) -> dict[str, ItpPoint]:
    """Match the form points to the old ones by the normalized activity (the prototype's rule)."""
    by_activity = {_normalized_activity(point.activity): point for point in old_points}
    matched: dict[str, ItpPoint] = {}
    for point_input in inputs:
        key = _normalized_activity(point_input.activity)
        if key in by_activity:
            matched[key] = by_activity[key]
    return matched


def _normalized_activity(text: str) -> str:
    return validation._normalize_text(text)


def _points_with_inspection(session: Session, point_ids: Sequence[int]) -> set[int]:
    if not point_ids:
        return set()
    return {
        point_id
        for point_id in session.scalars(
            select(Inspection.itp_point_id).where(Inspection.itp_point_id.in_(point_ids))
        ).all()
        if point_id is not None
    }


def _next_inspection_code(session: Session, reference_date: date) -> str:
    """The next number of the global inspection series (``INS-2026-0001``), four digits."""
    codes: Sequence[str] = session.scalars(select(Inspection.code)).all()
    return numbering.next_series_number(
        codes, prefix=INSPECTION_PREFIX, year=reference_date.year, digits=INSPECTION_DIGITS
    )


def _next_itp_code(
    session: Session, project: configuracoes.ProjectDetail, discipline: str, reference_date: date
) -> str:
    """The next number of the ITP series of the project and discipline (``ITP-TN-CIV-01``).

    The prototype computed it over the existing codes of the project and prefix, with two
    digits; the same rule here, over the unique codes of the table.
    """
    initials = (project.ata_pattern or f"TN-{reference_date.year}").split("-")[0]
    discipline_code = calculations.DISCIPLINE_CODES.get(
        discipline, calculations.DISCIPLINE_CODE_FALLBACK
    )
    prefix = f"{ITP_PREFIX}-{initials}-{discipline_code}-"
    codes: Sequence[str] = session.scalars(
        select(Itp.code).where(Itp.project_id == project.id)
    ).all()
    counters = [
        int(code[len(prefix) :])
        for code in codes
        if code.startswith(prefix) and code[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(counters, default=0) + 1:0{ITP_DIGITS}d}"


def _discipline_name(session: Session, discipline_id: int) -> str:
    names = configuracoes.discipline_names_by_id(session)
    return names.get(discipline_id, "")


# ── Integrações (D9, D5a) ────────────────────────────────────────────────────────────────────


def read_rnc_origin(session: Session, *, user: User, record_id: int) -> OriginRecord | None:
    """The reading function of the attachments of an RNC: who reads the RNC reads them."""
    rnc = session.get(Rnc, record_id)
    if rnc is None:
        return None
    rbac.require_module(user, MODULE)
    return OriginRecord(project_id=rnc.project_id)


def _rnc_exists(session: Session, reference: str) -> bool:
    """The RNC a lesson of Governança points to, by its number (D9)."""
    return session.scalar(select(Rnc.id).where(Rnc.code == reference)) is not None


# ── Internals ────────────────────────────────────────────────────────────────────────────────


def _discipline_id(session: Session, discipline: str) -> int:
    for discipline_id, name in configuracoes.discipline_names_by_id(session).items():
        if name == discipline:
            return discipline_id
    raise InvalidDataError({"disciplina": validation.CHOOSE_DISCIPLINE})


def _person_name(session: Session, person_id: int) -> str:
    people = configuracoes.find_people(session, [person_id])
    return people[person_id].name if person_id in people else ""


def _create_actions(
    session: Session,
    *,
    user: User,
    rnc: Rnc,
    actions_input: Sequence[ActionInput],
    reference_date: date,
) -> int:
    """The corrective actions of the RNC, written in the Central in the same transaction (D9)."""
    for item in actions_input:
        sequence = actions.next_origin_item(session, origin_kind=ORIGIN_KIND, reference=rnc.code)
        actions.create_action(
            session,
            user=user,
            new=NewAction(
                project_id=rnc.project_id,
                origin=ORIGIN_KIND,
                origin_ref=rnc.code,
                subject=item.subject.strip(),
                requester_id=user.person_id,
                responsible_id=cast(int, item.responsible_id),
                planned_date=item.planned_date,
                description=(item.description or "").strip() or None,
                group=ACTION_GROUP,
                item=sequence,
            ),
            reference_date=reference_date,
        )
    return len(actions_input)


def _write_lesson(
    session: Session, *, user: User, rnc: Rnc, data: VerificationInput, reference_date: date
) -> lessons_service.CreatedLesson:
    """The optional lesson of the closing, in Rascunho, through the facade of Governança (D9)."""
    return lessons_service.create_draft_lesson(
        session,
        user=user,
        project_id=rnc.project_id,
        draft=DraftInput(
            title=data.lesson_title.strip(),
            kind="A evitar",
            phase="Construção",
            area="Qualidade",
            origin=lessons.ORIGIN_NCR,
            origin_ref=rnc.code,
            what_happened=rnc.description,
            cause=(rnc.root_cause or "").strip(),
            recommendation=data.lesson_recommendation.strip(),
            cost_cents=rnc.cost_cents,
            keywords=(rnc.origin, "não conformidade"),
        ),
        reference_date=reference_date,
    )


def _append_history(
    session: Session,
    *,
    user: User,
    rnc: Rnc,
    reference_date: date,
    text: str,
    moment: datetime | None = None,
) -> None:
    """The rich line of the history: it has no column, so it rides the audit trail (D5b)."""
    audit.append(
        session,
        audit.TrailLine(
            user_id=user.id,
            entity=HISTORY_ENTITY,
            record_id=rnc.id,
            action=audit.CREATED,
            after={"data": reference_date.isoformat(), "texto": text},
            project_id=rnc.project_id,
            occurred_at=moment,
        ),
    )


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _money(cents: int) -> str:
    reais, centavos = divmod(cents, 100)
    whole = f"{reais:,}".replace(",", ".")
    return f"R$ {whole},{centavos:02d}"


def _br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


origin_links.register(
    origin_links.OriginLinkType(
        kind=ORIGIN_KIND,
        build=lambda reference: origin_links.link_to_screen(
            "qualidade/rnc", busca=reference.reference
        ),
    )
)

attachment_origins.register(OriginType(table=ENTITY, module=MODULE, read=read_rnc_origin))

lessons_service.register_origin(lessons.ORIGIN_NCR, _rnc_exists)
