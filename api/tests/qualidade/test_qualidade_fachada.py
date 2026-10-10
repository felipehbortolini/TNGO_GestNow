"""A fachada da Qualidade (ISSUE-068): fluxo, prazo, concessão, segregação, lição e integrações.

Os testes chamam o serviço direto, com o cenário na transação do teste e a data de referência
25/09/2026. A ação corretiva é lida pela fachada da Central (D9), nunca da tabela.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import attachment_origins, origin_links
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.validation import CompletionRequest
from src.modulos.governanca.lessons_models import Lesson
from src.modulos.qualidade import service
from src.modulos.qualidade.validation import (
    ActionInput,
    CancellationInput,
    CostInput,
    ResponsibleInput,
    RncFilters,
)
from tests.apoio_qualidade import REFERENCIA, Cenario, nova_abertura, nova_analise, nova_verificacao


def _abrir(sessao: Session, cenario: Cenario, **campos: object) -> str:
    resultado = service.open_rnc(
        sessao, user=cenario.mario, data=nova_abertura(cenario, **campos), reference_date=REFERENCIA
    )
    return resultado.code


def _analise_para(cenario: Cenario, **campos: object):
    return nova_analise(
        actions=(
            ActionInput(
                subject="Refazer as soldas reprovadas da linha 310-P-014",
                responsible_id=cenario.mario.person_id,
                planned_date=REFERENCIA + timedelta(days=10),
                description="Requalificar o soldador antes do retrabalho.",
            ),
        ),
        **campos,
    )


def _analisar(sessao: Session, cenario: Cenario, codigo: str, **campos: object) -> None:
    service.assign_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=ResponsibleInput(responsible_id=cenario.mario.person_id),
        reference_date=REFERENCIA,
    )
    service.record_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=_analise_para(cenario, **campos),
        reference_date=REFERENCIA,
    )


def _concluir_acoes(sessao: Session, cenario: Cenario, codigo: str) -> None:
    for acao in actions.actions_of_origin(
        sessao, user=cenario.mario, origin_kind="RNC", reference=codigo, reference_date=REFERENCIA
    ):
        actions.complete_action(
            sessao,
            user=cenario.mario,
            request=CompletionRequest(
                action_id=acao.id, completed_on=REFERENCIA, version=acao.version
            ),
            reference_date=REFERENCIA,
        )


def _enviar(sessao: Session, cenario: Cenario) -> str:
    codigo = _abrir(sessao, cenario)
    _analisar(sessao, cenario, codigo)
    _concluir_acoes(sessao, cenario, codigo)
    service.send_to_verification(
        sessao, user=cenario.mario, code=codigo, version=None, reference_date=REFERENCIA
    )
    return codigo


# ── Abertura e prazo ─────────────────────────────────────────────────────────


def test_abertura_sem_contencao_e_recusada(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.open_rnc(
            sessao,
            user=cenario.mario,
            data=nova_abertura(cenario, containment="curta"),
            reference_date=REFERENCIA,
        )

    assert "contenção imediata" in recusa.value.messages()[0]


def test_o_prazo_da_abertura_segue_a_severidade(sessao: Session, cenario: Cenario) -> None:
    critica = _abrir(sessao, cenario, severity="Crítica")
    menor = _abrir(sessao, cenario, severity="Menor")

    linha_critica = service.find_rnc(
        sessao, user=cenario.mario, code=critica, reference_date=REFERENCIA
    )
    linha_menor = service.find_rnc(
        sessao, user=cenario.mario, code=menor, reference_date=REFERENCIA
    )
    assert linha_critica is not None and linha_critica.deadline == REFERENCIA + timedelta(days=15)
    assert linha_menor is not None and linha_menor.deadline == REFERENCIA + timedelta(days=45)


def test_visualizador_nao_abre_rnc(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.open_rnc(
            sessao, user=cenario.vera, data=nova_abertura(cenario), reference_date=REFERENCIA
        )


# ── Análise e ações na Central ───────────────────────────────────────────────


def test_a_analise_cria_ao_menos_uma_acao_com_origem_rnc(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)

    _analisar(sessao, cenario, codigo)

    criadas = actions.actions_of_origin(
        sessao, user=cenario.mario, origin_kind="RNC", reference=codigo, reference_date=REFERENCIA
    )
    assert len(criadas) == 1
    assert criadas[0].item == "1"
    assert criadas[0].group == "Ação corretiva"
    linha = service.find_rnc(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert linha is not None
    assert linha.situation == "Ação corretiva"
    assert (linha.actions.total, linha.actions.open) == (1, 1)
    assert linha.actions.open_subject.startswith("Refazer as soldas")


def test_reparo_sem_concessao_e_recusado(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)
    service.assign_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=ResponsibleInput(responsible_id=cenario.mario.person_id),
        reference_date=REFERENCIA,
    )

    with pytest.raises(InvalidDataError) as recusa:
        service.record_analysis(
            sessao,
            user=cenario.mario,
            code=codigo,
            data=_analise_para(cenario, disposition="Reparo"),
            reference_date=REFERENCIA,
        )

    assert "concessão" in recusa.value.messages()[0]


def test_a_verificacao_recusa_acao_aberta_e_preve_trinta_dias(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _abrir(sessao, cenario)
    _analisar(sessao, cenario, codigo)

    with pytest.raises(InvalidDataError) as recusa:
        service.send_to_verification(
            sessao, user=cenario.mario, code=codigo, version=None, reference_date=REFERENCIA
        )
    assert "em aberto" in recusa.value.messages()[0]

    _concluir_acoes(sessao, cenario, codigo)
    prevista = service.send_to_verification(
        sessao, user=cenario.mario, code=codigo, version=None, reference_date=REFERENCIA
    )
    assert prevista == REFERENCIA + timedelta(days=30)
    linha = service.find_rnc(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert linha is not None and linha.situation == "Verificação de eficácia"


# ── Verificação de eficácia ──────────────────────────────────────────────────


def test_a_verificacao_exige_gestor(sessao: Session, cenario: Cenario) -> None:
    codigo = _enviar(sessao, cenario)

    with pytest.raises(AccessDeniedError) as recusa:
        service.verify_effectiveness(
            sessao,
            user=cenario.mario,
            code=codigo,
            data=nova_verificacao(),
            reference_date=REFERENCIA,
        )

    assert "Gestor" in str(recusa.value)


def test_quem_respondeu_pela_analise_nao_verifica(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)
    service.assign_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=ResponsibleInput(responsible_id=cenario.gil.person_id),
        reference_date=REFERENCIA,
    )
    service.record_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=_analise_para(cenario),
        reference_date=REFERENCIA,
    )
    _concluir_acoes(sessao, cenario, codigo)
    service.send_to_verification(
        sessao, user=cenario.mario, code=codigo, version=None, reference_date=REFERENCIA
    )

    with pytest.raises(AccessDeniedError) as recusa:
        service.verify_effectiveness(
            sessao,
            user=cenario.gil,
            code=codigo,
            data=nova_verificacao(),
            reference_date=REFERENCIA,
        )

    assert "segregação" in str(recusa.value)


def test_ineficaz_volta_para_a_acao_corretiva_e_conta_reincidencia(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _enviar(sessao, cenario)

    resultado = service.verify_effectiveness(
        sessao,
        user=cenario.ada,
        code=codigo,
        data=nova_verificacao(effective=False),
        reference_date=REFERENCIA,
    )

    assert resultado.closed is False
    linha = service.find_rnc(sessao, user=cenario.ada, code=codigo, reference_date=REFERENCIA)
    assert linha is not None
    assert linha.situation == "Ação corretiva"
    assert linha.recurrence_count == 1


def test_eficaz_encerra_e_cria_a_licao_em_rascunho_na_mesma_transacao(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _enviar(sessao, cenario)

    resultado = service.verify_effectiveness(
        sessao,
        user=cenario.ada,
        code=codigo,
        data=nova_verificacao(
            register_lesson=True,
            lesson_title="Requalificar o soldador antes do retrabalho",
            lesson_recommendation="Exigir a qualificação vigente do soldador na liberação da frente.",
        ),
        reference_date=REFERENCIA,
    )

    assert resultado.closed is True
    assert resultado.lesson_code is not None
    licao = sessao.scalars(select(Lesson).where(Lesson.code == resultado.lesson_code)).one()
    assert licao.situation == "Rascunho"
    assert licao.origin == "RNC"
    assert licao.origin_ref == codigo
    linha = service.find_rnc(sessao, user=cenario.ada, code=codigo, reference_date=REFERENCIA)
    assert linha is not None
    assert linha.situation == "Encerrada"
    assert linha.lesson_id == licao.id


# ── Cancelamento e custo ─────────────────────────────────────────────────────


def test_cancelamento_depois_da_acao_corretiva_e_recusado(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _abrir(sessao, cenario)
    _analisar(sessao, cenario, codigo)

    with pytest.raises(InvalidDataError) as recusa:
        service.cancel_rnc(
            sessao,
            user=cenario.gil,
            code=codigo,
            data=CancellationInput(reason="Registro em duplicidade na mesma frente."),
            reference_date=REFERENCIA,
        )

    assert "antes da ação corretiva" in recusa.value.messages()[0]


def test_cancelamento_antes_da_acao_corretiva_exige_gestor_e_motivo(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _abrir(sessao, cenario)

    with pytest.raises(AccessDeniedError):
        service.cancel_rnc(
            sessao,
            user=cenario.mario,
            code=codigo,
            data=CancellationInput(reason="Registro em duplicidade na mesma frente."),
            reference_date=REFERENCIA,
        )

    service.cancel_rnc(
        sessao,
        user=cenario.gil,
        code=codigo,
        data=CancellationInput(reason="Registro em duplicidade na mesma frente."),
        reference_date=REFERENCIA,
    )
    linha = service.find_rnc(sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA)
    assert linha is not None and linha.situation == "Cancelada"


def test_o_custo_atualiza_so_com_justificativa_e_rnc_ativa(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _abrir(sessao, cenario)

    with pytest.raises(InvalidDataError):
        service.update_cost(
            sessao,
            user=cenario.mario,
            code=codigo,
            data=CostInput(cost_cents=340_000, justification="curta"),
            reference_date=REFERENCIA,
        )

    service.update_cost(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=CostInput(cost_cents=3_400_000, justification="Retrabalho das seis juntas e ensaio."),
        reference_date=REFERENCIA,
    )
    linha = service.find_rnc(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
    assert linha is not None and linha.cost_cents == 3_400_000


# ── Listagem, KPIs, vínculos e anexos ───────────────────────────────────────


def test_a_listagem_filtra_e_resume(sessao: Session, cenario: Cenario) -> None:
    vencida = _abrir(
        sessao,
        cenario,
        rnc_date=REFERENCIA - timedelta(days=60),
        severity="Maior",
        origin_ref="INS-2026-0001",
    )
    _abrir(sessao, cenario, origin="Auditoria", origin_ref="AUD-TN-2026-02", severity="Crítica")

    listagem = service.list_rncs(
        sessao,
        user=cenario.mario,
        scope=Scope(project_id=cenario.projeto.id, source="padrao"),
        filters=RncFilters(situation="vencidas"),
        reference_date=REFERENCIA,
    )

    assert listagem.total == 1
    assert listagem.lines[0].code == vencida
    assert listagem.lines[0].overdue is True
    resumo = service.rnc_summary(
        sessao,
        user=cenario.mario,
        scope=Scope(project_id=cenario.projeto.id, source="padrao"),
        reference_date=REFERENCIA,
    )
    assert resumo.active == 2
    assert resumo.critical == 1
    assert resumo.overdue == 1


def test_a_busca_por_numero_encontra_a_rnc(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)

    listagem = service.list_rncs(
        sessao,
        user=cenario.mario,
        scope=Scope(project_id=cenario.projeto.id, source="padrao"),
        filters=RncFilters(search=codigo),
        reference_date=REFERENCIA,
    )

    assert [linha.code for linha in listagem.lines] == [codigo]


def test_o_link_de_origem_e_os_anexos_da_rnc(sessao: Session, cenario: Cenario) -> None:
    codigo = _abrir(sessao, cenario)

    link = origin_links.resolve("RNC", codigo)
    assert link.has_link is True
    assert "busca=" in (link.url or "")

    registro = service.read_rnc_origin(
        sessao,
        user=cenario.mario,
        record_id=service.find_rnc(
            sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA
        ).id,
    )
    assert registro is not None and registro.project_id == cenario.projeto.id
    assert attachment_origins.find("rnc") is not None


def test_a_ficha_traz_a_acao_a_trilha_e_a_licao(sessao: Session, cenario: Cenario) -> None:
    codigo = _enviar(sessao, cenario)
    service.verify_effectiveness(
        sessao,
        user=cenario.ada,
        code=codigo,
        data=nova_verificacao(
            register_lesson=True,
            lesson_title="Requalificar o soldador antes do retrabalho",
            lesson_recommendation="Exigir a qualificação vigente do soldador na liberação da frente.",
        ),
        reference_date=REFERENCIA,
    )

    ficha = service.rnc_sheet(sessao, user=cenario.ada, code=codigo, reference_date=REFERENCIA)

    assert ficha is not None
    assert len(ficha.actions) == 1
    assert ficha.actions[0].status_label == "Concluída"
    assert ficha.lesson_code is not None
    assert any("RNC aberta" in linha.text for linha in ficha.history)
    assert any("Eficácia verificada" in linha.text for linha in ficha.history)


def test_data_da_verificacao_nao_pode_ser_futura(sessao: Session, cenario: Cenario) -> None:
    codigo = _enviar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        service.verify_effectiveness(
            sessao,
            user=cenario.ada,
            code=codigo,
            data=nova_verificacao(checked_on=REFERENCIA + timedelta(days=1)),
            reference_date=REFERENCIA,
        )

    assert "posterior" in recusa.value.messages()[0]
