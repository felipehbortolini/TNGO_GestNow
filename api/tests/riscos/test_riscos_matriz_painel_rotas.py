"""As rotas da matriz e do painel de riscos (ISSUE-066, D11, D12, D14).

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa e
a unidade de trabalho do teste (fixture ``sessao``).
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import unquote, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.riscos import panel_routes, routes, service
from tests.apoio_riscos import REFERENCIA, Cenario, nova_avaliacao, novo_risco


def _requisicao(
    usuario: User,
    *,
    metodo: str = "GET",
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, str] | None = None,
    alvo: str = "painel-conteudo",
) -> func.HttpRequest:
    headers = {
        "X-Alpine-Request": "true",
        "X-Alpine-Target": alvo,
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/riscos/painel",
        headers=headers,
        params=dict(params or {}),
        route_params={},
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def _criar(sessao: Session, cenario: Cenario) -> str:
    resultado = service.save_risk(
        sessao, user=cenario.mario, data=novo_risco(cenario), reference_date=REFERENCIA
    )
    return resultado.code


def _avaliar(sessao: Session, cenario: Cenario, codigo: str, **campos: object) -> None:
    service.assess_risk(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=nova_avaliacao(**campos),
        reference_date=REFERENCIA,
    )


def _do_projeto(cenario: Cenario) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


# ── Matriz ───────────────────────────────────────────────────────────────────────────────────


def test_a_matriz_mostra_o_visual_e_a_celula(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = panel_routes.risk_matrix_screen(
        _requisicao(cenario.mario, params=_do_projeto(cenario), alvo="matriz-conteudo")
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'data-grafico="matriz-formatada"' in corpo
    assert "celula=p3%7Ci4" in corpo
    assert "1 risco ativo" in corpo
    assert "Movimentação inerente para residual" in corpo


def test_o_registro_entende_o_filtro_da_celula(sessao: Session, cenario: Cenario) -> None:
    dentro = _criar(sessao, cenario)
    _avaliar(sessao, cenario, dentro)
    fora = _criar(sessao, cenario)
    _avaliar(sessao, cenario, fora, probability=2, impact=2, dimensions={"prazo": 2})

    resposta = routes.risk_register_screen(
        _requisicao(
            cenario.mario,
            params={**_do_projeto(cenario), "celula": "p3|i4"},
            alvo="registro-conteudo",
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Célula: P3 x I4" in corpo
    assert dentro in corpo
    assert fora not in corpo


# ── Painel ───────────────────────────────────────────────────────────────────────────────────


def test_o_painel_mostra_a_evolucao_as_categorias_e_a_pauta(
    sessao: Session, cenario: Cenario
) -> None:
    avaliado = _criar(sessao, cenario)
    _avaliar(sessao, cenario, avaliado)
    pendente = _criar(sessao, cenario)  # identificado sem avaliação: entra na pauta

    resposta = panel_routes.risk_panel_screen(
        _requisicao(cenario.mario, params=_do_projeto(cenario))
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'data-grafico="linhas-multiplas"' in corpo
    assert "Exposição por categoria (RBS)" in corpo
    assert "Técnico" in corpo
    assert "Pauta de escalonamento" in corpo
    assert pendente in corpo


def test_o_painel_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario)

    resposta = panel_routes.risk_panel_screen(_requisicao(cenario.mario))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert ">Projeto</th>" in corpo
    assert "TN-RSK-001" in corpo


# ── Envio da pauta ───────────────────────────────────────────────────────────────────────────


def test_o_modal_do_envio_traz_o_destinatario_e_a_mensagem(
    sessao: Session, cenario: Cenario
) -> None:
    _criar(sessao, cenario)

    resposta = panel_routes.risk_panel_agenda_form(
        _requisicao(cenario.mario, params=_do_projeto(cenario), alvo="riscos-pauta-modal")
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'name="mensagem"' in corpo
    assert "gerente-tn-rsk-001@example.invalid" in corpo


def test_o_envio_da_pauta_pelo_modal_responde_simulado(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario)

    resposta = panel_routes.risk_panel_agenda_send(
        _requisicao(
            cenario.mario,
            metodo="POST",
            params=_do_projeto(cenario),
            corpo={"mensagem": ""},
            alvo="riscos-pauta-modal",
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "simulado" in corpo.lower()
    assert "simulado" in unquote(resposta.headers.get("X-TN-Toast", "")).lower()


def test_visualizador_nao_envia_a_pauta(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario)

    resposta = panel_routes.risk_panel_agenda_send(
        _requisicao(
            cenario.vera,
            metodo="POST",
            params=_do_projeto(cenario),
            corpo={"mensagem": ""},
            alvo="riscos-pauta-modal",
        )
    )

    assert resposta.status_code == 403


# ── Exportações ──────────────────────────────────────────────────────────────────────────────


def test_as_exportacoes_da_matriz_saem(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    excel = panel_routes.risk_matrix_excel(
        _requisicao(cenario.mario, params=_do_projeto(cenario), alvo="matriz-conteudo")
    )
    imprimivel = panel_routes.risk_matrix_printable(
        _requisicao(cenario.mario, params=_do_projeto(cenario), alvo="matriz-conteudo")
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    assert imprimivel.status_code == 200
    assert "Matriz de riscos 5x5" in imprimivel.get_body().decode()


def test_as_exportacoes_do_painel_saem_e_o_portfolio_traz_o_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)
    _criar(sessao, cenario)  # identificado sem avaliação: entra na pauta do Portfólio

    excel = panel_routes.risk_panel_excel(_requisicao(cenario.mario))
    imprimivel = panel_routes.risk_panel_printable(_requisicao(cenario.mario))

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    assert imprimivel.status_code == 200
    assert "Painel de riscos" in imprimivel.get_body().decode()
