"""The Design System colors as the API sees them: one source, ``app/ds/tokens.css`` (D12).

The cells of the Excel the server builds take their colors from the same tokens
the screen uses, so a color changed in ``tokens.css`` changes in the spreadsheet
too. No hexadecimal is written in the Python code: this module is the only place
that holds the values, and it holds them as a file.

Only ``api/`` is deployed to Azure, where ``app/ds/tokens.css`` does not exist.
``scripts/generate_ds_assets.py`` therefore writes the colors to
``tokens_ds.json`` beside this module (and copies the logo that goes in the
Excel header, ``logo_timenow.png``), and a test fails when either copy stops
matching the Design System: the source stays one, and the copy that travels with
the API cannot go stale unnoticed. To use a new token, add it to ``tokens.css``
and run the script.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

TOKENS_FILE = Path(__file__).with_name("tokens_ds.json")
LOGO_FILE = Path(__file__).with_name("logo_timenow.png")

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
# ``--ok-50: #DDF8F0;``: a custom property whose value is a plain hexadecimal color.
_COLOR_DECLARATION = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3}))\s*;")
# ``--font: "Segoe UI", system-ui, sans-serif;``: the first family is the one a spreadsheet can name.
_FONT_DECLARATION = re.compile(r'--font\s*:\s*"([^"]+)"')

_SHORT_HEX_LENGTH = 4


class UnknownTokenError(LookupError):
    """The token is not a color of ``tokens.css``: a typo, or a token that needs the script."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Token do Design System desconhecido: {name}")


@dataclass(frozen=True)
class DesignTokens:
    """What the API reads of ``tokens.css``: the colors by token name and the base font."""

    font: str
    colors: Mapping[str, str]


def parse_css(css: str) -> DesignTokens:
    """Read the colors (``#RRGGBB`` by token name) and the base font out of ``tokens.css``."""
    text = _COMMENT.sub("", css)
    colors = {name: _long_hex(value) for name, value in _COLOR_DECLARATION.findall(text)}
    font = _FONT_DECLARATION.search(text)
    return DesignTokens(font=font.group(1) if font else "", colors=colors)


def to_data(tokens: DesignTokens) -> dict[str, Any]:
    """The tokens as the JSON file keeps them (Portuguese keys, like every data file)."""
    return {
        "descricao": (
            "Cores e fonte de app/ds/tokens.css que o Excel do servidor usa (D12). "
            "Gerado por scripts/generate_ds_assets.py; não edite à mão."
        ),
        "fonte": tokens.font,
        "cores": dict(tokens.colors),
    }


def from_data(data: Mapping[str, Any]) -> DesignTokens:
    """Read the tokens back from the shape ``to_data`` writes."""
    return DesignTokens(font=data["fonte"], colors=dict(data["cores"]))


@cache
def load_tokens() -> DesignTokens:
    """The tokens the API uses, read once from ``tokens_ds.json``."""
    return from_data(json.loads(TOKENS_FILE.read_text(encoding="utf-8")))


def write_tokens(tokens: DesignTokens, path: Path = TOKENS_FILE) -> None:
    """Write the tokens file; ``scripts/generate_ds_assets.py`` is the only caller."""
    text = json.dumps(to_data(tokens), ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def color(name: str) -> str:
    """The color of a token as ``RRGGBB``, the way a spreadsheet wants it.

    Fails loud on a name that is not a color of ``tokens.css``.
    """
    value = load_tokens().colors.get(name)
    if value is None:
        raise UnknownTokenError(name)
    return value.removeprefix("#")


def font_name() -> str:
    """The first family of the base font (``--font``), the one a spreadsheet can name."""
    return load_tokens().font


def _long_hex(value: str) -> str:
    """``#abc`` becomes ``#AABBCC``; every color is kept as six uppercase digits."""
    digits = value.removeprefix("#")
    if len(value) == _SHORT_HEX_LENGTH:
        digits = "".join(character * 2 for character in digits)
    return f"#{digits.upper()}"
