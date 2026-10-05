"""Local configuration loading and the app mode.

``GESTNOW_DATABASE_URL`` is an environment variable in every environment
(D5). On the local machine it is written by ``scripts/prepare_database.py``
into ``api/local.settings.json`` — the same file the Azure Functions runtime
reads — which is outside git. Loading it into the process environment lets the
local server and the test suite see the same variable the Functions host
would.

``GESTNOW_MODO`` decides between demonstration and production (ISSUE-008):
unset means demonstration, the local mode; anything other than the two known
values fails loud instead of silently loading the wrong base. In production,
``GESTNOW_ADMIN_EMAIL`` carries the first Admin's e-mail.

``GESTNOW_ENVIO_EMAIL`` switches the real e-mail sending on (ISSUE-013, D12),
with the same rule: unset means off — the notification port then records the
send as simulated — and any other value than the two known ones fails loud.
The Microsoft Graph credentials that the "on" state needs are read by
``graph_mail``, which is the only consumer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

LOCAL_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "local.settings.json"

APP_MODE_VARIABLE = "GESTNOW_MODO"
ADMIN_EMAIL_VARIABLE = "GESTNOW_ADMIN_EMAIL"
EMAIL_SENDING_VARIABLE = "GESTNOW_ENVIO_EMAIL"

DEMONSTRATION = "demonstracao"
PRODUCTION = "producao"

EMAIL_SENDING_OFF = "desligado"
EMAIL_SENDING_ON = "ligado"


class InvalidApplicationModeError(RuntimeError):
    """Raised when the app mode value is not one of the two known modes."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Valor invalido em {APP_MODE_VARIABLE}: {value!r}. "
            f"Use {DEMONSTRATION!r} ou {PRODUCTION!r}."
        )


class InvalidEmailSendingError(RuntimeError):
    """Raised when the e-mail sending value is not one of the two known states."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Valor invalido em {EMAIL_SENDING_VARIABLE}: {value!r}. "
            f"Use {EMAIL_SENDING_OFF!r} ou {EMAIL_SENDING_ON!r}."
        )


def load_local_settings() -> None:
    """Copy ``Values`` from the local settings file without overwriting the environment."""
    if not LOCAL_SETTINGS_PATH.is_file():
        return
    settings = json.loads(LOCAL_SETTINGS_PATH.read_text(encoding="utf-8"))
    values = settings.get("Values", {})
    for key, value in values.items():
        if isinstance(value, str) and key not in os.environ:
            os.environ[key] = value


def app_mode() -> str:
    """The configured app mode; unset means demonstration, any other value fails loud."""
    value = (os.environ.get(APP_MODE_VARIABLE) or DEMONSTRATION).strip().lower()
    if value == DEMONSTRATION:
        return DEMONSTRATION
    if value == PRODUCTION:
        return PRODUCTION
    raise InvalidApplicationModeError(value)


def admin_email() -> str | None:
    """The first Admin's e-mail configured for production, or ``None`` when absent."""
    value = os.environ.get(ADMIN_EMAIL_VARIABLE)
    return value.strip() if value and value.strip() else None


def email_sending() -> str:
    """The configured e-mail sending state; unset means off, any other value fails loud."""
    value = (os.environ.get(EMAIL_SENDING_VARIABLE) or EMAIL_SENDING_OFF).strip().lower()
    if value == EMAIL_SENDING_OFF:
        return EMAIL_SENDING_OFF
    if value == EMAIL_SENDING_ON:
        return EMAIL_SENDING_ON
    raise InvalidEmailSendingError(value)
