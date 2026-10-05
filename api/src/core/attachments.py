"""Attachments of the records: upload, list, download and evidence (D5a, HU-140 to HU-143, ISSUE-012).

The platform owns the ``anexo`` table and the file port; the module that owns
the record an attachment belongs to owns the question *may this person read it?*
(``attachment_origins``). Every function here asks that question before it does
anything, so the permission of an attachment is always the permission of its
record, and an attachment of personal data (Q35) is read only by who may read
restricted data.

* ``upload`` validates against the limits of the Anexos group in force, writes
  the metadata with its trail line in the request's transaction and, last,
  keeps the file: a file that could not be kept rolls the row back with it;
* ``panel`` is what the list of a record shows to one user: name, size, who
  sent it and when, and whether that user may send and see;
* ``open_download`` hands back the file with the name it was sent with, or
  ``None`` when there is nothing to hand back;
* ``has_evidence`` is what "evidência obrigatória" means for the modules: the
  record has at least one attachment.

The limits are the ``anexos`` group of the parameters in force on the reference
date (25 MB; PDF, JPG, PNG, DOCX, XLSX, PPTX, DWG and ZIP at the start): a new
version of the group changes the next upload, not the attachments already kept.
Size and type are refused with 422 and the message for the field ``arquivo``.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from src.core import attachment_origins, audit, calendario, file_storage, rbac
from src.core.attachment_origins import OriginRecord, OriginType
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.file_storage import FileStorage, StoredFileNotFoundError
from src.core.models import Attachment
from src.core.rbac import Permission, User
from src.modulos.configuracoes import service as configuracoes

logger = logging.getLogger(__name__)

# The name of the field of the form the messages of the file belong to.
FILE_FIELD = "arquivo"

ATTACHMENTS_GROUP = "anexos"
SIZE_KEY = "tamanhoMaximoMb"
TYPES_KEY = "tiposAceitos"

KILOBYTE = 1024
MEGABYTE = 1024 * KILOBYTE

# A JPEG photo is a JPG attachment: same format, the other extension.
TYPE_ALIASES = {"JPEG": "JPG"}

# The server picks the MIME type from the type of the file, never from what the
# client claimed: the type is what the download tells the browser it is getting.
MIME_BY_TYPE = {
    "PDF": "application/pdf",
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "DWG": "image/vnd.dwg",
    "ZIP": "application/zip",
}
OTHER_MIME_TYPE = "application/octet-stream"

MAX_NAME_CHARS = 200
MAX_EXTENSION_CHARS = 20
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_FOLDER_SEPARATORS = re.compile(r"[\\/]")

NO_FILE_MESSAGE = "Escolha um arquivo para anexar."
EMPTY_FILE_MESSAGE = "O arquivo está vazio."
NO_EXTENSION_MESSAGE = "O arquivo não tem extensão."
UNKNOWN_ORIGIN_MESSAGE = "O tipo de registro ao qual o anexo pertence não existe."
MISSING_RECORD_MESSAGE = "O registro ao qual o anexo pertence não foi encontrado."
UNOWNED_ATTACHMENT_MESSAGE = (
    "O módulo dono do registro deste anexo não está disponível, e o download foi recusado."
)


def _holders_of(permission: Permission) -> str:
    """The profiles that hold the permission, as a sentence lists them: ``A e B``."""
    names = [
        profile.value
        for profile in rbac.GeneralProfile
        if permission in rbac.PROFILE_PERMISSIONS[profile]
    ]
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} e {names[-1]}"


# What the list says in place of the files, to whoever may send but not see them (Q35).
RESTRICTED_NOTICE = (
    "Os anexos deste registro contêm dados pessoais: "
    f"só {_holders_of(Permission.VIEW_RESTRICTED)} os veem e baixam."
)


# ── The limits (parameters of the Anexos group) ──────────────────────────


@dataclass(frozen=True)
class AttachmentLimits:
    """The Anexos group in force: the largest file, in megabytes, and the accepted types."""

    max_megabytes: float
    types: tuple[str, ...]

    @property
    def max_bytes(self) -> int:
        """The largest file in bytes: 1 MB is 1.048.576 bytes, and a file of exactly this passes."""
        return int(self.max_megabytes * MEGABYTE)

    @property
    def max_megabytes_text(self) -> str:
        """The limit as a person reads it: ``25``, or ``2,5``."""
        return f"{self.max_megabytes:g}".replace(".", ",")

    @property
    def extensions(self) -> tuple[str, ...]:
        """The extensions of the accepted types in lower case, aliases included (``jpg``, ``jpeg``)."""
        aliases = [alias for alias, kind in TYPE_ALIASES.items() if kind in self.types]
        return tuple(kind.lower() for kind in (*self.types, *aliases))


def limits_from_values(values: Mapping[str, Any]) -> AttachmentLimits:
    """The limits of one version of the group; a missing or unusable value falls back to the initial.

    The initial values are the ones the group is seeded with (D5a), so a base
    that still has no version of the group refuses nothing it should accept.
    """
    initial = configuracoes.INITIAL_PARAMETERS[ATTACHMENTS_GROUP]
    megabytes = _positive_number(values.get(SIZE_KEY))
    types = _clean_types(values.get(TYPES_KEY))
    return AttachmentLimits(
        max_megabytes=megabytes if megabytes is not None else float(initial[SIZE_KEY]),
        types=types or _clean_types(initial[TYPES_KEY]),
    )


def current_limits(session: Session, *, reference_date: date) -> AttachmentLimits:
    """The limits of the Anexos group in force on the reference date."""
    values = configuracoes.current_group(
        session, group=ATTACHMENTS_GROUP, reference_date=reference_date
    )
    return limits_from_values(values)


def file_problem(file_name: str, size_bytes: int, limits: AttachmentLimits) -> str | None:
    """The message for the field when the file breaks a limit, or ``None`` when it holds up.

    The boundary is exact: a file of the size of the limit passes and one byte
    more does not. A file with no content never passes, because it is not
    evidence of anything.
    """
    kind = file_type(file_name)
    if kind not in limits.types:
        return _type_message(kind, limits)
    if size_bytes == 0:
        return EMPTY_FILE_MESSAGE
    if size_bytes > limits.max_bytes:
        return (
            f"O arquivo tem {format_size(size_bytes)}, "
            f"acima do limite de {limits.max_megabytes_text} MB."
        )
    return None


def file_type(file_name: str) -> str:
    """The type of the file for the accepted list: its extension in capitals, JPEG as JPG."""
    extension = PurePosixPath(file_name).suffix.lstrip(".").upper()
    return TYPE_ALIASES.get(extension, extension)


def mime_type_of(file_name: str) -> str:
    """The MIME type the download declares for the file, from its type."""
    return MIME_BY_TYPE.get(file_type(file_name), OTHER_MIME_TYPE)


def clean_name(raw_name: str | None) -> str:
    """The name the list and the download show: what the person sent, made safe.

    The folders some browsers send with the name are cut, the control characters
    (a line break could split a header) are dropped and the accents are composed,
    so a name typed on a Mac reads the same everywhere. A very long name loses
    the end of its stem and keeps the extension.
    """
    name = unicodedata.normalize("NFC", raw_name or "")
    name = _CONTROL_CHARACTERS.sub("", name)
    name = _FOLDER_SEPARATORS.split(name)[-1].strip()
    if len(name) <= MAX_NAME_CHARS:
        return name
    extension = PurePosixPath(name).suffix
    if len(extension) > MAX_EXTENSION_CHARS:
        extension = ""
    return name[: MAX_NAME_CHARS - len(extension)] + extension


def format_size(size_bytes: int) -> str:
    """The size as the list shows it: ``812 B``, ``1,5 KB``, ``25,0 MB``.

    A size is rounded up to the tenth, so a file over the limit never reads as
    the limit itself in the message that refuses it.
    """
    if size_bytes < KILOBYTE:
        return f"{size_bytes} B"
    tenths = _tenths(size_bytes, KILOBYTE)
    if tenths < 10 * KILOBYTE:
        return f"{_decimal(tenths)} KB"
    return f"{_decimal(_tenths(size_bytes, MEGABYTE))} MB"


# ── Upload ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NewAttachment:
    """What a person sends: the record the file belongs to and the file as the browser gave it."""

    origin_table: str
    origin_record_id: int
    file_name: str | None
    content: bytes


def upload(
    session: Session,
    *,
    user: User,
    new: NewAttachment,
    reference_date: date,
    storage: FileStorage | None = None,
) -> Attachment:
    """Record and keep one attachment, or refuse with 403 or 422 before anything is written.

    Who writes and may read the record sends; the file is checked against the
    limits in force. The metadata and its trail line go in the request's
    transaction and the file is kept last: if keeping it fails, the exception
    rolls the row back. ``storage`` replaces the environment's choice, which is
    how the tests inject a double.
    """
    rbac.require(user, Permission.WRITE)
    record = _existing_record(
        session, user=user, origin_table=new.origin_table, record_id=new.origin_record_id
    )
    name = clean_name(new.file_name)
    _require_acceptable_file(
        name, len(new.content), current_limits(session, reference_date=reference_date)
    )
    attachment = Attachment(
        project_id=record.project_id,
        uploaded_by_id=user.id,
        name=name,
        mime_type=mime_type_of(name),
        size_bytes=len(new.content),
        file_hash=hashlib.sha256(new.content).hexdigest(),
        origin_table=new.origin_table,
        origin_record_id=new.origin_record_id,
        uploaded_at=calendario.now(),
    )
    session.add(attachment)
    session.flush()
    audit.created(session, user_id=user.id, entity=attachment.__tablename__, record=attachment)
    chosen = file_storage.configured_storage() if storage is None else storage
    chosen.save(storage_key(attachment), new.content)
    return attachment


def storage_key(attachment: Attachment) -> str:
    """Where the file is kept: the project and the attachment, never the name it was sent with."""
    return f"{attachment.project_id}/{attachment.id}"


# ── The list of a record ─────────────────────────────────────────────────


@dataclass(frozen=True)
class AttachmentEntry:
    """One attachment of the list: name, size, who sent it and when (HU-143)."""

    id: int
    name: str
    size_bytes: int
    uploaded_by: str
    uploaded_at: datetime


@dataclass(frozen=True)
class AttachmentPanel:
    """What the attachments of one record show to one user.

    ``can_view`` is false when the attachments are restricted (Q35) and the user
    does not hold the permission: ``entries`` is then empty. ``can_upload`` is
    independent: the Membro fills in the occurrence and sends its attachments
    without being able to see them afterwards.
    """

    entries: tuple[AttachmentEntry, ...]
    can_view: bool
    can_upload: bool
    limits: AttachmentLimits


def panel(
    session: Session,
    *,
    user: User,
    origin_table: str,
    origin_record_id: int,
    reference_date: date,
) -> AttachmentPanel:
    """The attachments of the record the user may see, and what the user may do with them."""
    record = _existing_record(
        session, user=user, origin_table=origin_table, record_id=origin_record_id
    )
    can_view = _may_view_attachments(user, record)
    entries = (
        _entries(session, origin_table=origin_table, record_id=origin_record_id) if can_view else ()
    )
    return AttachmentPanel(
        entries=entries,
        can_view=can_view,
        can_upload=rbac.can(user, Permission.WRITE),
        limits=current_limits(session, reference_date=reference_date),
    )


# ── Download ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Download:
    """The file to hand to the browser, with the name and the type it was sent with."""

    name: str
    mime_type: str
    content: bytes


def open_download(
    session: Session,
    *,
    user: User,
    attachment_id: int,
    storage: FileStorage | None = None,
) -> Download | None:
    """The file of the attachment, if the user may read the record it belongs to (HU-141, HU-142).

    Raises ``AccessDeniedError`` (403) when the module that owns the record
    refuses the user, when the attachment is restricted and the user may not
    read restricted data, or when no module owns the record any longer. Returns
    ``None`` when there is nothing to hand back: no such attachment, a record
    that no longer exists, or a file that is not in the storage (which is
    logged, since the database says it should be there).
    """
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        return None
    origin_type = attachment_origins.find(attachment.origin_table)
    if origin_type is None:
        raise AccessDeniedError(UNOWNED_ATTACHMENT_MESSAGE)
    record = _read_record(
        session, user=user, origin_type=origin_type, record_id=attachment.origin_record_id
    )
    if record is None:
        return None
    if record.restricted:
        rbac.require(user, Permission.VIEW_RESTRICTED)
    return _fetch(attachment, storage)


# ── Evidence ─────────────────────────────────────────────────────────────


def has_evidence(session: Session, *, origin_table: str, origin_record_id: int) -> bool:
    """Whether the record has at least one attachment: what "evidência obrigatória" means (D5a).

    It is a fact about the record and not a reading of its files, so it does
    not ask who may read them: a module that requires evidence to close an item
    answers the same for every user, restricted attachments included.
    """
    statement = select(
        exists().where(
            Attachment.origin_table == origin_table,
            Attachment.origin_record_id == origin_record_id,
        )
    )
    return bool(session.scalar(statement))


# ── Internals ────────────────────────────────────────────────────────────


def _origin_type(origin_table: str) -> OriginType:
    """The registered origin type of the table, or 422: the form named a kind that does not exist."""
    origin_type = attachment_origins.find(origin_table)
    if origin_type is None:
        raise InvalidDataError(UNKNOWN_ORIGIN_MESSAGE)
    return origin_type


def _read_record(
    session: Session, *, user: User, origin_type: OriginType, record_id: int
) -> OriginRecord | None:
    """Ask the module that owns the record: the user must reach it, then it answers for the record."""
    rbac.require_module(user, origin_type.module)
    return origin_type.read(session, user=user, record_id=record_id)


def _existing_record(
    session: Session, *, user: User, origin_table: str, record_id: int
) -> OriginRecord:
    """The record the attachment is about, read through its owner, or 403 or 422."""
    record = _read_record(
        session, user=user, origin_type=_origin_type(origin_table), record_id=record_id
    )
    if record is None:
        raise InvalidDataError(MISSING_RECORD_MESSAGE)
    return record


def _may_view_attachments(user: User, record: OriginRecord) -> bool:
    return not record.restricted or rbac.can(user, Permission.VIEW_RESTRICTED)


def _require_acceptable_file(name: str, size_bytes: int, limits: AttachmentLimits) -> None:
    if not name:
        raise InvalidDataError({FILE_FIELD: NO_FILE_MESSAGE})
    problem = file_problem(name, size_bytes, limits)
    if problem is not None:
        raise InvalidDataError({FILE_FIELD: problem})


def _entries(session: Session, *, origin_table: str, record_id: int) -> tuple[AttachmentEntry, ...]:
    statement = (
        select(Attachment)
        .where(
            Attachment.origin_table == origin_table,
            Attachment.origin_record_id == record_id,
        )
        .order_by(Attachment.uploaded_at, Attachment.id)
    )
    rows = session.scalars(statement).all()
    authors = {
        author_id: audit.author_name(session, author_id)
        for author_id in {row.uploaded_by_id for row in rows}
    }
    return tuple(
        AttachmentEntry(
            id=row.id,
            name=row.name,
            size_bytes=row.size_bytes,
            uploaded_by=authors[row.uploaded_by_id],
            uploaded_at=row.uploaded_at,
        )
        for row in rows
    )


def _fetch(attachment: Attachment, storage: FileStorage | None) -> Download | None:
    chosen = file_storage.configured_storage() if storage is None else storage
    try:
        content = chosen.read(storage_key(attachment))
    except StoredFileNotFoundError:
        content = None
    if content is None:
        logger.error("O arquivo do anexo %s não está no armazenamento.", attachment.id)
        return None
    return Download(name=attachment.name, mime_type=attachment.mime_type, content=content)


def _type_message(kind: str, limits: AttachmentLimits) -> str:
    accepted = f"Aceitos: {', '.join(limits.types)}."
    if not kind:
        return f"{NO_EXTENSION_MESSAGE} {accepted}"
    return f"Tipo de arquivo não aceito (.{kind.lower()}). {accepted}"


def _positive_number(value: Any) -> float | None:
    """A usable limit: a finite number above zero, and never a boolean."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) and value > 0 else None


def _clean_types(raw: Any) -> tuple[str, ...]:
    """The accepted types in capitals, without dots or repeats, in the order the group lists them."""
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return ()
    cleaned = (str(item).strip().lstrip(".").upper() for item in raw)
    return tuple(dict.fromkeys(TYPE_ALIASES.get(item, item) for item in cleaned if item))


def _tenths(size_bytes: int, unit: int) -> int:
    """The size in units, in tenths, rounded up."""
    return -(-size_bytes * 10 // unit)


def _decimal(tenths: int) -> str:
    return f"{tenths // 10},{tenths % 10}"
