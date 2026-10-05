"""Azure Blob Storage: the second adapter of the file port, written for ``blob`` (D5a, ISSUE-012).

The adapter behind the file port when ``GESTNOW_ARMAZENAMENTO_ANEXOS=blob``. Two
settings, both environment variables, so nothing changes in the code when the
app moves from the local machine to Azure (see ``VARIABLES``):

* ``GESTNOW_BLOB_CONEXAO``: the connection string of the storage account. It is
  a secret: it lives only in the application settings of Azure, never in git;
* ``GESTNOW_BLOB_CONTAINER``: the container of the attachments (``anexos`` when
  absent). The container is created with the storage account (the publication
  guide, ISSUE-092) and stays private: every download goes through the API,
  which checks the permission of the record the file belongs to.

The official SDK, ``azure-storage-blob``, is imported in
``BlobStorage.from_environment`` and nowhere else in the product. The adapter
itself talks to ``BlobContainer``, the two calls it makes on the SDK's
``ContainerClient``: the tests hand it a double, so no test reaches the network
and none needs the SDK installed. There is no retry and no streaming: the
largest attachment is 25 MB by default and a failed upload rolls the whole
request back for the person to try again.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol, cast

from src.core.file_storage import StoredFileNotFoundError

# The environment variable of each setting of ``BlobSettings``: the list the README shows.
VARIABLES = {
    "connection_string": "GESTNOW_BLOB_CONEXAO",
    "container": "GESTNOW_BLOB_CONTAINER",
}

DEFAULT_CONTAINER = "anexos"

HTTP_NOT_FOUND = 404


class BlobSettingsError(RuntimeError):
    """The Blob settings are incomplete: the message names the variables, never their values."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__(
            f"A configuração do armazenamento Blob está incompleta. Faltam: {', '.join(missing)}."
        )


class BlobDownload(Protocol):
    """What the SDK hands back when a download starts: the bytes are read from it."""

    def readall(self) -> bytes:
        """Read the whole blob."""


class BlobContainer(Protocol):
    """The two calls the adapter makes on the SDK's ``ContainerClient``: the seam the tests fake."""

    def upload_blob(self, name: str, data: bytes, *, overwrite: bool) -> object:
        """Upload the bytes as the blob, replacing it when ``overwrite`` is set."""

    def download_blob(self, blob: str) -> BlobDownload:
        """Start the download of a blob; the SDK raises an error with status 404 when it is absent."""


@dataclass(frozen=True)
class BlobSettings:
    """What the adapter needs to reach the container; read from the environment, never from code."""

    # Out of ``repr`` so that printing or logging the settings can never show it.
    connection_string: str = field(repr=False)
    container: str

    @classmethod
    def from_environment(cls) -> BlobSettings:
        """Read the settings; an absent connection string is empty, checked later."""
        return cls(
            connection_string=_read(VARIABLES["connection_string"]),
            container=_read(VARIABLES["container"]) or DEFAULT_CONTAINER,
        )

    def missing_variables(self) -> list[str]:
        """The environment variables that are empty, by name and never by value."""
        return [] if self.connection_string else [VARIABLES["connection_string"]]


class BlobStorage:
    """Keeps each file as a blob of the container, named by the key."""

    def __init__(self, container: BlobContainer) -> None:
        self._container = container

    @classmethod
    def from_environment(cls) -> BlobStorage:
        """The adapter for the container the environment names, or ``BlobSettingsError``."""
        settings = BlobSettings.from_environment()
        missing = settings.missing_variables()
        if missing:
            raise BlobSettingsError(missing)
        # The one import of the SDK in the product: it is only needed with Blob switched on.
        from azure.storage.blob import BlobServiceClient

        service = BlobServiceClient.from_connection_string(settings.connection_string)
        return cls(cast("BlobContainer", service.get_container_client(settings.container)))

    def save(self, key: str, content: bytes) -> None:
        self._container.upload_blob(key, content, overwrite=True)

    def read(self, key: str) -> bytes:
        try:
            content = self._container.download_blob(key).readall()
        except Exception as error:
            # The SDK's own "not found" error carries the HTTP status of the service.
            if _status_of(error) == HTTP_NOT_FOUND:
                raise StoredFileNotFoundError(key) from error
            raise
        return content


def _read(variable: str) -> str:
    return (os.environ.get(variable) or "").strip()


def _status_of(error: Exception) -> int | None:
    """The HTTP status an SDK error carries, or ``None`` for any other exception."""
    status = getattr(error, "status_code", None)
    return status if isinstance(status, int) else None
