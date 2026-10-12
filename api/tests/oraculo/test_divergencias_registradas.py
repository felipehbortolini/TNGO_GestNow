"""As divergências registradas (ISSUE-089, Q31): a tabela completa e o Histórico ligado às issues.

Lê ``docs/DIVERGENCIAS-DO-PROTOTIPO.md`` como o repositório o guarda: a tabela
principal (regra, número do protótipo, número correto, motivo e situação) sai
inteira, com as cinco colunas preenchidas e a situação não vazia; o Histórico cita
só issues que existem no ``index.md``; e o arquivo mantém ao menos as linhas
conhecidas. O teste lê o markdown, nunca o edita.
"""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DIVERGENCES_PATH = REPOSITORY_ROOT / "docs" / "DIVERGENCIAS-DO-PROTOTIPO.md"
ISSUES_INDEX_PATH = REPOSITORY_ROOT / "docs" / "issues" / "spec-migracao-gestnow" / "index.md"

MAIN_HEADER = "Regra"
MAIN_COLUMNS = ("Regra", "Número do protótipo", "Número correto", "Motivo", "Situação")
HISTORY_HEADER = "Data"
HISTORY_COLUMNS = ("Data", "Issue", "Alteração")

# A tabela principal fechou em 82 linhas e o Histórico em 40 na ISSUE-089; a
# contagem mínima guarda o arquivo contra um corte acidental.
MINIMUM_MAIN_ROWS = 80
MINIMUM_HISTORY_ROWS = 38

ISSUE_PATTERN = re.compile(r"ISSUE-\d{3}")
INDEX_ROW_PATTERN = re.compile(r"^\|\s*(ISSUE-\d{3})\s*\|", re.MULTILINE)
HEADERS = (MAIN_HEADER, HISTORY_HEADER)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    return all(cell and set(cell) <= set("-: ") for cell in cells)


def _rows(text: str, header_first_cell: str) -> list[list[str]]:
    """As linhas de dados da tabela cujo cabeçalho começa por ``header_first_cell``."""
    rows: list[list[str]] = []
    started = False
    for line in text.splitlines():
        if not line.startswith("|"):
            if started:
                break
            continue
        cells = _cells(line)
        if cells[0] in HEADERS:
            if cells[0] == header_first_cell:
                started = True
                continue
            if started:
                break
        if not started:
            continue
        if not _is_separator(cells):
            rows.append(cells)
    return rows


def test_a_tabela_principal_tem_as_cinco_colunas_preenchidas() -> None:
    rows = _rows(_text(DIVERGENCES_PATH), MAIN_HEADER)

    assert len(rows) >= MINIMUM_MAIN_ROWS, "as divergencias conhecidas continuam registradas"
    for number, cells in enumerate(rows, start=2):
        assert len(cells) == len(MAIN_COLUMNS), f"linha {number}: cinco colunas"
        for label, cell in zip(MAIN_COLUMNS, cells, strict=True):
            assert cell, f"linha {number}: a coluna {label} esta preenchida"
        assert cells[-1], f"linha {number}: a situacao esta preenchida"


def test_todo_issue_citado_no_historico_existe_no_indice() -> None:
    history = _rows(_text(DIVERGENCES_PATH), HISTORY_HEADER)
    known = set(INDEX_ROW_PATTERN.findall(_text(ISSUES_INDEX_PATH)))

    assert len(history) >= MINIMUM_HISTORY_ROWS, "o historico conhecido continua registrado"
    assert known, "o indice de issues lista as ISSUE-NNN"
    for number, cells in enumerate(history, start=2):
        assert len(cells) == len(HISTORY_COLUMNS), f"linha {number}: tres colunas"
        assert cells[1], f"linha {number}: a issue esta preenchida"
        for issue in ISSUE_PATTERN.findall(" ".join(cells)):
            assert issue in known, f"linha {number}: {issue} existe no indice de issues"
