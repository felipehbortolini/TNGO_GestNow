"""As rotas da Qualidade (ISSUE-068, D14): a tela, a ficha, os formulários e as recusas.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import unquote, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.validation import CompletionRequest
from src.modulos.qualidade import routes, service
from src.modulos.qualidade.validation import ActionInput, ResponsibleInput
from tests.apoio_qualidade import (
    REFERENCIA,
    Cenario,
    nova_abertura,
    nova_analise,
    usuario_de,
)
from tests.identidades import criar_colaborador


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
        "X-Alpine-Target": "rnc-conteudo",
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/qualidade/rnc",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def _abrir(sessao: Session, cenario: Cenario, **campos: object) -> str:
    resultado = service.open_rnc(
        sessao, user=cenario.mario, data=nova_abertura(cenario, **campos), reference_date=REFERENCIA
    )
    return resultado.code


def _corpo_nova(cenario: Cenario, **campos: str) -> dict[str, str]:
    corpo = {
        "projeto": str(cenario.projeto.id),
        "data": REFERENCIA.isoformat(),
        "origem": "Inspeção",
        "origemRef": "INS-2026-0001",
        "disciplina": "Mecânica",
        "empresaId": str(cenario.empresa.id),
        "severidade": "Maior",
        "descricao": "Seis juntas soldadas da linha 310-P-014 reprovadas no ultrassom.",
        "contencao": "Linha bloqueada para o teste hidrostático; soldador afastado da frente.",
        "consulta": "",
    }
    corpo.update(campos)
    return corpo


# ── A tela e as exportações ──────────────────────────────────────────────────


def test_a_tela_mostra_kpis_e_a_lista(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)

    resposta = routes.rnc_list_screen(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert codigo in corpo
    assert "RNC em aberto" in corpo
    assert "rnc__tabela" in corpo


def test_a_tela_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    _abrir(sessao, cenario)

    corpo = routes.rnc_list_screen(_requisicao(cenario.mario)).get_body().decode()

    assert ">Projeto</th>" in corpo
    assert "TN-RNC-001" in corpo


def test_o_excel_e_o_imprimivel_saem_no_mesmo_filtro(sessao: Session, cenario: Cenario) -> None:
    _abrir(sessao, cenario)

    excel = routes.rnc_list_excel(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )
    imprimivel = routes.rnc_list_printable(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    assert imprimivel.status_code == 200
    assert "Relatórios de não conformidade" in imprimivel.get_body().decode()


def test_o_fornecedor_nao_alcanca_o_modulo(sessao: Session, cenario: Cenario) -> None:
    fornecedor = usuario_de(
        sessao,
        criar_colaborador(
            sessao,
            email="fornecedor@qualidade.example.invalid",
            nome="Fornecedor da obra",
            vinculo="Fornecedor",
            empresa=cenario.empresa,
        ),
    )

    resposta = routes.rnc_list_screen(_requisicao(fornecedor))

    assert resposta.status_code == 403


# ── Abertura ─────────────────────────────────────────────────────────────────


def test_no_portfolio_o_formulario_pede_o_projeto(cenario: Cenario) -> None:
    resposta = routes.rnc_new_form(_requisicao(cenario.mario))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'name="projeto"' in corpo


def test_o_formulario_de_nova_rnc_salva_e_devolve_a_lista(cenario: Cenario) -> None:
    resposta = routes.rnc_new_save(
        _requisicao(cenario.mario, metodo="POST", corpo=_corpo_nova(cenario))
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert "RNC-TN-2026-0001" in corpo
    assert "data-rnc-abrir-ficha" in corpo


def test_abertura_sem_contencao_devolve_422_com_a_mensagem(cenario: Cenario) -> None:
    resposta = routes.rnc_new_save(
        _requisicao(cenario.mario, metodo="POST", corpo=_corpo_nova(cenario, contencao="curta"))
    )

    assert resposta.status_code == 422
    assert "contenção imediata" in resposta.get_body().decode()


def test_visualizador_nao_salva_rnc(cenario: Cenario) -> None:
    resposta = routes.rnc_new_save(
        _requisicao(cenario.vera, metodo="POST", corpo=_corpo_nova(cenario))
    )

    assert resposta.status_code == 403


# ── Ficha e fluxo ────────────────────────────────────────────────────────────


def test_a_ficha_traz_a_contencao_e_as_acoes(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)
    service.assign_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=ResponsibleInput(responsible_id=cenario.mario.person_id),
        reference_date=REFERENCIA,
    )
    service.record_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=_analise_com_acao(cenario),
        reference_date=REFERENCIA,
    )

    resposta = routes.rnc_sheet_fragment(_requisicao(cenario.mario, rota={"codigo": codigo}))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Contenção" in corpo
    assert "Ações na Central" in corpo
    assert "Evidências" in corpo


def test_o_responsavel_e_a_analise_atualizam_a_lista(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)

    resposta = routes.rnc_assign_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={"responsavelId": str(cenario.mario.person_id), "versao": "1", "consulta": ""},
            rota={"codigo": codigo},
        )
    )
    assert resposta.status_code == 200
    assert "Análise atribuída" in unquote(resposta.headers.get("X-TN-Toast", ""))

    resposta = routes.rnc_analysis_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={
                "metodo": "5 porquês",
                "causaRaiz": "Soldador sem qualificação para o processo e a espessura.",
                "disposicao": "Retrabalho",
                "custoCentavos": "34.000,00",
                "acao1_assunto": "Refazer as soldadas reprovadas da linha",
                "acao1_responsavel": str(cenario.mario.person_id),
                "acao1_prevista": (REFERENCIA.isoformat()),
                "versao": "2",
                "consulta": "",
            },
            rota={"codigo": codigo},
        )
    )

    assert resposta.status_code == 200
    criadas = actions.actions_of_origin(
        sessao, user=cenario.mario, origin_kind="RNC", reference=codigo, reference_date=REFERENCIA
    )
    assert len(criadas) == 1


def test_membro_nao_verifica_eficacia(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)

    resposta = routes.rnc_effectiveness_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={
                "eficaz": "sim",
                "texto": "Evidência com quinze caracteres.",
                "data": REFERENCIA.isoformat(),
                "versao": "1",
                "consulta": "",
            },
            rota={"codigo": codigo},
        )
    )

    assert resposta.status_code == 403


def test_a_eficacia_encerra_e_registra_a_licao(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)
    service.assign_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=ResponsibleInput(responsible_id=cenario.mario.person_id),
        reference_date=REFERENCIA,
    )
    service.record_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=_analise_com_acao(cenario),
        reference_date=REFERENCIA,
    )
    for acao in actions.actions_of_origin(
        sessao, user=cenario.mario, origin_kind="RNC", reference=codigo, reference_date=REFERENCIA
    ):
        actions.complete_action(
            sessao,
            user=cenario.mario,
            request=CompletionRequest(
                action_id=acao.id, completed_on=REFERENCIA, version=acao.version
            ),
            reference_date=REFERENCIA,
        )
    service.send_to_verification(
        sessao, user=cenario.mario, code=codigo, version=None, reference_date=REFERENCIA
    )
    linha = service.find_rnc(sessao, user=cenario.ada, code=codigo, reference_date=REFERENCIA)
    assert linha is not None

    resposta = routes.rnc_effectiveness_save(
        _requisicao(
            cenario.ada,
            metodo="POST",
            corpo={
                "eficaz": "sim",
                "texto": "Dez soldas seguintes aprovadas no ultrassom, soldador requalificado.",
                "data": REFERENCIA.isoformat(),
                "registrarLicao": "1",
                "licaoTitulo": "Requalificar o soldador antes do retrabalho",
                "licaoRecomendacao": "Exigir a qualificação vigente do soldador na liberação.",
                "versao": str(linha.version),
                "consulta": "",
            },
            rota={"codigo": codigo},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Lição" in unquote(resposta.headers.get("X-TN-Toast", ""))
    assert "Encerrada" in corpo


def _analise_com_acao(cenario: Cenario):
    """Uma análise válida com a ação corretiva atribuída a quem responde por ela."""
    return nova_analise(
        actions=(
            ActionInput(
                subject="Refazer as soldas reprovadas da linha 310-P-014",
                responsible_id=cenario.mario.person_id,
                planned_date=REFERENCIA + timedelta(days=10),
            ),
        )
    )
