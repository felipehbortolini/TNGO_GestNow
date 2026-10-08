"""As rotas do plano de compras (ISSUE-058): a tela, o formulário e as recusas no modal.

A rota roda na transação do teste (fixture ``sessao``), no modo demonstração e com o relógio em
25/09/2026. A requisição é montada como o shell a envia: cabeçalho do Alpine AJAX, o principal
do colaborador e o escopo no parâmetro ``projeto``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modulos.suprimentos import routes
from src.modulos.suprimentos.models import PurchasePackage
from tests.apoio_pacotes import (
    ANA,
    ITEM_CODE,
    PACKAGE_CODE,
    VITOR,
    CenarioPlano,
    montar_cenario_do_plano,
)
from tests.identidades import requisicao


@pytest.fixture
def cenario_plano(sessao: Session) -> CenarioPlano:
    """O cenário do plano na sessão do teste, servindo as rotas pela unidade de trabalho."""
    return montar_cenario_do_plano(sessao)


def _params(cenario: CenarioPlano) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


def _post(cenario: CenarioPlano, caminho: str, **corpo: str):
    partes = caminho.rstrip("/").split("/")
    rota = {"pacote_id": partes[-2]} if partes[-1] == "editar" else {}
    return requisicao(
        caminho,
        metodo="POST",
        email=ANA,
        params=_params(cenario),
        rota=rota,
        corpo=corpo,
        alvo="pacote-modal-corpo",
    )


def _campos_novos(cenario: CenarioPlano, **extras: str) -> dict[str, str]:
    corpo = {
        "escopo": "Compressores de ar",
        "tipo": "Equipamento",
        "modalidade": "Preço global",
        "disciplina": str(cenario.disciplina.id),
        "comprador": str(cenario.ana.person_id),
        "eac": ITEM_CODE,
        "estimativa": "500.000,00",
        "requisicao": "2026-10-01",
        "rfx": "2026-10-15",
        "adjudicacao": "2026-11-20",
        "pedido": "2026-11-25",
        "ros": "2027-03-15",
    }
    corpo.update(extras)
    return corpo


def test_a_rota_da_lista_responde_o_fragmento_da_tela(cenario_plano: CenarioPlano) -> None:
    resposta = routes.package_list(
        requisicao(
            "/api/suprimentos/plano-de-compras",
            email=ANA,
            params=_params(cenario_plano),
            alvo="plano-compras-conteudo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert 'id="plano-compras-conteudo"' in corpo
    assert PACKAGE_CODE in corpo


def test_a_rota_novo_responde_o_formulario_com_o_saldo(cenario_plano: CenarioPlano) -> None:
    resposta = routes.package_form(
        requisicao(
            "/api/suprimentos/plano-de-compras/novo",
            email=ANA,
            params=_params(cenario_plano),
            alvo="pacote-modal-corpo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Saldo a comprometer" in corpo
    assert 'data-saldo-centavos="60000000"' in corpo


def test_a_rota_editar_desenha_o_formulario_congelado(cenario_plano: CenarioPlano) -> None:
    resposta = routes.package_edit_form(
        requisicao(
            f"/api/suprimentos/plano-de-compras/{cenario_plano.pacote.id}/editar",
            email=ANA,
            params=_params(cenario_plano),
            rota={"pacote_id": str(cenario_plano.pacote.id)},
            alvo="pacote-modal-corpo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "congelada desde a requisição" in corpo
    assert "Justificativa da alteração" in corpo
    assert "Requisição (LB)" not in corpo, "o formulário congelado não traz a linha de base"


def test_o_post_cria_o_pacote_e_responde_a_tela(
    sessao: Session, cenario_plano: CenarioPlano
) -> None:
    resposta = routes.package_save(
        _post(
            cenario_plano,
            "/api/suprimentos/plano-de-compras/novo",
            **_campos_novos(cenario_plano),
        )
    )

    assert resposta.status_code == 200
    criado = sessao.scalars(select(PurchasePackage).where(PurchasePackage.code == "PC-02")).one()
    assert criado.project_id == cenario_plano.projeto.id
    assert criado.estimate_cents == 50_000_000


def test_o_post_invalido_devolve_o_formulario_no_modal(cenario_plano: CenarioPlano) -> None:
    resposta = routes.package_save(
        _post(
            cenario_plano,
            "/api/suprimentos/plano-de-compras/novo",
            **_campos_novos(cenario_plano, eac=""),
        )
    )

    assert resposta.status_code == 422
    corpo = resposta.get_body().decode()
    assert "item da EAC" in corpo
    assert 'id="pacote-modal-corpo"' in corpo


def test_o_post_de_congelado_com_campo_da_lb_e_recusado(
    sessao: Session, cenario_plano: CenarioPlano
) -> None:
    resposta = routes.package_edit_save(
        _post(
            cenario_plano,
            f"/api/suprimentos/plano-de-compras/{cenario_plano.pacote.id}/editar",
            escopo="Compressores de ar revisados",
            comprador=str(cenario_plano.ana.person_id),
            estimativa="450.000,00",
            ros="2027-04-15",
            justificativa="O ROS mudou com o cronograma do projeto.",
            versao=str(cenario_plano.pacote.version),
            tipo="Material",
        )
    )

    assert resposta.status_code == 422
    assert "congelada" in resposta.get_body().decode()
    sessao.refresh(cenario_plano.pacote)
    assert cenario_plano.pacote.scope == "Compressores de ar"


def test_o_post_de_congelado_com_mudanca_justificada_grava(
    sessao: Session, cenario_plano: CenarioPlano
) -> None:
    resposta = routes.package_edit_save(
        _post(
            cenario_plano,
            f"/api/suprimentos/plano-de-compras/{cenario_plano.pacote.id}/editar",
            escopo="Compressores de ar revisados",
            comprador=str(cenario_plano.ana.person_id),
            estimativa="450.000,00",
            ros="2027-04-15",
            justificativa="O ROS mudou com o cronograma do projeto.",
            versao=str(cenario_plano.pacote.version),
        )
    )

    assert resposta.status_code == 200
    sessao.refresh(cenario_plano.pacote)
    assert cenario_plano.pacote.scope == "Compressores de ar revisados"
    assert cenario_plano.pacote.ros.isoformat() == "2027-04-15"


def test_o_visualizador_recebe_403_na_gravacao(cenario_plano: CenarioPlano) -> None:
    resposta = routes.package_save(
        requisicao(
            "/api/suprimentos/plano-de-compras/novo",
            metodo="POST",
            email=VITOR,
            params=_params(cenario_plano),
            corpo=_campos_novos(cenario_plano),
            alvo="pacote-modal-corpo",
        )
    )

    assert resposta.status_code == 403


def test_o_pacote_fora_do_escopo_nao_abre(cenario_plano: CenarioPlano) -> None:
    resposta = routes.package_edit_form(
        requisicao(
            f"/api/suprimentos/plano-de-compras/{cenario_plano.pacote.id}/editar",
            email=ANA,
            params={"projeto": str(cenario_plano.outro.id)},
            rota={"pacote_id": str(cenario_plano.pacote.id)},
            alvo="pacote-modal-corpo",
        )
    )

    assert resposta.status_code == 422
