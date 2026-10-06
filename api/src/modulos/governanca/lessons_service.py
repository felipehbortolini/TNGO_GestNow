"""Business facade of the lessons learned of Governança (ISSUE-027, HU-129).

The acervo, the flow Rascunho, Em validação, Validada and Publicada (the validator is a Gestor and never
the author: D7), the origin that can be traced, and the reuse of a lesson in a project. Everything the
routes, the seed and the other modules ask of the lessons goes through here (D5, D9): reading needs the
module, writing needs the Membro permission (the validation and the publication need Gestor); every
write goes through ``core.recording`` and the number of a lesson through ``core.numbering``. Nothing here
reads the clock for a rule: the caller passes the reference date.

Points where other modules enter (D9):

* ``create_draft_lesson`` opens a draft with an origin; the first caller is the closing of an SM
  (ISSUE-025), which builds the text with ``lessons_calculations.lesson_draft_for_change``;
* ``register_origin`` is how the owner of a record says that a number exists: the Mudança is here;
  the Ata is registered by ISSUE-021 and each other module by its own issue (until then its origin
  is not offered in the form);
* the risk that "Aplicar em projeto" may create in Riscos is wired in ISSUE-067.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import calendario, numbering, origin_links, rbac, recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.export_document import project_label
from src.core.import_values import normalize_text
from src.core.rbac import Conflict, Permission, User
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.central_acoes.validation import NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import calculations
from src.modulos.governanca import lessons_calculations as calc
from src.modulos.governanca import lessons_models as lm
from src.modulos.governanca import lessons_validation as validation
from src.modulos.governanca.lessons_calculations import LessonActions
from src.modulos.governanca.lessons_models import (
    Lesson,
    LessonApplication,
    LessonHistory,
    LessonKeyword,
)
from src.modulos.governanca.models import ChangeRequest

MODULE = "governanca"
NUMBERING_KIND = "licao"
ACTION_ORIGIN = "Lição"
ACTION_GROUP = "Reuso"
RETURN_PREFIX = "Devolvida ao autor: "
PARAMETER_GROUP = "licoes"
ALERT_PARAMETER = "alertaSemRegistroDias"
DEFAULT_ALERT_DAYS = 90

NOT_FOUND_MESSAGE = "Lição não encontrada."
NOT_FOUND_PROJECT_MESSAGE = "Projeto não encontrado."
ONLY_DRAFT_EDITED = "Só lição em Rascunho pode ser editada (lição devolvida volta a Rascunho)."
ONLY_AUTHOR_EDITS = "Só o autor ou um Gestor edita a lição."
ONLY_DRAFT_SENT = "Só lição em Rascunho pode ser enviada para validação."
ONLY_AUTHOR_SENDS = "Só o autor ou um Gestor envia a lição para validação."
INCOMPLETE_MESSAGE = (
    "Complete a lição (disciplina e recomendação com 20 caracteres ou mais) antes de enviar. "
    "Use Editar."
)
VALIDATOR_MANAGER_MESSAGE = (
    "A validação é feita pelo PMO ou pela gerência do projeto (papel Gestor)."
)
ONLY_VALIDATING_MESSAGE = "Só lição Em validação pode ser validada ou devolvida."
SELF_VALIDATION_MESSAGE = "O autor não pode validar a própria lição (segregação de funções)."
PUBLISH_MANAGER_MESSAGE = "Publicar no acervo exige papel Gestor."
ONLY_VALIDATED_MESSAGE = "Só lição Validada pode ser publicada."
ONLY_PUBLISHED_MESSAGE = "Só lição publicada no acervo pode ser aplicada."
REACH_MESSAGE = "A aplicabilidade da lição ({applicability}) não alcança este projeto."
DEMONSTRATION_REUSE_TEXT = "Reuso registrado na carga de demonstração (sem detalhe no protótipo)."

type OriginCheck = Callable[[Session, str], bool]

_ORIGIN_CHECKS: dict[str, OriginCheck] = {}


def register_origin(origin: str, check: OriginCheck) -> None:
    """The owner of a record says how to confirm that its number exists (``check(session, number)``)."""
    _ORIGIN_CHECKS[origin] = check


def available_origins() -> tuple[str, ...]:
    """The origins the form offers: the modules that registered a check, then the free ones."""
    wired = tuple(origin for origin in lm.MODULE_ORIGINS if origin in _ORIGIN_CHECKS)
    return (*wired, *lm.FREE_ORIGINS)


def _change_exists(session: Session, reference: str) -> bool:
    found = session.scalar(select(ChangeRequest.id).where(ChangeRequest.code == reference))
    return found is not None


register_origin(lm.ORIGIN_CHANGE, _change_exists)


def _lesson_link(reference: origin_links.OriginRef) -> str | None:
    return origin_links.link_to_screen("governanca/licoes", codigo=reference.reference)


origin_links.register(origin_links.OriginLinkType(kind=ACTION_ORIGIN, build=_lesson_link))

ORIGIN_SCREENS = {
    lm.ORIGIN_CHANGE: ("governanca/mudanca", "codigo"),
    lm.ORIGIN_MINUTES: ("central_acoes/atas", "busca"),
    lm.ORIGIN_RISK: ("riscos/ficha", "codigo"),
}


def origin_url(origin: str, reference: str | None) -> str | None:
    """The address of the record of origin when its module has a screen for it, else ``None``."""
    screen = ORIGIN_SCREENS.get(origin)
    if screen is None or not reference:
        return None
    return origin_links.link_to_screen(screen[0], **{screen[1]: reference})


# ── What the screens read ────────────────────────────────────────────────


@dataclass(frozen=True)
class LessonFilter:
    """The filters of the acervo: each one is optional and the search needs every word."""

    search: str | None = None
    kind: str | None = None
    situation: str | None = None
    phase: str | None = None
    area: str | None = None
    discipline: str | None = None
    origin: str | None = None
    applicability: str | None = None


@dataclass(frozen=True)
class LessonRow:
    """One lesson as the card, the list and the export read it, with what the user may do with it."""

    id: int
    code: str
    project_id: int
    project_label: str
    title: str
    kind: str
    situation: str
    phase: str
    area: str
    discipline: str
    applicability: str
    origin: str
    origin_ref: str | None
    origin_url: str | None
    recommendation: str
    term_days: int
    cost_cents: int
    reuses: int
    registered_on: date
    author_id: int
    keywords: tuple[str, ...]
    actions: LessonActions

    @property
    def origin_label(self) -> str:
        """The origin as the screen names it."""
        return calc.origin_label(self.origin)

    @property
    def has_impact(self) -> bool:
        """Whether the lesson tells an impact in term or cost."""
        return bool(self.term_days or self.cost_cents)


@dataclass(frozen=True)
class Acervo:
    """The acervo of the scope: the cards after the filters, and the lines over them."""

    rows: tuple[LessonRow, ...]
    total_in_scope: int
    counts: calc.AcervoCounts
    published_by_phase: Mapping[str, int]
    is_portfolio: bool


@dataclass(frozen=True)
class LessonPanel:
    """O painel do acervo: os indicadores, as contagens por fase, área e situação, o reuso e os destaques."""

    total: int
    published: int
    published_in_period: int
    in_flow: int
    validating: int
    to_repeat: int
    to_avoid: int
    reuse_rate: Decimal | None
    reuses: int
    avoid_impact_cents: int
    by_phase: tuple[calc.LessonGroupLine, ...]
    by_area: tuple[calc.LessonGroupLine, ...]
    by_situation: tuple[calculations.CountLine, ...]
    last_lesson: date | None
    days_without_record: int | None
    registration_alert: bool
    alert_days: int
    most_reused: tuple[LessonRow, ...]
    projects_without_record: tuple[configuracoes.ProjectDetail, ...]


@dataclass(frozen=True)
class ApplicationLine:
    """One reuse of the lesson: when, where, how, and the action it generated in the Central."""

    applied_on: date
    project_label: str
    how: str
    registered_by: str
    action_id: int | None
    risk_id: int | None


@dataclass(frozen=True)
class HistoryLineView:
    """One line of the history: when, who and what happened."""

    moment: datetime
    person_name: str
    text: str


@dataclass(frozen=True)
class LessonSheet:
    """The sheet of a lesson: the card and what only the sheet shows."""

    row: LessonRow
    what_happened: str
    cause: str
    author_name: str
    applications: tuple[ApplicationLine, ...]
    history: tuple[HistoryLineView, ...]
    return_note: str | None
    version: int


@dataclass(frozen=True)
class FormOptions:
    """The lists the lesson form and the filters offer."""

    disciplines: tuple[str, ...]
    origins: tuple[str, ...]


@dataclass(frozen=True)
class LessonForm:
    """The lesson form to edit: the values as the form writes them and the version it opened."""

    code: str
    values: dict[str, str]


@dataclass(frozen=True)
class CreatedLesson:
    """What the route needs after a lesson is written: the code and the project of the acervo."""

    id: int
    code: str
    project_id: int


@dataclass(frozen=True)
class _Loaded:
    lesson: Lesson
    keywords: tuple[str, ...]
    reuses: int


@dataclass(frozen=True)
class _Lookups:
    projects: Mapping[int, configuracoes.ProjectDetail]
    disciplines: Mapping[int, str]


def acervo(session: Session, *, user: User, scope: Scope, filters: LessonFilter) -> Acervo:
    """The acervo of the scope: its own lessons and the Corporativa ones published by other projects."""
    rbac.require_module(user, MODULE)
    lookups = _lookups(session)
    visible = [item for item in _load(session) if _visible(item, scope)]
    rows = [_row(item, user=user, lookups=lookups) for item in visible]
    matching = [row for row in rows if _matches(row, filters)]
    matching.sort(key=lambda row: calc.lesson_order_key(row.situation, row.registered_on))
    return Acervo(
        rows=tuple(matching),
        total_in_scope=len(rows),
        counts=calc.acervo_counts(
            [(row.project_id, row.applicability) for row in rows], scope_project_id=scope.project_id
        ),
        published_by_phase=calc.published_by_phase([(row.phase, row.situation) for row in rows]),
        is_portfolio=scope.is_portfolio,
    )


def lesson_panel(
    session: Session, *, user: User, scope: Scope, reference_date: date
) -> LessonPanel:
    """O painel do acervo do escopo (HU-130): indicadores, contagens, reuso e projetos sem registro.

    As contagens saem das lições visíveis no escopo (como o acervo); "dias desde a última lição" e
    "projetos sem registro" olham as lições do próprio projeto, com a janela do parâmetro.
    """
    rbac.require_module(user, MODULE)
    lookups = _lookups(session)
    items = [item for item in _load(session) if _visible(item, scope)]
    rows = [_row(item, user=user, lookups=lookups) for item in items]
    alert_days = _alert_days(session, reference_date)
    published = [row for row in rows if row.situation == lm.SITUATION_PUBLISHED]
    reused = [row for row in published if row.reuses]
    window_start = reference_date - timedelta(days=alert_days)
    own = _own_lessons(items, scope)
    last = max((item.lesson.registered_on for item in own), default=None)
    projects = _scope_projects(session, scope)
    last_by_project: dict[int, date | None] = {project.id: None for project in projects}
    for item in own:
        current = last_by_project.get(item.lesson.project_id)
        if current is None or item.lesson.registered_on > current:
            last_by_project[item.lesson.project_id] = item.lesson.registered_on
    without_record = calc.projects_without_record(
        records=last_by_project,
        project_ids=[project.id for project in projects],
        reference_date=reference_date,
        alert_days=alert_days,
    )
    return LessonPanel(
        total=len(rows),
        published=len(published),
        published_in_period=sum(1 for row in published if row.registered_on >= window_start),
        in_flow=len(rows) - len(published),
        validating=sum(1 for row in rows if row.situation == lm.SITUATION_VALIDATING),
        to_repeat=sum(1 for row in rows if row.kind == lm.LESSON_TYPES[0]),
        to_avoid=sum(1 for row in rows if row.kind == lm.LESSON_TYPES[1]),
        reuse_rate=calc.reuse_rate(published=len(published), reused=len(reused)),
        reuses=sum(row.reuses for row in published),
        avoid_impact_cents=sum(row.cost_cents for row in rows if row.kind == lm.LESSON_TYPES[1]),
        by_phase=calc.lines_by_phase((row.phase, row.kind, row.situation) for row in rows),
        by_area=calc.lines_by_area((row.area, row.kind, row.situation) for row in rows),
        by_situation=calculations.count_lines(
            (row.situation for row in rows), lm.LESSON_SITUATIONS
        ),
        last_lesson=last,
        days_without_record=calc.days_since_last(last, reference_date),
        registration_alert=calc.is_registration_alert(last, reference_date, alert_days),
        alert_days=alert_days,
        most_reused=tuple(
            sorted(reused, key=lambda row: (-row.reuses, row.code))[: calc.PANEL_TOP_REUSED]
        ),
        projects_without_record=tuple(
            project for project in projects if project.id in without_record
        ),
    )


def find_lesson_sheet(session: Session, *, user: User, code: str) -> LessonSheet | None:
    """The sheet of the lesson with the code, or ``None`` when there is none."""
    rbac.require_module(user, MODULE)
    lesson = _by_code(session, code)
    if lesson is None:
        return None
    lookups = _lookups(session)
    item = _load_one(session, lesson)
    history = _history(session, lesson)
    names = configuracoes.person_names(
        session, {lesson.author_id, *(line.person_id for line in history)}
    )
    return LessonSheet(
        row=_row(item, user=user, lookups=lookups),
        what_happened=lesson.what_happened,
        cause=lesson.cause,
        author_name=names.get(lesson.author_id, ""),
        applications=_application_lines(session, lesson, lookups),
        history=tuple(
            HistoryLineView(
                calendario.in_product_timezone(line.moment),
                names.get(line.person_id, ""),
                line.text,
            )
            for line in history
        ),
        return_note=_return_note(lesson, history),
        version=lesson.version,
    )


def form_options(session: Session, *, user: User) -> FormOptions:
    """The lists of the lesson form: the register's disciplines and the origins that are wired."""
    rbac.require_module(user, MODULE)
    disciplines = configuracoes.discipline_names_by_id(session)
    return FormOptions(disciplines=tuple(sorted(disciplines.values())), origins=available_origins())


def edit_form(session: Session, *, user: User, code: str) -> LessonForm:
    """The form of a draft lesson filled with what it holds, for who may edit it (403 or 422 else)."""
    lesson = _editable_lesson(session, user=user, code=code, only_draft=ONLY_DRAFT_EDITED)
    item = _load_one(session, lesson)
    discipline = _lookups(session).disciplines.get(lesson.discipline_id or 0, "")
    return LessonForm(
        code=lesson.code,
        values={
            validation.FIELD_TITLE: lesson.title,
            validation.FIELD_KIND: lesson.kind,
            validation.FIELD_PHASE: lesson.phase,
            validation.FIELD_AREA: lesson.area,
            validation.FIELD_DISCIPLINE: discipline,
            validation.FIELD_ORIGIN: lesson.origin,
            validation.FIELD_ORIGIN_REF: lesson.origin_ref or "",
            validation.FIELD_WHAT_HAPPENED: lesson.what_happened,
            validation.FIELD_CAUSE: lesson.cause,
            validation.FIELD_TERM_DAYS: str(lesson.term_impact_days),
            validation.FIELD_COST: validation.money_input(lesson.cost_impact_cents),
            validation.FIELD_RECOMMENDATION: lesson.recommendation,
            validation.FIELD_KEYWORDS: ", ".join(item.keywords),
            validation.FIELD_APPLICABILITY: lesson.applicability,
            validation.FIELD_VERSION: str(lesson.version),
        },
    )


def validation_form_values(session: Session, *, user: User, code: str) -> LessonForm:
    """The form of the validator: it opens only for who may validate this lesson now."""
    lesson = _validatable_lesson(session, user=user, code=code)
    return LessonForm(
        code=lesson.code,
        values={
            validation.FIELD_APPLICABILITY: lesson.applicability,
            validation.FIELD_VERSION: str(lesson.version),
        },
    )


def application_form_values(
    session: Session, *, user: User, code: str, reference_date: date
) -> LessonForm:
    """The form of the reuse: it opens only for a published lesson and for who may write."""
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    lesson = _lesson(session, code)
    _require_published(lesson)
    return LessonForm(
        code=lesson.code,
        values={
            validation.FIELD_PROJECT: str(lesson.project_id),
            validation.FIELD_DATE: reference_date.isoformat(),
            validation.FIELD_GENERATE: validation.GENERATE_NOTHING,
        },
    )


def reachable_projects(
    session: Session, *, user: User, code: str
) -> list[configuracoes.ProjectDetail]:
    """The projects a published lesson reaches: all for a Corporativa one, its own for a Projeto one."""
    rbac.require_module(user, MODULE)
    lesson = _lesson(session, code)
    return [
        project
        for project in configuracoes.list_project_details(session)
        if _reaches(lesson, project.id)
    ]


def person_options(session: Session) -> list[configuracoes.RegisterOption]:
    """The people the responsible of a generated action is chosen from."""
    return configuracoes.list_person_options(session)


# ── Writing: the lesson and its flow ─────────────────────────────────────


def create_lesson(
    session: Session, *, user: User, scope: Scope, form: validation.Form, reference_date: date
) -> CreatedLesson:
    """Register a lesson in Rascunho (or sent to validation when the form says so), HU-129.

    Refused with 403 without the Membro permission and with 422 when the scope is the Portfólio (a
    lesson belongs to a project), a field breaks a rule or the number of the origin does not exist.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    project_id = scope.require_project()
    project = configuracoes.find_project(session, project_id)
    if project is None:
        raise InvalidDataError(NOT_FOUND_PROJECT_MESSAGE)
    disciplines = _discipline_ids(session)
    new = validation.validate_lesson(
        form, discipline_names=frozenset(disciplines), origins=available_origins()
    )
    _require_origin_exists(session, new.origin, new.origin_ref)
    code = numbering.next_number(
        session, project=project, kind=NUMBERING_KIND, reference_date=reference_date
    )
    lesson = _write_new(
        session,
        user=user,
        values={**_columns(new, disciplines[new.discipline]), "registered_on": reference_date},
        project_id=project.id,
        code=code,
    )
    _keywords_of(session, lesson, new.keywords)
    _note(session, lesson, user.person_id, f"Lição registrada ({_origin_text(lesson)}).")
    if form.get(validation.FIELD_SEND) == validation.CHECKED_VALUE:
        _send(session, user=user, lesson=lesson, version=None)
    return CreatedLesson(id=lesson.id, code=code, project_id=project.id)


def create_draft_lesson(
    session: Session,
    *,
    user: User,
    project_id: int,
    draft: validation.DraftInput,
    reference_date: date,
) -> CreatedLesson:
    """Open a draft lesson with an origin: what the other modules call (the closing of an SM first).

    The draft is born Rascunho, authored by the user, with the origin and its number. A module origin
    needs the number of an existing record, confirmed by the owner of that record (422 otherwise).
    """
    rbac.require(user, Permission.WRITE)
    project = configuracoes.find_project(session, project_id)
    if project is None:
        raise InvalidDataError(NOT_FOUND_PROJECT_MESSAGE)
    validation.validate_draft(draft)
    _require_origin_exists(session, draft.origin, draft.origin_ref)
    disciplines = _discipline_ids(session)
    code = numbering.next_number(
        session, project=project, kind=NUMBERING_KIND, reference_date=reference_date
    )
    lesson = _write_new(
        session,
        user=user,
        values={
            **_draft_columns(draft, disciplines.get(draft.discipline)),
            "registered_on": reference_date,
        },
        project_id=project.id,
        code=code,
    )
    _keywords_of(session, lesson, draft.keywords)
    reference = f" {draft.origin_ref}" if draft.origin_ref else ""
    _note(session, lesson, user.person_id, f"Lição criada a partir de {draft.origin}{reference}.")
    return CreatedLesson(id=lesson.id, code=code, project_id=project.id)


def update_lesson(
    session: Session, *, user: User, code: str, form: validation.Form
) -> CreatedLesson:
    """Edit a draft lesson (author or Gestor); the form may also send it to validation."""
    lesson = _editable_lesson(session, user=user, code=code, only_draft=ONLY_DRAFT_EDITED)
    disciplines = _discipline_ids(session)
    unchanged_origin = (lesson.origin, lesson.origin_ref)
    new = validation.validate_lesson(
        form,
        discipline_names=frozenset(disciplines),
        origins=(*available_origins(), lesson.origin),
    )
    if (new.origin, new.origin_ref) != unchanged_origin:
        _require_origin_exists(session, new.origin, new.origin_ref)
    recording.update(
        session,
        user_id=user.id,
        record=lesson,
        changes=_columns(new, disciplines[new.discipline]),
        version=form.get(validation.FIELD_VERSION),
    )
    _keywords_of(session, lesson, new.keywords, replace=True)
    _note(session, lesson, user.person_id, "Lição editada.")
    if form.get(validation.FIELD_SEND) == validation.CHECKED_VALUE:
        _send(session, user=user, lesson=lesson, version=None)
    return CreatedLesson(id=lesson.id, code=lesson.code, project_id=lesson.project_id)


def send_for_validation(
    session: Session, *, user: User, code: str, version: str | None
) -> CreatedLesson:
    """Rascunho to Em validação, by the author or a Gestor, once the lesson is complete."""
    lesson = _editable_lesson(session, user=user, code=code, only_draft=ONLY_DRAFT_SENT)
    _send(session, user=user, lesson=lesson, version=version)
    return CreatedLesson(id=lesson.id, code=lesson.code, project_id=lesson.project_id)


def decide_validation(
    session: Session, *, user: User, code: str, form: validation.Form
) -> CreatedLesson:
    """The validator validates, validates and publishes, or returns to Rascunho with a comment.

    Refused with 403 when the user is not a Gestor or is the author of the lesson (segregation, D7).
    """
    lesson = _validatable_lesson(session, user=user, code=code)
    decision = validation.validate_decision(form, current_applicability=lesson.applicability)
    version = form.get(validation.FIELD_VERSION)
    if decision.result == validation.RESULT_RETURNED:
        _move(
            session,
            user=user,
            lesson=lesson,
            changes={"situation": lm.SITUATION_DRAFT},
            version=version,
        )
        _note(session, lesson, user.person_id, RETURN_PREFIX + decision.comment)
        return _created(lesson)
    changed = decision.applicability != lesson.applicability
    _move(
        session,
        user=user,
        lesson=lesson,
        changes={"situation": decision.result, "applicability": decision.applicability},
        version=version,
    )
    verb = (
        "Validada e publicada no acervo"
        if decision.result == validation.RESULT_PUBLISHED
        else "Validada"
    )
    adjusted = ", ajustada na validação" if changed else ""
    comment = f" {decision.comment}" if decision.comment else ""
    _note(
        session,
        lesson,
        user.person_id,
        f"{verb} (aplicabilidade {lesson.applicability}{adjusted}).{comment}",
    )
    return _created(lesson)


def publish_lesson(
    session: Session, *, user: User, code: str, version: str | None
) -> CreatedLesson:
    """Validada to Publicada: it enters the acervo of the organization (Gestor only)."""
    rbac.require_module(user, MODULE)
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(PUBLISH_MANAGER_MESSAGE)
    lesson = _lesson(session, code)
    if lesson.situation != lm.SITUATION_VALIDATED:
        raise InvalidDataError(ONLY_VALIDATED_MESSAGE)
    _move(
        session,
        user=user,
        lesson=lesson,
        changes={"situation": lm.SITUATION_PUBLISHED},
        version=version,
    )
    _note(
        session,
        lesson,
        user.person_id,
        f"Publicada no acervo (aplicabilidade {lesson.applicability}).",
    )
    return _created(lesson)


def apply_lesson(
    session: Session, *, user: User, code: str, form: validation.Form, reference_date: date
) -> CreatedLesson:
    """Register the reuse of a published lesson in a project and, when asked, open the action.

    The action is created by the single seam of the Central (origin ``Lição``, reference the code of the
    lesson), in the same transaction; the reuse keeps the link to it. The risk of Riscos is wired in
    ISSUE-067.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    lesson = _lesson(session, code)
    _require_published(lesson)
    people = frozenset(option.id for option in configuracoes.list_person_options(session))
    new = validation.validate_application(form, reference_date=reference_date, person_ids=people)
    project = configuracoes.find_project(session, new.project_id)
    if project is None or not _reaches(lesson, project.id):
        applicability = lesson.applicability
        message = (
            REACH_MESSAGE.format(applicability=applicability) if project else "Escolha o projeto."
        )
        raise InvalidDataError({validation.FIELD_PROJECT: message})
    action_id = _open_action(
        session, user=user, lesson=lesson, new=new, reference_date=reference_date
    )
    recording.create(
        session,
        user_id=user.id,
        record=LessonApplication(
            lesson_id=lesson.id,
            project_id=project.id,
            action_id=action_id,
            registered_by_id=user.person_id,
            applied_on=new.applied_on,
            how=new.how,
        ),
    )
    generated = " Gerado: ação na Central." if action_id else ""
    _note(session, lesson, user.person_id, f"Aplicada no projeto {project.code}.{generated}")
    return _created(lesson)


# ── Demonstration load ───────────────────────────────────────────────────


@dataclass(frozen=True)
class SeedLesson:
    """A lesson of the demonstration, as the prototype's mocks tell it, already moved to the date."""

    project_id: int
    code: str
    author_person_id: int
    discipline: str
    registered_on: date
    reuses: int
    columns: Mapping[str, Any]
    keywords: tuple[str, ...]


class DemonstrationNumberError(RuntimeError):
    """The number the sequence of the project gave is not the one the prototype printed."""


def load_demonstration_lesson(
    session: Session, *, author_id: int, seed: SeedLesson, reference_date: date
) -> Lesson:
    """Write a demonstration lesson in the author's name, with its keywords and reuses.

    The code is reserved from the sequence of the project and must be the prototype's, so the next real
    lesson continues the numbering. The origin is not confirmed: the modules of those records arrive
    later. The prototype only counted the reuses; each one becomes a reuse in the lesson's project.
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
    discipline_id = _discipline_ids(session).get(seed.discipline)
    lesson = Lesson(
        project_id=project.id,
        discipline_id=discipline_id,
        author_id=seed.author_person_id,
        code=code,
        registered_on=seed.registered_on,
        **seed.columns,
    )
    recording.create(session, user_id=author_id, record=lesson)
    _keywords_of(session, lesson, seed.keywords)
    moment = datetime.combine(seed.registered_on, time(8, 0), tzinfo=UTC)
    _note(
        session,
        lesson,
        seed.author_person_id,
        f"Lição registrada ({_origin_text(lesson)}).",
        moment,
    )
    for _ in range(seed.reuses):
        recording.create(
            session,
            user_id=author_id,
            record=LessonApplication(
                lesson_id=lesson.id,
                project_id=project.id,
                registered_by_id=seed.author_person_id,
                applied_on=seed.registered_on,
                how=DEMONSTRATION_REUSE_TEXT,
            ),
        )
    return lesson


# ── Internals ────────────────────────────────────────────────────────────


def _lesson(session: Session, code: str) -> Lesson:
    lesson = _by_code(session, code)
    if lesson is None:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return lesson


def _by_code(session: Session, code: str) -> Lesson | None:
    return session.scalar(select(Lesson).where(Lesson.code == code.strip()))


def _created(lesson: Lesson) -> CreatedLesson:
    return CreatedLesson(id=lesson.id, code=lesson.code, project_id=lesson.project_id)


def _require_published(lesson: Lesson) -> None:
    if lesson.situation != lm.SITUATION_PUBLISHED:
        raise InvalidDataError(ONLY_PUBLISHED_MESSAGE)


def _editable_lesson(session: Session, *, user: User, code: str, only_draft: str) -> Lesson:
    """The draft the user may edit or send: write permission, a draft, by its author or a Gestor."""
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    lesson = _lesson(session, code)
    if lesson.situation != lm.SITUATION_DRAFT:
        raise InvalidDataError(only_draft)
    if lesson.author_id != user.person_id and not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(
            ONLY_AUTHOR_EDITS if only_draft == ONLY_DRAFT_EDITED else ONLY_AUTHOR_SENDS
        )
    return lesson


def _validatable_lesson(session: Session, *, user: User, code: str) -> Lesson:
    """The lesson the user may validate now: a Gestor, in validation, and not its author."""
    rbac.require_module(user, MODULE)
    if not rbac.can(user, Permission.MANAGE):
        raise AccessDeniedError(VALIDATOR_MANAGER_MESSAGE)
    lesson = _lesson(session, code)
    if lesson.situation != lm.SITUATION_VALIDATING:
        raise InvalidDataError(ONLY_VALIDATING_MESSAGE)
    rbac.require_segregation(user, Conflict(lesson.author_id, SELF_VALIDATION_MESSAGE))
    return lesson


def _send(session: Session, *, user: User, lesson: Lesson, version: str | None) -> None:
    complete = calc.is_ready_to_send(
        recommendation=lesson.recommendation, has_discipline=lesson.discipline_id is not None
    )
    if not complete:
        raise InvalidDataError(INCOMPLETE_MESSAGE)
    _move(
        session,
        user=user,
        lesson=lesson,
        changes={"situation": lm.SITUATION_VALIDATING},
        version=version,
    )
    _note(session, lesson, user.person_id, "Enviada para validação.")


def _move(
    session: Session, *, user: User, lesson: Lesson, changes: Mapping[str, Any], version: Any
) -> None:
    """Change the lesson through the recording: the version the screen opened must still be current."""
    expected = lesson.version if version is None else version
    recording.update(session, user_id=user.id, record=lesson, changes=changes, version=expected)


def _write_new(
    session: Session,
    *,
    user: User,
    values: Mapping[str, Any],
    project_id: int,
    code: str,
) -> Lesson:
    lesson = Lesson(
        project_id=project_id,
        author_id=user.person_id,
        code=code,
        situation=lm.SITUATION_DRAFT,
        **values,
    )
    recording.create(session, user_id=user.id, record=lesson)
    return lesson


def _columns(new: validation.LessonInput, discipline_id: int) -> dict[str, Any]:
    return {
        "discipline_id": discipline_id,
        "title": new.title,
        "kind": new.kind,
        "phase": new.phase,
        "area": new.area,
        "origin": new.origin,
        "origin_ref": new.origin_ref,
        "what_happened": new.what_happened,
        "cause": new.cause,
        "term_impact_days": new.term_days,
        "cost_impact_cents": new.cost_cents,
        "recommendation": new.recommendation,
        "applicability": new.applicability,
    }


def _draft_columns(draft: validation.DraftInput, discipline_id: int | None) -> dict[str, Any]:
    return {
        "discipline_id": discipline_id,
        "title": draft.title.strip(),
        "kind": draft.kind,
        "phase": draft.phase,
        "area": draft.area,
        "origin": draft.origin,
        "origin_ref": (draft.origin_ref or "").strip().upper() or None,
        "what_happened": draft.what_happened,
        "cause": draft.cause,
        "term_impact_days": draft.term_days,
        "cost_impact_cents": draft.cost_cents,
        "recommendation": draft.recommendation.strip(),
        "applicability": draft.applicability,
    }


def _keywords_of(
    session: Session, lesson: Lesson, words: Iterable[str], *, replace: bool = False
) -> None:
    if replace:
        for old in session.scalars(
            select(LessonKeyword).where(LessonKeyword.lesson_id == lesson.id)
        ):
            session.delete(old)
        session.flush()
    session.add_all(LessonKeyword(lesson_id=lesson.id, word=word) for word in words)
    session.flush()


def _note(
    session: Session,
    lesson: Lesson,
    person_id: int,
    text: str,
    moment: datetime | None = None,
) -> None:
    session.add(
        LessonHistory(
            lesson_id=lesson.id,
            person_id=person_id,
            moment=moment or calendario.now(),
            text=text,
        )
    )
    session.flush()


def _origin_text(lesson: Lesson) -> str:
    return f"{lesson.origin} {lesson.origin_ref}" if lesson.origin_ref else lesson.origin


def _require_origin_exists(session: Session, origin: str, reference: str | None) -> None:
    """422 when a module origin has no wired owner or the owner does not know the number."""
    if not calc.is_module_origin(origin):
        return
    check = _ORIGIN_CHECKS.get(origin)
    if check is None:
        message = f"A origem {origin} ainda não está ligada ao acervo de lições."
        raise InvalidDataError({validation.FIELD_ORIGIN: message})
    if not reference or not check(session, reference.strip().upper()):
        message = f"Registro {reference} não encontrado no módulo de origem."
        raise InvalidDataError({validation.FIELD_ORIGIN_REF: message})


def _discipline_ids(session: Session) -> dict[str, int]:
    return {name: key for key, name in configuracoes.discipline_names_by_id(session).items()}


def _reaches(lesson: Lesson, project_id: int) -> bool:
    return calc.is_lesson_visible(
        lesson_project_id=lesson.project_id,
        applicability=lesson.applicability,
        situation=lesson.situation,
        scope_project_id=project_id,
    )


def _open_action(
    session: Session,
    *,
    user: User,
    lesson: Lesson,
    new: validation.ApplicationInput,
    reference_date: date,
) -> int | None:
    if not new.generate_action or new.responsible_person_id is None:
        return None
    so_far = session.scalar(
        select(func.count())
        .select_from(LessonApplication)
        .where(LessonApplication.lesson_id == lesson.id, LessonApplication.action_id.is_not(None))
    )
    record = central_acoes.create_action(
        session,
        user=user,
        new=NewAction(
            project_id=new.project_id,
            origin=ACTION_ORIGIN,
            origin_ref=lesson.code,
            subject=f"Aplicar a lição {lesson.code}: {lesson.title}",
            description=new.how,
            requester_id=user.person_id,
            responsible_id=new.responsible_person_id,
            planned_date=new.planned_date,
            group=ACTION_GROUP,
            item=calc.next_application_item(so_far or 0),
        ),
        reference_date=reference_date,
    )
    return record.id


def _visible(item: _Loaded, scope: Scope) -> bool:
    return calc.is_lesson_visible(
        lesson_project_id=item.lesson.project_id,
        applicability=item.lesson.applicability,
        situation=item.lesson.situation,
        scope_project_id=scope.project_id,
    )


def _own_lessons(items: list[_Loaded], scope: Scope) -> list[_Loaded]:
    """As lições do próprio escopo: no Portfólio todas, no projeto só as dele."""
    return [
        item for item in items if scope.is_portfolio or item.lesson.project_id == scope.project_id
    ]


def _scope_projects(session: Session, scope: Scope) -> list[configuracoes.ProjectDetail]:
    projects = configuracoes.list_project_details(session)
    if scope.is_portfolio:
        return projects
    return [project for project in projects if project.id == scope.project_id]


def _alert_days(session: Session, reference_date: date) -> int:
    """A janela do alerta de lições sem registro: o parâmetro em vigor, com o padrão do protótipo."""
    found = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    )
    return int(found.get(ALERT_PARAMETER, DEFAULT_ALERT_DAYS))


def _lookups(session: Session) -> _Lookups:
    return _Lookups(
        projects={project.id: project for project in configuracoes.list_project_details(session)},
        disciplines=configuracoes.discipline_names_by_id(session),
    )


def _load(session: Session) -> list[_Loaded]:
    lessons = list(session.scalars(select(Lesson).order_by(Lesson.id)))
    keywords: dict[int, list[str]] = defaultdict(list)
    for entry in session.scalars(select(LessonKeyword).order_by(LessonKeyword.id)):
        keywords[entry.lesson_id].append(entry.word)
    counts = dict(
        session.execute(
            select(LessonApplication.lesson_id, func.count()).group_by(LessonApplication.lesson_id)
        ).all()
    )
    return [
        _Loaded(lesson, tuple(keywords.get(lesson.id, ())), counts.get(lesson.id, 0))
        for lesson in lessons
    ]


def _load_one(session: Session, lesson: Lesson) -> _Loaded:
    words = session.scalars(
        select(LessonKeyword.word)
        .where(LessonKeyword.lesson_id == lesson.id)
        .order_by(LessonKeyword.id)
    )
    reuses = session.scalar(
        select(func.count())
        .select_from(LessonApplication)
        .where(LessonApplication.lesson_id == lesson.id)
    )
    return _Loaded(lesson, tuple(words), reuses or 0)


def _row(item: _Loaded, *, user: User, lookups: _Lookups) -> LessonRow:
    lesson = item.lesson
    project = lookups.projects.get(lesson.project_id)
    return LessonRow(
        id=lesson.id,
        code=lesson.code,
        project_id=lesson.project_id,
        project_label=project_label(project) if project else "",
        title=lesson.title,
        kind=lesson.kind,
        situation=lesson.situation,
        phase=lesson.phase,
        area=lesson.area,
        discipline=lookups.disciplines.get(lesson.discipline_id or 0, ""),
        applicability=lesson.applicability,
        origin=lesson.origin,
        origin_ref=lesson.origin_ref,
        origin_url=origin_url(lesson.origin, lesson.origin_ref),
        recommendation=lesson.recommendation,
        term_days=lesson.term_impact_days,
        cost_cents=lesson.cost_impact_cents,
        reuses=item.reuses,
        registered_on=lesson.registered_on,
        author_id=lesson.author_id,
        keywords=item.keywords,
        actions=calc.lesson_actions(
            lesson.situation,
            is_author=lesson.author_id == user.person_id,
            can_write=rbac.can(user, Permission.WRITE),
            can_manage=rbac.can(user, Permission.MANAGE),
        ),
    )


def _matches(row: LessonRow, filters: LessonFilter) -> bool:
    exact = (
        (filters.kind, row.kind),
        (filters.situation, row.situation),
        (filters.phase, row.phase),
        (filters.area, row.area),
        (filters.origin, row.origin),
        (filters.applicability, row.applicability),
    )
    if any(wanted and wanted != actual for wanted, actual in exact):
        return False
    if filters.discipline and normalize_text(filters.discipline) != normalize_text(row.discipline):
        return False
    text = " ".join(
        [row.code, row.title, row.recommendation, row.discipline, _origin_words(row), *row.keywords]
    )
    return calc.search_matches(filters.search, text)


def _origin_words(row: LessonRow) -> str:
    return f"{row.origin} {row.origin_ref or ''} {row.origin_label}"


def _history(session: Session, lesson: Lesson) -> list[LessonHistory]:
    statement = (
        select(LessonHistory)
        .where(LessonHistory.lesson_id == lesson.id)
        .order_by(LessonHistory.moment.desc(), LessonHistory.id.desc())
    )
    return list(session.scalars(statement))


def _return_note(lesson: Lesson, history: list[LessonHistory]) -> str | None:
    """The validator's comment while the lesson is a draft again: the latest line, when it is a return."""
    if lesson.situation != lm.SITUATION_DRAFT or not history:
        return None
    latest = history[0].text
    return latest.removeprefix(RETURN_PREFIX) if latest.startswith(RETURN_PREFIX) else None


def _application_lines(
    session: Session, lesson: Lesson, lookups: _Lookups
) -> tuple[ApplicationLine, ...]:
    rows = list(
        session.scalars(
            select(LessonApplication)
            .where(LessonApplication.lesson_id == lesson.id)
            .order_by(LessonApplication.applied_on.desc(), LessonApplication.id.desc())
        )
    )
    names = configuracoes.person_names(session, {row.registered_by_id for row in rows})
    lines = []
    for row in rows:
        project = lookups.projects.get(row.project_id)
        lines.append(
            ApplicationLine(
                applied_on=row.applied_on,
                project_label=project_label(project) if project else "",
                how=row.how,
                registered_by=names.get(row.registered_by_id, ""),
                action_id=row.action_id,
                risk_id=row.risk_id,
            )
        )
    return tuple(lines)
