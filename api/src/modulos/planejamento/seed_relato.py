"""Relato do período na carga de demonstração (ISSUE-044, D6).

Chamado por ``seed.load``, que registra a parte do módulo (6WLA e Relato do período).

Lê os relatos dos mocks do protótipo (``prototype_collection("relatos")``: 9 relatos dos três
projetos, semanais de S36 a S38 e mensais de julho e agosto) e grava pela fachada, com a trilha.
Os períodos andam em períodos inteiros, não em dias: com a data de referência da execução, a
última semana e o último mês fechados do protótipo continuam sendo a última semana e o último
mês fechados de hoje (a semana 39 e setembro seguem pendentes, em andamento). Os carimbos de
criação e de edição andam em dias, como toda data da carga (``shift_date``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.carga import DEMO_ANCHOR, prototype_collection, shift_date
from src.core import calendario
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, service
from src.modulos.planejamento.models import Report
from src.modulos.planejamento.validation import PointInput


def load_reports(session: Session, reference_date: date) -> None:
    """Write the nine reports of the prototype, shifted to the reference date of the run."""
    project_ids = {project.code: project.id for project in configuracoes.list_projects(session)}
    codes = {source["id"]: source["codigo"] for source in prototype_collection("projetos")}
    emails = {source["id"]: source["email"] for source in prototype_collection("pessoas")}
    for source in prototype_collection("relatos"):
        author = _access(session, emails[source["criadoPorId"]])
        editor = _access(session, emails[source["atualizadoPorId"]])
        report = Report(
            project_id=project_ids[codes[source["projetoId"]]],
            created_by_id=author.person_id,
            updated_by_id=editor.person_id,
            kind=source["tipo"],
            period=calculations.shift_period(
                source["tipo"], source["periodo"], anchor=DEMO_ANCHOR, reference_date=reference_date
            ),
            created_at=_moment(source["criadoEm"], reference_date),
            updated_at=_moment(source["atualizadoEm"], reference_date),
        )
        service.fill_report(
            report,
            activities=source["atividadesPeriodo"],
            next_activities=source["atividadesProximo"],
            points=[_point(point) for point in source["pontos"]],
        )
        service.insert_report(session, user_id=author.id, report=report)


def _access(session: Session, email: str) -> configuracoes.CollaboratorAccess:
    """The collaborator of a person of the prototype; the platform part wrote every one of them."""
    access = configuracoes.find_access_by_email(session, email)
    if access is None:
        message = f"A pessoa {email} do protótipo não está no cadastro de Colaboradores."
        raise ValueError(message)
    return access


def _moment(text: str, reference_date: date) -> datetime:
    """A local timestamp of the prototype (``2026-09-21T08:30``) moved to the run, in the product timezone."""
    original = datetime.fromisoformat(text)
    return datetime.combine(
        shift_date(original.date(), reference_date),
        original.time(),
        tzinfo=calendario.PRODUCT_TIMEZONE,
    )


def _point(source: dict[str, Any]) -> PointInput:
    return PointInput(
        description=source["descricao"], nature=source["natureza"], risk=source["risco"]
    )
