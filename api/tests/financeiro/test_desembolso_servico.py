"""Fachada do cronograma de desembolso (ISSUE-043, HU-091): visão, carteira e envio.

O cenário é o do protótipo: a curva financeira congela R$ 44,6 mi, o ERP acumula R$ 28,7 mi até
setembro e a projeção no término fecha em R$ 45,255 mi, deixando R$ 16,555 mi a desembolsar. O
saldo de cada item é distribuído pelos meses depois do corte; o contrato com marcos futuros usa
os marcos e o que sobrar segue o perfil da projeção; o envio à tesouraria fica na trilha como
"simulado" enquanto o envio real está desligado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry, Notification
from src.core.notification import SIMULATED
from src.core.rbac import GeneralProfile
from src.core.scope import Scope
from src.modulos.financeiro import calculations, service
from src.modulos.financeiro.models import (
    Contract,
    ContractPaymentMilestone,
    CurvaFinanceiraMonth,
    CurvaFinanceiraRevision,
    EacRevision,
    EacRevisionItem,
)
from src.modulos.planejamento import service as planejamento
from src.modulos.planejamento.models import EapItem, EapMeasurement, EapRevision, EapRevisionItem
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario, user_of
from tests.identidades import criar_empresa

D = Decimal
HOJE = REFERENCE_DATE
PORTFOLIO = Scope(project_id=None, source="padrao")
JUSTIFICATIVA = "Revisão de teste do cronograma de desembolso."
BAC = 4_460_000_000
PROJECTION = 4_525_500_000
AC = 2_870_000_000
SALDO = PROJECTION - AC
SECOND_TOTAL = 2_000_000_000

PROFILE = (
    D("2.1"),
    D("5.4"),
    D("10.2"),
    D("16.8"),
    D("24.5"),
    D("33.0"),
    D("42.1"),
    D("54.0"),
    D("65.7"),
    D("75.8"),
    D("84.2"),
    D("90.6"),
    D("95.1"),
    D("98.4"),
    D("100"),
    D("100"),
)
MONTHS = (
    date(2026, 1, 1),
    date(2026, 2, 1),
    date(2026, 3, 1),
    date(2026, 4, 1),
    date(2026, 5, 1),
    date(2026, 6, 1),
    date(2026, 7, 1),
    date(2026, 8, 1),
    date(2026, 9, 1),
    date(2026, 10, 1),
    date(2026, 11, 1),
    date(2026, 12, 1),
    date(2027, 1, 1),
    date(2027, 2, 1),
    date(2027, 3, 1),
    date(2027, 4, 1),
)
PLANNED = calculations.curva_financeira_planejado(PROFILE, BAC)
REAL_PCT = ("2.1", "5.4", "10.2", "16.8", "24.5", "33.0", "42.1", "54.0", "61.8")
COMMITTED_DELTAS = (
    448_000_000,
    920_000_000,
    0,
    652_000_000,
    480_000_000,
    800_000_000,
    400_000_000,
    260_000_000,
    153_000_000,
)
ACTUAL_DELTAS = (
    90_000_000,
    155_000_000,
    195_000_000,
    260_000_000,
    310_000_000,
    350_000_000,
    400_000_000,
    520_000_000,
    590_000_000,
)
SECOND_MONTHS = tuple(date(2026, mes, 1) for mes in range(1, 13))
SECOND_PLANNED = tuple(SECOND_TOTAL * (index + 1) // 12 for index in range(12))
SECOND_REAL_PCT = ("10", "15", "20", "25", "30", "35", "40", "45", "50")


def _escopo(project) -> Scope:
    return Scope(project_id=project.id, source="url")


def _visao(cenario: EacScenario, scope: Scope | None = None) -> service.DisbursementOverview:
    return service.disbursement_overview(
        cenario.session, scope=scope or _escopo(cenario.first), reference_date=HOJE
    )


def _linha(view: service.DisbursementOverview, code: str) -> service.DisbursementItem:
    return next(row for row in view.items if row.code == code)


def _fisica(cenario: EacScenario, *, project=None, real_pct=REAL_PCT) -> None:
    """O pacote com as medições mensais até setembro e a curva física congelada."""
    projeto = project or cenario.first
    session = cenario.session
    item = EapItem(
        project_id=projeto.id,
        code="1.1.1",
        description="Estacas",
        level=3,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("100"),
        predicted=D("100"),
        start=date(2026, 1, 1),
        finish=date(2026, 12, 31),
        quantity=D("100"),
        executed=D("100"),
    )
    session.add(item)
    session.flush()
    revision = EapRevision(
        project_id=projeto.id,
        approved_by_id=projeto.manager_id,
        revision=0,
        revision_date=date(2026, 1, 5),
        alteration="Linha de base",
        justification="Linha de base aprovada no teste do desembolso.",
    )
    session.add(revision)
    session.flush()
    session.add(EapRevisionItem(revision_id=revision.id, item_id=item.id, weight=D("100")))
    for index, pct in enumerate(real_pct):
        session.add(
            EapMeasurement(
                item_id=item.id,
                author_id=cenario.member.person_id,
                measured_on=date(2026, index + 1, 15),
                from_pct=D("0"),
                to_pct=D(pct),
                note="Boletim",
            )
        )
    session.flush()
    planejamento.freeze_curve(
        session, project_id=projeto.id, revision_id=revision.id, reference_date=HOJE
    )


def _financeira(cenario: EacScenario, *, project=None, total_cents: int, months, planned) -> None:
    """A revisão da EAC e a curva financeira congelada com o planejado exato do cenário."""
    projeto = project or cenario.first
    session = cenario.session
    record = EacRevision(
        project_id=projeto.id,
        change_id=None,
        approved_by_id=projeto.manager_id,
        revision=0,
        revision_date=date(2026, 1, 5),
        justification=JUSTIFICATIVA,
    )
    session.add(record)
    session.flush()
    session.add(
        EacRevisionItem(
            revision_id=record.id,
            item_id=cenario.items[f"{projeto.code}:1.1.1"],
            base_cents=total_cents,
        )
    )
    session.flush()
    curve = CurvaFinanceiraRevision(project_id=projeto.id, eac_revision_id=record.id)
    session.add(curve)
    session.flush()
    session.add_all(
        CurvaFinanceiraMonth(revision_id=curve.id, month=month, planned_cents=value)
        for month, value in zip(months, planned, strict=True)
    )
    session.flush()


def _erp_projeto(cenario: EacScenario) -> None:
    linhas = tuple(
        service.ErpCostLine(
            item_id=cenario.items[f"{cenario.first.code}:1.1.1"],
            month=date(2026, index + 1, 1),
            committed_cents=committed,
            actual_cents=actual,
            projection_cents=PROJECTION if index == len(ACTUAL_DELTAS) - 1 else None,
        )
        for index, (committed, actual) in enumerate(
            zip(COMMITTED_DELTAS, ACTUAL_DELTAS, strict=True)
        )
    )
    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.first.id,
        linhas=linhas,
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )


def _erp_segundo(cenario: EacScenario) -> None:
    item_id = cenario.items[f"{cenario.second.code}:1.1.1"]
    linhas = (
        service.ErpCostLine(
            item_id=item_id,
            month=date(2026, 1, 1),
            committed_cents=1_200_000_000,
            actual_cents=100_000_000,
        ),
        *(
            service.ErpCostLine(
                item_id=item_id,
                month=date(2026, index, 1),
                actual_cents=100_000_000,
            )
            for index in range(2, 10)
        ),
    )
    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.second.id,
        linhas=linhas,
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )


def _contrato(cenario: EacScenario, *, item_code: str, original_cents: int) -> Contract:
    session = cenario.session
    empresa = criar_empresa(session, nome=f"Contratada {item_code}")
    contrato = Contract(
        project_id=cenario.first.id,
        company_id=empresa.id,
        eac_item_id=cenario.items[f"{cenario.first.code}:{item_code}"],
        manager_id=cenario.first.manager_id,
        fiscal_id=cenario.member.person_id,
        number=f"CT-2026-{item_code}",
        object="Contrato de teste do desembolso",
        modality="Preço global",
        original_value_cents=original_cents,
        start=date(2026, 1, 2),
        original_end=date(2026, 12, 31),
        current_end=date(2026, 12, 31),
        retention_pct=5,
        claim_notice_days=30,
        situation="Em execução",
    )
    session.add(contrato)
    session.flush()
    return contrato


def _marco(cenario: EacScenario, contrato: Contract, *, numero: str, pct: int, prevista: date):
    marco = ContractPaymentMilestone(
        contract_id=contrato.id,
        number=numero,
        description="Marco de teste",
        acceptance_criteria="Evidência aprovada",
        pct=pct,
        expected_on=prevista,
        situation=calculations.MILESTONE_FORECAST,
    )
    cenario.session.add(marco)
    cenario.session.flush()
    return marco


@pytest.fixture
def cenario_desembolso(cenario: EacScenario) -> EacScenario:
    _fisica(cenario)
    _financeira(cenario, total_cents=BAC, months=MONTHS, planned=PLANNED)
    _erp_projeto(cenario)
    return cenario


def _membro(cenario: EacScenario):
    return user_of(cenario.member, cenario.session, GeneralProfile.MEMBER)


def _visualizador(cenario: EacScenario):
    return user_of(cenario.viewer, cenario.session, GeneralProfile.VIEWER)


# ── A visão do projeto ───────────────────────────────────────────────────


def test_o_cronograma_do_projeto_tem_os_numeros_do_cenario(
    cenario_desembolso: EacScenario,
) -> None:
    view = _visao(cenario_desembolso)

    assert not view.is_empty
    assert view.cut_month == date(2026, 9, 1)
    assert view.months == MONTHS
    assert view.future_months == MONTHS[9:]
    assert view.balance_cents == SALDO
    assert view.projection_cents == PROJECTION
    assert view.actual_until_cut_cents == AC

    historico = {linha.month: linha for linha in view.histogram}
    assert historico[date(2026, 9, 1)].planned_cents == PLANNED[8] - PLANNED[7]
    assert historico[date(2026, 9, 1)].actual_cents == ACTUAL_DELTAS[8]
    assert historico[date(2026, 10, 1)].planned_cents == PLANNED[9] - PLANNED[8]
    assert historico[date(2026, 10, 1)].actual_cents is None

    item = _linha(view, "1.1.1")
    assert item.balance_cents == SALDO
    assert sum(item.amounts) == SALDO
    pacote = _linha(view, "1")
    assert pacote.balance_cents == SALDO
    assert pacote.amounts == item.amounts

    assert view.totals == tuple(
        sum(row.amounts[index] for row in view.items if row.level == 1)
        for index in range(len(view.future_months))
    )
    assert sum(view.totals) == view.balance_cents

    kpis = view.kpis
    assert kpis is not None
    assert kpis.actual_until_cut_cents == AC
    assert kpis.projection_cents == PROJECTION
    assert kpis.actual_pct == D("63.4")
    assert kpis.cut_actual_cents == ACTUAL_DELTAS[8]
    assert kpis.cut_planned_cents == PLANNED[8] - PLANNED[7]
    assert kpis.planned_until_cut_cents == PLANNED[8]
    assert kpis.planned_balance_cents == BAC - PLANNED[8]
    assert kpis.next_three_cents == sum(view.totals[:3])
    assert kpis.peak_month == view.future_months[list(view.totals).index(max(view.totals))]


def test_contrato_com_marco_futuro_usa_o_marco(cenario_desembolso: EacScenario) -> None:
    contrato = _contrato(cenario_desembolso, item_code="1.1.1", original_cents=SALDO)
    _marco(cenario_desembolso, contrato, numero="M1", pct=100, prevista=date(2026, 10, 20))

    view = _visao(cenario_desembolso)

    item = _linha(view, "1.1.1")
    assert item.amounts[0] == SALDO
    assert sum(item.amounts) == SALDO


def test_o_marco_passado_nao_entra_na_distribuicao(cenario_desembolso: EacScenario) -> None:
    antes = _visao(cenario_desembolso)
    contrato = _contrato(cenario_desembolso, item_code="1.1.1", original_cents=SALDO)
    _marco(cenario_desembolso, contrato, numero="M1", pct=100, prevista=date(2026, 9, 10))

    depois = _visao(cenario_desembolso)

    assert _linha(depois, "1.1.1").amounts == _linha(antes, "1.1.1").amounts


# ── A carteira ───────────────────────────────────────────────────────────


def test_carteira_une_os_meses_e_soma_os_projetos(cenario_desembolso: EacScenario) -> None:
    _fisica(cenario_desembolso, project=cenario_desembolso.second, real_pct=SECOND_REAL_PCT)
    _financeira(
        cenario_desembolso,
        project=cenario_desembolso.second,
        total_cents=SECOND_TOTAL,
        months=SECOND_MONTHS,
        planned=SECOND_PLANNED,
    )
    _erp_segundo(cenario_desembolso)

    projeto = _visao(cenario_desembolso)
    outro = _visao(cenario_desembolso, _escopo(cenario_desembolso.second))
    carteira = _visao(cenario_desembolso, PORTFOLIO)

    assert carteira.is_portfolio
    assert carteira.scope_label == "Portfólio"
    assert carteira.months == MONTHS
    assert carteira.cut_month == date(2026, 9, 1)
    assert carteira.balance_cents == projeto.balance_cents + outro.balance_cents
    assert carteira.projection_cents == projeto.projection_cents + outro.projection_cents
    assert carteira.actual_until_cut_cents == (
        projeto.actual_until_cut_cents + outro.actual_until_cut_cents
    )
    assert [row.code for row in carteira.items] == ["1", "1.1", "1.2", "2", "2.1"]
    assert carteira.items[0].project_label == "TN-EAC-001 · Fábrica de teste"
    assert carteira.items[0].amounts == projeto.totals
    assert carteira.items[3].amounts[3:] == (0,) * 4
    assert sum(carteira.items[3].amounts) == outro.balance_cents
    assert carteira.items[0].amounts == tuple(
        first + second
        for first, second in zip(carteira.items[1].amounts, carteira.items[2].amounts, strict=True)
    )
    assert sum(carteira.totals) == carteira.balance_cents
    assert carteira.kpis is not None
    assert carteira.kpis.actual_until_cut_cents == AC + 900_000_000


# ── Vazio de origem ──────────────────────────────────────────────────────


def test_sem_curva_a_visao_e_vazia(cenario: EacScenario) -> None:
    projeto = _visao(cenario)
    carteira = _visao(cenario, PORTFOLIO)

    assert projeto.is_empty
    assert projeto.kpis is None
    assert projeto.items == ()
    assert carteira.is_empty
    assert carteira.items == ()


# ── Envio à tesouraria ───────────────────────────────────────────────────


def test_o_envio_a_tesouraria_registra_na_trilha_com_simulado(
    cenario_desembolso: EacScenario,
) -> None:
    resultado = service.send_to_treasury(
        cenario_desembolso.session,
        user=_membro(cenario_desembolso),
        scope=_escopo(cenario_desembolso.first),
        reference_date=HOJE,
    )

    assert resultado.situation == SIMULATED
    assert "simulado" in resultado.notice.lower()
    assert resultado.toast_kind == "aviso"

    registro = cenario_desembolso.session.get(Notification, resultado.notification_id)
    assert registro is not None
    assert registro.kind == "tesouraria"
    assert registro.project_id == cenario_desembolso.first.id
    assert registro.recipients == "tesouraria@exemplo.com"
    assert registro.subject == "Cronograma de desembolso de out/26 em diante"
    assert registro.body == (
        "Cronograma de desembolso atualizado com o fechamento de set/26. "
        "Saldo a desembolsar: R$ 16.555.000,00."
    )

    linhas = cenario_desembolso.session.scalars(
        select(AuditEntry).where(
            AuditEntry.entity == "notificacao",
            AuditEntry.record_id == resultado.notification_id,
        )
    ).all()
    assert len(linhas) == 1
    assert linhas[0].after is not None
    assert linhas[0].after["situacao"] == "simulado"
    assert linhas[0].after["destinatarios"] == "tesouraria@exemplo.com"
    assert "erro" not in linhas[0].after


def test_o_envio_exige_perfil_com_escrita(cenario_desembolso: EacScenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.send_to_treasury(
            cenario_desembolso.session,
            user=_visualizador(cenario_desembolso),
            scope=_escopo(cenario_desembolso.first),
            reference_date=HOJE,
        )


def test_o_envio_no_portfolio_pede_o_projeto(cenario_desembolso: EacScenario) -> None:
    with pytest.raises(InvalidDataError):
        service.send_to_treasury(
            cenario_desembolso.session,
            user=_membro(cenario_desembolso),
            scope=PORTFOLIO,
            reference_date=HOJE,
        )


def test_o_envio_sem_cronograma_e_recusado(cenario: EacScenario) -> None:
    with pytest.raises(InvalidDataError):
        service.send_to_treasury(
            cenario.session,
            user=_membro(cenario),
            scope=_escopo(cenario.first),
            reference_date=HOJE,
        )
