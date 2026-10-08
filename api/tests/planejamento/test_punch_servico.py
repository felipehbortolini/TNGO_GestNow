"""Fachada da Punch list (ISSUE-049): fluxo, segregação, evidência, bloqueio e sincronização.

A data de referência é injetada (25/09/2026) e o cenário mínimo vem de ``apoio_punch``; a
ação da Central é lida pela tabela ``acao``, no teste, para provar a costura (D9).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import origin_links
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.central_acoes import origins
from src.modulos.central_acoes.models import Action
from src.modulos.central_acoes.origins import ActionEvent
from src.modulos.configuracoes.models import System
from src.modulos.planejamento import calculations, service, validation
from src.modulos.planejamento.models import PunchItem
from tests.apoio_punch import (
    HOJE,
    Cenario,
    enviar_anexo,
    form_cancelamento,
    form_item,
    form_verificacao,
    montar_cenario,
)
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.identidades import criar_projeto

RAIZ = "PL-TN-2026-0001"


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    return montar_cenario(sessao)


@pytest.fixture
def armazenamento() -> ArmazenamentoEmMemoria:
    return ArmazenamentoEmMemoria()


def _criar(cenario: Cenario, sessao: Session, **overrides: object) -> PunchItem:
    return service.create_punch_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        form=form_item(cenario, **overrides),
        reference_date=HOJE,
    )


def _ate_a_verificacao(cenario: Cenario, sessao: Session, **overrides: object) -> PunchItem:
    item = _criar(cenario, sessao, **overrides)
    service.treat_punch_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )
    return service.send_punch_item_to_verification(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )


def _acao(sessao: Session) -> Action:
    return sessao.scalars(select(Action).where(Action.origin == "Punch list")).one()


def test_a_inclusao_numera_e_abre_a_acao_na_central(cenario: Cenario, sessao: Session) -> None:
    item = _criar(cenario, sessao)

    assert item.code == RAIZ
    assert (item.situation, item.opened_on, item.due_date) == (
        validation.PUNCH_OPEN,
        HOJE,
        timedelta(days=15) + HOJE,
    )
    acao = _acao(sessao)
    assert (acao.origin, acao.origin_ref) == ("Punch list", RAIZ)
    assert acao.subject == item.description
    assert acao.responsible_id == cenario.executante.person_id
    assert acao.planned_date == item.due_date
    assert acao.group == "310 Flotação"
    assert acao.completed_on is None


def test_o_visualizador_le_mas_nao_grava(cenario: Cenario, sessao: Session) -> None:
    _criar(cenario, sessao)
    visao = service.punch_overview(
        sessao,
        user=cenario.usuario_visualizador,
        scope=cenario.escopo,
        punch_filter=service.PunchFilter(),
        reference_date=HOJE,
    )

    assert len(visao.rows) == 1
    with pytest.raises(AccessDeniedError):
        service.create_punch_item(
            sessao,
            user=cenario.usuario_visualizador,
            scope=cenario.escopo,
            form=form_item(cenario),
            reference_date=HOJE,
        )


def test_a_edicao_do_prazo_espelha_a_acao(cenario: Cenario, sessao: Session) -> None:
    item = _criar(cenario, sessao)

    service.update_punch_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        form=form_item(cenario, prazo="2026-11-20", descricao="Descrição revisada do item."),
        version=str(item.version),
        reference_date=HOJE,
    )

    acao = _acao(sessao)
    assert acao.planned_date.isoformat() == "2026-11-20"
    assert acao.subject == "Descrição revisada do item."


def test_o_fluxo_trata_envia_e_reprova_de_volta(cenario: Cenario, sessao: Session) -> None:
    item = _ate_a_verificacao(cenario, sessao)

    assert item.situation == validation.PUNCH_VERIFYING
    reprovado = service.verify_punch_item(
        sessao,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        item_id=item.id,
        form=form_verificacao(
            cenario,
            resultado=validation.PUNCH_RESULT_REJECTED,
            comentario="Falta o teste de estanqueidade.",
        ),
        version=str(item.version),
        reference_date=HOJE,
    )

    assert reprovado.situation == validation.PUNCH_TREATMENT
    assert _acao(sessao).completed_on is None


def test_o_fechamento_sem_anexo_e_recusado(cenario: Cenario, sessao: Session) -> None:
    item = _ate_a_verificacao(cenario, sessao)

    with pytest.raises(InvalidDataError) as recusa:
        service.verify_punch_item(
            sessao,
            user=cenario.usuario_gestor,
            scope=cenario.escopo,
            item_id=item.id,
            form=form_verificacao(cenario),
            version=str(item.version),
            reference_date=HOJE,
        )

    assert service.PUNCH_EVIDENCE_MESSAGE in str(recusa.value)
    assert item.situation == validation.PUNCH_VERIFYING
    assert _acao(sessao).completed_on is None


def test_o_fechamento_com_evidencia_fecha_e_conclui_a_acao(
    cenario: Cenario, sessao: Session, armazenamento: ArmazenamentoEmMemoria
) -> None:
    item = _ate_a_verificacao(cenario, sessao)
    enviar_anexo(
        sessao,
        user=cenario.usuario_membro,
        item_id=item.id,
        armazenamento=armazenamento,
    )

    fechado = service.verify_punch_item(
        sessao,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        item_id=item.id,
        form=form_verificacao(cenario, comentario="Conferido em campo."),
        version=str(item.version),
        reference_date=HOJE,
    )

    assert fechado.situation == validation.PUNCH_CLOSED
    assert fechado.closed_on == HOJE
    assert fechado.verified_by_id == cenario.gestor.person_id
    acao = _acao(sessao)
    assert acao.completed_on == HOJE
    assert acao.replanned_date is None


def test_o_verificador_igual_ao_executante_recebe_403(cenario: Cenario, sessao: Session) -> None:
    item = _ate_a_verificacao(cenario, sessao)

    with pytest.raises(AccessDeniedError):
        service.verify_punch_item(
            sessao,
            user=cenario.usuario_membro,
            scope=cenario.escopo,
            item_id=item.id,
            form=form_verificacao(cenario, verificador=cenario.executante.person_id),
            version=str(item.version),
            reference_date=HOJE,
        )

    assert item.situation == validation.PUNCH_VERIFYING


@pytest.mark.parametrize("justificativa", ["", "curta"])
def test_o_cancelamento_exige_justificativa(
    cenario: Cenario, sessao: Session, justificativa: str
) -> None:
    item = _criar(cenario, sessao)

    with pytest.raises(InvalidDataError):
        service.cancel_punch_item(
            sessao,
            user=cenario.usuario_membro,
            scope=cenario.escopo,
            item_id=item.id,
            form=form_cancelamento(justificativa),
            version=str(item.version),
            reference_date=HOJE,
        )

    assert item.situation == validation.PUNCH_OPEN


def test_o_cancelamento_encerra_a_acao(cenario: Cenario, sessao: Session) -> None:
    item = _criar(cenario, sessao)

    cancelado = service.cancel_punch_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        form=form_cancelamento(),
        version=str(item.version),
        reference_date=HOJE,
    )

    assert cancelado.situation == validation.PUNCH_CANCELLED
    assert _acao(sessao).completed_on == HOJE


def test_o_item_a_aberto_bloqueia_o_sistema_para_o_marco(cenario: Cenario, sessao: Session) -> None:
    _criar(
        cenario,
        sessao,
        categoria="A",
        marco="Completação mecânica",
        tag="310-P-031",
    )
    _criar(cenario, sessao, categoria="B", marco="Partida", tag="310-P-032")

    visao = service.punch_overview(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        punch_filter=service.PunchFilter(),
        reference_date=HOJE,
    )

    assert [bloco.code for bloco in visao.blocked_for("Completação mecânica")] == ["310"]
    assert visao.blocked_for("Pré-comissionamento")[0].blocks["Pré-comissionamento"] == 1
    assert visao.blocked_for("Aceite provisório")[0].blocks["Aceite provisório"] == 1
    # A categoria B não bloqueia nenhum marco pelo item, e o aceite definitivo é bloqueado
    # por qualquer item aberto, como o protótipo mostra.
    assert visao.blocks[0].blocks["Pré-comissionamento"] == 1
    assert visao.blocks[0].blocks["Aceite definitivo"] == 2

    states = (
        calculations.PunchState(
            situation=validation.PUNCH_OPEN,
            category="A",
            milestone="Partida",
            system_id=cenario.sistema.id,
            due_date=HOJE,
        ),
        calculations.PunchState(
            situation=validation.PUNCH_CLOSED,
            category="A",
            milestone="Completação mecânica",
            system_id=cenario.sistema.id,
            due_date=HOJE,
        ),
    )
    assert (
        calculations.punch_system_block_count(
            states, system_id=cenario.sistema.id, milestone="Comissionamento"
        )
        == 0
    )


def test_a_sincronizacao_com_a_central_vai_e_volta(cenario: Cenario, sessao: Session) -> None:
    item = _criar(cenario, sessao)
    acao = _acao(sessao)
    assert origins.reaction_for("Punch list") is service.react_to_punch_action

    # Ação para o item: a conclusão da ação na Central fecha o item.
    acao.completed_on = HOJE
    sessao.flush()
    origins.react(sessao, cenario.usuario_membro, acao, ActionEvent.COMPLETED)
    assert item.situation == validation.PUNCH_CLOSED
    assert item.closed_on == HOJE

    # Ação para o item: o replanejamento da ação move o prazo do item aberto.
    segundo = _criar(cenario, sessao, tag="310-P-033")
    acao_segundo = sessao.scalars(select(Action).where(Action.origin_ref == segundo.code)).one()
    acao_segundo.replanned_date = HOJE + timedelta(days=30)
    sessao.flush()
    origins.react(sessao, cenario.usuario_membro, acao_segundo, ActionEvent.REPLANNED)
    assert segundo.due_date == HOJE + timedelta(days=30)

    # Item para a ação: fechar o item conclui a ação.
    terceiro = _ate_a_verificacao(cenario, sessao, tag="310-P-034")
    enviar_anexo(
        sessao,
        user=cenario.usuario_membro,
        item_id=terceiro.id,
        armazenamento=ArmazenamentoEmMemoria(),
    )
    service.verify_punch_item(
        sessao,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        item_id=terceiro.id,
        form=form_verificacao(cenario),
        version=str(terceiro.version),
        reference_date=HOJE,
    )
    acao_terceiro = sessao.scalars(select(Action).where(Action.origin_ref == terceiro.code)).one()
    assert acao_terceiro.completed_on == HOJE


def test_o_link_da_acao_volta_para_a_lista_com_a_busca(cenario: Cenario, sessao: Session) -> None:
    item = _criar(cenario, sessao)

    link = origin_links.resolve("Punch list", item.code)

    assert link.has_link
    assert link.url is not None
    assert "/planejamento/punch-list" in link.url
    assert f"busca={item.code}" in link.url


def test_o_portfolio_traz_uma_linha_por_projeto(cenario: Cenario, sessao: Session) -> None:
    outro = criar_projeto(sessao, codigo="TN-PUNCH-002", nome="Fábrica 2")
    outro.punch_pattern = "PL-CB-2026"
    sessao.add(System(project_id=outro.id, code="610", name="Caldeira", area="Vapor"))
    sessao.flush()
    _criar(cenario, sessao)
    outro_sistema = sessao.scalars(select(System.id).where(System.project_id == outro.id)).one()
    service.create_punch_item(
        sessao,
        user=cenario.usuario_membro,
        scope=Scope(project_id=outro.id, source="url"),
        form=form_item(cenario, sistema=str(outro_sistema)),
        reference_date=HOJE,
    )

    carteira = service.punch_overview(
        sessao,
        user=cenario.usuario_membro,
        scope=Scope(project_id=None, source="padrao"),
        punch_filter=service.PunchFilter(),
        reference_date=HOJE,
    )

    assert carteira.is_portfolio
    assert [item.code for item in carteira.rows] == ["PL-CB-2026-0001", RAIZ]
    assert [item.project_code for item in carteira.rows] == ["TN-PUNCH-002", "TN-PUNCH-001"]
    assert sessao.scalar(select(func.count()).select_from(Action)) == 2


def test_o_filtro_de_categoria_e_busca_recorta_a_lista(cenario: Cenario, sessao: Session) -> None:
    _criar(cenario, sessao, categoria="A", tag="310-P-040", descricao="Aterramento incompleto.")
    _criar(cenario, sessao, categoria="B", tag="310-P-041", descricao="Pintura de acabamento.")

    por_categoria = service.punch_overview(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        punch_filter=service.PunchFilter(category="A"),
        reference_date=HOJE,
    )
    por_busca = service.punch_overview(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        punch_filter=service.PunchFilter(search="pintura"),
        reference_date=HOJE,
    )

    assert [item.tag for item in por_categoria.rows] == ["310-P-040"]
    assert [item.tag for item in por_busca.rows] == ["310-P-041"]
    assert por_categoria.kpis.opened == 2, "os indicadores são do conjunto, não do filtro"
