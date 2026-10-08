"""Input validation of the supplier register (ISSUE-057).

The shapes the facade receives (new supplier, qualification, filters, documents) and the checks
of what a person types. The checks are pure and return one message per field, in a dict that is
empty when everything holds up; the facade turns it into one ``InvalidDataError`` (422), so the
rule holds for the route and for any module that calls the facade.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from src.modulos.suprimentos import calculations
from src.modulos.suprimentos.calculations import BLOCKED, QUALIFIED, RESTRICTED, SITUATIONS

KINDS: tuple[str, ...] = ("Fornecedor", "Contratada")

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
