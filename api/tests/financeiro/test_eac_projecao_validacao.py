"""Validações puras da projeção no término e da importação dos custos do ERP (ISSUE-031).

A projeção exige justificativa e não fica negativa nem abaixo do realizado; a linha do ERP
confere o item de custo, o mês, os valores não negativos e ao menos uma coluna preenchida.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from src.core.errors import InvalidDataError
from src.modulos.financeiro import validation
from src.modulos.financeiro.validation import ErpCostInput

REFERENCE = date(2026, 9, 25)
LEVELS = {"1.1.1": 3, "1.1": 2}


# ── Projeção no término ──────────────────────────────────────────────────


def test_projecao_sem_justificativa_e_recusada_com_a_mensagem_no_campo() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_projection_form({"projecao": "10.000,00", "justificativa": "  "})

    assert "justificativa da projeção" in erro.value.detail["justificativa"]


def test_projecao_valida_volta_em_centavos_com_a_justificativa() -> None:
    form = validation.parse_projection_form(
        {"projecao": "10.000,00", "justificativa": "Premissas revisadas."}
    )

    assert form.value_cents == 1_000_000
    assert form.justification == "Premissas revisadas."


def test_projecao_sem_valor_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_projection_form({"projecao": "", "justificativa": "Premissas revisadas."})

    assert "Informe a projeção" in erro.value.detail["projecao"]


def test_projecao_negativa_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_projection_form(
            {"projecao": "-1,00", "justificativa": "Premissas revisadas."}
        )

    assert "negativa" in erro.value.detail["projecao"]


def test_projecao_abaixo_do_realizado_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_projection_form(
            {"projecao": "999,00", "justificativa": "Premissas revisadas."}, actual_cents=100_000
        )

    assert "menor que o realizado" in erro.value.detail["projecao"]


def test_justificativa_acima_do_maximo_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_projection_form({"projecao": "1.000,00", "justificativa": "x" * 301})

    assert "300" in erro.value.detail["justificativa"]


# ── Importação dos custos do ERP ─────────────────────────────────────────


def _line(**fields: Any) -> ErpCostInput:
    base: dict[str, Any] = {
        "code": "1.1.1",
        "month": date(2026, 8, 1),
        "committed_cents": 1_000,
        "actual_cents": 600,
        "projection_cents": None,
    }
    return ErpCostInput(**{**base, **fields})


def _problems(line: ErpCostInput, **extra: Any) -> dict[str, str]:
    return validation.erp_cost_problems(line, item_levels=LEVELS, reference_date=REFERENCE, **extra)


def test_linha_do_erp_valida_passa_sem_erro() -> None:
    assert _problems(_line()) == {}


def test_item_desconhecido_no_erp_e_recusado() -> None:
    problems = _problems(_line(code="9.9.9"))

    assert "não existe na EAC" in problems["item"]


def test_item_de_pacote_no_erp_e_recusado() -> None:
    problems = _problems(_line(code="1.1"))

    assert "nível 3" in problems["item"]


def test_mes_futuro_no_erp_e_recusado() -> None:
    problems = _problems(_line(month=date(2026, 10, 1)))

    assert "mês futuro" in problems["mes"]


def test_mes_do_mesmo_mes_da_referencia_e_aceito() -> None:
    assert _problems(_line(month=date(2026, 9, 30))) == {}


def test_mes_ausente_no_erp_e_recusado() -> None:
    problems = _problems(_line(month=None))

    assert "Informe o mês" in problems["mes"]


def test_valor_negativo_no_erp_e_recusado() -> None:
    problems = _problems(_line(committed_cents=-1))

    assert "negativo" in problems["comprometido"]


def test_linha_do_erp_sem_valor_algum_e_recusada() -> None:
    problems = _problems(_line(committed_cents=None, actual_cents=None, projection_cents=None))

    assert "ao menos um valor" in problems["valores"]


def test_linha_do_erp_com_apenas_um_valor_passa() -> None:
    line = _line(committed_cents=None, actual_cents=None, projection_cents=1_500)

    assert _problems(line) == {}


def test_projecao_do_erp_abaixo_do_realizado_e_recusada() -> None:
    problems = _problems(_line(actual_cents=1_000, projection_cents=999))

    assert "menor que o realizado" in problems["projecao"]


def test_projecao_vigente_cobre_a_linha_que_omite_a_projecao() -> None:
    line = _line(committed_cents=None, actual_cents=1_000, projection_cents=None)

    problems = _problems(line, current_projection_cents=900)

    assert "menor que o realizado" in problems["projecao"]
