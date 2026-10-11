"""Análise do período na carga de demonstração (ISSUE-081, D6).

Chamado pelo runner, que importa o ``seed`` de cada módulo.

Lê as análises dos mocks do protótipo (``prototype_collection("analisesPeriodo")``: 22 registros
dos módulos 02, 03 e 04, seis deles do Portfólio, que a ISSUE-082 lê) e grava pela fachada, com
a trilha da criação, como o relato. Os períodos andam em períodos inteiros, não em dias: com a
data de referência da execução, a última semana e o último mês fechados do protótipo continuam
sendo a última semana e o último mês fechados de hoje. Os carimbos de criação e de edição andam
em dias, como toda data da carga (``shift_date``).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from src.carga import DEMO_ANCHOR, prototype_collection, register, shift_date
from src.core import calendario
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations as planning_calculations
from src.modulos.relatorio import service
from src.modulos.relatorio.models import Analysis, AnalysisDeviation

PART_NAME = "relatorio-analises"


def load_analyses(session: Session, reference_date: date) -> None:
    """Grava as análises do protótipo dos módulos da 081, deslocadas para a data da execução."""
    projects = {project.code: project.id for project in configuracoes.list_projects(session)}
    project_ids = {
        source["id"]: projects[source["codigo"]] for source in prototype_collection("projetos")
    }
    emails = {source["id"]: source["email"] for source in prototype_collection("pessoas")}
    for source in prototype_collection("analisesPeriodo"):
        module = source["modulo"]
        if module not in service.ANALYSIS_MODULES:
            continue
        author = _access(session, emails[source["criadoPorId"]])
        editor = _access(session, emails[source["atualizadoPorId"]])
        analysis = Analysis(
            project_id=(
                project_ids[source["projetoId"]] if source.get("projetoId") is not None else None
            ),
            created_by_id=author.person_id,
            updated_by_id=editor.person_id,
            module=module,
            kind=source["tipo"],
            period=planning_calculations.shift_period(
                source["tipo"], source["periodo"], anchor=DEMO_ANCHOR, reference_date=reference_date
            ),
            text=source["analise"],
            created_at=_moment(source["criadoEm"], reference_date),
            updated_at=_moment(source["atualizadoEm"], reference_date),
            deviations=[
                AnalysisDeviation(
                    key=item["chave"],
                    indicator=item["indicador"],
                    comment=item["comentario"],
                )
                for item in source.get("desvios") or ()
            ],
        )
        service.insert_analysis(session, user_id=author.id, analysis=analysis)


def _access(session: Session, email: str) -> configuracoes.CollaboratorAccess:
    """O colaborador de uma pessoa do protótipo; a parte da plataforma escreveu todas."""
    access = configuracoes.find_access_by_email(session, email)
    if access is None:
        message = f"A pessoa {email} do protótipo não está no cadastro de Colaboradores."
        raise ValueError(message)
    return access


def _moment(text: str, reference_date: date) -> datetime:
    """Um carimbo local do protótipo (``2026-09-21T08:30``) movido para a execução, no fuso do produto."""
    original = datetime.fromisoformat(text)
    return datetime.combine(
        shift_date(original.date(), reference_date),
        original.time(),
        tzinfo=calendario.PRODUCT_TIMEZONE,
    )


register(PART_NAME, load_analyses)
