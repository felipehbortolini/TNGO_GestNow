"""Exportação do Início (ISSUE-079, D12): um documento, o Excel e a folha imprimível.

O documento do resumo leva o que a tela mostra: os oito indicadores-chave com a
referência de gestão, os pontos de atenção e os cards dos módulos como tabela.
Os dois formatos saem daqui (``core.excel`` e ``core.printable``), então nada
que a tela mostra falta em um deles. Como os títulos dos pontos de atenção já
trazem o código do projeto no Portfólio, as tabelas não pedem a coluna
``Projeto`` automática (``per_project=False``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
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

ATTENTION_TITLE = "Pontos de atenção"
MODULES_TITLE = "Módulos"

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
    return Document(
        title=TITLE_PORTFOLIO if overview.is_portfolio else TITLE_PROJECT,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=overview.is_portfolio,
        context=_context(overview),
        kpis=_kpis(overview),
        tables=(_attention_table(overview), _modules_table(overview)),
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
