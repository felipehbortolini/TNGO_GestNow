"""The spreadsheet importers of the HSE module: HHT and the monthly closing (D12, ISSUE-072).

Both read the project from the scope (an import in the Portfólio is refused with the message of
the scope) and write through the facade, so an imported line is an upsert like the form: a month
and company already recorded are updated, never duplicated. The check reads and never writes;
the confirmation writes the lines without error, all or none.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.core import importing
from src.core.export_document import ValueKind
from src.core.importing import ImportColumn, ImportContext, Importer, RowCheck
from src.modulos.hse import service, validation
from src.modulos.hse.validation import ClosingInput, HoursInput

HOURS_KEY = "hht"
CLOSING_KEY = "hse-mensal"
MODULE = "hse"

MONTH_HEADER = "Mês (1º dia)"
COMPANY_HEADER = "Empresa"
HEADCOUNT_HEADER = "Efetivo médio"
HOURS_HEADER = "HHT"
COMPANY_NOT_FOUND = "a empresa não está no cadastro"

# The form field of each message, and the header of the column the person sees it under.
HOURS_HEADERS = {
    "mes": MONTH_HEADER,
    "empresa": COMPANY_HEADER,
    "efetivo_medio": HEADCOUNT_HEADER,
    "hht": HOURS_HEADER,
}
CLOSING_COLUMNS = (
    ("month", "mes", MONTH_HEADER, ValueKind.DATE, "01/09/2026"),
    ("planned_dds", "dds_programados", "DDS programados", ValueKind.INTEGER, "20"),
    ("held_dds", "dds_realizados", "DDS realizados", ValueKind.INTEGER, "18"),
    ("inspected_items", "itens_inspecionados", "Itens inspecionados", ValueKind.INTEGER, "120"),
    ("conforming_items", "itens_conformes", "Itens conformes", ValueKind.INTEGER, "110"),
    ("observations", "observacoes", "Observações", ValueKind.INTEGER, "30"),
    ("deviations", "desvios", "Desvios", ValueKind.INTEGER, "12"),
)
CLOSING_HEADERS = {form: header for _, form, header, _, _ in CLOSING_COLUMNS}


def _messages(problems: Mapping[str, str], headers: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(f"{headers.get(field, field)}: {message}" for field, message in problems.items())


def _hours_input(session: Session, values: Mapping[str, Any], context: ImportContext) -> HoursInput:
    return HoursInput(
        project_id=context.scope.require_project(),
        month=values["month"],
        company_id=service.company_id_by_name(session, values["company"]),
        headcount=values["headcount"],
        hours=Decimal(values["hours"]) if values["hours"] is not None else None,
    )


def _validate_hours(
    session: Session, *, values: Mapping[str, Any], context: ImportContext
) -> RowCheck:
    data = _hours_input(session, values, context)
    problems = validation.hours_problems(
        data, service.register_choices(session), reference_date=context.reference_date
    )
    if data.company_id is None:
        problems["empresa"] = COMPANY_NOT_FOUND
    return RowCheck(errors=_messages(problems, HOURS_HEADERS))


def _save_hours(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    service.save_hours(
        session,
        user=context.user,
        data=_hours_input(session, values, context),
        reference_date=context.reference_date,
    )


def _closing_input(values: Mapping[str, Any], context: ImportContext) -> ClosingInput:
    return ClosingInput(
        project_id=context.scope.require_project(),
        month=values["month"],
        deviations=values["deviations"],
        observations=values["observations"],
        planned_dds=values["planned_dds"],
        held_dds=values["held_dds"],
        inspected_items=values["inspected_items"],
        conforming_items=values["conforming_items"],
    )


def _validate_closing(
    session: Session, *, values: Mapping[str, Any], context: ImportContext
) -> RowCheck:
    del session
    problems = validation.closing_problems(
        _closing_input(values, context), reference_date=context.reference_date
    )
    return RowCheck(errors=_messages(problems, CLOSING_HEADERS))


def _save_closing(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    service.save_closing(
        session,
        user=context.user,
        data=_closing_input(values, context),
        reference_date=context.reference_date,
    )


def hours_importer() -> Importer:
    """The HHT importer: month, company, average headcount and hours; one line per month and company."""
    return Importer(
        key=HOURS_KEY,
        title="Horas trabalhadas (HHT)",
        module=MODULE,
        columns=(
            ImportColumn(
                "month", MONTH_HEADER, ValueKind.DATE, required=True, example="01/09/2026"
            ),
            ImportColumn("company", COMPANY_HEADER, required=True, example="Alfa Montagens"),
            ImportColumn(
                "headcount", HEADCOUNT_HEADER, ValueKind.INTEGER, required=True, example="60"
            ),
            ImportColumn("hours", HOURS_HEADER, ValueKind.DECIMAL, required=True, example="13080"),
        ),
        validate=_validate_hours,
        save=_save_hours,
        unique=("month", "company"),
    )


def closing_importer() -> Importer:
    """The monthly closing importer: DDS, inspection items, observations and deviations of a month."""
    return Importer(
        key=CLOSING_KEY,
        title="Inspeções, observações e DDS (fechamento mensal)",
        module=MODULE,
        columns=tuple(
            ImportColumn(field, header, kind, required=True, example=example)
            for field, _, header, kind, example in CLOSING_COLUMNS
        ),
        validate=_validate_closing,
        save=_save_closing,
        unique=("month",),
    )


def register_importers() -> None:
    """Register the two importers once; calling again keeps the ones already registered."""
    for importer in (hours_importer(), closing_importer()):
        if importing.find(importer.key) is None:
            importing.register(importer)
