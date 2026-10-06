"""Validações puras das revisões, do remanejamento e do item novo (ISSUE-030).

Cada regra recusa com a mensagem no campo do formulário: saldo livre da origem, custo aprovado
da SM, SM aprovada com custo para a revisão e item da análise que exista na EAC em nível 3.
"""

from __future__ import annotations

import pytest

from src.core.errors import InvalidDataError
from src.modulos.financeiro import validation
from src.modulos.financeiro.validation import RevisionSource


def test_remanejamento_acima_do_saldo_livre_e_recusado_com_a_mensagem() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_reallocation_balance(
            item_code="1.1.1", value_cents=5_000, free_cents=4_999
        )

    message = erro.value.detail["remanejamento_valor"]
    assert "saldo livre" in message
    assert "1.1.1" in message
    assert "R$ 50,00" in message
    assert "R$ 49,99" in message


def test_remanejamento_igual_ao_saldo_livre_passa() -> None:
    validation.check_reallocation_balance(item_code="1.1.1", value_cents=5_000, free_cents=5_000)


def test_item_novo_acima_do_custo_aprovado_na_sm_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_new_item_cost(value_cents=10_001, approved_cents=10_000)

    assert "custo aprovado na SM" in erro.value.detail["item_novo_valor"]


def test_item_novo_igual_ao_custo_aprovado_passa() -> None:
    validation.check_new_item_cost(value_cents=10_000, approved_cents=10_000)


@pytest.mark.parametrize(
    "source",
    [
        RevisionSource(change_id=None, approved=True, cost_cents=1_000),
        RevisionSource(change_id=7, approved=False, cost_cents=1_000),
        RevisionSource(change_id=7, approved=True, cost_cents=0),
    ],
)
def test_revisao_sem_sm_aprovada_com_custo_e_recusada(source: RevisionSource) -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_revision_source(source)

    assert "SM aprovada com custo" in erro.value.detail["mudanca_id"]


def test_revisao_com_sm_aprovada_com_custo_passa() -> None:
    validation.check_revision_source(RevisionSource(change_id=7, approved=True, cost_cents=1_000))


def test_item_da_analise_que_nao_existe_na_eac_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_impact_item(code="9.9.9", level=None)

    message = erro.value.detail["itens_eac"]
    assert "9.9.9" in message
    assert "não existe na EAC" in message


def test_item_da_analise_fora_do_nivel_3_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_impact_item(code="1.1", level=2)

    assert "nível 3" in erro.value.detail["itens_eac"]


def test_item_da_analise_de_nivel_3_passa() -> None:
    validation.check_impact_item(code="1.1.1", level=3)
