"""The origin types of the attachments: how each module says who may read a record (D5a, ISSUE-012).

An attachment belongs to a record of some module (a punch item, a supplier
document, an HSE occurrence), kept in its row as the table and the id of the
record (``anexo.origem_tabela`` and ``origem_registro_id``). A module never
reads the tables of another (D5), so the platform cannot tell who may read a
record it does not own. Each module registers here its **origin type**: the table
it owns, its folder, and its **reading function**, the answer of its facade to
one question, *may this person read this record?*

The reading function receives the session, the user and the id of the record,
and answers in one of three ways:

* it returns the ``OriginRecord`` when the record exists and the user may read it;
* it returns ``None`` when the record does not exist;
* it raises ``AccessDeniedError`` when the record exists and the user may not read
  it: the cut by bond, the company of a supplier, whatever the module decides.

The platform asks before it lists, uploads or downloads, so the permission of an
attachment is always the permission of its record. Personal data (the HSE fields
of Q35) says so with ``OriginRecord.restricted``: only who holds
``Permission.VIEW_RESTRICTED`` (Gestor and Admin) lists and downloads those
attachments, while whoever may write still sends them.

A module registers its type when it is imported, at the end of its facade::

    attachment_origins.register(
        OriginType(table="punch_item", module="planejamento", read=read_punch_item)
    )

The registry is the same idea as the registry of the demonstration load
(``carga.registro``): the platform owns the mechanism, each module its entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from src.core.rbac import User


@dataclass(frozen=True)
class OriginRecord:
    """What the owner module says about a record that may be read.

    ``project_id`` is the project the record belongs to, which the attachment
    takes (every attachment is of one project). ``restricted`` marks a record
    whose attachments carry personal data (Q35).
    """

    project_id: int
    restricted: bool = False


class OriginReader(Protocol):
    """The reading function of a module: the record it lets the user read, ``None`` or a refusal."""

    def __call__(self, session: Session, *, user: User, record_id: int) -> OriginRecord | None:
        """Return the record, ``None`` when it does not exist, or raise ``AccessDeniedError``."""


@dataclass(frozen=True)
class OriginType:
    """One kind of record that accepts attachments: its table, its module and its reader.

    ``table`` is what ``anexo.origem_tabela`` stores, the table of the owner's
    record; ``module`` is the folder of the owner module (``planejamento``): the
    user must reach it, as for any other route of the module.
    """

    table: str
    module: str
    read: OriginReader


_ORIGINS: dict[str, OriginType] = {}


def register(origin_type: OriginType) -> None:
    """Register the origin type of a module; two modules cannot share a table.

    Registering the very same type again does nothing, so a module that is
    imported twice does not fail; a different type under a taken table does.
    """
    known = _ORIGINS.get(origin_type.table)
    if known is not None and known != origin_type:
        message = f"O tipo de origem {origin_type.table} já está registrado por outro módulo."
        raise ValueError(message)
    _ORIGINS[origin_type.table] = origin_type


def find(table: str) -> OriginType | None:
    """The origin type registered for the table, or ``None`` when no module registered it."""
    return _ORIGINS.get(table)


def registered() -> list[OriginType]:
    """The registered origin types, in registration order."""
    return list(_ORIGINS.values())
