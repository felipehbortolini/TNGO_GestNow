"""Health check blueprint."""

from datetime import UTC, datetime

import azure.functions as func

bp = func.Blueprint()


@bp.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Return a simple health-check JSON response."""
    return func.HttpResponse(
        body=(f'{{"status":"ok","timestamp":"{datetime.now(UTC).isoformat()}"}}'),
        status_code=200,
        mimetype="application/json",
    )
