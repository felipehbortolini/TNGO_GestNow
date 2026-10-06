"""Importadores de teste e planilhas montadas à mão: o que um módulo registraria na importação.

Dois importadores servem aos testes do fluxo (ISSUE-018):

* ``importador_de_clientes`` grava de verdade, pela fachada (``core.recording``), na tabela
  ``cliente`` da plataforma: o que prova que a conferência não grava, que a confirmação grava
  com a trilha e que a gravação é tudo ou nada;
* ``importador_de_tipos`` tem uma coluna de cada tipo (texto, lista, inteiro, decimal, percentual,
  dinheiro e data) e só anota o que recebeu: o que prova a conversão de cada célula.

As planilhas são montadas com o openpyxl, como o Excel as entregaria; ``corpo_multipart`` monta o
envio do formulário como o navegador o faz.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import recording
from src.core.errors import InvalidDataError
from src.core.export_document import ValueKind
from src.core.importing import ImportColumn, ImportContext, Importer, RowCheck
from src.core.models import Client
from src.core.rbac import Permission

CHAVE_DE_CLIENTES = "clientes-de-teste"
CHAVE_DE_TIPOS = "tipos-de-teste"
MODULO_DE_TESTE = "planejamento"

PREFIXO = "Teste Importação"
NOME_RECUSADO = f"{PREFIXO} Recusado"
CABECALHO_DE_CLIENTES = ("Nome", "Sigla", "Ativo")
CABECALHO_DE_TIPOS = (
    "Código",
    "Quantidade",
    "Peso",
    "Avanço",
    "Valor",
    "Início",
    "Situação",
)

SITUACOES = ("Aberta", "Fechada")
MENSAGEM_DE_RECUSA = "O cliente recusado não pode ser importado."


# ── O importador que grava ───────────────────────────────────────────────


def _validar_cliente(
    session: Session, *, values: Mapping[str, Any], **_contexto: object
) -> RowCheck:
    """Erro se o nome já existe; aviso se a sigla está em branco (a linha entra assim mesmo)."""
    existente = session.scalar(
        select(func.count())
        .select_from(Client)
        .where(func.lower(Client.name) == values["name"].lower())
    )
    erros = ("Nome: já existe um cliente com este nome",) if existente else ()
    avisos = () if values["acronym"] else ("Sigla em branco: o cliente entra sem sigla",)
    return RowCheck(errors=erros, warnings=avisos)


def _gravar_cliente(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    """Grava pela fachada; o nome ``NOME_RECUSADO`` passa na conferência e a gravação o recusa."""
    if values["name"] == NOME_RECUSADO:
        raise InvalidDataError(MENSAGEM_DE_RECUSA)
    recording.create(
        session,
        user_id=context.user.id,
        record=Client(
            name=values["name"], acronym=values["acronym"], active=values["active"] != "Não"
        ),
    )


def importador_de_clientes() -> Importer:
    """O importador de clientes de teste: nome obrigatório e único na planilha, sigla e ativo."""
    return Importer(
        key=CHAVE_DE_CLIENTES,
        title="Clientes de teste",
        module=MODULO_DE_TESTE,
        columns=(
            ImportColumn("name", "Nome", required=True, example=f"{PREFIXO} Alfa"),
            ImportColumn("acronym", "Sigla", example="ALF"),
            ImportColumn("active", "Ativo", options=("Sim", "Não"), example="Sim"),
        ),
        validate=_validar_cliente,
        save=_gravar_cliente,
        unique=("name",),
    )


def clientes_gravados(session: Session) -> list[str]:
    """Os nomes dos clientes que os testes de importação gravaram, em ordem."""
    consulta = select(Client.name).where(Client.name.like(f"{PREFIXO}%")).order_by(Client.id)
    return list(session.scalars(consulta))


# ── O importador de todos os tipos ───────────────────────────────────────


def importador_de_tipos(
    destino: list[Mapping[str, Any]], *, permissao: Permission = Permission.WRITE
) -> Importer:
    """Uma coluna de cada tipo; as linhas gravadas vão para ``destino``, sem tocar o banco.

    Quantidade negativa é erro e avanço acima de 100 é aviso; o código não se repete na planilha.
    """

    def validar(_session: Session, *, values: Mapping[str, Any], **_contexto: object) -> RowCheck:
        erros = ("Quantidade: não pode ser negativa",) if (values["quantity"] or 0) < 0 else ()
        acima = values["progress"] is not None and values["progress"] > 100
        avisos = ("Avanço acima de 100%",) if acima else ()
        return RowCheck(errors=erros, warnings=avisos)

    def gravar(_session: Session, *, values: Mapping[str, Any], **_contexto: object) -> None:
        destino.append(dict(values))

    return Importer(
        key=CHAVE_DE_TIPOS,
        title="Tipos de teste",
        module=MODULO_DE_TESTE,
        columns=(
            ImportColumn("code", "Código", required=True, example="A-1"),
            ImportColumn("quantity", "Quantidade", ValueKind.INTEGER, example="12"),
            ImportColumn("weight", "Peso", ValueKind.DECIMAL, example="12,5"),
            ImportColumn("progress", "Avanço", ValueKind.PERCENT, digits=1, example="45,3"),
            ImportColumn("value", "Valor", ValueKind.MONEY, example="1234,56"),
            ImportColumn("start", "Início", ValueKind.DATE, example="05/10/2026"),
            ImportColumn("status", "Situação", options=SITUACOES, example="Aberta"),
        ),
        validate=validar,
        save=gravar,
        permission=permissao,
        unique=("code",),
    )


# ── Planilhas ────────────────────────────────────────────────────────────


def planilha(
    linhas: Iterable[Sequence[Any]],
    *,
    cabecalho: Sequence[str] = CABECALHO_DE_CLIENTES,
    acima: int = 0,
    formatos: Mapping[str, str] | None = None,
    aba: str = "Dados",
) -> bytes:
    """O ``.xlsx`` com o cabeçalho na linha ``acima + 1`` e as linhas logo abaixo.

    ``acima`` são linhas de identificação antes do cabeçalho (o modelo baixado traz o logo, o
    título, o escopo e a data). ``formatos`` dá o formato de número de uma coluna pelo cabeçalho.
    """
    livro = Workbook()
    folha = livro.active
    folha.title = aba
    for numero in range(acima):
        folha.append([f"Identificação {numero + 1}"])
    folha.append(list(cabecalho))
    for linha in linhas:
        folha.append(list(linha))
    for coluna, titulo in enumerate(cabecalho, start=1):
        formato = (formatos or {}).get(titulo)
        if formato is not None:
            for celula in folha.iter_cols(min_col=coluna, max_col=coluna, min_row=acima + 2):
                for item in celula:
                    item.number_format = formato
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


def linhas_de_clientes(*nomes: str) -> bytes:
    """A planilha de clientes com um nome por linha, sem sigla."""
    return planilha([(nome, None, None) for nome in nomes])


# ── O envio do formulário ────────────────────────────────────────────────

FRONTEIRA = "fronteira-do-teste-de-importacao"


def corpo_multipart(
    campos: Mapping[str, str], arquivo: tuple[str, bytes] | None
) -> tuple[bytes, str]:
    """O corpo ``multipart/form-data`` como o navegador o envia, e o seu Content-Type.

    A parte do arquivo declara ``text/html`` de propósito: o servidor nunca confia nesse tipo.
    """
    partes = [
        f'--{FRONTEIRA}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n'.encode()
        for nome, valor in campos.items()
    ]
    if arquivo is not None:
        nome_do_arquivo, conteudo = arquivo
        cabecalho = (
            f"--{FRONTEIRA}\r\n"
            f'Content-Disposition: form-data; name="arquivo"; filename="{nome_do_arquivo}"\r\n'
            "Content-Type: text/html\r\n\r\n"
        )
        partes.append(cabecalho.encode() + conteudo + b"\r\n")
    partes.append(f"--{FRONTEIRA}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={FRONTEIRA}"
