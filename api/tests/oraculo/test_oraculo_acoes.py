"""Oráculo da Central de Ações (ISSUE-019): os números do protótipo em 25/09/2026.

Valores obtidos executando ``statusAcao`` e ``acoesComStatus`` do protótipo sobre os mocks
(60 ações nativas e 19 derivadas da Punch list não cancelada, 3 informações fora da conta).
O projeto 1 (TN-2026-014) é o da tela do protótipo: 8 ações atrasadas.
"""

from __future__ import annotations

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.central_acoes import service
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from tests.oraculo import OracleContext, register_check

# código do projeto -> (em andamento no prazo, atrasadas, concluídas)
EXPECTED_BY_PROJECT = {
    "TN-2026-014": (25, 8, 19),
    "TN-2026-021": (8, 5, 5),
    "TN-2026-027": (3, 1, 2),
}


def _admin(context: OracleContext) -> User:
    access = configuracoes.find_access_by_email(context.session, ADMIN_EMAIL)
    assert access is not None, "admin da demonstracao"
    return User(
        id=access.id,
        person_id=access.person_id,
        name=access.name,
        email=access.email,
        general_profile=GeneralProfile(access.general_profile),
        bond=Bond(access.bond),
        company_id=access.company_id,
    )


def _afirmar_acoes_por_projeto(context: OracleContext) -> None:
    user = _admin(context)
    projects = {
        project.code: project.id for project in context.session.scalars(select(Project)).all()
    }
    for code, (on_time, overdue, completed) in EXPECTED_BY_PROJECT.items():
        counts = service.count_by_status(
            context.session,
            user=user,
            scope=Scope(project_id=projects[code], source="padrao"),
            reference_date=context.reference_date,
        )
        assert (counts.on_time, counts.overdue, counts.completed) == (
            on_time,
            overdue,
            completed,
        ), f"acoes do projeto {code}"
    assert EXPECTED_BY_PROJECT["TN-2026-014"][1] == 8, "8 acoes atrasadas em 25/09/2026"


def _afirmar_acoes_do_portfolio(context: OracleContext) -> None:
    counts = service.count_by_status(
        context.session,
        user=_admin(context),
        scope=Scope(project_id=None, source="padrao"),
        reference_date=context.reference_date,
    )
    assert (counts.on_time, counts.overdue, counts.completed, counts.total) == (
        36,
        14,
        26,
        76,
    ), "acoes do portfolio"


register_check("acoes atrasadas e KPIs por projeto", _afirmar_acoes_por_projeto)
register_check("acoes do portfolio", _afirmar_acoes_do_portfolio)
