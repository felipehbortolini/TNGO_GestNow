"""As fronteiras do diligenciamento (ISSUE-061): a situação do marco, a folga, o atraso e o OTD.

Funções puras, sem banco: a situação de um marco contra a data de referência (prazo, atraso,
vencido, previsto em atraso, a vencer e sem data), a folga do pedido contra o ROS (a mesma
fórmula do ``delivery_slack_days`` da emissão), o atraso contratual, a situação do pedido e o OTD
de um conjunto de entregas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.suprimentos import calculations

REFERENCIA = date(2026, 9, 25)


def test_o_marco_realizado_le_o_desvio_contra_a_lb() -> None:
    no_prazo = calculations.milestone_situation(
        baseline=date(2026, 9, 10),
        forecast=None,
        real=date(2026, 9, 8),
        reference_date=REFERENCIA,
    )
    assert no_prazo.situation == calculations.MILESTONE_ON_TIME
    assert no_prazo.deviation_days == -2
    assert no_prazo.days_overdue == 0

    atrasado = calculations.milestone_situation(
        baseline=date(2026, 9, 10),
        forecast=None,
        real=date(2026, 9, 25),
        reference_date=REFERENCIA,
    )
    assert atrasado.situation == calculations.MILESTONE_LATE
    assert atrasado.deviation_days == 15


def test_o_marco_sem_lb_realizado_nao_tem_desvio() -> None:
    leitura = calculations.milestone_situation(
        baseline=None, forecast=None, real=date(2026, 9, 20), reference_date=REFERENCIA
    )
    assert leitura.situation == calculations.MILESTONE_ON_TIME
    assert leitura.deviation_days == 0


def test_o_marco_pendente_com_previsao_futura_le_a_lb() -> None:
    a_vencer = calculations.milestone_situation(
        baseline=date(2026, 10, 10),
        forecast=date(2026, 10, 5),
        real=None,
        reference_date=REFERENCIA,
    )
    assert a_vencer.situation == calculations.MILESTONE_DUE_SOON
    assert a_vencer.deviation_days == -5

    atrasado = calculations.milestone_situation(
        baseline=date(2026, 10, 10),
        forecast=date(2026, 10, 20),
        real=None,
        reference_date=REFERENCIA,
    )
    assert atrasado.situation == calculations.MILESTONE_FORECAST_LATE
    assert atrasado.deviation_days == 10


def test_o_marco_vencido_conta_os_dias_desde_a_previsao() -> None:
    vencido = calculations.milestone_situation(
        baseline=date(2026, 9, 1),
        forecast=date(2026, 9, 20),
        real=None,
        reference_date=REFERENCIA,
    )
    assert vencido.situation == calculations.MILESTONE_OVERDUE
    assert vencido.deviation_days == 19
    assert vencido.days_overdue == 5

    so_lb = calculations.milestone_situation(
        baseline=date(2026, 9, 15),
        forecast=None,
        real=None,
        reference_date=REFERENCIA,
    )
    assert so_lb.situation == calculations.MILESTONE_OVERDUE
    assert so_lb.days_overdue == 10


def test_o_marco_sem_lb_nem_previsao_fica_sem_data() -> None:
    leitura = calculations.milestone_situation(
        baseline=None, forecast=None, real=None, reference_date=REFERENCIA
    )
    assert leitura.situation == calculations.MILESTONE_WITHOUT_DATE
    assert leitura.deviation_days is None


def test_a_folga_do_ros_e_a_mesma_da_emissao() -> None:
    assert calculations.required_on_site_slack(date(2026, 11, 15), date(2026, 10, 30)) == 16
    assert calculations.required_on_site_slack(date(2026, 10, 25), date(2026, 10, 30)) == -5
    assert calculations.required_on_site_slack(None, date(2026, 10, 30)) is None
    assert calculations.required_on_site_slack(date(2026, 10, 25), None) is None
    assert calculations.required_on_site_slack(
        date(2026, 11, 15), date(2026, 10, 30)
    ) == calculations.delivery_slack_days(date(2026, 11, 15), date(2026, 10, 30))


def test_o_atraso_contratual_e_positivo_depois_da_data() -> None:
    assert calculations.contractual_delay_days(date(2026, 10, 30), date(2026, 11, 5)) == 6
    assert calculations.contractual_delay_days(date(2026, 10, 30), date(2026, 10, 30)) == 0
    assert calculations.contractual_delay_days(date(2026, 10, 30), None) is None


def test_a_situacao_do_pedido_le_a_faixa_e_os_marcos_vencidos() -> None:
    assert (
        calculations.order_situation(
            delivered=True, band=calculations.SLACK_CRITICAL, has_overdue=True
        )
        == calculations.ORDER_DELIVERED
    )
    assert (
        calculations.order_situation(
            delivered=False, band=calculations.SLACK_CRITICAL, has_overdue=False
        )
        == calculations.ORDER_CRITICAL
    )
    assert (
        calculations.order_situation(
            delivered=False, band=calculations.SLACK_WARNING, has_overdue=False
        )
        == calculations.ORDER_WARNING
    )
    assert (
        calculations.order_situation(delivered=False, band=calculations.SLACK_OK, has_overdue=True)
        == calculations.ORDER_WARNING
    )
    assert (
        calculations.order_situation(delivered=False, band=calculations.SLACK_OK, has_overdue=False)
        == calculations.ORDER_ON_TIME
    )


def test_o_otd_divide_as_entregas_no_prazo_pelas_entregues() -> None:
    assert calculations.on_time_delivery(
        [
            (date(2026, 8, 28), date(2026, 8, 30)),
            (date(2026, 9, 10), date(2026, 9, 5)),
            (date(2026, 9, 1), date(2026, 9, 1)),
        ]
    ) == Decimal("66.7")
    assert calculations.on_time_delivery([]) is None
    assert calculations.on_time_delivery([(None, date(2026, 9, 1))]) is None
    assert calculations.on_time_delivery(
        [(date(2026, 9, 1), date(2026, 9, 1)), (date(2026, 8, 1), date(2026, 9, 1))]
    ) == Decimal("100.0")
    assert calculations.on_time_delivery([(date(2026, 9, 2), None)]) == Decimal("100.0")
