"""Apoio dos testes de Governança: projetos com orçamento, pessoas e a solicitação válida."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Project
from src.modulos.governanca import models, service
from tests.identidades import criar_colaborador, criar_projeto

HOJE = date(2026, 10, 6)
ORCAMENTO = 4_460_000_000

MEMBRO = "marina.membro@example.invalid"
OUTRO_MEMBRO = "otavio.membro@example.invalid"
GESTOR = "gabriel.gestor@example.invalid"
VISUALIZADOR = "vera.visualizadora@example.invalid"
FORNECEDOR = "fabio.fornecedor@example.invalid"


def projeto_com_orcamento(
    session: Session, *, codigo: str = "TN-2026-014", padrao: str = "TN-2026"
) -> Project:
    """Um projeto com o padrão de numeração e o orçamento do projeto da demonstração."""
    projeto = criar_projeto(session, codigo=codigo, nome=f"Projeto {codigo}")
    projeto.ata_pattern = padrao
    projeto.budget_cents = ORCAMENTO
    session.flush()
    return projeto


def usuario_de(colaborador: Collaborator, *, nome: str = "Pessoa de teste") -> User:
    """O ``User`` do colaborador, como o login o resolveria."""
    return User(
        id=colaborador.id,
        person_id=colaborador.person_id,
        name=nome,
        email=f"{colaborador.id}@example.invalid",
        general_profile=GeneralProfile(colaborador.general_profile),
        bond=Bond(colaborador.bond),
    )


def colaborador(session: Session, email: str, perfil: str = "Membro") -> Collaborator:
    """Um colaborador do cadastro com o perfil geral."""
    return criar_colaborador(session, email=email, nome=email.split("@")[0], perfil=perfil)


def escopo_do_projeto(projeto: Project) -> Scope:
    """O escopo de um projeto."""
    return Scope(project_id=projeto.id, source="url")


PORTFOLIO = Scope(project_id=None, source="padrao")


def solicitacao_valida(**mudancas: str) -> dict[str, str]:
    """O formulário de uma solicitação que passa em todas as regras; ``mudancas`` troca campos."""
    campos = {
        "titulo": "Inclusão do sistema de tratamento",
        "tipo": "Escopo",
        "origem": "Cliente",
        "prioridade": "Normal",
        "data_solicitacao": HOJE.isoformat(),
        "descricao": "Exigência do órgão ambiental para a licença de operação.",
    }
    campos.update(mudancas)
    return campos


def registrar(
    session: Session, usuario: User, projeto: Project, **mudancas: str
) -> service.CreatedChange:
    """Registra uma solicitação válida no projeto pela fachada."""
    return service.create_change(
        session,
        user=usuario,
        scope=escopo_do_projeto(projeto),
        form=solicitacao_valida(**mudancas),
        reference_date=HOJE,
    )


def semente(
    projeto: Project, pessoa_id: int, codigo: str, situacao: str, **mudancas: object
) -> service.SeedChange:
    """Uma SM da demonstração na situação pedida, para os testes que partem de uma SM já andada."""
    base = {
        "project_id": projeto.id,
        "code": codigo,
        "requester_person_id": pessoa_id,
        "title": "Solicitação da demonstração",
        "kind": "Escopo",
        "origin": "Cliente",
        "priority": "Normal",
        "request_date": date(2026, 9, 1),
        "description": "Descrição da solicitação da demonstração.",
        "situation": situacao,
    }
    base.update(mudancas)
    return service.SeedChange(**base)  # type: ignore[arg-type]


SITUACOES_ABERTAS_ANTES_DA_DECISAO = (
    models.SITUATION_REGISTERED,
    models.SITUATION_ANALYSIS,
    models.SITUATION_AWAITING,
    models.SITUATION_POSTPONED,
)
