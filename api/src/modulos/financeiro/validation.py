"""Input validation of the Financeiro module (D14).

The server is the only barrier: a screen's own checks are a convenience. A refusal carries one
message per field, keyed by the name of the field in the form, so the form comes back filled
with the messages next to the fields.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from src.core.errors import InvalidDataError
from src.core.money import format_brl
from src.modulos.financeiro import calculations

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


# ── Revisões, remanejamentos e itens da análise (ISSUE-030) ──────────────


FIELD_REALLOCATION_VALUE = "remanejamento_valor"
FIELD_NEW_ITEM_VALUE = "item_novo_valor"
FIELD_REVISION_CHANGE = "mudanca_id"
FIELD_EAC_ITEMS = "itens_eac"

REALLOCATION_OVER_BALANCE = (
    "O remanejamento de {value} supera o saldo livre de {free} do item {code}."
)
NEW_ITEM_OVER_APPROVED_COST = "O item novo de {value} supera o custo aprovado na SM, de {approved}."
REVISION_WITHOUT_APPROVED_CHANGE = (
    "A revisão só entra a partir de uma SM aprovada com custo: escolha a SM que a origina."
)
IMPACT_ITEM_UNKNOWN = "O item {code} não existe na EAC do projeto."
IMPACT_ITEM_NOT_LEAF = (
    "O item {code} não é de nível 3: só os itens de custo entram na análise de impacto."
)


def check_reallocation_balance(*, item_code: str, value_cents: int, free_cents: int) -> None:
    """Remanejamento acima do saldo livre da origem: 422 com a mensagem no valor."""
    if value_cents > free_cents:
        raise InvalidDataError(
            {
                FIELD_REALLOCATION_VALUE: REALLOCATION_OVER_BALANCE.format(
                    code=item_code, value=format_brl(value_cents), free=format_brl(free_cents)
                )
            }
        )


def check_new_item_cost(*, value_cents: int, approved_cents: int) -> None:
    """O item novo não pode superar o custo aprovado na SM que o financia."""
    if value_cents > approved_cents:
        raise InvalidDataError(
            {
                FIELD_NEW_ITEM_VALUE: NEW_ITEM_OVER_APPROVED_COST.format(
                    value=format_brl(value_cents), approved=format_brl(approved_cents)
                )
            }
        )


@dataclass(frozen=True)
class RevisionSource:
    """A SM que a revisão informa: ela precisa estar aprovada e ter custo."""

    change_id: int | None
    approved: bool
    cost_cents: int


def check_revision_source(source: RevisionSource) -> None:
    """Revisão sem SM aprovada com custo é recusada; a linha de base nasce sem mudança."""
    if source.change_id is None or not source.approved or source.cost_cents <= 0:
        raise InvalidDataError({FIELD_REVISION_CHANGE: REVISION_WITHOUT_APPROVED_CHANGE})


def check_impact_item(*, code: str, level: int | None) -> None:
    """Item da análise de impacto: precisa existir na EAC do projeto e ser de nível 3."""
    if level is None:
        raise InvalidDataError({FIELD_EAC_ITEMS: IMPACT_ITEM_UNKNOWN.format(code=code)})
    if level != calculations.LEAF_LEVEL:
        raise InvalidDataError({FIELD_EAC_ITEMS: IMPACT_ITEM_NOT_LEAF.format(code=code)})
