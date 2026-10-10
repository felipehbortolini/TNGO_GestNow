"""Os cálculos das auditorias (ISSUE-070): atraso, conformidade e aderência, com a fronteira.

Funções puras, com a data de referência injetada (D6): o dia planejado ainda não atrasa;
conformidade e aderência arredondam para cima na metade e vazias devolvem ``None``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.modulos.qualidade import calculations

REFERENCIA = date(2026, 9, 25)


def test_o_dia_planejado_ainda_nao_atrasa() -> None:
    assert calculations.audit_overdue("Planejada", REFERENCIA, REFERENCIA) is False
    assert calculations.audit_overdue("Planejada", date(2026, 9, 24), REFERENCIA) is True
    assert calculations.audit_overdue("Realizada", date(2026, 9, 24), REFERENCIA) is False
    assert calculations.audit_days_overdue("Planejada", date(2026, 9, 15), REFERENCIA) == 10
    assert calculations.audit_days_overdue("Planejada", REFERENCIA, REFERENCIA) == 0
    assert calculations.audit_days_overdue("Realizada", date(2026, 9, 15), REFERENCIA) == 0


def test_a_conformidade_arredonda_com_uma_casa() -> None:
    assert calculations.audit_conformity_rate(36, 40) == Decimal("90.0")
    assert calculations.audit_conformity_rate(29, 35) == Decimal("82.9")
    assert calculations.audit_conformity_rate(65, 75) == Decimal("86.7")
    assert calculations.audit_conformity_rate(1, 16) == Decimal("6.3")
    assert calculations.audit_conformity_rate(0, 0) is None


def test_a_aderencia_ao_programa() -> None:
    assert calculations.audit_program_adherence(2, 3) == Decimal("66.7")
    assert calculations.audit_program_adherence(1, 1) == Decimal("100.0")
    assert calculations.audit_program_adherence(0, 3) == Decimal("0.0")
    assert calculations.audit_program_adherence(0, 0) is None


def test_as_contagens_por_tipo_de_constatacao() -> None:
    contagens = calculations.finding_type_counts(
        ["Não conformidade", "Observação", "Não conformidade"]
    )

    assert contagens == {
        "Não conformidade": 2,
        "Observação": 1,
        "Oportunidade de melhoria": 0,
    }
