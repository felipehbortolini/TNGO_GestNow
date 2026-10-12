"""Exportações das telas de Configurações (ISSUE-076, ISSUE-077 e ISSUE-078, D12).

O mesmo documento alimenta o Excel e a versão imprimível (o PDF do navegador).

* **Parâmetros:** as duas tabelas do protótipo — Parâmetros vigentes
  (Grupo/Parâmetro/Valor/Módulo) e Histórico de versões (Versão/Grupo/Vigência/
  Alterada por/Justificativa/Alterações, com a coluna Grupo que o versionamento
  por grupo acrescentou). Os parâmetros são globais, não de um projeto.
* **Colaboradores:** a lista de quem tem acesso (Pessoa/E-mail/Função/Perfil/
  Vínculo/Empresa/Situação/Papéis na Programação Semanal), sem a coluna Projeto
  porque o cadastro de acesso não pertence a um projeto.
* **Cadastros de apoio:** as sete tabelas da tela (empresas, pessoas, projetos,
  sistemas, unidades, locais e disciplinas), com as mesmas colunas da tela;
  sistemas e locais trazem a coluna Projeto porque são por projeto.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core.export_document import (
    Cell,
    Column,
    Document,
    Row,
    Table,
    Tone,
    ValueKind,
    describe_scope,
    format_value,
    row,
)
from src.core.navigation_view import ProjectLike
from src.core.scope import Scope
from src.modulos.configuracoes.service import (
    CollaboratorRow,
    CompanyRegisterRow,
    DisciplineRegisterRow,
    GroupView,
    HistoryEntry,
    LocationRegisterRow,
    ParameterOverview,
    PersonRegisterRow,
    ProjectRegisterRow,
    RegistersOverview,
    SystemRegisterRow,
    UnitRegisterRow,
)

TITLE = "Parâmetros do sistema"
CURRENT_TABLE = "Parâmetros vigentes"
HISTORY_TABLE = "Histórico de versões"
NOT_RECORDED = "·"
INITIAL_JUSTIFICATION = "Versão inicial"

COLLABORATORS_TITLE = "Colaboradores"
COLLABORATORS_TABLE = "Quem tem acesso hoje"
ACTIVE_TEXT = "Ativo"
SUSPENDED_TEXT = "Suspenso"

COLLABORATORS_COLUMNS = (
    Column("Pessoa", width=28),
    Column("E-mail", width=30),
    Column("Função", width=22),
    Column("Perfil", width=14),
    Column("Vínculo", width=12),
    Column("Empresa", width=24),
    Column("Situação", width=12),
    Column("Papéis na Programação Semanal", width=44),
)

CURRENT_COLUMNS = (
    Column("Grupo", width=26),
    Column("Parâmetro", width=52),
    Column("Valor", width=26),
    Column("Módulo", width=22),
)

HISTORY_COLUMNS = (
    Column("Versão", width=10),
    Column("Grupo", width=26),
    Column("Vigência", width=24),
    Column("Alterada por", width=22),
    Column("Justificativa", width=48),
    Column("Alterações", ValueKind.INTEGER, width=12),
)


def parametros_document(
    *,
    overview: ParameterOverview,
    history: Sequence[HistoryEntry],
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """O documento da tela: a versão vigente no cabeçalho e as duas tabelas do protótipo."""
    return Document(
        namespace="configuracoes",
        idioma=idioma,
        title=TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        context=(
            ("Versão vigente", _latest_text(overview)),
            ("Versões registradas", str(overview.total_versions)),
        ),
        tables=(
            _current_table(overview.groups),
            _history_table(history),
        ),
    )


def _latest_text(overview: ParameterOverview) -> str:
    if overview.latest is None:
        return NOT_RECORDED
    return f"v{overview.latest.version} desde {_date(overview.latest.effective_from)}"


def _current_table(groups: Sequence[GroupView]) -> Table:
    rows = tuple(
        row(group.form.nome, line.rotulo, line.valor, group.form.modulo_nome)
        for group in groups
        for line in group.rows
    )
    return Table(title=CURRENT_TABLE, columns=CURRENT_COLUMNS, rows=rows, per_project=False)


def _history_table(history: Sequence[HistoryEntry]) -> Table:
    rows = tuple(
        row(
            f"v{entry.version}",
            entry.group_name,
            _period(entry),
            entry.author_name or NOT_RECORDED,
            entry.justification or INITIAL_JUSTIFICATION,
            len(entry.changes),
        )
        for entry in history
    )
    return Table(title=HISTORY_TABLE, columns=HISTORY_COLUMNS, rows=rows, per_project=False)


def _period(entry: HistoryEntry) -> str:
    """A vigência de uma versão: ``dd/mm/aaaa em diante`` (o GestNow não guarda a vigência fim)."""
    return f"{_date(entry.effective_from)} em diante"


def colaboradores_document(
    *,
    rows: Sequence[CollaboratorRow],
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """O documento da tela de Colaboradores: a lista de quem tem acesso, com os papéis por projeto."""
    return Document(
        namespace="configuracoes",
        idioma=idioma,
        title=COLLABORATORS_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        context=(("Pessoas no cadastro", str(len(rows))),),
        tables=(
            Table(
                title=COLLABORATORS_TABLE,
                columns=COLLABORATORS_COLUMNS,
                rows=tuple(_collaborator_row(registro) for registro in rows),
                per_project=False,
            ),
        ),
    )


def _collaborator_row(registro: CollaboratorRow) -> Row:
    return row(
        registro.name,
        registro.email,
        registro.role or NOT_RECORDED,
        registro.general_profile,
        registro.bond,
        registro.company_name or NOT_RECORDED,
        _situation(registro),
        _schedule_roles_text(registro),
    )


def _situation(registro: CollaboratorRow) -> Cell:
    return Cell(ACTIVE_TEXT, Tone.OK) if registro.active else Cell(SUSPENDED_TEXT, Tone.NEUTRAL)


def _schedule_roles_text(registro: CollaboratorRow) -> str:
    if not registro.schedule_roles:
        return NOT_RECORDED
    return " · ".join(line.label for line in registro.schedule_roles)


# ── Cadastros de apoio (ISSUE-078) ───────────────────────────────────────

REGISTERS_TITLE = "Cadastros de apoio"
REGISTERS_CONTEXT = "Registros"

COMPANY_COLUMNS = (
    Column("Nome", width=36),
    Column("Tipo", width=16),
)

PERSON_COLUMNS = (
    Column("Nome", width=28),
    Column("Função", width=20),
    Column("Empresa", width=24),
    Column("E-mail", width=30),
)

PROJECT_COLUMNS = (
    Column("Código", width=14),
    Column("Nome", width=28),
    Column("Cliente", width=20),
    Column("Gerente", width=22),
    Column("Orçamento", ValueKind.MONEY, width=18),
    Column("Início", ValueKind.DATE, width=12),
    Column("Término", ValueKind.DATE, width=12),
    Column("Notas", width=24),
)

SYSTEM_COLUMNS = (
    Column("Projeto", width=24),
    Column("Código", width=14),
    Column("Nome", width=28),
    Column("Área", width=18),
)

UNIT_COLUMNS = (
    Column("Tipo", width=14),
    Column("Código", width=12),
    Column("Nome", width=28),
)

LOCATION_COLUMNS = (
    Column("Projeto", width=24),
    Column("Código", width=14),
    Column("Nome", width=28),
)

DISCIPLINE_COLUMNS = (Column("Nome", width=28),)


def registers_document(
    *,
    overview: RegistersOverview,
    scope: Scope,
    projects: Sequence[ProjectLike],
    today: date,
    idioma: str = "pt",
) -> Document:
    """O documento da tela de Cadastros: as sete tabelas, com as mesmas colunas da tela.

    Sistemas e locais trazem a coluna Projeto em qualquer escopo porque são por
    projeto; as demais tabelas não abrem a coluna no Portfólio (``per_project``
    falso): uma empresa não pertence a um projeto.
    """
    return Document(
        namespace="configuracoes",
        idioma=idioma,
        title=REGISTERS_TITLE,
        scope_label=describe_scope(scope, projects),
        generated_on=today,
        portfolio=scope.is_portfolio,
        context=((REGISTERS_CONTEXT, str(overview.total)),),
        tables=(
            _companies_table(overview.companies),
            _people_table(overview.people),
            _projects_table(overview.projects),
            _systems_table(overview.systems),
            _units_table(overview.units),
            _locations_table(overview.locations),
            _disciplines_table(overview.disciplines),
        ),
    )


def _companies_table(companies: Sequence[CompanyRegisterRow]) -> Table:
    return Table(
        title="Empresas",
        columns=COMPANY_COLUMNS,
        rows=tuple(row(item.name, item.kind or NOT_RECORDED) for item in companies),
        per_project=False,
    )


def _people_table(people: Sequence[PersonRegisterRow]) -> Table:
    return Table(
        title="Pessoas",
        columns=PERSON_COLUMNS,
        rows=tuple(
            row(item.name, item.role or NOT_RECORDED, item.company_name or NOT_RECORDED, item.email)
            for item in people
        ),
        per_project=False,
    )


def _projects_table(projects: Sequence[ProjectRegisterRow]) -> Table:
    return Table(
        title="Projetos",
        columns=PROJECT_COLUMNS,
        rows=tuple(
            row(
                item.code,
                item.name,
                item.client_name,
                item.manager_name,
                item.budget_cents,
                item.start_date,
                item.expected_end_date,
                item.grades_text or NOT_RECORDED,
            )
            for item in projects
        ),
        per_project=False,
    )


def _systems_table(systems: Sequence[SystemRegisterRow]) -> Table:
    return Table(
        title="Sistemas",
        columns=SYSTEM_COLUMNS,
        rows=tuple(
            row(item.project_label, item.code, item.name, item.area or NOT_RECORDED)
            for item in systems
        ),
        per_project=False,
    )


def _units_table(units: Sequence[UnitRegisterRow]) -> Table:
    return Table(
        title="Unidades",
        columns=UNIT_COLUMNS,
        rows=tuple(row(item.kind, item.code, item.name) for item in units),
        per_project=False,
    )


def _locations_table(locations: Sequence[LocationRegisterRow]) -> Table:
    return Table(
        title="Locais",
        columns=LOCATION_COLUMNS,
        rows=tuple(row(item.project_label, item.code, item.name) for item in locations),
        per_project=False,
    )


def _disciplines_table(disciplines: Sequence[DisciplineRegisterRow]) -> Table:
    return Table(
        title="Disciplinas",
        columns=DISCIPLINE_COLUMNS,
        rows=tuple(row(item.name) for item in disciplines),
        per_project=False,
    )


def _date(value: date) -> str:
    return format_value(ValueKind.DATE, value)
