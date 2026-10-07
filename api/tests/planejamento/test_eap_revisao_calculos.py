"""Cálculos da revisão da EAP (ISSUE-038): o maior resto e o previsto linear.

O maior resto fecha o alvo em centésimos mesmo na fronteira, com o empate resolvido pela
ordem de entrada e a soma zero virando zeros; o previsto linear usa as datas da linha de
base e a referência que entra como argumento (D6).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.planejamento.calculations import eap_linear_predicted, eap_rescale_weights

D = Decimal

INICIO = date(2026, 1, 5)
TERMINO = date(2026, 1, 15)


def test_maior_resto_fecha_o_alvo_em_centesimos() -> None:
    pesos = (("a", D("40")), ("b", D("30")), ("c", D("30")))

    resultado = eap_rescale_weights(pesos, D("99.99"))

    assert resultado == {"a": D("39.99"), "b": D("30.00"), "c": D("30.00")}
    assert sum(resultado.values()) == D("99.99")


def test_tres_pesos_iguais_arredondam_para_o_alvo() -> None:
    resultado = eap_rescale_weights((("a", D(1)), ("b", D(1)), ("c", D(1))), D("99.99"))

    assert resultado == {"a": D("33.33"), "b": D("33.33"), "c": D("33.33")}
    assert sum(resultado.values()) == D("99.99")


def test_pesos_que_ja_somam_o_alvo_ficam_iguais() -> None:
    pesos = (("a", D("60")), ("b", D("40")))
    assert eap_rescale_weights(pesos, D(100)) == dict(pesos)

    centesimos = (("a", D("33.33")), ("b", D("33.33")), ("c", D("33.34")))
    assert eap_rescale_weights(centesimos, D(100)) == dict(centesimos)


def test_empate_no_maior_resto_segue_a_ordem_de_entrada() -> None:
    resultado = eap_rescale_weights((("a", D(1)), ("b", D(1)), ("c", D(1))), D(100))

    assert resultado == {"a": D("33.34"), "b": D("33.33"), "c": D("33.33")}
    assert sum(resultado.values()) == D(100)


def test_soma_zero_devolve_todos_zerados() -> None:
    assert eap_rescale_weights((("a", D(0)), ("b", D(0))), D(100)) == {"a": D(0), "b": D(0)}
    assert eap_rescale_weights((), D(100)) == {}


def test_pesos_saem_com_duas_casas() -> None:
    resultado = eap_rescale_weights((("a", D(1)), ("b", D(2)), ("c", D(3))), D(100))

    assert resultado == {"a": D("16.67"), "b": D("33.33"), "c": D("50.00")}
    assert all(valor.as_tuple().exponent == -2 for valor in resultado.values())


def test_previsto_linear_sem_datas_e_zero() -> None:
    assert eap_linear_predicted(None, TERMINO, INICIO) == D(0)
    assert eap_linear_predicted(INICIO, None, INICIO) == D(0)
    assert eap_linear_predicted(None, None, INICIO) == D(0)


def test_previsto_linear_ate_o_inicio_e_zero() -> None:
    assert eap_linear_predicted(INICIO, TERMINO, date(2026, 1, 4)) == D(0)
    assert eap_linear_predicted(INICIO, TERMINO, INICIO) == D(0)


def test_previsto_linear_do_termino_em_diante_e_cem() -> None:
    assert eap_linear_predicted(INICIO, TERMINO, TERMINO) == D(100)
    assert eap_linear_predicted(INICIO, TERMINO, date(2026, 2, 1)) == D(100)


def test_previsto_linear_no_meio_tem_uma_casa() -> None:
    assert eap_linear_predicted(INICIO, TERMINO, date(2026, 1, 8)) == D("30.0")

    assert eap_linear_predicted(date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 4)) == D("42.9")
