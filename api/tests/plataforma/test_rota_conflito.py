"""Costura HTTP da gravação segura: 409 com o formulário preenchido, 422, 403 e o gate.

O decorador único de rota (``fragment_route``) é o dono da transação e do
mapa de erros. O formulário de teste faz o papel do formulário de um
módulo: no 409 ele volta com o que a pessoa digitou e com a mensagem que
nomeia quem gravou antes.

A trilha é só de inclusão: as linhas de auditoria gravadas aqui ficam no
``gestnow_teste`` até a próxima execução do pytest, que recria o schema.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

import azure.functions as func
import pytest
from jinja2 import FileSystemLoader
from sqlalchemy import text

from src.core import database, recording
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.jinja_env import jinja_env
from src.core.models import Client
from src.core.responses import AlpineAjaxResponse
from src.core.routing import fragment_route
from src.modulos.configuracoes.models import Collaborator, Person

TEMPLATES_DA_API = Path(__file__).resolve().parents[2] / "src" / "templates"
TEMPLATES_DO_TESTE = Path(__file__).resolve().parent / "templates"
EMAIL_DO_AUTOR = "rota-409@example.invalid"


@pytest.fixture
def formulario_do_teste(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adds the test form template to the Jinja loader, after the app's templates."""
    loader = FileSystemLoader([str(TEMPLATES_DA_API), str(TEMPLATES_DO_TESTE)])
    monkeypatch.setattr(jinja_env, "loader", loader)


def _requisicao(**campos: str) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/teste",
        headers={
            "X-Alpine-Request": "true",
            "X-Alpine-Target": "formulario",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        params={},
        route_params={},
        body=urlencode(campos).encode(),
    )


def _cliente_com_duas_versoes() -> tuple[int, int]:
    """A committed record already at version 2, changed by Ana Souza."""
    with database.unidade_de_trabalho() as session:
        pessoa = Person(name="Ana Souza", email=EMAIL_DO_AUTOR)
        session.add(pessoa)
        session.flush()
        autor = Collaborator(person_id=pessoa.id, general_profile="Membro", bond="Timenow")
        session.add(autor)
        session.flush()
        cliente = recording.create(
            session, user_id=autor.id, record=Client(name="Cliente A", active=True)
        )
        recording.update(
            session,
            user_id=autor.id,
            record=cliente,
            changes={"name": "Cliente B"},
            version=1,
        )
        return cliente.id, autor.id


def _limpar(cliente_id: int) -> None:
    with database.get_engine().begin() as connection:
        connection.execute(text("DELETE FROM cliente WHERE id = :id"), {"id": cliente_id})


@pytest.mark.usefixtures("formulario_do_teste")
def test_rota_devolve_409_com_formulario_preenchido() -> None:
    cliente_id, autor_id = _cliente_com_duas_versoes()

    def renderizar_formulario(req: func.HttpRequest, erro: DomainError) -> func.HttpResponse | None:
        if not isinstance(erro, VersionConflictError):
            return None
        return AlpineAjaxResponse(
            template_name="formulario.html",
            context={
                "valores": {
                    "nome": req.form.get("nome") or "",
                    "versao": req.form.get("versao") or "",
                },
                "mensagem": str(erro),
            },
            request=req,
            status_code=409,
            toast=str(erro),
            toast_tipo="erro",
        )

    @fragment_route(on_error=renderizar_formulario)
    def salvar(req: func.HttpRequest, session) -> func.HttpResponse:
        cliente = session.get(Client, cliente_id)
        recording.update(
            session,
            user_id=autor_id,
            record=cliente,
            changes={"name": req.form.get("nome") or ""},
            version=req.form.get("versao"),
        )
        return AlpineAjaxResponse(template_name="formulario.html", context={}, request=req)

    try:
        resposta = salvar(_requisicao(nome="Cliente digitado", versao="1"))
    finally:
        _limpar(cliente_id)

    assert resposta.status_code == 409
    corpo = resposta.get_body().decode()
    assert "Ana Souza" in corpo
    assert re.search(r"às \d{2}/\d{2}/\d{4} \d{2}:\d{2}", corpo)
    assert 'value="Cliente digitado"' in corpo
    assert resposta.headers.get("X-TN-Toast")


def test_rota_devolve_422_com_o_erro_comum() -> None:
    @fragment_route
    def salvar(_req: func.HttpRequest, _session) -> func.HttpResponse:
        raise InvalidDataError({"nome": "Informe o nome."})

    resposta = salvar(_requisicao(nome="", versao="1"))

    assert resposta.status_code == 422
    assert "Informe o nome." in resposta.get_body().decode()


def test_rota_devolve_403_quando_o_acesso_e_recusado() -> None:
    @fragment_route
    def salvar(_req: func.HttpRequest, _session) -> func.HttpResponse:
        raise AccessDeniedError

    resposta = salvar(_requisicao())

    assert resposta.status_code == 403
    assert "Seu perfil não permite esta operação." in resposta.get_body().decode()


def test_rota_sem_alpine_redireciona_para_o_shell() -> None:
    chamou: list[bool] = []

    @fragment_route
    def listar(_req: func.HttpRequest, _session) -> func.HttpResponse:
        chamou.append(True)
        return func.HttpResponse("ok")

    requisicao = func.HttpRequest(
        method="GET", url="/api/teste", headers={}, params={}, route_params={}, body=b""
    )
    resposta = listar(requisicao)

    assert resposta.status_code == 302
    assert resposta.headers.get("Location") == "/index.html"
    assert chamou == []
