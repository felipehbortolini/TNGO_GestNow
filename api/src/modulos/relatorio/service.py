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
areas. The links the modal offers point at the screens that register each piece. The
ISSUE-084 adds the Financeiro sheet — the cost KPIs in the competence month, the owner's
financial curve with the trend of that very month and the EAC by package — and the
Suprimentos sheet — the panel KPIs at the cut, the contracting curve, the milestones done in
the period and the adjudications and deliveries of the horizon. The ISSUE-085 adds the Riscos
sheet — the panel position at the cut, the residual matrix with the threats and opportunities
per cell, the monthly exposure of the threats, the analysis and the top risks —, the Qualidade
sheet — the RNC position at the cut and the pauta at the reference date, the period's
inspections and audits against the owner's targets, the six-month series and the rejected
inspections —, the HSE sheet — the month's and the accumulated indicators, the security
pyramid, the evolution of TF and TRIF and the proactive indicators — and, in the Portfólio,
the Carteira de projetos as the first folha: the weighted physical S curve, the ponderation
criteria and the same reading of the Início's carteira, at the reference date.
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

from src.core import audit, calendario, rbac, translations, versioning
from src.core.audit import TrailLine
from src.core.errors import InvalidDataError
from src.core.rbac import Permission, User
from src.core.scope import PORTFOLIO_PARAMETER, Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.inicio import calculations as inicio_calculations
from src.modulos.relatorio import calculations, validation
from src.modulos.relatorio.models import Analysis, AnalysisDeviation

MODULE = "relatorio"


def _label(text: str, idioma: str) -> str:
    """O texto de interface do relatório no idioma do request (D13)."""
    return translations.translate(MODULE, text, idioma)


def _chart_data(data: Mapping[str, Any], idioma: str) -> dict[str, Any]:
    """O JSON do gráfico no idioma: textos pelo catálogo e os rótulos do motor (D13)."""
    translated = _translated_strings(data, idioma)
    especificos = data.get("rotulos")
    if not isinstance(especificos, Mapping):
        especificos = {}
    translated["rotulos"] = translations.rotulos_de_grafico(idioma, dict(especificos))
    return translated


def _translated_strings(data: Mapping[str, Any], idioma: str) -> dict[str, Any]:
    """Os textos de dentro do JSON (títulos, séries, eixos) no idioma; a forma fica igual."""
    translated: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            translated[key] = _label(value, idioma)
        elif isinstance(value, Mapping):
            translated[key] = _translated_strings(value, idioma)
        elif isinstance(value, list):
            translated[key] = [
                _translated_strings(item, idioma)
                if isinstance(item, Mapping)
                else _label(item, idioma)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            translated[key] = value
    return translated


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

# As seções que o relatório implementa, na ordem do modal. A Carteira de projetos não é uma
# seção escolhível: no Portfólio ela entra sozinha, como a primeira folha (o protótipo).
REPORT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("planejamento", "Planejamento (2 páginas)"),
    ("financeiro", "Financeiro (1 página)"),
    ("suprimentos", "Suprimentos (1 página)"),
    ("riscos", "Riscos (1 página)"),
    ("qualidade", "Qualidade (1 página)"),
    ("hse", "HSE (1 página)"),
)

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
    idioma: str = "pt",
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
        idioma=idioma,
    )
    return AnalysisPeriodsView(
        module=module,
        module_label=_label(ANALYSIS_MODULES[module], idioma),
        kind=kind,
        project_label=_scope_label(session, scope, idioma),
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
    idioma: str = "pt",
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
        idioma=idioma,
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
    idioma: str = "pt",
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
        project_label=_scope_label(session, scope, idioma),
        collected=collected,
        record=_record_of(
            session, project_id=scope.project_id, module=module, kind=kind, period=period
        ),
        previous=_previous_of(
            session, project_id=scope.project_id, module=module, kind=kind, period=period
        ),
        reference_date=reference_date,
        idioma=idioma,
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
    idioma: str = "pt",
) -> AnalysisView:
    """Monta a leitura do passo 2 a partir das figuras, do registro e do anterior."""
    deviations = _detected(module, collected.figures)
    comments = {row.key: row.comment for row in record.deviations} if record is not None else {}
    views = tuple(
        AnalysisDeviationView(
            key=deviation.key,
            indicator=_label(deviation.indicator, idioma),
            description=calculations.deviation_description(deviation),
            comment=comments.get(deviation.key, ""),
        )
        for deviation in deviations
    )
    required = DEVIATION_REQUIRED[module]
    summary = tuple(
        replace(item, label=_label(item.label, idioma))
        for item in calculations.analysis_summary(module, collected.figures)
    )
    return AnalysisView(
        module=module,
        module_label=_label(ANALYSIS_MODULES[module], idioma),
        kind=kind,
        period=period,
        period_label=calculations.period_name(kind, period, idioma),
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
        summary=summary,
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
    idioma: str = "pt",
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
        project_label=_scope_label(session, scope, idioma),
        collected=collected,
        record=analysis,
        previous=_previous_of(
            session, project_id=project_id, module=module, kind=kind, period=period
        ),
        reference_date=reference_date,
        idioma=idioma,
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
    idioma: str = "pt",
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
        idioma=idioma,
    )
    default = _default_period(options, kind=chosen_kind, reference_date=reference_date)
    chosen_period = period if period in {option.period for option in options} else default
    return ReportStatusView(
        scope=scope.parameter,
        scope_label=_scope_label(session, scope, idioma),
        kind=chosen_kind,
        period=chosen_period,
        period_label=calculations.period_name(chosen_kind, chosen_period, idioma),
        in_progress=calculations.is_partial_period(chosen_kind, chosen_period, reference_date),
        project_options=_scope_options(session, scope, idioma),
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
                session,
                user=user,
                scope=scope,
                kind=chosen_kind,
                period=chosen_period,
                idioma=idioma,
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
                idioma=idioma,
            )
            for module in ANALYSIS_MODULES
        ),
        sections=_section_options(sections, idioma),
    )


def _scope_options(
    session: Session, scope: Scope, idioma: str = "pt"
) -> tuple[ReportScopeOption, ...]:
    """As opções do "Relatório de": o Portfólio e os projetos do cadastro."""
    options = [
        ReportScopeOption(
            value=PORTFOLIO_PARAMETER,
            label=_label("Portfólio (todos os projetos)", idioma),
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


def _section_options(
    sections: Sequence[str], idioma: str = "pt"
) -> tuple[ReportSectionOption, ...]:
    """As seções implementadas; o que o formulário não mandou entra marcado."""
    requested = {key for key in sections if key}
    return tuple(
        ReportSectionOption(
            key=key, label=_label(label, idioma), selected=not requested or key in requested
        )
        for key, label in REPORT_SECTIONS
    )


def _relato_status(
    session: Session, *, user: User, scope: Scope, kind: str, period: str, idioma: str = "pt"
) -> ReportRelatoStatus:
    """A situação do relato do projeto do escopo: registrado ou pendente, com o endereço."""
    report = _find_report(session, user=user, scope=scope, kind=kind, period=period)
    return ReportRelatoStatus(
        registered=report is not None,
        url=_relato_url(kind, period),
        project_label=_scope_label(session, scope, idioma),
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
    idioma: str = "pt",
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
        label=_label(ANALYSIS_MODULES[module], idioma),
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
class CostPackageRow:
    """Uma linha da EAC por pacote na folha Financeiro, com a faixa do desvio do dono."""

    code: str
    description: str
    project_code: str
    current_cents: int
    committed_cents: int
    actual_cents: int
    projection_cents: int
    deviation_cents: int
    deviation_percent: Decimal | None
    band_tone: str
    band_label: str


@dataclass(frozen=True)
class CostValueMonth:
    """Um mês do valor agregado da folha Financeiro: o mês e os valores que a tabela mostra."""

    month: date
    pv_cents: int
    ev_cents: int
    ac_cents: int
    cpi: Decimal | None
    spi: Decimal | None


@dataclass(frozen=True)
class FinanceiroSheet:
    """A folha Financeiro: os KPIs de custo, a curva com a tendência, o valor agregado e a EAC.

    O mês é o de competência (no semanal, o último fechado até o fim do período) e a curva é a do
    dono lida nele: a tendência parte do realizado do próprio mês, sem dado posterior. ``empty``
    é o aviso do protótipo — sem fechamento até o fim do período a folha mostra só a análise.
    """

    analysis: AnalysisView
    analysis_url: str
    empty: bool
    month: date
    month_current: bool
    is_portfolio: bool
    budget_cents: int = 0
    actual_cents: int = 0
    actual_month_cents: int = 0
    planned_month_cents: int = 0
    ev_cents: int = 0
    pv_cents: int = 0
    cpi: Decimal | None = None
    spi: Decimal | None = None
    previous_cpi: Decimal | None = None
    projection_cents: int | None = None
    vac_cents: int | None = None
    band_tone: str = "neutro"
    band_label: str = ""
    contingency_pct: Decimal | None = None
    contingency_consumed_cents: int = 0
    contingency_total_cents: int = 0
    eac_trend_cents: int | None = None
    curve_chart: Mapping[str, Any] = field(default_factory=dict)
    history: tuple[CostValueMonth, ...] = ()
    packages: tuple[CostPackageRow, ...] = ()
    total: CostPackageRow | None = None


@dataclass(frozen=True)
class ProcurementCriticalRow:
    """Um pedido crítico da folha Suprimentos: o número, o item, o ROS, a previsão e a folga."""

    number: str
    description: str
    project_code: str
    ros: date | None
    forecast: date
    slack_days: int | None
    lli: bool = False


@dataclass(frozen=True)
class ProcurementEventRow:
    """Um evento de suprimentos na folha: a data, o tipo, o pedido ou pacote e o desvio."""

    date: date
    kind: str
    code: str
    description: str
    project_code: str
    deviation_days: int | None


@dataclass(frozen=True)
class ProcurementSheet:
    """A folha Suprimentos: os KPIs do painel, a curva de contratação, os críticos e o horizonte.

    Os eventos são os marcos de pedido realizados dentro do período e os previstos são as
    adjudicações e entregas do horizonte (4 semanas seguintes no semanal, o mês seguinte no
    mensal), ambos com o desvio contra o plano.
    """

    analysis: AnalysisView
    analysis_url: str
    is_portfolio: bool
    adherence_pct: Decimal | None
    adherence_target: int
    adjudicated: int
    planned: int
    packages_total: int
    adjudicated_cents: int
    saving_cents: int
    saving_pct: Decimal | None
    otd_pct: Decimal | None
    otd_target: int
    delivered: int
    delivered_on_time: int
    critical: int
    warning: int
    emitted: int
    emitted_planned: int
    criticals: tuple[ProcurementCriticalRow, ...]
    events: tuple[ProcurementEventRow, ...]
    forecasts: tuple[ProcurementEventRow, ...]
    horizon_start: date
    horizon_end: date
    weekly: bool
    curve_chart: Mapping[str, Any]


# ── Relatório gerencial: a folha Riscos (ISSUE-085) ────────────────────────

# Quantos riscos principais a folha lista: a tabela do protótipo mostra cinco.
TOP_RISKS = 5


@dataclass(frozen=True)
class RiskBandView:
    """Uma faixa de severidade na folha: o nome, a contagem, a natureza e a meta."""

    name: str
    total: int
    threats: int
    opportunities: int
    goal: int


@dataclass(frozen=True)
class RiskMatrixCellView:
    """Uma célula da matriz residual: a posição, o tom da faixa e as contagens de A e O."""

    probability: int
    impact: int
    tone: str
    threats: int
    opportunities: int

    @property
    def text(self) -> str:
        """O texto da célula: ``2A``, ``1O``, ``1A · 2O`` ou vazio."""
        return calculations.matrix_cell_text(self.threats, self.opportunities)


@dataclass(frozen=True)
class RiskTopRow:
    """Um risco principal: o número, o título, o residual, a estratégia e a revisão."""

    number: str
    title: str
    nature: str
    score: int
    severity: str
    tone: str
    strategy: str
    owner_name: str
    next_review: date | None
    review_overdue: bool


@dataclass(frozen=True)
class RiskMonthPoint:
    """Um mês da exposição: o mês, o score residual somado das ameaças e se é o corrente."""

    month: str
    score: int
    current: bool


@dataclass(frozen=True)
class RiskSheet:
    """A folha Riscos: o painel na data de referência, a matriz, a exposição e os principais.

    Os KPIs, a matriz e os principais são a posição na data de referência; identificados e
    encerrados saem do histórico, dentro do período; a exposição mensal vem reconstruída do
    painel do dono. ``exposure_limit_cents`` é o saldo da reserva de contingência (o limite do
    protótipo), lido do mapa de controle do Financeiro na mesma data.
    """

    analysis: AnalysisView
    analysis_url: str
    is_portfolio: bool
    active: int
    registered: int
    threats: int
    opportunities: int
    top: RiskBandView
    second: RiskBandView | None
    exposure_cents: int
    exposure_limit_cents: int | None
    overdue_reviews: int
    agenda: int
    identified: int
    closed: int
    matrix: tuple[RiskMatrixCellView, ...]
    evolution: tuple[RiskMonthPoint, ...]
    evolution_chart: Mapping[str, Any]
    principais: tuple[RiskTopRow, ...]


# ── Relatório gerencial: a folha Qualidade (ISSUE-085) ─────────────────────

# Quantas inspeções reprovadas e quantas RNC da pauta a folha lista; o protótipo mostra cinco.
TOP_REJECTED = 5
TOP_AGENDA = 5


@dataclass(frozen=True)
class QualityRejectedRow:
    """Uma inspeção reprovada no período: a data, o ponto com o ITP, a empresa e a RNC."""

    date: date
    point: str
    itp_code: str
    company_name: str
    rnc_code: str


@dataclass(frozen=True)
class QualityAgendaRow:
    """Uma RNC da pauta de tratamento: a identificação, a severidade e os motivos do dono."""

    code: str
    description: str
    severity: str
    situation: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class QualityDisciplineRow:
    """Uma disciplina do Pareto de RNC: o total e a fatia do total."""

    name: str
    total: int
    pct: Decimal


@dataclass(frozen=True)
class QualitySeriesPoint:
    """Um mês da série de RNC: as abertas, as encerradas e as inspeções do mês."""

    month: str
    opened: int
    closed: int
    open: int
    inspections: int
    approval_pct: Decimal | None


@dataclass(frozen=True)
class QualitySheet:
    """A folha Qualidade: a posição no corte, o período, as metas, a série e a pauta.

    A posição (em aberto e críticas) e o custo acumulado são do corte; as abertas, encerradas,
    inspeções e auditorias realizadas são do período; a pauta e as auditorias atrasadas são a
    posição na data de referência, como o rodapé da folha informa. A série de RNC termina no mês
    do corte e a disciplina com mais RNC sai do painel do dono.
    """

    analysis: AnalysisView
    analysis_url: str
    is_portfolio: bool
    open_at_cut: int
    critical_at_cut: int
    overdue_at_reference: int
    opened_period: int
    closed_period: int
    approval_pct: Decimal | None
    approval_meta: Decimal | None
    rejected: tuple[QualityRejectedRow, ...]
    inspections: int
    conformity_pct: Decimal | None
    conformity_meta: Decimal | None
    audits_period: int
    late_audits: int
    cost_accumulated_cents: int
    cost_period_cents: int
    discipline: tuple[QualityDisciplineRow, ...]
    discipline_total: int
    series: tuple[QualitySeriesPoint, ...]
    series_chart: Mapping[str, Any]
    agenda: tuple[QualityAgendaRow, ...]


# ── Relatório gerencial: a folha HSE (ISSUE-085) ───────────────────────────

# Quantos meses a evolução de TF e TRIF da folha HSE mostra, terminando no mês do corte.
HSE_EVOLUTION_MONTHS = 6


@dataclass(frozen=True)
class HseSheet:
    """A folha HSE: o mês e o acumulado do dono, a pirâmide, a evolução e os proativos.

    As taxas são as do painel do dono no mês do corte (no semanal, o mês parcial com as taxas
    do mês inteiro até ele): ``month_indicators`` é o mês e ``accumulated_indicators`` vai do
    primeiro mês com HHT até ele. No semanal a folha troca o KPI do HHT pelo das ocorrências da
    semana, com os níveis da pirâmide do mês como referência; no mensal o HHT previsto vem do
    histograma de mão de obra do próprio dono. ``empty`` é o escopo ainda sem HHT: só a análise.
    """

    analysis: AnalysisView
    analysis_url: str
    is_portfolio: bool
    weekly: bool
    empty: bool
    month: date = date(1970, 1, 1)
    partial_month: bool = False
    base: int = 0
    base_name: str = ""
    reference_name: str = ""
    reference_ratio: Decimal | None = None
    observations_target: int = 0
    month_indicators: Any = None
    accumulated: Any = None
    days_expected: int | None = None
    days_since: date | None = None
    occurrences: int = 0
    occurrence_levels: tuple[int, ...] = ()
    hipo_period: int = 0
    month_occurrences: int = 0
    hours_expected: int | None = None
    first_month: date = date(1970, 1, 1)
    pyramid_chart: Mapping[str, Any] = field(default_factory=dict)
    evolution_chart: Mapping[str, Any] = field(default_factory=dict)


# ── Relatório gerencial: a folha Carteira de projetos (ISSUE-085) ──────────


@dataclass(frozen=True)
class CarteiraProjectRow:
    """Um projeto da carteira: o peso e os mesmos indicadores da tela Início, no mesmo corte."""

    project_id: int
    code: str
    name: str
    weight: Decimal
    budget_cents: int
    predicted: Decimal
    actual: Decimal
    spi: Decimal | None
    cpi: Decimal | None
    projection_cents: int | None
    vac_cents: int | None
    baseline_finish: date | None
    trend_finish: date | None
    critical_risks: int
    critical_orders: int
    overdue_actions: int
    health: str | None

    @property
    def health_label(self) -> str:
        """``Em dia``, ``Atenção`` ou ``Crítico``: o rótulo da situação (vazio sem ela)."""
        return inicio_calculations.health_label(self.health)


@dataclass(frozen=True)
class CarteiraCriterionRow:
    """Um critério da ponderação vigente: o nome, o peso e a fonte (orçamento ou nota)."""

    id: str
    name: str
    source: str
    weight: Decimal


@dataclass(frozen=True)
class CarteiraSheet:
    """A folha Carteira de projetos, só no Portfólio: a posição na data de referência.

    Como o protótipo, a folha é a primeira do relatório e lê o mesmo que o Início lê: o peso de
    ``financeiro.portfolio_weights``; por projeto, o prazo (``planning_kpis_overview``) e o
    custo (``cost_kpis_overview``) com a tendência da própria curva, os riscos no topo
    (``risk_panel``), os pedidos críticos (``list_panel``) e as ações atrasadas
    (``count_by_status``); e a Curva S física ponderada da carteira, com os critérios da
    ponderação. Os totais reusam as leituras consolidadas do Portfólio.
    """

    reference_date: date
    project_count: int
    budget_cents: int
    budget_baseline_cents: int | None
    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    spi_tone: str
    cpi: Decimal | None
    cpi_tone: str
    projection_cents: int | None
    vac_cents: int | None
    baseline_finish: date | None
    trend_finish: date | None
    critical_risks: int
    critical_orders: int
    overdue_actions: int
    projects: tuple[CarteiraProjectRow, ...]
    criteria: tuple[CarteiraCriterionRow, ...]
    curve_chart: Mapping[str, Any]


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
    financeiro: FinanceiroSheet | None
    suprimentos: ProcurementSheet | None
    riscos: RiskSheet | None
    qualidade: QualitySheet | None
    hse: HseSheet | None
    carteira: CarteiraSheet | None
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
    idioma: str = "pt",
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
    financeiro = None
    suprimentos = None
    riscos = None
    qualidade = None
    hse = None
    carteira = None
    analysis = None
    analysis_url = ""
    relato = None
    relato_url = ""
    project_relatos: tuple[ProjectRelatoSheet, ...] = ()
    relato_points: tuple[tuple[str, Any], ...] = ()
    if scope.is_portfolio:
        carteira = _carteira_sheet(session, user=user, reference_date=reference_date)
    if "planejamento" in chosen:
        planning = _planning_sheet(
            session,
            user=user,
            scope=scope,
            kind=kind,
            period=period,
            reference_date=reference_date,
            cut=cut,
            idioma=idioma,
        )
        analysis = _analysis_reading(
            session,
            user=user,
            scope=scope,
            module="planejamento",
            kind=kind,
            period=period,
            reference_date=reference_date,
            idioma=idioma,
        )
        analysis_url = _analysis_url("planejamento", kind, period, scope)
        if scope.is_portfolio:
            project_relatos = _project_relato_sheets(session, user=user, kind=kind, period=period)
            relato_points = _portfolio_points(project_relatos)
        else:
            relato = _find_report(session, user=user, scope=scope, kind=kind, period=period)
            relato_url = _relato_url(kind, period)
    if "financeiro" in chosen:
        financeiro = _financeiro_sheet(
            session,
            user=user,
            scope=scope,
            kind=kind,
            period=period,
            reference_date=reference_date,
            idioma=idioma,
        )
    if "suprimentos" in chosen:
        suprimentos = _procurement_sheet(
            session,
            user=user,
            scope=scope,
            kind=kind,
            period=period,
            reference_date=reference_date,
            cut=cut,
            idioma=idioma,
        )
    if "riscos" in chosen:
        riscos = _risk_sheet(
            session,
            user=user,
            scope=scope,
            kind=kind,
            period=period,
            reference_date=reference_date,
            cut=cut,
            idioma=idioma,
        )
    if "qualidade" in chosen:
        qualidade = _quality_sheet(
            session,
            user=user,
            scope=scope,
            kind=kind,
            period=period,
            reference_date=reference_date,
            cut=cut,
            idioma=idioma,
        )
    if "hse" in chosen:
        hse = _hse_sheet(
            session,
            user=user,
            scope=scope,
            kind=kind,
            period=period,
            reference_date=reference_date,
            cut=cut,
            idioma=idioma,
        )
    return ReportSheets(
        scope=scope.parameter,
        scope_label=_scope_label(session, scope, idioma),
        kind=kind,
        period=period,
        period_label=calculations.period_name(kind, period, idioma),
        short_period=calculations.short_month(kind, period, idioma),
        in_progress=calculations.is_partial_period(kind, period, reference_date),
        cut=cut,
        reference_date=reference_date,
        emitted_by=user.name,
        sections=chosen,
        is_portfolio=scope.is_portfolio,
        planning=planning,
        financeiro=financeiro,
        suprimentos=suprimentos,
        riscos=riscos,
        qualidade=qualidade,
        hse=hse,
        carteira=carteira,
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
    idioma: str = "pt",
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
        bars_chart=_bars_chart(kind, bars, idioma),
        curve_chart=dict(read.overview.curve.chart),
        deviation_bands=tuple(read.overview.bands),
        is_portfolio=read.overview.is_portfolio,
        week_label=calculations.short_month(calendario.WEEKLY, calendario.iso_week(cut), idioma),
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


def _bars_chart(
    kind: str, bars: Sequence[calculations.PeriodBar], idioma: str = "pt"
) -> Mapping[str, Any]:
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
    return _chart_data(
        {
            "titulo": _label("Avanço por semana" if weekly else "Avanço por mês", idioma),
            "modo": "periodo",
            "formato": "numero",
            "unidade": " p.p.",
            "casas": 1,
            "series": [
                {"id": "previsto", "rotulo": "Previsto", "papel": "linha-base", "tipo": "valor"},
                {"id": "realizado", "rotulo": "Realizado", "papel": "realizado", "tipo": "valor"},
            ],
            "periodos": periods,
        },
        idioma,
    )


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


# ── Relatório gerencial: a folha Financeiro (ISSUE-084) ────────────────────

# Quantos meses o valor agregado mês a mês da folha mostra, terminando no mês de competência.
VALUE_MONTHS = 6


def _financeiro_sheet(
    session: Session,
    *,
    user: User,
    scope: Scope,
    kind: str,
    period: str,
    reference_date: date,
    idioma: str = "pt",
) -> FinanceiroSheet:
    """A folha Financeiro montada no mês de competência, pela leitura do dono (D9).

    Os números são os mesmos da tela de KPIs de custo no mesmo corte: ``cost_kpis_overview`` no
    mês de competência (no semanal, o último mês fechado). A curva vem de
    ``financial_curve_overview`` lida no próprio mês — a tendência do dono já sai calculada a
    partir do realizado dele, sem dado posterior ao período — e a EAC por pacote é a leitura do
    mapa de controle no mês, com as faixas de calor que o dono calcula dos parâmetros vigentes.
    Sem fechamento até o fim do período, a folha sai no aviso do protótipo, só com a análise.
    """
    from src.modulos.financeiro import export as financial_export
    from src.modulos.financeiro import service as financeiro

    month = calculations.competence_month(kind, period)
    overview = financeiro.cost_kpis_overview(session, scope=scope, reference_date=month)
    analysis = _analysis_reading(
        session,
        user=user,
        scope=scope,
        module="financeiro",
        kind=kind,
        period=period,
        reference_date=reference_date,
        idioma=idioma,
    )
    analysis_url = _analysis_url("financeiro", kind, period, scope)
    if overview.actual is None:
        return FinanceiroSheet(
            analysis=analysis,
            analysis_url=analysis_url,
            empty=True,
            month=month,
            month_current=False,
            is_portfolio=scope.is_portfolio,
        )
    curve = financeiro.financial_curve_overview(session, scope=scope, reference_date=month)
    mapa = financeiro.mapa_controle(session, scope=scope, reference_date=month)
    actual = overview.actual
    previous_cents = overview.previous.ac_cents if overview.previous is not None else 0
    return FinanceiroSheet(
        analysis=analysis,
        analysis_url=analysis_url,
        empty=False,
        month=month,
        month_current=_is_cut_month(curve, month),
        is_portfolio=scope.is_portfolio,
        budget_cents=overview.budget_cents,
        actual_cents=actual.ac_cents,
        actual_month_cents=actual.ac_cents - previous_cents,
        planned_month_cents=_planned_month_cents(curve, month),
        ev_cents=actual.ev_cents,
        pv_cents=actual.pv_cents,
        cpi=actual.cpi,
        spi=actual.spi,
        previous_cpi=overview.previous.cpi if overview.previous is not None else None,
        projection_cents=overview.projection_cents,
        vac_cents=overview.vac_cents,
        band_tone=mapa.total.band.tone,
        band_label=mapa.total.band.label,
        contingency_pct=overview.contingency_pct,
        contingency_consumed_cents=overview.contingency_consumed_cents,
        contingency_total_cents=overview.contingency_total_cents,
        eac_trend_cents=curve.kpis.trend_cents if curve.kpis is not None else None,
        curve_chart={} if curve.is_empty else financial_export.curva_financeira_chart(curve),
        history=tuple(
            CostValueMonth(
                month=row.month,
                pv_cents=row.pv_cents,
                ev_cents=row.ev_cents,
                ac_cents=row.ac_cents,
                cpi=row.cpi,
                spi=row.spi,
            )
            for row in overview.history[-VALUE_MONTHS:]
        ),
        packages=tuple(_cost_package_row(row) for row in mapa.rows if row.level == 1),
        total=_cost_package_row(mapa.total),
    )


def _is_cut_month(curve: Any, month: date) -> bool:
    """Se o mês de competência é o mês do corte da curva do dono (o mês ainda em andamento)."""
    index = curve.series.cut_index
    return index >= 0 and curve.series.months[index] == month


def _planned_month_cents(curve: Any, month: date) -> int:
    """O planejado do mês na curva do dono: a diferença para o mês anterior (o primeiro vale o seu)."""
    months = curve.series.months
    if month not in months:
        return 0
    index = months.index(month)
    previous = curve.series.planned[index - 1] if index > 0 else 0
    return curve.series.planned[index] - previous


def _cost_package_row(row: Any) -> CostPackageRow:
    """Uma linha do mapa de controle como a folha Financeiro a lê."""
    return CostPackageRow(
        code=row.code,
        description=row.description,
        project_code=_project_code(row.project_label),
        current_cents=row.current_cents,
        committed_cents=row.committed_cents,
        actual_cents=row.actual_cents,
        projection_cents=row.projection_cents,
        deviation_cents=row.deviation_cents,
        deviation_percent=row.deviation_percent,
        band_tone=row.band.tone,
        band_label=row.band.label,
    )


# ── Relatório gerencial: a folha Suprimentos (ISSUE-084) ───────────────────


def _procurement_sheet(
    session: Session,
    *,
    user: User,
    scope: Scope,
    kind: str,
    period: str,
    reference_date: date,
    cut: date,
    idioma: str = "pt",
) -> ProcurementSheet:
    """A folha Suprimentos montada no corte, pelas fachadas do dono (D9).

    Os KPIs são os do painel de suprimentos no corte; a curva de contratação é a do painel. Os
    marcos realizados são os marcos de pedido com real dentro do período, todos com o desvio
    (a 081 só lista os atrasados). Os previstos são as adjudicações do plano ainda não
    adjudicadas e as entregas dos pedidos ainda não entregues dentro do horizonte do tipo.
    """
    from src.modulos.suprimentos import export as procurement_export
    from src.modulos.suprimentos import service as suprimentos
    from src.modulos.suprimentos import validation as procurement_validation

    panel = suprimentos.list_panel(session, user=user, scope=scope, reference_date=cut)
    listing = suprimentos.list_orders(
        session,
        user=user,
        scope=scope,
        filters=procurement_validation.OrderFilters(
            situation=procurement_validation.ORDER_SITUATION_ALL
        ),
        reference_date=cut,
    )
    packages = suprimentos.list_packages(
        session,
        user=user,
        scope=scope,
        filters=procurement_validation.PackageFilters(),
        reference_date=cut,
    )
    analysis = _analysis_reading(
        session,
        user=user,
        scope=scope,
        module="suprimentos",
        kind=kind,
        period=period,
        reference_date=reference_date,
        idioma=idioma,
    )
    bounds = calendario.period_bounds(kind, period)
    first = bounds[0] if bounds is not None else cut
    horizon = calculations.report_horizon(kind, period)
    summary = panel.summary
    criticals = sorted(
        (line for line in listing.lines if line.critical),
        key=lambda line: (line.slack_days or 0, line.number),
    )
    return ProcurementSheet(
        analysis=analysis,
        analysis_url=_analysis_url("suprimentos", kind, period, scope),
        is_portfolio=scope.is_portfolio,
        adherence_pct=summary.adherence_pct,
        adherence_target=summary.adherence_target,
        adjudicated=summary.adjudicated_until_reference,
        planned=summary.planned_until_reference,
        packages_total=summary.packages,
        adjudicated_cents=summary.adjudicated_cents,
        saving_cents=summary.saving_cents,
        saving_pct=summary.saving_pct,
        otd_pct=summary.orders.otd,
        otd_target=summary.otd_target,
        delivered=summary.orders.delivered,
        delivered_on_time=summary.orders.delivered_on_time,
        critical=summary.orders.critical,
        warning=summary.orders.warning,
        emitted=sum(1 for line in listing.lines if line.emission <= cut),
        emitted_planned=sum(
            1 for line in packages.lines if line.plan_order is not None and line.plan_order <= cut
        ),
        criticals=tuple(_critical_row(line) for line in criticals),
        events=_executed_events(listing.lines, first=first, cut=cut),
        forecasts=_forecast_events(
            packages.lines,
            listing.lines,
            start=horizon[0] if horizon is not None else cut,
            end=horizon[1] if horizon is not None else cut,
        ),
        horizon_start=horizon[0] if horizon is not None else cut,
        horizon_end=horizon[1] if horizon is not None else cut,
        weekly=kind == calendario.WEEKLY,
        curve_chart=procurement_export.panel_contracting_chart(panel),
    )


def _critical_row(line: Any) -> ProcurementCriticalRow:
    """Um pedido crítico como a folha Suprimentos o lê."""
    return ProcurementCriticalRow(
        number=line.number,
        description=line.description,
        project_code=_project_code(line.project_label),
        ros=line.ros,
        forecast=line.forecast,
        slack_days=line.slack_days,
        lli=line.lli,
    )


def _executed_events(
    lines: Sequence[Any], *, first: date, cut: date
) -> tuple[ProcurementEventRow, ...]:
    """Os marcos de pedido realizados dentro do período, com o desvio contra a linha de base."""
    rows: list[ProcurementEventRow] = []
    for line in lines:
        for milestone in line.milestones:
            if milestone.real is None or not first <= milestone.real <= cut:
                continue
            rows.append(
                ProcurementEventRow(
                    date=milestone.real,
                    kind=milestone.name,
                    code=line.number,
                    description=line.description,
                    project_code=_project_code(line.project_label),
                    deviation_days=milestone.deviation_days,
                )
            )
    rows.sort(key=lambda row: (row.date, row.code))
    return tuple(rows)


def _forecast_events(
    packages: Sequence[Any],
    orders: Sequence[Any],
    *,
    start: date,
    end: date,
) -> tuple[ProcurementEventRow, ...]:
    """As adjudicações e entregas previstas no horizonte, com o desvio contra o plano ou o contrato.

    A adjudicação prevista é a do pacote ainda não adjudicado, na previsão do dono ou, sem ela,
    na linha de base; a entrega prevista é a do pedido ainda não entregue.
    """
    rows: list[ProcurementEventRow] = []
    for line in packages:
        adjudication = line.adjudication
        if adjudication is None or adjudication.real is not None:
            continue
        forecast = adjudication.forecast or adjudication.plan
        if forecast is None or not start <= forecast <= end:
            continue
        rows.append(
            ProcurementEventRow(
                date=forecast,
                kind="Adjudicação",
                code=line.code,
                description=line.scope,
                project_code=_project_code(line.project_label),
                deviation_days=(
                    None if adjudication.plan is None else (forecast - adjudication.plan).days
                ),
            )
        )
    for line in orders:
        if line.delivered or not start <= line.forecast <= end:
            continue
        rows.append(
            ProcurementEventRow(
                date=line.forecast,
                kind="Entrega",
                code=line.number,
                description=line.description,
                project_code=_project_code(line.project_label),
                deviation_days=line.contractual_delay_days,
            )
        )
    rows.sort(key=lambda row: (row.date, row.code))
    return tuple(rows)


def _project_code(label: str | None) -> str:
    """O código do projeto no rótulo ``COD · Nome`` do dono; vazio quando não há rótulo."""
    return "" if not label else label.split(" · ", 1)[0]


# ── Relatório gerencial: as folhas Riscos, Qualidade e HSE (ISSUE-085) ─────


def _risk_sheet(
    session: Session,
    *,
    user: User,
    scope: Scope,
    kind: str,
    period: str,
    reference_date: date,
    cut: date,
    idioma: str = "pt",
) -> RiskSheet:
    """A folha Riscos montada na data de referência, pelas fachadas do dono (D9).

    O painel dá os KPIs (ativos, faixas com a meta, exposição, revisão vencida e a pauta), o
    registro dá as naturezas, os identificados e os encerrados do período e os principais; a
    matriz residual (com a inerente de quem não tem residual) vem do painel do dono. A posição
    é a da data de referência (o rodapé da folha informa) e só os identificados e encerrados
    usam o período. O limite da exposição é o saldo da reserva de contingência lido no mapa de
    controle do Financeiro na mesma data.
    """
    from src.modulos.financeiro import service as financeiro
    from src.modulos.riscos import panel_service
    from src.modulos.riscos import service as riscos
    from src.modulos.riscos import validation as risco_validation
    from src.modulos.riscos.calculations import OPPORTUNITY

    panel = panel_service.risk_panel(session, user=user, scope=scope, reference_date=reference_date)
    summary = panel.summary
    listing = riscos.list_risks(
        session,
        user=user,
        scope=scope,
        filters=risco_validation.RiskFilters(
            situation=risco_validation.SITUATION_ALL, include_closed=True
        ),
        reference_date=reference_date,
    )
    matrix = panel_service.risk_matrix(
        session,
        user=user,
        scope=scope,
        assessment=risco_validation.RESIDUAL,
        nature="",
        reference_date=reference_date,
    )
    mapa = financeiro.mapa_controle(session, scope=scope, reference_date=reference_date)
    bounds = calendario.period_bounds(kind, period)
    first = bounds[0] if bounds is not None else cut
    active = [line for line in listing.lines if line.active]
    assessed = [(line, line.current) for line in active if line.current is not None]
    assessed.sort(key=lambda pair: (-pair[1].score, -pair[0].vme_cents, pair[0].code))
    tones = {style.band.id: style.tone for style in matrix.bands}
    evolution = tuple(
        RiskMonthPoint(month=point.month, score=point.score, current=point.current)
        for point in panel.evolution
    )
    return RiskSheet(
        analysis=_analysis_reading(
            session,
            user=user,
            scope=scope,
            module="riscos",
            kind=kind,
            period=period,
            reference_date=reference_date,
            idioma=idioma,
        ),
        analysis_url=_analysis_url("riscos", kind, period, scope),
        is_portfolio=scope.is_portfolio,
        active=summary.active,
        registered=summary.registered,
        threats=sum(1 for line in active if line.nature != OPPORTUNITY),
        opportunities=sum(1 for line in active if line.nature == OPPORTUNITY),
        top=_risk_band_view(summary.top),
        second=None if summary.second is None else _risk_band_view(summary.second),
        exposure_cents=summary.exposure_cents,
        exposure_limit_cents=(
            mapa.reserves.contingency_balance_cents if mapa.reserves is not None else None
        ),
        overdue_reviews=len(summary.overdue),
        agenda=len(panel.agenda),
        identified=sum(1 for line in listing.lines if first <= line.identified_on <= cut),
        closed=sum(
            1
            for line in listing.lines
            if line.closing_date is not None and first <= line.closing_date <= cut
        ),
        matrix=tuple(
            RiskMatrixCellView(
                probability=cell.probability,
                impact=cell.impact,
                tone=tones.get(cell.severity.id, "neutro"),
                threats=sum(1 for risk in cell.risks if risk.nature != OPPORTUNITY),
                opportunities=sum(1 for risk in cell.risks if risk.nature == OPPORTUNITY),
            )
            for cell in matrix.cells
        ),
        evolution=evolution,
        evolution_chart=_risk_evolution_chart(evolution),
        principais=tuple(
            RiskTopRow(
                number=calculations.risk_number(line.code, portfolio=scope.is_portfolio),
                title=line.title,
                nature=line.nature,
                score=view.score,
                severity=view.severity.name,
                tone=tones.get(view.severity.id, "neutro"),
                strategy=line.strategy or "",
                owner_name=line.owner_name,
                next_review=line.next_review,
                review_overdue=line.review_overdue,
            )
            for line, view in assessed[:TOP_RISKS]
        ),
    )


def _risk_band_view(count: Any) -> RiskBandView:
    """Uma faixa do resumo de riscos como a folha a lê."""
    return RiskBandView(
        name=count.band.name,
        total=count.total,
        threats=count.threats,
        opportunities=count.opportunities,
        goal=count.goal,
    )


def _risk_evolution_chart(
    points: Sequence[RiskMonthPoint], idioma: str = "pt"
) -> Mapping[str, Any]:
    """O ``data-dados`` da exposição mensal: o score residual somado das ameaças por mês."""
    periods: list[dict[str, Any]] = []
    for point in points:
        year, month = _month_of(point.month)
        periods.append(
            {
                "ano": year,
                "mes": month,
                "valores": {"score": float(point.score)},
            }
        )
    return _chart_data(
        {
            "titulo": "Exposição das ameaças",
            "modo": "periodo",
            "formato": "numero",
            "casas": 0,
            "series": [
                {
                    "id": "score",
                    "rotulo": "Score residual somado",
                    "papel": "atencao",
                    "tipo": "valor",
                }
            ],
            "periodos": periods,
        },
        idioma,
    )


def _quality_sheet(
    session: Session,
    *,
    user: User,
    scope: Scope,
    kind: str,
    period: str,
    reference_date: date,
    cut: date,
    idioma: str = "pt",
) -> QualitySheet:
    """A folha Qualidade montada no corte, pelas fachadas do dono (D9).

    A posição no corte (em aberto, críticas e custo acumulado), o período (abertas, encerradas,
    inspeções e auditorias realizadas e o custo do período) e a data de referência (a pauta e as
    auditorias atrasadas) vêm do registro e do painel; a série de RNC termina no mês do corte e a
    disciplina com mais RNC vem do painel do dono. As metas são as do grupo ``qualidade`` vigente.
    """
    from src.modulos.qualidade import calculations as quality_calculations
    from src.modulos.qualidade import painel_service
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
    panel = painel_service.quality_panel(
        session, user=user, scope=scope, reference_date=reference_date
    )
    bounds = calendario.period_bounds(kind, period)
    first = bounds[0] if bounds is not None else cut
    in_period = [line for line in inspections if first <= line.inspection_date <= cut]
    performed = [
        line
        for line in audits
        if line.situation == quality_calculations.AUDIT_DONE
        and first <= (line.performed_on or line.audit_date) <= cut
    ]
    series = tuple(
        QualitySeriesPoint(
            month=point.month,
            opened=point.opened,
            closed=point.closed,
            open=point.open,
            inspections=point.inspections,
            approval_pct=point.approval_pct,
        )
        for point in painel_service.quality_series(rncs, inspections, reference_date=cut)
    )
    discipline = tuple(
        QualityDisciplineRow(name=line.name, total=line.total, pct=line.pct)
        for line in panel.by_discipline
    )
    open_at_cut = [
        line
        for line in rncs
        if line.rnc_date <= cut
        and (line.closing_date is None or line.closing_date > cut)
        and line.situation != quality_calculations.SITUATION_CANCELLED
    ]
    return QualitySheet(
        analysis=_analysis_reading(
            session,
            user=user,
            scope=scope,
            module="qualidade",
            kind=kind,
            period=period,
            reference_date=reference_date,
            idioma=idioma,
        ),
        analysis_url=_analysis_url("qualidade", kind, period, scope),
        is_portfolio=scope.is_portfolio,
        open_at_cut=len(open_at_cut),
        critical_at_cut=sum(
            1 for line in open_at_cut if line.severity == quality_calculations.SEVERITIES[0]
        ),
        overdue_at_reference=sum(1 for entry in panel.agenda if entry.line.overdue),
        opened_period=sum(
            1
            for line in rncs
            if first <= line.rnc_date <= cut
            and line.situation != quality_calculations.SITUATION_CANCELLED
        ),
        closed_period=sum(
            1
            for line in rncs
            if line.situation == quality_calculations.SITUATION_CLOSED
            and line.closing_date is not None
            and first <= line.closing_date <= cut
        ),
        approval_pct=quality_calculations.inspection_approval_rate(
            line.result for line in in_period
        ),
        approval_meta=_meta(parameters, "metaAprovacaoInspecaoPct"),
        rejected=tuple(
            QualityRejectedRow(
                date=line.inspection_date,
                point=line.point,
                itp_code=line.itp_code,
                company_name=line.company_name,
                rnc_code=line.rnc_code,
            )
            for line in in_period
            if line.result == quality_calculations.RESULT_REJECTED
        ),
        inspections=len(in_period),
        conformity_pct=quality_calculations.audit_conformity_rate(
            sum(line.items_conforming or 0 for line in performed),
            sum(line.items_verified or 0 for line in performed),
        ),
        conformity_meta=_meta(parameters, "metaConformidadeAuditoriaPct"),
        audits_period=len(performed),
        late_audits=len(panel.overdue_audits),
        cost_accumulated_cents=sum(
            line.cost_cents
            for line in rncs
            if line.rnc_date <= cut and line.situation != quality_calculations.SITUATION_CANCELLED
        ),
        cost_period_cents=sum(
            line.cost_cents
            for line in rncs
            if first <= line.rnc_date <= cut
            and line.situation != quality_calculations.SITUATION_CANCELLED
        ),
        discipline=discipline,
        discipline_total=sum(line.total for line in discipline),
        series=series,
        series_chart=_quality_series_chart(series, idioma),
        agenda=tuple(
            QualityAgendaRow(
                code=entry.line.code,
                description=entry.line.description,
                severity=entry.line.severity,
                situation=entry.line.situation,
                reasons=entry.reasons,
            )
            for entry in panel.agenda
        ),
    )


def _quality_series_chart(
    series: Sequence[QualitySeriesPoint], idioma: str = "pt"
) -> Mapping[str, Any]:
    """O ``data-dados`` das RNC por mês: as abertas e as encerradas de cada mês do corte."""
    periods: list[dict[str, Any]] = []
    for point in series:
        year, month = _month_of(point.month)
        periods.append(
            {
                "ano": year,
                "mes": month,
                "valores": {"abertas": point.opened, "encerradas": point.closed},
            }
        )
    return _chart_data(
        {
            "titulo": "RNC por mês",
            "modo": "periodo",
            "formato": "numero",
            "casas": 0,
            "series": [
                {"id": "abertas", "rotulo": "Abertas", "papel": "atencao", "tipo": "valor"},
                {"id": "encerradas", "rotulo": "Encerradas", "papel": "realizado", "tipo": "valor"},
            ],
            "periodos": periods,
        },
        idioma,
    )


def _hse_sheet(
    session: Session,
    *,
    user: User,
    scope: Scope,
    kind: str,
    period: str,
    reference_date: date,
    cut: date,
    idioma: str = "pt",
) -> HseSheet:
    """A folha HSE montada no mês do corte, pelo painel do dono (D9).

    O painel dá os indicadores do mês e do acumulado, a referência da pirâmide e a base das
    taxas; o histograma de mão de obra do dono dá o HHT previsto do mês; as ocorrências da
    semana (não ambientais) saem da tela de ocorrências do dono, com os níveis da pirâmide.
    """
    from src.modulos.hse import calculations as hse_calculations
    from src.modulos.hse import painel_service
    from src.modulos.hse import service as hse
    from src.modulos.hse import validation as hse_validation

    month = date(cut.year, cut.month, 1)
    panel = painel_service.panel(
        session,
        user=user,
        scope=scope,
        reference_date=cut,
        month=month,
        pyramid_kind=None,
    )
    analysis = _analysis_reading(
        session,
        user=user,
        scope=scope,
        module="hse",
        kind=kind,
        period=period,
        reference_date=reference_date,
        idioma=idioma,
    )
    analysis_url = _analysis_url("hse", kind, period, scope)
    if (
        panel.month is None
        or panel.month_indicators is None
        or panel.accumulated_indicators is None
    ):
        return HseSheet(
            analysis=analysis,
            analysis_url=analysis_url,
            is_portfolio=scope.is_portfolio,
            weekly=kind == calendario.WEEKLY,
            empty=True,
        )
    bounds = calendario.period_bounds(kind, period)
    first = bounds[0] if bounds is not None else cut
    screen = hse.occurrences_screen(
        session,
        scope=scope,
        filters=hse_validation.OccurrenceFilters(),
        reference_date=cut,
    )
    period_rows = [
        row
        for row in screen.rows
        if not row.environmental
        and first <= calendario.in_product_timezone(row.happened_at).date() <= cut
    ]
    levels = [0, 0, 0, 0]
    for row in period_rows:
        if row.level is not None and 1 <= row.level <= len(levels):
            levels[row.level - 1] += 1
    histogram = hse.labour_histogram(session, scope=scope, reference_date=cut)
    planned = hse_calculations.planned_labour(histogram, up_to=panel.month, only_month=True)
    start = panel.project_start
    evolution = replace(panel, evolution=panel.evolution[-HSE_EVOLUTION_MONTHS:])
    return HseSheet(
        analysis=analysis,
        analysis_url=analysis_url,
        is_portfolio=scope.is_portfolio,
        weekly=kind == calendario.WEEKLY,
        empty=False,
        month=panel.month,
        partial_month=panel.month == date(reference_date.year, reference_date.month, 1),
        base=panel.base,
        base_name=hse_calculations.rate_base_name(panel.base),
        reference_name=panel.reference.name,
        reference_ratio=panel.reference.almost_miss_ratio,
        observations_target=panel.observations_target,
        month_indicators=panel.month_indicators,
        accumulated=panel.accumulated_indicators,
        days_expected=None if start is None else max(0, (cut - start).days),
        days_since=panel.last_lti or start,
        occurrences=len(period_rows),
        occurrence_levels=tuple(levels),
        hipo_period=sum(1 for row in period_rows if row.hipo),
        month_occurrences=sum(panel.month_indicators.pyramid[: len(levels)]),
        hours_expected=None if planned is None else planned.hours,
        first_month=panel.window_start or panel.month,
        pyramid_chart=painel_service.pyramid_chart(panel),
        evolution_chart=painel_service.evolution_chart(evolution),
    )


def _carteira_sheet(session: Session, *, user: User, reference_date: date) -> CarteiraSheet:
    """A folha Carteira montada na data de referência, só no Portfólio (D9).

    Espelha a leitura da carteira do Início (ISSUE-080): o peso de ``portfolio_weights``; por
    projeto, o prazo (``planning_kpis_overview``) e o custo (``cost_kpis_overview``) com a
    tendência da própria curva, os riscos no topo (``risk_panel``), os pedidos críticos
    (``list_panel``) e as ações atrasadas (``count_by_status``). Os totais reusam as leituras
    consolidadas do Portfólio e a situação usa as faixas do Início; a Curva S física é a
    ponderada da carteira e os critérios vêm do grupo ``portfolio`` dos parâmetros vigentes.
    """
    from src.modulos.central_acoes import service as central_acoes
    from src.modulos.financeiro import service as financeiro
    from src.modulos.planejamento import service as planejamento
    from src.modulos.riscos import panel_service as riscos_painel
    from src.modulos.suprimentos import service as suprimentos

    portfolio = Scope(project_id=None, source="url")
    planning = planejamento.planning_kpis_overview(
        session, scope=portfolio, reference_date=reference_date
    )
    cost = financeiro.cost_kpis_overview(session, scope=portfolio, reference_date=reference_date)
    risks = riscos_painel.risk_panel(
        session, user=user, scope=portfolio, reference_date=reference_date
    )
    supply = suprimentos.list_panel(
        session, user=user, scope=portfolio, reference_date=reference_date
    )
    actions = central_acoes.count_by_status(
        session, user=user, scope=portfolio, reference_date=reference_date
    )
    mapa = financeiro.mapa_controle(session, scope=portfolio, reference_date=reference_date)
    weights = financeiro.portfolio_weights(session, reference_date=reference_date)
    rows: list[CarteiraProjectRow] = []
    for project in configuracoes.list_projects(session):
        scope = Scope(project_id=project.id, source="url")
        project_planning = planejamento.planning_kpis_overview(
            session, scope=scope, reference_date=reference_date
        )
        project_cost = financeiro.cost_kpis_overview(
            session, scope=scope, reference_date=reference_date
        )
        project_risks = riscos_painel.risk_panel(
            session, user=user, scope=scope, reference_date=reference_date
        )
        project_supply = suprimentos.list_panel(
            session, user=user, scope=scope, reference_date=reference_date
        )
        project_actions = central_acoes.count_by_status(
            session, user=user, scope=scope, reference_date=reference_date
        )
        weight = weights.get(project.id)
        cpi = None if project_cost.indicators is None else project_cost.indicators.cpi
        rows.append(
            CarteiraProjectRow(
                project_id=project.id,
                code=project.code,
                name=project.name,
                weight=Decimal(0) if weight is None else weight.weight,
                budget_cents=project_cost.budget_cents,
                predicted=project_planning.indicators.predicted,
                actual=project_planning.indicators.actual,
                spi=project_planning.indicators.spi,
                cpi=cpi,
                projection_cents=project_cost.projection_cents,
                vac_cents=project_cost.vac_cents,
                baseline_finish=project_planning.indicators.baseline_finish,
                trend_finish=calculations.trend_finish(
                    project_planning.curve.series.months, project_planning.curve.series.trend
                ),
                critical_risks=project_risks.summary.top.total,
                critical_orders=project_supply.summary.orders.critical,
                overdue_actions=project_actions.overdue,
                health=inicio_calculations.health_band(project_planning.indicators.spi, cpi),
            )
        )
    rows.sort(key=lambda row: row.weight, reverse=True)
    group = configuracoes.current_group(session, group="portfolio", reference_date=reference_date)
    criteria = tuple(
        CarteiraCriterionRow(
            id=str(item["id"]),
            name=str(item.get("nome") or item["id"]),
            source=str(item.get("fonte", "nota")),
            weight=Decimal(str(item.get("peso", 0))),
        )
        for item in group.get("criterios") or []
        if isinstance(item, Mapping) and item.get("id")
    )
    return CarteiraSheet(
        reference_date=reference_date,
        project_count=len(rows),
        budget_cents=cost.budget_cents,
        budget_baseline_cents=mapa.total.baseline_cents,
        predicted=planning.indicators.predicted,
        actual=planning.indicators.actual,
        deviation_pp=planning.indicators.deviation_pp,
        spi=planning.indicators.spi,
        spi_tone=_carteira_tone(
            planning.indicators.spi,
            attention=inicio_calculations.SPI_ATTENTION,
            critical=inicio_calculations.SPI_CRITICAL,
        ),
        cpi=None if cost.indicators is None else cost.indicators.cpi,
        cpi_tone=_carteira_tone(
            None if cost.indicators is None else cost.indicators.cpi,
            attention=inicio_calculations.CPI_ATTENTION,
            critical=inicio_calculations.CPI_CRITICAL,
        ),
        projection_cents=cost.projection_cents,
        vac_cents=cost.vac_cents,
        baseline_finish=planning.indicators.baseline_finish,
        trend_finish=calculations.trend_finish(
            planning.curve.series.months, planning.curve.series.trend
        ),
        critical_risks=risks.summary.top.total,
        critical_orders=supply.summary.orders.critical,
        overdue_actions=actions.overdue,
        projects=tuple(rows),
        criteria=criteria,
        curve_chart=dict(planning.curve.chart),
    )


def _carteira_tone(value: Decimal | None, *, attention: Decimal, critical: Decimal) -> str:
    """O tom do índice da carteira nas faixas do Início: ``success``, ``warning``, ``danger`` ou ``info``.

    As faixas são as da tela Início (``inicio.calculations.index_band``): o SPI em 0,95 e 0,90 e
    o CPI em 0,98 e 0,93, para o relatório mostrar a mesma situação da carteira do Início.
    """
    band = inicio_calculations.index_band(value, attention, critical)
    return {"ok": "success", "warn": "warning", "erro": "danger"}.get(band or "", "info")


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


def _scope_label(session: Session, scope: Scope, idioma: str = "pt") -> str:
    """O rótulo do escopo: ``COD · Nome`` no projeto; ``Portfólio · N projetos`` no Portfólio."""
    if scope.project_id is None:
        count = len(configuracoes.list_projects(session))
        noun = _label("projeto" if count == 1 else "projetos", idioma)
        return f"{_label('Portfólio', idioma)} · {count} {noun}"
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
