"""Cálculos puros do Registro de riscos (ISSUE-064, D6): score, severidade, VME e numeração.

Score e severidade nas duas escalas (Timenow de 4 faixas e CIPM de 3), o risco à vida sempre na
faixa mais alta na CIPM, o impacto pelo pior caso — elevado, nunca reduzido —, o VME em centavos
e a exposição que soma só as ameaças. Nada aqui lê o relógio nem o banco.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.modulos.configuracoes import service as configuracoes
from src.modulos.riscos import calculations
from src.modulos.riscos.calculations import (
    Band,
    Scale,
    days_until,
    expected_monetary_value,
    format_code,
    is_impact_reduced,
    is_review_due_soon,
    is_review_overdue,
    justification_required,
    next_code_number,
    parameters_from_values,
    probability_mean_pct,
    residual_exceeds_inherent,
    resulting_impact,
    review_cadence,
    risk_score,
    risk_severity,
    severity_rank,
    threat_exposure,
)

TIMENOW = Scale(
    name="Timenow (4 faixas)",
    bands=(
        Band("baixo", "Baixo", 1),
        Band("moderado", "Moderado", 5),
        Band("alto", "Alto", 10),
        Band("critico", "Crítico", 15),
    ),
    life_risk_is_high=False,
)
CIPM = Scale(
    name="CIPM ArcelorMittal (3 faixas)",
    bands=(Band("baixo", "Baixo", 1), Band("moderado", "Moderado", 8), Band("alto", "Alto", 16)),
    life_risk_is_high=True,
)
REFERENCIA = date(2026, 9, 25)


@pytest.fixture
def parametros() -> calculations.RiskParameters:
    """O grupo Riscos dos parâmetros iniciais, como o servidor o lê."""
    return parameters_from_values(configuracoes.INITIAL_PARAMETERS["riscos"])


# ── Score e severidade ───────────────────────────────────────────────────────────────────────


def test_score_e_probabilidade_vezes_impacto() -> None:
    assert risk_score(1, 1) == 1
    assert risk_score(3, 4) == 12
    assert risk_score(5, 5) == 25


@pytest.mark.parametrize(
    ("score", "faixa"),
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
def test_severidade_na_escala_timenow(score: int, faixa: str) -> None:
    assert risk_severity(score, TIMENOW).id == faixa


@pytest.mark.parametrize(
    ("score", "faixa"),
    [(1, "baixo"), (7, "baixo"), (8, "moderado"), (15, "moderado"), (16, "alto"), (25, "alto")],
)
def test_severidade_na_escala_cipm(score: int, faixa: str) -> None:
    assert risk_severity(score, CIPM).id == faixa


def test_risco_a_vida_na_cipm_e_sempre_a_faixa_mais_alta() -> None:
    assert risk_severity(1, CIPM, life_risk=True).id == "alto"
    assert risk_severity(25, CIPM, life_risk=True).id == "alto"


def test_risco_a_vida_nao_muda_a_faixa_na_escala_timenow() -> None:
    assert risk_severity(3, TIMENOW, life_risk=True).id == "baixo"


def test_posicao_da_faixa_na_escala() -> None:
    assert severity_rank("baixo", TIMENOW) == 0
    assert severity_rank("critico", TIMENOW) == 3
    assert severity_rank("critico", CIPM) == 2  # não existe na CIPM: vale a mais alta
    assert severity_rank("moderado", CIPM) == 1


# ── Impacto pelo pior caso ───────────────────────────────────────────────────────────────────


def test_impacto_resultante_e_a_maior_dimensao() -> None:
    dimensoes = {"prazo": 4, "custo": 3, "escopo": None, "sms": 2, "imagem": None, "legal": None}
    assert resulting_impact(dimensoes) == 4


def test_impacto_resultante_sem_dimensao_avaliada_e_zero() -> None:
    assert resulting_impact({}) == 0
    assert resulting_impact({"prazo": None, "custo": None}) == 0


def test_impacto_abaixo_do_pior_caso_e_reducao() -> None:
    dimensoes = {"prazo": 4}

    assert is_impact_reduced(3, dimensoes)
    assert not is_impact_reduced(4, dimensoes)
    assert not is_impact_reduced(5, dimensoes)


# ── VME e exposição ──────────────────────────────────────────────────────────────────────────


def test_probabilidade_media_vem_da_faixa(
    parametros: calculations.RiskParameters,
) -> None:
    assert probability_mean_pct(3, parametros.probabilities) == Decimal(40)
    assert probability_mean_pct(5, parametros.probabilities) == Decimal(85)
    assert probability_mean_pct(7, parametros.probabilities) is None


def test_vme_e_probabilidade_media_vezes_o_custo_em_centavos(
    parametros: calculations.RiskParameters,
) -> None:
    # P3 = 40%; 40% de R$ 340.000,00 = R$ 136.000,00.
    vme = expected_monetary_value(3, 34_000_000, parametros.probabilities)

    assert vme == 13_600_000


def test_vme_sobe_o_meio_centavo(parametros: calculations.RiskParameters) -> None:
    # P1 = 5%; 5% de 15 centavos = 0,75 centavo: 1.
    assert expected_monetary_value(1, 15, parametros.probabilities) == 1


def test_vme_sem_custo_e_zero(parametros: calculations.RiskParameters) -> None:
    assert expected_monetary_value(3, 0, parametros.probabilities) == 0


def test_exposicao_soma_so_as_ameacas() -> None:
    itens = [("Ameaça", 10_000_000), ("Oportunidade", 5_000_000), ("Ameaça", 2_000_000)]

    assert threat_exposure(itens) == 12_000_000
    assert threat_exposure([]) == 0


# ── Cadência e revisão ───────────────────────────────────────────────────────────────────────


def test_cadencia_vem_da_faixa_e_a_maior_na_falta() -> None:
    cadencia = {"critico": 15, "alto": 30, "moderado": 60, "baixo": 90}

    assert review_cadence("critico", cadencia) == 15
    assert review_cadence("desconhecido", cadencia) == 90


def test_revisao_vencida_e_proxima_do_alerta() -> None:
    assert is_review_overdue(date(2026, 9, 24), REFERENCIA, active=True)
    assert not is_review_overdue(REFERENCIA, REFERENCIA, active=True)
    assert not is_review_overdue(REFERENCIA, REFERENCIA, active=False)
    assert not is_review_overdue(None, REFERENCIA, active=True)

    assert is_review_due_soon(REFERENCIA, REFERENCIA, active=True, alert_days=15)
    assert is_review_due_soon(date(2026, 10, 10), REFERENCIA, active=True, alert_days=15)
    assert not is_review_due_soon(date(2026, 10, 11), REFERENCIA, active=True, alert_days=15)
    assert is_review_due_soon(REFERENCIA, REFERENCIA, active=True, alert_days=0)


def test_dias_ate_a_revisao() -> None:
    assert days_until(REFERENCIA, REFERENCIA) == 0
    assert days_until(date(2026, 9, 30), REFERENCIA) == 5
    assert days_until(date(2026, 9, 20), REFERENCIA) == -5
    assert days_until(None, REFERENCIA) is None


# ── Regras que precisam do histórico ─────────────────────────────────────────────────────────


def test_justificativa_obrigatoria_quando_o_score_muda() -> None:
    assert justification_required(12, 16)
    assert not justification_required(12, 12)
    assert not justification_required(None, 16)  # primeira avaliação


def test_residual_acima_do_inerente_so_e_proibido_para_ameaca() -> None:
    assert residual_exceeds_inherent("Ameaça", 20, 12)
    assert not residual_exceeds_inherent("Ameaça", 12, 12)
    assert not residual_exceeds_inherent("Oportunidade", 20, 12)
    assert not residual_exceeds_inherent("Ameaça", 20, None)


# ── Numeração ────────────────────────────────────────────────────────────────────────────────


def test_a_numeracao_ignora_sufixos_nao_numericos() -> None:
    codigos = ["RSK-TN-2026-0001", "RSK-TN-2026-0009", "RSK-TN-2026-SE-0012", "RSK-TN-2025-0099"]

    assert next_code_number(codigos, "RSK-TN-2026") == 10


def test_a_numeracao_comeca_em_um_sem_codigo_numerico() -> None:
    assert next_code_number([], "RSK") == 1
    assert next_code_number(["RSK-SE-0007"], "RSK") == 1


def test_o_codigo_sai_com_quatro_digitos() -> None:
    assert format_code("RSK-TN-2026", 1) == "RSK-TN-2026-0001"
    assert format_code("RSK", 12345) == "RSK-12345"
