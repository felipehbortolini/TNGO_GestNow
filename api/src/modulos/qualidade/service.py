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
from src.modulos.qualidade.models import Rnc
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
