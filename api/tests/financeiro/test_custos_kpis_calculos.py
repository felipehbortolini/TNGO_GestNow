"""Cálculos dos KPIs de custo (ISSUE-042): CPI, SPI, CV, SV, VAC, EAC pelo CPI e TCPI.

O cenário de 25/09/2026: BAC de R$ 44,6 mi, EV de 61,8% do avanço físico real sobre o BAC, PV
de 65,7% da linha de base e AC de R$ 28,7 mi dão CPI 0,96 e SPI de custo 0,94, como o protótipo
afirma. Fronteiras: sem AC o CPI e a EAC pelo CPI não existem; com BAC igual ao AC o TCPI não
existe; sem EV o CPI é zero e a EAC pelo CPI não existe.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.financeiro.calculations import (
    committed_percent,
    cost_indicators,
    cost_performance_index,
    cost_schedule_index,
    estimate_variance,
    reserve_consumption_pct,
    value_aggregated_month,
)

D = Decimal

BAC = 4_460_000_000
EV = 2_756_280_000
PV = 2_930_220_000
AC = 2_870_000_000
PROJECTION = 4_525_500_000


def test_indices_do_cenario_do_prototipo() -> None:
    indicators = cost_indicators(bac_cents=BAC, ev_cents=EV, pv_cents=PV, ac_cents=AC)

    assert indicators.cpi == D("0.96")
    assert indicators.spi == D("0.94")
    assert indicators.cv_cents == -113_720_000
    assert indicators.sv_cents == -173_940_000
    assert indicators.eac_by_cpi_cents == 4_644_012_945
    assert indicators.tcpi == D("1.07")


def test_vac_e_o_bac_menos_a_projecao_no_termino() -> None:
    assert estimate_variance(BAC, PROJECTION) == -65_500_000
    assert estimate_variance(BAC, BAC) == 0


def test_sem_ac_o_cpi_e_a_eac_pelo_cpi_nao_existem() -> None:
    indicators = cost_indicators(bac_cents=BAC, ev_cents=EV, pv_cents=PV, ac_cents=0)

    assert cost_performance_index(EV, 0) is None
    assert indicators.cpi is None
    assert indicators.eac_by_cpi_cents is None
    assert indicators.cv_cents == EV
    assert indicators.tcpi == D("0.38")


def test_bac_igual_ao_ac_nao_tem_tcpi() -> None:
    indicators = cost_indicators(bac_cents=BAC, ev_cents=EV, pv_cents=PV, ac_cents=BAC)

    assert indicators.tcpi is None


def test_sem_ev_o_cpi_e_zero_e_a_eac_pelo_cpi_nao_existe() -> None:
    indicators = cost_indicators(bac_cents=BAC, ev_cents=0, pv_cents=PV, ac_cents=AC)

    assert indicators.cpi == D("0.00")
    assert indicators.spi == D("0.00")
    assert indicators.eac_by_cpi_cents is None
    assert indicators.tcpi == D("2.81")


def test_cpi_que_arredonda_para_zero_nao_projeta_a_eac() -> None:
    indicators = cost_indicators(bac_cents=BAC, ev_cents=1, pv_cents=PV, ac_cents=1_000)

    assert indicators.cpi == D("0.00")
    assert indicators.eac_by_cpi_cents is None


def test_sem_pv_o_spi_de_custo_nao_existe() -> None:
    assert cost_schedule_index(EV, 0) is None
    assert cost_indicators(bac_cents=BAC, ev_cents=EV, pv_cents=0, ac_cents=AC).spi is None


def test_valor_agregado_do_mes_do_cenario() -> None:
    point = value_aggregated_month(
        month=date(2026, 9, 1),
        bac_cents=BAC,
        physical_actual_pct=D("61.8"),
        pv_cents=PV,
        ac_cents=AC,
    )

    assert point is not None
    assert point.ev_cents == EV
    assert (point.cpi, point.spi) == (D("0.96"), D("0.94"))
    assert (point.cv_cents, point.sv_cents) == (-113_720_000, -173_940_000)


def test_valor_agregado_sem_avanco_real_ou_sem_realizado_nao_existe() -> None:
    sem_avanco = value_aggregated_month(
        month=date(2026, 9, 1),
        bac_cents=BAC,
        physical_actual_pct=None,
        pv_cents=PV,
        ac_cents=AC,
    )
    sem_realizado = value_aggregated_month(
        month=date(2026, 9, 1),
        bac_cents=BAC,
        physical_actual_pct=D("61.8"),
        pv_cents=PV,
        ac_cents=None,
    )

    assert sem_avanco is None
    assert sem_realizado is None


def test_percentual_comprometido_e_consumo_da_contingencia() -> None:
    assert committed_percent(4_113_000_000, BAC) == D("92.2")
    assert committed_percent(1_000, 0) is None
    assert reserve_consumption_pct(30_000_000, 200_000_000) == D("15.0")
    assert reserve_consumption_pct(1_000, 0) is None
