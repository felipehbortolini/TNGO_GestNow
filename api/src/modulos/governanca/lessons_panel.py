"""Os gráficos do painel de lições (ISSUE-028): as mesmas séries da tela e da impressão.

O painel nasce do elemento com ``data-grafico`` e ``data-dados`` que o servidor manda; nenhum
fragmento traz ``<script>``. Os visuais são os da biblioteca do Design System: comparativo de
barras com os dois tipos (a repetir e a evitar), por fase e por área de conhecimento.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.core.export_document import Chart
from src.modulos.governanca.lessons_calculations import LessonGroupLine
from src.modulos.governanca.lessons_service import LessonPanel


def charts_of(panel: LessonPanel) -> tuple[Chart, ...]:
    """Os gráficos do painel, na ordem da tela."""
    return (
        _group_chart("Lições por fase", panel.by_phase),
        _group_chart("Lições por área de conhecimento", panel.by_area),
    )


def _group_chart(title: str, lines: Sequence[LessonGroupLine]) -> Chart:
    categories = [{"id": line.label, "rotulo": line.label, "papel": "neutro"} for line in lines]
    return Chart(
        title,
        "comparativo-barras",
        {
            "titulo": title,
            "paineis": [
                {
                    "titulo": title,
                    "categorias": categories,
                    "linhas": [
                        {
                            "rotulo": "A repetir",
                            "valores": {line.label: line.to_repeat for line in lines},
                        },
                        {
                            "rotulo": "A evitar",
                            "valores": {line.label: line.to_avoid for line in lines},
                        },
                    ],
                }
            ],
        },
    )
