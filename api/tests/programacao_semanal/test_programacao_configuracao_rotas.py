"""Routes of the configuration: the HTTP of the parameters and the windows (ISSUE-054)."""

from __future__ import annotations

import html

import azure.functions as func
import pytest

from src.modulos.programacao_semanal import repository, routes
from tests.cenario_programacao import WEEK, Scenario
from tests.identidades import criar_colaborador, requisicao

pytestmark = pytest.mark.usefixtures("sessao_das_rotas")

PLANNER = "ps-plan@example.invalid"
FISCAL = "ps-fisc@example.invalid"
SUPPLIER_A = "ps-forn-a@example.invalid"
CONFIG_TARGET = "config-painel"
SETTINGS_TARGET = "config-parametros"
WINDOWS_TARGET = "config-janelas"


def _body(response: func.HttpResponse) -> str:
    return html.unescape(response.get_body().decode())


def _get(scenario: Scenario, email: str, *, project: bool = True) -> dict:
    query = {"projeto": str(scenario.project_id) if project else "portfolio"}
    return {"email": email, "params": query}


def _configuration(scenario: Scenario, email: str, *, project: bool = True) -> func.HttpResponse:
    return routes.configuration(
        requisicao(
            "/api/programacao-semanal/configuracao",
            alvo=CONFIG_TARGET,
            **_get(scenario, email, project=project),
        )
    )


def _settings(scenario: Scenario, email: str, fields: dict[str, str]) -> func.HttpResponse:
    return routes.save_settings(
        requisicao(
            "/api/programacao-semanal/configuracao/parametros",
            metodo="POST",
            alvo=SETTINGS_TARGET,
            corpo=fields,
            **_get(scenario, email),
        )
    )


def _window(scenario: Scenario, email: str, fields: dict) -> func.HttpResponse:
    return routes.save_window(
        requisicao(
            "/api/programacao-semanal/configuracao/janela",
            metodo="POST",
            alvo=WINDOWS_TARGET,
            corpo=fields,
            **_get(scenario, email),
        )
    )


def _settings_fields(**overrides: str) -> dict[str, str]:
    fields = {
        "versao": "",
        "meta_aderencia": "60",
        "meta_ppc": "75",
        "semana_referencia": "",
        "exige_justificativa_desvio": "sim",
        "limite_desvio_justificativa": "15",
    }
    return {**fields, **overrides}


def _window_fields(scenario: Scenario, **overrides: object) -> dict:
    fields: dict = {
        "versao": "",
        "empresa": str(scenario.company_b),
        "dia": "5",
        "abre": "08:00",
        "fecha": "15:00",
        "semanas": [WEEK],
        "extra_semana": "",
        "extra_abre": "",
        "extra_fecha": "",
    }
    return {**fields, **overrides}


# ── O painel ────────────────────────────────────────────────────────────


def test_configuration_has_the_parameters_and_the_windows(scenario: Scenario) -> None:
    response = _configuration(scenario, PLANNER)
    body = _body(response)

    assert response.status_code == 200
    assert 'id="config-painel"' in body
    assert 'id="config-parametros"' in body
    assert 'id="config-janelas"' in body
    for field in ("meta_aderencia", "meta_ppc", "semana_referencia", "limite_desvio_justificativa"):
        assert f'name="{field}"' in body
    assert "Empresa A" in body
    assert "Empresa B" in body
    assert 'name="semanas"' in body
    assert 'name="extra_semana"' in body


def test_configuration_in_the_portfolio_asks_for_a_project(scenario: Scenario) -> None:
    response = _configuration(scenario, PLANNER, project=False)
    body = _body(response)

    assert response.status_code == 200
    assert "Escolha um projeto" in body
    assert "config-parametros" not in body
    assert 'name="meta_aderencia"' not in body


def test_supplier_configuration_is_read_only_and_shows_its_company(scenario: Scenario) -> None:
    response = _configuration(scenario, SUPPLIER_A)
    body = _body(response)

    assert response.status_code == 200
    assert "Empresa A" in body
    assert "Empresa B" not in body
    assert "Salvar parâmetros" not in body
    assert "Salvar a janela de Empresa A" not in body


# ── Os parâmetros ───────────────────────────────────────────────────────


def test_saving_the_parameters_is_effective_and_toasts(scenario: Scenario) -> None:
    response = _settings(scenario, PLANNER, _settings_fields(meta_aderencia="80"))
    body = _body(response)

    assert response.status_code == 200
    assert 'id="config-parametros"' in body
    assert 'value="80"' in body
    assert response.headers.get("X-TN-Toast")
    configuration = repository.settings_of(scenario.session, scenario.project_id)
    assert configuration is not None and configuration.adherence_target == 80.0


def test_invalid_parameters_come_back_filled_with_422(scenario: Scenario) -> None:
    response = _settings(
        scenario,
        PLANNER,
        _settings_fields(meta_aderencia="150", semana_referencia="S.99/2026"),
    )
    body = _body(response)

    assert response.status_code == 422
    assert 'value="150"' in body
    assert "Informe a meta de aderência entre 0 e 100." in body
    assert "Informe uma semana válida" in body
    assert repository.settings_of(scenario.session, scenario.project_id) is None


def test_a_non_planner_gets_403_on_the_parameters(scenario: Scenario) -> None:
    response = _settings(scenario, FISCAL, _settings_fields(meta_aderencia="80"))
    body = _body(response)

    assert response.status_code == 403
    assert "Planejador" in body
    assert repository.settings_of(scenario.session, scenario.project_id) is None


def test_the_planner_of_another_project_gets_403(scenario: Scenario) -> None:
    criar_colaborador(
        scenario.session,
        email="ps-fora@example.invalid",
        papeis=[(scenario.other_project_id, "Planejador")],
    )

    response = _settings(scenario, "ps-fora@example.invalid", _settings_fields(meta_aderencia="80"))

    assert response.status_code == 403
    assert repository.settings_of(scenario.session, scenario.project_id) is None


def test_the_supplier_does_not_save_the_parameters(scenario: Scenario) -> None:
    response = _settings(scenario, SUPPLIER_A, _settings_fields(meta_aderencia="80"))

    assert response.status_code == 403


# ── As janelas ──────────────────────────────────────────────────────────


def test_saving_a_window_creates_it_and_toasts(scenario: Scenario) -> None:
    response = _window(scenario, PLANNER, _window_fields(scenario))
    body = _body(response)

    assert response.status_code == 200
    assert 'id="config-janelas"' in body
    assert response.headers.get("X-TN-Toast")
    assert 'value="S.31/2026"' in body
    assert "checked" in body
    row = repository.window_row_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_b
    )
    assert row is not None
    window = repository.window_of_row(scenario.session, row)
    assert window.weeks == frozenset({WEEK})


def test_the_window_error_comes_back_in_the_card_with_422(scenario: Scenario) -> None:
    response = _window(
        scenario,
        PLANNER,
        _window_fields(scenario, abre="25:00", fecha="", semanas=["S.99/2026"]),
    )
    body = _body(response)

    assert response.status_code == 422
    assert 'id="config-janelas"' in body
    assert "Informe um horário válido" in body
    assert "S.99/2026" in body
    assert (
        repository.window_row_of(
            scenario.session, project_id=scenario.project_id, company_id=scenario.company_b
        )
        is None
    )


def test_a_stale_window_version_is_409(scenario: Scenario) -> None:
    _window(scenario, PLANNER, _window_fields(scenario))

    response = _window(scenario, PLANNER, _window_fields(scenario, versao="0"))
    body = _body(response)

    assert response.status_code == 409
    assert 'id="config-janelas"' in body
    assert "alterado por" in body


def test_the_supplier_does_not_save_a_window(scenario: Scenario) -> None:
    response = _window(scenario, SUPPLIER_A, _window_fields(scenario))

    assert response.status_code == 403


def test_the_admin_edits_the_window_of_the_project(scenario: Scenario) -> None:
    row = repository.window_row_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert row is not None

    response = _window(
        scenario,
        "ps-admin@example.invalid",
        _window_fields(scenario, empresa=str(scenario.company_a), versao=str(row.version)),
    )

    assert response.status_code == 200
    assert "Empresa A" in _body(response)
