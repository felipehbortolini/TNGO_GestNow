"""Cálculos puros do Relato do período (ISSUE-044): períodos, fronteiras e ordem. A data entra como argumento (D6)."""

from __future__ import annotations

from datetime import date

from src.modulos.planejamento import calculations as calc
from src.modulos.planejamento.validation import MONTHLY, WEEKLY

HOJE = date(2026, 9, 25)  # sexta-feira da semana ISO 39
INICIO = date(2026, 8, 20)


def test_periodo_corrente_e_aceito_nas_duas_pontas() -> None:
    assert (
        calc.report_period_error(WEEKLY, "2026-S39", project_start=INICIO, reference_date=HOJE)
        is None
    )
    assert (
        calc.report_period_error(MONTHLY, "2026-09", project_start=INICIO, reference_date=HOJE)
        is None
    )
    # a semana e o mês do início do projeto ainda valem
    assert (
        calc.report_period_error(WEEKLY, "2026-S34", project_start=INICIO, reference_date=HOJE)
        is None
    )
    assert (
        calc.report_period_error(MONTHLY, "2026-08", project_start=INICIO, reference_date=HOJE)
        is None
    )


def test_periodo_futuro_e_recusado() -> None:
    erro = calc.report_period_error(WEEKLY, "2026-S40", project_start=INICIO, reference_date=HOJE)
    assert erro == calc.NOT_STARTED_MESSAGE
    erro = calc.report_period_error(MONTHLY, "2026-10", project_start=INICIO, reference_date=HOJE)
    assert erro == calc.NOT_STARTED_MESSAGE


def test_periodo_anterior_ao_inicio_do_projeto_e_recusado() -> None:
    assert (
        calc.report_period_error(WEEKLY, "2026-S33", project_start=INICIO, reference_date=HOJE)
        == calc.BEFORE_PROJECT_MESSAGE
    )
    assert (
        calc.report_period_error(MONTHLY, "2026-07", project_start=INICIO, reference_date=HOJE)
        == calc.BEFORE_PROJECT_MESSAGE
    )


def test_periodo_malformado_pede_a_escolha() -> None:
    for kind, period in (
        (WEEKLY, ""),
        (WEEKLY, "2026-S54"),
        (MONTHLY, "2026-13"),
        (MONTHLY, "2026-S39"),
    ):
        assert (
            calc.report_period_error(kind, period, project_start=INICIO, reference_date=HOJE)
            == calc.PERIOD_REQUIRED_MESSAGE
        )


def test_projeto_sem_inicio_comeca_na_data_de_referencia() -> None:
    assert calc.report_period_range(WEEKLY, None, HOJE) == ("2026-S39", "2026-S39")


def test_relatos_devidos_deixam_o_periodo_corrente_de_fora() -> None:
    assert calc.expected_report_count(WEEKLY, INICIO, HOJE) == 5  # S34 a S38
    assert calc.expected_report_count(MONTHLY, INICIO, HOJE) == 1  # agosto
    assert calc.expected_report_count(WEEKLY, HOJE, HOJE) == 0
    assert calc.expected_report_count(MONTHLY, None, HOJE) == 0


def test_periodo_anterior_e_proximo_na_virada_do_ano() -> None:
    assert calc.previous_period(WEEKLY, date(2027, 1, 4)) == "2026-S53"
    assert calc.previous_period(MONTHLY, date(2026, 1, 15)) == "2025-12"
    assert calc.next_period(MONTHLY, "2026-12") == "2027-01"
    assert calc.next_period(WEEKLY, "2026-S53") == "2027-S01"
    assert calc.next_period(WEEKLY, "lixo") is None


def test_nomes_do_periodo() -> None:
    assert calc.period_name(WEEKLY, "2026-S38") == "Semana 38 · 14/09 a 20/09/2026"
    assert calc.period_name(MONTHLY, "2026-08") == "Agosto de 2026"
    assert calc.short_period_name(WEEKLY, "2026-S08") == "S08"
    assert calc.short_period_name(MONTHLY, "2026-08") == "ago/26"
    assert calc.period_name(WEEKLY, "lixo") == "lixo"


def test_opcoes_do_formulario_marcam_corrente_e_ja_relatados() -> None:
    options = calc.period_options(
        WEEKLY, project_start=INICIO, reference_date=HOJE, taken=["2026-S38"]
    )
    assert [option.period for option in options][:2] == ["2026-S39", "2026-S38"]
    assert [option.in_progress for option in options][:2] == [True, False]
    assert [option.taken for option in options][:2] == [False, True]
    assert calc.first_free_period(options) == "2026-S39"
    assert calc.choose_period(options, "2026-S38") == "2026-S39"  # ocupado: cai no primeiro livre
    assert calc.choose_period(options, "2026-S37") == "2026-S37"
    assert calc.first_free_period([]) == ""


def test_periodo_anterior_para_copiar_nao_precisa_ser_o_vizinho() -> None:
    assert calc.latest_period_before(["2026-S35", "2026-S37", "2026-S39"], "2026-S39") == "2026-S37"
    assert calc.latest_period_before(["2026-S39"], "2026-S39") is None
    assert calc.latest_period_before([], "2026-S39") is None


def test_ordem_mais_recente_primeiro_e_mensal_antes_do_semanal_no_empate() -> None:
    chaves = [
        (WEEKLY, "2026-S35"),
        (MONTHLY, "2026-08"),
        (WEEKLY, "2026-S36"),
        (WEEKLY, "2026-S31"),
    ]
    ordenados = sorted(chaves, key=lambda item: calc.report_order_key(*item))
    assert ordenados[0] == (WEEKLY, "2026-S36")
    # início igual (semana que abre no dia 1): o mensal vem antes
    assert calc.report_order_key(MONTHLY, "2026-06") < calc.report_order_key(WEEKLY, "2026-S23")


def test_contagens_e_textos_dos_pontos() -> None:
    assert calc.nature_counts(["Ameaça", "Oportunidade", "Ameaça"]) == (2, 1)
    assert calc.plural(1, "ameaça") == "1 ameaça"
    assert calc.plural(0, "ameaça") == "0 ameaças"
    assert calc.points_summary(2, 1) == "2 ameaças · 1 oportunidade"


def test_deslocamento_de_periodos_para_a_carga() -> None:
    ancora = date(2026, 9, 25)
    assert calc.period_offset(WEEKLY, anchor=ancora, reference_date=date(2026, 10, 9)) == 2
    assert calc.period_offset(MONTHLY, anchor=ancora, reference_date=date(2026, 10, 1)) == 1
    assert calc.period_offset(WEEKLY, anchor=ancora, reference_date=ancora) == 0
