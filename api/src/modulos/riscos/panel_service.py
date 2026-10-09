"""The calculated views of Riscos: the matrix and the panel (ISSUE-066, D6, D11).

The matrix counts the risks of the chosen assessment by cell (probability x impact), carries each
cell to the register filtered and shows the movement from the inherent to the residual score. The
panel sums the exposure by category of the RBS, reconstructs the monthly residual score from the
history of assessments and reviews (never a stored series, D6) and lists the escalation agenda;
the send of the agenda goes through the notification port (``pauta_riscos``). Nothing here reads
the clock: the reference date is an argument and every number is calculated on the query.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import calendario, notification, rbac
from src.core.errors import InvalidDataError
from src.core.notification import NotificationChannel
from src.core.rbac import Permission, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.riscos import calculations, presentation, service
from src.modulos.riscos.calculations import (
    OPPORTUNITY,
    THREAT,
    Band,
    RiskParameters,
    Scale,
)
from src.modulos.riscos.models import Risk, RiskAssessment, RiskReview
from src.modulos.riscos.validation import INHERENT, RESIDUAL, RiskFilters

MODULE = "riscos"
EVOLUTION_MONTHS = 6

AGENDA_SUBJECT = "Pauta de escalonamento de riscos · {scope}"
AGENDA_GREETING = "Prezados,"
AGENDA_REQUEST = "Solicitamos decisão na próxima reunião de acompanhamento do projeto."
AGENDA_FOOTER = "PMO · Gestão Integrada AMT"
AGENDA_EMPTY_MESSAGE = "A pauta está vazia: não há risco para escalonar no projeto."
NO_MANAGER_MESSAGE = "O gerente do projeto não tem e-mail cadastrado: nada foi enviado."

# The tone and the icon of each position of the scale, from the lightest to the heaviest. An
# opportunity flips the scale: the highest score is the best outcome, in the cold families and
# the green.
THREAT_STYLES = (("ok", "ok"), ("alerta", "alerta"), ("atencao", "atencao"), ("erro", "erro"))
OPPORTUNITY_STYLES = (("neutro", "ponto"), ("info", "info"), ("roxo", "sobe"), ("ok", "ok"))


def plural(count: int, singular: str, plural_form: str) -> str:
    """``1 risco ativo`` or ``2 riscos ativos``: the count with the right noun."""
    return f"{count} {singular if count == 1 else plural_form}"


@dataclass(frozen=True)
class MatrixRisk:
    """One risk inside a cell of the matrix."""

    code: str
    title: str
    nature: str
    life_risk: bool
    project_id: int


@dataclass(frozen=True)
class MatrixCell:
    """One cell of the 5 x 5: the score, its band, the risks and the register link when not empty."""

    probability: int
    impact: int
    score: int
    severity: Band
    risks: tuple[MatrixRisk, ...]
    href: str | None


@dataclass(frozen=True)
class BandStyle:
    """A band of the active scale as the visuals paint it: range, tone, icon and level."""

    band: Band
    minimum: int
    maximum: int
    tone: str
    icon: str
    level: int


@dataclass(frozen=True)
class Movement:
    """One risk moved from the inherent to the residual score."""

    code: str
    title: str
    nature: str
    project_id: int
    inherent_score: int
    inherent_band: Band
    residual_score: int
    residual_band: Band
    no_reduction: bool


@dataclass(frozen=True)
class RiskMatrix:
    """Everything the matrix shows: the cells, the movement and the notes below both."""

    assessment: str
    nature: str
    parameters: RiskParameters
    bands: tuple[BandStyle, ...]
    cells: tuple[MatrixCell, ...]
    registered: int
    total: int
    unassessed: int
    life_risks: int
    movement: tuple[Movement, ...]
    caption: str
    notes: tuple[str, ...]
    movement_note: str

    @property
    def styles_by_band(self) -> Mapping[str, BandStyle]:
        """The band styles by band id: the tone of a movement bar and the legend of the chart."""
        return {style.band.id: style for style in self.bands}


@dataclass(frozen=True)
class CategoryExposure:
    """The exposure of one category of the RBS: the summed score, the risks and the VME."""

    group: str
    score: int
    risks: int
    vme_cents: int
    href: str


@dataclass(frozen=True)
class EvolutionPoint:
    """The reconstructed residual score of one month of the panel."""

    month: str
    score: int
    current: bool


@dataclass(frozen=True)
class AgendaEntry:
    """One risk of the escalation agenda, with the reasons the manager has to see it."""

    code: str
    title: str
    category_label: str
    nature: str
    score: int | None
    severity: Band | None
    reasons: tuple[str, ...]
    owner_name: str
    project_id: int


@dataclass(frozen=True)
class RiskPanel:
    """Everything the panel shows: the summary, the categories, the evolution and the agenda."""

    summary: service.RiskSummary
    parameters: RiskParameters
    reduction_avg_pct: int | None
    reduction_target_pct: int | None
    categories: tuple[CategoryExposure, ...]
    evolution: tuple[EvolutionPoint, ...]
    agenda: tuple[AgendaEntry, ...]


# ── Matriz P x I ─────────────────────────────────────────────────────────────────────────────


def risk_matrix(
    session: Session,
    *,
    user: User,
    scope: Scope,
    assessment: str,
    nature: str,
    reference_date: date,
) -> RiskMatrix:
    """The 5 x 5 matrix of the scope for the assessment and the nature chosen.

    Only active risks enter, as in the prototype; a risk without the inherent assessment is out
    of the matrix (it counts in the note) and, on the residual view, a risk without the residual
    enters with the inherent one. The cell carries the address of the register filtered by it.
    """
    rbac.require_module(user, MODULE)
    params = service.parameters(session, reference_date=reference_date)
    lines = _scope_lines(
        session, user=user, scope=scope, params=params, reference_date=reference_date
    )
    universe = [line for line in lines if line.active and (not nature or line.nature == nature)]
    assessed = [line for line in universe if line.inherent is not None]
    cells = tuple(
        _cell(
            probability=probability,
            impact=impact,
            lines=assessed,
            assessment=assessment,
            nature=nature,
            params=params,
        )
        for probability in range(calculations.MAX_LEVEL, calculations.MIN_LEVEL - 1, -1)
        for impact in range(calculations.MIN_LEVEL, calculations.MAX_LEVEL + 1)
    )
    movement = _movement(assessed)
    total = len(assessed)
    life_risks = sum(1 for line in assessed if line.life_risk)
    caption = f"{plural(total, 'risco ativo', 'riscos ativos')} · avaliação {assessment}"
    if nature:
        caption += f" · {'somente ameaças' if nature == THREAT else 'somente oportunidades'}"
    caption += f" · escala {params.scale.name}"
    return RiskMatrix(
        assessment=assessment,
        nature=nature,
        parameters=params,
        bands=_band_styles(params.scale, nature),
        cells=cells,
        registered=len(lines),
        total=total,
        unassessed=len(universe) - total,
        life_risks=life_risks,
        movement=movement,
        caption=caption,
        notes=_matrix_notes(
            nature=nature,
            assessment=assessment,
            unassessed=len(universe) - total,
            life_risks=life_risks,
            life_risk_is_high=params.scale.life_risk_is_high,
        ),
        movement_note=_movement_note(movement),
    )


def _cell(
    *,
    probability: int,
    impact: int,
    lines: Sequence[service.RiskLine],
    assessment: str,
    nature: str,
    params: RiskParameters,
) -> MatrixCell:
    score = calculations.risk_score(probability, impact)
    severity = calculations.risk_severity(score, params.scale)
    risks = tuple(
        MatrixRisk(line.code, line.title, line.nature, line.life_risk, line.project_id)
        for line in lines
        if (view := _displayed(line, assessment)) is not None
        and view.probability == probability
        and view.impact == impact
    )
    href = (
        presentation.cell_address(
            RiskFilters(
                probability=probability, impact=impact, assessment=assessment, nature=nature
            )
        )
        if risks
        else None
    )
    return MatrixCell(
        probability=probability,
        impact=impact,
        score=score,
        severity=severity,
        risks=risks,
        href=href,
    )


def _displayed(line: service.RiskLine, assessment: str) -> service.AssessmentView | None:
    """The assessment the matrix draws: the inherent one, or the residual (else inherent)."""
    return line.inherent if assessment == INHERENT else line.current


def _movement(lines: Sequence[service.RiskLine]) -> tuple[Movement, ...]:
    moves = [
        Movement(
            code=line.code,
            title=line.title,
            nature=line.nature,
            project_id=line.project_id,
            inherent_score=line.inherent.score,
            inherent_band=line.inherent.severity,
            residual_score=line.residual.score,
            residual_band=line.residual.severity,
            no_reduction=calculations.has_no_reduction(
                line.nature, line.residual.score, line.inherent.score
            ),
        )
        for line in lines
        if line.has_plan and line.inherent is not None and line.residual is not None
    ]
    moves.sort(
        key=lambda item: (
            -item.inherent_score,
            item.residual_score - item.inherent_score,
            item.code,
        )
    )
    return tuple(moves)


def _band_styles(scale: Scale, nature: str) -> tuple[BandStyle, ...]:
    """The active scale painted from the lightest to the heaviest, inverted for opportunities."""
    palette = OPPORTUNITY_STYLES if nature == OPPORTUNITY else THREAT_STYLES
    total = len(scale.bands)
    styles = []
    for rank, band in enumerate(scale.bands):
        index = 0 if total <= 1 else round(rank * (len(palette) - 1) / (total - 1))
        tone, icon = palette[index]
        styles.append(
            BandStyle(
                band=band,
                minimum=band.minimum,
                maximum=calculations.band_ceiling(band, scale),
                tone=tone,
                icon=icon,
                level=3 if rank == total - 1 else 2,
            )
        )
    return tuple(styles)


def _matrix_notes(
    *,
    nature: str,
    assessment: str,
    unassessed: int,
    life_risks: int,
    life_risk_is_high: bool,
) -> tuple[str, ...]:
    """The notes below the matrix, in the order the prototype listed them."""
    notes: list[str] = []
    if unassessed:
        notes.append(
            plural(
                unassessed,
                "risco identificado sem avaliação fica fora da matriz",
                "riscos identificados sem avaliação ficam fora da matriz",
            )
            + "."
        )
    if nature == OPPORTUNITY:
        notes.append("Para oportunidades, score alto indica prioridade de captura.")
    if life_risk_is_high and life_risks:
        notes.append(
            "Na escala ativa, risco à vida é sempre da faixa mais alta: "
            + plural(life_risks, "risco", "riscos")
            + " com classificação acima da cor da célula."
        )
    if assessment == RESIDUAL:
        notes.append("Riscos sem avaliação residual entram com a inerente.")
    return tuple(notes)


def _movement_note(movement: Sequence[Movement]) -> str:
    without = [item.code for item in movement if item.no_reduction]
    parts: list[str] = []
    if without:
        parts.append(
            "Sem redução após o plano, o risco entra na pauta de escalonamento ("
            + ", ".join(without)
            + ")."
        )
    parts.append(
        "Barra clara: inerente; barra cheia: residual. "
        "Oportunidades crescem quando a resposta funciona."
    )
    return " ".join(parts)


# ── Painel de riscos ─────────────────────────────────────────────────────────────────────────


def risk_panel(session: Session, *, user: User, scope: Scope, reference_date: date) -> RiskPanel:
    """The panel of the scope: the five indicators, the categories, the evolution and the agenda."""
    rbac.require_module(user, MODULE)
    params = service.parameters(session, reference_date=reference_date)
    lines = _scope_lines(
        session, user=user, scope=scope, params=params, reference_date=reference_date
    )
    summary = service._summary(lines, RESIDUAL, params)
    active = [line for line in lines if line.active]
    threats = [line for line in active if line.nature == THREAT and line.inherent is not None]
    return RiskPanel(
        summary=summary,
        parameters=params,
        reduction_avg_pct=_reduction_average(threats),
        reduction_target_pct=_reduction_target(threats, params),
        categories=_categories(threats),
        evolution=_evolution(session, project_id=scope.project_id, reference_date=reference_date),
        agenda=_agenda(active, params, reference_date),
    )


def _reduction_average(lines: Sequence[service.RiskLine]) -> int | None:
    """Redução média: the mean drop from the inherent to the residual, over the assessed threats."""
    values = [
        (line.inherent.score - line.residual.score) / line.inherent.score
        for line in lines
        if line.inherent is not None and line.residual is not None and line.inherent.score > 0
    ]
    return _average_pct(values)


def _reduction_target(lines: Sequence[service.RiskLine], params: RiskParameters) -> int | None:
    """A meta do protótipo: the mean reduction that brings each threat up to its target band."""
    bands = {band.id: band for band in params.scale.bands}
    values: list[float] = []
    for line in lines:
        if line.inherent is None or line.residual is None or line.inherent.score <= 0:
            continue
        target = bands.get(line.target_severity or "")
        if target is None:
            continue
        ceiling = calculations.band_ceiling(target, params.scale)
        values.append(max(0.0, (line.inherent.score - ceiling) / line.inherent.score))
    return _average_pct(values)


def _average_pct(values: Sequence[float]) -> int | None:
    if not values:
        return None
    mean = sum(values) / len(values) * 100
    return int(Decimal(repr(mean)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _categories(lines: Sequence[service.RiskLine]) -> tuple[CategoryExposure, ...]:
    """Exposição por categoria (RBS): the score summed by group, the heaviest first."""
    grouped: dict[str, list[service.RiskLine]] = {}
    for line in lines:
        grouped.setdefault(line.category_group, []).append(line)
    items = [
        CategoryExposure(
            group=group,
            score=sum(line.current.score for line in group_lines if line.current is not None),
            risks=len(group_lines),
            vme_cents=sum(line.vme_cents for line in group_lines),
            href=presentation.screen_address(RiskFilters(category=group)),
        )
        for group, group_lines in grouped.items()
    ]
    items.sort(key=lambda item: (-item.score, -item.vme_cents, item.group))
    return tuple(items)


def _evolution(
    session: Session, *, project_id: int | None, reference_date: date
) -> tuple[EvolutionPoint, ...]:
    """The monthly residual score of the threats, reconstructed from the history (D6)."""
    current = calendario.period_of(calendario.MONTHLY, reference_date)
    windows: list[calculations.MonthWindow] = []
    for offset in range(-(EVOLUTION_MONTHS - 1), 1):
        label = calendario.add_periods(calendario.MONTHLY, current, offset)
        if label is None:
            continue
        end = calendario.cut_date(calendario.MONTHLY, label, reference_date)
        if end is not None:
            windows.append(calculations.MonthWindow(label=label, end=end))
    histories = _histories(session, project_id=project_id)
    scores = calculations.monthly_residual_scores(histories, tuple(windows))
    return tuple(
        EvolutionPoint(month=item.month, score=item.score, current=item.month == current)
        for item in scores
    )


def _histories(session: Session, *, project_id: int | None) -> tuple[calculations.RiskHistory, ...]:
    """The dated scores of every threat of the scope: its assessments and its reviews."""
    statement = select(Risk).where(Risk.nature == THREAT, Risk.hidden.is_(False)).order_by(Risk.id)
    if project_id is not None:
        statement = statement.where(Risk.project_id == project_id)
    risks = list(session.scalars(statement).all())
    events: dict[int, list[calculations.ScoredEvent]] = {risk.id: [] for risk in risks}
    ids = list(events)
    if ids:
        assessments = select(RiskAssessment).where(RiskAssessment.risk_id.in_(ids))
        for assessment in session.scalars(assessments):
            events[assessment.risk_id].append(
                calculations.ScoredEvent(
                    assessment.assessed_on,
                    assessment.probability * assessment.impact,
                    assessment.kind == RESIDUAL,
                )
            )
        reviews = select(RiskReview).where(RiskReview.risk_id.in_(ids))
        for review in session.scalars(reviews):
            events[review.risk_id].append(
                calculations.ScoredEvent(
                    review.reviewed_on, review.score_to, review.kind == RESIDUAL
                )
            )
    return tuple(
        calculations.RiskHistory(
            identified_on=risk.identified_on,
            closed_on=risk.closing_date,
            events=tuple(events[risk.id]),
        )
        for risk in risks
    )


def _agenda(
    lines: Sequence[service.RiskLine], params: RiskParameters, reference_date: date
) -> tuple[AgendaEntry, ...]:
    """The active risks with at least one reason of the escalation agenda, the heaviest first."""
    entries: list[AgendaEntry] = []
    for line in lines:
        reasons = calculations.pauta_reasons(_pauta_facts(line, reference_date), params)
        if not reasons:
            continue
        entries.append(
            AgendaEntry(
                code=line.code,
                title=line.title,
                category_label=line.category_label,
                nature=line.nature,
                score=line.current.score if line.current is not None else None,
                severity=line.current.severity if line.current is not None else None,
                reasons=reasons,
                owner_name=line.owner_name,
                project_id=line.project_id,
            )
        )
    entries.sort(key=lambda item: (-(item.score or 0), -len(item.reasons), item.code))
    return tuple(entries)


def _pauta_facts(line: service.RiskLine, reference_date: date) -> calculations.PautaFacts:
    return calculations.PautaFacts(
        active=line.active,
        situation=line.situation,
        nature=line.nature,
        inherent_band_id=line.inherent.severity.id if line.inherent is not None else None,
        current_band_id=line.current.severity.id if line.current is not None else None,
        inherent_score=line.inherent.score if line.inherent is not None else None,
        residual_score=line.residual.score if line.residual is not None else None,
        has_plan=line.has_plan,
        plan_pending=line.plan_pending,
        target_band_id=line.target_severity,
        days_to_target=calculations.days_until(line.target_date, reference_date),
        review_overdue=line.review_overdue,
        trigger_on=line.trigger_on,
    )


def _scope_lines(
    session: Session, *, user: User, scope: Scope, params: RiskParameters, reference_date: date
) -> list[service.RiskLine]:
    """The lines of the scope, as the register reads them: no hidden risk, every situation."""
    return service._lines(
        service._Ctx(session, user, reference_date),
        project_id=scope.project_id,
        include_hidden=False,
        params=params,
    )


# ── Envio da pauta ───────────────────────────────────────────────────────────────────────────


def agenda_default_message(panel: RiskPanel, *, scope_label: str, reference_date: date) -> str:
    """O texto padrão do protótipo para o envio da pauta ao gerente do projeto."""
    lines = [
        AGENDA_GREETING,
        "",
        (
            f"Segue a pauta de escalonamento de riscos ({scope_label}), "
            f"referência {reference_date:%d/%m/%Y}:"
        ),
        "",
    ]
    lines.extend(_agenda_line(item) for item in panel.agenda)
    lines.extend(("", AGENDA_REQUEST, "", AGENDA_FOOTER))
    return "\n".join(lines)


def _agenda_line(item: AgendaEntry) -> str:
    shown = (
        "sem avaliação"
        if item.score is None or item.severity is None
        else f"{item.score} {item.severity.name}"
    )
    return (
        f"* {item.code} {item.title}: residual {shown}. "
        f"Motivo: {'; '.join(item.reasons)}. Dono: {item.owner_name}."
    )


@dataclass(frozen=True)
class AgendaTarget:
    """O destinatário do envio da pauta: o gerente do projeto e o rótulo do escopo."""

    email: str
    scope_label: str
    project_code: str
    project_id: int


def agenda_target(session: Session, *, scope: Scope, panel: RiskPanel) -> AgendaTarget:
    """Quem recebe a pauta: o gerente do projeto, recusando o Portfólio, a pauta vazia e o sem e-mail."""
    project_id = scope.require_project()
    if not panel.agenda:
        raise InvalidDataError(AGENDA_EMPTY_MESSAGE)
    project = configuracoes.find_project(session, project_id)
    if project is None:
        raise InvalidDataError(service.UNKNOWN_PROJECT_MESSAGE)
    email = _manager_email(session, project.manager_person_id)
    if not email:
        raise InvalidDataError(NO_MANAGER_MESSAGE)
    return AgendaTarget(
        email=email,
        scope_label=f"{project.code} · {project.name}",
        project_code=project.code,
        project_id=project_id,
    )


def send_risk_agenda(
    session: Session,
    *,
    user: User,
    scope: Scope,
    reference_date: date,
    message: str = "",
    channel: NotificationChannel | None = None,
) -> notification.NotificationOutcome:
    """Envia a pauta ao gerente do projeto pela porta de notificação (``pauta_riscos``).

    The send belongs to a project: in the Portfólio there is no manager to address, so the scope
    asks for the project first. The recipient comes from the register, never from the screen; the
    body is the default text of the prototype unless the form sends its own. The register and the
    trail line go in the caller's transaction and, with the e-mail sending off, stay ``simulado``.
    """
    rbac.require(user, Permission.WRITE)
    panel = risk_panel(session, user=user, scope=scope, reference_date=reference_date)
    target = agenda_target(session, scope=scope, panel=panel)
    body = message.strip() or agenda_default_message(
        panel, scope_label=target.scope_label, reference_date=reference_date
    )
    return notification.send(
        session,
        user_id=user.id,
        request=notification.NotificationRequest(
            kind=notification.RISK_AGENDA,
            project_id=target.project_id,
            recipients=[target.email],
            subject=AGENDA_SUBJECT.format(scope=target.project_code),
            body=body,
        ),
        channel=channel,
    )


def _manager_email(session: Session, person_id: int | None) -> str:
    if not person_id:
        return ""
    person = configuracoes.find_people(session, {person_id}).get(person_id)
    return (person.email or "") if person is not None else ""
