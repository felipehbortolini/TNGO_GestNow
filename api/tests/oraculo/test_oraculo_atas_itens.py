"""Oráculo dos itens das atas (ISSUE-022): os números do protótipo em 25/09/2026.

Valores obtidos das coleções ``atas`` e ``acoes`` do protótipo: 28 itens com ``ataId``, todos de
origem ``Ata`` e com a referência no número da ata; a ata TN-2026-0028 tem cinco itens, numerados
1.1 a 3.1 pelos três grupos (Obras civis, Montagem e HSE).
"""

from __future__ import annotations

from sqlalchemy import func, select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.central_acoes import minutes_service
from src.modulos.central_acoes.models import Action, Minutes
from src.modulos.configuracoes import service as configuracoes
from tests.oraculo import OracleContext, register_check

EXPECTED_ITEMS = 28
NUMBER_WITH_ITEMS = "TN-2026-0028"
EXPECTED_NUMBERS = ["1.1", "1.2", "2.1", "2.2", "3.1"]
EXPECTED_GROUPS = ["Obras civis", "Montagem", "HSE"]


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


def _afirmar_itens_das_atas(context: OracleContext) -> None:
    session = context.session
    total = session.scalar(
        select(func.count()).select_from(Action).where(Action.ata_id.is_not(None))
    )
    assert total == EXPECTED_ITEMS, "28 itens de ata no prototipo"

    minutes = session.scalars(
        select(Minutes).where(Minutes.number == NUMBER_WITH_ITEMS, Minutes.revision == 0)
    ).one()
    listing = minutes_service.list_items(
        session,
        user=_admin(context),
        minutes_id=minutes.id,
        reference_date=context.reference_date,
    )
    assert [item.item for group in listing.groups for item in group.items] == EXPECTED_NUMBERS
    assert [group.name for group in listing.groups] == EXPECTED_GROUPS


def _afirmar_origem_das_acoes_de_ata(context: OracleContext) -> None:
    session = context.session
    pairs = session.execute(
        select(Action.origin, Action.origin_ref, Minutes.number)
        .join(Minutes, Minutes.id == Action.ata_id)
        .where(Action.ata_id.is_not(None))
    ).all()
    assert len(pairs) == EXPECTED_ITEMS
    assert all(origin == "Ata" and reference == number for origin, reference, number in pairs), (
        "toda acao de ata tem origem Ata e referencia no numero da ata"
    )


register_check("itens das atas: numeracao por grupo", _afirmar_itens_das_atas)
register_check("itens das atas: origem Ata e referencia", _afirmar_origem_das_acoes_de_ata)
