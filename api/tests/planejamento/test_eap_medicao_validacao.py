"""Validação do registro do avanço e da importação (ISSUE-037).

O formulário manda texto; a validação devolve o dado tipado ou a mensagem de cada campo
errado. O estorno exige papel Gestor e justificativa de 10 caracteres; o executado não passa
a quantidade da linha de base; o percentual estimado só vale até o peso do parâmetro. A
importação recusa cada linha com o motivo e ignora a linha sem mudança.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.core.errors import AccessDeniedError, InvalidDataError
from src.modulos.planejamento import calculations as c
from src.modulos.planejamento import validation as v
from src.modulos.planejamento.calculations import EapStep

D = Decimal
HOJE = date(2026, 9, 25)

ETAPAS = (
    EapStep("Elaboração", D(40), D(100)),
    EapStep("Emissão para comentários", D(30), D(50)),
    EapStep("Entrega na obra", D(30), D(0)),
)


def pacote_etapas(*, current: str = "55.00") -> v.ProgressPackage:
    return v.ProgressPackage(
        kind="Trabalho",
        criterion="Etapas",
        weight=D("2.00"),
        current=D(current),
        steps=ETAPAS,
    )


def pacote_unidades(*, current: str = "50.00") -> v.ProgressPackage:
    return v.ProgressPackage(
        kind="Trabalho",
        criterion="Unidades",
        weight=D("1.00"),
        current=D(current),
        quantity=D(1400),
        unit="m",
    )


def pacote_estimado(weight: str) -> v.ProgressPackage:
    return v.ProgressPackage(
        kind="Trabalho",
        criterion="Percentual estimado",
        weight=D(weight),
        current=D("10.00"),
    )


def registrar(
    raw: dict[str, str], package: v.ProgressPackage, *, is_manager: bool = False
) -> v.ProgressData:
    return v.parse_progress_form(
        raw,
        package,
        reference_date=HOJE,
        is_manager=is_manager,
        max_estimated_weight=D(5),
    )


def _erros(chamada: object) -> dict[str, str]:
    with pytest.raises(InvalidDataError) as erro:
        chamada()  # type: ignore[operator]
    assert isinstance(erro.value.detail, dict)
    return erro.value.detail


def _mensagem(chamada: object) -> str:
    with pytest.raises(InvalidDataError) as erro:
        chamada()  # type: ignore[operator]
    return str(erro.value)


def test_formulario_de_etapas_vira_medicao_tipada() -> None:
    raw = {
        "data": "2026-09-20",
        "etapa0": "100",
        "etapa1": "50",
        "etapa2": "0",
        "obs": "Boletim de medição de setembro",
    }

    dado = registrar(raw, pacote_etapas())

    assert dado.measured_on == date(2026, 9, 20)
    assert (dado.from_pct, dado.to_pct) == (D("55.00"), D("55.00"))
    assert [step.pct for step in dado.entries.steps] == [D(100), D(50), D(0)]
    assert dado.note == "Boletim de medição de setembro"


def test_etapa_fora_da_faixa_e_recusada() -> None:
    raw = {"data": "2026-09-20", "etapa0": "150"}

    erros = _erros(lambda: registrar(raw, pacote_etapas()))

    assert erros == {"etapa0": v.STEP_PCT_RANGE_MESSAGE}


def test_data_da_medicao_e_obrigatoria_e_nao_pode_ser_futura() -> None:
    sem_data = {"etapa0": "100", "etapa1": "50", "etapa2": "0"}
    assert _erros(lambda: registrar(sem_data, pacote_etapas())) == {
        "data": v.MEASUREMENT_DATE_REQUIRED_MESSAGE
    }

    futura = dict(sem_data, data="2026-09-26")
    assert _erros(lambda: registrar(futura, pacote_etapas())) == {
        "data": v.MEASUREMENT_DATE_FUTURE_MESSAGE
    }


def test_unidades_recusam_executado_ausente_negativo_ou_invalido() -> None:
    for text in ("", "-1", "abc"):
        raw = {"data": "2026-09-20", "executado": text}
        assert _erros(lambda raw=raw: registrar(raw, pacote_unidades())) == {
            "executado": v.EXECUTED_REQUIRED_MESSAGE
        }


def test_executado_acima_da_linha_de_base_pede_sm() -> None:
    raw = {"data": "2026-09-20", "executado": "1500"}

    erros = _erros(lambda: registrar(raw, pacote_unidades()))

    assert erros == {
        "executado": v.EXECUTED_OVER_QUANTITY_MESSAGE.format(quantity="1400", unit="m")
    }


def test_marco_fora_dos_degraus_e_recusado() -> None:
    package = v.ProgressPackage(kind="Trabalho", criterion="Marco 50/50", weight=D(1), current=D(0))
    raw = {"data": "2026-09-20", "estado": "Meio"}

    assert _erros(lambda: registrar(raw, package)) == {"estado": v.MILESTONE_STATE_MESSAGE}


def test_estimado_fora_da_faixa_e_recusado() -> None:
    raw = {"data": "2026-09-20", "estimadoPct": "150"}

    assert _erros(lambda: registrar(raw, pacote_estimado("1"))) == {
        "estimadoPct": v.ESTIMATED_PCT_RANGE_MESSAGE
    }


def test_estimado_acima_do_peso_do_parametro_e_recusado() -> None:
    raw = {"data": "2026-09-20", "estimadoPct": "50"}

    erros = _erros(lambda: registrar(raw, pacote_estimado("6")))

    assert erros == {"estimadoPct": v.ESTIMATED_WEIGHT_MESSAGE.format(maximum="5")}


def test_estimado_no_limite_do_peso_do_parametro_e_aceito() -> None:
    raw = {"data": "2026-09-20", "estimadoPct": "60"}

    dado = registrar(raw, pacote_estimado("5"))

    assert (dado.from_pct, dado.to_pct) == (D("10.00"), D("60.00"))


def test_pacote_sem_criterio_e_recusado() -> None:
    package = v.ProgressPackage(kind="Trabalho", criterion=None, weight=D(1), current=D(0))

    assert _mensagem(lambda: registrar({"data": "2026-09-20"}, package)) == (
        c.EAP_NO_CRITERION_MESSAGE
    )


def test_regressao_sem_gestor_e_recusada() -> None:
    raw = {"data": "2026-09-20", "etapa0": "0", "etapa1": "0", "etapa2": "0"}

    with pytest.raises(AccessDeniedError) as erro:
        registrar(raw, pacote_etapas())

    assert str(erro.value) == v.REVERSAL_MANAGER_MESSAGE


def test_regressao_com_gestor_exige_justificativa() -> None:
    raw = {
        "data": "2026-09-20",
        "etapa0": "0",
        "etapa1": "0",
        "etapa2": "0",
        "justificativa": "curta",
    }

    erros = _erros(lambda: registrar(raw, pacote_etapas(), is_manager=True))

    assert erros == {
        "justificativa": v.REVERSAL_JUSTIFICATION_MESSAGE.format(from_pct="55", to_pct="0")
    }


def test_estorno_justificado_por_gestor_vira_medicao() -> None:
    raw = {
        "data": "2026-09-20",
        "etapa0": "0",
        "etapa1": "0",
        "etapa2": "0",
        "justificativa": "Retrabalho do moinho refeito",
    }

    dado = registrar(raw, pacote_etapas(), is_manager=True)

    assert (dado.from_pct, dado.to_pct) == (D("55.00"), D("0.00"))
    assert dado.note == "Retrabalho do moinho refeito"


def test_importacao_aceita_linhas_validas() -> None:
    packages = {"2.1.1": pacote_etapas(), "3.1.1": pacote_unidades()}

    results = v.parse_import_rows(
        (
            v.ImportRowInput(code="2.1.1", percent=D(70)),
            v.ImportRowInput(code="3.1.1", executed=D(1050)),
            v.ImportRowInput(code="3.1.1", percent=D(100)),
        ),
        packages,
    )

    etapas, por_quantidade, por_percentual = results
    assert (etapas.from_pct, etapas.to_pct) == (D("55.00"), D("70.00"))
    assert [step.pct for step in etapas.entries.steps] == [D(100), D(100), D(0)]
    assert (por_quantidade.from_pct, por_quantidade.to_pct) == (D("50.00"), D("75.00"))
    assert por_quantidade.entries.executed == D(1050)
    assert (por_percentual.from_pct, por_percentual.to_pct) == (D("50.00"), D("100.00"))
    assert por_percentual.entries.executed == D(1400)


def test_importacao_recusa_pacote_inexistente_e_de_planejamento() -> None:
    packages = {
        "4.1.1": v.ProgressPackage(kind="Planejamento", criterion=None, weight=D(2), current=D(0))
    }

    inexistente, planejamento = v.parse_import_rows(
        (
            v.ImportRowInput(code="9.9.9", percent=D(50)),
            v.ImportRowInput(code="4.1.1", percent=D(50)),
        ),
        packages,
    )

    assert inexistente.error == v.IMPORT_PACKAGE_NOT_FOUND_MESSAGE.format(code="9.9.9")
    assert planejamento.error == v.IMPORT_PLANNING_MESSAGE.format(code="4.1.1")


def test_importacao_recusa_marco_fora_dos_degraus() -> None:
    packages = {
        "5.1.1": v.ProgressPackage(
            kind="Trabalho", criterion="Marco 0/100", weight=D(2), current=D(0)
        )
    }

    result = v.parse_import_rows((v.ImportRowInput(code="5.1.1", percent=D(50)),), packages)[0]

    assert result.error == f"5.1.1: {c.MILESTONE_0_100_OPTIONS_MESSAGE}"


def test_importacao_recusa_linha_que_regride() -> None:
    packages = {"2.1.1": pacote_etapas()}

    result = v.parse_import_rows((v.ImportRowInput(code="2.1.1", percent=D(40)),), packages)[0]

    assert result.error == v.IMPORT_REGRESSION_MESSAGE.format(
        code="2.1.1", from_pct="55", to_pct="40"
    )


def test_importacao_ignora_linha_sem_mudanca() -> None:
    packages = {"2.1.1": pacote_etapas()}

    result = v.parse_import_rows((v.ImportRowInput(code="2.1.1", percent=D(55)),), packages)[0]

    assert result.error == ""
    assert result.entries is None


def test_importacao_recusa_executado_acima_da_quantidade() -> None:
    packages = {"3.1.1": pacote_unidades()}

    result = v.parse_import_rows((v.ImportRowInput(code="3.1.1", executed=D(1500)),), packages)[0]

    assert result.error == (
        "3.1.1: " + v.EXECUTED_OVER_QUANTITY_MESSAGE.format(quantity="1400", unit="m")
    )


def test_importacao_recusa_percentual_ausente() -> None:
    packages = {"2.1.1": pacote_etapas()}

    result = v.parse_import_rows((v.ImportRowInput(code="2.1.1"),), packages)[0]

    assert result.error == f"2.1.1: {c.EAP_PERCENT_RANGE_MESSAGE}"
