"""Routes of the configuration of the schedule: the screen, the 403, the toast and the Portfólio (ISSUE-054)."""

from __future__ import annotations

import html
from collections.abc import Callable
from urllib.parse import unquote

import azure.functions as func
import pytest

from src.core.rbac import ScheduleRole
from src.modulos.programacao_semanal import repository, routes, service
from tests.cenario_programacao import WEEK, Scenario, make_user
from tests.identidades import requisicao

pytestmark = pytest.mark.usefixtures("sessao_das_rotas")

PLANNER = "ps-plan@example.invalid"
SUPPLIER_A = "ps-forn-a@example.invalid"
VIEWER = "ps-view@example.invalid"
OTHER_PLANNER = "cfg-plan-outro@example.invalid"
BASE = "/api/programacao-semanal/configuracoes"


def _body(response: func.HttpResponse) -> str:
    return html.unescape(response.get_body().decode())


def _toast(response: func.HttpResponse) -> str:
    return unquote(response.headers.get("X-TN-Toast", ""))


def _call(
    route: Callable[[func.HttpRequest], func.HttpResponse],
    email: str,
    *,
    project: int | None,
    method: str = "GET",
    fields: dict[str, str] | None = None,
) -> func.HttpResponse:
    return route(
        requisicao(
            BASE,
            metodo=method,
            email=email,
            alvo="config-area",
            params={"projeto": str(project)} if project is not None else {},
            corpo=fields,
        )
    )


@pytest.fixture
def other_planner(scenario: Scenario) -> None:
    make_user(
        scenario.session,
        email=OTHER_PLANNER,
        project_id=scenario.other_project_id,
        role=ScheduleRole.PLANNER,
    )


def test_the_planner_opens_the_screen_with_the_forms(scenario: Scenario) -> None:
    response = _call(routes.configuration_screen, PLANNER, project=scenario.project_id)

    body = _body(response)
    assert response.status_code == 200
    assert 'id="config-area"' in body
    assert "Salvar os parâmetros" in body
    assert "Salvar a janela de Empresa A" in body
    assert "Fechada agora" in body or "Aberta agora" in body


def test_the_viewer_reads_without_the_buttons_of_saving(scenario: Scenario) -> None:
    response = _call(routes.configuration_screen, VIEWER, project=scenario.project_id)

    body = _body(response)
    assert response.status_code == 200
    assert "Somente o planejador do projeto ou o administrador altera" in body
    assert "Salvar os parâmetros" not in body
    assert "Salvar a janela" not in body


def test_a_supplier_sees_only_its_own_company(scenario: Scenario) -> None:
    body = _body(_call(routes.configuration_screen, SUPPLIER_A, project=scenario.project_id))

    assert "Empresa A" in body
    assert "Empresa B" not in body


@pytest.mark.usefixtures("scenario")
def test_in_the_portfolio_the_screen_is_read_only_and_asks_for_a_project() -> None:
    response = _call(routes.configuration_screen, PLANNER, project=None)

    body = _body(response)
    assert response.status_code == 200
    assert "Escolher um projeto" in body
    assert "PS-1 · Projeto da programação" in body
    assert "PS-2 · Outro projeto" in body
    assert "Salvar os parâmetros" not in body


def test_the_planner_saves_the_parameters_and_the_next_request_reads_them(
    scenario: Scenario,
) -> None:
    fields = {
        "meta_aderencia": "52",
        "meta_ppc": "81",
        "semana_referencia": WEEK,
        "exige_justificativa_desvio": "sim",
        "limite_desvio_justificativa": "18",
        "versao": "",
    }

    response = _call(
        routes.save_parameters, PLANNER, project=scenario.project_id, method="POST", fields=fields
    )

    assert response.status_code == 200
    assert _toast(response) == "Parâmetros salvos."
    parameters = service.parameters_of(scenario.session, scenario.project_id)
    assert (parameters.adherence_target, parameters.ppc_target) == (52.0, 81.0)
    assert parameters.reference_week == WEEK
    assert 'value="52"' in _body(response)


@pytest.mark.usefixtures("other_planner")
def test_the_planner_of_another_project_gets_403_on_both_saves(scenario: Scenario) -> None:
    parameters = _call(
        routes.save_parameters,
        OTHER_PLANNER,
        project=scenario.project_id,
        method="POST",
        fields={"meta_ppc": "10"},
    )
    window = _call(
        routes.save_window,
        OTHER_PLANNER,
        project=scenario.project_id,
        method="POST",
        fields={"empresa": str(scenario.company_a)},
    )

    assert parameters.status_code == 403
    assert window.status_code == 403
    assert service.parameters_of(scenario.session, scenario.project_id).ppc_target == 75.0


def test_a_number_out_of_range_is_422_and_saves_nothing(scenario: Scenario) -> None:
    response = _call(
        routes.save_parameters,
        PLANNER,
        project=scenario.project_id,
        method="POST",
        fields={"meta_ppc": "101"},
    )

    assert response.status_code == 422
    assert repository.settings_of(scenario.session, scenario.project_id) is None


@pytest.mark.usefixtures("scenario")
def test_saving_in_the_portfolio_is_422() -> None:
    response = _call(
        routes.save_parameters, PLANNER, project=None, method="POST", fields={"meta_ppc": "70"}
    )

    assert response.status_code == 422


def test_the_planner_saves_a_window_with_the_ticked_weeks(scenario: Scenario) -> None:
    version = repository.windows_by_company(scenario.session, project_id=scenario.project_id)[
        scenario.company_a
    ].version
    fields = {
        "empresa": str(scenario.company_a),
        "versao": str(version),
        "dia_2": "1",
        "abre_2": "06:30",
        "fecha_2": "11:00",
        "semanas": f"{WEEK},S.32/2026",
    }

    response = _call(
        routes.save_window, PLANNER, project=scenario.project_id, method="POST", fields=fields
    )

    assert response.status_code == 200
    assert _toast(response) == "Janela de Empresa A atualizada."
    window = repository.window_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert window is not None
    assert window.weeks == frozenset({WEEK, "S.32/2026"})
    assert [day.weekday for day in window.days] == [2]


def test_a_stale_window_version_is_409(scenario: Scenario) -> None:
    fields = {"empresa": str(scenario.company_a), "versao": "99", "semanas": WEEK}

    response = _call(
        routes.save_window, PLANNER, project=scenario.project_id, method="POST", fields=fields
    )

    assert response.status_code == 409
