"""Os importadores de planilha do módulo Planejamento (D12, ISSUE-037).

O importador do avanço da EAP (``eap-avanco``): uma linha por pacote de trabalho, com o %
acumulado ou a quantidade executada (esta para o critério Unidades). A conferência lê cada
linha com ``validation.parse_import_rows`` — pacote inexistente, pacote de planejamento,
marco fora dos degraus, executado acima da linha de base e regressão são o motivo da recusa,
e a linha que não muda nada vira aviso —; a confirmação grava pela fachada
(``service.import_progress``), uma medição por linha aceita, datada com a data de referência
da importação e sem estorno. A data da medição viaja no ``ImportContext`` que a rota monta a
partir do formulário.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from src.core import importing
from src.core.errors import InvalidDataError
from src.core.export_document import ValueKind, format_value
from src.core.importing import ImportColumn, ImportContext, Importer, RowCheck
from src.modulos.planejamento import service, validation

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


def register_importers() -> None:
    """Registra o importador do módulo uma vez; chamar de novo mantém o que já está registrado."""
    importer = progress_importer()
    if importing.find(importer.key) is None:
        importing.register(importer)
