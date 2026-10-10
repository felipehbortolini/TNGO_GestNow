"""Apoio dos testes da Qualidade: o cenário da RNC (projetos, pessoas, parâmetros e cadastros).

O cenário vive na transação do teste: dois projetos, um colaborador de cada perfil (Admin,
Gestor, Membro e Visualizador), a versão 1 dos parâmetros (o grupo Qualidade traz os prazos e a
espera da verificação), uma disciplina e uma empresa do cadastro. As entradas de partida são uma
abertura, uma análise e uma verificação completas, para os testes mudarem só o que importa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Company, Discipline, Project
from src.modulos.qualidade.validation import (
    ActionInput,
    AnalysisInput,
    OpeningInput,
    VerificationInput,
)
from tests.identidades import criar_colaborador, criar_projeto

REFERENCIA = date(2026, 9, 25)
DISCIPLINA = "Mecânica"
EMPRESA = "Gama Válvulas"
ADA = "ada.admin@qualidade.example.invalid"
GIL = "gil.gestor@qualidade.example.invalid"
MARIO = "mario.membro@qualidade.example.invalid"
VERA = "vera.visualizadora@qualidade.example.invalid"


@dataclass(frozen=True)
class Cenario:
    """Dois projetos, as pessoas do teste e a disciplina e a empresa de partida."""

    projeto: Project
    outro: Project
    ada: User
    gil: User
    mario: User
    vera: User
    disciplina: Discipline
    empresa: Company


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
    """Cria projetos, colaboradores, parâmetros, disciplina e empresa na transação do teste."""
    projeto = criar_projeto(session, codigo="TN-RNC-001", nome="Fábrica de teste")
    outro = criar_projeto(session, codigo="TN-RNC-002", nome="Caldeira de teste")
    disciplina = Discipline(name=DISCIPLINA)
    empresa = Company(name=EMPRESA, kind="Contratada")
    session.add_all([disciplina, empresa])
    session.flush()
    ada = usuario_de(
        session, criar_colaborador(session, email=ADA, nome="Ada Admin", perfil="Admin")
    )
    gil = usuario_de(
        session, criar_colaborador(session, email=GIL, nome="Gil Gestor", perfil="Gestor")
    )
    mario = usuario_de(session, criar_colaborador(session, email=MARIO, nome="Mário Membro"))
    vera = usuario_de(
        session,
        criar_colaborador(session, email=VERA, nome="Vera Visualizadora", perfil="Visualizador"),
    )
    configuracoes.seed_initial_parameters(session, author_id=gil.id, effective_from=REFERENCIA)
    return Cenario(
        projeto=projeto,
        outro=outro,
        ada=ada,
        gil=gil,
        mario=mario,
        vera=vera,
        disciplina=disciplina,
        empresa=empresa,
    )


def nova_abertura(cenario: Cenario, **campos: object) -> OpeningInput:
    """Uma abertura de partida no projeto 1: origem Inspeção, severidade Maior, sem referência."""
    base = OpeningInput(
        project_id=cenario.projeto.id,
        rnc_date=REFERENCIA,
        origin="Inspeção",
        origin_ref="INS-2026-0001",
        discipline=DISCIPLINA,
        company_id=cenario.empresa.id,
        severity="Maior",
        description="Seis juntas soldadas da linha 310-P-014 reprovadas no ultrassom.",
        containment="Linha bloqueada para o teste hidrostático; soldador afastado da frente.",
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def nova_analise(**campos: object) -> AnalysisInput:
    """Uma análise de partida: 5 porquês, retrabalho e uma ação corretiva para dez dias."""
    base = AnalysisInput(
        method="5 porquês",
        root_cause="Soldador sem qualificação para o processo e a espessura da junta.",
        disposition="Retrabalho",
        actions=(
            ActionInput(
                subject="Refazer as soldas reprovadas da linha 310-P-014",
                responsible_id=None,
                planned_date=REFERENCIA + timedelta(days=10),
                description="Requalificar o soldador antes do retrabalho.",
            ),
        ),
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def nova_verificacao(**campos: object) -> VerificationInput:
    """Uma verificação de partida: eficaz, com evidência, na data de referência."""
    base = VerificationInput(
        effective=True,
        text="Dez soldas seguintes aprovadas no ultrassom; soldador requalificado no processo.",
        checked_on=REFERENCIA,
    )
    return replace(base, **campos)  # type: ignore[arg-type]
