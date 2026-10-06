"""Documentos de exportação de teste: o que uma tela de módulo entregaria ao Excel e à folha.

Os testes do Excel, da versão imprimível e das rotas partem do mesmo documento, com
os dois projetos do Portfólio, os cinco tipos de valor, um tom em cada situação, uma
linha de totais, uma tabela que não é por projeto (a legenda) e um gráfico.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.core.export_document import (
    Cell,
    Chart,
    Column,
    Document,
    Kpi,
    Paper,
    Row,
    Table,
    Tone,
    ValueKind,
    row,
)

HOJE = date(2026, 10, 5)
FABRICA = "TN-001 · Fábrica"
CALDEIRA = "TN-002 · Caldeira"

COLUNAS = (
    Column("Atividade", width=34),
    Column("Início", ValueKind.DATE),
    Column("Quantidade", ValueKind.INTEGER),
    Column("Avanço", ValueKind.PERCENT, digits=1),
    Column("Valor", ValueKind.MONEY),
    Column("Situação"),
)

INDICADORES = (
    Kpi(
        "Avanço",
        Decimal("87.5"),
        "Meta: 90%",
        ValueKind.PERCENT,
        digits=1,
        tone=Tone.WARN,
        status="Atenção",
    ),
    Kpi(
        "Desembolso",
        125_000_000,
        "Orçado: R$ 1.500.000,00",
        ValueKind.MONEY,
        tone=Tone.OK,
        status="Dentro do orçado",
    ),
    Kpi("Concluídas", 18, "Previsto: 20", ValueKind.INTEGER),
    Kpi(
        "Próximo marco",
        date(2026, 10, 19),
        "Data prevista",
        ValueKind.DATE,
        tone=Tone.INFO,
        status="Futuro",
    ),
)

# O contrato do gráfico: ``app/ds/graficos/comparativo-barras.js``.
GRAFICO = Chart(
    title="Linha de base x Atual",
    kind="comparativo-barras",
    data={
        "titulo": "Linha de base x Atual",
        "paineis": [
            {
                "titulo": "Atividades por situação",
                "categorias": [
                    {"id": "no_prazo", "rotulo": "No prazo", "papel": "ok", "favoravel": "sobe"},
                    {
                        "id": "atrasadas",
                        "rotulo": "Atrasadas",
                        "papel": "erro",
                        "favoravel": "desce",
                    },
                ],
                "linhas": [
                    {"rotulo": "Linha de base", "valores": {"no_prazo": 24, "atrasadas": 0}},
                    {"rotulo": "Atual", "valores": {"no_prazo": 20, "atrasadas": 3}},
                ],
            }
        ],
    },
)


def linhas() -> tuple[Row, ...]:
    """Três atividades: duas na fábrica e uma na caldeira, cada uma com o seu tom."""
    return (
        row(
            "Concretagem",
            date(2026, 9, 5),
            120,
            Decimal(100),
            45_000_000,
            Cell("No prazo", Tone.OK),
            project=FABRICA,
        ),
        row(
            "Montagem",
            date(2026, 9, 25),
            80,
            Decimal("62.5"),
            27_500_000,
            Cell("Atenção", Tone.WARN),
            project=FABRICA,
        ),
        row(
            "Testes",
            date(2026, 10, 10),
            40,
            Decimal(10),
            10_000_000,
            Cell("Atrasada", Tone.ERROR),
            project=CALDEIRA,
        ),
    )


def tabela_de_atividades() -> Table:
    """A tabela por projeto, com a linha de totais."""
    return Table(
        title="Atividades",
        columns=COLUNAS,
        rows=linhas(),
        totals=(Cell("Total"), Cell(), Cell(240), Cell(), Cell(82_500_000), Cell()),
    )


def legenda() -> Table:
    """A tabela que não é por projeto: o Portfólio não lhe dá a coluna Projeto."""
    return Table(
        title="Legenda",
        columns=(Column("Situação"), Column("Significado")),
        rows=(row("No prazo", "Dentro do previsto"), row("Atrasada", "Passou do previsto")),
        per_project=False,
    )


def documento(
    *,
    portfolio: bool = True,
    paper: Paper = Paper.A4,
    kpis: tuple[Kpi, ...] = INDICADORES,
    tables: tuple[Table, ...] | None = None,
    charts: tuple[Chart, ...] = (),
) -> Document:
    """O documento de teste: no Portfólio ou na fábrica, em A4 ou A3."""
    return Document(
        title="Mapa de controle",
        scope_label="Portfólio" if portfolio else FABRICA,
        generated_on=HOJE,
        portfolio=portfolio,
        context=(("Período", "S40/2026"),),
        kpis=kpis,
        charts=charts,
        tables=(tabela_de_atividades(), legenda()) if tables is None else tables,
        paper=paper,
    )
