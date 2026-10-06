import logging
import re
import unicodedata
from urllib.parse import quote

import azure.functions as func

from .jinja_env import jinja_env

logger = logging.getLogger(__name__)

# Headers that ds/ui.js turns into a toast. Percent-encoded because HTTP
# headers do not carry accents, and every message here is Portuguese.
CABECALHO_TOAST = "X-TN-Toast"
CABECALHO_TOAST_TIPO = "X-TN-Toast-Tipo"


def cabecalhos_de_toast(mensagem: str, tipo: str = "ok") -> dict[str, str]:
    """Headers that turn into a toast on the client. ``tipo``: ok|erro|aviso."""
    return {CABECALHO_TOAST: quote(mensagem), CABECALHO_TOAST_TIPO: tipo}


# ---------------------------------------------------------------------------
# Request utilities
# ---------------------------------------------------------------------------


def is_alpine_request(req: func.HttpRequest) -> bool:
    """Return ``True`` if the request was issued by Alpine AJAX.

    Alpine AJAX sets ``X-Alpine-Request: true`` on every request it makes.
    Use this to gate fragment endpoints so that direct browser access
    (bookmarks, cURL, etc.) is redirected to the application shell.
    """
    return req.headers.get("X-Alpine-Request") == "true"


def redirect_to(location: str, *, status_code: int = 302) -> func.HttpResponse:
    """Return an HTTP redirect response.

    Alpine AJAX captures redirects and triggers ``x-target.away`` behaviour
    (typically a full-page navigation).
    """
    return func.HttpResponse(
        status_code=status_code,
        headers={"Location": location},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_response_id(request: func.HttpRequest) -> str | None:
    """Parse the response-side target ID from the X-Alpine-Target header.

    ``x-target="comments"``            → ``"comments"``
    ``x-target="page_id:response_id"`` → ``"response_id"`` (alias form)
    ``x-target="a b"``                 → ``"a"`` (first target)
    """
    header = request.headers.get("X-Alpine-Target")
    if not header:
        return None
    first = header.split()[0]
    if ":" in first:
        return first.split(":", 1)[1]
    return first


class AlpineAjaxResponse(func.HttpResponse):
    """Render a Jinja2 template as an HTML fragment for Alpine AJAX.

    The rendered template should extend ``base_fragment.html``, which
    provides the root wrapper element.  ``target_id`` is resolved from
    *request* (or *target_id* override) and injected into the context
    automatically.

    Parameters
    ----------
    template_name:
        Jinja2 template path relative to ``api/src/templates/``.
    context:
        Variables passed to the template.
    request:
        The incoming HTTP request.  Used to read ``X-Alpine-Target``.
    target_id:
        Explicit override — wins over *request* when both are given.
    root_class:
        CSS classes injected into the root wrapper ``<div>`` via
        ``base_fragment.html``.  Use for flex/grid/spacing classes
        that the wrapper needs to carry so it doesn't break layout.
        Ignored when a template overrides ``{% block root %}``.
    status_code:
        HTTP status code (default 200).
    toast:
        Message shown to the user by ``ds/ui.js``.  Travels in a response
        header so the page never has to carry a slot for it — the same
        fragment serves a silent reload and a "saved" confirmation.
    toast_tipo:
        ``ok`` | ``erro`` | ``aviso``.
    """

    def __init__(
        self,
        template_name: str,
        context: dict | None = None,
        *,
        request: func.HttpRequest | None = None,
        target_id: str | None = None,
        root_class: str | None = None,
        status_code: int = 200,
        toast: str | None = None,
        toast_tipo: str = "ok",
    ):
        context = dict(context or {})

        # Resolve the ID the frontend expects
        resolved_id: str | None = None
        if target_id:
            resolved_id = target_id
        elif request is not None:
            resolved_id = _extract_response_id(request)

        if resolved_id:
            context.setdefault("target_id", resolved_id)

        if root_class:
            context.setdefault("root_class", root_class)

        html_content = jinja_env.get_template(template_name).render(**context)

        headers = {"Content-Type": "text/html", "Cache-Control": "no-cache"}
        if toast:
            headers.update(cabecalhos_de_toast(toast, toast_tipo))

        super().__init__(
            body=html_content,
            status_code=status_code,
            mimetype="text/html",
            headers=headers,
        )

    @classmethod
    def redirect(cls, location: str, *, status_code: int = 302) -> func.HttpResponse:
        """Return an HTTP redirect (e.g. after a successful POST).

        Usage::

            return AlpineAjaxResponse.redirect("/some/page")
        """
        return redirect_to(location, status_code=status_code)


# ---------------------------------------------------------------------------
# Downloads: a file, not a fragment
# ---------------------------------------------------------------------------

# What a plain ``filename=`` may carry: the characters of an ASCII name, nothing that breaks a header.
_UNSAFE_FILENAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._ -]")


def file_response(content: bytes, *, filename: str, content_type: str) -> func.HttpResponse:
    """A file the browser saves: the download exception of the Padrão (D14).

    A download answers with the file itself and no fragment, so it is the one
    kind of route that does not go through the Alpine gate (the browser asks
    for a file without that header); the access is still checked by
    ``routing.file_route``. ``filename`` may carry accents: the header gives an
    ASCII name for old clients and the UTF-8 one (RFC 5987) for the others.
    ``private, no-store`` because what is inside is data of the project.
    """
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    fallback = _UNSAFE_FILENAME_CHARACTERS.sub("_", ascii_name) or "arquivo"
    disposition = (
        f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"
    )
    return func.HttpResponse(
        body=content,
        mimetype=content_type,
        headers={
            "Content-Type": content_type,
            "Content-Disposition": disposition,
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
