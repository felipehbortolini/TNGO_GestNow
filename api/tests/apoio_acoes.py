"""Apoio dos testes da Central de Ações: o cenário (projetos e pessoas) e uma ação de partida.

O cenário vive na transação do teste: dois projetos e cinco colaboradores, um de cada perfil
(Admin, Gestor, Membro, Visualizador) mais um Fornecedor, cada um com a pessoa do cadastro que
as ações apontam como solicitante e responsável.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.central_acoes.calculations import ACTION
from src.modulos.central_acoes.validation import NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Project
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto

REFERENCIA = date(2026, 9, 25)
ADA = "ada.admin@acoes.example.invalid"
GIL = "gil.gestor@acoes.example.invalid"
MARIO = "mario.membro@acoes.example.invalid"
VERA = "vera.visualizadora@acoes.example.invalid"
FABIO = "fabio.fornecedor@acoes.example.invalid"


def usuario_de(session: Session, colaborador: Collaborator) -> User:
    """The ``User`` the platform builds for a collaborator of the register."""
    acesso = configuracoes.find_access(session, colaborador.id)
    if acesso is None:
        message = f"Colaborador {colaborador.id} fora do cadastro."
        raise LookupError(message)
    return User(
        id=acesso.id,
        person_id=acesso.person_id,
        name=acesso.name,
        email=acesso.email,
        general_profile=GeneralProfile(acesso.general_profile),
        bond=Bond(acesso.bond),
        company_id=acesso.company_id,
    )


@dataclass(frozen=True)
class Cenario:
    """Dois projetos e as pessoas do teste, cada uma como colaborador e como ``User``."""

    projeto_a: Project
    projeto_b: Project
    ada: User
    gil: User
    mario: User
    vera: User
    fabio: User


def montar_cenario(session: Session) -> Cenario:
    """Cria os projetos e os colaboradores do cenário, dentro da transação do teste."""
    empresa = criar_empresa(session, "Fornecedora de teste")
    return Cenario(
        projeto_a=criar_projeto(session, codigo="TN-ACAO-001", nome="Fábrica de teste"),
        projeto_b=criar_projeto(session, codigo="TN-ACAO-002", nome="Caldeira de teste"),
        ada=usuario_de(
            session, criar_colaborador(session, email=ADA, nome="Ada Admin", perfil="Admin")
        ),
        gil=usuario_de(
            session, criar_colaborador(session, email=GIL, nome="Gil Gestor", perfil="Gestor")
        ),
        mario=usuario_de(session, criar_colaborador(session, email=MARIO, nome="Mário Membro")),
        vera=usuario_de(
            session,
            criar_colaborador(
                session, email=VERA, nome="Vera Visualizadora", perfil="Visualizador"
            ),
        ),
        fabio=usuario_de(
            session,
            criar_colaborador(
                session, email=FABIO, nome="Fábio Fornecedor", vinculo="Fornecedor", empresa=empresa
            ),
        ),
    )


def nova_acao(cenario: Cenario, **campos: object) -> NewAction:
    """Uma ação de partida: origem Risco no projeto A, prevista 10 dias depois da referência."""
    base = NewAction(
        project_id=cenario.projeto_a.id,
        origin="Risco",
        origin_ref="RSK-TESTE-0001",
        subject="Protocolar o programa de monitoramento",
        requester_id=cenario.mario.person_id,
        responsible_id=cenario.gil.person_id,
        planned_date=REFERENCIA + timedelta(days=10),
        kind=ACTION,
        description="Condicionante da licença de operação.",
        group="Plano de resposta",
    )
    return replace(base, **campos)  # type: ignore[arg-type]
