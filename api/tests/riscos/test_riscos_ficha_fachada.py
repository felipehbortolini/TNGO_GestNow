"""Fachada da ficha do risco (ISSUE-065, D7, D9): plano, aprovação, revisão, encerramento e reabertura.

O plano de resposta com cada regra (residual só depois do plano, alvo não maior que a inerente,
prazo futuro, ação obrigatória para inerente Alto ou Crítico, Evitar com 80 caracteres e SM,
Transferir com instrumento, Aceitar com 30 caracteres), a aprovação do gestor com a segregação de
quem responde pelo plano, a revisão com a cadência que nunca é postergada e o gatilho que força a
reavaliação, o encerramento com a lição sempre obrigatória e as criações na mesma transação, e a
reabertura com justificativa.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.governanca import service as governanca
from src.modulos.riscos import ficha_service, service
from src.modulos.riscos.models import Risk, RiskPlanApproval, RiskReview
from src.modulos.riscos.validation import (
    ActionInput,
    ApprovalInput,
    ClosingInput,
    PlanInput,
    ReopenInput,
    ReviewInput,
)
from tests.apoio_riscos import REFERENCIA, Cenario, nova_avaliacao, novo_risco

PLAN_TEXT = "Antecipar as entregas condicionantes e negociar prioridade com o fornecedor."


def _criar(sessao: Session, cenario: Cenario, **campos: object) -> str:
    return service.save_risk(
        sessao, user=cenario.mario, data=novo_risco(cenario, **campos), reference_date=REFERENCIA
    ).code


def _avaliar(sessao: Session, cenario: Cenario, codigo: str, **campos: object):
    return service.assess_risk(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=nova_avaliacao(**campos),
        reference_date=REFERENCIA,
    )


def _plano(**campos: object) -> PlanInput:
    base = PlanInput(
        strategy="Mitigar",
        plan=PLAN_TEXT,
        target_severity="baixo",
        target_date=REFERENCIA + timedelta(days=30),
        plan_responsible_id=None,
    )
    return replace(base, **campos)


def _salvar_plano(sessao: Session, cenario: Cenario, codigo: str, **campos: object):
    data = _plano(**campos)
    if data.plan_responsible_id is None:
        data = replace(data, plan_responsible_id=cenario.mario.person_id)
    return ficha_service.save_plan(
        sessao, user=cenario.mario, code=codigo, data=data, reference_date=REFERENCIA
    )


def _acao(sessao: Session, cenario: Cenario, codigo: str, **campos: object) -> None:
    base = ActionInput(
        subject="Contratar a consultoria ambiental",
        requester_id=cenario.mario.person_id,
        responsible_id=cenario.mario.person_id,
        planned_date=REFERENCIA + timedelta(days=5),
    )
    ficha_service.create_risk_action(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=replace(base, **campos),
        reference_date=REFERENCIA,
    )


def _risco_de_baixo(sessao: Session, cenario: Cenario) -> str:
    codigo = _criar(sessao, cenario)
    _avaliar(
        sessao,
        cenario,
        codigo,
        probability=2,
        impact=2,
        dimensions={"prazo": 2},
        cost_impact_cents=10_000_000,
    )
    return codigo


# ── Plano de resposta ────────────────────────────────────────────────────────────────────────


def test_plano_salvo_habilita_o_residual(sessao: Session, cenario: Cenario) -> None:
    codigo = _risco_de_baixo(sessao, cenario)

    resultado = _salvar_plano(sessao, cenario, codigo)

    assert resultado.enables_residual
    assert resultado.situation == "Em tratamento"
    linha = service.find_risk(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert linha is not None and linha.has_plan
    assert linha.strategy == "Mitigar"
    assert linha.target_severity == "baixo"
    # O residual só habilita depois do plano: agora a avaliação residual é aceita.
    residual = service.assess_risk(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=nova_avaliacao(
            kind="residual",
            probability=1,
            impact=2,
            dimensions={"prazo": 2},
            cost_impact_cents=10_000_000,
            justification="Residual estimado após o plano.",
        ),
        reference_date=REFERENCIA,
    )
    assert residual.score == 2


def test_plano_exige_avaliacao_inerente(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(sessao, cenario, codigo)

    assert "Avalie o risco (inerente)" in str(recusa.value)


def test_alvo_acima_da_inerente_e_recusado_para_ameaca(sessao: Session, cenario: Cenario) -> None:
    codigo = _risco_de_baixo(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(sessao, cenario, codigo, target_severity="moderado")

    assert "não pode ser maior que a inerente" in str(recusa.value)


def test_prazo_do_alvo_no_passado_e_recusado(sessao: Session, cenario: Cenario) -> None:
    codigo = _risco_de_baixo(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(sessao, cenario, codigo, target_date=REFERENCIA - timedelta(days=1))

    assert "data futura" in str(recusa.value)


def test_acao_obrigatoria_para_inerente_alto(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)  # P3 x I4 = 12 (alto)

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(sessao, cenario, codigo, target_severity="alto")

    assert "pelo menos uma ação vinculada" in str(recusa.value)

    _acao(sessao, cenario, codigo)
    resultado = _salvar_plano(sessao, cenario, codigo, target_severity="alto")

    assert resultado.situation == "Em tratamento"


def test_aceitar_nao_exige_acao_mas_exige_justificativa(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)  # alto

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(
            sessao, cenario, codigo, strategy="Aceitar", plan="Aceito.", target_severity="alto"
        )

    assert "mínimo de 30 caracteres" in str(recusa.value)

    resultado = _salvar_plano(
        sessao,
        cenario,
        codigo,
        strategy="Aceitar",
        plan="Aceito com base no cadastro de interferências do cliente e na reserva.",
        target_severity="alto",
    )

    assert resultado.situation == "Monitorado"


def test_evitar_exige_oitenta_caracteres(sessao: Session, cenario: Cenario) -> None:
    codigo = _risco_de_baixo(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(sessao, cenario, codigo, strategy="Evitar", plan="Evita o problema.")

    assert "mínimo de 80 caracteres" in str(recusa.value)


def test_evitar_exige_sm(sessao: Session, cenario: Cenario) -> None:
    codigo = _risco_de_baixo(sessao, cenario)
    texto = (
        "Sondagem complementar antes de liberar as frentes e reprojeto preventivo das fundações."
    )

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(sessao, cenario, codigo, strategy="Evitar", plan=texto)

    assert "Evitar exige registro da mudança" in str(recusa.value)

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(sessao, cenario, codigo, strategy="Evitar", plan=texto, change_code="SM-9999")

    assert "SM não encontrada" in str(recusa.value)


def test_evitar_com_sm_existente_vincula_a_mudanca(sessao: Session, cenario: Cenario) -> None:
    codigo = _risco_de_baixo(sessao, cenario)
    criada = governanca.create_change(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=cenario.projeto.id, source="padrao"),
        form={
            "titulo": "Mudança de solução da fundação",
            "tipo": "Escopo",
            "origem": "Interna",
            "prioridade": "Normal",
            "descricao": "Mudança de solução para eliminar a exposição do risco.",
            "data_solicitacao": REFERENCIA.isoformat(),
        },
        reference_date=REFERENCIA,
    )
    texto = (
        "Sondagem complementar antes de liberar as frentes e reprojeto preventivo das fundações."
    )

    resultado = _salvar_plano(
        sessao, cenario, codigo, strategy="Evitar", plan=texto, change_code=criada.code
    )

    assert resultado.enables_residual
    risco = sessao.scalars(select(Risk).where(Risk.code == codigo)).one()
    assert risco.change_id == criada.id


def test_evitar_com_sm_nova_cria_acao_na_central(sessao: Session, cenario: Cenario) -> None:
    codigo = _risco_de_baixo(sessao, cenario)
    texto = (
        "Sondagem complementar antes de liberar as frentes e reprojeto preventivo das fundações."
    )

    _salvar_plano(sessao, cenario, codigo, strategy="Evitar", plan=texto, change_code="nova")

    contagens = central_acoes.count_actions_of_origin(
        sessao,
        user=cenario.mario,
        origin_kind="Risco",
        references=[codigo],
        reference_date=REFERENCIA,
    )
    assert contagens[codigo].total == 1
    risco = sessao.scalars(select(Risk).where(Risk.code == codigo)).one()
    assert risco.change_id is None


def test_transferir_exige_instrumento(sessao: Session, cenario: Cenario) -> None:
    codigo = _risco_de_baixo(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _salvar_plano(sessao, cenario, codigo, strategy="Transferir")

    assert "instrumento da transferência" in str(recusa.value)

    resultado = _salvar_plano(sessao, cenario, codigo, strategy="Transferir", instrument="Seguro")
    assert resultado.situation == "Em tratamento"


# ── Aprovação do plano ───────────────────────────────────────────────────────────────────────


def _plano_pendente(sessao: Session, cenario: Cenario) -> str:
    """Um risco crítico com plano Aceitar aguardando a aprovação da gerência."""
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo, probability=4, impact=4)
    _salvar_plano(
        sessao,
        cenario,
        codigo,
        strategy="Aceitar",
        plan="Aceito com base no cadastro de interferências do cliente e na reserva.",
        target_severity="moderado",
    )
    return codigo


def test_inerente_na_faixa_mais_alta_exige_aprovacao(sessao: Session, cenario: Cenario) -> None:
    codigo = _plano_pendente(sessao, cenario)

    linha = service.find_risk(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert linha is not None and linha.plan_pending
    aprovacoes = sessao.scalars(
        select(RiskPlanApproval).where(RiskPlanApproval.risk_id == linha.id)
    ).all()
    assert [item.situation for item in aprovacoes] == ["Pendente"]


def test_aprovar_exige_gestor(sessao: Session, cenario: Cenario) -> None:
    codigo = _plano_pendente(sessao, cenario)

    with pytest.raises(AccessDeniedError):
        ficha_service.approve_plan(
            sessao,
            user=cenario.mario,
            code=codigo,
            data=ApprovalInput(decision="Aprovado"),
            reference_date=REFERENCIA,
        )


def test_responsavel_pelo_plano_nao_aprova(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo, probability=4, impact=4)
    _salvar_plano(
        sessao,
        cenario,
        codigo,
        strategy="Aceitar",
        plan="Aceito com base no cadastro de interferências do cliente e na reserva.",
        target_severity="moderado",
        plan_responsible_id=cenario.gil.person_id,
    )

    with pytest.raises(AccessDeniedError) as recusa:
        ficha_service.approve_plan(
            sessao,
            user=cenario.gil,
            code=codigo,
            data=ApprovalInput(decision="Aprovado"),
            reference_date=REFERENCIA,
        )

    assert "segregação de funções" in str(recusa.value)


def test_aprovar_plano_aceitar_leva_a_monitorado(sessao: Session, cenario: Cenario) -> None:
    codigo = _plano_pendente(sessao, cenario)

    resultado = ficha_service.approve_plan(
        sessao,
        user=cenario.ada,
        code=codigo,
        data=ApprovalInput(decision="Aprovado"),
        reference_date=REFERENCIA,
    )

    assert resultado.situation == "Monitorado"
    linha = service.find_risk(sessao, user=cenario.ada, code=codigo, reference_date=REFERENCIA)
    assert linha is not None and not linha.plan_pending


def test_devolver_plano_exige_comentario(sessao: Session, cenario: Cenario) -> None:
    codigo = _plano_pendente(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        ficha_service.approve_plan(
            sessao,
            user=cenario.ada,
            code=codigo,
            data=ApprovalInput(decision="Devolvido", comment="Curto"),
            reference_date=REFERENCIA,
        )

    assert "mínimo de 10 caracteres" in str(recusa.value)

    ficha_service.approve_plan(
        sessao,
        user=cenario.ada,
        code=codigo,
        data=ApprovalInput(decision="Devolvido", comment="Detalhe o custo da resposta."),
        reference_date=REFERENCIA,
    )
    folha = ficha_service.find_risk_sheet(
        sessao, user=cenario.ada, code=codigo, reference_date=REFERENCIA
    )
    assert folha is not None and folha.approval_returned


# ── Revisão periódica ────────────────────────────────────────────────────────────────────────


def _revisao(**campos: object) -> ReviewInput:
    base = ReviewInput(
        reviewed_on=REFERENCIA,
        assessed_situation="Sem mudança",
        probability=3,
        impact=4,
        comment="Revisão de rotina, sem mudanças no cenário.",
        trigger=False,
        next_review=REFERENCIA + timedelta(days=25),
    )
    return replace(base, **campos)


def _revisar(sessao: Session, cenario: Cenario, codigo: str, **campos: object):
    return ficha_service.review_risk(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=_revisao(**campos),
        reference_date=REFERENCIA,
    )


def test_revisao_nunca_posterga_a_cadencia(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)  # alto: cadência de 30 dias

    with pytest.raises(InvalidDataError) as recusa:
        _revisar(sessao, cenario, codigo, next_review=REFERENCIA + timedelta(days=31))

    assert "nunca postergar" in str(recusa.value)


def test_revisao_pode_antecipar_a_cadencia(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resultado = _revisar(sessao, cenario, codigo, next_review=REFERENCIA + timedelta(days=10))

    assert resultado.score == 12
    linha = service.find_risk(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert linha is not None and linha.next_review == REFERENCIA + timedelta(days=10)


def test_revisao_atualiza_a_avaliacao_vigente(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    _revisar(
        sessao,
        cenario,
        codigo,
        probability=2,
        impact=4,
        assessed_situation="Risco reduzido",
    )

    linha = service.find_risk(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert linha is not None and linha.current is not None
    assert linha.current.probability == 2
    assert linha.current.score == 8


def test_situacao_apurada_precisa_bater_com_o_score(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    with pytest.raises(InvalidDataError) as recusa:
        _revisar(sessao, cenario, codigo, assessed_situation="Risco reduzido")

    assert "a situação apurada deve ser" in str(recusa.value)


def test_gatilho_forca_reavaliacao_e_entra_na_pauta(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resultado = _revisar(sessao, cenario, codigo, trigger=True)

    assert resultado.re_assess
    folha = ficha_service.find_risk_sheet(
        sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA
    )
    assert folha is not None
    assert folha.trigger_on == REFERENCIA
    assert any("Gatilho ocorrido" in motivo for motivo in folha.pauta)


def test_materializado_abre_o_encerramento(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resultado = _revisar(
        sessao, cenario, codigo, assessed_situation="Risco materializado", trigger=True
    )

    assert resultado.closes_with == "Materializado"


# ── Encerramento ─────────────────────────────────────────────────────────────────────────────


def _encerrar(sessao: Session, cenario: Cenario, codigo: str, **campos: object):
    base = ClosingInput(
        reason="Não se materializou",
        closed_on=REFERENCIA,
        lesson="Estoque de segurança de insumos críticos reduziu a exposição logística.",
        action_subject="Tratar o problema decorrente do risco",
        action_responsible_id=cenario.mario.person_id,
        action_planned_date=REFERENCIA + timedelta(days=7),
    )
    return ficha_service.close_risk(
        sessao,
        user=cenario.gil,
        code=codigo,
        data=replace(base, **campos),
        reference_date=REFERENCIA,
    )


def test_encerrar_exige_licao(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    with pytest.raises(InvalidDataError) as recusa:
        _encerrar(sessao, cenario, codigo, lesson="Curta")

    assert "Lição aprendida" in str(recusa.value)


def test_encerrar_com_acao_aberta_e_recusado_salvo_materializado(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)
    _acao(sessao, cenario, codigo)

    with pytest.raises(InvalidDataError) as recusa:
        _encerrar(sessao, cenario, codigo)

    assert "ação em aberto" in str(recusa.value)

    resultado = _encerrar(
        sessao,
        cenario,
        codigo,
        reason="Materializado",
        real_schedule_days=10,
        real_cost_cents=1_000_000,
        generate_action=True,
    )

    assert resultado.situation == "Materializado"
    assert resultado.lesson_code
    assert resultado.action_item


def test_materializado_cria_licao_acao_e_sm_na_mesma_transacao(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    resultado = _encerrar(
        sessao,
        cenario,
        codigo,
        reason="Materializado",
        real_schedule_days=21,
        real_cost_cents=40_000_000,
        generate_action=True,
        open_change=True,
    )

    assert resultado.lesson_code.startswith("LA-")
    assert resultado.change_code is not None and resultado.change_code.startswith("SM-")
    assert resultado.action_item == "1"
    risco = sessao.scalars(select(Risk).where(Risk.code == codigo)).one()
    assert risco.lesson_id is not None
    assert risco.closing_change_id is not None
    assert risco.closed_by_id == cenario.gil.person_id
    assert risco.situation == "Materializado"
    contagens = central_acoes.count_actions_of_origin(
        sessao,
        user=cenario.gil,
        origin_kind="Risco",
        references=[codigo],
        reference_date=REFERENCIA,
    )
    assert contagens[codigo].total == 1  # a ação do problema, criada no encerramento


def test_oportunidade_materializada_nao_gera_problema_nem_sm(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario, nature="Oportunidade")
    _avaliar(
        sessao,
        cenario,
        codigo,
        probability=2,
        impact=2,
        dimensions={"prazo": 2},
        cost_impact_cents=10_000_000,
    )

    resultado = _encerrar(
        sessao,
        cenario,
        codigo,
        reason="Materializado",
        real_schedule_days=9,
        real_cost_cents=3_000_000,
        open_change=True,
        generate_action=True,
    )

    assert resultado.situation == "Materializado"
    assert resultado.change_code is None
    assert resultado.action_item is None
    risco = sessao.scalars(select(Risk).where(Risk.code == codigo)).one()
    assert risco.lesson_id is not None and risco.closing_change_id is None


def test_encerrar_exige_gestor(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)
    data = ClosingInput(
        reason="Não se materializou",
        closed_on=REFERENCIA,
        lesson="Estoque de segurança de insumos críticos reduziu a exposição logística.",
    )

    with pytest.raises(AccessDeniedError):
        ficha_service.close_risk(
            sessao, user=cenario.mario, code=codigo, data=data, reference_date=REFERENCIA
        )


# ── Reabertura ───────────────────────────────────────────────────────────────────────────────


def test_reabrir_devolve_a_situacao_e_limpa_o_encerramento(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)
    _acao(sessao, cenario, codigo)
    _salvar_plano(sessao, cenario, codigo, target_severity="baixo")
    _encerrar(
        sessao,
        cenario,
        codigo,
        reason="Materializado",
        real_schedule_days=5,
        real_cost_cents=100_000,
    )

    resultado = ficha_service.reopen_risk(
        sessao,
        user=cenario.gil,
        code=codigo,
        data=ReopenInput(justification="O risco voltou a ser monitorado pela gerência."),
        reference_date=REFERENCIA,
    )

    assert resultado.situation == "Em tratamento"
    risco = sessao.scalars(select(Risk).where(Risk.code == codigo)).one()
    assert risco.closing_reason is None and risco.lesson_id is None
    assert risco.closed_by_id is None and risco.situation == "Em tratamento"
    folha = ficha_service.find_risk_sheet(
        sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA
    )
    assert folha is not None
    assert any("Justificativa" in linha.text for linha in folha.history)


def test_reabrir_exige_gestor_e_justificativa(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)
    _encerrar(sessao, cenario, codigo)

    with pytest.raises(AccessDeniedError):
        ficha_service.reopen_risk(
            sessao,
            user=cenario.mario,
            code=codigo,
            data=ReopenInput(justification="O risco voltou a ser monitorado pela gerência."),
            reference_date=REFERENCIA,
        )

    with pytest.raises(InvalidDataError) as recusa:
        ficha_service.reopen_risk(
            sessao,
            user=cenario.gil,
            code=codigo,
            data=ReopenInput(justification="Curta"),
            reference_date=REFERENCIA,
        )

    assert "mínimo de 10 caracteres" in str(recusa.value)


# ── Ficha e linha do tempo ───────────────────────────────────────────────────────────────────


def test_a_ficha_traz_revisoes_acoes_e_historico(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)
    _acao(sessao, cenario, codigo)
    _revisar(sessao, cenario, codigo)

    folha = ficha_service.find_risk_sheet(
        sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA
    )

    assert folha is not None
    assert len(folha.reviews) == 2  # a avaliação inicial e a revisão
    assert folha.actions[0].subject == "Contratar a consultoria ambiental"
    assert any("Avaliação inerente" in linha.text for linha in folha.history)
    assert any("Revisão registrada" in linha.text for linha in folha.history)
    revisoes = sessao.scalars(select(RiskReview).where(RiskReview.risk_id == folha.line.id)).all()
    assert any(item.kind == "revisao" for item in revisoes)
