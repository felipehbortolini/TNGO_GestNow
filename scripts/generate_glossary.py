"""Regenerate ``api/src/core/glossario.json`` from ``CONTEXT.md``.

CONTEXT.md is the single source of the glossary. Only ``api/`` is deployed to
Azure, so the siglas the shell explains on hover travel as a file inside it;
this script is the one thing that writes that file, and the test
``test_glossario.py`` fails when the file and CONTEXT.md disagree.

    api/.venv/bin/python scripts/generate_glossary.py          (Windows: Scripts\\python.exe)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "api"))

from src.core import glossary  # noqa: E402  (the path above must exist before the import)

CONTEXT_FILE = ROOT_DIR / "CONTEXT.md"


def main() -> int:
    parsed = glossary.parse_context(CONTEXT_FILE.read_text(encoding="utf-8"))
    glossary.write_glossary(parsed)
    print(
        f"glossario.json atualizado: {len(parsed.abbreviations)} siglas e "
        f"{len(parsed.patterns)} notacao(oes), a partir de {CONTEXT_FILE.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
