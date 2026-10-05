"""Attachments (ISSUE-012): the limits, the upload, the list, the download and the evidence.

This is the transversal test of the spec for the attachments: a file over the
limit or of a type outside the list is refused with 422 and the message under
the field; a download is refused to whoever may not read the record the file
belongs to; the environment picks the storage with no change of code.

Two seams. The facade ``core.attachments``, with the session of the test
database and the file port in memory. And the three routes of the blueprint,
called with an ``HttpRequest`` built here (``multipart/form-data`` for the
upload), over a local folder inside ``tmp_path``. No module owns attachments
yet, so the tests register their own origin types in a registry that is
isolated for the test: ``teste_registro`` (a common record and a reserved one,
which only some people may read) and ``teste_dado_pessoal`` (personal data, Q35).

Nothing is committed: every test runs in the transaction ``db_session`` rolls back.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import azure.functions as func
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from src.blueprints.attachments import download_attachment, list_attachments, upload_attachment
from src.core import attachment_origins, attachments, auth, calendario, config, rbac
from src.core.attachment_origins import OriginRecord, OriginType
from src.core.attachments import AttachmentLimits, NewAttachment
from src.core.auth import PRINCIPAL_HEADER
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import Attachment, AuditEntry
from src.core.rbac import Permission, User
from src.core.responses import cabecalhos_de_toast
from src.core.routing import Access, file_route
from src.modulos.configuracoes import service as configuracoes
from tests.armazenamento_falso import ArmazenamentoEmMemoria, SdkFalso
from tests.html_tags import Tag, find_all, find_by_id, parse_tags
from tests.identidades import (
    cabecalho_do_principal,
    criar_colaborador,
    criar_empresa,
    criar_projeto,
    requisicao,
)

REFERENCIA = date(2026, 10, 5)
MEGABYTE = 1024 * 1024
TIPOS_INICIAIS = ("PDF", "JPG", "PNG", "DOCX", "XLSX", "PPTX", "DWG", "ZIP")
LIMITES_INICIAIS = AttachmentLimits(max_megabytes=25, types=TIPOS_INICIAIS)
ACEITOS_INICIAIS = "Aceitos: PDF, JPG, PNG, DOCX, XLSX, PPTX, DWG, ZIP."
FALTA_O_REGISTRO = "Informe o registro ao qual o anexo pertence."

VERA = "vera.visualizadora@example.invalid"
MARIO = "mario.membro@example.invalid"
GIL = "gil.gestor@example.invalid"
ADA = "ada.admin@example.invalid"
FABIO = "fabio.fornecedor@example.invalid"

REGISTRO_COMUM = 101
REGISTRO_RESERVADO = 102
REGISTRO_PESSOAL = 201
REGISTRO_INEXISTENTE = 999
RECUSA_DO_REGISTRO = "Você não participa deste registro."
TABELAS_DE_TESTE = ("teste_registro", "teste_dado_pessoal")

ALVO = "anexos-teste"
DATA_E_HORA = re.compile(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}")


# ── The rules, with no database ──────────────────────────────────────────


def test_arquivo_do_tamanho_exato_do_limite_passa_e_um_byte_a_mais_nao() -> None:
    limite = 25 * MEGABYTE

    assert attachments.file_problem("projeto.pdf", limite, LIMITES_INICIAIS) is None
    assert attachments.file_problem("projeto.pdf", limite + 1, LIMITES_INICIAIS) == (
        "O arquivo tem 25,1 MB, acima do limite de 25 MB."
    )


def test_limite_fracionario_e_lido_em_megabytes_e_escrito_com_virgula() -> None:
    limites = AttachmentLimits(max_megabytes=2.5, types=("PDF",))

    assert limites.max_bytes == 2_621_440
    assert limites.max_megabytes_text == "2,5"
    assert attachments.file_problem("a.pdf", 2_621_440, limites) is None
    assert attachments.file_problem("a.pdf", 2_621_441, limites) == (
        "O arquivo tem 2,6 MB, acima do limite de 2,5 MB."
    )


def test_arquivo_vazio_nunca_passa() -> None:
    assert attachments.file_problem("vazio.pdf", 0, LIMITES_INICIAIS) == "O arquivo está vazio."
    assert attachments.file_problem("vazio.pdf", 1, LIMITES_INICIAIS) is None


@pytest.mark.parametrize(
    "nome",
    [
        "laudo.pdf",
        "LAUDO.PDF",
        "foto.jpg",
        "foto.JPEG",
        "imagem.png",
        "contrato.docx",
        "dados.xlsx",
        "apresentacao.pptx",
        "planta.dwg",
        "pacote.zip",
    ],
)
def test_os_oito_tipos_da_lista_sao_aceitos_sem_diferenciar_maiusculas(nome: str) -> None:
    assert attachments.file_problem(nome, 10, LIMITES_INICIAIS) is None


@pytest.mark.parametrize(
    ("nome", "mensagem"),
    [
        ("programa.exe", f"Tipo de arquivo não aceito (.exe). {ACEITOS_INICIAIS}"),
        ("pagina.HTML", f"Tipo de arquivo não aceito (.html). {ACEITOS_INICIAIS}"),
        ("pacote.tar.gz", f"Tipo de arquivo não aceito (.gz). {ACEITOS_INICIAIS}"),
        ("sem_extensao", f"O arquivo não tem extensão. {ACEITOS_INICIAIS}"),
        (".pdf", f"O arquivo não tem extensão. {ACEITOS_INICIAIS}"),
    ],
)
def test_tipo_fora_da_lista_e_recusado_com_a_lista_dos_aceitos(nome: str, mensagem: str) -> None:
    assert attachments.file_problem(nome, 10, LIMITES_INICIAIS) == mensagem


def test_o_tipo_e_conferido_antes_do_tamanho_e_do_vazio() -> None:
    assert attachments.file_problem("programa.exe", 0, LIMITES_INICIAIS) == (
        f"Tipo de arquivo não aceito (.exe). {ACEITOS_INICIAIS}"
    )


@pytest.mark.parametrize(
    ("nome", "tipo", "mime"),
    [
        ("a.pdf", "PDF", "application/pdf"),
        ("A.PDF", "PDF", "application/pdf"),
        ("foto.jpeg", "JPG", "image/jpeg"),
        ("foto.jpg", "JPG", "image/jpeg"),
        ("planta.dwg", "DWG", "image/vnd.dwg"),
        ("dados.xlsx", "XLSX", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("notas.txt", "TXT", "application/octet-stream"),
        ("sem_extensao", "", "application/octet-stream"),
    ],
)
def test_o_tipo_vem_da_extensao_e_o_mime_vem_do_tipo(nome: str, tipo: str, mime: str) -> None:
    assert attachments.file_type(nome) == tipo
    assert attachments.mime_type_of(nome) == mime


def test_sem_versao_o_grupo_vale_os_valores_iniciais() -> None:
    limites = attachments.limits_from_values({})

    assert limites.max_megabytes == 25
    assert limites.types == TIPOS_INICIAIS


def test_o_grupo_lido_dos_parametros_limpa_os_tipos_e_converte_o_limite() -> None:
    limites = attachments.limits_from_values(
        {"tamanhoMaximoMb": 2.5, "tiposAceitos": ["pdf", ".PNG", "pdf", "", "jpeg"]}
    )

    assert limites.max_megabytes == 2.5
    assert limites.types == ("PDF", "PNG", "JPG")
    assert limites.extensions == ("pdf", "png", "jpg", "jpeg")


@pytest.mark.parametrize(
    "valores",
    [
        {"tamanhoMaximoMb": 0, "tiposAceitos": []},
        {"tamanhoMaximoMb": -5, "tiposAceitos": "PDF"},
        {"tamanhoMaximoMb": True, "tiposAceitos": None},
        {"tamanhoMaximoMb": "25", "tiposAceitos": 7},
        {"tamanhoMaximoMb": float("inf"), "tiposAceitos": [""]},
    ],
)
def test_valor_inutilizavel_do_grupo_cai_no_valor_inicial(valores: dict[str, object]) -> None:
    limites = attachments.limits_from_values(valores)

    assert limites.max_megabytes == 25
    assert limites.types == TIPOS_INICIAIS


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("laudo.pdf", "laudo.pdf"),
        ("C:\\Users\\ana\\laudo final.pdf", "laudo final.pdf"),
        ("/obra/relatório.pdf", "relatório.pdf"),
        ("relato\u0301rio.pdf", "relatório.pdf"),
        ("laudo\r\nSet-Cookie: x.pdf", "laudoSet-Cookie: x.pdf"),
        ("  com espaços  .pdf  ", "com espaços  .pdf"),
        ("pasta/", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_o_nome_perde_a_pasta_os_caracteres_de_controle_e_ganha_acento_composto(
    bruto: str | None, esperado: str
) -> None:
    assert attachments.clean_name(bruto) == esperado


def test_nome_muito_longo_perde_o_fim_do_miolo_e_guarda_a_extensao() -> None:
    nome = attachments.clean_name("a" * 300 + ".pdf")

    assert len(nome) == attachments.MAX_NAME_CHARS
    assert nome.endswith("aaa.pdf")


@pytest.mark.parametrize(
    ("tamanho", "texto"),
    [
        (0, "0 B"),
        (1, "1 B"),
        (1023, "1023 B"),
        (1024, "1,0 KB"),
        (1025, "1,1 KB"),
        (1536, "1,5 KB"),
        (MEGABYTE - 1, "1,0 MB"),
        (MEGABYTE, "1,0 MB"),
        (MEGABYTE + 1, "1,1 MB"),
        (25 * MEGABYTE, "25,0 MB"),
        (25 * MEGABYTE + 1, "25,1 MB"),
    ],
)
def test_o_tamanho_e_escrito_arredondado_para_cima_com_virgula(tamanho: int, texto: str) -> None:
    assert attachments.format_size(tamanho) == texto


# ── The registry of origin types ─────────────────────────────────────────


def test_dois_modulos_nao_dividem_a_mesma_tabela_de_origem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attachment_origins, "_ORIGINS", {})

    def leitor_do_planejamento(_session: Session, **_campos: object) -> None:
        return None

    def leitor_do_hse(_session: Session, **_campos: object) -> None:
        return None

    punch = OriginType(table="punch_item", module="planejamento", read=leitor_do_planejamento)
    attachment_origins.register(punch)
    attachment_origins.register(punch)

    with pytest.raises(ValueError, match="já está registrado por outro módulo"):
        attachment_origins.register(
            OriginType(table="punch_item", module="hse", read=leitor_do_hse)
        )

    assert attachment_origins.find("punch_item") is punch
    assert attachment_origins.find("outra_tabela") is None
    assert attachment_origins.registered() == [punch]


# ── The fixtures of the database tests ───────────────────────────────────


@dataclass
class Origens:
    """The records the test origin types know, and who the reserved one lets in."""

    projeto_id: int
    participantes: set[str] = field(default_factory=set)
    removidos: set[int] = field(default_factory=set)


def _criar_pessoas(session: Session) -> None:
    """One person of each profile that matters, and a supplier, in the register."""
    criar_colaborador(session, email=VERA, nome="Vera Visualizadora", perfil="Visualizador")
    criar_colaborador(session, email=MARIO, nome="Mário Membro", perfil="Membro")
    criar_colaborador(session, email=GIL, nome="Gil Gestor", perfil="Gestor")
    criar_colaborador(session, email=ADA, nome="Ada Admin", perfil="Admin")
    criar_colaborador(
        session,
        email=FABIO,
        nome="Fábio Fornecedor",
        perfil="Membro",
        vinculo="Fornecedor",
        empresa=criar_empresa(session, "Contratada Alfa"),
    )


@pytest.fixture
def origens(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> Origens:
    """The people, a project and two origin types in a registry of their own."""
    _criar_pessoas(db_session)
    projeto = criar_projeto(db_session, codigo="TN-ANEXOS-001", nome="Projeto dos anexos")
    estado = Origens(projeto_id=projeto.id)

    def ler_registro(_session: Session, *, user: User, record_id: int) -> OriginRecord | None:
        if record_id in estado.removidos or record_id not in (REGISTRO_COMUM, REGISTRO_RESERVADO):
            return None
        if record_id == REGISTRO_RESERVADO and user.email not in estado.participantes:
            raise AccessDeniedError(RECUSA_DO_REGISTRO)
        return OriginRecord(project_id=estado.projeto_id)

    def ler_dado_pessoal(
        _session: Session, *, record_id: int, **_campos: object
    ) -> OriginRecord | None:
        if record_id != REGISTRO_PESSOAL:
            return None
        return OriginRecord(project_id=estado.projeto_id, restricted=True)

    monkeypatch.setattr(attachment_origins, "_ORIGINS", {})
    attachment_origins.register(
        OriginType(table="teste_registro", module="planejamento", read=ler_registro)
    )
    attachment_origins.register(
        OriginType(table="teste_dado_pessoal", module="hse", read=ler_dado_pessoal)
    )
    return estado


@pytest.fixture
def pasta_de_anexos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The environment points the local adapter at a folder of the test."""
    monkeypatch.setenv(config.ATTACHMENT_STORAGE_VARIABLE, config.ATTACHMENT_STORAGE_LOCAL)
    monkeypatch.setenv(config.ATTACHMENT_FOLDER_VARIABLE, str(tmp_path))
    return tmp_path


@pytest.fixture
def hoje_fixo(monkeypatch: pytest.MonkeyPatch) -> date:
    """The routes read the limits in force on this date, whatever day the suite runs."""
    monkeypatch.setattr(calendario, "today", lambda: REFERENCIA)
    return REFERENCIA


def _usuario(session: Session, email: str) -> User:
    """The ``User`` the login resolves for the e-mail, as a route would hand it to the facade."""
    return auth.resolve_user(session, requisicao(email=email))


def _novo(**mudancas: object) -> NewAttachment:
    campos: dict[str, object] = {
        "origin_table": "teste_registro",
        "origin_record_id": REGISTRO_COMUM,
        "file_name": "laudo.pdf",
        "content": b"%PDF-1.7 conteudo do laudo",
    }
    return NewAttachment(**(campos | mudancas))


def _enviar(
    session: Session,
    armazenamento: ArmazenamentoEmMemoria | None,
    *,
    email: str = MARIO,
    referencia: date = REFERENCIA,
    **mudancas: object,
) -> Attachment:
    return attachments.upload(
        session,
        user=_usuario(session, email),
        new=_novo(**mudancas),
        reference_date=referencia,
        storage=armazenamento,
    )


def _baixar(
    session: Session,
    armazenamento: ArmazenamentoEmMemoria | None,
    anexo_id: int,
    *,
    email: str,
) -> attachments.Download | None:
    return attachments.open_download(
        session, user=_usuario(session, email), attachment_id=anexo_id, storage=armazenamento
    )


def _painel(
    session: Session, *, email: str, tabela: str = "teste_registro", registro: int = REGISTRO_COMUM
) -> attachments.AttachmentPanel:
    return attachments.panel(
        session,
        user=_usuario(session, email),
        origin_table=tabela,
        origin_record_id=registro,
        reference_date=REFERENCIA,
    )


def _anexos_gravados(session: Session) -> list[Attachment]:
    statement = (
        sa.select(Attachment)
        .where(Attachment.origin_table.in_(TABELAS_DE_TESTE))
        .order_by(Attachment.id)
    )
    return list(session.scalars(statement).all())


def _linhas_de_trilha(session: Session) -> int:
    statement = (
        sa.select(sa.func.count()).select_from(AuditEntry).where(AuditEntry.entity == "anexo")
    )
    return session.scalar(statement) or 0


def _nova_versao_dos_parametros(
    session: Session, *, megabytes: float, tipos: list[str], vigente_desde: date
) -> None:
    """Version 1 of every group, and a version of the Anexos group that changes the limits."""
    autor = criar_colaborador(session, email="autor.parametros@example.invalid", perfil="Gestor")
    configuracoes.seed_initial_parameters(
        session, author_id=autor.id, effective_from=date(2026, 9, 25)
    )
    configuracoes.save_parameter_group(
        session,
        author_id=autor.id,
        group="anexos",
        values={"tamanhoMaximoMb": megabytes, "tiposAceitos": tipos},
        effective_from=vigente_desde,
        justification="Alterar os limites dos anexos",
    )


# ── Upload (facade) ──────────────────────────────────────────────────────


def test_envio_grava_os_metadados_a_trilha_e_o_arquivo(
    db_session: Session, origens: Origens, armazenamento: ArmazenamentoEmMemoria
) -> None:
    conteudo = b"%PDF-1.7 corpo do relatorio"

    anexo = _enviar(db_session, armazenamento, file_name="Relatório final.pdf", content=conteudo)

    assert anexo.id is not None
    assert anexo.name == "Relatório final.pdf"
    assert anexo.mime_type == "application/pdf"
    assert anexo.size_bytes == len(conteudo)
    assert anexo.file_hash == hashlib.sha256(conteudo).hexdigest()
    assert (anexo.origin_table, anexo.origin_record_id) == ("teste_registro", REGISTRO_COMUM)
    assert anexo.project_id == origens.projeto_id
    assert anexo.uploaded_by_id == _usuario(db_session, MARIO).id
    assert armazenamento.arquivos == {f"{origens.projeto_id}/{anexo.id}": conteudo}

    trilha = db_session.scalars(
        sa.select(AuditEntry).where(AuditEntry.entity == "anexo", AuditEntry.record_id == anexo.id)
    ).all()
    assert [linha.action for linha in trilha] == ["criado"]
    assert trilha[0].user_id == anexo.uploaded_by_id
    assert trilha[0].project_id == origens.projeto_id
    assert trilha[0].after is not None
    assert trilha[0].after["nome"] == "Relatório final.pdf"
    assert trilha[0].after["hash"] == anexo.file_hash


@pytest.mark.usefixtures("origens")
def test_o_hash_guardado_e_o_sha256_do_conteudo_em_hexadecimal(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    anexo = _enviar(db_session, armazenamento, content=b"abc")

    # The first test vector of the SHA-256 standard: the digest of the three bytes "abc".
    assert anexo.file_hash == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@pytest.mark.usefixtures("origens")
def test_o_nome_guardado_perde_a_pasta_e_o_mime_vem_da_extensao(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    anexo = _enviar(db_session, armazenamento, file_name="C:\\fotos\\obra.JPEG")

    assert anexo.name == "obra.JPEG"
    assert anexo.mime_type == "image/jpeg"


@pytest.mark.usefixtures("origens")
@pytest.mark.parametrize(
    ("mudancas", "mensagem"),
    [
        ({"file_name": "programa.exe"}, f"Tipo de arquivo não aceito (.exe). {ACEITOS_INICIAIS}"),
        ({"file_name": "sem_extensao"}, f"O arquivo não tem extensão. {ACEITOS_INICIAIS}"),
        ({"content": b""}, "O arquivo está vazio."),
        ({"file_name": None}, "Escolha um arquivo para anexar."),
        ({"file_name": ""}, "Escolha um arquivo para anexar."),
        ({"file_name": "pasta/"}, "Escolha um arquivo para anexar."),
    ],
)
def test_envio_recusado_e_422_com_a_mensagem_no_campo_e_nada_fica_gravado(
    db_session: Session,
    armazenamento: ArmazenamentoEmMemoria,
    mudancas: dict[str, object],
    mensagem: str,
) -> None:
    with pytest.raises(InvalidDataError) as erro:
        _enviar(db_session, armazenamento, **mudancas)

    assert erro.value.detail == {"arquivo": mensagem}
    assert _anexos_gravados(db_session) == []
    assert _linhas_de_trilha(db_session) == 0
    assert armazenamento.arquivos == {}


def test_arquivo_de_exatamente_25_mb_e_aceito_e_um_byte_a_mais_e_recusado(
    db_session: Session, origens: Origens, armazenamento: ArmazenamentoEmMemoria
) -> None:
    no_limite = b"x" * (25 * MEGABYTE)

    anexo = _enviar(db_session, armazenamento, file_name="no_limite.pdf", content=no_limite)
    with pytest.raises(InvalidDataError) as erro:
        _enviar(db_session, armazenamento, file_name="acima.pdf", content=no_limite + b"x")

    assert anexo.size_bytes == 25 * MEGABYTE
    assert erro.value.detail == {"arquivo": "O arquivo tem 25,1 MB, acima do limite de 25 MB."}
    assert _anexos_gravados(db_session) == [anexo]
    assert list(armazenamento.arquivos) == [f"{origens.projeto_id}/{anexo.id}"]


@pytest.mark.usefixtures("origens")
def test_os_limites_seguem_a_versao_dos_parametros_vigente_na_data(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    _nova_versao_dos_parametros(
        db_session, megabytes=1, tipos=["PDF"], vigente_desde=date(2026, 10, 1)
    )
    antes, depois = date(2026, 9, 30), date(2026, 10, 1)

    planilha_antiga = _enviar(
        db_session,
        armazenamento,
        referencia=antes,
        file_name="planilha.xlsx",
        content=b"x" * (2 * MEGABYTE),
    )
    with pytest.raises(InvalidDataError) as tipo:
        _enviar(db_session, armazenamento, referencia=depois, file_name="planilha.xlsx")
    with pytest.raises(InvalidDataError) as tamanho:
        _enviar(
            db_session,
            armazenamento,
            referencia=depois,
            file_name="grande.pdf",
            content=b"x" * (MEGABYTE + 1),
        )
    no_limite = _enviar(
        db_session,
        armazenamento,
        referencia=depois,
        file_name="no_limite.pdf",
        content=b"x" * MEGABYTE,
    )

    assert planilha_antiga.size_bytes == 2 * MEGABYTE
    assert tipo.value.detail == {"arquivo": "Tipo de arquivo não aceito (.xlsx). Aceitos: PDF."}
    assert tamanho.value.detail == {"arquivo": "O arquivo tem 1,1 MB, acima do limite de 1 MB."}
    assert no_limite.size_bytes == MEGABYTE


@pytest.mark.usefixtures("origens")
def test_origem_desconhecida_e_registro_inexistente_sao_422(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    with pytest.raises(InvalidDataError) as desconhecida:
        _enviar(db_session, armazenamento, origin_table="nao_existe")
    with pytest.raises(InvalidDataError) as inexistente:
        _enviar(db_session, armazenamento, origin_record_id=REGISTRO_INEXISTENTE)

    assert desconhecida.value.detail == attachments.UNKNOWN_ORIGIN_MESSAGE
    assert inexistente.value.detail == attachments.MISSING_RECORD_MESSAGE
    assert _anexos_gravados(db_session) == []


@pytest.mark.usefixtures("origens")
def test_falha_ao_guardar_o_arquivo_sobe_como_a_excecao_do_meio_para_a_requisicao_desfazer_tudo(
    db_session: Session,
) -> None:
    class ArmazenamentoSemEspaco:
        def save(self, key: str, content: bytes) -> None:
            message = f"sem espaço para {key} ({len(content)} bytes)"
            raise OSError(message)

        def read(self, key: str) -> bytes:
            raise OSError(key)

    with pytest.raises(OSError, match=r"sem espaço para \d+/\d+"):
        attachments.upload(
            db_session,
            user=_usuario(db_session, MARIO),
            new=_novo(),
            reference_date=REFERENCIA,
            storage=ArmazenamentoSemEspaco(),
        )


# ── Permissions (facade) ─────────────────────────────────────────────────


@pytest.mark.usefixtures("origens")
def test_visualizador_le_mas_nao_envia(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    with pytest.raises(AccessDeniedError) as erro:
        _enviar(db_session, armazenamento, email=VERA)

    assert "Esta operação exige o perfil Membro, Gestor ou Admin." in str(erro.value)
    assert "O seu perfil é Visualizador." in str(erro.value)
    assert _painel(db_session, email=VERA).can_upload is False
    assert _painel(db_session, email=MARIO).can_upload is True


@pytest.mark.usefixtures("origens")
def test_fornecedor_nao_envia_nem_alcanca_o_modulo_dono_do_registro(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    anexo = _enviar(db_session, armazenamento, email=MARIO)

    with pytest.raises(AccessDeniedError) as envio:
        _enviar(db_session, armazenamento, email=FABIO)
    with pytest.raises(AccessDeniedError) as lista:
        _painel(db_session, email=FABIO)
    with pytest.raises(AccessDeniedError) as download:
        _baixar(db_session, armazenamento, anexo.id, email=FABIO)

    for erro in (envio, lista, download):
        assert str(erro.value) == rbac.SUPPLIER_SCOPE_MESSAGE


def test_registro_reservado_recusa_quem_o_modulo_dono_nao_deixa_ler(
    db_session: Session, origens: Origens, armazenamento: ArmazenamentoEmMemoria
) -> None:
    origens.participantes.add(GIL)
    anexo = _enviar(db_session, armazenamento, email=GIL, origin_record_id=REGISTRO_RESERVADO)

    with pytest.raises(AccessDeniedError, match=RECUSA_DO_REGISTRO):
        _enviar(db_session, armazenamento, email=MARIO, origin_record_id=REGISTRO_RESERVADO)
    with pytest.raises(AccessDeniedError, match=RECUSA_DO_REGISTRO):
        _painel(db_session, email=MARIO, registro=REGISTRO_RESERVADO)
    with pytest.raises(AccessDeniedError, match=RECUSA_DO_REGISTRO):
        _baixar(db_session, armazenamento, anexo.id, email=MARIO)

    liberado = _baixar(db_session, armazenamento, anexo.id, email=GIL)
    assert liberado is not None
    assert liberado.name == "laudo.pdf"
    assert _anexos_gravados(db_session) == [anexo]


# ── The list of a record ─────────────────────────────────────────────────


def test_a_lista_mostra_nome_tamanho_quem_enviou_e_quando(
    db_session: Session, origens: Origens, armazenamento: ArmazenamentoEmMemoria
) -> None:
    origens.participantes.add(GIL)
    primeiro = _enviar(
        db_session, armazenamento, email=MARIO, file_name="planta.dwg", content=b"x" * 1536
    )
    segundo = _enviar(db_session, armazenamento, email=GIL, file_name="foto.png")
    _enviar(db_session, armazenamento, email=GIL, origin_record_id=REGISTRO_RESERVADO)

    painel = _painel(db_session, email=VERA)

    assert painel.can_view is True
    assert painel.limits == LIMITES_INICIAIS
    assert [
        (entrada.id, entrada.name, entrada.size_bytes, entrada.uploaded_by, entrada.uploaded_at)
        for entrada in painel.entries
    ] == [
        (primeiro.id, "planta.dwg", 1536, "Mário Membro", primeiro.uploaded_at),
        (segundo.id, "foto.png", segundo.size_bytes, "Gil Gestor", segundo.uploaded_at),
    ]


@pytest.mark.usefixtures("origens")
def test_registro_sem_anexo_tem_a_lista_vazia(db_session: Session) -> None:
    painel = _painel(db_session, email=MARIO)

    assert painel.entries == ()
    assert painel.can_view is True


# ── Download (facade) ────────────────────────────────────────────────────


@pytest.mark.usefixtures("origens")
def test_download_entrega_o_arquivo_com_o_nome_e_o_tipo_de_quando_foi_enviado(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    conteudo = b"conteudo do laudo"
    anexo = _enviar(
        db_session, armazenamento, email=MARIO, file_name="Laudo técnico.pdf", content=conteudo
    )

    download = _baixar(db_session, armazenamento, anexo.id, email=VERA)

    assert download == attachments.Download(
        name="Laudo técnico.pdf", mime_type="application/pdf", content=conteudo
    )


@pytest.mark.usefixtures("origens")
def test_download_de_anexo_que_nao_existe_nao_entrega_nada(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    assert _baixar(db_session, armazenamento, 999_999_999, email=MARIO) is None


def test_download_de_registro_que_deixou_de_existir_nao_entrega_nada(
    db_session: Session, origens: Origens, armazenamento: ArmazenamentoEmMemoria
) -> None:
    anexo = _enviar(db_session, armazenamento)
    origens.removidos.add(REGISTRO_COMUM)

    assert _baixar(db_session, armazenamento, anexo.id, email=MARIO) is None


@pytest.mark.usefixtures("origens")
def test_download_sem_o_arquivo_no_armazenamento_nao_entrega_nada_e_registra_o_erro(
    db_session: Session,
    armazenamento: ArmazenamentoEmMemoria,
    caplog: pytest.LogCaptureFixture,
) -> None:
    anexo = _enviar(db_session, armazenamento)
    armazenamento.arquivos.clear()

    with caplog.at_level(logging.ERROR, logger="src.core.attachments"):
        download = _baixar(db_session, armazenamento, anexo.id, email=MARIO)

    assert download is None
    assert f"O arquivo do anexo {anexo.id} não está no armazenamento." in caplog.text


@pytest.mark.usefixtures("origens")
def test_anexo_cujo_tipo_de_origem_ninguem_mais_registra_e_recusado(
    db_session: Session,
    armazenamento: ArmazenamentoEmMemoria,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anexo = _enviar(db_session, armazenamento)
    monkeypatch.setattr(attachment_origins, "_ORIGINS", {})

    with pytest.raises(AccessDeniedError) as erro:
        _baixar(db_session, armazenamento, anexo.id, email=ADA)

    assert str(erro.value) == attachments.UNOWNED_ATTACHMENT_MESSAGE


# ── Personal data (Q35) ──────────────────────────────────────────────────


@pytest.mark.usefixtures("origens")
def test_anexo_de_dado_pessoal_so_e_visto_por_gestor_e_admin_mas_o_membro_envia(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    anexo = _enviar(
        db_session,
        armazenamento,
        email=MARIO,
        origin_table="teste_dado_pessoal",
        origin_record_id=REGISTRO_PESSOAL,
        file_name="atestado.pdf",
    )

    for email in (MARIO, VERA):
        with pytest.raises(AccessDeniedError) as erro:
            _baixar(db_session, armazenamento, anexo.id, email=email)
        assert "Esta operação exige o perfil Gestor ou Admin." in str(erro.value)
    for email in (GIL, ADA):
        liberado = _baixar(db_session, armazenamento, anexo.id, email=email)
        assert liberado is not None
        assert liberado.name == "atestado.pdf"


@pytest.mark.usefixtures("origens")
def test_a_lista_de_dado_pessoal_some_para_quem_nao_pode_ver_e_o_envio_continua(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    anexo = _enviar(
        db_session,
        armazenamento,
        origin_table="teste_dado_pessoal",
        origin_record_id=REGISTRO_PESSOAL,
    )

    def painel_de(email: str) -> attachments.AttachmentPanel:
        return _painel(
            db_session, email=email, tabela="teste_dado_pessoal", registro=REGISTRO_PESSOAL
        )

    membro, visualizador, gestor = painel_de(MARIO), painel_de(VERA), painel_de(GIL)

    assert (membro.can_view, membro.can_upload, membro.entries) == (False, True, ())
    assert (visualizador.can_view, visualizador.can_upload, visualizador.entries) == (
        False,
        False,
        (),
    )
    assert gestor.can_view is True
    assert [entrada.id for entrada in gestor.entries] == [anexo.id]


# ── Evidence ─────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("origens")
def test_has_evidence_responde_se_o_registro_tem_ao_menos_um_anexo(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    def tem(tabela: str, registro: int) -> bool:
        return attachments.has_evidence(db_session, origin_table=tabela, origin_record_id=registro)

    assert tem("teste_registro", REGISTRO_COMUM) is False

    _enviar(db_session, armazenamento)

    assert tem("teste_registro", REGISTRO_COMUM) is True
    assert tem("teste_registro", REGISTRO_RESERVADO) is False
    assert tem("teste_dado_pessoal", REGISTRO_COMUM) is False

    _enviar(db_session, armazenamento, file_name="segundo.pdf")

    assert tem("teste_registro", REGISTRO_COMUM) is True


@pytest.mark.usefixtures("origens")
def test_has_evidence_nao_depende_de_quem_pergunta_nem_de_o_anexo_ser_restrito(
    db_session: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    _enviar(
        db_session,
        armazenamento,
        origin_table="teste_dado_pessoal",
        origin_record_id=REGISTRO_PESSOAL,
    )

    assert attachments.has_evidence(
        db_session, origin_table="teste_dado_pessoal", origin_record_id=REGISTRO_PESSOAL
    )


# ── The environment picks the storage ────────────────────────────────────


def test_trocar_a_variavel_de_ambiente_troca_o_armazenamento_sem_mudar_o_codigo(
    db_session: Session,
    origens: Origens,
    pasta_de_anexos: Path,
    sdk_do_azure: SdkFalso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    na_pasta = _enviar(db_session, None, file_name="local.pdf", content=b"no disco")

    monkeypatch.setenv(config.ATTACHMENT_STORAGE_VARIABLE, config.ATTACHMENT_STORAGE_BLOB)
    monkeypatch.setenv("GESTNOW_BLOB_CONEXAO", "conexao-de-teste")
    monkeypatch.delenv("GESTNOW_BLOB_CONTAINER", raising=False)
    no_blob = _enviar(db_session, None, file_name="nuvem.pdf", content=b"no blob")

    assert (pasta_de_anexos / str(origens.projeto_id) / str(na_pasta.id)).read_bytes() == (
        b"no disco"
    )
    assert sdk_do_azure.containers["anexos"].blobs == {
        f"{origens.projeto_id}/{no_blob.id}": b"no blob"
    }
    do_blob = _baixar(db_session, None, no_blob.id, email=VERA)
    assert do_blob is not None
    assert do_blob.content == b"no blob"

    monkeypatch.setenv(config.ATTACHMENT_STORAGE_VARIABLE, config.ATTACHMENT_STORAGE_LOCAL)
    da_pasta = _baixar(db_session, None, na_pasta.id, email=VERA)
    assert da_pasta is not None
    assert da_pasta.content == b"no disco"


# ── Routes: the requests ─────────────────────────────────────────────────


def _multipart(campos: dict[str, str], arquivo: tuple[str, bytes] | None) -> tuple[bytes, str]:
    """A ``multipart/form-data`` body as the browser sends it, and its Content-Type.

    The part of the file claims ``text/html`` on purpose: the server never trusts it.
    """
    fronteira = "fronteira-do-teste-de-anexos"
    partes = [
        f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n'.encode()
        for nome, valor in campos.items()
    ]
    if arquivo is not None:
        nome_do_arquivo, conteudo = arquivo
        cabecalho = (
            f"--{fronteira}\r\n"
            f'Content-Disposition: form-data; name="arquivo"; filename="{nome_do_arquivo}"\r\n'
            "Content-Type: text/html\r\n\r\n"
        )
        partes.append(cabecalho.encode() + conteudo + b"\r\n")
    partes.append(f"--{fronteira}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={fronteira}"


def _post(
    email: str,
    campos: dict[str, str],
    arquivo: tuple[str, bytes] | None,
    *,
    alpine: bool = True,
) -> func.HttpResponse:
    corpo, tipo = _multipart(campos, arquivo)
    headers = {"Content-Type": tipo, PRINCIPAL_HEADER: cabecalho_do_principal(email)}
    if alpine:
        headers.update({"X-Alpine-Request": "true", "X-Alpine-Target": ALVO})
    return upload_attachment(
        func.HttpRequest(
            method="POST",
            url="/api/anexos/enviar",
            headers=headers,
            params={},
            route_params={},
            body=corpo,
        )
    )


def _registro(tabela: str = "teste_registro", registro: int = REGISTRO_COMUM) -> dict[str, str]:
    return {"origem": tabela, "registro": str(registro)}


def _get_lista(email: str, **params: str) -> func.HttpResponse:
    return list_attachments(
        func.HttpRequest(
            method="GET",
            url="/api/anexos",
            headers={
                "X-Alpine-Request": "true",
                "X-Alpine-Target": ALVO,
                PRINCIPAL_HEADER: cabecalho_do_principal(email),
            },
            params=params,
            route_params={},
            body=b"",
        )
    )


def _get_arquivo(email: str | None, anexo_id: str) -> func.HttpResponse:
    """The link of the list, opened by the browser: no Alpine header at all."""
    headers = {PRINCIPAL_HEADER: cabecalho_do_principal(email)} if email is not None else {}
    return download_attachment(
        func.HttpRequest(
            method="GET",
            url=f"/api/anexos/{anexo_id}/baixar",
            headers=headers,
            params={},
            route_params={"anexo_id": anexo_id},
            body=b"",
        )
    )


def _corpo(resposta: func.HttpResponse) -> str:
    return resposta.get_body().decode()


def _texto_do(tags: list[Tag], element_id: str) -> str:
    """The text of the element with the id, which the fragment must have."""
    tag = find_by_id(tags, element_id)
    assert tag is not None, element_id
    return tag.clean_text()


def _anexo_na_pasta(session: Session, **mudancas: object) -> Attachment:
    """An attachment kept in the folder of the environment, as the upload route keeps it."""
    return _enviar(session, None, **mudancas)


# ── Routes: upload ───────────────────────────────────────────────────────


@pytest.mark.usefixtures("origens", "hoje_fixo")
def test_envio_pela_rota_grava_o_arquivo_e_responde_a_lista_atualizada_com_o_toast(
    sessao_das_rotas: Session, pasta_de_anexos: Path
) -> None:
    conteudo = b"%PDF-1.7 vistoria"

    resposta = _post(MARIO, _registro(), ("Relatório de vistoria.pdf", conteudo))

    assert resposta.status_code == 200
    assert resposta.headers["X-TN-Toast"] == cabecalhos_de_toast("Anexo enviado.")["X-TN-Toast"]
    assert resposta.headers["X-TN-Toast-Tipo"] == "ok"
    (anexo,) = _anexos_gravados(sessao_das_rotas)
    assert anexo.name == "Relatório de vistoria.pdf"
    # The part claimed text/html: the type is the server's, from the extension.
    assert anexo.mime_type == "application/pdf"
    assert (pasta_de_anexos / str(anexo.project_id) / str(anexo.id)).read_bytes() == conteudo

    tags = parse_tags(_corpo(resposta))
    assert find_by_id(tags, ALVO) is not None
    assert _texto_do(tags, f"{ALVO}-titulo") == "Anexos (1)"
    (linha,) = [tr for tr in find_all(tags, "tr") if "Relatório de vistoria.pdf" in tr.clean_text()]
    assert f"{len(conteudo)} B" in linha.clean_text()
    assert "Mário Membro" in linha.clean_text()
    assert DATA_E_HORA.search(linha.clean_text())
    (link,) = find_all(tags, "a", "anexos__link")
    assert link.attrs["href"] == f"/api/anexos/{anexo.id}/baixar"
    assert "download" in link.attrs


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos", "sessao_das_rotas")
def test_o_fragmento_traz_o_formulario_de_envio_do_design_system() -> None:
    resposta = _get_lista(MARIO, origem="teste_registro", registro=str(REGISTRO_COMUM))

    assert resposta.status_code == 200
    tags = parse_tags(_corpo(resposta))
    assert find_by_id(tags, ALVO) is not None
    (formulario,) = find_all(tags, "form", "upload")
    assert formulario.attrs["method"] == "post"
    assert formulario.attrs["action"] == "/api/anexos/enviar"
    assert formulario.attrs["enctype"] == "multipart/form-data"
    assert formulario.attrs["x-target"] == ALVO
    ocultos = {
        campo.attrs["name"]: campo.attrs["value"]
        for campo in find_all(tags, "input")
        if campo.attrs.get("type") == "hidden"
    }
    assert ocultos == {"origem": "teste_registro", "registro": str(REGISTRO_COMUM)}
    campo = find_by_id(tags, f"{ALVO}-arquivo")
    assert campo is not None
    assert campo.attrs["type"] == "file"
    assert campo.attrs["name"] == "arquivo"
    assert campo.attrs["accept"] == ".pdf,.jpg,.png,.docx,.xlsx,.pptx,.dwg,.zip,.jpeg"
    assert "required" in campo.attrs
    assert "aria-invalid" not in campo.attrs
    assert _texto_do(tags, f"{ALVO}-dica") == (
        "Até 25 MB por arquivo. Tipos aceitos: PDF, JPG, PNG, DOCX, XLSX, PPTX, DWG, ZIP."
    )
    assert _texto_do(tags, f"{ALVO}-titulo") == "Anexos (0)"
    assert "Nenhum anexo enviado ainda." in _corpo(resposta)
    assert find_all(tags, "table") == []


@pytest.mark.usefixtures("origens", "hoje_fixo")
def test_arquivo_acima_do_limite_volta_422_com_a_mensagem_no_campo_e_nada_e_gravado(
    sessao_das_rotas: Session, pasta_de_anexos: Path
) -> None:
    _nova_versao_dos_parametros(
        sessao_das_rotas,
        megabytes=1,
        tipos=list(TIPOS_INICIAIS),
        vigente_desde=date(2026, 10, 1),
    )

    resposta = _post(MARIO, _registro(), ("grande.pdf", b"x" * (MEGABYTE + 1)))

    assert resposta.status_code == 422
    assert "X-TN-Toast" not in resposta.headers
    tags = parse_tags(_corpo(resposta))
    assert _texto_do(tags, f"{ALVO}-erro") == "O arquivo tem 1,1 MB, acima do limite de 1 MB."
    campo = find_by_id(tags, f"{ALVO}-arquivo")
    assert campo is not None
    assert campo.attrs["aria-invalid"] == "true"
    assert campo.has_class("input--erro")
    assert f"{ALVO}-erro" in campo.attrs["aria-describedby"]
    assert len(find_all(tags, "form", "upload")) == 1
    assert _anexos_gravados(sessao_das_rotas) == []
    assert list(pasta_de_anexos.rglob("*")) == []


@pytest.mark.usefixtures("origens", "hoje_fixo")
def test_tipo_fora_da_lista_volta_422_com_a_mensagem_no_campo(
    sessao_das_rotas: Session, pasta_de_anexos: Path
) -> None:
    resposta = _post(MARIO, _registro(), ("programa.exe", b"MZ conteudo"))

    assert resposta.status_code == 422
    tags = parse_tags(_corpo(resposta))
    assert _texto_do(tags, f"{ALVO}-erro") == (
        f"Tipo de arquivo não aceito (.exe). {ACEITOS_INICIAIS}"
    )
    assert _anexos_gravados(sessao_das_rotas) == []
    assert list(pasta_de_anexos.rglob("*")) == []


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
@pytest.mark.parametrize("arquivo", [None, ("", b"")])
def test_envio_sem_escolher_arquivo_volta_422_pedindo_o_arquivo(
    sessao_das_rotas: Session, arquivo: tuple[str, bytes] | None
) -> None:
    resposta = _post(MARIO, _registro(), arquivo)

    assert resposta.status_code == 422
    assert _texto_do(parse_tags(_corpo(resposta)), f"{ALVO}-erro") == (
        "Escolha um arquivo para anexar."
    )
    assert _anexos_gravados(sessao_das_rotas) == []


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_visualizador_recebe_403_no_envio(sessao_das_rotas: Session) -> None:
    resposta = _post(VERA, _registro(), ("laudo.pdf", b"conteudo"))

    assert resposta.status_code == 403
    assert "Não foi possível concluir." in _corpo(resposta)
    assert "O seu perfil é Visualizador." in _corpo(resposta)
    assert _anexos_gravados(sessao_das_rotas) == []


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_quem_nao_pode_ler_o_registro_de_origem_recebe_403_no_envio(
    sessao_das_rotas: Session,
) -> None:
    resposta = _post(MARIO, _registro(registro=REGISTRO_RESERVADO), ("laudo.pdf", b"conteudo"))

    assert resposta.status_code == 403
    assert RECUSA_DO_REGISTRO in _corpo(resposta)
    assert _anexos_gravados(sessao_das_rotas) == []


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
@pytest.mark.parametrize(
    ("campos", "mensagem"),
    [
        (_registro(tabela="nao_existe"), attachments.UNKNOWN_ORIGIN_MESSAGE),
        (_registro(registro=REGISTRO_INEXISTENTE), attachments.MISSING_RECORD_MESSAGE),
        ({"origem": "teste_registro", "registro": "abc"}, FALTA_O_REGISTRO),
        ({"origem": "teste_registro"}, FALTA_O_REGISTRO),
        ({"registro": "101"}, FALTA_O_REGISTRO),
    ],
)
def test_registro_de_origem_invalido_volta_422_e_nada_e_gravado(
    sessao_das_rotas: Session, campos: dict[str, str], mensagem: str
) -> None:
    resposta = _post(MARIO, campos, ("laudo.pdf", b"conteudo"))

    assert resposta.status_code == 422
    assert mensagem in _corpo(resposta)
    assert _anexos_gravados(sessao_das_rotas) == []


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_o_envio_sem_o_cabecalho_do_alpine_redireciona_para_o_shell(
    sessao_das_rotas: Session,
) -> None:
    resposta = _post(MARIO, _registro(), ("laudo.pdf", b"conteudo"), alpine=False)

    assert resposta.status_code == 302
    assert resposta.headers["Location"] == "/index.html"
    assert _anexos_gravados(sessao_das_rotas) == []


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_quem_nao_esta_no_cadastro_recebe_403_no_envio(sessao_das_rotas: Session) -> None:
    resposta = _post("intruso@example.invalid", _registro(), ("laudo.pdf", b"conteudo"))

    assert resposta.status_code == 403
    assert auth.NOT_REGISTERED_MESSAGE in _corpo(resposta)
    assert _anexos_gravados(sessao_das_rotas) == []


# ── Routes: the list ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_o_visualizador_ve_a_lista_mas_nao_o_formulario_de_envio(
    sessao_das_rotas: Session,
) -> None:
    _post(MARIO, _registro(), ("laudo.pdf", b"conteudo"))

    resposta = _get_lista(VERA, origem="teste_registro", registro=str(REGISTRO_COMUM))

    assert resposta.status_code == 200
    tags = parse_tags(_corpo(resposta))
    assert find_all(tags, "form") == []
    assert len(find_all(tags, "a", "anexos__link")) == 1
    assert len(_anexos_gravados(sessao_das_rotas)) == 1


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos", "sessao_das_rotas")
@pytest.mark.parametrize(
    "params",
    [{}, {"origem": "teste_registro"}, {"registro": "101"}, {"origem": "x", "registro": "1x"}],
)
def test_lista_sem_o_registro_ou_com_o_registro_mal_formado_volta_422(
    params: dict[str, str],
) -> None:
    resposta = _get_lista(MARIO, **params)

    assert resposta.status_code == 422
    assert FALTA_O_REGISTRO in _corpo(resposta)


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos", "sessao_das_rotas")
def test_fornecedor_recebe_403_na_lista() -> None:
    resposta = _get_lista(FABIO, origem="teste_registro", registro=str(REGISTRO_COMUM))

    assert resposta.status_code == 403
    assert rbac.SUPPLIER_SCOPE_MESSAGE in _corpo(resposta)


@pytest.mark.usefixtures("origens", "hoje_fixo")
def test_dado_pessoal_o_membro_envia_e_ve_o_aviso_o_gestor_ve_a_lista(
    sessao_das_rotas: Session, pasta_de_anexos: Path
) -> None:
    resposta = _post(
        MARIO,
        _registro("teste_dado_pessoal", REGISTRO_PESSOAL),
        ("atestado.pdf", b"dado pessoal"),
    )

    assert resposta.status_code == 200
    (anexo,) = _anexos_gravados(sessao_das_rotas)
    assert (pasta_de_anexos / str(anexo.project_id) / str(anexo.id)).read_bytes() == b"dado pessoal"
    tags = parse_tags(_corpo(resposta))
    assert len(find_all(tags, "form", "upload")) == 1
    assert find_all(tags, "table") == []
    assert find_all(tags, "a", "anexos__link") == []
    (aviso,) = find_all(tags, "div", "aviso--info")
    assert aviso.clean_text() == attachments.RESTRICTED_NOTICE
    assert _texto_do(tags, f"{ALVO}-titulo") == "Anexos"

    do_gestor = _get_lista(GIL, origem="teste_dado_pessoal", registro=str(REGISTRO_PESSOAL))

    tags_do_gestor = parse_tags(_corpo(do_gestor))
    assert len(find_all(tags_do_gestor, "a", "anexos__link")) == 1
    assert find_all(tags_do_gestor, "div", "aviso--info") == []


# ── Routes: download ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_download_entrega_o_arquivo_com_o_nome_original_sem_o_cabecalho_do_alpine(
    sessao_das_rotas: Session,
) -> None:
    conteudo = b"%PDF-1.7 vistoria"
    anexo = _anexo_na_pasta(
        sessao_das_rotas, file_name="Relatório de vistoria.pdf", content=conteudo
    )

    resposta = _get_arquivo(VERA, str(anexo.id))

    assert resposta.status_code == 200
    assert resposta.get_body() == conteudo
    assert resposta.headers["Content-Type"] == "application/pdf"
    assert resposta.headers["Content-Disposition"] == (
        'attachment; filename="Relat_rio de vistoria.pdf"; '
        "filename*=UTF-8''Relat%C3%B3rio%20de%20vistoria.pdf"
    )
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["Cache-Control"] == "private, no-store"


@pytest.mark.usefixtures("hoje_fixo", "pasta_de_anexos")
def test_download_de_quem_nao_le_o_registro_de_origem_e_recusado_em_texto(
    sessao_das_rotas: Session, origens: Origens
) -> None:
    origens.participantes.add(GIL)
    anexo = _anexo_na_pasta(sessao_das_rotas, email=GIL, origin_record_id=REGISTRO_RESERVADO)

    resposta = _get_arquivo(MARIO, str(anexo.id))

    assert resposta.status_code == 403
    assert resposta.headers["Content-Type"].startswith("text/plain")
    assert _corpo(resposta) == RECUSA_DO_REGISTRO
    assert _get_arquivo(GIL, str(anexo.id)).status_code == 200


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_download_de_dado_pessoal_e_403_para_o_membro_e_libera_o_gestor(
    sessao_das_rotas: Session,
) -> None:
    anexo = _anexo_na_pasta(
        sessao_das_rotas,
        origin_table="teste_dado_pessoal",
        origin_record_id=REGISTRO_PESSOAL,
        file_name="atestado.pdf",
        content=b"dado pessoal",
    )

    do_membro = _get_arquivo(MARIO, str(anexo.id))
    do_gestor = _get_arquivo(GIL, str(anexo.id))

    assert do_membro.status_code == 403
    assert "Esta operação exige o perfil Gestor ou Admin." in _corpo(do_membro)
    assert do_gestor.status_code == 200
    assert do_gestor.get_body() == b"dado pessoal"


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_download_do_fornecedor_e_recusado_pelo_vinculo(sessao_das_rotas: Session) -> None:
    anexo = _anexo_na_pasta(sessao_das_rotas)

    resposta = _get_arquivo(FABIO, str(anexo.id))

    assert resposta.status_code == 403
    assert _corpo(resposta) == rbac.SUPPLIER_SCOPE_MESSAGE


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos")
def test_download_sem_identidade_em_producao_pede_o_login(
    sessao_das_rotas: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    anexo = _anexo_na_pasta(sessao_das_rotas)
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)

    resposta = _get_arquivo(None, str(anexo.id))

    assert resposta.status_code == 403
    assert _corpo(resposta) == auth.SIGN_IN_MESSAGE


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos", "sessao_das_rotas")
def test_download_de_anexo_que_nao_existe_e_404_em_texto() -> None:
    resposta = _get_arquivo(MARIO, "999999999")

    assert resposta.status_code == 404
    assert resposta.headers["Content-Type"].startswith("text/plain")
    assert _corpo(resposta) == "Anexo não encontrado."


@pytest.mark.usefixtures("origens", "hoje_fixo")
def test_download_cujo_arquivo_sumiu_do_armazenamento_e_404(
    sessao_das_rotas: Session, pasta_de_anexos: Path
) -> None:
    anexo = _anexo_na_pasta(sessao_das_rotas)
    (pasta_de_anexos / str(anexo.project_id) / str(anexo.id)).unlink()

    resposta = _get_arquivo(MARIO, str(anexo.id))

    assert resposta.status_code == 404
    assert _corpo(resposta) == "Anexo não encontrado."


@pytest.mark.usefixtures("origens", "hoje_fixo", "pasta_de_anexos", "sessao_das_rotas")
@pytest.mark.parametrize("identificador", ["abc", "1.5", "-3", "", "1" * 19, "²"])
def test_download_com_identificador_mal_formado_e_422_em_texto(identificador: str) -> None:
    resposta = _get_arquivo(MARIO, identificador)

    assert resposta.status_code == 422
    assert _corpo(resposta) == "Informe o anexo que deseja baixar."


# ── Routes: the contract ─────────────────────────────────────────────────


def test_as_rotas_de_anexos_estao_registradas_com_os_caminhos_e_os_metodos_da_spec() -> None:
    import function_app

    rotas = {
        funcao.get_function_name(): (
            funcao.get_trigger().route,
            [metodo.value for metodo in funcao.get_trigger().methods],
        )
        for funcao in function_app.app.get_functions()
    }

    assert rotas["list_attachments"] == ("anexos", ["GET"])
    assert rotas["upload_attachment"] == ("anexos/enviar", ["POST"])
    assert rotas["download_attachment"] == ("anexos/{anexo_id}/baixar", ["GET"])


def test_o_download_declara_so_a_identidade_e_a_permissao_vem_do_registro_de_origem() -> None:
    import function_app

    rotas = {funcao.get_function_name(): funcao for funcao in function_app.app.get_functions()}

    declarado = rotas["download_attachment"].get_user_function().__dict__["access"]

    assert declarado == Access()


def test_file_route_nao_exige_o_cabecalho_do_alpine_e_recusa_em_texto(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(sessao_das_rotas, email=VERA, perfil="Visualizador")

    @file_route(access=Access(permission=Permission.WRITE))
    def rota(_req: func.HttpRequest, _session: Session, _contexto: object) -> func.HttpResponse:
        return func.HttpResponse("não deveria chegar aqui")

    resposta = rota(
        func.HttpRequest(
            method="GET",
            url="/api/teste",
            headers={PRINCIPAL_HEADER: cabecalho_do_principal(VERA)},
            params={},
            route_params={},
            body=b"",
        )
    )

    assert resposta.status_code == 403
    assert resposta.headers["Content-Type"].startswith("text/plain")
    assert "O seu perfil é Visualizador." in _corpo(resposta)
