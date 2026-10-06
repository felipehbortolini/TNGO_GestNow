"""Rotas de mudanças (ISSUE-023): 422 com o formulário de volta, 403, redirecionamento e a ficha."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.modulos.governanca import models, routes, service
from tests.governanca import apoio
from tests.governanca.apoio import HOJE
from tests.identidades import requisicao


def _cenario(sessao: Session):
    projeto = apoio.projeto_com_orcamento(sessao)
    membro = apoio.colaborador(sessao, apoio.MEMBRO)
    return projeto, membro, apoio.usuario_de(membro)


def _texto(resposta) -> str:
    return resposta.get_body().decode()


def test_post_valido_registra_e_redireciona_para_a_ficha(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    resposta = routes.register_change(
        requisicao(
            "/api/governanca/mudancas",
            metodo="POST",
            email=apoio.MEMBRO,
            params={"projeto": str(projeto.id)},
            corpo=apoio.solicitacao_valida(),
        )
    )
    assert resposta.status_code == 302
    local = resposta.headers["Location"]
    assert local.startswith("/governanca/mudanca?codigo=SM-TN-2026-0001")
    assert f"projeto={projeto.id}" in local
    ficha = service.find_change_sheet(
        sessao, user=usuario, code="SM-TN-2026-0001", reference_date=HOJE
    )
    assert ficha is not None
    assert ficha.change.situation == models.SITUATION_REGISTERED


def test_post_sem_titulo_devolve_422_com_o_formulario_preenchido(sessao: Session) -> None:
    projeto, _, _ = _cenario(sessao)
    resposta = routes.register_change(
        requisicao(
            "/api/governanca/mudancas",
            metodo="POST",
            email=apoio.MEMBRO,
            params={"projeto": str(projeto.id)},
            corpo=apoio.solicitacao_valida(titulo="", descricao="Descrição que o usuário digitou."),
        )
    )
    assert resposta.status_code == 422
    corpo = _texto(resposta)
    assert "Título é obrigatório." in corpo
    assert "Descrição que o usuário digitou." in corpo


def test_post_do_visualizador_e_403(sessao: Session) -> None:
    projeto, _, _ = _cenario(sessao)
    apoio.colaborador(sessao, apoio.VISUALIZADOR, perfil="Visualizador")
    resposta = routes.register_change(
        requisicao(
            "/api/governanca/mudancas",
            metodo="POST",
            email=apoio.VISUALIZADOR,
            params={"projeto": str(projeto.id)},
            corpo=apoio.solicitacao_valida(),
        )
    )
    assert resposta.status_code == 403


def test_formulario_da_nova_solicitacao_no_portfolio_pede_projeto(sessao: Session) -> None:
    _cenario(sessao)
    resposta = routes.new_change_form(
        requisicao("/api/governanca/mudancas/nova", email=apoio.MEMBRO)
    )
    assert resposta.status_code == 422


def test_registro_lista_a_solicitacao_com_numero_e_situacao(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    apoio.registrar(sessao, usuario, projeto)
    resposta = routes.change_register(
        requisicao(
            "/api/governanca/mudancas", email=apoio.MEMBRO, params={"projeto": str(projeto.id)}
        )
    )
    assert resposta.status_code == 200
    corpo = _texto(resposta)
    assert "SM-TN-2026-0001" in corpo
    assert models.SITUATION_REGISTERED in corpo


def test_registro_filtrado_sem_resultado_mostra_o_vazio_do_filtro(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    apoio.registrar(sessao, usuario, projeto)
    resposta = routes.change_register(
        requisicao(
            "/api/governanca/mudancas",
            email=apoio.MEMBRO,
            params={"projeto": str(projeto.id), "busca": "nada-assim"},
        )
    )
    assert 'data-estado="vazio-filtro"' in _texto(resposta)


def test_ficha_existente_e_inexistente(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    codigo = apoio.registrar(sessao, usuario, projeto).code
    pedido = requisicao(
        "/api/governanca/mudanca",
        email=apoio.MEMBRO,
        params={"codigo": codigo, "projeto": str(projeto.id)},
    )
    ficha = routes.change_sheet(pedido)
    assert ficha.status_code == 200
    assert codigo in _texto(ficha)
    ausente = routes.change_sheet(
        requisicao(
            "/api/governanca/mudanca",
            email=apoio.MEMBRO,
            params={"codigo": "SM-X", "projeto": str(projeto.id)},
        )
    )
    assert ausente.status_code == 404


def _cancelar(codigo: str, email: str, projeto_id: int, justificativa: str = "x" * 12):
    return routes.cancel_change_request(
        requisicao(
            "/api/governanca/mudanca/cancelar",
            metodo="POST",
            email=email,
            params={"projeto": str(projeto_id)},
            corpo={"codigo": codigo, "justificativa": justificativa, "versao": "1"},
        )
    )


def test_cancelamento_pelo_solicitante_volta_para_a_ficha(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    codigo = apoio.registrar(sessao, usuario, projeto).code
    resposta = _cancelar(codigo, apoio.MEMBRO, projeto.id)
    assert resposta.status_code == 302
    assert codigo in resposta.headers["Location"]


def test_cancelamento_por_outro_membro_e_403(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    apoio.colaborador(sessao, apoio.OUTRO_MEMBRO)
    codigo = apoio.registrar(sessao, usuario, projeto).code
    assert _cancelar(codigo, apoio.OUTRO_MEMBRO, projeto.id).status_code == 403


def test_cancelamento_sem_justificativa_e_422_com_a_mensagem(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    codigo = apoio.registrar(sessao, usuario, projeto).code
    resposta = _cancelar(codigo, apoio.MEMBRO, projeto.id, justificativa="")
    assert resposta.status_code == 422
    assert "Justificativa do cancelamento é obrigatório." in _texto(resposta)


def test_cancelamento_de_sm_aprovada_e_recusado(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    service.load_demonstration_change(
        sessao,
        author_id=membro.id,
        seed=apoio.semente(projeto, membro.person_id, "SM-TN-2026-0001", models.SITUATION_APPROVED),
        reference_date=HOJE,
    )
    resposta = _cancelar("SM-TN-2026-0001", apoio.MEMBRO, projeto.id)
    assert resposta.status_code == 422
    assert "registre nova SM" in _texto(resposta)
