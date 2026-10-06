"""Importação (ISSUE-018): a conversão de cada célula da planilha para o tipo da coluna.

Cada regra de ``core.import_values`` tem o seu teste de fronteira: a vírgula e o ponto, o dinheiro
em centavos arredondado para cima na metade, o percentual que o Excel guarda como fração, a data que
não existe, o número de série do Excel e a lista que ignora caixa e acento. São as regras do
``importar.js`` do protótipo.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from src.core.export_document import ValueKind
from src.core.import_values import (
    MAX_EXCEL_SERIAL,
    Converted,
    cents_of,
    convert,
    date_of,
    is_blank,
    normalize_text,
    number_of,
    text_of,
)
from src.core.spreadsheet_reader import RawCell


def _celula(valor: Any, formato: str = "General") -> RawCell:
    return RawCell(valor, formato)


# ── Texto e vazio ────────────────────────────────────────────────────────


@pytest.mark.parametrize("valor", [None, "", "   ", "\t\n"])
def test_celula_vazia_ou_so_com_espacos_e_vazia(valor: object) -> None:
    assert is_blank(valor) is True


@pytest.mark.parametrize("valor", [0, 0.0, "0", "x", False])
def test_zero_e_falso_nao_sao_celula_vazia(valor: object) -> None:
    assert is_blank(valor) is False


def test_texto_perde_os_espacos_das_pontas() -> None:
    assert convert(_celula("  Torre B  "), ValueKind.TEXT) == Converted(value="Torre B")


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        (12.0, "12"),
        (12.5, "12.5"),
        (7, "7"),
        (datetime.fromisoformat("2026-10-05T00:00:00"), "05/10/2026"),
        (date(2026, 10, 5), "05/10/2026"),
    ],
)
def test_numero_inteiro_nao_ganha_ponto_zero_e_data_vira_dia_mes_ano(
    valor: object, texto: str
) -> None:
    assert text_of(valor) == texto
    assert convert(_celula(valor), ValueKind.TEXT).value == texto


def test_lista_ignora_caixa_acento_e_espacos_e_devolve_a_opcao_do_modulo() -> None:
    opcoes = ("Não conforme", "Conforme")

    for digitado in ("não conforme", "NAO  CONFORME", " Nao Conforme "):
        assert convert(_celula(digitado), ValueKind.TEXT, options=opcoes) == Converted(
            value="Não conforme"
        )


def test_valor_fora_da_lista_diz_quais_sao_as_opcoes() -> None:
    resultado = convert(_celula("Talvez"), ValueKind.TEXT, options=("Sim", "Não"))

    assert resultado == Converted(problem="valor fora da lista (Sim, Não)")


def test_o_texto_normalizado_perde_acento_caixa_e_espaco_repetido() -> None:
    assert normalize_text("  Situação   Atual ") == "situacao atual"
    assert normalize_text("ÇÃO") == "cao"


# ── Números ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("digitado", "esperado"),
    [
        ("1234", Decimal(1234)),
        ("1234,56", Decimal("1234.56")),
        ("1.234,56", Decimal("1234.56")),
        ("1.234.567,8", Decimal("1234567.8")),
        ("R$ 1.234,56", Decimal("1234.56")),
        ("45,3%", Decimal("45.3")),
        ("12.5", Decimal("12.5")),
        ("1.234", Decimal("1.234")),
        ("-7,5", Decimal("-7.5")),
        ("+3", Decimal(3)),
        (" 8 ", Decimal(8)),
    ],
)
def test_numero_digitado_com_virgula_ponto_simbolo_e_espacos(
    digitado: str, esperado: Decimal
) -> None:
    assert number_of(digitado) == esperado


@pytest.mark.parametrize(
    "digitado", ["abc", "12a", "1e5", "1_000", "NaN", "Infinity", "1,2,3", "--4", ".", "R$", "1R2"]
)
def test_texto_que_nao_e_numero_e_recusado(digitado: str) -> None:
    assert number_of(digitado) is None
    assert convert(_celula(digitado), ValueKind.DECIMAL) == Converted(problem="número inválido")


@pytest.mark.parametrize("valor", [True, False, None, date(2026, 1, 1), float("nan"), float("inf")])
def test_booleano_data_vazio_e_nao_finito_nao_sao_numero(valor: object) -> None:
    assert number_of(valor) is None


def test_numero_de_celula_numerica_nao_perde_casas_por_causa_do_float() -> None:
    assert number_of(0.1) == Decimal("0.1")
    assert number_of(1234.56) == Decimal("1234.56")


def test_inteiro_aceita_zero_decimal_e_recusa_fracao() -> None:
    assert convert(_celula(12.0), ValueKind.INTEGER) == Converted(value=12)
    assert convert(_celula("12,0"), ValueKind.INTEGER) == Converted(value=12)
    assert convert(_celula("12,5"), ValueKind.INTEGER) == Converted(
        problem="número inteiro inválido"
    )
    assert convert(_celula(-3), ValueKind.INTEGER) == Converted(value=-3)


def test_decimal_guarda_o_numero_exato() -> None:
    assert convert(_celula("12,345"), ValueKind.DECIMAL) == Converted(value=Decimal("12.345"))


def test_numero_acima_do_limite_e_recusado_e_o_limite_exato_passa() -> None:
    assert convert(_celula(10**15), ValueKind.DECIMAL) == Converted(value=Decimal(10**15))
    assert convert(_celula(10**15 + 1), ValueKind.DECIMAL) == Converted(
        problem="número fora do limite"
    )
    assert convert(_celula(-(10**15) - 1), ValueKind.MONEY) == Converted(
        problem="número fora do limite"
    )


# ── Dinheiro ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("reais", "centavos"),
    [
        (Decimal("1234.56"), 123456),
        (Decimal(0), 0),
        (Decimal("0.005"), 1),
        (Decimal("0.004"), 0),
        (Decimal("-0.005"), -1),
        (Decimal("1.005"), 101),
        (Decimal("19.999"), 2000),
    ],
)
def test_reais_viram_centavos_inteiros_arredondados_para_cima_na_metade(
    reais: Decimal, centavos: int
) -> None:
    assert cents_of(reais) == centavos


def test_dinheiro_de_texto_e_de_celula_numerica_chega_em_centavos() -> None:
    assert convert(_celula("1.234,56"), ValueKind.MONEY) == Converted(value=123456)
    assert convert(_celula(1234.56, '"R$" #,##0.00'), ValueKind.MONEY) == Converted(value=123456)
    assert convert(_celula("R$ 10"), ValueKind.MONEY) == Converted(value=1000)


def test_dinheiro_invalido_diz_valor_invalido() -> None:
    assert convert(_celula("dez reais"), ValueKind.MONEY) == Converted(problem="valor inválido")


# ── Percentual ───────────────────────────────────────────────────────────


def test_celula_formatada_como_percentual_guarda_fracao_e_volta_em_pontos() -> None:
    assert convert(_celula(0.453, "0.0%"), ValueKind.PERCENT) == Converted(value=Decimal("45.3"))
    assert convert(_celula(1, "0%"), ValueKind.PERCENT) == Converted(value=Decimal(100))


def test_percentual_digitado_como_texto_ou_numero_comum_ja_esta_em_pontos() -> None:
    assert convert(_celula("45,3%"), ValueKind.PERCENT) == Converted(value=Decimal("45.3"))
    assert convert(_celula("0,5"), ValueKind.PERCENT) == Converted(value=Decimal("0.5"))
    assert convert(_celula(45.3), ValueKind.PERCENT) == Converted(value=Decimal("45.3"))


def test_texto_com_porcento_em_celula_formatada_como_percentual_nao_multiplica_de_novo() -> None:
    assert convert(_celula("45,3%", "0.0%"), ValueKind.PERCENT) == Converted(value=Decimal("45.3"))


# ── Datas ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("valor", "esperada"),
    [
        (datetime.fromisoformat("2026-10-05T13:30:00"), date(2026, 10, 5)),
        (date(2026, 10, 5), date(2026, 10, 5)),
        ("05/10/2026", date(2026, 10, 5)),
        ("5/1/2026", date(2026, 1, 5)),
        ("05/10/26", date(2026, 10, 5)),
        ("2026-10-05", date(2026, 10, 5)),
        ("2026-10-05T10:00:00", date(2026, 10, 5)),
        (" 29/02/2028 ", date(2028, 2, 29)),
        (1, date(1899, 12, 31)),
        (46_300, date(2026, 10, 5)),
        (46_300.9, date(2026, 10, 5)),
    ],
)
def test_data_de_celula_de_texto_e_de_numero_de_serie(valor: object, esperada: date) -> None:
    assert date_of(valor) == esperada


@pytest.mark.parametrize(
    "valor",
    [
        "31/02/2026",
        "29/02/2027",
        "32/01/2026",
        "01/13/2026",
        "2026-02-30",
        "05-10-2026",
        "ontem",
        "5/10",
        0,
        -4,
        MAX_EXCEL_SERIAL + 1,
        float("nan"),
        float("inf"),
        True,
    ],
)
def test_data_que_nao_existe_ou_fora_do_formato_e_invalida(valor: object) -> None:
    assert date_of(valor) is None
    assert convert(_celula(valor), ValueKind.DATE) == Converted(
        problem="data inválida (use dd/mm/aaaa)"
    )


def test_o_ultimo_numero_de_serie_valido_e_31_12_9999() -> None:
    assert date_of(MAX_EXCEL_SERIAL) == date(9999, 12, 31)
