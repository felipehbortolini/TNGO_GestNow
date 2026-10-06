"""Fórmulas da Governança (ISSUE-023): alçada, prazos, indicadores e etapa, com os casos de fronteira."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.modulos.governanca import calculations as calc
from src.modulos.governanca import models

HOJE = date(2026, 10, 6)


def _alcada(valor: int, *, orcamento: int | None = 1_000_000, marco: bool = False, pct: int = 1):
    return calc.minimum_change_authority(
        value_cents=valor,
        budget_cents=orcamento,
        affects_contract_milestone=marco,
        manager_limit_percent=pct,
    )


def test_alcada_no_limite_exato_e_do_gerente() -> None:
    resultado = _alcada(10_000)
    assert resultado.limit_cents == 10_000
    assert resultado.authority == models.AUTHORITY_MANAGER


def test_alcada_um_centavo_acima_do_limite_e_do_comite() -> None:
    assert _alcada(10_001).authority == models.AUTHORITY_COMMITTEE


def test_alcada_usa_o_valor_absoluto_do_remanejamento() -> None:
    assert _alcada(-10_000).authority == models.AUTHORITY_MANAGER
    assert _alcada(-10_001).authority == models.AUTHORITY_COMMITTEE


def test_alcada_marco_contratual_vai_ao_comite_mesmo_sem_custo() -> None:
    assert _alcada(0, marco=True).authority == models.AUTHORITY_COMMITTEE


def test_alcada_sem_orcamento_so_o_valor_zero_fica_com_o_gerente() -> None:
    assert _alcada(0, orcamento=None).authority == models.AUTHORITY_MANAGER
    assert _alcada(1, orcamento=None).authority == models.AUTHORITY_COMMITTEE


def test_ratificacao_emergencial_soma_os_dias_configurados() -> None:
    assert calc.emergency_ratification_due_date(date(2026, 9, 28), 7) == date(2026, 10, 5)
    assert calc.emergency_ratification_due_date(date(2026, 12, 28), 7) == date(2027, 1, 4)


def test_analise_vencida_so_depois_do_prazo_e_so_em_analise() -> None:
    em_analise = models.SITUATION_ANALYSIS
    assert not calc.is_analysis_overdue(em_analise, HOJE, HOJE)
    assert calc.is_analysis_overdue(em_analise, date(2026, 10, 5), HOJE)
    assert not calc.is_analysis_overdue(models.SITUATION_AWAITING, date(2026, 10, 5), HOJE)
    assert not calc.is_analysis_overdue(em_analise, None, HOJE)


def test_ratificacao_pendente_e_vencida() -> None:
    pendente = calc.is_emergency_pending(
        emergency=True, has_decision=False, situation=models.SITUATION_REGISTERED
    )
    assert pendente
    assert not calc.is_emergency_pending(
        emergency=True, has_decision=True, situation=models.SITUATION_REGISTERED
    )
    assert not calc.is_emergency_pending(
        emergency=True, has_decision=False, situation=models.SITUATION_CANCELLED
    )
    assert not calc.is_ratification_overdue(pending=True, due_date=HOJE, reference_date=HOJE)
    assert calc.is_ratification_overdue(
        pending=True, due_date=date(2026, 10, 5), reference_date=HOJE
    )
    assert not calc.is_ratification_overdue(
        pending=False, due_date=date(2026, 10, 5), reference_date=HOJE
    )


@pytest.mark.parametrize(
    ("situacao", "etapa"),
    [
        (models.SITUATION_REGISTERED, 0),
        (models.SITUATION_ANALYSIS, 1),
        (models.SITUATION_AWAITING, 2),
        (models.SITUATION_POSTPONED, 2),
        (models.SITUATION_APPROVED, 3),
        (models.SITUATION_IMPLEMENTING, 3),
        (models.SITUATION_CANCELLED, calc.LAST_STAGE),
    ],
)
def test_etapa_da_mudanca(situacao: str, etapa: int) -> None:
    assert calc.change_stage(situacao) == etapa


def test_percentual_do_orcamento_arredonda_meio_para_cima_e_sem_orcamento_e_nulo() -> None:
    assert calc.percent_of(5, 10_000) == Decimal("0.1")
    assert calc.percent_of(4, 10_000) == Decimal("0.0")
    assert calc.percent_of(1, 0) is None
    assert calc.percent_of(1, None) is None


def _fig(situacao: str, pedido: date, decisao: date | None = None, **resto):
    return calc.ChangeFigures(
        situation=situacao, request_date=pedido, decision_date=decisao, **resto
    )


def test_tempo_medio_de_decisao_arredonda_meio_para_cima() -> None:
    figuras = [
        _fig(models.SITUATION_APPROVED, date(2026, 9, 1), date(2026, 9, 2)),
        _fig(models.SITUATION_REJECTED, date(2026, 9, 1), date(2026, 9, 4)),
        _fig(models.SITUATION_REGISTERED, date(2026, 9, 1)),
    ]
    assert calc.mean_decision_days(figuras) == 2  # (1 + 3) / 2
    assert calc.mean_decision_days([figuras[0], _fig("x", date(2026, 9, 1), date(2026, 9, 3))]) == 2
    assert calc.mean_decision_days([figuras[2]]) is None


def test_indicadores_do_registro() -> None:
    figuras = [
        _fig(models.SITUATION_REGISTERED, date(2026, 10, 1)),
        _fig(
            models.SITUATION_ANALYSIS,
            date(2026, 9, 20),
            analysis_deadline=date(2026, 10, 5),
        ),
        _fig(models.SITUATION_AWAITING, date(2026, 9, 1)),
        _fig(
            models.SITUATION_APPROVED,
            date(2026, 9, 1),
            date(2026, 9, 11),
            cost_cents=20_000,
            term_days=5,
        ),
        _fig(
            models.SITUATION_IMPLEMENTING,
            date(2025, 12, 1),
            date(2025, 12, 31),
            cost_cents=30_000,
            term_days=-2,
        ),
        _fig(models.SITUATION_REJECTED, date(2026, 9, 1), date(2026, 9, 3), cost_cents=99_999),
    ]
    resumo = calc.summarize_changes(figuras, budget_cents=1_000_000, reference_date=HOJE)
    assert resumo.total == 6
    assert resumo.in_analysis == 2
    assert resumo.overdue_analysis == 1
    assert resumo.awaiting_committee == 1
    assert resumo.approved == 2
    assert resumo.approved_in_year == 1
    assert resumo.approved_value_cents == 50_000
    assert resumo.approved_value_percent == Decimal("5.0")
    assert resumo.approved_term_days == 3
    assert resumo.mean_decision_days == 14  # (10 + 30 + 2) / 3


def test_indicadores_do_registro_vazio() -> None:
    resumo = calc.summarize_changes([], budget_cents=None, reference_date=HOJE)
    assert resumo.total == 0
    assert resumo.approved_value_percent is None
    assert resumo.mean_decision_days is None


# ── Alçada exigida e prazo da análise (ISSUE-024) ────────────────────────


def _exigida(**fatos):
    base = {
        "kind": "Custo",
        "resource_source": None,
        "cost_cents": 0,
        "transferred_cents": 0,
        "budget_cents": 1_000_000,
        "affects_contract_milestone": False,
    }
    base.update(fatos)
    return calc.required_change_authority(calc.AuthorityFacts(**base), manager_limit_percent=1)


def test_alcada_exigida_no_limite_do_percentual_e_do_gerente() -> None:
    assert _exigida(cost_cents=10_000).authority == models.AUTHORITY_MANAGER
    assert _exigida(cost_cents=10_001).authority == models.AUTHORITY_COMMITTEE


def test_alcada_exigida_com_marco_contratual_e_do_comite_mesmo_sem_custo() -> None:
    assert (
        _exigida(cost_cents=0, affects_contract_milestone=True).authority
        == models.AUTHORITY_COMMITTEE
    )
    assert (
        _exigida(cost_cents=0, affects_contract_milestone=False).authority
        == models.AUTHORITY_MANAGER
    )


def test_alcada_exigida_le_o_maior_entre_o_custo_e_o_remanejado() -> None:
    assert (
        _exigida(cost_cents=5_000, transferred_cents=10_000).authority == models.AUTHORITY_MANAGER
    )
    assert (
        _exigida(cost_cents=5_000, transferred_cents=10_001).authority == models.AUTHORITY_COMMITTEE
    )
    assert _exigida(cost_cents=-10_001).authority == models.AUTHORITY_COMMITTEE


def test_liberacao_de_reserva_vai_sempre_ao_comite() -> None:
    resultado = _exigida(kind=models.TYPE_RESERVE_RELEASE, cost_cents=0)
    assert resultado.authority == models.AUTHORITY_COMMITTEE
    assert resultado.limit_cents == 10_000


def test_reserva_gerencial_vai_sempre_ao_comite_e_a_de_contingencia_segue_o_valor() -> None:
    assert (
        _exigida(resource_source=models.SOURCE_MANAGEMENT_RESERVE, cost_cents=1).authority
        == models.AUTHORITY_COMMITTEE
    )
    assert (
        _exigida(resource_source="Reserva de contingência", cost_cents=1).authority
        == models.AUTHORITY_MANAGER
    )


def test_sem_orcamento_so_custo_zero_cabe_ao_gerente() -> None:
    assert _exigida(cost_cents=0, budget_cents=None).authority == models.AUTHORITY_MANAGER
    assert _exigida(cost_cents=1, budget_cents=None).authority == models.AUTHORITY_COMMITTEE


def test_so_rebaixar_e_recusado() -> None:
    assert calc.is_authority_lowered(models.AUTHORITY_MANAGER, models.AUTHORITY_COMMITTEE)
    assert not calc.is_authority_lowered(models.AUTHORITY_COMMITTEE, models.AUTHORITY_COMMITTEE)
    assert not calc.is_authority_lowered(models.AUTHORITY_COMMITTEE, models.AUTHORITY_MANAGER)
    assert not calc.is_authority_lowered(models.AUTHORITY_MANAGER, models.AUTHORITY_MANAGER)


@pytest.mark.parametrize(
    ("dias", "esperado"), [(0, HOJE), (10, date(2026, 10, 16)), (26, date(2026, 11, 1))]
)
def test_prazo_padrao_da_analise_soma_os_dias_do_parametro(dias: int, esperado: date) -> None:
    assert calc.analysis_deadline(HOJE, dias) == esperado
