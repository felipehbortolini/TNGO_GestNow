"""Visão consolidada da administração contratual: as listas e os indicadores da carga (ISSUE-035).

A visão do projeto 1 e a do Portfólio são conferidas contra o mock: as cinco listas (contratos,
claims, EOTs, marcos e avaliações), o resumo e os dez indicadores, com a data de referência da
demonstração injetada. Os valores são os do protótipo de 25/09/2026, os mesmos conferidos à mão
nos cálculos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import DEMO_ANCHOR, run_demonstration
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from src.modulos.financeiro import calculations, service

D = Decimal
PROJECT_CODE = "TN-2026-014"


def _usuario(perfil: GeneralProfile = GeneralProfile.ADMIN, bond: Bond = Bond.TIMENOW) -> User:
    return User(
        id=1,
        person_id=1,
        name="Admin da carga",
        email="admin-carga@example.invalid",
        general_profile=perfil,
        bond=bond,
    )


def _escopo(project: Project | None) -> Scope:
    if project is None:
        return Scope(project_id=None, source="padrao")
    return Scope(project_id=project.id, source="url")


def _projeto(session: Session) -> Project:
    return session.scalars(select(Project).where(Project.code == PROJECT_CODE)).one()


def _visao(session: Session, project: Project | None) -> service.ContractsOverview:
    return service.contracts_overview(
        session, user=_usuario(), scope=_escopo(project), reference_date=DEMO_ANCHOR
    )


def test_visao_do_projeto_semeado_traz_as_listas_e_os_indicadores(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)
    project = _projeto(db_session)

    overview = _visao(db_session, project)

    assert not overview.is_portfolio
    assert not overview.is_empty
    assert overview.scope_label == f"{project.code} · {project.name}"
    assert [row.number for row in overview.contracts] == [
        "CT-2026-011",
        "CT-2026-012",
        "CT-2026-014",
    ]

    first = overview.contracts[0]
    assert (first.current_value_cents, first.measured_cents, first.balance_to_invoice_cents) == (
        345_000_000,
        289_800_000,
        55_200_000,
    )
    assert first.measured_pct == D("84.0")
    assert (first.days_added, first.original_end, first.current_end) == (
        21,
        date(2026, 10, 30),
        date(2026, 11, 20),
    )
    assert first.last_evaluation is not None
    assert (first.last_evaluation.score, first.last_evaluation.score_class) == (83, "B")

    third = overview.contracts[2]
    assert (third.open_claims, third.exposure_cents) == (2, 60_500_000)
    assert third.last_evaluation is not None
    assert (third.last_evaluation.score, third.last_evaluation.score_class) == (63, "C")

    assert [row.code for row in overview.claims] == [
        "CLM-TN-2026-0005",
        "CLM-TN-2026-0004",
        "CLM-TN-2026-0003",
        "CLM-TN-2026-0002",
        "CLM-TN-2026-0001",
    ]
    late = next(row for row in overview.claims if row.code == "CLM-TN-2026-0003")
    assert (late.notification_days, late.notification_late, late.is_open) == (56, True, True)
    on_time = next(row for row in overview.claims if row.code == "CLM-TN-2026-0001")
    assert (on_time.notification_days, on_time.notification_late, on_time.is_open) == (
        14,
        False,
        True,
    )
    assert (on_time.claimed_cents, on_time.recognized_cents) == (18_500_000, None)

    assert [
        (row.code, row.claim_code, row.requested_days, row.granted_days, row.is_open)
        for row in overview.extensions
    ] == [
        ("EOT-TN-2026-0003", "CLM-TN-2026-0005", 21, 21, False),
        ("EOT-TN-2026-0002", "CLM-TN-2026-0003", 45, None, True),
        ("EOT-TN-2026-0001", "CLM-TN-2026-0004", 30, 21, False),
    ]

    assert [row.number for row in overview.milestones] == ["M1", "M2", "M3", "M4", "M5", "M6"]
    assert [row.value_cents for row in overview.milestones] == [
        34_500_000,
        69_000_000,
        86_250_000,
        100_050_000,
        41_400_000,
        13_800_000,
    ]
    m5 = overview.milestones[4]
    assert (m5.is_late, m5.late_days, m5.expected_on) == (True, 5, date(2026, 9, 20))
    m6 = overview.milestones[5]
    assert (m6.is_late, m6.late_days) == (False, 0)

    assert len(overview.evaluations) == 6
    assert overview.evaluations[0].contract_number == "CT-2026-011"
    assert overview.evaluations[0].view.period == date(2026, 9, 1)

    assert overview.summary == calculations.ContractsSummary(
        contracts=3,
        exposure_cents=60_500_000,
        open_claims=2,
        late_notifications=1,
        late_milestones=1,
        contractors_c_or_d=1,
    )
    assert overview.indicators == calculations.ContractIndicators(
        contractor_exposure_cents=60_500_000,
        client_exposure_cents=0,
        recognition_rate=D("78.6"),
        average_resolution_days=49,
        requested_days=96,
        granted_days=42,
        extension_percent=D("4.9"),
        approved_not_invoiced_cents=0,
        paid_forecast_percent=D("57.3"),
        average_score=D("75.3"),
    )


def test_portfolio_traz_todos_os_contratos_e_os_indicadores_da_carga(
    db_session: Session,
) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)

    overview = _visao(db_session, None)

    assert overview.is_portfolio
    assert overview.scope_label == "Portfólio"
    assert [row.number for row in overview.contracts] == [
        "CT-2026-011",
        "CT-2026-012",
        "CT-2026-014",
        "CT-2026-020",
        "CT-2026-021",
        "CT-2026-022",
        "CT-2026-026",
        "CT-2026-027",
        "CT-2026-028",
    ]
    assert len(overview.claims) == 7
    assert len(overview.extensions) == 4
    assert len(overview.milestones) == 14
    assert len(overview.evaluations) == 10

    assert overview.summary == calculations.ContractsSummary(
        contracts=9,
        exposure_cents=106_500_000,
        open_claims=4,
        late_notifications=1,
        late_milestones=1,
        contractors_c_or_d=3,
    )
    assert overview.indicators == calculations.ContractIndicators(
        contractor_exposure_cents=106_500_000,
        client_exposure_cents=0,
        recognition_rate=D("78.6"),
        average_resolution_days=49,
        requested_days=111,
        granted_days=42,
        extension_percent=D("1.9"),
        approved_not_invoiced_cents=107_000_000,
        paid_forecast_percent=D("55.2"),
        average_score=D("71.7"),
    )


def test_leitura_exige_o_modulo_e_recusa_projeto_desconhecido(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=DEMO_ANCHOR)
    project = _projeto(db_session)

    overview = service.contracts_overview(
        db_session,
        user=_usuario(GeneralProfile.VIEWER),
        scope=_escopo(project),
        reference_date=DEMO_ANCHOR,
    )
    assert overview.contracts

    fornecedor = _usuario(GeneralProfile.VIEWER, Bond.SUPPLIER)
    with pytest.raises(AccessDeniedError):
        service.contracts_overview(
            db_session, user=fornecedor, scope=_escopo(project), reference_date=DEMO_ANCHOR
        )

    with pytest.raises(InvalidDataError):
        service.contracts_overview(
            db_session,
            user=_usuario(),
            scope=Scope(project_id=999_999, source="url"),
            reference_date=DEMO_ANCHOR,
        )
