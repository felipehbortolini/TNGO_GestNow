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
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core import audit, rbac, recording
from src.core.errors import InvalidDataError
from src.core.models import Client
from src.core.money import format_brl
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
    System,
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
    if group == "portfolio":
        _copy_portfolio_weights(session, version=version)
    return version


def _copy_portfolio_weights(session: Session, *, version: ParameterVersion) -> None:
    """A nova versão do grupo portfolio nasce com as notas da anterior (ISSUE-078).

    As notas dos projetos vivem dentro da versão (D8); sem a cópia, gravar os
    pesos do portfólio na tela de Parâmetros zeraria a ponderação de todos os
    projetos. As linhas são filhas da versão: a trilha da versão nova já
    registra a criação, e a cópia não entra na trilha linha a linha.
    """
    previous = session.scalars(
        select(ParameterVersion)
        .where(
            ParameterVersion.group == version.group,
            ParameterVersion.version < version.version,
        )
        .order_by(ParameterVersion.version.desc())
        .limit(1)
    ).first()
    if previous is None:
        return
    rows = session.scalars(
        select(PortfolioWeight).where(PortfolioWeight.version_id == previous.id)
    ).all()
    for row in rows:
        session.add(
            PortfolioWeight(
                version_id=version.id,
                project_id=row.project_id,
                criterion=row.criterion,
                grade=row.grade,
            )
        )
    session.flush()


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


# ── Tela de Cadastros (ISSUE-078) ────────────────────────────────────────
#
# A tela mantém os cadastros de apoio que alimentam os formulários (D5):
# empresas, pessoas, projetos, sistemas, unidades, locais e disciplinas. A
# gravação valida aqui, com uma mensagem por campo; a exclusão é recusada
# quando o registro está em uso, primeiro pelas referências do próprio módulo
# (com a contagem) e depois pela chave estrangeira do banco (o nome da tabela
# sai da mensagem do erro). O projeto novo nasce com a configuração padrão da
# Programação Semanal (``ensure_settings``) e as notas de ponderação vivem na
# versão vigente do grupo ``portfolio``, como as dos demais projetos.

REGISTER_KINDS: tuple[str, ...] = (
    "empresa",
    "pessoa",
    "projeto",
    "sistema",
    "unidade",
    "local",
    "disciplina",
)

REGISTER_LABELS: dict[str, str] = {
    "empresa": "Empresa",
    "pessoa": "Pessoa",
    "projeto": "Projeto",
    "sistema": "Sistema",
    "unidade": "Unidade",
    "local": "Local",
    "disciplina": "Disciplina",
}

REGISTER_NOT_FOUND = "Cadastro de apoio desconhecido."
REGISTER_RECORD_NOT_FOUND = "Registro fora do cadastro."

COMPANY_KINDS: tuple[str, ...] = ("Contratada", "Fornecedor", "Gerenciadora")
UNIT_KINDS: tuple[str, ...] = ("medida", ORGANIZATIONAL_UNIT_KIND)

_REGISTER_MODELS: dict[str, Any] = {
    "empresa": Company,
    "pessoa": Person,
    "projeto": Project,
    "sistema": System,
    "unidade": Unit,
    "local": Location,
    "disciplina": Discipline,
}

# O rótulo, em português, da tabela que uma chave estrangeira cita: é o que a
# mensagem de exclusão recusada mostra no lugar do nome técnico. As tabelas que
# não estão aqui caem na mensagem genérica.
_USED_BY_LABELS: dict[str, str] = {
    "acao": "ação",
    "acao_replanejamento": "replanejamento de ação",
    "amostragem": "amostragem do trabalho",
    "amostragem_motivo": "amostragem do trabalho",
    "analise_risco": "análise de risco",
    "analise_risco_participante": "análise de risco",
    "analise_risco_recomendacao": "análise de risco",
    "anexo": "anexo",
    "ata": "ata",
    "ata_empresa": "ata",
    "ata_participante": "ata",
    "auditoria_constatacao": "auditoria da qualidade",
    "auditoria_qualidade": "auditoria da qualidade",
    "auditoria_reprogramacao": "reprogramação de auditoria",
    "colaborador": "colaborador",
    "colaborador_papel_programacao": "papel na Programação Semanal",
    "contrato": "contrato",
    "contrato_aditivo": "contrato",
    "contrato_avaliacao": "avaliação de contrato",
    "contrato_avaliacao_criterio": "avaliação de contrato",
    "contrato_claim": "contrato",
    "contrato_extensao_prazo": "contrato",
    "contrato_marco_pagamento": "contrato",
    "contrato_medicao": "contrato",
    "curva_financeira_mes": "revisão da Curva S financeira",
    "curva_financeira_revisao": "revisão da Curva S financeira",
    "curva_fisica_mes": "revisão da Curva S física",
    "curva_fisica_revisao": "revisão da Curva S física",
    "custo_erp": "custo do ERP",
    "eac_item": "item da EAC",
    "eac_projecao": "projeção no término",
    "eac_remanejamento": "remanejamento da EAC",
    "eac_revisao": "revisão da EAC",
    "eac_revisao_item": "revisão da EAC",
    "eap_desdobramento": "desdobramento da EAP",
    "eap_item": "item da EAP",
    "eap_item_etapa": "item da EAP",
    "eap_medicao": "medição da EAP",
    "eap_revisao": "revisão da EAP",
    "eap_revisao_item": "revisão da EAP",
    "fornecedor": "fornecedor",
    "fornecedor_categoria": "fornecedor",
    "fornecedor_documento": "fornecedor",
    "fornecedor_historico": "fornecedor",
    "hht": "registro de HHT",
    "hse_dds": "DDS do HSE",
    "hse_inspecao": "inspeção do HSE",
    "hse_inspecao_item": "inspeção do HSE",
    "hse_mensal": "fechamento mensal do HSE",
    "hse_observacao": "observação do HSE",
    "inspecao": "inspeção",
    "itp": "ITP",
    "itp_ponto": "ITP",
    "itp_revisao": "ITP",
    "jornada_campo": "jornada de campo",
    "licao": "lição aprendida",
    "licao_aplicacao": "lição aprendida",
    "licao_historico": "lição aprendida",
    "licao_palavra_chave": "lição aprendida",
    "lookahead": "lookahead (6WLA)",
    "lookahead_restricao": "restrição do lookahead",
    "lookahead_semana": "semana do lookahead",
    "mudanca": "solicitação de mudança",
    "mudanca_analise": "análise de mudança",
    "mudanca_decisao": "decisão de mudança",
    "mudanca_decisao_participante": "decisão de mudança",
    "mudanca_impacto": "análise de impacto",
    "mudanca_impacto_eac_item": "análise de impacto",
    "mudanca_remanejamento": "remanejamento de mudança",
    "notificacao": "notificação",
    "ocorrencia": "ocorrência",
    "ocorrencia_investigacao": "ocorrência",
    "ocorrencia_restrito": "ocorrência",
    "pacote_compra": "pacote de compra",
    "pacote_compra_marco": "pacote de compra",
    "paralisacao": "paralisação",
    "parametro_valor": "versão de parâmetros",
    "parametro_versao": "versão de parâmetros",
    "pedido": "pedido de compra",
    "pedido_marco": "pedido de compra",
    "portfolio_ponderacao": "nota de ponderação",
    "processo_compra": "processo de compra",
    "processo_convidado": "processo de compra",
    "processo_negociacao": "processo de compra",
    "processo_proposta": "processo de compra",
    "produtividade_apontamento": "apontamento de produtividade",
    "produtividade_distribuicao": "distribuição de produtividade",
    "produtividade_item": "item de produtividade",
    "produtividade_revisao": "revisão de produtividade",
    "programacao_atividade": "atividade da Programação Semanal",
    "programacao_configuracao": "configuração da Programação Semanal",
    "programacao_dia": "atividade da Programação Semanal",
    "programacao_janela": "janela da Programação Semanal",
    "programacao_janela_dia": "janela da Programação Semanal",
    "programacao_janela_semana": "janela da Programação Semanal",
    "programacao_liberacao_extra": "janela da Programação Semanal",
    "programacao_pedido_alteracao": "pedido de alteração da Programação Semanal",
    "punch_item": "item da punch list",
    "recebimento": "recebimento",
    "relato": "relato de campo",
    "relato_atividade": "relato de campo",
    "relato_ponto": "relato de campo",
    "reserva": "reserva",
    "reserva_movimento": "movimento de reserva",
    "risco": "risco",
    "risco_avaliacao": "risco",
    "risco_plano_aprovacao": "risco",
    "risco_revisao": "risco",
    "rnc": "RNC",
    "sequencia_numeracao": "sequência de numeração",
}

_ON_TABLE = re.compile(r'on table "([^"]+)"')


@dataclass(frozen=True)
class CompanyRegisterRow:
    """Uma empresa da tela: o nome e o tipo."""

    id: int
    name: str
    kind: str | None


@dataclass(frozen=True)
class PersonRegisterRow:
    """Uma pessoa da tela: nome, função, empresa e e-mail."""

    id: int
    name: str
    role: str | None
    company_name: str | None
    email: str


@dataclass(frozen=True)
class GradeLine:
    """Uma nota de ponderação do projeto: o nome do critério e a nota (1 a 5)."""

    criterion: str
    grade: int

    @property
    def label(self) -> str:
        """``Criticidade estratégica: 4``: como a tela e a exportação a imprimem."""
        return f"{self.criterion}: {self.grade}"


@dataclass(frozen=True)
class ProjectRegisterRow:
    """Um projeto da tela: identidade, cliente, gerente, orçamento, datas e notas."""

    id: int
    code: str
    name: str
    client_name: str
    manager_name: str
    budget_cents: int | None
    start_date: date | None
    expected_end_date: date | None
    grades: tuple[GradeLine, ...] = ()

    @property
    def grades_text(self) -> str:
        """As notas numa linha, para a exportação (``Estratégico: 4 · Complexidade: 3``)."""
        return " · ".join(line.label for line in self.grades)


@dataclass(frozen=True)
class SystemRegisterRow:
    """Um sistema da tela: o projeto, o código, o nome e a área."""

    id: int
    project_id: int
    project_label: str
    code: str
    name: str
    area: str | None


@dataclass(frozen=True)
class UnitRegisterRow:
    """Uma unidade da tela: o tipo, o código e o nome."""

    id: int
    kind: str
    code: str
    name: str


@dataclass(frozen=True)
class LocationRegisterRow:
    """Um local da tela: o projeto, o código e o nome."""

    id: int
    project_id: int
    project_label: str
    code: str
    name: str


@dataclass(frozen=True)
class DisciplineRegisterRow:
    """Uma disciplina da tela: o nome."""

    id: int
    name: str


@dataclass(frozen=True)
class RegistersOverview:
    """Os sete cadastros da tela, na ordem dos cartões."""

    companies: tuple[CompanyRegisterRow, ...]
    people: tuple[PersonRegisterRow, ...]
    projects: tuple[ProjectRegisterRow, ...]
    systems: tuple[SystemRegisterRow, ...]
    units: tuple[UnitRegisterRow, ...]
    locations: tuple[LocationRegisterRow, ...]
    disciplines: tuple[DisciplineRegisterRow, ...]

    @property
    def total(self) -> int:
        """O total de registros dos sete cadastros (a linha da barra de exportações)."""
        return sum(
            len(rows)
            for rows in (
                self.companies,
                self.people,
                self.projects,
                self.systems,
                self.units,
                self.locations,
                self.disciplines,
            )
        )


@dataclass(frozen=True)
class AppetiteOption:
    """Uma faixa de apetite a risco da escala vigente: o id gravado e o nome lido."""

    value: str
    name: str


@dataclass(frozen=True)
class GradeCriterion:
    """Um critério de nota da carteira vigente: id, nome e a faixa de notas (D8)."""

    id: str
    name: str
    minimum: int
    maximum: int

    @property
    def field_name(self) -> str:
        """O nome do campo da nota no formulário (``nota_estrategico``)."""
        return f"nota_{self.id}"


@dataclass(frozen=True)
class RegisterFormOptions:
    """As listas dos formulários da tela: empresas, pessoas, projetos, apetite e notas."""

    companies: tuple[RegisterOption, ...]
    people: tuple[RegisterOption, ...]
    projects: tuple[ProjectSummary, ...]
    appetites: tuple[AppetiteOption, ...]
    criteria: tuple[GradeCriterion, ...]
    company_kinds: tuple[str, ...]
    unit_kinds: tuple[str, ...]


def registers_overview(session: Session, *, reference_date: date) -> RegistersOverview:
    """Os sete cadastros da tela, com a empresa, o projeto e o gerente de cada linha."""
    return RegistersOverview(
        companies=_company_rows(session),
        people=_person_rows(session),
        projects=_project_rows(session, reference_date=reference_date),
        systems=_system_rows(session),
        units=_unit_rows(session),
        locations=_location_rows(session),
        disciplines=_discipline_rows(session),
    )


def _company_rows(session: Session) -> tuple[CompanyRegisterRow, ...]:
    statement = select(Company.id, Company.name, Company.kind).order_by(Company.name, Company.id)
    return tuple(
        CompanyRegisterRow(id=row.id, name=row.name, kind=row.kind)
        for row in session.execute(statement)
    )


def _person_rows(session: Session) -> tuple[PersonRegisterRow, ...]:
    statement = (
        select(
            Person.id,
            Person.name,
            Person.role,
            Person.email,
            Company.name.label("empresa"),
        )
        .outerjoin(Company, Company.id == Person.company_id)
        .order_by(Person.name, Person.id)
    )
    return tuple(
        PersonRegisterRow(
            id=row.id,
            name=row.name,
            role=row.role,
            company_name=row.empresa,
            email=row.email,
        )
        for row in session.execute(statement)
    )


def _project_rows(session: Session, *, reference_date: date) -> tuple[ProjectRegisterRow, ...]:
    statement = (
        select(Project, Client.name.label("cliente"), Person.name.label("gerente"))
        .join(Client, Client.id == Project.client_id)
        .join(Person, Person.id == Project.manager_id)
        .order_by(Project.code)
    )
    grades_by_project = portfolio_grades(session, reference_date=reference_date)
    criteria = _grade_criteria(session, reference_date=reference_date)
    rows: list[ProjectRegisterRow] = []
    for project, client_name, manager_name in session.execute(statement):
        grades = grades_by_project.get(project.id, {})
        rows.append(
            ProjectRegisterRow(
                id=project.id,
                code=project.code,
                name=project.name,
                client_name=client_name,
                manager_name=manager_name,
                budget_cents=project.budget_cents,
                start_date=project.start_date,
                expected_end_date=project.expected_end_date,
                grades=tuple(
                    GradeLine(criterion=criterion.name, grade=grades[criterion.id])
                    for criterion in criteria
                    if criterion.id in grades
                ),
            )
        )
    return tuple(rows)


def _system_rows(session: Session) -> tuple[SystemRegisterRow, ...]:
    statement = (
        select(System, Project.code.label("codigo"), Project.name.label("nome"))
        .join(Project, Project.id == System.project_id)
        .order_by(Project.code, System.code)
    )
    return tuple(
        SystemRegisterRow(
            id=system.id,
            project_id=system.project_id,
            project_label=f"{project_code} · {project_name}",
            code=system.code,
            name=system.name,
            area=system.area,
        )
        for system, project_code, project_name in session.execute(statement)
    )


def _unit_rows(session: Session) -> tuple[UnitRegisterRow, ...]:
    statement = select(Unit.id, Unit.kind, Unit.code, Unit.name).order_by(
        Unit.kind, Unit.code, Unit.id
    )
    return tuple(
        UnitRegisterRow(id=row.id, kind=row.kind, code=row.code, name=row.name)
        for row in session.execute(statement)
    )


def _location_rows(session: Session) -> tuple[LocationRegisterRow, ...]:
    statement = (
        select(Location, Project.code.label("codigo"), Project.name.label("nome"))
        .join(Project, Project.id == Location.project_id)
        .order_by(Project.code, Location.code)
    )
    return tuple(
        LocationRegisterRow(
            id=location.id,
            project_id=location.project_id,
            project_label=f"{project_code} · {project_name}",
            code=location.code,
            name=location.name,
        )
        for location, project_code, project_name in session.execute(statement)
    )


def _discipline_rows(session: Session) -> tuple[DisciplineRegisterRow, ...]:
    statement = select(Discipline.id, Discipline.name).order_by(Discipline.name, Discipline.id)
    return tuple(
        DisciplineRegisterRow(id=row.id, name=row.name) for row in session.execute(statement)
    )


def register_form_options(session: Session, *, reference_date: date) -> RegisterFormOptions:
    """O que os formulários da tela oferecem, dos cadastros e da versão vigente dos parâmetros."""
    return RegisterFormOptions(
        companies=tuple(list_company_options(session)),
        people=tuple(list_person_options(session)),
        projects=tuple(list_projects(session)),
        appetites=_appetite_options(session, reference_date),
        criteria=_grade_criteria(session, reference_date),
        company_kinds=COMPANY_KINDS,
        unit_kinds=UNIT_KINDS,
    )


def register_form_values(
    session: Session, kind: str, register_id: int, *, reference_date: date
) -> dict[str, Any] | None:
    """O registro como o formulário de edição o carrega, ou ``None`` fora do cadastro."""
    record = _register_record(session, kind, register_id)
    if record is None:
        return None
    values: dict[str, Any]
    if kind == "empresa":
        values = {"nome": record.name, "tipo": record.kind or ""}
    elif kind == "pessoa":
        values = {
            "nome": record.name,
            "funcao": record.role or "",
            "empresa": str(record.company_id) if record.company_id is not None else "",
            "email": record.email,
        }
    elif kind == "projeto":
        values = _project_values(session, record, reference_date=reference_date)
    elif kind == "sistema":
        values = {
            "projeto": str(record.project_id),
            "codigo": record.code,
            "nome": record.name,
            "area": record.area or "",
        }
    elif kind == "unidade":
        values = {"tipo": record.kind, "codigo": record.code, "nome": record.name}
    elif kind == "local":
        values = {"projeto": str(record.project_id), "codigo": record.code, "nome": record.name}
    else:
        values = {"nome": record.name}
    return values


def _project_values(session: Session, project: Any, *, reference_date: date) -> dict[str, Any]:
    client = session.get(Client, project.client_id)
    grades = portfolio_grades(session, reference_date=reference_date).get(project.id, {})
    values: dict[str, Any] = {
        "codigo": project.code,
        "nome": project.name,
        "cliente_nome": client.name if client is not None else "",
        "cliente_sigla": (client.acronym or "") if client is not None else "",
        "gerente": str(project.manager_id),
        "pep": project.pep or "",
        "apetite": project.risk_appetite or "",
        "inicio": project.start_date.isoformat() if project.start_date is not None else "",
        "termino_previsto": (
            project.expected_end_date.isoformat() if project.expected_end_date is not None else ""
        ),
        "orcamento": (format_brl(project.budget_cents) if project.budget_cents is not None else ""),
        "padrao_ata": project.ata_pattern or "",
        "padrao_risco": project.risk_pattern or "",
        "padrao_punch": project.punch_pattern or "",
    }
    for criterion, grade in grades.items():
        values[f"nota_{criterion}"] = str(grade)
    return values


def save_register(
    session: Session,
    *,
    kind: str,
    author_id: int,
    register_id: int | None,
    form: Mapping[str, Any],
    reference_date: date,
) -> str:
    """Grava um cadastro de apoio (novo ou existente), com validação e trilha.

    Devolve o rótulo do registro (nome, ou o código no projeto) para o aviso da
    tela; a falha de qualquer regra levanta ``InvalidDataError`` com a mensagem
    de cada campo. O projeto novo chama ``ensure_settings`` da Programação
    Semanal e as notas de ponderação entram na versão vigente do portfólio.
    """
    saver = _REGISTER_SAVERS.get(kind)
    if saver is None:
        raise InvalidDataError({"geral": REGISTER_NOT_FOUND})
    return saver(
        session,
        author_id=author_id,
        register_id=register_id,
        form=form,
        reference_date=reference_date,
    )


def _save_company(
    session: Session,
    *,
    author_id: int,
    register_id: int | None,
    form: Mapping[str, Any],
    reference_date: date,
) -> str:
    del reference_date
    record = _register_record(session, "empresa", register_id)
    if register_id is not None and record is None:
        raise InvalidDataError({"geral": REGISTER_RECORD_NOT_FOUND})
    name = (form.get("nome") or "").strip()
    kind = (form.get("tipo") or "").strip()
    errors: dict[str, str] = {}
    if not name:
        errors["nome"] = "Informe o nome da empresa."
    elif _company_name_taken(session, name, ignore_id=register_id):
        errors["nome"] = "Já existe uma empresa com este nome."
    if kind not in COMPANY_KINDS:
        errors["tipo"] = "Escolha o tipo da empresa."
    if errors:
        raise InvalidDataError(errors)
    if record is None:
        record = recording.create(session, user_id=author_id, record=Company(name=name, kind=kind))
    else:
        recording.update(
            session,
            user_id=author_id,
            record=record,
            changes={"name": name, "kind": kind},
            version=record.version,
        )
    session.flush()
    return str(record.name)


def _save_person(
    session: Session,
    *,
    author_id: int,
    register_id: int | None,
    form: Mapping[str, Any],
    reference_date: date,
) -> str:
    del reference_date
    record = _register_record(session, "pessoa", register_id)
    if register_id is not None and record is None:
        raise InvalidDataError({"geral": REGISTER_RECORD_NOT_FOUND})
    name = (form.get("nome") or "").strip()
    role = (form.get("funcao") or "").strip()
    email = (form.get("email") or "").strip().lower()
    company_text = (form.get("empresa") or "").strip()
    company_id = _int_of(company_text)
    errors: dict[str, str] = {}
    if not name:
        errors["nome"] = "Informe o nome da pessoa."
    if not _EMAIL.match(email):
        errors["email"] = "Informe um e-mail válido."
    elif _person_email_taken(session, email, ignore_id=register_id):
        errors["email"] = "Já existe uma pessoa com este e-mail."
    if company_text and (company_id is None or session.get(Company, company_id) is None):
        errors["empresa"] = "Empresa fora do cadastro."
    if errors:
        raise InvalidDataError(errors)
    changes = {
        "name": name,
        "role": role or None,
        "email": email,
        "company_id": company_id,
    }
    if record is None:
        record = recording.create(session, user_id=author_id, record=Person(**changes))
    else:
        recording.update(
            session, user_id=author_id, record=record, changes=changes, version=record.version
        )
    session.flush()
    return str(record.name)


def _save_project(
    session: Session,
    *,
    author_id: int,
    register_id: int | None,
    form: Mapping[str, Any],
    reference_date: date,
) -> str:
    record = _register_record(session, "projeto", register_id)
    if register_id is not None and record is None:
        raise InvalidDataError({"geral": REGISTER_RECORD_NOT_FOUND})
    data, errors = _validate_project(
        session, register_id=register_id, form=form, reference_date=reference_date
    )
    if errors:
        raise InvalidDataError(errors)
    client = _find_client(session, data.client_name)
    if client is None:
        client = recording.create(
            session,
            user_id=author_id,
            record=Client(name=data.client_name, acronym=data.client_sigla or None, active=True),
        )
    changes = {
        "client_id": client.id,
        "manager_id": data.manager_id,
        "code": data.code,
        "name": data.name,
        "pep": data.pep,
        "ata_pattern": data.ata_pattern,
        "risk_pattern": data.risk_pattern,
        "punch_pattern": data.punch_pattern,
        "risk_appetite": data.appetite,
        "start_date": data.start,
        "expected_end_date": data.end,
        "budget_cents": data.budget_cents,
    }
    if record is None:
        record = recording.create(session, user_id=author_id, record=Project(**changes))
        _new_project_settings(session, author_id=author_id, project_id=record.id)
    else:
        recording.update(
            session, user_id=author_id, record=record, changes=changes, version=record.version
        )
    _replace_project_grades(
        session,
        author_id=author_id,
        project_id=record.id,
        grades=data.grades,
        reference_date=reference_date,
    )
    session.flush()
    return str(record.code)


@dataclass(frozen=True)
class _ProjectData:
    """O projeto validado, pronto para a gravação."""

    code: str
    name: str
    client_name: str
    client_sigla: str
    manager_id: int
    pep: str | None
    appetite: str | None
    start: date | None
    end: date | None
    budget_cents: int | None
    ata_pattern: str | None
    risk_pattern: str | None
    punch_pattern: str | None
    grades: Mapping[str, int]


def _validate_project(
    session: Session, *, register_id: int | None, form: Mapping[str, Any], reference_date: date
) -> tuple[_ProjectData, dict[str, str]]:
    """As regras do projeto por campo: código único, cliente, gerente, datas, orçamento e notas."""
    errors: dict[str, str] = {}
    code = (form.get("codigo") or "").strip()
    name = (form.get("nome") or "").strip()
    client_name = (form.get("cliente_nome") or "").strip()
    client_sigla = (form.get("cliente_sigla") or "").strip()
    manager_id = _int_of(form.get("gerente"))
    appetite = (form.get("apetite") or "").strip()
    if not code:
        errors["codigo"] = "Informe o código do projeto."
    elif _project_code_taken(session, code, ignore_id=register_id):
        errors["codigo"] = "Já existe um projeto com este código."
    if not name:
        errors["nome"] = "Informe o nome do projeto."
    if not client_name:
        errors["cliente"] = "Informe o cliente do projeto."
    elif _find_client(session, client_name) is None and not client_sigla:
        errors["cliente"] = "Informe a sigla do cliente novo."
    if manager_id is None or session.get(Person, manager_id) is None:
        errors["gerente"] = "Escolha o gerente do projeto."
    if appetite and all(
        option.value != appetite for option in _appetite_options(session, reference_date)
    ):
        errors["apetite"] = "Escolha um apetite da escala vigente."
    start = _date_or_error(form.get("inicio"), "inicio", errors)
    end = _date_or_error(form.get("termino_previsto"), "termino_previsto", errors)
    if start is not None and end is not None and end < start:
        errors["termino"] = "O término não pode ser anterior ao início."
    budget_text = (form.get("orcamento") or "").strip()
    budget_cents = forms.parse_money(budget_text)
    if budget_text and budget_cents is None:
        errors["orcamento"] = "Informe um valor em reais (ex.: 1.234,56)."
    grades = _posted_grades(form, _grade_criteria(session, reference_date), errors)
    data = _ProjectData(
        code=code,
        name=name,
        client_name=client_name,
        client_sigla=client_sigla,
        manager_id=manager_id or 0,
        pep=(form.get("pep") or "").strip() or None,
        appetite=appetite or None,
        start=start,
        end=end,
        budget_cents=budget_cents,
        ata_pattern=(form.get("padrao_ata") or "").strip() or None,
        risk_pattern=(form.get("padrao_risco") or "").strip() or None,
        punch_pattern=(form.get("padrao_punch") or "").strip() or None,
        grades=grades,
    )
    return data, errors


def _date_or_error(raw: Any, field: str, errors: dict[str, str]) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        errors[field] = "Informe uma data válida."
        return None


def _posted_grades(
    form: Mapping[str, Any], criteria: Sequence[GradeCriterion], errors: dict[str, str]
) -> dict[str, int]:
    """As notas digitadas por critério; campo vazio não grava nota, fora da faixa é recusado."""
    grades: dict[str, int] = {}
    for criterion in criteria:
        text = str(form.get(criterion.field_name) or "").strip()
        if not text:
            continue
        value = _int_of(text)
        if value is None or not criterion.minimum <= value <= criterion.maximum:
            errors[criterion.field_name] = (
                f"Informe uma nota de {criterion.minimum} a {criterion.maximum}."
            )
            continue
        grades[criterion.id] = value
    return grades


def _replace_project_grades(
    session: Session,
    *,
    author_id: int,
    project_id: int,
    grades: Mapping[str, int],
    reference_date: date,
) -> None:
    """As notas do projeto passam a ser as enviadas, na versão vigente do grupo portfolio.

    As notas vivem dentro da versão (D8); sem versão vigente (antes da primeira
    semeadura) nada é gravado. O que sai e o que entra ficam na trilha, como os
    papéis da Programação Semanal: linhas filhas, sem ``versao`` própria.
    """
    version = current_version(session, group="portfolio", reference_date=reference_date)
    if version is None:
        return
    current = {
        row.criterion: row
        for row in session.scalars(
            select(PortfolioWeight).where(
                PortfolioWeight.version_id == version.id,
                PortfolioWeight.project_id == project_id,
            )
        ).all()
    }
    for criterion, row in current.items():
        if grades.get(criterion) == row.grade:
            continue
        before = audit.snapshot(row)
        session.delete(row)
        session.flush()
        audit.deleted(
            session, user_id=author_id, entity=row.__tablename__, record=row, before=before
        )
    for criterion, grade in grades.items():
        if criterion in current and current[criterion].grade == grade:
            continue
        recording.create(
            session,
            user_id=author_id,
            record=PortfolioWeight(
                version_id=version.id,
                project_id=project_id,
                criterion=criterion,
                grade=grade,
            ),
        )


def replace_portfolio_grades(
    session: Session,
    *,
    version: ParameterVersion,
    grades: Mapping[int, Mapping[str, int]],
    author_id: int,
) -> None:
    """As notas da carteira passam a ser as enviadas, na versão dada do grupo portfolio.

    A ponderação do Início (ISSUE-080) cria a versão nova por
    ``save_parameter_group`` — que copia as notas da anterior — e substitui, na
    sequência, as notas digitadas por projeto e critério. O que sai e o que
    entra ficam na trilha, como a edição das notas de um projeto: linhas filhas,
    sem ``versao`` própria; nota igual à da versão não gera trilha.
    """
    current = {
        (row.project_id, row.criterion): row
        for row in session.scalars(
            select(PortfolioWeight).where(PortfolioWeight.version_id == version.id)
        ).all()
    }
    for (project_id, criterion), row in current.items():
        wanted = grades.get(project_id, {}).get(criterion)
        if wanted is None or wanted == row.grade:
            continue
        before = audit.snapshot(row)
        session.delete(row)
        session.flush()
        audit.deleted(
            session, user_id=author_id, entity=row.__tablename__, record=row, before=before
        )
    for project_id, criteria in grades.items():
        for criterion, grade in criteria.items():
            row = current.get((project_id, criterion))
            if row is not None and row.grade == grade:
                continue
            recording.create(
                session,
                user_id=author_id,
                record=PortfolioWeight(
                    version_id=version.id,
                    project_id=project_id,
                    criterion=criterion,
                    grade=grade,
                ),
            )


def _new_project_settings(session: Session, *, author_id: int, project_id: int) -> None:
    """O projeto nasce com a configuração padrão da Programação Semanal (ISSUE-054)."""
    from src.modulos.programacao_semanal import service as programacao

    programacao.ensure_settings(session, author_id=author_id, project_id=project_id)


def _remove_schedule_settings(session: Session, *, author_id: int, project_id: int) -> None:
    """Apaga a configuração da Programação Semanal do projeto, pela fachada dona (D10)."""
    from src.modulos.programacao_semanal import service as programacao

    programacao.remove_settings(session, author_id=author_id, project_id=project_id)


def _save_system(
    session: Session,
    *,
    author_id: int,
    register_id: int | None,
    form: Mapping[str, Any],
    reference_date: date,
) -> str:
    del reference_date
    record = _register_record(session, "sistema", register_id)
    if register_id is not None and record is None:
        raise InvalidDataError({"geral": REGISTER_RECORD_NOT_FOUND})
    project_id = _int_of(form.get("projeto"))
    code = (form.get("codigo") or "").strip()
    name = (form.get("nome") or "").strip()
    area = (form.get("area") or "").strip()
    errors: dict[str, str] = {}
    if project_id is None or session.get(Project, project_id) is None:
        errors["projeto"] = "Escolha o projeto."
    if not code:
        errors["codigo"] = "Informe o código do sistema."
    elif project_id is not None and _system_code_taken(
        session, project_id=project_id, code=code, ignore_id=register_id
    ):
        errors["codigo"] = "Já existe um sistema com este código neste projeto."
    if not name:
        errors["nome"] = "Informe o nome do sistema."
    if errors:
        raise InvalidDataError(errors)
    changes = {"project_id": project_id, "code": code, "name": name, "area": area or None}
    if record is None:
        record = recording.create(session, user_id=author_id, record=System(**changes))
    else:
        recording.update(
            session, user_id=author_id, record=record, changes=changes, version=record.version
        )
    session.flush()
    return str(record.name)


def _save_unit(
    session: Session,
    *,
    author_id: int,
    register_id: int | None,
    form: Mapping[str, Any],
    reference_date: date,
) -> str:
    del reference_date
    record = _register_record(session, "unidade", register_id)
    if register_id is not None and record is None:
        raise InvalidDataError({"geral": REGISTER_RECORD_NOT_FOUND})
    kind = (form.get("tipo") or "").strip()
    code = (form.get("codigo") or "").strip()
    name = (form.get("nome") or "").strip()
    errors: dict[str, str] = {}
    if kind not in UNIT_KINDS:
        errors["tipo"] = "Escolha o tipo da unidade."
    if not code:
        errors["codigo"] = "Informe o código da unidade."
    elif kind in UNIT_KINDS and _unit_code_taken(
        session, kind=kind, code=code, ignore_id=register_id
    ):
        errors["codigo"] = "Já existe uma unidade com este código neste tipo."
    if not name:
        errors["nome"] = "Informe o nome da unidade."
    if errors:
        raise InvalidDataError(errors)
    changes = {"kind": kind, "code": code, "name": name}
    if record is None:
        record = recording.create(session, user_id=author_id, record=Unit(**changes))
    else:
        recording.update(
            session, user_id=author_id, record=record, changes=changes, version=record.version
        )
    session.flush()
    return str(record.name)


def _save_location(
    session: Session,
    *,
    author_id: int,
    register_id: int | None,
    form: Mapping[str, Any],
    reference_date: date,
) -> str:
    del reference_date
    record = _register_record(session, "local", register_id)
    if register_id is not None and record is None:
        raise InvalidDataError({"geral": REGISTER_RECORD_NOT_FOUND})
    project_id = _int_of(form.get("projeto"))
    code = (form.get("codigo") or "").strip()
    name = (form.get("nome") or "").strip()
    errors: dict[str, str] = {}
    if project_id is None or session.get(Project, project_id) is None:
        errors["projeto"] = "Escolha o projeto."
    if not code:
        errors["codigo"] = "Informe o código do local."
    elif project_id is not None and _location_code_taken(
        session, project_id=project_id, code=code, ignore_id=register_id
    ):
        errors["codigo"] = "Já existe um local com este código neste projeto."
    if not name:
        errors["nome"] = "Informe o nome do local."
    if errors:
        raise InvalidDataError(errors)
    changes = {"project_id": project_id, "code": code, "name": name}
    if record is None:
        record = recording.create(session, user_id=author_id, record=Location(**changes))
    else:
        recording.update(
            session, user_id=author_id, record=record, changes=changes, version=record.version
        )
    session.flush()
    return str(record.name)


def _save_discipline(
    session: Session,
    *,
    author_id: int,
    register_id: int | None,
    form: Mapping[str, Any],
    reference_date: date,
) -> str:
    del reference_date
    record = _register_record(session, "disciplina", register_id)
    if register_id is not None and record is None:
        raise InvalidDataError({"geral": REGISTER_RECORD_NOT_FOUND})
    name = (form.get("nome") or "").strip()
    errors: dict[str, str] = {}
    if not name:
        errors["nome"] = "Informe o nome da disciplina."
    elif _discipline_name_taken(session, name, ignore_id=register_id):
        errors["nome"] = "Já existe uma disciplina com este nome."
    if errors:
        raise InvalidDataError(errors)
    if record is None:
        record = recording.create(session, user_id=author_id, record=Discipline(name=name))
    else:
        recording.update(
            session,
            user_id=author_id,
            record=record,
            changes={"name": name},
            version=record.version,
        )
    session.flush()
    return str(record.name)


# As fachadas de gravação de cada tipo, pelo contrato uniforme do ``save_register``.
_REGISTER_SAVERS: dict[str, Callable[..., str]] = {
    "empresa": _save_company,
    "pessoa": _save_person,
    "projeto": _save_project,
    "sistema": _save_system,
    "unidade": _save_unit,
    "local": _save_location,
    "disciplina": _save_discipline,
}


def delete_register(session: Session, *, kind: str, author_id: int, register_id: int) -> str:
    """Exclui um cadastro de apoio, com a trilha, e devolve o rótulo do registro.

    A exclusão é recusada com ``InvalidDataError`` quando o registro está em uso:
    as referências do próprio módulo são contadas antes (a mensagem diz quantas
    são); as demais vêm da chave estrangeira do banco, dentro do savepoint, e a
    tabela é lida da mensagem do erro. No projeto, a configuração da Programação
    Semanal sai antes pela fachada dona; a recusa desfaz tudo com o rollback.
    """
    if kind not in REGISTER_KINDS:
        raise InvalidDataError({"geral": REGISTER_NOT_FOUND})
    record = _register_record(session, kind, register_id)
    if record is None:
        raise InvalidDataError({"geral": REGISTER_RECORD_NOT_FOUND})
    label = _register_label(kind, record)
    in_use = _register_in_use(session, kind, register_id, label)
    if in_use is not None:
        raise InvalidDataError({"geral": in_use})
    if kind == "projeto":
        _remove_schedule_settings(session, author_id=author_id, project_id=register_id)
    try:
        with session.begin_nested():
            recording.delete(session, user_id=author_id, record=record, version=record.version)
    except IntegrityError as error:
        raise InvalidDataError({"geral": _fk_in_use_message(label, error)}) from None
    return label


def _register_record(session: Session, kind: str, register_id: int | None) -> Any:
    if register_id is None:
        return None
    model = _REGISTER_MODELS.get(kind)
    return session.get(model, register_id) if model is not None else None


def _register_label(kind: str, record: Any) -> str:
    return str(record.code) if kind == "projeto" else str(record.name)


@dataclass(frozen=True)
class _UseCheck:
    """Uma referência do próprio módulo que impede a exclusão de um cadastro."""

    model: Any
    column: Any
    singular: str
    plural: str


_MODULE_USE_CHECKS: dict[str, tuple[_UseCheck, ...]] = {
    "empresa": (
        _UseCheck(Person, Person.company_id, "pessoa do cadastro", "pessoas do cadastro"),
        _UseCheck(Collaborator, Collaborator.company_id, "colaborador", "colaboradores"),
    ),
    "pessoa": (
        _UseCheck(Collaborator, Collaborator.person_id, "colaborador", "colaboradores"),
        _UseCheck(
            Project,
            Project.manager_id,
            "projeto em que é gerente",
            "projetos em que é gerente",
        ),
    ),
    "projeto": (
        _UseCheck(System, System.project_id, "sistema", "sistemas"),
        _UseCheck(
            CollaboratorScheduleRole,
            CollaboratorScheduleRole.project_id,
            "papel na Programação Semanal",
            "papéis na Programação Semanal",
        ),
        _UseCheck(
            PortfolioWeight,
            PortfolioWeight.project_id,
            "nota de ponderação",
            "notas de ponderação",
        ),
    ),
}


def _register_in_use(session: Session, kind: str, register_id: int, label: str) -> str | None:
    """A primeira referência do próprio módulo, com a contagem; ``None`` quando não há."""
    for check in _MODULE_USE_CHECKS.get(kind, ()):
        count = (
            session.scalar(
                select(func.count()).select_from(check.model).where(check.column == register_id)
            )
            or 0
        )
        if count == 0:
            continue
        what = check.singular if count == 1 else check.plural
        return f"“{label}” está em uso por {count} {what} e não pode ser excluído."
    return None


def _fk_in_use_message(label: str, error: IntegrityError) -> str:
    """A recusa pela chave estrangeira, com o rótulo da tabela que bloqueou a exclusão.

    A trilha de auditoria tem mensagem própria: ela é o registro do projeto que o
    próprio cadastro deixou ao gravar, e a mensagem genérica de "registros de"
    não diria o que a pessoa precisa ouvir.
    """
    table = _fk_table(error)
    if table == "auditoria":
        return f"“{label}” está em uso pela trilha de auditoria e não pode ser excluído."
    what = _USED_BY_LABELS.get(table) if table is not None else None
    if what is None:
        return f"“{label}” está em uso no sistema e não pode ser excluído."
    return f"“{label}” está em uso por registros de {what} e não pode ser excluído."


def _fk_table(error: IntegrityError) -> str | None:
    """A tabela que barrou a exclusão: o diagnóstico da violação ou a última citação do erro.

    A mensagem do banco começa pela tabela excluída (``update or delete on table
    "unidade"``) e só depois cita a que guarda a chave estrangeira
    (``on table "eap_item"``); o diagnóstico do psycopg traz a tabela certa de
    imediato e a última citação cobre um driver sem diagnóstico.
    """
    diag = getattr(error.orig, "diag", None)
    name = getattr(diag, "table_name", None)
    if name:
        return str(name)
    text = str(error.orig if error.orig is not None else error)
    found = _ON_TABLE.findall(text)
    return found[-1] if found else None


def _int_of(raw: Any) -> int | None:
    text = str(raw or "").strip()
    return int(text) if text.isdecimal() else None


def _company_name_taken(session: Session, name: str, *, ignore_id: int | None) -> bool:
    wanted = name.strip().casefold()
    statement = select(Company.id, Company.name)
    return any(
        row.id != ignore_id and row.name.strip().casefold() == wanted
        for row in session.execute(statement)
    )


def _person_email_taken(session: Session, email: str, *, ignore_id: int | None) -> bool:
    wanted = email.strip().casefold()
    statement = select(Person.id, Person.email)
    return any(
        row.id != ignore_id and row.email.strip().casefold() == wanted
        for row in session.execute(statement)
    )


def _project_code_taken(session: Session, code: str, *, ignore_id: int | None) -> bool:
    wanted = code.strip().casefold()
    statement = select(Project.id, Project.code)
    return any(
        row.id != ignore_id and row.code.strip().casefold() == wanted
        for row in session.execute(statement)
    )


def _discipline_name_taken(session: Session, name: str, *, ignore_id: int | None) -> bool:
    wanted = name.strip().casefold()
    statement = select(Discipline.id, Discipline.name)
    return any(
        row.id != ignore_id and row.name.strip().casefold() == wanted
        for row in session.execute(statement)
    )


def _system_code_taken(
    session: Session, *, project_id: int, code: str, ignore_id: int | None
) -> bool:
    statement = select(System.id, System.code).where(System.project_id == project_id)
    wanted = code.strip().casefold()
    return any(
        row.id != ignore_id and row.code.strip().casefold() == wanted
        for row in session.execute(statement)
    )


def _location_code_taken(
    session: Session, *, project_id: int, code: str, ignore_id: int | None
) -> bool:
    statement = select(Location.id, Location.code).where(Location.project_id == project_id)
    wanted = code.strip().casefold()
    return any(
        row.id != ignore_id and row.code.strip().casefold() == wanted
        for row in session.execute(statement)
    )


def _unit_code_taken(session: Session, *, kind: str, code: str, ignore_id: int | None) -> bool:
    statement = select(Unit.id, Unit.code).where(Unit.kind == kind)
    wanted = code.strip().casefold()
    return any(
        row.id != ignore_id and row.code.strip().casefold() == wanted
        for row in session.execute(statement)
    )


def _find_client(session: Session, name: str) -> Client | None:
    """O cliente do nome, sem diferenciar maiúsculas (o projeto o reusa), ou ``None``."""
    wanted = name.strip().casefold()
    for client in session.scalars(select(Client).order_by(Client.id)):
        if client.name.strip().casefold() == wanted:
            return client
    return None


def _appetite_options(session: Session, reference_date: date) -> tuple[AppetiteOption, ...]:
    """As faixas de apetite a risco da escala vigente, na ordem do parâmetro."""
    options: list[AppetiteOption] = []
    for faixa in _appetite_bands(session, reference_date):
        value = str(faixa.get("id") or "").strip()
        if not value:
            continue
        options.append(AppetiteOption(value=value, name=str(faixa.get("nome") or value)))
    return tuple(options)


def _appetite_bands(session: Session, reference_date: date) -> tuple[Mapping[str, Any], ...]:
    """As faixas da escala de riscos vigente: o apetite do projeto escolhe uma delas."""
    values = current_group(session, group="riscos", reference_date=reference_date)
    escalas = values.get("escalas")
    active = values.get("escalaAtiva")
    if not isinstance(escalas, Mapping) or not isinstance(active, str):
        return ()
    escala = escalas.get(active)
    if not isinstance(escala, Mapping):
        return ()
    faixas = escala.get("faixas")
    if not isinstance(faixas, list):
        return ()
    return tuple(faixa for faixa in faixas if isinstance(faixa, Mapping))


def _grade_criteria(session: Session, reference_date: date) -> tuple[GradeCriterion, ...]:
    """Os critérios de nota da carteira vigente, com a faixa de notas (D8)."""
    values = current_group(session, group="portfolio", reference_date=reference_date)
    criteria = values.get("criterios")
    if not isinstance(criteria, list):
        return ()
    minimum = _int_of(values.get("notaMinima")) or 1
    maximum = _int_of(values.get("notaMaxima")) or 5
    return tuple(
        GradeCriterion(
            id=str(item["id"]),
            name=str(item.get("nome") or item["id"]),
            minimum=minimum,
            maximum=maximum,
        )
        for item in criteria
        if isinstance(item, Mapping) and item.get("fonte") == "nota" and item.get("id")
    )
