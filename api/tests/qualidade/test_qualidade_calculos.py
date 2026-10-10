"""Os cálculos puros da Qualidade (ISSUE-068): prazos, situação, verificação e reincidência."""

from __future__ import annotations

from datetime import date, timedelta

from src.modulos.qualidade import calculations

REFERENCIA = date(2026, 9, 25)
PRAZOS = {"critica": 15, "maior": 30, "menor": 45}


def test_o_prazo_segue_a_severidade_do_parametro() -> None:
    assert calculations.treatment_deadline(REFERENCIA, "Crítica", PRAZOS) == date(2026, 10, 10)
    assert calculations.treatment_deadline(REFERENCIA, "Maior", PRAZOS) == date(2026, 10, 25)
    assert calculations.treatment_deadline(REFERENCIA, "Menor", PRAZOS) == date(2026, 11, 9)


def test_a_fronteira_do_vencimento_e_o_dia_seguinte_ao_prazo() -> None:
    prazo = date(2026, 9, 25)

    assert not calculations.is_overdue(prazo, "Ação corretiva", REFERENCIA)
    assert calculations.is_overdue(prazo, "Ação corretiva", REFERENCIA + timedelta(days=1))
    assert calculations.days_overdue(prazo, "Ação corretiva", REFERENCIA + timedelta(days=3)) == 3
    assert calculations.days_overdue(prazo, "Ação corretiva", REFERENCIA) == 0


def test_o_prazo_so_vale_ate_a_acao_corretiva() -> None:
    prazo = date(2026, 8, 1)

    assert calculations.is_overdue(prazo, "Aberta", REFERENCIA)
    assert calculations.is_overdue(prazo, "Em análise de causa", REFERENCIA)
    assert not calculations.is_overdue(prazo, "Verificação de eficácia", REFERENCIA)
    assert not calculations.is_overdue(prazo, "Encerrada", REFERENCIA)
    assert not calculations.is_overdue(prazo, "Cancelada", REFERENCIA)


def test_a_verificacao_vencida_e_a_prevista_anterior_a_referencia() -> None:
    esperada = date(2026, 10, 5)

    assert not calculations.is_verification_overdue("Verificação de eficácia", esperada, REFERENCIA)
    assert calculations.is_verification_overdue(
        "Verificação de eficácia", esperada, date(2026, 10, 6)
    )
    assert not calculations.is_verification_overdue("Ação corretiva", esperada, date(2026, 11, 1))
    assert not calculations.is_verification_overdue(
        "Verificação de eficácia", None, date(2026, 11, 1)
    )


def test_dias_aberta_para_no_encerramento() -> None:
    assert calculations.days_open(date(2026, 9, 1), None, REFERENCIA) == 24
    assert calculations.days_open(date(2026, 9, 1), date(2026, 9, 10), REFERENCIA) == 9


def test_a_proxima_etapa_por_situacao() -> None:
    assert calculations.next_step("Aberta") == "Atribuir a análise de causa"
    assert (
        calculations.next_step("Em análise de causa") == "Registrar causa raiz, disposição e ações"
    )
    assert calculations.next_step("Ação corretiva") == "Concluir as ações e enviar para verificação"
    assert calculations.next_step("Verificação de eficácia") == "Verificar a eficácia"
    assert calculations.next_step("Encerrada") == ""
    assert calculations.next_step("Cancelada") == ""


def test_a_reincidencia_conta_as_verificacoes_ineficazes_da_trilha() -> None:
    verificacao = {"situacao": "Verificação de eficácia"}
    acao = {"situacao": "Ação corretiva"}
    trilha = [
        (None, {"situacao": "Aberta"}),
        ({"situacao": "Em análise de causa"}, acao),
        (verificacao, acao),
        (acao, acao),
        (acao, verificacao),
        (verificacao, acao),
        (acao, {"situacao": "Encerrada"}),
    ]

    assert calculations.recurrence_count(trilha) == 2
    assert calculations.recurrence_count([]) == 0


def test_o_tempo_medio_de_tratamento_arredonda_e_sem_encerrada_e_nulo() -> None:
    assert calculations.average_treatment_days([10, 11, 12]) == 11
    assert calculations.average_treatment_days([10, 11]) == 11
    assert calculations.average_treatment_days([]) is None
