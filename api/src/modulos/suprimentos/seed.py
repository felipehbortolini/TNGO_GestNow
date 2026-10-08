"""Part of the supplier register in the demonstration load (ISSUE-057, D6/Q15).

The 17 qualifications of the prototype (``fornecedores``), with their categories, documents and
the situation history, enter through the facade (``core.recording``, inside the caller's
transaction), with the companies of the platform part and the people of the mock. Every date is
shifted by ``shift_date``; on 25/09/2026 (the oracle) nothing moves and the dates of the mock
come out whole. The companies of the Weekly Scheduling (the demonstration adds three) stay
without qualification and show up as "Sem qualificação", as any company of the register does.

The file of a document is an ``anexo`` (D5a): the load keeps the metadata of the document only,
as the prototype kept the name, because the demonstration has no files.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core import recording
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.suprimentos.models import (
    Supplier,
    SupplierCategory,
    SupplierDocument,
    SupplierHistory,
)

PART_NAME = "suprimentos-fornecedores"


@dataclass(frozen=True)
class _Lookups:
    """What the conversion needs to turn ids of the prototype into ids of the database."""

    user: User
    reference_date: date
    companies: Mapping[int, int]
    people: Mapping[int, int]

    def shifted(self, value: str | None) -> date | None:
        """A date of the prototype moved to the reference date of the run."""
        if not value:
            return None
        return shift_date(date.fromisoformat(value), self.reference_date)

    def person(self, mock_id: int | None) -> int | None:
        """The person of the register behind an id of the prototype."""
        return None if mock_id is None else self.people[mock_id]


def load(session: Session, reference_date: date) -> None:
    """Write the qualifications of the prototype, with their history."""
    lookups = _lookups(session, reference_date)
    for source in prototype_collection("fornecedores"):
        _record(session, lookups, source)


def _lookups(session: Session, reference_date: date) -> _Lookups:
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if access is None:
        message = f"O Admin da demonstração ({ADMIN_EMAIL}) não está no cadastro."
        raise LookupError(message)
    user = User(
        id=access.id,
        person_id=access.person_id,
        name=access.name,
        email=access.email,
        general_profile=GeneralProfile(access.general_profile),
        bond=Bond(access.bond),
        company_id=access.company_id,
    )
    ids_by_name = {
        company.name: company.id for company in configuracoes.list_company_summaries(session)
    }
    ids_by_email = {
        person.email.lower(): person.id for person in configuracoes.list_people(session)
    }
    return _Lookups(
        user=user,
        reference_date=reference_date,
        companies={
            company["id"]: ids_by_name[company["nome"]]
            for company in prototype_collection("empresas")
        },
        people={
            person["id"]: ids_by_email[person["email"].lower()]
            for person in prototype_collection("pessoas")
        },
    )


def _record(session: Session, lookups: _Lookups, source: Mapping[str, Any]) -> None:
    supplier = recording.create(
        session,
        user_id=lookups.user.id,
        record=Supplier(
            company_id=lookups.companies[source["empresaId"]],
            situation=source["situacao"],
            validity=lookups.shifted(source.get("validadeQualificacao")),
            observation=source.get("observacao"),
        ),
    )
    for category in source["categorias"]:
        recording.create(
            session,
            user_id=lookups.user.id,
            record=SupplierCategory(supplier_id=supplier.id, category=category),
        )
    for document in source["documentos"]:
        recording.create(
            session,
            user_id=lookups.user.id,
            record=SupplierDocument(
                supplier_id=supplier.id,
                name=document["nome"],
                validity=lookups.shifted(document.get("validade")),
            ),
        )
    for entry in source.get("historico", ()):
        recording.create(
            session,
            user_id=lookups.user.id,
            record=SupplierHistory(
                supplier_id=supplier.id,
                by_id=lookups.person(entry["porId"]),
                on=lookups.shifted(entry["data"]),
                from_situation=entry.get("de"),
                to_situation=entry["para"],
                justification=entry["justificativa"],
            ),
        )


register(PART_NAME, load)
