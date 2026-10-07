"""Input validation of the Financeiro module (D14).

The server is the only barrier: a screen's own checks are a convenience. A refusal carries one
message per field, keyed by the name of the field in the form, so the form comes back filled
with the messages next to the fields.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.core.errors import InvalidDataError
from src.core.export_document import ValueKind
from src.core.import_values import convert, normalize_text
from src.core.money import format_brl
from src.core.spreadsheet_reader import RawCell
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
FIELD_REVISION_JUSTIFICATION = "justificativa"
FIELD_REVISION_ITEMS = "itens"
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


# ── Formulários das rotas da ISSUE-030 ───────────────────────────────────


FIELD_REALLOCATION_ORIGIN = "origem"
FIELD_REALLOCATION_TARGET = "destino"
FIELD_REALLOCATION_AMOUNT = "valor"
FIELD_REALLOCATION_TITLE = "titulo"
FIELD_REALLOCATION_PRIORITY = "prioridade"
FIELD_REVISION_ITEM = "item"
FIELD_NEW_ITEM_CODE = "codigo"
FIELD_NEW_ITEM_PARENT = "pai"
FIELD_NEW_ITEM_UNIT = "unidade"
FIELD_NEW_ITEM_QUANTITY = "quantidade"
FIELD_NEW_ITEM_PRICE = "preco"
FIELD_NEW_ITEM_RECOURSE = "recurso"
FIELD_IMPORT_CHECKED = "conferido"
FIELD_IMPORT_ACKNOWLEDGED = "ciente"

RECOURSE_REALLOCATION = "remanejamento"
RECOURSE_REVISION = "revisao"
RECOURSES = (RECOURSE_REALLOCATION, RECOURSE_REVISION)
PRIORITIES = ("Normal", "Urgente")
IMPORT_ACKNOWLEDGED_VALUE = "sim"
DEFAULT_PRIORITY = "Normal"

REALLOCATION_ORIGIN_MESSAGE = "Informe o item de origem."
REALLOCATION_TARGET_MESSAGE = "Informe o item de destino."
REALLOCATION_AMOUNT_MESSAGE = "Informe um valor maior que zero."
REALLOCATION_PRIORITY_MESSAGE = "Escolha a prioridade: Normal ou Urgente."
REALLOCATION_JUSTIFICATION_ASK = "Informe a justificativa do remanejamento"
REVISION_CHANGE_MESSAGE = "Escolha a SM aprovada que origina a revisão."
REVISION_ITEM_MESSAGE = "Escolha o item de custo que recebe o valor."
REVISION_AMOUNT_MESSAGE = "Informe um valor maior que zero."
REVISION_JUSTIFICATION_ASK = "Informe a justificativa da revisão"
RECOURSE_MESSAGE = "Escolha a origem do recurso: remanejamento ou nova revisão."
NEW_ITEM_CODE_MESSAGE = "Informe o código do item, com três níveis (ex.: 3.2.5)."
NEW_ITEM_PARENT_MESSAGE = "O subpacote {code} não existe na EAC do projeto."
NEW_ITEM_UNIT_MESSAGE = "A unidade {code} não está no cadastro."
NEW_ITEM_QUANTITY_MESSAGE = "Informe uma quantidade maior que zero."
NEW_ITEM_PRICE_MESSAGE = "Informe um preço unitário maior que zero."
NEW_ITEM_RESPONSIBLE_MESSAGE = "O responsável {name} não está no cadastro."


def parse_money(text: str) -> int | None:
    """Cents of a value written in reais (``1.234,56``), or ``None`` when it is not one."""
    if not text.strip():
        return None
    converted = convert(RawCell(value=text), ValueKind.MONEY)
    return converted.value if converted.problem is None else None


def parse_quantity(text: str) -> Decimal | None:
    """The number of a quantity written by a person, or ``None`` when it is not one."""
    if not text.strip():
        return None
    converted = convert(RawCell(value=text), ValueKind.DECIMAL)
    return converted.value if converted.problem is None else None


@dataclass(frozen=True)
class NewItemInput:
    """O item novo de um formulário: os atributos cadastrais e o valor orçado calculado."""

    code: str
    description: str
    parent_code: str
    cost_type: str
    unit_code: str
    quantity: Decimal
    unit_price_cents: int
    capex: bool
    cost_center: str
    responsible_name: str

    @property
    def budget_cents(self) -> int:
        """Valor orçado do item novo: quantidade x preço unitário, em centavos."""
        return calculations.budgeted_cents(self.quantity, self.unit_price_cents)


@dataclass(frozen=True)
class ReallocationForm:
    """O remanejamento pedido pela tela: a transferência, a justificativa e a prioridade."""

    title: str
    justification: str
    priority: str
    origin_code: str
    target_code: str
    value_cents: int


@dataclass(frozen=True)
class NewItemForm:
    """O item novo pedido pela tela: por remanejamento de outro item ou por nova revisão."""

    item: NewItemInput
    recourse: str
    origin_code: str
    change_id: int | None
    justification: str
    priority: str


@dataclass(frozen=True)
class RevisionForm:
    """A revisão pedida pela tela: a SM aprovada, a justificativa e o ajuste que ela incorpora."""

    change_id: int
    justification: str
    item_code: str
    delta_cents: int


def parse_reallocation_form(form: Mapping[str, str | None]) -> ReallocationForm:
    """Check the remanejamento form; refuse with 422, one message per field."""
    origin = _text(form, FIELD_REALLOCATION_ORIGIN)
    target = _text(form, FIELD_REALLOCATION_TARGET)
    value = parse_money(_text(form, FIELD_REALLOCATION_AMOUNT))
    justification = _text(form, FIELD_JUSTIFICATION)
    priority = _text(form, FIELD_REALLOCATION_PRIORITY) or DEFAULT_PRIORITY
    _refuse(
        {
            FIELD_REALLOCATION_ORIGIN: "" if origin else REALLOCATION_ORIGIN_MESSAGE,
            FIELD_REALLOCATION_TARGET: "" if target else REALLOCATION_TARGET_MESSAGE,
            FIELD_REALLOCATION_AMOUNT: "" if value and value > 0 else REALLOCATION_AMOUNT_MESSAGE,
            FIELD_REALLOCATION_PRIORITY: ""
            if priority in PRIORITIES
            else REALLOCATION_PRIORITY_MESSAGE,
            FIELD_JUSTIFICATION: _length_error(
                justification,
                JUSTIFICATION_MIN,
                JUSTIFICATION_MAX,
                REALLOCATION_JUSTIFICATION_ASK,
            ),
        }
    )
    return ReallocationForm(
        title=_text(form, FIELD_REALLOCATION_TITLE),
        justification=justification,
        priority=priority,
        origin_code=origin,
        target_code=target,
        value_cents=value or 0,
    )


def parse_new_item_form(
    form: Mapping[str, str | None],
    *,
    parent_codes: Collection[str],
    unit_codes: Collection[str],
    responsible_names: Collection[str],
) -> NewItemForm:
    """Check the new item form; the recourse says whether it is a remanejamento or a revisão."""
    item = _parse_new_item(
        form,
        parent_codes=parent_codes,
        unit_codes=unit_codes,
        responsible_names=responsible_names,
    )
    recourse = _text(form, FIELD_NEW_ITEM_RECOURSE) or RECOURSE_REALLOCATION
    justification = _text(form, FIELD_JUSTIFICATION)
    origin = _text(form, FIELD_REALLOCATION_ORIGIN)
    change_id = _digit(_text(form, FIELD_REVISION_CHANGE))
    priority = _text(form, FIELD_REALLOCATION_PRIORITY) or DEFAULT_PRIORITY
    _refuse(
        {
            FIELD_NEW_ITEM_RECOURSE: "" if recourse in RECOURSES else RECOURSE_MESSAGE,
            FIELD_REALLOCATION_ORIGIN: (
                "" if recourse == RECOURSE_REVISION or origin else REALLOCATION_ORIGIN_MESSAGE
            ),
            FIELD_REVISION_CHANGE: (
                "" if recourse == RECOURSE_REALLOCATION or change_id else REVISION_CHANGE_MESSAGE
            ),
            FIELD_REALLOCATION_PRIORITY: ""
            if priority in PRIORITIES
            else REALLOCATION_PRIORITY_MESSAGE,
            FIELD_JUSTIFICATION: _length_error(
                justification,
                JUSTIFICATION_MIN,
                JUSTIFICATION_MAX,
                REALLOCATION_JUSTIFICATION_ASK,
            ),
        }
    )
    return NewItemForm(
        item=item,
        recourse=recourse,
        origin_code=origin,
        change_id=change_id,
        justification=justification,
        priority=priority,
    )


def parse_revision_form(
    form: Mapping[str, str | None], *, require_adjustment: bool = True
) -> RevisionForm:
    """Check the revision form; the import confirmation carries only the SM and the justification."""
    change_id = _digit(_text(form, FIELD_REVISION_CHANGE))
    justification = _text(form, FIELD_JUSTIFICATION)
    item_code = _text(form, FIELD_REVISION_ITEM) if require_adjustment else ""
    delta = parse_money(_text(form, FIELD_REALLOCATION_AMOUNT)) if require_adjustment else 0
    _refuse(
        {
            FIELD_REVISION_CHANGE: "" if change_id else REVISION_CHANGE_MESSAGE,
            FIELD_REVISION_ITEM: (
                "" if not require_adjustment or _is_leaf_code(item_code) else REVISION_ITEM_MESSAGE
            ),
            FIELD_REALLOCATION_AMOUNT: (
                "" if not require_adjustment or (delta and delta > 0) else REVISION_AMOUNT_MESSAGE
            ),
            FIELD_JUSTIFICATION: _length_error(
                justification,
                JUSTIFICATION_MIN,
                JUSTIFICATION_MAX,
                REVISION_JUSTIFICATION_ASK,
            ),
        }
    )
    return RevisionForm(
        change_id=change_id or 0,
        justification=justification,
        item_code=item_code,
        delta_cents=delta or 0,
    )


def _parse_new_item(
    form: Mapping[str, str | None],
    *,
    parent_codes: Collection[str],
    unit_codes: Collection[str],
    responsible_names: Collection[str],
) -> NewItemInput:
    code = _text(form, FIELD_NEW_ITEM_CODE)
    description = _text(form, FIELD_DESCRIPTION)
    parent = _text(form, FIELD_NEW_ITEM_PARENT)
    cost_type = _text(form, FIELD_COST_TYPE)
    unit = _text(form, FIELD_NEW_ITEM_UNIT)
    quantity = parse_quantity(_text(form, FIELD_NEW_ITEM_QUANTITY))
    price = parse_money(_text(form, FIELD_NEW_ITEM_PRICE))
    classification = _text(form, FIELD_CLASSIFICATION)
    cost_center = _text(form, FIELD_COST_CENTER)
    responsible = _text(form, FIELD_RESPONSIBLE)
    _refuse(
        {
            FIELD_NEW_ITEM_CODE: "" if _is_leaf_code(code) else NEW_ITEM_CODE_MESSAGE,
            FIELD_DESCRIPTION: _length_error(
                description, DESCRIPTION_MIN, DESCRIPTION_MAX, "Informe a descrição"
            ),
            FIELD_NEW_ITEM_PARENT: (
                "" if parent in parent_codes else NEW_ITEM_PARENT_MESSAGE.format(code=parent)
            ),
            FIELD_COST_TYPE: "" if cost_type in COST_TYPES else "Escolha o tipo de custo.",
            FIELD_NEW_ITEM_UNIT: (
                "" if _matches(unit, unit_codes) else NEW_ITEM_UNIT_MESSAGE.format(code=unit)
            ),
            FIELD_NEW_ITEM_QUANTITY: (
                "" if quantity is not None and quantity > 0 else NEW_ITEM_QUANTITY_MESSAGE
            ),
            FIELD_NEW_ITEM_PRICE: "" if price and price > 0 else NEW_ITEM_PRICE_MESSAGE,
            FIELD_CLASSIFICATION: (
                ""
                if classification in CLASSIFICATIONS
                else "Escolha a classificação: CAPEX ou OPEX."
            ),
            FIELD_COST_CENTER: (
                ""
                if len(cost_center) <= COST_CENTER_MAX
                else f"O centro de custo aceita até {COST_CENTER_MAX} caracteres."
            ),
            FIELD_RESPONSIBLE: (
                ""
                if _matches(responsible, responsible_names)
                else NEW_ITEM_RESPONSIBLE_MESSAGE.format(name=responsible)
            ),
        }
    )
    return NewItemInput(
        code=code,
        description=description,
        parent_code=parent,
        cost_type=cost_type,
        unit_code=unit,
        quantity=quantity or Decimal(0),
        unit_price_cents=price or 0,
        capex=classification == "CAPEX",
        cost_center=cost_center,
        responsible_name=responsible,
    )


def _refuse(problems: Mapping[str, str]) -> None:
    found = {field: message for field, message in problems.items() if message}
    if found:
        raise InvalidDataError(found)


def _digit(text: str) -> int | None:
    return int(text) if text.isdigit() else None


def _is_leaf_code(code: str) -> bool:
    parts = code.split(".")
    return len(parts) == 3 and all(part.isdigit() for part in parts)


def _matches(text: str, options: Collection[str]) -> bool:
    wanted = normalize_text(text)
    return any(normalize_text(option) == wanted for option in options)


# ── Projeção no término e custos do ERP (ISSUE-031) ──────────────────────


FIELD_PROJECTION = "projecao"
FIELD_ERP_ITEM = "item"
FIELD_ERP_MONTH = "mes"
FIELD_ERP_COMMITTED = "comprometido"
FIELD_ERP_ACTUAL = "realizado"
FIELD_ERP_PROJECTION = "projecao"
FIELD_ERP_VALUES = "valores"

PROJECTION_REQUIRED = "Informe a projeção no término."
PROJECTION_NEGATIVE = "A projeção no término não pode ser negativa."
PROJECTION_BELOW_ACTUAL = "A projeção no término não pode ser menor que o realizado."
PROJECTION_JUSTIFICATION_ASK = "Informe a justificativa da projeção."
ERP_ITEM_UNKNOWN = "O item {code} não existe na EAC do projeto."
ERP_ITEM_NOT_LEAF = "O item {code} não é item de custo (nível 3) da EAC do projeto."
ERP_MONTH_REQUIRED = "Informe o mês (AAAA-MM)."
ERP_MONTH_IN_THE_FUTURE = "Não é possível importar um mês futuro em relação à data de referência."
ERP_VALUE_NEGATIVE = "O valor não pode ser negativo."
ERP_VALUES_REQUIRED = "Preencha ao menos um valor: comprometido, realizado ou projeção."


@dataclass(frozen=True)
class ProjectionForm:
    """A projeção pedida pela tela: o valor no término e a justificativa do responsável."""

    value_cents: int
    justification: str


def parse_projection_form(
    form: Mapping[str, str | None], *, actual_cents: int | None = None
) -> ProjectionForm:
    """Check the projection form; refused with 422, the message next to the field.

    The prototype asks a filled justification (up to 300 characters, no character minimum) and
    refuses a projection that is negative or below the realized cost of the item.
    """
    value = parse_money(_text(form, FIELD_PROJECTION))
    justification = _text(form, FIELD_JUSTIFICATION)
    _refuse(
        {
            FIELD_PROJECTION: _projection_problem(value, actual_cents),
            FIELD_JUSTIFICATION: _projection_justification_problem(justification),
        }
    )
    return ProjectionForm(value_cents=value or 0, justification=justification)


def _projection_problem(value: int | None, actual_cents: int | None) -> str:
    if value is None:
        return PROJECTION_REQUIRED
    if value < 0:
        return PROJECTION_NEGATIVE
    if actual_cents is not None and value < actual_cents:
        return PROJECTION_BELOW_ACTUAL
    return ""


def _projection_justification_problem(justification: str) -> str:
    if not justification:
        return PROJECTION_JUSTIFICATION_ASK
    if len(justification) > JUSTIFICATION_MAX:
        return f"Use até {JUSTIFICATION_MAX} caracteres."
    return ""


@dataclass(frozen=True)
class ErpCostInput:
    """One line of the ERP import: the item, the month and the three closing values, in cents."""

    code: str
    month: date | None
    committed_cents: int | None
    actual_cents: int | None
    projection_cents: int | None


def erp_cost_problems(
    line: ErpCostInput,
    *,
    item_levels: Mapping[str, int],
    reference_date: date,
    current_projection_cents: int | None = None,
) -> dict[str, str]:
    """The messages of one ERP line by field: the item, the month and the three values.

    The item must exist in the EAC of the project and be a cost item (level 3); the month cannot
    be in the future; no value is negative; at least one of the three is filled. The projection,
    the line's own or the vigente that the line omits, cannot be below the realized of the line
    (the rule of the prototype).
    """
    projection = (
        line.projection_cents if line.projection_cents is not None else current_projection_cents
    )
    problems = {
        FIELD_ERP_ITEM: _erp_item_problem(line.code, item_levels.get(line.code)),
        FIELD_ERP_MONTH: _erp_month_problem(line.month, reference_date),
        FIELD_ERP_COMMITTED: _erp_value_problem(line.committed_cents),
        FIELD_ERP_ACTUAL: _erp_value_problem(line.actual_cents),
        FIELD_ERP_PROJECTION: _erp_value_problem(line.projection_cents),
    }
    if all(
        value is None for value in (line.committed_cents, line.actual_cents, line.projection_cents)
    ):
        problems[FIELD_ERP_VALUES] = ERP_VALUES_REQUIRED
    elif (
        line.actual_cents is not None
        and projection is not None
        and projection < line.actual_cents
        and not problems[FIELD_ERP_PROJECTION]
    ):
        problems[FIELD_ERP_PROJECTION] = PROJECTION_BELOW_ACTUAL
    return {field: message for field, message in problems.items() if message}


def _erp_item_problem(code: str, level: int | None) -> str:
    if level is None:
        return ERP_ITEM_UNKNOWN.format(code=code)
    if level != calculations.LEAF_LEVEL:
        return ERP_ITEM_NOT_LEAF.format(code=code)
    return ""


def _erp_month_problem(month: date | None, reference_date: date) -> str:
    if month is None:
        return ERP_MONTH_REQUIRED
    if (month.year, month.month) > (reference_date.year, reference_date.month):
        return ERP_MONTH_IN_THE_FUTURE
    return ""


def _erp_value_problem(value: int | None) -> str:
    return ERP_VALUE_NEGATIVE if value is not None and value < 0 else ""


# ── Medições e aditivos do contrato (ISSUE-032) ──────────────────────────


MEASUREMENT_TRANSITIONS: Mapping[str, tuple[str, ...]] = {
    calculations.SITUATION_UNDER_REVIEW: (
        calculations.SITUATION_APPROVED,
        calculations.SITUATION_RETURNED,
    ),
    calculations.SITUATION_APPROVED: (calculations.SITUATION_INVOICED,),
    calculations.SITUATION_INVOICED: (calculations.SITUATION_PAID,),
}

CONTRACT_REASON_MAX = 300

FIELD_MEASUREMENT_PERIOD = "periodo"
FIELD_MEASUREMENT_VALUE = "bruto"
FIELD_MEASUREMENT_MILESTONE = "marco"
FIELD_MEASUREMENT_SITUATION = "situacao"
FIELD_MEASUREMENT_REASON = "motivo"
FIELD_ADDENDUM_DATE = "data"
FIELD_ADDENDUM_VALUE = "valor"
FIELD_ADDENDUM_DAYS = "dias"
FIELD_ADDENDUM_REASON = "motivo"
FIELD_ADDENDUM_CHANGE = "sm"
FIELD_ADDENDUM_CLAIM = "claim"

MEASUREMENT_PERIOD_REQUIRED = "Informe o período da medição."
MEASUREMENT_VALUE_REQUIRED = "Informe um valor maior que zero."
MEASUREMENT_OVER_BALANCE = (
    "O valor de {value} supera o saldo disponível de {available}. Registre um aditivo antes."
)
MEASUREMENT_RETURN_REASON_ASK = "Informe o motivo da devolução."
MEASUREMENT_TRANSITION_REFUSED = "A medição {current} não pode ir para {target}."
ADDENDUM_DATE_REQUIRED = "Informe a data de assinatura."
ADDENDUM_VALUE_OR_DAYS_REQUIRED = "Informe valor, prorrogação ou ambos."
ADDENDUM_REASON_ASK = "Informe o motivo do aditivo."


@dataclass(frozen=True)
class MeasurementForm:
    """A medição nova pedida pela tela: o período, o valor bruto e o marco opcional."""

    period: date
    value_cents: int
    milestone_id: int | None


@dataclass(frozen=True)
class AddendumForm:
    """O aditivo pedido pela tela: valor e/ou dias, motivo e as origens opcionais."""

    signed_on: date
    value_cents: int
    days: int
    reason: str
    change_id: int | None
    claim_id: int | None


def measurement_transition_allowed(current: str, target: str) -> bool:
    """A situação atual admite a próxima, pelo fluxo do protótipo."""
    return target in MEASUREMENT_TRANSITIONS.get(current, ())


def check_measurement_transition(current: str, target: str) -> None:
    """Transição fora do fluxo é recusada com 422 e a mensagem no campo da situação."""
    if not measurement_transition_allowed(current, target):
        raise InvalidDataError(
            {
                FIELD_MEASUREMENT_SITUATION: MEASUREMENT_TRANSITION_REFUSED.format(
                    current=current, target=target
                )
            }
        )


def parse_measurement_form(form: Mapping[str, str | None]) -> MeasurementForm:
    """A medição nova: período obrigatório e valor bruto maior que zero; o marco é opcional."""
    period = _month(_text(form, FIELD_MEASUREMENT_PERIOD))
    value = parse_money(_text(form, FIELD_MEASUREMENT_VALUE))
    milestone_id = _digit(_text(form, FIELD_MEASUREMENT_MILESTONE))
    _refuse(
        {
            FIELD_MEASUREMENT_PERIOD: "" if period else MEASUREMENT_PERIOD_REQUIRED,
            FIELD_MEASUREMENT_VALUE: "" if value and value > 0 else MEASUREMENT_VALUE_REQUIRED,
        }
    )
    return MeasurementForm(
        period=period or date.min,
        value_cents=value or 0,
        milestone_id=milestone_id,
    )


def check_measurement_balance(*, value_cents: int, available_cents: int) -> None:
    """Medição acima do saldo disponível do contrato: 422 com a mensagem no valor."""
    if value_cents > available_cents:
        raise InvalidDataError(
            {
                FIELD_MEASUREMENT_VALUE: MEASUREMENT_OVER_BALANCE.format(
                    value=format_brl(value_cents), available=format_brl(available_cents)
                )
            }
        )


def parse_return_form(form: Mapping[str, str | None]) -> str:
    """A devolução exige o motivo, preenchido e dentro do limite; volta no campo do motivo."""
    reason = _text(form, FIELD_MEASUREMENT_REASON)
    _refuse({FIELD_MEASUREMENT_REASON: _reason_problem(reason, MEASUREMENT_RETURN_REASON_ASK)})
    return reason


def parse_addendum_form(form: Mapping[str, str | None]) -> AddendumForm:
    """O aditivo: data e motivo obrigatórios e valor ou dias (não ambos zero)."""
    signed_on = _date(_text(form, FIELD_ADDENDUM_DATE))
    value = parse_money(_text(form, FIELD_ADDENDUM_VALUE)) or 0
    days = _digit(_text(form, FIELD_ADDENDUM_DAYS)) or 0
    reason = _text(form, FIELD_ADDENDUM_REASON)
    _refuse(
        {
            FIELD_ADDENDUM_DATE: "" if signed_on else ADDENDUM_DATE_REQUIRED,
            FIELD_ADDENDUM_VALUE: "" if value or days else ADDENDUM_VALUE_OR_DAYS_REQUIRED,
            FIELD_ADDENDUM_REASON: _reason_problem(reason, ADDENDUM_REASON_ASK),
        }
    )
    return AddendumForm(
        signed_on=signed_on or date.min,
        value_cents=value,
        days=days,
        reason=reason,
        change_id=_digit(_text(form, FIELD_ADDENDUM_CHANGE)),
        claim_id=_digit(_text(form, FIELD_ADDENDUM_CLAIM)),
    )


def _month(text: str) -> date | None:
    """The first day of the month of a ``AAAA-MM`` label, or ``None`` when it is not one."""
    try:
        return date.fromisoformat(f"{text}-01")
    except ValueError:
        return None


def _date(text: str) -> date | None:
    """A date as the date field sends it, or ``None`` when empty or invalid."""
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _reason_problem(reason: str, ask: str, maximum: int = CONTRACT_REASON_MAX) -> str:
    """Filled reason within the limit, as the prototype's ``motivo`` fields ask."""
    if not reason:
        return ask
    if len(reason) > maximum:
        return f"Use até {maximum} caracteres."
    return ""


# ── Marcos, claims e EOT (ISSUE-033) ─────────────────────────────────────


MILESTONE_CRITERIA_MIN = 3
MILESTONE_CRITERIA_MAX = 160
CLAIM_CLAUSE_MAX = 20
CLAIM_DESCRIPTION_MAX = 300
STATEMENT_MAX = 400
EXTENSION_EVENT_MAX = 300
EXTENSION_MILESTONE_MAX = 120

CLAIM_DIRECTION_CONTRACTOR = "Da contratada"
CLAIM_DIRECTION_CLIENT = "Do contratante"
CLAIM_DIRECTIONS = (CLAIM_DIRECTION_CONTRACTOR, CLAIM_DIRECTION_CLIENT)

CLAIM_KIND_TIME = "Prazo"
CLAIM_KIND_COST = "Custo"
CLAIM_KIND_BOTH = "Prazo e custo"
CLAIM_KINDS = (CLAIM_KIND_TIME, CLAIM_KIND_COST, CLAIM_KIND_BOTH)

CLAIM_CAUSES = (
    "Liberação de área",
    "Mudança de escopo",
    "Informação de projeto tardia",
    "Interferência",
    "Suspensão",
    "Condição climática",
    "Força maior",
    "Outros",
)

EXTENSION_METHODS = (
    "Análise de impacto no tempo",
    "Análise por janelas",
    "Planejado x executado",
)

EXTENSION_CLASSIFICATIONS = (
    "Justificável e compensável",
    "Justificável não compensável",
    "Não justificável",
)

EXTENSION_DECISIONS = (
    calculations.EXTENSION_GRANTED,
    calculations.EXTENSION_PARTIALLY_GRANTED,
    calculations.EXTENSION_DENIED,
)

MILESTONE_TRANSITIONS: Mapping[str, tuple[str, ...]] = {
    calculations.MILESTONE_FORECAST: (calculations.MILESTONE_EVIDENCE_SENT,),
    calculations.MILESTONE_EVIDENCE_SENT: (calculations.MILESTONE_APPROVED,),
    calculations.MILESTONE_APPROVED: (calculations.MILESTONE_INVOICED,),
    calculations.MILESTONE_INVOICED: (calculations.MILESTONE_PAID,),
}

CLAIM_TRANSITIONS: Mapping[str, tuple[str, ...]] = {
    calculations.CLAIM_NOTIFIED: (calculations.CLAIM_UNDER_REVIEW,),
    calculations.CLAIM_UNDER_REVIEW: (
        calculations.CLAIM_IN_NEGOTIATION,
        calculations.CLAIM_REJECTED,
    ),
    calculations.CLAIM_IN_NEGOTIATION: (
        calculations.CLAIM_AGREED,
        calculations.CLAIM_REJECTED,
        calculations.CLAIM_IN_DISPUTE,
    ),
    calculations.CLAIM_AGREED: (calculations.CLAIM_CLOSED,),
    calculations.CLAIM_REJECTED: (calculations.CLAIM_IN_DISPUTE, calculations.CLAIM_CLOSED),
    calculations.CLAIM_IN_DISPUTE: (calculations.CLAIM_AGREED, calculations.CLAIM_CLOSED),
}

EXTENSION_TRANSITIONS: Mapping[str, tuple[str, ...]] = {
    calculations.EXTENSION_REQUESTED: (
        calculations.EXTENSION_UNDER_REVIEW,
        calculations.EXTENSION_GRANTED,
        calculations.EXTENSION_PARTIALLY_GRANTED,
        calculations.EXTENSION_DENIED,
    ),
    calculations.EXTENSION_UNDER_REVIEW: (
        calculations.EXTENSION_GRANTED,
        calculations.EXTENSION_PARTIALLY_GRANTED,
        calculations.EXTENSION_DENIED,
    ),
}

FIELD_MILESTONE_DESCRIPTION = "descricao"
FIELD_MILESTONE_CRITERIA = "criterio"
FIELD_MILESTONE_PCT = "pct"
FIELD_MILESTONE_EXPECTED = "prevista"
FIELD_MILESTONE_COMPLETED = "conclusao"
FIELD_MILESTONE_EVIDENCE = "evidencias"
FIELD_MILESTONE_SITUATION = "situacao"
FIELD_CLAIM_DIRECTION = "direcao"
FIELD_CLAIM_KIND = "tipo"
FIELD_CLAIM_CAUSE = "causa"
FIELD_CLAIM_CLAUSE = "clausula"
FIELD_CLAIM_DESCRIPTION = "descricao"
FIELD_CLAIM_EVENT = "evento"
FIELD_CLAIM_NOTIFICATION = "notificacao"
FIELD_CLAIM_VALUE = "valor"
FIELD_CLAIM_DAYS = "dias"
FIELD_CLAIM_SITUATION = "situacao"
FIELD_CLAIM_RECOGNIZED = "reconhecido"
FIELD_CLAIM_STATEMENT = "parecer"
FIELD_EXTENSION_CLAIM = "claim"
FIELD_EXTENSION_EVENT = "evento"
FIELD_EXTENSION_DAYS = "dias"
FIELD_EXTENSION_MILESTONE = "marco"
FIELD_EXTENSION_METHOD = "metodo"
FIELD_EXTENSION_SITUATION = "situacao"
FIELD_EXTENSION_CLASSIFICATION = "classificacao"
FIELD_EXTENSION_STATEMENT = "parecer"

MILESTONE_DESCRIPTION_ASK = "Informe a descrição"
MILESTONE_CRITERIA_ASK = "Informe o critério de aceite"
MILESTONE_PCT_REQUIRED = "Informe o percentual do marco, maior que zero."
MILESTONE_PCT_ABOVE_100 = "O percentual do marco vai até 100%."
MILESTONE_PCT_INTEGER = "Informe o percentual em número inteiro."
MILESTONE_PCT_OVER_TOTAL = "A soma dos marcos passaria de 100% (restam {remaining}%)."
MILESTONE_PCT_NOT_TOTAL = "A soma dos marcos precisa ser 100% (soma atual: {total}%)."
MILESTONE_EXPECTED_REQUIRED = "Informe a data prevista."
MILESTONE_COMPLETED_REQUIRED = "Informe a data de conclusão."
MILESTONE_EVIDENCE_REQUIRED = "A aprovação do marco exige anexo de evidência."
MILESTONE_TRANSITION_REFUSED = "O marco {current} não pode ir para {target}."
CLAIM_DIRECTION_REQUIRED = "Escolha a direção do claim."
CLAIM_KIND_REQUIRED = "Escolha o tipo: Prazo, Custo ou Prazo e custo."
CLAIM_CAUSE_REQUIRED = "Escolha a causa do claim."
CLAIM_CLAUSE_MAX_MESSAGE = f"A cláusula aceita até {CLAIM_CLAUSE_MAX} caracteres."
CLAIM_DESCRIPTION_ASK = "Informe a descrição do claim"
CLAIM_EVENT_REQUIRED = "Informe a data do evento."
CLAIM_NOTIFICATION_REQUIRED = "Informe a data da notificação."
CLAIM_NOTIFICATION_BEFORE_EVENT = "A notificação não pode ser anterior ao evento."
CLAIM_VALUE_REQUIRED = "Informe o valor pleiteado."
CLAIM_DAYS_REQUIRED = "Informe os dias pleiteados."
CLAIM_SITUATION_REQUIRED = "Escolha a nova situação do claim."
CLAIM_RECOGNIZED_REQUIRED = "Informe o valor reconhecido."
CLAIM_RECOGNIZED_OVER_CLAIMED = "O reconhecido não pode superar o pleiteado."
CLAIM_STATEMENT_ASK = "Informe o parecer."
CLAIM_TRANSITION_REFUSED = "O claim {current} não pode ir para {target}."
EXTENSION_EVENT_ASK = "Informe o evento causador"
EXTENSION_DAYS_REQUIRED = "Informe os dias solicitados."
EXTENSION_MILESTONE_ASK = "Informe o marco contratual afetado"
EXTENSION_METHOD_REQUIRED = "Escolha o método de análise de atraso."
EXTENSION_DECISION_REQUIRED = "Escolha a decisão: Concedida, Concedida parcialmente ou Negada."
EXTENSION_GRANTED_REQUIRED = "Informe os dias concedidos."
EXTENSION_GRANTED_FULL = (
    "Concedida integralmente: {requested} dias. Use Concedida parcialmente para menos dias."
)
EXTENSION_GRANTED_PARTIAL = "Parcial precisa ser menor que o solicitado."
EXTENSION_CLASSIFICATION_REQUIRED = "Escolha a classificação."
EXTENSION_STATEMENT_ASK = "Informe o parecer da análise de atraso."
EXTENSION_TRANSITION_REFUSED = "A extensão de prazo {current} não pode ir para {target}."


@dataclass(frozen=True)
class MilestoneForm:
    """O marco novo pedido pela tela: descrição, critério, percentual e data prevista."""

    description: str
    criteria: str
    pct: int
    expected_on: date


@dataclass(frozen=True)
class ClaimForm:
    """O claim novo pedido pela tela: direção, tipo, causa, datas e valores pleiteados."""

    direction: str
    kind: str
    cause: str
    clause: str
    description: str
    event_date: date
    notification_date: date
    claimed_cents: int
    claimed_days: int


@dataclass(frozen=True)
class ClaimUpdateForm:
    """A atualização do claim: a nova situação, o parecer e o reconhecido quando acordado."""

    target: str
    recognized_cents: int | None
    recognized_days: int | None
    statement: str


@dataclass(frozen=True)
class ExtensionForm:
    """A EOT nova pedida pela tela: claim de origem opcional, evento, dias, marco e método."""

    claim_id: int | None
    event: str
    requested_days: int
    affected_milestone: str
    method: str


@dataclass(frozen=True)
class ExtensionDecisionForm:
    """A decisão da EOT: concedida (integral ou parcial) ou negada, com parecer e classificação."""

    target: str
    granted_days: int
    classification: str
    statement: str


def milestone_transition_allowed(current: str, target: str) -> bool:
    """A situação atual do marco admite a próxima, pelo fluxo do protótipo."""
    return target in MILESTONE_TRANSITIONS.get(current, ())


def check_milestone_transition(current: str, target: str) -> None:
    """Transição fora do fluxo do marco é recusada com a mensagem no campo da situação."""
    if not milestone_transition_allowed(current, target):
        raise InvalidDataError(
            {
                FIELD_MILESTONE_SITUATION: MILESTONE_TRANSITION_REFUSED.format(
                    current=current, target=target
                )
            }
        )


def check_milestone_evidence(*, has_evidence: bool) -> None:
    """O marco só é aprovado com um anexo de evidência gravado (D5a)."""
    if not has_evidence:
        raise InvalidDataError({FIELD_MILESTONE_EVIDENCE: MILESTONE_EVIDENCE_REQUIRED})


def check_milestone_pct(*, used_pct: int, new_pct: int) -> None:
    """O marco novo não pode passar a soma dos 100%; a mensagem diz quanto resta."""
    if used_pct + new_pct > calculations.MILESTONE_PCT_TOTAL:
        remaining = calculations.MILESTONE_PCT_TOTAL - used_pct
        raise InvalidDataError(
            {FIELD_MILESTONE_PCT: MILESTONE_PCT_OVER_TOTAL.format(remaining=remaining)}
        )


def check_milestone_pct_total(pcts: Sequence[int]) -> None:
    """A soma dos percentuais dos marcos do contrato precisa fechar 100%."""
    if not calculations.milestone_pct_complete(pcts):
        total = calculations.milestone_pct_total(pcts)
        raise InvalidDataError({FIELD_MILESTONE_PCT: MILESTONE_PCT_NOT_TOTAL.format(total=total)})


def parse_milestone_form(form: Mapping[str, str | None]) -> MilestoneForm:
    """O marco novo: descrição, critério, percentual inteiro e data prevista obrigatórios."""
    description = _text(form, FIELD_MILESTONE_DESCRIPTION)
    criteria = _text(form, FIELD_MILESTONE_CRITERIA)
    pct = parse_quantity(_text(form, FIELD_MILESTONE_PCT))
    expected_on = _date(_text(form, FIELD_MILESTONE_EXPECTED))
    _refuse(
        {
            FIELD_MILESTONE_DESCRIPTION: _length_error(
                description, DESCRIPTION_MIN, DESCRIPTION_MAX, MILESTONE_DESCRIPTION_ASK
            ),
            FIELD_MILESTONE_CRITERIA: _length_error(
                criteria, MILESTONE_CRITERIA_MIN, MILESTONE_CRITERIA_MAX, MILESTONE_CRITERIA_ASK
            ),
            FIELD_MILESTONE_PCT: _milestone_pct_problem(pct),
            FIELD_MILESTONE_EXPECTED: "" if expected_on else MILESTONE_EXPECTED_REQUIRED,
        }
    )
    return MilestoneForm(
        description=description,
        criteria=criteria,
        pct=int(pct or 0),
        expected_on=expected_on or date.min,
    )


def parse_milestone_evidence_form(form: Mapping[str, str | None]) -> date:
    """O envio de evidência do marco: a data de conclusão é obrigatória; o anexo é à parte."""
    completed_on = _date(_text(form, FIELD_MILESTONE_COMPLETED))
    _refuse({FIELD_MILESTONE_COMPLETED: "" if completed_on else MILESTONE_COMPLETED_REQUIRED})
    return completed_on or date.min


def parse_claim_form(form: Mapping[str, str | None]) -> ClaimForm:
    """O claim novo: direção, tipo, causa, datas e o valor/dias que o tipo pede."""
    direction = _text(form, FIELD_CLAIM_DIRECTION)
    kind = _text(form, FIELD_CLAIM_KIND)
    cause = _text(form, FIELD_CLAIM_CAUSE)
    clause = _text(form, FIELD_CLAIM_CLAUSE)
    description = _text(form, FIELD_CLAIM_DESCRIPTION)
    event_date = _date(_text(form, FIELD_CLAIM_EVENT))
    notification_date = _date(_text(form, FIELD_CLAIM_NOTIFICATION))
    claimed = parse_money(_text(form, FIELD_CLAIM_VALUE))
    days = _digit(_text(form, FIELD_CLAIM_DAYS))
    _refuse(
        {
            FIELD_CLAIM_DIRECTION: ""
            if direction in CLAIM_DIRECTIONS
            else CLAIM_DIRECTION_REQUIRED,
            FIELD_CLAIM_KIND: "" if kind in CLAIM_KINDS else CLAIM_KIND_REQUIRED,
            FIELD_CLAIM_CAUSE: "" if cause in CLAIM_CAUSES else CLAIM_CAUSE_REQUIRED,
            FIELD_CLAIM_CLAUSE: "" if len(clause) <= CLAIM_CLAUSE_MAX else CLAIM_CLAUSE_MAX_MESSAGE,
            FIELD_CLAIM_DESCRIPTION: _length_error(
                description, DESCRIPTION_MIN, CLAIM_DESCRIPTION_MAX, CLAIM_DESCRIPTION_ASK
            ),
            FIELD_CLAIM_EVENT: "" if event_date else CLAIM_EVENT_REQUIRED,
            FIELD_CLAIM_NOTIFICATION: _notification_problem(event_date, notification_date),
            FIELD_CLAIM_VALUE: (
                "" if kind == CLAIM_KIND_TIME or (claimed and claimed > 0) else CLAIM_VALUE_REQUIRED
            ),
            FIELD_CLAIM_DAYS: (
                "" if kind == CLAIM_KIND_COST or (days and days > 0) else CLAIM_DAYS_REQUIRED
            ),
        }
    )
    return ClaimForm(
        direction=direction,
        kind=kind,
        cause=cause,
        clause=clause,
        description=description,
        event_date=event_date or date.min,
        notification_date=notification_date or date.min,
        claimed_cents=claimed or 0,
        claimed_days=days or 0,
    )


def claim_transition_allowed(current: str, target: str) -> bool:
    """A situação atual do claim admite a próxima, pelo fluxo do protótipo."""
    return target in CLAIM_TRANSITIONS.get(current, ())


def check_claim_transition(current: str, target: str) -> None:
    """Transição fora do fluxo do claim é recusada com a mensagem no campo da situação."""
    if not claim_transition_allowed(current, target):
        raise InvalidDataError(
            {FIELD_CLAIM_SITUATION: CLAIM_TRANSITION_REFUSED.format(current=current, target=target)}
        )


def parse_claim_update_form(
    form: Mapping[str, str | None], *, claimed_cents: int | None = None
) -> ClaimUpdateForm:
    """A atualização do claim: situação, parecer obrigatório e o reconhecido quando acordado."""
    target = _text(form, FIELD_CLAIM_SITUATION)
    statement = _text(form, FIELD_CLAIM_STATEMENT)
    recognized = parse_money(_text(form, FIELD_CLAIM_RECOGNIZED))
    days = _digit(_text(form, FIELD_CLAIM_DAYS))
    agreed = target == calculations.CLAIM_AGREED
    problems = {
        FIELD_CLAIM_SITUATION: _claim_target_problem(target),
        FIELD_CLAIM_STATEMENT: _reason_problem(
            statement, CLAIM_STATEMENT_ASK, maximum=STATEMENT_MAX
        ),
    }
    if agreed:
        problems[FIELD_CLAIM_RECOGNIZED] = _recognized_problem(recognized, claimed_cents)
    _refuse(problems)
    return ClaimUpdateForm(
        target=target,
        recognized_cents=recognized if agreed else None,
        recognized_days=(days or 0) if agreed else None,
        statement=statement,
    )


def extension_transition_allowed(current: str, target: str) -> bool:
    """A situação atual da EOT admite a próxima, pelo fluxo do protótipo."""
    return target in EXTENSION_TRANSITIONS.get(current, ())


def check_extension_transition(current: str, target: str) -> None:
    """Transição fora do fluxo da EOT é recusada com a mensagem no campo da situação."""
    if not extension_transition_allowed(current, target):
        raise InvalidDataError(
            {
                FIELD_EXTENSION_SITUATION: EXTENSION_TRANSITION_REFUSED.format(
                    current=current, target=target
                )
            }
        )


def parse_extension_form(form: Mapping[str, str | None]) -> ExtensionForm:
    """A EOT nova: evento, dias solicitados, marco afetado e método; o claim é opcional."""
    claim_id = _digit(_text(form, FIELD_EXTENSION_CLAIM))
    event = _text(form, FIELD_EXTENSION_EVENT)
    days = _digit(_text(form, FIELD_EXTENSION_DAYS))
    milestone = _text(form, FIELD_EXTENSION_MILESTONE)
    method = _text(form, FIELD_EXTENSION_METHOD)
    _refuse(
        {
            FIELD_EXTENSION_EVENT: _length_error(
                event, DESCRIPTION_MIN, EXTENSION_EVENT_MAX, EXTENSION_EVENT_ASK
            ),
            FIELD_EXTENSION_DAYS: "" if days and days > 0 else EXTENSION_DAYS_REQUIRED,
            FIELD_EXTENSION_MILESTONE: _length_error(
                milestone, DESCRIPTION_MIN, EXTENSION_MILESTONE_MAX, EXTENSION_MILESTONE_ASK
            ),
            FIELD_EXTENSION_METHOD: ""
            if method in EXTENSION_METHODS
            else EXTENSION_METHOD_REQUIRED,
        }
    )
    return ExtensionForm(
        claim_id=claim_id,
        event=event,
        requested_days=days or 0,
        affected_milestone=milestone,
        method=method,
    )


def parse_extension_decision_form(
    form: Mapping[str, str | None], *, requested_days: int
) -> ExtensionDecisionForm:
    """A decisão da EOT: integral, parcial ou negada, com parecer e classificação."""
    target = _text(form, FIELD_EXTENSION_SITUATION)
    granted = _digit(_text(form, FIELD_EXTENSION_DAYS))
    classification = _text(form, FIELD_EXTENSION_CLASSIFICATION)
    statement = _text(form, FIELD_EXTENSION_STATEMENT)
    decided = target in (
        calculations.EXTENSION_GRANTED,
        calculations.EXTENSION_PARTIALLY_GRANTED,
    )
    problems = {
        FIELD_EXTENSION_SITUATION: ""
        if target in EXTENSION_DECISIONS
        else EXTENSION_DECISION_REQUIRED,
        FIELD_EXTENSION_STATEMENT: _reason_problem(
            statement, EXTENSION_STATEMENT_ASK, maximum=STATEMENT_MAX
        ),
    }
    if decided:
        problems[FIELD_EXTENSION_DAYS] = _granted_problem(target, granted, requested_days)
        problems[FIELD_EXTENSION_CLASSIFICATION] = (
            "" if classification in EXTENSION_CLASSIFICATIONS else EXTENSION_CLASSIFICATION_REQUIRED
        )
    _refuse(problems)
    return ExtensionDecisionForm(
        target=target,
        granted_days=granted if decided and granted is not None else 0,
        classification=classification if decided else "",
        statement=statement,
    )


def _milestone_pct_problem(pct: Decimal | None) -> str:
    if pct is None or pct <= 0:
        return MILESTONE_PCT_REQUIRED
    if pct > calculations.MILESTONE_PCT_TOTAL:
        return MILESTONE_PCT_ABOVE_100
    if pct != pct.to_integral_value():
        return MILESTONE_PCT_INTEGER
    return ""


def _notification_problem(event_date: date | None, notification_date: date | None) -> str:
    if notification_date is None:
        return CLAIM_NOTIFICATION_REQUIRED
    if event_date is not None and notification_date < event_date:
        return CLAIM_NOTIFICATION_BEFORE_EVENT
    return ""


def _claim_target_problem(target: str) -> str:
    situations = (
        calculations.CLAIM_NOTIFIED,
        calculations.CLAIM_UNDER_REVIEW,
        calculations.CLAIM_IN_NEGOTIATION,
        calculations.CLAIM_AGREED,
        calculations.CLAIM_REJECTED,
        calculations.CLAIM_IN_DISPUTE,
        calculations.CLAIM_CLOSED,
    )
    return "" if target in situations else CLAIM_SITUATION_REQUIRED


def _recognized_problem(recognized: int | None, claimed_cents: int | None) -> str:
    if recognized is None or recognized < 0:
        return CLAIM_RECOGNIZED_REQUIRED
    if claimed_cents is not None and recognized > claimed_cents:
        return CLAIM_RECOGNIZED_OVER_CLAIMED
    return ""


def _granted_problem(target: str, granted: int | None, requested_days: int) -> str:
    if granted is None or granted < 1:
        return EXTENSION_GRANTED_REQUIRED
    if target == calculations.EXTENSION_GRANTED and granted != requested_days:
        return EXTENSION_GRANTED_FULL.format(requested=requested_days)
    if target == calculations.EXTENSION_PARTIALLY_GRANTED and granted >= requested_days:
        return EXTENSION_GRANTED_PARTIAL
    return ""


# ── Avaliação de desempenho da contratada (ISSUE-034) ────────────────────


EVALUATION_COMMENT_MAX = 400

FIELD_EVALUATION_PERIOD = "periodo"
FIELD_EVALUATION_KIND = "tipo"
FIELD_EVALUATION_COMMENT = "comentario"

EVALUATION_PERIOD_REQUIRED = "Informe o período da avaliação (AAAA-MM)."
EVALUATION_KIND_REQUIRED = "Escolha o tipo da avaliação: Mensal ou Final."
EVALUATION_NOTE_REQUIRED = "Informe uma nota de 1 a 5."
EVALUATION_COMMENT_MAX_MESSAGE = f"Use até {EVALUATION_COMMENT_MAX} caracteres."


@dataclass(frozen=True)
class EvaluationForm:
    """A avaliação nova pedida pela tela: período, tipo, as notas por critério e o comentário."""

    period: date
    kind: str
    notes: Mapping[str, int]
    comment: str


def parse_evaluation_form(
    form: Mapping[str, str | None], *, criteria_ids: Collection[str]
) -> EvaluationForm:
    """Check the evaluation form; refuse with 422, one message per field of the criterion.

    The criteria are the ones in force in the parameters and each note is required and goes from
    1 to 5; the period is the month the evaluation refers to. The comment is optional and within
    400 characters; the evidence that a note 1 or 2 requires is an attachment, checked by the
    service, not here.
    """
    period = _month(_text(form, FIELD_EVALUATION_PERIOD))
    kind = _text(form, FIELD_EVALUATION_KIND)
    comment = _text(form, FIELD_EVALUATION_COMMENT)
    notes = {criterion: _note(form, criterion) for criterion in criteria_ids}
    problems = {
        FIELD_EVALUATION_PERIOD: "" if period else EVALUATION_PERIOD_REQUIRED,
        FIELD_EVALUATION_KIND: ""
        if kind in calculations.EVALUATION_KINDS
        else EVALUATION_KIND_REQUIRED,
        FIELD_EVALUATION_COMMENT: (
            "" if len(comment) <= EVALUATION_COMMENT_MAX else EVALUATION_COMMENT_MAX_MESSAGE
        ),
    }
    problems.update(
        {
            criterion: "" if note is not None else EVALUATION_NOTE_REQUIRED
            for criterion, note in notes.items()
        }
    )
    _refuse(problems)
    return EvaluationForm(
        period=period or date.min,
        kind=kind,
        notes={criterion: note or 0 for criterion, note in notes.items()},
        comment=comment,
    )


def _note(form: Mapping[str, str | None], criterion: str) -> int | None:
    note = _digit(_text(form, criterion))
    if note is None or not 1 <= note <= calculations.EVALUATION_MAX_NOTE:
        return None
    return note
