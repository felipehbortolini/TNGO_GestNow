"""Routes of the matrix: the HTTP seam of the cut by company, the window and the Portfólio."""

from __future__ import annotations

import html

import azure.functions as func
import pytest

from src.core.routing import ACCESS_ATTRIBUTE
from src.modulos.programacao_semanal import routes
from tests.cenario_programacao import SATURDAY_MORNING, WEEK, Scenario
from tests.identidades import requisicao

pytestmark = pytest.mark.usefixtures("sessao_das_rotas")

MATRIX_TARGETS = "prog-resumo prog-tabela"
DRAWER_TARGETS = "drawer prog-resumo prog-tabela"
PLANNER = "ps-plan@example.invalid"
SUPPLIER_A = "ps-forn-a@example.invalid"


def _body(response: func.HttpResponse) -> str:
    return html.unescape(response.get_body().decode())


def _get(scenario: Scenario, email: str, *, project: bool = True, **params: str) -> dict:
    query = {"semana": WEEK, "projeto": str(scenario.project_id) if project else "portfolio"}
    return {"email": email, "params": {**query, **params}}


def _fields(scenario: Scenario, **overrides: str) -> dict[str, str]:
    fields = {
        "semana": WEEK,
        "atividade_id": "",
        "versao": "",
        "id_exclusiva": "R-1",
        "atividade": "Atividade pela rota",
        "local": str(scenario.location_id),
        "empresa": str(scenario.company_a),
        "encarregado": str(scenario.foreman_a),
        "responsavel": "",
        "unidade": str(scenario.unit_id),
        "prod_prevista": "70",
        **{f"dias_previsto_{index}": "10" for index in range(7)},
    }
    return {**fields, **overrides}


def _save(scenario: Scenario, email: str, fields: dict[str, str]) -> func.HttpResponse:
    return routes.save_activity(
        requisicao(
            "/api/programacao-semanal/atividades",
            metodo="POST",
            alvo=DRAWER_TARGETS,
            corpo=fields,
            **_get(scenario, email),
        )
    )


def _matrix(scenario: Scenario, email: str, **kwargs) -> func.HttpResponse:
    return routes.matrix(
        requisicao(
            "/api/programacao-semanal/programacoes",
            alvo=MATRIX_TARGETS,
            **_get(scenario, email, **kwargs),
        )
    )


def test_matrix_has_the_columns_and_the_grid_of_days_of_the_app(scenario: Scenario) -> None:
    _save(scenario, PLANNER, _fields(scenario))

    response = _matrix(scenario, PLANNER)
    body = _body(response)

    assert response.status_code == 200
    assert 'id="prog-resumo"' in body
    assert 'id="prog-tabela"' in body
    for header in ("#", "Atividade", "Execução", "Situação", "Semana", "PPC", "Ações"):
        assert header in body
    for label in ("2ª", "3ª", "4ª", "5ª", "6ª", "Sáb", "Dom"):
        assert f">{label}<" in body
    assert "Atividade pela rota" in body
    assert body.count("dia dia--prev") == 7


def test_supplier_matrix_never_shows_another_company(scenario: Scenario) -> None:
    _save(scenario, PLANNER, _fields(scenario, id_exclusiva="A-1", atividade="Serviço da A"))
    _save(
        scenario,
        PLANNER,
        _fields(
            scenario,
            id_exclusiva="B-1",
            atividade="Serviço da B",
            empresa=str(scenario.company_b),
            encarregado=str(scenario.foreman_b),
        ),
    )

    body = _body(_matrix(scenario, SUPPLIER_A))

    assert "Serviço da A" in body
    assert "Serviço da B" not in body


def test_supplier_cannot_filter_its_way_to_another_company(scenario: Scenario) -> None:
    _save(
        scenario,
        PLANNER,
        _fields(
            scenario,
            atividade="Serviço da B",
            empresa=str(scenario.company_b),
            encarregado=str(scenario.foreman_b),
        ),
    )

    body = _body(_matrix(scenario, SUPPLIER_A, empresa=str(scenario.company_b)))

    assert "Serviço da B" not in body


def test_supplier_saving_for_another_company_is_403(scenario: Scenario) -> None:
    response = _save(
        scenario,
        SUPPLIER_A,
        _fields(scenario, empresa=str(scenario.company_b), encarregado=str(scenario.foreman_b)),
    )

    assert response.status_code == 403


def test_save_outside_the_window_is_403_with_the_message_of_the_app(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes.calendario, "now", lambda: SATURDAY_MORNING)

    response = _save(scenario, SUPPLIER_A, _fields(scenario))

    assert response.status_code == 403
    assert "Hoje não é dia de programar" in _body(response)


def test_save_in_the_portfolio_asks_for_a_project(scenario: Scenario) -> None:
    response = routes.save_activity(
        requisicao(
            "/api/programacao-semanal/atividades",
            metodo="POST",
            alvo=DRAWER_TARGETS,
            corpo=_fields(scenario),
            **_get(scenario, PLANNER, project=False),
        )
    )

    assert response.status_code == 422
    assert "projeto" in _body(response)


def test_portfolio_matrix_is_read_only(scenario: Scenario) -> None:
    _save(scenario, PLANNER, _fields(scenario))

    response = _matrix(scenario, PLANNER, projeto="portfolio")
    body = _body(response)

    assert response.status_code == 200
    assert "Atividade pela rota" in body
    assert ">Editar<" not in body
    assert ">Excluir<" not in body


def test_invalid_save_gives_the_form_back_filled_with_422(scenario: Scenario) -> None:
    response = _save(scenario, PLANNER, _fields(scenario, prod_prevista="500", id_exclusiva=""))

    body = _body(response)
    assert response.status_code == 422
    assert 'id="drawer"' in body
    assert 'value="500"' in body or "prevista: 500" in body
    assert "Informe a ID exclusiva." in body
    assert "A soma dos dias" in body


def test_valid_save_redraws_the_matrix_and_closes_the_drawer(scenario: Scenario) -> None:
    response = _save(scenario, PLANNER, _fields(scenario))

    body = _body(response)
    assert response.status_code == 200
    assert 'id="drawer"' in body
    assert 'id="prog-tabela"' in body
    assert "Atividade pela rota" in body
    assert response.headers.get("X-TN-Toast")


def test_form_has_the_seven_days_and_the_version(scenario: Scenario) -> None:
    response = routes.activity_form(
        requisicao(
            "/api/programacao-semanal/atividades/formulario",
            alvo="drawer",
            **_get(scenario, PLANNER),
        )
    )

    body = _body(response)
    assert response.status_code == 200
    for index in range(7):
        assert f'name="dias_previsto_{index}"' in body
    assert 'name="versao"' in body
    assert "Nova atividade" in body


def test_banner_tells_the_supplier_when_the_window_is_closed(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes.calendario, "now", lambda: SATURDAY_MORNING)

    response = routes.window_banner(
        requisicao(
            "/api/programacao-semanal/programacoes/janela",
            alvo="prog-janela",
            **_get(scenario, SUPPLIER_A),
        )
    )

    assert "Janela fechada" in _body(response)


def test_every_route_of_the_module_declares_its_access() -> None:
    for handler in (
        routes.matrix,
        routes.toolbar,
        routes.window_banner,
        routes.activity_form,
        routes.save_activity,
        routes.delete_activity,
    ):
        # `bp.route` embala a função do `fragment_route`; o `Access` mora na função de dentro.
        funcao = handler.build().get_user_function()
        access = funcao.__dict__[ACCESS_ATTRIBUTE]
        assert access is not None
        assert access.module == "programacao_semanal"
