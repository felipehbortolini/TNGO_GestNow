"""Business facade of Configurações: versioned parameters (D5, D6).

A parameter version is immutable: saving creates a new version of the group
with effectiveness, author and a mandatory justification, after the rules of
section 7.4 (``validation``). The version in force on a date is the last one
whose effectiveness is not after it. Nothing here reads the clock: the caller
passes the reference date, obtained from ``core.calendario``.

The values of a version keep the shape of the prototype's
``MOCK.parametros`` — the same keys the module facades will consume — and are
stored one row per leaf in ``parametro_valor``, with the path as the key, a
type and the value as text (lists use the index in the path).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import recording
from src.core.errors import InvalidDataError
from src.modulos.configuracoes import validation
from src.modulos.configuracoes.models import ParameterValue, ParameterVersion, Project

INITIAL_JUSTIFICATION = "Versão inicial"

# Version 1 seeds with the initial values of table 7.4 of the prototype's
# README (13 groups) plus the Anexos group of D5a (25 MB; PDF, JPG, PNG,
# DOCX, XLSX, PPTX, DWG and ZIP). The keys match ``MOCK.parametros`` minus
# the version metadata, so a module facade reads the same path the prototype
# read.
INITIAL_PARAMETERS: dict[str, dict[str, Any]] = {
    "avaliacaoContratada": {
        "criterios": [
            {"id": "hse", "nome": "HSE", "peso": 25},
            {"id": "qualidade", "nome": "Qualidade", "peso": 20},
            {"id": "prazo", "nome": "Prazo", "peso": 20},
            {"id": "gestao", "nome": "Gestão contratual e comercial", "peso": 15},
            {"id": "recursos", "nome": "Recursos e mobilização", "peso": 10},
            {"id": "documentacao", "nome": "Documentação e comunicação", "peso": 10},
        ],
        "classes": [
            {"classe": "A", "minimo": 85, "descricao": "Preferencial"},
            {"classe": "B", "minimo": 70, "descricao": "Aprovada"},
            {"classe": "C", "minimo": 50, "descricao": "Aprovada com plano de melhoria"},
            {"classe": "D", "minimo": 0, "descricao": "Não recomendada"},
        ],
        "notaExigePlano": 2,
    },
    "claims": {"prazoNotificacaoPadraoDias": 30},
    "hse": {
        "baseTaxa": 1000000,
        "prazos": {
            "comunicacaoHoras": 24,
            "investigacaoPreliminarHoras": 48,
            "relatorioFinalDias": 30,
        },
        "referenciaPiramide": "bird",
        "metas": {"observacoesPor10MilHht": 40, "desviosPor10MilHht": 12},
    },
    "riscos": {
        "escalaAtiva": "timenow",
        "escalas": {
            "timenow": {
                "nome": "Timenow (4 faixas)",
                "faixas": [
                    {"id": "baixo", "nome": "Baixo", "minimo": 1},
                    {"id": "moderado", "nome": "Moderado", "minimo": 5},
                    {"id": "alto", "nome": "Alto", "minimo": 10},
                    {"id": "critico", "nome": "Crítico", "minimo": 15},
                ],
                "riscoVidaEhAlto": False,
            },
            "cipm": {
                "nome": "CIPM ArcelorMittal (3 faixas)",
                "faixas": [
                    {"id": "baixo", "nome": "Baixo", "minimo": 1},
                    {"id": "moderado", "nome": "Moderado", "minimo": 8},
                    {"id": "alto", "nome": "Alto", "minimo": 16},
                ],
                "riscoVidaEhAlto": True,
            },
        },
        "cadenciaDias": {"critico": 15, "alto": 30, "moderado": 60, "baixo": 90},
        "probabilidades": [
            {"nivel": 1, "nome": "Muito baixa", "faixa": "até 10%", "mediaPct": 5},
            {"nivel": 2, "nome": "Baixa", "faixa": "10 a 30%", "mediaPct": 20},
            {"nivel": 3, "nome": "Média", "faixa": "30 a 50%", "mediaPct": 40},
            {"nivel": 4, "nome": "Alta", "faixa": "50 a 70%", "mediaPct": 60},
            {"nivel": 5, "nome": "Muito alta", "faixa": "acima de 70%", "mediaPct": 85},
        ],
        "impactos": ["Muito baixo", "Baixo", "Moderado", "Alto", "Muito alto"],
        "pautaDiasAntesDoPrazo": 30,
        "revisaoAlertaDias": 15,
    },
    "financeiro": {
        "faixasDesvio": [1, 5, 10],
        "contingencia": {"toleranciaConsumoPP": 10, "coberturaMinimaPct": 100},
    },
    "suprimentos": {
        "propostasMinimas": 3,
        "folgaAlertaDias": 7,
        "alcadas": [
            {"ate": 50000000, "papel": "Gerente de suprimentos"},
            {"ate": 500000000, "papel": "Gerente do projeto"},
            {"ate": None, "papel": "Comitê de investimentos"},
        ],
        "pesosMarcos": {
            "requisicao": 5,
            "rfx": 5,
            "propostas": 5,
            "eqTecnica": 5,
            "eqComercial": 5,
            "adjudicacao": 5,
            "pedido": 10,
            "documentos": 10,
            "fabricacao": 30,
            "inspecao": 10,
            "embarque": 5,
            "entrega": 5,
        },
    },
    "punch": {"agingFaixas": [7, 30]},
    "mudancas": {
        "alcadaGerentePctOrcamento": 1,
        "prazoAnaliseDias": 10,
        "quorumComite": 3,
        "prazoAcoesDias": 15,
        "ratificacaoDias": 7,
    },
    "licoes": {"alertaSemRegistroDias": 90},
    "produtividade": {
        "jornadaDiariaHoras": 8.8,
        "metaTrabalhandoPct": 60,
        "metaUtilizacaoPct": 75,
        "aderenciaFaixas": [75, 90],
        "pfFaixas": [1.0, 1.1],
        "semanasMedia": 4,
        "spiFaixas": [0.85, 0.95],
        "atrasoInicioFaixasMin": [15, 30],
    },
    "eap": {
        "faixasDesvioPP": [2, 5],
        "pesoMaximoPacotePct": 10,
        "estimadoMaximoPct": 5,
        "modelosEtapas": [
            {
                "id": "engenharia",
                "nome": "Engenharia (documentos)",
                "etapas": [
                    {"nome": "Elaboração", "peso": 40},
                    {"nome": "Emissão para comentários", "peso": 30},
                    {"nome": "Emissão para construção", "peso": 30},
                ],
            },
            {
                "id": "suprimentos",
                "nome": "Suprimentos (equipamentos e materiais)",
                "etapas": [
                    {"nome": "Pedido emitido", "peso": 10},
                    {"nome": "Documentos do fornecedor aprovados", "peso": 15},
                    {"nome": "Fabricação", "peso": 45},
                    {"nome": "Inspeção e FAT", "peso": 10},
                    {"nome": "Entrega na obra", "peso": 20},
                ],
            },
            {
                "id": "montagem",
                "nome": "Montagem de equipamentos",
                "etapas": [
                    {"nome": "Posicionamento", "peso": 30},
                    {"nome": "Nivelamento e alinhamento", "peso": 40},
                    {"nome": "Grauteamento", "peso": 15},
                    {"nome": "Checklist de liberação", "peso": 15},
                ],
            },
            {
                "id": "paineis",
                "nome": "Montagem de painéis",
                "etapas": [
                    {"nome": "Posicionamento", "peso": 30},
                    {"nome": "Fixação e aterramento", "peso": 30},
                    {"nome": "Conexões", "peso": 25},
                    {"nome": "Checklist de liberação", "peso": 15},
                ],
            },
            {
                "id": "comissionamento",
                "nome": "Comissionamento",
                "etapas": [
                    {"nome": "Inspeções e testes", "peso": 70},
                    {"nome": "Certificado emitido", "peso": 30},
                ],
            },
        ],
    },
    "qualidade": {
        "prazoTratamentoDias": {"critica": 15, "maior": 30, "menor": 45},
        "verificacaoEficaciaDias": 30,
        "metaAprovacaoInspecaoPct": 95,
        "metaConformidadeAuditoriaPct": 90,
        "notificacaoClienteHoras": 48,
    },
    "portfolio": {
        "criterios": [
            {
                "id": "valor",
                "nome": "Valor financeiro (orçamento vigente)",
                "peso": 60,
                "fonte": "orcamento",
            },
            {"id": "estrategico", "nome": "Criticidade estratégica", "peso": 25, "fonte": "nota"},
            {
                "id": "complexidade",
                "nome": "Complexidade e exposição a risco",
                "peso": 15,
                "fonte": "nota",
            },
        ],
        "notaMinima": 1,
        "notaMaxima": 5,
    },
    "anexos": {
        "tamanhoMaximoMb": 25,
        "tiposAceitos": ["PDF", "JPG", "PNG", "DOCX", "XLSX", "PPTX", "DWG", "ZIP"],
    },
}

PARAMETER_GROUPS: tuple[str, ...] = tuple(INITIAL_PARAMETERS)


# ── Leitura ──────────────────────────────────────────────────────────────


def current_version(
    session: Session, *, group: str, reference_date: date
) -> ParameterVersion | None:
    """The version of the group in force on the date, or ``None`` before the first."""
    statement = (
        select(ParameterVersion)
        .where(
            ParameterVersion.group == group,
            ParameterVersion.effective_from <= reference_date,
        )
        .order_by(ParameterVersion.effective_from.desc(), ParameterVersion.version.desc())
        .limit(1)
    )
    return session.scalars(statement).first()


def current_versions(session: Session, *, reference_date: date) -> dict[str, ParameterVersion]:
    """The version in force on the date for every group that has one, keyed by group."""
    statement = (
        select(ParameterVersion)
        .where(ParameterVersion.effective_from <= reference_date)
        .order_by(
            ParameterVersion.group,
            ParameterVersion.effective_from.desc(),
            ParameterVersion.version.desc(),
        )
    )
    versions: dict[str, ParameterVersion] = {}
    for row in session.scalars(statement).all():
        versions.setdefault(row.group, row)
    return versions


def parameter_values(session: Session, version: ParameterVersion) -> dict[str, Any]:
    """The values of a version, rebuilt in the shape of the seeded payload."""
    statement = (
        select(ParameterValue)
        .where(ParameterValue.version_id == version.id)
        .order_by(ParameterValue.order)
    )
    return _restore(session.scalars(statement).all())


def current_group(session: Session, *, group: str, reference_date: date) -> dict[str, Any]:
    """The values of the group in force on the date, empty when there is no version."""
    version = current_version(session, group=group, reference_date=reference_date)
    return parameter_values(session, version) if version is not None else {}


def current_parameters(session: Session, *, reference_date: date) -> dict[str, dict[str, Any]]:
    """The values of every group in force on the date, keyed by group."""
    versions = current_versions(session, reference_date=reference_date)
    if not versions:
        return {}
    statement = (
        select(ParameterValue)
        .where(ParameterValue.version_id.in_([version.id for version in versions.values()]))
        .order_by(ParameterValue.order)
    )
    rows_by_version: dict[int, list[ParameterValue]] = {}
    for row in session.scalars(statement).all():
        rows_by_version.setdefault(row.version_id, []).append(row)
    return {
        group: _restore(rows_by_version.get(version.id, [])) for group, version in versions.items()
    }


@dataclass(frozen=True)
class ProjectSummary:
    """The fields of a project that other modules and the shell may read: identity and label."""

    id: int
    code: str
    name: str


def list_projects(session: Session) -> list[ProjectSummary]:
    """Every project of the portfolio, ordered by code: the list of the scope selector (D8).

    The register belongs to Configurações (D5), so the platform layer that
    resolves the scope and the shell that renders the selector read it here
    and never the table.
    """
    statement = select(Project.id, Project.code, Project.name).order_by(Project.code)
    return [
        ProjectSummary(id=row.id, code=row.code, name=row.name)
        for row in session.execute(statement)
    ]


# ── Gravação ─────────────────────────────────────────────────────────────


def seed_initial_parameters(
    session: Session, *, author_id: int, effective_from: date
) -> list[ParameterVersion]:
    """Create version 1 of every group that has none; idempotent by design.

    Called by the demonstration load and by production start-up (D6, D15);
    running it again finds every group already versioned and creates nothing.
    """
    created: list[ParameterVersion] = []
    for group, values in INITIAL_PARAMETERS.items():
        if _has_version(session, group):
            continue
        created.append(
            _create_version(
                session,
                author_id=author_id,
                group=group,
                values=values,
                effective_from=effective_from,
                justification=INITIAL_JUSTIFICATION,
            )
        )
    return created


def save_parameter_group(
    session: Session,
    *,
    author_id: int,
    group: str,
    values: Mapping[str, Any],
    effective_from: date,
    justification: str,
) -> ParameterVersion:
    """Validate and create the next version of one group, in the caller's transaction.

    The justification is mandatory (at least 10 characters, as the prototype
    required) and the values pass the rules of section 7.4 before anything is
    written; a validation failure raises 422 with one message per field.
    """
    if group not in INITIAL_PARAMETERS:
        raise InvalidDataError({"grupo": "Grupo de parâmetros desconhecido."})
    text = (justification or "").strip()
    if len(text) < 10:
        raise InvalidDataError(
            {"justificativa": "Informe a justificativa da alteração (mínimo de 10 caracteres)."}
        )
    errors = validation.validate_parameter_group(group, values)
    if errors:
        raise InvalidDataError(errors)
    return _create_version(
        session,
        author_id=author_id,
        group=group,
        values=values,
        effective_from=effective_from,
        justification=text,
    )


def _create_version(
    session: Session,
    *,
    author_id: int,
    group: str,
    values: Mapping[str, Any],
    effective_from: date,
    justification: str,
) -> ParameterVersion:
    version = ParameterVersion(
        author_id=author_id,
        group=group,
        version=_next_version(session, group),
        effective_from=effective_from,
        justification=justification,
    )
    recording.create(session, user_id=author_id, record=version)
    for order, (key, value_type, value) in enumerate(_flatten(values)):
        session.add(
            ParameterValue(
                version_id=version.id,
                key=key,
                order=order,
                value_type=value_type,
                value=value,
            )
        )
    session.flush()
    return version


def _has_version(session: Session, group: str) -> bool:
    statement = select(ParameterVersion.id).where(ParameterVersion.group == group).limit(1)
    return session.scalar(statement) is not None


def _next_version(session: Session, group: str) -> int:
    last = session.scalar(
        select(func.max(ParameterVersion.version)).where(ParameterVersion.group == group)
    )
    return (last or 0) + 1


# ── Serialização dos valores ─────────────────────────────────────────────
# A folha vira uma linha tipada; listas usam o índice no caminho
# (``riscos.probabilidades.0.mediaPct``) e a ordem da travessia no ``ordem``.


def _flatten(values: Mapping[str, Any], prefix: str = "") -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for key, value in values.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            rows.extend(_flatten(value, path))
        elif isinstance(value, list):
            rows.extend(_flatten_list(value, path))
        else:
            rows.append((path, *_encode(value)))
    return rows


def _flatten_list(items: Sequence[Any], path: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for index, item in enumerate(items):
        item_path = f"{path}.{index}"
        if isinstance(item, Mapping):
            rows.extend(_flatten(item, item_path))
        else:
            rows.append((item_path, *_encode(item)))
    return rows


def _encode(value: Any) -> tuple[str, str]:
    if value is None:
        return ("nulo", "")
    if isinstance(value, bool):
        return ("booleano", "true" if value else "false")
    if isinstance(value, int):
        return ("inteiro", str(value))
    if isinstance(value, float):
        return ("decimal", repr(value))
    return ("texto", str(value))


def _decode(value_type: str, value: str) -> Any:
    if value_type == "booleano":
        return value == "true"
    if value_type == "inteiro":
        return int(value)
    if value_type == "decimal":
        return float(value)
    if value_type == "nulo":
        return None
    return value


def _restore(rows: Sequence[ParameterValue]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for row in rows:
        _place(values, row.key.split("."), _decode(row.value_type, row.value))
    return values


def _place(container: Any, segments: Sequence[str], value: Any) -> None:
    head, rest = segments[0], segments[1:]
    if not rest:
        if isinstance(container, list):
            _grow(container, int(head), value)
        else:
            container[head] = value
        return
    next_head = rest[0]
    if head.isdigit():
        index = int(head)
        child = container[index] if index < len(container) else None
        if child is None:
            child = [] if next_head.isdigit() else {}
            _grow(container, index, child)
        _place(child, rest, value)
    else:
        child = container.get(head)
        if child is None:
            child = [] if next_head.isdigit() else {}
            container[head] = child
        _place(child, rest, value)


def _grow(container: list[Any], index: int, child: Any) -> None:
    while len(container) <= index:
        container.append(None)
    container[index] = child
