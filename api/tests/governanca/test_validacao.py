"""Validação da solicitação e do cancelamento (ISSUE-023): obrigatórios, limites e a emergência."""

from __future__ import annotations

import pytest

from src.core.errors import InvalidDataError
from src.modulos.governanca import validation as v
from tests.governanca.apoio import HOJE, solicitacao_valida


def _erros(**mudancas: str) -> dict[str, str]:
    with pytest.raises(InvalidDataError) as erro:
        v.validate_new_change(solicitacao_valida(**mudancas), reference_date=HOJE)
    return dict(erro.value.detail)


def test_solicitacao_valida_passa() -> None:
    nova = v.validate_new_change(solicitacao_valida(), reference_date=HOJE)
    assert nova.kind == "Escopo"
    assert nova.emergency_start is None
    assert not nova.is_emergency_execution


@pytest.mark.parametrize(
    "campo",
    [v.FIELD_TITLE, v.FIELD_KIND, v.FIELD_ORIGIN, v.FIELD_PRIORITY, v.FIELD_DESCRIPTION],
)
def test_campo_obrigatorio_faltando_aponta_o_campo(campo: str) -> None:
    assert campo in _erros(**{campo: ""})


def test_limites_do_titulo_na_fronteira() -> None:
    assert v.FIELD_TITLE in _erros(titulo="x" * 9)
    assert v.FIELD_TITLE in _erros(titulo="x" * 151)
    for tamanho in (10, 150):
        v.validate_new_change(solicitacao_valida(titulo="x" * tamanho), reference_date=HOJE)


def test_limites_da_descricao_na_fronteira() -> None:
    assert v.FIELD_DESCRIPTION in _erros(descricao="x" * 19)
    assert v.FIELD_DESCRIPTION in _erros(descricao="x" * 1001)
    v.validate_new_change(solicitacao_valida(descricao="x" * 20), reference_date=HOJE)


def test_opcao_fora_da_lista_e_recusada() -> None:
    assert v.FIELD_KIND in _erros(tipo="Inventado")


def test_data_da_solicitacao_nao_pode_ser_futura_nem_invalida() -> None:
    assert _erros(data_solicitacao="2026-10-07")[v.FIELD_REQUEST_DATE] == v.DATE_AFTER_TODAY_MESSAGE
    assert _erros(data_solicitacao="06/10/2026")[v.FIELD_REQUEST_DATE] == v.INVALID_DATE_MESSAGE
    assert v.FIELD_REQUEST_DATE in _erros(data_solicitacao="")
    v.validate_new_change(solicitacao_valida(data_solicitacao="2026-10-06"), reference_date=HOJE)


def test_emergencia_so_conta_com_a_marca_de_execucao_antecipada() -> None:
    sem_marca = v.validate_new_change(
        solicitacao_valida(prioridade="Emergencial"), reference_date=HOJE
    )
    assert sem_marca.emergency_start is None


def test_emergencia_marcada_exige_inicio_e_justificativa() -> None:
    erros = _erros(prioridade="Emergencial", execucao_antecipada="sim")
    assert v.FIELD_EMERGENCY_START in erros
    assert v.FIELD_EMERGENCY_JUSTIFICATION in erros


def test_inicio_da_emergencia_fronteiras() -> None:
    base = {"prioridade": "Emergencial", "execucao_antecipada": "sim"}
    justificativa = "x" * 20
    ok = v.validate_new_change(
        solicitacao_valida(
            **base, inicio_emergencia="2026-10-06", justificativa_emergencia=justificativa
        ),
        reference_date=HOJE,
    )
    assert ok.is_emergency_execution
    antes = _erros(**base, inicio_emergencia="2026-10-05", justificativa_emergencia=justificativa)
    assert v.FIELD_EMERGENCY_START in antes
    depois = _erros(**base, inicio_emergencia="2026-10-07", justificativa_emergencia=justificativa)
    assert depois[v.FIELD_EMERGENCY_START] == v.DATE_AFTER_TODAY_MESSAGE
    assert v.FIELD_EMERGENCY_JUSTIFICATION in _erros(
        **base, inicio_emergencia="2026-10-06", justificativa_emergencia="x" * 19
    )


def test_justificativa_do_cancelamento_fronteiras() -> None:
    for tamanho in (10, 500):
        assert (
            len(v.validate_cancellation_justification({"justificativa": "x" * tamanho})) == tamanho
        )
    for texto in ("", "   ", "x" * 9, "x" * 501):
        with pytest.raises(InvalidDataError):
            v.validate_cancellation_justification({"justificativa": texto})
