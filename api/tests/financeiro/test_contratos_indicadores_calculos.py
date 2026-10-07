"""Cálculos dos indicadores da administração contratual (ISSUE-035).

Os dez indicadores do protótipo são funções puras sobre fatos, com a data de referência injetada:
exposição de claims por direção, taxa de reconhecimento, tempo médio de resolução, notificações
fora do prazo, dias solicitados x concedidos, extensão de prazo acumulada, aprovado não faturado,
pago x previsto, marcos atrasados e desempenho das contratadas (nota média e C ou D). As fronteiras
cobertas são o ``None`` sem base, o arredondamento meio para cima, os claims abertos contra os
encerrados, a direção do claim e o marco na própria data de referência.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from src.modulos.financeiro import calculations

D = Decimal
REF = date(2026, 9, 25)
ONE_DAY = timedelta(days=1)
MOCK_WEIGHTS = {
    "hse": 25,
    "qualidade": 20,
    "prazo": 20,
    "gestao": 15,
    "recursos": 10,
    "documentacao": 10,
}


def _claim(**overrides: object) -> calculations.ClaimFact:
    """Um claim de teste: a contratada em análise, notificada nove dias após o evento."""
    fields: dict[str, object] = {
        "direction": calculations.CLAIM_DIRECTION_CONTRACTOR,
        "situation": calculations.CLAIM_UNDER_REVIEW,
        "claimed_cents": 10_000_000,
        "event_date": date(2026, 8, 1),
        "notification_date": date(2026, 8, 10),
        "notice_days": 30,
    }
    fields.update(overrides)
    return calculations.ClaimFact(**fields)


def _milestone(**overrides: object) -> calculations.MilestoneFact:
    """Um marco de teste: um previsto de R$ 100 mil com data prevista em setembro."""
    fields: dict[str, object] = {
        "value_cents": 10_000_000,
        "expected_on": date(2026, 9, 1),
        "situation": calculations.MILESTONE_FORECAST,
    }
    fields.update(overrides)
    return calculations.MilestoneFact(**fields)


def _evaluation(notes: dict[str, int]) -> calculations.EvaluationFact:
    """Uma avaliação de teste com os pesos do grupo inicial de ``avaliacaoContratada``."""
    return calculations.EvaluationFact(period=date(2026, 9, 1), notes=notes, weights=MOCK_WEIGHTS)


# ── Exposição por direção ────────────────────────────────────────────────


def test_exposicao_por_direcao_soma_so_os_claims_abertos_de_cada_direcao() -> None:
    claims = (
        _claim(claimed_cents=18_500_000, situation=calculations.CLAIM_IN_NEGOTIATION),
        _claim(claimed_cents=42_000_000, situation=calculations.CLAIM_UNDER_REVIEW),
        _claim(claimed_cents=2_000_000, direction=calculations.CLAIM_DIRECTION_CLIENT),
        _claim(
            claimed_cents=52_000_000,
            situation=calculations.CLAIM_CLOSED,
            recognized_cents=40_000_000,
            closed_on=date(2026, 7, 10),
        ),
        _claim(
            claimed_cents=3_400_000,
            direction=calculations.CLAIM_DIRECTION_CLIENT,
            situation=calculations.CLAIM_AGREED,
            recognized_cents=3_400_000,
            closed_on=date(2026, 9, 9),
        ),
    )

    exposure = calculations.exposure_by_direction(claims)

    assert exposure.contractor_cents == 60_500_000
    assert exposure.client_cents == 2_000_000
    assert calculations.open_claim_count(claims) == 3


def test_exposicao_de_uma_direcao_ignora_os_encerrados() -> None:
    claims = (
        _claim(claimed_cents=1_000),
        _claim(claimed_cents=2_000, situation=calculations.CLAIM_REJECTED, recognized_cents=0),
    )

    assert (
        calculations.claim_exposure_cents(claims, direction=calculations.CLAIM_DIRECTION_CONTRACTOR)
        == 1_000
    )


# ── Taxa de reconhecimento ───────────────────────────────────────────────


def test_taxa_de_reconhecimento_e_da_contratada_nos_encerrados() -> None:
    claims = (
        _claim(
            claimed_cents=52_000_000,
            recognized_cents=40_000_000,
            situation=calculations.CLAIM_CLOSED,
        ),
        _claim(
            claimed_cents=18_000_000,
            recognized_cents=15_000_000,
            situation=calculations.CLAIM_AGREED,
        ),
        _claim(claimed_cents=100_000_000, situation=calculations.CLAIM_UNDER_REVIEW),
        _claim(
            claimed_cents=3_400_000,
            direction=calculations.CLAIM_DIRECTION_CLIENT,
            recognized_cents=3_400_000,
            situation=calculations.CLAIM_AGREED,
        ),
        _claim(
            claimed_cents=10_000_000,
            recognized_cents=None,
            situation=calculations.CLAIM_REJECTED,
        ),
    )

    assert calculations.recognition_rate(claims) == D("68.8")


def test_taxa_de_reconhecimento_sem_pleiteado_encerrado_e_nula() -> None:
    claims = (
        _claim(claimed_cents=100, situation=calculations.CLAIM_UNDER_REVIEW),
        _claim(direction=calculations.CLAIM_DIRECTION_CLIENT, situation=calculations.CLAIM_CLOSED),
    )

    assert calculations.recognition_rate(claims) is None
    assert calculations.recognition_rate(()) is None


# ── Tempo médio de resolução ─────────────────────────────────────────────


def test_tempo_medio_de_resolucao_e_a_media_dos_encerrados() -> None:
    claims = (
        _claim(notification_date=date(2026, 8, 26), closed_on=date(2026, 9, 9)),
        _claim(notification_date=date(2026, 4, 20), closed_on=date(2026, 7, 10)),
        _claim(notification_date=date(2026, 3, 27), closed_on=date(2026, 5, 18)),
        _claim(closed_on=None),
    )

    assert calculations.average_resolution_days(claims) == 49


def test_tempo_medio_de_resolucao_arredonda_meio_para_cima() -> None:
    claims = (
        _claim(notification_date=date(2026, 8, 1), closed_on=date(2026, 8, 2)),
        _claim(notification_date=date(2026, 8, 1), closed_on=date(2026, 8, 3)),
    )

    assert calculations.average_resolution_days(claims) == 2
    assert calculations.average_resolution_days((_claim(),)) is None


# ── Notificações fora do prazo ───────────────────────────────────────────


def test_notificacao_no_ultimo_dia_do_prazo_nao_e_atraso() -> None:
    deadline = date(2026, 8, 31)
    on_time = _claim(event_date=date(2026, 8, 1), notification_date=deadline, notice_days=30)
    late = _claim(event_date=date(2026, 8, 1), notification_date=deadline + ONE_DAY, notice_days=30)

    assert calculations.late_notification_count((on_time,)) == 0
    assert calculations.late_notification_count((late,)) == 1


# ── Dias e extensão de prazo ─────────────────────────────────────────────


def test_dias_solicitados_e_concedidos_somam_as_eots() -> None:
    extensions = (
        calculations.ExtensionFact(requested_days=30, granted_days=21),
        calculations.ExtensionFact(requested_days=45),
        calculations.ExtensionFact(requested_days=21, granted_days=21),
    )

    days = calculations.extension_days(extensions)

    assert (days.requested, days.granted) == (96, 42)


def test_extensao_percentual_sobre_a_duracao_original() -> None:
    duration = calculations.contract_duration_days(date(2026, 1, 12), date(2026, 10, 30))

    assert duration == 291
    assert calculations.extension_percent(granted_days=42, duration_days=862) == D("4.9")
    assert calculations.extension_percent(granted_days=1, duration_days=16) == D("6.3")
    assert calculations.extension_percent(granted_days=1, duration_days=0) is None


# ── Aprovado não faturado e pago x previsto ──────────────────────────────


def test_aprovado_nao_faturado_soma_so_os_marcos_aprovados() -> None:
    milestones = (
        _milestone(value_cents=39_000_000, situation=calculations.MILESTONE_APPROVED),
        _milestone(value_cents=68_000_000, situation=calculations.MILESTONE_APPROVED),
        _milestone(value_cents=102_000_000, situation=calculations.MILESTONE_PAID),
        _milestone(value_cents=45_500_000, situation=calculations.MILESTONE_FORECAST),
    )

    assert calculations.approved_not_invoiced_cents(milestones) == 107_000_000


def test_pago_previsto_conta_o_marco_na_data_de_referencia() -> None:
    milestones = (
        _milestone(value_cents=100, situation=calculations.MILESTONE_PAID, expected_on=REF),
        _milestone(value_cents=300, expected_on=REF),
        _milestone(
            value_cents=50,
            situation=calculations.MILESTONE_PAID,
            expected_on=REF + ONE_DAY,
        ),
        _milestone(value_cents=200, expected_on=REF - ONE_DAY),
    )

    assert calculations.paid_forecast_percent(milestones, reference_date=REF) == D("25.0")
    assert (
        calculations.paid_forecast_percent(
            (_milestone(expected_on=REF + ONE_DAY),), reference_date=REF
        )
        is None
    )
    assert calculations.paid_forecast_percent((), reference_date=REF) is None


def test_pago_previsto_arredonda_meio_para_cima() -> None:
    milestones = (
        _milestone(value_cents=1, situation=calculations.MILESTONE_PAID, expected_on=REF),
        _milestone(value_cents=15, expected_on=REF),
    )

    assert calculations.paid_forecast_percent(milestones, reference_date=REF) == D("6.3")


# ── Nota média das contratadas ───────────────────────────────────────────


def test_nota_media_e_a_media_das_ultimas_avaliacoes() -> None:
    evaluations = (
        _evaluation(
            {
                "hse": 5,
                "qualidade": 4,
                "prazo": 3,
                "gestao": 4,
                "recursos": 4,
                "documentacao": 5,
            }
        ),
        _evaluation(dict.fromkeys(MOCK_WEIGHTS, 4)),
        _evaluation(
            {
                "hse": 4,
                "qualidade": 3,
                "prazo": 2,
                "gestao": 3,
                "recursos": 4,
                "documentacao": 3,
            }
        ),
    )

    assert calculations.average_evaluation_score(evaluations) == D("75.3")


def test_nota_media_arredonda_meio_para_cima_e_ignora_a_avaliacao_sem_nota() -> None:
    seventy = {"hse": 3, "qualidade": 4, "prazo": 4, "gestao": 3, "recursos": 3, "documentacao": 4}
    seventy_one = {
        "hse": 4,
        "qualidade": 4,
        "prazo": 3,
        "gestao": 3,
        "recursos": 4,
        "documentacao": 3,
    }
    evaluations = (
        _evaluation(seventy),
        _evaluation(seventy),
        _evaluation(seventy),
        _evaluation(seventy_one),
        calculations.EvaluationFact(period=date(2026, 9, 1), notes={}, weights={}),
    )

    assert calculations.average_evaluation_score(evaluations) == D("70.3")
    assert calculations.average_evaluation_score(()) is None


# ── Marcos atrasados ─────────────────────────────────────────────────────


def test_marcos_atrasados_contam_so_os_pendentes_com_data_vencida() -> None:
    milestones = (
        _milestone(expected_on=REF),
        _milestone(situation=calculations.MILESTONE_EVIDENCE_SENT, expected_on=REF - ONE_DAY),
        _milestone(situation=calculations.MILESTONE_PAID, expected_on=REF - 10 * ONE_DAY),
        _milestone(situation=calculations.MILESTONE_APPROVED, expected_on=REF - 10 * ONE_DAY),
        _milestone(expected_on=REF + ONE_DAY),
    )

    assert calculations.late_milestone_count(milestones, reference_date=REF) == 1


# ── Medido percentual do contrato ────────────────────────────────────────


def test_medido_percentual_do_contrato() -> None:
    assert calculations.contract_measured_percent(289_800_000, 345_000_000) == D("84.0")
    assert calculations.contract_measured_percent(1, 16) == D("6.3")
    assert calculations.contract_measured_percent(0, 0) is None


# ── Resumo e composição dos indicadores ──────────────────────────────────


def _mock_facts() -> calculations.ContractFacts:
    """Os fatos do projeto 1 da carga: os mesmos números que a visão consolidada confere."""
    claims = (
        _claim(claimed_cents=18_500_000, situation=calculations.CLAIM_IN_NEGOTIATION),
        _claim(
            claimed_cents=3_400_000,
            direction=calculations.CLAIM_DIRECTION_CLIENT,
            situation=calculations.CLAIM_AGREED,
            recognized_cents=3_400_000,
            notification_date=date(2026, 8, 26),
            closed_on=date(2026, 9, 9),
        ),
        _claim(
            claimed_cents=42_000_000,
            event_date=date(2026, 6, 10),
            notification_date=date(2026, 8, 5),
        ),
        _claim(
            claimed_cents=52_000_000,
            recognized_cents=40_000_000,
            situation=calculations.CLAIM_CLOSED,
            notification_date=date(2026, 4, 20),
            closed_on=date(2026, 7, 10),
        ),
        _claim(
            claimed_cents=18_000_000,
            recognized_cents=15_000_000,
            situation=calculations.CLAIM_CLOSED,
            notification_date=date(2026, 3, 27),
            closed_on=date(2026, 5, 18),
        ),
    )
    milestones = (
        _milestone(
            value_cents=34_500_000,
            situation=calculations.MILESTONE_PAID,
            expected_on=date(2026, 1, 30),
        ),
        _milestone(
            value_cents=69_000_000,
            situation=calculations.MILESTONE_PAID,
            expected_on=date(2026, 4, 10),
        ),
        _milestone(
            value_cents=86_250_000,
            situation=calculations.MILESTONE_PAID,
            expected_on=date(2026, 6, 15),
        ),
        _milestone(
            value_cents=100_050_000,
            situation=calculations.MILESTONE_INVOICED,
            expected_on=date(2026, 8, 15),
        ),
        _milestone(
            value_cents=41_400_000,
            situation=calculations.MILESTONE_EVIDENCE_SENT,
            expected_on=date(2026, 9, 20),
        ),
        _milestone(value_cents=13_800_000, expected_on=date(2026, 11, 20)),
    )
    contracts = (
        calculations.ContractFact(
            start=date(2026, 1, 12), original_end=date(2026, 10, 30), evaluation_class="B"
        ),
        calculations.ContractFact(
            start=date(2026, 2, 2), original_end=date(2026, 11, 30), evaluation_class="B"
        ),
        calculations.ContractFact(
            start=date(2026, 5, 4), original_end=date(2027, 1, 29), evaluation_class="C"
        ),
    )
    evaluations = (
        _evaluation(
            {
                "hse": 5,
                "qualidade": 4,
                "prazo": 3,
                "gestao": 4,
                "recursos": 4,
                "documentacao": 5,
            }
        ),
        _evaluation(dict.fromkeys(MOCK_WEIGHTS, 4)),
        _evaluation(
            {
                "hse": 4,
                "qualidade": 3,
                "prazo": 2,
                "gestao": 3,
                "recursos": 4,
                "documentacao": 3,
            }
        ),
    )
    return calculations.ContractFacts(
        contracts=contracts,
        claims=claims,
        extensions=(
            calculations.ExtensionFact(requested_days=30, granted_days=21),
            calculations.ExtensionFact(requested_days=45),
            calculations.ExtensionFact(requested_days=21, granted_days=21),
        ),
        milestones=milestones,
        evaluations=evaluations,
    )


def test_resumo_da_administracao_contratual_bate_com_o_mock() -> None:
    summary = calculations.contracts_summary(_mock_facts(), reference_date=REF)

    assert summary == calculations.ContractsSummary(
        contracts=3,
        exposure_cents=60_500_000,
        open_claims=2,
        late_notifications=1,
        late_milestones=1,
        contractors_c_or_d=1,
    )


def test_indicadores_da_administracao_contratual_batem_com_o_mock() -> None:
    indicators = calculations.contract_indicators(_mock_facts(), reference_date=REF)

    assert indicators == calculations.ContractIndicators(
        contractor_exposure_cents=60_500_000,
        client_exposure_cents=0,
        recognition_rate=D("78.6"),
        average_resolution_days=49,
        requested_days=96,
        granted_days=42,
        extension_percent=D("4.9"),
        approved_not_invoiced_cents=0,
        paid_forecast_percent=D("57.3"),
        average_score=D("75.3"),
    )
