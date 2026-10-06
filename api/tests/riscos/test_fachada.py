"""Fachada do Registro de riscos (ISSUE-064): permissão da exclusão e da restauração, categoria.

A exclusão é do Gestor e só o Admin restaura; as recusas por ação aberta e por risco encerrado ficam
cobertas pela regra pura (``is_active``) e pela contagem de ações da origem (Central de Ações).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.modulos.riscos import service
from src.modulos.riscos.validation import DeletionInput
from tests.governanca.apoio import colaborador, usuario_de

HOJE = date(2026, 10, 6)


def test_membro_nao_exclui_risco(db_session: Session) -> None:
    membro = usuario_de(colaborador(db_session, "membro.risco@example.invalid", "Membro"))

    with pytest.raises(AccessDeniedError):
        service.delete_risk(
            db_session,
            user=membro,
            code="RSK-TN-2026-0001",
            data=DeletionInput(reason="Criado por engano"),
            reference_date=HOJE,
        )


def test_gestor_nao_restaura_risco_excluido(db_session: Session) -> None:
    gestor = usuario_de(colaborador(db_session, "gestor.risco@example.invalid", "Gestor"))

    assert not service.can_see_deleted(gestor)
    with pytest.raises(AccessDeniedError):
        service.restore_risk(db_session, user=gestor, code="RSK-TN-2026-0001")


def test_so_o_admin_ve_os_excluidos(db_session: Session) -> None:
    admin = usuario_de(colaborador(db_session, "admin.risco@example.invalid", "Admin"))

    assert service.can_see_deleted(admin)


def test_categoria_nova_entra_no_catalogo_e_a_repetida_e_recusada(db_session: Session) -> None:
    membro = usuario_de(colaborador(db_session, "cat.risco@example.invalid", "Membro"))

    criada = service.create_category(db_session, user=membro, group="Técnico", name="Geotecnia")

    assert criada.id is not None
    assert any(item.name == "Geotecnia" for item in service.list_categories(db_session))
    with pytest.raises(InvalidDataError):
        service.create_category(db_session, user=membro, group="técnico", name="GEOTECNIA")
