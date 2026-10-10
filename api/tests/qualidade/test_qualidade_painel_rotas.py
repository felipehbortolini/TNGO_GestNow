"""As rotas do painel da Qualidade (ISSUE-071, D11, D12, D14): o fragmento, o gate e as exportações.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.core import calendario
from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.qualidade import painel_routes, service
from tests.apoio_qualidade import REFERENCIA, Cenario, nova_abertura, nova_auditoria, usuario_de
from tests.identidades import criar_colaborador


def _requisicao(
    usuario: User,
    *,
    params: Mapping[str, str] | None = None,
    alvo: str = "painel-conteudo",
    cabecalho: bool = True,
) -> func.HttpRequest:
    headers = {
        "X-Alpine-Target": alvo,
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if cabecalho:
        headers["X-Alpine-Request"] = "true"
    return func.HttpRequest(
        method="GET",
        url="/api/qualidade/painel",
        headers=headers,
        params=dict(params or {}),
        route_params={},
        body=b"",
    )


def _abrir(sessao: Session, cenario: Cenario) -> str:
    resultado = service.open_rnc(
        sessao, user=cenario.mario, data=nova_abertura(cenario), reference_date=REFERENCIA
    )
    return resultado.code


def _abrir_vencida(sessao: Session, cenario: Cenario) -> str:
    """Abre uma RNC do prazo vencido: ela entra na pauta e leva o número e o projeto à tela."""
    resultado = service.open_rnc(
        sessao,
        user=cenario.mario,
        data=nova_abertura(cenario, severity="Menor", rnc_date=REFERENCIA - timedelta(days=90)),
        reference_date=REFERENCIA,
    )
    return resultado.code


# ── O painel ─────────────────────────────────────────────────────────────────────────────────


def test_o_painel_mostra_kpis_graficos_tabelas_e_exportacoes(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _abrir_vencida(sessao, cenario)

    resposta = painel_routes.quality_panel_view(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "RNC em aberto" in corpo
    assert "Aprovação em inspeções" in corpo
    assert "Conformidade em auditorias" in corpo
    assert "Custo da não qualidade" in corpo
    assert 'data-grafico="curva-s-barra-linha"' in corpo
    assert 'data-grafico="linhas-multiplas"' in corpo
    assert 'data-grafico="pareto"' in corpo
    assert 'data-grafico="comparativo-barras"' in corpo
    assert "Pauta de tratamento" in corpo
    assert "Desempenho da qualidade por empresa" in corpo
    assert "Não conformidades" in corpo
    assert 'data-tn-excel="/api/qualidade/painel/excel"' in corpo
    assert 'data-tn-pdf="/api/qualidade/painel/imprimivel"' in corpo
    assert codigo in corpo
    assert 'data-situacao="conteudo"' in corpo


def test_o_alerta_de_auditorias_atrasadas_aparece_e_some(
    sessao: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    sem_alerta = (
        painel_routes.quality_panel_view(
            _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
        )
        .get_body()
        .decode()
    )
    assert "auditoria atrasada" not in sem_alerta

    planejada = service.create_audit(
        sessao,
        user=cenario.mario,
        data=nova_auditoria(cenario, audit_date=REFERENCIA + timedelta(days=40)),
        reference_date=REFERENCIA,
    )
    monkeypatch.setattr(calendario, "today", lambda: REFERENCIA + timedelta(days=60))
    com_alerta = (
        painel_routes.quality_panel_view(
            _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
        )
        .get_body()
        .decode()
    )

    assert "auditoria atrasada" in com_alerta
    assert planejada.code in com_alerta
    assert "Controle tecnológico do concreto" in com_alerta


def test_o_painel_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    _abrir_vencida(sessao, cenario)

    corpo = painel_routes.quality_panel_view(_requisicao(cenario.mario)).get_body().decode()

    assert "Pauta de tratamento" in corpo
    assert ">Projeto</th>" in corpo
    assert "TN-RNC-001" in corpo


def test_o_vazio_de_origem_marca_a_situacao(cenario: Cenario) -> None:
    resposta = painel_routes.quality_panel_view(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'data-situacao="vazio-origem"' in corpo
    assert "Ainda não há registros da qualidade" in corpo


def test_sem_o_cabecalho_do_alpine_o_painel_manda_para_o_shell(cenario: Cenario) -> None:
    resposta = painel_routes.quality_panel_view(
        _requisicao(cenario.mario, params={"projeto": str(cenario.projeto.id)}, cabecalho=False)
    )

    assert resposta.status_code == 302


def test_o_fornecedor_nao_alcanca_o_painel(sessao: Session, cenario: Cenario) -> None:
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

    resposta = painel_routes.quality_panel_view(_requisicao(fornecedor))

    assert resposta.status_code == 403


# ── As exportações ───────────────────────────────────────────────────────────────────────────


def test_as_exportacoes_do_painel_saem_com_o_mesmo_conteudo(
    sessao: Session, cenario: Cenario
) -> None:
    _abrir(sessao, cenario)

    excel = painel_routes.quality_panel_excel(
        _requisicao(
            cenario.mario, params={"projeto": str(cenario.projeto.id)}, alvo="painel-conteudo"
        )
    )
    imprimivel = painel_routes.quality_panel_printable(
        _requisicao(
            cenario.mario, params={"projeto": str(cenario.projeto.id)}, alvo="painel-conteudo"
        )
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    corpo = imprimivel.get_body().decode()
    assert imprimivel.status_code == 200
    assert "Painel da qualidade" in corpo
    assert "Pauta de tratamento" in corpo
    assert "Desempenho por empresa" in corpo
    assert 'data-grafico="pareto"' in corpo


def test_as_exportacoes_no_portfolio_trazem_o_projeto(sessao: Session, cenario: Cenario) -> None:
    _abrir_vencida(sessao, cenario)

    imprimivel = painel_routes.quality_panel_printable(
        _requisicao(cenario.mario, alvo="painel-conteudo")
    )

    corpo = imprimivel.get_body().decode()
    assert ">Projeto</th>" in corpo
    assert "TN-RNC-001" in corpo
