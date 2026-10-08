"""Importação da semana pela planilha modelo do app (D10, D12, ISSUE-055).

O importador registra as colunas do app — uma linha ``Prev.`` por atividade e a
linha ``Real.`` opcional logo abaixo — com as obrigatórias e as regras da
``_Conferencia`` do app: semana ISO válida, ID exclusiva que não repete na semana,
Local, Empresa, Unidade, Fiscal e Encarregado dos cadastros do projeto, produção
prevista maior que zero e a soma dos sete dias batendo com ela (tolerância de
0,51). A conferência e a confirmação são o fluxo genérico da plataforma
(``core.importing``); a gravação passa pela fachada (``service.store_activity`` e
``service.import_done_days``), com a trilha única e a versão da linha.

O papel é o do projeto (D7): a permissão genérica do importador é a **leitura** do
módulo, e ``permissions.can_import`` (Planejador no projeto ou Admin) decide nas
rotas e na validação — a mesma regra do app, que dava ``importar`` só ao Planejador
e ao Admin. O fornecedor não passa nem na leitura do importador: o ``core.rbac``
recusa qualquer permissão geral para o vínculo.

Tradução do app: a linha ``Prev.`` vira a atividade (previsto dos sete dias, em
elaboração); a linha ``Real.`` vira o **turno dia** do realizado da atividade de
mesma semana e ID (o modelo do app não carregava o turno noite). A coluna ``Item``
é informativa: o item da semana é o próximo do projeto, como na criação pela tela.
O ID exclusivo é o ``unique_id``; o fiscal é o ``inspector``; o encarregado é o
``foreman``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from src.core import calendario, importing, rbac
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.export_document import ValueKind
from src.core.import_values import normalize_text
from src.core.importing import ImportColumn, ImportContext, Importer, RowCheck
from src.core.rbac import Permission
from src.modulos.configuracoes.registers import Option
from src.modulos.programacao_semanal import (
    calculations,
    permissions,
    repository,
    service,
    validation,
    weeks,
)
from src.modulos.programacao_semanal.models import Activity
from src.modulos.programacao_semanal.service import NewActivity

KEY = "programacao-semanal"
MODULE = "programacao_semanal"
TITLE = "Programação da semana"

ITEM_HEADER = "Item"
WEEK_HEADER = "Semana"
UNIQUE_ID_HEADER = "ID Exclusiva"
DESCRIPTION_HEADER = "Atividade Detalhada"
LOCATION_HEADER = "Local"
COMPANY_HEADER = "Empresa"
INSPECTOR_HEADER = "Fiscal"
FOREMAN_HEADER = "Encarregado"
HEADLINE_HEADER = "Prod. Prevista"
UNIT_HEADER = "Unidade"
KIND_HEADER = "Prev/Real"
DAY_HEADERS = calculations.DAY_LABELS

FIELD_ITEM = "item"
FIELD_WEEK = "semana"
FIELD_UNIQUE_ID = "id_exclusiva"
FIELD_DESCRIPTION = "atividade"
FIELD_LOCATION = "local"
FIELD_COMPANY = "empresa"
FIELD_INSPECTOR = "responsavel"
FIELD_FOREMAN = "encarregado"
FIELD_HEADLINE = "prod_prevista"
FIELD_UNIT = "unidade"
FIELD_KIND = "prev_real"
DAY_FIELDS = tuple(f"dia_{index}" for index in range(calculations.DAYS))

KIND_PREV = "Prev."
KIND_REAL = "Real."

WEEK_INVALID = "“{week}” não é uma semana válida. Use o formato S.30/2026."
DESCRIPTION_REQUIRED = "Atividade Detalhada não pode ficar em branco."
LOCATION_REQUIRED = "Local não pode ficar em branco."
COMPANY_REQUIRED = "Empresa não pode ficar em branco."
FOREMAN_REQUIRED = "Encarregado não pode ficar em branco."
HEADLINE_REQUIRED = "Produção prevista não pode ficar em branco."
UNIT_REQUIRED = "Unidade não pode ficar em branco."
HEADLINE_POSITIVE = "Produção prevista precisa ser maior que zero."
DAYS_ZERO = "Distribua a produção ao longo dos sete dias."
DAYS_MISMATCH = "A soma dos dias ({total:g}) não bate com a produção prevista ({headline:g})."
REGISTER_MISSING = "“{value}” não está no cadastro de {register}."
DUPLICATE = "A ID “{unique_id}” já existe na semana {week}."
FROZEN = "O realizado já foi aprovado pelo fiscal e não pode mudar."
ID_TOO_LONG = f"A ID exclusiva tem no máximo {validation.MAX_UNIQUE_ID_LENGTH} caracteres."

# (o campo, como o cadastro é nomeado na mensagem) das colunas do bloco.
_REGISTERS = (
    (FIELD_LOCATION, "locais"),
    (FIELD_COMPANY, "empresas"),
    (FIELD_UNIT, "unidades"),
    (FIELD_FOREMAN, "encarregados"),
)
_REQUIRED = (
    (FIELD_DESCRIPTION, DESCRIPTION_REQUIRED),
    (FIELD_LOCATION, LOCATION_REQUIRED),
    (FIELD_COMPANY, COMPANY_REQUIRED),
    (FIELD_FOREMAN, FOREMAN_REQUIRED),
    (FIELD_HEADLINE, HEADLINE_REQUIRED),
    (FIELD_UNIT, UNIT_REQUIRED),
)


def programacao_importer() -> Importer:
    """The Weekly Scheduling importer: the app's columns, validated line by line."""
    return Importer(
        key=KEY,
        title=TITLE,
        module=MODULE,
        columns=(
            ImportColumn(FIELD_ITEM, ITEM_HEADER, ValueKind.INTEGER, example="01"),
            ImportColumn(FIELD_WEEK, WEEK_HEADER, required=True, example="S.30/2026"),
            ImportColumn(FIELD_UNIQUE_ID, UNIQUE_ID_HEADER, required=True, example="PS1-ARM-015"),
            ImportColumn(
                FIELD_DESCRIPTION,
                DESCRIPTION_HEADER,
                example="Armação das paredes",
            ),
            ImportColumn(FIELD_LOCATION, LOCATION_HEADER, example="Frente 1"),
            ImportColumn(FIELD_COMPANY, COMPANY_HEADER, example="Empresa A"),
            ImportColumn(FIELD_INSPECTOR, INSPECTOR_HEADER, example="Ana Fiscal"),
            ImportColumn(FIELD_FOREMAN, FOREMAN_HEADER, example="João Encarregado"),
            ImportColumn(
                FIELD_HEADLINE,
                HEADLINE_HEADER,
                ValueKind.DECIMAL,
                example="1000",
            ),
            ImportColumn(FIELD_UNIT, UNIT_HEADER, example="m²"),
            ImportColumn(
                FIELD_KIND,
                KIND_HEADER,
                options=(KIND_PREV, KIND_REAL),
                required=True,
                example=KIND_PREV,
            ),
            *(
                ImportColumn(field, header, ValueKind.DECIMAL, example="180")
                for field, header in zip(DAY_FIELDS, DAY_HEADERS, strict=True)
            ),
        ),
        validate=_validate,
        save=_save,
        # The app's planejador/admin rule is a role of the project (D7): the generic
        # layer only asks the reading of the module, and ``can_import`` decides.
        permission=Permission.VIEW,
        unique=(FIELD_WEEK, FIELD_UNIQUE_ID, FIELD_KIND),
    )


def register_importers() -> None:
    """Register the module's importer once; calling again keeps the one already registered."""
    importer = programacao_importer()
    if importing.find(importer.key) is None:
        importing.register(importer)


# ── Step 2: the check of one line ────────────────────────────────────────


def _validate(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> RowCheck:
    """Check one line against the app's rules: registers, the week, the sums and the ID."""
    project_id = _project_of(context)
    _require_import(context.user, project_id)
    if values.get(FIELD_KIND) == KIND_REAL:
        return RowCheck(errors=_real_problems(session, values, project_id=project_id))
    return RowCheck(errors=_prev_problems(session, values, context=context, project_id=project_id))


def _prev_problems(
    session: Session, values: Mapping[str, Any], *, context: ImportContext, project_id: int
) -> tuple[str, ...]:
    """Every reason a ``Prev.`` line is blocked: filled in, known, adds up and unique."""
    problems: list[str] = []
    for field, message in _REQUIRED:
        value = values.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append(message)
    problems.extend(_identity_problems(values))
    problems.extend(_register_problems(session, values, context=context, project_id=project_id))
    problems.extend(_quantity_problems(values))
    problems.extend(_duplicate_problems(session, values, project_id=project_id))
    return tuple(problems)


def _real_problems(
    session: Session, values: Mapping[str, Any], *, project_id: int
) -> tuple[str, ...]:
    """A ``Real.`` line only needs its week and ID; the approved done work is frozen."""
    problems = list(_identity_problems(values))
    activity = _matching_activity(session, values, project_id=project_id)
    if activity is not None and activity.approval == calculations.APPROVAL_APPROVED:
        problems.append(FROZEN)
    return tuple(problems)


def _identity_problems(values: Mapping[str, Any]) -> list[str]:
    week = _text(values, FIELD_WEEK)
    problems = []
    if week and not weeks.is_valid(week):
        problems.append(WEEK_INVALID.format(week=week))
    if len(_text(values, FIELD_UNIQUE_ID)) > validation.MAX_UNIQUE_ID_LENGTH:
        problems.append(ID_TOO_LONG)
    return problems


def _register_problems(
    session: Session, values: Mapping[str, Any], *, context: ImportContext, project_id: int
) -> list[str]:
    """Every register of the line has to exist where the form offers it."""
    options = service.form_options(session, user=context.user, project_id=project_id)
    offered = {
        FIELD_LOCATION: options.locations,
        FIELD_COMPANY: options.companies,
        FIELD_UNIT: options.units,
        FIELD_FOREMAN: options.foremen,
        FIELD_INSPECTOR: options.inspectors,
    }
    problems = []
    for field, register in _REGISTERS:
        value = _text(values, field)
        if _id_for(offered[field], value) is None:
            problems.append(REGISTER_MISSING.format(value=value, register=register))
    inspector = _text(values, FIELD_INSPECTOR)
    if inspector and _id_for(offered[FIELD_INSPECTOR], inspector) is None:
        problems.append(REGISTER_MISSING.format(value=inspector, register="fiscais"))
    return problems


def _quantity_problems(values: Mapping[str, Any]) -> list[str]:
    """The app's account: a positive headline and the seven days adding up to it."""
    headline = _number(values.get(FIELD_HEADLINE))
    days = _days(values)
    problems = []
    if headline is not None and headline <= 0:
        problems.append(HEADLINE_POSITIVE)
    total = round(sum(days), 2)
    if total <= 0:
        problems.append(DAYS_ZERO)
    elif headline is not None and abs(total - headline) > validation.SUM_TOLERANCE:
        problems.append(DAYS_MISMATCH.format(total=total, headline=headline))
    return problems


def _duplicate_problems(
    session: Session, values: Mapping[str, Any], *, project_id: int
) -> list[str]:
    week = _canonical_week(_text(values, FIELD_WEEK))
    unique_id = _text(values, FIELD_UNIQUE_ID)
    if not week or not unique_id:
        return []
    taken = repository.unique_id_taken(
        session, project_id=project_id, week=week, unique_id=unique_id
    )
    if taken:
        return [DUPLICATE.format(unique_id=unique_id, week=week)]
    return []


# ── Step 3: the write of one line ────────────────────────────────────────


def _save(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    """Write one checked line through the facade: a new activity, or the done of one."""
    project_id = _project_of(context)
    _require_import(context.user, project_id)
    if values.get(FIELD_KIND) == KIND_REAL:
        _save_done(session, values, context, project_id=project_id)
        return
    _save_activity(session, values, context, project_id=project_id)


def _save_activity(
    session: Session, values: Mapping[str, Any], context: ImportContext, *, project_id: int
) -> None:
    """Create the activity of a ``Prev.`` line in elaboration, with the day plan."""
    options = service.form_options(session, user=context.user, project_id=project_id)
    week = _canonical_week(_text(values, FIELD_WEEK))
    unique_id = _text(values, FIELD_UNIQUE_ID)
    if repository.unique_id_taken(session, project_id=project_id, week=week, unique_id=unique_id):
        raise InvalidDataError(DUPLICATE.format(unique_id=unique_id, week=week))
    service.store_activity(
        session,
        author_id=context.user.id,
        new=NewActivity(
            project_id=project_id,
            company_id=_required_id(options.companies, values, FIELD_COMPANY, "empresas"),
            week=week,
            unique_id=unique_id,
            item=repository.next_item(session, project_id=project_id, week=week),
            description=_text(values, FIELD_DESCRIPTION),
            planned_headline=_number(values.get(FIELD_HEADLINE)) or 0.0,
            author_person_id=context.user.person_id,
            at=calendario.now(),
            location_id=_required_id(options.locations, values, FIELD_LOCATION, "locais"),
            unit_id=_required_id(options.units, values, FIELD_UNIT, "unidades"),
            inspector_id=_id_for(options.inspectors, _text(values, FIELD_INSPECTOR)),
            foreman_id=_required_id(options.foremen, values, FIELD_FOREMAN, "encarregados"),
            planned_days=tuple(_days(values)),
        ),
    )


def _save_done(
    session: Session, values: Mapping[str, Any], context: ImportContext, *, project_id: int
) -> None:
    """Apply the day shift of a ``Real.`` line to the activity of the same week and ID.

    A ``Real.`` line without its ``Prev.`` — in the file or already stored — is
    ignored, as the app ignores it with a warning.
    """
    activity = _matching_activity(session, values, project_id=project_id)
    if activity is None:
        return
    service.import_done_days(
        session,
        user=context.user,
        activity=activity,
        day_shift=tuple(_days(values)),
        at=calendario.now(),
    )


# ── Internals ────────────────────────────────────────────────────────────


def _project_of(context: ImportContext) -> int:
    """The project of the import: the Portfólio asks to choose one (D8)."""
    return context.scope.require_project()


def _require_import(user: rbac.User, project_id: int) -> None:
    """The import is the Planner of the project or the Admin, as the app's ``importar``."""
    if not permissions.can_import(user, project_id):
        raise AccessDeniedError(permissions.IMPORT_DENIED)


def _text(values: Mapping[str, Any], field: str) -> str:
    return str(values.get(field) or "").strip()


def _number(value: object) -> float | None:
    if value is None or value == "":
        return None
    return round(calculations.to_number(value), 2)


def _days(values: Mapping[str, Any]) -> list[float]:
    return calculations.seven_days([values.get(field) for field in DAY_FIELDS])


def _id_for(options: list[Option], label: str) -> int | None:
    wanted = normalize_text(label)
    if not wanted:
        return None
    return next((option.id for option in options if normalize_text(option.label) == wanted), None)


def _required_id(
    options: list[Option], values: Mapping[str, Any], field: str, register: str
) -> int:
    """The id of a register the check already approved; ``None`` here is a mistake, not a refusal."""
    chosen = _id_for(options, _text(values, field))
    if chosen is None:
        raise InvalidDataError(
            REGISTER_MISSING.format(value=_text(values, field), register=register)
        )
    return chosen


def _canonical_week(week: str) -> str:
    """The week as the product writes it (``S.1/2026`` becomes ``S.01/2026``)."""
    if not weeks.is_valid(week):
        return week
    return weeks.reference(*weeks.parts(week))


def _matching_activity(
    session: Session, values: Mapping[str, Any], *, project_id: int
) -> Activity | None:
    """The activity a ``Real.`` line completes, or ``None`` while it does not exist."""
    week = _canonical_week(_text(values, FIELD_WEEK))
    unique_id = _text(values, FIELD_UNIQUE_ID)
    if not week or not unique_id:
        return None
    return repository.find_activity_of_week(
        session, project_id=project_id, week=week, unique_id=unique_id
    )
