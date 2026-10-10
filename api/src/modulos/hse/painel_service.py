"""O painel HSE (ISSUE-075, D6, D9, D11): os indicadores, as janelas, a evolução e a nota sugerida.

O painel é calculado a cada leitura: a base das taxas e a referência da pirâmide vêm do grupo
``hse`` dos parâmetros vigentes (a referência pode ser sobreposta pela query), o HHT e os
fechamentos saem das tabelas do próprio módulo e as ações de HSE vêm da fachada da Central
(origem ``HSE`` das ocorrências e das recomendações, mais o grupo ``HSE`` das atas) — nenhum
módulo lê a tabela ``acao`` (D9). Nada aqui lê o relógio: a data de referência é argumento.

As janelas são as do protótipo: "no mês" é o mês escolhido e "acumulado" vai do primeiro mês
com HHT até ele. "Dias sem afastamento" e "ações no prazo" são do acumulado, mas calculados em
qualquer janela do mesmo jeito: a última LTI é a de **todas** as ocorrências do escopo e as
ações comparam com a data de referência, nunca com o fim do mês.

A nota HSE sugerida de uma empresa (``company_note_suggestion``) é decisão do dono (10/10/2026):
o painel calcula de 1 a 5 pela TRIF da empresa contra a do projeto e a avaliação de desempenho
(03) a exibe e a pré-seleciona no critério HSE — a nota gravada é a que o avaliador confirmar.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, service
from src.modulos.hse.calculations import (
    ActionDueLine,
    ClosingLine,
    HoursLine,
    HseIndicators,
    HseWindow,
    OccurrenceFact,
)
from src.modulos.hse.models import MonthlyClosing, Occurrence, OccurrenceRestricted

MODULE = "hse"
PARAMETER_GROUP = "hse"
# O grupo das ações de HSE que vêm das atas, ao lado da origem ``HSE`` das ocorrências.
HSE_GROUP = "HSE"
# O limiar do card "Ações HSE no prazo" (o protótipo o tinha na tela, não no parâmetro).
ACTIONS_ON_TIME_TARGET = 90

PYRAMID_CHART_TITLE = "Pirâmide de segurança"
EVOLUTION_CHART_TITLE = "Evolução mensal de TF e TRIF"


@dataclass(frozen=True)
class HseMonthPoint:
    """Um mês da evolução: a TF e a TRIF do próprio mês."""

    month: date
    tf: Decimal | None
    trif: Decimal | None


@dataclass(frozen=True)
class HseGroupLine:
    """Uma linha das listas por área ou por empresa: o nome e o total de ocorrências."""

    name: str
    total: int


@dataclass(frozen=True)
class HseMonthOption:
    """Uma opção do seletor de mês: o valor ``AAAA-MM`` e o rótulo curto (``Set``)."""

    value: str
    label: str


@dataclass(frozen=True)
class CompanyHseNote:
    """A nota HSE sugerida de uma empresa e o que a sustenta (a leitura da avaliação de 03)."""

    note: int
    trif: Decimal
    project_trif: Decimal
    hours: Decimal
    registrable: int
    lti: int


@dataclass(frozen=True)
class HsePanel:
    """Tudo o que o painel mostra: os meses, os indicadores das duas janelas, a evolução e as listas."""

    months: tuple[date, ...]
    years: tuple[str, ...]
    year: str
    month: date | None
    month_options: tuple[HseMonthOption, ...]
    window_start: date | None
    window_end: date | None
    month_indicators: HseIndicators | None
    accumulated_indicators: HseIndicators | None
    evolution: tuple[HseMonthPoint, ...]
    by_area: tuple[HseGroupLine, ...]
    by_company: tuple[HseGroupLine, ...]
    base: int
    reference: calculations.PyramidReference
    observations_target: int
    reference_date: date
    project_start: date | None
    last_lti: date | None

    @property
    def is_empty(self) -> bool:
        """Se o escopo ainda não tem nenhum mês com HHT: o vazio de origem do painel."""
        return self.month is None

    @classmethod
    def empty(
        cls,
        *,
        base: int,
        reference: calculations.PyramidReference,
        observations_target: int,
        reference_date: date,
        project_start: date | None = None,
    ) -> HsePanel:
        """O painel vazio do escopo sem HHT: o fragmento mostra o vazio de origem, sem KPIs."""
        return cls(
            months=(),
            years=(),
            year="",
            month=None,
            month_options=(),
            window_start=None,
            window_end=None,
            month_indicators=None,
            accumulated_indicators=None,
            evolution=(),
            by_area=(),
            by_company=(),
            base=base,
            reference=reference,
            observations_target=observations_target,
            reference_date=reference_date,
            project_start=project_start,
            last_lti=None,
        )


@dataclass(frozen=True)
class _PanelData:
    """O que a fachada leu uma vez e as duas janelas reaproveitam."""

    facts: tuple[OccurrenceFact, ...]
    hours: tuple[HoursLine, ...]
    closings: tuple[ClosingLine, ...]
    actions: tuple[ActionDueLine, ...]
    base: int
    recommendations_pct: Decimal | None
    last_lti: date | None
    project_start: date | None
    reference_date: date

    def window(self, start: date, end: date) -> HseIndicators:
        """Os indicadores da janela de meses, de ``start`` a ``end`` inclusive."""
        facts = [fact for fact in self.facts if start <= calculations.month_of(fact.day) <= end]
        closings = [
            line for line in self.closings if start <= calculations.month_of(line.month) <= end
        ]
        hours = sum(
            (
                line.hours
                for line in self.hours
                if start <= calculations.month_of(line.month) <= end
            ),
            Decimal(0),
        )
        return calculations.summarize_window(
            HseWindow(
                facts=facts,
                closings=closings,
                actions=self.actions,
                hours=hours,
                deviations=sum(line.deviations for line in closings),
                base=self.base,
                recommendations_pct=self.recommendations_pct,
                reference_date=self.reference_date,
                last_lti=self.last_lti,
                project_start=self.project_start,
            )
        )


def panel_months(session: Session, *, scope: Scope) -> list[date]:
    """Os meses com HHT no escopo, do mais antigo ao mais novo."""
    return sorted({line.month for line in service.hours_lines(session, scope=scope)})


def resolve_month(
    months: Sequence[date], *, year: str | None, requested: date | None
) -> date | None:
    """O mês pedido quando existe no ano pedido (ou no escopo); senão o último mês dele.

    É a regra do protótipo: trocar o ano leva ao último mês com HHT daquele ano; sem mês ou com
    um mês fora, o último mês com HHT. Sem nenhum mês, ``None``.
    """
    if not months:
        return None
    candidates = list(months)
    wanted = (year or "").strip()
    if wanted:
        in_year = [month for month in months if f"{month.year:04d}" == wanted]
        if in_year:
            candidates = in_year
    if requested is not None and requested in candidates:
        return requested
    return candidates[-1]


def panel(
    session: Session,
    *,
    user: User,
    scope: Scope,
    reference_date: date,
    month: date | None,
    pyramid_kind: str | None,
) -> HsePanel:
    """O painel do escopo: os meses, o mês selecionado, as duas janelas de indicadores e os gráficos."""
    rbac.require_module(user, MODULE)
    parameters = _parameters(session, reference_date=reference_date)
    base = int(parameters.get("baseTaxa", calculations.DEFAULT_RATE_BASE))
    kind = (
        pyramid_kind
        if pyramid_kind in calculations.PYRAMID_REFERENCES
        else str(parameters.get("referenciaPiramide") or "")
    )
    reference = calculations.pyramid_reference(kind)
    months = panel_months(session, scope=scope)
    project_start = _project_start(session, scope=scope)
    observations_target = int(
        parameters.get("metas", {}).get(
            "observacoesPor10MilHht", service.DEFAULT_OBSERVATION_TARGET
        )
    )
    if not months:
        return HsePanel.empty(
            base=base,
            reference=reference,
            observations_target=observations_target,
            reference_date=reference_date,
            project_start=project_start,
        )
    chosen = resolve_month(months, year=None, requested=month) or months[-1]
    data = _read(session, user=user, scope=scope, reference_date=reference_date, base=base)
    first = months[0]
    return HsePanel(
        months=tuple(months),
        years=tuple(sorted({f"{item.year:04d}" for item in months})),
        year=f"{chosen.year:04d}",
        month=chosen,
        month_options=tuple(
            HseMonthOption(
                value=calculations.month_label(item),
                label=calculations.MONTH_NAMES[item.month - 1],
            )
            for item in months
            if item.year == chosen.year
        ),
        window_start=first,
        window_end=chosen,
        month_indicators=data.window(chosen, chosen),
        accumulated_indicators=data.window(first, chosen),
        evolution=tuple(
            HseMonthPoint(
                month=item,
                tf=data.window(item, item).tf,
                trif=data.window(item, item).trif,
            )
            for item in months
        ),
        by_area=_area_lines(data.facts, start=first, end=chosen),
        by_company=_company_lines(session, data.facts, start=first, end=chosen),
        base=base,
        reference=reference,
        observations_target=observations_target,
        reference_date=reference_date,
        project_start=project_start,
        last_lti=data.last_lti,
    )


def company_note_suggestion(
    session: Session, *, company_id: int, scope: Scope, reference_date: date
) -> CompanyHseNote | None:
    """A nota HSE sugerida de uma empresa na janela acumulada do escopo; ``None`` sem HHT dela.

    A janela vai do primeiro mês com HHT do escopo até a data de referência. A TRIF da empresa
    é comparada com a do projeto (``calculations.suggested_hse_note``) e uma LTI da empresa na
    janela limita a nota a 2.
    """
    months = [month for month in panel_months(session, scope=scope) if month <= reference_date]
    if not months:
        return None
    window_start, window_end = months[0], months[-1]
    facts = [
        fact
        for fact in _facts(session, scope=scope)
        if window_start <= calculations.month_of(fact.day) <= window_end
    ]
    hours = [
        line
        for line in service.hours_lines(session, scope=scope)
        if window_start <= calculations.month_of(line.month) <= window_end
    ]
    company_hours = sum((line.hours for line in hours if line.company_id == company_id), Decimal(0))
    if company_hours <= 0:
        return None
    parameters = _parameters(session, reference_date=reference_date)
    base = int(parameters.get("baseTaxa", calculations.DEFAULT_RATE_BASE))
    company_registrable = sum(
        1
        for fact in facts
        if fact.company_id == company_id and fact.kind in calculations.REGISTRABLE_KINDS
    )
    company_lti = sum(
        1 for fact in facts if fact.company_id == company_id and fact.kind in calculations.LTI_KINDS
    )
    project_registrable = sum(1 for fact in facts if fact.kind in calculations.REGISTRABLE_KINDS)
    project_hours = sum((line.hours for line in hours), Decimal(0))
    company_trif = calculations.quantize_half_up(
        calculations.rate_hse(company_registrable, company_hours, base), 2
    )
    project_trif = calculations.quantize_half_up(
        calculations.rate_hse(project_registrable, project_hours, base), 2
    )
    note = calculations.suggested_hse_note(company_trif, project_trif, company_lti)
    if note is None or company_trif is None or project_trif is None:
        return None
    return CompanyHseNote(
        note=note,
        trif=company_trif,
        project_trif=project_trif,
        hours=company_hours,
        registrable=company_registrable,
        lti=company_lti,
    )


def pyramid_chart(panel: HsePanel) -> dict[str, object]:
    """O ``data-dados`` da pirâmide dupla: as contagens do mês e do acumulado e a referência.

    O painel vazio de origem (sem mês) devolve um mapa vazio: o fragmento só o pede com dados.
    """
    if panel.month is None or panel.window_start is None or panel.window_end is None:
        return {}
    return {
        "titulo": PYRAMID_CHART_TITLE,
        "niveis": [
            {
                "id": level_id,
                "rotulo": label,
                "papel": role,
            }
            for level_id, label, role in zip(
                calculations.PYRAMID_LEVEL_IDS,
                calculations.PYRAMID_CHART_LABELS,
                calculations.PYRAMID_LEVEL_ROLES,
                strict=True,
            )
        ],
        "piramides": [
            {
                "titulo": f"Mês: {calculations.month_display(panel.month)}",
                "valores": _pyramid_values(panel.month_indicators),
            },
            {
                "titulo": (
                    f"Acumulado: {calculations.month_display(panel.window_start)}"
                    f" a {calculations.month_display(panel.window_end)}"
                ),
                "valores": _pyramid_values(panel.accumulated_indicators),
            },
        ],
        "referencia": panel.reference.chart(),
    }


def evolution_chart(panel: HsePanel) -> dict[str, object]:
    """O ``data-dados`` da evolução mensal (linhas múltiplas): a TF e a TRIF de cada mês com HHT."""
    return {
        "titulo": EVOLUTION_CHART_TITLE,
        "casas": 2,
        "series": [
            {"id": "tf", "rotulo": "TF (com afastamento)", "papel": "realizado"},
            {"id": "trif", "rotulo": "TRIF (registráveis)", "papel": "comprometido"},
        ],
        "periodos": [
            {
                "ano": point.month.year,
                "mes": point.month.month,
                "valores": {
                    "tf": _number(point.tf),
                    "trif": _number(point.trif),
                },
            }
            for point in panel.evolution
        ],
    }


def _parameters(session: Session, *, reference_date: date) -> dict[str, Any]:
    """O grupo vigente do HSE, com o valor inicial do que faltar, como o serviço o lê."""
    values = configuracoes.current_group(
        session, group=PARAMETER_GROUP, reference_date=reference_date
    )
    initial = configuracoes.INITIAL_PARAMETERS[PARAMETER_GROUP]
    return {**initial, **values}


def _read(
    session: Session, *, user: User, scope: Scope, reference_date: date, base: int
) -> _PanelData:
    """Lê uma vez o que as duas janelas usam: ocorrências, HHT, fechamentos e as ações de HSE."""
    facts = _facts(session, scope=scope)
    return _PanelData(
        facts=facts,
        hours=tuple(service.hours_lines(session, scope=scope)),
        closings=_closings(session, scope=scope),
        actions=tuple(
            ActionDueLine(due_date=record.due_date, completed_on=record.completed_on)
            for record in actions.actions_of_origin_or_group(
                session,
                user=user,
                scope=scope,
                origin_kind=service.HSE_ORIGIN,
                group=HSE_GROUP,
                reference_date=reference_date,
            )
        ),
        base=base,
        recommendations_pct=service.recommendation_share(session, scope=scope).pct,
        last_lti=_last_lti(facts),
        project_start=_project_start(session, scope=scope),
        reference_date=reference_date,
    )


def _scoped(statement: Select[Any], model: Any, scope: Scope) -> Select[Any]:
    if scope.project_id is None:
        return statement
    return statement.where(model.project_id == scope.project_id)


def _facts(session: Session, *, scope: Scope) -> tuple[OccurrenceFact, ...]:
    """As ocorrências do escopo como o painel as lê, com os dias do bloco restrito (sem o nome)."""
    statement = (
        select(Occurrence, OccurrenceRestricted)
        .outerjoin(OccurrenceRestricted, OccurrenceRestricted.occurrence_id == Occurrence.id)
        .order_by(Occurrence.happened_at, Occurrence.id)
    )
    if scope.project_id is not None:
        statement = statement.where(Occurrence.project_id == scope.project_id)
    return tuple(
        OccurrenceFact(
            day=calendario.in_product_timezone(row.Occurrence.happened_at).date(),
            kind=row.Occurrence.kind,
            area=row.Occurrence.area,
            company_id=row.Occurrence.company_id,
            environmental=row.Occurrence.environmental,
            hipo=row.Occurrence.hipo,
            days_lost=(
                row.OccurrenceRestricted.days_lost if row.OccurrenceRestricted is not None else 0
            ),
            days_charged=(
                row.OccurrenceRestricted.days_charged if row.OccurrenceRestricted is not None else 0
            ),
        )
        for row in session.execute(statement).all()
    )


def _closings(session: Session, *, scope: Scope) -> tuple[ClosingLine, ...]:
    """Os fechamentos mensais do escopo como os indicadores proativos os leem."""
    statement = _scoped(select(MonthlyClosing), MonthlyClosing, scope).order_by(
        MonthlyClosing.month
    )
    return tuple(
        ClosingLine(
            project_id=row.project_id,
            month=row.month,
            deviations=row.deviations,
            observations=row.observations,
            planned_dds=row.planned_dds,
            held_dds=row.held_dds,
            inspected_items=row.inspected_items,
            conforming_items=row.conforming_items,
        )
        for row in session.scalars(statement)
    )


def _last_lti(facts: Sequence[OccurrenceFact]) -> date | None:
    """A última LTI de todas as ocorrências do escopo, fora de qualquer janela (o protótipo)."""
    days = [fact.day for fact in facts if fact.kind in calculations.LTI_KINDS]
    return max(days) if days else None


def _project_start(session: Session, *, scope: Scope) -> date | None:
    """O início do projeto do escopo; no Portfólio, o início mais antigo da carteira."""
    starts = [
        project.start_date
        for project in configuracoes.list_projects(session)
        if (scope.project_id is None or project.id == scope.project_id)
    ]
    found = [start for start in starts if start is not None]
    return min(found) if found else None


def _pyramid_values(indicators: HseIndicators | None) -> dict[str, int]:
    levels = indicators.pyramid if indicators is not None else (0, 0, 0, 0, 0)
    return dict(zip(calculations.PYRAMID_LEVEL_IDS, levels, strict=True))


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _group_counts(lines: Sequence[tuple[str, int]]) -> tuple[HseGroupLine, ...]:
    """Ordena as contagens por total desc (empate pelo nome) e as devolve como linhas."""
    ordered = sorted(lines, key=lambda pair: (-pair[1], pair[0]))
    return tuple(HseGroupLine(name=name, total=total) for name, total in ordered)


def _area_lines(
    facts: Sequence[OccurrenceFact], *, start: date, end: date
) -> tuple[HseGroupLine, ...]:
    """As ocorrências não ambientais da janela acumulada por área, da maior para a menor."""
    counts = Counter(
        fact.area
        for fact in facts
        if not fact.environmental and start <= calculations.month_of(fact.day) <= end
    )
    return _group_counts(list(counts.items()))


def _company_lines(
    session: Session,
    facts: Sequence[OccurrenceFact],
    *,
    start: date,
    end: date,
) -> tuple[HseGroupLine, ...]:
    """As ocorrências não ambientais da janela acumulada por empresa, com o nome do cadastro."""
    names = service.names_of(session)
    counts = Counter(
        fact.company_id
        for fact in facts
        if not fact.environmental and start <= calculations.month_of(fact.day) <= end
    )
    return _group_counts(
        [(names.company(company_id), total) for company_id, total in counts.items()]
    )
