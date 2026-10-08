"""A fachada do dashboard: indicadores, filtros, horizonte e o recorte do fornecedor (ISSUE-056)."""

from __future__ import annotations

from src.core import calendario
from src.modulos.programacao_semanal import calculations, export, screen, service
from src.modulos.programacao_semanal.service import Filters, NewActivity
from tests.cenario_programacao import WEEK, Scenario

PREVIOUS_WEEK = "S.30/2026"


def _store(
    scenario: Scenario,
    unique_id: str,
    *,
    week: str = WEEK,
    planned: float = 70.0,
    done: float = 70.0,
    night: float = 0.0,
    company_id: int | None = None,
    location_id: int | None = None,
    foreman_id: int | None = None,
    project_id: int | None = None,
    situation: str = calculations.SITUATION_PUBLISHED,
    approval: str = calculations.APPROVAL_APPROVED,
) -> None:
    service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=project_id or scenario.project_id,
            company_id=company_id or scenario.company_a,
            week=week,
            unique_id=unique_id,
            item=1,
            description=f"Serviço {unique_id}",
            planned_headline=planned,
            author_person_id=scenario.planner.person_id,
            at=calendario.now(),
            location_id=location_id or scenario.location_id,
            unit_id=scenario.unit_id,
            foreman_id=foreman_id or scenario.foreman_a,
            inspector_id=scenario.fiscal.person_id,
            planned_days=(planned / calculations.DAYS,) * calculations.DAYS,
            day_shift=(done / calculations.DAYS,) * calculations.DAYS,
            night_shift=(night / calculations.DAYS,) * calculations.DAYS,
            situation=situation,
            approval=approval,
            approved_at=calendario.now() if approval == calculations.APPROVAL_APPROVED else None,
        ),
    )


def _data(
    scenario: Scenario,
    *,
    filters: Filters | None = None,
    user=None,
    week: str = WEEK,
    project: bool = True,
) -> service.DashboardData:
    return service.dashboard_data(
        scenario.session,
        caller=scenario.caller(user or scenario.planner, project=project),
        week=week,
        filters=filters,
    )


# ── Os indicadores ───────────────────────────────────────────────────────


def test_o_painel_traz_os_indicadores_do_app(scenario: Scenario) -> None:
    _store(scenario, "A-1", planned=70.0, done=70.0)
    _store(scenario, "A-2", planned=140.0, done=70.0)

    data = _data(scenario)

    assert (data.summary.total, data.companies, data.locations) == (2, 1, 1)
    assert data.summary.adherence == 66.67
    assert data.summary.mean_ppc == 75.0
    assert data.parameters.adherence_target == 60.0
    assert data.parameters.ppc_target == 75.0

    assert [line.label for line in data.by_company] == ["Empresa A"]
    assert data.by_company[0].adherence == 66.67
    assert data.by_company[0].pending == 0
    assert [segment.value for segment in data.status[0].segments] == [2, 0, 0]
    assert [segment.value for segment in data.status[2].segments] == [1, 0, 1]


def test_o_horizonte_le_a_semana_e_as_doze_anteriores(scenario: Scenario) -> None:
    _store(scenario, "ANT-1", week=PREVIOUS_WEEK, planned=70.0, done=35.0)
    _store(scenario, "ATU-1", week=WEEK, planned=70.0, done=70.0)

    data = _data(scenario)

    assert [point.week for point in data.curve] == [PREVIOUS_WEEK, WEEK]
    assert data.curve[0].planned == 50.0
    assert [point.week for point in data.evolution.points] == [PREVIOUS_WEEK, WEEK]


def test_os_filtros_recortam_o_painel_e_a_evolucao(scenario: Scenario) -> None:
    _store(scenario, "A-1")
    _store(scenario, "B-1", company_id=scenario.company_b, foreman_id=scenario.foreman_b)

    data = _data(scenario, filters=Filters(company_id=scenario.company_b))

    assert data.summary.total == 1
    assert [line.label for line in data.by_company] == ["Empresa B"]
    assert data.evolution.series == ("Empresa B",)
    assert data.week_total == 2


def test_os_gargalos_e_o_heatmap_saem_da_semana(scenario: Scenario) -> None:
    _store(scenario, "PARADO", planned=70.0, done=0.0)

    data = _data(scenario)

    assert [item.identity for item in data.bottlenecks] == ["PARADO"]
    assert data.bottlenecks[0].idle_days == calculations.DAYS
    assert data.heatmap.columns == calculations.DAY_LABELS
    assert data.heatmap.rows[0].label == "Frente 1"
    assert data.heatmap.rows[0].cells[0].percent == 0.0


def test_os_turnos_saem_da_semana(scenario: Scenario) -> None:
    _store(scenario, "T-1", planned=70.0, done=42.0, night=14.0)

    data = _data(scenario)

    assert data.shifts[0].day_shift == 6.0
    assert data.shifts[0].night_shift == 2.0
    assert data.shifts[0].done == 8.0


# ── O drill da aderência ─────────────────────────────────────────────────


def test_o_drill_da_aderencia_manda_o_par_de_cada_semana(scenario: Scenario) -> None:
    """O drill agrega taxa por numerador e denominador, nunca pela média das taxas.

    Duas semanas de tamanhos bem diferentes: a média das aderências semanais daria
    75%, e a aderência do período — a soma do realizado pela soma do previsto — dá
    55%. O gráfico só consegue acertar porque cada semana viaja como par (num, den),
    e o mês fechado soma os numeradores e os denominadores antes de dividir.
    """
    _store(scenario, "SEM-1", week=PREVIOUS_WEEK, planned=70.0, done=70.0)
    _store(scenario, "SEM-2", week=WEEK, planned=630.0, done=315.0)

    chart = export.adherence_chart(_data(scenario))
    series = chart.data["series"]
    periodos = chart.data["periodos"]

    assert [serie["id"] for serie in series] == ["serie-1", "meta"]
    assert series[0]["tipo"] == "razao"
    assert series[0]["rotulo"] == "Empresa A"
    assert series[1]["tipo"] == "razao"
    assert series[1]["papel"] == "linha-base"

    primeiro, segundo = periodos
    assert primeiro["valores"]["serie-1"] == {"num": 70.0, "den": 70.0}
    assert segundo["valores"]["serie-1"] == {"num": 315.0, "den": 630.0}
    assert primeiro["valores"]["meta"] == {"num": 60.0, "den": 100.0}

    # A conta do drill, mês fechado: soma o numerador e o denominador e divide uma vez.
    soma_num = primeiro["valores"]["serie-1"]["num"] + segundo["valores"]["serie-1"]["num"]
    soma_den = primeiro["valores"]["serie-1"]["den"] + segundo["valores"]["serie-1"]["den"]
    assert round(soma_num / soma_den * 100, 1) == 55.0
    assert round((100 + 50) / 2, 1) == 75.0  # a média, que seria a errada


def test_os_outros_graficos_mandam_quantidade(scenario: Scenario) -> None:
    """A curva e as barras falam em pontos percentuais do escopo do horizonte, como o app.

    Uma atividade que entregou metade do escopo marca 50% no realizado e 100% no
    previsto — o peso é igual por atividade e o denominador é o escopo dela no
    horizonte, nunca a quantidade bruta da semana.
    """
    _store(scenario, "A-1", planned=70.0, done=35.0)

    data = _data(scenario)
    weekly = export.weekly_chart(data)
    curve = export.curve_chart(data)

    assert weekly.kind == "curva-s-barra-linha"
    assert weekly.data["modo"] == "periodo"
    assert weekly.data["periodos"][0]["valores"] == {"previsto": 100.0, "realizado": 50.0}
    assert curve.kind == "curva-s-linha"
    assert curve.data["modo"] == "acumulado"
    assert curve.data["periodos"][0]["valores"]["realizado"] == 50.0


# ── O recorte do fornecedor e os vazios ──────────────────────────────────


def test_o_fornecedor_ve_o_dashboard_so_da_propria_empresa(scenario: Scenario) -> None:
    _store(scenario, "A-1")
    _store(scenario, "B-1", company_id=scenario.company_b, foreman_id=scenario.foreman_b)

    data = _data(scenario, user=scenario.supplier_a)

    assert data.week_total == 1
    assert data.summary.total == 1
    assert [line.label for line in data.by_company] == ["Empresa A"]
    assert data.evolution.series == ("Empresa A",)
    assert all("Empresa B" not in point.totals for point in data.evolution.points)


def test_o_portfolio_le_o_dashboard_de_todos_os_projetos(scenario: Scenario) -> None:
    _store(scenario, "A-1")
    _store(
        scenario,
        "B-1",
        project_id=scenario.other_project_id,
        company_id=scenario.company_b,
        foreman_id=scenario.foreman_b,
    )

    data = _data(scenario, project=False)

    assert data.summary.total == 2
    assert [line.label for line in data.by_company] == ["Empresa A", "Empresa B"]
    assert data.week_total == 2


def test_a_semana_vazia_e_o_filtro_vazio_nao_sao_o_mesmo_estado(scenario: Scenario) -> None:
    vazia = screen.dashboard_context(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        params={"semana": PREVIOUS_WEEK},
    )
    assert vazia["situacao"] == "vazio-origem"

    _store(scenario, "A-1")
    filtrado = screen.dashboard_context(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        params={"semana": WEEK, "empresa": str(scenario.company_b)},
    )
    assert filtrado["situacao"] == "vazio-filtro"

    conteudo = screen.dashboard_context(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        params={"semana": WEEK},
    )
    assert conteudo["situacao"] == "conteudo"
    assert conteudo["semana"] == WEEK
    assert conteudo["excel_url"].startswith("/api/programacao-semanal/dashboard/excel?")
