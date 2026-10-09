"""As fachadas do processo de compra (ISSUE-059): cada ação, as recusas e o que fica gravado.

A leitura usa o escopo do projeto; cada ação passa pela fachada, dentro da transação do teste,
com a trilha e a versão. As recusas são as do protótipo: mínimo de convidados (ou fornecedor
único com justificativa), bloqueado fora, pesos somando 100, técnica antes da comercial, proposta
reprovada fora do ranking e negociação só com aprovada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.core.scope import Scope
from src.modulos.suprimentos import calculations, service, validation
from src.modulos.suprimentos.models import (
    PackageMilestone,
    ProcessInvitee,
    ProcessNegotiation,
    ProcessProposal,
    PurchaseProcess,
)
from tests.apoio_pacotes import REFERENCIA
from tests.apoio_processos import (
    CenarioProcessos,
    montar_cenario_processos,
    proposta_do_cenario,
    requisicao,
    rfx_do_cenario,
)
from tests.armazenamento_falso import ArmazenamentoEmMemoria


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


def _linha(sessao: Session, cenario: CenarioProcessos, pacote_id: int) -> service.ProcessLine:
    line = service.find_process(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=pacote_id,
        reference_date=REFERENCIA,
    )
    assert line is not None
    return line


def _emitir_rfx(
    sessao: Session, cenario: CenarioProcessos, **campos: object
) -> service.ProcessSave:
    return service.issue_rfx(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=rfx_do_cenario(cenario, **campos),
        reference_date=REFERENCIA,
    )


def _registrar_proposta(
    sessao: Session, cenario: CenarioProcessos, **campos: object
) -> service.ProcessSave:
    return service.register_proposal(
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


def _encerrar(sessao: Session, cenario: CenarioProcessos, **campos: object) -> service.ProcessSave:
    base: dict[str, object] = {
        "date": date(2026, 8, 31),
        "justification": "Poucos fornecedores no mercado local com o escopo completo.",
    }
    base.update(campos)
    return service.close_receipt(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.ClosingInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _avaliar(
    sessao: Session,
    cenario: CenarioProcessos,
    avaliacoes: list[tuple[int | None, bool]],
    **campos: object,
) -> service.ProcessSave:
    line = _linha(sessao, cenario, cenario.pacote.id)
    items = tuple(
        validation.TechnicalEvaluation(
            proposal_id=proposal.id,
            score=score,
            approved=approved,
            deviations="Sem desvios.",
            version=proposal.version,
        )
        for proposal, (score, approved) in zip(line.proposals, avaliacoes, strict=False)
    )
    base: dict[str, object] = {
        "date": date(2026, 9, 10),
        "evaluations": items,
        "responsible_id": cenario.ana.person_id,
        "opinion": "Parecer técnico de teste.",
        "justification": "Apenas um fornecedor atende a especificação completa do escopo.",
    }
    base.update(campos)
    return service.equalize_technically(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.TechnicalInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _comercial(sessao: Session, cenario: CenarioProcessos, **campos: object) -> service.ProcessSave:
    base: dict[str, object] = {
        "date": date(2026, 9, 15),
        "weight_technical": 50,
        "weight_commercial": 50,
        "version": _processo(sessao, cenario.pacote.id).version,
    }
    base.update(campos)
    return service.equalize_commercially(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.CommercialInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _fluxo_ate_comercial(sessao: Session, cenario: CenarioProcessos) -> None:
    """O processo do cenário percorrido até Negociação, com duas propostas aprovadas."""
    _emitir_rfx(sessao, cenario)
    _registrar_proposta(sessao, cenario, value_cents=40_000_000)
    _registrar_proposta(
        sessao, cenario, company_id=cenario.fornecedores[1].id, value_cents=45_000_000
    )
    _registrar_proposta(
        sessao,
        cenario,
        company_id=cenario.fornecedores[2].id,
        value_cents=38_000_000,
    )
    _encerrar(sessao, cenario)
    _avaliar(sessao, cenario, [(90, True), (80, True), (70, False)])
    _comercial(sessao, cenario)


# ── Nova requisição ──────────────────────────────────────────────────────────


def test_a_requisicao_grava_o_marco_e_a_trilha_do_pacote(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    resultado = service.start_requisition(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.planejado.id,
        data=requisicao(document="RM-MEC-0042 rev. 0", observation="Requisição do reserva."),
        reference_date=REFERENCIA,
    )

    marco = _milestone(sessao, cenario.planejado.id, "requisicao")
    assert marco.real_date == REFERENCIA
    assert resultado.code == "PC-02"
    linhas = sessao.scalars(
        select(AuditEntry).where(
            AuditEntry.entity == service.HISTORY_ENTITY,
            AuditEntry.record_id == cenario.planejado.id,
        )
    ).all()
    assert linhas[-1].after is not None
    assert linhas[-1].after["campos"] == ["requisicao"]
    assert linhas[-1].after["documento"] == "RM-MEC-0042 rev. 0"
    assert linhas[-1].after["justificativa"] == "Requisição do reserva."

    with pytest.raises(InvalidDataError):
        service.start_requisition(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            package_id=cenario.planejado.id,
            data=requisicao(),
            reference_date=REFERENCIA,
        )


def test_a_requisicao_no_futuro_e_recusada(sessao: Session, cenario: CenarioProcessos) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.start_requisition(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            package_id=cenario.planejado.id,
            data=requisicao(date=date(2026, 10, 1)),
            reference_date=REFERENCIA,
        )

    assert any("posterior" in mensagem for mensagem in recusa.value.messages())
    assert _milestone(sessao, cenario.planejado.id, "requisicao").real_date is None


# ── Emitir RFx ───────────────────────────────────────────────────────────────


def test_a_rfx_abaixo_do_minimo_e_recusada(sessao: Session, cenario: CenarioProcessos) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _emitir_rfx(sessao, cenario, invitees=(cenario.fornecedores[0].id,))

    assert any("Convide ao menos 3" in mensagem for mensagem in recusa.value.messages())
    assert sessao.scalars(select(PurchaseProcess)).all() == []


def test_a_rfx_cria_o_processo_com_numero_marco_e_convidados(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    resultado = _emitir_rfx(sessao, cenario)

    processo = _processo(sessao, cenario.pacote.id)
    assert resultado.number == "RFQ-2026-001"
    assert processo.number == "RFQ-2026-001"
    assert (processo.weight_technical, processo.weight_commercial) == (40, 60)
    assert processo.proposals_deadline == date(2026, 8, 31)
    convidados = sessao.scalars(
        select(ProcessInvitee).where(ProcessInvitee.process_id == processo.id)
    ).all()
    assert {row.company_id for row in convidados} == {
        empresa.id for empresa in cenario.fornecedores
    }
    assert _milestone(sessao, cenario.pacote.id, "rfx").real_date == date(2026, 8, 10)
    assert _milestone(sessao, cenario.pacote.id, "propostas").forecast_date == date(2026, 8, 31)
    historico = _historico(sessao, processo.id)
    assert historico[-1]["etapa"] == "RFx emitida"
    assert historico[-1]["texto"] == "RFQ-2026-001 emitida para 3 fornecedores."


def test_o_fornecedor_bloqueado_nao_e_convidado(sessao: Session, cenario: CenarioProcessos) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _emitir_rfx(
            sessao,
            cenario,
            invitees=(*[empresa.id for empresa in cenario.fornecedores], cenario.bloqueada.id),
        )

    assert any("bloqueado" in mensagem.lower() for mensagem in recusa.value.messages())
    assert sessao.scalars(select(PurchaseProcess)).all() == []


def test_a_rfx_de_fornecedor_unico_exige_justificativa(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _emitir_rfx(
            sessao, cenario, invitees=(), single_supplier=True, single_justification="curta"
        )

    assert any("Fornecedor único" in mensagem for mensagem in recusa.value.messages())

    _emitir_rfx(
        sessao,
        cenario,
        invitees=(),
        single_supplier=True,
        single_justification="Único fornecedor com certificação exigida pela especificação.",
    )
    linha = _linha(sessao, cenario, cenario.pacote.id)
    assert linha.single_supplier is True, "sem convidados além do mínimo, é fornecedor único"


def test_o_peso_que_nao_soma_100_e_recusado(sessao: Session, cenario: CenarioProcessos) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _emitir_rfx(sessao, cenario, weight_technical=50, weight_commercial=40)

    assert any("somar 100" in mensagem for mensagem in recusa.value.messages())


# ── Registrar proposta ───────────────────────────────────────────────────────


def test_a_proposta_exige_o_pdf_e_move_a_etapa(sessao: Session, cenario: CenarioProcessos) -> None:
    _emitir_rfx(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        service.register_proposal(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            package_id=cenario.pacote.id,
            data=proposta_do_cenario(cenario),
            reference_date=REFERENCIA,
        )

    assert any("arquivo" in mensagem.lower() for mensagem in recusa.value.messages())
    assert sessao.scalars(select(ProcessProposal)).all() == [], "nada é gravado sem o PDF"

    _registrar_proposta(sessao, cenario)
    processo = _processo(sessao, cenario.pacote.id)
    propostas = sessao.scalars(
        select(ProcessProposal).where(ProcessProposal.process_id == processo.id)
    ).all()
    assert len(propostas) == 1
    assert propostas[0].company_id == cenario.fornecedores[0].id
    historico = _historico(sessao, processo.id)
    assert [linha["etapa"] for linha in historico[-2:]] == [
        "Propostas recebidas",
        "Propostas recebidas",
    ]
    assert historico[-2]["texto"] == service.FIRST_PROPOSAL_NOTE
    linha = _linha(sessao, cenario, cenario.pacote.id)
    assert linha.stage == "Propostas recebidas"
    assert linha.received_count == 1


def test_a_proposta_repetida_e_recusada(sessao: Session, cenario: CenarioProcessos) -> None:
    _emitir_rfx(sessao, cenario)
    _registrar_proposta(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _registrar_proposta(sessao, cenario)

    assert any("já tem proposta" in mensagem for mensagem in recusa.value.messages())


def test_a_proposta_de_fornecedor_bloqueado_e_recusada(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _emitir_rfx(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _registrar_proposta(sessao, cenario, company_id=cenario.bloqueada.id)

    assert any("bloqueado" in mensagem.lower() for mensagem in recusa.value.messages())


# ── Encerrar recebimento ─────────────────────────────────────────────────────


def test_o_encerramento_abaixo_do_minimo_exige_justificativa(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _emitir_rfx(sessao, cenario)
    _registrar_proposta(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _encerrar(sessao, cenario, justification="curta")

    assert any("Justifique para seguir" in mensagem for mensagem in recusa.value.messages())

    _encerrar(sessao, cenario)
    assert _milestone(sessao, cenario.pacote.id, "propostas").real_date == date(2026, 8, 31)
    processo = _processo(sessao, cenario.pacote.id)
    assert _historico(sessao, processo.id)[-1]["etapa"] == "Equalização técnica"


# ── Equalização técnica ──────────────────────────────────────────────────────


def test_a_equalizacao_tecnica_exige_nota_aprovacao_e_minimo(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _emitir_rfx(sessao, cenario)
    _registrar_proposta(sessao, cenario)
    _registrar_proposta(sessao, cenario, company_id=cenario.fornecedores[1].id)
    _encerrar(sessao, cenario)
    with pytest.raises(InvalidDataError) as recusa:
        _avaliar(sessao, cenario, [(90, True)])

    assert any("nota técnica" in mensagem for mensagem in recusa.value.messages())

    with pytest.raises(InvalidDataError) as sem_aprovada:
        _avaliar(sessao, cenario, [(90, False), (80, False)])

    assert any(
        "Nenhuma proposta aprovada" in mensagem for mensagem in sem_aprovada.value.messages()
    )

    with pytest.raises(InvalidDataError) as abaixo:
        _avaliar(sessao, cenario, [(90, True), (80, False)], justification="curta")

    assert any("aprovada(s) tecnicamente" in mensagem for mensagem in abaixo.value.messages())

    _avaliar(sessao, cenario, [(90, True), (80, False)])
    processo = _processo(sessao, cenario.pacote.id)
    propostas = sessao.scalars(
        select(ProcessProposal)
        .where(ProcessProposal.process_id == processo.id)
        .order_by(ProcessProposal.id)
    ).all()
    assert [(row.technical_score, row.technically_approved) for row in propostas] == [
        (90, True),
        (80, False),
    ]
    assert _milestone(sessao, cenario.pacote.id, "eqTecnica").real_date == date(2026, 9, 10)
    assert _historico(sessao, processo.id)[-1]["etapa"] == "Equalização comercial"
    assert _historico(sessao, processo.id)[-1]["texto"] == (
        "Parecer técnico: 1 de 2 propostas aprovadas."
    )


# ── Equalização comercial e negociação ───────────────────────────────────────


def test_a_comercial_antes_da_tecnica_e_recusada(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _emitir_rfx(sessao, cenario)
    _registrar_proposta(sessao, cenario)
    _encerrar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _comercial(sessao, cenario)

    assert any("Equalização técnica" in mensagem for mensagem in recusa.value.messages())


def test_a_comercial_grava_os_pesos_e_o_ranking(sessao: Session, cenario: CenarioProcessos) -> None:
    _fluxo_ate_comercial(sessao, cenario)

    processo = _processo(sessao, cenario.pacote.id)
    assert (processo.weight_technical, processo.weight_commercial) == (50, 50)
    assert processo.version == 2
    assert _milestone(sessao, cenario.pacote.id, "eqComercial").real_date == date(2026, 9, 15)
    assert _historico(sessao, processo.id)[-1]["etapa"] == "Negociação"

    linha = _linha(sessao, cenario, cenario.pacote.id)
    assert linha.stage == "Negociação"
    assert linha.received_count == 3
    assert linha.approved_count == 2
    assert linha.best is not None
    assert linha.best.name == "Alfa Fornecimentos de teste"
    assert (linha.best.commercial_score, linha.best.final_score, linha.best.rank) == (
        Decimal("100.0"),
        Decimal("95.0"),
        1,
    )
    assert linha.proposals[1].name == "Beta Fornecimentos de teste"
    assert (linha.proposals[1].commercial_score, linha.proposals[1].final_score) == (
        Decimal("88.9"),
        Decimal("84.5"),
    )
    assert linha.proposals[2].rank is None, "a reprovada fica fora do ranking"
    assert linha.approval_band == "Gerente de suprimentos"


def test_a_negociacao_exige_aprovada_e_respeita_o_teto(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_comercial(sessao, cenario)
    line = _linha(sessao, cenario, cenario.pacote.id)
    reprovada = line.proposals[2]
    aprovada = line.proposals[1]

    with pytest.raises(InvalidDataError) as nao_aprovada:
        service.register_negotiation(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            package_id=cenario.pacote.id,
            data=validation.NegotiationInput(
                proposal_id=reprovada.id,
                value_cents=37_000_000,
                date=date(2026, 9, 18),
            ),
            reference_date=REFERENCIA,
        )

    assert any("aprovadas tecnicamente" in mensagem for mensagem in nao_aprovada.value.messages())

    with pytest.raises(InvalidDataError) as acima:
        service.register_negotiation(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            package_id=cenario.pacote.id,
            data=validation.NegotiationInput(
                proposal_id=aprovada.id,
                value_cents=46_000_000,
                date=date(2026, 9, 18),
            ),
            reference_date=REFERENCIA,
        )

    assert any("superar a proposta" in mensagem for mensagem in acima.value.messages())

    service.register_negotiation(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.NegotiationInput(
            proposal_id=aprovada.id,
            value_cents=44_000_000,
            date=date(2026, 9, 18),
            observation="Desconto por pagamento em marcos.",
        ),
        reference_date=REFERENCIA,
    )

    processo = _processo(sessao, cenario.pacote.id)
    negociacoes = sessao.scalars(
        select(ProcessNegotiation).where(ProcessNegotiation.process_id == processo.id)
    ).all()
    assert len(negociacoes) == 1
    assert negociacoes[0].company_id == cenario.fornecedores[1].id
    assert negociacoes[0].value_cents == 44_000_000
    assert _historico(sessao, processo.id)[-1]["texto"] == (
        "Negociação com Beta Fornecimentos de teste registrada."
    )
    assert _linha(sessao, cenario, cenario.pacote.id).proposals[1].negotiated_cents == 44_000_000


def test_a_versao_antiga_da_comercial_e_recusada(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _emitir_rfx(sessao, cenario)
    _registrar_proposta(sessao, cenario)
    _encerrar(sessao, cenario)
    _avaliar(sessao, cenario, [(90, True)])

    with pytest.raises(VersionConflictError):
        _comercial(sessao, cenario, version=_processo(sessao, cenario.pacote.id).version + 5)


# ── Leitura, escopo e perfil ─────────────────────────────────────────────────


def test_a_lista_traz_etapa_passo_melhor_e_alcada(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    _fluxo_ate_comercial(sessao, cenario)

    listagem = service.list_processes(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        filters=validation.ProcessFilters(),
        reference_date=REFERENCIA,
    )

    assert listagem.total == 2, "PC-01 em negociação e PC-02 planejado"
    linha = next(item for item in listagem.lines if item.package_id == cenario.pacote.id)
    assert (linha.stage, linha.stage_index) == ("Negociação", 6)
    assert linha.steps[4].situation == calculations.STEP_DONE
    assert linha.steps[5].situation == calculations.STEP_CURRENT
    assert linha.steps[6].situation == calculations.STEP_FUTURE
    assert linha.number == "RFQ-2026-001"
    assert linha.minimum == 3
    assert linha.approval_band == "Gerente de suprimentos"
    assert linha.reference_value_cents == 40_000_000
    assert linha.eac_balance_cents is None, "o saldo a comprometer é lido na ficha, não na lista"
    ficha = _linha(sessao, cenario, cenario.pacote.id)
    assert ficha.eac_balance_cents is not None
    assert listagem.summary.in_progress == 2
    assert listagem.summary.mean_valid_proposals == Decimal("2.0")
    assert listagem.summary.single_supplier_count == 0
    assert listagem.summary.cycle_mean_days is None, "nenhum processo chegou ao pedido"
    assert listagem.summary.baseline_cycle_days is None, "a LB só conta dos concluídos"


def test_o_processo_fora_do_escopo_nao_e_encontrado(
    sessao: Session, cenario: CenarioProcessos
) -> None:
    assert (
        service.find_process(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario, portfolio=True),
            package_id=cenario.pacote.id,
            reference_date=REFERENCIA,
        )
        is not None
    )
    assert (
        service.find_process(
            sessao,
            user=cenario.ana,
            scope=Scope(project_id=cenario.outro.id, source="url"),
            package_id=cenario.pacote.id,
            reference_date=REFERENCIA,
        )
        is None
    )


def test_o_visualizador_le_e_nao_grava(sessao: Session, cenario: CenarioProcessos) -> None:
    listagem = service.list_processes(
        sessao,
        user=cenario.vitor,
        scope=_scope(cenario),
        filters=validation.ProcessFilters(),
        reference_date=REFERENCIA,
    )
    assert listagem.total == 2

    with pytest.raises(AccessDeniedError):
        service.issue_rfx(
            sessao,
            user=cenario.vitor,
            scope=_scope(cenario),
            package_id=cenario.pacote.id,
            data=rfx_do_cenario(cenario),
            reference_date=REFERENCIA,
        )
