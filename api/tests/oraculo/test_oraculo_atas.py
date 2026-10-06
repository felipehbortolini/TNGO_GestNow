"""Oráculo das atas da Central (ISSUE-021): os números do protótipo em 25/09/2026.

Valores obtidos executando ``statusAcao`` do protótipo sobre os mocks (``atas`` e ``acoes``) e a
regra de ``atas.js``: só a revisão mais recente de cada número; "Ações abertas" são as ações (nunca
as informações) sem conclusão, e "Atrasadas" as de status atrasada. São 9 revisões em 8 atas: o
número TN-2026-0031 tem a Rev 0 e a Rev 1.
"""

from __future__ import annotations

from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.central_acoes import minutes_service
from src.modulos.central_acoes.validation import MinutesFilters
from src.modulos.configuracoes import service as configuracoes
from tests.oraculo import OracleContext, register_check

# número da ata e revisão vigente -> (ações abertas, atrasadas)
EXPECTED_ROWS = {
    ("TN-2026-0028", 0): (1, 1),
    ("TN-2026-0031", 1): (1, 0),
    ("TN-2026-0036", 0): (3, 1),
    ("TN-2026-0038", 0): (1, 0),
    ("TN-2026-0034", 0): (0, 0),
    ("CB-2026-0001", 0): (1, 1),
    ("CB-2026-0002", 0): (4, 2),
    ("TR-2026-0001", 0): (3, 1),
}

# número e revisão -> participantes da lista de presença
EXPECTED_ATTENDANCE = {
    ("TN-2026-0028", 0): 7,
    ("TN-2026-0031", 1): 5,
    ("TN-2026-0036", 0): 5,
    ("TN-2026-0038", 0): 5,
    ("TN-2026-0034", 0): 6,
    ("CB-2026-0001", 0): 7,
    ("CB-2026-0002", 0): 6,
    ("TR-2026-0001", 0): 6,
}


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


def _portfolio(context: OracleContext) -> minutes_service.MinutesListing:
    return minutes_service.list_minutes(
        context.session,
        user=_admin(context),
        scope=Scope(project_id=None, source="padrao"),
        filters=MinutesFilters(),
        reference_date=context.reference_date,
    )


def _afirmar_atas_vigentes(context: OracleContext) -> None:
    listing = _portfolio(context)
    assert listing.total == 8, "8 atas vigentes (9 revisoes, TN-2026-0031 tem duas)"
    found = {
        (line.record.number, line.record.revision): (line.open_count, line.overdue_count)
        for line in listing.rows
    }
    assert found == EXPECTED_ROWS, "revisao vigente e acoes abertas e atrasadas de cada ata"


def _afirmar_atas_por_projeto(context: OracleContext) -> None:
    listing = _portfolio(context)
    by_project: dict[str, int] = {}
    for line in listing.rows:
        code = line.project_label.split(" · ")[0]
        by_project[code] = by_project.get(code, 0) + 1
    assert by_project == {"TN-2026-014": 5, "TN-2026-021": 2, "TN-2026-027": 1}, "atas por projeto"


def _afirmar_lista_de_presenca(context: OracleContext) -> None:
    listing = _portfolio(context)
    user = _admin(context)
    for line in listing.rows:
        sheet = minutes_service.find_minutes(
            context.session,
            user=user,
            minutes_id=line.record.id,
            reference_date=context.reference_date,
        )
        assert sheet is not None
        key = (line.record.number, line.record.revision)
        assert len(sheet.attendees) == EXPECTED_ATTENDANCE[key], f"presenca da ata {key}"
        assert sheet.is_latest, f"a ata {key} e a revisao vigente"


register_check("atas vigentes e acoes por ata", _afirmar_atas_vigentes)
register_check("atas por projeto", _afirmar_atas_por_projeto)
register_check("lista de presenca das atas", _afirmar_lista_de_presenca)
