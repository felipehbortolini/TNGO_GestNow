"""A revisão mais recente de cada ata (ISSUE-021): a linhagem é o número dentro do projeto."""

from __future__ import annotations

import pytest

from src.modulos.central_acoes.calculations import RevisionEntry, latest_revision_ids


def _entry(entry_id: int, number: str, revision: int, project_id: int = 1) -> RevisionEntry:
    return RevisionEntry(id=entry_id, project_id=project_id, number=number, revision=revision)


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        ([], set()),
        ([_entry(1, "TN-2026-0001", 0)], {1}),
        ([_entry(1, "TN-2026-0001", 0), _entry(2, "TN-2026-0001", 1)], {2}),
        ([_entry(2, "TN-2026-0001", 1), _entry(1, "TN-2026-0001", 0)], {2}),
        (
            [
                _entry(1, "TN-2026-0001", 0),
                _entry(2, "TN-2026-0001", 1),
                _entry(3, "TN-2026-0001", 2),
                _entry(4, "TN-2026-0002", 0),
            ],
            {3, 4},
        ),
        (
            [
                _entry(1, "TN-2026-0001", 0, project_id=1),
                _entry(2, "TN-2026-0001", 0, project_id=2),
            ],
            {1, 2},
        ),
    ],
    ids=[
        "sem atas",
        "uma ata, revisão 0",
        "duas revisões: vale a maior",
        "a ordem de chegada não importa",
        "três revisões e outra ata",
        "o mesmo número em dois projetos são duas linhagens",
    ],
)
def test_latest_revision_ids(entries: list[RevisionEntry], expected: set[int]) -> None:
    assert latest_revision_ids(entries) == expected
