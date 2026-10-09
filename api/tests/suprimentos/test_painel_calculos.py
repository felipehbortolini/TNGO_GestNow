"""Os cálculos do painel de suprimentos (ISSUE-063): uma fórmula por teste, sem banco.

As funções que os indicadores e as curvas usam vivem em ``calculations``; aqui cada uma é lida
com números redondos para a regra de negócio ficar explícita (arredondamento meio para cima,
denominador zerado sem indicador e o corte das curvas na data de referência).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.suprimentos import calculations

MILESTONE = calculations.ProgressCurveMilestone


# ── Os nove indicadores ──────────────────────────────────────────────────────────────────────


def test_aderencia_ao_plano_de_compras() -> None:
    assert calculations.purchase_plan_adherence(13, 14) == Decimal("92.9")
    assert calculations.purchase_plan_adherence(14, 14) == Decimal("100.0")
    assert calculations.purchase_plan_adherence(0, 5) == Decimal("0.0")
    assert calculations.purchase_plan_adherence(2, 0) is None, "sem planejados não há aderência"


def test_ciclo_medio_de_compra() -> None:
    assert calculations.average_cycle_days([10, 11]) == 11, "10,5 arredonda meio para cima"
    assert calculations.average_cycle_days([45]) == 45
    assert calculations.average_cycle_days([]) is None


def test_saving_sobre_a_estimativa() -> None:
    assert calculations.saving_pct(4115, 3900) == Decimal("5.2")
    assert calculations.saving_pct(1000, 1000) == Decimal("0.0")
    assert calculations.saving_pct(1000, 1100) == Decimal("-10.0")
    assert calculations.saving_pct(0, 0) is None, "sem base não há saving"


def test_saving_de_negociacao() -> None:
    assert calculations.saving_pct(40912, 39000) == Decimal("4.7")
    assert calculations.saving_pct(3200, 3000) == Decimal("6.3"), "6,25 arredonda meio para cima"


def test_competitividade_media_de_propostas() -> None:
    ofertas = [4, 5, 3, 3, 4, 3, 3, 5, 3, 4, 4, 3, 4, 4]
    assert calculations.average_offers(ofertas) == Decimal("3.7")
    assert calculations.average_offers([]) is None


def test_competitividade_fornecedor_unico() -> None:
    assert calculations.single_supplier_share([True, False, False, False]) == Decimal("25.0")
    assert calculations.single_supplier_share([True, False]) == Decimal("50.0")
    assert calculations.single_supplier_share([]) is None


def test_compras_emergenciais() -> None:
    assert calculations.emergency_share(1, 4) == Decimal("25.0")
    assert calculations.emergency_share(0, 0) is None, "sem contratado não há percentual"


def test_comprometido_x_orcado() -> None:
    assert calculations.committed_over_budget(105, 100) == Decimal("105.0")
    assert calculations.committed_over_budget(90, 100) == Decimal("90.0")
    assert calculations.committed_over_budget(10, 0) is None, "sem orçado não há percentual"


# ── As curvas ────────────────────────────────────────────────────────────────────────────────


def test_fim_do_mes() -> None:
    assert calculations.month_end(date(2026, 1, 10)) == date(2026, 1, 31)
    assert calculations.month_end(date(2026, 2, 1)) == date(2026, 2, 28)
    assert calculations.month_end(date(2026, 12, 5)) == date(2026, 12, 31)
    assert calculations.month_end(date(2028, 2, 1)) == date(2028, 2, 29), "ano bissexto"


def test_curva_de_contratacao() -> None:
    curva = calculations.contracting_curve(
        [date(2026, 1, 5), date(2026, 2, 15), date(2026, 3, 10)],
        [date(2026, 1, 8), date(2026, 2, 20), date(2026, 8, 1)],
        reference_date=date(2026, 3, 25),
    )

    assert curva.months[0] == date(2026, 1, 1)
    assert curva.months[-1] == date(2026, 8, 1), "os meses vão até a última data ou a referência"
    assert len(curva.months) == 8
    assert curva.planned == (1, 2, 3, 3, 3, 3, 3, 3), "o plano acumula e segue para a direita"
    assert curva.realized == (1, 2, 2, None, None, None, None, None), (
        "o real para no mês do corte (a adjudicação de agosto não aparece)"
    )
    assert curva.cut_month == date(2026, 3, 1)


def test_curva_de_contratacao_sem_datas() -> None:
    curva = calculations.contracting_curve([], [], reference_date=date(2026, 9, 25))

    assert curva.months == ()
    assert curva.planned == ()
    assert curva.realized == ()


def test_curva_de_saving() -> None:
    curva = calculations.saving_curve(
        [(date(2026, 1, 8), 100, 20), (date(2026, 2, 20), 50, None), (date(2026, 4, 1), 10, 5)],
        reference_date=date(2026, 3, 25),
    )

    assert len(curva.months) == 4
    assert curva.estimated == (100, 150, 150, None), "acumula até o corte e para"
    assert curva.negotiation == (20, 20, 20, None), "o pacote sem primeira proposta não soma"
    assert curva.cut_month == date(2026, 3, 1)


def test_curva_de_avanco_do_mas() -> None:
    pacote = (
        (
            MILESTONE(
                weight=50,
                applicable=True,
                baseline=date(2026, 1, 10),
                forecast=None,
                real=date(2026, 1, 15),
            ),
            MILESTONE(
                weight=50,
                applicable=True,
                baseline=date(2026, 2, 10),
                forecast=date(2026, 3, 10),
                real=None,
            ),
        ),
        100,
    )

    curva = calculations.procurement_curve([pacote], reference_date=date(2026, 2, 20))

    assert curva is not None
    assert len(curva.months) == 3
    assert curva.baseline == (Decimal("50.0"), Decimal("100.0"), Decimal("100.0"))
    assert curva.real == (Decimal("50.0"), Decimal("50.0"), None), "o real para no corte"
    assert curva.trend == (None, Decimal("50.0"), Decimal("100.0")), (
        "a tendência segue o real, a previsão ou a LB"
    )
    assert curva.cut_month == date(2026, 2, 1)


def test_curva_de_avanco_renormaliza_os_marcos_nao_aplicaveis() -> None:
    pacote = (
        (
            MILESTONE(
                weight=60,
                applicable=False,
                baseline=date(2026, 1, 1),
                forecast=None,
                real=None,
            ),
            MILESTONE(
                weight=40,
                applicable=True,
                baseline=date(2026, 1, 10),
                forecast=None,
                real=date(2026, 1, 20),
            ),
        ),
        10,
    )

    curva = calculations.procurement_curve([pacote], reference_date=date(2026, 1, 25))

    assert curva is not None
    assert curva.baseline == (Decimal("100.0"),), "o peso não aplicável fica fora do total"
    assert curva.real == (Decimal("100.0"),)


def test_curva_de_avanco_sem_datas_ou_sem_valor() -> None:
    sem_datas = (MILESTONE(weight=10, applicable=True, baseline=None, forecast=None, real=None),)
    com_datas = (
        MILESTONE(
            weight=10,
            applicable=True,
            baseline=date(2026, 1, 1),
            forecast=None,
            real=None,
        ),
    )

    assert (
        calculations.procurement_curve([(sem_datas, 100)], reference_date=date(2026, 1, 25)) is None
    )
    assert (
        calculations.procurement_curve([(com_datas, 0)], reference_date=date(2026, 1, 25)) is None
    )
