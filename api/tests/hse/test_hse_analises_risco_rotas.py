"""Rotas das Análises de risco do HSE (ISSUE-074, D14): a tela, a ficha, os formulários e as recusas.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa e
a unidade de trabalho do teste (fixture ``sessao``). A criação da ação e o fechamento da
recomendação gravam pela fachada da Central na mesma transação; a segunda ação da mesma
recomendação volta com a mensagem do protótipo no modal.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import unquote, urlencode

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.hse import analises_risco_routes as routes
from src.modulos.hse import service
from tests.apoio_hse import REFERENCIA, Cenario, analise_de, usuario_de
from tests.identidades import criar_colaborador

ALVO = "analises-risco-conteudo"
MODAL = "analises-risco-modal-corpo"


def _requisicao(
    usuario: User,
    *,
    metodo: str = "GET",
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, object] | None = None,
    rota: Mapping[str, str] | None = None,
) -> func.HttpRequest:
    headers = {
        "X-Alpine-Request": "true",
        "X-Alpine-Target": ALVO,
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/hse/analises-risco",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo, doseq=True).encode() if corpo is not None else b"",
    )


def _corpo_nova(cenario: Cenario, **campos: object) -> dict[str, object]:
    dados = analise_de(cenario)
    rec = dados.recommendations[0]
    corpo: dict[str, object] = {
        "tipo": dados.kind,
        "area": dados.area,
        "titulo": dados.title,
        "data": dados.held_on.isoformat(),
        "participantes": [str(person_id) for person_id in dados.participant_ids],
        "rec_descricao_1": rec.description,
        "rec_responsavel_1": str(rec.responsible_id),
        "rec_prazo_1": rec.due_date.isoformat(),
        "consulta": "",
    }
    corpo.update(campos)
    return corpo


def _registrar(sessao: Session, cenario: Cenario, **campos: object) -> str:
    salva = service.save_analysis(
        sessao,
        user=cenario.maria,
        data=analise_de(cenario, **campos),
        reference_date=REFERENCIA,
    )
    return salva.code


# ── A tela e as exportações ─────────────────────────────────────────────────────────────────


def test_a_tela_traz_os_indicadores_e_o_estudo(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)

    resposta = routes.risk_study_screen(
        _requisicao(cenario.maria, params={"projeto": str(cenario.projeto.id)})
    )
    corpo = resposta.get_body().decode()

    assert resposta.status_code == 200
    assert "Estudos registrados" in corpo
    assert "Recomendações abertas" in corpo
    assert "Recomendações atrasadas" in corpo
    assert "Recomendações fechadas" in corpo
    assert codigo in corpo
    assert "Novo estudo" in corpo


def test_a_tela_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    _registrar(sessao, cenario)

    corpo = routes.risk_study_screen(_requisicao(cenario.maria)).get_body().decode()

    assert ">Projeto</th>" in corpo
    assert "TN-HSE-001" in corpo


def test_os_filtros_da_tela_recortam_a_lista(sessao: Session, cenario: Cenario) -> None:
    apr = _registrar(sessao, cenario)
    hazop = _registrar(sessao, cenario, kind="HAZOP", title="Circuito de reagentes")

    so_hazop = (
        routes.risk_study_screen(
            _requisicao(
                cenario.maria,
                params={"projeto": str(cenario.projeto.id), "tipo": "HAZOP"},
            )
        )
        .get_body()
        .decode()
    )
    com_busca = (
        routes.risk_study_screen(
            _requisicao(
                cenario.maria,
                params={"projeto": str(cenario.projeto.id), "busca": "reagentes"},
            )
        )
        .get_body()
        .decode()
    )

    assert hazop in so_hazop and apr not in so_hazop
    assert "1 estudo encontrado" in so_hazop
    assert hazop in com_busca and apr not in com_busca


def test_o_excel_e_o_imprimivel_saem_no_mesmo_filtro(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)

    excel = routes.risk_study_excel(
        _requisicao(cenario.maria, params={"projeto": str(cenario.projeto.id)})
    )
    imprimivel = routes.risk_study_printable(
        _requisicao(cenario.maria, params={"projeto": str(cenario.projeto.id)})
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    assert imprimivel.status_code == 200
    assert "Análises de risco (APR/HAZOP)" in imprimivel.get_body().decode()
    assert codigo in imprimivel.get_body().decode()


def test_o_imprimivel_no_portfolio_traz_a_coluna_de_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    _registrar(sessao, cenario)

    imprimivel = routes.risk_study_printable(_requisicao(cenario.maria))

    assert ">Projeto</th>" in imprimivel.get_body().decode()


# ── A ficha (modal) ──────────────────────────────────────────────────────────────────────────


def test_a_ficha_traz_as_recomendacoes_e_as_acoes(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)

    resposta = routes.risk_study_sheet_fragment(_requisicao(cenario.maria, rota={"codigo": codigo}))
    corpo = resposta.get_body().decode()

    assert resposta.status_code == 200
    assert MODAL in corpo
    assert "Plano de rigging" in corpo
    assert "Criar ação" in corpo
    assert "Fechar" in corpo
    assert "Moagem 210" in corpo


def test_a_ficha_mostra_o_status_da_acao_da_recomendacao(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)
    service.create_recommendation_action(
        sessao, user=cenario.maria, code=codigo, position=1, reference_date=REFERENCIA
    )

    corpo = (
        routes.risk_study_sheet_fragment(_requisicao(cenario.gil, rota={"codigo": codigo}))
        .get_body()
        .decode()
    )

    assert "Em andamento" in corpo
    assert "Criar ação" not in corpo, "a recomendação já tem ação"


def test_a_ficha_de_estudo_inexistente_e_recusada(cenario: Cenario) -> None:
    resposta = routes.risk_study_sheet_fragment(
        _requisicao(cenario.maria, rota={"codigo": "APR-TN-2026-9999"})
    )

    assert resposta.status_code == 422


# ── O formulário do novo estudo ──────────────────────────────────────────────────────────────


def test_o_formulario_da_nova_recusa_e_volta_no_modal(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo_nova(cenario)
    corpo["titulo"] = "abc"

    resposta = routes.risk_study_new_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            corpo=corpo,
        )
    )

    assert resposta.status_code == 422
    assert MODAL in resposta.get_body().decode()
    assert "título do estudo" in resposta.get_body().decode()
    assert service.analysis_by_code(sessao, "APR-TN-2026-0001") is None


def test_a_nova_grava_e_devolve_a_lista_com_a_ficha_para_reabrir(cenario: Cenario) -> None:
    resposta = routes.risk_study_new_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            corpo=_corpo_nova(cenario),
        )
    )
    corpo = resposta.get_body().decode()

    assert resposta.status_code == 200
    assert ALVO in corpo
    assert "APR-TN-2026-0001" in corpo
    assert 'data-analises-risco-abrir-ficha="APR-TN-2026-0001"' in corpo
    tosta = unquote(resposta.headers.get("X-TN-Toast", ""))
    assert tosta == "Estudo APR-TN-2026-0001 registrado."


def test_a_nova_no_portfolio_pede_o_projeto_no_modal(cenario: Cenario) -> None:
    resposta = routes.risk_study_new_form(_requisicao(cenario.maria, params={"consulta": ""}))

    assert resposta.status_code == 422
    assert "Escolha um projeto" in resposta.get_body().decode()


# ── A ação na Central e o fechamento ────────────────────────────────────────────────────────


def test_o_envio_da_acao_cria_na_central_e_atualiza_a_lista(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)

    resposta = routes.risk_study_action_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            rota={"codigo": codigo, "ordem": "1"},
            corpo={"consulta": ""},
        )
    )

    assert resposta.status_code == 200
    assert unquote(resposta.headers.get("X-TN-Toast", "")) == "Ação criada na Central."
    assert f'data-analises-risco-abrir-ficha="{codigo}"' in resposta.get_body().decode()
    ficha = service.analysis_sheet(sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA)
    assert ficha is not None and ficha.line.recommendations[0].action is not None


def test_a_acao_duplicada_volta_com_a_mensagem_do_prototipo(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)
    service.create_recommendation_action(
        sessao, user=cenario.maria, code=codigo, position=1, reference_date=REFERENCIA
    )

    resposta = routes.risk_study_action_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            rota={"codigo": codigo, "ordem": "1"},
            corpo={"consulta": ""},
        )
    )

    assert resposta.status_code == 422
    assert MODAL in resposta.get_body().decode()
    assert "Já existe uma ação na Central para esta recomendação." in resposta.get_body().decode()


def test_o_fechamento_da_recomendacao_pela_rota_conclui_a_acao(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)
    record = service.create_recommendation_action(
        sessao, user=cenario.maria, code=codigo, position=1, reference_date=REFERENCIA
    )

    resposta = routes.risk_study_close_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            rota={"codigo": codigo, "ordem": "1"},
            corpo={
                "data": REFERENCIA.isoformat(),
                "evidencia": "Verificação em campo assinada.",
                "consulta": "",
            },
        )
    )

    assert resposta.status_code == 200
    assert unquote(resposta.headers.get("X-TN-Toast", "")) == "Recomendação fechada."
    ficha = service.analysis_sheet(sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA)
    assert ficha is not None
    recomendacao = ficha.line.recommendations[0]
    assert recomendacao.is_closed and recomendacao.closed_on == REFERENCIA
    assert recomendacao.action is not None and recomendacao.action.id == record.id
    assert recomendacao.action.status_label == "Concluída"


def test_o_formulario_do_fechamento_e_recusado_ao_visualizador(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)
    vendo = usuario_de(
        sessao,
        criar_colaborador(
            sessao,
            email="vera.rotas@example.invalid",
            nome="Vera Visualizadora",
            perfil="Visualizador",
        ),
    )

    resposta = routes.risk_study_close_form(
        _requisicao(vendo, rota={"codigo": codigo, "ordem": "1"})
    )

    assert resposta.status_code == 403
    assert MODAL in resposta.get_body().decode()


def test_o_fechamento_sem_data_volta_no_modal(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)

    resposta = routes.risk_study_close_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            rota={"codigo": codigo, "ordem": "1"},
            corpo={"data": "", "evidencia": "", "consulta": ""},
        )
    )

    assert resposta.status_code == 422
    assert MODAL in resposta.get_body().decode()
    assert "data de conclusão" in resposta.get_body().decode()


@pytest.mark.parametrize("origem", ["ficha", "fechar", "acao"])
def test_estudo_inexistente_na_rota_do_modal(origem: str, cenario: Cenario) -> None:
    rota = {"codigo": "APR-TN-2026-9999", "ordem": "1"}
    if origem == "ficha":
        resposta = routes.risk_study_sheet_fragment(_requisicao(cenario.maria, rota=rota))
    elif origem == "fechar":
        resposta = routes.risk_study_close_form(_requisicao(cenario.maria, rota=rota))
    else:
        resposta = routes.risk_study_action_save(
            _requisicao(
                cenario.maria,
                metodo="POST",
                params={"projeto": str(cenario.projeto.id)},
                rota=rota,
                corpo={"consulta": ""},
            )
        )

    assert resposta.status_code == 422
