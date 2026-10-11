"""Rotas da Análise do período (ISSUE-081/ISSUE-082): 403 por perfil, 422 por campo, cópia, exclusão e Portfólio."""

from __future__ import annotations

import html
from collections.abc import Mapping
from urllib.parse import unquote

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.core import calendario
from src.core.auth import DEMO_COOKIE
from src.modulos.planejamento.validation import WEEKLY
from src.modulos.relatorio import routes, service, validation
from tests.identidades import requisicao
from tests.relatorio.conftest import Cenario, Demonstracao

TEXTO = "Panorama, desempenho dos períodos anteriores, causas e tendência. " * 4

TEXTO_ANTERIOR = "Texto do período anterior com panorama e tendência. " * 6


def _periodo(deslocamento: int = 0) -> str:
    atual = calendario.period_of(WEEKLY, calendario.today())
    return calendario.add_periods(WEEKLY, atual, deslocamento) or ""


def _corpo_do_formulario(**campos: str) -> dict[str, str]:
    base = {
        "modulo": "planejamento",
        "tipo": WEEKLY,
        "periodo": _periodo(),
        "analise": TEXTO,
        "id": "",
        "versao": "",
    }
    base.update(campos)
    return base


def _chamar_rota(
    funcao: object,
    *,
    colaborador_id: int,
    projeto_id: int | None,
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, str] | None = None,
) -> func.HttpResponse:
    """Chama a rota como o colaborador: POST quando há corpo, GET quando não; o alvo é o modal."""
    parametros = dict(params or {})
    if projeto_id is not None:
        parametros["projeto"] = str(projeto_id)
    requisicao_http = requisicao(
        "/api/relatorio/analise",
        metodo="POST" if corpo is not None else "GET",
        cookies={DEMO_COOKIE: str(colaborador_id)},
        alvo=routes.ANALYSIS_MODAL_TARGET,
        params=parametros,
        corpo=corpo,
    )
    return funcao(requisicao_http)  # type: ignore[operator]


def _chamar(
    cenario: Cenario,
    funcao: object,
    perfil: str,
    *,
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, str] | None = None,
) -> func.HttpResponse:
    """Chama a rota como o perfil do cenário, no projeto do cenário."""
    return _chamar_rota(
        funcao,
        colaborador_id=cenario.colaboradores[perfil],
        projeto_id=cenario.project.id,
        params=params,
        corpo=corpo,
    )


def _texto(resposta: func.HttpResponse) -> str:
    return html.unescape(resposta.get_body().decode())


def _gravar(cenario: Cenario, perfil: str = "Membro", **campos: str) -> func.HttpResponse:
    return _chamar(cenario, routes.analysis_save, perfil, corpo=_corpo_do_formulario(**campos))


def _registro(cenario: Cenario) -> service.AnalysisView:
    visao = service.analysis_view(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        module="planejamento",
        kind=WEEKLY,
        period=_periodo(),
        reference_date=calendario.today(),
    )
    assert visao.record is not None
    return visao


# ── Gravar: 200, 403 e 422 ─────────────────────────────────────────────────


def test_membro_grava_e_a_resposta_fecha_o_modal(cenario: Cenario) -> None:
    resposta = _gravar(cenario)

    assert resposta.status_code == 200
    assert "data-analise-salvo" in _texto(resposta)
    assert _registro(cenario).record is not None


@pytest.mark.parametrize("perfil", ["Visualizador"])
def test_quem_nao_e_membro_recebe_403_ao_gravar(cenario: Cenario, perfil: str) -> None:
    resposta = _gravar(cenario, perfil)

    assert resposta.status_code == 403
    assert (
        service.analysis_record(
            cenario.session,
            project_id=cenario.project.id,
            module="planejamento",
            kind=WEEKLY,
            period=_periodo(),
        )
        is None
    )


def test_formulario_e_passo_1_exigem_membro(cenario: Cenario) -> None:
    params = {"modulo": "planejamento", "tipo": WEEKLY, "periodo": _periodo()}

    assert _chamar(cenario, routes.analysis_form, "Visualizador", params=params).status_code == 403
    assert _chamar(cenario, routes.analysis_form, "Membro", params=params).status_code == 200
    assert (
        _chamar(
            cenario,
            routes.analysis_period_picker,
            "Visualizador",
            params={"modulo": "planejamento"},
        ).status_code
        == 403
    )


def test_texto_curto_responde_422_com_a_mensagem_no_campo(cenario: Cenario) -> None:
    resposta = _gravar(cenario, analise="curto")

    texto = _texto(resposta)
    assert resposta.status_code == 422
    assert 'id="analise-modal"' in texto
    assert "ao menos 150 caracteres" in texto
    assert "curto" in texto


def test_periodo_futuro_responde_422(cenario: Cenario) -> None:
    resposta = _gravar(cenario, periodo=_periodo(1))

    assert resposta.status_code == 422
    assert "O período ainda não começou" in _texto(resposta)


def test_analise_duplicada_responde_422(cenario: Cenario) -> None:
    _gravar(cenario)

    resposta = _gravar(cenario)

    assert resposta.status_code == 422
    assert "Já existe análise semanal para este período" in _texto(resposta)


# ── Excluir: Gestor ────────────────────────────────────────────────────────


def test_gestor_exclui_e_membro_recebe_403(cenario: Cenario) -> None:
    _gravar(cenario)
    visao = _registro(cenario)
    assert visao.record is not None
    corpo = {"id": str(visao.record.id), "versao": str(visao.record.version)}

    negado = _chamar(cenario, routes.analysis_delete, "Membro", corpo=corpo)
    assert negado.status_code == 403

    feito = _chamar(cenario, routes.analysis_delete, "Gestor", corpo=corpo)
    assert feito.status_code == 200
    assert "data-analise-excluida" in _texto(feito)
    assert (
        service.analysis_record(
            cenario.session,
            project_id=cenario.project.id,
            module="planejamento",
            kind=WEEKLY,
            period=_periodo(),
        )
        is None
    )


# ── Copiar, passo 1 e o endereço ?analise ──────────────────────────────────


def test_copiar_traz_o_texto_do_periodo_anterior(cenario: Cenario) -> None:
    _gravar(cenario, periodo=_periodo(-1), analise=TEXTO_ANTERIOR)

    resposta = _chamar(
        cenario,
        routes.analysis_copy,
        "Membro",
        corpo=_corpo_do_formulario(analise="", periodo=_periodo()),
    )

    assert resposta.status_code == 200
    assert TEXTO_ANTERIOR.strip() in _texto(resposta)
    assert "copiado para revisão" in unquote(resposta.headers.get("X-TN-Toast", ""))


def test_copiar_sem_analise_anterior_avisa_sem_trocar_o_texto(cenario: Cenario) -> None:
    resposta = _chamar(
        cenario,
        routes.analysis_copy,
        "Membro",
        corpo=_corpo_do_formulario(analise=TEXTO, periodo=_periodo()),
    )

    assert resposta.status_code == 200
    assert TEXTO.strip() in _texto(resposta)
    assert "Não há análise registrada no período anterior." in unquote(
        resposta.headers.get("X-TN-Toast", "")
    )


def test_passo_1_lista_os_periodos_com_a_situacao(cenario: Cenario) -> None:
    antes = _texto(
        _chamar(
            cenario,
            routes.analysis_period_picker,
            "Membro",
            params={"modulo": "planejamento", "tipo": WEEKLY},
        )
    )
    assert "em andamento" in antes
    assert "pendente" in antes

    _gravar(cenario)

    depois = _texto(
        _chamar(
            cenario,
            routes.analysis_period_picker,
            "Membro",
            params={"modulo": "planejamento", "tipo": WEEKLY},
        )
    )
    assert "análise registrada" in depois


def test_o_endereco_analise_abre_o_formulario(cenario: Cenario) -> None:
    resposta = _chamar(
        cenario,
        routes.analysis_form,
        "Membro",
        params={"modulo": "planejamento", "tipo": WEEKLY, "periodo": _periodo()},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'name="analise"' in texto
    assert 'action="/api/relatorio/analise/gravar"' in texto
    assert validation.TEXT_SHORT_MESSAGE not in texto


# ── Módulos 05, 06 e 07 e o Portfólio ──────────────────────────────────────


@pytest.mark.parametrize("modulo", ["riscos", "qualidade", "hse"])
def test_passo_2_dos_modulos_05_06_07(cenario: Cenario, modulo: str) -> None:
    resposta = _chamar(
        cenario,
        routes.analysis_form,
        "Membro",
        params={"modulo": modulo, "tipo": WEEKLY, "periodo": _periodo()},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'name="analise"' in texto


def test_gravar_qualidade_sem_comentario(cenario: Cenario) -> None:
    resposta = _gravar(cenario, modulo="qualidade")

    assert resposta.status_code == 200
    assert "data-analise-salvo" in _texto(resposta)


def test_gravar_no_portfolio(cenario: Cenario) -> None:
    resposta = _chamar_rota(
        routes.analysis_save,
        colaborador_id=cenario.colaboradores["Membro"],
        projeto_id=None,
        corpo=_corpo_do_formulario(modulo="riscos"),
    )

    assert resposta.status_code == 200
    assert "data-analise-salvo" in _texto(resposta)
    assert (
        service.analysis_record(
            cenario.session,
            project_id=None,
            module="riscos",
            kind=WEEKLY,
            period=_periodo(),
        )
        is not None
    )


def test_comentario_longo_no_06_responde_422(
    sessao_das_rotas: Session, demonstracao: Demonstracao
) -> None:
    record = service.analysis_record(
        sessao_das_rotas,
        project_id=demonstracao.project_id,
        module="qualidade",
        kind=WEEKLY,
        period="2026-S38",
    )
    assert record is not None

    resposta = _chamar_rota(
        routes.analysis_save,
        colaborador_id=demonstracao.admin.id,
        projeto_id=demonstracao.project_id,
        corpo=_corpo_do_formulario(
            modulo="qualidade",
            periodo="2026-S38",
            id=str(record.id),
            versao=str(record.version),
            desvio_0="a" * 601,
            desvio_chave_0="rnc_vencidas",
        ),
    )

    assert resposta.status_code == 422
    assert validation.COMMENT_LONG_MESSAGE in _texto(resposta)
