"""A fachada do painel de suprimentos (ISSUE-063): os indicadores, as curvas e o escopo.

O cenário do diligenciamento serve: o PC-01 (equipamento) tem pedido emitido com os seis marcos
de fabricação e o PC-02 é um pacote planejado, sem pedido. Os testes completam o cenário com as
datas reais, o processo vivo e o contrato do serviço, e leem o painel pela fachada, na transação
do teste e com o relógio em 25/09/2026.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro.models import Contract
from src.modulos.suprimentos import service
from src.modulos.suprimentos.models import (
    PackageMilestone,
    ProcessProposal,
    PurchaseProcess,
)
from tests.apoio_diligenciamento import (
    REFERENCIA,
    CenarioDiligenciamento,
    montar_cenario_diligenciamento,
)

PEDIDO_REAL = date(2026, 9, 18)
ADJUDICACAO_REAL = date(2026, 9, 15)
CONTRACT_VALUE_CENTS = 30_000_000


@pytest.fixture
def cenario(sessao: Session) -> CenarioDiligenciamento:
    return montar_cenario_diligenciamento(sessao)


def _scope(cenario: CenarioDiligenciamento) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _list(sessao: Session, cenario: CenarioDiligenciamento) -> service.PanelListing:
    return service.list_panel(
        sessao, user=cenario.ana, scope=_scope(cenario), reference_date=REFERENCIA
    )


def _realizar(sessao: Session, cenario: CenarioDiligenciamento) -> None:
    """Realiza a RFx até o pedido do PC-01, para o ciclo e a etapa saírem do realizado."""
    reals = {
        "rfx": date(2026, 8, 10),
        "propostas": date(2026, 8, 31),
        "eqTecnica": date(2026, 9, 5),
        "eqComercial": date(2026, 9, 12),
        "adjudicacao": ADJUDICACAO_REAL,
        "pedido": PEDIDO_REAL,
    }
    for milestone, value in reals.items():
        row = sessao.scalars(
            select(PackageMilestone).where(
                PackageMilestone.package_id == cenario.pacote.id,
                PackageMilestone.milestone == milestone,
            )
        ).one()
        row.real_date = value
    sessao.flush()


def _processo_vivo(sessao: Session, cenario: CenarioDiligenciamento) -> PurchaseProcess:
    """Um processo do PC-01 com a recomendação no primeiro fornecedor e três propostas."""
    processo = PurchaseProcess(
        package_id=cenario.pacote.id,
        number="RFQ-2026-900",
        weight_technical=40,
        weight_commercial=60,
        proposals_deadline=date(2026, 8, 31),
        recommendation_company_id=cenario.fornecedores[0].id,
        recommendation_value_cents=40_000_000,
        version=1,
    )
    sessao.add(processo)
    sessao.flush()
    for index, value in enumerate((45_000_000, 48_000_000, 50_000_000)):
        sessao.add(
            ProcessProposal(
                process_id=processo.id,
                company_id=cenario.fornecedores[0].id if index == 0 else None,
                name=None if index == 0 else f"Sem cadastro {index}",
                received=date(2026, 8, 20),
                value_cents=value,
                deadline_days=90,
                version=1,
            )
        )
    sessao.flush()
    return processo


def _contrato_do_servico(sessao: Session, cenario: CenarioDiligenciamento) -> Contract:
    """O PC-02 vira serviço com o contrato emitido, como no fluxo da emissão (D9)."""
    cenario.planejado.kind = "Serviço"
    contrato = Contract(
        project_id=cenario.projeto.id,
        company_id=cenario.fornecedores[0].id,
        eac_item_id=cenario.item.id,
        purchase_package_id=cenario.planejado.id,
        manager_id=cenario.projeto.manager_id,
        fiscal_id=cenario.ana.person_id,
        number="CT-2026-900",
        object=cenario.planejado.scope,
        modality=cenario.planejado.modality,
        original_value_cents=CONTRACT_VALUE_CENTS,
        start=REFERENCIA,
        original_end=date(2027, 3, 15),
        current_end=date(2027, 3, 15),
        retention_pct=5,
        claim_notice_days=30,
        situation="Em execução",
        version=1,
    )
    sessao.add(contrato)
    sessao.flush()
    return contrato


# ── Os indicadores ───────────────────────────────────────────────────────────────────────────


def test_o_painel_le_o_plano_e_as_curvas_do_escopo(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    _realizar(sessao, cenario)

    listing = _list(sessao, cenario)
    summary = listing.summary

    assert summary.packages == 2
    assert summary.planned_until_reference == 1, "só o PC-01 tinha adjudicação planejada até a data"
    assert summary.adjudicated_until_reference == 1
    assert summary.adherence_pct == Decimal("100.0")
    assert summary.adherence_target == 90, "a meta vem do grupo suprimentos"
    assert summary.otd_target == 90
    assert summary.cycle_days == 48, "01/08 a 18/09"
    assert summary.cycle_baseline_days == 52, "01/08 a 22/09 na LB"
    assert summary.estimate_cents == 50_000_000
    assert summary.adjudicated_cents == 40_000_000, "o valor do pedido"
    assert summary.saving_cents == 10_000_000
    assert summary.saving_pct == Decimal("20.0")
    assert summary.negotiation_saving_pct is None, "sem primeira proposta registrada"
    assert summary.average_offers is None and summary.single_supplier_pct is None
    assert summary.orders.critical == 0
    assert summary.committed_pct == Decimal("40.0"), "40M adjudicados sobre o orçado de 100M"

    assert listing.contracting.planned[-1] == 2, "o plano acumula os dois pacotes"
    assert listing.contracting.realized[-1] is None, "o real para no mês do corte"
    assert listing.progress_curve is not None
    assert [stage.stage for stage in listing.stages] == ["Planejado", "Pedido/contrato emitido"]


def test_o_processo_vivo_vence_as_colunas_da_carga(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    _realizar(sessao, cenario)
    cenario.pacote.first_proposal_cents = 55_000_000
    cenario.pacote.valid_proposals = 5
    cenario.pacote.single_supplier = True
    _processo_vivo(sessao, cenario)

    listing = _list(sessao, cenario)

    assert listing.summary.negotiation_saving_cents == 5_000_000, (
        "45M da primeira proposta menos os 40M adjudicados"
    )
    assert listing.summary.negotiation_saving_pct == Decimal("11.1")
    assert listing.saving.negotiation[-1] == 5_000_000
    assert listing.summary.average_offers == Decimal("3.0"), "as três propostas do processo"
    assert listing.summary.single_supplier_pct == Decimal("100.0"), (
        "sem convidados, fornecedor único"
    )


def test_as_colunas_da_carga_servem_quando_nao_ha_processo(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    _realizar(sessao, cenario)
    cenario.pacote.first_proposal_cents = 50_000_000
    cenario.pacote.valid_proposals = 4
    cenario.pacote.single_supplier = False

    listing = _list(sessao, cenario)

    assert listing.summary.negotiation_saving_cents == 10_000_000
    assert listing.summary.negotiation_saving_pct == Decimal("20.0")
    assert listing.summary.average_offers == Decimal("4.0")
    assert listing.summary.single_supplier_pct == Decimal("0.0")


def test_o_contrato_do_servico_e_o_valor_adjudicado(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    _realizar(sessao, cenario)
    _contrato_do_servico(sessao, cenario)

    listing = _list(sessao, cenario)
    linha = next(line for line in listing.mas.lines if line.code == "PC-02")

    assert linha.adjudicated_cents == CONTRACT_VALUE_CENTS
    assert linha.value_cents == CONTRACT_VALUE_CENTS
    assert linha.contract_number == "CT-2026-900"
    assert listing.summary.adjudicated_cents == 70_000_000, "o pedido do PC-01 mais o contrato"
    assert listing.summary.saving_pct == Decimal("30.0")


# ── A tabela dos pedidos ─────────────────────────────────────────────────────────────────────


def test_os_pedidos_por_folga_saem_do_mas_por_folga_crescente(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    _realizar(sessao, cenario)

    listing = _list(sessao, cenario)

    assert [line.code for line in listing.slack_lines] == ["PC-02", "PC-01"], (
        "o pacote sem pedido tem a folga estimada (zero) e o pedido do PC-01 tem folga"
    )
    por_codigo = {line.code: line for line in listing.slack_lines}
    assert por_codigo["PC-01"].supplier == cenario.fornecedores[0].name
    assert por_codigo["PC-02"].supplier == "", "o pacote em contratação não tem fornecedor"


def test_o_pacote_de_servico_fica_fora_da_tabela(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    _realizar(sessao, cenario)
    _contrato_do_servico(sessao, cenario)

    listing = _list(sessao, cenario)

    assert [line.code for line in listing.slack_lines] == ["PC-01"], (
        "o contrato do serviço não tem entrega e não entra na folga"
    )


def test_as_metas_do_painel_vem_dos_parametros_vigentes(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    valores = deepcopy(configuracoes.INITIAL_PARAMETERS["suprimentos"])
    valores["metaAderenciaPct"] = 80
    valores["metaOtdPct"] = 95
    configuracoes.save_parameter_group(
        sessao,
        author_id=cenario.ana.id,
        group="suprimentos",
        values=valores,
        effective_from=REFERENCIA,
        justification="Metas do painel revisadas na reunião de compras.",
    )

    listing = _list(sessao, cenario)

    assert listing.summary.adherence_target == 80
    assert listing.summary.otd_target == 95


def test_o_visualizador_le_o_painel(sessao: Session, cenario: CenarioDiligenciamento) -> None:
    listing = service.list_panel(
        sessao, user=cenario.vitor, scope=_scope(cenario), reference_date=REFERENCIA
    )

    assert listing.summary.packages == 2
