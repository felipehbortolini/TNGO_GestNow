"""Oráculo do HSE, fatia HHT e consolidado mensal (ISSUE-072): números do protótipo.

Somas obtidas das coleções ``hht`` e ``hseMensal`` do protótipo (mesmos valores que as telas do
protótipo somavam): registros, HHT e efetivo por projeto, e desvios, observações e DDS realizados
do consolidado mensal. O histograma previsto depende da Curva S física, ainda sem dono no app
(``register_curve_reader``); sua afirmação entra quando a curva chegar.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from src.modulos.hse import service
from tests.oraculo import OracleContext, register_check

# código do projeto -> (registros de HHT, HHT total, soma do efetivo médio)
EXPECTED_HOURS = {
    "TN-2026-014": (32, Decimal(788070), 3615),
    "TN-2026-021": (23, Decimal(160012), 734),
    "TN-2026-027": (12, Decimal(34880), 160),
}
# código do projeto -> (meses, desvios, observações, DDS realizados)
EXPECTED_CLOSINGS = {
    "TN-2026-014": (9, 1240, 3231, 1155),
    "TN-2026-021": (7, 174, 608, 168),
    "TN-2026-027": (4, 36, 133, 47),
}


def _project_ids(context: OracleContext) -> dict[str, int]:
    return {p.code: p.id for p in context.session.scalars(select(Project)).all()}


def _afirmar_hht_por_projeto(context: OracleContext) -> None:
    for code, project_id in _project_ids(context).items():
        if code not in EXPECTED_HOURS:
            continue
        rows = service.list_hours(
            context.session, scope=Scope(project_id=project_id, source="padrao")
        )
        got = (len(rows), sum((r.hours for r in rows), Decimal(0)), sum(r.headcount for r in rows))
        assert got == EXPECTED_HOURS[code], f"HHT do projeto {code}"


def _afirmar_consolidado_mensal(context: OracleContext) -> None:
    for code, project_id in _project_ids(context).items():
        if code not in EXPECTED_CLOSINGS:
            continue
        rows = service.list_closings(
            context.session, scope=Scope(project_id=project_id, source="padrao")
        )
        got = (
            len(rows),
            sum(r.deviations for r in rows),
            sum(r.observations for r in rows),
            sum(r.held_dds for r in rows),
        )
        assert got == EXPECTED_CLOSINGS[code], f"consolidado mensal do projeto {code}"
        assert len({r.month for r in rows}) == len(rows), "um consolidado por mês"


register_check("HHT: registros, horas e efetivo por projeto", _afirmar_hht_por_projeto)
register_check("HSE: consolidado mensal por projeto", _afirmar_consolidado_mensal)
