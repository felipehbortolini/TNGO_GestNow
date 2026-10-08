"""Routes of the flow: the HTTP seam of the roles, the refusals and the fields (D7, D10)."""

from __future__ import annotations

import html
from urllib.parse import unquote

import azure.functions as func
import pytest
from sqlalchemy import select

from src.core import calendario
from src.modulos.programacao_semanal import calculations, routes, service
from src.modulos.programacao_semanal.models import Activity, ActivityDay
from src.modulos.programacao_semanal.service import NewActivity
from tests.cenario_programacao import WEEK, Scenario
from tests.identidades import requisicao

pytestmark = pytest.mark.usefixtures("sessao_das_rotas")

MATRIX_TARGETS = "prog-resumo prog-tabela"
DRAWER_TARGETS = "drawer prog-resumo prog-tabela"
PLANNER = "ps-plan@example.invalid"
FISCAL = "ps-fisc@example.invalid"
FOREMAN = "ps-enc@example.invalid"
ADMIN = "ps-admin@example.invalid"
SUPPLIER_A = "ps-forn-a@example.invalid"
VIEWER = "ps-view@example.invalid"


def _body(response: func.HttpResponse) -> str:
    return html.unescape(response.get_body().decode())


def _get(scenario: Scenario, email: str, **params: str) -> dict:
    query = {"semana": WEEK, "projeto": str(scenario.project_id)}
    return {"email": email, "params": {**query, **params}}


def _store(
    scenario: Scenario,
    *,
    unique_id: str = "R-1",
    situation: str = calculations.SITUATION_DRAFT,
    approval: str = calculations.APPROVAL_PENDING,
    day_shift: tuple[float, ...] = (0.0,) * calculations.DAYS,
) -> Activity:
    validated = situation != calculations.SITUATION_DRAFT
    return service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=scenario.company_a,
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
            day_shift=day_shift,
            situation=situation,
            approval=approval,
            approved_at=calendario.now() if approval == calculations.APPROVAL_APPROVED else None,
        ),
    )


def _matrix(scenario: Scenario, email: str) -> func.HttpResponse:
    return routes.matrix(
        requisicao(
            "/api/programacao-semanal/programacoes",
            alvo=MATRIX_TARGETS,
            **_get(scenario, email),
        )
    )


def _filters(scenario: Scenario, email: str) -> func.HttpResponse:
    return routes.toolbar(
        requisicao(
            "/api/programacao-semanal/programacoes/filtros",
            alvo="prog-filtros",
            **_get(scenario, email),
        )
    )


def _validation_fields(scenario: Scenario, activity: Activity, **overrides: str) -> dict:
    fields = {
        "atividade_id": str(activity.id),
        "versao": str(activity.version),
        "responsavel": str(scenario.fiscal.person_id),
        "comentarios": "",
    }
    return {**fields, **overrides}


def _report_fields(activity: Activity, **overrides: str) -> dict:
    fields = {
        "atividade_id": str(activity.id),
        "versao": str(activity.version),
        "observacoes": "",
        **{f"dias_realizado_{index}": "10" for index in range(calculations.DAYS)},
        **{f"dias_noite_{index}": "0" for index in range(calculations.DAYS)},
    }
    return {**fields, **overrides}


def _approval_fields(activity: Activity, **overrides: str) -> dict:
    fields = {
        "atividade_id": str(activity.id),
        "versao": str(activity.version),
        "comentarios": "",
    }
    return {**fields, **overrides}


def _post(route, scenario: Scenario, email: str, fields: dict, **params: str) -> func.HttpResponse:
    return route(
        requisicao(
            "/api/programacao-semanal/fluxo",
            metodo="POST",
            alvo=DRAWER_TARGETS,
            corpo=fields,
            **_get(scenario, email, **params),
        )
    )


# ── O caminho feliz de cada transição ───────────────────────────────────


def test_the_planner_validates_through_the_route(scenario: Scenario) -> None:
    activity = _store(scenario)

    response = _post(
        routes.save_validation, scenario, PLANNER, _validation_fields(scenario, activity)
    )

    body = _body(response)
    assert response.status_code == 200
    assert 'id="prog-tabela"' in body
    assert response.headers.get("X-TN-Toast")
    assert activity.situation == calculations.SITUATION_VALIDATED
    assert activity.inspector_id == scenario.fiscal.person_id


def test_the_supplier_reports_through_the_route(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    response = _post(routes.save_report, scenario, SUPPLIER_A, _report_fields(activity))

    assert response.status_code == 200
    assert 'id="prog-tabela"' in _body(response)
    days = scenario.session.scalars(
        select(ActivityDay).where(ActivityDay.activity_id == activity.id)
    ).all()
    assert len(days) == calculations.DAYS


def test_the_fiscal_approves_and_reopens_through_the_routes(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED, day_shift=(5.0,) * 7)

    approved = _post(
        routes.save_approval,
        scenario,
        FISCAL,
        _approval_fields(activity, comentarios="Conferido."),
    )
    assert approved.status_code == 200
    assert activity.approval == calculations.APPROVAL_APPROVED

    reopened = _post(
        routes.reopen_activity,
        scenario,
        FISCAL,
        _approval_fields(activity, motivo="A quarta saiu trocada."),
    )
    assert reopened.status_code == 200
    assert activity.approval == calculations.APPROVAL_PENDING


def test_the_planner_publishes_through_the_route(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    response = _post(
        routes.publish,
        scenario,
        PLANNER,
        {},
        atividade=str(activity.id),
        versao=str(activity.version),
    )

    assert response.status_code == 200
    assert activity.situation == calculations.SITUATION_PUBLISHED
    assert activity.published_at is not None


def test_publishing_the_week_publishes_the_validated_only(scenario: Scenario) -> None:
    _store(scenario, unique_id="D-1")
    validated = _store(scenario, unique_id="V-1", situation=calculations.SITUATION_VALIDATED)

    response = _post(routes.publish_week, scenario, PLANNER, {})

    assert response.status_code == 200
    assert validated.situation == calculations.SITUATION_PUBLISHED
    assert unquote(response.headers["X-TN-Toast"]) == "1 programação(ões) publicada(s)."


# ── Cada transição só é aceita do papel certo (403) ─────────────────────


def test_validation_from_another_role_is_403(scenario: Scenario) -> None:
    activity = _store(scenario)

    response = _post(
        routes.save_validation, scenario, SUPPLIER_A, _validation_fields(scenario, activity)
    )

    assert response.status_code == 403
    assert activity.situation == calculations.SITUATION_DRAFT


def test_report_from_another_role_is_403(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    response = _post(routes.save_report, scenario, FISCAL, _report_fields(activity))

    assert response.status_code == 403


def test_approval_from_another_role_is_403(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED, day_shift=(5.0,) * 7)

    response = _post(routes.save_approval, scenario, SUPPLIER_A, _approval_fields(activity))

    assert response.status_code == 403
    assert activity.approval == calculations.APPROVAL_PENDING


def test_reopen_from_another_role_is_403(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    response = _post(
        routes.reopen_activity,
        scenario,
        FOREMAN,
        _approval_fields(activity, motivo="Quero corrigir."),
    )

    assert response.status_code == 403


def test_publish_from_another_role_is_403(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    response = _post(
        routes.publish,
        scenario,
        SUPPLIER_A,
        {},
        atividade=str(activity.id),
        versao=str(activity.version),
    )

    assert response.status_code == 403


def test_publishing_the_week_from_another_role_is_403(scenario: Scenario) -> None:
    response = _post(routes.publish_week, scenario, SUPPLIER_A, {})

    assert response.status_code == 403


# ── 422, 409 e o painel de volta ────────────────────────────────────────


def test_validation_without_the_inspector_gives_the_panel_back_with_422(
    scenario: Scenario,
) -> None:
    activity = _store(scenario)

    response = _post(
        routes.save_validation,
        scenario,
        PLANNER,
        _validation_fields(scenario, activity, responsavel=""),
    )

    body = _body(response)
    assert response.status_code == 422
    assert 'id="drawer"' in body
    assert 'id="prog-resumo"' in body
    assert 'id="prog-tabela"' in body
    assert "Escolha um fiscal" in body
    assert activity.situation == calculations.SITUATION_DRAFT


def test_the_deviation_without_a_note_gives_the_panel_back_with_422(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    response = _post(
        routes.save_report,
        scenario,
        SUPPLIER_A,
        _report_fields(activity, **{f"dias_realizado_{index}": "0" for index in range(7)}),
    )

    body = _body(response)
    assert response.status_code == 422
    assert 'id="drawer"' in body
    assert "Explique o desvio" in body


def test_a_stale_version_gives_the_panel_back_with_409(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)
    first = _post(routes.save_report, scenario, SUPPLIER_A, _report_fields(activity))
    assert first.status_code == 200

    stale = _post(routes.save_report, scenario, SUPPLIER_A, _report_fields(activity, versao="1"))

    body = _body(stale)
    assert stale.status_code == 409
    assert 'id="drawer"' in body
    assert "alterado por" in body


def test_the_supplier_never_reaches_another_company(scenario: Scenario) -> None:
    other = service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=scenario.company_b,
            week=WEEK,
            unique_id="B-1",
            item=1,
            description="Serviço da B",
            planned_headline=70.0,
            author_person_id=scenario.planner.person_id,
            at=calendario.now(),
            location_id=scenario.location_id,
            unit_id=scenario.unit_id,
            foreman_id=scenario.foreman_b,
            inspector_id=scenario.fiscal.person_id,
            planned_days=(10.0,) * calculations.DAYS,
            situation=calculations.SITUATION_VALIDATED,
        ),
    )

    response = _post(routes.save_report, scenario, SUPPLIER_A, _report_fields(other))

    assert response.status_code == 403


# ── O botão da próxima ação e o menu por perfil ─────────────────────────


def test_the_row_button_changes_with_the_profile(scenario: Scenario) -> None:
    _store(scenario, unique_id="D-1")

    planner_body = _body(_matrix(scenario, PLANNER))
    supplier_body = _body(_matrix(scenario, SUPPLIER_A))
    viewer_body = _body(_matrix(scenario, VIEWER))

    assert 'title="Validar D-1"' in planner_body
    assert "Editar a programação" in planner_body
    assert 'title="Validar D-1"' not in supplier_body
    assert 'title="Ver D-1"' in supplier_body
    assert 'title="Ver D-1"' in viewer_body
    assert "Mais ações" not in viewer_body


def test_the_fiscal_sees_aprovar_where_the_supplier_sees_lancar(scenario: Scenario) -> None:
    _store(
        scenario,
        unique_id="V-1",
        situation=calculations.SITUATION_VALIDATED,
        day_shift=(5.0,) * 7,
    )

    assert 'title="Aprovar V-1"' in _body(_matrix(scenario, FISCAL))
    assert 'title="Lançar V-1"' in _body(_matrix(scenario, SUPPLIER_A))


def test_the_admin_menu_offers_the_other_steps(scenario: Scenario) -> None:
    _store(
        scenario,
        unique_id="V-1",
        situation=calculations.SITUATION_VALIDATED,
        day_shift=(5.0,) * 7,
    )

    body = _body(_matrix(scenario, ADMIN))

    assert 'title="Aprovar V-1"' in body
    assert "Lançar o realizado" in body
    assert "Publicar<small>" in body
    assert "Excluir a atividade" in body


def test_the_published_row_does_not_offer_publish_again(scenario: Scenario) -> None:
    _store(
        scenario,
        unique_id="P-1",
        situation=calculations.SITUATION_PUBLISHED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    body = _body(_matrix(scenario, PLANNER))

    assert "Publicar" not in body
    assert 'title="Ver P-1"' in body


def test_the_week_publication_is_offered_to_the_planner_only(scenario: Scenario) -> None:
    assert "Publicar as validadas" in _body(_filters(scenario, PLANNER))
    assert "Publicar as validadas" in _body(_filters(scenario, ADMIN))
    assert "Publicar as validadas" not in _body(_filters(scenario, SUPPLIER_A))
    assert "Publicar as validadas" not in _body(_filters(scenario, VIEWER))


# ── Os painéis de leitura ───────────────────────────────────────────────


def test_the_validation_form_lists_the_inspectors_of_the_project(scenario: Scenario) -> None:
    activity = _store(scenario)

    response = routes.validation_form(
        requisicao(
            "/api/programacao-semanal/validacoes/formulario",
            alvo="drawer",
            **_get(scenario, PLANNER, atividade=str(activity.id)),
        )
    )

    body = _body(response)
    assert response.status_code == 200
    assert "Validar a programação" in body
    assert "ps-fisc" in body


def test_the_report_form_carries_both_shifts_and_the_shortcuts(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    response = routes.done_form(
        requisicao(
            "/api/programacao-semanal/realizados/formulario",
            alvo="drawer",
            **_get(scenario, SUPPLIER_A, atividade=str(activity.id)),
        )
    )

    body = _body(response)
    assert response.status_code == 200
    for index in range(calculations.DAYS):
        assert f'name="dias_realizado_{index}"' in body
        assert f'name="dias_noite_{index}"' in body
    assert "= previsto" in body
    assert "Copiar a semana inteira" in body


def test_the_detail_panel_is_read_only_and_carries_the_history(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    response = routes.activity_detail(
        requisicao(
            "/api/programacao-semanal/atividades/detalhe",
            alvo="drawer",
            **_get(scenario, VIEWER, atividade=str(activity.id)),
        )
    )

    body = _body(response)
    assert response.status_code == 200
    assert "Somente leitura" in body
    assert "Atividade criada" in body


def test_the_fiscal_opens_the_reopen_form_when_the_done_is_approved(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    response = routes.approval_form(
        requisicao(
            "/api/programacao-semanal/aprovacoes/formulario",
            alvo="drawer",
            **_get(scenario, FISCAL, atividade=str(activity.id)),
        )
    )

    body = _body(response)
    assert response.status_code == 200
    assert "Reabrir o realizado" in body
    assert 'name="motivo"' in body
