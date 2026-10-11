"""Análise do período na carga de demonstração (ISSUE-081/ISSUE-082, D6).

Chamado pelo runner, que importa o ``seed`` de cada módulo.

Lê as análises dos mocks do protótipo (``prototype_collection("analisesPeriodo")``: 40 registros
dos módulos 02 a 07, doze deles do Portfólio) e grava pela fachada, com a trilha da criação, como
o relato. A parte ``relatorio-analises`` (ISSUE-081) grava os módulos 02, 03 e 04 — inclusive as
seis análises do Portfólio, que a 082 lê; a parte ``relatorio-analises-050607`` (ISSUE-082) grava
os módulos 05, 06 e 07 (18 registros: 12 de projeto e 6 do Portfólio), sem desvios porque o
comentário é opcional e nenhum foi salvo no mock. Os períodos andam em períodos inteiros, não em
dias: com a data de referência da execução, a última semana e o último mês fechados do protótipo
continuam sendo a última semana e o último mês fechados de hoje. Os carimbos de criação e de
edição andam em dias, como toda data da carga (``shift_date``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy.orm import Session

from src.carga import DEMO_ANCHOR, prototype_collection, register, shift_date
from src.core import calendario
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations as planning_calculations
from src.modulos.relatorio import service
from src.modulos.relatorio.models import Analysis, AnalysisDeviation

PART_NAME = "relatorio-analises"

PART_NAME_050607 = "relatorio-analises-050607"

# As partes são pinadas aos seus módulos: a 081 gravou os 02/03/04 e a 082 grava os 05/06/07, sem
# depender de ``ANALYSIS_MODULES`` (que a 082 estendeu) — num banco novo cada parte grava a sua
# metade e num banco já carregado só a parte nova roda.
MODULES_081 = ("planejamento", "financeiro", "suprimentos")

MODULES_050607 = ("riscos", "qualidade", "hse")


def load_analyses(session: Session, reference_date: date) -> None:
    """Grava as análises do protótipo dos módulos 02, 03 e 04 (ISSUE-081)."""
    _load(session, reference_date, MODULES_081)


def load_analyses_050607(session: Session, reference_date: date) -> None:
    """Grava as análises do protótipo dos módulos 05, 06 e 07 (ISSUE-082)."""
    _load(session, reference_date, MODULES_050607)


def _load(session: Session, reference_date: date, modules: Sequence[str]) -> None:
    """Grava as análises do protótipo dos módulos pedidos, deslocadas para a data da execução."""
    projects = {project.code: project.id for project in configuracoes.list_projects(session)}
    project_ids = {
        source["id"]: projects[source["codigo"]] for source in prototype_collection("projetos")
    }
    emails = {source["id"]: source["email"] for source in prototype_collection("pessoas")}
    for source in prototype_collection("analisesPeriodo"):
        module = source["modulo"]
        if module not in modules:
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

register(PART_NAME_050607, load_analyses_050607)
