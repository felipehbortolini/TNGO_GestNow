"""Local development server that runs without Azure Functions Core Tools."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import traceback
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DIR = ROOT_DIR / "app"
sys.path.insert(0, str(ROOT_DIR / "api"))

import azure.functions as func  # noqa: E402

from src.core.config import load_local_settings  # noqa: E402

load_local_settings()

from src.blueprints import acesso, attachments, exports, health, importing, nav  # noqa: E402
from src.modulos.central_acoes import routes as central_acoes  # noqa: E402
from src.modulos.planejamento import routes as planejamento_routes  # noqa: E402

# Only tells the shell that someone is signed in. In demonstration the API does
# not take the identity from here: it comes from the profile selector in the
# sidebar (cookie ``gestnow_demo_perfil``), and with a real principal header
# (SWA CLI emulator, Azure) the header wins.
DEMO_USER = {
    "clientPrincipal": {
        "identityProvider": "aad",
        "userId": "00000000-0000-0000-0000-000000000000",
        "userDetails": "gestnow.demo@example.invalid",
        "userRoles": ["anonymous", "authenticated"],
        "claims": [{"typ": "name", "val": "Demonstração GestNow"}],
    }
}

# The e-mail of a Microsoft account to simulate: with it the server adds the
# principal header that Static Web Apps would, so the real login path can be
# seen locally (an e-mail in the register of Colaboradores enters, any other one
# sees the screen of denied access) and the profile selector disappears, as in
# Azure. Unset, the demonstration selector decides who is signed in.
DEV_PRINCIPAL_VARIABLE = "GESTNOW_DEV_PRINCIPAL"
PRINCIPAL_HEADER = "x-ms-client-principal"


def dev_principal_header() -> str | None:
    """The principal header for the simulated account, or ``None`` when none is set."""
    email = (os.environ.get(DEV_PRINCIPAL_VARIABLE) or "").strip()
    if not email:
        return None
    principal = {
        "identityProvider": "aad",
        "userId": "00000000000000000000000000000000",
        "userDetails": email,
        "userRoles": ["anonymous", "authenticated"],
    }
    return base64.b64encode(json.dumps(principal).encode()).decode()


ROUTES: list[tuple[str, re.Pattern[str], Callable[[func.HttpRequest], func.HttpResponse]]] = [
    ("GET", re.compile(r"^/api/health$"), health.health),
    ("GET", re.compile(r"^/api/nav$"), nav.main_nav),
    ("GET", re.compile(r"^/api/escopo/projetos$"), nav.choose_project),
    ("GET", re.compile(r"^/api/glossario$"), nav.glossary),
    ("GET", re.compile(r"^/api/acesso-negado$"), acesso.denied_screen),
    ("POST", re.compile(r"^/api/demonstracao/perfil$"), acesso.switch_demo_profile),
    ("GET", re.compile(r"^/api/exportacao/exemplo/excel$"), exports.example_excel),
    ("GET", re.compile(r"^/api/exportacao/exemplo/imprimivel$"), exports.example_printable),
    ("GET", re.compile(r"^/api/anexos$"), attachments.list_attachments),
    ("POST", re.compile(r"^/api/anexos/enviar$"), attachments.upload_attachment),
    (
        "GET",
        re.compile(r"^/api/anexos/(?P<anexo_id>[^/]+)/baixar$"),
        attachments.download_attachment,
    ),
    ("GET", re.compile(r"^/api/importacao/(?P<chave>[^/]+)$"), importing.import_steps),
    ("GET", re.compile(r"^/api/importacao/(?P<chave>[^/]+)/modelo$"), importing.import_template),
    ("POST", re.compile(r"^/api/importacao/(?P<chave>[^/]+)/conferir$"), importing.import_check),
    ("POST", re.compile(r"^/api/importacao/(?P<chave>[^/]+)/confirmar$"), importing.import_confirm),
    # Planejamento > Relato do período (ISSUE-044).
    ("GET", re.compile(r"^/api/planejamento/relatos$"), planejamento_routes.report_panel),
    ("GET", re.compile(r"^/api/planejamento/relatos/ver$"), planejamento_routes.report_view),
    ("GET", re.compile(r"^/api/planejamento/relatos/abrir$"), planejamento_routes.report_open),
    ("GET", re.compile(r"^/api/planejamento/relatos/formulario$"), planejamento_routes.report_form),
    (
        "POST",
        re.compile(r"^/api/planejamento/relatos/formulario$"),
        planejamento_routes.report_form_reload,
    ),
    ("POST", re.compile(r"^/api/planejamento/relatos/copiar$"), planejamento_routes.report_copy),
    ("POST", re.compile(r"^/api/planejamento/relatos/gravar$"), planejamento_routes.report_save),
    ("POST", re.compile(r"^/api/planejamento/relatos/excluir$"), planejamento_routes.report_delete),
    ("GET", re.compile(r"^/api/planejamento/relatos/excel$"), planejamento_routes.report_excel),
    (
        "GET",
        re.compile(r"^/api/planejamento/relatos/imprimivel$"),
        planejamento_routes.report_printable,
    ),
    ("GET", re.compile(r"^/api/central-acoes/acoes$"), central_acoes.list_actions_screen),
    ("GET", re.compile(r"^/api/central-acoes/acoes/excel$"), central_acoes.actions_excel),
    ("GET", re.compile(r"^/api/central-acoes/acoes/imprimivel$"), central_acoes.actions_printable),
    (
        "GET",
        re.compile(r"^/api/central-acoes/acoes/(?P<acao_id>[^/]+)/replanejar$"),
        central_acoes.replan_form,
    ),
    (
        "POST",
        re.compile(r"^/api/central-acoes/acoes/(?P<acao_id>[^/]+)/replanejar$"),
        central_acoes.replan_save,
    ),
    (
        "GET",
        re.compile(r"^/api/central-acoes/acoes/(?P<acao_id>[^/]+)/concluir$"),
        central_acoes.complete_form,
    ),
    (
        "POST",
        re.compile(r"^/api/central-acoes/acoes/(?P<acao_id>[^/]+)/concluir$"),
        central_acoes.complete_save,
    ),
    (
        "GET",
        re.compile(r"^/api/central-acoes/acoes/(?P<acao_id>[^/]+)/historico$"),
        central_acoes.replan_history_view,
    ),
    ("GET", re.compile(r"^/api/planejamento/6wla$"), planejamento_routes.lookahead_screen),
    ("GET", re.compile(r"^/api/planejamento/6wla/excel$"), planejamento_routes.lookahead_excel),
    (
        "GET",
        re.compile(r"^/api/planejamento/6wla/imprimivel$"),
        planejamento_routes.lookahead_printable,
    ),
    (
        "GET",
        re.compile(r"^/api/planejamento/6wla/atividades/nova$"),
        planejamento_routes.lookahead_new_activity_form,
    ),
    (
        "POST",
        re.compile(r"^/api/planejamento/6wla/atividades$"),
        planejamento_routes.lookahead_create_activity,
    ),
    (
        "GET",
        re.compile(r"^/api/planejamento/6wla/atividades/(?P<atividade_id>[^/]+)/editar$"),
        planejamento_routes.lookahead_edit_activity_form,
    ),
    (
        "POST",
        re.compile(r"^/api/planejamento/6wla/atividades/(?P<atividade_id>[^/]+)$"),
        planejamento_routes.lookahead_update_activity,
    ),
    (
        "GET",
        re.compile(r"^/api/planejamento/6wla/restricoes/nova$"),
        planejamento_routes.lookahead_new_constraint_form,
    ),
    (
        "POST",
        re.compile(r"^/api/planejamento/6wla/restricoes$"),
        planejamento_routes.lookahead_create_constraint,
    ),
    (
        "GET",
        re.compile(r"^/api/planejamento/6wla/restricoes/(?P<restricao_id>[^/]+)/editar$"),
        planejamento_routes.lookahead_edit_constraint_form,
    ),
    (
        "GET",
        re.compile(r"^/api/planejamento/6wla/restricoes/(?P<restricao_id>[^/]+)/remover$"),
        planejamento_routes.lookahead_removal_form,
    ),
    (
        "POST",
        re.compile(r"^/api/planejamento/6wla/restricoes/(?P<restricao_id>[^/]+)/remocao$"),
        planejamento_routes.lookahead_remove_constraint,
    ),
    (
        "POST",
        re.compile(r"^/api/planejamento/6wla/restricoes/(?P<restricao_id>[^/]+)$"),
        planejamento_routes.lookahead_update_constraint,
    ),
]


class LocalHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format_string: str, *args: object) -> None:
        sys.stderr.write(f"  {format_string % args}\n")

    def _send_response(
        self,
        status_code: int,
        body: bytes | str = b"",
        content_type: str = "text/html; charset=utf-8",
        headers: dict[str, str] | None = None,
    ) -> None:
        if isinstance(body, str):
            body = body.encode("utf-8")
        if content_type.startswith("text/") and "charset=" not in content_type.lower():
            content_type += "; charset=utf-8"
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_request_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _api_headers(self) -> dict[str, str]:
        """The request headers, with the principal of the simulated account when there is one.

        Static Web Apps overwrites whatever the client sent as the principal, so
        the simulated one replaces it; without a simulated account nothing changes.
        """
        headers = dict(self.headers.items())
        principal = dev_principal_header()
        if principal is None:
            return headers
        kept = {name: value for name, value in headers.items() if name.lower() != PRINCIPAL_HEADER}
        return {**kept, PRINCIPAL_HEADER: principal}

    def _dispatch_api(self, method: str, path: str, query: dict[str, list[str]]) -> bool:
        for route_method, route_pattern, handler in ROUTES:
            if route_method != method:
                continue
            match = route_pattern.match(path)
            if not match:
                continue

            request = func.HttpRequest(
                method=method,
                url=path,
                headers=self._api_headers(),
                params={name: values[0] for name, values in query.items()},
                route_params=match.groupdict(),
                body=self._read_request_body(),
            )
            try:
                response = handler(request)
            except Exception as error:  # pragma: no cover
                traceback.print_exc()
                self._send_response(500, f"<pre>{type(error).__name__}: {error}</pre>")
                return True

            response_headers = {
                name: value
                for name, value in response.headers.items()
                if name.lower() != "content-type"
            }
            self._send_response(
                response.status_code,
                response.get_body(),
                response.headers.get("Content-Type", "text/html; charset=utf-8"),
                response_headers,
            )
            return True
        return False

    def _serve_static(self, path: str) -> bool:
        if path == "/":
            path = "/index.html"
        app_root = APP_DIR.resolve()
        target = (APP_DIR / path.lstrip("/")).resolve()
        if not target.is_relative_to(app_root) or not target.is_file():
            return False
        content_type, _ = mimetypes.guess_type(str(target))
        self._send_response(
            200,
            target.read_bytes(),
            content_type or "application/octet-stream",
        )
        return True

    def _serve(self, method: str) -> None:
        request_url = urlparse(self.path)
        path, query = request_url.path, parse_qs(request_url.query)

        if path == "/.auth/me":
            self._send_response(200, json.dumps(DEMO_USER), "application/json")
            return
        if path.startswith(("/.auth/login", "/.auth/logout")):
            self._send_response(302, b"", headers={"Location": "/"})
            return

        if path.startswith("/api/"):
            if not self._dispatch_api(method, path, query):
                self._send_response(404, "<pre>Rota da API não encontrada</pre>")
            return

        if method in ("GET", "HEAD") and self._serve_static(path):
            return
        if method in ("GET", "HEAD"):
            self._send_response(200, (APP_DIR / "index.html").read_bytes())
            return

        self._send_response(405, "<pre>Método não permitido</pre>")

    def do_GET(self) -> None:
        self._serve("GET")

    def do_HEAD(self) -> None:
        self._serve("HEAD")

    def do_POST(self) -> None:
        self._serve("POST")

    def do_DELETE(self) -> None:
        self._serve("DELETE")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4280
    print(f"Timenow GestNow em http://localhost:{port}")
    print(f"  arquivos estaticos: {APP_DIR}")
    print("  modo local de demonstracao; use Ctrl+C para parar\n")
    ThreadingHTTPServer(("127.0.0.1", port), LocalHandler).serve_forever()
