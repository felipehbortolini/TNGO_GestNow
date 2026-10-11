"""Oráculo do relatório gerencial (ISSUE-083): as folhas do projeto 1 em 2026-S38.

Na demonstração, o corte da semana 38 é 20/09/2026 e as folhas do projeto 1 saem com a
posição da leitura semanal do dono — o previsto interpolado dentro do mês (61,7%, contra 65,7%
do ponto do mês) e o real medido (61,8%, parado desde a semana anterior) —, a produtividade da
janela de quatro semanas (SPI de quantidades 0,89, FP 1,10, aderência 83,9%, pessoas trabalhando
55,2%, utilização 77,2% e 480,7 HH paralisadas, com a Alfa Montagens em alerta), as barras das
últimas 8 semanas e a análise e o relato do período registrados. O custo usa o mês de
competência (2026-08 no semanal).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core import calendario
from src.core.auth import _user_of
from src.core.rbac import GeneralProfile
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.relatorio import calculations, service
from tests.oraculo import OracleContext, harness

PROJECT_1 = "TN-2026-014"

D = Decimal


def _afirmar_as_folhas(context: OracleContext) -> None:
    admin = next(
        acesso
        for acesso in configuracoes.list_active_access(context.session)
        if acesso.general_profile == GeneralProfile.ADMIN
    )
    project = next(
        item for item in configuracoes.list_projects(context.session) if item.code == PROJECT_1
    )
    visao = service.report_view(
        context.session,
        user=_user_of(admin),
        scope=Scope(project_id=project.id, source="url"),
        kind=calendario.WEEKLY,
        period="2026-S38",
        sections=("planejamento",),
        reference_date=context.reference_date,
    )

    assert visao.cut == date(2026, 9, 20), "corte da semana 38"
    planejamento = visao.planning
    assert planejamento is not None
    assert (planejamento.figures.predicted, planejamento.figures.actual) == (
        D("61.7"),
        D("61.8"),
    ), "posicao interpolada no corte semanal"
    assert planejamento.figures.deviation_pp == D("0.1"), "desvio acumulado no corte"
    assert planejamento.figures.spi == D("1.00"), "SPI fisico no corte"
    assert (
        planejamento.figures.previous_predicted,
        planejamento.figures.previous_actual,
        planejamento.figures.previous_spi,
    ) == (D("58.8"), D("61.8"), D("1.05")), "posicao anterior"
    assert (
        planejamento.figures.predicted_period,
        planejamento.figures.actual_period,
    ) == (D("2.9"), D("0.0")), "avanco do periodo na semana"
    assert planejamento.figures.trend_finish == date(2027, 4, 1), "termino pela tendencia"
    assert planejamento.figures.baseline_finish == date(2027, 3, 1), "termino da linha de base"
    produtividade = planejamento.figures.productivity
    assert produtividade is not None
    assert (
        produtividade.spi,
        produtividade.pf_window,
        produtividade.adherence,
        produtividade.working_pct,
        produtividade.utilization,
    ) == (D("0.89"), D("1.10"), D("83.9"), D("55.20"), D("77.2")), "produtividade da janela"
    assert produtividade.stoppage_hours == D("480.7"), "HH paralisadas na janela"
    assert produtividade.alert_companies == ("Alfa Montagens",), "empresas em alerta"
    assert len(planejamento.bars) == 8, "barras das ultimas 8 semanas"
    assert planejamento.bars[-1].period == "2026-S38"
    assert visao.analysis is not None and visao.analysis.record is not None, "analise registrada"
    assert visao.relato is not None and visao.relato.activities, "relato registrado"
    assert calculations.competence_month(calendario.WEEKLY, "2026-S38") == date(2026, 8, 1), (
        "custo apurado no ultimo mes fechado"
    )


def test_oraculo_do_relatorio_gerencial(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    _afirmar_as_folhas(context)
