"""Validações dos marcos, claims e EOT (ISSUE-033): fluxos, evidência, percentuais e formulários.

Os fluxos são os do protótipo: o marco vai Previsto → Evidência enviada → Aprovado → Faturado →
Pago; o claim vai Notificado → Em análise → Em negociação → Acordado/Rejeitado/Em disputa →
Encerrado; a EOT vai Solicitada → Em análise → Concedida (ou parcialmente) / Negada, e a decisão
também é possível direto de Solicitada, como o protótipo permitia. O marco só aprova com evidência
e a soma dos percentuais fecha 100.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.core.errors import InvalidDataError
from src.modulos.financeiro import calculations, validation

# ── Transições do marco ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (calculations.MILESTONE_FORECAST, calculations.MILESTONE_EVIDENCE_SENT),
        (calculations.MILESTONE_EVIDENCE_SENT, calculations.MILESTONE_APPROVED),
        (calculations.MILESTONE_APPROVED, calculations.MILESTONE_INVOICED),
        (calculations.MILESTONE_INVOICED, calculations.MILESTONE_PAID),
    ],
)
def test_transicao_permitida_do_marco_passa(current: str, target: str) -> None:
    assert validation.milestone_transition_allowed(current, target)
    validation.check_milestone_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (calculations.MILESTONE_FORECAST, calculations.MILESTONE_APPROVED),
        (calculations.MILESTONE_FORECAST, calculations.MILESTONE_PAID),
        (calculations.MILESTONE_EVIDENCE_SENT, calculations.MILESTONE_INVOICED),
        (calculations.MILESTONE_APPROVED, calculations.MILESTONE_PAID),
        (calculations.MILESTONE_INVOICED, calculations.MILESTONE_APPROVED),
        (calculations.MILESTONE_PAID, calculations.MILESTONE_INVOICED),
    ],
)
def test_transicao_recusada_do_marco_traz_a_situacao_no_campo(current: str, target: str) -> None:
    assert not validation.milestone_transition_allowed(current, target)

    with pytest.raises(InvalidDataError) as erro:
        validation.check_milestone_transition(current, target)

    message = erro.value.detail["situacao"]
    assert current in message
    assert target in message


# ── Evidência e percentuais do marco ─────────────────────────────────────


def test_aprovacao_sem_evidencia_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_milestone_evidence(has_evidence=False)

    assert "anexo de evidência" in erro.value.detail["evidencias"]


def test_aprovacao_com_evidencia_passa() -> None:
    validation.check_milestone_evidence(has_evidence=True)


def test_marco_que_cabe_no_restante_passa() -> None:
    validation.check_milestone_pct(used_pct=90, new_pct=10)


def test_marco_que_passa_de_100_e_recusado_com_o_restante() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_milestone_pct(used_pct=90, new_pct=11)

    message = erro.value.detail["pct"]
    assert "passaria de 100%" in message
    assert "restam 10%" in message


def test_soma_dos_percentuais_em_100_passa() -> None:
    validation.check_milestone_pct_total([10, 20, 25, 29, 12, 4])


@pytest.mark.parametrize("pcts", [[10, 20], [99], [101], [50, 51]])
def test_soma_dos_percentuais_diferente_de_100_e_recusada(pcts: list[int]) -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.check_milestone_pct_total(pcts)

    message = erro.value.detail["pct"]
    assert "precisa ser 100%" in message
    assert f"soma atual: {sum(pcts)}%" in message


# ── Formulário do marco ──────────────────────────────────────────────────


def test_marco_valido_volta_com_percentual_e_data() -> None:
    form = validation.parse_milestone_form(
        {
            "descricao": "Mobilização e plano de projeto",
            "criterio": "Plano de projeto aprovado",
            "pct": "10",
            "prevista": "2026-01-30",
        }
    )

    assert form.description == "Mobilização e plano de projeto"
    assert form.criteria == "Plano de projeto aprovado"
    assert form.pct == 10
    assert form.expected_on == date(2026, 1, 30)


def test_marco_sem_descricao_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_milestone_form(
            {"descricao": "  ", "criterio": "Plano aprovado", "pct": "10", "prevista": "2026-01-30"}
        )

    assert "descrição" in erro.value.detail["descricao"]


def test_marco_sem_criterio_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_milestone_form(
            {"descricao": "Mobilização", "criterio": "", "pct": "10", "prevista": "2026-01-30"}
        )

    assert "critério de aceite" in erro.value.detail["criterio"]


@pytest.mark.parametrize(
    ("pct", "trecho"),
    [
        ("", "maior que zero"),
        ("0", "maior que zero"),
        ("-10", "maior que zero"),
        ("101", "até 100%"),
        ("10,5", "número inteiro"),
    ],
)
def test_marco_com_percentual_invalido_e_recusado(pct: str, trecho: str) -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_milestone_form(
            {"descricao": "Mobilização", "criterio": "Plano aprovado", "pct": pct, "prevista": ""}
        )

    assert trecho in erro.value.detail["pct"]


def test_marco_sem_data_prevista_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_milestone_form(
            {"descricao": "Mobilização", "criterio": "Plano aprovado", "pct": "10", "prevista": ""}
        )

    assert "data prevista" in erro.value.detail["prevista"]


def test_envio_de_evidencia_volta_a_data_de_conclusao() -> None:
    completed_on = validation.parse_milestone_evidence_form(
        {"conclusao": "2026-01-28", "evidencias": "ata.pdf"}
    )

    assert completed_on == date(2026, 1, 28)


def test_envio_de_evidencia_sem_data_de_conclusao_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_milestone_evidence_form({"conclusao": "sem-data"})

    assert "data de conclusão" in erro.value.detail["conclusao"]


# ── Transições do claim ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (calculations.CLAIM_NOTIFIED, calculations.CLAIM_UNDER_REVIEW),
        (calculations.CLAIM_UNDER_REVIEW, calculations.CLAIM_IN_NEGOTIATION),
        (calculations.CLAIM_UNDER_REVIEW, calculations.CLAIM_REJECTED),
        (calculations.CLAIM_IN_NEGOTIATION, calculations.CLAIM_AGREED),
        (calculations.CLAIM_IN_NEGOTIATION, calculations.CLAIM_REJECTED),
        (calculations.CLAIM_IN_NEGOTIATION, calculations.CLAIM_IN_DISPUTE),
        (calculations.CLAIM_AGREED, calculations.CLAIM_CLOSED),
        (calculations.CLAIM_REJECTED, calculations.CLAIM_IN_DISPUTE),
        (calculations.CLAIM_REJECTED, calculations.CLAIM_CLOSED),
        (calculations.CLAIM_IN_DISPUTE, calculations.CLAIM_AGREED),
        (calculations.CLAIM_IN_DISPUTE, calculations.CLAIM_CLOSED),
    ],
)
def test_transicao_permitida_do_claim_passa(current: str, target: str) -> None:
    assert validation.claim_transition_allowed(current, target)
    validation.check_claim_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (calculations.CLAIM_NOTIFIED, calculations.CLAIM_AGREED),
        (calculations.CLAIM_NOTIFIED, calculations.CLAIM_IN_NEGOTIATION),
        (calculations.CLAIM_UNDER_REVIEW, calculations.CLAIM_AGREED),
        (calculations.CLAIM_UNDER_REVIEW, calculations.CLAIM_CLOSED),
        (calculations.CLAIM_AGREED, calculations.CLAIM_IN_DISPUTE),
        (calculations.CLAIM_REJECTED, calculations.CLAIM_AGREED),
        (calculations.CLAIM_CLOSED, calculations.CLAIM_IN_DISPUTE),
    ],
)
def test_transicao_recusada_do_claim_traz_a_situacao_no_campo(current: str, target: str) -> None:
    assert not validation.claim_transition_allowed(current, target)

    with pytest.raises(InvalidDataError) as erro:
        validation.check_claim_transition(current, target)

    message = erro.value.detail["situacao"]
    assert current in message
    assert target in message


# ── Formulário do claim ──────────────────────────────────────────────────


def test_claim_valido_de_prazo_e_custo_volta_com_os_campos() -> None:
    form = validation.parse_claim_form(
        {
            "direcao": "Da contratada",
            "tipo": "Prazo e custo",
            "causa": "Liberação de área",
            "clausula": "12.3",
            "descricao": "Improdutividade pela liberação tardia da frente PR-02.",
            "evento": "2026-07-08",
            "notificacao": "2026-07-22",
            "valor": "185.000,00",
            "dias": "14",
        }
    )

    assert form.direction == "Da contratada"
    assert form.kind == "Prazo e custo"
    assert form.cause == "Liberação de área"
    assert form.clause == "12.3"
    assert form.event_date == date(2026, 7, 8)
    assert form.notification_date == date(2026, 7, 22)
    assert form.claimed_cents == 18_500_000
    assert form.claimed_days == 14


def test_claim_de_prazo_dispensa_valor_mas_exige_dias() -> None:
    form = validation.parse_claim_form(
        {
            "direcao": "Da contratada",
            "tipo": "Prazo",
            "causa": "Condição climática",
            "descricao": "Chuvas que paralisaram a concretagem.",
            "evento": "2026-06-01",
            "notificacao": "2026-06-10",
            "dias": "7",
        }
    )

    assert form.claimed_cents == 0
    assert form.claimed_days == 7


def test_claim_de_custo_dispensa_dias_mas_exige_valor() -> None:
    form = validation.parse_claim_form(
        {
            "direcao": "Do contratante",
            "tipo": "Custo",
            "causa": "Outros",
            "descricao": "Back-charge do retrabalho de solda.",
            "evento": "2026-08-19",
            "notificacao": "2026-08-26",
            "valor": "34.000,00",
        }
    )

    assert form.claimed_cents == 3_400_000
    assert form.claimed_days == 0


def test_claim_de_custo_sem_valor_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_form(
            {
                "direcao": "Da contratada",
                "tipo": "Custo",
                "causa": "Outros",
                "descricao": "Back-charge do retrabalho.",
                "evento": "2026-08-19",
                "notificacao": "2026-08-26",
            }
        )

    assert "valor pleiteado" in erro.value.detail["valor"]


def test_claim_de_prazo_sem_dias_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_form(
            {
                "direcao": "Da contratada",
                "tipo": "Prazo",
                "causa": "Condição climática",
                "descricao": "Chuvas que paralisaram a concretagem.",
                "evento": "2026-06-01",
                "notificacao": "2026-06-10",
            }
        )

    assert "dias pleiteados" in erro.value.detail["dias"]


def test_notificacao_anterior_ao_evento_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_form(
            {
                "direcao": "Da contratada",
                "tipo": "Custo",
                "causa": "Outros",
                "descricao": "Back-charge do retrabalho.",
                "evento": "2026-08-19",
                "notificacao": "2026-08-18",
                "valor": "34.000,00",
            }
        )

    assert "anterior ao evento" in erro.value.detail["notificacao"]


@pytest.mark.parametrize(
    ("field", "value", "trecho"),
    [
        ("direcao", "Da prefeitura", "direção"),
        ("tipo", "Multa", "tipo"),
        ("causa", "Astrologia", "causa"),
        ("clausula", "x" * 21, "20 caracteres"),
        ("descricao", "ab", "descrição"),
    ],
)
def test_claim_com_campo_invalido_e_recusado(field: str, value: str, trecho: str) -> None:
    form = {
        "direcao": "Da contratada",
        "tipo": "Custo",
        "causa": "Outros",
        "clausula": "12.3",
        "descricao": "Back-charge do retrabalho de solda da linha.",
        "evento": "2026-08-19",
        "notificacao": "2026-08-26",
        "valor": "34.000,00",
    }
    form[field] = value

    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_form(form)

    assert trecho in erro.value.detail[field]


# ── Atualização do claim ─────────────────────────────────────────────────


def test_claim_acordado_volta_com_o_reconhecido() -> None:
    form = validation.parse_claim_update_form(
        {
            "situacao": "Acordado",
            "reconhecido": "40.000,00",
            "dias": "21",
            "parecer": "Acordo firmado.",
        },
        claimed_cents=50_000_000,
    )

    assert form.target == calculations.CLAIM_AGREED
    assert form.recognized_cents == 4_000_000
    assert form.recognized_days == 21
    assert form.statement == "Acordo firmado."


def test_claim_acordado_sem_dias_reconhecidos_usa_zero() -> None:
    form = validation.parse_claim_update_form(
        {"situacao": "Acordado", "reconhecido": "40.000,00", "parecer": "Acordo firmado."},
        claimed_cents=50_000_000,
    )

    assert form.recognized_days == 0


def test_claim_acordado_sem_reconhecido_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_update_form(
            {"situacao": "Acordado", "parecer": "Acordo firmado."},
            claimed_cents=50_000_000,
        )

    assert "valor reconhecido" in erro.value.detail["reconhecido"]


def test_reconhecido_acima_do_pleiteado_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_update_form(
            {"situacao": "Acordado", "reconhecido": "50.000,01", "parecer": "Acordo firmado."},
            claimed_cents=5_000_000,
        )

    assert "superar o pleiteado" in erro.value.detail["reconhecido"]


def test_claim_sem_parecer_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_update_form({"situacao": "Em análise"}, claimed_cents=50_000_000)

    assert "parecer" in erro.value.detail["parecer"]


def test_claim_com_situacao_desconhecida_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_update_form(
            {"situacao": "Sumiu", "parecer": "Sem efeito."}, claimed_cents=50_000_000
        )

    assert "nova situação" in erro.value.detail["situacao"]


def test_claim_em_analise_nao_pede_reconhecido() -> None:
    form = validation.parse_claim_update_form(
        {"situacao": "Em análise", "parecer": "Parecer inicial registrado."},
        claimed_cents=50_000_000,
    )

    assert form.recognized_cents is None
    assert form.recognized_days is None


def test_claim_com_parecer_longo_e_recusado() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_claim_update_form(
            {"situacao": "Em análise", "parecer": "x" * 401}, claimed_cents=50_000_000
        )

    assert "400" in erro.value.detail["parecer"]


# ── Transições e formulários da EOT ──────────────────────────────────────


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (calculations.EXTENSION_REQUESTED, calculations.EXTENSION_UNDER_REVIEW),
        (calculations.EXTENSION_REQUESTED, calculations.EXTENSION_GRANTED),
        (calculations.EXTENSION_REQUESTED, calculations.EXTENSION_PARTIALLY_GRANTED),
        (calculations.EXTENSION_REQUESTED, calculations.EXTENSION_DENIED),
        (calculations.EXTENSION_UNDER_REVIEW, calculations.EXTENSION_GRANTED),
        (calculations.EXTENSION_UNDER_REVIEW, calculations.EXTENSION_PARTIALLY_GRANTED),
        (calculations.EXTENSION_UNDER_REVIEW, calculations.EXTENSION_DENIED),
    ],
)
def test_transicao_permitida_da_eot_passa(current: str, target: str) -> None:
    assert validation.extension_transition_allowed(current, target)
    validation.check_extension_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (calculations.EXTENSION_GRANTED, calculations.EXTENSION_UNDER_REVIEW),
        (calculations.EXTENSION_GRANTED, calculations.EXTENSION_PARTIALLY_GRANTED),
        (calculations.EXTENSION_PARTIALLY_GRANTED, calculations.EXTENSION_GRANTED),
        (calculations.EXTENSION_DENIED, calculations.EXTENSION_UNDER_REVIEW),
        (calculations.EXTENSION_UNDER_REVIEW, calculations.EXTENSION_REQUESTED),
    ],
)
def test_transicao_recusada_da_eot_traz_a_situacao_no_campo(current: str, target: str) -> None:
    assert not validation.extension_transition_allowed(current, target)

    with pytest.raises(InvalidDataError) as erro:
        validation.check_extension_transition(current, target)

    message = erro.value.detail["situacao"]
    assert current in message
    assert target in message


def test_eot_valida_volta_com_o_claim_opcional() -> None:
    form = validation.parse_extension_form(
        {
            "claim": "3",
            "evento": "Revisão tardia dos desenhos de montagem do moinho.",
            "dias": "45",
            "marco": "Montagem mecânica do moinho",
            "metodo": "Análise por janelas",
        }
    )

    assert form.claim_id == 3
    assert form.requested_days == 45
    assert form.affected_milestone == "Montagem mecânica do moinho"
    assert form.method == "Análise por janelas"


def test_eot_sem_claim_e_aceita() -> None:
    form = validation.parse_extension_form(
        {
            "evento": "Interferência não mapeada no subsolo da fundação F-12.",
            "dias": "30",
            "marco": "Término das fundações",
            "metodo": "Análise de impacto no tempo",
        }
    )

    assert form.claim_id is None


@pytest.mark.parametrize(
    ("field", "value", "trecho"),
    [
        ("evento", "", "evento causador"),
        ("dias", "0", "dias solicitados"),
        ("marco", "", "marco contratual afetado"),
        ("metodo", "Achismo", "método"),
    ],
)
def test_eot_com_campo_invalido_e_recusada(field: str, value: str, trecho: str) -> None:
    form = {
        "evento": "Interferência não mapeada no subsolo da fundação.",
        "dias": "30",
        "marco": "Término das fundações",
        "metodo": "Análise de impacto no tempo",
    }
    form[field] = value

    with pytest.raises(InvalidDataError) as erro:
        validation.parse_extension_form(form)

    assert trecho in erro.value.detail[field]


def test_eot_concedida_integralmente_volta_com_os_dias() -> None:
    form = validation.parse_extension_decision_form(
        {
            "situacao": "Concedida",
            "dias": "30",
            "classificacao": "Justificável e compensável",
            "parecer": "Atraso no caminho crítico comprovado.",
        },
        requested_days=30,
    )

    assert form.target == calculations.EXTENSION_GRANTED
    assert form.granted_days == 30
    assert form.classification == "Justificável e compensável"


def test_eot_concedida_com_dias_diferentes_do_solicitado_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_extension_decision_form(
            {
                "situacao": "Concedida",
                "dias": "21",
                "classificacao": "Justificável e compensável",
                "parecer": "Atraso comprovado.",
            },
            requested_days=30,
        )

    assert "Concedida integralmente" in erro.value.detail["dias"]


def test_eot_concedida_parcialmente_com_menos_dias_passa() -> None:
    form = validation.parse_extension_decision_form(
        {
            "situacao": "Concedida parcialmente",
            "dias": "21",
            "classificacao": "Justificável não compensável",
            "parecer": "Só parte do atraso é imputável ao contratante.",
        },
        requested_days=30,
    )

    assert form.target == calculations.EXTENSION_PARTIALLY_GRANTED
    assert form.granted_days == 21


def test_eot_parcial_com_todos_os_dias_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_extension_decision_form(
            {
                "situacao": "Concedida parcialmente",
                "dias": "30",
                "classificacao": "Justificável e compensável",
                "parecer": "Atraso comprovado.",
            },
            requested_days=30,
        )

    assert "Parcial precisa ser menor" in erro.value.detail["dias"]


def test_eot_negada_dispensa_dias_e_classificacao() -> None:
    form = validation.parse_extension_decision_form(
        {"situacao": "Negada", "parecer": "Sem nexo de causalidade com o contrato."},
        requested_days=30,
    )

    assert form.target == calculations.EXTENSION_DENIED
    assert form.granted_days == 0
    assert form.classification == ""


def test_eot_com_decisao_desconhecida_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_extension_decision_form(
            {"situacao": "Talvez", "parecer": "Em avaliação."}, requested_days=30
        )

    assert "decisão" in erro.value.detail["situacao"]


def test_eot_concedida_sem_classificacao_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_extension_decision_form(
            {"situacao": "Concedida", "dias": "30", "parecer": "Atraso comprovado."},
            requested_days=30,
        )

    assert "classificação" in erro.value.detail["classificacao"]


def test_eot_sem_parecer_e_recusada() -> None:
    with pytest.raises(InvalidDataError) as erro:
        validation.parse_extension_decision_form({"situacao": "Negada"}, requested_days=30)

    assert "parecer" in erro.value.detail["parecer"]
