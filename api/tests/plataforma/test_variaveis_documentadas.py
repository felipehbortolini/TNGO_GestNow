"""A tabela de variáveis do guia de publicação confere com o código (ISSUE-092, D16).

O guia ``docs/PUBLICACAO-AZURE.md`` é o passo a passo do dono para publicar no
Azure; ele tem de documentar **todas** as variáveis ``GESTNOW_*`` que o código
lê — nem uma a menos (o dono não saberia o que preencher) nem uma a mais (nome
que o código não lê só confundiria a conferência). Sem banco: o teste lê
somente arquivos do repositório.

A varredura (escopo: código do app e scripts, fora os testes) lê:

* cada ``.py`` de ``api/src``, ``api/migrations``, ``scripts`` e o
  ``api/function_app.py`` com o ``ast``: vale todo literal de string que seja
  exatamente um nome ``GESTNOW_*``. O produto nomeia as variáveis por
  constantes e mapas (``config.py``, ``database.py``, ``blob_storage.py``,
  ``graph_mail.py``, ``prepare_database.py``), e os textos de mensagem que
  citam o nome no meio da frase não contam;
* os demais arquivos de ``scripts`` e ``app`` (``.mjs``, ``.js``, ``.ps1``,
  ``.bat``) e o ``run.bat`` por expressão regular: neles o nome aparece como
  ``process.env.GESTNOW_...`` ou ``if not defined GESTNOW_...``.

A tabela do guia é lida pelas linhas de Markdown cuja primeira célula é um
nome ``GESTNOW_*`` entre crases — a mesma forma que o guia usa. O defeito
reprova nomeando a variável.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[3]
GUIA = RAIZ_DO_REPOSITORIO / "docs" / "PUBLICACAO-AZURE.md"

PASTAS_DE_PYTHON = ("api/src", "api/migrations", "scripts")
ARQUIVO_DE_PYTHON_EXTRA = Path("api/function_app.py")
PASTAS_DE_TEXTO = ("scripts", "app")
ARQUIVO_DE_TEXTO_EXTRA = Path("run.bat")
SUFIXOS_DE_TEXTO = (".mjs", ".js", ".ps1", ".bat", ".cmd")

NOME_DA_VARIAVEL = re.compile(r"GESTNOW_[A-Z0-9_]+")

# O núcleo que a sanidade exige: se a varredura devolvesse vazio (parser
# quebrado), a comparação passaria sem conferir nada.
VARIAVEIS_ESSENCIAIS = {
    "GESTNOW_MODO",
    "GESTNOW_DATABASE_URL",
    "GESTNOW_ADMIN_EMAIL",
    "GESTNOW_ENVIO_EMAIL",
    "GESTNOW_ARMAZENAMENTO_ANEXOS",
}

COLUNAS_DA_TABELA = 4
INDICE_LOCAL = 1
INDICE_AZURE = 2
INDICE_DESCRICAO = 3


def _nomes_do_python(caminho: Path) -> set[str]:
    """Os literais de string do módulo que são exatamente um nome de variável."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    return {
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant)
        and isinstance(no.value, str)
        and NOME_DA_VARIAVEL.fullmatch(no.value)
    }


def _arquivos(pasta: str, sufixos: tuple[str, ...]) -> list[Path]:
    raiz = RAIZ_DO_REPOSITORIO / pasta
    return sorted(
        caminho for caminho in raiz.rglob("*") if caminho.is_file() and caminho.suffix in sufixos
    )


def _variaveis_do_codigo() -> set[str]:
    """Todas as ``GESTNOW_*`` que o código do app e os scripts leem."""
    encontradas: set[str] = set()
    for pasta in PASTAS_DE_PYTHON:
        for caminho in _arquivos(pasta, (".py",)):
            encontradas |= _nomes_do_python(caminho)
    encontradas |= _nomes_do_python(RAIZ_DO_REPOSITORIO / ARQUIVO_DE_PYTHON_EXTRA)
    for pasta in PASTAS_DE_TEXTO:
        for caminho in _arquivos(pasta, SUFIXOS_DE_TEXTO):
            encontradas |= set(
                NOME_DA_VARIAVEL.findall(caminho.read_text(encoding="utf-8", errors="replace"))
            )
    encontradas |= set(
        NOME_DA_VARIAVEL.findall(
            (RAIZ_DO_REPOSITORIO / ARQUIVO_DE_TEXTO_EXTRA).read_text(
                encoding="utf-8", errors="replace"
            )
        )
    )
    return encontradas


def _linhas_da_tabela_do_guia() -> dict[str, list[str]]:
    """As células das linhas do guia cuja primeira coluna é uma variável, por nome."""
    linhas: dict[str, list[str]] = {}
    for linha in GUIA.read_text(encoding="utf-8").splitlines():
        texto = linha.strip()
        if not texto.startswith("|"):
            continue
        celulas = [celula.strip() for celula in texto.strip("|").split("|")]
        primeira = celulas[0]
        if primeira.startswith("`") and primeira.endswith("`"):
            nome = primeira.strip("`")
            if NOME_DA_VARIAVEL.fullmatch(nome):
                linhas[nome] = celulas
    return linhas


def test_o_guia_e_a_tabela_existem() -> None:
    assert GUIA.is_file(), "o guia docs/PUBLICACAO-AZURE.md não existe"
    assert len(_linhas_da_tabela_do_guia()) >= len(VARIAVEIS_ESSENCIAIS), (
        "a tabela de variáveis do guia está vazia ou fora do formato"
    )


def test_a_varredura_encontra_o_nucleo_de_variaveis() -> None:
    assert _variaveis_do_codigo() >= VARIAVEIS_ESSENCIAIS


def test_o_guia_documenta_toda_variavel_que_o_codigo_le() -> None:
    faltando = _variaveis_do_codigo() - set(_linhas_da_tabela_do_guia())

    assert not faltando, f"o guia não documenta: {', '.join(sorted(faltando))}"


def test_o_guia_nao_lista_variavel_que_o_codigo_nao_le() -> None:
    sobrando = set(_linhas_da_tabela_do_guia()) - _variaveis_do_codigo()

    assert not sobrando, f"o guia lista variável que o código não lê: {', '.join(sorted(sobrando))}"


def test_a_linha_do_guia_tem_o_valor_local_o_do_azure_e_o_que_faz() -> None:
    problemas: list[str] = []
    for nome, celulas in _linhas_da_tabela_do_guia().items():
        if len(celulas) != COLUNAS_DA_TABELA:
            problemas.append(f"{nome}: a linha não tem as quatro colunas")
            continue
        for indice, rotulo in (
            (INDICE_LOCAL, "o valor local"),
            (INDICE_AZURE, "o valor no Azure"),
            (INDICE_DESCRICAO, "o que faz"),
        ):
            if not celulas[indice]:
                problemas.append(f"{nome}: a linha não diz {rotulo}")

    assert not problemas, "; ".join(problemas)
