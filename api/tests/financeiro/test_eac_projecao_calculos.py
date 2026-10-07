"""Cálculos puros da projeção, do desvio e das faixas do mapa de calor (ISSUE-031, D6).

As três fórmulas do mapa (orçado atual, saldo a comprometer e desvio, com o positivo sendo
sobrecusto), a projeção vigente entre o histórico manual e o do ERP, os totais do ERP até a data
de corte e as faixas do mapa de calor, que mudam quando o parâmetro muda.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.financeiro.calculations import (
    ERP_ORIGIN,
    MANUAL_ORIGIN,
    ErpCostFact,
    ErpTotals,
    ItemLine,
    ProjectionFact,
    baseline_base_cents,
    deviation_band,
    deviation_cents,
    deviation_heatmap_faixas,
    deviation_percent,
    erp_totals_until,
    latest_projections,
    projected_total_cents,
    reallocation_cents,
    saldo_a_comprometer_cents,
)

D = Decimal


def _item(
    identifier: int, quantity: str, price: int, *, parent_id: int | None = None, **fields: object
) -> ItemLine:
    return ItemLine(
        id=identifier,
        parent_id=parent_id,
        code=str(identifier),
        description="Item",
        level=3,
        quantity=D(quantity),
        unit_price_cents=price,
        **fields,
    )


# ── Linha de base, orçado atual e remanejamentos ─────────────────────────


def test_linha_de_base_sem_revisao_e_quantidade_vezes_preco() -> None:
    items = [_item(1, "10", 1_000), _item(2, "2", 500)]

    bases = baseline_base_cents(items, revision_bases={}, latest_revision=None)

    assert bases == {1: 10_000, 2: 1_000}


def test_linha_de_base_com_revisao_usa_a_base_congelada_e_zero_fora_dela() -> None:
    items = [_item(1, "10", 1_000), _item(2, "2", 500)]

    bases = baseline_base_cents(items, revision_bases={1: 9_000}, latest_revision=2)

    assert bases == {1: 9_000, 2: 0}


def test_remanejamento_e_o_orcado_atual_menos_a_linha_de_base() -> None:
    assert reallocation_cents(12_000, 10_000) == 2_000
    assert reallocation_cents(8_500, 10_000) == -1_500


def test_saldo_a_comprometer_e_o_orcado_atual_menos_o_comprometido() -> None:
    assert saldo_a_comprometer_cents(10_000, 6_000) == 4_000


def test_saldo_a_comprometer_fica_negativo_quando_o_comprometido_supera_o_orcado() -> None:
    assert saldo_a_comprometer_cents(10_000, 12_500) == -2_500


# ── Desvio ───────────────────────────────────────────────────────────────


def test_desvio_positivo_quando_a_projecao_supera_o_orcado_atual() -> None:
    assert deviation_cents(11_000, 10_000) == 1_000


def test_desvio_negativo_quando_a_projecao_fica_abaixo_do_orcado_atual() -> None:
    assert deviation_cents(9_500, 10_000) == -500


def test_desvio_percentual_tem_uma_casa_e_nenhum_com_orcado_zero() -> None:
    assert deviation_percent(1_000, 10_000) == D("10.0")
    assert deviation_percent(-500, 10_000) == D("-5.0")
    assert deviation_percent(500, 0) is None


# ── Faixas do mapa de calor ──────────────────────────────────────────────


def test_desvio_dentro_da_primeira_faixa_e_neutro() -> None:
    band = deviation_band(D("0.9"))

    assert (band.key, band.tone, band.level) == ("neutro", "neutro", 0)


def test_faixas_seguem_os_limites_do_prototipo_nas_fronteiras() -> None:
    assert deviation_band(D("1.0")).key == "sobrecusto-1"
    assert deviation_band(D("5.0")).key == "sobrecusto-1"
    assert deviation_band(D("5.1")).key == "sobrecusto-2"
    assert deviation_band(D("10.0")).key == "sobrecusto-2"
    assert deviation_band(D("10.1")).key == "sobrecusto-3"


def test_sobrecusto_usa_a_familia_erro_e_economia_a_familia_ok() -> None:
    assert deviation_band(D("7.5")).tone == "erro"
    assert deviation_band(D("-7.5")).tone == "ok"
    assert deviation_band(D("-7.5")).key == "economia-2"


def test_faixas_mudam_quando_o_parametro_muda() -> None:
    assert deviation_band(D("1.0"), (1, 5, 10)).key == "sobrecusto-1"
    assert deviation_band(D("1.0"), (2, 5, 10)).key == "neutro"
    assert deviation_band(D("6.0"), (2, 5, 20)).key == "sobrecusto-2"
    assert deviation_band(D("12.0"), (2, 5, 20)).key == "sobrecusto-2"
    assert deviation_band(D("12.0"), (2, 5, 10)).key == "sobrecusto-3"


def test_desvio_sem_valor_e_neutro() -> None:
    band = deviation_band(None)

    assert (band.key, band.tone, band.level) == ("neutro", "neutro", 0)


def test_desvio_percentual_e_classificado_pelas_faixas_vigentes() -> None:
    percent = deviation_percent(deviation_cents(10_500, 10_000), 10_000)

    band = deviation_band(percent, (1, 5, 10))

    assert band.key == "sobrecusto-1"


def test_faixas_do_visual_tabela_heatmap_seguem_o_mapa_de_calor() -> None:
    faixas = deviation_heatmap_faixas((1, 5, 10))

    assert [faixa["nivel"] for faixa in faixas] == [3, 2, 1, 1, 3, 2, 1]
    assert [faixa["tom"] for faixa in faixas] == [
        "erro",
        "erro",
        "erro",
        "neutro",
        "ok",
        "ok",
        "ok",
    ]
    assert [faixa["icone"] for faixa in faixas] == [
        "sobe",
        "sobe",
        "sobe",
        "igual",
        "desce",
        "desce",
        "desce",
    ]
    assert faixas[0]["rotulo"] == "Sobrecusto acima de 10%"
    assert faixas[3]["rotulo"] == "Até 1%"
    assert faixas[6]["rotulo"] == "Economia de 1% a 5%"


def test_limites_das_faixas_do_visual_seguem_os_parametros_vigentes() -> None:
    faixas = deviation_heatmap_faixas((2, 5, 20))

    assert faixas[0]["maior_que"] == 20.0
    assert faixas[2] == {
        "de": 2.0,
        "ate": 5.0,
        "tom": "erro",
        "nivel": 1,
        "icone": "sobe",
        "rotulo": "Sobrecusto de 2% a 5%",
    }
    assert faixas[3]["maior_que"] == -2.0
    assert faixas[3]["menor_que"] == 2.0
    assert faixas[4]["menor_que"] == -20.0


# ── Projeção vigente e projeção no término ───────────────────────────────


def test_projecao_vigente_e_a_do_fato_mais_recente() -> None:
    facts = [
        ProjectionFact(item_id=1, value_cents=900, on=date(2026, 8, 1), origin=ERP_ORIGIN),
        ProjectionFact(item_id=1, value_cents=1_100, on=date(2026, 9, 25), origin=MANUAL_ORIGIN),
    ]

    assert latest_projections(facts)[1].value_cents == 1_100


def test_projecao_do_erp_de_mes_mais_novo_vence_a_manual() -> None:
    facts = [
        ProjectionFact(item_id=1, value_cents=1_100, on=date(2026, 8, 25), origin=MANUAL_ORIGIN),
        ProjectionFact(item_id=1, value_cents=1_050, on=date(2026, 9, 1), origin=ERP_ORIGIN),
    ]

    assert latest_projections(facts)[1].value_cents == 1_050


def test_no_empate_de_data_a_projecao_do_erp_vence() -> None:
    for facts in (
        [
            ProjectionFact(item_id=1, value_cents=1_100, on=date(2026, 9, 1)),
            ProjectionFact(item_id=1, value_cents=1_050, on=date(2026, 9, 1), origin=ERP_ORIGIN),
        ],
        [
            ProjectionFact(item_id=1, value_cents=1_050, on=date(2026, 9, 1), origin=ERP_ORIGIN),
            ProjectionFact(item_id=1, value_cents=1_100, on=date(2026, 9, 1)),
        ],
    ):
        assert latest_projections(facts)[1].value_cents == 1_050


def test_projecao_no_termino_soma_os_filhos_e_usa_o_orcado_atual_sem_fato() -> None:
    items = [
        ItemLine(id=1, parent_id=None, code="1", description="Pacote", level=1),
        ItemLine(id=2, parent_id=1, code="1.1", description="Subpacote", level=2),
        _item(3, "1", 1, parent_id=2),
        _item(4, "1", 1, parent_id=2),
        ItemLine(id=5, parent_id=None, code="2", description="Pacote", level=1),
        ItemLine(id=6, parent_id=5, code="2.1", description="Subpacote", level=2),
        _item(7, "1", 1, parent_id=6),
    ]
    bases = {1: 30_000, 2: 30_000, 3: 10_000, 4: 20_000, 5: 30_000, 6: 30_000, 7: 30_000}
    facts = [
        ProjectionFact(item_id=3, value_cents=11_000, on=date(2026, 9, 25)),
        ProjectionFact(item_id=7, value_cents=25_000, on=date(2026, 9, 25)),
    ]

    projected = projected_total_cents(items, current_bases=bases, facts=facts)

    assert projected.by_item[3] == 11_000
    assert projected.by_item[4] == 20_000
    assert projected.by_item[1] == 31_000
    assert projected.by_item[5] == 25_000
    assert projected.total_cents == 56_000


# ── Custos do ERP ────────────────────────────────────────────────────────


def test_totais_do_erp_somam_os_meses_ate_a_data_de_corte() -> None:
    facts = [
        ErpCostFact(item_id=1, month=date(2026, 7, 1), committed_cents=1_000, actual_cents=600),
        ErpCostFact(item_id=1, month=date(2026, 8, 1), committed_cents=500, actual_cents=300),
        ErpCostFact(item_id=1, month=date(2026, 9, 1), committed_cents=100, actual_cents=50),
        ErpCostFact(item_id=1, month=date(2026, 10, 1), committed_cents=9_999, actual_cents=9_999),
    ]

    totals = erp_totals_until(facts, cutoff=date(2026, 9, 25))

    assert totals[1] == ErpTotals(committed_cents=1_600, actual_cents=950)


def test_totais_do_erp_separam_os_itens_e_ignoram_o_valor_vazio() -> None:
    facts = [
        ErpCostFact(item_id=1, month=date(2026, 9, 1), projection_cents=2_000),
        ErpCostFact(item_id=2, month=date(2026, 9, 1), committed_cents=300),
    ]

    totals = erp_totals_until(facts, cutoff=date(2026, 9, 30))

    assert totals[1] == ErpTotals(committed_cents=0, actual_cents=0)
    assert totals[2] == ErpTotals(committed_cents=300, actual_cents=0)
