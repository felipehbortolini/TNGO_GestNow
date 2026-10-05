"""Identidades de teste: colaboradores do cadastro e o principal do Static Web Apps.

Os testes de acesso (login, perfis, papéis por projeto, vínculo e seletor da
demonstração) criam as pessoas de que precisam dentro da transação do teste e
montam a requisição como o Azure a entregaria: com o cabeçalho
``x-ms-client-principal`` (base64 de um JSON) ou, na demonstração, com o cookie
do seletor de perfil.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable, Mapping
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE, PRINCIPAL_HEADER
from src.core.models import Client
from src.modulos.configuracoes.models import (
    Collaborator,
    CollaboratorScheduleRole,
    Company,
    Person,
    Project,
)


def criar_empresa(session: Session, nome: str = "Empresa de teste") -> Company:
    """A company of the register, for the supplier bond."""
    empresa = Company(name=nome, kind="Contratada")
    session.add(empresa)
    session.flush()
    return empresa


def criar_projeto(session: Session, *, codigo: str, nome: str) -> Project:
    """A project of the register, with the client and manager it requires.

    The roles of the Weekly Scheduling are given per project, so the access
    tests need real projects to point them at.
    """
    cliente = Client(name=f"Cliente {codigo}", active=True)
    gerente = Person(name=f"Gerente {codigo}", email=f"gerente-{codigo.lower()}@example.invalid")
    session.add_all([cliente, gerente])
    session.flush()
    projeto = Project(client_id=cliente.id, manager_id=gerente.id, code=codigo, name=nome)
    session.add(projeto)
    session.flush()
    return projeto


def criar_colaborador(
    session: Session,
    *,
    email: str,
    nome: str | None = None,
    perfil: str = "Membro",
    vinculo: str = "Timenow",
    empresa: Company | None = None,
    ativo: bool = True,
    papeis: Iterable[tuple[int, str]] = (),
) -> Collaborator:
    """A person and the collaborator that gives it access, inside the test transaction.

    ``papeis`` are ``(project_id, role)`` pairs of the Weekly Scheduling.
    """
    pessoa = Person(
        name=nome or email.split("@")[0],
        email=email,
        company_id=empresa.id if empresa is not None else None,
    )
    session.add(pessoa)
    session.flush()
    colaborador = Collaborator(
        person_id=pessoa.id,
        company_id=empresa.id if empresa is not None else None,
        general_profile=perfil,
        bond=vinculo,
        active=ativo,
    )
    session.add(colaborador)
    session.flush()
    for projeto_id, papel in papeis:
        session.add(
            CollaboratorScheduleRole(
                collaborator_id=colaborador.id, project_id=projeto_id, role=papel
            )
        )
    session.flush()
    return colaborador


def cabecalho_do_principal(email: str | None, *, provedor: str = "aad") -> str:
    """The value of ``x-ms-client-principal`` as Static Web Apps sends it: base64 of a JSON."""
    principal = {
        "identityProvider": provedor,
        "userId": "00000000000000000000000000000000",
        "userDetails": email,
        "userRoles": ["anonymous", "authenticated"],
    }
    return base64.b64encode(json.dumps(principal).encode()).decode()


def requisicao(
    caminho: str = "/api/nav",
    *,
    metodo: str = "GET",
    email: str | None = None,
    cabecalho_bruto: str | None = None,
    cookies: Mapping[str, str] | None = None,
    alvo: str = "main-nav module-tabs",
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, str] | None = None,
) -> func.HttpRequest:
    """A request as the shell sends it, with the principal of ``email`` when informed.

    ``cabecalho_bruto`` replaces the principal header with any text, to test
    what a malformed header does.
    """
    headers = {"X-Alpine-Request": "true", "X-Alpine-Target": alvo}
    if cabecalho_bruto is not None:
        headers[PRINCIPAL_HEADER] = cabecalho_bruto
    elif email is not None:
        headers[PRINCIPAL_HEADER] = cabecalho_do_principal(email)
    if cookies:
        headers["Cookie"] = "; ".join(f"{nome}={valor}" for nome, valor in cookies.items())
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url=caminho,
        headers=headers,
        params=dict(params or {}),
        route_params={},
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def cookie_do_seletor(colaborador: Collaborator) -> dict[str, str]:
    """The cookie the demonstration selector leaves for the collaborator."""
    return {DEMO_COOKIE: str(colaborador.id)}
