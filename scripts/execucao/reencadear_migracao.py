#!/usr/bin/env python3
"""Chain the migrations staged by a squash merge after the current Alembic head.

Usage (from the repository root, right after ``git merge --squash``):

    python scripts/execucao/reencadear_migracao.py 019

Every migration file added to the index gets ``down_revision`` set to the head of
the committed chain, so parallel issues that all branched from the same head end
up in a single line.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "api" / "migrations" / "versions"
REVISION = re.compile(r'^revision: str = "([^"]+)"', re.M)
DOWN = re.compile(r'^down_revision: str \| None = (?:"[^"]*"|None)', re.M)


def git(*args: str) -> str:
    """Run git in the repository root and return its output."""
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def committed_head() -> str:
    """Return the revision id that no committed migration descends from."""
    files = git("ls-tree", "--name-only", "HEAD", "api/migrations/versions/").split()
    revisions: dict[str, str | None] = {}
    for name in files:
        if not name.endswith(".py") or name.endswith("__init__.py"):
            continue
        text = git("show", f"HEAD:{name}")
        revision = REVISION.search(text)
        down = re.search(r'^down_revision: str \| None = "([^"]*)"', text, re.M)
        if revision:
            revisions[revision.group(1)] = down.group(1) if down else None
    parents = {d for d in revisions.values() if d}
    heads = [r for r in revisions if r not in parents]
    return sorted(heads)[-1]


def main() -> None:
    """Rechain every staged new migration, in file-name order."""
    number = sys.argv[1]
    head = committed_head()
    added = [
        Path(n)
        for n in git(
            "diff", "--cached", "--name-only", "--diff-filter=A", "api/migrations/versions/"
        ).split()
        if n.endswith(".py")
    ]
    for path in sorted(added):
        file = ROOT / path
        text = file.read_text(encoding="utf-8")
        revision = REVISION.search(text)
        if revision is None:
            continue
        text = DOWN.sub(f'down_revision: str | None = "{head}"', text, count=1)
        file.write_text(text, encoding="utf-8")
        head = revision.group(1)
        sys.stdout.write(f"{path.name}: down_revision -> encadeada (issue {number})\n")
        git("add", str(path))


if __name__ == "__main__":
    main()
