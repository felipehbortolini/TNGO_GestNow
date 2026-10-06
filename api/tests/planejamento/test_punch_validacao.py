"""Validação da Punch list (ISSUE-049): uma mensagem por campo, com os limites do protótipo."""

from __future__ import annotations

from datetime import date

import pytest

from src.modulos.planejamento import punch_validation as validation
from src.modulos.planejamento.punch_validation import ItemInput, RegisterChoices

ESCOLHAS = RegisterChoices(
    system_ids=frozenset({1}), company_ids=frozenset({2}), person_ids=frozenset({3})
)


def _valido(**mudancas: object) -> ItemInput:
    base = ItemInput(
        system_id=1,
        subsystem="Painéis",
        tag="PN-01",
        discipline="Elétrica",
        category="A",
        milestone="Comissionamento",
        origin="Walkdown",
        description="Falta identificação dos cabos.",
        company_id=2,
        responsible_id=3,
        identified_by_id=3,
        due_date=date(2026, 10, 5),
    )
    return ItemInput(**{**base.__dict__, **mudancas})


def test_item_completo_nao_tem_mensagem() -> None:
    assert validation.item_problems(_valido(), ESCOLHAS) == {}


def test_item_vazio_pede_todos_os_campos() -> None:
    problemas = validation.item_problems(ItemInput(), ESCOLHAS)
    assert set(problemas) == {
        "sistema",
        "empresa",
        "responsavel",
        "identificado_por",
        "disciplina",
        "categoria",
        "marco",
        "origem",
        "subsistema",
        "tag",
        "descricao",
        "prazo",
    }


def test_sistema_de_outro_projeto_e_recusado() -> None:
    assert validation.item_problems(_valido(system_id=99), ESCOLHAS) == {
        "sistema": validation.INVALID_CHOICE
    }


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("category", "D"), ("discipline", "Pintura"), ("milestone", "Natal"), ("origin", "Boato")],
)
def test_lista_fechada_recusa_o_que_nao_esta_nela(campo: str, valor: str) -> None:
    assert len(validation.item_problems(_valido(**{campo: valor}), ESCOLHAS)) == 1


def test_descricao_aceita_trezentos_caracteres_e_recusa_trezentos_e_um() -> None:
    assert validation.item_problems(_valido(description="x" * 300), ESCOLHAS) == {}
    assert "descricao" in validation.item_problems(_valido(description="x" * 301), ESCOLHAS)


def test_cancelamento_pede_dez_caracteres() -> None:
    assert validation.cancellation_problems("123456789") == {
        "justificativa": validation.JUSTIFICATION_REQUIRED
    }
    assert validation.cancellation_problems(" 1234567890 ") == {}


def test_reprovar_pede_o_motivo_e_aprovar_nao() -> None:
    assert validation.verification_problems("reprovado", " ") == {
        "comentario": validation.REJECTION_REASON_REQUIRED
    }
    assert validation.verification_problems("reprovado", "Cabo trocado") == {}
    assert validation.verification_problems("aprovado", "") == {}
    assert "resultado" in validation.verification_problems("talvez", "")


def test_enviar_para_verificacao_pede_o_que_foi_feito() -> None:
    assert validation.treatment_problems("  ") == {"comentario": validation.TREATMENT_REQUIRED}
    assert validation.treatment_problems("Feito.") == {}


def test_o_formulario_vira_item_e_o_que_nao_le_fica_vazio() -> None:
    item = validation.item_from_form({"sistema": "7", "prazo": "2026-10-05", "empresa": "x"})
    assert item.system_id == 7
    assert item.due_date == date(2026, 10, 5)
    assert item.company_id is None
    assert validation.date_of("31/02/2026") is None
