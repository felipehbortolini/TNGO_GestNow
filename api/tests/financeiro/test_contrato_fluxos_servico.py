"""Fachada dos marcos, claims e EOT da ficha do contrato (ISSUE-033).

O marco vai Previsto → Evidência enviada → Aprovado → Faturado → Pago e só aprova com o anexo
de evidência gravado; a soma dos percentuais não passa de 100. O claim anda pelo fluxo e, ao
ser Acordado, abre a SM na Governança na mesma transação, gravando o vínculo em ``mudanca_id``;
o alerta de notificação aparece na visão no último dia do prazo e no primeiro dia de atraso.
A EOT concedida prorroga o término vigente e cria a SM do cronograma; a medição de marco
faturada ou paga leva o marco junto.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy import func, select

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import Attachment
from src.core.rbac import GeneralProfile, User
from src.core.scope import Scope
from src.modulos.financeiro import calculations, service, validation
from src.modulos.financeiro.models import (
    Contract,
    ContractClaim,
    ContractPaymentMilestone,
    ContractTimeExtension,
)
from src.modulos.governanca import service as governanca
from src.modulos.governanca.models import ChangeRequest
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario, user_of
from tests.identidades import criar_empresa

HOJE = REFERENCE_DATE
ORIGINAL_CENTS = 100_000_000
CONTRACT_END = date(2026, 10, 30)
EVIDENCE_BYTES = b"%PDF-1.7 evidencia do marco"


class FalhaSimuladaError(Exception):
    """A falha que o teste injeta depois de a SM ter sido criada, para provar o rollback."""


def _escopo(cenario: EacScenario) -> Scope:
    return Scope(project_id=cenario.first.id, source="url")


def _usuario(cenario: EacScenario, perfil: GeneralProfile) -> User:
    colaborador = {
        GeneralProfile.VIEWER: cenario.viewer,
        GeneralProfile.MEMBER: cenario.member,
        GeneralProfile.MANAGER: cenario.manager,
    }[perfil]
    return user_of(colaborador, cenario.session, perfil)


def _criar_contrato(
    cenario: EacScenario, *, claim_notice_days: int = 30, retention_pct: int = 5
) -> Contract:
    session = cenario.session
    empresa = criar_empresa(session, "Contratada de teste")
    count = session.scalar(select(func.count()).select_from(Contract)) or 0
    contract = Contract(
        project_id=cenario.first.id,
        company_id=empresa.id,
        eac_item_id=cenario.items["TN-EAC-001:1.1.1"],
        manager_id=cenario.responsible.id,
        fiscal_id=cenario.responsible.id,
        number=f"CT-2026-{count + 1:03d}",
        object="Obra de teste",
        modality="Preço unitário",
        original_value_cents=ORIGINAL_CENTS,
        start=date(2026, 1, 5),
        original_end=CONTRACT_END,
        current_end=CONTRACT_END,
        retention_pct=retention_pct,
        claim_notice_days=claim_notice_days,
        situation="Em execução",
    )
    session.add(contract)
    session.flush()
    return contract


def _ficha(
    cenario: EacScenario, contract: Contract, perfil: GeneralProfile = GeneralProfile.VIEWER
) -> service.ContractView:
    return service.contract_detail(
        cenario.session, user=_usuario(cenario, perfil), contract_id=contract.id
    )


def _criar_marco(
    cenario: EacScenario,
    contract: Contract,
    *,
    pct: str = "10",
    prevista: str = "2026-01-30",
    perfil: GeneralProfile = GeneralProfile.MANAGER,
) -> service.MilestoneView:
    return service.create_milestone(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        contract_id=contract.id,
        form={
            "descricao": "Mobilização e plano de projeto",
            "criterio": "Plano de projeto aprovado",
            "pct": pct,
            "prevista": prevista,
        },
    )


def _enviar_evidencia(
    cenario: EacScenario,
    marco: service.MilestoneView,
    *,
    storage: ArmazenamentoEmMemoria,
    perfil: GeneralProfile = GeneralProfile.MANAGER,
) -> service.MilestoneView:
    return service.send_milestone_evidence(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        milestone_id=marco.id,
        form={"conclusao": "2026-01-28", "versao": str(marco.version)},
        reference_date=HOJE,
        file_name="evidencia do marco.pdf",
        content=EVIDENCE_BYTES,
        storage=storage,
    )


def _aprovar(
    cenario: EacScenario,
    marco: service.MilestoneView,
    *,
    perfil: GeneralProfile = GeneralProfile.MANAGER,
) -> service.MilestoneView:
    return service.approve_milestone(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        milestone_id=marco.id,
        form={"versao": str(marco.version)},
    )


def _criar_medicao(
    cenario: EacScenario,
    contract: Contract,
    *,
    milestone_id: int,
    perfil: GeneralProfile = GeneralProfile.MANAGER,
) -> service.MeasurementView:
    return service.create_measurement(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        contract_id=contract.id,
        form={
            "periodo": "2026-09",
            "bruto": "1.000,00",
            "marco": str(milestone_id),
        },
    )


def _avancar_medicao(
    cenario: EacScenario,
    medicao: service.MeasurementView,
    target: str,
    *,
    perfil: GeneralProfile = GeneralProfile.MANAGER,
) -> service.MeasurementView:
    return service.transition_measurement(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        measurement_id=medicao.id,
        target=target,
        form={"versao": str(medicao.version)},
    )


def _criar_claim(
    cenario: EacScenario,
    contract: Contract,
    *,
    tipo: str = "Custo",
    valor: str = "34.000,00",
    perfil: GeneralProfile = GeneralProfile.MANAGER,
    **extra: str,
) -> service.ClaimView:
    form: dict[str, str] = {
        "direcao": "Da contratada",
        "tipo": tipo,
        "causa": "Outros",
        "clausula": "18.1",
        "descricao": "Back-charge do retrabalho de solda da linha.",
        "evento": "2026-08-19",
        "notificacao": "2026-08-26",
        "valor": valor,
        "dias": "0",
    }
    form.update(extra)
    return service.create_claim(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        contract_id=contract.id,
        form=form,
    )


def _atualizar_claim(
    cenario: EacScenario,
    claim: service.ClaimView,
    target: str,
    *,
    parecer: str = "Parecer registrado.",
    perfil: GeneralProfile = GeneralProfile.MANAGER,
    **extra: str,
) -> service.ClaimView:
    form: dict[str, str] = {"situacao": target, "parecer": parecer, "versao": str(claim.version)}
    form.update(extra)
    return service.update_claim(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        claim_id=claim.id,
        form=form,
        reference_date=HOJE,
    )


def _decidir_claim(
    cenario: EacScenario,
    claim: service.ClaimView,
    target: str,
    *,
    parecer: str = "Acordo firmado entre as partes.",
    **extra: str,
) -> service.ClaimView:
    form: dict[str, str] = {"situacao": target, "parecer": parecer, "versao": str(claim.version)}
    form.update(extra)
    return service.decide_claim(
        cenario.session,
        user=_usuario(cenario, GeneralProfile.MANAGER),
        scope=_escopo(cenario),
        claim_id=claim.id,
        form=form,
        reference_date=HOJE,
    )


def _criar_eot(
    cenario: EacScenario,
    contract: Contract,
    *,
    claim_id: int | None = None,
    dias: str = "30",
    perfil: GeneralProfile = GeneralProfile.MANAGER,
) -> service.ExtensionView:
    form: dict[str, str] = {
        "evento": "Interferência não mapeada no subsolo da fundação F-12.",
        "dias": dias,
        "marco": "Término das fundações",
        "metodo": "Análise de impacto no tempo",
    }
    if claim_id is not None:
        form["claim"] = str(claim_id)
    return service.create_extension(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        contract_id=contract.id,
        form=form,
        reference_date=HOJE,
    )


def _decidir_eot(
    cenario: EacScenario,
    eot: service.ExtensionView,
    target: str,
    *,
    dias: str | None = None,
    perfil: GeneralProfile = GeneralProfile.MANAGER,
) -> service.ExtensionView:
    form: dict[str, str] = {
        "situacao": target,
        "parecer": "Atraso comprovado no caminho crítico.",
        "versao": str(eot.version),
    }
    if dias is not None:
        form["dias"] = dias
    if target != calculations.EXTENSION_DENIED:
        form["classificacao"] = "Justificável e compensável"
    return service.decide_extension(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        extension_id=eot.id,
        form=form,
        reference_date=HOJE,
    )


def _contar_sms(cenario: EacScenario) -> int:
    return cenario.session.scalar(select(func.count()).select_from(ChangeRequest)) or 0


# ── Marcos ───────────────────────────────────────────────────────────────


def test_marco_so_aprova_com_evidencia_e_o_anexo_vira_evidencia_do_marco(
    cenario: EacScenario,
) -> None:
    contract = _criar_contrato(cenario)
    marco = _criar_marco(cenario, contract, pct="10")

    assert (marco.number, marco.situation, marco.pct) == (
        "M1",
        calculations.MILESTONE_FORECAST,
        10,
    )
    assert (marco.value_cents, marco.retention_cents, marco.has_evidence) == (
        10_000_000,
        500_000,
        False,
    )

    armazenamento = ArmazenamentoEmMemoria()
    enviado = _enviar_evidencia(cenario, marco, storage=armazenamento)

    assert (enviado.situation, enviado.completed_on, enviado.has_evidence) == (
        calculations.MILESTONE_EVIDENCE_SENT,
        date(2026, 1, 28),
        True,
    )
    anexo = cenario.session.get(Attachment, enviado.attachment_id)
    assert anexo is not None
    assert (anexo.origin_table, anexo.origin_record_id, anexo.project_id) == (
        "contrato_marco_pagamento",
        marco.id,
        cenario.first.id,
    )
    assert armazenamento.arquivos == {f"{cenario.first.id}/{anexo.id}": EVIDENCE_BYTES}

    aprovado = _aprovar(cenario, enviado)

    assert aprovado.situation == calculations.MILESTONE_APPROVED
    ficha = _ficha(cenario, contract)
    assert ficha.milestone_pct_total == 10
    assert (ficha.milestones[0].situation, ficha.milestones[0].has_evidence) == (
        calculations.MILESTONE_APPROVED,
        True,
    )


def test_marco_em_evidencia_sem_anexo_e_recusado_na_aprovacao(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    marco = ContractPaymentMilestone(
        contract_id=contract.id,
        number="M1",
        description="Mobilização e plano de projeto",
        acceptance_criteria="Plano de projeto aprovado",
        pct=10,
        expected_on=date(2026, 1, 30),
        completed_on=date(2026, 1, 28),
        situation=calculations.MILESTONE_EVIDENCE_SENT,
    )
    cenario.session.add(marco)
    cenario.session.flush()

    with pytest.raises(InvalidDataError) as erro:
        service.approve_milestone(
            cenario.session,
            user=_usuario(cenario, GeneralProfile.MANAGER),
            scope=_escopo(cenario),
            milestone_id=marco.id,
        )

    assert "anexo de evidência" in erro.value.detail[validation.FIELD_MILESTONE_EVIDENCE]
    assert marco.situation == calculations.MILESTONE_EVIDENCE_SENT
    assert marco.version == 1


def test_soma_de_percentuais_acima_de_100_e_recusada_e_nada_grava(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    _criar_marco(cenario, contract, pct="60")

    with pytest.raises(InvalidDataError) as erro:
        _criar_marco(cenario, contract, pct="50", prevista="2026-02-28")

    assert "passaria de 100%" in erro.value.detail[validation.FIELD_MILESTONE_PCT]
    assert "restam 40%" in erro.value.detail[validation.FIELD_MILESTONE_PCT]
    assert len(cenario.session.scalars(select(ContractPaymentMilestone)).all()) == 1


def test_medicao_de_marco_faturada_e_paga_atualiza_o_marco(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    marco = _aprovar(
        cenario,
        _enviar_evidencia(
            cenario, _criar_marco(cenario, contract), storage=ArmazenamentoEmMemoria()
        ),
    )
    medicao = _criar_medicao(cenario, contract, milestone_id=marco.id)
    medicao = _avancar_medicao(cenario, medicao, calculations.SITUATION_APPROVED)
    medicao = _avancar_medicao(cenario, medicao, calculations.SITUATION_INVOICED)

    faturado = cenario.session.get(ContractPaymentMilestone, marco.id)
    assert faturado is not None
    assert faturado.situation == calculations.MILESTONE_INVOICED

    _avancar_medicao(cenario, medicao, calculations.SITUATION_PAID)

    pago = cenario.session.get(ContractPaymentMilestone, marco.id)
    assert pago is not None
    assert pago.situation == calculations.MILESTONE_PAID


# ── Claims ───────────────────────────────────────────────────────────────


def test_claim_acordado_cria_sm_na_governanca_e_grava_o_vinculo(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    claim = _criar_claim(cenario, contract)
    gestor = _usuario(cenario, GeneralProfile.MANAGER)

    em_analise = _atualizar_claim(cenario, claim, calculations.CLAIM_UNDER_REVIEW)
    em_negociacao = _atualizar_claim(cenario, em_analise, calculations.CLAIM_IN_NEGOTIATION)
    acordado = _decidir_claim(
        cenario,
        em_negociacao,
        calculations.CLAIM_AGREED,
        reconhecido="30.000,00",
        dias="0",
    )

    assert (acordado.situation, acordado.recognized_cents, acordado.recognized_days) == (
        calculations.CLAIM_AGREED,
        3_000_000,
        0,
    )
    assert acordado.change_id is not None
    sm = cenario.session.get(ChangeRequest, acordado.change_id)
    assert sm is not None
    assert (sm.situation, sm.kind, sm.origin, sm.project_id) == (
        "Registrada",
        "Custo",
        "Contratada",
        cenario.first.id,
    )
    assert sm.requester_id == gestor.person_id
    assert sm.title == f"Claim {claim.code} acordado"
    assert "Acordo firmado entre as partes." in sm.description
    assert acordado.change_code == sm.code

    ficha = _ficha(cenario, contract)
    assert (ficha.claims[0].situation, ficha.claims[0].change_code) == (
        calculations.CLAIM_AGREED,
        sm.code,
    )


def test_falha_ao_criar_a_sm_desfaz_a_atualizacao_da_mesma_transacao(
    cenario: EacScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _criar_contrato(cenario)
    claim = _criar_claim(cenario, contract)
    em_analise = _atualizar_claim(cenario, claim, calculations.CLAIM_UNDER_REVIEW)
    em_negociacao = _atualizar_claim(cenario, em_analise, calculations.CLAIM_IN_NEGOTIATION)
    antes = _contar_sms(cenario)

    real = governanca.create_change

    def falha_apos_criar(*args: Any, **kwargs: Any) -> Any:
        real(*args, **kwargs)
        raise FalhaSimuladaError

    monkeypatch.setattr(governanca, "create_change", falha_apos_criar)
    savepoint = cenario.session.begin_nested()
    with pytest.raises(FalhaSimuladaError):
        _decidir_claim(cenario, em_negociacao, calculations.CLAIM_AGREED, reconhecido="30.000,00")

    assert _contar_sms(cenario) == antes + 1
    savepoint.rollback()

    assert _contar_sms(cenario) == antes
    recarregado = cenario.session.get(ContractClaim, claim.id)
    assert recarregado is not None
    assert (recarregado.situation, recarregado.change_id) == (
        calculations.CLAIM_IN_NEGOTIATION,
        None,
    )


def test_alerta_de_notificacao_no_ultimo_dia_e_no_primeiro_de_atraso(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario, claim_notice_days=30)
    _criar_claim(cenario, contract, valor="1.000,00", evento="2026-08-01", notificacao="2026-08-31")
    _criar_claim(cenario, contract, valor="1.000,00", evento="2026-08-01", notificacao="2026-09-01")

    ficha = _ficha(cenario, contract)
    atrasado, no_prazo = ficha.claims

    assert (no_prazo.notification_days, no_prazo.notification_late) == (30, False)
    assert (atrasado.notification_days, atrasado.notification_late) == (31, True)


def test_claim_rejeitado_zera_o_reconhecido_e_encerrado_guarda_a_data(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    claim = _criar_claim(cenario, contract)
    em_analise = _atualizar_claim(cenario, claim, calculations.CLAIM_UNDER_REVIEW)

    rejeitado = _atualizar_claim(
        cenario, em_analise, calculations.CLAIM_REJECTED, parecer="Sem nexo de causalidade."
    )

    assert (rejeitado.recognized_cents, rejeitado.recognized_days) == (0, 0)
    assert rejeitado.change_id is None

    encerrado = _atualizar_claim(cenario, rejeitado, calculations.CLAIM_CLOSED)

    assert (encerrado.situation, encerrado.closed_on) == (calculations.CLAIM_CLOSED, HOJE)


# ── Extensões de prazo ───────────────────────────────────────────────────


def test_eot_concedida_prorroga_o_termino_vigente_e_cria_sm(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    claim = _criar_claim(cenario, contract, tipo="Prazo", valor="0,00", dias="30")
    eot = _criar_eot(cenario, contract, claim_id=claim.id)

    assert (eot.situation, eot.is_open, eot.claim_code) == (
        calculations.EXTENSION_REQUESTED,
        True,
        claim.code,
    )

    concedida = _decidir_eot(
        cenario,
        eot,
        calculations.EXTENSION_PARTIALLY_GRANTED,
        dias="21",
    )

    assert (concedida.situation, concedida.granted_days, concedida.is_open) == (
        calculations.EXTENSION_PARTIALLY_GRANTED,
        21,
        False,
    )
    assert concedida.decided_on == HOJE
    assert contract.current_end == date(2026, 11, 20)
    assert concedida.change_id is not None
    sm = cenario.session.get(ChangeRequest, concedida.change_id)
    assert sm is not None
    assert (sm.kind, sm.origin, sm.project_id) == ("Prazo", "Contratada", cenario.first.id)
    assert sm.title == f"EOT {eot.code}: {calculations.EXTENSION_PARTIALLY_GRANTED}"
    assert "Atraso comprovado no caminho crítico." in sm.description

    ficha = _ficha(cenario, contract)
    assert (ficha.current_end, ficha.extensions[0].change_code) == (date(2026, 11, 20), sm.code)


def test_eot_negada_nao_prorroga_nem_cria_sm(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    eot = _criar_eot(cenario, contract)
    antes = _contar_sms(cenario)

    negada = _decidir_eot(cenario, eot, calculations.EXTENSION_DENIED)

    assert (negada.situation, negada.change_id, negada.granted_days) == (
        calculations.EXTENSION_DENIED,
        None,
        0,
    )
    assert negada.decided_on == HOJE
    assert contract.current_end == CONTRACT_END
    assert _contar_sms(cenario) == antes


def test_eot_com_claim_de_outro_contrato_e_recusada(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    outro = _criar_contrato(cenario)
    claim_do_outro = _criar_claim(cenario, outro, tipo="Prazo", valor="0,00", dias="10")

    with pytest.raises(InvalidDataError) as erro:
        _criar_eot(cenario, contract, claim_id=claim_do_outro.id)

    assert "não pertence ao contrato" in erro.value.detail[validation.FIELD_EXTENSION_CLAIM]


# ── Transições recusadas e permissões ────────────────────────────────────


def test_transicoes_fora_do_fluxo_sao_recusadas(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    marco = _criar_marco(cenario, contract)

    with pytest.raises(InvalidDataError) as pulo_do_marco:
        service.transition_milestone(
            cenario.session,
            user=_usuario(cenario, GeneralProfile.MANAGER),
            scope=_escopo(cenario),
            milestone_id=marco.id,
            target=calculations.MILESTONE_PAID,
        )

    assert "não pode ir para" in pulo_do_marco.value.detail[validation.FIELD_MILESTONE_SITUATION]

    claim = _criar_claim(cenario, contract)
    with pytest.raises(InvalidDataError) as pulo_do_claim:
        _atualizar_claim(
            cenario,
            claim,
            calculations.CLAIM_AGREED,
            reconhecido="1.000,00",
        )

    assert "não pode ir para" in pulo_do_claim.value.detail[validation.FIELD_CLAIM_SITUATION]

    eot = _criar_eot(cenario, contract)
    negada = _decidir_eot(cenario, eot, calculations.EXTENSION_DENIED)
    with pytest.raises(InvalidDataError) as eot_terminal:
        _decidir_eot(cenario, negada, calculations.EXTENSION_GRANTED, dias="30")

    assert "não pode ir para" in eot_terminal.value.detail[validation.FIELD_EXTENSION_SITUATION]

    outra_eot = _criar_eot(cenario, contract, dias="30")
    with pytest.raises(InvalidDataError) as decisao_restrita:
        _decidir_eot(cenario, outra_eot, calculations.EXTENSION_UNDER_REVIEW)

    assert "decisão" in decisao_restrita.value.detail[validation.FIELD_EXTENSION_SITUATION]


def test_escrita_dos_fluxos_e_de_quem_gera_e_leitura_de_quem_ve(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)

    with pytest.raises(AccessDeniedError):
        _criar_marco(cenario, contract, perfil=GeneralProfile.MEMBER)
    with pytest.raises(AccessDeniedError):
        _criar_claim(cenario, contract, perfil=GeneralProfile.MEMBER)
    with pytest.raises(AccessDeniedError):
        _criar_eot(cenario, contract, perfil=GeneralProfile.MEMBER)

    ficha = _ficha(cenario, contract, GeneralProfile.VIEWER)

    assert (ficha.milestones, ficha.claims, ficha.extensions) == ((), (), ())
    assert ficha.milestone_pct_total == 0


def test_escolha_do_alvo_fora_da_decisao_do_claim_e_recusada(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    claim = _criar_claim(cenario, contract)

    with pytest.raises(InvalidDataError) as erro:
        _decidir_claim(cenario, claim, calculations.CLAIM_IN_NEGOTIATION)

    assert "Acordado ou Rejeitado" in erro.value.detail[validation.FIELD_CLAIM_SITUATION]


def test_codigos_do_claim_e_da_eot_sao_sequenciais(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    primeiro = _criar_claim(cenario, contract, valor="1.000,00")
    segundo = _criar_claim(cenario, contract, valor="1.000,00")
    eot = _criar_eot(cenario, contract)

    assert primeiro.code == "CLM-TN-2026-0001"
    assert segundo.code == "CLM-TN-2026-0002"
    assert eot.code == "EOT-TN-2026-0001"
    assert cenario.session.get(ContractTimeExtension, eot.id) is not None
