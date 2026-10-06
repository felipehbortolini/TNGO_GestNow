"""Fachada do Registro de riscos (ISSUE-064, D5, D6): numeração, avaliação, exclusão e restauração.

O score, a severidade e o VME nascem no servidor; a numeração reserva o próximo sufixo numérico
do projeto; a exclusão lógica é do Gestor, bloqueada com ação aberta e para risco encerrado, e só
o Admin vê e restaura o excluído.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import NumberingSequence
from src.core.rbac import GeneralProfile
from src.modulos.central_acoes import service as central_acoes
from src.modulos.central_acoes.calculations import ACTION
from src.modulos.central_acoes.validation import NewAction
from src.modulos.riscos import service
from src.modulos.riscos.models import Risk
from src.modulos.riscos.validation import DeletionInput
from tests.apoio_riscos import REFERENCIA, Cenario, nova_avaliacao, novo_risco


def _criar(sessao: Session, cenario: Cenario, **campos: object) -> str:
    resultado = service.save_risk(
        sessao, user=cenario.mario, data=novo_risco(cenario, **campos), reference_date=REFERENCIA
    )
    return resultado.code


def _avaliar(sessao: Session, cenario: Cenario, codigo: str, **campos: object):
    return service.assess_risk(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=nova_avaliacao(**campos),
        reference_date=REFERENCIA,
    )


# ── Numeração ────────────────────────────────────────────────────────────────


def test_o_codigo_continua_a_serie_do_projeto(sessao: Session, cenario: Cenario) -> None:
    assert _criar(sessao, cenario) == "RSK-0001"
    assert _criar(sessao, cenario) == "RSK-0002"


def test_a_numeracao_ignora_sufixos_nao_numericos(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario)
    sequencia = sessao.scalars(
        select(NumberingSequence).where(
            NumberingSequence.project_id == cenario.projeto.id,
            NumberingSequence.kind == "risco",
        )
    ).one()
    sequencia.next_value = 1  # a sequência volta, como se o risco tivesse vindo de uma importação
    sessao.add(
        Risk(
            project_id=cenario.projeto.id,
            category_id=cenario.categorias[0].id,
            owner_id=cenario.mario.person_id,
            identified_by_id=cenario.mario.person_id,
            code="RSK-0041",
            title="Risco importado",
            nature="Ameaça",
            origin_type="Manual",
            cause="Causa importada",
            consequence="Consequência importada",
            situation="Identificado",
            identified_on=REFERENCIA,
        )
    )
    sessao.add(
        Risk(
            project_id=cenario.projeto.id,
            category_id=cenario.categorias[0].id,
            owner_id=cenario.mario.person_id,
            identified_by_id=cenario.mario.person_id,
            code="RSK-SE-0099",  # sufixo não numérico: não move a série
            title="Risco de sistema",
            nature="Ameaça",
            origin_type="Sistema",
            cause="Causa de sistema",
            consequence="Consequência de sistema",
            situation="Identificado",
            identified_on=REFERENCIA,
        )
    )
    sessao.flush()

    assert _criar(sessao, cenario) == "RSK-0042"


# ── Avaliação ────────────────────────────────────────────────────────────────


def test_avaliacao_calcula_o_score_e_a_severidade_no_servidor(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)

    resultado = _avaliar(sessao, cenario, codigo)

    assert resultado.score == 12
    assert resultado.severity.id == "alto"
    assert resultado.situation == "Em análise"
    assert not resultado.requires_plan
    assert not resultado.manager_alert


def test_avaliacao_na_faixa_mais_alta_avisa_o_gestor_e_exige_plano(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)

    resultado = _avaliar(sessao, cenario, codigo, probability=4, impact=4)

    assert resultado.score == 16
    assert resultado.severity.id == "critico"
    assert resultado.requires_plan
    assert resultado.manager_alert


def test_avaliacao_residual_exige_o_plano_de_resposta(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _avaliar(sessao, cenario, codigo, kind="residual")

    assert "plano de resposta" in str(recusa.value)


def test_score_novo_exige_justificativa(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo)

    with pytest.raises(InvalidDataError) as recusa:
        _avaliar(sessao, cenario, codigo, probability=4, impact=4)

    assert "Justifique" in str(recusa.value)

    resultado = _avaliar(
        sessao, cenario, codigo, probability=4, impact=4, justification="Elevada após a revisão."
    )
    assert resultado.score == 16


def test_impacto_menor_que_a_maior_dimensao_e_recusado(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _avaliar(sessao, cenario, codigo, impact=2)

    assert "maior dimensão" in str(recusa.value)


def test_residual_acima_do_inerente_e_recusado_para_ameaca(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _criar(sessao, cenario)
    _avaliar(sessao, cenario, codigo, probability=3, impact=3, dimensions={"prazo": 3})
    risco = sessao.scalars(select(Risk).where(Risk.code == codigo)).one()
    risco.strategy, risco.plan = "Mitigar", "Plano de resposta aprovado."
    sessao.flush()

    with pytest.raises(InvalidDataError) as recusa:
        _avaliar(
            sessao,
            cenario,
            codigo,
            kind="residual",
            probability=4,
            impact=4,
            dimensions={"prazo": 4},
            justification="Residual estimado após o plano.",
        )

    assert "residual não pode superar" in str(recusa.value)


# ── Exclusão e restauração ───────────────────────────────────────────────────


def _excluir(
    sessao: Session,
    cenario: Cenario,
    codigo: str,
    *,
    usuario=None,
    motivo: str = "Criado por engano",
):
    linha = service.find_risk(
        sessao, user=usuario or cenario.gil, code=codigo, reference_date=REFERENCIA
    )
    assert linha is not None
    return service.delete_risk(
        sessao,
        user=usuario or cenario.gil,
        code=codigo,
        data=DeletionInput(reason=motivo, note="", version=linha.version),
        reference_date=REFERENCIA,
    )


def test_exclusao_com_acao_aberta_e_recusada(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    central_acoes.create_action(
        sessao,
        user=cenario.gil,
        new=NewAction(
            project_id=cenario.projeto.id,
            origin="Risco",
            origin_ref=codigo,
            subject="Tratar o risco",
            requester_id=cenario.mario.person_id,
            responsible_id=cenario.mario.person_id,
            planned_date=REFERENCIA + timedelta(days=10),
            kind=ACTION,
            description="Ação vinculada ao risco.",
            group="Plano de resposta",
        ),
        reference_date=REFERENCIA,
    )

    with pytest.raises(InvalidDataError) as recusa:
        _excluir(sessao, cenario, codigo)

    assert "ação em aberto" in str(recusa.value)


def test_exclusao_de_risco_encerrado_e_recusada(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)
    risco = sessao.scalars(select(Risk).where(Risk.code == codigo)).one()
    risco.situation = "Encerrado"
    sessao.flush()

    with pytest.raises(InvalidDataError) as recusa:
        _excluir(sessao, cenario, codigo)

    assert "já saiu da carteira ativa" in str(recusa.value)


def test_exclusao_exige_gestor(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)

    with pytest.raises(AccessDeniedError):
        _excluir(sessao, cenario, codigo, usuario=cenario.mario)

    assert cenario.mario.general_profile is GeneralProfile.MEMBER


def test_excluido_so_o_admin_ve_e_restaura(sessao: Session, cenario: Cenario) -> None:
    codigo = _criar(sessao, cenario)

    _excluir(sessao, cenario, codigo)

    assert (
        service.find_risk(sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA) is None
    )
    assert (
        service.find_risk(sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA)
        is None
    )
    do_admin = service.find_risk(sessao, user=cenario.ada, code=codigo, reference_date=REFERENCIA)
    assert do_admin is not None and do_admin.hidden
    assert do_admin.deletion_reason == "Criado por engano"

    with pytest.raises(AccessDeniedError):
        service.restore_risk(sessao, user=cenario.gil, code=codigo)

    service.restore_risk(sessao, user=cenario.ada, code=codigo)
    assert service.find_risk(sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA)
