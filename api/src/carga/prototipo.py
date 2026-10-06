"""Read the prototype collections converted by ``scripts/converter_mocks.mjs``."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_FILE = Path(__file__).parent / "dados" / "prototipo.json"


@lru_cache(maxsize=1)
def _all_collections() -> dict[str, Any]:
    """Load the whole converted prototype file once."""
    return json.loads(_FILE.read_text(encoding="utf-8"))


def prototype_collection(name: str) -> Any:
    """Return one prototype collection (e.g. ``"acoes"``) exactly as the mocks define it."""
    return _all_collections()[name]
