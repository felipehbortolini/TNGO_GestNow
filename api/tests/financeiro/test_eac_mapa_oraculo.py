"""Oráculo do mapa de controle (ISSUE-031): a projeção no término da demonstração em 25/09/2026.

A parte ``financeiro-custos`` grava os fatos de ``custo_erp`` do mock: um por item de custo, no
mês da data de corte, com o comprometido, o realizado e a projeção do protótipo. A soma das
projeções do projeto 1 fecha ``4.525.500.000`` centavos — apresentada em milhões com duas casas,
os R$ 45,26 mi do cenário — e o desvio do projeto é positivo, isto é, sobrecusto. A carteira traz
um registro por projeto e o total é a soma deles.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import plataforma, prototype_collection
from src.carga.registro import DEMO_ANCHOR
from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from src.modulos.financeiro import seed, service
from tests.oraculo import OracleContext, register_check

MOCK_PROJECT = 1
PROJECT_CODE = "TN-2026-014"
PROJECTION_TOTAL_CENTS = 4_525_500_000
PROJECTION_TOTAL_MI = Decimal("45.26")
COMMITTED_TOTAL_CENTS = 4_113_000_000
ACTUAL_TOTAL_CENTS = 2_870_000_000
LEAF_LEVEL = 3
PORTFOLIO = Scope(project_id=None, source="padrao")


def _projects(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.code)))


def _mapa(session: Session, scope: Scope, reference_date: date) -> service.MapaControleView:
    return service.mapa_controle(session, scope=scope, reference_date=reference_date)


def _project_scope(project: Project) -> Scope:
    return Scope(project_id=project.id, source="url")


def _afirmar_projecao_da_demonstracao(context: OracleContext) -> None:
    first = _projects(context.session)[0]
    view = _mapa(context.session, _project_scope(first), context.reference_date)
    mock_total = sum(
        int(source["projecao"])
        for source in prototype_collection("eac")
        if source["projetoId"] == MOCK_PROJECT and source["nivel"] == LEAF_LEVEL
    )

    assert mock_total == PROJECTION_TOTAL_CENTS, "soma das projeções do mock do projeto 1"
    assert view.total.projection_cents == PROJECTION_TOTAL_CENTS, (
        "a projeção no término do projeto 1 é a soma das projeções por item"
    )
    millions = (Decimal(view.total.projection_cents) / Decimal(100_000_000)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert millions == PROJECTION_TOTAL_MI, "projeção no término do projeto 1: R$ 45,26 mi"
    assert view.total.deviation_cents == view.total.projection_cents - view.total.current_cents
    assert view.total.deviation_cents > 0, "o desvio positivo é sobrecusto"


def _afirmar_carteira_do_mapa(context: OracleContext) -> None:
    projects = _projects(context.session)
    view = _mapa(context.session, PORTFOLIO, context.reference_date)

    assert view.is_portfolio
    assert [row.project_id for row in view.rows] == [project.id for project in projects]
    assert view.rows[0].projection_cents == PROJECTION_TOTAL_CENTS, "projeto 1 na carteira"
    assert view.total.projection_cents == sum(row.projection_cents for row in view.rows)
    assert view.total.deviation_cents > 0


register_check(
    "mapa de controle: projeção no término do projeto 1", _afirmar_projecao_da_demonstracao
)
register_check("mapa de controle: carteira", _afirmar_carteira_do_mapa)


def test_o_fechamento_do_erp_da_carga_fecha_a_projecao_em_45_26_mi(db_session: Session) -> None:
    plataforma.load(db_session, DEMO_ANCHOR)
    seed.load(db_session, DEMO_ANCHOR)
    seed.load_erp_costs(db_session, DEMO_ANCHOR)

    first = db_session.scalars(select(Project).where(Project.code == PROJECT_CODE)).one()
    view = _mapa(db_session, _project_scope(first), DEMO_ANCHOR)

    assert view.total.committed_cents == COMMITTED_TOTAL_CENTS
    assert view.total.actual_cents == ACTUAL_TOTAL_CENTS
    assert view.total.projection_cents == PROJECTION_TOTAL_CENTS
    assert view.total.deviation_cents > 0
