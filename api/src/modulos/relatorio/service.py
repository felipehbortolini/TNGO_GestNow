"""Business facade for the Management reporting module.

Análise do período (ISSUE-081/ISSUE-082, D6): o texto executivo e analítico de um módulo (02 a
07) num tipo (Semanal ou Mensal) e período de um projeto ou do Portfólio, com os desvios
negativos detectados no servidor a partir das fachadas donas e o comentário obrigatório de cada
um nos módulos 02, 03, 04 e 06, gravado pela chave do desvio. Um registro por projeto, módulo,
tipo e período; o semanal e o mensal são distintos e a análise do Portfólio (projeto nulo) não
se mistura com a de um projeto. Writing asks for Membro; deleting asks for Gestor. Nothing here
reads the clock: the reference date comes from ``core.calendario`` through the caller.

The module is the report's own (D9): the 083 reads the analyses from here, and the module of
the row names the analysed module. The figures come from the public facades of Planning,
Financeiro, Suprimentos, Riscos, Qualidade and HSE, called with the period cut; no formula of
an owner is duplicated.

Relatório gerencial (ISSUE-083, D12): ``report_status`` draws the emission modal — the scope,
the type, the period and the real situation of the period's report and of each module's
analysis (read without WRITE, so a Visualizador sees it) — and ``report_view`` draws the A4
sheets. The cut is ``calculations.report_period_cutoff`` (the end of the period, limited to
the reference date) and the sheet of Planning reuses the same reading as the analysis: the
position, the productivity, the owner's curve, the bars of the advance per period and the
areas. The links the modal offers point at the screens that register each piece.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.core import audit, calendario, rbac, versioning
from src.core.audit import TrailLine
from src.core.errors import InvalidDataError
from src.core.rbac import Permission, User
from src.core.scope import PORTFOLIO_PARAMETER, Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.relatorio import calculations, validation
from src.modulos.relatorio.models import Analysis, AnalysisDeviation

MODULE = "relatorio"

ANALYSIS_MODULES: Mapping[str, str] = {
    "planejamento": "02 Planejamento",
    "financeiro": "03 Gestão Financeira",
    "suprimentos": "04 Suprimentos",
    "riscos": "05 Gestão de Riscos",
    "qualidade": "06 Gestão da Qualidade",
    "hse": "07 HSE",
}

# Todo desvio negativo detectado exige comentário nos módulos 02, 03, 04 e 06; em 05 e 07 só o
# texto é exigido (o protótipo não define detecção para eles).
DEVIATION_REQUIRED: Mapping[str, bool] = {
    "planejamento": True,
    "financeiro": True,
    "suprimentos": True,
    "riscos": False,
    "qualidade": False,
    "hse": False,
}

# As seções que o relatório já implementa, na ordem do modal; cresce nas ISSUE-084/ISSUE-085.
REPORT_SECTIONS: tuple[tuple[str, str], ...] = (("planejamento", "Planejamento (2 páginas)"),)

# A tela de cada módulo onde a análise do período é registrada: o endereço que o modal oferece.
REPORT_ANALYSIS_SCREENS: Mapping[str, str] = {
    "planejamento": "planejamento/relato",
    "financeiro": "financeiro/kpis",
    "suprimentos": "suprimentos/painel",
    "riscos": "riscos/painel",
    "qualidade": "qualidade/painel",
    "hse": "hse/painel",
}

# A tela onde o relato do período é registrado (02 Planejamento), com o endereço de abertura.
REPORT_RELATO_SCREEN = "planejamento/relato"

FigureSet = (
    calculations.PlanningFigures
    | calculations.CostFigures
    | calculations.ProcurementFigures
    | calculations.RiskFigures
    | calculations.QualityFigures
    | calculations.HseFigures
)

NOT_FOUND_MESSAGE = "A análise do período não foi encontrada."

UNKNOWN_PROJECT_MESSAGE = "O projeto não foi encontrado."


@dataclass(frozen=True)
class AnalysisOption:
    """Um período da lista do passo 1: o rótulo, se está em andamento e se tem análise."""

    period: str
    label: str
    in_progress: bool
    registered: bool


@dataclass(frozen=True)
class AnalysisPeriodsView:
    """O passo 1: o módulo, o tipo e os períodos do início do projeto até o corrente."""

    module: str
    module_label: str
    kind: str
    project_label: str
    options: tuple[AnalysisOption, ...]
    selected: str


@dataclass(frozen=True)
class AnalysisDeviationView:
    """Um desvio detectado no corte, com o comentário gravado (vazio é pendente)."""

    key: str
    indicator: str
    description: str
    comment: str


@dataclass(frozen=True)
class AnalysisRecordView:
    """O registro gravado como o formulário o lê."""

    id: int
    version: int
    text: str
    updated_at: datetime
    updated_by: str


@dataclass(frozen=True)
class PreviousAnalysis:
    """A análise do período imediatamente anterior do mesmo tipo, para o Copiar."""

    period: str
    label: str
    text: str


@dataclass(frozen=True)
class AnalysisView:
    """O passo 2: o resumo do período, os desvios, o registro e o anterior."""

    module: str
    module_label: str
    kind: str
    period: str
    period_label: str
    in_progress: bool
    project_label: str
    record: AnalysisRecordView | None
    deviations: tuple[AnalysisDeviationView, ...]
    pending: int
    previous: PreviousAnalysis | None
    summary: tuple[calculations.SummaryItem, ...]
    sem_fechamento: bool
    deviation_required: bool

    @property
    def text(self) -> str:
        """O texto que o formulário mostra: o gravado, ou vazio quando não há registro."""
        return self.record.text if self.record is not None else ""


@dataclass(frozen=True)
class DeletedAnalysis:
    """O que a exclusão devolve para a mensagem: a identidade e o rótulo do período."""

    id: int
    module: str
    kind: str
    period: str
    period_label: str


@dataclass(frozen=True)
class AnalysisRequest:
    """O que a gravação recebe do formulário: a identidade, o texto e os comentários."""

    module: str
    kind: str
    period: str
    analysis_id: int | None = None
    version: str | None = None
    text: str = ""
    comments: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _Collected:
    """As figuras coletadas de um módulo, com o aviso de que o custo não tem fechamento."""

    figures: FigureSet
    sem_fechamento: bool


# ── Leitura ────────────────────────────────────────────────────────────────


def analysis_options(
    session: Session,
    *,
    user: User,
    scope: Scope,
    module: str,
    kind: str,
    reference_date: date,
) -> AnalysisPeriodsView:
    """Os períodos do passo 1, do início do escopo ao corrente, com a situação de cada um.

    O período padrão é o anterior ao corrente; fora do intervalo, o mais recente. No Portfólio a
    faixa vai do início mais antigo da carteira e o rótulo diz quantos projetos ela tem.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    _check_module(module)
    _check_kind(kind)
    registered = set(
        session.scalars(
            select(Analysis.period).where(
                Analysis.project_id == scope.project_id,
                Analysis.module == module,
                Analysis.kind == kind,
            )
        )
    )
    options = calculations.period_options(
        kind,
        project_start=_project_start(session, scope),
        reference_date=reference_date,
        taken=registered,
    )
    return AnalysisPeriodsView(
        module=module,
        module_label=ANALYSIS_MODULES[module],
        kind=kind,
        project_label=_scope_label(session, scope),
        options=tuple(
            AnalysisOption(
                period=option.period,
                label=option.label,
                in_progress=option.in_progress,
                registered=option.taken,
            )
            for option in options
        ),
        selected=_default_period(options, kind=kind, reference_date=reference_date),
    )


def analysis_view(
    session: Session,
    *,
    user: User,
    scope: Scope,
    module: str,
    kind: str,
    period: str,
    reference_date: date,
) -> AnalysisView:
    """O passo 2 de um módulo, tipo e período: resumo, desvios, registro e o anterior."""
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    return _analysis_reading(
        session,
        user=user,
        scope=scope,
        module=module,
        kind=kind,
        period=period,
        reference_date=reference_date,
    )


def _analysis_reading(
    session: Session,
    *,
    user: User,
    scope: Scope,
    module: str,
    kind: str,
    period: str,
    reference_date: date,
) -> AnalysisView:
    """A leitura do passo 2 sem exigir WRITE: o relatório gerencial (READ) também a usa."""
    rbac.require_module(user, MODULE)
    _check_module(module)
    _check_kind(kind)
    _check_period(
        kind,
        period,
        project_start=_project_start(session, scope),
        reference_date=reference_date,
    )
    collected = _collect(
        session,
        user=user,
        scope=scope,
        module=module,
        kind=kind,
        period=period,
        reference_date=reference_date,
    )
    return _view_of(
        session,
        module=module,
        kind=kind,
        period=period,
        project_label=_scope_label(session, scope),
        collected=collected,
        record=_record_of(
            session, project_id=scope.project_id, module=module, kind=kind, period=period
        ),
        previous=_previous_of(
            session, project_id=scope.project_id, module=module, kind=kind, period=period
        ),
        reference_date=reference_date,
    )


def analysis_record(
    session: Session, *, project_id: int, module: str, kind: str, period: str
) -> Analysis | None:
    """A análise do projeto, módulo, tipo e período, ou ``None`` quando não há registro."""
    return _record_of(session, project_id=project_id, module=module, kind=kind, period=period)


def _view_of(
    session: Session,
    *,
    module: str,
    kind: str,
    period: str,
    project_label: str,
    collected: _Collected,
    record: Analysis | None,
    previous: PreviousAnalysis | None,
    reference_date: date,
) -> AnalysisView:
    """Monta a leitura do passo 2 a partir das figuras, do registro e do anterior."""
    deviations = _detected(module, collected.figures)
    comments = {row.key: row.comment for row in record.deviations} if record is not None else {}
    views = tuple(
        AnalysisDeviationView(
            key=deviation.key,
            indicator=deviation.indicator,
            description=calculations.deviation_description(deviation),
            comment=comments.get(deviation.key, ""),
        )
        for deviation in deviations
    )
    required = DEVIATION_REQUIRED[module]
    return AnalysisView(
        module=module,
        module_label=ANALYSIS_MODULES[module],
        kind=kind,
        period=period,
        period_label=calculations.period_name(kind, period),
        in_progress=calendario.is_partial(kind, period, reference_date),
        project_label=project_label,
        record=(
            AnalysisRecordView(
                id=record.id,
                version=record.version,
                text=record.text,
                updated_at=record.updated_at,
                updated_by=configuracoes.person_names(session, [record.updated_by_id]).get(
                    record.updated_by_id, ""
                ),
            )
            if record is not None
            else None
        ),
        deviations=views,
        pending=sum(1 for view in views if not view.comment) if required else 0,
        previous=previous,
        summary=calculations.analysis_summary(module, collected.figures),
        sem_fechamento=collected.sem_fechamento,
        deviation_required=required,
    )


# ── Escrita ────────────────────────────────────────────────────────────────


def save_analysis(
    session: Session,
    *,
    user: User,
    scope: Scope,
    request: AnalysisRequest,
    reference_date: date,
) -> AnalysisView:
    """Cria a análise ou salva a edição de uma, ou recusa com 422 por campo.

    Gravar exige Membro. A análise nova pertence ao projeto do escopo; no Portfólio ela nasce com
    projeto nulo, sobre os números consolidados da carteira. O módulo, o tipo e o período de uma
    análise existente são mantidos: só o texto e os comentários mudam. A versão vencida é
    recusada com 409.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.WRITE)
    existing = (
        _find(session, scope, request.analysis_id) if request.analysis_id is not None else None
    )
    project_id = existing.project_id if existing is not None else scope.project_id
    module = existing.module if existing is not None else request.module
    kind = existing.kind if existing is not None else request.kind
    period = existing.period if existing is not None else request.period
    text = validation.clean_text(request.text)
    errors: dict[str, str] = {}
    errors.update(validation.validate_module(module, ANALYSIS_MODULES))
    if not errors:
        errors.update(validation.validate_kind(kind))
    if not errors:
        problem = calculations.period_error(
            kind,
            period,
            project_start=_project_start(session, scope),
            reference_date=reference_date,
        )
        errors.update(validation.validate_period(kind, period, problem=problem))
    errors.update(validation.validate_text(text))
    if existing is None:
        duplicate = _record_of(
            session, project_id=project_id, module=module, kind=kind, period=period
        )
        if duplicate is not None:
            errors[validation.FIELD_PERIOD] = _duplicate_message(kind)
    if errors:
        raise InvalidDataError(errors)
    collected = _collect(
        session,
        user=user,
        scope=scope,
        module=module,
        kind=kind,
        period=period,
        reference_date=reference_date,
    )
    deviations = _detected(module, collected.figures)
    comment_errors = validation.validate_comments(
        [deviation.key for deviation in deviations],
        request.comments,
        required=DEVIATION_REQUIRED[module],
    )
    if comment_errors:
        raise InvalidDataError(comment_errors)
    if existing is not None:
        analysis = _edit(
            session,
            user=user,
            analysis=existing,
            version=request.version,
            text=text,
            deviations=deviations,
            comments=request.comments,
        )
    else:
        analysis = _assemble(
            project_id=project_id,
            module=module,
            kind=kind,
            period=period,
            person_id=user.person_id,
            text=text,
            deviations=deviations,
            comments=request.comments,
        )
        insert_analysis(session, user_id=user.id, analysis=analysis)
    return _view_of(
        session,
        module=module,
        kind=kind,
        period=period,
        project_label=_scope_label(session, scope),
        collected=collected,
        record=analysis,
        previous=_previous_of(
            session, project_id=project_id, module=module, kind=kind, period=period
        ),
        reference_date=reference_date,
    )


def insert_analysis(session: Session, *, user_id: int, analysis: Analysis) -> Analysis:
    """Grava uma análise montada com a trilha da criação (o conteúdo inteiro, depois).

    A tela cria por ``save_analysis``; a carga de demonstração chama esta, com os autores e
    os horários do protótipo já no registro.
    """
    session.add(analysis)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user_id,
            entity=Analysis.__tablename__,
            record_id=analysis.id,
            action=audit.CREATED,
            after=_aggregate(analysis),
            project_id=analysis.project_id,
        ),
    )
    return analysis


def delete_analysis(
    session: Session, *, user: User, scope: Scope, analysis_id: int, version: str | None
) -> DeletedAnalysis:
    """Exclui a análise, que deixa o período pendente outra vez; exige Gestor.

    Devolve o que foi excluído para a mensagem. A versão vencida é recusada com 409.
    """
    rbac.require_module(user, MODULE)
    rbac.require(user, Permission.MANAGE)
    analysis = _find(session, scope, analysis_id)
    deleted = DeletedAnalysis(
        id=analysis.id,
        module=analysis.module,
        kind=analysis.kind,
        period=analysis.period,
        period_label=calculations.period_name(analysis.kind, analysis.period),
    )
    before = _aggregate(analysis)
    versioning.require(session, analysis, version)
    session.delete(analysis)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=Analysis.__tablename__,
            record_id=deleted.id,
            action=audit.DELETED,
            before=before,
            project_id=analysis.project_id,
        ),
    )
    return deleted


def _assemble(
    *,
    project_id: int | None,
    module: str,
    kind: str,
    period: str,
    person_id: int,
    text: str,
    deviations: Sequence[calculations.Deviation],
    comments: Mapping[str, str],
) -> Analysis:
    """Uma análise ainda não escrita, com os autores e os carimbos de agora."""
    moment = calendario.now()
    return Analysis(
        project_id=project_id,
        created_by_id=person_id,
        updated_by_id=person_id,
        module=module,
        kind=kind,
        period=period,
        text=text,
        created_at=moment,
        updated_at=moment,
        deviations=_deviation_rows(deviations, comments),
    )


def _edit(
    session: Session,
    *,
    user: User,
    analysis: Analysis,
    version: str | None,
    text: str,
    deviations: Sequence[calculations.Deviation],
    comments: Mapping[str, str],
) -> Analysis:
    """Salva o conteúdo de uma análise existente depois da checagem de versão, com a trilha."""
    before = _aggregate(analysis)
    versioning.require(session, analysis, version)
    analysis.text = text
    analysis.deviations = _deviation_rows(deviations, comments)
    analysis.updated_by_id = user.person_id
    analysis.updated_at = calendario.now()
    versioning.advance(analysis)
    session.flush()
    audit.append(
        session,
        TrailLine(
            user_id=user.id,
            entity=Analysis.__tablename__,
            record_id=analysis.id,
            action=audit.UPDATED,
            before=before,
            after=_aggregate(analysis),
            project_id=analysis.project_id,
        ),
    )
    return analysis


def _deviation_rows(
    deviations: Sequence[calculations.Deviation], comments: Mapping[str, str]
) -> list[AnalysisDeviation]:
    """Só os comentários dos desvios detectados, por chave: comentário vazio não é gravado."""
    rows: list[AnalysisDeviation] = []
    for deviation in deviations:
        comment = validation.clean_text(comments.get(deviation.key, ""))
        if comment:
            rows.append(
                AnalysisDeviation(key=deviation.key, indicator=deviation.indicator, comment=comment)
            )
    return rows


def _aggregate(analysis: Analysis) -> dict[str, Any]:
    """A análise e os seus desvios como a trilha os guarda, pelas colunas em português."""
    return {
        **audit.snapshot(analysis),
        "desvios": [
            {"chave": row.key, "indicador": row.indicator, "comentario": row.comment}
            for row in analysis.deviations
        ],
    }


def _duplicate_message(kind: str) -> str:
    return f"Já existe análise {kind.lower()} para este período; edite o registro existente."


# ── Relatório gerencial: o modal de emissão (ISSUE-083) ────────────────────


@dataclass(frozen=True)
class ReportScopeOption:
    """Uma opção de "Relatório de": o valor que viaja, o rótulo e se está escolhida."""

    value: str
    label: str
    selected: bool


@dataclass(frozen=True)
class ReportPeriodOption:
    """Um período da lista do modal: o rótulo, em andamento, padrão e escolhido."""

    period: str
    label: str
    in_progress: bool
    is_default: bool
    selected: bool


@dataclass(frozen=True)
class ReportSectionOption:
    """Uma seção do Conteúdo: a chave, o rótulo e se está marcada."""

    key: str
    label: str
    selected: bool


@dataclass(frozen=True)
class ReportRelatoStatus:
    """A situação do relato do período: registrado ou pendente, com o endereço de registro."""

    registered: bool
    url: str
    project_label: str = ""


@dataclass(frozen=True)
class ReportAnalysisStatus:
    """A situação da análise do período de um módulo, com o endereço de registro."""

    module: str
    label: str
    url: str
    registered: bool
    deviations: int
    pending: int
    required: bool

    @property
    def situation(self) -> str:
        """Como a situação se lê: ``registered``, ``deviations`` (sem comentário) ou ``missing``."""
        if not self.registered:
            return "missing"
        return "deviations" if self.pending else "registered"


@dataclass(frozen=True)
class ReportStatusView:
    """O modal de emissão: o escopo, o tipo, o período e a situação real do período."""

    scope: str
    scope_label: str
    kind: str
    period: str
    period_label: str
    in_progress: bool
    project_options: tuple[ReportScopeOption, ...]
    period_options: tuple[ReportPeriodOption, ...]
    relato: ReportRelatoStatus | None
    project_relatos: tuple[ReportRelatoStatus, ...]
    analyses: tuple[ReportAnalysisStatus, ...]
    sections: tuple[ReportSectionOption, ...]


def report_scope(session: Session, *, fallback: Scope, requested: str) -> Scope:
    """O escopo do relatório que o modal pede: ``portfolio``, o id de um projeto, ou o do request.

    O parâmetro ``escopo`` é o do formulário (o "Relatório de"); sem ele vale o escopo do
    request. Um valor que não nomeia projeto do cadastro é recusado com a mensagem do projeto.
    """
    text = (requested or "").strip().lower()
    if not text:
        return fallback
    if text == PORTFOLIO_PARAMETER:
        return Scope(project_id=None, source="url")
    if text.isascii() and text.isdecimal():
        project_id = int(text)
        if any(project.id == project_id for project in configuracoes.list_projects(session)):
            return Scope(project_id=project_id, source="url")
    raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)


def report_status(
    session: Session,
    *,
    user: User,
    scope: Scope,
    kind: str,
    period: str,
    reference_date: date,
    sections: Sequence[str] = (),
) -> ReportStatusView:
    """O modal de emissão: o escopo, o tipo e o período escolhidos e a situação real.

    O tipo e o período pedidos valem quando são válidos para o escopo; fora disso valem os
    padrões (Semanal e o período anterior ao corrente), como o formulário abre. A situação de
    cada módulo lê o registro e recomputa os desvios sem exigir WRITE — o modal é READ e um
    Visualizador precisa vê-lo. No Portfólio a situação do relato sai por projeto; no projeto,
    a do próprio.
    """
    rbac.require_module(user, MODULE)
    chosen_kind = kind if kind in validation.KINDS else validation.WEEKLY
    options = calculations.period_options(
        chosen_kind,
        project_start=_project_start(session, scope),
        reference_date=reference_date,
        taken=(),
    )
    default = _default_period(options, kind=chosen_kind, reference_date=reference_date)
    chosen_period = period if period in {option.period for option in options} else default
    return ReportStatusView(
        scope=scope.parameter,
        scope_label=_scope_label(session, scope),
        kind=chosen_kind,
        period=chosen_period,
        period_label=calculations.period_name(chosen_kind, chosen_period),
        in_progress=calculations.is_partial_period(chosen_kind, chosen_period, reference_date),
        project_options=_scope_options(session, scope),
        period_options=tuple(
            ReportPeriodOption(
                period=option.period,
                label=option.label,
                in_progress=option.in_progress,
                is_default=option.period == default,
                selected=option.period == chosen_period,
            )
            for option in options
        ),
        relato=(
            None
            if scope.is_portfolio
            else _relato_status(
                session, user=user, scope=scope, kind=chosen_kind, period=chosen_period
            )
        ),
        project_relatos=(
            _project_relatos(session, user=user, kind=chosen_kind, period=chosen_period)
            if scope.is_portfolio
            else ()
        ),
        analyses=tuple(
            _analysis_status(
                session,
                user=user,
                scope=scope,
                module=module,
                kind=chosen_kind,
                period=chosen_period,
                reference_date=reference_date,
            )
            for module in ANALYSIS_MODULES
        ),
        sections=_section_options(sections),
    )


def _scope_options(session: Session, scope: Scope) -> tuple[ReportScopeOption, ...]:
    """As opções do "Relatório de": o Portfólio e os projetos do cadastro."""
    options = [
        ReportScopeOption(
            value=PORTFOLIO_PARAMETER,
            label="Portfólio (todos os projetos)",
            selected=scope.is_portfolio,
        )
    ]
    options.extend(
        ReportScopeOption(
            value=str(project.id),
            label=f"{project.code} · {project.name}",
            selected=project.id == scope.project_id,
        )
        for project in configuracoes.list_projects(session)
    )
    return tuple(options)


def _section_options(sections: Sequence[str]) -> tuple[ReportSectionOption, ...]:
    """As seções implementadas; o que o formulário não mandou entra marcado."""
    requested = {key for key in sections if key}
    return tuple(
        ReportSectionOption(key=key, label=label, selected=not requested or key in requested)
        for key, label in REPORT_SECTIONS
    )


def _relato_status(
    session: Session, *, user: User, scope: Scope, kind: str, period: str
) -> ReportRelatoStatus:
    """A situação do relato do projeto do escopo: registrado ou pendente, com o endereço."""
    report = _find_report(session, user=user, scope=scope, kind=kind, period=period)
    return ReportRelatoStatus(
        registered=report is not None,
        url=_relato_url(kind, period),
        project_label=_scope_label(session, scope),
    )


def _project_relatos(
    session: Session, *, user: User, kind: str, period: str
) -> tuple[ReportRelatoStatus, ...]:
    """A situação do relato de cada projeto da carteira, com o endereço que reabre a tela nele."""
    from src.modulos.planejamento import service as planejamento

    reports = {
        report.project_id: report
        for report in planejamento.list_reports(
            session, user=user, scope=Scope(project_id=None, source="url")
        )
        if report.kind == kind and report.period == period
    }
    return tuple(
        ReportRelatoStatus(
            registered=project.id in reports,
            url=_project_relato_url(kind, period, project.id),
            project_label=f"{project.code} · {project.name}",
        )
        for project in configuracoes.list_projects(session)
    )


def _analysis_status(
    session: Session,
    *,
    user: User,
    scope: Scope,
    module: str,
    kind: str,
    period: str,
    reference_date: date,
) -> ReportAnalysisStatus:
    """A situação da análise do módulo: registro, desvios detectados e os que estão sem comentário."""
    collected = _collect(
        session,
        user=user,
        scope=scope,
        module=module,
        kind=kind,
        period=period,
        reference_date=reference_date,
    )
    deviations = _detected(module, collected.figures)
    record = _record_of(
        session, project_id=scope.project_id, module=module, kind=kind, period=period
    )
    commented = {row.key for row in record.deviations} if record is not None else set()
    required = DEVIATION_REQUIRED[module]
    return ReportAnalysisStatus(
        module=module,
        label=ANALYSIS_MODULES[module],
        url=_analysis_url(module, kind, period, scope),
        registered=record is not None,
        deviations=len(deviations),
        pending=sum(1 for deviation in deviations if deviation.key not in commented)
        if required
        else 0,
        required=required,
    )


def _relato_url(kind: str, period: str) -> str:
    """O endereço que abre o relato do período (ou o cadastro dele) no mesmo escopo do request."""
    return f"/{REPORT_RELATO_SCREEN}?" + urlencode({"abrir": "1", "tipo": kind, "periodo": period})


def _project_relato_url(kind: str, period: str, project_id: int) -> str:
    """O endereço que reabre a tela do relato no projeto: no Portfólio, um link por projeto."""
    return f"/{REPORT_RELATO_SCREEN}?" + urlencode(
        {"projeto": str(project_id), "abrir": "1", "tipo": kind, "periodo": period}
    )


def _analysis_url(module: str, kind: str, period: str, scope: Scope) -> str:
    """O endereço da tela do módulo que abre a análise do período; no Portfólio, o escopo vai."""
    params = {"analise": "1", "tipo": kind, "periodo": period}
    if scope.is_portfolio:
        params["projeto"] = PORTFOLIO_PARAMETER
    return f"/{REPORT_ANALYSIS_SCREENS[module]}?" + urlencode(params)


# ── Relatório gerencial: as folhas (ISSUE-083) ─────────────────────────────


@dataclass(frozen=True)
class PlanningSheet:
    """A folha 1: a posição no corte, a produtividade, a curva, as barras e as áreas."""

    empty: bool
    figures: calculations.PlanningFigures
    rows: tuple[Any, ...]
    bars: tuple[calculations.PeriodBar, ...]
    bars_chart: Mapping[str, Any]
    curve_chart: Mapping[str, Any]
    deviation_bands: tuple[Decimal, Decimal]
    is_portfolio: bool
    week_label: str

    @property
    def predicted_period(self) -> Decimal | None:
        """O previsto do período do relatório: o da última barra (a semana ou o mês do corte)."""
        return self.bars[-1].predicted if self.bars else None

    @property
    def actual_period(self) -> Decimal | None:
        """O real do período do relatório: o da última barra (a semana ou o mês do corte)."""
        return self.bars[-1].actual if self.bars else None


@dataclass(frozen=True)
class ProjectRelatoSheet:
    """Um projeto na folha 2 do Portfólio: o relato, os seus pontos e o endereço de registro."""

    project_id: int
    project_label: str
    registered: bool
    url: str
    updated: str
    points: tuple[Any, ...]


@dataclass(frozen=True)
class ReportSheets:
    """As folhas do relatório: o cabeçalho do escopo e do período e o que cada seção traz."""

    scope: str
    scope_label: str
    kind: str
    period: str
    period_label: str
    short_period: str
    in_progress: bool
    cut: date
    reference_date: date
    emitted_by: str
    sections: tuple[str, ...]
    is_portfolio: bool
    planning: PlanningSheet | None
    analysis: AnalysisView | None
    analysis_url: str
    relato: Any | None
    relato_url: str
    project_relatos: tuple[ProjectRelatoSheet, ...]
    relato_points: tuple[tuple[str, Any], ...]


def report_view(
    session: Session,
    *,
    user: User,
    scope: Scope,
    kind: str,
    period: str,
    sections: Sequence[str],
    reference_date: date,
) -> ReportSheets:
    """As folhas do relatório para o escopo, o tipo, o período e as seções pedidas.

    O corte é o fim do período limitado à data de referência; o período em andamento sai
    marcado parcial. A folha 1 lê os números pelas fachadas donas e a folha 2 usa a leitura da
    análise do período do próprio módulo, sem exigir WRITE (a tela do relatório é READ).
    """
    rbac.require_module(user, MODULE)
    _check_kind(kind)
    _check_period(
        kind, period, project_start=_project_start(session, scope), reference_date=reference_date
    )
    chosen = _report_sections(sections)
    cut = calculations.report_period_cutoff(kind, period, reference_date)
    if cut is None:
        raise InvalidDataError({validation.FIELD_PERIOD: validation.CHOOSE_MESSAGE})
    planning = None
    analysis = None
    analysis_url = ""
    relato = None
    relato_url = ""
    project_relatos: tuple[ProjectRelatoSheet, ...] = ()
    relato_points: tuple[tuple[str, Any], ...] = ()
    if "planejamento" in chosen:
        planning = _planning_sheet(
            session,
            user=user,
            scope=scope,
            kind=kind,
            period=period,
            reference_date=reference_date,
            cut=cut,
        )
        analysis = _analysis_reading(
            session,
            user=user,
            scope=scope,
            module="planejamento",
            kind=kind,
            period=period,
            reference_date=reference_date,
        )
        analysis_url = _analysis_url("planejamento", kind, period, scope)
        if scope.is_portfolio:
            project_relatos = _project_relato_sheets(session, user=user, kind=kind, period=period)
            relato_points = _portfolio_points(project_relatos)
        else:
            relato = _find_report(session, user=user, scope=scope, kind=kind, period=period)
            relato_url = _relato_url(kind, period)
    return ReportSheets(
        scope=scope.parameter,
        scope_label=_scope_label(session, scope),
        kind=kind,
        period=period,
        period_label=calculations.period_name(kind, period),
        short_period=calculations.short_month(kind, period),
        in_progress=calculations.is_partial_period(kind, period, reference_date),
        cut=cut,
        reference_date=reference_date,
        emitted_by=user.name,
        sections=chosen,
        is_portfolio=scope.is_portfolio,
        planning=planning,
        analysis=analysis,
        analysis_url=analysis_url,
        relato=relato,
        relato_url=relato_url,
        project_relatos=project_relatos,
        relato_points=relato_points,
    )


def _report_sections(sections: Sequence[str]) -> tuple[str, ...]:
    """As seções implementadas que o pedido escolheu; sem nenhuma delas, a mensagem do formulário."""
    known = {key for key, _ in REPORT_SECTIONS}
    requested = tuple(key for key in sections if key)
    if not requested:
        return tuple(key for key, _ in REPORT_SECTIONS)
    chosen = tuple(key for key in requested if key in known)
    if not chosen:
        raise InvalidDataError({validation.FIELD_SECTIONS: validation.SECTION_MESSAGE})
    return chosen


def _planning_sheet(
    session: Session,
    *,
    user: User,
    scope: Scope,
    kind: str,
    period: str,
    reference_date: date,
    cut: date,
) -> PlanningSheet:
    """A folha 1 montada: figuras, linhas por área, barras do avanço por período e os gráficos."""
    read = _planning_read(session, user=user, scope=scope, kind=kind, period=period, cut=cut)
    bars = _period_bars(
        session,
        scope=scope,
        kind=kind,
        period=period,
        reference_date=reference_date,
        read=read,
    )
    return PlanningSheet(
        empty=read.overview.is_empty,
        figures=_sheet_figures(read, kind=kind, period=period, cut=cut),
        rows=tuple(read.overview.rows),
        bars=bars,
        bars_chart=_bars_chart(kind, bars),
        curve_chart=dict(read.overview.curve.chart),
        deviation_bands=tuple(read.overview.bands),
        is_portfolio=read.overview.is_portfolio,
        week_label=calculations.short_month(calendario.WEEKLY, calendario.iso_week(cut)),
    )


def _sheet_figures(
    read: _PlanningRead, *, kind: str, period: str, cut: date
) -> calculations.PlanningFigures:
    """As figuras da folha 1: no semanal, a posição acumulada da leitura semanal do dono.

    A Curva S física é mensal: no Mensal vale o ponto do mês (o mesmo das telas e da Home); no
    Semanal a posição sai do gráfico do dono — o previsto interpolado dentro do mês até o fim
    da semana e o real medido —, a regra do relatório. O restante (términos, áreas e
    produtividade) vem da leitura comum, e sem leitura do dono valem as figuras do mês.
    """
    figures = _planning_figures(read)
    if kind != calendario.WEEKLY:
        return figures
    periods = read.overview.curve.chart.get("periodos", ())
    if not periods:
        return figures
    bounds = calendario.period_bounds(kind, period)
    before = calendario.add_days(bounds[0], -1) if bounds is not None else cut
    at_cut = calculations.chart_reading(periods, day=cut)
    earlier = calculations.chart_reading(periods, day=before)
    if at_cut.actual is None:
        return figures
    return replace(
        figures,
        predicted=at_cut.predicted,
        actual=at_cut.actual,
        deviation_pp=at_cut.deviation_pp or calculations.ZERO,
        spi=at_cut.spi,
        previous_predicted=earlier.predicted,
        previous_actual=earlier.actual or calculations.ZERO,
        previous_spi=earlier.spi,
    )


def _period_bars(
    session: Session,
    *,
    scope: Scope,
    kind: str,
    period: str,
    reference_date: date,
    read: _PlanningRead,
) -> tuple[calculations.PeriodBar, ...]:
    """As barras do avanço por período, na leitura do dono para o tipo do relatório.

    No Mensal são os meses da série da curva (o previsto e o real de cada mês). No Semanal,
    as semanas do gráfico do dono — o previsto interpolado dentro do mês e o real medido até
    cada fim de semana —, a mesma leitura da posição acumulada da folha.
    """
    periods = calculations.bar_periods(
        kind,
        period,
        reference_date=reference_date,
        project_start=_project_start(session, scope),
    )
    if not periods or read.overview.is_empty:
        return ()
    if kind == calendario.MONTHLY:
        cumulative = tuple(
            (f"{month.year}-{month.month:02d}", point.predicted, point.actual)
            for month, point in zip(
                read.overview.curve.series.months, read.overview.curve.points, strict=True
            )
        )
    else:
        cumulative = tuple(
            (
                f"{item['ano']}-S{item['semana']:02d}",
                _decimal_of(item["valores"].get("linha_base")),
                _decimal_of(item["valores"].get("realizado")),
            )
            for item in read.overview.curve.chart.get("periodos", ())
        )
    return calculations.period_bars(kind, periods, cumulative)


def _decimal_of(value: Any) -> Decimal | None:
    """O número do gráfico do dono como Decimal; nulo continua nulo."""
    return None if value is None else Decimal(str(value))


def _bars_chart(kind: str, bars: Sequence[calculations.PeriodBar]) -> Mapping[str, Any]:
    """O ``data-dados`` do avanço por período (D11): barras de previsto e real em p.p."""
    weekly = kind == calendario.WEEKLY
    periods: list[dict[str, Any]] = []
    for bar in bars:
        start = calendario.week_start(bar.period) if weekly else None
        if weekly and start is None:
            continue
        year, month = (start.year, start.month) if start is not None else _month_of(bar.period)
        period: dict[str, Any] = {
            "ano": year,
            "mes": month,
            "valores": {
                "previsto": None if bar.predicted is None else float(bar.predicted),
                "realizado": None if bar.actual is None else float(bar.actual),
            },
        }
        if start is not None:
            period["semana"] = start.isocalendar()[1]
        periods.append(period)
    return {
        "titulo": "Avanço por semana" if weekly else "Avanço por mês",
        "modo": "periodo",
        "formato": "numero",
        "unidade": " p.p.",
        "casas": 1,
        "series": [
            {"id": "previsto", "rotulo": "Previsto", "papel": "linha-base", "tipo": "valor"},
            {"id": "realizado", "rotulo": "Realizado", "papel": "realizado", "tipo": "valor"},
        ],
        "periodos": periods,
    }


def _month_of(label: str) -> tuple[int, int]:
    """O ano e o mês de um rótulo mensal ``2026-08``."""
    year, month = label.split("-")
    return int(year), int(month)


def _project_relato_sheets(
    session: Session, *, user: User, kind: str, period: str
) -> tuple[ProjectRelatoSheet, ...]:
    """Os relatos da folha 2 do Portfólio: um por projeto, com os pontos de atenção dele."""
    from src.modulos.planejamento import service as planejamento

    reports = {
        report.project_id: report
        for report in planejamento.list_reports(
            session, user=user, scope=Scope(project_id=None, source="url")
        )
        if report.kind == kind and report.period == period
    }
    sheets: list[ProjectRelatoSheet] = []
    for project in configuracoes.list_projects(session):
        report = reports.get(project.id)
        sheets.append(
            ProjectRelatoSheet(
                project_id=project.id,
                project_label=f"{project.code} · {project.name}",
                registered=report is not None,
                url=_project_relato_url(kind, period, project.id),
                updated=_report_updated(report) if report is not None else "",
                points=() if report is None else tuple(report.points),
            )
        )
    return tuple(sheets)


def _report_updated(report: Any) -> str:
    """Quando e por quem o relato foi atualizado, como a folha lê."""
    return f"registrado em {calculations.format_date(report.updated_at)} por {report.updated_by}"


def _portfolio_points(
    sheets: Sequence[ProjectRelatoSheet],
) -> tuple[tuple[str, Any], ...]:
    """Os pontos de atenção dos relatos dos projetos, na ordem das linhas, para a folha 2."""
    points: list[tuple[str, Any]] = []
    for sheet in sheets:
        points.extend((sheet.project_label, point) for point in sheet.points)
    return tuple(points)


def _find_report(
    session: Session, *, user: User, scope: Scope, kind: str, period: str
) -> Any | None:
    """O relato do período do projeto do escopo, pela fachada dona (D9)."""
    from src.modulos.planejamento import service as planejamento

    return planejamento.find_report(session, user=user, scope=scope, kind=kind, period=period)


# ── Coleta dos dados (fachadas donas) ──────────────────────────────────────


def _collect(
    session: Session,
    *,
    user: User,
    scope: Scope,
    module: str,
    kind: str,
    period: str,
    reference_date: date,
) -> _Collected:
    """Coleta as figuras do módulo no corte do período, pelas fachadas donas (D9)."""
    cut = calendario.cut_date(kind, period, reference_date)
    bounds = calendario.period_bounds(kind, period)
    if cut is None or bounds is None:
        raise InvalidDataError({validation.FIELD_PERIOD: validation.CHOOSE_MESSAGE})
    first = bounds[0]
    if module == "planejamento":
        return _collect_planning(session, user=user, scope=scope, kind=kind, period=period, cut=cut)
    if module == "financeiro":
        return _collect_cost(session, scope=scope, kind=kind, period=period)
    if module == "suprimentos":
        return _collect_procurement(
            session, user=user, scope=scope, kind=kind, period=period, cut=cut
        )
    if module == "riscos":
        return _collect_risk(session, user=user, scope=scope, first=first, cut=cut)
    if module == "qualidade":
        return _collect_quality(session, user=user, scope=scope, first=first, cut=cut)
    return _collect_hse(session, user=user, scope=scope, first=first, cut=cut)


def _collect_planning(
    session: Session, *, user: User, scope: Scope, kind: str, period: str, cut: date
) -> _Collected:
    """Os números do planejamento no corte: posição, posição anterior, términos, áreas e produtividade."""
    read = _planning_read(session, user=user, scope=scope, kind=kind, period=period, cut=cut)
    return _Collected(figures=_planning_figures(read), sem_fechamento=False)


@dataclass(frozen=True)
class _PlanningRead:
    """As leituras do planejamento no corte, compartilhadas pela análise e pelas folhas."""

    overview: Any
    earlier: Any
    performance: Any


def _planning_read(
    session: Session, *, user: User, scope: Scope, kind: str, period: str, cut: date
) -> _PlanningRead:
    """Lê os KPIs do planejamento, a posição anterior e a performance no corte (uma vez só)."""
    from src.modulos.planejamento import service as planejamento

    overview = planejamento.planning_kpis_overview(session, scope=scope, reference_date=cut)
    bounds = calendario.period_bounds(kind, period)
    before = calendario.add_days(bounds[0], -1) if bounds is not None else cut
    earlier = planejamento.curva_fisica_overview(
        session, scope=scope, reference_date=before
    ).indicators
    performance = planejamento.performance_overview(
        session, user=user, scope=scope, reference_date=cut
    )
    return _PlanningRead(overview=overview, earlier=earlier, performance=performance)


def _planning_figures(read: _PlanningRead) -> calculations.PlanningFigures:
    """As figuras do planejamento a partir das leituras: a mesma montagem da ISSUE-081."""
    from src.modulos.planejamento import calculations as planning

    overview = read.overview
    indicators = overview.curve.indicators
    earlier = read.earlier
    previous_spi = planning.spi_index(earlier.actual, earlier.predicted) if earlier.actual else None
    return calculations.PlanningFigures(
        predicted=indicators.predicted,
        actual=indicators.actual,
        deviation_pp=indicators.deviation_pp,
        spi=indicators.spi,
        previous_predicted=earlier.predicted,
        previous_actual=earlier.actual,
        previous_spi=previous_spi,
        trend_finish=calculations.trend_finish(
            overview.curve.series.months, overview.curve.series.trend
        ),
        baseline_finish=calculations.finish_month(
            overview.curve.series.months, overview.curve.series.baseline
        ),
        areas=tuple(
            calculations.AreaFigure(name=row.name, deviation_pp=row.deviation_pp)
            for row in overview.rows
        ),
        productivity=_productivity_figure(read.performance),
    )


def _productivity_figure(overview: Any) -> calculations.ProductivityFigure:
    """Os indicadores de produtividade do bloco geral, com as metas vigentes dos parâmetros."""
    general = overview.general
    parameters = overview.parameters
    return calculations.ProductivityFigure(
        spi=general.quantities.spi,
        pf_window=general.quantities.pf_window,
        adherence=general.quantities.window_adherence,
        working_pct=general.sample.working_pct,
        utilization=general.capacity.utilization,
        meta_pf=parameters.pf_bands[0],
        meta_adherence=parameters.adherence_bands[1],
        meta_working=parameters.working_pct,
        meta_utilization=parameters.utilization_pct,
        weeks=parameters.window_weeks,
        stoppage_hours=general.stoppages.crew_hours,
        stoppage_share=general.stoppage_share,
        alert_companies=tuple(block.company_name for block in overview.companies if block.alerts),
        bands=general.bands,
    )


def _collect_cost(session: Session, *, scope: Scope, kind: str, period: str) -> _Collected:
    """Os números do financeiro no mês de competência: valor agregado, projeção e pacotes."""
    from src.modulos.financeiro import service as financeiro

    month = calculations.competence_month(kind, period)
    overview = financeiro.cost_kpis_overview(session, scope=scope, reference_date=month)
    if overview.actual is None:
        return _Collected(figures=calculations.CostFigures(closed=False), sem_fechamento=True)
    mapa = financeiro.mapa_controle(session, scope=scope, reference_date=month)
    packages = tuple(
        calculations.CostPackageFigure(
            code=row.code,
            description=row.description,
            deviation_cents=row.deviation_cents,
            deviation_percent=row.deviation_percent,
        )
        for row in mapa.rows
        if row.level == 1 and row.deviation_cents > 0
    )
    actual = overview.actual
    figures = calculations.CostFigures(
        closed=True,
        cpi=actual.cpi,
        spi=actual.spi,
        cv_cents=actual.cv_cents,
        sv_cents=actual.sv_cents,
        ev_cents=actual.ev_cents,
        ac_cents=actual.ac_cents,
        previous_cpi=overview.previous.cpi if overview.previous is not None else None,
        budget_cents=overview.budget_cents,
        projection_cents=overview.projection_cents,
        vac_cents=overview.vac_cents,
        deviation_percent=mapa.total.deviation_percent,
        contingency_pct=overview.contingency_pct,
        packages=packages,
    )
    return _Collected(figures=figures, sem_fechamento=False)


def _collect_procurement(
    session: Session, *, user: User, scope: Scope, kind: str, period: str, cut: date
) -> _Collected:
    """Os números de suprimentos no corte: painel, pedidos críticos e marcos atrasados do período."""
    from src.modulos.suprimentos import calculations as procurement_calculations
    from src.modulos.suprimentos import service as suprimentos
    from src.modulos.suprimentos import validation as procurement_validation

    panel = suprimentos.list_panel(session, user=user, scope=scope, reference_date=cut)
    summary = panel.summary
    listing = suprimentos.list_orders(
        session,
        user=user,
        scope=scope,
        filters=procurement_validation.OrderFilters(
            situation=procurement_validation.ORDER_SITUATION_ALL
        ),
        reference_date=cut,
    )
    bounds = calendario.period_bounds(kind, period)
    first = bounds[0] if bounds is not None else cut
    critical = tuple(
        calculations.CriticalOrderFigure(
            number=line.number, description=line.description, slack_days=line.slack_days
        )
        for line in listing.lines
        if line.critical
    )
    delivered = tuple(
        line for line in listing.lines if line.delivery is not None and line.delivery <= cut
    )
    on_time = sum(
        1
        for line in delivered
        if line.contractual_delay_days is not None and line.contractual_delay_days <= 0
    )
    figures = calculations.ProcurementFigures(
        adherence_pct=summary.adherence_pct,
        adjudicated=summary.adjudicated_until_reference,
        planned=summary.planned_until_reference,
        saving_pct=summary.saving_pct,
        otd_pct=procurement_calculations.on_time_delivery(
            (line.delivery, line.contractual_date) for line in delivered
        ),
        on_time=on_time,
        deliveries=len(delivered),
        warning=summary.orders.warning,
        critical_orders=critical,
        late_milestones=_late_milestones(listing.lines, first=first, cut=cut),
    )
    return _Collected(figures=figures, sem_fechamento=False)


def _late_milestones(
    lines: Sequence[Any], *, first: date, cut: date
) -> tuple[calculations.LateMilestoneFigure, ...]:
    """Os marcos de pedido realizados com atraso dentro do período: só pedidos, como o protótipo."""
    found: list[calculations.LateMilestoneFigure] = []
    for line in lines:
        for row in line.milestones:
            if row.real is None or not first <= row.real <= cut:
                continue
            if row.deviation_days is None or row.deviation_days <= 0:
                continue
            found.append(
                calculations.LateMilestoneFigure(
                    code=line.number, milestone=row.name, days=row.deviation_days
                )
            )
    return tuple(found)


def _collect_risk(
    session: Session, *, user: User, scope: Scope, first: date, cut: date
) -> _Collected:
    """Os números de riscos no corte: o painel e as contagens de identificados e encerrados."""
    from src.modulos.riscos import panel_service
    from src.modulos.riscos import service as riscos
    from src.modulos.riscos import validation as risk_validation

    panel = panel_service.risk_panel(session, user=user, scope=scope, reference_date=cut)
    summary = panel.summary
    listing = riscos.list_risks(
        session,
        user=user,
        scope=scope,
        filters=risk_validation.RiskFilters(
            situation=risk_validation.SITUATION_ALL, include_closed=True
        ),
        reference_date=cut,
    )
    figures = calculations.RiskFigures(
        active=summary.active,
        top_band=summary.top.band.name,
        top_total=summary.top.total,
        exposure_cents=summary.exposure_cents,
        overdue_reviews=len(summary.overdue),
        identified=sum(1 for line in listing.lines if first <= line.identified_on <= cut),
        closed=sum(
            1
            for line in listing.lines
            if line.closing_date is not None and first <= line.closing_date <= cut
        ),
        reduction_avg_pct=panel.reduction_avg_pct,
    )
    return _Collected(figures=figures, sem_fechamento=False)


def _collect_quality(
    session: Session, *, user: User, scope: Scope, first: date, cut: date
) -> _Collected:
    """Os números da qualidade no corte: RNC, inspeções do período, auditorias e custo."""
    from src.modulos.qualidade import calculations as quality_calculations
    from src.modulos.qualidade import service as qualidade
    from src.modulos.qualidade import validation as quality_validation

    parameters = qualidade.parameters(session, reference_date=cut)
    rncs = qualidade.list_rncs(
        session,
        user=user,
        scope=scope,
        filters=quality_validation.RncFilters(situation=quality_validation.SITUATION_ALL),
        reference_date=cut,
    ).lines
    inspections = qualidade.list_inspections(
        session, user=user, scope=scope, filters=quality_validation.InspectionFilters()
    ).lines
    audits = qualidade.list_audits(
        session,
        user=user,
        scope=scope,
        filters=quality_validation.AuditFilters(),
        reference_date=cut,
    ).lines
    in_period = [line for line in inspections if first <= line.inspection_date <= cut]
    performed = [
        line
        for line in audits
        if line.situation == quality_calculations.AUDIT_DONE
        and first <= (line.performed_on or line.audit_date) <= cut
    ]
    figures = calculations.QualityFigures(
        open_in_period=sum(
            1
            for line in rncs
            if first <= line.rnc_date <= cut
            and line.situation != quality_calculations.SITUATION_CANCELLED
        ),
        closed_in_period=sum(
            1
            for line in rncs
            if line.situation == quality_calculations.SITUATION_CLOSED
            and line.closing_date is not None
            and first <= line.closing_date <= cut
        ),
        open_at_cut=sum(
            1
            for line in rncs
            if line.rnc_date <= cut
            and (line.closing_date is None or line.closing_date > cut)
            and line.situation != quality_calculations.SITUATION_CANCELLED
        ),
        approval_pct=quality_calculations.inspection_approval_rate(
            line.result for line in in_period
        ),
        approval_meta=_meta(parameters, "metaAprovacaoInspecaoPct"),
        approval_rejected=sum(
            1 for line in in_period if line.result == quality_calculations.RESULT_REJECTED
        ),
        approval_total=len(in_period),
        conformity_pct=quality_calculations.audit_conformity_rate(
            sum(line.items_conforming or 0 for line in performed),
            sum(line.items_verified or 0 for line in performed),
        ),
        conformity_meta=_meta(parameters, "metaConformidadeAuditoriaPct"),
        non_quality_cost_cents=sum(
            line.cost_cents
            for line in rncs
            if line.rnc_date <= cut and line.situation != quality_calculations.SITUATION_CANCELLED
        ),
        overdue=_overdue_items(line for line in rncs if line.overdue),
        late_audits=_overdue_items(line for line in audits if line.overdue),
    )
    return _Collected(figures=figures, sem_fechamento=False)


def _meta(parameters: Mapping[str, Any], key: str) -> Decimal | None:
    """A meta vigente do grupo Qualidade, ou ``None`` quando a chave não veio."""
    value = parameters.get(key)
    return None if value is None else Decimal(str(value))


def _overdue_items(lines: Any) -> tuple[calculations.OverdueItem, ...]:
    """Os itens vencidos na data de referência, o mais atrasado primeiro."""
    items = [calculations.OverdueItem(code=line.code, days=line.days_overdue) for line in lines]
    items.sort(key=lambda item: (-item.days, item.code))
    return tuple(items)


def _collect_hse(
    session: Session, *, user: User, scope: Scope, first: date, cut: date
) -> _Collected:
    """Os números do HSE no corte: as taxas do mês, o acumulado, os dias e as ocorrências."""
    from src.modulos.hse import calculations as hse_calculations
    from src.modulos.hse import painel_service
    from src.modulos.hse import service as hse
    from src.modulos.hse import validation as hse_validation

    panel = painel_service.panel(
        session,
        user=user,
        scope=scope,
        reference_date=cut,
        month=date(cut.year, cut.month, 1),
        pyramid_kind=None,
    )
    month = panel.month_indicators
    accumulated = panel.accumulated_indicators
    screen = hse.occurrences_screen(
        session,
        scope=scope,
        filters=hse_validation.OccurrenceFilters(),
        reference_date=cut,
    )
    days = [
        calendario.in_product_timezone(row.happened_at).date()
        for row in screen.rows
        if not row.environmental
    ]
    lti_days = [
        calendario.in_product_timezone(row.happened_at).date()
        for row in screen.rows
        if row.kind in hse_calculations.LTI_KINDS
    ]
    until_cut = [day for day in lti_days if day <= cut]
    if until_cut:
        days_without_leave = max(0, (cut - max(until_cut)).days)
    else:
        days_without_leave = month.days_without_leave if month is not None else None
    figures = calculations.HseFigures(
        tf=month.tf if month is not None else None,
        trif=month.trif if month is not None else None,
        accumulated_trif=accumulated.trif if accumulated is not None else None,
        days_without_leave=days_without_leave,
        hipo=month.hipo if month is not None else 0,
        hours=month.hours if month is not None else None,
        occurrences=sum(1 for day in days if first <= day <= cut),
    )
    return _Collected(figures=figures, sem_fechamento=False)


def _detected(module: str, figures: FigureSet) -> tuple[calculations.Deviation, ...]:
    """Os desvios negativos do módulo a partir das figuras coletadas.

    Riscos e HSE não têm detecção — neles só o texto é exigido, como no protótipo.
    """
    if module == "planejamento" and isinstance(figures, calculations.PlanningFigures):
        return calculations.planning_deviations(figures)
    if module == "financeiro" and isinstance(figures, calculations.CostFigures):
        return calculations.cost_deviations(figures)
    if module == "suprimentos" and isinstance(figures, calculations.ProcurementFigures):
        return calculations.procurement_deviations(figures)
    if module == "qualidade" and isinstance(figures, calculations.QualityFigures):
        return calculations.quality_deviations(figures)
    return ()


# ── Helpers de leitura ─────────────────────────────────────────────────────


def _project(session: Session, project_id: int) -> configuracoes.ProjectSummary:
    for project in configuracoes.list_projects(session):
        if project.id == project_id:
            return project
    raise InvalidDataError(UNKNOWN_PROJECT_MESSAGE)


def _project_label(project: configuracoes.ProjectSummary) -> str:
    return f"{project.code} · {project.name}"


def _project_start(session: Session, scope: Scope) -> date | None:
    """O início do escopo: o do projeto, ou o início mais antigo da carteira no Portfólio.

    A faixa de períodos do Portfólio cobre a carteira inteira, como o protótipo; sem projeto com
    início cadastrado não há limite inferior.
    """
    if scope.project_id is not None:
        return _project(session, scope.project_id).start_date
    starts = [
        project.start_date for project in configuracoes.list_projects(session) if project.start_date
    ]
    return min(starts) if starts else None


def _scope_label(session: Session, scope: Scope) -> str:
    """O rótulo do escopo: ``COD · Nome`` no projeto; ``Portfólio · N projetos`` no Portfólio."""
    if scope.project_id is None:
        count = len(configuracoes.list_projects(session))
        return f"Portfólio · {count} {'projeto' if count == 1 else 'projetos'}"
    return _project_label(_project(session, scope.project_id))


def _record_of(
    session: Session, *, project_id: int | None, module: str, kind: str, period: str
) -> Analysis | None:
    statement = (
        select(Analysis)
        .options(selectinload(Analysis.deviations))
        .where(
            Analysis.project_id == project_id,
            Analysis.module == module,
            Analysis.kind == kind,
            Analysis.period == period,
        )
    )
    return session.scalars(statement).first()


def _find(session: Session, scope: Scope, analysis_id: int) -> Analysis:
    """A análise com o id dentro do escopo, ou 422: um id de outro projeto não é encontrado."""
    analysis = session.get(Analysis, analysis_id)
    if analysis is None or analysis.project_id != scope.project_id:
        raise InvalidDataError(NOT_FOUND_MESSAGE)
    return analysis


def _previous_of(
    session: Session, *, project_id: int | None, module: str, kind: str, period: str
) -> PreviousAnalysis | None:
    """A análise do período imediatamente anterior do mesmo tipo, só quando há registro."""
    earlier = calculations.previous_period(kind, period)
    if earlier is None:
        return None
    record = _record_of(session, project_id=project_id, module=module, kind=kind, period=earlier)
    if record is None:
        return None
    return PreviousAnalysis(
        period=earlier, label=calculations.period_name(kind, earlier), text=record.text
    )


def _default_period(options: Sequence[Any], *, kind: str, reference_date: date) -> str:
    """O período selecionado do passo 1: o anterior ao corrente, ou o mais recente."""
    if not options:
        return ""
    earlier = calculations.previous_period(kind, calendario.period_of(kind, reference_date))
    if earlier is not None and earlier in {option.period for option in options}:
        return earlier
    return str(options[0].period)


def _check_module(module: str) -> None:
    errors = validation.validate_module(module, ANALYSIS_MODULES)
    if errors:
        raise InvalidDataError(errors)


def _check_kind(kind: str) -> None:
    errors = validation.validate_kind(kind)
    if errors:
        raise InvalidDataError(errors)


def _check_period(
    kind: str, period: str, *, project_start: date | None, reference_date: date
) -> None:
    problem = calculations.period_error(
        kind, period, project_start=project_start, reference_date=reference_date
    )
    errors = validation.validate_period(kind, period, problem=problem)
    if errors:
        raise InvalidDataError(errors)
