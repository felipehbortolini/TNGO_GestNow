"""Validação do dicionário da EAP e dos pesos (ISSUE-036).

O formulário manda texto; a validação devolve o dado tipado ou a mensagem de cada campo
errado (422). As fronteiras: 3 e 120 caracteres da descrição, 300 dos textos, e os pesos
zero, no máximo do pacote e fechando 100.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.core.errors import InvalidDataError
from src.modulos.planejamento import validation as v

D = Decimal

ESCOLHAS = v.DictionaryChoices(
    company_ids=frozenset({5, 7}),
    person_ids=frozenset({6, 11}),
    eac_codes=frozenset({"1.1.1", "3.1.2"}),
)

DICIONARIO = {
    "descricao": "Moinho de bolas",
    "entregavel": "Moinho entregue na obra com data book",
    "aceitacao": "Recebimento sem avarias e FAT aprovado",
    "empresa": "7",
    "responsavel": "6",
    "eac": "1.1.1",
}


def _erros(chamada: object) -> dict[str, str]:
    with pytest.raises(InvalidDataError) as erro:
        chamada()  # type: ignore[operator]
    assert isinstance(erro.value.detail, dict)
    return erro.value.detail


def test_dicionario_valido_vira_dado_tipado() -> None:
    dado = v.parse_dictionary_form(DICIONARIO, ESCOLHAS)

    assert dado.description == "Moinho de bolas"
    assert dado.deliverable == "Moinho entregue na obra com data book"
    assert dado.acceptance == "Recebimento sem avarias e FAT aprovado"
    assert (dado.company_id, dado.owner_id) == (7, 6)
    assert dado.eac_code == "1.1.1"


def test_campos_opcionais_vazios_viram_nulo() -> None:
    dado = v.parse_dictionary_form({"descricao": "Fundações", "responsavel": "11"}, ESCOLHAS)

    assert dado.deliverable == ""
    assert dado.acceptance == ""
    assert dado.company_id is None
    assert dado.eac_code is None


def test_espacos_nas_pontas_nao_contam() -> None:
    campos = dict(DICIONARIO, descricao="  Moinho de bolas  ")

    assert v.parse_dictionary_form(campos, ESCOLHAS).description == "Moinho de bolas"


def test_descricao_curta_demais_e_recusada() -> None:
    erros = _erros(
        lambda: v.parse_dictionary_form({"descricao": "AB", "responsavel": "6"}, ESCOLHAS)
    )

    assert erros == {"descricao": v.PACKAGE_DESCRIPTION_MESSAGE}


def test_descricao_sem_responsavel_diz_o_que_falta() -> None:
    erros = _erros(lambda: v.parse_dictionary_form({"descricao": "Moinho de bolas"}, ESCOLHAS))

    assert erros == {"responsavel": v.REQUIRED_MESSAGE.format(label="o responsável")}


def test_descricao_aceita_120_caracteres_e_recusa_121() -> None:
    campos = dict(DICIONARIO, descricao="a" * 120)
    assert v.parse_dictionary_form(campos, ESCOLHAS).description == "a" * 120

    campos["descricao"] = "a" * 121
    erros = _erros(lambda: v.parse_dictionary_form(campos, ESCOLHAS))
    assert list(erros) == ["descricao"]


def test_textos_aceitam_300_caracteres_e_recusam_301() -> None:
    campos = dict(DICIONARIO, entregavel="b" * 300, aceitacao="c" * 300)
    dado = v.parse_dictionary_form(campos, ESCOLHAS)
    assert (len(dado.deliverable), len(dado.acceptance)) == (300, 300)

    campos["entregavel"] = "b" * 301
    campos["aceitacao"] = "c" * 301
    erros = _erros(lambda: v.parse_dictionary_form(campos, ESCOLHAS))
    assert set(erros) == {"entregavel", "aceitacao"}


def test_cadastros_fora_da_lista_sao_recusados() -> None:
    campos = dict(DICIONARIO, empresa="99", eac="9.9.9", responsavel="abc")

    erros = _erros(lambda: v.parse_dictionary_form(campos, ESCOLHAS))

    assert set(erros) == {"empresa", "eac", "responsavel"}


def test_regra_dos_cem_por_cento_recusa_soma_diferente() -> None:
    assert v.hundred_rule_error([D("60"), D("40")]) is None
    assert v.hundred_rule_error([D("33.33"), D("33.33"), D("33.34")]) is None
    assert v.hundred_rule_error([]) == v.WEIGHTS_TOTAL_MESSAGE.format(total=D("0.00"))

    erro = v.hundred_rule_error([D("60"), D("30")])

    assert erro == v.WEIGHTS_TOTAL_MESSAGE.format(total=D("90.00"))


def test_peso_do_pacote_entre_zero_e_o_maximo() -> None:
    assert v.package_weight_error(D("0.5"), maximum=D("10")) is None
    assert v.package_weight_error(D("10"), maximum=D("10")) is None
    assert v.package_weight_error(D(0), maximum=D("10")) == v.PACKAGE_WEIGHT_ZERO_MESSAGE
    assert v.package_weight_error(D("-1"), maximum=D("10")) == v.PACKAGE_WEIGHT_ZERO_MESSAGE
    assert v.package_weight_error(
        D("10.01"), maximum=D("10")
    ) == v.PACKAGE_WEIGHT_MAX_MESSAGE.format(maximum=D("10"))
