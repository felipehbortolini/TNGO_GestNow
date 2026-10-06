"""Oráculo do Relato do período (ISSUE-044): os 9 relatos do protótipo em 25/09/2026.

Números do protótipo (README, "Relato do período: regras", e ``mock-planejamento``): semanais S36,
S37 e S38 e mensais de julho e agosto de 2026 para o projeto 1; S38 e agosto para os projetos 2 e 3;
a semana 39 e setembro (em andamento) ficam pendentes. Sem divergência com o protótipo.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.auth import _user_of
from src.core.rbac import GeneralProfile
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import service
from src.modulos.planejamento.validation import MONTHLY, WEEKLY
from tests.oraculo import OracleContext, harness, register_check

PROJECT_1 = "TN-2026-014"
PROJECT_2 = "TN-2026-021"
PROJECT_3 = "TN-2026-027"

EXPECTED_REPORTS = {
    (PROJECT_1, MONTHLY, "2026-07"): (4, 4, 2),
    (PROJECT_1, MONTHLY, "2026-08"): (4, 4, 3),
    (PROJECT_1, WEEKLY, "2026-S36"): (3, 3, 1),
    (PROJECT_1, WEEKLY, "2026-S37"): (4, 4, 2),
    (PROJECT_1, WEEKLY, "2026-S38"): (5, 5, 3),
    (PROJECT_2, MONTHLY, "2026-08"): (4, 4, 2),
    (PROJECT_2, WEEKLY, "2026-S38"): (3, 3, 1),
    (PROJECT_3, MONTHLY, "2026-08"): (3, 3, 1),
    (PROJECT_3, WEEKLY, "2026-S38"): (3, 3, 1),
}


def _afirmar_relatos_do_periodo(context: OracleContext) -> None:
    session = context.session
    admin = next(
        access
        for access in configuracoes.list_active_access(session)
        if access.general_profile == GeneralProfile.ADMIN
    )
    user = _user_of(admin)
    portfolio = Scope(project_id=None, source="url")

    reports = service.list_reports(session, user=user, scope=portfolio)
    found = {
        (report.project_code, report.kind, report.period): (
            len(report.activities),
            len(report.next_activities),
            len(report.points),
        )
        for report in reports
    }
    assert found == EXPECTED_REPORTS, (
        "relatos do prototipo (projeto, tipo, periodo, linhas, pontos)"
    )

    summary = service.report_summary(
        session, user=user, scope=portfolio, reference_date=context.reference_date
    )
    assert (summary.total, summary.weekly_total, summary.monthly_total) == (9, 5, 4), (
        "relatos registrados"
    )
    assert (summary.previous_week.period, summary.previous_week.registered) == ("2026-S38", 3)
    assert (summary.previous_month.period, summary.previous_month.registered) == ("2026-08", 3)
    assert summary.previous_week.expected == summary.previous_month.expected == 3, (
        "projetos esperados"
    )
    assert not [view for view in reports if view.period in ("2026-S39", "2026-09")], "pendentes"
    project_1 = next(p for p in configuracoes.list_projects(session) if p.code == PROJECT_1)
    own = service.report_summary(
        session,
        user=user,
        scope=Scope(project_id=project_1.id, source="url"),
        reference_date=context.reference_date,
    )
    assert own.last_weekly is not None
    assert own.last_weekly.period == "2026-S38"
    assert len(own.last_weekly.points) == 3, "pontos de atencao do ultimo semanal"
    assert own.reference_points == 2, "pontos do semanal anterior (S37)"


register_check("relato do periodo", _afirmar_relatos_do_periodo)


def test_oraculo_do_relato_do_periodo(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    _afirmar_relatos_do_periodo(context)
