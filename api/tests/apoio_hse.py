"""Apoio dos testes do HSE: o cenário (projetos, empresas e pessoas) e os registros de partida.

O cenário vive na transação do teste: dois projetos, duas empresas contratadas e um colaborador
de cada perfil (Admin, Gestor e Membro), com a versão 1 dos parâmetros. As identidades de partida
são um HHT, um fechamento mensal e uma ocorrência completos, para os testes mudarem só o que
importa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Company, Project
from src.modulos.hse.validation import (
    ClosingInput,
    ClosureInput,
    CorrectiveActionInput,
    HoursInput,
    InvestigationInput,
    OccurrenceInput,
)
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


def ocorrencia_de(cenario: Cenario, **campos: object) -> OccurrenceInput:
    """Uma ocorrência de partida: hoje, Quase acidente na Alfa, potencial 3 x 4, comunicação em 2 h."""
    base = OccurrenceInput(
        project_id=cenario.projeto.id,
        happened_on=REFERENCIA,
        happened_time="09:30",
        area="Moagem 210",
        company_id=cenario.alfa.id,
        kind="Quase acidente",
        description="Ferramenta caiu de 6 m sem amarração na área de circulação.",
        people_involved=0,
        potential_p=3,
        potential_i=4,
        immediate_cause="Procedimento não seguido",
        communication_hours=2,
        name="João da Silva",
        real_gravity=1,
        days_lost=0,
        days_charged=0,
        cat=False,
        medical_notes="Sem lesão; avaliação no ambulatório.",
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def investigacao_de(**campos: object) -> InvestigationInput:
    """Uma investigação de partida: 5 porquês, hoje, com a causa raiz do cenário."""
    base = InvestigationInput(
        method="5 porquês",
        root_cause="Ferramenta sem amarração durante o trabalho em altura.",
        investigated_on=REFERENCIA,
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def acao_de(cenario: Cenario, **campos: object) -> CorrectiveActionInput:
    """Uma ação corretiva de partida: amarração de ferramentas, responsável o Gestor, prevista hoje."""
    base = CorrectiveActionInput(
        subject="Amarração de ferramentas em trabalho em altura",
        responsible_id=cenario.gil.person_id,
        planned_date=REFERENCIA,
        description="Talabartes de ferramenta e inspeção diária nas frentes de altura.",
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def encerramento_de(**campos: object) -> ClosureInput:
    """Um encerramento de partida: eficácia verificada hoje, sem a lição (o HiPo a exige)."""
    base = ClosureInput(
        effectiveness="Inspeções diárias seguidas sem reincidência do desvio.",
        closed_on=REFERENCIA,
    )
    return replace(base, **campos)  # type: ignore[arg-type]
