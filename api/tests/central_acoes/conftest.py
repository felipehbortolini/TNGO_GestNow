"""Fixtures dos testes da Central de Ações: as rotas na transação do teste e o cenário.

``fragment_route`` abre a própria unidade de trabalho, que gravaria no ``gestnow_teste`` e não
enxergaria o que o teste escreveu em ``db_session``. Aqui a unidade de trabalho é a sessão do
teste, no modo demonstração: a rota lê os projetos e as pessoas do cenário e nada sobrevive ao
teste. O módulo registra o tipo de origem dos anexos ao importar o ``service``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from src.core import calendario, config, database
from tests.apoio_acoes import REFERENCIA, Cenario, montar_cenario


@pytest.fixture
def sessao(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """A sessão do teste serve a toda rota, no modo demonstração, com o relógio em 25/09/2026."""

    @contextmanager
    def unidade_do_teste() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(database, "unidade_de_trabalho", unidade_do_teste)
    monkeypatch.delenv(config.APP_MODE_VARIABLE, raising=False)
    monkeypatch.setattr(calendario, "today", lambda: REFERENCIA)
    return db_session


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    """Dois projetos e cinco pessoas, um colaborador de cada perfil."""
    return montar_cenario(sessao)
