"""Oráculo do HSE (ISSUE-072 e ISSUE-073): o HHT, o histograma de mão de obra e as ocorrências.

O histograma previsto de ``histogramaMaoDeObra`` é o HHT registrado de cada projeto e mês
ajustado pelo fator da Curva S física (``calculations.histogram_factor``): o oráculo monta a
curva de ``curvaFisica`` e confere as 20 linhas dos projetos 1 a 3. A leitura viva da curva
chega com a ISSUE-039; aqui ela é a do protótipo.

A ocorrência (ISSUE-073) é afirmada no projeto 1 em 25/09/2026: as 240 do mock convertido, com
as situações do cenário (o mesmo estado do fluxo que a idade do mock produzia), 63 em aberto, 2
HiPo (1 em aberto), 7 fora do prazo (3 de comunicação e 4 de investigação vencida; divergência
registrada em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``: o mock não guardava o encerramento e o
protótipo contava 8, com o HiPo encerrado marcado como relatório vencido) e a pirâmide por
nível (0, 16, 31 e 190, com 3 ambientais fora dela). A ocorrência HiPo OCR-TN-2026-0219 entra Em
investigação com a investigação registrada e as duas ações da Central do mock.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import func, select

from src.carga import prototype_collection
from src.core.auth import _user_of
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, models, service, validation
from src.modulos.hse.calculations import CurvePoint
from tests.oraculo import OracleContext, register_check

EXPECTED_POINTS = 20
PROJECT_CODE = "TN-2026-014"

# O cenário do projeto 1 em 25/09/2026 (a âncora, sem deslocamento).
EXPECTED_TOTAL = 240
EXPECTED_SITUATIONS = {
    "Encerrada": 177,
    "Em tratamento": 38,
    "Ações definidas": 17,
    "Em investigação": 1,
    "Registrada": 7,
}
EXPECTED_OPEN = 63
EXPECTED_HIPO = 2
EXPECTED_HIPO_OPEN = 1
EXPECTED_OVERDUE = 7
EXPECTED_COMMUNICATION_LATE = 3
EXPECTED_INVESTIGATION_LATE = 4
EXPECTED_PYRAMID = {1: 0, 2: 16, 3: 31, 4: 190}
EXPECTED_ENVIRONMENTAL = 3
EXPECTED_INVESTIGATIONS = 233
EXPECTED_HIPO_OCCURRENCE = "OCR-TN-2026-0219"
EXPECTED_HIPO_ACTIONS = 2


def _project_id(context: OracleContext, code: str) -> int:
    return next(
        project.id
        for project in configuracoes.list_projects(context.session)
        if project.code == code
    )


def _occurrence_screen(context: OracleContext) -> service.OccurrenceScreen:
    return service.occurrences_screen(
        context.session,
        scope=Scope(project_id=_project_id(context, PROJECT_CODE), source="url"),
        filters=validation.OccurrenceFilters(),
        reference_date=context.reference_date,
    )


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


def _afirmar_ocorrencias_do_projeto_1(context: OracleContext) -> None:
    screen = _occurrence_screen(context)
    rows = screen.rows
    summary = screen.summary

    assert screen.universe == EXPECTED_TOTAL, "as 240 ocorrências do mock convertido"
    assert len(rows) == EXPECTED_TOTAL, "sem filtro, a lista inteira"
    assert dict(Counter(row.situation for row in rows)) == EXPECTED_SITUATIONS, (
        "o cenário do mock vira o estado do fluxo"
    )
    assert summary.open_count == EXPECTED_OPEN, "63 não encerradas"
    assert sum(1 for row in rows if row.hipo) == EXPECTED_HIPO, "2 HiPo no mock"
    assert summary.hipo_open == EXPECTED_HIPO_OPEN, "1 HiPo em aberto"

    pyramid = Counter(row.level for row in rows if not row.environmental)
    assert {level: pyramid.get(level, 0) for level in EXPECTED_PYRAMID} == EXPECTED_PYRAMID, (
        "a pirâmide por nível do mock (N1 a N4)"
    )
    assert sum(1 for row in rows if row.environmental) == EXPECTED_ENVIRONMENTAL, (
        "3 ambientais, fora da pirâmide"
    )

    # Fora do prazo: 3 comunicações acima das 24 h gravadas e 4 investigações vencidas (as
    # Registradas de 22/09, com o prazo preliminar de 2 dias). O relatório final não vence em
    # nenhuma: o HiPo encerrado fechou em 20 dias e o HiPo aberto vence em 12/10. O protótipo
    # contava 8 porque o mock não guardava o encerramento (divergência registrada, pendente de
    # aceite); o GestNow grava o encerramento e o relatório entregue no prazo não conta.
    assert summary.overdue == EXPECTED_OVERDUE, "7 fora do prazo no cenário convertido"
    assert sum(1 for row in rows if row.communication_overdue) == EXPECTED_COMMUNICATION_LATE
    assert (
        sum(1 for row in rows if row.investigation_late == "vencido") == EXPECTED_INVESTIGATION_LATE
    )
    assert all(row.report_late is None for row in rows), "nenhum relatório final fora do prazo"

    # O prazo vigente gravado na ocorrência é o do mock-config (24/48/30), não o do parâmetro vivo.
    deadlines = context.session.execute(
        select(
            models.Occurrence.communication_deadline_hours,
            models.Occurrence.investigation_deadline_hours,
            models.Occurrence.report_deadline_days,
        )
        .where(models.Occurrence.project_id == _project_id(context, PROJECT_CODE))
        .distinct()
    ).all()
    assert deadlines == [(24, 48, 30)], "o prazo vigente gravado no registro (D5b)"


def _afirmar_investigacoes_e_acoes_da_ocorrencia(context: OracleContext) -> None:
    session = context.session
    project_id = _project_id(context, PROJECT_CODE)
    investigations = session.scalar(
        select(func.count())
        .select_from(models.OccurrenceInvestigation)
        .join(
            models.Occurrence, models.Occurrence.id == models.OccurrenceInvestigation.occurrence_id
        )
        .where(models.Occurrence.project_id == project_id)
    )
    assert investigations == EXPECTED_INVESTIGATIONS, "tudo o que passou de Registrada investigou"

    row = next(
        line for line in _occurrence_screen(context).rows if line.code == EXPECTED_HIPO_OCCURRENCE
    )
    assert (row.situation, row.hipo) == ("Em investigação", True), "o HiPo de 12/09 do mock"

    sheet = service.occurrence_sheet(
        context.session,
        user=_manager(context),
        code=EXPECTED_HIPO_OCCURRENCE,
        reference_date=context.reference_date,
    )
    assert sheet is not None
    assert sheet.investigation is not None, "a investigação do cenário fixo"
    assert sheet.investigation.method == "Árvore de causas", "o método que o mock guardou"
    assert len(sheet.actions) == EXPECTED_HIPO_ACTIONS, "as duas ações de HSE do mock-central"
    assert {record.origin for record in sheet.actions} == {"HSE"}
    assert {record.origin_ref for record in sheet.actions} == {EXPECTED_HIPO_OCCURRENCE}


def _manager(context: OracleContext) -> Any:
    """Um colaborador de perfil Gestor do cadastro da demonstração, para a leitura da ficha."""
    access = next(
        item
        for item in configuracoes.list_active_access(context.session)
        if item.general_profile == "Gestor"
    )
    return _user_of(access)


register_check("hse: hht registrado", _afirmar_hht_registrado)
register_check(
    "hse: histograma de mão de obra do projeto 1 a 3", _afirmar_histograma_de_mao_de_obra
)
register_check("hse: ocorrências do projeto 1 em 25/09/2026", _afirmar_ocorrencias_do_projeto_1)
register_check(
    "hse: investigações e ações da ocorrência HiPo", _afirmar_investigacoes_e_acoes_da_ocorrencia
)
