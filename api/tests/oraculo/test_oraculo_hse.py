"""Oráculo do HSE (ISSUE-072 a ISSUE-075): o HHT, o histograma, as ocorrências e os estudos.

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

As análises de risco (ISSUE-074) são afirmadas no projeto 1 em 25/09/2026: os 5 estudos do mock
(3 APR e 2 HAZOP), as 17 recomendações (8 abertas e 9 fechadas), as 3 atrasadas (abertas com o
prazo anterior a 25/09/2026, como ``analiseCalculada`` do protótipo contava) e o indicador de
fechadas ÷ emitidas em 52,9%.

O painel (ISSUE-075) é afirmado no projeto 1 em 25/09/2026: o mês padrão é o último com HHT
(2026-09) e o acumulado vai de 2026-01 a 2026-09; a TF fecha em 0,00 e a TRIF do mês em 6,80 e
do acumulado em 8,88 (7 registráveis), a pirâmide acumulada em 0/16/31/190/1.240, os dias sem
afastamento em 263 (sem LTI, desde o início do projeto em 05/01/2026), as ações HSE no prazo em
50,0% (1 das 2 vencidas concluída no prazo) e a nota HSE sugerida da Alfa Montagens em 3
(TRIF 11,01 contra 8,88 do projeto).
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from src.carga import prototype_collection
from src.core.auth import _user_of
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, models, painel_service, service, validation
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

# As análises de risco do projeto 1 em 25/09/2026 (divergências: nenhuma).
EXPECTED_ANALYSES = 5
EXPECTED_ANALYSIS_TYPES = {"APR": 3, "HAZOP": 2}
EXPECTED_RECOMMENDATIONS = 17
EXPECTED_RECOMMENDATIONS_OPEN = 8
EXPECTED_RECOMMENDATIONS_CLOSED = 9
EXPECTED_RECOMMENDATIONS_OVERDUE = 3
EXPECTED_OVERDUE_DUE_DATES = [date(2026, 8, 20), date(2026, 9, 10), date(2026, 9, 20)]
EXPECTED_RECOMMENDATIONS_CLOSED_PCT = Decimal("52.9")

# O painel do projeto 1 em 25/09/2026 (ISSUE-075; divergências: nenhuma).
EXPECTED_PANEL_MONTH = date(2026, 9, 1)
EXPECTED_PANEL_WINDOW = (date(2026, 1, 1), date(2026, 9, 1))
EXPECTED_MONTH_RATES = (Decimal("0.00"), Decimal("6.80"), Decimal("0.0"))
EXPECTED_MONTH_PYRAMID = (0, 2, 5, 32, 189)
EXPECTED_PANEL_RATES = (Decimal("0.00"), Decimal("8.88"), Decimal("0.0"))
EXPECTED_PANEL_PYRAMID = (0, 16, 31, 190, 1240)
EXPECTED_DAYS_WITHOUT_LEAVE = 263
EXPECTED_EVOLUTION_POINTS = 9
EXPECTED_AREA_TOP = ("Terraplenagem", 39)
EXPECTED_COMPANY_TOP = ("Zeta Civil", 132)
EXPECTED_ACTIONS_ON_TIME_PCT = Decimal("50.0")
EXPECTED_COMPANY_NOTE = (3, Decimal("11.01"), Decimal("8.88"))


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


def _afirmar_analises_de_risco_do_projeto_1(context: OracleContext) -> None:
    project_id = _project_id(context, PROJECT_CODE)
    scope = Scope(project_id=project_id, source="url")
    screen = service.analyses_screen(
        context.session,
        scope=scope,
        filters=validation.AnalysisFilters(),
        reference_date=context.reference_date,
    )

    assert screen.universe == EXPECTED_ANALYSES, "os 5 estudos do mock no projeto 1"
    assert len(screen.rows) == EXPECTED_ANALYSES, "sem filtro, a lista inteira"
    assert Counter(row.kind for row in screen.rows) == Counter(EXPECTED_ANALYSIS_TYPES), (
        "3 APR e 2 HAZOP, como o mock"
    )

    summary = screen.summary
    assert summary.open == EXPECTED_RECOMMENDATIONS_OPEN, "8 recomendações abertas"
    assert summary.closed == EXPECTED_RECOMMENDATIONS_CLOSED, "9 recomendações fechadas"
    assert summary.open + summary.closed == EXPECTED_RECOMMENDATIONS, "as 17 emitidas do mock"
    assert summary.overdue == EXPECTED_RECOMMENDATIONS_OVERDUE, (
        "3 abertas com o prazo anterior a 25/09/2026"
    )
    atrasadas = sorted(
        line.due_date for row in screen.rows for line in row.recommendations if line.overdue
    )
    assert atrasadas == EXPECTED_OVERDUE_DUE_DATES, "os prazos vencidos do mock"

    share = service.recommendation_share(context.session, scope=scope)
    assert (share.closed, share.emitted) == (
        EXPECTED_RECOMMENDATIONS_CLOSED,
        EXPECTED_RECOMMENDATIONS,
    ), "o indicador conta as recomendações do projeto"
    assert share.pct == EXPECTED_RECOMMENDATIONS_CLOSED_PCT, "9 de 17 fecha em 52,9%"

    # A HAZOP de 22/06/2026 é a maior do mock: 6 recomendações, 3 de cada situação.
    hazop = next(row for row in screen.rows if row.code == "HAZOP-TN-2026-01")
    assert (hazop.kind, hazop.open_count, hazop.closed_count, hazop.overdue_count) == (
        "HAZOP",
        3,
        3,
        1,
    )
    assert hazop.participants == 4, "os 4 participantes do mock"


def _afirmar_painel_hse(context: OracleContext) -> None:
    scope = Scope(project_id=_project_id(context, PROJECT_CODE), source="url")
    panel = painel_service.panel(
        context.session,
        user=_manager(context),
        scope=scope,
        reference_date=context.reference_date,
        month=None,
        pyramid_kind=None,
    )
    month = panel.month_indicators
    accumulated = panel.accumulated_indicators
    assert panel.month == EXPECTED_PANEL_MONTH, "o mês padrão é o último com HHT"
    assert (panel.window_start, panel.window_end) == EXPECTED_PANEL_WINDOW, "a janela acumulada"
    assert month is not None and accumulated is not None

    assert (month.tf, month.trif, month.tg) == EXPECTED_MONTH_RATES, "as taxas do mês"
    assert month.pyramid == EXPECTED_MONTH_PYRAMID, "a pirâmide do mês"
    assert (accumulated.tf, accumulated.trif, accumulated.tg) == EXPECTED_PANEL_RATES, (
        "as taxas do acumulado"
    )
    assert accumulated.pyramid == EXPECTED_PANEL_PYRAMID, "a pirâmide acumulada 0/16/31/190/1.240"
    assert accumulated.days_without_leave == EXPECTED_DAYS_WITHOUT_LEAVE, (
        "263 dias sem afastamento, desde o início do projeto em 05/01/2026"
    )
    assert len(panel.evolution) == EXPECTED_EVOLUTION_POINTS, "um ponto por mês com HHT"
    assert (panel.by_area[0].name, panel.by_area[0].total) == EXPECTED_AREA_TOP, (
        "a maior área do acumulado"
    )
    assert (panel.by_company[0].name, panel.by_company[0].total) == EXPECTED_COMPANY_TOP, (
        "a maior empresa do acumulado"
    )
    assert accumulated.actions_on_time_pct == EXPECTED_ACTIONS_ON_TIME_PCT, (
        "1 das 2 ações HSE vencidas concluída no prazo"
    )

    alfa = next(
        option
        for option in configuracoes.list_company_options(context.session)
        if option.name == "Alfa Montagens"
    )
    note = painel_service.company_note_suggestion(
        context.session,
        company_id=alfa.id,
        scope=scope,
        reference_date=context.reference_date,
    )
    assert note is not None
    assert (note.note, note.trif, note.project_trif) == EXPECTED_COMPANY_NOTE, (
        "a nota HSE sugerida da Alfa Montagens"
    )


register_check("hse: hht registrado", _afirmar_hht_registrado)
register_check(
    "hse: histograma de mão de obra do projeto 1 a 3", _afirmar_histograma_de_mao_de_obra
)
register_check("hse: ocorrências do projeto 1 em 25/09/2026", _afirmar_ocorrencias_do_projeto_1)
register_check(
    "hse: investigações e ações da ocorrência HiPo", _afirmar_investigacoes_e_acoes_da_ocorrencia
)
register_check(
    "hse: análises de risco do projeto 1 em 25/09/2026", _afirmar_analises_de_risco_do_projeto_1
)
register_check("hse: painel do projeto 1 em 25/09/2026", _afirmar_painel_hse)
