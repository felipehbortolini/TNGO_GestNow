"""Cálculos da Curva S física (ISSUE-039): baseline, real, tendência e carteira.

O previsto do mês vem da distribuição linear da LB (o mês da referência usa a
própria referência, não o fim do mês); o real vem da última medição até a data do
mês e fica vazio depois do corte; a tendência arranca no real do corte e segue a
linha de base, com teto de 100; a carteira é a média ponderada pelos pesos,
renormalizada, no calendário da união dos meses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from src.modulos.planejamento.calculations import (
    CurvaFisicaCalendar,
    CurvaFisicaMeasurement,
    CurvaFisicaPackage,
    CurvaFisicaSeries,
    curva_fisica_baseline,
    curva_fisica_months,
    curva_fisica_portfolio,
    curva_fisica_real,
    curva_fisica_trend,
)

D = Decimal

JAN = date(2026, 1, 1)
FEB = date(2026, 2, 1)
MAR = date(2026, 3, 1)
APR = date(2026, 4, 1)


def pacote(
    peso: str,
    inicio: date | None = None,
    termino: date | None = None,
    medicoes: Sequence[CurvaFisicaMeasurement] = (),
) -> CurvaFisicaPackage:
    return CurvaFisicaPackage(
        weight=D(peso), start=inicio, finish=termino, measurements=tuple(medicoes)
    )


def medicao(dia: date, para: str) -> CurvaFisicaMeasurement:
    return CurvaFisicaMeasurement(measured_on=dia, to_pct=D(para))


def serie(
    meses: Sequence[date],
    baseline: Sequence[Decimal | str | int | None],
    real: Sequence[Decimal | str | int | None],
    tendencia: Sequence[Decimal | str | int | None],
    corte: int,
) -> CurvaFisicaSeries:
    def valores(itens: Sequence[Decimal | str | int | None]) -> tuple[Decimal | None, ...]:
        return tuple(None if item is None else D(str(item)) for item in itens)

    return CurvaFisicaSeries(
        months=tuple(meses),
        cut_index=corte,
        baseline=valores(baseline),
        real=valores(real),
        trend=valores(tendencia),
    )


def test_meses_vao_do_primeiro_inicio_ao_ultimo_termino() -> None:
    packages = (
        pacote("30", date(2026, 1, 20), date(2026, 2, 10)),
        pacote("70", date(2026, 2, 5), date(2026, 4, 2)),
    )

    calendar = curva_fisica_months(packages, date(2026, 2, 15))

    assert calendar.months == (JAN, FEB, MAR, APR)
    assert calendar.cut_index == 1


def test_meses_ignoram_pacote_sem_peso_e_pacote_sem_datas() -> None:
    packages = (
        pacote("0", date(2025, 1, 1), date(2025, 2, 1)),
        pacote("50", None, date(2026, 5, 1)),
        pacote("50", date(2026, 3, 10), date(2026, 4, 20)),
    )

    calendar = curva_fisica_months(packages, date(2026, 4, 1))

    assert calendar.months == (MAR, APR)
    assert calendar.cut_index == 1


def test_meses_sem_pacote_com_peso_ficam_vazios() -> None:
    packages = (pacote("0", date(2026, 1, 1), date(2026, 2, 1)),)

    assert curva_fisica_months(packages, date(2026, 2, 1)) == CurvaFisicaCalendar(
        months=(), cut_index=-1
    )
    assert curva_fisica_months((), date(2026, 2, 1)) == CurvaFisicaCalendar(months=(), cut_index=-1)


def test_corte_apos_o_termino_e_o_ultimo_mes() -> None:
    packages = (pacote("100", date(2026, 1, 10), date(2026, 2, 20)),)

    calendar = curva_fisica_months(packages, date(2026, 6, 1))

    assert calendar.months == (JAN, FEB)
    assert calendar.cut_index == 1


def test_corte_antes_do_inicio_nao_existe() -> None:
    packages = (pacote("100", date(2026, 3, 10), date(2026, 5, 20)),)

    calendar = curva_fisica_months(packages, date(2026, 1, 5))

    assert calendar.months == (MAR, APR, date(2026, 5, 1))
    assert calendar.cut_index == -1


def test_previsto_do_mes_da_referencia_usa_a_referencia() -> None:
    packages = (pacote("100", date(2026, 1, 1), date(2026, 1, 11)),)

    baseline = curva_fisica_baseline(packages, (JAN,), date(2026, 1, 6))

    assert baseline == (D("50.0"),)


def test_previsto_dos_outros_meses_usa_o_ultimo_dia() -> None:
    packages = (pacote("100", date(2026, 1, 1), date(2026, 3, 1)),)

    baseline = curva_fisica_baseline(packages, (JAN, FEB), date(2026, 2, 10))

    assert baseline == (D("50.8"), D("67.8"))


def test_previsto_do_mes_pondera_pelo_peso() -> None:
    packages = (
        pacote("60", date(2026, 1, 1), date(2026, 1, 11)),
        pacote("40", date(2026, 1, 5), date(2026, 1, 15)),
    )

    baseline = curva_fisica_baseline(packages, (JAN,), date(2026, 1, 6))

    assert baseline == (D("34.0"),)


def test_previsto_antes_do_inicio_e_zero_e_apos_o_termino_e_cem() -> None:
    packages = (pacote("100", date(2026, 2, 1), date(2026, 2, 11)),)

    baseline = curva_fisica_baseline(packages, (JAN, FEB, MAR), date(2026, 2, 6))

    assert baseline == (D("0.0"), D("50.0"), D("100.0"))


def test_real_usa_a_ultima_medicao_ate_o_fim_do_periodo() -> None:
    packages = (
        pacote(
            "100",
            date(2026, 1, 1),
            date(2026, 4, 1),
            (medicao(date(2026, 1, 20), "10"), medicao(date(2026, 2, 5), "40")),
        ),
    )

    real = curva_fisica_real(packages, (JAN, FEB, MAR), date(2026, 2, 10))

    assert real == (D("10.0"), D("40.0"), None)


def test_medicao_nova_muda_o_periodo_seguinte_e_nao_o_passado() -> None:
    antigas = pacote("100", date(2026, 1, 1), date(2026, 4, 1), (medicao(date(2026, 1, 20), "10"),))
    novas = pacote(
        "100",
        date(2026, 1, 1),
        date(2026, 4, 1),
        (medicao(date(2026, 1, 20), "10"), medicao(date(2026, 2, 5), "40")),
    )

    anterior = curva_fisica_real((antigas,), (JAN, FEB), date(2026, 2, 10))
    atual = curva_fisica_real((novas,), (JAN, FEB), date(2026, 2, 10))

    assert anterior == (D("10.0"), D("10.0"))
    assert atual == (D("10.0"), D("40.0"))


def test_medicao_depois_da_data_do_periodo_nao_conta() -> None:
    packages = (
        pacote(
            "100",
            date(2026, 1, 1),
            date(2026, 4, 1),
            (medicao(date(2026, 2, 20), "90"),),
        ),
    )

    real = curva_fisica_real(packages, (JAN,), date(2026, 2, 10))

    assert real == (D("0.0"),)


def test_real_conta_medicao_exatamente_na_data_do_periodo() -> None:
    packages = (
        pacote(
            "100",
            date(2026, 1, 1),
            date(2026, 3, 1),
            (medicao(date(2026, 1, 31), "25"),),
        ),
    )

    real = curva_fisica_real(packages, (JAN,), date(2026, 2, 10))

    assert real == (D("25.0"),)


def test_pacote_sem_medicao_tem_real_zero() -> None:
    packages = (pacote("100", date(2026, 1, 1), date(2026, 3, 1)),)

    assert curva_fisica_real(packages, (JAN,), date(2026, 2, 10)) == (D("0.0"),)


def test_real_pondera_pelo_peso() -> None:
    packages = (
        pacote("60", date(2026, 1, 1), date(2026, 3, 1), (medicao(date(2026, 1, 10), "50"),)),
        pacote("40", date(2026, 1, 1), date(2026, 3, 1)),
    )

    real = curva_fisica_real(packages, (JAN,), date(2026, 1, 31))

    assert real == (D("30.0"),)


def test_tendencia_arranca_no_real_do_corte_e_segue_a_base() -> None:
    baseline = (D("10.0"), D("30.0"), D("60.0"), D("90.0"))
    real = (D("5.0"), D("20.0"), None, None)

    trend = curva_fisica_trend(baseline, real, 1)

    assert trend == (None, D("20.0"), D("50.0"), D("80.0"))


def test_tendencia_no_primeiro_e_no_ultimo_mes() -> None:
    baseline = (D("10.0"), D("50.0"))
    real = (D("8.0"), None)

    assert curva_fisica_trend(baseline, real, 0) == (D("8.0"), D("48.0"))
    assert curva_fisica_trend(baseline, (D("8.0"), D("40.0")), 1) == (None, D("40.0"))


def test_tendencia_tem_teto_de_cem() -> None:
    baseline = (D("10.0"), D("30.0"), D("80.0"))
    real = (D("5.0"), D("70.0"), None)

    assert curva_fisica_trend(baseline, real, 1) == (None, D("70.0"), D("100.0"))


def test_tendencia_sem_corte_ou_sem_real_no_corte_nao_existe() -> None:
    baseline = (D("10.0"), D("30.0"))

    assert curva_fisica_trend(baseline, (None, None), -1) == (None, None)
    assert curva_fisica_trend(baseline, (None, None), 0) == (None, None)


def test_carteira_une_os_calendarios_e_pondera_os_projetos() -> None:
    series = {
        1: serie((JAN,), (50,), (40,), (40,), 0),
        2: serie((JAN, FEB), (20, 60), (10, 20), (None, 20), 1),
        3: serie((FEB, MAR), (30, 90), (15, None), (15, 75), 0),
    }

    portfolio = curva_fisica_portfolio(series, {1: D("3"), 2: D("5"), 3: D("2")}, (JAN, FEB, MAR))

    assert portfolio.months == (JAN, FEB, MAR)
    assert portfolio.cut_index == 1
    assert portfolio.baseline == (D("25.0"), D("66.0"), D("98.0"))
    assert portfolio.real == (D("17.0"), D("25.0"), None)
    assert portfolio.trend == (None, D("43.0"), D("95.0"))


def test_carteira_antes_do_inicio_e_zero_e_apos_o_termino_fecha() -> None:
    series = {
        1: serie((JAN,), (50,), (40,), (40,), 0),
        2: serie((JAN, FEB), (20, 60), (10, 20), (None, 20), 1),
    }

    portfolio = curva_fisica_portfolio(series, {1: D("50"), 2: D("50")}, (JAN, FEB))

    assert portfolio.baseline == (D("35.0"), D("80.0"))
    assert portfolio.real == (D("25.0"), D("30.0"))
    assert portfolio.trend == (None, D("60.0"))


def test_carteira_sem_projetos_fica_vazia() -> None:
    portfolio = curva_fisica_portfolio({}, {}, ())

    assert portfolio == CurvaFisicaSeries(months=(), cut_index=-1, baseline=(), real=(), trend=())
