"""Oráculo do painel de mudanças (ISSUE-026): o Pareto e a taxa de aprovação do protótipo.

Valores obtidos de ``painelMudancas`` do protótipo (``api.js``) sobre ``mock-governanca.js`` com a
data de referência 25/09/2026: 16 SMs no portfólio; por origem, Interna 6, Cliente 5, Contratada 2,
Engenharia 2 e Legal/regulatória 1; taxa de aprovação 6 de 7 = 85,7% (sem as adiadas).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Person
from src.modulos.governanca import service
from tests.governanca.apoio import usuario_de
from tests.oraculo import OracleContext, register_check

EXPECTED_TOTAL = 16
EXPECTED_ORIGINS = (
    ("Interna", 6),
    ("Cliente", 5),
    ("Contratada", 2),
    ("Engenharia", 2),
    ("Legal/regulatória", 1),
)
EXPECTED_RATE = Decimal("85.7")


def _admin(context: OracleContext):
    admin = context.session.scalars(
        select(Collaborator)
        .join(Person, Person.id == Collaborator.person_id)
        .where(Person.email == ADMIN_EMAIL)
    ).one()
    return usuario_de(admin)


def _afirmar_painel_do_portfolio(context: OracleContext) -> None:
    painel = service.change_panel(
        context.session,
        user=_admin(context),
        scope=Scope(project_id=None, source="padrao"),
        reference_date=context.reference_date,
    )

    assert painel.summary.total == EXPECTED_TOTAL, "16 SMs no portfolio"
    assert [(linha.label, linha.total) for linha in painel.origins] == list(EXPECTED_ORIGINS)
    assert painel.origins[-1].cumulative == Decimal("100.0"), "o acumulado fecha em 100%"
    assert painel.approval_rate == EXPECTED_RATE, "6 de 7 decididas, sem as adiadas"


register_check("mudancas: painel do portfolio", _afirmar_painel_do_portfolio)
