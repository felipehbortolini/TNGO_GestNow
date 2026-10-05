"""The file port (ISSUE-012): the environment picks the adapter, the local folder and Blob keep the bytes.

Nothing here reaches the network or needs the Azure SDK: the Blob adapter talks
to a container in memory, and the selection test puts a stand-in for
``azure.storage.blob`` in the import system (``tests/armazenamento_falso.py``).
The local folder tests use ``tmp_path``, so no test writes to ``data/anexos/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core import blob_storage, config, file_storage
from src.core.blob_storage import BlobSettings, BlobSettingsError, BlobStorage
from src.core.file_storage import LocalFolderStorage, StoredFileNotFoundError
from tests.armazenamento_falso import BlobInexistenteError, ContainerFalso, SdkFalso

CONEXAO_DE_TESTE = "valor-que-nunca-pode-vazar"


# ── The variables ────────────────────────────────────────────────────────


def test_sem_a_variavel_o_armazenamento_e_a_pasta_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.ATTACHMENT_STORAGE_VARIABLE, raising=False)

    assert config.attachment_storage() == config.ATTACHMENT_STORAGE_LOCAL


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("local", config.ATTACHMENT_STORAGE_LOCAL),
        ("  LOCAL  ", config.ATTACHMENT_STORAGE_LOCAL),
        ("blob", config.ATTACHMENT_STORAGE_BLOB),
        ("Blob", config.ATTACHMENT_STORAGE_BLOB),
    ],
)
def test_a_variavel_aceita_os_dois_valores_sem_diferenciar_caixa(
    monkeypatch: pytest.MonkeyPatch, valor: str, esperado: str
) -> None:
    monkeypatch.setenv(config.ATTACHMENT_STORAGE_VARIABLE, valor)

    assert config.attachment_storage() == esperado


def test_valor_desconhecido_falha_alto_nomeando_a_variavel_e_os_valores_validos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ATTACHMENT_STORAGE_VARIABLE, "nuvem")

    with pytest.raises(config.InvalidAttachmentStorageError) as erro:
        config.attachment_storage()

    mensagem = str(erro.value)
    assert config.ATTACHMENT_STORAGE_VARIABLE in mensagem
    assert "'nuvem'" in mensagem
    assert "'local'" in mensagem
    assert "'blob'" in mensagem


def test_a_pasta_local_padrao_e_data_anexos_na_raiz_e_o_git_a_ignora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(config.ATTACHMENT_FOLDER_VARIABLE, raising=False)

    pasta = config.attachment_folder()

    assert pasta == config.REPOSITORY_ROOT / "data" / "anexos"
    assert (config.REPOSITORY_ROOT / "api" / "function_app.py").is_file()
    regras = (config.REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/anexos/" in regras


def test_a_variavel_da_pasta_troca_a_pasta_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(config.ATTACHMENT_FOLDER_VARIABLE, f"  {tmp_path}  ")

    assert config.attachment_folder() == tmp_path


# ── The local folder ─────────────────────────────────────────────────────


def test_pasta_local_guarda_e_devolve_o_conteudo_sob_a_chave(tmp_path: Path) -> None:
    armazenamento = LocalFolderStorage(tmp_path)

    armazenamento.save("7/42", b"conteudo do anexo")

    assert (tmp_path / "7" / "42").read_bytes() == b"conteudo do anexo"
    assert armazenamento.read("7/42") == b"conteudo do anexo"


def test_pasta_local_regrava_a_mesma_chave_e_nao_deixa_arquivo_parcial(tmp_path: Path) -> None:
    armazenamento = LocalFolderStorage(tmp_path)

    armazenamento.save("7/42", b"primeiro")
    armazenamento.save("7/42", b"segundo")

    assert armazenamento.read("7/42") == b"segundo"
    assert [arquivo for arquivo in tmp_path.rglob("*") if arquivo.is_file()] == [
        tmp_path / "7" / "42"
    ]


def test_pasta_local_sem_o_arquivo_devolve_o_erro_da_porta(tmp_path: Path) -> None:
    with pytest.raises(StoredFileNotFoundError) as erro:
        LocalFolderStorage(tmp_path).read("7/42")

    assert erro.value.key == "7/42"


@pytest.mark.parametrize("chave", ["../fora", "7/../../fora", "/etc/passwd", "", "."])
def test_pasta_local_recusa_chave_que_sai_da_pasta(tmp_path: Path, chave: str) -> None:
    armazenamento = LocalFolderStorage(tmp_path / "anexos")

    with pytest.raises(ValueError, match="sai da pasta"):
        armazenamento.save(chave, b"x")
    with pytest.raises(ValueError, match="sai da pasta"):
        armazenamento.read(chave)

    assert not (tmp_path / "fora").exists()


# ── The Blob adapter, with a double ──────────────────────────────────────


def test_blob_guarda_cada_arquivo_como_blob_da_chave_e_le_de_volta() -> None:
    container = ContainerFalso()
    armazenamento = BlobStorage(container)

    armazenamento.save("7/42", b"conteudo")
    armazenamento.save("7/42", b"conteudo novo")

    assert container.blobs == {"7/42": b"conteudo novo"}
    assert armazenamento.read("7/42") == b"conteudo novo"
    assert container.chamadas == [("upload", "7/42"), ("upload", "7/42"), ("download", "7/42")]


def test_blob_ausente_vira_o_erro_de_arquivo_nao_encontrado_da_porta() -> None:
    with pytest.raises(StoredFileNotFoundError) as erro:
        BlobStorage(ContainerFalso()).read("7/42")

    assert erro.value.key == "7/42"
    assert isinstance(erro.value.__cause__, BlobInexistenteError)


class ErroDoServicoError(Exception):
    """A failure of the service that is not "not found": it carries another status."""

    status_code = 500


@pytest.mark.parametrize("falha", [ErroDoServicoError("indisponivel"), ConnectionError("sem rede")])
def test_outra_falha_do_blob_nao_vira_arquivo_nao_encontrado(falha: Exception) -> None:
    class ContainerQuebrado(ContainerFalso):
        def download_blob(self, _blob: str):
            raise falha

    with pytest.raises(type(falha)):
        BlobStorage(ContainerQuebrado()).read("7/42")


def test_a_configuracao_do_blob_nao_mostra_a_chave_de_conexao_no_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(blob_storage.VARIABLES["connection_string"], CONEXAO_DE_TESTE)

    configuracao = BlobSettings.from_environment()

    assert configuracao.connection_string == CONEXAO_DE_TESTE
    assert CONEXAO_DE_TESTE not in repr(configuracao)


def test_configuracao_incompleta_nomeia_a_variavel_que_falta_e_nunca_um_valor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(blob_storage.VARIABLES["connection_string"], raising=False)

    with pytest.raises(BlobSettingsError) as erro:
        BlobStorage.from_environment()

    assert "GESTNOW_BLOB_CONEXAO" in str(erro.value)
    assert erro.value.args[0].startswith("A configuração do armazenamento Blob está incompleta.")


def test_do_ambiente_o_blob_usa_o_container_anexos_quando_nenhum_e_informado(
    monkeypatch: pytest.MonkeyPatch, sdk_do_azure: SdkFalso
) -> None:
    monkeypatch.setenv(blob_storage.VARIABLES["connection_string"], CONEXAO_DE_TESTE)
    monkeypatch.delenv(blob_storage.VARIABLES["container"], raising=False)

    BlobStorage.from_environment().save("7/42", b"conteudo")

    assert sdk_do_azure.conexoes == [CONEXAO_DE_TESTE]
    assert sdk_do_azure.containers["anexos"].blobs == {"7/42": b"conteudo"}


def test_do_ambiente_o_blob_usa_o_container_informado(
    monkeypatch: pytest.MonkeyPatch, sdk_do_azure: SdkFalso
) -> None:
    monkeypatch.setenv(blob_storage.VARIABLES["connection_string"], CONEXAO_DE_TESTE)
    monkeypatch.setenv(blob_storage.VARIABLES["container"], "anexos-do-gestnow")

    BlobStorage.from_environment().save("7/42", b"conteudo")

    assert list(sdk_do_azure.containers) == ["anexos-do-gestnow"]


# ── The environment picks the adapter ────────────────────────────────────


def test_o_ambiente_escolhe_a_pasta_local_por_padrao_e_o_blob_quando_a_variavel_diz_blob(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sdk_do_azure: SdkFalso
) -> None:
    monkeypatch.setenv(config.ATTACHMENT_FOLDER_VARIABLE, str(tmp_path))
    monkeypatch.setenv(blob_storage.VARIABLES["connection_string"], CONEXAO_DE_TESTE)

    monkeypatch.delenv(config.ATTACHMENT_STORAGE_VARIABLE, raising=False)
    file_storage.configured_storage().save("7/42", b"na pasta")
    monkeypatch.setenv(config.ATTACHMENT_STORAGE_VARIABLE, config.ATTACHMENT_STORAGE_BLOB)
    file_storage.configured_storage().save("7/42", b"no blob")

    assert (tmp_path / "7" / "42").read_bytes() == b"na pasta"
    assert sdk_do_azure.containers["anexos"].blobs == {"7/42": b"no blob"}


def test_valor_desconhecido_da_variavel_tambem_falha_alto_ao_escolher_o_armazenamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ATTACHMENT_STORAGE_VARIABLE, "nuvem")

    with pytest.raises(config.InvalidAttachmentStorageError):
        file_storage.configured_storage()
