"""Imprime, numa chamada só, o contexto de uma issue da migração.

Uso (da raiz do repositório ou do worktree da issue):

    python scripts/execucao/contexto_da_issue.py 012

Saída: o arquivo da issue, as seções da spec citadas em ``spec_decisions``, as
histórias citadas em ``source_requirements`` e a Definição de pronto com as
decisões da execução do ``index.md``. Substitui a leitura da spec, do index e
do modelo de dados inteiros: o agente lê só o que a issue cita.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISSUES = ROOT / "docs" / "issues" / "spec-migracao-gestnow"


def section(spec: list[str], decision: str) -> str:
    """O texto de uma decisão (``### D7. ...``) até o próximo título."""
    start = next((i for i, line in enumerate(spec) if re.match(rf"### {decision}\.", line)), None)
    if start is None:
        return ""
    end = next(
        (i for i in range(start + 1, len(spec)) if spec[i].startswith(("### ", "## "))),
        len(spec),
    )
    return "\n".join(spec[start:end]).rstrip()


def story(body: list[str], number: int) -> str:
    """O texto de uma história de usuário numerada, com as linhas de continuação."""
    start = next((i for i, line in enumerate(body) if re.match(rf"{number}\. ", line)), None)
    if start is None:
        return ""
    end = next(
        (
            i
            for i in range(start + 1, len(body))
            if re.match(r"\d+\. ", body[i]) or body[i].startswith(("#", "---"))
        ),
        len(body),
    )
    return "\n".join(body[start:end]).rstrip()


def main(number: str) -> int:
    matches = sorted(ISSUES.glob(f"{number}-*.md"))
    if not matches:
        print(f"Issue {number} não encontrada em {ISSUES}", file=sys.stderr)
        return 1
    issue = Path(matches[0])
    text = issue.read_text(encoding="utf-8")
    spec = (ROOT / "docs" / "SPEC-MIGRACAO-GESTNOW.md").read_text(encoding="utf-8").split("\n")
    index = (ISSUES / "index.md").read_text(encoding="utf-8")

    front = text.split("---")[1]
    decisions = (
        re.findall(r"^  - (D\d+[ab]?)\s*$", front.split("spec_decisions:")[-1], re.MULTILINE)
        if "spec_decisions:" in front
        else []
    )
    requirements = [int(n) for n in re.findall(r"HU-(\d+)", front)]

    print(f"########## ISSUE {issue.name}\n{text}\n")

    print("########## SPEC: decisões citadas (seções inteiras)")
    for decision in decisions:
        print(section(spec, decision) + "\n")

    print("########## SPEC: histórias citadas")
    first = next(i for i, line in enumerate(spec) if line.startswith("## User Stories"))
    last = next(i for i, line in enumerate(spec) if line.startswith("## Implementation Decisions"))
    body = spec[first:last]
    for requirement in requirements:
        print(story(body, requirement))
    print()

    print("########## index.md: Definição de pronto e decisões da execução")
    found = re.search(r"## Definição de pronto.*?(?=\n## Cobertura)", index, re.DOTALL)
    print(found.group(0).strip() if found else "")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
