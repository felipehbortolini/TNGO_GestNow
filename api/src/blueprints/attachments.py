"""Attachments blueprint: the upload, the list and the download of the files of a record (D5a, D14).

The three routes are the platform side of the attachments of every module
(ISSUE-012). ``origem`` is the table of the record, as the module that owns it
registered it in ``attachment_origins``; ``registro`` is its id.

* ``GET /api/anexos?origem=<tabela>&registro=<id>`` is the list of a record: the
  upload component of the Design System and the table of its attachments (name,
  size, who sent it, when) in one fragment, which a screen asks for where it
  wants attachments;
* ``POST /api/anexos/enviar`` receives the file (``multipart/form-data``) and
  answers the same fragment, refreshed; a file over the limit or of a type
  outside the list is 422 with the message under the field;
* ``GET /api/anexos/{anexo_id}/baixar`` is the download, the one route of the
  product that answers a file and not a fragment (the download exception of the
  Padrão): the browser opens it as a plain link, and it checks the permission of
  the record the file belongs to.

Writing is a rule of ``core.attachments``, the facade of the platform: the
routes only read the request, call it and draw the answer.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario
from src.core.errors import InvalidDataError
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import (
    Access,
    RequestContext,
    file_route,
    fragment_route,
    plain_text_response,
)

bp = func.Blueprint()

TEMPLATE = "comum/anexos.html"
UPLOADED_NOTICE = "Anexo enviado."
NOT_FOUND_MESSAGE = "Anexo não encontrado."
INVALID_ATTACHMENT_MESSAGE = "Informe o anexo que deseja baixar."
INVALID_RECORD_MESSAGE = "Informe o registro ao qual o anexo pertence."

DATE_TIME_FORMAT = "%d/%m/%Y %H:%M"

# An id never has more digits than this; the cap keeps ``int`` and the database
# away from absurd input that comes straight from a URL or a form.
MAX_ID_DIGITS = 18

# What a header may carry as the plain name of the file: everything else becomes
# ``_`` here, and the real name travels percent-encoded beside it (RFC 6266).
_PLAIN_NAME_CHARACTER = re.compile(r"[A-Za-z0-9 ._()\[\]-]")
FALLBACK_NAME = "anexo"


@dataclass(frozen=True)
class RecordRef:
    """The record the attachments belong to: the table of its origin type and its id."""

    table: str
    id: int


@dataclass(frozen=True)
class AttachmentRow:
    """One line of the table, already as it reads on screen."""

    id: int
    name: str
    size: str
    uploaded_by: str
    uploaded_at: str
    url: str


@bp.route(route="anexos", methods=["GET"])
@fragment_route(access=Access())
def list_attachments(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The attachments of a record, with the upload component for who may send."""
    record = _record_of(req.params)
    panel = _panel(session, context, record)
    return AlpineAjaxResponse(
        template_name=TEMPLATE, context=_context(panel, record, errors={}), request=req
    )


@bp.route(route="anexos/enviar", methods=["POST"])
@fragment_route(access=Access(permission=Permission.WRITE))
def upload_attachment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Receive the file of a record and answer the list again, or 422 with the message under the field."""
    record = _record_of(req.form)
    sent = req.files.get(attachments.FILE_FIELD)
    new = attachments.NewAttachment(
        origin_table=record.table,
        origin_record_id=record.id,
        file_name=sent.filename if sent is not None else None,
        content=sent.stream.read() if sent is not None else b"",
    )
    try:
        attachments.upload(session, user=context.user, new=new, reference_date=calendario.today())
    except InvalidDataError as error:
        # Nothing was written: the list is read again to answer the form with its message.
        return AlpineAjaxResponse(
            template_name=TEMPLATE,
            context=_context(_panel(session, context, record), record, _field_errors(error)),
            request=req,
            status_code=422,
        )
    return AlpineAjaxResponse(
        template_name=TEMPLATE,
        context=_context(_panel(session, context, record), record, errors={}),
        request=req,
        toast=UPLOADED_NOTICE,
    )


@bp.route(route="anexos/{anexo_id}/baixar", methods=["GET"])
@file_route(access=Access())
def download_attachment(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Hand the file to the browser, with its original name, if the user may read its record."""
    attachment_id = _parse_id(req.route_params.get("anexo_id"))
    if attachment_id is None:
        raise InvalidDataError(INVALID_ATTACHMENT_MESSAGE)
    download = attachments.open_download(session, user=context.user, attachment_id=attachment_id)
    if download is None:
        return plain_text_response(NOT_FOUND_MESSAGE, status_code=404)
    return func.HttpResponse(
        download.content,
        status_code=200,
        headers={
            "Content-Type": download.mime_type,
            "Content-Disposition": _content_disposition(download.name),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
        mimetype=download.mime_type,
    )


def _record_of(source: Mapping[str, str]) -> RecordRef:
    """The record the request is about, as the query or the form names it."""
    table = (source.get("origem") or "").strip()
    record_id = _parse_id(source.get("registro"))
    if not table or record_id is None:
        raise InvalidDataError(INVALID_RECORD_MESSAGE)
    return RecordRef(table=table, id=record_id)


def _parse_id(raw: str | None) -> int | None:
    """The id in the text, or ``None`` when it is not plain digits within a sane size."""
    text = (raw or "").strip()
    if not (text.isascii() and text.isdigit()) or len(text) > MAX_ID_DIGITS:
        return None
    return int(text)


def _panel(
    session: Session, context: RequestContext, record: RecordRef
) -> attachments.AttachmentPanel:
    return attachments.panel(
        session,
        user=context.user,
        origin_table=record.table,
        origin_record_id=record.id,
        reference_date=calendario.today(),
    )


def _field_errors(error: InvalidDataError) -> dict[str, str]:
    """The messages of the refusal by field; a refusal with a single message is general."""
    if isinstance(error.detail, Mapping):
        return dict(error.detail)
    return {"geral": str(error.detail)}


def _context(
    panel: attachments.AttachmentPanel, record: RecordRef, errors: Mapping[str, str]
) -> dict[str, object]:
    """What the fragment prints: the rows, what the user may do, the limits and the messages."""
    limits = panel.limits
    return {
        "origem": record.table,
        "registro": record.id,
        "linhas": [_row(entry) for entry in panel.entries],
        "pode_ver": panel.can_view,
        "pode_enviar": panel.can_upload,
        "aviso_restrito": attachments.RESTRICTED_NOTICE,
        "limite_mb": limits.max_megabytes_text,
        "tipos": ", ".join(limits.types),
        "aceitos": ",".join(f".{extension}" for extension in limits.extensions),
        "erro_arquivo": errors.get(attachments.FILE_FIELD, ""),
        "erros_gerais": [
            message
            for field, message in errors.items()
            if field != attachments.FILE_FIELD and message
        ],
    }


def _row(entry: attachments.AttachmentEntry) -> AttachmentRow:
    moment = calendario.in_product_timezone(entry.uploaded_at)
    return AttachmentRow(
        id=entry.id,
        name=entry.name,
        size=attachments.format_size(entry.size_bytes),
        uploaded_by=entry.uploaded_by,
        uploaded_at=moment.strftime(DATE_TIME_FORMAT),
        url=f"/api/anexos/{entry.id}/baixar",
    )


def _content_disposition(name: str) -> str:
    """``attachment`` with the original name: a plain fallback and the UTF-8 name (RFC 6266)."""
    plain = "".join(char if _PLAIN_NAME_CHARACTER.fullmatch(char) else "_" for char in name)
    encoded = quote(name, safe="")
    return "; ".join(
        ["attachment", f'filename="{plain or FALLBACK_NAME}"', f"filename*=UTF-8''{encoded}"]
    )
