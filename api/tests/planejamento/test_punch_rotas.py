"""Rotas da Punch list (ISSUE-049): tela, gravação, 403 da segregação e do perfil, exportação.

A costura é HTTP: o handler recebe a ``HttpRequest`` do navegador e a resposta é lida como a
pessoa a veria (status e texto).
"""

from __future__ import annotations

import html
from urllib.parse import unquote

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.core.models import Attachment
from src.modulos.planejamento import punch_calculations as calc
from src.modulos.planejamento import punch_routes as routes
from tests.apoio_6wla import Cadastro, Envio, pedido
from tests.apoio_punch import (
    CenarioPunch,
    abrir,
    anexar_evidencia,
    levar_a_verificacao,
    montar_cenario,
)

BASE = "/api/planejamento/punch-list"
EMAIL_MEMBRO = "membro-6wla@example.invalid"
EMAIL_ADMIN = "admin-6wla@example.invalid"
EMAIL_VISUALIZADOR = "visualizador-6wla@example.invalid"
EMAIL_FORNECEDOR = "fornecedor-6wla@example.invalid"
ALVO = "punch-conteudo"


@pytest.fixture
def cenario(sessao: Session, cadastro: Cadastro) -> CenarioPunch:
    """O cadastro do 6WLA com a numeração do projeto e dois sistemas."""
    return montar_cenario(sessao, cadastro)


def _texto(resposta: object) -> str:
    return html.unescape(resposta.get_body().decode())  # type: ignore[attr-defined]


def _aviso(resposta: object) -> str:
    return unquote(resposta.headers["X-TN-Toast"])  # type: ignore[attr-defined]


def _projeto(cenario: CenarioPunch) -> dict[str, str]:
    return {"projeto": str(cenario.cadastro.projeto.id)}


def _envio(cenario: CenarioPunch, **dados: object) -> Envio:
    return Envio(params=_projeto(cenario), alvo=ALVO, **dados)  # type: ignore[arg-type]


def test_a_tela_lista_o_item_o_alerta_e_a_tabela_de_sistemas(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)

    resposta = routes.punch_screen(pedido(BASE, email=EMAIL_MEMBRO, envio=_envio(cenario)))

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert item.code in texto
    assert "1 sistema bloqueado por item A aberto" in texto
    assert "Sistemas e liberação por marco" in texto
    assert "Bloqueado (1)" in texto


@pytest.mark.usefixtures("sessao")
def test_a_tela_sem_item_mostra_o_vazio_de_origem(cenario: CenarioPunch) -> None:
    resposta = routes.punch_screen(pedido(BASE, email=EMAIL_MEMBRO, envio=_envio(cenario)))
    assert 'data-estado="vazio-origem"' in _texto(resposta)


def test_o_filtro_sem_resultado_mostra_o_vazio_por_filtro(
    sessao: Session, cenario: CenarioPunch
) -> None:
    abrir(sessao, cenario)
    envio = Envio(params={**_projeto(cenario), "categoria": "C"}, alvo=ALVO)
    resposta = routes.punch_screen(pedido(BASE, email=EMAIL_MEMBRO, envio=envio))
    assert 'data-estado="vazio-filtro"' in _texto(resposta)


def test_fornecedor_nao_abre_a_tela(sessao: Session, cenario: CenarioPunch) -> None:
    abrir(sessao, cenario)
    resposta = routes.punch_screen(pedido(BASE, email=EMAIL_FORNECEDOR, envio=_envio(cenario)))
    assert resposta.status_code == 403


def test_visualizador_le_mas_nao_ve_os_botoes_nem_grava(
    sessao: Session, cenario: CenarioPunch
) -> None:
    abrir(sessao, cenario)
    leitura = routes.punch_screen(pedido(BASE, email=EMAIL_VISUALIZADOR, envio=_envio(cenario)))
    assert leitura.status_code == 200
    assert "Novo item" not in _texto(leitura)

    gravacao = routes.punch_new_save(
        pedido(
            f"{BASE}/novo",
            email=EMAIL_VISUALIZADOR,
            envio=_envio(cenario, metodo="POST", campos={"tag": "X"}),
        )
    )
    assert gravacao.status_code == 403


@pytest.mark.usefixtures("sessao")
def test_membro_abre_item_pela_rota_e_a_resposta_traz_a_tela_e_o_aviso(
    cenario: CenarioPunch,
) -> None:
    campos = {
        "sistema": str(cenario.sistema.id),
        "subsistema": "Painéis",
        "tag": "PN-210-01",
        "disciplina": "Elétrica",
        "categoria": "A",
        "marco": "Comissionamento",
        "origem": "Walkdown",
        "prazo": "2026-10-05",
        "descricao": "Falta identificação dos cabos.",
        "empresa": str(cenario.cadastro.empresa.id),
        "responsavel": str(cenario.cadastro.responsavel.id),
        "identificado_por": str(cenario.cadastro.responsavel.id),
    }
    resposta = routes.punch_new_save(
        pedido(
            f"{BASE}/novo",
            email=EMAIL_MEMBRO,
            envio=_envio(cenario, metodo="POST", campos=campos),
        )
    )
    assert resposta.status_code == 200
    assert "PL-TN-2026-0001" in _texto(resposta)
    assert "ação criada na Central" in _aviso(resposta)


@pytest.mark.usefixtures("sessao")
def test_dados_invalidos_devolvem_o_formulario_com_422_e_a_mensagem_sob_o_campo(
    cenario: CenarioPunch,
) -> None:
    resposta = routes.punch_new_save(
        pedido(
            f"{BASE}/novo",
            email=EMAIL_MEMBRO,
            envio=_envio(cenario, metodo="POST", campos={"tag": "", "categoria": "A"}),
        )
    )
    assert resposta.status_code == 422
    assert "Campo obrigatório." in _texto(resposta)


def test_verificador_igual_ao_executante_recebe_403(sessao: Session, cenario: CenarioPunch) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)

    resposta = routes.punch_verify_save(
        pedido(
            f"{BASE}/{item.id}/verificar",
            email=EMAIL_MEMBRO,
            envio=_envio(
                cenario,
                metodo="POST",
                campos={"resultado": "aprovado", "versao": str(item.version)},
                rota={"item_id": str(item.id)},
            ),
        )
    )

    assert resposta.status_code == 403
    assert "executante" in _texto(resposta)
    assert item.situation == calc.AWAITING_VERIFICATION


def test_fechamento_sem_anexo_devolve_422_com_a_mensagem(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)
    sessao.execute(delete(Attachment))

    resposta = routes.punch_verify_save(
        pedido(
            f"{BASE}/{item.id}/verificar",
            email=EMAIL_ADMIN,
            envio=_envio(
                cenario,
                metodo="POST",
                campos={"resultado": "aprovado", "versao": str(item.version)},
                rota={"item_id": str(item.id)},
            ),
        )
    )

    assert resposta.status_code == 422
    assert "evidência é obrigatória" in _texto(resposta)


def test_verificador_diferente_fecha_o_item_pela_rota(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)

    resposta = routes.punch_verify_save(
        pedido(
            f"{BASE}/{item.id}/verificar",
            email=EMAIL_ADMIN,
            envio=_envio(
                cenario,
                metodo="POST",
                campos={"resultado": "aprovado", "versao": str(item.version)},
                rota={"item_id": str(item.id)},
            ),
        )
    )

    assert resposta.status_code == 200
    assert item.situation == calc.CLOSED
    assert "fechado" in _aviso(resposta)


def test_o_modal_de_verificacao_lista_os_anexos_do_item(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)
    anexar_evidencia(sessao, cenario, item)

    resposta = routes.punch_verify_form(
        pedido(
            f"{BASE}/{item.id}/verificar",
            email=EMAIL_ADMIN,
            envio=_envio(cenario, rota={"item_id": str(item.id)}),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert f"registro={item.id}" in texto
    assert "Registrar verificação" in texto


def test_o_excel_e_o_pdf_trazem_os_mesmos_dados_da_tela(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)

    excel = routes.punch_excel(
        pedido(f"{BASE}/excel", email=EMAIL_MEMBRO, envio=_envio(cenario, alpine=False))
    )
    pdf = routes.punch_printable(
        pedido(f"{BASE}/imprimivel", email=EMAIL_MEMBRO, envio=_envio(cenario))
    )

    assert excel.status_code == 200
    assert excel.headers["Content-Disposition"].startswith("attachment")
    assert pdf.status_code == 200
    assert item.code in _texto(pdf)
    assert "Sistemas e liberação por marco" in _texto(pdf)
