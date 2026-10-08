"""Importação do plano de compras pela planilha modelo (D12, ISSUE-058).

O importador registra as colunas do protótipo — escopo, tipo, modalidade, disciplina, item da
EAC, estimativa, comprador, as quatro datas do plano, ROS e LLI — e valida linha a linha com as
mesmas regras do formulário: o item é de custo (nível 3) da EAC do projeto, o comprador é uma
pessoa do cadastro, a disciplina é do cadastro de disciplinas, a estimativa é maior que zero, as
datas crescem e o plano não nasce com folga negativa. A conferência e a confirmação são o fluxo
genérico da plataforma (``core.importing``); a gravação passa pela fachada
(``service.create_package``), com a trilha e a versão.

O protótipo exigia o prazo de entrega para equipamento e material e o somava ao pedido na folga;
o modelo não tem a coluna e o mock não traz o dado, então a coluna não entra na planilha e a
folga usa o pedido (DECISION e DIVERGENCIAS-DO-PROTOTIPO, ISSUE-058).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.core import importing
from src.core.export_document import ValueKind
from src.core.import_values import normalize_text
from src.core.importing import ImportColumn, ImportContext, Importer, RowCheck
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service as financeiro
from src.modulos.suprimentos import service, validation

KEY = "plano-de-compras"
MODULE = "suprimentos"
TITLE = "Plano de compras"

SCOPE_HEADER = "Escopo"
KIND_HEADER = "Tipo"
MODALITY_HEADER = "Modalidade"
DISCIPLINE_HEADER = "Disciplina"
EAC_HEADER = "Item da EAC"
ESTIMATE_HEADER = "Estimativa (R$)"
BUYER_HEADER = "Comprador"
REQUISITION_HEADER = "Requisição"
RFX_HEADER = "RFx"
ADJUDICATION_HEADER = "Adjudicação"
ORDER_HEADER = "Pedido"
ROS_HEADER = "ROS"
LLI_HEADER = "LLI"

FIELD_SCOPE = "escopo"
FIELD_KIND = "tipo"
FIELD_MODALITY = "modalidade"
FIELD_DISCIPLINE = "disciplina"
FIELD_EAC = "eac"
FIELD_ESTIMATE = "estimativa"
FIELD_BUYER = "comprador"
FIELD_REQUISITION = "requisicao"
FIELD_RFX = "rfx"
FIELD_ADJUDICATION = "adjudicacao"
FIELD_ORDER = "pedido"
FIELD_ROS = "ros"
FIELD_LLI = "lli"

LLI_YES = "Sim"
LLI_NO = "Não"

DISCIPLINE_MISSING = "A disciplina “{value}” não está no cadastro."
BUYER_MISSING = "O comprador “{value}” não está no cadastro."


@dataclass(frozen=True)
class _Lookups:
    """O que a linha precisa para virar um ``PackageInput``: nomes resolvidos e o item da EAC."""

    disciplines: Mapping[str, int]
    buyers: Mapping[str, int]
    eac_items: Mapping[str, int]

    @classmethod
    def build(cls, session: Session, *, code: str, project_id: int) -> _Lookups:
        disciplines = {
            normalize_text(name): discipline_id
            for discipline_id, name in configuracoes.discipline_names_by_id(session).items()
        }
        buyers = {
            normalize_text(person.name): person.id
            for person in configuracoes.list_person_options(session)
        }
        eac_items: dict[str, int] = {}
        if code:
            levels = financeiro.eac_item_levels_by_code(
                session, project_id=project_id, codes=[code]
            )
            ids = financeiro.eac_item_ids_by_code(session, project_id=project_id, codes=[code])
            if levels.get(code) == 3 and code in ids:
                eac_items[code] = ids[code]
        return cls(disciplines=disciplines, buyers=buyers, eac_items=eac_items)


def packages_importer() -> Importer:
    """The plan importer: the prototype's columns, checked line by line against the project."""
    return Importer(
        key=KEY,
        title=TITLE,
        module=MODULE,
        columns=(
            ImportColumn(FIELD_SCOPE, SCOPE_HEADER, required=True, example="Compressores de ar"),
            ImportColumn(
                FIELD_KIND,
                KIND_HEADER,
                options=validation.PACKAGE_TYPES,
                required=True,
                example="Equipamento",
            ),
            ImportColumn(
                FIELD_MODALITY,
                MODALITY_HEADER,
                options=validation.PACKAGE_MODALITIES,
                required=True,
                example="Preço global",
            ),
            ImportColumn(FIELD_DISCIPLINE, DISCIPLINE_HEADER, required=True, example="Mecânica"),
            ImportColumn(FIELD_EAC, EAC_HEADER, required=True, example="2.1.4"),
            ImportColumn(
                FIELD_ESTIMATE,
                ESTIMATE_HEADER,
                ValueKind.MONEY,
                required=True,
                example="250.000,00",
            ),
            ImportColumn(FIELD_BUYER, BUYER_HEADER, required=True, example="Diego Matos"),
            ImportColumn(
                FIELD_REQUISITION,
                REQUISITION_HEADER,
                ValueKind.DATE,
                required=True,
                example="05/10/2026",
            ),
            ImportColumn(
                FIELD_RFX, RFX_HEADER, ValueKind.DATE, required=True, example="15/10/2026"
            ),
            ImportColumn(
                FIELD_ADJUDICATION,
                ADJUDICATION_HEADER,
                ValueKind.DATE,
                required=True,
                example="20/11/2026",
            ),
            ImportColumn(
                FIELD_ORDER, ORDER_HEADER, ValueKind.DATE, required=True, example="25/11/2026"
            ),
            ImportColumn(
                FIELD_ROS, ROS_HEADER, ValueKind.DATE, required=True, example="15/03/2027"
            ),
            ImportColumn(FIELD_LLI, LLI_HEADER, options=(LLI_YES, LLI_NO), example=LLI_NO),
        ),
        validate=_validate,
        save=_save,
    )


def register_importers() -> None:
    """Register the importer once; calling again keeps the one already registered."""
    importer = packages_importer()
    if importing.find(importer.key) is None:
        importing.register(importer)


def _validate(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> RowCheck:
    """Check one line against the plan rules: registers, dates, slack and level-3 item."""
    project_id = context.scope.require_project()
    data, lookups = _read_line(session, values, project_id=project_id)
    problems = validation.package_problems(
        data,
        eac_items=lookups.eac_items,
        discipline_ids=set(lookups.disciplines.values()),
        buyer_ids=set(lookups.buyers.values()),
    )
    _prefer_register_messages(problems, values, lookups)
    return RowCheck(errors=tuple(problems.values()))


def _save(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    """Write one checked line through the facade, as an import of the plan."""
    project_id = context.scope.require_project()
    data, _ = _read_line(session, values, project_id=project_id)
    service.create_package(
        session,
        user=context.user,
        project_id=project_id,
        data=data,
        reference_date=context.reference_date,
        note=service.IMPORT_NOTE,
    )


def _read_line(
    session: Session, values: Mapping[str, Any], *, project_id: int
) -> tuple[validation.PackageInput, _Lookups]:
    """A linha como ``PackageInput``, com os cadastros que ela resolveu."""
    code = _text(values, FIELD_EAC)
    lookups = _Lookups.build(session, code=code, project_id=project_id)
    discipline = _text(values, FIELD_DISCIPLINE)
    buyer = _text(values, FIELD_BUYER)
    estimate = values.get(FIELD_ESTIMATE)
    data = validation.PackageInput(
        scope=_text(values, FIELD_SCOPE),
        kind=_text(values, FIELD_KIND),
        modality=_text(values, FIELD_MODALITY),
        discipline_id=lookups.disciplines.get(normalize_text(discipline)),
        buyer_id=lookups.buyers.get(normalize_text(buyer)),
        eac_code=code,
        estimate_cents=estimate if isinstance(estimate, int) else None,
        requisition=_date(values, FIELD_REQUISITION),
        rfx=_date(values, FIELD_RFX),
        adjudication=_date(values, FIELD_ADJUDICATION),
        order=_date(values, FIELD_ORDER),
        ros=_date(values, FIELD_ROS),
        lli=normalize_text(_text(values, FIELD_LLI)) == normalize_text(LLI_YES),
    )
    return data, lookups


def _prefer_register_messages(
    problems: dict[str, str], values: Mapping[str, Any], lookups: _Lookups
) -> None:
    """O cadastro desconhecido fala o nome da planilha, não o genérico "Escolha"."""
    discipline = _text(values, FIELD_DISCIPLINE)
    if discipline and normalize_text(discipline) not in lookups.disciplines:
        problems["disciplina"] = DISCIPLINE_MISSING.format(value=discipline)
    buyer = _text(values, FIELD_BUYER)
    if buyer and normalize_text(buyer) not in lookups.buyers:
        problems["comprador"] = BUYER_MISSING.format(value=buyer)


def _text(values: Mapping[str, Any], field: str) -> str:
    return str(values.get(field) or "").strip()


def _date(values: Mapping[str, Any], field: str) -> date | None:
    """The date of the line, or ``None`` when the cell did not convert into one."""
    value = values.get(field)
    return value if isinstance(value, date) else None


__all__ = ["packages_importer", "register_importers"]
