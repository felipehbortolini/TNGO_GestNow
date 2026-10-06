"""Servidor de desenvolvimento local — alternativa ao SWA CLI.

O caminho oficial é `swa start --config swa-cli.config.json`, que precisa do
Azure Functions Core Tools. Quando o `func` não estiver disponível, este script
sobe um equivalente:

  * serve app/ como estático
  * responde /.auth/me com um usuário simulado
  * roteia /api/* para os handlers reais dos blueprints
  * aplica o navigationFallback para /index.html

**As rotas não são listadas aqui.** Elas são lidas do próprio
`function_app.py`, que é onde os blueprints já se registram. Manter uma
segunda lista à mão era a fonte garantida do bug "funciona no Azure e dá
404 no local" — e ele só aparecia depois, na tela.

Não substitui o SWA CLI para validar deploy: usa o servidor HTTP da
biblioteca padrão, não o host do Functions. Serve para desenvolver e
revisar tela.

    python scripts/dev_local.py [porta]
"""

from __future__ import annotations

import json
import mimetypes
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app"
sys.path.insert(0, str(RAIZ / "api"))

import azure.functions as func  # noqa: E402

import function_app  # noqa: E402

# Usuário simulado — espelha o formato do clientPrincipal do Azure SWA.
# A aplicação não o usa no modo demonstração (ela entra pelo cadastro de
# colaboradores), mas /.auth/me precisa responder algo para o shell.
USUARIO = {
    "clientPrincipal": {
        "identityProvider": "aad",
        "userId": "00000000-0000-0000-0000-000000000000",
        "userDetails": "demonstracao@timenow.com.br",
        "userRoles": ["anonymous", "authenticated"],
        "claims": [{"typ": "name", "val": "Modo demonstração"}],
    }
}

_SEGMENTO = re.compile(r"\{(?P<nome>[A-Za-z_][A-Za-z0-9_]*)(?::(?P<tipo>[a-z]+))?\}")
_TIPOS = {"int": r"\d+"}


def _para_regex(rota: str) -> re.Pattern:
    """Traduz `atividade/{chave}` para a expressão que o servidor casa."""

    def trocar(achado: re.Match) -> str:
        padrao = _TIPOS.get(achado.group("tipo") or "", r"[^/]+")
        return f"(?P<{achado.group('nome')}>{padrao})"

    corpo = _SEGMENTO.sub(trocar, re.escape(rota).replace(r"\{", "{").replace(r"\}", "}"))
    return re.compile(rf"^/api/{corpo}$")


def _tabela_de_rotas() -> list[tuple[set[str], re.Pattern, object]]:
    """Lê as rotas registradas no FunctionApp.

    Usa `_function_builders`, que é interno da biblioteca. É uma escolha
    consciente: a alternativa é duplicar à mão a lista de rotas de dez
    blueprints, e a duplicata desatualizada custa mais do que a chance de
    o atributo mudar de nome numa atualização — que falha aqui, alto e na
    hora, e não em produção.
    """
    tabela = []
    for construtor in function_app.app._function_builders:  # noqa: SLF001
        funcao = construtor._function  # noqa: SLF001
        gatilho = funcao.get_trigger().get_dict_repr()
        if gatilho.get("type") != "httpTrigger":
            continue
        metodos = {str(getattr(m, "value", m)).upper() for m in gatilho.get("methods") or ["GET"]}
        tabela.append((metodos, _para_regex(gatilho["route"]), funcao.get_user_function()))
    return tabela


ROTAS = _tabela_de_rotas()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        sys.stderr.write("  %s\n" % (formato % args))

    # ---------------------------------------------------------------- helpers

    def _responder(self, status, corpo=b"", tipo="text/html; charset=utf-8", extra=None):
        if isinstance(corpo, str):
            corpo = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-cache")
        for chave, valor in (extra or {}).items():
            self.send_header(chave, valor)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def _corpo(self) -> bytes:
        tamanho = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(tamanho) if tamanho else b""

    # ------------------------------------------------------------------ rotas

    def _api(self, metodo, caminho, consulta):
        for metodos, padrao, handler in ROTAS:
            if metodo not in metodos:
                continue
            achou = padrao.match(caminho)
            if not achou:
                continue

            requisicao = func.HttpRequest(
                method=metodo,
                url=caminho,
                headers=dict(self.headers.items()),
                params={k: v[0] for k, v in consulta.items()},
                route_params={k: unquote(v) for k, v in achou.groupdict().items()},
                body=self._corpo(),
            )
            try:
                resposta = handler(requisicao)
            except Exception as erro:  # noqa: BLE001 — o servidor local não pode cair
                traceback.print_exc()
                self._responder(
                    500,
                    f"<pre style='padding:24px;color:#D03636'>{type(erro).__name__}: {erro}</pre>",
                )
                return True

            extra = {
                chave: valor
                for chave, valor in resposta.headers.items()
                if chave.lower() != "content-type"
            }
            self._responder(
                resposta.status_code,
                resposta.get_body(),
                resposta.headers.get("Content-Type", "text/html; charset=utf-8"),
                extra,
            )
            return True
        return False

    def _estatico(self, caminho):
        alvo = (APP / (caminho.lstrip("/") or "index.html")).resolve()
        if not str(alvo).startswith(str(APP.resolve())) or not alvo.is_file():
            return False
        tipo, _ = mimetypes.guess_type(str(alvo))
        self._responder(200, alvo.read_bytes(), tipo or "application/octet-stream")
        return True

    # ----------------------------------------------------------------- verbos

    def _servir(self, metodo):
        partes = urlparse(self.path)
        caminho, consulta = partes.path, parse_qs(partes.query)

        if caminho == "/.auth/me":
            self._responder(200, json.dumps(USUARIO), "application/json")
            return
        if caminho.startswith("/.auth/"):
            self._responder(302, b"", extra={"Location": "/"})
            return

        if caminho.startswith("/api/"):
            if not self._api(metodo, caminho, consulta):
                self._responder(404, "<pre>rota de API não encontrada</pre>")
            return

        if metodo in ("GET", "HEAD") and self._estatico(caminho):
            return

        if metodo in ("GET", "HEAD"):
            self._responder(200, (APP / "index.html").read_bytes())
            return

        self._responder(405, "<pre>método não permitido</pre>")

    def do_GET(self):  # noqa: N802 — assinatura da biblioteca padrão
        self._servir("GET")

    def do_HEAD(self):  # noqa: N802
        self._servir("HEAD")

    def do_POST(self):  # noqa: N802
        self._servir("POST")

    def do_DELETE(self):  # noqa: N802
        self._servir("DELETE")


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 4280
    endereco = "0.0.0.0" if "--rede" in sys.argv else "127.0.0.1"  # noqa: S104
    print(f"Programação Semanal em http://localhost:{porta}")
    print(f"  estáticos: {APP}")
    print(f"  rotas de API: {len(ROTAS)}")
    if endereco == "0.0.0.0":  # noqa: S104
        print("  ouvindo em toda a rede (--rede)")
    print("  equivalente local do SWA CLI — ver docstring\n")
    ThreadingHTTPServer((endereco, porta), Handler).serve_forever()
