"""Rotas da Produtividade (ISSUE-046): tela, modais, gravações, importação e exportações.

A costura é HTTP: o handler recebe a ``HttpRequest`` do navegador e a resposta é lida como a
pessoa a veria (status, texto, cabeçalho do aviso).
"""

from __future__ import annotations

import html

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import importing
from src.modulos.planejamento import calculations, routes, service
from src.modulos.planejamento.models import ProductivityEntry, ProductivityItem
from tests.apoio_produtividade import (
    HOJE,
    SEMANA_ATUAL,
    Cenario,
    Envio,
    form_item,
    montar_cenario,
    pedido,
)

BASE = "/api/planejamento/produtividade"
EMAIL_MEMBRO = "membro-prod@example.invalid"
EMAIL_GESTOR = "gestor-prod@example.invalid"
EMAIL_VISUALIZADOR = "visualizador-prod@example.invalid"


def _texto(resposta: func.HttpResponse) -> str:
    return html.unescape(resposta.get_body().decode())


def _projeto(cenario: Cenario) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    return montar_cenario(sessao)


def _criar(
    cenario: Cenario, sessao: Session, *, gestor: bool = False, **overrides: str
) -> ProductivityItem:
    return service.save_item(
        sessao,
        user=cenario.usuario_gestor if gestor else cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=None,
        form=form_item(cenario, **overrides),
        reference_date=HOJE,
    )


def _aprovar(cenario: Cenario, sessao: Session, item: ProductivityItem) -> ProductivityItem:
    return service.approve_item(
        sessao,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )


def test_a_tela_traz_os_filtros_e_a_aba_quantidades(sessao: Session, cenario: Cenario) -> None:
    _criar(cenario, sessao)

    resposta = routes.productivity_screen(
        pedido(BASE, email=EMAIL_MEMBRO, envio=Envio(params=_projeto(cenario)))
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "produtividade-filtros" in texto
    assert "produtividade-conteudo" in texto
    assert 'data-resultado="conteudo"' in texto
    assert "QTD-01" in texto
    assert "Plano x realizado por item" in texto


def test_o_filtro_de_empresa_recorta_o_conteudo(sessao: Session, cenario: Cenario) -> None:
    _criar(cenario, sessao)

    resposta = routes.productivity_screen(
        pedido(
            BASE,
            email=EMAIL_MEMBRO,
            envio=Envio(
                params={
                    **_projeto(cenario),
                    "empresa": str(cenario.empresa.id),
                    "corte": SEMANA_ATUAL,
                }
            ),
        )
    )

    assert resposta.status_code == 200
    assert 'data-resultado="conteudo"' in _texto(resposta)


def test_o_formulario_do_item_novo_abre_no_modal(cenario: Cenario) -> None:
    resposta = routes.productivity_new_item(
        pedido(
            f"{BASE}/itens/novo",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alvo="produtividade-modal"),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="produtividade-modal"' in texto
    assert "Novo item" in texto
    assert "Previsto por semana" in texto


def test_o_item_novo_grava_e_a_resposta_traz_o_conteudo(cenario: Cenario) -> None:
    form = form_item(cenario)
    campos = [
        *form.fields.items(),
        *((f"previsto_{week}", value) for week, value in form.planned.items()),
    ]

    resposta = routes.productivity_create_item(
        pedido(
            f"{BASE}/itens",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario)),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "QTD-01" in texto
    assert "data-prod-conteudo" in texto
    assert resposta.headers.get("X-TN-Toast")


def test_formulario_invalido_volta_422_com_a_mensagem(cenario: Cenario) -> None:
    campos = dict(form_item(cenario).fields)
    campos["empresa"] = ""

    resposta = routes.productivity_create_item(
        pedido(
            f"{BASE}/itens",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario)),
        )
    )

    assert resposta.status_code == 422
    assert "Escolha a empresa" in _texto(resposta)


def test_quem_elaborou_recebe_403_ao_aprovar(sessao: Session, cenario: Cenario) -> None:
    item = _criar(cenario, sessao, gestor=True)

    resposta = routes.productivity_approve_item(
        pedido(
            f"{BASE}/itens/{item.id}/aprovacao",
            email=EMAIL_GESTOR,
            envio=Envio(
                metodo="POST",
                campos={"versao": str(item.version)},
                params=_projeto(cenario),
                rota={"item_id": str(item.id)},
                alvo="produtividade-modal",
            ),
        )
    )

    assert resposta.status_code == 403
    assert "segregação de funções" in _texto(resposta)


def test_o_gestor_aprova_e_a_lb_sai_dos_indicadores(sessao: Session, cenario: Cenario) -> None:
    item = _criar(cenario, sessao)

    resposta = routes.productivity_approve_item(
        pedido(
            f"{BASE}/itens/{item.id}/aprovacao",
            email=EMAIL_GESTOR,
            envio=Envio(
                metodo="POST",
                campos={"versao": str(item.version)},
                params=_projeto(cenario),
                rota={"item_id": str(item.id)},
                alvo="produtividade-modal",
            ),
        )
    )

    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert item.situation == calculations.ITEM_APPROVED


def test_visualizador_le_mas_nao_grava(cenario: Cenario) -> None:
    leitura = routes.productivity_screen(
        pedido(BASE, email=EMAIL_VISUALIZADOR, envio=Envio(params=_projeto(cenario)))
    )
    form = form_item(cenario)
    gravacao = routes.productivity_create_item(
        pedido(
            f"{BASE}/itens",
            email=EMAIL_VISUALIZADOR,
            envio=Envio(metodo="POST", campos=form.fields, params=_projeto(cenario)),
        )
    )

    assert leitura.status_code == 200
    assert gravacao.status_code == 403


def test_o_excel_sai_como_arquivo(sessao: Session, cenario: Cenario) -> None:
    _criar(cenario, sessao)

    resposta = routes.productivity_excel(
        pedido(
            f"{BASE}/excel",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alpine=False),
        )
    )

    assert resposta.status_code == 200
    assert "spreadsheetml" in resposta.mimetype
    assert resposta.get_body()[:2] == b"PK"


def test_a_versao_imprimivel_traz_a_coluna_projeto(sessao: Session, cenario: Cenario) -> None:
    _criar(cenario, sessao)

    resposta = routes.productivity_printable(
        pedido(
            f"{BASE}/imprimivel",
            email=EMAIL_MEMBRO,
            envio=Envio(params={"projeto": "portfolio"}),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Projeto" in texto
    assert "TN-PROD-001" in texto


def test_o_formulario_da_revisao_oferece_a_sm_aprovada(sessao: Session, cenario: Cenario) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))

    resposta = routes.productivity_revision_form(
        pedido(
            f"{BASE}/itens/{item.id}/revisao",
            email=EMAIL_MEMBRO,
            envio=Envio(
                params=_projeto(cenario),
                rota={"item_id": str(item.id)},
                alvo="produtividade-modal",
            ),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "SM-TN-2026-9001" in texto
    assert "Semanas congeladas" in texto


def test_o_apontamento_grava_a_semana(sessao: Session, cenario: Cenario) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))

    resposta = routes.productivity_register_entries(
        pedido(
            f"{BASE}/apontamento",
            email=EMAIL_MEMBRO,
            envio=Envio(
                metodo="POST",
                campos={
                    "empresa": str(cenario.empresa.id),
                    "semana": "2026-S38",
                    f"realizado_{item.id}": "10",
                    f"hh_{item.id}": "100",
                },
                params=_projeto(cenario),
                alvo="produtividade-modal",
            ),
        )
    )

    entrada = sessao.scalars(
        select(ProductivityEntry).where(ProductivityEntry.item_id == item.id)
    ).one()
    assert resposta.status_code == 200
    assert entrada.week == "2026-S38"
    assert resposta.headers.get("X-TN-Toast")


def test_a_importacao_da_produtividade_esta_registrada() -> None:
    importer = importing.find("produtividade-itens")

    assert importer is not None
    assert importer.module == "planejamento"
    assert [coluna.field for coluna in importer.columns][:2] == ["empresa", "grupo"]
