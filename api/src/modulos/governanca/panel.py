"""Os gráficos do painel de mudanças (ISSUE-026): as mesmas séries da tela e da impressão.

O painel nasce do elemento com ``data-grafico`` e ``data-dados`` que o servidor manda; nenhum
fragmento traz ``<script>``. Os visuais são os da biblioteca do Design System: comparativo de
barras (situação), Pareto (origem), linhas sem suavização (valor e prazo acumulados) e rosca
(tipo).
"""

from __future__ import annotations

from datetime import date

from src.core import translations
from src.core.export_document import Chart
from src.modulos.governanca.service import ChangePanel


def _label(text: str, idioma: str) -> str:
    """O texto de interface da Governança no idioma do request (D13)."""
    return translations.translate("governanca", text, idioma)


def month_label(month: date, idioma: str = "pt") -> str:
    """``2026-09`` como ``set/2026``, como o gráfico e a tabela escrevem o mês."""
    return f"{translations.mes_curto(month.month, idioma)}/{month.year}"


def charts_of(panel: ChangePanel, idioma: str = "pt") -> tuple[Chart, ...]:
    """Os gráficos do painel, na ordem da tela."""
    return (
        _situation_chart(panel, idioma),
        _origin_chart(panel, idioma),
        _value_chart(panel, idioma),
        _term_chart(panel, idioma),
        _kind_chart(panel, idioma),
    )


def _rotulos(idioma: str) -> dict[str, str]:
    return translations.rotulos_de_grafico(idioma)


def _situation_chart(panel: ChangePanel, idioma: str) -> Chart:
    title = _label("Mudanças por situação", idioma)
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
                    "titulo": _label("Solicitações", idioma),
                    "categorias": categories,
                    "linhas": [
                        {
                            "rotulo": _label("Solicitações", idioma),
                            "valores": {line.label: line.total for line in panel.situations},
                        }
                    ],
                }
            ],
            "rotulos": _rotulos(idioma),
        },
    )


def _origin_chart(panel: ChangePanel, idioma: str) -> Chart:
    title = _label("Pareto por origem", idioma)
    return Chart(
        title,
        "pareto",
        {
            "titulo": title,
            "eixo_esquerdo": _label("Nº de mudanças", idioma),
            "eixo_direito": _label("% acumulado", idioma),
            "status": [{"id": "total", "rotulo": _label("Mudanças", idioma), "papel": "neutro"}],
            "categorias": [
                {"rotulo": line.label, "valores": {"total": line.total}} for line in panel.origins
            ],
            "rotulos": _rotulos(idioma),
        },
    )


def _value_chart(panel: ChangePanel, idioma: str) -> Chart:
    title = _label("Valor aprovado acumulado", idioma)
    return Chart(
        title,
        "linhas-multiplas",
        {
            "titulo": title,
            "suavizar": False,
            "series": [
                {
                    "id": "valor",
                    "rotulo": _label("Valor aprovado (R$)", idioma),
                    "papel": "realizado",
                }
            ],
            "periodos": [
                {
                    "ano": item.month.year,
                    "mes": item.month.month,
                    "valores": {"valor": item.value_cents / 100},
                }
                for item in panel.months
            ],
            "rotulos": _rotulos(idioma),
        },
    )


def _term_chart(panel: ChangePanel, idioma: str) -> Chart:
    title = _label("Impacto de prazo acumulado", idioma)
    return Chart(
        title,
        "linhas-multiplas",
        {
            "titulo": title,
            "suavizar": False,
            "series": [
                {"id": "prazo", "rotulo": _label("Dias acumulados", idioma), "papel": "realizado"}
            ],
            "periodos": [
                {
                    "ano": item.month.year,
                    "mes": item.month.month,
                    "valores": {"prazo": item.term_days},
                }
                for item in panel.months
            ],
            "rotulos": _rotulos(idioma),
        },
    )


def _kind_chart(panel: ChangePanel, idioma: str) -> Chart:
    title = _label("Mudanças por tipo", idioma)
    return Chart(
        title,
        "rosca",
        {
            "rotulo_total": _label("Mudanças", idioma),
            "maximo_fatias": 0,
            "fatias": [
                {"id": line.label, "rotulo": line.label, "valor": line.total, "papel": "marca"}
                for line in panel.kinds
            ],
            "rotulos": _rotulos(idioma),
        },
    )
