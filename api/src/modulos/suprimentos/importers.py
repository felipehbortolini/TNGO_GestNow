"""Importação do plano de compras e dos marcos dos pedidos pela planilha modelo (D12, ISSUE-058/061).

O importador do plano registra as colunas do protótipo — escopo, tipo, modalidade, disciplina,
item da EAC, estimativa, comprador, as quatro datas do plano, ROS e LLI — e valida linha a linha
com as mesmas regras do formulário: o item é de custo (nível 3) da EAC do projeto, o comprador é
uma pessoa do cadastro, a disciplina é do cadastro de disciplinas, a estimativa é maior que zero,
as datas crescem e o plano não nasce com folga negativa. A conferência e a confirmação são o
fluxo genérico da plataforma (``core.importing``); a gravação passa pela fachada
(``service.create_package``), com a trilha e a versão.

O importador do diligenciamento (ISSUE-061) é a importação do ERP: uma linha por marco do pedido
(``Nº do pedido``, ``Marco``, ``Previsão`` e ``Realizada``), com a previsão ou a realização — uma
delas obrigatória —, a realização nunca futura e a previsão nunca no passado; a gravação passa
por ``service.apply_order_import_row``, a mesma regra da tela, e a linha do mesmo pedido e marco
repetida na planilha é recusada (o protótipo aplicava as duas em ordem).

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

ORDERS_KEY = "diligenciamento"
ORDERS_TITLE = "Diligenciamento e recebimento (ERP)"

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

# The columns of the ERP import of the expediting (ISSUE-061): one line per milestone.
ERP_ORDER_HEADER = "Nº do pedido"
MILESTONE_HEADER = "Marco"
FORECAST_HEADER = "Previsão"
REALIZED_HEADER = "Realizada"
FIELD_ORDER_NUMBER = "numero"
FIELD_MILESTONE = "marco"
FIELD_FORECAST = "previsao"
FIELD_REALIZED = "realizada"

LINE_EMPTY = "Informe a previsão ou a data realizada."

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
    """Register the importers once; calling again keeps the ones already registered."""
    for importer in (packages_importer(), orders_importer()):
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


# ── The ERP import of the order milestones (ISSUE-061) ───────────────────────────────────────


def orders_importer() -> Importer:
    """The ERP importer: one line per milestone, with the forecast or the realization."""
    return Importer(
        key=ORDERS_KEY,
        title=ORDERS_TITLE,
        module=MODULE,
        columns=(
            ImportColumn(
                FIELD_ORDER_NUMBER, ERP_ORDER_HEADER, required=True, example="PED-2026-0001"
            ),
            ImportColumn(
                FIELD_MILESTONE,
                MILESTONE_HEADER,
                options=service.DILIGENCE_MILESTONES,
                required=True,
                example="Embarque",
            ),
            ImportColumn(FIELD_FORECAST, FORECAST_HEADER, ValueKind.DATE, example="30/09/2026"),
            ImportColumn(FIELD_REALIZED, REALIZED_HEADER, ValueKind.DATE, example="28/09/2026"),
        ),
        validate=_validate_order,
        save=_save_order,
        unique=(FIELD_ORDER_NUMBER, FIELD_MILESTONE),
    )


def _validate_order(
    session: Session, *, values: Mapping[str, Any], context: ImportContext
) -> RowCheck:
    """Check one imported line: the order, the milestone, the dates and one date at least."""
    context.scope.require_project()
    forecast = _date(values, FIELD_FORECAST)
    realized = _date(values, FIELD_REALIZED)
    if forecast is None and realized is None:
        return RowCheck(errors=(LINE_EMPTY,))
    problems = service.order_import_problems(
        session,
        scope=context.scope,
        number=_text(values, FIELD_ORDER_NUMBER),
        milestone=_text(values, FIELD_MILESTONE),
        forecast=forecast,
        realized=realized,
        reference_date=context.reference_date,
    )
    return RowCheck(errors=tuple(problems.values()))


def _save_order(session: Session, *, values: Mapping[str, Any], context: ImportContext) -> None:
    """Write one checked line through the facade, as an ERP import of the expediting."""
    context.scope.require_project()
    service.apply_order_import_row(
        session,
        user=context.user,
        scope=context.scope,
        number=_text(values, FIELD_ORDER_NUMBER),
        milestone=_text(values, FIELD_MILESTONE),
        forecast=_date(values, FIELD_FORECAST),
        realized=_date(values, FIELD_REALIZED),
        reference_date=context.reference_date,
    )


__all__ = ["orders_importer", "packages_importer", "register_importers"]
