"""As rotas das Inspeções e ITP (ISSUE-069, D14): a tela, a ficha, os formulários e as recusas.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``).
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import unquote, urlencode

import azure.functions as func
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.qualidade import inspecoes_routes as routes
from src.modulos.qualidade import service
from src.modulos.qualidade.models import Rnc
from src.modulos.qualidade.validation import InspectionInput, ItpInput, ItpPointInput
from tests.apoio_qualidade import REFERENCIA, Cenario, itp_aprovado, usuario_de
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
        "X-Alpine-Target": "inspecoes-conteudo",
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/qualidade/inspecoes",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def _corpo_itp(cenario: Cenario, **campos: str) -> dict[str, str]:
    corpo = {
        "projeto": str(cenario.projeto.id),
        "titulo": "Montagem de equipamentos rotativos",
        "disciplina": "Mecânica",
        "empresaId": str(cenario.empresa.id),
        "ponto1_atividade": "Nivelamento da base do moinho",
        "ponto1_tipo": "H",
        "ponto1_criterio": "Desvio máximo de 0,05 mm/m",
        "ponto1_referencia": "Manual do fabricante",
        "ponto1_responsavel": "Contratada",
        "consulta": "",
    }
    corpo.update(campos)
    return corpo


def _corpo_inspecao(linha, cenario: Cenario, **campos: str) -> dict[str, str]:
    corpo = {
        "projeto": str(cenario.projeto.id),
        "itpId": str(linha.id),
        "pontoId": str(linha.points[0].id),
        "data": REFERENCIA.isoformat(),
        "inspetorId": str(cenario.mario.person_id),
        "resultado": "Aprovado",
        "consulta": "",
    }
    corpo.update(campos)
    return corpo


# ── A tela e as exportações ─────────────────────────────────────────────────────────────────


def test_a_tela_mostra_kpis_as_tabelas_e_a_inspecao(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)
    registrada = service.record_inspection(
        sessao,
        user=cenario.mario,
        data=InspectionInput(
            project_id=cenario.projeto.id,
            itp_id=linha.id,
            point_id=linha.points[0].id,
            inspection_date=REFERENCIA,
            inspector_id=cenario.mario.person_id,
            result="Aprovado",
        ),
        reference_date=REFERENCIA,
    )

    resposta = routes.inspection_list_screen(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Inspeções registradas" in corpo
    assert "Planos de inspeção e testes (ITP)" in corpo
    assert "Registros de inspeção" in corpo
    assert linha.code in corpo
    assert registrada.code in corpo


def test_a_tela_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    itp_aprovado(sessao, cenario)

    corpo = routes.inspection_list_screen(_requisicao(cenario.mario)).get_body().decode()

    assert ">Projeto</th>" in corpo
    assert "TN-RNC-001" in corpo


def test_o_excel_e_o_imprimivel_saem_no_mesmo_filtro(sessao: Session, cenario: Cenario) -> None:
    itp_aprovado(sessao, cenario)

    excel = routes.inspection_list_excel(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )
    imprimivel = routes.inspection_list_printable(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    assert imprimivel.status_code == 200
    assert "Registros de inspeção" in imprimivel.get_body().decode()


def test_o_excel_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    itp_aprovado(sessao, cenario)

    excel = routes.inspection_list_excel(_requisicao(cenario.mario))
    imprimivel = routes.inspection_list_printable(_requisicao(cenario.mario))

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    corpo = imprimivel.get_body().decode()
    assert imprimivel.status_code == 200
    assert "Projeto" in corpo
    assert "TN-RNC-001" in corpo


def test_o_fornecedor_nao_alcanca_o_modulo(sessao: Session, cenario: Cenario) -> None:
    fornecedor = usuario_de(
        sessao,
        criar_colaborador(
            sessao,
            email="fornecedor@inspecoes.example.invalid",
            nome="Fornecedor da obra",
            vinculo="Fornecedor",
            empresa=cenario.empresa,
        ),
    )

    resposta = routes.inspection_list_screen(_requisicao(fornecedor))

    assert resposta.status_code == 403


# ── ITP: formulário, revisão e aprovação ────────────────────────────────────────────────────


def test_no_portfolio_o_formulario_do_itp_pede_o_projeto(cenario: Cenario) -> None:
    resposta = routes.itp_new_form(_requisicao(cenario.mario))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'name="projeto"' in corpo


def test_o_formulario_de_novo_itp_salva_e_devolve_a_lista(cenario: Cenario) -> None:
    resposta = routes.itp_new_save(
        _requisicao(cenario.mario, metodo="POST", corpo=_corpo_itp(cenario))
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "ITP-TN-MEC-01" in corpo
    assert "ITP-TN-MEC-01" in unquote(resposta.headers.get("X-TN-Toast", ""))


def test_itp_sem_pontos_devolve_422_com_a_mensagem(cenario: Cenario) -> None:
    corpo = _corpo_itp(cenario)
    for chave in [chave for chave in corpo if chave.startswith("ponto1_")]:
        del corpo[chave]

    resposta = routes.itp_new_save(_requisicao(cenario.mario, metodo="POST", corpo=corpo))

    assert resposta.status_code == 422
    assert "ao menos um ponto de inspeção" in resposta.get_body().decode()


def test_a_ficha_do_itp_traz_os_pontos(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)

    resposta = routes.itp_sheet_fragment(_requisicao(cenario.mario, rota={"codigo": linha.code}))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Pontos da revisão vigente" in corpo
    assert "Nivelamento da base do moinho" in corpo
    assert "Aprovado" in corpo


def test_membro_nao_aprova_o_itp(sessao: Session, cenario: Cenario) -> None:
    criado = service.create_itp(
        sessao,
        user=cenario.mario,
        data=ItpInput(
            project_id=cenario.projeto.id,
            title="Montagem de equipamentos rotativos",
            discipline="Mecânica",
            company_id=cenario.empresa.id,
            points=(
                ItpPointInput(
                    activity="Nivelamento da base do moinho",
                    point_type="H",
                    criterion="Desvio máximo de 0,05 mm/m",
                ),
            ),
        ),
        reference_date=REFERENCIA,
    )

    resposta = routes.itp_approval_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo={
                "referencia": "Carta MQS-QUA-0012",
                "data": REFERENCIA.isoformat(),
                "consulta": "",
            },
            rota={"codigo": criado.code},
        )
    )

    assert resposta.status_code == 403


def test_a_aprovacao_do_gestor_atualiza_a_lista(sessao: Session, cenario: Cenario) -> None:
    criado = service.create_itp(
        sessao,
        user=cenario.mario,
        data=ItpInput(
            project_id=cenario.projeto.id,
            title="Montagem de equipamentos rotativos",
            discipline="Mecânica",
            company_id=cenario.empresa.id,
            points=(
                ItpPointInput(
                    activity="Nivelamento da base do moinho",
                    point_type="H",
                    criterion="Desvio máximo de 0,05 mm/m",
                ),
            ),
        ),
        reference_date=REFERENCIA,
    )

    resposta = routes.itp_approval_save(
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo={
                "referencia": "Carta MQS-QUA-0012",
                "data": REFERENCIA.isoformat(),
                "consulta": "",
            },
            rota={"codigo": criado.code},
        )
    )

    assert resposta.status_code == 200
    assert "aprovado pelo cliente" in unquote(resposta.headers.get("X-TN-Toast", ""))


def test_a_revisao_salva_e_volta_a_pedir_a_aprovacao(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)

    formulario = routes.itp_revision_form(_requisicao(cenario.mario, rota={"codigo": linha.code}))
    assert formulario.status_code == 200
    assert "Montagem de equipamentos rotativos" in formulario.get_body().decode()

    resposta = routes.itp_revision_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_corpo_itp(cenario, versao=str(linha.version)),
            rota={"codigo": linha.code},
        )
    )

    assert resposta.status_code == 200
    assert "Revisão 1" in unquote(resposta.headers.get("X-TN-Toast", ""))
    revisada = service.itp_sheet(
        sessao, user=cenario.mario, code=linha.code, reference_date=REFERENCIA
    )
    assert revisada is not None and revisada.approved_by_client is False


# ── Inspeção ────────────────────────────────────────────────────────────────────────────────


def test_no_portfolio_o_formulario_da_inspecao_pede_o_projeto(cenario: Cenario) -> None:
    resposta = routes.inspection_form(_requisicao(cenario.mario))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'name="projeto"' in corpo


def test_a_inspecao_salva_e_abre_a_rnc(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)

    resposta = routes.inspection_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_corpo_inspecao(
                linha,
                cenario,
                resultado="Reprovado",
                observacao="Desvio acima do critério de aceitação.",
                severidade="Maior",
                contencao="Montagem suspensa até o reaperto.",
            ),
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "aberta" in unquote(resposta.headers.get("X-TN-Toast", ""))
    rnc = sessao.scalars(select(Rnc)).one()
    assert rnc.origin == "Inspeção"
    assert rnc.code in corpo


def test_a_inspecao_em_itp_nao_aprovado_devolve_422(sessao: Session, cenario: Cenario) -> None:
    criado = service.create_itp(
        sessao,
        user=cenario.mario,
        data=ItpInput(
            project_id=cenario.projeto.id,
            title="Montagem de equipamentos rotativos",
            discipline="Mecânica",
            company_id=cenario.empresa.id,
            points=(
                ItpPointInput(
                    activity="Nivelamento da base do moinho",
                    point_type="H",
                    criterion="Desvio máximo de 0,05 mm/m",
                ),
            ),
        ),
        reference_date=REFERENCIA,
    )
    linha = service.itp_sheet(
        sessao, user=cenario.mario, code=criado.code, reference_date=REFERENCIA
    )
    assert linha is not None

    resposta = routes.inspection_save(
        _requisicao(cenario.mario, metodo="POST", corpo=_corpo_inspecao(linha, cenario))
    )

    assert resposta.status_code == 422
    assert "ainda não tem aprovação do cliente" in resposta.get_body().decode()


def test_visualizador_nao_salva_inspecao(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)

    resposta = routes.inspection_save(
        _requisicao(cenario.vera, metodo="POST", corpo=_corpo_inspecao(linha, cenario))
    )

    assert resposta.status_code == 403
