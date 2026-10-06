"""O status da ação e os números dos KPIs (ISSUE-019, D6): as regras puras, com a data injetada.

O status sai sempre da consulta, nunca de uma coluna: Informação; Concluída quando há data de
conclusão; Atrasada quando a Replanejada (ou, sem ela, a Prevista) é anterior à data de
referência; senão Em andamento. A fronteira é a data prevista igual à de referência: ainda
está em dia.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.modulos.central_acoes import calculations
from src.modulos.central_acoes.calculations import (
    ACTION,
    INFORMATION,
    ActionDates,
    ActionStatus,
    StatusCounts,
    StatusFilter,
)

REFERENCIA = date(2026, 9, 25)
ONTEM = REFERENCIA - timedelta(days=1)
AMANHA = REFERENCIA + timedelta(days=1)


def _datas(
    prevista: date | None,
    replanejada: date | None = None,
    conclusao: date | None = None,
    tipo: str = ACTION,
) -> ActionDates:
    return ActionDates(
        kind=tipo, planned_date=prevista, replanned_date=replanejada, completed_on=conclusao
    )


# ── Os quatro casos do status ────────────────────────────────────────────────


def test_informacao_nao_e_acao() -> None:
    status = calculations.action_status(_datas(None, tipo=INFORMATION), REFERENCIA)

    assert status is ActionStatus.INFORMATION


def test_com_data_de_conclusao_a_acao_esta_concluida_mesmo_depois_do_prazo() -> None:
    status = calculations.action_status(_datas(ONTEM, conclusao=REFERENCIA), REFERENCIA)

    assert status is ActionStatus.COMPLETED


def test_prevista_anterior_a_referencia_esta_atrasada() -> None:
    assert calculations.action_status(_datas(ONTEM), REFERENCIA) is ActionStatus.OVERDUE


def test_prevista_futura_esta_em_andamento() -> None:
    assert calculations.action_status(_datas(AMANHA), REFERENCIA) is ActionStatus.IN_PROGRESS


# ── A fronteira: prevista igual a hoje ───────────────────────────────────────


def test_prevista_igual_a_referencia_ainda_esta_em_andamento() -> None:
    assert calculations.action_status(_datas(REFERENCIA), REFERENCIA) is ActionStatus.IN_PROGRESS


def test_um_dia_depois_da_fronteira_a_mesma_acao_esta_atrasada() -> None:
    status = calculations.action_status(_datas(REFERENCIA), AMANHA)

    assert status is ActionStatus.OVERDUE


def test_replanejada_igual_a_referencia_ainda_esta_em_andamento() -> None:
    status = calculations.action_status(_datas(ONTEM, replanejada=REFERENCIA), REFERENCIA)

    assert status is ActionStatus.IN_PROGRESS


# ── A replanejada manda sobre a prevista ─────────────────────────────────────


def test_replanejar_para_o_futuro_tira_a_acao_do_atraso() -> None:
    status = calculations.action_status(_datas(ONTEM, replanejada=AMANHA), REFERENCIA)

    assert status is ActionStatus.IN_PROGRESS


def test_replanejada_vencida_atrasa_mesmo_com_a_prevista_no_futuro() -> None:
    status = calculations.action_status(_datas(AMANHA, replanejada=ONTEM), REFERENCIA)

    assert status is ActionStatus.OVERDUE


def test_sem_nenhuma_data_nao_ha_atraso() -> None:
    assert calculations.action_status(_datas(None), REFERENCIA) is ActionStatus.IN_PROGRESS


@pytest.mark.parametrize(
    "tipo", ["Informação", "informação", "INFORMAÇÃO", "Informacao", "  inform"]
)
def test_o_tipo_informacao_e_reconhecido_pelo_prefixo_sem_diferenciar_caixa(tipo: str) -> None:
    assert calculations.is_information(tipo) is True


@pytest.mark.parametrize("tipo", ["Ação", "acao", ""])
def test_outros_tipos_sao_acao(tipo: str) -> None:
    assert calculations.is_information(tipo) is False


def test_informacao_com_conclusao_continua_informacao() -> None:
    dados = _datas(None, conclusao=ONTEM, tipo=INFORMATION)

    assert calculations.action_status(dados, REFERENCIA) is ActionStatus.INFORMATION


# ── Dias de atraso ───────────────────────────────────────────────────────────


def test_dias_de_atraso_contam_do_prazo_vigente() -> None:
    dados = _datas(date(2026, 8, 30), replanejada=date(2026, 9, 20))

    assert calculations.days_overdue(dados, REFERENCIA) == 5


def test_o_dia_da_fronteira_tem_zero_dias_de_atraso() -> None:
    assert calculations.days_overdue(_datas(REFERENCIA), REFERENCIA) == 0


def test_acao_concluida_ou_em_dia_nao_tem_dias_de_atraso() -> None:
    assert calculations.days_overdue(_datas(ONTEM, conclusao=ONTEM), REFERENCIA) == 0
    assert calculations.days_overdue(_datas(AMANHA), REFERENCIA) == 0


def test_o_prazo_vigente_e_a_replanejada_ou_a_prevista() -> None:
    assert calculations.effective_due_date(ONTEM, AMANHA) == AMANHA
    assert calculations.effective_due_date(ONTEM, None) == ONTEM
    assert calculations.effective_due_date(None, None) is None


# ── Total de ações atrasadas ─────────────────────────────────────────────────


def test_total_de_acoes_atrasadas_conta_so_as_atrasadas() -> None:
    acoes = [
        _datas(ONTEM),
        _datas(REFERENCIA),
        _datas(AMANHA),
        _datas(ONTEM, conclusao=ONTEM),
        _datas(ONTEM, replanejada=AMANHA),
        _datas(AMANHA, replanejada=ONTEM),
        _datas(None, tipo=INFORMATION),
    ]

    assert calculations.overdue_action_count(acoes, REFERENCIA) == 2


def test_total_de_acoes_atrasadas_sem_acoes_e_zero() -> None:
    assert calculations.overdue_action_count([], REFERENCIA) == 0


# ── O filtro de status e os KPIs ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("filtro", "esperados"),
    [
        (StatusFilter.OPEN, {ActionStatus.IN_PROGRESS, ActionStatus.OVERDUE}),
        (StatusFilter.ON_TIME, {ActionStatus.IN_PROGRESS}),
        (StatusFilter.OVERDUE, {ActionStatus.OVERDUE}),
        (StatusFilter.COMPLETED, {ActionStatus.COMPLETED}),
        (
            StatusFilter.ALL,
            {ActionStatus.IN_PROGRESS, ActionStatus.OVERDUE, ActionStatus.COMPLETED},
        ),
    ],
)
def test_o_filtro_em_andamento_inclui_as_atrasadas_e_nenhum_inclui_informacao(
    filtro: StatusFilter, esperados: set[ActionStatus]
) -> None:
    passam = {
        status for status in ActionStatus if calculations.matches_status_filter(filtro, status)
    }

    assert passam == esperados


def test_os_kpis_contam_em_dia_atrasadas_concluidas_e_total() -> None:
    contagem = calculations.counts_by_status(
        [
            ActionStatus.IN_PROGRESS,
            ActionStatus.IN_PROGRESS,
            ActionStatus.OVERDUE,
            ActionStatus.COMPLETED,
            ActionStatus.INFORMATION,
        ]
    )

    assert contagem == StatusCounts(on_time=2, overdue=1, completed=1)
    assert contagem.open == 3
    assert contagem.total == 4


def test_previsto_conta_o_prazo_original_ate_a_referencia_inclusive() -> None:
    acoes = [
        _datas(ONTEM),
        _datas(REFERENCIA),
        _datas(AMANHA),
        _datas(None),
        _datas(ONTEM, replanejada=AMANHA),
    ]

    assert calculations.due_by_reference_count(acoes, REFERENCIA) == 3


@pytest.mark.parametrize(
    ("atrasadas", "em_dia", "esperado"),
    [
        (0, 0, None),
        (0, 5, 0),
        (1, 2, 33),
        (2, 1, 67),
        (1, 1, 50),
        (1, 7, 13),
        (3, 0, 100),
    ],
)
def test_atrasadas_como_percentual_inteiro_das_abertas(
    atrasadas: int, em_dia: int, esperado: int | None
) -> None:
    contagem = StatusCounts(on_time=em_dia, overdue=atrasadas, completed=9)

    assert calculations.overdue_share_of_open(contagem) == esperado
