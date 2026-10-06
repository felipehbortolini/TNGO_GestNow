"""Validação do servidor nos formulários do 6WLA (ISSUE-045): os campos do protótipo.

O que a tela manda é texto; a validação devolve dado tipado ou a mensagem de cada campo
errado (422). O caso de fronteira de cada limite: o comprimento exato, a data que não
existe, a semana fora do horizonte.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.core.errors import InvalidDataError
from src.modulos.planejamento import validation as v

ESCOLHAS = v.RegisterChoices(
    company_ids=frozenset({1, 2}),
    person_ids=frozenset({5, 7}),
    disciplines=frozenset({"Civil", "Mecânica"}),
)
ATIVIDADE = {
    "atividade": "Montagem da carcaça",
    "area": "Moagem 210",
    "disciplina": "Mecânica",
    "empresa": "1",
    "responsavel": "5",
}
RESTRICAO = {
    "tipo": "Material",
    "responsavel": "7",
    "descricao": "Chegada do moinho",
    "necessaria": "2026-09-28",
}


def _erros(chamada: object) -> dict[str, str]:
    with pytest.raises(InvalidDataError) as erro:
        chamada()  # type: ignore[operator]
    assert isinstance(erro.value.detail, dict)
    return erro.value.detail


def test_atividade_valida_vira_dado_tipado() -> None:
    dado = v.parse_activity(v.ActivityForm(ATIVIDADE, ["0", "2"]), ESCOLHAS)

    assert dado.activity == "Montagem da carcaça"
    assert (dado.company_id, dado.owner_id) == (1, 5)
    assert dado.planned == (True, False, True, False, False, False)


def test_atividade_sem_nada_diz_o_que_falta_em_cada_campo() -> None:
    erros = _erros(lambda: v.parse_activity(v.ActivityForm({}, []), ESCOLHAS))

    assert set(erros) == {"atividade", "area", "disciplina", "empresa", "responsavel", "semanas"}
    assert erros["semanas"] == v.WEEKS_MESSAGE


def test_atividade_aceita_120_caracteres_e_recusa_121() -> None:
    campos = dict(ATIVIDADE)
    campos["atividade"] = "a" * 120
    assert v.parse_activity(v.ActivityForm(campos, ["0"]), ESCOLHAS).activity == "a" * 120

    campos["atividade"] = "a" * 121
    erros = _erros(lambda: v.parse_activity(v.ActivityForm(campos, ["0"]), ESCOLHAS))
    assert list(erros) == ["atividade"]


def test_espacos_nas_pontas_nao_contam() -> None:
    campos = dict(ATIVIDADE, atividade="   Montagem   ")

    assert v.parse_activity(v.ActivityForm(campos, ["0"]), ESCOLHAS).activity == "Montagem"


def test_empresa_responsavel_e_disciplina_fora_do_cadastro_sao_recusados() -> None:
    campos = dict(ATIVIDADE, empresa="99", responsavel="abc", disciplina="Astrologia")

    erros = _erros(lambda: v.parse_activity(v.ActivityForm(campos, ["0"]), ESCOLHAS))

    assert set(erros) == {"empresa", "responsavel", "disciplina"}


def test_semana_fora_do_horizonte_e_ignorada() -> None:
    assert v.planned_weeks(["5"]) == (False, False, False, False, False, True)
    assert v.planned_weeks(["6", "-1", "x", "²"]) == (False,) * 6


def test_restricao_valida() -> None:
    dado = v.parse_constraint(RESTRICAO, ESCOLHAS)

    assert dado.kind == "Material"
    assert dado.owner_id == 7
    assert dado.due_date == date(2026, 9, 28)


def test_os_oito_tipos_do_prototipo() -> None:
    assert v.CONSTRAINT_KINDS == (
        "Projeto",
        "Material",
        "Mão de obra",
        "Equipamento",
        "Liberação de área",
        "Segurança",
        "Documentação",
        "Predecessora",
    )


def test_restricao_com_tipo_desconhecido_data_inexistente_e_descricao_longa() -> None:
    campos = dict(RESTRICAO, tipo="Outro", necessaria="2026-02-30", descricao="d" * 201)

    erros = _erros(lambda: v.parse_constraint(campos, ESCOLHAS))

    assert set(erros) == {"tipo", "necessaria", "descricao"}


def test_descricao_aceita_200_caracteres() -> None:
    campos = dict(RESTRICAO, descricao="d" * 200)

    assert len(v.parse_constraint(campos, ESCOLHAS).description) == 200


def test_remocao_pede_a_data_e_aceita_comentario_vazio() -> None:
    dado = v.parse_removal({"remocao": "2026-09-25", "comentario": "  "})

    assert dado.removal_date == date(2026, 9, 25)
    assert dado.comment is None


def test_remocao_recusa_data_ausente_e_comentario_acima_de_200() -> None:
    erros = _erros(lambda: v.parse_removal({"comentario": "c" * 201}))

    assert set(erros) == {"remocao", "comentario"}


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("7", 7),
        (" 12 ", 12),
        ("", None),
        (None, None),
        ("abc", None),
        ("-1", None),
        ("²", None),
        ("1" * 19, None),
    ],
)
def test_id_do_endereco_ou_do_formulario(texto: str | None, esperado: int | None) -> None:
    assert v.parse_id(texto) == esperado
