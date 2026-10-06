"""The forms of the HSE screens: what the person typed becomes an input, and a record becomes fields.

``parse_*`` read the form of a request (Portuguese field names) into the inputs of
``validation``; ``*_fields`` describe the fields a form draws, filled with a record or with what
was typed before a refusal. Nothing here talks to the database.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from src.modulos.configuracoes.service import RegisterOption
from src.modulos.hse import calculations, service, validation
from src.modulos.hse.models import SafetyInspectionItem
from src.modulos.hse.validation import (
    ChecklistItemInput,
    ClosingInput,
    HoursInput,
    InspectionInput,
    ObservationInput,
    TalkInput,
)

CHECKLIST_SLOTS = 10
CONFORMING = "sim"
NON_CONFORMING = "nao"

KIND_CLOSING = "mensal"
KIND_INSPECTION = "inspecao"
KIND_OBSERVATION = "observacao"
KIND_TALK = "dds"
RECORD_KINDS = (KIND_CLOSING, KIND_INSPECTION, KIND_OBSERVATION, KIND_TALK)


@dataclass(frozen=True)
class FormField:
    """One field of a form: its name, label, kind, current value, options and message."""

    name: str
    label: str
    kind: str = "text"
    value: str = ""
    options: tuple[tuple[str, str], ...] = ()
    required: bool = True
    locked: bool = False
    full: bool = False
    hint: str = ""
    error: str = ""
    maximum: str = ""

    def with_error(self, message: str) -> FormField:
        """The same field carrying the message of a refusal."""
        return FormField(
            name=self.name,
            label=self.label,
            kind=self.kind,
            value=self.value,
            options=self.options,
            required=self.required,
            locked=self.locked,
            full=self.full,
            hint=self.hint,
            error=message,
            maximum=self.maximum,
        )


@dataclass(frozen=True)
class ChecklistRow:
    """One slot of the checklist: the description, whether it is conforming and the note."""

    index: int
    description: str = ""
    conforming: str = CONFORMING
    note: str = ""


def _text(form: Mapping[str, str], name: str) -> str:
    return (form.get(name) or "").strip()


def _opt_id(form: Mapping[str, str], name: str) -> int | None:
    return validation.parse_id(form.get(name))


def parse_hours(form: Mapping[str, str], *, project_id: int) -> HoursInput:
    """The HHT form: month, company, average headcount and hours."""
    return HoursInput(
        project_id=project_id,
        month=calculations.parse_month(form.get("mes")),
        company_id=_opt_id(form, "empresa"),
        headcount=validation.parse_count(form.get("efetivo_medio")),
        hours=validation.parse_decimal(form.get("hht")),
        version=form.get("versao"),
    )


def parse_closing(form: Mapping[str, str], *, project_id: int) -> ClosingInput:
    """The monthly closing form: the month and the six counts."""
    return ClosingInput(
        project_id=project_id,
        month=calculations.parse_month(form.get("mes")),
        deviations=validation.parse_count(form.get("desvios")),
        observations=validation.parse_count(form.get("observacoes")),
        planned_dds=validation.parse_count(form.get("dds_programados")),
        held_dds=validation.parse_count(form.get("dds_realizados")),
        inspected_items=validation.parse_count(form.get("itens_inspecionados")),
        conforming_items=validation.parse_count(form.get("itens_conformes")),
        version=form.get("versao"),
    )


def checklist_of(form: Mapping[str, str]) -> tuple[ChecklistRow, ...]:
    """The slots of the checklist as typed, in order, blank ones included."""
    rows = []
    for index in range(1, CHECKLIST_SLOTS + len(form) + 1):
        if f"item_descricao_{index}" not in form and index > CHECKLIST_SLOTS:
            break
        rows.append(
            ChecklistRow(
                index=index,
                description=_text(form, f"item_descricao_{index}"),
                conforming=_text(form, f"item_conforme_{index}") or CONFORMING,
                note=_text(form, f"item_observacao_{index}"),
            )
        )
    return tuple(rows)


def parse_inspection(form: Mapping[str, str], *, project_id: int) -> InspectionInput:
    """The inspection form: date, area, people and the filled slots of the checklist."""
    items = tuple(
        ChecklistItemInput(
            description=row.description,
            conforming=row.conforming == CONFORMING,
            note=row.note,
        )
        for row in checklist_of(form)
        if row.description or row.note
    )
    return InspectionInput(
        project_id=project_id,
        inspected_on=validation.parse_date(form.get("data")),
        area=_text(form, "area"),
        responsible_id=_opt_id(form, "responsavel"),
        company_id=_opt_id(form, "empresa"),
        note=_text(form, "observacao"),
        items=items,
        version=form.get("versao"),
    )


def parse_observation(form: Mapping[str, str], *, project_id: int) -> ObservationInput:
    """The observation form: date, area, kind, description, people and status."""
    return ObservationInput(
        project_id=project_id,
        observed_on=validation.parse_date(form.get("data")),
        area=_text(form, "area"),
        kind=_text(form, "tipo"),
        description=_text(form, "descricao"),
        responsible_id=_opt_id(form, "responsavel"),
        company_id=_opt_id(form, "empresa"),
        observed_id=_opt_id(form, "observado"),
        status=_text(form, "situacao") or validation.OBSERVATION_OPEN,
        version=form.get("versao"),
    )


def parse_talk(form: Mapping[str, str], *, project_id: int) -> TalkInput:
    """The DDS form: date, topic, who led it, company and participants."""
    return TalkInput(
        project_id=project_id,
        held_on=validation.parse_date(form.get("data")),
        topic=_text(form, "tema"),
        responsible_id=_opt_id(form, "responsavel"),
        participants=validation.parse_count(form.get("participantes")),
        company_id=_opt_id(form, "empresa"),
        version=form.get("versao"),
    )


# ── Fields ───────────────────────────────────────────────────────────────────────────────────


def _options(items: Sequence[tuple[int, str]]) -> tuple[tuple[str, str], ...]:
    return tuple((str(item_id), name) for item_id, name in items)


def _companies(session_options: Sequence[RegisterOption]) -> tuple[tuple[str, str], ...]:
    return _options([(item.id, item.name) for item in session_options])


def hours_fields(
    values: Mapping[str, str],
    *,
    companies: Sequence[RegisterOption],
    reference_date: date,
    locked: bool,
) -> tuple[FormField, ...]:
    """The fields of the HHT form; editing locks the month and the company."""
    return (
        FormField(
            "mes",
            "Mês",
            "month",
            values.get("mes") or calculations.month_label(reference_date),
            locked=locked,
            maximum=calculations.month_label(reference_date),
        ),
        FormField(
            "empresa",
            "Empresa",
            "select",
            values.get("empresa", ""),
            options=_companies(companies),
            locked=locked,
        ),
        FormField(
            "efetivo_medio",
            "Efetivo médio",
            "number",
            values.get("efetivo_medio", ""),
            hint=f"De 0 a {validation.MAX_HEADCOUNT}.",
        ),
        FormField(
            "hht",
            "Horas-homem trabalhadas (HHT)",
            "number",
            values.get("hht", ""),
            hint="0 ou mais.",
        ),
    )


def closing_fields(
    values: Mapping[str, str], *, reference_date: date, locked: bool
) -> tuple[FormField, ...]:
    """The fields of the monthly closing form; editing locks the month."""
    counts = (
        ("dds_programados", "DDS programados"),
        ("dds_realizados", "DDS realizados"),
        ("itens_inspecionados", "Itens de checklist inspecionados"),
        ("itens_conformes", "Itens conformes"),
        ("observacoes", "Observações comportamentais"),
    )
    return (
        FormField(
            "mes",
            "Mês",
            "month",
            values.get("mes") or calculations.month_label(reference_date),
            locked=locked,
            maximum=calculations.month_label(reference_date),
        ),
        *(FormField(name, label, "number", values.get(name, "0")) for name, label in counts),
        FormField(
            "desvios",
            "Desvios (atos e condições inseguras)",
            "number",
            values.get("desvios", "0"),
            hint="Nível 5 da pirâmide de segurança.",
        ),
    )


def _person_field(
    name: str,
    label: str,
    values: Mapping[str, str],
    people: Sequence[RegisterOption],
    *,
    required: bool,
) -> FormField:
    return FormField(
        name,
        label,
        "select",
        values.get(name, ""),
        options=_companies(people),
        required=required,
    )


def inspection_fields(
    values: Mapping[str, str],
    *,
    people: Sequence[RegisterOption],
    companies: Sequence[RegisterOption],
    reference_date: date,
) -> tuple[FormField, ...]:
    """The fields of the inspection form (the checklist is drawn apart)."""
    return (
        FormField(
            "data",
            "Data",
            "date",
            values.get("data") or reference_date.isoformat(),
            maximum=reference_date.isoformat(),
        ),
        FormField("area", "Área", "text", values.get("area", "")),
        _person_field("responsavel", "Responsável", values, people, required=True),
        _person_field("empresa", "Empresa", values, companies, required=False),
        FormField(
            "observacao",
            "Observação",
            "textarea",
            values.get("observacao", ""),
            required=False,
            full=True,
        ),
    )


def observation_fields(
    values: Mapping[str, str],
    *,
    people: Sequence[RegisterOption],
    companies: Sequence[RegisterOption],
    reference_date: date,
    show_observed: bool,
) -> tuple[FormField, ...]:
    """The fields of the observation form; the observed person is asked only of who may read it."""
    fields = [
        FormField(
            "data",
            "Data",
            "date",
            values.get("data") or reference_date.isoformat(),
            maximum=reference_date.isoformat(),
        ),
        FormField("area", "Área", "text", values.get("area", "")),
        FormField(
            "tipo",
            "Tipo",
            "select",
            values.get("tipo", ""),
            options=tuple((kind, kind) for kind in validation.OBSERVATION_KINDS),
        ),
        FormField(
            "situacao",
            "Situação",
            "select",
            values.get("situacao") or validation.OBSERVATION_OPEN,
            options=tuple((status, status) for status in validation.OBSERVATION_STATUSES),
        ),
        _person_field("responsavel", "Responsável", values, people, required=True),
        _person_field("empresa", "Empresa", values, companies, required=False),
    ]
    if show_observed:
        fields.append(
            _person_field("observado", "Pessoa observada", values, people, required=False)
        )
    fields.append(
        FormField("descricao", "Descrição", "textarea", values.get("descricao", ""), full=True)
    )
    return tuple(fields)


def talk_fields(
    values: Mapping[str, str],
    *,
    people: Sequence[RegisterOption],
    companies: Sequence[RegisterOption],
    reference_date: date,
) -> tuple[FormField, ...]:
    """The fields of the DDS form."""
    return (
        FormField(
            "data",
            "Data",
            "date",
            values.get("data") or reference_date.isoformat(),
            maximum=reference_date.isoformat(),
        ),
        FormField("tema", "Tema", "text", values.get("tema", "")),
        _person_field("responsavel", "Responsável", values, people, required=True),
        _person_field("empresa", "Empresa", values, companies, required=False),
        FormField("participantes", "Participantes", "number", values.get("participantes", "")),
    )


def checklist_rows_of(
    items: Sequence[SafetyInspectionItem] | None, form_rows: Sequence[ChecklistRow] | None = None
) -> tuple[ChecklistRow, ...]:
    """The slots of the checklist: what was typed, else the items of the record, plus blank slots."""
    if form_rows:
        return tuple(form_rows)
    rows = [
        ChecklistRow(
            index=position,
            description=item.description,
            conforming=CONFORMING if item.conforming else NON_CONFORMING,
            note=item.note or "",
        )
        for position, item in enumerate(items or (), start=1)
    ]
    slots = max(CHECKLIST_SLOTS, len(rows) + 2)
    rows.extend(ChecklistRow(index=index) for index in range(len(rows) + 1, slots + 1))
    return tuple(rows)


def attach_errors(fields: Sequence[FormField], errors: Mapping[str, str]) -> tuple[FormField, ...]:
    """The fields with the message of each refusal under its field."""
    return tuple(
        field.with_error(errors[field.name]) if field.name in errors else field for field in fields
    )


def values_of_hours(row: service.HoursRow) -> dict[str, str]:
    """The values an HHT form shows for a record."""
    return {
        "mes": calculations.month_label(row.month),
        "empresa": str(row.company_id),
        "efetivo_medio": str(row.headcount),
        "hht": _plain_number(row.hours),
        "versao": str(row.version),
    }


def values_of_closing(row: service.ClosingRow) -> dict[str, str]:
    """The values a monthly closing form shows for a record."""
    return {
        "mes": calculations.month_label(row.month),
        "dds_programados": str(row.planned_dds),
        "dds_realizados": str(row.held_dds),
        "itens_inspecionados": str(row.inspected_items),
        "itens_conformes": str(row.conforming_items),
        "observacoes": str(row.observations),
        "desvios": str(row.deviations),
        "versao": str(row.version),
    }


def values_of_inspection(row: service.InspectionRow) -> dict[str, str]:
    """The values an inspection form shows for a record."""
    return {
        "data": row.inspected_on.isoformat(),
        "area": row.area,
        "responsavel": str(row.responsible_id),
        "empresa": "" if row.company_id is None else str(row.company_id),
        "observacao": row.note,
        "versao": str(row.version),
    }


def values_of_observation(row: service.ObservationRow) -> dict[str, str]:
    """The values an observation form shows for a record."""
    return {
        "data": row.observed_on.isoformat(),
        "area": row.area,
        "tipo": row.kind,
        "situacao": row.status,
        "responsavel": str(row.responsible_id),
        "empresa": "" if row.company_id is None else str(row.company_id),
        "observado": "" if row.observed_id is None else str(row.observed_id),
        "descricao": row.description,
        "versao": str(row.version),
    }


def values_of_talk(row: service.TalkRow) -> dict[str, str]:
    """The values a DDS form shows for a record."""
    return {
        "data": row.held_on.isoformat(),
        "tema": row.topic,
        "responsavel": str(row.responsible_id),
        "empresa": "" if row.company_id is None else str(row.company_id),
        "participantes": str(row.participants),
        "versao": str(row.version),
    }


def _plain_number(value: object) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
