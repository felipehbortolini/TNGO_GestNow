"""Conversão do avanço por percentual e regressão (ISSUE-037).

O protótipo converte o % acumulado nas entradas do critério (``entradasPorPercentual``):
Etapas em sequência pelo peso, Unidades pela quantidade da linha de base, os marcos só nos
degraus e o Percentual estimado pelo próprio valor, com o arredondamento de 2 casas. O
acumulado regride quando o real depois fica abaixo do real antes.
"""

from __future__ import annotations

from decimal import Decimal

from src.modulos.planejamento import calculations as c

D = Decimal

ETAPAS = (
    c.EapStep("Elaboração", D(40), D(100)),
    c.EapStep("Emissão para comentários", D(30), D(50)),
    c.EapStep("Entrega na obra", D(30), D(0)),
)


def test_etapas_preenchem_em_sequencia_pelo_peso() -> None:
    converted = c.eap_entries_from_percent("Etapas", D(55), etapas=ETAPAS)

    assert converted.ok is True
    assert [step.pct for step in converted.etapas] == [D("100"), D("50"), D("0")]
    assert [step.name for step in converted.etapas] == [step.name for step in ETAPAS]
    assert c.eap_package_progress("Etapas", etapas=converted.etapas) == D("55.00")


def test_etapas_nas_fronteiras_zero_e_cem() -> None:
    zero = c.eap_entries_from_percent("Etapas", D(0), etapas=ETAPAS)
    full = c.eap_entries_from_percent("Etapas", D(100), etapas=ETAPAS)

    assert [step.pct for step in zero.etapas] == [D(0), D(0), D(0)]
    assert [step.pct for step in full.etapas] == [D(100), D(100), D(100)]


def test_etapa_de_peso_zero_fica_zerada() -> None:
    steps = (c.EapStep("Sem peso", D(0), D(50)), c.EapStep("Com peso", D(100), D(0)))

    converted = c.eap_entries_from_percent("Etapas", D(50), etapas=steps)

    assert [step.pct for step in converted.etapas] == [D(0), D("50")]


def test_unidades_convertem_pela_quantidade_da_linha_de_base() -> None:
    converted = c.eap_entries_from_percent("Unidades", D("12.5"), quantity=D(1400))

    assert converted.executed == D("175.00")
    assert c.eap_package_progress("Unidades", quantity=D(1400), executed=converted.executed) == D(
        "12.50"
    )


def test_unidades_sem_quantidade_medem_zero() -> None:
    converted = c.eap_entries_from_percent("Unidades", D(50))

    assert converted.executed == D("0.00")


def test_marco_zero_cem_so_aceita_os_degraus() -> None:
    assert c.eap_entries_from_percent("Marco 0/100", D(0)).state == c.MILESTONE_NOT_STARTED
    assert c.eap_entries_from_percent("Marco 0/100", D(100)).state == c.MILESTONE_DONE

    refused = c.eap_entries_from_percent("Marco 0/100", D(50))

    assert refused.ok is False
    assert refused.error == c.MILESTONE_0_100_OPTIONS_MESSAGE


def test_marco_cinquenta_cinquenta_so_aceita_os_degraus() -> None:
    assert c.eap_entries_from_percent("Marco 50/50", D(0)).state == c.MILESTONE_NOT_STARTED
    assert c.eap_entries_from_percent("Marco 50/50", D(50)).state == c.MILESTONE_STARTED
    assert c.eap_entries_from_percent("Marco 50/50", D(100)).state == c.MILESTONE_DONE

    refused = c.eap_entries_from_percent("Marco 50/50", D(25))

    assert refused.error == c.MILESTONE_50_50_OPTIONS_MESSAGE


def test_percentual_estimado_arredonda_com_duas_casas() -> None:
    converted = c.eap_entries_from_percent("Percentual estimado", D("12.345"))

    assert converted.estimated_pct == D("12.35")
    assert c.eap_package_progress(
        "Percentual estimado", estimated_pct=converted.estimated_pct
    ) == D("12.35")


def test_percentual_fora_da_faixa_nao_converte() -> None:
    for percent in (D(-1), D(101), None):
        converted = c.eap_entries_from_percent("Unidades", percent, quantity=D(10))
        assert converted.ok is False
        assert converted.error == c.EAP_PERCENT_RANGE_MESSAGE


def test_pacote_sem_criterio_nao_converte() -> None:
    converted = c.eap_entries_from_percent(None, D(50))

    assert converted.error == c.EAP_NO_CRITERION_MESSAGE


def test_regressao_compara_o_antes_com_o_depois() -> None:
    assert c.eap_progress_regression(D("55.00"), D("40.00")) is True
    assert c.eap_progress_regression(D("55.00"), D("55.00")) is False
    assert c.eap_progress_regression(D("40.00"), D("55.00")) is False
