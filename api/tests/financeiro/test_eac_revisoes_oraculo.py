"""Oráculo das revisões da EAC e dos remanejamentos (ISSUE-030): os números do protótipo.

A parte ``governanca-eac`` da demonstração escreve as revisões do mock com a linha de base
congelada de cada item de nível 3, os remanejamentos aplicados com a revisão que os consolidará
(a próxima, Rev 3) e a SM 0011 pendente. O orçamento vigente passa a ser a linha de base da
última revisão: no projeto 1 o total calculado e o do mock coincidem; nos projetos 2 e 3 vale o
total do mock (a diferença de centavos fica no valor calculado dos itens sem revisão, registrada
em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modulos.configuracoes.models import Project
from src.modulos.financeiro import service
from src.modulos.financeiro.models import EacItem, EacReallocation, EacRevision, EacRevisionItem
from src.modulos.governanca.models import ChangeReallocation, ChangeRequest
from tests.oraculo import OracleContext, harness, register_check

REVISIONS = (
    ("TN-2026-014", 0, "2026-01-05", 4_380_000_000),
    ("TN-2026-014", 1, "2026-05-18", 4_420_000_000),
    ("TN-2026-014", 2, "2026-07-10", 4_460_000_000),
    ("TN-2026-021", 0, "2026-03-02", 1_820_000_000),
    ("TN-2026-027", 0, "2026-06-01", 740_000_000),
)
APPLIED = (
    ("SM-TN-2026-0009", "2026-08-12", "2.1.3", "1.2.2", 15_000_000),
    ("SM-TN-2026-0010", "2026-09-02", "2.2.5", "3.1.2", 20_000_000),
)
PENDING = ("SM-TN-2026-0011", "3.2.1", "3.1.2", 25_000_000)
INCORPORATED = {"SM-TN-2026-0001": 1, "SM-TN-2026-0002": 2}
NEXT_REVISION = 3
FREE_BALANCE_321 = 300_000_000


def _project(session: Session, code: str) -> Project:
    return session.scalars(select(Project).where(Project.code == code)).one()


def _revisions(session: Session, project_id: int) -> dict[int, EacRevision]:
    records = session.scalars(select(EacRevision).where(EacRevision.project_id == project_id)).all()
    return {record.revision: record for record in records}


def _frozen(session: Session, revision_id: int) -> dict[str, int]:
    rows = session.execute(
        select(EacItem.code, EacRevisionItem.base_cents)
        .join(EacRevisionItem, EacRevisionItem.item_id == EacItem.id)
        .where(EacRevisionItem.revision_id == revision_id)
    ).all()
    return dict(rows)


def _item_id(session: Session, project_id: int, code: str) -> int:
    return session.scalars(
        select(EacItem.id).where(EacItem.project_id == project_id, EacItem.code == code)
    ).one()


def _afirmar_revisoes(context: OracleContext) -> None:
    session = context.session
    for code, revision, day, total_cents in REVISIONS:
        project = _project(session, code)
        record = _revisions(session, project.id)[revision]
        assert record.revision_date == date.fromisoformat(day), f"data da Rev {revision} de {code}"
        views = service.revisions(session, project_id=project.id)
        found = next(view for view in views if view.revision == revision)
        assert found.total_cents == total_cents, f"total da Rev {revision} de {code}"


def _afirmar_linhas_congeladas(context: OracleContext) -> None:
    session = context.session
    project = _project(session, "TN-2026-014")
    records = _revisions(session, project.id)
    rev2 = _frozen(session, records[2].id)
    rev1 = _frozen(session, records[1].id)
    rev0 = _frozen(session, records[0].id)

    assert rev2["1.2.1"] == 110_000_000, "Rev 2 congela a base atual do mock"
    assert rev1["1.2.1"] == 70_000_000, "Rev 1 é a Rev 2 menos os R$ 400 mil da SM 0002"
    assert rev0["1.1.1"] == 30_000_000, "Rev 0 é a Rev 1 menos os R$ 400 mil da SM 0001"
    assert rev1["1.1.1"] == 70_000_000
    assert sum(rev0.values()) == 4_380_000_000
    assert sum(rev1.values()) == 4_420_000_000
    assert sum(rev2.values()) == 4_460_000_000


def _afirmar_remanejamentos(context: OracleContext) -> None:
    session = context.session
    project = _project(session, "TN-2026-014")
    applied = session.scalars(
        select(EacReallocation).where(EacReallocation.project_id == project.id)
    ).all()
    assert len(applied) == len(APPLIED), "remanejamentos aplicados da demonstração"

    by_change = {
        change.id: change.code
        for change in session.scalars(
            select(ChangeRequest).where(ChangeRequest.id.in_([row.change_id for row in applied]))
        )
    }
    rows = {by_change[row.change_id]: row for row in applied}
    for code, day, source, target, value_cents in APPLIED:
        row = rows[code]
        assert row.revision == NEXT_REVISION, f"{code} aponta para a revisão que a consolida"
        assert row.applied_on == date.fromisoformat(day), f"data de {code}"
        assert row.source_item_id == _item_id(session, project.id, source)
        assert row.target_item_id == _item_id(session, project.id, target)
        assert row.value_cents == value_cents

    transfers = session.scalars(
        select(ChangeReallocation).where(ChangeReallocation.applied.is_(True))
    ).all()
    assert len(transfers) == len(APPLIED), "transferências aplicadas de mudanca_remanejamento"
    for transfer in transfers:
        assert transfer.eac_revision == NEXT_REVISION
        assert transfer.applied_on is not None
        assert transfer.applied_by_id is not None

    pending = session.scalars(
        select(ChangeReallocation).where(ChangeReallocation.applied.is_(False))
    ).all()
    assert len(pending) == 1, "a SM 0011 fica pendente"
    transfer = pending[0]
    change = session.get(ChangeRequest, transfer.change_id)
    assert change is not None and change.code == PENDING[0]
    assert transfer.value_cents == PENDING[3]
    assert transfer.source_item_id == _item_id(session, project.id, PENDING[1])
    assert transfer.target_item_id == _item_id(session, project.id, PENDING[2])
    assert transfer.eac_revision is None

    listing = service.reallocations(session, project_id=project.id)
    assert [view.change_code for view in listing.applied] == [code for code, *_ in APPLIED]
    assert len(listing.pending) == 1
    assert listing.pending[0].free_balance_cents == FREE_BALANCE_321


def _afirmar_incorporacao(context: OracleContext) -> None:
    session = context.session
    for code, revision in INCORPORATED.items():
        change = session.scalars(select(ChangeRequest).where(ChangeRequest.code == code)).one()
        assert change.eac_revision == revision, f"{code} incorporada pela Rev {revision}"


register_check("EAC: revisões do protótipo", _afirmar_revisoes)
register_check("EAC: linhas congeladas das revisões", _afirmar_linhas_congeladas)
register_check("EAC: remanejamentos aplicados e pendente", _afirmar_remanejamentos)
register_check("EAC: revisões incorporadas pelas SMs", _afirmar_incorporacao)


def test_a_carga_de_revisoes_bate_com_o_mock(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    _afirmar_revisoes(context)
    _afirmar_linhas_congeladas(context)
    _afirmar_remanejamentos(context)
    _afirmar_incorporacao(context)
