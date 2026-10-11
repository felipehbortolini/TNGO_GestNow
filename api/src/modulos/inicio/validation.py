"""Validação de entrada do Início (ISSUE-080): os campos do modal da ponderação.

O modal da ponderação envia o peso de cada critério (``peso_<id>``), a nota de
cada projeto por critério de fonte "nota" (``nota_<projetoId>_<critérioId>``) e
a justificativa. As mensagens são as do protótipo e do dono: a soma dos pesos
fora de 100% é recusada com a mensagem de ``configuracoes.validation``, na
fachada. Nada aqui toca banco: recebe o texto digitado e devolve o valor ou a
mensagem.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

JUSTIFICATION_MIN = 10
WEIGHT_MIN = Decimal(0)
WEIGHT_MAX = Decimal(100)

WEIGHT_RANGE_MESSAGE = "Use um peso entre 0 e 100%."

JUSTIFICATION_MESSAGE = "Informe a justificativa da alteração (mínimo de 10 caracteres)."

JUSTIFICATION_FIELD = "justificativa"

_WEIGHT_PREFIX = "peso_"
_GRADE_PREFIX = "nota_"


def weight_field(criterion_id: str) -> str:
    """``peso_valor``: o nome do campo do peso de um critério no formulário."""
    return f"{_WEIGHT_PREFIX}{criterion_id}"


def grade_field(project_id: int, criterion_id: str) -> str:
    """``nota_12_estrategico``: o nome do campo da nota de um projeto por critério."""
    return f"{_GRADE_PREFIX}{project_id}_{criterion_id}"


def grade_message(minimum: int, maximum: int) -> str:
    """``Nota inteira de 1 a 5.``: a mensagem da nota fora da faixa (protótipo)."""
    return f"Nota inteira de {minimum} a {maximum}."


def parse_weight(raw: Any) -> Decimal | None:
    """O peso digitado como número; vazio, texto ou infinito devolve ``None``."""
    text = str(raw or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def parse_grade(raw: Any) -> int | None:
    """A nota digitada como inteiro; fração, texto ou vazio devolve ``None``."""
    value = parse_weight(raw)
    if value is None or value != value.to_integral_value():
        return None
    return int(value)


def justification_error(justification: str) -> str | None:
    """A justificativa obrigatória, com o mínimo do dono; ``None`` quando passa."""
    return (
        None if len((justification or "").strip()) >= JUSTIFICATION_MIN else JUSTIFICATION_MESSAGE
    )


@dataclass(frozen=True)
class PonderationForm:
    """O que o modal da ponderação enviou: pesos, notas e justificativa por texto digitado."""

    weights: Mapping[str, str]
    grades: Mapping[int, Mapping[str, str]]
    justification: str = ""

    @property
    def values(self) -> dict[str, str]:
        """Todos os campos digitados pelo nome do formulário, como a tela os redesenha."""
        values = {weight_field(criterion_id): text for criterion_id, text in self.weights.items()}
        for project_id, criteria in self.grades.items():
            for criterion_id, text in criteria.items():
                values[grade_field(project_id, criterion_id)] = text
        values[JUSTIFICATION_FIELD] = self.justification
        return values


def read_form(form: Mapping[str, str]) -> PonderationForm:
    """Lê o formulário do modal: ``peso_<id>``, ``nota_<projetoId>_<critérioId>`` e a justificativa."""
    weights: dict[str, str] = {}
    grades: dict[int, dict[str, str]] = {}
    for field, text in form.items():
        if field.startswith(_WEIGHT_PREFIX):
            weights[field[len(_WEIGHT_PREFIX) :]] = text
        elif field.startswith(_GRADE_PREFIX):
            project_text, _, criterion_id = field[len(_GRADE_PREFIX) :].partition("_")
            if project_text.isdecimal() and criterion_id:
                grades.setdefault(int(project_text), {})[criterion_id] = text
    return PonderationForm(
        weights=weights, grades=grades, justification=form.get(JUSTIFICATION_FIELD, "")
    )
