"""Routes of the governance: the panel, the queue and the change requests (D7, D10)."""

from __future__ import annotations

import html
from urllib.parse import unquote

import azure.functions as func
import pytest
from sqlalchemy import func as sql_func
from sqlalchemy import select

from src.core import calendario
from src.core.excel import XLSX_CONTENT_TYPE
from src.modulos.programacao_semanal import calculations, routes, service
from src.modulos.programacao_semanal.models import Activity, ChangeRequest
from src.modulos.programacao_semanal.service import NewActivity
from tests.cenario_programacao import WEEK, Scenario
from tests.identidades import requisicao

pytestmark = pytest.mark.usefixtures("sessao_das_rotas")

MATRIX_TARGETS = "prog-resumo prog-tabela"
DRAWER_TARGETS = "drawer prog-resumo prog-tabela"
QUEUE_TARGETS = "gov-pedidos gov-trilha"
PLANNER = "ps-plan@example.invalid"
FISCAL = "ps-fisc@example.invalid"
SUPPLIER_A = "ps-forn-a@example.invalid"
SUPPLIER_B = "ps-forn-b@example.invalid"
VIEWER = "ps-view@example.invalid"
REASON = "A medição de quarta saiu trocada com a de quinta na conferência."


def _body(response: func.HttpResponse) -> str:
    return html.unescape(response.get_body().decode())


def _get(scenario: Scenario, email: str, **params: str) -> dict:
    return {"email": email, "params": {"projeto": str(scenario.project_id), **params}}


def _store(
    scenario: Scenario,
    *,
    unique_id: str = "R-1",
    company_id: int | None = None,
    situation: str = calculations.SITUATION_PUBLISHED,
    approval: str = calculations.APPROVAL_APPROVED,
    done: float = 70.0,
) -> Activity:
    validated = situation != calculations.SITUATION_DRAFT
    return service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=company_id or scenario.company_a,
            week=WEEK,
            unique_id=unique_id,
            item=1,
            description=f"Serviço {unique_id}",
            planned_headline=70.0,
            author_person_id=scenario.planner.person_id,
            at=calendario.now(),
            location_id=scenario.location_id,
            unit_id=scenario.unit_id,
            foreman_id=scenario.foreman_a,
            inspector_id=scenario.fiscal.person_id if validated else None,
            planned_days=(10.0,) * calculations.DAYS,
            day_shift=(done / calculations.DAYS,) * calculations.DAYS,
            situation=situation,
            approval=approval,
            approved_at=calendario.now() if approval == calculations.APPROVAL_APPROVED else None,
        ),
    )


def _request(scenario: Scenario, activity: Activity, email: str) -> ChangeRequest:
    return service.request_change(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a if email == SUPPLIER_A else scenario.supplier_b),
        activity_id=activity.id,
        reason=REASON,
    )


def _requests(scenario: Scenario) -> int:
    return scenario.session.scalar(select(sql_func.count()).select_from(ChangeRequest)) or 0


def _open(route, scenario: Scenario, email: str, fields: dict, **params: str) -> func.HttpResponse:
    return route(
        requisicao(
            "/api/programacao-semanal/pedidos",
            metodo="POST",
            alvo=DRAWER_TARGETS,
            corpo=fields,
            **_get(scenario, email, **params),
        )
    )


def _decide(
    scenario: Scenario,
    request: ChangeRequest,
    *,
    email: str,
    decision: str,
    answer: str = "",
    versao: str | None = None,
) -> func.HttpResponse:
    return routes.decide_request(
        requisicao(
            f"/api/programacao-semanal/pedidos/{request.id}/decisao",
            metodo="POST",
            alvo=QUEUE_TARGETS,
            rota={"id": str(request.id)},
            corpo={
                "decisao": decision,
                "resposta": answer,
                "versao": versao if versao is not None else str(request.version),
            },
            **_get(scenario, email),
        )
    )


# ── O painel ────────────────────────────────────────────────────────────


def test_the_panel_route_serves_the_indicators_and_the_control_list(scenario: Scenario) -> None:
    _store(scenario)

    response = routes.governance_panel(
        requisicao(
            "/api/programacao-semanal/governanca", alvo="gov-painel", **_get(scenario, PLANNER)
        )
    )

    body = _body(response)
    assert response.status_code == 200
    assert 'id="gov-painel"' in body
    for label in (
        "Contratadas ativas",
        "Janelas abertas hoje",
        "Aguardando fiscal",
        "Atividades no histórico",
        "Janelas de programação",
        "Lista de controle",
        "Pedidos de alteração",
        "Trilha de auditoria",
    ):
        assert label in body
    assert "Empresa A" in body
    assert 'data-tn-excel="/api/programacao-semanal/governanca/excel"' in body
    assert 'data-tn-pdf="/api/programacao-semanal/governanca/imprimivel"' in body


def test_the_supplier_panel_never_shows_another_company(scenario: Scenario) -> None:
    _store(scenario, unique_id="A-1")
    _store(scenario, unique_id="B-1", company_id=scenario.company_b)

    response = routes.governance_panel(
        requisicao(
            "/api/programacao-semanal/governanca", alvo="gov-painel", **_get(scenario, SUPPLIER_A)
        )
    )

    body = _body(response)
    assert "Empresa A" in body
    assert "Empresa B" not in body


def test_the_supplier_panel_hides_the_trail(scenario: Scenario) -> None:
    response = routes.governance_panel(
        requisicao(
            "/api/programacao-semanal/governanca", alvo="gov-painel", **_get(scenario, SUPPLIER_A)
        )
    )

    assert "Trilha de auditoria" not in _body(response)


# ── A fila ──────────────────────────────────────────────────────────────


def test_the_queue_route_shows_only_the_requests_of_the_company(scenario: Scenario) -> None:
    activity_a = _store(scenario, unique_id="Q-A")
    activity_b = _store(scenario, unique_id="Q-B", company_id=scenario.company_b)
    _request(scenario, activity_a, SUPPLIER_A)
    _request(scenario, activity_b, SUPPLIER_B)

    supplier = _body(
        routes.request_queue(
            requisicao(
                "/api/programacao-semanal/pedidos", alvo="gov-pedidos", **_get(scenario, SUPPLIER_A)
            )
        )
    )
    planner = _body(
        routes.request_queue(
            requisicao(
                "/api/programacao-semanal/pedidos", alvo="gov-pedidos", **_get(scenario, PLANNER)
            )
        )
    )

    assert "Q-A" in supplier
    assert "Q-B" not in supplier
    assert "Q-A" in planner and "Q-B" in planner


def test_the_queue_route_offers_the_decision_to_the_planner_only(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="Q-A")
    _request(scenario, activity, SUPPLIER_A)

    planner = _body(
        routes.request_queue(
            requisicao(
                "/api/programacao-semanal/pedidos", alvo="gov-pedidos", **_get(scenario, PLANNER)
            )
        )
    )
    supplier = _body(
        routes.request_queue(
            requisicao(
                "/api/programacao-semanal/pedidos", alvo="gov-pedidos", **_get(scenario, SUPPLIER_A)
            )
        )
    )

    assert 'name="decisao"' in planner
    assert "Liberar" in planner and "Recusar" in planner
    assert "Aguardando decisão" in supplier
    assert 'name="decisao"' not in supplier


# ── Abrir o pedido ──────────────────────────────────────────────────────


def test_the_supplier_opens_a_request_through_the_route(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")

    response = _open(
        routes.open_request,
        scenario,
        SUPPLIER_A,
        {
            "atividade_id": str(activity.id),
            "motivo": REASON,
            "semana": WEEK,
        },
    )

    body = _body(response)
    assert response.status_code == 200
    assert 'id="drawer"' in body
    assert 'id="prog-tabela"' in body
    assert unquote(response.headers["X-TN-Toast"]) == "Pedido registrado para C-1."
    assert _requests(scenario) == 1


def test_a_short_reason_returns_the_drawer_with_422(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")

    response = _open(
        routes.open_request,
        scenario,
        SUPPLIER_A,
        {"atividade_id": str(activity.id), "motivo": "curto", "semana": WEEK},
    )

    body = _body(response)
    assert response.status_code == 422
    assert 'id="drawer"' in body
    assert 'id="prog-resumo"' in body
    assert 'id="prog-tabela"' in body
    assert "Explique o que precisa mudar" in body
    assert _requests(scenario) == 0


def test_the_supplier_does_not_open_a_request_for_another_company(scenario: Scenario) -> None:
    other = _store(scenario, unique_id="B-1", company_id=scenario.company_b)

    response = _open(
        routes.open_request,
        scenario,
        SUPPLIER_A,
        {"atividade_id": str(other.id), "motivo": REASON, "semana": WEEK},
    )

    assert response.status_code == 403
    assert _requests(scenario) == 0


def test_a_request_for_an_editable_activity_is_422(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        unique_id="D-1",
        situation=calculations.SITUATION_DRAFT,
        approval=calculations.APPROVAL_PENDING,
        done=0.0,
    )

    response = _open(
        routes.open_request,
        scenario,
        SUPPLIER_A,
        {"atividade_id": str(activity.id), "motivo": REASON, "semana": WEEK},
    )

    assert response.status_code == 422
    assert "aberta para edição" in _body(response)
    assert _requests(scenario) == 0


# ── Decidir o pedido ────────────────────────────────────────────────────


def test_the_planner_applies_through_the_route(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")
    request = _request(scenario, activity, SUPPLIER_A)

    response = _decide(scenario, request, email=PLANNER, decision="aplicar")

    body = _body(response)
    assert response.status_code == 200
    assert 'id="gov-pedidos"' in body
    assert 'id="gov-trilha"' in body
    assert unquote(response.headers["X-TN-Toast"]) == "C-1 liberado para alteração."
    assert activity.approval == calculations.APPROVAL_PENDING
    assert request.situation == service.REQUEST_APPLIED


def test_the_planner_refuses_through_the_route(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")
    request = _request(scenario, activity, SUPPLIER_A)

    response = _decide(
        scenario,
        request,
        email=PLANNER,
        decision="recusar",
        answer="O item está publicado e medido.",
    )

    assert response.status_code == 200
    assert unquote(response.headers["X-TN-Toast"]) == "Pedido de C-1 recusado."
    assert request.situation == service.REQUEST_REJECTED
    assert activity.approval == calculations.APPROVAL_APPROVED


def test_refusing_without_the_answer_is_422(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")
    request = _request(scenario, activity, SUPPLIER_A)

    response = _decide(scenario, request, email=PLANNER, decision="recusar")

    body = _body(response)
    assert response.status_code == 422
    assert 'id="gov-pedidos"' in body
    assert "Diga por que o pedido está sendo recusado" in body
    assert request.situation == service.REQUEST_PENDING


def test_a_supplier_cannot_decide(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")
    request = _request(scenario, activity, SUPPLIER_A)

    response = _decide(scenario, request, email=SUPPLIER_A, decision="aplicar")

    assert response.status_code == 403
    assert request.situation == service.REQUEST_PENDING


def test_the_fiscal_cannot_decide(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")
    request = _request(scenario, activity, SUPPLIER_A)

    response = _decide(scenario, request, email=FISCAL, decision="aplicar")

    assert response.status_code == 403
    assert request.situation == service.REQUEST_PENDING


def test_a_stale_decision_is_409(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")
    request = _request(scenario, activity, SUPPLIER_A)

    response = _decide(scenario, request, email=PLANNER, decision="aplicar", versao="0")

    body = _body(response)
    assert response.status_code == 409
    assert 'id="gov-pedidos"' in body
    assert "alterado por" in body
    assert request.situation == service.REQUEST_PENDING


# ── A trilha ────────────────────────────────────────────────────────────


def test_the_trail_route_is_only_for_the_planner(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")
    request = _request(scenario, activity, SUPPLIER_A)
    _decide(scenario, request, email=PLANNER, decision="aplicar")

    planner = routes.governance_trail(
        requisicao(
            "/api/programacao-semanal/governanca/trilha",
            alvo="gov-trilha",
            **_get(scenario, PLANNER),
        )
    )
    supplier = routes.governance_trail(
        requisicao(
            "/api/programacao-semanal/governanca/trilha",
            alvo="gov-trilha",
            **_get(scenario, SUPPLIER_A),
        )
    )

    body = _body(planner)
    assert planner.status_code == 200
    assert "Pedido de alteração aberto" in body
    assert "Pedido de alteração aplicado" in body
    assert supplier.status_code == 403


# ── A ação na Programação ───────────────────────────────────────────────


def test_the_matrix_offers_the_request_where_the_app_offers(scenario: Scenario) -> None:
    _store(scenario, unique_id="C-1")

    response = routes.matrix(
        requisicao(
            "/api/programacao-semanal/programacoes",
            alvo=MATRIX_TARGETS,
            **_get(scenario, SUPPLIER_A, semana=WEEK),
        )
    )

    body = _body(response)
    assert "Pedir alteração" in body
    assert "/api/programacao-semanal/pedidos/formulario?atividade=" in body


def test_the_matrix_does_not_offer_the_request_for_an_editable_row(scenario: Scenario) -> None:
    _store(
        scenario,
        unique_id="D-1",
        situation=calculations.SITUATION_DRAFT,
        approval=calculations.APPROVAL_PENDING,
        done=0.0,
    )

    response = routes.matrix(
        requisicao(
            "/api/programacao-semanal/programacoes",
            alvo=MATRIX_TARGETS,
            **_get(scenario, SUPPLIER_A, semana=WEEK),
        )
    )

    assert "Pedir alteração" not in _body(response)


def test_the_detail_panel_carries_the_request_form(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")

    response = routes.activity_detail(
        requisicao(
            "/api/programacao-semanal/atividades/detalhe",
            alvo="drawer",
            **_get(scenario, SUPPLIER_A, atividade=str(activity.id)),
        )
    )

    body = _body(response)
    assert response.status_code == 200
    assert "Pedir alteração" in body
    assert 'name="motivo"' in body
    assert "A programação foi publicada." in body


def test_the_request_form_opens_in_the_drawer(scenario: Scenario) -> None:
    activity = _store(scenario, unique_id="C-1")

    response = routes.request_form(
        requisicao(
            "/api/programacao-semanal/pedidos/formulario",
            alvo="drawer",
            **_get(scenario, SUPPLIER_A, atividade=str(activity.id)),
        )
    )

    body = _body(response)
    assert response.status_code == 200
    assert 'id="drawer"' in body
    assert "O que precisa mudar, e por quê" in body


# ── As exportações ──────────────────────────────────────────────────────


def test_the_exports_answer_with_their_mechanisms(scenario: Scenario) -> None:
    _store(scenario, unique_id="C-1")

    excel = routes.governance_excel(
        requisicao(
            "/api/programacao-semanal/governanca/excel",
            email=PLANNER,
            params={"projeto": str(scenario.project_id)},
        )
    )
    printable = routes.governance_printable(
        requisicao(
            "/api/programacao-semanal/governanca/imprimivel",
            alvo="folha-impressao",
            **_get(scenario, PLANNER),
        )
    )

    assert excel.status_code == 200
    assert excel.headers.get("Content-Type") == XLSX_CONTENT_TYPE
    assert printable.status_code == 200
    assert "Governança da programação" in _body(printable)
