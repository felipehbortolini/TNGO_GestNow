"""Rotas dos KPIs de performance (ISSUE-048): aba, formulário do plano, gravação e exportações.

A costura é HTTP: o handler recebe a ``HttpRequest`` do navegador e a resposta é lida como a
pessoa a veria (status, texto, cabeçalho do aviso).
"""

from __future__ import annotations

import html

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modulos.central_acoes.models import Action
from src.modulos.planejamento import routes, service, validation
from src.modulos.planejamento.models import ProductivityItem
from tests.apoio_produtividade import (
    HOJE,
    Cenario,
    Envio,
    campos_do_plano,
    form_item,
    montar_cenario,
    pedido,
)

BASE = "/api/planejamento/produtividade"
KPIS = f"{BASE}/kpis"
EMAIL_MEMBRO = "membro-prod@example.invalid"
EMAIL_GESTOR = "gestor-prod@example.invalid"
EMAIL_VISUALIZADOR = "visualizador-prod@example.invalid"
ALVO_KPIS = "produtividade-kpis"
ALVO_MODAL = "produtividade-modal produtividade-kpis"


def _texto(resposta: func.HttpResponse) -> str:
    return html.unescape(resposta.get_body().decode())


def _projeto(cenario: Cenario) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    return montar_cenario(sessao)


def _item(cenario: Cenario, sessao: Session) -> ProductivityItem:
    item = service.save_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=None,
        form=form_item(cenario),
        reference_date=HOJE,
    )
    return service.approve_item(
        sessao,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )


def test_a_tela_traz_as_tres_abas(sessao: Session, cenario: Cenario) -> None:
    _item(cenario, sessao)

    resposta = routes.productivity_screen(
        pedido(BASE, email=EMAIL_MEMBRO, envio=Envio(params=_projeto(cenario)))
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="produtividade-kpis"' in texto
    assert "Performance por empresa" in texto


def test_a_aba_traz_os_indicadores_e_a_tabela(sessao: Session, cenario: Cenario) -> None:
    _item(cenario, sessao)

    resposta = routes.productivity_performance(
        pedido(
            KPIS,
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alvo=ALVO_KPIS),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="produtividade-kpis"' in texto
    assert "Performance geral" in texto
    assert "Performance por empresa" in texto
    assert "Tendência semanal por empresa" in texto
    assert "Montadora Alfa" in texto


def test_a_aba_no_portfolio_traz_a_coluna_projeto(sessao: Session, cenario: Cenario) -> None:
    _item(cenario, sessao)

    resposta = routes.productivity_performance(
        pedido(
            KPIS,
            email=EMAIL_MEMBRO,
            envio=Envio(params={"projeto": "portfolio"}, alvo=ALVO_KPIS),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Performance geral" in texto
    assert "Projeto" in texto
    assert "TN-PROD-001" in texto


def test_o_formulario_do_plano_abre_no_modal(sessao: Session, cenario: Cenario) -> None:
    _item(cenario, sessao)

    resposta = routes.productivity_new_performance_action(
        pedido(
            f"{KPIS}/acoes/nova",
            email=EMAIL_MEMBRO,
            envio=Envio(
                params={**_projeto(cenario), "empresa": str(cenario.empresa.id)},
                alvo="produtividade-modal",
            ),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="produtividade-modal"' in texto
    assert "Plano de ação de produtividade" in texto
    assert "Recuperar a produtividade" in texto
    assert "Gerar plano de ação" in texto


def test_o_plano_grava_e_a_resposta_traz_a_aba(sessao: Session, cenario: Cenario) -> None:
    campos = {
        **campos_do_plano(cenario),
        "f_empresa": str(cenario.empresa.id),
        "f_corte": "2026-S39",
    }

    resposta = routes.productivity_create_performance_action(
        pedido(
            f"{KPIS}/acoes",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_MODAL),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert "data-produtividade-salvo" in texto
    assert 'id="produtividade-kpis"' in texto
    acao = sessao.scalars(select(Action)).one()
    assert acao.origin == "Produtividade"
    assert acao.origin_ref == f"PRD-2026-S39-{cenario.empresa.id:02d}"


def test_o_plano_duplicado_volta_422(sessao: Session, cenario: Cenario) -> None:
    campos = {
        **campos_do_plano(cenario),
        "f_empresa": str(cenario.empresa.id),
        "f_corte": "2026-S39",
    }
    primeiro = routes.productivity_create_performance_action(
        pedido(
            f"{KPIS}/acoes",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_MODAL),
        )
    )
    segundo = routes.productivity_create_performance_action(
        pedido(
            f"{KPIS}/acoes",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_MODAL),
        )
    )

    assert primeiro.status_code == 200
    assert segundo.status_code == 422
    assert "Já existe ação aberta" in _texto(segundo)
    assert len(sessao.scalars(select(Action)).all()) == 1


def test_o_plano_com_assunto_curto_volta_422_com_a_mensagem(
    sessao: Session, cenario: Cenario
) -> None:
    campos = {
        **campos_do_plano(cenario, assunto="curta"),
        "f_empresa": str(cenario.empresa.id),
        "f_corte": "2026-S39",
    }

    resposta = routes.productivity_create_performance_action(
        pedido(
            f"{KPIS}/acoes",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_MODAL),
        )
    )

    assert resposta.status_code == 422
    assert validation.PLAN_SUBJECT_MESSAGE in _texto(resposta)
    assert sessao.scalars(select(Action)).all() == []


def test_o_excel_e_o_imprimivel_da_aba(sessao: Session, cenario: Cenario) -> None:
    _item(cenario, sessao)

    excel = routes.productivity_performance_excel(
        pedido(
            f"{KPIS}/excel",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alpine=False),
        )
    )
    imprimivel = routes.productivity_performance_printable(
        pedido(
            f"{KPIS}/imprimivel",
            email=EMAIL_MEMBRO,
            envio=Envio(params={"projeto": "portfolio"}),
        )
    )

    assert excel.status_code == 200
    assert "spreadsheetml" in excel.mimetype
    assert excel.get_body()[:2] == b"PK"
    texto = _texto(imprimivel)
    assert imprimivel.status_code == 200
    assert "Performance por empresa" in texto
    assert "Tendência semanal por empresa" in texto
    assert "Projeto" in texto
    assert "TN-PROD-001" in texto


def test_o_visualizador_le_mas_nao_grava(sessao: Session, cenario: Cenario) -> None:
    _item(cenario, sessao)
    leitura = routes.productivity_performance(
        pedido(
            KPIS,
            email=EMAIL_VISUALIZADOR,
            envio=Envio(params=_projeto(cenario), alvo=ALVO_KPIS),
        )
    )
    campos = {
        **campos_do_plano(cenario),
        "f_empresa": str(cenario.empresa.id),
        "f_corte": "2026-S39",
    }
    gravacao = routes.productivity_create_performance_action(
        pedido(
            f"{KPIS}/acoes",
            email=EMAIL_VISUALIZADOR,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_MODAL),
        )
    )

    assert leitura.status_code == 200
    assert gravacao.status_code == 403
