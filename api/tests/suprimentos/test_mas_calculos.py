"""Os cálculos do MAS (ISSUE-062): as seis situações do marco, a LB estimada, a linha e o avanço.

Cada regra da situação do marco tem um teste; a estimativa da linha de base de fabricação de um
pacote sem pedido segue as proporções da emissão entre o pedido e o ROS; o avanço pondera os pesos
do parâmetro pelo valor do pacote e o índice é o real dividido pelo previsto.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.suprimentos import calculations

REFERENCIA = date(2026, 9, 25)


# ── As seis regras da situação do marco ─────────────────────────────────────────────────────


def test_o_marco_realizado_ate_a_linha_de_base_le_no_prazo() -> None:
    read = calculations.milestone_situation(
        baseline=date(2026, 9, 20),
        forecast=None,
        real=date(2026, 9, 20),
        reference_date=REFERENCIA,
    )

    assert read.situation == calculations.MILESTONE_ON_TIME
    assert read.deviation_days == 0
    assert read.days_overdue == 0


def test_o_marco_realizado_depois_da_linha_de_base_le_com_atraso() -> None:
    read = calculations.milestone_situation(
        baseline=date(2026, 9, 10),
        forecast=None,
        real=date(2026, 9, 24),
        reference_date=REFERENCIA,
    )

    assert read.situation == calculations.MILESTONE_LATE
    assert read.deviation_days == 14
    assert read.days_overdue == 0


def test_o_marco_vencido_sem_realizacao() -> None:
    read = calculations.milestone_situation(
        baseline=date(2026, 9, 10),
        forecast=date(2026, 9, 15),
        real=None,
        reference_date=REFERENCIA,
    )

    assert read.situation == calculations.MILESTONE_OVERDUE
    assert read.deviation_days == 5
    assert read.days_overdue == 10


def test_o_marco_com_previsao_apos_a_linha_de_base() -> None:
    read = calculations.milestone_situation(
        baseline=date(2026, 9, 20),
        forecast=date(2026, 10, 5),
        real=None,
        reference_date=REFERENCIA,
    )

    assert read.situation == calculations.MILESTONE_FORECAST_LATE
    assert read.deviation_days == 15


def test_o_marco_a_vencer() -> None:
    read = calculations.milestone_situation(
        baseline=date(2026, 9, 30),
        forecast=None,
        real=None,
        reference_date=REFERENCIA,
    )

    assert read.situation == calculations.MILESTONE_DUE_SOON
    assert read.deviation_days == 0


def test_o_marco_que_nao_se_aplica_a_fabricacao_de_servico() -> None:
    read = calculations.milestone_situation(
        baseline=None,
        forecast=None,
        real=None,
        reference_date=REFERENCIA,
        applicable=False,
    )

    assert read.situation == calculations.MILESTONE_NOT_APPLICABLE
    assert read.deviation_days is None


def test_o_marco_sem_data_nem_linha_de_base() -> None:
    read = calculations.milestone_situation(
        baseline=None, forecast=None, real=None, reference_date=REFERENCIA
    )

    assert read.situation == calculations.MILESTONE_WITHOUT_DATE


# ── A LB estimada e a situação da linha ─────────────────────────────────────────────────────


def test_a_lb_estimada_interpola_pelas_proporcoes_da_emissao() -> None:
    pedido = date(2026, 9, 18)
    ros = date(2027, 1, 10)

    assert calculations.estimated_fabrication_date(pedido, ros, 0) == date(2026, 10, 5)
    assert calculations.estimated_fabrication_date(pedido, ros, 2) == date(2026, 12, 13)
    assert calculations.estimated_fabrication_date(pedido, ros, 5) == ros
    assert calculations.estimated_fabrication_date(None, ros, 0) is None


def test_a_situacao_da_linha_segue_o_fim_do_ciclo_e_a_faixa() -> None:
    assert (
        calculations.mas_line_situation(
            concluded=False, service=False, band=calculations.SLACK_CRITICAL, has_overdue=False
        )
        == calculations.MAS_CRITICAL
    )
    assert (
        calculations.mas_line_situation(
            concluded=False, service=False, band=calculations.SLACK_OK, has_overdue=True
        )
        == calculations.MAS_WARNING
    )
    assert (
        calculations.mas_line_situation(
            concluded=False, service=False, band=calculations.SLACK_OK, has_overdue=False
        )
        == calculations.MAS_ON_TIME
    )
    assert (
        calculations.mas_line_situation(
            concluded=True, service=False, band=calculations.SLACK_OK, has_overdue=False
        )
        == calculations.MAS_DELIVERED
    )
    assert (
        calculations.mas_line_situation(
            concluded=True, service=True, band=calculations.SLACK_OK, has_overdue=False
        )
        == calculations.MAS_CONTRACTED
    )


# ── O avanço de suprimentos e o índice ──────────────────────────────────────────────────────


def _milestone(
    weight: int, *, baseline: date | None = None, real: date | None = None, applicable: bool = True
):
    return calculations.MasProgressMilestone(
        weight=weight, applicable=applicable, baseline=baseline, real=real
    )


def test_o_avanco_do_pacote_renormaliza_os_marcos_aplicaveis() -> None:
    progress = calculations.package_progress(
        (
            _milestone(5, baseline=date(2026, 8, 1), real=date(2026, 8, 1)),
            _milestone(5, baseline=date(2026, 8, 10)),
            _milestone(10, applicable=False),
        ),
        reference_date=REFERENCIA,
    )

    assert progress.realized_pct == Decimal("50.0")
    assert progress.planned_pct == Decimal("100.0")


def test_o_avanco_de_suprimentos_pondera_pelo_valor_do_pacote() -> None:
    primeiro = calculations.MasProgress(realized_pct=Decimal("10.0"), planned_pct=Decimal("40.0"))
    segundo = calculations.MasProgress(realized_pct=Decimal("100.0"), planned_pct=Decimal("100.0"))

    progress = calculations.procurement_progress(((primeiro, 100_000_00), (segundo, 300_000_00)))

    assert progress.realized_pct == Decimal("77.5")
    assert progress.planned_pct == Decimal("85.0")
    assert progress.index == Decimal("0.91")


def test_sem_valor_o_avanco_de_suprimentos_zera_e_nao_tem_indice() -> None:
    progress = calculations.procurement_progress(())

    assert progress.realized_pct == Decimal(0)
    assert progress.index is None


def test_a_faixa_do_indice_le_o_ritmo_da_linha_de_base() -> None:
    assert calculations.progress_band(Decimal("1.00")) == calculations.PROGRESS_ON_PACE
    assert calculations.progress_band(Decimal("0.95")) == calculations.PROGRESS_NEAR
    assert calculations.progress_band(Decimal("0.94")) == calculations.PROGRESS_BELOW
    assert calculations.progress_band(None) is None
