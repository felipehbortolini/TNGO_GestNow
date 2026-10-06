"""As rotas da tela Análises de risco (ISSUE-074, D14): tela, filtros, novo estudo, fechar e ação.

O handler é chamado com a requisição de Alpine, o seletor da demonstração identificando a pessoa e
a unidade de trabalho do teste (fixture ``sessao``). O escopo vem de ``?projeto=``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.hse import analysis_routes as routes
from src.modulos.hse import analysis_service as analyses
from src.modulos.hse.analysis_service import RecommendationRef
from src.modulos.hse.validation import (
    AnalysisInput,
    ClosingRecommendationInput,
    RecommendationInput,
)
from tests.apoio_acoes import REFERENCIA, Cenario


@dataclass(frozen=True)
class Chamada:
    """O que varia entre as requisições dos testes: método, alvo do Alpine, query, corpo e rota."""

    metodo: str = "GET"
    alvo: str = "analises-conteudo"
    params: Mapping[str, str] = field(default_factory=dict)
    corpo: Sequence[tuple[str, str]] | None = None
    rota: Mapping[str, str] = field(default_factory=dict)


def _requisicao(
    usuario: User, cenario: Cenario, chamada: Chamada | None = None
) -> func.HttpRequest:
    chamada = chamada or Chamada()
    headers = {
        "X-Alpine-Request": "true",
        "X-Alpine-Target": chamada.alvo,
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if chamada.corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=chamada.metodo,
        url="/api/hse/analises-de-risco",
        headers=headers,
        params={"projeto": str(cenario.projeto_a.id), **chamada.params},
        route_params=dict(chamada.rota),
        body=urlencode(list(chamada.corpo)).encode() if chamada.corpo is not None else b"",
    )


def _corpo(response: func.HttpResponse) -> str:
    return response.get_body().decode()


def _registrar(session: Session, cenario: Cenario) -> str:
    saved = analyses.save_analysis(
        session,
        user=cenario.mario,
        data=AnalysisInput(
            project_id=cenario.projeto_a.id,
            kind="HAZOP",
            area="Reator R-101",
            title="Revisão de segurança do reator",
            studied_on=REFERENCIA - timedelta(days=3),
            participant_ids=(cenario.gil.person_id,),
            recommendations=(
                RecommendationInput(
                    description="Instalar válvula de alívio redundante.",
                    responsible_id=cenario.gil.person_id,
                    due_date=REFERENCIA - timedelta(days=1),
                ),
            ),
        ),
        reference_date=REFERENCIA,
    )
    return saved.code


def _formulario_novo(cenario: Cenario, **campos: str) -> list[tuple[str, str]]:
    base = {
        "tipo": "APR",
        "data": REFERENCIA.isoformat(),
        "area": "Moagem 210",
        "titulo": "Içamento da carcaça do moinho",
        "rec_descricao_1": "Plano de rigging assinado.",
        "rec_responsavel_1": str(cenario.gil.person_id),
        "rec_prazo_1": (REFERENCIA + timedelta(days=7)).isoformat(),
        "rec_descricao_2": "",
    }
    pairs = list({**base, **campos}.items())
    pairs.append(("participantes", str(cenario.gil.person_id)))
    pairs.append(("participantes", str(cenario.mario.person_id)))
    return pairs


def _tela(cenario: Cenario, chamada: Chamada | None = None) -> func.HttpResponse:
    return routes.analysis_screen.get_user_function()(_requisicao(cenario.mario, cenario, chamada))


def _modal(*, rota: Mapping[str, str], corpo: Sequence[tuple[str, str]] | None = None) -> Chamada:
    return Chamada(
        metodo="POST" if corpo is not None else "GET",
        alvo="hse-modal-corpo",
        corpo=corpo,
        rota=rota,
    )


def test_tela_mostra_o_estudo_os_indicadores_e_a_recomendacao_atrasada(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)

    resposta = _tela(cenario)

    html = _corpo(resposta)
    assert resposta.status_code == 200
    assert code in html
    assert "Revisão de segurança do reator" in html
    assert "Recomendações atrasadas" in html
    assert "1 atrasada" in html
    assert "data-hse-auto" not in html


def test_tela_sem_estudo_mostra_o_vazio_de_origem(cenario: Cenario) -> None:
    assert 'data-estado="vazio-origem"' in _corpo(_tela(cenario))


def test_filtro_sem_resultado_mostra_o_vazio_por_filtro(sessao: Session, cenario: Cenario) -> None:
    _registrar(sessao, cenario)

    resposta = _tela(cenario, Chamada(params={"busca": "nada disso"}))

    assert 'data-estado="vazio-filtro"' in _corpo(resposta)


def test_filtro_responde_so_os_dois_blocos(sessao: Session, cenario: Cenario) -> None:
    _registrar(sessao, cenario)

    resposta = _tela(
        cenario, Chamada(alvo="analises-kpis analises-tabela", params={"tipo": "HAZOP"})
    )

    html = _corpo(resposta)
    assert 'id="analises-kpis"' in html
    assert 'id="analises-tabela"' in html
    assert 'id="analises-conteudo"' not in html


def test_link_da_acao_abre_o_estudo_pelo_codigo_exato(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)

    assert "data-hse-auto" in _corpo(_tela(cenario, Chamada(params={"busca": code})))


def test_novo_estudo_grava_e_responde_a_tela_com_o_codigo(cenario: Cenario) -> None:
    chamada = Chamada(metodo="POST", corpo=_formulario_novo(cenario))

    resposta = routes.analysis_new_save.get_user_function()(
        _requisicao(cenario.mario, cenario, chamada)
    )

    assert resposta.status_code == 200
    assert "APR-TN-2026-0001" in _corpo(resposta)


def test_novo_estudo_sem_recomendacao_volta_o_formulario_com_422(cenario: Cenario) -> None:
    chamada = Chamada(
        metodo="POST",
        alvo="hse-modal-corpo",
        corpo=_formulario_novo(cenario, rec_descricao_1=""),
    )

    resposta = routes.analysis_new_save.get_user_function()(
        _requisicao(cenario.mario, cenario, chamada)
    )

    assert resposta.status_code == 422
    assert "Inclua ao menos uma recomendação." in _corpo(resposta)
    assert "Içamento da carcaça do moinho" in _corpo(resposta)


def test_novo_estudo_no_portfolio_pede_o_projeto(cenario: Cenario) -> None:
    requisicao = _requisicao(cenario.mario, cenario, Chamada(params={"projeto": "portfolio"}))

    resposta = routes.analysis_new_form.get_user_function()(requisicao)

    assert resposta.status_code == 422


def test_visualizador_nao_abre_o_formulario(cenario: Cenario) -> None:
    resposta = routes.analysis_new_form.get_user_function()(_requisicao(cenario.vera, cenario))

    assert resposta.status_code == 403


def test_estudo_abre_com_as_recomendacoes_e_o_botao_criar_acao(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)

    resposta = routes.analysis_view.get_user_function()(
        _requisicao(cenario.mario, cenario, _modal(rota={"codigo": code}))
    )

    html = _corpo(resposta)
    assert "Instalar válvula de alívio redundante." in html
    assert "Criar ação" in html
    assert "Sem ação" in html


def test_criar_acao_mostra_a_situacao_da_acao_no_estudo(sessao: Session, cenario: Cenario) -> None:
    code = _registrar(sessao, cenario)
    chamada = _modal(rota={"codigo": code, "ordem": "1"}, corpo=[])

    resposta = routes.recommendation_action.get_user_function()(
        _requisicao(cenario.mario, cenario, chamada)
    )

    html = _corpo(resposta)
    assert resposta.status_code == 200
    assert "Sem ação" not in html
    assert "Criar ação" not in html


def test_segunda_acao_da_mesma_recomendacao_volta_a_mensagem_no_estudo(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)
    analyses.create_recommendation_action(
        sessao, user=cenario.mario, code=code, position=1, reference_date=REFERENCIA
    )
    chamada = _modal(rota={"codigo": code, "ordem": "1"}, corpo=[])

    resposta = routes.recommendation_action.get_user_function()(
        _requisicao(cenario.mario, cenario, chamada)
    )

    assert resposta.status_code == 422
    assert "Já existe uma ação na Central para esta recomendação." in _corpo(resposta)


def test_fechar_a_recomendacao_pela_rota_atualiza_o_estudo(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)
    corpo = [("data", REFERENCIA.isoformat()), ("evidencia", "Válvula instalada."), ("versao", "1")]
    chamada = _modal(rota={"codigo": code, "ordem": "1"}, corpo=corpo)

    resposta = routes.recommendation_close_save.get_user_function()(
        _requisicao(cenario.mario, cenario, chamada)
    )

    assert resposta.status_code == 200
    assert "Evidência: Válvula instalada." in _corpo(resposta)


def test_fechar_com_data_futura_volta_o_formulario_com_a_mensagem(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)
    corpo = [("data", (REFERENCIA + timedelta(days=1)).isoformat()), ("versao", "1")]
    chamada = _modal(rota={"codigo": code, "ordem": "1"}, corpo=corpo)

    resposta = routes.recommendation_close_save.get_user_function()(
        _requisicao(cenario.mario, cenario, chamada)
    )

    assert resposta.status_code == 422
    assert "A data não pode ser posterior à referência." in _corpo(resposta)


def test_fechar_com_versao_velha_volta_o_formulario_com_409(
    sessao: Session, cenario: Cenario
) -> None:
    code = _registrar(sessao, cenario)
    analyses.close_recommendation(
        sessao,
        user=cenario.gil,
        target=RecommendationRef(code=code, position=1),
        data=ClosingRecommendationInput(closed_on=REFERENCIA, version=1),
        reference_date=REFERENCIA,
    )
    corpo = [("data", REFERENCIA.isoformat()), ("versao", "1")]
    chamada = _modal(rota={"codigo": code, "ordem": "1"}, corpo=corpo)

    resposta = routes.recommendation_close_save.get_user_function()(
        _requisicao(cenario.mario, cenario, chamada)
    )

    assert resposta.status_code in {409, 422}


def test_excel_e_pdf_saem_com_os_indicadores_e_a_tabela(sessao: Session, cenario: Cenario) -> None:
    _registrar(sessao, cenario)

    excel = routes.analysis_excel.get_user_function()(_requisicao(cenario.mario, cenario))
    pdf = routes.analysis_printable.get_user_function()(_requisicao(cenario.mario, cenario))

    assert excel.status_code == 200
    assert excel.get_body()[:2] == b"PK"
    assert "Recomendações fechadas" in _corpo(pdf)
    assert "HAZOP" in _corpo(pdf)
