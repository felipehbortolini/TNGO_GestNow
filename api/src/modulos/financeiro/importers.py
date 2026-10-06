"""The spreadsheet importer of the EAC: the new cost items of a revision (D12, ISSUE-030).

The generic flow of ISSUE-018 has one writer per line, but a line of the EAC is not written on its
own: the imported items enter together in a **revision** bound to an approved SM, and the revision
is created by ``financeiro.service.create_revision`` from the checked lines. So this importer
registers its columns and its per-line validation (the model download and the check work through
the generic routes) and its ``save`` refuses: the confirmation belongs to the EAC screen, which
carries the SM and the justification and creates the revision all at once. The alternative — a
``save`` that writes an item — would let the generic confirmation put items in the EAC without a
revision, against the rule that every change of value passes through the management of changes.

The module's routes (``routes.py``) do the two steps with ``core.importing``: the check renders
the preview and the confirmation checks again and calls ``create_revision`` with the writable
lines converted by :func:`revision_items`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.core import importing
from src.core.errors import InvalidDataError
from src.core.export_document import ValueKind
from src.core.import_values import normalize_text
from src.core.importing import CheckedRow, ImportColumn, ImportContext, Importer, RowCheck
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import calculations, service, validation

EAC_ITEMS_KEY = "eac-itens"
MODULE = service.MODULE

CODE_HEADER = "Código"
DESCRIPTION_HEADER = "Descrição"
COST_TYPE_HEADER = "Tipo de custo"
UNIT_HEADER = "Unidade"
QUANTITY_HEADER = "Quantidade"
PRICE_HEADER = "Preço unitário (R$)"
CLASSIFICATION_HEADER = "CAPEX/OPEX"
COST_CENTER_HEADER = "Centro de custo"
RESPONSIBLE_HEADER = "Responsável"

HEADERS = {
    validation.FIELD_NEW_ITEM_CODE: CODE_HEADER,
    validation.FIELD_DESCRIPTION: DESCRIPTION_HEADER,
    validation.FIELD_COST_TYPE: COST_TYPE_HEADER,
    validation.FIELD_NEW_ITEM_UNIT: UNIT_HEADER,
    validation.FIELD_NEW_ITEM_QUANTITY: QUANTITY_HEADER,
    validation.FIELD_NEW_ITEM_PRICE: PRICE_HEADER,
    validation.FIELD_CLASSIFICATION: CLASSIFICATION_HEADER,
    validation.FIELD_COST_CENTER: COST_CENTER_HEADER,
    validation.FIELD_RESPONSIBLE: RESPONSIBLE_HEADER,
}

PARENT_MESSAGE = "o subpacote {code} não existe na EAC do projeto"
DUPLICATE_MESSAGE = "o código {code} já existe na EAC do projeto"
UNIT_MESSAGE = "a unidade {code} não está no cadastro"
RESPONSIBLE_MESSAGE = "o responsável {name} não está no cadastro"
QUANTITY_MESSAGE = "informe uma quantidade maior que zero"
PRICE_MESSAGE = "informe um preço unitário maior que zero"
CONFIRMATION_MESSAGE = (
    "a importação de itens da EAC é confirmada pela revisão vinculada à SM: "
    "envie a planilha pela tela da EAC"
)


def _messages(problems: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(
        f"{HEADERS.get(field, field)}: {message}" for field, message in problems.items() if message
    )


def _validate(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> RowCheck:
    """Check one line against the EAC of the project: place in the tree, duplicates and cadastre."""
    project_id = context.scope.require_project()
    code = str(values.get(validation.FIELD_NEW_ITEM_CODE) or "").strip()
    parent = code.rsplit(calculations.CODE_SEPARATOR, 1)[0] if code.count(".") == 2 else ""
    levels = service.eac_item_levels_by_code(session, project_id=project_id, codes=[code, parent])
    problems = {
        validation.FIELD_NEW_ITEM_CODE: _code_problem(code, parent=parent, levels=levels),
        validation.FIELD_DESCRIPTION: _length_problem(
            str(values.get(validation.FIELD_DESCRIPTION) or "")
        ),
        validation.FIELD_NEW_ITEM_UNIT: (
            ""
            if _unit_id(session, str(values.get(validation.FIELD_NEW_ITEM_UNIT) or "")) is not None
            else UNIT_MESSAGE.format(code=values.get(validation.FIELD_NEW_ITEM_UNIT) or "")
        ),
        validation.FIELD_NEW_ITEM_QUANTITY: (
            "" if _positive(values.get(validation.FIELD_NEW_ITEM_QUANTITY)) else QUANTITY_MESSAGE
        ),
        validation.FIELD_NEW_ITEM_PRICE: (
            "" if _positive(values.get(validation.FIELD_NEW_ITEM_PRICE)) else PRICE_MESSAGE
        ),
        validation.FIELD_COST_CENTER: (
            ""
            if len(str(values.get(validation.FIELD_COST_CENTER) or ""))
            <= validation.COST_CENTER_MAX
            else f"use até {validation.COST_CENTER_MAX} caracteres"
        ),
        validation.FIELD_RESPONSIBLE: (
            ""
            if _person_id(session, str(values.get(validation.FIELD_RESPONSIBLE) or "")) is not None
            else RESPONSIBLE_MESSAGE.format(name=values.get(validation.FIELD_RESPONSIBLE) or "")
        ),
    }
    return RowCheck(errors=_messages(problems))


def _code_problem(code: str, *, parent: str, levels: Mapping[str, int]) -> str:
    if not _is_leaf_code(code):
        return "informe o código com três níveis (ex.: 3.2.5)"
    if levels.get(parent) != calculations.PORTFOLIO_MAIN_LEVEL:
        return PARENT_MESSAGE.format(code=parent)
    if code in levels:
        return DUPLICATE_MESSAGE.format(code=code)
    return ""


def _is_leaf_code(code: str) -> bool:
    parts = code.split(calculations.CODE_SEPARATOR)
    return len(parts) == 3 and all(part.isdigit() for part in parts)


def _length_problem(description: str) -> str:
    if len(description) < validation.DESCRIPTION_MIN:
        return f"informe a descrição (mínimo de {validation.DESCRIPTION_MIN} caracteres)"
    if len(description) > validation.DESCRIPTION_MAX:
        return f"use até {validation.DESCRIPTION_MAX} caracteres"
    return ""


def _positive(value: object) -> bool:
    return isinstance(value, int | Decimal) and not isinstance(value, bool) and value > 0


def _unit_id(session: Session, code: str) -> int | None:
    wanted = normalize_text(code)
    return next(
        (
            unit.id
            for unit in configuracoes.list_measure_units(session)
            if normalize_text(unit.code) == wanted
        ),
        None,
    )


def _person_id(session: Session, name: str) -> int | None:
    wanted = normalize_text(name)
    return next(
        (
            person.id
            for person in configuracoes.list_people(session)
            if normalize_text(person.name) == wanted
        ),
        None,
    )


def _refuse_line(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    """The generic confirmation does not write the EAC: the revision is the writer (see the module)."""
    del session, values, context
    raise InvalidDataError(CONFIRMATION_MESSAGE)


def revision_items(
    session: Session, *, project_id: int, rows: Sequence[CheckedRow]
) -> tuple[service.RevisionItemRequest, ...]:
    """The checked lines as the new items of the revision, with the ids of the cadastre resolved."""
    parents = service.eac_item_ids_by_code(
        session,
        project_id=project_id,
        codes=[_parent_code(row) for row in rows],
    )
    units = {
        normalize_text(unit.code): unit.id for unit in configuracoes.list_measure_units(session)
    }
    people = {
        normalize_text(person.name): person.id for person in configuracoes.list_people(session)
    }
    return tuple(_revision_item(row, parents=parents, units=units, people=people) for row in rows)


def _parent_code(row: CheckedRow) -> str:
    code = str(row.values.get(validation.FIELD_NEW_ITEM_CODE) or "")
    return code.rsplit(calculations.CODE_SEPARATOR, 1)[0] if code.count(".") == 2 else ""


def _revision_item(
    row: CheckedRow,
    *,
    parents: Mapping[str, int],
    units: Mapping[str, int],
    people: Mapping[str, int],
) -> service.RevisionItemRequest:
    values = row.values
    quantity = values[validation.FIELD_NEW_ITEM_QUANTITY]
    price = int(values[validation.FIELD_NEW_ITEM_PRICE])
    code = str(values[validation.FIELD_NEW_ITEM_CODE])
    return service.RevisionItemRequest(
        code=code,
        description=str(values[validation.FIELD_DESCRIPTION]),
        base_cents=calculations.budgeted_cents(quantity, price),
        parent_id=parents.get(_parent_code(row)),
        unit_id=units.get(normalize_text(str(values[validation.FIELD_NEW_ITEM_UNIT]))),
        cost_type=str(values[validation.FIELD_COST_TYPE]),
        capex=values[validation.FIELD_CLASSIFICATION] == "CAPEX",
        cost_center=str(values[validation.FIELD_COST_CENTER] or ""),
        responsible_id=people.get(normalize_text(str(values[validation.FIELD_RESPONSIBLE]))),
        quantity=quantity,
        unit_price_cents=price,
    )


def eac_items_importer() -> Importer:
    """The EAC importer: the new cost items of a revision, checked against the tree of the project."""
    return Importer(
        key=EAC_ITEMS_KEY,
        title="Itens da EAC (nível 3)",
        module=MODULE,
        columns=(
            ImportColumn(
                validation.FIELD_NEW_ITEM_CODE, CODE_HEADER, required=True, example="3.2.5"
            ),
            ImportColumn(
                validation.FIELD_DESCRIPTION,
                DESCRIPTION_HEADER,
                required=True,
                example="Isolamento térmico",
            ),
            ImportColumn(
                validation.FIELD_COST_TYPE,
                COST_TYPE_HEADER,
                options=validation.COST_TYPES,
                required=True,
                example="Serviço",
            ),
            ImportColumn(validation.FIELD_NEW_ITEM_UNIT, UNIT_HEADER, required=True, example="m²"),
            ImportColumn(
                validation.FIELD_NEW_ITEM_QUANTITY,
                QUANTITY_HEADER,
                ValueKind.DECIMAL,
                required=True,
                example="1200",
            ),
            ImportColumn(
                validation.FIELD_NEW_ITEM_PRICE,
                PRICE_HEADER,
                ValueKind.MONEY,
                required=True,
                example="85,00",
            ),
            ImportColumn(
                validation.FIELD_CLASSIFICATION,
                CLASSIFICATION_HEADER,
                options=validation.CLASSIFICATIONS,
                required=True,
                example="CAPEX",
            ),
            ImportColumn(validation.FIELD_COST_CENTER, COST_CENTER_HEADER, example="CC-4501-05"),
            ImportColumn(
                validation.FIELD_RESPONSIBLE,
                RESPONSIBLE_HEADER,
                required=True,
                example="Carlos Nunes",
            ),
        ),
        validate=_validate,
        save=_refuse_line,
        unique=(validation.FIELD_NEW_ITEM_CODE,),
    )


def register_importers() -> None:
    """Register the EAC importer once; calling again keeps the one already registered."""
    importer = eac_items_importer()
    if importing.find(importer.key) is None:
        importing.register(importer)
