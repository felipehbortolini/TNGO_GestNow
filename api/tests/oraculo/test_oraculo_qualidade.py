"""Oráculo da Qualidade (ISSUE-068): as RNC abertas em 25/09/2026 no projeto 1.

Valores obtidos executando o fluxo do protótipo sobre ``mock-qualidade.js`` e
``mock-portfolio.js``: o projeto 1 (TN-2026-014) tem 4 RNC abertas — 0002 (em verificação de
eficácia, prevista para 05/10/2026), 0004 (ação corretiva, com o prazo de tratamento vencido em
17/09/2026), 0005 (em análise de causa) e 0006 (aberta) —, com os números, as severidades e os
prazos do mock; a 0004 é a única com o prazo vencido na data de corte.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from src.modulos.qualidade import service
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


def _afirmar_rncs_abertas_do_projeto_1(context: OracleContext) -> None:
    project_id = context.session.scalars(
        select(Project.id).where(Project.code == PROJECT_CODE)
    ).one()
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


register_check(
    "qualidade: as 4 RNC abertas do projeto 1 em 25/09/2026", _afirmar_rncs_abertas_do_projeto_1
)
