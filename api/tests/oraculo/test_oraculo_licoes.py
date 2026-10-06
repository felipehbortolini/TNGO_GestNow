"""Oráculo das lições aprendidas (ISSUE-027): os 10 registros do protótipo e o seu fluxo.

Os códigos saem da numeração de cada projeto (``LA-TN-2026-...``) e são os do protótipo; a
situação de cada um é a que ele já tinha, e os reusos contados no cartão viram aplicações. A
origem de módulo vira a origem do modelo e o número do registro (``Claim CLM-...`` →
``Contrato``/``CLM-...``).
"""

from __future__ import annotations

from sqlalchemy import func, select

from src.modulos.governanca import lessons_models as lm
from src.modulos.governanca.lessons_models import Lesson, LessonApplication
from tests.oraculo import OracleContext, register_check

EXPECTED_CODES = (
    "LA-TN-2026-0001",
    "LA-TN-2026-0002",
    "LA-TN-2026-0003",
    "LA-TN-2026-0004",
    "LA-TN-2026-0005",
    "LA-TN-2026-0006",
    "LA-TN-2026-0007",
    "LA-TN-2026-0008",
    "LA-CB-2026-0001",
    "LA-TR-2026-0001",
)
EXPECTED_PUBLISHED = 4
EXPECTED_CORPORATE = 9
EXPECTED_REUSES = 6


def _afirmar_licoes(context: OracleContext) -> None:
    lessons = context.session.scalars(select(Lesson).order_by(Lesson.id)).all()

    assert [lesson.code for lesson in lessons] == list(EXPECTED_CODES), "codigos do prototipo"
    assert (
        sum(1 for lesson in lessons if lesson.situation == lm.SITUATION_PUBLISHED)
        == EXPECTED_PUBLISHED
    ), "licoes publicadas"
    assert (
        sum(1 for lesson in lessons if lesson.applicability == lm.APPLICABILITY_CORPORATE)
        == EXPECTED_CORPORATE
    ), "licoes corporativas"
    reuses = context.session.scalar(select(func.count()).select_from(LessonApplication))
    assert reuses == EXPECTED_REUSES, "reusos do prototipo"
    first = lessons[0]
    assert (first.origin, first.origin_ref) == (
        lm.ORIGIN_CONTRACT,
        "CLM-TN-2026-0004",
    ), "origem rastreavel da primeira licao"


register_check("licoes: codigos, situacoes e reusos do prototipo", _afirmar_licoes)
