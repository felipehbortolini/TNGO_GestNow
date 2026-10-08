"""Rotas das horas efetivas (ISSUE-047): aba, modais, gravações e exportações.

A costura é HTTP: o handler recebe a ``HttpRequest`` do navegador e a resposta é lida como a
pessoa a veria (status, texto, cabeçalho do aviso).
"""

from __future__ import annotations

import html

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.modulos.planejamento import routes, service
from src.modulos.planejamento.models import FieldDay
from tests.apoio_produtividade import (
    HOJE,
    Cenario,
    Envio,
    campos_da_amostra,
    campos_da_paralisacao,
    form_jornada,
    montar_cenario,
    pedido,
)

BASE = "/api/planejamento/produtividade"
HORAS = f"{BASE}/horas-efetivas"
EMAIL_MEMBRO = "membro-prod@example.invalid"
EMAIL_VISUALIZADOR = "visualizador-prod@example.invalid"
ALVO_HORAS = "produtividade-horas"
ALVO_MODAL = "produtividade-modal produtividade-horas"


def _texto(resposta: func.HttpResponse) -> str:
    return html.unescape(resposta.get_body().decode())


def _projeto(cenario: Cenario) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    return montar_cenario(sessao)


def _jornada(cenario: Cenario, sessao: Session, **overrides: str) -> FieldDay:
    return service.save_field_day(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        day_id=None,
        form=form_jornada(cenario, **overrides),
        reference_date=HOJE,
    )


def test_a_tela_traz_as_duas_abas(sessao: Session, cenario: Cenario) -> None:
    _jornada(cenario, sessao)

    resposta = routes.productivity_screen(
        pedido(BASE, email=EMAIL_MEMBRO, envio=Envio(params=_projeto(cenario)))
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "produtividade-filtros" in texto
    assert "produtividade-conteudo" in texto
    assert 'id="produtividade-horas"' in texto
    assert "Capacidade produtiva" in texto


def test_a_aba_das_horas_traz_os_registros_e_os_filtros(sessao: Session, cenario: Cenario) -> None:
    _jornada(cenario, sessao)

    resposta = routes.productivity_hours(
        pedido(
            HORAS,
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alvo=ALVO_HORAS),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="produtividade-horas"' in texto
    assert "Sérgio Pinto" in texto
    assert "Registros de jornada" in texto
    assert "Pareto dos motivos de parada" in texto


def test_o_filtro_da_area_recorta_a_aba(sessao: Session, cenario: Cenario) -> None:
    _jornada(cenario, sessao, area="Flotação 310")
    _jornada(cenario, sessao, area="Moagem 210", encarregado="Mário Castro", data="2026-09-24")

    resposta = routes.productivity_hours(
        pedido(
            HORAS,
            email=EMAIL_MEMBRO,
            envio=Envio(params={**_projeto(cenario), "area": "Moagem 210"}, alvo=ALVO_HORAS),
        )
    )

    texto = _texto(resposta)
    assert "Moagem 210" in texto
    assert "1 registro de jornada" in texto
    assert "2 registros de jornada" not in texto


def test_o_formulario_da_jornada_abre_no_modal(cenario: Cenario) -> None:
    resposta = routes.productivity_new_field_day(
        pedido(
            f"{HORAS}/jornadas/nova",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alvo="produtividade-modal"),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="produtividade-modal"' in texto
    assert "Registrar jornada" in texto
    assert "Turno da manhã" in texto


def test_a_jornada_grava_e_a_resposta_traz_a_aba(cenario: Cenario) -> None:
    campos = form_jornada(cenario).fields

    resposta = routes.productivity_create_field_day(
        pedido(
            f"{HORAS}/jornadas",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_MODAL),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert "Sérgio Pinto" in texto
    assert "data-produtividade-salvo" in texto


def test_a_segunda_jornada_da_mesma_frente_volta_422(sessao: Session, cenario: Cenario) -> None:
    _jornada(cenario, sessao)

    resposta = routes.productivity_create_field_day(
        pedido(
            f"{HORAS}/jornadas",
            email=EMAIL_MEMBRO,
            envio=Envio(
                metodo="POST",
                campos=form_jornada(cenario).fields,
                params=_projeto(cenario),
                alvo=ALVO_MODAL,
            ),
        )
    )

    assert resposta.status_code == 422
    assert "desta frente" in _texto(resposta)


def test_o_horario_fora_de_ordem_volta_422_com_a_mensagem(cenario: Cenario) -> None:
    resposta = routes.productivity_create_field_day(
        pedido(
            f"{HORAS}/jornadas",
            email=EMAIL_MEMBRO,
            envio=Envio(
                metodo="POST",
                campos=form_jornada(cenario, mInicio="07:00").fields,
                params=_projeto(cenario),
                alvo=ALVO_MODAL,
            ),
        )
    )

    assert resposta.status_code == 422
    assert "ordem" in _texto(resposta)


def test_a_jornada_em_edicao_volta_no_modal(sessao: Session, cenario: Cenario) -> None:
    registro = _jornada(cenario, sessao)

    resposta = routes.productivity_edit_field_day(
        pedido(
            f"{HORAS}/jornadas/{registro.id}/editar",
            email=EMAIL_MEMBRO,
            envio=Envio(
                params=_projeto(cenario),
                rota={"registro_id": str(registro.id)},
                alvo="produtividade-modal",
            ),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Editar jornada" in texto
    assert "08:00" in texto


def test_a_rodada_grava_a_grade_de_motivos(cenario: Cenario) -> None:
    campos, parados, transitos = campos_da_amostra(
        cenario, parado={0: "6", 2: "5"}, transito={0: "2"}
    )
    enviados = {
        **campos,
        **{f"parado_{indice}": valor for indice, valor in parados.items()},
        **{f"transito_{indice}": valor for indice, valor in transitos.items()},
    }

    resposta = routes.productivity_create_sample(
        pedido(
            f"{HORAS}/amostragens",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=enviados, params=_projeto(cenario), alvo=ALVO_MODAL),
        )
    )

    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert "Rodada" in _texto(resposta)


def test_a_rodada_sem_pessoas_volta_422(cenario: Cenario) -> None:
    campos, _, _ = campos_da_amostra(cenario, trabalhando="0")

    resposta = routes.productivity_create_sample(
        pedido(
            f"{HORAS}/amostragens",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_MODAL),
        )
    )

    assert resposta.status_code == 422
    assert "ao menos uma pessoa observada" in _texto(resposta)


def test_a_paralisacao_grava_e_o_aviso_do_pleito_aparece(cenario: Cenario) -> None:
    resposta = routes.productivity_create_stoppage(
        pedido(
            f"{HORAS}/paralisacoes",
            email=EMAIL_MEMBRO,
            envio=Envio(
                metodo="POST",
                campos=campos_da_paralisacao(cenario, responsabilidade="Cliente"),
                params=_projeto(cenario),
                alvo=ALVO_MODAL,
            ),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert "pleito" in texto


def test_o_excel_das_horas_sai_como_arquivo(sessao: Session, cenario: Cenario) -> None:
    _jornada(cenario, sessao)

    resposta = routes.productivity_hours_excel(
        pedido(
            f"{HORAS}/excel",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alpine=False),
        )
    )

    assert resposta.status_code == 200
    assert "spreadsheetml" in resposta.mimetype
    assert resposta.get_body()[:2] == b"PK"


def test_a_versao_imprimivel_traz_as_tabelas(sessao: Session, cenario: Cenario) -> None:
    _jornada(cenario, sessao)

    resposta = routes.productivity_hours_printable(
        pedido(
            HORAS + "/imprimivel",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario)),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Capacidade produtiva" in texto
    assert "Registros de jornada" in texto
    assert "Pareto dos motivos de parada" in texto


def test_o_visualizador_le_mas_nao_grava(cenario: Cenario) -> None:
    leitura = routes.productivity_hours(
        pedido(
            HORAS, email=EMAIL_VISUALIZADOR, envio=Envio(params=_projeto(cenario), alvo=ALVO_HORAS)
        )
    )
    gravacao = routes.productivity_create_field_day(
        pedido(
            f"{HORAS}/jornadas",
            email=EMAIL_VISUALIZADOR,
            envio=Envio(
                metodo="POST",
                campos=form_jornada(cenario).fields,
                params=_projeto(cenario),
                alvo=ALVO_MODAL,
            ),
        )
    )

    assert leitura.status_code == 200
    assert gravacao.status_code == 403
