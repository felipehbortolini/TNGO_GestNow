"""As rotas das Auditorias (ISSUE-070, D14): a tela, a ficha, os formulários e as recusas.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import unquote, urlencode

import azure.functions as func
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.qualidade import auditorias_routes as routes
from src.modulos.qualidade import service
from src.modulos.qualidade.models import Rnc
from src.modulos.qualidade.validation import AuditFilters
from tests.apoio_qualidade import (
    REFERENCIA,
    Cenario,
    nova_auditoria,
    nova_constatacao,
    resultado_auditoria,
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
        "X-Alpine-Target": "auditorias-conteudo",
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/qualidade/auditorias",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def _corpo_auditoria(cenario: Cenario, **campos: str) -> dict[str, str]:
    corpo = {
        "projeto": str(cenario.projeto.id),
        "tipo": "Contratada",
        "auditadoId": str(cenario.empresa.id),
        "auditorId": str(cenario.mario.person_id),
        "escopo": "Controle tecnológico do concreto",
        "criterio": "ET-CIV-001 e NBR 12655",
        "data": (REFERENCIA + timedelta(days=10)).isoformat(),
        "consulta": "",
    }
    corpo.update(campos)
    return corpo


def _corpo_resultado(**campos: str) -> dict[str, str]:
    corpo = {
        "data": REFERENCIA.isoformat(),
        "itensVerificados": "40",
        "itensConformes": "36",
        "constatacao1_tipo": "Não conformidade",
        "constatacao1_descricao": "Ensaios de abatimento sem registro em 3 caminhões.",
        "constatacao1_requisito": "NBR 12655, 6.2",
        "constatacao1_disciplina": "Mecânica",
        "constatacao1_severidade": "Maior",
        "resumo": "Conformidade abaixo da meta.",
        "consulta": "",
    }
    corpo.update(campos)
    return corpo


def _planejar(sessao: Session, cenario: Cenario):
    return service.create_audit(
        sessao,
        user=cenario.mario,
        data=nova_auditoria(cenario),
        reference_date=REFERENCIA,
    )


# ── A tela e as exportações ─────────────────────────────────────────────────────────────────


def test_a_tela_mostra_kpis_o_programa_e_a_auditoria(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    resposta = routes.audit_list_screen(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Aderência ao programa" in corpo
    assert "Auditorias atrasadas" in corpo
    assert "Programa de auditorias" in corpo
    assert criada.code in corpo
    assert "Controle tecnológico do concreto" in corpo


def test_a_tela_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    _planejar(sessao, cenario)

    corpo = routes.audit_list_screen(_requisicao(cenario.mario)).get_body().decode()

    assert ">Projeto</th>" in corpo
    assert "TN-RNC-001" in corpo


def test_o_excel_e_o_imprimivel_saem_no_mesmo_filtro(sessao: Session, cenario: Cenario) -> None:
    _planejar(sessao, cenario)

    excel = routes.audit_list_excel(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )
    imprimivel = routes.audit_list_printable(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    assert imprimivel.status_code == 200
    assert "Programa de auditorias" in imprimivel.get_body().decode()


def test_o_excel_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    _planejar(sessao, cenario)

    excel = routes.audit_list_excel(_requisicao(cenario.mario))
    imprimivel = routes.audit_list_printable(_requisicao(cenario.mario))

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
            email="fornecedor@auditorias.example.invalid",
            nome="Fornecedor da obra",
            vinculo="Fornecedor",
            empresa=cenario.empresa,
        ),
    )

    resposta = routes.audit_list_screen(_requisicao(fornecedor))

    assert resposta.status_code == 403


def test_a_ficha_traz_as_constatacoes_e_a_rnc(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)
    resultado = service.record_result(
        sessao,
        user=cenario.mario,
        code=criada.code,
        data=resultado_auditoria(findings=(nova_constatacao(),)),
        reference_date=REFERENCIA,
    )

    resposta = routes.audit_sheet_fragment(_requisicao(cenario.mario, rota={"codigo": criada.code}))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Constatações" in corpo
    assert "Ensaios de abatimento sem registro em 3 caminhões." in corpo
    assert resultado.rnc_codes[0] in corpo
    assert "Aberta" in corpo


# ── Planejar e reprogramar ──────────────────────────────────────────────────────────────────


def test_no_portfolio_o_formulario_pede_o_projeto(cenario: Cenario) -> None:
    resposta = routes.audit_new_form(_requisicao(cenario.mario))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'name="projeto"' in corpo


def test_o_formulario_de_nova_auditoria_salva_e_devolve_a_lista(cenario: Cenario) -> None:
    resposta = routes.audit_new_save(
        _requisicao(cenario.mario, metodo="POST", corpo=_corpo_auditoria(cenario))
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "AUD-TN-2026-01" in corpo
    assert "AUD-TN-2026-01" in unquote(resposta.headers.get("X-TN-Toast", ""))


def test_auditoria_com_data_no_passado_devolve_422(cenario: Cenario) -> None:
    corpo = _corpo_auditoria(cenario, data=(REFERENCIA - timedelta(days=1)).isoformat())

    resposta = routes.audit_new_save(_requisicao(cenario.mario, metodo="POST", corpo=corpo))

    assert resposta.status_code == 422
    assert "não pode ser anterior à referência" in resposta.get_body().decode()


def test_o_formulario_de_reprogramacao_abre_preenchido(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    resposta = routes.audit_reschedule_form(
        _requisicao(cenario.mario, rota={"codigo": criada.code})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert criada.code in corpo
    assert "Controle tecnológico do concreto" in corpo
    assert 'name="justificativa"' in corpo


def test_a_reprogramacao_sem_justificativa_devolve_422(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)
    corpo = _corpo_auditoria(
        cenario,
        data=(REFERENCIA + timedelta(days=20)).isoformat(),
        versao="1",
        justificativa="Curta.",
    )

    resposta = routes.audit_reschedule_save(
        _requisicao(cenario.mario, metodo="POST", corpo=corpo, rota={"codigo": criada.code})
    )

    assert resposta.status_code == 422
    assert "Reprogramação exige justificativa" in resposta.get_body().decode()


def test_a_reprogramacao_com_justificativa_atualiza_a_lista(
    sessao: Session, cenario: Cenario
) -> None:
    criada = _planejar(sessao, cenario)
    corpo = _corpo_auditoria(
        cenario,
        data=(REFERENCIA + timedelta(days=20)).isoformat(),
        versao="1",
        justificativa="Negociação com a contratada para a mobilização da equipe.",
    )

    resposta = routes.audit_reschedule_save(
        _requisicao(cenario.mario, metodo="POST", corpo=corpo, rota={"codigo": criada.code})
    )

    assert resposta.status_code == 200
    assert "reprogramada" in unquote(resposta.headers.get("X-TN-Toast", "")).lower()
    linha = service.find_audit(
        sessao, user=cenario.mario, code=criada.code, reference_date=REFERENCIA
    )
    assert linha is not None and len(linha.reschedules) == 1


# ── Resultado ───────────────────────────────────────────────────────────────────────────────


def test_o_formulario_do_resultado_abre_com_as_constatacoes(
    sessao: Session, cenario: Cenario
) -> None:
    criada = _planejar(sessao, cenario)

    resposta = routes.audit_result_form(_requisicao(cenario.mario, rota={"codigo": criada.code}))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Conclusão da auditoria" in corpo
    assert "Constatação 1" in corpo
    assert "Adicionar constatação" in corpo
    assert criada.code in corpo


def test_o_resultado_com_nc_abre_a_rnc_e_avisa(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    resposta = routes.audit_result_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_corpo_resultado(versao="1"),
            rota={"codigo": criada.code},
        )
    )

    corpo = resposta.get_body().decode()
    aviso = unquote(resposta.headers.get("X-TN-Toast", ""))
    assert resposta.status_code == 200
    assert "RNC aberta" in aviso
    rnc = sessao.scalars(select(Rnc)).one()
    assert rnc.origin == "Auditoria"
    assert rnc.code in aviso
    assert "1 RNC em aberto" in corpo


def test_mais_nc_que_itens_nao_conformes_devolve_422(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    resposta = routes.audit_result_save(
        _requisicao(
            cenario.mario,
            metodo="POST",
            corpo=_corpo_resultado(itensConformes="40", versao="1"),
            rota={"codigo": criada.code},
        )
    )

    assert resposta.status_code == 422
    assert "Há mais não conformidades (1) que itens não conformes (0)." in (
        resposta.get_body().decode()
    )
    assert sessao.scalars(select(Rnc)).all() == []


def test_visualizador_nao_salva_o_resultado(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    resposta = routes.audit_result_save(
        _requisicao(
            cenario.vera,
            metodo="POST",
            corpo=_corpo_resultado(versao="1"),
            rota={"codigo": criada.code},
        )
    )

    assert resposta.status_code == 403


def test_a_lista_da_tela_filtra_por_situacao(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)
    service.record_result(
        sessao,
        user=cenario.mario,
        code=criada.code,
        data=resultado_auditoria(items_verified=10, items_conforming=9),
        reference_date=REFERENCIA,
    )

    resposta = routes.audit_list_screen(
        _requisicao(
            cenario.mario,
            params={"projeto": str(cenario.projeto.id), "situacao": "Realizada"},
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert criada.code in corpo
    assert "90,0%" in corpo

    planejadas = service.list_audits(
        sessao,
        user=cenario.mario,
        scope=Scope(project_id=cenario.projeto.id, source="url"),
        filters=AuditFilters(situation="Planejada"),
        reference_date=REFERENCIA,
    )
    assert planejadas.lines == ()
