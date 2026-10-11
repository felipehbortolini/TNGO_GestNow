"""Rotas do relatório gerencial (ISSUE-083): o modal, as folhas, os 422 e o Portfólio.

O modal e as folhas são READ: o Visualizador os vê. Sem tipo ou período as folhas respondem
422 com a mensagem do formulário; uma seção que o relatório ainda não implementa também. O
modal redesenha com o escopo, o tipo e o período trocados.
"""

from __future__ import annotations

import html
from collections.abc import Mapping

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario
from src.core.auth import DEMO_COOKIE
from src.modulos.planejamento.validation import MONTHLY, WEEKLY
from src.modulos.relatorio import routes, validation
from tests.identidades import requisicao
from tests.relatorio.conftest import Cenario, Demonstracao


def _periodo(kind: str = WEEKLY, deslocamento: int = 0) -> str:
    return (
        calendario.add_periods(kind, calendario.period_of(kind, calendario.today()), deslocamento)
        or ""
    )


def _chamar_rota(
    funcao: object,
    *,
    colaborador_id: int,
    projeto_id: int | None,
    alvo: str,
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, object] | None = None,
) -> func.HttpResponse:
    """Chama a rota como o colaborador: POST quando há corpo, GET quando não."""
    parametros = dict(params or {})
    if projeto_id is not None:
        parametros["projeto"] = str(projeto_id)
    requisicao_http = requisicao(
        "/api/relatorio/gerencial",
        metodo="POST" if corpo is not None else "GET",
        cookies={DEMO_COOKIE: str(colaborador_id)},
        alvo=alvo,
        params=parametros,
        corpo=corpo,
    )
    return funcao(requisicao_http)  # type: ignore[operator]


def _chamar(
    cenario: Cenario,
    funcao: object,
    perfil: str = "Membro",
    *,
    alvo: str = routes.REPORT_MODAL_TARGET,
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, object] | None = None,
) -> func.HttpResponse:
    return _chamar_rota(
        funcao,
        colaborador_id=cenario.colaboradores[perfil],
        projeto_id=cenario.project.id,
        alvo=alvo,
        params=params,
        corpo=corpo,
    )


def _texto(resposta: func.HttpResponse) -> str:
    return html.unescape(resposta.get_body().decode())


# ── O modal ────────────────────────────────────────────────────────────────


def test_modal_abre_para_visualizador_com_a_situacao_e_os_links(cenario: Cenario) -> None:
    resposta = _chamar(cenario, routes.report_emission, "Visualizador")

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="relatorio-modal"' in texto
    assert "Relato do período (02 Planejamento)" in texto
    assert "Análise do período por módulo" in texto
    assert "Planejamento (2 páginas)" in texto
    assert "Financeiro (1 página)" in texto
    assert "Suprimentos (1 página)" in texto
    assert "Riscos (1 página)" in texto
    assert "Qualidade (1 página)" in texto
    assert "HSE (1 página)" in texto
    assert 'value="riscos" checked' in texto
    assert 'value="qualidade" checked' in texto
    assert 'value="hse" checked' in texto
    assert "Carteira de projetos antes das demais" in texto
    assert "Portfólio (todos os projetos)" in texto
    assert "(padrão)" in texto
    assert "Pendente" in texto
    assert ">Semanal<" in texto and ">Mensal<" in texto
    assert f"/planejamento/relato?abrir=1&tipo={WEEKLY}&periodo={_periodo(WEEKLY, -1)}" in texto
    assert f"/planejamento/relato?analise=1&tipo={WEEKLY}&periodo={_periodo(WEEKLY, -1)}" in texto


def test_modal_redesenha_com_o_tipo_o_periodo_e_o_escopo_trocados(cenario: Cenario) -> None:
    mensal = _chamar(
        cenario,
        routes.report_emission,
        corpo={
            "escopo": str(cenario.project.id),
            "tipo": MONTHLY,
            "periodo": _periodo(WEEKLY, -1),
            "secoes": ["planejamento"],
        },
    )

    texto_mensal = _texto(mensal)
    assert mensal.status_code == 200
    assert f'value="{_periodo(MONTHLY, -1)}" selected' in texto_mensal
    assert f"/planejamento/relato?analise=1&tipo={MONTHLY}&periodo={_periodo(MONTHLY, -1)}" in (
        texto_mensal
    )

    portfolio = _chamar(
        cenario,
        routes.report_emission,
        corpo={
            "escopo": "portfolio",
            "tipo": WEEKLY,
            "periodo": _periodo(WEEKLY, -1),
            "secoes": ["planejamento"],
        },
    )

    texto_portfolio = _texto(portfolio)
    assert portfolio.status_code == 200
    assert 'value="portfolio" selected' in texto_portfolio
    assert f"projeto={cenario.project.id}" in texto_portfolio
    assert "Registrar agora" in texto_portfolio
    assert "projeto=portfolio" in texto_portfolio


def test_modal_recusa_escopo_desconhecido(cenario: Cenario) -> None:
    resposta = _chamar(
        cenario,
        routes.report_emission,
        corpo={"escopo": "99999", "tipo": WEEKLY, "periodo": "", "secoes": ["planejamento"]},
    )

    assert resposta.status_code == 422
    assert "O projeto não foi encontrado." in _texto(resposta)


# ── As folhas ──────────────────────────────────────────────────────────────


def test_folhas_com_a_secao_de_planejamento(cenario: Cenario) -> None:
    resposta = _chamar(
        cenario,
        routes.report_screen,
        "Visualizador",
        alvo=routes.REPORT_TARGET,
        params={"tipo": WEEKLY, "periodo": _periodo(WEEKLY, -1), "secoes": "planejamento"},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="gerencial-conteudo"' in texto
    assert "pagina--relatorio-gerencial" in texto
    assert texto.count('class="rel-folha"') == 2
    assert "Planejamento · Curva S, KPIs e produtividade" in texto
    assert "Planejamento · Análise e relato do período" in texto
    assert "Sem Curva S cadastrada no escopo." in texto
    assert "Análise semanal do período não registrada." in texto
    assert "Relato semanal do período não registrado." in texto
    assert "data-grafico" not in texto


def test_folhas_sem_tipo_ou_periodo_responde_422(cenario: Cenario) -> None:
    resposta = _chamar(cenario, routes.report_screen, alvo=routes.REPORT_TARGET)

    assert resposta.status_code == 422
    assert validation.CHOOSE_MESSAGE in _texto(resposta)


def test_folhas_com_secao_nao_implementada_responde_422(cenario: Cenario) -> None:
    resposta = _chamar(
        cenario,
        routes.report_screen,
        alvo=routes.REPORT_TARGET,
        params={"tipo": WEEKLY, "periodo": _periodo(WEEKLY, -1), "secoes": "carteira"},
    )

    assert resposta.status_code == 422
    assert validation.SECTION_MESSAGE in _texto(resposta)


def test_folhas_com_as_secoes_de_financeiro_e_suprimentos(cenario: Cenario) -> None:
    resposta = _chamar(
        cenario,
        routes.report_screen,
        "Visualizador",
        alvo=routes.REPORT_TARGET,
        params={
            "tipo": WEEKLY,
            "periodo": _periodo(WEEKLY, -1),
            "secoes": "financeiro,suprimentos",
        },
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert texto.count('class="rel-folha"') == 2
    assert 'aria-label="Financeiro"' in texto
    assert 'aria-label="Suprimentos"' in texto
    assert "Sem fechamento mensal de custos até o fim do período." in texto
    assert "Análise semanal do período não registrada." in texto
    assert "Nenhum pedido com folga negativa." in texto
    assert "Nenhum marco de suprimentos realizado no período." in texto


def test_folhas_financeiro_e_suprimentos_do_projeto_1_na_demonstracao(
    sessao_das_rotas: Session, demonstracao: Demonstracao
) -> None:
    resposta = _chamar_rota(
        routes.report_screen,
        colaborador_id=demonstracao.admin.id,
        projeto_id=demonstracao.project_id,
        alvo=routes.REPORT_TARGET,
        params={
            "tipo": WEEKLY,
            "periodo": "2026-S38",
            "secoes": "financeiro,suprimentos",
        },
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert texto.count('class="rel-folha"') == 2
    assert "Curva S financeira" in texto
    assert "Valor agregado mês a mês" in texto
    assert "EAC por pacote" in texto
    assert 'class="rel-heat rel-heat--erro" title="Sobrecusto de 1% a 5%"' in texto
    assert "+R$ 655 mil" in texto
    assert "Curva de contratação" in texto
    assert "Pedidos críticos" in texto
    assert "Previsto nas próximas 4 semanas" in texto
    assert "PED-2026-0002" in texto
    assert "PC-14" in texto
    assert texto.count('data-grafico="curva-s-linha"') == 2
    assert "Comentário pendente" not in texto


def test_folhas_do_portfolio(cenario: Cenario) -> None:
    resposta = _chamar_rota(
        routes.report_screen,
        colaborador_id=cenario.colaboradores["Membro"],
        projeto_id=None,
        alvo=routes.REPORT_TARGET,
        params={"tipo": WEEKLY, "periodo": _periodo(WEEKLY, -1)},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Portfólio · 1 projeto" in texto
    assert "Relatos dos projetos" in texto


def test_folhas_do_projeto_1_na_demonstracao(
    sessao_das_rotas: Session, demonstracao: Demonstracao
) -> None:
    resposta = _chamar_rota(
        routes.report_screen,
        colaborador_id=demonstracao.admin.id,
        projeto_id=demonstracao.project_id,
        alvo=routes.REPORT_TARGET,
        params={"tipo": WEEKLY, "periodo": "2026-S38", "secoes": "planejamento"},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "65,7%" in texto
    assert "61,8%" in texto
    assert "0,94" in texto
    assert "Alfa Montagens" in texto
    assert 'data-grafico="curva-s-linha"' in texto
    assert 'data-grafico="curva-s-barra-linha"' in texto
    assert "Avanço por semana" in texto
    assert "Atividades do período" in texto
    assert "Comentário pendente" not in texto
    assert "Análise semanal do período não registrada." not in texto
    assert "Relato semanal do período não registrado." not in texto


def test_folhas_do_portfolio_na_demonstracao(
    sessao_das_rotas: Session, demonstracao: Demonstracao
) -> None:
    resposta = _chamar_rota(
        routes.report_screen,
        colaborador_id=demonstracao.admin.id,
        projeto_id=None,
        alvo=routes.REPORT_TARGET,
        params={"tipo": WEEKLY, "periodo": "2026-S38", "secoes": "planejamento"},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Portfólio · 3 projetos" in texto
    assert "Relatos dos projetos" in texto
    assert "Pontos de atenção e riscos dos projetos" in texto
    assert "Avanço por projeto" in texto


# ── As folhas Riscos, Qualidade, HSE e Carteira (ISSUE-085) ────────────────


def test_folhas_de_riscos_qualidade_e_hse_do_projeto_1(
    sessao_das_rotas: Session, demonstracao: Demonstracao
) -> None:
    resposta = _chamar_rota(
        routes.report_screen,
        colaborador_id=demonstracao.admin.id,
        projeto_id=demonstracao.project_id,
        alvo=routes.REPORT_TARGET,
        params={"tipo": WEEKLY, "periodo": "2026-S38", "secoes": "riscos,qualidade,hse"},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert texto.count('class="rel-folha"') == 3
    assert 'aria-label="Riscos"' in texto
    assert 'aria-label="Qualidade"' in texto
    assert 'aria-label="HSE"' in texto
    assert "Carteira de projetos" not in texto
    assert "Matriz P x I" in texto
    assert 'class="rel-matriz__cel rel-matriz__cel--erro" title="P4 x I4"' in texto
    assert "RSK-0004" in texto
    assert "RNC-TN-2026-0004" in texto
    assert "Pirâmide de segurança" in texto
    assert texto.count('data-grafico="curva-s-barra-linha"') == 2
    assert 'data-grafico="piramide-seguranca"' in texto
    assert 'data-grafico="linhas-multiplas"' in texto
    assert "Comentário pendente" not in texto


def test_folhas_do_portfolio_com_a_carteira_primeiro(
    sessao_das_rotas: Session, demonstracao: Demonstracao
) -> None:
    resposta = _chamar_rota(
        routes.report_screen,
        colaborador_id=demonstracao.admin.id,
        projeto_id=None,
        alvo=routes.REPORT_TARGET,
        params={"tipo": WEEKLY, "periodo": "2026-S38", "secoes": "riscos"},
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert texto.count('class="rel-folha"') == 2
    assert texto.index('aria-label="Carteira de projetos"') < texto.index('aria-label="Riscos"')
    assert "Total da carteira" in texto
    assert "55,4%" in texto
    assert "Valor financeiro (orçamento vigente)" in texto
    assert "nota de 1 a 5 por projeto" in texto
    assert 'data-grafico="curva-s-linha"' in texto
    assert 'data-grafico="curva-s-barra-linha"' in texto
    assert "RSK-CB-2026-0001" in texto
