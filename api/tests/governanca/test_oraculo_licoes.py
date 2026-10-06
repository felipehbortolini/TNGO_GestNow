"""Oráculo das lições (ISSUE-027): o acervo da demonstração em 25/09/2026.

Os números saem de ``mock-governanca.js`` (``licoes``) com a regra de ``licoes.html``: o projeto vê as
próprias lições e as Corporativas publicadas dos outros. Das dez lições, oito são do projeto TN-2026-014
(sete Corporativas); publicadas nele: 0001, 0002, 0003 e 0008 (Construção 3, Suprimentos 1); reusos
2 + 3 + 1 = 6. As dos outros dois projetos não estão publicadas (TN-2026-027 vê 5: 1 própria e 4 Corporativas). Sem divergência com o protótipo.
"""

from __future__ import annotations

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Person, Project
from src.modulos.governanca import lessons_models as lm
from src.modulos.governanca import lessons_service
from tests.governanca.apoio import usuario_de
from tests.oraculo import OracleContext, register_check

SITUACOES_DO_PROJETO_14 = {"Publicada": 4, "Rascunho": 2, "Em validação": 1, "Validada": 1}


def _acervo(
    context: OracleContext, *, codigo: str | None, **filtros: str
) -> lessons_service.Acervo:
    session = context.session
    admin = session.scalars(
        select(Collaborator)
        .join(Person, Person.id == Collaborator.person_id)
        .where(Person.email == ADMIN_EMAIL)
    ).one()
    projeto = (
        session.scalars(select(Project).where(Project.code == codigo)).one() if codigo else None
    )
    return lessons_service.acervo(
        session,
        user=usuario_de(admin),
        scope=Scope(project_id=projeto.id if projeto else None, source="url"),
        filters=lessons_service.LessonFilter(**filtros),
    )


def _afirmar_acervo_do_projeto(context: OracleContext) -> None:
    visao = _acervo(context, codigo="TN-2026-014")
    assert visao.total_in_scope == 8, "8 licoes do projeto TN-2026-014"
    situacoes: dict[str, int] = {}
    for linha in visao.rows:
        situacoes[linha.situation] = situacoes.get(linha.situation, 0) + 1
    assert situacoes == SITUACOES_DO_PROJETO_14
    assert visao.counts.own == 8 and visao.counts.corporate == 7
    assert visao.published_by_phase["Construção"] == 3, "checklist de kickoff: Construção"
    assert visao.published_by_phase["Suprimentos"] == 1, "checklist de kickoff: Suprimentos"
    assert sum(linha.reuses for linha in visao.rows) == 6, "reusos do prototipo"


def _afirmar_acervo_do_portfolio(context: OracleContext) -> None:
    visao = _acervo(context, codigo=None)
    assert visao.total_in_scope == 10, "o Portfolio ve as 10 licoes"
    assert len(_acervo(context, codigo=None, situation=lm.SITUATION_PUBLISHED).rows) == 4


def _afirmar_projeto_com_corporativas_de_outros(context: OracleContext) -> None:
    visao = _acervo(context, codigo="TN-2026-027")
    assert visao.total_in_scope == 5, "1 propria (LA-TR) e as 4 Corporativas publicadas de outro"


register_check("licoes: acervo do projeto", _afirmar_acervo_do_projeto)
register_check("licoes: acervo do portfolio", _afirmar_acervo_do_portfolio)
register_check(
    "licoes: corporativas de outros projetos", _afirmar_projeto_com_corporativas_de_outros
)
