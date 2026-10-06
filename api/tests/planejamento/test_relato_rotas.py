"""Rotas do Relato do período (ISSUE-044): 403 por perfil, 422 por campo, cópia, abrir e exportações."""

from __future__ import annotations

import html
from collections.abc import Mapping
from urllib.parse import unquote

import azure.functions as func
import pytest

from src.core import calendario
from src.core.auth import DEMO_COOKIE
from src.modulos.planejamento import routes, service
from src.modulos.planejamento.validation import MONTHLY, WEEKLY, PointInput
from tests.identidades import requisicao
from tests.planejamento.conftest import Cenario

PONTO = PointInput(
    description="Chuva forte prevista para a semana",
    nature="Ameaça",
    risk="Atraso na concretagem por chuva acima da média",
)


def _periodo(deslocamento: int = 0, kind: str = WEEKLY) -> str:
    atual = calendario.period_of(kind, calendario.today())
    return calendario.add_periods(kind, atual, deslocamento) or ""


def _corpo_do_formulario(**campos: str) -> dict[str, str]:
    base = {
        "tipo": WEEKLY,
        "periodo": _periodo(),
        "atividades_periodo": "Concretagem do bloco A",
        "atividades_proximo": "Armação do bloco B",
        "ponto_0_descricao": PONTO.description,
        "ponto_0_natureza": PONTO.nature,
        "ponto_0_risco": PONTO.risk,
    }
    base.update(campos)
    return base


def _chamar(
    cenario: Cenario,
    funcao: object,
    perfil: str,
    *,
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, str] | None = None,
) -> func.HttpResponse:
    """Chama a rota como o perfil: POST quando há corpo, GET quando não; o alvo segue a rota."""
    painel = funcao in (routes.report_panel, routes.report_delete)
    requisicao_http = requisicao(
        "/api/planejamento/relatos",
        metodo="POST" if corpo is not None else "GET",
        cookies={DEMO_COOKIE: str(cenario.colaboradores[perfil])},
        alvo=routes.PANEL_TARGET if painel else routes.MODAL_TARGET,
        params={"projeto": str(cenario.project.id), **(params or {})},
        corpo=corpo,
    )
    return funcao(requisicao_http)  # type: ignore[operator]


def _texto(resposta: func.HttpResponse) -> str:
    return html.unescape(resposta.get_body().decode())


def _gravar(cenario: Cenario, perfil: str = "Membro", **campos: str) -> func.HttpResponse:
    return _chamar(
        cenario,
        routes.report_save,
        perfil,
        corpo=_corpo_do_formulario(**campos),
    )


def _um_relato(cenario: Cenario) -> service.ReportView:
    relatos = service.list_reports(cenario.session, user=cenario.membro, scope=cenario.scope)
    assert len(relatos) == 1
    return relatos[0]


# ── Gravar: 200, 403 e 422 ─────────────────────────────────────────────────


def test_membro_grava_e_a_resposta_fecha_o_modal(cenario: Cenario) -> None:
    resposta = _gravar(cenario)

    assert resposta.status_code == 200
    assert _um_relato(cenario).activities == ("Concretagem do bloco A",)


@pytest.mark.parametrize("perfil", ["Visualizador"])
def test_quem_nao_e_membro_recebe_403_ao_gravar(cenario: Cenario, perfil: str) -> None:
    resposta = _gravar(cenario, perfil)

    assert resposta.status_code == 403
    assert service.list_reports(cenario.session, user=cenario.membro, scope=cenario.scope) == []


def test_formulario_tambem_exige_membro(cenario: Cenario) -> None:
    assert _chamar(cenario, routes.report_form, "Visualizador").status_code == 403
    assert _chamar(cenario, routes.report_form, "Membro").status_code == 200


def test_periodo_futuro_responde_422_com_a_mensagem_no_campo(cenario: Cenario) -> None:
    resposta = _gravar(cenario, periodo=_periodo(1))

    assert resposta.status_code == 422
    assert "O período ainda não começou" in _texto(resposta)


def test_periodo_duplicado_responde_422(cenario: Cenario) -> None:
    _gravar(cenario)

    resposta = _gravar(cenario)

    assert resposta.status_code == 422
    assert "Já existe relato semanal para este período" in _texto(resposta)


def test_limites_respondem_422_por_campo(cenario: Cenario) -> None:
    sem_atividade = _gravar(cenario, atividades_periodo="", atividades_proximo="")
    linha_longa = _gravar(cenario, atividades_periodo="a" * 301)
    vinte_e_uma = _gravar(cenario, atividades_proximo="\n".join("a" for _ in range(21)))
    ponto_curto = _gravar(cenario, ponto_0_descricao="curto")

    assert {r.status_code for r in (sem_atividade, linha_longa, vinte_e_uma, ponto_curto)} == {422}
    assert "Informe ao menos uma atividade" in _texto(sem_atividade)
    assert "até 300 caracteres" in _texto(linha_longa)
    assert "no máximo 20 linhas" in _texto(vinte_e_uma)
    assert "10" in _texto(ponto_curto)
    assert service.list_reports(cenario.session, user=cenario.membro, scope=cenario.scope) == []


def test_mais_de_12_pontos_responde_422(cenario: Cenario) -> None:
    pontos: dict[str, str] = {}
    for indice in range(13):
        pontos[f"ponto_{indice}_descricao"] = PONTO.description
        pontos[f"ponto_{indice}_natureza"] = PONTO.nature
        pontos[f"ponto_{indice}_risco"] = PONTO.risk

    resposta = _gravar(cenario, **pontos)

    assert resposta.status_code == 422
    assert "No máximo 12 pontos de atenção" in _texto(resposta)


# ── Excluir: Gestor ────────────────────────────────────────────────────────


def test_gestor_exclui_e_membro_recebe_403(cenario: Cenario) -> None:
    _gravar(cenario)
    relato = _um_relato(cenario)
    corpo = {"id": str(relato.id), "versao": str(relato.version)}

    negado = _chamar(
        cenario,
        routes.report_delete,
        "Membro",
        corpo=corpo,
    )
    assert negado.status_code == 403
    assert len(service.list_reports(cenario.session, user=cenario.membro, scope=cenario.scope)) == 1

    feito = _chamar(
        cenario,
        routes.report_delete,
        "Gestor",
        corpo=corpo,
    )
    assert feito.status_code == 200
    assert service.list_reports(cenario.session, user=cenario.membro, scope=cenario.scope) == []


# ── Copiar, abrir, ver e listar ────────────────────────────────────────────


def test_copiar_traz_o_proximo_periodo_e_os_pontos(cenario: Cenario) -> None:
    _gravar(cenario, periodo=_periodo(-1), atividades_proximo="Entrega da armação")

    resposta = _chamar(
        cenario,
        routes.report_copy,
        "Membro",
        corpo={"tipo": WEEKLY, "periodo": _periodo(0)},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Entrega da armação" in texto
    assert PONTO.description in texto


def test_copiar_sem_relato_anterior_avisa_sem_gravar(cenario: Cenario) -> None:
    resposta = _chamar(
        cenario,
        routes.report_copy,
        "Membro",
        corpo={"tipo": MONTHLY, "periodo": _periodo(0, MONTHLY)},
    )

    assert resposta.status_code == 200
    assert "Não há relato mensal anterior para copiar." in unquote(
        resposta.headers.get("X-TN-Toast", "")
    )


def test_abrir_leva_ao_relato_do_periodo_ou_ao_formulario(cenario: Cenario) -> None:
    params = {"tipo": WEEKLY, "periodo": _periodo()}
    formulario = _chamar(cenario, routes.report_open, "Membro", params=params)
    assert formulario.status_code == 200
    assert 'name="atividades_periodo"' in _texto(formulario)

    _gravar(cenario)
    ver = _chamar(cenario, routes.report_open, "Visualizador", params=params)
    assert ver.status_code == 200
    assert "Concretagem do bloco A" in _texto(ver)


def test_abrir_periodo_sem_relato_para_visualizador_informa(cenario: Cenario) -> None:
    resposta = _chamar(
        cenario,
        routes.report_open,
        "Visualizador",
        params={"tipo": WEEKLY, "periodo": _periodo()},
    )

    assert resposta.status_code == 422
    assert "Ainda não há relato para este período." in _texto(resposta)


def test_painel_lista_e_filtra(cenario: Cenario) -> None:
    _gravar(cenario, atividades_periodo="Montagem do guindaste")
    _gravar(cenario, tipo=MONTHLY, periodo=_periodo(0, MONTHLY), atividades_periodo="Fechamento")

    todos = _texto(_chamar(cenario, routes.report_panel, "Visualizador"))
    mensais = _texto(
        _chamar(
            cenario,
            routes.report_panel,
            "Visualizador",
            params={"tipo": MONTHLY},
        )
    )

    assert "Semanal" in todos and "Mensal" in todos
    assert "Semanal" not in mensais.split("<tbody", 1)[-1]


def test_exportacoes_do_painel(cenario: Cenario) -> None:
    _gravar(cenario)

    excel = _chamar(cenario, routes.report_excel, "Visualizador")
    imprimivel = _chamar(cenario, routes.report_printable, "Visualizador")

    assert excel.status_code == 200
    assert excel.get_body()[:2] == b"PK"
    assert imprimivel.status_code == 200
    assert "Atividades" in _texto(imprimivel)
