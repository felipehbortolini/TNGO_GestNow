"""Cálculos das horas efetivas (ISSUE-047): CP, utilização, HH, amostragem, Pareto e paradas.

Fórmulas puras, com a data injetada (D6): cada teste afirma o número que a pessoa lê.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from src.modulos.planejamento import calculations as c

D = Decimal


def _turno(chegada: str, inicio: str, termino: str) -> c.ShiftTimes:
    return c.ShiftTimes(
        arrival=time.fromisoformat(chegada),
        start=time.fromisoformat(inicio),
        end=time.fromisoformat(termino),
    )


def test_a_capacidade_produtiva_soma_a_execucao_dos_dois_turnos() -> None:
    figuras = c.field_day_figures(
        day=date(2026, 9, 24),
        crew=10,
        morning=_turno("07:30", "08:00", "11:00"),
        afternoon=_turno("13:00", "13:05", "17:05"),
        daily_hours=D("8.8"),
    )

    assert figuras.morning_execution == D("3")
    assert figuras.afternoon_execution == D("4")
    assert figuras.capacity == D("7")
    assert figuras.utilization == D("79.5")
    assert figuras.week == "2026-S39"


def test_o_atraso_e_o_almoco_saem_dos_horarios() -> None:
    figuras = c.field_day_figures(
        day=date(2026, 9, 24),
        crew=10,
        morning=_turno("07:30", "08:00", "11:00"),
        afternoon=_turno("13:00", "13:05", "17:05"),
        daily_hours=D("8.8"),
    )

    assert figuras.morning_delay_min == 30
    assert figuras.afternoon_delay_min == 5
    assert figuras.lunch_min == 120


def test_as_horas_homem_efetivas_e_improdutivas_multiplicam_pelo_efetivo() -> None:
    figuras = c.field_day_figures(
        day=date(2026, 9, 24),
        crew=10,
        morning=_turno("07:30", "08:00", "11:00"),
        afternoon=_turno("13:00", "13:05", "17:05"),
        daily_hours=D("8.8"),
    )

    assert figuras.effective_hh == D("70")
    assert figuras.idle_hh == D("18")


def test_a_jornada_sem_ordem_de_horarios_nao_tem_execucao() -> None:
    figuras = c.field_day_figures(
        day=date(2026, 9, 24),
        crew=4,
        morning=_turno("07:30", "11:00", "08:00"),
        afternoon=_turno("13:00", "13:05", "17:05"),
        daily_hours=D("8.8"),
    )

    assert figuras.morning_execution is None
    assert figuras.capacity == D("4")
    assert figuras.idle_hh == D("19.2")


def test_o_resumo_da_capacidade_media_os_dias_e_soma_as_horas() -> None:
    manha = _turno("07:30", "08:00", "11:00")
    tarde = _turno("13:00", "13:05", "17:05")
    primeiro = c.field_day_figures(
        day=date(2026, 9, 24), crew=10, morning=manha, afternoon=tarde, daily_hours=D("8.8")
    )
    segundo = c.field_day_figures(
        day=date(2026, 9, 25), crew=20, morning=manha, afternoon=tarde, daily_hours=D("8.8")
    )

    resumo = c.capacity_summary([primeiro, segundo], daily_hours=D("8.8"))

    assert resumo.records == 2
    assert resumo.average_crew == D("15")
    assert resumo.capacity == D("7")
    assert resumo.utilization == D("79.5")
    assert resumo.effective_hh == D("210")
    assert resumo.idle_hh == D("54")
    assert resumo.morning == c.ShiftTimes(time(7, 30), time(8, 0), time(11, 0))


def test_o_resumo_sem_jornadas_nao_tem_capacidade() -> None:
    resumo = c.capacity_summary([], daily_hours=D("8.8"))

    assert resumo.records == 0
    assert resumo.capacity is None
    assert resumo.utilization is None
    assert resumo.effective_hh == D("0")
    assert resumo.morning is None


def test_o_percentual_da_amostragem_divide_cada_estado_pelo_observado() -> None:
    resumo = c.sample_share(
        [
            c.SampleCounts(working=6, transit=2, stopped=2),
            c.SampleCounts(working=0, transit=0, stopped=5),
        ]
    )

    assert (resumo.records, resumo.people) == (2, 15)
    assert (resumo.working, resumo.transit, resumo.stopped) == (6, 2, 7)
    assert (resumo.working_pct, resumo.transit_pct, resumo.stopped_pct) == (
        D("40.00"),
        D("13.33"),
        D("46.67"),
    )


def test_o_pareto_ordena_decrescente_e_acumula() -> None:
    catalogo = ("A", "B", "C", "D")
    pareto = c.reason_pareto({"C": 5, "A": 3, "B": 2}, catalog=catalogo)

    assert [(linha.reason, linha.total) for linha in pareto] == [("C", 5), ("A", 3), ("B", 2)]
    assert pareto[0].percent == D("50.0")
    assert pareto[0].accumulated == D("50.0")
    assert pareto[1].accumulated == D("80.0")
    assert pareto[2].accumulated == D("100.0")


def test_o_empate_do_pareto_fica_com_a_ordem_do_catalogo() -> None:
    pareto = c.reason_pareto({"C": 2, "A": 2}, catalog=("A", "C"))

    assert [linha.reason for linha in pareto] == ["A", "C"]


def test_o_motivo_fora_do_catalogo_entra_depois() -> None:
    pareto = c.reason_pareto({"Z": 9, "A": 1}, catalog=("A",))

    assert [linha.reason for linha in pareto] == ["Z", "A"]


def test_a_paralisacao_de_efetivo_vira_hhora() -> None:
    figuras = c.stoppage_figures(
        day=date(2026, 9, 24),
        kind=c.STOPPAGE_CREW,
        reason="Falta de material",
        responsibility="Cliente",
        quantity=D(16),
        start=time(13, 20),
        end=time(16, 40),
    )

    assert figuras.hours == D("3.33")
    assert figuras.total == D("53.3")
    assert figuras.external is True
    assert figuras.week == "2026-S39"


def test_a_paralisacao_de_maquina_vira_mhora() -> None:
    figuras = c.stoppage_figures(
        day=date(2026, 8, 12),
        kind=c.STOPPAGE_MACHINE,
        reason="Chuva / condição climática",
        responsibility="Clima",
        quantity=D(3),
        start=time(13, 20),
        end=time(16, 40),
    )

    assert figuras.total == D("10.0")
    assert figuras.external is False


def test_o_resumo_das_paralisacoes_separa_efetivo_e_maquina() -> None:
    efetivo = c.stoppage_figures(
        day=date(2026, 9, 24),
        kind=c.STOPPAGE_CREW,
        reason="Falta de material",
        responsibility="Cliente",
        quantity=D(16),
        start=time(13, 20),
        end=time(16, 40),
    )
    clima = c.stoppage_figures(
        day=date(2026, 9, 25),
        kind=c.STOPPAGE_CREW,
        reason="Chuva / condição climática",
        responsibility="Clima",
        quantity=D(10),
        start=time(13, 10),
        end=time(15, 10),
    )
    maquina = c.stoppage_figures(
        day=date(2026, 9, 24),
        kind=c.STOPPAGE_MACHINE,
        reason="Quebra de máquina / equipamento",
        responsibility="Terceiros",
        quantity=D(1),
        start=time(8, 0),
        end=time(12, 0),
    )

    resumo = c.stoppage_summary([efetivo, clima, maquina])

    assert resumo.events == 3
    assert resumo.crew_hours == D("73.3")
    assert resumo.machine_hours == D("4.0")
    assert resumo.client_hours == D("53.3")
    assert resumo.weather_hours == D("20.0")
    assert resumo.external_hours == D("53.3")
    assert [linha.key for linha in resumo.by_responsibility] == ["Cliente", "Clima"]
    assert [linha.key for linha in resumo.machine_by_reason] == ["Quebra de máquina / equipamento"]


def test_as_faixas_da_utilizacao_trabalho_e_atraso() -> None:
    assert c.utilization_band(D("80"), target=D("75")) == "success"
    assert c.utilization_band(D("70"), target=D("75")) == "warning"
    assert c.utilization_band(D("60"), target=D("75")) == "danger"
    assert c.utilization_band(None, target=D("75")) is None

    assert c.working_band(D("61"), target=D("60")) == "success"
    assert c.working_band(D("55"), target=D("60")) == "warning"
    assert c.working_band(D("40"), target=D("60")) == "danger"

    assert c.start_delay_band(D("10"), c.DEFAULT_DELAY_BANDS) == "success"
    assert c.start_delay_band(D("20"), c.DEFAULT_DELAY_BANDS) == "warning"
    assert c.start_delay_band(D("40"), c.DEFAULT_DELAY_BANDS) == "danger"


def test_a_janela_do_periodo_respeita_a_data_de_referencia() -> None:
    referencia = date(2026, 9, 25)

    assert c.hours_window(
        c.PERIOD_WEEK, cut_week="2026-S39", window_weeks=4, reference_date=referencia
    ) == (date(2026, 9, 21), referencia)
    assert c.hours_window(
        c.PERIOD_WINDOW, cut_week="2026-S39", window_weeks=4, reference_date=referencia
    ) == (date(2026, 8, 31), referencia)
    assert c.hours_window(
        c.PERIOD_ALL, cut_week="2026-S39", window_weeks=4, reference_date=referencia
    ) == (None, referencia)


def test_a_janela_de_um_corte_passado_termina_na_semana_do_corte() -> None:
    referencia = date(2026, 9, 25)

    assert c.hours_window(
        c.PERIOD_WEEK, cut_week="2026-S37", window_weeks=4, reference_date=referencia
    ) == (date(2026, 9, 7), date(2026, 9, 13))


def test_o_sentido_da_duracao_e_o_mesmo_do_prototipo() -> None:
    assert c.shift_hours(time(8, 0), time(11, 30)) == D("3.5")
    assert c.shift_hours(time(11, 0), time(8, 0)) is None
