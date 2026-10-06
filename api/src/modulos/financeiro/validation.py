"""Input validation of the Financeiro module (D14).

The server is the only barrier: a screen's own checks are a convenience. A refusal carries one
message per field, keyed by the name of the field in the form, so the form comes back filled
with the messages next to the fields.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from src.core.errors import InvalidDataError

COST_TYPES = ("Material", "Mão de obra", "Equipamento", "Serviço", "Indireto", "Contingência")
CLASSIFICATIONS = ("CAPEX", "OPEX")

DESCRIPTION_MIN = 3
DESCRIPTION_MAX = 120
COST_CENTER_MAX = 20
JUSTIFICATION_MIN = 10
JUSTIFICATION_MAX = 300

FIELD_DESCRIPTION = "descricao"
FIELD_COST_TYPE = "tipo_custo"
FIELD_CLASSIFICATION = "classificacao"
FIELD_COST_CENTER = "centro_custo"
FIELD_RESPONSIBLE = "responsavel"
FIELD_JUSTIFICATION = "justificativa"
FIELD_VERSION = "versao"


@dataclass(frozen=True)
class RegistryEdit:
    """The cadastral data of an item as the person sent it, already checked.

    None of these fields changes a value of the budget (the quantity, the unit price and the
    structure belong to ISSUE-030), so the change needs no SM, only the justification.
    """

    description: str
    cost_type: str
    capex: bool
    cost_center: str
    responsible_id: int
    justification: str


def parse_registry_edit(
    form: Mapping[str, str | None], *, responsible_ids: Collection[int]
) -> RegistryEdit:
    """Check the cadastral edit of an item; refuse with 422, one message per field."""
    description = _text(form, FIELD_DESCRIPTION)
    cost_type = _text(form, FIELD_COST_TYPE)
    classification = _text(form, FIELD_CLASSIFICATION)
    cost_center = _text(form, FIELD_COST_CENTER)
    justification = _text(form, FIELD_JUSTIFICATION)
    responsible_id = _responsible(form, responsible_ids)
    errors = {
        FIELD_DESCRIPTION: _length_error(
            description, DESCRIPTION_MIN, DESCRIPTION_MAX, "Informe a descrição"
        ),
        FIELD_COST_TYPE: "" if cost_type in COST_TYPES else "Escolha o tipo de custo.",
        FIELD_CLASSIFICATION: ""
        if classification in CLASSIFICATIONS
        else "Escolha a classificação: CAPEX ou OPEX.",
        FIELD_COST_CENTER: ""
        if len(cost_center) <= COST_CENTER_MAX
        else f"O centro de custo aceita até {COST_CENTER_MAX} caracteres.",
        FIELD_RESPONSIBLE: "" if responsible_id is not None else "Escolha o responsável.",
        FIELD_JUSTIFICATION: _length_error(
            justification,
            JUSTIFICATION_MIN,
            JUSTIFICATION_MAX,
            "Informe a justificativa da alteração",
        ),
    }
    problems = {field: message for field, message in errors.items() if message}
    if problems or responsible_id is None:
        raise InvalidDataError(problems)
    return RegistryEdit(
        description=description,
        cost_type=cost_type,
        capex=classification == "CAPEX",
        cost_center=cost_center,
        responsible_id=responsible_id,
        justification=justification,
    )


def _text(form: Mapping[str, str | None], field: str) -> str:
    return (form.get(field) or "").strip()


def _responsible(form: Mapping[str, str | None], responsible_ids: Collection[int]) -> int | None:
    raw = _text(form, FIELD_RESPONSIBLE)
    if not raw.isdigit():
        return None
    identifier = int(raw)
    return identifier if identifier in responsible_ids else None


def _length_error(text: str, minimum: int, maximum: int, ask: str) -> str:
    if len(text) < minimum:
        return f"{ask} (mínimo de {minimum} caracteres)."
    if len(text) > maximum:
        return f"Use até {maximum} caracteres."
    return ""
