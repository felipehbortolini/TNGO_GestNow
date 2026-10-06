"""Fachada de mudanças (ISSUE-023): numeração, situação inicial, cancelamento, lista e KPIs."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.governanca import models, service
from tests.governanca import apoio
from tests.governanca.apoio import HOJE


def _cenario(session: Session):
    projeto = apoio.projeto_com_orcamento(session)
    membro = apoio.colaborador(session, apoio.MEMBRO)
    return projeto, membro, apoio.usuario_de(membro)


def _visao(session: Session, usuario, escopo: Scope, **filtros: str) -> service.RegisterOverview:
    return service.register_overview(
        session,
        user=usuario,
        scope=escopo,
        filters=service.ChangeFilter(**filtros),
        reference_date=HOJE,
    )


def test_nova_solicitacao_recebe_o_numero_do_projeto_e_nasce_registrada(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    primeira = apoio.registrar(sessao, usuario, projeto)
    segunda = apoio.registrar(sessao, usuario, projeto, titulo="Outra solicitação de escopo")
    assert primeira.code == "SM-TN-2026-0001"
    assert segunda.code == "SM-TN-2026-0002"
    ficha = service.find_change_sheet(sessao, user=usuario, code=primeira.code, reference_date=HOJE)
    assert ficha is not None
    assert ficha.change.situation == models.SITUATION_REGISTERED
    assert ficha.change.project_id == projeto.id
    assert ficha.stage == 0


def test_a_sequencia_e_por_projeto(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    outro = apoio.projeto_com_orcamento(sessao, codigo="TN-2026-015", padrao="TN-2026-B")
    apoio.registrar(sessao, usuario, projeto)
    assert apoio.registrar(sessao, usuario, outro).code == "SM-TN-2026-B-0001"


def test_emergencial_com_execucao_antecipada_guarda_inicio_e_justificativa(
    sessao: Session,
) -> None:
    projeto, _, usuario = _cenario(sessao)
    criada = apoio.registrar(
        sessao,
        usuario,
        projeto,
        prioridade="Emergencial",
        execucao_antecipada="sim",
        inicio_emergencia=HOJE.isoformat(),
        justificativa_emergencia="Risco de parada da frente de obra.",
    )
    ficha = service.find_change_sheet(sessao, user=usuario, code=criada.code, reference_date=HOJE)
    assert ficha is not None
    assert ficha.change.emergency
    assert ficha.change.implementation_start == HOJE
    assert ficha.row.emergency_pending


def test_campo_obrigatorio_faltando_e_422_e_nao_consome_numero(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    with pytest.raises(InvalidDataError):
        apoio.registrar(sessao, usuario, projeto, titulo="")
    assert apoio.registrar(sessao, usuario, projeto).code == "SM-TN-2026-0001"


def test_no_portfolio_a_solicitacao_pede_projeto(sessao: Session) -> None:
    _, _, usuario = _cenario(sessao)
    with pytest.raises(InvalidDataError):
        service.create_change(
            sessao,
            user=usuario,
            scope=apoio.PORTFOLIO,
            form=apoio.solicitacao_valida(),
            reference_date=HOJE,
        )


def test_visualizador_nao_registra(sessao: Session) -> None:
    projeto, _, _ = _cenario(sessao)
    visualizador = apoio.usuario_de(
        apoio.colaborador(sessao, apoio.VISUALIZADOR, perfil="Visualizador")
    )
    with pytest.raises(AccessDeniedError):
        apoio.registrar(sessao, visualizador, projeto)


def _cancelar(sessao: Session, usuario, codigo: str, versao: int = 1, texto: str = "x" * 12):
    return service.cancel_change(
        sessao,
        user=usuario,
        code=codigo,
        form={"justificativa": texto, "versao": str(versao)},
        reference_date=HOJE,
    )


def test_solicitante_cancela_antes_da_decisao(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    codigo = apoio.registrar(sessao, usuario, projeto).code
    cancelada = _cancelar(sessao, usuario, codigo)
    assert cancelada.situation == models.SITUATION_CANCELLED
    assert cancelada.closing_date == HOJE
    assert cancelada.closing_note == "x" * 12


def test_gestor_cancela_solicitacao_de_outra_pessoa(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    gestor = apoio.usuario_de(apoio.colaborador(sessao, apoio.GESTOR, perfil="Gestor"))
    codigo = apoio.registrar(sessao, usuario, projeto).code
    assert _cancelar(sessao, gestor, codigo).situation == models.SITUATION_CANCELLED


def test_outro_membro_nao_cancela(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    outro = apoio.usuario_de(apoio.colaborador(sessao, apoio.OUTRO_MEMBRO))
    codigo = apoio.registrar(sessao, usuario, projeto).code
    with pytest.raises(AccessDeniedError):
        _cancelar(sessao, outro, codigo)


def test_cancelamento_pede_justificativa(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    codigo = apoio.registrar(sessao, usuario, projeto).code
    with pytest.raises(InvalidDataError):
        _cancelar(sessao, usuario, codigo, texto="curta")


@pytest.mark.parametrize(
    "situacao",
    [
        models.SITUATION_APPROVED,
        models.SITUATION_APPROVED_WITH_CONDITIONS,
        models.SITUATION_IMPLEMENTING,
        models.SITUATION_REJECTED,
        models.SITUATION_CLOSED,
        models.SITUATION_CANCELLED,
    ],
)
def test_depois_da_decisao_nao_se_cancela(sessao: Session, situacao: str) -> None:
    projeto, membro, usuario = _cenario(sessao)
    service.load_demonstration_change(
        sessao,
        author_id=membro.id,
        seed=apoio.semente(projeto, membro.person_id, "SM-TN-2026-0001", situacao),
        reference_date=HOJE,
    )
    with pytest.raises(InvalidDataError) as erro:
        _cancelar(sessao, usuario, "SM-TN-2026-0001")
    if situacao in {models.SITUATION_APPROVED, models.SITUATION_IMPLEMENTING}:
        assert "registre nova SM" in str(erro.value.detail)


@pytest.mark.parametrize("situacao", apoio.SITUACOES_ABERTAS_ANTES_DA_DECISAO)
def test_antes_da_decisao_se_cancela(sessao: Session, situacao: str) -> None:
    projeto, membro, usuario = _cenario(sessao)
    service.load_demonstration_change(
        sessao,
        author_id=membro.id,
        seed=apoio.semente(projeto, membro.person_id, "SM-TN-2026-0001", situacao),
        reference_date=HOJE,
    )
    assert _cancelar(sessao, usuario, "SM-TN-2026-0001").situation == models.SITUATION_CANCELLED


def test_codigo_desconhecido_na_ficha_e_nulo_e_no_cancelamento_e_422(sessao: Session) -> None:
    _, _, usuario = _cenario(sessao)
    assert service.find_change_sheet(sessao, user=usuario, code="SM-X", reference_date=HOJE) is None
    with pytest.raises(InvalidDataError):
        _cancelar(sessao, usuario, "SM-X")


def test_lista_filtra_por_situacao_e_conta_o_escopo(sessao: Session) -> None:
    projeto, membro, usuario = _cenario(sessao)
    situacoes = [
        models.SITUATION_REGISTERED,
        models.SITUATION_ANALYSIS,
        models.SITUATION_AWAITING,
        models.SITUATION_APPROVED,
        models.SITUATION_REJECTED,
    ]
    for indice, situacao in enumerate(situacoes, start=1):
        service.load_demonstration_change(
            sessao,
            author_id=membro.id,
            seed=apoio.semente(projeto, membro.person_id, f"SM-TN-2026-{indice:04d}", situacao),
            reference_date=HOJE,
        )
    escopo = apoio.escopo_do_projeto(projeto)
    visao = _visao(sessao, usuario, escopo)
    assert visao.total_in_scope == 5
    assert len(visao.rows) == 5
    assert visao.summary.in_analysis == 2
    assert visao.summary.awaiting_committee == 1
    assert visao.summary.approved == 1
    so_aprovadas = _visao(sessao, usuario, escopo, situation=service.SITUATION_GROUP_APPROVED)
    assert [linha.situation for linha in so_aprovadas.rows] == [models.SITUATION_APPROVED]
    assert so_aprovadas.total_in_scope == 5
    assert _visao(sessao, usuario, escopo, search="nada-assim").rows == ()


def test_portfolio_enxerga_os_projetos_e_o_projeto_so_o_seu(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    outro = apoio.projeto_com_orcamento(sessao, codigo="TN-2026-015", padrao="TN-2026-B")
    apoio.registrar(sessao, usuario, projeto)
    apoio.registrar(sessao, usuario, outro)
    assert _visao(sessao, usuario, apoio.PORTFOLIO).total_in_scope == 2
    assert _visao(sessao, usuario, apoio.escopo_do_projeto(outro)).total_in_scope == 1


def test_numero_da_demonstracao_fora_da_sequencia_e_recusado(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    with pytest.raises(service.DemonstrationNumberError):
        service.load_demonstration_change(
            sessao,
            author_id=membro.id,
            seed=apoio.semente(
                projeto, membro.person_id, "SM-TN-2026-0007", models.SITUATION_REGISTERED
            ),
            reference_date=date(2026, 10, 6),
        )
