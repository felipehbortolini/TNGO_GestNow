"""Apoio dos testes do HSE: o cenário (projetos, empresas e pessoas) e os registros de partida.

O cenário vive na transação do teste: dois projetos, duas empresas contratadas e um colaborador
de cada perfil (Admin, Gestor e Membro), com a versão 1 dos parâmetros. As identidades de partida
são um HHT e um fechamento mensal completos, para os testes mudarem só o que importa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Company, Project
from src.modulos.hse.validation import ClosingInput, HoursInput
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto

REFERENCIA = date(2026, 9, 25)
ADA = "ada.admin@hse.example.invalid"
GIL = "gil.gestor@hse.example.invalid"
MARIA = "maria.membro@hse.example.invalid"


@dataclass(frozen=True)
class Cenario:
    """Dois projetos, duas empresas e as pessoas do teste."""

    projeto: Project
    outro: Project
    alfa: Company
    beta: Company
    ada: User
    gil: User
    maria: User


def usuario_de(session: Session, colaborador: Collaborator) -> User:
    """O ``User`` que a plataforma monta para um colaborador do cadastro."""
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


def montar_cenario(session: Session) -> Cenario:
    """Cria projetos, empresas, colaboradores e os parâmetros dentro da transação do teste."""
    alfa = criar_empresa(session, "Alfa Montagens")
    beta = criar_empresa(session, "Beta Serviços")
    gil = usuario_de(
        session, criar_colaborador(session, email=GIL, nome="Gil Gestor", perfil="Gestor")
    )
    configuracoes.seed_initial_parameters(session, author_id=gil.id, effective_from=REFERENCIA)
    return Cenario(
        projeto=criar_projeto(session, codigo="TN-HSE-001", nome="Fábrica de teste"),
        outro=criar_projeto(session, codigo="TN-HSE-002", nome="Caldeira de teste"),
        alfa=alfa,
        beta=beta,
        ada=usuario_de(
            session, criar_colaborador(session, email=ADA, nome="Ada Admin", perfil="Admin")
        ),
        gil=gil,
        maria=usuario_de(session, criar_colaborador(session, email=MARIA, nome="Maria Membro")),
    )


def horas_de(cenario: Cenario, **campos: object) -> HoursInput:
    """Um HHT de partida: agosto de 2026 da Alfa, com 60 pessoas e 13.080 horas."""
    base = HoursInput(
        project_id=cenario.projeto.id,
        month=date(2026, 8, 1),
        company_id=cenario.alfa.id,
        headcount=60,
        hours=Decimal("13080"),
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def fechamento_de(cenario: Cenario, **campos: object) -> ClosingInput:
    """Um fechamento de partida: agosto de 2026, com DDS, itens, observações e desvios."""
    base = ClosingInput(
        project_id=cenario.projeto.id,
        month=date(2026, 8, 1),
        deviations=12,
        observations=30,
        planned_dds=22,
        held_dds=20,
        inspected_items=60,
        conforming_items=57,
    )
    return replace(base, **campos)  # type: ignore[arg-type]
