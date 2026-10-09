"""As fórmulas do processo de compra (ISSUE-059): fronteiras das notas, do ranking e das regras.

Todas as funções são puras e recebem a data de referência como argumento quando ela importa; os
casos de fronteira são o valor no próprio limite (a banda da alçada, o menor preço, a soma dos
pesos) e o que não existe (sem preço, sem nota, sem histórico).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.suprimentos import calculations


def test_a_nota_comercial_e_o_menor_preco_sobre_o_preco() -> None:
    assert calculations.commercial_score(100, 100) == Decimal("100.0")
    assert calculations.commercial_score(200, 100) == Decimal("50.0")
    assert calculations.commercial_score(3, 100) == Decimal("3333.3"), "arredonda a uma casa"
    assert calculations.commercial_score(0, 100) is None
    assert calculations.commercial_score(100, None) is None
    assert calculations.commercial_score(None, 100) is None


def test_a_nota_final_pondera_pelos_pesos_e_arredonda() -> None:
    assert calculations.final_score(84, Decimal("100.0"), 40, 60) == Decimal("93.6")
    assert calculations.final_score(84, Decimal("100.0"), 0, 100) == Decimal("100.0")
    assert calculations.final_score(84, Decimal("100.0"), 100, 0) == Decimal("84.0")
    assert calculations.final_score(88, Decimal("93.4"), 40, 60) == Decimal("91.2")
    assert calculations.final_score(None, Decimal("100.0"), 40, 60) is None
    assert calculations.final_score(84, None, 40, 60) is None
    assert calculations.final_score(84, Decimal("100.0"), 0, 0) is None, "sem peso não há nota"


def test_o_ranking_e_nota_final_decrescente_e_preco_crescente() -> None:
    entries = [
        (1, Decimal("90.0"), 40_000_000),
        (2, Decimal("95.0"), 45_000_000),
        (3, Decimal("95.0"), 42_000_000),
        (4, None, 30_000_000),
    ]

    assert calculations.proposal_ranking(entries) == [(3, 1), (2, 2), (1, 3)], (
        "a reprovada fica fora e o empate na nota desempata pelo menor preço"
    )
    assert calculations.proposal_ranking([]) == []


def test_a_banda_da_alcada_e_a_primeira_que_cobre_o_valor() -> None:
    bands = [
        (50_000_000, "Gerente de suprimentos"),
        (500_000_000, "Gerente do projeto"),
        (None, "Comitê"),
    ]

    assert calculations.approval_band_for(0, bands) == "Gerente de suprimentos"
    assert calculations.approval_band_for(50_000_000, bands) == "Gerente de suprimentos", (
        "o teto fecha"
    )
    assert calculations.approval_band_for(50_000_001, bands) == "Gerente do projeto"
    assert calculations.approval_band_for(500_000_001, bands) == "Comitê"
    assert calculations.approval_band_for(10, []) is None


def test_o_fornecedor_unico_e_o_convidado_abaixo_do_minimo() -> None:
    assert calculations.single_supplier(2, 3) is True
    assert calculations.single_supplier(3, 3) is False, "o mínimo vale"


def test_a_situacao_do_passo_segue_a_etapa_do_fluxo() -> None:
    assert calculations.step_situation(1, current=0, done=False) == calculations.STEP_FUTURE
    assert calculations.step_situation(5, current=5, done=False) == calculations.STEP_CURRENT
    assert calculations.step_situation(4, current=5, done=False) == calculations.STEP_DONE
    assert calculations.step_situation(6, current=5, done=False) == calculations.STEP_FUTURE
    assert calculations.step_situation(5, current=5, done=True) == calculations.STEP_CURRENT, (
        "a etapa só anda quando a ação roda"
    )
    assert calculations.step_situation(6, current=5, done=True) == calculations.STEP_DONE, (
        "um fato à frente da etapa conta como feito"
    )
    assert all(
        calculations.step_situation(position, current=9, done=False) == calculations.STEP_DONE
        for position in range(1, 10)
    ), "no último passo todos estão concluídos"


def test_a_etapa_do_processo_e_a_ultima_acao_registrada() -> None:
    assert calculations.process_stage(["RFx emitida", "Propostas recebidas"], "Requisição") == (
        "Propostas recebidas"
    )
    assert calculations.process_stage([], "Equalização técnica") == "Equalização técnica"
    assert calculations.stage_index("Negociação") == 6
    assert calculations.stage_index("Etapa desconhecida") == 0


def test_o_numero_do_processo_e_global_por_tipo_e_ano() -> None:
    assert calculations.next_process_number([], service=False, year=2026) == "RFQ-2026-001"
    assert (
        calculations.next_process_number(
            ["RFQ-2026-014", "RFQ-2026-012", "RFP-2026-003"], service=False, year=2026
        )
        == "RFQ-2026-015"
    ), "o maior número do tipo e do ano"
    assert (
        calculations.next_process_number(["RFQ-2025-099"], service=True, year=2026)
        == "RFP-2026-001"
    ), "o tipo e o ano separam as séries"
    assert (
        calculations.next_process_number(["RFQ-2026-099"], service=False, year=2026)
        == "RFQ-2026-100"
    ), "do 100º em diante o número cresce"


def test_o_tipo_servico_gera_contrato() -> None:
    assert calculations.is_service("Serviço") is True
    assert calculations.is_service("EPC") is True
    assert calculations.is_service("Equipamento") is False
    assert calculations.is_service("Material") is False


def test_o_ciclo_de_compra_vai_da_requisicao_ao_pedido_ou_a_referencia() -> None:
    reference = date(2026, 9, 25)

    assert calculations.cycle_days(None, None, reference) is None
    assert calculations.cycle_days(date(2026, 8, 1), date(2026, 9, 1), reference) == 31
    assert calculations.cycle_days(date(2026, 8, 1), None, reference) == 55
    assert calculations.cycle_days(reference, None, reference) == 0, "a fronteira é o zero"
