"""Oráculo da Qualidade (ISSUE-068, 069 e 070): as RNC, as inspeções e as auditorias.

Valores obtidos executando o fluxo do protótipo sobre ``mock-qualidade.js`` e
``mock-portfolio.js``: o projeto 1 (TN-2026-014) tem 4 RNC abertas — 0002 (em verificação de
eficácia, prevista para 05/10/2026), 0004 (ação corretiva, com o prazo de tratamento vencido em
17/09/2026), 0005 (em análise de causa) e 0006 (aberta) —, com os números, as severidades e os
prazos do mock; a 0004 é a única com o prazo vencido na data de corte. Nas inspeções, o projeto
1 tem 5 ITPs (4 aprovados pelo cliente) e 20 registros: 3 reprovados, 17 aprovados (a ressalva
incluída) e as três reprovações ligadas às RNC-TN-2026-0004, 0005 e 0002. Nas auditorias, o
projeto 1 tem 5 do programa (2 realizadas e 3 planejadas, com a AUD-TN-2026-05 atrasada em
15/09/2026), conformidade de 90,0% na AUD-TN-2026-01 e 82,9% na AUD-TN-2026-02, aderência ao
programa de 66,7% e as constatações ligando a AUD-TN-2026-01 à RNC-TN-2026-0001 (encerrada) e
a AUD-TN-2026-02 à RNC-TN-2026-0005 (ativa).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from src.modulos.qualidade import service
from src.modulos.qualidade.validation import AuditFilters, InspectionFilters, ItpFilters
from tests.oraculo import OracleContext, register_check

PROJECT_CODE = "TN-2026-014"
EXPECTED_OPEN = ("RNC-TN-2026-0002", "RNC-TN-2026-0004", "RNC-TN-2026-0005", "RNC-TN-2026-0006")
EXPECTED_DEADLINES = {
    "RNC-TN-2026-0002": date(2026, 8, 20),
    "RNC-TN-2026-0004": date(2026, 9, 17),
    "RNC-TN-2026-0005": date(2026, 10, 19),
    "RNC-TN-2026-0006": date(2026, 11, 7),
}
EXPECTED_OVERDUE = "RNC-TN-2026-0004"
EXPECTED_VERIFICATION = date(2026, 10, 5)

EXPECTED_ITPS = (
    "ITP-TN-CIV-01",
    "ITP-TN-ELE-01",
    "ITP-TN-INS-01",
    "ITP-TN-MEC-01",
    "ITP-TN-TUB-01",
)
EXPECTED_INSPECTION_LINKS = {
    "INS-2026-0145": "RNC-TN-2026-0004",
    "INS-2026-0155": "RNC-TN-2026-0005",
    "INS-2026-0117": "RNC-TN-2026-0002",
}

EXPECTED_AUDITS = (
    "AUD-TN-2026-01",
    "AUD-TN-2026-05",
    "AUD-TN-2026-02",
    "AUD-TN-2026-03",
    "AUD-TN-2026-04",
)
EXPECTED_AUDIT_CONFORMITY = {
    "AUD-TN-2026-01": Decimal("90.0"),
    "AUD-TN-2026-02": Decimal("82.9"),
}
EXPECTED_AUDIT_LINKS = {
    "AUD-TN-2026-01": "RNC-TN-2026-0001",
    "AUD-TN-2026-02": "RNC-TN-2026-0005",
}
EXPECTED_AUDIT_OVERDUE = "AUD-TN-2026-05"


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


def _project_id(context: OracleContext) -> int:
    return context.session.scalars(select(Project.id).where(Project.code == PROJECT_CODE)).one()


def _afirmar_rncs_abertas_do_projeto_1(context: OracleContext) -> None:
    project_id = _project_id(context)
    user = _admin(context)
    scope = Scope(project_id=project_id, source="padrao")
    summary = service.rnc_summary(
        context.session, user=user, scope=scope, reference_date=context.reference_date
    )
    assert summary.active == 4, "4 RNC abertas no projeto 1"
    assert summary.overdue == 1, "a 0004 vencida no corte"
    assert summary.critical == 0, "nenhuma critica no projeto 1"
    listagem = service.list_rncs(
        context.session,
        user=user,
        scope=scope,
        filters=service.RncFilters(situation="ativas"),
        reference_date=context.reference_date,
    )
    assert {linha.code for linha in listagem.lines} == set(EXPECTED_OPEN)
    assert [linha.code for linha in listagem.lines] == [
        "RNC-TN-2026-0006",
        "RNC-TN-2026-0005",
        "RNC-TN-2026-0004",
        "RNC-TN-2026-0002",
    ], "a lista vem da mais recente para a mais antiga, como o protótipo"
    for linha in listagem.lines:
        assert linha.deadline == EXPECTED_DEADLINES[linha.code], linha.code
        if linha.code == EXPECTED_OVERDUE:
            assert linha.overdue is True
        else:
            assert linha.overdue is False
    verificacao = next(linha for linha in listagem.lines if linha.code == "RNC-TN-2026-0002")
    assert verificacao.situation == "Verificação de eficácia"
    assert verificacao.verification_expected == EXPECTED_VERIFICATION


def _afirmar_inspecoes_do_projeto_1(context: OracleContext) -> None:
    project_id = _project_id(context)
    user = _admin(context)
    scope = Scope(project_id=project_id, source="padrao")

    summary = service.inspecoes_summary(
        context.session, user=user, scope=scope, reference_date=context.reference_date
    )
    assert summary.itps == 5, "5 ITPs no projeto 1"
    assert summary.itps_approved == 4, "o ITP-TN-INS-01 segue pendente"
    assert summary.points == 40, "os 40 pontos do mock"
    assert summary.covered_points == 15, "os pontos com ao menos um registro"
    assert summary.registered == 20, "20 inspeções no projeto 1"
    assert summary.approved == 17, "aprovadas com a ressalva incluída"
    assert summary.with_remark == 2, "duas com ressalva"
    assert summary.rejected == 3, "três reprovações"
    assert summary.rejected_open_rnc == 3, "as três RNC ligadas seguem abertas no corte"
    assert summary.approval_pct is not None and str(summary.approval_pct) == "85.0"

    itps = service.list_itps(
        context.session,
        user=user,
        scope=scope,
        filters=ItpFilters(),
        reference_date=context.reference_date,
    )
    assert [linha.code for linha in itps.lines] == list(EXPECTED_ITPS)
    pendente = next(linha for linha in itps.lines if linha.code == "ITP-TN-INS-01")
    assert pendente.approved_by_client is False
    assert pendente.total_points == 4

    listagem = service.list_inspections(
        context.session,
        user=user,
        scope=scope,
        filters=InspectionFilters(),
    )
    assert listagem.total == 20
    assert listagem.lines[0].code == "INS-2026-0164", "a mais recente no corte"
    for code, rnc_code in EXPECTED_INSPECTION_LINKS.items():
        linha = next(item for item in listagem.lines if item.code == code)
        assert linha.result == "Reprovado", code
        assert linha.rnc_code == rnc_code, code
        assert linha.rnc_situation not in ("Encerrada", "Cancelada"), code


def _afirmar_auditorias_do_projeto_1(context: OracleContext) -> None:
    project_id = _project_id(context)
    user = _admin(context)
    scope = Scope(project_id=project_id, source="padrao")

    summary = service.audit_summary(
        context.session, user=user, scope=scope, reference_date=context.reference_date
    )
    assert summary.due == 3, "as três previstas até 25/09/2026 (01, 02 e 05)"
    assert summary.done == 2, "as duas realizadas entre as previstas"
    assert summary.adherence is not None and str(summary.adherence) == "66.7"
    assert summary.overdue == 1, "a AUD-TN-2026-05 é a única atrasada"
    assert (summary.verified_items, summary.conforming_items) == (75, 65)
    assert summary.conformity is not None and str(summary.conformity) == "86.7"
    assert summary.nc == 2, "uma NC em cada auditoria realizada"
    assert summary.open_nc == 1, "só a RNC-TN-2026-0005 está ativa"
    assert summary.next_audit is not None
    assert summary.next_audit.code == "AUD-TN-2026-03"
    assert summary.next_audit.audit_date == date(2026, 10, 14)
    assert summary.next_audit.baseline_date == date(2026, 10, 14)

    listagem = service.list_audits(
        context.session,
        user=user,
        scope=scope,
        filters=AuditFilters(),
        reference_date=context.reference_date,
    )
    assert [linha.code for linha in listagem.lines] == list(EXPECTED_AUDITS), (
        "a lista vem da data mais antiga para a mais recente, como o protótipo"
    )
    por_codigo = {linha.code: linha for linha in listagem.lines}
    assert sum(1 for linha in listagem.lines if linha.situation == "Realizada") == 2
    assert sum(1 for linha in listagem.lines if linha.overdue) == 1

    atrasada = por_codigo[EXPECTED_AUDIT_OVERDUE]
    assert atrasada.audit_date == date(2026, 9, 15)
    assert atrasada.situation == "Planejada"

    for code, expected in EXPECTED_AUDIT_CONFORMITY.items():
        assert por_codigo[code].conformity_pct == expected, code
    for code, rnc_code in EXPECTED_AUDIT_LINKS.items():
        constatacao = por_codigo[code].findings[0]
        assert constatacao.finding_type == "Não conformidade", code
        assert constatacao.rnc_code == rnc_code, code
    assert por_codigo["AUD-TN-2026-01"].findings[0].rnc_active is False, "a 0001 está encerrada"
    assert por_codigo["AUD-TN-2026-02"].findings[0].rnc_active is True, "a 0005 está ativa"
    assert por_codigo["AUD-TN-2026-02"].open_nc == 1

    atrasadas = service.list_audits(
        context.session,
        user=user,
        scope=scope,
        filters=AuditFilters(situation="Atrasada"),
        reference_date=context.reference_date,
    )
    assert [linha.code for linha in atrasadas.lines] == [EXPECTED_AUDIT_OVERDUE]


register_check(
    "qualidade: as 4 RNC abertas do projeto 1 em 25/09/2026", _afirmar_rncs_abertas_do_projeto_1
)
register_check(
    "qualidade: os 5 ITPs e as 20 inspeções do projeto 1 em 25/09/2026",
    _afirmar_inspecoes_do_projeto_1,
)
register_check(
    "qualidade: as 5 auditorias do projeto 1 em 25/09/2026", _afirmar_auditorias_do_projeto_1
)
