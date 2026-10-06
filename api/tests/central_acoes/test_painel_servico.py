"""A fachada do painel e do follow-up (ISSUE-020, D12): contagem igual à da lista e um aviso por responsável."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import config, notification
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import Notification
from src.core.scope import Scope
from src.modulos.central_acoes import panel_service, service
from src.modulos.central_acoes.calculations import StatusFilter
from src.modulos.central_acoes.panel_service import FollowUpRequest
from src.modulos.central_acoes.validation import ActionFilters
from tests.apoio_acoes import REFERENCIA, Cenario, nova_acao

PORTFOLIO = Scope(project_id=None, source="padrao")


def _criar(session: Session, cenario: Cenario, **campos: object) -> None:
    service.create_action(
        session, user=cenario.gil, new=nova_acao(cenario, **campos), reference_date=REFERENCIA
    )


def _massa(session: Session, cenario: Cenario) -> None:
    atrasada = REFERENCIA - timedelta(days=4)
    _criar(session, cenario, origin_ref="RSK-1", subject="Do Gil, no prazo")
    _criar(session, cenario, origin_ref="RSK-2", subject="Do Gil, atrasada", planned_date=atrasada)
    _criar(
        session,
        cenario,
        origin="Ata",
        origin_ref="TN-2026-0001",
        subject="Do Mário",
        responsible_id=cenario.mario.person_id,
        project_id=cenario.projeto_b.id,
    )


def _pedido(**campos: object) -> FollowUpRequest:
    base = {
        "scope": PORTFOLIO,
        "filters": ActionFilters(),
        "reference_date": REFERENCIA,
    }
    return FollowUpRequest(**{**base, **campos})  # type: ignore[arg-type]


def test_contagens_do_painel_batem_com_as_da_lista_no_mesmo_escopo(
    sessao: Session, cenario: Cenario
) -> None:
    _massa(sessao, cenario)

    painel = panel_service.dashboard(
        sessao, user=cenario.gil, scope=PORTFOLIO, origin="", reference_date=REFERENCIA
    )
    lista = service.list_actions(
        sessao,
        user=cenario.gil,
        scope=PORTFOLIO,
        filters=ActionFilters(status=StatusFilter.ALL),
        reference_date=REFERENCIA,
    )

    assert painel.counts == lista.counts
    assert painel.counts.total == 3
    assert painel.counts.overdue == 1
    assert sum(line.tally.total for line in painel.origins) == painel.counts.total
    assert sum(line.tally.total for line in painel.responsibles) == painel.counts.total
    assert sum(line.tally.total for line in painel.projects) == painel.counts.total


def test_painel_de_um_projeto_nao_traz_a_quebra_por_projeto_e_respeita_a_origem(
    sessao: Session, cenario: Cenario
) -> None:
    _massa(sessao, cenario)

    painel = panel_service.dashboard(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=cenario.projeto_a.id, source="padrao"),
        origin="Risco",
        reference_date=REFERENCIA,
    )

    assert painel.projects == ()
    assert painel.counts.total == 2
    assert [line.origin for line in painel.origins] == ["Risco"]


def test_follow_up_agrupa_por_responsavel_e_so_leva_as_abertas(
    sessao: Session, cenario: Cenario
) -> None:
    _massa(sessao, cenario)

    plano = panel_service.plan_follow_up(sessao, user=cenario.gil, request=_pedido())

    assert [len(e.group.actions) for e in plano.entries] == [2, 1]
    assert plano.entries[0].name == "Gil Gestor"
    assert plano.action_count == 3
    assert "ATRASADA há 4 dias" in plano.entries[0].body
    assert "2 ações, 1 atrasada" in plano.entries[0].subject


def test_follow_up_respeita_o_filtro_de_responsavel(sessao: Session, cenario: Cenario) -> None:
    _massa(sessao, cenario)

    plano = panel_service.plan_follow_up(
        sessao,
        user=cenario.gil,
        request=_pedido(filters=ActionFilters(responsible_id=cenario.mario.person_id)),
    )

    assert [e.name for e in plano.entries] == ["Mário Membro"]


def test_envio_simulado_grava_uma_notificacao_por_responsavel(
    sessao: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(config.EMAIL_SENDING_VARIABLE, raising=False)
    _massa(sessao, cenario)

    resultado = panel_service.send_follow_up(sessao, user=cenario.gil, request=_pedido())

    linhas = list(sessao.scalars(select(Notification).where(Notification.kind == "follow_up")))
    assert len(resultado.outcomes) == len(linhas) == 2
    assert {linha.situation for linha in linhas} == {notification.SIMULATED}
    assert "simulado" in resultado.notice.lower()
    assert resultado.toast_kind == "aviso"


def test_sem_acoes_abertas_o_envio_e_recusado(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError, match="Nenhuma ação em aberto"):
        panel_service.send_follow_up(sessao, user=cenario.gil, request=_pedido())


def test_membro_nao_envia_follow_up(sessao: Session, cenario: Cenario) -> None:
    _massa(sessao, cenario)

    with pytest.raises(AccessDeniedError):
        panel_service.send_follow_up(sessao, user=cenario.mario, request=_pedido())
