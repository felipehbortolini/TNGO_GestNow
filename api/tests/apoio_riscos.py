"""Apoio dos testes do Registro de riscos: o cenário (projetos, pessoas, parâmetros e RBS).

O cenário vive na transação do teste: dois projetos, um colaborador de cada perfil (Admin,
Gestor, Membro e Visualizador), a versão 1 dos parâmetros (o grupo Riscos traz a escala Timenow
e as probabilidades) e três categorias da RBS. As identidades de partida são um risco e uma
avaliação completos, para os testes mudarem só o que importa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Project
from src.modulos.riscos.models import RiskCategory
from src.modulos.riscos.validation import AssessmentInput, RiskInput
from tests.identidades import criar_colaborador, criar_projeto

REFERENCIA = date(2026, 9, 25)
ADA = "ada.admin@riscos.example.invalid"
GIL = "gil.gestor@riscos.example.invalid"
MARIO = "mario.membro@riscos.example.invalid"
VERA = "vera.visualizadora@riscos.example.invalid"


@dataclass(frozen=True)
class Cenario:
    """Dois projetos, as pessoas do teste e a RBS de partida."""

    projeto: Project
    outro: Project
    ada: User
    gil: User
    mario: User
    vera: User
    categorias: tuple[RiskCategory, ...]


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
    """Cria projetos, colaboradores, parâmetros e categorias dentro da transação do teste."""
    projeto = criar_projeto(session, codigo="TN-RSK-001", nome="Fábrica de teste")
    outro = criar_projeto(session, codigo="TN-RSK-002", nome="Caldeira de teste")
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
    categorias = (
        RiskCategory(group="Técnico", name="Prazo"),
        RiskCategory(group="Técnico", name="Custo"),
        RiskCategory(group="Externo", name="Fornecedor"),
    )
    session.add_all(categorias)
    session.flush()
    return Cenario(
        projeto=projeto,
        outro=outro,
        ada=ada,
        gil=gil,
        mario=mario,
        vera=vera,
        categorias=tuple(categorias),
    )


def novo_risco(cenario: Cenario, **campos: object) -> RiskInput:
    """Um risco de partida no projeto 1: ameaça de prazo com causa, evento e consequência."""
    base = RiskInput(
        nature="Ameaça",
        category_id=cenario.categorias[0].id,
        cause="Atraso na liberação dos desenhos de detalhamento.",
        title="Atraso na liberação dos desenhos",
        consequence="A montagem mecânica atrasa e o comissionamento escorrega.",
        owner_id=cenario.mario.person_id,
        identified_on=REFERENCIA,
        origin_type="Manual",
        description="",
        trigger="",
        project_id=cenario.projeto.id,
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def nova_avaliacao(**campos: object) -> AssessmentInput:
    """Uma avaliação inerente de partida: P3, pior dimensão 4 (prazo) e custo de R$ 1 mi."""
    base = AssessmentInput(
        kind="inerente",
        probability=3,
        impact=4,
        dimensions={
            "prazo": 4,
            "custo": 2,
            "escopo": None,
            "sms": None,
            "imagem": None,
            "legal": None,
        },
        schedule_impact_days=10,
        cost_impact_cents=100_000_000,
        life_risk=False,
        justification="",
    )
    return replace(base, **campos)  # type: ignore[arg-type]
