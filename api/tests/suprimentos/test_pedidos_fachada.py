"""As fachadas da recomendação, da aprovação e da emissão (ISSUE-060).

O processo do cenário percorre o fluxo da ISSUE-059 até a negociação e cada ação nova passa pela
fachada, dentro da transação do teste: a recomendação com as suas justificativas, a aprovação com
a segregação de funções (403), a alçada e o saldo da EAC, a devolução com motivo e a emissão do
pedido (cronograma, compromisso na EAC e ação de diligenciamento) ou do contrato (fachada do
Financeiro). O teste transversal prova que uma falha no meio da emissão não deixa nada gravado.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry
from src.core.scope import Scope
from src.modulos.central_acoes.models import Action
from src.modulos.financeiro import service as financeiro
from src.modulos.financeiro.models import Contract, ErpCost
from src.modulos.suprimentos import calculations, service, validation
from src.modulos.suprimentos.models import (
    PackageMilestone,
    ProcessProposal,
    PurchaseOrder,
    PurchaseOrderMilestone,
    PurchaseProcess,
    Supplier,
)
from tests.apoio_pacotes import REFERENCIA
from tests.apoio_processos import (
    CenarioProcessos,
    montar_cenario_processos,
    proposta_do_cenario,
    rfx_do_cenario,
)
from tests.armazenamento_falso import ArmazenamentoEmMemoria

ADIANTADO = date(2026, 9, 20)


class FalhaSimuladaError(RuntimeError):
    """Falha forçada no meio da transação, só para provar a atomicidade."""


@pytest.fixture
def cenario(sessao: Session) -> CenarioProcessos:
    """O cenário do processo no lugar do cenário de fornecedores do conftest."""
    return montar_cenario_processos(sessao)


def _scope(cenario: CenarioProcessos, *, portfolio: bool = False) -> Scope:
    return Scope(project_id=None if portfolio else cenario.projeto.id, source="url")


def _milestone(sessao: Session, pacote_id: int, key: str) -> PackageMilestone:
    return sessao.scalars(
        select(PackageMilestone).where(
            PackageMilestone.package_id == pacote_id, PackageMilestone.milestone == key
        )
    ).one()


def _processo(sessao: Session, pacote_id: int) -> PurchaseProcess:
    return sessao.scalars(
        select(PurchaseProcess).where(PurchaseProcess.package_id == pacote_id)
    ).one()


def _historico(sessao: Session, processo_id: int) -> list[dict[str, object]]:
    statement = (
        select(AuditEntry)
        .where(
            AuditEntry.entity == service.PROCESS_HISTORY_ENTITY,
            AuditEntry.record_id == processo_id,
        )
        .order_by(AuditEntry.id)
    )
    return [entry.after or {} for entry in sessao.scalars(statement)]


def _linha(sessao: Session, cenario: CenarioProcessos) -> service.ProcessLine:
    line = service.find_process(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        reference_date=REFERENCIA,
    )
    assert line is not None
    return line


def _registrar_proposta(sessao: Session, cenario: CenarioProcessos, **campos: object) -> None:
    service.register_proposal(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=proposta_do_cenario(cenario, **campos),
        reference_date=REFERENCIA,
        file_name="proposta.pdf",
        content=b"%PDF-1.7 proposta",
        storage=ArmazenamentoEmMemoria(),
    )


def _fluxo_ate_negociacao(
    sessao: Session, cenario: CenarioProcessos, *, com_livre: bool = False
) -> None:
    """O processo do cenário percorrido até Negociação, com duas propostas aprovadas.

    ``com_livre`` acrescenta uma quarta proposta sem cadastro, aprovada tecnicamente, para o
    caso da recomendação que exige cadastro.
    """
    service.issue_rfx(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=rfx_do_cenario(cenario),
        reference_date=REFERENCIA,
    )
    _registrar_proposta(sessao, cenario, value_cents=40_000_000)
    _registrar_proposta(
        sessao, cenario, company_id=cenario.fornecedores[1].id, value_cents=45_000_000
    )
    _registrar_proposta(
        sessao, cenario, company_id=cenario.fornecedores[2].id, value_cents=38_000_000
    )
    if com_livre:
        _registrar_proposta(
            sessao, cenario, company_id=None, name="Sem Cadastro", value_cents=39_000_000
        )
    service.close_receipt(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.ClosingInput(date=date(2026, 8, 31)),
        reference_date=REFERENCIA,
    )
    line = _linha(sessao, cenario)
    notas = {
        cenario.fornecedores[0].id: (90, True),
        cenario.fornecedores[1].id: (80, True),
        cenario.fornecedores[2].id: (70, False),
    }
    items = tuple(
        validation.TechnicalEvaluation(
            proposal_id=proposal.id,
            score=notas.get(proposal.company_id or 0, (60, True))[0],
            approved=notas.get(proposal.company_id or 0, (60, True))[1],
            deviations="Sem desvios.",
            version=proposal.version,
        )
        for proposal in line.proposals
    )
    service.equalize_technically(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.TechnicalInput(
            date=date(2026, 9, 10),
            evaluations=items,
            justification="Mercado local com poucos fornecedores para o escopo completo.",
        ),
        reference_date=REFERENCIA,
    )
    service.equalize_commercially(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.CommercialInput(
            date=date(2026, 9, 15),
            weight_technical=50,
            weight_commercial=50,
            version=_processo(sessao, cenario.pacote.id).version,
        ),
        reference_date=REFERENCIA,
    )


def _proposta_aprovada(sessao: Session, cenario: CenarioProcessos, posicao: int) -> ProcessProposal:
    line = _linha(sessao, cenario)
    proposta = line.proposals[posicao]
    row = sessao.get(ProcessProposal, proposta.id)
    assert row is not None
    return row


def _recomendar(
    sessao: Session, cenario: CenarioProcessos, *, posicao: int = 0, **campos: object
) -> service.ProcessSave:
    proposta = _proposta_aprovada(sessao, cenario, posicao)
    base: dict[str, object] = {
        "proposal_id": proposta.id,
        "value_cents": 40_000_000,
        "date": ADIANTADO,
        "justification": "",
    }
    base.update(campos)
    return service.recommend_award(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.RecommendationInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _aprovar(
    sessao: Session, cenario: CenarioProcessos, *, aprovador_id: int | None = None, **campos: object
) -> service.ProcessSave:
    base: dict[str, object] = {
        "approver_id": aprovador_id if aprovador_id is not None else cenario.vitor.person_id,
        "date": date(2026, 9, 22),
        "opinion": "Aprovado.",
    }
    base.update(campos)
    return service.approve_award(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.ApprovalInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _emitir(sessao: Session, cenario: CenarioProcessos, **campos: object) -> service.ProcessSave:
    base: dict[str, object] = {
        "date": date(2026, 9, 24),
        "deadline_days": 90,
    }
    base.update(campos)
    return service.emit_order_or_contract(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.EmissionInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _comprometido(sessao: Session, cenario: CenarioProcessos) -> int:
    fact = sessao.scalars(
        select(ErpCost).where(ErpCost.item_id == cenario.item.id, ErpCost.month == date(2026, 9, 1))
    ).one()
    return fact.committed_cents or 0


# ── Recomendação ─────────────────────────────────────────────────────────────────────────────


def test_a_recomendacao_grava_as_colunas_e_o_historico(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)

    _recomendar(sessao, cenario)

    processo = _processo(sessao, cenario.pacote.id)
    assert processo.recommendation_on == ADIANTADO
    assert processo.recommendation_company_id == cenario.fornecedores[0].id
    assert processo.recommendation_value_cents == 40_000_000
    assert processo.recommendation_by_id == cenario.ana.person_id
    assert processo.recommendation_justification is None
    assert _historico(sessao, processo.id)[-1]["etapa"] == "Recomendação de adjudicação"
    assert _historico(sessao, processo.id)[-1]["texto"] == (
        "Recomendada a Alfa Fornecimentos de teste."
    )
    linha = _linha(sessao, cenario)
    assert linha.stage == "Recomendação de adjudicação"
    assert linha.recommendation is not None
    assert linha.recommendation.value_cents == 40_000_000


def test_a_recomendacao_de_reprovada_e_recusada(sessao: Session, cenario: CenarioProcessos) -> None:
    _fluxo_ate_negociacao(sessao, cenario)

    with pytest.raises(InvalidDataError) as reprovada:
        _recomendar(sessao, cenario, posicao=2)

    assert any("aprovadas tecnicamente" in msg for msg in reprovada.value.messages())


def test_a_recomendacao_de_fornecedor_sem_cadastro_e_recusada(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario, com_livre=True)
    processo = _processo(sessao, cenario.pacote.id)
    proposta_livre = sessao.scalars(
        select(ProcessProposal).where(
            ProcessProposal.process_id == processo.id, ProcessProposal.name == "Sem Cadastro"
        )
    ).one()

    with pytest.raises(InvalidDataError) as sem_cadastro:
        service.recommend_award(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            package_id=cenario.pacote.id,
            data=validation.RecommendationInput(
                proposal_id=proposta_livre.id,
                value_cents=39_000_000,
                date=ADIANTADO,
            ),
            reference_date=REFERENCIA,
        )

    assert any("Cadastre e qualifique" in msg for msg in sem_cadastro.value.messages())


def test_a_recomendacao_de_outra_nota_exige_justificativa(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)

    with pytest.raises(InvalidDataError) as curta:
        _recomendar(sessao, cenario, posicao=1, value_cents=44_000_000, justification="curta")

    assert any("melhor nota final" in msg for msg in curta.value.messages())

    _recomendar(
        sessao,
        cenario,
        posicao=1,
        value_cents=44_000_000,
        justification="Fornecedor com melhor prazo e assistência técnica local.",
    )
    processo = _processo(sessao, cenario.pacote.id)
    assert processo.recommendation_company_id == cenario.fornecedores[1].id
    assert processo.recommendation_justification is not None


def test_a_recomendacao_de_fornecedor_bloqueado_e_recusada(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    fornecedor = sessao.scalars(
        select(Supplier).where(Supplier.company_id == cenario.fornecedores[0].id)
    ).one()
    fornecedor.situation = calculations.BLOCKED
    sessao.flush()

    with pytest.raises(InvalidDataError) as recusa:
        _recomendar(sessao, cenario)

    assert any("bloqueado" in msg.lower() for msg in recusa.value.messages())


# ── Aprovação ────────────────────────────────────────────────────────────────────────────────


def test_o_aprovador_igual_ao_comprador_ou_ao_recomendador_recebe_403(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)

    with pytest.raises(AccessDeniedError) as recusa:
        _aprovar(sessao, cenario, aprovador_id=cenario.ana.person_id)

    assert "segregação" in str(recusa.value)
    assert _milestone(sessao, cenario.pacote.id, "adjudicacao").real_date is None


def test_a_aprovacao_grava_a_alcada_o_marco_e_a_trilha(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)

    _aprovar(sessao, cenario)

    processo = _processo(sessao, cenario.pacote.id)
    assert processo.approval_on == date(2026, 9, 22)
    assert processo.approval_by_id == cenario.vitor.person_id
    assert processo.approval_band == "Gerente de suprimentos", "o teto de 50 milhões fecha"
    assert processo.approval_opinion == "Aprovado."
    assert _milestone(sessao, cenario.pacote.id, "adjudicacao").real_date == date(2026, 9, 22)
    assert _historico(sessao, processo.id)[-1]["etapa"] == "Aprovada"
    assert _historico(sessao, processo.id)[-1]["texto"] == (
        "Aprovada na alçada: Gerente de suprimentos."
    )
    assert _linha(sessao, cenario).stage == "Aprovada"


def test_a_alcada_muda_um_centavo_acima_do_teto(sessao: Session, cenario: CenarioProcessos) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario, value_cents=50_000_001)

    _aprovar(sessao, cenario)

    assert _processo(sessao, cenario.pacote.id).approval_band == "Gerente do projeto"


def test_o_valor_no_proprio_saldo_da_eac_passa(sessao: Session, cenario: CenarioProcessos) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario, value_cents=60_000_000)

    _aprovar(sessao, cenario)

    assert _processo(sessao, cenario.pacote.id).approval_on is not None


def test_o_valor_acima_do_saldo_da_eac_e_recusado(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario, value_cents=60_000_001)

    with pytest.raises(InvalidDataError) as recusa:
        _aprovar(sessao, cenario)

    assert any("saldo a comprometer" in msg for msg in recusa.value.messages())
    assert _processo(sessao, cenario.pacote.id).approval_on is None


def test_o_lli_antes_do_gate_exige_a_aprovacao_do_gate(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    cenario.projeto.start_date = date(2026, 8, 15)
    cenario.pacote.lli = True
    sessao.flush()
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _aprovar(sessao, cenario)

    assert any("gate LLI" in msg for msg in recusa.value.messages())

    cenario.pacote.gate_lli_date = date(2026, 8, 5)
    cenario.pacote.gate_lli_reference = "Aprovação do gate LLI CIPM"
    sessao.flush()
    _aprovar(sessao, cenario)
    assert _processo(sessao, cenario.pacote.id).approval_on is not None


# ── Devolução ────────────────────────────────────────────────────────────────────────────────


def test_devolver_volta_para_negociacao_com_motivo(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)

    with pytest.raises(InvalidDataError) as curto:
        service.return_recommendation(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            package_id=cenario.pacote.id,
            data=validation.ReturnInput(reason="curto"),
            reference_date=REFERENCIA,
        )

    assert any("motivo" in msg for msg in curto.value.messages())

    service.return_recommendation(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.ReturnInput(reason="Prazo de entrega acima do necessário."),
        reference_date=REFERENCIA,
    )

    processo = _processo(sessao, cenario.pacote.id)
    assert processo.recommendation_on is None
    assert processo.recommendation_company_id is None
    assert processo.recommendation_value_cents is None
    assert processo.recommendation_by_id is None
    assert _historico(sessao, processo.id)[-1]["etapa"] == "Negociação"
    assert _historico(sessao, processo.id)[-1]["texto"] == (
        "Recomendação devolvida: Prazo de entrega acima do necessário."
    )
    assert _linha(sessao, cenario).stage == "Negociação"


# ── Emissão ──────────────────────────────────────────────────────────────────────────────────


def test_a_emissao_do_pedido_cria_o_cronograma_e_compromete_a_eac(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)
    _aprovar(sessao, cenario)

    resultado = _emitir(sessao, cenario)

    assert resultado.document == "PED-2026-0001", "a primeira emissão da série global"
    pedido = sessao.scalars(select(PurchaseOrder)).one()
    assert pedido.package_id == cenario.pacote.id
    assert pedido.company_id == cenario.fornecedores[0].id
    assert pedido.value_cents == 40_000_000
    assert pedido.emission == date(2026, 9, 24)
    assert pedido.contractual_date == date(2026, 12, 23), "90 dias após a emissão"
    assert pedido.forecast == date(2026, 12, 23)
    assert pedido.ros == cenario.pacote.ros
    assert pedido.delivery is None
    marcos = sessao.scalars(
        select(PurchaseOrderMilestone)
        .where(PurchaseOrderMilestone.order_id == pedido.id)
        .order_by(PurchaseOrderMilestone.position)
    ).all()
    assert len(marcos) == 6
    assert marcos[-1].name == "Entrega"
    assert marcos[-1].baseline_date == date(2026, 12, 23)
    assert marcos[0].baseline_date == date(2026, 10, 8), "15% da janela, arredondado para cima"
    assert _milestone(sessao, cenario.pacote.id, "pedido").real_date == date(2026, 9, 24)
    assert _comprometido(sessao, cenario) == 80_000_000, (
        "os 40 milhões do cenário mais os 40 do pedido"
    )
    assert _historico(sessao, _processo(sessao, cenario.pacote.id).id)[-1]["texto"] == (
        "Pedido PED-2026-0001 emitido; valor comprometido na EAC."
    )
    assert _linha(sessao, cenario).stage == "Pedido/contrato emitido"
    assert _linha(sessao, cenario).order_number == "PED-2026-0001"
    assert sessao.scalars(select(Action)).all() == [], "sem folga negativa, sem ação"


def test_o_pedido_com_folga_negativa_cria_a_acao_na_central(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    cenario.pacote.ros = date(2026, 10, 1)
    sessao.flush()
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)
    _aprovar(sessao, cenario)

    _emitir(sessao, cenario)

    acao = sessao.scalars(select(Action)).one()
    assert acao.origin == "Suprimentos"
    assert acao.origin_ref == "PED-2026-0001"
    assert acao.group == "Diligenciamento"
    assert acao.subject == "Recuperar a folga do pedido PED-2026-0001"
    assert acao.responsible_id == cenario.ana.person_id, "o responsável é o comprador"
    assert acao.planned_date is not None
    assert (acao.planned_date - REFERENCIA).days == 7, "prazo de sete dias"
    assert "folga de -83 dias" in (acao.description or "")


def test_a_emissao_do_contrato_cria_o_contrato_no_financeiro(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    cenario.pacote.kind = "Serviço"
    sessao.flush()
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)
    _aprovar(sessao, cenario)

    resultado = _emitir(
        sessao,
        cenario,
        deadline_days=None,
        start=date(2026, 10, 1),
        end=date(2027, 6, 30),
        fiscal_id=cenario.vitor.person_id,
        retention_pct=5,
    )

    assert resultado.document == "CT-2026-001"
    contrato = sessao.scalars(select(Contract)).one()
    assert contrato.purchase_package_id == cenario.pacote.id, "o vínculo com o pacote (D9)"
    assert contrato.project_id == cenario.projeto.id
    assert contrato.company_id == cenario.fornecedores[0].id
    assert contrato.eac_item_id == cenario.item.id
    assert contrato.object == cenario.pacote.scope
    assert contrato.modality == cenario.pacote.modality
    assert contrato.original_value_cents == 40_000_000
    assert contrato.start == date(2026, 10, 1)
    assert contrato.original_end == date(2027, 6, 30)
    assert contrato.current_end == date(2027, 6, 30)
    assert contrato.manager_id == cenario.projeto.manager_id
    assert contrato.fiscal_id == cenario.vitor.person_id
    assert contrato.retention_pct == 5
    assert contrato.claim_notice_days == 30, "o prazo padrão do grupo claims"
    assert contrato.situation == "Em execução"
    assert _comprometido(sessao, cenario) == 80_000_000
    assert _milestone(sessao, cenario.pacote.id, "pedido").real_date == date(2026, 9, 24)
    assert sessao.scalars(select(PurchaseOrder)).all() == [], "serviço não gera pedido"
    assert _linha(sessao, cenario).contract_number == "CT-2026-001"


def test_o_contrato_exige_termino_posterior_a_emissao(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    cenario.pacote.kind = "EPC"
    sessao.flush()
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)
    _aprovar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _emitir(
            sessao,
            cenario,
            deadline_days=None,
            end=date(2026, 9, 24),
            fiscal_id=cenario.vitor.person_id,
        )

    assert any("término contratual" in msg for msg in recusa.value.messages())
    assert sessao.scalars(select(Contract)).all() == []


def test_a_falha_no_meio_da_emissao_nao_deixa_nada_gravado(
    sessao: Session, cenario: CenarioProcessos, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    _recomendar(sessao, cenario)
    _aprovar(sessao, cenario)
    real = financeiro.commit_purchase_cost

    def falha_apos_gravar(*args: Any, **kwargs: Any) -> None:
        real(*args, **kwargs)
        raise FalhaSimuladaError

    monkeypatch.setattr(financeiro, "commit_purchase_cost", falha_apos_gravar)
    savepoint = sessao.begin_nested()
    with pytest.raises(FalhaSimuladaError):
        _emitir(sessao, cenario)

    assert sessao.scalars(select(PurchaseOrder)).all() != [], "dentro da transação, gravou"
    savepoint.rollback()

    assert sessao.scalars(select(PurchaseOrder)).all() == [], "o rollback desfaz o pedido"
    assert sessao.scalars(select(PurchaseOrderMilestone)).all() == []
    assert _comprometido(sessao, cenario) == 40_000_000, "o comprometido volta ao valor anterior"
    assert _milestone(sessao, cenario.pacote.id, "pedido").real_date is None
    assert _processo(sessao, cenario.pacote.id).approval_on is not None, "a aprovação fica"


def test_o_visualizador_nao_recomenda(sessao: Session, cenario: CenarioProcessos) -> None:
    _fluxo_ate_negociacao(sessao, cenario)
    proposta = _proposta_aprovada(sessao, cenario, 0)

    with pytest.raises(AccessDeniedError):
        service.recommend_award(
            sessao,
            user=cenario.vitor,
            scope=_scope(cenario),
            package_id=cenario.pacote.id,
            data=validation.RecommendationInput(
                proposal_id=proposta.id, value_cents=40_000_000, date=ADIANTADO
            ),
            reference_date=REFERENCIA,
        )
