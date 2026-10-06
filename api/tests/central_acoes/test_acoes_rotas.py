"""As rotas da tela Ações (ISSUE-019, D14): filtros, chips, kanban, replanejar com 422 e 403.

O handler é chamado com a requisição de Alpine, o seletor da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import urlencode

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.central_acoes import routes, service
from tests.apoio_acoes import REFERENCIA, Cenario, nova_acao


def _requisicao(
    usuario: User,
    *,
    metodo: str = "GET",
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, str] | None = None,
    rota: Mapping[str, str] | None = None,
) -> func.HttpRequest:
    headers = {
        "X-Alpine-Request": "true",
        "X-Alpine-Target": "acoes-conteudo",
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/central-acoes/acoes",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def _tela(usuario: User, **params: str) -> func.HttpResponse:
    return routes.list_actions_screen.get_user_function()(_requisicao(usuario, params=params))


def _criar(session: Session, cenario: Cenario, **campos: object) -> service.ActionRecord:
    return service.create_action(
        session, user=cenario.gil, new=nova_acao(cenario, **campos), reference_date=REFERENCIA
    )


def _tres_acoes(session: Session, cenario: Cenario) -> service.ActionRecord:
    _criar(session, cenario, origin_ref="RSK-NO-PRAZO", subject="Assunto no prazo")
    atrasada = _criar(
        session,
        cenario,
        origin_ref="RSK-ATRASADA",
        subject="Assunto atrasado",
        planned_date=REFERENCIA - timedelta(days=4),
    )
    _criar(session, cenario, origin="Ata", origin_ref="TN-2026-0001", subject="Assunto da ata")
    return atrasada


# ── A tela, os KPIs, os filtros e os chips ───────────────────────────────────


def test_a_tela_lista_as_acoes_em_andamento_com_os_kpis(sessao: Session, cenario: Cenario) -> None:
    _tres_acoes(sessao, cenario)

    resposta = _tela(cenario.gil)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Assunto no prazo" in corpo
    assert "Assunto atrasado" in corpo
    assert "RSK-ATRASADA" in corpo


def test_filtro_atrasada_mostra_so_as_atrasadas_e_vira_chip(
    sessao: Session, cenario: Cenario
) -> None:
    _tres_acoes(sessao, cenario)

    corpo = _tela(cenario.gil, status="atrasada").get_body().decode()

    assert "Assunto atrasado" in corpo
    assert "Assunto no prazo" not in corpo
    assert 'class="chip"' in corpo


def test_filtros_de_origem_e_busca_se_somam(sessao: Session, cenario: Cenario) -> None:
    _tres_acoes(sessao, cenario)

    corpo = _tela(cenario.gil, origem="Ata", busca="ata").get_body().decode()

    assert "Assunto da ata" in corpo
    assert "Assunto atrasado" not in corpo


def test_o_kanban_mostra_as_mesmas_acoes_por_status(sessao: Session, cenario: Cenario) -> None:
    _tres_acoes(sessao, cenario)

    corpo = _tela(cenario.gil, visao="kanban").get_body().decode()

    assert "acoes__quadro" in corpo
    assert "Assunto atrasado" in corpo
    assert "Assunto no prazo" in corpo


def test_o_excel_das_acoes_sai_com_o_mesmo_filtro(sessao: Session, cenario: Cenario) -> None:
    _tres_acoes(sessao, cenario)
    requisicao = _requisicao(cenario.gil, params={"status": "atrasada"})

    resposta = routes.actions_excel.get_user_function()(requisicao)

    assert resposta.status_code == 200
    assert resposta.get_body().startswith(b"PK")


# ── Replanejar ───────────────────────────────────────────────────────────────


def _replanejar(
    cenario: Cenario, acao: service.ActionRecord, usuario: User | None = None, **form: str
) -> func.HttpResponse:
    corpo = {
        "data": (REFERENCIA + timedelta(days=15)).isoformat(),
        "justificativa": "Aguardando a liberação do fornecedor.",
        "versao": str(acao.version),
        "consulta": "",
        **form,
    }
    requisicao = _requisicao(
        usuario or cenario.gil,
        metodo="POST",
        corpo=corpo,
        rota={"acao_id": str(acao.id)},
    )
    return routes.replan_save.get_user_function()(requisicao)


def test_replanejar_sem_justificativa_devolve_422_com_o_formulario_preenchido(
    sessao: Session, cenario: Cenario
) -> None:
    acao = _tres_acoes(sessao, cenario)

    resposta = _replanejar(cenario, acao, justificativa="   ")

    assert resposta.status_code == 422
    assert service.replan_history(sessao, user=cenario.gil, action_id=acao.id) == []
    corpo = resposta.get_body().decode()
    assert (REFERENCIA + timedelta(days=15)).isoformat() in corpo
    assert "justificativa" in corpo.lower()


def test_replanejar_com_justificativa_atualiza_a_tela_e_guarda_o_historico(
    sessao: Session, cenario: Cenario
) -> None:
    acao = _tres_acoes(sessao, cenario)

    resposta = _replanejar(cenario, acao)

    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    historico = service.replan_history(sessao, user=cenario.gil, action_id=acao.id)
    assert [linha.justification for linha in historico] == ["Aguardando a liberação do fornecedor."]


def test_replanejar_com_a_versao_antiga_devolve_409(sessao: Session, cenario: Cenario) -> None:
    acao = _tres_acoes(sessao, cenario)
    assert _replanejar(cenario, acao).status_code == 200

    resposta = _replanejar(cenario, acao, data=(REFERENCIA + timedelta(days=30)).isoformat())

    assert resposta.status_code == 409


def test_visualizador_nao_replaneja_nem_ve_o_formulario(sessao: Session, cenario: Cenario) -> None:
    acao = _tres_acoes(sessao, cenario)

    resposta = _replanejar(cenario, acao, usuario=cenario.vera)

    assert resposta.status_code == 403
    assert service.replan_history(sessao, user=cenario.gil, action_id=acao.id) == []


def test_o_historico_lista_a_justificativa(sessao: Session, cenario: Cenario) -> None:
    acao = _tres_acoes(sessao, cenario)
    _replanejar(cenario, acao)
    requisicao = _requisicao(cenario.gil, rota={"acao_id": str(acao.id)})

    resposta = routes.replan_history_view.get_user_function()(requisicao)

    assert resposta.status_code == 200
    assert "Aguardando a liberação do fornecedor." in resposta.get_body().decode()


@pytest.mark.usefixtures("sessao")
def test_acao_inexistente_no_historico_devolve_422(cenario: Cenario) -> None:
    requisicao = _requisicao(cenario.gil, rota={"acao_id": "999999"})

    resposta = routes.replan_history_view.get_user_function()(requisicao)

    assert resposta.status_code == 422
