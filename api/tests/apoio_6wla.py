"""Apoio dos testes do 6WLA (ISSUE-045): cadastros mínimos, usuários e pedidos HTTP.

Os testes de fachada e de rota precisam do mesmo cenário pequeno: dois projetos, uma
empresa, pessoas com cada perfil e as disciplinas do cadastro. Tudo nasce dentro da
transação do teste e some no fim dela.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Company, Discipline, Person, Project
from src.modulos.planejamento import service, validation
from tests.identidades import (
    cabecalho_do_principal,
    criar_colaborador,
    criar_empresa,
    criar_projeto,
)

HOJE = date(2026, 9, 25)
DISCIPLINAS = ("Civil", "Mecânica", "Tubulação")
ALVO_DA_GRAVACAO = "lookahead-formulario lookahead-filtros lookahead-conteudo"


@dataclass(frozen=True)
class Cadastro:
    """O cenário mínimo: dois projetos, uma empresa e uma pessoa de cada perfil."""

    projeto: Project
    outro_projeto: Project
    empresa: Company
    responsavel: Person
    admin: Collaborator
    membro: Collaborator
    visualizador: Collaborator
    fornecedor: Collaborator

    def usuario(self, colaborador: Collaborator, perfil: GeneralProfile) -> User:
        """O ``User`` do colaborador, como o login o resolveria."""
        pessoa_id = colaborador.person_id
        return User(
            id=colaborador.id,
            person_id=pessoa_id,
            name="Pessoa de teste",
            email="pessoa@example.invalid",
            general_profile=perfil,
            bond=Bond.TIMENOW,
        )

    @property
    def usuario_membro(self) -> User:
        """O membro: pode gravar."""
        return self.usuario(self.membro, GeneralProfile.MEMBER)

    @property
    def usuario_visualizador(self) -> User:
        """O visualizador: só lê."""
        return self.usuario(self.visualizador, GeneralProfile.VIEWER)


def montar_cadastro(session: Session) -> Cadastro:
    """Cria o cenário mínimo dentro da transação do teste."""
    for nome in DISCIPLINAS:
        session.add(Discipline(name=nome))
    empresa = criar_empresa(session, "Montadora Alfa")
    projeto = criar_projeto(session, codigo="TN-TESTE-001", nome="Fábrica")
    outro = criar_projeto(session, codigo="TN-TESTE-002", nome="Caldeira")
    admin = criar_colaborador(session, email="admin-6wla@example.invalid", perfil="Admin")
    membro = criar_colaborador(
        session, email="membro-6wla@example.invalid", nome="Maria Responsável", perfil="Membro"
    )
    visualizador = criar_colaborador(
        session, email="visualizador-6wla@example.invalid", perfil="Visualizador"
    )
    fornecedor = criar_colaborador(
        session,
        email="fornecedor-6wla@example.invalid",
        perfil="Membro",
        vinculo="Fornecedor",
        empresa=empresa,
    )
    session.flush()
    responsavel = session.scalars(select(Person).where(Person.id == membro.person_id)).one()
    return Cadastro(projeto, outro, empresa, responsavel, admin, membro, visualizador, fornecedor)


def campos_da_atividade(
    cadastro: Cadastro, *, atividade: str = "Montagem da carcaça", semanas: Sequence[int] = (0, 1)
) -> validation.ActivityForm:
    """O formulário de atividade preenchido como a tela enviaria."""
    return validation.ActivityForm(
        fields={
            "atividade": atividade,
            "area": "Moagem 210",
            "disciplina": "Mecânica",
            "empresa": str(cadastro.empresa.id),
            "responsavel": str(cadastro.responsavel.id),
        },
        weeks=[str(semana) for semana in semanas],
    )


def campos_da_restricao(
    cadastro: Cadastro, atividade_id: int, *, necessaria: str = "2026-10-02"
) -> dict[str, str]:
    """O formulário de restrição preenchido como a tela enviaria."""
    return {
        "atividade": str(atividade_id),
        "tipo": "Material",
        "responsavel": str(cadastro.responsavel.id),
        "descricao": "Chegada do moinho",
        "necessaria": necessaria,
    }


def incluir_atividade(
    session: Session,
    cadastro: Cadastro,
    *,
    projeto: Project | None = None,
    atividade: str = "Montagem da carcaça",
    semanas: Sequence[int] = (0, 1),
) -> service.ActivityView:
    """Inclui uma atividade pela fachada e devolve como a grade a lê."""
    alvo = projeto or cadastro.projeto
    registro = service.create_activity(
        session,
        user=cadastro.usuario_membro,
        scope=Scope(project_id=alvo.id, source="url"),
        form=campos_da_atividade(cadastro, atividade=atividade, semanas=semanas),
    )
    return service.find_activity(
        session,
        scope=Scope(project_id=alvo.id, source="url"),
        activity_id=registro.id,
        reference_date=HOJE,
    )


@dataclass(frozen=True)
class Envio:
    """O que varia de um pedido para outro: método, campos do formulário, consulta e rota."""

    metodo: str = "GET"
    campos: Mapping[str, str] | Sequence[tuple[str, str]] | None = None
    params: Mapping[str, str] | None = None
    rota: Mapping[str, str] | None = None
    alvo: str = "lookahead-conteudo"
    alpine: bool = True


def pedido(caminho: str, *, email: str, envio: Envio | None = None) -> func.HttpRequest:
    """O pedido que o navegador (ou o botão de exportar) faria, com o principal do e-mail."""
    dados = envio or Envio()
    cabecalhos = {"x-ms-client-principal": cabecalho_do_principal(email)}
    if dados.alpine:
        cabecalhos["X-Alpine-Request"] = "true"
        cabecalhos["X-Alpine-Target"] = dados.alvo
    corpo = b""
    if dados.campos is not None:
        cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        pares = (
            list(dados.campos.items()) if isinstance(dados.campos, Mapping) else list(dados.campos)
        )
        corpo = urlencode(pares).encode()
    return func.HttpRequest(
        method=dados.metodo,
        url=caminho,
        headers=cabecalhos,
        params=dict(dados.params or {}),
        route_params=dict(dados.rota or {}),
        body=corpo,
    )
