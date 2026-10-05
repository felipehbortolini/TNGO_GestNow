"""Health check blueprint."""

import json

import azure.functions as func

from src.core import calendario, database

bp = func.Blueprint()


@bp.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Report the service status, the database situation and the migration revision."""
    body = json.dumps(
        {
            "status": "ok",
            "timestamp": calendario.now().isoformat(),
            "banco": database.database_report(),
        }
    )
    return func.HttpResponse(body=body, status_code=200, mimetype="application/json")
