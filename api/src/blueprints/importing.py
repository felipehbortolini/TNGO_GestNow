"""Import blueprint: the four routes of the spreadsheet import every module reuses (D12, ISSUE-018).

A module registers its ``Importer`` (``core.importing``) and puts the import where it wants it; the
routes are generic and take the importer from the ``chave`` of the address:

* ``GET /api/importacao/{chave}`` is the screen of the steps, a fragment: the button of the model,
  what each column asks, the upload form and the place where the check will appear;
* ``GET /api/importacao/{chave}/modelo`` is the model, a download (the download exception of the
  Padrão: ``file_route`` and ``core.excel.excel_response``; the button ``data-tn-excel`` of
  ``ds/ui.js`` takes it, with the scope);
* ``POST /api/importacao/{chave}/conferir`` receives the file (``multipart/form-data``) and answers
  the check line by line; a file that is not a spreadsheet is 422 with the message in the place of
  the check. **It writes nothing.**
* ``POST /api/importacao/{chave}/confirmar`` receives the same file, the digest of the one that was
  checked and the acknowledgement, and answers the result: every line without error written, or
  none (422 with the line that was refused).

Between the steps the server keeps nothing: the form that holds the file sends it again at the
confirmation, and ``core.importing.confirm`` reads and checks it once more before writing.
Cancelling is closing the check; there is nothing to undo. The rules are those of
``core.importing``: the routes only read the request, call it and draw the answer.
"""

from collections.abc import Mapping
from typing import Any

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario, importing
from src.core.excel import excel_response
from src.core.export_document import ValueKind, format_value
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.core.spreadsheet_reader import MAX_DATA_ROWS, MAX_FILE_BYTES, MEGABYTE

bp = func.Blueprint()

STEPS_ROUTE = "importacao/{chave}"
MODEL_ROUTE = "importacao/{chave}/modelo"
CHECK_ROUTE = "importacao/{chave}/conferir"
CONFIRM_ROUTE = "importacao/{chave}/confirmar"

STEPS_TEMPLATE = "comum/importacao.html"
CHECK_TEMPLATE = "comum/importacao_conferencia.html"
RESULT_TEMPLATE = "comum/importacao_resultado.html"

KEY_PARAMETER = "chave"
CHECKED_FIELD = "conferido"
ACKNOWLEDGED_FIELD = "ciente"
ACKNOWLEDGED_VALUE = "sim"

# Importing is writing: the route asks for it, and the importer asks for its module and for more
# when it needs (``core.importing.authorize``). A supplier has no general permission: refused.
IMPORT_ACCESS = Access(permission=Permission.WRITE)

# The kinds of column the preview aligns to the right.
_NUMERIC_KINDS = frozenset(
    {ValueKind.INTEGER, ValueKind.DECIMAL, ValueKind.PERCENT, ValueKind.MONEY}
)


@bp.route(route=STEPS_ROUTE, methods=["GET"])
@fragment_route(access=IMPORT_ACCESS)
def import_steps(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The steps of the import: the model, the upload form and the place of the check."""
    importer = _importer_of(req)
    importing.authorize(importer, context.user)
    return AlpineAjaxResponse(
        template_name=STEPS_TEMPLATE, context=_steps_context(importer), request=req
    )


@bp.route(route=MODEL_ROUTE, methods=["GET"])
@file_route(access=IMPORT_ACCESS)
def import_template(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The model of the importer: the empty workbook with the header and the instructions."""
    importer = _importer_of(req)
    document = importing.model_document(
        session, importer=importer, context=_import_context(context)
    )
    return excel_response(document)


@bp.route(route=CHECK_ROUTE, methods=["POST"])
@fragment_route(access=IMPORT_ACCESS)
def import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Read the file and answer what each line will do; nothing is written."""
    importer = _importer_of(req)
    preview = importing.check(
        session, importer=importer, upload=_upload_of(req), context=_import_context(context)
    )
    return AlpineAjaxResponse(
        template_name=CHECK_TEMPLATE, context=_check_context(importer, preview), request=req
    )


@bp.route(route=CONFIRM_ROUTE, methods=["POST"])
@fragment_route(access=IMPORT_ACCESS)
def import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Write every line without error, all or none, and answer what entered and what did not."""
    importer = _importer_of(req)
    result = importing.confirm(
        session,
        importer=importer,
        upload=_upload_of(req),
        context=_import_context(context),
        confirmation=importing.Confirmation(
            checked_digest=(req.form.get(CHECKED_FIELD) or "").strip() or None,
            acknowledged=req.form.get(ACKNOWLEDGED_FIELD) == ACKNOWLEDGED_VALUE,
        ),
    )
    return AlpineAjaxResponse(
        template_name=RESULT_TEMPLATE,
        context={"resultado": result, "importador": importer.title},
        request=req,
        toast=_notice(result),
        toast_tipo="aviso" if result.skipped else "ok",
    )


def _importer_of(req: func.HttpRequest) -> importing.Importer:
    """The importer the address names, or 422 when no module registered it."""
    return importing.require((req.route_params.get(KEY_PARAMETER) or "").strip())


def _import_context(context: RequestContext) -> importing.ImportContext:
    """Who imports, in which scope and today: the only place of the flow that reads the clock."""
    return importing.ImportContext(
        user=context.user, scope=context.scope, reference_date=calendario.today()
    )


def _upload_of(req: func.HttpRequest) -> importing.Upload:
    """The file of the form; at most one byte over the limit is read, so a huge one costs nothing."""
    sent = req.files.get(attachments.FILE_FIELD)
    if sent is None:
        return importing.Upload(name=None, content=b"")
    return importing.Upload(name=sent.filename, content=sent.stream.read(MAX_FILE_BYTES + 1))


def _notice(result: importing.ImportResult) -> str:
    """The toast: how many lines entered and, when an error left some out, how many did not."""
    written = len(result.written)
    imported = "1 linha importada" if written == 1 else f"{written} linhas importadas"
    if not result.skipped:
        return f"{imported}."
    skipped = len(result.skipped)
    left_out = "1 com erro não entrou" if skipped == 1 else f"{skipped} com erro não entraram"
    return f"{imported}; {left_out}."


def _urls(importer: importing.Importer) -> dict[str, str]:
    base = f"/api/{STEPS_ROUTE.format(chave=importer.key)}"
    return {
        "modelo_url": f"{base}/modelo",
        "conferir_url": f"{base}/conferir",
        "confirmar_url": f"{base}/confirmar",
    }


def _steps_context(importer: importing.Importer) -> dict[str, Any]:
    """What the steps fragment prints: the importer, its columns as the model asks them, the limits."""
    return {
        "titulo": importer.title,
        "colunas": [
            {
                "cabecalho": column.header,
                "obrigatoria": column.required,
                "formato": column.format_hint,
                "exemplo": column.example,
            }
            for column in importer.columns
        ],
        "limite_mb": MAX_FILE_BYTES // MEGABYTE,
        "limite_linhas": format_value(ValueKind.INTEGER, MAX_DATA_ROWS),
        "campo_arquivo": attachments.FILE_FIELD,
        **_urls(importer),
    }


def _check_context(
    importer: importing.Importer, preview: importing.ImportPreview
) -> Mapping[str, Any]:
    """What the check fragment prints: the preview, the counts and where the confirmation goes."""
    return {
        "arquivo": preview.file_name,
        "preview": preview,
        "colunas": [
            {"cabecalho": column.header, "numerica": column.kind in _NUMERIC_KINDS}
            for column in preview.columns
        ],
        "lidas": len(preview.rows),
        "vao_gravar": len(preview.writable_rows),
        "com_aviso": len(preview.warning_rows),
        "com_erro": len(preview.error_rows),
        "campo_conferido": CHECKED_FIELD,
        "campo_ciente": ACKNOWLEDGED_FIELD,
        "valor_ciente": ACKNOWLEDGED_VALUE,
        **_urls(importer),
    }
