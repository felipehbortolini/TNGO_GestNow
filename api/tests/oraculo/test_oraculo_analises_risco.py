"""Oráculo das análises de risco do HSE (ISSUE-074): números do protótipo.

Contagens obtidas executando a regra do protótipo (``analiseCalculada`` de ``api.js``: atrasada é
a recomendação Aberta com prazo anterior à referência, 25/09/2026) sobre a coleção ``analisesRisco``:
estudos, recomendações emitidas, abertas, atrasadas e fechadas por projeto, e a taxa de
recomendações fechadas ÷ emitidas (``F.pct(fechadas / total * 100, 1)`` da tela do protótipo).
Divergência: nenhuma; o protótipo e a regra do app coincidem.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from src.modulos.hse import analysis_service
from src.modulos.hse.analysis_service import AnalysisFilter
from tests.oraculo import OracleContext, register_check

# código do projeto -> (estudos, emitidas, abertas, atrasadas, fechadas, taxa de fechadas em %)
EXPECTED_ANALYSES = {
    "TN-2026-014": (5, 17, 8, 3, 9, Decimal("52.9")),
    "TN-2026-021": (2, 6, 3, 1, 3, Decimal("50.0")),
    "TN-2026-027": (1, 2, 2, 1, 0, Decimal("0.0")),
}
# Portfólio, na mesma ordem dos números de cada projeto.
EXPECTED_PORTFOLIO = (8, 25, 13, 5, 12, Decimal("48.0"))


def _summary(
    context: OracleContext, scope: Scope
) -> tuple[int, int, int, int, int, Decimal | None]:
    listing = analysis_service.list_analyses(
        context.session,
        scope=scope,
        filters=AnalysisFilter(),
        reference_date=context.reference_date,
    )
    counts = listing.counts
    return (
        len(listing.rows),
        counts.issued,
        counts.open,
        counts.overdue,
        counts.closed,
        listing.closed_rate,
    )


def _afirmar_por_projeto(context: OracleContext) -> None:
    projects = {p.code: p.id for p in context.session.scalars(select(Project)).all()}
    for code, expected in EXPECTED_ANALYSES.items():
        scope = Scope(project_id=projects[code], source="padrao")
        assert _summary(context, scope) == expected, f"análises de risco do projeto {code}"


def _afirmar_portfolio(context: OracleContext) -> None:
    got = _summary(context, Scope(project_id=None, source="padrao"))
    assert got == EXPECTED_PORTFOLIO, "análises de risco do Portfólio"


register_check("HSE: análises de risco e recomendações por projeto", _afirmar_por_projeto)
register_check("HSE: recomendações fechadas ÷ emitidas no Portfólio", _afirmar_portfolio)
