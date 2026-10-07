"""Validação do formulário da avaliação de desempenho da contratada (ISSUE-034).

O formulário pede período (AAAA-MM), tipo Mensal ou Final, uma nota de 1 a 5 em todos os
critérios vigentes e comentário dentro de 400 caracteres. O anexo que as notas 1 e 2 exigem é do
serviço (``attachments.has_evidence``), não daqui.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.core.errors import InvalidDataError
from src.modulos.financeiro import validation

CRITERIA = ("hse", "qualidade", "prazo")


def _form(**changes: str) -> dict[str, str]:
    form = {
        "periodo": "2026-07",
        "tipo": "Mensal",
        "hse": "4",
        "qualidade": "4",
        "prazo": "3",
        "comentario": "Mobilização dentro do plano.",
    }
    form.update(changes)
    return form


def test_avaliacao_valida_volta_com_as_notas_e_o_comentario() -> None:
    evaluation = validation.parse_evaluation_form(_form(), criteria_ids=CRITERIA)

    assert evaluation.period == date(2026, 7, 1)
    assert evaluation.kind == "Mensal"
    assert evaluation.notes == {"hse": 4, "qualidade": 4, "prazo": 3}
    assert evaluation.comment == "Mobilização dentro do plano."


def test_avaliacao_final_e_aceita() -> None:
    evaluation = validation.parse_evaluation_form(_form(tipo="Final"), criteria_ids=CRITERIA)

    assert evaluation.kind == "Final"


def test_comentario_e_opcional() -> None:
    evaluation = validation.parse_evaluation_form(_form(comentario=""), criteria_ids=CRITERIA)

    assert evaluation.comment == ""


def test_espacos_sao_removidos_dos_campos() -> None:
    evaluation = validation.parse_evaluation_form(
        _form(comentario="  Plano registrado.  "), criteria_ids=CRITERIA
    )

    assert evaluation.comment == "Plano registrado."


@pytest.mark.parametrize("kind", ["", "Trimestral", "mensal"])
def test_tipo_invalido_e_recusado(kind: str) -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_evaluation_form(_form(tipo=kind), criteria_ids=CRITERIA)

    assert "Mensal" in erro.value.detail["tipo"]


@pytest.mark.parametrize("period", ["", "2026-13", "julho", "2026-07-15"])
def test_periodo_invalido_e_recusado(period: str) -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_evaluation_form(_form(periodo=period), criteria_ids=CRITERIA)

    assert "período" in erro.value.detail["periodo"]


@pytest.mark.parametrize("note", ["", "0", "6", "x", "4,5"])
def test_nota_fora_de_1_a_5_e_recusada(note: str) -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_evaluation_form(_form(prazo=note), criteria_ids=CRITERIA)

    assert "nota de 1 a 5" in erro.value.detail["prazo"]


def test_todos_os_criterios_vigentes_sao_obrigatorios() -> None:
    form = _form()
    del form["qualidade"]

    with pytest.raises(InvalidDataError) as erro:
        validation.parse_evaluation_form(form, criteria_ids=CRITERIA)

    assert "nota de 1 a 5" in erro.value.detail["qualidade"]


def test_comentario_acima_de_400_caracteres_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_evaluation_form(_form(comentario="x" * 401), criteria_ids=CRITERIA)

    assert "400" in erro.value.detail["comentario"]
