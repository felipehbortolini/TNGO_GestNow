"""Regenerate the Design System copies that travel with the API (ISSUE-017, D12).

``app/ds/tokens.css`` is the single source of the colors and
``app/ds/assets/favicon-timenow.png`` the single source of the logo. Only
``api/`` is deployed to Azure, so the Excel the server builds reads
``api/src/core/tokens_ds.json`` and ``api/src/core/logo_timenow.png``. This
script is the one thing that writes both files, and the test
``test_ativos_da_exportacao.py`` fails when either stops matching the Design
System.

    api/.venv/bin/python scripts/generate_ds_assets.py          (Windows: Scripts\\python.exe)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "api"))

from src.core import design_tokens  # noqa: E402  (the path above must exist before the import)

TOKENS_CSS = ROOT_DIR / "app" / "ds" / "tokens.css"
DS_LOGO = ROOT_DIR / "app" / "ds" / "assets" / "favicon-timenow.png"


def main() -> int:
    tokens = design_tokens.parse_css(TOKENS_CSS.read_text(encoding="utf-8"))
    design_tokens.write_tokens(tokens)
    shutil.copyfile(DS_LOGO, design_tokens.LOGO_FILE)
    print(
        f"tokens_ds.json atualizado: {len(tokens.colors)} cores e a fonte {tokens.font!r}, "
        f"a partir de {TOKENS_CSS.name}; logo copiado de {DS_LOGO.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
