"""HTTP seam: ``/api/health`` reports the database situation and the migration revision."""

from __future__ import annotations

import json
from pathlib import Path

import azure.functions as func
from alembic.config import Config
from alembic.script import ScriptDirectory

from src.blueprints.health import health
from src.core import database

API_DIR = Path(__file__).resolve().parents[2]


def health_request() -> func.HttpRequest:
    """A minimal GET request for the health handler."""
    return func.HttpRequest(method="GET", url="/api/health", headers={}, params={}, body=b"")


def test_health_mostra_o_banco_e_a_revisao() -> None:
    response = health(health_request())

    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["status"] == "ok"
    assert body["banco"]["situacao"] == "ok"

    head = ScriptDirectory.from_config(Config(str(API_DIR / "alembic.ini"))).get_current_head()
    assert body["banco"]["revisao"] == head


def test_health_sem_url_mostra_banco_indisponivel(monkeypatch) -> None:
    monkeypatch.delenv(database.DATABASE_URL_VARIABLE, raising=False)
    database.reset_engine()

    response = health(health_request())

    body = json.loads(response.get_body())
    assert body["banco"]["situacao"] == "erro"
    assert body["banco"]["revisao"] is None
