"""Part of the Financeiro module in the demonstration load (ISSUE-029, D6).

Reads the ``eac`` collection of the prototype and writes the tree of each project through the
facade. The quantity and the unit price of the prototype are kept as they are, and the budgeted
value is their product, as in the product (the prototype also stored a ``base`` that rounded the
last cents; see ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``). The items carry no date, so there is
nothing to shift with ``shift_date``; the commitments, the realized values and the projections of
the prototype belong to the issues that own them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register
from src.carga.plataforma import ADMIN_EMAIL
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service
from src.modulos.financeiro.calculations import CODE_SEPARATOR, code_key

PART_NAME = "financeiro"


def load(session: Session, _reference_date: date) -> None:
    """Write the EAC tree of every project of the prototype, inside the caller's transaction."""
    admin = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if admin is None:
        return
    project_ids = {project.code: project.id for project in configuracoes.list_projects(session)}
    mock_codes = {project["id"]: project["codigo"] for project in prototype_collection("projetos")}
    mock_emails = {person["id"]: person["email"] for person in prototype_collection("pessoas")}
    people = {person.email: person.id for person in configuracoes.list_people(session)}
    units = {unit.code: unit.id for unit in configuracoes.list_measure_units(session)}
    created: dict[tuple[int, str], int] = {}
    sources = sorted(
        prototype_collection("eac"), key=lambda item: (item["projetoId"], code_key(item["codigo"]))
    )
    for source in sources:
        project_id = project_ids[mock_codes[source["projetoId"]]]
        parent_code = CODE_SEPARATOR.join(source["codigo"].split(CODE_SEPARATOR)[:-1])
        responsible = source.get("responsavelId")
        created[(project_id, source["codigo"])] = service.create_item(
            session,
            user_id=admin.id,
            new=_new_item(
                source,
                project_id=project_id,
                parent_id=created.get((project_id, parent_code)),
                unit_id=units.get(source.get("unidade") or ""),
                responsible_id=people.get(mock_emails[responsible]) if responsible else None,
            ),
        )


def _new_item(
    source: dict[str, Any],
    *,
    project_id: int,
    parent_id: int | None,
    unit_id: int | None,
    responsible_id: int | None,
) -> service.NewItem:
    quantity = source.get("quantidade")
    return service.NewItem(
        project_id=project_id,
        code=source["codigo"],
        description=source["descricao"],
        level=source["nivel"],
        parent_id=parent_id,
        unit_id=unit_id,
        responsible_id=responsible_id,
        cost_type=source.get("tipoCusto"),
        quantity=Decimal(str(quantity)) if quantity is not None else None,
        unit_price_cents=source.get("precoUnitario"),
        capex=source.get("capex"),
        cost_center=source.get("centroCusto"),
    )


register(PART_NAME, load)
