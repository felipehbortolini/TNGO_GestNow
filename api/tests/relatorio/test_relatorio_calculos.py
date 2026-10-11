"""Cálculos do motor de corte do relatório gerencial (ISSUE-083): corte, parcial, competência e barras.

O corte é o fim do período limitado à data de referência; o período em andamento sai marcado
parcial. As barras do avanço por período são as últimas 8 semanas ou 6 meses até o corte, sem
os períodos anteriores ao início do projeto, e cada barra é o incremento entre pontos
acumulados. O mês de competência do custo é o último mês fechado no semanal.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.relatorio import calculations

D = Decimal

SEMANA = "Semanal"

MES = "Mensal"


def test_corte_da_semana_no_meio_do_mes_e_o_fim_da_semana() -> None:
    assert calculations.report_period_cutoff(SEMANA, "2026-S38", date(2026, 9, 25)) == date(
        2026, 9, 20
    )


def test_corte_do_periodo_passado_e_o_fim_do_periodo() -> None:
    assert calculations.report_period_cutoff(SEMANA, "2026-S38", date(2026, 10, 11)) == date(
        2026, 9, 20
    )
    assert calculations.report_period_cutoff(MES, "2026-08", date(2026, 10, 11)) == date(
        2026, 8, 31
    )


def test_corte_do_periodo_corrente_e_a_data_de_referencia() -> None:
    assert calculations.report_period_cutoff(SEMANA, "2026-S38", date(2026, 9, 16)) == date(
        2026, 9, 16
    )
    assert calculations.report_period_cutoff(MES, "2026-09", date(2026, 9, 25)) == date(2026, 9, 25)


def test_corte_de_rotulo_invalido_e_none() -> None:
    assert calculations.report_period_cutoff(SEMANA, "qualquer", date(2026, 9, 25)) is None


def test_periodo_em_andamento_na_data_de_referencia() -> None:
    assert calculations.is_partial_period(SEMANA, "2026-S38", date(2026, 9, 16)) is True
    assert calculations.is_partial_period(SEMANA, "2026-S38", date(2026, 9, 25)) is False
    assert calculations.is_partial_period(MES, "2026-09", date(2026, 9, 25)) is True


def test_mes_de_competencia_do_custo_no_semanal_e_o_ultimo_fechado() -> None:
    assert calculations.competence_month(SEMANA, "2026-S38") == date(2026, 8, 1)
    assert calculations.competence_month(MES, "2026-08") == date(2026, 8, 1)


# ── Barras do avanço por período ───────────────────────────────────────────


def _acumulado(labels: list[str], passo: int = 10) -> tuple[tuple[str, Decimal, Decimal], ...]:
    return tuple((label, D(i * passo), D(i * (passo - 1))) for i, label in enumerate(labels))


def test_bar_periods_do_semanal_sao_as_ultimas_oito_semanas() -> None:
    periods = calculations.bar_periods(
        SEMANA, "2026-S38", reference_date=date(2026, 9, 25), project_start=date(2026, 1, 5)
    )

    assert periods == tuple(f"2026-S{n:02d}" for n in range(31, 39))


def test_bar_periods_do_mensal_sao_os_ultimos_seis_meses() -> None:
    periods = calculations.bar_periods(
        MES, "2026-08", reference_date=date(2026, 9, 25), project_start=date(2026, 1, 5)
    )

    assert periods == ("2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08")


def test_bar_periods_nao_tem_periodo_antes_do_inicio_do_projeto() -> None:
    periods = calculations.bar_periods(
        SEMANA, "2026-S38", reference_date=date(2026, 9, 25), project_start=date(2026, 8, 10)
    )

    assert periods == ("2026-S33", "2026-S34", "2026-S35", "2026-S36", "2026-S37", "2026-S38")


def test_bar_periods_de_rotulo_invalido_e_vazio() -> None:
    assert (
        calculations.bar_periods(
            SEMANA, "qualquer", reference_date=date(2026, 9, 25), project_start=None
        )
        == ()
    )


def test_barras_sao_o_incremento_entre_os_pontos() -> None:
    labels = [f"2026-S{n:02d}" for n in range(30, 39)]

    bars = calculations.period_bars(SEMANA, tuple(labels[1:]), _acumulado(labels))

    assert bars[0].period == "2026-S31"
    assert bars[-1].period == "2026-S38"
    assert bars[-1].predicted == D("10.0")
    assert bars[-1].actual == D("9.0")
    assert bars[-1].label == "S38"


def test_barra_do_primeiro_periodo_do_projeto_vale_contra_zero() -> None:
    bars = calculations.period_bars(SEMANA, ("2026-S33",), (("2026-S33", D("12.0"), D("10.0")),))

    assert bars[0].predicted == D("12.0")
    assert bars[0].actual == D("10.0")


def test_barra_sem_real_fica_sem_real() -> None:
    bars = calculations.period_bars(
        SEMANA,
        ("2026-S38",),
        (("2026-S37", D("54.0"), D("50.3")), ("2026-S38", D("65.7"), None)),
    )

    assert bars[0].predicted == D("11.7")
    assert bars[0].actual is None


# ── Leitura da curva do dono num dia (a posição do corte semanal) ──────────


def _semanas(*items: tuple[int, float | None, float | None]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "ano": 2026,
            "semana": week,
            "valores": {"linha_base": base, "realizado": realized},
        }
        for week, base, realized in items
    )


def test_chart_reading_usa_a_semana_do_dia() -> None:
    periods = _semanas((36, 54.0, 50.3), (37, 58.8, 61.8), (38, 61.7, 61.8), (39, 65.7, None))

    leitura = calculations.chart_reading(periods, day=date(2026, 9, 20))

    assert leitura.predicted == D("61.7")
    assert leitura.actual == D("61.8")
    assert leitura.deviation_pp == D("0.1")
    assert leitura.spi == D("1.00")


def test_chart_reading_interpola_o_previsto_e_mede_o_real() -> None:
    """O previsto da semana sai da interpolação do dono; o real é o medido, nunca interpolado."""
    periods = _semanas((37, 58.8, 61.8), (38, 61.7, 61.8))

    antes = calculations.chart_reading(periods, day=date(2026, 9, 13))

    assert (antes.predicted, antes.actual, antes.spi) == (D("58.8"), D("61.8"), D("1.05"))


def test_chart_reading_antes_da_primeira_semana_vale_zero() -> None:
    periods = _semanas((38, 61.7, 61.8))

    leitura = calculations.chart_reading(periods, day=date(2026, 1, 5))

    assert leitura.predicted == D("0.0")
    assert leitura.actual is None
    assert leitura.spi is None


def test_chart_reading_depois_da_ultima_semana_vale_o_ultimo_ponto() -> None:
    periods = _semanas((38, 61.7, 61.8))

    leitura = calculations.chart_reading(periods, day=date(2027, 3, 1))

    assert (leitura.predicted, leitura.actual) == (D("61.7"), D("61.8"))


def test_chart_reading_sem_real_fica_sem_indice() -> None:
    periods = _semanas((38, 61.7, None))

    leitura = calculations.chart_reading(periods, day=date(2026, 9, 20))

    assert leitura.predicted == D("61.7")
    assert leitura.actual is None
    assert leitura.deviation_pp is None
    assert leitura.spi is None
