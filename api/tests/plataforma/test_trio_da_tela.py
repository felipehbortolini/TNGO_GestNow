"""Verificação trio-da-tela (ISSUE-010, D3): reprova, nomeando a tela, o trio que falta ou não bate.

O script Node lê a lista de navegação e confere o disco e o shell. Aqui ele roda sobre uma árvore
mínima montada em ``tmp_path`` (três telas, uma delas da pasta ``programacao_semanal``, que aparece
entre as abas do Planejamento): a árvore completa passa, e cada defeito reprova nomeando só a tela
que o tem. Os quatro defeitos da issue (view sem CSS, view sem JS, trio fora do shell e view sem
item de navegação) e os de coerência do trio têm um caso cada. O último teste roda o script sobre
o repositório de verdade.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[3]
SCRIPT = RAIZ_DO_REPOSITORIO / "scripts" / "verificar-trio-da-tela.mjs"

# Início, uma tela do Planejamento e uma da pasta própria da Programação Semanal.
TELAS = ("inicio/home", "planejamento/eap", "programacao_semanal/programacao")

NAVEGACAO = {
    "modulos": [
        {
            "id": "inicio",
            "titulo": "Início",
            "icone": "home",
            "telas": [{"id": "home", "titulo": "Início"}],
        },
        {
            "id": "planejamento",
            "numero": "02",
            "titulo": "Planejamento",
            "icone": "chartLine",
            "telas": [
                {"id": "eap", "titulo": "EAP"},
                {
                    "modulo": "programacao_semanal",
                    "id": "programacao",
                    "titulo": "Programação",
                    "grupo": "Programação Semanal",
                },
            ],
        },
    ]
}


# ── A árvore mínima ──────────────────────────────────────────────────────


def _view(chave: str) -> str:
    modulo, tela = chave.split("/")
    return f"""<main id="app-shell" class="content pagina--{modulo}-{tela}"
  x-data="{{ estado: 'vazio-origem' }}"
  x-init="TN.paginas['{chave}'].iniciar($el)">
</main>
"""


def _script(chave: str) -> str:
    return f'window.TN.paginas["{chave}"] = {{ iniciar: function () {{}} }};\n'


def _shell() -> str:
    vinculos = "\n".join(
        f'    <link rel="stylesheet" href="/paginas/{chave}.css" />\n'
        f'    <script defer src="/paginas/{chave}.js"></script>'
        for chave in TELAS
    )
    return f'<!doctype html>\n<html lang="pt-BR">\n  <head>\n{vinculos}\n  </head>\n</html>\n'


def _montar(raiz: Path) -> None:
    """Escreve a lista de navegação, o shell e o trio completo de cada tela."""
    navegacao = raiz / "api" / "src" / "core" / "navegacao.json"
    navegacao.parent.mkdir(parents=True)
    navegacao.write_text(json.dumps(NAVEGACAO), encoding="utf-8")
    (raiz / "app").mkdir(parents=True, exist_ok=True)
    (raiz / "app" / "index.html").write_text(_shell(), encoding="utf-8")
    for chave in TELAS:
        arquivos = {
            f"_views/{chave}.html": _view(chave),
            f"paginas/{chave}.css": "/* estilo da página */\n",
            f"paginas/{chave}.js": _script(chave),
        }
        for caminho, conteudo in arquivos.items():
            destino = raiz / "app" / caminho
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(conteudo, encoding="utf-8")


def _rodar(*argumentos: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    assert node, "node não está no PATH: a verificação trio-da-tela é um script Node"
    return subprocess.run(  # noqa: S603 - comando fixo: o node do PATH roda um script deste repositório
        [node, str(SCRIPT), *argumentos],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _verificar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return _rodar("--raiz", str(raiz))


def _saida(resultado: subprocess.CompletedProcess[str]) -> str:
    return resultado.stdout + resultado.stderr


# ── Os defeitos ──────────────────────────────────────────────────────────


def _apagar(raiz: Path, caminho: str) -> None:
    (raiz / caminho).unlink()


def _tirar_linhas(raiz: Path, caminho: str, trecho: str) -> None:
    arquivo = raiz / caminho
    linhas = arquivo.read_text(encoding="utf-8").splitlines(keepends=True)
    arquivo.write_text("".join(linha for linha in linhas if trecho not in linha), encoding="utf-8")


def _trocar(raiz: Path, caminho: str, antigo: str, novo: str) -> None:
    arquivo = raiz / caminho
    texto = arquivo.read_text(encoding="utf-8")
    assert antigo in texto
    arquivo.write_text(texto.replace(antigo, novo), encoding="utf-8")


def _tirar_da_navegacao(raiz: Path, tela: str) -> None:
    arquivo = raiz / "api" / "src" / "core" / "navegacao.json"
    lista = json.loads(arquivo.read_text(encoding="utf-8"))
    for modulo in lista["modulos"]:
        modulo["telas"] = [item for item in modulo["telas"] if item["id"] != tela]
    arquivo.write_text(json.dumps(lista), encoding="utf-8")


DEFEITOS = [
    pytest.param(
        partial(_apagar, caminho="app/paginas/planejamento/eap.css"),
        "planejamento/eap",
        "view sem CSS",
        id="view-sem-css",
    ),
    pytest.param(
        partial(_apagar, caminho="app/paginas/programacao_semanal/programacao.js"),
        "programacao_semanal/programacao",
        "view sem JS",
        id="view-sem-js",
    ),
    pytest.param(
        partial(_tirar_linhas, caminho="app/index.html", trecho="/paginas/planejamento/eap.css"),
        "planejamento/eap",
        "trio fora do shell",
        id="css-fora-do-shell",
    ),
    pytest.param(
        partial(_tirar_linhas, caminho="app/index.html", trecho="/paginas/inicio/home.js"),
        "inicio/home",
        "trio fora do shell",
        id="js-fora-do-shell",
    ),
    pytest.param(
        partial(_tirar_da_navegacao, tela="eap"),
        "planejamento/eap",
        "view sem item de navegação",
        id="view-sem-item-de-navegacao",
    ),
    pytest.param(
        partial(_apagar, caminho="app/_views/inicio/home.html"),
        "inicio/home",
        "item de navegação sem view",
        id="item-de-navegacao-sem-view",
    ),
    pytest.param(
        partial(
            _trocar,
            caminho="app/_views/planejamento/eap.html",
            antigo="pagina--planejamento-eap",
            novo="pagina--outra-tela",
        ),
        "planejamento/eap",
        "a raiz da view não tem a classe pagina--planejamento-eap",
        id="classe-raiz-errada",
    ),
    pytest.param(
        partial(
            _trocar,
            caminho="app/_views/inicio/home.html",
            antigo=".iniciar($el)",
            novo=".nada($el)",
        ),
        "inicio/home",
        "a view não aciona",
        id="view-nao-aciona-o-js",
    ),
    pytest.param(
        partial(
            _trocar,
            caminho="app/paginas/planejamento/eap.js",
            antigo='paginas["planejamento/eap"]',
            novo='paginas["outra/tela"]',
        ),
        "planejamento/eap",
        "o JS não registra",
        id="js-nao-registra-a-pagina",
    ),
    pytest.param(
        partial(
            _trocar,
            caminho="app/_views/planejamento/eap.html",
            antigo="</main>",
            novo="<script>alert(1)</script></main>",
        ),
        "planejamento/eap",
        "view com <script>",
        id="view-com-script",
    ),
]


def test_arvore_completa_passa(tmp_path: Path) -> None:
    _montar(tmp_path)

    resultado = _verificar(tmp_path)

    assert resultado.returncode == 0, _saida(resultado)


@pytest.mark.parametrize(("defeito", "tela", "mensagem"), DEFEITOS)
def test_defeito_reprova_nomeando_so_a_tela_que_o_tem(
    tmp_path: Path, defeito: Callable[[Path], None], tela: str, mensagem: str
) -> None:
    _montar(tmp_path)
    defeito(tmp_path)

    resultado = _verificar(tmp_path)

    saida = _saida(resultado)
    assert resultado.returncode == 1, saida
    assert tela in saida
    assert mensagem in saida
    assert [outra for outra in TELAS if outra != tela and outra in saida] == []


def test_lista_de_navegacao_ilegivel_reprova(tmp_path: Path) -> None:
    _montar(tmp_path)
    _apagar(tmp_path, "api/src/core/navegacao.json")

    resultado = _verificar(tmp_path)

    assert resultado.returncode == 1, _saida(resultado)
    assert "lista de navegação ilegível" in _saida(resultado)


def test_repositorio_tem_o_trio_de_todas_as_telas() -> None:
    resultado = _rodar()

    assert resultado.returncode == 0, _saida(resultado)
