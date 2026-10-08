"""Os indicadores do dashboard, portados do app (ISSUE-056).

Os testes do app viram estes: a curva fecha em 100% do previsto, a ordem é a do
calendário e não a do texto, a curva sem dados é vazia, unidades diferentes não se
somam, a medida respeita a unidade, o nível de calor respeita as fronteiras e a
evolução manda quantidade e não percentual, ignorando a empresa sem atividade na
semana. Nada aqui lê o relógio nem o banco: são as funções puras de ``calculations``.
"""

from __future__ import annotations

import pytest

from src.modulos.programacao_semanal import calculations, presentation


def _activity(
    week: str,
    identity: str,
    planned: float,
    done: float,
    *,
    company: str = "Alfa",
    location: str = "Frente 1",
    foreman: str = "",
    unit: str = "m³",
    situation: str = calculations.SITUATION_PUBLISHED,
    approval: str = calculations.APPROVAL_APPROVED,
    night: float = 0.0,
) -> calculations.IndicatorActivity:
    return calculations.IndicatorActivity(
        week=week,
        identity=identity,
        description=f"Serviço {identity}",
        project_label="TN-2026-014 · Projeto da programação",
        location=location,
        company=company,
        foreman=foreman,
        unit=unit,
        situation=situation,
        approval=approval,
        figures=calculations.figures_of(
            [planned / calculations.DAYS] * calculations.DAYS,
            [done / calculations.DAYS] * calculations.DAYS,
            [night / calculations.DAYS] * calculations.DAYS,
        ),
    )


def _curve(activities: list[calculations.IndicatorActivity]) -> list[calculations.CurvePoint]:
    return calculations.curve_points(
        [
            calculations.CurveActivity(
                week=item.week,
                identity=item.identity,
                planned_total=item.figures.planned_total,
                done_total=item.figures.done_total,
            )
            for item in activities
        ]
    )


# ── Curva S ──────────────────────────────────────────────────────────────


def test_a_curva_fecha_em_cem_por_cento_do_previsto() -> None:
    """O previsto acumulado do horizonte inteiro tem de fechar em 100.

    É o teste que pegaria o erro de usar o previsto da SEMANA como denominador:
    ali cada semana marcava 100% e o acumulado ia a 600.
    """
    activities = [_activity(f"S.{n}/2026", "A-1", 100, 50) for n in (28, 29, 30)] + [
        _activity(f"S.{n}/2026", "A-2", 200, 200) for n in (28, 29, 30)
    ]

    curve = _curve(activities)

    assert len(curve) == 3
    assert curve[-1].planned_accumulated == pytest.approx(100, abs=0.1)
    assert curve[-1].base_accumulated == pytest.approx(100, abs=0.1)
    # A-1 entregou metade e A-2 tudo, com peso igual: 75%.
    assert curve[-1].done_accumulated == pytest.approx(75, abs=0.1)


def test_a_curva_ordena_por_calendario_e_nao_por_texto() -> None:
    activities = [
        _activity("S.02/2027", "A-1", 10, 10),
        _activity("S.51/2026", "A-1", 10, 10),
    ]

    assert [point.week for point in _curve(activities)] == ["S.51/2026", "S.02/2027"]


def test_a_curva_sem_dados_e_vazia() -> None:
    assert _curve([]) == []


def test_unidades_diferentes_nao_sao_somadas() -> None:
    """Duas atividades em unidades incompatíveis, uma bem maior em número.

    Se a curva somasse quantidade bruta, os 3.000 m³ afogariam os 2 und. Com peso
    igual por atividade, uma parada e outra completa dão 50%.
    """
    activities = [
        _activity("S.30/2026", "SOLO", 3000, 0, unit="m³"),
        _activity("S.30/2026", "TRAFO", 2, 2, unit="und"),
    ]

    assert _curve(activities)[-1].done_accumulated == pytest.approx(50, abs=0.1)


# ── Medida e faixas de leitura ───────────────────────────────────────────


def test_a_medida_respeita_a_unidade() -> None:
    """A unidade muda o formato, porque muda o que o número significa."""
    assert presentation.format_quantity(2, "und") == "2"
    assert presentation.format_quantity(2.4, "und") == "2"  # meia unidade não existe
    assert presentation.format_quantity(2.5, "m³") == "2,5"  # meio metro cúbico existe
    assert (
        presentation.format_quantity(1234.5, "kg") == "1.234"
    )  # acima de 100 o decimal só ocupa espaço
    assert presentation.format_quantity(120000, "kg") == "120 mil"  # senão não cabe na célula
    assert presentation.format_quantity(0, "kg") == "—"  # zero é ausência, e se lê como tal


def test_o_nivel_de_calor_respeita_as_fronteiras() -> None:
    """A escala do mapa de calor é a mesma do módulo: 60 e 80, em três tons.

    O dia sem previsão não tem tom: não é 0% de aderência, é ausência de plano.
    """
    assert calculations.heat_band(None) == ""
    assert calculations.heat_band(0) == "erro"
    assert calculations.heat_band(59.9) == "erro"
    assert calculations.heat_band(60) == "atencao"
    assert calculations.heat_band(79.9) == "atencao"
    assert calculations.heat_band(80) == "ok"
    assert calculations.heat_band(140) == "ok"

    faixas = calculations.heat_faixas()
    assert faixas[0]["de"] == 80.0
    assert faixas[-1]["vazia"] is True


# ── Evolução por contratada ──────────────────────────────────────────────


def test_a_evolucao_manda_quantidade_e_nao_percentual() -> None:
    """O gráfico agrupa semanas em meses, e aderência de mês não é média.

    Com duas semanas de tamanhos diferentes, a média das aderências semanais e a
    aderência do mês dão números distintos. Mandar quantidade é o que deixa o
    desenho fazer a conta certa em qualquer nível de agrupamento.
    """
    activities = [
        _activity("S.28/2026", "A-1", 100, 100, company="Alfa"),  # 100%
        _activity("S.29/2026", "A-2", 900, 450, company="Alfa"),  # 50%
    ]

    evolution = calculations.evolution_by_company(activities)

    assert evolution.series == ("Alfa",)
    assert len(evolution.points) == 2
    first = evolution.points[0].totals["Alfa"]
    assert (first.planned, first.done) == (100.0, 100.0)

    total_planned = sum(point.totals["Alfa"].planned for point in evolution.points)
    total_done = sum(point.totals["Alfa"].done for point in evolution.points)
    assert round(total_done / total_planned * 100, 1) == 55.0  # a conta certa
    assert round((100 + 50) / 2, 1) == 75.0  # a média, que seria a errada


def test_a_evolucao_ignora_empresa_sem_atividade_na_semana() -> None:
    activities = [
        _activity("S.28/2026", "A-1", 100, 50, company="Alfa"),
        _activity("S.29/2026", "B-1", 100, 50, company="Beta"),
    ]

    points = calculations.evolution_by_company(activities).points

    assert "Beta" not in points[0].totals
    assert "Alfa" not in points[1].totals


# ── Gargalos e turnos ────────────────────────────────────────────────────


def test_os_gargalos_sao_as_atividades_abaixo_da_faixa_de_atencao() -> None:
    """A lista de ação do app: PPC abaixo de 60, pior primeiro, sem plano fora."""
    activities = [
        _activity("S.31/2026", "OK-1", 100, 100),
        _activity("S.31/2026", "MEIO-1", 100, 70),
        _activity("S.31/2026", "BAIXO-1", 100, 30),
        _activity("S.31/2026", "BAIXO-2", 100, 0),
        _activity("S.31/2026", "SEM-PLANO", 0, 10),
    ]

    items = calculations.bottlenecks(activities)

    assert [item.identity for item in items] == ["BAIXO-2", "BAIXO-1"]
    assert items[0].idle_days == calculations.DAYS
    assert items[1].ppc == 30.0


def test_os_turnos_separam_o_dia_da_noite() -> None:
    activity = _activity("S.31/2026", "T-1", 70, 42, night=14)

    shifts = calculations.shifts_by_day([activity])

    assert len(shifts) == calculations.DAYS
    assert shifts[0].day_shift == 6.0
    assert shifts[0].night_shift == 2.0
    assert shifts[0].done == 8.0
    assert shifts[0].planned == 10.0


def test_a_distribuicao_conta_fluxo_aprovacao_e_faixa() -> None:
    activities = [
        _activity("S.31/2026", "PUB-1", 100, 100),
        _activity(
            "S.31/2026",
            "VAL-1",
            100,
            0,
            situation=calculations.SITUATION_VALIDATED,
            approval=calculations.APPROVAL_PENDING,
        ),
        _activity(
            "S.31/2026",
            "DRAFT-1",
            100,
            0,
            situation=calculations.SITUATION_DRAFT,
            approval=calculations.APPROVAL_PENDING,
        ),
    ]

    blocks = calculations.situation_distribution(activities)
    flow, approval, band = blocks

    assert [segment.value for segment in flow.segments] == [1, 1, 1]
    assert [segment.value for segment in approval.segments] == [1, 0, 2]
    assert [segment.value for segment in band.segments] == [1, 0, 2]
