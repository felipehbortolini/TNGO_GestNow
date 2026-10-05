"""Leva as linhas ``DECISÃO:`` dos registros de execução para o Histórico de decisões da spec.

Uso (da raiz do repositório):

    python scripts/execucao/consolidar_decisoes.py 012 015 016

Cada linha ``DECISÃO: tema | decisão | refs`` do ``## Registro de execução`` de uma issue
vira uma linha da tabela da spec, "Decisão da execução (ISSUE-NNN), pendente de revisão do
dono". É idempotente: uma decisão (issue e tema) que já está na tabela não se repete.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISSUES = ROOT / "docs" / "issues" / "spec-migracao-gestnow"
SPEC = ROOT / "docs" / "SPEC-MIGRACAO-GESTNOW.md"
ROW = "| Decisão da execução (ISSUE-{number}), pendente de revisão do dono | {theme} | {decision} | {refs} |"


def decisions_of(issue: Path) -> list[tuple[str, str, str]]:
    """As decisões ``(tema, decisão, refs)`` escritas no registro de execução da issue."""
    text = issue.read_text(encoding="utf-8")
    registry = (
        text.split("## Registro de execução")[-1] if "## Registro de execução" in text else ""
    )
    found = []
    for line in registry.splitlines():
        match = re.match(r"DECISÃO:\s*(.+?)\s*\|\s*(.+)\s*\|\s*([^|]+)$", line.strip())
        if match:
            found.append((match.group(1).strip(), match.group(2).strip(), match.group(3).strip()))
    return found


def main(numbers: list[str]) -> int:
    lines = SPEC.read_text(encoding="utf-8").split("\n")
    last = max(i for i, line in enumerate(lines) if line.startswith("| Decisão da execução ("))
    added = 0
    for number in numbers:
        issue = next(iter(sorted(ISSUES.glob(f"{number}-*.md"))), None)
        if issue is None:
            print(f"Issue {number} não encontrada", file=sys.stderr)
            continue
        for theme, decision, refs in decisions_of(issue):
            row = ROW.format(number=number, theme=theme, decision=decision, refs=refs)
            if any(f"(ISSUE-{number})" in line and f"| {theme} |" in line for line in lines):
                continue
            last += 1
            lines.insert(last, row)
            added += 1
    SPEC.write_text("\n".join(lines), encoding="utf-8")
    print(f"{added} decisão(ões) acrescentada(s) ao Histórico de decisões da spec.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
