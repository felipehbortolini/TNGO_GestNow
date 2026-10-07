"""Cálculos puros da EAP (ISSUE-036): o real por critério, as somas ponderadas e a regra dos 100%.

A data de referência entra como argumento (D6). Cada critério de medição tem o seu caso, a
fronteira das faixas -2 e -5 p.p. tem teste e a linha 0 fecha os pesos em 100.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.planejamento.calculations import (
    EapPackage,
    EapStep,
    EapTotals,
    EapWeightedValue,
    eap_deviation_band,
    eap_deviation_pp,
    eap_node_totals,
    eap_package_not_started,
    eap_package_overdue,
    eap_package_progress,
    eap_package_totals,
    eap_root_totals,
    eap_weighted_progress,
)

D = Decimal

HOJE = date(2026, 9, 25)
INICIO = date(2026, 1, 5)
TERMINO = date(2026, 9, 15)
FAIXAS = (D(2), D(5))


def test_etapas_somam_peso_vezes_percentual() -> None:
    progress = eap_package_progress(
        "Etapas",
        etapas=(
            EapStep("Elaboração", D(40), D(100)),
            EapStep("Emissão para comentários", D(30), D(50)),
            EapStep("Emissão para construção", D(30), D(0)),
        ),
    )

    assert progress == D("55.00")


def test_etapas_sem_percentual_contam_zero() -> None:
    assert eap_package_progress("Etapas", etapas=(EapStep("Elaboração", D(40)),)) == D("0.00")


def test_unidades_limitam_o_executado_a_quantidade() -> None:
    assert eap_package_progress("Unidades", quantity=D(1400), executed=D(1260)) == D("90.00")
    assert eap_package_progress("Unidades", quantity=D(1400), executed=D(2800)) == D("100.00")
    assert eap_package_progress("Unidades", quantity=D(0), executed=D(10)) == D("0.00")
    assert eap_package_progress("Unidades", quantity=None, executed=D(10)) == D("0.00")
    assert eap_package_progress("Unidades", quantity=D(10), executed=None) == D("0.00")


def test_marco_zero_cem_e_cem_ou_zero() -> None:
    assert eap_package_progress("Marco 0/100", state="Concluído") == D("100.00")
    assert eap_package_progress("Marco 0/100", state="Não iniciado") == D("0.00")
    assert eap_package_progress("Marco 0/100") == D("0.00")


def test_marco_cinquenta_cinquenta_e_cem_cinquenta_ou_zero() -> None:
    assert eap_package_progress("Marco 50/50", state="Concluído") == D("100.00")
    assert eap_package_progress("Marco 50/50", state="Iniciado") == D("50.00")
    assert eap_package_progress("Marco 50/50", state="Não iniciado") == D("0.00")
    assert eap_package_progress("Marco 50/50", state="Outro") == D("0.00")


def test_percentual_estimado_usa_o_valor_informado() -> None:
    assert eap_package_progress("Percentual estimado", estimated_pct=D("12.5")) == D("12.50")
    assert eap_package_progress("Percentual estimado") == D("0.00")


def test_pacote_de_planejamento_nao_mede_avanco() -> None:
    progress = eap_package_progress(
        None,
        etapas=(EapStep("Elaboração", D(100), D(100)),),
        quantity=D(100),
        executed=D(100),
        state="Concluído",
        estimated_pct=D(100),
    )

    assert progress == D("0.00")
    assert eap_package_progress("Sem critério") == D("0.00")


def test_o_real_fica_entre_zero_e_cem_com_duas_casas() -> None:
    assert eap_package_progress("Etapas", etapas=(EapStep("A", D(150), D(100)),)) == D("100.00")
    assert eap_package_progress("Percentual estimado", estimated_pct=D("-5")) == D("0.00")
    assert eap_package_progress("Unidades", quantity=D(3), executed=D(1)) == D("33.33")


def test_media_ponderada_dos_valores_pelo_peso() -> None:
    values = (
        EapWeightedValue(D(60), D(50)),
        EapWeightedValue(D(40), D(80)),
    )

    assert eap_weighted_progress(values) == D("62.00")
    assert eap_weighted_progress(()) == D("0.00")
    assert eap_weighted_progress((EapWeightedValue(D(0), D(90)),)) == D("0.00")


def test_desvio_em_pontos_percentuais_com_uma_casa() -> None:
    assert eap_deviation_pp(D("90.00"), D("100.00")) == D("-10.0")
    assert eap_deviation_pp(D("65.35"), D("60.00")) == D("5.4")
    assert eap_deviation_pp(D(100), D(100)) == D("0.0")


def test_faixa_do_desvio_nas_fronteiras() -> None:
    assert eap_deviation_band(D("-1.9"), FAIXAS) == "success"
    assert eap_deviation_band(D("-2.0"), FAIXAS) == "success"
    assert eap_deviation_band(D("-2.1"), FAIXAS) == "warning"
    assert eap_deviation_band(D("-5.0"), FAIXAS) == "warning"
    assert eap_deviation_band(D("-5.1"), FAIXAS) == "danger"
    assert eap_deviation_band(D("3.0"), FAIXAS) == "success"
    assert eap_deviation_band(None, FAIXAS) is None


def test_vencido_e_nao_iniciado_com_a_data_injetada() -> None:
    assert eap_package_overdue("Trabalho", date(2026, 9, 24), D(80), HOJE) is True
    assert eap_package_overdue("Trabalho", HOJE, D(80), HOJE) is False
    assert eap_package_overdue("Trabalho", date(2026, 9, 24), D(100), HOJE) is False
    assert eap_package_overdue("Planejamento", date(2026, 9, 24), D(0), HOJE) is False
    assert eap_package_overdue("Trabalho", None, D(0), HOJE) is False

    assert eap_package_not_started("Trabalho", HOJE, D(0), HOJE) is True
    assert eap_package_not_started("Trabalho", date(2026, 9, 26), D(0), HOJE) is False
    assert eap_package_not_started("Trabalho", INICIO, D(1), HOJE) is False
    assert eap_package_not_started("Planejamento", INICIO, D(0), HOJE) is False
    assert eap_package_not_started("Trabalho", None, D(0), HOJE) is False


def test_no_do_pacote_usa_o_real_do_criterio() -> None:
    package = EapPackage(
        kind="Trabalho",
        weight=D("2.00"),
        predicted=D("100.00"),
        start=INICIO,
        finish=TERMINO,
        criterion="Etapas",
        etapas=(EapStep("Entrega na obra", D(100), D(80)),),
    )

    totals = eap_package_totals(package, reference_date=HOJE)

    assert totals.actual == D("80.00")
    assert (totals.packages, totals.planning) == (1, 0)
    assert totals.overdue is True
    assert totals.not_started is False


def test_no_do_pacote_de_planejamento_conta_como_planejamento() -> None:
    package = EapPackage(
        kind="Planejamento",
        weight=D("1.20"),
        predicted=D("0.00"),
        start=date(2027, 2, 15),
        finish=date(2027, 4, 16),
        criterion="Percentual estimado",
        estimated_pct=D(100),
    )

    totals = eap_package_totals(package, reference_date=HOJE)

    assert totals.actual == D("0.00")
    assert (totals.packages, totals.planning) == (0, 1)
    assert totals.overdue is False
    assert totals.not_started is False


def _totals(weight: str, predicted: str = "50.00", actual: str = "50.00") -> EapTotals:
    return EapTotals(
        weight=D(weight), predicted=D(predicted), actual=D(actual), start=None, finish=None
    )


def test_regra_dos_cem_por_cento_e_a_soma_dos_filhos() -> None:
    area_a = eap_node_totals((_totals("30"), _totals("10")))
    area_b = eap_node_totals((_totals("50"), _totals("10")))
    root = eap_root_totals((area_a, area_b))

    assert area_a.weight == D("40.00")
    assert area_b.weight == D("60.00")
    assert root.weight == D("100.00")
    assert root.weight == area_a.weight + area_b.weight


def test_regra_dos_cem_por_cento_arredonda_com_duas_casas() -> None:
    total = eap_node_totals((_totals("33.333"), _totals("33.333"), _totals("33.334")))

    assert total.weight == D("100.00")


def test_linha_zero_pondera_previsto_e_real_pelas_areas() -> None:
    area_a = EapTotals(
        weight=D(75),
        predicted=D(80),
        actual=D(100),
        start=INICIO,
        finish=date(2026, 6, 30),
        packages=3,
        overdue=True,
    )
    area_b = EapTotals(
        weight=D(25),
        predicted=D(40),
        actual=D(50),
        start=date(2026, 3, 1),
        finish=TERMINO,
        packages=2,
        planning=1,
        not_started=True,
    )

    root = eap_root_totals((area_a, area_b))

    assert root.predicted == D("70.00")
    assert root.actual == D("87.50")
    assert root.start == INICIO
    assert root.finish == TERMINO
    assert (root.packages, root.planning) == (5, 1)
    assert root.overdue is True
    assert root.not_started is True
    assert eap_deviation_pp(root.actual, root.predicted) == D("17.5")
    assert eap_deviation_band(eap_deviation_pp(root.actual, root.predicted), FAIXAS) == "success"


def test_no_sem_filhos_fica_zerado() -> None:
    empty = eap_node_totals(())

    assert empty.weight == D(0)
    assert empty.predicted == D(0)
    assert empty.actual == D(0)
    assert empty.start is None
    assert empty.finish is None
    assert (empty.packages, empty.planning) == (0, 0)
    assert empty.overdue is False
    assert empty.not_started is False
