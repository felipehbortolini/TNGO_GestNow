"""Fixtures that give every test its own data directory.

Before this file, no test touched the persistence port — the domain
tests are pure functions. The isolation tests write to disk, so each of
them gets a throwaway ``PROGRAMACAO_DATA_DIR``, and the real base is
never touched.

The port guard keeps one instance per environment for the life of the
process — by design, and without eviction (decision 8). Tests therefore
never reuse a slug across tests: a slug used by an earlier test would
come back pointing at that test's already-deleted temp dir.

The register, unlike the port, is a single instance per installation —
so its singleton is dropped between tests, letting each one rebuild it
pointed at its own temp dir.

Tests run in production mode unless one says otherwise: the demo mode
seeds two environments and a full history into the register on first
read, and that noise would leak into every test that touches it. The
handful of tests that exercise the demonstration set
``PROGRAMACAO_MODO=demo`` explicitly.
"""

import pytest

from src.core import registro


@pytest.fixture(autouse=True)
def dados_temporarios(tmp_path, monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROGRAMACAO_MODO", "producao")
    registro.definir(None)
