"""Input validation of the supplier register, of the purchase plan and of the process (ISSUE-057/058/059).

The shapes the facade receives (new supplier, qualification, filters, documents, packages,
process actions) and the checks of what a person types. The checks are pure and return one
message per field, in a dict that is empty when everything holds up; the facade turns it into one
``InvalidDataError`` (422), so the rule holds for the route and for any module that calls the
facade.

The package of the plan is always tied to a cost item (level 3) of the EAC, the plan dates grow
and the plan may not be born with negative slack; the emergency purchase demands its
justification and the LLI contracted before the investment gate demands the specific approval.
After the requisition the baseline is frozen: only scope, buyer, estimate and ROS change, with a
justification.

The process of purchase: the RFx demands the minimum of invitees of the parameter (or a single
supplier with justification), the technical and commercial weights sum 100 and a blocked
supplier is refused; below the minimum of proposals or of approvals the flow only goes on with a
justification; the technical equalization gives a score to every proposal and needs at least one
approval before the commercial one.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from src.core.export_document import ValueKind
from src.core.import_values import RawCell, convert
from src.core.money import format_brl
from src.modulos.suprimentos import calculations
from src.modulos.suprimentos.calculations import BLOCKED, QUALIFIED, RESTRICTED, SITUATIONS

KINDS: tuple[str, ...] = ("Fornecedor", "Contratada")

PACKAGE_TYPES: tuple[str, ...] = ("Equipamento", "Material", "Serviço", "EPC")
PACKAGE_MODALITIES: tuple[str, ...] = ("Preço global", "Preço unitário", "Administração", "EPC")
PACKAGE_PAGE_SIZE = 20

# The fields of the baseline: sent to a frozen package they are a refusal, whatever the value.
BASELINE_FIELDS: tuple[str, ...] = (
    "tipo",
    "modalidade",
    "disciplina",
    "eac",
    "requisicao",
    "rfx",
    "adjudicacao",
    "pedido",
    "lli",
    "antecipado",
    "gate",
    "emergencial",
    "justEmergencial",
)

# The three documents the prototype already opens on a new supplier; the form shows them with an
# empty validity and they enter in the cadastro with whatever date the person gives them.
DEFAULT_DOCUMENTS: tuple[str, ...] = (
    "Certidão negativa de débitos federais",
    "Certidão negativa de débitos trabalhistas",
    "Certificado de regularidade do FGTS",
)

MIN_NAME = 3
MAX_NAME = 80
MAX_CATEGORY = 60
MAX_CATEGORIES = 160
MAX_DOCUMENT_NAME = 200
MAX_OBSERVATION = 300
MAX_JUSTIFICATION = 300
MIN_JUSTIFICATION = 10
MAX_SEARCH = 120
MAX_ID_DIGITS = 18
PAGE_SIZE = 20
MAX_PAGE = 9999

NAME_REQUIRED = "Informe a razão social ou o nome fantasia."
NAME_TOO_SHORT = f"O nome precisa de pelo menos {MIN_NAME} caracteres."
NAME_TOO_LONG = f"O nome comporta no máximo {MAX_NAME} caracteres."
CHOOSE_KIND = "Escolha o tipo."
CHOOSE_SITUATION = "Preencha este campo."
CATEGORIES_REQUIRED = "Informe ao menos uma categoria."
CATEGORY_TOO_LONG = f"Cada categoria comporta no máximo {MAX_CATEGORY} caracteres."
CATEGORIES_TOO_LONG = f"O conjunto de categorias comporta no máximo {MAX_CATEGORIES} caracteres."
DOCUMENT_NAME_REQUIRED = "Informe o nome do documento."
DOCUMENT_NAME_TOO_LONG = f"O nome do documento comporta no máximo {MAX_DOCUMENT_NAME} caracteres."
OBSERVATION_TOO_LONG = f"A observação comporta no máximo {MAX_OBSERVATION} caracteres."
VALIDITY_REQUIRED = "Fornecedor qualificado precisa de validade da qualificação."
VALIDITY_IN_THE_PAST = "A validade não pode estar vencida."
JUSTIFICATION_REQUIRED = (
    f"Justifique a mudança de situação (mínimo de {MIN_JUSTIFICATION} caracteres)."
)
JUSTIFICATION_TOO_LONG = f"A justificativa comporta no máximo {MAX_JUSTIFICATION} caracteres."
REASON_REQUIRED = "Registre o motivo da restrição ou do bloqueio."

# ── Purchase plan (ISSUE-058) ────────────────────────────────────────────────────────────────

MIN_PACKAGE_SCOPE = 3
MAX_PACKAGE_SCOPE = 120
MAX_GATE_REFERENCE = 160
MIN_EMERGENCY_JUSTIFICATION = 20

SCOPE_REQUIRED = "Informe o escopo de fornecimento."
SCOPE_TOO_SHORT = f"O escopo precisa de pelo menos {MIN_PACKAGE_SCOPE} caracteres."
SCOPE_TOO_LONG = f"O escopo comporta no máximo {MAX_PACKAGE_SCOPE} caracteres."
CHOOSE_TYPE = "Escolha o tipo."
CHOOSE_MODALITY = "Escolha a modalidade contratual."
CHOOSE_DISCIPLINE = "Escolha a disciplina."
DISCIPLINE_UNKNOWN = "A disciplina informada não está no cadastro."
CHOOSE_BUYER = "Escolha o comprador."
BUYER_UNKNOWN = "O comprador informado não está no cadastro."
EAC_REQUIRED = "Todo pacote nasce vinculado a um item da EAC."
EAC_NOT_COST_ITEM = "O item {code} não é item de custo (nível 3) da EAC."
ESTIMATE_REQUIRED = "Informe uma estimativa maior que zero."
PLAN_DATE_REQUIRED = "Preencha este campo."
PLAN_DATES_ORDER = (
    "As datas do plano precisam ser crescentes: requisição, RFx, adjudicação e pedido."
)
ROS_REQUIRED = "Informe a data necessária na obra (ROS)."
SLACK_NEGATIVE = (
    "A data do pedido fica depois do ROS: o plano já nasceria com folga negativa. Revise as datas."
)
GATE_REQUIRED = (
    "LLI contratado antes do gate de investimento exige a aprovação específica (gate LLI)."
)
GATE_TOO_LONG = f"A referência do gate LLI comporta no máximo {MAX_GATE_REFERENCE} caracteres."
EMERGENCY_REQUIRED = (
    f"Justifique a compra emergencial (mínimo de {MIN_EMERGENCY_JUSTIFICATION} caracteres)."
)
EMERGENCY_TOO_LONG = (
    f"A justificativa da compra emergencial comporta no máximo {MAX_JUSTIFICATION} caracteres."
)
CHANGE_JUSTIFICATION_REQUIRED = (
    f"Justifique a alteração (mínimo de {MIN_JUSTIFICATION} caracteres)."
)
FROZEN_BASELINE = (
    "A linha de base está congelada desde a requisição: só escopo, comprador, estimativa e ROS "
    "mudam, com justificativa."
)
BASELINE_EDITABLE = "A linha de base deste pacote ainda está editável: use a edição do plano."
PACKAGE_NOT_FOUND = "Pacote não encontrado."


@dataclass(frozen=True)
class DocumentInput:
    """One document of the form: the row being edited (``id``), its name and its validity."""

    name: str
    id: int | None = None
    validity: date | None = None
    version: int | str | None = None


@dataclass(frozen=True)
class SupplierInput:
    """What the form of Novo fornecedor sends: the company and its first qualification."""

    name: str
    kind: str
    categories: tuple[str, ...]
    documents: tuple[DocumentInput, ...] = ()
    observation: str = ""


@dataclass(frozen=True)
class QualificationInput:
    """What the form of Atualizar qualificação sends."""

    situation: str
    categories: tuple[str, ...]
    documents: tuple[DocumentInput, ...] = ()
    validity: date | None = None
    observation: str = ""
    justification: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class SupplierFilters:
    """The filters of the list: what the query string of the screen says."""

    search: str = ""
    situation: str = ""
    category: str = ""
    page: int = 1


@dataclass(frozen=True)
class PackageInput:
    """What the form of Novo pacote (or the import) sends for the full plan of a package."""

    scope: str
    kind: str
    modality: str
    discipline_id: int | None
    buyer_id: int | None
    eac_code: str
    estimate_cents: int | None
    requisition: date | None
    rfx: date | None
    adjudication: date | None
    order: date | None
    ros: date | None
    lli: bool = False
    anticipated_fid: bool = False
    gate_reference: str = ""
    emergency: bool = False
    emergency_justification: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class PackageChangeInput:
    """What the frozen form sends: only the four fields that may change, with the justification."""

    scope: str
    buyer_id: int | None
    estimate_cents: int | None
    ros: date | None
    justification: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class PackageFilters:
    """The filters of the plan: search, type, LLI only and the page."""

    search: str = ""
    kind: str = ""
    lli_only: bool = False
    page: int = 1


# ── Purchase process (ISSUE-059) ─────────────────────────────────────────────────────────────

MIN_PROCESS_JUSTIFICATION = 20
MAX_PROCESS_OBSERVATION = 300
MAX_PROCESS_DOCUMENT = 40
MAX_PROCESS_OPINION = 400
MAX_PROPOSAL_DEVIATIONS = 160
MAX_OTHER_INVITEES = 200
MAX_POINTS = 100
MAX_DEADLINE_DAYS = 900

DATE_IN_THE_FUTURE = "A data não pode ser posterior à data de referência."
ACTION_NOT_IN_STAGE = "Ação não disponível na etapa {stage}."
INVITEES_MINIMUM = (
    "Convide ao menos {minimum} fornecedores (ou registre fornecedor único com justificativa)."
)
INVITEE_UNKNOWN = "O fornecedor informado não está no cadastro."
INVITEE_BLOCKED = "Fornecedor bloqueado não pode ser convidado: {names}."
SINGLE_JUSTIFICATION = "Fornecedor único exige justificativa (mínimo de 20 caracteres)."
DEADLINE_ORDER = "O prazo das propostas deve ser igual ou posterior à emissão da RFx."
WEIGHTS_TOTAL = "Os pesos técnico e comercial devem somar 100."
PROPOSAL_SUPPLIER_REQUIRED = "Informe o fornecedor da proposta."
PROPOSAL_DUPLICATE = "Este fornecedor já tem proposta registrada."
PROPOSAL_BLOCKED = "Fornecedor bloqueado: a proposta não pode ser aceita."
PROPOSAL_VALUE_REQUIRED = "Informe o valor da proposta."
PROPOSAL_DEADLINE_REQUIRED = "Informe o prazo de entrega em dias."
MINIMUM_EXCEPTION = (
    "Só {count} proposta(s); o mínimo é {minimum}. Justifique para seguir "
    "(mínimo de 20 caracteres) ou aguarde novas propostas."
)
TECHNICAL_MISSING = "Dê a nota técnica de todas as propostas (faltam {names})."
TECHNICAL_NONE_APPROVED = "Nenhuma proposta aprovada tecnicamente: revise a especificação."
TECHNICAL_MINIMUM = (
    "Só {count} proposta(s) aprovada(s) tecnicamente; o mínimo é {minimum}. Justifique para "
    "seguir (mínimo de 20 caracteres)."
)
NEGOTIATION_APPROVED_ONLY = "Negocie só com propostas aprovadas tecnicamente."
NEGOTIATION_VALUE_REQUIRED = "Informe o valor negociado."
NEGOTIATION_ABOVE_PROPOSAL = "O valor negociado não pode superar a proposta original."
PROCESS_NOT_FOUND = "Processo não encontrado."

# ── Recomendação, aprovação e emissão (ISSUE-060) ────────────────────────────────────────────

MIN_RETURN_REASON = 10
MAX_RETENTION_PCT = 20
RECOMMENDATION_APPROVED_ONLY = "Recomende só propostas aprovadas tecnicamente."
RECOMMENDATION_UNREGISTERED = "Cadastre e qualifique {name} em Fornecedores antes de recomendar."
RECOMMENDATION_BLOCKED = "Fornecedor bloqueado não pode ser adjudicado."
RECOMMENDATION_BEST_JUSTIFICATION = (
    "A recomendação não é a melhor nota final. Justifique (mínimo de 20 caracteres)."
)
RECOMMENDATION_QUALIFICATION_JUSTIFICATION = (
    "Fornecedor não está qualificado. Justifique (mínimo de 20 caracteres)."
)
RECOMMENDATION_VALUE_REQUIRED = "Informe o valor recomendado."
RETURN_REASON_REQUIRED = "Informe o motivo (mínimo de 10 caracteres)."
APPROVER_REQUIRED = "Preencha este campo."
APPROVER_UNKNOWN = "O aprovador informado não está no cadastro."
SEGREGATION_MESSAGE = (
    "Quem aprova não pode ser o comprador nem quem recomendou (segregação de funções)."
)
LLI_GATE_MESSAGE = (
    "LLI contratado antes do gate de investimento: registre a aprovação específica do gate LLI "
    "no plano de compras."
)
EAC_BALANCE_MESSAGE = (
    "O valor recomendado supera o saldo a comprometer do item {code} da EAC ({balance}). Faça "
    "remanejamento ou SM antes de aprovar."
)
CONTRACT_END_REQUIRED = "Informe o término contratual (posterior à emissão)."
CHOOSE_FISCAL = "Escolha o fiscal do contrato."
FISCAL_UNKNOWN = "O fiscal informado não está no cadastro."
RETENTION_RANGE = f"A retenção contratual deve ficar entre 0% e {MAX_RETENTION_PCT}%."

# ── Diligenciamento e recebimento (ISSUE-061) ────────────────────────────────────────────────

MAX_ORDER_COMMENT = 300
MAX_RECEIPT_PENDING = 300
MIN_DAMAGE_DESCRIPTION = 10

MILESTONE_DONE = "realizado"
MILESTONE_FORECAST = "previsao"
MILESTONE_KINDS: tuple[str, ...] = (MILESTONE_DONE, MILESTONE_FORECAST)

ORDER_SITUATION_OPEN = "abertos"
ORDER_SITUATION_ALL = "todos"
ORDER_BANDS: tuple[str, ...] = ("critico", "atencao", "vencidos")
ORDER_PAGE_SIZE = 20

ORDER_NOT_FOUND = "Pedido não encontrado."
MILESTONE_REQUIRED = "Escolha o marco."
MILESTONE_ALREADY_DONE = "Este marco já foi realizado."
DELIVERY_BY_RECEIPT = "A entrega é registrada em Registrar recebimento (conferência na obra)."
REALIZED_IN_FUTURE = "A data realizada não pode ser posterior à data de referência."
PREVIOUS_MILESTONE_REQUIRED = "Registre antes o marco anterior ({name})."
REALIZED_BEFORE_PREVIOUS = "A data não pode ser anterior à do marco anterior."
FORECAST_IN_PAST = "A previsão não pode ser anterior à data de referência."
RECEIPT_DUPLICATED = "Pedido já recebido."
SHIPMENT_REQUIRED = "Registre o embarque antes do recebimento na obra."
RECEIPT_DATE_REQUIRED = "Informe a data do recebimento (até a data de referência)."
RECEIPT_BEFORE_SHIPMENT = "O recebimento não pode ser anterior ao embarque."
DAMAGE_DESCRIPTION_REQUIRED = (
    f"Descreva as avarias (mínimo de {MIN_DAMAGE_DESCRIPTION} caracteres)."
)
DILIGENCE_ACTION_EXISTS = "Já existe ação aberta na Central para {number}."
COMMENT_TOO_LONG = f"O comentário comporta no máximo {MAX_ORDER_COMMENT} caracteres."
PENDING_TOO_LONG = f"As pendências comportam no máximo {MAX_RECEIPT_PENDING} caracteres."

MIN_RISK_TITLE = 10
RISK_LEVEL_MIN = 1
RISK_LEVEL_MAX = 5
RISK_TITLE_SHORT = f"Descreva o risco (mínimo de {MIN_RISK_TITLE} caracteres)."
RISK_LEVELS_MESSAGE = "Probabilidade e impacto de 1 a 5."
RISK_OWNER_REQUIRED = "Escolha o dono do risco."
RISK_COST_INVALID = "Informe o impacto em custo (zero ou mais)."


@dataclass(frozen=True)
class OrderFilters:
    """The filters of the order list: the search, whether delivered orders show and the band."""

    search: str = ""
    situation: str = ORDER_SITUATION_OPEN
    band: str = ""
    page: int = 1


@dataclass(frozen=True)
class MilestoneInput:
    """What the form of Atualizar marco sends: the milestone, the kind and its dates.

    On the Inspeção / FAT milestone the realization also sends the result of the inspection
    (Aprovado or Reprovado) and the inspector; a rejection demands the new forecast of the
    retest (ISSUE-069).
    """

    index: int | None
    kind: str
    realized: date | None = None
    forecast: date | None = None
    cascade: bool = True
    comment: str = ""
    result: str = ""
    inspector_id: int | None = None


@dataclass(frozen=True)
class ReceiptInput:
    """What the form of Registrar recebimento sends; the evidence arrives apart, as attachments."""

    date: date | None
    checked: bool
    damaged: bool
    damage_description: str = ""
    pending: str = ""


@dataclass(frozen=True)
class SuggestedRiskInput:
    """O que o modal de Registrar risco sugerido envia: a avaliação proposta do risco."""

    title: str
    owner_id: int | None
    probability: int | None
    impact: int | None
    cost_cents: int | None = None
    cause: str = ""
    consequence: str = ""


def suggested_risk_problems(data: SuggestedRiskInput) -> dict[str, str]:
    """Uma mensagem por campo do risco sugerido que não passa (as do protótipo)."""
    problems: dict[str, str] = {}
    if len(data.title.strip()) < MIN_RISK_TITLE:
        problems["titulo"] = RISK_TITLE_SHORT
    if data.owner_id is None:
        problems["dono"] = RISK_OWNER_REQUIRED
    for level in (data.probability, data.impact):
        if level is None or not RISK_LEVEL_MIN <= level <= RISK_LEVEL_MAX:
            problems["probabilidade"] = RISK_LEVELS_MESSAGE
    if data.cost_cents is not None and data.cost_cents < 0:
        problems["custo"] = RISK_COST_INVALID
    return problems


@dataclass(frozen=True)
class RequisitionInput:
    """What the form of Nova requisição sends: the date and the reference of the request."""

    date: date | None
    document: str = ""
    observation: str = ""


@dataclass(frozen=True)
class RfxInput:
    """What the form of Emitir RFx sends: the emission, the weights and the invitees."""

    date: date | None
    deadline: date | None
    weight_technical: int | None
    weight_commercial: int | None
    invitees: tuple[int, ...] = ()
    other_invitees: tuple[str, ...] = ()
    single_supplier: bool = False
    single_justification: str = ""


@dataclass(frozen=True)
class ProposalInput:
    """What the form of Registrar proposta sends; the PDF arrives apart, as an attachment."""

    company_id: int | None
    name: str
    received: date | None
    value_cents: int | None
    deadline_days: int | None
    validity: date | None = None


@dataclass(frozen=True)
class ClosingInput:
    """What the form of Encerrar recebimento sends."""

    date: date | None
    justification: str = ""


@dataclass(frozen=True)
class TechnicalEvaluation:
    """The score and the approval of one proposal, with the version the form opened."""

    proposal_id: int
    score: int | None
    approved: bool
    deviations: str = ""
    version: int | str | None = None


@dataclass(frozen=True)
class TechnicalInput:
    """What the form of Equalização técnica sends: one evaluation per proposal."""

    date: date | None
    evaluations: tuple[TechnicalEvaluation, ...]
    responsible_id: int | None = None
    opinion: str = ""
    justification: str = ""


@dataclass(frozen=True)
class CommercialInput:
    """What the form of Equalização comercial sends: the weights and the date of the map."""

    date: date | None
    weight_technical: int | None
    weight_commercial: int | None
    version: int | str | None = None


@dataclass(frozen=True)
class NegotiationInput:
    """What the form of Registrar negociação sends: the approved proposal and the value."""

    proposal_id: int | None
    value_cents: int | None
    date: date | None
    observation: str = ""


@dataclass(frozen=True)
class RecommendationInput:
    """What the form of Recomendar adjudicação sends: the proposal and the recommended value."""

    proposal_id: int | None
    value_cents: int | None
    date: date | None
    justification: str = ""


@dataclass(frozen=True)
class ReturnInput:
    """What the form of Devolver recomendação sends: the reason that returns to negotiation."""

    reason: str = ""


@dataclass(frozen=True)
class ApprovalInput:
    """What the form of Aprovar adjudicação sends: who approves, when and the opinion."""

    approver_id: int | None
    date: date | None
    opinion: str = ""


@dataclass(frozen=True)
class EmissionInput:
    """What the form of Emitir pedido ou contrato sends.

    For an equipment/material package only the delivery deadline matters; for a service/EPC
    package the contract carries the start, the end, the fiscal and the retention.
    """

    date: date | None
    deadline_days: int | None = None
    start: date | None = None
    end: date | None = None
    fiscal_id: int | None = None
    retention_pct: int | None = None


@dataclass(frozen=True)
class ProposalSituation:
    """What the recommendation check needs to know about the chosen proposal.

    ``approved`` is whether it is technically approved, ``registered`` whether its supplier is
    in the register and ``blocked`` whether the qualification blocks it; ``not_best`` and
    ``needs_justification`` say why the justification is demanded, as the prototype chose the
    message between the two cases.
    """

    approved: bool
    registered: bool
    blocked: bool
    name: str
    not_best: bool
    needs_justification: bool


@dataclass(frozen=True)
class ProcessFilters:
    """The filters of the list: the search and whether the concluded processes show."""

    search: str = ""
    situation: str = "andamento"


def date_problem(
    value: date | None, *, reference_date: date, field: str = "data"
) -> dict[str, str]:
    """The date of an action: required and never after the reference date."""
    if value is None:
        return {field: PLAN_DATE_REQUIRED}
    if value > reference_date:
        return {field: DATE_IN_THE_FUTURE}
    return {}


def rfx_problems(
    data: RfxInput,
    *,
    reference_date: date,
    minimum: int,
    blocked: Sequence[str] = (),
    unknown: Sequence[str] = (),
) -> dict[str, str]:
    """One message per field of the RFx that does not hold up.

    ``blocked`` and ``unknown`` are the invitees the facade resolved as blocked suppliers or as
    companies outside the register; the minimum of the parameter applies only without the single
    supplier, which demands its justification.
    """
    problems = date_problem(data.date, reference_date=reference_date)
    if data.deadline is None:
        problems["dataLimite"] = PLAN_DATE_REQUIRED
    elif data.date is not None and data.deadline < data.date:
        problems["dataLimite"] = DEADLINE_ORDER
    problems.update(_weight_problems(data.weight_technical, data.weight_commercial))
    invitees = len(data.invitees) + len(data.other_invitees)
    if data.single_supplier:
        if len(data.single_justification.strip()) < MIN_PROCESS_JUSTIFICATION:
            problems["justUnico"] = SINGLE_JUSTIFICATION
    elif invitees < minimum:
        problems["convidados"] = INVITEES_MINIMUM.format(minimum=minimum)
    if unknown:
        problems["convidados"] = INVITEE_UNKNOWN
    if blocked:
        problems["convidados"] = INVITEE_BLOCKED.format(names=", ".join(blocked))
    return problems


def proposal_problems(
    data: ProposalInput,
    *,
    reference_date: date,
    blocked: bool = False,
    duplicated: bool = False,
) -> dict[str, str]:
    """One message per field of the proposal that does not hold up."""
    problems: dict[str, str] = {}
    if data.company_id is None and not data.name.strip():
        problems["fornecedor"] = PROPOSAL_SUPPLIER_REQUIRED
    if blocked:
        problems["fornecedor"] = PROPOSAL_BLOCKED
    if duplicated:
        problems["fornecedor"] = PROPOSAL_DUPLICATE
    problems.update(date_problem(data.received, reference_date=reference_date, field="recebida"))
    if data.value_cents is None or data.value_cents <= 0:
        problems["valor"] = PROPOSAL_VALUE_REQUIRED
    if data.deadline_days is None or data.deadline_days <= 0:
        problems["prazo"] = PROPOSAL_DEADLINE_REQUIRED
    return problems


def closing_problems(
    data: ClosingInput, *, reference_date: date, count: int, minimum: int, exception: bool
) -> dict[str, str]:
    """The closing date, and the justification the flow demands below the minimum.

    ``exception`` is the single supplier of the RFx, whose justification already covers the
    exception to the minimum.
    """
    problems = date_problem(data.date, reference_date=reference_date)
    below = count < minimum and not exception
    if below and len(data.justification.strip()) < MIN_PROCESS_JUSTIFICATION:
        problems["justificativa"] = MINIMUM_EXCEPTION.format(count=count, minimum=minimum)
    return problems


def technical_score_problems(
    data: TechnicalInput, *, reference_date: date, missing: Sequence[str] = ()
) -> dict[str, str]:
    """The date and the scores of the technical equalization: every proposal gets a score."""
    problems = date_problem(data.date, reference_date=reference_date)
    if missing:
        problems["avaliacoes"] = TECHNICAL_MISSING.format(names=", ".join(missing))
    return problems


def technical_approval_problems(
    data: TechnicalInput, *, approved_count: int, minimum: int, single_supplier: bool
) -> dict[str, str]:
    """At least one approval, and below the minimum a justification (single supplier excepted)."""
    if not approved_count:
        return {"avaliacoes": TECHNICAL_NONE_APPROVED}
    below = approved_count < minimum and not single_supplier
    if below and len(data.justification.strip()) < MIN_PROCESS_JUSTIFICATION:
        return {"justificativa": TECHNICAL_MINIMUM.format(count=approved_count, minimum=minimum)}
    return {}


def commercial_problems(data: CommercialInput, *, reference_date: date) -> dict[str, str]:
    """The date of the map and the weights of the commercial equalization."""
    problems = date_problem(data.date, reference_date=reference_date)
    problems.update(_weight_problems(data.weight_technical, data.weight_commercial))
    return problems


def negotiation_problems(
    data: NegotiationInput, *, reference_date: date, above_proposal: bool
) -> dict[str, str]:
    """The date, the value and the ceiling of the negotiation (the original proposal)."""
    problems = date_problem(data.date, reference_date=reference_date)
    if data.value_cents is None or data.value_cents <= 0:
        problems["valor"] = NEGOTIATION_VALUE_REQUIRED
    elif above_proposal:
        problems["valor"] = NEGOTIATION_ABOVE_PROPOSAL
    return problems


def recommendation_problems(
    data: RecommendationInput,
    *,
    reference_date: date,
    situation: ProposalSituation,
) -> dict[str, str]:
    """One message per field of the recommendation that does not hold up.

    A recommendation that is not the best score or not from a qualified supplier demands the
    justification (20 characters and up), with the message of the prototype for each case; a
    blocked supplier never follows.
    """
    problems = date_problem(data.date, reference_date=reference_date)
    if data.proposal_id is None or not situation.approved:
        problems["fornecedor"] = RECOMMENDATION_APPROVED_ONLY
    elif not situation.registered:
        problems["fornecedor"] = RECOMMENDATION_UNREGISTERED.format(name=situation.name)
    elif situation.blocked:
        problems["fornecedor"] = RECOMMENDATION_BLOCKED
    if data.value_cents is None or data.value_cents <= 0:
        problems["valor"] = RECOMMENDATION_VALUE_REQUIRED
    if situation.needs_justification and (
        len(data.justification.strip()) < MIN_PROCESS_JUSTIFICATION
    ):
        problems["justificativa"] = (
            RECOMMENDATION_BEST_JUSTIFICATION
            if situation.not_best
            else RECOMMENDATION_QUALIFICATION_JUSTIFICATION
        )
    return problems


def return_problems(data: ReturnInput) -> dict[str, str]:
    """The reason of the return (10 characters and up), as the prototype; the date is the reference."""
    if len(data.reason.strip()) < MIN_RETURN_REASON:
        return {"motivo": RETURN_REASON_REQUIRED}
    return {}


def approval_problems(
    data: ApprovalInput, *, reference_date: date, approver_known: bool
) -> dict[str, str]:
    """The approver and the date of the approval; the segregation is a 403 of the facade."""
    problems = date_problem(data.date, reference_date=reference_date)
    if data.approver_id is None:
        problems["aprovador"] = APPROVER_REQUIRED
    elif not approver_known:
        problems["aprovador"] = APPROVER_UNKNOWN
    return problems


def emission_problems(
    data: EmissionInput,
    *,
    reference_date: date,
    service: bool,
    fiscal_known: bool = True,
) -> dict[str, str]:
    """One message per field of the emission that does not hold up.

    An equipment/material package demands the delivery deadline; a service/EPC package demands
    the contractual end after the emission, the fiscal and a retention between 0% and 20%.
    """
    problems = date_problem(data.date, reference_date=reference_date)
    if service:
        if data.end is None or (data.date is not None and data.end <= data.date):
            problems["termino"] = CONTRACT_END_REQUIRED
        if data.fiscal_id is None:
            problems["fiscal"] = CHOOSE_FISCAL
        elif not fiscal_known:
            problems["fiscal"] = FISCAL_UNKNOWN
        if data.retention_pct is not None and not 0 <= data.retention_pct <= MAX_RETENTION_PCT:
            problems["retencao"] = RETENTION_RANGE
    elif data.deadline_days is None or data.deadline_days <= 0:
        problems["prazo"] = PROPOSAL_DEADLINE_REQUIRED
    return problems


def eac_balance_problem(*, code: str, balance_cents: int, value_cents: int) -> str | None:
    """The message of a recommended value above the saldo a comprometer, or ``None``."""
    if value_cents <= balance_cents:
        return None
    return EAC_BALANCE_MESSAGE.format(code=code, balance=format_brl(balance_cents))


def _weight_problems(weight_technical: int | None, weight_commercial: int | None) -> dict[str, str]:
    if weight_technical is None or weight_commercial is None:
        return {"pesoTecnico": PLAN_DATE_REQUIRED, "pesoComercial": PLAN_DATE_REQUIRED}
    if weight_technical + weight_commercial != 100:
        return {"pesoTecnico": WEIGHTS_TOTAL}
    return {}


def names_of(raw: str) -> tuple[str, ...]:
    """The names typed as a comma-separated list: trimmed, without blanks and without repeats."""
    cleaned = (item.strip() for item in (raw or "").split(","))
    return tuple(dict.fromkeys(item for item in cleaned if item))


def parse_points(raw: str | None) -> int | None:
    """A whole number from 0 to 100 (a score or a weight), or ``None`` when it is not one."""
    text = (raw or "").strip()
    if not text.isdigit():
        return None
    value = int(text)
    return value if value <= MAX_POINTS else None


def parse_positive_int(raw: str | None, *, maximum: int = MAX_DEADLINE_DAYS) -> int | None:
    """A whole number from 1 to ``maximum``, or ``None`` when it is not one."""
    text = (raw or "").strip()
    if not text.isdigit():
        return None
    value = int(text)
    return value if 1 <= value <= maximum else None


def parse_process_filters(params: Mapping[str, str]) -> ProcessFilters:
    """Read the filters of the process list; the default is the in-progress processes."""
    raw = (params.get("situacao") or "").strip()
    return ProcessFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH],
        situation="" if raw == "todos" else "andamento",
    )


def creation_problems(data: SupplierInput) -> dict[str, str]:
    """One message per field of the new supplier that does not hold up."""
    problems: dict[str, str] = {}
    name = data.name.strip()
    if not name:
        problems["nome"] = NAME_REQUIRED
    elif len(name) < MIN_NAME:
        problems["nome"] = NAME_TOO_SHORT
    elif len(name) > MAX_NAME:
        problems["nome"] = NAME_TOO_LONG
    if data.kind not in KINDS:
        problems["tipo"] = CHOOSE_KIND
    problems.update(_category_problems(data.categories))
    problems.update(_observation_problems(data.observation))
    problems.update(_document_problems(data.documents))
    return problems


def qualification_problems(
    data: QualificationInput, *, previous_situation: str | None, reference_date: date
) -> dict[str, str]:
    """One message per field of the qualification that does not hold up."""
    problems: dict[str, str] = {}
    if data.situation not in SITUATIONS:
        problems["situacao"] = CHOOSE_SITUATION
    if data.situation == QUALIFIED and data.validity is None:
        problems["validade"] = VALIDITY_REQUIRED
    elif data.validity is not None and data.validity < reference_date:
        problems["validade"] = VALIDITY_IN_THE_PAST
    problems.update(_category_problems(data.categories))
    justification = data.justification.strip()
    if len(justification) > MAX_JUSTIFICATION:
        problems["justificativa"] = JUSTIFICATION_TOO_LONG
    elif (
        calculations.justification_is_required(previous_situation, data.situation)
        and len(justification) < MIN_JUSTIFICATION
    ):
        problems["justificativa"] = JUSTIFICATION_REQUIRED
    if data.situation in (RESTRICTED, BLOCKED) and not (data.observation.strip() or justification):
        problems["observacao"] = REASON_REQUIRED
    problems.update(_observation_problems(data.observation))
    problems.update(_document_problems(data.documents))
    return problems


def _category_problems(categories: tuple[str, ...]) -> dict[str, str]:
    if not categories:
        return {"categorias": CATEGORIES_REQUIRED}
    if sum(len(category) for category in categories) > MAX_CATEGORIES:
        return {"categorias": CATEGORIES_TOO_LONG}
    if any(len(category) > MAX_CATEGORY for category in categories):
        return {"categorias": CATEGORY_TOO_LONG}
    return {}


def _observation_problems(observation: str) -> dict[str, str]:
    if len(observation.strip()) > MAX_OBSERVATION:
        return {"observacao": OBSERVATION_TOO_LONG}
    return {}


def _document_problems(documents: Iterable[DocumentInput]) -> dict[str, str]:
    for document in documents:
        name = document.name.strip()
        if not name:
            return {"documentos": DOCUMENT_NAME_REQUIRED}
        if len(name) > MAX_DOCUMENT_NAME:
            return {"documentos": DOCUMENT_NAME_TOO_LONG}
    return {}


def categories_of(raw: str) -> tuple[str, ...]:
    """The categories typed as a comma-separated list: trimmed, without blanks and without repeats."""
    cleaned = (item.strip() for item in (raw or "").split(","))
    return tuple(dict.fromkeys(item for item in cleaned if item))


# ── What a person types, as the route reads it ────────────────────────────────────────────────


def parse_id(raw: str | None) -> int | None:
    """A positive whole number from the request, or ``None`` when it is not one."""
    text = (raw or "").strip()
    if not text.isdigit() or len(text) > MAX_ID_DIGITS or int(text) < 1:
        return None
    return int(text)


def parse_date(raw: str | None) -> date | None:
    """A date written ``2026-09-25``, or ``None`` when it is empty or not a real date."""
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def parse_filters(params: Mapping[str, str]) -> SupplierFilters:
    """Read the filters of the list from the query string; an invalid value is ignored."""
    page = parse_id(params.get("pagina")) or 1
    return SupplierFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH],
        situation=(params.get("situacao") or "").strip(),
        category=(params.get("categoria") or "").strip(),
        page=min(page, MAX_PAGE),
    )


def parse_documents(
    ids: Iterable[str],
    names: Iterable[str],
    validities: Iterable[str],
    versions: Iterable[str] = (),
) -> tuple[DocumentInput, ...]:
    """The document rows of the form, paired by position and without the blank names."""
    rows: list[DocumentInput] = []
    for raw_id, name, raw_validity, raw_version in zip(
        ids, names, validities, versions, strict=False
    ):
        cleaned = name.strip()
        if cleaned:
            rows.append(
                DocumentInput(
                    id=parse_id(raw_id),
                    name=cleaned,
                    validity=parse_date(raw_validity),
                    version=(raw_version or "").strip() or None,
                )
            )
    return tuple(rows)


# ── Purchase plan: the checks (ISSUE-058) ────────────────────────────────────────────────────


def package_problems(
    data: PackageInput,
    *,
    eac_items: Mapping[str, object],
    discipline_ids: Collection[int],
    buyer_ids: Collection[int],
) -> dict[str, str]:
    """One message per field of the package that does not hold up, in the full plan."""
    problems = _scope_problems(data.scope)
    if data.kind not in PACKAGE_TYPES:
        problems["tipo"] = CHOOSE_TYPE
    if data.modality not in PACKAGE_MODALITIES:
        problems["modalidade"] = CHOOSE_MODALITY
    if data.discipline_id is None:
        problems["disciplina"] = CHOOSE_DISCIPLINE
    elif data.discipline_id not in discipline_ids:
        problems["disciplina"] = DISCIPLINE_UNKNOWN
    if data.buyer_id is None:
        problems["comprador"] = CHOOSE_BUYER
    elif data.buyer_id not in buyer_ids:
        problems["comprador"] = BUYER_UNKNOWN
    problems.update(_eac_problems(data.eac_code, eac_items))
    problems.update(_plan_problems(data))
    problems.update(_gate_problems(data))
    problems.update(_emergency_problems(data))
    return problems


def change_problems(data: PackageChangeInput, *, changed: bool) -> dict[str, str]:
    """One message per field of the frozen form that does not hold up.

    The justification is only demanded when something really changes (10 characters and up);
    the estimate stays positive and the ROS is required, as in the prototype.
    """
    problems = _scope_problems(data.scope)
    if data.buyer_id is None:
        problems["comprador"] = CHOOSE_BUYER
    if data.estimate_cents is None or data.estimate_cents <= 0:
        problems["estimativa"] = ESTIMATE_REQUIRED
    if data.ros is None:
        problems["ros"] = ROS_REQUIRED
    justification = data.justification.strip()
    if len(justification) > MAX_JUSTIFICATION:
        problems["justificativa"] = JUSTIFICATION_TOO_LONG
    elif changed and len(justification) < MIN_JUSTIFICATION:
        problems["justificativa"] = CHANGE_JUSTIFICATION_REQUIRED
    return problems


def frozen_baseline_problems(posted_fields: Iterable[str]) -> dict[str, str]:
    """A frozen package refuses any baseline field coming from the form, whatever the value."""
    sent = set(posted_fields)
    if any(name in sent for name in BASELINE_FIELDS):
        return {"geral": FROZEN_BASELINE}
    return {}


def _scope_problems(scope: str) -> dict[str, str]:
    cleaned = scope.strip()
    if not cleaned:
        return {"escopo": SCOPE_REQUIRED}
    if len(cleaned) < MIN_PACKAGE_SCOPE:
        return {"escopo": SCOPE_TOO_SHORT}
    if len(cleaned) > MAX_PACKAGE_SCOPE:
        return {"escopo": SCOPE_TOO_LONG}
    return {}


def _eac_problems(eac_code: str, eac_items: Mapping[str, object]) -> dict[str, str]:
    cleaned = eac_code.strip()
    if not cleaned:
        return {"eac": EAC_REQUIRED}
    if cleaned not in eac_items:
        return {"eac": EAC_NOT_COST_ITEM.format(code=cleaned)}
    return {}


def _plan_problems(data: PackageInput) -> dict[str, str]:
    """The four required plan dates, their order and the planned slack against the ROS."""
    problems: dict[str, str] = {}
    dates = {
        "requisicao": data.requisition,
        "rfx": data.rfx,
        "adjudicacao": data.adjudication,
        "pedido": data.order,
    }
    for field, value in dates.items():
        if value is None:
            problems[field] = PLAN_DATE_REQUIRED
    if not problems and not calculations.plan_dates_in_order(dates):
        problems["pedido"] = PLAN_DATES_ORDER
    if data.estimate_cents is None or data.estimate_cents <= 0:
        problems["estimativa"] = ESTIMATE_REQUIRED
    if data.ros is None:
        problems["ros"] = ROS_REQUIRED
    else:
        slack = calculations.planned_slack_days(data.ros, data.order)
        if slack is not None and slack < 0:
            problems["ros"] = SLACK_NEGATIVE
    return problems


def _gate_problems(data: PackageInput) -> dict[str, str]:
    """LLI before the investment gate demands the specific approval reference."""
    if not (data.lli and data.anticipated_fid):
        return {}
    reference = data.gate_reference.strip()
    if not reference:
        return {"gate": GATE_REQUIRED}
    if len(reference) > MAX_GATE_REFERENCE:
        return {"gate": GATE_TOO_LONG}
    return {}


def _emergency_problems(data: PackageInput) -> dict[str, str]:
    """An emergency purchase is marked and justified (20 characters and up, as the prototype)."""
    if not data.emergency:
        return {}
    justification = data.emergency_justification.strip()
    if len(justification) < MIN_EMERGENCY_JUSTIFICATION:
        return {"justEmergencial": EMERGENCY_REQUIRED}
    if len(justification) > MAX_JUSTIFICATION:
        return {"justEmergencial": EMERGENCY_TOO_LONG}
    return {}


def parse_package_filters(params: Mapping[str, str]) -> PackageFilters:
    """Read the filters of the plan from the query string; an invalid value is ignored."""
    page = parse_id(params.get("pagina")) or 1
    kind = (params.get("tipo") or "").strip()
    return PackageFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH],
        kind=kind if kind in PACKAGE_TYPES else "",
        lli_only=parse_flag(params.get("lli")),
        page=min(page, MAX_PAGE),
    )


def parse_money(text: str) -> int | None:
    """Cents of a value written in reais (``1.234,56``), or ``None`` when it is not one."""
    if not text.strip():
        return None
    converted = convert(RawCell(value=text), ValueKind.MONEY)
    return converted.value if converted.problem is None else None


def parse_flag(raw: str | None) -> bool:
    """A checkbox value of the form: ``1``, ``true``, ``on`` or ``sim`` mean yes."""
    return (raw or "").strip().lower() in ("1", "true", "on", "sim")


# ── Diligenciamento e recebimento: the checks (ISSUE-061) ────────────────────────────────────


def parse_order_filters(params: Mapping[str, str]) -> OrderFilters:
    """Read the filters of the order list; the default is the open orders."""
    raw = (params.get("situacao") or "").strip()
    band = (params.get("faixa") or "").strip()
    page = parse_id(params.get("pagina")) or 1
    return OrderFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH],
        situation=ORDER_SITUATION_ALL if raw == "todos" else ORDER_SITUATION_OPEN,
        band=band if band in ORDER_BANDS else "",
        page=min(page, MAX_PAGE),
    )


@dataclass(frozen=True)
class MilestoneContext:
    """O estado do marco que a validação lê: a referência, o já realizado e o marco anterior."""

    reference_date: date
    already_done: bool
    is_delivery: bool
    previous_name: str
    previous_real: date | None
    is_inspection: bool = False


def milestone_problems(data: MilestoneInput, context: MilestoneContext) -> dict[str, str]:
    """One message per field of the milestone update that does not hold up.

    The check of the stage and of the previous milestone, of the date against the reference and
    of the forecast that may not fall in the past, as the prototype refused them; the delivery
    milestone only completes through the receipt. The Inspeção / FAT milestone demands the
    result of the inspection, and a rejection does not complete the milestone: it demands the
    new forecast of the retest (ISSUE-069).
    """
    if data.index is None:
        return {"marco": MILESTONE_REQUIRED}
    if context.already_done:
        return {"marco": MILESTONE_ALREADY_DONE}
    problems = (
        _realization_problems(data, context)
        if data.kind == MILESTONE_DONE
        else _forecast_problems(data, context)
    )
    if not problems and data.kind == MILESTONE_DONE and context.is_inspection:
        problems = _inspection_problems(data, context)
    if len(data.comment.strip()) > MAX_ORDER_COMMENT:
        problems["comentario"] = COMMENT_TOO_LONG
    return problems


def _realization_problems(data: MilestoneInput, context: MilestoneContext) -> dict[str, str]:
    """The realization: the delivery is the receipt, and the date respects the previous one."""
    if context.is_delivery:
        return {"realizada": DELIVERY_BY_RECEIPT}
    if data.realized is None:
        return {"realizada": PLAN_DATE_REQUIRED}
    if data.realized > context.reference_date:
        return {"realizada": REALIZED_IN_FUTURE}
    if context.previous_name and context.previous_real is None:
        return {"realizada": PREVIOUS_MILESTONE_REQUIRED.format(name=context.previous_name)}
    if context.previous_real is not None and data.realized < context.previous_real:
        return {"realizada": REALIZED_BEFORE_PREVIOUS}
    return {}


def _forecast_problems(data: MilestoneInput, context: MilestoneContext) -> dict[str, str]:
    """The reprogramming: the forecast never falls in the past."""
    if data.kind != MILESTONE_FORECAST:
        return {"tipo": PLAN_DATE_REQUIRED}
    if data.forecast is None:
        return {"previsao": PLAN_DATE_REQUIRED}
    if data.forecast < context.reference_date:
        return {"previsao": FORECAST_IN_PAST}
    return {}


FAT_RESULTS: tuple[str, ...] = ("Aprovado", "Reprovado")
FAT_RESULT_REQUIRED = "Informe o resultado da inspeção em fábrica."
FAT_RETEST_REQUIRED = "FAT reprovado: informe a nova previsão do reteste."


def _inspection_problems(data: MilestoneInput, context: MilestoneContext) -> dict[str, str]:
    """The FAT: the result of the inspection, and the retest forecast when it is rejected."""
    if data.result not in FAT_RESULTS:
        return {"resultado": FAT_RESULT_REQUIRED}
    if data.result == "Reprovado" and (
        data.forecast is None or data.forecast < context.reference_date
    ):
        return {"previsao": FAT_RETEST_REQUIRED}
    return {}


def receipt_problems(
    data: ReceiptInput,
    *,
    reference_date: date,
    already_received: bool,
    shipment_real: date | None,
) -> dict[str, str]:
    """One message per field of the receipt that does not hold up.

    The receipt demands the shipment done and a date up to the reference and never before the
    shipment; damages demand their description (10 characters and up), as the prototype.
    """
    if already_received:
        return {"geral": RECEIPT_DUPLICATED}
    if shipment_real is None:
        return {"geral": SHIPMENT_REQUIRED}
    problems: dict[str, str] = {}
    if data.date is None or data.date > reference_date:
        problems["data"] = RECEIPT_DATE_REQUIRED
    elif data.date < shipment_real:
        problems["data"] = RECEIPT_BEFORE_SHIPMENT
    if data.damaged and len(data.damage_description.strip()) < MIN_DAMAGE_DESCRIPTION:
        problems["descricaoAvarias"] = DAMAGE_DESCRIPTION_REQUIRED
    if len(data.pending.strip()) > MAX_RECEIPT_PENDING:
        problems["pendencias"] = PENDING_TOO_LONG
    return problems


# ── O Mapa de Suprimentos (ISSUE-062) ────────────────────────────────────────────────────────

MAS_MODE_DATES = "datas"
MAS_MODE_DEVIATION = "desvio"
MAS_MODES: tuple[str, ...] = (MAS_MODE_DATES, MAS_MODE_DEVIATION)
MAS_PHASE_ALL = "todos"
MAS_PHASES: tuple[str, ...] = ("aquisicao", "fabricacao")
MAS_LLI_CHOICES: tuple[str, ...] = ("sim", "nao")
MAS_ORDERS: tuple[str, ...] = ("codigo", "folga", "valor", "avanco")
MAS_LINE_SITUATIONS: tuple[str, ...] = (
    calculations.MAS_CRITICAL,
    calculations.MAS_WARNING,
    calculations.MAS_ON_TIME,
    calculations.MAS_DELIVERED,
    calculations.MAS_CONTRACTED,
)

MAS_ORDER_DEFAULT = "codigo"


@dataclass(frozen=True)
class MasFilters:
    """The filters of the map: what the query string of the screen says.

    ``mode`` is what the cells show (dates or the deviation in days), ``phase`` which half of the
    milestones the table carries, and ``order`` the sorting of the lines; an invalid value falls
    back to the default, as everywhere else.
    """

    search: str = ""
    mode: str = MAS_MODE_DATES
    phase: str = MAS_PHASE_ALL
    discipline_id: int | None = None
    kind: str = ""
    lli: str = ""
    buyer_id: int | None = None
    supplier_id: int | None = None
    situation: str = ""
    overdue_only: bool = False
    order: str = MAS_ORDER_DEFAULT


def parse_mas_filters(params: Mapping[str, str]) -> MasFilters:
    """Read the filters of the map from the query string; an invalid value is ignored."""
    mode = (params.get("modo") or "").strip()
    phase = (params.get("fase") or "").strip()
    lli = (params.get("lli") or "").strip()
    situation = (params.get("situacao") or "").strip()
    kind = (params.get("tipo") or "").strip()
    order = (params.get("ordem") or "").strip()
    return MasFilters(
        search=(params.get("busca") or "").strip()[:MAX_SEARCH],
        mode=mode if mode in MAS_MODES else MAS_MODE_DATES,
        phase=phase if phase in MAS_PHASES else MAS_PHASE_ALL,
        discipline_id=parse_id(params.get("disciplina")),
        kind=kind if kind in PACKAGE_TYPES else "",
        lli=lli if lli in MAS_LLI_CHOICES else "",
        buyer_id=parse_id(params.get("comprador")),
        supplier_id=parse_id(params.get("fornecedor")),
        situation=situation if situation in MAS_LINE_SITUATIONS else "",
        overdue_only=parse_flag(params.get("vencidos")),
        order=order if order in MAS_ORDERS else MAS_ORDER_DEFAULT,
    )
