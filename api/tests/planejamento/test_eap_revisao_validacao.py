"""Validação do pacote novo e da revisão da EAP (ISSUE-038).

O formulário manda texto; a validação devolve o dado tipado ou a mensagem de cada campo
errado. O desdobramento sai de um pacote de planejamento existente e não passa o peso da
origem; a revisão exige a SM, ajusta um pacote de nível 3 e a soma dos pesos alterados fica
abaixo de 100. O peso acima do máximo, a quantidade abaixo do executado e o término antes do
início são recusados com a mensagem.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.core.errors import InvalidDataError
from src.modulos.planejamento import validation as v
from src.modulos.planejamento.calculations import EapStep

D = Decimal

LIMITES = v.RevisionLimits(max_package_weight=D(10), max_estimated_weight=D(5))

MODELOS = (
    {
        "id": "engenharia",
        "nome": "Engenharia (documentos)",
        "etapas": (
            {"nome": "Elaboração", "peso": 40},
            {"nome": "Emissão para construção", "peso": 60},
        ),
    },
)

PACOTES = {
    "2.1": v.PackageState(code="2.1", level=2, kind="", criterion=None, weight=D(0)),
    "3.1.1": v.PackageState(
        code="3.1.1",
        level=3,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("2.00"),
        quantity=D(120),
        executed=D(40),
        start=date(2026, 1, 5),
        finish=date(2026, 12, 20),
    ),
    "3.1.2": v.PackageState(
        code="3.1.2",
        level=3,
        kind="Planejamento",
        criterion=None,
        weight=D("3.00"),
        start=date(2026, 1, 5),
        finish=date(2026, 12, 31),
    ),
}


def formulario(**alteracoes: str) -> dict[str, str]:
    raw = {
        "recurso": v.REVISION,
        "sm": "SM-2026-001",
        "tipo": "Trabalho",
        "pai": "2.1",
        "descricao": "Pipe rack PR-03",
        "criterio": "Unidades",
        "unidade": "m",
        "quantidade": "120",
        "peso": "2.50",
        "inicio": "2026-10-05",
        "termino": "2026-12-20",
        "responsavel": "6",
        "justificativa": "Acréscimo de escopo aprovado na SM.",
    }
    raw.update(alteracoes)
    return raw


def revisao(**alteracoes: str) -> dict[str, str]:
    raw = {
        "sm": "SM-2026-001",
        "pacote": "3.1.1",
        "peso": "4.00",
        "justificativa": "Acréscimo de escopo aprovado na SM.",
    }
    raw.update(alteracoes)
    return raw


def novo(raw: dict[str, str]) -> v.NewPackageData:
    return v.parse_package_form(raw, packages=PACOTES, limits=LIMITES, stage_models=MODELOS)


def ajuste(raw: dict[str, str]) -> v.RevisionData:
    return v.parse_revision_form(raw, packages=PACOTES, limits=LIMITES)


def _erros(chamada: object) -> dict[str, str]:
    with pytest.raises(InvalidDataError) as erro:
        chamada()  # type: ignore[operator]
    assert isinstance(erro.value.detail, dict)
    return erro.value.detail


def test_pacote_novo_por_revisao_vira_dado_tipado() -> None:
    dado = novo(formulario())

    assert dado.resource == v.REVISION
    assert dado.parent_code == "2.1"
    assert dado.description == "Pipe rack PR-03"
    assert dado.kind == "Trabalho"
    assert dado.criterion == "Unidades"
    assert (dado.unit, dado.quantity) == ("m", D(120))
    assert dado.weight == D("2.50")
    assert (dado.start, dado.finish) == (date(2026, 10, 5), date(2026, 12, 20))
    assert (dado.company_id, dado.owner_id) == (None, 6)
    assert dado.change_code == "SM-2026-001"
    assert dado.source_code is None
    assert dado.steps == ()


def test_pacote_novo_por_desdobramento_instancia_as_etapas_do_modelo() -> None:
    raw = formulario(
        recurso=v.BREAKDOWN,
        sm="",
        origem="3.1.2",
        criterio="Etapas",
        modelo="engenharia",
        unidade="",
        quantidade="",
        peso="3.00",
    )

    dado = novo(raw)

    assert dado.resource == v.BREAKDOWN
    assert dado.kind == "Trabalho"
    assert dado.criterion == "Etapas"
    assert dado.model == "engenharia"
    assert dado.source_code == "3.1.2"
    assert dado.change_code is None
    assert dado.steps == (
        EapStep(name="Elaboração", weight=D(40)),
        EapStep(name="Emissão para construção", weight=D(60)),
    )


def test_pacote_de_planejamento_na_revisao_nao_pede_criterio() -> None:
    raw = formulario(tipo="Planejamento", criterio="", unidade="", quantidade="")

    dado = novo(raw)

    assert dado.kind == "Planejamento"
    assert dado.criterion is None
    assert (dado.unit, dado.quantity) == ("", None)
    assert dado.steps == ()


def test_desdobramento_e_sempre_pacote_de_trabalho() -> None:
    raw = formulario(recurso=v.BREAKDOWN, sm="", origem="3.1.2", tipo="Planejamento", peso="1.00")

    assert novo(raw).kind == "Trabalho"


@pytest.mark.parametrize(
    "criterio",
    ["Etapas", "Unidades", "Marco 0/100", "Marco 50/50", "Percentual estimado"],
)
def test_pacote_de_trabalho_aceita_cada_criterio(criterio: str) -> None:
    raw = formulario(criterio=criterio)
    if criterio == "Etapas":
        raw.update(modelo="engenharia", unidade="", quantidade="")
    elif criterio != "Unidades":
        raw.update(unidade="", quantidade="")

    dado = novo(raw)

    assert dado.criterion == criterio


def test_pacote_novo_com_subarea_inexistente_e_recusado() -> None:
    assert _erros(lambda: novo(formulario(pai="9.9"))) == {"pai": v.PARENT_MESSAGE}


def test_peso_acima_do_maximo_e_recusado() -> None:
    erros = _erros(lambda: novo(formulario(peso="10.01")))

    assert erros == {"peso": v.PACKAGE_WEIGHT_MAX_MESSAGE.format(maximum=D(10))}


def test_desdobramento_acima_do_peso_da_origem_e_recusado() -> None:
    raw = formulario(recurso=v.BREAKDOWN, sm="", origem="3.1.2", peso="3.01")

    erros = _erros(lambda: novo(raw))

    assert erros == {"peso": v.BREAKDOWN_WEIGHT_MESSAGE.format(code="3.1.2", weight="3")}


def test_desdobramento_de_pacote_que_nao_e_de_planejamento_e_recusado() -> None:
    raw = formulario(recurso=v.BREAKDOWN, sm="", origem="3.1.1", peso="1.00")

    assert _erros(lambda: novo(raw)) == {"origem": v.ORIGIN_MESSAGE}


def test_justificativa_curta_do_desdobramento_e_recusada() -> None:
    raw = formulario(recurso=v.BREAKDOWN, sm="", origem="3.1.2", peso="1.00", justificativa="curta")

    assert _erros(lambda: novo(raw)) == {"justificativa": v.BREAKDOWN_JUSTIFICATION_MESSAGE}


def test_justificativa_curta_da_revisao_e_recusada() -> None:
    assert _erros(lambda: novo(formulario(justificativa="curta"))) == {
        "justificativa": v.REVISION_JUSTIFICATION_MESSAGE
    }


def test_revisao_sem_sm_e_recusada() -> None:
    assert _erros(lambda: novo(formulario(sm=""))) == {"sm": v.CHANGE_MESSAGE}


def test_pacote_de_trabalho_sem_criterio_e_recusado() -> None:
    assert _erros(lambda: novo(formulario(criterio=""))) == {"criterio": v.CRITERION_MESSAGE}


def test_etapas_com_modelo_inexistente_e_recusado() -> None:
    raw = formulario(criterio="Etapas", modelo="nao-existe", unidade="", quantidade="")

    assert _erros(lambda: novo(raw)) == {"modelo": v.STAGE_MODEL_MESSAGE}


def test_unidades_sem_unidade_e_com_quantidade_invalida_e_recusado() -> None:
    raw = formulario(unidade="", quantidade="0")

    erros = _erros(lambda: novo(raw))

    assert erros == {"unidade": v.UNIT_MESSAGE, "quantidade": v.QUANTITY_MESSAGE}


def test_percentual_estimado_acima_do_peso_do_parametro_e_recusado() -> None:
    raw = formulario(criterio="Percentual estimado", unidade="", quantidade="", peso="6.00")

    erros = _erros(lambda: novo(raw))

    assert erros == {"criterio": v.ESTIMATED_WEIGHT_MESSAGE.format(maximum="5")}


def test_termino_antes_do_inicio_do_pacote_novo_e_recusado() -> None:
    raw = formulario(inicio="2026-10-05", termino="2026-10-04")

    assert _erros(lambda: novo(raw)) == {"termino": v.FINISH_MESSAGE}


def test_pacote_novo_sem_responsavel_e_recusado() -> None:
    assert _erros(lambda: novo(formulario(responsavel=""))) == {
        "responsavel": v.REQUIRED_MESSAGE.format(label="o responsável")
    }


def test_revisao_valida_vira_o_ajuste_tipado() -> None:
    dado = ajuste(revisao(quantidade="80", termino="2027-01-31"))

    assert dado.change_code == "SM-2026-001"
    assert dado.justification == "Acréscimo de escopo aprovado na SM."
    assert dado.adjustment == v.RevisionAdjustment(
        code="3.1.1", weight=D("4.00"), quantity=D(80), finish=date(2027, 1, 31)
    )


def test_revisao_sem_quantidade_nem_termino_mantem_a_linha_de_base() -> None:
    dado = ajuste(revisao())

    assert dado.adjustment.quantity is None
    assert dado.adjustment.finish is None


def test_revisao_com_quantidade_abaixo_do_executado_e_recusada() -> None:
    erros = _erros(lambda: ajuste(revisao(quantidade="30")))

    assert erros == {"quantidade": v.REVISION_QUANTITY_MESSAGE.format(executed="40")}


def test_revisao_com_termino_antes_do_inicio_do_pacote_e_recusada() -> None:
    erros = _erros(lambda: ajuste(revisao(termino="2026-01-04")))

    assert erros == {"termino": v.REVISION_FINISH_MESSAGE.format(start="05/01/2026")}


def test_revisao_com_peso_acima_do_maximo_e_recusada() -> None:
    erros = _erros(lambda: ajuste(revisao(peso="10.01")))

    assert erros == {"peso": v.REVISION_WEIGHT_MAX_MESSAGE.format(maximum="10")}


def test_revisao_com_peso_zero_e_recusada() -> None:
    assert _erros(lambda: ajuste(revisao(peso="0"))) == {"peso": v.PACKAGE_WEIGHT_ZERO_MESSAGE}


def test_revisao_de_pacote_inexistente_ou_de_subarea_e_recusada() -> None:
    inexistente = _erros(lambda: ajuste(revisao(pacote="9.9.9")))
    assert inexistente == {"pacote": v.REVISION_PACKAGE_NOT_FOUND_MESSAGE.format(code="9.9.9")}

    subarea = _erros(lambda: ajuste(revisao(pacote="2.1")))
    assert subarea == {"pacote": v.REVISION_PACKAGE_NOT_FOUND_MESSAGE.format(code="2.1")}


def test_soma_dos_pesos_fixos_abaixo_de_cem_ainda_deixa_peso() -> None:
    assert v.revision_fixed_weight_error(D("99.99")) is None
    assert v.revision_fixed_weight_error(D(0)) is None


def test_soma_dos_pesos_fixos_em_cem_ou_mais_fica_sem_peso() -> None:
    assert v.revision_fixed_weight_error(D(100)) == v.REVISION_FIXED_WEIGHT_MESSAGE
    assert v.revision_fixed_weight_error(D("100.01")) == v.REVISION_FIXED_WEIGHT_MESSAGE
