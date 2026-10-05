"""Doubles of the file storage for the tests: an in-memory port and a container of the Azure SDK.

The Blob adapter talks to ``BlobContainer``, so a container in memory stands in
for the SDK's ``ContainerClient``. The fixture ``sdk_do_azure`` (in
``tests/plataforma/conftest.py``) goes one step further: it puts a stand-in for
``azure.storage.blob`` in the import system, which is how
``BlobStorage.from_environment`` is tested without the network and without the
SDK installed (the product imports it only there).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.file_storage import StoredFileNotFoundError


class ArmazenamentoEmMemoria:
    """The file port in memory: what a facade test hands to ``storage=``."""

    def __init__(self) -> None:
        self.arquivos: dict[str, bytes] = {}

    def save(self, key: str, content: bytes) -> None:
        self.arquivos[key] = content

    def read(self, key: str) -> bytes:
        if key not in self.arquivos:
            raise StoredFileNotFoundError(key)
        return self.arquivos[key]


class BlobInexistenteError(Exception):
    """What the SDK raises for a missing blob: an error that carries the HTTP status 404."""

    status_code = 404


class DownloadFalso:
    """What ``download_blob`` returns: the bytes are read from it."""

    def __init__(self, conteudo: bytes) -> None:
        self._conteudo = conteudo

    def readall(self) -> bytes:
        return self._conteudo


class ContainerFalso:
    """A container in memory that records the calls: the double of ``ContainerClient``."""

    def __init__(self, nome: str = "anexos") -> None:
        self.nome = nome
        self.blobs: dict[str, bytes] = {}
        self.chamadas: list[tuple[str, str]] = []

    def upload_blob(self, name: str, data: bytes, *, overwrite: bool) -> None:
        self.chamadas.append(("upload", name))
        if not overwrite and name in self.blobs:
            raise FileExistsError(name)
        self.blobs[name] = bytes(data)

    def download_blob(self, blob: str) -> DownloadFalso:
        self.chamadas.append(("download", blob))
        if blob not in self.blobs:
            raise BlobInexistenteError(blob)
        return DownloadFalso(self.blobs[blob])


@dataclass
class SdkFalso:
    """What the stand-in SDK saw: the containers it handed out and the connections it opened."""

    containers: dict[str, ContainerFalso] = field(default_factory=dict)
    conexoes: list[str] = field(default_factory=list)
