"""Routes of the five-step flow: the 403 of each step, the drawers and the row of the matrix (ISSUE-052)."""

from __future__ import annotations

import html
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote

import azure.functions as func
import pytest

from src.core import calendario
from src.core.rbac import ScheduleRole
from src.modulos.programacao_semanal import calculations, routes, service
from src.modulos.programacao_semanal.models import Activity
from src.modulos.programacao_semanal.service import NewActivity
from tests.cenario_programacao import WEEK, Scenario, make_user
from tests.identidades import requisicao

pytestmark = pytest.mark.usefixtures("sessao_das_rotas")

DRAWER_TARGETS = "drawer prog-resumo prog-tabela"
PLANNER = "ps-plan@example.invalid"
SUPPLIER_A = "ps-forn-a@example.invalid"
SUPPLIER_B = "ps-forn-b@example.invalid"
VIEWER = "ps-view@example.invalid"
INSPECTOR = "fr-fiscal@example.invalid"
OTHER_INSPECTOR = "fr-fiscal2@example.invalid"
FORM_BASE = "/api/programacao-semanal"


@dataclass(frozen=True)
class Inspectors:
    """The two inspectors of the project, as persons of the register."""

    mine: int
    other: int


@pytest.fixture
def inspectors(scenario: Scenario) -> Inspectors:
    mine = make_user(
        scenario.session,
        email=INSPECTOR,
        project_id=scenario.project_id,
        role=ScheduleRole.INSPECTOR,
    )
    other = make_user(
        scenario.session,
        email=OTHER_INSPECTOR,
        project_id=scenario.project_id,
        role=ScheduleRole.INSPECTOR,
    )
    return Inspectors(mine=mine.person_id, other=other.person_id)


def _toast(response: func.HttpResponse) -> str:
    return unquote(response.headers.get("X-TN-Toast", ""))


def _body(response: func.HttpResponse) -> str:
    return html.unescape(response.get_body().decode())


def _store(
    scenario: Scenario,
    inspectors: Inspectors,
    *,
    state: tuple[str, str] = (calculations.SITUATION_DRAFT, calculations.APPROVAL_PENDING),
    done: float = 0.0,
) -> Activity:
    situation, approval = state
    return service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=scenario.company_a,
            week=WEEK,
            unique_id="F-1",
            item=1,
            description="Serviço do fluxo",
            planned_headline=70.0,
            author_person_id=scenario.planner.person_id,
            at=calendario.now(),
            location_id=scenario.location_id,
            unit_id=scenario.unit_id,
            inspector_id=inspectors.mine if situation != calculations.SITUATION_DRAFT else None,
            foreman_id=scenario.foreman_a,
            planned_days=(10.0,) * 7,
            day_shift=(done,) * 7,
            situation=situation,
            approval=approval,
        ),
    )


def _call(
    route: Callable[[func.HttpRequest], func.HttpResponse],
    scenario: Scenario,
    email: str,
    *,
    method: str = "GET",
    fields: dict[str, str] | None = None,
) -> func.HttpResponse:
    params = {"semana": WEEK, "projeto": str(scenario.project_id)}
    if method == "GET":
        params.update(fields or {})
        fields = None
    return route(
        requisicao(
            f"{FORM_BASE}/passo",
            metodo=method,
            email=email,
            alvo=DRAWER_TARGETS if method == "POST" else "drawer",
            params=params,
            corpo=fields,
        )
    )


def _matrix(scenario: Scenario, email: str) -> str:
    response = _call(routes.matrix, scenario, email)
    assert response.status_code == 200
    return _body(response)


VALIDATED = (calculations.SITUATION_VALIDATED, calculations.APPROVAL_PENDING)
APPROVED = (calculations.SITUATION_VALIDATED, calculations.APPROVAL_APPROVED)


# ── The button and the menu of the row, by profile ───────────────────────


def test_the_button_of_the_row_is_the_next_action_of_who_looks(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    _store(scenario, inspectors, state=VALIDATED, done=10.0)

    assert "Lançar o realizado · F-1" in _matrix(scenario, SUPPLIER_A)
    assert "Aprovar o realizado · F-1" in _matrix(scenario, INSPECTOR)
    assert "Ver os detalhes · F-1" in _matrix(scenario, OTHER_INSPECTOR)


def test_the_planner_sees_validate_on_a_draft(scenario: Scenario, inspectors: Inspectors) -> None:
    _store(scenario, inspectors)

    body = _matrix(scenario, PLANNER)

    assert "Validar a programação · F-1" in body
    assert "Publicar a programação · F-1" not in body


def test_the_viewer_only_looks_and_has_no_menu(scenario: Scenario, inspectors: Inspectors) -> None:
    _store(scenario, inspectors, state=VALIDATED, done=10.0)

    body = _matrix(scenario, VIEWER)

    assert "Ver os detalhes · F-1" in body
    assert "Mais ações para F-1" not in body


def test_the_menu_holds_only_what_the_profile_can_still_do(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    _store(scenario, inspectors, state=APPROVED, done=10.0)

    inspector_body = _matrix(scenario, INSPECTOR)
    supplier_body = _matrix(scenario, SUPPLIER_A)

    assert "Reabrir o realizado" in inspector_body
    assert "Reabrir o realizado" not in supplier_body


# ── Each step: the wrong role is 403 ─────────────────────────────────────


def test_a_supplier_cannot_open_or_post_the_validation(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors)

    opened = _call(
        routes.validation_form,
        scenario,
        SUPPLIER_A,
        fields={"atividade": str(activity.id)},
    )
    posted = _call(
        routes.validate_activity,
        scenario,
        SUPPLIER_A,
        method="POST",
        fields={
            "atividade_id": str(activity.id),
            "versao": str(activity.version),
            "responsavel": str(inspectors.mine),
        },
    )

    assert (opened.status_code, posted.status_code) == (403, 403)
    assert activity.situation == calculations.SITUATION_DRAFT


def test_the_planner_validates_and_the_matrix_shows_it(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors)

    response = _call(
        routes.validate_activity,
        scenario,
        PLANNER,
        method="POST",
        fields={
            "atividade_id": str(activity.id),
            "versao": str(activity.version),
            "responsavel": str(inspectors.mine),
            "comentarios": "Pode lançar",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("X-TN-Toast")
    assert "Validada" in _body(response)
    assert activity.situation == calculations.SITUATION_VALIDATED


def test_validating_without_an_inspector_gives_the_drawer_back_with_422(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors)

    response = _call(
        routes.validate_activity,
        scenario,
        PLANNER,
        method="POST",
        fields={"atividade_id": str(activity.id), "versao": str(activity.version)},
    )

    assert response.status_code == 422
    assert 'id="drawer"' in _body(response)
    assert "Escolha um fiscal" in _body(response)


def test_the_report_drawer_has_the_shortcuts_and_the_two_shifts(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors, state=VALIDATED)

    response = _call(
        routes.report_form,
        scenario,
        SUPPLIER_A,
        fields={"atividade": str(activity.id)},
    )

    body = _body(response)
    assert response.status_code == 200
    assert "= previsto" in body
    assert "Copiar a semana" in body
    assert 'name="dias_realizado_0"' in body
    assert 'name="dias_noite_6"' in body
    assert 'name="versao"' in body


def _report_fields(activity: Activity, day: str, note: str = "") -> dict[str, str]:
    fields = {
        "atividade_id": str(activity.id),
        "versao": str(activity.version),
        "observacoes": note,
    }
    for index in range(7):
        fields[f"dias_realizado_{index}"] = day
        fields[f"dias_noite_{index}"] = "0"
    return fields


def test_a_deviation_above_the_limit_without_justification_is_422_with_the_message(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors, state=VALIDATED)

    response = _call(
        routes.report_done,
        scenario,
        SUPPLIER_A,
        method="POST",
        fields=_report_fields(activity, "5"),
    )

    body = _body(response)
    assert response.status_code == 422
    assert "Explique o desvio para salvar." in body
    assert 'id="drawer"' in body


def test_the_report_inside_the_limit_is_saved_and_the_matrix_redraws(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors, state=VALIDATED)

    response = _call(
        routes.report_done,
        scenario,
        SUPPLIER_A,
        method="POST",
        fields=_report_fields(activity, "10"),
    )

    assert response.status_code == 200
    assert "PPC de 100%" in _toast(response)
    assert "Aguarda fiscal" in _body(response)


def test_the_planner_cannot_report(scenario: Scenario, inspectors: Inspectors) -> None:
    activity = _store(scenario, inspectors, state=VALIDATED)

    response = _call(
        routes.report_done,
        scenario,
        PLANNER,
        method="POST",
        fields=_report_fields(activity, "10"),
    )

    assert response.status_code == 403


def test_only_the_inspector_of_the_activity_approves(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors, state=VALIDATED, done=10.0)
    fields = {"atividade_id": str(activity.id), "versao": str(activity.version)}

    other = _call(routes.approve_done, scenario, OTHER_INSPECTOR, method="POST", fields=fields)
    supplier = _call(routes.approve_done, scenario, SUPPLIER_A, method="POST", fields=fields)
    mine = _call(routes.approve_done, scenario, INSPECTOR, method="POST", fields=fields)

    assert (other.status_code, supplier.status_code, mine.status_code) == (403, 403, 200)
    assert activity.approval == calculations.APPROVAL_APPROVED
    assert "Aprovado" in _body(mine)


def test_reopening_asks_for_the_reason_and_gives_the_drawer_back(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors, state=APPROVED, done=10.0)
    fields = {"atividade_id": str(activity.id), "versao": str(activity.version), "motivo": ""}

    refused = _call(routes.reopen_done, scenario, INSPECTOR, method="POST", fields=fields)
    reopened = _call(
        routes.reopen_done,
        scenario,
        INSPECTOR,
        method="POST",
        fields={**fields, "motivo": "Medição divergente"},
    )

    assert refused.status_code == 422
    assert "Explique por que está reabrindo" in _body(refused)
    assert reopened.status_code == 200
    assert activity.approval == calculations.APPROVAL_PENDING


def test_only_the_planner_publishes(scenario: Scenario, inspectors: Inspectors) -> None:
    activity = _store(scenario, inspectors, state=APPROVED, done=10.0)
    fields = {"atividade_id": str(activity.id), "versao": str(activity.version)}

    supplier = _call(routes.publish_activity, scenario, SUPPLIER_A, method="POST", fields=fields)
    inspector = _call(routes.publish_activity, scenario, INSPECTOR, method="POST", fields=fields)
    planner = _call(routes.publish_activity, scenario, PLANNER, method="POST", fields=fields)

    assert (supplier.status_code, inspector.status_code, planner.status_code) == (403, 403, 200)
    assert activity.situation == calculations.SITUATION_PUBLISHED
    assert "Publicada" in _body(planner)


def test_publishing_the_week_is_for_the_planner(scenario: Scenario, inspectors: Inspectors) -> None:
    _store(scenario, inspectors, state=VALIDATED)

    refused = _call(routes.publish_week, scenario, SUPPLIER_A, method="POST", fields={})
    done = _call(routes.publish_week, scenario, PLANNER, method="POST", fields={})

    assert refused.status_code == 403
    assert done.status_code == 200
    assert "1 programação(ões) publicada(s)." in _toast(done)


def test_a_supplier_of_another_company_cannot_open_the_detail(
    scenario: Scenario, inspectors: Inspectors
) -> None:
    activity = _store(scenario, inspectors, state=VALIDATED, done=10.0)

    own = _call(
        routes.activity_detail,
        scenario,
        SUPPLIER_A,
        fields={"atividade": str(activity.id)},
    )
    other = _call(
        routes.activity_detail,
        scenario,
        SUPPLIER_B,
        fields={"atividade": str(activity.id)},
    )

    assert own.status_code == 200
    assert "Dia a dia" in _body(own)
    assert other.status_code == 403
