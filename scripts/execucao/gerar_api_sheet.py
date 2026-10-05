"""Imprime a folha de assinaturas da plataforma já pronta (``api/src/core`` e afins).

Uso (da raiz do repositório ou do worktree da issue):

    python scripts/execucao/gerar_api_sheet.py

Lê o código por AST (sem importar nada), então reflete o que existe no
momento: funções públicas com a assinatura e a primeira linha da docstring, e
as classes com os métodos. O agente de uma issue usa a saída para reutilizar a
plataforma em vez de explorar o repositório.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = ("api/src/core/*.py", "api/src/blueprints/*.py", "api/src/carga/*.py")


def describe(path: Path) -> str:
    """O bloco de Markdown de um arquivo: resumo do módulo e itens públicos."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    items: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith(
            "_"
        ):
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            doc = (ast.get_docstring(node) or "").split("\n")[0]
            items.append(f"  def {node.name}({ast.unparse(node.args)}){returns}  # {doc}")
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            doc = (ast.get_docstring(node) or "").split("\n")[0]
            methods = [
                member.name
                for member in node.body
                if isinstance(member, ast.FunctionDef) and not member.name.startswith("_")
            ]
            items.append(f"  class {node.name}  # {doc}  [{', '.join(methods[:8])}]")
    if not items:
        return ""
    summary = (ast.get_docstring(tree) or "").split("\n")[0]
    return f"## {path.relative_to(ROOT).as_posix()}\n{summary}\n" + "\n".join(items)


def main() -> int:
    blocks = []
    for pattern in PATTERNS:
        for path in sorted(ROOT.glob(pattern)):
            block = describe(path)
            if block:
                blocks.append(block)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
