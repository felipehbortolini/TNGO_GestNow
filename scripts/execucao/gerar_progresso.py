#!/usr/bin/env python3
"""Regenerate PROGRESSO.md from the issue index and the git history (one commit per issue)."""

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "docs/issues/spec-migracao-gestnow/index.md"
ROW = re.compile(r"\| ISSUE-(\d+) \| (.*?) \| (\d+) \| \w+ \| ([a-z-]+) \| [a-z-]+ \| (.*?) \|")
STATUS_LABEL = {
    "done": "concluída",
    "in-progress": "em andamento",
    "blocked": "bloqueada",
    "proposed": "na fila",
}


def commit_of(number: str) -> str:
    """Return the short hash of the commit that closed the issue, or a dash."""
    out = subprocess.run(  # noqa: S603
        ["git", "log", "-1", "--format=%h", f"--grep=^ISSUE-{number}:"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return f"`{out}`" if out else "-"


def main() -> None:
    """Write PROGRESSO.md."""
    rows = [m.groups() for m in map(ROW.match, INDEX.read_text(encoding="utf-8").split("\n")) if m]
    by_status: dict[str, list[tuple[str, ...]]] = {}
    for row in rows:
        by_status.setdefault(row[3], []).append(row)
    done = by_status.get("done", [])
    last = done[-1][0] if done else "-"
    lines = [
        f"<!-- Progresso da migração: {len(done)} de {len(rows)} -->",
        "",
        "# Progresso da migração",
        "",
        (
            f"**{len(done)} de {len(rows)} issues concluídas** (última fechada: ISSUE-{last}). "
            f"Atualizado em {datetime.now(UTC):%d/%m/%Y %H:%M} UTC por "
            "`scripts/execucao/gerar_progresso.py`; a situação oficial é a coluna Situação do "
            "`docs/issues/spec-migracao-gestnow/index.md`."
        ),
        "",
        "| Situação | Quantidade | Issues |",
        "|---|---|---|",
    ]
    for status in ("done", "in-progress", "blocked", "proposed"):
        group = by_status.get(status, [])
        if group:
            ids = ", ".join(r[0] for r in group)
            lines.append(f"| {STATUS_LABEL[status]} | {len(group)} | {ids} |")
    lines += ["", "## Concluídas", "", "| Issue | Título | Commit |", "|---|---|---|"]
    lines += [f"| ISSUE-{n} | {t} | {commit_of(n)} |" for n, t, _e, _s, _b in done]
    pending = [r for r in rows if r[3] != "done"]
    if pending:
        lines += [
            "",
            "## Em andamento, bloqueadas e na fila",
            "",
            "| Issue | Título | Situação | Bloqueada por |",
            "|---|---|---|---|",
        ]
        lines += [f"| ISSUE-{n} | {t} | {STATUS_LABEL[s]} | {b} |" for n, t, _e, s, b in pending]
    lines += [
        "",
        (
            "Pendências de fonte: `docs/issues/spec-migracao-gestnow/PENDENCIAS-DE-FONTE.md`. "
            "Retrato por entrega: `docs/issues/spec-migracao-gestnow/RELATORIO-DE-EXECUCAO.md`."
        ),
        "",
    ]
    (ROOT / "PROGRESSO.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
