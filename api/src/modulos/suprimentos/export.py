"""The export of the register: one ``Document``, the Excel and the printable version (D12).

What the screen shows is what leaves: the six KPIs with their reference, the line of active
filters and the table of the suppliers of the filter, with the same content the prototype
exported (Empresa with the type, Categorias, Situação, Validade, Documentos, Desempenho with the
class and the note of the contract evaluations and the Valor contratado). The register is global
(``fornecedor`` is per company, not per project), so the table declares itself not per project:
there is no ``Projeto`` column, which the platform only adds to a table that is per project
(HU-016).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
    Column,
    Document,
    Kpi,
    Paper,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.suprimentos import calculations, service
from src.modulos.suprimentos.validation import SupplierFilters

TITLE = "Fornecedores"
TABLE_TITLE = "Fornecedores e contratadas"
ALL_SUPPLIERS = "Todos os fornecedores"
DOCUMENTS_IN_DAY = "Válidos"
DOCUMENTS_EXPIRED = "Documentos vencidos"

SITUATION_TONES = {
    calculations.QUALIFIED: Tone.OK,
    calculations.IN_QUALIFICATION: Tone.INFO,
    calculations.RESTRICTED: Tone.WARN,
    calculations.BLOCKED: Tone.ERROR,
    service.NO_QUALIFICATION: Tone.NEUTRAL,
}


def build_document(
    *,
    listing: service.SupplierListing,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
) -> Document:
    """The document of the register for the filters in force: KPIs, filters and the table."""
    return Document(
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=(
            ("Filtros", filter_text(listing.filters)),
            ("Fornecedores no filtro", str(listing.total)),
        ),
        kpis=_kpis(listing),
        tables=(_table(listing.lines),),
        paper=Paper.A4,
    )


def filter_text(filters: SupplierFilters) -> str:
    """The active filters as one line, or the whole register when there is none."""
    parts: list[str] = []
    if filters.search:
        parts.append(f"Busca: {filters.search}")
    if filters.situation:
        parts.append(f"Situação: {filters.situation}")
    if filters.category:
        parts.append(f"Categoria: {filters.category}")
    return " · ".join(parts) if parts else ALL_SUPPLIERS


def evaluation_text(line: service.SupplierLine) -> str:
    """The performance as the prototype exported it: ``Classe A (86)``; empty without one."""
    evaluation = line.last_evaluation
    if evaluation is None or evaluation.score is None or not evaluation.score_class:
        return ""
    return f"Classe {evaluation.score_class} ({evaluation.score})"


def _kpis(listing: service.SupplierListing) -> tuple[Kpi, ...]:
    summary = listing.summary
    return (
        Kpi(
            "Cadastrados",
            summary.registered,
            f"Referência: de {summary.companies} empresas",
            ValueKind.INTEGER,
            tone=Tone.NEUTRAL,
            status=f"{summary.unregistered} empresas sem qualificação",
        ),
        Kpi(
            "Qualificados",
            summary.qualified,
            f"Referência: de {summary.registered} cadastrados",
            ValueKind.INTEGER,
            tone=Tone.OK,
        ),
        Kpi(
            "Em qualificação",
            summary.in_qualification,
            f"Referência: de {summary.registered} cadastrados",
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
        Kpi(
            "Restritos ou bloqueados",
            summary.restricted_or_blocked,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.restricted_or_blocked else Tone.OK,
            status=f"{summary.blocked} bloqueados",
        ),
        Kpi(
            "Documentos vencidos",
            summary.expired_documents,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.ERROR if summary.expired_documents else Tone.OK,
            status="certidões e certificados fora da validade",
        ),
        Kpi(
            "Qualificação a vencer",
            summary.validity_due,
            "Esperado: 0",
            ValueKind.INTEGER,
            tone=Tone.WARN if summary.validity_due else Tone.OK,
            status="vencida ou vence em até 90 dias",
        ),
    )


def _table(lines: Sequence[service.SupplierLine]) -> Table:
    return Table(
        title=TABLE_TITLE,
        columns=(
            Column("Empresa", width=34),
            Column("Tipo", width=14),
            Column("Categorias", width=34),
            Column("Situação", width=18),
            Column("Validade", width=14, kind=ValueKind.DATE),
            Column("Documentos", width=24),
            Column("Desempenho", width=20),
            Column("Valor contratado", width=20, kind=ValueKind.MONEY),
        ),
        rows=tuple(_row(line) for line in lines),
        per_project=False,
    )


def _row(line: service.SupplierLine) -> Row:
    documents = DOCUMENTS_IN_DAY if line.documents_up_to_date else DOCUMENTS_EXPIRED
    return row(
        line.name,
        line.kind or "",
        ", ".join(line.categories),
        Cell(line.situation, SITUATION_TONES.get(line.situation, Tone.NEUTRAL)),
        line.validity,
        Cell(documents, Tone.OK if line.documents_up_to_date else Tone.ERROR),
        evaluation_text(line),
        line.contracted_cents,
    )
