"""Calendário da plataforma: semana ISO, período parcial, corte e a trava do relógio.

Todas as fórmulas recebem a data de referência como argumento (D6); o único
leitor do relógio é ``src/core/calendario.py``, e o teste abaixo reprova
qualquer outra ocorrência no código da aplicação.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from src.core import calendario

FONTE = Path(__file__).resolve().parents[2] / "src"
LEITOR_DO_RELOGIO = FONTE / "core" / "calendario.py"

PADROES_DE_RELOGIO = (
    "datetime.now(",
    "datetime.utcnow(",
    "datetime.today(",
    "date.today(",
    "time.time(",
    "time.monotonic(",
    "time.perf_counter(",
)


def test_semana_iso_na_virada_do_ano() -> None:
    # A semana 1 de 2026 contém a primeira quinta-feira do ano (01/01/2026).
    assert calendario.iso_week(date(2025, 12, 29)) == "2026-S01"
    assert calendario.iso_week(date(2026, 1, 1)) == "2026-S01"
    assert calendario.iso_week(date(2026, 1, 4)) == "2026-S01"
    assert calendario.iso_week(date(2026, 1, 5)) == "2026-S02"
    # 01/01/2021, sexta-feira, pertence à última semana de 2020.
    assert calendario.iso_week(date(2021, 1, 1)) == "2020-S53"


def test_inicio_da_semana_iso_e_a_segunda_e_o_fim_e_domingo() -> None:
    assert calendario.week_start("2026-S01") == date(2025, 12, 29)
    assert calendario.period_bounds(calendario.WEEKLY, "2026-S01") == (
        date(2025, 12, 29),
        date(2026, 1, 4),
    )


def test_rotulo_de_semana_invalido_nao_vira_periodo() -> None:
    assert calendario.week_start("2026-S54") is None
    assert not calendario.valid_period(calendario.WEEKLY, "2026-S1")
    assert not calendario.valid_period(calendario.WEEKLY, "2026-38")


def test_periodo_parcial_e_corte_limitado_a_data_de_referencia_na_semana() -> None:
    # A semana 40 de 2026 vai de 28/09/2026 (segunda) a 04/10/2026 (domingo).
    assert calendario.is_partial(calendario.WEEKLY, "2026-S40", date(2026, 9, 30))
    assert calendario.cut_date(calendario.WEEKLY, "2026-S40", date(2026, 9, 30)) == date(
        2026, 9, 30
    )
    # No último dia a semana ainda está em andamento; o corte é o próprio fim.
    assert calendario.is_partial(calendario.WEEKLY, "2026-S40", date(2026, 10, 4))
    assert calendario.cut_date(calendario.WEEKLY, "2026-S40", date(2026, 10, 4)) == date(
        2026, 10, 4
    )
    # Depois do fim, a semana fechou e o corte para no domingo.
    assert not calendario.is_partial(calendario.WEEKLY, "2026-S40", date(2026, 10, 5))
    assert calendario.cut_date(calendario.WEEKLY, "2026-S40", date(2026, 10, 5)) == date(
        2026, 10, 4
    )


def test_periodo_parcial_e_corte_no_mes_civil() -> None:
    assert calendario.period_of(calendario.MONTHLY, date(2026, 9, 30)) == "2026-09"
    assert calendario.is_partial(calendario.MONTHLY, "2026-09", date(2026, 9, 15))
    assert calendario.cut_date(calendario.MONTHLY, "2026-09", date(2026, 9, 15)) == date(
        2026, 9, 15
    )
    assert not calendario.is_partial(calendario.MONTHLY, "2026-09", date(2026, 10, 1))
    assert calendario.cut_date(calendario.MONTHLY, "2026-09", date(2026, 10, 1)) == date(
        2026, 9, 30
    )
    assert calendario.period_bounds(calendario.MONTHLY, "2026-02") == (
        date(2026, 2, 1),
        date(2026, 2, 28),
    )
    assert calendario.month_end("2028-02") == date(2028, 2, 29)


def test_lista_de_periodos_do_inicio_do_projeto_ate_o_corrente() -> None:
    # Do início em 01/09/2026 (semana 36) até 30/09/2026 (semana 40).
    assert calendario.project_periods(calendario.WEEKLY, date(2026, 9, 1), date(2026, 9, 30)) == [
        "2026-S36",
        "2026-S37",
        "2026-S38",
        "2026-S39",
        "2026-S40",
    ]
    assert calendario.project_periods(calendario.MONTHLY, date(2026, 7, 15), date(2026, 9, 30)) == [
        "2026-07",
        "2026-08",
        "2026-09",
    ]


def test_somar_periodos_atravessa_a_virada_do_ano() -> None:
    assert calendario.add_periods(calendario.WEEKLY, "2025-S52", 1) == "2026-S01"
    assert calendario.add_periods(calendario.MONTHLY, "2026-12", 1) == "2027-01"
    assert calendario.period_bounds(calendario.WEEKLY, "2026-S99") is None


def test_hoje_e_o_instante_vem_do_fuso_do_produto() -> None:
    assert isinstance(calendario.today(), date)
    assert calendario.now().tzinfo is UTC
    # O fuso do produto é UTC-3 sem horário de verão.
    momento = datetime(2026, 10, 5, 2, 0, tzinfo=UTC)
    assert calendario.in_product_timezone(momento).hour == 23


def test_nenhuma_funcao_de_calculo_le_o_relogio() -> None:
    ocorrencias: list[str] = []
    for caminho in sorted(FONTE.rglob("*.py")):
        if caminho == LEITOR_DO_RELOGIO:
            continue
        texto = caminho.read_text(encoding="utf-8")
        encontrados = [padrao for padrao in PADROES_DE_RELOGIO if padrao in texto]
        if encontrados:
            ocorrencias.append(f"{caminho.relative_to(FONTE)}: {', '.join(encontrados)}")
    assert ocorrencias == []
