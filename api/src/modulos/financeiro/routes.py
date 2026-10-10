"""Route blueprint of the Financeiro module (D14).

The EAC screen (ISSUE-029, ISSUE-030) and what hangs from it, all under ``/api/financeiro/eac``:

* ``GET /eac`` is the content of the screen (KPIs and tree) for the scope of the request, with the
  filters ``busca``, ``nivel`` and ``tipo``; in the Portfólio it is read-only;
* ``GET /eac/itens/{item_id}/editar`` is the cadastral edit form of an item, with its history;
* ``POST /eac/itens/{item_id}`` saves it: justification required, no SM, nothing of value;
* ``GET /eac/revisoes`` and ``GET /eac/remanejamentos`` are the two panels of the screen (the
  frozen baseline of each revision and the applied and pending transfers), in the Portfólio with
  a line per project;
* ``POST /eac/remanejamentos`` opens the SM of a reallocation (the value stays reserved in the
  origin until the decision); ``POST /eac/revisoes`` creates a revision from an approved SM with
  cost; ``POST /eac/itens`` creates a new item, financed by a reallocation or by a revision;
* ``GET /eac/revisoes/importar/formulario`` is the import form the modal of the screen opens;
  ``POST /eac/revisoes/importar/conferir`` and ``.../confirmar`` are the two steps of the import
  of new items by spreadsheet: the check reads and never writes (and answers the result with the
  two panels), and the confirmation checks again and creates the revision bound to the SM;
* ``GET /eac/excel`` and ``GET /eac/imprimivel`` are the two exports of the platform, with the
  same filters and the same tables the screen shows.

The map of ISSUE-031 lives under ``/api/financeiro/mapa-de-controle`` and ``/api/financeiro/custos``:

* ``GET /mapa-de-controle`` is the content of the map (KPIs and the lines of the scope) for one
  project or the Portfólio; ``GET /mapa-de-controle/excel`` and ``GET /mapa-de-controle/imprimivel``
  are its two exports, in full reais and with the ``Projeto`` column in the Portfólio;
* ``GET /mapa-de-controle/projecao/{item_id}/formulario`` is the projection form of an item and
  ``POST /mapa-de-controle/projecao/{item_id}`` saves it: justification required, the history of
  the item grows by one fact, and the refusal comes back in the form with 422;
* ``GET /custos/importar/formulario`` is the import form of the ERP closing; the check
  (``POST .../conferir``) reads and never writes and the confirmation (``POST .../confirmar``)
  checks the file again and writes one fact per item and month, replacing a reimported month.

The ficha do contrato of ISSUE-032 lives under ``/api/financeiro/contrato``, opened by the contract
number (``?numero=``): ``GET /contrato/resumo``, ``/contrato/medicoes`` and ``/contrato/aditivos``
are the content of each tab; ``GET /contrato/medicoes/nova``, ``/contrato/medicoes/{id}/devolucao``
and ``/contrato/aditivos/novo`` are the forms; ``POST /contrato/medicoes`` and
``POST /contrato/aditivos`` create the record; ``POST /contrato/medicoes/{id}/aprovar``,
``.../faturar``, ``.../pagar`` and ``.../devolver`` move the measurement through the flow; the
saved answers bring the panels again (a multi-target response, with the form emptied).
``GET /contrato/excel`` and ``GET /contrato/imprimivel`` are the two exports of the ficha.

The marcos, claims and EOT of ISSUE-033 hang from the same ficha: ``GET /contrato/marcos``,
``/contrato/claims`` and ``/contrato/extensoes`` are the content of each tab;
``GET /contrato/marcos/novo``, ``/contrato/marcos/{id}/evidencia``, ``/contrato/claims/novo``,
``/contrato/claims/{id}/atualizar``, ``/contrato/claims/{id}/decidir``, ``/contrato/extensoes/nova``
and ``/contrato/extensoes/{id}/decidir`` are the forms (the evidence one sends a file);
``POST /contrato/marcos``, ``POST /contrato/marcos/{id}/evidencia``, ``POST /contrato/marcos/{id}/aprovar``,
``.../faturar`` and ``.../pagar`` move the milestone, ``POST /contrato/claims``,
``POST /contrato/claims/{id}/atualizar`` and ``.../decidir`` move the claim, and
``POST /contrato/extensoes`` and ``POST /contrato/extensoes/{id}/decidir`` move the EOT. Each tab has
its own Excel and imprimível (``.../excel`` and ``.../imprimivel``); the saved answers bring the
panels again (a multi-target response, with the form emptied).

The Avaliação de desempenho of ISSUE-034 hangs from the same ficha: ``GET /contrato/avaliacoes`` is
the content of the tab (the table and the Gráfico de Áreas de Avaliação), ``GET
/contrato/avaliacoes/nova`` is the form (the notes of the criteria in force, with their weights),
``POST /contrato/avaliacoes`` creates the evaluation (multipart, with the evidence when a note 1 or
2 demands it) and ``GET /contrato/avaliacoes/excel`` and ``.../imprimivel`` are its two exports.
The saved answer brings the tab again (a multi-target response, with the form emptied).

The consolidated vision of ISSUE-035 lives under ``/api/financeiro/contratos/consolidado``:
``GET`` is the content of the screen (the six KPIs and the five tabs of the scope, with the filters
``busca`` and ``contrato``), ``GET .../excel`` downloads the document with the KPIs and the five
tables (``contratos-<código do projeto|portfolio>``) and ``GET .../imprimivel`` renders the same
document for the PDF button. New records are born in the ficha of the contract, so no tab of this
screen carries an inclusion button.

The Contingência screen of ISSUE-041 lives under ``/api/financeiro/contingencia``:
``GET`` is the content of the screen for the scope of the request (the four indicators with their
management reference, the alerts, the chart of the real against the expected balance, the
composition of the budget, the statement of movements and, in the Portfólio, the table per
project); ``GET .../contingencia/excel`` and ``GET .../contingencia/imprimivel`` are its two
exports, with the same content — the numbers behind the chart travel in the burn table of the
document, because the spreadsheet has no chart.

The Curva S financeira and the KPIs de custo of ISSUE-042 live under ``/api/financeiro/curva-s``
and ``/api/financeiro/kpis``: ``GET`` is the content of each screen for the scope of the request
(the four indicators of the curve and its four series, the month-by-month table, and the six cost
indicators with the CPI against the SPI and the value table — in the Portfólio, the sums and the
performance per project); ``GET .../excel`` and ``GET .../imprimivel`` are the two exports of each
screen, with the same content, the ``Projeto`` column coming from the generic mechanism in the
Portfólio.

The Cronograma de desembolso of ISSUE-043 lives under ``/api/financeiro/desembolso``: ``GET`` is
the content of the screen for the scope of the request (the four indicators with the planned
reference, the monthly chart of previsto, realizado and projetado and the balance to pay per item
and month, with the ``Projeto`` column in the Portfólio); ``GET .../excel`` and
``GET .../imprimivel`` are its two exports, with the same content; ``GET .../enviar`` is the modal
form of the send to the treasury, prefilled with the default recipient and message, and
``POST .../enviar`` sends it through the notification port (recorded as ``simulado`` while the
e-mail sending is off), refusing the Portfólio and the scope without a schedule.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import attachments, calendario, database, importing, notification, rbac
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.excel import XLSX_CONTENT_TYPE, build_workbook, excel_response
from src.core.export_document import (
    Document,
    Kpi,
    ValueKind,
    describe_scope,
    format_value,
)
from src.core.import_values import normalize_text
from src.core.printable import printable_response
from src.core.rbac import Permission, User
from src.core.responses import AlpineAjaxResponse, file_response
from src.core.routing import (
    Access,
    RequestContext,
    authorize,
    file_route,
    fragment_route,
)
from src.core.scope import Scope
from src.core.spreadsheet_reader import MAX_DATA_ROWS, MAX_FILE_BYTES, MEGABYTE
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import calculations, export, importers, service, validation
from src.modulos.financeiro.calculations import LEAF_LEVEL, PORTFOLIO_MAIN_LEVEL, TreeRow
from src.modulos.financeiro.service import EacFilters, EacView, ItemForm
from src.modulos.hse import painel_service as hse_painel

bp = func.Blueprint()

importers.register_importers()

CONTENT_ROUTE = "financeiro/eac"
FORM_ROUTE = "financeiro/eac/itens/{item_id}/editar"
SAVE_ROUTE = "financeiro/eac/itens/{item_id}"
REVISIONS_ROUTE = "financeiro/eac/revisoes"
REALLOCATIONS_ROUTE = "financeiro/eac/remanejamentos"
NEW_ITEM_ROUTE = "financeiro/eac/itens"
IMPORT_FORM_ROUTE = "financeiro/eac/revisoes/importar/formulario"
IMPORT_CHECK_ROUTE = "financeiro/eac/revisoes/importar/conferir"
IMPORT_CONFIRM_ROUTE = "financeiro/eac/revisoes/importar/confirmar"
EXCEL_ROUTE = "financeiro/eac/excel"
PRINTABLE_ROUTE = "financeiro/eac/imprimivel"

CONTENT_TEMPLATE = "financeiro/eac.html"
FORM_TEMPLATE = "financeiro/eac_form.html"
SAVED_TEMPLATE = "financeiro/eac_salvo.html"
REVISIONS_TEMPLATE = "financeiro/eac_revisoes.html"
REALLOCATIONS_TEMPLATE = "financeiro/eac_remanejamentos.html"
REVISION_SAVED_TEMPLATE = "financeiro/eac_revisao_salva.html"
REALLOCATION_SAVED_TEMPLATE = "financeiro/eac_remanejamento_salvo.html"
IMPORT_FORM_TEMPLATE = "financeiro/eac_importacao_form.html"
IMPORT_CHECK_TEMPLATE = "financeiro/eac_importacao_conferencia.html"

FORM_TARGET = "eac-formulario"
CONTENT_TARGET = "eac-conteudo"
REVISIONS_TARGET = "eac-revisoes"
REALLOCATIONS_TARGET = "eac-remanejamentos"
IMPORT_RESULT_TARGET = "eac-importacao-resultado"
SAVED_MESSAGE = "Item {code} atualizado; alteração registrada no histórico."
NOTHING_CHANGED_MESSAGE = "Nenhum dado alterado."
REALLOCATION_CREATED_MESSAGE = (
    "SM {code} registrada em Governança: o valor muda na EAC só depois da aprovação."
)
REVISION_CREATED_MESSAGE = "Rev {revision} criada: orçamento de {total}."
IMPORT_CONFIRMED_MESSAGE = "Rev {revision} criada: {items} ({total})."
IMPORT_ITEM = "1 item novo"
IMPORT_ITEMS = "{count} itens novos"
ITEM_PARAMETER = "item_id"

MAP_ROUTE = "financeiro/mapa-de-controle"
MAP_PROJECTION_FORM_ROUTE = "financeiro/mapa-de-controle/projecao/{item_id}/formulario"
MAP_PROJECTION_SAVE_ROUTE = "financeiro/mapa-de-controle/projecao/{item_id}"
MAP_EXCEL_ROUTE = "financeiro/mapa-de-controle/excel"
MAP_PRINTABLE_ROUTE = "financeiro/mapa-de-controle/imprimivel"
ERP_IMPORT_FORM_ROUTE = "financeiro/custos/importar/formulario"
ERP_IMPORT_CHECK_ROUTE = "financeiro/custos/importar/conferir"
ERP_IMPORT_CONFIRM_ROUTE = "financeiro/custos/importar/confirmar"

MAP_TEMPLATE = "financeiro/mapa_controle.html"
MAP_PROJECTION_FORM_TEMPLATE = "financeiro/mapa_projecao_form.html"
MAP_PROJECTION_SAVED_TEMPLATE = "financeiro/mapa_projecao_salvo.html"
ERP_IMPORT_FORM_TEMPLATE = "financeiro/custos_importacao_form.html"
ERP_IMPORT_CHECK_TEMPLATE = "financeiro/custos_importacao_conferencia.html"
ERP_IMPORT_RESULT_TEMPLATE = "financeiro/custos_importacao_resultado.html"

MAP_TARGET = "mapa-conteudo"
PROJECTION_FORM_TARGET = "mapa-projecao-formulario"

CONTRACT_CONTENT_BASE = "financeiro/contrato"
CONTRACT_RESUME_ROUTE = f"{CONTRACT_CONTENT_BASE}/resumo"
CONTRACT_MEASUREMENTS_ROUTE = f"{CONTRACT_CONTENT_BASE}/medicoes"
CONTRACT_ADDENDA_ROUTE = f"{CONTRACT_CONTENT_BASE}/aditivos"
CONTRACT_MEASUREMENT_FORM_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/nova"
CONTRACT_MEASUREMENT_CREATE_ROUTE = CONTRACT_MEASUREMENTS_ROUTE
CONTRACT_MEASUREMENT_APPROVE_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/aprovar"
CONTRACT_MEASUREMENT_INVOICE_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/faturar"
CONTRACT_MEASUREMENT_PAY_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/pagar"
CONTRACT_MEASUREMENT_RETURN_FORM_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/devolucao"
CONTRACT_MEASUREMENT_RETURN_ROUTE = f"{CONTRACT_MEASUREMENTS_ROUTE}/{{medicao_id}}/devolver"
CONTRACT_ADDENDUM_FORM_ROUTE = f"{CONTRACT_ADDENDA_ROUTE}/novo"
CONTRACT_ADDENDUM_CREATE_ROUTE = CONTRACT_ADDENDA_ROUTE
CONTRACT_EXCEL_ROUTE = f"{CONTRACT_CONTENT_BASE}/excel"
CONTRACT_PRINTABLE_ROUTE = f"{CONTRACT_CONTENT_BASE}/imprimivel"

CONTRACT_MILESTONES_ROUTE = f"{CONTRACT_CONTENT_BASE}/marcos"
CONTRACT_MILESTONE_FORM_ROUTE = f"{CONTRACT_MILESTONES_ROUTE}/novo"
CONTRACT_MILESTONE_CREATE_ROUTE = CONTRACT_MILESTONES_ROUTE
CONTRACT_MILESTONE_EVIDENCE_ROUTE = f"{CONTRACT_MILESTONES_ROUTE}/{{marco_id}}/evidencia"
CONTRACT_MILESTONE_APPROVE_ROUTE = f"{CONTRACT_MILESTONES_ROUTE}/{{marco_id}}/aprovar"
CONTRACT_MILESTONE_INVOICE_ROUTE = f"{CONTRACT_MILESTONES_ROUTE}/{{marco_id}}/faturar"
CONTRACT_MILESTONE_PAY_ROUTE = f"{CONTRACT_MILESTONES_ROUTE}/{{marco_id}}/pagar"
CONTRACT_MILESTONES_EXCEL_ROUTE = f"{CONTRACT_MILESTONES_ROUTE}/excel"
CONTRACT_MILESTONES_PRINTABLE_ROUTE = f"{CONTRACT_MILESTONES_ROUTE}/imprimivel"

CONTRACT_CLAIMS_ROUTE = f"{CONTRACT_CONTENT_BASE}/claims"
CONTRACT_CLAIM_FORM_ROUTE = f"{CONTRACT_CLAIMS_ROUTE}/novo"
CONTRACT_CLAIM_CREATE_ROUTE = CONTRACT_CLAIMS_ROUTE
CONTRACT_CLAIM_UPDATE_ROUTE = f"{CONTRACT_CLAIMS_ROUTE}/{{claim_id}}/atualizar"
CONTRACT_CLAIM_DECIDE_ROUTE = f"{CONTRACT_CLAIMS_ROUTE}/{{claim_id}}/decidir"
CONTRACT_CLAIMS_EXCEL_ROUTE = f"{CONTRACT_CLAIMS_ROUTE}/excel"
CONTRACT_CLAIMS_PRINTABLE_ROUTE = f"{CONTRACT_CLAIMS_ROUTE}/imprimivel"

CONTRACT_EXTENSIONS_ROUTE = f"{CONTRACT_CONTENT_BASE}/extensoes"
CONTRACT_EXTENSION_FORM_ROUTE = f"{CONTRACT_EXTENSIONS_ROUTE}/nova"
CONTRACT_EXTENSION_CREATE_ROUTE = CONTRACT_EXTENSIONS_ROUTE
CONTRACT_EXTENSION_DECISION_ROUTE = f"{CONTRACT_EXTENSIONS_ROUTE}/{{extensao_id}}/decidir"
CONTRACT_EXTENSIONS_EXCEL_ROUTE = f"{CONTRACT_EXTENSIONS_ROUTE}/excel"
CONTRACT_EXTENSIONS_PRINTABLE_ROUTE = f"{CONTRACT_EXTENSIONS_ROUTE}/imprimivel"

CONTRACT_EVALUATIONS_ROUTE = f"{CONTRACT_CONTENT_BASE}/avaliacoes"
CONTRACT_EVALUATION_FORM_ROUTE = f"{CONTRACT_EVALUATIONS_ROUTE}/nova"
CONTRACT_EVALUATION_CREATE_ROUTE = CONTRACT_EVALUATIONS_ROUTE
CONTRACT_EVALUATIONS_EXCEL_ROUTE = f"{CONTRACT_EVALUATIONS_ROUTE}/excel"
CONTRACT_EVALUATIONS_PRINTABLE_ROUTE = f"{CONTRACT_EVALUATIONS_ROUTE}/imprimivel"

CONTRATOS_CONSOLIDADO_ROUTE = "financeiro/contratos/consolidado"
CONTRATOS_CONSOLIDADO_EXCEL_ROUTE = f"{CONTRATOS_CONSOLIDADO_ROUTE}/excel"
CONTRATOS_CONSOLIDADO_PRINTABLE_ROUTE = f"{CONTRATOS_CONSOLIDADO_ROUTE}/imprimivel"

CONTRACT_RESUME_TEMPLATE = "financeiro/contrato_resumo.html"
CONTRACT_MEASUREMENTS_TEMPLATE = "financeiro/contrato_medicoes.html"
CONTRACT_ADDENDA_TEMPLATE = "financeiro/contrato_aditivos.html"
CONTRACT_SAVED_TEMPLATE = "financeiro/contrato_salvo.html"
CONTRACT_MEASUREMENT_FORM_TEMPLATE = "financeiro/contrato_medicao_form.html"
CONTRACT_MEASUREMENT_RETURN_TEMPLATE = "financeiro/contrato_medicao_devolucao.html"
CONTRACT_ADDENDUM_FORM_TEMPLATE = "financeiro/contrato_aditivo_form.html"

CONTRACT_MILESTONES_TEMPLATE = "financeiro/contrato_marcos.html"
CONTRACT_CLAIMS_TEMPLATE = "financeiro/contrato_claims.html"
CONTRACT_EXTENSIONS_TEMPLATE = "financeiro/contrato_extensoes.html"
CONTRACT_FLOWS_SAVED_TEMPLATE = "financeiro/contrato_fluxos_salvo.html"
CONTRACT_MILESTONE_FORM_TEMPLATE = "financeiro/contrato_marco_form.html"
CONTRACT_MILESTONE_EVIDENCE_TEMPLATE = "financeiro/contrato_marco_evidencia.html"
CONTRACT_CLAIM_FORM_TEMPLATE = "financeiro/contrato_claim_form.html"
CONTRACT_CLAIM_UPDATE_TEMPLATE = "financeiro/contrato_claim_atualizacao.html"
CONTRACT_EXTENSION_FORM_TEMPLATE = "financeiro/contrato_eot_form.html"
CONTRACT_EXTENSION_DECISION_TEMPLATE = "financeiro/contrato_eot_decisao.html"
CONTRACT_EVALUATIONS_TEMPLATE = "financeiro/contrato_avaliacoes.html"
CONTRACT_EVALUATION_FORM_TEMPLATE = "financeiro/contrato_avaliacao_form.html"
CONTRACT_EVALUATION_SAVED_TEMPLATE = "financeiro/contrato_avaliacao_salvo.html"

CONTRATOS_CONSOLIDADO_TEMPLATE = "financeiro/contratos_consolidado.html"
CONTRATOS_CONSOLIDADO_PARTS_TEMPLATE = "financeiro/contratos_consolidado_partes.html"

CONTRACT_RESUME_TARGET = "contrato-resumo"
CONTRACT_MEASUREMENTS_TARGET = "contrato-medicoes"
CONTRACT_ADDENDA_TARGET = "contrato-aditivos"
CONTRACT_MILESTONES_TARGET = "contrato-marcos"
CONTRACT_CLAIMS_TARGET = "contrato-claims"
CONTRACT_EXTENSIONS_TARGET = "contrato-extensoes"
CONTRACT_EVALUATIONS_TARGET = "contrato-avaliacoes"
CONTRACT_FORM_TARGET = "contrato-formulario"

CONTRATOS_CONSOLIDADO_TARGET = "contratos-conteudo"
CONTRATOS_KPIS_TARGET = "contratos-kpis"
CONTRATOS_TABELAS_TARGET = "contratos-tabelas"
CONTRATOS_FILTERED_BLOCKS = (CONTRATOS_KPIS_TARGET, CONTRATOS_TABELAS_TARGET)
CONTRATOS_FILTER_PARAMETER = "contrato"

CONTRACT_NUMBER_PARAMETER = "numero"
CONTRACT_MEASUREMENT_PARAMETER = "medicao_id"
CONTRACT_MILESTONE_PARAMETER = "marco_id"
CONTRACT_CLAIM_PARAMETER = "claim_id"
CONTRACT_EXTENSION_PARAMETER = "extensao_id"

CONTRACT_MEASUREMENT_CREATED_MESSAGE = "Medição {number} registrada em análise."
CONTRACT_MEASUREMENT_MOVED_MESSAGE = "Medição {number}: {situation}."
CONTRACT_MEASUREMENT_RETURNED_MESSAGE = "Medição {number} devolvida à contratada."
CONTRACT_ADDENDUM_CREATED_MESSAGE = "Aditivo {number} registrado."
CONTRACT_ADDENDUM_EXTENDED_SUFFIX = " Término vigente prorrogado em {days} dias."

CONTRACT_MILESTONE_CREATED_MESSAGE = "Marco {number} cadastrado."
CONTRACT_MILESTONE_EVIDENCE_MESSAGE = "Evidência do marco {number} enviada para aprovação."
CONTRACT_MILESTONE_MOVED_MESSAGE = "Marco {number}: {situation}."
CONTRACT_CLAIM_CREATED_MESSAGE = "Claim {code} registrado."
CONTRACT_CLAIM_MOVED_MESSAGE = "Claim {code}: {situation}."
CONTRACT_CLAIM_AGREED_SUFFIX = " SM {code} aberta em Governança."
CONTRACT_EXTENSION_CREATED_MESSAGE = "Extensão de prazo {code} registrada."
CONTRACT_EXTENSION_MOVED_MESSAGE = "Extensão {code}: {situation}."
CONTRACT_EXTENSION_EXTENDED_SUFFIX = " Término vigente prorrogado em {days} dias."
CONTRACT_EVALUATION_CREATED_MESSAGE = "Avaliação {kind} de {period} registrada."
CONTRACT_EVALUATION_PLAN_SUFFIX = " Plano de melhoria aberto na Central."
CONTRACT_EVALUATION_LESSON_SUFFIX = " Lição de fornecedor criada em rascunho."
CONTRACT_EVALUATIONS_CHART_TITLE = "Desempenho da contratada"

_SITUATION_PILLS = {
    calculations.SITUATION_UNDER_REVIEW: "warn",
    calculations.SITUATION_APPROVED: "fix",
    calculations.SITUATION_INVOICED: "fix",
    calculations.SITUATION_PAID: "ok",
    calculations.SITUATION_RETURNED: "erro",
}

_MILESTONE_PILLS = {
    calculations.MILESTONE_FORECAST: "neutral",
    calculations.MILESTONE_EVIDENCE_SENT: "warn",
    calculations.MILESTONE_APPROVED: "fix",
    calculations.MILESTONE_INVOICED: "fix",
    calculations.MILESTONE_PAID: "ok",
}

_CLAIM_PILLS = {
    calculations.CLAIM_NOTIFIED: "warn",
    calculations.CLAIM_UNDER_REVIEW: "warn",
    calculations.CLAIM_IN_NEGOTIATION: "warn",
    calculations.CLAIM_AGREED: "ok",
    calculations.CLAIM_REJECTED: "erro",
    calculations.CLAIM_IN_DISPUTE: "erro",
    calculations.CLAIM_CLOSED: "neutral",
}

_EXTENSION_PILLS = {
    calculations.EXTENSION_REQUESTED: "warn",
    calculations.EXTENSION_UNDER_REVIEW: "warn",
    calculations.EXTENSION_GRANTED: "ok",
    calculations.EXTENSION_PARTIALLY_GRANTED: "ok",
    calculations.EXTENSION_DENIED: "erro",
}

_EVALUATION_CLASS_PILLS = {"A": "ok", "B": "fix", "C": "warn", "D": "erro"}
_EVALUATION_CLASS_PAPEIS = {"A": "ok", "B": "marca", "C": "alerta", "D": "erro"}

MIL_CENTS = 100_000
MIL_ONE_PLACE = Decimal("0.1")
MAP_TITLE_PROJECT = "Mapa de controle da EAC"
MAP_TITLE_PORTFOLIO = "Mapa de controle da carteira"
MAP_ITEM_ROW_LABEL = "Código"
MAP_PROJECT_ROW_LABEL = "Projeto"
MAP_DESCRIPTION_ID = "descricao"
MAP_PERCENT_ID = "desvio_pct"
MAP_MONEY_COLUMNS: tuple[tuple[str, str, bool, str], ...] = (
    ("orcado", "Orçado", False, "baseline_cents"),
    ("remanejamentos", "Remanejamentos", True, "reallocation_cents"),
    ("atual", "Orçado atual", False, "current_cents"),
    ("comprometido", "Comprometido", False, "committed_cents"),
    ("realizado", "Realizado", False, "actual_cents"),
    ("saldo", "Saldo a comprometer", False, "saldo_cents"),
    ("projecao", "Projeção no término", False, "projection_cents"),
    ("desvio", "Desvio", True, "deviation_cents"),
)

PROJECTION_SAVED_MESSAGE = "Projeção de {code} atualizada."
PROJECTION_PORTFOLIO_MESSAGE = (
    "A projeção no término é de um item de um projeto. Abra o projeto para atualizá-la."
)
ERP_IMPORTED_MESSAGE = "{count} itens atualizados no mapa de controle."
ERP_IMPORTED_ONE_MESSAGE = "1 item atualizado no mapa de controle."
ERP_SKIPPED_SUFFIX = " {count} com erro não entraram."

# Reading the EAC is reading the module; the edit asks to write (a supplier reaches neither).
READ_ACCESS = Access(module=service.MODULE, permission=Permission.VIEW)
WRITE_ACCESS = Access(module=service.MODULE, permission=Permission.WRITE)

# The kinds of column the import preview aligns to the right.
_NUMERIC_KINDS = frozenset(
    {ValueKind.INTEGER, ValueKind.DECIMAL, ValueKind.PERCENT, ValueKind.MONEY}
)


@dataclass(frozen=True)
class LineView:
    """A line of the tree as the table prints it: the row, its texts and where it can go."""

    row: TreeRow
    quantity: str
    unit_price: str
    budget: str
    weight: str
    classification: str
    has_children: bool
    edit_query: str
    can_edit: bool


# ── Tela ─────────────────────────────────────────────────────────────────


@bp.route(route=CONTENT_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eac_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The content of the EAC screen: the KPIs and the tree of the scope, filtered."""
    view = _view_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTENT_TEMPLATE, context=_content_context(view), request=req
    )


@bp.route(route=EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def eac_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The Excel of the EAC: the download of the screen, with the same filters."""
    return excel_response(_document_of(req, session, context))


@bp.route(route=PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eac_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The printable version of the EAC: what the PDF button mounts and prints."""
    return printable_response(_document_of(req, session, context), req)


# ── Cadastro do item ─────────────────────────────────────────────────────


@bp.route(route=FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eac_item_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The edit form of the cadastral data of an item, with its history."""
    form = service.item_form(
        session, user=context.user, scope=context.scope, item_id=_item_id_of(req)
    )
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context=_form_context(form, values={}, problems={}, filters=_filters_of(req.params)),
        request=req,
    )


def _render_form_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The form again, with what the person typed, when the save is refused with 422 or 409."""
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            form = service.item_form(
                session, user=context.user, scope=context.scope, item_id=_item_id_of(req)
            )
    except DomainError:
        return None
    problems = error.detail if isinstance(error, InvalidDataError) else {}
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context=_form_context(
            form,
            values=_posted(req.form),
            problems=problems if isinstance(problems, Mapping) else {},
            filters=_filters_of(req.form),
            message=str(error) if isinstance(error, VersionConflictError) else "",
        ),
        request=req,
        target_id=FORM_TARGET,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=SAVE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_form_error)
def eac_item_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Save the cadastral edit of an item and answer the screen again, the form closed."""
    item_id = _item_id_of(req)
    result = service.edit_item_registry(
        session, user=context.user, scope=context.scope, item_id=item_id, form=_posted(req.form)
    )
    view = service.eac_view(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.form),
        reference_date=calendario.today(),
    )
    code = next((row.code for row in view.full_rows if row.item_id == item_id), "")
    return AlpineAjaxResponse(
        template_name=SAVED_TEMPLATE,
        context=_content_context(view),
        request=req,
        toast=SAVED_MESSAGE.format(code=code) if result.changed_fields else NOTHING_CHANGED_MESSAGE,
        toast_tipo="ok" if result.changed_fields else "aviso",
    )


# ── Montagem ─────────────────────────────────────────────────────────────


def _view_of(req: func.HttpRequest, session: Session, context: RequestContext) -> EacView:
    """The EAC of the request; the only place of the reading routes that reads the clock."""
    return service.eac_view(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.params),
        reference_date=calendario.today(),
    )


def _document_of(req: func.HttpRequest, session: Session, context: RequestContext) -> Document:
    view = _view_of(req, session, context)
    project_ids = _project_ids(session, context.scope)
    return export.eac_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
        revisions=service.revision_rows(session, project_ids=project_ids),
        reallocations=service.reallocation_rows(session, project_ids=project_ids),
    )


def _filters_of(source: Mapping[str, str | None]) -> EacFilters:
    """The filters of the tree from a query or a form: an unreadable level is the deepest."""
    raw_level = (source.get("nivel") or "").strip()
    cost_type = (source.get("tipo") or "").strip()
    return EacFilters(
        search=(source.get("busca") or "").strip(),
        level=int(raw_level) if raw_level.isdigit() else LEAF_LEVEL,
        cost_type=cost_type if cost_type in validation.COST_TYPES else "",
    )


def _item_id_of(req: func.HttpRequest) -> int:
    raw = req.route_params.get(ITEM_PARAMETER) or ""
    if not raw.isdigit():
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return int(raw)


def _posted(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_DESCRIPTION,
        validation.FIELD_COST_TYPE,
        validation.FIELD_CLASSIFICATION,
        validation.FIELD_COST_CENTER,
        validation.FIELD_RESPONSIBLE,
        validation.FIELD_JUSTIFICATION,
        validation.FIELD_VERSION,
    )
    return {name: form.get(name) for name in names}


def _content_context(view: EacView) -> dict[str, object]:
    filter_query = _filter_query(view.filters)
    return {
        "view": view,
        "linhas": [_line_view(view, row, filter_query) for row in view.rows],
        "resultado": _result_of(view),
        "orcamento": _money(view.summary.budget_cents),
        "total_filtrado": _money(view.filtered_total_cents),
        "tipos_de_custo": validation.COST_TYPES,
        "alvo_formulario": FORM_TARGET,
        "alvo_conteudo": CONTENT_TARGET,
    }


def _line_view(view: EacView, row: TreeRow, filter_query: str) -> LineView:
    return LineView(
        row=row,
        quantity=_decimal(row.quantity),
        unit_price=_money(row.unit_price_cents),
        budget=_money(row.budget_cents),
        weight=_percent(row.weight),
        classification=_classification(row),
        has_children=row.code in view.parents,
        edit_query=filter_query,
        can_edit=view.can_edit and row.item_id is not None and row.level >= LEAF_LEVEL,
    )


def _result_of(view: EacView) -> str:
    if view.is_empty:
        return "vazio-origem"
    return "vazio-filtro" if view.has_no_match else "conteudo"


def _money(cents: int | None) -> str:
    return "" if cents is None else format_value(ValueKind.MONEY, cents)


def _decimal(value: Decimal | None) -> str:
    return "" if value is None else format_value(ValueKind.DECIMAL, value)


def _percent(value: Decimal | None) -> str:
    return "" if value is None else format_value(ValueKind.PERCENT, value)


def _classification(row: TreeRow) -> str:
    if row.level < LEAF_LEVEL or row.capex is None:
        return ""
    return "CAPEX" if row.capex else "OPEX"


def _filter_query(filters: EacFilters) -> str:
    """The filters as a query string, so the edit form can bring them back to the screen."""
    pairs = {"busca": filters.search, "nivel": str(filters.level), "tipo": filters.cost_type}
    return urlencode({key: value for key, value in pairs.items() if value})


def _form_context(
    form: ItemForm,
    *,
    values: Mapping[str, str | None],
    problems: Mapping[str, str],
    filters: EacFilters,
    message: str = "",
) -> dict[str, object]:
    return {
        "formulario": form,
        "valores": values,
        "erros": problems,
        "mensagem": message,
        "filtros": filters,
        "tipos_de_custo": validation.COST_TYPES,
        "classificacoes": validation.CLASSIFICATIONS,
        "orcado": _money(form.row.budget_cents),
        "preco": _money(form.row.unit_price_cents),
        "quantidade": _decimal(form.row.quantity),
        "unidade": form.row.unit or "",
        "alvo_conteudo": CONTENT_TARGET,
    }


# ── Revisões e remanejamentos (ISSUE-030) ────────────────────────────────


def _render_revision_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The panels again, with the refusal at the top of the revisions table."""
    return _render_panel_error(req, error, template=REVISION_SAVED_TEMPLATE)


def _render_reallocation_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """The panels again, with the refusal at the top of the reallocations table."""
    return _render_panel_error(req, error, template=REALLOCATION_SAVED_TEMPLATE)


def _render_new_item_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """The panels again, with the refusal in the table of the recourse the person chose."""
    recourse = req.form.get(validation.FIELD_NEW_ITEM_RECOURSE) or validation.RECOURSE_REALLOCATION
    template = (
        REVISION_SAVED_TEMPLATE
        if recourse == validation.RECOURSE_REVISION
        else REALLOCATION_SAVED_TEMPLATE
    )
    return _render_panel_error(req, error, template=template)


@bp.route(route=REVISIONS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eac_revisions(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The revisions of the scope: the frozen baseline of each one, with the variation."""
    return AlpineAjaxResponse(
        template_name=REVISIONS_TEMPLATE,
        context=_revisions_context(
            session, context.scope, user=context.user, filters=_filters_of(req.params)
        ),
        request=req,
    )


@bp.route(route=REALLOCATIONS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def eac_reallocations(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The reallocations of the scope: applied and pending, with the free balance of the origin."""
    return AlpineAjaxResponse(
        template_name=REALLOCATIONS_TEMPLATE,
        context=_reallocations_context(
            session, context.scope, user=context.user, filters=_filters_of(req.params)
        ),
        request=req,
    )


@bp.route(route=REALLOCATIONS_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_reallocation_error)
def eac_reallocate(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Open the SM of a budget reallocation, as the EAC screen asks; the value stays reserved."""
    form = validation.parse_reallocation_form(req.form)
    created = service.reallocate(
        session,
        user=context.user,
        scope=context.scope,
        request=_reallocation_request(form),
        reference_date=calendario.today(),
    )
    return _reallocation_saved(req, session, context, created)


@bp.route(route=REVISIONS_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_revision_error)
def eac_create_revision(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create the revision of the EAC from an approved SM with cost (Gestor)."""
    form = validation.parse_revision_form(req.form)
    revision = service.create_revision(
        session,
        user=context.user,
        scope=context.scope,
        request=service.RevisionRequest(
            change_id=form.change_id,
            justification=form.justification,
            adjustments=(
                service.AdjustmentRequest(code=form.item_code, delta_cents=form.delta_cents),
            ),
        ),
        reference_date=calendario.today(),
    )
    return _revision_saved(req, session, context, revision)


@bp.route(route=NEW_ITEM_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_new_item_error)
def eac_new_item(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Create an item of the EAC: by a reallocation SM or by a revision from an approved SM."""
    project_id = context.scope.require_project()
    form = validation.parse_new_item_form(
        req.form,
        parent_codes=_parent_codes(session, project_id),
        unit_codes={unit.code for unit in configuracoes.list_measure_units(session)},
        responsible_names={person.name for person in configuracoes.list_people(session)},
    )
    reference_date = calendario.today()
    if form.recourse == validation.RECOURSE_REVISION:
        revision = service.create_revision(
            session,
            user=context.user,
            scope=context.scope,
            request=service.RevisionRequest(
                change_id=form.change_id or 0,
                justification=form.justification,
                new_items=(_revision_item_of(form.item, session=session, project_id=project_id),),
            ),
            reference_date=reference_date,
        )
        return _revision_saved(req, session, context, revision)
    created = service.reallocate(
        session,
        user=context.user,
        scope=context.scope,
        request=_new_item_reallocation(form, session=session, project_id=project_id),
        reference_date=reference_date,
    )
    return _reallocation_saved(req, session, context, created)


@bp.route(route=IMPORT_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def eac_import_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """The form of the import of items, opened in the modal of the EAC screen."""
    project_id = context.scope.require_project()
    return AlpineAjaxResponse(
        template_name=IMPORT_FORM_TEMPLATE,
        context={
            "fontes": service.revision_source_options(session, project_id=project_id),
            "filtros": _filters_of(req.params),
            "campo_arquivo": attachments.FILE_FIELD,
            "limite_mb": MAX_FILE_BYTES // MEGABYTE,
            "limite_linhas": MAX_DATA_ROWS,
        },
        request=req,
    )


@bp.route(route=IMPORT_CHECK_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eac_import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Read the spreadsheet of new items and answer what each line will do; nothing is written."""
    context.scope.require_project()
    preview = importing.check(
        session,
        importer=importers.eac_items_importer(),
        upload=_upload_of(req),
        context=_import_context(context),
    )
    data = _check_context(preview)
    data |= _panels_context(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.form),
    )
    data |= {
        "alvo_importacao": IMPORT_RESULT_TARGET,
        "alvo_revisoes": REVISIONS_TARGET,
        "alvo_conteudo": CONTENT_TARGET,
    }
    return AlpineAjaxResponse(template_name=IMPORT_CHECK_TEMPLATE, context=data, request=req)


@bp.route(route=IMPORT_CONFIRM_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def eac_import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Check the file again and create the revision with the writable lines, all or none."""
    project_id = context.scope.require_project()
    upload = _upload_of(req)
    preview = importing.check(
        session,
        importer=importers.eac_items_importer(),
        upload=upload,
        context=_import_context(context),
    )
    _require_importable(upload, preview, req.form)
    form = validation.parse_revision_form(req.form, require_adjustment=False)
    revision = service.create_revision(
        session,
        user=context.user,
        scope=context.scope,
        request=service.RevisionRequest(
            change_id=form.change_id,
            justification=form.justification,
            new_items=importers.revision_items(
                session, project_id=project_id, rows=preview.writable_rows
            ),
        ),
        reference_date=calendario.today(),
    )
    count = len(preview.writable_rows)
    items = IMPORT_ITEM if count == 1 else IMPORT_ITEMS.format(count=count)
    return _revision_saved(
        req,
        session,
        context,
        revision,
        toast=IMPORT_CONFIRMED_MESSAGE.format(
            revision=revision.revision, items=items, total=_money(revision.total_cents)
        ),
    )


# ── Montagem das respostas ───────────────────────────────────────────────


def _project_ids(session: Session, scope: Scope) -> tuple[int, ...]:
    """The projects of the scope: the chosen one, or every project in the Portfólio."""
    if not scope.is_portfolio:
        return (scope.require_project(),)
    return tuple(project.id for project in configuracoes.list_projects(session))


def _revisions_context(
    session: Session,
    scope: Scope,
    *,
    user: User,
    filters: EacFilters,
    erro: str = "",
) -> dict[str, object]:
    project_id = None if scope.is_portfolio else scope.require_project()
    return {
        "revisoes": service.revision_rows(session, project_ids=_project_ids(session, scope)),
        "carteira": scope.is_portfolio,
        "erro": erro,
        "filtros": filters,
        "pode_gravar": project_id is not None and rbac.can(user, Permission.WRITE),
        "proxima_revisao": (
            service.next_revision(session, project_id=project_id) if project_id else 0
        ),
        "itens": service.item_options(session, project_id=project_id) if project_id else (),
        "fontes": (
            service.revision_source_options(session, project_id=project_id) if project_id else ()
        ),
    }


def _reallocations_context(
    session: Session,
    scope: Scope,
    *,
    user: User,
    filters: EacFilters,
    erro: str = "",
) -> dict[str, object]:
    project_id = None if scope.is_portfolio else scope.require_project()
    return {
        "remanejamentos": service.reallocation_rows(
            session, project_ids=_project_ids(session, scope)
        ),
        "carteira": scope.is_portfolio,
        "erro": erro,
        "filtros": filters,
        "pode_gravar": project_id is not None and rbac.can(user, Permission.WRITE),
        "itens": service.item_options(session, project_id=project_id) if project_id else (),
        "subpacotes": (
            service.subpackage_options(session, project_id=project_id) if project_id else ()
        ),
        "fontes": (
            service.revision_source_options(session, project_id=project_id) if project_id else ()
        ),
        "unidades": configuracoes.list_measure_units(session) if project_id else (),
        "pessoas": configuracoes.list_people(session) if project_id else (),
        "tipos_de_custo": validation.COST_TYPES,
        "classificacoes": validation.CLASSIFICATIONS,
        "prioridades": validation.PRIORITIES,
    }


def _panels_context(
    session: Session, *, user: User, scope: Scope, filters: EacFilters, erro: str = ""
) -> dict[str, object]:
    view = service.eac_view(
        session, user=user, scope=scope, filters=filters, reference_date=calendario.today()
    )
    data = _content_context(view)
    data |= _revisions_context(session, scope, user=user, filters=filters, erro=erro)
    data |= _reallocations_context(session, scope, user=user, filters=filters, erro=erro)
    data |= {"alvo_revisoes": REVISIONS_TARGET, "alvo_remanejamentos": REALLOCATIONS_TARGET}
    return data


def _reallocation_request(form: validation.ReallocationForm) -> service.ReallocationRequest:
    return service.ReallocationRequest(
        title=form.title,
        justification=form.justification,
        priority=form.priority,
        transfers=(
            service.TransferRequest(
                source_code=form.origin_code,
                target_code=form.target_code,
                value_cents=form.value_cents,
            ),
        ),
    )


def _new_item_reallocation(
    form: validation.NewItemForm, *, session: Session, project_id: int
) -> service.ReallocationRequest:
    return service.ReallocationRequest(
        justification=form.justification,
        priority=form.priority,
        transfers=(
            service.TransferRequest(
                source_code=form.origin_code,
                target_code=form.item.code,
                value_cents=form.item.budget_cents,
                new_item=_new_item_request(form.item, session=session, project_id=project_id),
            ),
        ),
    )


def _new_item_request(
    item: validation.NewItemInput, *, session: Session, project_id: int
) -> service.NewItemRequest:
    parents = service.eac_item_ids_by_code(session, project_id=project_id, codes=[item.parent_code])
    units = {
        normalize_text(unit.code): unit.id for unit in configuracoes.list_measure_units(session)
    }
    people = {
        normalize_text(person.name): person.id for person in configuracoes.list_people(session)
    }
    return service.NewItemRequest(
        code=item.code,
        description=item.description,
        parent_id=parents.get(item.parent_code),
        unit_id=units.get(normalize_text(item.unit_code)),
        cost_type=item.cost_type,
        capex=item.capex,
        cost_center=item.cost_center,
        responsible_id=people.get(normalize_text(item.responsible_name)),
        quantity=item.quantity,
        unit_price_cents=item.unit_price_cents,
    )


def _revision_item_of(
    item: validation.NewItemInput, *, session: Session, project_id: int
) -> service.RevisionItemRequest:
    request = _new_item_request(item, session=session, project_id=project_id)
    return service.RevisionItemRequest(
        code=request.code,
        description=request.description,
        base_cents=item.budget_cents,
        parent_id=request.parent_id,
        unit_id=request.unit_id,
        cost_type=request.cost_type,
        capex=request.capex,
        cost_center=request.cost_center,
        responsible_id=request.responsible_id,
        quantity=request.quantity,
        unit_price_cents=request.unit_price_cents,
    )


def _parent_codes(session: Session, project_id: int) -> set[str]:
    """The subpackages (level 2) of the project: where a new item can be born."""
    levels = service.eac_item_levels(session, project_id=project_id)
    return {code for code, level in levels.items() if level == PORTFOLIO_MAIN_LEVEL}


def _reallocation_saved(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    created: service.CreatedReallocation,
) -> func.HttpResponse:
    data = _panels_context(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.form),
    )
    return AlpineAjaxResponse(
        template_name=REALLOCATION_SAVED_TEMPLATE,
        context=data,
        request=req,
        toast=REALLOCATION_CREATED_MESSAGE.format(code=created.code),
        toast_tipo="ok",
    )


def _revision_saved(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    revision: service.RevisionView,
    *,
    toast: str | None = None,
) -> func.HttpResponse:
    data = _panels_context(
        session,
        user=context.user,
        scope=context.scope,
        filters=_filters_of(req.form),
    )
    return AlpineAjaxResponse(
        template_name=REVISION_SAVED_TEMPLATE,
        context=data,
        request=req,
        toast=toast
        or REVISION_CREATED_MESSAGE.format(
            revision=revision.revision, total=_money(revision.total_cents)
        ),
        toast_tipo="ok",
    )


def _render_panel_error(
    req: func.HttpRequest, error: DomainError, *, template: str
) -> func.HttpResponse | None:
    """The panels again, with the refusal at the top of the one the person was editing."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            data = _panels_context(
                session,
                user=context.user,
                scope=context.scope,
                filters=_filters_of(req.form),
                erro=str(error),
            )
    except DomainError:
        return None
    return AlpineAjaxResponse(
        template_name=template,
        context=data,
        request=req,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


# ── Importação dos itens (ISSUE-030) ─────────────────────────────────────


def _import_context(context: RequestContext) -> importing.ImportContext:
    return importing.ImportContext(
        user=context.user, scope=context.scope, reference_date=calendario.today()
    )


def _upload_of(req: func.HttpRequest) -> importing.Upload:
    """The file of the form; at most one byte over the limit is read."""
    sent = req.files.get(attachments.FILE_FIELD)
    if sent is None:
        return importing.Upload(name=None, content=b"")
    return importing.Upload(name=sent.filename, content=sent.stream.read(MAX_FILE_BYTES + 1))


def _require_importable(
    upload: importing.Upload, preview: importing.ImportPreview, form: Mapping[str, str | None]
) -> None:
    """The guards of the generic confirmation, before the revision is written."""
    digest = (form.get(validation.FIELD_IMPORT_CHECKED) or "").strip()
    if not digest:
        raise InvalidDataError(importing.NOT_CHECKED_MESSAGE)
    if digest != importing.digest_of(upload):
        raise InvalidDataError(importing.CHANGED_MESSAGE)
    if preview.missing:
        raise InvalidDataError(importing.MISSING_MESSAGE.format(columns=", ".join(preview.missing)))
    if not preview.writable_rows:
        raise InvalidDataError(importing.NOTHING_MESSAGE)
    acknowledged = form.get(validation.FIELD_IMPORT_ACKNOWLEDGED)
    if preview.error_rows and acknowledged != validation.IMPORT_ACKNOWLEDGED_VALUE:
        raise InvalidDataError(importing.NOT_ACKNOWLEDGED_MESSAGE)


def _check_context(preview: importing.ImportPreview) -> dict[str, object]:
    return {
        "arquivo": preview.file_name,
        "preview": preview,
        "colunas": [
            {"cabecalho": column.header, "numerica": column.kind in _NUMERIC_KINDS}
            for column in preview.columns
        ],
        "lidas": len(preview.rows),
        "vao_gravar": len(preview.writable_rows),
        "com_aviso": len(preview.warning_rows),
        "com_erro": len(preview.error_rows),
        "campo_conferido": validation.FIELD_IMPORT_CHECKED,
        "campo_ciente": validation.FIELD_IMPORT_ACKNOWLEDGED,
        "valor_ciente": validation.IMPORT_ACKNOWLEDGED_VALUE,
        "confirmar_url": f"/api/{IMPORT_CONFIRM_ROUTE}",
    }


# ── Mapa de controle, projeção e custos do ERP (ISSUE-031) ───────────────


@dataclass(frozen=True)
class MapaLineView:
    """Uma linha do mapa como os fragmentos a imprimem: a linha e o texto de cada coluna."""

    row: service.MapaRow
    baseline: str
    reallocation: str
    current: str
    committed: str
    actual: str
    saldo: str
    projection: str
    deviation: str
    deviation_percent: str
    can_project: bool


@dataclass(frozen=True)
class ProjectionFormView:
    """O formulário da projeção no término: a linha do item e os valores vigentes."""

    row: service.MapaRow
    current: str
    committed: str
    actual: str
    projection: str


@bp.route(route=MAP_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def mapa_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O mapa de controle do escopo: item a item no projeto, um registro por projeto na carteira."""
    return AlpineAjaxResponse(
        template_name=MAP_TEMPLATE, context=_mapa_context(session, context), request=req
    )


@bp.route(route=MAP_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def mapa_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do mapa de controle: as colunas da tela em R$ integral; no Portfólio com Projeto."""
    del req
    return excel_response(_mapa_document_of(session, context))


@bp.route(route=MAP_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def mapa_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do mapa de controle: o mesmo documento que o Excel imprime."""
    return printable_response(_mapa_document_of(session, context), req)


@bp.route(route=MAP_PROJECTION_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def mapa_projection_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da projeção no término de um item, com os valores vigentes do mapa."""
    row = _projection_row(session, context, _item_id_of(req))
    return AlpineAjaxResponse(
        template_name=MAP_PROJECTION_FORM_TEMPLATE,
        context=_projection_context(row, values={}, problems={}),
        request=req,
    )


def _render_projection_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """O formulário da projeção de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            row = _projection_row(session, context, _item_id_of(req))
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=MAP_PROJECTION_FORM_TEMPLATE,
        context=_projection_context(row, values=_posted_projection(req.form), problems=problems),
        request=req,
        target_id=PROJECTION_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=MAP_PROJECTION_SAVE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_projection_error)
def mapa_projection_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Atualiza a projeção no término do item: justificativa obrigatória e fato no histórico."""
    item_id = _item_id_of(req)
    row = _projection_row(session, context, item_id)
    form = validation.parse_projection_form(req.form)
    service.update_projection(
        session,
        item_id=item_id,
        valor_centavos=form.value_cents,
        justificativa=form.justification,
        autor_id=context.user.person_id,
        hoje=calendario.today(),
    )
    return AlpineAjaxResponse(
        template_name=MAP_PROJECTION_SAVED_TEMPLATE,
        context=_mapa_context(session, context),
        request=req,
        toast=PROJECTION_SAVED_MESSAGE.format(code=row.code),
        toast_tipo="ok",
    )


@bp.route(route=ERP_IMPORT_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def erp_import_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da importação dos custos do ERP, aberto no modal do mapa de controle."""
    del session
    context.scope.require_project()
    return AlpineAjaxResponse(
        template_name=ERP_IMPORT_FORM_TEMPLATE,
        context={
            "campo_arquivo": attachments.FILE_FIELD,
            "limite_mb": MAX_FILE_BYTES // MEGABYTE,
            "limite_linhas": MAX_DATA_ROWS,
        },
        request=req,
    )


@bp.route(route=ERP_IMPORT_CHECK_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def erp_import_check(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Lê a planilha do fechamento e responde o que cada linha vai gravar; nada é escrito."""
    context.scope.require_project()
    preview = importing.check(
        session,
        importer=importers.erp_costs_importer(),
        upload=_upload_of(req),
        context=_import_context(context),
    )
    data = _erp_check_context(preview)
    data |= _mapa_context(session, context)
    return AlpineAjaxResponse(template_name=ERP_IMPORT_CHECK_TEMPLATE, context=data, request=req)


@bp.route(route=ERP_IMPORT_CONFIRM_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS)
def erp_import_confirm(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Checa a planilha de novo e grava o fechamento do mês por item e mês: só na confirmação."""
    context.scope.require_project()
    importer = importers.erp_costs_importer()
    result = importing.confirm(
        session,
        importer=importer,
        upload=_upload_of(req),
        context=_import_context(context),
        confirmation=importing.Confirmation(
            checked_digest=(req.form.get(validation.FIELD_IMPORT_CHECKED) or "").strip() or None,
            acknowledged=req.form.get(validation.FIELD_IMPORT_ACKNOWLEDGED)
            == validation.IMPORT_ACKNOWLEDGED_VALUE,
        ),
    )
    data: dict[str, object] = {
        "resultado": result,
        "importador": importer.title,
        "alvo_conteudo": MAP_TARGET,
    }
    data |= _mapa_context(session, context)
    return AlpineAjaxResponse(
        template_name=ERP_IMPORT_RESULT_TEMPLATE,
        context=data,
        request=req,
        toast=_erp_imported_notice(result),
        toast_tipo="aviso" if result.skipped else "ok",
    )


def _projection_row(session: Session, context: RequestContext, item_id: int) -> service.MapaRow:
    """A linha do item no mapa do escopo; no Portfólio ou fora do item do projeto, a rota recusa."""
    if context.scope.is_portfolio:
        raise AccessDeniedError(PROJECTION_PORTFOLIO_MESSAGE)
    view = service.mapa_controle(session, scope=context.scope, reference_date=calendario.today())
    row = next((line for line in view.rows if line.item_id == item_id), None)
    if row is None:
        raise InvalidDataError(service.NOT_FOUND_MESSAGE)
    return row


def _projection_context(
    row: service.MapaRow, *, values: Mapping[str, str | None], problems: Mapping[str, str]
) -> dict[str, object]:
    return {
        "formulario": ProjectionFormView(
            row=row,
            current=_money(row.current_cents),
            committed=_money(row.committed_cents),
            actual=_money(row.actual_cents),
            projection=_money(row.projection_cents),
        ),
        "valores": values,
        "erros": problems,
        "alvo_conteudo": MAP_TARGET,
    }


def _posted_projection(form: Mapping[str, str | None]) -> dict[str, str | None]:
    return {
        validation.FIELD_PROJECTION: form.get(validation.FIELD_PROJECTION),
        validation.FIELD_JUSTIFICATION: form.get(validation.FIELD_JUSTIFICATION),
    }


def _mapa_document_of(session: Session, context: RequestContext) -> Document:
    view = service.mapa_controle(session, scope=context.scope, reference_date=calendario.today())
    return export.mapa_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _mapa_context(
    session: Session, context: RequestContext, *, erro: str = ""
) -> dict[str, object]:
    view = service.mapa_controle(session, scope=context.scope, reference_date=calendario.today())
    pode_gravar = not view.is_portfolio and rbac.can(context.user, Permission.WRITE)
    return {
        "mapa": view,
        "linhas": [_mapa_line(line, pode_gravar=pode_gravar) for line in view.rows],
        "total": _mapa_line(view.total, pode_gravar=False),
        "carteira": view.is_portfolio,
        "pode_gravar": pode_gravar,
        "resultado": "conteudo" if view.rows else "vazio-origem",
        "grafico": _mapa_grafico(view, pode_gravar=pode_gravar),
        "alvo_conteudo": MAP_TARGET,
        "alvo_formulario": PROJECTION_FORM_TARGET,
        "erro": erro,
    }


def _mapa_line(row: service.MapaRow, *, pode_gravar: bool) -> MapaLineView:
    return MapaLineView(
        row=row,
        baseline=_money(row.baseline_cents),
        reallocation=_delta_money(row.reallocation_cents),
        current=_money(row.current_cents),
        committed=_money(row.committed_cents),
        actual=_money(row.actual_cents),
        saldo=_money(row.saldo_cents),
        projection=_money(row.projection_cents),
        deviation=_signed_money(row.deviation_cents),
        deviation_percent=_percent(row.deviation_percent),
        can_project=pode_gravar and row.level >= LEAF_LEVEL and row.item_id is not None,
    )


def _mil(cents: int) -> float:
    """O valor em R$ mil, com uma casa, como a grade do mapa mostra (a exportação é integral)."""
    return float((Decimal(cents) / MIL_CENTS).quantize(MIL_ONE_PLACE, rounding=ROUND_HALF_UP))


def _mapa_grafico(view: service.MapaControleView, *, pode_gravar: bool) -> dict[str, object]:
    """O mapa no contrato do visual Tabela Heatmap (D11): R$ mil e o desvio pintado pelas faixas.

    As faixas são as dos parâmetros vigentes e chegam prontas no JSON; a coluna do desvio
    percentual é a única pintada, e o valor de cada item mostra o sinal e o ícone da faixa,
    nunca só a cor. Com escrita, a célula do desvio do item carrega o id que abre a projeção.
    """
    faixas = list(calculations.deviation_heatmap_faixas(view.bands))
    return {
        "titulo": MAP_TITLE_PORTFOLIO if view.is_portfolio else MAP_TITLE_PROJECT,
        "rotulo_linhas": MAP_PROJECT_ROW_LABEL if view.is_portfolio else MAP_ITEM_ROW_LABEL,
        "cabecalho": "horizontal",
        "casas": 1,
        "colunas": _mapa_grafico_colunas(view.total, carteira=view.is_portfolio),
        "linhas": [
            _mapa_grafico_linha(row, carteira=view.is_portfolio, pode_gravar=pode_gravar)
            for row in view.rows
        ],
        "total": {"linha": view.total.description, "coluna": False},
        "faixas": {"padrao": faixas, "total": faixas},
    }


def _mapa_grafico_colunas(total: service.MapaRow, *, carteira: bool) -> list[dict[str, object]]:
    colunas: list[dict[str, object]] = []
    if not carteira:
        colunas.append({"id": MAP_DESCRIPTION_ID, "rotulo": "Descrição", "calor": False})
    colunas.extend(
        {
            "id": coluna,
            "rotulo": rotulo,
            "calor": False,
            "casas": 1,
            "sinal": sinal,
            "total": _mil(getattr(total, campo)),
        }
        for coluna, rotulo, sinal, campo in MAP_MONEY_COLUMNS
    )
    colunas.append(_mapa_grafico_coluna_percentual(total.deviation_percent))
    return colunas


def _mapa_grafico_coluna_percentual(percent: Decimal | None) -> dict[str, object]:
    coluna: dict[str, object] = {
        "id": MAP_PERCENT_ID,
        "rotulo": "Desvio %",
        "casas": 1,
        "unidade": "%",
        "sinal": True,
        "somar": False,
    }
    if percent is not None:
        coluna["total"] = float(percent)
    return coluna


def _mapa_grafico_linha(
    row: service.MapaRow, *, carteira: bool, pode_gravar: bool
) -> dict[str, object]:
    valores: dict[str, object] = {
        coluna: _mil(getattr(row, campo)) for coluna, _rotulo, _sinal, campo in MAP_MONEY_COLUMNS
    }
    if not carteira:
        valores[MAP_DESCRIPTION_ID] = {"texto": row.description}
    valores[MAP_PERCENT_ID] = _mapa_grafico_celula_percentual(row, pode_gravar=pode_gravar)
    return {
        "id": row.code,
        "rotulo": row.project_label if carteira else row.code,
        "valores": valores,
    }


def _mapa_grafico_celula_percentual(row: service.MapaRow, *, pode_gravar: bool) -> object:
    percent = row.deviation_percent
    if percent is None:
        return None
    if pode_gravar and row.level >= LEAF_LEVEL and row.item_id is not None:
        return {"valor": float(percent), "selecionavel": True, "id": row.item_id}
    return float(percent)


def _signed_money(cents: int) -> str:
    return f"+{_money(cents)}" if cents > 0 else _money(cents)


def _delta_money(cents: int) -> str:
    return "" if cents == 0 else _signed_money(cents)


def _erp_check_context(preview: importing.ImportPreview) -> dict[str, object]:
    return {
        "arquivo": preview.file_name,
        "preview": preview,
        "colunas": [
            {"cabecalho": column.header, "numerica": column.kind in _NUMERIC_KINDS}
            for column in preview.columns
        ],
        "lidas": len(preview.rows),
        "vao_gravar": len(preview.writable_rows),
        "com_aviso": len(preview.warning_rows),
        "com_erro": len(preview.error_rows),
        "campo_conferido": validation.FIELD_IMPORT_CHECKED,
        "campo_ciente": validation.FIELD_IMPORT_ACKNOWLEDGED,
        "valor_ciente": validation.IMPORT_ACKNOWLEDGED_VALUE,
        "confirmar_url": f"/api/{ERP_IMPORT_CONFIRM_ROUTE}",
        "alvo_conteudo": MAP_TARGET,
    }


def _erp_imported_notice(result: importing.ImportResult) -> str:
    written = len(result.written)
    notice = (
        ERP_IMPORTED_ONE_MESSAGE if written == 1 else ERP_IMPORTED_MESSAGE.format(count=written)
    )
    if result.skipped:
        return notice + ERP_SKIPPED_SUFFIX.format(count=len(result.skipped))
    return notice


# ── Ficha do contrato: medições e aditivos (ISSUE-032) ───────────────────


@dataclass(frozen=True)
class MedicaoLineView:
    """Uma medição como a tabela a imprime: os textos prontos e as transições que a situação admite."""

    medicao: service.MeasurementView
    periodo: str
    bruto: str
    retencao: str
    liquido: str
    situacao_tom: str
    pode_aprovar: bool
    pode_faturar: bool
    pode_pagar: bool
    pode_devolver: bool


@bp.route(route=CONTRACT_RESUME_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_resumo(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Resumo da ficha: os KPIs, a cascata do valor e os dados do contrato."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_RESUME_TEMPLATE,
        context=_contrato_resumo_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_MEASUREMENTS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_medicoes(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """As medições da ficha, da mais recente para a mais antiga, com as transições do fluxo."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENTS_TEMPLATE,
        context=_contrato_medicoes_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_ADDENDA_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_aditivos(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Os aditivos da ficha, do mais recente para o mais antigo."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_ADDENDA_TEMPLATE,
        context=_contrato_aditivos_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def contrato_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da ficha: o Resumo com os KPIs e as tabelas de medições e aditivos."""
    return excel_response(_contrato_document_of(req, session, context))


@bp.route(route=CONTRACT_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da ficha: o mesmo documento do Excel, com a cascata desenhada."""
    return printable_response(_contrato_document_of(req, session, context), req)


@bp.route(route=CONTRACT_MEASUREMENT_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_medicao_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da medição nova, com o saldo disponível do contrato."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENT_FORM_TEMPLATE,
        context=_contrato_medicao_form_context(view, values={}, problems={}),
        request=req,
    )


def _render_medicao_form_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """O formulário da medição de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENT_FORM_TEMPLATE,
        context=_contrato_medicao_form_context(
            view,
            values=_posted_medicao(req.form),
            problems=problems,
            message="" if problems else str(error),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_MEASUREMENT_CREATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_medicao_form_error)
def contrato_medicao_create(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o boletim de medição Em análise e devolve a ficha atualizada."""
    view = _contract_of(req, session, context)
    medicao = service.create_measurement(
        session,
        user=context.user,
        scope=context.scope,
        contract_id=view.id,
        form=_posted_medicao(req.form),
    )
    return _contrato_saved(
        req,
        session,
        context,
        toast=CONTRACT_MEASUREMENT_CREATED_MESSAGE.format(number=medicao.number),
    )


def _render_contrato_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """A ficha de volta, com a recusa no painel das medições, no 422 ou no 409."""
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    data = _contrato_context(view, user=context.user)
    data["erro"] = str(error)
    return AlpineAjaxResponse(
        template_name=CONTRACT_SAVED_TEMPLATE,
        context=data,
        request=req,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_MEASUREMENT_APPROVE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_contrato_error)
def contrato_medicao_approve(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Aprova a medição: o bruto passa a contar como medido e alimenta a EAC."""
    return _move_measurement(req, session, context, target=calculations.SITUATION_APPROVED)


@bp.route(route=CONTRACT_MEASUREMENT_INVOICE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_contrato_error)
def contrato_medicao_invoice(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o faturamento da medição aprovada."""
    return _move_measurement(req, session, context, target=calculations.SITUATION_INVOICED)


@bp.route(route=CONTRACT_MEASUREMENT_PAY_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_contrato_error)
def contrato_medicao_pay(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o pagamento da medição faturada."""
    return _move_measurement(req, session, context, target=calculations.SITUATION_PAID)


@bp.route(route=CONTRACT_MEASUREMENT_RETURN_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_medicao_return_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da devolução da medição, com o motivo obrigatório."""
    view = _contract_of(req, session, context)
    medicao = _medicao_of(view, _medicao_id_of(req))
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENT_RETURN_TEMPLATE,
        context=_contrato_devolucao_context(view, medicao, values={}, problems={}),
        request=req,
    )


def _render_devolucao_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """O formulário da devolução de volta, com o motivo digitado, no 422 ou no 409."""
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
            medicao = _medicao_of(view, _medicao_id_of(req))
    except DomainError:
        return None
    problems = (
        error.detail
        if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping)
        else {}
    )
    return AlpineAjaxResponse(
        template_name=CONTRACT_MEASUREMENT_RETURN_TEMPLATE,
        context=_contrato_devolucao_context(
            view,
            medicao,
            values=_posted_transition(req.form),
            problems=problems,
            message=str(error) if isinstance(error, VersionConflictError) else "",
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_MEASUREMENT_RETURN_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_devolucao_error)
def contrato_medicao_return(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Devolve a medição à contratada, com o motivo obrigatório."""
    return _move_measurement(req, session, context, target=calculations.SITUATION_RETURNED)


@bp.route(route=CONTRACT_ADDENDUM_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_aditivo_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do aditivo novo, com as SM aprovadas do projeto."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_ADDENDUM_FORM_TEMPLATE,
        context=_contrato_aditivo_form_context(session, view, values={}, problems={}),
        request=req,
    )


def _render_aditivo_form_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """O formulário do aditivo de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=CONTRACT_ADDENDUM_FORM_TEMPLATE,
        context=_contrato_aditivo_form_context(
            session,
            view,
            values=_posted_aditivo(req.form),
            problems=problems,
            message="" if problems else str(error),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_ADDENDUM_CREATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_aditivo_form_error)
def contrato_aditivo_create(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o aditivo aprovado e prorroga o término vigente quando ele tem dias."""
    view = _contract_of(req, session, context)
    aditivo = service.create_addendum(
        session,
        user=context.user,
        scope=context.scope,
        contract_id=view.id,
        form=_posted_aditivo(req.form),
    )
    message = CONTRACT_ADDENDUM_CREATED_MESSAGE.format(number=aditivo.number)
    if aditivo.days:
        message += CONTRACT_ADDENDUM_EXTENDED_SUFFIX.format(days=aditivo.days)
    return _contrato_saved(req, session, context, toast=message)


# ── Montagem da ficha do contrato ────────────────────────────────────────


def _contract_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> service.ContractView:
    """A ficha do contrato do número pedido; número ausente ou desconhecido é 422."""
    return service.contract_by_number(
        session, user=context.user, number=req.params.get(CONTRACT_NUMBER_PARAMETER) or ""
    )


def _medicao_id_of(req: func.HttpRequest) -> int:
    raw = req.route_params.get(CONTRACT_MEASUREMENT_PARAMETER) or ""
    if not raw.isdigit():
        raise InvalidDataError(service.MEASUREMENT_NOT_FOUND_MESSAGE)
    return int(raw)


def _medicao_of(view: service.ContractView, medicao_id: int) -> service.MeasurementView:
    medicao = next((row for row in view.measurements if row.id == medicao_id), None)
    if medicao is None:
        raise InvalidDataError(service.MEASUREMENT_NOT_FOUND_MESSAGE)
    return medicao


def _move_measurement(
    req: func.HttpRequest, session: Session, context: RequestContext, *, target: str
) -> func.HttpResponse:
    view = _contract_of(req, session, context)
    medicao = _medicao_of(view, _medicao_id_of(req))
    moved = service.transition_measurement(
        session,
        user=context.user,
        scope=context.scope,
        measurement_id=medicao.id,
        target=target,
        form=_posted_transition(req.form),
    )
    return _contrato_saved(req, session, context, toast=_moved_message(moved))


def _moved_message(medicao: service.MeasurementView) -> str:
    if medicao.situation == calculations.SITUATION_RETURNED:
        return CONTRACT_MEASUREMENT_RETURNED_MESSAGE.format(number=medicao.number)
    return CONTRACT_MEASUREMENT_MOVED_MESSAGE.format(
        number=medicao.number, situation=medicao.situation.lower()
    )


def _contrato_saved(
    req: func.HttpRequest, session: Session, context: RequestContext, *, toast: str
) -> func.HttpResponse:
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_SAVED_TEMPLATE,
        context=_contrato_context(view, user=context.user),
        request=req,
        toast=toast,
        toast_tipo="ok",
    )


def _contrato_document_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    view = _contract_of(req, session, context)
    return export.contrato_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _contrato_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    data = _contrato_resumo_context(view, user=user)
    data |= _contrato_medicoes_context(view, user=user)
    data |= _contrato_aditivos_context(view, user=user)
    return data


def _contrato_resumo_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    return {
        "ficha": view,
        "pode_gerir": rbac.can(user, Permission.MANAGE),
        "cascata": _cascata_data(view),
        "anexos_url": f"/api/anexos?origem={service.ATTACHMENT_TABLE}&registro={view.id}",
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_medicoes_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    pode_gerir = rbac.can(user, Permission.MANAGE)
    return {
        "ficha": view,
        "pode_gerir": pode_gerir,
        "linhas": [_medicao_line(row, pode_gerir=pode_gerir) for row in view.measurements],
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_aditivos_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    return {
        "ficha": view,
        "pode_gerir": rbac.can(user, Permission.MANAGE),
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_medicao_form_context(
    view: service.ContractView,
    *,
    values: Mapping[str, str | None],
    problems: Mapping[str, str],
    message: str = "",
) -> dict[str, object]:
    return {
        "ficha": view,
        "valores": values,
        "erros": problems,
        "mensagem": message,
        "disponivel": _money(view.available_to_measure_cents),
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_devolucao_context(
    view: service.ContractView,
    medicao: service.MeasurementView,
    *,
    values: Mapping[str, str | None],
    problems: Mapping[str, str],
    message: str = "",
) -> dict[str, object]:
    return {
        "ficha": view,
        "medicao": medicao,
        "bruto": _money(medicao.gross_cents),
        "valores": values,
        "erros": problems,
        "mensagem": message,
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _contrato_aditivo_form_context(
    session: Session,
    view: service.ContractView,
    *,
    values: Mapping[str, str | None],
    problems: Mapping[str, str],
    message: str = "",
) -> dict[str, object]:
    return {
        "ficha": view,
        "valores": values,
        "erros": problems,
        "mensagem": message,
        "sms": service.change_options(session, project_id=view.project_id),
        "hoje": calendario.today(),
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
    }


def _cascata_data(view: service.ContractView) -> dict[str, object]:
    return {
        "titulo": "Composição do valor do contrato",
        "formato": {"divisor": 100, "moeda": "BRL", "casas": 0},
        "etapas": [dict(step) for step in view.cascade],
    }


def _medicao_line(medicao: service.MeasurementView, *, pode_gerir: bool) -> MedicaoLineView:
    return MedicaoLineView(
        medicao=medicao,
        periodo=medicao.period.strftime("%m/%Y"),
        bruto=_money(medicao.gross_cents),
        retencao=_money(medicao.retention_cents),
        liquido=_money(medicao.net_cents),
        situacao_tom=_SITUATION_PILLS.get(medicao.situation, "neutral"),
        pode_aprovar=pode_gerir
        and validation.measurement_transition_allowed(
            medicao.situation, calculations.SITUATION_APPROVED
        ),
        pode_faturar=pode_gerir
        and validation.measurement_transition_allowed(
            medicao.situation, calculations.SITUATION_INVOICED
        ),
        pode_pagar=pode_gerir
        and validation.measurement_transition_allowed(
            medicao.situation, calculations.SITUATION_PAID
        ),
        pode_devolver=pode_gerir
        and validation.measurement_transition_allowed(
            medicao.situation, calculations.SITUATION_RETURNED
        ),
    )


def _posted_medicao(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_MEASUREMENT_PERIOD,
        validation.FIELD_MEASUREMENT_VALUE,
        validation.FIELD_MEASUREMENT_MILESTONE,
    )
    return {name: form.get(name) for name in names}


def _posted_transition(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (validation.FIELD_VERSION, validation.FIELD_MEASUREMENT_REASON)
    return {name: form.get(name) for name in names}


def _posted_aditivo(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_ADDENDUM_DATE,
        validation.FIELD_ADDENDUM_VALUE,
        validation.FIELD_ADDENDUM_DAYS,
        validation.FIELD_ADDENDUM_CHANGE,
        validation.FIELD_ADDENDUM_REASON,
    )
    return {name: form.get(name) for name in names}


# ── Marcos, claims e EOT da ficha (ISSUE-033) ────────────────────────────


@dataclass(frozen=True)
class MarcoLineView:
    """Um marco como a tabela o imprime: o atraso, o tom da situação e as transições do fluxo."""

    marco: service.MilestoneView
    atrasado: bool
    atraso_dias: int
    situacao_tom: str
    pode_enviar_evidencia: bool
    pode_aprovar: bool
    pode_faturar: bool
    pode_pagar: bool


@dataclass(frozen=True)
class ClaimLineView:
    """Um claim como a tabela o imprime: o tom da situação e as portas de atualização e decisão."""

    claim: service.ClaimView
    situacao_tom: str
    pode_atualizar: bool
    pode_decidir: bool


@dataclass(frozen=True)
class EotLineView:
    """Uma EOT como a tabela a imprime: o tom da situação e a porta da decisão."""

    eot: service.ExtensionView
    situacao_tom: str
    pode_decidir: bool


@bp.route(route=CONTRACT_MILESTONES_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_marcos(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Os marcos de pagamento da ficha, com o atraso, a evidência e a soma dos percentuais."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_MILESTONES_TEMPLATE,
        context=_contrato_marcos_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_CLAIMS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_claims(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Os claims da ficha, do mais recente para o mais antigo, com o alerta de notificação."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_CLAIMS_TEMPLATE,
        context=_contrato_claims_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_EXTENSIONS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_extensoes(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """As extensões de prazo da ficha, com a decisão e a SM da linha de base do cronograma."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_EXTENSIONS_TEMPLATE,
        context=_contrato_extensoes_context(view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_MILESTONES_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def contrato_marcos_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da aba dos marcos de pagamento, com o atraso e a soma dos percentuais."""
    return excel_response(_contrato_marcos_document_of(req, session, context))


@bp.route(route=CONTRACT_MILESTONES_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_marcos_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da aba dos marcos: o mesmo documento do Excel."""
    return printable_response(_contrato_marcos_document_of(req, session, context), req)


@bp.route(route=CONTRACT_CLAIMS_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def contrato_claims_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da aba dos claims, com o alerta de notificação fora do prazo."""
    return excel_response(_contrato_claims_document_of(req, session, context))


@bp.route(route=CONTRACT_CLAIMS_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_claims_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da aba dos claims: o mesmo documento do Excel."""
    return printable_response(_contrato_claims_document_of(req, session, context), req)


@bp.route(route=CONTRACT_EXTENSIONS_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def contrato_extensoes_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da aba das extensões de prazo, com a decisão e a SM."""
    return excel_response(_contrato_extensoes_document_of(req, session, context))


@bp.route(route=CONTRACT_EXTENSIONS_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_extensoes_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da aba das extensões de prazo: o mesmo documento do Excel."""
    return printable_response(_contrato_extensoes_document_of(req, session, context), req)


@bp.route(route=CONTRACT_MILESTONE_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_marco_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do marco novo, com o percentual que ainda cabe nos 100% do contrato."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_MILESTONE_FORM_TEMPLATE,
        context=_contrato_marco_form_context(view, FormState.empty()),
        request=req,
    )


def _render_marco_form_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """O formulário do marco de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=CONTRACT_MILESTONE_FORM_TEMPLATE,
        context=_contrato_marco_form_context(
            view,
            FormState(
                values=_posted_marco(req.form),
                problems=problems,
                message="" if problems else str(error),
            ),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_MILESTONE_CREATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_marco_form_error)
def contrato_marco_create(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cadastra o marco Previsto e devolve a ficha atualizada."""
    view = _contract_of(req, session, context)
    marco = service.create_milestone(
        session,
        user=context.user,
        scope=context.scope,
        contract_id=view.id,
        form=_posted_marco(req.form),
    )
    return _fluxos_saved(
        req,
        session,
        context,
        toast=CONTRACT_MILESTONE_CREATED_MESSAGE.format(number=marco.number),
    )


@bp.route(route=CONTRACT_MILESTONE_EVIDENCE_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_marco_evidencia_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da evidência do marco, com a data de conclusão e o arquivo."""
    view = _contract_of(req, session, context)
    marco = _marco_of(view, _marco_id_of(req))
    return AlpineAjaxResponse(
        template_name=CONTRACT_MILESTONE_EVIDENCE_TEMPLATE,
        context=_contrato_evidencia_context(session, view, marco, FormState.empty()),
        request=req,
    )


def _render_evidencia_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """O formulário da evidência de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
            marco = _marco_of(view, _marco_id_of(req))
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=CONTRACT_MILESTONE_EVIDENCE_TEMPLATE,
        context=_contrato_evidencia_context(
            session,
            view,
            marco,
            FormState(
                values=_posted_evidencia(req.form),
                problems=problems,
                message="" if problems else str(error),
            ),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_MILESTONE_EVIDENCE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_evidencia_error)
def contrato_marco_evidencia(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Envia a evidência do marco: a data de conclusão e o anexo de verdade (D5a)."""
    view = _contract_of(req, session, context)
    marco = _marco_of(view, _marco_id_of(req))
    sent = req.files.get(attachments.FILE_FIELD)
    updated = service.send_milestone_evidence(
        session,
        user=context.user,
        scope=context.scope,
        milestone_id=marco.id,
        form=_posted_evidencia(req.form),
        reference_date=calendario.today(),
        file_name=sent.filename if sent is not None else None,
        content=sent.stream.read() if sent is not None else b"",
    )
    return _fluxos_saved(
        req,
        session,
        context,
        toast=CONTRACT_MILESTONE_EVIDENCE_MESSAGE.format(number=updated.number),
    )


def _render_marcos_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """A ficha de volta, com a recusa no painel dos marcos, no 422 ou no 409."""
    return _render_fluxos_error(req, error, area="marcos")


@bp.route(route=CONTRACT_MILESTONE_APPROVE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_marcos_error)
def contrato_marco_approve(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Aprova o marco: exige o anexo de evidência gravado (D5a)."""
    view = _contract_of(req, session, context)
    marco = _marco_of(view, _marco_id_of(req))
    approved = service.approve_milestone(
        session,
        user=context.user,
        scope=context.scope,
        milestone_id=marco.id,
        form=_posted_versao(req.form),
    )
    return _fluxos_saved(
        req,
        session,
        context,
        toast=CONTRACT_MILESTONE_MOVED_MESSAGE.format(
            number=approved.number, situation=approved.situation.lower()
        ),
    )


@bp.route(route=CONTRACT_MILESTONE_INVOICE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_marcos_error)
def contrato_marco_invoice(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o faturamento do marco aprovado."""
    return _move_marco(req, session, context, target=calculations.MILESTONE_INVOICED)


@bp.route(route=CONTRACT_MILESTONE_PAY_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_marcos_error)
def contrato_marco_pay(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o pagamento do marco faturado."""
    return _move_marco(req, session, context, target=calculations.MILESTONE_PAID)


@bp.route(route=CONTRACT_CLAIM_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_claim_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário do claim novo, com o prazo de notificação do contrato."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_CLAIM_FORM_TEMPLATE,
        context=_contrato_claim_form_context(session, view, FormState.empty()),
        request=req,
    )


def _render_claim_form_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """O formulário do claim de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
            return AlpineAjaxResponse(
                template_name=CONTRACT_CLAIM_FORM_TEMPLATE,
                context=_contrato_claim_form_context(
                    session,
                    view,
                    FormState(
                        values=_posted_claim(req.form),
                        problems=problems,
                        message="" if problems else str(error),
                    ),
                ),
                request=req,
                target_id=CONTRACT_FORM_TARGET,
                status_code=422,
                toast=str(error),
                toast_tipo="erro",
            )
    except DomainError:
        return None


@bp.route(route=CONTRACT_CLAIM_CREATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_claim_form_error)
def contrato_claim_create(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra o claim Notificado, com o código sequencial do projeto."""
    view = _contract_of(req, session, context)
    claim = service.create_claim(
        session,
        user=context.user,
        scope=context.scope,
        contract_id=view.id,
        form=_posted_claim(req.form),
    )
    return _fluxos_saved(
        req, session, context, toast=CONTRACT_CLAIM_CREATED_MESSAGE.format(code=claim.code)
    )


@bp.route(route=CONTRACT_CLAIM_UPDATE_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_claim_update_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário de atualização do claim, com as próximas situações do fluxo."""
    view = _contract_of(req, session, context)
    claim = _claim_of(view, _claim_id_of(req))
    return AlpineAjaxResponse(
        template_name=CONTRACT_CLAIM_UPDATE_TEMPLATE,
        context=_contrato_claim_update_context(
            view,
            claim,
            FormState.empty(),
            action=_claim_action(view, claim.id, CONTRACT_CLAIM_UPDATE_ROUTE),
            situations=_claim_transitions(claim),
        ),
        request=req,
    )


@bp.route(route=CONTRACT_CLAIM_DECIDE_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_claim_decide_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da decisão de mérito do claim: Acordado ou Rejeitado."""
    view = _contract_of(req, session, context)
    claim = _claim_of(view, _claim_id_of(req))
    return AlpineAjaxResponse(
        template_name=CONTRACT_CLAIM_UPDATE_TEMPLATE,
        context=_contrato_claim_update_context(
            view,
            claim,
            FormState.empty(),
            action=_claim_action(view, claim.id, CONTRACT_CLAIM_DECIDE_ROUTE),
            situations=_claim_decisions(claim),
        ),
        request=req,
    )


def _render_claim_update_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """O formulário de atualização do claim de volta, com o que a pessoa digitou, no 422."""
    return _render_claim_form_update(req, error, route=CONTRACT_CLAIM_UPDATE_ROUTE)


def _render_claim_decide_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """O formulário da decisão do claim de volta, com o que a pessoa digitou, no 422."""
    return _render_claim_form_update(req, error, route=CONTRACT_CLAIM_DECIDE_ROUTE)


def _render_claim_form_update(
    req: func.HttpRequest, error: DomainError, *, route: str
) -> func.HttpResponse | None:
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
            claim = _claim_of(view, _claim_id_of(req))
    except DomainError:
        return None
    problems = (
        error.detail
        if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping)
        else {}
    )
    return AlpineAjaxResponse(
        template_name=CONTRACT_CLAIM_UPDATE_TEMPLATE,
        context=_contrato_claim_update_context(
            view,
            claim,
            FormState(
                values=_posted_claim_update(req.form),
                problems=problems,
                message=str(error) if isinstance(error, VersionConflictError) else "",
            ),
            action=_claim_action(view, claim.id, route),
            situations=_claim_decisions(claim)
            if route == CONTRACT_CLAIM_DECIDE_ROUTE
            else _claim_transitions(claim),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_CLAIM_UPDATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_claim_update_error)
def contrato_claim_update(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Atualiza o claim no fluxo, com o parecer e o reconhecido do acordo."""
    view = _contract_of(req, session, context)
    claim = _claim_of(view, _claim_id_of(req))
    updated = service.update_claim(
        session,
        user=context.user,
        scope=context.scope,
        claim_id=claim.id,
        form=_posted_claim_update(req.form),
        reference_date=calendario.today(),
    )
    return _fluxos_saved(req, session, context, toast=_claim_moved_message(updated))


@bp.route(route=CONTRACT_CLAIM_DECIDE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_claim_decide_error)
def contrato_claim_decide(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A decisão de mérito do claim: Acordado (com a SM) ou Rejeitado."""
    view = _contract_of(req, session, context)
    claim = _claim_of(view, _claim_id_of(req))
    decided = service.decide_claim(
        session,
        user=context.user,
        scope=context.scope,
        claim_id=claim.id,
        form=_posted_claim_update(req.form),
        reference_date=calendario.today(),
    )
    return _fluxos_saved(req, session, context, toast=_claim_moved_message(decided))


@bp.route(route=CONTRACT_EXTENSION_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_extensao_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da extensão de prazo nova, com os claims de prazo do contrato."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_EXTENSION_FORM_TEMPLATE,
        context=_contrato_eot_form_context(view, FormState.empty()),
        request=req,
    )


def _render_eot_form_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse | None:
    """O formulário da extensão de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=CONTRACT_EXTENSION_FORM_TEMPLATE,
        context=_contrato_eot_form_context(
            view,
            FormState(
                values=_posted_eot(req.form),
                problems=problems,
                message="" if problems else str(error),
            ),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_EXTENSION_CREATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_eot_form_error)
def contrato_extensao_create(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra a EOT Solicitada, com o claim de origem opcional do contrato."""
    view = _contract_of(req, session, context)
    eot = service.create_extension(
        session,
        user=context.user,
        scope=context.scope,
        contract_id=view.id,
        form=_posted_eot(req.form),
        reference_date=calendario.today(),
    )
    return _fluxos_saved(
        req, session, context, toast=CONTRACT_EXTENSION_CREATED_MESSAGE.format(code=eot.code)
    )


@bp.route(route=CONTRACT_EXTENSION_DECISION_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_extensao_decisao_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da decisão da EOT: Concedida (integral ou parcial) ou Negada."""
    view = _contract_of(req, session, context)
    eot = _extensao_of(view, _extensao_id_of(req))
    return AlpineAjaxResponse(
        template_name=CONTRACT_EXTENSION_DECISION_TEMPLATE,
        context=_contrato_eot_decisao_context(view, eot, FormState.empty()),
        request=req,
    )


def _render_eot_decisao_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """O formulário da decisão da EOT de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
            eot = _extensao_of(view, _extensao_id_of(req))
    except DomainError:
        return None
    problems = (
        error.detail
        if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping)
        else {}
    )
    return AlpineAjaxResponse(
        template_name=CONTRACT_EXTENSION_DECISION_TEMPLATE,
        context=_contrato_eot_decisao_context(
            view,
            eot,
            FormState(
                values=_posted_eot_decisao(req.form),
                problems=problems,
                message=str(error) if isinstance(error, VersionConflictError) else "",
            ),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_EXTENSION_DECISION_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_eot_decisao_error)
def contrato_extensao_decide(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Decide a EOT; a concessão prorroga o término vigente e cria a SM do cronograma."""
    view = _contract_of(req, session, context)
    eot = _extensao_of(view, _extensao_id_of(req))
    decided = service.decide_extension(
        session,
        user=context.user,
        scope=context.scope,
        extension_id=eot.id,
        form=_posted_eot_decisao(req.form),
        reference_date=calendario.today(),
    )
    return _fluxos_saved(req, session, context, toast=_extension_moved_message(decided))


def _move_marco(
    req: func.HttpRequest, session: Session, context: RequestContext, *, target: str
) -> func.HttpResponse:
    view = _contract_of(req, session, context)
    marco = _marco_of(view, _marco_id_of(req))
    moved = service.transition_milestone(
        session,
        user=context.user,
        scope=context.scope,
        milestone_id=marco.id,
        target=target,
        form=_posted_versao(req.form),
    )
    return _fluxos_saved(
        req,
        session,
        context,
        toast=CONTRACT_MILESTONE_MOVED_MESSAGE.format(
            number=moved.number, situation=moved.situation.lower()
        ),
    )


def _fluxos_saved(
    req: func.HttpRequest, session: Session, context: RequestContext, *, toast: str
) -> func.HttpResponse:
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_FLOWS_SAVED_TEMPLATE,
        context=_contrato_fluxos_context(view, user=context.user),
        request=req,
        toast=toast,
        toast_tipo="ok",
    )


def _render_fluxos_error(
    req: func.HttpRequest, error: DomainError, *, area: str
) -> func.HttpResponse | None:
    """A ficha de volta, com a recusa no painel da área, no 422 ou no 409."""
    if not isinstance(error, InvalidDataError | VersionConflictError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
    except DomainError:
        return None
    data = _contrato_fluxos_context(view, user=context.user)
    data[f"erro_{area}"] = str(error)
    return AlpineAjaxResponse(
        template_name=CONTRACT_FLOWS_SAVED_TEMPLATE,
        context=data,
        request=req,
        status_code=409 if isinstance(error, VersionConflictError) else 422,
        toast=str(error),
        toast_tipo="erro",
    )


def _contrato_fluxos_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    data = _contrato_context(view, user=user)
    data |= _contrato_marcos_context(view, user=user)
    data |= _contrato_claims_context(view, user=user)
    data |= _contrato_extensoes_context(view, user=user)
    return data


def _fluxos_targets() -> dict[str, str]:
    return {
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_resumo": CONTRACT_RESUME_TARGET,
        "alvo_medicoes": CONTRACT_MEASUREMENTS_TARGET,
        "alvo_aditivos": CONTRACT_ADDENDA_TARGET,
        "alvo_marcos": CONTRACT_MILESTONES_TARGET,
        "alvo_claims": CONTRACT_CLAIMS_TARGET,
        "alvo_extensoes": CONTRACT_EXTENSIONS_TARGET,
    }


def _contrato_marcos_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    pode_gerir = rbac.can(user, Permission.MANAGE)
    reference_date = calendario.today()
    return {
        "ficha": view,
        "pode_gerir": pode_gerir,
        "linhas_marcos": [
            _marco_line(row, reference_date=reference_date, pode_gerir=pode_gerir)
            for row in view.milestones
        ],
        "soma_pct": view.milestone_pct_total,
        "disponivel_pct": calculations.MILESTONE_PCT_TOTAL - view.milestone_pct_total,
        "erro_marcos": "",
        **_fluxos_targets(),
    }


def _contrato_claims_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    pode_gerir = rbac.can(user, Permission.MANAGE)
    return {
        "ficha": view,
        "pode_gerir": pode_gerir,
        "linhas_claims": [_claim_line(row, pode_gerir=pode_gerir) for row in view.claims],
        "erro_claims": "",
        **_fluxos_targets(),
    }


def _contrato_extensoes_context(view: service.ContractView, *, user: User) -> dict[str, object]:
    pode_gerir = rbac.can(user, Permission.MANAGE)
    return {
        "ficha": view,
        "pode_gerir": pode_gerir,
        "linhas_extensoes": [_eot_line(row, pode_gerir=pode_gerir) for row in view.extensions],
        "erro_extensoes": "",
        **_fluxos_targets(),
    }


@dataclass(frozen=True)
class FormState:
    """O que os formulários dos fluxos devolvem: o que a pessoa digitou, os erros e a mensagem."""

    values: Mapping[str, str | None]
    problems: Mapping[str, str]
    message: str = ""

    @classmethod
    def empty(cls) -> FormState:
        """O formulário recém-aberto: sem valores digitados nem erros."""
        return cls(values={}, problems={})


def _contrato_marco_form_context(view: service.ContractView, state: FormState) -> dict[str, object]:
    return {
        "ficha": view,
        "valores": state.values,
        "erros": state.problems,
        "mensagem": state.message,
        "disponivel_pct": calculations.MILESTONE_PCT_TOTAL - view.milestone_pct_total,
        **_fluxos_targets(),
    }


def _contrato_evidencia_context(
    session: Session,
    view: service.ContractView,
    marco: service.MilestoneView,
    state: FormState,
) -> dict[str, object]:
    limits = attachments.current_limits(session, reference_date=calendario.today())
    return {
        "ficha": view,
        "marco": marco,
        "valores": state.values,
        "erros": state.problems,
        "mensagem": state.message,
        "campo_arquivo": attachments.FILE_FIELD,
        "limite_mb": limits.max_megabytes_text,
        "tipos": ", ".join(limits.types),
        "aceitos": ",".join(f".{extension}" for extension in limits.extensions),
        **_fluxos_targets(),
    }


def _contrato_claim_form_context(
    session: Session, view: service.ContractView, state: FormState
) -> dict[str, object]:
    """O formulário do claim novo: as listas do contrato e os riscos do projeto (ISSUE-067)."""
    from src.modulos.riscos import service as riscos

    return {
        "ficha": view,
        "valores": state.values,
        "erros": state.problems,
        "mensagem": state.message,
        "direcoes": validation.CLAIM_DIRECTIONS,
        "tipos": validation.CLAIM_KINDS,
        "causas": validation.CLAIM_CAUSES,
        "riscos": riscos.risk_options(session, project_id=view.project_id),
        **_fluxos_targets(),
    }


def _contrato_claim_update_context(
    view: service.ContractView,
    claim: service.ClaimView,
    state: FormState,
    *,
    action: str,
    situations: tuple[str, ...],
) -> dict[str, object]:
    return {
        "ficha": view,
        "claim": claim,
        "valores": state.values,
        "erros": state.problems,
        "mensagem": state.message,
        "acao": action,
        "situacoes": situations,
        **_fluxos_targets(),
    }


def _contrato_eot_form_context(view: service.ContractView, state: FormState) -> dict[str, object]:
    return {
        "ficha": view,
        "valores": state.values,
        "erros": state.problems,
        "mensagem": state.message,
        "claims": [row for row in view.claims if row.kind != validation.CLAIM_KIND_COST],
        "metodos": validation.EXTENSION_METHODS,
        **_fluxos_targets(),
    }


def _contrato_eot_decisao_context(
    view: service.ContractView,
    eot: service.ExtensionView,
    state: FormState,
) -> dict[str, object]:
    return {
        "ficha": view,
        "eot": eot,
        "valores": state.values,
        "erros": state.problems,
        "mensagem": state.message,
        "decisoes": validation.EXTENSION_DECISIONS,
        "classificacoes": validation.EXTENSION_CLASSIFICATIONS,
        **_fluxos_targets(),
    }


def _marco_line(
    marco: service.MilestoneView, *, reference_date: date, pode_gerir: bool
) -> MarcoLineView:
    late = calculations.milestone_is_late(marco.expected_on, marco.situation, reference_date)
    return MarcoLineView(
        marco=marco,
        atrasado=late,
        atraso_dias=calculations.milestone_late_days(marco.expected_on, reference_date)
        if late
        else 0,
        situacao_tom=_MILESTONE_PILLS.get(marco.situation, "neutral"),
        pode_enviar_evidencia=pode_gerir
        and validation.milestone_transition_allowed(
            marco.situation, calculations.MILESTONE_EVIDENCE_SENT
        ),
        pode_aprovar=pode_gerir
        and validation.milestone_transition_allowed(
            marco.situation, calculations.MILESTONE_APPROVED
        ),
        pode_faturar=pode_gerir
        and validation.milestone_transition_allowed(
            marco.situation, calculations.MILESTONE_INVOICED
        ),
        pode_pagar=pode_gerir
        and validation.milestone_transition_allowed(marco.situation, calculations.MILESTONE_PAID),
    )


def _claim_line(claim: service.ClaimView, *, pode_gerir: bool) -> ClaimLineView:
    targets = _claim_transitions(claim)
    return ClaimLineView(
        claim=claim,
        situacao_tom=_CLAIM_PILLS.get(claim.situation, "neutral"),
        pode_atualizar=pode_gerir
        and any(target not in service.CLAIM_DECISIONS for target in targets),
        pode_decidir=pode_gerir and any(target in service.CLAIM_DECISIONS for target in targets),
    )


def _eot_line(eot: service.ExtensionView, *, pode_gerir: bool) -> EotLineView:
    return EotLineView(
        eot=eot,
        situacao_tom=_EXTENSION_PILLS.get(eot.situation, "neutral"),
        pode_decidir=pode_gerir
        and any(
            validation.extension_transition_allowed(eot.situation, target)
            for target in validation.EXTENSION_DECISIONS
        ),
    )


def _claim_transitions(claim: service.ClaimView) -> tuple[str, ...]:
    return validation.CLAIM_TRANSITIONS.get(claim.situation, ())


def _claim_decisions(claim: service.ClaimView) -> tuple[str, ...]:
    return tuple(
        target for target in _claim_transitions(claim) if target in service.CLAIM_DECISIONS
    )


def _claim_action(view: service.ContractView, claim_id: int, route: str) -> str:
    return f"/api/{route.format(claim_id=claim_id)}?numero={view.number}"


def _claim_moved_message(claim: service.ClaimView) -> str:
    message = CONTRACT_CLAIM_MOVED_MESSAGE.format(
        code=claim.code, situation=claim.situation.lower()
    )
    if claim.change_code:
        message += CONTRACT_CLAIM_AGREED_SUFFIX.format(code=claim.change_code)
    return message


def _extension_moved_message(eot: service.ExtensionView) -> str:
    message = CONTRACT_EXTENSION_MOVED_MESSAGE.format(
        code=eot.code, situation=eot.situation.lower()
    )
    if eot.granted_days:
        message += CONTRACT_EXTENSION_EXTENDED_SUFFIX.format(days=eot.granted_days)
    return message


def _marco_of(view: service.ContractView, marco_id: int) -> service.MilestoneView:
    marco = next((row for row in view.milestones if row.id == marco_id), None)
    if marco is None:
        raise InvalidDataError(service.MILESTONE_NOT_FOUND_MESSAGE)
    return marco


def _claim_of(view: service.ContractView, claim_id: int) -> service.ClaimView:
    claim = next((row for row in view.claims if row.id == claim_id), None)
    if claim is None:
        raise InvalidDataError(service.CLAIM_NOT_FOUND_MESSAGE)
    return claim


def _extensao_of(view: service.ContractView, extensao_id: int) -> service.ExtensionView:
    eot = next((row for row in view.extensions if row.id == extensao_id), None)
    if eot is None:
        raise InvalidDataError(service.EXTENSION_NOT_FOUND_MESSAGE)
    return eot


def _marco_id_of(req: func.HttpRequest) -> int:
    raw = req.route_params.get(CONTRACT_MILESTONE_PARAMETER) or ""
    if not raw.isdigit():
        raise InvalidDataError(service.MILESTONE_NOT_FOUND_MESSAGE)
    return int(raw)


def _claim_id_of(req: func.HttpRequest) -> int:
    raw = req.route_params.get(CONTRACT_CLAIM_PARAMETER) or ""
    if not raw.isdigit():
        raise InvalidDataError(service.CLAIM_NOT_FOUND_MESSAGE)
    return int(raw)


def _extensao_id_of(req: func.HttpRequest) -> int:
    raw = req.route_params.get(CONTRACT_EXTENSION_PARAMETER) or ""
    if not raw.isdigit():
        raise InvalidDataError(service.EXTENSION_NOT_FOUND_MESSAGE)
    return int(raw)


def _posted_versao(form: Mapping[str, str | None]) -> dict[str, str | None]:
    return {validation.FIELD_VERSION: form.get(validation.FIELD_VERSION)}


def _posted_marco(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_MILESTONE_DESCRIPTION,
        validation.FIELD_MILESTONE_CRITERIA,
        validation.FIELD_MILESTONE_PCT,
        validation.FIELD_MILESTONE_EXPECTED,
        validation.FIELD_VERSION,
    )
    return {name: form.get(name) for name in names}


def _posted_evidencia(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (validation.FIELD_MILESTONE_COMPLETED, validation.FIELD_VERSION)
    return {name: form.get(name) for name in names}


def _posted_claim(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_CLAIM_DIRECTION,
        validation.FIELD_CLAIM_KIND,
        validation.FIELD_CLAIM_CAUSE,
        validation.FIELD_CLAIM_CLAUSE,
        validation.FIELD_CLAIM_DESCRIPTION,
        validation.FIELD_CLAIM_EVENT,
        validation.FIELD_CLAIM_NOTIFICATION,
        validation.FIELD_CLAIM_VALUE,
        validation.FIELD_CLAIM_DAYS,
        validation.FIELD_CLAIM_RISK,
        validation.FIELD_VERSION,
    )
    return {name: form.get(name) for name in names}


def _posted_claim_update(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_CLAIM_SITUATION,
        validation.FIELD_CLAIM_RECOGNIZED,
        validation.FIELD_CLAIM_DAYS,
        validation.FIELD_CLAIM_STATEMENT,
        validation.FIELD_VERSION,
    )
    return {name: form.get(name) for name in names}


def _posted_eot(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_EXTENSION_CLAIM,
        validation.FIELD_EXTENSION_EVENT,
        validation.FIELD_EXTENSION_DAYS,
        validation.FIELD_EXTENSION_MILESTONE,
        validation.FIELD_EXTENSION_METHOD,
        validation.FIELD_VERSION,
    )
    return {name: form.get(name) for name in names}


def _posted_eot_decisao(form: Mapping[str, str | None]) -> dict[str, str | None]:
    names = (
        validation.FIELD_EXTENSION_SITUATION,
        validation.FIELD_EXTENSION_DAYS,
        validation.FIELD_EXTENSION_CLASSIFICATION,
        validation.FIELD_EXTENSION_STATEMENT,
        validation.FIELD_VERSION,
    )
    return {name: form.get(name) for name in names}


def _contrato_marcos_document_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    view = _contract_of(req, session, context)
    return export.contrato_marcos_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _contrato_claims_document_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    view = _contract_of(req, session, context)
    return export.contrato_claims_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _contrato_extensoes_document_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    view = _contract_of(req, session, context)
    return export.contrato_extensoes_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


# ── Avaliação de desempenho da contratada (ISSUE-034) ────────────────────


@dataclass(frozen=True)
class AvaliacaoLineView:
    """Uma avaliação como a tabela a imprime: o período, as notas por critério e o tom da classe."""

    avaliacao: service.EvaluationView
    periodo: str
    notas: tuple[service.EvaluationCriterionView | None, ...]
    notas_baixas: tuple[bool, ...]
    classe_tom: str


@bp.route(route=CONTRACT_EVALUATIONS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_avaliacoes(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """As avaliações de desempenho da ficha, com a série do Gráfico de Áreas de Avaliação."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_EVALUATIONS_TEMPLATE,
        context=_contrato_avaliacoes_context(session, view, user=context.user),
        request=req,
    )


@bp.route(route=CONTRACT_EVALUATIONS_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def contrato_avaliacoes_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da aba das avaliações, com as notas por critério, a nota e a classe."""
    return excel_response(_contrato_avaliacoes_document_of(req, session, context))


@bp.route(route=CONTRACT_EVALUATIONS_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contrato_avaliacoes_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da aba das avaliações: o mesmo documento do Excel."""
    return printable_response(_contrato_avaliacoes_document_of(req, session, context), req)


@bp.route(route=CONTRACT_EVALUATION_FORM_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS)
def contrato_avaliacao_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O formulário da avaliação nova, com os critérios vigentes e os seus pesos."""
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_EVALUATION_FORM_TEMPLATE,
        context=_contrato_avaliacao_form_context(session, view, FormState.empty()),
        request=req,
    )


def _render_avaliacao_form_error(
    req: func.HttpRequest, error: DomainError
) -> func.HttpResponse | None:
    """O formulário da avaliação de volta, com o que a pessoa digitou, no 422."""
    if not isinstance(error, InvalidDataError):
        return None
    try:
        with database.unidade_de_trabalho() as session:
            context = authorize(session, req, WRITE_ACCESS)
            view = _contract_of(req, session, context)
            criterios = _criterios_da_avaliacao(session)
    except DomainError:
        return None
    problems = error.detail if isinstance(error.detail, Mapping) else {}
    return AlpineAjaxResponse(
        template_name=CONTRACT_EVALUATION_FORM_TEMPLATE,
        context=_contrato_avaliacao_form_context(
            session,
            view,
            FormState(
                values=_posted_avaliacao(req.form, criterios=criterios),
                problems=problems,
                message="" if problems else str(error),
            ),
        ),
        request=req,
        target_id=CONTRACT_FORM_TARGET,
        status_code=422,
        toast=str(error),
        toast_tipo="erro",
    )


@bp.route(route=CONTRACT_EVALUATION_CREATE_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_render_avaliacao_form_error)
def contrato_avaliacao_create(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Registra a avaliação com os pesos congelados; a nota baixa exige a evidência."""
    view = _contract_of(req, session, context)
    criterios = _criterios_da_avaliacao(session)
    sent = req.files.get(attachments.FILE_FIELD)
    avaliacao = service.create_evaluation(
        session,
        user=context.user,
        scope=context.scope,
        contract_id=view.id,
        form=_posted_avaliacao(req.form, criterios=criterios),
        reference_date=calendario.today(),
        file_name=sent.filename if sent is not None else None,
        content=sent.stream.read() if sent is not None else b"",
    )
    return _avaliacao_saved(req, session, context, toast=_avaliacao_created_message(avaliacao))


def _avaliacao_saved(
    req: func.HttpRequest, session: Session, context: RequestContext, *, toast: str
) -> func.HttpResponse:
    view = _contract_of(req, session, context)
    return AlpineAjaxResponse(
        template_name=CONTRACT_EVALUATION_SAVED_TEMPLATE,
        context=_contrato_avaliacoes_context(session, view, user=context.user),
        request=req,
        toast=toast,
        toast_tipo="ok",
    )


def _avaliacao_created_message(avaliacao: service.EvaluationView) -> str:
    message = CONTRACT_EVALUATION_CREATED_MESSAGE.format(
        kind=avaliacao.kind.lower(), period=avaliacao.period.strftime("%m/%Y")
    )
    if avaliacao.requires_plan:
        message += CONTRACT_EVALUATION_PLAN_SUFFIX
    if avaliacao.kind == calculations.EVALUATION_KIND_FINAL:
        message += CONTRACT_EVALUATION_LESSON_SUFFIX
    return message


def _contrato_avaliacoes_context(
    session: Session, view: service.ContractView, *, user: User
) -> dict[str, object]:
    criterios = _criterios_da_avaliacao(session)
    limite_plano = int(_avaliacao_parametros(session)["notaExigePlano"])
    return {
        "ficha": view,
        "pode_gerir": rbac.can(user, Permission.MANAGE),
        "criterios": criterios,
        "linhas_avaliacoes": [
            _avaliacao_line(avaliacao, criterios=criterios, limite_plano=limite_plano)
            for avaliacao in view.evaluations
        ],
        "grafico": _avaliacao_grafico(_classes_da_avaliacao(session), view.evaluation_trend),
        "erro_avaliacoes": "",
        "limite_plano": limite_plano,
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_avaliacoes": CONTRACT_EVALUATIONS_TARGET,
    }


def _contrato_avaliacao_form_context(
    session: Session, view: service.ContractView, state: FormState
) -> dict[str, object]:
    limits = attachments.current_limits(session, reference_date=calendario.today())
    sugestao = _sugestao_hse(session, view)
    return {
        "ficha": view,
        "valores": state.values,
        "erros": state.problems,
        "mensagem": state.message,
        "criterios": _criterios_da_avaliacao(session),
        "tipos": calculations.EVALUATION_KINDS,
        "campo_arquivo": attachments.FILE_FIELD,
        "campo_evidencia": service.EVALUATION_EVIDENCE_FIELD,
        "limite_mb": limits.max_megabytes_text,
        "tipos_arquivo": ", ".join(limits.types),
        "aceitos": ",".join(f".{extension}" for extension in limits.extensions),
        "limite_plano": int(_avaliacao_parametros(session)["notaExigePlano"]),
        "sugestao_hse": sugestao,
        "sugestoes": {"hse": str(sugestao.note)} if sugestao is not None else {},
        "sugestao_hse_texto": _sugestao_hse_texto(sugestao),
        "alvo_formulario": CONTRACT_FORM_TARGET,
        "alvo_avaliacoes": CONTRACT_EVALUATIONS_TARGET,
    }


def _sugestao_hse(session: Session, view: service.ContractView) -> hse_painel.CompanyHseNote | None:
    """A nota HSE sugerida da empresa do contrato, na janela do projeto dele (ISSUE-075).

    O painel do HSE calcula a nota de 1 a 5 pela TRIF da empresa contra a do projeto; o
    formulário a exibe e a pré-seleciona no critério HSE, e o avaliador pode trocá-la — a nota
    gravada é a que ele confirmar.
    """
    return hse_painel.company_note_suggestion(
        session,
        company_id=view.company_id,
        scope=Scope(project_id=view.project_id, source="url"),
        reference_date=calendario.today(),
    )


def _sugestao_hse_texto(sugestao: hse_painel.CompanyHseNote | None) -> str:
    """``Sugestão do HSE: nota 3 · TRIF da empresa 11,01 contra 8,88 do projeto``."""
    if sugestao is None:
        return "Sugestão do HSE: sem HHT registrado para a empresa no projeto."
    return (
        f"Sugestão do HSE: nota {sugestao.note}"
        f" · TRIF da empresa {_two_decimals(sugestao.trif)}"
        f" contra {_two_decimals(sugestao.project_trif)} do projeto"
    )


def _two_decimals(value: Decimal) -> str:
    return format_value(ValueKind.DECIMAL, value, 2)


def _avaliacao_parametros(session: Session) -> dict[str, Any]:
    """O grupo vigente da avaliação, com o valor inicial do que faltar, como o serviço o lê."""
    values = configuracoes.current_group(
        session, group=service.EVALUATION_GROUP, reference_date=calendario.today()
    )
    initial = configuracoes.INITIAL_PARAMETERS[service.EVALUATION_GROUP]
    return {**initial, **values}


def _criterios_da_avaliacao(session: Session) -> tuple[service.EvaluationCriterionSpec, ...]:
    """Os critérios vigentes da avaliação, para o formulário e os rótulos das tabelas."""
    return tuple(
        service.EvaluationCriterionSpec(
            id=str(item["id"]),
            name=str(item.get("nome") or item["id"]),
            weight=int(item["peso"]),
        )
        for item in _avaliacao_parametros(session)["criterios"]
    )


def _classes_da_avaliacao(session: Session) -> tuple[calculations.EvaluationClass, ...]:
    """As classes vigentes da avaliação: as faixas do gráfico e as notas mínimas."""
    return tuple(
        calculations.EvaluationClass(
            name=str(item["classe"]),
            minimum=int(item["minimo"]),
            description=str(item.get("descricao", "")),
        )
        for item in _avaliacao_parametros(session)["classes"]
    )


def _avaliacao_grafico(
    classes: tuple[calculations.EvaluationClass, ...],
    trend: tuple[dict[str, int], ...],
) -> dict[str, object]:
    """O contrato de dados do Gráfico de Áreas de Avaliação: as classes e a série de notas."""
    zonas = sorted(classes, key=lambda classe: classe.minimum)
    data: dict[str, object] = {
        "titulo": CONTRACT_EVALUATIONS_CHART_TITLE,
        "unidade": "%",
        "casas": 0,
        "zonas": [
            {
                "de": classe.minimum,
                "rotulo": f"Classe {classe.name}",
                "papel": _EVALUATION_CLASS_PAPEIS.get(classe.name.upper(), "neutro"),
            }
            for classe in zonas
        ],
        "pontos": list(trend),
        "rotulos": {"vazio": "Nenhuma avaliação registrada."},
    }
    if zonas:
        data["meta"] = zonas[-1].minimum
    return data


def _avaliacao_line(
    avaliacao: service.EvaluationView,
    *,
    criterios: tuple[service.EvaluationCriterionSpec, ...],
    limite_plano: int,
) -> AvaliacaoLineView:
    congeladas = {item.criterion: item for item in avaliacao.criteria}
    notas = tuple(congeladas.get(criterio.id) for criterio in criterios)
    return AvaliacaoLineView(
        avaliacao=avaliacao,
        periodo=avaliacao.period.strftime("%m/%Y"),
        notas=notas,
        notas_baixas=tuple(nota is not None and nota.note <= limite_plano for nota in notas),
        classe_tom=_EVALUATION_CLASS_PILLS.get(avaliacao.score_class, "neutral"),
    )


def _posted_avaliacao(
    form: Mapping[str, str | None], *, criterios: tuple[service.EvaluationCriterionSpec, ...]
) -> dict[str, str | None]:
    names = (
        validation.FIELD_EVALUATION_PERIOD,
        validation.FIELD_EVALUATION_KIND,
        validation.FIELD_EVALUATION_COMMENT,
        *(criterio.id for criterio in criterios),
    )
    return {name: form.get(name) for name in names}


def _contrato_avaliacoes_document_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    view = _contract_of(req, session, context)
    return export.contrato_avaliacoes_document(
        view,
        criteria=_criterios_da_avaliacao(session),
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


# ── Visão consolidada da administração contratual (ISSUE-035) ────────────


@dataclass(frozen=True)
class ContratosFilters:
    """O que a pessoa digitou nos filtros da visão consolidada: a busca e o contrato escolhido."""

    search: str = ""
    contract: str = ""

    @property
    def is_active(self) -> bool:
        """Se algum filtro estreita as listas (os KPIs seguem do escopo inteiro)."""
        return bool(self.search.strip() or self.contract.strip())


@dataclass(frozen=True)
class ContratoKpiCard:
    """Um KPI da administração contratual como o cartão da tela o imprime."""

    label: str
    value: str
    icon: str
    tone: str
    reference: str
    footer: str = ""
    unit: str = ""


@dataclass(frozen=True)
class ContratoLinha:
    """Uma linha da aba Contratos: a linha do serviço e os textos que a tabela imprime."""

    contrato: service.ContractOverviewRow
    medido: str
    dias_aditados: str
    classe: str
    classe_tom: str


@dataclass(frozen=True)
class ClaimLinha:
    """Uma linha da aba Claims: o claim e o tom da situação."""

    claim: service.ClaimOverviewRow
    situacao_tom: str


@dataclass(frozen=True)
class ExtensaoLinha:
    """Uma linha da aba Extensões de prazo: a EOT e o tom da situação."""

    eot: service.ExtensionOverviewRow
    situacao_tom: str


@dataclass(frozen=True)
class MarcoLinha:
    """Uma linha da aba Marcos de pagamento: o marco e o tom da situação."""

    marco: service.MilestoneOverviewRow
    situacao_tom: str


@dataclass(frozen=True)
class AvaliacaoLinha:
    """Uma linha da aba Avaliações: a avaliação, o período como a tabela o imprime e a classe."""

    avaliacao: service.EvaluationOverviewRow
    periodo: str
    classe_tom: str


CONTRATOS_SUB_CONTRATOS = (
    "Valor atual = original + aditivos; saldo = valor atual menos medido aprovado"
)
CONTRATOS_SUB_AVALIACOES = (
    "Nota ponderada de 0 a 100 com os pesos gravados em cada avaliação · "
    "nota 1 ou 2 em algum critério exige plano de melhoria"
)
CONTRATOS_LIMIT_PERCENT = Decimal(10)


@bp.route(route=CONTRATOS_CONSOLIDADO_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contratos_consolidado(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A visão consolidada da administração contratual: os KPIs e as cinco abas do escopo."""
    view, filtered, filters = _contratos_consolidado_view(req, session, context)
    return AlpineAjaxResponse(
        template_name=(
            CONTRATOS_CONSOLIDADO_PARTS_TEMPLATE
            if _asks_for_contratos_parts(req)
            else CONTRATOS_CONSOLIDADO_TEMPLATE
        ),
        context=_contratos_consolidado_context(view, filtered, filters=filters, context=context),
        request=req,
    )


@bp.route(route=CONTRATOS_CONSOLIDADO_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def contratos_consolidado_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da visão consolidada: os KPIs do escopo e as cinco tabelas, com os filtros."""
    return file_response(
        build_workbook(_contratos_consolidado_document_of(req, session, context)),
        filename=_contratos_file_name(session, context),
        content_type=XLSX_CONTENT_TYPE,
    )


@bp.route(route=CONTRATOS_CONSOLIDADO_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contratos_consolidado_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da visão consolidada: o mesmo documento do Excel."""
    return printable_response(_contratos_consolidado_document_of(req, session, context), req)


def _contratos_consolidado_view(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> tuple[service.ContractsOverview, service.ContractsOverview, ContratosFilters]:
    """A leitura do escopo e a cópia com os filtros: os KPIs são da visão inteira."""
    view = service.contracts_overview(
        session, user=context.user, scope=context.scope, reference_date=calendario.today()
    )
    filters = _contratos_filters_of(req)
    return view, _filter_contratos(view, filters), filters


def _contratos_consolidado_document_of(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> Document:
    view, filtered, filters = _contratos_consolidado_view(req, session, context)
    return export.contratos_consolidado_document(
        view,
        filtered=filtered,
        filter_label=_contratos_filter_label(filters),
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _contratos_file_name(session: Session, context: RequestContext) -> str:
    """``contratos-<código do projeto|portfolio>.xlsx``: o nome que o protótipo dava ao arquivo."""
    if context.scope.is_portfolio:
        return "contratos-portfolio.xlsx"
    project = next(
        (
            item
            for item in configuracoes.list_projects(session)
            if item.id == context.scope.project_id
        ),
        None,
    )
    return f"contratos-{project.code if project is not None else context.scope.parameter}.xlsx"


def _contratos_filters_of(req: func.HttpRequest) -> ContratosFilters:
    return ContratosFilters(
        search=(req.params.get("busca") or "").strip(),
        contract=(req.params.get(CONTRATOS_FILTER_PARAMETER) or "").strip(),
    )


def _contratos_filter_label(filters: ContratosFilters) -> str:
    parts: list[str] = []
    if filters.search:
        parts.append(f"busca: {filters.search}")
    if filters.contract:
        parts.append(f"contrato: {filters.contract}")
    return " · ".join(parts)


def _asks_for_contratos_parts(req: func.HttpRequest) -> bool:
    targets = (req.headers.get("X-Alpine-Target") or "").split()
    return all(block in targets for block in CONTRATOS_FILTERED_BLOCKS)


def _filter_contratos(
    view: service.ContractsOverview, filters: ContratosFilters
) -> service.ContractsOverview:
    """As cinco listas filtradas; o resumo e os indicadores seguem do escopo inteiro."""
    if not filters.is_active:
        return view
    needle = normalize_text(filters.search)
    number = filters.contract
    return replace(
        view,
        contracts=tuple(item for item in view.contracts if _contrato_matches(item, needle, number)),
        claims=tuple(item for item in view.claims if _claim_matches(item, needle, number)),
        extensions=tuple(
            item for item in view.extensions if _extensao_matches(item, needle, number)
        ),
        milestones=tuple(item for item in view.milestones if _marco_matches(item, needle, number)),
        evaluations=tuple(
            item for item in view.evaluations if _avaliacao_matches(item, needle, number)
        ),
    )


def _matches(needle: str, *fields: str) -> bool:
    return not needle or needle in normalize_text(" ".join(fields))


def _by_contract(number: str, contract_number: str) -> bool:
    return not number or number == contract_number


def _contrato_matches(item: service.ContractOverviewRow, needle: str, number: str) -> bool:
    if not _by_contract(number, item.number):
        return False
    return _matches(needle, item.number, item.company, item.object, item.modality)


def _claim_matches(item: service.ClaimOverviewRow, needle: str, number: str) -> bool:
    if not _by_contract(number, item.contract_number):
        return False
    return _matches(
        needle,
        item.code,
        item.contract_number,
        item.description,
        item.cause,
        item.kind,
        item.direction,
    )


def _extensao_matches(item: service.ExtensionOverviewRow, needle: str, number: str) -> bool:
    if not _by_contract(number, item.contract_number):
        return False
    return _matches(
        needle,
        item.code,
        item.contract_number,
        item.event,
        item.claim_code,
        item.affected_milestone,
    )


def _marco_matches(item: service.MilestoneOverviewRow, needle: str, number: str) -> bool:
    if not _by_contract(number, item.contract_number):
        return False
    return _matches(needle, item.number, item.contract_number, item.description, item.criteria)


def _avaliacao_matches(item: service.EvaluationOverviewRow, needle: str, number: str) -> bool:
    if not _by_contract(number, item.contract_number):
        return False
    return _matches(
        needle,
        item.contract_number,
        item.company,
        _period_text(item.view.period),
        item.view.comment,
    )


def _contratos_consolidado_context(
    view: service.ContractsOverview,
    filtered: service.ContractsOverview,
    *,
    filters: ContratosFilters,
    context: RequestContext,
) -> dict[str, object]:
    return {
        "visao": view,
        "carteira": view.is_portfolio,
        "vazio": view.is_empty,
        "cartoes": _contratos_cards(view),
        "sub_contratos": CONTRATOS_SUB_CONTRATOS,
        "sub_claims": _claims_subtitle(view),
        "sub_extensoes": _extensions_subtitle(view),
        "sub_marcos": _milestones_subtitle(view),
        "sub_avaliacoes": CONTRATOS_SUB_AVALIACOES,
        "contratos": [_contrato_line(item) for item in filtered.contracts],
        "claims": [
            ClaimLinha(claim=item, situacao_tom=_CLAIM_PILLS.get(item.situation, "neutral"))
            for item in filtered.claims
        ],
        "extensoes": [
            ExtensaoLinha(eot=item, situacao_tom=_EXTENSION_PILLS.get(item.situation, "neutral"))
            for item in filtered.extensions
        ],
        "marcos": [
            MarcoLinha(marco=item, situacao_tom=_MILESTONE_PILLS.get(item.situation, "neutral"))
            for item in filtered.milestones
        ],
        "avaliacoes": [
            AvaliacaoLinha(
                avaliacao=item,
                periodo=_period_text(item.view.period),
                classe_tom=_EVALUATION_CLASS_PILLS.get(item.view.score_class, "neutral"),
            )
            for item in filtered.evaluations
        ],
        "filtros": filters,
        "contrato_opcoes": [
            (item.number, f"{item.number} {item.company}") for item in view.contracts
        ],
        "projeto": context.scope.parameter,
        "alvo_conteudo": CONTRATOS_CONSOLIDADO_TARGET,
        "alvo_kpis": CONTRATOS_KPIS_TARGET,
        "alvo_tabelas": CONTRATOS_TABELAS_TARGET,
    }


def _contratos_cards(view: service.ContractsOverview) -> tuple[ContratoKpiCard, ...]:
    """Os seis cartões da tela, cada um com a referência de gestão e a nota do protótipo."""
    summary = view.summary
    indicators = view.indicators
    total_cents = sum(item.current_value_cents for item in view.contracts)
    paid_forecast = indicators.paid_forecast_percent
    average_score = indicators.average_score
    extension = indicators.extension_percent
    return (
        ContratoKpiCard(
            label="Contratos",
            value=_integer(summary.contracts),
            icon="file",
            tone="info",
            reference="Contratos do escopo",
            footer=f"{_money(total_cents)} em valor atual",
        ),
        ContratoKpiCard(
            label="Exposição de claims",
            value=_money(summary.exposure_cents),
            icon="money",
            tone="warn" if summary.exposure_cents else "ok",
            reference="Esperado: R$ 0,00",
            footer=_open_claims_text(summary.open_claims),
        ),
        ContratoKpiCard(
            label="Notificados fora do prazo",
            value=_integer(summary.late_notifications),
            icon="clock",
            tone="erro" if summary.late_notifications else "ok",
            reference="Esperado: 0",
            footer="risco de preclusão do pleito",
        ),
        ContratoKpiCard(
            label="Marcos atrasados",
            value=_integer(summary.late_milestones),
            icon="pin",
            tone="warn" if summary.late_milestones else "ok",
            reference="Esperado: 0",
            footer=(
                ""
                if paid_forecast is None
                else f"pago {_percent1(paid_forecast)} do previsto até hoje"
            ),
        ),
        ContratoKpiCard(
            label="Extensão de prazo",
            value="·" if extension is None else format_value(ValueKind.DECIMAL, extension, 1),
            icon="calendar",
            tone="warn"
            if extension is not None and extension > CONTRATOS_LIMIT_PERCENT
            else "info",
            reference="Limite: ≤ 10%",
            footer=(
                f"{indicators.granted_days} de {indicators.requested_days} "
                "dias solicitados concedidos"
            ),
            unit="%",
        ),
        ContratoKpiCard(
            label="Contratadas C ou D",
            value=_integer(summary.contractors_c_or_d),
            icon="person",
            tone="warn" if summary.contractors_c_or_d else "ok",
            reference="Esperado: 0",
            footer="" if average_score is None else f"nota média {_decimal1(average_score)}",
        ),
    )


def _contrato_line(item: service.ContractOverviewRow) -> ContratoLinha:
    evaluation = item.last_evaluation
    return ContratoLinha(
        contrato=item,
        medido=_percent_or_dot(item.measured_pct),
        dias_aditados=_days_added_text(item.days_added),
        classe=_evaluation_text(evaluation),
        classe_tom=(
            _EVALUATION_CLASS_PILLS.get(evaluation.score_class, "neutral")
            if evaluation is not None
            else "neutral"
        ),
    )


def _evaluation_text(evaluation: service.EvaluationView | None) -> str:
    if evaluation is None or not evaluation.score_class:
        return ""
    if evaluation.score is None:
        return evaluation.score_class
    return f"{evaluation.score_class} ({evaluation.score})"


def _days_added_text(days: int) -> str:
    if days <= 0:
        return ""
    return f"+{days} dia" if days == 1 else f"+{days} dias"


def _claims_subtitle(view: service.ContractsOverview) -> str:
    indicators = view.indicators
    return (
        f"Taxa de reconhecimento {_percent_or_dot(indicators.recognition_rate)}"
        f" · tempo médio de resolução {_days_or_dot(indicators.average_resolution_days)}"
        f" · back-charges em aberto {_money(indicators.client_exposure_cents)}"
    )


def _extensions_subtitle(view: service.ContractsOverview) -> str:
    indicators = view.indicators
    return (
        f"{indicators.requested_days} dias solicitados x {indicators.granted_days} concedidos"
        f" · {_percent_or_dot(indicators.extension_percent)} da duração original dos contratos"
    )


def _milestones_subtitle(view: service.ContractsOverview) -> str:
    indicators = view.indicators
    return (
        f"Aprovado não faturado {_money(indicators.approved_not_invoiced_cents)}"
        f" · pago x previsto até hoje {_percent_or_dot(indicators.paid_forecast_percent)}"
        " · marco só é aprovado com evidência"
    )


def _open_claims_text(count: int) -> str:
    return "1 claim aberto" if count == 1 else f"{count} claims abertos"


def _integer(value: int) -> str:
    return format_value(ValueKind.INTEGER, value)


def _percent1(value: Decimal) -> str:
    return format_value(ValueKind.PERCENT, value, digits=1)


def _decimal1(value: Decimal) -> str:
    return format_value(ValueKind.DECIMAL, value, digits=1)


def _percent_or_dot(value: Decimal | None) -> str:
    return "·" if value is None else _percent1(value)


def _days_or_dot(value: int | None) -> str:
    if value is None:
        return "·"
    return "1 dia" if value == 1 else f"{value} dias"


def _period_text(period: date) -> str:
    return period.strftime("%m/%Y")


# ── Contingência e reservas (ISSUE-041) ──────────────────────────────────


@dataclass(frozen=True)
class ContingenciaKpi:
    """Um indicador da faixa do topo, com a referência e o rodapé; o pedido leva o link das SMs."""

    rotulo: str
    valor: str
    referencia: str
    rodape: str
    tom: str
    icone: str
    href: str = ""


@dataclass(frozen=True)
class ContingenciaComposicaoLinha:
    """Uma linha da composição do orçamento: o rótulo, o valor e o sinal da parcela."""

    rotulo: str
    valor: str
    sinal: str = ""
    total: bool = False


@dataclass(frozen=True)
class ContingenciaMovimentoLinha:
    """Uma linha do extrato: o movimento do serviço e os textos que a tabela imprime."""

    movimento: service.ReserveMovementView
    data: str
    reserva: str
    tipo_tom: str
    valor: str
    saldo: str


@dataclass(frozen=True)
class ContingenciaProjetoLinha:
    """Uma linha da tabela da carteira: o projeto e os números formatados de suas reservas."""

    projeto_id: int
    codigo: str
    nome: str
    constituida: str
    consumida: str
    saldo: str
    consumo: str
    limite: str
    em_analise: str
    gerencial: str
    consumo_alto: bool


@dataclass(frozen=True)
class ContingenciaAmeacaLinha:
    """Uma linha de Ameaças ativas e cobertura: o risco, o VME e as SMs que o citam."""

    ameaca: service.ContingencyThreatView
    projeto: str
    risco: str
    severidade: str
    situacao: str
    vme: str
    sms: tuple[tuple[str, str], ...]


CONTINGENCY_ROUTE = "financeiro/contingencia"
CONTINGENCY_EXCEL_ROUTE = f"{CONTINGENCY_ROUTE}/excel"
CONTINGENCY_PRINTABLE_ROUTE = f"{CONTINGENCY_ROUTE}/imprimivel"

CONTINGENCY_TEMPLATE = "financeiro/contingencia.html"
CONTINGENCY_TARGET = "contingencia-conteudo"

CONTINGENCY_CHANGES_SCREEN = "/governanca/mudancas"

CONTINGENCY_KPI_ICONS = ("shield", "warning", "file", "target", "lock")
CONTINGENCY_MOVEMENT_PILLS = {
    calculations.MOVEMENT_CONSTITUTION: "fix",
    calculations.MOVEMENT_CONSUMPTION: "warn",
    calculations.MOVEMENT_RELEASE: "ok",
    calculations.MOVEMENT_IN_ANALYSIS: "neutral",
}
CONTINGENCY_SUBTITLE = (
    "Saldo real e saldo previsto pelo avanço físico planejado "
    "(consumo proporcional à linha de base)"
)
CONTINGENCY_THREATS_SCREEN = "/riscos/painel"
CONTINGENCY_NO_VALUE = "·"


@bp.route(route=CONTINGENCY_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contingencia_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A tela de Contingência do escopo: indicadores, alertas, gráfico, composição e extrato."""
    view = _contingencia_view(session, context)
    return AlpineAjaxResponse(
        template_name=CONTINGENCY_TEMPLATE,
        context=_contingencia_context(view, context=context),
        request=req,
    )


@bp.route(route=CONTINGENCY_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def contingencia_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da Contingência: os indicadores, as tabelas e os números do gráfico."""
    del req
    return excel_response(_contingencia_document_of(session, context))


@bp.route(route=CONTINGENCY_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def contingencia_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da Contingência: o mesmo documento do Excel, com o gráfico."""
    return printable_response(_contingencia_document_of(session, context), req)


def _contingencia_view(session: Session, context: RequestContext) -> service.ContingencyOverview:
    """A leitura do escopo do pedido; a única da rota que vê o relógio."""
    return service.contingency_overview(
        session, user=context.user, scope=context.scope, reference_date=calendario.today()
    )


def _contingencia_document_of(session: Session, context: RequestContext) -> Document:
    view = _contingencia_view(session, context)
    return export.contingencia_document(
        view,
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _contingencia_context(
    view: service.ContingencyOverview, *, context: RequestContext
) -> dict[str, object]:
    """O que o fragmento imprime: a visão, os indicadores, o gráfico, as tabelas e o estado."""
    return {
        "visao": view,
        "carteira": view.is_portfolio,
        "situacao": "vazio-origem" if view.is_empty else "conteudo",
        "kpis": _contingencia_kpis(view, projeto=context.scope.parameter),
        "grafico": export.contingencia_chart(view),
        "composicao": _contingencia_composicao(view),
        "movimentos": _contingencia_movimentos(view),
        "projetos": _contingencia_projetos(view),
        "ameacas": _contingencia_ameacas(view),
        "totais": _contingencia_total(view),
        "subtitulo": _contingencia_subtitulo(view),
        "subtitulo_ameacas": _contingencia_subtitulo_ameacas(view),
        "pauta_url": _contingencia_pauta_url(view, context.scope.parameter),
        "alvo_conteudo": CONTINGENCY_TARGET,
    }


def _contingencia_kpis(
    view: service.ContingencyOverview, *, projeto: str
) -> tuple[ContingenciaKpi, ...]:
    """Os cinco indicadores do serviço como a faixa os imprime; dois levam link."""
    changes_url = f"{CONTINGENCY_CHANGES_SCREEN}?projeto={projeto}"
    pauta_url = _contingencia_pauta_url(view, projeto)
    return tuple(
        ContingenciaKpi(
            rotulo=kpi.label,
            valor=(
                CONTINGENCY_NO_VALUE
                if kpi.value is None
                else format_value(kpi.kind, kpi.value, kpi.digits)
            ),
            referencia=kpi.reference,
            rodape=kpi.status,
            tom=kpi.tone.value if kpi.tone is not None else "neutro",
            icone=icone,
            href=(
                changes_url
                if kpi.label == export.CONTINGENCY_KPI_ANALYSIS
                else pauta_url
                if kpi.label == export.CONTINGENCY_KPI_COVERAGE
                else ""
            ),
        )
        for kpi, icone in zip(export.contingencia_kpis(view), CONTINGENCY_KPI_ICONS, strict=True)
    )


def _contingencia_pauta_url(view: service.ContingencyOverview, projeto: str) -> str:
    """O link do indicador da cobertura para o painel de riscos do escopo (protótipo)."""
    if view.is_portfolio:
        return CONTINGENCY_THREATS_SCREEN
    return f"{CONTINGENCY_THREATS_SCREEN}?projeto={projeto}"


def _contingencia_subtitulo(view: service.ContingencyOverview) -> str:
    if view.is_portfolio:
        return f"{CONTINGENCY_SUBTITLE} · carteira: soma dos projetos"
    return CONTINGENCY_SUBTITLE


def _contingencia_composicao(
    view: service.ContingencyOverview,
) -> tuple[ContingenciaComposicaoLinha, ...]:
    contingency = view.contingency.balance_cents if view.contingency else 0
    management = view.management.balance_cents if view.management else 0
    return (
        ContingenciaComposicaoLinha(
            "Orçado atual da EAC (linha de base de medição)", _money(view.eac_current_cents)
        ),
        ContingenciaComposicaoLinha(
            "Saldo da reserva de contingência", _money(contingency), sinal="+"
        ),
        ContingenciaComposicaoLinha(
            "Linha de base de custo", _money(view.cost_baseline_cents), total=True
        ),
        ContingenciaComposicaoLinha("Saldo da reserva gerencial", _money(management), sinal="+"),
        ContingenciaComposicaoLinha(
            "Orçamento do projeto", _money(view.project_budget_cents), total=True
        ),
    )


def _contingencia_movimentos(
    view: service.ContingencyOverview,
) -> tuple[ContingenciaMovimentoLinha, ...]:
    return tuple(
        ContingenciaMovimentoLinha(
            movimento=linha,
            data=format_value(ValueKind.DATE, linha.on),
            reserva=linha.reserve_kind,
            tipo_tom=CONTINGENCY_MOVEMENT_PILLS.get(linha.kind, "neutral"),
            valor=_signed_money(linha.value_cents),
            saldo=(
                CONTINGENCY_NO_VALUE if linha.balance_cents is None else _money(linha.balance_cents)
            ),
        )
        for linha in view.movements
    )


def _contingencia_projetos(
    view: service.ContingencyOverview,
) -> tuple[ContingenciaProjetoLinha, ...]:
    linhas: list[ContingenciaProjetoLinha] = []
    for item in view.projects:
        codigo, _, nome = item.project_label.partition(" · ")
        linhas.append(
            _contingencia_linha(projeto_id=item.project_id, codigo=codigo, nome=nome, reservas=item)
        )
    return tuple(linhas)


def _contingencia_ameacas(
    view: service.ContingencyOverview,
) -> tuple[ContingenciaAmeacaLinha, ...]:
    """As ameaças ativas e a cobertura, como a tabela da tela as imprime."""
    return tuple(
        ContingenciaAmeacaLinha(
            ameaca=threat,
            projeto=threat.project_code,
            risco=threat.code,
            severidade=threat.severity,
            situacao=threat.situation,
            vme=_money(threat.vme_cents),
            sms=tuple((code, f"/governanca/mudanca?codigo={code}") for code in threat.change_codes),
        )
        for threat in view.threats
    )


def _contingencia_subtitulo_ameacas(view: service.ContingencyOverview) -> str:
    """A linha do protótipo: a exposição contra o saldo e as SMs que citam o risco."""
    balance = view.contingency.balance_cents if view.contingency is not None else 0
    return (
        f"Exposição (VME) de {_money(view.exposure_cents)} contra saldo de {_money(balance)} "
        "· SMs que citam o risco na análise de impacto"
    )


def _contingencia_total(view: service.ContingencyOverview) -> ContingenciaProjetoLinha:
    return _contingencia_linha(projeto_id=0, codigo="Total", nome="", reservas=view)


def _contingencia_linha(
    *,
    projeto_id: int,
    codigo: str,
    nome: str,
    reservas: service.ContingencyProjectRow | service.ContingencyOverview,
) -> ContingenciaProjetoLinha:
    contingency = reservas.contingency
    management = reservas.management
    limit = reservas.consumption_limit_pct
    pct = contingency.consumption_pct if contingency is not None else None
    return ContingenciaProjetoLinha(
        projeto_id=projeto_id,
        codigo=codigo,
        nome=nome,
        constituida=_money_or_dot(contingency.total_cents if contingency else None),
        consumida=_money_or_dot(contingency.consumed_cents if contingency else None),
        saldo=_money_or_dot(contingency.balance_cents if contingency else None),
        consumo=_percent_or_dot(pct),
        limite=_percent_or_dot(limit),
        em_analise=_money_or_dot(contingency.in_analysis_cents if contingency else None),
        gerencial=_money_or_dot(management.balance_cents if management else None),
        consumo_alto=pct is not None and limit is not None and pct > limit,
    )


def _money_or_dot(cents: int | None) -> str:
    return CONTINGENCY_NO_VALUE if cents is None else _money(cents)


# ── Curva S financeira e KPIs de custo (ISSUE-042) ───────────────────────


CURVA_FINANCEIRA_ROUTE = "financeiro/curva-s"
CURVA_FINANCEIRA_EXCEL_ROUTE = f"{CURVA_FINANCEIRA_ROUTE}/excel"
CURVA_FINANCEIRA_PRINTABLE_ROUTE = f"{CURVA_FINANCEIRA_ROUTE}/imprimivel"
CUSTOS_KPIS_ROUTE = "financeiro/kpis"
CUSTOS_KPIS_EXCEL_ROUTE = f"{CUSTOS_KPIS_ROUTE}/excel"
CUSTOS_KPIS_PRINTABLE_ROUTE = f"{CUSTOS_KPIS_ROUTE}/imprimivel"

CURVA_FINANCEIRA_TEMPLATE = "financeiro/curva_financeira.html"
CUSTOS_KPIS_TEMPLATE = "financeiro/custos_kpis.html"

CURVA_FINANCEIRA_TARGET = "curva-s-conteudo"
CUSTOS_KPIS_TARGET = "kpis-conteudo"

CURVA_FINANCEIRA_KPI_ICONS = ("chartLine", "money", "file", "pin")
CUSTOS_KPI_ICONS = ("chartLine", "clock", "money", "pin", "shield", "file")

CURVA_FINANCEIRA_PORTFOLIO_SUFFIX = (
    " · carteira: soma dos valores em R$ dos projetos (sem ponderação)"
)
CUSTOS_KPIS_PROJECT_SUFFIX = " · EV = avanço físico real x orçamento (BAC)"
CUSTOS_KPIS_PORTFOLIO_SUFFIX = (
    " · carteira: soma do EV, PV e AC dos projetos (EV de cada projeto = avanço físico real x BAC)"
)

_PILL_POR_TOM = {"ok": "ok", "erro": "erro", "warn": "warn", "info": "fix", "neutro": "neutral"}


def _pill_tom(tom: str) -> str:
    """O nome da classe da pastilha para o tom do Design System (``fix`` e ``neutral`` diferem)."""
    return _PILL_POR_TOM.get(tom, "neutral")


@dataclass(frozen=True)
class CurvaFinanceiraKpi:
    """Um indicador da Curva S financeira, já escrito como a pessoa o lê."""

    rotulo: str
    valor: str
    referencia: str
    rodape: str
    tom: str
    icone: str


@dataclass(frozen=True)
class CurvaFinanceiraLinha:
    """Uma linha da tabela período a período da Curva S financeira, com o corte marcado."""

    mes: str
    planejado_mes: str
    planejado: str
    comprometido: str
    realizado_mes: str
    realizado: str
    projecao: str
    desvio: str
    tom: str
    corte: bool


@dataclass(frozen=True)
class CustosKpi:
    """Um indicador dos KPIs de custo, já escrito como a pessoa o lê."""

    rotulo: str
    valor: str
    referencia: str
    rodape: str
    tom: str
    icone: str


@dataclass(frozen=True)
class CustosValorLinha:
    """Uma linha da tabela de valor agregado, com o corte marcado."""

    mes: str
    pv: str
    ev: str
    ac: str
    cv: str
    tom_cv: str
    sv: str
    tom_sv: str
    cpi: str
    tom_cpi: str
    spi: str
    tom_spi: str
    eac: str
    tcpi: str
    corte: bool


@dataclass(frozen=True)
class CustosResumoLinha:
    """Uma linha do resumo do valor agregado, com a leitura do protótipo."""

    sigla: str
    nome: str
    valor: str
    indice: str
    tom: str
    leitura: str


@dataclass(frozen=True)
class CustosProjetoLinha:
    """Uma linha do desempenho de custo por projeto, na carteira."""

    projeto_id: int
    codigo: str
    nome: str
    bac: str
    ev: str
    ac: str
    cpi: str
    tom_cpi: str
    spi: str
    tom_spi: str
    projecao: str
    vac: str
    tom_vac: str
    contingencia: str


@bp.route(route=CURVA_FINANCEIRA_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def curva_financeira_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A Curva S financeira do escopo: indicadores, gráfico e tabela período a período."""
    return AlpineAjaxResponse(
        template_name=CURVA_FINANCEIRA_TEMPLATE,
        context=_curva_financeira_context(_curva_financeira_view(session, context)),
        request=req,
    )


@bp.route(route=CURVA_FINANCEIRA_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def curva_financeira_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da Curva S financeira: os indicadores, o gráfico e a tabela, no escopo do pedido."""
    del req
    return excel_response(_curva_financeira_document_of(session, context))


@bp.route(route=CURVA_FINANCEIRA_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def curva_financeira_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível da Curva S financeira: o mesmo documento que o Excel carrega."""
    return printable_response(_curva_financeira_document_of(session, context), req)


@bp.route(route=CUSTOS_KPIS_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def custos_kpis_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Os KPIs de custo do escopo: indicadores, gráfico de CPI e SPI e a tabela de valor agregado."""
    return AlpineAjaxResponse(
        template_name=CUSTOS_KPIS_TEMPLATE,
        context=_custos_kpis_context(_custos_kpis_view(session, context)),
        request=req,
    )


@bp.route(route=CUSTOS_KPIS_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def custos_kpis_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel dos KPIs de custo: os indicadores, o gráfico e as tabelas, no escopo do pedido."""
    del req
    return excel_response(_custos_kpis_document_of(session, context))


@bp.route(route=CUSTOS_KPIS_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def custos_kpis_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível dos KPIs de custo: o mesmo documento que o Excel carrega."""
    return printable_response(_custos_kpis_document_of(session, context), req)


def _curva_financeira_view(
    session: Session, context: RequestContext
) -> service.FinancialCurveOverview:
    """A Curva S financeira do escopo do pedido; a única leitura da rota que vê o relógio."""
    return service.financial_curve_overview(
        session, scope=context.scope, reference_date=calendario.today()
    )


def _curva_financeira_document_of(session: Session, context: RequestContext) -> Document:
    return export.curva_financeira_document(
        _curva_financeira_view(session, context),
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _custos_kpis_view(session: Session, context: RequestContext) -> service.CostKpisOverview:
    """Os KPIs de custo do escopo do pedido; a única leitura da rota que vê o relógio."""
    return service.cost_kpis_overview(
        session, scope=context.scope, reference_date=calendario.today()
    )


def _custos_kpis_document_of(session: Session, context: RequestContext) -> Document:
    return export.custos_kpis_document(
        _custos_kpis_view(session, context),
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
    )


def _curva_financeira_context(view: service.FinancialCurveOverview) -> dict[str, object]:
    """O que o fragmento imprime: a visão, os indicadores, o gráfico e a tabela."""
    return {
        "visao": view,
        "carteira": view.is_portfolio,
        "situacao": "vazio-origem" if view.is_empty else "conteudo",
        "kpis": _curva_financeira_kpis(view),
        "grafico": export.curva_financeira_chart(view),
        "linhas": _curva_financeira_linhas(view),
        "subtitulo": _curva_financeira_subtitulo(view),
        "alvo_conteudo": CURVA_FINANCEIRA_TARGET,
    }


def _custos_kpis_context(view: service.CostKpisOverview) -> dict[str, object]:
    """O que o fragmento dos KPIs imprime: a visão, os cartões, o gráfico e as tabelas."""
    return {
        "visao": view,
        "carteira": view.is_portfolio,
        "situacao": "vazio-origem" if view.is_empty else "conteudo",
        "kpis": _custos_kpis(view),
        "grafico": export.custos_kpis_chart(view),
        "grafico_valor": export.custos_valor_chart(view),
        "linhas": _custos_valor_linhas(view),
        "resumo": _custos_resumo_linhas(view),
        "projetos": _custos_projeto_linhas(view),
        "subtitulo": _custos_kpis_subtitulo(view),
        "alvo_conteudo": CUSTOS_KPIS_TARGET,
    }


def _curva_financeira_kpis(
    view: service.FinancialCurveOverview,
) -> tuple[CurvaFinanceiraKpi, ...]:
    """Os quatro indicadores do serviço como a faixa os imprime."""
    kpis = export.curva_financeira_kpis(view)
    if not kpis:
        return ()
    return tuple(
        CurvaFinanceiraKpi(
            rotulo=kpi.label,
            valor=_kpi_value_text(kpi),
            referencia=kpi.reference,
            rodape=kpi.status,
            tom=kpi.tone.value if kpi.tone is not None else "neutro",
            icone=icone,
        )
        for kpi, icone in zip(kpis, CURVA_FINANCEIRA_KPI_ICONS, strict=True)
    )


def _custos_kpis(view: service.CostKpisOverview) -> tuple[CustosKpi, ...]:
    """Os seis indicadores do serviço como a faixa os imprime."""
    kpis = export.custos_kpis(view)
    if not kpis:
        return ()
    return tuple(
        CustosKpi(
            rotulo=kpi.label,
            valor=_kpi_value_text(kpi),
            referencia=kpi.reference,
            rodape=kpi.status,
            tom=kpi.tone.value if kpi.tone is not None else "neutro",
            icone=icone,
        )
        for kpi, icone in zip(kpis, CUSTOS_KPI_ICONS, strict=True)
    )


def _kpi_value_text(kpi: Kpi) -> str:
    """O valor do indicador como a tela o escreve; sem valor, o ponto médio."""
    return (
        CONTINGENCY_NO_VALUE if kpi.value is None else format_value(kpi.kind, kpi.value, kpi.digits)
    )


def _curva_financeira_subtitulo(view: service.FinancialCurveOverview) -> str:
    cut = _curva_financeira_cut_label(view)
    text = f"Corte em {cut} · acumulado por mês" if cut else "Sem corte na referência"
    if view.is_portfolio:
        text += CURVA_FINANCEIRA_PORTFOLIO_SUFFIX
    return text


def _curva_financeira_cut_label(view: service.FinancialCurveOverview) -> str:
    if view.series.cut_index < 0:
        return ""
    return export.curva_financeira_month_label(view.series.months[view.series.cut_index])


def _curva_financeira_linhas(
    view: service.FinancialCurveOverview,
) -> tuple[CurvaFinanceiraLinha, ...]:
    """A tabela período a período: acumulados e o movimento do mês, com o corte marcado."""
    linhas: list[CurvaFinanceiraLinha] = []
    for index, point in enumerate(view.points):
        previous = view.points[index - 1] if index > 0 else None
        planned_month = point.planned_cents - (previous.planned_cents if previous else 0)
        actual_month = (
            None
            if point.actual_cents is None
            else point.actual_cents
            - (previous.actual_cents if previous and previous.actual_cents is not None else 0)
        )
        deviation = None if point.actual_cents is None else point.actual_cents - point.planned_cents
        linhas.append(
            CurvaFinanceiraLinha(
                mes=export.curva_financeira_month_label(point.month),
                planejado_mes=_money(planned_month),
                planejado=_money(point.planned_cents),
                comprometido=_money_or_dot(point.committed_cents),
                realizado_mes=_money_or_dot(actual_month),
                realizado=_money_or_dot(point.actual_cents),
                projecao=_money_or_dot(point.trend_cents),
                desvio="" if deviation is None else _signed_money(deviation),
                tom=(
                    "neutral"
                    if deviation is None
                    else "erro"
                    if deviation > 0
                    else "ok"
                    if deviation < 0
                    else "neutral"
                ),
                corte=point.is_cut,
            )
        )
    return tuple(linhas)


def _custos_kpis_subtitulo(view: service.CostKpisOverview) -> str:
    cut = export.curva_financeira_month_label(view.cut_month)
    text = f"Corte em {cut}" if cut else "Sem corte na referência"
    text += CUSTOS_KPIS_PORTFOLIO_SUFFIX if view.is_portfolio else CUSTOS_KPIS_PROJECT_SUFFIX
    return text


def _custos_valor_linhas(view: service.CostKpisOverview) -> tuple[CustosValorLinha, ...]:
    """A tabela de valor agregado: os valores de cada mês e os índices acumulados até ele."""
    return tuple(
        CustosValorLinha(
            mes=export.curva_financeira_month_label(row.month),
            pv=_money(row.pv_cents),
            ev=_money(row.ev_cents),
            ac=_money(row.ac_cents),
            cv=_signed_money(row.cv_cents),
            tom_cv="erro" if row.cv_cents < 0 else "ok",
            sv=_signed_money(row.sv_cents),
            tom_sv="erro" if row.sv_cents < 0 else "ok",
            cpi=_decimal(row.cpi),
            tom_cpi=_pill_tom(export.financial_index_tone(row.cpi).value),
            spi=_decimal(row.spi),
            tom_spi=_pill_tom(export.financial_index_tone(row.spi).value),
            eac=_money_or_dot(row.eac_by_cpi_cents),
            tcpi=_decimal(row.tcpi),
            corte=row.month == view.cut_month,
        )
        for row in view.history
    )


def _custos_projeto_linhas(view: service.CostKpisOverview) -> tuple[CustosProjetoLinha, ...]:
    """O desempenho de custo por projeto, no Portfólio."""
    linhas: list[CustosProjetoLinha] = []
    for item in view.projects:
        codigo, _, nome = item.project_label.partition(" · ")
        linhas.append(
            CustosProjetoLinha(
                projeto_id=item.project_id,
                codigo=codigo,
                nome=nome,
                bac=_money(item.bac_cents),
                ev=_money(item.ev_cents),
                ac=_money(item.ac_cents),
                cpi=_decimal(item.cpi),
                tom_cpi=_pill_tom(export.financial_index_tone(item.cpi).value),
                spi=_decimal(item.spi),
                tom_spi=_pill_tom(export.financial_index_tone(item.spi).value),
                projecao=_money_or_dot(item.projection_cents),
                vac=(
                    CONTINGENCY_NO_VALUE
                    if item.vac_cents is None
                    else _signed_money(item.vac_cents)
                ),
                tom_vac=(
                    "neutral" if item.vac_cents is None else "erro" if item.vac_cents < 0 else "ok"
                ),
                contingencia=_percent_or_dot(item.contingency_pct),
            )
        )
    return tuple(linhas)


def _custos_resumo_linhas(view: service.CostKpisOverview) -> tuple[CustosResumoLinha, ...]:
    """O resumo do valor agregado na data de corte, com a leitura do protótipo."""
    linhas: list[CustosResumoLinha] = []
    for item in export.custos_kpis_resumo(view):
        value = _resumo_value_text(item)
        index = item.kind is ValueKind.DECIMAL
        linhas.append(
            CustosResumoLinha(
                sigla=item.sigla,
                nome=item.nome,
                valor="" if index else value,
                indice=value if index else "",
                tom="" if item.tone is None else _pill_tom(item.tone.value),
                leitura=item.leitura,
            )
        )
    return tuple(linhas)


def _resumo_value_text(item: export.CustosResumoItem) -> str:
    return CONTINGENCY_NO_VALUE if item.value is None else format_value(item.kind, item.value, 2)


# ── Cronograma de desembolso (ISSUE-043) ─────────────────────────────────


DESEMBOLSO_ROUTE = "financeiro/desembolso"
DESEMBOLSO_EXCEL_ROUTE = f"{DESEMBOLSO_ROUTE}/excel"
DESEMBOLSO_PRINTABLE_ROUTE = f"{DESEMBOLSO_ROUTE}/imprimivel"
DESEMBOLSO_SEND_ROUTE = f"{DESEMBOLSO_ROUTE}/enviar"

DESEMBOLSO_TEMPLATE = "financeiro/desembolso.html"
DESEMBOLSO_SEND_TEMPLATE = "financeiro/desembolso_envio.html"

DESEMBOLSO_TARGET = "desembolso-conteudo"
DESEMBOLSO_MODAL_TARGET = "desembolso-modal"

DESEMBOLSO_KPI_ICONS = ("money", "calendar", "clock", "chartLine")

DESEMBOLSO_SUBTITLE = "previsto na linha de base, realizado até o corte e projetado depois"
DESEMBOLSO_PORTFOLIO_SUFFIX = " · soma dos projetos da carteira"


@dataclass(frozen=True)
class DesembolsoKpi:
    """Um indicador do cronograma, já escrito como a pessoa o lê."""

    rotulo: str
    valor: str
    referencia: str
    rodape: str
    tom: str
    icone: str


@dataclass(frozen=True)
class DesembolsoLinha:
    """Uma linha da tabela saldo a pagar por mês, com os valores já formatados."""

    codigo: str
    descricao: str
    nivel: int
    projeto: str
    saldo: str
    meses: tuple[str, ...]


@dataclass(frozen=True)
class DesembolsoTotais:
    """A linha de totais da tabela: o saldo do escopo e a soma dos meses."""

    saldo: str
    meses: tuple[str, ...]


@dataclass(frozen=True)
class DesembolsoEnvioForm:
    """O formulário do envio, com o destinatário e a mensagem que o protótipo sugere."""

    para: str
    mensagem: str


@dataclass(frozen=True)
class DesembolsoEnvioResultado:
    """O que o modal mostra depois do envio: o aviso da porta e a situação."""

    aviso: str
    simulado: bool
    erro: bool


def _desembolso_envio_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A recusa dentro do modal: a mensagem no corpo onde a pessoa está olhando."""
    mensagens = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": mensagens},
        request=req,
        target_id=DESEMBOLSO_MODAL_TARGET,
        status_code=_desembolso_error_status(error),
        toast=mensagens[0] if mensagens else "Não foi possível concluir.",
        toast_tipo="erro",
    )


def _desembolso_error_status(error: DomainError) -> int:
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


@bp.route(route=DESEMBOLSO_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def desembolso_content(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O cronograma do escopo: os indicadores, o gráfico mensal e a tabela item x mês."""
    nivel = validation.parse_desembolso_level(req.params.get("nivel"))
    return AlpineAjaxResponse(
        template_name=DESEMBOLSO_TEMPLATE,
        context=_desembolso_context(_desembolso_view(session, context), nivel=nivel),
        request=req,
    )


@bp.route(route=DESEMBOLSO_EXCEL_ROUTE, methods=["GET"])
@file_route(access=READ_ACCESS)
def desembolso_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel do cronograma: os indicadores, o gráfico e a tabela, no escopo do pedido."""
    nivel = validation.parse_desembolso_level(req.params.get("nivel"))
    return excel_response(_desembolso_document_of(session, context, nivel=nivel))


@bp.route(route=DESEMBOLSO_PRINTABLE_ROUTE, methods=["GET"])
@fragment_route(access=READ_ACCESS)
def desembolso_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do cronograma: o mesmo documento que o Excel carrega."""
    nivel = validation.parse_desembolso_level(req.params.get("nivel"))
    return printable_response(_desembolso_document_of(session, context, nivel=nivel), req)


@bp.route(route=DESEMBOLSO_SEND_ROUTE, methods=["GET"])
@fragment_route(access=WRITE_ACCESS, on_error=_desembolso_envio_error)
def desembolso_envio_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O modal do envio: Para e Mensagem preenchidos do cronograma do escopo."""
    view = _desembolso_view(session, context)
    service.treasury_sendable_project(context.scope, view)
    return AlpineAjaxResponse(
        template_name=DESEMBOLSO_SEND_TEMPLATE,
        context={"formulario": _desembolso_envio_formulario(view), "resultado": None},
        request=req,
        target_id=DESEMBOLSO_MODAL_TARGET,
    )


@bp.route(route=DESEMBOLSO_SEND_ROUTE, methods=["POST"])
@fragment_route(access=WRITE_ACCESS, on_error=_desembolso_envio_error)
def desembolso_envio_send(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Envia o cronograma à tesouraria e responde o que foi registrado, com o toast."""
    formulario = validation.parse_treasury_form(req.form)
    resultado = service.send_to_treasury(
        session,
        user=context.user,
        scope=context.scope,
        reference_date=calendario.today(),
        recipient=formulario.recipient,
        message=formulario.message or None,
    )
    return AlpineAjaxResponse(
        template_name=DESEMBOLSO_SEND_TEMPLATE,
        context={"formulario": None, "resultado": _desembolso_envio_resultado(resultado)},
        request=req,
        target_id=DESEMBOLSO_MODAL_TARGET,
        toast=_desembolso_envio_toast(formulario.recipient, resultado),
        toast_tipo=resultado.toast_kind,
    )


def _desembolso_view(session: Session, context: RequestContext) -> service.DisbursementOverview:
    """O cronograma do escopo do pedido; a única leitura da rota que vê o relógio."""
    return service.disbursement_overview(
        session, scope=context.scope, reference_date=calendario.today()
    )


def _desembolso_document_of(session: Session, context: RequestContext, *, nivel: int) -> Document:
    return export.desembolso_document(
        _desembolso_view(session, context),
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
        level=nivel,
    )


def _desembolso_context(view: service.DisbursementOverview, *, nivel: int) -> dict[str, object]:
    """O que o fragmento imprime: a visão, os indicadores, o gráfico e a tabela do nível."""
    return {
        "visao": view,
        "carteira": view.is_portfolio,
        "situacao": "vazio-origem" if view.is_empty else "conteudo",
        "kpis": _desembolso_kpis(view),
        "grafico": export.desembolso_chart(view),
        "meses": _desembolso_meses(view),
        "linhas": _desembolso_linhas(view, nivel=nivel),
        "totais": _desembolso_totais(view),
        "subtitulo": _desembolso_subtitulo(view),
        "alvo_conteudo": DESEMBOLSO_TARGET,
    }


def _desembolso_kpis(view: service.DisbursementOverview) -> tuple[DesembolsoKpi, ...]:
    """Os quatro indicadores do serviço como a faixa os imprime."""
    kpis = export.desembolso_kpis(view)
    if not kpis:
        return ()
    return tuple(
        DesembolsoKpi(
            rotulo=kpi.label,
            valor=_kpi_value_text(kpi),
            referencia=kpi.reference,
            rodape=kpi.status,
            tom=kpi.tone.value if kpi.tone is not None else "neutro",
            icone=icone,
        )
        for kpi, icone in zip(kpis, DESEMBOLSO_KPI_ICONS, strict=True)
    )


def _desembolso_meses(view: service.DisbursementOverview) -> tuple[str, ...]:
    return tuple(export.curva_financeira_month_label(month) for month in view.future_months)


def _desembolso_linhas(
    view: service.DisbursementOverview, *, nivel: int
) -> tuple[DesembolsoLinha, ...]:
    """As linhas da tabela até o nível pedido, com os meses já escritos."""
    return tuple(
        DesembolsoLinha(
            codigo=item.code,
            descricao=export.desembolso_row_description(item),
            nivel=item.level,
            projeto=item.project_label,
            saldo=_money(item.balance_cents),
            meses=tuple(_desembolso_mes_value(value) for value in item.amounts),
        )
        for item in export.desembolso_visible_items(view, level=nivel)
    )


def _desembolso_mes_value(cents: int) -> str:
    """O valor de um mês; o zero fica em branco, e o fragmento desenha o ponto médio."""
    return "" if cents == 0 else _money(cents)


def _desembolso_totais(view: service.DisbursementOverview) -> DesembolsoTotais:
    return DesembolsoTotais(
        saldo=_money(view.balance_cents),
        meses=tuple(_money(value) for value in view.totals),
    )


def _desembolso_subtitulo(view: service.DisbursementOverview) -> str:
    cut = export.curva_financeira_month_label(view.cut_month)
    text = f"Corte em {cut} · {DESEMBOLSO_SUBTITLE}" if cut else DESEMBOLSO_SUBTITLE
    return text + (DESEMBOLSO_PORTFOLIO_SUFFIX if view.is_portfolio else "")


def _desembolso_envio_formulario(view: service.DisbursementOverview) -> DesembolsoEnvioForm:
    return DesembolsoEnvioForm(
        para=service.TREASURY_EMAIL,
        mensagem=service.treasury_default_message(view),
    )


def _desembolso_envio_resultado(
    outcome: notification.NotificationOutcome,
) -> DesembolsoEnvioResultado:
    return DesembolsoEnvioResultado(
        aviso=outcome.notice,
        simulado=outcome.situation == notification.SIMULATED,
        erro=outcome.situation == notification.FAILED,
    )


def _desembolso_envio_toast(recipient: str, outcome: notification.NotificationOutcome) -> str:
    """O toast do protótipo quando o envio é simulado; senão, o aviso da porta."""
    if outcome.situation == notification.SIMULATED:
        return f"Cronograma enviado para {recipient} (envio simulado)."
    return outcome.notice
