"""Score, severidade, impacto, VME, exposição e numeração do Registro de riscos (ISSUE-064, D6).

As fórmulas são puras: a data de referência entra por argumento. Cada regra tem o caso comum e a
fronteira (o mínimo exato da faixa, o impacto igual ao pior caso, o sufixo não numérico).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.modulos.configuracoes.service import INITIAL_PARAMETERS
from src.modulos.riscos import calculations
from src.modulos.riscos.calculations import (
    Band,
    ProbabilityBand,
    Scale,
    parameters_from_values,
)

REFERENCIA = date(2026, 9, 25)

TIMENOW = Scale(
    name="Timenow",
    bands=(
        Band("baixo", "Baixo", 1),
        Band("moderado", "Moderado", 5),
        Band("alto", "Alto", 10),
        Band("critico", "Crítico", 15),
    ),
    life_risk_is_high=False,
)
CIPM = Scale(
    name="CIPM",
    bands=(Band("baixo", "Baixo", 1), Band("moderado", "Moderado", 8), Band("alto", "Alto", 16)),
    life_risk_is_high=True,
)
PROBABILIDADES = (
    ProbabilityBand(1, "Muito baixa", "até 10%", Decimal(5)),
    ProbabilityBand(2, "Baixa", "10 a 30%", Decimal(20)),
    ProbabilityBand(3, "Média", "30 a 50%", Decimal(40)),
    ProbabilityBand(4, "Alta", "50 a 70%", Decimal(60)),
    ProbabilityBand(5, "Muito alta", "acima de 70%", Decimal(85)),
)


def test_score_e_probabilidade_vezes_impacto() -> None:
    assert calculations.risk_score(3, 4) == 12
    assert calculations.risk_score(1, 1) == 1
    assert calculations.risk_score(5, 5) == 25


@pytest.mark.parametrize(
    ("score", "esperada"),
    [
        (1, "baixo"),
        (4, "baixo"),
        (5, "moderado"),
        (9, "moderado"),
        (10, "alto"),
        (14, "alto"),
        (15, "critico"),
        (25, "critico"),
    ],
)
def test_severidade_timenow_nas_fronteiras_das_quatro_faixas(score: int, esperada: str) -> None:
    assert calculations.risk_severity(score, TIMENOW).id == esperada


@pytest.mark.parametrize(
    ("score", "esperada"),
    [(1, "baixo"), (7, "baixo"), (8, "moderado"), (15, "moderado"), (16, "alto"), (25, "alto")],
)
def test_severidade_cipm_nas_fronteiras_das_tres_faixas(score: int, esperada: str) -> None:
    assert calculations.risk_severity(score, CIPM).id == esperada


def test_risco_a_vida_na_cipm_e_sempre_a_faixa_mais_alta() -> None:
    assert calculations.risk_severity(1, CIPM, life_risk=True).id == "alto"


def test_risco_a_vida_na_timenow_nao_muda_a_faixa() -> None:
    assert calculations.risk_severity(1, TIMENOW, life_risk=True).id == "baixo"


def test_posicao_da_faixa_e_o_critico_desconhecido_e_o_topo() -> None:
    assert calculations.severity_rank("baixo", TIMENOW) == 0
    assert calculations.severity_rank("critico", TIMENOW) == 3
    assert calculations.severity_rank("critico", CIPM) == 2
    assert calculations.severity_rank("inexistente", TIMENOW) == -1


def test_impacto_e_a_maior_dimensao() -> None:
    assert calculations.resulting_impact({"prazo": 2, "custo": 4, "sms": None, "legal": 3}) == 4
    assert calculations.resulting_impact({"prazo": None}) == 0
    assert calculations.resulting_impact({}) == 0


def test_impacto_pode_ser_elevado_mas_nao_reduzido() -> None:
    dimensoes = {"prazo": 2, "custo": 4}

    assert not calculations.is_impact_reduced(4, dimensoes)
    assert not calculations.is_impact_reduced(5, dimensoes)
    assert calculations.is_impact_reduced(3, dimensoes)


def test_vme_e_a_media_da_faixa_vezes_o_custo_em_centavos() -> None:
    assert calculations.expected_monetary_value(3, 185_000_000, PROBABILIDADES) == 74_000_000
    assert calculations.expected_monetary_value(5, 100_000_000, PROBABILIDADES) == 85_000_000


def test_vme_arredonda_meio_para_cima_e_zera_sem_faixa_ou_custo() -> None:
    assert calculations.expected_monetary_value(1, 10, PROBABILIDADES) == 1
    assert calculations.expected_monetary_value(3, 0, PROBABILIDADES) == 0
    assert calculations.expected_monetary_value(9, 100, PROBABILIDADES) == 0


def test_exposicao_soma_so_as_ameacas() -> None:
    itens = [("Ameaça", 100), ("Oportunidade", 900), ("Ameaça", 50)]

    assert calculations.threat_exposure(itens) == 150
    assert calculations.threat_exposure([("Oportunidade", 10)]) == 0
    assert calculations.threat_exposure([]) == 0


def test_cadencia_da_revisao_usa_o_maior_prazo_quando_a_faixa_nao_tem_valor() -> None:
    cadencia = {"critico": 15, "alto": 30, "baixo": 90}

    assert calculations.review_cadence("critico", cadencia) == 15
    assert calculations.review_cadence("moderado", cadencia) == 90


def test_risco_ativo_ate_materializar_ou_encerrar() -> None:
    assert calculations.is_active("Em análise")
    assert not calculations.is_active("Materializado")
    assert not calculations.is_active("Encerrado")


def test_revisao_vencida_so_para_ativo_e_antes_da_referencia() -> None:
    ontem = REFERENCIA - timedelta(days=1)

    assert calculations.is_review_overdue(ontem, REFERENCIA, active=True)
    assert not calculations.is_review_overdue(REFERENCIA, REFERENCIA, active=True)
    assert not calculations.is_review_overdue(ontem, REFERENCIA, active=False)
    assert not calculations.is_review_overdue(None, REFERENCIA, active=True)


def test_dias_ate_a_revisao_pode_ser_negativo() -> None:
    assert calculations.days_until(REFERENCIA + timedelta(days=3), REFERENCIA) == 3
    assert calculations.days_until(REFERENCIA - timedelta(days=2), REFERENCIA) == -2
    assert calculations.days_until(None, REFERENCIA) is None


def test_residual_de_ameaca_nao_passa_da_inerente() -> None:
    assert calculations.residual_exceeds_inherent("Ameaça", 12, 10)
    assert not calculations.residual_exceeds_inherent("Ameaça", 10, 10)
    assert not calculations.residual_exceeds_inherent("Oportunidade", 12, 10)
    assert not calculations.residual_exceeds_inherent("Ameaça", 12, None)


def test_justificativa_so_quando_o_score_difere_da_avaliacao_anterior() -> None:
    assert not calculations.justification_required(None, 12)
    assert not calculations.justification_required(12, 12)
    assert calculations.justification_required(12, 8)


def test_revisao_proxima_inclui_hoje_e_o_ultimo_dia_do_alerta() -> None:
    kwargs = {"active": True, "alert_days": 15}
    limite = REFERENCIA + timedelta(days=15)

    assert calculations.is_review_due_soon(REFERENCIA, REFERENCIA, **kwargs)
    assert calculations.is_review_due_soon(limite, REFERENCIA, **kwargs)
    assert not calculations.is_review_due_soon(limite + timedelta(days=1), REFERENCIA, **kwargs)
    assert not calculations.is_review_due_soon(REFERENCIA - timedelta(days=1), REFERENCIA, **kwargs)


def test_numeracao_ignora_sufixos_nao_numericos() -> None:
    codigos = ["RSK-TN-2026-0003", "RSK-TN-2026-SE-0009", "RSK-TN-2026-ABC", "RSK-TN-2026-0007"]

    assert calculations.next_code_number(codigos, "RSK-TN-2026") == 8


def test_numeracao_sem_codigos_comeca_em_um() -> None:
    assert calculations.next_code_number([], "RSK-TN-2026") == 1
    assert calculations.next_code_number(["RSK-TN-2026-SE-0009"], "RSK-TN-2026") == 1


def test_codigo_formatado_com_quatro_digitos() -> None:
    assert calculations.format_code("RSK-TN-2026", 10) == "RSK-TN-2026-0010"


def test_parametros_padrao_dao_as_duas_escalas() -> None:
    padrao = parameters_from_values(INITIAL_PARAMETERS["riscos"])
    cipm = parameters_from_values({**INITIAL_PARAMETERS["riscos"], "escalaAtiva": "cipm"})

    assert [faixa.id for faixa in padrao.scale.bands] == ["baixo", "moderado", "alto", "critico"]
    assert [faixa.id for faixa in cipm.scale.bands] == ["baixo", "moderado", "alto"]
    assert cipm.scale.life_risk_is_high
    assert padrao.review_alert_days == 15
