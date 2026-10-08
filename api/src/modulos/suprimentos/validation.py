"""Input validation of the supplier register and of the purchase plan (ISSUE-057/058).

The shapes the facade receives (new supplier, qualification, filters, documents, packages) and
the checks of what a person types. The checks are pure and return one message per field, in a
dict that is empty when everything holds up; the facade turns it into one ``InvalidDataError``
(422), so the rule holds for the route and for any module that calls the facade.

The package of the plan is always tied to a cost item (level 3) of the EAC, the plan dates grow
and the plan may not be born with negative slack; the emergency purchase demands its
justification and the LLI contracted before the investment gate demands the specific approval.
After the requisition the baseline is frozen: only scope, buyer, estimate and ROS change, with a
justification.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from src.core.export_document import ValueKind
from src.core.import_values import RawCell, convert
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
