"""Os importadores de planilha do módulo Planejamento (D12, ISSUE-037).

O importador do avanço da EAP (``eap-avanco``): uma linha por pacote de trabalho, com o %
acumulado ou a quantidade executada (esta para o critério Unidades). A conferência lê cada
linha com ``validation.parse_import_rows`` — pacote inexistente, pacote de planejamento,
marco fora dos degraus, executado acima da linha de base e regressão são o motivo da recusa,
e a linha que não muda nada vira aviso —; a confirmação grava pela fachada
(``service.import_progress``), uma medição por linha aceita, datada com a data de referência
da importação e sem estorno. A data da medição viaja no ``ImportContext`` que a rota monta a
partir do formulário.

Os pacotes novos da EAP (``eap-pacotes``, ISSUE-038): uma linha por pacote de nível 3, com o
tipo, o critério, o modelo de etapas, a unidade e a quantidade, o peso, as datas da linha de
base, o responsável, a empresa executante e o item da EAC. A conferência checa cada linha
contra o projeto e os cadastros, com as mesmas regras dos formulários
(``service.revision_form_options`` e ``validation``); a confirmação genérica **recusa** porque
uma linha de pacote não é gravada sozinha: os pacotes entram juntos na revisão vinculada à SM,
criada pela tela da EAP (``service.create_revision``), que converte as linhas conferidas com
``revision_packages``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.core import importing
from src.core.errors import InvalidDataError
from src.core.export_document import ValueKind, format_value
from src.core.import_values import normalize_text
from src.core.importing import CheckedRow, ImportColumn, ImportContext, Importer, RowCheck
from src.modulos.planejamento import calculations, service, validation

PROGRESS_KEY = "eap-avanco"

MODULE = service.MODULE

CODE_FIELD = "codigo"
PERCENT_FIELD = "pct"
EXECUTED_FIELD = "executado"

CODE_HEADER = "Código do pacote"
PERCENT_HEADER = "Avanço acumulado (%)"
EXECUTED_HEADER = "Quantidade executada"

NO_CHANGE_MESSAGE = "o avanço já é {pct}: a linha não muda nada"


def _line(values: Mapping[str, Any]) -> validation.ImportRowInput:
    """A linha da planilha como a validação pura da importação a lê."""
    return validation.ImportRowInput(
        code=str(values.get(CODE_FIELD) or "").strip(),
        percent=values.get(PERCENT_FIELD),
        executed=values.get(EXECUTED_FIELD),
    )


def _validate(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> RowCheck:
    """Confere uma linha contra os pacotes do projeto, sem gravar."""
    packages = service.progress_import_packages(session, project_id=context.scope.require_project())
    result = validation.parse_import_rows((_line(values),), packages)[0]
    if result.error:
        return RowCheck(errors=(result.error,))
    if result.entries is None:
        current = packages[result.code].current
        return RowCheck(
            warnings=(NO_CHANGE_MESSAGE.format(pct=format_value(ValueKind.PERCENT, current, 1)),)
        )
    return RowCheck()


def _save(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    """Grava uma linha pela fachada, com a data de referência da importação como data da medição."""
    result = service.import_progress(
        session,
        user=context.user,
        scope=context.scope,
        rows=(_line(values),),
        measurement_date=context.reference_date,
        reference_date=context.reference_date,
    )
    if result.errors:
        raise InvalidDataError(result.errors[0])


def progress_importer() -> Importer:
    """O importador do avanço: o código do pacote e o % acumulado ou a quantidade executada."""
    return Importer(
        key=PROGRESS_KEY,
        title="Avanço da EAP",
        module=MODULE,
        columns=(
            ImportColumn(CODE_FIELD, CODE_HEADER, required=True, example="4.4.3"),
            ImportColumn(PERCENT_FIELD, PERCENT_HEADER, ValueKind.PERCENT, example="12,5"),
            ImportColumn(EXECUTED_FIELD, EXECUTED_HEADER, ValueKind.DECIMAL, example="120"),
        ),
        validate=_validate,
        save=_save,
        unique=(CODE_FIELD,),
    )


# ── Importação dos pacotes novos (ISSUE-038) ─────────────────────────────


PACKAGES_KEY = "eap-pacotes"


DESCRIPTION_FIELD = "descricao"


KIND_FIELD = "tipo"


CRITERION_FIELD = "criterio"


MODEL_FIELD = "modelo"


UNIT_FIELD = "unidade"


QUANTITY_FIELD = "quantidade"


WEIGHT_FIELD = "peso"


START_FIELD = "inicio"


FINISH_FIELD = "termino"


OWNER_FIELD = "responsavel"


COMPANY_FIELD = "empresa"


EAC_FIELD = "eac"


PACKAGE_CODE_HEADER = "Código"


DESCRIPTION_HEADER = "Descrição"


KIND_HEADER = "Tipo"


CRITERION_HEADER = "Critério de medição"


MODEL_HEADER = "Modelo de etapas"


UNIT_HEADER = "Unidade"


QUANTITY_HEADER = "Quantidade"


WEIGHT_HEADER = "Peso (% do projeto)"


START_HEADER = "Início LB"


FINISH_HEADER = "Término LB"


OWNER_HEADER = "Responsável"


COMPANY_HEADER = "Empresa executante"


EAC_HEADER = "Item da EAC"


PACKAGE_HEADERS = {
    CODE_FIELD: PACKAGE_CODE_HEADER,
    DESCRIPTION_FIELD: DESCRIPTION_HEADER,
    KIND_FIELD: KIND_HEADER,
    CRITERION_FIELD: CRITERION_HEADER,
    MODEL_FIELD: MODEL_HEADER,
    UNIT_FIELD: UNIT_HEADER,
    QUANTITY_FIELD: QUANTITY_HEADER,
    WEIGHT_FIELD: WEIGHT_HEADER,
    START_FIELD: START_HEADER,
    FINISH_FIELD: FINISH_HEADER,
    OWNER_FIELD: OWNER_HEADER,
    COMPANY_FIELD: COMPANY_HEADER,
    EAC_FIELD: EAC_HEADER,
}


CODE_MESSAGE = "informe o código com três níveis (ex.: 4.1.3)"


SUBAREA_MESSAGE = "a subárea {code} não existe na EAP do projeto"


EXISTING_MESSAGE = "o código {code} já existe na EAP do projeto"


OWNER_MESSAGE = "o responsável {name} não está no cadastro"


COMPANY_MESSAGE = "a empresa {name} não está no cadastro"


EAC_MESSAGE = "o item {code} da EAC não é de nível 3"


PACKAGES_CONFIRMATION_MESSAGE = (
    "a importação de pacotes da EAP é confirmada pela revisão vinculada à SM: "
    "envie a planilha pela tela da EAP"
)


def _messages(problems: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(
        f"{PACKAGE_HEADERS.get(field, field)}: {message}"
        for field, message in problems.items()
        if message
    )


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        found = Decimal(str(value))
    except ArithmeticError:
        return None
    return found if found.is_finite() else None


def _validate_package(
    session: Session, *, values: Mapping[str, Any], context: ImportContext
) -> RowCheck:
    """Confere uma linha contra a EAP do projeto, o cadastro e os parâmetros vigentes."""
    context.scope.require_project()
    options = service.revision_form_options(
        session, user=context.user, scope=context.scope, reference_date=context.reference_date
    )
    return RowCheck(errors=_messages(_package_problems(values, options=options)))


def _package_problems(
    values: Mapping[str, Any], *, options: service.EapFormOptions
) -> dict[str, str]:
    kind = str(values.get(KIND_FIELD) or "")
    criterion = str(values.get(CRITERION_FIELD) or "")
    return {
        CODE_FIELD: _code_problem(str(values.get(CODE_FIELD) or "").strip(), states=options.states),
        DESCRIPTION_FIELD: _description_problem(str(values.get(DESCRIPTION_FIELD) or "")),
        KIND_FIELD: (
            ""
            if kind in (calculations.WORK_PACKAGE, calculations.PLANNING_PACKAGE)
            else validation.PACKAGE_KIND_MESSAGE
        ),
        CRITERION_FIELD: _criterion_problem(kind, criterion),
        MODEL_FIELD: _model_problem(kind, criterion, values.get(MODEL_FIELD), options),
        UNIT_FIELD: _unit_problem(kind, criterion, values.get(UNIT_FIELD), options),
        QUANTITY_FIELD: _quantity_problem(kind, criterion, values.get(QUANTITY_FIELD)),
        WEIGHT_FIELD: _weight_problem(
            _decimal(values.get(WEIGHT_FIELD)),
            kind=kind,
            criterion=criterion,
            options=options,
        ),
        FINISH_FIELD: _finish_problem(values.get(START_FIELD), values.get(FINISH_FIELD)),
        OWNER_FIELD: _owner_problem(values.get(OWNER_FIELD), options),
        COMPANY_FIELD: _company_problem(values.get(COMPANY_FIELD), options),
        EAC_FIELD: _eac_problem(values.get(EAC_FIELD), options),
    }


def _code_problem(code: str, *, states: Mapping[str, validation.PackageState]) -> str:
    parts = code.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return CODE_MESSAGE
    parent = code.rsplit(".", 1)[0]
    state = states.get(parent)
    if state is None or state.level != validation.PARENT_LEVEL:
        return SUBAREA_MESSAGE.format(code=parent)
    if code in states:
        return EXISTING_MESSAGE.format(code=code)
    return ""


def _description_problem(description: str) -> str:
    if len(description) < validation.PACKAGE_DESCRIPTION_MIN:
        return validation.PACKAGE_DESCRIPTION_MESSAGE
    if len(description) > validation.PACKAGE_DESCRIPTION_MAX:
        return validation.TOO_LONG_MESSAGE.format(
            label="A descrição", limit=validation.PACKAGE_DESCRIPTION_MAX
        )
    return ""


def _criterion_problem(kind: str, criterion: str) -> str:
    if kind == calculations.PLANNING_PACKAGE:
        return ""
    if criterion not in calculations.EAP_CRITERIA:
        return validation.CRITERION_MESSAGE
    return ""


def _model_problem(
    kind: str, criterion: str, value: object, options: service.EapFormOptions
) -> str:
    if kind == calculations.PLANNING_PACKAGE or criterion != calculations.CRITERION_STEPS:
        return ""
    if _model_id(options, value):
        return ""
    return validation.STAGE_MODEL_MESSAGE


def _unit_problem(kind: str, criterion: str, value: object, options: service.EapFormOptions) -> str:
    if kind == calculations.PLANNING_PACKAGE or criterion != calculations.CRITERION_UNITS:
        return ""
    wanted = normalize_text(str(value or ""))
    if any(normalize_text(unit.code) == wanted for unit in options.units):
        return ""
    return validation.UNIT_MESSAGE


def _quantity_problem(kind: str, criterion: str, value: object) -> str:
    if kind == calculations.PLANNING_PACKAGE or criterion != calculations.CRITERION_UNITS:
        return ""
    quantity = _decimal(value)
    if quantity is None or quantity <= 0:
        return validation.QUANTITY_MESSAGE
    return ""


def _weight_problem(
    weight: Decimal | None,
    *,
    kind: str,
    criterion: str,
    options: service.EapFormOptions,
) -> str:
    if weight is None:
        return ""
    message = validation.package_weight_error(weight, maximum=options.limits.max_package_weight)
    if message:
        return message
    if (
        kind == calculations.WORK_PACKAGE
        and criterion == calculations.CRITERION_ESTIMATED
        and weight > options.limits.max_estimated_weight
    ):
        return validation.ESTIMATED_WEIGHT_MESSAGE.format(
            maximum=_plain(options.limits.max_estimated_weight)
        )
    return ""


def _finish_problem(start: object, finish: object) -> str:
    if not isinstance(start, date) or not isinstance(finish, date):
        return ""
    return validation.FINISH_MESSAGE if finish < start else ""


def _owner_problem(value: object, options: service.EapFormOptions) -> str:
    wanted = normalize_text(str(value or ""))
    if not wanted:
        return ""
    if any(normalize_text(item.name) == wanted for item in options.people):
        return ""
    return OWNER_MESSAGE.format(name=value)


def _company_problem(value: object, options: service.EapFormOptions) -> str:
    wanted = normalize_text(str(value or ""))
    if not wanted:
        return ""
    if any(normalize_text(item.name) == wanted for item in options.companies):
        return ""
    return COMPANY_MESSAGE.format(name=value)


def _eac_problem(value: object, options: service.EapFormOptions) -> str:
    code = str(value or "").strip()
    if not code or code in options.eac_codes:
        return ""
    return EAC_MESSAGE.format(code=code)


def _refuse_package_line(
    session: Session, *, values: Mapping[str, Any], context: ImportContext
) -> None:
    """A confirmação genérica não grava pacotes: a revisão vinculada à SM é quem grava."""
    del session, values, context
    raise InvalidDataError(PACKAGES_CONFIRMATION_MESSAGE)


def packages_importer() -> Importer:
    """O importador dos pacotes novos da EAP: conferidos como o formulário, gravados pela revisão."""
    return Importer(
        key=PACKAGES_KEY,
        title="Pacotes da EAP (nível 3)",
        module=MODULE,
        columns=(
            ImportColumn(CODE_FIELD, PACKAGE_CODE_HEADER, required=True, example="4.1.3"),
            ImportColumn(
                DESCRIPTION_FIELD,
                DESCRIPTION_HEADER,
                required=True,
                example="Pipe rack PR-03",
            ),
            ImportColumn(
                KIND_FIELD,
                KIND_HEADER,
                options=(calculations.WORK_PACKAGE, calculations.PLANNING_PACKAGE),
                required=True,
                example=calculations.WORK_PACKAGE,
            ),
            ImportColumn(
                CRITERION_FIELD,
                CRITERION_HEADER,
                options=calculations.EAP_CRITERIA,
                example=calculations.CRITERION_UNITS,
            ),
            ImportColumn(MODEL_FIELD, MODEL_HEADER, example="Engenharia (documentos)"),
            ImportColumn(UNIT_FIELD, UNIT_HEADER, example="m²"),
            ImportColumn(QUANTITY_FIELD, QUANTITY_HEADER, ValueKind.DECIMAL, example="120"),
            ImportColumn(
                WEIGHT_FIELD, WEIGHT_HEADER, ValueKind.PERCENT, required=True, example="1,5"
            ),
            ImportColumn(
                START_FIELD, START_HEADER, ValueKind.DATE, required=True, example="05/10/2026"
            ),
            ImportColumn(
                FINISH_FIELD, FINISH_HEADER, ValueKind.DATE, required=True, example="29/01/2027"
            ),
            ImportColumn(OWNER_FIELD, OWNER_HEADER, required=True, example="Carlos Nunes"),
            ImportColumn(COMPANY_FIELD, COMPANY_HEADER, example="Alfa Montagens"),
            ImportColumn(EAC_FIELD, EAC_HEADER, example="3.2.4"),
        ),
        validate=_validate_package,
        save=_refuse_package_line,
        unique=(CODE_FIELD,),
    )


def revision_packages(
    *,
    options: service.EapFormOptions,
    rows: Sequence[CheckedRow],
    change_code: str,
    justification: str,
) -> tuple[validation.NewPackageData, ...]:
    """As linhas conferidas como pacotes novos da revisão, com os vínculos do cadastro resolvidos.

    Cada linha passa de novo por ``validation.parse_package_form`` — a mesma porta dos
    formulários —, com os ids das pessoas e empresas e o id do modelo de etapas já resolvidos.
    """
    return tuple(
        _revision_package(
            row, options=options, change_code=change_code, justification=justification
        )
        for row in rows
    )


def _revision_package(
    row: CheckedRow,
    *,
    options: service.EapFormOptions,
    change_code: str,
    justification: str,
) -> validation.NewPackageData:
    values = row.values
    code = str(values.get(CODE_FIELD) or "").strip()
    raw = {
        validation.FIELD_RESOURCE: validation.REVISION,
        validation.FIELD_CHANGE: change_code,
        validation.FIELD_PACKAGE_KIND: str(values.get(KIND_FIELD) or ""),
        validation.FIELD_PARENT: _parent_code(code),
        DESCRIPTION_FIELD: str(values.get(DESCRIPTION_FIELD) or ""),
        validation.FIELD_CRITERION: str(values.get(CRITERION_FIELD) or ""),
        validation.FIELD_STAGE_MODEL: _model_id(options, values.get(MODEL_FIELD)),
        validation.FIELD_UNIT: str(values.get(UNIT_FIELD) or ""),
        validation.FIELD_QUANTITY: _plain(values.get(QUANTITY_FIELD)),
        validation.FIELD_WEIGHT: _plain(values.get(WEIGHT_FIELD)),
        validation.FIELD_START: _date_text(values.get(START_FIELD)),
        validation.FIELD_FINISH: _date_text(values.get(FINISH_FIELD)),
        validation.FIELD_OWNER: _person_id(options, values.get(OWNER_FIELD)),
        validation.FIELD_COMPANY: _company_id(options, values.get(COMPANY_FIELD)),
        validation.FIELD_EAC: str(values.get(EAC_FIELD) or ""),
        validation.FIELD_JUSTIFICATION: justification,
    }
    return replace(
        validation.parse_package_form(
            raw,
            packages=options.states,
            limits=options.limits,
            stage_models=options.stage_models,
        ),
        code=code,
    )


def _parent_code(code: str) -> str:
    return code.rsplit(".", 1)[0] if code.count(".") == 2 else ""


def _model_id(options: service.EapFormOptions, value: object) -> str:
    wanted = normalize_text(str(value or ""))
    if not wanted:
        return ""
    for model in options.stage_models:
        if wanted in (
            normalize_text(str(model.get("id", ""))),
            normalize_text(str(model.get("nome", ""))),
        ):
            return str(model.get("id", ""))
    return ""


def _person_id(options: service.EapFormOptions, value: object) -> str:
    wanted = normalize_text(str(value or ""))
    found = next((item.id for item in options.people if normalize_text(item.name) == wanted), None)
    return "" if found is None else str(found)


def _company_id(options: service.EapFormOptions, value: object) -> str:
    wanted = normalize_text(str(value or ""))
    if not wanted:
        return ""
    found = next(
        (item.id for item in options.companies if normalize_text(item.name) == wanted), None
    )
    return "" if found is None else str(found)


def _date_text(value: object) -> str:
    return value.isoformat() if isinstance(value, date) else ""


def _plain(value: object) -> str:
    """O número como texto, já que o formulário da validação lê texto."""
    return "" if value is None else str(value)


def register_importers() -> None:
    """Registra os importadores do módulo uma vez; chamar de novo mantém o que já está registrado."""
    for importer in (progress_importer(), packages_importer()):
        if importing.find(importer.key) is None:
            importing.register(importer)
