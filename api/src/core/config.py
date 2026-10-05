"""Local configuration loading.

``GESTNOW_DATABASE_URL`` is an environment variable in every environment
(D5). On the local machine it is written by ``scripts/prepare_database.py``
into ``api/local.settings.json`` — the same file the Azure Functions runtime
reads — which is outside git. Loading it into the process environment lets the
local server and the test suite see the same variable the Functions host
would.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

LOCAL_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "local.settings.json"


def load_local_settings() -> None:
    """Copy ``Values`` from the local settings file without overwriting the environment."""
    if not LOCAL_SETTINGS_PATH.is_file():
        return
    settings = json.loads(LOCAL_SETTINGS_PATH.read_text(encoding="utf-8"))
    values = settings.get("Values", {})
    for key, value in values.items():
        if isinstance(value, str) and key not in os.environ:
            os.environ[key] = value
