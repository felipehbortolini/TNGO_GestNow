"""Afirmações do oráculo para a EAP (ISSUE-036): números do protótipo em 25/09/2026.

Fonte: ``mock-planejamento`` (coleções ``eap``, ``eapRevisoes`` e ``eapDesdobramentos``) e as
regras de ``regras.js`` (``avancoPacoteEap``, ``faixaDesvioFisico``) e de ``api.js``
(``eapArvoreDe``, ``eapCarteira``), calculadas com um script descartável sobre o mock. O projeto 1
tem 38 pacotes (37 de trabalho e 1 de planejamento, 5.2.1 com 1,2 %), Rev 2 vigente (Rev 1 pela
SM-TN-2026-0001 e Rev 2 pela SM-TN-2026-0002), um desdobramento (5.2.1 > 5.2.2) e dois pacotes com
término vencido (2.1.1 e 3.2.1); previsto 65,7 % e real 61,8 % em set/26. Os pesos da carteira são
55,36 / 29,34 / 15,30 (os mesmos da EAC). Nenhuma divergência: o real calculado pelas medições da
carga é o real que o protótipo calculava pelas entradas do critério.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from src.modulos.planejamento import eap_calculations as calc
from src.modulos.planejamento import eap_service as service
from src.modulos.planejamento.models import EapItem, EapMeasurement
from tests.oraculo import OracleContext, harness, register_check

D = Decimal
PROJECT_CODES = ("TN-2026-014", "TN-2026-021", "TN-2026-027")
# previsto, real, desvio (p.p.), faixa, pacotes de trabalho, de planejamento, áreas, subáreas,
# pacotes vencidos, pacotes com desvio fora da faixa
BY_PROJECT = {
    "TN-2026-014": (D("65.70"), D("61.80"), D("-3.9"), calc.WARNING, 37, 1, 5, 13, 2, 11),
    "TN-2026-021": (D("35.96"), D("32.23"), D("-3.7"), calc.WARNING, 16, 1, 5, 8, 0, 2),
    "TN-2026-027": (D("33.15"), D("34.14"), D("1.0"), calc.OK, 13, 0, 5, 6, 0, 1),
}
# peso, previsto, real, desvio, faixa de cada área (o avanço por área da tela)
AREAS = {
    "TN-2026-014": (
        (D(15), D(98), D(96), D("-2.0"), calc.OK),
        (D(30), D(80), D(78), D("-2.0"), calc.OK),
        (D(25), D(70), D(66), D("-4.0"), calc.WARNING),
        (D(25), D(38), D(30), D("-8.0"), calc.DANGER),
        (D(5), D(0), D(0), D("0.0"), calc.OK),
    ),
    "TN-2026-021": (
        (D(12), D("97.92"), D("96.25"), D("-1.7"), calc.OK),
        (D(40), D("42.77"), D("35.65"), D("-7.1"), calc.DANGER),
        (D(18), D("36.11"), D("32.35"), D("-3.8"), calc.WARNING),
        (D(25), D("2.40"), D("2.38"), D("0.0"), calc.OK),
        (D(5), D(0), D(0), D("0.0"), calc.OK),
    ),
    "TN-2026-027": (
        (D(10), D("95.50"), D("96.40"), D("0.9"), calc.OK),
        (D(45), D("36.89"), D("37.71"), D("0.8"), calc.OK),
        (D(25), D(28), D("30.12"), D("2.1"), calc.OK),
        (D(15), D(0), D(0), D("0.0"), calc.OK),
        (D(5), D(0), D(0), D("0.0"), calc.OK),
    ),
}
PROJECT_WEIGHTS = (D("55.36"), D("29.34"), D("15.30"))
# pacotes principais da carteira: o peso de cada área vezes o do projeto
PORTFOLIO_AREA_WEIGHTS = {
    "1.1": D("8.30"), "1.2": D("16.61"), "1.3": D("13.84"), "1.4": D("13.84"), "1.5": D("2.77"),
    "2.1": D("3.52"), "2.2": D("11.74"), "2.3": D("5.28"), "2.4": D("7.34"), "2.5": D("1.47"),
    "3.1": D("1.53"), "3.2": D("6.89"), "3.3": D("3.83"), "3.4": D("2.30"), "3.5": D("0.77"),
}  # fmt: skip
PORTFOLIO = (D("51.99"), D("48.89"), D("-3.1"), calc.WARNING)
PORTFOLIO_COUNTS = (
    66,
    2,
    15,
    2,
    14,
)  # trabalho, planejamento, pacotes principais, vencidos, fora da faixa
PACKAGES_BY_PROJECT = (38, 17, 13)
REVISION_PACKAGES = (37, 17, 13)  # pacotes com peso congelado na revisão vigente


def _viewer() -> User:
    return User(
        id=0,
        person_id=0,
        name="Oráculo",
        email="oraculo@example.invalid",
        general_profile=GeneralProfile.ADMIN,
        bond=Bond.TIMENOW,
    )


def _projects(context: OracleContext) -> list[Project]:
    return [
        context.session.scalars(select(Project).where(Project.code == code)).one()
        for code in PROJECT_CODES
    ]


def _view(context: OracleContext, project_id: int | None) -> service.EapView:
    return service.eap_view(
        context.session,
        user=_viewer(),
        scope=Scope(project_id=project_id, source="url"),
        filters=service.EapFilters(),
        reference_date=context.reference_date,
    )


def _afirmar_o_avanco_dos_projetos(context: OracleContext) -> None:
    for project in _projects(context):
        view = _view(context, project.id)
        summary = view.summary
        previsto, real, desvio, faixa, work, planning, areas, subareas, overdue, behind = (
            BY_PROJECT[project.code]
        )
        got = (
            summary.planned,
            summary.real,
            summary.deviation,
            summary.band,
            summary.work_count,
            summary.planning_count,
            summary.area_count,
            summary.subarea_count,
            summary.overdue_count,
            summary.behind_count,
        )
        assert got == (
            previsto,
            real,
            desvio,
            faixa,
            work,
            planning,
            areas,
            subareas,
            overdue,
            behind,
        ), f"avanço da EAP de {project.code}"
        assert view.weight_rule_holds, f"regra dos 100% em {project.code}"


def _afirmar_as_areas(context: OracleContext) -> None:
    for project in _projects(context):
        rows = [row for row in _view(context, project.id).rows if row.level == 1]
        got = tuple((row.weight, row.planned, row.real, row.deviation, row.band) for row in rows)
        assert got == AREAS[project.code], f"avanço por área de {project.code}"


def _afirmar_os_pacotes_vencidos_e_a_regra_dos_100(context: OracleContext) -> None:
    first = _projects(context)[0]
    view = _view(context, first.id)
    overdue = [row.code for row in view.rows if row.level == 3 and row.is_overdue]
    assert overdue == ["2.1.1", "3.2.1"], "os dois pacotes com término vencido"
    planning = [row for row in view.rows if row.level == 3 and not row.is_work]
    assert [(row.code, row.weight) for row in planning] == [("5.2.1", D("1.20"))]
    assert view.summary.planning_weight == D("1.20")
    root = view.rows[0]
    assert (root.weight, root.start_date is not None, root.end_date is not None) == (
        D(100),
        True,
        True,
    )


def _afirmar_a_revisao_vigente_e_o_desdobramento(context: OracleContext) -> None:
    first, second, third = _projects(context)
    view = _view(context, first.id)
    current = view.current_revision
    assert current is not None
    assert (current.number, current.change_code) == (2, "SM-TN-2026-0002"), "Rev 2 vigente"
    by_number = {item.number: item for item in view.revisions}
    assert by_number[1].change_code == "SM-TN-2026-0001"
    assert by_number[0].change == "Linha de base"
    assert len(view.splits) == 1
    split = view.splits[0]
    assert split.source.startswith("5.2.1 ")
    assert split.target.startswith("5.2.2 ")
    assert split.weight == D("0.8")
    counts = [
        _view(context, project.id).current_revision.package_count  # type: ignore[union-attr]
        for project in (first, second, third)
    ]
    assert tuple(counts) == REVISION_PACKAGES, "pacotes na revisão vigente de cada projeto"


def _afirmar_a_carteira(context: OracleContext) -> None:
    view = _view(context, None)
    root = view.rows[0]
    assert (root.planned, root.real, root.deviation, root.band) == PORTFOLIO, "avanço da carteira"
    assert root.weight == D(100)
    projects = [row for row in view.rows if row.level == 1]
    assert [row.weight for row in projects] == list(PROJECT_WEIGHTS), "pesos da carteira"
    areas = {row.code: row.weight for row in view.rows if row.level == 2}
    assert areas == PORTFOLIO_AREA_WEIGHTS, "peso dos pacotes principais na carteira"
    summary = view.summary
    got = (
        summary.work_count,
        summary.planning_count,
        summary.area_count,
        summary.overdue_count,
        summary.behind_count,
    )
    assert got == PORTFOLIO_COUNTS, "indicadores da carteira"
    assert [item.number for item in view.revisions] == [2, 0, 0], "revisão vigente por projeto"


def _afirmar_a_carga(context: OracleContext) -> None:
    session = context.session
    for project, expected in zip(_projects(context), PACKAGES_BY_PROJECT, strict=True):
        count = session.scalar(
            select(func.count())
            .select_from(EapItem)
            .where(EapItem.project_id == project.id, EapItem.level == 3)
        )
        assert count == expected, f"pacotes da EAP de {project.code}"
    total = session.scalar(select(func.count()).select_from(EapItem))
    assert total == 110, "itens da EAP do mock"
    measured = session.scalar(select(func.count(func.distinct(EapMeasurement.item_id))))
    assert measured and measured > 0


register_check("EAP: avanço dos projetos", _afirmar_o_avanco_dos_projetos)
register_check("EAP: avanço por área", _afirmar_as_areas)
register_check(
    "EAP: pacotes vencidos e planejamento", _afirmar_os_pacotes_vencidos_e_a_regra_dos_100
)
register_check("EAP: revisão vigente e desdobramento", _afirmar_a_revisao_vigente_e_o_desdobramento)
register_check("EAP: carteira", _afirmar_a_carteira)
register_check("EAP: carga", _afirmar_a_carga)


def test_a_demonstracao_traz_a_eap_do_prototipo(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    for check in (
        _afirmar_a_carga,
        _afirmar_o_avanco_dos_projetos,
        _afirmar_as_areas,
        _afirmar_os_pacotes_vencidos_e_a_regra_dos_100,
        _afirmar_a_revisao_vigente_e_o_desdobramento,
        _afirmar_a_carteira,
    ):
        check(context)
