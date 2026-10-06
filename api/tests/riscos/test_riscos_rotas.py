"""As rotas do Registro de riscos (ISSUE-064, D14): a tela, o novo risco, a avaliação e as recusas.

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
from src.modulos.riscos import routes, service
from src.modulos.riscos.validation import DeletionInput
from tests.apoio_riscos import REFERENCIA, Cenario, novo_risco


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
        "X-Alpine-Target": "registro-conteudo",
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/riscos/registro",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def _criar(sessao: Session, cenario: Cenario, **campos: object) -> str:
    resultado = service.save_risk(
        sessao, user=cenario.mario, data=novo_risco(cenario, **campos), reference_date=REFERENCIA
    )
    return resultado.code


# ── A tela ───────────────────────────────────────────────────────────────────


def test_a_tela_mostra_o_contexto_os_kpis_e_o_risco(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)

    resposta = routes.risk_register_screen(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert codigo in corpo
    assert "Atraso na liberação dos desenhos" in corpo
    assert "Apetite" in corpo
    assert "registro__tabela" in corpo


def test_a_tela_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario)

    corpo = routes.risk_register_screen(_requisicao(cenario.mario)).get_body().decode()

    assert ">Projeto</th>" in corpo
    assert "TN-RSK-001" in corpo


def test_o_excel_sai_no_mesmo_filtro(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario)

    resposta = routes.risk_register_excel(_requisicao(cenario.mario, params={"situacao": "ativos"}))

    assert resposta.status_code == 200
    assert resposta.get_body().startswith(b"PK")


# ── Novo risco ───────────────────────────────────────────────────────────────


def _novo_form(cenario: Cenario) -> dict[str, str]:
    return {
        "natureza": "Ameaça",
        "categoria": str(cenario.categorias[0].id),
        "causa": "Falha no fornecimento do aço estrutural.",
        "titulo": "Falta de aço estrutural",
        "consequencia": "A estrutura atrasa e a equipe fica parada.",
        "donoId": str(cenario.mario.person_id),
        "identificadoEm": REFERENCIA.isoformat(),
        "origemTipo": "Manual",
        "projeto": str(cenario.projeto.id),
        "versao": "",
        "consulta": "",
    }


def test_o_formulario_de_novo_risco_salva_e_devolve_a_tela(cenario: Cenario) -> None:
    resposta = routes.new_risk_save(
        _requisicao(cenario.mario, metodo="POST", corpo=_novo_form(cenario))
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert "RSK-0001" in corpo
    assert "Falta de aço estrutural" in corpo


def test_no_portfolio_o_formulario_pede_o_projeto(cenario: Cenario) -> None:
    resposta = routes.new_risk_form(_requisicao(cenario.mario))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'name="projeto"' in corpo
    assert "Escolha" in corpo


def test_visualizador_nao_salva_risco(cenario: Cenario) -> None:
    resposta = routes.new_risk_save(
        _requisicao(cenario.vera, metodo="POST", corpo=_novo_form(cenario))
    )

    assert resposta.status_code == 403
    assert "perfil" in resposta.get_body().decode()


# ── Avaliação ────────────────────────────────────────────────────────────────


def _avaliacao(**campos: str) -> dict[str, str]:
    corpo = {
        "tipo": "inerente",
        "p": "3",
        "i": "4",
        "d_prazo": "4",
        "d_custo": "2",
        "d_escopo": "",
        "d_sms": "",
        "d_imagem": "",
        "d_legal": "",
        "impactoPrazoDias": "10",
        "impactoCustoCentavos": "100.000,00",
        "riscoVida": "",
        "justificativa": "",
        "versao": "0",
        "consulta": "",
    }
    corpo.update(campos)
    return corpo


def test_a_avaliacao_atualiza_a_tela_com_o_score(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    linha = service.find_risk(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert linha is not None

    resposta = routes.assess_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_avaliacao(versao=str(linha.version)),
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Avaliação inerente registrada" in unquote(resposta.headers.get("X-TN-Toast", ""))
    assert "Em análise" in corpo
    avaliado = service.find_risk(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert avaliado is not None and avaliado.inherent is not None


def test_impacto_reduzido_devolve_422_com_a_mensagem_no_formulario(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)

    resposta = routes.assess_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_avaliacao(i="2"),
            rota={"codigo": codigo},
        )
    )

    assert resposta.status_code == 422
    assert "maior dimensão" in resposta.get_body().decode()


def test_restaurar_sem_admin_devolve_403(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    linha = service.find_risk(sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA)
    assert linha is not None
    service.delete_risk(
        sessao,
        user=cenario.gil,
        code=codigo,
        data=DeletionInput(reason="Criado por engano", note="", version=linha.version),
        reference_date=REFERENCIA,
    )

    resposta = routes.restore_save(_requisicao(cenario.gil, metodo="POST", rota={"codigo": codigo}))

    assert resposta.status_code == 403
