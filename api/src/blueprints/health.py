"""Health check blueprint."""

import json
from datetime import UTC, datetime

import azure.functions as func

from src.core import database

bp = func.Blueprint()


@bp.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Report the service status, the database situation and the migration revision."""
    body = json.dumps(
        {
            "status": "ok",
            "timestamp": datetime.now(UTC).isoformat(),
            "banco": database.database_report(),
        }
    )
    return func.HttpResponse(body=body, status_code=200, mimetype="application/json")
