"""A fachada das Auditorias (ISSUE-070): plano, reprogramação, resultado e as RNC.

Os testes chamam o serviço direto, com o cenário na transação do teste e a data de referência
25/09/2026. Nova auditoria com data no passado é recusada; a reprogramação só vale na
planejada, com a nova data até a referência e a justificativa (mínimo de 10 caracteres), e
deixa a linha em `auditoria_reprogramacao` com o autor; o resultado só entra na planejada;
cada Não conformidade abre a RNC na mesma transação (D9) com o vínculo e a contenção padrão; e
não pode haver mais NC que itens não conformes.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.qualidade import service
from src.modulos.qualidade.models import AuditFinding, AuditReschedule, QualityAudit, Rnc
from src.modulos.qualidade.validation import AuditFilters
from tests.apoio_qualidade import (
    REFERENCIA,
    Cenario,
    nova_auditoria,
    nova_constatacao,
    resultado_auditoria,
)


def _scope(cenario: Cenario) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _planejar(sessao: Session, cenario: Cenario, **campos: object):
    return service.create_audit(
        sessao,
        user=cenario.mario,
        data=nova_auditoria(cenario, **campos),
        reference_date=REFERENCIA,
    )


def _resultar(sessao: Session, cenario: Cenario, code: str, **campos: object):
    base = resultado_auditoria(**campos)
    return service.record_result(
        sessao, user=cenario.mario, code=code, data=base, reference_date=REFERENCIA
    )


# ── Planejar e reprogramar ──────────────────────────────────────────────────────────────────


def test_a_auditoria_nasce_com_o_codigo_do_padrao_do_projeto(sessao: Session, cenario: Cenario):
    primeira = _planejar(sessao, cenario)
    segunda = _planejar(sessao, cenario, scope="Rastreabilidade de materiais")

    assert primeira.code == "AUD-TN-2026-01", "o padrão do projeto e dois dígitos"
    assert segunda.code == "AUD-TN-2026-02"

    linha = service.find_audit(
        sessao, user=cenario.mario, code=primeira.code, reference_date=REFERENCIA
    )
    assert linha is not None
    assert linha.situation == "Planejada"
    assert linha.auditee_name == cenario.empresa.name
    assert linha.lead_auditor_name == cenario.mario.name


def test_auditoria_com_data_no_passado_e_recusada(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _planejar(sessao, cenario, audit_date=REFERENCIA - timedelta(days=1))

    assert "não pode ser anterior à referência" in recusa.value.messages()[0]
    assert sessao.scalars(select(QualityAudit)).all() == []


def test_o_visualizador_nao_planeja_nem_resulta(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.create_audit(
            sessao, user=cenario.vera, data=nova_auditoria(cenario), reference_date=REFERENCIA
        )

    criada = _planejar(sessao, cenario)
    with pytest.raises(AccessDeniedError):
        service.record_result(
            sessao,
            user=cenario.vera,
            code=criada.code,
            data=resultado_auditoria(),
            reference_date=REFERENCIA,
        )
    with pytest.raises(AccessDeniedError):
        service.save_audit(
            sessao,
            user=cenario.vera,
            code=criada.code,
            data=nova_auditoria(cenario, audit_date=REFERENCIA + timedelta(days=20)),
            reference_date=REFERENCIA,
        )


def test_a_reprogramacao_so_vale_na_planejada(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)
    _resultar(sessao, cenario, criada.code)

    with pytest.raises(InvalidDataError) as recusa:
        service.save_audit(
            sessao,
            user=cenario.mario,
            code=criada.code,
            data=nova_auditoria(cenario, audit_date=REFERENCIA + timedelta(days=20)),
            reference_date=REFERENCIA,
        )

    assert "Só a auditoria planejada" in recusa.value.messages()[0]


def test_a_reprogramacao_sem_justificativa_e_recusada(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        service.save_audit(
            sessao,
            user=cenario.mario,
            code=criada.code,
            data=nova_auditoria(
                cenario, audit_date=REFERENCIA + timedelta(days=20), justification="Curta."
            ),
            reference_date=REFERENCIA,
        )

    assert "Reprogramação exige justificativa" in recusa.value.messages()[0]
    assert sessao.scalars(select(AuditReschedule)).all() == []


def test_a_reprogramacao_grava_a_linha_com_o_autor(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)
    nova_data = REFERENCIA + timedelta(days=30)

    salva = service.save_audit(
        sessao,
        user=cenario.mario,
        code=criada.code,
        data=nova_auditoria(
            cenario,
            audit_date=nova_data,
            justification="Negociação com a contratada para a mobilização da equipe.",
        ),
        reference_date=REFERENCIA,
    )

    assert salva.rescheduled is True
    linha = sessao.scalars(select(AuditReschedule)).one()
    assert (linha.previous_date, linha.new_date) == (REFERENCIA + timedelta(days=10), nova_data)
    assert linha.author_id == cenario.mario.person_id
    assert linha.registered_at is not None
    assert linha.justification == "Negociação com a contratada para a mobilização da equipe."

    ficha = service.audit_sheet(
        sessao, user=cenario.mario, code=criada.code, reference_date=REFERENCIA
    )
    assert ficha is not None
    assert ficha.audit_date == nova_data
    assert ficha.baseline_date == REFERENCIA + timedelta(days=10)
    assert len(ficha.reschedules) == 1
    assert ficha.reschedules[0].author_name == cenario.mario.name


def test_a_reprogramacao_para_data_passada_e_recusada(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        service.save_audit(
            sessao,
            user=cenario.mario,
            code=criada.code,
            data=nova_auditoria(
                cenario,
                audit_date=REFERENCIA - timedelta(days=1),
                justification="Justificativa suficientemente longa para passar.",
            ),
            reference_date=REFERENCIA,
        )

    assert "A nova data não pode ser anterior à referência" in recusa.value.messages()[0]


def test_a_edicao_sem_mudar_a_data_nao_gera_reprogramacao(
    sessao: Session, cenario: Cenario
) -> None:
    criada = _planejar(sessao, cenario)

    salva = service.save_audit(
        sessao,
        user=cenario.mario,
        code=criada.code,
        data=nova_auditoria(cenario, scope="Qualificação de soldadores e procedimentos"),
        reference_date=REFERENCIA,
    )

    assert salva.rescheduled is False
    assert sessao.scalars(select(AuditReschedule)).all() == []
    linha = service.find_audit(
        sessao, user=cenario.mario, code=criada.code, reference_date=REFERENCIA
    )
    assert linha is not None and linha.scope == "Qualificação de soldadores e procedimentos"


# ── Resultado, constatações e a RNC ─────────────────────────────────────────────────────────


def test_o_resultado_so_entra_em_auditoria_planejada(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)
    _resultar(sessao, cenario, criada.code)

    with pytest.raises(InvalidDataError) as recusa:
        _resultar(sessao, cenario, criada.code)

    assert "O resultado desta auditoria já foi registrado." in recusa.value.messages()[0]


def test_itens_conformes_fora_da_faixa_e_recusado(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _resultar(sessao, cenario, criada.code, items_verified=40, items_conforming=41)

    assert "Itens conformes entre zero e o total verificado" in recusa.value.messages()[0]


def test_mais_nc_que_itens_nao_conformes_e_recusado(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _resultar(
            sessao,
            cenario,
            criada.code,
            items_verified=10,
            items_conforming=10,
            findings=(nova_constatacao(),),
        )

    assert recusa.value.messages()[0] == (
        "Há mais não conformidades (1) que itens não conformes (0)."
    )
    assert sessao.scalars(select(Rnc)).all() == []
    assert sessao.scalars(select(AuditFinding)).all() == []


def test_cada_nc_abre_a_rnc_com_o_vinculo_e_a_contencao_padrao(
    sessao: Session, cenario: Cenario
) -> None:
    criada = _planejar(sessao, cenario)

    resultado = _resultar(
        sessao,
        cenario,
        criada.code,
        items_verified=40,
        items_conforming=36,
        findings=(nova_constatacao(),),
        summary="Conformidade abaixo da meta no controle tecnológico do concreto.",
    )

    assert resultado.rnc_codes == ("RNC-TN-2026-0001",)
    rnc = sessao.scalars(select(Rnc).where(Rnc.code == resultado.rnc_codes[0])).one()
    assert rnc.origin == "Auditoria"
    assert rnc.origin_ref == criada.code
    assert rnc.company_id == cenario.empresa.id
    assert rnc.severity == "Maior"
    assert rnc.description == (
        "Ensaios de abatimento sem registro em 3 caminhões. Requisito: NBR 12655, 6.2."
    )
    assert rnc.containment == (
        f"Contenção a definir pelo auditado em até 48 horas da auditoria {criada.code}."
    )
    constatacao = sessao.scalars(select(AuditFinding)).one()
    assert constatacao.rnc_id == rnc.id
    assert constatacao.order == 1

    ficha = service.audit_sheet(
        sessao, user=cenario.mario, code=criada.code, reference_date=REFERENCIA
    )
    assert ficha is not None
    assert ficha.situation == "Realizada"
    assert ficha.performed_on == REFERENCIA
    assert ficha.items_verified == 40
    assert ficha.items_conforming == 36
    assert ficha.conformity_pct == Decimal("90.0")
    assert ficha.summary == "Conformidade abaixo da meta no controle tecnológico do concreto."
    assert ficha.open_nc == 1
    assert ficha.findings[0].rnc_code == rnc.code
    assert ficha.findings[0].rnc_situation == "Aberta"
    assert ficha.findings[0].rnc_active is True


def test_observacoes_e_oportunidades_nao_abrem_rnc(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    resultado = _resultar(
        sessao,
        cenario,
        criada.code,
        items_verified=40,
        items_conforming=40,
        findings=(
            nova_constatacao(
                finding_type="Observação",
                description="Laboratório sem controle de temperatura da câmara úmida.",
                requirement="NBR 5738",
                discipline="",
                severity="",
            ),
            nova_constatacao(
                finding_type="Oportunidade de melhoria",
                description="Painel diário de resultados de fck na frente de obra.",
                requirement="",
                discipline="",
                severity="",
            ),
        ),
    )

    assert resultado.rnc_codes == ()
    assert sessao.scalars(select(Rnc)).all() == []
    ficha = service.audit_sheet(
        sessao, user=cenario.mario, code=criada.code, reference_date=REFERENCIA
    )
    assert ficha is not None
    assert ficha.non_conformities == 0
    assert [item.finding_type for item in ficha.findings] == [
        "Observação",
        "Oportunidade de melhoria",
    ]


def test_a_nc_sem_disciplina_ou_severidade_e_recusada(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)

    with pytest.raises(InvalidDataError) as sem_disciplina:
        _resultar(sessao, cenario, criada.code, findings=(nova_constatacao(discipline=""),))

    assert "escolha a disciplina da RNC" in sem_disciplina.value.messages()[0]

    with pytest.raises(InvalidDataError) as sem_severidade:
        _resultar(sessao, cenario, criada.code, findings=(nova_constatacao(severity=""),))

    assert "escolha a severidade da RNC" in sem_severidade.value.messages()[0]
    assert sessao.scalars(select(AuditFinding)).all() == []


def test_a_auditoria_vencida_aparece_atrasada(sessao: Session, cenario: Cenario) -> None:
    criada = _planejar(sessao, cenario)
    futuro = _planejar(sessao, cenario, audit_date=REFERENCIA + timedelta(days=30))
    registro = sessao.scalars(select(QualityAudit).where(QualityAudit.code == criada.code)).one()
    registro.audit_date = REFERENCIA - timedelta(days=3)
    sessao.flush()

    linhas = service.list_audits(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=AuditFilters(),
        reference_date=REFERENCIA,
    )
    por_codigo = {linha.code: linha for linha in linhas.lines}
    assert por_codigo[criada.code].overdue is True
    assert por_codigo[criada.code].days_overdue == 3
    assert por_codigo[futuro.code].overdue is False

    atrasadas = service.list_audits(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=AuditFilters(situation="Atrasada"),
        reference_date=REFERENCIA,
    )
    assert [linha.code for linha in atrasadas.lines] == [criada.code]
    assert atrasadas.summary.overdue == 1
    assert atrasadas.summary.adherence is not None
    assert atrasadas.summary.adherence == Decimal("0.0")


def test_a_lista_filtra_por_tipo_e_busca_e_ordena_por_data(
    sessao: Session, cenario: Cenario
) -> None:
    primeira = _planejar(sessao, cenario, audit_date=REFERENCIA + timedelta(days=20))
    segunda = _planejar(
        sessao,
        cenario,
        audit_date=REFERENCIA + timedelta(days=5),
        audit_type="Fornecedor",
        scope="Rastreabilidade de materiais",
    )

    linhas = service.list_audits(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=AuditFilters(),
        reference_date=REFERENCIA,
    )
    assert [linha.code for linha in linhas.lines] == [segunda.code, primeira.code], (
        "a lista vem da data mais próxima para a mais distante, como o protótipo"
    )

    por_tipo = service.list_audits(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=AuditFilters(audit_type="Fornecedor"),
        reference_date=REFERENCIA,
    )
    assert [linha.code for linha in por_tipo.lines] == [segunda.code]

    por_busca = service.list_audits(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=AuditFilters(search="rastreabilidade"),
        reference_date=REFERENCIA,
    )
    assert [linha.code for linha in por_busca.lines] == [segunda.code]


def test_o_resumo_do_programa_calcula_aderencia_e_conformidade(
    sessao: Session, cenario: Cenario
) -> None:
    realizada = _planejar(sessao, cenario, audit_date=REFERENCIA)
    _resultar(sessao, cenario, realizada.code, items_verified=40, items_conforming=36)
    _planejar(sessao, cenario, audit_date=REFERENCIA, scope="Rastreabilidade de materiais")
    _planejar(sessao, cenario, audit_date=REFERENCIA + timedelta(days=30))

    resumo = service.audit_summary(
        sessao, user=cenario.mario, scope=_scope(cenario), reference_date=REFERENCIA
    )

    assert (
        service.parameters(sessao, reference_date=REFERENCIA)["metaConformidadeAuditoriaPct"] == 90
    ), "a meta do grupo Qualidade que a tela lê"
    assert resumo.due == 2
    assert resumo.done == 1
    assert resumo.adherence == Decimal("50.0")
    assert resumo.overdue == 0
    assert (resumo.verified_items, resumo.conforming_items) == (40, 36)
    assert resumo.conformity == Decimal("90.0")
    assert resumo.nc == 0
    assert resumo.open_nc == 0
    assert resumo.next_audit is not None
    assert resumo.next_audit.audit_date == REFERENCIA

    sem_previstas = service.audit_summary(
        sessao,
        user=cenario.mario,
        scope=Scope(project_id=cenario.outro.id, source="url"),
        reference_date=REFERENCIA,
    )
    assert sem_previstas.due == 0
    assert sem_previstas.adherence is None
    assert sem_previstas.conformity is None


def test_o_escopo_nao_alcanca_a_auditoria_do_outro_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    _planejar(sessao, cenario)
    service.create_audit(
        sessao,
        user=cenario.mario,
        data=nova_auditoria(cenario, project_id=cenario.outro.id),
        reference_date=REFERENCIA,
    )

    listagem = service.list_audits(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=AuditFilters(),
        reference_date=REFERENCIA,
    )
    assert [linha.project_id for linha in listagem.lines] == [cenario.projeto.id]
