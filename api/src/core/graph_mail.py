"""E-mail by Microsoft Graph ``sendMail``: written, and off until the owner turns it on (D12).

The adapter behind the notification port when ``GESTNOW_ENVIO_EMAIL=ligado``.
It sends as the app, not as the person who clicked: the app registered in
Microsoft Entra asks for a token with its own credentials (the client
credentials flow) and posts the message from the app's mailbox. Four
settings, all environment variables, so nothing changes in the code when the
app moves from the local machine to Azure (see ``VARIABLES``):

* ``GESTNOW_GRAPH_TENANT_ID``: the Entra directory (tenant) of the registration;
* ``GESTNOW_GRAPH_CLIENT_ID``: the application (client) id;
* ``GESTNOW_GRAPH_CLIENT_SECRET``: a secret of the registration, never in git;
* ``GESTNOW_GRAPH_REMETENTE``: the mailbox the e-mail leaves from.

The registration needs the Microsoft Graph application permission
``Mail.Send``, with the administrator's consent. A missing setting is a
delivery failure like any other: the port records it, with the names of the
variables that are empty (never their values), and the record that asked for
the notification stays.

The HTTP call is a seam of its own (``HttpClient``). The tests inject a fake;
``StdlibHttpClient`` is the only code here that touches the network. There is
no retry, no token cache and no attachment: sending is rare and started by a
person, ``sendMail`` is not idempotent, and a failed send is recorded for
someone to look at instead of repeated behind their back.
"""

from __future__ import annotations

import http.client
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote, urlencode, urlsplit

from src.core.notification import SENT, DeliveryError, NotificationRequest

# Public cloud endpoints. Sovereign clouds are out of scope.
AUTHORITY = "https://login.microsoftonline.com"
GRAPH_API = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"

# Each setting of ``GraphSettings`` and the environment variable it comes from.
# One table instead of one constant per name: it is the list the README shows.
VARIABLES = {
    "tenant_id": "GESTNOW_GRAPH_TENANT_ID",
    "client_id": "GESTNOW_GRAPH_CLIENT_ID",
    "client_secret": "GESTNOW_GRAPH_CLIENT_SECRET",
    "sender": "GESTNOW_GRAPH_REMETENTE",
}

# Each of the two calls (token, then sendMail) gets this long before the send
# is recorded as failed. The person is waiting on the screen, with the request's
# transaction open, so the wait has to be short.
REQUEST_TIMEOUT_SECONDS = 10

# What is read back of an answer: Graph's errors are a few hundred bytes.
MAX_RESPONSE_BYTES = 65536
MAX_DETAIL_CHARS = 500

INCOMPLETE_SETTINGS = "O e-mail não foi enviado: a configuração do envio está incompleta."
TIMED_OUT = "O e-mail não foi enviado: sem resposta da Microsoft dentro do tempo limite."
NETWORK_FAILURE = "O e-mail não foi enviado: falha de rede ao falar com a Microsoft."
ENTRA_NO_ACCESS = "O e-mail não foi enviado: o Microsoft Entra não devolveu o token de acesso."
ENTRA_REFUSED = "o Microsoft Entra recusou as credenciais do app"
GRAPH_REFUSED = "o Microsoft Graph recusou o envio"


@dataclass(frozen=True)
class HttpResponse:
    """What the adapter needs of an answer: the status and the body."""

    status: int
    body: bytes


class HttpClient(Protocol):
    """The network seam: one POST. Any answer, error statuses included, is a response."""

    def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> HttpResponse:
        """POST the body and return the answer; raise ``OSError`` when there is none."""


class StdlibHttpClient:
    """The real HTTP client: standard library only, https only, no redirects.

    It does not read proxy settings: Azure Functions reaches Microsoft
    directly. Whoever must go through a corporate proxy supplies another
    ``HttpClient``.
    """

    def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> HttpResponse:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            message = "O envio de e-mail só fala https."
            raise ValueError(message)
        target = parts.path + (f"?{parts.query}" if parts.query else "")
        connection = http.client.HTTPSConnection(parts.hostname, parts.port, timeout=timeout)
        try:
            connection.request("POST", target, body=body, headers=dict(headers))
            response = connection.getresponse()
            return HttpResponse(status=response.status, body=response.read(MAX_RESPONSE_BYTES))
        finally:
            connection.close()


@dataclass(frozen=True)
class GraphSettings:
    """What the adapter needs to speak for the app; read from the environment, never from code."""

    tenant_id: str
    client_id: str
    # Out of ``repr`` so that printing or logging the settings can never show it.
    client_secret: str = field(repr=False)
    sender: str

    @classmethod
    def from_environment(cls) -> GraphSettings:
        """Read the four settings; an absent variable is an empty string, checked later."""
        return cls(**{attribute: _read(variable) for attribute, variable in VARIABLES.items()})

    def missing_variables(self) -> list[str]:
        """The environment variables that are empty, by name and never by value."""
        return [
            variable for attribute, variable in VARIABLES.items() if not getattr(self, attribute)
        ]


class GraphMailChannel:
    """Delivers by Microsoft Graph ``sendMail``, as the app registered in Entra."""

    situation = SENT

    def __init__(self, settings: GraphSettings, http_client: HttpClient) -> None:
        self._settings = settings
        self._http = http_client

    def deliver(self, request: NotificationRequest) -> None:
        """Get a token, then post the message; every way to fail is a ``DeliveryError``."""
        missing = self._settings.missing_variables()
        if missing:
            raise DeliveryError(INCOMPLETE_SETTINGS, detail=f"Faltam: {', '.join(missing)}.")
        self._send_mail(self._acquire_token(), request)

    def _acquire_token(self) -> str:
        """Client credentials flow: the app proves who it is with its own secret."""
        tenant = quote(self._settings.tenant_id, safe="")
        form = urlencode(
            {
                "client_id": self._settings.client_id,
                "client_secret": self._settings.client_secret,
                "scope": GRAPH_SCOPE,
                "grant_type": "client_credentials",
            }
        )
        response = self._post(
            f"{AUTHORITY}/{tenant}/oauth2/v2.0/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            body=form.encode("utf-8"),
        )
        if not _succeeded(response):
            raise _refused(ENTRA_REFUSED, response)
        token = _json_object(response.body).get("access_token")
        if not isinstance(token, str) or not token:
            raise DeliveryError(ENTRA_NO_ACCESS)
        return token

    def _send_mail(self, token: str, request: NotificationRequest) -> None:
        """Post the message as plain text: the body carries user-typed text, so no HTML."""
        sender = quote(self._settings.sender, safe="@")
        payload = {
            "message": {
                "subject": request.subject,
                "body": {"contentType": "Text", "content": request.body},
                "toRecipients": [
                    {"emailAddress": {"address": address}} for address in request.recipients
                ],
            },
            # A copy stays in the app mailbox's Sent Items, to compare with the trail.
            "saveToSentItems": True,
        }
        response = self._post(
            f"{GRAPH_API}/users/{sender}/sendMail",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(payload).encode("utf-8"),
        )
        if not _succeeded(response):
            raise _refused(GRAPH_REFUSED, response)

    def _post(self, url: str, *, headers: Mapping[str, str], body: bytes) -> HttpResponse:
        try:
            return self._http.post(url, headers=headers, body=body, timeout=REQUEST_TIMEOUT_SECONDS)
        except TimeoutError as error:
            raise DeliveryError(TIMED_OUT) from error
        except (OSError, http.client.HTTPException) as error:
            raise DeliveryError(
                NETWORK_FAILURE, detail=f"{type(error).__name__}: {error}"
            ) from error


def _read(variable: str) -> str:
    return (os.environ.get(variable) or "").strip()


def _succeeded(response: HttpResponse) -> bool:
    """Entra answers 200 and Graph answers 202 Accepted: the range is the contract."""
    return 200 <= response.status < 300


def _refused(who: str, response: HttpResponse) -> DeliveryError:
    return DeliveryError(
        f"O e-mail não foi enviado: {who} (HTTP {response.status}).",
        detail=_error_detail(response.body),
    )


def _error_detail(body: bytes) -> str:
    """The service's own error code and message, on one line and capped."""
    payload = _json_object(body)
    error = payload.get("error")
    if isinstance(error, dict):
        # Graph nests the code and the message under an ``error`` object.
        code, message = error.get("code"), error.get("message")
    else:
        # The Entra token endpoint puts ``error`` and ``error_description`` at the top.
        code, message = error, payload.get("error_description")
    text = ": ".join(str(part) for part in (code, message) if part)
    return " ".join(text.split())[:MAX_DETAIL_CHARS]


def _json_object(body: bytes) -> dict[str, Any]:
    """The JSON object in the body; anything else, including bad JSON, is an empty one."""
    try:
        payload = json.loads(body)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}
