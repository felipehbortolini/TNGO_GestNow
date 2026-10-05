import azure.functions as func

from src.blueprints.health import bp as health_bp
from src.blueprints.nav import bp as nav_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_functions(health_bp)
app.register_functions(nav_bp)
