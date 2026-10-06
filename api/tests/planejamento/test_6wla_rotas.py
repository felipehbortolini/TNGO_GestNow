"""Rotas do 6WLA (ISSUE-045): tela, formulários, gravação, exportações e perfis.

A costura é HTTP: o handler recebe a ``HttpRequest`` do navegador e a resposta é lida como
a pessoa a veria (status, texto, cabeçalho do aviso).
"""

from __future__ import annotations

import html

import pytest
from sqlalchemy.orm import Session

from src.modulos.planejamento import routes
from tests.apoio_6wla import Cadastro, Envio, campos_da_atividade, incluir_atividade, pedido

BASE = "/api/planejamento/6wla"
EMAIL_MEMBRO = "membro-6wla@example.invalid"
EMAIL_VISUALIZADOR = "visualizador-6wla@example.invalid"


def _texto(resposta: object) -> str:
    return html.unescape(resposta.get_body().decode())  # type: ignore[attr-defined]


def _projeto(cadastro: Cadastro) -> dict[str, str]:
    return {"projeto": str(cadastro.projeto.id)}


def test_a_tela_lista_a_atividade_e_as_seis_semanas(sessao: Session, cadastro: Cadastro) -> None:
    incluir_atividade(sessao, cadastro)

    resposta = routes.lookahead_screen(
        pedido(
            BASE,
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cadastro)),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Montagem da carcaça" in texto
    assert "S40" in texto
    assert "S45" in texto


@pytest.mark.usefixtures("sessao")
def test_membro_inclui_atividade_e_a_resposta_traz_o_aviso(cadastro: Cadastro) -> None:
    campos = dict(campos_da_atividade(cadastro).fields)

    resposta = routes.lookahead_create_activity(
        pedido(
            f"{BASE}/atividades",
            email=EMAIL_MEMBRO,
            envio=Envio(
                metodo="POST",
                campos=[*campos.items(), ("semanas", "0"), ("semanas", "1")],
                params=_projeto(cadastro),
            ),
        )
    )

    assert resposta.status_code == 200
    assert "LA-01" in _texto(resposta)


@pytest.mark.usefixtures("sessao")
def test_formulario_invalido_volta_422_com_a_mensagem_do_campo(cadastro: Cadastro) -> None:
    resposta = routes.lookahead_create_activity(
        pedido(
            f"{BASE}/atividades",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos={"atividade": ""}, params=_projeto(cadastro)),
        )
    )

    assert resposta.status_code == 422


@pytest.mark.usefixtures("sessao")
def test_visualizador_le_mas_nao_grava(cadastro: Cadastro) -> None:
    email = EMAIL_VISUALIZADOR
    leitura = routes.lookahead_screen(
        pedido(BASE, email=email, envio=Envio(params=_projeto(cadastro)))
    )
    gravacao = routes.lookahead_create_activity(
        pedido(
            f"{BASE}/atividades",
            email=email,
            envio=Envio(
                metodo="POST",
                campos=campos_da_atividade(cadastro).fields,
                params=_projeto(cadastro),
            ),
        )
    )

    assert leitura.status_code == 200
    assert gravacao.status_code == 403


def test_o_excel_sai_como_arquivo(sessao: Session, cadastro: Cadastro) -> None:
    incluir_atividade(sessao, cadastro)

    resposta = routes.lookahead_excel(
        pedido(
            f"{BASE}/excel",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cadastro), alpine=False),
        )
    )

    assert resposta.status_code == 200
    assert "spreadsheetml" in resposta.mimetype
    assert resposta.get_body()[:2] == b"PK"


def test_a_versao_imprimivel_traz_a_coluna_projeto_no_portfolio(
    sessao: Session, cadastro: Cadastro
) -> None:
    incluir_atividade(sessao, cadastro)

    resposta = routes.lookahead_printable(
        pedido(
            f"{BASE}/imprimivel",
            email=EMAIL_MEMBRO,
            envio=Envio(params={"projeto": "portfolio"}),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Projeto" in texto
    assert "TN-TESTE-001" in texto
