"""Oráculo da EAC (ISSUE-029): os números do protótipo na demonstração de 25/09/2026.

O BAC do projeto 1 é R$ 44,6 mi e os pesos da carteira são 55,36 / 29,34 / 15,30 (ponderação
60% orçamento vigente, 25% criticidade estratégica e 15% complexidade, fechada em 100 pelo maior
resto). Nos projetos 2 e 3 a soma de quantidade x preço difere do ``base`` do protótipo em
centavos (R$ 0,02 e R$ 25,57), porque o protótipo guardava o valor arredondado; o GestNow
calcula, e a diferença está em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md`` como pendente de aceite.
Os pesos saem iguais nos dois casos.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.carga import plataforma
from src.carga.registro import DEMO_ANCHOR
from src.modulos.configuracoes.models import Project
from src.modulos.financeiro import seed, service
from src.modulos.financeiro.models import EacItem
from tests.oraculo import OracleContext, register_check

D = Decimal
BAC_PROJECT_1 = 4_460_000_000
BAC_PROJECT_2 = 1_819_999_800  # 1.820.000.000 no protótipo; ver a divergência registrada
BAC_PROJECT_3 = 740_002_557  # 740.000.000 no protótipo; ver a divergência registrada
ITEMS_BY_PROJECT = (33, 25, 21)


def _projects(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.code)))


def _afirmar_bac_do_projeto_1(context: OracleContext) -> None:
    first, second, third = _projects(context.session)[:3]
    budgets = service.current_budgets(context.session)

    assert budgets[first.id] == BAC_PROJECT_1, "BAC do projeto 1: R$ 44,6 mi"
    assert budgets[second.id] == BAC_PROJECT_2, "BAC do projeto 2 (calculado, divergência)"
    assert budgets[third.id] == BAC_PROJECT_3, "BAC do projeto 3 (calculado, divergência)"


def _afirmar_pesos_da_carteira(context: OracleContext) -> None:
    projects = _projects(context.session)[:3]

    weights = service.portfolio_weights(context.session, reference_date=context.reference_date)

    assert [weights[project.id].weight for project in projects] == [
        D("55.36"),
        D("29.34"),
        D("15.30"),
    ], "pesos da carteira"
    assert sum(weight.weight for weight in weights.values()) == D(100)


def _afirmar_arvore_da_carga(context: OracleContext) -> None:
    session = context.session
    for project, expected in zip(_projects(session)[:3], ITEMS_BY_PROJECT, strict=True):
        count = session.scalar(
            select(func.count()).select_from(EacItem).where(EacItem.project_id == project.id)
        )
        assert count == expected, f"linhas da EAC de {project.code}"


register_check("EAC: BAC dos projetos", _afirmar_bac_do_projeto_1)
register_check("EAC: pesos da carteira", _afirmar_pesos_da_carteira)
register_check("EAC: árvore da carga", _afirmar_arvore_da_carga)


def test_a_carga_da_eac_monta_a_arvore_com_pais_e_totais_do_prototipo(db_session: Session) -> None:
    plataforma.load(db_session, DEMO_ANCHOR)
    seed.load(db_session, DEMO_ANCHOR)

    context = OracleContext(session=db_session, reference_date=DEMO_ANCHOR)
    _afirmar_bac_do_projeto_1(context)
    _afirmar_pesos_da_carteira(context)
    _afirmar_arvore_da_carga(context)
    items = {item.id: item for item in db_session.scalars(select(EacItem))}
    for item in items.values():
        if item.level == 1:
            assert item.parent_id is None
            continue
        parent = items[item.parent_id] if item.parent_id else None
        assert parent is not None, item.code
        assert parent.project_id == item.project_id
        assert parent.level == item.level - 1
        assert item.code.startswith(parent.code + ".")


def test_a_carga_nao_grava_valor_agregado_so_quantidade_e_preco(db_session: Session) -> None:
    plataforma.load(db_session, DEMO_ANCHOR)
    seed.load(db_session, DEMO_ANCHOR)

    leaf = db_session.scalars(
        select(EacItem).where(EacItem.code == "1.2.1").order_by(EacItem.id)
    ).first()

    assert leaf is not None
    assert (leaf.quantity, leaf.unit_price_cents) == (D(5500), 20_000)
    assert leaf.cost_type == "Serviço"
    assert leaf.capex is True
