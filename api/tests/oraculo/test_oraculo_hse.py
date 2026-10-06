"""Oráculo do HSE (ISSUE-072): o HHT gravado e o histograma de mão de obra do protótipo.

O histograma previsto de ``histogramaMaoDeObra`` é o HHT registrado de cada projeto e mês
ajustado pelo fator da Curva S física (``calculations.histogram_factor``): o oráculo monta a
curva de ``curvaFisica`` e confere as 20 linhas dos projetos 1 a 3. A leitura viva da curva
chega com a ISSUE-039; aqui ela é a do protótipo.
"""

from __future__ import annotations

from src.carga import prototype_collection
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, service
from src.modulos.hse.calculations import CurvePoint
from tests.oraculo import OracleContext, register_check

EXPECTED_POINTS = 20


def _curves_by_project(context: OracleContext) -> dict[int, tuple[CurvePoint, ...]]:
    """A Curva S física de cada projeto, como o protótipo a tinha, por id do banco."""
    codes = {project["id"]: project["codigo"] for project in prototype_collection("projetos")}
    ids = {project.code: project.id for project in configuracoes.list_projects(context.session)}
    curves: dict[int, tuple[CurvePoint, ...]] = {}
    for source in prototype_collection("curvaFisica"):
        points = []
        for label, planned, actual in zip(
            source["meses"], source["baseline"], source["real"], strict=True
        ):
            month = calculations.parse_month(label)
            if month is None:
                continue
            points.append(
                CurvePoint(
                    month=month,
                    planned=float(planned),
                    actual=None if actual is None else float(actual),
                )
            )
        curves[ids[codes[source["projetoId"]]]] = tuple(points)
    return curves


def _afirmar_hht_registrado(context: OracleContext) -> None:
    lines = service.hours_lines(context.session, scope=Scope(project_id=None, source="padrao"))
    total = sum(int(source["hht"]) for source in prototype_collection("hht"))

    assert len(lines) == len(prototype_collection("hht")), "um registro por mes e empresa"
    assert sum((line.hours for line in lines), start=0) == total, "HHT total do prototipo"


def _afirmar_histograma_de_mao_de_obra(context: OracleContext) -> None:
    lines = service.hours_lines(context.session, scope=Scope(project_id=None, source="padrao"))
    points = calculations.labour_histogram(lines, _curves_by_project(context))
    codes = {project["id"]: project["codigo"] for project in prototype_collection("projetos")}
    ids = {project.code: project.id for project in configuracoes.list_projects(context.session)}
    expected = {
        (ids[codes[source["projetoId"]]], calculations.parse_month(source["mes"])): (
            int(source["hhtPrevisto"]),
            int(source["efetivoPrevisto"]),
        )
        for source in prototype_collection("histogramaMaoDeObra")
    }
    got = {
        (point.project_id, point.month): (point.planned_hours, point.planned_headcount)
        for point in points
    }

    assert len(got) == EXPECTED_POINTS, "20 linhas de histograma no prototipo"
    for key, value in expected.items():
        assert got.get(key) == value, f"histograma previsto de {key}"


register_check("hse: hht registrado", _afirmar_hht_registrado)
register_check(
    "hse: histograma de mao de obra do projeto 1 a 3", _afirmar_histograma_de_mao_de_obra
)
