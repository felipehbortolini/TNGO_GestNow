"""Costura de fachada da gravação segura: atomicidade, trilha, versão e dinheiro.

As fachadas de módulo ainda não existem; o que se prova aqui é o contrato
que elas vão usar: ``recording`` grava o registro e a trilha na mesma
transação, ``versioning`` recusa a versão vencida com o autor e a hora,
``numbering`` segue o padrão do projeto e o tipo de dinheiro guarda
centavos sem formatar.
"""

from __future__ import annotations

import re
from datetime import date

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core import database, money, numbering, recording
from src.core.errors import VersionConflictError
from src.core.models import AuditEntry, Client
from src.modulos.configuracoes.models import Collaborator, Person, Project


class ForcedFailureError(RuntimeError):
    """Falha forçada no meio da transação, só para provar a atomicidade."""


def _colaborador(
    session: Session,
    nome: str = "Ana Souza",
    email: str = "ana@example.invalid",
) -> Collaborator:
    pessoa = Person(name=nome, email=email)
    session.add(pessoa)
    session.flush()
    colaborador = Collaborator(person_id=pessoa.id, general_profile="Membro", bond="Timenow")
    session.add(colaborador)
    session.flush()
    return colaborador


def _projeto(
    session: Session,
    *,
    code: str = "TN-2026-014",
    ata: str | None = "TN-2026",
    risco: str | None = "RSK-TN-2026",
    punch: str | None = "PL-TN-2026",
) -> Project:
    cliente = Client(name=f"Cliente {code}", active=True)
    gerente = Person(name=f"Gerente {code}", email=f"gerente-{code.lower()}@example.invalid")
    session.add_all([cliente, gerente])
    session.flush()
    projeto = Project(
        client_id=cliente.id,
        manager_id=gerente.id,
        code=code,
        name=f"Projeto {code}",
        ata_pattern=ata,
        risk_pattern=risco,
        punch_pattern=punch,
    )
    session.add(projeto)
    session.flush()
    return projeto


# ── Atomicidade ──────────────────────────────────────────────────────────


def test_falha_no_meio_de_duas_gravacoes_nao_deixa_nenhuma() -> None:
    with database.new_session() as session:
        antes = session.scalar(select(func.count()).select_from(Client))

    with pytest.raises(ForcedFailureError), database.unidade_de_trabalho() as session:
        session.add(Client(name="Cliente A", active=True))
        session.add(Client(name="Cliente B", active=True))
        session.flush()
        raise ForcedFailureError

    with database.new_session() as session:
        depois = session.scalar(select(func.count()).select_from(Client))
    assert depois == antes


# ── Trilha ───────────────────────────────────────────────────────────────


def test_gravacao_deixa_trilha_com_antes_e_depois_na_mesma_transacao(db_session: Session) -> None:
    autor = _colaborador(db_session)
    cliente = recording.create(
        db_session, user_id=autor.id, record=Client(name="Cliente A", active=True)
    )
    recording.update(
        db_session,
        user_id=autor.id,
        record=cliente,
        changes={"name": "Cliente B"},
        version=1,
    )

    linhas = db_session.scalars(
        select(AuditEntry)
        .where(AuditEntry.entity == "cliente", AuditEntry.record_id == cliente.id)
        .order_by(AuditEntry.id)
    ).all()
    assert [linha.action for linha in linhas] == ["criado", "alterado"]
    assert linhas[0].before is None
    assert linhas[0].after["nome"] == "Cliente A"
    assert linhas[0].project_id is None
    assert linhas[1].before["nome"] == "Cliente A"
    assert linhas[1].after["nome"] == "Cliente B"
    assert linhas[1].user_id == autor.id

    cliente_id = cliente.id
    db_session.rollback()
    assert (
        db_session.scalar(select(func.count()).select_from(Client).where(Client.id == cliente_id))
        == 0
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(AuditEntry).where(AuditEntry.record_id == cliente_id)
        )
        == 0
    )


def test_trilha_recusa_alteracao(db_session: Session) -> None:
    autor = _colaborador(db_session)
    recording.create(db_session, user_id=autor.id, record=Client(name="Cliente", active=True))

    with pytest.raises(SQLAlchemyError):
        db_session.execute(text("UPDATE auditoria SET acao = 'mudou'"))
    db_session.rollback()


def test_trilha_recusa_exclusao(db_session: Session) -> None:
    autor = _colaborador(db_session)
    recording.create(db_session, user_id=autor.id, record=Client(name="Cliente", active=True))

    with pytest.raises(SQLAlchemyError):
        db_session.execute(text("DELETE FROM auditoria"))
    db_session.rollback()


# ── Controle de edição simultânea ────────────────────────────────────────


def test_gravacao_com_versao_antiga_e_recusada_com_autor_e_hora(db_session: Session) -> None:
    autor = _colaborador(db_session, nome="Ana Souza")
    cliente = recording.create(
        db_session, user_id=autor.id, record=Client(name="Cliente A", active=True)
    )
    recording.update(
        db_session,
        user_id=autor.id,
        record=cliente,
        changes={"name": "Cliente B"},
        version=1,
    )

    with pytest.raises(VersionConflictError) as recusa:
        recording.update(
            db_session,
            user_id=autor.id,
            record=cliente,
            changes={"name": "Cliente C"},
            version=1,
        )

    mensagem = str(recusa.value)
    assert "Ana Souza" in mensagem
    assert "Recarregue para ver a versão atual" in mensagem
    assert re.search(r"às \d{2}/\d{2}/\d{4} \d{2}:\d{2}", mensagem)
    assert cliente.name == "Cliente B"
    assert cliente.version == 2


# ── Dinheiro ─────────────────────────────────────────────────────────────


def test_tipo_de_dinheiro_guarda_centavos_e_formata_so_na_apresentacao(db_session: Session) -> None:
    projeto = _projeto(db_session)
    projeto.budget_cents = 123456
    db_session.flush()

    guardado = db_session.execute(
        text("SELECT orcamento_centavos FROM projeto WHERE id = :id"), {"id": projeto.id}
    ).scalar_one()
    assert guardado == 123456
    assert projeto.budget_cents == 123456
    assert money.format_brl(projeto.budget_cents) == "R$ 1.234,56"
    assert money.format_brl(-123456) == "-R$ 1.234,56"
    assert money.format_brl(None) == ""


# ── Numeração ────────────────────────────────────────────────────────────


def test_numeracao_segue_o_padrao_do_projeto(db_session: Session) -> None:
    projeto = _projeto(db_session)
    data = date(2026, 10, 5)
    esperados = {
        "ata": "TN-2026-0001",
        "mudanca": "SM-TN-2026-0001",
        "risco": "RSK-TN-2026-0001",
        "punch": "PL-TN-2026-0001",
        "rnc": "RNC-TN-2026-0001",
        "claim": "CLM-TN-2026-0001",
        "eot": "EOT-TN-2026-0001",
        "licao": "LA-TN-2026-0001",
        "pedido": "PED-2026-001",
        "contrato": "CT-2026-001",
    }
    for kind, esperado in esperados.items():
        numero = numbering.next_number(db_session, project=projeto, kind=kind, reference_date=data)
        assert numero == esperado

    proximo = numbering.next_number(
        db_session, project=projeto, kind="mudanca", reference_date=data
    )
    assert proximo == "SM-TN-2026-0002"


def test_numeracao_usa_o_fallback_quando_o_projeto_nao_tem_padrao(db_session: Session) -> None:
    projeto = _projeto(db_session, code="TN-2026-021", ata=None, risco=None, punch=None)
    data = date(2026, 10, 5)
    ata = numbering.next_number(db_session, project=projeto, kind="ata", reference_date=data)
    risco = numbering.next_number(db_session, project=projeto, kind="risco", reference_date=data)
    punch = numbering.next_number(db_session, project=projeto, kind="punch", reference_date=data)
    assert ata == "TN-2026-0001"
    assert risco == "RSK-0001"
    assert punch == "PL-0001"


def test_numero_reservado_e_devolvido_quando_a_transacao_desfaz() -> None:
    code = "TN-2026-030"
    with database.unidade_de_trabalho() as session:
        projeto = _projeto(session, code=code)
        project_id = projeto.id
    try:
        with pytest.raises(ForcedFailureError), database.unidade_de_trabalho() as session:
            projeto = session.get(Project, project_id)
            numero = numbering.next_number(
                session, project=projeto, kind="rnc", reference_date=date(2026, 10, 5)
            )
            assert numero == "RNC-TN-2026-0001"
            raise ForcedFailureError

        with database.unidade_de_trabalho() as session:
            projeto = session.get(Project, project_id)
            numero = numbering.next_number(
                session, project=projeto, kind="rnc", reference_date=date(2026, 10, 5)
            )
            assert numero == "RNC-TN-2026-0001"  # devolvido: sem buraco por concorrência
    finally:
        with database.get_engine().begin() as connection:
            connection.execute(
                text("DELETE FROM sequencia_numeracao WHERE projeto_id = :p"), {"p": project_id}
            )
            connection.execute(text("DELETE FROM projeto WHERE id = :p"), {"p": project_id})
            connection.execute(
                text("DELETE FROM pessoa WHERE email = :e"),
                {"e": f"gerente-{code.lower()}@example.invalid"},
            )
            connection.execute(
                text("DELETE FROM cliente WHERE nome = :n"), {"n": f"Cliente {code}"}
            )
