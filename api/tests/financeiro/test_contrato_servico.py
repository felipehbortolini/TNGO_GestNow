"""Fachada da ficha do contrato: medições, aditivos e o efeito na EAC (ISSUE-032).

A medição nasce Em análise, anda só pelas transições do protótipo e a aprovação soma o bruto ao
realizado do item da EAC do contrato, no mês do período, por um fato de ``custo_erp`` (upsert por
item e mês). O aditivo nasce aprovado, muda o valor atual na leitura e prorroga o término vigente;
a SM de origem, quando informada, precisa ser aprovada e do projeto. A cascata, o saldo e o
disponível a medir são conferidos à mão com números redondos, e o contrato aceita anexo pelo tipo
de origem registrado na plataforma.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from src.core import attachment_origins, attachments
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import GeneralProfile, User
from src.core.scope import Scope
from src.modulos.financeiro import calculations, service, validation
from src.modulos.financeiro.models import (
    Contract,
    ContractMeasurement,
    ContractPaymentMilestone,
    ErpCost,
)
from src.modulos.governanca.models import ChangeRequest
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario, user_of
from tests.identidades import criar_empresa

HOJE = REFERENCE_DATE
ORIGINAL_CENTS = 100_000_000
CONTRACT_END = date(2026, 10, 30)
EAC_LEAF = "1.1.1"


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
    cenario: EacScenario,
    *,
    original_cents: int = ORIGINAL_CENTS,
    item_code: str = EAC_LEAF,
    retention_pct: int = 5,
) -> Contract:
    session = cenario.session
    empresa = criar_empresa(session, "Contratada de teste")
    count = session.scalar(select(func.count()).select_from(Contract)) or 0
    contract = Contract(
        project_id=cenario.first.id,
        company_id=empresa.id,
        eac_item_id=cenario.items.get(f"TN-EAC-001:{item_code}") if item_code else None,
        manager_id=cenario.responsible.id,
        fiscal_id=cenario.responsible.id,
        number=f"CT-2026-{count + 1:03d}",
        object="Obra de teste",
        modality="Preço unitário",
        original_value_cents=original_cents,
        start=date(2026, 1, 5),
        original_end=CONTRACT_END,
        current_end=CONTRACT_END,
        retention_pct=retention_pct,
        claim_notice_days=30,
        situation="Em execução",
    )
    session.add(contract)
    session.flush()
    return contract


def _medicao(cenario: EacScenario, measurement_id: int) -> ContractMeasurement:
    record = cenario.session.get(ContractMeasurement, measurement_id)
    assert record is not None
    return record


def _criar_medicao(
    cenario: EacScenario,
    contract: Contract,
    *,
    period: str = "2026-09",
    value: str = "1.000,00",
    perfil: GeneralProfile = GeneralProfile.MANAGER,
    **extra: str,
) -> service.MeasurementView:
    form = {"periodo": period, "bruto": value} | extra
    return service.create_measurement(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        contract_id=contract.id,
        form=form,
    )


def _avancar(
    cenario: EacScenario,
    measurement: service.MeasurementView,
    target: str,
    *,
    reason: str | None = None,
    perfil: GeneralProfile = GeneralProfile.MANAGER,
) -> service.MeasurementView:
    form = {"versao": str(_medicao(cenario, measurement.id).version)}
    if reason is not None:
        form["motivo"] = reason
    return service.transition_measurement(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        measurement_id=measurement.id,
        target=target,
        form=form,
    )


def _criar_aditivo(
    cenario: EacScenario,
    contract: Contract,
    *,
    value: str = "150.000,00",
    days: str = "21",
    perfil: GeneralProfile = GeneralProfile.MANAGER,
    **extra: str,
) -> service.AddendumView:
    form = {
        "data": "2026-05-18",
        "valor": value,
        "dias": days,
        "motivo": "Engenharia do sistema de tratamento.",
    } | extra
    return service.create_addendum(
        cenario.session,
        user=_usuario(cenario, perfil),
        scope=_escopo(cenario),
        contract_id=contract.id,
        form=form,
    )


def _ficha(
    cenario: EacScenario, contract: Contract, perfil: GeneralProfile = GeneralProfile.VIEWER
) -> service.ContractView:
    return service.contract_detail(
        cenario.session, user=_usuario(cenario, perfil), contract_id=contract.id
    )


def _criar_sm(
    cenario: EacScenario,
    *,
    code: str,
    project_id: int | None = None,
    situation: str = "Aprovada",
) -> ChangeRequest:
    sm = ChangeRequest(
        project_id=project_id or cenario.first.id,
        requester_id=cenario.responsible.id,
        code=code,
        title="Mudança de teste",
        kind="Escopo",
        origin="Interna",
        priority="Normal",
        request_date=HOJE,
        description="Mudança criada no teste da ficha do contrato.",
        situation=situation,
    )
    cenario.session.add(sm)
    cenario.session.flush()
    return sm


# ── A ficha do contrato ──────────────────────────────────────────────────


def test_ficha_do_contrato_traz_cascata_saldo_e_listas_conferidos_a_mao(
    cenario: EacScenario,
) -> None:
    contract = _criar_contrato(cenario)
    _criar_aditivo(cenario, contract, value="150.000,00", days="21")
    _criar_aditivo(
        cenario, contract, value="-50.000,00", days="0", motivo="Supressão do escopo de teste."
    )
    cenario.session.add_all(
        [
            ContractMeasurement(
                contract_id=contract.id,
                number="BM-01",
                period=date(2026, 7, 1),
                gross_cents=10_000_000,
                situation=calculations.SITUATION_PAID,
            ),
            ContractMeasurement(
                contract_id=contract.id,
                number="BM-02",
                period=date(2026, 8, 1),
                gross_cents=5_000_000,
                situation=calculations.SITUATION_APPROVED,
            ),
            ContractMeasurement(
                contract_id=contract.id,
                number="BM-03",
                period=date(2026, 9, 1),
                gross_cents=3_000_000,
                situation=calculations.SITUATION_UNDER_REVIEW,
            ),
            ContractMeasurement(
                contract_id=contract.id,
                number="BM-04",
                period=date(2026, 6, 1),
                gross_cents=2_000_000,
                situation=calculations.SITUATION_RETURNED,
                return_reason="Falta a evidência do marco.",
            ),
        ]
    )
    cenario.session.flush()

    ficha = _ficha(cenario, contract)

    assert (ficha.number, ficha.company, ficha.eac_code) == (
        "CT-2026-001",
        "Contratada de teste",
        EAC_LEAF,
    )
    assert (ficha.manager, ficha.fiscal) == ("Maria Membro", "Maria Membro")
    assert (ficha.original_value_cents, ficha.addenda_cents, ficha.current_value_cents) == (
        100_000_000,
        10_000_000,
        110_000_000,
    )
    assert (
        ficha.measured_cents,
        ficha.balance_to_invoice_cents,
        ficha.available_to_measure_cents,
    ) == (15_000_000, 95_000_000, 92_000_000)
    assert (ficha.original_end, ficha.current_end) == (CONTRACT_END, date(2026, 11, 20))
    assert [step["id"] for step in ficha.cascade] == [
        "original",
        "aditivos",
        "atual",
        "medido",
        "saldo",
    ]
    assert [step["valor"] for step in ficha.cascade] == [
        100_000_000,
        10_000_000,
        110_000_000,
        -15_000_000,
        95_000_000,
    ]
    assert [row.number for row in ficha.measurements] == ["BM-04", "BM-03", "BM-02", "BM-01"]
    assert (ficha.measurements[0].situation, ficha.measurements[0].return_reason) == (
        calculations.SITUATION_RETURNED,
        "Falta a evidência do marco.",
    )
    paga = ficha.measurements[-1]
    assert (paga.gross_cents, paga.retention_cents, paga.net_cents) == (
        10_000_000,
        500_000,
        9_500_000,
    )
    assert [row.number for row in ficha.addenda] == ["AD-02", "AD-01"]
    assert (ficha.addenda[1].value_cents, ficha.addenda[1].days) == (15_000_000, 21)
    assert (ficha.addenda[0].value_cents, ficha.addenda[0].days) == (-5_000_000, 0)


# ── O fluxo da medição e o efeito na EAC ─────────────────────────────────


def test_fluxo_da_medicao_aprova_fatura_paga_e_alimenta_o_item_da_eac(
    cenario: EacScenario,
) -> None:
    contract = _criar_contrato(cenario)
    milestone = ContractPaymentMilestone(
        contract_id=contract.id,
        number="M1",
        description="Marco de teste",
        acceptance_criteria="Aceite do marco de teste",
        pct=10,
        expected_on=CONTRACT_END,
        situation=calculations.MILESTONE_FORECAST,
    )
    cenario.session.add(milestone)
    cenario.session.flush()
    medicao = _criar_medicao(
        cenario, contract, period="2026-09", value="1.000,00", marco=str(milestone.id)
    )

    assert (medicao.number, medicao.situation, medicao.milestone_id) == (
        "BM-01",
        calculations.SITUATION_UNDER_REVIEW,
        milestone.id,
    )
    assert (medicao.gross_cents, medicao.retention_cents, medicao.net_cents) == (
        100_000,
        5_000,
        95_000,
    )

    aprovada = _avancar(cenario, medicao, calculations.SITUATION_APPROVED)

    assert aprovada.situation == calculations.SITUATION_APPROVED
    item_id = cenario.items[f"TN-EAC-001:{EAC_LEAF}"]
    facts = cenario.session.scalars(select(ErpCost).where(ErpCost.item_id == item_id)).all()
    assert [(fact.month, fact.actual_cents) for fact in facts] == [(date(2026, 9, 1), 100_000)]
    mapa = service.mapa_controle(cenario.session, scope=_escopo(cenario), reference_date=HOJE)
    linha = next(row for row in mapa.rows if row.code == EAC_LEAF)
    assert linha.actual_cents == 100_000

    faturada = _avancar(cenario, aprovada, calculations.SITUATION_INVOICED)
    paga = _avancar(cenario, faturada, calculations.SITUATION_PAID)

    assert (faturada.situation, paga.situation) == (
        calculations.SITUATION_INVOICED,
        calculations.SITUATION_PAID,
    )
    assert len(cenario.session.scalars(select(ErpCost)).all()) == 1
    assert _medicao(cenario, medicao.id).version == 4


def test_duas_medicoes_aprovadas_no_mesmo_mes_somam_num_unico_fato(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    primeira = _criar_medicao(cenario, contract, value="1.000,00")
    segunda = _criar_medicao(cenario, contract, value="500,00")

    assert (primeira.number, segunda.number) == ("BM-01", "BM-02")

    _avancar(cenario, primeira, calculations.SITUATION_APPROVED)
    _avancar(cenario, segunda, calculations.SITUATION_APPROVED)

    facts = cenario.session.scalars(select(ErpCost)).all()
    assert len(facts) == 1
    assert facts[0].actual_cents == 150_000


def test_devolucao_exige_motivo_e_libera_o_saldo(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario, original_cents=1_000_000)
    medicao = _criar_medicao(cenario, contract, value="10.000,00")

    with pytest.raises(InvalidDataError) as sem_motivo:
        _avancar(cenario, medicao, calculations.SITUATION_RETURNED, reason="   ")

    assert "motivo da devolução" in sem_motivo.value.detail[validation.FIELD_MEASUREMENT_REASON]
    assert _medicao(cenario, medicao.id).situation == calculations.SITUATION_UNDER_REVIEW

    devolvida = _avancar(
        cenario, medicao, calculations.SITUATION_RETURNED, reason="Falta a evidência do marco."
    )

    assert (devolvida.situation, devolvida.return_reason) == (
        calculations.SITUATION_RETURNED,
        "Falta a evidência do marco.",
    )
    nova = _criar_medicao(cenario, contract, value="10.000,00")
    assert nova.gross_cents == 1_000_000


def test_medicao_acima_do_saldo_e_recusada_e_nada_grava(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario, original_cents=1_000_000)

    with pytest.raises(InvalidDataError) as recusa:
        _criar_medicao(cenario, contract, value="10.000,01")

    assert "supera o saldo disponível" in recusa.value.detail[validation.FIELD_MEASUREMENT_VALUE]
    assert cenario.session.scalars(select(ContractMeasurement)).all() == []

    _criar_medicao(cenario, contract, value="10.000,00")
    with pytest.raises(InvalidDataError):
        _criar_medicao(cenario, contract, value="0,01")


def test_transicoes_fora_do_fluxo_sao_recusadas(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    medicao = _criar_medicao(cenario, contract)

    with pytest.raises(InvalidDataError) as pulo:
        _avancar(cenario, medicao, calculations.SITUATION_PAID)

    assert "não pode ir para" in pulo.value.detail[validation.FIELD_MEASUREMENT_SITUATION]

    aprovada = _avancar(cenario, medicao, calculations.SITUATION_APPROVED)
    with pytest.raises(InvalidDataError):
        _avancar(cenario, aprovada, calculations.SITUATION_APPROVED)

    outra = _criar_medicao(cenario, contract, value="500,00")
    _avancar(cenario, outra, calculations.SITUATION_RETURNED, reason="Motivo de teste.")
    with pytest.raises(InvalidDataError):
        _avancar(cenario, outra, calculations.SITUATION_INVOICED)


# ── Os aditivos ──────────────────────────────────────────────────────────


def test_aditivo_muda_o_valor_atual_e_o_termino_vigente(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)

    prorrogacao = _criar_aditivo(cenario, contract, value="150.000,00", days="21")

    assert (prorrogacao.number, prorrogacao.value_cents, prorrogacao.days) == (
        "AD-01",
        15_000_000,
        21,
    )
    assert contract.current_end == date(2026, 11, 20)
    assert contract.version == 2

    supressao = _criar_aditivo(
        cenario, contract, value="-50.000,00", days="0", motivo="Supressão do escopo."
    )

    assert (supressao.value_cents, supressao.days) == (-5_000_000, 0)
    assert contract.current_end == date(2026, 11, 20)
    assert contract.version == 2

    dias = _criar_aditivo(cenario, contract, value="0,00", days="10", motivo="Prorrogação.")

    assert dias.days == 10
    assert contract.current_end == date(2026, 11, 30)
    assert contract.version == 3

    ficha = _ficha(cenario, contract)
    assert (ficha.addenda_cents, ficha.current_value_cents) == (10_000_000, 110_000_000)
    assert ficha.current_end == date(2026, 11, 30)


def test_aditivo_registra_a_sm_aprovada_e_recusa_sm_de_outro_projeto(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    sm = _criar_sm(cenario, code="SM-TN-2026-9001")

    aditivo = _criar_aditivo(cenario, contract, sm=str(sm.id))

    assert (aditivo.change_id, aditivo.change_code) == (sm.id, "SM-TN-2026-9001")

    with pytest.raises(InvalidDataError) as desconhecida:
        _criar_aditivo(cenario, contract, sm="999999")
    assert "SM" in desconhecida.value.detail[validation.FIELD_ADDENDUM_CHANGE]

    outra = _criar_sm(cenario, project_id=cenario.second.id, code="SM-TN-2026-9002")
    with pytest.raises(InvalidDataError):
        _criar_aditivo(cenario, contract, sm=str(outra.id))

    registrada = _criar_sm(cenario, code="SM-TN-2026-9003", situation="Registrada")
    with pytest.raises(InvalidDataError):
        _criar_aditivo(cenario, contract, sm=str(registrada.id))


# ── Permissões e anexo ───────────────────────────────────────────────────


def test_leitura_para_quem_ve_e_escrita_para_quem_gere(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)

    ficha = _ficha(cenario, contract, GeneralProfile.VIEWER)
    assert ficha.number == contract.number

    with pytest.raises(AccessDeniedError):
        _criar_medicao(cenario, contract, perfil=GeneralProfile.MEMBER)
    with pytest.raises(AccessDeniedError):
        _criar_aditivo(cenario, contract, perfil=GeneralProfile.MEMBER)

    medicao = _criar_medicao(cenario, contract)
    with pytest.raises(AccessDeniedError):
        _avancar(cenario, medicao, calculations.SITUATION_APPROVED, perfil=GeneralProfile.MEMBER)

    with pytest.raises(InvalidDataError):
        service.create_measurement(
            cenario.session,
            user=_usuario(cenario, GeneralProfile.MANAGER),
            scope=Scope(project_id=None, source="padrao"),
            contract_id=contract.id,
            form={"periodo": "2026-09", "bruto": "1,00"},
        )


def test_anexo_do_contrato_e_aceito_com_o_tipo_de_origem_registrado(
    cenario: EacScenario,
) -> None:
    contract = _criar_contrato(cenario)
    armazenamento = ArmazenamentoEmMemoria()
    membro = _usuario(cenario, GeneralProfile.MEMBER)
    origem = attachment_origins.find("contrato")

    assert origem is not None and origem.module == "financeiro"

    conteudo = b"%PDF-1.7 contrato assinado"
    anexo = attachments.upload(
        cenario.session,
        user=membro,
        new=attachments.NewAttachment(
            origin_table="contrato",
            origin_record_id=contract.id,
            file_name="contrato assinado.pdf",
            content=conteudo,
        ),
        reference_date=HOJE,
        storage=armazenamento,
    )

    assert (anexo.origin_table, anexo.project_id) == ("contrato", cenario.first.id)
    assert attachments.has_evidence(
        cenario.session, origin_table="contrato", origin_record_id=contract.id
    )
    assert armazenamento.arquivos == {f"{cenario.first.id}/{anexo.id}": conteudo}
    painel = attachments.panel(
        cenario.session,
        user=membro,
        origin_table="contrato",
        origin_record_id=contract.id,
        reference_date=HOJE,
    )
    assert painel.can_view
    assert [entry.name for entry in painel.entries] == ["contrato assinado.pdf"]
