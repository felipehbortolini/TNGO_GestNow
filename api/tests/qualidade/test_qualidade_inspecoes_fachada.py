"""A fachada das Inspeções e ITP (ISSUE-069): ITP, pontos, reprovação e o FAT.

Os testes chamam o serviço direto, com o cenário na transação do teste e a data de referência
25/09/2026. A inspeção só entra em ITP aprovado; a revisão não retira ponto com inspeção; a
reprovação abre a RNC na mesma transação (D9); a fronteira da notificação segue o parâmetro; e
o FAT de Suprimentos grava a inspeção sem ponto de ITP, identificada pelo pedido.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.qualidade import service
from src.modulos.qualidade.models import Inspection, Itp, ItpPoint, ItpRevision, Rnc
from src.modulos.qualidade.validation import (
    InspectionFilters,
    ItpApprovalInput,
    ItpFilters,
    ItpPointInput,
)
from tests.apoio_diligenciamento import montar_cenario_diligenciamento
from tests.apoio_qualidade import (
    REFERENCIA,
    Cenario,
    itp_aprovado,
    nova_inspecao,
    novo_itp,
)


def _scope(cenario: Cenario) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _inspecionar(sessao: Session, cenario: Cenario, itp_id: int, point_id: int, **campos: object):
    return service.record_inspection(
        sessao,
        user=cenario.mario,
        data=nova_inspecao(
            project_id=cenario.projeto.id,
            itp_id=itp_id,
            point_id=point_id,
            inspector_id=cenario.mario.person_id,
            **campos,
        ),
        reference_date=REFERENCIA,
    )


# ── ITP: criação, revisão e aprovação ───────────────────────────────────────────────────────


def test_o_itp_nasce_com_a_revisao_zero_e_o_codigo_do_padrao(sessao: Session, cenario: Cenario):
    criado = service.create_itp(
        sessao, user=cenario.mario, data=novo_itp(cenario), reference_date=REFERENCIA
    )

    assert criado.code == "ITP-TN-MEC-01", "o padrão do projeto e a sigla da disciplina"
    assert criado.revision == 0
    linha = service.itp_sheet(
        sessao, user=cenario.mario, code=criado.code, reference_date=REFERENCIA
    )
    assert linha is not None
    assert linha.approved_by_client is False
    assert [ponto.point_type for ponto in linha.points] == ["H", "W"]


def test_atividades_repetidas_sao_recusadas(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.create_itp(
            sessao,
            user=cenario.mario,
            data=novo_itp(
                cenario,
                points=(
                    ItpPointInput(activity="Liberação de armadura", point_type="H", criterion="ok"),
                    ItpPointInput(
                        activity="Liberação de Armadura", point_type="W", criterion="ok também"
                    ),
                ),
            ),
            reference_date=REFERENCIA,
        )

    assert "atividades repetidas" in recusa.value.messages()[0]


def test_a_aprovacao_exige_gestor_e_uma_vez_por_revisao(sessao: Session, cenario: Cenario) -> None:
    criado = service.create_itp(
        sessao, user=cenario.mario, data=novo_itp(cenario), reference_date=REFERENCIA
    )
    aprovacao = ItpApprovalInput(reference="Carta MQS-QUA-0012", approval_date=REFERENCIA)

    with pytest.raises(AccessDeniedError) as recusa:
        service.approve_itp(
            sessao, user=cenario.mario, code=criado.code, data=aprovacao, reference_date=REFERENCIA
        )
    assert "Gestor" in str(recusa.value)

    service.approve_itp(
        sessao, user=cenario.gil, code=criado.code, data=aprovacao, reference_date=REFERENCIA
    )
    with pytest.raises(InvalidDataError) as repetida:
        service.approve_itp(
            sessao, user=cenario.gil, code=criado.code, data=aprovacao, reference_date=REFERENCIA
        )
    assert "já está aprovada" in repetida.value.messages()[0]


def test_a_revisao_volta_a_pedir_a_aprovacao_e_preserva_o_ponto(
    sessao: Session, cenario: Cenario
) -> None:
    linha = itp_aprovado(sessao, cenario)
    ponto = linha.points[0]
    _inspecionar(sessao, cenario, linha.id, ponto.id)

    resultado = service.revise_itp(
        sessao,
        user=cenario.mario,
        code=linha.code,
        data=novo_itp(cenario, version=linha.version, title="Montagem de rotativos (rev B)"),
        reference_date=REFERENCIA,
    )

    assert resultado.revision == 1
    revisada = service.itp_sheet(
        sessao, user=cenario.mario, code=linha.code, reference_date=REFERENCIA
    )
    assert revisada is not None
    assert revisada.approved_by_client is False, "a revisão volta a pedir a aprovação"
    assert revisada.approval_reference is None
    assert [item.id for item in revisada.points] == [item.id for item in linha.points], (
        "o ponto preserva o id, e a inspeção continua ligada a ele"
    )
    revisoes = sessao.scalars(
        select(ItpRevision).where(ItpRevision.itp_id == linha.id).order_by(ItpRevision.revision)
    ).all()
    assert [row.revision for row in revisoes] == [0, 1]


def test_a_revisao_nao_retira_ponto_com_inspecao(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)
    inspecionado = linha.points[0]
    _inspecionar(sessao, cenario, linha.id, inspecionado.id)

    with pytest.raises(InvalidDataError) as recusa:
        service.revise_itp(
            sessao,
            user=cenario.mario,
            code=linha.code,
            data=novo_itp(
                cenario,
                version=linha.version,
                points=(
                    ItpPointInput(
                        activity="Alinhamento de acoplamentos",
                        point_type="W",
                        criterion="Desalinhamento até 0,05 mm",
                    ),
                ),
            ),
            reference_date=REFERENCIA,
        )

    assert "não podem sair do ITP" in recusa.value.messages()[0]
    assert "Nivelamento da base do moinho" in recusa.value.messages()[0]


def test_o_visualizador_nao_cria_itp_nem_inspeciona(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.create_itp(
            sessao, user=cenario.vera, data=novo_itp(cenario), reference_date=REFERENCIA
        )

    linha = itp_aprovado(sessao, cenario)
    with pytest.raises(AccessDeniedError):
        service.record_inspection(
            sessao,
            user=cenario.vera,
            data=nova_inspecao(
                project_id=cenario.projeto.id,
                itp_id=linha.id,
                point_id=linha.points[0].id,
                inspector_id=cenario.vera.person_id,
            ),
            reference_date=REFERENCIA,
        )


# ── Inspeção: ITP aprovado, resultado e notificação ─────────────────────────────────────────


def test_inspecao_em_itp_nao_aprovado_e_recusada(sessao: Session, cenario: Cenario) -> None:
    criado = service.create_itp(
        sessao, user=cenario.mario, data=novo_itp(cenario), reference_date=REFERENCIA
    )
    linha = service.itp_sheet(
        sessao, user=cenario.mario, code=criado.code, reference_date=REFERENCIA
    )
    assert linha is not None

    with pytest.raises(InvalidDataError) as recusa:
        _inspecionar(sessao, cenario, linha.id, linha.points[0].id)

    assert "ainda não tem aprovação do cliente" in recusa.value.messages()[0]
    assert sessao.scalars(select(Inspection)).all() == []


def test_a_notificacao_avisa_pela_fronteira_do_parametro(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)
    ponto_w = linha.points[1]
    assert ponto_w.point_type == "W"

    sem_notificacao = _inspecionar(sessao, cenario, linha.id, ponto_w.id)
    assert sem_notificacao.warnings == ("Ponto W sem registro da notificação ao cliente.",)

    menor = _inspecionar(
        sessao,
        cenario,
        linha.id,
        ponto_w.id,
        notification=REFERENCIA - timedelta(days=1),
    )
    assert menor.warnings == ("Notificação ao cliente com antecedência menor que 48 horas.",)

    exata = _inspecionar(
        sessao,
        cenario,
        linha.id,
        ponto_w.id,
        notification=REFERENCIA - timedelta(days=2),
    )
    assert exata.warnings == (), "exatamente o parâmetro passa"


def test_o_ponto_r_nao_guarda_notificacao(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(
        sessao,
        cenario,
        points=(
            ItpPointInput(
                activity="Registros de soldagem",
                point_type="R",
                criterion="Mapa de soldas completo",
            ),
        ),
    )
    resultado = _inspecionar(sessao, cenario, linha.id, linha.points[0].id, notification=REFERENCIA)

    assert resultado.warnings == ()
    registro = sessao.scalars(select(Inspection)).one()
    assert registro.notification is None


def test_a_notificacao_posterior_a_inspecao_e_recusada(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)
    ponto_w = linha.points[1]

    with pytest.raises(InvalidDataError) as recusa:
        _inspecionar(
            sessao,
            cenario,
            linha.id,
            ponto_w.id,
            notification=REFERENCIA + timedelta(days=1),
        )

    assert "não pode ser posterior à inspeção" in recusa.value.messages()[0]


def test_a_reprovacao_abre_a_rnc_na_mesma_transacao(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)
    ponto = linha.points[0]

    resultado = _inspecionar(
        sessao,
        cenario,
        linha.id,
        ponto.id,
        result="Reprovado",
        observation="Desvio acima do critério de aceitação.",
        severity="Maior",
        containment="Montagem suspensa até o reaperto.",
    )

    assert resultado.rnc_code is not None
    rnc = sessao.scalars(select(Rnc).where(Rnc.code == resultado.rnc_code)).one()
    assert rnc.origin == "Inspeção"
    assert rnc.origin_ref == resultado.code
    assert rnc.severity == "Maior"
    assert rnc.containment == "Montagem suspensa até o reaperto."
    assert rnc.description == (
        f"{ponto.activity} ({linha.code}): Desvio acima do critério de aceitação."
    )
    registro = sessao.scalars(select(Inspection)).one()
    assert registro.rnc_id == rnc.id


def test_a_reprovacao_exige_severidade_e_contencao(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _inspecionar(
            sessao,
            cenario,
            linha.id,
            linha.points[0].id,
            result="Reprovado",
            observation="Desvio acima do critério de aceitação.",
        )

    mensagens = " ".join(recusa.value.messages())
    assert "escolha a severidade" in mensagens
    assert "contenção imediata" in mensagens


def test_o_resumo_conta_aprovadas_ressalvas_e_reprovadas(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)
    _inspecionar(sessao, cenario, linha.id, linha.points[0].id)
    _inspecionar(
        sessao,
        cenario,
        linha.id,
        linha.points[1].id,
        result="Aprovado com ressalva",
        observation="Abatimento no limite superior em um caminhão.",
    )
    _inspecionar(
        sessao,
        cenario,
        linha.id,
        linha.points[0].id,
        result="Reprovado",
        observation="Desvio acima do critério de aceitação.",
        severity="Menor",
        containment="Frente suspensa até a correção.",
    )

    resumo = service.inspecoes_summary(
        sessao, user=cenario.mario, scope=_scope(cenario), reference_date=REFERENCIA
    )

    assert resumo.itps == 1
    assert resumo.itps_approved == 1
    assert resumo.points == 2
    assert resumo.covered_points == 2
    assert resumo.registered == 3
    assert resumo.approved == 2, "a ressalva conta como aprovada"
    assert resumo.with_remark == 1
    assert resumo.rejected == 1
    assert resumo.rejected_open_rnc == 1
    assert resumo.approval_pct is not None and str(resumo.approval_pct) == "66.7"


def test_a_lista_filtra_por_itp_resultado_tipo_e_busca(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)
    aprovada = _inspecionar(sessao, cenario, linha.id, linha.points[0].id)
    reprovada = _inspecionar(
        sessao,
        cenario,
        linha.id,
        linha.points[1].id,
        result="Reprovado",
        observation="Desvio acima do critério de aceitação.",
        severity="Maior",
        containment="Montagem suspensa até o reaperto.",
    )

    por_resultado = service.list_inspections(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=InspectionFilters(result="Reprovado"),
    )
    assert [item.code for item in por_resultado.lines] == [reprovada.code]

    por_tipo = service.list_inspections(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=InspectionFilters(point_type="W"),
    )
    assert [item.code for item in por_tipo.lines] == [reprovada.code]

    por_itp = service.list_inspections(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=InspectionFilters(itp_id=linha.id),
    )
    assert {item.code for item in por_itp.lines} == {aprovada.code, reprovada.code}

    por_busca = service.list_inspections(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=InspectionFilters(search=aprovada.code),
    )
    assert [item.code for item in por_busca.lines] == [aprovada.code]


def test_a_lista_de_itps_filtra_por_disciplina_e_busca(sessao: Session, cenario: Cenario) -> None:
    criado = service.create_itp(
        sessao, user=cenario.mario, data=novo_itp(cenario), reference_date=REFERENCIA
    )

    por_disciplina = service.list_itps(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=ItpFilters(discipline="Mecânica"),
        reference_date=REFERENCIA,
    )
    assert [item.code for item in por_disciplina.lines] == [criado.code]

    vazia = service.list_itps(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=ItpFilters(discipline="Civil"),
        reference_date=REFERENCIA,
    )
    assert vazia.total == 0

    por_busca = service.list_itps(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=ItpFilters(search="rotativos"),
        reference_date=REFERENCIA,
    )
    assert [item.code for item in por_busca.lines] == [criado.code]


# ── O FAT de Suprimentos (D9) ───────────────────────────────────────────────────────────────


@pytest.fixture
def pedido(sessao: Session):
    """O pedido do diligenciamento: o FAT aponta para a tabela pedido (FK real, D5)."""
    return montar_cenario_diligenciamento(sessao).pedido


def _fat(sessao: Session, cenario: Cenario, pedido, **campos: object):
    base: dict[str, object] = {
        "user": cenario.mario,
        "project_id": cenario.projeto.id,
        "order_id": pedido.id,
        "order_number": pedido.number,
        "supplier_company_id": cenario.empresa.id,
        "result": "Aprovado",
        "inspected_on": REFERENCIA,
        "inspector_id": cenario.mario.person_id,
        "reference_date": REFERENCIA,
    }
    base.update(campos)
    return service.record_fat_inspection(sessao, **base)  # type: ignore[arg-type]


def test_o_fat_grava_a_inspecao_sem_ponto_e_com_o_pedido(
    sessao: Session, cenario: Cenario, pedido
) -> None:
    resultado = _fat(sessao, cenario, pedido)

    registro = sessao.scalars(select(Inspection)).one()
    assert registro.itp_point_id is None
    assert registro.order_id == pedido.id
    assert registro.point == "Inspeção em fábrica (FAT) PED-2026-0001"
    assert registro.point_type == "H"
    assert registro.company_id == cenario.empresa.id

    listagem = service.list_inspections(
        sessao, user=cenario.mario, scope=_scope(cenario), filters=InspectionFilters()
    )
    assert [item.code for item in listagem.lines] == [resultado.code]
    linha = listagem.lines[0]
    assert linha.itp_id is None
    assert linha.itp_title == "Inspeção em fábrica (04)"
    assert linha.order_number == "PED-2026-0001"
    assert linha.result == "Aprovado"


def test_o_fat_recusa_resultado_fora_do_rol_e_data_futura(
    sessao: Session, cenario: Cenario, pedido
) -> None:
    with pytest.raises(InvalidDataError) as resultado:
        _fat(sessao, cenario, pedido, result="")

    assert "Informe o resultado da inspeção em fábrica." in resultado.value.messages()

    with pytest.raises(InvalidDataError) as futura:
        _fat(sessao, cenario, pedido, inspected_on=REFERENCIA + timedelta(days=1))

    assert "posterior à referência" in futura.value.messages()[0]
    assert sessao.scalars(select(Inspection)).all() == []


def test_o_fat_sem_inspetor_usa_quem_gravou(sessao: Session, cenario: Cenario, pedido) -> None:
    _fat(sessao, cenario, pedido, inspector_id=None)

    registro = sessao.scalars(select(Inspection)).one()
    assert registro.inspector_id == cenario.mario.person_id


def test_a_inspecao_do_fat_aparece_com_o_numero_do_pedido(
    sessao: Session, cenario: Cenario, pedido
) -> None:
    """O teste do critério: a inspeção do FAT na lista, com o número do pedido no ponto."""
    _fat(sessao, cenario, pedido, order_number="PED-2026-0004", result="Reprovado")

    listagem = service.list_inspections(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario),
        filters=InspectionFilters(search="PED-2026-0004"),
    )
    assert len(listagem.lines) == 1
    assert listagem.lines[0].point.endswith("PED-2026-0004")
    assert listagem.lines[0].result == "Reprovado"


def test_o_escopo_nao_alcanca_a_inspecao_do_outro_projeto(
    sessao: Session, cenario: Cenario, pedido
) -> None:
    fat = _fat(sessao, cenario, pedido, project_id=cenario.outro.id)

    listagem = service.list_inspections(
        sessao, user=cenario.mario, scope=_scope(cenario), filters=InspectionFilters()
    )
    assert fat.code not in {item.code for item in listagem.lines}


def test_o_modelo_de_itp_tem_uma_revisao_vigente(sessao: Session, cenario: Cenario) -> None:
    linha = itp_aprovado(sessao, cenario)

    itp = sessao.scalars(select(Itp).where(Itp.code == linha.code)).one()
    revisoes = sessao.scalars(select(ItpRevision).where(ItpRevision.itp_id == itp.id)).all()
    pontos = sessao.scalars(select(ItpPoint).where(ItpPoint.revision_id == revisoes[0].id)).all()
    assert len(revisoes) == 1
    assert len(pontos) == 2
