"""Fixtures dos testes das rotas de Configurações: rotas na transação do teste e o cenário.

``fragment_route`` abre a própria unidade de trabalho, que gravaria no ``gestnow_teste`` e não
veria nada do que o teste escreveu em ``db_session``. Aqui a unidade de trabalho é a sessão do
teste, no modo demonstração, com o relógio em 25/09/2026: a rota lê os projetos, as pessoas e os
parâmetros do cenário e nada sobrevive ao teste.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from src.core import calendario, config, database
from tests.apoio_riscos import REFERENCIA, Cenario, montar_cenario


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
    """Dois projetos, os quatro perfis e a versão 1 dos 14 grupos de parâmetros.

    O cenário é o dos riscos porque a troca da escala precisa de um risco criado pela fachada
    da Riscos para a contagem de críticos mudar na consulta seguinte.
    """
    return montar_cenario(sessao)
