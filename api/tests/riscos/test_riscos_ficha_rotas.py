"""Rotas da ficha do risco (ISSUE-065, D14): a tela, os modais, as recusas e os 403.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa e
a unidade de trabalho do teste (fixture ``sessao``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import unquote, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.governanca import service as governanca
from src.modulos.riscos import ficha_routes, service
from tests.apoio_riscos import REFERENCIA, Cenario, nova_avaliacao, novo_risco

PLAN_TEXT = "Antecipar as entregas condicionantes e negociar prioridade com o fornecedor."
ACCEPT_TEXT = "Aceito com base no cadastro de interferências do cliente e na reserva."
LESSON_TEXT = "Estoque de segurança de insumos críticos reduziu a exposição logística."


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
        "X-Alpine-Target": "ficha-conteudo",
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/riscos/ficha",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def _criar(sessao: Session, cenario: Cenario, **campos: object) -> str:
    return service.save_risk(
        sessao, user=cenario.mario, data=novo_risco(cenario, **campos), reference_date=REFERENCIA
    ).code


def _avaliar(sessao: Session, cenario: Cenario, codigo: str, **campos: object):
    return service.assess_risk(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=nova_avaliacao(**campos),
        reference_date=REFERENCIA,
    )


def _plano_form(cenario: Cenario, **campos: str) -> dict[str, str]:
    corpo = {
        "estrategia": "Mitigar",
        "plano": PLAN_TEXT,
        "instrumento": "",
        "smRef": "",
        "severidadeAlvo": "baixo",
        "prazoAlvo": (REFERENCIA + timedelta(days=30)).isoformat(),
        "custoRespostaCentavos": "",
        "responsavelPlanoId": str(cenario.mario.person_id),
        "exigirAprovacao": "",
        "versao": "",
    }
    corpo.update(campos)
    return corpo


def _encerrar_form(**campos: str) -> dict[str, str]:
    corpo = {
        "motivo": "Não se materializou",
        "data": REFERENCIA.isoformat(),
        "duplicadoDe": "",
        "impactoRealPrazoDias": "0",
        "impactoRealCustoCentavos": "0,00",
        "gerarAcao": "1",
        "acaoAssunto": "Tratar o problema decorrente do risco",
        "acaoResponsavelId": "",
        "acaoPrevista": (REFERENCIA + timedelta(days=7)).isoformat(),
        "abrirSm": "",
        "licao": LESSON_TEXT,
        "versao": "",
    }
    corpo.update(campos)
    return corpo


# ── A tela e as exportações ──────────────────────────────────────────────────────────────────


def test_a_ficha_mostra_o_risco_e_as_abas(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_ficha_screen(_requisicao(cenario.mario, params={"codigo": codigo}))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert codigo in corpo
    assert "Atraso na liberação dos desenhos" in corpo
    assert "ficha__faixa" in corpo
    assert "Monitoramento" in corpo


def test_ficha_de_risco_inexistente_devolve_404(cenario: Cenario) -> None:
    resposta = ficha_routes.risk_ficha_screen(
        _requisicao(cenario.mario, params={"codigo": "RSK-9999"})
    )

    assert resposta.status_code == 404


def test_o_excel_da_ficha_sai(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_ficha_excel(_requisicao(cenario.mario, params={"codigo": codigo}))

    assert resposta.status_code == 200
    assert resposta.get_body().startswith(b"PK")


def test_o_imprimivel_da_ficha_sai(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_ficha_printable(
        _requisicao(cenario.mario, params={"codigo": codigo})
    )

    assert resposta.status_code == 200
    assert "Ficha do risco" in resposta.get_body().decode()


# ── Plano de resposta ────────────────────────────────────────────────────────────────────────


def test_o_formulario_do_plano_abre_no_modal(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_plan_form(_requisicao(cenario.mario, rota={"codigo": codigo}))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Plano de resposta" in corpo
    assert f'action="/api/riscos/{codigo}/plano"' in corpo


def test_plano_salvo_devolve_a_ficha_atualizada(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(
        sessao,
        cenario,
        codigo,
        probability=2,
        impact=2,
        dimensions={"prazo": 2},
        cost_impact_cents=10_000_000,
    )

    resposta = ficha_routes.risk_plan_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_plano_form(cenario),
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Em tratamento" in corpo
    assert unquote(resposta.headers.get("X-TN-Toast", ""))


def test_recusa_do_plano_volta_no_modal(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_plan_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_plano_form(cenario, estrategia="Transferir", instrumento=""),
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert "instrumento da transferência" in corpo


def test_visualizador_nao_salva_plano(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_plan_save(
        _requisicao(
            cenario.vera,
            metodo="POST",
            corpo=_plano_form(cenario),
            rota={"codigo": codigo},
        )
    )

    assert resposta.status_code == 403


# ── Aprovação ────────────────────────────────────────────────────────────────────────────────


def _plano_pendente(sessao: Session, cenario: Cenario) -> str:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo, probability=4, impact=4)
    resposta = ficha_routes.risk_plan_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_plano_form(
                cenario,
                estrategia="Aceitar",
                plano=ACCEPT_TEXT,
                severidadeAlvo="moderado",
            ),
            rota={"codigo": codigo},
        )
    )
    assert resposta.status_code == 200
    return codigo


def test_aprovar_plano_pela_rota(sessao: Session, cenario: Cenario) -> None:
    codigo = _plano_pendente(sessao, cenario)

    resposta = ficha_routes.risk_plan_approval_save(
        _requisicao(
            cenario.ada,
            metodo="POST",
            corpo={"decisao": "Aprovado", "comentario": "", "versao": ""},
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Monitorado" in corpo


def test_responsavel_pelo_plano_recebe_403_na_aprovacao(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo, probability=4, impact=4)
    ficha_routes.risk_plan_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_plano_form(
                cenario,
                estrategia="Aceitar",
                plano=ACCEPT_TEXT,
                severidadeAlvo="moderado",
                responsavelPlanoId=str(cenario.gil.person_id),
            ),
            rota={"codigo": codigo},
        )
    )

    resposta = ficha_routes.risk_plan_approval_save(
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo={"decisao": "Aprovado", "comentario": "", "versao": ""},
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 403
    assert "segregação de funções" in corpo


def test_membro_nao_aprova_plano(sessao: Session, cenario: Cenario) -> None:
    codigo = _plano_pendente(sessao, cenario)

    resposta = ficha_routes.risk_plan_approval_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={"decisao": "Aprovado", "comentario": "", "versao": ""},
            rota={"codigo": codigo},
        )
    )

    assert resposta.status_code == 403


# ── Ação, revisão, encerramento e reabertura ─────────────────────────────────────────────────


def test_nova_acao_cria_e_volta_para_a_ficha(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_action_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={
                "assunto": "Contratar a consultoria ambiental",
                "descricao": "",
                "solicitanteId": str(cenario.mario.person_id),
                "responsavelId": str(cenario.mario.person_id),
                "prevista": (REFERENCIA + timedelta(days=5)).isoformat(),
                "contribuicaoProbabilidade": "1",
                "contribuicaoImpacto": "",
            },
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Contratar a consultoria ambiental" in corpo
    assert "Central de Ações" in unquote(resposta.headers.get("X-TN-Toast", ""))


def test_salvar_e_nova_reabre_o_modal(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_action_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={
                "assunto": "Contratar a consultoria ambiental",
                "descricao": "",
                "solicitanteId": str(cenario.mario.person_id),
                "responsavelId": str(cenario.mario.person_id),
                "prevista": (REFERENCIA + timedelta(days=5)).isoformat(),
                "contribuicaoProbabilidade": "",
                "contribuicaoImpacto": "",
                "acao": "nova",
            },
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "data-ficha-abrir-url" in corpo


def test_revisao_registrada_volta_para_a_ficha(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_review_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={
                "data": REFERENCIA.isoformat(),
                "situacaoApurada": "Sem mudança",
                "p": "3",
                "i": "4",
                "comentario": "Revisão de rotina, sem mudanças no cenário.",
                "gatilho": "nao",
                "proximaRevisao": (REFERENCIA + timedelta(days=20)).isoformat(),
                "notificar": "",
                "versao": "",
            },
            rota={"codigo": codigo},
        )
    )

    assert resposta.status_code == 200
    assert "Revisão registrada" in unquote(resposta.headers.get("X-TN-Toast", ""))


def test_encerrar_sem_licao_devolve_422(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_closing_save(
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo=_encerrar_form(licao="Curta"),
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert "Lição aprendida" in corpo


def test_membro_nao_encerra_nem_reabre(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    encerrar = ficha_routes.risk_closing_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_encerrar_form(),
            rota={"codigo": codigo},
        )
    )
    reabrir = ficha_routes.risk_reopen_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={"justificativa": "O risco voltou a ser monitorado.", "versao": ""},
            rota={"codigo": codigo},
        )
    )

    assert encerrar.status_code == 403
    assert reabrir.status_code == 403


def test_encerramento_materializado_traz_licao_e_sm(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resposta = ficha_routes.risk_closing_save(
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo=_encerrar_form(
                motivo="Materializado",
                impactoRealPrazoDias="21",
                impactoRealCustoCentavos="400.000,00",
                abrirSm="1",
                acaoResponsavelId=str(cenario.mario.person_id),
            ),
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    aviso = unquote(resposta.headers.get("X-TN-Toast", ""))
    assert resposta.status_code == 200
    assert "Materializado" in corpo
    assert "Lição" in aviso and "SM-" in aviso


def test_reabertura_pela_rota_devolve_a_ficha(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)
    ficha_routes.risk_closing_save(
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo=_encerrar_form(),
            rota={"codigo": codigo},
        )
    )

    resposta = ficha_routes.risk_reopen_save(
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo={"justificativa": "O risco voltou a ser monitorado.", "versao": ""},
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Risco reaberto" in unquote(resposta.headers.get("X-TN-Toast", ""))
    assert "Em análise" in corpo or "Em tratamento" in corpo


def test_encerramento_de_oportunidade_materializada_nao_gera_sm(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario, nature="Oportunidade")
    _avaliar(
        sessao,
        cenario,
        codigo,
        probability=2,
        impact=2,
        dimensions={"prazo": 2},
        cost_impact_cents=10_000_000,
    )

    resposta = ficha_routes.risk_closing_save(
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo=_encerrar_form(
                motivo="Materializado",
                impactoRealPrazoDias="9",
                impactoRealCustoCentavos="30.000,00",
                abrirSm="1",
            ),
            rota={"codigo": codigo},
        )
    )

    aviso = unquote(resposta.headers.get("X-TN-Toast", ""))
    assert resposta.status_code == 200
    assert "SM-" not in aviso


def test_o_plano_evitar_pela_rota_lista_as_sms_do_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(
        sessao,
        cenario,
        codigo,
        probability=2,
        impact=2,
        dimensions={"prazo": 2},
        cost_impact_cents=10_000_000,
    )
    governanca.create_change(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=cenario.projeto.id, source="padrao"),
        form={
            "titulo": "Mudança de solução da fundação",
            "tipo": "Escopo",
            "origem": "Interna",
            "prioridade": "Normal",
            "descricao": "Mudança de solução para eliminar a exposição do risco.",
            "data_solicitacao": REFERENCIA.isoformat(),
        },
        reference_date=REFERENCIA,
    )

    resposta = ficha_routes.risk_plan_form(_requisicao(cenario.mario, rota={"codigo": codigo}))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Registrar nova SM" in corpo
