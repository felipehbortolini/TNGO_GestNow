"""Afirmações do oráculo para a Punch list (ISSUE-049): números do protótipo em 25/09/2026.

Fonte: ``mock-planejamento`` (coleção ``punch``, 20 itens: 16 no projeto 1, 4 no projeto 2 e
nenhum no 3) e as regras de ``api.js`` (``punchComCalculos``, ``resumoPunch``) e de
``punch-list.js`` (``bloqueio``), calculadas com um script descartável sobre o mock. Sem
divergência com o protótipo.
"""

from __future__ import annotations

from sqlalchemy import select

from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from src.modulos.planejamento import punch_service as service
from tests.oraculo import OracleContext, register_check

# itens, abertos, abertos da categoria A, vencidos, aguardando verificação, fechados, válidos
BY_PROJECT = {
    "TN-2026-014": (16, 12, 4, 2, 2, 3, 15),
    "TN-2026-021": (4, 3, 1, 1, 1, 1, 4),
}
PORTFOLIO = (20, 15, 5, 3, 3, 4, 19)
BLOCKED_SYSTEMS = {
    "TN-2026-014": ("210 Moagem", "310 Flotação", "420 Subestação unitária"),
    "TN-2026-021": ("610 Caldeira e queimador",),
}
# Por sistema: itens abertos que bloqueiam Completação mecânica, Comissionamento e Aceite definitivo.
RELEASE_MATRIX = {
    "210": (0, 2, 4),
    "310": (0, 1, 4),
    "420": (1, 1, 1),
    "510": (0, 0, 3),
    "610": (1, 1, 2),
    "620": (0, 0, 1),
    "630": (0, 0, 0),
    "710": (0, 0, 0),
    "720": (0, 0, 0),
}


def _board(context: OracleContext, project_id: int | None) -> service.PunchBoard:
    viewer = User(
        id=0,
        person_id=0,
        name="Oráculo",
        email="oraculo@example.invalid",
        general_profile=GeneralProfile.ADMIN,
        bond=Bond.TIMENOW,
    )
    return service.punch_board(
        context.session,
        user=viewer,
        scope=Scope(project_id=project_id, source="url"),
        reference_date=context.reference_date,
        filters=service.PunchFilter(situation=""),
    )


def _figures(board: service.PunchBoard) -> tuple[int, ...]:
    figures = board.figures
    return (
        board.total,
        figures.open,
        figures.open_a,
        figures.overdue,
        figures.awaiting,
        figures.closed,
        figures.valid,
    )


def _assert_punch_list_of_the_prototype(context: OracleContext) -> None:
    portfolio = _board(context, None)
    assert _figures(portfolio) == PORTFOLIO, "indicadores da Punch list no Portfólio"
    for code, expected in BY_PROJECT.items():
        project = context.session.scalars(select(Project).where(Project.code == code)).one()
        board = _board(context, project.id)
        assert _figures(board) == expected, f"Punch list do projeto {code}"
        assert board.blocked_systems == BLOCKED_SYSTEMS[code], f"sistemas bloqueados de {code}"
    for system in portfolio.systems:
        code = system.label.split(" ", 1)[0]
        assert system.blocks == RELEASE_MATRIX[code], f"liberação por marco do sistema {code}"


register_check(
    "Punch list: indicadores, bloqueio e liberação por marco", _assert_punch_list_of_the_prototype
)
