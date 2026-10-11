"""Exportação do Início (ISSUE-079 e ISSUE-080, D12): um documento, o Excel e a folha imprimível.

O documento do resumo leva o que a tela mostra: os oito indicadores-chave com a
referência de gestão, a carteira de projetos (no Portfólio, a primeira das
tabelas), os pontos de atenção e os cards dos módulos como tabela. Os dois
formatos saem daqui (``core.excel`` e ``core.printable``), então nada que a
tela mostra falta em um deles. Como os títulos dos pontos de atenção já trazem
o código do projeto no Portfólio e a carteira tem a sua própria coluna
``Projeto``, as tabelas não pedem a coluna ``Projeto`` automática
(``per_project=False``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from src.core.export_document import (
    Cell,
    Column,
    Document,
    Kpi,
    Paper,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    format_value,
    row,
)
from src.modulos.inicio import service

if TYPE_CHECKING:
    from src.core.navigation_view import ProjectLike
    from src.core.scope import Scope

TITLE_PROJECT = "Resumo do projeto"
TITLE_PORTFOLIO = "Resumo do portfólio"

CARTEIRA_TITLE = "Carteira de projetos"
ATTENTION_TITLE = "Pontos de atenção"
MODULES_TITLE = "Módulos"

_HEALTH_TONES: dict[str, Tone] = {"ok": Tone.OK, "warn": Tone.WARN, "erro": Tone.ERROR}

_KPI_TONES: dict[str, Tone] = {
    "ok": Tone.OK,
    "warn": Tone.WARN,
    "erro": Tone.ERROR,
    "info": Tone.INFO,
    "neutro": Tone.NEUTRAL,
}

_LEVEL_TONES: dict[str, Tone] = {"danger": Tone.ERROR, "warning": Tone.WARN}


def build_document(
    *,
    overview: service.HomeOverview,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """O documento do Início no escopo do request; a data de geração vem da rota."""
    tables = [_attention_table(overview), _modules_table(overview)]
    if overview.is_portfolio and overview.portfolio_rows:
        tables.insert(0, _carteira_table(overview))
    return Document(
        title=TITLE_PORTFOLIO if overview.is_portfolio else TITLE_PROJECT,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=overview.is_portfolio,
        context=_context(overview),
        kpis=_kpis(overview),
        tables=tuple(tables),
        paper=Paper.A4,
    )


def _context(overview: service.HomeOverview) -> tuple[tuple[str, str], ...]:
    """As etiquetas da barra de contexto, com o consolidado no Portfólio."""
    context = [
        ("Data de referência", format_value(ValueKind.DATE, overview.reference_date)),
        ("Orçamento", format_value(ValueKind.MONEY, overview.budget_cents)),
    ]
    if overview.expected_end_date is not None:
        context.append(
            ("Término previsto", format_value(ValueKind.DATE, overview.expected_end_date))
        )
    return tuple(context)


def _kpis(overview: service.HomeOverview) -> tuple[Kpi, ...]:
    """Os oito indicadores, com o rótulo do módulo e a referência de gestão no rodapé."""
    return tuple(
        Kpi(
            label=f"{kpi.module_label} · {kpi.label}",
            value=kpi.export_value,
            reference=f"{kpi.reference} · {kpi.footer}" if kpi.footer else kpi.reference,
            kind=kpi.export_kind,
            tone=_KPI_TONES.get(kpi.tone),
            status=kpi.status,
        )
        for kpi in overview.kpis
    )


def _carteira_table(overview: service.HomeOverview) -> Table:
    """A carteira de projetos: peso, BAC, avanço, índices, projeção, término, contagens e situação.

    A linha de fechamento é o rodapé ``Portfólio`` da tela: o peso fecha em
    100,00%, as somas em reais e os índices consolidados do dono.
    """
    totals = overview.portfolio_totals
    return Table(
        title=CARTEIRA_TITLE,
        columns=(
            Column("Projeto", width=30),
            Column("Peso na carteira", ValueKind.PERCENT, digits=2, width=14),
            Column("Orçamento vigente", ValueKind.MONEY, width=16),
            Column("Avanço previsto", ValueKind.PERCENT, digits=1, width=14),
            Column("Avanço real", ValueKind.PERCENT, digits=1, width=14),
            Column("SPI", ValueKind.DECIMAL, digits=2, width=10),
            Column("CPI", ValueKind.DECIMAL, digits=2, width=10),
            Column("Projeção no término", ValueKind.MONEY, width=16),
            Column("VAC", ValueKind.MONEY, width=14),
            Column("Término (linha de base)", ValueKind.DATE, width=14),
            Column("Término (tendência)", ValueKind.DATE, width=14),
            Column("Riscos no topo", ValueKind.INTEGER, width=12),
            Column("Pedidos críticos", ValueKind.INTEGER, width=13),
            Column("Ações atrasadas", ValueKind.INTEGER, width=13),
            Column("Situação", width=12),
        ),
        rows=tuple(
            row(
                f"{item.code} · {item.name}",
                item.weight,
                item.budget_cents,
                item.predicted,
                item.actual,
                item.spi,
                item.cpi,
                item.projection_cents,
                item.vac_cents,
                item.baseline_finish,
                item.trend_finish,
                item.critical_risks,
                item.critical_orders,
                item.overdue_actions,
                Cell(item.health_label, _HEALTH_TONES.get(item.health or "")),
            )
            for item in overview.portfolio_rows
        ),
        totals=None if totals is None else _carteira_totals(totals),
        per_project=False,
    )


def _carteira_totals(totals: service.PortfolioTotals) -> tuple[Cell, ...]:
    """O rodapé da carteira no formato do documento: o peso fecha em 100,00%."""
    return (
        Cell("Portfólio", Tone.NEUTRAL),
        Cell(Decimal(100)),
        Cell(totals.budget_cents),
        Cell(totals.predicted),
        Cell(totals.actual),
        Cell(totals.spi),
        Cell(totals.cpi),
        Cell(totals.projection_cents),
        Cell(totals.vac_cents),
        Cell(totals.baseline_finish),
        Cell(totals.trend_finish),
        Cell(totals.critical_risks),
        Cell(totals.critical_orders),
        Cell(totals.overdue_actions),
        Cell(),
    )


def _attention_table(overview: service.HomeOverview) -> Table:
    """Os pontos de atenção: módulo, nível, título e detalhe."""
    return Table(
        title=ATTENTION_TITLE,
        columns=(
            Column("Módulo", width=28),
            Column("Nível", width=12),
            Column("Ponto de atenção", width=48),
            Column("Detalhe", width=48),
        ),
        rows=tuple(
            row(
                service.MODULE_LABELS.get(attention.module, attention.module),
                "Crítico" if attention.level == "danger" else "Atenção",
                Cell(attention.title, _LEVEL_TONES.get(attention.level)),
                attention.detail,
            )
            for attention in overview.attention
        ),
        per_project=False,
    )


def _modules_table(overview: service.HomeOverview) -> Table:
    """Os cards dos módulos como tabela: título, descrição e selos."""
    return Table(
        title=MODULES_TITLE,
        columns=(
            Column("Módulo", width=28),
            Column("Descrição", width=60),
            Column("Selos", width=28),
        ),
        rows=tuple(
            row(card.title, card.description, "; ".join(badge.text for badge in card.badges))
            for card in overview.cards
        ),
        per_project=False,
    )
