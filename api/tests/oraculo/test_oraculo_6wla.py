"""Afirmações do oráculo para o 6WLA (ISSUE-045): números do protótipo em 25/09/2026.

Fonte: ``mock-planejamento`` (coleção ``lookahead``) e as regras de ``api.js`` / ``6wla.js``,
calculadas com um script descartável sobre o mock: 23 atividades (14, 5 e 4 por projeto),
11 delas no curto prazo (duas primeiras semanas), 3 prontas; 28 restrições, 23 abertas,
1 vencida (aberta com data necessária anterior a 25/09/2026); índice de remoção 18 %
(17,86 sem arredondar para inteiro, como a tela mostra).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from src.modulos.planejamento import service
from tests.oraculo import OracleContext, register_check

PROJECT_CODES = ("TN-2026-014", "TN-2026-021", "TN-2026-027")
# atividades, curto prazo, prontas no curto prazo, restrições, abertas, vencidas
BY_PROJECT = {
    "TN-2026-014": (14, 7, 2, 15, 13, 1),
    "TN-2026-021": (5, 3, 1, 8, 6, 0),
    "TN-2026-027": (4, 1, 0, 5, 4, 0),
}
PORTFOLIO = (23, 11, 3, 28, 23, 1)
REMOVAL_INDEX = Decimal("17.86")


def _board(context: OracleContext, project_id: int | None) -> service.LookaheadBoard:
    viewer = User(
        id=0,
        person_id=0,
        name="Oráculo",
        email="oraculo@example.invalid",
        general_profile=GeneralProfile.ADMIN,
        bond=Bond.TIMENOW,
    )
    return service.lookahead_board(
        context.session,
        user=viewer,
        scope=Scope(project_id=project_id, source="url"),
        reference_date=context.reference_date,
        filters=service.LookaheadFilter(),
    )


def _figures(board: service.LookaheadBoard) -> tuple[int, ...]:
    figures = board.figures
    return (
        figures.activities,
        figures.short_term_activities,
        figures.short_term_ready,
        figures.total_constraints,
        figures.open_constraints,
        figures.overdue_constraints,
    )


def _assert_lookahead_of_the_prototype(context: OracleContext) -> None:
    portfolio = _board(context, None)
    assert _figures(portfolio) == PORTFOLIO, "indicadores do 6WLA no Portfólio"
    assert portfolio.figures.removal_index == REMOVAL_INDEX, "índice de remoção do Portfólio"
    assert portfolio.weeks[0].start.isoformat() == "2026-09-28", "primeira semana do horizonte"
    assert len(portfolio.weeks) == 6
    for code in PROJECT_CODES:
        project = context.session.scalars(select(Project).where(Project.code == code)).one()
        assert _figures(_board(context, project.id)) == BY_PROJECT[code], f"6WLA do projeto {code}"


register_check("6WLA: indicadores do protótipo", _assert_lookahead_of_the_prototype)
