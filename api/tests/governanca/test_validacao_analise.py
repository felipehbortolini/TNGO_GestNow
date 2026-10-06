"""Validação da análise de impacto (ISSUE-024): 422 por campo, custo zero dos tipos especiais, dinheiro."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.core.errors import InvalidDataError
from src.modulos.governanca import models, validation

HOJE = date(2026, 10, 6)
REGRAS = validation.ImpactRules(
    kind="Custo", budget_cents=1_000_000, manager_limit_percent=Decimal(1)
)


def _form(**campos: str) -> dict[str, str]:
    base = {
        "custo": "0",
        "prazo_dias": "0",
        "marco_contratual": "nao",
        "escopo": "Sem impacto",
        "qualidade": "Sem impacto",
        "riscos": "Sem impacto",
        "sms": "Sem impacto",
        "contrato": "Sem impacto",
        "alcada": "Gerente do projeto",
    }
    base.update(campos)
    return base


def _mensagens(form: dict[str, str], regras: validation.ImpactRules = REGRAS) -> dict[str, str]:
    with pytest.raises(InvalidDataError) as erro:
        validation.validate_impact(form, rules=regras)
    return dict(erro.value.detail)


@pytest.mark.parametrize(
    ("texto", "centavos"),
    [
        ("0", 0),
        ("1.234,56", 123_456),
        ("1234,5", 123_450),
        ("-500", -50_000),
        ("R$ 10,00", 1_000),
        ("1234.56", None),
        ("abc", None),
        ("", None),
        ("1,234", None),
    ],
)
def test_dinheiro_em_reais_vira_centavos(texto: str, centavos: int | None) -> None:
    assert validation.parse_money(texto) == centavos


def test_analise_completa_passa_e_leva_a_alcada_pedida() -> None:
    entrada = validation.validate_impact(_form(custo="-100,00", prazo_dias="-3"), rules=REGRAS)
    assert entrada.cost_cents == -10_000
    assert entrada.term_days == -3
    assert entrada.resource_source is None
    assert entrada.required_authority == models.AUTHORITY_MANAGER


def test_analise_vazia_recusa_cada_campo_obrigatorio() -> None:
    mensagens = _mensagens({})
    assert set(mensagens) >= {
        "custo",
        "prazo_dias",
        "marco_contratual",
        "escopo",
        "qualidade",
        "riscos",
        "sms",
        "contrato",
        "alcada",
    }


def test_texto_curto_demais_e_longo_demais_sao_recusados() -> None:
    assert "mínimo de 3" in _mensagens(_form(escopo="ab"))["escopo"]
    assert "máximo de 300" in _mensagens(_form(contrato="x" * 301))["contrato"]
    assert validation.validate_impact(_form(escopo="abc", contrato="x" * 300), rules=REGRAS)


def test_prazo_em_dias_inteiros() -> None:
    assert "dias inteiros" in _mensagens(_form(prazo_dias="1,5"))["prazo_dias"]


def test_custo_positivo_exige_a_fonte_do_recurso() -> None:
    assert "fonte do recurso" in _mensagens(_form(custo="10,00"))["fonte_recurso"]
    entrada = validation.validate_impact(
        _form(custo="10,00", fonte_recurso="Aditivo de orçamento"), rules=REGRAS
    )
    assert entrada.resource_source == "Aditivo de orçamento"


def test_custo_zero_ou_negativo_descarta_a_fonte() -> None:
    entrada = validation.validate_impact(
        _form(custo="0", fonte_recurso="Aditivo de orçamento"), rules=REGRAS
    )
    assert entrada.resource_source is None


def test_rebaixar_a_alcada_e_recusado_e_elevar_e_aceito() -> None:
    muito = _form(custo="100,01", fonte_recurso="Aditivo de orçamento", alcada="Gerente do projeto")
    assert "nunca rebaixada" in _mensagens(muito)["alcada"]
    elevada = _form(custo="1,00", alcada="Comitê")
    entrada = validation.validate_impact(elevada, rules=REGRAS)
    assert entrada.authority == models.AUTHORITY_COMMITTEE
    assert entrada.required_authority == models.AUTHORITY_MANAGER


def test_marco_contratual_exige_o_comite() -> None:
    assert "alçada" in _mensagens(_form(marco_contratual="sim"))["alcada"]


def test_reserva_gerencial_so_vai_ao_comite() -> None:
    form = _form(custo="1,00", fonte_recurso=models.SOURCE_MANAGEMENT_RESERVE)
    assert "reserva gerencial" in _mensagens(form)["alcada"]


def test_remanejamento_tem_custo_zero_e_pede_as_transferencias() -> None:
    regras = validation.ImpactRules(
        kind=models.TYPE_REALLOCATION, budget_cents=1_000_000, manager_limit_percent=Decimal(1)
    )
    mensagens = _mensagens(_form(custo="10,00"), regras)
    assert "custo zero" in mensagens["custo"]
    assert "ao menos uma transferência" in mensagens["remanejamentos"]


def test_remanejamento_valido_guarda_as_transferencias_e_a_alcada_vem_do_total() -> None:
    regras = validation.ImpactRules(
        kind=models.TYPE_REALLOCATION, budget_cents=1_000_000, manager_limit_percent=Decimal(1)
    )
    pequeno = _form(
        remanejamento_origem_1="2.1.3",
        remanejamento_destino_1="1.2.2",
        remanejamento_valor_1="100,00",
    )
    entrada = validation.validate_impact(pequeno, rules=regras)
    assert entrada.transfers == (validation.TransferInput("2.1.3", "1.2.2", 10_000),)
    assert entrada.required_authority == models.AUTHORITY_MANAGER
    grande = _form(
        remanejamento_origem_1="2.1.3",
        remanejamento_destino_1="1.2.2",
        remanejamento_valor_1="100,01",
    )
    assert "nunca rebaixada" in _mensagens(grande, regras)["alcada"]


@pytest.mark.parametrize(
    ("origem", "destino", "valor", "trecho"),
    [
        ("", "1.2.2", "10,00", "origem e o de destino"),
        ("2.1.3", "2.1.3", "10,00", "diferentes"),
        ("2.1.3", "1.2.2", "0", "maior que zero"),
        ("2.1.3", "1.2.2", "", "maior que zero"),
    ],
)
def test_transferencia_incompleta_ou_invalida_e_recusada(
    origem: str, destino: str, valor: str, trecho: str
) -> None:
    regras = validation.ImpactRules(
        kind=models.TYPE_REALLOCATION, budget_cents=1_000_000, manager_limit_percent=Decimal(1)
    )
    form = _form(
        remanejamento_origem_1=origem, remanejamento_destino_1=destino, remanejamento_valor_1=valor
    )
    assert trecho in _mensagens(form, regras)["remanejamentos"]


def test_liberacao_de_reserva_pede_a_reserva_e_o_valor_e_vai_ao_comite() -> None:
    regras = validation.ImpactRules(
        kind=models.TYPE_RESERVE_RELEASE, budget_cents=1_000_000, manager_limit_percent=Decimal(1)
    )
    mensagens = _mensagens(_form(custo="5,00"), regras)
    assert "custo zero" in mensagens["custo"]
    assert "liberacao_reserva" in mensagens
    assert "liberacao_valor" in mensagens
    assert "Comitê" in mensagens["alcada"]
    completo = _form(alcada="Comitê", liberacao_reserva="Contingência", liberacao_valor="1.000,00")
    entrada = validation.validate_impact(completo, rules=regras)
    assert (entrada.release_reserve, entrada.release_cents) == ("Contingência", 100_000)


def test_itens_da_eac_sem_repeticao_e_em_ordem() -> None:
    entrada = validation.validate_impact(
        _form(itens_eac="2.1.3; 1.2.2, 2.1.3  3.1.1"), rules=REGRAS
    )
    assert entrada.item_codes == ("2.1.3", "1.2.2", "3.1.1")


def test_inicio_da_analise_pede_responsavel_e_prazo_nao_anterior_a_hoje() -> None:
    pessoas = frozenset({7})
    with pytest.raises(InvalidDataError) as erro:
        validation.validate_analysis_start({}, people_ids=pessoas, reference_date=HOJE)
    assert set(erro.value.detail) == {"responsavel_id", "prazo"}
    with pytest.raises(InvalidDataError) as ontem:
        validation.validate_analysis_start(
            {"responsavel_id": "7", "prazo": "2026-10-05"}, people_ids=pessoas, reference_date=HOJE
        )
    assert "anterior" in ontem.value.detail["prazo"]
    hoje = validation.validate_analysis_start(
        {"responsavel_id": "7", "prazo": "2026-10-06"}, people_ids=pessoas, reference_date=HOJE
    )
    assert hoje.deadline == HOJE
    with pytest.raises(InvalidDataError) as outro:
        validation.validate_analysis_start(
            {"responsavel_id": "8", "prazo": "2026-10-06"}, people_ids=pessoas, reference_date=HOJE
        )
    assert "responsavel_id" in outro.value.detail
