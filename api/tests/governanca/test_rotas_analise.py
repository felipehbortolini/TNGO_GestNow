"""Rotas da análise de impacto (ISSUE-024): formulários, 422 com o formulário de volta, 403 e redirecionamento."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.modulos.governanca import models, routes, service
from tests.governanca import apoio
from tests.governanca.apoio import HOJE
from tests.governanca.test_analise import _cenario, _iniciar, _registrar, analise_valida
from tests.identidades import requisicao


def _texto(resposta) -> str:
    return resposta.get_body().decode()


def _pedido(rota: str, mudanca, *, metodo: str = "GET", email: str = apoio.MEMBRO, corpo=None):
    params = {"codigo": mudanca.code} if metodo == "GET" else None
    return requisicao(f"/api/{rota}", metodo=metodo, email=email, params=params, corpo=corpo)


def test_formulario_de_inicio_traz_o_prazo_padrao_e_as_pessoas(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    resposta = routes.start_analysis_form(_pedido(routes.START_ANALYSIS_ROUTE, mudanca))
    assert resposta.status_code == 200
    corpo = _texto(resposta)
    assert 'value="2026-10-16"' in corpo
    assert "Responsável pela análise" in corpo


def test_post_do_inicio_redireciona_para_a_ficha_e_muda_a_situacao(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    corpo = {
        "codigo": mudanca.code,
        "responsavel_id": str(usuario.person_id),
        "prazo": "2026-10-16",
        "versao": str(mudanca.version),
    }
    resposta = routes.start_analysis(
        _pedido(routes.START_ANALYSIS_ROUTE, mudanca, metodo="POST", corpo=corpo)
    )
    assert resposta.status_code == 302
    assert resposta.headers["Location"].startswith("/governanca/mudanca?codigo=SM-TN-2026-0001")
    assert mudanca.situation == models.SITUATION_ANALYSIS


def test_post_do_inicio_sem_responsavel_devolve_422_com_o_formulario(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    corpo = {"codigo": mudanca.code, "prazo": "2026-10-20", "versao": str(mudanca.version)}
    resposta = routes.start_analysis(
        _pedido(routes.START_ANALYSIS_ROUTE, mudanca, metodo="POST", corpo=corpo)
    )
    assert resposta.status_code == 422
    texto = _texto(resposta)
    assert "Escolha o responsável pela análise." in texto
    assert 'value="2026-10-20"' in texto


def test_formulario_da_analise_pede_so_os_campos_do_tipo(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    comum = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, comum)
    assert "Fonte do recurso" in _texto(
        routes.impact_analysis_form(_pedido(routes.IMPACT_ROUTE, comum))
    )
    remanejamento = _registrar(sessao, usuario, projeto, tipo=models.TYPE_REALLOCATION)
    _iniciar(sessao, usuario, remanejamento)
    texto = _texto(routes.impact_analysis_form(_pedido(routes.IMPACT_ROUTE, remanejamento)))
    assert "Transferências entre itens da EAC" in texto
    assert "Fonte do recurso" not in texto
    liberacao = _registrar(sessao, usuario, projeto, tipo=models.TYPE_RESERVE_RELEASE)
    _iniciar(sessao, usuario, liberacao)
    assert "Reserva a liberar" in _texto(
        routes.impact_analysis_form(_pedido(routes.IMPACT_ROUTE, liberacao))
    )


def test_post_da_analise_valida_redireciona_e_a_ficha_mostra_a_aba(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    corpo = {**analise_valida(mudanca), "codigo": mudanca.code}
    resposta = routes.conclude_impact_analysis(
        _pedido(routes.IMPACT_ROUTE, mudanca, metodo="POST", corpo=corpo)
    )
    assert resposta.status_code == 302
    ficha = routes.change_sheet(_pedido(routes.SHEET_ROUTE, mudanca))
    texto = _texto(ficha)
    assert "Concluída em 06/10/2026" in texto
    assert "Decisão do gerente do projeto" in texto
    assert "Aditivo de orçamento" in texto
    assert "Rever análise de impacto" in texto


def test_post_da_analise_incompleta_devolve_422_por_campo_com_o_texto_digitado(
    sessao: Session,
) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    corpo = {
        "codigo": mudanca.code,
        "versao": str(mudanca.version),
        "escopo": "Texto que a pessoa digitou",
    }
    resposta = routes.conclude_impact_analysis(
        _pedido(routes.IMPACT_ROUTE, mudanca, metodo="POST", corpo=corpo)
    )
    assert resposta.status_code == 422
    texto = _texto(resposta)
    assert "Informe o impacto em custo" in texto
    assert "Informe se a mudança afeta marco contratual." in texto
    assert "Texto que a pessoa digitou" in texto
    assert mudanca.situation == models.SITUATION_ANALYSIS


def test_rebaixar_a_alcada_devolve_422_na_rota(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    corpo = {**analise_valida(mudanca, custo="500.000,00"), "codigo": mudanca.code}
    resposta = routes.conclude_impact_analysis(
        _pedido(routes.IMPACT_ROUTE, mudanca, metodo="POST", corpo=corpo)
    )
    assert resposta.status_code == 422
    assert "nunca rebaixada" in _texto(resposta)


def test_visualizador_recebe_403_nas_rotas_da_analise(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    apoio.colaborador(sessao, apoio.VISUALIZADOR, perfil="Visualizador")
    for rota, metodo in (
        (routes.START_ANALYSIS_ROUTE, "GET"),
        (routes.IMPACT_ROUTE, "GET"),
    ):
        pedido = _pedido(rota, mudanca, metodo=metodo, email=apoio.VISUALIZADOR)
        handler = (
            routes.start_analysis_form
            if rota == routes.START_ANALYSIS_ROUTE
            else routes.impact_analysis_form
        )
        assert handler(pedido).status_code == 403
    assert service.find_change_sheet(sessao, user=usuario, code=mudanca.code, reference_date=HOJE)
