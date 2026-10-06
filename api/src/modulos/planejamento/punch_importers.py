"""The spreadsheet importer of the Punch list (D12, ISSUE-049): walkdowns and commissioning lists.

The project comes from the scope (an import in the Portfólio is refused with the message of the
scope). The check reads every line and never writes; the confirmation writes the lines without
error, all or none, through the facade, so each imported line is an item with its action in the
Central, exactly like the form. The person who imports is the one who identified the items.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from src.core import importing
from src.core.export_document import ValueKind
from src.core.import_values import normalize_text
from src.core.importing import ImportColumn, ImportContext, Importer, RowCheck
from src.modulos.planejamento import punch_calculations as calc
from src.modulos.planejamento import punch_service as service
from src.modulos.planejamento import punch_validation as validation
from src.modulos.planejamento.punch_validation import ItemInput

KEY = "punch-list"
MODULE = "planejamento"
SYSTEM_NOT_FOUND = "o sistema não está no cadastro do projeto"
COMPANY_NOT_FOUND = "a empresa não está no cadastro"
PERSON_NOT_FOUND = "a pessoa não está no cadastro"

# The form field of each message, and the header of the column the person sees it under.
HEADERS = {
    "sistema": "Sistema",
    "subsistema": "Subsistema",
    "tag": "TAG",
    "disciplina": "Disciplina",
    "categoria": "Categoria",
    "marco": "Marco",
    "origem": "Origem",
    "descricao": "Descrição",
    "empresa": "Empresa",
    "responsavel": "Responsável",
    "prazo": "Prazo",
}


def _by_name(options: Any, name: str) -> int | None:
    wanted = normalize_text(name)
    return next((item.id for item in options if normalize_text(item.name) == wanted), None)


def _item_of(session: Session, values: Mapping[str, Any], context: ImportContext) -> ItemInput:
    options = service.form_options(session, project_id=context.scope.require_project())
    wanted = normalize_text(values["system"])
    system_id = next(
        (
            item.id
            for item in options.systems
            if normalize_text(item.label.split(" ", 1)[0]) == wanted
        ),
        None,
    )
    return ItemInput(
        system_id=system_id,
        subsystem=values["subsystem"].strip(),
        tag=values["tag"].strip(),
        discipline=values["discipline"],
        category=values["category"],
        milestone=values["milestone"],
        origin=values["origin"],
        description=values["description"].strip(),
        company_id=_by_name(options.companies, values["company"]),
        responsible_id=_by_name(options.people, values["responsible"]),
        identified_by_id=context.user.person_id,
        due_date=values["due_date"],
    )


def _validate(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> RowCheck:
    data = _item_of(session, values, context)
    problems = validation.item_problems(
        data, service.register_choices(session, project_id=context.scope.require_project())
    )
    for name, message in (
        ("sistema", SYSTEM_NOT_FOUND),
        ("empresa", COMPANY_NOT_FOUND),
        ("responsavel", PERSON_NOT_FOUND),
    ):
        if name in problems:
            problems[name] = message
    return RowCheck(
        errors=tuple(f"{HEADERS.get(field, field)}: {text}" for field, text in problems.items())
    )


def _save(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    service.create_item(
        session,
        user=context.user,
        scope=context.scope,
        data=_item_of(session, values, context),
        reference_date=context.reference_date,
    )


def punch_importer() -> Importer:
    """The Punch list importer: one line is one item, opened today with its action."""
    return Importer(
        key=KEY,
        title="Itens da punch list",
        module=MODULE,
        columns=(
            ImportColumn("system", "Sistema", required=True, example="310"),
            ImportColumn("subsystem", "Subsistema", required=True, example="Tubulação"),
            ImportColumn("tag", "TAG", required=True, example="310-P-030"),
            ImportColumn(
                "discipline",
                "Disciplina",
                required=True,
                options=calc.DISCIPLINES,
                example="Tubulação",
            ),
            ImportColumn(
                "category", "Categoria", required=True, options=calc.CATEGORIES, example="B"
            ),
            ImportColumn(
                "milestone",
                "Marco",
                required=True,
                options=calc.MILESTONES,
                example="Aceite provisório",
            ),
            ImportColumn(
                "origin", "Origem", required=True, options=calc.ORIGINS, example="Walkdown"
            ),
            ImportColumn(
                "description", "Descrição", required=True, example="Isolamento térmico incompleto"
            ),
            ImportColumn("company", "Empresa", required=True, example="Alfa Montagens"),
            ImportColumn("responsible", "Responsável", required=True, example="Carlos Nunes"),
            ImportColumn("due_date", "Prazo", ValueKind.DATE, required=True, example="15/10/2026"),
        ),
        validate=_validate,
        save=_save,
    )


def register_importers() -> None:
    """Register the importer once; calling again keeps the one already registered."""
    importer = punch_importer()
    if importing.find(importer.key) is None:
        importing.register(importer)
