"""Local development server that runs without Azure Functions Core Tools."""

from __future__ import annotations

import json
import mimetypes
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

from src.blueprints import health, nav  # noqa: E402

DEMO_USER = {
    "clientPrincipal": {
        "identityProvider": "aad",
        "userId": "00000000-0000-0000-0000-000000000000",
        "userDetails": "gestnow.demo@example.invalid",
        "userRoles": ["anonymous", "authenticated"],
        "claims": [{"typ": "name", "val": "Demonstração GestNow"}],
    }
}

ROUTES: list[tuple[str, re.Pattern[str], Callable[[func.HttpRequest], func.HttpResponse]]] = [
    ("GET", re.compile(r"^/api/health$"), health.health),
    ("GET", re.compile(r"^/api/nav$"), nav.main_nav),
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
                headers=dict(self.headers.items()),
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
