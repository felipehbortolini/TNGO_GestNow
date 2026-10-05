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
"""

from __future__ import annotations

import json
import os
from pathlib import Path

LOCAL_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "local.settings.json"

APP_MODE_VARIABLE = "GESTNOW_MODO"
ADMIN_EMAIL_VARIABLE = "GESTNOW_ADMIN_EMAIL"

DEMONSTRATION = "demonstracao"
PRODUCTION = "producao"


class InvalidApplicationModeError(RuntimeError):
    """Raised when the app mode value is not one of the two known modes."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Valor invalido em {APP_MODE_VARIABLE}: {value!r}. "
            f"Use {DEMONSTRATION!r} ou {PRODUCTION!r}."
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
