"""A fachada do MAS (ISSUE-062): uma linha por pacote, os doze marcos, os filtros e o escopo.

O cenário do diligenciamento serve: um pacote congelado com pedido emitido (PC-01), um pacote
planejado sem pedido (PC-02) e os dois projetos. O MAS lê o plano, o pedido e o processo, sem
cadastro próprio; a linha de um pacote sem pedido estima a LB de fabricação entre o pedido e o
ROS, e os filtros cortam a tabela. Tudo roda na transação do teste, com o relógio em 25/09/2026.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session

from src.core.scope import Scope
from src.modulos.suprimentos import calculations, service, validation
from tests.apoio_diligenciamento import (
    CRITICAL_ROS,
    REFERENCIA,
    CenarioDiligenciamento,
    montar_cenario_diligenciamento,
)


@pytest.fixture
def cenario(sessao: Session) -> CenarioDiligenciamento:
    return montar_cenario_diligenciamento(sessao)


def _scope(cenario: CenarioDiligenciamento) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _list(
    sessao: Session,
    cenario: CenarioDiligenciamento,
    **filtros: Any,
) -> service.MasListing:
    return service.list_mas(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        filters=validation.MasFilters(**filtros),
        reference_date=REFERENCIA,
    )


# ── A leitura ───────────────────────────────────────────────────────────────────────────────


def test_a_lista_traz_uma_linha_por_pacote_com_os_doze_marcos(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    listing = _list(sessao, cenario)

    assert [line.code for line in listing.lines] == ["PC-01", "PC-02"]
    for line in listing.lines:
        assert len(line.milestones) == 12
        fases = {item.phase for item in line.milestones}
        assert fases == {calculations.MAS_ACQUISITION, calculations.MAS_FABRICATION}
    assert len(listing.columns) == 12


def test_o_pacote_com_pedido_le_a_fabricacao_do_cronograma_contratual(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    listing = _list(sessao, cenario)
    linha = next(line for line in listing.lines if line.code == "PC-01")
    documentos = linha.milestone("documentos")

    assert documentos is not None
    assert documentos.estimated is False
    assert documentos.baseline == date(2026, 10, 5), "15% entre a emissão e a data contratual"
    assert documentos.applicable is True
    assert linha.order_number == "PED-2026-0001"
    assert linha.adjudicated_cents == 40_000_000
    assert linha.value_cents == 40_000_000


def test_o_pacote_sem_pedido_estima_a_lb_de_fabricacao(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    listing = _list(sessao, cenario)
    linha = next(line for line in listing.lines if line.code == "PC-02")
    documentos = linha.milestone("documentos")
    entrega = linha.milestone("entrega")

    assert documentos is not None
    assert documentos.estimated is True
    assert documentos.baseline == date(2026, 12, 12), "15% entre o pedido planejado e o ROS"
    assert entrega is not None
    assert entrega.baseline == linha.ros, "a estimativa termina no ROS"
    assert linha.adjudicated_cents is None
    assert linha.value_cents == linha.estimate_cents


def test_a_fabricacao_de_um_pacote_de_servico_nao_se_aplica(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    cenario.pacote.kind = "Serviço"
    sessao.flush()

    listing = _list(sessao, cenario)
    linha = next(line for line in listing.lines if line.code == "PC-01")
    fabricacao = [item for item in linha.milestones if item.phase == calculations.MAS_FABRICATION]

    assert all(item.situation == calculations.MILESTONE_NOT_APPLICABLE for item in fabricacao)
    assert all(item.applicable is False for item in fabricacao)
    assert linha.service is True


def test_o_resumo_conta_o_universo_e_o_avanco_ponderado(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    listing = _list(sessao, cenario)

    assert listing.summary.items == 2
    assert listing.summary.with_baseline == 2
    assert listing.summary.overdue_milestones == 6, "as datas do plano do PC-01 já passaram"
    assert listing.summary.realized_pct == Decimal("2.2")
    assert listing.summary.planned_pct == Decimal("17.8")
    assert listing.summary.index == Decimal("0.12")


def test_o_escopo_do_projeto_nao_ve_o_pacote_do_outro(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    listing = service.list_mas(
        sessao,
        user=cenario.ana,
        scope=Scope(project_id=cenario.outro.id, source="url"),
        filters=validation.MasFilters(),
        reference_date=REFERENCIA,
    )

    assert listing.lines == ()


# ── Os filtros ──────────────────────────────────────────────────────────────────────────────


def test_o_filtro_de_fase_corta_as_colunas(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    aquisicao = _list(sessao, cenario, phase="aquisicao")
    fabricacao = _list(sessao, cenario, phase="fabricacao")

    assert len(aquisicao.columns) == 7
    assert {column.phase for column in aquisicao.columns} == {calculations.MAS_ACQUISITION}
    assert len(fabricacao.columns) == 5
    assert {column.phase for column in fabricacao.columns} == {calculations.MAS_FABRICATION}


def test_os_filtros_de_tipo_lli_comprador_e_fornecedor(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    cenario.pacote.lli = True
    sessao.flush()

    assert [line.code for line in _list(sessao, cenario, kind="Serviço").lines] == []
    assert [line.code for line in _list(sessao, cenario, kind="Equipamento").lines] == [
        "PC-01",
        "PC-02",
    ]
    assert [line.code for line in _list(sessao, cenario, lli="sim").lines] == ["PC-01"]
    assert [line.code for line in _list(sessao, cenario, lli="nao").lines] == ["PC-02"]
    assert [line.code for line in _list(sessao, cenario, buyer_id=cenario.ana.person_id).lines] == [
        "PC-01",
        "PC-02",
    ]
    assert [
        line.code for line in _list(sessao, cenario, supplier_id=cenario.fornecedores[0].id).lines
    ] == ["PC-01"]


def test_os_filtros_de_situacao_vencidos_e_busca(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    cenario.pacote.ros = CRITICAL_ROS
    sessao.flush()

    assert [line.code for line in _list(sessao, cenario, situation="Crítico").lines] == ["PC-01"]
    assert [line.code for line in _list(sessao, cenario, situation="Atenção").lines] == ["PC-02"]
    assert [line.code for line in _list(sessao, cenario, overdue_only=True).lines] == ["PC-01"]
    assert [line.code for line in _list(sessao, cenario, search="reserva").lines] == ["PC-02"]
    assert [line.code for line in _list(sessao, cenario, search="PED-2026-0001").lines] == ["PC-01"]


def test_a_ordenacao_por_valor_e_por_folga(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    por_valor = _list(sessao, cenario, order="valor")
    por_folga = _list(sessao, cenario, order="folga")

    assert [line.code for line in por_valor.lines] == ["PC-02", "PC-01"]
    assert [line.code for line in por_folga.lines] == ["PC-02", "PC-01"], "folga 0 antes de 91"


def test_o_rodape_conta_realizados_sobre_previstos(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    listing = _list(sessao, cenario, phase="aquisicao")
    requisicao = next(total for total in listing.totals if total.key == "requisicao")
    pedido = next(total for total in listing.totals if total.key == "pedido")

    assert (requisicao.realized, requisicao.planned) == (1, 1)
    assert (pedido.realized, pedido.planned) == (0, 1)


def test_as_escolhas_dos_filtros_saem_do_universo(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    listing = _list(sessao, cenario)

    assert {choice.name for choice in listing.buyers} == {"Ana Admin"}
    assert {choice.name for choice in listing.suppliers} == {cenario.fornecedores[0].name}
    assert listing.disciplines, "as disciplinas do cadastro alimentam o filtro"
