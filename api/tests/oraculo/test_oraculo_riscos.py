"""Oráculo do Registro de riscos (ISSUE-064): os números do protótipo em 25/09/2026.

Valores obtidos executando ``severidade`` e ``vme`` do protótipo (``regras.js``) sobre
``mock-riscos.js`` e ``mock-config.js`` (escala Timenow, avaliação residual quando existe):
o projeto 1 (TN-2026-014) tem 7 riscos ativos (os riscos 8 e 9 estão encerrado e
materializado), 2 na faixa Crítico (3 e 4, esta uma oportunidade), 1 em Alto, 1 com revisão
vencida e exposição de R$ 3,4 mi, que soma só o VME das ameaças (a oportunidade fica fora).
"""

from __future__ import annotations

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from src.modulos.riscos import service
from tests.oraculo import OracleContext, register_check

PROJECT_CODE = "TN-2026-014"
EXPECTED_ACTIVE = 7
EXPECTED_CRITICAL_RESIDUAL = 2
EXPECTED_HIGH_RESIDUAL = 1
EXPECTED_OVERDUE = 1
EXPECTED_EXPOSURE_CENTS = 340_000_000


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


def _afirmar_riscos_do_projeto_1(context: OracleContext) -> None:
    project_id = context.session.scalars(
        select(Project.id).where(Project.code == PROJECT_CODE)
    ).one()
    summary = service.risk_summary(
        context.session,
        user=_admin(context),
        scope=Scope(project_id=project_id, source="padrao"),
        assessment="residual",
        reference_date=context.reference_date,
    )
    assert summary.active == EXPECTED_ACTIVE, "7 riscos ativos no projeto 1"
    assert summary.top.band.id == "critico"
    assert summary.top.total == EXPECTED_CRITICAL_RESIDUAL, "2 criticos no residual"
    assert summary.second is not None
    assert summary.second.total == EXPECTED_HIGH_RESIDUAL, "1 alto no residual"
    assert len(summary.overdue) == EXPECTED_OVERDUE, "1 revisao vencida"
    assert summary.exposure_cents == EXPECTED_EXPOSURE_CENTS, "exposicao de R$ 3,4 mi (ameacas)"


register_check("riscos: ativos, criticos e exposicao do projeto 1", _afirmar_riscos_do_projeto_1)
