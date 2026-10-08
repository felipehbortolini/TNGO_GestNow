"""As fórmulas do plano de compras (ISSUE-058): etapa, folga, ordem, derivação e código.

Cada fórmula recebe as datas como argumento e tem o caso de fronteira: o dia da igualdade, o
sinal da folga, o plano que nasce negativo e o código a partir do 100º pacote.
"""

from __future__ import annotations

from datetime import date

from src.modulos.suprimentos import calculations


def test_a_etapa_e_a_do_ultimo_marco_com_data_real() -> None:
    assert calculations.package_stage({}) == "Planejado"
    assert calculations.package_stage({"requisicao": date(2026, 8, 1), "rfx": None}) == "Requisição"
    assert (
        calculations.package_stage(
            {
                "requisicao": date(2026, 8, 1),
                "adjudicacao": date(2026, 9, 20),
                "pedido": None,
            }
        )
        == "Aprovada"
    )
    assert (
        calculations.package_stage({"requisicao": date(2026, 8, 1), "pedido": date(2026, 9, 22)})
        == "Pedido/contrato emitido"
    )


def test_a_lb_congela_com_a_requisicao_real() -> None:
    assert calculations.lb_frozen(None) is False
    assert calculations.lb_frozen(date(2026, 8, 1)) is True


def test_as_datas_do_plano_crescem_e_a_igualdade_vale() -> None:
    ordered = {
        "requisicao": date(2026, 8, 1),
        "rfx": date(2026, 8, 10),
        "adjudicacao": date(2026, 9, 20),
        "pedido": date(2026, 9, 22),
    }
    assert calculations.plan_dates_in_order(ordered) is True
    assert calculations.plan_dates_in_order({**ordered, "rfx": date(2026, 9, 21)}) is False
    assert calculations.plan_dates_in_order({**ordered, "pedido": None}) is False


def test_a_folga_planejada_e_o_ros_menos_o_pedido() -> None:
    pedido = date(2026, 11, 25)
    assert calculations.planned_slack_days(date(2026, 12, 2), pedido) == 7
    assert calculations.planned_slack_days(pedido, pedido) == 0
    assert calculations.planned_slack_days(date(2026, 11, 20), pedido) == -5
    assert calculations.planned_slack_days(None, pedido) is None
    assert calculations.planned_slack_days(date(2027, 1, 1), None) is None


def test_a_faixa_da_folga_nas_fronteiras() -> None:
    assert calculations.slack_band(None) == calculations.SLACK_OK
    assert calculations.slack_band(-1) == calculations.SLACK_CRITICAL
    assert calculations.slack_band(0) == calculations.SLACK_WARNING
    assert calculations.slack_band(7) == calculations.SLACK_WARNING
    assert calculations.slack_band(8) == calculations.SLACK_OK


def test_as_datas_intermediarias_do_plano_seguem_o_prototipo() -> None:
    plan = calculations.derived_plan_dates(
        requisition=date(2025, 11, 10),
        rfx=date(2025, 11, 20),
        adjudication=date(2026, 1, 5),
        order=date(2026, 1, 8),
    )
    assert plan == {
        "requisicao": date(2025, 11, 10),
        "rfx": date(2025, 11, 20),
        "propostas": date(2025, 12, 11),
        "eqTecnica": date(2025, 12, 20),
        "eqComercial": date(2025, 12, 29),
        "adjudicacao": date(2026, 1, 5),
        "pedido": date(2026, 1, 8),
    }


def test_as_datas_intermediarias_encurtam_quando_a_janela_e_curta() -> None:
    plan = calculations.derived_plan_dates(
        requisition=date(2026, 1, 1),
        rfx=date(2026, 1, 1),
        adjudication=date(2026, 1, 10),
        order=date(2026, 1, 12),
    )
    assert plan["propostas"] == date(2026, 1, 5)
    assert plan["eqComercial"] == date(2026, 1, 8)
    assert plan["eqTecnica"] == date(2026, 1, 7)


def test_o_desvio_da_adjudicacao_usa_real_previsao_ou_a_referencia() -> None:
    plan = date(2026, 9, 20)
    assert (
        calculations.adjudication_deviation_days(plan, date(2026, 9, 22), None, date(2026, 9, 25))
        == 2
    )
    assert (
        calculations.adjudication_deviation_days(plan, None, date(2026, 9, 30), date(2026, 9, 25))
        == 10
    )
    assert calculations.adjudication_deviation_days(plan, None, None, date(2026, 9, 25)) == 5
    assert (
        calculations.adjudication_deviation_days(date(2026, 10, 1), None, None, date(2026, 9, 25))
        is None
    )
    assert (
        calculations.adjudication_deviation_days(plan, date(2026, 9, 18), None, date(2026, 9, 25))
        == -2
    )


def test_a_adjudicacao_atrasada_e_a_que_nao_aconteceu_e_passou_da_lb() -> None:
    plan = date(2026, 9, 20)
    assert calculations.adjudication_overdue(plan, None, None, date(2026, 9, 25)) is True
    assert (
        calculations.adjudication_overdue(plan, None, date(2026, 9, 30), date(2026, 9, 25)) is True
    )
    assert calculations.adjudication_overdue(plan, None, None, date(2026, 9, 19)) is False
    assert (
        calculations.adjudication_overdue(plan, date(2026, 9, 22), None, date(2026, 9, 25)) is False
    )


def test_o_proximo_codigo_segue_o_prefixo_do_ultimo_e_o_maior_numero() -> None:
    assert calculations.next_package_code([]) == "PC-01"
    assert calculations.next_package_code(["PC-01", "PC-02"]) == "PC-03"
    assert calculations.next_package_code(["CB-PC-01", "CB-PC-09"]) == "CB-PC-10"
    assert calculations.next_package_code(["PC-99"]) == "PC-100"
    assert calculations.next_package_code(["PC-01", "CB-PC-03"]) == "CB-PC-04"
