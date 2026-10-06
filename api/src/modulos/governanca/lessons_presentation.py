"""How the lessons screens and exports write what the facade hands them (D12, ISSUE-027).

The tone of each situation and type, and the texts of the impact and of the line over the acervo, live
here once: the fragments (Jinja) and the export read the same functions, so the screen, the paper and
the spreadsheet agree.
"""

from __future__ import annotations

from src.core.export_document import Tone
from src.core.money import format_brl
from src.modulos.governanca import lessons_models as lm
from src.modulos.governanca.presentation import PILL_BY_TONE, plural

SITUATION_TONES: dict[str, Tone] = {
    lm.SITUATION_DRAFT: Tone.NEUTRAL,
    lm.SITUATION_VALIDATING: Tone.WARN,
    lm.SITUATION_VALIDATED: Tone.INFO,
    lm.SITUATION_PUBLISHED: Tone.OK,
}
KIND_TONES: dict[str, Tone] = {"A repetir": Tone.OK, "A evitar": Tone.WARN}


def situation_tone(situation: str) -> Tone:
    """The tone of a situation of the flow; an unknown one reads as neutral."""
    return SITUATION_TONES.get(situation, Tone.NEUTRAL)


def situation_pill(situation: str) -> str:
    """The pill class of a situation of the flow."""
    return PILL_BY_TONE[situation_tone(situation)]


def kind_pill(kind: str) -> str:
    """The pill class of the type: to repeat is good news, to avoid is a warning."""
    return PILL_BY_TONE[KIND_TONES.get(kind, Tone.NEUTRAL)]


def impact_text(term_days: int, cost_cents: int) -> str:
    """The impact of the lesson: ``21 dias · R$ 400.000,00``."""
    return f"{plural(term_days, 'dia')} · {format_brl(cost_cents)}"


def scope_line(*, is_portfolio: bool, project_code: str, own: int, corporate: int) -> str:
    """The line over the acervo: whose lessons these are and how many are shared with the organization."""
    whose = "Acervo do portfólio" if is_portfolio else f"Acervo do projeto {project_code}"
    shared = plural(corporate, "corporativa", "corporativas")
    return (
        f"{whose}: {plural(own, 'lição', 'lições')} ({shared}, compartilhadas com a organização)."
    )
