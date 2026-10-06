"""As rotas do painel e do follow-up (ISSUE-020, D12): PDF só do filtro, painel, modal, 403 e simulado."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import urlencode

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.core import config
from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.central_acoes import panel_routes, routes, service
from tests.apoio_acoes import REFERENCIA, Cenario, nova_acao


def _requisicao(
    usuario: User, *, metodo: str = "GET", params: Mapping[str, str] | None = None
) -> func.HttpRequest:
    return func.HttpRequest(
        method=metodo,
        url="/api/central-acoes/painel",
        headers={
            "X-Alpine-Request": "true",
            "X-Alpine-Target": "painel-conteudo",
            "Cookie": f"{DEMO_COOKIE}={usuario.id}",
        },
        params=dict(params or {}),
        route_params={},
        body=urlencode({}).encode(),
    )


def _chamar(rota: object, requisicao: func.HttpRequest) -> func.HttpResponse:
    return rota.get_user_function()(requisicao)  # type: ignore[attr-defined]


def _massa(session: Session, cenario: Cenario) -> None:
    for referencia, assunto, campos in (
        ("RSK-A", "Assunto do Gil", {}),
        (
            "RSK-B",
            "Assunto do Mário",
            {"responsible_id": cenario.mario.person_id},
        ),
        (
            "RSK-C",
            "Assunto atrasado do Gil",
            {"planned_date": REFERENCIA - timedelta(days=2)},
        ),
    ):
        service.create_action(
            session,
            user=cenario.gil,
            new=nova_acao(cenario, origin_ref=referencia, subject=assunto, **campos),
            reference_date=REFERENCIA,
        )


def test_pdf_das_acoes_traz_exatamente_as_do_filtro(sessao: Session, cenario: Cenario) -> None:
    _massa(sessao, cenario)
    filtro = {"responsavel": str(cenario.mario.person_id)}

    resposta = _chamar(routes.actions_printable, _requisicao(cenario.gil, params=filtro))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Assunto do Mário" in corpo
    assert "Assunto do Gil" not in corpo
    assert "Assunto atrasado do Gil" not in corpo


def test_painel_mostra_as_contagens_e_oferece_excel_e_pdf(
    sessao: Session, cenario: Cenario
) -> None:
    _massa(sessao, cenario)

    tela = _chamar(panel_routes.panel_screen, _requisicao(cenario.gil))
    excel = _chamar(panel_routes.panel_excel, _requisicao(cenario.gil))
    imprimivel = _chamar(panel_routes.panel_printable, _requisicao(cenario.gil))

    assert tela.status_code == excel.status_code == imprimivel.status_code == 200
    assert "Gil Gestor" in tela.get_body().decode()
    assert "painel/excel" in tela.get_body().decode()
    assert "painel/imprimivel" in tela.get_body().decode()
    assert excel.get_body()[:2] == b"PK"


def test_modal_do_follow_up_lista_um_responsavel_por_linha_e_avisa_simulado(
    sessao: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(config.EMAIL_SENDING_VARIABLE, raising=False)
    _massa(sessao, cenario)

    previa = _chamar(panel_routes.follow_up_form, _requisicao(cenario.gil))
    envio = _chamar(panel_routes.follow_up_send, _requisicao(cenario.gil, metodo="POST"))

    texto = previa.get_body().decode()
    assert "Gil Gestor" in texto
    assert "Mário Membro" in texto
    assert "imulado" in texto
    assert envio.status_code == 200
    assert any("imulado" in valor for valor in envio.headers.values())


def test_membro_nao_abre_nem_envia_o_follow_up(sessao: Session, cenario: Cenario) -> None:
    _massa(sessao, cenario)

    previa = _chamar(panel_routes.follow_up_form, _requisicao(cenario.mario))
    envio = _chamar(panel_routes.follow_up_send, _requisicao(cenario.mario, metodo="POST"))

    assert previa.status_code == 403
    assert envio.status_code == 403
