"""Oráculo do painel de lições (ISSUE-028): os números de ``painelLicoes`` com a data do protótipo.

Valores obtidos de ``painelLicoes`` do protótipo (``api.js``) sobre o ``mock-governanca.js`` com a
data de referência 25/09/2026: 10 lições no portfólio, 4 publicadas (3 delas nos últimos 90 dias), 2
em validação, 6 reusos e taxa de reuso de 75,0%; a última lição é 24/09/2026 (1 dia); nenhum projeto
passou dos 90 dias sem registrar.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Person
from src.modulos.governanca import lessons_service
from tests.governanca.apoio import usuario_de
from tests.oraculo import OracleContext, register_check

EXPECTED_TOTAL = 10
EXPECTED_PUBLISHED = 4
EXPECTED_PUBLISHED_PERIOD = 3
EXPECTED_VALIDATING = 2
EXPECTED_REUSES = 6
EXPECTED_REUSE_RATE = Decimal("75.0")
EXPECTED_AVOID_COST_CENTS = 77_400_000
EXPECTED_LAST = date(2026, 9, 24)
EXPECTED_PHASES = (
    ("Iniciação", 0, 0, 0, 0),
    ("Engenharia", 2, 0, 2, 0),
    ("Suprimentos", 3, 3, 0, 1),
    ("Construção", 5, 1, 4, 3),
    ("Comissionamento", 0, 0, 0, 0),
    ("Encerramento", 0, 0, 0, 0),
)
EXPECTED_AREAS = (
    ("Riscos", 3),
    ("Aquisições", 2),
    ("Cronograma", 1),
    ("Custos", 1),
    ("Qualidade", 1),
    ("Comunicações", 1),
    ("SMS", 1),
)
EXPECTED_SITUATIONS = (
    ("Rascunho", 3),
    ("Em validação", 2),
    ("Validada", 1),
    ("Publicada", 4),
)
EXPECTED_MOST_REUSED = (
    ("LA-TN-2026-0002", 3),
    ("LA-TN-2026-0001", 2),
    ("LA-TN-2026-0003", 1),
)


def _admin(context: OracleContext):
    admin = context.session.scalars(
        select(Collaborator)
        .join(Person, Person.id == Collaborator.person_id)
        .where(Person.email == ADMIN_EMAIL)
    ).one()
    return usuario_de(admin)


def _afirmar_painel_de_licoes(context: OracleContext) -> None:
    painel = lessons_service.lesson_panel(
        context.session,
        user=_admin(context),
        scope=Scope(project_id=None, source="padrao"),
        reference_date=context.reference_date,
    )

    assert painel.total == EXPECTED_TOTAL, "10 licoes no portfolio"
    assert painel.published == EXPECTED_PUBLISHED, "publicadas"
    assert painel.published_in_period == EXPECTED_PUBLISHED_PERIOD, "publicadas nos 90 dias"
    assert painel.validating == EXPECTED_VALIDATING, "em validacao"
    assert painel.reuses == EXPECTED_REUSES, "reusos"
    assert painel.reuse_rate == EXPECTED_REUSE_RATE, "taxa de reuso"
    assert painel.avoid_impact_cents == EXPECTED_AVOID_COST_CENTS, "custo das licoes a evitar"
    assert painel.last_lesson == EXPECTED_LAST, "ultima licao"
    assert painel.days_without_record == 1, "dias desde a ultima licao"
    assert not painel.registration_alert, "1 dia nao dispara o alerta de 90"
    assert [
        (line.label, line.total, line.to_repeat, line.to_avoid, line.published)
        for line in painel.by_phase
    ] == list(EXPECTED_PHASES)
    assert [(line.label, line.total) for line in painel.by_area] == list(EXPECTED_AREAS)
    assert [(line.label, line.total) for line in painel.by_situation] == list(EXPECTED_SITUATIONS)
    assert [(item.code, item.reuses) for item in painel.most_reused] == list(EXPECTED_MOST_REUSED)
    assert painel.projects_without_record == (), "todos registraram dentro da janela"


register_check("licoes: painel do portfolio", _afirmar_painel_de_licoes)
