"""The file port: where the bytes of an attachment live (D5a, ISSUE-012).

The database keeps the metadata of an attachment (name, type, size, hash, who
sent it, when, and the record it belongs to); the file itself lives in a storage
that the environment chooses, with no change of code:

* the local folder (``GESTNOW_ARMAZENAMENTO_ANEXOS`` unset or ``local``):
  ``data/anexos/`` at the repository root, outside git. It is the adapter of the
  local machine and of the demonstration;
* Azure Blob Storage (``blob``): ``blob_storage``.

The port is two verbs, ``save`` and ``read``, over an opaque key that the facade
of the attachments builds from the ids of the row, never from the name the
person gave the file (that name lives only in the database). A key with no file
is the one failure the port names, ``StoredFileNotFoundError``; any other failure
of the medium (full disk, network, permission) is the medium's own exception, so
the request fails loud and its transaction rolls back, instead of recording an
attachment whose file was not kept.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.core import config

# A file is written under this suffix and renamed when complete, so a reader
# never sees half a file.
PARTIAL_SUFFIX = ".parte"


class StoredFileNotFoundError(Exception):
    """The storage holds no file under the key: the row exists but the bytes do not."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Não há arquivo guardado com a chave {key!r}.")


class FileStorage(Protocol):
    """Where the files are kept: the seam of the port, with two real adapters."""

    def save(self, key: str, content: bytes) -> None:
        """Keep the content under the key, replacing what was there."""

    def read(self, key: str) -> bytes:
        """The content kept under the key; raise ``StoredFileNotFoundError`` when there is none."""


class LocalFolderStorage:
    """The local adapter: one file per key under a root folder (``data/anexos/``)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, key: str, content: bytes) -> None:
        target = self._path_of(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f"{target.name}{PARTIAL_SUFFIX}")
        partial.write_bytes(content)
        partial.replace(target)

    def read(self, key: str) -> bytes:
        path = self._path_of(key)
        try:
            content = path.read_bytes()
        except FileNotFoundError as error:
            raise StoredFileNotFoundError(key) from error
        return content

    def _path_of(self, key: str) -> Path:
        """The file of the key, which can never be outside the root folder."""
        root = self._root.resolve()
        path = (root / key).resolve()
        if path == root or not path.is_relative_to(root):
            message = f"A chave {key!r} sai da pasta de anexos."
            raise ValueError(message)
        return path


def configured_storage() -> FileStorage:
    """The storage the environment selects: the local folder unless Blob is switched on.

    An unknown ``GESTNOW_ARMAZENAMENTO_ANEXOS`` raises
    ``config.InvalidAttachmentStorageError``: a mistake to fix, not a fallback.
    """
    if config.attachment_storage() == config.ATTACHMENT_STORAGE_BLOB:
        # Imported here because blob_storage needs this module's error type.
        from src.core import blob_storage

        return blob_storage.BlobStorage.from_environment()
    return LocalFolderStorage(config.attachment_folder())
