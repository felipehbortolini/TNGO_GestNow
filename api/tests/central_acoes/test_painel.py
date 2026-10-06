"""Painel e follow-up da Central (ISSUE-020): contagens, agrupamento e envio simulado.

As contagens do painel saem da mesma listagem da tela Ações, então batem com ela no mesmo
escopo; o follow-up agrupa as ações em aberto por responsável e registra uma notificação por
responsável com e-mail — "simulado" enquanto o envio real está desligado.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

import azure.functions as func
from sqlalchemy import func as sql_func
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.models import Notification
from src.core.notification import SIMULATED
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.central_acoes import calculations, panel_routes, panel_service, service
from src.modulos.central_acoes.validation import ActionFilters
from tests.apoio_acoes import REFERENCIA, Cenario, nova_acao


def _escopo(cenario: Cenario) -> Scope:
    return Scope(project_id=cenario.projeto_a.id, source="url")


def _criar(sessao: Session, cenario: Cenario, **campos: object) -> service.ActionRecord:
    return service.create_action(
        sessao, user=cenario.gil, new=nova_acao(cenario, **campos), reference_date=REFERENCIA
    )


def _follow_up_request(cenario: Cenario) -> panel_service.FollowUpRequest:
    return panel_service.FollowUpRequest(
        scope=_escopo(cenario),
        filters=ActionFilters(status=calculations.StatusFilter.ALL),
        reference_date=REFERENCIA,
    )


# ── As contagens do painel batem com a lista ─────────────────────────────────────────────────


def test_as_contagens_do_painel_batem_com_as_da_lista(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario, origin_ref="RSK-EM-DIA")
    _criar(
        sessao,
        cenario,
        origin_ref="RSK-ATRASADA",
        planned_date=REFERENCIA - timedelta(days=4),
    )
    _criar(sessao, cenario, origin_ref="RSK-CONCLUIDA", completed_on=REFERENCIA)

    lista = service.list_actions(
        sessao,
        user=cenario.gil,
        scope=_escopo(cenario),
        filters=ActionFilters(status=calculations.StatusFilter.ALL),
        reference_date=REFERENCIA,
    )
    painel = panel_service.dashboard(
        sessao, user=cenario.gil, scope=_escopo(cenario), origin="", reference_date=REFERENCIA
    )

    assert painel.counts == lista.counts
    assert painel.universe == lista.universe == 3
    assert (painel.counts.total, painel.counts.open, painel.counts.overdue) == (3, 2, 1)
    assert painel.counts.completed == 1


def test_o_filtro_de_origem_do_painel_recorta_o_universo(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario, origin_ref="RSK-1")
    _criar(sessao, cenario, origin="Ata", origin_ref="TN-2026-0001")

    painel = panel_service.dashboard(
        sessao,
        user=cenario.gil,
        scope=_escopo(cenario),
        origin="Ata",
        reference_date=REFERENCIA,
    )

    assert painel.counts.total == 1
    assert painel.universe == 2  # a referência é o escopo inteiro; o filtro recorta as contagens
    assert [linha.origin for linha in painel.origins] == ["Ata"]


# ── Follow-up ────────────────────────────────────────────────────────────────────────────────


def _tres_acoes(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario, origin_ref="RSK-1")
    _criar(sessao, cenario, origin_ref="RSK-2", subject="Protocolar o monitoramento")
    _criar(
        sessao,
        cenario,
        origin_ref="RSK-3",
        responsible_id=cenario.mario.person_id,
        subject="Revisar o procedimento",
    )


def test_o_follow_up_agrupa_por_responsavel(sessao: Session, cenario: Cenario) -> None:
    _tres_acoes(sessao, cenario)

    plano = panel_service.plan_follow_up(
        sessao, user=cenario.gil, request=_follow_up_request(cenario)
    )

    por_nome = {entrada.name: entrada for entrada in plano.entries}
    assert plano.action_count == 3
    assert set(por_nome) == {"Gil Gestor", "Mário Membro"}
    assert len(por_nome["Gil Gestor"].group.actions) == 2
    assert por_nome["Mário Membro"].email == "mario.membro@acoes.example.invalid"
    assert plano.simulated is True
    assert all(entrada.subject for entrada in plano.entries)


def test_o_envio_do_follow_up_registra_uma_notificacao_simulada_por_responsavel(
    sessao: Session, cenario: Cenario
) -> None:
    _tres_acoes(sessao, cenario)

    resultado = panel_service.send_follow_up(
        sessao, user=cenario.gil, request=_follow_up_request(cenario)
    )

    assert len(resultado.outcomes) == 2
    assert {item.situation for item in resultado.outcomes} == {SIMULATED}
    assert "simulado" in resultado.notice.lower()
    gravadas = sessao.scalar(select(sql_func.count()).select_from(Notification))
    assert gravadas == 2


def test_o_follow_up_sem_acao_aberta_e_recusado(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario, origin_ref="RSK-CONCLUIDA", completed_on=REFERENCIA)

    plano = panel_service.plan_follow_up(
        sessao, user=cenario.gil, request=_follow_up_request(cenario)
    )

    assert plano.entries == ()


# ── A rota do PDF com o filtro ───────────────────────────────────────────────────────────────


def _requisicao(
    usuario: User, *, params: Mapping[str, str] | None = None, alvo: str = "painel-conteudo"
) -> func.HttpRequest:
    return func.HttpRequest(
        method="GET",
        url="/api/central-acoes/painel",
        headers={
            "X-Alpine-Request": "true",
            "X-Alpine-Target": alvo,
            "Cookie": f"{DEMO_COOKIE}={usuario.id}",
        },
        params=dict(params or {}),
        route_params={},
        body=b"",
    )


def test_o_pdf_do_painel_sai_com_o_filtro_aplicado(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario, origin_ref="RSK-1")
    _criar(sessao, cenario, origin="Ata", origin_ref="TN-2026-0001")

    resposta = panel_routes.panel_printable(_requisicao(cenario.gil, params={"origem": "Ata"}))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Ata" in corpo
    assert "RSK-1" not in corpo


def test_o_excel_do_painel_sai_com_o_filtro_aplicado(sessao: Session, cenario: Cenario) -> None:
    _criar(sessao, cenario, origin_ref="RSK-1")

    resposta = panel_routes.panel_excel(_requisicao(cenario.gil, params={"origem": "Risco"}))

    assert resposta.status_code == 200
    assert resposta.get_body().startswith(b"PK")
