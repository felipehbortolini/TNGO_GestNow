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

import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core import audit, rbac, recording
from src.core.errors import InvalidDataError
from src.core.models import Client
from src.modulos.configuracoes import forms, validation
from src.modulos.configuracoes.models import (
    Collaborator,
    CollaboratorScheduleRole,
    Company,
    Discipline,
    Location,
    ParameterValue,
    ParameterVersion,
    Person,
    PortfolioWeight,
    Project,
    Unit,
)

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
        "metaAderenciaPct": 90,
        "metaOtdPct": 90,
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
    """The fields of a project that other modules and the shell may read: identity and label.

    ``start_date`` is the start of the project, which the period screens read to bound the
    periods (the first one is the period of that date); it is ``None`` when none was registered.
    """

    id: int
    code: str
    name: str
    manager_id: int | None = None
    budget_cents: int | None = None
    start_date: date | None = None
    expected_end_date: date | None = None


def list_projects(session: Session) -> list[ProjectSummary]:
    """Every project of the portfolio, ordered by code: the list of the scope selector (D8).

    The register belongs to Configurações (D5), so the platform layer that
    resolves the scope and the shell that renders the selector read it here
    and never the table.
    """
    statement = select(
        Project.id,
        Project.code,
        Project.name,
        Project.manager_id,
        Project.budget_cents,
        Project.start_date,
        Project.expected_end_date,
    ).order_by(Project.code)
    return [
        ProjectSummary(
            id=row.id,
            code=row.code,
            name=row.name,
            manager_id=row.manager_id,
            budget_cents=row.budget_cents,
            start_date=row.start_date,
            expected_end_date=row.expected_end_date,
        )
        for row in session.execute(statement)
    ]


@dataclass
class ProjectDetail:
    """The fields of a project that other modules read: numbering patterns, budget and manager.

    Not frozen on purpose: ``core.numbering.NumberedProject`` declares writable attributes, and a frozen
    dataclass does not satisfy that protocol.
    """

    id: int
    code: str
    name: str
    ata_pattern: str | None
    risk_pattern: str | None
    punch_pattern: str | None
    budget_cents: int | None
    manager_person_id: int


def find_project(session: Session, project_id: int) -> ProjectDetail | None:
    """The project with the id, or ``None``: what numbering and the budget readers need."""
    project = session.get(Project, project_id)
    return _project_detail(project) if project is not None else None


def list_project_details(session: Session) -> list[ProjectDetail]:
    """Every project with its patterns and budget, ordered by code."""
    statement = select(Project).order_by(Project.code)
    return [_project_detail(project) for project in session.scalars(statement)]


def _project_detail(project: Project) -> ProjectDetail:
    return ProjectDetail(
        id=project.id,
        code=project.code,
        name=project.name,
        ata_pattern=project.ata_pattern,
        risk_pattern=project.risk_pattern,
        punch_pattern=project.punch_pattern,
        budget_cents=project.budget_cents,
        manager_person_id=project.manager_id,
    )


@dataclass(frozen=True)
class ProjectRiskContext:
    """What the risk register prints about a project: client, numbering pattern and appetite."""

    id: int
    code: str
    name: str
    client_acronym: str
    risk_pattern: str | None
    risk_appetite: str | None


def list_project_risk_contexts(session: Session) -> list[ProjectRiskContext]:
    """Every project with the client acronym, the risk numbering pattern and the risk appetite."""
    statement = (
        select(Project, Client.acronym, Client.name)
        .join(Client, Client.id == Project.client_id)
        .order_by(Project.code)
    )
    return [
        ProjectRiskContext(
            id=project.id,
            code=project.code,
            name=project.name,
            client_acronym=acronym or client_name,
            risk_pattern=project.risk_pattern,
            risk_appetite=project.risk_appetite,
        )
        for project, acronym, client_name in session.execute(statement)
    ]


def person_names(session: Session, person_ids: Iterable[int]) -> dict[int, str]:
    """The names of the people of the register, by id; an unknown id is left out."""
    wanted = {person_id for person_id in person_ids if person_id is not None}
    if not wanted:
        return {}
    statement = select(Person.id, Person.name).where(Person.id.in_(wanted))
    return {row.id: row.name for row in session.execute(statement)}


def find_person_id_by_email(session: Session, email: str) -> int | None:
    """The id of the person with the e-mail (compared without case), or ``None``."""
    statement = select(Person.id).where(func.lower(Person.email) == email.strip().lower())
    return session.scalars(statement).first()


@dataclass(frozen=True)
class PersonSummary:
    """The fields of a person that other modules may read: identity and name."""

    id: int
    name: str
    email: str = ""


def list_people(session: Session) -> list[PersonSummary]:
    """Every person of the register, ordered by name: the options of a responsible field."""
    statement = select(Person.id, Person.name, Person.email).order_by(Person.name, Person.id)
    return [
        PersonSummary(id=row.id, name=row.name, email=row.email)
        for row in session.execute(statement)
    ]


@dataclass(frozen=True)
class MeasureUnitSummary:
    """A unit of measure of the register: identity and the code the screens print (``m²``)."""

    id: int
    code: str
    name: str


def list_measure_units(session: Session) -> list[MeasureUnitSummary]:
    """The units of measure of the register, ordered by code."""
    statement = (
        select(Unit.id, Unit.code, Unit.name).where(Unit.kind == "medida").order_by(Unit.code)
    )
    return [
        MeasureUnitSummary(id=row.id, code=row.code, name=row.name)
        for row in session.execute(statement)
    ]


def portfolio_grades(session: Session, *, reference_date: date) -> dict[int, dict[str, int]]:
    """The grades (1 to 5) of each project by criterion, in the portfolio version in force.

    Keyed by project id, then by criterion id (``estrategico``, ``complexidade``). The grades
    live inside the version of the ``portfolio`` group (D8), so a new version of the weighting
    brings its own grades; before the first version there are none.
    """
    version = current_version(session, group="portfolio", reference_date=reference_date)
    if version is None:
        return {}
    statement = select(
        PortfolioWeight.project_id, PortfolioWeight.criterion, PortfolioWeight.grade
    ).where(PortfolioWeight.version_id == version.id)
    grades: dict[int, dict[str, int]] = {}
    for row in session.execute(statement):
        grades.setdefault(row.project_id, {})[row.criterion] = row.grade
    return grades


def find_people(session: Session, ids: Collection[int]) -> dict[int, PersonSummary]:
    """The people with the ids, by id; an id with no person is simply absent from the answer."""
    if not ids:
        return {}
    statement = select(Person.id, Person.name, Person.email).where(Person.id.in_(set(ids)))
    return {
        row.id: PersonSummary(id=row.id, name=row.name, email=row.email)
        for row in session.execute(statement)
    }


@dataclass(frozen=True)
class CollaboratorAccess:
    """What the access gate reads of a collaborator: who, profile, bond, company and roles (D7).

    Plain values, as the register keeps them: the platform (``core.auth``)
    turns the texts into its profile, bond and role types and refuses a value
    it does not know. ``schedule_roles`` holds one ``(project_id, role)`` pair
    per role given in the Programação Semanal.
    """

    id: int
    person_id: int
    name: str
    email: str
    general_profile: str
    bond: str
    company_id: int | None
    active: bool
    schedule_roles: tuple[tuple[int, str], ...] = ()


def find_access_by_email(session: Session, email: str) -> CollaboratorAccess | None:
    """The collaborator of an e-mail, active or not, or ``None`` outside the register.

    The register is the source of truth of who enters (D7); the e-mail is
    compared without regard to case, because the Microsoft account and the
    register may spell it differently.
    """
    found = _access_rows(session, func.lower(Person.email) == email.strip().lower())
    return found[0] if found else None


def find_access(session: Session, collaborator_id: int) -> CollaboratorAccess | None:
    """The collaborator with the id, active or not, or ``None`` when there is none."""
    found = _access_rows(session, Collaborator.id == collaborator_id)
    return found[0] if found else None


def list_active_access(session: Session) -> list[CollaboratorAccess]:
    """Every active collaborator, by id: the people the demonstration selector offers."""
    return _access_rows(session, Collaborator.active.is_(True))


def _access_rows(session: Session, condition: Any) -> list[CollaboratorAccess]:
    """The collaborators that meet the condition, with their person, by id.

    One query for the people and one for all their roles, so a list of
    collaborators costs two queries and not one per person.
    """
    statement = (
        select(Collaborator, Person)
        .join(Person, Person.id == Collaborator.person_id)
        .where(condition)
        .order_by(Collaborator.id)
    )
    rows = session.execute(statement).all()
    roles = _schedule_roles_by_collaborator(session, [row.Collaborator.id for row in rows])
    return [
        CollaboratorAccess(
            id=row.Collaborator.id,
            person_id=row.Person.id,
            name=row.Person.name,
            email=row.Person.email,
            general_profile=row.Collaborator.general_profile,
            bond=row.Collaborator.bond,
            company_id=row.Collaborator.company_id,
            active=row.Collaborator.active,
            schedule_roles=roles.get(row.Collaborator.id, ()),
        )
        for row in rows
    ]


def _schedule_roles_by_collaborator(
    session: Session, collaborator_ids: Sequence[int]
) -> dict[int, tuple[tuple[int, str], ...]]:
    if not collaborator_ids:
        return {}
    statement = (
        select(
            CollaboratorScheduleRole.collaborator_id,
            CollaboratorScheduleRole.project_id,
            CollaboratorScheduleRole.role,
        )
        .where(CollaboratorScheduleRole.collaborator_id.in_(collaborator_ids))
        .order_by(
            CollaboratorScheduleRole.collaborator_id,
            CollaboratorScheduleRole.project_id,
            CollaboratorScheduleRole.role,
        )
    )
    grouped: dict[int, list[tuple[int, str]]] = {}
    for row in session.execute(statement):
        grouped.setdefault(row.collaborator_id, []).append((row.project_id, row.role))
    return {collaborator_id: tuple(pairs) for collaborator_id, pairs in grouped.items()}


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


# ── Tela de Parâmetros (ISSUE-076) ───────────────────────────────────────
#
# A leitura que a tela e o histórico consomem: os grupos da tela (``forms``)
# com os valores vigentes, a versão vigente de cada grupo de origem com autor,
# vigência e justificativa, e as alterações de cada versão contra a anterior do
# MESMO grupo (o GestNow versiona por grupo; o protótipo versionava o conjunto).
# O filtro da tela (busca e módulo) é do servidor: o fragmento é pedido de novo
# pela query.


@dataclass(frozen=True)
class ParameterRow:
    """Uma linha da tabela de um grupo: o rótulo do campo e o valor vigente já escrito."""

    rotulo: str
    valor: str


@dataclass(frozen=True)
class GroupVersion:
    """A versão vigente de um grupo de parâmetros como a tela a lê."""

    group: str
    version: int
    effective_from: date
    author_name: str
    justification: str


@dataclass(frozen=True)
class GroupView:
    """Um grupo da tela: os metadados, as linhas vigentes e as versões dos grupos de origem."""

    form: forms.ParameterGroupForm
    rows: tuple[ParameterRow, ...]
    versions: tuple[GroupVersion, ...]

    @property
    def current(self) -> GroupVersion | None:
        """A versão mais recente entre os grupos de origem: a manchete do grupo."""
        return self.versions[0] if self.versions else None

    @property
    def source_count(self) -> int:
        return len(self.versions)


@dataclass(frozen=True)
class ParameterOverview:
    """O que a tela mostra: os grupos filtrados, a versão mais recente e a contagem de versões."""

    groups: tuple[GroupView, ...]
    latest: GroupVersion | None
    previous_versions: int
    total_versions: int


@dataclass(frozen=True)
class VersionChange:
    """Uma alteração de uma versão: o grupo, o parâmetro e o antes e o depois já escritos."""

    grupo: str
    parametro: str
    de: str
    para: str


@dataclass(frozen=True)
class HistoryEntry:
    """Uma versão no histórico: identificação, autor, justificativa, alterações e se é a vigente."""

    group: str
    group_name: str
    version: int
    effective_from: date
    author_name: str
    justification: str
    current: bool
    changes: tuple[VersionChange, ...]


def parameter_overview(
    session: Session, *, reference_date: date, search: str = "", module: str = ""
) -> ParameterOverview:
    """Os grupos da tela com os valores vigentes, já filtrados pela busca e pelo módulo."""
    values = current_parameters(session, reference_date=reference_date)
    versions = current_versions(session, reference_date=reference_date)
    names = _author_names(session, [version.author_id for version in versions.values()])
    todas = [_group_version(version, names) for version in versions.values()]
    latest = max(todas, key=_version_order) if todas else None
    groups: list[GroupView] = []
    for group_form in forms.group_forms(values):
        if module and group_form.modulo != module:
            continue
        visible = [field for field in group_form.campos if forms.matches(group_form, field, search)]
        if not visible:
            continue
        group_versions = tuple(
            _group_version(versions[group], names)
            for group in forms.group_sources(group_form.id)
            if group in versions
        )
        rows = tuple(
            ParameterRow(
                rotulo=field.rotulo,
                valor=forms.exibir(field, forms.value_at(values, field.caminho)),
            )
            for field in visible
        )
        groups.append(GroupView(form=group_form, rows=rows, versions=_latest_first(group_versions)))
    total = session.scalar(select(func.count()).select_from(ParameterVersion)) or 0
    return ParameterOverview(
        groups=tuple(groups),
        latest=latest,
        previous_versions=max(total - len(versions), 0),
        total_versions=total,
    )


def parameter_history(
    session: Session, *, reference_date: date, group: str | None = None
) -> tuple[HistoryEntry, ...]:
    """As versões registradas, da mais recente para a mais antiga, com o antes e o depois.

    As alterações de cada versão comparam com a versão anterior do MESMO grupo,
    como o GestNow versiona (o protótipo versionava o conjunto inteiro); a
    primeira versão de cada grupo não tem alterações.
    """
    statement = select(ParameterVersion).order_by(
        ParameterVersion.effective_from.desc(),
        ParameterVersion.version.desc(),
        ParameterVersion.group,
    )
    if group is not None:
        statement = statement.where(ParameterVersion.group == group)
    versions = list(session.scalars(statement).all())
    if not versions:
        return ()
    by_key = {(version.group, version.version): version for version in versions}
    rows_by_version = _values_by_version(session, [version.id for version in versions])
    current_ids = {
        version.id for version in current_versions(session, reference_date=reference_date).values()
    }
    names = _author_names(session, [version.author_id for version in versions])
    labels_by_path = forms.labels(current_parameters(session, reference_date=reference_date))
    entries: list[HistoryEntry] = []
    for version in versions:
        previous = by_key.get((version.group, version.version - 1))
        changes = (
            ()
            if previous is None
            else _changes(
                {version.group: _restore(rows_by_version.get(previous.id, []))},
                {version.group: _restore(rows_by_version.get(version.id, []))},
                labels_by_path,
            )
        )
        entries.append(
            HistoryEntry(
                group=version.group,
                group_name=_screen_group_name(version.group),
                version=version.version,
                effective_from=version.effective_from,
                author_name=names.get(version.author_id, ""),
                justification=version.justification,
                current=version.id in current_ids,
                changes=changes,
            )
        )
    return tuple(entries)


def _group_version(version: ParameterVersion, names: Mapping[int, str]) -> GroupVersion:
    return GroupVersion(
        group=version.group,
        version=version.version,
        effective_from=version.effective_from,
        author_name=names.get(version.author_id, ""),
        justification=version.justification,
    )


def _version_order(version: GroupVersion) -> tuple[date, int]:
    return (version.effective_from, version.version)


def _latest_first(versions: tuple[GroupVersion, ...]) -> tuple[GroupVersion, ...]:
    return tuple(sorted(versions, key=_version_order, reverse=True))


def _screen_group_name(group: str) -> str:
    screen = forms.SCREEN_GROUP_OF.get(group)
    return forms.GROUP_NAMES[screen] if screen is not None else group


def _author_names(session: Session, author_ids: Iterable[int]) -> dict[int, str]:
    """O nome do colaborador de cada id de autor: o que a tela e o histórico imprimem."""
    wanted = {author_id for author_id in author_ids if author_id is not None}
    if not wanted:
        return {}
    statement = (
        select(Collaborator.id, Person.name)
        .join(Person, Person.id == Collaborator.person_id)
        .where(Collaborator.id.in_(wanted))
    )
    return {row.id: row.name for row in session.execute(statement)}


def _values_by_version(
    session: Session, version_ids: Sequence[int]
) -> dict[int, list[ParameterValue]]:
    statement = (
        select(ParameterValue)
        .where(ParameterValue.version_id.in_(version_ids))
        .order_by(ParameterValue.order)
    )
    grouped: dict[int, list[ParameterValue]] = {}
    for row in session.scalars(statement).all():
        grouped.setdefault(row.version_id, []).append(row)
    return grouped


def _changes(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    labels_by_path: Mapping[str, forms.FieldLabel],
) -> tuple[VersionChange, ...]:
    """As alterações entre duas versões, na ordem das folhas, pelo rótulo do campo."""
    before_leaves = forms.leaf_values(before)
    after_leaves = forms.leaf_values(after)
    changes: list[VersionChange] = []
    for path in dict.fromkeys([*before_leaves, *after_leaves]):
        old = before_leaves.get(path)
        new = after_leaves.get(path)
        if forms.same_value(old, new):
            continue
        label = labels_by_path.get(path)
        changes.append(
            VersionChange(
                grupo=label.grupo if label is not None else "Outros",
                parametro=label.rotulo if label is not None else path,
                de=forms.exibir(label.campo, old) if label is not None else _plain(old),
                para=forms.exibir(label.campo, new) if label is not None else _plain(new),
            )
        )
    return tuple(changes)


def _plain(value: Any) -> str:
    return "·" if value is None or value == "" else str(value)


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


@dataclass(frozen=True)
class RegisterOption:
    """An entry of a register as a list shows it: the id a form sends and the name a person reads."""

    id: int
    name: str


def list_company_options(session: Session) -> list[RegisterOption]:
    """Every company of the register, by name: what a company selector offers."""
    statement = select(Company.id, Company.name).order_by(Company.name, Company.id)
    return [RegisterOption(id=row.id, name=row.name) for row in session.execute(statement)]


def list_person_options(session: Session) -> list[RegisterOption]:
    """Every person of the register, by name: what a responsible selector offers."""
    statement = select(Person.id, Person.name).order_by(Person.name, Person.id)
    return [RegisterOption(id=row.id, name=row.name) for row in session.execute(statement)]


def list_discipline_names(session: Session) -> list[str]:
    """The disciplines of the register, by name."""
    return list(session.scalars(select(Discipline.name).order_by(Discipline.name)))


def discipline_names_by_id(session: Session) -> dict[int, str]:
    """The disciplines of the register: the name of each, by id (what a lesson points to)."""
    statement = select(Discipline.id, Discipline.name).order_by(Discipline.name)
    return {row.id: row.name for row in session.execute(statement)}


# ── Register writes for the demonstration load of other modules (ISSUE-051) ──
#
# The Weekly Scheduling demonstration brings its own companies, locations, units and
# people. Configurações owns those tables, so the load asks for them here: each
# ``ensure_*`` finds the row and creates it (with the trail) only when it is missing.


@dataclass(frozen=True)
class CompanySummary:
    """Uma empresa do cadastro com o tipo: o que o seletor de fornecedores lê (ISSUE-057)."""

    id: int
    name: str
    kind: str | None


def list_company_summaries(session: Session) -> list[CompanySummary]:
    """Todas as empresas do cadastro, por nome: o universo da tela de fornecedores."""
    statement = select(Company.id, Company.name, Company.kind).order_by(Company.name, Company.id)
    return [
        CompanySummary(id=row.id, name=row.name, kind=row.kind)
        for row in session.execute(statement)
    ]


def find_company_id_by_name(session: Session, name: str) -> int | None:
    """O id da empresa com este nome, sem diferença de maiúsculas, ou ``None`` (nome livre)."""
    wanted = name.strip().casefold()
    statement = select(Company.id, Company.name)
    for row in session.execute(statement):
        if row.name.strip().casefold() == wanted:
            return row.id
    return None


def create_company(session: Session, *, author_id: int, name: str, kind: str) -> Company:
    """Grava a empresa do cadastro, com a trilha e o controle de versão (dono: este módulo)."""
    return recording.create(
        session, user_id=author_id, record=Company(name=name.strip(), kind=kind)
    )


def find_project_id(session: Session, code: str) -> int | None:
    """The id of the project with the code, or ``None``."""
    return session.scalar(select(Project.id).where(Project.code == code))


def ensure_company(session: Session, *, author_id: int, name: str, kind: str) -> int:
    """The id of the company with the name; created, with the trail, when missing."""
    found = session.scalar(select(Company.id).where(Company.name == name))
    if found is not None:
        return found
    return recording.create(session, user_id=author_id, record=Company(name=name, kind=kind)).id


def ensure_measure_unit(session: Session, *, author_id: int, code: str, name: str) -> int:
    """The id of the unit of measure with the code; created when missing."""
    found = session.scalar(select(Unit.id).where(Unit.kind == "medida", Unit.code == code))
    if found is not None:
        return found
    unit = Unit(kind="medida", code=code, name=name)
    return recording.create(session, user_id=author_id, record=unit).id


def ensure_location(session: Session, *, author_id: int, project_id: int, name: str) -> int:
    """The id of the location of the project with the name; created when missing."""
    found = session.scalar(
        select(Location.id).where(Location.project_id == project_id, Location.name == name)
    )
    if found is not None:
        return found
    location = Location(project_id=project_id, code=name, name=name)
    return recording.create(session, user_id=author_id, record=location).id


def ensure_collaborator(
    session: Session,
    *,
    author_id: int,
    name: str,
    email: str,
    role: str,
    company_id: int | None,
    profile: str,
    bond: str,
) -> tuple[int, int]:
    """The ``(person id, collaborator id)`` of the e-mail; both created when missing."""
    person_id = session.scalar(select(Person.id).where(func.lower(Person.email) == email.lower()))
    if person_id is None:
        person = Person(name=name, role=role, email=email, company_id=company_id)
        person_id = recording.create(session, user_id=author_id, record=person).id
    collaborator_id = session.scalar(
        select(Collaborator.id).where(Collaborator.person_id == person_id)
    )
    if collaborator_id is None:
        collaborator = Collaborator(
            person_id=person_id,
            company_id=company_id,
            general_profile=profile,
            bond=bond,
            active=True,
        )
        collaborator_id = recording.create(session, user_id=author_id, record=collaborator).id
    return person_id, collaborator_id


def grant_schedule_role(
    session: Session, *, collaborator_id: int, project_id: int, role: str
) -> None:
    """Give the collaborator a Weekly Scheduling role in the project, once."""
    given = session.scalar(
        select(CollaboratorScheduleRole.id).where(
            CollaboratorScheduleRole.collaborator_id == collaborator_id,
            CollaboratorScheduleRole.project_id == project_id,
            CollaboratorScheduleRole.role == role,
        )
    )
    if given is None:
        session.add(
            CollaboratorScheduleRole(
                collaborator_id=collaborator_id, project_id=project_id, role=role
            )
        )
        session.flush()


@dataclass(frozen=True)
class PersonDetail:
    """A person as an attendance list prints it: name, role, company and e-mail."""

    id: int
    name: str
    role: str | None
    company_id: int | None
    email: str


def find_person_details(session: Session, ids: Collection[int]) -> dict[int, PersonDetail]:
    """The people with the ids, with role and company, by id; an unknown id is left out."""
    if not ids:
        return {}
    statement = select(Person).where(Person.id.in_(set(ids)))
    return {person.id: _person_detail(person) for person in session.scalars(statement)}


def list_person_details(session: Session) -> list[PersonDetail]:
    """Every person of the register, by name, with role and company: what a guest search reads."""
    statement = select(Person).order_by(Person.name, Person.id)
    return [_person_detail(person) for person in session.scalars(statement)]


def _person_detail(person: Person) -> PersonDetail:
    return PersonDetail(
        id=person.id,
        name=person.name,
        role=person.role,
        company_id=person.company_id,
        email=person.email,
    )


def list_company_names(session: Session) -> dict[int, str]:
    """The name of every company of the register, by id."""
    return {option.id: option.name for option in list_company_options(session)}


ORGANIZATIONAL_UNIT_KIND = "organizacional"


def list_organizational_units(session: Session) -> list[RegisterOption]:
    """The organizational units of the register, by name: what a unit selector offers."""
    statement = (
        select(Unit.id, Unit.name)
        .where(Unit.kind == ORGANIZATIONAL_UNIT_KIND)
        .order_by(Unit.name, Unit.id)
    )
    return [RegisterOption(id=row.id, name=row.name) for row in session.execute(statement)]


# ── Tela de Colaboradores (ISSUE-077) ────────────────────────────────────
#
# A tela mantém quem entra e o que faz (D7): perfil geral, vínculo e empresa,
# e os papéis da Programação Semanal por projeto. O cadastro é a fonte de
# verdade do acesso — o gate (``core.auth``) o lê a cada requisição, então a
# mudança vale na requisição seguinte. O último Admin ativo não pode ser
# removido nem rebaixado.

PROFILE_OPTIONS: tuple[str, ...] = tuple(profile.value for profile in rbac.GeneralProfile)
BOND_OPTIONS: tuple[str, ...] = tuple(bond.value for bond in rbac.Bond)
SCHEDULE_ROLE_OPTIONS: tuple[str, ...] = tuple(role.value for role in rbac.ScheduleRole)

_PROFILES = frozenset(PROFILE_OPTIONS)
_BONDS = frozenset(BOND_OPTIONS)
_SCHEDULE_ROLES = frozenset(SCHEDULE_ROLE_OPTIONS)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

LAST_ADMIN_MESSAGE = "O último Admin não pode ser removido nem rebaixado."
EMAIL_TAKEN_MESSAGE = "Já existe um acesso com este e-mail."
EMAIL_OTHER_PERSON_MESSAGE = "Este e-mail já pertence a outra pessoa do cadastro."
COLLABORATOR_NOT_FOUND = "Colaborador fora do cadastro."
REVOKE_REFERENCED_MESSAGE = (
    "Este colaborador já tem registros no GestNow: suspenda o acesso em vez de revogar, "
    "para a trilha de auditoria não perder o autor."
)


@dataclass(frozen=True)
class ScheduleRoleLine:
    """Um papel da Programação Semanal de um colaborador: o projeto e o papel (D7)."""

    project_id: int
    project_code: str
    role: str

    @property
    def label(self) -> str:
        """``TN-001 · Fiscal``: como a lista e a exportação nomeiam o papel."""
        return f"{self.project_code} · {self.role}"


@dataclass(frozen=True)
class CollaboratorRow:
    """Um colaborador como a tela o lê: a pessoa, o acesso e os papéis por projeto."""

    collaborator_id: int
    person_id: int
    name: str
    email: str
    role: str | None
    company_id: int | None
    company_name: str | None
    general_profile: str
    bond: str
    active: bool
    schedule_roles: tuple[ScheduleRoleLine, ...] = ()


@dataclass(frozen=True)
class CollaboratorOverview:
    """O que a tela mostra: as linhas filtradas, a contagem por perfil e o total do cadastro."""

    rows: tuple[CollaboratorRow, ...]
    profile_counts: Mapping[str, int]
    total: int


def list_collaborators_overview(
    session: Session, *, search: str = "", profile: str = "", bond: str = ""
) -> CollaboratorOverview:
    """As linhas da tela, já filtradas; a contagem por perfil é a do universo completo (KPIs).

    A busca não diferencia maiúsculas de nome, e-mail, função e empresa; o
    perfil e o vínculo filtram pelo valor exato. Os KPIs contam o universo
    inteiro, como o app precedente: o filtro não muda a situação do cadastro.
    """
    rows = _all_collaborator_rows(session)
    counts: dict[str, int] = dict.fromkeys(PROFILE_OPTIONS, 0)
    for row in rows:
        if row.general_profile in counts:
            counts[row.general_profile] += 1
    visible = tuple(row for row in rows if _matches_filters(row, search, profile, bond))
    return CollaboratorOverview(rows=visible, profile_counts=counts, total=len(rows))


def find_collaborator(session: Session, collaborator_id: int) -> CollaboratorRow | None:
    """O colaborador com o id, com a empresa e os papéis: o que o modal de edição carrega."""
    statement = (
        select(Collaborator, Person, Company.name)
        .join(Person, Person.id == Collaborator.person_id)
        .outerjoin(Company, Company.id == Collaborator.company_id)
        .where(Collaborator.id == collaborator_id)
    )
    found = session.execute(statement).first()
    if found is None:
        return None
    colaborador, pessoa, empresa = found
    lines = _schedule_role_lines(session, [colaborador.id])
    return _collaborator_row(colaborador, pessoa, empresa, lines.get(colaborador.id, ()))


def _all_collaborator_rows(session: Session) -> list[CollaboratorRow]:
    statement = (
        select(Collaborator, Person, Company.name)
        .join(Person, Person.id == Collaborator.person_id)
        .outerjoin(Company, Company.id == Collaborator.company_id)
        .order_by(Person.name, Person.id)
    )
    rows = [tuple(row) for row in session.execute(statement)]
    lines = _schedule_role_lines(session, [row[0].id for row in rows])
    return [
        _collaborator_row(colaborador, pessoa, empresa, lines.get(colaborador.id, ()))
        for colaborador, pessoa, empresa in rows
    ]


def _collaborator_row(
    colaborador: Collaborator,
    pessoa: Person,
    company_name: str | None,
    schedule_roles: tuple[ScheduleRoleLine, ...],
) -> CollaboratorRow:
    return CollaboratorRow(
        collaborator_id=colaborador.id,
        person_id=pessoa.id,
        name=pessoa.name,
        email=pessoa.email,
        role=pessoa.role,
        company_id=colaborador.company_id,
        company_name=company_name,
        general_profile=colaborador.general_profile,
        bond=colaborador.bond,
        active=colaborador.active,
        schedule_roles=schedule_roles,
    )


def _schedule_role_lines(
    session: Session, collaborator_ids: Sequence[int]
) -> dict[int, tuple[ScheduleRoleLine, ...]]:
    """Os papéis dos colaboradores, por id, com o código do projeto e em ordem de código."""
    if not collaborator_ids:
        return {}
    statement = (
        select(
            CollaboratorScheduleRole.collaborator_id,
            CollaboratorScheduleRole.project_id,
            Project.code,
            CollaboratorScheduleRole.role,
        )
        .join(Project, Project.id == CollaboratorScheduleRole.project_id)
        .where(CollaboratorScheduleRole.collaborator_id.in_(collaborator_ids))
        .order_by(
            CollaboratorScheduleRole.collaborator_id,
            Project.code,
            CollaboratorScheduleRole.role,
        )
    )
    grouped: dict[int, list[ScheduleRoleLine]] = {}
    for row in session.execute(statement):
        grouped.setdefault(row.collaborator_id, []).append(
            ScheduleRoleLine(project_id=row.project_id, project_code=row.code, role=row.role)
        )
    return {collaborator_id: tuple(lines) for collaborator_id, lines in grouped.items()}


def _matches_filters(row: CollaboratorRow, search: str, profile: str, bond: str) -> bool:
    if profile and row.general_profile != profile:
        return False
    if bond and row.bond != bond:
        return False
    if not search:
        return True
    needle = search.casefold()
    values = (row.name, row.email, row.role or "", row.company_name or "")
    return any(needle in value.casefold() for value in values)


def save_collaborator(
    session: Session,
    *,
    author_id: int,
    collaborator_id: int | None,
    name: str,
    email: str,
    role: str,
    profile: str,
    bond: str,
    company_id: int | None,
    active: bool,
    roles: Sequence[tuple[int, str]],
) -> Collaborator:
    """Grava o acesso (novo ou existente), com a trilha, e substitui os papéis pelo enviado.

    As regras do D7: nome obrigatório; e-mail com formato, normalizado para
    minúsculas e único entre quem já tem acesso (o e-mail de uma pessoa sem
    acesso reusa a pessoa); perfil e vínculo do vocabulário; empresa
    obrigatória no vínculo Fornecedor e ignorada nos demais; projetos dos
    papéis existentes e papel do vocabulário, sem repetição. O último Admin
    ativo não pode ser desativado nem rebaixado. A falha de qualquer regra
    levanta ``InvalidDataError`` com a mensagem de cada campo.
    """
    current = session.get(Collaborator, collaborator_id) if collaborator_id is not None else None
    if collaborator_id is not None and current is None:
        raise InvalidDataError({"geral": COLLABORATOR_NOT_FOUND})
    name = name.strip()
    email = email.strip().lower()
    role = role.strip()
    errors = _collaborator_errors(
        session,
        current=current,
        name=name,
        email=email,
        profile=profile,
        bond=bond,
        company_id=company_id,
        active=active,
    )
    wanted = _wanted_schedule_roles(session, roles, errors)
    if errors:
        raise InvalidDataError(errors)
    if bond != rbac.Bond.SUPPLIER:
        company_id = None

    if current is None:
        person = _write_person(
            session,
            author_id=author_id,
            person_id=find_person_id_by_email(session, email) if email else None,
            name=name,
            email=email,
            role=role,
            company_id=company_id,
        )
        record = recording.create(
            session,
            user_id=author_id,
            record=Collaborator(
                person_id=person.id,
                company_id=company_id,
                general_profile=profile,
                bond=bond,
                active=active,
            ),
        )
    else:
        _write_person(
            session,
            author_id=author_id,
            person_id=current.person_id,
            name=name,
            email=email,
            role=role,
            company_id=company_id,
        )
        recording.update(
            session,
            user_id=author_id,
            record=current,
            changes={
                "general_profile": profile,
                "bond": bond,
                "company_id": company_id,
                "active": active,
            },
            version=current.version,
        )
        record = current
    _replace_schedule_roles(session, author_id=author_id, collaborator_id=record.id, wanted=wanted)
    session.flush()
    return record


def revoke_collaborator(session: Session, *, author_id: int, collaborator_id: int) -> None:
    """Apaga o acesso e os papéis, com a trilha; a pessoa permanece no cadastro de apoio.

    O último Admin ativo não é revogado: a recusa volta no campo geral, porque
    a revogação não tem campo. Quem dona das pessoas é o cadastro de apoio
    (ISSUE-078); revogar só tira o acesso, e o gate deixa de achar o e-mail na
    requisição seguinte. Quem já deixou trilha de auditoria (é autor de alguma
    gravação) não é apagado, porque a trilha perde o autor: a recusa orienta a
    suspender o acesso.
    """
    record = session.get(Collaborator, collaborator_id)
    if record is None:
        raise InvalidDataError({"geral": COLLABORATOR_NOT_FOUND})
    if _is_last_active_admin(session, record):
        raise InvalidDataError({"geral": LAST_ADMIN_MESSAGE})
    try:
        with session.begin_nested():
            for row in session.scalars(
                select(CollaboratorScheduleRole).where(
                    CollaboratorScheduleRole.collaborator_id == collaborator_id
                )
            ).all():
                before = audit.snapshot(row)
                session.delete(row)
                session.flush()
                audit.deleted(
                    session, user_id=author_id, entity=row.__tablename__, record=row, before=before
                )
            recording.delete(session, user_id=author_id, record=record, version=record.version)
    except IntegrityError:
        raise InvalidDataError({"geral": REVOKE_REFERENCED_MESSAGE}) from None


def _write_person(
    session: Session,
    *,
    author_id: int,
    person_id: int | None,
    name: str,
    email: str,
    role: str,
    company_id: int | None,
) -> Person:
    """A pessoa do cadastro: cria, ou atualiza nome, função e empresa, com a trilha.

    O e-mail não muda na edição (o formulário o bloqueia); na criação de um
    acesso para pessoa que já existia sem acesso, ele já é o mesmo que a
    tornou encontrada.
    """
    if person_id is None:
        return recording.create(
            session,
            user_id=author_id,
            record=Person(name=name, role=role or None, email=email, company_id=company_id),
        )
    person = session.get(Person, person_id)
    if person is None:
        raise InvalidDataError({"geral": "Pessoa fora do cadastro."})
    recording.update(
        session,
        user_id=author_id,
        record=person,
        changes={"name": name, "role": role or None, "company_id": company_id},
        version=person.version,
    )
    return person


def _wanted_schedule_roles(
    session: Session, roles: Sequence[tuple[int, str]], errors: dict[str, str]
) -> list[tuple[int, str]]:
    """Os pares (projeto, papel) válidos e sem repetição; preenche o erro do campo ``papeis``."""
    wanted: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()
    for project_id, papel in roles:
        pair = (project_id, papel)
        if pair in seen:
            continue
        seen.add(pair)
        if session.get(Project, project_id) is None:
            errors.setdefault("papeis", "Projeto fora do cadastro.")
            continue
        if papel not in _SCHEDULE_ROLES:
            errors.setdefault("papeis", "Escolha um papel da Programação Semanal.")
            continue
        wanted.append(pair)
    return wanted


def _collaborator_errors(
    session: Session,
    *,
    current: Collaborator | None,
    name: str,
    email: str,
    profile: str,
    bond: str,
    company_id: int | None,
    active: bool,
) -> dict[str, str]:
    """As regras do D7 por campo: o que a tela mostra sob o campo e no aviso do topo."""
    errors: dict[str, str] = {}
    if not name:
        errors["nome"] = "Informe o nome completo."
    if not _EMAIL.match(email):
        errors["email"] = "Informe um e-mail corporativo válido."
    if profile not in _PROFILES:
        errors["perfil"] = "Escolha um perfil."
    if bond not in _BONDS:
        errors["vinculo"] = "Escolha o vínculo."
    if bond == rbac.Bond.SUPPLIER:
        if company_id is None:
            errors["empresa"] = "Escolha a empresa da pessoa."
        elif session.get(Company, company_id) is None:
            errors["empresa"] = "Empresa fora do cadastro."
    _email_errors(session, current=current, email=email, errors=errors)
    _last_admin_errors(session, current=current, active=active, profile=profile, errors=errors)
    return errors


def _email_errors(
    session: Session,
    *,
    current: Collaborator | None,
    email: str,
    errors: dict[str, str],
) -> None:
    """O e-mail de outra pessoa: recusa se ela já tem acesso; reusa a pessoa quando não tem."""
    person_id = find_person_id_by_email(session, email) if email else None
    if person_id is None or (current is not None and person_id == current.person_id):
        return
    if _has_access(session, person_id):
        errors["email"] = EMAIL_TAKEN_MESSAGE
    elif current is not None:
        errors["email"] = EMAIL_OTHER_PERSON_MESSAGE


def _last_admin_errors(
    session: Session,
    *,
    current: Collaborator | None,
    active: bool,
    profile: str,
    errors: dict[str, str],
) -> None:
    """O último Admin ativo não pode ser desativado nem rebaixado."""
    if current is None or not _is_last_active_admin(session, current):
        return
    if not active:
        errors["ativo"] = LAST_ADMIN_MESSAGE
    elif profile != rbac.GeneralProfile.ADMIN:
        errors["perfil"] = LAST_ADMIN_MESSAGE


def _replace_schedule_roles(
    session: Session, *, author_id: int, collaborator_id: int, wanted: Sequence[tuple[int, str]]
) -> None:
    """Os papéis passam a ser o conjunto enviado: o que sai e o que entra ficam na trilha."""
    current = {
        (row.project_id, row.role): row
        for row in session.scalars(
            select(CollaboratorScheduleRole).where(
                CollaboratorScheduleRole.collaborator_id == collaborator_id
            )
        ).all()
    }
    for pair, row in current.items():
        if pair in wanted:
            continue
        before = audit.snapshot(row)
        session.delete(row)
        session.flush()
        audit.deleted(
            session, user_id=author_id, entity=row.__tablename__, record=row, before=before
        )
    for project_id, papel in wanted:
        if (project_id, papel) in current:
            continue
        recording.create(
            session,
            user_id=author_id,
            record=CollaboratorScheduleRole(
                collaborator_id=collaborator_id, project_id=project_id, role=papel
            ),
        )


def _has_access(session: Session, person_id: int) -> bool:
    statement = select(Collaborator.id).where(Collaborator.person_id == person_id).limit(1)
    return session.scalar(statement) is not None


def _is_last_active_admin(session: Session, collaborator: Collaborator) -> bool:
    """Se o colaborador é o único Admin ativo: o que não pode ser removido nem rebaixado."""
    if not collaborator.active or collaborator.general_profile != rbac.GeneralProfile.ADMIN:
        return False
    active_admins = session.scalar(
        select(func.count())
        .select_from(Collaborator)
        .where(
            Collaborator.active.is_(True),
            Collaborator.general_profile == rbac.GeneralProfile.ADMIN,
        )
    )
    return (active_admins or 0) <= 1
