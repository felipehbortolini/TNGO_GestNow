"""Os números do painel e do follow-up (ISSUE-020, D12): regras puras, com fronteira."""

from __future__ import annotations

from datetime import date

from src.modulos.central_acoes import calculations
from src.modulos.central_acoes.calculations import (
    ActionDates,
    ActionStatus,
    FollowUpAction,
    ResponsibleTally,
)

REFERENCIA = date(2026, 9, 25)


def _item(
    action_id: int, person: int, status: ActionStatus, days: int = 0, due: date | None = None
) -> FollowUpAction:
    return FollowUpAction(
        action_id=action_id,
        project_id=1,
        responsible_id=person,
        label="RSK",
        subject="Assunto",
        due_date=due,
        status=status,
        days_overdue=days,
    )


def test_percentual_inteiro_arredonda_meio_para_cima_e_zero_vira_none() -> None:
    assert calculations.whole_percent(1, 8) == 13
    assert calculations.whole_percent(0, 5) == 0
    assert calculations.whole_percent(3, 0) is None


def test_totais_do_responsavel_e_maior_atraso() -> None:
    tally = calculations.responsible_tally(
        [
            (ActionStatus.IN_PROGRESS, 0),
            (ActionStatus.OVERDUE, 3),
            (ActionStatus.OVERDUE, 9),
            (ActionStatus.COMPLETED, 0),
        ]
    )

    assert (tally.on_time, tally.overdue, tally.completed) == (1, 2, 1)
    assert (tally.open, tally.total, tally.longest_delay) == (3, 4, 9)
    assert tally.overdue_share == 67


def test_grupo_vazio_nao_tem_percentual_de_atraso() -> None:
    assert ResponsibleTally(0, 0, 2, 0).overdue_share is None


def test_concluida_no_prazo_original_aceita_a_data_prevista_e_recusa_o_dia_seguinte() -> None:
    previsto = date(2026, 9, 10)
    no_dia = ActionDates("Ação", previsto, None, previsto)
    um_dia_depois = ActionDates("Ação", previsto, None, date(2026, 9, 11))
    sem_data = ActionDates("Ação", None, None, previsto)

    assert calculations.completed_on_planned_count([no_dia, um_dia_depois, sem_data]) == 1


def test_previstas_e_concluidas_por_mes() -> None:
    meses = calculations.monthly_planned_vs_completed(
        [
            ActionDates("Ação", date(2026, 8, 31), None, date(2026, 9, 2)),
            ActionDates("Ação", date(2026, 9, 1), date(2026, 10, 5), None),
        ]
    )

    assert [(m.month, m.planned, m.completed) for m in meses] == [
        ("2026-08", 1, 0),
        ("2026-09", 0, 1),
        ("2026-10", 1, 0),
    ]


def test_ranking_dos_que_mais_tem_abertas_ignora_quem_so_concluiu() -> None:
    tallies = {
        1: ResponsibleTally(1, 1, 0, 2),
        2: ResponsibleTally(2, 0, 0, 0),
        3: ResponsibleTally(0, 0, 4, 0),
        4: ResponsibleTally(1, 1, 0, 1),
    }

    assert calculations.top_open_responsibles(tallies) == [1, 4, 2]
    assert calculations.top_open_responsibles(tallies, limit=1) == [1]


def test_agrupa_so_abertas_por_responsavel_com_a_mais_atrasada_primeiro() -> None:
    itens = [
        _item(1, 10, ActionStatus.IN_PROGRESS, due=date(2026, 10, 1)),
        _item(2, 10, ActionStatus.OVERDUE, 5, date(2026, 9, 20)),
        _item(3, 10, ActionStatus.COMPLETED),
        _item(4, 20, ActionStatus.IN_PROGRESS, due=date(2026, 10, 2)),
        _item(5, 30, ActionStatus.COMPLETED),
    ]

    grupos = calculations.group_for_follow_up(itens, {10: "Ana", 20: "Bia", 30: "Caio"})

    assert [g.responsible_id for g in grupos] == [10, 20]
    assert [a.action_id for a in grupos[0].actions] == [2, 1]
    assert grupos[0].overdue_count == 1
