"""Duas conexões reservando número ao mesmo tempo: a trava de linha da D5.

A segunda conexão fica bloqueada no ``SELECT ... FOR UPDATE`` enquanto a
primeira não confirma; quando confirma, recebe o número seguinte, sem
repetir e sem buraco. O teste usa conexões de verdade (duas threads, duas
sessões) porque é a concorrência que está sob teste.
"""

from __future__ import annotations

import threading
import time
from datetime import date

from sqlalchemy import text

from src.core import database, numbering
from src.core.models import Client
from src.modulos.configuracoes.models import Person, Project

EMAIL_DO_GERENTE = "gerente-concorrencia@example.invalid"
NOME_DO_CLIENTE = "Cliente concorrencia"


def _projeto_commitado() -> int:
    with database.unidade_de_trabalho() as session:
        cliente = Client(name=NOME_DO_CLIENTE, active=True)
        gerente = Person(name="Gerente concorrencia", email=EMAIL_DO_GERENTE)
        session.add_all([cliente, gerente])
        session.flush()
        projeto = Project(
            client_id=cliente.id,
            manager_id=gerente.id,
            code="TN-2026-027",
            name="Projeto concorrencia",
            ata_pattern="TN-2026",
        )
        session.add(projeto)
        session.flush()
        return projeto.id


def _limpar(project_id: int) -> None:
    with database.get_engine().begin() as connection:
        connection.execute(
            text("DELETE FROM sequencia_numeracao WHERE projeto_id = :p"), {"p": project_id}
        )
        connection.execute(text("DELETE FROM projeto WHERE id = :p"), {"p": project_id})
        connection.execute(text("DELETE FROM pessoa WHERE email = :e"), {"e": EMAIL_DO_GERENTE})
        connection.execute(text("DELETE FROM cliente WHERE nome = :n"), {"n": NOME_DO_CLIENTE})


def test_duas_conexoes_recebem_numeros_diferentes_e_consecutivos() -> None:
    project_id = _projeto_commitado()
    try:
        reservados: dict[str, str] = {}
        primeira_pegou = threading.Event()
        liberar = threading.Event()

        def primeira() -> None:
            with database.unidade_de_trabalho() as session:
                projeto = session.get(Project, project_id)
                reservados["a"] = numbering.next_number(
                    session, project=projeto, kind="mudanca", reference_date=date(2026, 10, 5)
                )
                primeira_pegou.set()
                liberar.wait(timeout=10)

        def segunda() -> None:
            primeira_pegou.wait(timeout=10)
            with database.unidade_de_trabalho() as session:
                projeto = session.get(Project, project_id)
                reservados["b"] = numbering.next_number(
                    session, project=projeto, kind="mudanca", reference_date=date(2026, 10, 5)
                )

        threads = [threading.Thread(target=primeira), threading.Thread(target=segunda)]
        for thread in threads:
            thread.start()
        try:
            assert primeira_pegou.wait(timeout=10)
            time.sleep(0.3)
            assert "b" not in reservados  # a segunda conexão está travada na linha
            liberar.set()
        finally:
            for thread in threads:
                thread.join(timeout=10)

        assert reservados["a"] == "SM-TN-2026-0001"
        assert reservados["b"] == "SM-TN-2026-0002"
    finally:
        _limpar(project_id)
