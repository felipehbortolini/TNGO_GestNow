"""Cálculos puros da matriz e do painel de riscos (ISSUE-066, D6).

O teto de cada faixa, a reconstrução mensal do score residual a partir do histórico (sem série
gravada) e cada regra da pauta de escalonamento com a data injetada. Nada aqui lê o relógio nem o
banco.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.modulos.configuracoes import service as configuracoes
from src.modulos.riscos import calculations
from src.modulos.riscos.calculations import (
    Band,
    MonthWindow,
    RiskHistory,
    Scale,
    ScoredEvent,
    band_ceiling,
    is_active_on,
    monthly_residual_scores,
    pauta_reasons,
    score_at,
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


@pytest.fixture
def parametros() -> calculations.RiskParameters:
    """O grupo Riscos dos parâmetros iniciais, como o servidor o lê."""
    return calculations.parameters_from_values(configuracoes.INITIAL_PARAMETERS["riscos"])


def _window(label: str, end: date) -> MonthWindow:
    return MonthWindow(label=label, end=end)


def _history(
    identified_on: date,
    events: tuple[ScoredEvent, ...],
    *,
    closed_on: date | None = None,
) -> RiskHistory:
    return RiskHistory(identified_on=identified_on, closed_on=closed_on, events=events)


def _facts(
    *,
    active: bool = True,
    situation: str = "Em tratamento",
    nature: str = calculations.THREAT,
    inherent_band_id: str | None = "alto",
    current_band_id: str | None = "alto",
    inherent_score: int | None = 12,
    residual_score: int | None = 8,
    has_plan: bool = True,
    plan_pending: bool = False,
    target_band_id: str | None = "moderado",
    days_to_target: int | None = 45,
    review_overdue: bool = False,
    trigger_on: date | None = None,
) -> calculations.PautaFacts:
    """Os fatos da pauta com um risco típico: ameaça com plano, alvo moderado e prazo distante."""
    return calculations.PautaFacts(
        active=active,
        situation=situation,
        nature=nature,
        inherent_band_id=inherent_band_id,
        current_band_id=current_band_id,
        inherent_score=inherent_score,
        residual_score=residual_score,
        has_plan=has_plan,
        plan_pending=plan_pending,
        target_band_id=target_band_id,
        days_to_target=days_to_target,
        review_overdue=review_overdue,
        trigger_on=trigger_on,
    )


# ── Teto da faixa ────────────────────────────────────────────────────────────────────────────


def test_o_teto_da_faixa_e_o_piso_da_seguinte_menos_um() -> None:
    assert band_ceiling(Band("baixo", "Baixo", 1), TIMENOW) == 4
    assert band_ceiling(Band("moderado", "Moderado", 5), TIMENOW) == 9
    assert band_ceiling(Band("alto", "Alto", 10), TIMENOW) == 14
    assert band_ceiling(Band("critico", "Crítico", 15), TIMENOW) == 25
    assert band_ceiling(Band("moderado", "Moderado", 8), CIPM) == 15


# ── Evolução mensal reconstruída ─────────────────────────────────────────────────────────────


def test_o_score_no_mes_e_o_evento_mais_novo_ate_a_data() -> None:
    history = _history(
        date(2026, 1, 10),
        (
            ScoredEvent(date(2026, 1, 10), 12, residual=False),
            ScoredEvent(date(2026, 3, 15), 6, residual=True),
        ),
    )

    assert score_at(history, date(2026, 1, 31)) == 12
    assert score_at(history, date(2026, 2, 28)) == 12
    assert score_at(history, date(2026, 3, 31)) == 6
    assert score_at(history, date(2026, 1, 9)) is None


def test_o_residual_vence_o_empate_com_o_inerente_no_mesmo_dia() -> None:
    history = _history(
        date(2026, 4, 1),
        (
            ScoredEvent(date(2026, 4, 10), 20, residual=False),
            ScoredEvent(date(2026, 4, 10), 8, residual=True),
        ),
    )

    assert score_at(history, date(2026, 4, 30)) == 8


def test_risco_fechado_conta_ate_o_mes_do_encerramento() -> None:
    history = _history(
        date(2026, 4, 5),
        (ScoredEvent(date(2026, 4, 5), 9, residual=False),),
        closed_on=date(2026, 6, 20),
    )

    assert is_active_on(history, date(2026, 6, 19))
    assert not is_active_on(history, date(2026, 6, 20))
    assert not is_active_on(history, date(2026, 7, 31))


def test_a_evolucao_mensal_soma_os_riscos_ativos_de_cada_mes() -> None:
    primeira = _history(
        date(2026, 1, 10),
        (
            ScoredEvent(date(2026, 1, 10), 6, residual=False),
            ScoredEvent(date(2026, 3, 15), 4, residual=True),
        ),
    )
    segunda = _history(
        date(2026, 4, 5),
        (ScoredEvent(date(2026, 4, 5), 9, residual=False),),
        closed_on=date(2026, 6, 20),
    )
    terceira = _history(
        date(2026, 7, 1),
        (ScoredEvent(date(2026, 7, 1), 12, residual=False),),
    )
    windows = (
        _window("2026-01", date(2026, 1, 31)),
        _window("2026-02", date(2026, 2, 28)),
        _window("2026-03", date(2026, 3, 31)),
        _window("2026-04", date(2026, 4, 30)),
        _window("2026-05", date(2026, 5, 31)),
        _window("2026-06", date(2026, 6, 30)),
        _window("2026-07", date(2026, 7, 31)),
        _window("2026-08", date(2026, 8, 31)),
    )

    scores = monthly_residual_scores((primeira, segunda, terceira), windows)

    assert [(item.month, item.score) for item in scores] == [
        ("2026-01", 6),
        ("2026-02", 6),
        ("2026-03", 4),
        ("2026-04", 13),
        ("2026-05", 13),
        ("2026-06", 4),
        ("2026-07", 16),
        ("2026-08", 16),
    ]


def test_risco_sem_avaliacao_ate_o_mes_nao_entra_na_evolucao() -> None:
    history = _history(date(2026, 4, 10), (ScoredEvent(date(2026, 5, 5), 8, residual=False),))

    scores = monthly_residual_scores(
        (history,), (_window("2026-04", date(2026, 4, 30)), _window("2026-05", date(2026, 5, 31)))
    )

    assert [item.score for item in scores] == [0, 8]


# ── Pauta de escalonamento: cada regra com a data injetada ───────────────────────────────────


def test_identificado_sem_avaliacao_entra_na_pauta(parametros: calculations.RiskParameters) -> None:
    reasons = pauta_reasons(
        _facts(
            situation="Identificado",
            inherent_band_id=None,
            current_band_id=None,
            inherent_score=None,
            residual_score=None,
            has_plan=False,
            target_band_id=None,
            days_to_target=None,
        ),
        parametros,
    )

    assert reasons == ("Identificado sem avaliação",)


def test_faixa_mais_alta_sem_plano_entra_na_pauta(
    parametros: calculations.RiskParameters,
) -> None:
    reasons = pauta_reasons(
        _facts(
            has_plan=False,
            current_band_id="critico",
            residual_score=None,
            target_band_id=None,
            days_to_target=None,
        ),
        parametros,
    )

    assert reasons == ("Crítico sem plano de resposta",)


def test_acima_do_alvo_a_menos_de_trinta_dias_entra_na_pauta(
    parametros: calculations.RiskParameters,
) -> None:
    reasons = pauta_reasons(_facts(days_to_target=30), parametros)

    assert reasons == ("Acima da severidade-alvo (Moderado) a 30 dias do prazo",)


def test_acima_do_alvo_com_prazo_vencido_entra_na_pauta(
    parametros: calculations.RiskParameters,
) -> None:
    reasons = pauta_reasons(_facts(days_to_target=-4), parametros)

    assert reasons == ("Acima da severidade-alvo (Moderado) com prazo vencido há 4 dias",)


def test_oportunidade_abaixo_do_alvo_entra_na_pauta(
    parametros: calculations.RiskParameters,
) -> None:
    reasons = pauta_reasons(
        _facts(nature=calculations.OPPORTUNITY, current_band_id="baixo", days_to_target=10),
        parametros,
    )

    assert reasons == ("Abaixo da severidade-alvo (Moderado) a 10 dias do prazo",)


def test_alvo_longe_do_prazo_nao_entra_na_pauta(parametros: calculations.RiskParameters) -> None:
    assert pauta_reasons(_facts(days_to_target=31), parametros) == ()


def test_sem_reducao_apos_o_plano_entra_na_pauta(
    parametros: calculations.RiskParameters,
) -> None:
    reasons = pauta_reasons(_facts(residual_score=12, days_to_target=45), parametros)

    assert reasons == ("Sem redução após o plano",)


def test_plano_aguardando_aprovacao_entra_na_pauta(
    parametros: calculations.RiskParameters,
) -> None:
    reasons = pauta_reasons(_facts(plan_pending=True, days_to_target=45), parametros)

    assert reasons == ("Plano aguardando aprovação",)


def test_revisao_vencida_entra_na_pauta(parametros: calculations.RiskParameters) -> None:
    reasons = pauta_reasons(_facts(review_overdue=True, days_to_target=45), parametros)

    assert reasons == ("Revisão vencida",)


def test_gatilho_ocorrido_entra_na_pauta_com_a_data(
    parametros: calculations.RiskParameters,
) -> None:
    reasons = pauta_reasons(_facts(trigger_on=date(2026, 9, 1), days_to_target=45), parametros)

    assert reasons == ("Gatilho ocorrido em 01/09/2026",)


def test_risco_encerrado_nao_entra_na_pauta(parametros: calculations.RiskParameters) -> None:
    assert pauta_reasons(_facts(active=False), parametros) == ()
