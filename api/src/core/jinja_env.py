from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .money import format_brl

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
)

# Presentation filter for money: the database and the Python values keep
# integer cents (D5); the reais only appear where a person reads them.
jinja_env.filters["brl"] = format_brl
