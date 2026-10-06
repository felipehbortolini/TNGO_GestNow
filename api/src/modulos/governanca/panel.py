"""Os gráficos do painel de mudanças (ISSUE-026): as mesmas séries da tela e da impressão.

O painel nasce do elemento com ``data-grafico`` e ``data-dados`` que o servidor manda; nenhum
fragmento traz ``<script>``. Os visuais são os da biblioteca do Design System: comparativo de
barras (situação), Pareto (origem), linhas sem suavização (valor e prazo acumulados) e rosca
(tipo).
"""

from __future__ import annotations

from datetime import date

from src.core.export_document import Chart
from src.modulos.governanca.service import ChangePanel

MONTH_NAMES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def month_label(month: date) -> str:
    """``2026-09`` como ``set/2026``, como o gráfico e a tabela escrevem o mês."""
    return f"{MONTH_NAMES[month.month - 1]}/{month.year}"


def charts_of(panel: ChangePanel) -> tuple[Chart, ...]:
    """Os gráficos do painel, na ordem da tela."""
    return (
        _situation_chart(panel),
        _origin_chart(panel),
        _value_chart(panel),
        _term_chart(panel),
        _kind_chart(panel),
    )


def _situation_chart(panel: ChangePanel) -> Chart:
    title = "Mudanças por situação"
    categories = [
        {"id": line.label, "rotulo": line.label, "papel": "neutro"} for line in panel.situations
    ]
    return Chart(
        title,
        "comparativo-barras",
        {
            "titulo": title,
            "paineis": [
                {
                    "titulo": "Solicitações",
                    "categorias": categories,
                    "linhas": [
                        {
                            "rotulo": "Solicitações",
                            "valores": {line.label: line.total for line in panel.situations},
                        }
                    ],
                }
            ],
        },
    )


def _origin_chart(panel: ChangePanel) -> Chart:
    title = "Pareto por origem"
    return Chart(
        title,
        "pareto",
        {
            "titulo": title,
            "eixo_esquerdo": "Nº de mudanças",
            "eixo_direito": "% acumulado",
            "status": [{"id": "total", "rotulo": "Mudanças", "papel": "neutro"}],
            "categorias": [
                {"rotulo": line.label, "valores": {"total": line.total}} for line in panel.origins
            ],
        },
    )


def _value_chart(panel: ChangePanel) -> Chart:
    title = "Valor aprovado acumulado"
    return Chart(
        title,
        "linhas-multiplas",
        {
            "titulo": title,
            "suavizar": False,
            "series": [{"id": "valor", "rotulo": "Valor aprovado (R$)", "papel": "realizado"}],
            "periodos": [
                {
                    "ano": item.month.year,
                    "mes": item.month.month,
                    "valores": {"valor": item.value_cents / 100},
                }
                for item in panel.months
            ],
        },
    )


def _term_chart(panel: ChangePanel) -> Chart:
    title = "Impacto de prazo acumulado"
    return Chart(
        title,
        "linhas-multiplas",
        {
            "titulo": title,
            "suavizar": False,
            "series": [{"id": "prazo", "rotulo": "Dias acumulados", "papel": "realizado"}],
            "periodos": [
                {
                    "ano": item.month.year,
                    "mes": item.month.month,
                    "valores": {"prazo": item.term_days},
                }
                for item in panel.months
            ],
        },
    )


def _kind_chart(panel: ChangePanel) -> Chart:
    title = "Mudanças por tipo"
    return Chart(
        title,
        "rosca",
        {
            "rotulo_total": "Mudanças",
            "maximo_fatias": 0,
            "fatias": [
                {"id": line.label, "rotulo": line.label, "valor": line.total, "papel": "marca"}
                for line in panel.kinds
            ],
        },
    )
