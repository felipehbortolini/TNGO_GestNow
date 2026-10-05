"""Fachada de Configurações: o que o gate lê do cadastro de Colaboradores (ISSUE-011, D7).

O cadastro é a fonte de verdade do acesso. A fachada entrega o colaborador de um
e-mail (sem diferenciar maiúsculas), o de um id, e a lista dos ativos, com perfil
geral, vínculo, empresa e os papéis da Programação Semanal por projeto, tudo como
o cadastro guarda. Costura da fachada, com o banco de teste e a transação
desfeita no fim de cada teste.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.modulos.configuracoes import service
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto


def test_colaborador_do_email_vem_com_perfil_vinculo_e_empresa(db_session: Session) -> None:
    empresa = criar_empresa(db_session)
    criado = criar_colaborador(
        db_session,
        email="Carlos.Nunes@Exemplo.com",
        nome="Carlos Nunes",
        perfil="Membro",
        vinculo="Fornecedor",
        empresa=empresa,
    )

    acesso = service.find_access_by_email(db_session, "  CARLOS.NUNES@exemplo.com ")

    assert acesso == service.CollaboratorAccess(
        id=criado.id,
        person_id=criado.person_id,
        name="Carlos Nunes",
        email="Carlos.Nunes@Exemplo.com",
        general_profile="Membro",
        bond="Fornecedor",
        company_id=empresa.id,
        active=True,
        schedule_roles=(),
    )


def test_email_fora_do_cadastro_nao_tem_colaborador(db_session: Session) -> None:
    criar_colaborador(db_session, email="alguem@example.invalid")

    assert service.find_access_by_email(db_session, "outro@example.invalid") is None
    assert service.find_access(db_session, 987654321) is None


def test_colaborador_desativado_continua_na_fachada_marcado_como_inativo(
    db_session: Session,
) -> None:
    criado = criar_colaborador(db_session, email="desligado@example.invalid", ativo=False)

    por_email = service.find_access_by_email(db_session, "desligado@example.invalid")
    por_id = service.find_access(db_session, criado.id)

    assert por_email is not None
    assert por_email.active is False
    assert por_id == por_email


def test_papeis_da_programacao_semanal_vem_por_projeto_em_ordem(db_session: Session) -> None:
    fabrica = criar_projeto(db_session, codigo="TN-ACESSO-001", nome="Projeto do acesso")
    caldeira = criar_projeto(db_session, codigo="TN-ACESSO-002", nome="Outro projeto")
    criado = criar_colaborador(
        db_session,
        email="papeis@example.invalid",
        papeis=[
            (caldeira.id, "Fiscal"),
            (fabrica.id, "Planejador"),
            (fabrica.id, "Encarregado"),
        ],
    )

    acesso = service.find_access(db_session, criado.id)

    assert acesso is not None
    assert acesso.schedule_roles == (
        (fabrica.id, "Encarregado"),
        (fabrica.id, "Planejador"),
        (caldeira.id, "Fiscal"),
    )


def test_colaborador_sem_papel_nenhum_traz_a_lista_vazia(db_session: Session) -> None:
    criado = criar_colaborador(db_session, email="sem.papel@example.invalid")

    acesso = service.find_access(db_session, criado.id)

    assert acesso is not None
    assert acesso.schedule_roles == ()


def test_lista_dos_ativos_exclui_os_desativados_e_segue_a_ordem_do_cadastro(
    db_session: Session,
) -> None:
    primeiro = criar_colaborador(db_session, email="primeiro@example.invalid")
    criar_colaborador(db_session, email="inativo@example.invalid", ativo=False)
    segundo = criar_colaborador(db_session, email="segundo@example.invalid")

    ids = [acesso.id for acesso in service.list_active_access(db_session)]

    assert primeiro.id in ids
    assert segundo.id in ids
    assert ids.index(primeiro.id) < ids.index(segundo.id)
    assert all(acesso.active for acesso in service.list_active_access(db_session))


@pytest.mark.parametrize("email", ["", "   "])
def test_email_em_branco_nao_acha_ninguem(db_session: Session, email: str) -> None:
    criar_colaborador(db_session, email="alguem@example.invalid")

    assert service.find_access_by_email(db_session, email) is None
